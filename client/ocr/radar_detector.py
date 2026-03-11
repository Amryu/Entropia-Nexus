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

from ..core.constants import (
    EVENT_RADAR_COORDINATES,
    EVENT_RADAR_DEBUG,
    EVENT_RADAR_LOST,
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

#: Lon row top edge  = cy + LON_OFFSET_RATIO * r
TEXT_LON_OFFSET_RATIO  = 1.032

#: Lat row top edge  = Lon row top + STRIDE_RATIO * r
TEXT_STRIDE_RATIO      = 0.181

#: Text left edge    = cx + LEFT_RATIO * r   (negative = left of centre)
TEXT_LEFT_RATIO        = -0.851

#: Text region width = WIDTH_RATIO * r  (extra margin beyond measured width)
TEXT_WIDTH_RATIO       = 0.90

#: Row region height = HEIGHT_RATIO * r  (cap height + descenders + padding)
TEXT_HEIGHT_RATIO      = 0.130

# ---------------------------------------------------------------------------
# OCR constants
# ---------------------------------------------------------------------------

#: Pixels below this brightness are zeroed before blob detection.
RADAR_TEXT_BRIGHTNESS_THRESHOLD = 100

#: Minimum bright px per column to count as a text column.
RADAR_MIN_COL_DENSITY   = 2

#: Column-sum below this in the 4-bit image = inter-character valley.
RADAR_VALLEY_THRESHOLD  = 15

#: Max single-character width before valley-splitting is attempted.
RADAR_MAX_SINGLE_W      = 14

#: Minimum sub-blob width after splitting.
RADAR_MIN_SUB_BLOB_W    = 2

#: Fixed template grid dimensions (all characters normalised to this size).
RADAR_GRID_W = 10
RADAR_GRID_H = 20   # must be >= max target_h (18 at 200 % scale)

#: Characters that appear in the label portion of each coordinate row.
#: Cardinal direction suffixes (N/S/E/W) are deliberately excluded — they
#: are skipped by the digit-zone position filter and never matched.
RADAR_CHARS = "0123456789Lonat:"

#: Coordinates are 4–6 digits (game coordinate space can require up to 6).
COORD_MIN_DIGITS = 4
COORD_MAX_DIGITS = 6

# ---------------------------------------------------------------------------
# Detection / timing constants
# ---------------------------------------------------------------------------

#: HoughCircles edge-strength threshold (param1).
HOUGH_PARAM1 = 100

#: HoughCircles accumulator threshold (param2); try cascading to 25 on miss.
HOUGH_PARAM2_STRICT  = 40
HOUGH_PARAM2_LENIENT = 25

#: Poll interval (seconds).  2 Hz is sufficient for coordinates.
DETECT_INTERVAL_S = 0.5

#: Confidence below this = failed read for that tick.
CONF_FAIL_THRESHOLD = 0.38

#: Consecutive failed reads before a background rescan is attempted.
CONSECUTIVE_FAIL_BEFORE_SCAN = 60   # ≈ 30 s at 2 Hz

#: How many px the circle centre must shift to trigger recalibration notice.
RECAL_DIST_THRESHOLD = 30

#: Circle radius must differ by more than this to trigger recalibration.
RECAL_RADIUS_THRESHOLD = 15

#: Seconds with no circle found before EVENT_RADAR_LOST is published.
LOST_TIMEOUT_S = 5.0

# ---------------------------------------------------------------------------
# Font / Scaleform renderer
# ---------------------------------------------------------------------------

FONT_PATH = Path(__file__).parent.parent / "assets" / "arial-unicode-bold.ttf"

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

    *frame_source* may be a ``SharedFrameCache`` or a ``ScreenCapturer``.
    """

    def __init__(self, config, event_bus, frame_source):
        self._config       = config
        self._event_bus    = event_bus

        # Frame source (SharedFrameCache or ScreenCapturer)
        self._frame_cache  = None
        self._capturer     = None
        try:
            from .frame_cache import SharedFrameCache
            if isinstance(frame_source, SharedFrameCache):
                self._frame_cache = frame_source
            else:
                self._capturer = frame_source
        except ImportError:
            self._capturer = frame_source

        # Thread control
        self._running = False
        self._thread  = None

        # Cached radar circle  (cx, cy, r)
        self._circle: tuple[int, int, int] | None = None
        self._scale:    float = 1.0
        self._pil_size: int   = 14

        # PIL template cache — keyed by pil_size, invalidated on scale change
        self._templates: dict[str, np.ndarray] | None = None

        # State
        self._last_coords:       tuple[int, int] | None = None
        self._consecutive_fails: int   = 0
        self._lost_since:        float | None = None

        # Game window
        self._game_hwnd     = None
        self._game_geometry = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._detect_loop, daemon=True, name="RadarDetector"
        )
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def trigger_recalibrate(self):
        """Force a full Hough re-scan on the next tick (e.g. from hotkey)."""
        self._circle = None
        log.info("Radar recalibration triggered")

    # ------------------------------------------------------------------
    # Thread
    # ------------------------------------------------------------------

    def _detect_loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as e:
                log.error("Radar tick error: %s", e, exc_info=True)
            time.sleep(DETECT_INTERVAL_S)

    def _tick(self):
        if cv2 is None or not _PIL_AVAILABLE:
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

        # Phase 1 — locate radar circle (only when not cached)
        if self._circle is None:
            frame = self._capture_frame()
            if frame is None:
                return
            circle = self._find_radar_circle(frame)
            if circle is None:
                self._handle_no_circle()
                return
            self._set_circle(circle)

        # Phase 2 — read coordinates
        frame = self._capture_frame()
        if frame is None:
            return

        result = self._read_coordinates(frame)
        if result is None:
            self._consecutive_fails += 1
            if self._consecutive_fails >= CONSECUTIVE_FAIL_BEFORE_SCAN:
                self._background_rescan(frame)
            return

        lon, lat, conf = result
        self._consecutive_fails = 0
        self._lost_since = None

        if (lon, lat) != self._last_coords:
            self._last_coords = (lon, lat)
            go = (self._game_geometry[0], self._game_geometry[1]) if self._game_geometry else (0, 0)
            cx, cy, r = self._circle
            self._event_bus.publish(EVENT_RADAR_COORDINATES, {
                "lon":        lon,
                "lat":        lat,
                "confidence": conf,
                "scale":      self._scale,
                "game_origin": go,
                "circle_cx":  go[0] + cx,
                "circle_cy":  go[1] + cy,
                "circle_r":   r,
            })

    def _background_rescan(self, frame):
        """After many consecutive failures, check whether the circle moved."""
        circle = self._find_radar_circle(frame)
        if circle is None:
            self._handle_no_circle()
            self._consecutive_fails = 0
            return

        cx,  cy,  r  = circle
        ocx, ocy, or_ = self._circle
        dist = ((cx - ocx) ** 2 + (cy - ocy) ** 2) ** 0.5
        if dist > RECAL_DIST_THRESHOLD or abs(r - or_) > RECAL_RADIUS_THRESHOLD:
            log.warning(
                "Radar moved: old=(%d,%d,r%d) new=(%d,%d,r%d) — requesting recalibration",
                ocx, ocy, or_, cx, cy, r,
            )
            self._event_bus.publish(EVENT_RADAR_DEBUG, {"needs_recalibrate": True})

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
        """Run HoughCircles on a grayscale frame; return (cx, cy, r) or None.

        Radius range covers 60 %–210 % UI scale relative to BASE_RADAR_RADIUS_PX.
        Dark-interior validation (mean pixel < 90) rejects non-radar circles.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        h, w = gray.shape

        min_r = max(20, int(BASE_RADAR_RADIUS_PX * 0.60))
        max_r = min(min(w, h) // 2, int(BASE_RADAR_RADIUS_PX * 2.10))

        circles = None
        for p2 in (HOUGH_PARAM2_STRICT, HOUGH_PARAM2_LENIENT):
            circles = cv2.HoughCircles(
                gray, cv2.HOUGH_GRADIENT, dp=1,
                minDist=min_r * 2,
                param1=HOUGH_PARAM1, param2=p2,
                minRadius=min_r, maxRadius=max_r,
            )
            if circles is not None:
                break

        if circles is None:
            return None

        # Among all candidates pick the one with the darkest interior
        best_circle = None
        best_interior = 1e9
        for cx, cy, r in np.round(circles[0]).astype(int):
            cx, cy, r = int(cx), int(cy), int(r)
            # Sample interior at 80 % radius to avoid the bright border ring
            mask = np.zeros_like(gray)
            cv2.circle(mask, (cx, cy), int(r * 0.80), 255, -1)
            interior_mean = float(gray[mask == 255].mean())
            if interior_mean < best_interior:
                best_interior = interior_mean
                best_circle   = (cx, cy, r)

        if best_interior > 90:
            return None  # interior not dark enough to be the radar

        # Refine radius: scan outward for the bright white border ring.
        # HoughCircles often locks onto an inner dial ring; the actual outer
        # border (white, ~2 px wide) produces a bright-fraction peak at the
        # true radius.
        cx, cy, r = best_circle
        corrected_r = self._find_white_border_radius(gray, cx, cy, r)
        return (cx, cy, corrected_r)

    @staticmethod
    def _find_white_border_radius(
        gray: np.ndarray, cx: int, cy: int, r_hint: int
    ) -> int:
        """Scan ring brightness outward from r_hint to locate the white border.

        The outer border of the radar is a bright (~255) ring roughly 2 px
        wide.  This pass finds the radius with the highest fraction of pixels
        > 150 in the range [85 %, 155 %] of r_hint and returns it when the
        fraction exceeds 0.12 (i.e. at least 12 % of ring pixels are bright).
        Falls back to r_hint if no clearly bright ring is found.
        """
        best_r    = r_hint
        best_frac = 0.0
        h, w = gray.shape
        for r_test in range(int(r_hint * 0.85), int(r_hint * 1.55) + 1):
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(mask, (cx, cy), r_test, 255, 2)
            pts = gray[mask == 255]
            if len(pts) == 0:
                continue
            frac = float((pts > 150).sum()) / len(pts)
            if frac > best_frac:
                best_frac = frac
                best_r    = r_test
        return best_r if best_frac > 0.12 else r_hint

    def _set_circle(self, circle: tuple[int, int, int]):
        cx, cy, r = circle
        self._circle = (cx, cy, r)
        self._scale  = r / BASE_RADAR_RADIUS_PX

        pil_size = max(8, min(40, round(BASE_CAP_HEIGHT_PX * self._scale / 0.72)))
        if pil_size != self._pil_size:
            self._pil_size  = pil_size
            self._templates = None  # invalidate cache

        log.info(
            "Radar circle set: cx=%d cy=%d r=%d scale=%.2f pil_size=%d",
            cx, cy, r, self._scale, self._pil_size,
        )

    # ------------------------------------------------------------------
    # Coordinate reading
    # ------------------------------------------------------------------

    def _read_coordinates(
        self, frame: np.ndarray
    ) -> tuple[int, int, float] | None:
        """Extract and OCR Lon + Lat rows. Returns (lon, lat, conf) or None."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        h, w = gray.shape
        cx, cy, r = self._circle

        row_h      = max(5, round(TEXT_HEIGHT_RATIO * r))
        text_left  = max(0,   cx + round(TEXT_LEFT_RATIO  * r) - 4)
        text_right = min(w,   cx + round(TEXT_LEFT_RATIO  * r) + round(TEXT_WIDTH_RATIO  * r) + 4)
        lon_top    = max(0,   cy + round(TEXT_LON_OFFSET_RATIO * r))
        lon_bot    = min(h,   lon_top + row_h)
        lat_top    = max(0,   cy + round((TEXT_LON_OFFSET_RATIO + TEXT_STRIDE_RATIO) * r))
        lat_bot    = min(h,   lat_top + row_h)

        if text_right <= text_left:
            return None

        lon_roi = gray[lon_top:lon_bot, text_left:text_right]
        lat_roi = gray[lat_top:lat_bot, text_left:text_right]

        if lon_roi.size == 0 or lat_roi.size == 0:
            return None

        lon_val, lon_conf = self._ocr_row(lon_roi)
        lat_val, lat_conf = self._ocr_row(lat_roi)

        if lon_val is None or lat_val is None:
            return None

        conf = (lon_conf * lat_conf) ** 0.5
        if conf < CONF_FAIL_THRESHOLD:
            return None

        return lon_val, lat_val, conf

    def _ocr_row(self, roi: np.ndarray) -> tuple[int | None, float]:
        """OCR a single coordinate row. Returns (coord_int, confidence) or (None, 0)."""
        # CLAHE — handles bright sky / variable backgrounds behind text
        enhanced = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4)).apply(roi)

        # Threshold → normalize → re-threshold (same pipeline as market_price_detector)
        intensity = enhanced.copy()
        intensity[intensity < RADAR_TEXT_BRIGHTNESS_THRESHOLD] = 0
        if intensity.max() > 0:
            intensity = cv2.normalize(
                intensity, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U
            )
        intensity[intensity < RADAR_TEXT_BRIGHTNESS_THRESHOLD] = 0

        intensity_4bit = np.minimum(
            intensity.astype(np.float32) / 16, 15
        ).astype(np.uint8)

        # Vertical text bounds
        rows_with_content = np.any(intensity_4bit > 0, axis=1)
        if not rows_with_content.any():
            return None, 0.0
        text_top = int(np.argmax(rows_with_content))
        text_bot = int(len(rows_with_content) - 1 - np.argmax(rows_with_content[::-1]))
        text_h   = text_bot - text_top + 1
        if text_h < 3:
            return None, 0.0

        # Blob segmentation
        text_strip  = intensity_4bit[text_top:text_bot + 1, :]
        col_density = np.sum(text_strip > 0, axis=0)
        col_active  = col_density >= RADAR_MIN_COL_DENSITY
        blobs: list[tuple[int, int]] = []
        start = -1
        for col in range(len(col_active) + 1):
            active = col < len(col_active) and col_active[col]
            if active and start < 0:
                start = col
            elif not active and start >= 0:
                blobs.append((start, col - 1))
                start = -1

        if len(blobs) < 6:  # need at least "Lon:" + 1 digit
            return None, 0.0

        blobs = self._split_blobs(intensity_4bit, blobs, text_top, text_h)

        # Positional filtering: the row format is  "Lon: DDDDD [X]"
        # where D = digit and X = optional direction letter.
        # We skip the label ("Lon: " / "Lat: " ≈ first 38 % of ROI) and any
        # trailing direction suffix (≈ last 12 % of ROI), then match only
        # the digit zone against digit-only templates to avoid letter/digit
        # confusion (e.g. 'S' vs '8') that arises at small font sizes.
        roi_w         = intensity_4bit.shape[1]
        digit_x_start = round(0.38 * roi_w)   # skip "Lon: " / "Lat: "
        digit_x_end   = round(0.88 * roi_w)   # skip optional NSEW suffix

        digit_templates = {
            ch: tmpl for ch, tmpl in self._get_templates().items()
            if ch in "0123456789"
        }
        if not digit_templates:
            return None, 0.0

        target_h = max(4, round(BASE_CAP_HEIGHT_PX * self._scale))
        chars:  list[str]   = []
        scores: list[float] = []
        for x0, x1 in blobs:
            x_center = (x0 + x1) // 2
            if x_center < digit_x_start or x_center > digit_x_end:
                continue  # outside digit zone

            candidate = self._norm_to_grid(
                intensity_4bit, x0, x1, text_top, text_h,
                RADAR_GRID_W, RADAR_GRID_H, target_h,
            )
            best_score = -1.0
            best_char  = "?"
            for ch, tmpl in digit_templates.items():
                s = self._score_grid(candidate, tmpl)
                if s > best_score:
                    best_score = s
                    best_char  = ch
            # Accept any positive-scoring match in the digit zone
            chars.append(best_char if best_score > 0.0 else "?")
            scores.append(max(0.0, best_score))

        if len(chars) < 4:  # fewer blobs than minimum digit count
            return None, 0.0

        text = "".join(chars)

        # Extract first 4-6-digit run
        m = _COORD_RE.search(text)
        if not m:
            return None, 0.0

        digit_str    = m.group(0)
        digit_start  = m.start()
        digit_scores = scores[digit_start: digit_start + len(digit_str)]
        if not digit_scores:
            return None, 0.0

        conf = float(np.prod(digit_scores) ** (1.0 / len(digit_scores)))
        return int(digit_str), conf

    # ------------------------------------------------------------------
    # Blob splitting
    # ------------------------------------------------------------------

    def _split_blobs(
        self,
        intensity_4bit: np.ndarray,
        blobs: list[tuple[int, int]],
        text_top: int,
        text_h: int,
    ) -> list[tuple[int, int]]:
        result: list[tuple[int, int]] = []
        for x0, x1 in blobs:
            if x1 - x0 + 1 <= RADAR_MAX_SINGLE_W:
                result.append((x0, x1))
                continue

            strip    = intensity_4bit[text_top: text_top + text_h, x0: x1 + 1]
            col_sums = np.sum(strip.astype(np.int32), axis=0)

            valleys: list[int] = []
            for c in range(1, len(col_sums) - 1):
                if col_sums[c] < RADAR_VALLEY_THRESHOLD:
                    if not valleys or (x0 + c) - valleys[-1] >= RADAR_MIN_SUB_BLOB_W:
                        valleys.append(x0 + c)

            if not valleys:
                result.append((x0, x1))
                continue

            prev = x0
            for v in valleys:
                if v - 1 >= prev + RADAR_MIN_SUB_BLOB_W - 1:
                    result.append((prev, v - 1))
                prev = v + 1
            if prev <= x1:
                result.append((prev, x1))

        return result

    # ------------------------------------------------------------------
    # PIL template rendering
    # ------------------------------------------------------------------

    def _get_templates(self) -> dict[str, np.ndarray]:
        if self._templates is None:
            self._templates = self._render_templates(self._pil_size)
        return self._templates

    def _render_templates(self, pil_size: int) -> dict[str, np.ndarray]:
        """Render every RADAR_CHARS glyph as a 4-bit normalised grid.

        Uses the Scaleform-faithful renderer (ScaleformRenderer) when
        freetype-py is available — this closely matches the game's own
        GFx rasterizer, giving much better scores at small font sizes.
        Falls back to PIL/Arial Bold when freetype-py is unavailable.

        After extracting the tight content bounding box, each glyph is
        rescaled so its height equals the expected in-game cap height
        (BASE_CAP_HEIGHT_PX * scale).  This ensures the template occupies
        the same grid rows as the observed blob, which _norm_to_grid places
        bottom-aligned in the fixed grid.
        """
        target_h = max(4, round(BASE_CAP_HEIGHT_PX * self._scale))

        if _SCALEFORM_AVAILABLE:
            # Scaleform takes the actual pixel size directly (not a point size).
            return self._render_templates_scaleform(target_h, target_h)
        if _PIL_AVAILABLE:
            return self._render_templates_pil(pil_size, target_h)
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

        templates: dict[str, np.ndarray] = {}
        for ch in RADAR_CHARS:
            try:
                bitmap = renderer.render_char(ch)
                if bitmap is None or bitmap.size == 0:
                    continue
                # Convert 8-bit alpha → 4-bit
                arr = np.minimum(bitmap.astype(np.float32) / 16, 15).astype(np.uint8)
                grid = RadarDetector._norm_to_grid(
                    arr,
                    0, arr.shape[1] - 1, 0, arr.shape[0],
                    RADAR_GRID_W, RADAR_GRID_H, target_h,
                )
                if grid.max() > 0:
                    templates[ch] = grid
            except Exception as e:
                log.debug("Scaleform template render failed for '%s': %s", ch, e)

        log.info(
            "Rendered %d radar character templates via Scaleform "
            "(font_size=%d target_h=%d)",
            len(templates), font_size, target_h,
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

                # Tight content bounding box
                rows = np.any(arr > 0, axis=1)
                cols = np.any(arr > 0, axis=0)
                if not rows.any() or not cols.any():
                    continue
                t_top  = int(np.argmax(rows))
                t_bot  = int(len(rows) - 1 - np.argmax(rows[::-1]))
                t_left = int(np.argmax(cols))
                t_right= int(len(cols) - 1 - np.argmax(cols[::-1]))
                content = arr[t_top:t_bot + 1, t_left:t_right + 1]

                # Resize to target_h
                src_h, src_w = content.shape
                if src_h != target_h:
                    new_w = max(1, round(src_w * target_h / src_h))
                    content = cv2.resize(
                        content, (new_w, target_h),
                        interpolation=cv2.INTER_AREA,
                    )
                content_4bit = np.minimum(content / 16, 15).astype(np.uint8)

                canvas = np.zeros(
                    (content_4bit.shape[0] + 2, content_4bit.shape[1] + 2),
                    dtype=np.uint8,
                )
                canvas[1:1 + content_4bit.shape[0], 1:1 + content_4bit.shape[1]] = content_4bit
                c_rows = np.any(canvas > 0, axis=1)
                c_cols = np.any(canvas > 0, axis=0)
                if not c_rows.any() or not c_cols.any():
                    continue
                c_top  = int(np.argmax(c_rows))
                c_bot  = int(len(c_rows) - 1 - np.argmax(c_rows[::-1]))
                c_left = int(np.argmax(c_cols))
                c_right= int(len(c_cols) - 1 - np.argmax(c_cols[::-1]))

                grid = RadarDetector._norm_to_grid(
                    canvas,
                    c_left, c_right, c_top, c_bot - c_top + 1,
                    RADAR_GRID_W, RADAR_GRID_H, target_h,
                )
                if grid.max() > 0:
                    templates[ch] = grid
            except Exception as e:
                log.debug("PIL template render failed for '%s': %s", ch, e)

        log.info("Rendered %d radar character templates via PIL (pil_size=%d target_h=%d)",
                 len(templates), pil_size, target_h)
        return templates

    # ------------------------------------------------------------------
    # Grid normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _norm_to_grid(
        intensity_4bit: np.ndarray,
        x0: int, x1: int,
        text_top: int, text_h: int,
        grid_w: int, grid_h: int,
        target_h: int,
    ) -> np.ndarray:
        """Extract blob tight content, resize to (grid_w × target_h), place bottom-aligned.

        Unlike normalize_blob (pixel-exact, no scaling), this method scales
        every blob to exactly (grid_w × target_h) before placing it at the
        bottom of the (grid_h × grid_w) grid.  Using the same target_h for
        both template rendering and observed blob extraction ensures both
        occupy the same rows of the grid regardless of the original glyph
        width, making the 4-bit overlap score reliable even when the PIL font
        and the in-game Scaleform font have different character widths.
        """
        rows = min(text_h, intensity_4bit.shape[0] - text_top)
        cols = min(x1 + 1, intensity_4bit.shape[1])
        region = intensity_4bit[text_top:text_top + rows, x0:cols]

        # Tight content bounding box
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
        if content.size == 0:
            return np.zeros((grid_h, grid_w), dtype=np.uint8)

        # Resize to grid_w × target_h  (normalises both width and height)
        resized = cv2.resize(
            content.astype(np.float32),
            (grid_w, target_h),
            interpolation=cv2.INTER_AREA,
        )

        # Bottom-align in the full grid
        gy  = max(0, grid_h - target_h)
        ph  = min(target_h, grid_h - gy)
        grid = np.zeros((grid_h, grid_w), dtype=np.uint8)
        grid[gy:gy + ph, :] = np.minimum(resized[:ph, :], 15).astype(np.uint8)
        return grid

    # ------------------------------------------------------------------
    # Grid scoring  (identical formula to MarketPriceDetector)
    # ------------------------------------------------------------------

    @staticmethod
    def _score_grid_raw(candidate: np.ndarray, template: np.ndarray) -> float:
        if candidate.shape != template.shape:
            return -1.0
        c      = candidate.astype(np.int32)
        t      = template.astype(np.int32)
        overlap = int(np.sum(np.minimum(c, t)))
        t_sum   = int(np.sum(t))
        c_sum   = int(np.sum(c))
        if t_sum == 0:
            return 0.0
        return float(6 * overlap - 2 * t_sum - c_sum) / float(3 * t_sum)

    @staticmethod
    def _score_grid(candidate: np.ndarray, template: np.ndarray) -> float:
        """Shift-tolerant scoring: try ±1 column horizontal shift."""
        best = RadarDetector._score_grid_raw(candidate, template)
        _, w = candidate.shape
        for shift in (-1, 1):
            shifted = np.zeros_like(candidate)
            if shift > 0:
                shifted[:, shift:] = candidate[:, :-shift]
            else:
                shifted[:, :w + shift] = candidate[:, -shift:]
            s = RadarDetector._score_grid_raw(shifted, template)
            if s > best:
                best = s
        return best
