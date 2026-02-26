"""OCR detector for the active tool name from the game HUD."""

import threading
import time

from ..core.constants import EVENT_ACTIVE_TOOL_CHANGED
from ..core.logger import get_logger

log = get_logger("ToolDetector")


TOOL_DETECT_INTERVAL = 0.2  # seconds (~5 Hz)


class ActiveToolDetector:
    """Rapidly OCRs the active tool name from the action bar or HUD.

    Runs at ~5 Hz only during an active hunt session.
    Falls back to loadout-defined tool when OCR fails.

    Publishes EVENT_ACTIVE_TOOL_CHANGED when the detected tool changes.
    """

    def __init__(self, config, event_bus, capturer, recognizer):
        self._config = config
        self._event_bus = event_bus
        self._capturer = capturer
        self._recognizer = recognizer
        self._running = False
        self._thread = None
        self._last_tool = None

    def start(self):
        if self._running:
            return
        if not self._config.tool_name_region:
            log.info("No tool name region configured — skipping")
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="tool-detector")
        self._thread.start()
        log.info("Started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _poll_loop(self):
        while self._running:
            try:
                self._detect()
            except Exception as e:
                log.error("Error: %s", e)
            time.sleep(TOOL_DETECT_INTERVAL)

    def _detect(self):
        region = self._config.tool_name_region
        if not region:
            return

        x, y, w, h = region

        screenshot = self._capturer.capture_region(x, y, w, h)
        if screenshot is None:
            return

        from .preprocessor import ImagePreprocessor
        preprocessor = ImagePreprocessor()
        processed = preprocessor.preprocess_light_text_dark_bg(screenshot)

        text = self._recognizer.read_text(processed)
        if not text:
            return

        text = text.strip()
        if not text:
            return

        if text != self._last_tool:
            self._last_tool = text
            self._event_bus.publish(EVENT_ACTIVE_TOOL_CHANGED, {
                "tool_name": text,
                "source": "ocr",
            })
