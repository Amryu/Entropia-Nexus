"""Categorised search results popup for the title bar search."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal

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
# Constants
# ---------------------------------------------------------------------------

MAX_PER_CATEGORY = 5
MAX_TOTAL = 20

_POPUP_STYLE = f"""
    QWidget#searchPopup {{
        background-color: {SECONDARY};
        border: 1px solid {BORDER};
        border-radius: 4px;
    }}
"""

_CATEGORY_STYLE = (
    f"color: {TEXT_MUTED}; font-size: 11px; font-weight: bold;"
    f" letter-spacing: 0.5px; text-transform: uppercase;"
    f" padding: 8px 12px; background-color: {HOVER};"
    f" border-bottom: 1px solid {BORDER};"
)

_ROW_STYLE = (
    f"padding: 8px 12px; border-bottom: 1px solid {BORDER};"
    f" background-color: transparent;"
)

_ROW_HIGHLIGHT_STYLE = (
    f"padding: 8px 12px; border-bottom: 1px solid {BORDER};"
    f" background-color: {HOVER};"
    f" outline: 2px solid {ACCENT}; outline-offset: -2px;"
)


# ---------------------------------------------------------------------------
# Popup widget
# ---------------------------------------------------------------------------

class SearchResultsPopup(QWidget):
    """Categorised search results dropdown positioned below the search bar."""

    result_selected = pyqtSignal(dict)     # individual result picked
    search_submitted = pyqtSignal(str)     # Enter without arrow selection

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("searchPopup")
        self.setWindowFlags(
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
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

        # Clear previous
        self._flat_results.clear()
        self._row_widgets.clear()
        while self._inner_layout.count():
            item = self._inner_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

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
            empty = QLabel(f'No results for "{query}"')
            empty.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 13px; padding: 16px;"
                " text-align: center; background: transparent;"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._inner_layout.addWidget(empty)

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
        row = QWidget()
        row.setStyleSheet(_ROW_STYLE)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        name = QLabel(item.get("DisplayName") or item.get("Name", ""))
        name.setStyleSheet(f"color: {TEXT}; font-size: 13px; background: transparent;")
        layout.addWidget(name, 1)

        type_badge = QLabel(get_type_name(item.get("Type", "")))
        type_badge.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px;"
            f" background-color: {PRIMARY}; border-radius: 3px;"
            f" padding: 2px 6px;"
        )
        layout.addWidget(type_badge)

        return row

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
