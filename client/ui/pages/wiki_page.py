"""Wiki page — browse the Entropia Nexus knowledge base."""

from __future__ import annotations

import threading
from urllib.parse import quote as _url_quote

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QFrame, QApplication,
    QStyle, QStyleOption,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QPainter

from ..theme import (
    PRIMARY, SECONDARY, HOVER, BORDER, ACCENT, TEXT, TEXT_MUTED,
    MAIN_DARK, PAGE_HEADER_OBJECT_NAME,
)
from ..icons import svg_icon
from ...data.wiki_columns import LEAF_DATA_MAP, LEAF_TOGGLE_MAP, COLUMN_DEFS, DEFAULT_COLUMNS, get_item_name

# ---------------------------------------------------------------------------
# Category data — mirrors the website overview pages
# ---------------------------------------------------------------------------

# (abbreviation, title, description, subtypes_or_None)
# If subtypes is None the category is a leaf (shows "Coming soon").
# If subtypes is a list of (abbrev, title, desc) tuples, clicking opens a sub-grid.

ITEMS_CATEGORIES: list[tuple[str, str, str, list | None]] = [
    ("WPN", "Weapons", "Combat weapons including melee, ranged, BLP and laser weapons", None),
    ("ARM", "Armor Sets", "Protective armor sets with piece stats and set bonuses", None),
    ("CLO", "Clothing", "Wearable items including cosmetics and buff equipment", None),
    ("ATT", "Attachments", "Weapon enhancements: amplifiers, scopes, sights, and absorbers", [
        ("AMP", "Weapon Amplifiers", "Damage amplifiers for weapons"),
        ("SCO", "Sights/Scopes", "Vision attachments for weapons"),
        ("ABS", "Absorbers", "Deterioration absorbers"),
        ("FAM", "Finder Amplifiers", "Amplifiers for finders"),
        ("PLT", "Armor Platings", "Protective armor platings"),
        ("ENH", "Enhancers", "Slot enhancers for items"),
        ("MFI", "Mindforce Implants", "Mindforce chip implants"),
    ]),
    ("MED", "Medical Tools", "Healing equipment including FAPs and healing chips", [
        ("MDT", "Medical Tools", "FAP and healing tools"),
        ("MDC", "Medical Chips", "Mindforce medical chips"),
    ]),
    ("TLS", "Tools", "Mining and crafting equipment: finders, excavators, refiners", [
        ("REF", "Refiners", "Material refining tools"),
        ("SCN", "Scanners", "Creature and resource scanners"),
        ("FND", "Finders", "Resource and treasure finders"),
        ("EXC", "Excavators", "Mining and extraction tools"),
        ("TPC", "Teleportation Chips", "Teleportation mindforce chips"),
        ("EFC", "Effect Chips", "Mindforce effect chips"),
        ("MSC", "Misc. Tools", "Other miscellaneous tools"),
    ]),
    ("MAT", "Materials", "Crafting resources: ores, enmatter, animal materials", None),
    ("BP", "Blueprints", "Crafting recipes with material requirements and QR info", None),
    ("CON", "Consumables", "Single-use items: pills, nutrio bars, stimulants", [
        ("STM", "Stimulants", "Buff and enhancement stimulants"),
        ("CCC", "Creature Control Capsules", "Pet capture capsules"),
    ]),
    ("VHC", "Vehicles", "Transportation: ground, air, and water vehicles", None),
    ("PET", "Pets", "Companion creatures with skills and buff effects", None),
    ("FRN", "Furnishings", "Estate decorations: furniture, decorations, and signs", [
        ("FUR", "Furniture", "Functional furniture pieces"),
        ("DEC", "Decorations", "Decorative items"),
        ("STC", "Storage Containers", "Item storage solutions"),
        ("SGN", "Signs", "Displayable signs"),
    ]),
    ("STR", "Strongboxes", "Strongboxes acquirable from the EU shop and events", None),
]

INFO_CATEGORIES: list[tuple[str, str, str, list | None]] = [
    ("GDE", "Guides", "Step-by-step guides and tutorials for Entropia Universe", None),
    ("MOB", "Mobs", "Creature database with maturities, spawns, loots, and codex calculator", None),
    ("MSN", "Missions", "Mission and mission chain reference data with steps and rewards", None),
    ("PRO", "Professions", "Character profession skill trees and level requirements", None),
    ("SKL", "Skills", "Individual character skills with profession contributions", None),
    ("VND", "Vendors", "NPC trade terminal vendors with locations and offers", None),
    ("LOC", "Locations", "Teleporters, areas, estates, outposts, and other locations", None),
    ("ENUM", "Enumerations", "Built-in and custom name/value datasets as reference tables", None),
]

GRID_COLUMNS = 3

# Map category title → section name for breadcrumbs
_SECTION_FOR_CATEGORY: dict[str, str] = {}
for _cat in ITEMS_CATEGORIES:
    _SECTION_FOR_CATEGORY[_cat[1]] = "Items"
for _cat in INFO_CATEGORIES:
    _SECTION_FOR_CATEGORY[_cat[1]] = "Information"


# ---------------------------------------------------------------------------
# Short URL generation — mirrors frontend Menu.svelte + short-url-routes.js
# ---------------------------------------------------------------------------

_SHORT_LINK_ORIGIN = "eunex.us"

# Category title → canonical URL prefix (mirrors frontend getEntityUrl)
_CATEGORY_URL_PREFIX: dict[str, str] = {
    # Items — top-level
    "Weapons": "/items/weapons",
    "Armor Sets": "/items/armorsets",
    "Clothing": "/items/clothing",
    "Materials": "/items/materials",
    "Blueprints": "/items/blueprints",
    "Vehicles": "/items/vehicles",
    "Pets": "/items/pets",
    "Strongboxes": "/items/strongboxes",
    # Attachments
    "Weapon Amplifiers": "/items/attachments/weaponamplifiers",
    "Sights/Scopes": "/items/attachments/weaponvisionattachments",
    "Absorbers": "/items/attachments/absorbers",
    "Finder Amplifiers": "/items/attachments/finderamplifiers",
    "Armor Platings": "/items/attachments/armorplatings",
    "Enhancers": "/items/attachments/enhancers",
    "Mindforce Implants": "/items/attachments/mindforceimplants",
    # Medical
    "Medical Tools": "/items/medicaltools/tools",
    "Medical Chips": "/items/medicaltools/chips",
    # Tools
    "Refiners": "/items/tools/refiners",
    "Scanners": "/items/tools/scanners",
    "Finders": "/items/tools/finders",
    "Excavators": "/items/tools/excavators",
    "Teleportation Chips": "/items/tools/teleportationchips",
    "Effect Chips": "/items/tools/effectchips",
    "Misc. Tools": "/items/tools/misctools",
    # Consumables
    "Stimulants": "/items/consumables/stimulants",
    "Creature Control Capsules": "/items/consumables/capsules",
    # Furnishings
    "Furniture": "/items/furnishings/furniture",
    "Decorations": "/items/furnishings/decorations",
    "Storage Containers": "/items/furnishings/storagecontainers",
    "Signs": "/items/furnishings/signs",
    # Information
    "Guides": "/information/guides",
    "Mobs": "/information/mobs",
    "Missions": "/information/missions",
    "Professions": "/information/professions",
    "Skills": "/information/skills",
    "Vendors": "/information/vendors",
    "Locations": "/information/locations",
    "Enumerations": "/information/enumerations",
}

