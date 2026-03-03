import threading
import time
import numpy as np
from pathlib import Path
from typing import Optional

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.logger import get_logger

log = get_logger("FontMatcher")

ASSETS_DIR = Path(__file__).parent.parent / "assets"
STPK_DIR = ASSETS_DIR / "stpk"
CAPTURED_DIR = Path("./data/captured_templates")

# Match thresholds for TM_CCOEFF_NORMED (penalizes both extra and missing).
# STPK templates are matched at native 1x resolution against noise-cleaned
# grayscale cells; 0.65 accommodates slight rendering differences.
SKILL_THRESHOLD = 0.65
RANK_THRESHOLD = 0.65

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


# --- 4-bit STPK digit matching constants ---

# Pixel-classification thresholds for orange/white text (RGB, matching C++)
WHITE_TEXT_MAX_SATURATION = 60
ORANGE_MIN_R = 120
ORANGE_MIN_DIFF = 40   # r - b threshold
WHITE_MIN_BRIGHTNESS = 100

# Blob segmentation & splitting
MAX_BLOB_WIDTH = 8       # blobs wider than this get split
MAX_SPLIT_DEPTH = 3
MIN_SPLIT_MARGIN = 3     # minimum pixels on left side of split

# 0-vs-9 tiebreaker: max score margin to apply bridge-row heuristic
ZERO_NINE_MAX_MARGIN = 30
# 5-vs-6 tiebreaker: max score margin to apply top-bar heuristic
FIVE_SIX_MAX_MARGIN = 30


class DigitMatcher:
    """Vectorized 4-bit digit template matcher.

    Stacks all template variants into a single (N, H*W) int16 array so that
    scoring an observed grid against every variant is one numpy operation.

    Scoring formula:  6*sum(min(obs, tmpl)) - 2*sum(tmpl) - sum(obs)
    Rewards overlap, penalizes extra and missing pixels using soft (4-bit)
    values rather than binary matching.
    """

    def __init__(self, digit_templates: list[list[np.ndarray]]):
        """digit_templates[d] = list of variant grids for digit d (0-9)."""
        all_tmpls = []
        self._digit_of: list[int] = []
        self._digit_starts: list[int] = []
        self._digit_counts: list[int] = []

        for d in range(10):
            self._digit_starts.append(len(all_tmpls))
            variants = digit_templates[d] if d < len(digit_templates) else []
            self._digit_counts.append(len(variants))
            for t in variants:
                all_tmpls.append(t.ravel().astype(np.int16))
                self._digit_of.append(d)

        self._tmpls = np.array(all_tmpls, dtype=np.int16)        # (N, H*W)
        self._n = self._tmpls.shape[0]
        self._tmpl_sums_x2 = np.sum(self._tmpls, axis=1).astype(np.int32) * 2
        self._reduce_idx = np.array(self._digit_starts, dtype=np.intp)
        self._scratch = np.empty_like(self._tmpls)

    def _score_all(self, obs_flat: np.ndarray) -> np.ndarray:
        """Score a flat observation against all templates. Returns (N,) int32."""
        obs_sum = int(np.sum(obs_flat))
        np.minimum(obs_flat, self._tmpls, out=self._scratch)
        overlap_sums = np.sum(self._scratch, axis=1)
        return (overlap_sums * 6 - self._tmpl_sums_x2 - obs_sum).astype(np.int32)

    def best_digit(
        self, observed: np.ndarray,
    ) -> tuple[int, float, list[float]]:
        """Score observed grid against all variants, return best digit.

        Returns (digit, best_score, per_digit_max_scores).
        """
        flat_scores = self._score_all(observed.ravel().astype(np.int16))
        per_digit = np.maximum.reduceat(flat_scores, self._reduce_idx)
        best_idx = int(np.argmax(per_digit))
        return best_idx, float(per_digit[best_idx]), per_digit.astype(np.float64).tolist()

    def best_score(self, observed: np.ndarray) -> float:
        """Score observed grid, return only the best score (for splitting)."""
        return float(np.max(self._score_all(observed.ravel().astype(np.int16))))


# --- 4-bit helper functions ---

