"""Offline tests for the rule that decides whether a screenshot goes with a question."""

import unittest

from trado.screen_need import needs_screenshot

# (question, a conversation is already going, should the screenshot be SENT)
CASES = [
    # clearly general knowledge: no screenshot
    ("What is a SIP?", False, False),
    ("And what is the minimum amount?", True, False),
    ("Explain that in simpler words.", True, False),
    ("Tell me about mutual funds.", False, False),
    ("What is the difference between Nifty 50 and Sensex?", False, False),
    ("Which stock should I buy today?", False, False),
    ("How does a limit order work?", False, False),
    ("What are options in the stock market?", False, False),
    ("Why is diversification important?", False, False),
    ("Is there a minimum for a SIP?", False, False),
    ("Who regulates the stock market in India?", False, False),
    ("Define market capitalisation.", False, False),
    ("What does P E ratio mean?", False, False),
    ("Hello", True, False),
    ("Is it risky?", True, False),
    ("What does that mean?", True, False),
    # about the screen: screenshot
    ("What am I looking at?", False, True),
    ("What do you see on my screen?", True, True),
    ("What does this candlestick mean?", False, True),
    ("Where is the sell button?", False, True),
    ("Click the buy button for me.", False, True),
    ("Explain the order window.", False, True),
    ("How do I place an order on this app?", False, True),
    ("Read this for me.", True, True),
    ("Point to the quantity box.", False, True),
    ("What is the number at the top left?", False, True),
    # the screen matters even without an obvious word like "screen"
    ("What is the value in the second row?", True, True),
    ("What does the green number mean?", True, True),
    ("What is written there?", True, True),
    ("What is that number next to Nifty?", True, True),
    ("Which one is the stop loss?", True, True),
    ("What's the P/E there?", True, True),
    ("What is the current price of Reliance?", True, True),
    ("What's my balance?", True, True),
    ("How are my holdings doing?", True, True),
    ("What is my profit so far?", True, True),
    ("Why is the first option greyed out?", True, True),
    # when unsure, the screenshot is sent
    ("Hello", False, True),
    ("What does that mean?", False, True),
    ("Explain that in simpler words.", False, True),
    ("", False, True),
]


class ScreenNeedTests(unittest.TestCase):
    def test_every_example(self):
        wrong = [(q, h, want) for q, h, want in CASES if needs_screenshot(q, h) != want]
        self.assertEqual(wrong, [], "these got the wrong decision (question, history, should send)")

    def test_saying_look_at_my_screen_always_sends_one(self):
        for q in ["What is a SIP? Look at my screen.", "Explain a SIP, and show me on the page", "What is this?"]:
            self.assertTrue(needs_screenshot(q, True), q)

    def test_capital_letters_and_punctuation_do_not_matter(self):
        self.assertFalse(needs_screenshot("  WHAT IS A SIP?!  ", False))
        self.assertTrue(needs_screenshot("WHAT AM I LOOKING AT???", False))


if __name__ == "__main__":
    unittest.main()