# Canonical prefix → preferred short code (from short-url-routes.js)
# Sorted longest-first so prefix matching picks the most specific code.
_SHORT_ROUTE_BY_PREFIX: list[tuple[str, str]] = sorted(
    [
        ("/items/weapons", "iw"),
        ("/items/armorsets", "ia"),
        ("/items/armors", "ir"),
        ("/items/attachments", "ij"),
        ("/items/blueprints", "ib"),
        ("/items/consumables", "ic"),
        ("/items/furnishings", "if"),
        ("/items/clothing", "il"),
        ("/items/materials", "im"),
        ("/items/medicaltools", "it"),
        ("/items/tools", "io"),
        ("/items/pets", "ip"),
        ("/items/vehicles", "iv"),
        ("/items/strongboxes", "ix"),
        ("/items", "i"),
        ("/information/guides", "ng"),
        ("/information/mobs", "nm"),
        ("/information/missions", "ni"),
        ("/information/professions", "np"),
        ("/information/skills", "ns"),
        ("/information/vendors", "nv"),
        ("/information/locations", "nl"),
        ("/information/enumerations", "ne"),
        ("/information", "n"),
    ],
    key=lambda t: -len(t[0]),
)


def _encode_uri_safe(s: str) -> str:
    """Port of frontend encodeURIComponentSafe — URL-encode with ~ for spaces."""
    if not s:
        return s
    # Pre-escape literal ~ as %7E, URL-encode, then use ~ for spaces.
    # safe="!*'()" matches JS encodeURIComponent which keeps those chars.
    encoded = _url_quote(s.replace("~", "%7E"), safe="!*'()")
    return encoded.replace("%20", "~")


def _get_short_url(path: list[str]) -> str | None:
    """Build a eunex.us short URL for the current wiki path, or None."""
    if not path:
        return None
    # path[0] is the leaf category title (e.g. "Weapons", "Finders")
    canonical = _CATEGORY_URL_PREFIX.get(path[0])
    if not canonical:
        return None
    # Entity detail — append encoded name
    if len(path) >= 2:
        canonical += "/" + _encode_uri_safe(path[-1])
    # Find longest matching short-route prefix
    for prefix, code in _SHORT_ROUTE_BY_PREFIX:
        if canonical.startswith(prefix):
            remainder = canonical[len(prefix):]
            return f"{_SHORT_LINK_ORIGIN}/{code}{remainder}"
    return None


def _find_category(title: str):
    """Find a category tuple by title across both sections."""
    for cat in ITEMS_CATEGORIES:
        if cat[1] == title:
            return cat
    for cat in INFO_CATEGORIES:
        if cat[1] == title:
            return cat
    return None


# ---------------------------------------------------------------------------
# Card widget
# ---------------------------------------------------------------------------

_CARD_STYLE = f"""
    QPushButton {{
        background-color: {SECONDARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 0px;
        text-align: left;
    }}
    QPushButton:hover {{
        border-color: {ACCENT};
        background-color: {HOVER};
    }}
"""


class _WikiCard(QPushButton):
    """Big button panel with abbreviation icon, title, description, and arrow."""

    def __init__(self, abbrev: str, title: str, description: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(_CARD_STYLE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(80)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Icon placeholder — abbreviation in a rounded square
        icon_frame = QFrame()
        icon_frame.setFixedSize(48, 48)
        icon_frame.setStyleSheet(
            f"background-color: {PRIMARY}; border-radius: 6px; border: none;"
        )
        icon_label = QLabel(abbrev, icon_frame)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(48, 48)
        icon_label.setStyleSheet(
            f"color: {TEXT}; font-size: 11px; font-weight: bold;"
            f" background: transparent; border: none; letter-spacing: 0.5px;"
        )
        layout.addWidget(icon_frame)

        # Title + description
        text_col = QWidget()
        text_col.setStyleSheet("background: transparent; border: none;")
        text_layout = QVBoxLayout(text_col)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {TEXT}; font-size: 14px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        text_layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px;"
            " background: transparent; border: none;"
        )
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)

        layout.addWidget(text_col, 1)

        # Arrow
        arrow = QLabel("\u2192")
        arrow.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 16px;"
            " background: transparent; border: none;"
        )
        arrow.setFixedWidth(20)
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(arrow)


# ---------------------------------------------------------------------------
# Section title
# ---------------------------------------------------------------------------

def _section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {TEXT}; font-size: 16px; font-weight: bold;"
        f" padding: 12px 0 4px 0; background: transparent;"
    )
    return label


# ---------------------------------------------------------------------------
# Table-of-contents sidebar for detail views
# ---------------------------------------------------------------------------

TOC_WIDTH = 150

# --- SVG icon data for TOC entries (mirrors detail_overlay.py tab icons) ---

