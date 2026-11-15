"""Short conversation memory, so follow-ups like "and what does that mean?" work.

It holds the last few question-and-answer pairs as plain text, only while Trado is open. It is never written to
disk and never holds screenshots. What it stores is the version you saw on screen (private-looking details are
already hidden). The remembered text is sent to Groq with each new question, so it counts toward free-plan limits.
"""

import re
import threading

MAX_ANSWER_CHARS = 700  # a long answer is trimmed when remembered, to protect the free per-minute token limit
MAX_QUESTION_CHARS = 300

_FORGET = re.compile(
    r"\b(?:forget (?:that|this|it|everything|our conversation|what (?:we|i) (?:said|talked about))"
    r"|clear (?:the |your )?(?:memory|conversation|history)"
    r"|(?:start|begin) (?:over|afresh|again)"
    r"|new (?:topic|conversation)"
    r"|reset (?:the |your )?(?:memory|conversation))\b",
    re.I,
)


def is_forget_request(text: str) -> bool:
    """True for short spoken commands like "forget that" or "start over". Long questions never count."""
    words = re.findall(r"[A-Za-z']+", text)
    return 0 < len(words) <= 6 and bool(_FORGET.search(text))


_NON_ANSWER = re.compile(r"^\W*(?:sorry\W+)?i (?:didn't|did not|couldn't|could not) (?:catch|hear|understand) that", re.I)


def is_non_answer(text: str) -> bool:
    """True for replies like "I didn't catch that", which are not worth remembering."""
    return bool(_NON_ANSWER.search(text.strip()))


class ConversationMemory:
    def __init__(self, max_exchanges: int = 5):
        self.max_exchanges = max(0, max_exchanges)
        self._turns: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def add(self, question: str, answer: str) -> None:
        question, answer = question.strip(), answer.strip()
        if self.max_exchanges == 0 or not question or not answer:
            return
        with self._lock:
            self._turns.append((question[:MAX_QUESTION_CHARS], answer[:MAX_ANSWER_CHARS]))
            del self._turns[: -self.max_exchanges]

    def messages(self) -> list[dict]:
        """The remembered turns, oldest first, in the shape the AI expects."""
        with self._lock:
            return [m for q, a in self._turns for m in ({"role": "user", "content": q}, {"role": "assistant", "content": a})]

    def clear(self) -> None:
        with self._lock:
            self._turns.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._turns)
