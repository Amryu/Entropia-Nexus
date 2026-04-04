"""Dedicated frame effects processor for the encode-first pipeline.

Applies blur regions, webcam overlay, background compositing, and resize
on a dedicated thread before frames reach the H.264 encoder.
"""

import queue
import threading

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.logger import get_logger
from .constants import get_interpolation
from .screenshot import apply_blur_regions, compose_on_background
from .video_effects import composite_webcam

log = get_logger("EffectsProcessor")


class EffectsProcessor:
    """Process raw captured frames through visual effects on a dedicated thread.

    Frames are queued via :meth:`push` and delivered to *on_frame* after
    effects are applied.  The queue is bounded — if the encoder can't keep
    up, frames are dropped (same behaviour as the recording path).
    """

    def __init__(
        self,
        config: dict,
        on_frame,
        max_queue: int = 5,
    ):
        """
        Args:
            config: Snapshot of effect settings (blur_regions, webcam, background, etc.).
            on_frame: Callback ``(frame_bgr: np.ndarray, timestamp: float) -> None``
                      invoked on the processing thread for each processed frame.
            max_queue: Maximum frames queued before dropping.
        """
        self._on_frame = on_frame
        self._queue: queue.Queue[tuple[np.ndarray, float, np.ndarray | None] | None] = queue.Queue(maxsize=max_queue)
        self._config = config
        self._config_lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True, name="effects-processor")
        self._running = False

    # -- public API --

    def start(self) -> None:
        """Start the processing thread."""
        self._running = True
        self._thread.start()

    def stop(self) -> None:
        """Signal the thread to stop and wait for it to finish."""
        self._running = False
        # Push sentinel to unblock the thread if it's waiting on get()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def push(self, frame_bgr: np.ndarray, timestamp: float,
             webcam_bgr: np.ndarray | None = None) -> bool:
        """Queue a frame for processing.  Returns False if the queue is full (frame dropped)."""
        try:
            self._queue.put_nowait((frame_bgr, timestamp, webcam_bgr))
            return True
        except queue.Full:
            return False

    def update_config(self, config: dict) -> None:
        """Atomically swap the effects configuration.

        Changes take effect starting with the next frame.
        """
        with self._config_lock:
            self._config = config

    # -- internal --

    def _get_config(self) -> dict:
        with self._config_lock:
            return self._config

    def _run(self) -> None:
        if cv2 is not None:
            cv2.setNumThreads(1)

        while self._running:
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break

            frame_bgr, timestamp, webcam_bgr = item
            try:
                processed = self._process(frame_bgr, webcam_bgr)
                self._on_frame(processed, timestamp)
            except Exception:
                log.exception("Frame processing failed at t=%.3f", timestamp)

    def _process(self, frame_bgr: np.ndarray,
                 webcam_bgr: np.ndarray | None) -> np.ndarray:
        cfg = self._get_config()

        background = cfg.get("background")
        target_res = cfg.get("target_res")  # (w, h) or None
        blur_regions = cfg.get("blur_regions")
        scaling = cfg.get("scaling", "cubic")

        # Background compositing (also handles resize to target)
        compose_bg = background is not None and target_res is not None
        if compose_bg:
            tw, th = target_res
            frame_bgr = compose_on_background(
                frame_bgr, background, tw, th, scaling=scaling,
            )

        # Blur regions are handled by FFmpeg's filter chain in the segment
        # encoder — applying Gaussian blur per-frame in Python/OpenCV is too
        # expensive (~45ms at 1080p single-threaded, or 80% CPU multi-threaded).

        # Webcam overlay
        if webcam_bgr is not None:
            frame_bgr = composite_webcam(
                frame_bgr, webcam_bgr,
                position_x=cfg.get("webcam_position_x", 0.88),
                position_y=cfg.get("webcam_position_y", 0.85),
                crop=cfg.get("webcam_crop"),
                chroma=cfg.get("webcam_chroma"),
                scale=cfg.get("webcam_scale", 0.2),
                scaling=scaling,
            )

        # Resize to target resolution if compositing didn't already handle it
        if target_res and not compose_bg:
            tw, th = target_res
            fh, fw = frame_bgr.shape[:2]
            if fw != tw or fh != th:
                frame_bgr = cv2.resize(
                    frame_bgr, (tw, th),
                    interpolation=get_interpolation(scaling),
                )

        return frame_bgr
