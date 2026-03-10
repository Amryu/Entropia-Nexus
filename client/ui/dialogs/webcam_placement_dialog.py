"""Webcam placement dialog — drag the webcam overlay to position it on the game frame.

Supports snapping to edges and to horizontal/vertical center lines.
Hold Alt to disable snapping.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget,
)
from PyQt6.QtCore import Qt, QTimer, QRect, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPixmap, QImage, QPen, QBrush

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ...core.config import save_config
from ...core.constants import EVENT_CONFIG_CHANGED
from ...core.logger import get_logger
from ...capture.constants import WEBCAM_OVERLAY_SCALE, WEBCAM_SNAP_THRESHOLD
from ..theme import ACCENT, TEXT_MUTED, BORDER

log = get_logger("WebcamPlacementDialog")


class _PlacementWidget(QWidget):
    """Widget that displays a game frame preview with a draggable webcam rectangle."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._webcam_pixmap: QPixmap | None = None
        # Normalized center position (0.0-1.0)
        self._pos_x: float = 0.88
        self._pos_y: float = 0.85
        self._dragging = False
        self._drag_offset: QPointF = QPointF(0, 0)
        self.setMinimumSize(640, 360)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_frame(self, frame_bgr: np.ndarray) -> None:
        """Update the preview with a new BGR game frame."""
        if cv2 is None:
            return
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self.update()

    def set_webcam_frame(self, frame_bgr: np.ndarray) -> None:
        """Update the webcam preview thumbnail."""
        if cv2 is None:
            return
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self._webcam_pixmap = QPixmap.fromImage(qimg)
        self.update()

    @property
    def position(self) -> tuple[float, float]:
        return self._pos_x, self._pos_y

    def set_position(self, x: float, y: float) -> None:
        self._pos_x = max(0.0, min(1.0, x))
        self._pos_y = max(0.0, min(1.0, y))
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

    def _webcam_display_rect(self) -> QRectF:
        """Compute the webcam overlay rect in widget coordinates."""
        dr = self._display_rect()
        # Webcam is WEBCAM_OVERLAY_SCALE of the frame width
        wc_w = dr.width() * WEBCAM_OVERLAY_SCALE
        # Maintain webcam aspect ratio (default 4:3 if no pixmap)
        if self._webcam_pixmap and self._webcam_pixmap.width() > 0:
            aspect = self._webcam_pixmap.height() / self._webcam_pixmap.width()
        else:
            aspect = 3.0 / 4.0
        wc_h = wc_w * aspect

        # Center position in widget coords
        cx = dr.x() + self._pos_x * dr.width()
        cy = dr.y() + self._pos_y * dr.height()

        return QRectF(cx - wc_w / 2, cy - wc_h / 2, wc_w, wc_h)

    def _snap_position(self, cx: float, cy: float) -> tuple[float, float]:
        """Snap the webcam center to edges or center lines.

        Works in normalized coordinates. Snaps when the webcam edges or center
        approach the frame edges or the frame center (bisection lines).
        """
        dr = self._display_rect()
        if dr.width() == 0 or dr.height() == 0:
            return cx, cy

        # Webcam half-size in normalized coords
        half_w = WEBCAM_OVERLAY_SCALE / 2
        if self._webcam_pixmap and self._webcam_pixmap.width() > 0:
            aspect = self._webcam_pixmap.height() / self._webcam_pixmap.width()
        else:
            aspect = 3.0 / 4.0
        half_h = (WEBCAM_OVERLAY_SCALE * aspect) / 2

        # Snap threshold in normalized coords
        snap_n = WEBCAM_SNAP_THRESHOLD / max(1, dr.width())

        # Small margin from edges (in normalized)
        margin_n = 10 / max(1, dr.width())

        # --- Horizontal snap lines ---
        # Left edge of webcam → left edge of frame (with margin)
        left_edge = cx - half_w
        if abs(left_edge - margin_n) < snap_n:
            cx = half_w + margin_n
        # Right edge of webcam → right edge of frame (with margin)
        right_edge = cx + half_w
        if abs(right_edge - (1.0 - margin_n)) < snap_n:
            cx = 1.0 - half_w - margin_n
        # Center of webcam → horizontal center of frame
        if abs(cx - 0.5) < snap_n:
            cx = 0.5

        # --- Vertical snap lines ---
        margin_v = 10 / max(1, dr.height())
        snap_v = WEBCAM_SNAP_THRESHOLD / max(1, dr.height())

        # Top edge of webcam → top edge of frame (with margin)
        top_edge = cy - half_h
        if abs(top_edge - margin_v) < snap_v:
            cy = half_h + margin_v
        # Bottom edge of webcam → bottom edge of frame (with margin)
        bottom_edge = cy + half_h
        if abs(bottom_edge - (1.0 - margin_v)) < snap_v:
            cy = 1.0 - half_h - margin_v
        # Center of webcam → vertical center of frame
        if abs(cy - 0.5) < snap_v:
            cy = 0.5

        return cx, cy

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            wc_rect = self._webcam_display_rect()
            if wc_rect.contains(event.position()):
                self._dragging = True
                self._drag_offset = event.position() - wc_rect.center()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._dragging:
            dr = self._display_rect()
            if dr.width() == 0 or dr.height() == 0:
                return
            # Compute new center in normalized coords
            new_center = event.position() - self._drag_offset
            nx = (new_center.x() - dr.x()) / dr.width()
            ny = (new_center.y() - dr.y()) / dr.height()
            nx = max(0.0, min(1.0, nx))
            ny = max(0.0, min(1.0, ny))

            # Snap unless Alt is held
            if not (event.modifiers() & Qt.KeyboardModifier.AltModifier):
                nx, ny = self._snap_position(nx, ny)

            self._pos_x = nx
            self._pos_y = ny
            self.update()
        else:
            # Hover cursor
            wc_rect = self._webcam_display_rect()
            if wc_rect.contains(event.position()):
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor("#111111"))

        # Game frame
        dr = self._display_rect()
        if self._pixmap:
            painter.drawPixmap(dr, self._pixmap)

        # Snap guide lines (subtle)
        pen = QPen(QColor(255, 255, 255, 40))
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        # Vertical center
        vcx = dr.x() + dr.width() // 2
        painter.drawLine(vcx, dr.y(), vcx, dr.y() + dr.height())
        # Horizontal center
        hcy = dr.y() + dr.height() // 2
        painter.drawLine(dr.x(), hcy, dr.x() + dr.width(), hcy)

        # Webcam overlay
        wc_rect = self._webcam_display_rect()
        if self._webcam_pixmap:
            painter.drawPixmap(wc_rect.toRect(), self._webcam_pixmap)
        else:
            # Placeholder
            painter.setBrush(QColor(60, 60, 60, 180))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(wc_rect.toRect())
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(wc_rect.toRect(), Qt.AlignmentFlag.AlignCenter, "Webcam")

        # Border around webcam
        border_pen = QPen(QColor(ACCENT))
        border_pen.setWidth(2)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(wc_rect.toRect())

        painter.end()


