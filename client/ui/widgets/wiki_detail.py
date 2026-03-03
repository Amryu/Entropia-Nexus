"""Reusable components for wiki entity detail pages (Wikipedia-style infobox layout)."""

from __future__ import annotations

import re
import threading
import webbrowser

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextBrowser, QSizePolicy, QFrame, QApplication,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt, QEvent, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QLinearGradient, QColor

import requests

from ..theme import (
    PRIMARY, SECONDARY, BORDER, TEXT, TEXT_MUTED, ACCENT,
    HOVER, DAMAGE_COLORS, TIER1_BLUE_START, TIER1_BLUE_END, SUCCESS,
)
from ...data.wiki_columns import _DAMAGE_TYPES, deep_get
from .fancy_table import FancyTable, ColumnDef

# Defense types share the same 9 names as damage types
_DEFENSE_TYPES = _DAMAGE_TYPES


# ---------------------------------------------------------------------------
# Shared table / label helpers (used by weapon, blueprint, and other detail views)
# ---------------------------------------------------------------------------

_TABLE_MAX_HEIGHT = 400
_TABLE_ROW_HEIGHT = 32


def section_title_label(text: str) -> QLabel:
    """Uppercase section title matching the website's .section-title."""
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color: {TEXT_MUTED}; font-size: 13px; font-weight: 600;"
        f" letter-spacing: 0.5px; background: transparent;"
        f" margin: 0 0 8px 0; padding: 0;"
    )
    return lbl


def no_data_label(text: str) -> QLabel:
    """Centered muted label for empty-data states."""
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"color: {TEXT_MUTED}; font-size: 14px;"
        f" background-color: {PRIMARY}; border-radius: 6px;"
        f" padding: 16px;"
    )
    return lbl


# --- Exchange link helpers (mirrors TYPE_ID_OFFSETS from itemTypes.js) ---

_TYPE_ID_OFFSETS = {
    "Material": 1_000_000, "Weapon": 2_000_000, "Armor": 3_000_000,
    "Tool": 4_000_000, "MedicalTool": 4_100_000, "MiscTool": 4_200_000,
    "Refiner": 4_300_000, "Scanner": 4_400_000, "Finder": 4_500_000,
    "Excavator": 4_600_000, "BlueprintBook": 4_700_000,
    "MedicalChip": 4_800_000, "TeleportationChip": 4_810_000,
    "EffectChip": 4_820_000, "Attachment": 5_000_000,
    "WeaponAmplifier": 5_100_000, "WeaponVisionAttachment": 5_200_000,
    "Absorber": 5_300_000, "FinderAmplifier": 5_400_000,
    "ArmorPlating": 5_500_000, "Enhancer": 5_600_000,
    "MindforceImplant": 5_700_000, "Blueprint": 6_000_000,
    "Vehicle": 7_000_000, "Clothing": 8_000_000,
    "Furniture": 9_100_000, "Decoration": 9_200_000,
    "StorageContainer": 9_300_000, "Sign": 9_400_000,
    "Consumable": 10_000_000, "Capsule": 10_100_000,
    "Pet": 11_000_000, "Strongbox": 12_000_000, "ArmorSet": 13_000_000,
}

# Map page_type_id (used by detail views) → TYPE_ID_OFFSETS key
PAGE_TYPE_TO_ENTITY: dict[str, str] = {
    "weapons": "Weapon", "materials": "Material", "blueprints": "Blueprint",
    "clothing": "Clothing", "vehicles": "Vehicle", "pets": "Pet",
    "armorsets": "ArmorSet", "strongboxes": "Strongbox",
    "amplifiers": "WeaponAmplifier", "armor": "Armor",
    # Tools
    "finders": "Finder", "excavators": "Excavator", "scanners": "Scanner",
    "refiners": "Refiner", "misctools": "MiscTool",
    "teleportationchips": "TeleportationChip",
    # Medical
    "medicaltools": "MedicalTool", "medicalchips": "MedicalChip",
    "effectchips": "EffectChip",
    # Generic
    "enhancers": "Enhancer", "stimulants": "Consumable",
    "capsules": "Capsule", "furniture": "Furniture",
    "storagecontainers": "StorageContainer", "signs": "Sign",
    "sightsscopes": "WeaponVisionAttachment", "absorbers": "Absorber",
    "finderamplifiers": "FinderAmplifier", "armorplatings": "ArmorPlating",
    "mindforceimplants": "MindforceImplant",
}


def exchange_url(item: dict, base_url: str, entity_type: str = "") -> str | None:
    """Build the exchange detail URL for an item, or None if type is unknown.

    *entity_type* overrides the item's own ``Type`` field when provided.
    """
    item_id = item.get("Id")
    item_type = entity_type or item.get("Type", "")
    offset = _TYPE_ID_OFFSETS.get(item_type)
    if item_id is not None and offset is not None:
        return f"{base_url}/market/exchange/listings/{item_id + offset}"
    return None


def _exchange_link_label(text: str, url: str) -> QPushButton:
    """Centered accent-colored link button that opens *url* in the browser."""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background: transparent; border: none;"
        f" color: {ACCENT}; font-size: 13px; padding: 4px 0px; }}"
        f"QPushButton:hover {{ color: {ACCENT}; }}"
    )
    btn.clicked.connect(lambda: webbrowser.open(url))
    return btn


