"""Settings, read from environment variables (and a local .env file)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_LLM_MODEL = "qwen/qwen3.8-27b"
DEFAULT_STT_MODEL = "whisper-large-v3"  # the full model: a little slower than turbo, a little more accurate
SENSITIVE_PAGE_MODES = ("ask", "skip", "send")
SCREEN_MODES = ("auto", "always")


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


def _screen_mode() -> str:
    value = os.getenv("TRADO_SCREEN_MODE", "").strip().lower()
    return value if value in SCREEN_MODES else "auto"


def _sensitive_mode() -> str:
    value = os.getenv("TRADO_SENSITIVE_PAGES", "").strip().lower()
    return value if value in SENSITIVE_PAGE_MODES else "ask"


# ---------- where the secret file lives ----------

def private_env_path() -> Path | None:
    """The preferred home for your key file: a private folder that cloud sync does not touch."""
    local = os.environ.get("LOCALAPPDATA", "").strip()
    return Path(local) / "Trado" / ".env" if local else None


def find_env_file() -> Path | None:
    """First existing of: TRADO_ENV_FILE, the private local folder, then the project folder."""
    candidates: list[Path] = []
    explicit = os.environ.get("TRADO_ENV_FILE", "").strip()
    if explicit:
        candidates.append(Path(explicit))
    private = private_env_path()
    if private:
        candidates.append(private)
    candidates.append(PROJECT_ROOT / ".env")
    return next((p for p in candidates if p.is_file()), None)


_SYNC_FOLDER_WORDS = ("onedrive", "dropbox", "google drive", "icloud")


def is_synced_path(path: Path) -> bool:
    """True if the path looks like it sits inside a cloud-synced folder (OneDrive, Dropbox, ...)."""
    try:
        text = str(path.resolve()).lower()
    except OSError:
        text = str(path).lower()
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        root = os.environ.get(var, "").strip().lower().rstrip("\\/")
        if root and text.startswith(root):
            return True
    return any(word in part for part in Path(text).parts for word in _SYNC_FOLDER_WORDS)


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = field(repr=False)  # repr=False: printing or logging the settings never shows the key
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
    screen_mode: str  # "auto" = send a screenshot only when the question looks screen-related; "always" = every time
    sensitive_pages: str  # "ask", "skip" or "send": what to do when the screen looks like a login/KYC/bank/broker page
    memory_exchanges: int  # how many recent question-and-answer pairs Trado remembers (0 = none)
    env_file: str  # which key file was loaded ("" if none)
    env_file_synced: bool  # True if that file is inside a cloud-synced folder
    env_overrides: tuple  # names of settings where the Windows environment overrides the key file


def load_settings() -> Settings:
    env_file = find_env_file()
    overrides: tuple[str, ...] = ()
    if env_file:
        # Values already set in the Windows environment win over the file. Remember which ones differ (names only).
        file_values = dotenv_values(env_file)
        overrides = tuple(sorted(k for k, v in file_values.items() if k in os.environ and os.environ[k] != (v or "")))
        load_dotenv(env_file)
    return Settings(
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        hotkey=os.getenv("TRADO_HOTKEY", "ctrl+alt_l").strip() or "ctrl+alt_l",
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
        screen_mode=_screen_mode(),
        sensitive_pages=_sensitive_mode(),
        memory_exchanges=_int("TRADO_MEMORY", 5, 0, 10),
        env_file=str(env_file) if env_file else "",
        env_file_synced=bool(env_file and is_synced_path(env_file)),
        env_overrides=overrides,
    )
