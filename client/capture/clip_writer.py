"""FFmpeg-based video clip writer — muxes frames + audio + webcam into MP4."""

import os
import subprocess
import tempfile

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.logger import get_logger
from .audio_utils import apply_gain, build_mic_filter, write_wav
from .constants import (
    BITRATE_TABLE,
    RESOLUTION_PRESETS,
    get_encode_thread_count,
    get_ffmpeg_flags,
    get_ffmpeg_scale_flag,
    get_interpolation,
)
from .ffmpeg import ensure_ffmpeg, find_rnnoise_model, get_encoder_args
from .screenshot import apply_blur_regions, compose_on_background
from .video_effects import composite_webcam

log = get_logger("ClipWriter")


def write_clip(
    frames: list[tuple[float, bytes, bytes | None]],
    audio_pcm: np.ndarray | None,
    output_path,
    fps: int = 30,
    resolution: str = "source",
    bitrate: str = "medium",
    blur_regions: list[dict] | None = None,
    mic_filters: dict | None = None,
    webcam_position_x: float = 0.88,
    webcam_position_y: float = 0.85,
    webcam_scale: float = 0.2,
    webcam_crop: dict | None = None,
    webcam_chroma: dict | None = None,
    ffmpeg_path: str = "",
    mic_pcm: np.ndarray | None = None,
    game_gain: float = 1.0,
    mic_gain: float = 1.0,
    background: np.ndarray | None = None,
    thumb_time: float = 0,
    scaling: str = "lanczos",
    on_progress=None,
    encode_priority: str = "normal",
    encode_threads: int = 0,
    video_encoder: str = "libx264",
) -> None:
    """Encode a video clip from buffered frames + optional audio.

    This runs synchronously (intended to be called from a daemon thread).

    Audio filters (noise suppression, noise gate, compressor) are applied
    only to the microphone track, not the system audio.

    Args:
        frames: List of (timestamp, jpeg_bytes, webcam_jpeg | None) from the
                frame buffer.  Each frame carries its own webcam snapshot.
        audio_pcm: Optional float32 PCM array (samples, channels) — game/system audio.
        output_path: Where to write the MP4.
        fps: Target frame rate.
        resolution: Resolution preset key.
        bitrate: Bitrate preset key.
        blur_regions: List of normalized blur region dicts.
        mic_filters: Dict of mic filter toggles + parameter values.
        webcam_position_x: Normalized X center for webcam overlay.
        webcam_position_y: Normalized Y center for webcam overlay.
        ffmpeg_path: Config override for FFmpeg binary path.
        mic_pcm: Optional float32 PCM array — microphone audio.
        game_gain: Gain multiplier for system audio (0.0-3.0).
        mic_gain: Gain multiplier for mic audio (0.0-3.0).
    """
    if cv2 is None:
        raise RuntimeError("OpenCV is required for video clip encoding")
    if not frames:
        raise ValueError("No frames to encode")

    from pathlib import Path
    output_path = Path(output_path)

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

    # When background compositing is active with a target resolution,
    # the output dimensions are the target (not the raw frame size).
    # The scale filter in FFmpeg is skipped; compositing is done in Python.
    has_bg = background is not None
    target_res = RESOLUTION_PRESETS.get(resolution)
    compose_bg = has_bg and target_res is not None
    if compose_bg:
        frame_w, frame_h = target_res

    # Apply gains to audio tracks
    has_game = audio_pcm is not None and len(audio_pcm) > 0
    has_mic = mic_pcm is not None and len(mic_pcm) > 0

    if has_game:
        audio_pcm = apply_gain(audio_pcm, game_gain)
    if has_mic:
        mic_pcm = apply_gain(mic_pcm, mic_gain)

    # Look up bitrate
    bitrate_val = BITRATE_TABLE.get((resolution, bitrate), "8M")

    # Compute effective FPS from actual frame timestamps for proper A/V sync.
    # The configured fps is the target rate, but actual capture timing varies.
    # Using the real rate ensures video duration matches the audio time window.
    effective_fps = fps
    if len(frames) >= 2:
        actual_duration = frames[-1][0] - frames[0][0]
        if actual_duration > 0:
            effective_fps = (len(frames) - 1) / actual_duration
            # Clamp to a sane range — timestamp anomalies can produce
            # extreme values that make FFmpeg produce broken output.
            effective_fps = max(1.0, min(effective_fps, fps * 2.0))

    # Build FFmpeg command
    cmd = [ffmpeg, "-y"]

    # Video input: raw BGR frames piped via stdin
    cmd.extend([
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{frame_w}x{frame_h}",
        "-r", str(effective_fps),
        "-i", "pipe:0",
    ])

    # Audio inputs — written as temp WAV files, cleaned up in the finally block.
    temp_game_wav = None
    temp_mic_wav = None
    temp_output = output_path.with_name(f".{output_path.stem}.encoding{output_path.suffix}")
    clip_done = False
    proc = None
    try:
        if has_game:
            temp_game_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            write_wav(audio_pcm, temp_game_wav.name)
            temp_game_wav.close()
            cmd.extend(["-i", temp_game_wav.name])  # input 1

        if has_mic:
            temp_mic_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            write_wav(mic_pcm, temp_mic_wav.name)
            temp_mic_wav.close()
            cmd.extend(["-i", temp_mic_wav.name])  # input 1 or 2

        # Video filter (skip FFmpeg scale when compositing background in Python).
        # Scale to fit within target while preserving aspect ratio (never upscale),
        # then pad with black bars to center the frame at exact target dimensions.
        vf_parts = []
        if target_res and not compose_bg:
            tw, th = target_res
            vf_parts.append(
                f"scale='min({tw},iw)':'min({th},ih)'"
                f":force_original_aspect_ratio=decrease:flags={get_ffmpeg_scale_flag(scaling)}"
            )
            vf_parts.append(f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black")
        if vf_parts:
            cmd.extend(["-vf", ",".join(vf_parts)])

        cmd.extend(get_encoder_args(
            video_encoder, bitrate_val,
            threads=encode_threads, realtime=False,
        ))

        # Audio encoding — filters apply to mic only
        rnnoise_model = find_rnnoise_model() if (mic_filters or {}).get("noise_suppression") else None
        if (mic_filters or {}).get("noise_suppression") and not rnnoise_model:
            log.warning("Noise suppression requested but RNNoise model not found — skipping")
        mic_af = build_mic_filter(mic_filters or {}, rnnoise_model=rnnoise_model)

        if has_game and has_mic:
            # Two separate audio tracks: game (track 1) + filtered mic (track 2)
            # Input indices: 0=video, 1=game, 2=mic
            if mic_af:
                mic_chain = f"[2:a]{mic_af}[mic_f]"
                cmd.extend(["-filter_complex", mic_chain])
                cmd.extend(["-map", "0:v", "-map", "1:a", "-map", "[mic_f]"])
            else:
                cmd.extend(["-map", "0:v", "-map", "1:a", "-map", "2:a"])
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
            # Label the tracks for editors/players
            cmd.extend([
                "-metadata:s:a:0", "title=System Audio",
                "-metadata:s:a:1", "title=Microphone",
            ])
        elif has_game:
            # System audio only — no filters needed
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        elif has_mic:
            # Mic only — apply filters directly
            if mic_af:
                cmd.extend(["-af", mic_af])
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        else:
            cmd.extend(["-an"])

        cmd.extend([str(temp_output)])

        log.info("Encoding clip: %d frames, %s, %s bitrate -> %s",
                 len(frames), resolution, bitrate_val, output_path)

        # Run FFmpeg — set cwd to model directory so arnndn can find the model
        # by filename alone (avoids Windows drive-letter colon in filter path).
        ffmpeg_cwd = os.path.dirname(rnnoise_model) if rnnoise_model else None

        # stdout is unused (output goes to file); stderr is drained in a
        # background thread to prevent pipe-buffer deadlock — writing raw
        # frames to stdin in a tight loop can fill the stderr pipe buffer
        # if FFmpeg's progress output backs up, causing both sides to block.
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            cwd=ffmpeg_cwd,
            **get_ffmpeg_flags(encode_priority),
        )

        stderr_chunks: list[bytes] = []

        def _drain_stderr():
            try:
                while True:
                    chunk = proc.stderr.read(4096)
                    if not chunk:
                        break
                    stderr_chunks.append(chunk)
            except Exception:
                pass

        import threading as _threading
        drain_thread = _threading.Thread(target=_drain_stderr, daemon=True)
        drain_thread.start()

        # Process frames in parallel — OpenCV decode/resize releases the GIL,
        # so a thread pool gives near-linear speedup.  A bounded queue keeps
        # memory usage in check (at most `ahead` processed frames buffered).
        from concurrent.futures import ThreadPoolExecutor

        def _process_frame(item):
            cv2.setNumThreads(1)
            ts, jpeg_bytes, webcam_jpeg = item
            frame_bgr = cv2.imdecode(
                np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR,
            )
            if frame_bgr is None:
                return None
            if compose_bg:
                frame_bgr = compose_on_background(
                    frame_bgr, background, frame_w, frame_h,
                    scaling=scaling,
                )
            if blur_regions:
                frame_bgr = apply_blur_regions(frame_bgr, blur_regions)
            if webcam_jpeg is not None:
                webcam_bgr = cv2.imdecode(
                    np.frombuffer(webcam_jpeg, dtype=np.uint8), cv2.IMREAD_COLOR,
                )
                if webcam_bgr is not None:
                    frame_bgr = composite_webcam(
                        frame_bgr, webcam_bgr, webcam_position_x, webcam_position_y,
                        crop=webcam_crop, chroma=webcam_chroma, scale=webcam_scale,
                        scaling=scaling,
                    )
            fh, fw = frame_bgr.shape[:2]
            if fw != frame_w or fh != frame_h:
                frame_bgr = cv2.resize(frame_bgr, (frame_w, frame_h), interpolation=get_interpolation(scaling))
            return frame_bgr

        workers = min(4, os.cpu_count() or 2)
        ahead = workers * 2  # max frames in flight to limit memory
        total_frames = len(frames)
        pipe_broken = False
        # Pre-allocate a black frame for decode failures so we maintain
        # the expected frame count and keep A/V sync intact.
        black_frame_bytes = b'\x00' * (frame_w * frame_h * 3)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            # Sliding window: keep at most `ahead` futures in flight so we
            # don't decode all frames into RAM at once (~6MB each at 1080p).
            from collections import deque
            pending: deque = deque()
            frame_iter = iter(enumerate(frames))
            written = 0

            def _submit_next():
                try:
                    idx, item = next(frame_iter)
                    pending.append((idx, pool.submit(_process_frame, item)))
                    return True
                except StopIteration:
                    return False

            # Fill initial window
            for _ in range(ahead):
                if not _submit_next():
                    break

            while pending:
                idx, future = pending.popleft()
                try:
                    frame_bgr = future.result(timeout=30)
                except Exception:
                    log.warning("Frame %d processing failed, inserting black frame", idx)
                    frame_bgr = None

                raw = frame_bgr.tobytes() if frame_bgr is not None else black_frame_bytes
                try:
                    proc.stdin.write(raw)
                    written += 1
                    if on_progress is not None:
                        try:
                            on_progress(written, total_frames)
                        except Exception:
                            pass
                except (BrokenPipeError, OSError, ValueError):
                    log.error("FFmpeg pipe broke after %d frames — process likely crashed", written)
                    pipe_broken = True
                    break
                # Refill window
                _submit_next()

            if pipe_broken:
                for _, f in pending:
                    f.cancel()

        try:
            proc.stdin.close()
        except Exception:
            pass
        drain_thread.join(timeout=120)
        try:
            proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            log.warning("FFmpeg did not exit in time — killing process")
            proc.kill()
            proc.wait(timeout=10)

        stderr_out = b"".join(stderr_chunks).decode("utf-8", errors="replace")
        if proc.returncode != 0:
            log.debug("FFmpeg stderr: %s", stderr_out[-1000:])
            raise RuntimeError(f"FFmpeg exited with code {proc.returncode}: {stderr_out[-500:]}")

        # Encoding succeeded — atomically reveal the final file.
        # replace() overwrites on Windows; rename() raises FileExistsError.
        temp_output.replace(output_path)
        clip_done = True

        # Save a thumbnail alongside the clip for instant gallery loading.
        # For global-triggered clips, use the frame closest to 1s after the
        # global was detected (the most interesting moment). For manual clips,
        # use the first frame.
        try:
            thumb_path = output_path.with_suffix(".thumb.jpg")
            thumb_idx = 0
            if thumb_time > 0:
                # Find the frame closest to thumb_time
                best_dist = abs(frames[0][0] - thumb_time)
                for i, (ts, _, _) in enumerate(frames):
                    dist = abs(ts - thumb_time)
                    if dist < best_dist:
                        best_dist = dist
                        thumb_idx = i
            thumb_raw = cv2.imdecode(
                np.frombuffer(frames[thumb_idx][1], dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if thumb_raw is not None:
                th, tw = thumb_raw.shape[:2]
                scale = min(320 / tw, 200 / th, 1.0)
                if scale < 1.0:
                    thumb_raw = cv2.resize(
                        thumb_raw,
                        (int(tw * scale), int(th * scale)),
                        interpolation=cv2.INTER_AREA,
                    )
                cv2.imwrite(str(thumb_path), thumb_raw,
                            [cv2.IMWRITE_JPEG_QUALITY, 80])
        except Exception as e:
            log.debug("Thumbnail generation failed: %s", e)

    finally:
        # Kill FFmpeg if it's still running (e.g. unhandled exception)
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
                proc.wait(timeout=10)
            except Exception:
                pass
        # Clean up temp audio files
        for tmp in (temp_game_wav, temp_mic_wav):
            if tmp:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass
        # Remove incomplete temp output on failure
        if not clip_done:
            try:
                if temp_output.exists():
                    temp_output.unlink()
            except OSError:
                pass
