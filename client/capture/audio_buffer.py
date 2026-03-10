"""Rolling audio ring buffer using PyAudioWPatch for WASAPI loopback capture."""

import threading
from collections import deque

import numpy as np

from ..core.logger import get_logger
from .constants import AUDIO_CHANNELS, AUDIO_SAMPLE_RATE

log = get_logger("AudioBuffer")

# Maximum buffer seconds (slightly longer than video to cover alignment)
MAX_AUDIO_BUFFER_S = 65
BLOCK_SIZE = 1024

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    pyaudio = None

# Keep sounddevice for resolve_device_index() (used by audio_check,
# audio_filter_dialogs which open their own sounddevice streams)
# and for lightweight device-change monitoring.
try:
    import sounddevice as sd
except ImportError:
    sd = None


class AudioBuffer:
    """Thread-safe rolling buffer of PCM audio captured via PyAudioWPatch.

    In loopback mode (default), captures system audio via WASAPI loopback
    using dedicated ``[Loopback]`` virtual input devices.
    In mic mode (loopback=False), captures from an input device.
    Memory: 48kHz stereo float32 = ~375KB/s, 65s ~ 24MB.
    """

    def __init__(
        self,
        device=None,
        sample_rate: int = AUDIO_SAMPLE_RATE,
        channels: int = AUDIO_CHANNELS,
        loopback: bool = True,
    ):
        if pyaudio is None:
            raise ImportError("PyAudioWPatch is required for audio capture")

        self._sample_rate = sample_rate
        self._channels = channels
        self._device = device  # device name string or None for default
        self._loopback = loopback
        self._pa: pyaudio.PyAudio | None = None
        self._stream = None
        self._running = False

        max_chunks = int(MAX_AUDIO_BUFFER_S * sample_rate / BLOCK_SIZE) + 1
        self._buffer: deque[tuple[float, np.ndarray]] = deque(maxlen=max_chunks)
        self._lock = threading.Lock()

        # Device monitoring
        self._monitor_thread: threading.Thread | None = None
        self._last_default_device = None

    @property
    def channels(self) -> int:
        """Actual channel count (set from device on stream open)."""
        return self._channels

    @property
    def sample_rate(self) -> int:
        """Actual sample rate (set from device on stream open)."""
        return self._sample_rate

    def start(self) -> None:
        """Start audio capture."""
        if self._running:
            return
        self._running = True
        self._pa = pyaudio.PyAudio()
        self._open_stream()
        self._start_device_monitor()
        mode = "loopback" if self._loopback else "input"
        log.info("Audio capture started (%s, device=%s, rate=%d, ch=%d)",
                 mode, self._device or "default", self._sample_rate,
                 self._channels)

    def stop(self) -> None:
        """Stop audio capture and release resources."""
        self._running = False
        self._close_stream()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
            self._monitor_thread = None
        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None
        log.info("Audio capture stopped")

    # ------------------------------------------------------------------
    # Stream management
    # ------------------------------------------------------------------

    def _find_loopback_device(self, name: str | None) -> dict | None:
        """Find a WASAPI loopback device by output device name.

        If *name* is None, returns the default loopback device.
        Otherwise, finds the ``[Loopback]`` counterpart of the named
        output device.
        """
        if not name:
            try:
                return self._pa.get_default_wasapi_loopback()
            except (OSError, LookupError) as e:
                log.warning("No default loopback device: %s", e)
                return None

        # User selected a specific output device — find its [Loopback] twin.
        for dev in self._pa.get_loopback_device_info_generator():
            lb_name = dev["name"]
            base_name = lb_name.replace(" [Loopback]", "")
            if base_name == name or name in lb_name:
                return dev
        log.warning("No loopback device found for '%s'", name)
        return None

    def _find_input_device(self, name: str | None) -> dict | None:
        """Find a WASAPI input (mic) device by name."""
        if not name:
            try:
                return self._pa.get_default_wasapi_device(d_in=True)
            except (OSError, LookupError):
                return None

        for dev in self._pa.get_device_info_generator_by_host_api(
            host_api_type=pyaudio.paWASAPI,
        ):
            if dev["maxInputChannels"] <= 0:
                continue
            if dev.get("isLoopbackDevice", False):
                continue
            if dev["name"] == name or name in dev["name"]:
                return dev
        log.warning("No input device found for '%s'", name)
        return None

    def _open_stream(self) -> None:
        """Open a PyAudioWPatch input stream."""
        if self._pa is None:
            return

        if self._loopback:
            dev_info = self._find_loopback_device(self._device)
        else:
            dev_info = self._find_input_device(self._device)

        if dev_info is None:
            mode = "loopback" if self._loopback else "input"
            log.warning("No %s device available", mode)
            return

        channels = dev_info["maxInputChannels"]
        sample_rate = int(dev_info["defaultSampleRate"])
        dev_name = dev_info["name"]

        log.debug("Opening stream: device='%s' (idx=%d), ch=%d, rate=%d",
                  dev_name, dev_info["index"], channels, sample_rate)

        try:
            self._stream = self._pa.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=sample_rate,
                frames_per_buffer=BLOCK_SIZE,
                input=True,
                input_device_index=dev_info["index"],
                stream_callback=self._audio_callback,
            )
            self._channels = channels
            self._sample_rate = sample_rate
            # Resize buffer for actual sample rate
            max_chunks = int(MAX_AUDIO_BUFFER_S * sample_rate / BLOCK_SIZE) + 1
            self._buffer = deque(self._buffer, maxlen=max_chunks)
        except Exception as e:
            mode = "loopback" if self._loopback else "input"
            log.warning("Failed to open %s stream on '%s': %s",
                        mode, dev_name, e)
            self._stream = None

    def _close_stream(self) -> None:
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _audio_callback(self, in_data, frame_count, time_info, status_flags):
        """Called by PyAudioWPatch on the audio thread with new PCM data."""
        if status_flags:
            log.debug("Audio status flags: %d", status_flags)
        import time
        ts = time.monotonic()
        chunk = np.frombuffer(in_data, dtype=np.float32).reshape(
            -1, self._channels,
        ).copy()
        with self._lock:
            self._buffer.append((ts, chunk))
        return (None, pyaudio.paContinue)

    # ------------------------------------------------------------------
    # Buffer access
    # ------------------------------------------------------------------

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
    # Device enumeration
    # ------------------------------------------------------------------

    @staticmethod
    def get_output_devices() -> list[dict]:
        """Return list of audio output devices (for WASAPI loopback source).

        Excludes ``[Loopback]`` virtual devices — those are used internally.
        """
        if pyaudio is None:
            return []
        try:
            p = pyaudio.PyAudio()
            result = []
            for dev in p.get_device_info_generator_by_host_api(
                host_api_type=pyaudio.paWASAPI,
            ):
                if dev["maxOutputChannels"] <= 0:
                    continue
                if dev.get("isLoopbackDevice", False):
                    continue
                result.append({
                    "index": dev["index"],
                    "name": dev["name"],
                    "max_output_channels": dev["maxOutputChannels"],
                })
            p.terminate()
            return result
        except Exception:
            return []

    @staticmethod
    def get_input_devices() -> list[dict]:
        """Return list of audio input devices (microphones).

        Excludes ``[Loopback]`` virtual devices.
        """
        if pyaudio is None:
            return []
        try:
            p = pyaudio.PyAudio()
            result = []
            for dev in p.get_device_info_generator_by_host_api(
                host_api_type=pyaudio.paWASAPI,
            ):
                if dev["maxInputChannels"] <= 0:
                    continue
                if dev.get("isLoopbackDevice", False):
                    continue
                result.append({
                    "index": dev["index"],
                    "name": dev["name"],
                    "max_input_channels": dev["maxInputChannels"],
                })
            p.terminate()
            return result
        except Exception:
            return []

    @staticmethod
    def get_devices() -> list[dict]:
        """Return list of all WASAPI audio devices for the settings UI.

        Excludes ``[Loopback]`` virtual devices.
        """
        if pyaudio is None:
            return []
        try:
            p = pyaudio.PyAudio()
            result = []
            for dev in p.get_device_info_generator_by_host_api(
                host_api_type=pyaudio.paWASAPI,
            ):
                if dev.get("isLoopbackDevice", False):
                    continue
                result.append({
                    "index": dev["index"],
                    "name": dev["name"],
                    "max_input_channels": dev["maxInputChannels"],
                    "max_output_channels": dev["maxOutputChannels"],
                })
            p.terminate()
            return result
        except Exception:
            return []

    # ------------------------------------------------------------------
    # sounddevice helpers (for audio_check / audio_filter_dialogs)
    # ------------------------------------------------------------------

    @staticmethod
    def _wasapi_hostapi_index() -> int | None:
        """Return the host API index for WASAPI in sounddevice."""
        if sd is None:
            return None
        try:
            for i, api in enumerate(sd.query_hostapis()):
                if "WASAPI" in api.get("name", ""):
                    return i
        except Exception:
            pass
        return None

    @staticmethod
    def resolve_device_index(name: str | None, kind: str = "input") -> int | None:
        """Resolve a device name to its WASAPI device index for sounddevice.

        Used by audio_check.py and audio_filter_dialogs.py which open their
        own sounddevice streams for mic passthrough/metering.
        """
        if sd is None or not name:
            return None
        import sys
        if sys.platform != "win32":
            return name
        wasapi_idx = AudioBuffer._wasapi_hostapi_index()
        if wasapi_idx is None:
            return name
        try:
            is_output = kind == "output"
            channel_key = "max_output_channels" if is_output else "max_input_channels"
            devices = sd.query_devices()
            # Exact match first
            for i, dev in enumerate(devices):
                if dev.get("hostapi") != wasapi_idx:
                    continue
                if dev.get(channel_key, 0) <= 0:
                    continue
                if dev.get("name") == name:
                    return i
            # Substring match within WASAPI only
            for i, dev in enumerate(devices):
                if dev.get("hostapi") != wasapi_idx:
                    continue
                if dev.get(channel_key, 0) <= 0:
                    continue
                if name in dev.get("name", ""):
                    return i
        except Exception:
            pass
        return name

    # ------------------------------------------------------------------
    # Device switching and monitoring
    # ------------------------------------------------------------------

    def set_device(self, device) -> None:
        """Switch to a different audio device (restarts stream)."""
        self._device = device
        if self._running:
            self._close_stream()
            # Reinitialize PyAudio to refresh the device list
            if self._pa:
                try:
                    self._pa.terminate()
                except Exception:
                    pass
            self._pa = pyaudio.PyAudio()
            self._open_stream()

    def _start_device_monitor(self) -> None:
        """Start a thread that monitors for default device changes."""
        self._monitor_thread = threading.Thread(
            target=self._device_monitor_loop, daemon=True,
            name="audio-device-monitor",
        )
        self._monitor_thread.start()

    def _device_monitor_loop(self) -> None:
        """Poll for changes to the default audio device.

        Uses sounddevice (lightweight) to check the current default,
        then reinitializes the PyAudioWPatch stream if it changed.
        """
        import time
        kind = "output" if self._loopback else "input"
        while self._running:
            try:
                if not self._device and sd is not None:
                    current = sd.query_devices(kind=kind)
                    current_name = current.get("name") if current else None
                    if (self._last_default_device is not None
                            and current_name != self._last_default_device):
                        log.info("Default %s device changed to: %s",
                                 kind, current_name)
                        self._close_stream()
                        if self._pa:
                            try:
                                self._pa.terminate()
                            except Exception:
                                pass
                        self._pa = pyaudio.PyAudio()
                        self._open_stream()
                    self._last_default_device = current_name
            except Exception:
                pass
            time.sleep(5)
