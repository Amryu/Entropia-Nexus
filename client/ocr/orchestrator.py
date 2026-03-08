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
    EVENT_OCR_PROGRESS, EVENT_OCR_COMPLETE, EVENT_OCR_CANCEL,
    EVENT_OCR_OVERLAYS_HIDE,
    EVENT_DEBUG_REGIONS, EVENT_DEBUG_ROW,
    EVENT_OCR_PAGE_CHANGED, EVENT_SKILL_SCANNED,
    EVENT_ROI_CONFIG_CHANGED,
)
from .models import SkillReading, SkillScanResult, ScanProgress
from .capturer import ScreenCapturer
from .preprocessor import ImagePreprocessor
from .skill_parser import SkillMatcher, RankVerifier
from .progress_bar import ProgressBarReader
from .detector import SkillsWindowDetector, SAVE_DEBUG_IMAGES, DEBUG_DIR
from .font_matcher import (
    FontMatcher, _detect_orange, _orange_grayscale,
)
from .navigator import SkillsNavigator
from .trace import OcrTracer

log = get_logger("OCR")

# How often to check for the skills window (seconds)
DETECT_POLL_INTERVAL = 1.0
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

# How many consecutive quick_verify failures before declaring the panel moved.
# A single bad window-capture frame (common with DirectX) should not trigger
# expensive re-detection; require multiple confirmations first.
VERIFY_FAIL_THRESHOLD = 2

# Faster poll interval when re-detecting a panel that was just visible.
REDETECT_POLL_INTERVAL = 0.3
# How long to keep looking for the panel after it disappears.
# After this, we consider it closed and enter hibernation (waiting for reopen).
REDETECT_TIMEOUT = 10.0

# Some backends on focused DirectX games may return stale (cached) frames.
# If this many consecutive captures are byte-identical in the table region,
# we assume the frames are stale and clear the page anchor so the next
# fresh frame triggers a re-scan.
STALE_FRAME_THRESHOLD = 15  # ~1.5s at 100ms poll interval

# Require repeated first-row mismatches before treating it as a page change.
PAGE_CHANGE_CONFIRM_TICKS = 2
# If first-row anchor is unreadable, wait this many monitor ticks before
# forcing a full page re-scan.
PAGE_UNKNOWN_RESCAN_TICKS = 20  # ~2s at 100ms poll interval

# Number of rows to store as anchors for page-change detection.
# If the first row is unreadable (background bleed-through, etc.),
# subsequent rows serve as fallback anchors.
MAX_ANCHOR_FALLBACK_ROWS = 3

# Minimum number of bright pixels (>80 grayscale) to consider a row non-empty.
# Using an absolute count instead of a fraction of cell area avoids rejecting
# short names like "Aim" that occupy very few pixels in a wide column.
# ~50 bright pixels ≈ a 3-character word at game font size.
MIN_BRIGHT_PIXELS = 50

# Pixels to trim from the right edge of the points column ROI.
# The points column extends to window_width - 5 (scrollbar edge), leaving
# ~30px of empty space past the actual digits.
POINTS_COL_RIGHT_TRIM = 30

# If this fraction (or more) of rows in a page scan fail to match a skill
# name, assume the window moved mid-capture and discard the page.
MAX_MISS_FRACTION = 0.5

# Warn when a previously stable skill value jumps by this many points.
SKILL_VALUE_JUMP_WARNING_DELTA = 30.0
# Confidence bands for below-threshold fallback matches.
# < 0.60: reject as failed OCR row.
# 0.60 - <0.70: accept but warn as low confidence.
FALLBACK_FAILURE_CONFIDENCE = 0.60
FALLBACK_LOW_CONFIDENCE = 0.70

# Skills that don't appear in the in-game SKILLS panel and should be
# excluded from the expected total / missing list.
EXCLUDED_SKILL_NAMES = {"Promoter Rating", "Reputation"}


