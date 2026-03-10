import os
import sys
import threading
import time
from contextlib import contextmanager
from typing import Optional

import numpy as np

from ..core.logger import get_logger

try:
    import mss
    import mss.tools
except ImportError:
    mss = None

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    # Win32 GDI constants for PrintWindow capture
    PW_RENDERFULLCONTENT = 0x00000002
    SRCCOPY = 0x00CC0020
    DIB_RGB_COLORS = 0

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    # Win32 DPI awareness context constant
    DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)


log = get_logger("Capturer")

WINDOW_BACKENDS = {"auto", "printwindow", "bitblt", "wgc"}
DEFAULT_CAPTURE_BACKEND = "auto"
WGC_MAX_FAIL_STREAK = 5

# Windows build that introduced GraphicsCaptureSession.IsBorderRequired
_WGC_BORDERLESS_MIN_BUILD = 20348

# Windows build that introduced GraphicsCaptureSession.MinUpdateInterval
# (Windows 11 22H2).  On older builds the parameter is silently ignored.
_WGC_MIN_UPDATE_INTERVAL_BUILD = 22621


@contextmanager
def _thread_per_monitor_dpi():
    """Temporarily opt current thread into PMv2 where supported."""
    if sys.platform != "win32":
        yield
        return
    set_thread_ctx = getattr(user32, "SetThreadDpiAwarenessContext", None)
    if set_thread_ctx is None:
        yield
        return
    previous = None
    try:
        previous = set_thread_ctx(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    except Exception:
        previous = None
    try:
        yield
    finally:
        if previous:
            try:
                set_thread_ctx(previous)
            except Exception:
                pass


def get_monitor_refresh_rate() -> int:
    """Return the primary monitor's refresh rate in Hz.

    Uses Qt's QScreen API which handles DPI-awareness, multi-monitor, and
    variable-refresh-rate correctly.  Falls back to 60 if unavailable.
    """
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            screen = app.primaryScreen()
            if screen is not None:
                hz = screen.refreshRate()
                if hz and hz > 1:
                    return int(round(hz))
    except Exception:
        pass
    return 60


def resolve_clip_backend(preference: str, clip_fps: int) -> str:
    """Resolve 'auto' clip capture backend to a concrete backend.

    Auto logic: Use WGC when the clip FPS matches (or exceeds) the monitor
    refresh rate, since WGC inherently captures at the display's refresh rate.
    For lower FPS, BitBlt is more efficient because WGC cannot be throttled on
    older Windows builds and wastes GPU on frames that will be dropped.

    Returns 'wgc' or 'bitblt'.
    """
    if preference == "wgc":
        return "wgc"
    if preference == "bitblt":
        return "bitblt"
    # auto: WGC only when FPS matches display rate
    monitor_hz = get_monitor_refresh_rate()
    if clip_fps >= monitor_hz:
        return "wgc"
    return "bitblt"


# ---------------------------------------------------------------------------
# Persistent WGC session (wraps windows-capture)
# ---------------------------------------------------------------------------

class _WgcPersistentSession:
    """Keeps a single WGC session alive across frames.

    The session runs on its own thread (via ``start_free_threaded``).
    ``on_frame_arrived`` stores the latest BGR frame; callers retrieve it
    with :meth:`get_frame`.

    *min_interval* (seconds) throttles ``_on_frame`` so the expensive
    numpy copy is skipped when a new frame arrives too soon.
    *update_interval_ms* is passed to the OS via ``minimum_update_interval``
    to reduce GPU-side frame delivery (Windows 11 22H2+).
    """

    def __init__(
        self,
        window_name: str,
        draw_border: bool | None,
        min_interval: float = 0.0,
        update_interval_ms: int | None = None,
    ):
        self._latest_frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._control = None
        self._closed = False
        self._min_interval = min_interval
        self._last_frame_time = 0.0

        from windows_capture.windows_capture import NativeWindowsCapture

        native = NativeWindowsCapture(
            self._on_frame,
            self._on_closed,
            False,                # cursor_capture
            draw_border,
            None,                 # secondary_window
            update_interval_ms,   # minimum_update_interval (milliseconds)
            None,                 # dirty_region
            None,                 # monitor_index
            window_name,
        )
        self._control = native.start_free_threaded()

    def _on_frame(self, buf, buf_len, width, height, stop_list, timespan):
        # Software throttle: skip the expensive numpy copy if too soon
        now = time.monotonic()
        if self._min_interval > 0 and (now - self._last_frame_time) < self._min_interval:
            return
        self._last_frame_time = now

        row_pitch = buf_len // height
        if row_pitch == width * 4:
            arr = np.ctypeslib.as_array(
                ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint8)),
                shape=(height, width, 4),
            )
        else:
            arr = np.ctypeslib.as_array(
                ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint8)),
                shape=(height, row_pitch),
            )[:, :width * 4].reshape(height, width, 4)
        # BGRA → BGR, copy to own buffer so the native side can free its memory
        bgr = arr[:, :, :3].copy()
        with self._lock:
            self._latest_frame = bgr

    def _on_closed(self):
        self._closed = True

    def set_min_interval(self, interval: float) -> None:
        """Update the software throttle interval (seconds)."""
        self._min_interval = interval

    def get_frame(self) -> np.ndarray | None:
        with self._lock:
            return self._latest_frame

    @property
    def is_closed(self) -> bool:
        return self._closed

    def stop(self):
        if self._control:
            try:
                self._control.stop()
            except Exception:
                pass
            self._control = None


