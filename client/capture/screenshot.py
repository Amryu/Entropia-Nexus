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
from .constants import DEFAULT_SCREENSHOT_DIR, FILENAME_TIMESTAMP_FMT, get_interpolation

log = get_logger("Screenshot")

# Characters not allowed in filenames
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize_filename(name: str) -> str:
    """Replace unsafe filename characters with dashes."""
    return _UNSAFE_CHARS.sub("-", name).strip(" .-")


def load_background_image(path: str) -> np.ndarray | None:
    """Load a background image from disk. Returns BGR numpy array or None."""
    if cv2 is None or not path:
        return None
    try:
        p = Path(path)
        if not p.is_file():
            return None
        # For video files, grab the first frame
        video_exts = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv", ".flv"}
        if p.suffix.lower() in video_exts:
            cap = cv2.VideoCapture(str(p))
            if cap.isOpened():
                ok, frame = cap.read()
                cap.release()
                return frame if ok else None
            cap.release()
            return None
        # Image file
        return cv2.imread(str(p))
    except Exception:
        return None


def compose_on_background(
    frame: np.ndarray,
    background: np.ndarray,
    target_w: int,
    target_h: int,
    scaling: str = "lanczos",
) -> np.ndarray:
    """Place the game frame centered on a background canvas at the target resolution.

    The background is stretched to fill (target_w, target_h).
    The game frame is scaled to fit (maintaining aspect ratio) and centered.

    If the game frame already matches the target size exactly, returns
    the frame unchanged (no background visible).
    """
    if cv2 is None:
        return frame

    fh, fw = frame.shape[:2]

    # If frame matches target exactly, no compositing needed
    if fw == target_w and fh == target_h:
        return frame

    # Build canvas from background (stretched to fill)
    interp = get_interpolation(scaling)
    canvas = cv2.resize(background, (target_w, target_h), interpolation=interp)

    # Scale game frame to fit within target, maintaining aspect ratio
    scale = min(target_w / fw, target_h / fh)
    new_w = int(fw * scale)
    new_h = int(fh * scale)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=interp)

    # Center on canvas
    x_off = (target_w - new_w) // 2
    y_off = (target_h - new_h) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized

    return canvas


def apply_blur_regions(
    frame: np.ndarray,
    blur_regions: list[dict],
) -> np.ndarray:
    """Apply gaussian blur to specified regions of a frame.

    Args:
        frame: BGR image (numpy array).
        blur_regions: List of dicts with normalized coords {x, y, w, h} (0.0-1.0).

    Returns:
        The frame with blur applied (modified in-place).
    """
    if not blur_regions or cv2 is None:
        return frame
    h, w = frame.shape[:2]
    for region in blur_regions:
        rx = max(0, int(region.get("x", 0) * w))
        ry = max(0, int(region.get("y", 0) * h))
        rw = min(w - rx, int(region.get("w", 0) * w))
        rh = min(h - ry, int(region.get("h", 0) * h))
        if rw <= 0 or rh <= 0:
            continue
        roi = frame[ry:ry + rh, rx:rx + rw]
        # Heavy blur kernel — must be odd
        ksize = max(31, (min(rw, rh) // 3) | 1)
        frame[ry:ry + rh, rx:rx + rw] = cv2.GaussianBlur(roi, (ksize, ksize), 0)
    return frame


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
    background: np.ndarray | None = None,
    target_resolution: tuple[int, int] | None = None,
    size_pct: int = 100,
    scaling: str = "lanczos",
) -> bool:
    """Save a BGR frame as a PNG with optional blur regions and background.

    Creates parent directories as needed.

    Args:
        target_resolution: Optional (width, height) for background compositing.
            When set and a background is provided, the frame is placed centered
            on the background at this resolution.  Without it, background
            compositing is skipped (the frame keeps its original size).
        size_pct: Percentage of source resolution (25, 50, 75, or 100).
            Applied after background compositing but before blur.

    Returns True on success.
    """
    if cv2 is None:
        log.error("OpenCV not available — cannot save screenshot")
        return False

    try:
        # Composite on background if provided and a target resolution is set
        if background is not None and target_resolution is not None:
            tw, th = target_resolution
            frame_bgr = compose_on_background(frame_bgr, background, tw, th, scaling=scaling)

        # Scale to requested percentage of source resolution
        if size_pct < 100:
            h, w = frame_bgr.shape[:2]
            scale = size_pct / 100.0
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            frame_bgr = cv2.resize(frame_bgr, (new_w, new_h),
                                   interpolation=get_interpolation(scaling))

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
