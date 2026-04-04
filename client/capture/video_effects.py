"""Reusable video compositing effects — webcam overlay and chroma key."""

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from .constants import WEBCAM_OVERLAY_SCALE, get_interpolation


def apply_chroma_key(
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


def composite_webcam(
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
        resized, alpha = apply_chroma_key(resized, chroma)
        alpha_f = alpha.astype(np.float32) / 255.0
        alpha_3 = alpha_f[:, :, np.newaxis]
        roi = frame[y:y + target_h, x:x + target_w].astype(np.float32)
        blended = roi * (1.0 - alpha_3) + resized.astype(np.float32) * alpha_3
        frame[y:y + target_h, x:x + target_w] = np.clip(blended, 0, 255).astype(np.uint8)
    else:
        frame[y:y + target_h, x:x + target_w] = resized

    return frame