def make_compact_table(headers: list[str], rows: list[list[str]]) -> QTableWidget:
    """Styled read-only table matching the website's FancyTable compact style."""
    table = QTableWidget(len(rows), len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.setShowGrid(False)
    table.setAlternatingRowColors(True)
    table.setStyleSheet(f"""
        QTableWidget {{
            background-color: {SECONDARY};
            alternate-background-color: {PRIMARY};
            border: 1px solid {BORDER};
            border-radius: 6px;
            font-size: 13px;
            color: {TEXT};
        }}
        QTableWidget::item {{
            padding: 4px 10px;
            border-bottom: 1px solid {BORDER};
            border-left: 2px solid transparent;
        }}
        QTableWidget::item:hover {{
            background-color: rgba(96, 176, 255, 0.15);
            border-left: 2px solid {ACCENT};
        }}
        QHeaderView::section {{
            background-color: {HOVER};
            color: {TEXT_MUTED};
            border: none;
            border-right: 1px solid {BORDER};
            border-bottom: 1px solid {BORDER};
            padding: 6px 10px;
            font-weight: 600;
            font-size: 11px;
        }}
    """)

    for r, row_data in enumerate(rows):
        for c, cell_text in enumerate(row_data):
            table.setItem(r, c, QTableWidgetItem(str(cell_text)))

    # Column sizing: first column stretches, others fit content
    header = table.horizontalHeader()
    header.setStretchLastSection(True)
    if len(headers) > 1:
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(headers)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
    else:
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

    for r in range(len(rows)):
        table.setRowHeight(r, _TABLE_ROW_HEIGHT)

    # Size to fit: header + rows + small border allowance
    content_height = _TABLE_ROW_HEIGHT + len(rows) * _TABLE_ROW_HEIGHT + 4
    table.setFixedHeight(min(content_height, _TABLE_MAX_HEIGHT))

    return table


# Max rows visible in section panel tables before scrolling
_SECTION_TABLE_MAX_ROWS = 12


def make_section_table(
    columns: list[ColumnDef],
    data: list[dict],
    *,
    max_visible_rows: int = _SECTION_TABLE_MAX_ROWS,
    searchable: bool = True,
    default_sort: tuple[str, str] | None = None,
) -> FancyTable:
    """Create a FancyTable sized for use inside a DataSection panel.

    Provides sorting, filtering, and bounded height — replaces
    make_compact_table() for new section panel tables.
    """
    table = FancyTable(
        columns,
        sortable=True,
        searchable=searchable,
        default_sort=default_sort,
        max_visible_rows=max_visible_rows,
        show_toolbar=False,
        compact_threshold=99,  # disable compact mode in embedded tables
    )
    table.set_data(data)
    return table


def build_acquisition_content(
    data: dict,
    *,
    exchange_link: str | None = None,
    on_navigate=None,
) -> QWidget:
    """Build the acquisition panel content from API data.

    Shared by all entity detail views (weapons, blueprints, etc.).
    ``exchange_link`` — full URL to the exchange item page (shown as
    a "create sell order" prompt when there is no acquisition data).
    ``on_navigate`` — optional callback(dict) for entity navigation.
    """
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(16)

    has_any = False

    # --- Vendor Offers ---
    vendor_offers = data.get("VendorOffers") or []
    if vendor_offers:
        has_any = True
        layout.addWidget(section_title_label("Vendor"))
        flat = []
        for offer in vendor_offers:
            value = deep_get(offer, "Item", "Properties", "Economy", "Value")
            flat.append({
                "name": deep_get(offer, "Vendor", "Name") or "",
                "price": value,
                "planet": deep_get(offer, "Vendor", "Planet", "Name") or "",
                "limited": "Yes" if offer.get("IsLimited") else "No",
            })
        table = make_section_table(
            [
                ColumnDef("name", "Name", main=True),
                ColumnDef("price", "Price", format=lambda v: f"{v} PED" if v is not None else ""),
                ColumnDef("planet", "Planet"),
                ColumnDef("limited", "Limited"),
            ],
            flat,
        )
        if on_navigate:
            table.row_activated.connect(
                lambda row, _idx: on_navigate(
                    {"Name": row.get("name", ""), "Type": "Vendor"}
                )
            )
        layout.addWidget(table)

    # --- Looted ---
    loots = data.get("Loots") or []
    if loots:
        has_any = True
        layout.addWidget(section_title_label("Looted"))
        flat = []
        for loot in loots:
            flat.append({
                "mob": deep_get(loot, "Mob", "Name") or "",
                "planet": deep_get(loot, "Mob", "Planet", "Name") or "",
                "maturity": deep_get(loot, "Maturity", "Name") or "",
                "frequency": loot.get("Frequency") or "",
            })
        table = make_section_table(
            [
                ColumnDef("mob", "Mob", main=True),
                ColumnDef("planet", "Planet"),
                ColumnDef("maturity", "Maturity"),
                ColumnDef("frequency", "Frequency"),
            ],
            flat,
        )
        if on_navigate:
            table.row_activated.connect(
                lambda row, _idx: on_navigate(
                    {"Name": row.get("mob", ""), "Type": "Mob"}
                )
            )
        layout.addWidget(table)

    # --- Shop Listings (Market) ---
    shop_listings = data.get("ShopListings") or []
    if shop_listings:
        has_any = True
        layout.addWidget(section_title_label("Market"))
        flat = []
        for listing in shop_listings:
            markup = listing.get("Markup")
            qty = listing.get("StackSize")
            flat.append({
                "shop": deep_get(listing, "Shop", "Name") or "",
                "markup": markup,
                "qty": qty,
                "planet": deep_get(listing, "Shop", "Planet", "Name") or "",
            })
        layout.addWidget(make_section_table(
            [
                ColumnDef("shop", "Shop", main=True),
                ColumnDef("markup", "Markup", format=lambda v: f"{v:.2f}%" if v is not None else ""),
                ColumnDef("qty", "Qty", format=lambda v: str(v) if v is not None else ""),
                ColumnDef("planet", "Planet"),
            ],
            flat,
        ))

    # --- Crafted (Blueprints) ---
    blueprints = data.get("Blueprints") or []
    if blueprints:
        has_any = True
        layout.addWidget(section_title_label("Crafted"))
        flat = []
        for bp in blueprints:
            flat.append({
                "blueprint": bp.get("Name", ""),
                "level": deep_get(bp, "Properties", "Level"),
                "profession": deep_get(bp, "Profession", "Name") or "",
            })
        table = make_section_table(
            [
                ColumnDef("blueprint", "Blueprint", main=True),
                ColumnDef("level", "Level", format=lambda v: str(v) if v is not None else ""),
                ColumnDef("profession", "Profession"),
            ],
            flat,
        )
        if on_navigate:
            table.row_activated.connect(
                lambda row, _idx: on_navigate(
                    {"Name": row.get("blueprint", ""), "Type": "Blueprint"}
                )
            )
        layout.addWidget(table)

    # --- Blueprint Discovery ---
    bp_drops = data.get("BlueprintDrops") or []
    if bp_drops:
        has_any = True
        layout.addWidget(section_title_label("Blueprint Discovery"))
        flat = []
        for bp in bp_drops:
            flat.append({
                "name": bp.get("Name", ""),
                "level": deep_get(bp, "Properties", "Level"),
            })
        table = make_section_table(
            [
                ColumnDef("name", "Name", main=True),
                ColumnDef("level", "Level", format=lambda v: str(v) if v is not None else ""),
            ],
            flat,
        )
        if on_navigate:
            table.row_activated.connect(
                lambda row, _idx: on_navigate(
                    {"Name": row.get("name", ""), "Type": "Blueprint"}
                )
            )
        layout.addWidget(table)

    if not has_any:
        layout.addWidget(
            no_data_label("No acquisition data available for this item.")
        )
        if exchange_link:
            layout.addWidget(
                _exchange_link_label("Create a sell order on the Exchange", exchange_link)
            )

    return container


def build_usage_content(
    data: dict,
    *,
    exchange_link: str | None = None,
    on_navigate=None,
) -> QWidget:
    """Build the usage panel content from API data.

    Shared by all entity detail views — shows where this item is used
    (blueprints, refining, missions, vendor currency).
    ``on_navigate`` — optional callback(dict) for entity navigation.
    """
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(16)

    has_any = False

    # --- Blueprints (this item is used as material) ---
    blueprints = data.get("Blueprints") or []
    if blueprints:
        has_any = True
        layout.addWidget(section_title_label("Blueprints"))
        flat = []
        for bp in blueprints:
            flat.append({
                "blueprint": bp.get("Name", ""),
                "type": deep_get(bp, "Properties", "Type") or "",
                "amount": bp.get("MaterialAmount"),
            })
        table = make_section_table(
            [
                ColumnDef("blueprint", "Blueprint", main=True),
                ColumnDef("type", "Type"),
                ColumnDef("amount", "Amount", format=lambda v: str(v) if v is not None else ""),
            ],
            flat,
        )
        if on_navigate:
            table.row_activated.connect(
                lambda row, _idx: on_navigate(
                    {"Name": row.get("blueprint", ""), "Type": "Blueprint"}
                )
            )
        layout.addWidget(table)

    # --- Refining Recipes (this item is an ingredient) ---
    recipes = data.get("RefiningRecipes") or []
    if recipes:
        has_any = True
        layout.addWidget(section_title_label("Refining Recipes"))
        flat = []
        for recipe in recipes:
            ingredients = recipe.get("Ingredients") or []
            ing_parts = []
            for ing in ingredients:
                ing_name = deep_get(ing, "Item", "Name") or "?"
                ing_amount = ing.get("Amount")
                if ing_amount is not None:
                    ing_parts.append(f"{ing_name} x{ing_amount}")
                else:
                    ing_parts.append(ing_name)
            flat.append({
                "product": deep_get(recipe, "Product", "Name") or "",
                "amount": recipe.get("Amount"),
                "ingredients": ", ".join(ing_parts) if ing_parts else "",
            })
        layout.addWidget(make_section_table(
            [
                ColumnDef("product", "Product", main=True),
                ColumnDef("amount", "Amount", format=lambda v: str(v) if v is not None else ""),
                ColumnDef("ingredients", "Ingredients"),
            ],
            flat,
        ))

    # --- Missions (this item is a hand-in) ---
    missions = data.get("Missions") or []
    if missions:
        has_any = True
        layout.addWidget(section_title_label("Missions"))
        flat = []
        for mission in missions:
            flat.append({
                "mission": mission.get("Name", ""),
                "type": mission.get("Type", ""),
                "location": mission.get("Location", ""),
                "handins": mission.get("HandIns"),
            })
        table = make_section_table(
            [
                ColumnDef("mission", "Mission", main=True),
                ColumnDef("type", "Type"),
                ColumnDef("location", "Location"),
                ColumnDef("handins", "Hand-ins", format=lambda v: str(v) if v is not None else ""),
            ],
            flat,
        )
        if on_navigate:
            table.row_activated.connect(
                lambda row, _idx: on_navigate(
                    {"Name": row.get("mission", ""), "Type": "Mission"}
                )
            )
        layout.addWidget(table)

    # --- Vendor Currency (this item is accepted as payment) ---
    vendor_offers = data.get("VendorOffers") or []
    vendor_flat = []
    for offer in vendor_offers:
        prices = offer.get("Prices") or []
        if not prices:
            continue
        v_name = deep_get(offer, "Vendor", "Name") or ""
        v_planet = deep_get(offer, "Vendor", "Planet", "Name") or ""
        item_name = deep_get(offer, "Item", "Name") or ""
        for price in prices:
            vendor_flat.append({
                "vendor": v_name,
                "planet": v_planet,
                "item": item_name,
                "amount": price.get("Amount"),
            })
    if vendor_flat:
        has_any = True
        layout.addWidget(section_title_label("Vendor Currency"))
        table = make_section_table(
            [
                ColumnDef("vendor", "Vendor", main=True),
                ColumnDef("planet", "Planet"),
                ColumnDef("item", "Item"),
                ColumnDef("amount", "Amount", format=lambda v: str(v) if v is not None else ""),
            ],
            vendor_flat,
        )
        if on_navigate:
            table.row_activated.connect(
                lambda row, _idx: on_navigate(
                    {"Name": row.get("vendor", ""), "Type": "Vendor"}
                )
            )
        layout.addWidget(table)

    if not has_any:
        layout.addWidget(
            no_data_label("No usage data available for this item.")
        )
        if exchange_link:
            layout.addWidget(
                _exchange_link_label("Create a buy order on the Exchange", exchange_link)
            )

    return container


# ---------------------------------------------------------------------------
# StatRow — single key-value pair
# ---------------------------------------------------------------------------

class StatRow(QWidget):
    """A single label: value stat row, matching the web frontend's .stat-row."""

    clicked = pyqtSignal()
    entity_clicked = pyqtSignal(dict)

    def __init__(
        self,
        label: str,
        value: str,
        *,
        highlight: bool = False,
        muted_value: bool = False,
        toggleable: bool = False,
        indent: bool = False,
        label_color: str | None = None,
        entity: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._entity = entity
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        if indent:
            layout.setContentsMargins(12, 4, 0, 4)

        lc = label_color or TEXT_MUTED
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {lc}; font-size: 13px; background: transparent;"
        )
        layout.addWidget(lbl)

        layout.addStretch()

        if entity:
            value_color = ACCENT
        elif highlight:
            value_color = SUCCESS
        elif muted_value:
            value_color = TEXT_MUTED
        else:
            value_color = TEXT

        self._value_label = QLabel(value)
        self._value_label.setStyleSheet(
            f"color: {value_color}; font-size: 13px; font-weight: 500;"
            " background: transparent;"
        )
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._value_label)

        if entity:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setStyleSheet(
                f"StatRow {{ border-radius: 4px; padding: 0 6px; }}"
                f"StatRow:hover {{ background-color: {HOVER}; }}"
            )
        elif toggleable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setStyleSheet(
                f"StatRow {{ border-radius: 4px; padding: 0 6px; }}"
                f"StatRow:hover {{ background-color: {HOVER}; }}"
            )

    def set_value(self, text: str):
        self._value_label.setText(text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            if self._entity:
                self.entity_clicked.emit(self._entity)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# WaypointCopyButton — click-to-copy waypoint matching web WaypointCopyButton
# ---------------------------------------------------------------------------

_WP_COPIED_MS = 2000

class WaypointCopyButton(QPushButton):
    """Button that displays a waypoint and copies it to clipboard on click.

    Matches the web's WaypointCopyButton.svelte — shows `/wp [Planet, X, Y, Z, Name]`,
    copies on click, and flashes green "Copied!" feedback for 2 seconds.
    """

    _STYLE_NORMAL = (
        f"WaypointCopyButton {{"
        f"  background-color: {PRIMARY};"
        f"  border: 1px solid {BORDER};"
        f"  border-radius: 4px;"
        f"  color: {TEXT};"
        f"  font-family: monospace;"
        f"  font-size: 12px;"
        f"  padding: 6px 10px;"
        f"  text-align: left;"
        f"}}"
        f"WaypointCopyButton:hover {{"
        f"  background-color: {ACCENT};"
        f"  border-color: {ACCENT};"
        f"  color: white;"
        f"}}"
    )

    _STYLE_COPIED = (
        f"WaypointCopyButton {{"
        f"  background-color: {SUCCESS};"
        f"  border: 1px solid {SUCCESS};"
        f"  border-radius: 4px;"
        f"  color: white;"
        f"  font-family: monospace;"
        f"  font-size: 12px;"
        f"  padding: 6px 10px;"
        f"  text-align: left;"
        f"}}"
    )

    def __init__(self, planet: str, coords: dict, name: str, parent=None):
        super().__init__(parent)
        lon = coords.get("Longitude")
        lat = coords.get("Latitude")
        alt = coords.get("Altitude", 100)
        self._waypoint = f"[{planet}, {lon}, {lat}, {alt}, {name}]"
        self.setText(f"/wp {self._waypoint}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(self._STYLE_NORMAL)
        self.clicked.connect(self._copy)

    def _copy(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(f"/wp {self._waypoint}")
        self.setText("\u2713 Copied!")
        self.setStyleSheet(self._STYLE_COPIED)
        QTimer.singleShot(_WP_COPIED_MS, self._reset)

    def _reset(self):
        self.setText(f"/wp {self._waypoint}")
        self.setStyleSheet(self._STYLE_NORMAL)


# ---------------------------------------------------------------------------
# InfoboxSection — titled group of stat rows
# ---------------------------------------------------------------------------

class InfoboxSection(QWidget):
    """A titled section inside the infobox, matching .stats-section."""

    def __init__(self, title: str | None = None, *, tier1: bool = False, parent=None):
        super().__init__(parent)
        self._tier1 = tier1
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(0)

        if not tier1:
            self.setStyleSheet(
                f"InfoboxSection {{"
                f"  background-color: {PRIMARY};"
                f"  border-radius: 6px;"
                f"}}"
            )

        if title:
            title_label = QLabel(title.upper())
            title_label.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 600;"
                " letter-spacing: 0.5px; background: transparent;"
                " margin-bottom: 10px;"
            )
            self._layout.addWidget(title_label)

    def add_row(self, row: StatRow):
        self._layout.addWidget(row)

    def add_widget(self, widget: QWidget):
        self._layout.addWidget(widget)

    def paintEvent(self, event):
        """Draw gradient background for tier-1 sections."""
        if self._tier1:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            gradient = QLinearGradient(0, 0, self.width(), self.height())
            gradient.setColorAt(0.0, QColor(TIER1_BLUE_START))
            gradient.setColorAt(1.0, QColor(TIER1_BLUE_END))
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect(), 6, 6)
            painter.end()
        else:
            super().paintEvent(event)


# ---------------------------------------------------------------------------
# Tier1StatRow — large-value stat row for the highlighted tier-1 section
# ---------------------------------------------------------------------------

class Tier1StatRow(QWidget):
    """Prominent stat row for the tier-1 (gradient) section."""

    def __init__(self, label: str, value: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background-color: rgba(255, 255, 255, 0.1);"
            f" border-radius: 4px;"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            "color: rgba(255, 255, 255, 0.9); font-size: 13px;"
            " font-weight: 500; background: transparent;"
        )
        layout.addWidget(lbl)

        layout.addStretch()

        self._value_label = QLabel(value)
        self._value_label.setStyleSheet(
            "color: #e8f4ff; font-size: 18px; font-weight: 700;"
            " background: transparent;"
        )
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._value_label)



