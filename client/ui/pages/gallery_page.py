"""Gallery page — browse screenshots and video clips with playback.

Layout: month sidebar (left) | scrollable content (right).
Content is grouped by day with date headers and horizontal rules.
Only the selected month's captures are shown.
"""

import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QGridLayout, QComboBox, QFrame, QDialog, QStyle, QSizePolicy,
    QStyleOption,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter

from ...capture.constants import DEFAULT_CLIP_DIR, DEFAULT_SCREENSHOT_DIR
from ...core.logger import get_logger
from ..icons import svg_icon, GALLERY
from ..theme import TEXT_MUTED, BORDER, BORDER_HOVER, ACCENT, SECONDARY, PRIMARY, MAIN_DARK, HOVER, TEXT
from ..widgets.gallery_common import (
    ThumbnailLoader, ThumbnailWidget, EncodingThumbnailWidget,
    THUMB_WIDTH, THUMB_HEIGHT, THUMB_COLS,
    generate_clip_thumbnail,
)
from ..widgets.video_player import VideoPlayerWidget, has_multimedia
from ..dialogs.upload_dialog import MediaUploadDialog

log = get_logger("Gallery")

# Minimum video dialog size
_MIN_VIDEO_W = 480
_MIN_VIDEO_H = 300

# Month sidebar width
_MONTH_SIDEBAR_WIDTH = 130


# ------------------------------------------------------------------
# Month sidebar
# ------------------------------------------------------------------

class _MonthEntry(QPushButton):
    """A single clickable month in the sidebar."""

    def __init__(self, label: str, year_month: tuple[int, int], count: int,
                 parent=None):
        super().__init__(parent)
        self.year_month = year_month
        self.setText(f"{label}  ({count})")
        self.setToolTip(f"{label} — {count} capture{'s' if count != 1 else ''}")
        self.setFixedHeight(26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setStyleSheet(
            f"QPushButton {{"
            f"  text-align: left; padding: 2px 10px; border: none;"
            f"  background: transparent; color: {TEXT_MUTED}; font-size: 12px;"
            f"}}"
            f"QPushButton:hover {{ background: {HOVER}; color: {TEXT}; }}"
            f"QPushButton:checked {{ color: {ACCENT}; font-weight: bold; }}"
        )


class _MonthSidebar(QWidget):
    """Sidebar listing available months for navigation."""

    month_selected = pyqtSignal(int, int)  # (year, month)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(_MONTH_SIDEBAR_WIDTH)
        self.setObjectName("galleryMonthSidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#galleryMonthSidebar {{"
            f"  background-color: {MAIN_DARK};"
            f"  border-right: 1px solid {BORDER};"
            f"}}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QLabel("Months")
        header.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; font-weight: bold;"
            f" letter-spacing: 0.5px; padding: 12px 10px 6px 10px;"
            f" background: transparent;"
        )
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            " QAbstractScrollArea::viewport { background: transparent; }"
        )

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch(1)
        scroll.setWidget(self._list_widget)
        outer.addWidget(scroll, 1)

        self._status = QLabel("")
        self._status.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; padding: 6px 10px;"
            f" background: transparent;"
        )
        self._status.setWordWrap(True)
        outer.addWidget(self._status)

        self._entries: list[_MonthEntry] = []

    def set_months(self, months: list[tuple[int, int, int]],
                   selected: tuple[int, int] | None = None):
        """Populate with (year, month, count) tuples, newest first.

        If *selected* is given, that month is checked.
        """
        # Clear
        for e in self._entries:
            e.deleteLater()
        self._entries = []

        # Remove the stretch, add entries, re-add stretch
        stretch = self._list_layout.takeAt(self._list_layout.count() - 1)

        for year, month, count in months:
            dt = datetime(year, month, 1)
            label = dt.strftime("%b %Y")  # e.g. "Mar 2026"
            entry = _MonthEntry(label, (year, month), count, self)
            entry.clicked.connect(lambda _, ym=(year, month): self._on_click(ym))
            if selected and (year, month) == selected:
                entry.setChecked(True)
            self._list_layout.addWidget(entry)
            self._entries.append(entry)

        self._list_layout.addStretch(1)

    def _on_click(self, ym: tuple[int, int]):
        # No-op if the clicked month is already active
        for e in self._entries:
            if e.year_month == ym and e.isChecked():
                return
        for e in self._entries:
            e.setChecked(e.year_month == ym)
        self.month_selected.emit(ym[0], ym[1])

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        p.end()


