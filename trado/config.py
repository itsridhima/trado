"""Settings, read from environment variables (and the local .env file)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    hotkey: str
    stt_provider: str
    stt_language: str  # "" means auto-detect


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        hotkey=os.getenv("TRADO_HOTKEY", "f9").strip() or "f9",
        stt_provider=os.getenv("TRADO_STT_PROVIDER", "groq").strip().lower() or "groq",
        stt_language=os.getenv("TRADO_STT_LANGUAGE", "").strip(),
    )
