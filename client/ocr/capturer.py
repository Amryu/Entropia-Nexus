import os
import sys
import threading
from contextlib import contextmanager
from typing import Callable, Optional

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
        self._wgc_capture_fn: Optional[Callable[[str], object]] = None
        self._wgc_fail_streak = 0

        if sys.platform == "win32":
            self._init_windows_backend()

    def set_capture_backend(self, capture_backend: str | None) -> None:
        """Update backend preference at runtime."""
        self._capture_backend_preference = self._normalize_backend_name(
            capture_backend or DEFAULT_CAPTURE_BACKEND,
        )
        self._wgc_fail_streak = 0
        if sys.platform == "win32":
            self._init_windows_backend()

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
            self._wgc_capture_fn = self._load_wgc_capture_fn()
            if self._wgc_capture_fn is not None:
                self._active_window_backend = "wgc"
                log.info("Window capture backend: Windows Graphics Capture")
                return
            if self._capture_backend_preference == "wgc":
                log.warning(
                    "WGC backend was requested but is unavailable. Falling back to PrintWindow.",
                )

        self._active_window_backend = "printwindow"
        if self._capture_backend_preference == "auto":
            log.info("Window capture backend: PrintWindow (WGC not available)")

    def _load_wgc_capture_fn(self) -> Optional[Callable[[str], object]]:
        try:
            import wgcapture
        except Exception:
            return None

        capture_fn = getattr(wgcapture, "capture_screen", None)
        if not callable(capture_fn):
            log.warning("wgcapture module is present but capture_screen() is missing")
            return None
        return capture_fn

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
                image = self._capture_window_wgc(hwnd)
                if image is not None:
                    self._wgc_fail_streak = 0
                    return image

                self._wgc_fail_streak += 1
                if self._wgc_fail_streak == 1:
                    log.debug("WGC capture failed; using PrintWindow fallback")
                if self._wgc_fail_streak >= WGC_MAX_FAIL_STREAK:
                    log.warning(
                        "WGC failed %d times in a row; disabling WGC for this session",
                        self._wgc_fail_streak,
                    )
                    self._active_window_backend = "printwindow"
            return self._capture_window_win32(hwnd)

        # Linux: fall back to region capture using geometry
        if geometry is None:
            return None
        x, y, w, h = geometry
        return self.capture_region(x, y, w, h)

    def _capture_window_wgc(self, hwnd: int) -> np.ndarray | None:
        """Capture via Windows Graphics Capture wrapper (if available)."""
        if self._wgc_capture_fn is None:
            return None

        title = self._get_window_title_win32(hwnd)
        if not title:
            return None

        try:
            raw = self._wgc_capture_fn(title)
        except Exception as e:
            log.debug("WGC capture raised for '%s': %s", title, e)
            return None
        if raw is None:
            return None

        image = np.asarray(raw)
        if image.ndim != 3 or image.shape[2] < 3:
            log.debug("WGC capture returned invalid shape: %s", getattr(image, "shape", None))
            return None

        if image.dtype != np.uint8:
            image = image.astype(np.uint8, copy=False)

        # wgcapture returns RGB/RGBA. Convert to BGR for OpenCV pipeline.
        return image[:, :, [2, 1, 0]]

    def _get_window_title_win32(self, hwnd: int) -> str:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value

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
