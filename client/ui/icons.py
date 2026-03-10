"""SVG icon rendering for the sidebar and other UI elements."""

import os
import sys

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

# Resolve logo path relative to this file
_ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")
_LOGO_PATH = os.path.join(_ASSETS, "logo.png")
_ICO_PATH = os.path.join(_ASSETS, "logo.ico")

# --- SVG path data (24x24 viewBox) ---

# 4-square grid
DASHBOARD = (
    '<rect x="3" y="3" width="8" height="8" rx="1"/>'
    '<rect x="13" y="3" width="8" height="8" rx="1"/>'
    '<rect x="3" y="13" width="8" height="8" rx="1"/>'
    '<rect x="13" y="13" width="8" height="8" rx="1"/>'
)

# Three ascending bars
SKILLS = (
    '<rect x="4" y="14" width="4" height="7" rx="0.5"/>'
    '<rect x="10" y="9" width="4" height="12" rx="0.5"/>'
    '<rect x="16" y="4" width="4" height="17" rx="0.5"/>'
)

# Kite shield with border (evenodd: outer = border, inner = hollow)
LOADOUT = (
    '<path fill-rule="evenodd" d="'
    # Outer edge
    'M12 2L4 6V12C4 16.5 7 20 12 22.5C17 20 20 16.5 20 12V6Z'
    # Inner cutout (slightly smaller, creates the border)
    'M12 4.5L6.5 7.5V12C6.5 15.5 8.8 18.5 12 20.3'
    'C15.2 18.5 17.5 15.5 17.5 12V7.5Z'
    '"/>'
)

# 3D box / inventory (matches website user menu icon)
INVENTORY = (
    # Top face
    '<path d="M12 2 L22 7 L12 12 L2 7z"/>'
    # Left face
    '<path d="M2 7 L12 12 L12 22 L2 17z" opacity="0.7"/>'
    # Right face
    '<path d="M22 7 L12 12 L12 22 L22 17z" opacity="0.5"/>'
)

# Open book (wiki / knowledge base)
WIKI = (
    '<path d="M4 4.5C4 3.12 5.12 2 6.5 2H12v15H6.5C5.12 17 4 18.12 4 19.5V4.5z"/>'
    '<path d="M12 2h5.5C18.88 2 20 3.12 20 4.5V17h-8V2z" opacity="0.7"/>'
    '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20v3.5a1.5 1.5 0 0 1-1.5 1.5H6.5'
    'A2.5 2.5 0 0 1 4 19.5z" opacity="0.5"/>'
)

# Map pin
MAPS = (
    '<path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z'
    'm0 9.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z"/>'
)

# Person silhouette (user avatar fallback)
USER = (
    '<circle cx="12" cy="8" r="4"/>'
    '<path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/>'
)

# Bell (notifications)
BELL = (
    '<path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2z"/>'
    '<path d="M18 16v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5'
    's-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.93 6 11v5l-2 2v1h16v-1l-2-2z"/>'
)

# Photo/film gallery (grid of images)
GALLERY = (
    '<rect x="3" y="3" width="7" height="7" rx="1"/>'
    '<rect x="14" y="3" width="7" height="5" rx="1"/>'
    '<rect x="3" y="14" width="7" height="7" rx="1"/>'
    '<rect x="14" y="12" width="7" height="9" rx="1"/>'
    '<path d="M5 8l2-2 2 2" fill="none" stroke="currentColor" stroke-width="0.8" opacity="0.6"/>'
    '<circle cx="16" cy="16" r="2" opacity="0.5"/>'
)

# Gear cog (fill-based, 6 teeth)
SETTINGS = (
    '<path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zm0 5a1.5 1.5 0 1 1 0-3 '
    '1.5 1.5 0 0 1 0 3z"/>'
    '<path d="M21.2 10.8h-1.5a7.5 7.5 0 0 0-.6-1.5l1.1-1.1a.8.8 0 0 0 0-1.1l-2.3-2.3'
    'a.8.8 0 0 0-1.1 0l-1.1 1.1a7.5 7.5 0 0 0-1.5-.6V3.8a.8.8 0 0 0-.8-.8h-3.2'
    'a.8.8 0 0 0-.8.8v1.5a7.5 7.5 0 0 0-1.5.6L6.8 4.8a.8.8 0 0 0-1.1 0L3.4 7.1'
    'a.8.8 0 0 0 0 1.1l1.1 1.1a7.5 7.5 0 0 0-.6 1.5H2.4a.8.8 0 0 0-.8.8v3.2'
    'a.8.8 0 0 0 .8.8h1.5a7.5 7.5 0 0 0 .6 1.5l-1.1 1.1a.8.8 0 0 0 0 1.1l2.3 2.3'
    'a.8.8 0 0 0 1.1 0l1.1-1.1a7.5 7.5 0 0 0 1.5.6v1.5a.8.8 0 0 0 .8.8h3.2'
    'a.8.8 0 0 0 .8-.8v-1.5a7.5 7.5 0 0 0 1.5-.6l1.1 1.1a.8.8 0 0 0 1.1 0l2.3-2.3'
    'a.8.8 0 0 0 0-1.1l-1.1-1.1a7.5 7.5 0 0 0 .6-1.5h1.5a.8.8 0 0 0 .8-.8v-3.2'
    'a.8.8 0 0 0-.8-.8z"/>'
)

