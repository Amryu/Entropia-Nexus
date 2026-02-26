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

_initialized = False


def init(verbose: bool = False) -> None:
    """Initialize logging. Call once from app.main()."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))

    root = logging.getLogger("Nexus")
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger under the Nexus namespace."""
    return logging.getLogger(f"Nexus.{name}")
