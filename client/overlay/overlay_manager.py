"""Centralized overlay manager — occlusion detection, widget registry, and snap calculations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QPoint, QRect, Qt, QTimer, pyqtSignal

from ..core.constants import (
    EVENT_CONFIG_CHANGED,
    GAME_TITLE_PREFIX,
    OVERLAY_FOCUS_POLL_MS,
    OVERLAY_SNAP_THRESHOLD,
)
from ..core.logger import get_logger
from ..platform import backend as _platform

if TYPE_CHECKING:
    from .overlay_widget import OverlayWidget

log = get_logger("OverlayManager")


class OverlayManager(QObject):
    """Manages overlay visibility, occlusion detection, and snap targets.

    - Polls every 500ms to detect whether the game window is occluded by
      a full application window (z-order walk).  Overlays stay visible
      when only small popups, tool windows, or our own overlays are in front.
    - Registered overlay widgets that have ``wants_visible`` set are
      shown/hidden automatically when visibility changes.
    - Provides snap target rectangles for drag-snap alignment.
    - Registers a global Ctrl+F hotkey (active only while overlays are shown).
    """

    search_hotkey_pressed = pyqtSignal()
    map_hotkey_pressed = pyqtSignal()
    exchange_hotkey_pressed = pyqtSignal()
    notifications_hotkey_pressed = pyqtSignal()
    debug_overlay_hotkey_pressed = pyqtSignal()
    game_focus_changed = pyqtSignal(bool)  # True when game is focused/visible
    opacity_changed = pyqtSignal(float)

    def __init__(self, *, config, event_bus=None, parent: QObject | None = None):
        super().__init__(parent)
        self._config = config
        self._widgets: list[OverlayWidget] = []
        self._game_focused = False
        self._game_hwnd = 0
        self._hotkey_registered = False
        self._overlay_hwnds: dict[int, OverlayWidget] = {}  # hwnd → widget

        self._timer = QTimer(self)
        self._timer.setInterval(OVERLAY_FOCUS_POLL_MS)
        self._timer.timeout.connect(self._poll_focus)

        if _platform.supports_focus_detection() and getattr(config, "overlay_enabled", True):
            self._timer.start()

        if event_bus:
            self._event_bus = event_bus
            event_bus.subscribe(EVENT_CONFIG_CHANGED, self._on_config_changed)

    # --- Widget registry ---

    def register(self, widget: OverlayWidget) -> None:
        if widget not in self._widgets:
            self._widgets.append(widget)
            hwnd = int(widget.winId())
            if hwnd:
                self._overlay_hwnds[hwnd] = widget

    def unregister(self, widget: OverlayWidget) -> None:
        try:
            self._widgets.remove(widget)
        except ValueError:
            pass
        hwnd = int(widget.winId())
        self._overlay_hwnds.pop(hwnd, None)

    @property
    def game_focused(self) -> bool:
        return self._game_focused

    # --- Snap targets ---

    def get_snap_targets(self, exclude: OverlayWidget) -> list[QRect]:
        """Return geometries of all visible registered widgets except *exclude*."""
        return [
            w.geometry()
            for w in self._widgets
            if w is not exclude and w.isVisible()
        ]

    @staticmethod
    def snap_position(pos_x: int, pos_y: int, size_w: int, size_h: int,
                      targets: list[QRect]) -> tuple[int, int]:
        """Adjust (pos_x, pos_y) to snap edges to nearby *targets*.

        Only snaps to a target on one axis if the widgets are close or
        overlapping on the other axis (prevents snapping to far-away widgets).

        Returns the (possibly adjusted) (x, y) position.
        """
        threshold = OVERLAY_SNAP_THRESHOLD

        for rect in targets:
            # Check proximity on each axis: do the ranges overlap or nearly
            # touch?  "Nearly touch" = gap <= threshold.
            h_close = (pos_x - threshold <= rect.right()
                       and pos_x + size_w + threshold >= rect.left())
            v_close = (pos_y - threshold <= rect.bottom()
                       and pos_y + size_h + threshold >= rect.top())

            # Horizontal snaps — only if vertically close
            if v_close:
                # Left edge to left edge
                if abs(pos_x - rect.left()) < threshold:
                    pos_x = rect.left()
                # Right edge to right edge
                elif abs((pos_x + size_w) - rect.right()) < threshold:
                    pos_x = rect.right() - size_w
                # Left edge to right edge
                elif abs(pos_x - rect.right()) < threshold:
                    pos_x = rect.right()
                # Right edge to left edge
                elif abs((pos_x + size_w) - rect.left()) < threshold:
                    pos_x = rect.left() - size_w

            # Vertical snaps — only if horizontally close
            if h_close:
                # Top to top
                if abs(pos_y - rect.top()) < threshold:
                    pos_y = rect.top()
                # Bottom to bottom
                elif abs((pos_y + size_h) - rect.bottom()) < threshold:
                    pos_y = rect.bottom() - size_h
                # Top to bottom
                elif abs(pos_y - rect.bottom()) < threshold:
                    pos_y = rect.bottom()
                # Bottom to top
                elif abs((pos_y + size_h) - rect.top()) < threshold:
                    pos_y = rect.top() - size_h

        return pos_x, pos_y

    # --- Occlusion detection ---

    def _poll_focus(self) -> None:
        """Check whether the game is visible (not occluded by a full window)."""
        try:
            fg_wid = _platform.get_foreground_window_id()
            if not fg_wid:
                return

            # Build set of our overlay window IDs (used for both checks)
            overlay_wids: set[int] = set()
            for w in self._widgets:
                if w.isVisible():
                    overlay_wids.add(int(w.winId()))

            # Fast path: one of our overlays has focus — stay visible
            if fg_wid in overlay_wids:
                if not self._game_focused:
                    self._game_focused = True
                    self._show_all()
                    self.game_focus_changed.emit(True)
                self._set_hotkeys_active(True)
                return

            # Find / validate the cached game window ID
            game_wid = self._game_hwnd
            if not game_wid or not _platform.is_window_visible(game_wid):
                game_wid = _platform.find_window_by_title_prefix(GAME_TITLE_PREFIX) or 0
                self._game_hwnd = game_wid
            if not game_wid:
                # Game not running — hide overlays
                if self._game_focused:
                    self._game_focused = False
                    self._hide_all()
                    self.game_focus_changed.emit(False)
                self._set_hotkeys_active(False)
                return

            # Game has focus → always visible
            fg_title = _platform.get_foreground_window_title()
            game_is_fg = fg_title.startswith(GAME_TITLE_PREFIX)
            if game_is_fg:
                visible = True
            else:
                # Game doesn't have focus — check if a full window occludes it
                visible = not _platform.is_window_occluded(game_wid, overlay_wids)

            if visible and not self._game_focused:
                self._game_focused = True
                self._show_all()
                self.game_focus_changed.emit(True)
            elif not visible and self._game_focused:
                self._game_focused = False
                self._hide_all()
                self.game_focus_changed.emit(False)

            # Hotkeys only when game has actual input focus
            self._set_hotkeys_active(game_is_fg)
        except Exception:
            pass

    def _show_all(self) -> None:
        for w in self._widgets:
            if w.wants_visible:
                w.show()

    def _hide_all(self) -> None:
        for w in self._widgets:
            if w.isVisible():
                w.hide()

    # --- Global hotkeys (only while game/overlay has input focus) ---
    #
    # Uses keyboard.hook(suppress=True) instead of add_hotkey(suppress=True).
    # add_hotkey's suppress buffers modifier keys (Ctrl) through a state machine
    # while it waits for the next key to determine if a hotkey matches.  This
    # causes non-matching Ctrl combos like Ctrl+V to be delayed, requiring a
    # double-press in-game.
    #
    # With hook(suppress=True), we get per-event control: Ctrl passes through
    # immediately (return True), and only the specific letter key is suppressed
    # (return False) when Ctrl is held.

    def _set_hotkeys_active(self, active: bool) -> None:
        """Register/unregister keyboard hook based on input focus."""
        if active and not self._hotkey_registered:
            self._register_hotkey()
        elif not active and self._hotkey_registered:
            self._unregister_hotkey()

    _HOTKEY_MAP = {
        "f": "search_hotkey_pressed",
        "m": "map_hotkey_pressed",
        "e": "exchange_hotkey_pressed",
        "n": "notifications_hotkey_pressed",
    }

    # Function keys — no Ctrl modifier required
    _FKEY_MAP = {
        "f3": "debug_overlay_hotkey_pressed",
    }

    def _register_hotkey(self) -> None:
        if not _platform.supports_global_hotkeys() or self._hotkey_registered:
            return
        try:
            self._suppressed_scancodes: set[int] = set()
            if _platform.register_hotkey_hook(self._key_hook):
                self._hotkey_registered = True
        except Exception as e:
            log.warning("Failed to register hotkeys: %s", e)

    def _unregister_hotkey(self) -> None:
        if not self._hotkey_registered:
            return
        try:
            _platform.unregister_hotkey_hook(self._key_hook)
        except Exception:
            pass
        self._hotkey_registered = False

    def _key_hook(self, event) -> bool:
        """Low-level keyboard hook — runs synchronously on the hook thread.

        Returns True to pass the event through, False to suppress it.
        Only suppresses the letter key of our hotkey combos; Ctrl itself
        always passes through immediately.

        On Win32 (keyboard library): receives *all* key events; we check
        is_pressed("ctrl") before acting.
        On X11 (XGrabKey): only Ctrl+letter events fire, so no Ctrl check
        is needed.
        """
        name = event.name

        # Function keys (no modifier required, pass through to game)
        if name in self._FKEY_MAP:
            if event.event_type == "down":
                fg = _platform.get_foreground_window_id()
                if fg in self._overlay_hwnds or \
                        _platform.get_foreground_window_title().startswith(GAME_TITLE_PREFIX):
                    signal = getattr(self, self._FKEY_MAP[name])
                    signal.emit()
            return True  # always pass function keys through

        # Ctrl+letter hotkeys
        if name not in self._HOTKEY_MAP:
            return True  # not a hotkey letter — pass through

        # event_type is "down"/"up" on both keyboard lib and X11KeyEvent
        if event.event_type == "down":
            # On Win32, verify Ctrl is actually held (the hook sees all keys)
            ctrl_held = True
            try:
                import keyboard as _kb
                ctrl_held = _kb.is_pressed("ctrl")
            except ImportError:
                pass  # X11: XGrabKey already ensures Ctrl is held

            if ctrl_held:
                # Real-time focus check — guard against poll lag after alt-tab
                fg = _platform.get_foreground_window_id()
                if fg in self._overlay_hwnds or \
                        _platform.get_foreground_window_title().startswith(GAME_TITLE_PREFIX):
                    self._suppressed_scancodes.add(event.scan_code)
                    signal = getattr(self, self._HOTKEY_MAP[name])
                    signal.emit()
                    return False  # suppress the letter key
            return True

        # KEY_UP: suppress if we suppressed the matching key-down
        if event.scan_code in self._suppressed_scancodes:
            self._suppressed_scancodes.discard(event.scan_code)
            return False
        return True

    # --- Config changes ---

    def _on_config_changed(self, config) -> None:
        opacity = config.overlay_opacity
        for w in self._widgets:
            w.setWindowOpacity(opacity)
        self.opacity_changed.emit(opacity)

    # --- Cleanup ---

    def stop(self) -> None:
        self._timer.stop()
        self._unregister_hotkey()
