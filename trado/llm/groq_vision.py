"""Groq vision model: reads a screenshot plus your question and streams back an answer."""

import base64
import json
import time
from typing import Callable, Iterator

import httpx

from trado.limits import Cancelled, LimitReached, RateLimiter, UsageCounter
from trado.llm.base import LlmError, LlmProvider, LlmRateLimitError
from trado.prompts import SYSTEM_PROMPT, build_user_text
from trado.textsafe import sanitize_message

API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "qwen/qwen3.8-27b"

MAX_ATTEMPTS = 3
MAX_WAIT_SECONDS = 45.0
TEXT_TOKEN_COST = 1400  # rough size of the prompt (about 1,200 tokens) plus a short answer, for the per-minute limit
IMAGE_TOKEN_COST = 2100  # each screenshot counts as about 2,048 tokens on Groq
DAILY_TOKEN_LIMIT = 200_000  # Groq's free plan for this model: about 200,000 tokens a day
MAX_ANSWER_TOKENS = 350


def describe_cost(text_questions: int = 0, screenshot_questions: int = 0) -> str:
    """A plain-words estimate of how much of the free daily allowance some questions will use."""
    tokens = text_questions * TEXT_TOKEN_COST + screenshot_questions * (TEXT_TOKEN_COST + IMAGE_TOKEN_COST)
    return (
        f"(This will use roughly {tokens // 1000:,} thousand of your free daily tokens; Groq's free plan allows about "
        f"{DAILY_TOKEN_LIMIT // 1000} thousand a day, shared with everything else you ask today.)"
    )  # answers are short; this also protects the free tokens-per-minute limit


class ThinkFilter:
    """Removes <think>...</think> text if a model streams its private reasoning."""

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self._buf = ""
        self._inside = False

    def feed(self, text: str) -> str:
        self._buf += text
        out: list[str] = []
        while True:
            if self._inside:
                end = self._buf.find(self.CLOSE)
                if end == -1:
                    self._buf = self._buf[-(len(self.CLOSE) - 1):]
                    break
                self._buf = self._buf[end + len(self.CLOSE):]
                self._inside = False
            else:
                start = self._buf.find(self.OPEN)
                if start == -1:
                    keep = 0  # hold back a possible half-arrived "<thi"
                    for k in range(min(len(self.OPEN) - 1, len(self._buf)), 0, -1):
                        if self.OPEN.startswith(self._buf[-k:]):
                            keep = k
                            break
                    out.append(self._buf[: len(self._buf) - keep])
                    self._buf = self._buf[len(self._buf) - keep:]
                    break
                out.append(self._buf[:start])
                self._buf = self._buf[start + len(self.OPEN):]
                self._inside = True
        return "".join(out)

    def flush(self) -> str:
        rest = "" if self._inside else self._buf
        self._buf = ""
        return rest


def _error_text(raw: bytes) -> str:
    """The server's error message, with control codes and anything key-like removed."""
    try:
        text = str(json.loads(raw).get("error", {}).get("message", ""))
    except Exception:
        text = raw.decode("utf-8", "ignore")[:300]
    return sanitize_message(text)


