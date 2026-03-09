"""Blur region editor — draw rectangles on a live game preview to define privacy regions."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget,
)
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint
from PyQt6.QtGui import QPainter, QColor, QPixmap, QImage

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ...core.config import save_config
from ...core.constants import EVENT_CONFIG_CHANGED
from ...core.logger import get_logger
from ..theme import ACCENT, TEXT_MUTED, BORDER

log = get_logger("BlurRegionDialog")


class _PreviewWidget(QWidget):
    """Widget that displays a live game frame and allows drawing blur rectangles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._regions: list[dict] = []  # [{x, y, w, h}] normalized 0.0-1.0
        self._drawing = False
        self._draw_start: QPoint | None = None
        self._draw_current: QPoint | None = None
        self.setMinimumSize(640, 360)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_frame(self, frame_bgr: np.ndarray) -> None:
        """Update the preview with a new BGR frame."""
        if cv2 is None:
            return
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self.update()

    @property
    def regions(self) -> list[dict]:
        return self._regions

    @regions.setter
    def regions(self, value: list[dict]):
        self._regions = list(value)
        self.update()

    def _display_rect(self) -> QRect:
        """Compute the scaled display rect maintaining aspect ratio."""
        if not self._pixmap:
            return QRect(0, 0, self.width(), self.height())
        pw, ph = self._pixmap.width(), self._pixmap.height()
        ww, wh = self.width(), self.height()
        scale = min(ww / pw, wh / ph)
        dw, dh = int(pw * scale), int(ph * scale)
        dx = (ww - dw) // 2
        dy = (wh - dh) // 2
        return QRect(dx, dy, dw, dh)

    def _widget_to_normalized(self, pos: QPoint) -> tuple[float, float]:
        """Convert widget coordinates to normalized (0-1) frame coordinates."""
        dr = self._display_rect()
        x = (pos.x() - dr.x()) / max(1, dr.width())
        y = (pos.y() - dr.y()) / max(1, dr.height())
        return max(0.0, min(1.0, x)), max(0.0, min(1.0, y))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._draw_start = event.pos()
            self._draw_current = event.pos()
        elif event.button() == Qt.MouseButton.RightButton:
            # Delete region under cursor
            nx, ny = self._widget_to_normalized(event.pos())
            for i, r in enumerate(self._regions):
                if (r["x"] <= nx <= r["x"] + r["w"]
                        and r["y"] <= ny <= r["y"] + r["h"]):
                    self._regions.pop(i)
                    self.update()
                    break

    def mouseMoveEvent(self, event):
        if self._drawing:
            self._draw_current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            if self._draw_start and self._draw_current:
                x1, y1 = self._widget_to_normalized(self._draw_start)
                x2, y2 = self._widget_to_normalized(self._draw_current)
                rx = min(x1, x2)
                ry = min(y1, y2)
                rw = abs(x2 - x1)
                rh = abs(y2 - y1)
                if rw > 0.01 and rh > 0.01:  # Minimum size threshold
                    self._regions.append({"x": rx, "y": ry, "w": rw, "h": rh})
            self._draw_start = None
            self._draw_current = None
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor("#111111"))

        # Frame
        dr = self._display_rect()
        if self._pixmap:
            painter.drawPixmap(dr, self._pixmap)

        # Existing blur regions (semi-transparent red)
        painter.setBrush(QColor(255, 80, 80, 80))
        painter.setPen(QColor(255, 80, 80, 200))
        for r in self._regions:
            rx = dr.x() + int(r["x"] * dr.width())
            ry = dr.y() + int(r["y"] * dr.height())
            rw = int(r["w"] * dr.width())
            rh = int(r["h"] * dr.height())
            painter.drawRect(rx, ry, rw, rh)

        # Current drawing rect (blue outline)
        if self._drawing and self._draw_start and self._draw_current:
            painter.setBrush(QColor(96, 176, 255, 40))
            painter.setPen(QColor(ACCENT))
            rect = QRect(self._draw_start, self._draw_current).normalized()
            painter.drawRect(rect)

        painter.end()


class BlurRegionDialog(QDialog):
    """Dialog for configuring blur/privacy regions on the game capture."""

    def __init__(self, *, config, config_path, event_bus, parent=None):
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._event_bus = event_bus

        self.setWindowTitle("Configure Blur Regions")
        self.setMinimumSize(800, 520)
        self.resize(900, 560)

        layout = QVBoxLayout(self)

        # Instructions
        desc = QLabel(
            "Draw rectangles on the preview to define regions that will be blurred "
            "in screenshots and video clips. Right-click a region to delete it."
        )
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Preview widget
        self._preview = _PreviewWidget()
        self._preview.regions = list(config.capture_blur_regions)
        layout.addWidget(self._preview)

        # Buttons
        btn_row = QHBoxLayout()

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_regions)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("accentButton")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        # Live preview refresh timer (~2fps)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(500)
        self._refresh_timer.timeout.connect(self._refresh_preview)
        self._refresh_timer.start()

        # Try to get a frame immediately
        self._frame_distributor = None
        self._refresh_preview()

    def _get_frame_distributor(self):
        """Lazily find the frame distributor from the app context."""
        if self._frame_distributor is not None:
            return self._frame_distributor
        # Walk up to find it from the main window (best effort)
        try:
            app = __import__("PyQt6").QtWidgets.QApplication.instance()
            for widget in app.topLevelWidgets():
                if hasattr(widget, "_frame_distributor"):
                    self._frame_distributor = widget._frame_distributor
                    return self._frame_distributor
        except Exception:
            pass
        return None

    def _refresh_preview(self) -> None:
        """Fetch the latest game frame and update the preview."""
        fd = self._get_frame_distributor()
        if fd is None:
            return
        frame = fd.get_latest_frame()
        if frame is not None:
            self._preview.set_frame(frame)

    def _clear_regions(self):
        self._preview.regions = []

    def _save(self):
        self._config.capture_blur_regions = self._preview.regions
        save_config(self._config, self._config_path)
        self._event_bus.publish(EVENT_CONFIG_CHANGED, self._config)
        self.accept()
