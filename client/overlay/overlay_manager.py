"""Centralized overlay manager — occlusion detection, widget registry, and snap calculations."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QPoint, QRect, Qt, QTimer, pyqtSignal

from ..core.constants import (
    GAME_TITLE_PREFIX,
    OVERLAY_FOCUS_POLL_MS,
    OVERLAY_SNAP_THRESHOLD,
)
from ..core.logger import get_logger

if TYPE_CHECKING:
    from .overlay_widget import OverlayWidget

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes
    _user32 = ctypes.windll.user32
    _dwmapi = ctypes.windll.dwmapi

log = get_logger("OverlayManager")

# --- Win32 constants for z-order / style queries ---

_GWL_EXSTYLE = -20
_GW_HWNDNEXT = 2
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_NOACTIVATE = 0x08000000
_DWMWA_CLOAKED = 14

# System window classes that should never count as occluders
_SYSTEM_CLASSES = frozenset({
    "Progman", "WorkerW", "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd", "DV2ControlHost",
})

# Minimum dimensions for a window to count as a "full" occluder
_OCCLUDER_MIN_SIZE = 200

# Minimum overlap (pixels) on each axis for a window to count as occluding.
# Prevents false positives from 1-2px edge overlaps on adjacent monitors.
_OCCLUDER_MIN_OVERLAP = 50


def _get_foreground_hwnd() -> int:
    """Return the HWND of the foreground window (Windows only)."""
    if sys.platform == "win32":
        return _user32.GetForegroundWindow()
    return 0


def _get_window_title(hwnd: int) -> str:
    """Return the window title for the given HWND."""
    if sys.platform != "win32" or not hwnd:
        return ""
    length = _user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _find_game_hwnd() -> int:
    """Find the game window HWND by walking the z-order (Windows only)."""
    if sys.platform != "win32":
        return 0
    hwnd = _user32.GetTopWindow(None)
    while hwnd:
        if _user32.IsWindowVisible(hwnd):
            title = _get_window_title(hwnd)
            if title.startswith(GAME_TITLE_PREFIX):
                return hwnd
        hwnd = _user32.GetWindow(hwnd, _GW_HWNDNEXT)
    return 0


def _get_window_pid(hwnd: int) -> int:
    """Return the process ID that owns *hwnd*."""
    pid = ctypes.wintypes.DWORD(0)
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


# Cache our own PID (never changes)
_OWN_PID = os.getpid()


def _is_occluding_window(hwnd: int, game_rect: ctypes.wintypes.RECT) -> bool:
    """Return True if *hwnd* is a real application window overlapping *game_rect*."""
    if not _user32.IsWindowVisible(hwnd):
        return False
    # Minimized windows are still "visible" in the z-order but not on screen
    if _user32.IsIconic(hwnd):
        return False
    # Never count our own application's windows as occluders
    if _get_window_pid(hwnd) == _OWN_PID:
        return False
    # Cloaked windows (virtual desktops, suspended UWP apps) pass
    # IsWindowVisible but aren't actually rendered on screen
    cloaked = ctypes.wintypes.DWORD(0)
    _dwmapi.DwmGetWindowAttribute(
        hwnd, _DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
    )
    if cloaked.value:
        return False
    # Must have a title (unnamed windows are usually internal/helper)
    if _user32.GetWindowTextLengthW(hwnd) == 0:
        return False
    # Filter out tool windows and no-activate overlays
    ex_style = _user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
    if ex_style & (_WS_EX_TOOLWINDOW | _WS_EX_NOACTIVATE):
        return False
    # Filter system classes (taskbar, desktop shell)
    cls_buf = ctypes.create_unicode_buffer(64)
    _user32.GetClassNameW(hwnd, cls_buf, 64)
    if cls_buf.value in _SYSTEM_CLASSES:
        return False
    # Too small — likely a tooltip or popup, not a full window
    rect = ctypes.wintypes.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(rect))
    if (rect.right - rect.left) < _OCCLUDER_MIN_SIZE or \
       (rect.bottom - rect.top) < _OCCLUDER_MIN_SIZE:
        return False
    # Require substantial overlap — not just 1-2px edge touching
    # (prevents false positives from windows on adjacent monitors)
    overlap_x = min(rect.right, game_rect.right) - max(rect.left, game_rect.left)
    overlap_y = min(rect.bottom, game_rect.bottom) - max(rect.top, game_rect.top)
    return overlap_x >= _OCCLUDER_MIN_OVERLAP and overlap_y >= _OCCLUDER_MIN_OVERLAP


def _is_game_occluded(game_hwnd: int, overlay_hwnds: set[int]) -> bool:
    """Walk z-order above *game_hwnd*. Return True if a full app window overlaps it."""
    game_rect = ctypes.wintypes.RECT()
    _user32.GetWindowRect(game_hwnd, ctypes.byref(game_rect))

    hwnd = _user32.GetTopWindow(None)
    while hwnd:
        if hwnd == game_hwnd:
            return False  # Reached the game without finding an occluder
        if hwnd not in overlay_hwnds:
            if _is_occluding_window(hwnd, game_rect):
                return True
        hwnd = _user32.GetWindow(hwnd, _GW_HWNDNEXT)
    return False  # Game window not found in z-order (edge case)


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
    game_focus_changed = pyqtSignal(bool)  # True when game is focused/visible

    def __init__(self, *, config, parent: QObject | None = None):
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

        if sys.platform == "win32" and getattr(config, "overlay_enabled", True):
            self._timer.start()

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
            fg_hwnd = _get_foreground_hwnd()
            if not fg_hwnd:
                return

            # Build set of our overlay HWNDs (used for both checks)
            overlay_hwnds: set[int] = set()
            for w in self._widgets:
                if w.isVisible():
                    overlay_hwnds.add(int(w.winId()))

            # Fast path: one of our overlays has focus — stay visible
            if fg_hwnd in overlay_hwnds:
                if not self._game_focused:
                    self._game_focused = True
                    self._show_all()
                    self.game_focus_changed.emit(True)
                self._set_hotkeys_active(True)
                return

            # Find / validate the cached game HWND
            game_hwnd = self._game_hwnd
            if not game_hwnd or not _user32.IsWindowVisible(game_hwnd):
                game_hwnd = _find_game_hwnd()
                self._game_hwnd = game_hwnd
            if not game_hwnd:
                # Game not running — hide overlays
                if self._game_focused:
                    self._game_focused = False
                    self._hide_all()
                    self.game_focus_changed.emit(False)
                self._set_hotkeys_active(False)
                return

            # Game has focus → always visible
            title = _get_window_title(fg_hwnd)
            game_is_fg = title.startswith(GAME_TITLE_PREFIX)
            if game_is_fg:
                visible = True
            else:
                # Game doesn't have focus — check if a full window occludes it
                visible = not _is_game_occluded(game_hwnd, overlay_hwnds)

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

    def _register_hotkey(self) -> None:
        if sys.platform != "win32" or self._hotkey_registered:
            return
        try:
            import keyboard
            self._suppressed_scancodes: set[int] = set()
            keyboard.hook(self._key_hook, suppress=True)
            self._hotkey_registered = True
        except ImportError:
            pass
        except Exception as e:
            log.warning("Failed to register hotkeys: %s", e)

    def _unregister_hotkey(self) -> None:
        if not self._hotkey_registered:
            return
        try:
            import keyboard
            keyboard.unhook(self._key_hook)
        except Exception:
            pass
        self._hotkey_registered = False

    def _key_hook(self, event) -> bool:
        """Low-level keyboard hook — runs synchronously on the hook thread.

        Returns True to pass the event through, False to suppress it.
        Only suppresses the letter key of our hotkey combos; Ctrl itself
        always passes through immediately.
        """
        import keyboard as _kb

        name = event.name
        if name not in self._HOTKEY_MAP:
            return True  # not a hotkey letter — pass through

        if event.event_type == _kb.KEY_DOWN:
            if _kb.is_pressed("ctrl"):
                # Real-time focus check — guard against poll lag after alt-tab
                fg = _get_foreground_hwnd()
                if fg in self._overlay_hwnds or \
                        _get_window_title(fg).startswith(GAME_TITLE_PREFIX):
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

    # --- Cleanup ---

    def stop(self) -> None:
        self._timer.stop()
        self._unregister_hotkey()