_ICON_INFO = (
    '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z'
    'm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>'
)
_ICON_ACQUIRE = (
    '<path d="M18 6h-2c0-2.21-1.79-4-4-4S8 3.79 8 6H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2'
    'h12c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-6-2c1.1 0 2 .9 2 2h-4c0-1.1.9-2 2-2z"/>'
)
_ICON_USAGE = (
    '<path d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9'
    ' 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1'
    ' .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z"/>'
)
_ICON_MATURITY = (
    '<path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7'
    'v2zM7 7v2h14V7H7z"/>'
)
_ICON_LOOT = (
    '<path d="M20 6h-2.18c.11-.31.18-.65.18-1a2.996 2.996 0 0 0-5.5-1.65l-.5.67-.5-.68'
    'C10.96 2.54 10.05 2 9 2 7.34 2 6 3.34 6 5c0 .35.07.69.18 1H4c-1.11 0-1.99.89-1.99'
    ' 2L2 19c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2z"/>'
)
_ICON_LOCATION = (
    '<path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z'
    'm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>'
)
_ICON_GLOBE = (
    '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z'
    'm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2'
    ' 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55'
    ' 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97'
    '-2.1 5.39z"/>'
)
_ICON_STEPS = (
    '<path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7'
    'v2zM7 7v2h14V7H7z"/>'
)
_ICON_REWARDS = (
    '<path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24'
    'l5.46 4.73L5.82 21z"/>'
)
_ICON_OFFERS = (
    '<path d="M20 4H4v2h16V4zm1 10v-2l-1-5H4l-1 5v2h1v6h10v-6h4v6h2v-6h1zm-9 4H6v-4h6v4z"/>'
)
_ICON_UNLOCK = (
    '<path d="M12 17a2 2 0 002-2 2 2 0 00-2-2 2 2 0 00-2 2 2 2 0 002 2m6-9a2 2 0 012'
    ' 2v10a2 2 0 01-2 2H6a2 2 0 01-2-2V10a2 2 0 012-2h9V6a3 3 0 00-3-3 3 3 0 00-3 3H7'
    'a5 5 0 015-5 5 5 0 015 5v2h1z"/>'
)
_ICON_EFFECTS = (
    '<path d="M12 2 L14 9 L21 9 L15.5 13.5 L17.5 21 L12 16.5 L6.5 21 L8.5 13.5 L3 9 L10 9 Z"/>'
)
_ICON_MARKET = (
    '<path d="M5 9.2h3V19H5V9.2zM10.6 5h2.8v14h-2.8V5zM16.2 13H19v6h-2.8v-6z"/>'
)
_ICON_TIERS = (
    '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z'
    'm0 18.5c-4.69 0-8.5-3.81-8.5-8.5S7.31 3.5 12 3.5s8.5 3.81 8.5 8.5-3.81 8.5-8.5 8.5z"/>'
    '<circle cx="12" cy="12" r="4"/>'
    '<path d="M14.83 4.1 A10 10 0 0 1 19.9 9.17 L15.17 10.83 A4 4 0 0 0 13.17 8.83 Z"/>'
    '<path d="M9.17 19.9 A10 10 0 0 1 4.1 14.83 L8.83 13.17 A4 4 0 0 0 10.83 15.17 Z"/>'
    '<path d="M19.9 14.83 A10 10 0 0 1 14.83 19.9 L13.17 15.17 A4 4 0 0 0 15.17 13.17 Z"/>'
    '<path d="M4.1 9.17 A10 10 0 0 1 9.17 4.1 L10.83 8.83 A4 4 0 0 0 8.83 10.83 Z"/>'
)
_ICON_BLUEPRINT = (
    '<rect x="3" y="3" width="18" height="18" rx="2" fill="none"'
    ' stroke="currentColor" stroke-width="1.5"/>'
    '<path d="M7 8h4v4H7z" fill="currentColor"/>'
    '<path d="M11 10h5M14 10v4M14 14h3M8 12v5M8 17h4" fill="none"'
    ' stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>'
)

# Map section titles → overlay-consistent SVG icon data
_SECTION_ICON_MAP: dict[str, str] = {
    "Details": _ICON_INFO,
    "Market Prices": _ICON_MARKET,
    "Locations": _ICON_LOCATION,
    "Maturities": _ICON_MATURITY,
    "Loots": _ICON_LOOT,
    "Globals": _ICON_GLOBE,
    "Acquisition": _ICON_ACQUIRE,
    "Drops": _ICON_LOOT,
    "Usage": _ICON_USAGE,
    "Tiers": _ICON_TIERS,
    "Construction": _ICON_BLUEPRINT,
    "Offers": _ICON_OFFERS,
    "Steps": _ICON_STEPS,
    "Rewards": _ICON_REWARDS,
    "Dependencies": _ICON_STEPS,
    "Unlocked By": _ICON_UNLOCK,
    "Skill Unlocks": _ICON_UNLOCK,
    "Skill Components": _ICON_MATURITY,
    "Affected Professions": _ICON_MATURITY,
    "Pet Skills": _ICON_EFFECTS,
    "Set Pieces": _ICON_TIERS,
    "Facilities": _ICON_LOCATION,
    "Waves": _ICON_MATURITY,
    "Spawns": _ICON_LOCATION,
}


class _TocEntry(QPushButton):
    """Single entry in the table-of-contents sidebar."""

    def __init__(self, title: str, section, parent=None):
        super().__init__(parent)
        self.section = section
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(title)
        self.setFixedHeight(28)

        svg_data = _SECTION_ICON_MAP.get(title, _ICON_INFO)
        self.setIcon(svg_icon(svg_data, TEXT_MUTED, 14))
        self.setIconSize(QSize(14, 14))
        self.setText(title)
        self.setStyleSheet(
            f"QPushButton {{"
            f"  background: transparent;"
            f"  border: none;"
            f"  color: {TEXT_MUTED};"
            f"  font-size: 12px;"
            f"  text-align: left;"
            f"  padding: 2px 8px 2px 10px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {HOVER};"
            f"  color: {TEXT};"
            f"}}"
        )


class _TocPanel(QWidget):
    """Table-of-contents sidebar showing article sections for detail views."""

    entry_clicked = pyqtSignal(object)  # DataSection

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(TOC_WIDTH)
        self.setObjectName("wikiTocPanel")
        self.setStyleSheet(
            f"#wikiTocPanel {{"
            f"  background-color: {MAIN_DARK};"
            f"  border-right: 1px solid {BORDER};"
            f"}}"
        )
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 12, 0, 12)
        self._layout.setSpacing(0)

        header = QLabel("Contents")
        header.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; font-weight: bold;"
            f" letter-spacing: 0.5px; padding: 0 10px 6px 10px;"
            f" background: transparent;"
        )
        self._layout.addWidget(header)

        self._entries_layout = QVBoxLayout()
        self._entries_layout.setContentsMargins(0, 0, 0, 0)
        self._entries_layout.setSpacing(0)
        self._layout.addLayout(self._entries_layout)

        self._layout.addStretch(1)

    def set_sections(self, sections):
        """Build TOC entries from a list of DataSection widgets.

        A "Details" entry is prepended that scrolls to the top of the article.
        """
        self.clear()
        # "Details" entry — scrolls to top (section=None signals scroll-to-top)
        details_entry = _TocEntry("Details", None, self)
        details_entry.clicked.connect(lambda _: self.entry_clicked.emit(None))
        self._entries_layout.addWidget(details_entry)

        for section in sections:
            title = getattr(section, "_title_text", "")
            if not title:
                continue
            entry = _TocEntry(title, section, self)
            entry.clicked.connect(lambda _, s=section: self.entry_clicked.emit(s))
            self._entries_layout.addWidget(entry)

    def clear(self):
        """Remove all TOC entries."""
        while self._entries_layout.count():
            item = self._entries_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def paintEvent(self, event):
        """Required for QSS background on plain QWidget subclasses."""
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        p.end()


# ---------------------------------------------------------------------------
# Search results view (shown when user presses Enter in title-bar search)
# ---------------------------------------------------------------------------

class _ClickableSearchRow(QWidget):
    """A clickable result row for the full search results page."""

    _STYLE = f"background-color: {SECONDARY}; border-radius: 4px;"
    _HOVER_STYLE = f"background-color: {HOVER}; border-radius: 4px;"

    def __init__(self, item: dict, view: "_SearchResultsView"):
        super().__init__()
        self._item = item
        self._view = view
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(self._STYLE)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._view.result_selected.emit(self._item)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.setStyleSheet(self._HOVER_STYLE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self._STYLE)
        super().leaveEvent(event)


