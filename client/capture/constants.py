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

# ---------------------------------------------------------------------------
# Resolution presets
# ---------------------------------------------------------------------------
# Grouped by aspect ratio for UI display.  Each entry:
#   (config_key, label, width, height)
RESOLUTION_GROUPS = [
    ("16:9", [
        ("3840x2160", "4K",    3840, 2160),
        ("2560x1440", "1440p", 2560, 1440),
        ("1920x1080", "1080p", 1920, 1080),
        ("1600x900",  "900p",  1600, 900),
        ("1280x720",  "720p",  1280, 720),
        ("854x480",   "480p",  854,  480),
    ]),
    ("21:9", [
        ("5120x2160", "UW-4K",  5120, 2160),
        ("3440x1440", "UW-QHD", 3440, 1440),
        ("2560x1080", "UW-FHD", 2560, 1080),
    ]),
    ("16:10", [
        ("2560x1600", "WQXGA",  2560, 1600),
        ("1920x1200", "WUXGA",  1920, 1200),
        ("1680x1050", "WSXGA+", 1680, 1050),
        ("1440x900",  "WXGA+",  1440, 900),
        ("1280x800",  "WXGA",   1280, 800),
    ]),
    ("4:3", [
        ("1600x1200", "UXGA", 1600, 1200),
        ("1280x960",  "SXGA", 1280, 960),
        ("1024x768",  "XGA",  1024, 768),
        ("800x600",   "SVGA", 800,  600),
    ]),
]

# Fast lookup: config_key -> (width, height) or None for "source".
RESOLUTION_PRESETS: dict[str, tuple[int, int] | None] = {"source": None}
for _grp, _items in RESOLUTION_GROUPS:
    for _key, _lbl, _w, _h in _items:
        RESOLUTION_PRESETS[_key] = (_w, _h)
# Backward-compatible aliases for old config values
RESOLUTION_PRESETS["1080p"] = (1920, 1080)
RESOLUTION_PRESETS["720p"] = (1280, 720)
RESOLUTION_PRESETS["480p"] = (854, 480)

# ---------------------------------------------------------------------------
# Bitrate calculation
# ---------------------------------------------------------------------------
# Reference bitrates at 1080p (2 073 600 pixels).  Other resolutions are
# derived using a power-law scale (exponent 0.75) which tracks the
# diminishing-returns of spatial redundancy at higher resolutions.
_REF_PIXELS = 1920 * 1080
_QUALITY_BPS = {
    "low":    3_000_000,
    "medium": 6_000_000,
    "high":  12_000_000,
    "ultra": 20_000_000,
}


def get_bitrate(resolution_key: str, quality: str) -> str:
    """Return a bitrate string (e.g. ``'6M'``, ``'1500k'``) for *resolution_key* + *quality*.

    *resolution_key* is a RESOLUTION_PRESETS key (``"source"``, ``"1920x1080"``, etc.).
    *quality* is one of ``"low"`` / ``"medium"`` / ``"high"`` / ``"ultra"``.
    """
    ref_bps = _QUALITY_BPS.get(quality, _QUALITY_BPS["medium"])
    dims = RESOLUTION_PRESETS.get(resolution_key)
    if dims is None:
        # "source" or unknown — use 1080p reference as-is
        bps = ref_bps
    else:
        pixels = dims[0] * dims[1]
        bps = int(ref_bps * (pixels / _REF_PIXELS) ** 0.75)
    if bps >= 1_000_000:
        return f"{round(bps / 1_000_000)}M"
    return f"{round(bps / 1000)}k"


# Legacy lookup kept as a thin wrapper so old ``BITRATE_TABLE[(key, quality)]``
# call sites keep working until migrated.
class _BitrateLookup:
    """Dict-like object that delegates to :func:`get_bitrate`."""
    def get(self, key: tuple[str, str], default: str = "8M") -> str:
        try:
            return get_bitrate(key[0], key[1])
        except Exception:
            return default

BITRATE_TABLE = _BitrateLookup()

# ---------------------------------------------------------------------------
# Scaling / interpolation
# ---------------------------------------------------------------------------
# OpenCV interpolation algorithms for frame resizing.
# Key → (cv2 constant, user-facing label, tooltip).
try:
    import cv2 as _cv2
except ImportError:
    _cv2 = None

SCALING_ALGORITHMS = {
    "lanczos":  (_cv2.INTER_LANCZOS4 if _cv2 else 4,  "Lanczos",   "Lanczos 8×8 — sharpest, used by OBS"),
    "linear":   (_cv2.INTER_LINEAR   if _cv2 else 1,  "Bilinear",  "Bilinear — fast, slightly soft"),
    "cubic":    (_cv2.INTER_CUBIC    if _cv2 else 2,  "Bicubic",   "Bicubic 4×4 — balanced sharpness"),
    "area":     (_cv2.INTER_AREA     if _cv2 else 3,  "Area",      "Pixel-area averaging — best for downscaling"),
    "nearest":  (_cv2.INTER_NEAREST  if _cv2 else 0,  "Nearest",   "Nearest neighbor — pixelated, fastest"),
}
DEFAULT_SCALING_ALGORITHM = "cubic"


def get_interpolation(key: str) -> int:
    """Return the cv2 interpolation constant for *key*, defaulting to Lanczos."""
    entry = SCALING_ALGORITHMS.get(key)
    if entry is None:
        entry = SCALING_ALGORITHMS[DEFAULT_SCALING_ALGORITHM]
    return entry[0]


# Webcam overlay size relative to video frame
WEBCAM_OVERLAY_SCALE = 0.2  # 20% of frame width (default)
WEBCAM_MIN_SCALE = 0.05     # 5% minimum
WEBCAM_MAX_SCALE = 0.6      # 60% maximum
WEBCAM_OVERLAY_MARGIN = 10  # px from edge

# Webcam default position (normalized center coordinates, 0.0-1.0)
WEBCAM_DEFAULT_POS_X = 0.88
WEBCAM_DEFAULT_POS_Y = 0.85

# Snap threshold for webcam placement dialog (px in preview widget)
WEBCAM_SNAP_THRESHOLD = 15

# Minimum webcam crop region in pixels (prevents too-small-to-interact crops)
WEBCAM_MIN_CROP_PX = 20

# Audio filter defaults — Noise Suppression (arnndn / RNNoise)
DEFAULT_NS_MIX = 1.0  # 0.0 = bypass, 1.0 = fully denoised

# Audio filter defaults — Noise Gate (agate)
# threshold: linear amplitude (0-1) below which the gate reduces signal
# ratio: gain reduction steepness — higher = harder gate (2=gentle, 10+=hard)
DEFAULT_GATE_THRESHOLD = 0.01  # ~-40 dB, catches silence/quiet hiss
DEFAULT_GATE_RATIO = 10.0     # aggressive gating below threshold
DEFAULT_GATE_ATTACK = 5.0     # ms — fast open so words aren't clipped
DEFAULT_GATE_RELEASE = 200.0  # ms — smooth close, avoids choppy speech tails

# Audio filter defaults — Compressor (acompressor)
DEFAULT_COMP_THRESHOLD = -20.0  # dB
DEFAULT_COMP_RATIO = 4.0
DEFAULT_COMP_ATTACK = 5.0      # ms
DEFAULT_COMP_RELEASE = 100.0   # ms

# Gain
DEFAULT_GAIN = 1.0
MAX_GAIN = 3.0

# Timestamp format for filenames (sort-friendly)
FILENAME_TIMESTAMP_FMT = "%Y-%m-%d_%H-%M-%S"
