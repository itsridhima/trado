"""Offline tests for hiding private-looking details. Every number below is made up."""

import unittest

from trado.privacy import luhn_ok, redact_sensitive, verhoeff_ok


class CheckDigitTests(unittest.TestCase):
    def test_verhoeff_known_examples(self):
        self.assertTrue(verhoeff_ok("2363"))  # standard textbook example
        self.assertFalse(verhoeff_ok("2364"))

    def test_luhn_known_examples(self):
        self.assertTrue(luhn_ok("4539578763621486"))  # a made-up test card number
        self.assertFalse(luhn_ok("4539578763621487"))


class RedactionTests(unittest.TestCase):
    def hidden(self, text):
        return redact_sensitive(text)

    def test_pan_is_hidden_in_both_written_and_spoken_form(self):
        out, n = self.hidden("My PAN is ABCDE1234F please")
        self.assertNotIn("ABCDE1234F", out)
        self.assertEqual(n, 1)
        out, n = self.hidden("it is A B C D E 1 2 3 4 F ok")
        self.assertNotIn("A B C D E", out)
        self.assertEqual(n, 1)

    def test_aadhaar_hidden_when_named_or_valid_but_years_are_left_alone(self):
        out, n = self.hidden("My Aadhaar number is 1234 5678 9012")
        self.assertNotIn("1234 5678 9012", out)
        self.assertEqual(n, 1)
        self.assertEqual(self.hidden("FY 2022 2023 2024 results"), ("FY 2022 2023 2024 results", 0))

    def test_card_number_hidden_only_if_it_passes_the_card_check(self):
        out, n = self.hidden("card 4539 5787 6362 1486 expires soon")
        self.assertNotIn("4539 5787", out)
        self.assertEqual(n, 1)
        text = "levels 24500 25000 24800 24900 held"
        self.assertEqual(self.hidden(text), (text, 0))

    def test_phone_email_upi_account(self):
        for text, secret in [
            ("call me on 98765 43210 today", "98765 43210"),
            ("call +91 9876543210 now", "9876543210"),
            ("mail me at someone@example.com", "someone@example.com"),
            ("pay to name@okbank", "name@okbank"),
            ("my account number is 123456789012345", "123456789012345"),
        ]:
            out, n = self.hidden(text)
            self.assertNotIn(secret, out, text)
            self.assertGreaterEqual(n, 1, text)

    def test_otp_pin_cvv_and_password(self):
        for text, secret in [
            ("the OTP is 482913", "482913"),
            ("my pin: 4821", "4821"),
            ("cvv is 123", "123"),
            ("my password is hunter2 ok", "hunter2"),
        ]:
            out, _ = self.hidden(text)
            self.assertNotIn(secret, out, text)

    def test_normal_trading_text_is_untouched(self):
        for text in [
            "What is a SIP of 5000 rupees a month?",
            "Nifty 50 closed near 24,500 with a P/E of 22.4.",
            "I forgot my password and need to learn about demat accounts.",
            "The 2024 budget changed the capital gains rate to 12.5 percent.",
        ]:
            self.assertEqual(self.hidden(text), (text, 0), text)


if __name__ == "__main__":
    unittest.main()
