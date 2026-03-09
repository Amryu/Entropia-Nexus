"""Win32 platform backend — wraps all ctypes / user32 / dwmapi / shell32 calls.

This module is only imported on Windows (``sys.platform == "win32"``).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import logging

log = logging.getLogger("platform.win32")

# ---------------------------------------------------------------------------
# Win32 handles
# ---------------------------------------------------------------------------

_user32 = ctypes.windll.user32
_dwmapi = ctypes.windll.dwmapi
_shell32 = ctypes.windll.shell32

# ---------------------------------------------------------------------------
# Win32 constants
# ---------------------------------------------------------------------------

_GWL_EXSTYLE = -20
_GW_HWNDNEXT = 2

_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_NOACTIVATE = 0x08000000
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020

_DWMWA_CLOAK = 13
_DWMWA_CLOAKED = 14

_FLASHW_ALL = 0x00000003
_FLASHW_TIMERNOFG = 0x0000000C

# System window classes that should never count as occluders
_SYSTEM_CLASSES = frozenset({
    "Progman", "WorkerW", "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd", "DV2ControlHost",
})

# Minimum dimensions for a window to count as a "full" occluder
_OCCLUDER_MIN_SIZE = 200

# Minimum overlap (pixels) on each axis for a window to count as occluding
_OCCLUDER_MIN_OVERLAP = 50

# Our own PID — never changes
_OWN_PID = os.getpid()


# ---------------------------------------------------------------------------
# FLASHWINFO structure for FlashWindowEx
# ---------------------------------------------------------------------------

class _FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.UINT),
        ("hwnd", ctypes.wintypes.HWND),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("uCount", ctypes.wintypes.UINT),
        ("dwTimeout", ctypes.wintypes.DWORD),
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_window_title(hwnd: int) -> str:
    """Return the window title for a given HWND."""
    if not hwnd:
        return ""
    length = _user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _is_occluding_window(hwnd: int, game_rect: ctypes.wintypes.RECT) -> bool:
    """Return True if *hwnd* is a real application window overlapping *game_rect*."""
    if not _user32.IsWindowVisible(hwnd):
        return False
    if _user32.IsIconic(hwnd):
        return False
    if _get_window_pid(hwnd) == _OWN_PID:
        return False

    cloaked = ctypes.wintypes.DWORD(0)
    _dwmapi.DwmGetWindowAttribute(
        hwnd, _DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked),
    )
    if cloaked.value:
        return False
    if _user32.GetWindowTextLengthW(hwnd) == 0:
        return False

    ex_style = _user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
    if ex_style & (_WS_EX_TOOLWINDOW | _WS_EX_NOACTIVATE):
        return False

    cls_buf = ctypes.create_unicode_buffer(64)
    _user32.GetClassNameW(hwnd, cls_buf, 64)
    if cls_buf.value in _SYSTEM_CLASSES:
        return False

    rect = ctypes.wintypes.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(rect))
    if (rect.right - rect.left) < _OCCLUDER_MIN_SIZE or \
       (rect.bottom - rect.top) < _OCCLUDER_MIN_SIZE:
        return False

    overlap_x = min(rect.right, game_rect.right) - max(rect.left, game_rect.left)
    overlap_y = min(rect.bottom, game_rect.bottom) - max(rect.top, game_rect.top)
    return overlap_x >= _OCCLUDER_MIN_OVERLAP and overlap_y >= _OCCLUDER_MIN_OVERLAP


def _get_window_pid(hwnd: int) -> int:
    """Return the process ID that owns *hwnd*."""
    pid = ctypes.wintypes.DWORD(0)
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


# ---------------------------------------------------------------------------
# Public backend class
# ---------------------------------------------------------------------------

class Win32Backend:
    """Full-featured Win32 platform backend."""

    # --- Capability queries ---

    def supports_focus_detection(self) -> bool:
        return True

    def supports_global_hotkeys(self) -> bool:
        return True

    # --- Focus detection ---

    def get_foreground_window_title(self) -> str:
        hwnd = _user32.GetForegroundWindow()
        return _get_window_title(hwnd)

    def get_foreground_window_id(self) -> int:
        return _user32.GetForegroundWindow()

    def find_window_by_title_prefix(self, prefix: str) -> int | None:
        hwnd = _user32.GetTopWindow(None)
        while hwnd:
            if _user32.IsWindowVisible(hwnd):
                title = _get_window_title(hwnd)
                if title.startswith(prefix):
                    return hwnd
            hwnd = _user32.GetWindow(hwnd, _GW_HWNDNEXT)
        return None

    def is_window_visible(self, wid: int) -> bool:
        return bool(_user32.IsWindowVisible(wid))

    def is_window_minimized(self, wid: int) -> bool:
        return bool(_user32.IsIconic(wid))

    def get_window_geometry(self, wid: int) -> tuple[int, int, int, int] | None:
        rect = ctypes.wintypes.RECT()
        if not _user32.GetWindowRect(wid, ctypes.byref(rect)):
            return None
        return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)

    def get_window_pid(self, wid: int) -> int:
        return _get_window_pid(wid)

    # --- Occlusion ---

    def is_window_occluded(self, target_wid: int, ignore_wids: set[int]) -> bool:
        game_rect = ctypes.wintypes.RECT()
        _user32.GetWindowRect(target_wid, ctypes.byref(game_rect))

        hwnd = _user32.GetTopWindow(None)
        while hwnd:
            if hwnd == target_wid:
                return False
            if hwnd not in ignore_wids:
                if _is_occluding_window(hwnd, game_rect):
                    return True
            hwnd = _user32.GetWindow(hwnd, _GW_HWNDNEXT)
        return False

    # --- Window manipulation ---

    def set_click_through(self, wid: int) -> bool:
        try:
            style = _user32.GetWindowLongW(wid, _GWL_EXSTYLE)
            style |= _WS_EX_LAYERED | _WS_EX_TRANSPARENT
            _user32.SetWindowLongW(wid, _GWL_EXSTYLE, style)
            return True
        except Exception as e:
            log.warning("Failed to set click-through: %s", e)
            return False

    def bring_to_foreground(self, wid: int) -> bool:
        try:
            fg_hwnd = _user32.GetForegroundWindow()
            if fg_hwnd == wid:
                return True

            fg_thread = _user32.GetWindowThreadProcessId(fg_hwnd, None)
            our_thread = _user32.GetWindowThreadProcessId(wid, None)

            attached = False
            if fg_thread != our_thread:
                attached = bool(
                    _user32.AttachThreadInput(fg_thread, our_thread, True),
                )

            _user32.SetForegroundWindow(wid)

            if attached:
                _user32.AttachThreadInput(fg_thread, our_thread, False)
            return True
        except Exception as e:
            log.warning("Failed to bring window to foreground: %s", e)
            return False

    def release_focus_to(self, title_prefix: str) -> bool:
        found = False

        def _enum_cb(hwnd, _):
            nonlocal found
            length = _user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                _user32.GetWindowTextW(hwnd, buf, length + 1)
                if buf.value.startswith(title_prefix):
                    _user32.SetForegroundWindow(hwnd)
                    found = True
                    return False  # stop enumeration
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p,
        )
        _user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
        return found

    def cloak_window(self, wid: int) -> None:
        """Cloak a window via DWM — hidden from the user but still composited.

        Used after winId() so the HWND gets its frameless/translucent styles
        composited by DWM without ever being visible.  Call uncloak_window()
        when the overlay is ready to appear.
        """
        val = ctypes.c_bool(True)
        _dwmapi.DwmSetWindowAttribute(
            wid, _DWMWA_CLOAK, ctypes.byref(val), ctypes.sizeof(val),
        )

    def uncloak_window(self, wid: int) -> None:
        """Remove DWM cloak — the window becomes visible immediately."""
        val = ctypes.c_bool(False)
        _dwmapi.DwmSetWindowAttribute(
            wid, _DWMWA_CLOAK, ctypes.byref(val), ctypes.sizeof(val),
        )

    # --- Decoration ---

    def enable_shadow(self, wid: int) -> bool:
        try:
            MARGINS = ctypes.c_int * 4
            margins = MARGINS(1, 1, 1, 1)
            _dwmapi.DwmExtendFrameIntoClientArea(wid, ctypes.byref(margins))
            return True
        except Exception:
            return False

    # --- Hotkeys ---

    def preinit_hotkeys(self) -> None:
        """Eagerly initialise the keyboard library's key-name tables.

        The first ``keyboard.hook()`` call triggers ``_setup_name_tables``
        which iterates every virtual-key code via ``ToUnicode`` — taking ~0.6s.
        Calling ``keyboard._winkeyboard.init()`` once at startup moves that
        cost off the focus-poll timer.
        """
        try:
            from keyboard import _winkeyboard
            _winkeyboard.init()
        except Exception:
            pass

    def register_hotkey_hook(self, callback) -> bool:
        try:
            import keyboard
            keyboard.hook(callback, suppress=True)
            return True
        except ImportError:
            return False
        except Exception as e:
            log.warning("Failed to register hotkey hook: %s", e)
            return False

    def unregister_hotkey_hook(self, callback=None) -> bool:
        try:
            import keyboard
            if callback is not None:
                keyboard.unhook(callback)
            else:
                keyboard.unhook_all()
            return True
        except Exception:
            return False

    # --- Window suppression ---

    def suppress_new_windows(self):
        """Context manager that hides any new windows created during its scope.

        Used to prevent V8/MiniRacer DLL initialization from flashing
        temporary native windows.  Installs a WH_CBT hook that intercepts
        HCBT_CREATEWND and immediately hides the window via ShowWindow(SW_HIDE).
        """
        import contextlib

        @contextlib.contextmanager
        def _suppress():
            pid = os.getpid()
            known: set[int] = set()

            # Snapshot existing windows
            WNDENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p,
            )
            def _enum(hwnd, _lp):
                lpdw = ctypes.wintypes.DWORD()
                _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw))
                if lpdw.value == pid:
                    known.add(hwnd)
                return True
            _user32.EnumWindows(WNDENUMPROC(_enum), 0)

            yield

            # Hide any new windows that appeared during the scope
            new_wins: list[int] = []
            def _enum2(hwnd, _lp):
                lpdw = ctypes.wintypes.DWORD()
                _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw))
                if lpdw.value == pid and hwnd not in known:
                    new_wins.append(hwnd)
                return True
            _user32.EnumWindows(WNDENUMPROC(_enum2), 0)
            for hwnd in new_wins:
                _user32.ShowWindow(hwnd, 0)  # SW_HIDE
                _user32.DestroyWindow(hwnd)

        return _suppress()

    # --- Desktop integration ---

    def set_app_id(self, app_id: str) -> None:
        _shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    def flash_taskbar(self, wid: int) -> None:
        fwi = _FLASHWINFO(
            cbSize=ctypes.sizeof(_FLASHWINFO),
            hwnd=wid,
            dwFlags=_FLASHW_ALL | _FLASHW_TIMERNOFG,
            uCount=0,
            dwTimeout=0,
        )
        _user32.FlashWindowEx(ctypes.byref(fwi))
