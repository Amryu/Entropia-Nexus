"""Test script: capture live frames and evaluate tool-name OCR preprocessing.

Captures frames from the running Entropia Universe client, locates the heart
icon, extracts the tool-name ROI, and runs the ONNX CRNN recognizer with
multiple preprocessing strategies.  Saves annotated screenshots so you can
visually compare what works best for white text, yellow text, and no text.

Usage (from repo root):
    python -m client.scripts.test_tool_name_ocr          # single snapshot
    python -m client.scripts.test_tool_name_ocr --loop 5  # 5 captures, 1 s apart

Output goes to  client/scripts/_tool_ocr_output/
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CLIENT_DIR = os.path.dirname(_SCRIPT_DIR)
_REPO_ROOT = os.path.dirname(_CLIENT_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from client.platform import backend as _platform
from client.core.constants import GAME_TITLE_PREFIX
from client.ocr.capturer import ScreenCapturer
from client.ocr import onnxtr_recognizer
from client.ocr.onnxtr_recognizer import (
    _ensure_session, _preprocess, _ctc_decode,
    _INPUT_HEIGHT, _INPUT_WIDTH,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "_tool_ocr_output")
TEMPLATE_PATH = os.path.join(_CLIENT_DIR, "assets", "player_heart.png")
MATCH_THRESHOLD = 0.90
MIN_INSIDE_BRIGHTNESS = 180
MIN_CONTRAST = 30

# Default tool-name ROI (relative to heart top-left)
ROI_DX = 30
ROI_DY = 13
ROI_W = 315
ROI_H = 14

# Tool presence heuristic
TOOL_BRIGHTNESS_THRESHOLD = 100
TOOL_TEXT_MIN_RATIO = 0.05

MIN_CONFIDENCE = 0.20

# Word segmentation: minimum gap width (px) at 32px height to split words.
# Inter-word gaps are ~8-10px at 32h; intra-character gaps are 1-4px.
WORD_GAP_MIN_PX = 6


# ---------------------------------------------------------------------------
# Low-level ONNX helpers (bypass the 128px crop)
# ---------------------------------------------------------------------------

def _run_session(image_rgb: np.ndarray) -> tuple[str, float] | None:
    """Run ONNX inference on an RGB image. The shared _preprocess handles resize/pad."""
    session = _ensure_session()
    if session is None:
        return None
    input_name = onnxtr_recognizer._input_name
    if input_name is None:
        return None
    tensor = _preprocess(image_rgb)
    try:
        outputs = session.run(None, {input_name: tensor})
    except Exception:
        return None
    text, conf = _ctc_decode(outputs[0])
    text = text.strip()
    return (text, conf) if text else None


def _to_rgb_32h(crop_bgr: np.ndarray) -> np.ndarray:
    """Convert BGR to RGB and scale height to 32px (aspect-preserving)."""
    rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    if h != _INPUT_HEIGHT:
        scale = _INPUT_HEIGHT / h
        new_w = max(1, round(w * scale))
        rgb = cv2.resize(rgb, (new_w, _INPUT_HEIGHT), interpolation=cv2.INTER_CUBIC)
    return rgb


# ---------------------------------------------------------------------------
# Word segmentation
# ---------------------------------------------------------------------------

def _find_word_segments(gray_32h: np.ndarray) -> list[tuple[int, int]]:
    """Find word-level segments by detecting dark column gaps.

    Uses adaptive thresholding on column-mean brightness to separate
    text columns from background.  Gaps narrower than WORD_GAP_MIN_PX
    are treated as intra-word space (kerning, anti-aliasing).
    """
    h, w = gray_32h.shape[:2]
    col_mean = np.mean(gray_32h, axis=0)

    # Adaptive threshold: 15% of the way from background to text brightness
    median = np.median(col_mean)
    text_mean = float(np.mean(col_mean[col_mean > median]))
    bg_mean = float(np.mean(col_mean[col_mean <= median]))
    gap_threshold = bg_mean + (text_mean - bg_mean) * 0.15

    is_gap = col_mean < gap_threshold

    segments: list[tuple[int, int]] = []
    in_text = False
    seg_start = 0
    x = 0

    while x < w:
        if not is_gap[x] and not in_text:
            seg_start = x
            in_text = True
            x += 1
        elif is_gap[x] and in_text:
            gap_start = x
            while x < w and is_gap[x]:
                x += 1
            if x - gap_start >= WORD_GAP_MIN_PX:
                segments.append((seg_start, gap_start))
                in_text = False
        else:
            x += 1

    if in_text:
        segments.append((seg_start, w))

    return segments


def _split_wide_segment(gray32: np.ndarray, x0: int, x1: int,
                        max_w: int = _INPUT_WIDTH) -> list[tuple[int, int]]:
    """Force-split a segment wider than max_w at its darkest column gap."""
    width = x1 - x0
    if width <= max_w:
        return [(x0, x1)]

    col_mean = np.mean(gray32[:, x0:x1], axis=0)
    # Find the best split point near the middle (darkest column in center 60%)
    margin = int(width * 0.2)
    search = col_mean[margin:width - margin]
    split_rel = int(np.argmin(search)) + margin
    split_abs = x0 + split_rel

    # Recurse in case sub-segments are still too wide
    left = _split_wide_segment(gray32, x0, split_abs, max_w)
    right = _split_wide_segment(gray32, split_abs, x1, max_w)
    return left + right


def _ocr_word_segments(rgb32: np.ndarray, gray32: np.ndarray,
                       segments: list[tuple[int, int]]) -> tuple[str, float]:
    """OCR word segments, grouping adjacent ones that fit within 128px.

    If a batch would exceed model input width, force-splits at the
    darkest column gap to ensure every batch fits.
    """
    if not segments:
        return ("", 0.0)

    # Group adjacent segments into batches that fit within model input width
    batches: list[tuple[int, int]] = []
    batch_start = segments[0][0]
    batch_end = segments[0][1]

    for seg_start, seg_end in segments[1:]:
        if seg_end - batch_start <= _INPUT_WIDTH:
            batch_end = seg_end
        else:
            batches.append((batch_start, batch_end))
            batch_start = seg_start
            batch_end = seg_end
    batches.append((batch_start, batch_end))

    # Force-split any batches that are still too wide
    final_batches: list[tuple[int, int]] = []
    for bx0, bx1 in batches:
        final_batches.extend(_split_wide_segment(gray32, bx0, bx1))

    parts: list[str] = []
    confs: list[float] = []

    for bx0, bx1 in final_batches:
        r = _run_session(rgb32[:, bx0:bx1])
        if r and r[0]:
            parts.append(r[0])
            confs.append(r[1])

    if not parts:
        return ("", 0.0)
    return (" ".join(parts), sum(confs) / len(confs))


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def strategy_raw(crop_bgr: np.ndarray) -> tuple[str, float]:
    """Baseline: pass raw crop to recognize_text (crops at 128px)."""
    r = onnxtr_recognizer.recognize_text(crop_bgr, min_confidence=MIN_CONFIDENCE)
    return r if r else ("", 0.0)


def strategy_grayscale(crop_bgr: np.ndarray) -> tuple[str, float]:
    """Grayscale before recognition (still crops at 128px)."""
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    r = onnxtr_recognizer.recognize_text(bgr, min_confidence=MIN_CONFIDENCE)
    return r if r else ("", 0.0)


def _words_pipeline(crop_bgr: np.ndarray) -> tuple[str, float]:
    """Core word-segmentation pipeline: scale to 32h, find gaps, batch OCR."""
    rgb32 = _to_rgb_32h(crop_bgr)
    h, full_w = rgb32.shape[:2]

    if full_w <= _INPUT_WIDTH:
        r = _run_session(rgb32)
        return r if r else ("", 0.0)

    gray32 = cv2.cvtColor(
        cv2.cvtColor(rgb32.astype(np.uint8), cv2.COLOR_RGB2BGR),
        cv2.COLOR_BGR2GRAY,
    )
    segments = _find_word_segments(gray32)
    return _ocr_word_segments(rgb32, gray32, segments)


def strategy_words(crop_bgr: np.ndarray) -> tuple[str, float]:
    """Word segmentation on raw input."""
    return _words_pipeline(crop_bgr)


def strategy_words_grayscale(crop_bgr: np.ndarray) -> tuple[str, float]:
    """Word segmentation on grayscale input."""
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    return _words_pipeline(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))


def strategy_words_desat(crop_bgr: np.ndarray) -> tuple[str, float]:
    """Word segmentation with desaturated input (unifies white + yellow)."""
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    hsv[:, :, 1] = 0
    return _words_pipeline(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR))


def strategy_words_value(crop_bgr: np.ndarray) -> tuple[str, float]:
    """Word segmentation using HSV Value channel (brightness only)."""
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    return _words_pipeline(cv2.cvtColor(hsv[:, :, 2], cv2.COLOR_GRAY2BGR))


def strategy_fast(crop_bgr: np.ndarray) -> tuple[str, float]:
    """Optimized: grayscale, word-segment, batched inference, no PIL.

    Single-pass pipeline:
    1. Grayscale + scale to 32h (one cv2.resize)
    2. Word segmentation on column brightness
    3. Group segments into <=128px batches
    4. Build one [N,3,32,128] tensor (pure numpy, no PIL)
    5. Single batched ONNX call
    6. CTC decode all outputs
    """
    session = _ensure_session()
    if session is None:
        return ("", 0.0)
    input_name = onnxtr_recognizer._input_name
    if input_name is None:
        return ("", 0.0)

    # Grayscale + scale to 32h in one step
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    new_w = max(1, round(w * _INPUT_HEIGHT / h))
    gray32 = cv2.resize(gray, (new_w, _INPUT_HEIGHT), interpolation=cv2.INTER_CUBIC)

    # Single-call fast path
    if new_w <= _INPUT_WIDTH:
        return _fast_infer_gray(session, input_name, gray32)

    # Word segmentation
    segments = _find_word_segments(gray32)
    if not segments:
        return ("", 0.0)

    # Group into batches <= 128px, force-split oversized
    batches = _group_batches(segments)
    final: list[tuple[int, int]] = []
    for bx0, bx1 in batches:
        final.extend(_split_wide_segment(gray32, bx0, bx1))

    n = len(final)
    if n == 0:
        return ("", 0.0)

    # Build batch tensor: [N, 3, 32, 128] without PIL
    mean = _PREPROCESS_MEAN
    std = _PREPROCESS_STD
    batch = np.zeros((n, 3, _INPUT_HEIGHT, _INPUT_WIDTH), dtype=np.float32)
    for i, (bx0, bx1) in enumerate(final):
        seg = gray32[:, bx0:bx1]
        seg_w = seg.shape[1]
        # Normalize to [0,1], apply ImageNet mean/std (same across R/G/B for gray)
        normalized = (seg.astype(np.float32) / 255.0 - mean) / std
        batch[i, 0, :, :seg_w] = normalized
        batch[i, 1, :, :seg_w] = normalized
        batch[i, 2, :, :seg_w] = normalized
        # Right padding stays at (0 - mean) / std from np.zeros init
        # Fix padding to match model expectation (zero-padded = black)
        if seg_w < _INPUT_WIDTH:
            pad_val = (0.0 - mean) / std
            batch[i, 0, :, seg_w:] = pad_val
            batch[i, 1, :, seg_w:] = pad_val
            batch[i, 2, :, seg_w:] = pad_val

    # Single batched inference
    try:
        outputs = session.run(None, {input_name: batch})
    except Exception:
        return ("", 0.0)

    # CTC decode each sequence
    logits = outputs[0]  # [N, seq_len, 127]
    parts: list[str] = []
    confs: list[float] = []
    for i in range(n):
        text, conf = _ctc_decode(logits[i:i+1])
        text = text.strip()
        if text:
            parts.append(text)
            confs.append(conf)

    if not parts:
        return ("", 0.0)
    return (" ".join(parts), sum(confs) / len(confs))


def _fast_infer_gray(session, input_name: str,
                     gray32: np.ndarray) -> tuple[str, float]:
    """Single-segment fast path for short text that fits in 128px."""
    w = gray32.shape[1]
    mean = _PREPROCESS_MEAN
    std = _PREPROCESS_STD
    normalized = (gray32.astype(np.float32) / 255.0 - mean) / std
    tensor = np.zeros((1, 3, _INPUT_HEIGHT, _INPUT_WIDTH), dtype=np.float32)
    tensor[0, 0, :, :w] = normalized
    tensor[0, 1, :, :w] = normalized
    tensor[0, 2, :, :w] = normalized
    if w < _INPUT_WIDTH:
        pad_val = (0.0 - mean) / std
        tensor[0, :, :, w:] = pad_val
    try:
        outputs = session.run(None, {input_name: tensor})
    except Exception:
        return ("", 0.0)
    text, conf = _ctc_decode(outputs[0])
    text = text.strip()
    return (text, conf) if text else ("", 0.0)


def _group_batches(segments: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Group adjacent word segments into batches that fit within 128px."""
    batches: list[tuple[int, int]] = []
    bs, be = segments[0]
    for s, e in segments[1:]:
        if e - bs <= _INPUT_WIDTH:
            be = e
        else:
            batches.append((bs, be))
            bs, be = s, e
    batches.append((bs, be))
    return batches


