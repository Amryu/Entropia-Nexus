"""Screenshot capture — frame grab, blur, and save to PNG."""

import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.logger import get_logger
from .constants import DEFAULT_SCREENSHOT_DIR, FILENAME_TIMESTAMP_FMT

log = get_logger("Screenshot")

# Characters not allowed in filenames
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize_filename(name: str) -> str:
    """Replace unsafe filename characters with dashes."""
    return _UNSAFE_CHARS.sub("-", name).strip(" .-")


def apply_blur_regions(
    frame: np.ndarray,
    blur_regions: list[dict],
) -> np.ndarray:
    """Apply gaussian blur to specified regions of a frame.

    Args:
        frame: BGR image (numpy array).
        blur_regions: List of dicts with normalized coords {x, y, w, h} (0.0-1.0).

    Returns:
        A copy of the frame with blur applied.
    """
    if not blur_regions or cv2 is None:
        return frame
    result = frame.copy()
    h, w = result.shape[:2]
    for region in blur_regions:
        rx = max(0, int(region.get("x", 0) * w))
        ry = max(0, int(region.get("y", 0) * h))
        rw = min(w - rx, int(region.get("w", 0) * w))
        rh = min(h - ry, int(region.get("h", 0) * h))
        if rw <= 0 or rh <= 0:
            continue
        roi = result[ry:ry + rh, rx:rx + rw]
        # Heavy blur kernel — must be odd
        ksize = max(31, (min(rw, rh) // 3) | 1)
        blurred = cv2.GaussianBlur(roi, (ksize, ksize), 0)
        result[ry:ry + rh, rx:rx + rw] = blurred
    return result


def build_screenshot_path(
    base_dir: str,
    daily_subfolder: bool,
    target_name: str = "",
    amount: float = 0.0,
    timestamp: datetime | None = None,
) -> Path:
    """Build the output path for a screenshot.

    Format: {base_dir}/[YYYY-MM-DD/]{YYYY-MM-DD_HH-MM-SS}_{target}_{amount}.png
    """
    ts = timestamp or datetime.now()
    base = Path(base_dir) if base_dir else Path(DEFAULT_SCREENSHOT_DIR)

    if daily_subfolder:
        base = base / ts.strftime("%Y-%m-%d")

    ts_str = ts.strftime(FILENAME_TIMESTAMP_FMT)

    parts = [ts_str]
    if target_name:
        parts.append(_sanitize_filename(target_name))
    if amount > 0:
        parts.append(f"{amount:.2f}")

    filename = "_".join(parts) + ".png"
    return base / filename


def save_screenshot(
    frame_bgr: np.ndarray,
    output_path: Path,
    blur_regions: list[dict] | None = None,
) -> bool:
    """Save a BGR frame as a PNG with optional blur regions.

    Creates parent directories as needed.
    Returns True on success.
    """
    if cv2 is None:
        log.error("OpenCV not available — cannot save screenshot")
        return False

    try:
        # Apply blur
        if blur_regions:
            frame_bgr = apply_blur_regions(frame_bgr, blur_regions)

        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save as PNG
        ok = cv2.imwrite(str(output_path), frame_bgr)
        if ok:
            log.info("Screenshot saved: %s", output_path)
        else:
            log.error("cv2.imwrite failed for %s", output_path)
        return ok
    except Exception as e:
        log.error("Failed to save screenshot: %s", e)
        return False
