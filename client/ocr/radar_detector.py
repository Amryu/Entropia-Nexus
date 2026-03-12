"""Radar coordinate OCR detector.

Reads "Lon: DDDDD" and "Lat: DDDDD" coordinates from the game's radar HUD.
The radar is a dark circular widget with a white outer border that scales
proportionally with the game's UI Scale setting (100%–200%).

Strategy:
1. HoughCircles anchors on the radar's dark circle + white border.
2. Scale is derived from detected radius vs BASE_RADAR_RADIUS_PX.
3. Text ROI is computed as fixed ratio-offsets from the circle centre.
4. Scaleform-faithful 4-bit templates (ScaleformRenderer) are matched
   against blob-segmented text using the same scoring formula as the
   STPK-based market price detector.  PIL is used as a fallback when
   freetype-py is unavailable.
5. Failed reads accumulate silently; after CONSECUTIVE_FAIL_BEFORE_SCAN
   ticks a background Hough scan checks whether the radar moved.  If it
   did, EVENT_RADAR_DEBUG {"needs_recalibrate": True} is published so the
   UI can prompt the user.  EVENT_RADAR_LOST is published only when the
   circle cannot be found for more than 5 s.

Geometry constants were measured from reference screenshots:
  full_radar_small.PNG  — 100 % UI scale  (r = 94 px)
  full_radar_big.PNG    — 200 % UI scale  (r = 190 px)
"""

import re
import threading
import time
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from PIL import Image, ImageDraw, ImageFont as _ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

try:
    from .scaleform_render import ScaleformRenderer as _ScaleformRenderer
    _SCALEFORM_AVAILABLE = True
except Exception:
    _SCALEFORM_AVAILABLE = False

try:
    from .stpk import read_stpk as _read_stpk
    _STPK_AVAILABLE = True
except Exception:
    _STPK_AVAILABLE = False

from ..core.constants import (
    EVENT_RADAR_COORDINATES,
    EVENT_RADAR_DEBUG,
    EVENT_RADAR_LOST,
    EVENT_HOTKEY_TRIGGERED,
    GAME_TITLE_PREFIX,
)
from ..core.logger import get_logger
from ..platform import backend as _platform

log = get_logger("Radar")

# ---------------------------------------------------------------------------
# Geometry constants  (all ratios are relative to the detected circle radius)
# ---------------------------------------------------------------------------

#: Radar circle radius at 100 % UI scale (measured from full_radar_small.PNG).
BASE_RADAR_RADIUS_PX   = 94

#: Text cap height at 100 % UI scale (measured from Min Size.PNG).
BASE_CAP_HEIGHT_PX     = 9

#: Base font pixel size at 100 % UI scale.  Scales linearly with radar radius.
BASE_FONT_SIZE_PX      = 11

#: Lon row top edge  = cy + LON_OFFSET_RATIO * r
TEXT_LON_OFFSET_RATIO  = 1.01

#: Lat row top edge  = Lon row top + STRIDE_RATIO * r
TEXT_STRIDE_RATIO      = 0.181

#: Text left edge    = cx + LEFT_RATIO * r   (negative = left of centre)
TEXT_LEFT_RATIO        = -0.48

#: Text region width = WIDTH_RATIO * r  (digits only, excludes label + compass dir)
TEXT_WIDTH_RATIO       = 0.41

#: Row region height = HEIGHT_RATIO * r  (cap height + descenders + padding)
TEXT_HEIGHT_RATIO      = 0.130

# ---------------------------------------------------------------------------
# OCR constants
# ---------------------------------------------------------------------------

#: Pixels below this brightness are zeroed before blob detection.
RADAR_TEXT_BRIGHTNESS_THRESHOLD = 100

#: Digit stride as fraction of circle radius r.
#: Measured: small r=95 → 5 digits in 33px (0.0695), big r=190 → 5 digits in 65px (0.0684).
DIGIT_STRIDE_RATIO      = 0.069

#: Fixed template grid dimensions (all characters normalised to this size).
RADAR_GRID_W = 10
RADAR_GRID_H = 20

#: Characters that appear in the label portion of each coordinate row.
#: Cardinal direction suffixes (N/S/E/W) are deliberately excluded — they
#: are skipped by the digit-zone position filter and never matched.
RADAR_CHARS = "0123456789Lonat:"

#: Coordinates are 4–6 digits (game coordinate space can require up to 6).
COORD_MIN_DIGITS = 4
COORD_MAX_DIGITS = 6
RADAR_EXPECTED_DIGITS = 5

# 2x OCR pipeline constants
RADAR_UPSCALE_FACTOR = 2
RADAR_UPSCALE_INTERP = cv2.INTER_CUBIC if cv2 is not None else None
RADAR_HUE_BASE_THRESHOLD = 10
RADAR_HUE_MIN_THRESHOLD = 0
RADAR_DIGIT_CONFIDENCE_TARGET = 0.80
# Base ROI is slightly nudged left to avoid clipping the first digit.
RADAR_TEXT_X_LEFT_NUDGE_PX = 1
RADAR_BINARIZE_THRESHOLD = 200
RADAR_BINARIZE_THRESHOLD_BRIGHT = 250
RADAR_STRICT_BIN_MIN_KEEP_RATIO = 0.85
RADAR_HUE_FILTER_MIN_KEEP_RATIO = 0.85
RADAR_TEXT_EXTRA_LEFT_PX = 2
RADAR_TEXT_EXTRA_RIGHT_PX = 1
RADAR_TEXT_EXTRA_ROW_PAD_PX = 1
RADAR_X_SWEEP_OFFSETS = (-2, -1, 0, 1, 2)
# Runtime fast path uses no sweep; full sweep is only used on failure fallback.
RADAR_X_SWEEP_FAST_OFFSETS = (0,)
RADAR_SCORE_SHIFT_OFFSETS = (-2, -1, 1, 2)
RADAR_VALLEY_SEARCH_RADIUS_RATIO = 0.30
RADAR_CONTENT_START_RATIO = 0.25
RADAR_BLOB_MIN_COL_DENSITY_RATIO = 0.20
RADAR_BLOB_MIN_WIDTH_RATIO = 0.35
RADAR_BLOB_MAX_WIDTH_RATIO = 1.45
RADAR_BLOB_ADVANCE_TOL_RATIO = 0.60
RADAR_ROW_DENSITY_KEEP_RATIO = 0.35
RADAR_ROW_KEEP_PAD_PX = 1
RADAR_BLOB_EDGE_KEEP_RATIO = 0.28
RADAR_TEXT_LEFT_NUDGE_MAX_SCALE = 1.35
RADAR_CALIBRATION_OFFSETS = (-1, 0, 1)
RADAR_CALIBRATION_HUES = tuple(range(RADAR_HUE_BASE_THRESHOLD, RADAR_HUE_MIN_THRESHOLD - 1, -1))
RADAR_DEFAULT_HUE_THRESHOLD = RADAR_HUE_BASE_THRESHOLD
RADAR_HUE_ADJUST_MIN_DIGIT_CONF = 0.70
RADAR_HUE_ADJUST_MIN_OVERALL_CONF = 0.75
RADAR_SECOND_BEST_CLEAR_MARGIN = 0.10
RADAR_GATED_DIGIT_SCORE_FLOOR = 0.02
RADAR_BENCHMARK_LOG_EVERY = 50

# ---------------------------------------------------------------------------
# Detection / timing constants
# ---------------------------------------------------------------------------

#: HoughCircles edge-strength threshold (param1).
HOUGH_PARAM1 = 100

#: HoughCircles accumulator threshold (param2); try cascading to 25 on miss.
HOUGH_PARAM2_STRICT  = 40
HOUGH_PARAM2_LENIENT = 25
HOUGH_PARAM2_BIN_SWEEP = (18, 22, 26)
RADAR_CIRCLE_BINARY_THRESHOLDS = (170, 180, 160, 190, 150, 200)

#: Poll interval (seconds).
DETECT_INTERVAL_S = 0.25   # 4 Hz

#: Confidence below this = failed read for that tick.
CONF_FAIL_THRESHOLD = 0.38

#: Consecutive failed reads before a background rescan is attempted.
CONSECUTIVE_FAIL_BEFORE_SCAN = 120   # ≈ 30 s at 4 Hz

#: How many px the circle centre must shift to trigger recalibration notice.
RECAL_DIST_THRESHOLD = 30

#: Circle radius must differ by more than this to trigger recalibration.
RECAL_RADIUS_THRESHOLD = 15

#: Seconds with no circle found before EVENT_RADAR_LOST is published.
LOST_TIMEOUT_S = 5.0

#: Minimum brightness for a pixel to count as "white border".
WHITE_BORDER_BRIGHTNESS = 220

#: Minimum fraction of white pixels in the border ring to accept a candidate.
#: The border is perfectly white but only ~1 px wide, so at small radii the
#: fraction of bright pixels in a sampled ring is modest.
WHITE_BORDER_MIN_FRAC = 0.12

#: Minimum brightness for an interior ring to count as a gray ring.
INTERIOR_RING_BRIGHTNESS = 40

#: Minimum number of interior gray rings to accept a candidate (radar has 4).
INTERIOR_RING_MIN_COUNT = 3

# ---------------------------------------------------------------------------
# Font / Scaleform renderer
# ---------------------------------------------------------------------------

STPK_DIR = Path(__file__).parent.parent / "assets" / "stpk"
RADAR_DIGIT_STPK_DEFAULT = "radar_digits.stpk"


