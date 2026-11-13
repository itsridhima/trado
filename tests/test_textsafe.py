"""Offline tests: terminal codes and secrets are removed from untrusted text, and the settings never show the key."""

import json
import os
import unittest
from unittest import mock

from trado import config
from trado.llm.groq_vision import _error_text
from trado.textsafe import redact_secrets, sanitize_message, strip_control

FAKE_KEY = "gsk_FAKE0123456789abcdefghijklmnop"


class StripControlTests(unittest.TestCase):
    def test_terminal_codes_are_removed(self):
        dirty = "Hello \x1b[2J\x1b]0;FAKE TITLE\x07 world \r overwritten \x1b[31mred\x1b[0m"
        self.assertEqual(strip_control(dirty), "Hello  world  overwritten red")

    def test_text_direction_tricks_and_nulls_are_removed(self):
        self.assertEqual(strip_control("ab‮cd\x00ef"), "abcdef")

    def test_normal_text_newlines_tabs_and_unicode_are_kept(self):
        text = "Line one\n\tIndented ₹5 lakh, café – fine."
        self.assertEqual(strip_control(text), text)


class RedactSecretsTests(unittest.TestCase):
    def test_keys_and_tokens_are_hidden(self):
        for text in [
            f"bad key {FAKE_KEY} was refused",
            "Authorization: Bearer abcdefghijklmnop123456",
            "token ghp_abcdefghijklmnopqrstuvwxyz0123456789",  # secret-scan: fake
            "key sk-abcdefghijklmnopqrstuvwxyz123456",  # secret-scan: fake
            "x AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz012345 y",  # secret-scan: fake
        ]:
            out = redact_secrets(text)
            self.assertIn("[hidden]", out, text)
            for secret in (FAKE_KEY, "abcdefghijklmnop123456", "ghp_abcdef", "sk-abcdef", "AIzaSyAb"):
                self.assertNotIn(secret, out)

    def test_ordinary_sentences_are_untouched(self):
        text = "Groq's free plan is busy, so I'm waiting about 12 seconds (error 429)."
        self.assertEqual(redact_secrets(text), text)


class WhereItMattersTests(unittest.TestCase):
    def test_server_error_text_is_cleaned(self):
        body = json.dumps({"error": {"message": f"Invalid key {FAKE_KEY}\x1b[2J"}}).encode()
        shown = _error_text(body)
        self.assertNotIn(FAKE_KEY, shown)
        self.assertNotIn("\x1b", shown)

    def test_non_json_error_body_is_cleaned_too(self):
        shown = _error_text(f"oops {FAKE_KEY} \x1b]0;x\x07".encode())
        self.assertNotIn(FAKE_KEY, shown)
        self.assertNotIn("\x1b", shown)

    def test_printing_or_logging_the_settings_never_shows_the_key(self):
        env = {"GROQ_API_KEY": FAKE_KEY, "TRADO_ENV_FILE": ""}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch("trado.config.find_env_file", return_value=None):
            settings = config.load_settings()
        self.assertEqual(settings.groq_api_key, FAKE_KEY)  # still usable by the app
        self.assertNotIn(FAKE_KEY, repr(settings))
        self.assertNotIn(FAKE_KEY, str(settings))
        self.assertNotIn("groq_api_key", repr(settings))

    def test_sanitize_message_does_both(self):
        self.assertEqual(sanitize_message(f"a\x1b[2J {FAKE_KEY} b"), "a [hidden] b")


if __name__ == "__main__":
    unittest.main()
