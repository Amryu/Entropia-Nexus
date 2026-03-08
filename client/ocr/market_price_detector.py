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

# --- Blob segmentation (calibrated via capture_market_glyphs.py) ---
# Minimum bright pixels per column to count as a "text column".
# Anti-aliased bridge pixels between characters often produce columns with
# only 1 bright pixel; real text columns have 2+.  Filtering these prevents
# characters from merging through subpixel bridges.
MARKET_MIN_COL_DENSITY = 2

# Valley-based blob splitting: column-sum threshold.
# Character gaps show column sums of ~5-22 in 4-bit space; interiors are 28+.
MARKET_VALLEY_THRESHOLD = 23

# Max single character width (no splitting attempted below this).
# Text chars are up to ~10px wide at size 14; digits ~8px at size 12.
MARKET_TEXT_MAX_SINGLE_W = 10
MARKET_DIGIT_MAX_SINGLE_W = 8

# Minimum sub-blob width after splitting; prevents fragmenting characters
# like 'm' whose internal humps create false valleys.
MARKET_MIN_SUB_BLOB_W = 3

# --- Period labels for the 5 data rows ---
PERIODS = ["1d", "7d", "30d", "90d", "365d"]

# --- STPK assets directory ---
STPK_DIR = Path(__file__).parent.parent / "assets" / "stpk"

