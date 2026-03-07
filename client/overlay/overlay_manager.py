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
    - Registers configurable global hotkeys (active only while overlays are shown).
    """

    search_hotkey_pressed = pyqtSignal()
    map_hotkey_pressed = pyqtSignal()
    exchange_hotkey_pressed = pyqtSignal()
    notifications_hotkey_pressed = pyqtSignal()
    debug_overlay_hotkey_pressed = pyqtSignal()
    overlay_toggle_hotkey_pressed = pyqtSignal()
    game_focus_changed = pyqtSignal(bool)  # True when game is focused/visible
    opacity_changed = pyqtSignal(float)

    # Config key → signal name mapping
    _HOTKEY_SIGNAL_MAP = {
        "hotkey_search": "search_hotkey_pressed",
        "hotkey_map": "map_hotkey_pressed",
        "hotkey_exchange": "exchange_hotkey_pressed",
        "hotkey_notifications": "notifications_hotkey_pressed",
        "hotkey_debug": "debug_overlay_hotkey_pressed",
        "hotkey_overlay_toggle": "overlay_toggle_hotkey_pressed",
    }

    def __init__(self, *, config, event_bus=None, parent: QObject | None = None):
        super().__init__(parent)
        self._config = config
        self._widgets: list[OverlayWidget] = []
        self._game_focused = False
        self._user_visible = True  # F2 toggle — master gate for overlay visibility
        self._game_hwnd = 0
        self._hotkey_registered = False
        self._overlay_hwnds: dict[int, OverlayWidget] = {}  # hwnd → widget

        # Dynamic hotkey bindings: trigger_key → [(required_modifiers_set, signal_name)]
        self._hotkey_bindings: dict[str, list[tuple[set[str], str]]] = {}
        self._rebuild_hotkey_bindings()

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

    def unregister(self, widget: OverlayWidget) -> None:
        try:
            self._widgets.remove(widget)
        except ValueError:
            pass
        self._overlay_hwnds = {
            h: w for h, w in self._overlay_hwnds.items() if w is not widget
        }

    @property
    def game_focused(self) -> bool:
        return self._game_focused

    def toggle_user_visible(self) -> None:
        """Toggle user-level overlay visibility (F2 hotkey).

        When toggled off, all registered widgets hide as if the game were
        occluded.  When toggled back on, widgets restore if the game is
        still focused.
        """
        self._user_visible = not self._user_visible
        if not self._user_visible:
            self._hide_all()
        elif self._game_focused:
            self._show_all()

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
                    wid = int(w.winId())
                    overlay_wids.add(wid)
                    self._overlay_hwnds[wid] = w

            # Fast path: one of our overlays has focus — stay visible
            if fg_wid in overlay_wids:
                if not self._game_focused:
                    self._game_focused = True
                    if self._user_visible:
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
                if self._user_visible:
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
                wid = int(w.winId())
                if wid:
                    self._overlay_hwnds[wid] = w

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
        # Respect the global hotkeys_enabled toggle
        if not getattr(self._config, "hotkeys_enabled", True):
            active = False
        if active and not self._hotkey_registered:
            self._register_hotkey()
        elif not active and self._hotkey_registered:
            self._unregister_hotkey()

    def _rebuild_hotkey_bindings(self) -> None:
        """Build dynamic hotkey bindings from config combo strings.

        Populates ``_hotkey_bindings``: trigger_key → [(modifiers_set, signal_name)].
        """
        bindings: dict[str, list[tuple[set[str], str]]] = {}
        for config_key, signal_name in self._HOTKEY_SIGNAL_MAP.items():
            combo = getattr(self._config, config_key, "")
            if not combo:
                continue
            parts = combo.lower().split("+")
            trigger = parts[-1]           # e.g. "f", "f3", "s"
            mods = set(parts[:-1])        # e.g. {"ctrl"}, {"ctrl", "shift"}, set()
            bindings.setdefault(trigger, []).append((mods, signal_name))
        self._hotkey_bindings = bindings

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
        Only suppresses the trigger key when modifiers match; modifier keys
        themselves always pass through immediately.

        On Win32 (keyboard library): receives *all* key events; we check
        is_pressed() for modifiers before acting.
        On X11 (XGrabKey): only grabbed combos fire, so no modifier check
        is needed.
        """
        name = event.name
        if name not in self._hotkey_bindings:
            return True  # not a trigger key — pass through

        entries = self._hotkey_bindings[name]

        if event.event_type == "down":
            # Determine which modifiers are currently held (Win32)
            held_mods: set[str] = set()
            try:
                import keyboard as _kb
                for mod in ("ctrl", "shift", "alt"):
                    if _kb.is_pressed(mod):
                        held_mods.add(mod)
            except ImportError:
                pass  # X11: XGrabKey already ensures correct modifiers

            for required_mods, signal_name in entries:
                if required_mods and not required_mods.issubset(held_mods):
                    continue  # required modifiers not held
                # For combos without modifiers (bare keys like F3), don't
                # require empty held_mods — just fire regardless of modifiers

                # Real-time focus check — guard against poll lag after alt-tab
                fg = _platform.get_foreground_window_id()
                if fg not in self._overlay_hwnds and \
                        not _platform.get_foreground_window_title().startswith(GAME_TITLE_PREFIX):
                    return True

                signal = getattr(self, signal_name)
                signal.emit()

                if required_mods:
                    # Has modifiers → suppress the trigger key
                    self._suppressed_scancodes.add(event.scan_code)
                    return False
                else:
                    # Bare key (e.g. F3) → pass through to game
                    return True

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

        # Rebuild hotkey bindings (combos or enabled state may have changed)
        self._rebuild_hotkey_bindings()
        # Re-evaluate: if hotkeys_enabled was toggled off, unregister
        if not getattr(config, "hotkeys_enabled", True) and self._hotkey_registered:
            self._unregister_hotkey()

    # --- Cleanup ---

    def stop(self) -> None:
        self._timer.stop()
        self._unregister_hotkey()
