"""Gallery overlay — browse screenshots and video clips with inline playback.

Features a collapsible title bar (matching other overlays), a left sidebar
for monthly navigation, and day-separated thumbnail grids.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget,
    QScrollArea, QGridLayout, QComboBox, QStackedWidget, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPixmap, QColor, QCursor

from .overlay_widget import OverlayWidget
from ..core.config import save_config
from ..core.logger import get_logger
from ..capture.constants import DEFAULT_CLIP_DIR, DEFAULT_SCREENSHOT_DIR
from ..ui.icons import svg_icon, svg_pixmap, ARROW_LEFT, GALLERY, CLOSE_X
from ..ui.widgets.gallery_common import (
    ThumbnailLoader, ThumbnailWidget, generate_clip_thumbnail,
)
from ..ui.widgets.video_player import VideoPlayerWidget, has_multimedia

if TYPE_CHECKING:
    from .overlay_manager import OverlayManager

log = get_logger("GalleryOverlay")

# Layout constants
GALLERY_MIN_WIDTH = 350
GALLERY_MIN_HEIGHT = 300
GALLERY_THUMB_WIDTH = 150
GALLERY_THUMB_HEIGHT = 100
_TITLE_H = 24
_SIDEBAR_W = 90

# Overlay-specific dark translucent theme (matches search/recording bar)
BG_COLOR = "rgba(20, 20, 30, 220)"
TITLE_BG = "rgba(30, 30, 45, 200)"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#888888"
ACCENT = "#00ccff"
TAB_HOVER_BG = "rgba(50, 50, 70, 160)"
SIDEBAR_BG = "rgba(15, 15, 25, 200)"
DAY_BORDER = "rgba(80, 80, 100, 100)"

_PAGE_GRID = 0
_PAGE_DETAIL = 1

_BTN_STYLE = (
    "QPushButton {"
    "  background: transparent; border: none; border-radius: 3px;"
    "  padding: 0px; margin: 0px;"
    "}"
    "QPushButton:hover {"
    f"  background-color: {TAB_HOVER_BG};"
    "}"
)

_SCROLLBAR_STYLE = (
    "QScrollArea { background: transparent; border: none; }"
    "QScrollBar:vertical {"
    "  background: rgba(30, 30, 45, 100); width: 8px;"
    "}"
    "QScrollBar::handle:vertical {"
    "  background: rgba(80, 80, 100, 180); border-radius: 4px;"
    "  min-height: 20px;"
    "}"
    "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
    "  height: 0px;"
    "}"
)


def _overlay_icon(svg_data, size=14):
    """Helper to create icons with overlay text color."""
    return svg_icon(svg_data, TEXT_COLOR, size)


class _ResizeGrip(QWidget):
    """Custom resize grip for the bottom-right corner."""

    def __init__(self, overlay: GalleryOverlay):
        super().__init__(overlay)
        self._overlay = overlay
        self._start_pos = None
        self._start_size = None
        self.setFixedSize(16, 16)
        self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(TEXT_DIM))
        pen.setWidthF(1.5)
        p.setPen(pen)
        p.drawLine(14, 2, 2, 14)
        p.drawLine(14, 7, 7, 14)
        p.drawLine(14, 12, 12, 14)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.globalPosition().toPoint()
            self._start_size = self._overlay.size()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._start_pos and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._start_pos
            new_w = max(GALLERY_MIN_WIDTH, self._start_size.width() + delta.x())
            new_h = max(GALLERY_MIN_HEIGHT, self._start_size.height() + delta.y())
            self._overlay.resize(new_w, new_h)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._start_pos is not None:
            self._start_pos = None
            self._overlay._save_size()
            event.accept()


class GalleryOverlay(OverlayWidget):
    """Resizable gallery overlay with thumbnail grid and inline playback."""

    def __init__(
        self,
        *,
        config,
        config_path: str,
        signals,
        manager: OverlayManager | None = None,
        db=None,
        nexus_client=None,
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="gallery_overlay_position",
            manager=manager,
        )
        self._signals = signals
        self._db = db
        self._nexus_client = nexus_client
        self._loader = None
        self._all_items: list[dict] = []
        self._selected_month: tuple[int, int] | None = None
        self._click_origin = None
        self._saved_size = (420, 500)

        # Pending clip thumbnails — retry until the file is finalized
        self._pending_thumbs: list[tuple[str, ThumbnailWidget, int]] = []
        self._pending_timer = QTimer(self)
        self._pending_timer.setSingleShot(True)
        self._pending_timer.setInterval(2000)
        self._pending_timer.timeout.connect(self._retry_pending_thumbs)

        # Restore size
        size = getattr(config, "gallery_overlay_size", (420, 500))
        self.resize(
            max(GALLERY_MIN_WIDTH, size[0]),
            max(GALLERY_MIN_HEIGHT, size[1]),
        )

        # Allow resize (override fixed-size constraint)
        self.layout().setSizeConstraint(QVBoxLayout.SizeConstraint.SetDefaultConstraint)

        # Container style — no border-radius on container; title bar handles top radii
        self._container.setStyleSheet(
            f"background-color: {BG_COLOR}; border-radius: 8px; padding: 0px;"
        )

        # Build UI
        self._build_ui()

        # Resize grip
        self._resize_grip = _ResizeGrip(self)
        self._position_resize_grip()

        # Connect capture events for auto-refresh
        signals.screenshot_saved.connect(lambda _: self._reload())
        signals.clip_saved.connect(lambda _: self._reload())
        signals.recording_stopped.connect(lambda _: self._reload())

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar (always visible, collapsible on click)
        self._title_bar = self._build_title_bar()
        layout.addWidget(self._title_bar)

        # Body (hidden when collapsed)
        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self._stack = QStackedWidget()
        body_layout.addWidget(self._stack)

        # Page 0: Grid view (sidebar + content)
        self._grid_page = self._build_grid_page()
        self._stack.addWidget(self._grid_page)

        # Page 1: Detail view
        self._detail_page = self._build_detail_page()
        self._stack.addWidget(self._detail_page)

        self._stack.setCurrentIndex(_PAGE_GRID)
        layout.addWidget(self._body, 1)

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(_TITLE_H)
        bar.setStyleSheet(
            f"background-color: {TITLE_BG};"
            " border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        # Gallery icon
        icon_lbl = QLabel()
        icon_lbl.setPixmap(svg_icon(GALLERY, ACCENT, 14).pixmap(14, 14))
        icon_lbl.setStyleSheet("background: transparent;")
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        # Title label
        title_label = QLabel("Gallery")
        title_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            " background: transparent;"
        )
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch(1)

        # Close button
        close_btn = QPushButton()
        close_btn.setFixedSize(18, 18)
        close_btn.setIcon(svg_icon(CLOSE_X, TEXT_DIM, 14))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(_BTN_STYLE)
        close_btn.clicked.connect(lambda: self.set_wants_visible(False))
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return bar

    def _build_grid_page(self) -> QWidget:
        page = QWidget()
        h_layout = QHBoxLayout(page)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # Month sidebar
        self._sidebar = self._build_sidebar()
        h_layout.addWidget(self._sidebar)

        # Content area (day-grouped thumbnails)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(6, 6, 6, 6)
        content_layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setStyleSheet(_SCROLLBAR_STYLE)

        self._content_widget = QWidget()
        self._content_widget.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._content_layout.addStretch(1)
        self._scroll.setWidget(self._content_widget)

        content_layout.addWidget(self._scroll, 1)

        # Status bar
        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; padding: 2px 0;")
        content_layout.addWidget(self._status)

        h_layout.addWidget(content, 1)

        return page

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(_SIDEBAR_W)
        sidebar.setStyleSheet(
            f"background-color: {SIDEBAR_BG};"
            f" border-right: 1px solid {DAY_BORDER};"
            " border-bottom-left-radius: 8px;"
        )

        outer = QVBoxLayout(sidebar)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QLabel("Months")
        header.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; font-weight: bold;"
            f" letter-spacing: 0.5px; padding: 8px 6px 4px 6px;"
            f" background: transparent;"
        )
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:vertical {"
            "  background: transparent; width: 4px;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(80, 80, 100, 150); border-radius: 2px;"
            "  min-height: 16px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "  height: 0px;"
            "}"
        )

        self._month_list = QWidget()
        self._month_list.setStyleSheet("background: transparent;")
        self._month_layout = QVBoxLayout(self._month_list)
        self._month_layout.setContentsMargins(0, 0, 0, 0)
        self._month_layout.setSpacing(0)
        self._month_layout.addStretch(1)
        scroll.setWidget(self._month_list)
        outer.addWidget(scroll, 1)

        self._month_entries: list[QPushButton] = []

        # Filter dropdown at the bottom of the sidebar
        self._filter = QComboBox()
        self._filter.addItem("All", "all")
        self._filter.addItem("Screenshots", "screenshots")
        self._filter.addItem("Clips", "clips")
        self._filter.setStyleSheet(
            f"QComboBox {{ background: rgba(40, 40, 55, 230);"
            f" border: 1px solid rgba(80, 80, 100, 180);"
            f" border-radius: 3px; color: {TEXT_COLOR};"
            f" padding: 2px 6px; font-size: 10px;"
            f" margin: 4px 6px 6px 6px; }}"
        )
        self._filter.currentIndexChanged.connect(self._reload)
        outer.addWidget(self._filter)

        return sidebar

    def _build_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Back row
        back_row = QHBoxLayout()
        back_row.setContentsMargins(0, 0, 0, 0)

        back_btn = QPushButton()
        back_btn.setFixedSize(22, 22)
        back_btn.setIcon(svg_icon(ARROW_LEFT, TEXT_COLOR, 14))
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(_BTN_STYLE)
        back_btn.clicked.connect(self._back_to_grid)
        back_row.addWidget(back_btn)

        self._detail_title = QLabel("")
        self._detail_title.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px;"
        )
        self._detail_title.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        back_row.addWidget(self._detail_title, 1)

        # Opaque toggle
        self._opaque_btn = QPushButton("Opaque")
        self._opaque_btn.setCheckable(True)
        self._opaque_btn.setFixedHeight(20)
        self._opaque_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._opaque_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: rgba(40, 40, 55, 200); border: 1px solid rgba(80, 80, 100, 180);"
            f"  border-radius: 3px; color: {TEXT_DIM}; font-size: 10px;"
            f"  padding: 1px 8px;"
            f"}}"
            f"QPushButton:hover {{ color: {TEXT_COLOR}; }}"
            f"QPushButton:checked {{"
            f"  background: rgba(0, 204, 255, 40); border-color: {ACCENT};"
            f"  color: {ACCENT};"
            f"}}"
        )
        self._opaque_btn.clicked.connect(self._toggle_opaque)
        back_row.addWidget(self._opaque_btn)

        layout.addLayout(back_row)

        # Media area (stacked: image label or video player)
        self._media_stack = QStackedWidget()
        self._media_stack.setStyleSheet("background: transparent;")

        # Image display
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet(
            f"background: rgba(15, 15, 25, 200); border-radius: 4px;"
        )
        self._media_stack.addWidget(self._image_label)

        # Video player widget
        self._video_player = VideoPlayerWidget(
            icon_helper=_overlay_icon,
        )
        self._media_stack.addWidget(self._video_player)

        layout.addWidget(self._media_stack, 1)

        return page

    # ------------------------------------------------------------------
    # Title bar collapse / expand (click detection)
    # ------------------------------------------------------------------

    def _toggle_minify(self):
        expanding = not self._body.isVisible()
        self._body.setVisible(expanding)
        if expanding:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG};"
                " border-top-left-radius: 8px; border-top-right-radius: 8px;"
            )
            # Restore full size
            self.setMinimumSize(GALLERY_MIN_WIDTH, GALLERY_MIN_HEIGHT)
            self.setMaximumSize(16777215, 16777215)
            self.resize(self._saved_size[0], self._saved_size[1])
        else:
            # Save current size and collapse to title bar height
            self._saved_size = (self.width(), self.height())
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG}; border-radius: 8px;"
            )
            self.setFixedSize(self.width(), _TITLE_H)
        self._resize_grip.setVisible(expanding)
        self._position_resize_grip()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_origin = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        click_origin = self._click_origin
        self._click_origin = None
        super().mouseReleaseEvent(event)

        if click_origin and event.button() == Qt.MouseButton.LeftButton:
            delta = (
                event.globalPosition().toPoint() - click_origin
            ).manhattanLength()
            if delta < 5:
                click_local = self.mapFromGlobal(click_origin)
                title_bottom = self._title_bar.mapTo(
                    self, QPoint(0, self._title_bar.height()),
                ).y()
                if click_local.y() <= title_bottom:
                    self._toggle_minify()

    # ------------------------------------------------------------------
    # Month sidebar
    # ------------------------------------------------------------------

    def _populate_sidebar(self):
        """Build the month list from loaded items."""
        # Clear existing
        for btn in self._month_entries:
            btn.deleteLater()
        self._month_entries = []

        # Remove stretch, add entries, re-add stretch
        stretch = self._month_layout.takeAt(self._month_layout.count() - 1)

        month_counts: dict[tuple[int, int], int] = defaultdict(int)
        for it in self._all_items:
            dt = datetime.fromtimestamp(it["mtime"])
            month_counts[(dt.year, dt.month)] += 1

        months = sorted(month_counts.keys(), reverse=True)
        for year, month in months:
            count = month_counts[(year, month)]
            dt = datetime(year, month, 1)
            label = f"{dt.strftime('%b %Y')}  ({count})"
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  text-align: left; padding: 1px 6px; border: none;"
                f"  background: transparent; color: {TEXT_DIM}; font-size: 10px;"
                f"}}"
                f"QPushButton:hover {{ background: {TAB_HOVER_BG}; color: {TEXT_COLOR}; }}"
                f"QPushButton:checked {{ color: {ACCENT}; font-weight: bold; }}"
            )
            ym = (year, month)
            btn.clicked.connect(lambda _, y=year, m=month: self._on_month_clicked(y, m))
            if self._selected_month and ym == self._selected_month:
                btn.setChecked(True)
            self._month_layout.addWidget(btn)
            self._month_entries.append(btn)

        self._month_layout.addStretch(1)

        # Auto-select newest month if no selection or selection no longer valid
        if months:
            if not self._selected_month or self._selected_month not in month_counts:
                self._selected_month = months[0]
                # Check the button
                if self._month_entries:
                    self._month_entries[0].setChecked(True)
            self._show_month(self._selected_month[0], self._selected_month[1])
        else:
            self._clear_content()
            self._status.setText("No captures found.")

    def _on_month_clicked(self, year: int, month: int):
        self._selected_month = (year, month)
        for btn in self._month_entries:
            btn.setChecked(False)
        # Find and check the clicked button
        for btn in self._month_entries:
            if btn.text().startswith(datetime(year, month, 1).strftime("%b %Y")):
                btn.setChecked(True)
                break
        self._show_month(year, month)

    # ------------------------------------------------------------------
    # Day-grouped content
    # ------------------------------------------------------------------

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _show_month(self, year: int, month: int):
        self._clear_content()
        self._pending_thumbs = []

        month_items = [
            it for it in self._all_items
            if (dt := datetime.fromtimestamp(it["mtime"])).year == year
            and dt.month == month
        ]

        if not month_items:
            empty = QLabel("No captures for this month.")
            empty.setStyleSheet(f"color: {TEXT_DIM}; padding: 12px; font-size: 11px;")
            self._content_layout.addWidget(empty)
            self._content_layout.addStretch(1)
            self._status.setText("0 items")
            return

        # Group by day (items already sorted by mtime desc)
        day_groups: dict[str, list[dict]] = defaultdict(list)
        for it in month_items:
            day_key = datetime.fromtimestamp(it["mtime"]).strftime("%Y-%m-%d")
            day_groups[day_key].append(it)

        sorted_days = sorted(day_groups.keys(), reverse=True)
        cols = self._calc_columns()

        for day_key in sorted_days:
            day_items = day_groups[day_key]
            dt = datetime.strptime(day_key, "%Y-%m-%d")
            day_label_text = dt.strftime("%A, %B %d")

            # Day header
            day_label = QLabel(day_label_text)
            day_label.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 11px; font-weight: bold;"
                f" padding: 8px 0 2px 0; background: transparent;"
            )
            self._content_layout.addWidget(day_label)

            # Horizontal rule
            hr = QFrame()
            hr.setFrameShape(QFrame.Shape.HLine)
            hr.setFixedHeight(1)
            hr.setStyleSheet(f"background: {DAY_BORDER}; border: none;")
            self._content_layout.addWidget(hr)

            # Thumbnail grid for this day
            grid = QGridLayout()
            grid.setSpacing(6)
            grid.setAlignment(
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
            )

            for i, item in enumerate(day_items):
                widget = ThumbnailWidget(
                    item,
                    thumb_width=GALLERY_THUMB_WIDTH,
                    thumb_height=GALLERY_THUMB_HEIGHT,
                )
                widget.clicked.connect(self._on_thumbnail_clicked)
                widget.upload_clicked.connect(self._on_upload_clicked)
                row, col = divmod(i, cols)
                grid.addWidget(widget, row, col)
                if item.get("pending"):
                    self._pending_thumbs.append((item["path"], widget, 0))

            grid_container = QWidget()
            grid_container.setStyleSheet("background: transparent;")
            grid_container.setLayout(grid)
            self._content_layout.addWidget(grid_container)

        self._content_layout.addStretch(1)

        total = len(month_items)
        month_name = datetime(year, month, 1).strftime("%B %Y")
        self._status.setText(
            f"{total} item{'s' if total != 1 else ''} in {month_name}"
        )

        if self._pending_thumbs:
            self._pending_timer.start()

        self._scroll.verticalScrollBar().setValue(0)

    # ------------------------------------------------------------------
    # Grid loading
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

        self._status.setText("Loading...")

        self._loader = ThumbnailLoader(
            ss_dir, clip_dir, filter_type,
            thumb_width=GALLERY_THUMB_WIDTH,
            thumb_height=GALLERY_THUMB_HEIGHT,
            db=self._db,
        )
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()

    _PENDING_MAX_RETRIES = 30  # 30 x 2s = 60s max wait

    def _on_loaded(self, items: list[dict]):
        self._all_items = items
        self._pending_thumbs = []
        self._populate_sidebar()

    def _retry_pending_thumbs(self):
        """Retry thumbnail generation for clips that were still encoding."""
        still_pending = []
        for path, widget, count in self._pending_thumbs:
            if count >= self._PENDING_MAX_RETRIES:
                widget.set_no_preview()
                continue
            pixmap = generate_clip_thumbnail(
                path, GALLERY_THUMB_WIDTH, GALLERY_THUMB_HEIGHT,
            )
            if pixmap:
                widget.set_pixmap(pixmap)
            else:
                still_pending.append((path, widget, count + 1))
        self._pending_thumbs = still_pending
        if self._pending_thumbs:
            self._pending_timer.start()

    def _calc_columns(self) -> int:
        available = self.width() - _SIDEBAR_W - 30  # sidebar + margins
        return max(1, available // (GALLERY_THUMB_WIDTH + 14))

    def _on_thumbnail_clicked(self, path: str, file_type: str):
        if file_type == "screenshot":
            self._show_screenshot(path)
        elif file_type == "clip":
            self._show_clip(path)

    # ------------------------------------------------------------------
    # Detail views
    # ------------------------------------------------------------------

    def _show_screenshot(self, path: str):
        self._video_player.stop()
        self._detail_title.setText(os.path.basename(path))

        pixmap = QPixmap(path)
        if not pixmap.isNull():
            available_w = self.width() - 20
            available_h = self.height() - 80
            scaled = pixmap.scaled(
                available_w, available_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._image_label.setPixmap(scaled)
        else:
            self._image_label.setText("Failed to load image")
            self._image_label.setStyleSheet(
                f"color: {TEXT_DIM}; background: rgba(15, 15, 25, 200);"
                f" border-radius: 4px;"
            )

        self._media_stack.setCurrentIndex(0)
        self._stack.setCurrentIndex(_PAGE_DETAIL)

    def _show_clip(self, path: str):
        self._detail_title.setText(os.path.basename(path))

        if self._video_player.load(path):
            self._media_stack.setCurrentIndex(1)
            self._stack.setCurrentIndex(_PAGE_DETAIL)
            self._video_player.play()
        else:
            # Fallback: open with system player
            self._open_system_player(path)

    def _open_system_player(self, path: str):
        """Fallback: open with system default player."""
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _on_upload_clicked(self, path: str):
        """Open the unified upload dialog for a thumbnail."""
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
            import os
            from datetime import datetime as _dt
            mtime = os.path.getmtime(path)
            created = _dt.fromtimestamp(mtime).isoformat()
            self._db.insert_screenshot(path, file_type, created)
            info = self._db.get_screenshot_by_path(path)
        if not info:
            return
        from ..ui.dialogs.upload_dialog import MediaUploadDialog
        dialog = MediaUploadDialog(
            path, info, self._db, self._nexus_client, parent=self,
        )
        dialog.upload_completed.connect(self._on_upload_completed)
        dialog.exec()

    def _on_upload_completed(self, path: str, server_global_id: int):
        """Refresh the thumbnail after a successful upload."""
        log.info("Upload completed: %s -> server global %d", path, server_global_id)
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

    def _toggle_opaque(self, checked: bool):
        self.setWindowOpacity(1.0 if checked else self._config.overlay_opacity)

    def _back_to_grid(self):
        self._video_player.stop()
        self._image_label.clear()
        if self._opaque_btn.isChecked():
            self._opaque_btn.setChecked(False)
            self.setWindowOpacity(self._config.overlay_opacity)
        self._stack.setCurrentIndex(_PAGE_GRID)

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_resize_grip()
        # Debounced relayout on resize
        if not hasattr(self, "_relayout_timer"):
            self._relayout_timer = QTimer(self)
            self._relayout_timer.setSingleShot(True)
            self._relayout_timer.setInterval(100)
            self._relayout_timer.timeout.connect(self._relayout_content)
        self._relayout_timer.start()

    def _relayout_content(self):
        """Re-render the month view with updated column count on resize."""
        if self._stack.currentIndex() != _PAGE_GRID:
            return
        if self._selected_month:
            self._show_month(self._selected_month[0], self._selected_month[1])

    def _position_resize_grip(self):
        if hasattr(self, "_resize_grip"):
            self._resize_grip.move(
                self.width() - self._resize_grip.width() - 2,
                self.height() - self._resize_grip.height() - 2,
            )
            self._resize_grip.raise_()

    def _save_size(self):
        self._config.gallery_overlay_size = (self.width(), self.height())
        save_config(self._config, self._config_path)

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------

    def set_wants_visible(self, visible: bool) -> None:
        super().set_wants_visible(visible)
        if visible and self._stack.currentIndex() == _PAGE_GRID:
            self._reload()

    def closeEvent(self, event):
        self._video_player.stop()
        self._pending_timer.stop()
        if hasattr(self, "_relayout_timer"):
            self._relayout_timer.stop()
        if self._loader is not None:
            try:
                self._loader.loaded.disconnect(self._on_loaded)
            except TypeError:
                pass
            if self._loader.isRunning():
                self._loader.wait(3000)
            self._loader = None
        super().closeEvent(event)
