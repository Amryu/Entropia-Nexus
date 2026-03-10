import hashlib
import os
import threading
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from ..core.config import AppConfig
from ..core.constants import EVENT_CATCHUP_COMPLETE, EVENT_CATCHUP_PROGRESS, EVENT_REPARSE_COMPLETE, EVENT_REPARSE_REQUESTED
from ..core.event_bus import EventBus
from ..core.database import Database
from ..core.logger import get_logger
from .line_parser import LineParser
from .message_classifier import MessageClassifier

log = get_logger("Watcher")

FINGERPRINT_LINES = 50
BATCH_COMMIT_INTERVAL = 5000  # Commit progress every N lines during catchup/reparse


def _file_fingerprint(path: str) -> str | None:
    """SHA-256 of the first FINGERPRINT_LINES lines of a file."""
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            lines = []
            for _ in range(FINGERPRINT_LINES):
                line = f.readline()
                if not line:
                    break
                lines.append(line)
        if not lines:
            return None
        return hashlib.sha256("".join(lines).encode()).hexdigest()
    except (IOError, OSError):
        return None


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
    re-parses the entire file on restart.  Detects log rotation via a
    SHA-256 fingerprint of the first 50 lines.
    """

    def __init__(self, config: AppConfig, event_bus: EventBus, db: Database, *,
                 authenticated: bool = False):
        self._config = config
        self._event_bus = event_bus
        self._db = db
        self._parser = LineParser()
        self._classifier = MessageClassifier(event_bus, db, authenticated=authenticated)
        self._observer = None
        self._running = False
        self._catching_up = False
        self._lock = threading.Lock()

        # File state
        self._file_path = config.chat_log_path
        self._byte_offset = 0
        self._line_number = 0
        self._line_buffer = ""
        self._file_hash: str | None = None

        # Resume from saved state
        state = db.get_parser_state(self._file_path)
        if state:
            saved_offset, saved_line, saved_hash = state
            current_hash = _file_fingerprint(self._file_path)

            if current_hash and saved_hash and current_hash != saved_hash:
                log.warning("Chat log file changed (rotated/replaced), resetting to beginning")
                self._file_hash = current_hash
            else:
                self._byte_offset = saved_offset
                self._line_number = saved_line
                self._file_hash = current_hash or saved_hash
                log.info("Resuming from byte %s, line %s", self._byte_offset, self._line_number)

    def start(self) -> None:
        """Start watching chat.log in a background thread."""
        if self._running:
            return

        self._running = True
        self._event_bus.subscribe(EVENT_REPARSE_REQUESTED, self._on_reparse_requested)

        # Set up watchdog observer first so we don't miss changes during catch-up
        watch_dir = str(Path(self._file_path).parent)
        handler = _FileChangeHandler(self._file_path, self._on_file_change)
        self._observer = Observer()
        self._observer.schedule(handler, watch_dir, recursive=False)
        self._observer.daemon = True
        self._observer.start()

        log.info("Watching %s", self._file_path)

        # Read any new content in a background thread so we don't block startup.
        # Global/trade events are suppressed during catchup to avoid flooding
        # the Qt signal queue with hundreds of events from old chat lines.
        def catch_up():
            log.info("Catching up on new lines...")
            self._catching_up = True
            self._classifier.set_catching_up(True)
            self._db.begin_batch()
            try:
                with self._lock:
                    self._read_new_lines()
            finally:
                self._db.end_batch()
                self._classifier.set_catching_up(False)
                self._catching_up = False
            if self._running:
                log.info("Catch-up complete (line %s, offset %s)", self._line_number, self._byte_offset)
                self._event_bus.publish(EVENT_CATCHUP_COMPLETE, None)
            else:
                log.info("Catch-up interrupted at line %s, will resume next startup", self._line_number)

        threading.Thread(target=catch_up, daemon=True, name="watcher-catchup").start()

    def stop(self) -> None:
        """Stop watching and flush pending state."""
        self._running = False
        self._event_bus.unsubscribe(EVENT_REPARSE_REQUESTED, self._on_reparse_requested)
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
        """Read new content from the file starting at the saved byte offset.

        Reads line-by-line so we can:
        - Break out cleanly on shutdown (check self._running)
        - Save progress periodically during catchup/reparse
        - Get accurate byte offsets from f.tell() at each line boundary
        """
        if not os.path.exists(self._file_path):
            return

        file_size = os.path.getsize(self._file_path)

        # If file shrunk (was rotated/truncated), reset to beginning
        if file_size < self._byte_offset:
            log.warning("File appears truncated, resetting to beginning")
            self._byte_offset = 0
            self._line_number = 0
            self._line_buffer = ""
            self._file_hash = _file_fingerprint(self._file_path)

        if file_size <= self._byte_offset:
            return

        # Compute fingerprint on first read of a new file
        if self._file_hash is None:
            self._file_hash = _file_fingerprint(self._file_path)

        # Total bytes to process (for progress reporting)
        start_offset = self._byte_offset
        total_bytes = file_size - start_offset

        # Partial line buffered from previous read
        prefix = self._line_buffer
        self._line_buffer = ""

        try:
            with open(self._file_path, "r", encoding="utf-8-sig", errors="replace") as f:
                f.seek(self._byte_offset)
                lines_in_batch = 0

                while True:
                    if not self._running:
                        log.info("Shutdown requested at line %d, saving progress",
                                 self._line_number)
                        break

                    raw_line = f.readline()
                    if not raw_line:
                        break  # EOF

                    if not raw_line.endswith("\n"):
                        # Partial line at end of file — buffer for next read
                        self._line_buffer = (prefix + raw_line) if prefix else raw_line
                        prefix = ""
                        self._byte_offset = f.tell()
                        break

                    raw_line = raw_line.rstrip("\r\n")
                    if prefix:
                        raw_line = prefix + raw_line
                        prefix = ""

                    self._line_number += 1
                    lines_in_batch += 1
                    parsed = self._parser.parse(raw_line, self._line_number)
                    if parsed:
                        self._classifier.classify_and_handle(parsed)

                    self._byte_offset = f.tell()

                    # Progress reporting during catchup
                    if self._catching_up and total_bytes > 20000 and lines_in_batch % 200 == 0:
                        consumed = self._byte_offset - start_offset
                        self._event_bus.publish(EVENT_CATCHUP_PROGRESS,
                                               {"parsed": consumed, "total": total_bytes})

                    # Periodic commit during catchup/reparse to persist progress
                    if self._catching_up and lines_in_batch % BATCH_COMMIT_INTERVAL == 0:
                        self._db.end_batch()
                        self._save_state()
                        self._db.begin_batch()

        except (IOError, OSError) as e:
            log.error("Error reading file: %s", e)
            # Re-buffer prefix if it wasn't consumed
            if prefix:
                self._line_buffer = prefix
            return

        # Re-buffer prefix if no lines were read (file hasn't grown)
        if prefix:
            self._line_buffer = prefix

        self._save_state()

    def _save_state(self) -> None:
        self._db.save_parser_state(
            file_path=self._file_path,
            byte_offset=self._byte_offset,
            last_line_number=self._line_number,
            file_hash=self._file_hash,
        )

    def _on_reparse_requested(self, _data):
        """Reset to beginning and re-parse the entire file.

        All EventBus events are suppressed during reparse (catchup mode) to
        avoid flooding the Qt signal queue. After reparse completes,
        EVENT_REPARSE_COMPLETE is published so the ingestion uploader can
        re-submit globals/trades from the local DB.
        """
        def reparse():
            log.info("Re-parsing chat.log from beginning...")
            log.info("Clearing non-deduped tables before reparse...")
            self._db.clear_parsed_data()

            with self._lock:
                self._byte_offset = 0
                self._line_number = 0
                self._line_buffer = ""
                self._file_hash = _file_fingerprint(self._file_path)

            self._catching_up = True
            self._classifier.set_catching_up(True)

            self._db.begin_batch()
            try:
                with self._lock:
                    self._read_new_lines()
            finally:
                self._db.end_batch()
                self._classifier.set_catching_up(False)
                self._catching_up = False

            if self._running:
                log.info("Re-parse complete (line %s, offset %s)", self._line_number, self._byte_offset)
                self._event_bus.publish(EVENT_REPARSE_COMPLETE, None)
                self._event_bus.publish(EVENT_CATCHUP_COMPLETE, None)
            else:
                log.info("Re-parse interrupted at line %s, will resume next startup", self._line_number)

        threading.Thread(target=reparse, daemon=True, name="watcher-reparse").start()

    def parse_file(self) -> None:
        """Parse the entire file from the current offset (non-watching mode).
        Useful for batch processing."""
        self._read_new_lines()
        self._classifier.flush()
        self._save_state()
