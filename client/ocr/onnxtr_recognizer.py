"""CRNN text recognition via raw onnxruntime.

Lazily downloads and loads the crnn_mobilenet_v3_large model (8-bit
quantized, ~9 MB) on first call.  Thread-safe: the model is loaded once
and reused across ticks.

Public API
----------
- ``recognize_text``       -- single-segment OCR (crops at 128 px)
- ``recognize_text_wide``  -- word-segmented batched OCR for wide images
- ``recognize_coordinate`` -- coordinate value from a row image
- ``is_available``         -- check if the model is ready
"""

from __future__ import annotations

import hashlib
import re
import string
import threading
import urllib.request
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.logger import get_logger

log = get_logger("CRNN")

# A failed onnxruntime import (DLL init error) leaves behind a native
# thread pool that busy-loops at 100% CPU.  We use a sentinel file so
# the broken import only happens once *ever*, not once per session.
_ORT_BROKEN_SENTINEL = Path("~/.entropia-nexus/.ort_broken").expanduser()

# ── Model download ───────────────────────────────────────────────────────────

_MODEL_URL = (
    "https://github.com/felixdittrich92/OnnxTR/releases/download/v0.1.2/"
    "crnn_mobilenet_v3_large_static_8_bit-459e856d.onnx"
)
_MODEL_FILENAME = "crnn_mobilenet_v3_large_static_8_bit-459e856d.onnx"
_MODEL_SHA256_PREFIX = "459e856d"
_MODEL_CACHE_DIR = Path("~/.entropia-nexus/models").expanduser()

# ── Preprocessing constants ──────────────────────────────────────────────────

_INPUT_HEIGHT = 32
_INPUT_WIDTH = 128
_MEAN = np.array([0.694, 0.695, 0.693], dtype=np.float32)
_STD = np.array([0.299, 0.296, 0.301], dtype=np.float32)

# ── CTC vocabulary (onnxtr "french") ─────────────────────────────────────────
# Must match the charset the model was trained on, in exact index order.
# 126 chars + blank at index 126 = 127 output classes.

VOCAB = (
    string.digits
    + string.ascii_letters
    + string.punctuation
    + "°£€¥¢฿"
    + "àâéèêëîïôùûüçÀÂÉÈÊËÎÏÔÙÛÜÇ"
)
BLANK_IDX = len(VOCAB)  # 126

# ── Coordinate extraction ────────────────────────────────────────────────────

_COORD_RE = re.compile(r"\d{1,6}")
_TARGET_HEIGHT = 32

_LABEL_PATTERNS: dict[str, re.Pattern] = {
    "lon": re.compile(r"^[Ll1][Oo0][Nn][:\s]*"),
    "lat": re.compile(r"^[Ll1][Aa][Tt][:\s]*"),
}

# ── Internals ────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_session = None
_input_name: str | None = None
_load_attempted = False