def _extract_text_intensity(
    cell_rgb: np.ndarray,
) -> tuple[np.ndarray, bool]:
    """Extract text intensity from an RGB cell, detecting orange vs white text.

    Returns (intensity, is_orange) where intensity is (H, W) uint8 with text
    pixels mapped to their brightness and non-text pixels set to 0.
    """
    r = cell_rgb[:, :, 2].astype(np.int16)  # BGR → R
    g = cell_rgb[:, :, 1].astype(np.int16)
    b = cell_rgb[:, :, 0].astype(np.int16)
    br = np.maximum(np.maximum(r, g), b)

    h, w = r.shape
    intensity = np.zeros((h, w), dtype=np.uint8)

    # Orange text
    orange_mask = (
        (r > ORANGE_MIN_R) & (r > g) & (g > b)
        & ((r - b) > ORANGE_MIN_DIFF) & (br > 60)
    )
    intensity[orange_mask] = r[orange_mask].clip(0, 255).astype(np.uint8)

    # White text (where not already orange)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    white_mask = (
        ~orange_mask
        & (br > WHITE_MIN_BRIGHTNESS)
        & ((mx - mn) < WHITE_TEXT_MAX_SATURATION)
    )
    intensity[white_mask] = mx[white_mask].clip(0, 255).astype(np.uint8)

    return intensity, int(np.sum(orange_mask)) > int(np.sum(white_mask))


def _extract_text_intensity_gray(cell_gray: np.ndarray) -> np.ndarray:
    """Fallback: extract text intensity from grayscale only (no color info)."""
    out = cell_gray.copy()
    out[out <= BINARY_THRESHOLD] = 0
    return out


def _find_blobs_4bit(
    intensity_4bit: np.ndarray, text_top: int, text_bot: int,
) -> list[tuple[int, int]]:
    """Find blobs (contiguous column ranges with content) in the 4-bit grid."""
    col_has = np.any(intensity_4bit[text_top:text_bot + 1, :] > 0, axis=0)

    blobs: list[tuple[int, int]] = []
    start = -1
    for col in range(len(col_has) + 1):
        has = col < len(col_has) and col_has[col]
        if has and start < 0:
            start = col
        elif not has and start >= 0:
            blobs.append((start, col - 1))
            start = -1
    return blobs


def _normalize_blob(
    intensity_4bit: np.ndarray,
    x0: int, x1: int,
    text_top: int, text_h: int,
    grid_w: int, grid_h: int,
) -> np.ndarray:
    """Right-align and bottom-align a blob into a grid_w x grid_h 4-bit grid."""
    rows = min(text_h, grid_h)
    y_end = min(text_top + rows, intensity_4bit.shape[0])
    x_end = min(x1 + 1, intensity_4bit.shape[1])

    region = intensity_4bit[text_top:y_end, x0:x_end]
    content_mask = region > 0
    if not content_mask.any():
        return np.zeros((grid_h, grid_w), dtype=np.uint8)

    row_has = np.any(content_mask, axis=1)
    col_has = np.any(content_mask, axis=0)
    ct = int(np.argmax(row_has))
    cb = int(len(row_has) - 1 - np.argmax(row_has[::-1]))
    cl = int(np.argmax(col_has))
    cr = int(len(col_has) - 1 - np.argmax(col_has[::-1]))

    content = region[ct:cb + 1, cl:cr + 1]
    ch, cw = content.shape

    # Right-align, bottom-align
    gx = max(grid_w - cw, 0)
    gy = max(grid_h - ch, 0)
    ph = min(ch, grid_h - gy)
    pw = min(cw, grid_w - gx)

    grid = np.zeros((grid_h, grid_w), dtype=np.uint8)
    grid[gy:gy + ph, gx:gx + pw] = content[:ph, :pw]
    return grid


def _find_first_content(
    intensity_4bit: np.ndarray, from_col: int, to_col: int,
    text_top: int, text_bot: int,
) -> int:
    """Find first column with content starting from from_col."""
    end_col = min(to_col + 1, intensity_4bit.shape[1])
    if from_col >= end_col:
        return to_col + 1
    region = intensity_4bit[text_top:text_bot + 1, from_col:end_col]
    col_has = np.any(region > 0, axis=0)
    if not col_has.any():
        return to_col + 1
    return from_col + int(np.argmax(col_has))


