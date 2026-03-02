"""Centralized logging for the Entropia Nexus client.

Usage:
    from ..core.logger import get_logger
    log = get_logger("Watcher")

    log.error("Something broke: %s", err)     # Always shown
    log.warning("File truncated")              # Always shown
    log.info("Started watching %s", path)      # Verbose only
    log.debug("Byte offset: %d", offset)       # Verbose only
"""

import logging
import sys
from collections import deque

_initialized = False
_recent_handler: "RecentLogHandler | None" = None

_RECENT_LOG_SIZE = 50


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


def init(verbose: bool = False) -> None:
    """Initialize logging. Call once from app.main()."""
    global _initialized, _recent_handler
    if _initialized:
        return
    _initialized = True

    fmt = logging.Formatter("[%(name)s] %(message)s")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)

    _recent_handler = RecentLogHandler()
    _recent_handler.setFormatter(fmt)

    root = logging.getLogger("Nexus")
    root.addHandler(handler)
    root.addHandler(_recent_handler)
    root.setLevel(logging.DEBUG if verbose else logging.WARNING)


def get_recent_logs() -> list[str]:
    """Return recent log messages from the ring buffer."""
    if _recent_handler is None:
        return []
    return _recent_handler.get_recent()


def get_logger(name: str) -> logging.Logger:
    """Get a named logger under the Nexus namespace."""
    return logging.getLogger(f"Nexus.{name}")
