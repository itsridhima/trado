"""Groq Whisper speech-to-text (free tier). Audio is sent from memory, never saved to disk."""

import time

import httpx

from trado.limits import LimitReached, RateLimiter, UsageCounter
from trado.stt.base import RateLimitError, SpeechToTextProvider, SttError, UnclearSpeechError

API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_MODEL = "whisper-large-v3-turbo"

# A hint that helps Whisper spell our name and Indian market words correctly.
VOCAB_HINT = "Trado, Nifty, Sensex, SEBI, NSE, BSE, SIP, mutual fund, demat, F&O, IPO, P/E ratio, stock."

# Whisper's own usual cut-offs for "this is probably not real speech".
NO_SPEECH_LIMIT = 0.6
MIN_LOGPROB = -1.0

MAX_ATTEMPTS = 3
MAX_WAIT_SECONDS = 20.0


class GroqWhisperProvider(SpeechToTextProvider):
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, language: str = ""):
        if not api_key:
            raise SttError(
                "GROQ_API_KEY is empty. Open your .env file and paste your Groq key after "
                "GROQ_API_KEY="
            )
        self._api_key = api_key
        self._model = model
        self._language = language
        self.last_confidence: float | None = None  # shown by TRADO_DEBUG=true
        # Groq's free plan allows 20 speech requests a minute and 2,000 a day; stay a little under.
        self._limiter = RateLimiter(18, 60.0, "speech")
        self._usage = UsageCounter(2000, "speech requests")

    def transcribe(self, wav_bytes: bytes) -> str:
        data = {
            "model": self._model,
            "response_format": "verbose_json",  # includes per-segment confidence numbers
            "temperature": "0",
            "prompt": VOCAB_HINT,
        }
        if self._language:
            data["language"] = self._language

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                self._limiter.acquire(1, notify=print)  # stay inside the free per-minute limit
            except LimitReached as err:
                raise RateLimitError(
                    f"To stay inside Groq's free limit I'd have to wait about {err.wait_seconds:.0f} seconds. "
                    "Please wait a moment and ask again."
                ) from None
            try:
                response = httpx.post(
                    API_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    data=data,
                    files={"file": ("speech.wav", wav_bytes, "audio/wav")},
                    timeout=30.0,
                )
            except httpx.TimeoutException:
                raise SttError("Groq took too long to answer. Check your internet and try again.")
            except httpx.HTTPError:
                raise SttError("Could not reach Groq. Check your internet connection.")

            status = response.status_code
            if status == 200:
                note = self._usage.record()
                if note:
                    print(note)
                return self._judge(response.json())

            if status == 429:
                wait = self._retry_delay(response, attempt)
                if attempt < MAX_ATTEMPTS and wait <= MAX_WAIT_SECONDS:
                    print(f"  (Groq says slow down; retrying in {wait:.0f}s...)")
                    time.sleep(wait)
                    continue
                raise RateLimitError(
                    "Groq's free limit was reached. Wait a minute and try again."
                )

            if status in (401, 403):
                raise SttError("Groq rejected your API key. Check GROQ_API_KEY in your .env file.")
            if status >= 500:
                raise SttError(f"Groq had a problem on its side (error {status}). Try again soon.")
            raise SttError(f"Groq could not transcribe this (error {status}).")

        raise SttError("Transcription failed after several tries.")

    def _judge(self, body: dict) -> str:
        """Return the text, but refuse it if Whisper itself says it was not confident.

        Whisper reports, per segment, how likely it was to be silence (no_speech_prob) and
        how confident it was in its words (avg_logprob; closer to 0 is better). Garbage such
        as "Vy stocne maj blik" usually scores badly, so we ask the user to repeat instead
        of sending garbage to the AI.
        """
        self.last_confidence = None
        segments = body.get("segments") or []
        if not segments:
            return body.get("text", "").strip()

        speech = [
            s for s in segments
            if not (s.get("no_speech_prob", 0.0) > NO_SPEECH_LIMIT and s.get("avg_logprob", 0.0) < MIN_LOGPROB)
        ]
        if not speech:
            return ""  # it was just silence or noise
        mean = sum(s.get("avg_logprob", 0.0) for s in speech) / len(speech)
        self.last_confidence = mean
        if mean < MIN_LOGPROB:
            raise UnclearSpeechError("I couldn't hear that clearly. Please say it again, a bit slower.")
        return "".join(s.get("text", "") for s in speech).strip()

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        header = response.headers.get("retry-after", "")
        try:
            return max(1.0, float(header))
        except ValueError:
            return float(2**attempt)
