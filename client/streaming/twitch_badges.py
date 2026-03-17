"""Twitch badge rendering — bundled SVG icons for broadcaster, moderator, subscriber."""

from __future__ import annotations

import os
import tempfile

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer


# --- SVG badge data (24×24 viewBox) ---

# Crown (broadcaster)
_BROADCASTER_SVG = (
    '<path d="M2 17h20v3H2z"/>'
    '<path d="M12 3l4 6 6-3-2 8H4L2 6l6 3z"/>'
)
_BROADCASTER_COLOR = "#e91916"

# Sword (moderator)
_MODERATOR_SVG = (
    '<path d="M12 2l2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5z"/>'
)
_MODERATOR_COLOR = "#00ad03"

# Star (subscriber)
_SUBSCRIBER_SVG = (
    '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77'
    'l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/>'
)
_SUBSCRIBER_COLOR = "#8205b3"

_BADGE_MAP = {
    "broadcaster": (_BROADCASTER_SVG, _BROADCASTER_COLOR),
    "moderator": (_MODERATOR_SVG, _MODERATOR_COLOR),
    "subscriber": (_SUBSCRIBER_SVG, _SUBSCRIBER_COLOR),
}

_pixmap_cache: dict[tuple[str, int], QPixmap] = {}
_file_cache: dict[tuple[str, int], str] = {}


def get_badge_pixmap(badge_type: str, size: int = 14) -> QPixmap | None:
    """Return a QPixmap for the given badge type, or None if unknown."""
    key = (badge_type, size)
    cached = _pixmap_cache.get(key)
    if cached is not None:
        return cached

    entry = _BADGE_MAP.get(badge_type)
    if entry is None:
        return None

    svg_data, color = entry
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 24 24" width="{size}" height="{size}" '
        f'fill="{color}">{svg_data}</svg>'
    )
    renderer = QSvgRenderer(svg.encode())
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    _pixmap_cache[key] = pixmap
    return pixmap


def get_badge_file(badge_type: str, size: int = 14) -> str | None:
    """Return a file path to a cached badge PNG for use in HTML <img> tags.

    Creates a temporary PNG on first call and reuses it afterwards.
    """
    key = (badge_type, size)
    cached = _file_cache.get(key)
    if cached is not None and os.path.isfile(cached):
        return cached

    pixmap = get_badge_pixmap(badge_type, size)
    if pixmap is None:
        return None

    path = os.path.join(tempfile.gettempdir(), f"nexus_badge_{badge_type}_{size}.png")
    pixmap.save(path, "PNG")
    _file_cache[key] = path
    return path
