"""Offline tests for the Groq provider (no internet or key needed)."""

import unittest
from unittest import mock

import httpx

from trado.stt.base import RateLimitError, SttError, UnclearSpeechError
from trado.stt.groq_whisper import GroqWhisperProvider


def fake_response(status, body=None, headers=None):
    return httpx.Response(status, json=body or {}, headers=headers or {})


class GroqProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = GroqWhisperProvider("test-key")

    def test_empty_key_is_rejected(self):
        with self.assertRaises(SttError):
            GroqWhisperProvider("")

    @mock.patch("trado.stt.groq_whisper.httpx.post")
    def test_success(self, post):
        post.return_value = fake_response(200, {"text": " hello nifty "})
        self.assertEqual(self.provider.transcribe(b"wav"), "hello nifty")

    @mock.patch("trado.stt.groq_whisper.time.sleep")
    @mock.patch("trado.stt.groq_whisper.httpx.post")
    def test_429_then_success(self, post, sleep):
        post.side_effect = [
            fake_response(429, headers={"retry-after": "1"}),
            fake_response(200, {"text": "ok"}),
        ]
        self.assertEqual(self.provider.transcribe(b"wav"), "ok")

    @mock.patch("trado.stt.groq_whisper.time.sleep")
    @mock.patch("trado.stt.groq_whisper.httpx.post")
    def test_429_forever_raises_rate_limit(self, post, sleep):
        post.return_value = fake_response(429, headers={"retry-after": "1"})
        with self.assertRaises(RateLimitError):
            self.provider.transcribe(b"wav")

    @mock.patch("trado.stt.groq_whisper.httpx.post")
    def test_bad_key(self, post):
        post.return_value = fake_response(401)
        with self.assertRaises(SttError):
            self.provider.transcribe(b"wav")

    @mock.patch("trado.stt.groq_whisper.httpx.post")
    def test_network_error(self, post):
        post.side_effect = httpx.ConnectError("no internet")
        with self.assertRaises(SttError):
            self.provider.transcribe(b"wav")


def seg(text, logprob=-0.2, no_speech=0.01):
    return {"text": text, "avg_logprob": logprob, "no_speech_prob": no_speech}


class ConfidenceTests(unittest.TestCase):
    def setUp(self):
        self.provider = GroqWhisperProvider("test-key")

    @mock.patch("trado.stt.groq_whisper.httpx.post")
    def test_clear_speech_passes(self, post):
        post.return_value = fake_response(200, {"text": "x", "segments": [seg(" What is a SIP?")]})
        self.assertEqual(self.provider.transcribe(b"wav"), "What is a SIP?")
        self.assertAlmostEqual(self.provider.last_confidence, -0.2)

    @mock.patch("trado.stt.groq_whisper.httpx.post")
    def test_garbled_speech_is_rejected(self, post):
        post.return_value = fake_response(200, {"text": "x", "segments": [seg(" Vy stocne maj blik.", -1.4)]})
        with self.assertRaises(UnclearSpeechError):
            self.provider.transcribe(b"wav")

    @mock.patch("trado.stt.groq_whisper.httpx.post")
    def test_silence_gives_empty_text(self, post):
        post.return_value = fake_response(200, {"text": "Thank you.", "segments": [seg(" Thank you.", -1.5, 0.9)]})
        self.assertEqual(self.provider.transcribe(b"wav"), "")

    @mock.patch("trado.stt.groq_whisper.httpx.post")
    def test_asks_for_confidence_data_and_sends_language(self, post):
        post.return_value = fake_response(200, {"text": "ok"})
        GroqWhisperProvider("k", language="en").transcribe(b"wav")
        sent = post.call_args.kwargs["data"]
        self.assertEqual(sent["response_format"], "verbose_json")
        self.assertEqual(sent["language"], "en")


if __name__ == "__main__":
    unittest.main()
