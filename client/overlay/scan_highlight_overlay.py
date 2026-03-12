"""Scan highlight overlay — click-through Qt overlay for skill scan visualization.

Highlights successfully scanned rows over the game's skills window. In debug
mode, also draws colored boxes around all detected regions (window, sidebar,
table, columns, pagination).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont

from ..core.event_bus import EventBus
from ..core.build_flags import is_dev_build
from ..core.constants import (
    EVENT_DEBUG_ROW, EVENT_DEBUG_REGIONS,
    EVENT_OCR_PAGE_CHANGED, EVENT_OCR_COMPLETE, EVENT_OCR_OVERLAYS_HIDE,
    EVENT_CONFIG_CHANGED, EVENT_TARGET_LOCK_UPDATE, EVENT_TARGET_LOCK_LOST,
    EVENT_MARKET_PRICE_DEBUG, EVENT_MARKET_PRICE_LOST,
    EVENT_PLAYER_STATUS_UPDATE, EVENT_PLAYER_STATUS_LOST,
    EVENT_SKILLS_TEMPLATE_DEBUG,
    EVENT_RADAR_COORDINATES, EVENT_RADAR_LOST, EVENT_RADAR_DEBUG,
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
ROW_WINDOW_BORDER = QColor(0, 221, 102, 220)  # Border around active green overlay area
CHECKMARK_COLOR = QColor(0, 221, 102)

# Skills template ROI colors (used by both debug overlay and scan highlights)
COLOR_TOTAL = QColor(255, 200, 51, 180)     # Gold
COLOR_INDICATOR = QColor(255, 140, 0, 200)  # Dark orange
COLOR_COL_NAME = QColor(51, 153, 255, 180)   # Blue
COLOR_COL_RANK = QColor(255, 153, 51, 180)   # Orange
COLOR_COL_POINTS = QColor(51, 221, 221, 180) # Teal
COLOR_BAR_RANK = QColor(255, 100, 100, 160)    # Red for rank bar
COLOR_BAR_POINTS = QColor(100, 255, 100, 160)  # Green for points bar

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

# Skills template overlay colors
ST_COLOR_OK = QColor(0, 200, 255, 200)         # Cyan border (matched)
ST_COLOR_FAIL = QColor(255, 80, 80, 200)        # Red border (below threshold)
ST_FILL = QColor(0, 200, 255, 20)               # Faint cyan fill
ST_LABEL_FONT = QFont("Consolas", 8, QFont.Weight.Bold)

# Player status overlay colors
PS_COLOR = QColor(255, 100, 100, 200)          # Red border (heart)
PS_FILL = QColor(255, 100, 100, 25)            # Faint red fill
PS_ROI_HEALTH = QColor(0, 255, 0, 140)         # Green for health bar
PS_ROI_RELOAD = QColor(255, 165, 0, 140)       # Orange for reload bar
PS_ROI_BUFF = QColor(200, 100, 255, 140)       # Purple for buff bar
PS_ROI_BUFF_SMALL = QColor(150, 100, 255, 140) # Light purple for small buff bar
PS_ROI_TOOL_NAME = QColor(255, 255, 100, 140)  # Yellow for tool name
PS_LABEL_FONT = QFont("Consolas", 7)

# Radar overlay colors
RADAR_COLOR      = QColor(255, 165,   0, 200)  # Orange border (radar circle)
RADAR_FILL       = QColor(255, 165,   0,  18)  # Faint orange fill
RADAR_WARN       = QColor(255,  80,  80, 220)  # Red for recalibration warning
RADAR_LABEL_FONT = QFont("Consolas", 7)
RADAR_COORD_FONT = QFont("Consolas", 9, QFont.Weight.Bold)


def _radar_overlay_enabled(config: "AppConfig") -> bool:
    """Radar overlay is enabled only in dev builds and when radar is enabled."""
    return is_dev_build() and getattr(config, "radar_enabled", True)


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
    _skills_template_signal = pyqtSignal(object)
    _player_status_signal = pyqtSignal(object)
    _player_status_lost_signal = pyqtSignal()
    _radar_signal = pyqtSignal(object)
    _radar_lost_signal = pyqtSignal()
    _radar_debug_signal = pyqtSignal(object)

    def __init__(self, *, config: AppConfig, event_bus: EventBus,
                 manager: OverlayManager | None = None):
        super().__init__()
        self._config = config
        self._event_bus = event_bus
        self._overlay_manager = manager
        self._debug = getattr(config, "scan_overlay_debug", False)
        self._radar_overlay_enabled = _radar_overlay_enabled(config)

        # State — scan highlight
        self._regions: dict | None = None     # Layout bounds from EVENT_DEBUG_REGIONS
        self._matched_rows: list[dict] = []   # Row highlight data
        self._game_focused = False
        self._game_screen_dpr: float = 1.0    # DPI of the screen the game is on
        self._game_origin: tuple[int, int] | None = None  # Physical screen pos of game window
        self._phys_origin: tuple[int, int] = (0, 0)  # Physical origin of overlay HWND

        # State — target lock
        self._target_lock_data: dict | None = None  # Last target lock update

        # State — market price (supports multiple simultaneous windows)
        self._market_price_windows: list[dict] = []
        self._mp_current_tick: int = 0  # timestamp hash for tick dedup

        # State — skills template
        self._skills_template_data: dict | None = None  # Last skills template match

        # State — player status
        self._player_status_data: dict | None = None  # Last player status update

        # State — radar
        self._radar_data: dict | None = None           # Last radar coordinate update
        self._radar_circle: dict | None = None         # Circle position (no OCR yet)
        self._radar_needs_recal: bool = False          # Recalibration requested

        # Qt window setup: full-screen, frameless, transparent, always-on-top
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Cover the entire virtual desktop (all monitors)
        from PyQt6.QtWidgets import QApplication
        screens = QApplication.screens()
        if screens:
            geo = screens[0].geometry()
            for s in screens[1:]:
                geo = geo.united(s.geometry())
            self.setGeometry(geo)
            for s in screens:
                sg = s.geometry()
                dpr = s.devicePixelRatio()
                log.info("Screen %s: logical=%dx%d+%d+%d dpr=%.2f physical=%dx%d",
                         s.name(), sg.width(), sg.height(), sg.x(), sg.y(), dpr,
                         int(sg.width() * dpr), int(sg.height() * dpr))
            log.info("Overlay widget geometry: %dx%d+%d+%d",
                     geo.width(), geo.height(), geo.x(), geo.y())

        # Make click-through on Windows without showing a startup overlay window.
        self.winId()  # Force native window creation while still hidden.
        self._make_click_through()
        # Qt sets widget geometry in logical pixels, but OCR coordinates are
        # physical pixels (Win32 PER_MONITOR_AWARE_V2).  On high-DPI screens
        # physical coords exceed the logical widget bounds and get clipped.
        # Resize the underlying HWND to physical extent via Win32 directly,
        # bypassing Qt's logical→physical scaling.
        self._resize_to_physical()
        self.hide()

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
        self._skills_template_signal.connect(self._on_skills_template_debug)
        self._player_status_signal.connect(self._on_player_status_update)
        self._player_status_lost_signal.connect(self._on_player_status_lost)
        self._radar_signal.connect(self._on_radar_update)
        self._radar_lost_signal.connect(self._on_radar_lost)
        self._radar_debug_signal.connect(self._on_radar_debug)

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
        self._cb_skills_template = lambda d: self._skills_template_signal.emit(d)
        self._cb_player_status = lambda d: self._player_status_signal.emit(d)
        self._cb_player_status_lost = lambda d: self._player_status_lost_signal.emit()
        self._cb_radar = lambda d: self._radar_signal.emit(d)
        self._cb_radar_lost = lambda d: self._radar_lost_signal.emit()
        self._cb_radar_debug = lambda d: self._radar_debug_signal.emit(d)
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
        event_bus.subscribe(EVENT_SKILLS_TEMPLATE_DEBUG, self._cb_skills_template)
        event_bus.subscribe(EVENT_PLAYER_STATUS_UPDATE, self._cb_player_status)
        event_bus.subscribe(EVENT_PLAYER_STATUS_LOST, self._cb_player_status_lost)
        if self._radar_overlay_enabled:
            event_bus.subscribe(EVENT_RADAR_COORDINATES, self._cb_radar)
            event_bus.subscribe(EVENT_RADAR_LOST, self._cb_radar_lost)
            event_bus.subscribe(EVENT_RADAR_DEBUG, self._cb_radar_debug)

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

    def _resize_to_physical(self) -> None:
        """Resize the overlay HWND to cover the physical virtual desktop.

        Qt sizes the widget in logical pixels, but the QPainter on a
        PER_MONITOR_AWARE_V2 process paints in physical pixel coordinates.
        Use Win32 GetSystemMetrics + SetWindowPos to expand the HWND to
        physical dimensions so that painting at physical coords is not clipped.
        """
        import sys
        if sys.platform != "win32":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = int(self.winId())

            # GetSystemMetrics returns physical pixels for DPI-aware processes
            SM_XVIRTUALSCREEN = 76
            SM_YVIRTUALSCREEN = 77
            SM_CXVIRTUALSCREEN = 78
            SM_CYVIRTUALSCREEN = 79
            vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            user32.SetWindowPos(
                hwnd, 0, vx, vy, vw, vh,
                SWP_NOZORDER | SWP_NOACTIVATE,
            )
            self._phys_origin = (vx, vy)
            log.info("Resized overlay HWND to physical: (%d,%d)+%dx%d",
                     vx, vy, vw, vh)
        except Exception as e:
            log.warning("Failed to resize overlay to physical extent: %s", e)

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
                          or len(self._market_price_windows) > 0
                          or self._player_status_data is not None
                          or self._skills_template_data is not None
                          or (self._radar_overlay_enabled and (
                              self._radar_data is not None
                              or self._radar_circle is not None
                          )))
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
        """Config changed — update debug mode and clear stale overlay data."""
        if not config:
            return
        if hasattr(config, "scan_overlay_debug"):
            self._debug = config.scan_overlay_debug
        radar_enabled = _radar_overlay_enabled(config)
        if radar_enabled != self._radar_overlay_enabled:
            self._radar_overlay_enabled = radar_enabled
            if radar_enabled:
                self._event_bus.subscribe(EVENT_RADAR_COORDINATES, self._cb_radar)
                self._event_bus.subscribe(EVENT_RADAR_LOST, self._cb_radar_lost)
                self._event_bus.subscribe(EVENT_RADAR_DEBUG, self._cb_radar_debug)
            else:
                self._event_bus.unsubscribe(EVENT_RADAR_COORDINATES, self._cb_radar)
                self._event_bus.unsubscribe(EVENT_RADAR_LOST, self._cb_radar_lost)
                self._event_bus.unsubscribe(EVENT_RADAR_DEBUG, self._cb_radar_debug)

        # Clear stale data for disabled components
        if not getattr(config, "target_lock_enabled", True):
            self._target_lock_data = None
        if not getattr(config, "market_price_enabled", True):
            self._market_price_windows.clear()
        if not getattr(config, "player_status_enabled", True):
            self._player_status_data = None
        if not self._radar_overlay_enabled:
            self._radar_data = None
            self._radar_circle = None
            self._radar_needs_recal = False

        self.update()
        # Hide if nothing to show
        if (self._regions is None and self._target_lock_data is None
                and len(self._market_price_windows) == 0
                and self._player_status_data is None
                and self._skills_template_data is None
                and (not self._radar_overlay_enabled or (
                    self._radar_data is None and self._radar_circle is None
                ))):
            self.hide()

    def _on_target_lock_update(self, data: dict) -> None:
        """Target lock detected — store position and repaint."""
        self._target_lock_data = data
        self._update_game_origin(data)
        if self._game_focused and self._debug:
            if not self.isVisible():
                self.show()
            self.update()

    def _on_target_lock_lost(self) -> None:
        """Target lock lost — clear and repaint."""
        self._target_lock_data = None
        self.update()
        # Hide if no other content
        if (self._regions is None and len(self._market_price_windows) == 0
                and self._player_status_data is None):
            self.hide()

    def _on_skills_template_debug(self, data: dict) -> None:
        """Skills template match attempted — store and repaint."""
        prev = self._skills_template_data
        if not prev or prev.get("x") != data.get("x") or prev.get("y") != data.get("y"):
            rois = data.get("rois", {})
            fr = rois.get("first_row", (0, 0, 0, 0))
            log.info("Skills template: tpl=(%d,%d)+%dx%d first_row=(%d,%d) "
                     "widget=(%d,%d)+%dx%d dpr=%.2f",
                     data.get("x", 0), data.get("y", 0),
                     data.get("w", 0), data.get("h", 0),
                     fr[0], fr[1],
                     self.x(), self.y(), self.width(), self.height(),
                     self._game_screen_dpr)
        self._skills_template_data = data
        self._update_game_origin(data)
        if self._game_focused and self._debug:
            if not self.isVisible():
                self.show()
            self.update()

    def _on_market_price_debug(self, data: dict) -> None:
        """Market price window detected — accumulate for this tick and repaint.

        Multiple events arrive per tick when several market price windows are
        open.  We detect a new tick via the monotonic tick_seq counter from
        the detector (immune to cached/reused timestamps on the fast path).
        """
        tick_seq = data.get("tick_seq", 0)
        if tick_seq != self._mp_current_tick:
            self._mp_current_tick = tick_seq
            self._market_price_windows.clear()
        self._market_price_windows.append(data)
        self._update_game_origin(data)
        if self._game_focused and self._debug:
            if not self.isVisible():
                self.show()
            self.update()

    def _on_market_price_lost(self) -> None:
        """Market price window lost — clear and repaint."""
        self._market_price_windows.clear()
        self.update()
        if (self._regions is None and self._target_lock_data is None
                and self._player_status_data is None):
            self.hide()

    def _on_player_status_update(self, data: dict) -> None:
        """Player heart detected — store position and repaint."""
        self._player_status_data = data
        self._update_game_origin(data)
        if self._game_focused:
            if not self.isVisible():
                self.show()
            self.update()

    def _on_player_status_lost(self) -> None:
        """Player heart lost — clear and repaint."""
        self._player_status_data = None
        self.update()
        if (self._regions is None and self._target_lock_data is None
                and len(self._market_price_windows) == 0):
            self.hide()

    def _on_radar_update(self, data: dict) -> None:
        """Radar coordinates received — store and repaint."""
        if not self._radar_overlay_enabled:
            return
        self._radar_data = data
        self._radar_needs_recal = False
        self._update_game_origin(data)
        if self._game_focused:
            if not self.isVisible():
                self.show()
            self.update()

    def _on_radar_lost(self) -> None:
        """Radar circle lost — clear and repaint."""
        if not self._radar_overlay_enabled:
            return
        self._radar_data = None
        self._radar_circle = None
        self._radar_needs_recal = False
        self.update()
        if (self._regions is None and self._target_lock_data is None
                and len(self._market_price_windows) == 0
                and self._player_status_data is None):
            self.hide()

    def _on_radar_debug(self, data: dict) -> None:
        """Radar debug event — circle position update and/or recalibration notice."""
        if not self._radar_overlay_enabled:
            return
        if data.get("needs_recalibrate"):
            self._radar_needs_recal = True
        if "circle_cx" in data:
            self._radar_circle = data
            if self._game_focused and not self.isVisible():
                self.show()
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

    # ── DPI detection ─────────────────────────────────────────────────

    def _update_game_origin(self, data: dict) -> None:
        """Update game origin and detect the DPI of the game's screen.

        The game origin (physical screen position of the game client area)
        is used to correct overlay placement on high-DPI monitors.
        """
        origin = data.get("game_origin")
        if not origin:
            return
        gx, gy = origin
        if self._game_origin is not None and gx == self._game_origin[0] and gy == self._game_origin[1]:
            return
        self._game_origin = (gx, gy)

        # Detect which screen the game is on
        from PyQt6.QtWidgets import QApplication
        for screen in QApplication.screens():
            geo = screen.geometry()
            dpr = screen.devicePixelRatio()
            if geo.contains(int(gx / dpr), int(gy / dpr)):
                if dpr != self._game_screen_dpr:
                    log.info("Game screen DPI: %.2f (screen %s, origin %d,%d)",
                             dpr, screen.name(), gx, gy)
                    self._game_screen_dpr = dpr
                return

    # ── Painting ───────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        # Clear previous frame (WA_TranslucentBackground doesn't auto-clear)
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.end()

        has_scan  = self._regions is not None
        has_lock  = self._target_lock_data is not None
        has_mp    = len(self._market_price_windows) > 0
        has_ps    = self._player_status_data is not None
        has_st    = self._skills_template_data is not None
        has_radar = self._radar_overlay_enabled and (
            self._radar_data is not None or self._radar_circle is not None
        )
        if not has_scan and not has_lock and not has_mp and not has_ps and not has_st and not has_radar:
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            # Translate so screen-absolute physical coords map to widget-local.
            # Use stored physical origin (from SetWindowPos) rather than self.x()/y()
            # which may be in logical pixels.
            px, py = self._phys_origin
            painter.translate(-px, -py)

            # Draw scan row highlights
            if has_scan:
                self._paint_rows(painter)

            # Draw skills template match (debug mode only)
            if has_st and self._debug:
                self._paint_skills_template(painter)

            # Draw target lock indicator
            if has_lock:
                self._paint_target_lock(painter)

            # Draw market price debug overlay (debug mode only)
            if has_mp and self._debug:
                self._paint_market_price(painter)

            # Draw player status indicator
            if has_ps:
                self._paint_player_status(painter)

            # Draw radar circle and coordinates
            if has_radar:
                self._paint_radar(painter)
        finally:
            painter.end()

    def _paint_rows(self, painter: QPainter) -> None:
        """Draw semi-transparent green highlights over scanned rows."""
        if not self._matched_rows:
            return

        # Get table position from skills template ROIs (primary) or regions (fallback)
        first_row = None
        row_pitch = None
        table_w = 0
        if self._skills_template_data and self._skills_template_data.get("matched"):
            rois = self._skills_template_data.get("rois", {})
            first_row = rois.get("first_row")
            row_pitch = self._skills_template_data.get("row_pitch")
            table_w = self._skills_template_data.get("table_width", 0)
        if not first_row and self._regions:
            tbl = self._regions.get("table")
            if tbl:
                first_row = tbl
                table_w = tbl[2]
        if not first_row:
            return
        table_x, table_y = first_row[0], first_row[1]

        fill = QBrush(ROW_FILL)
        pen = QPen(ROW_BORDER, 1)
        check_pen = QPen(CHECKMARK_COLOR)
        frame_pen = QPen(ROW_WINDOW_BORDER, 1)
        min_row_y = None
        max_row_y = None

        painter.setFont(CHECKMARK_FONT)

        for row in self._matched_rows:
            h = row.get("h", 0)
            if h <= 0:
                continue
            # Compute y dynamically from current first_row ROI + row index
            row_idx = row.get("row_idx")
            if row_idx is not None and row_pitch:
                y = table_y + row_idx * row_pitch
            else:
                y = row.get("y", 0)
            if y <= 0:
                continue

            # Row highlight rectangle
            painter.setPen(pen)
            painter.setBrush(fill)
            painter.drawRect(table_x, y, table_w, h)
            min_row_y = y if min_row_y is None else min(min_row_y, y)
            max_row_y = (y + h) if max_row_y is None else max(max_row_y, y + h)

            # Checkmark at the left edge
            painter.setPen(check_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawText(table_x - 14, y, 14, h,
                             Qt.AlignmentFlag.AlignCenter, "\u2713")

        if min_row_y is not None and max_row_y is not None and table_w > 0:
            painter.setPen(frame_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(
                table_x - 1,
                min_row_y - 1,
                table_w + 2,
                (max_row_y - min_row_y) + 2,
            )

    def _paint_skills_template(self, painter: QPainter) -> None:
        """Draw debug overlay for skills template match and ROIs."""
        data = self._skills_template_data
        if not data:
            return

        x = data.get("x", 0)
        y = data.get("y", 0)
        w = data.get("w", 0)
        h = data.get("h", 0)
        confidence = data.get("confidence", 0)
        matched = data.get("matched", False)
        if w <= 0 or h <= 0:
            return

        # Hide no-match box unless confidence is near the threshold (≥50%)
        if not matched and confidence < 0.50:
            return

        color = ST_COLOR_OK if matched else ST_COLOR_FAIL
        painter.setPen(QPen(color, 2))
        painter.setBrush(QBrush(ST_FILL))
        painter.drawRect(x, y, w, h)

        # Confidence label above template box
        painter.setFont(ST_LABEL_FONT)
        painter.setPen(QPen(color))
        status = "MATCHED" if matched else "NO MATCH"
        painter.drawText(x, y - 4, f"SKILLS ({confidence:.0%}) {status}")

        # Draw ROIs when template matched
        if not matched:
            return

        rois = data.get("rois", {})
        roi_colors = {
            "first_row":  QColor(0, 255, 255, 120),   # Cyan
            "total":      COLOR_TOTAL,
            "indicator":  COLOR_INDICATOR,
            # row_offset is a relative dimension, not a position — shown via row grid instead
        }
        painter.setFont(QFont("Consolas", 7))
        for roi_name, (rx, ry, rw, rh) in rois.items():
            rc = roi_colors.get(roi_name)
            if not rc:
                continue
            painter.setPen(QPen(rc, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if rw > 0 and rh > 0:
                painter.drawRect(rx, ry, rw, rh)
            painter.drawText(rx + 2, ry - 2, roi_name)

        # Draw column ranges with row grid (12 rows)
        col_ranges = data.get("col_ranges", {})
        row_height = data.get("row_height", 0)
        row_pitch = data.get("row_pitch", row_height)
        first_row = rois.get("first_row")
        if col_ranges and row_height > 0 and first_row:
            t_y = first_row[1]
            num_rows = 12
            text_h = int(row_height * 0.70)

            # Per-row column cells
            col_colors = {
                "name":   COLOR_COL_NAME,
                "rank":   COLOR_COL_RANK,
                "points": COLOR_COL_POINTS,
            }
            for col_name, (cx_start, cx_end) in col_ranges.items():
                cc = col_colors.get(col_name)
                if not cc:
                    continue
                painter.setPen(QPen(cc, 1, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                cw = cx_end - cx_start
                for ri in range(num_rows):
                    ry = t_y + ri * row_pitch
                    painter.drawRect(cx_start, ry, cw, text_h)

        # Bar ranges (positioned via bar_offset ROI)
        bar_ranges = data.get("bar_ranges", {})
        bar_offset_roi = rois.get("bar_offset")
        if bar_ranges and first_row and bar_offset_roi:
            t_y = first_row[1]
            num_rows = 12
            _, bar_y_off, _, bar_h = bar_offset_roi
            if bar_h > 0:
                bar_colors = {
                    "rank":   COLOR_BAR_RANK,
                    "points": COLOR_BAR_POINTS,
                }
                for bar_name, (bx_start, bx_end) in bar_ranges.items():
                    bc = bar_colors.get(bar_name)
                    if not bc:
                        continue
                    painter.setPen(QPen(bc, 1, Qt.PenStyle.DotLine))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    bw = bx_end - bx_start
                    for ri in range(num_rows):
                        ry = t_y + ri * row_pitch + bar_y_off
                        painter.drawRect(bx_start, ry, bw, bar_h)

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
        """Draw debug overlay for all detected market price windows."""
        for mp_data in self._market_price_windows:
            self._paint_one_market_price(painter, mp_data)

    def _paint_one_market_price(self, painter: QPainter, data: dict) -> None:
        """Draw debug overlay for a single market price window."""
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

        # Confidence label above template: template match + mean OCR confidence
        painter.setFont(MP_VALUE_FONT)
        painter.setPen(QPen(MP_COLOR))
        ocr_conf = parsed.get("ocr_confidence", 0)
        agg_raw = parsed.get("_agg_raw", 0)
        hp_raw = parsed.get("_hp_raw", 1)
        cell_confs = parsed.get("_cell_confs", [])
        # Raw cell confidences line above main label
        if cell_confs:
            painter.setFont(MP_LABEL_FONT)
            confs_str = " ".join(f"{c:.2f}" for c in cell_confs)
            painter.drawText(x, y - 16, confs_str)
        label = f"MARKET PRICE ({confidence:.0%} / OCR {ocr_conf:.0%})"
        label += f"  agg={agg_raw} hp={hp_raw}"
        painter.drawText(x, y - 4, label)

        self._paint_market_price_rois(painter, x, y, parsed)

    def _paint_market_price_rois(self, painter: QPainter, tx: int, ty: int,
                                  parsed: dict) -> None:
        """Draw labeled ROI boxes for market price window regions."""
        cfg = self._config

        def draw_roi(roi, color, label, value_text="", conf=None,
                     value_color=None, worst_char=""):
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
            # Value text at the bottom-right of the box
            if value_text:
                painter.setFont(MP_VALUE_FONT)
                vc = value_color or QColor(255, 255, 255, 220)
                painter.setPen(QPen(vc))
                fm = painter.fontMetrics()
                tw = fm.horizontalAdvance(value_text)
                th = fm.height()
                painter.drawText(
                    rx + rw - tw - 2, ry + rh - th,
                    tw + 4, th,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                    value_text,
                )
            # Per-field confidence below the box
            if conf is not None:
                painter.setFont(MP_LABEL_FONT)
                conf_pct = f"{conf:.0%}"
                if worst_char and conf < 0.95:
                    conf_pct += f" '{worst_char}'"
                if conf >= 0.90:
                    conf_color = QColor(100, 255, 100, 180)   # Green
                elif conf >= 0.70:
                    conf_color = QColor(255, 255, 100, 180)   # Yellow
                else:
                    conf_color = QColor(255, 100, 100, 180)   # Red
                painter.setPen(QPen(conf_color))
                painter.drawText(rx + rw - 24, ry + rh + 11, conf_pct)

        # Name rows
        name = parsed.get("item_name", "")
        roi_r1 = getattr(cfg, "market_price_roi_name_row1", None)
        roi_r2 = getattr(cfg, "market_price_roi_name_row2", None)
        draw_roi(roi_r1, MP_ROI_NAME, "Name R1", name if name else "—",
                 value_color=QColor(255, 80, 80, 220))
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

            periods = ["1d", "7d", "30d", "365d", "3650d"]
            metrics = ["markup", "sales"]
            for row_idx, period in enumerate(periods):
                for col_idx, metric in enumerate(metrics):
                    cell_dx = first_dx + col_idx * off_x
                    cell_dy = first_dy + row_idx * off_y
                    cell_roi = {"dx": cell_dx, "dy": cell_dy,
                                "w": cell_w, "h": cell_h}
                    key = f"{metric}_{period}"
                    val = parsed.get(key)
                    markup_mode = parsed.get("markup_mode", "percent")
                    val_str = self._format_cell_value(val, metric, markup_mode)
                    cell_conf = parsed.get(f"{key}_conf")
                    cell_worst = parsed.get(f"{key}_worst_char", "")
                    label = f"{metric[0].upper()}{period}"
                    draw_roi(cell_roi, MP_ROI_CELL, label, val_str,
                             conf=cell_conf, worst_char=cell_worst)

    @staticmethod
    def _format_cell_value(val, metric: str, markup_mode: str = "percent") -> str:
        """Format a parsed cell value for the debug overlay.

        Sales values use scientific notation for very small numbers
        (mPEC/uPEC range).  Markup values use % or + suffix depending
        on the detected markup mode.
        """
        if val is None:
            return "—"
        if not isinstance(val, (int, float)):
            return str(val)
        if val == 0:
            return "0"
        if metric == "sales":
            # Sales are in PED; 1 PEC = 0.01 PED.
            # Values are already parsed (e.g. "2.1k" → 2100.0 PED),
            # so divide back before applying SI suffix for display.
            abs_val = abs(val)
            if abs_val >= 1_000_000:
                return f"{val / 1_000_000:.4g}M"
            if abs_val >= 1_000:
                return f"{val / 1_000:.4g}k"
            if abs_val >= 0.01:
                return f"{val:.4g}"
            # Sub-PEC: use scientific notation
            return f"{val:.2e}"
        # Markup — suffix depends on mode (percent → %, absolute → +PED)
        suffix = "%" if markup_mode == "percent" else "+"
        abs_val = abs(val)
        if abs_val >= 100_000:
            return f"{val:.3g}{suffix}"
        if abs_val >= 100:
            return f"{val:.4g}{suffix}"
        return f"{val:.4g}{suffix}"

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

    # ── Radar ────────────────────────────────────────────────────────

    def _paint_radar(self, painter: QPainter) -> None:
        """Draw radar circle outline, coordinates, and optional warnings."""
        data = self._radar_data or self._radar_circle
        if not data:
            return

        cx = data.get("circle_cx", 0)
        cy = data.get("circle_cy", 0)
        r  = data.get("circle_r",  0)
        if r <= 0:
            return

        # Radar circle
        painter.setPen(QPen(RADAR_COLOR, 2))
        painter.setBrush(QBrush(RADAR_FILL))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        cx_f = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter

        if self._radar_data:
            # Full coordinate data — show lon/lat
            lon  = self._radar_data.get("lon", 0)
            lat  = self._radar_data.get("lat", 0)
            conf = self._radar_data.get("confidence", 0.0)
            if self._debug:
                scale  = self._radar_data.get("scale", 0.0)
                line_h = max(14, r // 2)
                painter.setFont(RADAR_COORD_FONT)
                painter.setPen(QPen(RADAR_COLOR))
                painter.drawText(cx - r, cy - line_h, 2 * r, line_h,
                                 cx_f, f"{lon}, {lat}")
                painter.setFont(RADAR_LABEL_FONT)
                painter.drawText(cx - r, cy, 2 * r, line_h,
                                 cx_f, f"conf={conf:.2f}  scale={scale:.2f}")
            else:
                painter.setFont(RADAR_COORD_FONT)
                painter.setPen(QPen(RADAR_COLOR))
                painter.drawText(cx - r, cy - r, 2 * r, 2 * r,
                                 cx_f, f"{lon}, {lat}")
        else:
            # Circle detected but OCR not yet successful
            painter.setFont(RADAR_LABEL_FONT)
            painter.setPen(QPen(RADAR_COLOR))
            painter.drawText(cx - r, cy - r, 2 * r, 2 * r,
                             cx_f, "Reading\u2026")

        # Recalibration warning above circle
        if self._radar_needs_recal:
            painter.setFont(RADAR_LABEL_FONT)
            painter.setPen(QPen(RADAR_WARN))
            painter.drawText(cx - r, cy - r - 18, 2 * r, 16,
                             Qt.AlignmentFlag.AlignHCenter,
                             "RADAR RECALIBRATING")

        # Debug: draw text ROI rectangles where coordinate OCR reads from
        circle_src = self._radar_circle or data
        lon_roi = circle_src.get("lon_roi")
        lat_roi = circle_src.get("lat_roi")
        if lon_roi:
            roi_pen = QPen(QColor(0, 255, 255, 180), 1)   # cyan
            painter.setPen(roi_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            rx, ry, rw, rh = lon_roi
            painter.drawRect(rx, ry, rw, rh)
            painter.setFont(QFont("Consolas", 7))
            painter.drawText(rx + 2, ry - 2, "Lon")
        if lat_roi:
            roi_pen = QPen(QColor(0, 255, 255, 180), 1)
            painter.setPen(roi_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            rx, ry, rw, rh = lat_roi
            painter.drawRect(rx, ry, rw, rh)
            painter.setFont(QFont("Consolas", 7))
            painter.drawText(rx + 2, ry - 2, "Lat")

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
        self._event_bus.unsubscribe(EVENT_SKILLS_TEMPLATE_DEBUG, self._cb_skills_template)
        self._event_bus.unsubscribe(EVENT_RADAR_COORDINATES, self._cb_radar)
        self._event_bus.unsubscribe(EVENT_RADAR_LOST, self._cb_radar_lost)
        self._event_bus.unsubscribe(EVENT_RADAR_DEBUG, self._cb_radar_debug)
        self.close()
