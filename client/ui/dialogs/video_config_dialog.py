"""Unified video capture configuration dialog.

Combines a live preview canvas with webcam placement, blur region drawing,
and all video recording settings in one place. The canvas adjusts to the
selected resolution or source game window size.
"""

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget,
    QComboBox, QCheckBox, QFileDialog, QGridLayout, QSlider,
    QColorDialog, QFrame, QMessageBox, QTabWidget,
)
from PyQt6.QtCore import Qt, QTimer, QRect, QRectF, QPoint, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPixmap, QImage, QPen

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ...core.config import save_config
from ...core.constants import EVENT_CONFIG_CHANGED
from ...core.logger import get_logger
from ...ocr.capturer import get_monitor_refresh_rate, resolve_clip_backend
from ...capture.constants import (
    RESOLUTION_PRESETS, RESOLUTION_GROUPS,
    WEBCAM_OVERLAY_SCALE, WEBCAM_SNAP_THRESHOLD,
    WEBCAM_MIN_SCALE, WEBCAM_MAX_SCALE, WEBCAM_MIN_CROP_PX,
    SCALING_ALGORITHMS, get_interpolation,
)
from ..theme import ACCENT, TEXT_MUTED, BORDER

log = get_logger("VideoConfigDialog")

# Default aspect ratio when no game window or resolution is configured
_DEFAULT_ASPECT = 16 / 9


