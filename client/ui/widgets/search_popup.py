"""Categorised search results popup for the title bar search."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from ..theme import (
    SECONDARY, HOVER, BORDER, PRIMARY, ACCENT, TEXT, TEXT_MUTED, MAIN_DARK,
)

# ---------------------------------------------------------------------------
# Type name mapping (ported from nexus/src/lib/util.js getTypeName)
# ---------------------------------------------------------------------------

TYPE_NAMES: dict[str, str] = {
    "Weapon": "Weapon",
    "Armor": "Armor",
    "ArmorSet": "Armor Set",
    "MedicalTool": "Medical Tool",
    "MedicalChip": "Medical Chip",
    "Refiner": "Refiner",
    "Scanner": "Scanner",
    "Finder": "Finder",
    "Excavator": "Excavator",
    "TeleportationChip": "Teleportation Chip",
    "EffectChip": "Effect Chip",
    "MiscTool": "Misc Tool",
    "Blueprint": "Blueprint",
    "BlueprintBook": "Blueprint Book",
    "Material": "Material",
    "Vehicle": "Vehicle",
    "Pet": "Pet",
    "Consumable": "Stimulant",
    "Capsule": "Capsule",
    "Furniture": "Furniture",
    "Decoration": "Decoration",
    "StorageContainer": "Storage Container",
    "Sign": "Sign",
    "Clothing": "Clothing",
    "WeaponAmplifier": "Weapon Amplifier",
    "WeaponVisionAttachment": "Sight/Scope",
    "Absorber": "Absorber",
    "ArmorPlating": "Armor Plating",
    "FinderAmplifier": "Finder Amplifier",
    "Enhancer": "Enhancer",
    "MindforceImplant": "Mindforce Implant",
    "Mob": "Mob",
    "Location": "Location",
    "Area": "Area",
    "Skill": "Skill",
    "Profession": "Profession",
    "Vendor": "Vendor",
    "Mission": "Mission",
    "MissionChain": "Mission Chain",
    "Shop": "Shop",
    "User": "User",
    "Society": "Society",
    "Strongbox": "Strongbox",
}


def get_type_name(type_key: str) -> str:
    """Return a human-readable display name for an API entity type."""
    return TYPE_NAMES.get(type_key, type_key or "Other")


# ---------------------------------------------------------------------------
# Location-specific type names
# ---------------------------------------------------------------------------

LOCATION_TYPE_NAMES: dict[str, str] = {
    "Teleporter": "Teleporter",
    "Npc": "NPC",
    "Interactable": "Interactable",
    "Area": "Area",
    "Estate": "Estate",
    "Outpost": "Outpost",
    "Camp": "Camp",
    "City": "City",
    "WaveEvent": "Wave Event",
    "RevivalPoint": "Revival Point",
    "InstanceEntrance": "Instance",
}


def get_display_type(item: dict) -> str:
    """Return display type, using specific location type when available."""
    if item.get("Type") == "Location":
        loc_type = (item.get("LocationType")
                    or (item.get("Properties") or {}).get("Type"))
        if loc_type:
            return LOCATION_TYPE_NAMES.get(loc_type, loc_type)
    return get_type_name(item.get("Type", ""))


# ---------------------------------------------------------------------------
# Type → wiki navigation path mapping (shared by main_window + wiki_page)
# ---------------------------------------------------------------------------

WIKI_PATHS: dict[str, list[str]] = {
    # Item types
    'Weapon': ['Weapons'],
    'Armor': ['Armor Sets'],
    'ArmorSet': ['Armor Sets'],
    'Clothing': ['Clothing'],
    'WeaponAmplifier': ['Attachments', 'Weapon Amplifiers'],
    'WeaponVisionAttachment': ['Attachments', 'Sights/Scopes'],
    'Absorber': ['Attachments', 'Absorbers'],
    'FinderAmplifier': ['Attachments', 'Finder Amplifiers'],
    'ArmorPlating': ['Attachments', 'Armor Platings'],
    'Enhancer': ['Attachments', 'Enhancers'],
    'MindforceImplant': ['Attachments', 'Mindforce Implants'],
    'MedicalTool': ['Medical Tools', 'Medical Tools'],
    'MedicalChip': ['Medical Tools', 'Medical Chips'],
    'Refiner': ['Tools', 'Refiners'],
    'Scanner': ['Tools', 'Scanners'],
    'Finder': ['Tools', 'Finders'],
    'Excavator': ['Tools', 'Excavators'],
    'TeleportationChip': ['Tools', 'Teleportation Chips'],
    'EffectChip': ['Tools', 'Effect Chips'],
    'MiscTool': ['Tools', 'Misc. Tools'],
    'Material': ['Materials'],
    'Blueprint': ['Blueprints'],
    'BlueprintBook': ['Blueprints'],
    'Consumable': ['Consumables', 'Stimulants'],
    'Capsule': ['Consumables', 'Creature Control Capsules'],
    'Vehicle': ['Vehicles'],
    'Pet': ['Pets'],
    'Furniture': ['Furnishings', 'Furniture'],
    'Decoration': ['Furnishings', 'Decorations'],
    'StorageContainer': ['Furnishings', 'Storage Containers'],
    'Sign': ['Furnishings', 'Signs'],
    'Strongbox': ['Strongboxes'],
    # Information types
    'Mob': ['Mobs'],
    'Skill': ['Skills'],
    'Profession': ['Professions'],
    'Vendor': ['Vendors'],
    'Location': ['Locations'],
    'Area': ['Locations'],
    'Mission': ['Missions'],
    'MissionChain': ['Missions'],
}


# ---------------------------------------------------------------------------
# Categories available for user-created wiki entries
# ---------------------------------------------------------------------------

CREATABLE_CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Items", [
        ("Weapon", "/items/weapons"),
        ("Armor Set", "/items/armorsets"),
        ("Clothing", "/items/clothing"),
        ("Material", "/items/materials"),
        ("Blueprint", "/items/blueprints"),
        ("Vehicle", "/items/vehicles"),
        ("Pet", "/items/pets"),
        ("Consumable", "/items/consumables"),
        ("Attachment", "/items/attachments"),
        ("Tool", "/items/tools"),
        ("Medical Tool", "/items/medicaltools"),
        ("Furnishing", "/items/furnishings"),
        ("Strongbox", "/items/strongboxes"),
    ]),
    ("Information", [
        ("Mob", "/information/mobs"),
        ("Mission", "/information/missions"),
        ("Profession", "/information/professions"),
        ("Skill", "/information/skills"),
        ("Vendor", "/information/vendors"),
        ("Location", "/information/locations"),
    ]),
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_PER_CATEGORY = 5
MAX_TOTAL = 20

_POPUP_STYLE = f"""
    QWidget#searchPopup {{
        background-color: {SECONDARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
    }}
