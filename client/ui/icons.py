"""SVG icon rendering for the sidebar and other UI elements."""

import os

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

# Resolve logo path relative to this file
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")

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

# Rifle silhouette
HUNT = (
    '<path d="M2 11 L14 7 L14 9 L20 8 L22 9 L22 11 L20 11 L20 10 L17 11 '
    'L17 13 L15 13 L15 11 L14 11 L12 14 L10 14 L10 12 L2 13z"/>'
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

# Navigation arrows (back/forward)
ARROW_LEFT = '<path d="M15.41 7.41L10.83 12l4.58 4.59L14 18l-6-6 6-6z"/>'
ARROW_RIGHT = '<path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>'

# Update available (download arrow + bar)
UPDATE = (
    '<path d="M13 7h-2v4H7l5 5 5-5h-4V7z"/>'
    '<path d="M19 19H5v-2h14v2z"/>'
)


def svg_icon(svg_elements: str, color: str, size: int = 24) -> QIcon:
    """Render inline SVG elements to a QIcon with the given fill color."""
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
    return QIcon(pixmap)


def svg_pixmap(svg_elements: str, color: str, size: int = 24) -> QPixmap:
    """Render inline SVG elements to a QPixmap with the given fill color."""
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
    return pixmap


def nexus_logo_icon(size: int = 16) -> QIcon:
    """Load the Nexus logo PNG as a QIcon."""
    pixmap = QPixmap(_LOGO_PATH)
    if pixmap.isNull():
        return QIcon()
    scaled = pixmap.scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return QIcon(scaled)


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
