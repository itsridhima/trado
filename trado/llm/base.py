"""The AI-answer interface. Any provider (Groq, Gemini, ...) implements this so it can be swapped."""

from abc import ABC, abstractmethod
from typing import Iterator


class LlmError(Exception):
    """The AI request failed. The message is safe and friendly to show the user."""


class LlmRateLimitError(LlmError):
    """The provider said 'too many requests' (HTTP 429) and waiting did not help."""


class LlmProvider(ABC):
    @abstractmethod
    def stream_answer(self, question: str, image_jpeg: bytes | None = None) -> Iterator[str]:
        """Yield the answer in small pieces as it arrives. Raise LlmError on failure."""