# ---------------------------------------------------------------------------
# MobDamageGridWidget — horizontal bar display for mob damage composition
# ---------------------------------------------------------------------------

_BAR_HEIGHT = 8

class MobDamageGridWidget(QWidget):
    """Horizontal-bar damage display matching the website's MobDamageGrid.

    Renders one group: an optional label, then one row per non-zero damage
    type with [TypeName] [===bar===] [value%].
    """

    def __init__(self, damage_spread: dict, label: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if label:
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600;"
                " background: transparent; letter-spacing: 0.5px;"
            )
            layout.addWidget(lbl)

        active = [(dt, damage_spread.get(dt) or 0)
                  for dt in _DAMAGE_TYPES if (damage_spread.get(dt) or 0) > 0]

        if not active:
            muted = QLabel("No damage data")
            muted.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 12px;"
                " font-style: italic; background: transparent;"
            )
            layout.addWidget(muted)
            return

        max_val = max(v for _, v in active)

        for dtype, val in active:
            color = DAMAGE_COLORS.get(dtype, TEXT_MUTED)
            pct = (val / max_val * 100) if max_val > 0 else 0

            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)

            type_lbl = QLabel(dtype)
            type_lbl.setFixedWidth(70)
            type_lbl.setStyleSheet(
                f"color: {color}; font-size: 11px; font-weight: 500;"
                " background: transparent;"
            )
            rl.addWidget(type_lbl)

            # Bar container + filled bar
            bar_container = QWidget()
            bar_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            bar_container.setFixedHeight(_BAR_HEIGHT)
            bar_container.setStyleSheet(
                f"background-color: rgba(0, 0, 0, 0.2);"
                f" border-radius: {_BAR_HEIGHT // 2}px;"
            )
            bar_layout = QHBoxLayout(bar_container)
            bar_layout.setContentsMargins(0, 0, 0, 0)
            bar_layout.setSpacing(0)

            bar_fill = QWidget()
            bar_fill.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            bar_fill.setFixedHeight(_BAR_HEIGHT)
            bar_fill.setStyleSheet(
                f"background-color: {color};"
                f" border-radius: {_BAR_HEIGHT // 2}px;"
            )
            # Use stretch factors to represent percentage
            fill_stretch = max(int(pct), 1)
            empty_stretch = max(100 - fill_stretch, 0)
            bar_layout.addWidget(bar_fill, fill_stretch)
            if empty_stretch > 0:
                spacer = QWidget()
                spacer.setStyleSheet("background: transparent;")
                bar_layout.addWidget(spacer, empty_stretch)

            rl.addWidget(bar_container, 1)

            val_lbl = QLabel(f"{val:.1f}%")
            val_lbl.setFixedWidth(45)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px;"
                " background: transparent;"
            )
            rl.addWidget(val_lbl)

            layout.addWidget(row)


