"""Microphone filter settings dialog — all filters in a single dialog with audio check."""

import os
import subprocess
import threading
import time

import numpy as np

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox,
    QPushButton, QCheckBox, QGridLayout, QFrame, QSlider, QWidget,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QLinearGradient

from ...core.config import save_config
from ...core.constants import EVENT_CONFIG_CHANGED
from ...core.logger import get_logger
from ..theme import TEXT_MUTED

log = get_logger("MicFilterDialog")

try:
    import sounddevice as sd
except ImportError:
    sd = None

# Audio level meter constants
_METER_HEIGHT = 10
_METER_UPDATE_MS = 50  # ~20 fps
_METER_BAR_W = 250

_METER_GREEN = QColor(76, 175, 80)
_METER_YELLOW = QColor(255, 193, 7)
_METER_RED = QColor(244, 67, 54)
_METER_BG = QColor(40, 40, 50)


class _LevelBar(QWidget):
    """Horizontal audio level bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = 0.0
        self._peak = 0.0
        self._peak_decay = 0.0
        self.setFixedHeight(_METER_HEIGHT)
        self.setFixedWidth(_METER_BAR_W)

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, level))
        if self._level >= self._peak:
            self._peak = self._level
            self._peak_decay = 0.0
        else:
            self._peak_decay += _METER_UPDATE_MS / 1000.0
            if self._peak_decay > 0.5:
                self._peak = max(self._level, self._peak - 0.02)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_METER_BG)
        p.drawRoundedRect(0, 0, w, h, 3, 3)

        fill_w = int(w * self._level)
        if fill_w > 0:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, _METER_GREEN)
            grad.setColorAt(0.6, _METER_YELLOW)
            grad.setColorAt(1.0, _METER_RED)
            p.setBrush(grad)
            p.drawRoundedRect(0, 0, fill_w, h, 3, 3)

        # Peak hold indicator (white line)
        peak_x = int(w * self._peak)
        if peak_x > 2:
            p.setPen(QColor(255, 255, 255, 200))
            p.drawLine(peak_x, 1, peak_x, h - 1)

        p.end()


# ---------------------------------------------------------------------------
# Filtered mic meter — pipes mic audio through FFmpeg filters for accurate
# level display that reflects noise gate, suppression, and compressor.
# ---------------------------------------------------------------------------

class _FilteredMicMeter:
    """Real-time mic -> FFmpeg filters -> peak level measurement (no speaker)."""

    def __init__(self, *, mic_device, mic_gain, filters, ffmpeg_path,
                 sample_rate=48000, channels=2):
        if sd is None:
            raise ImportError("sounddevice required")
        from ...capture.audio_buffer import AudioBuffer
        self._mic_device = AudioBuffer.resolve_device_index(mic_device, kind="input")
        self._mic_gain = mic_gain
        self._filters = filters or {}
        self._ffmpeg_path = ffmpeg_path
        self._sample_rate = sample_rate
        self._channels = channels
        self._mic_channels = channels
        self._running = False
        self._input_stream = None
        self._ffmpeg_proc = None
        self._reader_thread = None
        self._stderr_thread = None
        self._peak = 0.0
        self._lock = threading.Lock()

    @property
    def peak(self) -> float:
        with self._lock:
            return self._peak

    def _query_mic_channels(self) -> int:
        try:
            if self._mic_device is not None:
                info = sd.query_devices(self._mic_device)
            else:
                info = sd.query_devices(kind="input")
            return min(self._channels, int(info.get("max_input_channels", self._channels)))
        except Exception:
            return self._channels

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._mic_channels = self._query_mic_channels()

        from ...capture.ffmpeg import ensure_ffmpeg, find_rnnoise_model
        ffmpeg = ensure_ffmpeg(self._ffmpeg_path)
        if not ffmpeg:
            self._start_direct()
            return

        # Build filter chain
        rnnoise_model = None
        if self._filters.get("noise_suppression"):
            rnnoise_model = find_rnnoise_model()

        af_parts = []
        if self._mic_gain != 1.0:
            af_parts.append(f"volume={self._mic_gain}")
        if self._filters.get("noise_suppression") and rnnoise_model:
            mix = self._filters.get("ns_mix", 1.0)
            model_name = os.path.basename(rnnoise_model)
            af_parts.append(f"arnndn=m={model_name}:mix={mix}")
        if self._filters.get("noise_gate"):
            thresh = self._filters.get("gate_threshold", 0.01)
            ratio = self._filters.get("gate_ratio", 2.0)
            attack = self._filters.get("gate_attack", 10.0)
            release = self._filters.get("gate_release", 100.0)
            af_parts.append(
                f"agate=threshold={thresh}:ratio={ratio}"
                f":attack={attack}:release={release}"
            )
        if self._filters.get("compressor"):
            thresh = self._filters.get("comp_threshold", -20.0)
            ratio = self._filters.get("comp_ratio", 4.0)
            attack = self._filters.get("comp_attack", 5.0)
            release = self._filters.get("comp_release", 100.0)
            af_parts.append(
                f"acompressor=threshold={thresh}dB:ratio={ratio}"
                f":attack={attack}:release={release}"
            )

        af_str = ",".join(af_parts) if af_parts else "anull"

        ffmpeg_cwd = os.path.dirname(rnnoise_model) if rnnoise_model else None

        cmd = [
            ffmpeg, "-y",
            "-f", "f32le",
            "-ar", str(self._sample_rate),
            "-ac", str(self._mic_channels),
            "-i", "pipe:0",
            "-af", af_str,
            "-f", "f32le",
            "-ar", str(self._sample_rate),
            "-ac", str(self._channels),
            "pipe:1",
        ]

        try:
            self._ffmpeg_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=ffmpeg_cwd,
            )
        except Exception as e:
            log.debug("FFmpeg for meter failed: %s", e)
            self._start_direct()
            return

        # Drain stderr to prevent pipe buffer deadlock
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, daemon=True, name="meter-stderr",
        )
        self._stderr_thread.start()

        self._input_stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._mic_channels,
            dtype="float32",
            blocksize=1024,
            device=self._mic_device or None,
            callback=self._mic_callback_ffmpeg,
        )
        self._input_stream.start()

        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True, name="meter-reader",
        )
        self._reader_thread.start()

    def _start_direct(self):
        """Fallback: raw metering with gain only (no FFmpeg)."""
        self._input_stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._mic_channels,
            dtype="float32",
            blocksize=1024,
            device=self._mic_device or None,
            callback=self._mic_callback_direct,
        )
        self._input_stream.start()

    def _mic_callback_ffmpeg(self, indata, frames, time_info, status):
        if not self._running or not self._ffmpeg_proc:
            return
        try:
            self._ffmpeg_proc.stdin.write(indata.tobytes())
        except Exception:
            pass

    def _mic_callback_direct(self, indata, frames, time_info, status):
        if not self._running:
            return
        data = indata.copy()
        if self._mic_gain != 1.0:
            data = np.clip(data * self._mic_gain, -1.0, 1.0)
        peak = float(np.max(np.abs(data)))
        with self._lock:
            self._peak = peak

    def _reader_loop(self):
        bytes_per_sample = 4
        chunk_bytes = 1024 * self._channels * bytes_per_sample
        while self._running and self._ffmpeg_proc:
            try:
                data = self._ffmpeg_proc.stdout.read(chunk_bytes)
                if not data:
                    break
                arr = np.frombuffer(data, dtype=np.float32)
                peak = float(np.max(np.abs(arr)))
                with self._lock:
                    self._peak = peak
            except Exception:
                break

    def _drain_stderr(self):
        try:
            while True:
                chunk = self._ffmpeg_proc.stderr.read(4096)
                if not chunk:
                    break
        except Exception:
            pass

    def stop(self):
        self._running = False
        if self._input_stream:
            try:
                self._input_stream.stop()
                self._input_stream.close()
            except Exception:
                pass
            self._input_stream = None
        if self._ffmpeg_proc:
            try:
                self._ffmpeg_proc.stdin.close()
            except Exception:
                pass
            try:
                self._ffmpeg_proc.terminate()
                self._ffmpeg_proc.wait(timeout=2)
            except Exception:
                pass
            self._ffmpeg_proc = None
        if self._reader_thread:
            self._reader_thread.join(timeout=2)
            self._reader_thread = None
        if self._stderr_thread:
            self._stderr_thread.join(timeout=2)
            self._stderr_thread = None
        with self._lock:
            self._peak = 0.0


class MicFilterDialog(QDialog):
    """Combined mic settings — volume, noise suppression, gate, compressor.

    Uses a grid layout so labels and inputs align vertically.
    Includes an audio check button for live mic preview with filters applied.
    """

    # Signals for thread-safe UI updates from _start_audio_check_bg
    _check_started = pyqtSignal()
    _check_failed = pyqtSignal(str)

    def __init__(self, *, config, config_path, event_bus, parent=None):
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._event_bus = event_bus
        self._audio_check = None
        self._filtered_meter = None
        self._meter_timer = None

        self.setWindowTitle("Mic Settings")
        self.setMinimumWidth(460)

        # Connect thread-safe signals
        self._check_started.connect(self._on_check_started)
        self._check_failed.connect(self._on_check_failed)

        # Debounce timer for restarting audio check on setting changes
        self._restart_timer = QTimer(self)
        self._restart_timer.setSingleShot(True)
        self._restart_timer.setInterval(300)
        self._restart_timer.timeout.connect(self._restart_check)

        # Debounce timer for restarting the filtered meter
        self._meter_restart_timer = QTimer(self)
        self._meter_restart_timer.setSingleShot(True)
        self._meter_restart_timer.setInterval(500)
        self._meter_restart_timer.timeout.connect(self._restart_meter)

        layout = QVBoxLayout(self)

        desc = QLabel(
            "These settings are applied to the microphone track during clip encoding. "
            "Use Audio Check to preview the effect in real time."
        )
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # ---- Mic Volume ----
        vol_label = QLabel("Mic Volume")
        vol_label.setStyleSheet("font-weight: bold; margin-top: 6px;")
        layout.addWidget(vol_label)

        vol_row = QHBoxLayout()
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 300)
        self._vol_slider.setValue(int(config.clip_audio_mic_gain * 100))
        self._vol_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._vol_slider.setTickInterval(50)
        self._vol_slider.valueChanged.connect(self._on_vol_changed)
        vol_row.addWidget(self._vol_slider)
        self._vol_label = QLabel(f"{int(config.clip_audio_mic_gain * 100)}%")
        self._vol_label.setFixedWidth(40)
        vol_row.addWidget(self._vol_label)
        layout.addLayout(vol_row)

        self._add_separator(layout)

        # ---- Noise Suppression ----
        ns_label = QLabel("Noise Suppression")
        ns_label.setStyleSheet("font-weight: bold; margin-top: 6px;")
        layout.addWidget(ns_label)

        ns_desc = QLabel("Neural network voice denoiser (RNNoise).")
        ns_desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(ns_desc)

        self._ns_enabled = QCheckBox("Enabled")
        self._ns_enabled.setChecked(config.clip_audio_noise_suppression)
        layout.addWidget(self._ns_enabled)

        ns_row = QHBoxLayout()
        ns_row.addWidget(QLabel("Strength:"))
        self._ns_mix = QSlider(Qt.Orientation.Horizontal)
        self._ns_mix.setRange(0, 100)
        self._ns_mix.setValue(int(config.clip_audio_ns_mix * 100))
        self._ns_mix.setToolTip("0% = bypass, 100% = fully denoised. Default: 100%")
        ns_row.addWidget(self._ns_mix)
        self._ns_mix_label = QLabel(f"{int(config.clip_audio_ns_mix * 100)}%")
        self._ns_mix_label.setFixedWidth(40)
        ns_row.addWidget(self._ns_mix_label)
        self._ns_mix.valueChanged.connect(lambda v: self._ns_mix_label.setText(f"{v}%"))
        layout.addLayout(ns_row)

        self._add_separator(layout)

        # ---- Noise Gate ----
        gate_label = QLabel("Noise Gate")
        gate_label.setStyleSheet("font-weight: bold; margin-top: 2px;")
        layout.addWidget(gate_label)

        gate_desc = QLabel("Reduces audio below a threshold (agate).")
        gate_desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(gate_desc)

        self._gate_enabled = QCheckBox("Enabled")
        self._gate_enabled.setChecked(config.clip_audio_noise_gate)
        layout.addWidget(self._gate_enabled)

        gate_grid = QGridLayout()
        gate_grid.setColumnMinimumWidth(0, 130)
        gate_grid.addWidget(QLabel("Threshold:"), 0, 0)
        self._gate_threshold = QDoubleSpinBox()
        self._gate_threshold.setRange(0.001, 1.0)
        self._gate_threshold.setSingleStep(0.005)
        self._gate_threshold.setDecimals(3)
        self._gate_threshold.setValue(config.clip_audio_gate_threshold)
        self._gate_threshold.setToolTip(
            "Linear amplitude (0-1) below which the gate reduces signal.\n"
            "Lower = only gate near-silence. Higher = gate more aggressively.\n"
            "Default: 0.01 (~-40 dB)"
        )
        gate_grid.addWidget(self._gate_threshold, 0, 1)

        gate_grid.addWidget(QLabel("Ratio:"), 1, 0)
        self._gate_ratio = QDoubleSpinBox()
        self._gate_ratio.setRange(1.0, 20.0)
        self._gate_ratio.setSingleStep(0.5)
        self._gate_ratio.setDecimals(1)
        self._gate_ratio.setValue(config.clip_audio_gate_ratio)
        self._gate_ratio.setToolTip(
            "How aggressively signal below threshold is reduced.\n"
            "2 = gentle, 10+ = hard gate. Default: 10.0"
        )
        gate_grid.addWidget(self._gate_ratio, 1, 1)

        gate_grid.addWidget(QLabel("Attack (ms):"), 2, 0)
        self._gate_attack = QDoubleSpinBox()
        self._gate_attack.setRange(0.1, 500.0)
        self._gate_attack.setSingleStep(1.0)
        self._gate_attack.setDecimals(1)
        self._gate_attack.setValue(config.clip_audio_gate_attack)
        self._gate_attack.setToolTip("How fast the gate opens. Default: 10 ms")
        gate_grid.addWidget(self._gate_attack, 2, 1)

        gate_grid.addWidget(QLabel("Release (ms):"), 3, 0)
        self._gate_release = QDoubleSpinBox()
        self._gate_release.setRange(10.0, 5000.0)
        self._gate_release.setSingleStep(10.0)
        self._gate_release.setDecimals(1)
        self._gate_release.setValue(config.clip_audio_gate_release)
        self._gate_release.setToolTip("How fast the gate closes. Default: 100 ms")
        gate_grid.addWidget(self._gate_release, 3, 1)
        layout.addLayout(gate_grid)

        self._add_separator(layout)

        # ---- Compressor ----
        comp_label = QLabel("Compressor")
        comp_label.setStyleSheet("font-weight: bold; margin-top: 2px;")
        layout.addWidget(comp_label)

        comp_desc = QLabel("Dynamic range compression (acompressor).")
        comp_desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(comp_desc)

        self._comp_enabled = QCheckBox("Enabled")
        self._comp_enabled.setChecked(config.clip_audio_compressor)
        layout.addWidget(self._comp_enabled)

        comp_grid = QGridLayout()
        comp_grid.setColumnMinimumWidth(0, 130)
        comp_grid.addWidget(QLabel("Threshold (dB):"), 0, 0)
        self._comp_threshold = QDoubleSpinBox()
        self._comp_threshold.setRange(-60.0, 0.0)
        self._comp_threshold.setSingleStep(1.0)
        self._comp_threshold.setDecimals(1)
        self._comp_threshold.setValue(config.clip_audio_comp_threshold)
        self._comp_threshold.setToolTip("Level above which compression starts. Default: -20 dB")
        comp_grid.addWidget(self._comp_threshold, 0, 1)

        comp_grid.addWidget(QLabel("Ratio:"), 1, 0)
        self._comp_ratio = QDoubleSpinBox()
        self._comp_ratio.setRange(1.0, 20.0)
        self._comp_ratio.setSingleStep(0.5)
        self._comp_ratio.setDecimals(1)
        self._comp_ratio.setValue(config.clip_audio_comp_ratio)
        self._comp_ratio.setToolTip("Compression ratio (e.g. 4:1). Default: 4.0")
        comp_grid.addWidget(self._comp_ratio, 1, 1)

        comp_grid.addWidget(QLabel("Attack (ms):"), 2, 0)
        self._comp_attack = QDoubleSpinBox()
        self._comp_attack.setRange(0.1, 500.0)
        self._comp_attack.setSingleStep(1.0)
        self._comp_attack.setDecimals(1)
        self._comp_attack.setValue(config.clip_audio_comp_attack)
        self._comp_attack.setToolTip("How fast the compressor reacts. Default: 5 ms")
        comp_grid.addWidget(self._comp_attack, 2, 1)

        comp_grid.addWidget(QLabel("Release (ms):"), 3, 0)
        self._comp_release = QDoubleSpinBox()
        self._comp_release.setRange(10.0, 5000.0)
        self._comp_release.setSingleStep(10.0)
        self._comp_release.setDecimals(1)
        self._comp_release.setValue(config.clip_audio_comp_release)
        self._comp_release.setToolTip("How fast the compressor releases. Default: 100 ms")
        comp_grid.addWidget(self._comp_release, 3, 1)
        layout.addLayout(comp_grid)

        self._add_separator(layout)

        # ---- Audio Check ----
        check_row = QHBoxLayout()
        self._check_btn = QPushButton("Audio Check")
        self._check_btn.setToolTip(
            "Play back your microphone through the speakers\n"
            "with the current filters and gain applied."
        )
        self._check_btn.clicked.connect(self._toggle_check)
        check_row.addWidget(self._check_btn)
        self._level_bar = _LevelBar()
        check_row.addWidget(self._level_bar)
        # Error label (hidden by default, replaces meter on failure)
        self._check_error = QLabel("")
        self._check_error.setStyleSheet("color: #ff6b6b; font-size: 11px;")
        self._check_error.hide()
        check_row.addWidget(self._check_error)
        check_row.addStretch()
        layout.addLayout(check_row)

        # ---- Live-update: restart audio check + meter when settings change ----
        self._vol_slider.valueChanged.connect(self._schedule_restart)
        self._ns_enabled.toggled.connect(self._schedule_restart)
        self._ns_mix.valueChanged.connect(self._schedule_restart)
        self._gate_enabled.toggled.connect(self._schedule_restart)
        self._gate_threshold.valueChanged.connect(self._schedule_restart)
        self._gate_ratio.valueChanged.connect(self._schedule_restart)
        self._gate_attack.valueChanged.connect(self._schedule_restart)
        self._gate_release.valueChanged.connect(self._schedule_restart)
        self._comp_enabled.toggled.connect(self._schedule_restart)
        self._comp_threshold.valueChanged.connect(self._schedule_restart)
        self._comp_ratio.valueChanged.connect(self._schedule_restart)
        self._comp_attack.valueChanged.connect(self._schedule_restart)
        self._comp_release.valueChanged.connect(self._schedule_restart)

        # ---- Buttons ----
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        reset_btn = QPushButton("Reset All to Defaults")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("accentButton")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        # Start filtered mic level meter
        self._start_meter()

    # --- Filtered level meter ---

    def _start_meter(self) -> None:
        """Start the filtered mic meter pipeline."""
        self._stop_meter()
        try:
            self._filtered_meter = _FilteredMicMeter(
                mic_device=self._config.clip_mic_device or None,
                mic_gain=self._vol_slider.value() / 100.0,
                filters=self._get_filter_dict(),
                ffmpeg_path=self._config.ffmpeg_path,
            )
            self._filtered_meter.start()
        except Exception as e:
            log.debug("Could not start filtered meter: %s", e)
            return

        self._meter_timer = QTimer(self)
        self._meter_timer.setInterval(_METER_UPDATE_MS)
        self._meter_timer.timeout.connect(self._update_meter)
        self._meter_timer.start()

    def _stop_meter(self) -> None:
        """Stop the filtered mic meter."""
        if self._meter_timer is not None:
            self._meter_timer.stop()
            self._meter_timer = None
        if self._filtered_meter is not None:
            try:
                self._filtered_meter.stop()
            except Exception:
                pass
            self._filtered_meter = None

    def _restart_meter(self) -> None:
        """Restart the filtered meter with current settings."""
        self._start_meter()

    def _schedule_meter_restart(self) -> None:
        """Debounced restart of the filtered meter."""
        self._meter_restart_timer.start()

    def _update_meter(self) -> None:
        """Poll the filtered meter and update the level bar."""
        if self._filtered_meter is None:
            return
        peak = self._filtered_meter.peak
        level = min(1.0, peak * 2.0) if peak > 0 else 0.0
        self._level_bar.set_level(level)

    # --- Helpers ---

    def _add_separator(self, layout):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

    def _on_vol_changed(self, value):
        self._vol_label.setText(f"{value}%")

    def _schedule_restart(self):
        """Debounce: restart audio check and meter after settings change."""
        if self._audio_check and self._audio_check.running:
            self._restart_timer.start()
        self._meter_restart_timer.start()

    def _restart_check(self):
        """Stop current audio check and start a new one with updated settings."""
        if not (self._audio_check and self._audio_check.running):
            return
        self._audio_check.stop()
        self._audio_check = None
        # Re-use _toggle_check which starts a fresh check
        self._check_btn.setText("Audio Check")
        self._clear_check_error()
        self._toggle_check()

    def _reset(self):
        from ...capture.constants import (
            DEFAULT_NS_MIX,
            DEFAULT_GATE_THRESHOLD, DEFAULT_GATE_RATIO,
            DEFAULT_GATE_ATTACK, DEFAULT_GATE_RELEASE,
            DEFAULT_COMP_THRESHOLD, DEFAULT_COMP_RATIO,
            DEFAULT_COMP_ATTACK, DEFAULT_COMP_RELEASE,
        )
        self._vol_slider.setValue(100)
        self._ns_enabled.setChecked(True)
        self._ns_mix.setValue(int(DEFAULT_NS_MIX * 100))
        self._gate_enabled.setChecked(True)
        self._gate_threshold.setValue(DEFAULT_GATE_THRESHOLD)
        self._gate_ratio.setValue(DEFAULT_GATE_RATIO)
        self._gate_attack.setValue(DEFAULT_GATE_ATTACK)
        self._gate_release.setValue(DEFAULT_GATE_RELEASE)
        self._comp_enabled.setChecked(True)
        self._comp_threshold.setValue(DEFAULT_COMP_THRESHOLD)
        self._comp_ratio.setValue(DEFAULT_COMP_RATIO)
        self._comp_attack.setValue(DEFAULT_COMP_ATTACK)
        self._comp_release.setValue(DEFAULT_COMP_RELEASE)

    def _get_filter_dict(self) -> dict:
        """Build the current filter settings dict from the UI."""
        return {
            "noise_suppression": self._ns_enabled.isChecked(),
            "noise_gate": self._gate_enabled.isChecked(),
            "compressor": self._comp_enabled.isChecked(),
            "ns_mix": self._ns_mix.value() / 100.0,
            "gate_threshold": self._gate_threshold.value(),
            "gate_ratio": self._gate_ratio.value(),
            "gate_attack": self._gate_attack.value(),
            "gate_release": self._gate_release.value(),
            "comp_threshold": self._comp_threshold.value(),
            "comp_ratio": self._comp_ratio.value(),
            "comp_attack": self._comp_attack.value(),
            "comp_release": self._comp_release.value(),
        }

    def _show_check_error(self, msg: str) -> None:
        """Show error text in place of the level bar."""
        self._level_bar.hide()
        self._check_error.setText(msg)
        self._check_error.show()

    def _clear_check_error(self) -> None:
        """Hide error text and restore the level bar."""
        self._check_error.hide()
        self._check_error.setText("")
        self._level_bar.show()

    def _toggle_check(self):
        """Toggle real-time mic -> filters -> speaker passthrough."""
        if self._audio_check and self._audio_check.running:
            self._audio_check.stop()
            self._audio_check = None
            self._check_btn.setText("Audio Check")
            return

        self._clear_check_error()

        try:
            from ...capture.audio_check import AudioCheck
            self._audio_check = AudioCheck(
                mic_device=self._config.clip_mic_device or None,
                mic_gain=self._vol_slider.value() / 100.0,
                filters=self._get_filter_dict(),
                ffmpeg_path=self._config.ffmpeg_path,
            )
        except Exception as e:
            log.error("Audio check failed: %s", e)
            self._show_check_error(f"Error: {e}")
            return

        # Start in a background thread to avoid blocking the UI
        # (ensure_ffmpeg may download FFmpeg on first use)
        self._check_btn.setEnabled(False)
        threading.Thread(
            target=self._start_audio_check_bg, daemon=True,
            name="audio-check-start",
        ).start()

    def _start_audio_check_bg(self):
        """Background thread: start audio check (may download FFmpeg)."""
        try:
            self._audio_check.start()
            self._check_started.emit()
        except Exception as e:
            log.error("Audio check failed: %s", e)
            self._check_failed.emit(str(e))

    def _on_check_started(self):
        """Slot: audio check started successfully (runs on UI thread)."""
        self._check_btn.setEnabled(True)
        self._check_btn.setText("Stop Check")

    def _on_check_failed(self, error: str):
        """Slot: audio check failed to start (runs on UI thread)."""
        self._check_btn.setEnabled(True)
        self._show_check_error(f"Error: {error}")

    def _stop_check(self):
        if self._audio_check and self._audio_check.running:
            self._audio_check.stop()
            self._audio_check = None

    def _cancel(self):
        self._stop_check()
        self._stop_meter()
        self.reject()

    def _save(self):
        self._stop_check()
        self._stop_meter()

        self._config.clip_audio_mic_gain = self._vol_slider.value() / 100.0

        self._config.clip_audio_noise_suppression = self._ns_enabled.isChecked()
        self._config.clip_audio_ns_mix = self._ns_mix.value() / 100.0

        self._config.clip_audio_noise_gate = self._gate_enabled.isChecked()
        self._config.clip_audio_gate_threshold = self._gate_threshold.value()
        self._config.clip_audio_gate_ratio = self._gate_ratio.value()
        self._config.clip_audio_gate_attack = self._gate_attack.value()
        self._config.clip_audio_gate_release = self._gate_release.value()

        self._config.clip_audio_compressor = self._comp_enabled.isChecked()
        self._config.clip_audio_comp_threshold = self._comp_threshold.value()
        self._config.clip_audio_comp_ratio = self._comp_ratio.value()
        self._config.clip_audio_comp_attack = self._comp_attack.value()
        self._config.clip_audio_comp_release = self._comp_release.value()

        save_config(self._config, self._config_path)
        self._event_bus.publish(EVENT_CONFIG_CHANGED, self._config)
        self.accept()

    def closeEvent(self, event):
        self._stop_check()
        self._stop_meter()
        super().closeEvent(event)
