"""Text helpers for speaking: cut a streaming answer into sentences, and make text easy to say aloud."""

import re

# Words ending in a full stop that do NOT end a sentence ("Rs. 500", "e.g. a SIP").
_ABBREVIATIONS = {
    "rs", "no", "vs", "mr", "mrs", "ms", "dr", "approx", "etc", "e.g", "i.e", "inc", "ltd", "st", "sr", "jr",
}
_BOUNDARY = re.compile(r"([.!?]+[\"')\]]*)(\s+)")


class SentenceSplitter:
    """Feed it the answer as it streams in; it hands back each sentence as soon as it is complete."""

    MIN_CHARS = 25  # tiny sentences like "Sure." are joined to the next one so speech isn't choppy
    MAX_CHARS = 220  # a very long sentence is cut at a comma so speech can start sooner

    def __init__(self) -> None:
        self._buf = ""

    def feed(self, text: str) -> list[str]:
        self._buf += re.sub(r"\s*\n+\s*", " ", text)
        sentences: list[str] = []
        start = 0
        for match in _BOUNDARY.finditer(self._buf):
            if match.end() >= len(self._buf):
                break  # can't yet see what follows the full stop, so wait for more text
            candidate = self._buf[start:match.end(1)]
            if len(candidate.strip()) < self.MIN_CHARS or not self._is_real_end(candidate, match.group(1)):
                continue
            if match.group(1).startswith(".") and self._buf[match.end()].islower():
                continue  # "... 6.5. and so on" style: the next word is lower-case, so not a new sentence
            sentences.append(candidate.strip())
            start = match.end()
        self._buf = self._buf[start:]

        while len(self._buf) > self.MAX_CHARS:
            cut = max(self._buf.rfind(", ", 0, self.MAX_CHARS), self._buf.rfind("; ", 0, self.MAX_CHARS))
            if cut < 40:
                break
            sentences.append(self._buf[: cut + 1].strip())
            self._buf = self._buf[cut + 2:]
        return sentences

    def flush(self) -> list[str]:
        rest, self._buf = self._buf.strip(), ""
        return [rest] if rest else []

    @staticmethod
    def _is_real_end(candidate: str, punctuation: str) -> bool:
        if not punctuation.startswith("."):
            return True  # ! and ? always end a sentence
        words = candidate.rstrip(".\"')]").split()
        last = words[-1].lower().rstrip(".") if words else ""
        if last in _ABBREVIATIONS:
            return False
        if len(last) == 1 and last.isalpha():
            return False  # an initial such as "A."
        return True


# Capital-letter words that Indian speakers say letter by letter.
_SPELL_OUT = (
    "NSE BSE IPO ETF KYC ELSS NAV AMC RBI GST TDS STT UPI LTCG STCG CAGR EPS ROE ROI FD RD PPF NPS EPF "
    "FII DII FPO OTP PAN"
).split()
_SPELL_RE = re.compile(r"\b(" + "|".join(_SPELL_OUT) + r")\b")

_REPLACEMENTS = [
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),  # markdown links keep only their words
    (re.compile(r"[`*_#>|]+"), " "),  # markdown marks
    (re.compile(r"^\s*[-•]\s+", re.M), ""),  # bullets
    (re.compile(r"₹\s*([\d,.]+)\s*(lakh|crore|thousand|k)?", re.I), lambda m: f"{m.group(1)} {m.group(2) or ''} rupees"),
    (re.compile(r"\bRs\.?\s*([\d,.]+)", re.I), r"\1 rupees"),
    (re.compile(r"\bP\s*/\s*E\b"), "P E"),
    (re.compile(r"\bF\s*&\s*O\b"), "F and O"),
    (re.compile(r"\be\.g\.", re.I), "for example"),
    (re.compile(r"\bi\.e\.", re.I), "that is"),
    (re.compile(r"\bvs\.?", re.I), "versus"),
    (re.compile(r"\bapprox\.", re.I), "approximately"),
    (re.compile(r"\bSEBI\b"), "Sebi"),
    (re.compile(r"&"), " and "),
]


def clean_for_speech(text: str) -> str:
    """Remove markup and rewrite symbols and acronyms so a Windows voice says them sensibly."""
    for pattern, replacement in _REPLACEMENTS:
        text = pattern.sub(replacement, text)
    text = _SPELL_RE.sub(lambda m: " ".join(m.group(1)), text)
    return re.sub(r"\s+", " ", text).strip()
