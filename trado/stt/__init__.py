"""Speech-to-text providers. Add a new one here to make it swappable via TRADO_STT_PROVIDER."""

from trado.config import Settings
from trado.stt.base import RateLimitError, SpeechToTextProvider, SttError

__all__ = ["RateLimitError", "SpeechToTextProvider", "SttError", "create_provider"]


def create_provider(settings: Settings) -> SpeechToTextProvider:
    name = settings.stt_provider
    if name == "groq":
        from trado.stt.groq_whisper import GroqWhisperProvider

        return GroqWhisperProvider(settings.groq_api_key, language=settings.stt_language)
    raise SttError(f"Unknown speech-to-text provider '{name}'. Available: groq")
