import os
import re
import threading
import time
from datetime import datetime
from typing import Optional

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.config import AppConfig
from ..core.event_bus import EventBus
from ..core.database import Database
from ..core.logger import get_logger
from ..core.constants import (
    EVENT_OCR_PROGRESS, EVENT_OCR_COMPLETE,
    EVENT_DEBUG_REGIONS, EVENT_DEBUG_ROW,
    EVENT_OCR_PAGE_CHANGED,
)
from .models import SkillReading, SkillScanResult, ScanProgress
from .capturer import ScreenCapturer
from .preprocessor import ImagePreprocessor
from .recognizer import OCRRecognizer
from .skill_parser import SkillMatcher, RankVerifier
from .progress_bar import ProgressBarReader
from .detector import SkillsWindowDetector, WINDOW_LAYOUT
from .font_matcher import FontMatcher
from .navigator import SkillsNavigator

log = get_logger("OCR")

# How often to check for the skills window (seconds)
DETECT_POLL_INTERVAL = 2.0
# How long to wait before giving up on initial detection (seconds)
DETECT_TIMEOUT = 120.0
# How often to poll for page changes during continuous monitoring (seconds).
# Fast polling is cheap because we only check the first row's template match,
# not a full pixel diff or OCR scan.
MONITOR_INTERVAL = 0.1

# Window stability: require this many consecutive matching positions
# before starting a scan (each tick is STABILITY_POLL_INTERVAL seconds).
STABILITY_TICKS = 3
STABILITY_POLL_INTERVAL = 0.1

# Minimum number of bright pixels (>80 grayscale) to consider a row non-empty.
# Using an absolute count instead of a fraction of cell area avoids rejecting
# short names like "Aim" that occupy very few pixels in a wide column.
# ~50 bright pixels ≈ a 3-character word at game font size.
MIN_BRIGHT_PIXELS = 50

# If this fraction (or more) of rows in a page scan fail to match a skill
# name, assume the window moved mid-capture and discard the page.
MAX_MISS_FRACTION = 0.5