# ---------------------------------------------------------------------------
# DefenseBreakdownWidget — colored stat rows per defense type
# ---------------------------------------------------------------------------

class DefenseBreakdownWidget(QWidget):
    """Defense breakdown using colored stat rows for each non-zero type."""

    def __init__(self, defense: dict | None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if not defense:
            muted = QLabel("No defense data")
            muted.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 12px;"
                " font-style: italic; background: transparent;"
            )
            layout.addWidget(muted)
            return

        entries = [(dt, defense.get(dt) or 0) for dt in _DEFENSE_TYPES if (defense.get(dt) or 0) > 0]
        if not entries:
            muted = QLabel("No defense")
            muted.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 12px;"
                " font-style: italic; background: transparent;"
            )
            layout.addWidget(muted)
            return

        total = sum(v for _, v in entries)
        layout.addWidget(StatRow("Total", f"{total:.1f}"))

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER};")
        layout.addWidget(sep)

        for dtype, val in entries:
            color = DAMAGE_COLORS.get(dtype, TEXT_MUTED)
            layout.addWidget(StatRow(dtype, f"{val:.1f}", label_color=color))


# ---------------------------------------------------------------------------
# ImagePlaceholder — shown while image loads (or if no image)
# ---------------------------------------------------------------------------

class ImagePlaceholder(QLabel):
    """Rounded placeholder with centered abbreviation text."""

    def __init__(self, text: str, size: int = 160, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText(text[:3].upper())
        self.setStyleSheet(
            f"background-color: {PRIMARY}; border-radius: 8px;"
            f" color: {TEXT_MUTED}; font-size: 24px; font-weight: bold;"
            f" border: 1px solid {BORDER};"
        )


# ---------------------------------------------------------------------------
# DataSection — collapsible panel for the article area
# ---------------------------------------------------------------------------

class DataSection(QWidget):
    """Collapsible content section matching the website's DataSection.svelte."""

    def __init__(self, title: str, *, subtitle: str = "", expanded: bool = True, parent=None):
        super().__init__(parent)
        self._expanded = expanded
        self._subtitle_text = subtitle
        self._title_text = title

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._frame = QFrame()
        self._frame.setStyleSheet(
            f"QFrame#dataSection {{"
            f"  background-color: {SECONDARY};"
            f"  border: 1px solid {BORDER};"
            f"  border-radius: 8px;"
            f"}}"
        )
        self._frame.setObjectName("dataSection")
        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # --- Header (clickable) ---
        self._header = QWidget()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setObjectName("dataSectionHeader")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(8)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(
            f"color: {TEXT}; font-size: 16px; font-weight: 600;"
            " background: transparent;"
        )
        header_layout.addWidget(self._title_label)

        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;"
        )
        header_layout.addWidget(self._subtitle_label, 1)

        self._chevron = QLabel("\u25be")  # ▾
        self._chevron.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 14px; background: transparent;"
        )
        self._chevron.setFixedWidth(20)
        self._chevron.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self._chevron)

        self._header.mousePressEvent = lambda e: self.toggle()
        frame_layout.addWidget(self._header)

        # --- Separator (visible when expanded) ---
        self._separator = QFrame()
        self._separator.setFrameShape(QFrame.Shape.NoFrame)
        self._separator.setFixedHeight(1)
        self._separator.setStyleSheet(f"background-color: {BORDER};")
        frame_layout.addWidget(self._separator)

        # --- Content ---
        self._content = QWidget()
        self._content.setObjectName("dataSectionContent")
        self._content.setStyleSheet(
            "#dataSectionContent { background: transparent; }"
        )
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(16, 16, 16, 16)
        self._content_layout.setSpacing(12)
        frame_layout.addWidget(self._content)

        outer.addWidget(self._frame)

        self._update_state()

    def toggle(self):
        self._expanded = not self._expanded
        self._update_state()

    def set_subtitle(self, text: str):
        self._subtitle_text = text
        self._subtitle_label.setText(text)

    def set_loading(self):
        """Show a loading placeholder in the content area."""
        loading = QLabel("Loading...")
        loading.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;"
        )
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._content_layout.addWidget(loading)

    def set_content(self, widget: QWidget):
        """Replace content with the given widget."""
        # Clear existing content
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._content_layout.addWidget(widget)

    def add_content_widget(self, widget: QWidget):
        """Add a widget to the content area."""
        self._content_layout.addWidget(widget)

    def _update_state(self):
        self._content.setVisible(self._expanded)
        self._separator.setVisible(self._expanded)
        self._chevron.setText("\u25be" if self._expanded else "\u25b8")  # ▾ / ▸
        self._subtitle_label.setVisible(not self._expanded and bool(self._subtitle_text))
        # Header hover style
        if self._expanded:
            self._header.setStyleSheet(
                f"#dataSectionHeader {{ background: transparent; }}"
                f"#dataSectionHeader:hover {{ background-color: {HOVER}; }}"
            )
        else:
            self._header.setStyleSheet(
                f"#dataSectionHeader {{ background: transparent; }}"
                f"#dataSectionHeader:hover {{ background-color: {HOVER}; }}"
            )


