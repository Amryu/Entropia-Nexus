"""Historical chat log importer — parses a .log file and writes to the local DB.

Creates an isolated LineParser + MessageClassifier pipeline that reads an
entire file from beginning to end with events suppressed (DB writes only).
After import, publishes EVENT_HISTORICAL_IMPORT_COMPLETE so the ingestion
uploader can rebuffer from DB and queue the data for server upload.
"""

import os
import threading
from dataclasses import dataclass

from ..core.constants import (
    EVENT_AUTH_STATE_CHANGED,
    EVENT_HISTORICAL_IMPORT_COMPLETE,
    EVENT_HISTORICAL_IMPORT_PROGRESS,
)
from ..core.database import Database
from ..core.event_bus import EventBus
from ..core.logger import get_logger
from .line_parser import LineParser
from .message_classifier import MessageClassifier

log = get_logger("Importer")

BATCH_COMMIT_INTERVAL = 5000
PROGRESS_INTERVAL = 500


@dataclass
class ImportResult:
    lines_parsed: int = 0
    globals_found: int = 0
    trades_found: int = 0
    error: str | None = None


class HistoricalImporter:
    """Parses a chat log file from beginning to end, writing to the local DB."""

    def __init__(self, event_bus: EventBus, db: Database):
        self._event_bus = event_bus
        self._db = db
        self._cancel = threading.Event()

    @property
    def is_running(self) -> bool:
        return not self._cancel.is_set()

    def cancel(self):
        self._cancel.set()

    def import_file(self, file_path: str) -> ImportResult:
        """Parse a .log file and write globals/trades to the local DB.

        This is a blocking call — run it in a background thread.
        """
        result = ImportResult()

        if not os.path.exists(file_path):
            result.error = f"File not found: {file_path}"
            log.error(result.error)
            self._publish_complete(result)
            return result

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            result.error = "File is empty"
            log.warning(result.error)
            self._publish_complete(result)
            return result

        # Snapshot DB counts before import
        globals_before = self._count_globals()
        trades_before = self._count_trades()

        # Create isolated parser pipeline
        parser = LineParser()
        classifier = MessageClassifier(self._event_bus, self._db, authenticated=True)
        classifier.set_catching_up(True)  # suppress events, enable DB writes

        log.info("Importing %s (%d bytes)", file_path, file_size)

        line_number = 0
        self._db.begin_batch()
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                while not self._cancel.is_set():
                    raw_line = f.readline()
                    if not raw_line:
                        break  # EOF

                    raw_line = raw_line.rstrip("\r\n")
                    line_number += 1
                    parsed = parser.parse(raw_line, line_number)
                    if parsed:
                        classifier.classify_and_handle(parsed)

                    if line_number % BATCH_COMMIT_INTERVAL == 0:
                        self._db.end_batch()
                        self._db.begin_batch()

                    if line_number % PROGRESS_INTERVAL == 0:
                        self._event_bus.publish(EVENT_HISTORICAL_IMPORT_PROGRESS, {
                            "parsed_bytes": f.tell(),
                            "total_bytes": file_size,
                            "lines": line_number,
                        })

            classifier.flush()

        except (IOError, OSError) as e:
            result.error = f"Error reading file: {e}"
            log.error(result.error)
        finally:
            self._db.end_batch()
            result.lines_parsed = line_number
            # Cleanup classifier's auth subscription to avoid leaks
            self._event_bus.unsubscribe(EVENT_AUTH_STATE_CHANGED, classifier._on_auth_changed)

        # Count how many globals/trades were added
        result.globals_found = self._count_globals() - globals_before
        result.trades_found = self._count_trades() - trades_before

        if self._cancel.is_set():
            log.info("Import cancelled at line %d", result.lines_parsed)
            result.error = "Import cancelled"
        elif not result.error:
            log.info(
                "Import complete: %d lines, %d globals, %d trades",
                result.lines_parsed, result.globals_found, result.trades_found,
            )

        self._publish_complete(result)
        return result

    def _publish_complete(self, result: ImportResult):
        self._event_bus.publish(EVENT_HISTORICAL_IMPORT_COMPLETE, {
            "lines_parsed": result.lines_parsed,
            "globals_found": result.globals_found,
            "trades_found": result.trades_found,
            "error": result.error,
        })

    def _count_globals(self) -> int:
        with self._db._lock:
            cur = self._db._conn.execute("SELECT COUNT(*) FROM globals")
            return cur.fetchone()[0]

    def _count_trades(self) -> int:
        with self._db._lock:
            cur = self._db._conn.execute("SELECT COUNT(*) FROM trade_messages")
            return cur.fetchone()[0]