# ---------------------------------------------------------------------------
# Main capturer
# ---------------------------------------------------------------------------

class ScreenCapturer:
    """Captures screen regions using mss or a Windows window-capture backend.

    For game windows, use capture_window() which captures only the window's
    own pixels, ignoring overlays on top.
    """

    #: Class-level tracker so the backend message is only logged once
    #: across all instances (avoids spamming the ring buffer).
    _logged_backend: str | None = None

    def __init__(self, capture_backend: str | None = None):
        if mss is None:
            raise ImportError("mss is required for screen capture. Install with: pip install mss")
        self._local = threading.local()
        self._capture_backend_preference = self._normalize_backend_name(
            capture_backend or os.getenv("NEXUS_CAPTURE_BACKEND", DEFAULT_CAPTURE_BACKEND),
        )
        self._active_window_backend: str | None = None
        self._wgc_fail_streak = 0

        # Persistent WGC session state
        self._wgc_session: Optional[_WgcPersistentSession] = None
        self._wgc_session_hwnd: Optional[int] = None
        self._wgc_draw_border: bool | None = None  # False = borderless, None = OS default
        self._wgc_available = False
        self._wgc_min_interval: float = 0.0        # software throttle (seconds)
        self._wgc_update_interval_ms: int | None = None  # OS-level throttle (ms)
        self._wgc_suspended = False                      # True → session torn down, use BitBlt

        if sys.platform == "win32":
            self._init_windows_backend()

    def set_capture_backend(self, capture_backend: str | None) -> None:
        """Update backend preference at runtime."""
        self._stop_wgc_session()
        self._wgc_suspended = False
        self._capture_backend_preference = self._normalize_backend_name(
            capture_backend or DEFAULT_CAPTURE_BACKEND,
        )
        self._wgc_fail_streak = 0
        if sys.platform == "win32":
            self._init_windows_backend()

    def stop(self) -> None:
        """Clean up persistent sessions.  Called when the distributor stops."""
        self._stop_wgc_session()

    @property
    def active_window_backend(self) -> str:
        """Return the active Windows window-capture backend."""
        return self._active_window_backend

    def _normalize_backend_name(self, value: str) -> str:
        name = (value or DEFAULT_CAPTURE_BACKEND).strip().lower()
        aliases = {
            "default": "auto",
            "gdi": "bitblt",
            "print": "printwindow",
            "print_window": "printwindow",
            "wgcapture": "wgc",
            "windows_graphics_capture": "wgc",
        }
        normalized = aliases.get(name, name)
        if normalized not in WINDOW_BACKENDS:
            log.warning(
                "Unknown capture backend '%s'. Falling back to '%s'.",
                value, DEFAULT_CAPTURE_BACKEND,
            )
            return DEFAULT_CAPTURE_BACKEND
        return normalized

    def _init_windows_backend(self) -> None:
        pref = self._capture_backend_preference
        prev = self._active_window_backend

        if pref == "printwindow":
            self._active_window_backend = "printwindow"
        elif pref == "bitblt":
            self._active_window_backend = "bitblt"
        elif pref in {"auto", "wgc"}:
            wgc_ok = self._is_wgc_available()
            borderless = wgc_ok and self._is_borderless_supported()
            can_throttle = self._os_supports_min_update_interval()

            if pref == "auto" and borderless and can_throttle:
                # Auto: only use WGC when the OS can throttle it
                self._wgc_available = True
                self._wgc_draw_border = False
                self._active_window_backend = "wgc"
            elif pref == "wgc":
                # Explicit WGC request — honour it (warning shown in settings)
                if wgc_ok:
                    self._wgc_available = True
                    self._wgc_draw_border = False if borderless else None
                    self._active_window_backend = "wgc"
                else:
                    log.warning("WGC requested but unavailable, falling back to BitBlt")
                    self._active_window_backend = "bitblt"
            else:
                self._active_window_backend = "bitblt"

        backend = self._active_window_backend
        if backend != prev or backend != ScreenCapturer._logged_backend:
            names = {
                "printwindow": "PrintWindow",
                "bitblt": "BitBlt",
                "wgc": "Windows Graphics Capture",
            }
            name = names.get(backend, backend)
            if backend == "wgc":
                border = "borderless" if self._wgc_draw_border is False else "with border"
                name = f"{name} ({border})"
            log.info("Window capture backend: %s", name)
            ScreenCapturer._logged_backend = backend

    @staticmethod
    def _is_wgc_available() -> bool:
        """Check if the windows-capture library can be loaded."""
        try:
            from windows_capture.windows_capture import NativeWindowsCapture  # noqa: F401
            return True
        except Exception:
            return False

    @staticmethod
    def _is_borderless_supported() -> bool:
        """Check if the OS supports WGC borderless capture (IsBorderRequired).

        Tries to create a session with ``draw_border=False`` targeting a
        non-existent window name.  If ``windows-capture`` raises a border-
        specific error the API is unavailable; any other outcome (including
        window-not-found errors) means the border setting was accepted.
        """
        if sys.platform != "win32":
            return False
        # Windows builds >= 20348 natively support IsBorderRequired.
        # All Windows 11 versions (build 22000+) satisfy this.  Skip the
        # fragile runtime probe when the OS version already guarantees support.
        if sys.getwindowsversion().build >= _WGC_BORDERLESS_MIN_BUILD:
            return True
        try:
            from windows_capture.windows_capture import NativeWindowsCapture

            def _noop_frame(*a):
                pass

            def _noop_closed():
                pass

            native = NativeWindowsCapture(
                _noop_frame,
                _noop_closed,
                False,                                    # cursor_capture
                False,                                    # draw_border
                None,                                     # secondary_window
                None,                                     # minimum_update_interval
                None,                                     # dirty_region
                1,                                        # monitor_index (primary)
                None,                                     # window_name
            )
            # The session will start on the primary monitor.  If the OS
            # rejects draw_border=False the error is raised here.
            ctrl = native.start_free_threaded()
            ctrl.stop()
            return True
        except Exception as e:
            err_msg = str(e).lower()
            log.warning("WGC borderless probe error: %s", e)
            if "border" in err_msg:
                return False
            # Any other error (e.g. window not found) means the border setting
            # was accepted before the window lookup failed.
            return True

    # ------------------------------------------------------------------
    # Persistent WGC session management
    # ------------------------------------------------------------------

    @staticmethod
    def _hwnd_to_title(hwnd: int) -> str:
        """Return the window title for *hwnd*, or empty string on failure."""
        try:
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return ""
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value
        except Exception:
            return ""

    def _start_wgc_session(self, hwnd: int) -> bool:
        """Start a persistent WGC session for *hwnd*.  Returns True on success."""
        title = self._hwnd_to_title(hwnd)
        if not title:
            log.warning("WGC session start failed: could not get window title for hwnd %s", hwnd)
            return False
        draw_border = self._wgc_draw_border
        min_iv = self._wgc_min_interval
        update_ms = self._wgc_update_interval_ms
        try:
            self._wgc_session = _WgcPersistentSession(
                title, draw_border,
                min_interval=min_iv, update_interval_ms=update_ms,
            )
            self._wgc_session_hwnd = hwnd
            return True
        except Exception as e:
            err_msg = str(e).lower()
            # If borderless was requested but unsupported, retry with OS default
            if draw_border is False and "border" in err_msg:
                log.warning("Borderless WGC not supported; retrying with OS default border")
                self._wgc_draw_border = None
                try:
                    self._wgc_session = _WgcPersistentSession(
                        title, None,
                        min_interval=min_iv, update_interval_ms=update_ms,
                    )
                    self._wgc_session_hwnd = hwnd
                    return True
                except Exception as e2:
                    log.warning("WGC session start failed: %s", e2)
            else:
                log.warning("WGC session start failed: %s", e)
            self._wgc_session = None
            self._wgc_session_hwnd = None
            return False

    def _stop_wgc_session(self) -> None:
        """Stop the current persistent WGC session, if any."""
        if self._wgc_session is not None:
            self._wgc_session.stop()
            self._wgc_session = None
            self._wgc_session_hwnd = None

    @staticmethod
    def _os_supports_min_update_interval() -> bool:
        """True if the OS supports ``MinUpdateInterval`` (Win 11 22H2+)."""
        return (sys.platform == "win32"
                and sys.getwindowsversion().build >= _WGC_MIN_UPDATE_INTERVAL_BUILD)

    def set_wgc_throttle(self, interval_s: float, boosted: bool = False) -> None:
        """Control WGC session lifecycle based on capture rate.

        When *boosted* (video clips active), keeps the WGC session alive
        with a software throttle and OS-level ``minimum_update_interval``.

        When not boosted (OCR-only):
        - On Windows 11 22H2+ where ``MinUpdateInterval`` is supported,
          keeps WGC alive but throttled via the OS — low GPU overhead.
        - On older Windows where the parameter is ignored, **suspends**
          the WGC session entirely and falls through to BitBlt.
        """
        new_ms = max(1, int(interval_s * 1000)) if interval_s > 0 else None
        old_ms = self._wgc_update_interval_ms

        self._wgc_min_interval = interval_s
        self._wgc_update_interval_ms = new_ms

        if not boosted and not self._os_supports_min_update_interval():
            # OS can't throttle WGC — suspend to free GPU resources.
            # capture_window() will fall through to BitBlt.
            if not self._wgc_suspended:
                self._wgc_suspended = True
                if self._wgc_session is not None:
                    log.info("WGC suspended (OS lacks MinUpdateInterval, %.1f Hz) "
                             "— using BitBlt",
                             1.0 / interval_s if interval_s > 0 else 0)
                    self._stop_wgc_session()
            return

        # OS supports MinUpdateInterval, or we're boosted — keep WGC alive.
        if self._wgc_suspended:
            self._wgc_suspended = False
            log.info("WGC resumed (%.1f Hz, update_interval=%sms)",
                     1.0 / interval_s if interval_s > 0 else 0, new_ms)
            # Session will be started lazily on next capture_window() call
            return

        # Already running — update software throttle and restart if
        # OS-level interval changed significantly
        if self._wgc_session is not None:
            self._wgc_session.set_min_interval(interval_s)

            if old_ms and new_ms:
                ratio = new_ms / old_ms
                if ratio > 2.0 or ratio < 0.5:
                    hwnd = self._wgc_session_hwnd
                    log.info("WGC throttle changed %dms → %dms, restarting session",
                             old_ms, new_ms)
                    self._stop_wgc_session()
                    if hwnd:
                        self._start_wgc_session(hwnd)

    # ------------------------------------------------------------------
    # Public capture API
    # ------------------------------------------------------------------

    def _get_sct(self):
        """Get or create the mss instance for the current thread."""
        if not hasattr(self._local, "sct"):
            self._local.sct = mss.mss()
        return self._local.sct

    def capture_full_screen(self, monitor_index: int = 1) -> np.ndarray:
        """Capture the full screen as a numpy array (BGR format)."""
        sct = self._get_sct()
        monitor = sct.monitors[monitor_index]
        screenshot = sct.grab(monitor)
        return np.array(screenshot)[:, :, :3]  # Drop alpha channel

    def capture_region(self, x: int, y: int, width: int, height: int) -> np.ndarray:
        """Capture a specific screen region as a numpy array (BGR format).

        NOTE: This captures everything visible at that region, including
        overlays. For game windows, prefer capture_window() instead.
        """
        sct = self._get_sct()
        region = {"left": x, "top": y, "width": width, "height": height}
        screenshot = sct.grab(region)
        return np.array(screenshot)[:, :, :3]

    def capture_window(
        self,
        hwnd: int,
        geometry: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray | None:
        """Capture a window's content.

        On Windows, tries the configured backend (WGC, BitBlt, or
        PrintWindow) and falls back to BitBlt as needed. On Linux, falls
        back to mss region capture using *geometry* (x, y, w, h).

        Returns the window as a numpy array (BGR format), or None.
        """
        if sys.platform == "win32":
            if self._active_window_backend == "wgc":
                frame = self._capture_from_wgc_session(hwnd)
                if frame is not None:
                    self._wgc_fail_streak = 0
                    return frame

                self._wgc_fail_streak += 1
                if self._wgc_fail_streak == 1:
                    log.debug("WGC session returned no frame; using BitBlt fallback")
                if self._wgc_fail_streak >= WGC_MAX_FAIL_STREAK:
                    log.warning(
                        "WGC returned no frames %d times in a row; "
                        "stopping session (will retry on next call)",
                        self._wgc_fail_streak,
                    )
                    self._stop_wgc_session()
                    self._wgc_fail_streak = 0
            if self._active_window_backend == "bitblt":
                return self._capture_window_bitblt(hwnd)
            if self._active_window_backend == "printwindow":
                return self._capture_window_win32(hwnd)
            # WGC frame miss — use BitBlt for the single fallback frame
            return self._capture_window_bitblt(hwnd)

        # Linux: fall back to region capture using geometry
        if geometry is None:
            return None
        x, y, w, h = geometry
        return self.capture_region(x, y, w, h)

    def _capture_from_wgc_session(self, hwnd: int) -> np.ndarray | None:
        """Get the latest frame from the persistent WGC session.

        Starts a new session if needed, restarts if the HWND changed or
        the session closed.  Returns None immediately when the session
        is suspended (low-Hz mode uses BitBlt instead to save GPU).
        """
        if self._wgc_suspended:
            return None

        # Restart session if HWND changed or session died
        if (self._wgc_session_hwnd != hwnd
                or self._wgc_session is None
                or self._wgc_session.is_closed):
            self._stop_wgc_session()
            if not self._start_wgc_session(hwnd):
                return None

        return self._wgc_session.get_frame()

    def _capture_window_win32(self, hwnd: int) -> np.ndarray | None:
        """Capture a window via Win32 PrintWindow (ignores overlays)."""
        with _thread_per_monitor_dpi():
            # Get client area dimensions
            rect = ctypes.wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            width = rect.right - rect.left
            height = rect.bottom - rect.top

            if width <= 0 or height <= 0:
                return None

            # Create a device context and bitmap for the capture
            hwnd_dc = user32.GetDC(hwnd)
            if not hwnd_dc:
                return None

            mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
            bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
            gdi32.SelectObject(mem_dc, bitmap)

            # PrintWindow with PW_RENDERFULLCONTENT for DX/GL content
            result = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)

            if not result:
                # Fallback: try BitBlt (works for standard windows, not DX)
                gdi32.BitBlt(mem_dc, 0, 0, width, height, hwnd_dc, 0, 0, SRCCOPY)

            # Extract pixel data from the bitmap
            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", ctypes.c_uint32),
                    ("biWidth", ctypes.c_int32),
                    ("biHeight", ctypes.c_int32),
                    ("biPlanes", ctypes.c_uint16),
                    ("biBitCount", ctypes.c_uint16),
                    ("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32),
                    ("biXPelsPerMeter", ctypes.c_int32),
                    ("biYPelsPerMeter", ctypes.c_int32),
                    ("biClrUsed", ctypes.c_uint32),
                    ("biClrImportant", ctypes.c_uint32),
                ]

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = width
            bmi.biHeight = -height  # Negative = top-down DIB
            bmi.biPlanes = 1
            bmi.biBitCount = 32  # BGRA
            bmi.biCompression = 0  # BI_RGB

            buffer_size = width * height * 4
            buffer = ctypes.create_string_buffer(buffer_size)

            gdi32.GetDIBits(
                mem_dc, bitmap, 0, height,
                buffer, ctypes.byref(bmi), DIB_RGB_COLORS,
            )

            # Cleanup GDI resources
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hwnd, hwnd_dc)

            # Convert to numpy array (BGRA -> BGR)
            image = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)
            return image[:, :, :3]  # Drop alpha channel

    def _capture_window_bitblt(self, hwnd: int) -> np.ndarray | None:
        """Capture a window via BitBlt from its device context.

        Copies the window's client area directly via its DC.  Unlike
        PrintWindow, does not send WM_PRINT so there is no flicker.
        May return black for DirectX/OpenGL surfaces that don't
        render to the GDI-accessible buffer.
        """
        with _thread_per_monitor_dpi():
            rect = ctypes.wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width <= 0 or height <= 0:
                return None

            hwnd_dc = user32.GetDC(hwnd)
            if not hwnd_dc:
                return None

            mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
            bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
            gdi32.SelectObject(mem_dc, bitmap)

            gdi32.BitBlt(mem_dc, 0, 0, width, height, hwnd_dc, 0, 0, SRCCOPY)

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", ctypes.c_uint32),
                    ("biWidth", ctypes.c_int32),
                    ("biHeight", ctypes.c_int32),
                    ("biPlanes", ctypes.c_uint16),
                    ("biBitCount", ctypes.c_uint16),
                    ("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32),
                    ("biXPelsPerMeter", ctypes.c_int32),
                    ("biYPelsPerMeter", ctypes.c_int32),
                    ("biClrUsed", ctypes.c_uint32),
                    ("biClrImportant", ctypes.c_uint32),
                ]

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = width
            bmi.biHeight = -height  # top-down DIB
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0  # BI_RGB

            buffer_size = width * height * 4
            buffer = ctypes.create_string_buffer(buffer_size)

            gdi32.GetDIBits(
                mem_dc, bitmap, 0, height,
                buffer, ctypes.byref(bmi), DIB_RGB_COLORS,
            )

            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hwnd, hwnd_dc)

            image = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)
            return image[:, :, :3]