# ---------------------------------------------------------------------------
# WikiDetailView — base class for entity detail pages
# ---------------------------------------------------------------------------

class WikiDetailView(QWidget):
    """Single-column detail page: infobox panel at top, article below.

    Subclasses should call ``_build(item)`` to populate the layout.
    """

    _image_loaded = pyqtSignal(bytes)  # raw image bytes from background thread
    entity_navigate = pyqtSignal(dict)  # {"Name": str, "Type": str}

    IMAGE_SIZE = 100
    TIER1_WIDTH = 220
    SECTION_MAX_WIDTH = 400

    def __init__(self, item: dict, *, nexus_base_url: str = "", data_client=None, parent=None):
        super().__init__(parent)
        self._item = item
        self._nexus_base_url = nexus_base_url
        self._data_client = data_client
        self._image_loaded.connect(self._on_image_loaded)

        # Main vertical layout: infobox panel → description → article sections
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(12)

        # --- Infobox panel (full width) ---
        self._infobox = QWidget()
        self._infobox.setStyleSheet(
            f"#wikiInfobox {{"
            f"  background-color: {SECONDARY};"
            f"  border: 1px solid {BORDER};"
            f"  border-radius: 8px;"
            f"}}"
        )
        self._infobox.setObjectName("wikiInfobox")

        self._infobox_layout = QVBoxLayout(self._infobox)
        self._infobox_layout.setContentsMargins(16, 16, 16, 16)
        self._infobox_layout.setSpacing(12)

        # Header row: image | title+badges | stretch | tier1
        self._header_row = QHBoxLayout()
        self._header_row.setSpacing(16)
        self._infobox_layout.addLayout(self._header_row)

        # Sections row: stat sections laid out horizontally, left-aligned
        self._sections_row = QHBoxLayout()
        self._sections_row.setSpacing(8)
        self._sections_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._infobox_layout.addLayout(self._sections_row)

        self._main_layout.addWidget(self._infobox)

        # --- Description browser (below infobox) ---
        self._description_browser = QTextBrowser()
        self._description_browser.setOpenExternalLinks(True)
        self._description_browser.setStyleSheet(
            f"QTextBrowser {{"
            f"  background-color: {SECONDARY};"
            f"  color: {TEXT};"
            f"  font-size: 13px;"
            f"  border: 1px solid {BORDER};"
            f"  border-radius: 8px;"
            f"  padding: 8px 12px;"
            f"}}"
            f"QTextBrowser a {{ color: {ACCENT}; }}"
        )
        self._description_browser.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._description_browser.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        # Prevent mouse-wheel scrolling inside the description
        self._description_browser.viewport().installEventFilter(self)
        self._description_browser.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self._main_layout.addWidget(self._description_browser)

        # Article sections will be appended below by subclasses

    # --- Infobox header helpers ---

    def _add_image_placeholder(self, text: str):
        """Add image placeholder to the infobox header row (left)."""
        self._image_label = ImagePlaceholder(text, self.IMAGE_SIZE)
        self._header_row.addWidget(
            self._image_label, 0, Qt.AlignmentFlag.AlignTop
        )

    def _add_infobox_title(self, name: str, subtitle_widgets: list[QWidget] | None = None):
        """Add name + subtitle to the infobox header row (left-aligned)."""
        title_area = QWidget()
        title_area.setStyleSheet("background: transparent;")
        tl = QVBoxLayout(title_area)
        tl.setContentsMargins(0, 4, 0, 0)
        tl.setSpacing(6)

        title = QLabel(name)
        title.setWordWrap(True)
        title.setStyleSheet(
            f"color: {TEXT}; font-size: 18px; font-weight: 600;"
            " background: transparent; border: none;"
        )
        tl.addWidget(title)

        if subtitle_widgets:
            sub_row = QWidget()
            sub_row.setStyleSheet("background: transparent; border: none;")
            sr_layout = QHBoxLayout(sub_row)
            sr_layout.setContentsMargins(0, 0, 0, 0)
            sr_layout.setSpacing(8)
            for w in subtitle_widgets:
                sr_layout.addWidget(w, 0, Qt.AlignmentFlag.AlignVCenter)
            sr_layout.addStretch()
            tl.addWidget(sub_row)

        tl.addStretch()
        self._header_row.addWidget(title_area, 0, Qt.AlignmentFlag.AlignTop)
        self._header_row.addStretch()

    def _make_badge(self, text: str) -> QLabel:
        """Create a small accent-colored badge label."""
        badge = QLabel(text.upper())
        badge.setStyleSheet(
            f"background-color: {ACCENT}; color: white;"
            f" font-size: 10px; font-weight: 600;"
            f" border-radius: 4px; padding: 2px 8px;"
        )
        return badge

    def _make_subtitle_text(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px;"
            " background: transparent; border: none;"
        )
        return lbl

    def set_edit_url(self, url: str):
        """Add an edit icon button to the header row, positioned before Tier1."""
        import webbrowser
        from PyQt6.QtGui import QIcon
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QByteArray

        _EDIT_SVG = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"'
            b' viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"'
            b' stroke-linecap="round" stroke-linejoin="round">'
            b'<path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>'
            b'<path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>'
            b'</svg>'
        )

        renderer = QSvgRenderer(QByteArray(_EDIT_SVG))
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        btn = QPushButton()
        btn.setIcon(QIcon(pixmap))
        btn.setFixedSize(32, 32)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Edit on website")
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {SECONDARY}; border: 1px solid {BORDER};"
            f" border-radius: 4px; padding: 4px; }}"
            f"QPushButton:hover {{ background-color: {HOVER}; }}"
        )
        btn.clicked.connect(lambda: webbrowser.open(url))

        # Insert after the stretch spacer, before any Tier1 sections
        insert_idx = self._header_row.count()
        for i in range(self._header_row.count()):
            item = self._header_row.itemAt(i)
            if item and item.spacerItem():
                insert_idx = i + 1
                break
        self._header_row.insertWidget(insert_idx, btn, 0, Qt.AlignmentFlag.AlignTop)

    # --- Section helpers ---

    def _add_section(self, section: InfoboxSection):
        """Add section: tier1 goes in header row (right), others in sections row."""
        if section._tier1:
            section.setMinimumWidth(self.TIER1_WIDTH)
            section.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
            self._header_row.addWidget(section, 0, Qt.AlignmentFlag.AlignTop)
        else:
            section.setMaximumWidth(self.SECTION_MAX_WIDTH)
            self._sections_row.addWidget(section, 1, Qt.AlignmentFlag.AlignTop)

    def _add_infobox_stretch(self):
        """No-op — horizontal sections row doesn't need a bottom stretch."""
        pass

    def _linked_stat_row(self, label: str, value: str, entity_type: str,
                         **kwargs) -> StatRow:
        """Create a StatRow linked to entity navigation if the type is wiki-navigable."""
        from .search_popup import WIKI_PATHS
        if value and entity_type and entity_type in WIKI_PATHS:
            entity = {"Name": value, "Type": entity_type}
            row = StatRow(label, value, entity=entity, **kwargs)
            row.entity_clicked.connect(self.entity_navigate.emit)
            return row
        return StatRow(label, value, **kwargs)

    # --- Article helpers ---

    def _set_article_title(self, title: str):
        """No-op — title is now in the infobox header row."""
        pass

    def _set_description_html(self, html: str):
        stripped = html.strip() if html else ""
        # Check for effectively empty HTML (just tags, no visible text)
        text_only = re.sub(r"<[^>]+>", "", stripped).strip()
        if not text_only:
            self._description_browser.hide()
            return

        self._description_browser.show()
        self._description_browser.setHtml(
            f'<div style="color: {TEXT}; font-size: 13px;">{stripped}</div>'
        )
        # Size exactly to content — no wasted space
        doc = self._description_browser.document()
        doc.setTextWidth(self._description_browser.viewport().width())
        # +20 accounts for QSS padding (8px top + 8px bottom) and border (1px + 1px)
        self._description_browser.setFixedHeight(int(doc.size().height()) + 20)

    def eventFilter(self, obj, event):
        """Block wheel events on the description browser viewport."""
        if obj is self._description_browser.viewport() and event.type() == QEvent.Type.Wheel:
            return True  # consumed — don't scroll
        return super().eventFilter(obj, event)

    def _add_article_section(self, section: QWidget):
        """Add a widget to the bottom of the main layout."""
        self._main_layout.addWidget(section)

    # --- Async image loading ---

    def _load_image_async(self, url: str):
        """Fetch image from URL in a background thread."""
        def fetch():
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200 and resp.content:
                    self._image_loaded.emit(resp.content)
            except Exception:
                pass  # Keep placeholder

        threading.Thread(target=fetch, daemon=True, name="img-load").start()

    def _on_image_loaded(self, data: bytes):
        """Replace image placeholder with the loaded image (main thread)."""
        if not hasattr(self, '_image_label'):
            return
        pm = QPixmap()
        pm.loadFromData(data)
        if pm.isNull():
            return
        scaled = pm.scaled(
            self.IMAGE_SIZE, self.IMAGE_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setText("")
        self._image_label.setStyleSheet(
            f"background-color: {PRIMARY}; border-radius: 8px;"
            f" border: 1px solid {BORDER};"
        )
