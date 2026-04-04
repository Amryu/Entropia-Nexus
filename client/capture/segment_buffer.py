"""Rolling buffer of H.264 segment files with time-range queries."""

import math
import os
import shutil
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.logger import get_logger
from .constants import SEGMENT_DURATION_S

log = get_logger("SegmentBuffer")


@dataclass(frozen=True)
class SegmentInfo:
    """Metadata for a single encoded segment file."""

    path: Path
    start_time: float   # monotonic timestamp of first frame
    end_time: float      # monotonic timestamp of last frame
    index: int           # sequence number


class SegmentBuffer:
    """Thread-safe rolling buffer of H.264 segment files.

    Segments are added via :meth:`on_segment_complete` (called by the
    :class:`SegmentEncoder` when FFmpeg finishes a segment).  Old segments
    are deleted when the buffer exceeds its configured duration.
    """

    def __init__(self, max_seconds: int = 15, segment_duration: int = SEGMENT_DURATION_S):
        self._max_segments = max(1, math.ceil(max_seconds / max(1, segment_duration)) + 1)
        self._segment_duration = segment_duration
        self._segments: deque[SegmentInfo] = deque()
        self._lock = threading.Lock()
        self._next_index = 0

    @property
    def segment_count(self) -> int:
        with self._lock:
            return len(self._segments)

    def on_segment_complete(self, path: Path, start_time: float, end_time: float) -> None:
        """Register a newly completed segment.

        If the buffer is over capacity, the oldest segment file is deleted.
        """
        info = SegmentInfo(
            path=path,
            start_time=start_time,
            end_time=end_time,
            index=self._next_index,
        )
        self._next_index += 1

        with self._lock:
            self._segments.append(info)
            while len(self._segments) > self._max_segments:
                old = self._segments.popleft()
                self._delete_file(old.path)

    def get_segments(
        self,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> list[SegmentInfo]:
        """Return segments overlapping the requested time range.

        Includes segments that partially overlap (the remuxer trims).
        """
        with self._lock:
            if start_time is None and end_time is None:
                return list(self._segments)
            result = []
            for seg in self._segments:
                if end_time is not None and seg.start_time > end_time:
                    break
                if start_time is not None and seg.end_time < start_time:
                    continue
                result.append(seg)
            return result

    def get_thumbnail_frame(self, timestamp: float) -> np.ndarray | None:
        """Decode a single frame from the segment containing *timestamp*.

        Returns a BGR numpy array or None on failure.
        """
        if cv2 is None:
            return None

        segments = self.get_segments(timestamp, timestamp)
        if not segments:
            return None

        seg = segments[0]
        try:
            cap = cv2.VideoCapture(str(seg.path))
            if not cap.isOpened():
                return None
            # Seek to approximate position within segment
            offset = max(0, timestamp - seg.start_time)
            cap.set(cv2.CAP_PROP_POS_MSEC, offset * 1000)
            ok, frame = cap.read()
            cap.release()
            return frame if ok else None
        except Exception:
            log.debug("Thumbnail extraction failed for %s", seg.path)
            return None

    def resize(self, max_seconds: int) -> None:
        """Change buffer capacity.  Deletes excess old segments."""
        new_max = max(1, math.ceil(max_seconds / max(1, self._segment_duration)) + 1)
        with self._lock:
            self._max_segments = new_max
            while len(self._segments) > self._max_segments:
                old = self._segments.popleft()
                self._delete_file(old.path)

    def clear(self) -> None:
        """Delete all segment files and clear the buffer."""
        with self._lock:
            for seg in self._segments:
                self._delete_file(seg.path)
            self._segments.clear()

    def cleanup(self) -> None:
        """Clear buffer and remove the parent temp directory if empty."""
        dirs = set()
        with self._lock:
            for seg in self._segments:
                dirs.add(seg.path.parent)
                self._delete_file(seg.path)
            self._segments.clear()
        for d in dirs:
            try:
                if d.exists() and not any(d.iterdir()):
                    shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass

    @staticmethod
    def _delete_file(path: Path) -> None:
        try:
            if path.exists():
                os.unlink(path)
        except OSError:
            log.debug("Failed to delete segment: %s", path)
