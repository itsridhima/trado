"""Pointing accuracy test: how close does the AI get when asked to point at things whose position we know exactly?

Run from the project folder (needs your Groq key; takes about 4 minutes on the free plan):
    python -m tools.run_pointing_test                    the picture size Trado uses now (see TRADO_SCREEN_MAX_SIDE)
    python -m tools.run_pointing_test --max-side 1008    send a smaller picture, to test whether the AI shrinks it itself
    python -m tools.run_pointing_test --max-side 1008 --aspect 16:9    also change the screen shape (16:9, 4:3 ...)

It draws a FAKE broker page (nothing from your real screen), asks the AI to point at six things, and compares the
answers with the true positions. It also checks whether the AI uses real picture pixels or a 0-to-1000 scale, which
some vision models do, and whether its numbers look like they belong to a smaller copy of the picture.
A marked-up picture is saved in your temporary folder so you can see the result.
"""

import argparse
import re
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from trado.config import load_settings
from trado.llm import LlmError, LlmRateLimitError, create_llm_provider
from trado.llm.groq_vision import describe_cost
from trado.pointing import Geometry, PointTagFilter, parse_point_tag, resolve_height_fix
from trado.screen import MAX_SIDE, encode_jpeg_sized

WIDTH, HEIGHT = 1568, 980  # the size of the picture Trado sends today on a 1920x1200 screen

# name -> (left, top, right, bottom) in the 1568x980 page
TARGETS = {
    "Quantity box": (120, 220, 520, 290),
    "Price box": (120, 360, 520, 430),
    "Buy button": (120, 520, 320, 600),
    "Sell button": (360, 520, 560, 600),
    "Green candle": (900, 300, 960, 480),
    "Profit and loss number": (700, 720, 1100, 800),
}
_RAW = re.compile(r"\[POINT:\s*(\d+)\s*,\s*(\d+)", re.I)
TOLERANCE = 12  # pixels of slack around a box


def page_height_for(aspect: str) -> int:
    """Height of the 1568-wide page for a screen shape like '16:9' (the targets all sit above y=820)."""
    wide, tall = (int(part) for part in aspect.split(":"))
    height = round(WIDTH * tall / wide)
    if not 820 <= height <= 2000:
        raise ValueError(f"A {aspect} page would be {height} pixels tall; use a shape between about 16:12 and 16:9.")
    return height


