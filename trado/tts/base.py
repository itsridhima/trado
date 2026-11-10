"""The voice-out interface. Any provider (Windows voice, an offline neural voice, ...) implements this."""

from abc import ABC, abstractmethod


class TtsError(Exception):
    """Voice setup or playback failed. The message is safe and friendly to show the user."""


class Speaker(ABC):
    @abstractmethod
    def say(self, text: str) -> None:
        """Queue text to be spoken. Returns immediately; sentences play in the order queued."""

    @abstractmethod
    def stop(self) -> None:
        """Stop talking right now and forget anything still queued."""

    def is_speaking(self) -> bool:
        """True while a voice is talking or has sentences waiting."""
        return False


class NullSpeaker(Speaker):
    """Used when voice is turned off (TRADO_TTS=off): everything stays text only."""

    def say(self, text: str) -> None:
        pass

    def stop(self) -> None:
        pass
