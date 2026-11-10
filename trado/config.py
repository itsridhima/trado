"""Settings, read from environment variables (and the local .env file)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_LLM_MODEL = "qwen/qwen3.8-27b"
DEFAULT_STT_MODEL = "whisper-large-v3"  # the full model: a little slower than turbo, a little more accurate


def _int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, "").strip())
    except ValueError:
        return default
    return max(low, min(high, value))


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on")


def _language() -> str:
    """English by default: auto-detect often guesses the wrong language on short clips."""
    value = os.getenv("TRADO_STT_LANGUAGE", "").strip().lower()
    if value == "auto":
        return ""
    return value or "en"


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    hotkey: str
    stt_provider: str
    stt_language: str  # "" means auto-detect
    stt_model: str
    tts_provider: str  # "windows" or "off"
    tts_voice: str  # part of a voice name, e.g. "Zira"; "" means the Windows default
    tts_rate: int  # -10 (slow) to 10 (fast)
    mic_device: str  # "" means the Windows default microphone
    beep: bool
    debug: bool
    llm_provider: str
    llm_model: str
    llm_reasoning: str  # "" means don't send the setting
    send_screen: bool


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        hotkey=os.getenv("TRADO_HOTKEY", "f9").strip() or "f9",
        stt_provider=os.getenv("TRADO_STT_PROVIDER", "groq").strip().lower() or "groq",
        stt_language=_language(),
        stt_model=os.getenv("TRADO_STT_MODEL", "").strip() or DEFAULT_STT_MODEL,
        tts_provider=os.getenv("TRADO_TTS", "windows").strip().lower() or "windows",
        tts_voice=os.getenv("TRADO_VOICE", "").strip(),
        tts_rate=_int("TRADO_VOICE_RATE", 1, -10, 10),
        mic_device=os.getenv("TRADO_MIC_DEVICE", "").strip(),
        beep=_flag("TRADO_BEEP", True),
        debug=_flag("TRADO_DEBUG", False),
        llm_provider=os.getenv("TRADO_LLM_PROVIDER", "groq").strip().lower() or "groq",
        llm_model=os.getenv("TRADO_LLM_MODEL", "").strip() or DEFAULT_LLM_MODEL,
        llm_reasoning=os.getenv("TRADO_LLM_REASONING", "none").strip(),
        send_screen=_flag("TRADO_SEND_SCREEN", True),
    )
