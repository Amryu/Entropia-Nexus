"""CRNN text recognition for radar coordinate OCR (raw onnxruntime).

Lazily downloads and loads the crnn_mobilenet_v3_large model (8-bit
quantized, ~9 MB) on first call.  Thread-safe: the model is loaded once
and reused across ticks.
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
            import onnxruntime as ort

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
