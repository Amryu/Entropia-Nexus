"""Centralized logging for the Entropia Nexus client.

Usage:
    from ..core.logger import get_logger
    log = get_logger("Watcher")

    log.error("Something broke: %s", err)     # Always shown
    log.warning("File truncated")              # Always shown
    log.info("Started watching %s", path)      # Verbose only
    log.debug("Byte offset: %d", offset)       # Verbose only

Log file:
    ~/.entropia-nexus/client.log — rolling log with 1-hour retention.
    On startup, entries older than 1 hour are pruned.  File is capped
    at 256 KB with one backup to prevent unbounded growth.
"""

import faulthandler
import logging
import logging.handlers
import os
import sys
import time
from collections import deque
from pathlib import Path

_initialized = False
_recent_handler: "RecentLogHandler | None" = None
_log_path: str | None = None

_RECENT_LOG_SIZE = 50
_LOG_DIR = Path(os.path.expanduser("~")) / ".entropia-nexus"
_LOG_FILE = _LOG_DIR / "client.log"
_LOG_MAX_BYTES = 256 * 1024  # 256 KB
_LOG_BACKUP_COUNT = 1
_LOG_MAX_AGE_SECONDS = 3600  # 1 hour


class RecentLogHandler(logging.Handler):
    """Ring-buffer handler that stores the last N formatted log messages."""

    def __init__(self, maxlen: int = _RECENT_LOG_SIZE):
        super().__init__()
        self._buffer: deque[str] = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._buffer.append(self.format(record))
        except Exception:
            pass

    def get_recent(self) -> list[str]:
        return list(self._buffer)


def _prune_old_entries(path: Path) -> None:
    """Remove log lines older than 1 hour from the file."""
    if not path.exists():
        return
    try:
        cutoff = time.time() - _LOG_MAX_AGE_SECONDS
        kept: list[str] = []
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                # Lines start with "YYYY-MM-DD HH:MM:SS" timestamp
                try:
                    ts_str = line[:19]
                    ts = time.mktime(time.strptime(ts_str, "%Y-%m-%d %H:%M:%S"))
                    if ts >= cutoff:
                        kept.append(line)
                except (ValueError, OverflowError):
                    kept.append(line)  # keep lines without parseable timestamps
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(kept)
    except Exception:
        pass  # don't let log pruning crash the app


def init(verbose: bool = False) -> None:
    """Initialize logging. Call once from app.main()."""
    global _initialized, _recent_handler, _log_path
    if _initialized:
        return
    _initialized = True

    console_fmt = logging.Formatter("[%(name)s] %(message)s")
    file_fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s",
                                 datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler (respects verbose flag)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(console_fmt)

    # Ring-buffer handler (for crash reports)
    _recent_handler = RecentLogHandler()
    _recent_handler.setFormatter(console_fmt)

    root = logging.getLogger("Nexus")
    root.addHandler(console)
    root.addHandler(_recent_handler)
    root.setLevel(logging.DEBUG if verbose else logging.WARNING)

    # File handler — always captures WARNING+ regardless of verbose flag
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        _prune_old_entries(_LOG_FILE)
        file_handler = logging.handlers.RotatingFileHandler(
            _LOG_FILE, maxBytes=_LOG_MAX_BYTES, backupCount=_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(file_fmt)
        file_handler.setLevel(logging.WARNING)
        root.addHandler(file_handler)
        _log_path = str(_LOG_FILE)
    except Exception:
        pass  # file logging is best-effort

    # faulthandler — writes C-level crash tracebacks to the log file
    try:
        fh = open(_LOG_FILE, "a", encoding="utf-8")
        faulthandler.enable(file=fh)
    except Exception:
        faulthandler.enable()  # fallback: write to stderr


def get_log_path() -> str | None:
    """Return the path to the log file, or None if file logging is not active."""
    return _log_path


def get_recent_logs() -> list[str]:
    """Return recent log messages from the ring buffer."""
    if _recent_handler is None:
        return []
    return _recent_handler.get_recent()


def get_logger(name: str) -> logging.Logger:
    """Get a named logger under the Nexus namespace."""
    return logging.getLogger(f"Nexus.{name}")
