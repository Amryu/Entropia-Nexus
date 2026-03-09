"""Webcam capture thread using OpenCV VideoCapture."""

import threading

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.logger import get_logger

log = get_logger("WebcamCapture")


class WebcamCapture:
    """Captures frames from a webcam device in a background thread.

    Only the latest frame is kept (single-frame buffer for overlay compositing).
    """

    def __init__(self, device: int = 0):
        if cv2 is None:
            raise ImportError("OpenCV is required for webcam capture")
        self._device = device
        self._cap = None
        self._latest_frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Open the webcam and start the capture thread."""
        if self._running:
            return
        self._cap = cv2.VideoCapture(self._device)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open webcam device {self._device}")
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="webcam-capture",
        )
        self._thread.start()
        log.info("Webcam capture started (device=%d)", self._device)

    def stop(self) -> None:
        """Stop the capture thread and release the webcam."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        if self._cap:
            self._cap.release()
            self._cap = None
        log.info("Webcam capture stopped")

    def get_latest_frame(self) -> np.ndarray | None:
        """Return the most recent webcam frame (BGR), or None."""
        with self._lock:
            return self._latest_frame

    def _capture_loop(self) -> None:
        """Continuously read frames from the webcam at ~15fps."""
        import time
        interval = 1.0 / 15  # Webcam overlay doesn't need high FPS
        while self._running:
            tick = time.monotonic()
            ret, frame = self._cap.read()
            if ret and frame is not None:
                with self._lock:
                    self._latest_frame = frame
            else:
                # Camera may have been disconnected
                time.sleep(0.5)
                continue
            elapsed = time.monotonic() - tick
            if elapsed < interval:
                time.sleep(interval - elapsed)

    @staticmethod
    def list_devices(max_test: int = 5) -> list[dict]:
        """Probe for available webcam devices (blocking, slow).

        Tests device indices 0..max_test-1 and returns those that open.
        """
        if cv2 is None:
            return []
        devices = []
        for i in range(max_test):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                devices.append({"index": i, "width": w, "height": h})
                cap.release()
        return devices
