"""Audio Check — real-time mic → FFmpeg filters → speaker passthrough.

Lets the user hear their microphone with the configured audio filters
and gain applied, for testing before recording.
"""

import subprocess
import threading

import numpy as np

from ..core.logger import get_logger
from .constants import AUDIO_CHANNELS, AUDIO_DTYPE, AUDIO_SAMPLE_RATE
from .ffmpeg import ensure_ffmpeg, ensure_rnnoise_model

log = get_logger("AudioCheck")

try:
    import sounddevice as sd
except ImportError:
    sd = None


class AudioCheck:
    """Real-time mic → FFmpeg filters → speaker passthrough.

    Opens a mic input stream, pipes audio through FFmpeg with the configured
    filters and gain, and plays the processed output through the speakers.
    """

    def __init__(
        self,
        mic_device=None,
        mic_gain: float = 1.0,
        filters: dict | None = None,
        ffmpeg_path: str = "",
        sample_rate: int = AUDIO_SAMPLE_RATE,
        channels: int = AUDIO_CHANNELS,
    ):
        if sd is None:
            raise ImportError("sounddevice is required for audio check")

        # Resolve device name → WASAPI index to avoid multi-API ambiguity
        from .audio_buffer import AudioBuffer
        self._mic_device = AudioBuffer.resolve_device_index(mic_device, kind="input")
        self._mic_gain = mic_gain
        self._filters = filters or {}
        self._ffmpeg_path = ffmpeg_path
        self._sample_rate = sample_rate
        self._channels = channels

        self._running = False
        self._input_stream = None
        self._output_stream = None
        self._ffmpeg_proc = None
        self._reader_thread = None
        self._writer_thread = None

    @property
    def running(self) -> bool:
        return self._running

    def _query_mic_channels(self) -> int:
        """Query the actual channel count supported by the mic device."""
        try:
            if self._mic_device:
                info = sd.query_devices(self._mic_device)
            else:
                info = sd.query_devices(kind="input")
            return min(self._channels, int(info.get("max_input_channels", self._channels)))
        except Exception:
            return self._channels

    def start(self) -> None:
        """Start the audio check passthrough."""
        if self._running:
            return
        self._running = True

        # Use the mic's native channel count to avoid WASAPI channel mismatch
        self._mic_channels = self._query_mic_channels()

        ffmpeg = ensure_ffmpeg(self._ffmpeg_path)
        if not ffmpeg:
            # No FFmpeg: direct passthrough with gain only
            self._start_direct()
            return

        # Resolve RNNoise model if noise suppression is enabled
        rnnoise_model = None
        if self._filters.get("noise_suppression"):
            rnnoise_model = ensure_rnnoise_model()

        # Build FFmpeg filter chain
        af_parts = []
        if self._mic_gain != 1.0:
            af_parts.append(f"volume={self._mic_gain}")
        if self._filters.get("noise_suppression") and rnnoise_model:
            mix = self._filters.get("ns_mix", 1.0)
            # Use just the filename — cwd is set to the model directory below
            import os
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

        # Spawn FFmpeg for real-time processing
        # Input uses mic's native channel count; output always stereo
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

        # Set cwd to model directory so arnndn can find it by filename
        # (Windows drive-letter colon breaks FFmpeg filter path parsing).
        import os
        ffmpeg_cwd = os.path.dirname(rnnoise_model) if rnnoise_model else None

        try:
            self._ffmpeg_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=ffmpeg_cwd,
            )
        except Exception as e:
            log.warning("Failed to start FFmpeg for audio check: %s", e)
            self._start_direct()
            return

        # Open mic input (use mic's native channel count)
        self._input_stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._mic_channels,
            dtype=AUDIO_DTYPE,
            blocksize=1024,
            device=self._mic_device or None,
            callback=self._mic_callback_ffmpeg,
        )

        # Open speaker output
        self._output_stream = sd.OutputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype=AUDIO_DTYPE,
            blocksize=1024,
        )

        self._input_stream.start()
        self._output_stream.start()

        # Reader thread: read from FFmpeg stdout and play
        self._reader_thread = threading.Thread(
            target=self._ffmpeg_reader_loop, daemon=True, name="audio-check-reader",
        )
        self._reader_thread.start()

        log.info("Audio check started (with FFmpeg filters)")

    def _start_direct(self) -> None:
        """Fallback: direct passthrough with gain only (no FFmpeg)."""
        self._input_stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._mic_channels,
            dtype=AUDIO_DTYPE,
            blocksize=1024,
            device=self._mic_device or None,
            callback=self._mic_callback_direct,
        )
        self._output_stream = sd.OutputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype=AUDIO_DTYPE,
            blocksize=1024,
        )
        self._input_stream.start()
        self._output_stream.start()
        log.info("Audio check started (direct passthrough, gain=%.2f)", self._mic_gain)

    def stop(self) -> None:
        """Stop the audio check."""
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

        if self._output_stream:
            try:
                self._output_stream.stop()
                self._output_stream.close()
            except Exception:
                pass
            self._output_stream = None

        log.info("Audio check stopped")

    def _mic_callback_ffmpeg(self, indata, frames, time_info, status):
        """Write mic data to FFmpeg stdin."""
        if not self._running or not self._ffmpeg_proc:
            return
        try:
            self._ffmpeg_proc.stdin.write(indata.tobytes())
        except Exception:
            pass

    def _mic_callback_direct(self, indata, frames, time_info, status):
        """Direct passthrough: apply gain and write to output."""
        if not self._running or not self._output_stream:
            return
        try:
            data = indata.copy()
            if self._mic_gain != 1.0:
                data = np.clip(data * self._mic_gain, -1.0, 1.0).astype(np.float32)
            # Convert mono → stereo if needed
            if data.shape[1] < self._channels:
                data = np.column_stack([data] * self._channels)
            self._output_stream.write(data)
        except Exception:
            pass

    def _ffmpeg_reader_loop(self) -> None:
        """Read processed audio from FFmpeg stdout and play through speakers."""
        bytes_per_sample = 4  # float32
        chunk_bytes = 1024 * self._channels * bytes_per_sample

        while self._running and self._ffmpeg_proc:
            try:
                data = self._ffmpeg_proc.stdout.read(chunk_bytes)
                if not data:
                    break
                arr = np.frombuffer(data, dtype=np.float32).reshape(-1, self._channels)
                if self._output_stream:
                    self._output_stream.write(arr)
            except Exception:
                break
