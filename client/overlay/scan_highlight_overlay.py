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
    EVENT_CONFIG_CHANGED, EVENT_TARGET_LOCK_UPDATE, EVENT_TARGET_LOCK_LOST,
    EVENT_MARKET_PRICE_DEBUG, EVENT_MARKET_PRICE_LOST,
    EVENT_PLAYER_STATUS_UPDATE, EVENT_PLAYER_STATUS_LOST,
    GAME_TITLE_PREFIX,
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

# Target lock overlay colors
TARGET_LOCK_COLOR = QColor(0, 255, 255, 200)        # Cyan border
TARGET_LOCK_FILL = QColor(0, 255, 255, 25)          # Faint cyan fill
TARGET_LOCK_ROI_HP = QColor(255, 80, 80, 140)       # Red for HP ROI
TARGET_LOCK_ROI_SHARED = QColor(255, 200, 50, 140)  # Gold for Shared ROI
TARGET_LOCK_ROI_NAME = QColor(100, 200, 255, 140)   # Light blue for Name ROI
TARGET_LOCK_LABEL_FONT = QFont("Consolas", 7)

# Market price overlay colors
MP_COLOR = QColor(0, 255, 128, 200)               # Green border (template box)
MP_FILL = QColor(0, 255, 128, 20)                  # Faint green fill
MP_ROI_NAME = QColor(135, 206, 235, 160)           # Sky blue (name rows)
MP_ROI_CELL = QColor(255, 215, 0, 140)             # Gold (data cells)
MP_ROI_TIER = QColor(255, 105, 180, 160)           # Pink (tier)
MP_LABEL_FONT = QFont("Consolas", 7)
MP_VALUE_FONT = QFont("Consolas", 8, QFont.Weight.Bold)

