"""Target lock icon detection with configurable ROI reading.

Finds the game's target lock icon on screen using template matching,
then reads configurable regions relative to it (HP bar, shared icon, name).

Detection uses a three-tier strategy for performance:
1. Cheap pixel check — if the region at the last position hasn't changed, reuse it
2. Limited area search — template match in a ±SEARCH_MARGIN region around last position
3. Full game window search — template match across the entire game screenshot

Supports two modes:
- **Push mode** (FrameDistributor): subscribes with divisor=5 (2 Hz),
  receives frames via callback on the distributor's capture thread.
- **Legacy poll mode** (SharedFrameCache / ScreenCapturer): runs its own
  thread with sleep-based polling.
"""

import os
import threading
import time

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.constants import (
    EVENT_TARGET_LOCK_UPDATE, EVENT_TARGET_LOCK_LOST,
    EVENT_MOB_TARGET_CHANGED,
    EVENT_PLAYER_STATUS_UPDATE, EVENT_PLAYER_STATUS_LOST,
    GAME_TITLE_PREFIX,
)
from ..core.logger import get_logger
from ..platform import backend as _platform

log = get_logger("TargetLock")

# --- Timing ---
POLL_INTERVAL = 0.5  # seconds (~2 Hz) — legacy poll mode
DISTRIBUTOR_HZ = 2   # 2 Hz delivery rate

# --- Search ---
LOST_TICKS = 3       # consecutive misses before publishing lost event

# --- Foreground gating ---
BACKGROUND_SLEEP = 1.0  # seconds to sleep when game is not visible

# --- Match validation ---
MIN_INSIDE_BRIGHTNESS = 200  # pixels under mask must be very bright (white icon)
MIN_CONTRAST = 10            # brightness gap between inside and outside mask
                             # (lowered from 40 — bright scenery like sunlit trees
                             # reduces contrast; TM_CCOEFF_NORMED already rejects
                             # uniform bright areas via zero-variance scoring)

# --- HP bar HSV ranges (from mob_detector.py) ---
HP_RED_LOW1 = np.array([0, 80, 100])
HP_RED_HIGH1 = np.array([10, 255, 255])
HP_RED_LOW2 = np.array([170, 80, 100])
HP_RED_HIGH2 = np.array([180, 255, 255])
HP_GREEN_LOW = np.array([35, 80, 100])
HP_GREEN_HIGH = np.array([85, 255, 255])

# --- Shared icon brightness threshold ---
SHARED_BRIGHTNESS_THRESHOLD = 80


