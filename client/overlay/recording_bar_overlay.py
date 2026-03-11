"""Compact recording bar overlay — screenshot, clip, record controls."""

from __future__ import annotations

import shutil
import time
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QDialog,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from .overlay_widget import OverlayWidget
from ..core.config import save_config
from ..core.constants import EVENT_CONFIG_CHANGED, EVENT_HOTKEY_TRIGGERED
from ..core.logger import get_logger
from ..capture.constants import DEFAULT_CLIP_DIR, get_bitrate
from ..ui.icons import (
    svg_icon, SCREENSHOT, CLIP, RECORD_CIRCLE, STOP_SQUARE, GALLERY,
)

if TYPE_CHECKING:
    from .overlay_manager import OverlayManager
    from ..capture.capture_manager import CaptureManager

log = get_logger("RecordingBar")

BAR_WIDTH = 350

# Pulse animation interval (ms)
PULSE_INTERVAL_MS = 800

# Overlay-specific dark translucent theme (matches search overlay)
BG_COLOR = "rgba(20, 20, 30, 220)"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#888888"
DISABLED_COLOR = "#555555"
ACCENT = "#00ccff"
RECORD_RED = "#e53935"

_BTN_STYLE = (
    "QPushButton {"
    "  background: rgba(40, 40, 55, 230);"
    "  border: 1px solid rgba(80, 80, 100, 180);"
    "  border-radius: 4px;"
    "  padding: 3px 6px;"
    "}"
    "QPushButton:hover {"
    "  background: rgba(60, 60, 80, 200);"
    "  border-color: #00ccff;"
    "}"
    "QPushButton:pressed {"
    "  background: rgba(80, 80, 100, 200);"
    "}"
)

_BTN_RECORDING_STYLE = (
    "QPushButton {"
    "  background: rgba(80, 20, 20, 230);"
    "  border: 1px solid #e53935;"
    "  border-radius: 4px;"
    "  padding: 3px 6px;"
    "}"
    "QPushButton:hover {"
    "  background: rgba(100, 30, 30, 230);"
    "}"
    "QPushButton:pressed {"
    "  background: rgba(120, 40, 40, 230);"
    "}"
)

_BTN_DISABLED_STYLE = (
    "QPushButton {"
    "  background: rgba(30, 30, 40, 200);"
    "  border: 1px solid rgba(60, 60, 70, 150);"
    "  border-radius: 4px;"
    "  padding: 3px 6px;"
    "}"
    "QPushButton:hover {"
    "  background: rgba(40, 40, 55, 200);"
    "  border-color: rgba(80, 80, 100, 180);"
    "}"
)


