"""X11 platform backend — uses python-xlib for window management.

This module is only imported on Linux with an X11 display server.
Requires ``python-xlib>=0.33``.
"""

from __future__ import annotations

import logging
import os
import struct
import threading

log = logging.getLogger("platform.x11")

# Our own PID — never changes
_OWN_PID = os.getpid()


class X11Backend:
    """Full X11 backend using python-xlib (EWMH/ICCCM)."""

    def __init__(self):
        from Xlib import X, display as xdisplay, Xatom
        from Xlib.protocol import event as xevent

        self._display = xdisplay.Display()
        self._root = self._display.screen().root

        # Cache frequently used atoms
        self._NET_ACTIVE_WINDOW = self._display.intern_atom("_NET_ACTIVE_WINDOW")
        self._NET_WM_NAME = self._display.intern_atom("_NET_WM_NAME")
        self._NET_WM_PID = self._display.intern_atom("_NET_WM_PID")
        self._NET_WM_STATE = self._display.intern_atom("_NET_WM_STATE")
        self._NET_WM_STATE_HIDDEN = self._display.intern_atom("_NET_WM_STATE_HIDDEN")
        self._NET_CLIENT_LIST_STACKING = self._display.intern_atom(
            "_NET_CLIENT_LIST_STACKING"
        )
        self._UTF8_STRING = self._display.intern_atom("UTF8_STRING")

        # Hotkey state
        self._hotkey_thread: threading.Thread | None = None
        self._hotkey_running = False
        self._hotkey_callback = None

        log.info("X11 backend initialised (display %s)", self._display.get_display_name())

    # ------------------------------------------------------------------
    # Capability queries
    # ------------------------------------------------------------------

    def supports_focus_detection(self) -> bool:
        return True

    def supports_global_hotkeys(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Focus detection
    # ------------------------------------------------------------------

    def get_foreground_window_title(self) -> str:
        wid = self.get_foreground_window_id()
        if not wid:
            return ""
        return self._get_window_title(wid)

    def get_foreground_window_id(self) -> int:
        try:
            prop = self._root.get_full_property(self._NET_ACTIVE_WINDOW, 0)
            if prop and prop.value:
                return int(prop.value[0])
        except Exception:
            pass
        return 0

    def find_window_by_title_prefix(self, prefix: str) -> int | None:
        """Walk the stacking order and return the first window matching *prefix*."""
        for wid in self._get_stacking_order():
            title = self._get_window_title(wid)
            if title.startswith(prefix):
                return wid
        return None

    def is_window_visible(self, wid: int) -> bool:
        from Xlib import error as xerror
        try:
            win = self._display.create_resource_object("window", wid)
            attrs = win.get_attributes()
            return attrs.map_state != 0  # IsUnmapped = 0
        except (xerror.BadWindow, Exception):
            return False

    def is_window_minimized(self, wid: int) -> bool:
        try:
            win = self._display.create_resource_object("window", wid)
            prop = win.get_full_property(self._NET_WM_STATE, 0)
            if prop and prop.value:
                return self._NET_WM_STATE_HIDDEN in prop.value
        except Exception:
            pass
        return False

    def get_window_geometry(self, wid: int) -> tuple[int, int, int, int] | None:
        from Xlib import error as xerror
        try:
            win = self._display.create_resource_object("window", wid)
            geo = win.get_geometry()
            # Translate to root coordinates
            coords = win.translate_coords(self._root, 0, 0)
            return (-coords.x, -coords.y, geo.width, geo.height)
        except (xerror.BadWindow, xerror.BadDrawable, Exception):
            return None

    def get_window_pid(self, wid: int) -> int:
        try:
            win = self._display.create_resource_object("window", wid)
            prop = win.get_full_property(self._NET_WM_PID, 0)
            if prop and prop.value:
                return int(prop.value[0])
        except Exception:
            pass
        return 0

    # ------------------------------------------------------------------
    # Occlusion
    # ------------------------------------------------------------------

    # Minimum dimensions and overlap (mirrors Win32 backend constants)
    _OCCLUDER_MIN_SIZE = 200
    _OCCLUDER_MIN_OVERLAP = 50

    def is_window_occluded(self, target_wid: int, ignore_wids: set[int]) -> bool:
        target_geo = self.get_window_geometry(target_wid)
        if not target_geo:
            return False
        tx, ty, tw, th = target_geo

        stacking = self._get_stacking_order()
        # Walk from top of stack downward
        above_target = False
        for wid in reversed(stacking):
            if wid == target_wid:
                # Reached target without finding occluder above it
                return False
            if wid in ignore_wids:
                continue
            if self.is_window_minimized(wid):
                continue
            if self.get_window_pid(wid) == _OWN_PID:
                continue

            geo = self.get_window_geometry(wid)
            if not geo:
                continue
            wx, wy, ww, wh = geo
            if ww < self._OCCLUDER_MIN_SIZE or wh < self._OCCLUDER_MIN_SIZE:
                continue

            # Check overlap
            overlap_x = min(tx + tw, wx + ww) - max(tx, wx)
            overlap_y = min(ty + th, wy + wh) - max(ty, wy)
            if overlap_x >= self._OCCLUDER_MIN_OVERLAP and overlap_y >= self._OCCLUDER_MIN_OVERLAP:
                return True

        return False

    # ------------------------------------------------------------------
    # Window manipulation
    # ------------------------------------------------------------------

    def set_click_through(self, wid: int) -> bool:
        """Set an empty input shape to make the window click-through."""
        try:
            from Xlib.ext import shape
            from Xlib import X
            win = self._display.create_resource_object("window", wid)
            # Empty input region = all clicks pass through
            win.shape_rectangles(shape.SO.Set, shape.SK.Input, 0, 0, [], X.Unsorted)
            self._display.flush()
            return True
        except Exception as e:
            log.warning("Failed to set click-through via XShape: %s", e)
            return False

    def set_no_activate(self, wid: int) -> bool:
        return False  # Not needed on X11 — Tool windows don't steal focus

    def bring_to_foreground(self, wid: int) -> bool:
        """Send _NET_ACTIVE_WINDOW client message (EWMH standard)."""
        try:
            self._send_ewmh_active_window(wid)
            return True
        except Exception as e:
            log.warning("Failed to bring window to foreground: %s", e)
            return False

    def release_focus_to(self, title_prefix: str) -> bool:
        wid = self.find_window_by_title_prefix(title_prefix)
        if wid:
            return self.bring_to_foreground(wid)
        return False

    # ------------------------------------------------------------------
    # Decoration
    # ------------------------------------------------------------------

    def enable_shadow(self, wid: int) -> bool:
        # Linux compositors add shadows automatically for frameless windows
        return False

    # ------------------------------------------------------------------
    # Hotkeys
    # ------------------------------------------------------------------

    def register_hotkey_hook(self, callback) -> bool:
        """Install a keyboard hook using XGrabKey for Ctrl+letter hotkeys."""
        try:
            from Xlib import X, XK

            self._hotkey_callback = callback
            self._hotkey_running = True

            # Grab Ctrl+{F, M, E, N} on the root window
            keys = ["f", "m", "e", "n"]
            for key_name in keys:
                keysym = XK.string_to_keysym(key_name)
                keycode = self._display.keysym_to_keycode(keysym)
                if keycode:
                    # Grab with Ctrl modifier, including common lock combos
                    for mod_extra in [0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask]:
                        self._root.grab_key(
                            keycode,
                            X.ControlMask | mod_extra,
                            True,  # owner_events
                            X.GrabModeAsync,
                            X.GrabModeAsync,
                        )

            self._display.flush()

            # Start event loop thread
            self._hotkey_thread = threading.Thread(
                target=self._hotkey_event_loop,
                daemon=True,
                name="x11-hotkey",
            )
            self._hotkey_thread.start()
            return True
        except Exception as e:
            log.warning("Failed to register X11 hotkey grabs: %s", e)
            return False

    def unregister_hotkey_hook(self, callback=None) -> bool:
        self._hotkey_running = False
        try:
            from Xlib import X, XK

            keys = ["f", "m", "e", "n"]
            for key_name in keys:
                keysym = XK.string_to_keysym(key_name)
                keycode = self._display.keysym_to_keycode(keysym)
                if keycode:
                    for mod_extra in [0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask]:
                        self._root.ungrab_key(keycode, X.ControlMask | mod_extra)
            self._display.flush()
            return True
        except Exception:
            return False

    def _hotkey_event_loop(self):
        """Background thread: read X events for grabbed keys."""
        from Xlib import X, XK

        while self._hotkey_running:
            try:
                # pending_events() is non-blocking count
                count = self._display.pending_events()
                if count == 0:
                    # Brief sleep to avoid busy-waiting
                    import time
                    time.sleep(0.05)
                    continue
                event = self._display.next_event()
                if event.type == X.KeyPress:
                    keycode = event.detail
                    keysym = self._display.keycode_to_keysym(keycode, 0)
                    key_name = XK.keysym_to_string(keysym)
                    if key_name and self._hotkey_callback:
                        # Create a minimal event-like object compatible with
                        # the keyboard library's event format
                        self._hotkey_callback(_X11KeyEvent(key_name, "down"))
                elif event.type == X.KeyRelease:
                    keycode = event.detail
                    keysym = self._display.keycode_to_keysym(keycode, 0)
                    key_name = XK.keysym_to_string(keysym)
                    if key_name and self._hotkey_callback:
                        self._hotkey_callback(_X11KeyEvent(key_name, "up"))
            except Exception:
                if self._hotkey_running:
                    import time
                    time.sleep(0.1)

    # ------------------------------------------------------------------
    # Desktop integration
    # ------------------------------------------------------------------

    def set_app_id(self, app_id: str) -> None:
        try:
            from PyQt6.QtGui import QGuiApplication
            QGuiApplication.setDesktopFileName("entropia-nexus")
        except Exception:
            pass

    def flash_taskbar(self, wid: int) -> None:
        # Qt's QApplication.alert() handles _NET_WM_STATE_DEMANDS_ATTENTION
        pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_window_title(self, wid: int) -> str:
        """Get window title: _NET_WM_NAME (UTF-8) with WM_NAME fallback."""
        from Xlib import Xatom, error as xerror
        try:
            win = self._display.create_resource_object("window", wid)
            # Try _NET_WM_NAME first (UTF-8)
            prop = win.get_full_property(self._NET_WM_NAME, self._UTF8_STRING)
            if prop and prop.value:
                return prop.value.decode("utf-8", errors="replace")
            # Fallback to WM_NAME (Latin-1)
            prop = win.get_full_property(Xatom.WM_NAME, 0)
            if prop and prop.value:
                val = prop.value
                if isinstance(val, bytes):
                    return val.decode("latin-1", errors="replace")
                return str(val)
        except (xerror.BadWindow, Exception):
            pass
        return ""

    def _get_stacking_order(self) -> list[int]:
        """Return window IDs in stacking order (bottom-to-top)."""
        try:
            prop = self._root.get_full_property(self._NET_CLIENT_LIST_STACKING, 0)
            if prop and prop.value:
                return list(prop.value)
        except Exception:
            pass
        return []

    def _send_ewmh_active_window(self, wid: int):
        """Send _NET_ACTIVE_WINDOW client message to the root window."""
        from Xlib import X
        from Xlib.protocol import event as xevent

        win = self._display.create_resource_object("window", wid)
        ev = xevent.ClientMessage(
            window=win,
            client_type=self._NET_ACTIVE_WINDOW,
            data=(32, [2, 0, 0, 0, 0]),  # source=2 (pager), timestamp=0
        )
        self._root.send_event(
            ev,
            event_mask=X.SubstructureNotifyMask | X.SubstructureRedirectMask,
        )
        self._display.flush()


class _X11KeyEvent:
    """Minimal key event object compatible with the keyboard library's format.

    The overlay_manager's _key_hook expects ``event.name``, ``event.event_type``,
    and ``event.scan_code``.  XGrabKey inherently suppresses (keys don't reach
    the focused app), so the hook's return value is irrelevant.
    """

    def __init__(self, name: str, event_type: str):
        self.name = name
        self.event_type = event_type
        self.scan_code = hash(name)  # unique identifier per key
