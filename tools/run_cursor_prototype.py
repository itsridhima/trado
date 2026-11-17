"""Try the glowing cursor (looks and behaviour only, no AI).

    python -m tools.run_cursor_prototype              the cursor follows your mouse; Ctrl+C quits
    python -m tools.run_cursor_prototype --demo       also flies to your mouse position, then 4 screen spots
    python -m tools.run_cursor_prototype --selftest   checks the cursor is left out of screenshots, then exits
"""

import argparse
import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication

from trado.ui.overlay import CursorCompanion, logical_to_physical


def _demo(companion: CursorCompanion) -> None:
    screen = QGuiApplication.primaryScreen()
    geo, dpr = screen.geometry(), screen.devicePixelRatio()

    def spot(fx, fy, label):
        # a REAL screen pixel, like trado/pointing.py would give
        px, py = logical_to_physical(geo.left() + geo.width() * fx, geo.top() + geo.height() * fy, geo.left(), geo.top(), dpr)
        companion.fly_to_physical(px, py, label)

    steps = [
        (1500, lambda: (lambda p: companion.fly_to_logical(p.x(), p.y(), "Your mouse is here"))(QCursor.pos())),
        (7000, lambda: spot(0.10, 0.15, "Top-left area")),
        (12000, lambda: spot(0.90, 0.15, "Top-right area")),
        (17000, lambda: spot(0.10, 0.85, "Bottom-left area")),
        (22000, lambda: spot(0.90, 0.85, "Bottom-right area")),
        (27000, lambda: spot(0.50, 0.50, "Centre of screen")),
        (33000, QGuiApplication.quit),
    ]
    for delay, action in steps:
        QTimer.singleShot(delay, action)
    print(f"Demo running for about 33 seconds. Screen scale: {dpr * 100:.0f}%. Keep your mouse still for the first flight;")
    print("moving it more than a few centimetres while the cursor is pointing makes the cursor come back (that is on purpose).")


def _selftest(app, companion: CursorCompanion) -> None:
    """Take a picture of the screen with and without the cursor drawn; if they match, it is hidden from screenshots."""
    import mss

    screen = QGuiApplication.primaryScreen()
    geo, dpr = screen.geometry(), screen.devicePixelRatio()
    cx, cy = geo.left() + geo.width() // 2, geo.top() + geo.height() // 2
    companion.fly_to_logical(cx, cy, "Self-test")
    result = {}

    def grab():
        px, py = logical_to_physical(cx, cy, geo.left(), geo.top(), dpr)
        box = {"left": int(px) - 60, "top": int(py) - 60, "width": 120, "height": 120}
        with getattr(mss, "MSS", None)() if hasattr(mss, "MSS") else mss.mss() as sct:
            return bytes(sct.grab(box).rgb)

    def with_cursor():
        result["with"] = grab()
        companion.set_visible(False)

    def without_cursor():
        QTimer.singleShot(250, lambda: (result.__setitem__("without", grab()), control()))

    def control():
        # Control check: with the 'hide' switched OFF the cursor must show up in a screenshot, otherwise this test proves nothing.
        import ctypes
        from ctypes import wintypes

        for w in companion.windows:
            ctypes.windll.user32.SetWindowDisplayAffinity(wintypes.HWND(int(w.winId())), 0)
        companion.set_visible(True)
        QTimer.singleShot(400, lambda: (result.__setitem__("control", grab()), finish()))

    def finish():
        accepted = companion.hidden_from_capture
        same = result["with"] == result["without"]
        test_is_meaningful = result["control"] != result["without"]
        print(f"Control (hide switched off): cursor visible in a screenshot: {'YES' if test_is_meaningful else 'NO (so this test cannot tell)'}")
        print(f"Windows accepted 'hide from screenshots': {'YES' if accepted else 'NO'}")
        print(f"Screenshot with the cursor shown equals the one without it: {'YES (cursor is hidden from screenshots)' if same else 'NO (cursor appears in screenshots)'}")
        ok = accepted and same and test_is_meaningful
        print("RESULT:", "PASS" if ok else "FAIL")
        app.exit(0 if ok else 1)

    QTimer.singleShot(2300, lambda: (with_cursor(), without_cursor()))  # flight is 0.9 s, so it has arrived by then


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication(sys.argv)
    companion = CursorCompanion()
    companion.start()
    app._companion = companion
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    keepalive = QTimer()  # lets Python see Ctrl+C
    keepalive.start(100)
    keepalive.timeout.connect(lambda: None)
    if args.selftest:
        _selftest(app, companion)
    elif args.demo:
        _demo(companion)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