"""

_CATEGORY_STYLE = (
    f"color: {TEXT_MUTED}; font-size: 10px; font-weight: bold;"
    f" letter-spacing: 0.5px; text-transform: uppercase;"
    f" padding: 4px 8px; background-color: {MAIN_DARK};"
    f" border-bottom: 1px solid {BORDER};"
)

_ROW_STYLE = (
    f"padding: 1px 8px;"
    f" border: 1px solid transparent;"
    f" background-color: transparent;"
)

_ROW_HIGHLIGHT_STYLE = (
    f"padding: 1px 8px;"
    f" border: 1px solid {ACCENT};"
    f" background-color: {HOVER};"
)


# ---------------------------------------------------------------------------
# Popup widget
# ---------------------------------------------------------------------------

class _ClickableRow(QWidget):
    """A result row that supports click and hover."""

    def __init__(self, item: dict, popup: "SearchResultsPopup"):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._item = item
        self._popup = popup
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._popup.result_selected.emit(self._item)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        try:
            idx = self._popup._row_widgets.index(self)
            self._popup._set_highlight(idx)
        except ValueError:
            pass
        super().enterEvent(event)

    def leaveEvent(self, event):
        super().leaveEvent(event)


class _CategoryRow(QWidget):
    """A clickable row for the 'add to wiki' category picker."""

    def __init__(self, url_path: str, popup: "SearchResultsPopup"):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._url_path = url_path
        self._popup = popup
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._popup.create_requested.emit(self._url_path)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.setStyleSheet(_ROW_HIGHLIGHT_STYLE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(_ROW_STYLE)
        super().leaveEvent(event)


class SearchResultsPopup(QWidget):
    """Categorised search results dropdown positioned below the search bar."""

    result_selected = pyqtSignal(dict)     # individual result picked
    search_submitted = pyqtSignal(str)     # Enter without arrow selection
    create_requested = pyqtSignal(str)     # URL path for create mode

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("searchPopup")
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        )
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(_POPUP_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        layout.addWidget(self._scroll)

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(0)
        self._inner_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._inner)

        self._flat_results: list[dict] = []
        self._row_widgets: list[QWidget] = []
        self._highlighted_index: int = -1
        self._has_used_arrows: bool = False
        self._query: str = ""

    # --- Public API ---

    def set_results(self, scored_results: list[dict], query: str):
        """Populate the popup with scored, sorted results."""
        self._query = query
        self._highlighted_index = -1
        self._has_used_arrows = False
        self._flat_results.clear()
        self._row_widgets.clear()

        # Fresh inner widget — avoids stale layout geometry cache
        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(0)
        self._inner_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Categorise
        categories: dict[str, list[dict]] = {}
        for r in scored_results:
            cat = get_type_name(r.get("Type", ""))
            categories.setdefault(cat, []).append(r)

        # Sort categories by best score
        sorted_cats = sorted(
            categories.keys(),
            key=lambda c: -(categories[c][0].get("_score", 0)),
        )

        total = 0
        for cat in sorted_cats:
            remaining = MAX_TOTAL - total
            if remaining <= 0:
                break
            items = categories[cat][:min(MAX_PER_CATEGORY, remaining)]
            if not items:
                continue

            # Category header
            header = QLabel(cat)
            header.setStyleSheet(_CATEGORY_STYLE)
            self._inner_layout.addWidget(header)

            for item in items:
                row = self._make_row(item)
                self._inner_layout.addWidget(row)
                self._flat_results.append(item)
                self._row_widgets.append(row)
                total += 1

        if total == 0:
            self._build_empty_state(query)

        # setWidget deletes the old inner widget automatically
        self._scroll.setWidget(self._inner)

    def fit_height(self, max_h: int):
        """Size the popup to its content, then show it."""
        self._max_h = max_h
        self._inner_layout.activate()
        h = min(self._content_height(), max_h)
        # Destroy the native OS window handle; show() will create a
        # fresh one at the new size.  Required on Windows where
        # setFixedHeight() doesn't shrink a visible frameless window.
        win = self.windowHandle()
        if win:
            win.destroy()
        self.setFixedHeight(h)
        QTimer.singleShot(0, self._show_popup)

    def _show_popup(self):
        self.show()
        self.raise_()

    def _content_height(self) -> int:
        """Sum child widget sizeHints (skip isVisible — parent is hidden)."""
        h = 0
        for i in range(self._inner_layout.count()):
            w = self._inner_layout.itemAt(i).widget()
            if w:
                h += w.sizeHint().height()
        return h + 4

    def handle_key(self, key: int) -> bool:
        """Process a key press. Returns True if consumed."""
        if key == Qt.Key.Key_Down:
            self._has_used_arrows = True
            if self._highlighted_index < len(self._flat_results) - 1:
                self._set_highlight(self._highlighted_index + 1)
            return True

        if key == Qt.Key.Key_Up:
            self._has_used_arrows = True
            if self._highlighted_index > 0:
                self._set_highlight(self._highlighted_index - 1)
            return True

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._has_used_arrows and 0 <= self._highlighted_index < len(self._flat_results):
                self.result_selected.emit(self._flat_results[self._highlighted_index])
            else:
                self.search_submitted.emit(self._query)
            return True

        if key == Qt.Key.Key_Escape:
            self.hide()
            return True

        return False

    # --- Internal ---

    def _make_row(self, item: dict) -> QWidget:
        row = _ClickableRow(item, self)
        row.setStyleSheet(_ROW_STYLE)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        name = QLabel(item.get("DisplayName") or item.get("Name", ""))
        name.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; background: transparent;"
            " border: none; text-decoration: none;"
        )
        name.setWordWrap(True)
        name.setMinimumWidth(0)
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(name, 1)

        type_badge = QLabel(get_display_type(item))
        type_badge.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px;"
            f" background-color: {PRIMARY}; border-radius: 3px;"
            f" padding: 2px 6px; border: none; text-decoration: none;"
        )
        type_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(type_badge)

        return row

    def _build_empty_state(self, query: str):
        """Build the 'no results — add to wiki' empty state with category picker."""
        msg = QLabel(f'Can\'t find "{query}"?')
        msg.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; padding: 10px 10px 2px 10px;"
            " background: transparent;"
        )
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inner_layout.addWidget(msg)

        prompt = QLabel("Add it to the wiki")
        prompt.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; padding: 2px 10px 8px 10px;"
            " background: transparent;"
        )
        prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inner_layout.addWidget(prompt)

        # Category picker
        for section_name, entries in CREATABLE_CATEGORIES:
            header = QLabel(section_name)
            header.setStyleSheet(_CATEGORY_STYLE)
            self._inner_layout.addWidget(header)

            for display_name, url_path in entries:
                row = _CategoryRow(url_path, self)
                row.setStyleSheet(_ROW_STYLE)
                layout = QHBoxLayout(row)
                layout.setContentsMargins(8, 2, 8, 2)
                layout.setSpacing(0)

                lbl = QLabel(display_name)
                lbl.setStyleSheet(
                    f"color: {TEXT}; font-size: 12px; background: transparent;"
                    " border: none;"
                )
                lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                layout.addWidget(lbl, 1)

                self._inner_layout.addWidget(row)

    def _set_highlight(self, index: int):
        # Remove old highlight
        if 0 <= self._highlighted_index < len(self._row_widgets):
            self._row_widgets[self._highlighted_index].setStyleSheet(_ROW_STYLE)
        self._highlighted_index = index
        if 0 <= index < len(self._row_widgets):
            self._row_widgets[index].setStyleSheet(_ROW_HIGHLIGHT_STYLE)
            self._row_widgets[index].ensurePolished()
            # Scroll into view
            self._scroll.ensureWidgetVisible(self._row_widgets[index])
