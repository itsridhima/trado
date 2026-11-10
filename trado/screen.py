"""Screen capture. The screenshot lives only in memory; it is never written to disk."""

import ctypes
import io

import mss
from PIL import Image

MAX_SIDE = 1568  # longest side after shrinking; keeps text readable and uploads small
JPEG_QUALITY = 80


def make_dpi_aware() -> None:
    """Make Windows report real pixels, not scaled ones (e.g. at 125% or 150% display scaling).

    Without this, a screenshot can be cropped or blurry on scaled displays.
    Safe to call more than once.
    """
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _cursor_position() -> tuple[int, int] | None:
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    point = POINT()
    try:
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return point.x, point.y
    except Exception:
        pass
    return None


def _pick_monitor(monitors: list[dict]) -> dict:
    """monitors[0] is all screens combined; the rest are single screens. Prefer the one under the mouse."""
    singles = monitors[1:] or monitors[:1]
    pos = _cursor_position()
    if pos:
        x, y = pos
        for mon in singles:
            if mon["left"] <= x < mon["left"] + mon["width"] and mon["top"] <= y < mon["top"] + mon["height"]:
                return mon
    return singles[0]  # primary screen


def encode_jpeg(image: Image.Image, max_side: int = MAX_SIDE, quality: int = JPEG_QUALITY) -> bytes:
    """Shrink (keeping the shape) and compress an image to JPEG bytes, in memory."""
    image = image.convert("RGB")
    longest = max(image.size)
    if longest > max_side:
        scale = max_side / longest
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.LANCZOS,
        )
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def capture_screen_jpeg() -> bytes:
    """Grab the screen under the mouse and return it as JPEG bytes (not saved anywhere)."""
    make_dpi_aware()
    with mss.mss() as sct:
        monitor = _pick_monitor(sct.monitors)
        shot = sct.grab(monitor)
        image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    return encode_jpeg(image)