def _download_model() -> Path | None:
    """Download the CRNN ONNX model to the cache directory."""
    cache_dir = _MODEL_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / _MODEL_FILENAME

    if target.is_file():
        h = hashlib.sha256()
        with open(target, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        if h.hexdigest().startswith(_MODEL_SHA256_PREFIX):
            return target
        log.warning("Model hash mismatch, re-downloading")
        target.unlink()

    log.info("Downloading CRNN model (%s)...", _MODEL_URL)
    try:
        tmp = target.with_suffix(".tmp")
        urllib.request.urlretrieve(_MODEL_URL, str(tmp))
        h = hashlib.sha256()
        with open(tmp, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        if not h.hexdigest().startswith(_MODEL_SHA256_PREFIX):
            log.error("Downloaded model hash mismatch")
            tmp.unlink(missing_ok=True)
            return None
        tmp.rename(target)
        log.info("Model cached at %s", target)
        return target
    except Exception as e:
        log.warning("Failed to download CRNN model: %s", e)
        return None


def _preprocess(image_rgb: np.ndarray) -> np.ndarray:
    """Resize, pad, normalize an RGB image to a BCHW float32 tensor."""
    from PIL import Image

    h, w = image_rgb.shape[:2]
    # Resize height to _INPUT_HEIGHT, preserve aspect ratio
    new_w = max(1, round(w * _INPUT_HEIGHT / h))

    pil_img = Image.fromarray(image_rgb)
    pil_img = pil_img.resize((new_w, _INPUT_HEIGHT), Image.BILINEAR)

    # Crop or pad width to _INPUT_WIDTH
    arr = np.array(pil_img, dtype=np.float32) / 255.0
    if new_w > _INPUT_WIDTH:
        arr = arr[:, :_INPUT_WIDTH, :]
    elif new_w < _INPUT_WIDTH:
        padded = np.zeros((_INPUT_HEIGHT, _INPUT_WIDTH, 3), dtype=np.float32)
        padded[:, :new_w, :] = arr
        arr = padded

    arr = (arr - _MEAN) / _STD
    return arr.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)


def _ctc_decode(logits: np.ndarray) -> tuple[str, float]:
    """CTC greedy decode.  *logits* shape: ``[1, seq_len, num_classes]``."""
    seq = logits[0]  # [seq_len, num_classes]

    # Numerically stable softmax along classes axis
    exp = np.exp(seq - seq.max(axis=1, keepdims=True))
    probs = exp / exp.sum(axis=1, keepdims=True)

    indices = probs.argmax(axis=1)
    max_probs = probs.max(axis=1)

    chars: list[str] = []
    char_probs: list[float] = []
    prev_idx = -1
    for t, idx in enumerate(indices):
        if idx == prev_idx:
            continue
        prev_idx = int(idx)
        if idx == BLANK_IDX:
            continue
        if idx < len(VOCAB):
            chars.append(VOCAB[idx])
            char_probs.append(float(max_probs[t]))

    text = "".join(chars)
    confidence = min(char_probs) if char_probs else 0.0
    return text, confidence


def _ensure_session():
    """Lazily load the ONNX inference session (thread-safe)."""
    global _session, _input_name, _load_attempted
    if _session is not None or _load_attempted:
        return _session
    with _lock:
        if _session is not None or _load_attempted:
            return _session
        _load_attempted = True
        try:
            # Guard: a failed onnxruntime import (DLL init error) leaves
            # behind a native thread pool that busy-loops at 100% CPU.
            # A sentinel file persists the failure across sessions so the
            # broken import never happens again.
            if _ORT_BROKEN_SENTINEL.exists():
                log.info(
                    "onnxruntime previously failed to load — skipping.  "
                    "Delete %s to retry after installing VC++ runtime.",
                    _ORT_BROKEN_SENTINEL,
                )
                return None
            try:
                import onnxruntime as ort
            except (ImportError, OSError) as e:
                log.warning("onnxruntime unavailable: %s", e)
                if "DLL" in str(e):
                    log.warning(
                        "This usually means the Visual C++ 2015-2022 "
                        "Redistributable is missing or corrupted. "
                        "Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe"
                    )
                try:
                    _ORT_BROKEN_SENTINEL.parent.mkdir(parents=True, exist_ok=True)
                    _ORT_BROKEN_SENTINEL.write_text(
                        "onnxruntime import failed. Delete this file to retry.\n"
                    )
                except OSError:
                    pass
                return None

            model_path = _download_model()
            if model_path is None:
                return None

            so = ort.SessionOptions()
            so.intra_op_num_threads = 1
            so.inter_op_num_threads = 1
            so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            so.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )

            _session = ort.InferenceSession(
                str(model_path),
                sess_options=so,
                providers=["CPUExecutionProvider"],
            )
            _input_name = _session.get_inputs()[0].name

            # Sanity-check: model output classes must match vocab + blank
            out_shape = _session.get_outputs()[0].shape
            if isinstance(out_shape[-1], int) and out_shape[-1] != BLANK_IDX + 1:
                log.error(
                    "Model output classes (%s) != expected (%d)",
                    out_shape[-1],
                    BLANK_IDX + 1,
                )
                _session = None
                return None

            log.info("CRNN model loaded (%s, 1 thread)", model_path.name)
        except Exception as e:
            log.warning("Failed to load CRNN model: %s", e)
            _session = None
    return _session


# ── Public API ───────────────────────────────────────────────────────────────


def is_available() -> bool:
    """Return True if the CRNN model can be loaded and is ready."""
    return _ensure_session() is not None


def recognize_text(
    crop_bgr: np.ndarray,
    min_confidence: float = 0.3,
) -> tuple[str, float] | None:
    """Recognize arbitrary text from a cropped BGR image.

    Parameters
    ----------
    crop_bgr : np.ndarray
        BGR image of the text region.
    min_confidence : float
        Minimum per-character confidence threshold.

    Returns
    -------
    ``(text, confidence)`` or ``None`` if recognition fails or is below
    the confidence threshold.
    """
    session = _ensure_session()
    if session is None or cv2 is None:
        return None
    if crop_bgr is None or crop_bgr.size == 0:
        return None

    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)

    h, w = crop_rgb.shape[:2]
    if h < _TARGET_HEIGHT:
        scale = _TARGET_HEIGHT / h
        new_w = max(1, round(w * scale))
        crop_rgb = cv2.resize(
            crop_rgb, (new_w, _TARGET_HEIGHT), interpolation=cv2.INTER_CUBIC,
        )

    tensor = _preprocess(crop_rgb)
    try:
        outputs = session.run(None, {_input_name: tensor})
    except Exception:
        return None

    text, confidence = _ctc_decode(outputs[0])
    text = text.strip()

    if not text or confidence < min_confidence:
        return None

    return text, confidence