# Precomputed: mean of the 3 ImageNet channels (they're nearly identical for this model)
_PREPROCESS_MEAN = float(np.mean([0.694, 0.695, 0.693]))
_PREPROCESS_STD = float(np.mean([0.299, 0.296, 0.301]))


STRATEGIES: list[tuple[str, callable]] = [
    ("raw (128px crop)", strategy_raw),
    ("grayscale (crop)", strategy_grayscale),
    ("words+gray", strategy_words_grayscale),
    ("fast", strategy_fast),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_heart(image: np.ndarray, template_raw, mask_bool, inv_bool):
    """Locate the heart icon.  Returns (tx, ty) or None."""
    template_gray = template_raw[:, :, 3]
    th, tw = template_gray.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    result = cv2.matchTemplate(gray, template_gray, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < MATCH_THRESHOLD:
        return None
    x, y = max_loc
    region = image[y:y + th, x:x + tw]
    region_gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    inside = float(np.mean(region_gray[mask_bool]))
    outside = float(np.mean(region_gray[inv_bool]))
    if inside < MIN_INSIDE_BRIGHTNESS or inside - outside < MIN_CONTRAST:
        return None
    return (x, y)


def classify_tool_presence(tool_region_bgr: np.ndarray) -> str:
    """Classify as 'white', 'yellow', or 'empty'.

    Real text has brightness distributed across the middle rows.
    An empty ROI may have a bright border at top/bottom but dark middle.
    """
    gray = cv2.cvtColor(tool_region_bgr, cv2.COLOR_BGR2GRAY)
    h = gray.shape[0]

    # Check the inner third of rows for text presence (excludes border artifacts)
    y0 = max(1, h // 3)
    y1 = h - y0
    middle = gray[y0:y1, :]
    middle_bright = int(np.count_nonzero(middle > TOOL_BRIGHTNESS_THRESHOLD))
    if middle_bright <= middle.size * TOOL_TEXT_MIN_RATIO:
        return "empty"

    # Check for yellow via HSV saturation in the warm hue range
    hsv = cv2.cvtColor(tool_region_bgr, cv2.COLOR_BGR2HSV)
    yellow_mask = cv2.inRange(hsv, (15, 80, 150), (40, 255, 255))
    if np.count_nonzero(yellow_mask) / gray.size > 0.03:
        return "yellow"
    return "white"


# ---------------------------------------------------------------------------
# Core test
# ---------------------------------------------------------------------------

def capture_and_test(capturer, hwnd, template_raw, mask_bool, inv_bool, idx):
    frame = capturer.capture_window(hwnd)
    if frame is None:
        print(f"  [frame {idx}] Capture failed")
        return

    heart = find_heart(frame, template_raw, mask_bool, inv_bool)
    if heart is None:
        print(f"  [frame {idx}] Heart icon not found")
        cv2.imwrite(os.path.join(OUTPUT_DIR, f"frame_{idx:03d}_no_heart.png"), frame)
        return

    tx, ty = heart
    rx, ry = tx + ROI_DX, ty + ROI_DY
    ih, iw = frame.shape[:2]
    if rx < 0 or ry < 0 or rx + ROI_W > iw or ry + ROI_H > ih:
        print(f"  [frame {idx}] Tool ROI out of bounds")
        return

    tool_region = frame[ry:ry + ROI_H, rx:rx + ROI_W].copy()
    text_class = classify_tool_presence(tool_region)

    print(f"\n  [frame {idx}] Heart at ({tx},{ty}) | "
          f"Tool ROI at ({rx},{ry}) {ROI_W}x{ROI_H} | Class: {text_class}")

    # Save ROI (4x for visibility)
    roi_vis = cv2.resize(tool_region, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(os.path.join(OUTPUT_DIR, f"frame_{idx:03d}_{text_class}_roi.png"), roi_vis)

    if text_class == "empty":
        print(f"  => No tool equipped (empty ROI - skipping OCR)")
        # Save annotated crop
        _save_annotated(frame, template_raw, tx, ty, rx, ry, text_class, idx)
        return

    # Run all strategies
    rgb32 = _to_rgb_32h(tool_region)
    h32, w32 = rgb32.shape[:2]
    print(f"  Scaled to 32px height: {w32}x{h32} (model input: {_INPUT_WIDTH}x{_INPUT_HEIGHT})")
    print()
    print(f"  {'Strategy':<22} {'Text':<50} {'Conf':>6} {'Time':>8}")
    print(f"  {'-'*22} {'-'*50} {'-'*6} {'-'*8}")

    best_text, best_conf, best_name = "", 0.0, ""
    for name, fn in STRATEGIES:
        t0 = time.perf_counter()
        text, conf = fn(tool_region)
        elapsed = (time.perf_counter() - t0) * 1000
        display = text or "-"
        if len(display) > 48:
            display = display[:48] + ".."
        print(f"  {name:<22} {display:<50} {conf:>5.1%} {elapsed:>6.1f}ms")
        if len(text) > len(best_text) or (len(text) == len(best_text) and conf > best_conf):
            best_text, best_conf, best_name = text, conf, name

    print(f"\n  => Best: [{best_name}] \"{best_text}\" ({best_conf:.1%})")
    _save_annotated(frame, template_raw, tx, ty, rx, ry, text_class, idx)


def _save_annotated(frame, template_raw, tx, ty, rx, ry, text_class, idx):
    """Save annotated crop around the HUD area."""
    ih, iw = frame.shape[:2]
    th, tw = template_raw.shape[:2]
    annotated = frame.copy()
    cv2.rectangle(annotated, (tx, ty), (tx + tw, ty + th), (0, 0, 255), 1)
    cv2.rectangle(annotated, (rx, ry), (rx + ROI_W, ry + ROI_H), (0, 255, 255), 1)
    margin = 40
    c = annotated[max(0, ty - margin):min(ih, ry + ROI_H + margin),
                  max(0, tx - margin):min(iw, rx + ROI_W + margin)]
    cv2.imwrite(os.path.join(OUTPUT_DIR, f"frame_{idx:03d}_{text_class}_annotated.png"), c)


def main():
    parser = argparse.ArgumentParser(description="Test tool-name OCR preprocessing")
    parser.add_argument("--loop", type=int, default=1,
                        help="Number of captures (1 s apart)")
    args = parser.parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    template_raw = cv2.imread(TEMPLATE_PATH, cv2.IMREAD_UNCHANGED)
    if template_raw is None:
        print(f"ERROR: Cannot load template: {TEMPLATE_PATH}")
        sys.exit(1)
    mask_bool = template_raw[:, :, 3] > 0
    inv_bool = ~mask_bool

    print("Loading ONNX model...")
    if not onnxtr_recognizer.is_available():
        print("ERROR: ONNX runtime not available")
        sys.exit(1)
    # Warm-up inference
    onnxtr_recognizer.recognize_text(
        np.zeros((32, 128, 3), dtype=np.uint8), min_confidence=0.0,
    )
    print("ONNX model ready.\n")

    hwnd = _platform.find_window_by_title_prefix(GAME_TITLE_PREFIX)
    if not hwnd:
        print(f"ERROR: Game window not found (prefix: '{GAME_TITLE_PREFIX}')")
        sys.exit(1)
    print(f"Game window: hwnd={hwnd}")

    capturer = ScreenCapturer(capture_backend="bitblt")
    print(f"Capturing {args.loop} frame(s)...\n")

    for i in range(args.loop):
        if i > 0:
            time.sleep(1.0)
        capture_and_test(capturer, hwnd, template_raw, mask_bool, inv_bool, i)

    print(f"\nOutput saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
