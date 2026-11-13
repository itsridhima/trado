"""`python -m trado --setup`: store your Groq key in a private local folder (not synced to the cloud).

The key is typed with the screen hidden, never printed, and written only to your own PC.
"""

import getpass
import re

from trado.config import PROJECT_ROOT, private_env_path


def upsert_env_value(text: str, name: str, value: str) -> str:
    """Set NAME=value in .env-style text, replacing an existing NAME= line or adding one."""
    line = f"{name}={value}"
    pattern = re.compile(rf"^{re.escape(name)}=.*$", re.M)
    if pattern.search(text):
        return pattern.sub(lambda _m: line, text, count=1)
    return text + ("" if text.endswith("\n") or not text else "\n") + line + "\n"


def changeable_settings() -> set[str]:
    """Names of the ordinary (non-secret) settings listed in .env.example, e.g. TRADO_HOTKEY."""
    example = PROJECT_ROOT / ".env.example"
    text = example.read_text(encoding="utf-8") if example.is_file() else ""
    return {name for name in re.findall(r"^([A-Z][A-Z0-9_]*)=", text, re.M) if "KEY" not in name or name == "TRADO_HOTKEY"}


def set_setting(assignment: str) -> str:
    """`python -m trado --set NAME=value`: change one ordinary setting in your private settings file.

    Secrets (API keys) can't be set this way; use --setup for those, so they are never typed on a command line.
    Returns a message to show the user.
    """
    name, sep, value = assignment.partition("=")
    name, value = name.strip().upper(), value.strip()
    if not sep or not name:
        return "Use it like this:  python -m trado --set TRADO_HOTKEY=ctrl+alt_l"
    if name not in changeable_settings():
        return f"'{name}' isn't a setting I can change this way. Settings you can change are listed in .env.example (keys are set with --setup)."
    if name == "TRADO_HOTKEY":
        from trado.hotkey import _parse_part

        try:
            for part in value.split("+"):
                _parse_part(part)
        except ValueError as err:
            return f"Not saved. {err}"
    path = private_env_path()
    if path is None:
        return "Couldn't find your private Windows folder (LOCALAPPDATA), so nothing was saved."
    if path.is_file():
        text = path.read_text(encoding="utf-8")
    else:
        example = PROJECT_ROOT / ".env.example"
        text = example.read_text(encoding="utf-8") if example.is_file() else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(upsert_env_value(text, name, value), encoding="utf-8")
    return f"Saved {name}={value} in your private settings file. Restart Trado for it to take effect."


def run_setup() -> None:
    path = private_env_path()
    if path is None:
        print("Couldn't find your private Windows folder (LOCALAPPDATA), so I can't set this up.")
        return

    print("Trado key setup")
    print("Your key will be saved in a private folder on this PC that cloud sync (OneDrive) does not copy:")
    print(f"  {path}")
    print("Get a free key at https://console.groq.com/keys . What you type is hidden and is never shown again.\n")
    try:
        key = getpass.getpass("Paste your Groq API key and press Enter (nothing will appear): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled. Nothing was saved.")
        return
    if not key:
        print("No key entered. Nothing was saved.")
        return
    if any(ch.isspace() for ch in key) or len(key) < 20:
        print("That doesn't look like a Groq key (they are long, with no spaces). Nothing was saved.")
        return

    if path.is_file():
        text = path.read_text(encoding="utf-8")
    else:
        example = PROJECT_ROOT / ".env.example"
        text = example.read_text(encoding="utf-8") if example.is_file() else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(upsert_env_value(text, "GROQ_API_KEY", key), encoding="utf-8")
    print("\nSaved. You can now run:  python -m trado")
    print("If an old .env file with a key is still inside your project folder, delete it.")
