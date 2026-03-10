"""Capture manager — orchestrates screenshot and video clip capture.

Subscribes to globals/hotkeys, manages the rolling frame buffer,
and triggers screenshot/clip saves on own-global or manual hotkey.

Uses the shared FrameDistributor for capture (boost mode) so only
one capture thread serves both OCR detectors and video recording.
"""

import copy
import os
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.constants import (
    EVENT_AUTH_STATE_CHANGED,
    EVENT_CAPTURE_ERROR,
    EVENT_CLIP_ENCODING_PROGRESS,
    EVENT_CLIP_ENCODING_STARTED,
    EVENT_CLIP_SAVED,
    EVENT_CONFIG_CHANGED,
    EVENT_GLOBAL,
    EVENT_HOTKEY_TRIGGERED,
    EVENT_OBS_CONNECTED,
    EVENT_OWN_GLOBAL,
    EVENT_RECORDING_STARTED,
    EVENT_RECORDING_STOPPED,
    EVENT_SCREENSHOT_SAVED,
    GAME_TITLE_PREFIX,
)
from ..core.logger import get_logger
from ..ocr.capturer import resolve_clip_backend
from ..platform import backend as _platform
from .constants import (
    BITRATE_TABLE,
    DEFAULT_CLIP_DIR,
    DEFAULT_SCREENSHOT_DIR,
    FILENAME_TIMESTAMP_FMT,
    RESOLUTION_PRESETS,
    get_ffmpeg_scale_flag,
    get_interpolation,
)
from .ffmpeg import ensure_ffmpeg
from .frame_buffer import FrameBuffer
from .screenshot import (
    apply_blur_regions, build_screenshot_path, compose_on_background,
    load_background_image, save_screenshot,
)

log = get_logger("CaptureManager")