class GroqVisionProvider(LlmProvider):
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        reasoning_effort: str = "none",
        notify: Callable[[str], None] = print,
    ):
        if not api_key:
            raise LlmError(
                "GROQ_API_KEY is empty. Open your .env file and paste your Groq key after GROQ_API_KEY="
            )
        self._api_key = api_key
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._notify = notify
        # Groq's free plan: 30 requests and about 8,000 tokens a minute, 1,000 requests a day. Stay a little under.
        # A wait of up to a minute is allowed (it is announced, and pressing the hotkey cancels it).
        self._request_limiter = RateLimiter(28, 60.0, "request", max_wait=60.0)
        self._token_limiter = RateLimiter(7000, 60.0, "token", max_wait=60.0)
        # The binding daily limit is TOKENS (about 200,000 a day on the free plan), not requests. Counted as estimates.
        self._usage = UsageCounter(DAILY_TOKEN_LIMIT, "estimated tokens")

    def _payload(
        self,
        question: str,
        image_jpeg: bytes | None,
        history: list[dict] | None = None,
        image_size: tuple[int, int] | None = None,
    ) -> dict:
        text = build_user_text(question, image_jpeg is not None, image_size)
        earlier = [
            {"role": m["role"], "content": str(m["content"])}
            for m in (history or [])
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        if image_jpeg is None:
            user_content = text
        else:
            b64 = base64.b64encode(image_jpeg).decode("ascii")
            user_content = [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *earlier,  # earlier turns: text only, never screenshots
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.4,
            "max_completion_tokens": MAX_ANSWER_TOKENS,
            "stream": True,
        }
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        return payload

    def stream_answer(
        self,
        question: str,
        image_jpeg: bytes | None = None,
        history: list[dict] | None = None,
        cancelled: Callable[[], bool] | None = None,
        image_size: tuple[int, int] | None = None,
    ) -> Iterator[str]:
        payload = self._payload(question, image_jpeg, history, image_size)
        headers = {"Authorization": f"Bearer {self._api_key}"}
        attempt = 0
        remembered_chars = sum(len(m["content"]) for m in payload["messages"][1:-1])  # earlier turns
        tokens = (  # a rough estimate for the free per-minute limit: about 3 characters per token
            TEXT_TOKEN_COST + (IMAGE_TOKEN_COST if image_jpeg is not None else 0) + remembered_chars // 3
        )

        while True:
            attempt += 1
            status, retry_after, detail = 0, "", ""
            try:  # stay inside the free per-minute request and token limits (waits can be cancelled)
                self._request_limiter.acquire(1, notify=self._notify, cancelled=cancelled)
                self._token_limiter.acquire(tokens, notify=self._notify, cancelled=cancelled)
            except Cancelled:
                return  # you gave up on this question while it waited: send nothing
            except LimitReached as err:
                raise LlmRateLimitError(
                    f"To stay inside Groq's free limit I'd have to wait about {err.wait_seconds:.0f} seconds. "
                    "Please wait a moment and ask again."
                ) from None
            if cancelled and cancelled():
                return
            try:
                with httpx.stream(
                    "POST", API_URL, headers=headers, json=payload,
                    timeout=httpx.Timeout(60.0, connect=10.0),
                ) as response:
                    status = response.status_code
                    if status == 200:
                        note = self._usage.record(tokens)
                        if note:
                            self._notify(note)
                        yield from self._read_stream(response)
                        return
                    retry_after = response.headers.get("retry-after", "")
                    detail = _error_text(response.read())
            except httpx.TimeoutException:
                raise LlmError("The AI took too long to answer. Check your internet and try again.")
            except httpx.HTTPError:
                raise LlmError("Could not reach the AI service. Check your internet connection.")

            if status == 429:
                if "per day" in detail.lower() or "(tpd)" in detail.lower():
                    raise LlmRateLimitError(
                        "You've used up Groq's free daily allowance. It resets within a day, so please try again later."
                    )
                wait = self._wait_seconds(retry_after, attempt)
                if attempt < MAX_ATTEMPTS and wait <= MAX_WAIT_SECONDS:
                    self._notify(
                        f"  (Groq's free plan is busy, so I'm waiting about {wait:.0f} seconds and will try again...)"
                    )
                    time.sleep(wait)
                    continue
                raise LlmRateLimitError(
                    "Groq's free plan is allowing only a few questions per minute, and I've hit that limit. "
                    "Please wait a minute and ask again."
                )

            # If the reasoning setting is not accepted by this model, retry once without it.
            if status == 400 and "reasoning" in detail.lower() and "reasoning_effort" in payload:
                del payload["reasoning_effort"]
                self._notify("  (This model doesn't accept the reasoning setting; trying without it.)")
                continue

            if status in (401, 403):
                reason = f" Groq said: {detail[:120]}" if detail else ""
                raise LlmError(
                    f"Groq refused the request (error {status}). If this keeps happening, check GROQ_API_KEY "
                    f"in your .env file.{reason}"
                )
            if status == 404 or (status == 400 and "model" in detail.lower()):
                raise LlmError(
                    f"Groq doesn't know the model '{self._model}'. Check TRADO_LLM_MODEL in your .env "
                    "against the list at console.groq.com/docs/models."
                )
            if status in (400, 413):
                raise LlmError(f"Groq couldn't process the request (error {status}): {detail[:200]}")
            if status >= 500:
                raise LlmError(f"Groq had a problem on its side (error {status}). Try again soon.")
            raise LlmError(f"Groq returned an unexpected error ({status}).")

    @staticmethod
    def _read_stream(response: httpx.Response) -> Iterator[str]:
        think = ThinkFilter()
        try:
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0].get("delta", {})
                except (ValueError, KeyError, IndexError):
                    continue
                piece = think.feed(delta.get("content") or "")
                if piece:
                    yield piece
        except httpx.HTTPError:
            raise LlmError("The connection dropped while the answer was arriving.")
        rest = think.flush()
        if rest:
            yield rest

    @staticmethod
    def _wait_seconds(retry_after: str, attempt: int) -> float:
        try:
            return max(1.0, float(retry_after))
        except ValueError:
            return float(10 * attempt)
