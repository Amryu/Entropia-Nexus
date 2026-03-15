"""Radar calibration dialog — place bounding box, circle, and coordinate ROIs.

The user configures four elements on a game screenshot:
  1. **Radar bounding box** — rectangle enclosing the full radar HUD (drag).
  2. **Circle** — center + radius of the radar circle (click center, Shift+scroll radius).
  3. **Lon ROI** — rectangle covering the longitude digit area (drag).
  4. **Lat ROI** — rectangle covering the latitude digit area (drag).

All positions are stored relative to the circle centre at 1x UI scale so
they can be re-applied at any scale by multiplying by ``(r / base_radius)``.
"""

from __future__ import annotations

import enum

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget,
    QSpinBox, QGridLayout,
)
from PyQt6.QtCore import Qt, QRect, QPoint, QPointF, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QPixmap, QImage, QFont

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ...core.config import save_config
from ...core.constants import EVENT_CONFIG_CHANGED
from ...core.logger import get_logger
from ..theme import ACCENT, TEXT_MUTED, BORDER

log = get_logger("RadarCalibrationDialog")

from ...ocr.radar_detector import BASE_RADAR_RADIUS_PX

_DEFAULT_ASPECT = 16 / 9

# Zoom limits
_ZOOM_MIN = 1.0
_ZOOM_MAX = 12.0
_ZOOM_STEP = 1.15

# Overlay colours
_BOX_COLOR = QColor(80, 220, 80, 140)          # green dashed
_CIRCLE_COLOR = QColor(255, 165, 0, 180)       # orange
_LON_COLOR = QColor(0, 220, 255, 180)          # cyan
_LAT_COLOR = QColor(255, 100, 255, 180)        # magenta
_ACTIVE_BTN = f"background-color: {ACCENT}; color: #000; font-weight: bold;"


class _CircleDetectWorker(QThread):
    """Runs HoughCircles detection off the main thread."""

    finished = pyqtSignal(object)  # tuple[int,int,int] | None

    def __init__(self, frame_bgr: np.ndarray, parent=None):
        super().__init__(parent)
        self._frame = frame_bgr

    def run(self):
        circle = None
        try:
            from ...ocr.radar_detector import RadarDetector

            class _Cfg:
                radar_enabled = True
                radar_last_circle = None
                radar_base_radius = None
                radar_box_roi = None
                radar_lon_roi = None
                radar_lat_roi = None

            class _Bus:
                def subscribe(self, *a, **kw): pass
                def publish(self, *a, **kw): pass

            det = RadarDetector(_Cfg(), _Bus(), None)
            circle = det._find_radar_circle(self._frame)
        except Exception:
            pass
        self.finished.emit(circle)


class _Mode(enum.Enum):
    RADAR_BOX = "radar_box"
    CIRCLE = "circle"
    LON_ROI = "lon_roi"
    LAT_ROI = "lat_roi"


