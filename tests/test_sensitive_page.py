"""Offline tests for the check that runs before a screenshot is sent."""

import unittest

from trado.sensitive_page import PageGuard, classify_title, foreground_window_title


class ClassifyTests(unittest.TestCase):
    def test_private_pages_are_recognised(self):
        for title in [
            "Zerodha Kite - Dashboard",
            "Sign in to your account - Google Chrome",
            "SBI Net Banking | Login",
            "Complete your KYC | Groww",
            "Enter OTP to continue",
            "Pay now - Checkout",
        ]:
            self.assertIsNotNone(classify_title(title), title)

    def test_kinds(self):
        self.assertEqual(classify_title("Complete your KYC | Groww"), "KYC or identity")
        self.assertEqual(classify_title("Zerodha Kite - Dashboard"), "broker account")

    def test_ordinary_pages_are_left_alone(self):
        for title in [
            "",
            "Nifty 50 chart - TradingView",
            "Bank Nifty live chart",
            "Zerodha Varsity - Stock market lessons",
            "Windows PowerShell",
            "What is a P/E ratio? - Investopedia",
        ]:
            self.assertIsNone(classify_title(title), title)

    def test_real_window_title_call_returns_text(self):
        self.assertIsInstance(foreground_window_title(), str)


class GuardTests(unittest.TestCase):
    def guard(self, mode, title, answers):
        asked = []

        def asker(kind):
            asked.append(kind)
            return answers.pop(0)

        return PageGuard(mode, title_getter=lambda: title, asker=asker), asked

    def test_ordinary_page_is_allowed_without_asking(self):
        guard, asked = self.guard("ask", "Nifty 50 chart - TradingView", [])
        self.assertEqual(guard.check(), (True, ""))
        self.assertEqual(asked, [])

    def test_ask_no_blocks_and_never_shows_the_title(self):
        guard, asked = self.guard("ask", "Zerodha Kite - secret-account-name", [False])
        allowed, note = guard.check()
        self.assertFalse(allowed)
        self.assertIn("did NOT send a screenshot", note)
        self.assertNotIn("secret-account-name", note)
        self.assertEqual(len(asked), 1)

    def test_ask_yes_allows_and_is_remembered_for_that_page(self):
        guard, asked = self.guard("ask", "Zerodha Kite - Dashboard", [True])
        self.assertEqual(guard.check(), (True, ""))
        self.assertEqual(guard.check(), (True, ""))
        self.assertEqual(len(asked), 1)  # not asked a second time

    def test_a_no_is_asked_again_next_time(self):
        guard, asked = self.guard("ask", "Zerodha Kite - Dashboard", [False, False])
        guard.check()
        guard.check()
        self.assertEqual(len(asked), 2)

    def test_skip_never_asks_and_never_sends(self):
        guard, asked = self.guard("skip", "Sign in", [])
        self.assertFalse(guard.check()[0])
        self.assertEqual(asked, [])

    def test_send_mode_always_allows(self):
        guard, asked = self.guard("send", "Sign in", [])
        self.assertEqual(guard.check(), (True, ""))
        self.assertEqual(asked, [])


if __name__ == "__main__":
    unittest.main()
