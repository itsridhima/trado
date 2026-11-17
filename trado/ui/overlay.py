"""The glowing cursor: a see-through window over each screen.

Prototype B. It follows your mouse (a little arrow just beside it), and on request flies to a point on the
screen, shows a short label, then flies back. Clicks pass straight through it, it never takes focus, and it asks
Windows to leave it out of screenshots (so Trado's own screenshot never contains the cursor).

Positions: Trado's pointing code gives REAL screen pixels (see trado/pointing.py). Qt works in scaled units on
high-DPI screens, so `physical_to_logical` converts between the two.
"""

import ctypes
import math
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QWidget

from trado.ui.panel import _no_focus

FOLLOW_OFFSET = QPointF(18, 20)  # the companion sits just beside the real mouse pointer
FLY_SECONDS = 0.9
HOLD_SECONDS = 2.6
CANCEL_DISTANCE = 70  # if your mouse moves this far (screen units) while pointing, the cursor comes back
GLOW = QColor(45, 212, 191)
WDA_EXCLUDEFROMCAPTURE = 0x00000011


# ---------- pure helpers (tested offline) ----------

def physical_to_logical(x: float, y: float, geo_left: float, geo_top: float, dpr: float) -> tuple[float, float]:
    """Real screen pixel -> Qt's scaled position, for a screen whose top-left is (geo_left, geo_top)."""
    return geo_left + (x - geo_left) / dpr, geo_top + (y - geo_top) / dpr


def logical_to_physical(x: float, y: float, geo_left: float, geo_top: float, dpr: float) -> tuple[float, float]:
    return geo_left + (x - geo_left) * dpr, geo_top + (y - geo_top) * dpr


def bezier(p0: QPointF, p1: QPointF, p2: QPointF, t: float) -> QPointF:
    """A gentle curve from p0 to p2 (p1 is the bend)."""
    u = 1 - t
    return QPointF(u * u * p0.x() + 2 * u * t * p1.x() + t * t * p2.x(), u * u * p0.y() + 2 * u * t * p1.y() + t * t * p2.y())


def bend_point(a: QPointF, b: QPointF) -> QPointF:
    """A point off to the side of the straight line a->b, so the flight arcs instead of going straight."""
    mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
    dx, dy = b.x() - a.x(), b.y() - a.y()
    length = math.hypot(dx, dy) or 1.0
    bend = min(120.0, length * 0.25)
    return QPointF(mid.x() + (-dy / length) * bend, mid.y() + (dx / length) * bend)


def ease(t: float) -> float:
    return t * t * (3 - 2 * t)  # slow start, slow finish


def clean_label(text: str, limit: int = 28) -> str:
    return " ".join(text.split())[:limit]


# ---------- windows ----------

def _hide_from_capture(widget: QWidget) -> bool:
    """Ask Windows to leave this window out of screenshots. Returns True if Windows accepted (Windows 10 2004+)."""
    if sys.platform != "win32":
        return False
    hwnd = wintypes.HWND(int(widget.winId()))
    return bool(ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))


@dataclass
class _State:
    mode: str = "follow"  # follow | fly | hold | back
    pos: QPointF = None  # where the arrow tip is, in Qt screen units
    label: str = ""
    start: QPointF = None
    target: QPointF = None
    bend: QPointF = None
    started_at: float = 0.0
    mouse_at_start: QPointF = None


