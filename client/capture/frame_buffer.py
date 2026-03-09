"""Rolling JPEG-compressed frame buffer for video clip capture."""

import threading
from collections import deque

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.logger import get_logger
from .constants import JPEG_QUALITY

log = get_logger("FrameBuffer")


class FrameBuffer:
    """Thread-safe rolling buffer of JPEG-compressed frames.

    Stores ``(timestamp, jpeg_bytes)`` tuples in a bounded deque.
    At 1080p 30fps with JPEG quality 80, memory usage is ~45MB for 15s.
    """

    def __init__(self, max_seconds: int = 15, fps: int = 30):
        self._max_frames = max(1, max_seconds * fps)
        self._buffer: deque[tuple[float, bytes]] = deque(maxlen=self._max_frames)
        self._lock = threading.Lock()
        self._encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY] if cv2 else []

    @property
    def max_seconds(self) -> int:
        return self._max_frames // max(1, self._fps_hint)

    @property
    def frame_count(self) -> int:
        with self._lock:
            return len(self._buffer)

    def resize(self, max_seconds: int, fps: int) -> None:
        """Change buffer capacity.  Drops oldest frames if shrinking."""
        new_max = max(1, max_seconds * fps)
        with self._lock:
            new_buf: deque[tuple[float, bytes]] = deque(maxlen=new_max)
            # Keep the most recent frames that fit
            for item in self._buffer:
                new_buf.append(item)
            self._buffer = new_buf
            self._max_frames = new_max

    def push(self, frame_bgr: np.ndarray, timestamp: float) -> None:
        """JPEG-encode a BGR frame and append to the buffer.

        Called on the capture thread.  JPEG encoding takes ~2-5ms for 1080p.
        """
        if cv2 is None:
            return
        ok, jpeg = cv2.imencode(".jpg", frame_bgr, self._encode_params)
        if not ok:
            return
        jpeg_bytes = jpeg.tobytes()
        with self._lock:
            self._buffer.append((timestamp, jpeg_bytes))

    def snapshot(
        self,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> list[tuple[float, bytes]]:
        """Return a copy of buffered frames within the time range.

        If start_time/end_time are None, returns all buffered frames.
        Thread-safe — takes a snapshot under lock.
        """
        with self._lock:
            if start_time is None and end_time is None:
                return list(self._buffer)
            result = []
            for ts, data in self._buffer:
                if start_time is not None and ts < start_time:
                    continue
                if end_time is not None and ts > end_time:
                    break
                result.append((ts, data))
            return result

    def clear(self) -> None:
        """Discard all buffered frames."""
        with self._lock:
            self._buffer.clear()

    def memory_usage_mb(self) -> float:
        """Estimate current memory usage in MB."""
        with self._lock:
            total = sum(len(data) for _, data in self._buffer)
        return total / (1024 * 1024)
