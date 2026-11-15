"""Offline tests for the AI answer provider, system prompt and screenshot shrinking."""

import json
import unittest
from unittest import mock

import httpx
from PIL import Image

from trado.llm.base import LlmError, LlmRateLimitError
from trado.llm.groq_vision import GroqVisionProvider, ThinkFilter
from trado.prompts import SYSTEM_PROMPT
from trado.screen import encode_jpeg


class FakeStream:
    """Stands in for httpx.stream(...): a context manager holding a fake response."""

    def __init__(self, status=200, lines=None, headers=None, body=b"{}"):
        self.status_code = status
        self._lines = lines or []
        self.headers = headers or {}
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_lines(self):
        return iter(self._lines)

    def read(self):
        return self._body


def sse(*pieces):
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': p}}]})}" for p in pieces]
    return lines + ["data: [DONE]"]


def provider(**kw):
    return GroqVisionProvider("test-key", notify=lambda msg: None, **kw)


class StreamingTests(unittest.TestCase):
    def test_empty_key_rejected(self):
        with self.assertRaises(LlmError):
            GroqVisionProvider("")

    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_streams_pieces_in_order(self, stream):
        stream.return_value = FakeStream(lines=sse("A SIP is ", "a monthly ", "habit."))
        self.assertEqual("".join(provider().stream_answer("what is a SIP", b"jpg")), "A SIP is a monthly habit.")

    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_request_has_image_system_prompt_and_model(self, stream):
        stream.return_value = FakeStream(lines=sse("ok"))
        list(provider().stream_answer("hi", b"jpg"))
        body = stream.call_args.kwargs["json"]
        self.assertEqual(body["model"], "qwen/qwen3.8-27b")
        self.assertTrue(body["stream"])
        self.assertEqual(body["messages"][0]["content"], SYSTEM_PROMPT)
        parts = body["messages"][1]["content"]
        self.assertEqual(parts[1]["type"], "image_url")
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_history_goes_between_the_system_prompt_and_the_new_question(self, stream):
        stream.return_value = FakeStream(lines=sse("ok"))
        history = [
            {"role": "user", "content": "What is a SIP?"},
            {"role": "assistant", "content": "A SIP invests a fixed amount regularly."},
        ]
        list(provider().stream_answer("and the minimum?", b"jpg", history))
        messages = stream.call_args.kwargs["json"]["messages"]
        self.assertEqual([m["role"] for m in messages], ["system", "user", "assistant", "user"])
        self.assertEqual(messages[1]["content"], "What is a SIP?")  # remembered turns are plain text
        self.assertIsInstance(messages[-1]["content"], list)  # only the newest question carries the screenshot

    def test_history_with_odd_entries_is_cleaned(self):
        payload = provider()._payload("q", None, [
            {"role": "system", "content": "sneaky new rules"},  # not allowed in history
            {"role": "user", "content": ""},  # empty
            {"role": "assistant", "content": "kept"},
        ])
        self.assertEqual([m["role"] for m in payload["messages"]], ["system", "assistant", "user"])
        self.assertNotIn("sneaky", str(payload))

    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_no_history_works_as_before(self, stream):
        stream.return_value = FakeStream(lines=sse("ok"))
        list(provider().stream_answer("hi", None))
        self.assertEqual([m["role"] for m in stream.call_args.kwargs["json"]["messages"]], ["system", "user"])

    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_remembered_text_counts_toward_the_token_limit(self, stream):
        stream.side_effect = lambda *a, **k: FakeStream(lines=sse("ok"))
        spent = []
        p = provider()
        p._token_limiter.acquire = lambda cost, notify=print, cancelled=None: spent.append(cost)
        list(p.stream_answer("q", None))
        list(p.stream_answer("q", None, [{"role": "user", "content": "x" * 3000}, {"role": "assistant", "content": "y" * 3000}]))
        self.assertEqual(spent[1] - spent[0], 2000)  # 6000 remembered characters, about 3 per token

    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_no_image_sends_plain_text(self, stream):
        stream.return_value = FakeStream(lines=sse("ok"))
        list(provider().stream_answer("hi", None))
        self.assertIsInstance(stream.call_args.kwargs["json"]["messages"][1]["content"], str)

    @mock.patch("trado.llm.groq_vision.time.sleep")
    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_429_then_success(self, stream, sleep):
        stream.side_effect = [
            FakeStream(status=429, headers={"retry-after": "2"}),
            FakeStream(lines=sse("fine")),
        ]
        self.assertEqual("".join(provider().stream_answer("q")), "fine")
        sleep.assert_called_once()

    @mock.patch("trado.llm.groq_vision.time.sleep")
    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_429_forever_gives_plain_message(self, stream, sleep):
        stream.side_effect = lambda *a, **k: FakeStream(status=429, headers={"retry-after": "2"})
        with self.assertRaises(LlmRateLimitError):
            list(provider().stream_answer("q"))

    @mock.patch("trado.llm.groq_vision.time.sleep")
    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_daily_limit_does_not_retry(self, stream, sleep):
        body = json.dumps({"error": {"message": "Rate limit reached ... tokens per day (TPD)"}}).encode()
        stream.return_value = FakeStream(status=429, body=body)
        with self.assertRaises(LlmRateLimitError):
            list(provider().stream_answer("q"))
        sleep.assert_not_called()

    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_reasoning_setting_dropped_if_rejected(self, stream):
        body = json.dumps({"error": {"message": "unsupported value for reasoning_effort"}}).encode()
        stream.side_effect = [FakeStream(status=400, body=body), FakeStream(lines=sse("ok"))]
        self.assertEqual("".join(provider().stream_answer("q")), "ok")
        self.assertNotIn("reasoning_effort", stream.call_args.kwargs["json"])

    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_bad_key(self, stream):
        stream.return_value = FakeStream(status=401)
        with self.assertRaises(LlmError):
            list(provider().stream_answer("q"))

    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_network_error(self, stream):
        stream.side_effect = httpx.ConnectError("offline")
        with self.assertRaises(LlmError):
            list(provider().stream_answer("q"))