class ScanOrchestrator:
    """Coordinates the OCR skills scan pipeline.

    Operates in continuous monitoring mode:
    1. Wait for the skills window to appear
    2. Capture the game window directly (window capture backend, ignoring overlays)
    3. Crop the table region and OCR visible rows
    4. Detect page changes and re-scan automatically
    5. User navigates categories/pages manually
    """

    def __init__(self, config: AppConfig, event_bus: EventBus, db: Database,
                 frame_cache=None):
        self._config = config
        self._event_bus = event_bus
        self._db = db
        self._stop_event = threading.Event()
        self._rescan_requested = threading.Event()
        self._shutdown = False  # True only when app is shutting down (not on cancel)
        self._pause_until_window_reopen = False

        # Use shared frame cache if provided, else create own capturer
        self._frame_cache = frame_cache
        if frame_cache is None:
            self._capturer = ScreenCapturer(capture_backend=config.ocr_capture_backend)
        else:
            # Detector still needs its own direct window captures for detect().
            self._capturer = ScreenCapturer(capture_backend=config.ocr_capture_backend)
        self._tracer = OcrTracer()
        self._tracer.set_enabled(config.ocr_trace_enabled)

        self._preprocessor = ImagePreprocessor()
        self._skill_matcher = SkillMatcher()
        self._rank_verifier = RankVerifier()
        self._bar_reader = ProgressBarReader()
        self._bar_reader.set_tracer(self._tracer)
        self._detector = SkillsWindowDetector(
            self._capturer, event_bus=self._event_bus, config=config)
        self._detector.set_tracer(self._tracer)
        self._navigator = SkillsNavigator()

        self._all_skills = list(self._skill_matcher.get_all_skills())
        self._expected_skill_names: set[str] = {
            s["name"] for s in self._all_skills
            if s["name"] not in EXCLUDED_SKILL_NAMES
        }
        self._found_skill_names: set[str] = set()
        self._last_skill_readings: dict[str, SkillReading] = {}

        # Font-based template matcher for per-row OCR
        skill_names = [s["name"] for s in self._all_skills]
        rank_names = self._rank_verifier._rank_names
        self._font_matcher = FontMatcher(skill_names, rank_names)
        self._font_matcher.set_tracer(self._tracer)
        # Pre-render (or load cached) templates in background so they're
        # ready before the first scan — avoids a multi-second stall on
        # window detection.
        threading.Thread(
            target=self._font_matcher.pre_initialize,
            daemon=True, name="font-init",
        ).start()
        self._pending_captures: list[dict] = []
        # Cached local layout (relative to panel origin).  The skills panel is
        # fixed-size so these coordinates never change — only the screen
        # position (wx, wy) changes when the panel is moved.
        self._cached_local_layout: dict | None = None
        # Current window bounds (set during active scan, used for ROI live update)
        self._current_window_bounds: tuple[int, int, int, int] | None = None

        # Apply initial ROI overrides from config
        self._apply_roi_overrides(config.scan_roi_overrides)
        self._event_bus.subscribe(EVENT_ROI_CONFIG_CHANGED, self._on_roi_config_changed)
        self._event_bus.subscribe(EVENT_OCR_CANCEL, self._on_cancel)

    def stop(self):
        """Signal the continuous monitor to stop permanently (app shutdown)."""
        self._shutdown = True
        self._stop_event.set()
        self._event_bus.unsubscribe(EVENT_ROI_CONFIG_CHANGED, self._on_roi_config_changed)
        self._event_bus.unsubscribe(EVENT_OCR_CANCEL, self._on_cancel)

    def set_capture_backend(self, capture_backend: str) -> None:
        """Apply window capture backend change at runtime."""
        try:
            self._capturer.set_capture_backend(capture_backend)
        except Exception as e:
            log.warning("Failed to update OCR capture backend: %s", e)

    def set_trace_enabled(self, enabled: bool) -> None:
        """Toggle OCR trace mode at runtime."""
        self._tracer.set_enabled(enabled)

    def _on_cancel(self, data=None):
        """Handle external cancel request (e.g. from scan summary overlay)."""
        pause_until_reopen = (
            isinstance(data, dict) and bool(data.get("pause_until_reopen"))
        )
        if pause_until_reopen:
            self._pause_until_window_reopen = True
            log.info("Scan cancelled via EVENT_OCR_CANCEL (pause until reopen)")
        else:
            self._pause_until_window_reopen = False
            log.info("Scan cancelled via EVENT_OCR_CANCEL")
        self._stop_event.set()

    def _wait_for_window_reopen_cycle(self) -> bool:
        """Block resume until the Skills window has closed and reopened once."""
        log.info("OCR resume paused until SKILLS window is reopened")
        saw_closed = False

        while not self._stop_event.is_set() and not self._shutdown:
            if not self._detector.is_game_foreground():
                self._stop_event.wait(timeout=DETECT_POLL_INTERVAL)
                continue

            bounds = self._detector.detect()
            if bounds is None:
                saw_closed = True
            elif saw_closed:
                self._pause_until_window_reopen = False
                log.info("SKILLS window reopened, resuming scan")
                return True

            self._stop_event.wait(timeout=DETECT_POLL_INTERVAL)

        return False

    def _apply_roi_overrides(self, overrides: dict) -> None:
        """Push ROI pixel overrides from config to the detector."""
        parsed = {}
        for name, vals in overrides.items():
            if isinstance(vals, (list, tuple)) and len(vals) == 4:
                parsed[name] = tuple(int(v) for v in vals)
        self._detector.set_roi_overrides(parsed)

    def _on_roi_config_changed(self, data: dict) -> None:
        """Handle live ROI changes from the config dialog."""
        self._apply_roi_overrides(data)
        self._cached_local_layout = None
        # Re-publish debug overlay so ROI rectangles update in real-time
        self._detector.republish_roi_debug()

    def _wait_for_stable_window(self, bounds: tuple[int, int, int, int]
                                ) -> bool:
        """Wait for the window to hold still for STABILITY_TICKS consecutive
        fast polls.  Returns True if stable, False if stopped or moved away."""
        log.debug("Stability check: waiting for %d ticks at %s", STABILITY_TICKS, bounds)
        stable_count = 0
        while not self._stop_event.is_set() and stable_count < STABILITY_TICKS:
            self._stop_event.wait(timeout=STABILITY_POLL_INTERVAL)
            if self._stop_event.is_set():
                log.debug("Stability check: stopped")
                return False
            game_image = self._detector.capture_game()
            if game_image is None:
                stable_count = 0
                log.debug("Stability check: capture failed, reset count")
                continue
            wx, wy, ww, wh = bounds
            # Reuse quick_verify which checks that the expected position
            # still has the skills window header.
            panel_ix = wx - self._detector._game_origin[0] if self._detector._game_origin else 0
            panel_iy = wy - self._detector._game_origin[1] if self._detector._game_origin else 0
            if self._detector.quick_verify(game_image, panel_ix, panel_iy, ww, wh):
                stable_count += 1
                log.debug("Stability check: tick %d/%d", stable_count, STABILITY_TICKS)
            else:
                stable_count = 0
                log.debug("Stability check: verify failed, reset count")
        passed = stable_count >= STABILITY_TICKS
        log.debug("Stability check: %s", "STABLE" if passed else "UNSTABLE")
        return passed

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
                log.debug("Timed out after %.0fs — skills window not found",
                           DETECT_TIMEOUT)
                return None

            # Cheap foreground check: skip expensive capture + template
            # matching when the game isn't the active window (<0.1ms vs ~100ms)
            if not self._detector.is_game_foreground():
                self._stop_event.wait(timeout=DETECT_POLL_INTERVAL)
                continue

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

        Uses pixel-based ROIs (DEFAULT_ROI_PIXELS in detector.py, with
        user overrides from config) as the primary source.  Column ranges come from
        column-header template matching (more precise).  Falls back to
        pixel-based ROI definitions from the SKILLS template match.

        The skills panel is fixed-size, so local coordinates are cached
        after the first computation.

        Returns a dict with all layout values needed for cropping and scanning.
        """
        wx, wy, ww, wh = window_bounds
        gox, goy = self._detector.game_origin
        panel_ix = wx - gox
        panel_iy = wy - goy

        # Reuse cached local layout if panel dimensions match
        if (self._cached_local_layout is not None
                and self._cached_local_layout["ww"] == ww
                and self._cached_local_layout["wh"] == wh):
            log.debug("Using cached local layout for panel at (%d,%d)", wx, wy)
            c = self._cached_local_layout
        else:
            # All layout from ROIs (authoritative, pixel-based)
            col_ranges = self._detector.get_column_ranges(window_bounds)
            bar_ranges = self._detector.get_bar_ranges()
            first_row = self._detector.resolve_roi("first_row")
            total_roi = self._detector.resolve_roi("total")
            indicator_roi = self._detector.resolve_roi("indicator")
            row_height = self._detector.resolve_row_height()
            row_pitch = self._detector.resolve_row_pitch()

            table_lx = first_row[0] if first_row else 0
            table_ly = first_row[1] if first_row else 0
            table_lw = self._detector.resolve_table_width() or 0
            table_lh = self._detector.resolve_table_height() or 0

            total_lx = total_roi[0] if total_roi else 0
            total_ly = total_roi[1] if total_roi else 0
            total_lw = total_roi[2] if total_roi else 0
            total_lh = total_roi[3] if total_roi else 0

            indicator_lx = indicator_roi[0] if indicator_roi else 0
            indicator_ly = indicator_roi[1] if indicator_roi else 0
            indicator_lw = indicator_roi[2] if indicator_roi else 0
            indicator_lh = indicator_roi[3] if indicator_roi else 0

            # Pagination: derived from table bottom
            pag_lx = table_lx
            pag_ly = total_ly + total_lh + 4 if total_roi else 0
            pag_lw = table_lw
            pag_lh = wh - pag_ly if pag_ly > 0 else 0

            c = {
                "ww": ww, "wh": wh,
                "col_ranges": col_ranges,
                "bar_ranges": bar_ranges,
                "table_lx": table_lx, "table_ly": table_ly,
                "table_lw": table_lw, "table_lh": table_lh,
                "pag_lx": pag_lx, "pag_ly": pag_ly,
                "pag_lw": pag_lw, "pag_lh": pag_lh,
                "total_lx": total_lx, "total_ly": total_ly,
                "total_lw": total_lw, "total_lh": total_lh,
                "indicator_lx": indicator_lx, "indicator_ly": indicator_ly,
                "indicator_lw": indicator_lw, "indicator_lh": indicator_lh,
                "row_height": row_height or 25,
                "row_pitch": row_pitch or row_height or 25,
            }
            self._cached_local_layout = c
            log.debug("Cached local layout for %dx%d panel", ww, wh)

        # Combine cached local coords with current screen position
        return {
            "window_bounds": window_bounds,
            "col_ranges": c["col_ranges"],
            "bar_ranges": c["bar_ranges"],
            "table_lx": c["table_lx"], "table_ly": c["table_ly"],
            "table_lw": c["table_lw"], "table_lh": c["table_lh"],
            "table_sx": wx + c["table_lx"], "table_sy": wy + c["table_ly"],
            "pag_lx": c["pag_lx"], "pag_ly": c["pag_ly"],
            "pag_lw": c["pag_lw"], "pag_lh": c["pag_lh"],
            "total_lx": c["total_lx"], "total_ly": c["total_ly"],
            "total_lw": c["total_lw"], "total_lh": c["total_lh"],
            "indicator_lx": c["indicator_lx"], "indicator_ly": c["indicator_ly"],
            "indicator_lw": c["indicator_lw"], "indicator_lh": c["indicator_lh"],
            "row_height": c["row_height"],
            "row_pitch": c["row_pitch"],
            "panel_ix": panel_ix, "panel_iy": panel_iy,
            "ww": c["ww"], "wh": c["wh"],
        }

    def _verify_title_text(self, game_image: np.ndarray,
                           panel_ix: int, panel_iy: int,
                           window_bounds: tuple[int, int, int, int]) -> bool:
        """Verify the title band contains 'SKILLS' via template matching."""
        _, _, ww, wh = window_bounds
        return self._detector.quick_verify(
            game_image, panel_ix, panel_iy, ww, wh
        )

    def _publish_debug_regions(self, L: dict) -> None:
        """Publish layout regions to the scan row overlay."""
        self._event_bus.publish(EVENT_DEBUG_REGIONS, {
            "table": (L["table_sx"], L["table_sy"], L["table_lw"], L["table_lh"]),
        })

    def run_continuous(self, *, auto_resume: bool = True) -> Optional[SkillScanResult]:
        """Continuously monitor the skills window and scan visible pages.

        The user navigates manually; we detect changes and re-scan.
        Automatically resumes when the window is closed and reopened.
        Returns the final accumulated result when stopped.
        """
        if self._pause_until_window_reopen:
            if not self._wait_for_window_reopen_cycle():
                return None

        scan_start = datetime.now()
        result = SkillScanResult(
            scan_start=scan_start,
            total_expected=len(self._expected_skill_names),
        )
        self._found_skill_names.clear()
        self._last_skill_readings.clear()
        scan_count = 0

        # Outer loop: wait for window → monitor → window closed → repeat
        while not self._stop_event.is_set():
            # Step 1: Wait for the skills window and verify title
            window_bounds = self._wait_for_skills_window()
            if not window_bounds:
                break

            # Ensure the window is stable (not mid-drag) before proceeding
            if not self._wait_for_stable_window(window_bounds):
                break

            wx, wy, ww, wh = window_bounds
            log.info("Skills window found at (%d,%d) %dx%d", wx, wy, ww, wh)

            # Verify the title says "SKILLS" before proceeding
            game_image = self._detector.last_game_image
            L = self._compute_layout(window_bounds)
            if game_image is not None:
                if not self._verify_title_text(game_image, L["panel_ix"], L["panel_iy"], window_bounds):
                    log.warning("Window title is not 'SKILLS', re-detecting...")
                    self._detector.invalidate_cache()
                    continue  # Loop back to wait

            # Calibrate font matcher for the detected panel size
            self._font_matcher.calibrate(wh)

            log.debug("Layout: table=(%d,%d) %dx%d, cols=%s",
                      L['table_lx'], L['table_ly'], L['table_lw'], L['table_lh'],
                      {k: v for k, v in L['col_ranges'].items()})

            self._current_window_bounds = window_bounds
            self._publish_debug_regions(L)

            # Step 2: Monitor — returns True if window was closed (resume),
            # False if user cancelled (stop)
            window_closed, new_scan_count = self._run_monitor_loop(
                result, window_bounds, L, scan_count,
            )
            scan_count = new_scan_count

            if not window_closed:
                break  # User cancelled — exit outer loop

            if not auto_resume:
                # Manual mode: stop after the first completed monitor session.
                self._event_bus.publish(EVENT_OCR_OVERLAYS_HIDE, None)
                break

            # Window was closed — hide overlays and loop back to wait
            log.info("Skills window closed, waiting for it to reopen...")
            self._event_bus.publish(EVENT_OCR_OVERLAYS_HIDE, None)

        # Final result
        result.scan_end = datetime.now()
        result.total_found = len(
            self._found_skill_names - EXCLUDED_SKILL_NAMES
        )
        result.missing_skills = [
            s["name"] for s in self._all_skills
            if s["name"] not in self._found_skill_names
            and s["name"] not in EXCLUDED_SKILL_NAMES
        ]

        self._current_window_bounds = None
        self._event_bus.publish(EVENT_OCR_COMPLETE, result)
        log.info("Monitoring stopped: %d/%d skills found",
                 result.total_found, result.total_expected)
        log.info("Captured templates: %d skills, %d ranks, %d digits",
                 self._font_matcher.captured_skill_count,
                 self._font_matcher.captured_rank_count,
                 self._font_matcher.captured_digit_count)
        return result

    def _run_monitor_loop(
        self,
        result: SkillScanResult,
        window_bounds: tuple[int, int, int, int],
        L: dict,
        scan_count: int,
    ) -> tuple[bool, int]:
        """Inner monitoring loop: scan pages and detect changes.

        Returns (window_closed, scan_count):
            window_closed=True  → window was closed, caller should wait for reopen
            window_closed=False → user cancelled via stop_event
        """
        # Per-row anchors for page-change detection.  Each entry is
        # (skill_name | None, pixel_key | None) indexed by visual row.
        # None entries mean the row was unreadable at scan time.
        anchor_entries: list[tuple[Optional[str], bytes | None]] = []
        page_change_confirm_count = 0
        unknown_anchor_ticks = 0
        verify_fail_count = 0
        last_frame_hash: int = 0  # hash of last table region for stale detection
        stale_frame_count = 0
        wx, wy, ww, wh = window_bounds

        log.info("Monitoring skills window. Navigate in-game; scans happen automatically.")

        while not self._stop_event.is_set():
            # Check for manual re-scan request (clears anchors so the
            # current page is scanned again without leaving the loop).
            if self._rescan_requested.is_set():
                self._rescan_requested.clear()
                anchor_entries.clear()
                page_change_confirm_count = 0
                unknown_anchor_ticks = 0
                log.info("Manual re-scan requested, clearing anchors")

            # Capture the full game window (ignores overlays)
            game_image = self._detector.capture_game()
            if game_image is None:
                log.warning("Game window capture failed, retrying...")
                self._stop_event.wait(timeout=MONITOR_INTERVAL)
                continue

            img_h, img_w = game_image.shape[:2]

            # Detect small window movements via local-area template match.
            # Searches ±8px around last known position — catches 1px drift that
            # would otherwise cause wrong ROI reads.  Falls back to full-image
            # search if the panel moved far or was closed.
            new_bounds = self._detector.quick_adjust(game_image)
            if new_bounds is None:
                verify_fail_count += 1
                if verify_fail_count < VERIFY_FAIL_THRESHOLD:
                    log.debug("quick_adjust failed (%d/%d), retrying...",
                              verify_fail_count, VERIFY_FAIL_THRESHOLD)
                    self._stop_event.wait(timeout=MONITOR_INTERVAL)
                    continue

                # Panel lost — try full re-detection with game window lookup
                log.warning("Skills panel lost (%d consecutive failures), "
                            "re-detecting...", verify_fail_count)
                verify_fail_count = 0
                self._event_bus.publish(EVENT_OCR_OVERLAYS_HIDE, lambda: None)
                anchor_entries.clear()
                page_change_confirm_count = 0
                unknown_anchor_ticks = 0
                self._detector.invalidate_cache()
                redetect_deadline = time.monotonic() + REDETECT_TIMEOUT
                while not self._stop_event.is_set():
                    if time.monotonic() > redetect_deadline:
                        log.info("Panel not found after %.0fs — assuming closed",
                                 REDETECT_TIMEOUT)
                        break
                    new_bounds = self._detector.detect()
                    if new_bounds:
                        break
                    log.debug("Skills panel not found, waiting...")
                    self._stop_event.wait(timeout=REDETECT_POLL_INTERVAL)

                if not new_bounds:
                    if self._stop_event.is_set():
                        return False, scan_count  # User cancelled
                    return True, scan_count  # Window closed — auto-resume

                if not self._wait_for_stable_window(new_bounds):
                    return False, scan_count

            # Update layout if the panel position changed
            if new_bounds != window_bounds:
                L = self._compute_layout(new_bounds)
                window_bounds = new_bounds
                self._current_window_bounds = new_bounds
                wx, wy, ww, wh = new_bounds
                self._font_matcher.calibrate(wh)
                self._publish_debug_regions(L)

            verify_fail_count = 0

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

            # Stale frame detection: focused DirectX captures may return
            # return cached frames.  Track consecutive identical captures for
            # diagnostics.  Page-change detection now uses font-matched skill
            # names (robust to background transparency), so stale frames no
            # longer need to clear the anchor.
            frame_hash = hash(table_image.data.tobytes()[:4096])
            if frame_hash == last_frame_hash:
                stale_frame_count += 1
                if stale_frame_count == STALE_FRAME_THRESHOLD:
                    log.debug("Stale frames detected (%d identical captures)",
                              stale_frame_count)
            else:
                stale_frame_count = 0
            last_frame_hash = frame_hash

            # Fast page-change detection: check anchor rows against the
            # last scan.  Tries up to MAX_ANCHOR_FALLBACK_ROWS rows so that
            # if the first row is unreadable (background bleed-through, etc.)
            # subsequent rows serve as fallback anchors.
            _, _, _, wh_check = window_bounds
            rh = self._detector.get_row_height(wh_check)
            ns = L["col_ranges"]["name"][0]
            ne_local = L["col_ranges"]["name"][1] - ns
            th, tw = table_image.shape[:2]

            current_name = None  # for logging
            page_same = False
            any_readable = False
            num_check = min(
                len(anchor_entries), MAX_ANCHOR_FALLBACK_ROWS,
                th // rh if rh > 0 else 0,
            )

            if rh > 0 and ne_local <= tw:
                for check_idx in range(num_check):
                    anchor_name, anchor_key = anchor_entries[check_idx]
                    if anchor_name is None and anchor_key is None:
                        continue  # row was unreadable at scan time too

                    row_y = check_idx * rh
                    if row_y + rh > th:
                        break
                    cell = table_image[row_y:row_y + rh, 0:ne_local]
                    gray = (cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
                            if len(cell.shape) == 3 else cell)
                    cell_bgr = cell if len(cell.shape) == 3 else None
                    row_key = self._font_matcher._to_lookup_key(gray)
                    match = self._font_matcher.match_skill_name(
                        gray, cell_bgr, trace=False)
                    row_name = match[0] if match else None

                    if row_name is None and row_key is None:
                        continue  # row unreadable this tick, try next

                    any_readable = True
                    if current_name is None:
                        current_name = row_name

                    same_by_name = (
                        row_name is not None and row_name == anchor_name
                    )
                    same_by_key = (
                        row_key is not None
                        and anchor_key is not None
                        and row_key == anchor_key
                    )
                    if same_by_name or same_by_key:
                        page_same = True
                        break

            if page_same:
                page_change_confirm_count = 0
                unknown_anchor_ticks = 0
                self._stop_event.wait(timeout=MONITOR_INTERVAL)
                continue

            if anchor_entries:
                if not any_readable:
                    # All anchor rows unreadable — wait before forcing re-scan.
                    unknown_anchor_ticks += 1
                    if unknown_anchor_ticks < PAGE_UNKNOWN_RESCAN_TICKS:
                        self._stop_event.wait(timeout=MONITOR_INTERVAL)
                        continue
                    log.debug(
                        "Anchor rows unreadable for %d ticks; forcing re-scan",
                        unknown_anchor_ticks,
                    )
                    unknown_anchor_ticks = 0
                    page_change_confirm_count = 0
                else:
                    # At least one row readable but none match — page changed.
                    unknown_anchor_ticks = 0
                    page_change_confirm_count += 1
                    if page_change_confirm_count < PAGE_CHANGE_CONFIRM_TICKS:
                        self._stop_event.wait(timeout=MONITOR_INTERVAL)
                        continue
                    page_change_confirm_count = 0
                    prev_anchor = next(
                        (n for n, _ in anchor_entries if n is not None),
                        None,
                    )
                    log.debug(
                        "Page change detected (anchor: '%s' -> '%s')",
                        prev_anchor, current_name,
                    )

            # Page changed — clear old checkmarks
            self._event_bus.publish(EVENT_OCR_PAGE_CHANGED, None)
            if self._tracer.enabled:
                prev_anchor = next(
                    (n for n, _ in anchor_entries if n is not None), None,
                )
                self._tracer.log(
                    "PAGE",
                    f"anchor={prev_anchor}->{current_name} "
                    f"scan=#{scan_count + 1}",
                )
                page_annotated = table_image.copy()
                if len(page_annotated.shape) == 2:
                    page_annotated = cv2.cvtColor(
                        page_annotated, cv2.COLOR_GRAY2BGR)
                cv2.putText(page_annotated, f"Scan #{scan_count + 1}",
                            (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                            (0, 255, 255), 1)
                self._tracer.save_image("page", page_annotated)

            scan_count += 1

            # OCR the visible rows (returns None if too many misses)
            page_skills = self._scan_table_image(
                table_image, L["col_ranges"], L["bar_ranges"],
                window_bounds, L["table_sy"],
            )
            if page_skills is None:
                # Bad scan — window likely moved.  Reset anchors so the
                # next capture is treated as fresh.
                anchor_entries.clear()
                page_change_confirm_count = 0
                unknown_anchor_ticks = 0
                self._stop_event.wait(timeout=MONITOR_INTERVAL)
                continue

            # Update per-row anchors from the first readable rows.
            anchor_entries.clear()
            max_anchor = min(
                MAX_ANCHOR_FALLBACK_ROWS,
                th // rh if rh > 0 else 0,
            )
            for ai in range(max_anchor):
                row_y = ai * rh
                if row_y + rh > th:
                    break
                cell = table_image[row_y:row_y + rh, 0:ne_local]
                gray = (cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
                        if len(cell.shape) == 3 else cell)
                cell_bgr = cell if len(cell.shape) == 3 else None
                match = self._font_matcher.match_skill_name(
                    gray, cell_bgr, trace=False)
                if match:
                    key = self._font_matcher._to_lookup_key(gray)
                    anchor_entries.append((match[0], key))
                else:
                    anchor_entries.append((None, None))
            page_change_confirm_count = 0
            unknown_anchor_ticks = 0
            result.skills.extend(page_skills)

            # Read pagination from cropped game image
            pcx = L["panel_ix"] + L["pag_lx"]
            pcy = L["panel_iy"] + L["pag_ly"]
            if 0 <= pcx and pcx + L["pag_lw"] <= img_w and 0 <= pcy and pcy + L["pag_lh"] <= img_h:
                pag_image = game_image[pcy:pcy + L["pag_lh"], pcx:pcx + L["pag_lw"]]
                pag_text = self._read_pagination(pag_image)
                parsed = self._navigator.parse_pagination_text(pag_text) if pag_text else None

                self._event_bus.publish(EVENT_DEBUG_ROW, {
                    "type": "pagination",
                    "raw_text": pag_text or "",
                    "parsed": f"{parsed[0]}/{parsed[1]}" if parsed else "FAILED",
                    "category": "manual",
                })

            # Publish progress
            missing = [
                s["name"] for s in self._all_skills
                if s["name"] in self._expected_skill_names
                and s["name"] not in self._found_skill_names
            ]
            found_expected = len(
                self._found_skill_names.intersection(self._expected_skill_names)
            )
            expected_total = len(self._expected_skill_names)
            self._event_bus.publish(EVENT_OCR_PROGRESS, ScanProgress(
                total_skills_expected=expected_total,
                skills_found=found_expected,
                current_category="manual",
                current_page=scan_count,
                total_pages=0,
                missing_names=missing[-10:] if len(missing) <= 10 else [],
            ))

            log.info("Scan #%d: %d/%d skills found",
                     scan_count, found_expected, expected_total)
            if self._tracer.enabled:
                matched = len(page_skills) if page_skills else 0
                self._tracer.log("SCAN", f"#{scan_count} matched={matched} found={found_expected}/{expected_total}")

            # Verify total if ALL CATEGORIES is selected
            points_sum = sum(s.current_points for s in result.skills)
            verified = self._verify_total(game_image, L, points_sum)
            if verified is True:
                log.info("Points total verified against in-game display")
            elif verified is False:
                log.warning("Points total does NOT match in-game display")

            # Update detection debug image after each scan
            if SAVE_DEBUG_IMAGES:
                gox, goy = self._detector._game_origin or (0, 0)
                self._detector.save_debug_image(game_image, gox, goy, window_bounds)

            self._stop_event.wait(timeout=MONITOR_INTERVAL)

        return False, scan_count  # User cancelled

    def _scan_table_image(self, table_image: np.ndarray, col_ranges: dict,
                          bar_ranges: dict, window_bounds: tuple,
                          table_screen_y: int
                          ) -> Optional[list[SkillReading]]:
        """OCR all skill rows from a cropped table image.

        Returns the list of matched skills, or None if the scan is
        discarded (too many content rows failed to match, indicating the
        window may have moved mid-capture).
        """
        skills: list[SkillReading] = []
        _, _, _, wh = window_bounds
        row_height = self._detector.get_row_height(wh)
        row_pitch = self._detector.resolve_row_pitch() or row_height
        rows = self._preprocessor.extract_rows(table_image, row_height, row_pitch)
        text_h, _, _ = self._resolve_row_vertical_regions(row_height)

        # Precompute brightness-check dimensions (same logic as _parse_skill_row)
        name_start = col_ranges["name"][0]
        name_end_local = col_ranges["name"][1] - name_start

        content_rows = 0
        miss_rows = 0
        self._pending_captures.clear()

        for row_idx, row_image in enumerate(rows):
            _, row_w = row_image.shape[:2]
            ne = min(name_end_local, row_w)

            # Brightness check: does this row have visible text?
            name_area = row_image[:text_h, 0:ne]
            gray_check = (cv2.cvtColor(name_area, cv2.COLOR_BGR2GRAY)
                          if len(name_area.shape) == 3 else name_area)
            has_content = int(np.sum(gray_check > 80)) >= MIN_BRIGHT_PIXELS

            if has_content:
                content_rows += 1

            row_screen_y = table_screen_y + row_idx * row_pitch
            skill = self._parse_skill_row(
                row_image, col_ranges, bar_ranges, window_bounds,
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
            previous = self._last_skill_readings.get(skill.skill_name)
            if (
                previous is not None
                and not previous.is_mismatch
                and not skill.is_mismatch
            ):
                delta = abs(skill.current_points - previous.current_points)
                if delta > SKILL_VALUE_JUMP_WARNING_DELTA:
                    log.warning(
                        "Large OCR jump for '%s' without mismatch warning: "
                        "%.2f -> %.2f (delta=%.2f > %.2f)",
                        skill.skill_name,
                        previous.current_points,
                        skill.current_points,
                        delta,
                        SKILL_VALUE_JUMP_WARNING_DELTA,
                    )
            self._last_skill_readings[skill.skill_name] = skill

            self._found_skill_names.add(skill.skill_name)
            self._event_bus.publish(EVENT_SKILL_SCANNED, skill)

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
        self._pending_captures.clear()

        return skills

    def _resolve_row_vertical_regions(self, row_h: int) -> tuple[int, int, int]:
        """Resolve text and bar vertical zones from exact ROI configuration."""
        bar_offset = self._detector.resolve_bar_offset()
        if bar_offset is None:
            # Fallback only when title/template isn't resolved yet.
            bar_top = max(1, row_h - 4)
            bar_bot = row_h
        else:
            bar_top, bar_h = bar_offset
            bar_top = max(0, min(int(bar_top), row_h - 1))
            bar_h = max(1, int(bar_h))
            bar_bot = min(row_h, bar_top + bar_h)
            if bar_bot <= bar_top:
                bar_bot = min(row_h, bar_top + 1)

        text_h = max(1, min(bar_top, row_h))
        return text_h, bar_top, bar_bot

    def _save_row_debug(self, row_idx: int, row_image: np.ndarray,
                        cells: dict, results: dict) -> None:
        """Save an annotated debug image for one skill row.

        cells:   name_end, rank_start, rank_end, points_start, points_end,
                 rb_start, rb_end, pb_start, pb_end, text_h,
                 bar_top, bar_bot  (row-local px; bar_bot end-exclusive)
        results: matched_name, name_score, rank_text, rank_score,
                 points_text, rank_progress, points_progress,
                 name_gray, rank_gray, points_gray,
                 rank_bar_img, points_bar_img
        """
        try:
            out_dir = os.path.join(DEBUG_DIR, "rows")
            os.makedirs(out_dir, exist_ok=True)

            row_h, row_w = row_image.shape[:2]
            # Build a composite: row image on top, annotations below
            pad = 20  # text padding below
            canvas_h = row_h + pad
            canvas = np.zeros((canvas_h, row_w, 3), dtype=np.uint8)
            if len(row_image.shape) == 3:
                canvas[:row_h, :row_w] = row_image
            else:
                canvas[:row_h, :row_w] = cv2.cvtColor(row_image, cv2.COLOR_GRAY2BGR)

            text_h = cells["text_h"]

            # Draw cell boundaries (blue)
            for x in (cells["name_end"], cells["rank_start"], cells["rank_end"],
                      cells["points_start"], cells["points_end"]):
                if 0 <= x < row_w:
                    cv2.line(canvas, (x, 0), (x, row_h), (255, 100, 0), 1)

            # Text/bar split (green)
            cv2.line(canvas, (0, text_h), (row_w, text_h), (0, 200, 0), 1)

            # Bar boundaries (magenta = rank, cyan = points)
            bt = max(0, min(int(cells.get("bar_top", text_h)), row_h - 1))
            bar_bot = int(cells.get("bar_bot", row_h))
            bb = max(bt, min(max(bar_bot - 1, bt), row_h - 1))
            for bx_s, bx_e, color in (
                (cells["rb_start"], cells["rb_end"], (255, 0, 255)),
                (cells["pb_start"], cells["pb_end"], (255, 255, 0)),
            ):
                if 0 <= bx_s < row_w:
                    cv2.line(canvas, (bx_s, bt), (bx_s, bb), color, 1)
                if 0 <= bx_e < row_w:
                    cv2.line(canvas, (bx_e, bt), (bx_e, bb), color, 1)

            # Annotation text
            name = results.get("matched_name", "?")
            ns = results.get("name_score", 0)
            rank = results.get("rank_text") or "?"
            rs = results.get("rank_score", 0)
            pts = results.get("points_text") or "?"
            rp = results.get("rank_progress", 0)
            pp = results.get("points_progress", 0)

            label = (f"{name} ({ns:.3f})  |  {rank} ({rs:.3f})  |  "
                     f"{pts}  |  bars: rank={rp:.1f}% pts={pp:.1f}%")
            cv2.putText(canvas, label, (2, row_h + 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)

            path = os.path.join(out_dir, f"row_{row_idx:02d}.png")
            cv2.imwrite(path, canvas)
        except Exception as e:
            log.debug("Failed to save row debug: %s", e)

    def _save_low_confidence_debug(
        self,
        row_idx: int,
        row_image: np.ndarray,
        name_gray: np.ndarray,
        rank_gray: np.ndarray,
        points_gray: np.ndarray,
        matched_name: str,
        fallback_score: float,
        fallback_threshold: float,
        rank_text: Optional[str],
        points_text: Optional[str],
        rank_progress: float,
        points_progress: float,
    ) -> None:
        """Save focused debug output for low-confidence fallback matches."""
        try:
            out_dir = os.path.join(DEBUG_DIR, "low_confidence")
            os.makedirs(out_dir, exist_ok=True)

            row_bgr = (
                cv2.cvtColor(row_image, cv2.COLOR_GRAY2BGR)
                if len(row_image.shape) == 2
                else row_image
            )
            name_bgr = (
                cv2.cvtColor(name_gray, cv2.COLOR_GRAY2BGR)
                if len(name_gray.shape) == 2
                else name_gray
            )
            rank_bgr = (
                cv2.cvtColor(rank_gray, cv2.COLOR_GRAY2BGR)
                if len(rank_gray.shape) == 2
                else rank_gray
            )
            points_bgr = (
                cv2.cvtColor(points_gray, cv2.COLOR_GRAY2BGR)
                if len(points_gray.shape) == 2
                else points_gray
            )

            tiles = [
                ("NAME", name_bgr),
                ("RANK", rank_bgr),
                ("POINTS", points_bgr),
            ]
            pad = 6
            title_h = 14
            tiles_h = max(img.shape[0] for _, img in tiles)
            tiles_w = sum(img.shape[1] for _, img in tiles) + pad * (len(tiles) + 1)
            tiles_canvas = np.zeros((tiles_h + title_h + pad, tiles_w, 3), dtype=np.uint8)

            x = pad
            for label, img in tiles:
                cv2.putText(
                    tiles_canvas, label, (x, 11),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 220, 220), 1,
                )
                y = title_h + (tiles_h - img.shape[0]) // 2
                tiles_canvas[y:y + img.shape[0], x:x + img.shape[1]] = img
                x += img.shape[1] + pad

            info_h = 32
            out_w = max(row_bgr.shape[1], tiles_canvas.shape[1])
            out_h = row_bgr.shape[0] + tiles_canvas.shape[0] + info_h
            canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
            canvas[:row_bgr.shape[0], :row_bgr.shape[1]] = row_bgr
            y_tiles = row_bgr.shape[0]
            canvas[y_tiles:y_tiles + tiles_canvas.shape[0], :tiles_canvas.shape[1]] = tiles_canvas

            line1 = (
                f"row={row_idx} match='{matched_name}' "
                f"score={fallback_score:.3f} < {fallback_threshold:.2f}"
            )
            line2 = (
                f"rank={rank_text or '?'} points={points_text or '?'} "
                f"bars rank={rank_progress:.2f}% pts={points_progress:.2f}%"
            )
            text_y = y_tiles + tiles_canvas.shape[0] + 12
            cv2.putText(canvas, line1, (4, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)
            cv2.putText(canvas, line2, (4, text_y + 13),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)

            safe_name = re.sub(r"[^A-Za-z0-9]+", "_", matched_name).strip("_")
            if not safe_name:
                safe_name = "unknown"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            path = os.path.join(
                out_dir, f"row_{row_idx:02d}_{safe_name}_{timestamp}.png")
            cv2.imwrite(path, canvas)
            log.warning("Saved low-confidence OCR debug image: %s", path)
        except Exception as e:
            log.debug("Failed to save low-confidence debug image: %s", e)

    def _parse_skill_row(self, row_image, col_ranges: dict, bar_ranges: dict,
                         window_bounds: tuple,
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

        # Vertical split: text and bars come from explicit bar_offset ROI.
        text_h, bar_top, bar_bot = self._resolve_row_vertical_regions(row_h)

        # Column positions relative to the row image (which starts at name_start).
        name_end = min(col_ranges["name"][1] - name_start, row_w)
        rank_start = col_ranges["rank"][0] - name_start
        rank_end = min(col_ranges["rank"][1] - name_start, row_w)
        points_start = col_ranges["points"][0] - name_start
        points_end = min(col_ranges["points"][1] - name_start - POINTS_COL_RIGHT_TRIM, row_w)

        # Text zones (top portion of each cell)
        name_text_zone = row_image[:text_h, 0:name_end]

        # Quick brightness check: skip rows with no visible text.
        # Uses absolute pixel count — short names like "Aim" occupy very few pixels
        # in a wide column and fail fraction-based checks.
        gray_name = cv2.cvtColor(name_text_zone, cv2.COLOR_BGR2GRAY) \
            if len(name_text_zone.shape) == 3 else name_text_zone
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

        # Bar zones — use dedicated bar ROIs (relative to row image)
        rb_start = bar_ranges["rank"][0] - name_start
        rb_end = min(bar_ranges["rank"][1] - name_start, row_w)
        pb_start = bar_ranges["points"][0] - name_start
        pb_end = min(bar_ranges["points"][1] - name_start, row_w)
        rank_bar_img = row_image[bar_top:bar_bot, rb_start:rb_end]
        progress_bar_img = row_image[bar_top:bar_bot, pb_start:pb_end]

        # Grayscale cells for font matching.
        # Use a consistent text-zone crop for all three columns.
        name_gray = cv2.cvtColor(name_text_zone, cv2.COLOR_BGR2GRAY) \
            if len(name_text_zone.shape) == 3 else name_text_zone
        rank_text_zone = row_image[:text_h, rank_start:rank_end]
        rank_gray = cv2.cvtColor(rank_text_zone, cv2.COLOR_BGR2GRAY) \
            if len(rank_text_zone.shape) == 3 else rank_text_zone
        points_text_zone = row_image[:text_h, points_start:points_end]
        points_gray = cv2.cvtColor(points_text_zone, cv2.COLOR_BGR2GRAY) \
            if len(points_text_zone.shape) == 3 else points_text_zone

        # Match skill name via font templates
        # Pass BGR cell for orange/white text detection (trained skills
        # are rendered in orange which needs R-channel extraction).
        name_bgr = name_text_zone if len(name_text_zone.shape) == 3 else None
        matched_name = None
        name_text = ""
        font_attempt = None
        used_fallback = False
        low_confidence_fallback = False
        fallback_score = 0.0
        fallback_warn_threshold = FALLBACK_LOW_CONFIDENCE
        if self._font_matcher.calibrated:
            skill_match = self._font_matcher.match_skill_name(
                name_gray, name_bgr)
            if skill_match:
                matched_name, confidence = skill_match
                name_text = matched_name
                tpl = self._font_matcher.get_skill_template(matched_name)
                font_attempt = {"name": matched_name, "score": confidence,
                                "template": tpl}
            else:
                best = self._font_matcher.best_skill_match(
                    name_gray, name_bgr)
                if best:
                    log.debug("Row %d: font match below threshold, "
                              "best='%s' (score=%.3f)",
                              row_idx, best[0], best[1])
                    tpl = self._font_matcher.get_skill_template(best[0])
                    font_attempt = {"name": best[0], "score": best[1],
                                    "template": tpl}
                    if self._tracer.enabled:
                        self._tracer.log(
                            "FALLBACK",
                            f"[{row_idx:02d}] below_threshold best='{best[0]}'({best[1]:.3f})",
                        )
                else:
                    log.debug("Row %d: no font match at all (cell %dx%d)",
                              row_idx, name_gray.shape[1], name_gray.shape[0])
                    if self._tracer.enabled:
                        self._tracer.log(
                            "FALLBACK",
                            f"[{row_idx:02d}] no_match cell={name_gray.shape[1]}x{name_gray.shape[0]}",
                        )

        # Last resort: use best font template match (below threshold)
        if not matched_name and font_attempt:
            fallback_score = float(font_attempt["score"])
            if fallback_score < FALLBACK_FAILURE_CONFIDENCE:
                log.warning(
                    "Row %d: rejecting fallback skill match '%s' "
                    "(score=%.3f < %.2f)",
                    row_idx, font_attempt["name"], fallback_score,
                    FALLBACK_FAILURE_CONFIDENCE,
                )
                if self._tracer.enabled:
                    self._tracer.log(
                        "FALLBACK",
                        f"[{row_idx:02d}] REJECTED '{font_attempt['name']}'({fallback_score:.3f}) < {FALLBACK_FAILURE_CONFIDENCE:.2f}",
                    )
                    self._tracer.save_image("fallback_reject", name_gray, suffix=f"{row_idx:02d}_{font_attempt['name']}")
                return None

            matched_name = font_attempt["name"]
            name_text = matched_name
            used_fallback = True
            log.debug("Row %d: using best font match '%s' (score=%.3f) "
                      "as fallback", row_idx, matched_name,
                      fallback_score)
            if fallback_score < fallback_warn_threshold:
                low_confidence_fallback = True
                log.warning(
                    "Row %d: low-confidence skill fallback '%s' "
                    "(score=%.3f < %.2f)",
                    row_idx, matched_name, fallback_score,
                    fallback_warn_threshold,
                )
                if self._tracer.enabled:
                    self._tracer.log(
                        "FALLBACK",
                        f"[{row_idx:02d}] LOW_CONF '{matched_name}'({fallback_score:.3f}) < {fallback_warn_threshold:.2f}",
                    )

        if not matched_name:
            return None

        # Capture missing rank templates BEFORE matching so freshly
        # captured game-rendered templates are immediately available.
        fm = self._font_matcher
        # Pass BGR cell for orange/white text detection in rank matching
        rank_bgr = rank_text_zone if len(rank_text_zone.shape) == 3 else None
        if fm.calibrated:
            best_rank = fm.best_rank_match(rank_gray, rank_bgr)
            if best_rank and not fm.has_captured_rank(best_rank[0]):
                fm.capture_rank(best_rank[0], rank_gray)

        # Read rank via font templates (can now use freshly captured templates)
        # Compute the same effective grayscale that match_rank uses internally
        # so debug images reflect what the matcher actually sees.
        rank_match_gray = rank_gray
        if rank_bgr is not None and _detect_orange(rank_bgr):
            rank_match_gray = _orange_grayscale(rank_bgr)

        rank_text = None
        rank_score = 0.0
        if fm.calibrated:
            rank_match = fm.match_rank(rank_gray, rank_bgr)
            if rank_match:
                rank_text, rank_score = rank_match[0], rank_match[1]

        # Read points via font templates (can now use freshly captured templates)
        # Pass BGR cell for orange/white text detection in 4-bit pipeline
        points_text = None
        if fm.calibrated:
            points_bgr = points_text_zone if len(points_text_zone.shape) == 3 \
                else None
            points_text = fm.read_points(points_gray, points_bgr)

        # Defer skill name template capture — needs post-capture verification
        # and window-movement validation from _scan_table_image.
        if matched_name and fm.calibrated:
            self._pending_captures.append({
                "skill_name": matched_name,
                "name_gray": name_gray,
            })

        try:
            points_value = float(points_text) if points_text else 0.0
        except ValueError:
            log.debug("Points parse failed for '%s' (skill=%s), defaulting to 0.0",
                       points_text, matched_name)
            points_value = 0.0

        # Read progress bar (bottom of points cell) — the bar shows fractional
        # progress within the current integer point, so 56% → 0.56 decimals.
        progress = self._bar_reader.read_progress(progress_bar_img)
        points_value = float(int(points_value)) + progress / 100.0

        # Read rank bar (bottom of rank cell) — for cross-verification
        rank_progress = self._bar_reader.read_progress(rank_bar_img)

        if low_confidence_fallback:
            self._save_low_confidence_debug(
                row_idx=row_idx,
                row_image=row_image,
                name_gray=name_gray,
                rank_gray=rank_match_gray,
                points_gray=points_gray,
                matched_name=matched_name,
                fallback_score=fallback_score,
                fallback_threshold=fallback_warn_threshold,
                rank_text=rank_text,
                points_text=points_text,
                rank_progress=rank_progress,
                points_progress=progress,
            )

        # Save per-row debug images
        if SAVE_DEBUG_IMAGES:
            self._save_row_debug(row_idx, row_image,
                cells={
                    "name_end": name_end, "rank_start": rank_start,
                    "rank_end": rank_end, "points_start": points_start,
                    "points_end": points_end, "rb_start": rb_start,
                    "rb_end": rb_end, "pb_start": pb_start,
                    "pb_end": pb_end, "text_h": text_h,
                    "bar_top": bar_top, "bar_bot": bar_bot,
                },
                results={
                    "matched_name": matched_name,
                    "name_score": font_attempt["score"] if font_attempt else 0,
                    "rank_text": rank_text, "rank_score": rank_score,
                    "points_text": points_text,
                    "rank_progress": rank_progress,
                    "points_progress": progress,
                })
        # Trace: per-row summary
        if self._tracer.enabled:
            ns = font_attempt["score"] if font_attempt else 0
            fb = " FALLBACK" if used_fallback else ""
            self._tracer.log(
                "ROW",
                f"[{row_idx:02d}] name={matched_name}({ns:.2f}{fb}) "
                f"rank={rank_text or '?'}({rank_score:.2f}) "
                f"pts={points_text or '?'} bar={progress:.1f}%",
            )
            row_annotated = row_image.copy()
            if len(row_annotated.shape) == 2:
                row_annotated = cv2.cvtColor(row_annotated, cv2.COLOR_GRAY2BGR)
            label = f"{matched_name}({ns:.2f}{fb}) rank={rank_text or '?'} pts={points_text or '?'}"
            cv2.putText(row_annotated, label, (2, row_annotated.shape[0] - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
            self._tracer.save_image("row", row_annotated, suffix=f"{row_idx:02d}_{matched_name}")

        # Cross-verify rank + points against known rank thresholds
        verification = self._rank_verifier.verify(
            rank_text or "", points_value, rank_progress)
        if not verification["rank_matches"] and rank_text and points_value > 0:
            log.warning("Rank mismatch: '%s' vs expected '%s' for %s pts",
                        rank_text, verification['expected_rank'], points_value)
            if self._tracer.enabled:
                self._tracer.log(
                    "VERIFY",
                    f"[{row_idx:02d}] rank_mismatch actual='{rank_text}' "
                    f"expected='{verification['expected_rank']}' pts={points_value}",
                )

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
            "row_idx": row_idx,
            "y": row_screen_y,
            "h": row_height,
            "font_attempt": font_attempt,
            "used_fallback": used_fallback,
            "low_confidence_fallback": low_confidence_fallback,
            "fallback_score": fallback_score if used_fallback else None,
        })

        reading = SkillReading(
            skill_name=matched_name,
            rank=rank_text or "Unknown",
            current_points=points_value,
            progress_percent=progress,
            rank_bar_percent=rank_progress,
            category="manual",
            scan_timestamp=datetime.now(),
        )

        # Enrich with estimated decimal points and mismatch validation
        from .skill_estimator import enrich_skill_reading
        enrich_skill_reading(reading, self._rank_verifier._ranks)
        if reading.is_mismatch:
            log.warning(
                "Points mismatch for %s: estimated=%.1f, OCR=%d (rank=%s, rank_bar=%.2f%%)",
                reading.skill_name, reading.estimated_points,
                int(reading.current_points), reading.rank, reading.rank_bar_percent,
            )

        return reading

    def _read_pagination(self, pag_image: np.ndarray) -> Optional[str]:
        """Read pagination text like '1/3' using FontMatcher digit reading.

        Splits the image at the '/' separator (a vertical gap between digit
        groups), reads left and right halves as integers, and returns 'N/M'.
        """
        if not self._font_matcher.calibrated:
            return None

        gray = cv2.cvtColor(pag_image, cv2.COLOR_BGR2GRAY) \
            if len(pag_image.shape) == 3 else pag_image

        pag_bgr = pag_image if len(pag_image.shape) == 3 else None
        left = self._font_matcher.read_points(gray, pag_bgr)
        if not left:
            return None

        # The pagination is "N/M" — the '/' is not a digit so read_points
        # will only return the first number.  To get the second, find the
        # gap after the first digit group and read from there.
        cell_bin = self._font_matcher._to_binary(gray)
        col_sums = np.sum(cell_bin > 0, axis=0)

        # Walk right from the first bright pixel past the first digit group,
        # find the gap (separator), then the second digit group.
        bright = col_sums > 0
        in_text = False
        gap_start = None
        for x in range(len(bright)):
            if bright[x]:
                in_text = True
            elif in_text:
                # Entered a gap after first text group
                gap_start = x
                break

        if gap_start is None:
            return left  # Only one number found

        # Skip the gap to find the second digit group
        second_start = None
        for x in range(gap_start, len(bright)):
            if bright[x]:
                second_start = x
                break

        if second_start is None:
            return left

        right_region = gray[:, second_start:]
        right_bgr = pag_bgr[:, second_start:] if pag_bgr is not None else None
        right = self._font_matcher.read_points(right_region, right_bgr)
        if not right:
            return left

        return f"{left}/{right}"

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

        # Convert to grayscale and crop to the right half (digits only).
        # The "Total:" label occupies the left ~50%; digits are on the right.
        # Without cropping, read_points() matches digits from the label text
        # (e.g. the vertical stroke of "T" or "l" matching "1").
        gray = cv2.cvtColor(total_img, cv2.COLOR_BGR2GRAY) \
            if len(total_img.shape) == 3 else total_img
        gray = gray[:, cw // 2:]
        total_bgr = total_img[:, cw // 2:] \
            if len(total_img.shape) == 3 else None

        text = self._font_matcher.read_points(gray, total_bgr)
        if not text:
            log.debug("Total value not readable via FontMatcher")
            return None

        try:
            value = int(text)
            log.debug("Total value read: %d", value)
            return value
        except ValueError:
            log.debug("Total value parse failed: '%s'", text)
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
