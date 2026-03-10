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


def _is_executable(path: str) -> bool:
    """Check if a file exists and is likely executable."""
    if not os.path.isfile(path):
        return False
    if sys.platform == "win32":
        return path.lower().endswith(".exe")
    return os.access(path, os.X_OK)
