"""FFmpeg binary discovery, download, and path management."""

import os
import io
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

from ..core.logger import get_logger

log = get_logger("FFmpeg")

# Well-known locations to search (platform-specific)
_BUNDLED_DIR = Path(__file__).parent.parent / "bin"
_USER_BIN_DIR = Path("~/.entropia-nexus/bin").expanduser()

_FFMPEG_NAME = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"

# URL for auto-download (Windows essentials build from gyan.dev via GitHub)
_FFMPEG_DOWNLOAD_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/"
    "latest/ffmpeg-master-latest-win64-gpl.zip"
)

# RNNoise model for voice noise suppression (arnndn filter).
# "bd" = beguiling-drafter: trained on voice signal + recording noise.
_RNNOISE_MODEL_NAME = "bd.rnnn"
_RNNOISE_MODEL_URL = (
    "https://raw.githubusercontent.com/richardpl/arnndn-models/"
    "master/bd.rnnn"
)


def find_ffmpeg(config_path: str = "") -> str | None:
    """Find the FFmpeg binary.

    Search order:
    1. Explicit config path (if set)
    2. System PATH
    3. User bin directory (~/.entropia-nexus/bin/)
    4. Bundled location (client/bin/)

    Returns the path to the ffmpeg binary, or None if not found.
    """
    # 1. Config override
    if config_path:
        expanded = str(Path(config_path).expanduser())
        if os.path.isfile(expanded) and _is_executable(expanded):
            return expanded

    # 2. System PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # 3. User bin directory
    user_path = _USER_BIN_DIR / _FFMPEG_NAME
    if user_path.is_file() and _is_executable(str(user_path)):
        return str(user_path)

    # 4. Bundled
    bundled_path = _BUNDLED_DIR / _FFMPEG_NAME
    if bundled_path.is_file() and _is_executable(str(bundled_path)):
        return str(bundled_path)

    return None


def get_version(ffmpeg_path: str) -> str | None:
    """Return the FFmpeg version string, or None on failure."""
    try:
        from .constants import SUBPROCESS_FLAGS
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True, text=True, timeout=5,
            **SUBPROCESS_FLAGS,
        )
        if result.returncode == 0:
            first_line = result.stdout.split("\n")[0]
            return first_line.strip()
    except Exception as e:
        log.debug("Failed to get FFmpeg version: %s", e)
    return None


