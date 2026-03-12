import os
import subprocess
import sys
import numpy as np
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

try:
    import cv2
except ImportError:
    cv2 = None

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes
    user32 = ctypes.windll.user32
    DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)


@contextmanager
def _thread_per_monitor_dpi():
    """Temporarily opt current thread into PMv2 where supported."""
    if sys.platform != "win32":
        yield
        return
    set_thread_ctx = getattr(user32, "SetThreadDpiAwarenessContext", None)
    if set_thread_ctx is None:
        yield
        return
    previous = None
    try:
        previous = set_thread_ctx(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    except Exception:
        previous = None
    try:
        yield
    finally:
        if previous:
            try:
                set_thread_ctx(previous)
            except Exception:
                pass

from .capturer import ScreenCapturer
from ..core.constants import EVENT_SKILLS_TEMPLATE_DEBUG
from ..core.logger import get_logger
from ..platform import backend as _platform

log = get_logger("Detector")

# Debug image output directory (only used when ocr-trace is active)
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "..", "debug_output")

GAME_WINDOW_TITLE_PREFIX = "Entropia Universe Client"


# ── Template-relative ROI layout (pixel offsets) ─────────────────────
# All coordinates are pixel offsets from the SKILLS template top-left
# corner, measured at the native template size (68×20).  At runtime
# they are scaled by (matched_size / native_size) so the layout
# adapts to any game resolution.
#
# These are the built-in defaults.  User overrides (also in pixels at
# native template size) are stored in config.scan_roi_overrides and
# take precedence.
NATIVE_TEMPLATE_W = 66
NATIVE_TEMPLATE_H = 15

MAX_VISIBLE_ROWS = 12

DEFAULT_ROI_PIXELS = {
    # First row anchor: x,y = top-left of first data row (w,h unused)
    "first_row":            (-174,   71,    0,   0),
    "total":                ( 365,  384,  100,  12),
    "indicator":            (-399,   36,    3,  16),
    # Column offsets: x = offset from first_row.x, w = column width
    "name_column_offset":   (   0,    0,  249,   0),
    "rank_column_offset":   ( 313,    0,  195,   0),
    "points_column_offset": ( 528,    0,   94,   0),
    # Bar offsets: x = offset from first_row.x, w = bar width (per-row)
    "rank_bar":             ( 313,    0,  195,   0),
    "points_bar":           ( 528,    0,   94,   0),
    # Bar vertical offset: y = offset from row top to bar top, h = bar height
    "bar_offset":           (   0,   18,    0,   4),
    # Row stepping: y = pitch (distance between row starts), h = row content height
    "row_offset":           (   0,   25,    0,  22),
}

# ROI names exposed in the config UI (ordered for display).
ROI_NAMES = (
    "first_row",
    "total", "indicator",
    "name_column_offset", "rank_column_offset", "points_column_offset",
    "rank_bar", "points_bar",
    "bar_offset",
    "row_offset",
)

# The skills window background is dark navy/slate blue
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
TEMPLATE_MIN_INSIDE = 170        # Minimum brightness for text pixels (inside mask)
TEMPLATE_MIN_CONTRAST = 30       # Minimum brightness gap: text vs background

# Template position within the skills panel (normalized 0-1).
# Measured by template-matching skills_label.PNG against Skills.PNG reference.
# The "SKILLS" label sits centered in the title bar at the top of the panel.
TEMPLATE_OFFSET_X = 0.46       # Template left edge at 46% of panel width
TEMPLATE_OFFSET_Y = 0.023      # Template top edge at 2.3% of panel height
TEMPLATE_WIDTH_RATIO = 0.075   # Template width is 7.5% of panel width
TEMPLATE_HEIGHT_RATIO = 0.036  # Template height is 3.6% of panel height


def _find_game_window() -> Optional[tuple[int, int, int, int, int]]:
    """Find the Entropia Universe game window.

    Returns (window_id, x, y, width, height) of the game window's client area,
    or None. Uses Win32 EnumWindows on Windows, xdotool on Linux.
    """
    if sys.platform == "win32":
        return _find_game_window_win32()
    return _find_game_window_linux()


def _find_game_window_win32() -> Optional[tuple[int, int, int, int, int]]:
    """Find game window via Win32 EnumWindows."""
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
            log.debug("Found game window: '%s'", title)
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
    with _thread_per_monitor_dpi():
        user32.EnumWindows(enum_callback, 0)

    if not result:
        log.warning("No matching window found")
    return result[0] if result else None