# ------------------------------------------------------------------
# Video dialog
# ------------------------------------------------------------------

class _VideoDialog(QDialog):
    """Simple resizable dialog for video playback."""

    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setWindowIcon(svg_icon(GALLERY, "#e0e0e0", 16))
        self.setWindowTitle(title)
        self.setMinimumSize(_MIN_VIDEO_W, _MIN_VIDEO_H)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)


# ------------------------------------------------------------------
# Gallery page
# ------------------------------------------------------------------

class GalleryPage(QWidget):
    """Gallery page for browsing screenshots and video clips."""

    def __init__(self, *, config, signals, db=None, nexus_client=None):
        super().__init__()
        self._config = config
        self._signals = signals
        self._db = db
        self._nexus_client = nexus_client
        self._loader = None
        self._all_items: list[dict] = []
        self._selected_month: tuple[int, int] | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setObjectName("galleryToolbar")
        toolbar.setStyleSheet(
            f"#galleryToolbar {{"
            f"  background: {MAIN_DARK};"
            f"  border-bottom: 1px solid {BORDER};"
            f"}}"
            f"#galleryToolbar QPushButton {{"
            f"  background: {SECONDARY}; color: {TEXT};"
            f"  border: 1px solid {BORDER}; border-radius: 4px;"
            f"  padding: 4px 12px; font-size: 12px;"
            f"}}"
            f"#galleryToolbar QPushButton:hover {{"
            f"  background: {HOVER}; border-color: {BORDER_HOVER};"
            f"}}"
            f"#galleryToolbar QPushButton:pressed {{"
            f"  background: {PRIMARY};"
            f"}}"
        )
        filter_row = QHBoxLayout(toolbar)
        filter_row.setContentsMargins(12, 8, 12, 8)
        filter_row.setSpacing(10)

        show_label = QLabel("Show:")
        show_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; border: none;")
        filter_row.addWidget(show_label)
        self._filter = QComboBox()
        self._filter.addItem("All", "all")
        self._filter.addItem("Screenshots", "screenshots")
        self._filter.addItem("Clips", "clips")
        self._filter.setFixedWidth(120)
        self._filter.currentIndexChanged.connect(self._reload)
        filter_row.addWidget(self._filter)

        filter_row.addSpacing(10)

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
        outer.addWidget(toolbar)

        # Main content: sidebar + scroll area
        content_container = QWidget()
        content_row = QHBoxLayout(content_container)
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)

        self._sidebar = _MonthSidebar()
        self._sidebar.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding,
        )
        self._sidebar.month_selected.connect(self._on_month_selected)
        content_row.addWidget(self._sidebar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { border: none; }")

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(12, 8, 12, 12)
        self._content_layout.setSpacing(0)
        self._content_layout.addStretch(1)
        self._scroll.setWidget(self._content_widget)
        content_row.addWidget(self._scroll)

        outer.addWidget(content_container, 1)

        # Pending clip thumbnails
        self._pending_thumbs: list[tuple[str, ThumbnailWidget, int]] = []
        self._pending_timer = QTimer(self)
        self._pending_timer.setSingleShot(True)
        self._pending_timer.setInterval(2000)
        self._pending_timer.timeout.connect(self._retry_pending_thumbs)

        # Debounced incremental refresh on capture events
        self._capture_refresh_timer = QTimer(self)
        self._capture_refresh_timer.setSingleShot(True)
        self._capture_refresh_timer.setInterval(500)
        self._capture_refresh_timer.timeout.connect(self._reload)
        signals.screenshot_saved.connect(lambda _: self._capture_refresh_timer.start())
        signals.clip_saved.connect(self._on_clip_saved)
        signals.recording_stopped.connect(lambda _: self._capture_refresh_timer.start())

        # Encoding progress placeholders: path -> widget
        self._encoding_widgets: dict[str, EncodingThumbnailWidget] = {}
        signals.clip_encoding_started.connect(self._on_encoding_started)
        signals.clip_encoding_progress.connect(self._on_encoding_progress)

        self._reload()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _reload(self):
        # Disconnect old loader to prevent stale results; wait briefly for cleanup
        if self._loader is not None:
            try:
                self._loader.loaded.disconnect(self._on_loaded)
            except TypeError:
                pass  # already disconnected
            if self._loader.isRunning():
                self._loader.wait(3000)
            self._loader = None

        ss_dir = self._config.screenshot_directory or DEFAULT_SCREENSHOT_DIR
        clip_dir = self._config.clip_directory or DEFAULT_CLIP_DIR
        filter_type = self._filter.currentData() or "all"

        self._sidebar._status.setText("Loading...")
        self._loader = ThumbnailLoader(ss_dir, clip_dir, filter_type, db=self._db)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()

    def _on_loaded(self, items: list[dict]):
        self._all_items = items
        self._pending_thumbs = []

        # Build month list from all items
        month_counts: dict[tuple[int, int], int] = defaultdict(int)
        for it in items:
            dt = datetime.fromtimestamp(it["mtime"])
            month_counts[(dt.year, dt.month)] += 1

        months = sorted(month_counts.keys(), reverse=True)
        month_list = [(y, m, month_counts[(y, m)]) for y, m in months]

        if not months:
            self._sidebar.set_months([])
            self._clear_content()
            self._sidebar._status.setText(
                "No captures found. Take a screenshot or save a clip to get started."
            )
            return

        # Keep selection if still valid, otherwise select newest
        if self._selected_month and self._selected_month in month_counts:
            sel = self._selected_month
        else:
            sel = months[0]

        self._selected_month = sel
        self._sidebar.set_months(month_list, selected=sel)
        self._show_month(sel[0], sel[1])

    def _on_month_selected(self, year: int, month: int):
        self._selected_month = (year, month)
        self._show_month(year, month)

    # ------------------------------------------------------------------
    # Content rendering
    # ------------------------------------------------------------------

    def _clear_content(self):
        # Remove encoding widgets from layout (but don't delete them)
        for ew in self._encoding_widgets.values():
            self._content_layout.removeWidget(ew)
            ew.setParent(None)
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _insert_encoding_widgets(self):
        """Re-insert active encoding placeholders at the top of the content."""
        for ew in self._encoding_widgets.values():
            self._content_layout.insertWidget(0, ew)

    def _show_month(self, year: int, month: int):
        self._clear_content()
        self._pending_thumbs = []

        # Insert encoding progress placeholders at the top
        self._insert_encoding_widgets()

        # Filter items for this month
        month_items = []
        for it in self._all_items:
            dt = datetime.fromtimestamp(it["mtime"])
            if dt.year == year and dt.month == month:
                month_items.append(it)

        if not month_items and not self._encoding_widgets:
            empty = QLabel("No captures for this month.")
            empty.setStyleSheet(f"color: {TEXT_MUTED}; padding: 20px;")
            self._content_layout.addWidget(empty)
            self._content_layout.addStretch(1)
            self._sidebar._status.setText("0 items")
            return

        # Group by day (items already sorted by mtime desc)
        day_groups: dict[str, list[dict]] = defaultdict(list)
        for it in month_items:
            dt = datetime.fromtimestamp(it["mtime"])
            day_key = dt.strftime("%Y-%m-%d")
            day_groups[day_key].append(it)

        sorted_days = sorted(day_groups.keys(), reverse=True)

        for day_key in sorted_days:
            day_items = day_groups[day_key]
            dt = datetime.strptime(day_key, "%Y-%m-%d")
            day_label_text = dt.strftime("%A, %B %d")  # e.g. "Monday, March 10"

            # Day header
            day_label = QLabel(day_label_text)
            day_label.setStyleSheet(
                f"color: {TEXT}; font-size: 13px; font-weight: bold;"
                f" padding: 12px 0 4px 0;"
            )
            self._content_layout.addWidget(day_label)

            # Horizontal rule
            hr = QFrame()
            hr.setFrameShape(QFrame.Shape.HLine)
            hr.setStyleSheet(f"color: {BORDER};")
            self._content_layout.addWidget(hr)

            # Thumbnail grid for this day
            grid = QGridLayout()
            grid.setSpacing(8)
            grid.setAlignment(
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
            )

            for i, item in enumerate(day_items):
                widget = ThumbnailWidget(item)
                widget.clicked.connect(self._on_thumbnail_clicked)
                widget.upload_clicked.connect(self._on_upload_clicked)
                row, col = divmod(i, THUMB_COLS)
                grid.addWidget(widget, row, col)
                if item.get("pending"):
                    self._pending_thumbs.append((item["path"], widget, 0))

            grid_container = QWidget()
            grid_container.setLayout(grid)
            self._content_layout.addWidget(grid_container)

        self._content_layout.addStretch(1)

        total = len(month_items)
        month_name = datetime(year, month, 1).strftime("%B %Y")
        self._sidebar._status.setText(
            f"{total} item{'s' if total != 1 else ''} in {month_name}"
        )

        if self._pending_thumbs:
            self._pending_timer.start()

        self._scroll.verticalScrollBar().setValue(0)

    # ------------------------------------------------------------------
    # Pending thumbnails
    # ------------------------------------------------------------------

    _PENDING_MAX_RETRIES = 30

    def _retry_pending_thumbs(self):
        still_pending = []
        for path, widget, count in self._pending_thumbs:
            if count >= self._PENDING_MAX_RETRIES:
                widget.set_no_preview()
                continue
            pixmap = generate_clip_thumbnail(path)
            if pixmap:
                widget.set_pixmap(pixmap)
            else:
                still_pending.append((path, widget, count + 1))
        self._pending_thumbs = still_pending
        if self._pending_thumbs:
            self._pending_timer.start()

    # ------------------------------------------------------------------
    # Clip encoding progress
    # ------------------------------------------------------------------

    def _on_encoding_started(self, data):
        """Insert an encoding placeholder at the top of the gallery."""
        path = data.get("path", "")
        total = data.get("frames", 0)
        if path in self._encoding_widgets:
            return  # already tracking
        widget = EncodingThumbnailWidget(path, total)
        self._encoding_widgets[path] = widget
        # Insert at position 0 (before day groups)
        self._content_layout.insertWidget(0, widget)

    def _on_encoding_progress(self, data):
        """Update the encoding placeholder's progress bar."""
        path = data.get("path", "")
        widget = self._encoding_widgets.get(path)
        if widget is not None:
            widget.set_progress(data.get("written", 0), data.get("total", 1))

    def _on_clip_saved(self, data):
        """Remove encoding placeholder and refresh the gallery."""
        path = data.get("path", "")
        widget = self._encoding_widgets.pop(path, None)
        if widget is not None:
            widget.hide()
            widget.deleteLater()
        self._capture_refresh_timer.start()

    # ------------------------------------------------------------------
    # Thumbnail actions
    # ------------------------------------------------------------------

    def _on_thumbnail_clicked(self, path: str, file_type: str):
        if file_type == "screenshot":
            self._show_screenshot_preview(path)
        elif file_type == "clip":
            self._play_clip(path)

    def _on_upload_clicked(self, path: str):
        if not self._db or not self._nexus_client:
            return
        info = self._db.get_screenshot_by_path(path)
        if not info:
            # File not in DB yet — create a minimal record
            file_type = (
                "clip"
                if path.lower().endswith((".mp4", ".mkv", ".avi", ".webm"))
                else "screenshot"
            )
            mtime = os.path.getmtime(path)
            created = datetime.fromtimestamp(mtime).isoformat()
            self._db.insert_screenshot(path, file_type, created)
            info = self._db.get_screenshot_by_path(path)
        if not info:
            return
        dialog = MediaUploadDialog(
            path, info, self._db, self._nexus_client, parent=self,
        )
        dialog.upload_completed.connect(self._on_upload_completed)
        dialog.exec()

    def _on_upload_completed(self, path: str, server_global_id: int):
        log.info("Upload completed: %s -> server global %d", path, server_global_id)
        self._refresh_thumbnail(path)

    def _refresh_thumbnail(self, path: str):
        if not self._db:
            return
        new_info = self._db.get_screenshot_by_path(path)
        if not new_info:
            return
        info_dict = {
            "has_notes": bool(new_info.get("notes")),
            "global_type": new_info.get("global_type"),
            "is_hof": new_info.get("is_hof"),
            "is_ath": new_info.get("is_ath"),
            "upload_status": new_info.get("upload_status", "none"),
            "server_global_id": new_info.get("server_global_id"),
            "video_url": new_info.get("video_url"),
        }
        for w in self._content_widget.findChildren(ThumbnailWidget):
            if w._item.get("path") == path:
                w.update_screenshot_info(info_dict)
                break

    # ------------------------------------------------------------------
    # Screenshot preview
    # ------------------------------------------------------------------

    def _show_screenshot_preview(self, path: str):
        from PyQt6.QtWidgets import QTextEdit

        dialog = QDialog(self)
        dialog.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint
        )
        dialog.setWindowIcon(svg_icon(GALLERY, "#e0e0e0", 16))
        dialog.setWindowTitle(os.path.basename(path))
        dialog.setMinimumSize(800, 600)
        layout = QVBoxLayout(dialog)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                780, 520,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            img_label.setPixmap(scaled)
        else:
            img_label.setText("Failed to load image")
        layout.addWidget(img_label)

        record = self._db.get_screenshot_by_path(path) if self._db else None
        if record and record.get("global_type"):
            gt = record["global_type"]
            badges = []
            if record.get("is_ath"):
                badges.append("ATH")
            if record.get("is_hof"):
                badges.append("HoF")
            target = record.get("target_name", "")
            value = record.get("value", 0)
            info_text = f"Global: {gt} — {target}"
            if value:
                info_text += f" ({value:.2f} PED)"
            if badges:
                info_text += f" [{', '.join(badges)}]"
            info_label = QLabel(info_text)
            info_label.setStyleSheet(
                f"color: {ACCENT}; font-size: 11px; padding: 2px;"
            )
            layout.addWidget(info_label)

        notes_edit = QTextEdit()
        notes_edit.setPlaceholderText("Add notes...")
        notes_edit.setMaximumHeight(80)
        if record and record.get("notes"):
            notes_edit.setPlainText(record["notes"])
        layout.addWidget(QLabel("Notes:"))
        layout.addWidget(notes_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        def _save_notes():
            if self._db:
                notes = notes_edit.toPlainText().strip()
                self._db.update_screenshot_notes_by_path(path, notes)

        dialog.finished.connect(_save_notes)
        dialog.exec()

    # ------------------------------------------------------------------
    # Video playback
    # ------------------------------------------------------------------

    def _play_clip(self, path: str):
        if not has_multimedia():
            log.info("PyQt6-Multimedia not available, using system player")
            self._open_system_player(path)
            return

        dialog = _VideoDialog(self, os.path.basename(path))
        lay = QVBoxLayout(dialog)
        lay.setContentsMargins(0, 0, 0, 0)

        icon_helper = lambda svg_data, size: svg_icon(svg_data, "#e0e0e0", size)
        player = VideoPlayerWidget(dialog, icon_helper=icon_helper)
        lay.addWidget(player)

        def _on_resolution(w, h):
            bar_h = player.controls_height()
            target_w = min(w, 1200)
            video_h = int(target_w * h / w) if w else _MIN_VIDEO_H
            dialog.resize(
                max(_MIN_VIDEO_W, target_w),
                max(_MIN_VIDEO_H, video_h + bar_h),
            )

        player.video_resolution_changed.connect(_on_resolution)
        player.load(path)
        player.play()

        dialog.finished.connect(player.stop)
        dialog.show()

    # ------------------------------------------------------------------
    # Folder helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _open_system_player(path: str):
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

    def closeEvent(self, event):
        if self._loader is not None:
            try:
                self._loader.loaded.disconnect(self._on_loaded)
            except TypeError:
                pass
            if self._loader.isRunning():
                self._loader.wait(3000)
            self._loader = None
        super().closeEvent(event)
