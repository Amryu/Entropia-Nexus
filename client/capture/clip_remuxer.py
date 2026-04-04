"""Instant clip save via segment concatenation and audio muxing.

Concatenates pre-encoded H.264 segments and muxes audio using
``-c:v copy`` — no video re-encoding.  Typical runtime: 100-500ms.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.logger import get_logger
from .audio_utils import apply_gain, build_mic_filter, write_wav
from .constants import get_ffmpeg_flags
from .ffmpeg import find_rnnoise_model
from .segment_buffer import SegmentBuffer, SegmentInfo

log = get_logger("ClipRemuxer")


def remux_clip(
    segments: list[SegmentInfo],
    audio_pcm: np.ndarray | None,
    output_path,
    ffmpeg_path: str,
    clip_start: float,
    clip_end: float,
    mic_pcm: np.ndarray | None = None,
    mic_filters: dict | None = None,
    game_gain: float = 1.0,
    mic_gain: float = 1.0,
    encode_priority: str = "below_normal",
    segment_buffer: SegmentBuffer | None = None,
    thumb_time: float = 0,
) -> None:
    """Concatenate segments and mux audio into a final MP4.

    This runs synchronously (intended to be called from a daemon thread).
    Video is copied (``-c:v copy``), only audio is encoded.

    Args:
        segments: Ordered list of SegmentInfo covering the clip time range.
        audio_pcm: Optional float32 PCM — system/game audio.
        output_path: Where to write the final MP4.
        ffmpeg_path: Path to the FFmpeg binary.
        clip_start: Monotonic timestamp of desired clip start.
        clip_end: Monotonic timestamp of desired clip end.
        mic_pcm: Optional float32 PCM — microphone audio.
        mic_filters: Mic filter config dict (noise suppression, gate, compressor).
        game_gain: Gain multiplier for system audio.
        mic_gain: Gain multiplier for mic audio.
        encode_priority: FFmpeg process priority.
        segment_buffer: SegmentBuffer for thumbnail extraction.
        thumb_time: Monotonic timestamp for thumbnail frame.
    """
    if not segments:
        raise ValueError("No segments to remux")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_name(f".{output_path.stem}.remux{output_path.suffix}")

    # Apply gains
    has_game = audio_pcm is not None and len(audio_pcm) > 0
    has_mic = mic_pcm is not None and len(mic_pcm) > 0
    if has_game:
        audio_pcm = apply_gain(audio_pcm, game_gain)
    if has_mic:
        mic_pcm = apply_gain(mic_pcm, mic_gain)

    # Calculate trim points relative to first segment
    trim_start = max(0, clip_start - segments[0].start_time)
    duration = clip_end - clip_start

    # Build concat list file
    concat_file = None
    temp_game_wav = None
    temp_mic_wav = None
    remux_done = False

    try:
        concat_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, prefix="concat_",
        )
        for seg in segments:
            # FFmpeg concat requires forward slashes even on Windows
            safe_path = str(seg.path).replace("\\", "/")
            concat_file.write(f"file '{safe_path}'\n")
        concat_file.close()

        cmd = [ffmpeg_path, "-y"]

        # Video input: concat demuxer
        cmd.extend([
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file.name,
        ])

        # Audio inputs
        if has_game:
            temp_game_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            write_wav(audio_pcm, temp_game_wav.name)
            temp_game_wav.close()
            cmd.extend(["-i", temp_game_wav.name])

        if has_mic:
            temp_mic_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            write_wav(mic_pcm, temp_mic_wav.name)
            temp_mic_wav.close()
            cmd.extend(["-i", temp_mic_wav.name])

        # Trim to exact clip boundaries
        if trim_start > 0.05:
            cmd.extend(["-ss", f"{trim_start:.3f}"])
        if duration > 0:
            cmd.extend(["-t", f"{duration:.3f}"])

        # Video: copy (no re-encoding)
        cmd.extend(["-c:v", "copy"])

        # Audio encoding
        rnnoise_model = find_rnnoise_model() if (mic_filters or {}).get("noise_suppression") else None
        if (mic_filters or {}).get("noise_suppression") and not rnnoise_model:
            log.warning("Noise suppression requested but RNNoise model not found — skipping")
        mic_af = build_mic_filter(mic_filters or {}, rnnoise_model=rnnoise_model)

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
        else:
            cmd.extend(["-an"])

        cmd.extend(["-movflags", "+faststart", str(temp_output)])

        log.info("Remuxing clip: %d segments, %.1fs -> %s",
                 len(segments), duration, output_path)

        # Set cwd to model directory so arnndn can find the model
        ffmpeg_cwd = os.path.dirname(rnnoise_model) if rnnoise_model else None

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=60,
            cwd=ffmpeg_cwd,
            **get_ffmpeg_flags(encode_priority),
        )

        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[-500:]
            raise RuntimeError(f"Remux failed (exit {result.returncode}): {err}")

        temp_output.replace(output_path)
        remux_done = True

        # Thumbnail
        _generate_thumbnail(output_path, segment_buffer, thumb_time, segments)

    finally:
        for tmp in (concat_file, temp_game_wav, temp_mic_wav):
            if tmp:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass
        if not remux_done:
            try:
                if temp_output.exists():
                    temp_output.unlink()
            except OSError:
                pass


def _generate_thumbnail(
    output_path: Path,
    segment_buffer: SegmentBuffer | None,
    thumb_time: float,
    segments: list[SegmentInfo],
) -> None:
    """Save a thumbnail alongside the clip."""
    if cv2 is None:
        return
    try:
        thumb_path = output_path.with_suffix(".thumb.jpg")
        frame = None

        # Try extracting from segment buffer at the requested time
        if segment_buffer and thumb_time > 0:
            frame = segment_buffer.get_thumbnail_frame(thumb_time)

        # Fallback: read first frame from the output MP4
        if frame is None:
            cap = cv2.VideoCapture(str(output_path))
            if cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    frame = None
                cap.release()

        if frame is not None:
            th, tw = frame.shape[:2]
            scale = min(320 / tw, 200 / th, 1.0)
            if scale < 1.0:
                frame = cv2.resize(
                    frame,
                    (int(tw * scale), int(th * scale)),
                    interpolation=cv2.INTER_AREA,
                )
            cv2.imwrite(str(thumb_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    except Exception as e:
        log.debug("Thumbnail generation failed: %s", e)
