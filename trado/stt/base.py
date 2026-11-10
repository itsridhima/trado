"""The speech-to-text interface. Any provider (Groq, local Whisper, ...) implements this."""

from abc import ABC, abstractmethod


class SttError(Exception):
    """Transcription failed. The message is safe and friendly to show the user."""


class RateLimitError(SttError):
    """The provider said 'too many requests' (HTTP 429) and retrying did not help."""


class UnclearSpeechError(SttError):
    """The audio was transcribed, but the provider was not confident it was real, clear speech."""


class SpeechToTextProvider(ABC):
    @abstractmethod
    def transcribe(self, wav_bytes: bytes) -> str:
        """Turn WAV audio (held in memory) into text. Raise SttError on failure."""
