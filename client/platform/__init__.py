"""Platform abstraction — exports a *backend* singleton for the current OS.

Detection order:
1. ``sys.platform == "win32"`` -> Win32
2. ``XDG_SESSION_TYPE`` env var -> ``"x11"`` or ``"wayland"``
3. ``WAYLAND_DISPLAY`` env var -> Wayland
4. ``DISPLAY`` env var -> X11
5. Otherwise -> fallback (features disabled gracefully)
"""

from __future__ import annotations

import logging
import os
import sys

from ._base import PlatformBackend  # noqa: F401 — re-export for type hints

log = logging.getLogger("platform")


def detect_display_server() -> str:
    """Return ``"win32"``, ``"x11"``, ``"wayland"``, or ``"unknown"``."""
    if sys.platform == "win32":
        return "win32"

    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "x11":
        return "x11"
    if session == "wayland":
        return "wayland"

    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"

    return "unknown"


def _load_backend():
    """Instantiate the appropriate backend for the detected display server."""
    ds = detect_display_server()
    log.info("Detected display server: %s", ds)

    if ds == "win32":
        from ._win32 import Win32Backend
        return Win32Backend()

    if ds == "x11":
        try:
            from ._x11 import X11Backend
            return X11Backend()
        except Exception as e:
            log.warning("X11 backend failed to initialise: %s — using fallback", e)

    if ds == "wayland":
        try:
            from ._wayland import WaylandBackend
            return WaylandBackend()
        except Exception as e:
            log.warning("Wayland backend failed to initialise: %s — using fallback", e)

    from ._fallback import FallbackBackend
    return FallbackBackend()


DISPLAY_SERVER: str = detect_display_server()
backend = _load_backend()
