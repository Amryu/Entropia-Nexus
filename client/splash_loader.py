"""Loading splash — runs as a subprocess with its own event loop.

Displays a branded splash with a pulsing animation while the main
client process builds its UI.  Completely autonomous: since it has its
own QApplication in a separate process, it never freezes even when the
main process is blocked on heavy widget construction.

Protocol:  the parent writes ``close\n`` to stdin when initialization is
finished.  The splash fades out and the process exits.
"""

import os
import sys
import threading

# DPI awareness must be configured before any windows are created.
if sys.platform == "win32":
    import ctypes

    shcore = getattr(ctypes.windll, "shcore", None)
    user32 = ctypes.windll.user32
    try:
        ctx = getattr(user32, "SetProcessDpiAwarenessContext", None)
        if ctx is not None and bool(ctx(ctypes.c_void_p(-4))):
            pass  # Per-Monitor V2
        elif shcore is not None:
            shcore.SetProcessDpiAwareness(2)  # Per-Monitor V1
        else:
            user32.SetProcessDPIAware()
    except Exception:
        pass

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QGraphicsOpacityEffect,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSlot,
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QPainterPath, QColor, QMouseEvent,
)

_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
_LOGO_SIZE = 128
_CORNER_RADIUS = 12
_SPLASH_WIDTH = 400
_SPLASH_HEIGHT = 460
_PULSE_MS = 1200
_FADE_OUT_MS = 250

# Theme colours (duplicated to avoid importing the full client package)
_PRIMARY = "#222222"
_TEXT = "#ffffff"
_TEXT_MUTED = "#aaaaaa"


class _SplashWindow(QWidget):
    """Frameless branded splash with pulsing 'Loading…' label."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # no taskbar entry
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(_SPLASH_WIDTH, _SPLASH_HEIGHT)

        self._drag_pos = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)

        layout.addStretch(3)

        # Logo
        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("background: transparent;")
        pixmap = QPixmap(_LOGO_PATH)
        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaled(
                    _LOGO_SIZE, _LOGO_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        logo.setFixedHeight(_LOGO_SIZE)
        layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(16)

        # Title
        title = QLabel("Entropia Nexus")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"background: transparent; color: {_TEXT};"
            "font-size: 18px; font-weight: 600;"
        )
        layout.addWidget(title)

        layout.addSpacing(24)

        # Pulsing label
        self._loading = QLabel("Loading\u2026")
        self._loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading.setStyleSheet(
            f"background: transparent; color: {_TEXT_MUTED}; font-size: 13px;"
        )
        layout.addWidget(self._loading)

        self._pulse_fx = QGraphicsOpacityEffect(self._loading)
        self._pulse_fx.setOpacity(1.0)
        self._loading.setGraphicsEffect(self._pulse_fx)
        self._start_pulse()

        layout.addStretch(4)

    # --- pulse ---

    def _start_pulse(self):
        self._pulse = QPropertyAnimation(self._pulse_fx, b"opacity")
        self._pulse.setDuration(_PULSE_MS)
        self._pulse.setStartValue(1.0)
        self._pulse.setEndValue(0.3)
        self._pulse.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse.finished.connect(self._flip_pulse)
        self._pulse.start()

    def _flip_pulse(self):
        if not self.isVisible():
            return
        cur = self._pulse_fx.opacity()
        end = 1.0 if cur < 0.65 else 0.3
        self._pulse = QPropertyAnimation(self._pulse_fx, b"opacity")
        self._pulse.setDuration(_PULSE_MS)
        self._pulse.setStartValue(cur)
        self._pulse.setEndValue(end)
        self._pulse.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse.finished.connect(self._flip_pulse)
        self._pulse.start()

    # --- fade out & quit ---

    @pyqtSlot()
    def fade_out(self):
        self._pulse.stop()
        self._loading.setGraphicsEffect(None)

        self._fade_fx = QGraphicsOpacityEffect(self)
        self._fade_fx.setOpacity(1.0)
        self.setGraphicsEffect(self._fade_fx)

        self._fade = QPropertyAnimation(self._fade_fx, b"opacity")
        self._fade.setDuration(_FADE_OUT_MS)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(QApplication.instance().quit)
        self._fade.start()

    # --- rounded background ---

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            0.0, 0.0, float(self.width()), float(self.height()),
            _CORNER_RADIUS, _CORNER_RADIUS,
        )
        p.fillPath(path, QColor(_PRIMARY))

    # --- draggable ---

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev: QMouseEvent):
        if self._drag_pos is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()

    def mouseReleaseEvent(self, ev: QMouseEvent):
        self._drag_pos = None


def _find_target_screen(app):
    """Pick the screen matching --screen-center, or fall back to primary."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--screen-center", nargs=2, type=int, default=None)
    args, _ = parser.parse_known_args()

    screens = app.screens()
    if args.screen_center and screens:
        from PyQt6.QtCore import QPoint
        pt = QPoint(args.screen_center[0], args.screen_center[1])
        for s in screens:
            if s.availableGeometry().contains(pt):
                return s

    return app.primaryScreen()


def main():
    app = QApplication(sys.argv)

    splash = _SplashWindow()

    # Center on the same monitor the main window will use
    screen = _find_target_screen(app)
    if screen:
        geo = screen.availableGeometry()
        splash.move(
            geo.x() + (geo.width() - _SPLASH_WIDTH) // 2,
            geo.y() + (geo.height() - _SPLASH_HEIGHT) // 2,
        )

    # Enable drop shadow
    if sys.platform == "win32":
        try:
            from .platform import backend as _platform
            _platform.enable_shadow(int(splash.winId()))
        except Exception:
            pass

    splash.show()

    # Background thread reads stdin; "close\n" triggers fade-out.
    def _wait_for_close():
        try:
            for line in sys.stdin:
                if line.strip() == "close":
                    QTimer.singleShot(0, splash.fade_out)
                    return
        except Exception:
            pass
        # stdin closed unexpectedly — just quit
        QTimer.singleShot(0, app.quit)

    t = threading.Thread(target=_wait_for_close, daemon=True)
    t.start()

    app.exec()


if __name__ == "__main__":
    main()
