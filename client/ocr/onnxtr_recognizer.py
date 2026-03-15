"""OnnxTR-based text recognition for radar coordinate OCR.

Lazily loads the crnn_mobilenet_v3_large model (8-bit quantized, ~9 MB) on
first call.  Thread-safe: the model is loaded once and reused across ticks.
"""

from __future__ import annotations

import re
import threading

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from ..core.logger import get_logger

log = get_logger("OnnxTR")

_COORD_RE = re.compile(r"\d{1,6}")
_TARGET_HEIGHT = 32  # minimum crop height for reliable recognition

# Expected label prefixes per row type.  OnnxTR often misreads these as
# similar-looking characters (e.g. "L0n", "1at"), so we fuzzy-match and
# strip them before extracting the digit coordinate.
_LABEL_PATTERNS: dict[str, re.Pattern] = {
    "lon": re.compile(r"^[Ll1][Oo0][Nn][:\s]*"),
    "lat": re.compile(r"^[Ll1][Aa][Tt][:\s]*"),
}

# Module-level singleton
_lock = threading.Lock()
_predictor = None
_load_attempted = False


def _ensure_predictor():
    """Lazily load the recognition predictor (thread-safe)."""
    global _predictor, _load_attempted
    if _predictor is not None or _load_attempted:
        return _predictor
    with _lock:
        if _predictor is not None or _load_attempted:
            return _predictor
        _load_attempted = True
        try:
            # Limit OnnxRuntime to 1 thread — the model is tiny (32x128 input)
            # and thread synchronization overhead outweighs parallelism.
            import onnxruntime as _ort
            from onnxtr.models import recognition_predictor
            from onnxtr.models.engine import EngineConfig

            so = _ort.SessionOptions()
            so.intra_op_num_threads = 1
            so.inter_op_num_threads = 1

            _predictor = recognition_predictor(
                arch="crnn_mobilenet_v3_large",
                load_in_8_bit=True,
                engine_cfg=EngineConfig(session_options=so),
            )
            log.info("OnnxTR loaded (crnn_mobilenet_v3_large 8-bit, 1 thread)")
        except Exception as e:
            log.warning("Failed to load OnnxTR: %s", e)
            _predictor = None
    return _predictor


def is_available() -> bool:
    """Return True if OnnxTR can be loaded and the model is ready."""
    return _ensure_predictor() is not None


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
    predictor = _ensure_predictor()
    if predictor is None or cv2 is None:
        return None
    if crop_bgr is None or crop_bgr.size == 0:
        return None

    # BGR → RGB
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)

    # Upscale small crops so text is at least _TARGET_HEIGHT px tall
    h, w = crop_rgb.shape[:2]
    if h < _TARGET_HEIGHT:
        scale = _TARGET_HEIGHT / h
        new_w = max(1, round(w * scale))
        crop_rgb = cv2.resize(
            crop_rgb, (new_w, _TARGET_HEIGHT), interpolation=cv2.INTER_CUBIC,
        )

    try:
        result = predictor([crop_rgb])
    except Exception:
        return None

    if not result:
        return None

    # Extract text + confidence from the result entry
    raw_text = ""
    raw_conf = 0.0
    entry = result[0]
    if isinstance(entry, tuple) and len(entry) >= 2:
        raw_text = str(entry[0])
        raw_conf = float(entry[1])
    elif isinstance(entry, list) and entry:
        raw_text = "".join(w[0] for w in entry)
        raw_conf = float(min(w[1] for w in entry)) if entry else 0.0
    elif isinstance(entry, str):
        raw_text = entry
        raw_conf = 1.0

    # Strip label prefix ("Lon:", "Lat:") if present
    text = raw_text.strip()
    log.debug("OnnxTR raw: %r (conf=%.3f, row=%s)", raw_text, raw_conf, row)
    if row and row in _LABEL_PATTERNS:
        text = _LABEL_PATTERNS[row].sub("", text)
        log.debug("OnnxTR stripped: %r", text)

    # Extract 1–6 digit coordinate from the remaining text
    digits = "".join(c for c in text if c.isdigit())
    m = _COORD_RE.search(digits)
    if m is None:
        return None

    try:
        value = int(m.group())
    except ValueError:
        return None

    return value, raw_conf
