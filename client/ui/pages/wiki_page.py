"""Wiki page — browse the Entropia Nexus knowledge base."""

from __future__ import annotations

import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..theme import (
    PRIMARY, SECONDARY, HOVER, BORDER, ACCENT, TEXT, TEXT_MUTED,
    MAIN_DARK, PAGE_HEADER_OBJECT_NAME,
)
from ...data.wiki_columns import LEAF_DATA_MAP

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
# Search results view (shown when user presses Enter in title-bar search)
# ---------------------------------------------------------------------------

class _SearchResultsView(QWidget):
    """Full search results page displayed inside the wiki."""

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
                row = QWidget()
                row.setStyleSheet(
                    f"background-color: {SECONDARY}; border-radius: 4px;"
                )
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(12, 6, 12, 6)

                name = QLabel(item.get("DisplayName") or item.get("Name", ""))
                name.setStyleSheet(f"color: {TEXT}; font-size: 13px; background: transparent;")
                row_layout.addWidget(name, 1)

                type_badge = QLabel(get_type_name(item.get("Type", "")))
                type_badge.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 11px;"
                    f" background-color: {PRIMARY}; border-radius: 3px;"
                    f" padding: 2px 6px;"
                )
                row_layout.addWidget(type_badge)

                self._layout.addWidget(row)

        self._layout.addStretch(1)


# ---------------------------------------------------------------------------
# Wiki page
# ---------------------------------------------------------------------------

class WikiPage(QWidget):
    """Browsable wiki page mirroring the website's category structure."""

    navigation_changed = pyqtSignal(list)
    _data_loaded = pyqtSignal(str, list)  # (leaf_title, items)

    def __init__(self, *, signals, data_client, config=None, config_path=None, nexus_client=None):
        super().__init__()
        self._signals = signals
        self._data_client = data_client
        self._config = config
        self._config_path = config_path
        self._nexus_client = nexus_client
        self._path: list[str] = []
        self._current_table_view = None  # active WikiTableView (if any)

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

        # Scrollable content area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        root.addWidget(self._scroll)

        # Content widget (rebuilt on navigation)
        self._content: QWidget | None = None

        # Search results sub-view
        self._search_view = _SearchResultsView()

        # Wire data-loaded signal (from background threads → main thread)
        self._data_loaded.connect(self._on_data_loaded)

        # Build initial overview
        self._navigate_internal([])

    # --- Public API ---

    def navigate_to(self, path: list[str]):
        """Navigate to a path and emit navigation_changed."""
        if path == self._path:
            return
        self._navigate_internal(path)
        self.navigation_changed.emit(list(self._path))

    def get_sub_state(self) -> list[str]:
        return list(self._path)

    def set_sub_state(self, path: list[str]):
        """Restore a previously saved navigation path (no signal emitted)."""
        self._navigate_internal(path)

    def show_search_results(self, query: str, results: list[dict]):
        """Display full search results from the title bar."""
        self._path = ["Search"]
        self._update_breadcrumbs()
        self._search_view.show_results(query, results)
        self._scroll.setWidget(self._search_view)
        self._content = self._search_view
        self.navigation_changed.emit(list(self._path))

    # --- Internal navigation ---

    def _navigate_internal(self, path: list[str]):
        self._path = list(path)
        self._update_breadcrumbs()

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
            # Sub-category leaf (e.g. ["Attachments", "Weapon Amplifiers"])
            self._show_leaf(path[-1])
        else:
            self._show_leaf(path[-1])

    def _show_overview(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 16)
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
        self._scroll.setWidget(container)
        self._content = container

    def _show_sub_grid(self, parent_title: str, subtypes: list[tuple[str, str, str]]):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(0)

        grid = self._build_card_grid(
            subtypes,
            lambda title, pt=parent_title: self.navigate_to([pt, title]),
        )
        layout.addWidget(grid)
        layout.addStretch(1)
        self._scroll.setWidget(container)
        self._content = container

    def _show_leaf(self, title: str):
        mapping = LEAF_DATA_MAP.get(title)
        if not mapping:
            # Unmapped categories (Guides, Enumerations)
            self._show_placeholder(title)
            return

        method_name, page_type_id = mapping

        from ..widgets.wiki_table import WikiTableView

        column_prefs = {}
        if self._config:
            column_prefs = self._config.wiki_column_prefs or {}

        table_view = WikiTableView(
            page_type_id=page_type_id,
            column_prefs=column_prefs,
            on_columns_changed=self._on_columns_changed,
        )
        table_view.set_loading()
        self._current_table_view = table_view

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(0)
        layout.addWidget(table_view, 1)

        self._scroll.setWidget(container)
        self._content = container

        # Fetch data in background thread
        leaf_title = title

        def fetch():
            items = getattr(self._data_client, method_name)()
            self._data_loaded.emit(leaf_title, items)

        threading.Thread(target=fetch, daemon=True, name=f"wiki-{page_type_id}").start()

    def _show_placeholder(self, title: str):
        """Show 'Coming soon' for unmapped categories."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(8)

        placeholder = QLabel("Coming soon — this section is under development.")
        placeholder.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 14px; background: transparent;"
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder, 1)

        self._scroll.setWidget(container)
        self._content = container

    def _on_data_loaded(self, title: str, items: list):
        """Handle data arriving from background fetch — populate the table."""
        # Only populate if the user is still on the same leaf page
        if not self._path or self._path[-1] != title:
            return
        if self._current_table_view:
            self._current_table_view.set_data(items)

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
