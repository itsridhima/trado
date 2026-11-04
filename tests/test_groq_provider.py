"""Offline tests for the Groq provider (no internet or key needed)."""

import unittest
from unittest import mock

import httpx

from trado.stt.base import RateLimitError, SttError
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


if __name__ == "__main__":
    unittest.main()
