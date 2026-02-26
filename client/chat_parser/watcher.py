import os
import threading
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from ..core.config import AppConfig
from ..core.constants import EVENT_CATCHUP_COMPLETE
from ..core.event_bus import EventBus
from ..core.database import Database
from ..core.logger import get_logger
from .line_parser import LineParser
from .message_classifier import MessageClassifier

log = get_logger("Watcher")


class _FileChangeHandler(FileSystemEventHandler):
    """Watchdog handler that triggers on chat.log modifications."""

    def __init__(self, target_path: str, callback):
        super().__init__()
        self._target = os.path.normpath(target_path)
        self._callback = callback

    def on_modified(self, event):
        if not event.is_directory and os.path.normpath(event.src_path) == self._target:
            self._callback()


class ChatLogWatcher:
    """Watches chat.log for new content and parses new lines.

    Resumes from last known byte offset (stored in DB) so it never
    re-parses the entire file on restart.
    """

    def __init__(self, config: AppConfig, event_bus: EventBus, db: Database):
        self._config = config
        self._event_bus = event_bus
        self._db = db
        self._parser = LineParser()
        self._classifier = MessageClassifier(event_bus, db)
        self._observer = None
        self._running = False
        self._lock = threading.Lock()

        # File state
        self._file_path = config.chat_log_path
        self._byte_offset = 0
        self._line_number = 0
        self._line_buffer = ""

        # Resume from saved state
        state = db.get_parser_state(self._file_path)
        if state:
            self._byte_offset, self._line_number = state
            log.info("Resuming from byte %s, line %s", self._byte_offset, self._line_number)

    def start(self) -> None:
        """Start watching chat.log in a background thread."""
        if self._running:
            return

        self._running = True

        # Set up watchdog observer first so we don't miss changes during catch-up
        watch_dir = str(Path(self._file_path).parent)
        handler = _FileChangeHandler(self._file_path, self._on_file_change)
        self._observer = Observer()
        self._observer.schedule(handler, watch_dir, recursive=False)
        self._observer.daemon = True
        self._observer.start()

        log.info("Watching %s", self._file_path)

        # Read any new content in a background thread so we don't block startup
        def catch_up():
            log.info("Catching up on new lines...")
            self._db.begin_batch()
            try:
                with self._lock:
                    self._read_new_lines()
            finally:
                self._db.end_batch()
            log.info("Catch-up complete (line %s, offset %s)", self._line_number, self._byte_offset)
            self._event_bus.publish(EVENT_CATCHUP_COMPLETE, None)

        threading.Thread(target=catch_up, daemon=True, name="watcher-catchup").start()

    def stop(self) -> None:
        """Stop watching and flush pending state."""
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None
        self._classifier.flush()
        self._save_state()
        log.info("Stopped")

    def _on_file_change(self) -> None:
        """Called by watchdog when the file is modified."""
        with self._lock:
            self._read_new_lines()

    def _read_new_lines(self) -> None:
        """Read new content from the file starting at the saved byte offset."""
        if not os.path.exists(self._file_path):
            return

        file_size = os.path.getsize(self._file_path)

        # If file shrunk (was rotated/truncated), reset to beginning
        if file_size < self._byte_offset:
            log.warning("File appears truncated, resetting to beginning")
            self._byte_offset = 0
            self._line_number = 0
            self._line_buffer = ""

        if file_size <= self._byte_offset:
            return

        try:
            with open(self._file_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._byte_offset)
                new_content = f.read()
                new_offset = f.tell()
        except (IOError, OSError) as e:
            log.error("Error reading file: %s", e)
            return

        # Prepend any buffered partial line
        if self._line_buffer:
            new_content = self._line_buffer + new_content
            self._line_buffer = ""

        lines = new_content.split("\n")

        # If the last "line" is not terminated by newline, buffer it
        if not new_content.endswith("\n"):
            self._line_buffer = lines.pop()
        else:
            # Remove trailing empty string from split
            if lines and lines[-1] == "":
                lines.pop()

        for raw_line in lines:
            self._line_number += 1
            parsed = self._parser.parse(raw_line, self._line_number)
            if parsed:
                self._classifier.classify_and_handle(parsed)

        self._byte_offset = new_offset
        self._save_state()

    def _save_state(self) -> None:
        self._db.save_parser_state(
            file_path=self._file_path,
            byte_offset=self._byte_offset,
            last_line_number=self._line_number,
        )

    def parse_file(self) -> None:
        """Parse the entire file from the current offset (non-watching mode).
        Useful for batch processing."""
        self._read_new_lines()
        self._classifier.flush()
        self._save_state()