class CaptureManager:
    """Central coordinator for screenshot and video clip capture.

    Uses the shared FrameDistributor in boost mode (not foreground-gated,
    WGC preferred) so video buffer records even when the game is behind
    other windows without a second capture thread.
    """

    def __init__(self, *, config, event_bus, frame_distributor, oauth):
        self._config = config
        self._event_bus = event_bus
        self._frame_distributor = frame_distributor
        self._oauth = oauth

        self._eu_name: str | None = None
        self._running = False
        self._frame_sub = None  # FrameSubscription for video buffer

        # Frame buffer for video clips
        self._frame_buffer = FrameBuffer(
            max_seconds=config.clip_buffer_seconds,
            fps=config.clip_fps,
        )

        # Audio / webcam / mic (initialized later when clip features are built)
        self._audio_buffer = None
        self._mic_buffer = None
        self._webcam_capture = None

        # Pending clip save: when an own-global triggers a clip, we continue
        # buffering for post_global_seconds before saving.
        self._pending_clip_timer: threading.Timer | None = None

        # Cooldown tracking (monotonic timestamps of last auto-capture)
        self._last_auto_screenshot: float = 0.0
        self._last_auto_clip: float = 0.0

        # OBS integration (initialized on demand)
        self._obs_client = None  # capture.obs_client.OBSClient | None
        self._prev_obs_enabled = config.obs_enabled
        self._obs_game_poll_timer: threading.Timer | None = None
        self._obs_game_was_running = False

        # Continuous recording state
        self._recording = False
        self._rec_proc: subprocess.Popen | None = None
        self._rec_start: float = 0
        self._rec_frame_size: tuple[int, int] = (0, 0)
        self._rec_compose_bg = False
        self._rec_output: Path | None = None
        self._rec_temp_video: Path | None = None
        self._rec_ffmpeg: str = ""
        self._rec_frame_count = 0
        self._rec_fps: int = 30
        self._rec_audio_lock = threading.Lock()
        self._rec_game_chunks: list[np.ndarray] = []
        self._rec_mic_chunks: list[np.ndarray] = []
        self._rec_last_drain: float = 0
        self._rec_audio_stop: threading.Event | None = None
        self._rec_audio_thread: threading.Thread | None = None
        self._rec_stderr_chunks: list[bytes] = []
        self._rec_stderr_thread: threading.Thread | None = None
        self._rec_write_queue = None
        self._rec_writer_thread: threading.Thread | None = None
        self._rec_cfg: dict = {}
        self._rec_bg: np.ndarray | None = None

        # Background image for compositing (loaded lazily)
        self._background: np.ndarray | None = None
        self._load_background()

        # Snapshot of buffer-affecting settings for change detection
        self._prev_obs_enabled = config.obs_enabled
        self._prev_clip_enabled = config.clip_enabled
        self._prev_clip_fps = config.clip_fps
        self._prev_clip_buffer_seconds = config.clip_buffer_seconds
        self._prev_clip_webcam_enabled = config.clip_webcam_enabled
        self._prev_clip_webcam_device = config.clip_webcam_device
        self._prev_clip_webcam_fps = config.clip_webcam_fps
        self._prev_clip_webcam_keep_ready = config.clip_webcam_keep_ready
        self._prev_clip_audio_enabled = config.clip_audio_enabled
        self._prev_clip_audio_device = config.clip_audio_device
        self._prev_clip_mic_enabled = config.clip_mic_enabled
        self._prev_clip_mic_device = config.clip_mic_device
        self._prev_capture_bg = getattr(config, "capture_preview_background", "")

        # Track auth state for own-global detection
        if oauth and hasattr(oauth, "auth_state"):
            self._eu_name = getattr(oauth.auth_state, "eu_name", None)

        # Subscribe to events
        self._event_bus.subscribe(EVENT_GLOBAL, self._on_global)
        self._event_bus.subscribe(EVENT_AUTH_STATE_CHANGED, self._on_auth_changed)
        self._event_bus.subscribe(EVENT_HOTKEY_TRIGGERED, self._on_hotkey)
        self._event_bus.subscribe(EVENT_CONFIG_CHANGED, self._on_config_changed)
        self._event_bus.subscribe(EVENT_OBS_CONNECTED, self._on_obs_connected)

    def _load_background(self) -> None:
        """Load the configured background image for compositing."""
        path = getattr(self._config, "capture_preview_background", "")
        self._background = load_background_image(path) if path else None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the capture manager and subscribe to the frame distributor."""
        if self._running:
            return
        self._running = True

        if self._config.clip_enabled and self._config.obs_enabled:
            # OBS mode — no internal frame/audio/webcam capture
            self._start_obs()
        elif self._config.clip_enabled:
            # Internal capture mode
            self._start_frame_subscription()
            self._start_audio()
            self._start_mic()
            self._start_webcam()
        elif self._config.clip_webcam_keep_ready and self._config.clip_webcam_enabled:
            self._start_webcam()

        log.info("Capture manager started (screenshot=%s, clip=%s, obs=%s)",
                    self._config.screenshot_enabled, self._config.clip_enabled,
                    self._config.obs_enabled)

    def stop(self) -> None:
        """Stop the capture manager and clean up subscriptions."""
        self._running = False

        if self._recording:
            self._stop_recording()

        if self._pending_clip_timer:
            self._pending_clip_timer.cancel()
            self._pending_clip_timer = None

        self._stop_obs()
        self._stop_frame_subscription()
        self._stop_audio()
        self._stop_mic()
        self._stop_webcam()
        self._frame_buffer.clear()

        log.info("Capture manager stopped")

    # ------------------------------------------------------------------
    # Frame subscription (via FrameDistributor boost mode)
    # ------------------------------------------------------------------

    def _start_frame_subscription(self) -> None:
        """Subscribe to the frame distributor with boost for video buffering."""
        fps = max(1, self._config.clip_fps)
        pref = getattr(self._config, "clip_capture_backend", "auto")
        clip_backend = resolve_clip_backend(pref, fps)
        log.info("Video capture ready (backend=%s, fps=%d)", clip_backend, fps)
        self._frame_distributor.boost(
            "capture_manager", min_hz=fps, capture_backend=clip_backend,
        )
        self._frame_sub = self._frame_distributor.subscribe(
            "capture-buffer", self._on_capture_frame, hz=fps,
        )

    def _stop_frame_subscription(self) -> None:
        """Unsubscribe from the frame distributor and remove boost."""
        if self._frame_sub is not None:
            self._frame_distributor.unsubscribe(self._frame_sub)
            self._frame_sub = None
        self._frame_distributor.unboost("capture_manager")

    def _on_capture_frame(self, frame: np.ndarray, timestamp: float) -> None:
        """Callback from FrameDistributor — push frame into the rolling buffer."""
        webcam_frame = None
        wc = self._webcam_capture  # snapshot ref (main thread may set to None)
        if wc is not None:
            webcam_frame = wc.get_latest_frame()
        self._frame_buffer.push(frame, timestamp, webcam_frame)
        if self._recording:
            self._write_recording_frame(frame.copy())

    # ------------------------------------------------------------------
    # OBS integration
    # ------------------------------------------------------------------

    def _start_obs(self) -> None:
        """Initialize OBS WebSocket connection."""
        from .obs_client import OBSClient
        self._obs_client = OBSClient(
            event_bus=self._event_bus,
            config=self._config,
        )
        connected = self._obs_client.connect()
        if not connected:
            log.warning("OBS connection failed — will retry in background")

        # Start game window polling for replay buffer management
        if self._config.obs_manage_replay_buffer:
            self._start_obs_game_poll()
            # Start replay buffer immediately if game is already running
            if connected and self._frame_distributor.game_hwnd:
                self._obs_game_was_running = True
                self._obs_client.start_replay_buffer()

    def _stop_obs(self) -> None:
        """Disconnect from OBS."""
        self._stop_obs_game_poll()
        if self._obs_client:
            if self._config.obs_manage_replay_buffer:
                self._obs_client.stop_replay_buffer()
            self._obs_client.disconnect()
            self._obs_client = None

    # ------------------------------------------------------------------
    # OBS game window polling (replay buffer lifecycle)
    # ------------------------------------------------------------------

    _OBS_GAME_POLL_S = 3.0

    def _start_obs_game_poll(self) -> None:
        """Start periodic polling for game window presence."""
        self._obs_game_was_running = self._frame_distributor.game_hwnd is not None
        self._obs_game_poll_tick()

    def _stop_obs_game_poll(self) -> None:
        if self._obs_game_poll_timer:
            self._obs_game_poll_timer.cancel()
            self._obs_game_poll_timer = None

    def _obs_game_poll_tick(self) -> None:
        """Check if game window appeared or disappeared."""
        if not self._running or not self._obs_client:
            return
        game_running = self._frame_distributor.game_hwnd is not None
        if game_running and not self._obs_game_was_running:
            log.info("Game detected — starting OBS replay buffer")
            self._obs_client.start_replay_buffer()
        elif not game_running and self._obs_game_was_running:
            log.info("Game closed — stopping OBS replay buffer")
            self._obs_client.stop_replay_buffer()
        self._obs_game_was_running = game_running

        # Schedule next tick
        self._obs_game_poll_timer = threading.Timer(
            self._OBS_GAME_POLL_S, self._obs_game_poll_tick,
        )
        self._obs_game_poll_timer.daemon = True
        self._obs_game_poll_timer.start()

    def _on_obs_connected(self, _data) -> None:
        """Handle OBS (re)connection — start replay buffer if game is running."""
        if not self._obs_client or not self._config.obs_manage_replay_buffer:
            return
        if self._frame_distributor.game_hwnd:
            self._obs_game_was_running = True
            self._obs_client.start_replay_buffer()

    # ------------------------------------------------------------------
    # Audio (game/system audio via WASAPI loopback)
    # ------------------------------------------------------------------

    def _start_audio(self) -> None:
        """Start system audio capture (WASAPI loopback) if enabled."""
        if not self._config.clip_audio_enabled:
            return
        try:
            from .audio_buffer import AudioBuffer
            self._audio_buffer = AudioBuffer(
                device=self._config.clip_audio_device or None,
                loopback=True,
            )
            self._audio_buffer.start()
            dev_name = self._config.clip_audio_device or "default"
            log.info("System audio ready (device=%s)", dev_name)
        except Exception as e:
            log.warning("System audio capture unavailable: %s", e)
            self._audio_buffer = None

    def _stop_audio(self) -> None:
        if self._audio_buffer:
            self._audio_buffer.stop()
            self._audio_buffer = None

    # ------------------------------------------------------------------
    # Microphone
    # ------------------------------------------------------------------

    def _start_mic(self) -> None:
        """Start microphone capture if enabled."""
        if not self._config.clip_mic_enabled:
            return
        try:
            from .audio_buffer import AudioBuffer
            self._mic_buffer = AudioBuffer(
                device=self._config.clip_mic_device or None,
                loopback=False,
            )
            self._mic_buffer.start()
            dev_name = self._config.clip_mic_device or "default"
            log.info("Microphone ready (device=%s)", dev_name)
        except Exception as e:
            log.warning("Microphone capture unavailable: %s", e)
            self._mic_buffer = None

    def _stop_mic(self) -> None:
        if self._mic_buffer:
            self._mic_buffer.stop()
            self._mic_buffer = None

    # ------------------------------------------------------------------
    # Webcam
    # ------------------------------------------------------------------

    def _start_webcam(self) -> None:
        """Start webcam capture if enabled."""
        if not self._config.clip_webcam_enabled:
            return
        if self._webcam_capture:
            return  # already running
        try:
            from .webcam_capture import WebcamCapture
            self._webcam_capture = WebcamCapture(
                device=self._config.clip_webcam_device,
                fps=self._config.clip_webcam_fps or self._config.clip_fps,
            )
            self._webcam_capture.start()
            WebcamCapture._active_instance = self._webcam_capture
            WebcamCapture.discover_devices_async()
            log.info("Webcam ready (device=%s)", self._config.clip_webcam_device)
        except Exception as e:
            log.warning("Webcam capture unavailable: %s", e)
            self._webcam_capture = None

    def _release_webcam_if_not_needed(self) -> None:
        """Stop the webcam unless keep-ready mode wants it to stay running."""
        if self._config.clip_webcam_keep_ready and self._config.clip_webcam_enabled:
            return  # keep running for instant availability
        self._stop_webcam()

    def _stop_webcam(self) -> None:
        if self._webcam_capture:
            from .webcam_capture import WebcamCapture
            if WebcamCapture._active_instance is self._webcam_capture:
                WebcamCapture._active_instance = None
            self._webcam_capture.stop()
            self._webcam_capture = None

    # ------------------------------------------------------------------
    # Own-global detection
    # ------------------------------------------------------------------

    def _on_auth_changed(self, state) -> None:
        self._eu_name = getattr(state, "eu_name", None)

    # ------------------------------------------------------------------
    # Live reconfiguration on settings change
    # ------------------------------------------------------------------

    def _update_config_snapshot(self, cfg) -> None:
        """Update the stored snapshot of buffer-affecting config values."""
        self._prev_obs_enabled = cfg.obs_enabled
        self._prev_clip_enabled = cfg.clip_enabled
        self._prev_clip_fps = cfg.clip_fps
        self._prev_clip_buffer_seconds = cfg.clip_buffer_seconds
        self._prev_clip_webcam_enabled = cfg.clip_webcam_enabled
        self._prev_clip_webcam_device = cfg.clip_webcam_device
        self._prev_clip_webcam_fps = cfg.clip_webcam_fps
        self._prev_clip_webcam_keep_ready = cfg.clip_webcam_keep_ready
        self._prev_clip_audio_enabled = cfg.clip_audio_enabled
        self._prev_clip_audio_device = cfg.clip_audio_device
        self._prev_clip_mic_enabled = cfg.clip_mic_enabled
        self._prev_clip_mic_device = cfg.clip_mic_device
        self._prev_capture_bg = getattr(cfg, "capture_preview_background", "")

    def _on_config_changed(self, config) -> None:
        """Reconfigure capture buffers when video settings change.

        Only restarts the components whose settings actually changed.
        Skips reconfiguration during active continuous recording.
        """
        if not self._running:
            self._update_config_snapshot(config)
            return

        # Never reconfigure during active recording — would corrupt output
        obs_rec = self._obs_client and self._obs_client.is_recording()
        if self._recording or obs_rec:
            log.debug("Config changed during recording; deferring buffer reconfigure")
            self._update_config_snapshot(config)
            return

        cfg = config

        # --- obs_enabled toggle (requires clip_enabled as master gate) ---
        if cfg.obs_enabled != self._prev_obs_enabled:
            if cfg.obs_enabled and cfg.clip_enabled:
                log.info("OBS mode enabled — stopping internal capture")
                if self._pending_clip_timer:
                    self._pending_clip_timer.cancel()
                    self._pending_clip_timer = None
                self._stop_frame_subscription()
                self._stop_audio()
                self._stop_mic()
                self._release_webcam_if_not_needed()
                self._frame_buffer.clear()
                self._start_obs()
            else:
                log.info("OBS mode disabled — stopping OBS client")
                self._stop_obs()
                if cfg.clip_enabled:
                    self._start_frame_subscription()
                    self._start_audio()
                    self._start_mic()
                    self._start_webcam()
                elif cfg.clip_webcam_keep_ready and cfg.clip_webcam_enabled:
                    self._start_webcam()
            self._update_config_snapshot(config)
            return

        # --- clip_enabled toggle (master gate for all capture) ---
        if cfg.clip_enabled != self._prev_clip_enabled:
            if cfg.clip_enabled:
                if cfg.obs_enabled:
                    log.info("Clip recording enabled — starting OBS mode")
                    self._start_obs()
                else:
                    log.info("Clip recording enabled — starting internal capture")
                    self._start_frame_subscription()
                    self._start_audio()
                    self._start_mic()
                    self._start_webcam()
            else:
                log.info("Clip recording disabled — stopping all capture")
                if self._pending_clip_timer:
                    self._pending_clip_timer.cancel()
                    self._pending_clip_timer = None
                self._stop_obs()
                self._stop_frame_subscription()
                self._stop_audio()
                self._stop_mic()
                self._release_webcam_if_not_needed()
                self._frame_buffer.clear()
            self._update_config_snapshot(config)
            return

        # If OBS mode is active, handle OBS-specific config changes
        if cfg.clip_enabled and cfg.obs_enabled:
            if self._obs_client and self._obs_client.connected:
                new_dir = cfg.clip_directory
                if new_dir:
                    self._obs_client.update_record_directory(new_dir)
                if cfg.clip_buffer_seconds != self._prev_clip_buffer_seconds:
                    self._obs_client.update_replay_buffer_duration(
                        cfg.clip_buffer_seconds,
                    )

            # Replay buffer management toggled
            if cfg.obs_manage_replay_buffer and not self._obs_game_poll_timer:
                self._start_obs_game_poll()
                if self._obs_client and self._obs_client.connected \
                        and self._frame_distributor.game_hwnd:
                    self._obs_client.start_replay_buffer()
            elif not cfg.obs_manage_replay_buffer and self._obs_game_poll_timer:
                self._stop_obs_game_poll()

            self._update_config_snapshot(config)
            return

        # If clips are not enabled, handle keep-ready webcam changes only
        if not cfg.clip_enabled:
            self._handle_webcam_keep_ready_change(cfg)
            self._update_config_snapshot(config)
            return

        # --- Frame buffer: FPS or buffer duration changed ---
        fps_changed = cfg.clip_fps != self._prev_clip_fps
        buf_changed = cfg.clip_buffer_seconds != self._prev_clip_buffer_seconds

        if fps_changed or buf_changed:
            log.info("Resizing frame buffer: %ds @ %dfps",
                     cfg.clip_buffer_seconds, cfg.clip_fps)
            self._frame_buffer.resize(cfg.clip_buffer_seconds, cfg.clip_fps)

        if fps_changed:
            log.info("FPS changed %d -> %d, restarting frame subscription",
                     self._prev_clip_fps, cfg.clip_fps)
            self._stop_frame_subscription()
            self._start_frame_subscription()

        # --- Webcam ---
        webcam_toggled = cfg.clip_webcam_enabled != self._prev_clip_webcam_enabled
        webcam_dev_changed = cfg.clip_webcam_device != self._prev_clip_webcam_device
        webcam_fps_changed = cfg.clip_webcam_fps != self._prev_clip_webcam_fps

        if webcam_toggled:
            if cfg.clip_webcam_enabled:
                log.info("Webcam enabled")
                self._start_webcam()
            else:
                log.info("Webcam disabled")
                self._stop_webcam()
        elif cfg.clip_webcam_enabled and (webcam_dev_changed or webcam_fps_changed):
            log.info("Webcam settings changed — restarting webcam capture")
            self._stop_webcam()
            self._start_webcam()

        # --- System audio ---
        audio_toggled = cfg.clip_audio_enabled != self._prev_clip_audio_enabled
        audio_dev_changed = cfg.clip_audio_device != self._prev_clip_audio_device

        if audio_toggled:
            if cfg.clip_audio_enabled:
                log.info("System audio enabled")
                self._start_audio()
            else:
                log.info("System audio disabled")
                self._stop_audio()
        elif cfg.clip_audio_enabled and audio_dev_changed and self._audio_buffer:
            log.info("Audio device changed — switching device")
            self._audio_buffer.set_device(cfg.clip_audio_device or None)

        # --- Microphone ---
        mic_toggled = cfg.clip_mic_enabled != self._prev_clip_mic_enabled
        mic_dev_changed = cfg.clip_mic_device != self._prev_clip_mic_device

        if mic_toggled:
            if cfg.clip_mic_enabled:
                log.info("Microphone enabled")
                self._start_mic()
            else:
                log.info("Microphone disabled")
                self._stop_mic()
        elif cfg.clip_mic_enabled and mic_dev_changed and self._mic_buffer:
            log.info("Mic device changed — switching device")
            self._mic_buffer.set_device(cfg.clip_mic_device or None)

        # --- Background image ---
        bg_path = getattr(cfg, "capture_preview_background", "")
        if bg_path != self._prev_capture_bg:
            log.info("Background image changed — reloading")
            self._load_background()

        self._update_config_snapshot(config)

    def _handle_webcam_keep_ready_change(self, cfg) -> None:
        """Handle webcam keep-ready changes while clips are disabled.

        Keep-ready actively captures frames so the camera is warm and
        instantly available via _active_instance when recording starts.
        """
        keep_ready = cfg.clip_webcam_keep_ready and cfg.clip_webcam_enabled
        was_keep_ready = self._prev_clip_webcam_keep_ready and self._prev_clip_webcam_enabled

        webcam_dev_changed = cfg.clip_webcam_device != self._prev_clip_webcam_device
        webcam_fps_changed = cfg.clip_webcam_fps != self._prev_clip_webcam_fps

        if keep_ready and not was_keep_ready:
            self._start_webcam()
        elif not keep_ready and was_keep_ready:
            self._stop_webcam()
        elif keep_ready and (webcam_dev_changed or webcam_fps_changed):
            self._stop_webcam()
            self._start_webcam()

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

    def _check_conditions(
        self,
        event,
        min_ped: float,
        global_types: list[str],
        hof_only: bool,
        cooldown_s: float,
        last_time: float,
    ) -> bool:
        """Return True if *event* satisfies the configured conditions."""
        # HoF filter
        if hof_only and not event.is_hof:
            return False

        # Global type filter (empty list = all types accepted)
        if global_types:
            gt_val = (event.global_type.value
                      if hasattr(event.global_type, "value")
                      else str(event.global_type))
            if gt_val not in global_types:
                return False

        # Min PED filter — skip for types where value is optional/absent
        _VALUE_OPTIONAL = {"discovery", "tier", "rare_item", "pvp"}
        if min_ped > 0:
            gt_val = (event.global_type.value
                      if hasattr(event.global_type, "value")
                      else str(event.global_type))
            if gt_val not in _VALUE_OPTIONAL:
                if event.value < min_ped:
                    return False

        # Cooldown
        if cooldown_s > 0 and last_time > 0:
            elapsed = time.monotonic() - last_time
            if elapsed < cooldown_s:
                return False

        return True

    def _on_global(self, event) -> None:
        """Handle a global event — trigger capture if it's our own."""
        if not self._is_own_global(event.player_name):
            return

        log.info("Own global detected: %s killed %s for %.2f PED",
                 event.player_name, event.target_name, event.value)
        self._event_bus.publish(EVENT_OWN_GLOBAL, event)

        cfg = self._config

        # Screenshot
        if cfg.screenshot_enabled and cfg.screenshot_auto_on_global:
            if self._check_conditions(
                event,
                min_ped=cfg.screenshot_min_ped,
                global_types=cfg.screenshot_global_types,
                hof_only=cfg.screenshot_hof_only,
                cooldown_s=cfg.screenshot_cooldown_s,
                last_time=self._last_auto_screenshot,
            ):
                self._last_auto_screenshot = time.monotonic()
                delay = cfg.screenshot_delay_s
                threading.Timer(
                    delay,
                    self._take_global_screenshot,
                    args=(event,),
                ).start()

        # Video clip (internal or OBS — clip_enabled is the master gate)
        if cfg.clip_enabled and cfg.clip_auto_on_global:
            if self._check_conditions(
                event,
                min_ped=cfg.clip_min_ped,
                global_types=cfg.clip_global_types,
                hof_only=cfg.clip_hof_only,
                cooldown_s=cfg.clip_cooldown_s,
                last_time=self._last_auto_clip,
            ):
                global_mono = time.monotonic()
                self._last_auto_clip = global_mono
                post_seconds = cfg.clip_post_global_seconds
                # Cancel any pending clip save (e.g. rapid successive globals)
                if self._pending_clip_timer:
                    self._pending_clip_timer.cancel()
                if cfg.obs_enabled:
                    self._pending_clip_timer = threading.Timer(
                        post_seconds,
                        self._save_global_clip_obs,
                        args=(event,),
                    )
                else:
                    self._pending_clip_timer = threading.Timer(
                        post_seconds,
                        self._save_global_clip,
                        args=(event, global_mono),
                    )
                self._pending_clip_timer.start()

    def _on_hotkey(self, data) -> None:
        """Handle hotkey events for manual screenshot/clip."""
        if isinstance(data, str):
            action = data
        elif isinstance(data, dict):
            action = data.get("action")
        else:
            action = getattr(data, "action", None)
        if action == "screenshot":
            self._take_manual_screenshot()
        elif action == "save_clip":
            if not self._config.clip_enabled:
                return
            if self._config.obs_enabled:
                self._save_manual_clip_obs()
            else:
                self._save_manual_clip()
        elif action == "toggle_recording":
            if not self._config.clip_enabled:
                return
            if self._config.obs_enabled:
                self._toggle_recording_obs()
            elif self._recording:
                self._stop_recording()
            else:
                self._start_recording()

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

        ok = save_screenshot(
            frame, path, self._config.capture_blur_regions,
            background=self._background,
            target_resolution=RESOLUTION_PRESETS.get(self._config.clip_resolution),
            size_pct=self._config.screenshot_size_pct,
            scaling=getattr(self._config, "clip_scaling", "lanczos"),
        )
        if ok:
            gt = event.global_type
            gt_str = gt.value if hasattr(gt, "value") else str(gt)
            self._event_bus.publish(EVENT_SCREENSHOT_SAVED, {
                "path": str(path),
                "timestamp": datetime.now().isoformat(),
                "target": event.target_name,
                "value": event.value,
                "global_event": {
                    "global_type": gt_str,
                    "player_name": event.player_name,
                    "target_name": event.target_name,
                    "value": event.value,
                    "is_hof": event.is_hof,
                    "is_ath": event.is_ath,
                },
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

        ok = save_screenshot(
            frame, path, self._config.capture_blur_regions,
            background=self._background,
            target_resolution=RESOLUTION_PRESETS.get(self._config.clip_resolution),
            size_pct=self._config.screenshot_size_pct,
            scaling=getattr(self._config, "clip_scaling", "lanczos"),
        )
        if ok:
            self._event_bus.publish(EVENT_SCREENSHOT_SAVED, {
                "path": str(path),
                "timestamp": datetime.now().isoformat(),
            })
            log.info("Manual screenshot saved: %s", path)

    def _grab_frame(self) -> np.ndarray | None:
        """Force-capture a fresh frame from the game window.

        Always captures on demand rather than using the distributor's
        cached frame, which may be stale (e.g. 250ms old at 4 Hz OCR).
        """
        hwnd = self._frame_distributor.game_hwnd
        if hwnd is None:
            hwnd = _platform.find_window_by_title_prefix(GAME_TITLE_PREFIX)
        if hwnd is None:
            return None

        geo = _platform.get_window_geometry(hwnd)
        return self._frame_distributor.capturer.capture_window(hwnd, geometry=geo)

    # ------------------------------------------------------------------
    # Video clip actions
    # ------------------------------------------------------------------

    def _save_global_clip(self, event, global_mono: float = 0) -> None:
        """Save a video clip after an own-global event (called after post-delay)."""
        self._pending_clip_timer = None
        gt = event.global_type
        gt_str = gt.value if hasattr(gt, "value") else str(gt)
        self._do_save_clip(
            target_name=event.target_name,
            amount=event.value,
            timestamp=event.timestamp if hasattr(event, "timestamp") else None,
            global_event={
                "global_type": gt_str,
                "player_name": event.player_name,
                "target_name": event.target_name,
                "value": event.value,
                "is_hof": event.is_hof,
                "is_ath": event.is_ath,
            },
            thumb_time=global_mono + 1.0 if global_mono else 0,
        )

    def _save_manual_clip(self) -> None:
        """Save a video clip immediately via hotkey."""
        self._do_save_clip()
        log.info("Manual clip save triggered")

    # ------------------------------------------------------------------
    # OBS clip / recording actions
    # ------------------------------------------------------------------

    def _save_global_clip_obs(self, event) -> None:
        """Trigger OBS replay buffer save for an own-global."""
        self._pending_clip_timer = None
        if not self._obs_client or not self._obs_client.connected:
            self._event_bus.publish(EVENT_CAPTURE_ERROR,
                                    {"error": "OBS not connected — clip not saved"})
            return
        gt = event.global_type
        gt_str = gt.value if hasattr(gt, "value") else str(gt)
        self._obs_client.save_replay_buffer(global_event={
            "global_type": gt_str,
            "player_name": event.player_name,
            "target_name": event.target_name,
            "value": event.value,
            "is_hof": event.is_hof,
            "is_ath": event.is_ath,
        })

    def _save_manual_clip_obs(self) -> None:
        """Trigger OBS replay buffer save (manual hotkey)."""
        if not self._obs_client or not self._obs_client.connected:
            self._event_bus.publish(EVENT_CAPTURE_ERROR,
                                    {"error": "OBS not connected"})
            return
        self._obs_client.save_replay_buffer()
        log.info("Manual OBS clip save triggered")

    def _toggle_recording_obs(self) -> None:
        """Toggle OBS recording via WebSocket."""
        if not self._obs_client or not self._obs_client.connected:
            self._event_bus.publish(EVENT_CAPTURE_ERROR,
                                    {"error": "OBS not connected"})
            return
        if self._obs_client.is_recording():
            self._obs_client.stop_record()
        else:
            self._obs_client.start_record()

    # ------------------------------------------------------------------
    # Internal clip encoding
    # ------------------------------------------------------------------

    def _do_save_clip(
        self,
        target_name: str = "",
        amount: float = 0.0,
        timestamp: datetime | None = None,
        global_event: dict | None = None,
        thumb_time: float = 0,
    ) -> None:
        """Snapshot the buffer and encode a clip in a background thread."""
        frames = self._frame_buffer.snapshot()
        if not frames:
            self._event_bus.publish(EVENT_CAPTURE_ERROR,
                                    {"error": "No frames in buffer for clip"})
            return

        # Snapshot audio if available
        start_time = frames[0][0]
        end_time = frames[-1][0]

        audio_data = None
        if self._audio_buffer:
            audio_data = self._audio_buffer.snapshot(start_time, end_time)

        mic_data = None
        if self._mic_buffer:
            mic_data = self._mic_buffer.snapshot(start_time, end_time)

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

        # Snapshot config on the main thread so the encode thread doesn't
        # race with live settings changes.
        cfg = self._config
        clip_cfg = {
            "fps": cfg.clip_fps,
            "resolution": cfg.clip_resolution,
            "bitrate": cfg.clip_bitrate,
            "blur_regions": copy.deepcopy(cfg.capture_blur_regions),
            "mic_filters": {
                "noise_suppression": cfg.clip_audio_noise_suppression,
                "noise_gate": cfg.clip_audio_noise_gate,
                "compressor": cfg.clip_audio_compressor,
                "ns_mix": cfg.clip_audio_ns_mix,
                "gate_threshold": cfg.clip_audio_gate_threshold,
                "gate_ratio": cfg.clip_audio_gate_ratio,
                "gate_attack": cfg.clip_audio_gate_attack,
                "gate_release": cfg.clip_audio_gate_release,
                "comp_threshold": cfg.clip_audio_comp_threshold,
                "comp_ratio": cfg.clip_audio_comp_ratio,
                "comp_attack": cfg.clip_audio_comp_attack,
                "comp_release": cfg.clip_audio_comp_release,
            },
            "webcam_position_x": cfg.clip_webcam_position_x,
            "webcam_position_y": cfg.clip_webcam_position_y,
            "webcam_scale": cfg.clip_webcam_scale,
            "webcam_crop": {
                "x": cfg.clip_webcam_crop_x,
                "y": cfg.clip_webcam_crop_y,
                "w": cfg.clip_webcam_crop_w,
                "h": cfg.clip_webcam_crop_h,
            },
            "webcam_chroma": {
                "enabled": cfg.clip_webcam_chroma_enabled,
                "color": cfg.clip_webcam_chroma_color,
                "threshold": cfg.clip_webcam_chroma_threshold,
                "smoothing": cfg.clip_webcam_chroma_smoothing,
            },
            "ffmpeg_path": cfg.ffmpeg_path,
            "game_gain": cfg.clip_audio_game_gain,
            "mic_gain": cfg.clip_audio_mic_gain,
            "scaling": getattr(cfg, "clip_scaling", "lanczos"),
        }

        # Encode in background thread (webcam frames are stored per-frame in the buffer)
        threading.Thread(
            target=self._encode_clip,
            args=(frames, audio_data, mic_data, output_path, global_event,
                  thumb_time, clip_cfg),
            daemon=True,
            name="clip-encode",
        ).start()

    def _encode_clip(
        self,
        frames: list[tuple[float, bytes, bytes | None]],
        audio_data,
        mic_data,
        output_path: Path,
        global_event: dict | None = None,
        thumb_time: float = 0,
        clip_cfg: dict | None = None,
    ) -> None:
        """Encode a clip via FFmpeg (runs in background thread).

        *clip_cfg* is a config snapshot taken on the main thread so we
        don't read mutable Config attributes from this background thread.
        """
        path_str = str(output_path)
        total_frames = len(frames)

        self._event_bus.publish(EVENT_CLIP_ENCODING_STARTED, {
            "path": path_str,
            "frames": total_frames,
        })

        _last_pct = -1

        def _on_progress(written: int, total: int) -> None:
            nonlocal _last_pct
            pct = int(written * 100 / total) if total else 0
            if pct == _last_pct:
                return  # throttle: only emit on whole-percent changes
            _last_pct = pct
            self._event_bus.publish(EVENT_CLIP_ENCODING_PROGRESS, {
                "path": path_str,
                "written": written,
                "total": total,
            })

        try:
            from .clip_writer import write_clip

            duration = frames[-1][0] - frames[0][0] if len(frames) > 1 else 0
            c = clip_cfg or {}

            write_clip(
                frames=frames,
                audio_pcm=audio_data,
                output_path=output_path,
                fps=c.get("fps", 30),
                resolution=c.get("resolution", "source"),
                bitrate=c.get("bitrate", "medium"),
                blur_regions=c.get("blur_regions"),
                thumb_time=thumb_time,
                mic_filters=c.get("mic_filters"),
                webcam_position_x=c.get("webcam_position_x", 0.88),
                webcam_position_y=c.get("webcam_position_y", 0.85),
                webcam_scale=c.get("webcam_scale", 0.2),
                webcam_crop=c.get("webcam_crop"),
                webcam_chroma=c.get("webcam_chroma"),
                ffmpeg_path=c.get("ffmpeg_path", ""),
                mic_pcm=mic_data,
                game_gain=c.get("game_gain", 1.0),
                mic_gain=c.get("mic_gain", 1.0),
                background=self._background,
                scaling=c.get("scaling", "lanczos"),
                on_progress=_on_progress,
            )

            payload = {
                "path": path_str,
                "timestamp": datetime.now().isoformat(),
                "duration": duration,
                "frames": total_frames,
            }
            if global_event:
                payload["global_event"] = global_event
            self._event_bus.publish(EVENT_CLIP_SAVED, payload)
            log.info("Clip saved: %s (%.1fs, %d frames)",
                     output_path, duration, total_frames)
        except Exception as e:
            log.error("Failed to encode clip: %s", e)
            self._event_bus.publish(EVENT_CAPTURE_ERROR, {"error": str(e)})
            # Emit clip_saved so the gallery removes the encoding widget
            self._event_bus.publish(EVENT_CLIP_SAVED, {
                "path": path_str, "error": True,
            })

    # ------------------------------------------------------------------
    # Continuous recording (start/stop toggle)
    # ------------------------------------------------------------------

    @property
    def is_recording(self) -> bool:
        if self._obs_client and self._config.clip_enabled and self._config.obs_enabled:
            return self._obs_client.is_recording()
        return self._recording

    def _start_recording(self) -> None:
        """Begin continuous recording — pipe frames to FFmpeg in real-time."""
        if self._recording:
            return

        # Ensure capture infrastructure is running
        if not self._frame_sub:
            self._start_frame_subscription()
        if not self._audio_buffer and self._config.clip_audio_enabled:
            self._start_audio()
        if not self._mic_buffer and self._config.clip_mic_enabled:
            self._start_mic()
        if self._config.clip_webcam_enabled:
            self._start_webcam()

        # Determine frame dimensions from a live frame
        frame = self._grab_frame()
        if frame is None:
            self._event_bus.publish(EVENT_CAPTURE_ERROR,
                                    {"error": "Cannot start recording — no game frame"})
            return

        h, w = frame.shape[:2]
        target_res = RESOLUTION_PRESETS.get(self._config.clip_resolution)
        compose_bg = self._background is not None and target_res is not None
        if compose_bg:
            w, h = target_res

        # Find FFmpeg
        ffmpeg = ensure_ffmpeg(self._config.ffmpeg_path)
        if not ffmpeg:
            self._event_bus.publish(EVENT_CAPTURE_ERROR,
                                    {"error": "FFmpeg not found — cannot record"})
            return

        # Build output path
        ts = datetime.now()
        base = Path(self._config.clip_directory or DEFAULT_CLIP_DIR)
        if self._config.clip_daily_subfolder:
            base = base / ts.strftime("%Y-%m-%d")
        base.mkdir(parents=True, exist_ok=True)

        ts_str = ts.strftime(FILENAME_TIMESTAMP_FMT)
        self._rec_output = base / f"{ts_str}_recording.mp4"
        self._rec_temp_video = base / f".{ts_str}_rec_tmp.mp4"

        # FFmpeg command — video-only, audio muxed on stop
        fps = max(1, self._config.clip_fps)
        bitrate_val = BITRATE_TABLE.get(
            (self._config.clip_resolution, self._config.clip_bitrate), "8M")

        cmd = [ffmpeg, "-y",
               "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{w}x{h}", "-r", str(fps),
               "-i", "pipe:0"]

        vf_parts = []
        if target_res and not compose_bg:
            tw, th = target_res
            scaling = getattr(self._config, "clip_scaling", "lanczos")
            vf_parts.append(
                f"scale='min({tw},iw)':'min({th},ih)'"
                f":force_original_aspect_ratio=decrease:flags={get_ffmpeg_scale_flag(scaling)}"
            )
            vf_parts.append(f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black")
        if vf_parts:
            cmd.extend(["-vf", ",".join(vf_parts)])

        cmd.extend(["-c:v", "libx264", "-preset", "fast",
                     "-b:v", bitrate_val, "-pix_fmt", "yuv420p",
                     "-an", str(self._rec_temp_video)])

        try:
            self._rec_proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
        except Exception as e:
            self._event_bus.publish(EVENT_CAPTURE_ERROR,
                                    {"error": f"Failed to start FFmpeg: {e}"})
            return

        # Drain stderr in background to prevent pipe-buffer deadlock
        # during long recordings where FFmpeg status output accumulates.
        # Only keep the tail (last ~64 KB) for error reporting.
        _REC_STDERR_MAX_CHUNKS = 16  # 16 × 4096 = 64 KB
        self._rec_stderr_chunks: list[bytes] = []

        def _drain_rec_stderr(proc_ref=self._rec_proc):
            try:
                while True:
                    chunk = proc_ref.stderr.read(4096)
                    if not chunk:
                        break
                    self._rec_stderr_chunks.append(chunk)
                    if len(self._rec_stderr_chunks) > _REC_STDERR_MAX_CHUNKS:
                        self._rec_stderr_chunks = self._rec_stderr_chunks[-_REC_STDERR_MAX_CHUNKS:]
            except Exception:
                pass

        self._rec_stderr_thread = threading.Thread(
            target=_drain_rec_stderr, daemon=True, name="rec-stderr-drain",
        )
        self._rec_stderr_thread.start()

        self._rec_ffmpeg = ffmpeg
        self._rec_frame_size = (w, h)
        self._rec_compose_bg = compose_bg
        self._rec_start = time.monotonic()
        self._rec_frame_count = 0
        self._rec_fps = fps

        # Bounded queue + writer thread so pipe writes don't block capture.
        # Max 3 frames (~18 MB at 1080p) — if FFmpeg can't keep up we drop.
        import queue as _queue
        self._rec_write_queue: _queue.Queue = _queue.Queue(maxsize=3)
        self._rec_writer_thread = threading.Thread(
            target=self._rec_writer_loop, daemon=True, name="rec-writer",
        )
        self._rec_writer_thread.start()

        # Audio drain setup
        self._rec_game_chunks = []
        self._rec_mic_chunks = []
        self._rec_last_drain = self._rec_start
        self._rec_audio_stop = threading.Event()

        if self._audio_buffer or self._mic_buffer:
            self._rec_audio_thread = threading.Thread(
                target=self._rec_drain_audio_loop,
                daemon=True, name="rec-audio-drain",
            )
            self._rec_audio_thread.start()

        # Snapshot config + background for background threads so they
        # don't read the mutable main-thread config object.
        cfg = self._config
        self._rec_bg = self._background.copy() if self._background is not None else None
        self._rec_cfg = {
            # _write_recording_frame
            "clip_scaling": getattr(cfg, "clip_scaling", "lanczos"),
            "capture_blur_regions": copy.deepcopy(cfg.capture_blur_regions),
            "clip_webcam_position_x": cfg.clip_webcam_position_x,
            "clip_webcam_position_y": cfg.clip_webcam_position_y,
            "clip_webcam_crop_x": cfg.clip_webcam_crop_x,
            "clip_webcam_crop_y": cfg.clip_webcam_crop_y,
            "clip_webcam_crop_w": cfg.clip_webcam_crop_w,
            "clip_webcam_crop_h": cfg.clip_webcam_crop_h,
            "clip_webcam_chroma_enabled": cfg.clip_webcam_chroma_enabled,
            "clip_webcam_chroma_color": cfg.clip_webcam_chroma_color,
            "clip_webcam_chroma_threshold": cfg.clip_webcam_chroma_threshold,
            "clip_webcam_chroma_smoothing": cfg.clip_webcam_chroma_smoothing,
            "clip_webcam_scale": cfg.clip_webcam_scale,
            # _mux_recording_audio
            "clip_audio_game_gain": cfg.clip_audio_game_gain,
            "clip_audio_mic_gain": cfg.clip_audio_mic_gain,
            "clip_audio_noise_suppression": cfg.clip_audio_noise_suppression,
            "clip_audio_noise_gate": cfg.clip_audio_noise_gate,
            "clip_audio_compressor": cfg.clip_audio_compressor,
            "clip_audio_ns_mix": cfg.clip_audio_ns_mix,
            "clip_audio_gate_threshold": cfg.clip_audio_gate_threshold,
            "clip_audio_gate_ratio": cfg.clip_audio_gate_ratio,
            "clip_audio_gate_attack": cfg.clip_audio_gate_attack,
            "clip_audio_gate_release": cfg.clip_audio_gate_release,
            "clip_audio_comp_threshold": cfg.clip_audio_comp_threshold,
            "clip_audio_comp_ratio": cfg.clip_audio_comp_ratio,
            "clip_audio_comp_attack": cfg.clip_audio_comp_attack,
            "clip_audio_comp_release": cfg.clip_audio_comp_release,
        }

        self._recording = True
        self._event_bus.publish(EVENT_RECORDING_STARTED, {
            "path": str(self._rec_output),
        })
        log.info("Recording started: %s (%dx%d @ %dfps)", self._rec_output, w, h, fps)

    def _stop_recording(self) -> None:
        """Stop recording and finalize the output file."""
        if not self._recording:
            return
        self._recording = False

        rec_end = time.monotonic()

        # Flush the writer queue — sentinel tells it to exit after
        # draining remaining frames so we don't lose them.
        q = getattr(self, "_rec_write_queue", None)
        if q is not None:
            q.put(self._REC_WRITE_SENTINEL)
        wt = getattr(self, "_rec_writer_thread", None)
        if wt is not None:
            wt.join(timeout=10)
            self._rec_writer_thread = None
        self._rec_write_queue = None

        # Stop audio drain thread
        if self._rec_audio_stop:
            self._rec_audio_stop.set()
        if self._rec_audio_thread:
            self._rec_audio_thread.join(timeout=5)
            self._rec_audio_thread = None

        # Final audio drain
        self._rec_drain_audio(rec_end)

        # Close FFmpeg stdin
        proc = self._rec_proc
        self._rec_proc = None

        # Finalize in background thread
        threading.Thread(
            target=self._finalize_recording,
            args=(proc, rec_end),
            daemon=True, name="rec-finalize",
        ).start()

        log.info("Recording stopped (%.1fs, %d frames) — finalizing...",
                 rec_end - self._rec_start, self._rec_frame_count)

        # If clips are disabled, tear down the subscription we started
        if not self._config.clip_enabled:
            self._stop_frame_subscription()
            self._stop_audio()
            self._stop_mic()
            self._release_webcam_if_not_needed()

    def _emergency_stop_recording(self) -> None:
        """Clean up recording after a pipe break (called from background thread).

        Unlike _stop_recording, this skips the _recording guard since
        it was already set to False by the caller.
        """
        rec_end = time.monotonic()

        # Writer thread exits on pipe break, just clean up references
        self._rec_write_queue = None
        self._rec_writer_thread = None

        # Stop audio drain thread
        if self._rec_audio_stop:
            self._rec_audio_stop.set()
        if self._rec_audio_thread:
            self._rec_audio_thread.join(timeout=5)
            self._rec_audio_thread = None

        self._rec_drain_audio(rec_end)

        proc = self._rec_proc
        self._rec_proc = None

        threading.Thread(
            target=self._finalize_recording,
            args=(proc, rec_end),
            daemon=True, name="rec-finalize",
        ).start()

        log.info("Recording emergency stop (%.1fs, %d frames) — finalizing...",
                 rec_end - self._rec_start, self._rec_frame_count)

        if not self._config.clip_enabled:
            self._stop_frame_subscription()
            self._stop_audio()
            self._stop_mic()
            self._release_webcam_if_not_needed()

    def _write_recording_frame(self, frame_bgr: np.ndarray) -> None:
        """Process a frame and queue it for the writer thread.

        Runs on the capture thread.  The actual pipe write is offloaded
        to ``_rec_writer_loop`` so a slow FFmpeg doesn't block capture.
        """
        q = getattr(self, "_rec_write_queue", None)
        if q is None:
            return

        w, h = self._rec_frame_size
        c = self._rec_cfg  # snapshot taken at recording start
        bg = self._rec_bg

        # Background compositing
        if self._rec_compose_bg and bg is not None:
            frame_bgr = compose_on_background(frame_bgr, bg, w, h,
                                                  scaling=c.get("clip_scaling", "lanczos"))

        # Blur regions
        blur = c.get("capture_blur_regions")
        if blur:
            frame_bgr = apply_blur_regions(frame_bgr, blur)

        # Webcam overlay (live refresh each frame)
        if self._webcam_capture:
            wf = self._webcam_capture.get_latest_frame()
            if wf is not None:
                from .clip_writer import _composite_webcam
                frame_bgr = _composite_webcam(
                    frame_bgr, wf,
                    c.get("clip_webcam_position_x", 0), c.get("clip_webcam_position_y", 0),
                    crop={"x": c.get("clip_webcam_crop_x", 0), "y": c.get("clip_webcam_crop_y", 0),
                          "w": c.get("clip_webcam_crop_w", 0), "h": c.get("clip_webcam_crop_h", 0)},
                    chroma={"enabled": c.get("clip_webcam_chroma_enabled", False),
                            "color": c.get("clip_webcam_chroma_color", "#00FF00"),
                            "threshold": c.get("clip_webcam_chroma_threshold", 40),
                            "smoothing": c.get("clip_webcam_chroma_smoothing", 5)},
                    scale=c.get("clip_webcam_scale", 1.0),
                    scaling=c.get("clip_scaling", "lanczos"),
                )

        # Ensure consistent frame size
        fh, fw = frame_bgr.shape[:2]
        if (fw != w or fh != h) and cv2 is not None:
            frame_bgr = cv2.resize(frame_bgr, (w, h), interpolation=get_interpolation(c.get("clip_scaling", "lanczos")))

        raw = frame_bgr.tobytes()
        try:
            q.put_nowait(raw)
        except Exception:
            # Queue full — FFmpeg can't keep up; drop this frame.
            log.debug("Recording frame dropped (queue full)")

    _REC_WRITE_SENTINEL = object()

    def _rec_writer_loop(self) -> None:
        """Drain the write queue into FFmpeg stdin (runs in dedicated thread)."""
        q = self._rec_write_queue
        while True:
            raw = q.get()
            if raw is self._REC_WRITE_SENTINEL:
                break
            proc = self._rec_proc
            if not proc or not proc.stdin:
                continue
            try:
                proc.stdin.write(raw)
                self._rec_frame_count += 1
            except (BrokenPipeError, OSError, ValueError):
                log.error("Recording pipe broken — stopping")
                self._recording = False
                threading.Thread(
                    target=self._emergency_stop_recording,
                    daemon=True, name="rec-pipe-break-stop",
                ).start()
                break

    # ------------------------------------------------------------------
    # Recording audio drain
    # ------------------------------------------------------------------

    def _rec_drain_audio_loop(self) -> None:
        """Periodically drain audio buffers while recording."""
        DRAIN_INTERVAL = 5.0
        while not self._rec_audio_stop.is_set():
            self._rec_audio_stop.wait(DRAIN_INTERVAL)
            if not self._recording:
                break
            self._rec_drain_audio(time.monotonic())

    _REC_AUDIO_CONSOLIDATE_THRESHOLD = 12  # consolidate every ~60s

    def _rec_drain_audio(self, now: float) -> None:
        """Snapshot new audio since last drain and accumulate."""
        with self._rec_audio_lock:
            last = self._rec_last_drain
            if self._audio_buffer:
                data = self._audio_buffer.snapshot(last, now)
                if data is not None:
                    self._rec_game_chunks.append(data)
            if self._mic_buffer:
                data = self._mic_buffer.snapshot(last, now)
                if data is not None:
                    self._rec_mic_chunks.append(data)
            self._rec_last_drain = now
            # Periodically consolidate many small arrays into one to
            # reduce fragmentation and speed up final concatenation.
            if len(self._rec_game_chunks) >= self._REC_AUDIO_CONSOLIDATE_THRESHOLD:
                self._rec_game_chunks = [np.concatenate(self._rec_game_chunks, axis=0)]
            if len(self._rec_mic_chunks) >= self._REC_AUDIO_CONSOLIDATE_THRESHOLD:
                self._rec_mic_chunks = [np.concatenate(self._rec_mic_chunks, axis=0)]

    # ------------------------------------------------------------------
    # Recording finalization (runs in background thread)
    # ------------------------------------------------------------------

    def _finalize_recording(self, proc: subprocess.Popen | None, rec_end: float) -> None:
        """Wait for video encode, mux audio, publish result."""
        try:
            # Close stdin and wait for FFmpeg to finish the video
            if proc:
                if proc.stdin:
                    try:
                        proc.stdin.close()
                    except Exception:
                        pass
                # stderr is drained by _rec_stderr_thread; just wait for exit
                if self._rec_stderr_thread:
                    self._rec_stderr_thread.join(timeout=120)
                proc.wait(timeout=120)
                if proc.returncode != 0:
                    stderr_out = b"".join(
                        self._rec_stderr_chunks
                    ).decode("utf-8", errors="replace")
                    raise RuntimeError(f"Recording FFmpeg failed: {stderr_out[-500:]}")

            # Compute video time-scale correction.
            # FFmpeg assumed constant -r fps, but actual frame delivery may
            # differ — causing A/V desync if uncorrected.
            actual_duration = rec_end - self._rec_start
            assumed_duration = (self._rec_frame_count / self._rec_fps
                                if self._rec_fps > 0 else actual_duration)
            # itsscale > 1 → video was too short → stretch to match real time
            itsscale = (actual_duration / assumed_duration
                        if assumed_duration > 0 else 1.0)
            if abs(itsscale - 1.0) > 0.01:
                actual_fps = self._rec_frame_count / actual_duration if actual_duration > 0 else 0
                log.warning(
                    "Frame rate mismatch: configured %dfps, actual %.1ffps "
                    "(itsscale=%.4f, %d frames in %.1fs)",
                    self._rec_fps, actual_fps, itsscale,
                    self._rec_frame_count, actual_duration,
                )

            # Prepare audio — take ownership of chunks under lock
            with self._rec_audio_lock:
                game_chunks = list(self._rec_game_chunks)
                mic_chunks = list(self._rec_mic_chunks)
                self._rec_game_chunks.clear()
                self._rec_mic_chunks.clear()
            game_pcm = (np.concatenate(game_chunks, axis=0)
                        if game_chunks else None)
            mic_pcm = (np.concatenate(mic_chunks, axis=0)
                       if mic_chunks else None)
            has_audio = game_pcm is not None or mic_pcm is not None

            if has_audio:
                self._mux_recording_audio(game_pcm, mic_pcm, itsscale)
                # Remove temp video
                if self._rec_temp_video and self._rec_temp_video.exists():
                    self._rec_temp_video.unlink(missing_ok=True)
            else:
                # No audio — remux with timing correction if needed
                if self._rec_temp_video and self._rec_temp_video.exists():
                    if abs(itsscale - 1.0) > 0.01:
                        self._remux_video_timing(itsscale)
                    else:
                        self._rec_temp_video.rename(self._rec_output)

            # Save a thumbnail alongside the recording for gallery loading
            try:
                if cv2 is not None and self._rec_output and self._rec_output.exists():
                    cap = cv2.VideoCapture(str(self._rec_output))
                    ret, thumb_frame = cap.read()
                    cap.release()
                    if ret and thumb_frame is not None:
                        th, tw = thumb_frame.shape[:2]
                        scale = min(320 / tw, 200 / th, 1.0)
                        if scale < 1.0:
                            thumb_frame = cv2.resize(
                                thumb_frame,
                                (int(tw * scale), int(th * scale)),
                                interpolation=cv2.INTER_AREA,
                            )
                        thumb_path = self._rec_output.with_suffix(".thumb.jpg")
                        cv2.imwrite(str(thumb_path), thumb_frame,
                                    [cv2.IMWRITE_JPEG_QUALITY, 80])
            except Exception:
                pass  # thumbnail is optional

            duration = rec_end - self._rec_start
            self._event_bus.publish(EVENT_RECORDING_STOPPED, {
                "path": str(self._rec_output),
                "duration": duration,
                "frames": self._rec_frame_count,
            })
            log.info("Recording saved: %s (%.1fs, %d frames)",
                     self._rec_output, duration, self._rec_frame_count)
        except Exception as e:
            log.error("Failed to finalize recording: %s", e)
            self._event_bus.publish(EVENT_CAPTURE_ERROR, {"error": str(e)})
            # Clean up incomplete files on failure
            for f in (self._rec_temp_video, self._rec_output):
                try:
                    if f and f.exists():
                        f.unlink()
                except OSError:
                    pass
        finally:
            # Chunks are already moved out under lock above; clear as safety net
            with self._rec_audio_lock:
                self._rec_game_chunks.clear()
                self._rec_mic_chunks.clear()

    def _remux_video_timing(self, itsscale: float) -> None:
        """Remux temp video with corrected timing (no audio, no re-encode)."""
        cmd = [
            self._rec_ffmpeg, "-y",
            "-itsscale", str(itsscale),
            "-i", str(self._rec_temp_video),
            "-c", "copy",
            str(self._rec_output),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode != 0:
                log.warning("Timing remux failed, using uncorrected video")
                self._rec_temp_video.rename(self._rec_output)
            else:
                self._rec_temp_video.unlink(missing_ok=True)
        except Exception:
            self._rec_temp_video.rename(self._rec_output)

    def _mux_recording_audio(
        self,
        game_pcm: np.ndarray | None,
        mic_pcm: np.ndarray | None,
        itsscale: float = 1.0,
    ) -> None:
        """Mux recorded video with audio tracks via a second FFmpeg pass (copy video)."""
        from .clip_writer import _write_wav, _apply_gain, _build_mic_filter
        from .ffmpeg import ensure_rnnoise_model

        temp_files: list[str] = []
        try:
            cmd = [self._rec_ffmpeg, "-y"]

            # Apply time-scale correction to the video input so its duration
            # matches the real wall-clock recording time (and thus the audio).
            if abs(itsscale - 1.0) > 0.001:
                cmd.extend(["-itsscale", str(itsscale)])
                log.info("Applying video time-scale correction: %.4f", itsscale)

            cmd.extend(["-i", str(self._rec_temp_video)])

            has_game = game_pcm is not None and len(game_pcm) > 0
            has_mic = mic_pcm is not None and len(mic_pcm) > 0

            c = self._rec_cfg  # config snapshot from recording start

            if has_game:
                game_pcm = _apply_gain(game_pcm, c.get("clip_audio_game_gain", 0.0))
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                _write_wav(game_pcm, tmp.name)
                tmp.close()
                temp_files.append(tmp.name)
                cmd.extend(["-i", tmp.name])

            if has_mic:
                mic_pcm = _apply_gain(mic_pcm, c.get("clip_audio_mic_gain", 0.0))
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                _write_wav(mic_pcm, tmp.name)
                tmp.close()
                temp_files.append(tmp.name)
                cmd.extend(["-i", tmp.name])

            cmd.extend(["-c:v", "copy",
                        "-shortest"])  # trim to shorter of video/audio

            rnnoise_model = ensure_rnnoise_model() if c.get("clip_audio_noise_suppression") else None
            mic_af = _build_mic_filter({
                "noise_suppression": c.get("clip_audio_noise_suppression", False),
                "noise_gate": c.get("clip_audio_noise_gate", False),
                "compressor": c.get("clip_audio_compressor", False),
                "ns_mix": c.get("clip_audio_ns_mix", 1.0),
                "gate_threshold": c.get("clip_audio_gate_threshold", -40),
                "gate_ratio": c.get("clip_audio_gate_ratio", 2),
                "gate_attack": c.get("clip_audio_gate_attack", 5),
                "gate_release": c.get("clip_audio_gate_release", 100),
                "comp_threshold": c.get("clip_audio_comp_threshold", -20),
                "comp_ratio": c.get("clip_audio_comp_ratio", 4),
                "comp_attack": c.get("clip_audio_comp_attack", 5),
                "comp_release": c.get("clip_audio_comp_release", 100),
            }, rnnoise_model=rnnoise_model)

            if has_game and has_mic:
                mic_idx = 2  # 0=video, 1=game, 2=mic
                if mic_af:
                    cmd.extend(["-filter_complex", f"[{mic_idx}:a]{mic_af}[mic_f]"])
                    cmd.extend(["-map", "0:v", "-map", "1:a", "-map", "[mic_f]"])
                else:
                    cmd.extend(["-map", "0:v", "-map", "1:a", "-map", "2:a"])
                cmd.extend(["-c:a", "aac", "-b:a", "128k"])
                cmd.extend([
                    "-metadata:s:a:0", "title=System Audio",
                    "-metadata:s:a:1", "title=Microphone",
                ])
            elif has_game:
                cmd.extend(["-c:a", "aac", "-b:a", "128k"])
            elif has_mic:
                if mic_af:
                    cmd.extend(["-af", mic_af])
                cmd.extend(["-c:a", "aac", "-b:a", "128k"])

            cmd.append(str(self._rec_output))

            # Set cwd to model directory so arnndn can find the model by filename
            # (Windows drive-letter colon breaks FFmpeg filter path parsing).
            ffmpeg_cwd = os.path.dirname(rnnoise_model) if rnnoise_model else None
            result = subprocess.run(cmd, capture_output=True, timeout=300, cwd=ffmpeg_cwd)
            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace")[-500:]
                raise RuntimeError(f"Audio mux failed: {err}")
        finally:
            for f in temp_files:
                try:
                    os.unlink(f)
                except OSError:
                    pass
