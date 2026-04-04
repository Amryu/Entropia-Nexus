"""Shared audio utilities — WAV writing, gain, and FFmpeg mic filter chain."""

import os
import wave

import numpy as np

from .constants import AUDIO_CHANNELS, AUDIO_SAMPLE_RATE


def write_wav(pcm: np.ndarray, path: str, sample_rate: int = AUDIO_SAMPLE_RATE,
              channels: int = AUDIO_CHANNELS) -> None:
    """Write float32 PCM data to a WAV file.

    *channels* is used as a fallback; the actual channel count is inferred
    from *pcm*'s shape so the WAV header always matches the data (important
    when WASAPI loopback negotiates a different count than the default).
    """
    if pcm.size == 0:
        return
    actual_channels = pcm.shape[1] if pcm.ndim > 1 else 1
    # Convert float32 [-1, 1] to int16
    int16_data = np.clip(pcm * np.float32(32767), -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(actual_channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(int16_data.tobytes())


def apply_gain(pcm: np.ndarray, gain: float) -> np.ndarray:
    """Apply gain to PCM audio data."""
    if gain == 1.0:
        return pcm
    return np.clip(pcm * gain, -1.0, 1.0).astype(np.float32)


def _safe_float(val, default: float) -> float:
    """Coerce to float, falling back to *default* on any failure."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def build_mic_filter(filters: dict, rnnoise_model: str | None = None) -> str:
    """Build FFmpeg audio filter chain for the microphone track.

    Accepts a dict with boolean toggles and parameter values.
    All numeric parameters are coerced to float to prevent injection
    of arbitrary FFmpeg filter options via config values.
    """
    parts = []
    if filters.get("noise_suppression") and rnnoise_model:
        mix = _safe_float(filters.get("ns_mix"), 1.0)
        # Use just the filename — FFmpeg cwd must be set to the model directory
        # because Windows drive letters contain ':' which FFmpeg's filter parser
        # treats as an option separator and cannot be escaped.
        model_name = os.path.basename(rnnoise_model)
        parts.append(f"arnndn=m={model_name}:mix={mix:.4f}")
    if filters.get("noise_gate"):
        thresh = _safe_float(filters.get("gate_threshold"), 0.01)
        ratio = _safe_float(filters.get("gate_ratio"), 2.0)
        attack = _safe_float(filters.get("gate_attack"), 10.0)
        release = _safe_float(filters.get("gate_release"), 100.0)
        parts.append(
            f"agate=threshold={thresh:.6f}:ratio={ratio:.2f}"
            f":attack={attack:.2f}:release={release:.2f}"
        )
    if filters.get("compressor"):
        thresh = _safe_float(filters.get("comp_threshold"), -20.0)
        ratio = _safe_float(filters.get("comp_ratio"), 4.0)
        attack = _safe_float(filters.get("comp_attack"), 5.0)
        release = _safe_float(filters.get("comp_release"), 100.0)
        parts.append(
            f"acompressor=threshold={thresh:.2f}dB:ratio={ratio:.2f}"
            f":attack={attack:.2f}:release={release:.2f}"
        )
    return ",".join(parts) if parts else ""
