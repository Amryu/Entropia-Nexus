import sys
import threading
import numpy as np

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


class ScreenCapturer:
    """Captures screen regions using mss or Win32 PrintWindow.

    For game windows, use capture_window() which captures via PrintWindow —
    this gets only the window's own pixels, ignoring overlays on top.
    """

    def __init__(self):
        if mss is None:
            raise ImportError("mss is required for screen capture. Install with: pip install mss")
        self._local = threading.local()

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

    def capture_window(self, hwnd: int,
                       geometry: tuple[int, int, int, int] | None = None,
                       ) -> np.ndarray | None:
        """Capture a window's content.

        On Windows, uses PrintWindow (ignores overlays). On Linux, falls back
        to mss region capture using the provided *geometry* (x, y, w, h).

        Returns the window as a numpy array (BGR format), or None.
        """
        if sys.platform == "win32":
            return self._capture_window_win32(hwnd)
        # Linux: fall back to region capture using geometry
        if geometry is None:
            return None
        x, y, w, h = geometry
        return self.capture_region(x, y, w, h)

    def _capture_window_win32(self, hwnd: int) -> np.ndarray | None:
        """Capture a window via Win32 PrintWindow (ignores overlays)."""
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