def _find_game_window_linux() -> Optional[tuple[int, int, int, int, int]]:
    """Find game window via xdotool (works with Wine/Proton windows)."""
    try:
        # Search for windows whose name starts with the game title prefix
        search = subprocess.run(
            ["xdotool", "search", "--name", GAME_WINDOW_TITLE_PREFIX],
            capture_output=True, text=True, timeout=5,
        )
        if search.returncode != 0 or not search.stdout.strip():
            log.warning("No matching window found via xdotool")
            return None

        # Take the first matching window ID
        wid = int(search.stdout.strip().splitlines()[0])

        # Get window geometry
        geo = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", str(wid)],
            capture_output=True, text=True, timeout=5,
        )
        if geo.returncode != 0:
            log.warning("xdotool getwindowgeometry failed for window %s", wid)
            return None

        # Parse shell output: WINDOW=...\nX=...\nY=...\nWIDTH=...\nHEIGHT=...
        vals = {}
        for line in geo.stdout.strip().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                vals[k] = int(v)

        x = vals.get("X", 0)
        y = vals.get("Y", 0)
        w = vals.get("WIDTH", 0)
        h = vals.get("HEIGHT", 0)

        if w <= 0 or h <= 0:
            log.warning("Invalid window geometry: %sx%s", w, h)
            return None

        log.info("Found game window via xdotool: wid=%s at (%s,%s) %sx%s", wid, x, y, w, h)
        return (wid, x, y, w, h)

    except FileNotFoundError:
        log.warning("xdotool not found — install with: sudo apt install xdotool")
        return None
    except Exception as e:
        log.warning("xdotool window search failed: %s", e)
        return None


