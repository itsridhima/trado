"""Global hold-to-talk hotkey (works while other windows are focused)."""

from typing import Callable

from pynput import keyboard

# Left/right variants count as the same modifier when you write e.g. "ctrl+shift+space".
_GROUPS = {
    "ctrl": {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r},
    "shift": {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r},
    "alt": {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr},
}


def _parse_part(name: str) -> set:
    name = name.strip().lower()
    if name in _GROUPS:
        return _GROUPS[name]
    if hasattr(keyboard.Key, name):
        return {getattr(keyboard.Key, name)}
    if len(name) == 1:
        return {keyboard.KeyCode.from_char(name)}
    raise ValueError(
        f"Unknown hotkey part '{name}'. Try ctrl+alt_l, ctrl+alt, f9, space, or a combo like ctrl+shift+space."
    )


_FRIENDLY = {
    "ctrl": "Ctrl", "ctrl_l": "Left Ctrl", "ctrl_r": "Right Ctrl",
    "alt": "Alt", "alt_l": "Left Alt", "alt_r": "Right Alt", "alt_gr": "AltGr",
    "shift": "Shift", "shift_l": "Left Shift", "shift_r": "Right Shift", "space": "Space",
}


def describe_hotkey(spec: str) -> str:
    """Turn 'ctrl+alt_l' into 'Ctrl + Left Alt' for the start-up message."""
    return " + ".join(_FRIENDLY.get(part.strip().lower(), part.strip().upper()) for part in spec.split("+"))


class HoldToTalkHotkey:
    """Calls on_press when the whole hotkey is held down, on_release when it is let go."""

    def __init__(self, spec: str, on_press: Callable[[], None], on_release: Callable[[], None]):
        self._required = [_parse_part(p) for p in spec.split("+")]
        self._relevant = set().union(*self._required)  # every key that can be part of the hotkey
        self._needs_letters = any(isinstance(k, keyboard.KeyCode) for k in self._relevant)
        self._on_press = on_press
        self._on_release = on_release
        self._down: set = set()
        self._active = False
        self._listener = keyboard.Listener(on_press=self._press, on_release=self._release)

    def _is_held(self) -> bool:
        return all(group & self._down for group in self._required)

    @staticmethod
    def _normalise(key):
        if isinstance(key, keyboard.KeyCode) and key.char:
            return keyboard.KeyCode.from_char(key.char.lower())
        return key

    def _is_ours(self, key) -> bool:
        """True only for keys that are part of the hotkey. Any other key is dropped right here, without being
        read, stored or logged. (Windows hands this program every key you type; this is how we ignore them.)"""
        if isinstance(key, keyboard.KeyCode):
            return self._needs_letters and self._normalise(key) in self._relevant
        return key in self._relevant

    def _press(self, key) -> None:
        if not self._is_ours(key):
            return
        self._down.add(self._normalise(key))
        if not self._active and self._is_held():
            self._active = True
            self._on_press()

    def _release(self, key) -> None:
        if not self._is_ours(key):
            return
        self._down.discard(self._normalise(key))
        if self._active and not self._is_held():
            self._active = False
            self._on_release()

    def start(self) -> None:
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()

    def is_alive(self) -> bool:
        return self._listener.is_alive()

    def wait(self, seconds: float) -> None:
        """Wait a short while. Used in a loop so Ctrl+C can get through (a plain join() blocks it on Windows)."""
        self._listener.join(seconds)