# ── Wide-text recognition ────────────────────────────────────────────────────
# Scalar mean/std (the 3 ImageNet channels are nearly identical for this model)
_SCALAR_MEAN = float(np.mean([0.694, 0.695, 0.693]))
_SCALAR_STD = float(np.mean([0.299, 0.296, 0.301]))

# Word segmentation: minimum gap width (px at 32 h) to split words.
# Inter-word gaps are ~8-10 px; intra-character gaps are 1-4 px.
_WORD_GAP_MIN_PX = 6


def _find_word_segments(gray_32h: np.ndarray) -> list[tuple[int, int]]:
    """Find word-level segments by detecting dark column gaps."""
    w = gray_32h.shape[1]
    col_mean = np.mean(gray_32h, axis=0)

    median = float(np.median(col_mean))
    text_mean = float(np.mean(col_mean[col_mean > median]))
    bg_mean = float(np.mean(col_mean[col_mean <= median]))
    gap_thr = bg_mean + (text_mean - bg_mean) * 0.15

    is_gap = col_mean < gap_thr

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
            if x - gap_start >= _WORD_GAP_MIN_PX:
                segments.append((seg_start, gap_start))
                in_text = False
        else:
            x += 1
    if in_text:
        segments.append((seg_start, w))
    return segments


def _split_wide(gray_32h: np.ndarray, x0: int, x1: int) -> list[tuple[int, int]]:
    """Force-split a segment wider than _INPUT_WIDTH at its darkest gap."""
    if x1 - x0 <= _INPUT_WIDTH:
        return [(x0, x1)]
    col_mean = np.mean(gray_32h[:, x0:x1], axis=0)
    margin = int((x1 - x0) * 0.2)
    split_rel = int(np.argmin(col_mean[margin:-margin or 1])) + margin
    mid = x0 + split_rel
    return _split_wide(gray_32h, x0, mid) + _split_wide(gray_32h, mid, x1)


def recognize_text_wide(
    crop_bgr: np.ndarray,
    min_confidence: float = 0.3,
) -> tuple[str, float] | None:
    """Recognize text from a wide BGR image using word-segmented batched inference.

    Handles images wider than 128 px (at 32 px height) by splitting at
    natural word boundaries, batching all segments into a single ONNX call,
    and joining the results with spaces.

    For images that fit in one segment this is equivalent to (but slightly
    faster than) ``recognize_text`` because it skips PIL entirely.

    Parameters
    ----------
    crop_bgr : np.ndarray
        BGR image of the text region (any height, any width).
    min_confidence : float
        Minimum per-character confidence threshold.

    Returns
    -------
    ``(text, confidence)`` or ``None`` if recognition fails.
    """
    session = _ensure_session()
    if session is None or _input_name is None:
        return None

    prepared = _prepare_wide_batches(crop_bgr)
    if prepared is None:
        return None
    gray32, batches = prepared
    return _infer_gray_batch(session, gray32, batches, min_confidence)


def _infer_gray_batch(
    session,
    gray32: np.ndarray,
    regions: list[tuple[int, int]],
    min_confidence: float,
) -> tuple[str, float] | None:
    """Build a batch tensor from grayscale regions and run one inference call."""
    n = len(regions)
    mean = _SCALAR_MEAN
    std = _SCALAR_STD
    pad_val = (0.0 - mean) / std

    batch = np.full((n, 3, _INPUT_HEIGHT, _INPUT_WIDTH), pad_val, dtype=np.float32)
    for i, (x0, x1) in enumerate(regions):
        seg = gray32[:, x0:x1]
        seg_w = min(seg.shape[1], _INPUT_WIDTH)
        normalized = (seg[:, :seg_w].astype(np.float32) / 255.0 - mean) / std
        batch[i, 0, :, :seg_w] = normalized
        batch[i, 1, :, :seg_w] = normalized
        batch[i, 2, :, :seg_w] = normalized

    try:
        outputs = session.run(None, {_input_name: batch})
    except Exception:
        return None

    logits = outputs[0]  # [N, seq_len, 127]
    parts: list[str] = []
    confs: list[float] = []
    for i in range(n):
        text, conf = _ctc_decode(logits[i:i + 1])
        text = text.strip()
        if text:
            parts.append(text)
            confs.append(conf)

    if not parts:
        return None
    joined = " ".join(parts)
    avg_conf = sum(confs) / len(confs)
    if avg_conf < min_confidence:
        return None
    return joined, avg_conf


