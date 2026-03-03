"""Scan highlight overlay — click-through Qt overlay for skill scan visualization.

Highlights successfully scanned rows over the game's skills window. In debug
mode, also draws colored boxes around all detected regions (window, sidebar,
table, columns, pagination).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont

from ..core.event_bus import EventBus
from ..core.constants import (
    EVENT_DEBUG_ROW, EVENT_DEBUG_REGIONS,
    EVENT_OCR_PAGE_CHANGED, EVENT_OCR_COMPLETE, EVENT_OCR_OVERLAYS_HIDE,
    EVENT_CONFIG_CHANGED, GAME_TITLE_PREFIX,
)
from ..core.logger import get_logger
from ..platform import backend as _platform

if TYPE_CHECKING:
    from ..core.config import AppConfig
    from .overlay_manager import OverlayManager

log = get_logger("ScanHighlight")

# Focus check interval (ms)
FOCUS_POLL_MS = 500

# Auto-hide delay after scan completes (ms)
AUTO_HIDE_DELAY_MS = 3000

# Row highlight colors
ROW_FILL = QColor(0, 221, 102, 40)       # Semi-transparent green fill
ROW_BORDER = QColor(0, 221, 102, 120)    # Green border
CHECKMARK_COLOR = QColor(0, 221, 102)

# Debug region box colors
COLOR_WINDOW = QColor(255, 51, 51, 180)      # Red
COLOR_SIDEBAR = QColor(51, 255, 51, 180)     # Green
COLOR_TABLE = QColor(255, 255, 51, 180)      # Yellow
COLOR_PAGINATION = QColor(255, 51, 255, 180) # Magenta
COLOR_TOTAL = QColor(255, 200, 51, 180)     # Gold
COLOR_INDICATOR = QColor(255, 140, 0, 200)  # Dark orange
COLOR_COL_NAME = QColor(51, 153, 255, 180)   # Blue
COLOR_COL_RANK = QColor(255, 153, 51, 180)   # Orange
COLOR_COL_POINTS = QColor(51, 221, 221, 180) # Teal

COL_COLORS = {
    "name": COLOR_COL_NAME,
    "rank": COLOR_COL_RANK,
    "points": COLOR_COL_POINTS,
}

# Checkmark font
CHECKMARK_FONT = QFont("Consolas", 10, QFont.Weight.Bold)


class ScanHighlightOverlay(QWidget):
    """Click-through Qt overlay that highlights scanned skill rows.

    Receives events from the OCR pipeline via EventBus bridge signals:
    - EVENT_DEBUG_REGIONS: layout bounds (shows overlay, stores regions)
    - EVENT_DEBUG_ROW (type=matched): row highlight data
    - EVENT_OCR_PAGE_CHANGED: clear row highlights
    - EVENT_OCR_COMPLETE: auto-hide after delay
    """

    # Bridge signals: EventBus (worker thread) → Qt main thread
    _regions_signal = pyqtSignal(object)
    _row_signal = pyqtSignal(object)
    _page_changed_signal = pyqtSignal()
    _complete_signal = pyqtSignal()
    _hide_signal = pyqtSignal()
    _config_signal = pyqtSignal(object)

    def __init__(self, *, config: AppConfig, event_bus: EventBus,
                 manager: OverlayManager | None = None):
        super().__init__()
        self._config = config
        self._event_bus = event_bus
        self._overlay_manager = manager
        self._debug = getattr(config, "scan_overlay_debug", False)

        # State
        self._regions: dict | None = None     # Layout bounds from EVENT_DEBUG_REGIONS
        self._matched_rows: list[dict] = []   # Row highlight data
        self._game_focused = False

        # Qt window setup: full-screen, frameless, transparent, always-on-top
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Cover the primary screen
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.setGeometry(geo)

        # Make click-through on Windows
        self.show()
        self._make_click_through()
        self.hide()

        # Connect bridge signals
        self._regions_signal.connect(self._on_regions)
        self._row_signal.connect(self._on_row)
        self._page_changed_signal.connect(self._on_page_changed)
        self._complete_signal.connect(self._on_complete)
        self._hide_signal.connect(self._on_hide)
        self._config_signal.connect(self._on_config_changed)

        # Subscribe to EventBus (store references for unsubscribe)
        self._cb_regions = lambda d: self._regions_signal.emit(d)
        self._cb_row = lambda d: self._row_signal.emit(d)
        self._cb_page = lambda d: self._page_changed_signal.emit()
        self._cb_complete = lambda d: self._complete_signal.emit()
        self._cb_hide = lambda d: self._hide_signal.emit()
        self._cb_config = lambda d: self._config_signal.emit(d)
        event_bus.subscribe(EVENT_DEBUG_REGIONS, self._cb_regions)
        event_bus.subscribe(EVENT_DEBUG_ROW, self._cb_row)
        event_bus.subscribe(EVENT_OCR_PAGE_CHANGED, self._cb_page)
        event_bus.subscribe(EVENT_OCR_COMPLETE, self._cb_complete)
        event_bus.subscribe(EVENT_OCR_OVERLAYS_HIDE, self._cb_hide)
        event_bus.subscribe(EVENT_CONFIG_CHANGED, self._cb_config)

        # Focus polling timer
        self._focus_timer = QTimer(self)
        self._focus_timer.timeout.connect(self._check_focus)
        self._focus_timer.start(FOCUS_POLL_MS)

        # Auto-hide timer
        self._hide_timer: QTimer | None = None

    def set_debug(self, enabled: bool) -> None:
        """Toggle debug mode (draw region boxes)."""
        self._debug = enabled
        self.update()

    # ── Click-through ──────────────────────────────────────────────────

    def _make_click_through(self) -> None:
        """Make the overlay click-through using platform backend."""
        try:
            _platform.set_click_through(int(self.winId()))
        except Exception as e:
            log.warning("Failed to set click-through: %s", e)

    # ── Focus polling ──────────────────────────────────────────────────

    def _check_focus(self) -> None:
        """Show/hide based on whether the game window is in the foreground.

        Uses the OverlayManager's focus state if available — this correctly
        treats our own overlay windows as "game focused" so the highlight
        doesn't hide when the user interacts with e.g. the scan summary.
        """
        if self._overlay_manager is not None:
            focused = self._overlay_manager.game_focused
        elif _platform.supports_focus_detection():
            try:
                title = _platform.get_foreground_window_title()
                focused = title.startswith(GAME_TITLE_PREFIX)
            except Exception:
                focused = False
        else:
            return

        if focused != self._game_focused:
            self._game_focused = focused
            if focused and self._regions is not None:
                self.show()
            elif not focused:
                self.hide()

    # ── Event handlers ─────────────────────────────────────────────────

    def _on_regions(self, data: dict) -> None:
        """Layout regions detected — show overlay and store bounds."""
        self._regions = data
        self._matched_rows.clear()

        # Cancel any pending auto-hide
        if self._hide_timer:
            self._hide_timer.stop()
            self._hide_timer = None

        if self._game_focused:
            self.show()
        self.update()

    def _on_row(self, data: dict) -> None:
        """Row OCR result — add matched rows to highlight list."""
        if data.get("type") != "matched":
            return
        self._matched_rows.append(data)
        self.update()

    def _on_page_changed(self) -> None:
        """Page changed — clear row highlights."""
        self._matched_rows.clear()
        self.update()

    def _on_hide(self) -> None:
        """Skills panel lost — immediately hide overlay."""
        self.hide()
        self._regions = None
        self._matched_rows.clear()
        if self._hide_timer:
            self._hide_timer.stop()
            self._hide_timer = None

    def _on_config_changed(self, config) -> None:
        """Config changed — update debug mode."""
        if config and hasattr(config, "scan_overlay_debug"):
            self._debug = config.scan_overlay_debug
            self.update()

    def _on_complete(self) -> None:
        """Scan complete — auto-hide after a delay."""
        if self._hide_timer:
            self._hide_timer.stop()
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._auto_hide)
        self._hide_timer.start(AUTO_HIDE_DELAY_MS)

    def _auto_hide(self) -> None:
        """Hide the overlay after scan completion delay."""
        self.hide()
        self._regions = None
        self._matched_rows.clear()
        self._hide_timer = None

    # ── Painting ───────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        if self._regions is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Draw row highlights (always)
        self._paint_rows(painter)

        # Draw debug region boxes (only in debug mode)
        if self._debug:
            self._paint_debug_regions(painter)

        painter.end()

    def _paint_rows(self, painter: QPainter) -> None:
        """Draw semi-transparent green highlights over scanned rows."""
        if not self._matched_rows:
            return

        regions = self._regions
        if not regions:
            return

        # Table bounds for the row width
        table = regions.get("table")
        if not table:
            return
        table_x, _, table_w, _ = table

        fill = QBrush(ROW_FILL)
        pen = QPen(ROW_BORDER, 1)
        check_pen = QPen(CHECKMARK_COLOR)

        painter.setFont(CHECKMARK_FONT)

        for row in self._matched_rows:
            y = row.get("y", 0)
            h = row.get("h", 0)
            if y <= 0 or h <= 0:
                continue

            # Row highlight rectangle
            painter.setPen(pen)
            painter.setBrush(fill)
            painter.drawRect(table_x, y, table_w - 30, h)

            # Checkmark at the left edge
            painter.setPen(check_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawText(table_x - 14, y, 14, h,
                             Qt.AlignmentFlag.AlignCenter, "\u2713")

    def _paint_debug_regions(self, painter: QPainter) -> None:
        """Draw colored outlines around detected regions."""
        regions = self._regions
        if not regions:
            return

        def draw_box(rect_data, color, label=""):
            if not rect_data:
                return
            x, y, w, h = rect_data
            pen = QPen(color, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x, y, w, h)
            if label:
                painter.setPen(QPen(color))
                painter.setFont(QFont("Consolas", 8))
                painter.drawText(x + 2, y - 2, label)

        # Window bounds
        draw_box(regions.get("window"), COLOR_WINDOW, "window")

        # Sidebar
        draw_box(regions.get("sidebar"), COLOR_SIDEBAR, "sidebar")

        # Table area
        draw_box(regions.get("table"), COLOR_TABLE, "table")

        # Total row
        draw_box(regions.get("total"), COLOR_TOTAL, "total")

        # Orange indicator bar (ALL CATEGORIES selection)
        draw_box(regions.get("indicator"), COLOR_INDICATOR, "indicator")

        # Pagination
        draw_box(regions.get("pagination"), COLOR_PAGINATION, "pagination")

        # Column regions
        columns = regions.get("columns", {})
        for col_name, rect in columns.items():
            color = COL_COLORS.get(col_name, COLOR_TABLE)
            draw_box(rect, color, col_name)

        # Template match positions
        templates = regions.get("templates", {})
        template_color = QColor(255, 255, 255, 200)
        for tpl_name, rect in templates.items():
            draw_box(rect, template_color, tpl_name)

        # Per-row text cell outlines (name, rank, points) and bar regions
        table = regions.get("table")
        row_height = regions.get("row_height", 0)
        text_split = regions.get("text_split", 0.7)
        col_screen = regions.get("col_screen", {})

        if table and row_height > 0:
            t_x, t_y, t_w, t_h = table
            num_rows = min(12, t_h // row_height) if row_height else 0
            text_h = int(row_height * text_split)

            # Draw text cell outlines per row
            cell_colors = {
                "name":   COLOR_COL_NAME,
                "rank":   COLOR_COL_RANK,
                "points": COLOR_COL_POINTS,
            }
            for col_name, (cx_start, cx_end) in col_screen.items():
                color = cell_colors.get(col_name)
                if not color:
                    continue
                pen = QPen(color, 1, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                cw = cx_end - cx_start
                for ri in range(num_rows):
                    ry = t_y + ri * row_height
                    painter.drawRect(cx_start, ry, cw, text_h)

            # Bar regions (rank_bar = magenta, points_bar = cyan)
            bars = regions.get("bars", {})
            bar_colors = {
                "rank_bar":   QColor(255, 0, 255, 160),   # Magenta
                "points_bar": QColor(0, 255, 255, 160),    # Cyan
            }
            for bar_name, (bx_start, bx_end) in bars.items():
                color = bar_colors.get(bar_name, QColor(255, 255, 255, 160))
                pen = QPen(color, 1)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                bw = bx_end - bx_start
                for ri in range(num_rows):
                    ry = t_y + ri * row_height
                    bar_top = ry + text_h + 2
                    bar_h = row_height - text_h - 3
                    painter.drawRect(bx_start, bar_top, bw, bar_h)
                # Label above table
                painter.setPen(QPen(color))
                painter.setFont(QFont("Consolas", 7))
                painter.drawText(bx_start + 2, t_y - 2, bar_name)

    # ── Cleanup ────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Unsubscribe from events and clean up."""
        self._focus_timer.stop()
        if self._hide_timer:
            self._hide_timer.stop()
        self._event_bus.unsubscribe(EVENT_DEBUG_REGIONS, self._cb_regions)
        self._event_bus.unsubscribe(EVENT_DEBUG_ROW, self._cb_row)
        self._event_bus.unsubscribe(EVENT_OCR_PAGE_CHANGED, self._cb_page)
        self._event_bus.unsubscribe(EVENT_OCR_COMPLETE, self._cb_complete)
        self._event_bus.unsubscribe(EVENT_OCR_OVERLAYS_HIDE, self._cb_hide)
        self._event_bus.unsubscribe(EVENT_CONFIG_CHANGED, self._cb_config)
        self.close()
