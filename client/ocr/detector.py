import ctypes
import ctypes.wintypes
import os
import numpy as np
from pathlib import Path
from typing import Optional

try:
    import cv2
except ImportError:
    cv2 = None

from .capturer import ScreenCapturer
from ..core.logger import get_logger

log = get_logger("Detector")

# Debug image output directory
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "..", "debug_output")
SAVE_DEBUG_IMAGES = True

# Win32 API for window lookup (no debugger, no attachment — just title search)
user32 = ctypes.windll.user32

GAME_WINDOW_TITLE_PREFIX = "Entropia Universe Client"

# Approximate relative positions within the skills window (normalized 0-1)
# Measured from the reference screenshot (Skills.PNG)
#
# Column layout: NAME | RANK | POINTS
# Each row has text in the top portion and a progress bar in the bottom portion.
# RANK cells have a rank-progress bar; POINTS cells have a skill-progress bar.
WINDOW_LAYOUT = {
    "sidebar_width_ratio": 0.22,     # Left sidebar takes ~22% of window width
    "header_height_ratio": 0.08,     # Top header area ("SKILLS" title)
    "col_header_ratio": 0.10,        # Column headers row (SKILL NAME, RANK, POINTS)
    "table_top_ratio": 0.151,        # Table data starts below column headers (y≈84 at 557px)
    "table_bottom_ratio": 0.72,      # Table ends after 12 data rows + margin (y≈401 at 557px)
    "total_row_ratio": 0.70,         # "Total: XXXXX" row (between table and pagination)
    "pagination_ratio": 0.87,        # Pagination area
    "col_name_start": 0.22,          # Skill name column start (after sidebar)
    "col_name_end": 0.52,            # Skill name column end
    "col_rank_start": 0.52,          # Rank column start (text + rank bar below)
    "col_rank_end": 0.72,            # Rank column end
    "col_points_start": 0.72,        # Points column start (number + progress bar below)
    "col_points_end": 0.99,          # Points column end (includes progress bar area)
    "row_height_ratio": 0.045,       # Each skill row is ~4.5% of panel height (25px at 557px)
    "row_text_ratio": 0.70,          # Top 70% of each row = text zone
    "row_bar_ratio": 0.30,           # Bottom 30% of each row = bar zone
    # Sidebar category selection indicator (orange bar)
    "sidebar_indicator_width": 0.01, # Orange bar is ~1% of panel width
    "sidebar_first_item_y": 0.09,    # "ALL CATEGORIES" starts at ~9% of panel height
    "sidebar_item_height": 0.035,    # Each sidebar item is ~3.5% of panel height
}

# The skills window background is dark navy/slate blue
DARK_THRESHOLD_LOW = 20
DARK_THRESHOLD_HIGH = 70

# Skills panel dimension constraints
MIN_PANEL_WIDTH = 350
MIN_PANEL_HEIGHT = 250
# At 1080p the skills panel is ~650-900px wide, ~500-700px tall.
# At 1440p/4K it scales up but rarely exceeds 1200px wide.
MAX_PANEL_WIDTH = 1200
MAX_PANEL_HEIGHT = 900

# Template matching
ASSETS_DIR = Path(__file__).parent.parent / "assets"
TEMPLATE_PATH = ASSETS_DIR / "skills_label.PNG"
TEMPLATE_MATCH_THRESHOLD = 0.7
TEMPLATE_HIGH_CONFIDENCE = 0.9   # Skip verification when match is this good
TEMPLATE_SCALES = [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 2.0]

# Template position within the skills panel (normalized 0-1).
# Measured by template-matching skills_label.PNG against Skills.PNG reference.
# The "SKILLS" label sits centered in the title bar at the top of the panel.
TEMPLATE_OFFSET_X = 0.46       # Template left edge at 46% of panel width
TEMPLATE_OFFSET_Y = 0.023      # Template top edge at 2.3% of panel height
TEMPLATE_WIDTH_RATIO = 0.075   # Template width is 7.5% of panel width
TEMPLATE_HEIGHT_RATIO = 0.036  # Template height is 3.6% of panel height