class SkillsWindowDetector:
    """Detects and locates the skills window on screen.

    Step 1: Find the game window via Win32 API (window title lookup).
    Step 2: Within the game window region, find the skills panel using
            vision-based detection (dark rectangles, header verification).
    """

    def __init__(self, capturer: ScreenCapturer, event_bus=None, config=None,
                 frame_provider=None):
        if cv2 is None:
            raise ImportError("opencv-python is required")
        self._capturer = capturer
        self._event_bus = event_bus
        self._config = config
        # Optional FrameDistributor for pulling latest frames in monitoring mode.
        # Detection phase still uses self._capturer for on-demand capture.
        self._frame_provider = frame_provider
        self._cached_bounds: Optional[tuple[int, int, int, int]] = None
        self._game_hwnd: Optional[int] = None
        self._game_origin: tuple[int, int] = (0, 0)
        self._game_geometry: tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, w, h
        self._last_game_image: Optional[np.ndarray] = None

        # Load skills label template for template matching (with alpha mask)
        self._template: Optional[np.ndarray] = None
        self._template_mask_bool: Optional[np.ndarray] = None
        self._template_inv_bool: Optional[np.ndarray] = None
        if TEMPLATE_PATH.exists():
            raw = cv2.imread(str(TEMPLATE_PATH), cv2.IMREAD_UNCHANGED)
            if raw is not None and len(raw.shape) == 3 and raw.shape[2] >= 4:
                mask = raw[:, :, 3]
                self._template = mask.copy()
                self._template_mask_bool = mask > 0
                self._template_inv_bool = ~self._template_mask_bool
                opaque = int(self._template_mask_bool.sum())
                total = mask.shape[0] * mask.shape[1]
                log.info("Loaded template: %s (%dx%d, %d/%d opaque)",
                         TEMPLATE_PATH.name, mask.shape[1], mask.shape[0],
                         opaque, total)
            elif raw is not None:
                # Fallback: no alpha channel — use as grayscale directly
                self._template = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY) if len(raw.shape) == 3 else raw
                log.warning("Template has no alpha channel, using grayscale: %s", TEMPLATE_PATH)
            else:
                log.warning("Failed to read template: %s", TEMPLATE_PATH)
        else:
            log.warning("Template not found: %s", TEMPLATE_PATH)

        # ROI pixel overrides from config (takes precedence over DEFAULT_ROI_PIXELS)
        self._roi_overrides_px: dict[str, tuple[int, int, int, int]] = {}

        # Cached template match position (panel-local pixel coords)
        # (x, y, w, h) relative to panel top-left
        self._title_match: Optional[tuple[int, int, int, int]] = None

        # DPI scale: ratio of actual panel size to expected 100% DPI size.
        # Derived from cached_bounds vs template-predicted panel dims.
        self._dpi_scale: float = 1.0
        self._tracer = None  # OcrTracer, set via set_tracer()

    def set_tracer(self, tracer) -> None:
        """Set the OcrTracer for detailed trace output."""
        self._tracer = tracer

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

    def is_game_foreground(self) -> bool:
        """Check if the game window is the current foreground window.

        Uses the platform backend for a fast foreground title check (<0.1ms).
        On platforms without focus detection, assumes the game is in foreground.
        """
        if not _platform.supports_focus_detection():
            return True
        try:
            title = _platform.get_foreground_window_title()
            return title.startswith(GAME_WINDOW_TITLE_PREFIX)
        except Exception:
            return False

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
        self._game_geometry = (gx, gy, gw, gh)
        log.debug("Game window: (%s,%s) %sx%s hwnd=%s", gx, gy, gw, gh, hwnd)

        # Step 2: Capture the game window (window backend on Windows, mss on Linux)
        game_image = self._capturer.capture_window(hwnd, geometry=(gx, gy, gw, gh))
        if game_image is None:
            log.warning("Window capture failed, falling back to mss region")
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

        bounds = self._find_skills_panel(gray, gx, gy)

        # Save annotated debug image on every detection attempt
        if bounds:
            self.save_debug_image(game_image, gx, gy, bounds)
            self._cached_bounds = bounds
            if self._tracer and self._tracer.enabled:
                self._tracer.log("DETECT", f"panel_found={bounds}")
                self._trace_detect_image(game_image, gx, gy, bounds)
            return bounds

        # Save debug image on failure too for diagnostics
        self.save_debug_image(game_image, gx, gy, None)
        if self._tracer and self._tracer.enabled:
            self._tracer.log("DETECT", "no_panel")
        return self._cached_bounds

    def capture_game(self) -> np.ndarray | None:
        """Capture the current game window image.

        When a frame provider (FrameDistributor) is available, returns the
        latest frame it captured — avoiding a redundant window capture.
        Falls back to direct capture via self._capturer if the provider
        has no fresh frame or is not set.

        Returns the full game window as BGR numpy array, or None.
        Also stores the result in last_game_image.
        """
        if not self._game_hwnd:
            return None

        # Try the frame provider first (shares frames with other detectors)
        if self._frame_provider is not None:
            image = self._frame_provider.get_latest_frame()
            if image is not None:
                self._last_game_image = image
                return image

        image = self._capturer.capture_window(
            self._game_hwnd, geometry=self._game_geometry,
        )
        if image is not None:
            self._last_game_image = image
        return image

    def _validate_template_match(self, gray: np.ndarray,
                                 tx: int, ty: int) -> bool:
        """Verify a candidate match has bright text inside the mask and darker background."""
        if self._template_mask_bool is None:
            return True  # No mask available — skip validation

        tpl_h, tpl_w = self._template.shape
        img_h, img_w = gray.shape
        if tx < 0 or ty < 0 or tx + tpl_w > img_w or ty + tpl_h > img_h:
            return False

        region = gray[ty:ty + tpl_h, tx:tx + tpl_w]
        if region.shape != self._template.shape:
            log.debug("Template validation: region shape %s != template %s",
                      region.shape, self._template.shape)
            return False

        inside = float(np.mean(region[self._template_mask_bool]))
        outside = float(np.mean(region[self._template_inv_bool]))
        log.debug("Template validation: inside=%.0f outside=%.0f contrast=%.0f "
                  "(min_inside=%d min_contrast=%d)",
                  inside, outside, inside - outside,
                  TEMPLATE_MIN_INSIDE, TEMPLATE_MIN_CONTRAST)

        if inside < TEMPLATE_MIN_INSIDE:
            return False
        if inside - outside < TEMPLATE_MIN_CONTRAST:
            return False
        return True

    def _find_by_template(self, gray: np.ndarray,
                          offset_x: int, offset_y: int
                          ) -> Optional[tuple[int, int, int, int]]:
        """Find the skills panel by template matching the 'SKILLS' title label.

        Single-scale match — the skills window is fixed-size at any given
        game resolution, so the template always matches at 1.0.
        Returns screen-absolute (x, y, w, h) or None.
        """
        if self._template is None:
            return None

        img_h, img_w = gray.shape
        tpl_h, tpl_w = self._template.shape

        if tpl_w >= img_w or tpl_h >= img_h:
            return None

        result = cv2.matchTemplate(gray, self._template, cv2.TM_CCOEFF_NORMED)
        _, best_val, _, best_loc = cv2.minMaxLoc(result)

        log.debug("Template match: score=%.3f at (%d,%d) (threshold=%.1f)",
                  best_val, best_loc[0], best_loc[1], TEMPLATE_MATCH_THRESHOLD)

        # Helper to publish debug event for non-match / failure cases
        def _publish_no_match():
            if self._event_bus is not None:
                self._event_bus.publish(EVENT_SKILLS_TEMPLATE_DEBUG, {
                    "x": offset_x + best_loc[0],
                    "y": offset_y + best_loc[1],
                    "w": tpl_w, "h": tpl_h,
                    "confidence": best_val, "matched": False,
                })

        if best_val < TEMPLATE_MATCH_THRESHOLD:
            _publish_no_match()
            return None

        # Template matched at (tx, ty) — this is the title label position.
        # Since the skills window is fixed size, compute the full panel bounds
        # directly from the template position using known layout ratios.
        # This avoids fragile dark-edge scanning (the UI is semi-transparent).
        tx, ty = best_loc
        matched_w = tpl_w
        matched_h = tpl_h

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
            _publish_no_match()
            return None
        if panel_h < MIN_PANEL_HEIGHT or panel_h > MAX_PANEL_HEIGHT:
            log.debug("Template: panel height %d out of range", panel_h)
            _publish_no_match()
            return None

        if not self._validate_template_match(gray, tx, ty):
            log.debug("Template: mask validation failed")
            _publish_no_match()
            return None

        # Store title template position in panel-local coords
        self._title_match = (tx - panel_left, ty - panel_top, matched_w, matched_h)

        sx = offset_x + panel_left
        sy = offset_y + panel_top

        # Publish debug event with all resolved ROIs for overlay visualization
        if self._event_bus is not None:
            self._publish_debug_data(
                sx, sy, panel_w, panel_h, best_val,
                offset_x + best_loc[0], offset_y + best_loc[1],
                tpl_w, tpl_h,
            )

        log.info("Template match found panel at (%d,%d) %dx%d (score=%.3f)",
                 sx, sy, panel_w, panel_h, best_val)
        return (sx, sy, panel_w, panel_h)

    def _find_skills_panel(self, gray: np.ndarray,
                           offset_x: int, offset_y: int
                           ) -> Optional[tuple[int, int, int, int]]:
        """Find the skills panel via template matching (skills_label.PNG).

        Returns screen-absolute (x, y, w, h) or None.
        """
        if self._template is None:
            log.warning("No template loaded — cannot detect skills window")
            return None

        return self._find_by_template(gray, offset_x, offset_y)

    def get_table_top(self, wh: int) -> int:
        """Get table data top Y in panel-local coordinates."""
        first_row = self.resolve_roi("first_row")
        if first_row:
            return first_row[1]
        log.warning("get_table_top: no ROI resolved, template not matched yet")
        return 0

    def get_row_height(self, wh: int) -> int:
        """Get the row height in pixels."""
        rh = self.resolve_row_height()
        if rh is not None:
            return rh
        log.warning("get_row_height: no ROI resolved, template not matched yet")
        return 25  # native default

    def get_table_region(self, window_bounds: tuple[int, int, int, int]
                         ) -> tuple[int, int, int, int]:
        """Get the table data region within the skills window.

        Origin from first_row ROI (x,y); width/height derived from
        columns and row pitch.
        """
        wx, wy, _, _ = window_bounds
        first_row = self.resolve_roi("first_row")
        tw = self.resolve_table_width()
        th = self.resolve_table_height()
        if first_row and tw and th:
            return (wx + first_row[0], wy + first_row[1], tw, th)
        log.warning("get_table_region: no ROI resolved")
        return (wx, wy, 0, 0)

    def get_column_ranges(self, window_bounds: tuple[int, int, int, int]
                          ) -> dict[str, tuple[int, int]]:
        """Get pixel ranges for each column within the window.

        Returns dict with keys: 'name', 'rank', 'points'
        Each value is (start_x, end_x) relative to the panel left edge.
        Column offsets are relative to first_row.x.
        """
        resolved = self.resolve_columns()
        if resolved:
            return resolved
        log.warning("get_column_ranges: no ROI resolved, template not matched yet")
        return {"name": (0, 0), "rank": (0, 0), "points": (0, 0)}


    def resolve_roi(self, name: str) -> Optional[tuple[int, int, int, int]]:
        """Resolve a pixel-based ROI to panel-local pixel coordinates.

        Uses config overrides (_roi_overrides_px) if present, otherwise
        DEFAULT_ROI_PIXELS.  The stored pixel offsets are at native template
        size and get scaled to the matched template size at runtime.

        Returns (x, y, w, h) relative to the panel top-left, or None if
        the SKILLS template hasn't been matched yet.
        """
        if self._title_match is None:
            return None
        if name in self._roi_overrides_px:
            px, py, pw, ph = self._roi_overrides_px[name]
        elif name in DEFAULT_ROI_PIXELS:
            px, py, pw, ph = DEFAULT_ROI_PIXELS[name]
        else:
            return None
        tlx, tly, mtw, mth = self._title_match
        sx = mtw / NATIVE_TEMPLATE_W
        sy = mth / NATIVE_TEMPLATE_H
        return (
            round(tlx + px * sx),
            round(tly + py * sy),
            round(pw * sx),
            round(ph * sy),
        )

    def set_roi_overrides(self, overrides: dict[str, tuple[int, int, int, int]]) -> None:
        """Set pixel-based ROI overrides (at native template size)."""
        self._roi_overrides_px = dict(overrides)

    def republish_roi_debug(self) -> None:
        """Re-publish EVENT_SKILLS_TEMPLATE_DEBUG with current ROI overrides.

        Called when ROI config changes so the overlay updates in real-time
        without waiting for a new template match cycle.
        """
        if self._event_bus is None or self._cached_bounds is None or self._title_match is None:
            return
        sx, sy, panel_w, panel_h = self._cached_bounds
        self._publish_debug_data(
            sx, sy, panel_w, panel_h, 1.0,
            sx + self._title_match[0], sy + self._title_match[1],
            self._title_match[2], self._title_match[3],
        )

    def _publish_debug_data(self, sx: int, sy: int, panel_w: int, panel_h: int,
                            confidence: float, tpl_x: int, tpl_y: int,
                            tpl_w: int, tpl_h: int) -> None:
        """Build and publish EVENT_SKILLS_TEMPLATE_DEBUG with current ROI state."""
        debug_data = {
            "x": tpl_x, "y": tpl_y,
            "w": tpl_w, "h": tpl_h,
            "confidence": confidence, "matched": True,
            "panel": (sx, sy, panel_w, panel_h),
            "game_origin": self._game_origin,
            "rois": {},
        }
        # Position ROIs: resolve adds template-local offset → screen-absolute
        position_rois = {"first_row", "total", "indicator"}
        for roi_name in ROI_NAMES:
            if roi_name in position_rois:
                roi = self.resolve_roi(roi_name)
                if roi is not None:
                    debug_data["rois"][roi_name] = (
                        sx + roi[0], sy + roi[1], roi[2], roi[3],
                    )
            else:
                # Relative ROIs: scale only, no template-local offset
                px, py, pw, ph = self.get_roi_pixels(roi_name)
                scale_x = self._title_match[2] / NATIVE_TEMPLATE_W
                scale_y = self._title_match[3] / NATIVE_TEMPLATE_H
                debug_data["rois"][roi_name] = (
                    round(px * scale_x), round(py * scale_y),
                    round(pw * scale_x), round(ph * scale_y),
                )
        # Column ranges (screen-absolute x coords)
        col_ranges = self.get_column_ranges((sx, sy, panel_w, panel_h))
        if col_ranges:
            debug_data["col_ranges"] = {
                name: (sx + start, sx + end)
                for name, (start, end) in col_ranges.items()
            }
        # Bar ranges (screen-absolute x coords)
        bar_ranges = self.resolve_bars()
        if bar_ranges:
            debug_data["bar_ranges"] = {
                name: (sx + start, sx + end)
                for name, (start, end) in bar_ranges.items()
            }
        tw = self.resolve_table_width()
        if tw:
            debug_data["table_width"] = tw
        row_h = self.resolve_row_height()
        if row_h:
            debug_data["row_height"] = row_h
        row_p = self.resolve_row_pitch()
        if row_p:
            debug_data["row_pitch"] = row_p
        self._event_bus.publish(EVENT_SKILLS_TEMPLATE_DEBUG, debug_data)

    def get_roi_pixels(self, name: str) -> tuple[int, int, int, int]:
        """Get current ROI pixel values (override if set, else default)."""
        if name in self._roi_overrides_px:
            return self._roi_overrides_px[name]
        return DEFAULT_ROI_PIXELS.get(name, (0, 0, 0, 0))

    def resolve_columns(self) -> Optional[dict[str, tuple[int, int]]]:
        """Resolve column ROIs to panel-local x-coord ranges.

        Column offsets are relative to first_row.x.  The raw pixel values
        are scaled by template ratio and added to the resolved first_row x.

        Returns dict with (start_x, end_x) per column, or None.
        """
        first_row = self.resolve_roi("first_row")
        if first_row is None or self._title_match is None:
            return None
        base_x = first_row[0]
        sx = self._title_match[2] / NATIVE_TEMPLATE_W
        cols = {}
        for roi_name, col_key in (
            ("name_column_offset", "name"),
            ("rank_column_offset", "rank"),
            ("points_column_offset", "points"),
        ):
            px, _, pw, _ = self.get_roi_pixels(roi_name)
            start = base_x + round(px * sx)
            end = start + round(pw * sx)
            cols[col_key] = (start, end)
        return cols

    def resolve_bars(self) -> Optional[dict[str, tuple[int, int]]]:
        """Resolve bar ROIs to panel-local x-coord ranges.

        Bar offsets are relative to first_row.x (like column offsets).
        Returns dict with (start_x, end_x) per bar, or None.
        """
        first_row = self.resolve_roi("first_row")
        if first_row is None or self._title_match is None:
            return None
        base_x = first_row[0]
        sx = self._title_match[2] / NATIVE_TEMPLATE_W
        bars = {}
        for roi_name, bar_key in (
            ("rank_bar", "rank"),
            ("points_bar", "points"),
        ):
            px, _, pw, _ = self.get_roi_pixels(roi_name)
            start = base_x + round(px * sx)
            bars[bar_key] = (start, start + round(pw * sx))
        return bars

    def get_bar_ranges(self) -> dict[str, tuple[int, int]]:
        """Get pixel ranges for each bar.

        Returns dict with keys: 'rank', 'points'
        Each value is (start_x, end_x) relative to the panel left edge.
        """
        resolved = self.resolve_bars()
        if resolved:
            return resolved
        log.warning("get_bar_ranges: no ROI resolved, template not matched yet")
        return {"rank": (0, 0), "points": (0, 0)}

    def resolve_row_height(self) -> Optional[int]:
        """Resolve row content height (h component of row_offset ROI)."""
        if self._title_match is None:
            return None
        sy = self._title_match[3] / NATIVE_TEMPLATE_H
        _, _, _, ph = self.get_roi_pixels("row_offset")
        return max(20, round(ph * sy))

    def resolve_row_pitch(self) -> Optional[int]:
        """Resolve row pitch (y component of row_offset ROI).

        The pitch is the distance between consecutive row starts.
        """
        if self._title_match is None:
            return None
        sy = self._title_match[3] / NATIVE_TEMPLATE_H
        _, py, _, _ = self.get_roi_pixels("row_offset")
        return max(20, round(py * sy))

    def resolve_bar_offset(self) -> Optional[tuple[int, int]]:
        """Resolve bar vertical offset and height from bar_offset ROI.

        Returns:
            (bar_top, bar_height) in row-local pixels.
        """
        if self._title_match is None:
            return None
        sy = self._title_match[3] / NATIVE_TEMPLATE_H
        _, py, _, ph = self.get_roi_pixels("bar_offset")
        return max(0, round(py * sy)), max(1, round(ph * sy))

    def resolve_table_width(self) -> Optional[int]:
        """Derive table width from the rightmost column edge.

        Width = points_column_offset.x + points_column_offset.w (scaled),
        i.e. the right edge of the points column relative to first_row.x.
        """
        if self._title_match is None:
            return None
        sx = self._title_match[2] / NATIVE_TEMPLATE_W
        px, _, pw, _ = self.get_roi_pixels("points_column_offset")
        return round((px + pw) * sx)

    def resolve_table_height(self) -> Optional[int]:
        """Derive table height from row pitch * max visible rows."""
        pitch = self.resolve_row_pitch()
        if pitch is None:
            return None
        return pitch * MAX_VISIBLE_ROWS

    def is_all_categories_selected(self, game_image: np.ndarray,
                                   panel_ix: int, panel_iy: int,
                                   ww: int, wh: int) -> bool:
        """Check if 'ALL CATEGORIES' is the selected sidebar item.

        Detects the orange/amber selection indicator bar at the left edge
        of the first sidebar item position. The selected category has a
        bright orange vertical bar and brighter text than unselected items.
        """
        indicator_roi = self.resolve_roi("indicator")
        if not indicator_roi:
            log.debug("is_all_categories_selected: no indicator ROI resolved")
            return False

        img_h, img_w = game_image.shape[:2]
        bar_x = panel_ix + indicator_roi[0]
        bar_y = panel_iy + indicator_roi[1]
        bar_w = indicator_roi[2] + 4  # small margin
        bar_h = indicator_roi[3]

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
            log.debug("quick_verify: no template loaded")
            return False

        img_h, img_w = game_image.shape[:2]

        # Bounds check
        if (panel_ix < 0 or panel_iy < 0
                or panel_ix + ww > img_w or panel_iy + wh > img_h):
            log.debug("quick_verify: bounds check failed — panel=(%d,%d)+(%d,%d) image=%dx%d",
                       panel_ix, panel_iy, ww, wh, img_w, img_h)
            return False

        # Extract the title region (top 12% of panel) and template match
        title_y2 = panel_iy + int(wh * 0.12)
        title_region = game_image[panel_iy:title_y2, panel_ix:panel_ix + ww]
        if title_region.size == 0:
            log.debug("quick_verify: title region is empty")
            return False

        gray_region = cv2.cvtColor(title_region, cv2.COLOR_BGR2GRAY)
        tpl_h, tpl_w = self._template.shape
        rh, rw = gray_region.shape

        if tpl_w >= rw or tpl_h >= rh:
            log.debug("quick_verify: template %dx%d too large for region %dx%d",
                       tpl_w, tpl_h, rw, rh)
            return False

        result = cv2.matchTemplate(gray_region, self._template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        passed = max_val >= TEMPLATE_MATCH_THRESHOLD
        log.debug("quick_verify: score=%.3f threshold=%.1f → %s",
                   max_val, TEMPLATE_MATCH_THRESHOLD, "PASS" if passed else "FAIL")
        return passed

    # Search margin (pixels) around last known template position for quick_adjust.
    # Must be large enough to catch typical window drags between frames (~100ms)
    # but small enough to keep the search region tiny for speed.
    ADJUST_MARGIN = 8

    def quick_adjust(self, game_image: np.ndarray,
                     ) -> Optional[tuple[int, int, int, int]]:
        """Detect small skill window movements and re-adjust the template region.

        Searches a small area (±ADJUST_MARGIN px) around the last known template
        position.  Even a 1px offset can cause wrong ROI reads, so this method
        runs every frame and returns pixel-precise updated bounds.

        Falls back to full-image quick_relocate if the template is not found
        in the search area (panel moved far or was closed).

        Returns screen-absolute (x, y, w, h) or None.
        """
        if (self._template is None or self._game_origin is None
                or self._cached_bounds is None or self._title_match is None):
            return self.quick_relocate(game_image)

        gray = cv2.cvtColor(game_image, cv2.COLOR_BGR2GRAY)
        img_h, img_w = gray.shape
        tpl_h, tpl_w = self._template.shape
        gox, goy = self._game_origin

        # Last known template position in image coordinates
        old_sx, old_sy, old_pw, old_ph = self._cached_bounds
        old_tlx, old_tly, _, _ = self._title_match
        last_tx = (old_sx - gox) + old_tlx
        last_ty = (old_sy - goy) + old_tly

        # Build a small search region around the last known position
        margin = getattr(self._config, "ocr_adjust_margin", self.ADJUST_MARGIN) if self._config else self.ADJUST_MARGIN
        search_x1 = max(0, last_tx - margin)
        search_y1 = max(0, last_ty - margin)
        search_x2 = min(img_w, last_tx + tpl_w + margin)
        search_y2 = min(img_h, last_ty + tpl_h + margin)

        # Region must be large enough for the template
        if (search_x2 - search_x1 < tpl_w or search_y2 - search_y1 < tpl_h):
            return self.quick_relocate(game_image)

        search_region = gray[search_y1:search_y2, search_x1:search_x2]
        result = cv2.matchTemplate(search_region, self._template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val < TEMPLATE_MATCH_THRESHOLD:
            # Not found in small area — fall back to full-image search
            log.debug("quick_adjust: not in local area (score=%.3f), falling back", max_val)
            return self.quick_relocate(game_image)

        # Convert local match position back to full-image coordinates
        tx = search_x1 + max_loc[0]
        ty = search_y1 + max_loc[1]

        # Compute movement delta from last known position
        dx = tx - last_tx
        dy = ty - last_ty

        if dx == 0 and dy == 0:
            # No movement — return cached bounds as-is (avoid recomputation)
            log.debug("quick_adjust: no movement (score=%.3f)", max_val)
            return self._cached_bounds

        # Panel moved — derive new bounds from the precise template position.
        # Panel dimensions don't change (fixed-size window), only the origin shifts.
        panel_w = old_pw
        panel_h = old_ph
        panel_left = tx - int(panel_w * TEMPLATE_OFFSET_X)
        panel_top = ty - int(panel_h * TEMPLATE_OFFSET_Y)

        # Clamp to image bounds
        panel_left = max(0, panel_left)
        panel_top = max(0, panel_top)
        if panel_left + panel_w > img_w:
            panel_w = img_w - panel_left
        if panel_top + panel_h > img_h:
            panel_h = img_h - panel_top

        # Update stored state
        self._title_match = (tx - panel_left, ty - panel_top, tpl_w, tpl_h)
        sx = gox + panel_left
        sy = goy + panel_top
        self._cached_bounds = (sx, sy, panel_w, panel_h)

        # Publish debug overlay so it tracks the moved window
        if self._event_bus is not None:
            self._publish_debug_data(
                sx, sy, panel_w, panel_h, max_val,
                gox + tx, goy + ty, tpl_w, tpl_h,
            )

        log.info("quick_adjust: panel shifted by (%+d,%+d) → (%d,%d) %dx%d (score=%.3f)",
                 dx, dy, sx, sy, panel_w, panel_h, max_val)
        if self._tracer and self._tracer.enabled:
            self._tracer.log("ADJUST", f"({old_sx},{old_sy})->({sx},{sy}) score={max_val:.2f}")
        return (sx, sy, panel_w, panel_h)

    def quick_relocate(self, game_image: np.ndarray,
                       ) -> Optional[tuple[int, int, int, int]]:
        """Full-image re-detection when the skills panel moved far or was lost.

        Template-matches across the full game capture (no game window lookup,
        no column header matching).
        Returns screen-absolute (x, y, w, h) or None.
        """
        if self._template is None or self._game_origin is None:
            return None

        gray = cv2.cvtColor(game_image, cv2.COLOR_BGR2GRAY)
        img_h, img_w = gray.shape
        tpl_h, tpl_w = self._template.shape

        if tpl_w >= img_w or tpl_h >= img_h:
            return None

        result = cv2.matchTemplate(gray, self._template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        log.debug("quick_relocate: score=%.3f at (%d,%d) threshold=%.1f",
                   max_val, max_loc[0], max_loc[1], TEMPLATE_MATCH_THRESHOLD)

        if max_val < TEMPLATE_MATCH_THRESHOLD:
            return None

        # Derive panel bounds from template match position
        tx, ty = max_loc
        if not self._validate_template_match(gray, tx, ty):
            return None
        panel_w = int(tpl_w / TEMPLATE_WIDTH_RATIO)
        panel_h = int(tpl_h / TEMPLATE_HEIGHT_RATIO)
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
            log.debug("quick_relocate: panel width %d out of range", panel_w)
            return None
        if panel_h < MIN_PANEL_HEIGHT or panel_h > MAX_PANEL_HEIGHT:
            log.debug("quick_relocate: panel height %d out of range", panel_h)
            return None

        # Store title template position for future use
        self._title_match = (tx - panel_left, ty - panel_top, tpl_w, tpl_h)

        # Convert to screen coordinates
        gox, goy = self._game_origin
        sx = gox + panel_left
        sy = goy + panel_top
        self._cached_bounds = (sx, sy, panel_w, panel_h)

        # Publish debug overlay so it tracks the moved window
        if self._event_bus is not None:
            self._publish_debug_data(
                sx, sy, panel_w, panel_h, max_val,
                gox + tx, goy + ty, tpl_w, tpl_h,
            )

        log.info("quick_relocate: panel found at (%d,%d) %dx%d (score=%.3f)",
                  sx, sy, panel_w, panel_h, max_val)
        return (sx, sy, panel_w, panel_h)

    def invalidate_cache(self):
        """Clear cached window position."""
        self._cached_bounds = None

    def save_debug_image(self, game_image: np.ndarray, offset_x: int, offset_y: int,
                         panel_bounds: tuple | None) -> None:
        """Save an annotated debug image using actual detected positions.

        Draws the same regions the overlay uses: template match and resolved ROIs.
        """
        if not (self._tracer and self._tracer.enabled):
            return
        try:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            annotated = game_image.copy()

            if panel_bounds:
                px, py, pw, ph = panel_bounds
                lx = px - offset_x
                ly = py - offset_y

                # Panel outline (green)
                cv2.rectangle(annotated, (lx, ly), (lx + pw, ly + ph), (0, 255, 0), 2)
                cv2.putText(annotated, f"Panel: ({px},{py}) {pw}x{ph}",
                            (lx, ly - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                # SKILLS template match (white)
                if self._title_match:
                    tx, ty, tw, th = self._title_match
                    cv2.rectangle(annotated, (lx + tx, ly + ty),
                                  (lx + tx + tw, ly + ty + th), (255, 255, 255), 1)
                    cv2.putText(annotated, "SKILLS", (lx + tx, ly + ty - 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

                # Resolved ROIs
                roi_colors = {
                    "first_row": (0, 255, 255),   # yellow
                    "total":     (0, 200, 255),    # gold
                    "indicator": (0, 140, 255),    # dark orange
                }
                for name, color in roi_colors.items():
                    roi = self.resolve_roi(name)
                    if roi:
                        rx, ry, rw, rh = roi
                        cv2.rectangle(annotated, (lx + rx, ly + ry),
                                      (lx + rx + rw, ly + ry + rh), color, 1)
                        cv2.putText(annotated, name, (lx + rx, ly + ry - 4),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

                # Column ranges from get_column_ranges (blue lines)
                col_ranges = self.get_column_ranges(panel_bounds)
                first_row = self.resolve_roi("first_row")
                table_h = self.resolve_table_height()
                if first_row and table_h:
                    t_top = ly + first_row[1]
                    t_bot = t_top + table_h
                else:
                    t_top = ly
                    t_bot = ly + ph
                for _, (cs, ce) in col_ranges.items():
                    cv2.line(annotated, (lx + cs, t_top), (lx + cs, t_bot), (255, 100, 0), 1)
                    cv2.line(annotated, (lx + ce, t_top), (lx + ce, t_bot), (255, 100, 0), 1)

            path = os.path.join(DEBUG_DIR, "detection.png")
            cv2.imwrite(path, annotated)
            log.info("Debug image saved: %s", path)
        except Exception as e:
            log.error("Failed to save debug image: %s", e)

    def _trace_detect_image(self, game_image: np.ndarray,
                            gx: int, gy: int,
                            bounds: tuple[int, int, int, int]) -> None:
        """Save annotated detection image for trace."""
        if not self._tracer:
            return
        annotated = game_image.copy()
        px, py, pw, ph = bounds
        lx, ly = px - gx, py - gy
        cv2.rectangle(annotated, (lx, ly), (lx + pw, ly + ph), (0, 255, 0), 2)
        self._tracer.save_image("detect", annotated)