# Player status overlay colors
PS_COLOR = QColor(255, 100, 100, 200)          # Red border (heart)
PS_FILL = QColor(255, 100, 100, 25)            # Faint red fill
PS_ROI_HEALTH = QColor(0, 255, 0, 140)         # Green for health bar
PS_ROI_RELOAD = QColor(255, 165, 0, 140)       # Orange for reload bar
PS_ROI_BUFF = QColor(200, 100, 255, 140)       # Purple for buff bar
PS_ROI_BUFF_SMALL = QColor(150, 100, 255, 140) # Light purple for small buff bar
PS_ROI_TOOL_NAME = QColor(255, 255, 100, 140)  # Yellow for tool name
PS_LABEL_FONT = QFont("Consolas", 7)


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
    _target_lock_signal = pyqtSignal(object)
    _target_lock_lost_signal = pyqtSignal()
    _market_price_signal = pyqtSignal(object)
    _market_price_lost_signal = pyqtSignal()
    _player_status_signal = pyqtSignal(object)
    _player_status_lost_signal = pyqtSignal()

    def __init__(self, *, config: AppConfig, event_bus: EventBus,
                 manager: OverlayManager | None = None):
        super().__init__()
        self._config = config
        self._event_bus = event_bus
        self._overlay_manager = manager
        self._debug = getattr(config, "scan_overlay_debug", False)

        # State — scan highlight
        self._regions: dict | None = None     # Layout bounds from EVENT_DEBUG_REGIONS
        self._matched_rows: list[dict] = []   # Row highlight data
        self._game_focused = False

        # State — target lock
        self._target_lock_data: dict | None = None  # Last target lock update

        # State — market price
        self._market_price_data: dict | None = None  # Last market price debug update

        # State — player status
        self._player_status_data: dict | None = None  # Last player status update

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

        # Make click-through on Windows.
        # Briefly show to get a valid HWND, but at 0 opacity to prevent a dark flash.
        self.setWindowOpacity(0)
        self.show()
        self._make_click_through()
        self.hide()
        self.setWindowOpacity(1)

        # Connect bridge signals
        self._regions_signal.connect(self._on_regions)
        self._row_signal.connect(self._on_row)
        self._page_changed_signal.connect(self._on_page_changed)
        self._complete_signal.connect(self._on_complete)
        self._hide_signal.connect(self._on_hide)
        self._config_signal.connect(self._on_config_changed)
        self._target_lock_signal.connect(self._on_target_lock_update)
        self._target_lock_lost_signal.connect(self._on_target_lock_lost)
        self._market_price_signal.connect(self._on_market_price_debug)
        self._market_price_lost_signal.connect(self._on_market_price_lost)
        self._player_status_signal.connect(self._on_player_status_update)
        self._player_status_lost_signal.connect(self._on_player_status_lost)

        # Subscribe to EventBus (store references for unsubscribe)
        self._cb_regions = lambda d: self._regions_signal.emit(d)
        self._cb_row = lambda d: self._row_signal.emit(d)
        self._cb_page = lambda d: self._page_changed_signal.emit()
        self._cb_complete = lambda d: self._complete_signal.emit()
        self._cb_hide = lambda d: self._hide_signal.emit()
        self._cb_config = lambda d: self._config_signal.emit(d)
        self._cb_target_lock = lambda d: self._target_lock_signal.emit(d)
        self._cb_target_lock_lost = lambda d: self._target_lock_lost_signal.emit()
        self._cb_market_price = lambda d: self._market_price_signal.emit(d)
        self._cb_market_price_lost = lambda d: self._market_price_lost_signal.emit()
        self._cb_player_status = lambda d: self._player_status_signal.emit(d)
        self._cb_player_status_lost = lambda d: self._player_status_lost_signal.emit()
        event_bus.subscribe(EVENT_DEBUG_REGIONS, self._cb_regions)
        event_bus.subscribe(EVENT_DEBUG_ROW, self._cb_row)
        event_bus.subscribe(EVENT_OCR_PAGE_CHANGED, self._cb_page)
        event_bus.subscribe(EVENT_OCR_COMPLETE, self._cb_complete)
        event_bus.subscribe(EVENT_OCR_OVERLAYS_HIDE, self._cb_hide)
        event_bus.subscribe(EVENT_CONFIG_CHANGED, self._cb_config)
        event_bus.subscribe(EVENT_TARGET_LOCK_UPDATE, self._cb_target_lock)
        event_bus.subscribe(EVENT_TARGET_LOCK_LOST, self._cb_target_lock_lost)
        event_bus.subscribe(EVENT_MARKET_PRICE_DEBUG, self._cb_market_price)
        event_bus.subscribe(EVENT_MARKET_PRICE_LOST, self._cb_market_price_lost)
        event_bus.subscribe(EVENT_PLAYER_STATUS_UPDATE, self._cb_player_status)
        event_bus.subscribe(EVENT_PLAYER_STATUS_LOST, self._cb_player_status_lost)

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
            has_content = (self._regions is not None
                          or self._target_lock_data is not None
                          or self._market_price_data is not None
                          or self._player_status_data is not None)
            if focused and has_content:
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

    def _on_target_lock_update(self, data: dict) -> None:
        """Target lock detected — store position and repaint."""
        self._target_lock_data = data
        if self._game_focused and self._debug:
            if not self.isVisible():
                self.show()
            self.update()

    def _on_target_lock_lost(self) -> None:
        """Target lock lost — clear and repaint."""
        self._target_lock_data = None
        self.update()
        # Hide if no other content
        if (self._regions is None and self._market_price_data is None
                and self._player_status_data is None):
            self.hide()

    def _on_market_price_debug(self, data: dict) -> None:
        """Market price window detected — store position and repaint."""
        self._market_price_data = data
        if self._game_focused and self._debug:
            if not self.isVisible():
                self.show()
            self.update()

    def _on_market_price_lost(self) -> None:
        """Market price window lost — clear and repaint."""
        self._market_price_data = None
        self.update()
        if (self._regions is None and self._target_lock_data is None
                and self._player_status_data is None):
            self.hide()

    def _on_player_status_update(self, data: dict) -> None:
        """Player heart detected — store position and repaint."""
        self._player_status_data = data
        if self._game_focused:
            if not self.isVisible():
                self.show()
            self.update()

    def _on_player_status_lost(self) -> None:
        """Player heart lost — clear and repaint."""
        self._player_status_data = None
        self.update()
        if (self._regions is None and self._target_lock_data is None
                and self._market_price_data is None):
            self.hide()

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
        has_scan = self._regions is not None
        has_lock = self._target_lock_data is not None
        has_mp = self._market_price_data is not None
        has_ps = self._player_status_data is not None
        if not has_scan and not has_lock and not has_mp and not has_ps:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Draw scan row highlights
        if has_scan:
            self._paint_rows(painter)
            if self._debug:
                self._paint_debug_regions(painter)

        # Draw target lock indicator
        if has_lock:
            self._paint_target_lock(painter)

        # Draw market price debug overlay (debug mode only)
        if has_mp and self._debug:
            self._paint_market_price(painter)

        # Draw player status indicator
        if has_ps:
            self._paint_player_status(painter)

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

    def _paint_target_lock(self, painter: QPainter) -> None:
        """Draw debug overlay for target lock (debug mode only)."""
        if not self._debug:
            return

        data = self._target_lock_data
        if not data:
            return

        x = data.get("x", 0)
        y = data.get("y", 0)
        w = data.get("w", 0)
        h = data.get("h", 0)
        if w <= 0 or h <= 0:
            return

        # Template bounding box
        painter.setPen(QPen(TARGET_LOCK_COLOR, 1))
        painter.setBrush(QBrush(TARGET_LOCK_FILL))
        painter.drawRect(x, y, w, h)

        # ROI boxes
        self._paint_target_lock_rois(painter, x, y)

    def _paint_target_lock_rois(self, painter: QPainter, tx: int, ty: int) -> None:
        """Draw labeled ROI boxes relative to template position (debug only)."""
        rois = [
            ("HP", getattr(self._config, "target_lock_roi_hp", None), TARGET_LOCK_ROI_HP),
            ("Shared", getattr(self._config, "target_lock_roi_shared", None), TARGET_LOCK_ROI_SHARED),
            ("Name", getattr(self._config, "target_lock_roi_name", None), TARGET_LOCK_ROI_NAME),
        ]
        for label, roi, color in rois:
            if not roi:
                continue
            dx = roi.get("dx", 0)
            dy = roi.get("dy", 0)
            rw = roi.get("w", 0)
            rh = roi.get("h", 0)
            if rw <= 0 or rh <= 0:
                continue
            rx, ry = tx + dx, ty + dy
            painter.setPen(QPen(color, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rx, ry, rw, rh)
            painter.setFont(TARGET_LOCK_LABEL_FONT)
            painter.drawText(rx + 2, ry - 2, label)

    # ── Market price debug ────────────────────────────────────────────

    def _paint_market_price(self, painter: QPainter) -> None:
        """Draw debug overlay for the market price window (debug mode only)."""
        data = self._market_price_data
        if not data:
            return

        x = data.get("x", 0)
        y = data.get("y", 0)
        w = data.get("w", 0)
        h = data.get("h", 0)
        if w <= 0 or h <= 0:
            return

        confidence = data.get("confidence", 0)
        parsed = data.get("data", {})

        # Template bounding box
        painter.setPen(QPen(MP_COLOR, 2))
        painter.setBrush(QBrush(MP_FILL))
        painter.drawRect(x, y, w, h)

        # Confidence label above template
        painter.setFont(MP_VALUE_FONT)
        painter.setPen(QPen(MP_COLOR))
        painter.drawText(x, y - 4, f"MARKET PRICE ({confidence:.0%})")

        self._paint_market_price_rois(painter, x, y, parsed)

    def _paint_market_price_rois(self, painter: QPainter, tx: int, ty: int,
                                  parsed: dict) -> None:
        """Draw labeled ROI boxes for market price window regions."""
        cfg = self._config

        def draw_roi(roi, color, label, value_text=""):
            if not roi:
                return
            dx = roi.get("dx", 0)
            dy = roi.get("dy", 0)
            rw = roi.get("w", 0)
            rh = roi.get("h", 0)
            if rw <= 0 or rh <= 0:
                return
            rx, ry = tx + dx, ty + dy
            painter.setPen(QPen(color, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rx, ry, rw, rh)
            # Label above box
            painter.setFont(MP_LABEL_FONT)
            painter.drawText(rx + 2, ry - 2, label)
            # Value text to the right of the box (avoids overlapping game text)
            if value_text:
                painter.setFont(MP_VALUE_FONT)
                painter.setPen(QPen(QColor(255, 255, 255, 220)))
                painter.drawText(
                    rx + rw + 4, ry, 200, rh,
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    value_text,
                )

        # Name rows
        name = parsed.get("item_name", "")
        roi_r1 = getattr(cfg, "market_price_roi_name_row1", None)
        roi_r2 = getattr(cfg, "market_price_roi_name_row2", None)
        draw_roi(roi_r1, MP_ROI_NAME, "Name R1", name if name else "—")
        draw_roi(roi_r2, MP_ROI_NAME, "Name R2")

        # Tier
        tier = parsed.get("tier")
        roi_tier = getattr(cfg, "market_price_roi_tier", None)
        draw_roi(roi_tier, MP_ROI_TIER, "Tier",
                 str(tier) if tier is not None else "—")

        # Data cells (5 periods × 2 columns)
        roi_first = getattr(cfg, "market_price_roi_first_cell", None)
        cell_offset = getattr(cfg, "market_price_cell_offset", None)
        if roi_first and cell_offset:
            cell_w = roi_first.get("w", 0)
            cell_h = roi_first.get("h", 0)
            first_dx = roi_first.get("dx", 0)
            first_dy = roi_first.get("dy", 0)
            off_x = cell_offset.get("x", 0)
            off_y = cell_offset.get("y", 0)

            periods = ["1d", "7d", "30d", "90d", "365d"]
            metrics = ["markup", "sales"]
            for row_idx, period in enumerate(periods):
                for col_idx, metric in enumerate(metrics):
                    cell_dx = first_dx + col_idx * off_x
                    cell_dy = first_dy + row_idx * off_y
                    cell_roi = {"dx": cell_dx, "dy": cell_dy,
                                "w": cell_w, "h": cell_h}
                    key = f"{metric}_{period}"
                    val = parsed.get(key)
                    val_str = f"{val}" if val is not None else "—"
                    label = f"{metric[0].upper()}{period}"
                    draw_roi(cell_roi, MP_ROI_CELL, label, val_str)

    # ── Player status (heart) ────────────────────────────────────────

    def _paint_player_status(self, painter: QPainter) -> None:
        """Draw rectangle around detected heart icon and ROI boxes in debug mode."""
        data = self._player_status_data
        if not data:
            return

        x = data.get("x", 0)
        y = data.get("y", 0)
        w = data.get("w", 0)
        h = data.get("h", 0)
        if w <= 0 or h <= 0:
            return

        # Template bounding box
        painter.setPen(QPen(PS_COLOR, 1))
        painter.setBrush(QBrush(PS_FILL))
        painter.drawRect(x, y, w, h)

        # Debug mode: draw ROI boxes
        if self._debug:
            self._paint_player_status_rois(painter, x, y)

    def _paint_player_status_rois(self, painter: QPainter, tx: int, ty: int) -> None:
        """Draw labeled ROI boxes relative to heart template position (debug only)."""
        rois = [
            ("Health", getattr(self._config, "player_status_roi_health", None), PS_ROI_HEALTH),
            ("Reload", getattr(self._config, "player_status_roi_reload", None), PS_ROI_RELOAD),
            ("Buff", getattr(self._config, "player_status_roi_buff", None), PS_ROI_BUFF),
            ("Buff (S)", getattr(self._config, "player_status_roi_buff_small", None), PS_ROI_BUFF_SMALL),
            ("Tool", getattr(self._config, "player_status_roi_tool_name", None), PS_ROI_TOOL_NAME),
        ]
        for label, roi, color in rois:
            if not roi:
                continue
            dx = roi.get("dx", 0)
            dy = roi.get("dy", 0)
            rw = roi.get("w", 0)
            rh = roi.get("h", 0)
            if rw <= 0 or rh <= 0:
                continue
            rx, ry = tx + dx, ty + dy
            painter.setPen(QPen(color, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rx, ry, rw, rh)
            painter.setFont(PS_LABEL_FONT)
            painter.drawText(rx + 2, ry - 2, label)

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
        self._event_bus.unsubscribe(EVENT_TARGET_LOCK_UPDATE, self._cb_target_lock)
        self._event_bus.unsubscribe(EVENT_TARGET_LOCK_LOST, self._cb_target_lock_lost)
        self._event_bus.unsubscribe(EVENT_MARKET_PRICE_DEBUG, self._cb_market_price)
        self._event_bus.unsubscribe(EVENT_MARKET_PRICE_LOST, self._cb_market_price_lost)
        self._event_bus.unsubscribe(EVENT_PLAYER_STATUS_UPDATE, self._cb_player_status)
        self._event_bus.unsubscribe(EVENT_PLAYER_STATUS_LOST, self._cb_player_status_lost)
        self.close()
