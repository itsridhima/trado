"""Pointing: the AI ends an answer with a hidden tag like [POINT:640,360:Quantity box]. This module hides the tag from
what is shown and spoken, checks it, and turns it into a real position on your screen.

Everything from the AI is untrusted: only whole numbers are accepted, they are clamped to the screenshot's size, and
the label is cleaned. Anything that doesn't fit the exact format is ignored. Pointing is only ever for explaining;
nothing here clicks or types.
"""

import re
from dataclasses import dataclass

from trado.textsafe import strip_control

_TAG = re.compile(
    r"^\[POINT:\s*(?:(none)|(\d{1,5})\s*,\s*(\d{1,5})(?:\s*:\s*([^\]:]{1,60}?))?(?:\s*:\s*screen\d{1,2})?)\s*\]$",
    re.I,
)
_ANY_TAG = re.compile(r"\[POINT:[^\]]*\]", re.I)
_OPENING = "[POINT"


@dataclass(frozen=True)
class Geometry:
    """How the picture the AI saw relates to the real screen."""

    image_width: int  # size of the screenshot that was sent (after shrinking)
    image_height: int
    left: int  # the monitor that was captured, in real screen pixels (can be negative on multi-monitor setups)
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class Target:
    x: int  # real screen position
    y: int
    label: str
    across: float  # 0 to 1 inside the captured monitor
    down: float
    image_x: int  # position in the screenshot the AI saw (after clamping)
    image_y: int


def _clean_label(raw: str) -> str:
    label = strip_control(raw).replace("[", "").replace("]", "")
    return re.sub(r"\s+", " ", label).strip()[:40]


# Models whose up-and-down pointer number was MEASURED (python -m tools.run_pointing_test) to be "height as a fraction
# of the picture's width": it comes out too small by height/width, on every screen shape tried (16:10 and 16:9).
HEIGHT_FIX_MODELS = {"qwen/qwen3.8-27b"}


def resolve_height_fix(model: str, mode: str) -> bool:
    """Should the AI's up-and-down number be multiplied by width/height? 'auto' decides from the model's name."""
    if mode == "aspect":
        return True
    if mode == "none":
        return False
    return model.strip().lower() in HEIGHT_FIX_MODELS


def parse_point_tag(tag: str | None, geometry: Geometry | None, correct_height: bool = False) -> Target | None:
    """Turn a raw tag into a Target, or None for [POINT:none], a malformed tag, or when there is no screenshot.

    With correct_height, the up-and-down number is first multiplied by width/height (see HEIGHT_FIX_MODELS)."""
    if not tag or geometry is None or geometry.image_width <= 0 or geometry.image_height <= 0:
        return None
    match = _TAG.match(tag.strip())
    if not match or match.group(1):
        return None
    raw_y = int(match.group(3))
    if correct_height:
        raw_y = round(raw_y * geometry.image_width / geometry.image_height)
    image_x = min(max(int(match.group(2)), 0), geometry.image_width - 1)
    image_y = min(max(raw_y, 0), geometry.image_height - 1)
    # Use the centre of the screenshot pixel, so the picture's last pixel lands on the screen's last pixel.
    x = geometry.left + min(int((image_x + 0.5) * geometry.width / geometry.image_width), geometry.width - 1)
    y = geometry.top + min(int((image_y + 0.5) * geometry.height / geometry.image_height), geometry.height - 1)
    return Target(
        x=x,
        y=y,
        label=_clean_label(match.group(4) or ""),
        across=image_x / max(1, geometry.image_width - 1),
        down=image_y / max(1, geometry.image_height - 1),
        image_x=image_x,
        image_y=image_y,
    )


def describe_target(target: Target) -> str:
    name = f' "{target.label}"' if target.label else ""
    return (
        f"(Would point at screen position ({target.x}, {target.y}){name}: "
        f"{target.across:.0%} across and {target.down:.0%} down the screen.)"
    )


def strip_point_tags(text: str) -> str:
    """Remove every [POINT:...] tag from a finished piece of text."""
    return re.sub(r"[ \t]+\n", "\n", _ANY_TAG.sub("", text)).strip()


class PointTagFilter:
    """Sits between the AI's streamed text and the screen/voice: passes ordinary text through, holds back anything
    that might be the start of a [POINT...] tag until it is complete, and remembers the tag. A tag that never
    finishes is dropped, so half a tag is never shown or spoken."""

    def __init__(self) -> None:
        self._held = ""
        self.tag: str | None = None

    def feed(self, text: str) -> str:
        buffer, self._held = self._held + text, ""
        visible: list[str] = []
        while buffer:
            start = buffer.find("[")
            if start == -1:
                visible.append(buffer)
                break
            visible.append(buffer[:start])
            rest = buffer[start:]
            upper = rest.upper()
            if upper.startswith(_OPENING):
                end = rest.find("]")
                if end == -1:
                    self._held = rest  # wait for the rest of the tag
                    break
                self.tag = rest[: end + 1]
                buffer = rest[end + 1:]
            elif _OPENING.startswith(upper):
                self._held = rest  # might still turn into "[POINT"
                break
            else:
                visible.append("[")  # an ordinary bracket
                buffer = rest[1:]
        return "".join(visible)

    def flush(self) -> str:
        """Call when the answer is finished. Returns text that was held back but turned out to be ordinary."""
        rest, self._held = self._held, ""
        return "" if rest.upper().startswith(_OPENING) or _OPENING.startswith(rest.upper()) else rest