class TargetLockDetector:
    """Detects the target lock icon on the game screen and reads nearby ROIs.

    Uses alpha-masked template matching with a three-tier search strategy
    for fast, robust detection at ~2 Hz.
    """

    def __init__(self, config, event_bus, frame_source):
        self._config = config
        self._event_bus = event_bus

        # Detect frame source type
        self._distributor = None
        self._subscription = None
        self._frame_cache = None
        self._capturer = None

        from .frame_distributor import FrameDistributor
        if isinstance(frame_source, FrameDistributor):
            self._distributor = frame_source
        else:
            from .frame_cache import SharedFrameCache
            if isinstance(frame_source, SharedFrameCache):
                self._frame_cache = frame_source
            else:
                self._capturer = frame_source

        self._running = False
        self._thread = None
        self._tick_count = 0

        # Game window
        self._game_hwnd = None
        self._game_geometry: tuple[int, int, int, int] | None = None
        self._game_origin: tuple[int, int] = (0, 0)  # screen (x, y) of game client area

        # Template (loaded lazily)
        self._template_bgr = None
        self._template_gray = None   # Alpha channel as grayscale shape template
        self._template_mask = None
        self._template_mask_bool = None   # Boolean: True where opaque
        self._template_inv_bool = None    # Boolean: True where transparent
        self._template_h = 0
        self._template_w = 0

        # Tracking state
        self._last_pos: tuple[int, int] | None = None  # (x, y) in game-window coords
        self._last_region_pixels: np.ndarray | None = None  # small region for cheap check
        self._miss_count = 0
        self._published_lost = False

        # Idle mode tracking
        self._idle_ticks = 0  # consecutive ticks with no target found

        # Heart exclusion zone (set by player_status_detector)
        self._heart_exclusion: tuple[int, int, int, int] | None = None  # (x, y, w, h) screen-abs
        self._cb_heart_update = lambda d: self._on_heart_update(d)
        self._cb_heart_lost = lambda d: self._on_heart_lost()
        event_bus.subscribe(EVENT_PLAYER_STATUS_UPDATE, self._cb_heart_update)
        event_bus.subscribe(EVENT_PLAYER_STATUS_LOST, self._cb_heart_lost)

        # Mob name OCR state
        self._last_mob_name: str = ""
        self._name_candidate: str = ""
        self._name_confirm_count: int = 0
        self._name_debounce = getattr(config, 'target_lock_name_debounce', 2)
        self._name_min_confidence = getattr(config, 'target_lock_name_min_confidence', 0.3)

        self._load_template()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _load_template(self):
        if cv2 is None:
            log.warning("OpenCV not available — target lock detection disabled")
            return
        assets = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets"
        )
        path = os.path.join(assets, "target_lock.png")
        raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if raw is None:
            log.error("Failed to load template: %s", path)
            return
        if raw.shape[2] < 4:
            log.error("Template has no alpha channel: %s", path)
            return
        self._template_bgr = raw[:, :, :3]
        self._template_mask = raw[:, :, 3]
        self._template_h, self._template_w = raw.shape[:2]

        # Shape-based matching: use alpha as grayscale template.
        # TM_CCOEFF_NORMED subtracts the mean, so it matches the bright/dark
        # pattern (chevron shape) rather than absolute brightness — uniform
        # bright areas get score ≈ 0 because they have no variance.
        self._template_gray = self._template_mask.copy()
        self._template_mask_bool = self._template_mask > 0
        self._template_inv_bool = ~self._template_mask_bool
        opaque_px = int(self._template_mask_bool.sum())
        total_px = self._template_h * self._template_w
        log.info("Template loaded: %dx%d (%d/%d opaque)",
                 self._template_w, self._template_h, opaque_px, total_px)

    def set_game_hwnd(self, hwnd: int,
                      geometry: tuple[int, int, int, int] | None = None):
        """Set the game window handle and client-area geometry (x, y, w, h)."""
        self._game_hwnd = hwnd
        self._game_geometry = geometry
        if geometry:
            self._game_origin = (geometry[0], geometry[1])

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        if self._running or self._template_bgr is None:
            return
        self._running = True
        self._tick_count = 0

        if self._distributor is not None:
            self._subscription = self._distributor.subscribe(
                "target-lock", self._on_frame, hz=DISTRIBUTOR_HZ,
            )
            log.info("Started (push mode)")
        else:
            self._thread = threading.Thread(
                target=self._poll_loop, daemon=True, name="target-lock",
            )
            self._thread.start()
            log.info("Started (poll mode)")

    def stop(self):
        self._running = False
        if self._subscription is not None:
            self._subscription.enabled = False
            self._subscription = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self._event_bus.unsubscribe(EVENT_PLAYER_STATUS_UPDATE, self._cb_heart_update)
        self._event_bus.unsubscribe(EVENT_PLAYER_STATUS_LOST, self._cb_heart_lost)
        log.info("Stopped")

    # ------------------------------------------------------------------
    # Push mode (FrameDistributor callback)
    # ------------------------------------------------------------------

    def _on_frame(self, frame: np.ndarray, timestamp: float):
        """Callback from FrameDistributor — runs on the capture thread."""
        if not self._running:
            return
        if not getattr(self._config, "target_lock_enabled", True):
            return

        # Idle mode: skip most ticks when no target is found
        idle_threshold = getattr(self._config, "ocr_idle_threshold", 50)
        idle_mult = getattr(self._config, "ocr_idle_multiplier", 5)
        if self._idle_ticks >= idle_threshold and self._tick_count % idle_mult != 0:
            self._tick_count += 1
            return

        try:
            self._game_origin = self._distributor.game_origin
            self._process_image(frame)
        except Exception as e:
            log.error("Tick error: %s", e)
        self._tick_count += 1

    # ------------------------------------------------------------------
    # Legacy poll mode
    # ------------------------------------------------------------------

    def _capture_window(self, hwnd):
        """Capture via shared frame cache or legacy capturer."""
        if self._frame_cache is not None:
            return self._frame_cache.get_frame(hwnd, geometry=self._game_geometry)
        return self._capturer.capture_window(hwnd, geometry=self._game_geometry)

    def _poll_loop(self):
        while self._running:
            try:
                if getattr(self._config, "target_lock_enabled", True):
                    self._tick_legacy()
            except Exception as e:
                log.error("Tick error: %s", e)
            self._tick_count += 1
            # Idle mode: multiply poll interval when no target found
            idle_threshold = getattr(self._config, "ocr_idle_threshold", 50)
            idle_mult = getattr(self._config, "ocr_idle_multiplier", 5)
            if self._idle_ticks >= idle_threshold:
                time.sleep(POLL_INTERVAL * idle_mult)
            else:
                time.sleep(POLL_INTERVAL)

    def _tick_legacy(self):
        """Legacy poll tick: discover window, capture, then process."""
        # Auto-discover game window (or re-discover if capture fails)
        if not self._game_hwnd or not _platform.is_window_visible(self._game_hwnd):
            self._game_hwnd = None
            hwnd = _platform.find_window_by_title_prefix(GAME_TITLE_PREFIX)
            if hwnd:
                geo = _platform.get_window_geometry(hwnd)
                self.set_game_hwnd(hwnd, geo)
            else:
                return

        # Foreground gating: skip capture when game is not the active window
        try:
            if _platform.get_foreground_window_id() != self._game_hwnd:
                time.sleep(BACKGROUND_SLEEP)
                return
        except Exception:
            pass

        image = self._capture_window(self._game_hwnd)
        if image is None:
            return

        self._process_image(image)

    # ------------------------------------------------------------------
    # Core image processing (shared by both modes)
    # ------------------------------------------------------------------

    def _process_image(self, image: np.ndarray):
        """Process a captured game frame: template match + ROI reads."""
        threshold = getattr(self._config, "target_lock_match_threshold", 0.85)
        pos, confidence = self._find_template(image, threshold)

        # Reject matches that fall within the player heart exclusion zone
        if pos is not None and self._heart_exclusion is not None:
            gx, gy = self._game_origin
            abs_x, abs_y = gx + pos[0], gy + pos[1]
            hx, hy, hw, hh = self._heart_exclusion
            margin = 10
            if (hx - margin <= abs_x <= hx + hw + margin
                    and hy - margin <= abs_y <= hy + hh + margin):
                pos = None
                confidence = 0.0

        if pos is not None:
            prev_lost = self._published_lost
            self._last_pos = pos
            self._miss_count = 0
            self._published_lost = False
            self._idle_ticks = 0  # target found — reset idle

            # Log template position on first detection or re-acquisition
            x, y = pos
            if prev_lost or self._tick_count <= 1:
                ih, iw = image.shape[:2]
                log.info("Target lock found at (%d,%d) in %dx%d image, template=%dx%d",
                         x, y, iw, ih, self._template_w, self._template_h)

            # Cache pixels at this position for cheap check next tick
            self._last_region_pixels = self._extract_region(
                image, x, y, self._template_w, self._template_h
            )

            # Read ROIs and publish
            data = self._read_rois(image, x, y)
            gx, gy = self._game_origin
            data.update({
                "x": gx + x, "y": gy + y,
                "w": self._template_w, "h": self._template_h,
                "confidence": confidence,
                "game_origin": self._game_origin,
            })
            self._event_bus.publish(EVENT_TARGET_LOCK_UPDATE, data)

            # Check for mob name change (debounced)
            self._check_name_change(data.get("raw_name", ""))
        else:
            self._miss_count += 1
            self._idle_ticks += 1  # no target — increment idle counter
            if self._miss_count >= LOST_TICKS and not self._published_lost:
                self._published_lost = True
                self._last_pos = None
                self._last_region_pixels = None
                self._event_bus.publish(EVENT_TARGET_LOCK_LOST, {})

    # ------------------------------------------------------------------
    # Three-tier template search
    # ------------------------------------------------------------------

    def _find_template(self, image: np.ndarray, threshold: float
                       ) -> tuple[tuple[int, int] | None, float]:
        """Find the target lock icon in the game screenshot.

        Returns ((x, y), confidence) or (None, 0.0).
        """
        # Tier 1: cheap pixel check — has the region changed at all?
        if self._last_pos is not None and self._last_region_pixels is not None:
            x, y = self._last_pos
            current = self._extract_region(
                image, x, y, self._template_w, self._template_h
            )
            if current is not None and current.shape == self._last_region_pixels.shape:
                if np.array_equal(current, self._last_region_pixels):
                    # Unchanged — reuse position (skip expensive matching)
                    return self._last_pos, 1.0

        # Tier 2: limited area search around last known position
        if self._last_pos is not None:
            result = self._match_in_region(image, self._last_pos, threshold)
            if result is not None:
                return result

        # Tier 3: full game window search
        return self._match_full(image, threshold)

    def _match_in_region(self, image: np.ndarray, center: tuple[int, int],
                         threshold: float
                         ) -> tuple[tuple[int, int], float] | None:
        """Template match in a cropped region around *center*."""
        cx, cy = center
        ih, iw = image.shape[:2]
        th, tw = self._template_h, self._template_w

        # Crop region with margin, clamped to image bounds
        margin = getattr(self._config, "ocr_search_margin", 80)
        x1 = max(0, cx - margin)
        y1 = max(0, cy - margin)
        x2 = min(iw, cx + tw + margin)
        y2 = min(ih, cy + th + margin)

        region = image[y1:y2, x1:x2]
        if region.shape[0] < th or region.shape[1] < tw:
            return None

        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(
            gray, self._template_gray, cv2.TM_CCOEFF_NORMED,
        )
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            abs_x, abs_y = x1 + max_loc[0], y1 + max_loc[1]
            if self._validate_match(image, abs_x, abs_y):
                return (abs_x, abs_y), max_val
        return None

    def _match_full(self, image: np.ndarray, threshold: float
                    ) -> tuple[tuple[int, int] | None, float]:
        """Template match across the entire game screenshot."""
        ih, iw = image.shape[:2]
        if ih < self._template_h or iw < self._template_w:
            return None, 0.0

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(
            gray, self._template_gray, cv2.TM_CCOEFF_NORMED,
        )
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            if self._validate_match(image, max_loc[0], max_loc[1]):
                return max_loc, max_val
        return None, 0.0

    def _validate_match(self, image: np.ndarray, x: int, y: int) -> bool:
        """Verify a candidate match has bright pixels inside and darker outside.

        Rejects uniform bright areas (e.g. white arrows, UI elements) that
        happen to score well on shape correlation.
        """
        region = self._extract_region(image, x, y,
                                      self._template_w, self._template_h)
        if region is None:
            return False

        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        inside = float(np.mean(gray[self._template_mask_bool]))
        outside = float(np.mean(gray[self._template_inv_bool]))

        # Inside the shape must be very bright (white icon)
        if inside < MIN_INSIDE_BRIGHTNESS:
            return False
        # Must have clear contrast: outside should be noticeably darker
        if inside - outside < MIN_CONTRAST:
            return False
        return True

    @staticmethod
    def _extract_region(image: np.ndarray, x: int, y: int,
                        w: int, h: int) -> np.ndarray | None:
        """Extract a sub-region from image, returning None if out of bounds."""
        ih, iw = image.shape[:2]
        if x < 0 or y < 0 or x + w > iw or y + h > ih:
            return None
        return image[y:y + h, x:x + w].copy()

    # ------------------------------------------------------------------
    # ROI reading
    # ------------------------------------------------------------------

    def _read_rois(self, image: np.ndarray,
                   tx: int, ty: int) -> dict:
        """Read all configured ROI regions relative to template position."""
        data = {
            "hp_pct": None,
            "is_shared": None,
            "raw_name": "",
        }

        # HP bar
        roi_hp = getattr(self._config, "target_lock_roi_hp", None)
        if roi_hp:
            region = self._get_roi_region(image, tx, ty, roi_hp)
            if region is not None and region.size > 0:
                hp = self._read_hp_bar(region)
                data["hp_pct"] = hp
                if self._tick_count % 40 == 1:
                    log.info("Target HP: %.0f%% (ROI %dx%d, red+green pixels in region)",
                             (hp or 0) * 100, region.shape[1], region.shape[0])

        # Shared icon
        roi_shared = getattr(self._config, "target_lock_roi_shared", None)
        if roi_shared:
            region = self._get_roi_region(image, tx, ty, roi_shared)
            if region is not None and region.size > 0:
                data["is_shared"] = self._read_shared_icon(region)

        # Name — ONNX text recognition
        roi_name = getattr(self._config, "target_lock_roi_name", None)
        if roi_name:
            region = self._get_roi_region(image, tx, ty, roi_name)
            if region is not None and region.size > 0:
                name = self._read_mob_name(region)
                if name:
                    data["raw_name"] = name
                # Include the raw crop for debug overlay rendering
                if getattr(self._config, "scan_overlay_debug", False):
                    data["_name_crop"] = region
                if self._tick_count % 40 == 1:
                    log.info("Target name OCR: %r (ROI %dx%d)",
                             name, region.shape[1], region.shape[0])

        return data

    def _get_roi_region(self, image: np.ndarray, tx: int, ty: int,
                        roi: dict) -> np.ndarray | None:
        """Extract an ROI region from image given template position and offsets.

        Clamps the ROI to image bounds instead of rejecting out-of-bounds regions,
        so partial reads near screen edges still work.
        """
        dx = roi.get("dx", 0)
        dy = roi.get("dy", 0)
        w = roi.get("w", 0)
        h = roi.get("h", 0)
        if w <= 0 or h <= 0:
            return None

        ih, iw = image.shape[:2]
        x = tx + dx
        y = ty + dy

        # Clamp to image bounds
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(iw, x + w)
        y1 = min(ih, y + h)

        if x1 <= x0 or y1 <= y0:
            return None

        return image[y0:y1, x0:x1].copy()

    @staticmethod
    def _read_hp_bar(region: np.ndarray) -> float:
        """Estimate HP percentage from an HP bar region using HSV color analysis.

        Returns a float in [0.0, 1.0].
        """
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

        # Count red pixels (damage taken / low HP)
        red_mask1 = cv2.inRange(hsv, HP_RED_LOW1, HP_RED_HIGH1)
        red_mask2 = cv2.inRange(hsv, HP_RED_LOW2, HP_RED_HIGH2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)

        # Count green pixels (full HP)
        green_mask = cv2.inRange(hsv, HP_GREEN_LOW, HP_GREEN_HIGH)

        red_px = cv2.countNonZero(red_mask)
        green_px = cv2.countNonZero(green_mask)
        total = red_px + green_px

        if total == 0:
            return 0.0

        # Green portion = HP remaining
        return green_px / total

    @staticmethod
    def _read_shared_icon(region: np.ndarray) -> bool:
        """Detect if the shared loot icon is present via brightness check."""
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray)) > SHARED_BRIGHTNESS_THRESHOLD

    def _read_mob_name(self, region: np.ndarray) -> str | None:
        """Read mob name from the name ROI using ONNX text recognition."""
        try:
            from . import onnxtr_recognizer
            if not onnxtr_recognizer.is_available():
                return None
            result = onnxtr_recognizer.recognize_text(
                region, min_confidence=self._name_min_confidence,
            )
            if result is None:
                return None
            text, _confidence = result
            # Strip "Corpse" suffix if present
            if text.endswith(" Corpse"):
                text = text[:-7].strip()
            return text if text else None
        except Exception as e:
            log.debug("Mob name OCR failed: %s", e)
            return None

    def _check_name_change(self, raw_name: str):
        """Debounce and publish mob name changes.

        Requires `_name_debounce` consecutive frames with the same new name
        before publishing EVENT_MOB_TARGET_CHANGED.
        """
        if not raw_name:
            # No name detected — reset candidate but don't clear last published
            self._name_candidate = ""
            self._name_confirm_count = 0
            return

        if raw_name == self._last_mob_name:
            # Same as already published — no change needed
            self._name_candidate = ""
            self._name_confirm_count = 0
            return

        if raw_name == self._name_candidate:
            self._name_confirm_count += 1
        else:
            self._name_candidate = raw_name
            self._name_confirm_count = 1

        if self._name_confirm_count >= self._name_debounce:
            self._last_mob_name = raw_name
            self._name_candidate = ""
            self._name_confirm_count = 0
            self._event_bus.publish(EVENT_MOB_TARGET_CHANGED, {
                "mob_name": raw_name,
                "confidence": 0.8,
                "source": "ocr",
            })

    # ------------------------------------------------------------------
    # Heart exclusion zone
    # ------------------------------------------------------------------

    def _on_heart_update(self, data: dict):
        """Store the heart icon position for exclusion."""
        x = data.get("x", 0)
        y = data.get("y", 0)
        w = data.get("w", 0)
        h = data.get("h", 0)
        if w > 0 and h > 0:
            self._heart_exclusion = (x, y, w, h)

    def _on_heart_lost(self):
        """Clear the heart exclusion zone."""
        self._heart_exclusion = None
