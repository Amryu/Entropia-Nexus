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
    A single instance is shared via ``_active_instance`` — the preview dialog
    and clip writer both read from the same capture thread.
    """

    # Class-level device discovery cache shared across all instances.
    _device_cache: list[dict] | None = None
    _discovery_lock = threading.Lock()
    _discovery_event = threading.Event()
    _discovery_in_progress = False

    # Active background capture instance (set by CaptureManager).
    _active_instance: "WebcamCapture | None" = None

    @classmethod
    def discover_devices_async(cls) -> None:
        """Start background device discovery if not already done or in progress."""
        with cls._discovery_lock:
            if cls._device_cache is not None or cls._discovery_in_progress:
                return
            cls._discovery_in_progress = True
            cls._discovery_event.clear()
        threading.Thread(
            target=cls._run_discovery, daemon=True, name="wcam-discover",
        ).start()

    @classmethod
    def _run_discovery(cls) -> None:
        try:
            devices = cls.list_devices()
        except Exception:
            devices = []
        with cls._discovery_lock:
            cls._device_cache = devices
            cls._discovery_in_progress = False
        cls._discovery_event.set()
        log.info("Webcam device discovery complete: %d device(s)", len(devices))

    @classmethod
    def get_cached_devices(cls, timeout: float = 0) -> list[dict] | None:
        """Return cached device list, optionally waiting for in-progress discovery.

        Args:
            timeout: Seconds to wait for in-progress discovery. 0 = no wait.

        Returns:
            Cached device list, or None if not yet available.
        """
        if cls._device_cache is not None:
            return cls._device_cache
        if timeout > 0 and cls._discovery_in_progress:
            cls._discovery_event.wait(timeout)
            return cls._device_cache
        return None

    @classmethod
    def set_cached_devices(cls, devices: list[dict] | None) -> None:
        """Manually set the device cache (e.g. after a manual probe)."""
        with cls._discovery_lock:
            cls._device_cache = devices
            cls._discovery_in_progress = False
        cls._discovery_event.set()

    @classmethod
    def invalidate_cache(cls) -> None:
        """Clear the device cache and reset discovery state."""
        with cls._discovery_lock:
            cls._device_cache = None
            cls._discovery_in_progress = False
        cls._discovery_event.clear()

    def __init__(self, device: int = 0, fps: int = 30):
        if cv2 is None:
            raise ImportError("OpenCV is required for webcam capture")
        self._device = device
        self._fps = max(1, min(60, fps))
        self._latest_frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._stop_event = threading.Event()
        self._settings_requested = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the capture thread (camera opened in the background thread)."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="webcam-capture",
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the capture thread to stop and wait for it to exit.

        The background thread releases the camera before returning.
        Blocks for at most 5 seconds (camera release is usually instant).
        """
        self._running = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None

    def get_latest_frame(self) -> np.ndarray | None:
        """Return the most recent webcam frame (BGR), or None."""
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def request_settings_dialog(self) -> bool:
        """Request the native settings dialog from the capture thread.

        Returns True if the request was queued (capture is running).
        The dialog opens on the capture thread's next iteration, avoiding
        the cost of opening a new VideoCapture.
        """
        if not self._running:
            return False
        self._settings_requested = True
        return True

    # Backend preference: MSMF is faster on Windows but some cameras only
    # work with DirectShow.  Try MSMF first; fall back to DSHOW if read()
    # consistently fails.
    _BACKENDS = (
        (cv2.CAP_MSMF, "MSMF"),
        (cv2.CAP_DSHOW, "DSHOW"),
    ) if hasattr(cv2, "CAP_MSMF") else ()

    _MAX_CONSECUTIVE_FAILURES = 10  # switch backend after this many read() failures
    _STABILITY_READS = 5  # test reads before accepting a backend

    def _open_camera(
        self, exclude: set[int] | None = None,
    ) -> "tuple[cv2.VideoCapture, str, int] | tuple[None, None, None]":
        """Try each backend until the camera opens and can deliver frames.

        Args:
            exclude: Backend IDs to skip (ones that failed during the session).

        Returns:
            (VideoCapture, backend_name, backend_id) or (None, None, None).
        """
        import sys
        import time
        backends = self._BACKENDS if sys.platform == "win32" else ((cv2.CAP_ANY, "ANY"),)
        if exclude is None:
            exclude = set()
        for backend, name in backends:
            if backend in exclude:
                continue
            try:
                cap = cv2.VideoCapture(self._device, backend)
            except Exception:
                continue
            if not cap.isOpened():
                cap.release()
                continue
            # Some backends (MSMF) can deliver the first frame but then fail
            # on subsequent reads.  Do several test reads to verify stability.
            ok = True
            for _ in range(self._STABILITY_READS):
                ret, _ = cap.read()
                if not ret:
                    ok = False
                    break
                time.sleep(0.02)  # brief pause between test reads
            if ok:
                log.info(
                    "Webcam opened (device=%d, backend=%s, fps=%d)",
                    self._device, name, self._fps,
                )
                return cap, name, backend
            cap.release()
            log.debug(
                "Backend %s opened device %d but failed stability check, trying next",
                name, self._device,
            )
        return None, None, None

    def _capture_loop(self) -> None:
        """Open camera and continuously read frames."""
        import time

        failed_backends: set[int] = set()
        cap, backend_name, backend_id = self._open_camera()
        if cap is None:
            log.warning("Cannot open webcam device %d with any backend", self._device)
            self._running = False
            return

        try:
            interval = 1.0 / self._fps
            fail_count = 0
            while self._running:
                # Check for settings dialog request
                if self._settings_requested:
                    self._settings_requested = False
                    try:
                        cap.set(cv2.CAP_PROP_SETTINGS, 1)
                    except Exception as e:
                        log.warning("Failed to open settings from capture thread: %s", e)
                tick = time.monotonic()
                ret, frame = cap.read()
                if ret and frame is not None:
                    fail_count = 0
                    with self._lock:
                        self._latest_frame = frame
                else:
                    fail_count += 1
                    if fail_count >= self._MAX_CONSECUTIVE_FAILURES:
                        # Current backend stopped delivering — try switching
                        log.warning(
                            "Webcam backend %s: %d consecutive read failures, "
                            "attempting backend switch",
                            backend_name, fail_count,
                        )
                        cap.release()
                        failed_backends.add(backend_id)
                        cap, backend_name, backend_id = self._open_camera(
                            exclude=failed_backends,
                        )
                        if cap is None:
                            log.warning("No working backend found, stopping webcam")
                            break
                        fail_count = 0
                    else:
                        time.sleep(0.5)
                    continue
                elapsed = time.monotonic() - tick
                if elapsed < interval:
                    # Sleep interruptibly so stop() doesn't have to wait
                    self._stop_event.wait(timeout=interval - elapsed)
        finally:
            if cap is not None:
                cap.release()
            log.info("Webcam capture stopped (device=%d)", self._device)

    @staticmethod
    def list_devices(max_test: int = 3) -> list[dict]:
        """Probe for available webcam devices (blocking).

        Tests device indices 0..max_test-1 and returns those that open.
        Stops early after 2 consecutive failures (devices are usually contiguous).
        Uses MSMF backend on Windows for faster probing than default multi-backend.
        Redirects stderr to suppress OpenCV's C++ warnings for missing indices.
        """
        if cv2 is None:
            return []
        import os
        import sys
        # Redirect stderr at the OS level to suppress OpenCV C++ warnings.
        # Python's sys.stderr is separate from fd 2; OpenCV writes to fd 2.
        devnull_fd = -1
        saved_fd = -1
        try:
            if sys.platform == "win32":
                devnull_fd = os.open("NUL", os.O_WRONLY)
            else:
                devnull_fd = os.open(os.devnull, os.O_WRONLY)
            saved_fd = os.dup(2)
            os.dup2(devnull_fd, 2)
        except OSError:
            saved_fd = -1

        # Use MSMF on Windows — much faster than default multi-backend probe
        backend = cv2.CAP_MSMF if sys.platform == "win32" else cv2.CAP_ANY
        devices = []
        consecutive_failures = 0
        try:
            for i in range(max_test):
                try:
                    cap = cv2.VideoCapture(i, backend)
                except Exception:
                    consecutive_failures += 1
                    if consecutive_failures >= 2:
                        break
                    continue
                if cap.isOpened():
                    consecutive_failures = 0
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    label = f"Camera {i} ({w}\u00d7{h})"
                    devices.append({
                        "index": i,
                        "width": w,
                        "height": h,
                        "label": label,
                    })
                    cap.release()
                else:
                    cap.release()
                    consecutive_failures += 1
                    if consecutive_failures >= 2:
                        break
        finally:
            try:
                if saved_fd >= 0:
                    os.dup2(saved_fd, 2)
                    os.close(saved_fd)
                if devnull_fd >= 0:
                    os.close(devnull_fd)
            except OSError:
                pass
        return devices

    @staticmethod
    def open_settings_dialog(device: int = 0) -> None:
        """Open the native webcam properties dialog (Windows only, blocking).

        Tries MSMF first (matches discovery backend), then DirectShow.
        CAP_PROP_SETTINGS opens the native camera properties sheet.
        The dialog is modal and blocks until the user closes it.
        """
        if cv2 is None:
            return
        import sys
        if sys.platform != "win32":
            log.warning("Native webcam settings dialog is only available on Windows")
            return
        # Try backends in order: MSMF (fast, matches list_devices), then DSHOW
        for backend, name in ((cv2.CAP_MSMF, "MSMF"), (cv2.CAP_DSHOW, "DSHOW")):
            try:
                cap = cv2.VideoCapture(device, backend)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_SETTINGS, 1)
                    cap.release()
                    return
                cap.release()
            except Exception:
                pass
        log.warning("Cannot open webcam device %d for settings dialog", device)
