"""Rolling audio ring buffer using sounddevice for WASAPI loopback capture."""

import threading
from collections import deque

import numpy as np

from ..core.logger import get_logger
from .constants import AUDIO_CHANNELS, AUDIO_DTYPE, AUDIO_SAMPLE_RATE

log = get_logger("AudioBuffer")

# Maximum buffer seconds (slightly longer than video to cover alignment)
MAX_AUDIO_BUFFER_S = 65

try:
    import sounddevice as sd
except ImportError:
    sd = None


class AudioBuffer:
    """Thread-safe rolling buffer of PCM audio captured via sounddevice.

    On Windows, uses WASAPI loopback to capture system audio.
    Memory: 48kHz stereo float32 = ~375KB/s, 20s = ~7.5MB.
    """

    def __init__(
        self,
        device=None,
        sample_rate: int = AUDIO_SAMPLE_RATE,
        channels: int = AUDIO_CHANNELS,
    ):
        if sd is None:
            raise ImportError("sounddevice is required for audio capture")

        self._sample_rate = sample_rate
        self._channels = channels
        self._device = device
        self._stream = None
        self._running = False

        # Rolling buffer of (monotonic_time, pcm_chunk) tuples
        # Each chunk is a short segment (~20-50ms) from the audio callback
        max_chunks = int(MAX_AUDIO_BUFFER_S * sample_rate / 1024) + 1
        self._buffer: deque[tuple[float, np.ndarray]] = deque(maxlen=max_chunks)
        self._lock = threading.Lock()

        # Device monitoring
        self._monitor_thread: threading.Thread | None = None
        self._last_default_device = None

    def start(self) -> None:
        """Start audio capture."""
        if self._running:
            return
        self._running = True
        self._open_stream()
        self._start_device_monitor()
        log.info("Audio capture started (device=%s, rate=%d)",
                 self._device or "default", self._sample_rate)

    def stop(self) -> None:
        """Stop audio capture and release resources."""
        self._running = False
        self._close_stream()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
            self._monitor_thread = None
        log.info("Audio capture stopped")

    def _open_stream(self) -> None:
        """Open the sounddevice input stream."""
        try:
            # On Windows, try WASAPI loopback for system audio
            extra_settings = None
            device = self._device

            if not device:
                # Use default output device as loopback source
                try:
                    default_output = sd.query_devices(kind="output")
                    if default_output:
                        device = default_output["name"]
                        # WASAPI loopback requires the output device name
                        extra_settings = sd.WasapiSettings(exclusive=False)
                except Exception:
                    pass

            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype=AUDIO_DTYPE,
                blocksize=1024,
                device=device,
                callback=self._audio_callback,
                extra_settings=extra_settings,
            )
            self._stream.start()
        except Exception as e:
            log.warning("Failed to open audio stream: %s", e)
            self._stream = None

    def _close_stream(self) -> None:
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice on the audio thread with new PCM data."""
        if status:
            log.debug("Audio status: %s", status)
        import time
        ts = time.monotonic()
        chunk = indata.copy()
        with self._lock:
            self._buffer.append((ts, chunk))

    def snapshot(
        self,
        start_time: float,
        end_time: float,
    ) -> np.ndarray | None:
        """Return concatenated PCM data for the given time range.

        Returns a float32 numpy array of shape (samples, channels), or None.
        """
        with self._lock:
            chunks = []
            for ts, data in self._buffer:
                if ts < start_time:
                    continue
                if ts > end_time:
                    break
                chunks.append(data)

        if not chunks:
            return None
        return np.concatenate(chunks, axis=0)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()

    # ------------------------------------------------------------------
    # Device enumeration and monitoring
    # ------------------------------------------------------------------

    @staticmethod
    def get_devices() -> list[dict]:
        """Return list of available audio devices for the settings UI."""
        if sd is None:
            return []
        try:
            devices = sd.query_devices()
            result = []
            for i, dev in enumerate(devices):
                result.append({
                    "index": i,
                    "name": dev["name"],
                    "max_input_channels": dev["max_input_channels"],
                    "max_output_channels": dev["max_output_channels"],
                    "hostapi": dev["hostapi"],
                })
            return result
        except Exception:
            return []

    def set_device(self, device) -> None:
        """Switch to a different audio device (restarts stream)."""
        self._device = device
        if self._running:
            self._close_stream()
            self._open_stream()

    def _start_device_monitor(self) -> None:
        """Start a thread that monitors for default device changes."""
        self._monitor_thread = threading.Thread(
            target=self._device_monitor_loop, daemon=True,
            name="audio-device-monitor",
        )
        self._monitor_thread.start()

    def _device_monitor_loop(self) -> None:
        """Poll for changes to the default audio device."""
        import time
        while self._running:
            try:
                if not self._device:  # Only monitor when using default device
                    current = sd.query_devices(kind="output")
                    current_name = current.get("name") if current else None
                    if (self._last_default_device is not None
                            and current_name != self._last_default_device):
                        log.info("Default audio device changed to: %s", current_name)
                        self._close_stream()
                        self._open_stream()
                    self._last_default_device = current_name
            except Exception:
                pass
            time.sleep(5)
