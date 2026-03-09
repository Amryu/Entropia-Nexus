"""Capture manager — orchestrates screenshot and video clip capture.

Subscribes to globals/hotkeys, manages the rolling frame buffer,
and triggers screenshot/clip saves on own-global or manual hotkey.
"""

import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from ..core.constants import (
    EVENT_AUTH_STATE_CHANGED,
    EVENT_CAPTURE_ERROR,
    EVENT_CLIP_SAVED,
    EVENT_GLOBAL,
    EVENT_HOTKEY_TRIGGERED,
    EVENT_OWN_GLOBAL,
    EVENT_SCREENSHOT_SAVED,
    GAME_TITLE_PREFIX,
)
from ..core.logger import get_logger
from ..ocr.capturer import ScreenCapturer
from ..platform import backend as _platform
from .constants import (
    DEFAULT_CLIP_DIR,
    DEFAULT_SCREENSHOT_DIR,
    FILENAME_TIMESTAMP_FMT,
)
from .frame_buffer import FrameBuffer
from .screenshot import apply_blur_regions, build_screenshot_path, save_screenshot

log = get_logger("CaptureManager")


class CaptureManager:
    """Central coordinator for screenshot and video clip capture.

    Owns its capture thread (not foreground-gated) so video buffer
    records even when the game is behind other windows.
    """

    def __init__(self, *, config, event_bus, frame_distributor, oauth):
        self._config = config
        self._event_bus = event_bus
        self._frame_distributor = frame_distributor
        self._oauth = oauth

        self._eu_name: str | None = None
        self._running = False
        self._capture_thread: threading.Thread | None = None
        self._capturer: ScreenCapturer | None = None

        # Frame buffer for video clips
        self._frame_buffer = FrameBuffer(
            max_seconds=config.clip_buffer_seconds,
            fps=config.clip_fps,
        )

        # Audio / webcam (initialized later when clip features are built)
        self._audio_buffer = None
        self._webcam_capture = None

        # Pending clip save: when an own-global triggers a clip, we continue
        # buffering for post_global_seconds before saving.
        self._pending_clip_timer: threading.Timer | None = None

        # Track auth state for own-global detection
        if oauth and hasattr(oauth, "auth_state"):
            self._eu_name = getattr(oauth.auth_state, "eu_name", None)

        # Subscribe to events
        self._event_bus.subscribe(EVENT_GLOBAL, self._on_global)
        self._event_bus.subscribe(EVENT_AUTH_STATE_CHANGED, self._on_auth_changed)
        self._event_bus.subscribe(EVENT_HOTKEY_TRIGGERED, self._on_hotkey)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the capture manager and its capture thread."""
        if self._running:
            return
        self._running = True

        # Only start the continuous capture thread if clip recording is enabled
        if self._config.clip_enabled:
            self._start_capture_thread()
            self._start_audio()

        log.info("Capture manager started (screenshot=%s, clip=%s)",
                 self._config.screenshot_enabled, self._config.clip_enabled)

    def stop(self) -> None:
        """Stop the capture manager and all background threads."""
        self._running = False

        if self._pending_clip_timer:
            self._pending_clip_timer.cancel()
            self._pending_clip_timer = None

        if self._capture_thread:
            self._capture_thread.join(timeout=2)
            self._capture_thread = None

        if self._capturer:
            self._capturer.stop()
            self._capturer = None

        self._stop_audio()
        self._stop_webcam()
        self._frame_buffer.clear()

        log.info("Capture manager stopped")

    # ------------------------------------------------------------------
    # Capture thread (NOT foreground-gated)
    # ------------------------------------------------------------------

    def _start_capture_thread(self) -> None:
        """Start the dedicated capture thread for the rolling frame buffer."""
        backend = self._config.ocr_capture_backend
        self._capturer = ScreenCapturer(capture_backend=backend)
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="capture-buffer",
        )
        self._capture_thread.start()

    def _capture_loop(self) -> None:
        """Continuously capture game window frames into the rolling buffer."""
        fps = max(1, self._config.clip_fps)
        interval = 1.0 / fps
        game_hwnd = None

        while self._running:
            tick_start = time.monotonic()

            # Find game window if needed
            if not game_hwnd or not _platform.is_window_visible(game_hwnd):
                game_hwnd = _platform.find_window_by_title_prefix(GAME_TITLE_PREFIX)
                if not game_hwnd:
                    time.sleep(1.0)
                    continue

            # Capture (works even when game is behind other windows)
            geo = _platform.get_window_geometry(game_hwnd)
            frame = self._capturer.capture_window(game_hwnd, geometry=geo)
            if frame is not None:
                self._frame_buffer.push(frame, tick_start)

            # Sleep remainder of tick
            elapsed = time.monotonic() - tick_start
            remaining = interval - elapsed
            if remaining > 0:
                time.sleep(remaining)

    # ------------------------------------------------------------------
    # Audio (placeholder — implemented in audio_buffer.py)
    # ------------------------------------------------------------------

    def _start_audio(self) -> None:
        """Start audio capture if enabled."""
        if not self._config.clip_audio_enabled:
            return
        try:
            from .audio_buffer import AudioBuffer
            self._audio_buffer = AudioBuffer(
                device=self._config.clip_audio_device or None,
            )
            self._audio_buffer.start()
            log.info("Audio capture started")
        except Exception as e:
            log.warning("Audio capture unavailable: %s", e)
            self._audio_buffer = None

    def _stop_audio(self) -> None:
        if self._audio_buffer:
            self._audio_buffer.stop()
            self._audio_buffer = None

    def _start_webcam(self) -> None:
        """Start webcam capture if enabled."""
        if not self._config.clip_webcam_enabled:
            return
        try:
            from .webcam_capture import WebcamCapture
            self._webcam_capture = WebcamCapture(
                device=self._config.clip_webcam_device,
            )
            self._webcam_capture.start()
            log.info("Webcam capture started")
        except Exception as e:
            log.warning("Webcam capture unavailable: %s", e)
            self._webcam_capture = None

    def _stop_webcam(self) -> None:
        if self._webcam_capture:
            self._webcam_capture.stop()
            self._webcam_capture = None

    # ------------------------------------------------------------------
    # Own-global detection
    # ------------------------------------------------------------------

    def _on_auth_changed(self, state) -> None:
        self._eu_name = getattr(state, "eu_name", None)

    def _is_own_global(self, player_name: str) -> bool:
        """Check if a global belongs to the local player."""
        if not player_name:
            return False
        name_lower = player_name.lower()
        # Check EU name from auth
        if self._eu_name and name_lower == self._eu_name.lower():
            return True
        # Check config fallback
        char_name = self._config.character_name
        if char_name and name_lower == char_name.lower():
            return True
        return False

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_global(self, event) -> None:
        """Handle a global event — trigger capture if it's our own."""
        if not self._is_own_global(event.player_name):
            return

        log.info("Own global detected: %s killed %s for %.2f PED",
                 event.player_name, event.target_name, event.value)
        self._event_bus.publish(EVENT_OWN_GLOBAL, event)

        # Screenshot
        if self._config.screenshot_enabled and self._config.screenshot_auto_on_global:
            delay = self._config.screenshot_delay_s
            threading.Timer(
                delay,
                self._take_global_screenshot,
                args=(event,),
            ).start()

        # Video clip
        if self._config.clip_enabled and self._config.clip_auto_on_global:
            post_seconds = self._config.clip_post_global_seconds
            # Cancel any pending clip save (e.g. rapid successive globals)
            if self._pending_clip_timer:
                self._pending_clip_timer.cancel()
            self._pending_clip_timer = threading.Timer(
                post_seconds,
                self._save_global_clip,
                args=(event,),
            )
            self._pending_clip_timer.start()

    def _on_hotkey(self, data) -> None:
        """Handle hotkey events for manual screenshot/clip."""
        action = data if isinstance(data, str) else getattr(data, "action", None)
        if action == "screenshot":
            self._take_manual_screenshot()
        elif action == "save_clip":
            self._save_manual_clip()

    # ------------------------------------------------------------------
    # Screenshot actions
    # ------------------------------------------------------------------

    def _take_global_screenshot(self, event) -> None:
        """Capture a screenshot after an own-global event."""
        frame = self._grab_frame()
        if frame is None:
            self._event_bus.publish(EVENT_CAPTURE_ERROR,
                                    {"error": "No game frame available for screenshot"})
            return

        path = build_screenshot_path(
            base_dir=self._config.screenshot_directory,
            daily_subfolder=self._config.screenshot_daily_subfolder,
            target_name=event.target_name,
            amount=event.value,
            timestamp=event.timestamp if hasattr(event, "timestamp") else None,
        )

        ok = save_screenshot(frame, path, self._config.capture_blur_regions)
        if ok:
            self._event_bus.publish(EVENT_SCREENSHOT_SAVED, {
                "path": str(path),
                "timestamp": datetime.now().isoformat(),
                "target": event.target_name,
                "value": event.value,
            })

    def _take_manual_screenshot(self) -> None:
        """Capture a screenshot immediately via hotkey."""
        frame = self._grab_frame()
        if frame is None:
            self._event_bus.publish(EVENT_CAPTURE_ERROR,
                                    {"error": "No game frame available for screenshot"})
            return

        path = build_screenshot_path(
            base_dir=self._config.screenshot_directory,
            daily_subfolder=self._config.screenshot_daily_subfolder,
        )

        ok = save_screenshot(frame, path, self._config.capture_blur_regions)
        if ok:
            self._event_bus.publish(EVENT_SCREENSHOT_SAVED, {
                "path": str(path),
                "timestamp": datetime.now().isoformat(),
            })
            log.info("Manual screenshot saved: %s", path)

    def _grab_frame(self) -> np.ndarray | None:
        """Grab a single frame from the game window.

        Uses the FrameDistributor's cached frame if available,
        otherwise captures directly.
        """
        # Try the distributor's cached frame first
        frame = self._frame_distributor.get_latest_frame()
        if frame is not None:
            return frame

        # Direct capture fallback
        hwnd = self._frame_distributor.game_hwnd
        if hwnd is None:
            hwnd = _platform.find_window_by_title_prefix(GAME_TITLE_PREFIX)
        if hwnd is None:
            return None

        capturer = self._capturer or self._frame_distributor.capturer
        geo = _platform.get_window_geometry(hwnd)
        return capturer.capture_window(hwnd, geometry=geo)

    # ------------------------------------------------------------------
    # Video clip actions
    # ------------------------------------------------------------------

    def _save_global_clip(self, event) -> None:
        """Save a video clip after an own-global event (called after post-delay)."""
        self._pending_clip_timer = None
        self._do_save_clip(
            target_name=event.target_name,
            amount=event.value,
            timestamp=event.timestamp if hasattr(event, "timestamp") else None,
        )

    def _save_manual_clip(self) -> None:
        """Save a video clip immediately via hotkey."""
        self._do_save_clip()
        log.info("Manual clip save triggered")

    def _do_save_clip(
        self,
        target_name: str = "",
        amount: float = 0.0,
        timestamp: datetime | None = None,
    ) -> None:
        """Snapshot the buffer and encode a clip in a background thread."""
        frames = self._frame_buffer.snapshot()
        if not frames:
            self._event_bus.publish(EVENT_CAPTURE_ERROR,
                                    {"error": "No frames in buffer for clip"})
            return

        # Snapshot audio if available
        audio_data = None
        if self._audio_buffer:
            start_time = frames[0][0]
            end_time = frames[-1][0]
            audio_data = self._audio_buffer.snapshot(start_time, end_time)

        # Build output path
        ts = timestamp or datetime.now()
        base = Path(self._config.clip_directory or DEFAULT_CLIP_DIR)
        if self._config.clip_daily_subfolder:
            base = base / ts.strftime("%Y-%m-%d")

        from .screenshot import _sanitize_filename
        ts_str = ts.strftime(FILENAME_TIMESTAMP_FMT)
        parts = [ts_str]
        if target_name:
            parts.append(_sanitize_filename(target_name))
        if amount > 0:
            parts.append(f"{amount:.2f}")
        filename = "_".join(parts) + ".mp4"
        output_path = base / filename

        # Webcam frames
        webcam_frame = None
        if self._webcam_capture:
            webcam_frame = self._webcam_capture.get_latest_frame()

        # Encode in background thread
        threading.Thread(
            target=self._encode_clip,
            args=(frames, audio_data, webcam_frame, output_path),
            daemon=True,
            name="clip-encode",
        ).start()

    def _encode_clip(
        self,
        frames: list[tuple[float, bytes]],
        audio_data,
        webcam_frame,
        output_path: Path,
    ) -> None:
        """Encode a clip via FFmpeg (runs in background thread)."""
        try:
            from .clip_writer import write_clip

            duration = frames[-1][0] - frames[0][0] if len(frames) > 1 else 0

            write_clip(
                frames=frames,
                audio_pcm=audio_data,
                webcam_frame=webcam_frame,
                output_path=output_path,
                fps=self._config.clip_fps,
                resolution=self._config.clip_resolution,
                bitrate=self._config.clip_bitrate,
                blur_regions=self._config.capture_blur_regions,
                audio_filters={
                    "noise_suppression": self._config.clip_audio_noise_suppression,
                    "noise_gate": self._config.clip_audio_noise_gate,
                    "compressor": self._config.clip_audio_compressor,
                },
                webcam_position=self._config.clip_webcam_position,
                ffmpeg_path=self._config.ffmpeg_path,
            )

            self._event_bus.publish(EVENT_CLIP_SAVED, {
                "path": str(output_path),
                "duration": duration,
                "frames": len(frames),
            })
            log.info("Clip saved: %s (%.1fs, %d frames)",
                     output_path, duration, len(frames))
        except Exception as e:
            log.error("Failed to encode clip: %s", e)
            self._event_bus.publish(EVENT_CAPTURE_ERROR, {"error": str(e)})
