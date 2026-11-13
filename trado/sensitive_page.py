"""Before a screenshot is sent, check whether the window in front looks like a login, KYC, bank or broker page.

It only looks at the title of the front window. It never sends or prints that title, and it cannot see
other windows, tabs or notifications, so it is a safety net and not a guarantee.
"""

import ctypes
import re
from typing import Callable

_CATEGORIES = {
    "login": r"sign ?in|log ?in|password|forgot password|otp|one[- ]time password|two[- ]factor|2fa|verify your identity",
    "KYC or identity": r"kyc|e-?kyc|aadhaar|aadhar|digilocker|pan card|e-?sign",
    "banking or payment": r"net ?banking|internet banking|mobile banking|bank account|account statement|"
                          r"credit card|debit card|upi|payment|checkout|wallet|billing",
    "broker account": r"zerodha|kite|groww|upstox|angel one|5paisa|icici direct|hdfc securities|kotak securities|"
                      r"paytm money|sharekhan|motilal oswal|fyers|dhan|demat",
}
_COMPILED = {name: re.compile(rf"\b(?:{pattern})\b", re.I) for name, pattern in _CATEGORIES.items()}
_HARMLESS = re.compile(r"\bvarsity\b", re.I)  # e.g. Zerodha Varsity is a learning site, not an account page


def classify_title(title: str) -> str | None:
    """Name the kind of private page the title suggests, or None."""
    if not title or _HARMLESS.search(title):
        return None
    for name, pattern in _COMPILED.items():
        if pattern.search(title):
            return name
    return None


def foreground_window_title() -> str:
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value
    except Exception:
        return ""


def ask_yes_no(kind: str) -> bool:
    """A Windows Yes/No box that appears on top. The safe answer, No, is the default button."""
    flags = 0x4 | 0x30 | 0x100 | 0x10000 | 0x40000  # Yes/No, warning icon, default No, foreground, topmost
    message = (
        f"The window in front looks like a {kind} page.\n\n"
        "Send a screenshot of it to Groq (a cloud AI service) so Trado can explain it?\n\n"
        "Yes = send it, and don't ask again for this page during this session.\n"
        "No = answer without the screenshot."
    )
    try:
        return ctypes.windll.user32.MessageBoxW(0, message, "Trado: private page?", flags) == 6
    except Exception:
        return False  # if the box can't be shown, play safe and don't send


class PageGuard:
    """Decides whether a screenshot may be taken. Modes: ask (default), skip, send."""

    def __init__(
        self,
        mode: str = "ask",
        title_getter: Callable[[], str] = foreground_window_title,
        asker: Callable[[str], bool] = ask_yes_no,
    ):
        self._mode = mode
        self._title_getter = title_getter
        self._asker = asker
        self._allowed: set[str] = set()  # page titles you said Yes to, kept in memory for this session only

    def check(self) -> tuple[bool, str]:
        """Return (ok to send a screenshot, a message for the terminal, which never contains the page title)."""
        if self._mode == "send":
            return True, ""
        title = self._title_getter()
        kind = classify_title(title)
        if kind is None or title in self._allowed:
            return True, ""
        no_note = (
            f"(The window in front looks like a {kind} page, so I did NOT send a screenshot. "
            "I'll answer from your question alone.)"
        )
        if self._mode == "skip":
            return False, no_note
        if self._asker(kind):
            self._allowed.add(title)
            return True, ""
        return False, no_note