class _PreviewWidget(QWidget):
    """Combined preview: game frame + draggable/resizable webcam + drawable blur regions.

    Interaction:
    - Left-click on webcam rect → drag to reposition
    - Drag webcam edges/corners → resize (aspect ratio preserved)
    - Shift+left-click on webcam → draw crop region within webcam
    - Left-click elsewhere → draw a new blur region
    - Right-click on a blur region → delete it
    - Right-click on webcam → reset crop
    - Hold Alt while dragging webcam to disable snapping
    """

    # Resize handle size in pixels
    _HANDLE_SIZE = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        # Skip redundant background erase — we paint the entire widget
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        self._aspect: float = _DEFAULT_ASPECT
        self._pixmap: QPixmap | None = None
        self._bg_pixmap: QPixmap | None = None

        # Blur regions: [{x, y, w, h}] normalized 0.0-1.0
        self._regions: list[dict] = []

        # Webcam overlay
        self._webcam_enabled: bool = False
        self._webcam_pixmap: QPixmap | None = None
        self._webcam_x: float = 0.88
        self._webcam_y: float = 0.85
        self._webcam_scale: float = WEBCAM_OVERLAY_SCALE

        # Webcam crop: {x, y, w, h} normalized 0.0-1.0 within webcam frame
        self._webcam_crop: dict = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}

        # Interaction state
        self._mode: str = "idle"  # idle | drawing | dragging_webcam | cropping_webcam | resizing_webcam
        self._draw_start: QPoint | None = None
        self._draw_current: QPoint | None = None
        self._drag_offset: QPointF = QPointF(0, 0)
        self._resize_handle: str = ""  # tl|tr|bl|br|t|b|l|r
        self._resize_anchor: QPointF = QPointF(0, 0)  # fixed point during resize

        self.setMinimumSize(480, 270)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # --- Public API ---

    def set_aspect_ratio(self, ratio: float) -> None:
        self._aspect = max(0.5, min(4.0, ratio))
        self.update()

    def set_frame(self, frame_bgr: np.ndarray) -> None:
        h, w = frame_bgr.shape[:2]
        # Downscale to display size — avoids uploading millions of excess pixels
        dr = self._display_rect()
        if cv2 is not None and dr.width() > 0 and w > dr.width() * 1.2:
            scale = dr.width() / w
            frame_bgr = cv2.resize(
                frame_bgr, (dr.width(), int(h * scale)),
                interpolation=cv2.INTER_CUBIC,
            )
            h, w = frame_bgr.shape[:2]
        # BGR888: direct from numpy — no cvtColor needed
        qimg = QImage(
            frame_bgr.data, w, h, frame_bgr.strides[0],
            QImage.Format.Format_BGR888,
        )
        self._pixmap = QPixmap.fromImage(qimg)
        self.update()

    def set_background(self, pixmap: QPixmap | None) -> None:
        self._bg_pixmap = pixmap
        self.update()

    @property
    def regions(self) -> list[dict]:
        return self._regions

    @regions.setter
    def regions(self, value: list[dict]):
        self._regions = list(value)
        self.update()

    @property
    def webcam_position(self) -> tuple[float, float]:
        return self._webcam_x, self._webcam_y

    def set_webcam_position(self, x: float, y: float) -> None:
        self._webcam_x = max(0.0, min(1.0, x))
        self._webcam_y = max(0.0, min(1.0, y))
        self.update()

    @property
    def webcam_scale(self) -> float:
        return self._webcam_scale

    def set_webcam_scale(self, scale: float) -> None:
        self._webcam_scale = max(WEBCAM_MIN_SCALE, min(WEBCAM_MAX_SCALE, scale))
        self.update()

    @property
    def webcam_crop(self) -> dict:
        return self._webcam_crop

    def set_webcam_crop(self, crop: dict) -> None:
        self._webcam_crop = dict(crop)
        self.update()

    def set_webcam_enabled(self, enabled: bool) -> None:
        self._webcam_enabled = enabled
        self.update()

    def set_webcam_frame(self, frame: np.ndarray) -> None:
        """Accept a BGR or BGRA webcam frame for preview.

        If 4 channels are provided the alpha channel is used for
        compositing (chroma key transparency).

        BGR frames are downscaled to display size here.  BGRA frames
        (from chroma key) should be pre-sized by the caller — resizing
        premultiplied alpha with interpolation causes fringe artifacts.
        """
        h, w = frame.shape[:2]
        channels = frame.shape[2] if frame.ndim == 3 else 1
        # Only downscale BGR; BGRA should already be sized by caller
        if channels == 3:
            wc = self._webcam_display_rect()
            target_w = max(1, int(wc.width()))
            if cv2 is not None and target_w > 0 and w > target_w * 1.5:
                scale = target_w / w
                frame = cv2.resize(
                    frame, (target_w, int(h * scale)),
                    interpolation=cv2.INTER_CUBIC,
                )
                h, w = frame.shape[:2]
        if channels == 4:
            # BGRA premultiplied — Qt ARGB32_Premultiplied = B,G,R,A on little-endian
            qimg = QImage(
                frame.data, w, h, frame.strides[0],
                QImage.Format.Format_ARGB32_Premultiplied,
            )
        else:
            qimg = QImage(
                frame.data, w, h, frame.strides[0],
                QImage.Format.Format_BGR888,
            )
        self._webcam_pixmap = QPixmap.fromImage(qimg)
        self.update()

    # --- Geometry helpers ---

    def _display_rect(self) -> QRect:
        """Compute the canvas rect maintaining the target aspect ratio."""
        ww, wh = self.width(), self.height()
        scale = min(ww / self._aspect, wh)
        dw = int(scale * self._aspect)
        dh = int(scale)
        dx = (ww - dw) // 2
        dy = (wh - dh) // 2
        return QRect(dx, dy, dw, dh)

    def _widget_to_normalized(self, pos: QPoint) -> tuple[float, float]:
        dr = self._display_rect()
        x = (pos.x() - dr.x()) / max(1, dr.width())
        y = (pos.y() - dr.y()) / max(1, dr.height())
        return max(0.0, min(1.0, x)), max(0.0, min(1.0, y))

    def _webcam_aspect(self) -> float:
        """Full (uncropped) webcam aspect ratio (h/w)."""
        if self._webcam_pixmap and self._webcam_pixmap.width() > 0:
            return self._webcam_pixmap.height() / self._webcam_pixmap.width()
        return 3.0 / 4.0

    def _webcam_display_rect(self) -> QRectF:
        """Visible webcam rect (after crop).  Scale controls visible width."""
        dr = self._display_rect()
        vis_w = dr.width() * self._webcam_scale
        full_aspect = self._webcam_aspect()
        crop = self._webcam_crop
        # Cropped aspect: (crop_h * full_h) / (crop_w * full_w) = crop_h * aspect / crop_w
        crop_aspect = (crop["h"] * full_aspect) / max(0.001, crop["w"])
        vis_h = vis_w * crop_aspect
        cx = dr.x() + self._webcam_x * dr.width()
        cy = dr.y() + self._webcam_y * dr.height()
        return QRectF(cx - vis_w / 2, cy - vis_h / 2, vis_w, vis_h)

    def _webcam_full_rect(self) -> QRectF:
        """Full uncropped webcam rect, centered on the same position.

        Used during crop interaction so the user sees the entire webcam feed.
        """
        dr = self._display_rect()
        crop = self._webcam_crop
        # The visible width = scale * dr.width(); full width = visible / crop_w
        full_w = dr.width() * self._webcam_scale / max(0.001, crop["w"])
        full_h = full_w * self._webcam_aspect()
        cx = dr.x() + self._webcam_x * dr.width()
        cy = dr.y() + self._webcam_y * dr.height()
        return QRectF(cx - full_w / 2, cy - full_h / 2, full_w, full_h)

    def _snap_position(self, cx: float, cy: float) -> tuple[float, float]:
        """Snap webcam center so visible edges align with capture area boundaries."""
        dr = self._display_rect()
        if dr.width() == 0 or dr.height() == 0:
            return cx, cy

        half_w = self._webcam_scale / 2
        full_aspect = self._webcam_aspect()
        crop = self._webcam_crop
        crop_aspect = (crop["h"] * full_aspect) / max(0.001, crop["w"])
        half_h = (self._webcam_scale * crop_aspect) / 2

        snap_x = WEBCAM_SNAP_THRESHOLD / max(1, dr.width())
        snap_y = WEBCAM_SNAP_THRESHOLD / max(1, dr.height())

        # Horizontal: snap edges flush to capture area boundaries
        if abs(cx - half_w) < snap_x:
            cx = half_w  # left edge touches left boundary
        elif abs((cx + half_w) - 1.0) < snap_x:
            cx = 1.0 - half_w  # right edge touches right boundary
        if abs(cx - 0.5) < snap_x:
            cx = 0.5

        # Vertical: snap edges flush to capture area boundaries
        if abs(cy - half_h) < snap_y:
            cy = half_h  # top edge touches top boundary
        elif abs((cy + half_h) - 1.0) < snap_y:
            cy = 1.0 - half_h  # bottom edge touches bottom boundary
        if abs(cy - 0.5) < snap_y:
            cy = 0.5

        return cx, cy

    # --- Resize handle detection ---

    def _webcam_handle_at(self, pos: QPoint) -> str:
        """Return which resize handle the position is on, or empty string."""
        wc = self._webcam_display_rect()
        hs = self._HANDLE_SIZE
        r = wc.toRect()

        # Corners (check first — they overlap edges)
        corners = {
            "tl": QRect(r.left() - hs // 2, r.top() - hs // 2, hs, hs),
            "tr": QRect(r.right() - hs // 2, r.top() - hs // 2, hs, hs),
            "bl": QRect(r.left() - hs // 2, r.bottom() - hs // 2, hs, hs),
            "br": QRect(r.right() - hs // 2, r.bottom() - hs // 2, hs, hs),
        }
        for name, rect in corners.items():
            if rect.contains(pos):
                return name

        # Edges
        edges = {
            "t": QRect(r.left() + hs, r.top() - hs // 2, r.width() - 2 * hs, hs),
            "b": QRect(r.left() + hs, r.bottom() - hs // 2, r.width() - 2 * hs, hs),
            "l": QRect(r.left() - hs // 2, r.top() + hs, hs, r.height() - 2 * hs),
            "r": QRect(r.right() - hs // 2, r.top() + hs, hs, r.height() - 2 * hs),
        }
        for name, rect in edges.items():
            if rect.contains(pos):
                return name
        return ""

    def _handle_cursor(self, handle: str) -> Qt.CursorShape:
        if handle in ("tl", "br"):
            return Qt.CursorShape.SizeFDiagCursor
        if handle in ("tr", "bl"):
            return Qt.CursorShape.SizeBDiagCursor
        if handle in ("t", "b"):
            return Qt.CursorShape.SizeVerCursor
        if handle in ("l", "r"):
            return Qt.CursorShape.SizeHorCursor
        return Qt.CursorShape.CrossCursor

    def _apply_resize(self, mouse_pos: QPointF) -> None:
        """Compute new webcam scale from a resize drag, preserving aspect ratio."""
        dr = self._display_rect()
        if dr.width() == 0:
            return

        anchor = self._resize_anchor
        handle = self._resize_handle

        # Compute the desired width/height from mouse distance to anchor
        if handle in ("l", "r"):
            new_w = abs(mouse_pos.x() - anchor.x())
            new_scale = new_w / dr.width()
        elif handle in ("t", "b"):
            new_h = abs(mouse_pos.y() - anchor.y())
            full_aspect = self._webcam_aspect()
            crop = self._webcam_crop
            crop_aspect = (crop["h"] * full_aspect) / max(0.001, crop["w"])
            new_scale = new_h / (dr.width() * crop_aspect)
        else:
            # Corner: use the larger of width/height change
            new_w = abs(mouse_pos.x() - anchor.x())
            new_h = abs(mouse_pos.y() - anchor.y())
            full_aspect = self._webcam_aspect()
            crop = self._webcam_crop
            crop_aspect = (crop["h"] * full_aspect) / max(0.001, crop["w"])
            scale_from_w = new_w / dr.width()
            scale_from_h = new_h / (dr.width() * crop_aspect)
            new_scale = max(scale_from_w, scale_from_h)

        new_scale = max(WEBCAM_MIN_SCALE, min(WEBCAM_MAX_SCALE, new_scale))
        self._webcam_scale = new_scale
        self.update()

    # --- Mouse interaction ---

    def _widget_to_webcam_normalized(self, pos: QPoint) -> tuple[float, float]:
        """Convert widget position to normalized coords within the full webcam rect."""
        wc = self._webcam_full_rect()
        x = (pos.x() - wc.x()) / max(1, wc.width())
        y = (pos.y() - wc.y()) / max(1, wc.height())
        return max(0.0, min(1.0, x)), max(0.0, min(1.0, y))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicking on webcam overlay
            if self._webcam_enabled:
                # Check resize handles first
                handle = self._webcam_handle_at(event.pos())
                if handle:
                    self._mode = "resizing_webcam"
                    self._resize_handle = handle
                    # Anchor is the opposite edge/corner of the webcam rect
                    wc = self._webcam_display_rect()
                    anchors = {
                        "tl": QPointF(wc.right(), wc.bottom()),
                        "tr": QPointF(wc.left(), wc.bottom()),
                        "bl": QPointF(wc.right(), wc.top()),
                        "br": QPointF(wc.left(), wc.top()),
                        "t": QPointF(wc.center().x(), wc.bottom()),
                        "b": QPointF(wc.center().x(), wc.top()),
                        "l": QPointF(wc.right(), wc.center().y()),
                        "r": QPointF(wc.left(), wc.center().y()),
                    }
                    self._resize_anchor = anchors[handle]
                    self.setCursor(self._handle_cursor(handle))
                    return

                wc_rect = self._webcam_display_rect()
                if wc_rect.contains(event.position()):
                    # Shift+click → crop mode (show full webcam)
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        self._mode = "cropping_webcam"
                        self._draw_start = event.pos()
                        self._draw_current = event.pos()
                        return
                    # Normal click → drag mode
                    self._mode = "dragging_webcam"
                    self._drag_offset = event.position() - wc_rect.center()
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                    return
            # Otherwise, start drawing a blur region
            self._mode = "drawing"
            self._draw_start = event.pos()
            self._draw_current = event.pos()

        elif event.button() == Qt.MouseButton.RightButton:
            # Right-click on webcam → clear crop
            if self._webcam_enabled:
                wc_rect = self._webcam_display_rect()
                if wc_rect.contains(event.position()):
                    self._webcam_crop = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
                    self.update()
                    return
            # Right-click on blur region → delete it
            nx, ny = self._widget_to_normalized(event.pos())
            for i, r in enumerate(self._regions):
                if (r["x"] <= nx <= r["x"] + r["w"]
                        and r["y"] <= ny <= r["y"] + r["h"]):
                    self._regions.pop(i)
                    self.update()
                    break

    def mouseMoveEvent(self, event):
        if self._mode == "dragging_webcam":
            dr = self._display_rect()
            if dr.width() == 0 or dr.height() == 0:
                return
            new_center = event.position() - self._drag_offset
            nx = (new_center.x() - dr.x()) / dr.width()
            ny = (new_center.y() - dr.y()) / dr.height()
            nx = max(0.0, min(1.0, nx))
            ny = max(0.0, min(1.0, ny))
            if not (event.modifiers() & Qt.KeyboardModifier.AltModifier):
                nx, ny = self._snap_position(nx, ny)
            self._webcam_x = nx
            self._webcam_y = ny
            self.update()
        elif self._mode == "resizing_webcam":
            self._apply_resize(event.position())
        elif self._mode in ("drawing", "cropping_webcam"):
            self._draw_current = event.pos()
            self.update()
        else:
            # Hover cursor
            if self._webcam_enabled:
                handle = self._webcam_handle_at(event.pos())
                if handle:
                    self.setCursor(self._handle_cursor(handle))
                    return
                wc_rect = self._webcam_display_rect()
                if wc_rect.contains(event.position()):
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        self.setCursor(Qt.CursorShape.CrossCursor)
                    else:
                        self.setCursor(Qt.CursorShape.OpenHandCursor)
                    return
            self.setCursor(Qt.CursorShape.CrossCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._mode == "drawing" and self._draw_start and self._draw_current:
                x1, y1 = self._widget_to_normalized(self._draw_start)
                x2, y2 = self._widget_to_normalized(self._draw_current)
                rx, ry = min(x1, x2), min(y1, y2)
                rw, rh = abs(x2 - x1), abs(y2 - y1)
                # Clamp so region stays within capture area
                rw = min(rw, 1.0 - rx)
                rh = min(rh, 1.0 - ry)
                if rw > 0.01 and rh > 0.01:
                    self._regions.append({"x": rx, "y": ry, "w": rw, "h": rh})
            elif self._mode == "cropping_webcam" and self._draw_start and self._draw_current:
                # Convert to full-webcam-normalized coordinates
                full_rect = self._webcam_full_rect()
                x1 = (self._draw_start.x() - full_rect.x()) / max(1, full_rect.width())
                y1 = (self._draw_start.y() - full_rect.y()) / max(1, full_rect.height())
                x2 = (self._draw_current.x() - full_rect.x()) / max(1, full_rect.width())
                y2 = (self._draw_current.y() - full_rect.y()) / max(1, full_rect.height())
                x1, y1 = max(0, min(1, x1)), max(0, min(1, y1))
                x2, y2 = max(0, min(1, x2)), max(0, min(1, y2))
                rx, ry = min(x1, x2), min(y1, y2)
                rw, rh = abs(x2 - x1), abs(y2 - y1)
                # Enforce minimum crop size (WEBCAM_MIN_CROP_PX in display pixels)
                min_w_frac = WEBCAM_MIN_CROP_PX / max(1, full_rect.width())
                min_h_frac = WEBCAM_MIN_CROP_PX / max(1, full_rect.height())
                if rw >= min_w_frac and rh >= min_h_frac:
                    self._webcam_crop = {"x": rx, "y": ry, "w": rw, "h": rh}
                else:
                    # Too small — reset to full
                    self._webcam_crop = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
            elif self._mode == "dragging_webcam":
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            elif self._mode == "resizing_webcam":
                self._resize_handle = ""
            self._mode = "idle"
            self._draw_start = None
            self._draw_current = None
            self.update()

    # --- Painting ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Widget background
        painter.fillRect(self.rect(), QColor("#111111"))

        dr = self._display_rect()

        # Canvas: game frame > background > dark fill
        if self._pixmap:
            painter.drawPixmap(dr, self._pixmap)
        elif self._bg_pixmap:
            painter.drawPixmap(dr, self._bg_pixmap)
        else:
            painter.fillRect(dr, QColor("#1a1a1a"))

        # Blur regions (semi-transparent red)
        painter.setBrush(QColor(255, 80, 80, 80))
        painter.setPen(QColor(255, 80, 80, 200))
        for r in self._regions:
            rx = dr.x() + int(r["x"] * dr.width())
            ry = dr.y() + int(r["y"] * dr.height())
            rw = int(r["w"] * dr.width())
            rh = int(r["h"] * dr.height())
            painter.drawRect(rx, ry, rw, rh)

        # Current drawing rect
        if self._mode == "drawing" and self._draw_start and self._draw_current:
            painter.setBrush(QColor(96, 176, 255, 40))
            painter.setPen(QColor(ACCENT))
            rect = QRect(self._draw_start, self._draw_current).normalized()
            painter.drawRect(rect)

        # Webcam overlay
        if self._webcam_enabled:
            in_crop_mode = (self._mode == "cropping_webcam")

            if in_crop_mode:
                # During crop: show full uncropped webcam so user can see everything
                full_rect = self._webcam_full_rect()
                if self._webcam_pixmap:
                    painter.drawPixmap(full_rect.toRect(), self._webcam_pixmap)
                else:
                    painter.setBrush(QColor(60, 60, 60, 180))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRect(full_rect.toRect())
                    painter.setPen(QColor(200, 200, 200))
                    painter.drawText(
                        full_rect.toRect(), Qt.AlignmentFlag.AlignCenter, "Webcam",
                    )
                # Full webcam border
                border_pen = QPen(QColor(ACCENT))
                border_pen.setWidth(2)
                painter.setPen(border_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(full_rect.toRect())

                # Show existing crop region as overlay
                crop = self._webcam_crop
                has_crop = (crop["x"] > 0.01 or crop["y"] > 0.01
                            or crop["w"] < 0.99 or crop["h"] < 0.99)
                if has_crop:
                    cx = full_rect.x() + crop["x"] * full_rect.width()
                    cy = full_rect.y() + crop["y"] * full_rect.height()
                    cw = crop["w"] * full_rect.width()
                    ch = crop["h"] * full_rect.height()
                    crop_rect = QRectF(cx, cy, cw, ch)
                    # Dim area outside crop
                    painter.setBrush(QColor(0, 0, 0, 120))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRect(QRectF(full_rect.x(), full_rect.y(), full_rect.width(), cy - full_rect.y()))
                    painter.drawRect(QRectF(full_rect.x(), cy + ch, full_rect.width(), full_rect.bottom() - cy - ch))
                    painter.drawRect(QRectF(full_rect.x(), cy, cx - full_rect.x(), ch))
                    painter.drawRect(QRectF(cx + cw, cy, full_rect.right() - cx - cw, ch))
                    # Crop border
                    crop_pen = QPen(QColor(255, 200, 50))
                    crop_pen.setWidth(2)
                    crop_pen.setStyle(Qt.PenStyle.DashLine)
                    painter.setPen(crop_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(crop_rect)

                # In-progress crop drawing
                if self._draw_start and self._draw_current:
                    crop_pen = QPen(QColor(255, 200, 50, 200))
                    crop_pen.setWidth(2)
                    painter.setPen(crop_pen)
                    painter.setBrush(QColor(255, 200, 50, 30))
                    rect = QRect(self._draw_start, self._draw_current).normalized()
                    rect = rect.intersected(full_rect.toRect())
                    painter.drawRect(rect)
            else:
                # Normal mode: only show the cropped portion
                vis_rect = self._webcam_display_rect()
                if self._webcam_pixmap:
                    crop = self._webcam_crop
                    pw = self._webcam_pixmap.width()
                    ph = self._webcam_pixmap.height()
                    src_rect = QRectF(
                        crop["x"] * pw, crop["y"] * ph,
                        crop["w"] * pw, crop["h"] * ph,
                    )
                    painter.drawPixmap(vis_rect.toRect(), self._webcam_pixmap, src_rect.toRect())
                else:
                    painter.setBrush(QColor(60, 60, 60, 180))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRect(vis_rect.toRect())
                    painter.setPen(QColor(200, 200, 200))
                    painter.drawText(
                        vis_rect.toRect(), Qt.AlignmentFlag.AlignCenter, "Webcam",
                    )
                # Border
                border_pen = QPen(QColor(ACCENT))
                border_pen.setWidth(2)
                painter.setPen(border_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(vis_rect.toRect())

                # Resize handles (small squares at corners and edge midpoints)
                hs = self._HANDLE_SIZE
                r = vis_rect.toRect()
                handle_color = QColor(ACCENT)
                painter.setBrush(handle_color)
                painter.setPen(Qt.PenStyle.NoPen)
                # Corners
                for hx, hy in [
                    (r.left(), r.top()), (r.right(), r.top()),
                    (r.left(), r.bottom()), (r.right(), r.bottom()),
                ]:
                    painter.drawRect(hx - hs // 2, hy - hs // 2, hs, hs)
                # Edge midpoints
                for hx, hy in [
                    (r.center().x(), r.top()), (r.center().x(), r.bottom()),
                    (r.left(), r.center().y()), (r.right(), r.center().y()),
                ]:
                    painter.drawRect(hx - hs // 2, hy - hs // 2, hs, hs)

        # Snap guide lines (subtle)
        if self._mode == "dragging_webcam":
            pen = QPen(QColor(255, 255, 255, 40))
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            vcx = dr.x() + dr.width() // 2
            painter.drawLine(vcx, dr.y(), vcx, dr.y() + dr.height())
            hcy = dr.y() + dr.height() // 2
            painter.drawLine(dr.x(), hcy, dr.x() + dr.width(), hcy)

        painter.end()


class VideoConfigDialog(QDialog):
    """Unified video capture configuration with live preview.

    Combines resolution/FPS/bitrate settings, webcam placement,
    blur regions, and background in a single dialog.
    """

    _INPUT_MAX_W = 180
    _webcam_devices_ready = pyqtSignal(list)
    _frame_delivered = pyqtSignal()  # emitted from capture thread

    def __init__(self, *, config, config_path, event_bus,
                 frame_distributor=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._event_bus = event_bus
        self._frame_distributor = frame_distributor
        self._bg_video_cap = None
        self._bg_path: str = config.capture_preview_background
        self._webcam_capture = None  # WebcamCapture for live preview
        self._webcam_borrowed = False  # True when reusing background capture
        self._frame_sub = None       # FrameSubscription for sync'd delivery
        self._pending_frame = None   # latest frame from capture thread
        self._webcam_devices_ready.connect(self._update_webcam_combo)
        self._frame_delivered.connect(self._on_frame_delivered)

        self.setWindowTitle("Video Capture Configuration")
        self.setMinimumSize(1000, 620)
        self.resize(1100, 680)

        main_layout = QHBoxLayout(self)

        # --- Left: Preview ---
        left = QVBoxLayout()

        desc = QLabel(
            "Left-click to draw blur regions. Right-click to delete. "
            "Drag webcam to reposition (Alt disables snap). "
            "Drag edges/corners to resize. "
            "Shift+drag on webcam to crop. Right-click webcam to reset crop."
        )
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        desc.setWordWrap(True)
        left.addWidget(desc)

        aspect = self._detect_aspect_ratio()
        self._preview = _PreviewWidget()
        self._preview.set_aspect_ratio(aspect)
        self._preview.regions = list(config.capture_blur_regions)
        self._preview.set_webcam_enabled(config.clip_webcam_enabled)
        self._preview.set_webcam_scale(config.clip_webcam_scale)
        self._preview.set_webcam_position(
            config.clip_webcam_position_x, config.clip_webcam_position_y,
        )
        self._preview.set_webcam_crop({
            "x": config.clip_webcam_crop_x,
            "y": config.clip_webcam_crop_y,
            "w": config.clip_webcam_crop_w,
            "h": config.clip_webcam_crop_h,
        })
        left.addWidget(self._preview, stretch=1)

        # Preview buttons
        preview_btns = QHBoxLayout()
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setToolTip("Capture a new frame from the game window")
        self._refresh_btn.clicked.connect(self._refresh_preview)
        preview_btns.addWidget(self._refresh_btn)

        clear_blur_btn = QPushButton("Clear Blur Regions")
        clear_blur_btn.clicked.connect(lambda: setattr(self._preview, "regions", []))
        preview_btns.addWidget(clear_blur_btn)

        preview_btns.addStretch()
        left.addLayout(preview_btns)

        main_layout.addLayout(left, stretch=1)

        # --- Right: Tabs + buttons (fixed width) ---
        right_panel = QWidget()
        right_panel.setFixedWidth(320)
        right = QVBoxLayout(right_panel)
        right.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.addTab(self._build_output_tab(), "Output")
        tabs.addTab(self._build_webcam_tab(), "Webcam")
        tabs.addTab(self._build_blur_tab(), "Blur")
        right.addWidget(tabs, stretch=1)

        # Dialog buttons (outside tabs)
        dialog_btns = QHBoxLayout()
        dialog_btns.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        dialog_btns.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("accentButton")
        save_btn.clicked.connect(self._save)
        dialog_btns.addWidget(save_btn)
        right.addLayout(dialog_btns)

        main_layout.addWidget(right_panel)

        # --- Timers & frame sources ---
        self._boosted = False

        # Timer only for background video playback (not frame refresh)
        self._bg_timer = QTimer(self)
        self._bg_timer.timeout.connect(self._on_bg_tick)

        # Subscribe to frame distributor for live preview while dialog is open
        self._boost_distributor()

        # Load background
        self._load_background(self._bg_path)

        # Webcam preview timer (interval set dynamically from FPS selection)
        self._webcam_timer = QTimer(self)
        self._webcam_timer.timeout.connect(self._update_webcam_preview)

        # Blur count update timer (cheap, ~2Hz)
        self._count_timer = QTimer(self)
        self._count_timer.setInterval(500)
        self._count_timer.timeout.connect(
            lambda: self._blur_count_label.setText(self._blur_count_text())
        )
        self._count_timer.start()

        # Initial frame
        self._refresh_preview()

    # --- Tab builders ---

    def _build_output_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # Grid for Resolution / FPS / Bitrate
        grid = QGridLayout()
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setHorizontalSpacing(12)

        grid.addWidget(QLabel("Resolution:"), 0, 0)
        self._resolution_combo = QComboBox()
        self._resolution_combo.setMaximumWidth(220)
        self._resolution_combo.addItem("Source", "source")
        for group_label, items in RESOLUTION_GROUPS:
            self._resolution_combo.insertSeparator(self._resolution_combo.count())
            # Group header (disabled, not selectable)
            hdr_idx = self._resolution_combo.count()
            self._resolution_combo.addItem(f"── {group_label} ──", None)
            model = self._resolution_combo.model()
            if model and model.item(hdr_idx):
                model.item(hdr_idx).setEnabled(False)
            for key, label, w, h in items:
                self._resolution_combo.addItem(
                    f"{label}  ({w}\u00d7{h})", key,
                )
        idx = self._resolution_combo.findData(self._config.clip_resolution)
        if idx >= 0:
            self._resolution_combo.setCurrentIndex(idx)
        self._resolution_combo.currentIndexChanged.connect(self._on_resolution_changed)
        grid.addWidget(self._resolution_combo, 0, 1)

        grid.addWidget(QLabel("FPS:"), 1, 0)
        self._fps_combo = QComboBox()
        self._fps_combo.setMaximumWidth(self._INPUT_MAX_W)
        for fps in (15, 24, 30, 48, 60):
            self._fps_combo.addItem(str(fps), fps)
        idx = self._fps_combo.findData(self._config.clip_fps)
        if idx >= 0:
            self._fps_combo.setCurrentIndex(idx)
        self._fps_combo.currentIndexChanged.connect(self._on_output_fps_changed)
        grid.addWidget(self._fps_combo, 1, 1)

        grid.addWidget(QLabel("Bitrate:"), 2, 0)
        self._bitrate_combo = QComboBox()
        self._bitrate_combo.setMaximumWidth(self._INPUT_MAX_W)
        for br in ("low", "medium", "high", "ultra"):
            self._bitrate_combo.addItem(br.capitalize(), br)
        idx = self._bitrate_combo.findData(self._config.clip_bitrate)
        if idx >= 0:
            self._bitrate_combo.setCurrentIndex(idx)
        grid.addWidget(self._bitrate_combo, 2, 1)

        grid.addWidget(QLabel("Capture:"), 3, 0)
        self._backend_combo = QComboBox()
        self._backend_combo.setMaximumWidth(self._INPUT_MAX_W)
        self._backend_combo.addItem("Auto", "auto")
        self._backend_combo.addItem("WGC", "wgc")
        self._backend_combo.addItem("BitBlt", "bitblt")
        current_backend = getattr(self._config, "clip_capture_backend", "auto")
        idx = self._backend_combo.findData(current_backend)
        self._backend_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._backend_combo.setToolTip(
            "Auto: Uses WGC when clip FPS matches the monitor refresh rate,\n"
            "otherwise BitBlt to avoid unnecessary GPU load.\n"
            "WGC (Windows Graphics Capture): Best quality, HDR-safe.\n"
            "BitBlt: Lower overhead, works everywhere."
        )
        self._backend_combo.currentIndexChanged.connect(self._on_clip_backend_changed)
        grid.addWidget(self._backend_combo, 3, 1)

        grid.addWidget(QLabel("Scaling:"), 4, 0)
        self._scaling_combo = QComboBox()
        self._scaling_combo.setMaximumWidth(self._INPUT_MAX_W)
        for key, (_cv_const, label, tooltip) in SCALING_ALGORITHMS.items():
            self._scaling_combo.addItem(label, key)
        idx = self._scaling_combo.findData(
            getattr(self._config, "clip_scaling", "lanczos"),
        )
        self._scaling_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._scaling_combo.setToolTip(
            "Interpolation algorithm used when resizing frames.\n"
            "Lanczos: sharpest (OBS default). Bilinear: fast.\n"
            "Area: best for downscaling. Bicubic: balanced."
        )
        grid.addWidget(self._scaling_combo, 4, 1)

        layout.addLayout(grid)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(sep)

        # Background
        bg_label = QLabel("Background")
        bg_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(bg_label)

        bg_desc = QLabel(
            "Image or video shown behind the game frame when "
            "the output resolution differs from game window."
        )
        bg_desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        bg_desc.setWordWrap(True)
        layout.addWidget(bg_desc)

        bg_btn_row = QHBoxLayout()
        bg_browse_btn = QPushButton("Browse...")
        bg_browse_btn.clicked.connect(self._browse_background)
        bg_btn_row.addWidget(bg_browse_btn)
        bg_clear_btn = QPushButton("Clear")
        bg_clear_btn.clicked.connect(self._clear_background)
        bg_btn_row.addWidget(bg_clear_btn)
        bg_btn_row.addStretch()
        layout.addLayout(bg_btn_row)

        self._bg_path_label = QLabel("")
        self._bg_path_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        self._bg_path_label.setWordWrap(True)
        layout.addWidget(self._bg_path_label)
        self._update_bg_label()

        layout.addStretch()
        return tab

    def _build_webcam_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        self._webcam_cb = QCheckBox("Show webcam overlay")
        self._webcam_cb.setChecked(self._config.clip_webcam_enabled)
        self._webcam_cb.toggled.connect(self._on_webcam_toggled)
        layout.addWidget(self._webcam_cb)

        self._webcam_keep_ready_cb = QCheckBox("Keep webcam ready")
        self._webcam_keep_ready_cb.setToolTip(
            "Keep the webcam claimed when not recording, so it's\n"
            "instantly available. Other programs won't be able\n"
            "to use the webcam while this is enabled."
        )
        self._webcam_keep_ready_cb.setChecked(self._config.clip_webcam_keep_ready)
        self._webcam_keep_ready_cb.setEnabled(self._config.clip_webcam_enabled)
        layout.addWidget(self._webcam_keep_ready_cb)

        # Device selection
        dev_grid = QGridLayout()
        dev_grid.setColumnStretch(0, 0)
        dev_grid.setColumnStretch(1, 0)
        dev_grid.setHorizontalSpacing(12)

        dev_grid.addWidget(QLabel("Device:"), 0, 0)
        self._webcam_device_combo = QComboBox()
        self._webcam_device_combo.setMaximumWidth(self._INPUT_MAX_W)
        self._webcam_device_combo.addItem("Loading...", -1)
        dev_grid.addWidget(self._webcam_device_combo, 0, 1)

        dev_grid.addWidget(QLabel("FPS:"), 1, 0)
        self._webcam_fps_combo = QComboBox()
        self._webcam_fps_combo.setMaximumWidth(self._INPUT_MAX_W)
        self._webcam_fps_combo.addItem("Auto", 0)
        for fps in (15, 24, 30, 48, 60):
            self._webcam_fps_combo.addItem(str(fps), fps)
        webcam_fps = self._config.clip_webcam_fps
        idx = self._webcam_fps_combo.findData(webcam_fps)
        if idx >= 0:
            self._webcam_fps_combo.setCurrentIndex(idx)
        self._webcam_fps_combo.currentIndexChanged.connect(self._on_webcam_fps_changed)
        dev_grid.addWidget(self._webcam_fps_combo, 1, 1)
        # Apply initial clamp based on current output FPS
        self._clamp_webcam_fps()

        layout.addLayout(dev_grid)

        # Buttons
        btn_row = QHBoxLayout()
        self._cam_settings_btn = QPushButton("Camera Settings...")
        self._cam_settings_btn.setToolTip("Open the native webcam properties dialog")
        self._cam_settings_btn.clicked.connect(self._open_webcam_settings)
        btn_row.addWidget(self._cam_settings_btn)
        refresh_btn = QPushButton("Refresh Devices")
        refresh_btn.setToolTip("Re-scan for connected webcam devices")
        refresh_btn.clicked.connect(self._refresh_webcam_devices)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btn_row2 = QHBoxLayout()
        btn_row2.setSpacing(4)
        _compact = "padding: 3px 6px; font-size: 11px;"
        reset_pos_btn = QPushButton("Reset Position")
        reset_pos_btn.setStyleSheet(_compact)
        reset_pos_btn.clicked.connect(self._reset_webcam_position)
        btn_row2.addWidget(reset_pos_btn)
        reset_size_btn = QPushButton("Reset Size")
        reset_size_btn.setStyleSheet(_compact)
        reset_size_btn.clicked.connect(self._reset_webcam_scale)
        btn_row2.addWidget(reset_size_btn)
        reset_crop_btn = QPushButton("Reset Crop")
        reset_crop_btn.setStyleSheet(_compact)
        reset_crop_btn.clicked.connect(self._reset_webcam_crop)
        btn_row2.addWidget(reset_crop_btn)
        btn_row2.addStretch()
        layout.addLayout(btn_row2)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(sep)

        # Chroma key
        chroma_label = QLabel("Chroma Key")
        chroma_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(chroma_label)

        self._chroma_cb = QCheckBox("Enable green screen removal")
        self._chroma_cb.setChecked(self._config.clip_webcam_chroma_enabled)
        layout.addWidget(self._chroma_cb)

        chroma_grid = QGridLayout()
        chroma_grid.setColumnStretch(0, 0)
        chroma_grid.setColumnStretch(1, 0)
        chroma_grid.setHorizontalSpacing(12)

        chroma_grid.addWidget(QLabel("Key color:"), 0, 0)
        self._chroma_color_btn = QPushButton()
        self._chroma_color_btn.setFixedSize(32, 24)
        self._chroma_color = self._config.clip_webcam_chroma_color
        self._chroma_color_btn.setStyleSheet(
            f"background-color: {self._chroma_color}; border: 1px solid {BORDER};"
        )
        self._chroma_color_btn.clicked.connect(self._pick_chroma_color)
        chroma_grid.addWidget(self._chroma_color_btn, 0, 1)

        chroma_grid.addWidget(QLabel("Threshold:"), 1, 0)
        thresh_w = QWidget()
        thresh_h = QHBoxLayout(thresh_w)
        thresh_h.setContentsMargins(0, 0, 0, 0)
        self._chroma_threshold = QSlider(Qt.Orientation.Horizontal)
        self._chroma_threshold.setMaximumWidth(self._INPUT_MAX_W)
        self._chroma_threshold.setRange(5, 255)
        self._chroma_threshold.setValue(self._config.clip_webcam_chroma_threshold)
        thresh_h.addWidget(self._chroma_threshold)
        self._chroma_thresh_label = QLabel(str(self._config.clip_webcam_chroma_threshold))
        self._chroma_thresh_label.setFixedWidth(30)
        self._chroma_threshold.valueChanged.connect(
            lambda v: self._chroma_thresh_label.setText(str(v))
        )
        thresh_h.addWidget(self._chroma_thresh_label)
        chroma_grid.addWidget(thresh_w, 1, 1)

        chroma_grid.addWidget(QLabel("Smoothing:"), 2, 0)
        smooth_w = QWidget()
        smooth_h = QHBoxLayout(smooth_w)
        smooth_h.setContentsMargins(0, 0, 0, 0)
        self._chroma_smoothing = QSlider(Qt.Orientation.Horizontal)
        self._chroma_smoothing.setMaximumWidth(self._INPUT_MAX_W)
        self._chroma_smoothing.setRange(1, 21)
        self._chroma_smoothing.setSingleStep(2)
        self._chroma_smoothing.setValue(self._config.clip_webcam_chroma_smoothing)
        smooth_h.addWidget(self._chroma_smoothing)
        self._chroma_smooth_label = QLabel(str(self._config.clip_webcam_chroma_smoothing))
        self._chroma_smooth_label.setFixedWidth(30)
        self._chroma_smoothing.valueChanged.connect(
            lambda v: self._chroma_smooth_label.setText(str(v))
        )
        smooth_h.addWidget(self._chroma_smooth_label)
        chroma_grid.addWidget(smooth_w, 2, 1)

        layout.addLayout(chroma_grid)
        layout.addStretch()

        # Use cached devices from WebcamCapture if available, otherwise
        # wait for in-progress background discovery or probe from scratch.
        from ...capture.webcam_capture import WebcamCapture as _WC
        cached = _WC.get_cached_devices()
        if cached is not None:
            QTimer.singleShot(0, lambda: self._webcam_devices_ready.emit(cached))
        else:
            import threading
            threading.Thread(
                target=self._probe_webcam_devices, daemon=True,
                name="wcam-probe-dialog",
            ).start()

        return tab

    def _build_blur_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        desc = QLabel(
            "Draw rectangles on the preview to blur areas in "
            "both screenshots and video clips.\n\n"
            "Left-click to draw a new region.\n"
            "Right-click an existing region to delete it.\n\n"
            "Blur regions are clamped to the capture area so they "
            "work consistently between screenshots and video clips."
        )
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._blur_count_label = QLabel(self._blur_count_text())
        layout.addWidget(self._blur_count_label)

        layout.addStretch()
        return tab

    # --- Aspect ratio / resolution ---

    def _detect_aspect_ratio(self) -> float:
        try:
            from ...platform import backend as _platform
            from ...core.constants import GAME_TITLE_PREFIX
            hwnd = _platform.find_window_by_title_prefix(GAME_TITLE_PREFIX)
            if hwnd:
                geo = _platform.get_window_geometry(hwnd)
                if geo and geo[2] > 0 and geo[3] > 0:
                    return geo[2] / geo[3]
        except Exception:
            pass
        res = RESOLUTION_PRESETS.get(self._config.clip_resolution)
        if res:
            return res[0] / res[1]
        return _DEFAULT_ASPECT

    def _on_resolution_changed(self, _idx):
        res_key = self._resolution_combo.currentData()
        if res_key is None:
            return  # disabled group header — ignore
        res = RESOLUTION_PRESETS.get(res_key)
        if res:
            self._preview.set_aspect_ratio(res[0] / res[1])
        else:
            # Source — use game window aspect
            aspect = self._detect_aspect_ratio()
            self._preview.set_aspect_ratio(aspect)

    # --- Background ---

    def _update_bg_label(self):
        path = self._bg_path
        if path:
            name = Path(path).name
            self._bg_path_label.setText(name)
        else:
            self._bg_path_label.setText("None")

    def _load_background(self, path: str) -> None:
        if self._bg_video_cap is not None:
            self._bg_video_cap.release()
            self._bg_video_cap = None
            self._bg_timer.stop()

        if not path or not Path(path).is_file():
            self._preview.set_background(None)
            return

        if cv2 is None:
            return

        ext = Path(path).suffix.lower()
        video_exts = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv", ".flv"}
        if ext in video_exts:
            cap = cv2.VideoCapture(path)
            if cap.isOpened():
                self._bg_video_cap = cap
                self._advance_bg_video()
                if not self._bg_timer.isActive():
                    self._bg_timer.setInterval(33)  # ~30fps for bg video
                    self._bg_timer.start()
                return
            cap.release()

        img = cv2.imread(path)
        if img is not None:
            h, w = img.shape[:2]
            qimg = QImage(
                img.data, w, h, img.strides[0],
                QImage.Format.Format_BGR888,
            )
            self._preview.set_background(QPixmap.fromImage(qimg))

    def _advance_bg_video(self) -> None:
        if self._bg_video_cap is None or cv2 is None:
            return
        ok, frame = self._bg_video_cap.read()
        if not ok:
            self._bg_video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._bg_video_cap.read()
            if not ok:
                return
        h, w = frame.shape[:2]
        qimg = QImage(
            frame.data, w, h, frame.strides[0],
            QImage.Format.Format_BGR888,
        )
        self._preview.set_background(QPixmap.fromImage(qimg))

    def _browse_background(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Image or Video",
            self._bg_path or "",
            "Media files (*.png *.jpg *.jpeg *.bmp *.mp4 *.avi *.mkv *.mov *.webm *.wmv *.flv);;"
            "All files (*)",
        )
        if path:
            self._bg_path = path
            self._update_bg_label()
            self._load_background(path)

    def _clear_background(self):
        self._bg_path = ""
        self._update_bg_label()
        self._load_background("")

    # --- Webcam ---

    def _on_webcam_toggled(self, checked):
        self._preview.set_webcam_enabled(checked)
        self._webcam_keep_ready_cb.setEnabled(checked)
        if checked:
            self._start_webcam_preview()
        else:
            self._stop_webcam_preview()

    def _reset_webcam_position(self):
        from ...capture.constants import WEBCAM_DEFAULT_POS_X, WEBCAM_DEFAULT_POS_Y
        self._preview.set_webcam_position(WEBCAM_DEFAULT_POS_X, WEBCAM_DEFAULT_POS_Y)

    def _reset_webcam_scale(self):
        self._preview.set_webcam_scale(WEBCAM_OVERLAY_SCALE)

    def _reset_webcam_crop(self):
        self._preview.set_webcam_crop({"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0})

    def _open_webcam_settings(self):
        """Open the native webcam properties dialog.

        If a preview capture is already running, reuses its open VideoCapture
        (instant). Otherwise falls back to opening a new capture (slower).
        """
        dev_idx = self._webcam_device_combo.currentData()
        if dev_idx is None or dev_idx == -1:
            return
        # Reuse the existing capture if available — avoids opening a new camera
        if self._webcam_capture is not None:
            if self._webcam_capture.request_settings_dialog():
                return
        # No active preview — fall back to static method (opens a new capture)
        try:
            from ...capture.webcam_capture import WebcamCapture
            WebcamCapture.open_settings_dialog(dev_idx)
        except Exception as e:
            log.warning("Failed to open webcam settings: %s", e)

    def _pick_chroma_color(self):
        current = QColor(self._chroma_color)
        color = QColorDialog.getColor(current, self, "Select Chroma Key Color")
        if color.isValid():
            self._chroma_color = color.name()
            self._chroma_color_btn.setStyleSheet(
                f"background-color: {self._chroma_color}; border: 1px solid {BORDER};"
            )

    def _refresh_webcam_devices(self):
        """Manually re-probe webcam devices (clears cache)."""
        from ...capture.webcam_capture import WebcamCapture as _WC
        _WC.invalidate_cache()
        self._stop_webcam_preview()
        self._webcam_device_combo.clear()
        self._webcam_device_combo.addItem("Loading...", -1)
        import threading
        threading.Thread(
            target=self._probe_webcam_devices, daemon=True,
            name="wcam-probe-dialog",
        ).start()

    def _probe_webcam_devices(self):
        """Wait for in-progress background discovery or probe from scratch."""
        from ...capture.webcam_capture import WebcamCapture as _WC
        # If background discovery is in progress, wait for it
        devices = _WC.get_cached_devices(timeout=10)
        if devices is None:
            # No background discovery ran — probe from scratch
            try:
                devices = _WC.list_devices()
            except Exception:
                devices = []
            _WC.set_cached_devices(devices or None)
        self._webcam_devices_ready.emit(devices)

    def _update_webcam_combo(self, devices):
        """Update webcam device combo with probed results (main thread)."""
        self._webcam_device_combo.blockSignals(True)
        self._webcam_device_combo.clear()
        if not devices:
            self._webcam_device_combo.addItem("No cameras found", -1)
        else:
            for dev in devices:
                self._webcam_device_combo.addItem(dev["label"], dev["index"])
            current = self._config.clip_webcam_device
            idx = self._webcam_device_combo.findData(current)
            if idx >= 0:
                self._webcam_device_combo.setCurrentIndex(idx)
        self._webcam_device_combo.blockSignals(False)
        self._webcam_device_combo.currentIndexChanged.connect(self._on_webcam_device_changed)

        # Start live webcam preview if webcam is enabled and a device is available
        if self._webcam_cb.isChecked() and devices:
            self._start_webcam_preview()

    def _on_webcam_device_changed(self, _idx):
        """Restart webcam preview when device selection changes."""
        self._stop_webcam_preview()
        if self._webcam_cb.isChecked():
            self._start_webcam_preview()

    def _on_clip_backend_changed(self, _idx):
        """Re-boost the distributor with the new backend and warn about WGC overhead."""
        backend = self._backend_combo.currentData()
        clip_fps = self._fps_combo.currentData() or 30

        # Re-boost the frame distributor with the new backend
        if self._boosted:
            fd = self._get_frame_distributor()
            if fd is not None and hasattr(fd, "boost"):
                clip_backend = resolve_clip_backend(backend or "auto", clip_fps)
                fd.boost("video_config_dialog", min_hz=clip_fps, capture_backend=clip_backend)

        if backend != "wgc":
            return
        monitor_hz = get_monitor_refresh_rate()
        if clip_fps >= monitor_hz:
            return
        dlg = QMessageBox(self)
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setWindowTitle("WGC Resource Warning")
        dlg.setText(
            f"Your monitor runs at {monitor_hz} Hz but the clip FPS is set to "
            f"{clip_fps}. WGC captures at the display refresh rate, so "
            f"{monitor_hz - clip_fps} frames per second will be captured and "
            f"discarded, wasting GPU resources.\n\n"
            f"Consider setting the FPS to {monitor_hz} to fully utilise WGC, "
            f"or switch to BitBlt which only captures on demand."
        )
        switch_btn = dlg.addButton("Switch to BitBlt", QMessageBox.ButtonRole.AcceptRole)
        dlg.addButton("Keep WGC", QMessageBox.ButtonRole.RejectRole)
        dlg.setDefaultButton(switch_btn)
        dlg.exec()
        if dlg.clickedButton() == switch_btn:
            idx = self._backend_combo.findData("bitblt")
            if idx >= 0:
                self._backend_combo.blockSignals(True)
                self._backend_combo.setCurrentIndex(idx)
                self._backend_combo.blockSignals(False)
                # Re-boost with BitBlt
                fd = self._get_frame_distributor()
                if fd is not None and hasattr(fd, "boost"):
                    fd.boost("video_config_dialog", min_hz=clip_fps, capture_backend="bitblt")

    def _on_output_fps_changed(self, _idx):
        """Resubscribe at new FPS and update webcam clamp."""
        output_fps = self._fps_combo.currentData() or 30
        if self._boosted:
            fd = self._get_frame_distributor()
            if fd is not None:
                # Re-boost at new FPS (no backend change)
                if hasattr(fd, "boost"):
                    fd.boost("video_config_dialog", min_hz=output_fps)
                # Resubscribe at new Hz
                if self._frame_sub is not None and hasattr(fd, "unsubscribe"):
                    fd.unsubscribe(self._frame_sub)
                if hasattr(fd, "subscribe"):
                    self._frame_sub = fd.subscribe(
                        "video_config_dialog", self._on_capture_frame,
                        hz=output_fps,
                    )
        # Clamp webcam FPS
        self._clamp_webcam_fps()

    def _clamp_webcam_fps(self):
        """Disable webcam FPS options higher than the output FPS."""
        output_fps = self._fps_combo.currentData() or 30
        current_webcam_fps = self._webcam_fps_combo.currentData()

        for i in range(self._webcam_fps_combo.count()):
            fps_val = self._webcam_fps_combo.itemData(i)
            # Auto (0) is always enabled; disable concrete values > output
            disabled = fps_val > 0 and fps_val > output_fps
            model = self._webcam_fps_combo.model()
            item = model.item(i)
            if item is not None:
                if disabled:
                    item.setEnabled(False)
                else:
                    item.setEnabled(True)

        # If current selection is now disabled, fall back to Auto
        if current_webcam_fps > 0 and current_webcam_fps > output_fps:
            self._webcam_fps_combo.setCurrentIndex(0)  # Auto

    def _get_effective_webcam_fps(self) -> int:
        """Return the effective webcam FPS (resolves Auto to output FPS)."""
        val = self._webcam_fps_combo.currentData()
        if val == 0:  # Auto
            return self._fps_combo.currentData() or 30
        return val or 30

    def _on_webcam_fps_changed(self, _idx):
        """Restart webcam preview when FPS selection changes."""
        if self._webcam_capture is not None:
            self._stop_webcam_preview()
            self._start_webcam_preview()

    def _start_webcam_preview(self):
        """Start webcam capture for live preview in the dialog.

        Reuses the background capture from CaptureManager when the
        selected device matches, avoiding a second cv2.VideoCapture
        that would conflict on MSMF.
        """
        self._stop_webcam_preview()
        dev_idx = self._webcam_device_combo.currentData()
        if dev_idx is None or dev_idx == -1:
            return
        fps = self._get_effective_webcam_fps()
        from ...capture.webcam_capture import WebcamCapture
        # Borrow the active background capture if it's on the same device
        active = WebcamCapture._active_instance
        if active is not None and active._device == dev_idx and active._running:
            self._webcam_capture = active
            self._webcam_borrowed = True
            self._webcam_timer.setInterval(max(16, 1000 // fps))
            self._webcam_timer.start()
            log.debug("Webcam preview borrowing active capture (device=%d)", dev_idx)
            return
        try:
            self._webcam_capture = WebcamCapture(device=dev_idx, fps=fps)
            self._webcam_capture.start()
            self._webcam_borrowed = False
            # Match preview polling rate to capture FPS
            self._webcam_timer.setInterval(max(16, 1000 // fps))
            self._webcam_timer.start()
            log.debug("Webcam preview started (device=%d, fps=%d)", dev_idx, fps)
        except Exception as e:
            log.warning("Failed to start webcam preview: %s", e)
            self._webcam_capture = None
            self._webcam_borrowed = False
            WebcamCapture.invalidate_cache()

    def _stop_webcam_preview(self):
        """Stop the webcam capture preview.

        Borrowed captures (from CaptureManager) are detached but not stopped.
        """
        self._webcam_timer.stop()
        if self._webcam_capture is not None:
            if not self._webcam_borrowed:
                self._webcam_capture.stop()
            self._webcam_capture = None
            self._webcam_borrowed = False

    def _update_webcam_preview(self):
        """Feed the latest webcam frame to the preview widget.

        When chroma key is enabled, the BGR frame is downscaled first,
        then chroma is applied to produce BGRA.  This avoids interpolation
        artifacts on premultiplied alpha.
        """
        if self._webcam_capture is None:
            return
        frame = self._webcam_capture.get_latest_frame()
        if frame is None:
            return
        if cv2 is not None and self._chroma_cb.isChecked():
            # Downscale BGR before chroma to avoid premultiplied-alpha artifacts
            wc = self._preview._webcam_display_rect()
            target_w = max(1, int(wc.width()))
            h, w = frame.shape[:2]
            if target_w > 0 and w > target_w * 1.5:
                scale = target_w / w
                frame = cv2.resize(
                    frame, (target_w, int(h * scale)),
                    interpolation=cv2.INTER_CUBIC,
                )
            frame = self._apply_chroma_preview(frame)
        self._preview.set_webcam_frame(frame)

    def _apply_chroma_preview(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Apply chroma key to a BGR webcam frame, returning BGRA.

        Uses the same algorithm as ``clip_writer._apply_chroma_key`` but
        produces a 4-channel BGRA array for Qt alpha compositing.
        """
        color_hex = self._chroma_color.lstrip("#")
        try:
            r = int(color_hex[0:2], 16)
            g = int(color_hex[2:4], 16)
            b = int(color_hex[4:6], 16)
        except (ValueError, IndexError):
            r, g, b = 0, 255, 0
        threshold = self._chroma_threshold.value()
        smoothing = self._chroma_smoothing.value()

        key_bgr = np.array([b, g, r], dtype=np.float32)
        diff = np.linalg.norm(
            frame_bgr.astype(np.float32) - key_bgr, axis=2,
        )
        alpha = np.where(diff > threshold, 255, 0).astype(np.uint8)
        if smoothing > 1:
            ksize = smoothing | 1
            alpha = cv2.GaussianBlur(alpha, (ksize, ksize), 0)

        # Premultiply RGB by alpha for Qt Format_ARGB32_Premultiplied
        alpha_f = alpha.astype(np.float32) / 255.0
        premul = (frame_bgr.astype(np.float32) * alpha_f[:, :, np.newaxis]).astype(np.uint8)
        bgra = np.dstack((premul, alpha))
        return np.ascontiguousarray(bgra)

    # --- Blur ---

    def _blur_count_text(self) -> str:
        n = len(self._preview.regions)
        return f"{n} region{'s' if n != 1 else ''} defined"

    # --- Frame refresh ---

    def _boost_distributor(self) -> None:
        """Boost the frame distributor and subscribe for sync'd frame delivery.

        Does NOT force a capture backend switch — the preview uses whatever
        backend is already active.  Backend changes happen only when the
        user explicitly changes the Capture combo (see _on_clip_backend_changed).
        """
        if self._boosted:
            return
        fd = self._get_frame_distributor()
        if fd is None:
            return
        fps = self._fps_combo.currentData() or 30
        if hasattr(fd, "boost"):
            fd.boost("video_config_dialog", min_hz=fps)
        if hasattr(fd, "subscribe"):
            self._frame_sub = fd.subscribe(
                "video_config_dialog", self._on_capture_frame, hz=fps,
            )
        self._boosted = True

    def _unboost_distributor(self) -> None:
        """Remove preview boost and unsubscribe from frame delivery."""
        if not self._boosted:
            return
        fd = self._get_frame_distributor()
        if fd is not None:
            if self._frame_sub is not None and hasattr(fd, "unsubscribe"):
                fd.unsubscribe(self._frame_sub)
                self._frame_sub = None
            if hasattr(fd, "unboost"):
                fd.unboost("video_config_dialog")
        self._frame_sub = None
        self._boosted = False

    def _on_capture_frame(self, frame, _timestamp):
        """Callback from the capture thread — store frame and notify Qt."""
        try:
            self._pending_frame = frame
            self._frame_delivered.emit()
        except RuntimeError:
            # Dialog's C++ object already destroyed (race with cleanup)
            pass

    def _on_frame_delivered(self):
        """Main-thread handler: display the latest captured frame."""
        frame = self._pending_frame
        if frame is None:
            return
        self._preview.set_frame(frame)
        res_key = self._resolution_combo.currentData()
        if res_key == "source":
            h, w = frame.shape[:2]
            if w > 0 and h > 0:
                self._preview.set_aspect_ratio(w / h)

    def _on_bg_tick(self):
        """Timer tick for background video playback only."""
        if self._bg_video_cap is not None:
            self._advance_bg_video()
            if self._preview._pixmap is None:
                self._preview.update()

    def _get_frame_distributor(self):
        if self._frame_distributor is not None:
            return self._frame_distributor
        # Fallback: search top-level widgets (for backward compatibility)
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
        fd = self._get_frame_distributor()
        if fd is None:
            return
        frame = fd.get_latest_frame()
        if frame is None:
            frame = self._direct_capture(fd)
        if frame is not None:
            self._preview.set_frame(frame)
            # Update aspect when in source mode
            res_key = self._resolution_combo.currentData()
            if res_key == "source":
                h, w = frame.shape[:2]
                if w > 0 and h > 0:
                    self._preview.set_aspect_ratio(w / h)

    def _direct_capture(self, fd):
        try:
            from ...platform import backend as _platform
            from ...core.constants import GAME_TITLE_PREFIX
            hwnd = getattr(fd, "game_hwnd", None)
            if not hwnd:
                hwnd = _platform.find_window_by_title_prefix(GAME_TITLE_PREFIX)
            if not hwnd:
                return None
            capturer = getattr(fd, "capturer", None)
            if capturer is None:
                return None
            geo = _platform.get_window_geometry(hwnd)
            return capturer.capture_window(hwnd, geometry=geo)
        except Exception as e:
            log.debug("Direct capture failed: %s", e)
            return None

    # --- Save / Cancel ---

    def _save(self):
        cfg = self._config

        # Video output settings
        cfg.clip_resolution = self._resolution_combo.currentData() or "source"
        cfg.clip_fps = self._fps_combo.currentData() or 30
        cfg.clip_bitrate = self._bitrate_combo.currentData() or "medium"
        cfg.clip_capture_backend = self._backend_combo.currentData() or "auto"
        cfg.clip_scaling = self._scaling_combo.currentData() or "lanczos"

        # Webcam
        cfg.clip_webcam_enabled = self._webcam_cb.isChecked()
        cfg.clip_webcam_keep_ready = self._webcam_keep_ready_cb.isChecked()
        cfg.clip_webcam_scale = self._preview.webcam_scale
        wx, wy = self._preview.webcam_position
        cfg.clip_webcam_position_x = wx
        cfg.clip_webcam_position_y = wy

        # Webcam device & FPS
        dev_data = self._webcam_device_combo.currentData()
        if dev_data is not None and dev_data != -1:
            cfg.clip_webcam_device = dev_data
        webcam_fps = self._webcam_fps_combo.currentData()
        cfg.clip_webcam_fps = webcam_fps if webcam_fps else 0  # 0 = auto

        # Webcam crop
        crop = self._preview.webcam_crop
        cfg.clip_webcam_crop_x = crop["x"]
        cfg.clip_webcam_crop_y = crop["y"]
        cfg.clip_webcam_crop_w = crop["w"]
        cfg.clip_webcam_crop_h = crop["h"]

        # Chroma key
        cfg.clip_webcam_chroma_enabled = self._chroma_cb.isChecked()
        cfg.clip_webcam_chroma_color = self._chroma_color
        cfg.clip_webcam_chroma_threshold = self._chroma_threshold.value()
        cfg.clip_webcam_chroma_smoothing = self._chroma_smoothing.value()

        # Blur regions
        cfg.capture_blur_regions = self._preview.regions

        # Background
        cfg.capture_preview_background = self._bg_path

        save_config(cfg, self._config_path)
        self._event_bus.publish(EVENT_CONFIG_CHANGED, cfg)
        self.accept()

    def closeEvent(self, event):
        self._cleanup()
        super().closeEvent(event)

    def reject(self):
        self._cleanup()
        super().reject()

    def _cleanup(self):
        self._bg_timer.stop()
        self._count_timer.stop()
        self._stop_webcam_preview()
        self._unboost_distributor()
        if self._bg_video_cap is not None:
            self._bg_video_cap.release()
            self._bg_video_cap = None
