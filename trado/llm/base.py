"""The AI-answer interface. Any provider (Groq, Gemini, ...) implements this so it can be swapped."""

from abc import ABC, abstractmethod
from typing import Callable, Iterator


class LlmError(Exception):
    """The AI request failed. The message is safe and friendly to show the user."""


class LlmRateLimitError(LlmError):
    """The provider said 'too many requests' (HTTP 429) and waiting did not help."""


class LlmProvider(ABC):
    @abstractmethod
    def stream_answer(
        self,
        question: str,
        image_jpeg: bytes | None = None,
        history: list[dict] | None = None,
        cancelled: Callable[[], bool] | None = None,
        image_size: tuple[int, int] | None = None,
    ) -> Iterator[str]:
        """Yield the answer in small pieces as it arrives. Raise LlmError on failure.

        `history` is earlier turns as [{"role": "user"|"assistant", "content": text}, ...], oldest first.
        Only the current question carries a screenshot. If `cancelled()` becomes true before the request is sent
        (for example while waiting for the free limit), stop quietly without sending it. `image_size` is the width and
        height in pixels of the screenshot, so the AI can say where something is for pointing."""
