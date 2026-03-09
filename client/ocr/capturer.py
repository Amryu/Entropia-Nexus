import os
import sys
import threading
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

WINDOW_BACKENDS = {"auto", "printwindow", "wgc"}
DEFAULT_CAPTURE_BACKEND = "auto"
WGC_MAX_FAIL_STREAK = 5

# Windows build that introduced GraphicsCaptureSession.IsBorderRequired
_WGC_BORDERLESS_MIN_BUILD = 20348


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


# ---------------------------------------------------------------------------
# Persistent WGC session (wraps windows-capture)
# ---------------------------------------------------------------------------

class _WgcPersistentSession:
    """Keeps a single WGC session alive across frames.

    The session runs on its own thread (via ``start_free_threaded``).
    ``on_frame_arrived`` stores the latest BGR frame; callers retrieve it
    with :meth:`get_frame`.
    """

    def __init__(self, window_name: str, draw_border: bool | None):
        self._latest_frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._control = None
        self._closed = False

        from windows_capture.windows_capture import NativeWindowsCapture

        native = NativeWindowsCapture(
            self._on_frame,
            self._on_closed,
            False,           # cursor_capture
            draw_border,
            None,            # secondary_window
            None,            # minimum_update_interval
            None,            # dirty_region
            None,            # monitor_index
            window_name,
        )
        self._control = native.start_free_threaded()

    def _on_frame(self, buf, buf_len, width, height, stop_list, timespan):
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

    def __init__(self, capture_backend: str | None = None):
        if mss is None:
            raise ImportError("mss is required for screen capture. Install with: pip install mss")
        self._local = threading.local()
        self._capture_backend_preference = self._normalize_backend_name(
            capture_backend or os.getenv("NEXUS_CAPTURE_BACKEND", DEFAULT_CAPTURE_BACKEND),
        )
        self._active_window_backend = "printwindow"
        self._wgc_fail_streak = 0

        # Persistent WGC session state
        self._wgc_session: Optional[_WgcPersistentSession] = None
        self._wgc_session_hwnd: Optional[int] = None
        self._wgc_draw_border: bool | None = None  # False = borderless, None = OS default
        self._wgc_available = False

        if sys.platform == "win32":
            self._init_windows_backend()

    def set_capture_backend(self, capture_backend: str | None) -> None:
        """Update backend preference at runtime."""
        self._stop_wgc_session()
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
            "gdi": "printwindow",
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
        if self._capture_backend_preference == "printwindow":
            self._active_window_backend = "printwindow"
            log.info("Window capture backend: PrintWindow")
            return

        if self._capture_backend_preference in {"auto", "wgc"}:
            if self._is_wgc_available():
                self._wgc_available = True
                self._wgc_draw_border = False if self._is_borderless_supported() else None
                self._active_window_backend = "wgc"
                border_info = "borderless" if self._wgc_draw_border is False else "with border"
                log.info("Window capture backend: Windows Graphics Capture (%s)", border_info)
                return
            if self._capture_backend_preference == "wgc":
                log.warning(
                    "WGC backend was requested but is unavailable. Falling back to PrintWindow.",
                )

        self._active_window_backend = "printwindow"
        if self._capture_backend_preference == "auto":
            log.info("Window capture backend: PrintWindow (WGC not available)")

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
        try:
            self._wgc_session = _WgcPersistentSession(title, draw_border)
            self._wgc_session_hwnd = hwnd
            return True
        except Exception as e:
            err_msg = str(e).lower()
            # If borderless was requested but unsupported, retry with OS default
            if draw_border is False and "border" in err_msg:
                log.warning("Borderless WGC not supported; retrying with OS default border")
                self._wgc_draw_border = None
                try:
                    self._wgc_session = _WgcPersistentSession(title, None)
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

        On Windows, tries the configured backend (WGC or PrintWindow) and
        falls back to PrintWindow as needed. On Linux, falls back to mss
        region capture using *geometry* (x, y, w, h).

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
                    log.debug("WGC session returned no frame; using PrintWindow fallback")
                if self._wgc_fail_streak >= WGC_MAX_FAIL_STREAK:
                    log.warning(
                        "WGC returned no frames %d times in a row; disabling WGC for this session",
                        self._wgc_fail_streak,
                    )
                    self._stop_wgc_session()
                    self._active_window_backend = "printwindow"
            return self._capture_window_win32(hwnd)

        # Linux: fall back to region capture using geometry
        if geometry is None:
            return None
        x, y, w, h = geometry
        return self.capture_region(x, y, w, h)

    def _capture_from_wgc_session(self, hwnd: int) -> np.ndarray | None:
        """Get the latest frame from the persistent WGC session.

        Starts a new session if needed, restarts if the HWND changed or
        the session closed.
        """
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
