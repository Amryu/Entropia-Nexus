"""OCR Trace Mode — dedicated log file + rolling debug images.

When enabled, every OCR decision (skill match, rank match, digit read,
progress bar, panel detection) is logged to a separate trace file with
optional annotated debug images.  Images older than 3 minutes are
automatically cleaned up to limit disk usage.

Usage:
    tracer = OcrTracer()
    tracer.set_enabled(True)
    tracer.log("SKILL", f"fuzzy={name}({score:.2f})")
    tracer.save_image("skill", annotated_img, suffix="Anatomy")
"""

import logging
import logging.handlers
import os
import time
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None


TRACE_DIR = Path(os.path.expanduser("~")) / ".entropia-nexus" / "ocr_trace"
IMAGE_DIR = TRACE_DIR / "images"
LOG_FILE = TRACE_DIR / "trace.log"
MAX_IMAGE_AGE_S = 180  # 3 minutes
LOG_MAX_BYTES = 512 * 1024
LOG_BACKUP_COUNT = 1


class OcrTracer:
    """Manages OCR trace output: dedicated log file + rolling debug images."""

    def __init__(self):
        self._enabled = False
        self._logger = logging.getLogger("Nexus.OCR.Trace")
        self._logger.propagate = False
        self._file_handler: logging.handlers.RotatingFileHandler | None = None
        self._last_cleanup: float = 0.0

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool):
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if enabled:
            self._setup_file_handler()
            self.log("TRACE", "OCR trace enabled")
        else:
            self.log("TRACE", "OCR trace disabled")
            self._teardown_file_handler()

    def _setup_file_handler(self):
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        if self._file_handler is not None:
            return
        fh = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        fh.setFormatter(logging.Formatter(
            "%(asctime)s.%(msecs)03d [%(message)s",
            datefmt="%H:%M:%S",
        ))
        fh.setLevel(logging.DEBUG)
        self._logger.addHandler(fh)
        self._logger.setLevel(logging.DEBUG)
        self._file_handler = fh

    def _teardown_file_handler(self):
        if self._file_handler is not None:
            self._logger.removeHandler(self._file_handler)
            self._file_handler.close()
            self._file_handler = None

    def log(self, step: str, msg: str):
        """Write one concise trace line.  No-op when disabled."""
        if not self._enabled:
            return
        self._logger.debug("%s] %s", step, msg)

    def save_image(self, step: str, image: np.ndarray, suffix: str = ""):
        """Save a debug image with timestamp prefix.  No-op when disabled."""
        if not self._enabled or cv2 is None or image is None:
            return
        self._cleanup_old_images()
        ts = int(time.time() * 1000)
        name = f"{ts}_{step}"
        if suffix:
            # Sanitize suffix for filesystem safety
            safe = suffix.replace(" ", "_").replace("/", "_").replace("\\", "_")
            name += f"_{safe}"
        path = IMAGE_DIR / f"{name}.png"
        try:
            cv2.imwrite(str(path), image)
        except Exception:
            pass

    def _cleanup_old_images(self):
        """Delete images older than MAX_IMAGE_AGE_S.  Runs at most once/second."""
        now = time.time()
        if now - self._last_cleanup < 1.0:
            return
        self._last_cleanup = now
        try:
            cutoff = now - MAX_IMAGE_AGE_S
            for f in IMAGE_DIR.iterdir():
                if f.suffix == ".png" and f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
        except Exception:
            pass
