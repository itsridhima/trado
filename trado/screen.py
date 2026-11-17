"""Screen capture. The screenshot lives only in memory; it is never written to disk."""

import ctypes
import io
from dataclasses import dataclass

import mss
from PIL import Image

from trado.pointing import Geometry

MAX_SIDE = 1008  # longest side after shrinking. At this size the AI's sideways pointer positions were measured to be accurate
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


@dataclass(frozen=True)
class Capture:
    """A screenshot (in memory only) plus what is needed to turn a position in it into a real screen position."""

    jpeg: bytes
    image_size: tuple[int, int]  # size of the shrunk picture that is sent to the AI
    monitor: tuple[int, int, int, int]  # left, top, width, height of the captured monitor in real screen pixels

    @property
    def geometry(self) -> Geometry:
        left, top, width, height = self.monitor
        return Geometry(self.image_size[0], self.image_size[1], left, top, width, height)


def encode_jpeg_sized(
    image: Image.Image, max_side: int = MAX_SIDE, quality: int = JPEG_QUALITY
) -> tuple[bytes, tuple[int, int]]:
    """Shrink (keeping the shape) and compress an image to JPEG bytes, in memory. Also returns the final size."""
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
    return buffer.getvalue(), image.size


def encode_jpeg(image: Image.Image, max_side: int = MAX_SIDE, quality: int = JPEG_QUALITY) -> bytes:
    """Shrink and compress an image to JPEG bytes, in memory."""
    return encode_jpeg_sized(image, max_side, quality)[0]


def capture_screen(max_side: int = MAX_SIDE) -> Capture:
    """Grab the screen under the mouse. Kept in memory only, never saved anywhere."""
    make_dpi_aware()
    with mss.mss() as sct:
        monitor = _pick_monitor(sct.monitors)
        shot = sct.grab(monitor)
        image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    jpeg, size = encode_jpeg_sized(image, max_side)
    return Capture(jpeg, size, (monitor["left"], monitor["top"], monitor["width"], monitor["height"]))


def capture_screen_jpeg() -> bytes:
    """Like capture_screen(), but returns only the JPEG bytes."""
    return capture_screen().jpeg