class _OverlayWindow(QWidget):
    def __init__(self, screen, companion):
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
        super().__init__(None, flags)
        self.companion = companion
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self.hidden_from_capture = False

    def show_overlay(self):
        self.show()
        _no_focus(self)
        self.hidden_from_capture = _hide_from_capture(self)

    def paintEvent(self, event):
        s = self.companion.state
        if s.pos is None or not self.companion.visible:
            return
        local = QPointF(s.pos.x() - self.x(), s.pos.y() - self.y())
        if not QRectF(self.rect()).adjusted(-60, -60, 60, 60).contains(local):
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # soft glow
        glow = QRadialGradient(local, 22)
        glow.setColorAt(0.0, QColor(45, 212, 191, 150))
        glow.setColorAt(1.0, QColor(45, 212, 191, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(local, 22, 22)
        # arrow: the TIP is exactly at `local`
        p.save()
        p.translate(local)
        p.rotate(-30)
        arrow = QPolygonF([QPointF(0, 0), QPointF(-8, 17), QPointF(8, 17)])
        p.setBrush(GLOW)
        p.setPen(QColor(6, 32, 28, 160))
        p.drawPolygon(arrow)
        p.restore()
        # label bubble
        if s.label and s.mode in ("hold", "fly"):
            font = QFont("Segoe UI", 9)
            font.setBold(True)
            p.setFont(font)
            fm = QFontMetrics(font)
            w, h = fm.horizontalAdvance(s.label) + 20, fm.height() + 8
            box = QRectF(local.x() + 16, local.y() - h - 14, w, h)
            if box.right() > self.width():
                box.moveRight(local.x() - 16)
            if box.top() < 0:
                box.moveTop(local.y() + 24)
            path = QPainterPath()
            path.addRoundedRect(box, h / 2, h / 2)
            p.setPen(Qt.NoPen)
            p.setBrush(GLOW)
            p.drawPath(path)
            p.setPen(QColor(6, 32, 28))
            p.drawText(box, Qt.AlignCenter, s.label)


class CursorCompanion:
    """Owns the overlay windows and the follow / fly / hold / return behaviour."""

    def __init__(self):
        self.state = _State(pos=QPointF(QCursor.pos()) + FOLLOW_OFFSET)
        self.visible = True
        self.windows = [_OverlayWindow(s, self) for s in QGuiApplication.screens()]
        self._last_rect = QRect()
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)

    # -- public --
    def start(self) -> None:
        for w in self.windows:
            w.show_overlay()
        self._timer.start(16)

    def set_visible(self, visible: bool) -> None:
        self.visible = visible
        self._repaint_all()

    @property
    def hidden_from_capture(self) -> bool:
        return all(w.hidden_from_capture for w in self.windows)

    def fly_to_logical(self, x: float, y: float, label: str = "") -> None:
        """Fly to a point in Qt screen units, show the label, then come back."""
        s = self.state
        s.start, s.target = QPointF(s.pos), QPointF(x, y)
        s.bend = bend_point(s.start, s.target)
        s.label = clean_label(label)
        s.mode, s.started_at = "fly", time.monotonic()
        s.mouse_at_start = QPointF(QCursor.pos())

    def fly_to_physical(self, x: float, y: float, label: str = "") -> None:
        """Fly to a REAL screen pixel (what trado/pointing.py gives)."""
        screen = QGuiApplication.screenAt(QPointF(x, y).toPoint()) or QGuiApplication.primaryScreen()
        geo, dpr = screen.geometry(), screen.devicePixelRatio()
        lx, ly = physical_to_logical(x, y, geo.left(), geo.top(), dpr)
        self.fly_to_logical(lx, ly, label)

    def cancel(self) -> None:
        """Come back now (mouse moved, or the hotkey was pressed)."""
        s = self.state
        if s.mode in ("fly", "hold"):
            self._start_back()

    # -- internals --
    def _start_back(self) -> None:
        s = self.state
        s.start = QPointF(s.pos)
        s.target = QPointF(QCursor.pos()) + FOLLOW_OFFSET
        s.bend = bend_point(s.start, s.target)
        s.mode, s.started_at = "back", time.monotonic()

    def _tick(self) -> None:
        s = self.state
        now = time.monotonic()
        old = s.pos
        mouse = QPointF(QCursor.pos())
        if s.mode == "follow":
            goal = mouse + FOLLOW_OFFSET
            s.pos = QPointF(s.pos.x() + (goal.x() - s.pos.x()) * 0.35, s.pos.y() + (goal.y() - s.pos.y()) * 0.35)
        elif s.mode in ("fly", "back"):
            t = min(1.0, (now - s.started_at) / FLY_SECONDS)
            if s.mode == "back":  # the destination is wherever your mouse is now
                s.target = mouse + FOLLOW_OFFSET
            s.pos = bezier(s.start, s.bend, s.target, ease(t))
            if s.mode == "fly" and math.hypot(mouse.x() - s.mouse_at_start.x(), mouse.y() - s.mouse_at_start.y()) > CANCEL_DISTANCE:
                self._start_back()
            elif t >= 1.0:
                if s.mode == "fly":
                    s.mode, s.started_at = "hold", now
                else:
                    s.mode, s.label = "follow", ""
        elif s.mode == "hold":
            s.pos = QPointF(s.target)
            if math.hypot(mouse.x() - s.mouse_at_start.x(), mouse.y() - s.mouse_at_start.y()) > CANCEL_DISTANCE:
                self._start_back()
            elif now - s.started_at >= HOLD_SECONDS:
                self._start_back()
        if old is None or (old - s.pos).manhattanLength() > 0.01 or s.mode in ("hold", "fly"):
            self._repaint_all()

    def _repaint_all(self) -> None:
        for w in self.windows:
            w.update()


def run_with(app, setup) -> int:
    """Start a companion, call setup(companion) once, run until quit."""
    companion = CursorCompanion()
    companion.start()
    setup(companion)
    app._companion = companion  # keep it alive
    return app.exec()
