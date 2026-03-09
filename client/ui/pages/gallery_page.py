"""Gallery page — browse screenshots and video clips with playback."""

import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QGridLayout, QComboBox, QFrame, QMenu, QDialog, QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QPixmap, QImage, QAction

try:
    import cv2
except ImportError:
    cv2 = None

from ...capture.constants import DEFAULT_CLIP_DIR, DEFAULT_SCREENSHOT_DIR
from ...core.logger import get_logger
from ..theme import TEXT_MUTED, BORDER, ACCENT, SECONDARY, PRIMARY

log = get_logger("Gallery")

THUMB_WIDTH = 200
THUMB_HEIGHT = 130
THUMB_COLS = 4


class _ThumbnailLoader(QThread):
    """Background thread that scans directories and generates thumbnails."""
    loaded = pyqtSignal(list)  # list of {path, pixmap, type, mtime}

    def __init__(self, screenshot_dir: str, clip_dir: str, filter_type: str):
        super().__init__()
        self._screenshot_dir = screenshot_dir
        self._clip_dir = clip_dir
        self._filter_type = filter_type

    def run(self):
        items = []
        # Scan screenshots
        if self._filter_type in ("all", "screenshots"):
            items.extend(self._scan_dir(self._screenshot_dir, "screenshot"))
        # Scan clips
        if self._filter_type in ("all", "clips"):
            items.extend(self._scan_dir(self._clip_dir, "clip"))
        # Sort by modification time, newest first
        items.sort(key=lambda x: x["mtime"], reverse=True)
        self.loaded.emit(items)

    def _scan_dir(self, base_dir: str, file_type: str) -> list[dict]:
        if not base_dir or not os.path.isdir(base_dir):
            return []
        items = []
        for root, dirs, files in os.walk(base_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                ext = fname.lower().rsplit(".", 1)[-1] if "." in fname else ""
                if file_type == "screenshot" and ext in ("png", "jpg", "jpeg"):
                    items.append(self._make_item(fpath, "screenshot"))
                elif file_type == "clip" and ext in ("mp4", "mkv", "webm"):
                    items.append(self._make_item(fpath, "clip"))
        return items

    @staticmethod
    def _make_item(path: str, file_type: str) -> dict:
        mtime = os.path.getmtime(path)
        pixmap = None
        if file_type == "screenshot" and cv2 is not None:
            try:
                img = cv2.imread(path)
                if img is not None:
                    h, w = img.shape[:2]
                    scale = min(THUMB_WIDTH / w, THUMB_HEIGHT / h)
                    tw, th = int(w * scale), int(h * scale)
                    thumb = cv2.resize(img, (tw, th))
                    rgb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
                    qimg = QImage(rgb.data, tw, th, tw * 3, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimg.copy())
            except Exception:
                pass
        elif file_type == "clip" and cv2 is not None:
            try:
                cap = cv2.VideoCapture(path)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    scale = min(THUMB_WIDTH / w, THUMB_HEIGHT / h)
                    tw, th = int(w * scale), int(h * scale)
                    thumb = cv2.resize(frame, (tw, th))
                    rgb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
                    qimg = QImage(rgb.data, tw, th, tw * 3, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimg.copy())
            except Exception:
                pass
        return {"path": path, "pixmap": pixmap, "type": file_type, "mtime": mtime}


class _ThumbnailWidget(QWidget):
    """A single thumbnail tile in the gallery grid."""

    clicked = pyqtSignal(str, str)  # (path, type)

    def __init__(self, item: dict, parent=None):
        super().__init__(parent)
        self._path = item["path"]
        self._type = item["type"]
        self.setFixedSize(THUMB_WIDTH + 8, THUMB_HEIGHT + 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(os.path.basename(self._path))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Thumbnail image
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setFixedSize(THUMB_WIDTH, THUMB_HEIGHT)
        img_label.setStyleSheet(
            f"background: {SECONDARY}; border: 1px solid {BORDER}; border-radius: 4px;"
        )
        if item.get("pixmap"):
            img_label.setPixmap(item["pixmap"])
        else:
            img_label.setText("No Preview")
            img_label.setStyleSheet(
                img_label.styleSheet() + f" color: {TEXT_MUTED}; font-size: 11px;"
            )
        layout.addWidget(img_label)

        # Filename label
        name = os.path.basename(self._path)
        if len(name) > 28:
            name = name[:25] + "..."
        name_label = QLabel(name)
        name_label.setStyleSheet(f"font-size: 10px; color: {TEXT_MUTED};")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        self.setStyleSheet(
            f"_ThumbnailWidget {{ border-radius: 4px; }}"
            f"_ThumbnailWidget:hover {{ background: {SECONDARY}; }}"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._path, self._type)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        open_action = menu.addAction("Open in Folder")
        delete_action = menu.addAction("Delete")
        action = menu.exec(event.globalPos())
        if action == open_action:
            self._open_in_folder()
        elif action == delete_action:
            self._delete()

    def _open_in_folder(self):
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(self._path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", self._path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(self._path)])

    def _delete(self):
        try:
            os.remove(self._path)
            self.hide()
            self.deleteLater()
        except OSError as e:
            log.error("Failed to delete %s: %s", self._path, e)


class GalleryPage(QWidget):
    """Gallery page for browsing screenshots and video clips."""

    def __init__(self, *, config, signals):
        super().__init__()
        self._config = config
        self._signals = signals
        self._loader = None

        outer = QVBoxLayout(self)

        # Header
        header = QLabel("Gallery")
        header.setObjectName("pageHeader")
        outer.addWidget(header)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Show:"))
        self._filter = QComboBox()
        self._filter.addItem("All", "all")
        self._filter.addItem("Screenshots", "screenshots")
        self._filter.addItem("Clips", "clips")
        self._filter.currentIndexChanged.connect(self._reload)
        filter_row.addWidget(self._filter)

        open_ss_btn = QPushButton("Open Screenshots Folder")
        open_ss_btn.clicked.connect(self._open_screenshot_folder)
        filter_row.addWidget(open_ss_btn)

        open_clip_btn = QPushButton("Open Clips Folder")
        open_clip_btn.clicked.connect(self._open_clip_folder)
        filter_row.addWidget(open_clip_btn)

        filter_row.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._reload)
        filter_row.addWidget(refresh_btn)
        outer.addLayout(filter_row)

        # Scroll area for thumbnails
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(8)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._grid_widget)
        outer.addWidget(self._scroll)

        # Status
        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        outer.addWidget(self._status)

        # Connect capture events for auto-refresh
        signals.screenshot_saved.connect(lambda _: self._reload())
        signals.clip_saved.connect(lambda _: self._reload())

        # Initial load
        self._reload()

    def _reload(self):
        """Scan directories and rebuild the thumbnail grid."""
        ss_dir = self._config.screenshot_directory or DEFAULT_SCREENSHOT_DIR
        clip_dir = self._config.clip_directory or DEFAULT_CLIP_DIR
        filter_type = self._filter.currentData() or "all"

        self._status.setText("Loading...")

        # Clear existing grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Load in background
        self._loader = _ThumbnailLoader(ss_dir, clip_dir, filter_type)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()

    def _on_loaded(self, items: list[dict]):
        # Clear grid again (in case of race)
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not items:
            self._status.setText("No captures found. Take a screenshot or save a clip to get started.")
            return

        for i, item in enumerate(items):
            widget = _ThumbnailWidget(item)
            widget.clicked.connect(self._on_thumbnail_clicked)
            row, col = divmod(i, THUMB_COLS)
            self._grid.addWidget(widget, row, col)

        self._status.setText(f"{len(items)} item{'s' if len(items) != 1 else ''}")

    def _on_thumbnail_clicked(self, path: str, file_type: str):
        if file_type == "screenshot":
            self._show_screenshot_preview(path)
        elif file_type == "clip":
            self._play_clip(path)

    def _show_screenshot_preview(self, path: str):
        """Show a full-size screenshot in a dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle(os.path.basename(path))
        dialog.setMinimumSize(800, 600)
        layout = QVBoxLayout(dialog)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                780, 560,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            img_label.setPixmap(scaled)
        else:
            img_label.setText("Failed to load image")
        layout.addWidget(img_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.exec()

    def _play_clip(self, path: str):
        """Play a video clip using QMediaPlayer or system player."""
        try:
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PyQt6.QtMultimediaWidgets import QVideoWidget

            dialog = QDialog(self)
            dialog.setWindowTitle(os.path.basename(path))
            dialog.setMinimumSize(800, 500)
            layout = QVBoxLayout(dialog)

            video_widget = QVideoWidget()
            layout.addWidget(video_widget)

            audio_output = QAudioOutput()
            player = QMediaPlayer()
            player.setAudioOutput(audio_output)
            player.setVideoOutput(video_widget)
            player.setSource(QUrl.fromLocalFile(os.path.abspath(path)))

            # Controls
            ctrl_row = QHBoxLayout()
            play_btn = QPushButton("Play")
            pause_btn = QPushButton("Pause")
            stop_btn = QPushButton("Stop")
            play_btn.clicked.connect(player.play)
            pause_btn.clicked.connect(player.pause)
            stop_btn.clicked.connect(player.stop)
            ctrl_row.addWidget(play_btn)
            ctrl_row.addWidget(pause_btn)
            ctrl_row.addWidget(stop_btn)
            ctrl_row.addStretch()
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            ctrl_row.addWidget(close_btn)
            layout.addLayout(ctrl_row)

            # Auto-play
            player.play()

            # Stop on dialog close
            dialog.finished.connect(player.stop)

            dialog.exec()
        except ImportError:
            # Fallback: open with system player
            log.info("PyQt6-Multimedia not available, using system player")
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])

    def _open_screenshot_folder(self):
        path = self._config.screenshot_directory or DEFAULT_SCREENSHOT_DIR
        self._open_folder(path)

    def _open_clip_folder(self):
        path = self._config.clip_directory or DEFAULT_CLIP_DIR
        self._open_folder(path)

    @staticmethod
    def _open_folder(path: str):
        os.makedirs(path, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
