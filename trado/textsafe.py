"""Make untrusted text safe to print: remove terminal control codes, and hide anything that looks like a secret.

AI answers, server error messages and speech-to-text are all untrusted. Terminal "escape sequences" in them could
change the window title, clear the screen or overwrite lines to fake a message, so they are removed before printing.
"""

import re

# Terminal escape sequences: CSI (ESC [ ...), OSC (ESC ] ... BEL), and any other two-character ESC code.
_ESCAPES = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b.", re.S)
# Other control characters (but not newline or tab), plus text-direction tricks that can disguise text.
_CONTROLS = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f‪-‮⁦-⁩]")

_SECRETS = [
    re.compile(r"\bgsk_[A-Za-z0-9]{8,}"),  # Groq keys
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),  # OpenAI-style keys
    re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}"),  # Google keys
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),  # GitHub tokens
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{10,}"),  # authorization headers
    re.compile(r"\b(?=[A-Za-z0-9_\-]*\d)(?=[A-Za-z0-9_\-]*[A-Za-z])[A-Za-z0-9_\-]{32,}\b"),  # any long token-like string
]


def strip_control(text: str) -> str:
    """Remove terminal escape sequences and control characters."""
    return _CONTROLS.sub("", _ESCAPES.sub("", text))


def redact_secrets(text: str) -> str:
    """Replace anything that looks like an API key or token with [hidden]."""
    for pattern in _SECRETS:
        text = pattern.sub("[hidden]", text)
    return text


def sanitize_message(text: str) -> str:
    """For anything shown to the user that came from outside: no control codes, no secrets."""
    return redact_secrets(strip_control(text))