class WebcamPlacementDialog(QDialog):
    """Dialog for positioning the webcam overlay on the game capture."""

    def __init__(self, *, config, config_path, event_bus, parent=None):
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._event_bus = event_bus

        self.setWindowTitle("Webcam Overlay Placement")
        self.setMinimumSize(800, 520)
        self.resize(900, 560)

        layout = QVBoxLayout(self)

        # Instructions
        desc = QLabel(
            "Drag the webcam overlay to position it on the game frame. "
            "It snaps to edges and center lines. Hold Alt to disable snapping."
        )
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Preview widget
        self._preview = _PlacementWidget()
        self._preview.set_position(config.clip_webcam_position_x,
                                    config.clip_webcam_position_y)
        layout.addWidget(self._preview)

        # Buttons
        btn_row = QHBoxLayout()

        reset_btn = QPushButton("Reset to Bottom Right")
        reset_btn.clicked.connect(self._reset_position)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("accentButton")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        # Live preview refresh (~2fps)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(500)
        self._refresh_timer.timeout.connect(self._refresh_preview)
        self._refresh_timer.start()

        self._frame_distributor = None
        self._refresh_preview()

    def _get_frame_distributor(self):
        """Lazily find the frame distributor from the app context."""
        if self._frame_distributor is not None:
            return self._frame_distributor
        try:
            app = __import__("PyQt6").QtWidgets.QApplication.instance()
            for widget in app.topLevelWidgets():
                fd = getattr(widget, "_frame_distributor", None)
                if fd is not None:
                    self._frame_distributor = fd
                    return fd
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

    def _reset_position(self):
        from ...capture.constants import WEBCAM_DEFAULT_POS_X, WEBCAM_DEFAULT_POS_Y
        self._preview.set_position(WEBCAM_DEFAULT_POS_X, WEBCAM_DEFAULT_POS_Y)

    def _save(self):
        px, py = self._preview.position
        self._config.clip_webcam_position_x = px
        self._config.clip_webcam_position_y = py
        save_config(self._config, self._config_path)
        self._event_bus.publish(EVENT_CONFIG_CHANGED, self._config)
        self.accept()