# Clipboard (copy)
COPY = (
    '<path d="M16 1H4C2.9 1 2 1.9 2 3v14h2V3h12V1z"/>'
    '<path d="M19 5H8C6.9 5 6 5.9 6 7v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7'
    'c0-1.1-.9-2-2-2z"/>'
)

# Checkmark (confirmation feedback)
CHECK = '<path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>'

# Navigation arrows (back/forward/up/down)
ARROW_LEFT = '<path d="M15.41 7.41L10.83 12l4.58 4.59L14 18l-6-6 6-6z"/>'
ARROW_RIGHT = '<path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>'
ARROW_UP = '<path d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/>'
ARROW_DOWN = '<path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z"/>'

# Storefront / exchange (awning + counter)
EXCHANGE = (
    '<path d="M4 6h16v2H4z"/>'
    '<path d="M2 8l2-2h16l2 2v1H2z"/>'
    '<path d="M4 9v10h16V9h-2v6H6V9z" opacity="0.8"/>'
    '<path d="M8 12h3v3H8z"/>'
    '<path d="M14 9h4v2h-4z" opacity="0.6"/>'
)

# Clipboard checklist (tracker)
TRACKER = (
    '<path d="M9 2H15C15.55 2 16 2.45 16 3V4H17C18.1 4 19 4.9 19 6V20'
    'C19 21.1 18.1 22 17 22H7C5.9 22 5 21.1 5 20V6C5 4.9 5.9 4 7 4H8V3'
    'C8 2.45 8.45 2 9 2ZM10 4H14V3H10V4Z"/>'
    '<rect x="8" y="9" width="2" height="2" rx="0.3" fill="currentColor" opacity="0.9"/>'
    '<rect x="11" y="9" width="5" height="2" rx="0.3" fill="currentColor" opacity="0.5"/>'
    '<rect x="8" y="13" width="2" height="2" rx="0.3" fill="currentColor" opacity="0.9"/>'
    '<rect x="11" y="13" width="5" height="2" rx="0.3" fill="currentColor" opacity="0.5"/>'
    '<rect x="8" y="17" width="2" height="2" rx="0.3" fill="currentColor" opacity="0.9"/>'
    '<rect x="11" y="17" width="5" height="2" rx="0.3" fill="currentColor" opacity="0.5"/>'
)

# Pencil (edit)
PENCIL = (
    '<path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25z'
    'M20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0'
    'l-1.83 1.83 3.75 3.75 1.83-1.83z"/>'
)

# Update available (download arrow + bar)
UPDATE = (
    '<path d="M13 7h-2v4H7l5 5 5-5h-4V7z"/>'
    '<path d="M19 19H5v-2h14v2z"/>'
)

# Picture / landscape (image file indicator)
IMAGE = (
    '<path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2'
    'h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>'
)

# Viewfinder / crosshair (screenshot)
SCREENSHOT = (
    # Corner brackets
    '<path d="M3 8V5a2 2 0 0 1 2-2h3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
    '<path d="M16 3h3a2 2 0 0 1 2 2v3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
    '<path d="M21 16v3a2 2 0 0 1-2 2h-3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
    '<path d="M8 21H5a2 2 0 0 1-2-2v-3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
    # Center dot
    '<circle cx="12" cy="12" r="2"/>'
)
CAMERA = SCREENSHOT  # backward compat alias

# Film clip (save clip)
CLIP = (
    '<path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-2 '
    '.9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z"/>'
)

# Record circle
RECORD_CIRCLE = '<circle cx="12" cy="12" r="8"/>'

# Stop square
STOP_SQUARE = '<rect x="6" y="6" width="12" height="12" rx="1"/>'

# Play triangle
PLAY = '<path d="M8 5v14l11-7z"/>'

# Pause bars
PAUSE = '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>'

