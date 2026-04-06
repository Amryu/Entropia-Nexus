"""Persistent FFmpeg process that encodes raw BGR frames into H.264 segments.

The encoder writes 2-second MPEG-TS segments to a temporary directory.
A reader thread monitors FFmpeg's segment list output (stdout) and
notifies a callback when each segment completes.

Frames are written as they arrive from capture via a writer thread that
decouples pipe I/O from the capture callback.  FFmpeg uses wallclock
timestamps (``-use_wallclock_as_timestamps 1``) with VFR passthrough
(``-fps_mode vfr``) so segment duration matches real time without
frame duplication — only unique frames are piped.
"""

import ctypes
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

from ..core.logger import get_logger
from .constants import (
    SEGMENT_DURATION_S,
    SEGMENT_FORMAT,
    SEGMENT_TEMP_PREFIX,
    get_ffmpeg_flags,
)
from .ffmpeg import get_encoder_args

log = get_logger("SegmentEncoder")

# Maximum consecutive restart attempts before giving up
_MAX_RESTARTS = 3

# Sentinel object to signal writer thread to exit
_WRITE_SENTINEL = object()


class SegmentEncoder:
    """Manages a persistent FFmpeg subprocess for realtime H.264 segment encoding.

    Frames arrive via :meth:`write_frame` (called from capture or the
    effects processor).  A writer thread handles the blocking pipe I/O
    so the caller never stalls.

    Args:
        ffmpeg_path: Path to the FFmpeg binary.
        width: Frame width in pixels.
        height: Frame height in pixels.
        fps: Target frame rate (used for keyframe interval and ``-r``).
        cqp: Quality value (CQP/CRF).  Lower = better quality.
        on_segment: Callback ``(path: Path, start_time: float, end_time: float)``
                    invoked when a segment file is complete.
        encode_priority: Process priority.
        encode_threads: Thread count for CPU encoders (0 = auto).
        segment_duration: Segment length in seconds.
        blur_regions: List of ``{x, y, w, h}`` dicts (normalized 0–1).
    """

    def __init__(
        self,
        ffmpeg_path: str,
        width: int,
        height: int,
        fps: int,
        cqp: int,
        on_segment,
        encode_priority: str = "below_normal",
        encode_threads: int = 0,
        segment_duration: int = SEGMENT_DURATION_S,
        video_encoder: str = "libx264",
        on_error=None,
        blur_regions: list[dict] | None = None,
    ):
        self._ffmpeg = ffmpeg_path
        self._width = width
        self._height = height
        self._fps = max(1, fps)
        self._cqp = cqp
        self._on_segment = on_segment
        self._on_error = on_error
        self._priority = encode_priority
        self._threads = encode_threads
        self._seg_duration = segment_duration
        self._video_encoder = video_encoder
        self._blur_regions = blur_regions or []

        self._proc: subprocess.Popen | None = None
        self._seg_dir: Path | None = None
        self._start_mono: float = 0.0
        self._frames_written = 0
        self._lock = threading.Lock()
        self._running = False
        self._reader_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._writer_thread: threading.Thread | None = None
        self._write_queue: queue.Queue | None = None
        self._restart_count = 0

        # Debug stats
        self._dbg_file = None
        self._dbg_capture_count = 0
        self._dbg_written_count = 0
        self._dbg_queue_drops = 0
        self._dbg_tobytes_ms = 0.0     # total ms in tobytes() this interval
        self._dbg_write_ms = 0.0       # total ms in pipe write this interval
        self._dbg_last_log = 0.0
        self._dbg_ffmpeg_cpu = 0.0     # FFmpeg process CPU %
        self._dbg_psutil_proc = None

    # -- public API --

    @property
    def segment_dir(self) -> Path | None:
        return self._seg_dir

    @property
    def running(self) -> bool:
        return self._running and self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        """Create the temp directory and launch FFmpeg."""
        self._seg_dir = Path(tempfile.mkdtemp(prefix=SEGMENT_TEMP_PREFIX))
        self._running = True
        self._restart_count = 0
        self._frames_written = 0
        # Debug log
        try:
            dbg_path = Path(tempfile.gettempdir()) / "nexus_segment_debug.log"
            self._dbg_file = open(dbg_path, "w")
            self._dbg_file.write(
                "time,capture_fps,written_fps,queue_drops,queue_depth,"
                "tobytes_ms,write_ms,ffmpeg_cpu,frame_size\n"
            )
            self._dbg_file.flush()
            log.info("Segment debug log: %s", dbg_path)
        except Exception:
            self._dbg_file = None
        self._launch()

    def stop(self) -> None:
        """Gracefully stop the encoder."""
        self._running = False
        if self._dbg_file:
            try:
                self._dbg_file.close()
            except Exception:
                pass
            self._dbg_file = None
        # Signal writer thread to drain and exit
        if self._write_queue is not None:
            self._write_queue.put(_WRITE_SENTINEL)
        if self._writer_thread and self._writer_thread.is_alive():
            self._writer_thread.join(timeout=10)
        self._write_queue = None
        # Close FFmpeg
        self._close_proc()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=5)
        if self._stderr_thread and self._stderr_thread.is_alive():
            self._stderr_thread.join(timeout=5)

    def write_frame(self, frame_bgr, timestamp: float) -> bool:
        """Queue a frame for encoding.

        Near-zero cost on the caller's thread — just stores a numpy
        array reference.  The writer thread handles BGR→YUV conversion
        and pipe I/O so the capture loop stays fast.

        *frame_bgr* must be an ``np.ndarray`` (BGR24).
        """
        if not self._running or self._write_queue is None:
            return False

        self._dbg_capture_count += 1

        try:
            self._write_queue.put_nowait(frame_bgr)
        except queue.Full:
            self._dbg_queue_drops += 1

        return True

    def cleanup(self) -> None:
        """Remove the temporary segment directory and all files."""
        self.stop()
        if self._seg_dir and self._seg_dir.exists():
            import shutil
            try:
                shutil.rmtree(self._seg_dir, ignore_errors=True)
            except Exception:
                log.debug("Failed to clean up segment dir: %s", self._seg_dir)

    # -- internal --

    def _build_blur_filter(self) -> str:
        """Build an FFmpeg ``-vf`` filter string for blur regions.

        Each normalized region ``{x, y, w, h}`` becomes a
        crop → boxblur → overlay sub-graph.  FFmpeg applies blur during
        encoding with near-zero extra CPU cost.
        """
        if not self._blur_regions:
            return ""

        w, h = self._width, self._height
        parts = []
        prev = "[0:v]"
        valid = 0

        for i, region in enumerate(self._blur_regions):
            rx = max(0, int(region.get("x", 0) * w))
            ry = max(0, int(region.get("y", 0) * h))
            rw = max(2, int(region.get("w", 0) * w))
            rh = max(2, int(region.get("h", 0) * h))
            rw = min(rw, w - rx)
            rh = min(rh, h - ry)
            if rw < 2 or rh < 2:
                continue

            tag_blur = f"[bb{i}]"
            tag_out = f"[bo{i}]"

            parts.append(f"{prev}split[base{i}][src{i}]")
            parts.append(
                f"[src{i}]crop={rw}:{rh}:{rx}:{ry},"
                f"boxblur=luma_radius=20:luma_power=3{tag_blur}"
            )
            parts.append(f"[base{i}]{tag_blur}overlay={rx}:{ry}{tag_out}")
            prev = tag_out
            valid += 1

        if not parts:
            return ""

        filter_str = ";".join(parts)
        # Remove trailing output label from last overlay (becomes the output)
        last_tag = f"[bo{valid - 1}]"
        if filter_str.endswith(last_tag):
            filter_str = filter_str[: -len(last_tag)]

        return filter_str

    def _launch(self) -> None:
        """Start or restart the FFmpeg subprocess."""
        seg_pattern = str(self._seg_dir / f"seg_%05d.ts")

        cmd = [
            self._ffmpeg, "-y",
            # Wallclock timestamps: segment duration matches real time
            # without frame duplication.  Only unique frames are piped.
            "-use_wallclock_as_timestamps", "1",
            "-f", "rawvideo",
            "-pix_fmt", "yuv420p",
            "-s", f"{self._width}x{self._height}",
            "-r", str(self._fps),
            "-i", "pipe:0",
        ]

        # Blur regions as FFmpeg filter (near-zero CPU vs per-frame OpenCV)
        blur_vf = self._build_blur_filter()
        if blur_vf:
            cmd.extend(["-filter_complex", blur_vf])

        cmd.extend(get_encoder_args(
            self._video_encoder, self._cqp,
            threads=self._threads, realtime=True,
        ))
        cmd.extend([
            # VFR passthrough: preserve wallclock PTS as-is.  Without this,
            # FFmpeg's default cfr mode retimestamps frames to fixed 1/fps
            # intervals, which conflicts with wallclock timestamps.
            "-fps_mode", "vfr",
            "-g", str(self._fps * self._seg_duration),
            "-force_key_frames", f"expr:gte(t,n_forced*{self._seg_duration})",
            "-f", "segment",
            "-segment_time", str(self._seg_duration),
            "-segment_format", SEGMENT_FORMAT,
            "-segment_list", "pipe:1",
            "-segment_list_type", "csv",
            "-reset_timestamps", "1",
            seg_pattern,
        ])

        log.info(
            "Starting segment encoder: %dx%d @%dfps, CQP %d, %d threads, "
            "%ds segments, %d blur regions -> %s",
            self._width, self._height, self._fps, self._cqp,
            self._threads, self._seg_duration, len(self._blur_regions),
            self._seg_dir,
        )

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **get_ffmpeg_flags(self._priority),
            )
        except Exception as e:
            log.error("Failed to start segment encoder: %s", e)
            self._running = False
            return

        # Write queue: bounded at 1 second of frames.  If the encoder
        # can't keep up, oldest frames are dropped (capture rate > encode rate).
        self._write_queue = queue.Queue(maxsize=self._fps)

        self._reader_thread = threading.Thread(
            target=self._read_segment_list, daemon=True, name="seg-list-reader",
        )
        self._reader_thread.start()

        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, daemon=True, name="seg-stderr",
        )
        self._stderr_thread.start()

        self._writer_thread = threading.Thread(
            target=self._writer_loop, daemon=True, name="seg-writer",
        )
        self._writer_thread.start()

    # ------------------------------------------------------------------
    # Writer thread — drains queue into FFmpeg stdin
    # ------------------------------------------------------------------

    def _writer_loop(self) -> None:
        """Convert BGR→YUV and write to FFmpeg's stdin pipe.

        Uses numpy's buffer protocol to write directly to the pipe —
        no ``tobytes()`` copy needed.  This avoids a 3MB memcpy per
        frame that would hold the GIL and block the capture thread.
        """
        try:
            import cv2
            _cv2 = cv2
        except ImportError:
            _cv2 = None

        q = self._write_queue
        while True:
            item = q.get()
            if item is _WRITE_SENTINEL:
                break

            proc = self._proc
            if proc is None or proc.stdin is None:
                continue

            if self._frames_written == 0:
                self._start_mono = time.monotonic()
                self._dbg_last_log = self._start_mono
                try:
                    import psutil
                    self._dbg_psutil_proc = psutil.Process(proc.pid)
                    self._dbg_psutil_proc.cpu_percent()
                except Exception:
                    pass

            t0 = time.perf_counter()

            # BGR→YUV conversion (releases GIL during computation)
            if isinstance(item, bytes):
                raw = item
            elif _cv2 is not None:
                yuv = _cv2.cvtColor(item, _cv2.COLOR_BGR2YUV_I420)
                # Write contiguous numpy array directly via buffer protocol
                # — avoids tobytes() memcpy which holds the GIL for ~1ms.
                raw = np.ascontiguousarray(yuv) if not yuv.flags["C_CONTIGUOUS"] else yuv
            else:
                raw = item

            t1 = time.perf_counter()
            self._dbg_tobytes_ms += (t1 - t0) * 1000

            try:
                proc.stdin.write(raw)
                t2 = time.perf_counter()
                self._dbg_write_ms += (t2 - t1) * 1000
                with self._lock:
                    self._frames_written += 1
                self._dbg_written_count += 1
            except (BrokenPipeError, OSError, ValueError):
                log.warning("Encoder pipe broken after %d frames",
                            self._frames_written)
                self._try_restart()
                return

            # Debug stats every second
            now = time.monotonic()
            if now - self._dbg_last_log >= 1.0:
                self._flush_debug_stats(now, q)

    def _flush_debug_stats(self, now: float, q) -> None:
        dt = now - self._dbg_last_log
        if dt <= 0:
            return
        cap = self._dbg_capture_count / dt
        written = self._dbg_written_count / dt
        drops = self._dbg_queue_drops
        depth = q.qsize() if q else 0
        frame_sz = self._width * self._height * 3 // 2  # YUV420p
        # Average ms per operation
        tobytes_avg = (self._dbg_tobytes_ms / self._dbg_capture_count
                       if self._dbg_capture_count else 0)
        write_avg = (self._dbg_write_ms / self._dbg_written_count
                     if self._dbg_written_count else 0)
        # FFmpeg CPU %
        ffmpeg_cpu = 0.0
        if self._dbg_psutil_proc:
            try:
                ffmpeg_cpu = self._dbg_psutil_proc.cpu_percent()
            except Exception:
                pass

        self._dbg_capture_count = 0
        self._dbg_written_count = 0
        self._dbg_queue_drops = 0
        self._dbg_tobytes_ms = 0.0
        self._dbg_write_ms = 0.0
        self._dbg_last_log = now

        line = (
            f"{now - self._start_mono:.1f},"
            f"{cap:.1f},{written:.1f},{drops},{depth},"
            f"{tobytes_avg:.1f},{write_avg:.1f},{ffmpeg_cpu:.1f},{frame_sz}\n"
        )
        if self._dbg_file:
            try:
                self._dbg_file.write(line)
                self._dbg_file.flush()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # FFmpeg process management
    # ------------------------------------------------------------------

    def _close_proc(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
        except Exception:
            pass
        try:
            self._proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            log.warning("Segment encoder did not exit — killing")
            self._proc.kill()
            try:
                self._proc.wait(timeout=5)
            except Exception:
                pass
        self._proc = None

    def _try_restart(self) -> None:
        self._close_proc()
        self._restart_count += 1
        if self._restart_count > _MAX_RESTARTS:
            if self._video_encoder != "libx264":
                msg = (
                    f"Encoder {self._video_encoder} failed — falling back to x264 (CPU). "
                    f"Your GPU driver may need updating."
                )
                log.warning(msg)
                if self._on_error:
                    self._on_error(msg)
                self._video_encoder = "libx264"
                self._restart_count = 0
            else:
                log.error("Segment encoder (libx264) failed %d times — giving up",
                          _MAX_RESTARTS)
                self._running = False
                return
        log.warning("Restarting segment encoder (attempt %d/%d, encoder=%s)",
                     self._restart_count, _MAX_RESTARTS, self._video_encoder)
        time.sleep(0.2)
        self._launch()

    # ------------------------------------------------------------------
    # Segment list reader
    # ------------------------------------------------------------------

    def _read_segment_list(self) -> None:
        """Read segment completion lines from FFmpeg stdout.

        With wallclock timestamps, ``start_mono + seg_start`` gives
        accurate monotonic timestamps for segment boundaries.
        """
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            for raw_line in proc.stdout:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) < 3:
                    continue
                filename = parts[0].strip()
                try:
                    seg_start = float(parts[1])
                    seg_end = float(parts[2])
                except (ValueError, IndexError):
                    continue

                seg_path = self._seg_dir / filename
                if not seg_path.exists():
                    time.sleep(0.05)

                if seg_path.exists():
                    mono_start = self._start_mono + seg_start
                    mono_end = self._start_mono + seg_end
                    try:
                        self._on_segment(seg_path, mono_start, mono_end)
                    except Exception:
                        log.exception("on_segment callback failed for %s", filename)
                else:
                    log.debug("Segment file not found: %s", seg_path)
        except Exception:
            if self._running:
                log.debug("Segment list reader stopped")

    def _drain_stderr(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        chunks: list[bytes] = []
        try:
            while True:
                chunk = proc.stderr.read(4096)
                if not chunk:
                    break
                chunks.append(chunk)
        except Exception:
            pass
        if chunks:
            text = b"".join(chunks).decode("utf-8", errors="replace").strip()
            if proc.poll() and proc.returncode != 0:
                log.error("FFmpeg stderr (exit %d):\n%s", proc.returncode, text[-2000:])
            else:
                log.debug("FFmpeg stderr:\n%s", text[-500:])