# Column header template matching
COL_HEADER_PATHS = {
    "name": ASSETS_DIR / "skill_name_label.PNG",
    "rank": ASSETS_DIR / "rank_label.PNG",
    "points": ASSETS_DIR / "points_label.PNG",
}
COL_HEADER_THRESHOLD = 0.8  # Match confidence for column header templates


def _find_game_window() -> Optional[tuple[int, int, int, int, int]]:
    """Find the Entropia Universe game window using Win32 EnumWindows.

    Returns (hwnd, x, y, width, height) of the game window's client area, or None.
    This is a plain window title lookup — no process attachment or debugging.
    """
    result = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def enum_callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if title.startswith(GAME_WINDOW_TITLE_PREFIX):
            log.info("Found game window: '%s'", title)
            rect = ctypes.wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            point = ctypes.wintypes.POINT(0, 0)
            user32.ClientToScreen(hwnd, ctypes.byref(point))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            log.debug("Client area: (%s,%s) %sx%s", point.x, point.y, w, h)
            result.append((int(hwnd), point.x, point.y, w, h))
            return False  # Stop enumerating
        return True

    log.debug("Enumerating windows for '%s...'", GAME_WINDOW_TITLE_PREFIX)
    user32.EnumWindows(enum_callback, 0)

    if not result:
        log.warning("No matching window found")
    return result[0] if result else None


