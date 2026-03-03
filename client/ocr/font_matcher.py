import json
import os
import threading
import time
import numpy as np
from pathlib import Path
from typing import Optional

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from PIL import ImageFont, Image, ImageDraw
except ImportError:
    ImageFont = None

from ..core.logger import get_logger

log = get_logger("FontMatcher")

ASSETS_DIR = Path(__file__).parent.parent / "assets"
FONT_PATH = ASSETS_DIR / "arial-unicode-bold.ttf"
ASSETS_TEMPLATES_DIR = ASSETS_DIR / "rendered_templates"
CALIBRATION_FILE = Path("./data/font_calibration.json")
CAPTURED_DIR = Path("./data/captured_templates")
RENDERED_DIR = Path("./data/rendered_templates")

# Match thresholds for TM_CCOEFF_NORMED (penalizes both extra and missing).
# Binary-to-binary matching at 4x resolution; 0.65 accommodates slight
# rendering differences between game (ClearType) and PIL (FreeType).
SKILL_THRESHOLD = 0.65
RANK_THRESHOLD = 0.65
DIGIT_THRESHOLD = 0.65

# Inter-glyph spacing in rendered templates (pixels between glyph bounding boxes)
# Game renders text very tightly (~1px between glyphs)
GLYPH_GAP = 1

# Binary threshold (must match preprocessor)
BINARY_THRESHOLD = 110

# Minimum match score a NEW capture must achieve against its source cell
# before it's saved to disk.  This prevents saving noisy or misaligned
# templates (e.g. from a moved window).
CAPTURE_MIN_SCORE = 0.95

# Minimum bright pixels per column to count as a "text column" (not noise).
# At BINARY_THRESHOLD, real text columns have multiple bright pixels
# stacked vertically; noise columns have ≤1.
MIN_COL_DENSITY = 2

# Maximum gap (px) to bridge when grouping dense columns into text runs.
# Covers inter-character spacing and the space character at game font sizes.
# At 13-14px bold, inter-word spaces are 6-7px wide (e.g. "Grand Master"=7).
MAX_TEXT_GAP = 8

# Maximum digits expected in a single points cell (e.g. "123456")
MAX_DIGITS = 6

# Scale factor for template matching.  PIL-rendered templates are rasterized
# at font_size * MATCH_SCALE natively (no upscaling needed).  ROI cell images
# are upscaled to MATCH_SCALE using bicubic + binarize.  4x gives
# matchTemplate enough pixels to discriminate similar glyphs while keeping
# images small enough for fast matching.
MATCH_SCALE = 4



