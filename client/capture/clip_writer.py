"""FFmpeg-based video clip writer — muxes frames + audio + webcam into MP4."""

import os
import subprocess
import tempfile
import wave

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
    WEBCAM_OVERLAY_SCALE,
    get_ffmpeg_flags,
    get_ffmpeg_scale_flag,
    get_interpolation,
)
from .ffmpeg import ensure_ffmpeg, find_rnnoise_model
from .screenshot import apply_blur_regions, compose_on_background

log = get_logger("ClipWriter")


def _write_wav(pcm: np.ndarray, path: str, sample_rate: int = AUDIO_SAMPLE_RATE,
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


def _apply_gain(pcm: np.ndarray, gain: float) -> np.ndarray:
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


def _build_mic_filter(filters: dict, rnnoise_model: str | None = None) -> str:
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
        audio_pcm = _apply_gain(audio_pcm, game_gain)
    if has_mic:
        mic_pcm = _apply_gain(mic_pcm, mic_gain)

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
            _write_wav(audio_pcm, temp_game_wav.name)
            temp_game_wav.close()
            cmd.extend(["-i", temp_game_wav.name])  # input 1

        if has_mic:
            temp_mic_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            _write_wav(mic_pcm, temp_mic_wav.name)
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

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-b:v", bitrate_val,
            "-pix_fmt", "yuv420p",
        ])

        # Audio encoding — filters apply to mic only
        rnnoise_model = find_rnnoise_model() if (mic_filters or {}).get("noise_suppression") else None
        if (mic_filters or {}).get("noise_suppression") and not rnnoise_model:
            log.warning("Noise suppression requested but RNNoise model not found — skipping")
        mic_af = _build_mic_filter(mic_filters or {}, rnnoise_model=rnnoise_model)

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
                    frame_bgr = _composite_webcam(
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


def _apply_chroma_key(
    webcam: np.ndarray,
    chroma: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply chroma key to a webcam BGR frame.

    Returns (bgr_frame, alpha_mask) where alpha_mask is 0-255.
    """
    color_hex = chroma.get("color", "#00ff00").lstrip("#")
    r = int(color_hex[0:2], 16)
    g = int(color_hex[2:4], 16)
    b = int(color_hex[4:6], 16)
    threshold = chroma.get("threshold", 40)
    smoothing = chroma.get("smoothing", 5)

    # Convert key color to float array (BGR order)
    key_bgr = np.array([b, g, r], dtype=np.float32)

    # Compute per-pixel color distance
    diff = np.linalg.norm(
        webcam.astype(np.float32) - key_bgr, axis=2,
    )

    # Create mask: 255 = keep, 0 = transparent
    alpha = np.where(diff > threshold, 255, 0).astype(np.uint8)

    # Smooth edges
    if smoothing > 1:
        ksize = smoothing | 1  # ensure odd
        alpha = cv2.GaussianBlur(alpha, (ksize, ksize), 0)

    return webcam, alpha


def _composite_webcam(
    frame: np.ndarray,
    webcam: np.ndarray,
    position_x: float,
    position_y: float,
    crop: dict | None = None,
    chroma: dict | None = None,
    scale: float = WEBCAM_OVERLAY_SCALE,
    scaling: str = "lanczos",
) -> np.ndarray:
    """Overlay a webcam frame at a normalized (center) position on the main frame.

    Args:
        crop: Optional {x, y, w, h} normalized crop region within the webcam.
        chroma: Optional {enabled, color, threshold, smoothing} for chroma key.
        scale: Webcam width as fraction of frame width (after crop).
    """
    # Apply crop if configured
    if crop:
        wh, ww = webcam.shape[:2]
        cx = int(crop.get("x", 0.0) * ww)
        cy = int(crop.get("y", 0.0) * wh)
        cw = int(crop.get("w", 1.0) * ww)
        ch = int(crop.get("h", 1.0) * wh)
        # Clamp
        cx = max(0, min(cx, ww - 1))
        cy = max(0, min(cy, wh - 1))
        cw = max(1, min(cw, ww - cx))
        ch = max(1, min(ch, wh - cy))
        webcam = webcam[cy:cy + ch, cx:cx + cw]

    fh, fw = frame.shape[:2]
    target_w = int(fw * scale)
    wh, ww = webcam.shape[:2]
    target_h = int(target_w * wh / ww)

    resized = cv2.resize(webcam, (target_w, target_h), interpolation=get_interpolation(scaling))

    # Convert normalized center position to top-left pixel position
    px = int(position_x * fw)
    py = int(position_y * fh)
    x = px - target_w // 2
    y = py - target_h // 2

    # Clamp to frame bounds
    x = max(0, min(x, fw - target_w))
    y = max(0, min(y, fh - target_h))

    # Chroma key compositing
    if chroma and chroma.get("enabled"):
        resized, alpha = _apply_chroma_key(resized, chroma)
        alpha_f = alpha.astype(np.float32) / 255.0
        alpha_3 = alpha_f[:, :, np.newaxis]
        roi = frame[y:y + target_h, x:x + target_w].astype(np.float32)
        blended = roi * (1.0 - alpha_3) + resized.astype(np.float32) * alpha_3
        frame[y:y + target_h, x:x + target_w] = np.clip(blended, 0, 255).astype(np.uint8)
    else:
        frame[y:y + target_h, x:x + target_w] = resized

    return frame