def download_ffmpeg(progress_callback=None) -> str | None:
    """Download FFmpeg to the user bin directory.

    Args:
        progress_callback: Optional callable(downloaded_bytes, total_bytes).

    Returns the path to the downloaded ffmpeg binary, or None on failure.
    """
    if sys.platform != "win32":
        log.warning("Auto-download is only supported on Windows")
        return None

    import requests

    target_dir = _USER_BIN_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    log.info("Downloading FFmpeg from %s", _FFMPEG_DOWNLOAD_URL)

    try:
        resp = requests.get(_FFMPEG_DOWNLOAD_URL, stream=True, timeout=30)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        chunks = []

        for chunk in resp.iter_content(chunk_size=1024 * 256):
            chunks.append(chunk)
            downloaded += len(chunk)
            if progress_callback and total:
                progress_callback(downloaded, total)

        data = b"".join(chunks)

        # Extract ffmpeg.exe from the zip
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            ffmpeg_entry = None
            for name in zf.namelist():
                if name.endswith("bin/ffmpeg.exe"):
                    ffmpeg_entry = name
                    break

            if not ffmpeg_entry:
                log.error("ffmpeg.exe not found in downloaded archive")
                return None

            # Extract just ffmpeg.exe
            target_path = target_dir / _FFMPEG_NAME
            with zf.open(ffmpeg_entry) as src, open(target_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

        log.info("FFmpeg downloaded to %s", target_path)
        return str(target_path)

    except Exception as e:
        log.error("Failed to download FFmpeg: %s", e)
        return None


def ensure_ffmpeg(config_path: str = "", progress_callback=None) -> str | None:
    """Find or download FFmpeg.

    Returns the path to the ffmpeg binary, or None if unavailable.
    """
    path = find_ffmpeg(config_path)
    if path:
        return path

    # Attempt auto-download
    return download_ffmpeg(progress_callback)


def find_rnnoise_model() -> str | None:
    """Find the RNNoise model file.

    Search order:
    1. User bin directory (~/.entropia-nexus/bin/)
    2. Bundled location (client/bin/)

    Returns the path to the model file, or None if not found.
    """
    for directory in (_USER_BIN_DIR, _BUNDLED_DIR):
        path = directory / _RNNOISE_MODEL_NAME
        if path.is_file():
            return str(path)
    return None


def download_rnnoise_model() -> str | None:
    """Download the RNNoise model to the user bin directory.

    Returns the path to the downloaded model, or None on failure.
    """
    import requests

    target_dir = _USER_BIN_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / _RNNOISE_MODEL_NAME

    log.info("Downloading RNNoise model from %s", _RNNOISE_MODEL_URL)

    try:
        resp = requests.get(_RNNOISE_MODEL_URL, timeout=30)
        resp.raise_for_status()
        target_path.write_bytes(resp.content)
        log.info("RNNoise model downloaded to %s", target_path)
        return str(target_path)
    except Exception as e:
        log.error("Failed to download RNNoise model: %s", e)
        return None


def ensure_rnnoise_model() -> str | None:
    """Find or download the RNNoise model.

    Returns the path to the model file, or None if unavailable.
    """
    path = find_rnnoise_model()
    if path:
        return path
    return download_rnnoise_model()


# ---------------------------------------------------------------------------
# Hardware encoder detection and codec argument building
# ---------------------------------------------------------------------------

# Supported encoders in preference order.  Each entry:
#   (config_key, ffmpeg_codec, display_name, type)
# Grouped: GPU H.264 → GPU H.265 → CPU
ENCODERS = [
    # GPU — H.264
    ("h264_nvenc",  "h264_nvenc",  "NVIDIA NVENC H.264",     "gpu"),
    ("h264_amf",    "h264_amf",    "AMD AMF H.264",          "gpu"),
    ("h264_qsv",    "h264_qsv",    "Intel QuickSync H.264",  "gpu"),
    # GPU — H.265 (better compression, same hardware cost)
    ("hevc_nvenc",  "hevc_nvenc",  "NVIDIA NVENC H.265",     "gpu"),
    ("hevc_amf",    "hevc_amf",    "AMD AMF H.265",          "gpu"),
    ("hevc_qsv",    "hevc_qsv",    "Intel QuickSync H.265",  "gpu"),
    # CPU
    ("libx264",     "libx264",     "x264 H.264 (CPU)",       "cpu"),
    ("libx265",     "libx265",     "x265 H.265 (CPU, slow)", "cpu"),
]

# Cache: maps ffmpeg_path -> set of encoder names that actually work
_encoder_cache: dict[str, set[str]] = {}


def _probe_encoder(ffmpeg_path: str, codec: str) -> bool:
    """Test whether an encoder actually works by encoding one black frame.

    FFmpeg may list hardware encoders (e.g. h264_nvenc) that fail at
    runtime due to driver version mismatches or missing hardware.
    """
    from .constants import SUBPROCESS_FLAGS
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=black:s=256x256:d=0.04:r=25",
             "-frames:v", "1", "-c:v", codec,
             "-f", "null", os.devnull],
            capture_output=True, timeout=10,
            **SUBPROCESS_FLAGS,
        )
        if result.returncode != 0:
            log.debug("Probe %s failed (rc=%s): %s",
                      codec, result.returncode,
                      (result.stderr or b"").decode(errors="replace").strip())
        return result.returncode == 0
    except Exception:
        return False