class FontMatcher:
    """Recognizes game text via template matching using the known game font.

    Pre-renders all known skill names, rank names, and digit characters as
    binary template images, then matches them against preprocessed game
    screenshots using cv2.matchTemplate().
    """

    def __init__(self, skill_names: list[str], rank_names: list[str],
                 font_path: str = None):
        if cv2 is None:
            raise ImportError("opencv-python is required")

        self._font_path = font_path or str(FONT_PATH)
        self._skill_names = skill_names
        self._rank_names = rank_names

        self._font: Optional[ImageFont.FreeTypeFont] = None
        self._font_hires: Optional[ImageFont.FreeTypeFont] = None
        self._font_size: int = 0
        self._text_zone_height: int = 0
        self._calibrated = False
        self._render_mode: str = "native"  # "native" or "tight"

        # Pre-rendered templates: {name: grayscale_image}
        self._skill_templates: dict[str, np.ndarray] = {}
        self._rank_templates: dict[str, np.ndarray] = {}
        self._digit_templates: dict[str, np.ndarray] = {}

        # Width index for fast candidate filtering: {width: [(name, template), ...]}
        self._skill_width_index: dict[int, list[tuple[str, np.ndarray]]] = {}
        self._rank_width_index: dict[int, list[tuple[str, np.ndarray]]] = {}

        # Digit advance width (all digits have same advance in this font)
        self._digit_advance: int = 0


        # Exact-match lookup: image_key → name (for game-captured templates)
        self._captured_skill_lookup: dict[bytes, str] = {}
        self._captured_rank_lookup: dict[bytes, str] = {}

        # Background pre-initialization: signals when templates are loaded
        self._ready = threading.Event()
        # Track which settings the current templates were rendered for
        self._rendered_cache_key: str = ""

    def _load_font(self, size: int) -> bool:
        """Load font at given size. Returns False if font file or Pillow is missing."""
        if ImageFont is None:
            self._font = None
            self._font_hires = None
            return False
        font_path = Path(self._font_path)
        if not font_path.exists():
            self._font = None
            self._font_hires = None
            return False
        self._font = ImageFont.truetype(self._font_path, size)
        self._font_hires = ImageFont.truetype(self._font_path, size * MATCH_SCALE)
        return True

    def pre_initialize(self) -> None:
        """Pre-render (or load cached) templates with default settings.

        Call from a background thread at startup so templates are ready
        before the first scan.  `calibrate()` will skip the expensive
        render step if the settings haven't changed.
        """
        t0 = time.monotonic()
        try:
            # Use defaults — calibrate() will re-render only if settings differ
            self._font_size = 13
            self._render_mode = "native"
            self._load_font(13)
            self._render_all_templates()
            self._load_captured_templates()
            log.info("Pre-initialized templates in %.1fs (size=%d, mode=%s)",
                     time.monotonic() - t0, self._font_size, self._render_mode)
        except Exception as e:
            log.error("Pre-initialization failed: %s", e)
        finally:
            self._ready.set()

    @property
    def calibrated(self) -> bool:
        return self._calibrated

    @property
    def font_size(self) -> int:
        return self._font_size

    @property
    def font_path(self) -> str:
        return self._font_path

    def get_skill_template(self, name: str) -> Optional[np.ndarray]:
        """Return the pre-rendered template image for a skill name."""
        return self._skill_templates.get(name)

    def best_skill_match(self, cell: np.ndarray) -> Optional[tuple[str, float]]:
        """Return the best skill name match regardless of confidence threshold.

        Uses threshold=-1.0 to guarantee a result for any cell with visible
        text, since TM_CCOEFF_NORMED can return negative scores when PIL
        templates differ significantly from the Scaleform game rendering.
        """
        if not self._calibrated or not self._skill_width_index:
            return None
        return self._match_against_index(
            cell, self._skill_width_index, threshold=-1.0)

    def best_rank_match(self, cell: np.ndarray) -> Optional[tuple[str, float]]:
        """Return the best rank match regardless of confidence threshold."""
        if not self._calibrated or not self._rank_width_index:
            return None
        return self._match_against_index(
            cell, self._rank_width_index, threshold=-1.0)

    def calibrate(self, panel_height: int) -> None:
        """Calibrate font size for the detected panel dimensions and render all templates.

        If a saved calibration exists for this panel height, loads it.
        Otherwise uses defaults (size 13, native mode).
        Waits for pre_initialize() if it's still running.

        Args:
            panel_height: Height of the skills window panel in pixels.
        """
        # Wait for background pre-init to finish (if running)
        self._ready.wait()

        # Must exactly mirror the cell height calculation in orchestrator:
        #   row_height = max(20, round(wh * 0.045))
        #   text_h = int(row_height * 0.70)
        row_height = max(20, round(panel_height * 0.045))
        self._text_zone_height = int(row_height * 0.70)
        self._panel_height = panel_height

        # Try to load saved calibration for this panel height
        saved = self._load_calibration(panel_height)
        if saved:
            font_size = saved["font_size"]
            render_mode = saved["render_mode"]
            log.info("Font: size=%d mode=%s (saved, score=%.3f)",
                     font_size, render_mode, saved.get("avg_score", 0))
        else:
            font_size = 13
            render_mode = "native"
            log.info("Font: size=%d mode=%s (default)", font_size, render_mode)

        cache_key = f"s{font_size}_{render_mode}"
        if cache_key == self._rendered_cache_key:
            log.info("Templates already loaded for %s — skipping render", cache_key)
            self._calibrated = True
            return

        # Settings differ from what's loaded — re-render
        self._font_size = font_size
        self._render_mode = render_mode
        self._load_font(self._font_size)

        self._render_all_templates()
        self._load_captured_templates()
        self._calibrated = True

    def auto_calibrate(self, sample_cells: list[np.ndarray]) -> None:
        """Refine rendering mode and font size by testing against actual game cells.

        Tries both rendering modes ("native" and "tight") and font sizes 11-15,
        picking the combination with the highest average match score.
        Saves the result to disk for future runs.

        Requires the font file for rendering non-cached combos.  If the font
        is unavailable, skips combos that have no cached/shipped templates.

        Args:
            sample_cells: List of grayscale cell images from the game (name column).
        """
        if not sample_cells:
            return

        best_mode = self._render_mode
        best_size = self._font_size
        best_avg = 0.0

        for size in range(11, 16):
            for mode in ("native", "tight"):
                self._load_font(size)
                self._font_size = size
                self._render_mode = mode
                try:
                    self._render_all_templates()
                except RuntimeError:
                    # No cached templates and no font — skip this combo
                    continue

                # Score each sample cell against all templates
                scores = []
                for cell in sample_cells:
                    result = self._match_against_index(
                        cell, self._skill_width_index, threshold=0.0)
                    if result:
                        scores.append(result[1])

                if not scores:
                    continue

                avg = sum(scores) / len(scores)
                log.debug("Auto-calibrate: size=%d mode=%s avg_score=%.3f "
                          "(%d/%d cells matched)",
                          size, mode, avg, len(scores), len(sample_cells))

                if avg > best_avg:
                    best_avg = avg
                    best_mode = mode
                    best_size = size

        # Apply best settings
        self._font_size = best_size
        self._load_font(best_size)
        self._render_mode = best_mode
        self._render_all_templates()

        log.info("Auto-calibrated: size=%d, mode=%s, avg_score=%.3f",
                 best_size, best_mode, best_avg)

        # Save for future runs
        self._save_calibration(best_size, best_mode, best_avg)

    def _save_calibration(self, font_size: int, render_mode: str,
                          avg_score: float) -> None:
        """Save calibration result to disk."""
        try:
            CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 2,
                "panel_height": getattr(self, '_panel_height', 0),
                "font_size": font_size,
                "render_mode": render_mode,
                "avg_score": round(avg_score, 4),
            }
            with open(CALIBRATION_FILE, "w") as f:
                json.dump(data, f, indent=2)
            log.debug("Saved calibration to %s", CALIBRATION_FILE)
        except Exception as e:
            log.warning("Failed to save calibration: %s", e)

    @staticmethod
    def _load_calibration(panel_height: int) -> Optional[dict]:
        """Load saved calibration if it matches the current panel height."""
        try:
            if not CALIBRATION_FILE.exists():
                return None
            with open(CALIBRATION_FILE) as f:
                data = json.load(f)
            if data.get("version") != 2:
                log.debug("Saved calibration version mismatch — ignoring")
                return None
            if data.get("panel_height") != panel_height:
                log.debug("Saved calibration is for panel_height=%d, "
                          "current is %d — ignoring",
                          data.get("panel_height"), panel_height)
                return None
            return data
        except Exception as e:
            log.debug("Failed to load calibration: %s", e)
            return None

    def _render_all_templates(self) -> None:
        """Render all skill, rank, and digit templates.

        Tries three sources in order:
        1. Runtime data cache (./data/rendered_templates/)
        2. Shipped asset templates (client/assets/rendered_templates/)
        3. PIL font rendering (requires font file — development only)

        Raises RuntimeError if all three sources fail.
        """
        cache_key = f"s{self._font_size}_{self._render_mode}"
        cache_dir = RENDERED_DIR / cache_key

        # 1. Try runtime data cache
        if self._load_rendered_cache(cache_dir):
            self._rendered_cache_key = cache_key
            return

        # 2. Try shipped asset templates
        asset_dir = ASSETS_TEMPLATES_DIR / cache_key
        if self._load_rendered_cache(asset_dir):
            self._rendered_cache_key = cache_key
            self._save_rendered_cache(cache_dir)  # copy to data for next time
            return

        # 3. Fall back to PIL font rendering (development only)
        if not self._font or not self._font_hires:
            raise RuntimeError(
                f"No cached templates for {cache_key} and font file not available. "
                "Run: python -m client.scripts.generate_templates"
            )

        t0 = time.monotonic()

        # Skills
        self._skill_templates.clear()
        self._skill_width_index.clear()
        for name in self._skill_names:
            tpl = self._render_template(name)
            if tpl is not None:
                tpl = self._to_binary(tpl)
                self._skill_templates[name] = tpl
                w = tpl.shape[1]
                self._skill_width_index.setdefault(w, []).append((name, tpl))

        # Ranks
        self._rank_templates.clear()
        self._rank_width_index.clear()
        for name in self._rank_names:
            tpl = self._render_template(name)
            if tpl is not None:
                tpl = self._to_binary(tpl)
                self._rank_templates[name] = tpl
                w = tpl.shape[1]
                self._rank_width_index.setdefault(w, []).append((name, tpl))

        # Digits (0-9)
        self._digit_templates.clear()
        for ch in "0123456789":
            tpl = self._render_template(ch)
            if tpl is not None:
                self._digit_templates[ch] = self._to_binary(tpl)

        if self._digit_templates:
            self._digit_advance = self._digit_templates["0"].shape[1]

        elapsed = time.monotonic() - t0
        log.info("Rendered %d skills, %d ranks, %d digits in %.1fs",
                 len(self._skill_templates), len(self._rank_templates),
                 len(self._digit_templates), elapsed)

        self._save_rendered_cache(cache_dir)
        self._rendered_cache_key = cache_key

    def _load_rendered_cache(self, cache_dir: Path) -> bool:
        """Try to load pre-rendered templates from disk cache.

        Returns True if cache was loaded successfully, False on miss.
        """
        skills_dir = cache_dir / "skills"
        ranks_dir = cache_dir / "ranks"
        digits_dir = cache_dir / "digits"

        if not skills_dir.exists():
            return False

        t0 = time.monotonic()
        try:
            # Skills
            self._skill_templates.clear()
            self._skill_width_index.clear()
            for path in skills_dir.glob("*.png"):
                name = self._name_from_filename(path.stem)
                if name not in self._skill_names:
                    continue
                tpl = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if tpl is None:
                    continue
                self._skill_templates[name] = tpl
                w = tpl.shape[1]
                self._skill_width_index.setdefault(w, []).append((name, tpl))

            # Ranks
            self._rank_templates.clear()
            self._rank_width_index.clear()
            for path in ranks_dir.glob("*.png"):
                name = self._name_from_filename(path.stem)
                if name not in self._rank_names:
                    continue
                tpl = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if tpl is None:
                    continue
                self._rank_templates[name] = tpl
                w = tpl.shape[1]
                self._rank_width_index.setdefault(w, []).append((name, tpl))

            # Digits
            self._digit_templates.clear()
            for path in digits_dir.glob("*.png"):
                ch = path.stem
                if len(ch) != 1 or ch not in "0123456789":
                    continue
                tpl = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if tpl is None:
                    continue
                self._digit_templates[ch] = tpl

            if self._digit_templates:
                self._digit_advance = self._digit_templates["0"].shape[1]

            # Validate: every known skill name must be in the cache
            missing = set(self._skill_names) - set(self._skill_templates.keys())
            if missing:
                log.info("Template cache outdated — missing %d skills: %s",
                         len(missing), ", ".join(sorted(missing)[:5]))
                return False

            elapsed = time.monotonic() - t0
            log.info("Loaded cached templates in %.2fs: %d skills, %d ranks, %d digits",
                     elapsed, len(self._skill_templates),
                     len(self._rank_templates), len(self._digit_templates))
            return True
        except Exception as e:
            log.warning("Failed to load template cache: %s", e)
            return False

    def _save_rendered_cache(self, cache_dir: Path) -> None:
        """Save current rendered templates to disk cache."""
        try:
            skills_dir = cache_dir / "skills"
            ranks_dir = cache_dir / "ranks"
            digits_dir = cache_dir / "digits"
            skills_dir.mkdir(parents=True, exist_ok=True)
            ranks_dir.mkdir(parents=True, exist_ok=True)
            digits_dir.mkdir(parents=True, exist_ok=True)

            for name, tpl in self._skill_templates.items():
                cv2.imwrite(str(skills_dir / f"{self._safe_filename(name)}.png"), tpl)
            for name, tpl in self._rank_templates.items():
                cv2.imwrite(str(ranks_dir / f"{self._safe_filename(name)}.png"), tpl)
            for ch, tpl in self._digit_templates.items():
                cv2.imwrite(str(digits_dir / f"{ch}.png"), tpl)

            log.info("Saved template cache to %s", cache_dir)
        except Exception as e:
            log.warning("Failed to save template cache: %s", e)


    @staticmethod
    def _image_key(img: np.ndarray) -> bytes:
        """Create a unique key from a binary image for exact-match lookup."""
        h, w = img.shape
        return h.to_bytes(2, "big") + w.to_bytes(2, "big") + img.tobytes()

    def _to_lookup_key(self, cell_gray: np.ndarray) -> Optional[bytes]:
        """Binarize, tight-crop, and hash a cell for exact-match lookup."""
        cell_bin = self._to_binary(cell_gray)
        cropped = self._tight_crop(cell_bin, padding=1)
        if cropped is None:
            return None
        return self._image_key(cropped)

    @staticmethod
    def _safe_filename(name: str) -> str:
        """Convert a display name to a safe filename (without extension)."""
        return name.replace(" ", "_")

    @staticmethod
    def _name_from_filename(stem: str) -> str:
        """Convert a safe filename stem back to the display name."""
        return stem.replace("_", " ")

    @staticmethod
    def _replace_template(name: str, tpl: np.ndarray,
                          templates: dict[str, np.ndarray],
                          width_index: dict[int, list[tuple[str, np.ndarray]]],
                          ) -> None:
        """Replace a template in-place: update the template dict and width index."""
        # Remove old entry from width index
        old = templates.get(name)
        if old is not None:
            old_w = old.shape[1]
            bucket = width_index.get(old_w, [])
            width_index[old_w] = [(n, t) for n, t in bucket if n != name]
            if not width_index[old_w]:
                del width_index[old_w]

        # Insert new entry
        templates[name] = tpl
        new_w = tpl.shape[1]
        width_index.setdefault(new_w, []).append((name, tpl))

    def _load_captured_templates(self) -> None:
        """Load game-captured templates from disk for exact-match lookup.

        Captured templates come from the actual Scaleform renderer.  They are
        used ONLY for exact-match lookup (binary hash → instant name resolution).
        The PIL-rendered 4x templates remain in the width index for fuzzy
        matching — they are rendered natively at MATCH_SCALE by PIL's FreeType
        rasterizer, giving clean high-resolution glyphs without upscaling.
        """
        loaded = {"skills": 0, "ranks": 0}
        self._captured_skill_lookup.clear()
        self._captured_rank_lookup.clear()

        # Skills — register for exact-match lookup only
        skill_dir = CAPTURED_DIR / "skills"
        if skill_dir.exists():
            for path in skill_dir.glob("*.png"):
                name = self._name_from_filename(path.stem)
                if name not in self._skill_templates:
                    continue  # skip unknown names
                tpl = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if tpl is None:
                    continue
                # Register for exact-match lookup: binarize + tight_crop
                # to match what _to_lookup_key produces from a game cell
                tpl_bin = self._to_binary(tpl)
                tpl_key = self._tight_crop(tpl_bin, padding=1)
                if tpl_key is not None:
                    self._captured_skill_lookup[self._image_key(tpl_key)] = name
                loaded["skills"] += 1

        # Ranks — register for exact-match lookup only
        rank_dir = CAPTURED_DIR / "ranks"
        if rank_dir.exists():
            for path in rank_dir.glob("*.png"):
                name = self._name_from_filename(path.stem)
                if name not in self._rank_templates:
                    continue
                tpl = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if tpl is None:
                    continue
                tpl_bin = self._to_binary(tpl)
                tpl_key = self._tight_crop(tpl_bin, padding=1)
                if tpl_key is not None:
                    self._captured_rank_lookup[self._image_key(tpl_key)] = name
                loaded["ranks"] += 1

        total = sum(loaded.values())
        if total > 0:
            log.info("Loaded captured templates: %d skills, %d ranks",
                     loaded["skills"], loaded["ranks"])

    def _clean_capture(self, cell_gray: np.ndarray, padding: int = 1) -> Optional[np.ndarray]:
        """Tight-crop a grayscale cell image, preserving anti-aliasing.

        Uses _find_text_extent (run-based column grouping) to find the
        horizontal text region, preventing scattered noise columns from
        inflating the crop width.  Returns the grayscale region so
        sub-pixel information is retained for template matching.
        """
        detect_bin = ((cell_gray > BINARY_THRESHOLD).astype(
            np.uint8)) * 255

        # Use run-based text extent for horizontal bounds (prevents noise
        # columns at the far edges of the cell from inflating crop width)
        extent = self._find_text_extent(detect_bin)
        if extent is None:
            return None

        cmin, cmax_excl = extent  # end is exclusive

        # Vertical bounds: rows with dense text within the detected text region
        region = detect_bin[:, cmin:cmax_excl]
        row_sums = np.sum(region > 0, axis=1)
        dense_rows = np.where(row_sums >= MIN_COL_DENSITY)[0]

        if len(dense_rows) == 0:
            return None

        rmin, rmax = int(dense_rows[0]), int(dense_rows[-1])

        h, w = cell_gray.shape
        rmin = max(0, rmin - padding)
        rmax = min(h - 1, rmax + padding)
        cmin = max(0, cmin - padding)
        cmax = min(w - 1, cmax_excl - 1 + padding)

        cropped = cell_gray[rmin:rmax + 1, cmin:cmax + 1].copy()
        # Zero out background noise from the semi-transparent game window.
        # Pixels at or below BINARY_THRESHOLD are definitionally noise (not text),
        # while anti-aliased text edges above the threshold are preserved.
        cropped[cropped <= BINARY_THRESHOLD] = 0
        return cropped

    def _validate_capture(self, cropped: np.ndarray,
                          cell_gray: np.ndarray) -> bool:
        """Verify a candidate template matches its source cell well enough.

        Returns True only if the cropped template matches the cell at
        CAPTURE_MIN_SCORE or above.  This prevents saving noisy or
        misaligned templates (e.g. from a moved window).

        Both images are noise-cleaned before matching so that background
        noise (from the semi-transparent game window) doesn't reduce the
        score — the template already has noise zeroed by _clean_capture.
        """
        th, tw = cropped.shape
        ch, cw = cell_gray.shape
        if tw > cw or th > ch:
            return False
        cell_clean = cell_gray.copy()
        cell_clean[cell_clean <= BINARY_THRESHOLD] = 0
        score = self._template_match(cell_clean, cropped)
        if score < CAPTURE_MIN_SCORE:
            log.debug("Capture rejected: score=%.3f < %.2f",
                      score, CAPTURE_MIN_SCORE)
            return False
        return True

    def capture_skill(self, name: str, cell_gray: np.ndarray) -> bool:
        """Capture a game-rendered skill name cell as a grayscale template.

        Tight-crops the grayscale cell (preserving anti-aliasing), validates
        the capture scores CAPTURE_MIN_SCORE against the cell, then saves
        to disk and registers in both the width index and exact-match lookup.

        If a template already exists but doesn't validate against the current
        cell (e.g. captured from a different cell height), it is re-captured.
        """
        cropped = self._clean_capture(cell_gray)
        if cropped is None or cropped.shape[0] < 3 or cropped.shape[1] < 3:
            return False

        skill_dir = CAPTURED_DIR / "skills"
        skill_dir.mkdir(parents=True, exist_ok=True)
        path = skill_dir / f"{self._safe_filename(name)}.png"

        if path.exists():
            # Validate existing template against this cell
            existing = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if existing is not None and self._validate_capture(existing, cell_gray):
                return False  # existing template is fine
            log.debug("Re-capturing stale skill template: %s", name)

        if not self._validate_capture(cropped, cell_gray):
            return False

        cv2.imwrite(str(path), cropped)

        # Register for exact-match lookup (binary hash of the cell).
        # PIL 4x templates stay in the width index for fuzzy matching.
        key = self._to_lookup_key(cell_gray)
        if key is not None:
            self._captured_skill_lookup[key] = name

        log.debug("Captured skill template: %s (%dx%d)",
                  name, cropped.shape[1], cropped.shape[0])
        return True

    def capture_rank(self, name: str, cell_gray: np.ndarray) -> bool:
        """Capture a game-rendered rank name cell as a grayscale template."""
        rank_dir = CAPTURED_DIR / "ranks"
        rank_dir.mkdir(parents=True, exist_ok=True)
        path = rank_dir / f"{self._safe_filename(name)}.png"

        if path.exists():
            return False

        cropped = self._clean_capture(cell_gray)
        if cropped is None or cropped.shape[0] < 3 or cropped.shape[1] < 3:
            return False

        if not self._validate_capture(cropped, cell_gray):
            return False

        cv2.imwrite(str(path), cropped)

        # Register for exact-match lookup only
        key = self._to_lookup_key(cell_gray)
        if key is not None:
            self._captured_rank_lookup[key] = name

        log.debug("Captured rank template: %s (%dx%d)",
                  name, cropped.shape[1], cropped.shape[0])
        return True


    @property
    def captured_skill_count(self) -> int:
        """Number of skill templates captured from the game."""
        skill_dir = CAPTURED_DIR / "skills"
        if not skill_dir.exists():
            return 0
        return len(list(skill_dir.glob("*.png")))

    @property
    def captured_rank_count(self) -> int:
        """Number of rank templates captured from the game."""
        rank_dir = CAPTURED_DIR / "ranks"
        if not rank_dir.exists():
            return 0
        return len(list(rank_dir.glob("*.png")))

    @property
    def captured_digit_count(self) -> int:
        """Number of digit templates captured from the game."""
        digit_dir = CAPTURED_DIR / "digits"
        if not digit_dir.exists():
            return 0
        return len(list(digit_dir.glob("*.png")))

    def has_captured_rank(self, name: str) -> bool:
        """Check if a captured template exists for this rank name."""
        path = CAPTURED_DIR / "ranks" / f"{self._safe_filename(name)}.png"
        return path.exists()

    def _render_template(self, text: str) -> Optional[np.ndarray]:
        """Render a text string as a grayscale template image (white on black).

        Delegates to the current rendering mode (native or tight).
        """
        if not self._font:
            return None

        if len(text) == 1:
            return self._render_single_char(text)

        if self._render_mode == "native":
            return self._render_native(text)
        else:
            return self._render_tight(text)

    def _render_native(self, text: str) -> Optional[np.ndarray]:
        """Render text using PIL's native draw.text() with the font's own
        advance widths and kerning at MATCH_SCALE resolution.

        Uses _font_hires (font_size * MATCH_SCALE) so templates are natively
        high-resolution without any post-render upscaling."""
        if not self._font_hires:
            return None

        bbox = self._font_hires.getbbox(text)
        if not bbox:
            return None

        pad = 4
        canvas_w = (bbox[2] - bbox[0]) + pad * 2
        canvas_h = (bbox[3] - bbox[1]) + pad * 2

        img = Image.new("L", (canvas_w, canvas_h), 0)
        draw = ImageDraw.Draw(img)
        draw.text((pad - bbox[0], pad - bbox[1]), text, fill=255, font=self._font_hires)

        arr = np.array(img)
        return self._tight_crop(arr, padding=1)

    def _render_tight(self, text: str) -> Optional[np.ndarray]:
        """Render text character-by-character with scaled GLYPH_GAP spacing
        at MATCH_SCALE resolution.

        Draws all characters on a single PIL canvas with tight inter-glyph
        spacing to match the game's compact text rendering.  Uses _font_hires
        so templates are natively high-resolution.
        """
        if not self._font_hires:
            return None

        font = self._font_hires
        gap = GLYPH_GAP * MATCH_SCALE
        hires_size = self._font_size * MATCH_SCALE

        # Collect (character, bbox) pairs; None bbox = space
        entries: list[tuple[str, Optional[tuple]]] = []
        for ch in text:
            if ch == ' ':
                entries.append((ch, None))
            else:
                bbox = font.getbbox(ch)
                if bbox:
                    entries.append((ch, bbox))

        non_space = [(ch, b) for ch, b in entries if b is not None]
        if not non_space:
            return None

        # Vertical extent across all characters
        min_top = min(b[1] for _, b in non_space)
        max_bottom = max(b[3] for _, b in non_space)

        # Total width: each glyph's visible width + gaps
        total_w = 0
        for ch, b in entries:
            if b is None:
                total_w += max(2, hires_size // 3)
            else:
                total_w += (b[2] - b[0])
        total_w += gap * max(0, len(entries) - 1)

        pad = 4
        canvas_w = total_w + pad * 2
        canvas_h = (max_bottom - min_top) + pad * 2

        # y_origin: the text origin Y on the canvas.
        # PIL places glyph top at y_origin + bbox[1], so to put the
        # highest glyph (min_top) at y=pad: y_origin = pad - min_top
        y_origin = pad - min_top

        img = Image.new("L", (canvas_w, canvas_h), 0)
        draw = ImageDraw.Draw(img)

        x = pad
        for ch, b in entries:
            if b is None:
                x += max(2, hires_size // 3) + gap
                continue
            left, _top, right, _bottom = b
            # Position so visible left edge lands at x (subtract left bearing)
            draw.text((x - left, y_origin), ch, fill=255, font=font)
            x += (right - left) + gap

        arr = np.array(img)
        return self._tight_crop(arr, padding=1)

    def _render_single_char(self, ch: str) -> Optional[np.ndarray]:
        """Render a single character at MATCH_SCALE resolution and tight-crop it."""
        if not self._font_hires:
            return None

        bbox = self._font_hires.getbbox(ch)
        if not bbox:
            return None

        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        pad = 8
        canvas_w = text_w + pad * 2
        canvas_h = text_h + pad * 2
        img = Image.new("L", (canvas_w, canvas_h), 0)
        draw = ImageDraw.Draw(img)
        draw.text((pad - bbox[0], pad - bbox[1]), ch, fill=255, font=self._font_hires)

        arr = np.array(img)
        return self._tight_crop(arr, padding=0)

    @staticmethod
    def _tight_crop(image: np.ndarray, padding: int = 1) -> Optional[np.ndarray]:
        """Crop an image to its non-background bounding box plus *padding*.

        Works for both grayscale and binary images (uses > 30 threshold
        to detect text pixels including anti-aliased edges).
        """
        rows = np.any(image > 30, axis=1)
        cols = np.any(image > 30, axis=0)
        if not np.any(rows) or not np.any(cols):
            return None

        rmin, rmax = np.where(rows)[0][[0, -1]]
        cmin, cmax = np.where(cols)[0][[0, -1]]

        h, w = image.shape
        rmin = max(0, rmin - padding)
        rmax = min(h - 1, rmax + padding)
        cmin = max(0, cmin - padding)
        cmax = min(w - 1, cmax + padding)

        return image[rmin:rmax + 1, cmin:cmax + 1]

    def match_skill_name(self, cell_gray: np.ndarray) -> Optional[tuple[str, float]]:
        """Match a cell image against skill name templates.

        Tries exact pixel-match against captured game templates first (O(1)
        hash lookup).  Falls back to fuzzy template matching if no exact
        match is found.

        Returns:
            (skill_name, confidence) if matched, else None.
        """
        if not self._calibrated:
            return None

        # Exact match against captured templates
        if self._captured_skill_lookup:
            key = self._to_lookup_key(cell_gray)
            if key is not None:
                name = self._captured_skill_lookup.get(key)
                if name:
                    log.debug("match_skill: exact lookup → '%s'", name)
                    return (name, 1.0)

        # Fall back to fuzzy template matching
        if not self._skill_width_index:
            return None
        result = self._match_against_index(
            cell_gray, self._skill_width_index, SKILL_THRESHOLD)
        if result:
            log.debug("match_skill: fuzzy → '%s' (score=%.3f)", result[0], result[1])
        else:
            log.debug("match_skill: no match")
        return result

    def match_rank(self, cell_gray: np.ndarray) -> Optional[tuple[str, float]]:
        """Match a cell image against rank name templates.

        Tries exact pixel-match against captured game templates first.
        Falls back to fuzzy template matching.

        Returns:
            (rank_name, confidence) if matched, else None.
        """
        if not self._calibrated:
            return None

        # Exact match against captured templates
        if self._captured_rank_lookup:
            key = self._to_lookup_key(cell_gray)
            if key is not None:
                name = self._captured_rank_lookup.get(key)
                if name:
                    log.debug("match_rank: exact lookup → '%s'", name)
                    return (name, 1.0)

        # Fall back to fuzzy template matching
        if not self._rank_width_index:
            return None
        result = self._match_against_index(
            cell_gray, self._rank_width_index, RANK_THRESHOLD)
        if result:
            log.debug("match_rank: fuzzy → '%s' (score=%.3f)", result[0], result[1])
        else:
            log.debug("match_rank: no match")
        return result

    def read_points(self, cell_gray: np.ndarray) -> Optional[str]:
        """Read an integer value from a cell image using digit templates.

        Preprocesses the cell, segments digit blobs via contours, then
        matches each blob against digit templates using TM_CCOEFF_NORMED
        (same approach as skill/rank matching).  Templates are rendered
        natively at MATCH_SCALE by PIL; ROI blobs are upscaled via
        _upscale_roi.

        Returns the number as a string (e.g., "6256"), or None.
        """
        if not self._calibrated or not self._digit_templates:
            return None

        cell_h, cell_w = cell_gray.shape[:2]
        if cell_h < 4 or cell_w < 4:
            return None

        # Adaptive threshold for robust segmentation (finds bounding boxes)
        binary = self._preprocess_cell(cell_gray)
        bboxes = self._segment_digits(binary)
        if not bboxes:
            return None

        # Contrast-normalize and clean — same basis as skill/rank matching
        cell_norm = cv2.normalize(cell_gray, None, 0, 255, cv2.NORM_MINMAX,
                                  dtype=cv2.CV_8U)

        digits: list[str] = []
        for i, (x, y, w, h) in enumerate(bboxes):
            # Pad bounding box before cropping — segmented 1x boxes can be
            # tighter than the 4x templates.  2px at 1x → 8px at 4x.
            pad = 2
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(cell_w, x + w + pad)
            y1 = min(cell_h, y + h + pad)
            roi_gray = cell_norm[y0:y1, x0:x1]
            roi_up = self._to_binary(self._upscale_roi(roi_gray))

            # Score against every digit template via TM_CCOEFF_NORMED.
            # Both ROI and templates are binarized for clean matching.
            scores: dict[str, float] = {}
            best_ch = None
            best_score = DIGIT_THRESHOLD
            for ch, tpl in self._digit_templates.items():
                th, tw = tpl.shape
                rh, rw = roi_up.shape[:2]
                if tw > rw or th > rh:
                    scores[ch] = -1.0
                    continue
                score = self._template_match(roi_up, tpl)
                scores[ch] = score
                if score > best_score:
                    best_score = score
                    best_ch = ch

            # Log all scores for this digit position
            score_str = "  ".join(
                f"{ch}={'*' if ch == best_ch else ''}{scores[ch]:.3f}"
                for ch in sorted(scores))
            log.info("Digit[%d] x=%d w=%d: %s → %s",
                     i, x, w, score_str, best_ch or "?")

            if best_ch is not None:
                digits.append(best_ch)
            else:
                return None  # Unmatched digit → abort

        return "".join(digits) if digits else None

    def save_debug_samples(self, output_dir: str) -> None:
        """Save debug images of all rendered templates for visual inspection."""
        os.makedirs(output_dir, exist_ok=True)

        # Save digit templates as a horizontal strip
        if self._digit_templates:
            digits_sorted = sorted(self._digit_templates.items())
            max_h = max(t.shape[0] for _, t in digits_sorted)
            total_w = sum(t.shape[1] + 4 for _, t in digits_sorted)
            strip = np.zeros((max_h + 16, total_w), dtype=np.uint8)
            x = 0
            for ch, tpl in digits_sorted:
                th, tw = tpl.shape
                strip[:th, x:x + tw] = tpl
                x += tw + 4
            path = os.path.join(output_dir, "font_digits.png")
            cv2.imwrite(path, strip)

        # Save first 10 skill templates for inspection
        for i, (name, tpl) in enumerate(list(self._skill_templates.items())[:10]):
            path = os.path.join(output_dir, f"font_skill_{i:02d}_{name}.png")
            cv2.imwrite(path, tpl)

    def save_overlay_debug(self, label: str, cell: np.ndarray,
                           match_name: Optional[str], match_type: str,
                           output_dir: str) -> None:
        """Save a debug image overlaying the best template on the actual cell.

        Always finds and overlays the best matching template, even when the
        match was below threshold. Creates a color image where:
          - Red channel  = actual cell (game text)
          - Green channel = best template (positioned at best match)
          - Yellow overlap = pixels where both agree (good match)
        Text annotation shows the best match name and score.
        """
        os.makedirs(output_dir, exist_ok=True)

        # Pick the right template pool
        templates = {}
        if match_type == "skill":
            templates = self._skill_templates
        elif match_type == "rank":
            templates = self._rank_templates

        # Upscale cell to MATCH_SCALE and binarize (matches _score_candidates)
        cell_up = self._to_binary(self._upscale_roi(cell))
        up_h, up_w = cell_up.shape[:2]

        # If we have a matched name, use it; otherwise brute-force the best
        tpl = None
        best_name = match_name
        best_score = 0.0

        if match_name and match_name in templates:
            tpl = templates[match_name]
            th, tw = tpl.shape
            if tw <= up_w and th <= up_h:
                best_score = self._template_match(cell_up, tpl)
        else:
            # No match — find the best template for overlay anyway
            for name, t in templates.items():
                th, tw = t.shape
                if tw > up_w or th > up_h:
                    continue
                score = self._template_match(cell_up, t)
                if score > best_score:
                    best_score = score
                    best_name = name
                    tpl = t

        # Build overlay at MATCH_SCALE resolution
        overlay = np.zeros((up_h, up_w, 3), dtype=np.uint8)
        overlay[:, :, 2] = cell_up  # Red = game cell (upscaled grayscale)

        if tpl is not None:
            th, tw = tpl.shape
            if tw <= up_w and th <= up_h:
                result = cv2.matchTemplate(cell_up, tpl, cv2.TM_CCOEFF_NORMED)
                _, _, _, max_loc = cv2.minMaxLoc(result)
                bx, by = max_loc
                overlay[by:by + th, bx:bx + tw, 1] = tpl  # Green = template

        # Scale up for visibility (already at MATCH_SCALE, so less extra needed)
        vis_scale = max(1, 4 // MATCH_SCALE)
        scaled = cv2.resize(overlay, (up_w * vis_scale, up_h * vis_scale),
                            interpolation=cv2.INTER_NEAREST)

        # Add text annotation right-aligned inside the cell
        status = "OK" if match_name else "FAIL"
        text = f"{status}: {best_name} ({best_score:.3f})"
        font_scale = 0.4
        sh, sw = scaled.shape[:2]
        (text_w, _text_h), _ = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        text_x = sw - text_w - 4
        cv2.putText(scaled, text, (text_x, sh - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1)

        path = os.path.join(output_dir, f"overlay_{label}.png")
        cv2.imwrite(path, scaled)

    def save_digit_overlay_debug(self, label: str, cell_gray: np.ndarray,
                                 output_dir: str) -> None:
        """Save a debug overlay for digit matching on a points cell.

        Uses the same pipeline as read_points(): adaptive threshold for
        segmentation, crop from normalized grayscale, upscale via
        _upscale_roi, TM_CCOEFF_NORMED match.  Shows the best-matching
        template per segmented digit with its confidence score.
        """
        os.makedirs(output_dir, exist_ok=True)
        cell_h, cell_w = cell_gray.shape[:2]
        if not self._digit_templates or cell_h < 4 or cell_w < 4:
            return

        # Same pipeline as read_points
        binary = self._preprocess_cell(cell_gray)
        bboxes = self._segment_digits(binary)
        cell_norm = cv2.normalize(cell_gray, None, 0, 255, cv2.NORM_MINMAX,
                                  dtype=cv2.CV_8U)

        # Upscale + binarize full cell (mirrors read_points pipeline)
        cell_up = self._to_binary(self._upscale_roi(cell_norm))
        up_h, up_w = cell_up.shape[:2]

        overlay = np.zeros((up_h, up_w, 3), dtype=np.uint8)
        overlay[:, :, 2] = cell_up  # Red = game cell (binarized)

        s = MATCH_SCALE
        annotations: list[tuple[int, str, float]] = []  # (x_up, char, score)

        # Draw segmentation bounding boxes (cyan = contour bbox, blue = padded crop)
        for x, y, w, h in bboxes:
            cv2.rectangle(overlay, (x * s, y * s),
                          ((x + w) * s, (y + h) * s), (255, 255, 0), 1)
            pad = 2
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(cell_w, x + w + pad)
            y1 = min(cell_h, y + h + pad)
            cv2.rectangle(overlay, (x0 * s, y0 * s),
                          (x1 * s, y1 * s), (255, 100, 0), 1)

        for x, y, w, h in bboxes:
            pad = 2
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(cell_w, x + w + pad)
            y1 = min(cell_h, y + h + pad)
            roi_gray = cell_norm[y0:y1, x0:x1]
            roi_up = self._to_binary(self._upscale_roi(roi_gray))

            best_ch = None
            best_score = -1.0
            for digit_ch, tpl in self._digit_templates.items():
                th, tw = tpl.shape
                rh, rw = roi_up.shape[:2]
                if tw > rw or th > rh:
                    continue
                score = self._template_match(roi_up, tpl)
                if score > best_score:
                    best_score = score
                    best_ch = digit_ch

            if best_ch is not None:
                # Find alignment at MATCH_SCALE for overlay
                tpl = self._digit_templates[best_ch]
                th, tw = tpl.shape
                rh, rw = roi_up.shape[:2]
                if tw <= rw and th <= rh:
                    result = cv2.matchTemplate(
                        roi_up, tpl, cv2.TM_CCOEFF_NORMED)
                    _, _, _, max_loc = cv2.minMaxLoc(result)
                    bx, by_ = max_loc
                    ox, oy = x0 * s + bx, y0 * s + by_
                    overlay[oy:oy + th, ox:ox + tw, 1] = np.maximum(
                        overlay[oy:oy + th, ox:ox + tw, 1], tpl)
                annotations.append((x0 * s, best_ch, best_score))

        # Already at MATCH_SCALE; just scale up slightly for visibility
        vis_scale = max(1, 4 // MATCH_SCALE)
        scaled = cv2.resize(overlay, (up_w * vis_scale, up_h * vis_scale),
                            interpolation=cv2.INTER_NEAREST)

        # Draw confidence labels above each digit
        for ax, ach, ascore in annotations:
            text = f"{ach}:{ascore:.2f}"
            tx = ax * vis_scale
            ty = max(12, 2)  # near top of image
            cv2.putText(scaled, text, (tx, ty),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1,
                        cv2.LINE_AA)

        path = os.path.join(output_dir, f"overlay_digits_{label}.png")
        cv2.imwrite(path, scaled)

    @staticmethod
    def _upscale_roi(img: np.ndarray, scale: int = MATCH_SCALE) -> np.ndarray:
        """Upscale a grayscale ROI for template matching.

        Bicubic resize only.  Callers apply _to_binary() to produce a
        clean binary image that matches the binarized PIL templates.
        """
        h, w = img.shape[:2]
        return cv2.resize(img, (w * scale, h * scale),
                          interpolation=cv2.INTER_CUBIC)

    @staticmethod
    def _to_binary(img: np.ndarray, thresh: int = BINARY_THRESHOLD) -> np.ndarray:
        """Threshold a grayscale image to binary (0 or 255).

        This eliminates anti-aliasing differences between ClearType (game)
        and FreeType (PIL), so matching focuses purely on glyph shape.
        """
        return ((img > thresh).astype(np.uint8)) * 255

    @staticmethod
    def _preprocess_cell(cell_gray: np.ndarray) -> np.ndarray:
        """Preprocessing for digit/text segmentation.

        Global threshold at BINARY_THRESHOLD on raw pixel values.
        Game text (green/white ≈128-160, orange ≈121) is well above
        the threshold; semi-transparent background noise stays below.
        No normalization — avoids amplifying dim noise into the
        threshold range, which caused bridges between adjacent digits.
        """
        return ((cell_gray > BINARY_THRESHOLD).astype(np.uint8)) * 255

    def _segment_digits(self, binary: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Contour-based digit segmentation.

        Finds external contours, filters by expected digit dimensions,
        and sorts left-to-right.  Any bbox wider than a single digit
        is evenly split into the estimated number of digits based on
        the known digit advance width.

        Returns list of (x, y, w, h) bounding boxes, or empty list.
        """
        img_h, img_w = binary.shape[:2]
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Maximum single-digit width at 1x scale (templates are at MATCH_SCALE)
        digit_w_1x = (self._digit_advance // MATCH_SCALE) if self._digit_advance > 0 else 5
        max_digit_w = digit_w_1x + 2

        # Filter contours by expected digit dimensions
        min_h = int(img_h * 0.4)
        max_h = int(img_h * 1.1)
        bboxes: list[tuple[int, int, int, int]] = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if h < min_h or h > max_h:
                continue
            if w < 3:
                continue
            bboxes.append((x, y, w, h))

        if not bboxes:
            return []

        # Sort left-to-right
        bboxes.sort(key=lambda b: b[0])

        # Split any bbox wider than a single digit evenly
        split: list[tuple[int, int, int, int]] = []
        for x, y, w, h in bboxes:
            if w <= max_digit_w:
                split.append((x, y, w, h))
                continue
            # Estimate how many digits are merged in this bbox
            n = max(2, round(w / digit_w_1x)) if digit_w_1x > 0 else 2
            part_w = w / n
            for i in range(n):
                px = x + int(i * part_w)
                pw = int((i + 1) * part_w) - int(i * part_w)
                split.append((px, y, pw, h))

        # Reject if too many digits (noise)
        if len(split) > MAX_DIGITS:
            return []

        return split

    def _template_match(self, cell_bin: np.ndarray,
                        tpl_bin: np.ndarray) -> float:
        """Match using TM_CCOEFF_NORMED — penalizes both extra and missing pixels."""
        result = cv2.matchTemplate(cell_bin, tpl_bin, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val

    def _score_candidates(self, cell_crop: np.ndarray,
                           candidates: list[tuple[str, np.ndarray]],
                           threshold: float,
                           text_extent_w: int = 0,
                           ) -> Optional[tuple[str, float]]:
        """Score candidate templates against a cell image.

        Upscales the cell using bicubic + binarize.  Templates
        are already at MATCH_SCALE resolution (rendered natively by PIL at
        4x font size and binarized), so no template upscaling is needed.

        Applies a coverage penalty: templates narrower than the detected
        text content are penalized proportionally to the uncovered width.
        This prevents short substrings (e.g. "Great") from beating the
        full text (e.g. "Great Master") when both achieve high raw scores.

        Args:
            text_extent_w: Detected text width at 1x (from _find_text_extent).
                Used for coverage penalty.  Falls back to cell width if 0.

        Returns the raw (penalized) score as the confidence value.
        """
        cell_h, cell_w = cell_crop.shape[:2]

        # Upscale cell and binarize — removes background noise and matches
        # the binary templates rendered by PIL at MATCH_SCALE.
        cell_up = self._to_binary(self._upscale_roi(cell_crop))
        cell_up_h, cell_up_w = cell_up.shape[:2]

        # Reference width for coverage: detected text extent scaled to
        # MATCH_SCALE, or fall back to upscaled cell width.
        ref_w = (text_extent_w * MATCH_SCALE) if text_extent_w > 0 else cell_up_w

        best: Optional[tuple[str, float]] = None
        best_adjusted = 0.0
        best_raw = 0.0

        for name, tpl in candidates:
            th, tw = tpl.shape
            if tw > cell_up_w or th > cell_up_h:
                continue

            raw = self._template_match(cell_up, tpl)

            # Coverage penalty: how much of the detected text does the
            # template explain?  Uses text_extent_w (not cell width) so
            # cell padding doesn't inflate the denominator.
            coverage = min(1.0, tw / ref_w) if ref_w > 0 else 1.0
            score = raw * coverage

            if raw > best_raw:
                best_raw = raw

            if score >= threshold:
                if best is None or score > best_adjusted:
                    best = (name, score)
                    best_adjusted = score

        if best is None and best_raw > 0:
            log.debug("Below threshold: best raw=%.3f (need %.2f), "
                      "cell %dx%d",
                      best_raw, threshold, cell_h, cell_w)

        return best

    @staticmethod
    def _find_text_extent(detect_bin: np.ndarray,
                          min_density: int = MIN_COL_DENSITY,
                          ) -> Optional[tuple[int, int]]:
        """Find the horizontal extent of actual text in a binary cell image.

        Uses column density to distinguish real text columns (multiple bright
        pixels stacked vertically) from noise (isolated pixels from the
        semi-transparent window background).

        Groups dense columns into contiguous runs (bridging inter-char gaps)
        and returns the run with the highest total pixel density as
        (start_col, end_col).  This ensures text (high density per column)
        beats noise clusters (low density per column) even when the noise
        cluster happens to be wider.
        """
        col_sums = np.sum(detect_bin > 0, axis=0)
        dense_indices = np.where(col_sums >= min_density)[0]

        if len(dense_indices) == 0:
            return None

        # Group consecutive dense columns, bridging gaps ≤ MAX_TEXT_GAP
        runs: list[tuple[int, int]] = []
        run_start = int(dense_indices[0])
        run_end = run_start

        for idx in dense_indices[1:]:
            if idx - run_end <= MAX_TEXT_GAP:
                run_end = int(idx)
            else:
                runs.append((run_start, run_end + 1))
                run_start = int(idx)
                run_end = run_start
        runs.append((run_start, run_end + 1))

        # Pick the run with the highest total pixel density.
        # Text columns have 6–12 bright pixels each vs 2–3 for noise,
        # so total density reliably distinguishes text from noise clusters.
        return max(runs, key=lambda r: int(np.sum(col_sums[r[0]:r[1]])))

    def _match_against_index(self, cell_gray: np.ndarray,
                             width_index: dict[int, list[tuple[str, np.ndarray]]],
                             threshold: float) -> Optional[tuple[str, float]]:
        """Match a cell image against all templates in the index.

        Cleans background noise from the cell, crops to the horizontal
        text ROI, then scores every template using upscaled TM_CCOEFF_NORMED
        with coverage penalty.
        """
        cell_h, cell_w = cell_gray.shape[:2]
        if cell_h < 4 or cell_w < 4:
            return None

        # Quick check for any content (use binary threshold)
        cell_bin = self._to_binary(cell_gray)
        if not np.any(cell_bin > 0):
            log.debug("match_against_index: no content above threshold "
                      "in cell %dx%d", cell_h, cell_w)
            return None

        # Contrast normalization — stretches to full 0-255 range so
        # semi-transparent backgrounds with varying brightness don't
        # produce weak text that falls below the fixed threshold.
        cell_norm = cv2.normalize(cell_gray, None, 0, 255,
                                  cv2.NORM_MINMAX, dtype=cv2.CV_8U)

        # Suppress background noise before matching
        cell_clean = cell_norm.copy()
        cell_clean[cell_clean <= BINARY_THRESHOLD] = 0

        # Crop to horizontal text ROI — avoids upscaling empty margins.
        # Only crop when cell is significantly wider than the text
        # (e.g. skill name column with wide empty right margin).
        detect_bin = self._preprocess_cell(cell_gray)
        extent = self._find_text_extent(detect_bin)
        text_extent_w = cell_w  # fallback: full cell width
        if extent is not None:
            x_start, x_end = extent
            text_extent_w = x_end - x_start
            if cell_w > text_extent_w * 1.5:
                pad = max(6, text_extent_w // 4)
                x_start = max(0, x_start - pad)
                x_end = min(cell_w, x_end + pad)
                cell_clean = cell_clean[:, x_start:x_end]

        # Gather all candidates and score against the cropped cell
        all_candidates: list[tuple[str, np.ndarray]] = []
        for entries in width_index.values():
            all_candidates.extend(entries)

        result = self._score_candidates(
            cell_clean, all_candidates, threshold,
            text_extent_w=text_extent_w)
        if result is None:
            log.debug("match_against_index: no match in %d candidates, "
                      "cell %dx%d, threshold=%.2f",
                      len(all_candidates), cell_h, cell_w, threshold)
        return result