class RecordingBarOverlay(OverlayWidget):
    """Compact horizontal bar for capture controls."""

    open_settings = pyqtSignal()
    open_gallery = pyqtSignal()

    def __init__(
        self,
        *,
        config,
        config_path: str,
        event_bus,
        signals,
        capture_manager: CaptureManager,
        manager: OverlayManager | None = None,
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="recording_bar_overlay_position",
            manager=manager,
        )
        self._event_bus = event_bus
        self._signals = signals
        self._capture_manager = capture_manager

        # Let layout auto-resize the window to match content
        self.layout().setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        # Container style
        self._container.setFixedWidth(BAR_WIDTH)
        self._container.setStyleSheet(
            f"background-color: {BG_COLOR}; border-radius: 8px;"
        )

        layout = QHBoxLayout(self._container)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Screenshot button
        self._ss_btn = QPushButton()
        self._ss_btn.setFixedSize(28, 28)
        self._ss_btn.setIcon(svg_icon(SCREENSHOT, TEXT_COLOR, 16))
        self._ss_btn.setToolTip("Take screenshot")
        self._ss_btn.setStyleSheet(_BTN_STYLE)
        self._ss_btn.clicked.connect(self._on_screenshot_clicked)
        layout.addWidget(self._ss_btn)

        # Clip button
        self._clip_btn = QPushButton()
        self._clip_btn.setFixedSize(28, 28)
        self._clip_btn.setToolTip("Save clip")
        self._clip_btn.clicked.connect(self._on_clip_clicked)
        layout.addWidget(self._clip_btn)

        # Record button
        self._rec_btn = QPushButton()
        self._rec_btn.setFixedSize(28, 28)
        self._rec_btn.setIcon(svg_icon(RECORD_CIRCLE, TEXT_COLOR, 16))
        self._rec_btn.setToolTip("Start recording")
        self._rec_btn.setStyleSheet(_BTN_STYLE)
        self._rec_btn.clicked.connect(self._on_record_clicked)
        layout.addWidget(self._rec_btn)

        # Time / status label
        self._time_label = QLabel("")
        self._time_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px; font-family: monospace;"
            " padding: 0 4px;"
        )
        layout.addWidget(self._time_label, 1)

        # Gallery button (right side)
        self._gallery_btn = QPushButton()
        self._gallery_btn.setFixedSize(28, 28)
        self._gallery_btn.setIcon(svg_icon(GALLERY, TEXT_COLOR, 16))
        self._gallery_btn.setToolTip("Open gallery (Ctrl+G)")
        self._gallery_btn.setStyleSheet(_BTN_STYLE)
        self._gallery_btn.clicked.connect(self.open_gallery.emit)
        layout.addWidget(self._gallery_btn)

        # Recording timer (1 Hz)
        self._rec_timer = QTimer(self)
        self._rec_timer.setInterval(1000)
        self._rec_timer.timeout.connect(self._update_rec_display)
        self._disk_update_counter = 0
        self._last_remaining_text = ""

        # Idle refresh timer — update remaining time every 5s when not recording
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(5000)
        self._idle_timer.timeout.connect(self._update_idle_display)
        self._idle_timer.start()

        # Pulse animation timer for record/clip icons
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(PULSE_INTERVAL_MS)
        self._pulse_timer.timeout.connect(self._on_pulse_tick)
        self._pulse_bright = True  # toggles each tick

        # Webcam wait state
        self._webcam_timer: QTimer | None = None
        self._webcam_callback = None
        self._webcam_wait_start: float = 0.0

        # Clip encoding progress state
        self._encoding_pct: int = 0  # 0-100, 0 = no active encoding

        # OBS connection state
        self._obs_connected = False

        # Local recording start time (monotonic) for elapsed timer
        self._rec_start_mono: float = 0.0

        # Connect signals
        signals.recording_started.connect(self._on_recording_started)
        signals.recording_stopped.connect(self._on_recording_stopped)
        signals.clip_encoding_started.connect(self._on_encoding_started)
        signals.clip_encoding_progress.connect(self._on_encoding_progress)
        signals.clip_saved.connect(self._on_encoding_done)
        signals.capture_error.connect(self._on_encoding_done)

        # Listen for config changes to update clip button state
        event_bus.subscribe(EVENT_CONFIG_CHANGED, self._on_config_changed)

        # OBS connection events
        signals.obs_connected.connect(self._on_obs_bar_connected)
        signals.obs_disconnected.connect(self._on_obs_bar_disconnected)

        # Check first-open setup
        self._setup_checked = False

        # Initial clip button state
        self._update_clip_button_state()

        # Show idle placeholder
        self._update_idle_display()

    # ------------------------------------------------------------------
    # First-open setup dialog
    # ------------------------------------------------------------------

    def set_wants_visible(self, visible: bool) -> None:
        super().set_wants_visible(visible)
        if visible and not self._setup_checked:
            self._setup_checked = True
            self._maybe_show_setup()

    def _maybe_show_setup(self):
        """Show one-time setup dialog if not previously dismissed."""
        if getattr(self._config, "recording_bar_setup_shown", False):
            return

        dlg = QDialog()
        dlg.setWindowTitle("Recording Setup")
        dlg.setFixedWidth(380)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        msg = QLabel(
            "To use screenshot, clip, and recording features, you may need "
            "to download dependencies and configure video settings."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(dismiss_btn)

        settings_btn = QPushButton("Open Settings")
        settings_btn.setObjectName("accentButton")
        settings_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(settings_btn)

        layout.addLayout(btn_row)

        self._config.recording_bar_setup_shown = True
        save_config(self._config, self._config_path)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.open_settings.emit()

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_screenshot_clicked(self):
        self._event_bus.publish(EVENT_HOTKEY_TRIGGERED, "screenshot")

    def _on_clip_clicked(self):
        if not self._config.clip_enabled and not self._config.obs_enabled:
            # Neither mode active — open settings so user can enable one
            self.open_settings.emit()
            return
        if not self._config.obs_enabled and not self._ensure_media():
            return
        self._event_bus.publish(EVENT_HOTKEY_TRIGGERED, "save_clip")

    def _on_record_clicked(self):
        if self._capture_manager.is_recording:
            self._event_bus.publish(EVENT_HOTKEY_TRIGGERED, "toggle_recording")
            return

        capture_on = getattr(self._config, "capture_enabled", False)
        if not capture_on and not self._config.obs_enabled:
            # Neither mode active — open settings so user can enable one
            self.open_settings.emit()
            return

        if self._config.obs_enabled:
            # OBS mode — no media/webcam checks needed
            self._do_start_recording()
            return

        if not self._ensure_media():
            return

        # If webcam enabled, wait for it to be ready before starting
        if self._config.clip_webcam_enabled:
            self._wait_for_webcam(self._do_start_recording)
        else:
            self._do_start_recording()

    def _do_start_recording(self):
        self._event_bus.publish(EVENT_HOTKEY_TRIGGERED, "toggle_recording")

    def _ensure_media(self) -> bool:
        """Check media libraries + FFmpeg; show download dialogs if needed."""
        try:
            from ..ui.dialogs.media_download_dialog import ensure_media_libraries
            return ensure_media_libraries(
                self._config, self._event_bus, self._signals,
            )
        except Exception as e:
            log.error("Media library check failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Clip button state
    # ------------------------------------------------------------------

    def _update_clip_button_state(self):
        """Update clip and record button appearances based on enabled state."""
        clip_active = self._config.clip_enabled or self._config.obs_enabled
        capture_on = getattr(self._config, "capture_enabled", False)
        capture_active = capture_on or self._config.obs_enabled

        # Clip button
        if clip_active:
            tip = "Save clip (OBS)" if self._config.obs_enabled else "Save clip"
            self._clip_btn.setToolTip(tip)
            self._clip_btn.setStyleSheet(_BTN_STYLE)
            # Constant blue glow when buffer is active; pulse only while encoding
            self._set_clip_icon_bright(True)
            if self._encoding_pct > 0:
                self._start_pulse_if_needed()
            else:
                self._stop_pulse_if_unneeded()
        else:
            self._clip_btn.setIcon(svg_icon(CLIP, DISABLED_COLOR, 16))
            self._clip_btn.setToolTip("Clip buffer disabled — click to configure")
            self._clip_btn.setStyleSheet(_BTN_DISABLED_STYLE)
            self._stop_pulse_if_unneeded()

        # Record button
        if not self._capture_manager.is_recording:
            if capture_active:
                self._rec_btn.setIcon(svg_icon(RECORD_CIRCLE, TEXT_COLOR, 16))
                self._rec_btn.setToolTip("Start recording")
                self._rec_btn.setStyleSheet(_BTN_STYLE)
            else:
                self._rec_btn.setIcon(svg_icon(RECORD_CIRCLE, DISABLED_COLOR, 16))
                self._rec_btn.setToolTip("Video capture disabled — click to configure")
                self._rec_btn.setStyleSheet(_BTN_DISABLED_STYLE)

    def _set_clip_icon_bright(self, bright: bool):
        """Set clip icon to accent (bright) or dim."""
        color = ACCENT if bright else TEXT_DIM
        self._clip_btn.setIcon(svg_icon(CLIP, color, 16))

    # ------------------------------------------------------------------
    # Pulse animation (for record icon while recording, clip icon while encoding)
    # ------------------------------------------------------------------

    def _start_pulse_if_needed(self):
        """Start the pulse timer if recording is active or clip is encoding."""
        if not self._pulse_timer.isActive():
            self._pulse_bright = True
            self._pulse_timer.start()

    def _stop_pulse_if_unneeded(self):
        """Stop the pulse timer if neither recording nor clip encoding is active."""
        is_recording = self._capture_manager.is_recording
        is_encoding = self._encoding_pct > 0
        if not is_recording and not is_encoding:
            self._pulse_timer.stop()

    def _on_pulse_tick(self):
        """Toggle pulse state for animated icons."""
        self._pulse_bright = not self._pulse_bright

        # Pulse record icon red while recording
        if self._capture_manager.is_recording:
            color = RECORD_RED if self._pulse_bright else "#8b1a1a"
            self._rec_btn.setIcon(svg_icon(RECORD_CIRCLE, color, 16))

        # Pulse clip icon while encoding (constant blue otherwise)
        if self._encoding_pct > 0:
            self._set_clip_icon_bright(self._pulse_bright)

    # ------------------------------------------------------------------
    # Webcam wait
    # ------------------------------------------------------------------

    def _wait_for_webcam(self, callback):
        """Poll for webcam readiness before invoking callback."""
        self._webcam_callback = callback
        self._webcam_wait_start = time.monotonic()
        self._time_label.setText("Waiting for webcam...")

        # Ensure the webcam is actually started
        self._capture_manager._start_webcam()

        if self._webcam_timer is not None:
            self._webcam_timer.stop()
        self._webcam_timer = QTimer(self)
        self._webcam_timer.setInterval(200)
        self._webcam_timer.timeout.connect(self._check_webcam)
        self._webcam_timer.start()

    def _check_webcam(self):
        wc = self._capture_manager._webcam_capture
        if wc is not None and wc.get_latest_frame() is not None:
            self._webcam_timer.stop()
            self._webcam_timer = None
            self._time_label.setText("")
            if self._webcam_callback:
                self._webcam_callback()
                self._webcam_callback = None
            return

        # Timeout after 10 seconds
        elapsed = time.monotonic() - self._webcam_wait_start
        if elapsed > 10.0:
            self._webcam_timer.stop()
            self._webcam_timer = None
            self._time_label.setText("Webcam timeout")
            self._webcam_callback = None
            t = QTimer(self)
            t.setSingleShot(True)
            t.setInterval(3000)
            t.timeout.connect(self._clear_webcam_timeout)
            t.start()

    def _clear_webcam_timeout(self):
        """Clear the webcam timeout label if it hasn't been overwritten."""
        if self._time_label.text() == "Webcam timeout":
            self._time_label.setText("")

    # ------------------------------------------------------------------
    # Recording state signals
    # ------------------------------------------------------------------

    def _on_recording_started(self, data):
        self._rec_start_mono = time.monotonic()
        # Switch to pulsing record circle (not stop icon) — pulse handles color
        self._rec_btn.setIcon(svg_icon(RECORD_CIRCLE, RECORD_RED, 16))
        self._rec_btn.setToolTip("Stop recording")
        self._rec_btn.setStyleSheet(_BTN_RECORDING_STYLE)
        self._disk_update_counter = 0
        self._last_remaining_text = ""
        self._idle_timer.stop()
        self._rec_timer.start()
        self._start_pulse_if_needed()  # pulse for record icon
        self._update_rec_display()

        # Auto-show the bar when recording starts
        if not self.isVisible():
            self.set_wants_visible(True)
            self.raise_()

    def _on_recording_stopped(self, data):
        self._rec_timer.stop()
        self._last_remaining_text = ""
        self._stop_pulse_if_unneeded()
        # Restore record button to correct state based on capture_enabled
        self._update_clip_button_state()
        # Restore idle display and restart idle timer
        self._update_idle_display()
        self._idle_timer.start()

    # ------------------------------------------------------------------
    # Idle display (not recording)
    # ------------------------------------------------------------------

    def _update_idle_display(self):
        """Show 00:00 / ~remaining as placeholder when not recording."""
        if self._capture_manager.is_recording:
            return

        prefix = ""
        if self._config.obs_enabled:
            # ● connected, ○ disconnected
            prefix = "\u25cf " if self._obs_connected else "\u25cb "

        remaining = self._estimate_remaining()
        if remaining is not None:
            text = f"{prefix}00:00 / ~{self._format_time(remaining)}"
        else:
            text = f"{prefix}00:00"
        if self._encoding_pct > 0:
            text += f"  \u2022 Clip {self._encoding_pct}%"
        self._time_label.setText(text)

    # ------------------------------------------------------------------
    # Recording timer display
    # ------------------------------------------------------------------

    def _update_rec_display(self):
        """Update elapsed time and (every 5s) disk space remaining."""
        if not self._capture_manager.is_recording:
            return

        if self._rec_start_mono <= 0:
            return

        elapsed = time.monotonic() - self._rec_start_mono
        text = self._format_time(elapsed)

        # Update disk space estimate every 5 ticks (also on first tick)
        self._disk_update_counter += 1
        if self._disk_update_counter >= 5 or self._last_remaining_text == "":
            self._disk_update_counter = 0
            remaining = self._estimate_remaining()
            if remaining is not None:
                self._last_remaining_text = self._format_time(remaining)
            else:
                self._last_remaining_text = ""

        if self._last_remaining_text:
            text += f" / ~{self._last_remaining_text}"

        if self._encoding_pct > 0:
            text += f"  \u2022 Clip {self._encoding_pct}%"

        self._time_label.setText(text)

    @staticmethod
    def _format_time(seconds: float) -> str:
        total = int(seconds)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _estimate_remaining(self) -> float | None:
        """Estimate recording seconds remaining based on disk space."""
        clip_dir = self._config.clip_directory or DEFAULT_CLIP_DIR
        try:
            free = shutil.disk_usage(clip_dir).free
        except OSError:
            return None

        br_str = get_bitrate(
            self._config.clip_resolution, self._config.clip_bitrate
        )
        # Parse "8M" or "1500k" to bytes/sec
        try:
            if br_str.endswith("M"):
                bps = float(br_str[:-1]) * 1_000_000
            elif br_str.endswith("k"):
                bps = float(br_str[:-1]) * 1_000
            else:
                bps = 8_000_000
        except (ValueError, TypeError):
            bps = 8_000_000

        bytes_per_sec = bps / 8
        if bytes_per_sec <= 0:
            return None
        return free / bytes_per_sec

    # ------------------------------------------------------------------
    # Clip encoding progress
    # ------------------------------------------------------------------

    def _on_encoding_started(self, data):
        self._encoding_pct = 1  # non-zero to trigger pulse
        self._start_pulse_if_needed()
        self._update_idle_display()

    def _on_encoding_progress(self, data):
        total = data.get("total", 1)
        written = data.get("written", 0)
        self._encoding_pct = min(100, int(written * 100 / total)) if total else 1
        if not self._capture_manager.is_recording:
            self._update_idle_display()

    def _on_encoding_done(self, data):
        self._encoding_pct = 0
        self._stop_pulse_if_unneeded()
        # Restore steady blue if clip buffer is still active
        clip_active = self._config.clip_enabled or self._config.obs_enabled
        if clip_active:
            self._set_clip_icon_bright(True)
        if not self._capture_manager.is_recording:
            self._update_idle_display()

    # ------------------------------------------------------------------
    # Config changes
    # ------------------------------------------------------------------

    def _on_obs_bar_connected(self, data):
        self._obs_connected = True
        self._update_idle_display()

    def _on_obs_bar_disconnected(self, data):
        self._obs_connected = False
        self._update_idle_display()

    def _on_config_changed(self, config):
        """React to config changes — update button states."""
        self._update_clip_button_state()  # updates both clip and record buttons
        # Refresh idle display (bitrate/resolution may have changed)
        if not self._capture_manager.is_recording:
            self._update_idle_display()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        """Stop timers and unsubscribe from event bus on close."""
        self._rec_timer.stop()
        self._idle_timer.stop()
        self._pulse_timer.stop()
        if self._webcam_timer is not None:
            self._webcam_timer.stop()
            self._webcam_timer = None
        self._webcam_callback = None
        self._event_bus.unsubscribe(EVENT_CONFIG_CHANGED, self._on_config_changed)
        super().closeEvent(event)