def _prepare_wide_batches(
    crop_bgr: np.ndarray,
) -> tuple[np.ndarray, list[tuple[int, int]]] | None:
    """Prepare gray32 image and final batch ranges for wide-text recognition.

    Returns ``(gray32, batches)`` or ``None`` on failure.
    """
    if cv2 is None or crop_bgr is None or crop_bgr.size == 0:
        return None

    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    new_w = max(1, round(w * _INPUT_HEIGHT / h))
    gray32 = cv2.resize(gray, (new_w, _INPUT_HEIGHT), interpolation=cv2.INTER_CUBIC)

    if new_w <= _INPUT_WIDTH:
        return gray32, [(0, new_w)]

    segments = _find_word_segments(gray32)
    if not segments:
        return None

    # Group adjacent word segments into batches that fit within model width
    batches: list[tuple[int, int]] = []
    bs, be = segments[0]
    for s, e in segments[1:]:
        if e - bs <= _INPUT_WIDTH:
            be = e
        else:
            batches.append((bs, be))
            bs, be = s, e
    batches.append((bs, be))

    # Force-split any batches still wider than model input
    final: list[tuple[int, int]] = []
    for bx0, bx1 in batches:
        final.extend(_split_wide(gray32, bx0, bx1))

    return (gray32, final) if final else None


def recognize_text_wide_iter(
    crop_bgr: np.ndarray,
    min_confidence: float = 0.3,
):
    """Generator that yields ``(text, confidence)`` progressively.

    Lets callers stop early once they have enough information to act
    (e.g., the prefix uniquely identifies a known item).

    Yield order:
    1. Result from the first batch only (~5 ms).
    2. Result from all batches combined (~5 ms + ~20 ms for the rest).

    For text that fits in a single batch, only one yield occurs.

    Stopping iteration after the first yield skips the second inference
    call and saves ~20 ms.
    """
    session = _ensure_session()
    if session is None or _input_name is None:
        return

    prepared = _prepare_wide_batches(crop_bgr)
    if prepared is None:
        return
    gray32, batches = prepared

    if len(batches) == 1:
        result = _infer_gray_batch(session, gray32, batches, min_confidence)
        if result is not None:
            yield result
        return

    # Phase 1: first batch only (fast path)
    first = _infer_gray_batch(session, gray32, batches[:1], min_confidence)
    if first is None:
        return
    yield first

    # Phase 2: remaining batches (only runs if caller iterates again)
    rest = _infer_gray_batch(session, gray32, batches[1:], min_confidence)
    if rest is None:
        return
    combined_text = f"{first[0]} {rest[0]}"
    combined_conf = min(first[1], rest[1])
    yield (combined_text, combined_conf)


def recognize_coordinate(
    crop_bgr: np.ndarray,
    row: str | None = None,
) -> tuple[int, float] | None:
    """Recognize a coordinate value from a cropped BGR row image.

    Parameters
    ----------
    crop_bgr : np.ndarray
        BGR image of the coordinate row (may include the "Lon:"/"Lat:" label).
    row : str or None
        Expected row type (``"lon"`` or ``"lat"``).  When provided, the label
        prefix is stripped from the OCR text and acts as a checksum — if the
        label is present it confirms we're reading the right region.

    Returns
    -------
    ``(value, confidence)`` or ``None`` if recognition fails.
    """
    session = _ensure_session()
    if session is None or cv2 is None:
        return None
    if crop_bgr is None or crop_bgr.size == 0:
        return None

    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)

    h, w = crop_rgb.shape[:2]
    if h < _TARGET_HEIGHT:
        scale = _TARGET_HEIGHT / h
        new_w = max(1, round(w * scale))
        crop_rgb = cv2.resize(
            crop_rgb, (new_w, _TARGET_HEIGHT), interpolation=cv2.INTER_CUBIC,
        )

    tensor = _preprocess(crop_rgb)
    try:
        outputs = session.run(None, {_input_name: tensor})
    except Exception:
        return None

    raw_text, raw_conf = _ctc_decode(outputs[0])

    text = raw_text.strip()
    log.debug("CRNN raw: %r (conf=%.3f, row=%s)", raw_text, raw_conf, row)
    if row and row in _LABEL_PATTERNS:
        text = _LABEL_PATTERNS[row].sub("", text)
        log.debug("CRNN stripped: %r", text)

    digits = "".join(c for c in text if c.isdigit())
    m = _COORD_RE.search(digits)
    if m is None:
        return None

    try:
        value = int(m.group())
    except ValueError:
        return None

    return value, raw_conf
