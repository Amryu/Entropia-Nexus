"""Nameplate-based mob name detection from the game screen.

Mob nameplates float above mobs in the 3D world. Each nameplate contains:
- Text: "L{level} {name} {maturity}" (order of name/maturity varies)
- HP bar: red fill (damage taken) / green (full HP) / blue-dark (empty)
- Chevron: solid ▼ = locked target, empty ▽ = next lock candidate

Detection strategy:
1. Find HP bars via HSV color detection (red/green horizontal bars)
2. For each HP bar, extract the text region above it
3. Detect the chevron below to identify locked target
4. OCR the locked target's nameplate text
5. Parse and fuzzy-match against known mob data
"""

import re
import threading
import time
from difflib import SequenceMatcher

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.constants import EVENT_MOB_TARGET_CHANGED
from ..core.gil_yield import GilYielder
from ..core.logger import get_logger

log = get_logger("MobDetector")

# Detection timing
MOB_DETECT_INTERVAL = 0.5  # seconds (~2 Hz)

# HP bar color ranges in HSV (OpenCV: H 0-180, S 0-255, V 0-255)
# Red HP bar: hue wraps around 0, so check two ranges
HP_RED_LOW1 = np.array([0, 80, 100])
HP_RED_HIGH1 = np.array([10, 255, 255])
HP_RED_LOW2 = np.array([170, 80, 100])
HP_RED_HIGH2 = np.array([180, 255, 255])

# Green HP bar
HP_GREEN_LOW = np.array([35, 80, 100])
HP_GREEN_HIGH = np.array([85, 255, 255])

# Blue/dark empty portion of HP bar
HP_BLUE_LOW = np.array([95, 40, 60])
HP_BLUE_HIGH = np.array([130, 200, 200])

# Nameplate HP bar geometry constraints
MIN_BAR_WIDTH = 40
MAX_BAR_WIDTH = 300
MIN_BAR_HEIGHT = 3
MAX_BAR_HEIGHT = 16
MIN_BAR_ASPECT = 3.0  # width/height minimum ratio

# Text region relative to HP bar
TEXT_REGION_ABOVE_RATIO = 2.5   # text region height = bar_height * ratio, above the bar
TEXT_REGION_PADDING_X = 0.3     # extend text region width by this ratio on each side

# Chevron detection region below HP bar
CHEVRON_REGION_BELOW_PX = 20
CHEVRON_REGION_WIDTH_PX = 30

# Nameplate text pattern: "L{level} {words...}"
NAMEPLATE_PATTERN = re.compile(
    r'[Ll](\d+)\s+(.+)',
)


class NameplateInfo:
    """Parsed nameplate data."""
    __slots__ = ("x", "y", "width", "height", "is_locked", "raw_text",
                 "level", "mob_name", "maturity", "confidence")

    def __init__(self):
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self.is_locked = False
        self.raw_text = ""
        self.level = 0
        self.mob_name = ""
        self.maturity = ""
        self.confidence = 0.0


