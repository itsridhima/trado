"""The top panel: a thin line at the top-centre of the screen that opens a small panel when clicked.

Prototype A: looks and behaviour only (nothing here talks to the AI yet).
It never takes keyboard focus, so the app you are using keeps working and the hold-to-talk hotkey is unaffected.
"""

import ctypes
import signal
import sys
from ctypes import wintypes

from PySide6.QtCore import QByteArray, QEasingCurve, QPoint, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QCursor, QFont, QGuiApplication, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout, QWidget

ACCENT = "#2dd4bf"
PANEL_WIDTH = 360
HANDLE_W, HANDLE_H = 84, 5
HANDLE_HOVER_W, HANDLE_HOVER_H = 110, 7

MIC_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/>'
    '<path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3"/></svg>'
)
GEAR_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.7" '
    'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/>'
    '<path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/></svg>'
)


def handle_rect(screen: QRect, hover: bool = False) -> QRect:
    """The closed line: centred at the very top edge of the screen."""
    w, h = (HANDLE_HOVER_W, HANDLE_HOVER_H) if hover else (HANDLE_W, HANDLE_H)
    return QRect(screen.x() + (screen.width() - w) // 2, screen.y(), w, h)


def panel_rect(screen: QRect, height: int, width: int = PANEL_WIDTH) -> QRect:
    """The open panel: centred, attached to the top edge."""
    return QRect(screen.x() + (screen.width() - width) // 2, screen.y(), width, height)


def svg_pixmap(svg: str, colour: str, size: int, ratio: float) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg.format(c=colour).encode()))
    pm = QPixmap(int(size * ratio), int(size * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    renderer.render(p, QRectF(0, 0, size, size))
    p.end()
    return pm


def _no_focus(widget: QWidget) -> None:
    """Mark the window as 'never activate' and 'not in Alt-Tab / taskbar' so it can't steal focus."""
    if sys.platform != "win32":
        return
    GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = -20, 0x08000000, 0x00000080
    user32 = ctypes.windll.user32
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    hwnd = wintypes.HWND(int(widget.winId()))
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)


def _left_button_down() -> bool:
    return sys.platform == "win32" and bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)


_FLAGS = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus


