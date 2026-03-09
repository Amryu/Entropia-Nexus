"""FFmpeg-based video clip writer — muxes frames + audio + webcam into MP4."""

import io
import os
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.logger import get_logger
from .constants import (
    AUDIO_CHANNELS,
    AUDIO_SAMPLE_RATE,
    BITRATE_TABLE,
    RESOLUTION_PRESETS,
    WEBCAM_OVERLAY_MARGIN,
    WEBCAM_OVERLAY_SCALE,
)
from .ffmpeg import ensure_ffmpeg
from .screenshot import apply_blur_regions

log = get_logger("ClipWriter")


def _write_wav(pcm: np.ndarray, path: str, sample_rate: int = AUDIO_SAMPLE_RATE,
               channels: int = AUDIO_CHANNELS) -> None:
    """Write float32 PCM data to a WAV file."""
    # Convert float32 [-1, 1] to int16
    int16_data = np.clip(pcm * 32767, -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(int16_data.tobytes())


def _build_audio_filter(filters: dict) -> str:
    """Build FFmpeg audio filter chain from settings."""
    parts = []
    if filters.get("noise_suppression"):
        parts.append("afftdn=nf=-25")
    if filters.get("noise_gate"):
        parts.append("agate=threshold=0.01:ratio=2:attack=10:release=100")
    if filters.get("compressor"):
        parts.append("acompressor=threshold=-20dB:ratio=4:attack=5:release=100")
    return ",".join(parts) if parts else ""


def _build_video_filter(
    resolution: str,
    blur_regions: list[dict],
    webcam_frame: np.ndarray | None,
    webcam_position: str,
    frame_w: int,
    frame_h: int,
) -> str:
    """Build FFmpeg video filter chain."""
    filters = []

    # Blur regions (applied as drawbox with blur effect)
    # Using boxblur on specific regions via crop+overlay
    # For simplicity, we apply blur in the frame data before piping to FFmpeg
    # (see below in write_clip)

    # Resolution scaling
    target = RESOLUTION_PRESETS.get(resolution)
    if target:
        tw, th = target
        filters.append(f"scale={tw}:{th}:flags=lanczos")

    return ",".join(filters) if filters else ""


def write_clip(
    frames: list[tuple[float, bytes]],
    audio_pcm: np.ndarray | None,
    webcam_frame: np.ndarray | None,
    output_path: Path,
    fps: int = 30,
    resolution: str = "source",
    bitrate: str = "medium",
    blur_regions: list[dict] | None = None,
    audio_filters: dict | None = None,
    webcam_position: str = "bottom_right",
    ffmpeg_path: str = "",
) -> None:
    """Encode a video clip from buffered frames + optional audio.

    This runs synchronously (intended to be called from a daemon thread).

    Args:
        frames: List of (timestamp, jpeg_bytes) from the frame buffer.
        audio_pcm: Optional float32 PCM array (samples, channels).
        webcam_frame: Optional single webcam frame for overlay.
        output_path: Where to write the MP4.
        fps: Target frame rate.
        resolution: Resolution preset key.
        bitrate: Bitrate preset key.
        blur_regions: List of normalized blur region dicts.
        audio_filters: Dict of audio filter toggles.
        webcam_position: Corner for webcam overlay.
        ffmpeg_path: Config override for FFmpeg binary path.
    """
    if cv2 is None:
        raise RuntimeError("OpenCV is required for video clip encoding")

    # Find FFmpeg
    ffmpeg = ensure_ffmpeg(ffmpeg_path)
    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg not found. Please install FFmpeg or configure its path in Settings."
        )

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine frame dimensions from first frame
    first_jpeg = frames[0][1]
    first_frame = cv2.imdecode(
        np.frombuffer(first_jpeg, dtype=np.uint8), cv2.IMREAD_COLOR,
    )
    if first_frame is None:
        raise RuntimeError("Failed to decode first frame")
    frame_h, frame_w = first_frame.shape[:2]

    # Look up bitrate
    bitrate_val = BITRATE_TABLE.get((resolution, bitrate), "8M")

    # Build FFmpeg command
    cmd = [ffmpeg, "-y"]

    # Video input: raw BGR frames piped via stdin
    cmd.extend([
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{frame_w}x{frame_h}",
        "-r", str(fps),
        "-i", "pipe:0",
    ])

    # Audio input (if available)
    temp_wav = None
    if audio_pcm is not None and len(audio_pcm) > 0:
        temp_wav = tempfile.NamedTemporaryFile(
            suffix=".wav", delete=False,
        )
        _write_wav(audio_pcm, temp_wav.name)
        temp_wav.close()
        cmd.extend(["-i", temp_wav.name])

    # Video encoding
    vf_parts = []

    # Resolution scaling
    target_res = RESOLUTION_PRESETS.get(resolution)
    if target_res:
        tw, th = target_res
        vf_parts.append(f"scale={tw}:{th}:flags=lanczos")

    if vf_parts:
        cmd.extend(["-vf", ",".join(vf_parts)])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-b:v", bitrate_val,
        "-pix_fmt", "yuv420p",
    ])

    # Audio encoding
    if temp_wav:
        af_str = _build_audio_filter(audio_filters or {})
        if af_str:
            cmd.extend(["-af", af_str])
        cmd.extend(["-c:a", "aac", "-b:a", "128k"])
    else:
        cmd.extend(["-an"])

    # Output
    cmd.extend([str(output_path)])

    log.info("Encoding clip: %d frames, %s, %s bitrate -> %s",
             len(frames), resolution, bitrate_val, output_path)

    # Run FFmpeg
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Pipe frames
        for ts, jpeg_bytes in frames:
            frame_bgr = cv2.imdecode(
                np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR,
            )
            if frame_bgr is None:
                continue

            # Apply blur regions
            if blur_regions:
                frame_bgr = apply_blur_regions(frame_bgr, blur_regions)

            # Composite webcam overlay
            if webcam_frame is not None:
                frame_bgr = _composite_webcam(
                    frame_bgr, webcam_frame, webcam_position,
                )

            # Ensure consistent frame size
            fh, fw = frame_bgr.shape[:2]
            if fw != frame_w or fh != frame_h:
                frame_bgr = cv2.resize(frame_bgr, (frame_w, frame_h))

            proc.stdin.write(frame_bgr.tobytes())

        proc.stdin.close()
        stdout, stderr = proc.communicate(timeout=120)

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")[-500:]
            raise RuntimeError(f"FFmpeg exited with code {proc.returncode}: {err_msg}")

    finally:
        # Clean up temp audio file
        if temp_wav:
            try:
                os.unlink(temp_wav.name)
            except OSError:
                pass


def _composite_webcam(
    frame: np.ndarray,
    webcam: np.ndarray,
    position: str,
) -> np.ndarray:
    """Overlay a webcam frame onto a corner of the main frame."""
    fh, fw = frame.shape[:2]
    target_w = int(fw * WEBCAM_OVERLAY_SCALE)
    wh, ww = webcam.shape[:2]
    target_h = int(target_w * wh / ww)

    resized = cv2.resize(webcam, (target_w, target_h))
    margin = WEBCAM_OVERLAY_MARGIN

    if position == "top_left":
        x, y = margin, margin
    elif position == "top_right":
        x, y = fw - target_w - margin, margin
    elif position == "bottom_left":
        x, y = margin, fh - target_h - margin
    else:  # bottom_right
        x, y = fw - target_w - margin, fh - target_h - margin

    # Ensure bounds
    x = max(0, min(x, fw - target_w))
    y = max(0, min(y, fh - target_h))

    result = frame.copy()
    result[y:y + target_h, x:x + target_w] = resized
    return result
