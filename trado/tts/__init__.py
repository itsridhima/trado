"""Voice-out providers. Add a new one here to make it swappable via TRADO_TTS."""

from trado.config import Settings
from trado.tts.base import NullSpeaker, Speaker, TtsError

__all__ = ["NullSpeaker", "Speaker", "TtsError", "create_speaker"]


def create_speaker(settings: Settings) -> Speaker:
    name = settings.tts_provider
    if name == "off":
        return NullSpeaker()
    if name == "windows":
        from trado.tts.windows_sapi import WindowsSpeaker

        return WindowsSpeaker(settings.tts_voice, settings.tts_rate)
    raise TtsError(f"Unknown voice provider '{name}'. Available: windows, off")