class _RadarPreviewWidget(QWidget):
    """Canvas with interactive radar calibration overlays.

    Supports scroll-wheel zoom, middle-click pan, and four editing modes.
    """

    circle_changed = pyqtSignal()  # emitted when circle cx/cy/r changes
    rects_changed = pyqtSignal()  # emitted when any rect is drawn/modified

    def __init__(self, aspect_ratio: float = _DEFAULT_ASPECT, parent=None):
        super().__init__(parent)
        self._aspect = aspect_ratio
        self._pixmap: QPixmap | None = None
        self._frame_w: int = 0
        self._frame_h: int = 0

        self.mode: _Mode = _Mode.RADAR_BOX

        # Calibration state (frame pixel coords)
        self.radar_box: QRect | None = None
        self.circle: tuple[int, int, int] | None = None   # (cx, cy, r)
        self.lon_rect: QRect | None = None
        self.lat_rect: QRect | None = None

        self.scale: float = 1.0

        # Drawing state
        self._drawing = False
        self._draw_start: QPoint | None = None
        self._draw_current: QPoint | None = None

        # Zoom / pan
        self._zoom: float = 1.0
        self._pan: QPointF = QPointF(0.0, 0.0)
        self._panning = False
        self._pan_last: QPoint | None = None

        self.setMinimumSize(640, int(640 / self._aspect))
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_aspect_ratio(self, ratio: float) -> None:
        self._aspect = max(0.5, min(4.0, ratio))
        self.setMinimumSize(640, int(640 / self._aspect))
        self.update()

    def set_frame_pixmap(self, frame_bgr: np.ndarray) -> None:
        if cv2 is None:
            return
        h, w = frame_bgr.shape[:2]
        self._frame_w, self._frame_h = w, h
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg.copy())
        self.update()

    def set_circle_val(self, circle: tuple[int, int, int] | None, base_radius: int = BASE_RADAR_RADIUS_PX) -> None:
        self.circle = circle
        if circle:
            self.scale = circle[2] / base_radius
        self.circle_changed.emit()
        self.update()

    def adjust_radius(self, delta: int, base_radius: int) -> None:
        """Adjust circle radius by *delta* pixels."""
        if self.circle is None:
            return
        cx, cy, r = self.circle
        r = max(20, r + delta)
        self.circle = (cx, cy, r)
        self.scale = r / base_radius
        self.circle_changed.emit()
        self.update()

    # ----- coordinate conversion (zoom-aware) -----

    def _base_display_rect(self) -> QRect:
        ww, wh = self.width(), self.height()
        s = min(ww / self._aspect, wh)
        dw, dh = int(s * self._aspect), int(s)
        return QRect((ww - dw) // 2, (wh - dh) // 2, dw, dh)

    def _zoomed_display_rect(self) -> QRect:
        base = self._base_display_rect()
        cx = base.x() + base.width() / 2 + self._pan.x()
        cy = base.y() + base.height() / 2 + self._pan.y()
        zw = base.width() * self._zoom
        zh = base.height() * self._zoom
        return QRect(int(cx - zw / 2), int(cy - zh / 2), int(zw), int(zh))

    def _widget_to_frame(self, pos: QPoint) -> QPoint:
        dr = self._zoomed_display_rect()
        if self._frame_w == 0 or self._frame_h == 0:
            return QPoint(0, 0)
        fx = round((pos.x() - dr.x()) / max(1, dr.width()) * self._frame_w)
        fy = round((pos.y() - dr.y()) / max(1, dr.height()) * self._frame_h)
        return QPoint(max(0, min(self._frame_w, fx)), max(0, min(self._frame_h, fy)))

    def _frame_to_widget(self, fp: QPoint) -> QPoint:
        dr = self._zoomed_display_rect()
        if self._frame_w == 0 or self._frame_h == 0:
            return QPoint(0, 0)
        wx = dr.x() + round(fp.x() / max(1, self._frame_w) * dr.width())
        wy = dr.y() + round(fp.y() / max(1, self._frame_h) * dr.height())
        return QPoint(wx, wy)

    def _frame_rect_to_widget(self, fr: QRect) -> QRect:
        tl = self._frame_to_widget(fr.topLeft())
        br = self._frame_to_widget(fr.bottomRight())
        return QRect(tl, br)

    def _frame_radius_to_widget(self, r: int) -> int:
        dr = self._zoomed_display_rect()
        return round(r / max(1, self._frame_w) * dr.width())

    # ----- mouse events -----

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_last = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.mode == _Mode.CIRCLE:
            # Click sets circle center (keeps current radius or defaults to 94)
            fp = self._widget_to_frame(event.pos())
            r = self.circle[2] if self.circle else BASE_RADAR_RADIUS_PX
            self.circle = (fp.x(), fp.y(), r)
            self.circle_changed.emit()
            self.update()
        else:
            # All rect modes: drag to draw
            self._drawing = True
            self._draw_start = event.pos()
            self._draw_current = event.pos()

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_last is not None:
            delta = event.pos() - self._pan_last
            self._pan += QPointF(delta.x(), delta.y())
            self._pan_last = event.pos()
            self.update()
            return
        if self._drawing:
            self._draw_current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self._pan_last = None
            self.setCursor(Qt.CursorShape.CrossCursor)
            return
        if event.button() != Qt.MouseButton.LeftButton or not self._drawing:
            return
        self._drawing = False
        if self._draw_start and self._draw_current:
            fp1 = self._widget_to_frame(self._draw_start)
            fp2 = self._widget_to_frame(self._draw_current)
            rect = QRect(fp1, fp2).normalized()
            if rect.width() > 2 and rect.height() > 2:
                if self.mode == _Mode.RADAR_BOX:
                    self.radar_box = rect
                elif self.mode == _Mode.LON_ROI:
                    self.lon_rect = rect
                elif self.mode == _Mode.LAT_ROI:
                    self.lat_rect = rect
        self._draw_start = None
        self._draw_current = None
        self.rects_changed.emit()
        self.update()

    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        if angle == 0:
            return

        # Shift+scroll adjusts circle radius
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if self.circle:
                delta = 1 if angle > 0 else -1
                # emit via parent dialog so base_radius is known
                self.adjust_radius(delta, BASE_RADAR_RADIUS_PX)
            return

        # Normal scroll: zoom
        old_zoom = self._zoom
        if angle > 0:
            self._zoom = min(_ZOOM_MAX, self._zoom * _ZOOM_STEP)
        else:
            self._zoom = max(_ZOOM_MIN, self._zoom / _ZOOM_STEP)
        if self._zoom == old_zoom:
            return

        cursor = event.position()
        factor = self._zoom / old_zoom
        bc = self._base_display_rect().center()
        self._pan = QPointF(
            cursor.x() + factor * (self._pan.x() + bc.x() - cursor.x()) - bc.x(),
            cursor.y() + factor * (self._pan.y() + bc.y() - cursor.y()) - bc.y(),
        )
        self.update()

    # ----- paint -----

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#111111"))

        dr = self._zoomed_display_rect()

        if self._pixmap:
            painter.drawPixmap(dr, self._pixmap)
        else:
            painter.fillRect(dr, QColor("#1a1a1a"))

        # 1. Radar bounding box (behind everything)
        if self.radar_box:
            wr = self._frame_rect_to_widget(self.radar_box)
            painter.setPen(QPen(_BOX_COLOR, 1, Qt.PenStyle.DashLine))
            painter.setBrush(QColor(_BOX_COLOR.red(), _BOX_COLOR.green(), _BOX_COLOR.blue(), 12))
            painter.drawRect(wr)
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(_BOX_COLOR)
            painter.drawText(wr.x() + 4, wr.y() - 4, "Radar")

        # 2. Circle
        if self.circle:
            cx, cy, r = self.circle
            cp = self._frame_to_widget(QPoint(cx, cy))
            wr = self._frame_radius_to_widget(r)
            painter.setPen(QPen(_CIRCLE_COLOR, 2))
            painter.setBrush(QColor(255, 165, 0, 18))
            painter.drawEllipse(cp, wr, wr)
            # Center dot
            painter.setBrush(_CIRCLE_COLOR)
            painter.drawEllipse(cp, 3, 3)

        # 3. Lon ROI
        if self.lon_rect:
            self._draw_roi(painter, self.lon_rect, _LON_COLOR, "Lon")

        # 4. Lat ROI
        if self.lat_rect:
            self._draw_roi(painter, self.lat_rect, _LAT_COLOR, "Lat")

        # Current drawing rect
        if self._drawing and self._draw_start and self._draw_current:
            color = {
                _Mode.RADAR_BOX: _BOX_COLOR,
                _Mode.LON_ROI: _LON_COLOR,
                _Mode.LAT_ROI: _LAT_COLOR,
            }.get(self.mode, _BOX_COLOR)
            painter.setPen(QPen(color, 2, Qt.PenStyle.DashLine))
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 30))
            rect = QRect(self._draw_start, self._draw_current).normalized()
            painter.drawRect(rect)

        # Zoom indicator
        if self._zoom != 1.0:
            painter.setPen(QPen(QColor(200, 200, 200, 180)))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(10, self.height() - 10, f"{self._zoom:.1f}x")

        painter.end()

    def _draw_roi(self, painter: QPainter, frame_rect: QRect, color: QColor, label: str):
        wr = self._frame_rect_to_widget(frame_rect)
        painter.setPen(QPen(color, 2))
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 30))
        painter.drawRect(wr)
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(wr.x() + 4, wr.y() - 4, label)