class _SearchResultsView(QWidget):
    """Full search results page displayed inside the wiki."""

    result_selected = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(8)

    def show_results(self, query: str, results: list[dict]):
        """Rebuild the results display."""
        # Clear previous
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        header = QLabel(f'Search results for "{query}"')
        header.setStyleSheet(
            f"color: {TEXT}; font-size: 16px; font-weight: bold;"
            " background: transparent;"
        )
        self._layout.addWidget(header)

        if not results:
            empty = QLabel("No results found.")
            empty.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; background: transparent;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(empty, 1)
            return

        # Group by type
        from ..widgets.search_popup import get_type_name
        groups: dict[str, list[dict]] = {}
        for r in results:
            cat = get_type_name(r.get("Type", ""))
            groups.setdefault(cat, []).append(r)

        for cat_name, items in groups.items():
            # Category header
            cat_label = QLabel(cat_name.upper())
            cat_label.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px; font-weight: bold;"
                f" letter-spacing: 0.5px; padding: 8px 0 4px 0;"
                f" background: transparent;"
            )
            self._layout.addWidget(cat_label)

            for item in items:
                row = _ClickableSearchRow(item, self)
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(12, 6, 12, 6)

                name = QLabel(item.get("DisplayName") or item.get("Name", ""))
                name.setStyleSheet(f"color: {TEXT}; font-size: 13px; background: transparent;")
                name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                row_layout.addWidget(name, 1)

                type_badge = QLabel(get_type_name(item.get("Type", "")))
                type_badge.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 11px;"
                    f" background-color: {PRIMARY}; border-radius: 3px;"
                    f" padding: 2px 6px;"
                )
                type_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                row_layout.addWidget(type_badge)

                self._layout.addWidget(row)

        self._layout.addStretch(1)


# ---------------------------------------------------------------------------
# Wiki page
# ---------------------------------------------------------------------------