class ScanOrchestrator:
    """Coordinates the OCR skills scan pipeline.

    Operates in continuous monitoring mode:
    1. Wait for the skills window to appear
    2. Capture the game window directly (via PrintWindow, ignoring overlays)
    3. Crop the table region and OCR visible rows
    4. Detect page changes and re-scan automatically
    5. User navigates categories/pages manually
    """

    def __init__(self, config: AppConfig, event_bus: EventBus, db: Database):
        self._config = config
        self._event_bus = event_bus
        self._db = db
        self._stop_event = threading.Event()

        self._capturer = ScreenCapturer()
        self._preprocessor = ImagePreprocessor()
        self._recognizer = OCRRecognizer(config.tesseract_path)
        self._skill_matcher = SkillMatcher()
        self._rank_verifier = RankVerifier()
        self._bar_reader = ProgressBarReader()
        self._detector = SkillsWindowDetector(self._capturer)
        self._navigator = SkillsNavigator()

        self._all_skills = self._skill_matcher.get_all_skills()
        self._found_skill_names: set[str] = set()

        # Font-based template matcher (replaces Tesseract for per-row OCR)
        skill_names = [s["name"] for s in self._all_skills]
        rank_names = self._rank_verifier._rank_names
        self._font_matcher = FontMatcher(skill_names, rank_names)
        self._pending_captures: list[dict] = []

    def stop(self):
        """Signal the continuous monitor to stop."""
        self._stop_event.set()

    def _wait_for_stable_window(self, bounds: tuple[int, int, int, int]
                                ) -> bool:
        """Wait for the window to hold still for STABILITY_TICKS consecutive
        fast polls.  Returns True if stable, False if stopped or moved away."""
        stable_count = 0
        while not self._stop_event.is_set() and stable_count < STABILITY_TICKS:
            self._stop_event.wait(timeout=STABILITY_POLL_INTERVAL)
            if self._stop_event.is_set():
                return False
            game_image = self._detector.capture_game()
            if game_image is None:
                stable_count = 0
                continue
            wx, wy, ww, wh = bounds
            # Reuse quick_verify which checks that the expected position
            # still has the skills window header.
            panel_ix = wx - self._detector._game_origin[0] if self._detector._game_origin else 0
            panel_iy = wy - self._detector._game_origin[1] if self._detector._game_origin else 0
            if self._detector.quick_verify(game_image, panel_ix, panel_iy, ww, wh):
                stable_count += 1
            else:
                stable_count = 0
        return stable_count >= STABILITY_TICKS

    def _wait_for_skills_window(self) -> Optional[tuple[int, int, int, int]]:
        """Poll until the skills window is detected or timeout is reached."""
        log.info("Waiting for skills window... Open it in-game to begin scanning.")
        start = time.monotonic()
        attempt = 0

        while not self._stop_event.is_set():
            attempt += 1
            elapsed = time.monotonic() - start
            remaining = DETECT_TIMEOUT - elapsed

            if remaining <= 0:
                log.warning("Timed out after %.0fs — skills window not found",
                            DETECT_TIMEOUT)
                return None

            window_bounds = self._detector.detect()
            if window_bounds:
                log.info("Skills window detected at %s (attempt %d, %.1fs)",
                         window_bounds, attempt, elapsed)
                return window_bounds

            if attempt == 1:
                log.debug("Not found yet, retrying every %.0fs (timeout %.0fs)...",
                          DETECT_POLL_INTERVAL, DETECT_TIMEOUT)
            elif attempt % 10 == 0:
                log.debug("Still waiting... (%.0fs elapsed, %.0fs remaining)",
                          elapsed, remaining)

            self._stop_event.wait(timeout=DETECT_POLL_INTERVAL)

        return None

    def _compute_layout(self, window_bounds: tuple[int, int, int, int]) -> dict:
        """Compute all derived coordinates from window_bounds.

        Returns a dict with all layout values needed for cropping and scanning.
        """
        wx, wy, ww, wh = window_bounds
        col_ranges = self._detector.get_column_ranges(window_bounds)
        sidebar_bounds = self._detector.get_sidebar_region(window_bounds)
        pagination_bounds = self._detector.get_pagination_region(window_bounds)
        layout = WINDOW_LAYOUT

        # Table region in local coords (relative to skills panel origin)
        table_lx = col_ranges["name"][0]
        table_ly = self._detector.get_table_top(wh)
        table_lw = col_ranges["points"][1] - col_ranges["name"][0]
        table_lh = int(wh * layout["table_bottom_ratio"]) - table_ly

        # Screen-absolute positions for debug display
        table_sx = wx + table_lx
        table_sy = wy + table_ly

        # Pagination region in local coords
        pag_lx = col_ranges["name"][0]
        pag_ly = int(wh * layout["pagination_ratio"])
        pag_lw = col_ranges["points"][1] - col_ranges["name"][0]
        pag_lh = int(wh * (1.0 - layout["pagination_ratio"]))

        # Total row region in local coords (between table bottom and pagination)
        total_lx, total_ly, total_lw, total_lh = \
            self._detector.get_total_region(window_bounds)

        # Offset of skills panel within the full game window image
        gox, goy = self._detector.game_origin
        panel_ix = wx - gox
        panel_iy = wy - goy

        return {
            "window_bounds": window_bounds,
            "col_ranges": col_ranges,
            "sidebar_bounds": sidebar_bounds,
            "pagination_bounds": pagination_bounds,
            "table_lx": table_lx, "table_ly": table_ly,
            "table_lw": table_lw, "table_lh": table_lh,
            "table_sx": table_sx, "table_sy": table_sy,
            "pag_lx": pag_lx, "pag_ly": pag_ly,
            "pag_lw": pag_lw, "pag_lh": pag_lh,
            "total_lx": total_lx, "total_ly": total_ly,
            "total_lw": total_lw, "total_lh": total_lh,
            "panel_ix": panel_ix, "panel_iy": panel_iy,
            "ww": ww, "wh": wh,
        }

    def _verify_title_text(self, game_image: np.ndarray,
                           panel_ix: int, panel_iy: int,
                           window_bounds: tuple[int, int, int, int]) -> bool:
        """OCR the title band and check it says 'SKILLS'."""
        tx, ty, tw, th = self._detector.get_title_region(window_bounds)
        crop_x = panel_ix + tx
        crop_y = panel_iy + ty
        img_h, img_w = game_image.shape[:2]

        if crop_x < 0 or crop_y < 0 or crop_x + tw > img_w or crop_y + th > img_h:
            log.warning("Title band out of bounds")
            return False

        title_img = game_image[crop_y:crop_y + th, crop_x:crop_x + tw]
        title_processed = self._preprocessor.preprocess_light_text_dark_bg(title_img)
        title_text = self._recognizer.read_text(title_processed)

        if title_text and "skill" in title_text.lower():
            log.debug("Title verified: '%s'", title_text)
            return True

        log.warning("Title verification failed: '%s' (expected 'SKILLS')", title_text)
        return False

    def _publish_debug_regions(self, L: dict) -> None:
        """Publish layout regions to the debug overlay."""
        wb = L["window_bounds"]
        wx = wb[0]
        self._event_bus.publish(EVENT_DEBUG_REGIONS, {
            "window": wb,
            "sidebar": L["sidebar_bounds"],
            "pagination": L["pagination_bounds"],
            "table": (L["table_sx"], L["table_sy"], L["table_lw"], L["table_lh"]),
            "columns": {
                name: (wx + start, L["table_sy"], end - start, L["table_lh"])
                for name, (start, end) in L["col_ranges"].items()
            },
            "templates": self._detector.get_template_positions(wb),
            "col_screen": {
                name: (wx + start, wx + end)
                for name, (start, end) in L["col_ranges"].items()
            },
            "font_path": self._font_matcher.font_path,
            "font_size": self._font_matcher.font_size,
        })

    def run_continuous(self) -> Optional[SkillScanResult]:
        """Continuously monitor the skills window and scan visible pages.

        The user navigates manually; we detect changes and re-scan.
        Returns the final accumulated result when stopped or window closes.
        """
        scan_start = datetime.now()
        result = SkillScanResult(scan_start=scan_start, total_expected=len(self._all_skills))
        self._found_skill_names.clear()

        # Step 1: Wait for the skills window and verify title
        window_bounds = self._wait_for_skills_window()
        if not window_bounds:
            return None

        # Ensure the window is stable (not mid-drag) before proceeding
        if not self._wait_for_stable_window(window_bounds):
            return None

        wx, wy, ww, wh = window_bounds
        log.info("Skills window found at (%d,%d) %dx%d", wx, wy, ww, wh)

        # Verify the title says "SKILLS" before proceeding
        game_image = self._detector.last_game_image
        L = self._compute_layout(window_bounds)
        if game_image is not None:
            if not self._verify_title_text(game_image, L["panel_ix"], L["panel_iy"], window_bounds):
                log.warning("Window title is not 'SKILLS', re-detecting...")
                self._detector.invalidate_cache()
                window_bounds = self._wait_for_skills_window()
                if not window_bounds:
                    return None
                L = self._compute_layout(window_bounds)
                wx, wy, ww, wh = window_bounds

        # Calibrate font matcher for the detected panel size
        self._font_matcher.calibrate(wh)

        self._calibration_cells: list[np.ndarray] = []  # for auto-calibration
        self._auto_calibrated = False

        log.debug("Layout: table=(%d,%d) %dx%d, cols=%s",
                  L['table_lx'], L['table_ly'], L['table_lw'], L['table_lh'],
                  {k: v for k, v in L['col_ranges'].items()})

        self._publish_debug_regions(L)

        # Step 2: Continuous monitoring loop
        # anchor_skill / anchor_key: the first matched skill from the last
        # successful scan.  Used for fast page-change detection — if the first
        # row still exact-matches the anchor, the page hasn't changed.
        anchor_skill: Optional[str] = None
        anchor_key: Optional[bytes] = None
        scan_count = 0

        log.info("Monitoring skills window. Navigate in-game; scans happen automatically.")

        while not self._stop_event.is_set():
            # Capture the full game window via PrintWindow (ignores overlays)
            game_image = self._detector.capture_game()
            if game_image is None:
                log.warning("Game window capture failed, retrying...")
                self._stop_event.wait(timeout=MONITOR_INTERVAL)
                continue

            img_h, img_w = game_image.shape[:2]

            # Quick-verify the skills window is still at the expected position
            if not self._detector.quick_verify(
                game_image, L["panel_ix"], L["panel_iy"], L["ww"], L["wh"]
            ):
                log.warning("Skills window moved or closed, re-detecting...")
                self._detector.invalidate_cache()
                anchor_skill = None
                anchor_key = None

                # Re-detect (poll until found or stopped)
                new_bounds = None
                while not self._stop_event.is_set():
                    new_bounds = self._detector.detect()
                    if new_bounds:
                        break
                    log.debug("Skills window not found, waiting...")
                    self._stop_event.wait(timeout=DETECT_POLL_INTERVAL)

                if not new_bounds:
                    break  # Stopped

                # Recompute layout with new position
                L = self._compute_layout(new_bounds)
                window_bounds = new_bounds
                wx, wy, ww, wh = new_bounds

                # Re-capture and verify title at new position
                game_image = self._detector.capture_game()
                if game_image is not None:
                    if not self._verify_title_text(
                        game_image, L["panel_ix"], L["panel_iy"], new_bounds
                    ):
                        log.warning("Re-detected window title is not 'SKILLS', skipping...")
                        self._detector.invalidate_cache()
                        self._stop_event.wait(timeout=DETECT_POLL_INTERVAL)
                        continue

                # Wait for stable position before re-scanning
                if not self._wait_for_stable_window(new_bounds):
                    break

                self._font_matcher.calibrate(wh)
        
                self._calibration_cells = []
                self._auto_calibrated = False
                self._publish_debug_regions(L)
                log.info("Skills window re-detected at (%d,%d) %dx%d", wx, wy, ww, wh)
                continue  # Re-enter loop with fresh capture

            # Crop the table region
            crop_x = L["panel_ix"] + L["table_lx"]
            crop_y = L["panel_iy"] + L["table_ly"]
            crop_x2 = crop_x + L["table_lw"]
            crop_y2 = crop_y + L["table_lh"]

            if crop_x < 0 or crop_y < 0 or crop_x2 > img_w or crop_y2 > img_h:
                log.warning("Table crop out of bounds: (%d,%d)-(%d,%d) in %dx%d image",
                            crop_x, crop_y, crop_x2, crop_y2, img_w, img_h)
                self._stop_event.wait(timeout=MONITOR_INTERVAL)
                continue

            table_image = game_image[crop_y:crop_y2, crop_x:crop_x2]

            # Fast page-change detection: extract the first row's name cell
            # and check if it still matches the anchor from the last scan.
            # Much cheaper than a full pixel diff or OCR scan.
            if anchor_key is not None:
                _, _, _, wh_check = window_bounds
                rh = self._detector.get_row_height(wh_check)
                ns = L["col_ranges"]["name"][0]
                ne_local = L["col_ranges"]["name"][1] - ns
                th, tw = table_image.shape[:2]
                if rh <= th and ne_local <= tw:
                    first_row = table_image[0:rh, 0:ne_local]
                    first_gray = (cv2.cvtColor(first_row, cv2.COLOR_BGR2GRAY)
                                  if len(first_row.shape) == 3 else first_row)
                    current_key = self._font_matcher._to_lookup_key(first_gray)
                    if current_key == anchor_key:
                        self._stop_event.wait(timeout=MONITOR_INTERVAL)
                        continue
                log.debug("Page change detected (anchor '%s' no longer matches)",
                          anchor_skill)

            # Page changed — clear old checkmarks
            self._event_bus.publish(EVENT_OCR_PAGE_CHANGED, None)

            scan_count += 1

            # OCR the visible rows (returns None if too many misses)
            page_skills = self._scan_table_image(
                table_image, L["col_ranges"], window_bounds, L["table_sy"],
            )
            if page_skills is None:
                # Bad scan — window likely moved.  Reset anchor so the next
                # capture is treated as fresh.
                anchor_skill = None
                anchor_key = None
                self._stop_event.wait(timeout=MONITOR_INTERVAL)
                continue

            # Update anchor from the first matched skill for next poll
            if page_skills:
                anchor_skill = page_skills[0].skill_name
                # Re-extract first row cell to compute the anchor hash
                _, _, _, wh_anchor = window_bounds
                rh = self._detector.get_row_height(wh_anchor)
                ns = L["col_ranges"]["name"][0]
                ne_local = L["col_ranges"]["name"][1] - ns
                th, tw = table_image.shape[:2]
                if rh <= th and ne_local <= tw:
                    first_row = table_image[0:rh, 0:ne_local]
                    first_gray = (cv2.cvtColor(first_row, cv2.COLOR_BGR2GRAY)
                                  if len(first_row.shape) == 3 else first_row)
                    anchor_key = self._font_matcher._to_lookup_key(first_gray)
                else:
                    anchor_key = None
            else:
                anchor_skill = None
                anchor_key = None

            result.skills.extend(page_skills)

            # Auto-calibrate after first page: test font sizes and modes
            if (scan_count == 1 and not self._auto_calibrated
                    and hasattr(self, '_calibration_cells')
                    and self._calibration_cells):
                self._auto_calibrated = True
                log.info("Auto-calibrating with %d sample cells...",
                         len(self._calibration_cells))
                self._font_matcher.auto_calibrate(self._calibration_cells)

                self._calibration_cells.clear()

            # Read pagination from cropped game image
            pcx = L["panel_ix"] + L["pag_lx"]
            pcy = L["panel_iy"] + L["pag_ly"]
            if 0 <= pcx and pcx + L["pag_lw"] <= img_w and 0 <= pcy and pcy + L["pag_lh"] <= img_h:
                pag_image = game_image[pcy:pcy + L["pag_lh"], pcx:pcx + L["pag_lw"]]
                pag_processed = self._preprocessor.preprocess_light_text_dark_bg(pag_image)
                pag_text = self._recognizer.read_text(pag_processed)
                parsed = self._navigator.parse_pagination_text(pag_text)

                self._event_bus.publish(EVENT_DEBUG_ROW, {
                    "type": "pagination",
                    "raw_text": pag_text,
                    "parsed": f"{parsed[0]}/{parsed[1]}" if parsed else "FAILED",
                    "category": "manual",
                })

            # Publish progress
            missing = [s["name"] for s in self._all_skills
                       if s["name"] not in self._found_skill_names]
            self._event_bus.publish(EVENT_OCR_PROGRESS, ScanProgress(
                total_skills_expected=len(self._all_skills),
                skills_found=len(self._found_skill_names),
                current_category="manual",
                current_page=scan_count,
                total_pages=0,
                missing_names=missing[-10:] if len(missing) <= 10 else [],
            ))

            log.info("Scan #%d: %d/%d skills found",
                     scan_count, len(self._found_skill_names), len(self._all_skills))

            # Verify total if ALL CATEGORIES is selected
            points_sum = sum(s.current_points for s in result.skills)
            verified = self._verify_total(game_image, L, points_sum)
            if verified is True:
                log.info("Points total verified against in-game display")
            elif verified is False:
                log.warning("Points total does NOT match in-game display")

            self._stop_event.wait(timeout=MONITOR_INTERVAL)

        # Final result
        result.scan_end = datetime.now()
        result.total_found = len(self._found_skill_names)
        result.missing_skills = [
            s["name"] for s in self._all_skills
            if s["name"] not in self._found_skill_names
        ]

        self._event_bus.publish(EVENT_OCR_COMPLETE, result)
        log.info("Monitoring stopped: %d/%d skills found",
                 result.total_found, result.total_expected)
        log.info("Captured templates: %d skills, %d ranks, %d digits",
                 self._font_matcher.captured_skill_count,
                 self._font_matcher.captured_rank_count,
                 self._font_matcher.captured_digit_count)
        return result

    def _scan_table_image(self, table_image: np.ndarray, col_ranges: dict,
                          window_bounds: tuple, table_screen_y: int
                          ) -> Optional[list[SkillReading]]:
        """OCR all skill rows from a cropped table image.

        Returns the list of matched skills, or None if the scan is
        discarded (too many content rows failed to match, indicating the
        window may have moved mid-capture).
        """
        skills: list[SkillReading] = []
        _, _, _, wh = window_bounds
        row_height = self._detector.get_row_height(wh)
        rows = self._preprocessor.extract_rows(table_image, row_height)

        # Precompute brightness-check dimensions (same logic as _parse_skill_row)
        name_start = col_ranges["name"][0]
        name_end_local = col_ranges["name"][1] - name_start
        text_h_ratio = WINDOW_LAYOUT["row_text_ratio"]

        content_rows = 0
        miss_rows = 0
        self._pending_captures.clear()

        for row_idx, row_image in enumerate(rows):
            row_h, row_w = row_image.shape[:2]
            text_h = int(row_h * text_h_ratio)
            ne = min(name_end_local, row_w)

            # Brightness check: does this row have visible text?
            name_area = row_image[:text_h, 0:ne]
            gray_check = (cv2.cvtColor(name_area, cv2.COLOR_BGR2GRAY)
                          if len(name_area.shape) == 3 else name_area)
            has_content = int(np.sum(gray_check > 80)) >= MIN_BRIGHT_PIXELS

            if has_content:
                content_rows += 1

            row_screen_y = table_screen_y + row_idx * row_height
            skill = self._parse_skill_row(
                row_image, col_ranges, window_bounds,
                row_screen_y=row_screen_y, row_height=row_height,
                row_idx=row_idx,
            )

            if skill:
                skills.append(skill)
            elif has_content:
                miss_rows += 1

        # If too many content rows failed, the window likely moved mid-capture.
        # Discard the entire page — don't persist, don't capture templates.
        if content_rows > 0 and miss_rows / content_rows >= MAX_MISS_FRACTION:
            log.warning(
                "Scan discarded: %d/%d content rows unmatched "
                "(%.0f%% miss rate >= %.0f%% threshold)",
                miss_rows, content_rows,
                100 * miss_rows / content_rows,
                100 * MAX_MISS_FRACTION,
            )
            self._pending_captures.clear()
            return None

        # Scan is valid — persist results and execute deferred captures
        for skill in skills:
            self._found_skill_names.add(skill.skill_name)
            self._db.insert_skill_snapshot(
                scan_timestamp=skill.scan_timestamp.isoformat(),
                skill_name=skill.skill_name,
                rank=skill.rank,
                current_points=skill.current_points,
                progress_percent=skill.progress_percent,
                category=skill.category,
            )

        for cap in self._pending_captures:
            captured = self._font_matcher.capture_skill(
                cap["skill_name"], cap["name_gray"])
            if captured:
                # Verify the new template works through the full match pipeline
                verify = self._font_matcher.match_skill_name(cap["name_gray"])
                if not verify or verify[0] != cap["skill_name"]:
                    log.warning(
                        "Post-capture verification failed for '%s': got %s",
                        cap["skill_name"], verify)
            if cap["rank_text"]:
                self._font_matcher.capture_rank(cap["rank_text"], cap["rank_gray"])
            if cap["points_text"]:
                self._font_matcher.capture_digits(cap["points_text"], cap["points_gray"])
        self._pending_captures.clear()

        return skills

    def _parse_skill_row(self, row_image, col_ranges: dict, window_bounds: tuple,
                         row_screen_y: int = 0,
                         row_height: int = 0,
                         row_idx: int = 0) -> Optional[SkillReading]:
        """Parse a single skill row from its image.

        Each column cell has text in the top portion and a progress bar in the
        bottom portion. We split vertically to OCR text and read bars separately.
        """
        name_start = col_ranges["name"][0]
        row_h = row_image.shape[0]
        row_w = row_image.shape[1]

        # Vertical split: text zone (top) and bar zone (bottom)
        text_h = int(row_h * WINDOW_LAYOUT["row_text_ratio"])

        # Column positions relative to the row image (which starts at name_start)
        name_end = min(col_ranges["name"][1] - name_start, row_w)
        rank_start = col_ranges["rank"][0] - name_start
        rank_end = min(col_ranges["rank"][1] - name_start, row_w)
        points_start = col_ranges["points"][0] - name_start
        points_end = min(col_ranges["points"][1] - name_start, row_w)

        # Text zones (top portion of each cell)
        name_text_img = row_image[:text_h, 0:name_end]

        # Quick brightness check: skip rows with no visible text (avoids Tesseract).
        # Uses absolute pixel count — short names like "Aim" occupy very few pixels
        # in a wide column and fail fraction-based checks.
        gray_name = cv2.cvtColor(name_text_img, cv2.COLOR_BGR2GRAY) \
            if len(name_text_img.shape) == 3 else name_text_img
        bright_pixels = int(np.sum(gray_name > 80))
        if bright_pixels < MIN_BRIGHT_PIXELS:
            log.debug("Row %d: brightness check failed (%d < %d bright px, "
                      "cell %dx%d, max=%d)",
                      row_idx, bright_pixels, MIN_BRIGHT_PIXELS,
                      gray_name.shape[0], gray_name.shape[1],
                      int(np.max(gray_name)))
            return None

        rank_text_img = row_image[:text_h, rank_start:rank_end]
        points_text_img = row_image[:text_h, points_start:points_end]

        # Bar zones (bottom portion of each cell)
        rank_bar_img = row_image[text_h:, rank_start:rank_end]
        progress_bar_img = row_image[text_h:, points_start:points_end]

        # Grayscale cells for font matching — use full row height (not text_h)
        # so descenders and bottom antialiasing aren't clipped.  The progress
        # bar at the bottom is dark and gets cleaned by noise suppression.
        name_full = row_image[:, 0:name_end]
        name_gray = cv2.cvtColor(name_full, cv2.COLOR_BGR2GRAY) \
            if len(name_full.shape) == 3 else name_full
        rank_full = row_image[:, rank_start:rank_end]
        rank_gray = cv2.cvtColor(rank_full, cv2.COLOR_BGR2GRAY) \
            if len(rank_full.shape) == 3 else rank_full
        points_full = row_image[:, points_start:points_end]
        points_gray = cv2.cvtColor(points_full, cv2.COLOR_BGR2GRAY) \
            if len(points_text_img.shape) == 3 else points_text_img

        # Collect sample cells for auto-calibration (first page only)
        if hasattr(self, '_calibration_cells') and not self._auto_calibrated:
            if len(self._calibration_cells) < 12:
                self._calibration_cells.append(name_gray.copy())

        # Match skill name via font templates
        matched_name = None
        name_text = ""
        font_attempt = None
        if self._font_matcher.calibrated:
            skill_match = self._font_matcher.match_skill_name(name_gray)
            if skill_match:
                matched_name, confidence = skill_match
                name_text = matched_name
                tpl = self._font_matcher.get_skill_template(matched_name)
                font_attempt = {"name": matched_name, "score": confidence,
                                "template": tpl}
            else:
                best = self._font_matcher.best_skill_match(name_gray)
                if best:
                    log.debug("Row %d: font match below threshold, "
                              "best='%s' (score=%.3f)",
                              row_idx, best[0], best[1])
                    tpl = self._font_matcher.get_skill_template(best[0])
                    font_attempt = {"name": best[0], "score": best[1],
                                    "template": tpl}
                else:
                    log.debug("Row %d: no font match at all (cell %dx%d)",
                              row_idx, name_gray.shape[1], name_gray.shape[0])

        # Tesseract fallback if font matching failed
        if not matched_name:
            name_processed = self._preprocessor.preprocess_light_text_dark_bg(name_text_img)
            name_text = self._recognizer.read_skill_name(name_processed)
            log.debug("Row %d: Tesseract read '%s'", row_idx, name_text)

            if name_text and len(name_text) >= 2:
                matched = self._skill_matcher.match(
                    name_text, threshold=self._config.ocr_confidence_threshold)
                if matched:
                    matched_name = matched["name"]
                else:
                    log.debug("Row %d: Tesseract text '%s' did not match "
                              "any skill", row_idx, name_text)

        # Last resort: use best font template match (below threshold)
        if not matched_name and font_attempt:
            matched_name = font_attempt["name"]
            name_text = matched_name
            log.debug("Row %d: using best font match '%s' (score=%.3f) "
                      "as fallback", row_idx, matched_name,
                      font_attempt["score"])

        if not matched_name:
            return None

        # Read rank via font templates (with Tesseract fallback)
        rank_text = None
        if self._font_matcher.calibrated:
            rank_match = self._font_matcher.match_rank(rank_gray)
            if rank_match:
                rank_text = rank_match[0]

        if not rank_text:
            rank_processed = self._preprocessor.preprocess_light_text_dark_bg(rank_text_img)
            rank_raw = self._recognizer.read_rank(rank_processed)
            rank_text = self._rank_verifier.match_rank(rank_raw) or rank_raw

        # Read points via font templates (with Tesseract fallback)
        points_text = None
        if self._font_matcher.calibrated:
            points_text = self._font_matcher.read_points(points_gray)

        if not points_text:
            points_processed = self._preprocessor.preprocess_light_text_dark_bg(points_text_img)
            points_text = self._recognizer.read_number(points_processed)

        # Defer template capture — only execute if the whole page scan is valid
        # (no window-movement detected).  See _scan_table_image.
        if matched_name and self._font_matcher.calibrated:
            self._pending_captures.append({
                "skill_name": matched_name,
                "name_gray": name_gray,
                "rank_text": rank_text,
                "rank_gray": rank_gray,
                "points_text": points_text,
                "points_gray": points_gray,
            })

        try:
            points_value = float(points_text) if points_text else 0.0
        except ValueError:
            points_value = 0.0

        # Read progress bar (bottom of points cell) — the bar we care about
        progress = self._bar_reader.read_progress(progress_bar_img)

        # Read rank bar (bottom of rank cell) — for cross-verification
        rank_progress = self._bar_reader.read_progress(rank_bar_img)

        # Cross-verify rank + points against known rank thresholds
        verification = self._rank_verifier.verify(
            rank_text or "", points_value, rank_progress)
        if not verification["rank_matches"] and rank_text and points_value > 0:
            log.warning("Rank mismatch: '%s' vs expected '%s' for %s pts",
                        rank_text, verification['expected_rank'], points_value)

        self._event_bus.publish(EVENT_DEBUG_ROW, {
            "type": "matched",
            "raw_text": name_text,
            "matched_name": matched_name,
            "rank": rank_text or "?",
            "points": points_text or "?",
            "progress": f"{progress:.2f}%",
            "rank_bar": f"{rank_progress:.2f}%",
            "rank_verified": verification["rank_matches"],
            "expected_rank": verification["expected_rank"],
            "y": row_screen_y,
            "h": row_height,
            "font_attempt": font_attempt,
        })

        return SkillReading(
            skill_name=matched_name,
            rank=rank_text or "Unknown",
            current_points=points_value,
            progress_percent=progress,
            category="manual",
            scan_timestamp=datetime.now(),
        )

    def _read_total_value(self, game_image: np.ndarray, L: dict) -> Optional[int]:
        """Read the 'Total: XXXXX' value from the skills window.

        The Total row sits between the table bottom and pagination area.
        Returns the integer total, or None if it couldn't be read.
        """
        img_h, img_w = game_image.shape[:2]
        cx = L["panel_ix"] + L["total_lx"]
        cy = L["panel_iy"] + L["total_ly"]
        cw = L["total_lw"]
        ch = L["total_lh"]

        if cx < 0 or cy < 0 or cx + cw > img_w or cy + ch > img_h:
            log.debug("Total region out of bounds")
            return None

        total_img = game_image[cy:cy + ch, cx:cx + cw]
        if total_img.size == 0:
            return None

        processed = self._preprocessor.preprocess_light_text_dark_bg(total_img)
        text = self._recognizer.read_text(processed)
        if not text:
            return None

        # Parse "Total: 59094" or just "59094"
        match = re.search(r"(\d[\d,. ]*)", text.replace("O", "0").replace("o", "0"))
        if not match:
            log.debug("Total text not parseable: '%s'", text)
            return None

        num_str = match.group(1).replace(",", "").replace(".", "").replace(" ", "")
        try:
            value = int(num_str)
            log.debug("Total value read: %d (raw text: '%s')", value, text)
            return value
        except ValueError:
            log.debug("Total value parse failed: '%s' from '%s'", num_str, text)
            return None

    def _verify_total(self, game_image: np.ndarray, L: dict,
                      found_points_sum: float) -> Optional[bool]:
        """Verify scan accuracy by comparing found points to the displayed Total.

        Only works when ALL CATEGORIES is selected (otherwise the Total
        only reflects the current category).

        Returns True if verified, False if mismatch, None if can't verify.
        """
        if not self._detector.is_all_categories_selected(
            game_image, L["panel_ix"], L["panel_iy"], L["ww"], L["wh"]
        ):
            log.debug("Total verification skipped: ALL CATEGORIES not selected")
            return None

        displayed_total = self._read_total_value(game_image, L)
        if displayed_total is None:
            log.debug("Total verification skipped: couldn't read Total value")
            return None

        found_total = int(round(found_points_sum))
        if displayed_total == found_total:
            log.info("Total verified: %d matches displayed Total", found_total)
            return True

        log.warning("Total mismatch: OCR found %d points, display shows %d (diff: %d)",
                    found_total, displayed_total, abs(found_total - displayed_total))
        return False

