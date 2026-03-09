"""Capture system constants — presets, defaults, bitrate tables."""

import sys
from pathlib import Path

# Default output directories
if sys.platform == "win32":
    _PICTURES = Path("~/Pictures").expanduser()
    _VIDEOS = Path("~/Videos").expanduser()
else:
    _PICTURES = Path("~/Pictures").expanduser()
    _VIDEOS = Path("~/Videos").expanduser()

DEFAULT_SCREENSHOT_DIR = str(_PICTURES / "Entropia Nexus Screenshots")
DEFAULT_CLIP_DIR = str(_VIDEOS / "Entropia Nexus Clips")

# Capture defaults
DEFAULT_BUFFER_SECONDS = 15
DEFAULT_POST_GLOBAL_SECONDS = 5
DEFAULT_SCREENSHOT_DELAY_S = 1.0
DEFAULT_CAPTURE_FPS = 30

# JPEG quality for frame buffer (0-100, higher = bigger + better)
JPEG_QUALITY = 80

# Audio
AUDIO_SAMPLE_RATE = 48000
AUDIO_CHANNELS = 2
AUDIO_DTYPE = "float32"

# Resolution presets: name -> (width, height) or None for source
RESOLUTION_PRESETS = {
    "source": None,
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "480p": (854, 480),
}

# Bitrate presets: (resolution, quality) -> bitrate string
# Resolution keys: "source", "1080p", "720p", "480p"
# Quality keys: "low", "medium", "high", "ultra"
BITRATE_TABLE = {
    ("source", "low"): "4M",
    ("source", "medium"): "8M",
    ("source", "high"): "16M",
    ("source", "ultra"): "30M",
    ("1080p", "low"): "3M",
    ("1080p", "medium"): "6M",
    ("1080p", "high"): "12M",
    ("1080p", "ultra"): "20M",
    ("720p", "low"): "1500k",
    ("720p", "medium"): "3M",
    ("720p", "high"): "6M",
    ("720p", "ultra"): "10M",
    ("480p", "low"): "800k",
    ("480p", "medium"): "1500k",
    ("480p", "high"): "3M",
    ("480p", "ultra"): "5M",
}

# Webcam overlay size relative to video frame
WEBCAM_OVERLAY_SCALE = 0.2  # 20% of frame width
WEBCAM_OVERLAY_MARGIN = 10  # px from edge

# Webcam corner positions
WEBCAM_POSITIONS = ("top_left", "top_right", "bottom_left", "bottom_right")

# Timestamp format for filenames (sort-friendly)
FILENAME_TIMESTAMP_FMT = "%Y-%m-%d_%H-%M-%S"
