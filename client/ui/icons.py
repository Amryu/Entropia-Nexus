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

# Crossed swords
LOADOUT = (
    '<path d="M6.5 2 L8 3.5 L4.5 7 L6 8.5 L2.5 12 L2 11.5 L2 9 L5.5 5.5 L4 4z"/>'
    '<path d="M17.5 2 L16 3.5 L19.5 7 L18 8.5 L21.5 12 L22 11.5 L22 9 L18.5 5.5 L20 4z"/>'
    '<path d="M7 15 L12 10 L17 15 L15.5 16.5 L12 13 L8.5 16.5z"/>'
    '<rect x="10.5" y="16" width="3" height="4" rx="0.5"/>'
    '<rect x="9" y="20" width="6" height="2" rx="0.5"/>'
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

# Person silhouette (user avatar fallback)
USER = (
    '<circle cx="12" cy="8" r="4"/>'
    '<path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/>'
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


def svg_icon(svg_elements: str, color: str, size: int = 24) -> QIcon:
    """Render inline SVG elements to a QIcon with the given fill color."""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 24 24" width="{size}" height="{size}" '
        f'fill="{color}">'
        f'{svg_elements}'
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
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 24 24" width="{size}" height="{size}" '
        f'fill="{color}">'
        f'{svg_elements}'
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