def _resolve_radar_font_path() -> Path:
    """Resolve a usable Arial Unicode font path without bundling a TTF in assets."""
    candidates = [
        Path(__file__).parent.parent / "assets" / "arial-unicode-ms.ttf",
        Path(r"C:\Windows\Fonts\ARIALUNI.TTF"),
        Path(r"C:\Windows\Fonts\arialuni.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


FONT_PATH = _resolve_radar_font_path()

#: Subpixel offsets for the Scaleform-faithful renderer.  These simulate the
#: fractional screen position of the glyph inside the game UI and were found
#: by grid-search against observed pixel data from the coordinate overlay.
SCALEFORM_X_OFFSET = 0.28
SCALEFORM_Y_OFFSET = 0.04

# ---------------------------------------------------------------------------
# Coordinate pattern — matches 4–6 digit run in decoded text.
# ---------------------------------------------------------------------------

_COORD_RE = re.compile(r'\d{4,6}')


# ---------------------------------------------------------------------------
# normalize_blob import (same helper used by market_price_detector)
# ---------------------------------------------------------------------------

try:
    from .skill_disambiguation import normalize_blob as _normalize_blob
except ImportError:
    def _normalize_blob(intensity_4bit, x0, x1, text_top, text_h,   # noqa: E302
                        grid_w, grid_h, right_align):
        return np.zeros((grid_h, grid_w), dtype=np.uint8)


# ---------------------------------------------------------------------------
# RadarDetector
# ---------------------------------------------------------------------------

class RadarDetector:
    """Detects the radar HUD and publishes coordinate events at ~2 Hz.

    Constructor mirrors the other OCR detectors:
        RadarDetector(config, event_bus, frame_source)

    *frame_source* may be a ``FrameDistributor``, ``SharedFrameCache``,
    or ``ScreenCapturer``.  When a ``FrameDistributor`` is supplied the
    detector operates in push mode (no own thread); otherwise it falls
    back to poll mode with its own thread.
    """

    def __init__(self, config, event_bus, frame_source, config_path: str = "config.json"):
        self._config       = config
        self._config_path  = config_path
        self._event_bus    = event_bus

        # Frame source
        self._distributor  = None
        self._subscription = None
        self._frame_cache  = None
        self._capturer     = None
        try:
            from .frame_distributor import FrameDistributor
            if isinstance(frame_source, FrameDistributor):
                self._distributor = frame_source
            else:
                try:
                    from .frame_cache import SharedFrameCache
                    if isinstance(frame_source, SharedFrameCache):
                        self._frame_cache = frame_source
                    else:
                        self._capturer = frame_source
                except ImportError:
                    self._capturer = frame_source
        except ImportError:
            self._capturer = frame_source

        # Thread control (poll mode only)
        self._running = False
        self._thread  = None

        # Cached radar circle  (cx, cy, r) — restore from persisted calibration
        self._circle: tuple[int, int, int] | None = None
        self._scale:    float = 1.0
        self._font_size: int = BASE_FONT_SIZE_PX
        saved = getattr(config, "radar_last_circle", None)
        if isinstance(saved, (list, tuple)) and len(saved) == 3:
            try:
                self._set_circle((int(saved[0]), int(saved[1]), int(saved[2])),
                                 persist=False)
                log.info("Restored persisted radar circle: cx=%d cy=%d r=%d",
                         saved[0], saved[1], saved[2])
            except Exception:
                pass

        # Template cache — invalidated on font size change
        self._templates: dict[str, np.ndarray] | None = None
        self._grid_w: int = 0
        self._grid_h: int = 0
        # Multi-size template cache: list of (templates, grid_w, grid_h, font_size)
        self._multi_templates: list[tuple[dict[str, np.ndarray], int, int, float]] | None = None
        # STPK templates keyed by 2x font size
        self._stpk_templates_by_size: dict[int, dict[str, np.ndarray]] = {}
        self._stpk_grid_w: int = 0
        self._stpk_grid_h: int = 0
        self._stpk_sizes: list[int] = []
        self._stpk_missing_logged: bool = False
        self._load_radar_digit_stpk()

        # State
        self._last_coords:       tuple[int, int] | None = None
        self._consecutive_fails: int   = 0
        self._lost_since:        float | None = None
        self._runtime_calibration: dict | None = None
        self._first_calibration_ms: float | None = None
        self._subsequent_ms_total: float = 0.0
        self._subsequent_ms_count: int = 0

        # Game window
        self._game_hwnd     = None
        self._game_geometry = None

        # Hotkey subscription
        self._cb_hotkey = self._on_hotkey
        event_bus.subscribe(EVENT_HOTKEY_TRIGGERED, self._cb_hotkey)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        if self._running:
            return
        self._running = True
        if self._distributor is not None:
            self._subscription = self._distributor.subscribe(
                "radar", self._on_frame, hz=2,
            )
            log.info("Radar detector started (push mode)")
        else:
            self._thread = threading.Thread(
                target=self._detect_loop, daemon=True, name="RadarDetector"
            )
            self._thread.start()
            log.info("Radar detector started (poll mode)")

    def stop(self):
        self._running = False
        if self._subscription is not None:
            self._subscription.enabled = False
            self._subscription = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self._event_bus.unsubscribe(EVENT_HOTKEY_TRIGGERED, self._cb_hotkey)

    def _on_hotkey(self, data: dict) -> None:
        if isinstance(data, dict) and data.get("action") == "radar_recalibrate":
            self.trigger_recalibrate()

    def trigger_recalibrate(self):
        """Force a full Hough re-scan on the next tick (e.g. from hotkey)."""
        self._circle = None
        self._config.radar_last_circle = None
        self._runtime_calibration = None
        log.info("Radar recalibration triggered")

    # ------------------------------------------------------------------
    # Push mode (FrameDistributor callback)
    # ------------------------------------------------------------------

    def _on_frame(self, frame: np.ndarray, timestamp: float):
        """Callback from FrameDistributor — runs on the capture thread."""
        if not self._running:
            return
        if cv2 is None:
            return
        if not getattr(self._config, "radar_enabled", True):
            return
        self._game_geometry = self._distributor.game_geometry
        try:
            self._process_frame(frame)
        except Exception as e:
            log.error("Radar tick error: %s", e, exc_info=True)

    # ------------------------------------------------------------------
    # Poll mode (own thread)
    # ------------------------------------------------------------------

    def _detect_loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as e:
                log.error("Radar tick error: %s", e, exc_info=True)
            time.sleep(DETECT_INTERVAL_S)

    def _tick(self):
        if cv2 is None:
            return
        if not getattr(self._config, "radar_enabled", True):
            return

        # Auto-discover game window
        if not self._game_hwnd or not _platform.is_window_visible(self._game_hwnd):
            hwnd = _platform.find_window_by_title_prefix(GAME_TITLE_PREFIX)
            if not hwnd:
                return
            geo = _platform.get_window_geometry(hwnd)
            self._game_hwnd     = hwnd
            self._game_geometry = geo

        frame = self._capture_frame()
        if frame is None:
            return
        self._process_frame(frame)

    # ------------------------------------------------------------------
    # Shared frame processing
    # ------------------------------------------------------------------

    def _publish_circle_event(self) -> None:
        """Publish the current circle + ROI position so the overlay tracks every frame."""
        self._event_bus.publish(EVENT_RADAR_DEBUG, {
            "needs_recalibrate": False,
            **self._build_circle_data(),
        })

    def _build_circle_data(self) -> dict:
        """Build the circle + ROI dict for the current cached circle."""
        cx, cy, r = self._circle
        go = (self._game_geometry[0], self._game_geometry[1]) if self._game_geometry else (0, 0)
        gx, gy = go

        scale      = r / BASE_RADAR_RADIUS_PX
        left_extra = max(1, round(RADAR_TEXT_EXTRA_LEFT_PX * scale))
        right_extra = max(1, round(RADAR_TEXT_EXTRA_RIGHT_PX * scale))
        row_pad = max(1, round(RADAR_TEXT_EXTRA_ROW_PAD_PX * scale))
        row_h      = max(5, round(TEXT_HEIGHT_RATIO * r) + row_pad * 2)
        x_nudge    = round(-1 * (scale - 1))   # 0 at 100 %, -1 at 200 %
        left_nudge = RADAR_TEXT_X_LEFT_NUDGE_PX if scale <= RADAR_TEXT_LEFT_NUDGE_MAX_SCALE else 0
        text_left  = cx + round(TEXT_LEFT_RATIO * r) + x_nudge - left_nudge - left_extra
        text_right = cx + round(TEXT_LEFT_RATIO * r) + x_nudge + round(TEXT_WIDTH_RATIO * r) + round(4 * (scale - 1)) + 2 + right_extra
        lon_top    = cy + round(TEXT_LON_OFFSET_RATIO * r) - row_pad
        lat_top    = cy + round((TEXT_LON_OFFSET_RATIO + TEXT_STRIDE_RATIO) * r) - row_pad
        roi_w      = text_right - text_left

        return {
            "circle_cx":  gx + cx,
            "circle_cy":  gy + cy,
            "circle_r":   r,
            "game_origin": go,
            "lon_roi": (gx + text_left, gy + lon_top, roi_w, row_h),
            "lat_roi": (gx + text_left, gy + lat_top, roi_w, row_h),
        }

    def _process_frame(self, frame: np.ndarray):
        tick_start = time.perf_counter()
        # Phase 1 — locate radar circle (only when not cached)
        if self._circle is None:
            circle = self._find_radar_circle(frame)
            if circle is None:
                self._handle_no_circle()
                return
            self._set_circle(circle)

        # Always publish circle + ROI position so overlay tracks every frame
        self._publish_circle_event()

        # Phase 2 — read coordinates
        result = self._read_coordinates(frame)
        if result is None:
            self._consecutive_fails += 1
            if self._consecutive_fails >= CONSECUTIVE_FAIL_BEFORE_SCAN:
                self._background_rescan(frame)
            return

        lon, lat, conf = result
        self._consecutive_fails = 0
        self._lost_since = None

        circle_data = self._build_circle_data()
        self._last_coords = (lon, lat)

        elapsed_ms = (time.perf_counter() - tick_start) * 1000.0
        if self._first_calibration_ms is None and self._runtime_calibration is not None:
            self._first_calibration_ms = elapsed_ms
            log.info("Radar benchmark: first calibration run %.1f ms", elapsed_ms)
        else:
            self._subsequent_ms_total += elapsed_ms
            self._subsequent_ms_count += 1
            if self._subsequent_ms_count % RADAR_BENCHMARK_LOG_EVERY == 0:
                avg_ms = self._subsequent_ms_total / max(1, self._subsequent_ms_count)
                log.info(
                    "Radar benchmark: subsequent avg %.1f ms over %d runs",
                    avg_ms, self._subsequent_ms_count,
                )

        avg_subsequent_ms = (
            self._subsequent_ms_total / self._subsequent_ms_count
            if self._subsequent_ms_count > 0 else None
        )
        self._event_bus.publish(EVENT_RADAR_COORDINATES, {
            "lon":        lon,
            "lat":        lat,
            "confidence": conf,
            "scale":      self._scale,
            "first_calibration_ms": self._first_calibration_ms,
            "avg_subsequent_ms": avg_subsequent_ms,
            **circle_data,
        })

    def _background_rescan(self, frame):
        """After many consecutive failures, check whether the circle moved."""
        circle = self._find_radar_circle(frame)
        if circle is None:
            self._handle_no_circle()
            self._consecutive_fails = 0
            return

        cx,  cy,  r   = circle
        ocx, ocy, or_ = self._circle
        dist = ((cx - ocx) ** 2 + (cy - ocy) ** 2) ** 0.5
        if dist > RECAL_DIST_THRESHOLD or abs(r - or_) > RECAL_RADIUS_THRESHOLD:
            log.info(
                "Radar circle auto-updated: (%d,%d,r%d) → (%d,%d,r%d)",
                ocx, ocy, or_, cx, cy, r,
            )
            self._set_circle(circle)

        self._publish_circle_event()
        self._consecutive_fails = 0

    def _handle_no_circle(self):
        now = time.monotonic()
        if self._lost_since is None:
            self._lost_since = now
        elif now - self._lost_since >= LOST_TIMEOUT_S:
            self._event_bus.publish(EVENT_RADAR_LOST, {})
            self._lost_since = now  # rate-limit repeat publishes

    # ------------------------------------------------------------------
    # Frame capture
    # ------------------------------------------------------------------

    def _capture_frame(self) -> np.ndarray | None:
        if self._game_hwnd is None:
            return None
        try:
            if self._frame_cache is not None:
                return self._frame_cache.get_frame(
                    self._game_hwnd, geometry=self._game_geometry
                )
            return self._capturer.capture_window(
                self._game_hwnd, geometry=self._game_geometry
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Circle detection (Hough)
    # ------------------------------------------------------------------

    def _find_radar_circle(self, frame: np.ndarray) -> tuple[int, int, int] | None:
        """Desaturate + binarize, then run a single-pass Hough circle search."""
        if frame.ndim == 3:
            # Desaturate by zeroing HSV saturation, then convert to grayscale.
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hsv[:, :, 1] = 0
            desat_bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
            gray = cv2.cvtColor(desat_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        h, w = gray.shape
        min_r = max(20, int(BASE_RADAR_RADIUS_PX * 0.60))
        max_r = min(min(w, h) // 2, int(BASE_RADAR_RADIUS_PX * 2.10))

        # Threshold sweep keeps single-circle selection while recovering
        # detection reliability across lighting/background variants.
        for thr in RADAR_CIRCLE_BINARY_THRESHOLDS:
            _, binary = cv2.threshold(gray, int(thr), 255, cv2.THRESH_BINARY)
            for p2 in HOUGH_PARAM2_BIN_SWEEP:
                circles = cv2.HoughCircles(
                    binary,
                    cv2.HOUGH_GRADIENT,
                    dp=1,
                    minDist=min_r * 2,
                    param1=HOUGH_PARAM1,
                    param2=int(p2),
                    minRadius=min_r,
                    maxRadius=max_r,
                )
                if circles is None:
                    continue
                # Single-circle path: use the first detected circle.
                cx, cy, r = np.round(circles[0][0]).astype(int)
                return int(cx), int(cy), int(r)
        return None

    @staticmethod
    def _find_white_border(
        gray: np.ndarray, cx: int, cy: int, r_hint: int
    ) -> tuple[int, float]:
        """Scan outward from r_hint for a 1-px white ring.

        Returns (border_radius, fraction).  The radar border is perfectly
        white so we check for pixels > 220.  We return the *innermost* radius
        that exceeds the threshold — the inner edge of the border is the true
        geometric radius (anti-aliasing makes the border span 2–3 px outward).
        """
        h, w = gray.shape
        first_r    = r_hint
        first_frac = 0.0
        best_r     = r_hint
        best_frac  = 0.0
        for r_test in range(int(r_hint * 0.85), int(r_hint * 1.55) + 1):
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(mask, (cx, cy), r_test, 255, 1)  # 1-px ring
            pts = gray[mask == 255]
            if len(pts) == 0:
                continue
            frac = float((pts > WHITE_BORDER_BRIGHTNESS).sum()) / len(pts)
            if frac > best_frac:
                best_frac = frac
                best_r    = r_test
            if frac >= WHITE_BORDER_MIN_FRAC and first_frac == 0.0:
                first_r    = r_test
                first_frac = frac
        # Return innermost qualifying radius (with peak fraction for scoring)
        if first_frac > 0:
            return first_r, best_frac
        return best_r, best_frac

    @staticmethod
    def _count_interior_rings(
        gray: np.ndarray, cx: int, cy: int, r: int
    ) -> int:
        """Count concentric gray rings inside the circle.

        The radar has 4 evenly-spaced gray rings between the centre and the
        white outer border.  We sample ring brightness at every radius from
        10 % to 90 % of r and count peaks where the mean brightness exceeds
        INTERIOR_RING_BRIGHTNESS.
        """
        h, w = gray.shape
        # Sample mean brightness at each integer radius
        brightnesses = []
        r_start = max(3, int(r * 0.10))
        r_end   = int(r * 0.90)
        for r_test in range(r_start, r_end + 1):
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(mask, (cx, cy), r_test, 255, 1)
            pts = gray[mask == 255]
            if len(pts) == 0:
                brightnesses.append(0.0)
                continue
            brightnesses.append(float(pts.mean()))

        # Count peaks: a radius is a peak if brighter than its neighbours
        # and above the gray ring threshold.
        count = 0
        for i in range(1, len(brightnesses) - 1):
            if (brightnesses[i] > INTERIOR_RING_BRIGHTNESS
                    and brightnesses[i] > brightnesses[i - 1]
                    and brightnesses[i] > brightnesses[i + 1]):
                count += 1
        return count

    def _set_circle(self, circle: tuple[int, int, int], *, persist: bool = True):
        cx, cy, r = circle
        old_circle = self._circle
        self._circle = (cx, cy, r)
        self._scale  = r / BASE_RADAR_RADIUS_PX

        # Linear fit: 11px at scale=1.0, 24px at scale=2.0
        font_size = max(8, round(-2 + 12.87 * self._scale))
        if font_size != self._font_size:
            self._font_size = font_size
            self._templates = None  # invalidate cache
            self._multi_templates = None

        if old_circle != self._circle:
            # ROI offsets / hue / template size are tied to the detected circle.
            self._runtime_calibration = None

        log.info(
            "Radar circle set: cx=%d cy=%d r=%d scale=%.2f font_size=%d",
            cx, cy, r, self._scale, self._font_size,
        )

        if persist:
            self._persist_circle()

    def _persist_circle(self) -> None:
        """Save the current circle to config so it survives restarts."""
        if self._circle is None:
            return
        try:
            self._config.radar_last_circle = list(self._circle)
            from ..core.config import save_config
            save_config(self._config, self._config_path)
        except Exception as e:
            log.debug("Failed to persist radar circle: %s", e)

    def _load_radar_digit_stpk(self) -> None:
        """Load radar digit templates from STPK into size-indexed bins."""
        if not _STPK_AVAILABLE:
            return
        stpk_name = getattr(self._config, "radar_digit_stpk", RADAR_DIGIT_STPK_DEFAULT)
        stpk_path = STPK_DIR / stpk_name
        if not stpk_path.exists():
            log.info("Radar digit STPK not found: %s", stpk_path)
            return
        try:
            header, entries = _read_stpk(stpk_path)
            self._stpk_grid_w = int(header.get("grid_w", 0))
            self._stpk_grid_h = int(header.get("grid_h", 0))
            default_size = int(header.get("font_size", 0) or 0)
            size_map: dict[int, dict[str, np.ndarray]] = {}
            for entry in entries:
                raw_text = str(entry.get("text", "")).strip()
                parsed = self._parse_radar_stpk_text(raw_text, default_size)
                if parsed is None:
                    continue
                size, ch = parsed
                grid = entry.get("grid")
                if grid is None:
                    continue
                bin_grid = np.where(grid > 0, np.uint8(15), np.uint8(0))
                size_map.setdefault(size, {})[ch] = bin_grid

            # Keep only complete 0-9 sets to avoid partial calibration states.
            valid: dict[int, dict[str, np.ndarray]] = {}
            for size, tmpls in size_map.items():
                if all(d in tmpls for d in "0123456789"):
                    valid[size] = tmpls

            self._stpk_templates_by_size = valid
            self._stpk_sizes = sorted(valid.keys())
            self._stpk_missing_logged = False
            log.info(
                "Radar digit STPK loaded: %d sizes (%dx%d grid) from %s",
                len(self._stpk_sizes),
                self._stpk_grid_w,
                self._stpk_grid_h,
                stpk_name,
            )
        except Exception as e:
            log.warning("Failed to load radar digit STPK %s: %s", stpk_path, e)

    @staticmethod
    def _parse_radar_stpk_text(text: str, default_size: int) -> tuple[int, str] | None:
        """Parse STPK entry text into (size, digit)."""
        if len(text) == 1 and text.isdigit():
            size = max(8, int(default_size) if default_size > 0 else 22)
            return size, text

        for sep in ("|", ":", "@"):
            if sep not in text:
                continue
            left, right = text.split(sep, 1)
            left = left.strip()
            right = right.strip()
            if left.isdigit() and len(right) == 1 and right.isdigit():
                return max(8, int(left)), right
            if right.isdigit() and len(left) == 1 and left.isdigit():
                return max(8, int(right)), left
        return None

    # ------------------------------------------------------------------
    # Coordinate reading
    # ------------------------------------------------------------------

    def _read_coordinates(
        self, frame: np.ndarray
    ) -> tuple[int, int, float] | None:
        """Extract and OCR Lon + Lat rows. Returns (lon, lat, conf) or None."""
        if self._circle is None:
            return None
        if cv2 is None:
            return None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        bgr = frame if frame.ndim == 3 else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        base = self._compute_base_rois(gray)
        if base is None:
            return None

        # Cache per-frame row preprocessing (2x resize + CLAHE + binarize)
        # across calibration/evaluation passes.
        prep_cache: dict[tuple, dict] = {}

        if self._runtime_calibration is None:
            self._calibrate_once(gray, bgr, base, prep_cache=prep_cache)
        if self._runtime_calibration is None:
            return None

        # Runtime fast-path: use cheap scoring first; full scoring only on rescue path.
        read = self._evaluate_calibration(
            gray, bgr, base, self._runtime_calibration, fast=True, prep_cache=prep_cache,
        )
        if read is None:
            read = self._evaluate_calibration(
                gray, bgr, base, self._runtime_calibration, fast=False, prep_cache=prep_cache,
            )
        if read is None:
            return None

        if read["min_digit_conf"] < RADAR_DIGIT_CONFIDENCE_TARGET:
            changed = self._adjust_runtime_calibration(
                gray, bgr, base, read, prep_cache=prep_cache,
            )
            if changed:
                read2 = self._evaluate_calibration(
                    gray, bgr, base, self._runtime_calibration, fast=True, prep_cache=prep_cache,
                )
                if read2 is not None and read2["conf"] >= read["conf"]:
                    read = read2

        if read["conf"] < CONF_FAIL_THRESHOLD:
            # Last chance before failing the tick: run full scoring once.
            read_full = self._evaluate_calibration(
                gray, bgr, base, self._runtime_calibration, fast=False, prep_cache=prep_cache,
            )
            if read_full is not None and read_full["conf"] >= read["conf"]:
                read = read_full

        if read["conf"] < CONF_FAIL_THRESHOLD:
            return None
        return read["lon"], read["lat"], read["conf"]

    def _compute_base_rois(self, gray: np.ndarray) -> dict | None:
        """Compute the uncalibrated ROI geometry from the cached circle."""
        h, w = gray.shape
        cx, cy, r = self._circle
        scale = r / BASE_RADAR_RADIUS_PX
        left_extra = max(1, round(RADAR_TEXT_EXTRA_LEFT_PX * scale))
        right_extra = max(1, round(RADAR_TEXT_EXTRA_RIGHT_PX * scale))
        row_pad = max(1, round(RADAR_TEXT_EXTRA_ROW_PAD_PX * scale))
        row_h = max(5, round(TEXT_HEIGHT_RATIO * r) + row_pad * 2)
        x_nudge = round(-1 * (scale - 1))  # 0 at 100 %, -1 at 200 %
        left_nudge = RADAR_TEXT_X_LEFT_NUDGE_PX if scale <= RADAR_TEXT_LEFT_NUDGE_MAX_SCALE else 0
        text_left = max(0, cx + round(TEXT_LEFT_RATIO * r) + x_nudge - left_nudge - left_extra)
        text_right = min(
            w,
            cx + round(TEXT_LEFT_RATIO * r) + x_nudge
            + round(TEXT_WIDTH_RATIO * r) + round(4 * (scale - 1)) + 2 + right_extra,
        )
        lon_top = max(0, cy + round(TEXT_LON_OFFSET_RATIO * r) - row_pad)
        lat_top = max(0, cy + round((TEXT_LON_OFFSET_RATIO + TEXT_STRIDE_RATIO) * r) - row_pad)
        if text_right <= text_left:
            return None
        return {
            "h": h,
            "w": w,
            "text_left": text_left,
            "text_right": text_right,
            "row_h": row_h,
            "lon_top": lon_top,
            "lat_top": lat_top,
        }

    def _build_row_regions(self, gray: np.ndarray, bgr: np.ndarray, base: dict, params: dict) -> dict | None:
        """Build lon/lat row regions using calibrated offsets."""
        h = base["h"]
        w = base["w"]
        xl = int(base["text_left"] + params["x_offset"])
        xr = int(base["text_right"] + params["x_offset"])
        if xr <= xl:
            return None
        xl = max(0, xl)
        xr = min(w, xr)
        if xr <= xl:
            return None

        row_h = int(base["row_h"])
        lon_top = max(0, int(base["lon_top"] + params["y_lon_offset"]))
        lat_top = max(0, int(base["lat_top"] + params["y_lat_offset"]))
        lon_bot = min(h, lon_top + row_h)
        lat_bot = min(h, lat_top + row_h)
        if lon_bot <= lon_top or lat_bot <= lat_top:
            return None

        lon_gray = gray[lon_top:lon_bot, xl:xr]
        lat_gray = gray[lat_top:lat_bot, xl:xr]
        lon_bgr = bgr[lon_top:lon_bot, xl:xr]
        lat_bgr = bgr[lat_top:lat_bot, xl:xr]
        if lon_gray.size == 0 or lat_gray.size == 0:
            return None
        return {
            "lon_gray": lon_gray,
            "lat_gray": lat_gray,
            "lon_bgr": lon_bgr,
            "lat_bgr": lat_bgr,
            "xl": xl,
            "xr": xr,
            "lon_top": lon_top,
            "lon_bot": lon_bot,
            "lat_top": lat_top,
            "lat_bot": lat_bot,
        }

    def _calibrate_once(
        self,
        gray: np.ndarray,
        bgr: np.ndarray,
        base: dict,
        *,
        prep_cache: dict[tuple, dict] | None = None,
    ) -> None:
        """One-time calibration of template size, offsets, stride tweak, and hue."""
        if not self._stpk_sizes:
            if not self._stpk_missing_logged:
                log.warning("Radar calibration skipped: no radar digit STPK templates loaded")
                self._stpk_missing_logged = True
            self._runtime_calibration = None
            return
        if prep_cache is None:
            prep_cache = {}

        predicted_size = max(8, int(round(self._font_size * RADAR_UPSCALE_FACTOR)))
        default = {
            "template_size": self._get_candidate_sizes(predicted_size, max_count=1)[0],
            "x_offset": 0,
            "y_lon_offset": 0,
            "y_lat_offset": 0,
            "stride_tweak_px": 0,
            "hue_threshold": RADAR_DEFAULT_HUE_THRESHOLD,
        }

        best_params = dict(default)
        best_eval = self._evaluate_calibration(
            gray, bgr, base, best_params, fast=True, prep_cache=prep_cache,
        )

        # Stage 1: choose template size near predicted.
        for size in self._get_candidate_sizes(predicted_size, max_count=9):
            params = dict(default)
            params["template_size"] = size
            ev = self._evaluate_calibration(
                gray, bgr, base, params, fast=True, prep_cache=prep_cache,
            )
            if ev is None:
                continue
            if best_eval is None or ev["conf"] > best_eval["conf"]:
                best_eval = ev
                best_params = params

        # Stage 2: offset/stride calibration (full offset sweep).
        for x_off in RADAR_CALIBRATION_OFFSETS:
            for y_lon in RADAR_CALIBRATION_OFFSETS:
                for y_lat in RADAR_CALIBRATION_OFFSETS:
                    for stride_tweak in RADAR_CALIBRATION_OFFSETS:
                        params = dict(best_params)
                        params["x_offset"] = x_off
                        params["y_lon_offset"] = y_lon
                        params["y_lat_offset"] = y_lat
                        params["stride_tweak_px"] = stride_tweak
                        ev = self._evaluate_calibration(
                            gray, bgr, base, params, fast=True, prep_cache=prep_cache,
                        )
                        if ev is None:
                            continue
                        if best_eval is None or ev["conf"] > best_eval["conf"]:
                            best_eval = ev
                            best_params = params

        # Stage 3: hue calibration starts at 10 and adapts downward when needed.
        regions = self._build_row_regions(gray, bgr, base, best_params)
        bright_scene = False
        if regions is not None:
            bright_scene = (
                float(regions["lon_gray"].mean()) > 128
                or float(regions["lat_gray"].mean()) > 128
            )
        if bright_scene:
            for hue in RADAR_CALIBRATION_HUES:
                params = dict(best_params)
                params["hue_threshold"] = hue
                ev = self._evaluate_calibration(
                    gray, bgr, base, params, fast=True, prep_cache=prep_cache,
                )
                if ev is None:
                    continue
                if best_eval is None or ev["conf"] > best_eval["conf"]:
                    best_eval = ev
                    best_params = params

        best_eval = self._evaluate_calibration(
            gray, bgr, base, best_params, fast=False, prep_cache=prep_cache,
        )
        self._runtime_calibration = best_params if best_eval is not None else None
        log.info(
            "Radar calibration: size=%s x=%d ylon=%d ylat=%d stride=%d hue=%d conf=%s",
            best_params["template_size"],
            best_params["x_offset"],
            best_params["y_lon_offset"],
            best_params["y_lat_offset"],
            best_params["stride_tweak_px"],
            best_params["hue_threshold"],
            f"{best_eval['conf']:.3f}" if best_eval is not None else "n/a",
        )

    def _adjust_runtime_calibration(
        self,
        gray: np.ndarray,
        bgr: np.ndarray,
        base: dict,
        read: dict,
        *,
        prep_cache: dict[tuple, dict] | None = None,
    ) -> bool:
        """When per-digit confidence drops, refine offsets/hue around current values.

        Template size and geometry offsets stay locked after first calibration
        (radar scale/position are stable). Runtime adjustment only sweeps hue.
        """
        if self._runtime_calibration is None:
            return False
        if prep_cache is None:
            prep_cache = {}
        current = dict(self._runtime_calibration)
        best_params = dict(current)
        best_eval = read

        conf_now = float(read.get("conf", 1.0)) if read is not None else 1.0
        min_digit_now = float(read.get("min_digit_conf", 1.0)) if read is not None else 1.0
        hue_sweep_needed = (
            min_digit_now < RADAR_HUE_ADJUST_MIN_DIGIT_CONF
            or conf_now < RADAR_HUE_ADJUST_MIN_OVERALL_CONF
        )
        if not hue_sweep_needed:
            return False

        params = dict(current)
        max_hue = int(current.get("hue_threshold", RADAR_DEFAULT_HUE_THRESHOLD))
        for hue in range(max_hue, RADAR_HUE_MIN_THRESHOLD - 1, -1):
            params["hue_threshold"] = hue
            ev = self._evaluate_calibration(
                gray, bgr, base, params, fast=True, prep_cache=prep_cache,
            )
            if ev is None:
                continue
            if (
                best_eval is None
                or ev["conf"] > best_eval["conf"]
                or (
                    abs(ev["conf"] - best_eval["conf"]) < 1e-6
                    and ev["min_digit_conf"] > best_eval["min_digit_conf"]
                )
            ):
                best_eval = ev
                best_params = dict(params)

        final_eval = self._evaluate_calibration(
            gray, bgr, base, best_params, fast=False, prep_cache=prep_cache,
        )
        if final_eval is not None and final_eval["conf"] >= read["conf"]:
            self._runtime_calibration = best_params
            return best_params != current
        return False

    def _evaluate_calibration(
        self,
        gray: np.ndarray,
        bgr: np.ndarray,
        base: dict,
        params: dict,
        *,
        fast: bool = False,
        prep_cache: dict[tuple, dict] | None = None,
    ) -> dict | None:
        """Run lon+lat OCR for a given parameter set."""
        regions = self._build_row_regions(gray, bgr, base, params)
        if regions is None:
            return None

        stride_2x = DIGIT_STRIDE_RATIO * self._circle[2] * RADAR_UPSCALE_FACTOR
        stride_2x += float(params.get("stride_tweak_px", 0))
        if stride_2x <= 0:
            return None

        hue_threshold = int(params["hue_threshold"])
        template_size = int(params["template_size"])
        lon_cache_key = (
            "lon", regions["xl"], regions["xr"], regions["lon_top"], regions["lon_bot"], hue_threshold,
        )
        lat_cache_key = (
            "lat", regions["xl"], regions["xr"], regions["lat_top"], regions["lat_bot"], hue_threshold,
        )

        lon = self._ocr_row(
            regions["lon_gray"],
            regions["lon_bgr"],
            expected_stride_2x=stride_2x,
            hue_threshold=hue_threshold,
            template_size=template_size,
            fast=fast,
            prep_cache=prep_cache,
            prep_cache_key=lon_cache_key,
        )
        lat = self._ocr_row(
            regions["lat_gray"],
            regions["lat_bgr"],
            expected_stride_2x=stride_2x,
            hue_threshold=hue_threshold,
            template_size=template_size,
            fast=fast,
            prep_cache=prep_cache,
            prep_cache_key=lat_cache_key,
        )
        if lon is None or lat is None:
            return None

        lon_val, lon_conf, lon_min, lon_clear = lon
        lat_val, lat_conf, lat_min, lat_clear = lat
        conf = float((lon_conf * lat_conf) ** 0.5)
        return {
            "lon": lon_val,
            "lat": lat_val,
            "conf": conf,
            "min_digit_conf": min(lon_min, lat_min),
            "clear_ratio": float((lon_clear + lat_clear) / 2.0),
        }

    def _ocr_row(
        self,
        roi_gray: np.ndarray,
        roi_bgr: np.ndarray,
        *,
        expected_stride_2x: float,
        hue_threshold: int,
        template_size: int,
        fast: bool = False,
        prep_cache: dict[tuple, dict] | None = None,
        prep_cache_key: tuple | None = None,
    ) -> tuple[int, float, float, float] | None:
        """OCR one 5-digit coordinate row using the calibrated 2x pipeline."""
        bright_count = int((roi_gray > 200).sum())
        min_bright = roi_gray.shape[0] * 3
        if bright_count < min_bright:
            return None

        prep = (
            prep_cache.get(prep_cache_key)
            if (prep_cache is not None and prep_cache_key is not None)
            else None
        )
        if prep is None:
            prep = self._prepare_row_intensity(roi_gray, roi_bgr, hue_threshold)
            if prep is not None and prep_cache is not None and prep_cache_key is not None:
                prep_cache[prep_cache_key] = prep
        if prep is None:
            return None

        template_sets = self._resolve_template_sets(template_size)
        if not template_sets:
            return None
        min_blob_w, max_blob_w = self._estimate_digit_width_range(template_sets, expected_stride_2x)

        intensity_bin = prep["intensity_bin"]
        text_top = prep["text_top"]
        text_h = prep["text_h"]
        text_top, text_h = self._refine_text_band(
            intensity_bin, text_top, text_h, min_blob_w=min_blob_w,
        )
        text_region = intensity_bin[text_top:text_top + text_h, :]
        col_profile = text_region.sum(axis=0).astype(np.float32)
        blobs = self._find_digit_splits(
            text_region, col_profile, RADAR_EXPECTED_DIGITS, expected_stride_2x,
            min_blob_w=min_blob_w, max_blob_w=max_blob_w,
        )
        if len(blobs) != RADAR_EXPECTED_DIGITS:
            return None

        chars: list[str] = []
        scores: list[float] = []
        clear_flags: list[bool] = []
        for blob_x0, blob_x1 in blobs:
            blob_x0, blob_x1 = self._tighten_blob_to_component(
                intensity_bin, text_top, text_h, blob_x0, blob_x1, max_w_hint=max_blob_w,
            )
            # Tighten blob X bounds to actual local content to avoid trailing noise tails.
            local = intensity_bin[text_top:text_top + text_h, blob_x0:blob_x1 + 1]
            if local.size > 0:
                cols = np.where(np.any(local > 0, axis=0))[0]
                if len(cols) > 0:
                    blob_x0 = blob_x0 + int(cols[0])
                    blob_x1 = blob_x0 + int(cols[-1] - cols[0])

            score_result = self._score_digit_blob(
                intensity_bin, text_top, text_h, blob_x0, blob_x1, template_sets, fast=fast,
            )
            if score_result is None:
                return None

            best_ch = score_result["best_ch"]
            best_s = score_result["best_score"]
            all_scores = score_result["all_scores"]
            sorted_scores = sorted(all_scores.values(), reverse=True)
            raw_best = float(sorted_scores[0]) if sorted_scores else -999.0
            raw_second = float(sorted_scores[1]) if len(sorted_scores) > 1 else -999.0
            margin = raw_best - raw_second
            disamb_applied = False

            if not fast:
                natural_x0 = max(0, blob_x0)
                natural_x1 = min(intensity_bin.shape[1] - 1, blob_x1)
                natural_w = max(1, natural_x1 - natural_x0 + 1)
                base_gw = max(self._stpk_grid_w, self._grid_w, natural_w)
                base_gh = max(self._stpk_grid_h, self._grid_h, text_h)
                obs_base = self._normalize_blob(
                    intensity_bin, natural_x0, natural_x1, text_top, text_h, base_gw, base_gh,
                )
                if obs_base.any():
                    old_ch = best_ch
                    best_ch = self._disambiguate_digit(obs_base, best_ch, best_s, all_scores)
                    disamb_applied = best_ch != old_ch
                    best_s = all_scores.get(best_ch, best_s)

            clear_digit = disamb_applied or (margin >= RADAR_SECOND_BEST_CLEAR_MARGIN)
            eff_s = max(0.0, float(best_s))
            if eff_s <= 0.0 and clear_digit:
                eff_s = max(RADAR_GATED_DIGIT_SCORE_FLOOR, margin)

            chars.append(best_ch)
            scores.append(eff_s)
            clear_flags.append(clear_digit)

        if any(ch == "?" for ch in chars):
            return None
        if any(s <= 0.0 for s in scores):
            return None

        text = "".join(chars)
        try:
            value = int(text)
        except ValueError:
            return None
        conf = float(np.prod(scores) ** (1.0 / len(scores)))
        min_digit = float(min(scores))
        clear_ratio = float(sum(1 for flag in clear_flags if flag) / len(clear_flags))
        return value, conf, min_digit, clear_ratio

    def _prepare_row_intensity(self, roi_gray: np.ndarray, roi_bgr: np.ndarray, hue_threshold: int) -> dict | None:
        """2x upscale + optional hue filtering + binarized 4-bit intensity."""
        if RADAR_UPSCALE_INTERP is None:
            return None
        roi_2x = cv2.resize(
            roi_gray,
            (roi_gray.shape[1] * RADAR_UPSCALE_FACTOR, roi_gray.shape[0] * RADAR_UPSCALE_FACTOR),
            interpolation=RADAR_UPSCALE_INTERP,
        )
        shadow_mode = float(roi_2x.mean()) > 128

        filtered = roi_2x
        if roi_bgr is not None and roi_bgr.size > 0:
            roi_bgr_2x = cv2.resize(
                roi_bgr,
                (roi_bgr.shape[1] * RADAR_UPSCALE_FACTOR, roi_bgr.shape[0] * RADAR_UPSCALE_FACTOR),
                interpolation=RADAR_UPSCALE_INTERP,
            )
            ch_max = roi_bgr_2x.max(axis=2).astype(np.int16)
            ch_min = roi_bgr_2x.min(axis=2).astype(np.int16)
            spread = (ch_max - ch_min).astype(np.uint8)
            filtered_candidate = roi_2x.copy()
            filtered_candidate[spread > int(hue_threshold)] = 0
            if shadow_mode:
                filtered = filtered_candidate
            else:
                # Keep hue filtering on non-shadow rows only when enough signal survives.
                base_nz = int(np.count_nonzero(roi_2x >= RADAR_TEXT_BRIGHTNESS_THRESHOLD))
                filt_nz = int(np.count_nonzero(filtered_candidate >= RADAR_TEXT_BRIGHTNESS_THRESHOLD))
                min_keep = max(24, int(base_nz * RADAR_HUE_FILTER_MIN_KEEP_RATIO))
                filtered = filtered_candidate if filt_nz >= min_keep else roi_2x

        enhanced = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4)).apply(filtered)
        intensity = enhanced.copy()
        intensity[intensity < RADAR_TEXT_BRIGHTNESS_THRESHOLD] = 0
        if intensity.max() > 0:
            intensity = cv2.normalize(
                intensity, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U,
            )
        intensity[intensity < RADAR_TEXT_BRIGHTNESS_THRESHOLD] = 0

        intensity_4bit = np.minimum(
            intensity.astype(np.float32) / 16, 15,
        ).astype(np.uint8)
        base_bin = np.where(intensity_4bit > 0, np.uint8(15), np.uint8(0))
        strict_threshold = (
            RADAR_BINARIZE_THRESHOLD_BRIGHT if shadow_mode else RADAR_BINARIZE_THRESHOLD
        )
        strict_bin = np.where(intensity >= strict_threshold, np.uint8(15), np.uint8(0))
        # Keep strict thresholding only when it preserves enough foreground;
        # otherwise fall back to the legacy binarization to avoid dropouts.
        base_nz = int(np.count_nonzero(base_bin))
        strict_nz = int(np.count_nonzero(strict_bin))
        min_keep = max(24, int(base_nz * RADAR_STRICT_BIN_MIN_KEEP_RATIO))
        intensity_bin = strict_bin if strict_nz >= min_keep else base_bin

        row_bright_counts = np.sum(intensity > 200, axis=1)
        min_row_bright = max(3, intensity.shape[1] // 8)
        text_rows = row_bright_counts >= min_row_bright
        if not text_rows.any():
            return None
        text_top = int(np.argmax(text_rows))
        text_bot = int(len(text_rows) - 1 - np.argmax(text_rows[::-1]))
        text_h = text_bot - text_top + 1
        if text_h < 3:
            return None
        return {
            "intensity_bin": intensity_bin,
            "text_top": text_top,
            "text_h": text_h,
        }

    @staticmethod
    def _find_component_boxes(
        text_region: np.ndarray,
        *,
        min_w: int,
        min_h: int,
    ) -> list[tuple[int, int, int, int, int]]:
        """Find non-noise connected components as (x0,x1,y0,y1,area) in local coords."""
        if cv2 is None or text_region.size == 0:
            return []
        mask = (text_region > 0).astype(np.uint8)
        if int(np.count_nonzero(mask)) == 0:
            return []

        n_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        boxes: list[tuple[int, int, int, int, int]] = []
        for idx in range(1, int(n_labels)):
            x = int(stats[idx, cv2.CC_STAT_LEFT])
            y = int(stats[idx, cv2.CC_STAT_TOP])
            w = int(stats[idx, cv2.CC_STAT_WIDTH])
            h = int(stats[idx, cv2.CC_STAT_HEIGHT])
            area = int(stats[idx, cv2.CC_STAT_AREA])
            if w < min_w or h < min_h:
                continue
            # Skip sparse noise components that barely fill their bbox.
            if area < max(4, int(w * h * 0.18)):
                continue
            boxes.append((x, x + w - 1, y, y + h - 1, area))
        boxes.sort(key=lambda b: (b[0], b[2]))
        return boxes

    @staticmethod
    def _refine_text_band(
        intensity_bin: np.ndarray,
        text_top: int,
        text_h: int,
        *,
        min_blob_w: int,
    ) -> tuple[int, int]:
        """Refine row band to dominant consecutive shape in Y, suppressing noise rows."""
        if text_h < 3:
            return text_top, text_h
        text_bot = min(intensity_bin.shape[0], text_top + text_h)
        region = intensity_bin[text_top:text_bot, :]
        if region.size == 0:
            return text_top, text_h

        min_h = max(3, int(round(region.shape[0] * 0.28)))
        comp_boxes = RadarDetector._find_component_boxes(
            region,
            min_w=max(2, min_blob_w // 2),
            min_h=min_h,
        )
        if comp_boxes:
            # Anchor to the tallest/highest-area component, then include overlapping peers.
            anchor = max(comp_boxes, key=lambda b: ((b[3] - b[2] + 1), b[4]))
            ay0, ay1 = anchor[2], anchor[3]
            cluster = []
            for b in comp_boxes:
                by0, by1 = b[2], b[3]
                overlap = min(ay1, by1) - max(ay0, by0) + 1
                if overlap >= 0:
                    cluster.append(b)
            if not cluster:
                cluster = [anchor]
            y0 = min(b[2] for b in cluster)
            y1 = max(b[3] for b in cluster)
            pad = RADAR_ROW_KEEP_PAD_PX
            y0 = max(0, y0 - pad)
            y1 = min(region.shape[0] - 1, y1 + pad)
            new_h = y1 - y0 + 1
            if new_h >= 3:
                return text_top + y0, new_h

        # Density fallback: keep largest consecutive run of dense rows.
        row_density = np.sum(region > 0, axis=1)
        peak = int(row_density.max()) if row_density.size else 0
        if peak <= 0:
            return text_top, text_h
        min_row = max(2, int(round(min_blob_w * 0.35)))
        keep_thr = max(min_row, int(round(peak * RADAR_ROW_DENSITY_KEEP_RATIO)))
        dense = row_density >= keep_thr
        if not dense.any():
            return text_top, text_h
        best_s = -1
        best_e = -1
        start = -1
        for i in range(len(dense) + 1):
            on = i < len(dense) and bool(dense[i])
            if on and start < 0:
                start = i
            elif not on and start >= 0:
                end = i - 1
                if (best_s < 0) or (end - start > best_e - best_s):
                    best_s, best_e = start, end
                start = -1
        if best_s < 0:
            return text_top, text_h
        pad = RADAR_ROW_KEEP_PAD_PX
        y0 = max(0, best_s - pad)
        y1 = min(region.shape[0] - 1, best_e + pad)
        new_h = y1 - y0 + 1
        if new_h < 3:
            return text_top, text_h
        return text_top + y0, new_h

    @staticmethod
    def _trim_blob_bounds(
        col_density: np.ndarray,
        col_profile: np.ndarray,
        x0: int,
        x1: int,
        *,
        min_w: int,
        max_w: int,
    ) -> tuple[int, int]:
        """Trim noisy edges and clip too-wide blobs to the densest sub-window."""
        if x1 <= x0:
            return x0, x1
        total_w = len(col_density)
        x0 = max(0, min(total_w - 1, int(x0)))
        x1 = max(0, min(total_w - 1, int(x1)))
        if x1 <= x0:
            return x0, x1

        local = col_density[x0:x1 + 1]
        peak = int(local.max()) if local.size else 0
        keep_thr = max(1, int(round(peak * RADAR_BLOB_EDGE_KEEP_RATIO)))

        # Edge trim while preserving minimum plausible digit width.
        while x1 - x0 + 1 > min_w and col_density[x0] < keep_thr:
            x0 += 1
        while x1 - x0 + 1 > min_w and col_density[x1] < keep_thr:
            x1 -= 1

        width = x1 - x0 + 1
        if width > max_w:
            prof = col_profile[x0:x1 + 1]
            if len(prof) > max_w:
                kernel = np.ones(max_w, dtype=np.float32)
                sums = np.convolve(prof.astype(np.float32), kernel, mode="valid")
                off = int(np.argmax(sums))
                x0 = x0 + off
                x1 = x0 + max_w - 1
        return x0, x1

    @staticmethod
    def _tighten_blob_to_component(
        intensity_bin: np.ndarray,
        text_top: int,
        text_h: int,
        x0: int,
        x1: int,
        *,
        max_w_hint: int | None = None,
    ) -> tuple[int, int]:
        """Tighten blob bounds to the dominant connected component in the blob window."""
        if cv2 is None:
            return x0, x1
        h, w = intensity_bin.shape
        x0 = max(0, min(w - 1, int(x0)))
        x1 = max(0, min(w - 1, int(x1)))
        if x1 <= x0:
            return x0, x1
        y0 = max(0, int(text_top))
        y1 = min(h, int(text_top + text_h))
        if y1 <= y0:
            return x0, x1
        region = intensity_bin[y0:y1, x0:x1 + 1]
        if region.size == 0:
            return x0, x1
        mask = (region > 0).astype(np.uint8)
        if int(np.count_nonzero(mask)) == 0:
            return x0, x1
        n_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if int(n_labels) <= 1:
            return x0, x1

        best = None
        best_area = -1
        min_h = max(3, int(round(region.shape[0] * 0.35)))
        def _pick(require_width_cap: bool) -> tuple | None:
            pick = None
            pick_area = -1
            for idx in range(1, int(n_labels)):
                bx = int(stats[idx, cv2.CC_STAT_LEFT])
                by = int(stats[idx, cv2.CC_STAT_TOP])
                bw = int(stats[idx, cv2.CC_STAT_WIDTH])
                bh = int(stats[idx, cv2.CC_STAT_HEIGHT])
                area = int(stats[idx, cv2.CC_STAT_AREA])
                if bw < 2 or bh < min_h:
                    continue
                if require_width_cap and max_w_hint is not None and bw > max_w_hint + 1:
                    continue
                if area > pick_area:
                    pick_area = area
                    pick = (bx, by, bw, bh)
            return pick

        best = _pick(require_width_cap=True)
        if best is None:
            best = _pick(require_width_cap=False)
        if best is None:
            return x0, x1
        bx, _by, bw, _bh = best
        tx0 = x0 + bx
        tx1 = tx0 + bw - 1
        return tx0, tx1

    @staticmethod
    def _estimate_digit_width_range(
        template_sets: list[tuple[dict[str, np.ndarray], int, int, int]],
        expected_stride: float,
    ) -> tuple[int, int]:
        """Estimate plausible blob width range from template '1' and full-width digits."""
        one_w, full_w = RadarDetector._estimate_nominal_digit_widths(template_sets)
        # Keep a small stride guard to avoid exploding widths when segmentation drifts.
        stride_max = max(3, int(round(expected_stride * 1.20)))
        min_w = max(2, int(round(one_w * 0.70)))
        max_w = max(min_w + 1, min(stride_max, int(round(full_w * 1.35))))
        return min_w, max_w

    @staticmethod
    def _estimate_nominal_digit_widths(
        template_sets: list[tuple[dict[str, np.ndarray], int, int, int]],
    ) -> tuple[int, int]:
        """Return (one_width, full_width) from active templates.

        The model assumes two practical width classes:
        - narrow: digit '1'
        - full: all other digits
        """
        widths: list[int] = []
        one_widths: list[int] = []
        full_widths: list[int] = []
        for templates, _gw, _gh, _size in template_sets:
            for ch in "0123456789":
                tmpl = templates.get(ch)
                if tmpl is None or tmpl.size == 0:
                    continue
                cols = np.where(np.any(tmpl > 0, axis=0))[0]
                if len(cols) == 0:
                    continue
                w = int(cols[-1] - cols[0] + 1)
                widths.append(w)
                if ch == "1":
                    one_widths.append(w)
                else:
                    full_widths.append(w)

        if not widths:
            return 3, 8

        if one_widths:
            one_w = int(round(float(np.median(one_widths))))
        else:
            one_w = max(2, int(round(min(widths) * 0.75)))
        if full_widths:
            full_w = int(round(float(np.median(full_widths))))
        else:
            full_w = max(one_w + 1, int(round(max(widths))))

        one_w = max(2, one_w)
        full_w = max(one_w + 1, full_w)
        return one_w, full_w

    @staticmethod
    def _find_column_blobs(col_has: np.ndarray) -> list[tuple[int, int]]:
        """Return contiguous x ranges where the text band has column content."""
        blobs: list[tuple[int, int]] = []
        start = -1
        for col in range(len(col_has) + 1):
            has = col < len(col_has) and bool(col_has[col])
            if has and start < 0:
                start = col
            elif not has and start >= 0:
                blobs.append((start, col - 1))
                start = -1
        return blobs

    @staticmethod
    def _pick_blob_run(
        blobs: list[tuple[int, int]],
        n_digits: int,
        expected_stride: float,
    ) -> list[tuple[int, int]]:
        """Pick the most stride-consistent run of n blobs from candidates."""
        if len(blobs) < n_digits:
            return []
        if len(blobs) == n_digits:
            return list(blobs)

        best_run: list[tuple[int, int]] = []
        best_score = float("inf")
        for start in range(0, len(blobs) - n_digits + 1):
            run = blobs[start:start + n_digits]
            centers = [(x0 + x1) * 0.5 for x0, x1 in run]
            spacing_err = 0.0
            overlap_penalty = 0.0
            for i in range(1, len(centers)):
                spacing_err += abs((centers[i] - centers[i - 1]) - expected_stride)
                prev_x0, prev_x1 = run[i - 1]
                cur_x0, cur_x1 = run[i]
                overlap = max(0, min(prev_x1, cur_x1) - max(prev_x0, cur_x0) + 1)
                if overlap > 0:
                    # Large overlaps are almost always duplicate/shifted candidates.
                    if overlap > max(1, int(round(expected_stride * 0.10))):
                        overlap_penalty += 1000.0
                    else:
                        overlap_penalty += overlap * 4.0
            widths = [(x1 - x0 + 1) for x0, x1 in run]
            width_spread = float(max(widths) - min(widths))
            score = spacing_err + width_spread * 0.2 + overlap_penalty * 3.0
            if score < best_score:
                best_score = score
                best_run = run
        return best_run

    @staticmethod
    def _track_blob_progression(
        candidates: list[tuple[int, int]],
        col_density: np.ndarray,
        col_profile: np.ndarray,
        *,
        content_start: int,
        n_digits: int,
        expected_stride: float,
        total_w: int,
        min_blob_w: int,
        max_blob_w: int,
        one_w: int,
        full_w: int,
    ) -> list[tuple[int, int]]:
        """Build a non-overlapping left-to-right blob track with stride progression."""
        if not candidates or n_digits < 1:
            return []
        cand = []
        for x0, x1 in candidates:
            w = x1 - x0 + 1
            mid = (x0 + x1) * 0.5
            cand.append((x0, x1, mid, w))
        cand.sort(key=lambda c: c[0])

        anchor_mid = float(content_start + max(0, full_w - 1) * 0.5)
        used: set[int] = set()
        out: list[tuple[int, int]] = []
        prev_end = -1
        one_cut = int(round((one_w + full_w) * 0.5))
        for i in range(n_digits):
            expected_mid = anchor_mid + i * expected_stride
            best_idx = -1
            best_err = float("inf")
            for idx, (x0, x1, mid, _w) in enumerate(cand):
                if idx in used:
                    continue
                if prev_end >= 0 and x0 <= prev_end:
                    continue
                err = abs(mid - expected_mid)
                if err <= expected_stride * 0.65 and err < best_err:
                    best_err = err
                    best_idx = idx

            if best_idx >= 0:
                used.add(best_idx)
                x0, x1, _mid, raw_w = cand[best_idx]
                target_w = one_w if raw_w <= one_cut else full_w
            else:
                target_w = full_w
                x0 = int(round(expected_mid - (target_w - 1) / 2.0))
                x1 = x0 + target_w - 1

            x0, x1 = RadarDetector._trim_blob_bounds(
                col_density, col_profile, x0, x1, min_w=min_blob_w, max_w=max_blob_w,
            )
            if prev_end >= 0 and x0 <= prev_end:
                shift = prev_end - x0 + 1
                x0 += shift
                x1 += shift

            # Keep width near the target class while respecting global min/max.
            cur_w = x1 - x0 + 1
            min_w = max(min_blob_w, target_w - 2)
            max_w = min(max_blob_w, target_w + 4)
            if cur_w < min_w:
                x1 = x0 + min_w - 1
            elif cur_w > max_w:
                x1 = x0 + max_w - 1

            x0 = max(0, min(total_w - 1, x0))
            x1 = max(0, min(total_w - 1, x1))
            if x1 < x0:
                return []
            out.append((x0, x1))
            prev_end = x1
        return out

    @staticmethod
    def _find_digit_splits(
        text_region: np.ndarray,
        col_profile: np.ndarray,
        n_digits: int,
        expected_stride: float,
        *,
        min_blob_w: int | None = None,
        max_blob_w: int | None = None,
        one_w: int | None = None,
        full_w: int | None = None,
    ) -> list[tuple[int, int]]:
        """Find digit bounds using consecutive X/Y shapes + valley fallback."""
        total_w = len(col_profile)
        if total_w == 0 or n_digits < 1 or expected_stride <= 0:
            return []
        peak = float(col_profile.max())
        if peak <= 0:
            return []
        min_start = peak * RADAR_CONTENT_START_RATIO
        significant = np.where(col_profile >= min_start)[0]
        if len(significant) == 0:
            return []
        content_start_seed = int(significant[0])

        min_col_density = max(2, int(round(text_region.shape[0] * RADAR_BLOB_MIN_COL_DENSITY_RATIO)))
        col_density = np.sum(text_region > 0, axis=0)
        raw_blobs = RadarDetector._find_column_blobs(col_density >= min_col_density)

        if min_blob_w is None:
            min_blob_w = max(2, int(round(expected_stride * RADAR_BLOB_MIN_WIDTH_RATIO)))
        if max_blob_w is None:
            max_blob_w = max(min_blob_w + 1, int(round(expected_stride * RADAR_BLOB_MAX_WIDTH_RATIO)))
        if one_w is None:
            one_w = min_blob_w
        if full_w is None:
            full_w = max(min_blob_w + 1, int(round((min_blob_w + max_blob_w) * 0.5)))

        # Add component-derived boxes (consecutive in both X and Y) as strong candidates.
        min_comp_h = max(3, int(round(text_region.shape[0] * 0.35)))
        comp_boxes = RadarDetector._find_component_boxes(
            text_region,
            min_w=max(2, min_blob_w // 2),
            min_h=min_comp_h,
        )
        comp_blobs = [(b[0], b[1]) for b in comp_boxes]

        candidates = raw_blobs + comp_blobs
        prefiltered: list[tuple[int, int]] = []
        for x0, x1 in candidates:
            tx0, tx1 = RadarDetector._trim_blob_bounds(
                col_density, col_profile, x0, x1, min_w=min_blob_w, max_w=max_blob_w,
            )
            if tx1 - tx0 + 1 >= max(2, min_blob_w):
                prefiltered.append((tx0, tx1))

        # Deduplicate near-identical candidates by overlap + density.
        dedup: list[tuple[int, int]] = []
        for x0, x1 in sorted(prefiltered, key=lambda b: (b[0], (b[1] - b[0] + 1))):
            cw = x1 - x0 + 1
            c_score = float(col_profile[x0:x1 + 1].sum() / max(1, cw))
            merged = False
            for i, (dx0, dx1) in enumerate(dedup):
                dw = dx1 - dx0 + 1
                inter = max(0, min(x1, dx1) - max(x0, dx0) + 1)
                if inter <= 0:
                    continue
                c_mid = (x0 + x1) * 0.5
                d_mid = (dx0 + dx1) * 0.5
                center_delta = abs(c_mid - d_mid)
                overlap_ratio = inter / float(max(1, min(cw, dw)))
                if overlap_ratio < 0.45 and center_delta > max(2.0, min_blob_w * 0.8):
                    continue
                d_score = float(col_profile[dx0:dx1 + 1].sum() / max(1, dw))
                if c_score > d_score:
                    dedup[i] = (x0, x1)
                merged = True
                break
            if not merged:
                dedup.append((x0, x1))

        valid_blobs = [
            (x0, x1)
            for x0, x1 in dedup
            if min_blob_w <= (x1 - x0 + 1) <= max_blob_w
        ]
        picked = RadarDetector._pick_blob_run(valid_blobs, n_digits, expected_stride)
        if picked:
            return [
                RadarDetector._trim_blob_bounds(
                    col_density, col_profile, x0, x1, min_w=min_blob_w, max_w=max_blob_w,
                )
                for x0, x1 in picked
            ]

        content_start = int(valid_blobs[0][0]) if valid_blobs else int(significant[0])
        projected_end = content_start + int(round((n_digits - 1) * expected_stride))
        if valid_blobs:
            # Prefer blob-driven tail to avoid trailing noise inflating the last digit width.
            content_end = int(valid_blobs[-1][1])
            min_needed = content_start + int(round((n_digits - 1) * expected_stride * 0.75))
            content_end = max(content_end, min(total_w - 1, min_needed))
        else:
            content_end = int(significant[-1])
            content_end = max(content_end, projected_end)
        content_end = min(total_w - 1, content_end)
        if content_end <= content_start:
            return []

        splits: list[int] = []
        search_radius = max(2, int(expected_stride * RADAR_VALLEY_SEARCH_RADIUS_RATIO))
        for i in range(1, n_digits):
            expected_x = content_start + int(round(i * expected_stride))
            lo = max(content_start + 1, expected_x - search_radius)
            hi = min(content_end, expected_x + search_radius + 1)
            if lo >= hi:
                splits.append(max(content_start + 1, min(content_end, expected_x)))
                continue
            window = col_profile[lo:hi]
            valley_idx = lo + int(np.argmin(window))
            splits.append(valley_idx)

        bounds: list[tuple[int, int]] = []
        prev = content_start
        for s in splits:
            bounds.append((prev, s - 1))
            prev = s
        bounds.append((prev, content_end))

        # Snap valley bounds to nearby size-valid blobs when possible.
        if valid_blobs:
            aligned: list[tuple[int, int]] = []
            used: set[int] = set()
            max_delta = expected_stride * RADAR_BLOB_ADVANCE_TOL_RATIO
            for x0, x1 in bounds:
                mid = (x0 + x1) * 0.5
                best_idx = -1
                best_delta = float("inf")
                for idx, (bx0, bx1) in enumerate(valid_blobs):
                    if idx in used:
                        continue
                    bmid = (bx0 + bx1) * 0.5
                    delta = abs(bmid - mid)
                    if delta <= max_delta and delta < best_delta:
                        best_delta = delta
                        best_idx = idx
                if best_idx >= 0:
                    used.add(best_idx)
                    aligned.append(valid_blobs[best_idx])
                else:
                    aligned.append((x0, x1))
            bounds = aligned

        out: list[tuple[int, int]] = []
        for x0, x1 in bounds:
            tx0, tx1 = RadarDetector._trim_blob_bounds(
                col_density, col_profile, int(x0), int(x1), min_w=min_blob_w, max_w=max_blob_w,
            )
            tx0 = max(0, min(total_w - 1, int(tx0)))
            tx1 = max(0, min(total_w - 1, int(tx1)))
            if tx1 < tx0:
                return []
            out.append((tx0, tx1))

        return out if len(out) == n_digits else []

    def _resolve_template_sets(self, size_hint: int) -> list[tuple[dict[str, np.ndarray], int, int, int]]:
        """Resolve active digit template sets from STPK only.

        The calibrated template size is treated as locked after first run.
        """
        if self._stpk_templates_by_size:
            # Locked size first.
            exact = self._stpk_templates_by_size.get(int(size_hint))
            if exact:
                return [(exact, self._stpk_grid_w, self._stpk_grid_h, int(size_hint))]

            # Fallback only if exact size is missing from STPK.
            nearest = self._get_candidate_sizes(size_hint, max_count=1)
            if nearest:
                size = int(nearest[0])
                t = self._stpk_templates_by_size.get(size)
                if t:
                    return [(t, self._stpk_grid_w, self._stpk_grid_h, size)]
        return []

    def _get_candidate_sizes(self, size_hint: int, max_count: int) -> list[int]:
        """Template-size candidates near a hint (STPK sizes preferred)."""
        if self._stpk_sizes:
            ordered = sorted(self._stpk_sizes, key=lambda s: (abs(s - size_hint), s))
            return ordered[:max_count]
        return []

    def _score_digit_blob(
        self,
        intensity_bin: np.ndarray,
        text_top: int,
        text_h: int,
        blob_x0: int,
        blob_x1: int,
        template_sets: list[tuple[dict[str, np.ndarray], int, int, int]],
        *,
        fast: bool = False,
    ) -> dict | None:
        """Score one digit blob with x-boundary sweep and multi-size templates."""
        roi_w = intensity_bin.shape[1]
        blob_x0 = max(0, blob_x0)
        blob_x1 = min(roi_w - 1, blob_x1)
        if blob_x1 <= blob_x0:
            return None

        best_pos_score = -999.0
        best_pos: dict | None = None
        # Cache template stacks per grid shape within this blob scoring call.
        template_stack_cache: dict[tuple[int, int, int], tuple[list[str], np.ndarray]] = {}

        def _score_at_bounds(tx0: int, tx1: int) -> dict | None:
            col_w = tx1 - tx0 + 1
            all_scores: dict[str, float] = {}

            for templates, s_gw, s_gh, _size in template_sets:
                gw = max(s_gw, col_w)
                gh = max(s_gh, text_h)
                obs = self._normalize_blob(
                    intensity_bin, tx0, tx1, text_top, text_h, gw, gh,
                )
                if not obs.any():
                    continue

                cache_key = (id(templates), gh, gw)
                cached = template_stack_cache.get(cache_key)
                if cached is None:
                    chars: list[str] = []
                    placed: list[np.ndarray] = []
                    for ch, tmpl in templates.items():
                        t = tmpl if tmpl.shape == (gh, gw) else self._place_in_grid(tmpl, gh, gw)
                        chars.append(ch)
                        placed.append(t)
                    if not placed:
                        continue
                    stack = np.stack(placed, axis=0)
                    cached = (chars, stack)
                    template_stack_cache[cache_key] = cached

                chars, stack = cached
                scores = self._score_grid_batch(obs, stack)
                for idx, ch in enumerate(chars):
                    s = float(scores[idx])
                    if ch not in all_scores or s > all_scores[ch]:
                        all_scores[ch] = s

            if not all_scores:
                return None
            best_ch = max(all_scores.items(), key=lambda x: x[1])[0]
            return {
                "x0": tx0,
                "x1": tx1,
                "all_scores": all_scores,
                "best_ch": best_ch,
                "best_score": all_scores[best_ch],
            }

        if fast:
            # Fast mode keeps width fixed and only shifts the whole blob slightly.
            for dx in RADAR_X_SWEEP_FAST_OFFSETS:
                tx0 = max(0, blob_x0 + dx)
                tx1 = min(roi_w - 1, blob_x1 + dx)
                if tx1 <= tx0:
                    continue
                pos = _score_at_bounds(tx0, tx1)
                if pos is None:
                    continue
                local_best = float(pos["best_score"])
                if local_best > best_pos_score:
                    best_pos_score = local_best
                    best_pos = pos
        else:
            for dx0 in RADAR_X_SWEEP_OFFSETS:
                for dx1 in RADAR_X_SWEEP_OFFSETS:
                    tx0 = max(0, blob_x0 + dx0)
                    tx1 = min(roi_w - 1, blob_x1 + dx1)
                    if tx1 <= tx0:
                        continue
                    pos = _score_at_bounds(tx0, tx1)
                    if pos is None:
                        continue
                    local_best = float(pos["best_score"])
                    if local_best > best_pos_score:
                        best_pos_score = local_best
                        best_pos = pos

        return best_pos

    # ------------------------------------------------------------------
    # Digit disambiguation (adapted from skill_disambiguation.py)
    # ------------------------------------------------------------------

    @staticmethod
    def _disambiguate_digit(
        grid: np.ndarray,
        best_ch: str,
        best_score: float,
        all_scores: dict[str, float],
    ) -> str:
        """Apply geometric tiebreakers for confusable digit pairs."""
        PAIRS = [
            ("0", "9", RadarDetector._disambiguate_0_9, 0.15, 0.05),
            ("0", "8", RadarDetector._disambiguate_0_8, 0.12, 0.12),
            ("3", "8", RadarDetector._disambiguate_3_8, 0.20, 0.20),
            ("3", "5", RadarDetector._disambiguate_3_5, 0.12, 0.12),
            ("5", "6", RadarDetector._disambiguate_5_6, 0.15, 0.15),
            ("6", "9", RadarDetector._disambiguate_6_9, 0.12, 0.12),
            ("0", "6", RadarDetector._disambiguate_0_6, 0.05, 0.05),
            ("6", "8", RadarDetector._disambiguate_6_8, 0.12, 0.12),
            ("2", "7", RadarDetector._disambiguate_2_7, 0.15, 0.15),
        ]
        for a, b, func, margin_a2b, margin_b2a in PAIRS:
            if best_ch == a:
                rival_score = all_scores.get(b, -999)
                if best_score - rival_score < margin_a2b:
                    result = func(grid)
                    if result is not None:
                        return result
            elif best_ch == b:
                rival_score = all_scores.get(a, -999)
                if best_score - rival_score < margin_b2a:
                    result = func(grid)
                    if result is not None:
                        return result
        return best_ch

    @staticmethod
    def _get_content_bounds(grid: np.ndarray):
        content_cols = np.any(grid > 0, axis=0)
        content_rows = np.any(grid > 0, axis=1)
        if not content_cols.any() or not content_rows.any():
            return None
        col_l = int(np.argmax(content_cols))
        col_r = int(len(content_cols) - 1 - np.argmax(content_cols[::-1]))
        row_t = int(np.argmax(content_rows))
        row_b = int(len(content_rows) - 1 - np.argmax(content_rows[::-1]))
        return col_l, col_r, row_t, row_b

    @staticmethod
    def _disambiguate_0_9(grid: np.ndarray) -> str | None:
        """'9' has a solid bridge row in its middle; '0' has a hollow center."""
        bounds = RadarDetector._get_content_bounds(grid)
        if bounds is None:
            return None
        col_l, col_r, row_t, row_b = bounds
        cw = col_r - col_l + 1
        ch = row_b - row_t + 1
        if cw < 3 or ch < 5:
            return None
        for r in range(row_t + ch // 3, row_t + 2 * ch // 3 + 1):
            row_px = grid[r, col_l:col_r + 1]
            if np.count_nonzero(row_px) >= 0.75 * len(row_px):
                return "9"
        return "0"

    @staticmethod
    def _disambiguate_0_8(grid: np.ndarray) -> str | None:
        """'8' has a stronger middle bridge than '0' (two closed loops)."""
        bounds = RadarDetector._get_content_bounds(grid)
        if bounds is None:
            return None
        col_l, col_r, row_t, row_b = bounds
        cw = col_r - col_l + 1
        ch = row_b - row_t + 1
        if cw < 3 or ch < 5:
            return None
        mid0 = row_t + ch // 2 - max(1, ch // 10)
        mid1 = row_t + ch // 2 + max(1, ch // 10)
        mid0 = max(row_t, mid0)
        mid1 = min(row_b, mid1)
        mid_band = grid[mid0:mid1 + 1, col_l:col_r + 1]
        mid_fill = float(np.count_nonzero(mid_band)) / max(1, mid_band.size)
        return "8" if mid_fill >= 0.42 else "0"

    @staticmethod
    def _disambiguate_3_8(grid: np.ndarray) -> str | None:
        """'8' has content on the upper-left (closed loop); '3' is open on the left.

        Checks the left 1/3 of the upper 1/3: '8' has filled pixels there
        (closed loop), while '3' is open on the left throughout.
        """
        bounds = RadarDetector._get_content_bounds(grid)
        if bounds is None:
            return None
        col_l, col_r, row_t, row_b = bounds
        cw = col_r - col_l + 1
        ch = row_b - row_t + 1
        if cw < 3 or ch < 5:
            return None
        upper_end = row_t + ch // 3
        left_cols = max(2, cw // 3)
        left_zone = grid[row_t:upper_end + 1, col_l:col_l + left_cols]
        return "8" if int(np.sum(left_zone)) > 0 else "3"

    @staticmethod
    def _disambiguate_3_5(grid: np.ndarray) -> str | None:
        """'5' keeps left-mid linkage; '3' stays mostly open on the left."""
        bounds = RadarDetector._get_content_bounds(grid)
        if bounds is None:
            return None
        col_l, col_r, row_t, row_b = bounds
        cw = col_r - col_l + 1
        ch = row_b - row_t + 1
        if cw < 3 or ch < 5:
            return None
        left_w = max(2, cw // 3)
        mid0 = row_t + ch // 3
        mid1 = row_t + 2 * ch // 3
        left_mid = grid[mid0:mid1 + 1, col_l:col_l + left_w]
        fill = float(np.count_nonzero(left_mid)) / max(1, left_mid.size)
        return "5" if fill >= 0.20 else "3"

    @staticmethod
    def _disambiguate_5_6(grid: np.ndarray) -> str | None:
        """'5' has a wide flat top bar; '6' has a narrow curved top.

        Checks the top few rows: '5' has rows spanning >70% of the digit
        width (flat bar), while '6' curves and covers less width at the top.
        """
        bounds = RadarDetector._get_content_bounds(grid)
        if bounds is None:
            return None
        col_l, col_r, row_t, row_b = bounds
        cw = col_r - col_l + 1
        ch = row_b - row_t + 1
        if cw < 3 or ch < 4:
            return None

        # Check top 1/4 of content: count rows with wide content (>70% width)
        check_rows = max(2, ch // 4)
        wide_count = 0
        for r in range(row_t, row_t + check_rows):
            row_px = grid[r, col_l:col_r + 1]
            filled = np.count_nonzero(row_px)
            if filled >= 0.70 * cw:
                wide_count += 1

        # '5' has most top rows filled wide (flat bar); '6' has few or none
        return "5" if wide_count >= check_rows // 2 + 1 else "6"

    @staticmethod
    def _disambiguate_6_9(grid: np.ndarray) -> str | None:
        """'6' has lower-left connection; '9' has upper-right connection."""
        bounds = RadarDetector._get_content_bounds(grid)
        if bounds is None:
            return None
        col_l, col_r, row_t, row_b = bounds
        cw = col_r - col_l + 1
        ch = row_b - row_t + 1
        if cw < 3 or ch < 5:
            return None
        left_w = max(2, cw // 3)
        right_w = max(2, cw // 3)
        upper_h = max(2, ch // 3)
        lower_h = max(2, ch // 3)
        lower_left = grid[row_b - lower_h + 1:row_b + 1, col_l:col_l + left_w]
        upper_right = grid[row_t:row_t + upper_h, col_r - right_w + 1:col_r + 1]
        ll = float(np.count_nonzero(lower_left)) / max(1, lower_left.size)
        ur = float(np.count_nonzero(upper_right)) / max(1, upper_right.size)
        return "6" if ll >= ur else "9"

    @staticmethod
    def _disambiguate_0_6(grid: np.ndarray) -> str | None:
        """'6' has denser center than '0' (upper bowl closes into mid-band)."""
        bounds = RadarDetector._get_content_bounds(grid)
        if bounds is None:
            return None
        col_l, col_r, row_t, row_b = bounds
        cw = col_r - col_l + 1
        ch = row_b - row_t + 1
        if cw < 3 or ch < 5:
            return None
        center = grid[
            row_t + ch // 3:row_t + 2 * ch // 3 + 1,
            col_l + cw // 3:col_l + 2 * cw // 3 + 1,
        ]
        return "6" if int(np.sum(center)) >= 80 else "0"

    @staticmethod
    def _disambiguate_6_8(grid: np.ndarray) -> str | None:
        """'8' has a closed top-right loop; '6' is open on the top-right.

        Check the upper-right quadrant: '8' has content there (the top
        loop curves back), while '6' has little or none (open top).
        """
        bounds = RadarDetector._get_content_bounds(grid)
        if bounds is None:
            return None
        col_l, col_r, row_t, row_b = bounds
        cw = col_r - col_l + 1
        ch = row_b - row_t + 1
        if cw < 3 or ch < 5:
            return None
        # Upper-right zone: top third of height, right half of width
        upper_right = grid[
            row_t:row_t + ch // 3,
            col_l + cw // 2:col_r + 1,
        ]
        return "8" if int(np.sum(upper_right)) > 0 else "6"

    @staticmethod
    def _disambiguate_2_7(grid: np.ndarray) -> str | None:
        """'7' has stronger top stroke, '2' has stronger bottom stroke."""
        bounds = RadarDetector._get_content_bounds(grid)
        if bounds is None:
            return None
        col_l, col_r, row_t, row_b = bounds
        cw = col_r - col_l + 1
        ch = row_b - row_t + 1
        if cw < 3 or ch < 5:
            return None
        band_h = max(2, ch // 4)
        top = grid[row_t:row_t + band_h, col_l:col_r + 1]
        bot = grid[row_b - band_h + 1:row_b + 1, col_l:col_r + 1]
        top_fill = float(np.count_nonzero(top)) / max(1, top.size)
        bot_fill = float(np.count_nonzero(bot)) / max(1, bot.size)
        if bot_fill >= top_fill:
            return "2"
        return "7"

    # ------------------------------------------------------------------
    # PIL template rendering
    # ------------------------------------------------------------------

    def _get_templates(self) -> dict[str, np.ndarray]:
        if self._templates is None:
            self._templates = self._render_templates(self._font_size)
        return self._templates

    def _get_multi_templates(self) -> list[tuple[dict[str, np.ndarray], int, int, float]]:
        """Return templates at base font_size ±1 in 0.5px steps (5 sizes)."""
        if self._multi_templates is None:
            base = self._font_size
            sizes = [base - 1, base - 0.5, base, base + 0.5, base + 1]
            sizes = [max(8, s) for s in sizes]
            # Deduplicate (e.g. if base=8, base-1=8 after clamp)
            seen = set()
            result = []
            for s in sizes:
                if s in seen:
                    continue
                seen.add(s)
                old_gw, old_gh = self._grid_w, self._grid_h
                templates = self._render_templates(s)
                gw, gh = self._grid_w, self._grid_h
                self._grid_w, self._grid_h = old_gw, old_gh
                if templates:
                    result.append((templates, gw, gh, s))
            self._multi_templates = result
            # Restore base size grid dims
            if self._templates is None:
                self._get_templates()
        return self._multi_templates

    def _render_templates(self, font_size) -> dict[str, np.ndarray]:
        """Render every RADAR_CHARS glyph as native-size 4-bit content (no resizing)."""
        if _SCALEFORM_AVAILABLE:
            return self._render_templates_scaleform(font_size, 0)
        if _PIL_AVAILABLE:
            return self._render_templates_pil(font_size, 0)
        return {}

    def _render_templates_scaleform(
        self, font_size: int, target_h: int
    ) -> dict[str, np.ndarray]:
        """Render templates using the Scaleform-faithful rasterizer."""
        try:
            renderer = _ScaleformRenderer(
                FONT_PATH, size=font_size,
                x_offset=SCALEFORM_X_OFFSET,
                y_offset=SCALEFORM_Y_OFFSET,
            )
        except Exception as e:
            log.error("ScaleformRenderer init failed: %s", e)
            return {}

        # Render all glyphs — keep full bitmap as-is (no cropping)
        templates: dict[str, np.ndarray] = {}
        for ch in RADAR_CHARS:
            try:
                bitmap = renderer.render_char(ch)
                if bitmap is None or bitmap.size == 0:
                    continue
                arr = np.minimum(bitmap.astype(np.float32) / 16, 15).astype(np.uint8)
                if arr.max() > 0:
                    templates[ch] = arr
            except Exception as e:
                log.debug("Scaleform template render failed for '%s': %s", ch, e)

        if not templates:
            return {}

        # Grid dimensions = bitmap dimensions (all glyphs same size from renderer)
        sample = next(v for k, v in templates.items() if k in "0123456789")
        self._grid_w = sample.shape[1]
        self._grid_h = sample.shape[0]

        sample = templates.get('0')
        log.info(
            "Rendered %d radar templates via Scaleform (font_size=%d, grid=%dx%d)",
            len(templates), font_size, self._grid_w, self._grid_h,
        )
        return templates

    def _render_templates_pil(
        self, pil_size: int, target_h: int
    ) -> dict[str, np.ndarray]:
        """Render templates using PIL (fallback when freetype-py is unavailable)."""
        try:
            font = _ImageFont.truetype(str(FONT_PATH), pil_size)
        except Exception as e:
            log.error("Could not load font %s: %s", FONT_PATH, e)
            return {}

        templates: dict[str, np.ndarray] = {}
        for ch in RADAR_CHARS:
            try:
                bbox = font.getbbox(ch)
                cw   = bbox[2] - bbox[0]
                ch_h = bbox[3] - bbox[1]
                if cw < 1 or ch_h < 1:
                    continue

                img = Image.new("L", (cw + 4, ch_h + 4), 0)
                ImageDraw.Draw(img).text(
                    (2 - bbox[0], 2 - bbox[1]), ch, fill=255, font=font
                )
                arr = np.array(img, dtype=np.float32)
                arr[arr < 30] = 0

                # Tight content — no resizing
                rows = np.any(arr > 0, axis=1)
                cols = np.any(arr > 0, axis=0)
                if not rows.any() or not cols.any():
                    continue
                t_top  = int(np.argmax(rows))
                t_bot  = int(len(rows) - 1 - np.argmax(rows[::-1]))
                t_left = int(np.argmax(cols))
                t_right= int(len(cols) - 1 - np.argmax(cols[::-1]))
                content = arr[t_top:t_bot + 1, t_left:t_right + 1]
                content_4bit = np.minimum(content / 16, 15).astype(np.uint8)
                if content_4bit.max() > 0:
                    templates[ch] = content_4bit
            except Exception as e:
                log.debug("PIL template render failed for '%s': %s", ch, e)

        if not templates:
            return {}

        digit_contents = [v for k, v in templates.items() if k in "0123456789"]
        max_w = max(c.shape[1] for c in digit_contents)
        max_h = max(c.shape[0] for c in digit_contents)
        self._grid_w = max_w
        self._grid_h = max_h

        # Place into grids
        gridded: dict[str, np.ndarray] = {}
        for ch, content in templates.items():
            c_h, c_w = content.shape
            grid = np.zeros((max_h, max_w), dtype=np.uint8)
            gx = max(0, max_w - c_w)
            gy = max(0, max_h - c_h)
            grid[gy:gy + c_h, gx:gx + c_w] = content
            gridded[ch] = grid

        log.info("Rendered %d radar templates via PIL (pil_size=%d, grid=%dx%d)",
                 len(gridded), pil_size, self._grid_w, self._grid_h)
        return gridded

    # ------------------------------------------------------------------
    # Grid placement + scoring (same approach as skill scanner)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_blob(
        intensity_4bit: np.ndarray,
        x0: int, x1: int,
        text_top: int, text_h: int,
        grid_w: int, grid_h: int,
    ) -> np.ndarray:
        """Place blob content right-aligned + bottom-aligned in a fixed grid.

        Same approach as skill scanner's normalize_blob: extracts the tight
        content bounding box, then places it at the correct position in the
        target grid.  No stretching — pixel-exact placement.
        """
        rows = min(text_h, intensity_4bit.shape[0] - text_top)
        cols = min(x1 + 1, intensity_4bit.shape[1])
        region = intensity_4bit[text_top:text_top + rows, x0:cols]

        cm = region > 0
        if not cm.any():
            return np.zeros((grid_h, grid_w), dtype=np.uint8)

        rh = np.any(cm, axis=1)
        ch = np.any(cm, axis=0)
        ct = int(np.argmax(rh))
        cb = int(len(rh) - 1 - np.argmax(rh[::-1]))
        cl = int(np.argmax(ch))
        cr = int(len(ch) - 1 - np.argmax(ch[::-1]))

        content = region[ct:cb + 1, cl:cr + 1]
        c_h, c_w = content.shape

        # Left-aligned, bottom-aligned
        gy = max(0, grid_h - c_h)
        pw = min(c_w, grid_w)
        ph = min(c_h, grid_h)

        grid = np.zeros((grid_h, grid_w), dtype=np.uint8)
        grid[gy:gy + ph, :pw] = content[:ph, :pw]
        return grid

    @staticmethod
    def _place_in_grid(
        content: np.ndarray, grid_h: int, grid_w: int
    ) -> np.ndarray:
        """Place content left-aligned + bottom-aligned in a (possibly larger) grid."""
        c_h, c_w = content.shape
        grid = np.zeros((grid_h, grid_w), dtype=np.uint8)
        gy = max(0, grid_h - c_h)
        ph = min(c_h, grid_h)
        pw = min(c_w, grid_w)
        grid[gy:gy + ph, :pw] = content[c_h - ph:, :pw]
        return grid

    @staticmethod
    def _score_grid(candidate: np.ndarray, template: np.ndarray) -> float:
        """Shift-tolerant scoring without allocating shifted full-size arrays."""
        if candidate.shape != template.shape:
            return -1.0

        t_sum = int(np.sum(template, dtype=np.int32))
        if t_sum == 0:
            return 0.0
        c_sum = int(np.sum(candidate, dtype=np.int32))
        denom = float(3 * t_sum)

        best_overlap = int(np.sum(np.minimum(candidate, template), dtype=np.int32))
        best = float(6 * best_overlap - 2 * t_sum - c_sum) / denom

        _, w = candidate.shape
        # Candidate shift sweep (template fixed).
        for shift in RADAR_SCORE_SHIFT_OFFSETS:
            if abs(shift) >= w:
                continue
            if shift > 0:
                c_view = candidate[:, :w - shift]
                t_view = template[:, shift:]
            else:
                k = -shift
                c_view = candidate[:, k:]
                t_view = template[:, :w - k]
            overlap = int(np.sum(np.minimum(c_view, t_view), dtype=np.int32))
            s = float(6 * overlap - 2 * t_sum - c_sum) / denom
            if s > best:
                best = s

        # Template shift sweep (candidate fixed), keeps existing behavior.
        for shift in RADAR_SCORE_SHIFT_OFFSETS:
            if abs(shift) >= w:
                continue
            if shift > 0:
                c_view = candidate[:, shift:]
                t_view = template[:, :w - shift]
            else:
                k = -shift
                c_view = candidate[:, :w - k]
                t_view = template[:, k:]
            overlap = int(np.sum(np.minimum(c_view, t_view), dtype=np.int32))
            s = float(6 * overlap - 2 * t_sum - c_sum) / denom
            if s > best:
                best = s

        return best

    @staticmethod
    def _score_grid_batch(candidate: np.ndarray, templates: np.ndarray) -> np.ndarray:
        """Vectorized equivalent of _score_grid for a stack of templates."""
        if templates.ndim != 3 or candidate.ndim != 2:
            return np.full((0,), -1.0, dtype=np.float64)

        n, h, w = templates.shape
        if candidate.shape != (h, w):
            return np.full((n,), -1.0, dtype=np.float64)

        t_sum = np.sum(templates, axis=(1, 2), dtype=np.int32)
        best = np.zeros((n,), dtype=np.float64)
        valid = t_sum > 0
        if not np.any(valid):
            return best

        c_sum = int(np.sum(candidate, dtype=np.int32))
        c3 = candidate[np.newaxis, :, :]

        overlap = np.sum(np.minimum(c3, templates), axis=(1, 2), dtype=np.int32)
        numer = (
            6 * overlap.astype(np.int64)
            - 2 * t_sum.astype(np.int64)
            - np.int64(c_sum)
        )
        denom = 3.0 * t_sum.astype(np.float64)
        best[valid] = numer[valid] / denom[valid]

        # Candidate shift sweep (template fixed).
        for shift in RADAR_SCORE_SHIFT_OFFSETS:
            if abs(shift) >= w:
                continue
            if shift > 0:
                c_view = candidate[:, :w - shift][np.newaxis, :, :]
                t_view = templates[:, :, shift:]
            else:
                k = -shift
                c_view = candidate[:, k:][np.newaxis, :, :]
                t_view = templates[:, :, :w - k]
            overlap = np.sum(np.minimum(c_view, t_view), axis=(1, 2), dtype=np.int32)
            numer = (
                6 * overlap.astype(np.int64)
                - 2 * t_sum.astype(np.int64)
                - np.int64(c_sum)
            )
            score = np.zeros((n,), dtype=np.float64)
            score[valid] = numer[valid] / denom[valid]
            best = np.maximum(best, score)

        # Template shift sweep (candidate fixed).
        for shift in RADAR_SCORE_SHIFT_OFFSETS:
            if abs(shift) >= w:
                continue
            if shift > 0:
                c_view = candidate[:, shift:][np.newaxis, :, :]
                t_view = templates[:, :, :w - shift]
            else:
                k = -shift
                c_view = candidate[:, :w - k][np.newaxis, :, :]
                t_view = templates[:, :, k:]
            overlap = np.sum(np.minimum(c_view, t_view), axis=(1, 2), dtype=np.int32)
            numer = (
                6 * overlap.astype(np.int64)
                - 2 * t_sum.astype(np.int64)
                - np.int64(c_sum)
            )
            score = np.zeros((n,), dtype=np.float64)
            score[valid] = numer[valid] / denom[valid]
            best = np.maximum(best, score)

        return best

    # ------------------------------------------------------------------
    # Grid scoring — template-coverage approach
    # ------------------------------------------------------------------

    @staticmethod
    def _score_grid_raw(candidate: np.ndarray, template: np.ndarray) -> float:
        """Score candidate vs template (same formula as skill scanner).

        Formula: (6*sum(min(c,t)) - 2*sum(t) - sum(c)) / (3*sum(t))
        Normalized to roughly [-1, 1] range so thresholds stay consistent.
        Both arrays must have the same shape (normalised into a common grid).
        """
        if candidate.shape != template.shape:
            return -1.0
        c     = candidate.astype(np.int32)
        t     = template.astype(np.int32)
        t_sum = int(np.sum(t))
        if t_sum == 0:
            return 0.0
        overlap = int(np.sum(np.minimum(c, t)))
        c_sum   = int(np.sum(c))
        return float(6 * overlap - 2 * t_sum - c_sum) / float(3 * t_sum)