# -----------------------------------------------------------------------
# Dialog
# -----------------------------------------------------------------------

class RadarCalibrationDialog(QDialog):
    """Dialog for configuring radar circle, bounding box, and coordinate ROIs."""

    def __init__(self, *, config, config_path, event_bus, parent=None):
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._event_bus = event_bus
        self._frame_distributor = None
        self._detect_worker: _CircleDetectWorker | None = None

        self.setWindowTitle("Radar Calibration")
        self.setMinimumSize(900, 650)
        self.resize(1000, 700)

        layout = QVBoxLayout(self)

        # Instructions
        desc = QLabel(
            "Draw the radar bounding box, adjust the circle, then draw Lon/Lat "
            "digit ROIs. Scroll to zoom, middle-click to pan.\n"
            "Circle mode: click to place center, Shift+scroll to adjust radius."
        )
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Mode buttons + inline spinboxes for the active mode
        self._spins: dict[str, QSpinBox] = {}
        self._syncing_spins = False
        self._mode_btns: dict[_Mode, QPushButton] = {}
        self._spin_rows: dict[_Mode, QWidget] = {}

        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        _mode_defs = [
            (_Mode.RADAR_BOX, "Radar Box", [("x", "box_x"), ("y", "box_y"), ("w", "box_w"), ("h", "box_h")]),
            (_Mode.CIRCLE,    "Circle",    [("cx", "cir_cx"), ("cy", "cir_cy"), ("r", "cir_r")]),
            (_Mode.LON_ROI,   "Lon ROI",   [("x", "lon_x"), ("y", "lon_y"), ("w", "lon_w"), ("h", "lon_h")]),
            (_Mode.LAT_ROI,   "Lat ROI",   [("x", "lat_x"), ("y", "lat_y"), ("w", "lat_w"), ("h", "lat_h")]),
        ]

        for mode, label, fields in _mode_defs:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, m=mode: self._set_mode(m))
            toolbar.addWidget(btn)
            self._mode_btns[mode] = btn

        toolbar.addSpacing(8)

        # Build one QWidget per mode holding its spinboxes; only one visible at a time
        for mode, _label, fields in _mode_defs:
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(4)
            for field_label, key in fields:
                fl = QLabel(field_label)
                fl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
                row_l.addWidget(fl)
                spin = QSpinBox()
                spin.setRange(-2048, 4096)
                spin.setFixedWidth(56)
                spin.setStyleSheet("font-size: 10px;")
                spin.valueChanged.connect(self._on_spin_changed)
                row_l.addWidget(spin)
                self._spins[key] = spin
            row_w.setVisible(False)
            toolbar.addWidget(row_w)
            self._spin_rows[mode] = row_w

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Preview
        aspect = self._detect_aspect_ratio()
        self._preview = _RadarPreviewWidget(aspect_ratio=aspect)
        self._preview.circle_changed.connect(self._on_circle_changed)
        self._preview.rects_changed.connect(self._on_rects_changed)
        layout.addWidget(self._preview, stretch=1)

        # Status line
        self._status = QLabel("Load a screenshot to begin.")
        self._status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        layout.addWidget(self._status)

        # Bottom buttons
        btn_row = QHBoxLayout()

        refresh_btn = QPushButton("Refresh Screenshot")
        refresh_btn.setToolTip("Capture a new screenshot from the game window")
        refresh_btn.clicked.connect(self._refresh_preview)
        btn_row.addWidget(refresh_btn)

        auto_btn = QPushButton("Auto-Detect ROIs")
        auto_btn.setToolTip("Compute default ROI positions from the current circle")
        auto_btn.clicked.connect(self._auto_detect)
        btn_row.addWidget(auto_btn)

        self._scale_btn = QPushButton("Set as 1.00x")
        self._scale_btn.setToolTip(
            "Define the current circle radius as the 1.00x reference.\n"
            "Use when the game is at 100% UI scale."
        )
        self._scale_btn.clicked.connect(self._calibrate_scale)
        btn_row.addWidget(self._scale_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("accentButton")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        # Initial state
        self._set_mode(_Mode.RADAR_BOX)
        self._load_existing()
        QTimer.singleShot(0, self._refresh_preview)

    # ----- Mode management -----

    def _set_mode(self, mode: _Mode):
        self._preview.mode = mode
        for m, btn in self._mode_btns.items():
            btn.setChecked(m == mode)
            btn.setStyleSheet(_ACTIVE_BTN if m == mode else "")
        for m, row in self._spin_rows.items():
            row.setVisible(m == mode)

    def _on_circle_changed(self):
        """Circle changed — update circle spins and rescale rects.

        Only sync the circle spinboxes (cx/cy/r).  Do NOT re-read rect
        spinboxes from the preview — those frame-pixel rects are stale
        (from the old scale).  Instead, push the unchanged 1x spinbox
        values back at the new scale.
        """
        if self._syncing_spins:
            return
        self._syncing_spins = True
        p = self._preview
        if p.circle:
            for key, val in [("cir_cx", p.circle[0]), ("cir_cy", p.circle[1]), ("cir_r", p.circle[2])]:
                s = self._spins.get(key)
                if s and s.value() != val:
                    s.setValue(val)
        self._syncing_spins = False
        self._push_rects_from_spins()
        self._update_status()

    def _on_rects_changed(self):
        """A rect was drawn/modified on the canvas — update spinboxes."""
        self._sync_spins_from_preview()

    # ----- Spinbox ↔ preview sync -----

    def _sync_spins_from_preview(self):
        """Push current preview state into the spinboxes.

        Circle: absolute frame coords (cx, cy, r).
        All rects: (x, y, w, h) relative to circle center, at 1x scale.
        """
        if self._syncing_spins:
            return
        self._syncing_spins = True
        p = self._preview

        def _set(key: str, val: int):
            s = self._spins.get(key)
            if s and s.value() != val:
                s.setValue(val)

        if p.circle:
            cx, cy, r = p.circle
            scale = r / self._base_radius
            _set("cir_cx", cx)
            _set("cir_cy", cy)
            _set("cir_r", r)

            def _set_rect(prefix: str, rect: QRect | None):
                if rect is None:
                    return
                _set(f"{prefix}_x", round((rect.x() - cx) / scale))
                _set(f"{prefix}_y", round((rect.y() - cy) / scale))
                _set(f"{prefix}_w", round(rect.width() / scale))
                _set(f"{prefix}_h", round(rect.height() / scale))

            _set_rect("box", p.radar_box)
            _set_rect("lon", p.lon_rect)
            _set_rect("lat", p.lat_rect)

        self._syncing_spins = False

    def _push_rects_from_spins(self):
        """Recompute preview frame-pixel rects from the 1x spinbox values."""
        p = self._preview
        if not p.circle:
            return
        cx, cy, r = p.circle
        scale = r / self._base_radius
        sp = self._spins

        def _read_rect(prefix: str) -> QRect | None:
            w = round(sp[f"{prefix}_w"].value() * scale)
            h = round(sp[f"{prefix}_h"].value() * scale)
            if w <= 0 or h <= 0:
                return None
            x = cx + round(sp[f"{prefix}_x"].value() * scale)
            y = cy + round(sp[f"{prefix}_y"].value() * scale)
            return QRect(x, y, w, h)

        p.radar_box = _read_rect("box") or p.radar_box
        p.lon_rect = _read_rect("lon") or p.lon_rect
        p.lat_rect = _read_rect("lat") or p.lat_rect
        p.update()

    def _on_spin_changed(self, _value: int):
        """Any spinbox changed — push values back into the preview."""
        if self._syncing_spins:
            return
        self._syncing_spins = True

        # Circle is always absolute
        sp = self._spins
        p = self._preview
        if sp["cir_r"].value() > 0:
            p.circle = (sp["cir_cx"].value(), sp["cir_cy"].value(), sp["cir_r"].value())
            p.scale = p.circle[2] / self._base_radius

        self._push_rects_from_spins()

        self._syncing_spins = False
        self._update_status()

    # ----- Frame acquisition -----

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
        return _DEFAULT_ASPECT

    def _get_frame_distributor(self):
        if self._frame_distributor is not None:
            return self._frame_distributor
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            for widget in app.topLevelWidgets():
                fd = getattr(widget, "_frame_distributor", None)
                if fd is not None:
                    self._frame_distributor = fd
                    return fd
        except Exception:
            pass
        return None

    def _refresh_preview(self):
        fd = self._get_frame_distributor()
        if fd is None:
            return
        frame = fd.get_latest_frame()
        if frame is None:
            frame = self._direct_capture(fd)
        if frame is not None:
            h, w = frame.shape[:2]
            if w > 0 and h > 0:
                self._preview.set_aspect_ratio(w / h)
            self._preview.set_frame_pixmap(frame)
            self._status.setText("Detecting radar circle...")
            if self._detect_worker is not None:
                self._detect_worker.finished.disconnect()
                self._detect_worker.wait()
            self._detect_worker = _CircleDetectWorker(frame, parent=self)
            self._detect_worker.finished.connect(self._on_circle_detected)
            self._detect_worker.start()

    def _on_circle_detected(self, circle):
        self._preview.set_circle_val(circle, self._base_radius)
        # Rescale all rects at the newly detected circle's scale
        self._push_rects_from_spins()
        self._update_status()

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
        except Exception:
            return None

    # ----- Auto-detect -----

    def _auto_detect(self):
        circle = self._preview.circle
        if circle is None:
            self._status.setText("No circle detected — capture a screenshot first.")
            return

        from ...ocr.radar_detector import (
            TEXT_LON_OFFSET_RATIO, TEXT_STRIDE_RATIO,
            TEXT_LEFT_RATIO, TEXT_WIDTH_RATIO, TEXT_HEIGHT_RATIO,
            DIGIT_STRIDE_RATIO, COORD_MAX_DIGITS,
            RADAR_TEXT_EXTRA_ROW_PAD_PX,
        )

        cx, cy, r = circle
        scale = r / self._base_radius

        # Radar bounding box: circle center ± radius with some padding
        pad = round(4 * scale)
        self._preview.radar_box = QRect(
            cx - r - pad, cy - r - pad,
            2 * r + 2 * pad, 2 * r + 2 * pad,
        )

        # Coordinate ROIs (right-aligned digits)
        row_pad = max(1, round(RADAR_TEXT_EXTRA_ROW_PAD_PX * scale))
        text_right = cx + round((TEXT_LEFT_RATIO + TEXT_WIDTH_RATIO) * r) + 2
        digit_w = max(1, round(DIGIT_STRIDE_RATIO * r))
        text_left = text_right - COORD_MAX_DIGITS * digit_w - 2
        row_h = max(5, round(TEXT_HEIGHT_RATIO * r) + row_pad * 2)

        lon_top = cy + round(TEXT_LON_OFFSET_RATIO * r) - row_pad
        lat_top = cy + round((TEXT_LON_OFFSET_RATIO + TEXT_STRIDE_RATIO) * r) - row_pad
        roi_w = text_right - text_left

        self._preview.lon_rect = QRect(text_left, lon_top, roi_w, row_h)
        self._preview.lat_rect = QRect(text_left, lat_top, roi_w, row_h)
        self._preview.update()
        self._update_status()

    # ----- Scale calibration -----

    @property
    def _base_radius(self) -> int:
        return getattr(self._config, "radar_base_radius", None) or BASE_RADAR_RADIUS_PX

    def _calibrate_scale(self):
        circle = self._preview.circle
        if circle is None:
            self._status.setText("No circle detected — cannot calibrate scale.")
            return
        _, _, r = circle
        self._config.radar_base_radius = r
        self._preview.scale = 1.0
        self._update_status()

    # ----- Load / Save -----

    def _load_existing(self):
        self._saved_box_roi = getattr(self._config, "radar_box_roi", None)
        self._saved_lon_roi = getattr(self._config, "radar_lon_roi", None)
        self._saved_lat_roi = getattr(self._config, "radar_lat_roi", None)

    def _apply_saved_to_preview(self):
        """Project saved 1x-scale config values onto the current frame.

        All stored ROIs are (x, y, w, h) relative to circle center at 1x.
        After setting the rects, syncs the spinboxes so subsequent circle
        changes can rescale correctly via ``_push_rects_from_spins``.
        """
        circle = self._preview.circle
        if circle is None:
            return
        cx, cy, r = circle
        scale = r / self._base_radius
        applied = False

        if self._saved_box_roi and self._preview.radar_box is None:
            bx, by, bw, bh = self._saved_box_roi
            self._preview.radar_box = QRect(
                cx + round(bx * scale), cy + round(by * scale),
                round(bw * scale), round(bh * scale),
            )
            applied = True

        if self._saved_lon_roi and self._preview.lon_rect is None:
            lx, ly, lw, lh = self._saved_lon_roi
            self._preview.lon_rect = QRect(
                cx + round(lx * scale), cy + round(ly * scale),
                round(lw * scale), round(lh * scale),
            )
            applied = True

        if self._saved_lat_roi and self._preview.lat_rect is None:
            ax, ay, aw, ah = self._saved_lat_roi
            self._preview.lat_rect = QRect(
                cx + round(ax * scale), cy + round(ay * scale),
                round(aw * scale), round(ah * scale),
            )
            applied = True

        if applied:
            # Populate spinboxes with the 1x values so _push_rects_from_spins
            # works correctly on subsequent circle changes.
            self._sync_spins_from_preview()

        self._preview.update()

    def _update_status(self):
        circle = self._preview.circle
        if circle:
            cx, cy, r = circle
            self._status.setText(
                f"Circle: ({cx}, {cy}) r={r}   Scale: {self._preview.scale:.2f}x"
            )
            self._apply_saved_to_preview()
        else:
            self._status.setText("No circle detected. Try refreshing or adjusting the game window.")

    def _save(self):
        preview = self._preview
        circle = preview.circle
        if circle is None:
            self._status.setText("Cannot save without a circle.")
            return
        if preview.lon_rect is None or preview.lat_rect is None:
            self._status.setText("Please draw both Lon and Lat ROIs.")
            return

        cx, cy, r = circle
        scale = r / self._base_radius

        # All ROIs stored as (x, y, w, h) relative to circle center at 1x.
        if preview.radar_box:
            rb = preview.radar_box
            self._config.radar_box_roi = (
                round((rb.x() - cx) / scale),
                round((rb.y() - cy) / scale),
                round(rb.width() / scale),
                round(rb.height() / scale),
            )

        lr = preview.lon_rect
        self._config.radar_lon_roi = (
            round((lr.x() - cx) / scale),
            round((lr.y() - cy) / scale),
            round(lr.width() / scale),
            round(lr.height() / scale),
        )

        ar = preview.lat_rect
        self._config.radar_lat_roi = (
            round((ar.x() - cx) / scale),
            round((ar.y() - cy) / scale),
            round(ar.width() / scale),
            round(ar.height() / scale),
        )

        save_config(self._config, self._config_path)
        self._event_bus.publish(EVENT_CONFIG_CHANGED, self._config)
        log.info(
            "Radar calibration saved: box=%s lon=%s lat=%s base_r=%s",
            self._config.radar_box_roi,
            self._config.radar_lon_roi,
            self._config.radar_lat_roi,
            getattr(self._config, "radar_base_radius", None),
        )
        self.accept()