class MobNameDetector:
    """Detects mob nameplates in the game screen and reads the locked target's name.

    Uses HP bar color detection as anchor points, then OCRs the text above.
    Identifies the locked target by detecting the solid chevron below the HP bar.

    Supports two modes:
    - **Push mode** (FrameDistributor): subscribes with divisor=5 (2 Hz).
      Because HSV+contour+OCR can exceed 50 ms, the distributor callback
      drops the frame into a single-slot queue and a worker thread processes it.
    - **Legacy poll mode** (ScreenCapturer): runs its own thread with
      sleep-based polling.
    """

    def __init__(self, config, event_bus, frame_source, recognizer):
        self._config = config
        self._event_bus = event_bus
        self._recognizer = recognizer
        self._running = False
        self._thread = None
        self._last_mob_name = None
        self._last_level = None
        self._last_maturity = None
        self._known_mobs: list[str] = []
        self._known_maturities: list[str] = []
        self._game_hwnd = None
        self._game_geometry: tuple[int, int, int, int] | None = None

        # Detect frame source type
        self._distributor = None
        self._subscription = None
        self._capturer = None

        from .frame_distributor import FrameDistributor
        if isinstance(frame_source, FrameDistributor):
            self._distributor = frame_source
        else:
            self._capturer = frame_source

        # Worker queue for push mode (single-slot, newest-wins)
        self._frame_slot: np.ndarray | None = None
        self._frame_cond = threading.Condition()

    def set_known_mobs(self, mob_names: list[str]):
        """Set known mob names for fuzzy matching (from Nexus API)."""
        self._known_mobs = mob_names

    def set_known_maturities(self, maturities: list[str]):
        """Set known maturity names for parsing."""
        self._known_maturities = maturities

    def set_game_hwnd(self, hwnd: int,
                      geometry: tuple[int, int, int, int] | None = None):
        """Set the game window handle and geometry for capture."""
        self._game_hwnd = hwnd
        self._game_geometry = geometry

    def start(self):
        if self._running:
            return
        self._running = True

        if self._distributor is not None:
            # Worker thread processes frames from the single-slot queue
            self._thread = threading.Thread(
                target=self._worker_loop, daemon=True, name="mob-detector",
            )
            self._thread.start()
            self._subscription = self._distributor.subscribe(
                "mob-detector", self._on_frame, hz=2,
            )
            log.info("Started (push mode, worker thread)")
        else:
            self._thread = threading.Thread(
                target=self._poll_loop, daemon=True, name="mob-detector",
            )
            self._thread.start()
            log.info("Started (poll mode)")

    def stop(self):
        self._running = False
        if self._subscription is not None:
            self._subscription.enabled = False
            self._subscription = None
        # Wake the worker thread so it can exit
        with self._frame_cond:
            self._frame_cond.notify()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def detect_nameplates(self, image: np.ndarray) -> list[NameplateInfo]:
        """Detect all visible nameplates in a game screenshot.

        Args:
            image: BGR game window capture (numpy array)

        Returns:
            List of NameplateInfo for each detected nameplate.
        """
        if cv2 is None:
            return []

        nameplates = []
        hp_bars = self._find_hp_bars(image)

        for bx, by, bw, bh in hp_bars:
            info = NameplateInfo()
            info.x = bx
            info.y = by
            info.width = bw
            info.height = bh

            # Check for locked target chevron below the bar
            info.is_locked = self._detect_locked_chevron(image, bx, by, bw, bh)

            # Extract and OCR text region above the bar
            text_region = self._extract_text_region(image, bx, by, bw, bh)
            if text_region is not None and text_region.size > 0:
                raw_text = self._ocr_nameplate(text_region)
                if raw_text:
                    info.raw_text = raw_text
                    self._parse_nameplate_text(info, raw_text)

            if info.mob_name:
                nameplates.append(info)

        return nameplates

    def get_locked_target(self, image: np.ndarray) -> NameplateInfo | None:
        """Detect nameplates and return the locked target, if any.

        Falls back to the largest/closest nameplate if no chevron is detected.
        """
        nameplates = self.detect_nameplates(image)
        if not nameplates:
            return None

        # Prefer locked target
        locked = [n for n in nameplates if n.is_locked]
        if locked:
            return locked[0]

        # Fallback: largest bar (likely closest mob / main target)
        return max(nameplates, key=lambda n: n.width)

    # ------------------------------------------------------------------
    # Push mode (FrameDistributor)
    # ------------------------------------------------------------------

    def _on_frame(self, frame: np.ndarray, timestamp: float):
        """Callback from FrameDistributor — drops frame into worker queue."""
        with self._frame_cond:
            self._frame_slot = frame  # newest-wins: overwrite any pending frame
            self._frame_cond.notify()

    def _worker_loop(self):
        """Worker thread: waits for frames from the distributor callback."""
        while self._running:
            with self._frame_cond:
                while self._frame_slot is None and self._running:
                    self._frame_cond.wait(timeout=1.0)
                if not self._running:
                    break
                frame = self._frame_slot
                self._frame_slot = None

            try:
                self._process_image(frame)
            except Exception as e:
                log.error("Error: %s", e)

    # ------------------------------------------------------------------
    # Legacy poll mode
    # ------------------------------------------------------------------

    def _poll_loop(self):
        while self._running:
            try:
                self._detect_and_publish()
            except Exception as e:
                log.error("Error: %s", e)
            time.sleep(MOB_DETECT_INTERVAL)

    def _detect_and_publish(self):
        if not self._game_hwnd:
            return

        image = self._capturer.capture_window(self._game_hwnd,
                                               geometry=self._game_geometry)
        if image is None:
            return

        self._process_image(image)

    # ------------------------------------------------------------------
    # Core image processing (shared by both modes)
    # ------------------------------------------------------------------

    def _process_image(self, image: np.ndarray):
        """Process a captured game frame: detect nameplates and publish."""
        target = self.get_locked_target(image)
        if not target or not target.mob_name:
            return

        # Only publish if the target changed
        if (target.mob_name != self._last_mob_name
                or target.level != self._last_level
                or target.maturity != self._last_maturity):
            self._last_mob_name = target.mob_name
            self._last_level = target.level
            self._last_maturity = target.maturity

            self._event_bus.publish(EVENT_MOB_TARGET_CHANGED, {
                "mob_name": target.mob_name,
                "maturity": target.maturity,
                "level": target.level,
                "raw_text": target.raw_text,
                "confidence": target.confidence,
                "source": "ocr",
                "is_locked": target.is_locked,
            })

    def _find_hp_bars(self, image: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Find HP bars in the image using HSV color detection.

        Returns list of (x, y, width, height) bounding boxes.
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Detect red HP bar regions (two ranges because red wraps in HSV)
        red_mask1 = cv2.inRange(hsv, HP_RED_LOW1, HP_RED_HIGH1)
        red_mask2 = cv2.inRange(hsv, HP_RED_LOW2, HP_RED_HIGH2)
        red_mask = red_mask1 | red_mask2

        # Detect green HP bar regions
        green_mask = cv2.inRange(hsv, HP_GREEN_LOW, HP_GREEN_HIGH)

        # Detect blue (empty) HP bar regions
        blue_mask = cv2.inRange(hsv, HP_BLUE_LOW, HP_BLUE_HIGH)

        # Combine: an HP bar has red/green fill and often a blue empty portion
        hp_mask = red_mask | green_mask | blue_mask

        # Morphological close to merge fill + empty into one bar
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
        hp_mask = cv2.morphologyEx(hp_mask, cv2.MORPH_CLOSE, kernel)

        # Find contours
        contours, _ = cv2.findContours(
            hp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        bars = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            aspect = w / h if h > 0 else 0

            if (MIN_BAR_WIDTH <= w <= MAX_BAR_WIDTH
                    and MIN_BAR_HEIGHT <= h <= MAX_BAR_HEIGHT
                    and aspect >= MIN_BAR_ASPECT):
                bars.append((x, y, w, h))

        # Sort by Y position (top to bottom), then by size (larger first for same Y)
        bars.sort(key=lambda b: (b[1], -b[2]))

        # Deduplicate overlapping bars (keep larger)
        filtered = []
        for bar in bars:
            overlap = False
            for existing in filtered:
                if self._bars_overlap(bar, existing):
                    overlap = True
                    break
            if not overlap:
                filtered.append(bar)

        return filtered

    @staticmethod
    def _bars_overlap(a, b, threshold=0.5):
        """Check if two bars overlap significantly."""
        ax1, ay1, aw, ah = a
        bx1, by1, bw, bh = b
        ax2, ay2 = ax1 + aw, ay1 + ah
        bx2, by2 = bx1 + bw, by1 + bh

        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)

        if ix1 >= ix2 or iy1 >= iy2:
            return False

        intersection = (ix2 - ix1) * (iy2 - iy1)
        smaller_area = min(aw * ah, bw * bh)
        return intersection / smaller_area > threshold if smaller_area > 0 else False

    def _detect_locked_chevron(self, image: np.ndarray,
                                bx: int, by: int, bw: int, bh: int) -> bool:
        """Detect if there's a solid white chevron (▼) below the HP bar.

        The locked target has a solid filled downward-pointing triangle.
        """
        img_h, img_w = image.shape[:2]

        # Region below the HP bar, centered
        cx = bx + bw // 2
        rx = max(0, cx - CHEVRON_REGION_WIDTH_PX // 2)
        ry = min(by + bh, img_h - 1)
        rw = min(CHEVRON_REGION_WIDTH_PX, img_w - rx)
        rh = min(CHEVRON_REGION_BELOW_PX, img_h - ry)

        if rw <= 0 or rh <= 0:
            return False

        region = image[ry:ry + rh, rx:rx + rw]
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        # A solid white chevron has a cluster of bright pixels
        # forming a triangle shape. Simple heuristic: count bright pixels.
        bright_pixels = np.sum(gray > 200)
        total_pixels = gray.size

        # A solid chevron typically fills ~15-40% of this small region
        ratio = bright_pixels / total_pixels if total_pixels > 0 else 0
        return ratio > 0.08

    def _extract_text_region(self, image: np.ndarray,
                              bx: int, by: int, bw: int, bh: int) -> np.ndarray | None:
        """Extract the text region above an HP bar."""
        img_h, img_w = image.shape[:2]

        text_height = max(int(bh * TEXT_REGION_ABOVE_RATIO), 18)
        padding_x = int(bw * TEXT_REGION_PADDING_X)

        tx = max(0, bx - padding_x)
        ty = max(0, by - text_height)
        tw = min(bw + 2 * padding_x, img_w - tx)
        th = by - ty

        if tw <= 0 or th <= 0:
            return None

        return image[ty:ty + th, tx:tx + tw]

    def _ocr_nameplate(self, text_region: np.ndarray) -> str:
        """OCR a nameplate text region.

        The text is white/light on a variable 3D game background.
        Uses Otsu's thresholding to adaptively separate text from background.
        """
        gray = cv2.cvtColor(text_region, cv2.COLOR_BGR2GRAY)

        # Upscale for better OCR accuracy
        scale = 3.0
        h, w = gray.shape
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)),
                          interpolation=cv2.INTER_CUBIC)

        # Otsu's thresholding adapts to the local contrast
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Check if text is inverted (more white than black = background is bright)
        white_ratio = np.sum(binary > 128) / binary.size
        if white_ratio > 0.5:
            binary = cv2.bitwise_not(binary)

        # Small morphological open to remove speckle noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        text = self._recognizer.read_text(binary, config="--psm 7")
        return text.strip() if text else ""

    def _parse_nameplate_text(self, info: NameplateInfo, raw_text: str):
        """Parse nameplate text like 'L31 Hogglo Young' into components.

        Handles:
        - "L31 Hogglo Young" → level=31, name=Hogglo, maturity=Young
        - "L31 Young Hogglo" → level=31, name=Hogglo, maturity=Young
        - "L31 Hogglo" → level=31, name=Hogglo (single-maturity mob)
        """
        match = NAMEPLATE_PATTERN.match(raw_text)
        if not match:
            # Try without level prefix (OCR might miss the L)
            parts = raw_text.split()
            if not parts:
                return
            level_str = parts[0]
            if level_str.startswith(("L", "l")) and level_str[1:].isdigit():
                info.level = int(level_str[1:])
                remaining = " ".join(parts[1:])
            elif level_str.isdigit():
                info.level = int(level_str)
                remaining = " ".join(parts[1:])
            else:
                remaining = raw_text
        else:
            info.level = int(match.group(1))
            remaining = match.group(2).strip()

        if not remaining:
            return

        words = remaining.split()
        info.confidence = 0.5

        if len(words) == 1:
            # Single word: just the mob name (or could be mob with default maturity)
            info.mob_name = self._fuzzy_match_mob(words[0])
            info.confidence = 0.7
        elif len(words) >= 2:
            # Multiple words — try to identify which is name vs maturity
            best_match = self._split_name_maturity(words)
            if best_match:
                info.mob_name = best_match[0]
                info.maturity = best_match[1]
                info.confidence = best_match[2]
            else:
                # Fallback: assume last word is maturity, rest is name
                # (handles multi-word mob names like "Spina Worker")
                info.mob_name = self._fuzzy_match_mob(words[0])
                info.maturity = " ".join(words[1:])
                info.confidence = 0.4

    def _split_name_maturity(self, words: list[str]) -> tuple[str, str, float] | None:
        """Try to split words into (mob_name, maturity, confidence).

        Tests all possible splits and picks the best fuzzy match.
        """
        best = None
        best_score = 0

        for i in range(1, len(words)):
            # Forward: words[:i] = name, words[i:] = maturity
            name_part = " ".join(words[:i])
            maturity_part = " ".join(words[i:])

            name_match, name_score = self._best_fuzzy_match(name_part, self._known_mobs)
            mat_match, mat_score = self._best_fuzzy_match(maturity_part, self._known_maturities)

            forward_score = (name_score + mat_score) / 2
            if forward_score > best_score and name_score >= 0.6:
                best_score = forward_score
                best = (name_match or name_part, mat_match or maturity_part, forward_score)

            # Reverse: words[:i] = maturity, words[i:] = name
            name_match_r, name_score_r = self._best_fuzzy_match(maturity_part, self._known_mobs)
            mat_match_r, mat_score_r = self._best_fuzzy_match(name_part, self._known_maturities)

            reverse_score = (name_score_r + mat_score_r) / 2
            if reverse_score > best_score and name_score_r >= 0.6:
                best_score = reverse_score
                best = (name_match_r or maturity_part, mat_match_r or name_part, reverse_score)

        return best

    def _fuzzy_match_mob(self, text: str) -> str:
        """Fuzzy match a mob name against known mobs. Returns best match or original."""
        if not self._known_mobs:
            return text
        match, score = self._best_fuzzy_match(text, self._known_mobs)
        return match if match and score >= 0.6 else text

    @staticmethod
    def _best_fuzzy_match(text: str, candidates: list[str]) -> tuple[str | None, float]:
        """Find the best fuzzy match from a list of candidates."""
        if not candidates or not text:
            return None, 0

        text_lower = text.lower()
        best_match = None
        best_score = 0
        yielder = GilYielder()

        for candidate in candidates:
            score = SequenceMatcher(None, text_lower, candidate.lower()).ratio()
            if score > best_score:
                best_score = score
                best_match = candidate
            yielder.yield_if_needed()

        return best_match, best_score