class SkillsWindowDetector:
    """Detects and locates the skills window on screen.

    Step 1: Find the game window via Win32 API (window title lookup).
    Step 2: Within the game window region, find the skills panel using
            vision-based detection (dark rectangles, header verification).
    """

    def __init__(self, capturer: ScreenCapturer):
        if cv2 is None:
            raise ImportError("opencv-python is required")
        self._capturer = capturer
        self._cached_bounds: Optional[tuple[int, int, int, int]] = None
        self._game_hwnd: Optional[int] = None
        self._game_origin: tuple[int, int] = (0, 0)
        self._last_game_image: Optional[np.ndarray] = None

        # Load skills label template for template matching
        self._template: Optional[np.ndarray] = None
        if TEMPLATE_PATH.exists():
            tpl = cv2.imread(str(TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
            if tpl is not None:
                self._template = tpl
                log.info("Loaded template: %s (%dx%d)",
                         TEMPLATE_PATH.name, tpl.shape[1], tpl.shape[0])
            else:
                log.warning("Failed to read template: %s", TEMPLATE_PATH)
        else:
            log.warning("Template not found: %s", TEMPLATE_PATH)

        # Load column header templates for precise column positioning
        self._col_templates: dict[str, np.ndarray] = {}
        for col_name, path in COL_HEADER_PATHS.items():
            if path.exists():
                tpl = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self._col_templates[col_name] = tpl
                    log.info("Loaded column template: %s (%dx%d)",
                             col_name, tpl.shape[1], tpl.shape[0])

        # Cached template match positions (panel-local pixel coords)
        # Each entry: (x, y, w, h) relative to panel top-left
        self._title_match: Optional[tuple[int, int, int, int]] = None  # skills_label
        self._col_header_matches: Optional[dict[str, tuple[int, int, int, int]]] = None

    @property
    def game_hwnd(self) -> Optional[int]:
        """The HWND of the game window, if found."""
        return self._game_hwnd

    @property
    def game_origin(self) -> tuple[int, int]:
        """Screen coordinates of the game window's top-left corner."""
        return self._game_origin

    @property
    def last_game_image(self) -> Optional[np.ndarray]:
        """The most recent full game window capture (BGR)."""
        return self._last_game_image

    def detect(self) -> Optional[tuple[int, int, int, int]]:
        """Detect the skills window on screen.

        Returns (x, y, width, height) of the skills panel, or None if not found.
        """
        # Step 1: Find the game window
        game_rect = _find_game_window()
        if not game_rect:
            log.warning("Game window not found (looking for '%s...')",
                        GAME_WINDOW_TITLE_PREFIX)
            return self._cached_bounds

        hwnd, gx, gy, gw, gh = game_rect
        self._game_hwnd = hwnd
        self._game_origin = (gx, gy)
        log.info("Game window: (%s,%s) %sx%s hwnd=%s", gx, gy, gw, gh, hwnd)

        # Step 2: Capture the game window directly via PrintWindow (ignores overlays)
        game_image = self._capturer.capture_window(hwnd)
        if game_image is None:
            log.warning("PrintWindow capture failed, falling back to mss")
            game_image = self._capturer.capture_region(gx, gy, gw, gh)

        self._last_game_image = game_image
        gray = cv2.cvtColor(game_image, cv2.COLOR_BGR2GRAY)

        # Check if capture is all black (UIPI — game runs elevated, we don't)
        mean_brightness = float(np.mean(gray))
        log.debug("Capture mean brightness: %.1f", mean_brightness)
        if mean_brightness < 2.0:
            log.warning("Captured image is black! "
                        "The game may be running as Administrator. "
                        "Try running the client as Administrator too.")
            return self._cached_bounds

        bounds = self._find_skills_panel(gray, game_image, gx, gy)

        # Save annotated debug image on first successful detection
        if bounds and bounds != self._cached_bounds:
            self.save_debug_image(game_image, gx, gy, bounds)

        if bounds:
            self._cached_bounds = bounds
            return bounds

        # Save debug image even on failure (no bounds) for diagnostics
        if not self._cached_bounds:
            self.save_debug_image(game_image, gx, gy, None)

        return self._cached_bounds

    def capture_game(self) -> np.ndarray | None:
        """Capture the current game window image (via PrintWindow).

        Returns the full game window as BGR numpy array, or None.
        Also stores the result in last_game_image.
        """
        if not self._game_hwnd:
            return None
        image = self._capturer.capture_window(self._game_hwnd)
        if image is not None:
            self._last_game_image = image
        return image

    def _find_by_template(self, gray: np.ndarray, color: np.ndarray,
                          offset_x: int, offset_y: int
                          ) -> Optional[tuple[int, int, int, int]]:
        """Find the skills panel by template matching the 'SKILLS' title label.

        Tries exact scale (1.0) first since the skills window is fixed size.
        Falls back to multi-scale matching for different game resolutions.
        Returns screen-absolute (x, y, w, h) or None.
        """
        if self._template is None:
            return None

        img_h, img_w = gray.shape
        tpl_h, tpl_w = self._template.shape
        best_val = 0.0
        best_loc = (0, 0)
        best_scale = 1.0

        # Try exact scale first (skills window is fixed size)
        if tpl_w < img_w and tpl_h < img_h:
            result = cv2.matchTemplate(gray, self._template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= TEMPLATE_MATCH_THRESHOLD:
                best_val = max_val
                best_loc = max_loc
                log.debug("Template match at scale=1.0: %.3f at (%d,%d)",
                          best_val, best_loc[0], best_loc[1])

        # Fall back to multi-scale if exact match wasn't good enough
        if best_val < TEMPLATE_MATCH_THRESHOLD:
            for scale in TEMPLATE_SCALES:
                if scale == 1.0:
                    continue  # Already tried
                new_w = int(tpl_w * scale)
                new_h = int(tpl_h * scale)
                if new_w >= img_w or new_h >= img_h or new_w < 10 or new_h < 5:
                    continue

                scaled = cv2.resize(self._template, (new_w, new_h),
                                    interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
                result = cv2.matchTemplate(gray, scaled, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)

                if max_val > best_val:
                    best_val = max_val
                    best_loc = max_loc
                    best_scale = scale

        log.debug("Template match: best=%.3f at (%d,%d) scale=%.1f (threshold=%.1f)",
                  best_val, best_loc[0], best_loc[1], best_scale, TEMPLATE_MATCH_THRESHOLD)

        if best_val < TEMPLATE_MATCH_THRESHOLD:
            return None

        # Template matched at (tx, ty) — this is the title label position.
        # Since the skills window is fixed size, compute the full panel bounds
        # directly from the template position using known layout ratios.
        # This avoids fragile dark-edge scanning (the UI is semi-transparent).
        tx, ty = best_loc
        matched_w = int(tpl_w * best_scale)
        matched_h = int(tpl_h * best_scale)

        # Compute panel dimensions from template size and known ratios
        panel_w = int(matched_w / TEMPLATE_WIDTH_RATIO)
        panel_h = int(matched_h / TEMPLATE_HEIGHT_RATIO)

        # Compute panel origin from template position
        panel_left = tx - int(panel_w * TEMPLATE_OFFSET_X)
        panel_top = ty - int(panel_h * TEMPLATE_OFFSET_Y)

        # Clamp to image bounds
        panel_left = max(0, panel_left)
        panel_top = max(0, panel_top)
        if panel_left + panel_w > img_w:
            panel_w = img_w - panel_left
        if panel_top + panel_h > img_h:
            panel_h = img_h - panel_top

        if panel_w < MIN_PANEL_WIDTH or panel_w > MAX_PANEL_WIDTH:
            log.debug("Template: panel width %d out of range", panel_w)
            return None
        if panel_h < MIN_PANEL_HEIGHT or panel_h > MAX_PANEL_HEIGHT:
            log.debug("Template: panel height %d out of range", panel_h)
            return None

        # For high-confidence matches, skip verification (the template is
        # definitive and the UI is semi-transparent which confuses pixel checks)
        if best_val < TEMPLATE_HIGH_CONFIDENCE:
            if not self._verify_header(gray, color, panel_left, panel_top, panel_w, panel_h):
                log.debug("Template: header verification failed")
                return None

        # Store title template position in panel-local coords
        self._title_match = (tx - panel_left, ty - panel_top, matched_w, matched_h)

        # Match column headers within the found panel for precise column positioning
        panel_region = gray[panel_top:panel_top + panel_h, panel_left:panel_left + panel_w]
        self._col_header_matches = self._match_column_headers(panel_region)

        sx = offset_x + panel_left
        sy = offset_y + panel_top
        log.info("Template match found panel at (%d,%d) %dx%d (score=%.3f, scale=%.1f)",
                 sx, sy, panel_w, panel_h, best_val, best_scale)
        return (sx, sy, panel_w, panel_h)

    def _find_skills_panel(self, gray: np.ndarray, color: np.ndarray,
                           offset_x: int, offset_y: int
                           ) -> Optional[tuple[int, int, int, int]]:
        """Find the skills panel via template matching (skills_label.PNG).

        Returns screen-absolute (x, y, w, h) or None.
        """
        if self._template is None:
            log.warning("No template loaded — cannot detect skills window")
            return None

        return self._find_by_template(gray, color, offset_x, offset_y)

    def _match_column_headers(self, panel_gray: np.ndarray
                              ) -> Optional[dict[str, tuple[int, int, int, int]]]:
        """Match column header templates within the panel image.

        Returns dict with panel-local (x, y, w, h) for each matched header,
        or None if any header failed to match.
        """
        if not self._col_templates:
            return None

        ph, pw = panel_gray.shape
        # Only search in the header region (top 20% of panel)
        search_h = int(ph * 0.20)
        header_region = panel_gray[:search_h, :]
        rh, rw = header_region.shape

        matches = {}
        for col_name, tpl in self._col_templates.items():
            th, tw = tpl.shape
            if tw >= rw or th >= rh:
                continue

            result = cv2.matchTemplate(header_region, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val < COL_HEADER_THRESHOLD:
                log.debug("Column header '%s' match: %.3f (below %.1f threshold)",
                          col_name, max_val, COL_HEADER_THRESHOLD)
                return None

            matches[col_name] = (max_loc[0], max_loc[1], tw, th)
            log.debug("Column header '%s' matched: %.3f at (%d,%d) %dx%d",
                      col_name, max_val, max_loc[0], max_loc[1], tw, th)

        if len(matches) != 3:
            return None

        log.info("All column headers matched — using template-based column positions")
        return matches

    def _verify_header(self, gray: np.ndarray, color: np.ndarray,
                       x: int, y: int, w: int, h: int) -> bool:
        """Verify a candidate region looks like the skills window.

        Checks:
        1. The top ~8% has a bright text band (the "SKILLS" title)
        2. There's a horizontal band at ~10% with column header text
        3. The main body (15-80%) is mostly dark with scattered bright text
        4. The body contains cyan/teal colored pixels (progress bars)
        """
        img_h, img_w = gray.shape

        # Bounds safety
        if y + h > img_h or x + w > img_w:
            log.debug("  Candidate (%s,%s) %sx%s: out of bounds", x, y, w, h)
            return False

        # Check 1: Title band (top 2-8% of panel)
        title_y1 = int(h * 0.02)
        title_y2 = int(h * 0.08)
        title_band = gray[y + title_y1:y + title_y2, x:x + w]
        if title_band.size == 0:
            log.debug("  Candidate (%s,%s) %sx%s: title band empty", x, y, w, h)
            return False

        title_bright = np.sum(title_band > 180) / title_band.size
        if not (0.01 < title_bright < 0.25):
            log.debug("  Candidate (%s,%s) %sx%s: title bright ratio %.3f (need 0.01-0.25)",
                      x, y, w, h, title_bright)
            return False

        # Check 2: Column header band (~8-12%, right side only past sidebar)
        header_y1 = int(h * 0.08)
        header_y2 = int(h * 0.13)
        sidebar_x = x + int(w * WINDOW_LAYOUT["sidebar_width_ratio"])
        header_band = gray[y + header_y1:y + header_y2, sidebar_x:x + w]
        if header_band.size == 0:
            log.debug("  Candidate (%s,%s) %sx%s: header band empty", x, y, w, h)
            return False

        header_bright = np.sum(header_band > 150) / header_band.size
        if not (0.02 < header_bright < 0.40):
            log.debug("  Candidate (%s,%s) %sx%s: header bright ratio %.3f (need 0.02-0.40)",
                      x, y, w, h, header_bright)
            return False

        # Check 3: Table body should be mostly dark (skills window has very dark bg)
        body_y1 = int(h * 0.15)
        body_y2 = int(h * 0.80)
        body = gray[y + body_y1:y + body_y2, x:x + w]
        if body.size == 0:
            log.debug("  Candidate (%s,%s) %sx%s: body empty", x, y, w, h)
            return False

        body_dark = np.sum(body < 80) / body.size
        if body_dark < 0.60:
            log.debug("  Candidate (%s,%s) %sx%s: body dark ratio %.3f (need >= 0.60)",
                      x, y, w, h, body_dark)
            return False

        # Check 4: Cyan/teal progress bars (skills window has them, chat box does not)
        # Only check the right portion (rank + points columns) where bars live
        bar_x1 = x + int(w * WINDOW_LAYOUT["col_rank_start"])
        body_bgr = color[y + body_y1:y + body_y2, bar_x1:x + w]
        if body_bgr.size > 0:
            hsv = cv2.cvtColor(body_bgr, cv2.COLOR_BGR2HSV)
            # Cyan/teal hue range: 70-95 in OpenCV (140-190 degrees / 2)
            cyan_mask = (
                (hsv[:, :, 0] >= 70) & (hsv[:, :, 0] <= 95) &
                (hsv[:, :, 1] >= 50) &
                (hsv[:, :, 2] >= 80)
            )
            cyan_ratio = float(np.sum(cyan_mask)) / cyan_mask.size
            if cyan_ratio < 0.005:
                log.debug("  Candidate (%s,%s) %sx%s: cyan ratio %.4f (need >= 0.005)",
                          x, y, w, h, cyan_ratio)
                return False
        else:
            log.debug("  Candidate (%s,%s) %sx%s: body color empty", x, y, w, h)
            return False

        log.debug("  Candidate (%s,%s) %sx%s: VERIFIED "
                  "(title=%.3f, header=%.3f, body_dark=%.3f, cyan=%.4f)",
                  x, y, w, h, title_bright, header_bright, body_dark, cyan_ratio)
        return True

    def get_table_top(self, wh: int) -> int:
        """Get table data top Y in panel-local coordinates.

        Uses column header template matches for precision, falls back to ratio.
        """
        if self._col_header_matches:
            # Table starts below the lowest column header with a proportional gap
            max_bottom = max(
                pos[1] + pos[3] for pos in self._col_header_matches.values()
            )
            gap = round(wh * 0.013)  # ~7px gap at 557px panel height
            return max_bottom + gap
        return int(wh * WINDOW_LAYOUT["table_top_ratio"])

    def get_row_height(self, wh: int) -> int:
        """Get the row height in pixels from the panel height ratio."""
        return max(20, round(wh * WINDOW_LAYOUT["row_height_ratio"]))

    def get_table_region(self, window_bounds: tuple[int, int, int, int]
                         ) -> tuple[int, int, int, int]:
        """Get the table data region within the skills window."""
        wx, wy, ww, wh = window_bounds
        col_ranges = self.get_column_ranges(window_bounds)
        table_top = self.get_table_top(wh)
        table_bottom = int(wh * WINDOW_LAYOUT["table_bottom_ratio"])
        x = wx + col_ranges["name"][0]
        y = wy + table_top
        w = col_ranges["points"][1] - col_ranges["name"][0]
        h = table_bottom - table_top
        return (x, y, w, h)

    def get_sidebar_region(self, window_bounds: tuple[int, int, int, int]
                           ) -> tuple[int, int, int, int]:
        """Get the category sidebar region."""
        wx, wy, ww, wh = window_bounds
        layout = WINDOW_LAYOUT
        x = wx
        y = wy + int(wh * layout["header_height_ratio"])
        w = int(ww * layout["sidebar_width_ratio"])
        h = int(wh * (layout["table_bottom_ratio"] - layout["header_height_ratio"]))
        return (x, y, w, h)

    def get_column_ranges(self, window_bounds: tuple[int, int, int, int]
                          ) -> dict[str, tuple[int, int]]:
        """Get pixel ranges for each column within the window.

        Returns dict with keys: 'name', 'rank', 'points'
        Each value is (start_x, end_x) relative to the window left edge.

        Each column starts at its header's X position minus a small padding.
        Each column extends until the next column's start. The skills window
        is fixed-size so template-matched positions are authoritative.
        """
        _, _, ww, _ = window_bounds
        layout = WINDOW_LAYOUT

        if self._col_header_matches:
            name_x = self._col_header_matches["name"][0] - 2
            rank_x = self._col_header_matches["rank"][0] - 2
            points_x = self._col_header_matches["points"][0] - 2

            return {
                "name": (name_x, rank_x),
                "rank": (rank_x, points_x),
                "points": (points_x, ww - 5),
            }

        # Fallback if column headers weren't matched
        return {
            "name": (int(ww * layout["col_name_start"]),
                     int(ww * layout["col_name_end"])),
            "rank": (int(ww * layout["col_rank_start"]),
                     int(ww * layout["col_rank_end"])),
            "points": (int(ww * layout["col_points_start"]),
                       int(ww * layout["col_points_end"])),
        }

    def get_pagination_region(self, window_bounds: tuple[int, int, int, int]
                              ) -> tuple[int, int, int, int]:
        """Get the pagination area region."""
        wx, wy, ww, wh = window_bounds
        layout = WINDOW_LAYOUT
        x = wx + int(ww * layout["col_name_start"])
        y = wy + int(wh * layout["pagination_ratio"])
        w = int(ww * (layout["col_points_end"] - layout["col_name_start"]))
        h = int(wh * (1.0 - layout["pagination_ratio"]))
        return (x, y, w, h)

    def get_total_region(self, window_bounds: tuple[int, int, int, int]
                         ) -> tuple[int, int, int, int]:
        """Get the 'Total: XXXXX' row region (between table bottom and pagination).

        Returns (x, y, w, h) in local coordinates relative to panel origin.
        The total is right-aligned in the points column area.
        """
        _, _, ww, wh = window_bounds
        layout = WINDOW_LAYOUT
        x = int(ww * layout["col_rank_start"])
        y = int(wh * layout["total_row_ratio"])
        w = int(ww * (layout["col_points_end"] - layout["col_rank_start"]))
        h = int(wh * (layout["pagination_ratio"] - layout["total_row_ratio"]))
        return (x, y, w, h)

    def get_template_positions(self, window_bounds: tuple[int, int, int, int]
                              ) -> dict[str, tuple[int, int, int, int]]:
        """Get all template match positions in screen-absolute coordinates.

        Returns dict with keys like 'skills', 'name', 'rank', 'points'.
        Each value is (x, y, w, h) in screen coords.
        """
        wx, wy, _, _ = window_bounds
        positions = {}

        if self._title_match:
            tx, ty, tw, th = self._title_match
            positions["skills"] = (wx + tx, wy + ty, tw, th)

        if self._col_header_matches:
            for col_name, (cx, cy, cw, ch) in self._col_header_matches.items():
                positions[col_name] = (wx + cx, wy + cy, cw, ch)

        return positions

    def is_all_categories_selected(self, game_image: np.ndarray,
                                   panel_ix: int, panel_iy: int,
                                   ww: int, wh: int) -> bool:
        """Check if 'ALL CATEGORIES' is the selected sidebar item.

        Detects the orange/amber selection indicator bar at the left edge
        of the first sidebar item position. The selected category has a
        bright orange vertical bar and brighter text than unselected items.
        """
        layout = WINDOW_LAYOUT
        img_h, img_w = game_image.shape[:2]

        # Region: left edge of sidebar, at the first item ("ALL CATEGORIES")
        bar_x = panel_ix
        bar_y = panel_iy + int(wh * layout["sidebar_first_item_y"])
        bar_w = int(ww * layout["sidebar_indicator_width"]) + 4  # small margin
        bar_h = int(wh * layout["sidebar_item_height"])

        # Bounds check
        if (bar_x < 0 or bar_y < 0
                or bar_x + bar_w > img_w or bar_y + bar_h > img_h):
            return False

        bar_region = game_image[bar_y:bar_y + bar_h, bar_x:bar_x + bar_w]
        if bar_region.size == 0:
            return False

        # Look for orange/amber pixels (the selection indicator)
        # Orange in HSV: hue ~10-25, high saturation, moderate-high value
        hsv = cv2.cvtColor(bar_region, cv2.COLOR_BGR2HSV)
        orange_mask = (
            (hsv[:, :, 0] >= 8) & (hsv[:, :, 0] <= 25) &
            (hsv[:, :, 1] >= 100) &
            (hsv[:, :, 2] >= 120)
        )
        orange_ratio = float(np.sum(orange_mask)) / orange_mask.size

        # The indicator bar is a solid color strip; expect >15% orange pixels
        is_selected = orange_ratio > 0.15
        log.debug("ALL CATEGORIES check: orange_ratio=%.3f → %s",
                  orange_ratio, "selected" if is_selected else "not selected")
        return is_selected

    def get_title_region(self, window_bounds: tuple[int, int, int, int]
                         ) -> tuple[int, int, int, int]:
        """Get the title band region in local coordinates (relative to panel origin).

        Returns (x, y, w, h) where x/y are offsets within the panel.
        """
        _, _, ww, wh = window_bounds
        x = 0
        y = int(wh * 0.02)
        w = ww
        h = int(wh * 0.06)  # 2% to 8% of panel height
        return (x, y, w, h)

    def quick_verify(self, game_image: np.ndarray,
                     panel_ix: int, panel_iy: int,
                     ww: int, wh: int) -> bool:
        """Lightweight check that the skills panel is still at the expected location.

        Uses template matching on the title region — fast and reliable even with
        the semi-transparent UI that makes pixel brightness checks unreliable.

        Args:
            game_image: Full game window capture (BGR).
            panel_ix: Panel x offset in image coordinates.
            panel_iy: Panel y offset in image coordinates.
            ww: Panel width.
            wh: Panel height.

        Returns True if the panel appears present at the stored position.
        """
        if self._template is None:
            return False

        img_h, img_w = game_image.shape[:2]

        # Bounds check
        if (panel_ix < 0 or panel_iy < 0
                or panel_ix + ww > img_w or panel_iy + wh > img_h):
            return False

        # Extract the title region (top 12% of panel) and template match
        title_y2 = panel_iy + int(wh * 0.12)
        title_region = game_image[panel_iy:title_y2, panel_ix:panel_ix + ww]
        if title_region.size == 0:
            return False

        gray_region = cv2.cvtColor(title_region, cv2.COLOR_BGR2GRAY)
        tpl_h, tpl_w = self._template.shape
        rh, rw = gray_region.shape

        if tpl_w >= rw or tpl_h >= rh:
            return False

        result = cv2.matchTemplate(gray_region, self._template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        return max_val >= TEMPLATE_MATCH_THRESHOLD

    def invalidate_cache(self):
        """Clear cached window position."""
        self._cached_bounds = None

    def save_debug_image(self, game_image: np.ndarray, offset_x: int, offset_y: int,
                         panel_bounds: tuple | None) -> None:
        """Save an annotated debug image showing what was detected."""
        if not SAVE_DEBUG_IMAGES:
            return
        try:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            annotated = game_image.copy()

            if panel_bounds:
                px, py, pw, ph = panel_bounds
                # Convert screen coords to image-local coords
                lx = px - offset_x
                ly = py - offset_y

                # Draw panel outline (green)
                cv2.rectangle(annotated, (lx, ly), (lx + pw, ly + ph), (0, 255, 0), 2)

                # Draw the expected column regions
                layout = WINDOW_LAYOUT
                table_top = ly + int(ph * layout["table_top_ratio"])
                table_bot = ly + int(ph * layout["table_bottom_ratio"])

                # Sidebar boundary (red)
                sidebar_x = lx + int(pw * layout["sidebar_width_ratio"])
                cv2.line(annotated, (sidebar_x, ly), (sidebar_x, ly + ph), (0, 0, 255), 1)

                # Column boundaries (blue)
                for col_key in ("col_name_start", "col_name_end", "col_rank_start",
                                "col_rank_end", "col_points_start", "col_points_end"):
                    cx = lx + int(pw * layout[col_key])
                    cv2.line(annotated, (cx, table_top), (cx, table_bot), (255, 100, 0), 1)

                # Table top/bottom (yellow)
                name_start_x = lx + int(pw * layout["col_name_start"])
                points_end_x = lx + int(pw * layout["col_points_end"])
                cv2.line(annotated, (name_start_x, table_top), (points_end_x, table_top), (0, 255, 255), 1)
                cv2.line(annotated, (name_start_x, table_bot), (points_end_x, table_bot), (0, 255, 255), 1)

                # Add text labels
                cv2.putText(annotated, f"Panel: ({px},{py}) {pw}x{ph}",
                            (lx, ly - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            path = os.path.join(DEBUG_DIR, "detection.png")
            cv2.imwrite(path, annotated)
            log.info("Debug image saved: %s", path)
        except Exception as e:
            log.error("Failed to save debug image: %s", e)