def _best_norm_score(
    intensity_4bit: np.ndarray,
    x0: int, x1: int,
    text_top: int, text_h: int,
    matcher: DigitMatcher,
    grid_w: int, grid_h: int,
) -> float:
    """Score a blob region against all templates, return best score."""
    grid = _normalize_blob(intensity_4bit, x0, x1, text_top, text_h, grid_w, grid_h)
    return matcher.best_score(grid)


def _split_blobs(
    intensity_4bit: np.ndarray,
    blobs: list[tuple[int, int]],
    text_top: int, text_h: int,
    matcher: DigitMatcher,
    grid_w: int, grid_h: int,
    min_score: float = 65.0,
) -> list[tuple[int, int]]:
    """Split wide blobs that likely contain merged digits using score guidance."""
    text_bot = text_top + text_h - 1

    def _split(x0: int, x1: int, out: list, depth: int):
        bw = x1 - x0 + 1
        if bw <= MAX_BLOB_WIDTH or depth >= MAX_SPLIT_DEPTH:
            out.append((x0, x1))
            return

        best_score = 0.0
        best_col = -1

        for sc in range(x0 + MIN_SPLIT_MARGIN, x1 - 1):
            rs = _find_first_content(intensity_4bit, sc, x1, text_top, text_bot)
            if rs > x1:
                continue
            ls = _best_norm_score(
                intensity_4bit, x0, sc - 1, text_top, text_h,
                matcher, grid_w, grid_h)
            rrs = _best_norm_score(
                intensity_4bit, rs, x1, text_top, text_h,
                matcher, grid_w, grid_h)
            combined = min(ls, rrs)
            if combined > best_score:
                best_score = combined
                best_col = sc

        if best_col >= 0 and best_score >= min_score:
            _split(x0, best_col - 1, out, depth + 1)
            rs = _find_first_content(intensity_4bit, best_col, x1, text_top, text_bot)
            if rs <= x1:
                _split(rs, x1, out, depth + 1)
        else:
            out.append((x0, x1))

    result: list[tuple[int, int]] = []
    for x0, x1 in blobs:
        _split(x0, x1, result, 0)
    return result


