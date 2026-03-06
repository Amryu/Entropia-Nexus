"""Shared frame cache for OCR detectors.

Wraps a single ScreenCapturer and caches the latest window-capture result
with a timestamp. Multiple detectors polling at different rates can
share the same cached frame, avoiding redundant captures.

Also caches the grayscale conversion since multiple detectors need it.
"""

import threading
import time
from typing import Optional

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from .capturer import ScreenCapturer
from ..core.logger import get_logger

log = get_logger("FrameCache")


class SharedFrameCache:
    """Thread-safe frame cache wrapping a single ScreenCapturer.

    Callers request frames via get_frame(); if the cached frame is fresh
    enough (within max_age_ms), it is returned directly.  Otherwise a new
    window capture is performed and cached.
    """

    def __init__(self, capture_backend: str | None = None):
        self._capturer = ScreenCapturer(capture_backend=capture_backend)
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._gray: Optional[np.ndarray] = None
        self._frame_time: float = 0.0
        self._hwnd: Optional[int] = None

    def get_frame(self, hwnd: int, max_age_ms: float = 40,
                  geometry: Optional[tuple[int, int, int, int]] = None,
                  ) -> Optional[np.ndarray]:
        """Return cached frame if fresh enough, else capture a new one.

        Args:
            hwnd: Window handle to capture.
            max_age_ms: Maximum age of a cached frame in milliseconds.
            geometry: Optional (x, y, w, h) for non-Win32 fallback.

        Returns:
            BGR numpy array of the game window, or None on failure.
        """
        now = time.monotonic()
        with self._lock:
            if (self._frame is not None
                    and self._hwnd == hwnd
                    and (now - self._frame_time) * 1000 < max_age_ms):
                return self._frame

            frame = self._capturer.capture_window(hwnd, geometry=geometry)
            if frame is not None:
                self._frame = frame
                self._gray = None  # invalidate cached grayscale
                self._frame_time = now
                self._hwnd = hwnd
            return frame

    def set_capture_backend(self, capture_backend: str | None) -> None:
        """Update capture backend at runtime and clear cached frames."""
        with self._lock:
            self._capturer.set_capture_backend(capture_backend)
            self._frame = None
            self._gray = None
            self._frame_time = 0.0
            self._hwnd = None

    def get_frame_gray(self, hwnd: int, max_age_ms: float = 40,
                       geometry: Optional[tuple[int, int, int, int]] = None,
                       ) -> Optional[np.ndarray]:
        """Return cached grayscale frame (avoids repeated cvtColor).

        Calls get_frame() internally, then caches the grayscale conversion.
        """
        if cv2 is None:
            return None
        frame = self.get_frame(hwnd, max_age_ms, geometry)
        if frame is None:
            return None
        with self._lock:
            if self._gray is None:
                self._gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return self._gray

    def invalidate(self):
        """Clear the cache (e.g. when the game window handle changes)."""
        with self._lock:
            self._frame = None
            self._gray = None
            self._frame_time = 0.0
            self._hwnd = None