def make_page(height: int = HEIGHT) -> Image.Image:
    """A fake order window with a chart. Every target's position is known."""
    image = Image.new("RGB", (WIDTH, height), (245, 247, 250))
    draw = ImageDraw.Draw(image)
    big, body, small = ImageFont.load_default(size=34), ImageFont.load_default(size=26), ImageFont.load_default(size=22)
    draw.rectangle([0, 0, WIDTH, 70], fill=(30, 60, 120))
    draw.text((30, 16), "Demo Broker - Order window (not real)", fill="white", font=big)

    def box(name, label):
        left, top, right, bottom = TARGETS[name]
        draw.text((left, top - 36), label, fill=(60, 60, 60), font=small)
        draw.rectangle([left, top, right, bottom], fill="white", outline=(120, 130, 150), width=3)

    box("Quantity box", "Quantity")
    draw.text((140, 238), "10", fill=(30, 30, 30), font=body)
    box("Price box", "Price")
    draw.text((140, 378), "2,950.00", fill=(30, 30, 30), font=body)
    for name, colour, text in (("Buy button", (30, 150, 70), "BUY"), ("Sell button", (200, 50, 50), "SELL")):
        left, top, right, bottom = TARGETS[name]
        draw.rectangle([left, top, right, bottom], fill=colour)
        draw.text(((left + right) // 2 - 28, (top + bottom) // 2 - 14), text, fill="white", font=body)
    draw.text((120, 660), "Demo only: nothing here is real or clickable.", fill=(120, 120, 120), font=small)

    draw.rectangle([700, 140, 1500, 660], fill="white", outline=(180, 185, 195), width=2)
    draw.text((720, 150), "Chart", fill=(60, 60, 60), font=small)
    left, top, right, bottom = TARGETS["Green candle"]
    draw.line([((left + right) // 2, top - 40), ((left + right) // 2, bottom + 40)], fill=(30, 150, 70), width=4)
    draw.rectangle([left, top + 40, right, bottom - 40], fill=(30, 150, 70))
    draw.line([(1130, 330), (1130, 540)], fill=(200, 50, 50), width=4)
    draw.rectangle([1100, 370, 1160, 500], fill=(200, 50, 50))
    left, top, right, bottom = TARGETS["Profit and loss number"]
    draw.rectangle([left, top, right, bottom], fill="white", outline=(120, 130, 150), width=3)
    draw.text((left + 20, top + 18), "P&L:  +1,250", fill=(30, 150, 70), font=big)
    return image


def scaled_targets(scale: float) -> dict:
    """The target boxes for a picture shrunk to `scale` of the 1568-wide page."""
    return {name: tuple(round(v * scale) for v in rect) for name, rect in TARGETS.items()}


def centre(rect):
    return (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2


def inside(rect, x, y, slack=TOLERANCE):
    return rect[0] - slack <= x <= rect[2] + slack and rect[1] - slack <= y <= rect[3] + slack


def _median(values):
    return sorted(values)[len(values) // 2] if values else float("nan")


def evaluate(rows, width=WIDTH, height=HEIGHT, targets=None):
    """rows: [(name, (x, y) or None)]. Compares two ways of reading the AI's numbers and says which fits.

    Also reports how big the AI's numbers are compared with the truth (a ratio of 0.64 means they look like they
    belong to a picture 64% as big as the one sent)."""
    targets = targets or TARGETS
    pixels = thousand = aspect = missing = 0
    errors_px, errors_k, errors_a, ratios_x, ratios_y = [], [], [], [], []
    for name, raw in rows:
        if raw is None:
            missing += 1
            continue
        x, y = raw
        cx, cy = centre(targets[name])
        kx, ky = x / 1000 * width, y / 1000 * height  # if the AI used a 0-1000 scale
        ay = y * width / height  # if the AI's up-and-down number is "height as a fraction of the width"
        pixels += inside(targets[name], x, y)
        thousand += inside(targets[name], kx, ky)
        aspect += inside(targets[name], x, ay)
        errors_a.append(((x - cx) ** 2 + (ay - cy) ** 2) ** 0.5)
        errors_px.append(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5)
        errors_k.append(((kx - cx) ** 2 + (ky - cy) ** 2) ** 0.5)
        ratios_x.append(x / cx)
        ratios_y.append(y / cy)
    total = len(rows)
    best = max(pixels, thousand, aspect)
    if pixels == best and pixels >= total * 0.6:
        verdict = "PIXELS: the AI's numbers are real picture pixels. Pointing is usable as it is."
    elif aspect == best and aspect >= total * 0.6:
        verdict = ("ASPECT FIX: the AI's up-and-down number is too small by height/width. Multiplying it by "
                   "width/height lands on the targets. Trado can apply that.")
    elif thousand == best and thousand >= total * 0.6:
        verdict = "THOUSAND SCALE: the AI uses a 0-1000 scale. Trado needs to convert its numbers (easy to add)."
    else:
        verdict = "UNRELIABLE: none of the three readings lands on the targets often enough."
    return {"pixels": pixels, "thousand": thousand, "aspect": aspect, "missing": missing, "total": total,
            "median_error_px": _median(errors_px), "median_error_k": _median(errors_k),
            "median_error_aspect": _median(errors_a),
            "median_ratio_x": _median(ratios_x), "median_ratio_y": _median(ratios_y), "verdict": verdict}


def final_verdict(result, failed, planned):
    """The verdict to show. If some questions failed (for example the daily limit), say so instead of judging."""
    if failed:
        return (f"INCOMPLETE: {failed} of {planned} questions failed (see the errors above), so only {result['total']} were "
                f"scored and this result can't be trusted yet. Run it again when the limit has reset.")
    return result["verdict"]


def hits_through_trado(rows, size, targets, correct_height):
    """How many answers land inside the right box when read by Trado's own pointing code (the one the app uses)."""
    geometry = Geometry(size[0], size[1], 0, 0, size[0], size[1])  # the fake page IS the whole "screen"
    hits = 0
    for name, raw in rows:
        if raw is None:
            continue
        target = parse_point_tag(f"[POINT:{raw[0]},{raw[1]}:{name}]", geometry, correct_height=correct_height)
        hits += bool(target) and inside(targets[name], target.x, target.y)
    return hits


def save_marked_picture(page, rows, path, targets, width, height):
    marked = page.resize((width, height)) if page.size != (width, height) else page.copy()
    draw = ImageDraw.Draw(marked)
    font = ImageFont.load_default(size=22)
    for rect in targets.values():
        draw.rectangle(rect, outline=(255, 200, 0), width=3)  # yellow = the true box
    for name, raw in rows:
        if raw is None:
            continue
        x, y = raw
        draw.ellipse([x - 9, y - 9, x + 9, y + 9], outline=(255, 0, 255), width=4)  # magenta = read as pixels
        kx, ky = x / 1000 * width, y / 1000 * height
        draw.ellipse([kx - 9, ky - 9, kx + 9, ky + 9], outline=(0, 160, 255), width=4)  # blue = read as 0-1000 scale
        draw.text((x + 12, y - 12), name.split()[0], fill=(255, 0, 255), font=font)
    marked.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure how accurately the AI points.")
    parser.add_argument("--delay", type=float, default=15.0, help="seconds between questions (free-plan token limit)")
    parser.add_argument("--max-side", type=int, default=MAX_SIDE, help=f"longest side of the picture sent (Trado uses {MAX_SIDE})")
    parser.add_argument("--aspect", default="", help="screen shape to test, like 16:9 (default: the 16:10 page)")
    args = parser.parse_args()

    settings = load_settings()
    try:
        llm = create_llm_provider(settings)
    except LlmError as err:
        print(f"Setup problem: {err}")
        return 1

    try:
        page = make_page(page_height_for(args.aspect) if args.aspect else HEIGHT)
    except ValueError as err:
        print(err)
        return 1
    jpeg, size = encode_jpeg_sized(page, max_side=args.max_side)
    targets = scaled_targets(size[0] / WIDTH)
    print(f"Asking {settings.llm_model} to point at {len(TARGETS)} things on a fake {size[0]}x{size[1]} page...")
    print(describe_cost(screenshot_questions=len(TARGETS)) + "\n")
    rows, failed = [], []
    for index, name in enumerate(TARGETS):
        if index:
            time.sleep(args.delay)
        question = f"Where is the {name} on my screen? Point to it."
        tag_filter, spoken = PointTagFilter(), []
        try:
            for piece in llm.stream_answer(question, jpeg, None, None, size):
                spoken.append(tag_filter.feed(piece))
        except LlmError as err:
            print(f"[ERROR] {name}: {err}")
            failed.append(name)
            if isinstance(err, LlmRateLimitError) and "daily" in str(err).lower():
                print("STOPPED: the free daily allowance is used up. Run this again tomorrow.")
                break
            continue
        match = _RAW.match(tag_filter.tag or "")
        raw = (int(match.group(1)), int(match.group(2))) if match else None
        rows.append((name, raw))
        cx, cy = centre(targets[name])
        got = f"AI said ({raw[0]}, {raw[1]})" if raw else "AI gave no position"
        print(f"{name:24} true centre ({cx:.0f}, {cy:.0f})   {got}")

    if not rows:
        print("\nNo answers came back, so there is nothing to score. Try again later.")
        return 2
    result = evaluate(rows, size[0], size[1], targets)  # only the questions that were really answered
    fix = resolve_height_fix(settings.llm_model, settings.point_fix)
    through_trado = hits_through_trado(rows, size, targets, fix)
    path = Path(tempfile.gettempdir()) / "trado_pointing_test.png"
    save_marked_picture(page, rows, path, targets, size[0], size[1])
    print("\n" + "=" * 70)
    print(f"Picture sent           : {size[0]}x{size[1]}")
    print(f"Read as real pixels    : {result['pixels']} of {result['total']} inside the right box (typical miss {result['median_error_px']:.0f} px)")
    print(f"With height fix        : {result['aspect']} of {result['total']} inside the right box (typical miss {result['median_error_aspect']:.0f} px)"
          "   [up-and-down number x width/height]")
    print(f"THROUGH TRADO'S CODE   : {through_trado} of {result['total']} inside the right box "
          f"(height correction {'ON' if fix else 'OFF'} for {settings.llm_model}) <- this is what the app will do")
    print(f"Read as 0-1000 scale   : {result['thousand']} of {result['total']} inside the right box (typical miss {result['median_error_k']:.0f} px)")
    print(f"No position given      : {result['missing']}")
    print(f"AI's numbers vs truth  : {result['median_ratio_x']:.2f} across, {result['median_ratio_y']:.2f} down (1.00 would be perfect; "
          f"about 0.64 would mean it works on a copy 64% as big)")
    print("\nVERDICT:", final_verdict(result, len(failed), len(TARGETS)))
    print(f"\nA marked-up picture was saved here (a fake page, nothing private):\n  {path}")
    print("Yellow boxes = true positions. Magenta circles = where the AI pointed, read as pixels. Blue circles = read as 0-1000 scale.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
