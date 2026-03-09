"""Main thread freeze detector.

A lightweight watchdog that logs when the Qt event loop is blocked
for more than FREEZE_THRESHOLD seconds.  Captures the main thread's
stack trace during the freeze for diagnostic purposes.
"""

import sys
import threading
import time
import traceback

from PyQt6.QtCore import QTimer

from .logger import get_logger

log = get_logger("FreezeDetector")

FREEZE_THRESHOLD = 0.5  # seconds
HEARTBEAT_INTERVAL_MS = 200
CHECK_INTERVAL = 0.2  # seconds


class FreezeDetector:
    def __init__(self):
        self._last_heartbeat: float = time.monotonic()
        self._main_thread_id: int | None = threading.main_thread().ident
        self._timer: QTimer | None = None
        self._watchdog: threading.Thread | None = None
        self._running = False
        self._suppressed = True  # suppress during startup
        self._in_freeze = False
        self._freeze_start: float = 0.0

    def arm(self) -> None:
        """Enable freeze reporting (call after startup is complete)."""
        self._suppressed = False
        self._last_heartbeat = time.monotonic()

    def start(self) -> None:
        """Start heartbeat timer (main thread) and watchdog (background)."""
        self._running = True
        self._last_heartbeat = time.monotonic()

        self._timer = QTimer()
        self._timer.timeout.connect(self._heartbeat)
        self._timer.start(HEARTBEAT_INTERVAL_MS)

        self._watchdog = threading.Thread(
            target=self._watch, name="FreezeDetector", daemon=True,
        )
        self._watchdog.start()

    def stop(self) -> None:
        """Stop the detector. Safe to call from any thread."""
        self._running = False
        # QTimers can only be stopped from the thread that created them.
        # Setting _running = False is enough to stop the watchdog loop;
        # only touch the QTimer when called from the main thread.
        if self._timer is not None and threading.current_thread() is threading.main_thread():
            self._timer.stop()
            self._timer = None

    def _heartbeat(self) -> None:
        """Called by QTimer on the main thread."""
        self._last_heartbeat = time.monotonic()

    def _watch(self) -> None:
        """Background thread: checks heartbeat staleness."""
        while self._running:
            time.sleep(CHECK_INTERVAL)
            if not self._running:
                break

            if self._suppressed:
                continue

            elapsed = time.monotonic() - self._last_heartbeat

            if elapsed >= FREEZE_THRESHOLD:
                if not self._in_freeze:
                    self._in_freeze = True
                    self._freeze_start = time.monotonic()
                    stack = self._capture_main_stack()
                    log.warning(
                        "Main thread frozen for %.1fs\n%s",
                        elapsed, stack,
                    )
            elif self._in_freeze:
                total = time.monotonic() - self._freeze_start
                log.warning(
                    "Main thread freeze ended (total: %.1fs)", total,
                )
                self._in_freeze = False

    def _capture_main_stack(self) -> str:
        """Get the current stack trace of the main thread."""
        frames = sys._current_frames()
        frame = frames.get(self._main_thread_id)
        if frame is None:
            return "  (main thread frame not available)"
        return "".join(traceback.format_stack(frame)).rstrip()
