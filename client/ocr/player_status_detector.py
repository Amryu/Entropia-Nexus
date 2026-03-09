"""Player heart icon detection with fast bar reading.

Finds the player's heart icon on the HUD using template matching,
then reads health bar and reload bar fill percentages at high frequency.

Multi-rate polling architecture:
- 250 ms base interval / 4 Hz (reload + health bar reads)
- 1 s template re-detection + tool presence check (every 4th tick)

Bar fill is measured by scanning columns left-to-right for matching
colors. The health bar has a white marker at its fill edge (+1 px).
When no tool is equipped (empty tool_name ROI), both bars shift down
by 8 px.

Supports two modes:
- **Push mode** (FrameDistributor): subscribes with divisor=1, receives
  frames via callback on the distributor's capture thread.
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

from ..core.constants import EVENT_PLAYER_STATUS_UPDATE, EVENT_PLAYER_STATUS_LOST, GAME_TITLE_PREFIX
from ..core.logger import get_logger
from ..platform import backend as _platform

log = get_logger("PlayerStatus")

# --- Timing ---
POLL_INTERVAL = 0.25   # 250 ms base interval / 4 Hz (legacy poll mode)
TEMPLATE_TICKS = 4     # every 4 ticks = 1 s for template + tool check
HEALTH_TICKS = 1       # every tick = 250 ms for health bar

# --- Search ---
LOST_TICKS = 3         # consecutive template misses before publishing lost

# --- Foreground gating ---
BACKGROUND_SLEEP = 1.0  # seconds to sleep when game is not visible

# --- Match validation ---
MIN_INSIDE_BRIGHTNESS = 180  # heart icon is red, not pure white
MIN_CONTRAST = 30            # brightness gap inside vs outside mask

# --- Bar colors (BGR) ---
#   Health (healthy) #50b19e  → BGR(158, 177, 80)
#   Health (low)     #ede697  → BGR(151, 230, 237)
#   Health (critical)#e95357  → BGR(87, 83, 233)
#   Reload           #ede697  → BGR(151, 230, 237)
HEALTH_HEALTHY_BGR = np.array([158, 177, 80], dtype=np.uint8)
HEALTH_LOW_BGR = np.array([151, 230, 237], dtype=np.uint8)
HEALTH_CRITICAL_BGR = np.array([87, 83, 233], dtype=np.uint8)
RELOAD_BGR = np.array([151, 230, 237], dtype=np.uint8)

COLOR_TOLERANCE = 25   # per-channel tolerance for bar color matching

# --- Tool presence ---
TOOL_BRIGHTNESS_THRESHOLD = 100  # pixel brightness to count as "text"
TOOL_TEXT_MIN_RATIO = 0.05       # at least 5% bright pixels = has text

# --- Layout shift ---
NO_TOOL_BAR_OFFSET = 8  # px bars shift down when no tool equipped


def _precompute_color_ranges(colors, tolerance=COLOR_TOLERANCE):
    """Pre-compute (lower, upper) BGR bounds for cv2.inRange."""
    ranges = []
    for c in colors:
        lo = np.clip(c.astype(np.int16) - tolerance, 0, 255).astype(np.uint8)
        hi = np.clip(c.astype(np.int16) + tolerance, 0, 255).astype(np.uint8)
        ranges.append((lo, hi))
    return ranges


class PlayerStatusDetector:
    """Detects the player heart icon and reads health/reload bars at high frequency.

    Uses alpha-masked template matching (three-tier strategy) at 1 Hz for
    position tracking, then reads bar fill percentages at 50–100 ms via
    fast vectorized color matching.
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
        self._game_origin: tuple[int, int] = (0, 0)

        # Template (loaded lazily)
        self._template_bgr = None
        self._template_gray = None
        self._template_mask = None
        self._template_mask_bool = None
        self._template_inv_bool = None
        self._template_h = 0
        self._template_w = 0

        # Tracking state
        self._last_pos: tuple[int, int] | None = None
        self._last_region_pixels: np.ndarray | None = None
        self._miss_count = 0
        self._published_lost = False
        self._last_confidence = 0.0

        # Bar state (cached between reads)
        self._health_pct: float | None = None
        self._reload_pct: float | None = None
        self._tool_equipped = True  # assume equipped until checked

        # Idle mode tracking
        self._idle_ticks = 0  # consecutive ticks with no data change
        self._last_health_pct: float | None = None
        self._last_reload_pct: float | None = None

        # Pre-compute color ranges for fast cv2.inRange calls
        self._health_ranges = _precompute_color_ranges(
            [HEALTH_HEALTHY_BGR, HEALTH_LOW_BGR, HEALTH_CRITICAL_BGR]
        )
        self._reload_ranges = _precompute_color_ranges([RELOAD_BGR])

        self._load_template()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _load_template(self):
        if cv2 is None:
            log.warning("OpenCV not available — player status detection disabled")
            return
        assets = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets"
        )
        path = os.path.join(assets, "player_heart.png")
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
                "player-status", self._on_frame, hz=4,
            )
            log.info("Started (push mode)")
        else:
            self._thread = threading.Thread(
                target=self._poll_loop, daemon=True, name="player-status",
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
        log.info("Stopped")

    # ------------------------------------------------------------------
    # Push mode (FrameDistributor callback)
    # ------------------------------------------------------------------

    def _on_frame(self, frame: np.ndarray, timestamp: float):
        """Callback from FrameDistributor — runs on the capture thread."""
        if not self._running:
            return
        if not getattr(self._config, "player_status_enabled", True):
            return

        # Idle mode: skip most ticks when nothing is changing
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
                if getattr(self._config, "player_status_enabled", True):
                    self._tick_legacy()
            except Exception as e:
                log.error("Tick error: %s", e)
            self._tick_count += 1
            # Idle mode: multiply poll interval when no change detected
            idle_threshold = getattr(self._config, "ocr_idle_threshold", 50)
            idle_mult = getattr(self._config, "ocr_idle_multiplier", 5)
            if self._idle_ticks >= idle_threshold:
                time.sleep(POLL_INTERVAL * idle_mult)
            else:
                time.sleep(POLL_INTERVAL)

    def _tick_legacy(self):
        """Legacy poll tick: discover window, capture, then process."""
        # Auto-discover game window
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
        """Process a captured game frame: template match + bar reads."""
        tick_count = self._tick_count

        # --- Template detection (every TEMPLATE_TICKS or when lost) ---
        do_template = (tick_count % TEMPLATE_TICKS == 0) or self._last_pos is None
        if do_template:
            threshold = getattr(self._config, "player_status_match_threshold", 0.90)
            pos, confidence = self._find_template(image, threshold)
            if pos is not None:
                self._last_pos = pos
                self._miss_count = 0
                self._published_lost = False
                self._last_confidence = confidence
                x, y = pos
                self._last_region_pixels = self._extract_region(image, x, y,
                                                                self._template_w,
                                                                self._template_h)
                # Check tool presence (same 1 s cadence)
                self._update_tool_presence(image, x, y)
            else:
                self._miss_count += 1
                if self._miss_count >= LOST_TICKS and not self._published_lost:
                    self._published_lost = True
                    self._last_pos = None
                    self._last_region_pixels = None
                    self._health_pct = None
                    self._reload_pct = None
                    self._event_bus.publish(EVENT_PLAYER_STATUS_LOST, {})
                return

        if self._last_pos is None:
            return

        tx, ty = self._last_pos
        dy_adj = 0 if self._tool_equipped else NO_TOOL_BAR_OFFSET

        # --- Reload bar (every tick = 50 ms) ---
        self._reload_pct = self._read_bar(
            image, tx, ty, "player_status_roi_reload",
            self._reload_ranges, dy_adj, white_line=False,
        )

        # --- Health bar (every HEALTH_TICKS = 100 ms) ---
        if tick_count % HEALTH_TICKS == 0:
            self._health_pct = self._read_bar(
                image, tx, ty, "player_status_roi_health",
                self._health_ranges, dy_adj, white_line=True,
            )

        # --- Publish ---
        gx, gy = self._game_origin
        data = {
            "x": gx + tx, "y": gy + ty,
            "w": self._template_w, "h": self._template_h,
            "confidence": self._last_confidence,
            "health_pct": self._health_pct,
            "reload_pct": self._reload_pct,
            "tool_equipped": self._tool_equipped,
            "game_origin": self._game_origin,
        }
        self._event_bus.publish(EVENT_PLAYER_STATUS_UPDATE, data)

        # --- Idle tracking ---
        if (self._health_pct == self._last_health_pct
                and self._reload_pct == self._last_reload_pct):
            self._idle_ticks += 1
        else:
            self._idle_ticks = 0
        self._last_health_pct = self._health_pct
        self._last_reload_pct = self._reload_pct

    # ------------------------------------------------------------------
    # Three-tier template search
    # ------------------------------------------------------------------

    def _find_template(self, image: np.ndarray, threshold: float
                       ) -> tuple[tuple[int, int] | None, float]:
        """Find the heart icon in the game screenshot."""
        # Tier 1: cheap pixel check
        if self._last_pos is not None and self._last_region_pixels is not None:
            x, y = self._last_pos
            current = self._extract_region(
                image, x, y, self._template_w, self._template_h
            )
            if current is not None and current.shape == self._last_region_pixels.shape:
                if np.array_equal(current, self._last_region_pixels):
                    return self._last_pos, 1.0

        # Tier 2: limited area search
        if self._last_pos is not None:
            result = self._match_in_region(image, self._last_pos, threshold)
            if result is not None:
                return result

        # Tier 3: full game window search
        return self._match_full(image, threshold)

    def _match_in_region(self, image: np.ndarray, center: tuple[int, int],
                         threshold: float
                         ) -> tuple[tuple[int, int], float] | None:
        cx, cy = center
        ih, iw = image.shape[:2]
        th, tw = self._template_h, self._template_w
        margin = getattr(self._config, "ocr_search_margin", 80)
        x1 = max(0, cx - margin)
        y1 = max(0, cy - margin)
        x2 = min(iw, cx + tw + margin)
        y2 = min(ih, cy + th + margin)
        region = image[y1:y2, x1:x2]
        if region.shape[0] < th or region.shape[1] < tw:
            return None
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(gray, self._template_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val >= threshold:
            abs_x, abs_y = x1 + max_loc[0], y1 + max_loc[1]
            if self._validate_match(image, abs_x, abs_y):
                return (abs_x, abs_y), max_val
        return None

    def _match_full(self, image: np.ndarray, threshold: float
                    ) -> tuple[tuple[int, int] | None, float]:
        ih, iw = image.shape[:2]
        if ih < self._template_h or iw < self._template_w:
            return None, 0.0
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(gray, self._template_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val >= threshold:
            if self._validate_match(image, max_loc[0], max_loc[1]):
                return max_loc, max_val
        return None, 0.0

    def _validate_match(self, image: np.ndarray, x: int, y: int) -> bool:
        region = self._extract_region(image, x, y,
                                      self._template_w, self._template_h)
        if region is None:
            return False
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        inside = float(np.mean(gray[self._template_mask_bool]))
        outside = float(np.mean(gray[self._template_inv_bool]))
        if inside < MIN_INSIDE_BRIGHTNESS:
            return False
        if inside - outside < MIN_CONTRAST:
            return False
        return True

    @staticmethod
    def _extract_region(image: np.ndarray, x: int, y: int,
                        w: int, h: int) -> np.ndarray | None:
        ih, iw = image.shape[:2]
        if x < 0 or y < 0 or x + w > iw or y + h > ih:
            return None
        return image[y:y + h, x:x + w].copy()

    # ------------------------------------------------------------------
    # Bar reading
    # ------------------------------------------------------------------

    def _read_bar(self, image: np.ndarray, tx: int, ty: int,
                  config_attr: str, color_ranges: list,
                  dy_adj: int, *, white_line: bool) -> float | None:
        """Read bar fill percentage from a ROI using column color scanning.

        Args:
            color_ranges: Pre-computed list of (lower_bgr, upper_bgr) tuples.
            dy_adj: Extra vertical offset (e.g. NO_TOOL_BAR_OFFSET).
            white_line: If True, add 1 px for the health bar's white end marker.

        Returns:
            Fill percentage [0.0, 1.0] or None if ROI is not configured/capturable.
        """
        roi = getattr(self._config, config_attr, None)
        if not roi:
            return None
        w = roi.get("w", 0)
        h = roi.get("h", 0)
        if w <= 0 or h <= 0:
            return None

        rx = tx + roi.get("dx", 0)
        ry = ty + roi.get("dy", 0) + dy_adj
        ih, iw = image.shape[:2]
        if rx < 0 or ry < 0 or rx + w > iw or ry + h > ih:
            return None

        # View (no copy) — we only read pixels
        region = image[ry:ry + h, rx:rx + w]
        return self._measure_bar_fill(region, color_ranges, white_line)

    @staticmethod
    def _measure_bar_fill(region: np.ndarray,
                          color_ranges: list,
                          white_line: bool) -> float:
        """Measure bar fill by finding the rightmost column with matching color.

        Scans columns left-to-right. A column is "filled" if at least 1 pixel
        in that column matches any of the target colors (within tolerance).

        Args:
            region: BGR image of the bar ROI.
            color_ranges: Pre-computed [(lower_bgr, upper_bgr), ...] bounds.
            white_line: Add 1 px for the health bar's white end marker.
        """
        h, w = region.shape[:2]
        if w == 0:
            return 0.0

        # Build combined mask across all target colors using cv2.inRange (fast C++)
        mask = np.zeros((h, w), dtype=np.uint8)
        for lo, hi in color_ranges:
            mask = cv2.bitwise_or(mask, cv2.inRange(region, lo, hi))

        # Which columns have at least one matching pixel?
        col_filled = np.any(mask > 0, axis=0)
        indices = np.where(col_filled)[0]
        if len(indices) == 0:
            return 0.0

        rightmost = int(indices[-1])
        # +1 for 0-indexed → width; +1 extra for health bar's white end marker
        extra = 2 if white_line else 1
        return min(1.0, (rightmost + extra) / w)

    # ------------------------------------------------------------------
    # Tool presence
    # ------------------------------------------------------------------

    def _update_tool_presence(self, image: np.ndarray, tx: int, ty: int):
        """Check if a tool name is displayed in the tool_name ROI.

        When no tool is equipped, the HUD shifts the health and reload
        bars down by NO_TOOL_BAR_OFFSET pixels.
        """
        roi = getattr(self._config, "player_status_roi_tool_name", None)
        if not roi:
            self._tool_equipped = True
            return
        w = roi.get("w", 0)
        h = roi.get("h", 0)
        if w <= 0 or h <= 0:
            self._tool_equipped = True
            return

        rx = tx + roi.get("dx", 0)
        ry = ty + roi.get("dy", 0)
        ih, iw = image.shape[:2]
        if rx < 0 or ry < 0 or rx + w > iw or ry + h > ih:
            self._tool_equipped = True
            return

        region = image[ry:ry + h, rx:rx + w]
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        bright_pixels = int(np.count_nonzero(gray > TOOL_BRIGHTNESS_THRESHOLD))
        total_pixels = gray.size
        self._tool_equipped = bright_pixels > (total_pixels * TOOL_TEXT_MIN_RATIO)

    # ------------------------------------------------------------------
    # ROI helper (for overlay debug / generic reads)
    # ------------------------------------------------------------------

    def _get_roi_region(self, image: np.ndarray, tx: int, ty: int,
                        roi: dict) -> np.ndarray | None:
        """Extract an ROI region from image given template position and offsets."""
        dx = roi.get("dx", 0)
        dy = roi.get("dy", 0)
        w = roi.get("w", 0)
        h = roi.get("h", 0)
        if w <= 0 or h <= 0:
            return None
        return self._extract_region(image, tx + dx, ty + dy, w, h)