def detect_encoders(ffmpeg_path: str) -> list[tuple[str, str, str]]:
    """Probe FFmpeg for available and *working* encoders.

    Hardware encoders are tested with a 1-frame trial encode to verify
    driver compatibility.  CPU encoders are trusted if FFmpeg lists them.
    Results are cached.
    """
    cached = _encoder_cache.get(ffmpeg_path)
    if cached is None:
        # First pass: collect all encoders FFmpeg claims to have
        listed: set[str] = set()
        try:
            from .constants import SUBPROCESS_FLAGS
            result = subprocess.run(
                [ffmpeg_path, "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=10,
                **SUBPROCESS_FLAGS,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        listed.add(parts[1])
        except Exception as e:
            log.debug("Encoder listing failed: %s", e)

        # Second pass: verify GPU encoders with a trial encode
        cached = set()
        for key, codec, name, enc_type in ENCODERS:
            if codec not in listed:
                continue
            if enc_type == "gpu":
                if _probe_encoder(ffmpeg_path, codec):
                    cached.add(codec)
                    log.info("Encoder %s: available", codec)
                else:
                    log.info("Encoder %s: listed but failed probe (driver too old?)", codec)
            else:
                cached.add(codec)

        _encoder_cache[ffmpeg_path] = cached

    available = []
    for key, codec, name, _ in ENCODERS:
        if codec in cached:
            available.append((key, codec, name))
    return available


def get_encoder_args(
    encoder: str,
    cqp: int,
    threads: int = 0,
    realtime: bool = False,
) -> list[str]:
    """Build FFmpeg codec arguments for the given encoder.

    Uses constant-quality (CQP/CRF) rate control so every frame gets the
    bits it needs — high-motion scenes automatically receive more bitrate.
    This matches the approach used by OBS Studio for recording.

    Args:
        encoder: Config key (e.g. ``"libx264"``, ``"h264_nvenc"``).
        cqp: Quality value (CQP for HW encoders, CRF for libx264/libx265).
             Lower = better quality + larger files.  Typical: 16–28.
        threads: Thread count for CPU encoders (0 = auto).
        realtime: True for recording/segments (faster preset), False for
                  clip encoding (better quality preset).

    Returns a list of FFmpeg arguments (``["-c:v", ..., "-pix_fmt", ...]``).
    """
    from .constants import get_encode_thread_count

    args = []
    q = str(cqp)

    if encoder == "h264_nvenc" or encoder == "hevc_nvenc":
        args.extend(["-c:v", encoder])
        args.extend(["-preset", "p5" if realtime else "p5"])
        args.extend(["-tune", "ll" if realtime else "hq"])
        args.extend(["-rc", "constqp", "-qp", q])
        args.extend(["-pix_fmt", "yuv420p"])

    elif encoder == "h264_amf" or encoder == "hevc_amf":
        args.extend(["-c:v", encoder])
        args.extend(["-quality", "speed" if realtime else "quality"])
        args.extend(["-rc", "cqp", "-qp_i", q, "-qp_p", q, "-qp_b", q])
        args.extend(["-pix_fmt", "yuv420p"])

    elif encoder == "h264_qsv" or encoder == "hevc_qsv":
        args.extend(["-c:v", encoder])
        args.extend(["-preset", "faster" if realtime else "faster"])
        args.extend(["-global_quality", q])
        args.extend(["-pix_fmt", "yuv420p"])

    elif encoder == "libx265":
        args.extend(["-c:v", "libx265"])
        args.extend(["-preset", "superfast" if realtime else "fast"])
        args.extend(["-crf", q])
        args.extend(["-pix_fmt", "yuv420p"])
        args.extend(["-threads", str(get_encode_thread_count(threads))])
        if realtime:
            args.extend(["-tune", "zerolatency"])

    else:
        # Default: libx264
        args.extend(["-c:v", "libx264"])
        args.extend(["-preset", "superfast" if realtime else "fast"])
        args.extend(["-crf", q])
        args.extend(["-pix_fmt", "yuv420p"])
        args.extend(["-threads", str(get_encode_thread_count(threads))])
        if realtime:
            args.extend(["-tune", "zerolatency"])

    return args


def _is_executable(path: str) -> bool:
    """Check if a file exists and is likely executable."""
    if not os.path.isfile(path):
        return False
    if sys.platform == "win32":
        return path.lower().endswith(".exe")
    return os.access(path, os.X_OK)