# Volume speaker
VOLUME = (
    '<path d="M3 9v6h4l5 5V4L7 9H3z"/>'
    '<path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>'
)

# Seek forward (double right triangles)
SEEK_FORWARD = (
    '<path d="M4 18l8.5-6L4 6v12z"/>'
    '<path d="M11.5 18l8.5-6-8.5-6v12z"/>'
)

# Seek backward (double left triangles)
SEEK_BACKWARD = (
    '<path d="M20 18V6l-8.5 6 8.5 6z"/>'
    '<path d="M12.5 18V6L4 12l8.5 6z"/>'
)

# Frame forward (play + bar)
FRAME_FORWARD = (
    '<path d="M6 18l8.5-6L6 6v12z"/>'
    '<rect x="16" y="6" width="2.5" height="12"/>'
)

# Frame backward (bar + play reversed)
FRAME_BACKWARD = (
    '<rect x="5.5" y="6" width="2.5" height="12"/>'
    '<path d="M18 18l-8.5-6L18 6v12z"/>'
)

# Close X
CLOSE_X = (
    '<path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59'
    ' 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>'
)

# Cloud upload arrow
UPLOAD = (
    '<path d="M19.35 10.04C18.67 6.59 15.64 4 12 4'
    ' 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14'
    'c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5'
    ' 0-2.64-2.05-4.78-4.65-4.96z'
    'M14 13v4h-4v-4H7l5-5 5 5h-3z"/>'
)

# Chain link (external link)
LINK = (
    '<path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7'
    'c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7'
    'c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2z'
    'm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1'
    's-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z"/>'
)

# Document with lines (notes)
NOTES = (
    '<path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12'
    'c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2z'
    'M13 9V3.5L18.5 9H13z"/>'
)

# Globe (global event)
GLOBE = (
    '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10'
    ' 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93'
    ' 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93z'
    'M17.9 17.39c-.26-.81-1-1.39-1.9-1.39h-1v-3'
    'c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2'
    'c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41'
    ' 0 2.08-.8 3.97-2.1 5.39z"/>'
)

# Star (HoF / ATH)
STAR = (
    '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77'
    'l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>'
)


_icon_cache: dict[tuple[str, str, int], QIcon] = {}


def svg_icon(svg_elements: str, color: str, size: int = 24) -> QIcon:
    """Render inline SVG elements to a QIcon with the given fill color."""
    key = (svg_elements, color, size)
    cached = _icon_cache.get(key)
    if cached is not None:
        return cached
    resolved = svg_elements.replace("currentColor", color)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 24 24" width="{size}" height="{size}" '
        f'fill="{color}">'
        f'{resolved}'
        f'</svg>'
    )
    renderer = QSvgRenderer(svg.encode())
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    icon = QIcon(pixmap)
    _icon_cache[key] = icon
    return icon


_pixmap_cache: dict[tuple[str, str, int], QPixmap] = {}


def svg_pixmap(svg_elements: str, color: str, size: int = 24) -> QPixmap:
    """Render inline SVG elements to a QPixmap with the given fill color."""
    key = (svg_elements, color, size)
    cached = _pixmap_cache.get(key)
    if cached is not None:
        return cached
    resolved = svg_elements.replace("currentColor", color)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 24 24" width="{size}" height="{size}" '
        f'fill="{color}">'
        f'{resolved}'
        f'</svg>'
    )
    renderer = QSvgRenderer(svg.encode())
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    _pixmap_cache[key] = pixmap
    return pixmap


def nexus_logo_icon(size: int = 16) -> QIcon:
    """Load the Nexus logo as a QIcon with multiple resolutions.

    On Windows, loads the .ico file which contains pre-rendered sizes
    for reliable taskbar, Alt+Tab, and Task Manager display.
    On other platforms, builds a multi-size QIcon from the PNG.
    """
    # Windows: prefer .ico (Qt reads all embedded sizes automatically)
    if sys.platform == "win32" and os.path.isfile(_ICO_PATH):
        icon = QIcon(_ICO_PATH)
        if not icon.isNull():
            return icon

    # Fallback: build multi-size QIcon from PNG
    pixmap = QPixmap(_LOGO_PATH)
    if pixmap.isNull():
        return QIcon()
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(
            pixmap.scaled(s, s,
                          Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation),
        )
    return icon


def nexus_logo_pixmap(size: int = 16) -> QPixmap:
    """Load the Nexus logo PNG as a QPixmap."""
    pixmap = QPixmap(_LOGO_PATH)
    if pixmap.isNull():
        return pixmap
    return pixmap.scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