class FontMatcher:
    """Recognizes game text via template matching using STPK font templates.

    Loads pre-rendered Scaleform font templates from STPK pack files and
    matches them against game screenshots using cv2.matchTemplate().
    Digit recognition uses vectorized 4-bit grid scoring via DigitMatcher.
    """

    def __init__(self, skill_names: list[str], rank_names: list[str]):
        if cv2 is None:
            raise ImportError("opencv-python is required")

        self._skill_names = skill_names
        self._rank_names = rank_names

        self._font_size: int = 0
        self._text_zone_height: int = 0
        self._calibrated = False

        # STPK templates: {name: grayscale_image}
        self._skill_templates: dict[str, np.ndarray] = {}
        self._rank_templates: dict[str, np.ndarray] = {}

        # Width index for fast candidate filtering: {width: [(name, template), ...]}
        self._skill_width_index: dict[int, list[tuple[str, np.ndarray]]] = {}
        self._rank_width_index: dict[int, list[tuple[str, np.ndarray]]] = {}

        # 4-bit STPK digit matcher (vectorized scoring)
        self._digit_matcher: DigitMatcher | None = None
        self._digit_grid_w: int = 0
        self._digit_grid_h: int = 0

        # Exact-match lookup: image_key → name (for game-captured templates)
        self._captured_skill_lookup: dict[bytes, str] = {}
        self._captured_rank_lookup: dict[bytes, str] = {}

        # STPK state
        self._stpk_loaded: bool = False
        self._stpk_font_size: int = 0

        # Background pre-initialization: signals when templates are loaded
        self._ready = threading.Event()

    def pre_initialize(self) -> None:
        """Load STPK templates in a background thread at startup.

        Templates are ready before the first scan so `calibrate()` can
        skip the load step.
        """
        t0 = time.monotonic()
        try:
            if not self._load_stpk_templates():
                log.error("STPK templates not found — OCR will not work")
                return
            self._font_size = self._stpk_font_size
            self._load_captured_templates()
            log.info("Pre-initialized STPK templates in %.1fs (font_size=%d)",
                     time.monotonic() - t0, self._stpk_font_size)
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

    def get_skill_template(self, name: str) -> Optional[np.ndarray]:
        """Return the pre-rendered template image for a skill name."""
        return self._skill_templates.get(name)

    def best_skill_match(self, cell: np.ndarray) -> Optional[tuple[str, float]]:
        """Return the best skill name match regardless of confidence threshold."""
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
        """Set calibrated flag and compute text zone height.

        Waits for pre_initialize() if it's still running.
        """
        self._ready.wait()

        row_height = max(20, round(panel_height * 0.045))
        self._text_zone_height = int(row_height * 0.70)

        if self._stpk_loaded:
            self._font_size = self._stpk_font_size
            self._calibrated = True
            log.info("Calibrated with STPK templates (font_size=%d)",
                     self._stpk_font_size)
        else:
            log.error("STPK templates not loaded — cannot calibrate")

    def _load_stpk_templates(self) -> bool:
        """Load templates from STPK pack files (Scaleform-rendered, 1x).

        STPK templates are 8-bit anti-aliased grayscale bitmaps that faithfully
        reproduce the game's Scaleform text rendering. They replace PIL-rendered
        templates as the primary fuzzy matching source.

        Returns True if STPK files were loaded successfully.
        """
        from .stpk import read_stpk

        skills_path = STPK_DIR / "skill_names.stpk"
        ranks_path = STPK_DIR / "skill_ranks.stpk"
        digits_path = STPK_DIR / "digits.stpk"

        if not skills_path.exists():
            return False

        t0 = time.monotonic()

        try:
            # Skills
            self._skill_templates.clear()
            self._skill_width_index.clear()
            header, entries = read_stpk(skills_path)
            self._stpk_font_size = header["font_size"]

            for entry in entries:
                name = entry["text"]
                if name not in self._skill_names:
                    continue
                bitmap = entry["bitmap"]
                if bitmap is None:
                    continue
                cropped = self._tight_crop(bitmap, padding=0)
                if cropped is None:
                    continue
                self._skill_templates[name] = cropped
                w = cropped.shape[1]
                self._skill_width_index.setdefault(w, []).append((name, cropped))

            # Ranks
            self._rank_templates.clear()
            self._rank_width_index.clear()
            if ranks_path.exists():
                _, entries = read_stpk(ranks_path)
                for entry in entries:
                    name = entry["text"]
                    if name not in self._rank_names:
                        continue
                    bitmap = entry["bitmap"]
                    if bitmap is None:
                        continue
                    cropped = self._tight_crop(bitmap, padding=0)
                    if cropped is None:
                        continue
                    self._rank_templates[name] = cropped
                    w = cropped.shape[1]
                    self._rank_width_index.setdefault(w, []).append((name, cropped))

            # Digits — load 4-bit grids for vectorized matching
            self._digit_matcher: DigitMatcher | None = None
            self._digit_grid_w = 0
            self._digit_grid_h = 0
            if digits_path.exists():
                d_header, entries = read_stpk(digits_path)
                digit_grids: dict[str, list[np.ndarray]] = {}
                digit_count = 0
                for entry in entries:
                    text = entry["text"]
                    if len(text) != 1 or text not in "0123456789":
                        continue
                    digit_grids.setdefault(text, []).append(entry["grid"])
                    digit_count += 1

                if digit_grids:
                    ordered = [digit_grids.get(str(d), []) for d in range(10)]
                    self._digit_matcher = DigitMatcher(ordered)
                    self._digit_grid_w = d_header["grid_w"]
                    self._digit_grid_h = d_header["grid_h"]
                    total_v = sum(len(v) for v in ordered)
                    log.info("DigitMatcher: %d variants across 10 digits, "
                             "grid %dx%d", total_v,
                             self._digit_grid_w, self._digit_grid_h)

            # Validate: every known skill name should be in the pack
            missing = set(self._skill_names) - set(self._skill_templates.keys())
            if missing:
                log.warning("STPK missing %d skills: %s",
                            len(missing), ", ".join(sorted(missing)[:5]))

            self._stpk_loaded = True
            elapsed = time.monotonic() - t0
            log.info("Loaded STPK templates in %.2fs: %d skills, %d ranks "
                     "(font_size=%d)",
                     elapsed, len(self._skill_templates),
                     len(self._rank_templates),
                     self._stpk_font_size)
            return True

        except Exception as e:
            log.error("Failed to load STPK templates: %s", e)
            self._stpk_loaded = False
            return False

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
        used for exact-match lookup (binary hash → instant name resolution)
        and also added to the width index for fuzzy matching.
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

    def read_points(self, cell_gray: np.ndarray,
                    cell_rgb: np.ndarray | None = None) -> Optional[str]:
        """Read an integer value from a cell image using 4-bit STPK digit templates.

        Uses vectorized scoring against 4-bit lightness grids (preserves
        anti-aliasing info, robust to semi-transparent backgrounds).

        Args:
            cell_gray: (H, W) uint8 grayscale cell image
            cell_rgb: (H, W, 3) uint8 BGR cell image (optional, for
                orange/white text detection)

        Returns the number as a string (e.g., "6256"), or None.
        """
        if not self._calibrated or not self._digit_matcher:
            return None
        cell_h, cell_w = cell_gray.shape[:2]
        if cell_h < 4 or cell_w < 4:
            return None

        matcher = self._digit_matcher
        grid_w = self._digit_grid_w
        grid_h = self._digit_grid_h

        # Extract text intensity — orange/white aware if RGB available
        if cell_rgb is not None and len(cell_rgb.shape) == 3:
            intensity, is_orange = _extract_text_intensity(cell_rgb)
        else:
            intensity = _extract_text_intensity_gray(cell_gray)
            is_orange = False

        # Quantize to 4-bit
        intensity_4bit = np.minimum(intensity >> 4, 15).astype(np.uint8)

        # Find text vertical bounds
        rows_with_content = np.any(intensity_4bit > 0, axis=1)
        if not rows_with_content.any():
            log.debug("read_points_4bit: no content in %dx%d cell", cell_h, cell_w)
            return None

        text_top = int(np.argmax(rows_with_content))
        text_bot = int(len(rows_with_content) - 1 - np.argmax(rows_with_content[::-1]))
        text_h = text_bot - text_top + 1

        # Segment into blobs
        blobs = _find_blobs_4bit(intensity_4bit, text_top, text_bot)
        if not blobs:
            log.debug("read_points_4bit: no blobs in %dx%d cell", cell_h, cell_w)
            return None

        color_str = "ORANGE" if is_orange else "WHITE"
        init_diag = (
            f"initBlobs={len(blobs)} "
            f"[{' '.join(f'x{x0}-{x1}w{x1 - x0 + 1}' for x0, x1 in blobs)}] "
            f"textH={text_h} top={text_top} {color_str}"
        )

        # Split wide blobs using score-guided splitting
        final_blobs = _split_blobs(
            intensity_4bit, blobs, text_top, text_h,
            matcher, grid_w, grid_h,
        )

        if len(final_blobs) > MAX_DIGITS:
            log.debug("read_points_4bit: too many blobs (%d), rejecting",
                       len(final_blobs))
            return None

        # Classify each blob
        classified: list[dict] = []
        for x0, x1 in final_blobs:
            grid = _normalize_blob(
                intensity_4bit, x0, x1, text_top, text_h, grid_w, grid_h)
            digit, score, scores = matcher.best_digit(grid)
            classified.append({
                "x0": x0, "x1": x1, "digit": digit,
                "score": score, "scores": scores,
            })

        # 0-vs-9 tiebreaker: '9' has a solid bridge row in its middle
        # (where the loop closes into the tail) while '0' has a hollow center.
        for c in classified:
            if c["digit"] != 0:
                continue
            margin = c["scores"][0] - c["scores"][9]
            if margin > ZERO_NINE_MAX_MARGIN:
                continue

            grid = _normalize_blob(
                intensity_4bit, c["x0"], c["x1"],
                text_top, text_h, grid_w, grid_h)

            content_cols = np.any(grid > 0, axis=0)
            if not content_cols.any():
                continue
            col_l = int(np.argmax(content_cols))
            col_r = int(len(content_cols) - 1 - np.argmax(content_cols[::-1]))
            cw = col_r - col_l + 1
            if cw < 3:
                continue

            content_rows = np.any(grid > 0, axis=1)
            row_t = int(np.argmax(content_rows))
            row_b = int(len(content_rows) - 1 - np.argmax(content_rows[::-1]))
            ch = row_b - row_t + 1
            if ch < 5:
                continue

            mid_start = row_t + ch // 3
            mid_end = row_t + 2 * ch // 3
            has_bridge = False
            for r in range(mid_start, mid_end + 1):
                if np.all(grid[r, col_l:col_r + 1] > 0):
                    has_bridge = True
                    break

            if has_bridge:
                log.debug("0→9 override: x%d-%d margin=%.1f bridge at row %d",
                          c["x0"], c["x1"], margin, r)
                c["digit"] = 9
                c["score"] = c["scores"][9]

        # 5-vs-6 tiebreaker: '5' has a flat top bar filling the top row(s)
        # of the grid, while '6' has a curved top leaving the top row empty
        # (content_h=9 vs 10, bottom-aligned → empty first row for 6).
        for c in classified:
            if c["digit"] != 5:
                continue
            margin = c["scores"][5] - c["scores"][6]
            if margin > FIVE_SIX_MAX_MARGIN:
                continue

            grid = _normalize_blob(
                intensity_4bit, c["x0"], c["x1"],
                text_top, text_h, grid_w, grid_h)

            top_sum = int(np.sum(grid[0, :]))
            if top_sum == 0:
                log.debug("5→6 override: x%d-%d margin=%.1f top_sum=%d",
                          c["x0"], c["x1"], margin, top_sum)
                c["digit"] = 6
                c["score"] = c["scores"][6]

        # Build output and log diagnostics
        num_str = ""
        blob_diags = []
        for c in classified:
            bw = c["x1"] - c["x0"] + 1
            score_strs = ",".join(f"{s:.0f}" for s in c["scores"])
            blob_diags.append(
                f"x{c['x0']}-{c['x1']}w{bw}->{c['digit']}@{c['score']:.0f}"
                f"[{score_strs}]"
            )
            num_str += str(c["digit"])

        log.info("read_points_4bit: %s | blobs=%d %s → %s",
                 init_diag, len(classified), " ".join(blob_diags),
                 num_str or "?")

        return num_str if num_str else None


    @staticmethod
    def _to_binary(img: np.ndarray, thresh: int = BINARY_THRESHOLD) -> np.ndarray:
        """Threshold a grayscale image to binary (0 or 255).

        This eliminates anti-aliasing differences between ClearType (game)
        and FreeType (PIL), so matching focuses purely on glyph shape.
        """
        return ((img > thresh).astype(np.uint8)) * 255

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

        Matches noise-cleaned grayscale cell directly against STPK
        8-bit AA templates at native 1x resolution.

        Applies a coverage penalty: templates narrower than the detected
        text content are penalized proportionally to the uncovered width.
        """
        cell_h, cell_w = cell_crop.shape[:2]

        cell_match = cell_crop.copy()
        cell_match[cell_match <= BINARY_THRESHOLD] = 0
        cell_match_h, cell_match_w = cell_match.shape[:2]
        ref_w = text_extent_w if text_extent_w > 0 else cell_match_w

        best: Optional[tuple[str, float]] = None
        best_adjusted = 0.0
        best_raw = 0.0

        for name, tpl in candidates:
            th, tw = tpl.shape
            if tw > cell_match_w or th > cell_match_h:
                continue

            raw = self._template_match(cell_match, tpl)

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
        detect_bin = self._to_binary(cell_gray)
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
