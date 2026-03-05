"""Market price window detection with configurable ROI reading.

Finds the game's "MARKET PRICE" label on screen using template matching,
then reads configurable ROI regions relative to it:
- Item name (1-2 rows)
- 10 data cells in a 5×2 grid (markup + sales for 5 time periods)
- Tier (optional)

Detection uses the same three-tier strategy as target_lock_detector:
1. Cheap pixel check at last position
2. Limited area search around last position
3. Full game window search
"""

import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.constants import (
    EVENT_MARKET_PRICE_DEBUG,
    EVENT_MARKET_PRICE_ERROR,
    EVENT_MARKET_PRICE_LOST,
    EVENT_MARKET_PRICE_SCAN,
    GAME_TITLE_PREFIX,
)
from ..core.logger import get_logger
from ..platform import backend as _platform

log = get_logger("MarketPrice")

# --- Foreground gating ---
BACKGROUND_SLEEP = 1.0  # seconds to sleep when game is not visible

# --- Match validation ---
MIN_INSIDE_BRIGHTNESS = 180  # pixels under mask must be bright
MIN_CONTRAST = 30            # brightness gap between inside and outside mask

# --- Cell reading ---
EMPTY_CELL_BRIGHTNESS = 40   # below this mean brightness → cell is empty (N/A)
NA_TEXT = "N/A"

# --- Text extraction (noise filtering for semi-transparent background) ---
# Pixels below this brightness are zeroed out before blob detection.
# The market price window has a semi-transparent dark background; text is
# bright white/cyan.  This threshold separates text from background bleed.
TEXT_BRIGHTNESS_THRESHOLD = 80

# --- Period labels for the 5 data rows ---
PERIODS = ["1d", "7d", "30d", "90d", "365d"]

# --- STPK assets directory ---
STPK_DIR = Path(__file__).parent.parent / "assets" / "stpk"


