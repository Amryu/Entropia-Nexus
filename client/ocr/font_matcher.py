import json
import os
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
CALIBRATION_FILE = Path("./data/font_calibration.json")
CAPTURED_DIR = Path("./data/captured_templates")

# Match thresholds for TM_CCOEFF_NORMED (penalizes both extra and missing)
SKILL_THRESHOLD = 0.60
RANK_THRESHOLD = 0.60
DIGIT_THRESHOLD = 0.75

# Width tolerance for candidate filtering (pixels)
WIDTH_TOLERANCE = 6

# Inter-glyph spacing in rendered templates (pixels between glyph bounding boxes)
# Game renders text very tightly (~1px between glyphs)
GLYPH_GAP = 1

# Binary threshold (must match preprocessor)
BINARY_THRESHOLD = 100



class FontMatcher:
    """Recognizes game text via template matching using the known game font.

    Pre-renders all known skill names, rank names, and digit characters as
    binary template images, then matches them against preprocessed game
    screenshots using cv2.matchTemplate(). This is 100-300x faster than
    Tesseract because it uses in-process OpenCV calls instead of spawning
    external processes.
    """

    def __init__(self, skill_names: list[str], rank_names: list[str],
                 font_path: str = None):
        if cv2 is None:
            raise ImportError("opencv-python is required")
        if ImageFont is None:
            raise ImportError("Pillow is required. Install with: pip install Pillow")

        self._font_path = font_path or str(FONT_PATH)
        self._skill_names = skill_names
        self._rank_names = rank_names

        self._font: Optional[ImageFont.FreeTypeFont] = None
        self._font_size: int = 0
        self._text_zone_height: int = 0
        self._calibrated = False
        self._render_mode: str = "native"  # "native" or "tight"

        # Pre-rendered templates: {name: binary_image}
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
        """Return the best skill name match regardless of confidence threshold."""
        if not self._calibrated or not self._skill_width_index:
            return None
        return self._match_against_index(
            cell, self._skill_width_index, threshold=0.0)

    def calibrate(self, panel_height: int) -> None:
        """Calibrate font size for the detected panel dimensions and render all templates.

        If a saved calibration exists for this panel height, loads it.
        Otherwise uses defaults (size 13, native mode).

        Args:
            panel_height: Height of the skills window panel in pixels.
        """
        # Must exactly mirror the cell height calculation in orchestrator:
        #   row_height = max(20, round(wh * 0.045))
        #   text_h = int(row_height * 0.70)
        row_height = max(20, round(panel_height * 0.045))
        self._text_zone_height = int(row_height * 0.70)
        self._panel_height = panel_height

        # Try to load saved calibration for this panel height
        saved = self._load_calibration(panel_height)
        if saved:
            self._font_size = saved["font_size"]
            self._render_mode = saved["render_mode"]
            self._font = ImageFont.truetype(self._font_path, self._font_size)
            log.info("Font: size=%d mode=%s (saved, score=%.3f)",
                     self._font_size, self._render_mode,
                     saved.get("avg_score", 0))
        else:
            self._font_size = 13
            self._render_mode = "native"
            self._font = ImageFont.truetype(self._font_path, 13)
            log.info("Font: size=%d mode=%s (default)", self._font_size, self._render_mode)

        self._render_all_templates()
        self._load_captured_templates()
        self._calibrated = True

    def auto_calibrate(self, sample_cells: list[np.ndarray]) -> None:
        """Refine rendering mode and font size by testing against actual game cells.

        Tries both rendering modes ("native" and "tight") and font sizes 11-15,
        picking the combination with the highest average match score.
        Saves the result to disk for future runs.

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
                self._font = ImageFont.truetype(self._font_path, size)
                self._font_size = size
                self._render_mode = mode
                self._render_all_templates()

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
        self._font = ImageFont.truetype(self._font_path, best_size)
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
        """Render all skill, rank, and digit templates."""
        # Skills
        self._skill_templates.clear()
        self._skill_width_index.clear()
        for name in self._skill_names:
            tpl = self._render_template(name)
            if tpl is not None:
                self._skill_templates[name] = tpl
                w = tpl.shape[1]
                self._skill_width_index.setdefault(w, []).append((name, tpl))

        # Ranks
        self._rank_templates.clear()
        self._rank_width_index.clear()
        for name in self._rank_names:
            tpl = self._render_template(name)
            if tpl is not None:
                self._rank_templates[name] = tpl
                w = tpl.shape[1]
                self._rank_width_index.setdefault(w, []).append((name, tpl))

        # Digits (0-9)
        self._digit_templates.clear()
        for ch in "0123456789":
            tpl = self._render_template(ch)
            if tpl is not None:
                self._digit_templates[ch] = tpl

        # All digits have the same advance width in a monospace-ish bold font
        if self._digit_templates:
            self._digit_advance = self._digit_templates["0"].shape[1]

        log.debug("Templates: %d skills, %d ranks, %d digits",
                  len(self._skill_templates), len(self._rank_templates),
                  len(self._digit_templates))

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

    def _load_captured_templates(self) -> None:
        """Load game-captured templates from disk, replacing PIL-rendered ones.

        Captured templates come from the actual Scaleform renderer and match
        much better than PIL/FreeType-rendered approximations.
        """
        loaded = {"skills": 0, "ranks": 0, "digits": 0}
        self._captured_skill_lookup.clear()
        self._captured_rank_lookup.clear()

        # Skills
        skill_dir = CAPTURED_DIR / "skills"
        if skill_dir.exists():
            for path in skill_dir.glob("*.png"):
                name = self._name_from_filename(path.stem)
                if name not in self._skill_templates:
                    continue  # skip unknown names
                tpl = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if tpl is None:
                    continue
                self._captured_skill_lookup[self._image_key(tpl)] = name
                loaded["skills"] += 1

        # Ranks
        rank_dir = CAPTURED_DIR / "ranks"
        if rank_dir.exists():
            for path in rank_dir.glob("*.png"):
                name = self._name_from_filename(path.stem)
                if name not in self._rank_templates:
                    continue
                tpl = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if tpl is None:
                    continue
                self._captured_rank_lookup[self._image_key(tpl)] = name
                loaded["ranks"] += 1

        # Digits
        digit_dir = CAPTURED_DIR / "digits"
        if digit_dir.exists():
            for path in digit_dir.glob("*.png"):
                ch = path.stem
                if len(ch) != 1 or ch not in "0123456789":
                    continue
                tpl = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if tpl is None:
                    continue
                self._digit_templates[ch] = tpl
                loaded["digits"] += 1
            # Recompute digit advance from captured templates
            if self._digit_templates:
                self._digit_advance = max(
                    t.shape[1] for t in self._digit_templates.values()
                )

        total = sum(loaded.values())
        if total > 0:
            log.info("Loaded captured templates: %d skills, %d ranks, %d digits",
                     loaded["skills"], loaded["ranks"], loaded["digits"])

    def _clean_capture(self, cell_gray: np.ndarray, padding: int = 1) -> Optional[np.ndarray]:
        """Binarize and tight-crop a cell image for capture, removing noise."""
        cell_bin = self._to_binary(cell_gray)
        return self._tight_crop(cell_bin, padding=padding)

    def capture_skill(self, name: str, cell_gray: np.ndarray) -> bool:
        """Capture a game-rendered skill name cell as a template.

        Binarizes the cell first to remove background noise, then tight-crops
        and saves to disk. Updates the in-memory template index.
        """
        cropped = self._clean_capture(cell_gray)
        if cropped is None or cropped.shape[0] < 3 or cropped.shape[1] < 3:
            return False

        skill_dir = CAPTURED_DIR / "skills"
        skill_dir.mkdir(parents=True, exist_ok=True)
        path = skill_dir / f"{self._safe_filename(name)}.png"

        if path.exists():
            return False

        cv2.imwrite(str(path), cropped)
        self._captured_skill_lookup[self._image_key(cropped)] = name

        log.debug("Captured skill template: %s (%dx%d)",
                  name, cropped.shape[1], cropped.shape[0])
        return True

    def capture_rank(self, name: str, cell_gray: np.ndarray) -> bool:
        """Capture a game-rendered rank name cell as a template."""
        cropped = self._clean_capture(cell_gray)
        if cropped is None or cropped.shape[0] < 3 or cropped.shape[1] < 3:
            return False

        rank_dir = CAPTURED_DIR / "ranks"
        rank_dir.mkdir(parents=True, exist_ok=True)
        path = rank_dir / f"{self._safe_filename(name)}.png"

        if path.exists():
            return False

        cv2.imwrite(str(path), cropped)
        self._captured_rank_lookup[self._image_key(cropped)] = name

        log.debug("Captured rank template: %s (%dx%d)",
                  name, cropped.shape[1], cropped.shape[0])
        return True

    def capture_digits(self, number_text: str, cell_gray: np.ndarray) -> int:
        """Capture individual digit glyphs from a points cell.

        Finds actual digit blobs via connected-component analysis rather than
        assuming fixed spacing. Pairs blobs left-to-right with the known
        number string. Returns the count of newly captured digits.
        """
        digits_only = "".join(ch for ch in number_text if ch in "0123456789")
        if not digits_only:
            return 0

        cell_bin = self._to_binary(cell_gray)

        # Find digit blobs by grouping consecutive bright columns
        col_sums = np.sum(cell_bin > 0, axis=0)
        bright = col_sums > 0

        blobs: list[tuple[int, int]] = []  # (start_col, end_col) per blob
        in_blob = False
        start = 0
        for x in range(len(bright)):
            if bright[x] and not in_blob:
                start = x
                in_blob = True
            elif not bright[x] and in_blob:
                blobs.append((start, x))
                in_blob = False
        if in_blob:
            blobs.append((start, len(bright)))

        # Merge blobs that are very close (< 2px gap) — parts of same digit
        merged: list[tuple[int, int]] = []
        for s, e in blobs:
            if merged and s - merged[-1][1] < 2:
                merged[-1] = (merged[-1][0], e)
            else:
                merged.append((s, e))

        if len(merged) != len(digits_only):
            log.debug("Digit capture: %d blobs for %d digits — skipping",
                      len(merged), len(digits_only))
            return 0

        digit_dir = CAPTURED_DIR / "digits"
        digit_dir.mkdir(parents=True, exist_ok=True)
        captured = 0

        # Compute expected single-digit width range from existing templates
        if self._digit_templates:
            ref_w = max(t.shape[1] for t in self._digit_templates.values())
        else:
            ref_w = cell_bin.shape[0]  # rough estimate: digit width ~ cell height
        max_digit_w = int(ref_w * 1.5)

        for (col_start, col_end), ch in zip(merged, digits_only):
            blob_w = col_end - col_start
            if blob_w > max_digit_w:
                log.debug("Digit capture: blob too wide (%dpx > %dpx) — skipping %s",
                          blob_w, max_digit_w, ch)
                continue

            path = digit_dir / f"{ch}.png"
            if path.exists():
                continue

            digit_region = cell_bin[:, col_start:col_end]
            cropped = self._tight_crop(digit_region, padding=0)
            if cropped is not None and cropped.shape[0] >= 3 and cropped.shape[1] >= 3:
                cv2.imwrite(str(path), cropped)
                self._digit_templates[ch] = cropped
                log.debug("Captured digit template: %s (%dx%d)",
                          ch, cropped.shape[1], cropped.shape[0])
                captured += 1

        if captured > 0 and self._digit_templates:
            self._digit_advance = max(
                t.shape[1] for t in self._digit_templates.values()
            )

        return captured

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
        advance widths and kerning. This should match the game's rendering
        more closely since both use the font's built-in metrics."""
        if not self._font:
            return None

        # Get full text bounding box
        bbox = self._font.getbbox(text)
        if not bbox:
            return None

        pad = 4
        canvas_w = (bbox[2] - bbox[0]) + pad * 2
        canvas_h = (bbox[3] - bbox[1]) + pad * 2

        img = Image.new("L", (canvas_w, canvas_h), 0)
        draw = ImageDraw.Draw(img)
        draw.text((pad - bbox[0], pad - bbox[1]), text, fill=255, font=self._font)

        arr = np.array(img)
        return self._tight_crop(arr, padding=1)

    def _render_tight(self, text: str) -> Optional[np.ndarray]:
        """Render text character-by-character with GLYPH_GAP pixel spacing.

        Draws all characters on a single PIL canvas with tight inter-glyph
        spacing (GLYPH_GAP pixels between visible glyph edges) to match
        the game's compact text rendering. Because every character is drawn
        at the same y-origin on one canvas, baseline alignment is handled
        naturally by PIL (ascenders, descenders, etc. all correct).
        """
        # Collect (character, bbox) pairs; None bbox = space
        entries: list[tuple[str, Optional[tuple]]] = []
        for ch in text:
            if ch == ' ':
                entries.append((ch, None))
            else:
                bbox = self._font.getbbox(ch)
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
                total_w += max(2, self._font_size // 3)
            else:
                total_w += (b[2] - b[0])
        total_w += GLYPH_GAP * max(0, len(entries) - 1)

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
                x += max(2, self._font_size // 3) + GLYPH_GAP
                continue
            left, _top, right, _bottom = b
            # Position so visible left edge lands at x (subtract left bearing)
            draw.text((x - left, y_origin), ch, fill=255, font=self._font)
            x += (right - left) + GLYPH_GAP

        arr = np.array(img)
        return self._tight_crop(arr, padding=1)

    def _render_single_char(self, ch: str) -> Optional[np.ndarray]:
        """Render a single character and tight-crop it."""
        if not self._font:
            return None

        bbox = self._font.getbbox(ch)
        if not bbox:
            return None

        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        pad = 8
        canvas_w = text_w + pad * 2
        canvas_h = text_h + pad * 2
        img = Image.new("L", (canvas_w, canvas_h), 0)
        draw = ImageDraw.Draw(img)
        draw.text((pad - bbox[0], pad - bbox[1]), ch, fill=255, font=self._font)

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
        hash lookup). Falls back to fuzzy PIL template matching if no exact
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
                    return (name, 1.0)

        # Fall back to fuzzy PIL template matching
        if not self._skill_width_index:
            return None
        return self._match_against_index(
            cell_gray, self._skill_width_index, SKILL_THRESHOLD)

    def match_rank(self, cell_gray: np.ndarray) -> Optional[tuple[str, float]]:
        """Match a cell image against rank name templates.

        Tries exact pixel-match against captured game templates first.
        Falls back to fuzzy PIL template matching.

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
                    return (name, 1.0)

        # Fall back to fuzzy PIL template matching
        if not self._rank_width_index:
            return None
        return self._match_against_index(
            cell_gray, self._rank_width_index, RANK_THRESHOLD)

    def read_points(self, cell_binary: np.ndarray) -> Optional[str]:
        """Read an integer value from a cell image using digit templates.

        Greedily matches digits left-to-right across the cell: at each
        position, picks the highest-scoring digit above threshold, then
        advances by the digit width. Points are always integers (no decimals).

        Returns the number as a string (e.g., "6256"), or None.
        """
        if not self._calibrated or not self._digit_templates:
            return None

        cell_h, cell_w = cell_binary.shape[:2]
        if cell_h < 4 or cell_w < 4:
            return None

        cell_bin = self._to_binary(cell_binary)

        # Find where digits start (first bright column)
        col_sums = np.sum(cell_bin > 0, axis=0)
        bright_cols = np.where(col_sums > 0)[0]
        if len(bright_cols) == 0:
            return None

        # Greedy left-to-right matching: slide a window across the cell,
        # at each position try all 10 digits and pick the best
        digits: list[str] = []
        x = max(0, int(bright_cols[0]) - 1)  # start just before first bright pixel
        advance = self._digit_advance

        while x + advance <= cell_w:
            best_ch = None
            best_score = DIGIT_THRESHOLD

            # Extract a fixed-width region at position x (one digit wide)
            region = cell_bin[:, x:x + advance]
            rh, rw = region.shape

            for ch, tpl in self._digit_templates.items():
                th, tw = tpl.shape
                if tw > rw or th > rh:
                    continue

                tpl_bin = self._to_binary(tpl)
                max_val = self._template_match(region, tpl_bin)

                if max_val > best_score:
                    best_score = max_val
                    best_ch = ch

            if best_ch is not None:
                digits.append(best_ch)
                x += advance  # advance by one digit width
            else:
                x += 1  # no match here, slide forward by 1px

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
        ch, cw = cell.shape[:2]

        # Pick the right template pool
        templates = {}
        if match_type == "skill":
            templates = self._skill_templates
        elif match_type == "rank":
            templates = self._rank_templates

        # Build binary images (same as matching pipeline)
        cell_bin = self._to_binary(cell)

        # If we have a matched name, use it; otherwise brute-force the best
        tpl = None
        best_name = match_name
        best_score = 0.0

        if match_name and match_name in templates:
            tpl = templates[match_name]
            th, tw = tpl.shape
            if tw <= cw and th <= ch:
                tpl_bin = self._to_binary(tpl)
                best_score = self._template_match(cell_bin, tpl_bin)
        else:
            # No match — find the best template for overlay anyway
            for name, t in templates.items():
                th, tw = t.shape
                if tw > cw or th > ch:
                    continue
                t_bin = self._to_binary(t)
                score = self._template_match(cell_bin, t_bin)
                if score > best_score:
                    best_score = score
                    best_name = name
                    tpl = t

        overlay = np.zeros((ch, cw, 3), dtype=np.uint8)
        overlay[:, :, 2] = cell_bin  # Red = game cell (binary)

        if tpl is not None:
            tpl_bin = self._to_binary(tpl)
            th, tw = tpl_bin.shape
            if tw <= cw and th <= ch:
                result = cv2.matchTemplate(cell_bin, tpl_bin, cv2.TM_CCOEFF_NORMED)
                _, _, _, max_loc = cv2.minMaxLoc(result)
                bx, by = max_loc
                overlay[by:by + th, bx:bx + tw, 1] = tpl_bin  # Green = template

        # Scale up 4x for visibility
        scaled = cv2.resize(overlay, (cw * 4, ch * 4),
                            interpolation=cv2.INTER_NEAREST)

        # Add text annotation right-aligned inside the cell
        status = "OK" if match_name else "FAIL"
        text = f"{status}: {best_name} ({best_score:.3f})"
        font_scale = 0.4
        (text_w, text_h), _ = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        text_x = cw * 4 - text_w - 4
        cv2.putText(scaled, text, (text_x, ch * 4 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1)

        path = os.path.join(output_dir, f"overlay_{label}.png")
        cv2.imwrite(path, scaled)

    def save_digit_overlay_debug(self, label: str, cell_binary: np.ndarray,
                                 output_dir: str) -> None:
        """Save a debug overlay for digit matching on a points cell."""
        os.makedirs(output_dir, exist_ok=True)
        ch, cw = cell_binary.shape[:2]

        cell_bin = self._to_binary(cell_binary)
        overlay = np.zeros((ch, cw, 3), dtype=np.uint8)
        overlay[:, :, 2] = cell_bin  # Red = game cell (binary)

        # Show where each digit template matches
        for char, tpl in self._digit_templates.items():
            tpl_bin = self._to_binary(tpl)
            th, tw = tpl_bin.shape
            if tw > cw or th > ch:
                continue
            result = cv2.matchTemplate(cell_bin, tpl_bin, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= DIGIT_THRESHOLD)
            for y, x in zip(*locations):
                overlay[y:y + th, x:x + tw, 1] = np.maximum(
                    overlay[y:y + th, x:x + tw, 1], tpl_bin)

        scaled = cv2.resize(overlay, (cw * 4, ch * 4),
                            interpolation=cv2.INTER_NEAREST)
        path = os.path.join(output_dir, f"overlay_digits_{label}.png")
        cv2.imwrite(path, scaled)

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

    def _score_candidates(self, cell_bin: np.ndarray,
                           candidates: list[tuple[str, np.ndarray]],
                           threshold: float) -> Optional[tuple[str, float]]:
        """Score candidate templates against a binary cell image.

        Returns the best match above threshold, using a width-preference
        tie-breaker: among all matches within SCORE_MARGIN of the best score,
        prefer the widest template (longest name covers most of the cell).
        """
        cell_h, cell_w = cell_bin.shape[:2]
        matches: list[tuple[str, float, int]] = []
        best_raw = 0.0

        for name, tpl in candidates:
            th, tw = tpl.shape
            if tw > cell_w or th > cell_h:
                continue

            tpl_bin = self._to_binary(tpl)
            score = self._template_match(cell_bin, tpl_bin)

            if score > best_raw:
                best_raw = score

            if score >= threshold:
                matches.append((name, score, tw))

        if not matches:
            if best_raw > 0:
                log.debug("Below threshold: best raw=%.3f (need %.2f), "
                          "cell %dx%d",
                          best_raw, threshold, cell_h, cell_w)
            return None

        best_match_score = max(s for _, s, _ in matches)
        score_margin = 0.10
        contenders = [(n, s, w) for n, s, w in matches
                      if s >= best_match_score - score_margin]

        contenders.sort(key=lambda x: (-x[2], -x[1]))
        winner_name, winner_score, _ = contenders[0]
        return (winner_name, winner_score)

    def _match_against_index(self, cell_gray: np.ndarray,
                             width_index: dict[int, list[tuple[str, np.ndarray]]],
                             threshold: float) -> Optional[tuple[str, float]]:
        """Match a cell image against PIL-rendered templates using width filtering.

        Measures the cell's text width from bright pixel extent and first tries
        only templates within ±WIDTH_TOLERANCE pixels of that width. Falls back
        to all templates if no width-filtered match is found.
        """
        cell_h, cell_w = cell_gray.shape[:2]
        if cell_h < 4 or cell_w < 4:
            return None

        cell_bin = self._to_binary(cell_gray)

        # Check there's actually text in the cell
        cols = np.any(cell_bin > 0, axis=0)
        if not np.any(cols):
            return None

        # Measure cell text width from bright pixel extent
        bright_cols = np.where(cols)[0]
        cell_text_width = int(bright_cols[-1] - bright_cols[0] + 1)

        # Phase 1: width-filtered candidates (±WIDTH_TOLERANCE)
        filtered: list[tuple[str, np.ndarray]] = []
        for w, entries in width_index.items():
            if abs(w - cell_text_width) <= WIDTH_TOLERANCE:
                filtered.extend(entries)

        if filtered:
            result = self._score_candidates(cell_bin, filtered, threshold)
            if result:
                return result

        # Phase 2: all candidates (fallback when no width-filtered match)
        all_candidates: list[tuple[str, np.ndarray]] = []
        for entries in width_index.values():
            all_candidates.extend(entries)

        return self._score_candidates(cell_bin, all_candidates, threshold)