# --- Log directory (shared with core/logger.py) ---
_LOG_DIR = Path(os.path.expanduser("~")) / ".entropia-nexus"


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
        self._tracer = None  # OcrTracer, set via set_tracer()

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

        # Print dedup: {item_name: (monotonic_time, values_tuple)}
        self._print_seen: dict[str, tuple[float, tuple]] = {}
        self._mp_logger = self._setup_mp_logger()

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

        # 4-bit threshold: the detector zeroes pixels below
        # TEXT_BRIGHTNESS_THRESHOLD (80).  After /16 quantization that
        # means 4-bit values 0-4 are never produced from game pixels.
        # Template grids must match, otherwise faint anti-aliased edge
        # pixels inflate template content_h causing alignment mismatches
        # in normalize_blob (bottom-aligned placement differs when the
        # template is taller than the observed blob).
        grid_4bit_threshold = int(TEXT_BRIGHTNESS_THRESHOLD / 16)  # = 5

        digit_path = STPK_DIR / digit_name
        if digit_path.exists():
            try:
                header, entries = read_stpk(digit_path)
                for e in entries:
                    g = e.get("grid")
                    if g is not None:
                        e["grid"] = np.where(g >= grid_4bit_threshold, g, 0).astype(np.uint8)
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
                for e in entries:
                    g = e.get("grid")
                    if g is not None:
                        e["grid"] = np.where(g >= grid_4bit_threshold, g, 0).astype(np.uint8)
                self._text_entries = entries
                self._text_grid_w = header.get("grid_w", 0)
                self._text_grid_h = header.get("grid_h", 0)
                log.info("Text STPK loaded: %d entries (%dx%d grid)",
                         len(entries), self._text_grid_w, self._text_grid_h)
            except Exception as e:
                log.warning("Failed to load text STPK %s: %s", text_path, e)
        else:
            log.info("Text STPK not found: %s (name reading disabled)", text_path)

    def set_tracer(self, tracer):
        """Attach an OcrTracer for debug logging and image output."""
        self._tracer = tracer

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

            if self._tracer and self._tracer.enabled:
                self._tracer.log("MARKET", f"template pos=({x},{y}) conf={confidence:.3f}")

            # Read all ROIs
            data = self._read_all_rois(image, x, y)
            data["confidence"] = confidence
            data["timestamp"] = datetime.now(timezone.utc).isoformat()

            # Publish debug data every tick (screen-absolute coordinates)
            gx, gy = self._game_origin
            self._event_bus.publish(EVENT_MARKET_PRICE_DEBUG, {
                "x": gx + x, "y": gy + y,
                "w": self._template_w, "h": self._template_h,
                "confidence": data["confidence"],
                "data": data,
                "game_origin": self._game_origin,
            })

            # Only publish scan event if data changed from last scan
            if self._data_changed(data):
                self._last_data = data
                self._event_bus.publish(EVENT_MARKET_PRICE_SCAN, data)
                self._print_scan(data)
                log.info("Scan: '%s' tier=%s conf=%.2f",
                         data.get("item_name", "?"),
                         data.get("tier"), data["confidence"])
                if self._tracer and self._tracer.enabled:
                    self._tracer.log("MARKET_SCAN",
                        f"'{data.get('item_name', '?')}' tier={data.get('tier')}")
                    # Save annotated debug image of the market price window area
                    self._trace_save_window(image, x, y)
        else:
            # Window not detected — clear tracking
            if self._last_pos is not None:
                if self._tracer and self._tracer.enabled:
                    self._tracer.log("MARKET", "template lost")
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
    # Formatted scan output
    # ------------------------------------------------------------------

    PRINT_DEDUP_SECONDS = 3600  # 1 hour

    @staticmethod
    def _setup_mp_logger():
        """Create a dedicated logger writing to market-price-detection.log."""
        import logging
        import logging.handlers
        mp = logging.getLogger("Nexus.MarketPriceDetection")
        mp.propagate = False
        if mp.handlers:
            return mp
        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(
                _LOG_DIR / "market-price-detection.log",
                maxBytes=256 * 1024, backupCount=1, encoding="utf-8",
            )
            fh.setFormatter(logging.Formatter(
                "%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
            ))
            mp.addHandler(fh)
            mp.setLevel(logging.INFO)
        except Exception:
            pass
        return mp

    def _print_scan(self, data: dict) -> None:
        """Print a validated, formatted scan to console and dedicated log."""
        name = data.get("item_name", "")
        if not name:
            return

        # Validate: all 10 cells must be present
        for period in PERIODS:
            if data.get(f"markup_{period}") is None:
                return
            if data.get(f"sales_{period}") is None:
                return

        # Validate markup ranges
        mode = data.get("markup_mode")
        for period in PERIODS:
            val = data[f"markup_{period}"]
            if mode == "percent" and val < 100:
                return
            elif mode == "absolute" and val < 0:
                return

        # Build values tuple for dedup comparison
        values = tuple(
            (data.get(f"markup_{p}"), data.get(f"sales_{p}")) for p in PERIODS
        )

        # Dedup: same item + same values within 1 hour → skip
        now = time.monotonic()
        last = self._print_seen.get(name)
        if last:
            last_time, last_values = last
            if last_values == values and (now - last_time) < self.PRINT_DEDUP_SECONDS:
                return

        self._print_seen[name] = (now, values)

        # Format output
        parts = []
        for period in PERIODS:
            markup_raw = data.get(f"markup_{period}_raw", "")
            sales_val = data[f"sales_{period}"]
            parts.append(f"{period}: {markup_raw} / {self._format_sales(sales_val)}")
        line = f"[Market Price] {name} — " + " | ".join(parts)

        print(line)
        self._mp_logger.info(line)

    @staticmethod
    def _format_sales(value: float) -> str:
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f} MPED"
        if value >= 1_000:
            return f"{value / 1_000:.2f} kPED"
        if value >= 0.01:
            return f"{value:.2f} PED"
        return f"{value * 100:.2f} PEC"

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
        cell_confidences: list[float] = []

        # Item name (row 1 + optional row 2)
        roi_r1 = getattr(self._config, "market_price_roi_name_row1", None)
        roi_r2 = getattr(self._config, "market_price_roi_name_row2", None)
        name_parts = []
        name_confs: list[float] = []
        if roi_r1:
            region = self._get_roi_region(image, tx, ty, roi_r1)
            if region is not None and region.size > 0:
                text, conf = self._read_text(region)
                if text:
                    name_parts.append(text)
                    name_confs.append(conf)
        if roi_r2:
            region = self._get_roi_region(image, tx, ty, roi_r2)
            if region is not None and region.size > 0:
                text, conf = self._read_text(region)
                if text:
                    name_parts.append(text)
                    name_confs.append(conf)
        cell_confidences.append(min(name_confs) if name_confs else 0.0)
        raw_name = " ".join(name_parts).strip()
        normalized = self._normalize_item_name(raw_name)
        data["item_name"] = normalized
        # Include raw OCR name if normalization changed it (server can try both)
        if normalized != raw_name:
            data["item_name_raw"] = raw_name
        if self._tracer and self._tracer.enabled:
            self._tracer.log("MARKET_NAME", f"raw='{raw_name}' norm='{normalized}'")

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
                        value, raw, conf = self._read_cell(region)
                        key = f"{metric}_{period}"
                        data[key] = value
                        data[f"{key}_raw"] = raw
                        cell_confidences.append(conf)
                        if self._tracer and self._tracer.enabled:
                            self._tracer.log("MARKET_CELL", f"{key}={value}")
                    else:
                        errors.append(f"{metric}_{period}: out of bounds")

            # Detect markup mode from first non-empty markup raw text
            for period in PERIODS:
                raw = data.get(f"markup_{period}_raw", "")
                if raw:
                    data["markup_mode"] = "percent" if "%" in raw else "absolute"
                    break

        # Tier (optional — does not contribute to combined confidence)
        roi_tier = getattr(self._config, "market_price_roi_tier", None)
        if roi_tier:
            region = self._get_roi_region(image, tx, ty, roi_tier)
            if region is not None and region.size > 0:
                tier_val, _tier_conf = self._read_cell_number(region)
                if tier_val is not None:
                    try:
                        data["tier"] = int(tier_val)
                    except (ValueError, TypeError):
                        pass
                if self._tracer and self._tracer.enabled:
                    self._tracer.log("MARKET_CELL", f"tier={data.get('tier')}")

        # Aggregate OCR confidence (mean of name + cell confidences)
        data["ocr_confidence"] = (
            sum(cell_confidences) / len(cell_confidences)
            if cell_confidences else 0.0
        )

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
        - Uppercase → Title Case (the game displays item names in all-caps)
        - Trailing "..." from the game's text truncation
        - Multiple spaces from line-break joining
        - Leading/trailing whitespace

        Both the raw and normalized names are sent to the server, which
        resolves via case-insensitive and prefix matching.
        """
        name = raw.strip()
        # Strip trailing ellipsis (game truncates long names)
        if name.endswith("..."):
            name = name[:-3].rstrip()
        # Collapse multiple spaces (artifact of line-break joining)
        name = " ".join(name.split())
        # Convert all-caps to title case (game shows names in uppercase)
        if name == name.upper():
            name = name.title()
        return name

    # ------------------------------------------------------------------
    # OCR reading (STPK-based)
    # ------------------------------------------------------------------

    def _read_cell_number(self, region: np.ndarray) -> tuple[float | None, float]:
        """Read a numeric value from a cell region (BGR).

        Handles formats: "123.45%", "+123.45", "N/A", plain "12.34".
        Returns (numeric_value, confidence). Empty cells get confidence 1.0
        (empty is a valid state). Unreadable cells get 0.0.
        """
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        # Check if cell is truly empty: no pixels bright enough to be text
        threshold = getattr(
            self._config, "market_price_text_threshold",
            TEXT_BRIGHTNESS_THRESHOLD,
        )
        if int(np.max(gray)) < threshold:
            return None, 1.0

        # If STPK digit entries are available, use grid-based matching
        if self._digit_entries:
            text, conf = self._match_stpk_digits(region)
            if text:
                return self._parse_cell_value(text), conf

        # Fallback: no STPK available
        return None, 0.0

    def _read_cell(self, region: np.ndarray) -> tuple[float | None, str, float]:
        """Read a cell and return (parsed_value, raw_ocr_text, confidence).

        Empty cells get confidence 1.0 (valid state). Unreadable cells get 0.0.
        """
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        threshold = getattr(
            self._config, "market_price_text_threshold",
            TEXT_BRIGHTNESS_THRESHOLD,
        )
        if int(np.max(gray)) < threshold:
            return None, "", 1.0
        if self._digit_entries:
            text, conf = self._match_stpk_digits(region)
            if text:
                return self._parse_cell_value(text), text, conf
        return None, "", 0.0

    def _read_text(self, region: np.ndarray) -> tuple[str, float]:
        """Read text from a region (BGR) using text STPK templates.

        Returns (matched_text, confidence). Empty/unreadable returns ("", 0.0).
        """
        if not self._text_entries:
            return "", 0.0

        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        threshold = getattr(
            self._config, "market_price_text_threshold",
            TEXT_BRIGHTNESS_THRESHOLD,
        )
        if int(np.max(gray)) < threshold:
            return "", 0.0

        return self._match_stpk_text(region)

    def _match_stpk_digits(self, region: np.ndarray) -> tuple[str, float]:
        """Match digit STPK entries against a BGR cell image.

        Uses blob segmentation to find contiguous character groups, then
        matches each blob against STPK entries.  Wide blobs are first
        tested against multi-character entries (N/A, kPED, etc.) before
        being scored as single characters.

        Returns (matched_text, confidence) where confidence is the minimum
        per-character score (weakest link), or 0.0 if no match.
        """
        if not self._digit_entries or self._digit_grid_w == 0:
            return "", 0.0
        text, scores = self._match_stpk_blobs(
            region, self._digit_entries,
            self._digit_grid_w, self._digit_grid_h,
            right_align=True,
        )
        return text, (min(scores) if scores else 0.0)

    # Characters likely to appear in item names
    _TEXT_ALLOWED = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "(),.-' "
    )

    def _match_stpk_text(self, region: np.ndarray) -> tuple[str, float]:
        """Match text STPK entries against a BGR region.

        Uses blob segmentation, same as digits but with left-aligned
        text templates.  Filters entries to only item-name-plausible
        characters to prevent false matches from /, !, #, etc.

        Returns (matched_text, confidence) where confidence is the minimum
        per-character score (weakest link), or 0.0 if no match.
        """
        if not self._text_entries or self._text_grid_w == 0:
            return "", 0.0
        # Filter to item-name-plausible characters
        filtered = [
            e for e in self._text_entries
            if e.get("text", "") in self._TEXT_ALLOWED
        ]
        text, scores = self._match_stpk_blobs(
            region, filtered,
            self._text_grid_w, self._text_grid_h,
            right_align=False,
        )
        return text, (min(scores) if scores else 0.0)

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
    ) -> tuple[str, list[float]]:
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
            return "", []

        text_top = int(np.argmax(rows_with_content))
        text_bot = int(len(rows_with_content) - 1 - np.argmax(rows_with_content[::-1]))
        text_h = text_bot - text_top + 1
        if text_h < 3:
            return "", []

        # Find blobs: contiguous column ranges with sufficient text density.
        # Using column density >= MARKET_MIN_COL_DENSITY filters out single
        # anti-aliased pixels that would otherwise bridge character gaps.
        text_region = intensity_4bit[text_top:text_bot + 1, :]
        col_density = np.sum(text_region > 0, axis=0)
        col_has = col_density >= MARKET_MIN_COL_DENSITY
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
            return "", []

        # Split wide blobs at intensity valleys (character boundaries)
        max_single_w = (MARKET_DIGIT_MAX_SINGLE_W if right_align
                        else MARKET_TEXT_MAX_SINGLE_W)
        blobs = self._split_blobs_at_valleys(
            intensity_4bit, blobs, text_top, text_h, max_single_w,
        )
        # Merge narrow pairs (e.g. '"' rendered as two tick marks)
        blobs = self._merge_narrow_pairs(blobs)

        # Compute median inter-blob gap to detect word spaces
        gaps = []
        for j in range(1, len(blobs)):
            gap = blobs[j][0] - blobs[j - 1][1] - 1
            if gap > 0:
                gaps.append(gap)
        # Word space threshold: midpoint between char gaps and word gaps.
        # Typical char gap = 1-2px, word gap = 5-7px.
        if gaps:
            median_gap = float(sorted(gaps)[len(gaps) // 2])
            space_threshold = max(median_gap * 2, 4)
        else:
            space_threshold = 4

        # Index entries by content_w for faster lookup
        single_entries = [e for e in entries if e.get("content_w", 0) <= grid_w]
        multi_entries = [
            e for e in entries
            if len(e.get("text", "")) > 1 and e.get("content_w", 0) > 0
        ]

        result_chars: list[str] = []
        result_scores: list[float] = []
        # Per-blob tracking for disambiguation (parallel to result_scores)
        all_entry_scores: list[dict[str, float]] = []
        blob_positions: list[tuple[int, int]] = []
        i = 0
        while i < len(blobs):
            x0, x1 = blobs[i]
            blob_w = x1 - x0 + 1

            # Insert space if gap from previous blob is large enough
            if i > 0:
                gap = x0 - blobs[i - 1][1] - 1
                if gap >= space_threshold:
                    result_chars.append(" ")

            # Try multi-character entries that span consecutive blobs
            best_multi_score = -1.0
            best_multi_text = None
            best_multi_span = 0
            for entry in multi_entries:
                cw = entry.get("content_w", 0)
                if cw == 0:
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
                if abs(actual_w - cw) > 5:
                    continue
                # Use grid matching (same approach as font_matcher)
                entry_grid = entry.get("grid")
                if entry_grid is not None:
                    candidate = self._normalize_blob(
                        intensity_4bit, x0, actual_x1,
                        text_top, text_h, grid_w, grid_h, right_align,
                    )
                    score = self._score_grid(candidate, entry_grid)
                    if score > best_multi_score:
                        best_multi_score = score
                        best_multi_text = entry.get("text", "")
                        best_multi_span = span_count

            if best_multi_score > 0.4 and best_multi_text:
                if self._tracer and self._tracer.enabled:
                    self._tracer.log("MARKET_OCR",
                        f"multi x={x0}-{blobs[i + best_multi_span - 1][1]} "
                        f"'{best_multi_text}' s={best_multi_score:.3f}")
                result_chars.append(best_multi_text)
                result_scores.append(best_multi_score)
                all_entry_scores.append({best_multi_text: best_multi_score})
                blob_positions.append((x0, blobs[i + best_multi_span - 1][1]))
                i += best_multi_span
                continue

            # Single-blob matching: use grid matching (4-bit soft overlap),
            # like the skill scanner's font_matcher. Grid matching is more
            # robust with font-generated Scaleform templates since it avoids
            # bitmap resize interpolation artifacts.
            best_score = -1.0
            best_text = None
            entry_scores: dict[str, float] = {}

            candidate = self._normalize_blob(
                intensity_4bit, x0, x1,
                text_top, text_h, grid_w, grid_h, right_align,
            )
            for entry in single_entries:
                entry_grid = entry.get("grid")
                if entry_grid is None:
                    continue
                score = self._score_grid(candidate, entry_grid)
                char = entry.get("text", "")
                if len(char) == 1:
                    entry_scores[char] = max(
                        entry_scores.get(char, -999.0), score)
                if score > best_score:
                    best_score = score
                    best_text = char

            if best_score > 0.4 and best_text:
                result_chars.append(best_text)
                result_scores.append(best_score)
                all_entry_scores.append(entry_scores)
                blob_positions.append((x0, x1))
                if self._tracer and self._tracer.enabled:
                    self._tracer.log("MARKET_OCR",
                        f"x={x0}-{x1} '{best_text}' s={best_score:.3f}")
            else:
                result_scores.append(0.0)
                all_entry_scores.append(entry_scores)
                blob_positions.append((x0, x1))
                if self._tracer and self._tracer.enabled:
                    self._tracer.log("MARKET_OCR",
                        f"x={x0}-{x1} NO_MATCH best_s={best_score:.3f}")
            i += 1

        # Apply disambiguation tiebreakers
        from .market_disambiguation import (
            apply_digit_tiebreakers, apply_text_tiebreakers,
        )
        if right_align:
            # Digit mode: build classified list for digit tiebreakers
            classified = []
            score_idx = 0
            for ci, ch in enumerate(result_chars):
                if ch == " ":
                    continue
                if score_idx >= len(all_entry_scores):
                    break
                scores_dict = all_entry_scores[score_idx]
                if ch in "0123456789" and len(ch) == 1:
                    digit_scores = [
                        scores_dict.get(str(d), -999.0) for d in range(10)
                    ]
                    classified.append({
                        "char_idx": ci, "score_idx": score_idx,
                        "x0": blob_positions[score_idx][0],
                        "x1": blob_positions[score_idx][1],
                        "digit": int(ch),
                        "score": result_scores[score_idx],
                        "scores": digit_scores,
                    })
                score_idx += 1
            if classified:
                apply_digit_tiebreakers(
                    classified, intensity_4bit,
                    text_top, text_h, grid_w, grid_h,
                )
                # Apply overrides back
                for c in classified:
                    result_chars[c["char_idx"]] = str(c["digit"])
                    result_scores[c["score_idx"]] = c["score"]
        else:
            # Text mode: apply text tiebreakers
            apply_text_tiebreakers(
                result_chars, result_scores, all_entry_scores,
                intensity_4bit, blob_positions,
                text_top, text_h, grid_w, grid_h,
            )

        return "".join(result_chars), result_scores

    @staticmethod
    def _split_blobs_at_valleys(
        intensity_4bit: np.ndarray,
        blobs: list[tuple[int, int]],
        text_top: int,
        text_h: int,
        max_single_w: int,
    ) -> list[tuple[int, int]]:
        """Split wide blobs at low-intensity column valleys.

        Character boundaries show column sums of ~5-22 in 4-bit space,
        while character interiors are 28+.  Columns below MARKET_VALLEY_THRESHOLD
        are treated as split points.  This is more robust than local-minima
        detection because it uses an absolute threshold calibrated against
        game screenshots rather than relative comparisons.
        """
        result: list[tuple[int, int]] = []
        rows = min(text_h, intensity_4bit.shape[0] - text_top)

        for x0, x1 in blobs:
            w = x1 - x0 + 1
            if w <= max_single_w:
                result.append((x0, x1))
                continue

            # Compute column intensity profile within the text band
            region = intensity_4bit[text_top:text_top + rows, x0:x1 + 1]
            col_sums = region.sum(axis=0)

            # Find split points: columns where intensity is below threshold.
            # Group consecutive valley columns, split at each group boundary.
            sub_start = 0
            i = 0
            sub_blobs: list[tuple[int, int]] = []
            while i < len(col_sums):
                if col_sums[i] < MARKET_VALLEY_THRESHOLD:
                    # Found a valley — record the sub-blob before it
                    if i > sub_start:
                        sub_blobs.append((x0 + sub_start, x0 + i - 1))
                    # Skip through the valley
                    while i < len(col_sums) and col_sums[i] < MARKET_VALLEY_THRESHOLD:
                        i += 1
                    sub_start = i
                else:
                    i += 1

            # Last sub-blob
            if sub_start < len(col_sums):
                sub_blobs.append((x0 + sub_start, x1))

            if len(sub_blobs) > 1:
                # Reject if multiple fragments are too narrow (indicates
                # internal character structure, e.g. 'm' humps)
                narrow = sum(1 for sb in sub_blobs
                             if sb[1] - sb[0] + 1 < MARKET_MIN_SUB_BLOB_W)
                if narrow > 1:
                    result.append((x0, x1))
                else:
                    result.extend(sub_blobs)
            else:
                result.append((x0, x1))

        return result

    @staticmethod
    def _merge_narrow_pairs(
        blobs: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """Merge pairs of very narrow, closely-spaced blobs.

        Characters like '"' are rendered as two separate tick marks with a
        small gap.  This merges adjacent blobs where both are <= 2px wide
        and the gap between them is <= 2px.
        """
        if len(blobs) < 2:
            return blobs

        MAX_TICK_W = 2
        MAX_GAP = 2

        result: list[tuple[int, int]] = []
        i = 0
        while i < len(blobs):
            if i + 1 < len(blobs):
                x0a, x1a = blobs[i]
                x0b, x1b = blobs[i + 1]
                wa = x1a - x0a + 1
                wb = x1b - x0b + 1
                gap = x0b - x1a - 1
                if wa <= MAX_TICK_W and wb <= MAX_TICK_W and gap <= MAX_GAP:
                    result.append((x0a, x1b))
                    i += 2
                    continue
            result.append(blobs[i])
            i += 1
        return result

    from .skill_disambiguation import normalize_blob as _normalize_blob_fn
    _normalize_blob = staticmethod(_normalize_blob_fn)

    @staticmethod
    def _score_grid_raw(candidate: np.ndarray, template: np.ndarray) -> float:
        """Score a candidate grid against a template using soft overlap.

        Uses the same formula as font_matcher.DigitMatcher:
          6 * sum(min(obs, tmpl)) - 2 * sum(tmpl) - sum(obs)
        Normalized by 3 * sum(tmpl) for comparability.
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
        raw = 6 * overlap - 2 * t_sum - c_sum
        max_possible = 3 * t_sum
        if max_possible <= 0:
            return 0.0
        return float(raw) / float(max_possible)

    @staticmethod
    def _score_grid(candidate: np.ndarray, template: np.ndarray) -> float:
        """Shift-tolerant grid scoring.

        Each game character renders at a slightly different subpixel position,
        so the normalized blob may be shifted ±1 column relative to the
        template.  We try horizontal shifts of -1, 0, +1 and return the
        best score.
        """
        best = MarketPriceDetector._score_grid_raw(candidate, template)
        h, w = candidate.shape
        for shift in (-1, 1):
            shifted = np.zeros_like(candidate)
            if shift > 0:
                shifted[:, shift:] = candidate[:, :-shift]
            else:
                shifted[:, :w + shift] = candidate[:, -shift:]
            s = MarketPriceDetector._score_grid_raw(shifted, template)
            if s > best:
                best = s
        return best

    @staticmethod
    def _extract_blob_gray(
        intensity: np.ndarray,
        x0: int, x1: int,
        text_top: int, text_h: int,
    ) -> np.ndarray | None:
        """Extract a blob's tight bounding box from the 8-bit intensity image."""
        rows = min(text_h, intensity.shape[0] - text_top)
        cols_end = min(x1 + 1, intensity.shape[1])
        region = intensity[text_top:text_top + rows, x0:cols_end]

        mask = region > 0
        if not mask.any():
            return None

        row_has = np.any(mask, axis=1)
        col_has = np.any(mask, axis=0)
        ct = int(np.argmax(row_has))
        cb = int(len(row_has) - 1 - np.argmax(row_has[::-1]))
        cl = int(np.argmax(col_has))
        cr = int(len(col_has) - 1 - np.argmax(col_has[::-1]))

        return region[ct:cb + 1, cl:cr + 1].copy()

    @staticmethod
    def _score_bitmap(blob_gray: np.ndarray, template_bmp: np.ndarray) -> float:
        """Score a blob against a template bitmap using normalized correlation.

        Resizes the template to match the blob's height, then uses
        cv2.matchTemplate with TM_CCOEFF_NORMED for robust matching
        that tolerates anti-aliasing differences.  Applies a width
        similarity penalty to prevent wider templates from getting
        artificially high scores by sliding a narrow blob inside them.
        """
        bh, bw = blob_gray.shape
        th, tw = template_bmp.shape
        if bh < 3 or bw < 2 or th < 3 or tw < 2:
            return -1.0

        # Resize template to match blob height, preserving aspect ratio
        scale = bh / th
        new_tw = max(1, int(round(tw * scale)))
        new_th = bh
        resized = cv2.resize(
            template_bmp, (new_tw, new_th),
            interpolation=cv2.INTER_LINEAR,
        )

        # Width tolerance: if template is much wider/narrower, reject
        w_ratio = bw / new_tw if new_tw > 0 else 0
        if w_ratio < 0.5 or w_ratio > 2.0:
            return -1.0

        # Pad the smaller of the two to make matchTemplate work
        if new_tw <= bw:
            result = cv2.matchTemplate(
                blob_gray, resized, cv2.TM_CCOEFF_NORMED,
            )
        else:
            result = cv2.matchTemplate(
                resized, blob_gray, cv2.TM_CCOEFF_NORMED,
            )

        raw_score = float(result.max())

        # Apply width similarity penalty: templates whose width doesn't
        # closely match the blob width get penalized.  This prevents
        # wider templates (e.g. O=10px) from outscoring narrower ones
        # (e.g. C=9px) when the blob is 8px wide.
        w_diff = abs(bw - new_tw)
        if w_diff > 0:
            penalty = 1.0 - 0.05 * w_diff
            raw_score *= max(penalty, 0.5)

        return raw_score

    # Sales column unit suffixes → multiplier to normalize to PED
    # Ordered longest-first so "mPEC" matches before "PEC", "MPED" before "PED"
    _SALES_SUFFIXES = [
        ("MPED",  1_000_000.0),    # Mega-PED
        ("kPED",  1_000.0),        # Kilo-PED
        ("PED",   1.0),            # PED
        ("mPEC",  0.00001),        # Milli-PEC (1 PEC = 0.01 PED)
        ("uPEC",  0.00000001),     # Micro-PEC (game displays µ as 'u')
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
                    val = float(num_part) * multiplier
                    return 0.0 if val == 0.0 else val  # normalize -0.0
                except ValueError:
                    return None

        # Strip trailing '%' for markup values
        text = text.rstrip("%").strip()
        try:
            val = float(text)
            return 0.0 if val == 0.0 else val  # normalize -0.0
        except ValueError:
            return None

    def _trace_save_window(self, image: np.ndarray, tx: int, ty: int):
        """Save an annotated debug image of the market price window area."""
        if not self._tracer or cv2 is None:
            return
        # Crop a generous area around the detected window
        ih, iw = image.shape[:2]
        margin = 10
        x1 = max(0, tx - 100)
        y1 = max(0, ty - margin)
        x2 = min(iw, tx + self._template_w + 200)
        y2 = min(ih, ty + 280)
        crop = image[y1:y2, x1:x2].copy()
        self._tracer.save_image("market_price", crop,
                                suffix=str(self._last_data.get("item_name", ""))[:40])