class MarketPriceDetector:
    """Detects the MARKET PRICE window and reads price data from it.

    Uses alpha-masked template matching with a three-tier search strategy.
    Reads item name, 10 data cells (5 periods × 2 columns), and tier
    using STPK font templates when available.
    """

    def __init__(self, config, event_bus, capturer_or_cache):
        self._config = config
        self._event_bus = event_bus

        # Accept either a SharedFrameCache or legacy ScreenCapturer
        from .frame_cache import SharedFrameCache
        if isinstance(capturer_or_cache, SharedFrameCache):
            self._frame_cache = capturer_or_cache
            self._capturer = None
        else:
            self._frame_cache = None
            self._capturer = capturer_or_cache

        self._running = False
        self._thread = None

        # Game window
        self._game_hwnd = None
        self._game_geometry: tuple[int, int, int, int] | None = None
        self._game_origin: tuple[int, int] = (0, 0)

        # Template (loaded lazily)
        self._template_gray = None
        self._template_mask = None
        self._template_mask_bool = None
        self._template_inv_bool = None
        self._template_h = 0
        self._template_w = 0

        # Tracking state
        self._last_pos: tuple[int, int] | None = None
        self._last_region_pixels: np.ndarray | None = None
        self._last_data: dict | None = None  # last published data (skip if unchanged)

        # STPK entries (loaded lazily, None = not loaded, [] = loaded but empty)
        self._digit_entries: list[dict] | None = None
        self._text_entries: list[dict] | None = None
        self._digit_grid_w = 0
        self._digit_grid_h = 0
        self._text_grid_w = 0
        self._text_grid_h = 0

        self._load_template()
        self._load_stpk()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _load_template(self):
        if cv2 is None:
            log.warning("OpenCV not available — market price detection disabled")
            return
        assets = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets"
        )
        path = os.path.join(assets, "market_price_label.png")
        raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if raw is None:
            log.error("Failed to load template: %s", path)
            return
        if raw.shape[2] < 4:
            log.error("Template has no alpha channel: %s", path)
            return

        self._template_mask = raw[:, :, 3]
        self._template_h, self._template_w = raw.shape[:2]
        self._template_gray = self._template_mask.copy()
        self._template_mask_bool = self._template_mask > 0
        self._template_inv_bool = ~self._template_mask_bool

        opaque_px = int(self._template_mask_bool.sum())
        total_px = self._template_h * self._template_w
        log.info("Template loaded: %dx%d (%d/%d opaque)",
                 self._template_w, self._template_h, opaque_px, total_px)

    def _load_stpk(self):
        """Load STPK files for digit and text reading."""
        try:
            from .stpk import read_stpk
        except ImportError:
            log.warning("STPK reader not available")
            return

        digit_name = getattr(self._config, "market_price_digit_stpk", "market_digits.stpk")
        text_name = getattr(self._config, "market_price_text_stpk", "market_text.stpk")

        digit_path = STPK_DIR / digit_name
        if digit_path.exists():
            try:
                header, entries = read_stpk(digit_path)
                self._digit_entries = entries
                self._digit_grid_w = header.get("grid_w", 0)
                self._digit_grid_h = header.get("grid_h", 0)
                log.info("Digit STPK loaded: %d entries (%dx%d grid)",
                         len(entries), self._digit_grid_w, self._digit_grid_h)
            except Exception as e:
                log.warning("Failed to load digit STPK %s: %s", digit_path, e)
        else:
            log.info("Digit STPK not found: %s (OCR reading disabled)", digit_path)

        text_path = STPK_DIR / text_name
        if text_path.exists():
            try:
                header, entries = read_stpk(text_path)
                self._text_entries = entries
                self._text_grid_w = header.get("grid_w", 0)
                self._text_grid_h = header.get("grid_h", 0)
                log.info("Text STPK loaded: %d entries (%dx%d grid)",
                         len(entries), self._text_grid_w, self._text_grid_h)
            except Exception as e:
                log.warning("Failed to load text STPK %s: %s", text_path, e)
        else:
            log.info("Text STPK not found: %s (name reading disabled)", text_path)

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
        if self._running or self._template_gray is None:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="market-price"
        )
        self._thread.start()
        log.info("Started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        log.info("Stopped")

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    def _capture_window(self, hwnd):
        """Capture via shared frame cache or legacy capturer."""
        if self._frame_cache is not None:
            return self._frame_cache.get_frame(hwnd, geometry=self._game_geometry)
        return self._capturer.capture_window(hwnd, geometry=self._game_geometry)

    def _poll_loop(self):
        interval = getattr(self._config, "market_price_poll_interval", 1.0)
        while self._running:
            try:
                if getattr(self._config, "market_price_enabled", True):
                    self._tick()
            except Exception as e:
                log.error("Tick error: %s", e)
            time.sleep(interval)

    def _tick(self):
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

        threshold = getattr(self._config, "market_price_match_threshold", 0.85)
        pos, confidence = self._find_template(image, threshold)

        if pos is not None:
            self._last_pos = pos
            x, y = pos
            self._last_region_pixels = self._extract_region(
                image, x, y, self._template_w, self._template_h
            )

            # Read all ROIs
            data = self._read_all_rois(image, x, y)
            data["confidence"] = confidence
            data["timestamp"] = datetime.now(timezone.utc).isoformat()

            # Publish debug data every tick (screen-absolute coordinates)
            gx, gy = self._game_origin
            self._event_bus.publish(EVENT_MARKET_PRICE_DEBUG, {
                "x": gx + x, "y": gy + y,
                "w": self._template_w, "h": self._template_h,
                "confidence": confidence,
                "data": data,
                "game_origin": self._game_origin,
            })

            # Only publish scan event if data changed from last scan
            if self._data_changed(data):
                self._last_data = data
                self._event_bus.publish(EVENT_MARKET_PRICE_SCAN, data)
                log.info("Scan: '%s' tier=%s conf=%.2f",
                         data.get("item_name", "?"),
                         data.get("tier"), confidence)
        else:
            # Window not detected — clear tracking
            if self._last_pos is not None:
                self._last_pos = None
                self._last_region_pixels = None
                self._event_bus.publish(EVENT_MARKET_PRICE_LOST, {})

    def _data_changed(self, data: dict) -> bool:
        """Check if the scan data differs from the last published data."""
        if self._last_data is None:
            return True
        # Compare key fields
        for key in ("item_name", "tier",
                     "markup_1d", "sales_1d", "markup_7d", "sales_7d",
                     "markup_30d", "sales_30d", "markup_90d", "sales_90d",
                     "markup_365d", "sales_365d"):
            if data.get(key) != self._last_data.get(key):
                return True
        return False

    # ------------------------------------------------------------------
    # Three-tier template search
    # ------------------------------------------------------------------

    def _find_template(self, image: np.ndarray, threshold: float
                       ) -> tuple[tuple[int, int] | None, float]:
        """Find the market price label in the game screenshot."""
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
        """Verify a candidate match has bright pixels inside and darker outside."""
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
    # ROI reading
    # ------------------------------------------------------------------

    def _read_all_rois(self, image: np.ndarray, tx: int, ty: int) -> dict:
        """Read all configured ROI regions relative to template position."""
        data = {
            "item_name": "",
            "tier": None,
        }
        # Initialize all period fields to None
        for period in PERIODS:
            data[f"markup_{period}"] = None
            data[f"sales_{period}"] = None

        errors = []

        # Item name (row 1 + optional row 2)
        roi_r1 = getattr(self._config, "market_price_roi_name_row1", None)
        roi_r2 = getattr(self._config, "market_price_roi_name_row2", None)
        name_parts = []
        if roi_r1:
            region = self._get_roi_region(image, tx, ty, roi_r1)
            if region is not None and region.size > 0:
                text = self._read_text(region)
                if text:
                    name_parts.append(text)
        if roi_r2:
            region = self._get_roi_region(image, tx, ty, roi_r2)
            if region is not None and region.size > 0:
                text = self._read_text(region)
                if text:
                    name_parts.append(text)
        raw_name = " ".join(name_parts).strip()
        normalized = self._normalize_item_name(raw_name)
        data["item_name"] = normalized
        # Include raw OCR name if normalization changed it (server can try both)
        if normalized != raw_name:
            data["item_name_raw"] = raw_name

        # Data cells (5 periods × 2 columns: markup, sales)
        roi_first = getattr(self._config, "market_price_roi_first_cell", None)
        cell_offset = getattr(self._config, "market_price_cell_offset", None)
        if roi_first and cell_offset:
            cell_w = roi_first.get("w", 0)
            cell_h = roi_first.get("h", 0)
            first_dx = roi_first.get("dx", 0)
            first_dy = roi_first.get("dy", 0)
            off_x = cell_offset.get("x", 0)
            off_y = cell_offset.get("y", 0)

            for row_idx, period in enumerate(PERIODS):
                for col_idx, metric in enumerate(["markup", "sales"]):
                    cell_dx = first_dx + col_idx * off_x
                    cell_dy = first_dy + row_idx * off_y
                    roi = {"dx": cell_dx, "dy": cell_dy, "w": cell_w, "h": cell_h}
                    region = self._get_roi_region(image, tx, ty, roi)
                    if region is not None and region.size > 0:
                        value = self._read_cell_number(region)
                        key = f"{metric}_{period}"
                        data[key] = value
                    else:
                        errors.append(f"{metric}_{period}: out of bounds")

        # Tier (optional)
        roi_tier = getattr(self._config, "market_price_roi_tier", None)
        if roi_tier:
            region = self._get_roi_region(image, tx, ty, roi_tier)
            if region is not None and region.size > 0:
                tier_val = self._read_cell_number(region)
                if tier_val is not None:
                    try:
                        data["tier"] = int(tier_val)
                    except (ValueError, TypeError):
                        pass

        if errors:
            self._event_bus.publish(EVENT_MARKET_PRICE_ERROR, {
                "errors": errors,
                "item_name": data["item_name"],
            })

        return data

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

    @staticmethod
    def _normalize_item_name(raw: str) -> str:
        """Normalize an OCR'd item name from the market price window.

        Handles:
        - Trailing "..." from the game's text truncation
        - Multiple spaces from line-break joining
        - Leading/trailing whitespace

        Does NOT attempt to fix punctuation spacing (e.g. missing space
        after comma) because item names in the game are inconsistent and
        any specific rule would be too narrow.  Both the raw and normalized
        names are sent to the server, which resolves via case-insensitive
        and prefix matching.
        """
        name = raw.strip()
        # Strip trailing ellipsis (game truncates long names)
        if name.endswith("..."):
            name = name[:-3].rstrip()
        # Collapse multiple spaces (artifact of line-break joining)
        name = " ".join(name.split())
        return name

    # ------------------------------------------------------------------
    # OCR reading (STPK-based)
    # ------------------------------------------------------------------

    def _read_cell_number(self, region: np.ndarray) -> float | None:
        """Read a numeric value from a cell region (BGR).

        Handles formats: "123.45%", "+123.45", "N/A", plain "12.34".
        Returns the numeric value (stripped of % and +), or None for N/A / empty.
        """
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        # Check if cell is empty / N/A
        if float(np.mean(gray)) < EMPTY_CELL_BRIGHTNESS:
            return None

        # If STPK digit entries are available, use grid-based matching
        if self._digit_entries:
            text = self._match_stpk_digits(region)
            if text:
                return self._parse_cell_value(text)

        # Fallback: no STPK available, return None
        return None

    def _read_text(self, region: np.ndarray) -> str:
        """Read text from a region (BGR) using text STPK templates.

        Returns the matched text string, or empty string if STPK unavailable.
        """
        if not self._text_entries:
            return ""

        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        if float(np.mean(gray)) < EMPTY_CELL_BRIGHTNESS:
            return ""

        return self._match_stpk_text(region)

    def _match_stpk_digits(self, region: np.ndarray) -> str:
        """Match digit STPK entries against a BGR cell image.

        Uses blob segmentation to find contiguous character groups, then
        matches each blob against STPK entries.  Wide blobs are first
        tested against multi-character entries (N/A, kPED, etc.) before
        being scored as single characters.

        Returns the matched text string (e.g. "123.45%"), or empty string.
        """
        if not self._digit_entries or self._digit_grid_w == 0:
            return ""
        return self._match_stpk_blobs(
            region, self._digit_entries,
            self._digit_grid_w, self._digit_grid_h,
            right_align=True,
        )

    def _match_stpk_text(self, region: np.ndarray) -> str:
        """Match text STPK entries against a BGR region.

        Uses blob segmentation, same as digits but with left-aligned
        text templates.
        """
        if not self._text_entries or self._text_grid_w == 0:
            return ""
        return self._match_stpk_blobs(
            region, self._text_entries,
            self._text_grid_w, self._text_grid_h,
            right_align=False,
        )

    def _extract_text_intensity(self, region: np.ndarray) -> np.ndarray:
        """Extract text pixel intensity from a BGR region.

        The market price window has semi-transparent dark background with
        bright white/cyan text.  This filters out background noise by
        zeroing pixels below the brightness threshold, keeping only text.
        """
        if len(region.shape) == 3:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        else:
            gray = region
        threshold = getattr(
            self._config, "market_price_text_threshold",
            TEXT_BRIGHTNESS_THRESHOLD,
        )
        intensity = gray.copy()
        intensity[intensity < threshold] = 0
        return intensity

    def _match_stpk_blobs(
        self,
        region: np.ndarray,
        entries: list[dict],
        grid_w: int,
        grid_h: int,
        right_align: bool,
    ) -> str:
        """Blob-based STPK matching.

        1. Extract text intensity (threshold out background noise)
        2. Quantize to 4-bit, find text vertical bounds
        3. Segment into blobs (contiguous column groups with content)
        4. For each blob, match against all STPK entries
        5. Wide blobs try multi-char entries first; if none match well,
           treat as single character
        """
        # Extract text intensity with noise filtering
        intensity = self._extract_text_intensity(region)

        # Quantize to 4-bit lightness
        intensity_4bit = np.minimum(intensity.astype(np.float32) / 16, 15).astype(np.uint8)

        # Find text vertical bounds
        rows_with_content = np.any(intensity_4bit > 0, axis=1)
        if not rows_with_content.any():
            return ""

        text_top = int(np.argmax(rows_with_content))
        text_bot = int(len(rows_with_content) - 1 - np.argmax(rows_with_content[::-1]))
        text_h = text_bot - text_top + 1
        if text_h < 3:
            return ""

        # Find blobs: contiguous column ranges with content
        col_has = np.any(
            intensity_4bit[text_top:text_bot + 1, :] > 0, axis=0
        )
        blobs: list[tuple[int, int]] = []
        start = -1
        for col in range(len(col_has) + 1):
            has = col < len(col_has) and col_has[col]
            if has and start < 0:
                start = col
            elif not has and start >= 0:
                blobs.append((start, col - 1))
                start = -1

        if not blobs:
            return ""

        # Index entries by content_w for faster lookup
        single_entries = [e for e in entries if e.get("content_w", 0) <= grid_w]
        multi_entries = [
            e for e in entries
            if len(e.get("text", "")) > 1 and e.get("content_w", 0) > 0
        ]

        result_chars = []
        i = 0
        while i < len(blobs):
            x0, x1 = blobs[i]
            blob_w = x1 - x0 + 1

            # Try multi-character entries that span consecutive blobs
            best_multi_score = -1.0
            best_multi_text = None
            best_multi_span = 0
            for entry in multi_entries:
                entry_grid = entry.get("grid")
                cw = entry.get("content_w", 0)
                if entry_grid is None or cw == 0:
                    continue
                # Find how many blobs this entry might span
                span_x1 = x0 + cw - 1
                span_count = 0
                for j in range(i, len(blobs)):
                    if blobs[j][0] <= span_x1:
                        span_count = j - i + 1
                    else:
                        break
                if span_count < 2:
                    continue
                # Check if the actual content width is close enough
                actual_x1 = blobs[i + span_count - 1][1]
                actual_w = actual_x1 - x0 + 1
                if abs(actual_w - cw) > 3:
                    continue
                candidate = self._normalize_blob(
                    intensity_4bit, x0, actual_x1,
                    text_top, text_h, grid_w, grid_h, right_align,
                )
                score = self._score_grid(candidate, entry_grid)
                if score > best_multi_score:
                    best_multi_score = score
                    best_multi_text = entry.get("text", "")
                    best_multi_span = span_count

            if best_multi_score > 0.6 and best_multi_text:
                result_chars.append(best_multi_text)
                i += best_multi_span
                continue

            # Single-blob matching
            candidate = self._normalize_blob(
                intensity_4bit, x0, x1,
                text_top, text_h, grid_w, grid_h, right_align,
            )
            best_score = -1.0
            best_text = None
            for entry in single_entries:
                entry_grid = entry.get("grid")
                if entry_grid is None:
                    continue
                score = self._score_grid(candidate, entry_grid)
                if score > best_score:
                    best_score = score
                    best_text = entry.get("text", "")

            if best_score > 0.4 and best_text:
                result_chars.append(best_text)
            i += 1

        return "".join(result_chars)

    @staticmethod
    def _normalize_blob(
        intensity_4bit: np.ndarray,
        x0: int, x1: int,
        text_top: int, text_h: int,
        grid_w: int, grid_h: int,
        right_align: bool,
    ) -> np.ndarray:
        """Place a blob into a grid at the correct alignment position.

        Extracts the tight content bounding box from the blob region,
        then places it right-aligned + bottom-aligned (digits) or
        left-aligned + bottom-aligned (text) in the target grid.
        No stretching — pixel-exact placement.
        """
        rows = min(text_h, intensity_4bit.shape[0] - text_top)
        cols = min(x1 + 1, intensity_4bit.shape[1])
        region = intensity_4bit[text_top:text_top + rows, x0:cols]

        content_mask = region > 0
        if not content_mask.any():
            return np.zeros((grid_h, grid_w), dtype=np.uint8)

        # Tight bounding box of content within region
        row_has = np.any(content_mask, axis=1)
        col_has = np.any(content_mask, axis=0)
        ct = int(np.argmax(row_has))
        cb = int(len(row_has) - 1 - np.argmax(row_has[::-1]))
        cl = int(np.argmax(col_has))
        cr = int(len(col_has) - 1 - np.argmax(col_has[::-1]))

        content = region[ct:cb + 1, cl:cr + 1]
        ch, cw = content.shape

        # Place in grid: right-align or left-align, bottom-align
        if right_align:
            gx = max(grid_w - cw, 0)
        else:
            gx = 0
        gy = max(grid_h - ch, 0)

        pw = min(cw, grid_w - gx)
        ph = min(ch, grid_h - gy)

        grid = np.zeros((grid_h, grid_w), dtype=np.uint8)
        grid[gy:gy + ph, gx:gx + pw] = content[:ph, :pw]
        return grid

    @staticmethod
    def _score_grid(candidate: np.ndarray, template: np.ndarray) -> float:
        """Score a candidate grid against a template using soft overlap.

        Uses the same formula as font_matcher.DigitMatcher:
          6 * sum(min(obs, tmpl)) - 2 * sum(tmpl) - sum(obs)
        Normalized to 0-100 range for threshold comparison.
        """
        if candidate.shape != template.shape:
            return -1.0
        c = candidate.astype(np.int32)
        t = template.astype(np.int32)
        overlap = int(np.sum(np.minimum(c, t)))
        t_sum = int(np.sum(t))
        c_sum = int(np.sum(c))
        if t_sum == 0:
            return 0.0
        # Raw score; normalize by template energy for comparability
        raw = 6 * overlap - 2 * t_sum - c_sum
        max_possible = 6 * t_sum - 2 * t_sum - t_sum  # = 3 * t_sum
        if max_possible <= 0:
            return 0.0
        return float(raw) / float(max_possible)

    # Sales column unit suffixes → multiplier to normalize to PED
    # Ordered longest-first so "mPEC" matches before "PEC", "MPED" before "PED"
    _SALES_SUFFIXES = [
        ("MPED",  1_000_000.0),    # Mega-PED
        ("kPED",  1_000.0),        # Kilo-PED
        ("PED",   1.0),            # PED
        ("mPEC",  0.00001),        # Milli-PEC (1 PEC = 0.01 PED)
        ("\u00b5PED", 0.000001),   # µPED (micro-PED, µ = U+00B5)
        ("\u03bcPED", 0.000001),   # µPED (micro-PED, µ = U+03BC)
        ("PEC",   0.01),           # PEC (1 PEC = 0.01 PED)
    ]

    @classmethod
    def _parse_cell_value(cls, text: str) -> float | None:
        """Parse a cell text value into a float.

        Handles:
        - Markup: "123.45%", "+5.00" → stripped to numeric
        - Sales: "52.7PEC", "2.51PED", "7.22kPED", "1.5MPED", "0.3mPEC"
          → normalized to PED
        - N/A / empty → None
        """
        text = text.strip()
        if not text or text.upper() in ("N/A", "NA", "N", "-"):
            return None

        # Strip leading '+'
        text = text.lstrip("+")

        # Check for sales unit suffixes (longest match first)
        for suffix, multiplier in cls._SALES_SUFFIXES:
            if text.endswith(suffix):
                num_part = text[:len(text) - len(suffix)].strip()
                try:
                    return float(num_part) * multiplier
                except ValueError:
                    return None

        # Strip trailing '%' for markup values
        text = text.rstrip("%").strip()
        try:
            return float(text)
        except ValueError:
            return None