class WikiPage(QWidget):
    """Browsable wiki page mirroring the website's category structure."""

    navigation_changed = pyqtSignal(list)
    _data_loaded = pyqtSignal(str, list, list, list)  # title, items, cache, numeric
    _alt_data_loaded = pyqtSignal(str, list, list, list)  # title, items, cache, numeric
    _detail_items_ready = pyqtSignal(str, str, list)  # category, entity_name, items

    def __init__(self, *, signals, data_client, config=None, config_path=None, nexus_client=None):
        super().__init__()
        self._signals = signals
        self._data_client = data_client
        self._config = config
        self._config_path = config_path
        self._nexus_client = nexus_client
        self._path: list[str] = []
        self._current_table_view = None  # active WikiTableView (if any)
        self._leaf_items: dict[str, list[dict]] = {}  # title → fetched items
        self._precomputed_data: dict[str, tuple[list, list, list]] = {}  # title → (items, cache, numeric)
        self._precomputed_subsets: dict[str, tuple] = {}  # title → (col_defs, cache, numeric)
        self._cached_leaf_views: dict[str, QWidget] = {}    # title → container
        self._cached_table_refs = {}                         # title → WikiTableView
        self._toggle_states: dict[str, str] = {}             # title → "a" or "b"
        self._alt_table_refs: dict[str, object] = {}         # title → alt WikiTableView
        self._alt_items: dict[str, list[dict]] = {}          # title → alt items

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Breadcrumb toolbar (hidden on overview)
        self._toolbar = QWidget()
        self._toolbar.setFixedHeight(32)
        self._toolbar.setStyleSheet(
            f"background-color: {MAIN_DARK};"
            f" border-bottom: 1px solid {BORDER};"
        )
        tb_layout = QHBoxLayout(self._toolbar)
        tb_layout.setContentsMargins(16, 0, 16, 0)
        tb_layout.setSpacing(0)
        self._breadcrumb_container = tb_layout
        self._toolbar.hide()
        root.addWidget(self._toolbar)

        # Content row: TOC sidebar + scrollable content area
        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)

        self._toc_panel = _TocPanel()
        self._toc_panel.entry_clicked.connect(self._on_toc_entry_clicked)
        self._toc_panel.hide()
        content_row.addWidget(self._toc_panel)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content_row.addWidget(self._scroll)

        root.addLayout(content_row)

        # Content widget (rebuilt on navigation)
        self._content: QWidget | None = None

        # Search results sub-view
        self._search_view = _SearchResultsView()
        self._search_view.result_selected.connect(self._on_search_result_clicked)

        # Wire signals (from background threads → main thread)
        self._data_loaded.connect(self._on_data_loaded)
        self._alt_data_loaded.connect(self._on_alt_data_loaded)
        self._detail_items_ready.connect(self._on_detail_items_ready)

        # Build initial overview
        self._navigate_internal([])

        # Sync column preferences from server (account wins on conflict)
        self._sync_column_prefs_from_server()

        # Warm up all tables in the background
        self._warmup_stop = threading.Event()
        threading.Thread(
            target=self._warmup_all, daemon=True, name="wiki-warmup"
        ).start()

    # --- Public API ---

    def cleanup(self):
        """Stop background warmup thread."""
        self._warmup_stop.set()

    def navigate_to(self, path: list[str]):
        """Navigate to a path and emit navigation_changed."""
        if path == self._path:
            return
        self._navigate_internal(path)
        self.navigation_changed.emit(list(self._path))

    def get_sub_state(self) -> list[str]:
        return list(self._path)

    def set_sub_state(self, path):
        """Restore a previously saved navigation path (no signal emitted)."""
        if path is not None:
            self._navigate_internal(path)

    def get_scroll_position(self) -> int:
        return self._scroll.verticalScrollBar().value()

    def set_scroll_position(self, pos: int):
        self._scroll.verticalScrollBar().setValue(pos)

    def show_search_results(self, query: str, results: list[dict]):
        """Display full search results from the title bar."""
        self._path = ["Search"]
        self._update_breadcrumbs()
        self._search_view.show_results(query, results)
        self._swap_content(self._search_view)
        self.navigation_changed.emit(list(self._path))

    def _on_search_result_clicked(self, item: dict):
        """Handle click on a search result row (full results page)."""
        import webbrowser
        from urllib.parse import quote as url_quote
        from ..widgets.search_popup import WIKI_PATHS

        item_type = item.get("Type", "")
        item_name = item.get("Name", "")
        if not item_name:
            return

        # User/Society → open in system browser
        if item_type in ("User", "Society"):
            prefix = "/users/" if item_type == "User" else "/societies/"
            url = self._config.nexus_base_url + prefix + url_quote(item_name)
            webbrowser.open(url)
            return

        # Wiki-navigable types → navigate in-app
        path = WIKI_PATHS.get(item_type)
        if path:
            self.navigate_to(list(path) + [item_name])

    # --- Internal navigation ---

    def _navigate_internal(self, path: list[str]):
        self._path = list(path)
        self._update_breadcrumbs()
        self._toc_panel.hide()

        if not path:
            self._show_overview()
        elif len(path) == 1:
            # Top-level category (e.g. ["Attachments"])
            cat = _find_category(path[0])
            if cat and cat[3]:
                self._show_sub_grid(path[0], cat[3])
            else:
                self._show_leaf(path[0])
        elif len(path) == 2:
            cat = _find_category(path[0])
            if cat and cat[3]:
                # Has sub-categories — check if path[1] is a sub-category title
                if any(sub[1] == path[1] for sub in cat[3]):
                    self._show_leaf(path[1])
                else:
                    # Entity detail within a sub-category-parent context
                    self._show_entity_detail(path[0], path[1])
            else:
                # Entity detail for top-level leaf (e.g. ["Weapons", "Vivo T20 (L)"])
                self._show_entity_detail(path[0], path[1])
        elif len(path) == 3:
            # Sub-category entity detail (e.g. ["Attachments", "Weapon Amplifiers", "SomeAmp"])
            self._show_entity_detail(path[-2], path[-1])
        else:
            self._show_leaf(path[-1])

    def _swap_content(self, new_widget: QWidget):
        """Swap scroll area content — takeWidget() prevents deletion of cached views."""
        self._scroll.takeWidget()
        self._scroll.setWidget(new_widget)
        self._content = new_widget

    def _show_overview(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        # Items Database section
        layout.addWidget(_section_title("Items Database"))
        items_grid = self._build_card_grid(
            [(a, t, d) for a, t, d, _ in ITEMS_CATEGORIES],
            lambda title: self.navigate_to([title]),
        )
        layout.addWidget(items_grid)

        layout.addSpacing(12)

        # Information section
        layout.addWidget(_section_title("Information"))
        info_grid = self._build_card_grid(
            [(a, t, d) for a, t, d, _ in INFO_CATEGORIES],
            lambda title: self.navigate_to([title]),
        )
        layout.addWidget(info_grid)

        layout.addStretch(1)
        self._swap_content(container)

    def _show_sub_grid(self, parent_title: str, subtypes: list[tuple[str, str, str]]):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        grid = self._build_card_grid(
            subtypes,
            lambda title, pt=parent_title: self.navigate_to([pt, title]),
        )
        layout.addWidget(grid)
        layout.addStretch(1)
        self._swap_content(container)

    def _show_leaf(self, title: str):
        # 1. Cached table widget — show with preserved state
        if title in self._cached_leaf_views:
            # Restore correct _current_table_view based on toggle state
            if self._toggle_states.get(title) == "b" and title in self._alt_table_refs:
                self._current_table_view = self._alt_table_refs[title]
            else:
                self._current_table_view = self._cached_table_refs.get(title)
            self._swap_content(self._cached_leaf_views[title])
            return

        mapping = LEAF_DATA_MAP.get(title)
        if not mapping:
            self._show_placeholder(title)
            return

        method_name, page_type_id = mapping

        # 2. Precomputed data ready — create table instantly
        precomputed = self._precomputed_data.get(title)
        if precomputed:
            items, cache, numeric = precomputed
            self._create_and_show_table(title, page_type_id, items, cache, numeric)
            return

        # 3. Not ready yet — show loading, build cache in background
        self._show_loading_placeholder(title)

        leaf_title = title
        ptid = page_type_id
        prefetched = self._leaf_items.get(title)
        column_prefs = (self._config.wiki_column_prefs or {}) if self._config else {}

        def fetch():
            from ..widgets.wiki_table import build_column_cache, build_subset_cache

            items = prefetched if prefetched else getattr(self._data_client, method_name)()
            all_defs = COLUMN_DEFS.get(ptid, {})
            col_defs_list = list(all_defs.values())
            cache, numeric = build_column_cache(items, col_defs_list)

            # Pre-compute the active-column subset so the main thread
            # only needs to build widgets, not process data.
            prefs = column_prefs.get(ptid)
            if prefs:
                active_keys = list(prefs)
            else:
                active_keys = list(DEFAULT_COLUMNS.get(ptid, []))
            all_type_keys = list(all_defs.keys())
            subset = build_subset_cache(
                cache, numeric, all_type_keys, active_keys, all_defs,
            )
            self._precomputed_subsets[leaf_title] = subset

            self._data_loaded.emit(leaf_title, items, cache, numeric)

        threading.Thread(target=fetch, daemon=True, name=f"wiki-{ptid}").start()

    def _create_and_show_table(self, title: str, page_type_id: str,
                               items: list, cache: list, numeric: list):
        """Create a WikiTableView, populate it, cache it, and show it."""
        from ..widgets.wiki_table import WikiTableView

        column_prefs = {}
        if self._config:
            column_prefs = self._config.wiki_column_prefs or {}

        table_view = WikiTableView(
            page_type_id=page_type_id,
            column_prefs=column_prefs,
            on_columns_changed=self._on_columns_changed,
        )
        table_view.row_activated.connect(
            lambda item, t=title: self._on_row_activated(t, item)
        )
        table_view.new_clicked.connect(
            lambda t=title: self._on_new_clicked(t)
        )
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(0)

        # Toggle UI for categories with alternate views (Mobs↔Maturities, etc.)
        toggle_config = LEAF_TOGGLE_MAP.get(title)
        if toggle_config:
            toggle_widget, alt_table = self._build_toggle_ui(
                title, toggle_config, table_view, items, column_prefs,
            )
            layout.addWidget(toggle_widget)
            layout.addWidget(alt_table, 1)
            self._alt_table_refs[title] = alt_table

        layout.addWidget(table_view, 1)

        subset_result = self._precomputed_subsets.pop(title, None)
        table_view.set_data(items, cache, numeric, subset_result=subset_result)

        self._cached_leaf_views[title] = container
        self._cached_table_refs[title] = table_view
        self._current_table_view = table_view
        self._swap_content(container)

    def _show_placeholder(self, title: str):
        """Show 'Coming soon' for unmapped categories."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        placeholder = QLabel("Coming soon — this section is under development.")
        placeholder.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 14px; background: transparent;"
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder, 1)

        self._swap_content(container)

    def _on_data_loaded(self, title: str, items: list, full_cache: list, full_numeric: list):
        """Handle data arriving from background fetch or revalidation."""
        self._leaf_items[title] = items
        self._precomputed_data[title] = (items, full_cache, full_numeric)

        # If table already exists, refresh it in-place
        if title in self._cached_table_refs:
            subset = self._precomputed_subsets.pop(title, None)
            self._cached_table_refs[title].set_data(
                items, full_cache, full_numeric, subset_result=subset,
            )
            # Also refresh the alternate table if it was populated (e.g. re-derive maturities)
            toggle_config = LEAF_TOGGLE_MAP.get(title)
            if toggle_config and title in self._alt_table_refs and title in self._alt_items:
                self._load_alternate_data(title, toggle_config, items)
            return

        # Table not cached — only create if user is currently viewing this leaf
        if not self._path or self._path[-1] != title:
            return

        mapping = LEAF_DATA_MAP.get(title)
        if not mapping:
            return
        _, page_type_id = mapping

        self._create_and_show_table(title, page_type_id, items, full_cache, full_numeric)

    def _on_new_clicked(self, category_title: str):
        """Open the create-new-entity page in the system browser."""
        url_prefix = _CATEGORY_URL_PREFIX.get(category_title)
        if not url_prefix or not self._config:
            return
        import webbrowser
        webbrowser.open(self._config.nexus_base_url + url_prefix + "?mode=create")

    # --- Toggle view (Mobs↔Maturities, Missions↔Mission Chains) ---

    def _build_toggle_ui(self, title, toggle_config, primary_table, items, column_prefs):
        """Create toggle buttons and the alternate table for a leaf with two views.

        Returns ``(toggle_widget, alt_table)``.  The alt table starts hidden.
        """
        from ..widgets.wiki_table import WikiTableView

        # Toggle bar
        toggle_widget = QWidget()
        toggle_widget.setStyleSheet("background: transparent;")
        toggle_layout = QHBoxLayout(toggle_widget)
        toggle_layout.setContentsMargins(0, 0, 0, 8)
        toggle_layout.setSpacing(8)

        btn_a = QPushButton(toggle_config["label_a"])
        btn_b = QPushButton(toggle_config["label_b"])

        active_style = (
            f"QPushButton {{ background-color: {ACCENT}; color: white;"
            f" border: 1px solid {ACCENT}; border-radius: 4px;"
            f" padding: 6px 8px; font-size: 12px; }}"
        )
        inactive_style = (
            f"QPushButton {{ background-color: {SECONDARY}; color: {TEXT};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" padding: 6px 8px; font-size: 12px; }}"
            f"QPushButton:hover {{ background-color: {HOVER}; }}"
        )

        btn_a.setStyleSheet(active_style)
        btn_b.setStyleSheet(inactive_style)
        btn_a.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_b.setCursor(Qt.CursorShape.PointingHandCursor)

        toggle_layout.addWidget(btn_a)
        toggle_layout.addWidget(btn_b)
        toggle_layout.addStretch()

        # Alternate table (hidden, same container)
        alt_page_type_id = toggle_config["page_type_id"]
        alt_table = WikiTableView(
            page_type_id=alt_page_type_id,
            column_prefs=column_prefs,
            on_columns_changed=self._on_columns_changed,
        )
        alt_table.row_activated.connect(
            lambda item, t=title, tc=toggle_config: self._on_toggle_row_activated(t, item, tc)
        )
        alt_table.hide()

        def switch_to_a():
            self._toggle_states[title] = "a"
            btn_a.setStyleSheet(active_style)
            btn_b.setStyleSheet(inactive_style)
            alt_table.hide()
            primary_table.show()
            self._current_table_view = primary_table

        def switch_to_b():
            self._toggle_states[title] = "b"
            btn_b.setStyleSheet(active_style)
            btn_a.setStyleSheet(inactive_style)
            primary_table.hide()
            alt_table.show()
            self._current_table_view = alt_table
            # Lazy-load alternate data on first toggle
            if title not in self._alt_items:
                self._load_alternate_data(title, toggle_config, items)

        btn_a.clicked.connect(switch_to_a)
        btn_b.clicked.connect(switch_to_b)

        return toggle_widget, alt_table

    def _load_alternate_data(self, title, toggle_config, primary_items):
        """Fetch or derive alternate-view data in a background thread."""
        alt_ptid = toggle_config["page_type_id"]

        def fetch():
            from ..widgets.wiki_table import build_column_cache

            derive_fn = toggle_config.get("derive_fn")
            method_name = toggle_config.get("method_name")

            if derive_fn:
                alt_items = derive_fn(primary_items)
            elif method_name:
                alt_items = getattr(self._data_client, method_name)()
            else:
                return

            all_defs = COLUMN_DEFS.get(alt_ptid, {})
            col_defs_list = list(all_defs.values())
            cache, numeric = build_column_cache(alt_items, col_defs_list)
            self._alt_data_loaded.emit(title, alt_items, cache, numeric)

        threading.Thread(target=fetch, daemon=True, name=f"wiki-alt-{alt_ptid}").start()

    def _on_alt_data_loaded(self, title, items, cache, numeric):
        """Handle alternate-view data arriving from background thread."""
        self._alt_items[title] = items
        alt_table = self._alt_table_refs.get(title)
        if alt_table:
            alt_table.set_data(items, cache, numeric)

    def _on_toggle_row_activated(self, leaf_title, item, toggle_config):
        """Handle double-click on an alternate table row."""
        parent_key = toggle_config.get("parent_key")
        if parent_key and item.get(parent_key):
            # Navigate to the parent entity (e.g. maturity → parent mob)
            parent_name = item[parent_key]
            new_path = list(self._path) + [parent_name]
            QTimer.singleShot(0, lambda: self.navigate_to(new_path))
            return

        # No parent navigation — fall back to standard row activation
        entity_name = get_item_name(item)
        if entity_name:
            new_path = list(self._path) + [entity_name]
            QTimer.singleShot(0, lambda: self.navigate_to(new_path))

    def _on_row_activated(self, leaf_title: str, item: dict):
        """Handle double-click on a table row — navigate to entity detail."""
        entity_name = get_item_name(item)
        if not entity_name:
            return
        # Build path: current path + entity name
        # Current path is either ["Weapons"] or ["Attachments", "Weapon Amplifiers"]
        new_path = list(self._path) + [entity_name]
        # Defer to avoid destroying the QTableView while it's still
        # processing the doubleClicked signal (causes C++ use-after-free).
        QTimer.singleShot(0, lambda: self.navigate_to(new_path))

    def _show_entity_detail(self, category_title: str, entity_name: str):
        """Show the detail view for a single entity."""
        # Find the entity in cached items
        items = self._leaf_items.get(category_title)
        if not items:
            # Items not cached yet — fetch them, then signal main thread
            mapping = LEAF_DATA_MAP.get(category_title)
            if not mapping:
                self._show_placeholder(entity_name)
                return
            method_name, _ = mapping

            def fetch():
                fetched = getattr(self._data_client, method_name)()
                # Signal main thread — safe cross-thread communication
                self._detail_items_ready.emit(category_title, entity_name, fetched)

            threading.Thread(
                target=fetch, daemon=True, name="wiki-detail-fetch"
            ).start()
            self._show_loading_placeholder(entity_name)
            return

        # Find entity by name in primary items
        item = None
        for i in items:
            if get_item_name(i) == entity_name:
                item = i
                break

        # Not in primary items — check alternate (toggle) items
        page_type_id = None
        if not item:
            toggle_config = LEAF_TOGGLE_MAP.get(category_title)
            if toggle_config:
                alt_items = self._alt_items.get(category_title, [])
                for i in alt_items:
                    if get_item_name(i) == entity_name:
                        item = i
                        page_type_id = toggle_config["page_type_id"]
                        break

        if not item:
            self._show_placeholder(entity_name)
            return

        # Determine which detail view to use
        if page_type_id is None:
            mapping = LEAF_DATA_MAP.get(category_title)
            if not mapping:
                self._show_placeholder(entity_name)
                return
            _, page_type_id = mapping
        nexus_base_url = ""
        if self._config:
            nexus_base_url = getattr(self._config, "nexus_base_url", "")

        detail_view: QWidget | None = None
        if page_type_id == "weapons":
            from ..widgets.weapon_detail import WeaponDetailView
            detail_view = WeaponDetailView(
                item, nexus_base_url=nexus_base_url,
                data_client=self._data_client,
                nexus_client=self._nexus_client,
            )
        elif page_type_id == "blueprints":
            from ..widgets.blueprint_detail import BlueprintDetailView
            detail_view = BlueprintDetailView(
                item, nexus_base_url=nexus_base_url,
                data_client=self._data_client,
                nexus_client=self._nexus_client,
            )
        elif page_type_id == "armorsets":
            from ..widgets.armor_detail import ArmorSetDetailView
            detail_view = ArmorSetDetailView(
                item, nexus_base_url=nexus_base_url,
                data_client=self._data_client,
                nexus_client=self._nexus_client,
            )
        elif page_type_id == "vehicles":
            from ..widgets.vehicle_detail import VehicleDetailView
            detail_view = VehicleDetailView(
                item, nexus_base_url=nexus_base_url,
                data_client=self._data_client,
                nexus_client=self._nexus_client,
            )
        elif page_type_id == "pets":
            from ..widgets.pet_detail import PetDetailView
            detail_view = PetDetailView(
                item, nexus_base_url=nexus_base_url,
                data_client=self._data_client,
                nexus_client=self._nexus_client,
            )
        elif page_type_id in ("medicaltools", "medicalchips"):
            from ..widgets.medical_detail import MedicalDetailView
            detail_view = MedicalDetailView(
                item, page_type_id=page_type_id,
                nexus_base_url=nexus_base_url,
                data_client=self._data_client,
                nexus_client=self._nexus_client,
            )
        elif page_type_id in ("finders", "excavators", "scanners", "refiners",
                               "teleportationchips", "misctools"):
            from ..widgets.tool_detail import ToolDetailView
            detail_view = ToolDetailView(
                item, page_type_id=page_type_id,
                nexus_base_url=nexus_base_url,
                data_client=self._data_client,
                nexus_client=self._nexus_client,
            )
        elif page_type_id == "weaponamplifiers":
            from ..widgets.amplifier_detail import AmplifierDetailView
            detail_view = AmplifierDetailView(
                item, nexus_base_url=nexus_base_url,
                data_client=self._data_client,
                nexus_client=self._nexus_client,
            )
        elif page_type_id == "mobs":
            from ..widgets.mob_detail import MobDetailView
            detail_view = MobDetailView(
                item, nexus_base_url=nexus_base_url,
                data_client=self._data_client,
            )
        elif page_type_id == "skills":
            from ..widgets.skill_detail import SkillDetailView
            detail_view = SkillDetailView(
                item, nexus_base_url=nexus_base_url,
                data_client=self._data_client,
            )
        elif page_type_id == "professions":
            from ..widgets.profession_detail import ProfessionDetailView
            detail_view = ProfessionDetailView(
                item, nexus_base_url=nexus_base_url,
                data_client=self._data_client,
            )
        elif page_type_id == "vendors":
            from ..widgets.vendor_detail import VendorDetailView
            detail_view = VendorDetailView(
                item, nexus_base_url=nexus_base_url,
                data_client=self._data_client,
            )
        elif page_type_id == "missions":
            from ..widgets.mission_detail import MissionDetailView
            detail_view = MissionDetailView(
                item, nexus_base_url=nexus_base_url,
                data_client=self._data_client,
            )
        elif page_type_id == "missionchains":
            from ..widgets.mission_chain_detail import MissionChainDetailView
            detail_view = MissionChainDetailView(
                item, nexus_base_url=nexus_base_url,
                data_client=self._data_client,
            )
        elif page_type_id == "locations":
            from ..widgets.location_detail import LocationDetailView
            detail_view = LocationDetailView(
                item, nexus_base_url=nexus_base_url,
                data_client=self._data_client,
            )
        else:
            from ..widgets.generic_detail import GenericItemDetailView
            detail_view = GenericItemDetailView(
                item, page_type_id=page_type_id,
                nexus_base_url=nexus_base_url,
                data_client=self._data_client,
                nexus_client=self._nexus_client,
            )

        # Add edit button if URL is available
        url_prefix = _CATEGORY_URL_PREFIX.get(category_title)
        if url_prefix and nexus_base_url and hasattr(detail_view, "set_edit_url"):
            view_param = ""
            if page_type_id == "missionchains":
                view_param = "&view=chains"
            edit_url = (
                nexus_base_url + url_prefix + "/"
                + _encode_uri_safe(entity_name) + "?mode=edit" + view_param
            )
            detail_view.set_edit_url(edit_url)

        # Connect entity navigation signal
        if hasattr(detail_view, "entity_navigate"):
            detail_view.entity_navigate.connect(self._on_entity_navigate)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)
        layout.addWidget(detail_view)
        layout.addStretch(1)

        self._swap_content(container)
        self._current_table_view = None

        # Populate TOC sidebar from the detail view's article sections
        if hasattr(detail_view, "_article_sections") and detail_view._article_sections:
            self._toc_panel.set_sections(detail_view._article_sections)
            self._toc_panel.show()

    def _on_toc_entry_clicked(self, section):
        """Expand the section (if collapsed) and scroll its header into view."""
        if section is None:
            # "Details" entry — scroll to top
            self._scroll.verticalScrollBar().setValue(0)
            return
        if not section._expanded:
            section.toggle()
        # Scroll the section header to the top of the viewport.
        # ensureWidgetVisible centres the widget; instead, compute the
        # header's position and scroll there directly.
        def scroll_to_header():
            header = section._header
            # Map the header's top-left to the scroll area's widget coords,
            # then offset upward by half the inter-section gap for breathing room.
            pos = header.mapTo(self._scroll.widget(), header.rect().topLeft())
            self._scroll.verticalScrollBar().setValue(max(0, pos.y() - 6))
        # Small delay so layout updates after toggle before scrolling
        QTimer.singleShot(50, scroll_to_header)

    def _show_loading_placeholder(self, title: str):
        """Show 'Loading...' placeholder while fetching data."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        loading = QLabel(f"Loading {title}...")
        loading.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 14px; background: transparent;"
        )
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(loading, 1)

        self._swap_content(container)

    def _on_entity_navigate(self, entity: dict):
        """Handle entity link click from a detail view — navigate to the wiki page."""
        from ..widgets.search_popup import WIKI_PATHS
        entity_type = entity.get("Type", "")
        entity_name = entity.get("Name", "")
        if not entity_name:
            return
        path = WIKI_PATHS.get(entity_type)
        if path:
            QTimer.singleShot(0, lambda: self.navigate_to(list(path) + [entity_name]))

    def _on_detail_items_ready(self, category_title: str, entity_name: str, items: list):
        """Handle items arriving for entity detail — cache and show detail."""
        self._leaf_items[category_title] = items
        # Only proceed if user is still on the same detail path
        if entity_name in self._path:
            self._show_entity_detail(category_title, entity_name)

    def _sync_column_prefs_from_server(self):
        """Fetch column preferences from the server and merge into local config.

        Account preferences win on conflict so that switching machines
        preserves the user's layout.
        """
        if not self._nexus_client or not self._nexus_client.is_authenticated():
            return
        if not self._config:
            return

        _PREFIX = "wiki.nav-columns-"

        def _sync():
            prefs = self._nexus_client.get_preferences()
            if not prefs:
                return
            local = self._config.wiki_column_prefs or {}
            changed = False
            for key, data in prefs.items():
                if not key.startswith(_PREFIX):
                    continue
                page_type_id = key[len(_PREFIX):]
                if not isinstance(data, list):
                    continue
                # Account configuration wins over local
                if local.get(page_type_id) != data:
                    local[page_type_id] = data
                    changed = True
            if changed:
                self._config.wiki_column_prefs = local
                if self._config_path:
                    from ...core.config import save_config
                    save_config(self._config, self._config_path)

        threading.Thread(target=_sync, daemon=True, name="wiki-pref-dl").start()

    def _on_columns_changed(self, page_type_id: str, keys: list[str]):
        """Persist column preferences locally and to server."""
        if self._config:
            if not self._config.wiki_column_prefs:
                self._config.wiki_column_prefs = {}
            self._config.wiki_column_prefs[page_type_id] = keys
            if self._config_path:
                from ...core.config import save_config
                save_config(self._config, self._config_path)

        # Sync to server in background (if authenticated)
        if self._nexus_client and self._nexus_client.is_authenticated():
            pref_key = f"wiki.nav-columns-{page_type_id}"

            def sync():
                self._nexus_client.save_preference(pref_key, keys)

            threading.Thread(target=sync, daemon=True, name="wiki-pref-sync").start()

    # --- Background warmup ---

    def _warmup_all(self):
        """Background: pre-fetch raw wiki data, then revalidate every 15 min.

        Column caches are built lazily when the user navigates to a category
        (in _show_leaf), keeping startup fast by avoiding CPU-bound work that
        contends with the UI thread via the GIL.
        """
        import time
        from ..widgets.wiki_table import build_column_cache, build_subset_cache

        stop = self._warmup_stop
        while not stop.is_set():
            column_prefs = (self._config.wiki_column_prefs or {}) if self._config else {}
            for title, (method_name, page_type_id) in LEAF_DATA_MAP.items():
                if stop.is_set():
                    return
                try:
                    items = getattr(self._data_client, method_name)()
                    old_items = self._leaf_items.get(title)
                    self._leaf_items[title] = items

                    # Revalidation: if data changed AND table already built, rebuild cache
                    if old_items is not None and title in self._cached_table_refs:
                        if len(old_items) != len(items) or old_items != items:
                            all_defs = COLUMN_DEFS.get(page_type_id, {})
                            col_defs_list = list(all_defs.values())
                            cache, numeric = build_column_cache(items, col_defs_list)
                            self._precomputed_data[title] = (items, cache, numeric)
                            # Pre-compute subset for the active columns
                            prefs = column_prefs.get(page_type_id)
                            active_keys = list(prefs) if prefs else list(DEFAULT_COLUMNS.get(page_type_id, []))
                            all_type_keys = list(all_defs.keys())
                            self._precomputed_subsets[title] = build_subset_cache(
                                cache, numeric, all_type_keys, active_keys, all_defs,
                            )
                            self._data_loaded.emit(title, items, cache, numeric)
                except Exception:
                    pass
                # Yield GIL between entity fetches so the UI thread stays responsive.
                # Each fetch involves HTTP I/O + JSON parsing that can hold the GIL.
                time.sleep(0)

            # Invalidate data_client cache so next cycle fetches fresh data
            self._data_client.invalidate_cache()

            stop.wait(timeout=900)  # 15 minutes

    # --- Card grid builder ---

    def _build_card_grid(
        self,
        entries: list[tuple[str, str, str]],
        on_click,
    ) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        grid = QGridLayout(widget)
        grid.setContentsMargins(0, 8, 0, 0)
        grid.setSpacing(12)

        for i, (abbrev, title, desc) in enumerate(entries):
            card = _WikiCard(abbrev, title, desc)
            card.clicked.connect(lambda _, t=title: on_click(t))
            row, col = divmod(i, GRID_COLUMNS)
            grid.addWidget(card, row, col)

        # Fill remaining cells in last row with spacers
        remainder = len(entries) % GRID_COLUMNS
        if remainder:
            last_row = len(entries) // GRID_COLUMNS
            for c in range(remainder, GRID_COLUMNS):
                spacer = QWidget()
                spacer.setStyleSheet("background: transparent;")
                grid.addWidget(spacer, last_row, c)

        return widget

    # --- Breadcrumbs ---

    def _update_breadcrumbs(self):
        # Clear existing breadcrumb widgets
        while self._breadcrumb_container.count():
            item = self._breadcrumb_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self._path:
            self._toolbar.hide()
            return

        self._toolbar.show()

        # "Wiki" root link
        self._add_breadcrumb_link("Wiki", [])
        self._add_breadcrumb_separator()

        # Section name (Items / Information) if applicable
        section = _SECTION_FOR_CATEGORY.get(self._path[0])
        if section:
            self._add_breadcrumb_link(section, [])
            self._add_breadcrumb_separator()

        # Path segments
        for i, segment in enumerate(self._path):
            is_last = (i == len(self._path) - 1)
            if is_last:
                # Current location — not clickable
                label = QLabel(segment)
                label.setStyleSheet(
                    f"color: {TEXT}; font-size: 12px; font-weight: bold;"
                    " background: transparent; border: none; padding: 0 2px;"
                )
                self._breadcrumb_container.addWidget(label)
            else:
                self._add_breadcrumb_link(segment, self._path[:i + 1])
                self._add_breadcrumb_separator()

        self._breadcrumb_container.addStretch()

        # Short URL copy button (far right)
        short_url = _get_short_url(self._path)
        if short_url:
            btn = QPushButton("Copy Link")
            btn.setToolTip(short_url)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  color: {ACCENT}; background: transparent;"
                f"  border: 1px solid {BORDER}; border-radius: 4px;"
                f"  font-size: 11px; padding: 0 8px;"
                f"}}"
                f"QPushButton:hover {{ background-color: {HOVER}; }}"
            )
            btn.clicked.connect(lambda _, u=short_url: self._copy_short_url(u))
            self._breadcrumb_container.addWidget(btn)

    def _copy_short_url(self, url: str):
        """Copy short URL to clipboard with brief visual feedback."""
        QApplication.clipboard().setText(url)
        # Find the button (last widget before any stretch)
        sender = self.sender()
        if isinstance(sender, QPushButton):
            original = sender.text()
            sender.setText("Copied!")
            QTimer.singleShot(1500, lambda: sender.setText(original)
                              if sender and not sender.isHidden() else None)

    def _add_breadcrumb_link(self, text: str, path: list[str]):
        link = QLabel(text)
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.setStyleSheet(
            f"color: {ACCENT}; font-size: 12px; background: transparent;"
            " border: none; padding: 0 2px;"
        )
        link.mousePressEvent = lambda _, p=path: self.navigate_to(p)
        self._breadcrumb_container.addWidget(link)

    def _add_breadcrumb_separator(self):
        sep = QLabel("\u203a")  # ›
        sep.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;"
            " border: none; padding: 0 2px;"
        )
        self._breadcrumb_container.addWidget(sep)
