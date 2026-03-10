"""Push-based frame distribution for OCR detectors.

A single capture thread pushes frames to subscribed detectors.  Each
subscriber declares its desired rate in Hz; the distributor dynamically
sets its base capture rate to match the fastest subscriber and computes
divisors for the rest.  This replaces the pull-based SharedFrameCache,
eliminating redundant captures and ensuring maximum frame freshness.

Backward-compatible pull API (get_frame / get_frame_gray) is provided for
detectors that keep their own thread (e.g. the orchestrator).
"""

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from .capturer import ScreenCapturer
from ..core.constants import GAME_TITLE_PREFIX
from ..core.logger import get_logger
from ..platform import backend as _platform

log = get_logger("FrameDistributor")

# Default base capture rate when no subscribers are registered.
DEFAULT_BASE_HZ = 4.0

# When the game window is not found or not foreground, poll at this slower
# rate to avoid wasting CPU on window discovery / foreground checks.
IDLE_INTERVAL_S = 1.0


@dataclass
class FrameSubscription:
    """Describes a detector's frame delivery preferences."""

    callback: Callable[[np.ndarray, float], None]
    hz: float = 1.0
    divisor: int = 1  # auto-computed by FrameDistributor
    name: str = ""
    enabled: bool = True


class FrameDistributor:
    """Single-threaded capture with push-based frame distribution.

    Replaces SharedFrameCache.  A single ScreenCapturer captures the game
    window and distributes frames to subscribed detectors.  The capture
    rate is set dynamically to match the fastest subscriber; slower
    subscribers receive frames via computed divisors.

    Subscribers receive ``(frame_bgr, timestamp)`` in their callback,
    executed synchronously on the capture thread.  Heavy processing should
    be offloaded to a worker thread (see MobNameDetector pattern).

    For detectors that keep their own thread (orchestrator), the pull API
    ``get_latest_frame()`` / ``get_frame()`` / ``get_frame_gray()`` is
    available.

    **Boost mode**: When video buffering or a live preview is active, call
    ``boost()`` to override the base Hz, disable foreground gating, and
    force WGC backend.  Call ``unboost()`` to revert.  Boost callers are
    reference-counted so multiple boosts / unboosts nest correctly.
    """

    def __init__(self, capture_backend: str | None = None):
        self._capturer = ScreenCapturer(capture_backend=capture_backend)
        self._subscriptions: list[FrameSubscription] = []
        self._tick_count = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Dynamic base rate (recomputed when subscriptions change)
        self._base_hz: float = DEFAULT_BASE_HZ
        self._base_interval: float = 1.0 / DEFAULT_BASE_HZ

        # Boost mode: {caller_id: min_hz}
        self._boosts: dict[str, float] = {}
        self._boost_backends: dict[str, str] = {}  # {caller_id: backend}
        self._pre_boost_backend: Optional[str] = None

        # Game window state (updated by capture loop)
        self._game_hwnd: Optional[int] = None
        self._game_geometry: Optional[tuple[int, int, int, int]] = None

        # Latest frame cache (for pull API)
        self._frame: Optional[np.ndarray] = None
        self._gray: Optional[np.ndarray] = None
        self._frame_time: float = 0.0
        self._frame_lock = threading.Lock()

        # HDR compatibility mode: CLAHE on L-channel (LAB)
        self._hdr_mode = False
        self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)) if cv2 else None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def game_hwnd(self) -> Optional[int]:
        """The HWND of the game window, or None if not found."""
        return self._game_hwnd

    @property
    def game_geometry(self) -> Optional[tuple[int, int, int, int]]:
        """Client-area geometry ``(x, y, w, h)`` in screen coords."""
        return self._game_geometry

    @property
    def game_origin(self) -> tuple[int, int]:
        """Screen ``(x, y)`` of the game window's top-left corner."""
        geo = self._game_geometry
        return (geo[0], geo[1]) if geo else (0, 0)

    @property
    def active_window_backend(self) -> str:
        """Name of the active window-capture backend."""
        return self._capturer.active_window_backend

    @property
    def capturer(self) -> ScreenCapturer:
        """Direct access to the underlying capturer.

        Used by the orchestrator during its detection phase, which needs
        to capture on-demand outside the distributor's tick cycle.
        """
        return self._capturer

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def subscribe(
        self,
        name: str,
        callback: Callable[[np.ndarray, float], None],
        hz: float = 1.0,
    ) -> FrameSubscription:
        """Register a detector to receive frames.

        Args:
            name: Human-readable name for logging.
            callback: ``(frame_bgr, timestamp)`` called on the capture thread.
            hz: Desired delivery rate in Hz.  The distributor's base rate
                adapts to the fastest subscriber; slower ones get a divisor.

        Returns:
            The subscription object.  Set ``sub.enabled = False`` to pause.
        """
        sub = FrameSubscription(
            callback=callback, hz=max(0.1, hz), name=name,
        )
        self._subscriptions.append(sub)
        self._recompute_timing()
        log.info("Subscribed '%s' (%.1f Hz, divisor=%d, base=%.1f Hz)",
                 name, sub.hz, sub.divisor, self._base_hz)
        return sub

    def unsubscribe(self, subscription: FrameSubscription) -> None:
        """Remove a subscription."""
        try:
            self._subscriptions.remove(subscription)
            self._recompute_timing()
            log.info("Unsubscribed '%s'", subscription.name)
        except ValueError:
            pass

    def _recompute_timing(self):
        """Recompute base rate and divisors from current subscriptions.

        The base rate equals the fastest subscriber's Hz (or the highest
        boost Hz, whichever is greater).  Each subscriber's divisor is
        ``round(base_hz / sub.hz)``, clamped to >= 1.
        """
        sub_max = max((sub.hz for sub in self._subscriptions), default=DEFAULT_BASE_HZ)
        boost_max = max(self._boosts.values(), default=0.0)
        self._base_hz = max(sub_max, boost_max)

        self._base_interval = 1.0 / self._base_hz

        for sub in self._subscriptions:
            sub.divisor = max(1, round(self._base_hz / sub.hz))

        # When boosted (clips active), keep WGC alive with throttle.
        # When not boosted (OCR-only), suspend WGC to save GPU and use BitBlt.
        self._capturer.set_wgc_throttle(self._base_interval, boosted=self.boosted)

    # ------------------------------------------------------------------
    # Boost mode (video buffering / live preview)
    # ------------------------------------------------------------------

    @property
    def boosted(self) -> bool:
        """True if at least one boost caller is active."""
        return bool(self._boosts)

    def boost(
        self,
        caller_id: str,
        min_hz: float,
        capture_backend: str | None = None,
    ) -> None:
        """Activate boost mode: raise FPS, disable foreground gate.

        Multiple callers can boost simultaneously (reference-counted by id).
        The effective boost Hz is the max across all active callers.

        Args:
            caller_id: Unique identifier (e.g. ``"capture_manager"``).
            min_hz: Minimum capture rate while boosted.
            capture_backend: If set, switch to this backend while boosted
                (reverts to the OCR backend when the last booster leaves).
        """
        first_boost = not self._boosts
        self._boosts[caller_id] = float(min_hz)
        if capture_backend:
            self._boost_backends[caller_id] = capture_backend
        self._recompute_timing()

        # Save the pre-boost backend once so we can restore it later
        if first_boost:
            self._pre_boost_backend = self._capturer.active_window_backend

        # Switch backend only when explicitly requested and different
        if capture_backend and self._capturer.active_window_backend != capture_backend:
            self._capturer.set_capture_backend(capture_backend)
            log.info("Boost: switched backend to %s",
                     self._capturer.active_window_backend)

        log.info("Boost activated by '%s' (%.0f Hz, base=%.1f Hz, boosters=%d)",
                 caller_id, min_hz, self._base_hz, len(self._boosts))

    def unboost(self, caller_id: str) -> None:
        """Deactivate boost mode for a caller.

        When the last booster unboosts, foreground gating is restored and
        the backend reverts to its pre-boost setting.  When other boosters
        remain, their requested backend takes precedence.
        """
        self._boosts.pop(caller_id, None)
        self._boost_backends.pop(caller_id, None)
        self._recompute_timing()

        if not self._boosts and self._pre_boost_backend is not None:
            if self._capturer.active_window_backend != self._pre_boost_backend:
                self._capturer.set_capture_backend(self._pre_boost_backend)
                log.info("Boost: reverted backend to %s",
                         self._capturer.active_window_backend)
            self._pre_boost_backend = None
        elif self._boost_backends:
            # Other boosters remain — switch to the last remaining backend
            remaining_backend = list(self._boost_backends.values())[-1]
            if self._capturer.active_window_backend != remaining_backend:
                self._capturer.set_capture_backend(remaining_backend)
                log.info("Boost: switched backend to %s (after '%s' left)",
                         self._capturer.active_window_backend, caller_id)

        log.info("Boost deactivated by '%s' (base=%.1f Hz, boosters=%d)",
                 caller_id, self._base_hz, len(self._boosts))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the capture thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="frame-distributor",
        )
        self._thread.start()
        log.info("Started (%.1f Hz base rate)", self._base_hz)

    def stop(self):
        """Stop the capture thread and wait for it to finish."""
        self._running = False
        self._boosts.clear()
        self._boost_backends.clear()
        self._pre_boost_backend = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self._capturer.stop()
        log.info("Stopped")

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_capture_backend(self, capture_backend: str | None) -> None:
        """Update capture backend at runtime and clear cached frames.

        If boost mode is active, the request is stored as the pre-boost
        backend and applied when the last booster unboosts.
        """
        if self._boosts:
            # Don't change the actual backend while boosted; remember for later
            self._pre_boost_backend = capture_backend or "auto"
        else:
            with self._frame_lock:
                self._capturer.set_capture_backend(capture_backend)
                self._frame = None
                self._gray = None
                self._frame_time = 0.0

    def set_hdr_mode(self, enabled: bool) -> None:
        """Enable or disable HDR compatibility tone correction."""
        self._hdr_mode = enabled
        log.info("HDR compatibility mode %s", "enabled" if enabled else "disabled")

    def _apply_hdr_correction(self, frame: np.ndarray) -> np.ndarray:
        """Apply CLAHE on the L-channel of LAB to restore contrast."""
        if self._clahe is None:
            return frame
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self._clahe.apply(l)
        return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    # ------------------------------------------------------------------
    # Pull API (backward-compatible with SharedFrameCache)
    # ------------------------------------------------------------------

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Return the most recent captured frame regardless of age.

        Intended for the orchestrator, which runs its own timed loop and
        just wants whatever frame the distributor last captured.
        """
        with self._frame_lock:
            return self._frame

    def get_frame(
        self,
        hwnd: int,
        max_age_ms: float = 40,
        geometry: Optional[tuple[int, int, int, int]] = None,
    ) -> Optional[np.ndarray]:
        """Return cached frame if fresher than *max_age_ms*, else None.

        Signature matches ``SharedFrameCache.get_frame()`` for backward
        compatibility.  The *hwnd* and *geometry* arguments are ignored
        because the distributor manages its own window discovery.
        """
        now = time.monotonic()
        with self._frame_lock:
            if (self._frame is not None
                    and (now - self._frame_time) * 1000 < max_age_ms):
                return self._frame
        return None

    def get_frame_gray(
        self,
        hwnd: int,
        max_age_ms: float = 40,
        geometry: Optional[tuple[int, int, int, int]] = None,
    ) -> Optional[np.ndarray]:
        """Return cached grayscale frame (avoids repeated cvtColor).

        Signature matches ``SharedFrameCache.get_frame_gray()``.
        """
        if cv2 is None:
            return None
        frame = self.get_frame(hwnd, max_age_ms, geometry)
        if frame is None:
            return None
        with self._frame_lock:
            if self._gray is None:
                self._gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return self._gray

    def invalidate(self):
        """Clear the frame cache (e.g. when the game window handle changes)."""
        with self._frame_lock:
            self._frame = None
            self._gray = None
            self._frame_time = 0.0

    # ------------------------------------------------------------------
    # Capture loop
    # ------------------------------------------------------------------

    def _capture_loop(self):
        while self._running:
            tick_start = time.monotonic()

            # Discover game window if needed
            if not self._game_hwnd or not _platform.is_window_visible(self._game_hwnd):
                self._game_hwnd = None
                self._game_geometry = None
                hwnd = _platform.find_window_by_title_prefix(GAME_TITLE_PREFIX)
                if hwnd:
                    geo = _platform.get_window_geometry(hwnd)
                    self._game_hwnd = hwnd
                    self._game_geometry = geo
                    log.info("Game window found: hwnd=%s geometry=%s", hwnd, geo)
                else:
                    self._sleep_remainder(tick_start, IDLE_INTERVAL_S)
                    continue

            # Foreground gating: skip capture when game is not active.
            # Disabled when boosted (video recording needs frames regardless).
            if not self._boosts:
                try:
                    if _platform.get_foreground_window_id() != self._game_hwnd:
                        self._sleep_remainder(tick_start, IDLE_INTERVAL_S)
                        continue
                except Exception:
                    pass

            # Refresh geometry periodically (every ~1s worth of ticks)
            if self._tick_count % max(1, int(self._base_hz)) == 0:
                self._game_geometry = _platform.get_window_geometry(self._game_hwnd)

            # Capture
            frame = self._capturer.capture_window(
                self._game_hwnd, geometry=self._game_geometry,
            )
            if frame is None:
                self._sleep_remainder(tick_start, self._base_interval)
                continue

            if self._hdr_mode:
                frame = self._apply_hdr_correction(frame)

            now = time.monotonic()
            with self._frame_lock:
                self._frame = frame
                self._gray = None
                self._frame_time = now

            # Distribute to subscribers.
            # Tick 0 goes to everyone (0 % N == 0 for all N).
            self._distribute(frame, now)
            self._tick_count += 1

            self._sleep_remainder(tick_start, self._base_interval)

    def _distribute(self, frame: np.ndarray, timestamp: float):
        """Push frame to all eligible subscribers."""
        for sub in self._subscriptions:
            if not sub.enabled:
                continue
            if self._tick_count % sub.divisor != 0:
                continue
            try:
                sub.callback(frame, timestamp)
            except Exception:
                log.error("Subscriber '%s' raised an exception", sub.name,
                          exc_info=True)

    @staticmethod
    def _sleep_remainder(tick_start: float, interval: float):
        """Sleep for the remainder of the tick interval."""
        elapsed = time.monotonic() - tick_start
        remaining = interval - elapsed
        if remaining > 0:
            time.sleep(remaining)