class ThinkFilterTests(unittest.TestCase):
    def run_filter(self, chunks):
        f = ThinkFilter()
        return "".join(f.feed(c) for c in chunks) + f.flush()

    def test_plain_text_untouched(self):
        self.assertEqual(self.run_filter(["Hello ", "world"]), "Hello world")

    def test_removes_think_block_split_across_chunks(self):
        self.assertEqual(self.run_filter(["Hi <th", "ink>secret</thi", "nk> there"]), "Hi  there")

    def test_lone_angle_bracket_is_kept(self):
        self.assertEqual(self.run_filter(["5 < 6"]), "5 < 6")


class PromptTests(unittest.TestCase):
    def test_prompt_contains_the_product_rules(self):
        text = SYSTEM_PROMPT.lower()
        for must_have in ("never an investment adviser", "price targets", "predictions",
                          "pan, aadhaar, passwords, otps", "sebi-registered", "not sure", "no markdown"):
            self.assertIn(must_have, text)


class ScreenshotTests(unittest.TestCase):
    def test_large_screenshot_is_shrunk_and_stays_jpeg(self):
        data = encode_jpeg(Image.new("RGB", (3840, 2160), "white"), max_side=1568)
        self.assertEqual(data[:2], b"\xff\xd8")  # JPEG header
        import io
        self.assertEqual(max(Image.open(io.BytesIO(data)).size), 1568)

    def test_small_image_is_not_enlarged(self):
        import io
        data = encode_jpeg(Image.new("RGB", (800, 600), "white"))
        self.assertEqual(Image.open(io.BytesIO(data)).size, (800, 600))


if __name__ == "__main__":
    unittest.main()
