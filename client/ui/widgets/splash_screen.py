"""Splash screen — branded logo with login/offline options."""

import os

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, pyqtSignal, pyqtSlot,
)
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QMouseEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QGraphicsOpacityEffect,
    QApplication, QSpacerItem, QSizePolicy,
)

from ..icons import nexus_logo_icon
from ..theme import PRIMARY, TEXT_MUTED
from ...platform import backend as _platform


# Resolve logo path relative to this file
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "logo.png")

SPLASH_WIDTH = 400
SPLASH_HEIGHT = 500
LOGO_SIZE = 128
CORNER_RADIUS = 12


class SplashScreen(QWidget):
    """Branded splash with animated logo reveal and login/offline buttons."""

    login_clicked = pyqtSignal()
    offline_clicked = pyqtSignal()
    close_clicked = pyqtSignal()
    _login_error = pyqtSignal(str)  # internal: thread-safe error reporting

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(SPLASH_WIDTH, SPLASH_HEIGHT)
        self.setWindowIcon(nexus_logo_icon())

        self._login_error.connect(self.show_login_error)
        self._drag_pos = None

        # --- Build UI ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)

        # Top spacer (animated — starts large, shrinks to push logo up)
        self._top_spacer = QWidget()
        self._top_spacer.setFixedHeight(140)
        self._top_spacer.setStyleSheet("background: transparent;")
        layout.addWidget(self._top_spacer)

        # Logo
        self._logo = QLabel()
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo.setStyleSheet("background: transparent;")
        pixmap = QPixmap(_LOGO_PATH)
        if not pixmap.isNull():
            self._logo.setPixmap(
                pixmap.scaled(LOGO_SIZE, LOGO_SIZE,
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )
        self._logo.setFixedHeight(LOGO_SIZE)
        layout.addWidget(self._logo, 0, Qt.AlignmentFlag.AlignCenter)

        # Spacing between logo and title
        layout.addSpacing(16)

        # Title
        self._title = QLabel("Entropia Nexus")
        self._title.setObjectName("splashTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        # Spacing before buttons
        layout.addSpacing(32)

        # Buttons container (fades in)
        self._buttons = QWidget()
        self._buttons.setStyleSheet("background: transparent;")
        btn_layout = QVBoxLayout(self._buttons)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(12)

        self._login_btn = QPushButton("Log in with Nexus")
        self._login_btn.setObjectName("splashLoginBtn")
        self._login_btn.setFixedWidth(280)
        self._login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._login_btn.clicked.connect(self.login_clicked.emit)
        btn_layout.addWidget(self._login_btn, 0, Qt.AlignmentFlag.AlignCenter)

        self._offline_btn = QPushButton("Use offline  \u2192")
        self._offline_btn.setObjectName("splashOfflineBtn")
        self._offline_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._offline_btn.clicked.connect(self.offline_clicked.emit)
        btn_layout.addWidget(self._offline_btn, 0, Qt.AlignmentFlag.AlignCenter)

        # Status label (hidden by default)
        self._status = QLabel("")
        self._status.setObjectName("splashStatus")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setVisible(False)
        btn_layout.addWidget(self._status)

        layout.addWidget(self._buttons)

        # Bottom stretch
        layout.addStretch()

        # Opacity effect for fade-in
        self._btn_opacity = QGraphicsOpacityEffect(self._buttons)
        self._btn_opacity.setOpacity(0.0)
        self._buttons.setGraphicsEffect(self._btn_opacity)

        # Close button (absolute-positioned over everything)
        self._close_btn = QPushButton("\u00d7", self)  # × multiplication sign
        self._close_btn.setObjectName("splashCloseBtn")
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.close_clicked.emit)
        self._close_btn.move(SPLASH_WIDTH - 36, 8)
        self._close_btn.raise_()

    def show(self):
        """Center on screen, enable shadow, start animation."""
        # Center on primary screen
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - SPLASH_WIDTH) // 2
            y = geo.y() + (geo.height() - SPLASH_HEIGHT) // 2
            self.move(x, y)

        super().show()
        self._enable_shadow()

        # Start animation after a brief pause
        QTimer.singleShot(800, self._animate)

    def _animate(self):
        """Slide logo up and fade in buttons."""
        # Animate top spacer height: 140 → 40
        self._spacer_anim = QPropertyAnimation(self._top_spacer, b"maximumHeight")
        self._spacer_anim.setDuration(500)
        self._spacer_anim.setStartValue(140)
        self._spacer_anim.setEndValue(40)
        self._spacer_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._spacer_anim.start()

        # Also animate fixedHeight to match
        self._spacer_anim2 = QPropertyAnimation(self._top_spacer, b"minimumHeight")
        self._spacer_anim2.setDuration(500)
        self._spacer_anim2.setStartValue(140)
        self._spacer_anim2.setEndValue(40)
        self._spacer_anim2.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._spacer_anim2.start()

        # Fade in buttons after 200ms delay
        QTimer.singleShot(200, self._fade_in_buttons)

    def _fade_in_buttons(self):
        """Fade the button container from 0 to 1."""
        self._fade_anim = QPropertyAnimation(self._btn_opacity, b"opacity")
        self._fade_anim.setDuration(400)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()

    def show_login_progress(self):
        """Show waiting state while OAuth completes in browser."""
        self._login_btn.setEnabled(False)
        self._login_btn.setText("Waiting for browser...")
        self._status.setText("Complete login in your browser")
        self._status.setStyleSheet("")
        self._status.setVisible(True)

    @pyqtSlot(str)
    def show_login_error(self, message):
        """Show error and re-enable login button."""
        self._login_btn.setEnabled(True)
        self._login_btn.setText("Log in with Nexus")
        self._status.setText(message)
        self._status.setStyleSheet(f"color: #ff6b6b;")
        self._status.setVisible(True)

    # --- Window dragging (top area) ---

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 200:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        """Draw rounded-rect dark background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(
            0.0, 0.0, float(self.width()), float(self.height()),
            CORNER_RADIUS, CORNER_RADIUS,
        )
        painter.fillPath(path, QColor(PRIMARY))

    def _enable_shadow(self):
        """Add a drop shadow to the frameless window (DWM on Windows, compositor on Linux)."""
        _platform.enable_shadow(int(self.winId()))