class Handle(QWidget):
    """The thin black line. Click it to open the panel; right-click it for Quit."""

    def __init__(self, on_click, on_quit):
        super().__init__(None, _FLAGS)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self._hover = False
        self._on_click, self._on_quit = on_click, on_quit
        self.place()

    def place(self) -> None:
        screen = QGuiApplication.primaryScreen().geometry()
        r = handle_rect(screen, hover=True)  # window is as wide as the hover size so the line is easy to hit
        self.setGeometry(r.x(), r.y(), r.width(), r.height() + 3)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = (HANDLE_HOVER_W, HANDLE_HOVER_H) if self._hover else (HANDLE_W, HANDLE_H)
        x = (self.width() - w) / 2
        if self._hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(45, 212, 191, 70))
            p.drawRoundedRect(QRectF(x - 2, -8, w + 4, h + 10), 8, 8)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(QColor(0, 0, 0, 240))
        p.drawRoundedRect(QRectF(x, -8, w, h + 8), 6, 6)  # top corners sit above the screen edge: only the bottom edge shows

    def enterEvent(self, _e):
        self._hover = True
        self.update()

    def leaveEvent(self, _e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._on_click()
        elif e.button() == Qt.RightButton:
            menu = QMenu(self)
            quit_action = QAction("Quit Trado panel test", menu)
            quit_action.triggered.connect(self._on_quit)
            menu.addAction(quit_action)
            menu.exec(e.globalPosition().toPoint())


class Panel(QWidget):
    """The small open panel (360 px wide). One fixed layout: mic, usage pill, settings gear, greeting, talk pill."""

    def __init__(self, on_settings):
        super().__init__(None, _FLAGS)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedWidth(PANEL_WIDTH)
        ratio = QGuiApplication.primaryScreen().devicePixelRatio()

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 14)
        root.setSpacing(8)

        top = QHBoxLayout()
        mic = QLabel()
        mic.setPixmap(svg_pixmap(MIC_SVG, "#e8ecef", 17, ratio))
        mic.setFixedSize(30, 30)
        mic.setAlignment(Qt.AlignCenter)
        mic.setStyleSheet("background: rgba(255,255,255,0.12); border-radius: 15px;")
        top.addWidget(mic)
        top.addStretch(1)
        usage = QLabel("38% used today")
        usage.setStyleSheet(
            "color:#06201c; font-weight:600; font-size:11px; padding:5px 11px; border-radius:11px;"
            f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #8ff0e1, stop:1 {ACCENT});"
        )
        top.addWidget(usage)
        gear = QPushButton()
        gear.setIcon(QIcon(svg_pixmap(GEAR_SVG, "#c9d0d6", 17, ratio)))
        gear.setIconSize(QSize(17, 17))
        gear.setFixedSize(30, 30)
        gear.setCursor(Qt.PointingHandCursor)
        gear.setStyleSheet(
            "QPushButton{background:transparent;border:0;border-radius:15px;}"
            "QPushButton:hover{background:rgba(255,255,255,0.10);}"
        )
        gear.clicked.connect(on_settings)
        top.addWidget(gear)
        root.addLayout(top)

        title = QLabel("Ask me about trading")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:#f2f4f6; font-size:17px; font-weight:600; padding-top:10px;")
        sub = QLabel("Hold <b>Ctrl + Left Alt</b> and speak.")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color:#9aa3ad; font-size:12px; padding-bottom:8px;")
        root.addWidget(title)
        root.addWidget(sub)

        pill = QPushButton("  Hold Ctrl + Left Alt to talk")
        pill.setIcon(QIcon(svg_pixmap(MIC_SVG, "#06201c", 17, ratio)))
        pill.setIconSize(QSize(17, 17))
        pill.setFixedHeight(40)
        pill.setCursor(Qt.PointingHandCursor)
        pill.setStyleSheet(
            "QPushButton{color:#06201c;font-weight:600;font-size:13px;border:0;border-radius:20px;"
            f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #8ff0e1, stop:1 {ACCENT});}}"
        )
        root.addWidget(pill)
        self.adjustSize()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        r = QRectF(0.5, -30, self.width() - 1, self.height() + 29.5)  # top corners hidden above the screen edge
        path.addRoundedRect(r, 22, 22)
        p.setPen(QPen(QColor(255, 255, 255, 28), 1))
        p.setBrush(QColor(20, 22, 26, 238))
        p.drawPath(path)


class PanelController:
    """Connects the line and the panel: click the line to open, click anywhere else to close."""

    def __init__(self, app: QApplication):
        self.app = app
        self.panel = Panel(on_settings=lambda: print("Settings window: not built yet (next step)."))
        self.handle = Handle(self.open, app.quit)
        self._was_down = False
        self._fade = QPropertyAnimation(self.panel, b"windowOpacity")
        self._slide = QPropertyAnimation(self.panel, b"pos")
        for a in (self._fade, self._slide):
            a.setDuration(180)
            a.setEasingCurve(QEasingCurve.OutCubic)
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll)
        self._timer.start(30)
        self.handle.show()
        _no_focus(self.handle)

    def open(self) -> None:
        screen = QGuiApplication.primaryScreen().geometry()
        end = panel_rect(screen, self.panel.height()).topLeft()
        start = end - QPoint(0, 14)
        self.panel.move(start)
        self.panel.setWindowOpacity(0.0)
        self.panel.show()
        _no_focus(self.panel)
        self.handle.hide()
        self._fade.stop()
        self._slide.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._slide.setStartValue(start)
        self._slide.setEndValue(end)
        self._fade.start()
        self._slide.start()

    def close(self) -> None:
        self.panel.hide()
        self.handle.place()
        self.handle.show()

    def _poll(self) -> None:
        """Close the panel when you click outside it. (The panel never takes focus, so we watch the mouse button.)"""
        down = _left_button_down()
        if down and not self._was_down and self.panel.isVisible():
            if not self.panel.geometry().contains(QCursor.pos()):
                self.close()
        self._was_down = down


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Segoe UI", 9))
    controller = PanelController(app)  # noqa: F841  (kept alive for the event loop)
    signal.signal(signal.SIGINT, lambda *_: app.quit())  # Ctrl+C in the terminal quits quietly (the 30 ms timer lets Python see it)
    return app.exec()
