"""Blur region editor — draw rectangles on a game preview to define privacy regions.

Supports live video feed (when clip recording is active), static screenshot
with manual refresh, and a configurable background image/video that fills
the canvas when no game frame is available.
"""

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget,
    QFileDialog,
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
from ...capture.constants import RESOLUTION_PRESETS
from ..theme import ACCENT, TEXT_MUTED

log = get_logger("BlurRegionDialog")

# Default aspect ratio when no game window or resolution is configured
_DEFAULT_ASPECT = 16 / 9


class _PreviewWidget(QWidget):
    """Widget that displays a game frame preview and allows drawing blur rectangles.

    The canvas aspect ratio matches the game window (or configured resolution).
    When no game frame is available, a configured background image/video is
    stretched to fill, or solid black is shown.
    """

    def __init__(self, aspect_ratio: float = _DEFAULT_ASPECT, parent=None):
        super().__init__(parent)
        self._aspect = aspect_ratio
        self._pixmap: QPixmap | None = None
        self._bg_pixmap: QPixmap | None = None  # background image/video frame
        self._regions: list[dict] = []  # [{x, y, w, h}] normalized 0.0-1.0
        self._drawing = False
        self._draw_start: QPoint | None = None
        self._draw_current: QPoint | None = None
        self.setMinimumSize(640, int(640 / self._aspect))
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_aspect_ratio(self, ratio: float) -> None:
        self._aspect = max(0.5, min(4.0, ratio))
        self.setMinimumSize(640, int(640 / self._aspect))
        self.update()

    def set_frame(self, frame_bgr: np.ndarray) -> None:
        """Update the preview with a new BGR game frame."""
        if cv2 is None:
            return
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self.update()

    def set_background(self, pixmap: QPixmap | None) -> None:
        """Set the background pixmap (stretched to fill when no game frame)."""
        self._bg_pixmap = pixmap
        self.update()

    @property
    def regions(self) -> list[dict]:
        return self._regions

    @regions.setter
    def regions(self, value: list[dict]):
        self._regions = list(value)
        self.update()

    def _display_rect(self) -> QRect:
        """Compute the canvas rect that maintains the target aspect ratio."""
        ww, wh = self.width(), self.height()
        scale = min(ww / self._aspect, wh)
        dw = int(scale * self._aspect)
        dh = int(scale)
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
                # Clamp so region stays within capture area
                rw = min(rw, 1.0 - rx)
                rh = min(rh, 1.0 - ry)
                if rw > 0.01 and rh > 0.01:  # Minimum size threshold
                    self._regions.append({"x": rx, "y": ry, "w": rw, "h": rh})
            self._draw_start = None
            self._draw_current = None
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background (full widget)
        painter.fillRect(self.rect(), QColor("#111111"))

        dr = self._display_rect()

        # Canvas content: game frame > background > black
        if self._pixmap:
            painter.drawPixmap(dr, self._pixmap)
        elif self._bg_pixmap:
            # Stretch background to fill the canvas
            painter.drawPixmap(dr, self._bg_pixmap)
        else:
            painter.fillRect(dr, QColor("#1a1a1a"))

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
    """Dialog for configuring blur/privacy regions on the game capture.

    When clip recording is enabled, shows a live ~2fps video feed.
    Otherwise shows a static screenshot with a Refresh button.
    Supports a configurable background image/video file.
    """

    def __init__(self, *, config, config_path, event_bus, parent=None):
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._event_bus = event_bus
        self._bg_video_cap = None  # cv2.VideoCapture for background video

        self.setWindowTitle("Configure Blur Regions")
        self.setMinimumSize(800, 520)
        self.resize(900, 600)

        layout = QVBoxLayout(self)

        # Instructions
        desc = QLabel(
            "Draw rectangles on the preview to define regions that will be blurred "
            "in both screenshots and video clips. Right-click a region to delete it."
        )
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Preview widget — aspect ratio from game window or configured resolution
        aspect = self._detect_aspect_ratio()
        self._preview = _PreviewWidget(aspect_ratio=aspect)
        self._preview.regions = list(config.capture_blur_regions)
        layout.addWidget(self._preview, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_regions)
        btn_row.addWidget(clear_btn)

        # Refresh button (visible only in static/screenshot mode)
        self._refresh_btn = QPushButton("Refresh Screenshot")
        self._refresh_btn.setToolTip("Capture a new screenshot from the game window")
        self._refresh_btn.clicked.connect(self._refresh_preview)
        btn_row.addWidget(self._refresh_btn)

        # Background file selector
        bg_btn = QPushButton("Set Background...")
        bg_btn.setToolTip(
            "Choose an image or video file to display when the game\n"
            "window is not available. The file will be stretched to fit."
        )
        bg_btn.clicked.connect(self._browse_background)
        btn_row.addWidget(bg_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("accentButton")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        # Frame source
        self._frame_distributor = None
        self._live_mode = config.clip_enabled
        self._refresh_btn.setVisible(not self._live_mode)

        # Live preview refresh timer (~2fps when live, background video at ~15fps)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_tick)
        if self._live_mode:
            self._refresh_timer.setInterval(500)
            self._refresh_timer.start()

        # Load background if configured
        self._load_background(config.capture_preview_background)

        # Get initial frame
        self._refresh_preview()

    def _detect_aspect_ratio(self) -> float:
        """Determine the preview aspect ratio from game window or config."""
        # Try the frame distributor's game window first
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

        # Fall back to configured resolution
        res = RESOLUTION_PRESETS.get(self._config.clip_resolution)
        if res:
            return res[0] / res[1]

        return _DEFAULT_ASPECT

    def _load_background(self, path: str) -> None:
        """Load a background image or video from the given path."""
        # Clean up previous video capture
        if self._bg_video_cap is not None:
            self._bg_video_cap.release()
            self._bg_video_cap = None

        if not path or not Path(path).is_file():
            self._preview.set_background(None)
            return

        if cv2 is None:
            return

        # Try as video first
        ext = Path(path).suffix.lower()
        video_exts = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv", ".flv"}
        if ext in video_exts:
            cap = cv2.VideoCapture(path)
            if cap.isOpened():
                self._bg_video_cap = cap
                # Read first frame as initial background
                self._advance_bg_video()
                # Start timer for video playback if not already live
                if not self._live_mode:
                    self._refresh_timer.setInterval(66)  # ~15fps
                    self._refresh_timer.start()
                return
            cap.release()

        # Try as image
        img = cv2.imread(path)
        if img is not None:
            h, w = img.shape[:2]
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
            self._preview.set_background(QPixmap.fromImage(qimg))

    def _advance_bg_video(self) -> None:
        """Read the next frame from the background video, looping at end."""
        if self._bg_video_cap is None or cv2 is None:
            return
        ok, frame = self._bg_video_cap.read()
        if not ok:
            # Loop back to start
            self._bg_video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._bg_video_cap.read()
            if not ok:
                return
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self._preview.set_background(QPixmap.fromImage(qimg))

    def _on_tick(self) -> None:
        """Timer tick: refresh game frame and/or advance background video."""
        if self._live_mode:
            self._refresh_preview()
        if self._bg_video_cap is not None:
            self._advance_bg_video()
            # Only repaint if we don't have a game frame covering the canvas
            if self._preview._pixmap is None:
                self._preview.update()

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
        if frame is None:
            frame = self._direct_capture(fd)
        if frame is not None:
            self._preview.set_frame(frame)
            # Update aspect ratio from actual frame
            h, w = frame.shape[:2]
            if w > 0 and h > 0:
                self._preview.set_aspect_ratio(w / h)

    def _direct_capture(self, fd):
        """Capture a single frame directly from the game window."""
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

    def _browse_background(self):
        """Let the user pick a background image or video file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Image or Video",
            self._config.capture_preview_background or "",
            "Media files (*.png *.jpg *.jpeg *.bmp *.mp4 *.avi *.mkv *.mov *.webm *.wmv *.flv);;"
            "Images (*.png *.jpg *.jpeg *.bmp);;"
            "Videos (*.mp4 *.avi *.mkv *.mov *.webm *.wmv *.flv);;"
            "All files (*)",
        )
        if path:
            self._config.capture_preview_background = path
            self._load_background(path)

    def _clear_regions(self):
        self._preview.regions = []

    def _save(self):
        self._config.capture_blur_regions = self._preview.regions
        save_config(self._config, self._config_path)
        self._event_bus.publish(EVENT_CONFIG_CHANGED, self._config)
        self.accept()

    def closeEvent(self, event):
        self._cleanup()
        super().closeEvent(event)

    def reject(self):
        self._cleanup()
        super().reject()

    def _cleanup(self):
        """Release resources."""
        self._refresh_timer.stop()
        if self._bg_video_cap is not None:
            self._bg_video_cap.release()
            self._bg_video_cap = None
