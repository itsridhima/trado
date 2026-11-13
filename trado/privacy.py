"""Hide things that look like private details (PAN, Aadhaar, card and phone numbers, OTPs, passwords...).

Used on what you say before it goes to the AI, and on what the AI says before it is shown or spoken.
It works by patterns, so it can miss things and can occasionally hide something harmless.
It cannot undo audio that was already uploaded for transcription, so don't say private details aloud.
"""

import re

_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def verhoeff_ok(digits: str) -> bool:
    """The check used by real Aadhaar numbers, so random 12-digit numbers (like years) are left alone."""
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def luhn_ok(digits: str) -> bool:
    """The check used by real card numbers."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2:
            n = n * 2 - (9 if n > 4 else 0)
        total += n
    return total % 10 == 0


_EMAIL_OR_UPI = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)*\b")
_LONG_DIGITS = re.compile(r"\b(?:\d[ -]?){11,18}\d\b")  # 12 to 19 digits, maybe spaced
_ACCOUNT = re.compile(r"(?i)\b(account|a/c|acct)\b([^\d\n]{0,25})(\d[\d ]{7,17}\d)\b")
_PAN = re.compile(r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b")
_PAN_SPOKEN = re.compile(r"\b(?:[A-Za-z] ){4}[A-Za-z] (?:\d ){3}\d [A-Za-z]\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?91[ -]?)?[6-9]\d{4}[ -]?\d{5}(?!\d)")
_CODE = re.compile(
    r"(?i)\b(otp|pin|cvv|cvc|passcode|verification code|one[- ]time password)\b\W{0,12}(?:is\W+)?\d(?:[\d -]{1,8}\d)?\b"
)
_PASSWORD = re.compile(r"(?i)\b(password|passwd)\b\s*(?:is\b|:|=)\s*\S+")
_AADHAAR_WORDS = re.compile(r"(?i)aadhaar|aadhar|adhaar|\buid\b")


def redact_sensitive(text: str) -> tuple[str, int]:
    """Return (text with private-looking details replaced by [hidden ...], how many were hidden)."""
    count = 0

    def hit(label: str) -> str:
        nonlocal count
        count += 1
        return f"[hidden {label}]"

    text = _EMAIL_OR_UPI.sub(lambda m: hit("email or UPI ID"), text)

    def long_digits(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        before = text_before(m)
        if len(digits) == 12 and (verhoeff_ok(digits) or _AADHAAR_WORDS.search(before)):
            return hit("Aadhaar-like number")
        if 13 <= len(digits) <= 19 and luhn_ok(digits):
            return hit("card number")
        return m.group(0)

    def text_before(m: re.Match) -> str:
        return m.string[max(0, m.start() - 40): m.start()]

    text = _LONG_DIGITS.sub(long_digits, text)
    text = _ACCOUNT.sub(lambda m: f"{m.group(1)}{m.group(2)}{hit('account number')}", text)
    text = _PAN.sub(lambda m: hit("PAN"), text)
    text = _PAN_SPOKEN.sub(lambda m: hit("PAN"), text)
    text = _PHONE.sub(lambda m: hit("phone number"), text)
    text = _CODE.sub(lambda m: f"{m.group(1)} {hit('code')}", text)
    text = _PASSWORD.sub(lambda m: f"{m.group(1)} {hit('password')}", text)
    return text, count
