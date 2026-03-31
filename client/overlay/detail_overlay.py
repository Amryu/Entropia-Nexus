"""Compact detail overlay — wiki item info as an always-on-top overlay."""

from __future__ import annotations

import json
import logging
import os
import re
import threading

log = logging.getLogger(__name__)
import webbrowser
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QPushButton,
    QScrollArea, QStackedWidget, QDoubleSpinBox,
)
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal

from PyQt6.QtGui import QFontMetrics, QPixmap

from .overlay_widget import OverlayWidget
from ..core.thread_utils import invoke_on_main
from ..ui.icons import svg_icon, ARROW_LEFT, ARROW_RIGHT
from ..ui.widgets.search_popup import WIKI_PATHS, ITEM_TYPES, get_type_name, get_display_type
from ..data.wiki_columns import (
    deep_get, _DAMAGE_TYPES, LEAF_DATA_MAP, get_item_name,
    weapon_total_damage, weapon_effective_damage, weapon_dps, weapon_dpp,
    weapon_cost_per_use, weapon_total_uses, weapon_reload,
    armor_total_defense, _armor_total_absorption,
    _medical_hps, _medical_hpp,
    _excavator_eff_per_ped, _blueprint_cost,
    fmt_int, fmt_bool,
)
from ..ui.widgets.wiki_detail import _TYPE_ID_OFFSETS
from ..ui.widgets.mob_detail import (
    _maturity_stats, _get_damage_groups, _format_maturity_label,
    _spawn_maturities_for_mob,
)
from ..ui.theme import DAMAGE_COLORS

if TYPE_CHECKING:
    from ..api.data_client import DataClient
    from .overlay_manager import OverlayManager

# --- Layout ---
DETAIL_WIDTH = 340
BODY_HEIGHT = 280
TAB_STRIP_W = 28
TAB_BTN_SIZE = 22

# Compact damage bar height
_BAR_HEIGHT = 6
_TYPE_LABEL_W = 55

# --- Colors (overlay dark theme — more transparent) ---
BG_COLOR = "rgba(20, 20, 30, 180)"
TITLE_BG = "rgba(30, 30, 45, 200)"
TAB_BG = "rgba(25, 25, 40, 180)"
TAB_ACTIVE_BG = "rgba(60, 60, 90, 180)"
TAB_HOVER_BG = "rgba(50, 50, 70, 160)"
CONTENT_BG = "rgba(30, 30, 45, 160)"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#999999"
TEXT_BRIGHT = "#ffffff"
ACCENT = "#00ccff"
SECTION_COLOR = "#00ccff"
BADGE_BG = "rgba(50, 50, 70, 160)"
FOOTER_BG = "rgba(25, 25, 40, 160)"
HIGHLIGHT_COLOR = "#4ade80"
NAV_DISABLED = "#444444"
BORDER = "#555555"

# Stacking offset: each new overlay shifts by this many pixels
STACK_OFFSET = 24

# --- SVG icon paths (24x24 viewBox, fill-based) ---
_PIN_SVG = '<path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5v6l1 1 1-1v-6h5v-2z"/>'

_CLOSE_SVG = (
    '<path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59'
    ' 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>'
)

# Info circle (details tab)
_TAB_INFO_SVG = (
    '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z'
    'm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>'
)

# Shopping bag (acquisition tab)
_TAB_ACQUIRE_SVG = (
    '<path d="M18 6h-2c0-2.21-1.79-4-4-4S8 3.79 8 6H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2'
    'h12c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-6-2c1.1 0 2 .9 2 2h-4c0-1.1.9-2 2-2z"/>'
)

# Document (description tab)
_TAB_DESC_SVG = (
    '<path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6z'
    'm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>'
)

# Open book (open in wiki)
_WIKI_SVG = (
    '<path d="M4 4.5C4 3.12 5.12 2 6.5 2H12v15H6.5C5.12 17 4 18.12 4 19.5V4.5z"/>'
    '<path d="M12 2h5.5C18.88 2 20 3.12 20 4.5V17h-8V2z" opacity="0.7"/>'
    '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20v3.5a1.5 1.5 0 0 1-1.5 1.5H6.5'
    'A2.5 2.5 0 0 1 4 19.5z" opacity="0.5"/>'
)

# Wrench (usage tab)
_TAB_USAGE_SVG = (
    '<path d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9'
    ' 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1'
    ' .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z"/>'
)

# Expand / collapse chevrons
_EXPAND_SVG = '<path d="M7 10l5 5 5-5z"/>'
_COLLAPSE_SVG = '<path d="M7 14l5-5 5 5z"/>'

# Mob: maturities (stacked bars)
_TAB_MATURITY_SVG = (
    '<path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7'
    'v2zM7 7v2h14V7H7z"/>'
)
# Loot (gift/drop)
_TAB_LOOT_SVG = (
    '<path d="M20 6h-2.18c.11-.31.18-.65.18-1a2.996 2.996 0 0 0-5.5-1.65l-.5.67-.5-.68'
    'C10.96 2.54 10.05 2 9 2 7.34 2 6 3.34 6 5c0 .35.07.69.18 1H4c-1.11 0-1.99.89-1.99'
    ' 2L2 19c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2z"/>'
)
# Map pin (locations tab)
_TAB_LOCATION_SVG = (
    '<path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z'
    'm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>'
)
# Checkmark list (steps)
_TAB_STEPS_SVG = (
    '<path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7'
    'v2zM7 7v2h14V7H7z"/>'
)
# Star (rewards)
_TAB_REWARDS_SVG = (
    '<path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24'
    'l5.46 4.73L5.82 21z"/>'
)
# Storefront (offers)
_TAB_OFFERS_SVG = (
    '<path d="M20 4H4v2h16V4zm1 10v-2l-1-5H4l-1 5v2h1v6h10v-6h4v6h2v-6h1zm-9 4H6v-4h6v4z"/>'
)
# Map (embedded map tab)
_TAB_MAP_SVG = (
    '<path d="M20.5 3l-.16.03L15 5.1 9 3 3.36 4.9c-.21.07-.36.25-.36.48V20.5c0 .28.22.5'
    '.5.5l.16-.03L9 18.9l6 2.1 5.64-1.9c.21-.07.36-.25.36-.48V3.5c0-.28-.22-.5-.5-.5z'
    'M15 19l-6-2.11V5l6 2.11V19z"/>'
)
# Copy (waypoint)
_COPY_SVG = (
    '<path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2'
    ' 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>'
)
_CHECK_SVG = '<path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>'
SUCCESS_COLOR = "#16a34a"

# Unlock (open padlock)
_TAB_UNLOCK_SVG = (
    '<path d="M12 17a2 2 0 002-2 2 2 0 00-2-2 2 2 0 00-2 2 2 2 0 002 2m6-9a2 2 0 012'
    ' 2v10a2 2 0 01-2 2H6a2 2 0 01-2-2V10a2 2 0 012-2h9V6a3 3 0 00-3-3 3 3 0 00-3 3H7'
    'a5 5 0 015-5 5 5 0 015 5v2h1z"/>'
)

# Calculator (sigma symbol)
_TAB_CALC_SVG = (
    '<path d="M18 4H6v2l6.5 6L6 18v2h12v-3h-7l5-5-5-5h7V4z"/>'
)

# Blueprint (square with circuit traces)
_TAB_BLUEPRINT_SVG = (
    '<rect x="3" y="3" width="18" height="18" rx="2" fill="none"'
    ' stroke="currentColor" stroke-width="1.5"/>'
    '<path d="M7 8h4v4H7z" fill="currentColor"/>'
    '<path d="M11 10h5M14 10v4M14 14h3M8 12v5M8 17h4" fill="none"'
    ' stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>'
)

# Tier/construction calculator (poker chip — filled center, 4 filled + 4 empty segments)
_TAB_TIERS_SVG = (
    # Outer ring as filled annulus (matches solid fill style of other icons)
    '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z'
    'm0 18.5c-4.69 0-8.5-3.81-8.5-8.5S7.31 3.5 12 3.5s8.5 3.81 8.5 8.5-3.81 8.5-8.5 8.5z"/>'
    # Center disc
    '<circle cx="12" cy="12" r="4"/>'
    # 4 filled segments (NE, SW, SE, NW — pie slices between ring and center)
    '<path d="M14.83 4.1 A10 10 0 0 1 19.9 9.17 L15.17 10.83 A4 4 0 0 0 13.17 8.83 Z"/>'
    '<path d="M9.17 19.9 A10 10 0 0 1 4.1 14.83 L8.83 13.17 A4 4 0 0 0 10.83 15.17 Z"/>'
    '<path d="M19.9 14.83 A10 10 0 0 1 14.83 19.9 L13.17 15.17 A4 4 0 0 0 15.17 13.17 Z"/>'
    '<path d="M4.1 9.17 A10 10 0 0 1 9.17 4.1 L10.83 8.83 A4 4 0 0 0 8.83 10.83 Z"/>'
)

_TAB_EFFECTS_SVG = (
    # Sparkle / buff icon
    '<path d="M12 2 L14 9 L21 9 L15.5 13.5 L17.5 21 L12 16.5 L6.5 21 L8.5 13.5 L3 9 L10 9 Z"/>'
)

# Market prices (bar chart icon)
_TAB_MARKET_PRICES_SVG = (
    '<path d="M5 9.2h3V19H5V9.2zM10.6 5h2.8v14h-2.8V5zM16.2 13H19v6h-2.8v-6z"/>'
)

# Globals (globe icon)
_TAB_GLOBALS_SVG = (
    '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z'
    'm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2'
    ' 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55'
    ' 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97'
    '-2.1 5.39z"/>'
)

# Module-level callback set by app.py to open the map overlay.
# Signature: (planet_name: str, location_id: int) -> None
_map_overlay_callback = None

# --- Tab IDs ---
TAB_DETAILS = "details"
TAB_ACQUISITION = "acquisition"
TAB_USAGE = "usage"
TAB_DESCRIPTION = "description"
TAB_MATURITIES = "maturities"
TAB_LOOTS = "loots"
TAB_LOCATIONS = "locations"
TAB_STEPS = "steps"
TAB_REWARDS = "rewards"
TAB_OFFERS = "offers"
TAB_MAP = "map"
TAB_CALCULATOR = "calculator"
TAB_TIERS = "tiers"
TAB_CONSTRUCTION = "construction"
TAB_UNLOCKS = "unlocks"
TAB_EFFECTS = "effects"
TAB_MARKET_PRICES = "market_prices"
TAB_GLOBALS = "globals"

# Entity types that support tiering (have tier materials)
_TIERABLE_TYPES = {"Weapon", "Armor", "ArmorSet", "MedicalTool", "Finder", "Excavator"}


def _get_tab_defs(entity_type: str, item_name: str = "") -> list[tuple[str, str, str]]:
    """Return (svg_path, tooltip, tab_id) for each tab based on entity type."""
    if entity_type == "Mob":
        return [
            (_TAB_INFO_SVG, "Details", TAB_DETAILS),
            (_TAB_MATURITY_SVG, "Maturities", TAB_MATURITIES),
            (_TAB_LOOT_SVG, "Loots", TAB_LOOTS),
            (_TAB_LOCATION_SVG, "Locations", TAB_LOCATIONS),
            (_TAB_GLOBALS_SVG, "Globals", TAB_GLOBALS),
            (_TAB_DESC_SVG, "Description", TAB_DESCRIPTION),
        ]
    if entity_type in ("Mission", "MissionChain"):
        return [
            (_TAB_INFO_SVG, "Details", TAB_DETAILS),
            (_TAB_STEPS_SVG, "Steps", TAB_STEPS),
            (_TAB_REWARDS_SVG, "Rewards", TAB_REWARDS),
            (_TAB_DESC_SVG, "Description", TAB_DESCRIPTION),
        ]
    if entity_type == "Vendor":
        return [
            (_TAB_INFO_SVG, "Details", TAB_DETAILS),
            (_TAB_OFFERS_SVG, "Offers", TAB_OFFERS),
            (_TAB_DESC_SVG, "Description", TAB_DESCRIPTION),
        ]
    if entity_type in ("Location", "Area"):
        return [
            (_TAB_INFO_SVG, "Details", TAB_DETAILS),
            (_TAB_MAP_SVG, "Map", TAB_MAP),
            (_TAB_DESC_SVG, "Description", TAB_DESCRIPTION),
        ]
    if entity_type == "Pet":
        return [
            (_TAB_INFO_SVG, "Details", TAB_DETAILS),
            (_TAB_EFFECTS_SVG, "Effects", TAB_EFFECTS),
            (_TAB_ACQUIRE_SVG, "Acquisition", TAB_ACQUISITION),
            (_TAB_USAGE_SVG, "Usage", TAB_USAGE),
            (_TAB_DESC_SVG, "Description", TAB_DESCRIPTION),
        ]
    if entity_type in ITEM_TYPES:
        tabs = [
            (_TAB_INFO_SVG, "Details", TAB_DETAILS),
        ]
        is_limited = item_name.endswith("(L)")
        if entity_type in _TIERABLE_TYPES and not is_limited:
            tabs.append((_TAB_TIERS_SVG, "Tier Calculator", TAB_TIERS))
        if entity_type == "Blueprint":
            tabs.append((_TAB_BLUEPRINT_SVG, "Construction Cost", TAB_CONSTRUCTION))
        tabs.append((_TAB_MARKET_PRICES_SVG, "Market Prices", TAB_MARKET_PRICES))
        tabs += [
            (_TAB_ACQUIRE_SVG, "Acquisition", TAB_ACQUISITION),
            (_TAB_USAGE_SVG, "Usage", TAB_USAGE),
            (_TAB_DESC_SVG, "Description", TAB_DESCRIPTION),
        ]
        if entity_type == "Weapon":
            tabs.append((_TAB_CALC_SVG, "Calculator", TAB_CALCULATOR))
        return tabs
    if entity_type == "Skill":
        return [
            (_TAB_INFO_SVG, "Details", TAB_DETAILS),
            (_TAB_UNLOCK_SVG, "Unlocked By", TAB_UNLOCKS),
            (_TAB_DESC_SVG, "Description", TAB_DESCRIPTION),
        ]
    if entity_type == "Profession":
        return [
            (_TAB_INFO_SVG, "Details", TAB_DETAILS),
            (_TAB_UNLOCK_SVG, "Skill Unlocks", TAB_UNLOCKS),
            (_TAB_DESC_SVG, "Description", TAB_DESCRIPTION),
        ]
    # Fallback
    return [
        (_TAB_INFO_SVG, "Details", TAB_DETAILS),
        (_TAB_DESC_SVG, "Description", TAB_DESCRIPTION),
    ]

# --- Button stylesheets ---
_BTN_STYLE = (
    "QPushButton {"
    "  background: transparent; border: none; border-radius: 3px;"
    "  padding: 0px; margin: 0px;"
    "}"
    "QPushButton:hover {"
    "  background-color: rgba(60, 60, 80, 200);"
    "}"
)


def _tab_btn_style(active: bool) -> str:
    bg = TAB_ACTIVE_BG if active else "transparent"
    return (
        f"QPushButton {{"
        f"  background-color: {bg}; border: none; border-radius: 3px;"
        f"  padding: 2px;"
        f"}}"
        f"QPushButton:hover {{"
        f"  background-color: {TAB_HOVER_BG};"
        f"}}"
    )


def _mps_seg_radius(is_first: bool, is_last: bool) -> str:
    """Border-radius for a segmented control button (pill ends)."""
    r = "3px"
    if is_first and is_last:
        return r
    if is_first:
        return f"{r} 0 0 {r}"
    if is_last:
        return f"0 {r} {r} 0"
    return "0"


def _mps_seg_style(active: bool, radius: str) -> str:
    """Stylesheet for a segmented control button."""
    if active:
        return (
            f"QPushButton {{ background: {ACCENT}; color: #fff; font-size: 11px;"
            f" border: none; border-radius: {radius}; padding: 1px 2px;"
            f" font-weight: 600; }}"
            f"QPushButton:hover {{ background: {ACCENT}; }}"
        )
    return (
        f"QPushButton {{ background: rgba(50,50,70,160); color: {TEXT_DIM}; font-size: 11px;"
        f" border: none; border-radius: {radius}; padding: 1px 2px; }}"
        f"QPushButton:hover {{ background: rgba(60,60,80,180); color: {TEXT_COLOR}; }}"
    )


class _ElidedLabel(QLabel):
    """QLabel that truncates text with an ellipsis when it doesn't fit."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._full_text = text
        self.setMinimumWidth(0)
        self.setText(text)

    def set_text(self, text: str):
        """Update the displayed text (with eliding)."""
        self._full_text = text
        fm = self.fontMetrics()
        elided = fm.elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, self.width(),
        )
        super().setText(elided)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        fm = self.fontMetrics()
        elided = fm.elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, self.width(),
        )
        super().setText(elided)


class DetailOverlayWidget(OverlayWidget):
    """Compact always-on-top overlay showing wiki item details.

    - Title bar: pin button, item name (click to minify), close button
    - Body: left tab strip + right scrollable content area
    - Tabs: Details, Acquisition, Description
    - Data loaded in background after creation
    """

    open_in_wiki = pyqtSignal(dict)
    open_entity = pyqtSignal(dict)   # open a referenced entity in a new overlay
    create_loadout = pyqtSignal(dict)  # calculator tab → create loadout
    _entity_loaded = pyqtSignal(dict, str)  # (entity, page_type_id)
    _acquisition_loaded = pyqtSignal(dict)
    _usage_loaded = pyqtSignal(dict)
    _market_prices_loaded = pyqtSignal(object)
    _map_data_ready = pyqtSignal(dict, object, list)  # (planet, pixmap, locations)

    def __init__(
        self,
        item: dict,
        *,
        config,
        config_path: str,
        data_client: DataClient,
        nexus_client=None,
        manager: OverlayManager | None = None,
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="detail_overlay_position",
            manager=manager,
        )
        self._item = item
        self._data_client = data_client
        self._nexus_client = nexus_client
        self._full_item: dict | None = None
        self._acq_data: dict | None = None
        self._usage_data: dict | None = None
        self._market_prices_data: dict | None = None
        self._mps_pieces: list[dict] = []
        self._mps_selected_slot: str = ""
        self._mps_selected_gender: str = "male"
        self._mps_selected_tier: int = 0
        self._page_type_id: str = ""
        self._pinned = False
        self._expanded = False
        self._nav_history: list[dict] = [item]
        self._nav_index: int = 0
        self._load_gen: int = 0  # generation counter to discard stale async loads
        self._click_origin: QPoint | None = None

        # Auto-resize to content
        self.layout().setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        self._container.setFixedWidth(DETAIL_WIDTH)
        self._container.setStyleSheet(
            f"background-color: {BG_COLOR}; border-radius: 8px;"
        )

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Title bar ---
        self._title_bar = self._build_title_bar(item)
        layout.addWidget(self._title_bar)

        # --- Body (hidden when minified) ---
        self._body = QWidget()
        self._body.setFixedHeight(BODY_HEIGHT)
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Content row: tab strip + content stack
        content_row = QWidget()
        cr_layout = QHBoxLayout(content_row)
        cr_layout.setContentsMargins(0, 0, 0, 0)
        cr_layout.setSpacing(0)

        # Tab strip (left)
        self._tab_buttons: list[QPushButton] = []
        self._tab_defs = _get_tab_defs(item.get("Type", ""), get_item_name(item))
        self._tab_ids = [td[2] for td in self._tab_defs]
        self._tab_strip_widget = tab_strip = QWidget()
        tab_strip.setFixedWidth(TAB_STRIP_W)
        tab_strip.setStyleSheet(
            f"background-color: {TAB_BG};"
            " border-bottom-left-radius: 8px;"
        )
        ts_layout = QVBoxLayout(tab_strip)
        ts_layout.setContentsMargins(3, 4, 3, 4)
        ts_layout.setSpacing(2)
        ts_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for i, (svg_path, tooltip, _tab_id) in enumerate(self._tab_defs):
            btn = QPushButton()
            btn.setFixedSize(TAB_BTN_SIZE, TAB_BTN_SIZE)
            btn.setIcon(svg_icon(svg_path, TEXT_DIM, 16))
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            btn.setStyleSheet(_tab_btn_style(False))
            ts_layout.addWidget(btn)
            self._tab_buttons.append(btn)

        cr_layout.addWidget(tab_strip)

        # Content stack (right)
        self._content_stack = QStackedWidget()
        self._content_stack.setStyleSheet(f"background: transparent;")
        cr_layout.addWidget(self._content_stack, 1)

        body_layout.addWidget(content_row, 1)

        # Footer: Open in Wiki
        footer = QWidget()
        footer.setStyleSheet(
            f"background-color: {FOOTER_BG};"
            " border-bottom-right-radius: 8px;"
        )
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(TAB_STRIP_W + 4, 2, 4, 3)
        footer_layout.setSpacing(4)

        wiki_btn = QPushButton("Open in Wiki")
        wiki_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        wiki_btn.setIcon(svg_icon(_WIKI_SVG, ACCENT, 12))
        wiki_btn.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; background: transparent;"
            " border: none; padding: 2px 4px;"
        )
        wiki_btn.clicked.connect(lambda: self.open_in_wiki.emit(self._item))
        footer_layout.addWidget(wiki_btn)
        footer_layout.addStretch(1)

        # Expand / collapse toggle
        self._expand_btn = QPushButton()
        self._expand_btn.setFixedSize(TAB_BTN_SIZE, TAB_BTN_SIZE)
        self._expand_btn.setIcon(svg_icon(_EXPAND_SVG, TEXT_DIM, 16))
        self._expand_btn.setToolTip("Expand")
        self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_btn.setStyleSheet(_BTN_STYLE)
        self._expand_btn.clicked.connect(self._toggle_expand)
        footer_layout.addWidget(self._expand_btn)

        body_layout.addWidget(footer)
        layout.addWidget(self._body)

        # Initialize tabs with loading/placeholder state
        self._init_tabs()
        self._switch_tab(0)

        # Connect cross-thread signals
        self._entity_loaded.connect(self._on_entity_loaded)
        self._acquisition_loaded.connect(self._on_acquisition_loaded)
        self._usage_loaded.connect(self._on_usage_loaded)
        self._market_prices_loaded.connect(self._on_market_prices_loaded)
        self._map_data_ready.connect(self._on_map_data_ready)
        self._map_canvas = None

        # Start visible and activate so Windows sends mouse hover events
        self.set_wants_visible(True)
        self.activateWindow()

        # Fetch full entity data in background
        self._fetch_entity()

    # --- Title bar builder ---

    def _build_title_bar(self, item: dict) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(24)
        bar.setStyleSheet(
            f"background-color: {TITLE_BG};"
            " border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        # Pin button
        self._pin_btn = QPushButton()
        self._pin_btn.setFixedSize(18, 18)
        self._pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pin_btn.setStyleSheet(_BTN_STYLE)
        self._pin_btn.clicked.connect(self._toggle_pin)
        self._update_pin_icon()
        layout.addWidget(self._pin_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Back button
        self._back_btn = QPushButton()
        self._back_btn.setFixedSize(18, 18)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.setStyleSheet(_BTN_STYLE)
        self._back_btn.setIcon(svg_icon(ARROW_LEFT, NAV_DISABLED, 14))
        self._back_btn.setToolTip("Back")
        self._back_btn.setEnabled(False)
        self._back_btn.clicked.connect(self._navigate_back)
        layout.addWidget(self._back_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Forward button
        self._fwd_btn = QPushButton()
        self._fwd_btn.setFixedSize(18, 18)
        self._fwd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fwd_btn.setStyleSheet(_BTN_STYLE)
        self._fwd_btn.setIcon(svg_icon(ARROW_RIGHT, NAV_DISABLED, 14))
        self._fwd_btn.setToolTip("Forward")
        self._fwd_btn.setEnabled(False)
        self._fwd_btn.clicked.connect(self._navigate_forward)
        layout.addWidget(self._fwd_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Item name (elided with ellipsis)
        display_name = item.get("DisplayName") or item.get("Name", "")
        self._name_label = _ElidedLabel(display_name)
        self._name_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            " background: transparent;"
        )
        self._name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._name_label, 1, Qt.AlignmentFlag.AlignVCenter)

        # Type badge
        type_name = get_display_type(item)
        self._type_badge = QLabel(type_name or "")
        self._type_badge.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px;"
            f" background-color: {BADGE_BG}; border-radius: 2px;"
            f" padding: 1px 4px;"
        )
        self._type_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._type_badge.setVisible(bool(type_name))
        layout.addWidget(self._type_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        # Close button
        close_btn = QPushButton()
        close_btn.setFixedSize(18, 18)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setIcon(svg_icon(_CLOSE_SVG, TEXT_DIM, 14))
        close_btn.setStyleSheet(_BTN_STYLE)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return bar

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(DETAIL_WIDTH)
        return hint

    # --- Public API ---

    @property
    def pinned(self) -> bool:
        return self._pinned

    def set_pinned(self, pinned: bool):
        self._pinned = pinned
        self._update_pin_icon()

    # --- Pin ---

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self._update_pin_icon()

    def _update_pin_icon(self):
        color = ACCENT if self._pinned else TEXT_DIM
        self._pin_btn.setIcon(svg_icon(_PIN_SVG, color, 14))

    # --- Minify ---

    def _toggle_minify(self):
        expanding = not self._body.isVisible()
        self._body.setVisible(expanding)
        # Update title bar radii — full radius when minified (no body below)
        if expanding:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG};"
                " border-top-left-radius: 8px; border-top-right-radius: 8px;"
            )
        else:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG}; border-radius: 8px;"
            )
        # Hide stats panel when minified
        if hasattr(self, "_calc_stats_panel"):
            self._calc_stats_panel.set_wants_visible(
                expanding and self._tab_ids[self._content_stack.currentIndex()] == TAB_CALCULATOR
            )

    # --- Expand / collapse ---

    def _toggle_expand(self):
        self._expanded = not self._expanded
        h = BODY_HEIGHT * 2 if self._expanded else BODY_HEIGHT
        self._body.setFixedHeight(h)
        svg = _COLLAPSE_SVG if self._expanded else _EXPAND_SVG
        self._expand_btn.setIcon(svg_icon(svg, TEXT_DIM, 16))
        self._expand_btn.setToolTip("Collapse" if self._expanded else "Expand")
        # Update stats panel max height after body resize
        if hasattr(self, "_calc_stats_panel"):
            QTimer.singleShot(0, self._position_calc_stats_panel)

    # --- Navigation history ---

    def _handle_entity_click(self, item: dict):
        """Route entity clicks: left-click navigates in-place, middle-click opens new window."""
        if item.pop("_force_new", False):
            self.open_entity.emit(item)
        else:
            self._navigate_to(item)

    def _navigate_to(self, item: dict):
        """Push item onto history and navigate to it in-place."""
        current = self._nav_history[self._nav_index]
        if (item.get("Name") == current.get("Name")
                and item.get("Type") == current.get("Type")):
            return
        # Truncate forward history
        self._nav_history = self._nav_history[:self._nav_index + 1]
        self._nav_history.append(item)
        self._nav_index = len(self._nav_history) - 1
        self._load_item(item)
        self._update_nav_buttons()

    def _navigate_back(self):
        """Go back one step in history."""
        if self._nav_index <= 0:
            return
        self._nav_index -= 1
        self._load_item(self._nav_history[self._nav_index])
        self._update_nav_buttons()

    def _navigate_forward(self):
        """Go forward one step in history."""
        if self._nav_index >= len(self._nav_history) - 1:
            return
        self._nav_index += 1
        self._load_item(self._nav_history[self._nav_index])
        self._update_nav_buttons()

    def _update_nav_buttons(self):
        """Enable/disable back/forward buttons based on history position."""
        can_back = self._nav_index > 0
        can_fwd = self._nav_index < len(self._nav_history) - 1
        self._back_btn.setEnabled(can_back)
        self._back_btn.setIcon(svg_icon(
            ARROW_LEFT, TEXT_DIM if can_back else NAV_DISABLED, 14))
        self._fwd_btn.setEnabled(can_fwd)
        self._fwd_btn.setIcon(svg_icon(
            ARROW_RIGHT, TEXT_DIM if can_fwd else NAV_DISABLED, 14))

    def _update_title_bar_content(self, item: dict):
        """Update the name label and type badge for a new item."""
        display_name = item.get("DisplayName") or item.get("Name", "")
        self._name_label.set_text(display_name)
        type_name = get_display_type(item)
        if type_name:
            self._type_badge.setText(type_name)
            self._type_badge.show()
        else:
            self._type_badge.hide()

    def _load_item(self, item: dict):
        """Reset overlay state and load a new entity in-place."""
        new_type = item.get("Type", "")

        # Increment generation to invalidate in-flight async loads
        self._load_gen += 1

        # Update item reference
        self._item = item

        # Reset data state
        self._full_item = None
        self._acq_data = None
        self._usage_data = None
        self._market_prices_data = None
        self._mps_pieces = []
        self._mps_selected_slot = ""
        self._mps_selected_gender = "male"
        self._mps_selected_tier = 0
        self._page_type_id = ""
        self._map_canvas = None

        # Cleanup lazy-initialized tabs
        if hasattr(self, "_calc_tab"):
            del self._calc_tab
        if hasattr(self, "_calc_stats_panel"):
            self._calc_stats_panel.close()
            self._calc_stats_panel.deleteLater()
            del self._calc_stats_panel
        if hasattr(self, "_tiers_tab_built"):
            del self._tiers_tab_built
        if hasattr(self, "_construction_tab_built"):
            del self._construction_tab_built
        if hasattr(self, "_map_loading"):
            del self._map_loading

        # Update title bar
        self._update_title_bar_content(item)

        # Rebuild tab strip if entity type changed
        new_tab_defs = _get_tab_defs(new_type, get_item_name(item))
        new_tab_ids = [td[2] for td in new_tab_defs]
        if new_tab_ids != self._tab_ids:
            self._rebuild_tab_strip(new_tab_defs)
        else:
            self._reset_tab_content()

        # Switch to Details tab
        self._switch_tab(0)

        # Fetch new entity data
        self._fetch_entity()

    def _rebuild_tab_strip(self, new_tab_defs):
        """Tear down and rebuild tab strip + content stack for a new entity type."""
        self._tab_defs = new_tab_defs
        self._tab_ids = [td[2] for td in new_tab_defs]

        # Clear old tab buttons
        ts_layout = self._tab_strip_widget.layout()
        while ts_layout.count():
            child = ts_layout.takeAt(0)
            w = child.widget()
            if w:
                w.deleteLater()

        # Build new tab buttons
        self._tab_buttons = []
        for i, (svg_path, tooltip, _tab_id) in enumerate(self._tab_defs):
            btn = QPushButton()
            btn.setFixedSize(TAB_BTN_SIZE, TAB_BTN_SIZE)
            btn.setIcon(svg_icon(svg_path, TEXT_DIM, 16))
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            btn.setStyleSheet(_tab_btn_style(False))
            ts_layout.addWidget(btn)
            self._tab_buttons.append(btn)

        # Clear content stack
        while self._content_stack.count():
            w = self._content_stack.widget(0)
            self._content_stack.removeWidget(w)
            w.deleteLater()

        # Re-init with loading placeholders
        self._tab_scrolls = {}
        self._init_tabs()

    def _reset_tab_content(self):
        """Reset all tab scroll areas to loading placeholders (same tab structure)."""
        placeholders = {
            TAB_DETAILS: "Loading...",
            TAB_ACQUISITION: "Loading item data...",
            TAB_USAGE: "Loading usage data...",
            TAB_DESCRIPTION: "No description",
            TAB_MATURITIES: "Loading...",
            TAB_LOOTS: "Loading...",
            TAB_LOCATIONS: "Loading...",
            TAB_STEPS: "Loading...",
            TAB_REWARDS: "Loading...",
            TAB_OFFERS: "Loading...",
            TAB_MAP: "Loading map...",
            TAB_CALCULATOR: "Loading...",
            TAB_TIERS: "Loading tier data...",
            TAB_CONSTRUCTION: "Loading materials...",
            TAB_UNLOCKS: "Loading unlock data...",
            TAB_EFFECTS: "Loading effects...",
        }
        for tab_id, scroll in self._tab_scrolls.items():
            placeholder = placeholders.get(tab_id, "Loading...")
            scroll.setWidget(_make_centered_label(placeholder))

    # --- Calculator tab ---

    def _init_calculator(self):
        from .calc_tab import CalcTab
        from .calc_stats_panel import CalcStatsPanel

        self._calc_tab = CalcTab(
            data_client=self._data_client,
            weapon_item=self._item,
        )
        self._calc_stats_panel = CalcStatsPanel(config=self._config)

        if self._manager:
            self._manager.opacity_changed.connect(
                self._calc_stats_panel.setWindowOpacity
            )

        # Replace placeholder in the content stack
        calc_idx = self._tab_ids.index(TAB_CALCULATOR)
        old_widget = self._content_stack.widget(calc_idx)
        self._content_stack.removeWidget(old_widget)
        old_widget.deleteLater()
        self._content_stack.insertWidget(calc_idx, self._calc_tab)
        self._content_stack.setCurrentIndex(calc_idx)

        # Wire signals
        self._calc_tab.stats_updated.connect(self._calc_stats_panel.update_stats)
        self._calc_tab.create_loadout.connect(self.create_loadout.emit)

        # Show stats panel
        self._position_calc_stats_panel()
        self._calc_stats_panel.show()

    def _position_calc_stats_panel(self):
        if not hasattr(self, "_calc_stats_panel"):
            return
        self._calc_stats_panel.set_max_height(self.height())
        self._calc_stats_panel.move(
            self.x() + self.width() + 4,
            self.y(),
        )

    def _init_tiers_tab(self):
        """Lazy-init the tier calculator tab with a compact _TiersWidget."""
        if not self._full_item:
            return
        widget = _build_overlay_tiers(self._full_item, self._nexus_client)
        scroll = self._tab_scrolls.get(TAB_TIERS)
        if scroll:
            scroll.setWidget(widget)
        self._tiers_tab_built = True

    def _init_construction_tab(self):
        """Lazy-init the blueprint construction cost tab."""
        if not self._full_item:
            return
        widget = _build_overlay_construction(self._full_item, self._nexus_client)
        scroll = self._tab_scrolls.get(TAB_CONSTRUCTION)
        if scroll:
            scroll.setWidget(widget)
        self._construction_tab_built = True

    # --- Tab switching ---

    def _switch_tab(self, index: int):
        for i, btn in enumerate(self._tab_buttons):
            active = i == index
            btn.setStyleSheet(_tab_btn_style(active))
            btn.setIcon(svg_icon(
                self._tab_defs[i][0],
                ACCENT if active else TEXT_DIM,
                16,
            ))
        self._content_stack.setCurrentIndex(index)

        tab_id = self._tab_ids[index] if index < len(self._tab_ids) else ""
        # Lazy-load acquisition data on first tab switch
        if tab_id == TAB_ACQUISITION and self._acq_data is None:
            self._fetch_acquisition()
        # Lazy-load usage data on first tab switch
        if tab_id == TAB_USAGE and self._usage_data is None:
            self._fetch_usage()
        # Lazy-init calculator tab
        if tab_id == TAB_CALCULATOR and not hasattr(self, "_calc_tab"):
            self._init_calculator()
        # Lazy-init tier calculator tab
        if tab_id == TAB_TIERS and not hasattr(self, "_tiers_tab_built"):
            self._init_tiers_tab()
        # Lazy-init construction cost tab
        if tab_id == TAB_CONSTRUCTION and not hasattr(self, "_construction_tab_built"):
            self._init_construction_tab()
        # Lazy-load market prices tab
        if tab_id == TAB_MARKET_PRICES and self._market_prices_data is None:
            self._fetch_market_prices()
        # Show/hide stats panel based on active tab
        if hasattr(self, "_calc_stats_panel"):
            self._calc_stats_panel.set_wants_visible(tab_id == TAB_CALCULATOR)

    # --- Data loading ---

    def _fetch_entity(self):
        item_type = self._item.get("Type", "")
        item_name = self._item.get("Name", "")
        path = WIKI_PATHS.get(item_type)
        if not path:
            return

        category = path[-1]
        mapping = LEAF_DATA_MAP.get(category)
        if not mapping:
            return

        method_name = mapping[0]
        page_type_id = mapping[1]
        dc = self._data_client

        def fetch():
            items = getattr(dc, method_name)()
            entity = next(
                (i for i in items if get_item_name(i) == item_name), None,
            )
            if entity:
                self._entity_loaded.emit(entity, page_type_id)

        threading.Thread(
            target=fetch, daemon=True, name="detail-overlay-fetch",
        ).start()

    def _on_entity_loaded(self, entity: dict, page_type_id: str):
        # Guard: ignore stale loads from a previous navigation
        if get_item_name(entity) != self._item.get("Name", ""):
            return
        self._full_item = entity
        self._page_type_id = page_type_id
        self._rebuild_details_tab()
        self._rebuild_description_tab()
        # Rebuild type-specific tabs from full item data
        for tab_id in self._tab_ids:
            if tab_id in (TAB_DETAILS, TAB_DESCRIPTION,
                          TAB_ACQUISITION, TAB_USAGE):
                continue  # handled separately
            self._rebuild_entity_tab(tab_id)
        # If user is already viewing the tier/construction tab, init now
        cur = self._content_stack.currentIndex()
        cur_tab = self._tab_ids[cur] if cur < len(self._tab_ids) else ""
        if cur_tab == TAB_TIERS and not hasattr(self, "_tiers_tab_built"):
            self._init_tiers_tab()
        if cur_tab == TAB_CONSTRUCTION and not hasattr(self, "_construction_tab_built"):
            self._init_construction_tab()

    def _fetch_acquisition(self):
        item_name = self._item.get("Name", "")
        dc = self._data_client

        def fetch():
            data = dc.get_acquisition(item_name)
            if data:
                data["_item_name"] = item_name
                self._acquisition_loaded.emit(data)

        threading.Thread(
            target=fetch, daemon=True, name="detail-overlay-acq",
        ).start()

    def _on_acquisition_loaded(self, data: dict):
        # Guard: ignore stale loads from a previous navigation
        if data.get("_item_name") != self._item.get("Name", ""):
            return
        self._acq_data = data
        self._rebuild_acquisition_tab()

    def _fetch_usage(self):
        item_name = self._item.get("Name", "")
        dc = self._data_client

        def fetch():
            data = dc.get_usage(item_name)
            if data:
                data["_item_name"] = item_name
                self._usage_loaded.emit(data)

        threading.Thread(
            target=fetch, daemon=True, name="detail-overlay-usage",
        ).start()

    def _on_usage_loaded(self, data: dict):
        # Guard: ignore stale loads from a previous navigation
        if data.get("_item_name") != self._item.get("Name", ""):
            return
        self._usage_data = data
        self._rebuild_usage_tab()

    # --- Market prices ---

    def _is_mps_tierable(self) -> bool:
        """Check if current item supports tier filtering for market prices."""
        entity_type = self._item.get("Type", "")
        item_name = self._item.get("Name", "")
        return entity_type in _TIERABLE_TYPES

    def _fetch_market_prices(self, piece_name: str | None = None):
        nc = self._nexus_client
        item = self._full_item or self._item
        item_name = self._item.get("Name", "")

        if not nc:
            self._market_prices_loaded.emit({
                "_item_name": item_name, "snapshot": None, "pieces": [],
            })
            return

        # Build pieces list for armor sets
        pieces: list[dict] = []
        armors = item.get("Armors") or []
        for slot_variants in armors:
            if not isinstance(slot_variants, list):
                continue
            for armor in slot_variants:
                if not isinstance(armor, dict) or not armor.get("Name"):
                    continue
                pieces.append({
                    "name": armor["Name"],
                    "slot": (armor.get("Properties") or {}).get("Slot", ""),
                    "gender": (armor.get("Properties") or {}).get("Gender", "Both"),
                })

        # Determine what name/id to fetch
        fetch_name = piece_name
        fetch_id = None
        if not fetch_name and pieces:
            fetch_name = pieces[0]["name"]
        elif not fetch_name:
            fetch_id = item.get("ItemId") or item.get("Id")

        # Tier filter for tierable items
        tier = self._mps_selected_tier if self._is_mps_tierable() else None

        log.debug("[mps] %s: fetch_name=%s, fetch_id=%s, tier=%s, item keys=%s",
                    item_name, fetch_name, fetch_id, tier, list(item.keys()))

        def fetch():
            snapshot = None
            if fetch_name:
                rows = nc.get_item_market_prices_by_name(fetch_name, tier=tier)
                log.debug("[mps] by_name(%s) → %s", fetch_name, rows)
                if rows:
                    snapshot = rows[0]
            elif fetch_id:
                rows = nc.get_item_market_prices(fetch_id, tier=tier)
                log.debug("[mps] by_id(%s) → %s", fetch_id, rows)
                if rows:
                    snapshot = rows[0]
            else:
                log.debug("[mps] no fetch_name or fetch_id for %s", item_name)
            self._market_prices_loaded.emit({
                "_item_name": item_name,
                "snapshot": snapshot,
                "pieces": pieces,
            })

        threading.Thread(
            target=fetch, daemon=True, name="detail-overlay-mps",
        ).start()

    def _on_market_prices_loaded(self, data):
        if not isinstance(data, dict):
            return
        if data.get("_item_name") != self._item.get("Name", ""):
            return
        self._market_prices_data = data
        pieces = data.get("pieces", [])
        self._mps_pieces = pieces
        # Auto-select first slot if not already set
        if pieces and not self._mps_selected_slot:
            self._mps_selected_slot = pieces[0].get("slot", "")
        self._rebuild_market_prices_tab()

    def _rebuild_market_prices_tab(self):
        data = self._market_prices_data
        if data is None:
            return
        scroll = self._tab_scrolls.get(TAB_MARKET_PRICES)
        if scroll:
            scroll.setWidget(self._build_market_prices_content(data))

    def _build_market_prices_content(self, data: dict) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # Tier selector for tierable items
        if self._is_mps_tierable():
            tier_items = [(str(t), str(t)) for t in range(11)]
            layout.addWidget(self._mps_segmented_row(
                items=tier_items,
                selected=str(self._mps_selected_tier),
                on_click=self._on_mps_tier_selected,
            ))

        # Piece/gender selector for armor sets
        pieces = data.get("pieces", [])
        if pieces:
            selector = self._build_mps_piece_selector(pieces)
            layout.addWidget(selector)

        snapshot = data.get("snapshot")
        if not snapshot:
            layout.addWidget(_make_centered_label("No market price data available"))
            layout.addStretch(1)
            return widget

        layout.addWidget(_section_label("Market Prices"))

        periods = [
            ("1d", "1 Day"),
            ("7d", "7 Days"),
            ("30d", "30 Days"),
            ("365d", "1 Year"),
            ("3650d", "10 Years"),
        ]

        for key, label in periods:
            markup = snapshot.get(f"markup_{key}")
            sales = snapshot.get(f"sales_{key}")
            markup_str = f"{float(markup):.2f}%" if markup is not None else "\u2014"
            sales_str = f"{int(float(sales)):,}" if sales is not None else "\u2014"
            row = self._mps_row(label, markup_str, sales_str)
            layout.addWidget(row)

        # Last updated
        recorded_at = snapshot.get("recorded_at", "")
        if recorded_at:
            from datetime import datetime, timezone
            try:
                dt = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
                diff = datetime.now(timezone.utc) - dt
                mins = int(diff.total_seconds() / 60)
                if mins < 1:
                    ago = "just now"
                elif mins < 60:
                    ago = f"{mins}m ago"
                elif mins < 1440:
                    ago = f"{mins // 60}h ago"
                else:
                    ago = f"{mins // 1440}d ago"
                updated_lbl = QLabel(f"Updated {ago}")
                updated_lbl.setStyleSheet(
                    f"color: {TEXT_DIM}; font-size: 10px; background: transparent;"
                    " padding: 4px 0 0 0;"
                )
                layout.addWidget(updated_lbl)
            except (ValueError, TypeError):
                pass

        confidence = snapshot.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence = None
        if confidence is not None and confidence < 0.5:
            warn_lbl = QLabel("Low confidence")
            warn_lbl.setStyleSheet(
                "color: #e8a838; font-size: 10px; font-weight: bold;"
                " background: transparent; padding: 2px 0;"
            )
            layout.addWidget(warn_lbl)

        layout.addStretch(1)
        return widget

    # --- Armor set piece selector for market prices ---

    _SLOT_ORDER = ["Head", "Torso", "Arms", "Hands", "Legs", "Shins", "Feet"]

    def _build_mps_piece_selector(self, pieces: list[dict]) -> QWidget:
        """Build slot + gender segmented control for armor set piece selection."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 4)
        vbox.setSpacing(3)

        # Group pieces by slot
        by_slot: dict[str, dict] = {}
        for p in pieces:
            slot = p.get("slot", "")
            if slot not in by_slot:
                by_slot[slot] = {"male": None, "female": None}
            gender = p.get("gender", "Both")
            if gender in ("Both", "Male"):
                by_slot[slot]["male"] = p
            if gender in ("Both", "Female"):
                by_slot[slot]["female"] = p

        # Slot segmented control — uniform width, fills available space
        ordered_slots = [s for s in self._SLOT_ORDER if s in by_slot]
        vbox.addWidget(self._mps_segmented_row(
            items=[(s, s) for s in ordered_slots],
            selected=self._mps_selected_slot,
            on_click=self._on_mps_slot_selected,
        ))

        # Gender toggle (only if selected slot has distinct gender variants)
        entry = by_slot.get(self._mps_selected_slot, {})
        has_gender = (
            entry.get("male") and entry.get("female")
            and entry["male"].get("name") != entry["female"].get("name")
        )
        if has_gender:
            vbox.addWidget(self._mps_segmented_row(
                items=[("male", "Male"), ("female", "Female")],
                selected=self._mps_selected_gender,
                on_click=self._on_mps_gender_selected,
            ))

        return container

    @staticmethod
    def _mps_segmented_row(
        items: list[tuple[str, str]],
        selected: str,
        on_click,
    ) -> QWidget:
        """Build a segmented control row — equal-width buttons filling the width."""
        row = QWidget()
        row.setFixedHeight(20)
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        for i, (key, label) in enumerate(items):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            active = key == selected
            is_first = i == 0
            is_last = i == len(items) - 1
            radius = _mps_seg_radius(is_first, is_last)
            btn.setStyleSheet(_mps_seg_style(active, radius))
            btn.setFixedHeight(20)
            btn.clicked.connect(lambda checked=False, k=key: on_click(k))
            layout.addWidget(btn, 1)  # stretch=1 → equal width

        return row

    def _on_mps_slot_selected(self, slot: str):
        self._mps_selected_slot = slot
        self._mps_selected_gender = "male"
        self._refetch_mps_for_piece()

    def _on_mps_gender_selected(self, gender: str):
        self._mps_selected_gender = gender
        self._refetch_mps_for_piece()

    def _on_mps_tier_selected(self, tier_str: str):
        self._mps_selected_tier = int(tier_str)
        self._market_prices_data = None
        self._fetch_market_prices()

    def _refetch_mps_for_piece(self):
        """Re-fetch market prices for the currently selected piece."""
        pieces = self._mps_pieces
        if not pieces:
            return

        # Find the piece name for the selected slot/gender
        by_slot: dict[str, dict] = {}
        for p in pieces:
            slot = p.get("slot", "")
            if slot not in by_slot:
                by_slot[slot] = {"male": None, "female": None}
            gender = p.get("gender", "Both")
            if gender in ("Both", "Male"):
                by_slot[slot]["male"] = p
            if gender in ("Both", "Female"):
                by_slot[slot]["female"] = p

        entry = by_slot.get(self._mps_selected_slot, {})
        has_gender = (
            entry.get("male") and entry.get("female")
            and entry["male"].get("name") != entry["female"].get("name")
        )
        if has_gender:
            pick = entry.get(self._mps_selected_gender) or entry.get("male")
        else:
            pick = entry.get("male") or entry.get("female")

        piece_name = pick.get("name") if pick else None
        if piece_name:
            self._market_prices_data = None
            self._fetch_market_prices(piece_name=piece_name)

    @staticmethod
    def _mps_row(period: str, markup: str, sales: str) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 2, 0, 2)
        rl.setSpacing(4)

        period_lbl = QLabel(period)
        period_lbl.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;"
        )
        period_lbl.setFixedWidth(60)
        rl.addWidget(period_lbl)

        markup_lbl = QLabel(markup)
        markup_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 12px; background: transparent;"
        )
        markup_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        rl.addWidget(markup_lbl, 1)

        sales_lbl = QLabel(sales)
        sales_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
        )
        sales_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        sales_lbl.setFixedWidth(70)
        rl.addWidget(sales_lbl)

        return row

    def _get_exchange_url(self) -> str | None:
        """Compute the exchange detail URL from the loaded entity data."""
        full = self._full_item
        if not full:
            return None
        entity_id = full.get("Id")
        entity_type = self._item.get("Type", "")
        offset = _TYPE_ID_OFFSETS.get(entity_type)
        if entity_id is not None and offset is not None:
            base = getattr(self._config, "nexus_base_url", "https://entropianexus.com")
            return f"{base}/market/exchange/listings/{entity_id + offset}"
        return None

    # --- Tab initialization ---

    def _init_tabs(self):
        self._tab_scrolls: dict[str, QScrollArea] = {}
        _placeholders = {
            TAB_DETAILS: "Loading...",
            TAB_ACQUISITION: "Loading item data...",
            TAB_USAGE: "Loading usage data...",
            TAB_DESCRIPTION: "No description",
            TAB_MATURITIES: "Loading...",
            TAB_LOOTS: "Loading...",
            TAB_LOCATIONS: "Loading...",
            TAB_STEPS: "Loading...",
            TAB_REWARDS: "Loading...",
            TAB_OFFERS: "Loading...",
            TAB_MAP: "Loading map...",
            TAB_CALCULATOR: "Loading...",
            TAB_TIERS: "Loading tier data...",
            TAB_CONSTRUCTION: "Loading materials...",
            TAB_UNLOCKS: "Loading unlock data...",
            TAB_EFFECTS: "Loading effects...",
            TAB_MARKET_PRICES: "Loading market prices...",
        }
        for tab_id in self._tab_ids:
            scroll = self._make_scroll(
                _make_centered_label(_placeholders.get(tab_id, "Loading...")),
            )
            self._tab_scrolls[tab_id] = scroll
            self._content_stack.addWidget(scroll)

    def _rebuild_details_tab(self):
        item = self._full_item
        if not item:
            return
        scroll = self._tab_scrolls.get(TAB_DETAILS)
        if scroll:
            builder = _TYPE_BUILDERS.get(self._page_type_id, _build_generic_details)
            widget = builder(item, self._page_type_id,
                             on_entity=self._handle_entity_click)
            scroll.setWidget(widget)

    def _rebuild_acquisition_tab(self):
        data = self._acq_data
        if not data:
            return
        scroll = self._tab_scrolls.get(TAB_ACQUISITION)
        if scroll:
            scroll.setWidget(self._build_acquisition_content(data))

    def _rebuild_usage_tab(self):
        data = self._usage_data
        if not data:
            return
        scroll = self._tab_scrolls.get(TAB_USAGE)
        if scroll:
            scroll.setWidget(self._build_usage_content(data))

    def _rebuild_description_tab(self):
        item = self._full_item
        if not item:
            return
        desc = (
            deep_get(item, "Properties", "Description")
            or item.get("Description")
            or ""
        )
        if desc:
            widget = self._build_description_content(desc)
        else:
            widget = _make_centered_label("No description available")
        scroll = self._tab_scrolls.get(TAB_DESCRIPTION)
        if scroll:
            scroll.setWidget(widget)

    def _rebuild_entity_tab(self, tab_id: str):
        """Rebuild a type-specific tab from full item data."""
        item = self._full_item
        if not item:
            return
        scroll = self._tab_scrolls.get(tab_id)
        if not scroll:
            return
        builder = {
            TAB_MATURITIES: self._build_maturities_content,
            TAB_LOOTS: self._build_loots_content,
            TAB_LOCATIONS: self._build_locations_content,
            TAB_STEPS: self._build_steps_content,
            TAB_REWARDS: self._build_rewards_content,
            TAB_OFFERS: self._build_offers_content,
            TAB_MAP: self._build_map_content,
            TAB_UNLOCKS: self._build_unlocks_content,
            TAB_EFFECTS: self._build_effects_content,
            TAB_GLOBALS: self._build_globals_tab_content,
        }.get(tab_id)
        if builder:
            scroll.setWidget(builder(item))

    # ----- Mob: Maturities tab -----

    def _build_maturities_content(self, item: dict) -> QWidget:
        maturities = item.get("Maturities") or []
        if not maturities:
            return _make_centered_label("No maturity data")
        widget, layout = _details_container()
        # Sort by level then HP
        sorted_mats = sorted(maturities, key=lambda m: (
            deep_get(m, "Properties", "Boss") is True,
            deep_get(m, "Properties", "Level") or 0,
            deep_get(m, "Properties", "Health") or 0,
        ))
        # Header
        hdr = QWidget()
        hdr.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(0, 0, 0, 2)
        hl.setSpacing(0)
        for text, w in [("Name", 80), ("Lvl", 35), ("HP", 45),
                        ("HP/L", 38), ("Dmg", 40), ("Def", 40)]:
            lbl = QLabel(text)
            lbl.setFixedWidth(w)
            lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 9px; font-weight: 600;"
                " background: transparent; letter-spacing: 0.3px;"
            )
            hl.addWidget(lbl)
        layout.addWidget(hdr)
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(100, 100, 120, 80);")
        layout.addWidget(sep)
        for m in sorted_mats:
            lvl = deep_get(m, "Properties", "Level")
            hp = deep_get(m, "Properties", "Health")
            hpl = (hp / lvl) if (hp and lvl and lvl > 0) else None
            attacks = m.get("Attacks") or []
            primary = next((a for a in attacks if a.get("Name") == "Primary"), None)
            dmg = primary.get("TotalDamage") if primary else None
            defense = deep_get(m, "Properties", "Defense") or {}
            total_def = sum(defense.get(dt) or 0 for dt in _DAMAGE_TYPES) or None
            boss = deep_get(m, "Properties", "Boss")
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 1, 0, 1)
            rl.setSpacing(0)
            name_lbl = QLabel(m.get("Name", "?"))
            name_lbl.setFixedWidth(80)
            name_color = "#fbbf24" if boss else TEXT_COLOR
            name_lbl.setStyleSheet(
                f"color: {name_color}; font-size: 10px; background: transparent;"
            )
            rl.addWidget(name_lbl)
            for val, w in [(fmt_int(lvl), 35), (fmt_int(hp), 45),
                           (_fv(hpl, 1) if hpl else "-", 38),
                           (_fv(dmg, 1) if dmg else "-", 40),
                           (_fv(total_def, 1) if total_def else "-", 40)]:
                cell = QLabel(str(val) if val is not None else "-")
                cell.setFixedWidth(w)
                cell.setStyleSheet(
                    f"color: {TEXT_DIM}; font-size: 10px; background: transparent;"
                )
                rl.addWidget(cell)
            layout.addWidget(row)
        layout.addStretch(1)
        return widget

    # ----- Mob: Loots tab -----

    _FREQ_COLORS = {
        "Always": "#4ade80",
        "Very often": "#22d3ee",
        "Often": "#60a5fa",
        "Common": "#818cf8",
        "Uncommon": "#a78bfa",
        "Rare": "#c084fc",
        "Very rare": "#e879f9",
        "Extremely rare": "#f472b6",
        "Discontinued": "#6b7280",
    }

    def _build_loots_content(self, item: dict) -> QWidget:
        loots = item.get("Loots") or []
        if not loots:
            return _make_centered_label("No loot data")
        widget, layout = _details_container()
        emit = self._handle_entity_click
        # Sort by frequency order
        freq_order = list(self._FREQ_COLORS.keys())
        sorted_loots = sorted(loots, key=lambda l: (
            freq_order.index(l.get("Frequency", ""))
            if l.get("Frequency", "") in freq_order else 99
        ))
        for loot in sorted_loots:
            item_data = loot.get("Item") or {}
            item_name = item_data.get("Name") or "?"
            freq = loot.get("Frequency") or ""
            maturity = deep_get(loot, "Maturity", "Name") or ""
            info_parts = [freq] if freq else []
            if maturity:
                info_parts.append(maturity + "+")
            info = "  ".join(info_parts)
            color = self._FREQ_COLORS.get(freq, TEXT_DIM)
            entity = {"Name": item_name, "Type": "Material"}
            row = _acq_row(item_name, info, entity, emit, freq_color=color)
            layout.addWidget(row)
        layout.addStretch(1)
        return widget

    # ----- Mob: Locations tab -----

    def _build_locations_content(self, item: dict) -> QWidget:
        from ..ui.pages.maps_page import _mob_area_difficulty, _difficulty_color

        spawns = item.get("Spawns") or []
        if not spawns:
            return _make_centered_label("No location data")
        widget, layout = _details_container()
        mob_name = item.get("Name", "")
        for spawn in spawns:
            spawn_name = spawn.get("Name") or "?"
            planet = deep_get(spawn, "Planet", "Name") or ""
            coords = deep_get(spawn, "Properties", "Coordinates") or {}
            density = deep_get(spawn, "Properties", "Density")
            mats = spawn.get("Maturities") or []

            # Maturity range for this mob (level-sorted, boss-aware)
            mat_str = _spawn_maturities_for_mob(spawn, mob_name)

            # Other mob names present at this spawn
            other_mobs: list[str] = []
            seen: set[str] = set()
            for m in mats:
                mob_raw = deep_get(m, "Maturity", "Mob")
                other = (mob_raw.get("Name", "") if isinstance(mob_raw, dict)
                         else mob_raw or "")
                if other and other != mob_name and other not in seen:
                    seen.add(other)
                    other_mobs.append(other)

            # Difficulty
            diff = _mob_area_difficulty(spawn)

            # --- Render ---
            box = QWidget()
            box.setStyleSheet("background: transparent;")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(0, 2, 0, 2)
            bl.setSpacing(1)

            # Title: maturity range + difficulty badge
            title_row = QWidget()
            title_row.setStyleSheet("background: transparent;")
            trl = QHBoxLayout(title_row)
            trl.setContentsMargins(0, 0, 0, 0)
            trl.setSpacing(4)
            mat_lbl = QLabel(mat_str or "All")
            mat_lbl.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 12px; font-weight: 500;"
                " background: transparent;"
            )
            mat_lbl.setWordWrap(True)
            trl.addWidget(mat_lbl, 1)
            if diff:
                band, label = diff
                r, g, b = _difficulty_color(band)
                diff_badge = QLabel(label)
                diff_badge.setStyleSheet(
                    f"color: rgb({r},{g},{b}); font-size: 10px;"
                    f" background-color: rgba({r},{g},{b},30);"
                    " border-radius: 2px; padding: 0px 3px;"
                )
                trl.addWidget(diff_badge)
            bl.addWidget(title_row)

            # Info line: others + density
            info_parts = []
            if other_mobs:
                info_parts.append("Also: " + ", ".join(other_mobs))
            if density:
                density_labels = {1: "Low", 2: "Med", 3: "High"}
                info_parts.append(
                    f"Density: {density_labels.get(density, density)}"
                )
            if info_parts:
                info_lbl = QLabel(" | ".join(info_parts))
                info_lbl.setStyleSheet(
                    f"color: {TEXT_DIM}; font-size: 11px;"
                    " background: transparent;"
                )
                info_lbl.setWordWrap(True)
                bl.addWidget(info_lbl)

            # Button row: waypoint + map
            lon = coords.get("Longitude")
            lat = coords.get("Latitude")
            if lon is not None and lat is not None:
                btn_row = QWidget()
                btn_row.setStyleSheet("background: transparent;")
                brl = QHBoxLayout(btn_row)
                brl.setContentsMargins(0, 0, 0, 0)
                brl.setSpacing(4)
                wp_name = f"{mob_name} {mat_str}" if mat_str and mat_str != "All" else mob_name
                brl.addWidget(_overlay_waypoint_btn(planet, coords, wp_name))
                brl.addWidget(_overlay_map_btn(planet, spawn.get("Id")))
                brl.addStretch(1)
                bl.addWidget(btn_row)
            layout.addWidget(box)
            # Separator
            sep = QWidget()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background-color: rgba(100, 100, 120, 40);")
            layout.addWidget(sep)
        layout.addStretch(1)
        return widget

    # ----- Mob: Globals tab -----

    def _build_globals_tab_content(self, item: dict) -> QWidget:
        """Build globals tab content — fetches data asynchronously."""
        mob_name = item.get("Name", "")
        if not mob_name:
            return _make_centered_label("No mob name")

        widget, layout = _details_container()

        loading = QLabel("Loading globals...")
        loading.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
        )
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(loading)

        # Store reference for async replacement
        self._globals_overlay_widget = widget
        self._globals_overlay_layout = layout
        self._globals_overlay_loading = loading
        self._globals_overlay_mob_name = mob_name
        self._globals_overlay_period = "30d"
        self._globals_overlay_top_sort = "value"
        self._globals_skeleton_built = False

        dc = getattr(self, "_data_client", None)
        if dc:
            import threading as _th

            def fetch():
                data = dc.get_mob_globals(mob_name, period="30d")
                invoke_on_main(lambda d=data: self._populate_globals_overlay(d))

            _th.Thread(target=fetch, daemon=True, name="overlay-mob-globals").start()
        else:
            loading.setText("No data client available")

        return widget

    def _populate_globals_overlay(self, data: dict):
        """Populate the globals tab after initial async fetch."""
        layout = getattr(self, "_globals_overlay_layout", None)
        if not layout:
            return
        # Clear loading label and build skeleton
        _clear_layout(layout)
        self._globals_overlay_loading = None
        try:
            self._populate_globals_overlay_inner(data, layout)
        except Exception:
            log.exception("Failed to populate globals overlay")
            err = QLabel("Error loading globals")
            err.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
            )
            err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(err)

    def _populate_globals_overlay_inner(self, data: dict, layout):
        """Inner populate — separated so exceptions are caught."""
        self._build_globals_skeleton(layout)
        self._fill_globals_data(data)

    def _build_globals_skeleton(self, layout):
        """Build the persistent widget skeleton for the globals tab.

        Creates period buttons, stat cards, message label, recent/top
        containers — all reusable across period changes and re-sorts.
        """
        # Period buttons row
        period_row = QWidget()
        period_row.setStyleSheet("background: transparent;")
        pl = QHBoxLayout(period_row)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(3)
        self._globals_period_buttons = {}
        for p in ("24h", "7d", "30d", "90d", "1y", "all"):
            btn = QPushButton(p)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda checked=False, period=p: self._on_globals_overlay_period(period)
            )
            pl.addWidget(btn)
            self._globals_period_buttons[p] = btn
        pl.addStretch(1)
        layout.addWidget(period_row)
        self._update_globals_period_styles()

        # Summary stats row — values start as "-"
        stats_row = QWidget()
        stats_row.setStyleSheet("background: transparent;")
        sl = QHBoxLayout(stats_row)
        sl.setContentsMargins(0, 8, 0, 0)
        sl.setSpacing(4)
        self._globals_stat_labels = {}
        for key, label in [
            ("total_count", "Globals"),
            ("total_value", "Total"),
            ("max_value", "Highest"),
            ("hof_count", "HoF"),
        ]:
            card = QWidget()
            card.setStyleSheet(
                "background: rgba(30,30,50,80); border-radius: 3px;"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(6, 4, 6, 4)
            cl.setSpacing(1)
            val_lbl = QLabel("-")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl.setStyleSheet(
                f"color: {TEXT_BRIGHT}; font-size: 12px; font-weight: 700;"
                " background: transparent;"
            )
            cl.addWidget(val_lbl)
            lbl = QLabel(label.upper())
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 9px; font-weight: 600;"
                " letter-spacing: 0.2px; background: transparent;"
            )
            cl.addWidget(lbl)
            sl.addWidget(card)
            self._globals_stat_labels[key] = val_lbl
        layout.addWidget(stats_row)

        # Message label (loading / empty / error) — initially hidden
        self._globals_message_label = QLabel("")
        self._globals_message_label.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
        )
        self._globals_message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._globals_message_label.setVisible(False)
        layout.addWidget(self._globals_message_label)

        # Recent globals section
        self._globals_recent_title = QLabel("RECENT")
        self._globals_recent_title.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; font-weight: 600;"
            " letter-spacing: 0.3px; background: transparent;"
            " margin-top: 8px;"
        )
        self._globals_recent_title.setVisible(False)
        layout.addWidget(self._globals_recent_title)

        self._globals_recent_container = QWidget()
        self._globals_recent_container.setStyleSheet("background: transparent;")
        rc_layout = QVBoxLayout(self._globals_recent_container)
        rc_layout.setContentsMargins(0, 0, 0, 0)
        rc_layout.setSpacing(0)
        layout.addWidget(self._globals_recent_container)

        # Top players header (label + sort buttons)
        self._globals_top_header = QWidget()
        self._globals_top_header.setStyleSheet("background: transparent;")
        th_layout = QHBoxLayout(self._globals_top_header)
        th_layout.setContentsMargins(0, 8, 0, 0)
        th_layout.setSpacing(6)
        top_label = QLabel("TOP PLAYERS")
        top_label.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; font-weight: 600;"
            " letter-spacing: 0.3px; background: transparent;"
        )
        th_layout.addWidget(top_label)
        th_layout.addStretch(1)
        self._globals_sort_buttons = {}
        for sk, sl_text in [("value", "Total"), ("count", "Count"), ("best_value", "Best")]:
            sbtn = QPushButton(sl_text)
            sbtn.setCursor(Qt.CursorShape.PointingHandCursor)
            sbtn.clicked.connect(
                lambda checked=False, k=sk: self._on_globals_overlay_sort(k)
            )
            th_layout.addWidget(sbtn)
            self._globals_sort_buttons[sk] = sbtn
        self._globals_top_header.setVisible(False)
        layout.addWidget(self._globals_top_header)
        self._update_globals_sort_styles()

        # Top players rows container
        self._globals_top_container = QWidget()
        self._globals_top_container.setStyleSheet("background: transparent;")
        tc_layout = QVBoxLayout(self._globals_top_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(0)
        layout.addWidget(self._globals_top_container)

        layout.addStretch(1)
        self._globals_skeleton_built = True

    # --- Globals: data fill ---

    def _fill_globals_data(self, data: dict):
        """Populate data values into the existing skeleton."""
        self._globals_overlay_data = data
        summary = data.get("summary") or {}
        has_data = summary and summary.get("total_count", 0) > 0

        # Update stat labels
        if has_data:
            self._globals_stat_labels["total_count"].setText(
                f"{summary.get('total_count', 0):,}")
            self._globals_stat_labels["total_value"].setText(
                _overlay_format_ped(summary.get("total_value", 0)))
            self._globals_stat_labels["max_value"].setText(
                _overlay_format_ped(summary.get("max_value", 0)))
            self._globals_stat_labels["hof_count"].setText(
                f"{summary.get('hof_count', 0):,}")
        else:
            for lbl in self._globals_stat_labels.values():
                lbl.setText("-")

        # Message label
        if not has_data:
            msg = ("Failed to load \u2014 try a shorter period"
                   if not data else "No globals recorded")
            self._globals_message_label.setText(msg)
            self._globals_message_label.setVisible(True)
        else:
            self._globals_message_label.setVisible(False)

        # Recent section
        self._fill_globals_recent(data, has_data)

        # Top players section
        top = data.get("top_players") or []
        self._globals_top_header.setVisible(bool(top) and has_data)
        self._fill_globals_top_players()

    def _fill_globals_recent(self, data: dict, has_data: bool):
        """Fill the recent globals sub-container."""
        rc_layout = self._globals_recent_container.layout()
        _clear_layout(rc_layout)
        recent = (data.get("recent") or [])[:8] if has_data else []
        self._globals_recent_title.setVisible(bool(recent))
        for g in recent:
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 1, 0, 1)
            rl.setSpacing(4)
            player = g.get("player") or "?"
            if g.get("type") == "team_kill":
                player = "[T] " + player
            p_lbl = _ElidedLabel(player)
            p_lbl.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;"
            )
            rl.addWidget(p_lbl, 1)
            # Badge
            if g.get("ath"):
                badge = QLabel("ATH")
                badge.setStyleSheet(
                    "color: #ef4444; background: rgba(239,68,68,0.2);"
                    " border-radius: 2px; padding: 0 3px; font-size: 9px;"
                    " font-weight: 700;"
                )
                rl.addWidget(badge)
            elif g.get("hof"):
                badge = QLabel("HoF")
                badge.setStyleSheet(
                    "color: #eab308; background: rgba(234,179,8,0.15);"
                    " border-radius: 2px; padding: 0 3px; font-size: 9px;"
                    " font-weight: 700;"
                )
                rl.addWidget(badge)
            val = g.get("value", 0)
            v_lbl = QLabel(f"{_overlay_format_ped(val)} PED")
            v_lbl.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 12px; font-weight: 600;"
                " background: transparent;"
            )
            rl.addWidget(v_lbl)
            # Time
            ts = g.get("timestamp", "")
            t_lbl = QLabel(_overlay_time_ago(ts))
            t_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 10px; background: transparent;"
            )
            rl.addWidget(t_lbl)
            rc_layout.addWidget(row)

    def _fill_globals_top_players(self):
        """Fill the top players sub-container from stored data."""
        tc_layout = self._globals_top_container.layout()
        _clear_layout(tc_layout)
        data = getattr(self, "_globals_overlay_data", None)
        if not data:
            return
        top = data.get("top_players") or []
        if not top:
            return
        sort_key = getattr(self, "_globals_overlay_top_sort", "value")
        self._update_globals_sort_styles()
        sorted_top = sorted(
            top, key=lambda p: p.get(sort_key, 0), reverse=True,
        )[:10]
        for i, p in enumerate(sorted_top):
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 1, 0, 1)
            rl.setSpacing(4)
            rank_lbl = QLabel(f"#{i + 1}")
            rank_lbl.setFixedWidth(20)
            rank_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
            )
            rl.addWidget(rank_lbl)
            name = p.get("player", "?")
            if p.get("is_team"):
                name = "[T] " + name
            n_lbl = _ElidedLabel(name)
            n_lbl.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;"
            )
            rl.addWidget(n_lbl, 1)
            cnt = p.get("count", 0)
            c_lbl = QLabel(f"{cnt:,}")
            c_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
            )
            rl.addWidget(c_lbl)
            total = p.get("value", 0)
            t_lbl = QLabel(f"{_overlay_format_ped(total)} PED")
            t_lbl.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 12px; font-weight: 600;"
                " background: transparent;"
            )
            rl.addWidget(t_lbl)
            tc_layout.addWidget(row)

    # --- Globals: style helpers ---

    def _update_globals_period_styles(self):
        """Restyle period buttons to reflect the active period."""
        current = self._globals_overlay_period
        for p, btn in self._globals_period_buttons.items():
            active = p == current
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {ACCENT if active else 'transparent'};"
                f"  color: {'#fff' if active else TEXT_DIM};"
                f"  border: 1px solid {ACCENT if active else BORDER};"
                f"  border-radius: 2px; font-size: 10px;"
                f"  padding: 2px 8px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  color: {'#fff' if active else TEXT_COLOR};"
                f"  border-color: {ACCENT};"
                f"}}"
            )

    def _update_globals_sort_styles(self):
        """Restyle sort buttons to reflect the active sort key."""
        current = getattr(self, "_globals_overlay_top_sort", "value")
        for sk, sbtn in self._globals_sort_buttons.items():
            active = sk == current
            sbtn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {ACCENT if active else 'transparent'};"
                f"  color: {'#fff' if active else TEXT_DIM};"
                f"  border: 1px solid {ACCENT if active else BORDER};"
                f"  border-radius: 2px; font-size: 10px;"
                f"  padding: 1px 6px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  color: {'#fff' if active else TEXT_COLOR};"
                f"  border-color: {ACCENT};"
                f"}}"
            )

    # --- Globals: period / sort handlers ---

    def _on_globals_overlay_period(self, period: str):
        """Refetch globals data for a different period.

        Keeps the skeleton intact — updates button styles and stat labels
        immediately, clears only the dynamic sub-containers.
        """
        self._globals_overlay_period = period
        dc = getattr(self, "_data_client", None)
        mob_name = getattr(self, "_globals_overlay_mob_name", "")
        if not dc or not mob_name:
            return

        if getattr(self, "_globals_skeleton_built", False):
            # Update period buttons immediately
            self._update_globals_period_styles()
            # Set stat labels to loading placeholder
            for lbl in self._globals_stat_labels.values():
                lbl.setText("-")
            # Show loading message, clear dynamic sections
            self._globals_message_label.setText("Loading\u2026")
            self._globals_message_label.setVisible(True)
            self._globals_recent_title.setVisible(False)
            _clear_layout(self._globals_recent_container.layout())
            self._globals_top_header.setVisible(False)
            _clear_layout(self._globals_top_container.layout())

        import threading as _th

        def fetch():
            data = dc.get_mob_globals(mob_name, period=period)
            invoke_on_main(lambda d=data: self._replace_globals_overlay(d))

        _th.Thread(target=fetch, daemon=True, name="overlay-mob-globals-refetch").start()

    def _replace_globals_overlay(self, data: dict):
        """Update globals tab content after a period change."""
        if getattr(self, "_globals_skeleton_built", False):
            # Skeleton exists — update data in place
            try:
                self._fill_globals_data(data)
            except Exception:
                log.exception("Failed to update globals overlay")
                self._globals_message_label.setText("Error loading globals")
                self._globals_message_label.setVisible(True)
        else:
            # No skeleton yet — full build (shouldn't normally happen)
            layout = getattr(self, "_globals_overlay_layout", None)
            if not layout:
                return
            _clear_layout(layout)
            self._globals_overlay_loading = None
            try:
                self._populate_globals_overlay_inner(data, layout)
            except Exception:
                log.exception("Failed to populate globals overlay")
                err = QLabel("Error loading globals")
                err.setStyleSheet(
                    f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
                )
                err.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(err)

    def _on_globals_overlay_sort(self, sort_key: str):
        """Re-sort top players in overlay without refetching."""
        self._globals_overlay_top_sort = sort_key
        if getattr(self, "_globals_skeleton_built", False):
            self._fill_globals_top_players()
        else:
            data = getattr(self, "_globals_overlay_data", None)
            if data:
                self._replace_globals_overlay(data)

    # ----- Mission: Steps tab -----

    def _build_steps_content(self, item: dict) -> QWidget:
        steps = item.get("Steps") or item.get("Objectives") or []
        if not steps:
            return _make_centered_label("No step information")
        widget, layout = _details_container()
        for i, step in enumerate(steps):
            idx = step.get("Index", i + 1)
            title = step.get("Title") or step.get("Objective") or step.get("Type") or ""
            desc = step.get("Description") or ""
            objectives = step.get("Objectives") or []
            box = QWidget()
            box.setStyleSheet("background: transparent;")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(0, 2, 0, 2)
            bl.setSpacing(1)
            # Step header
            hdr_text = f"#{idx}"
            if title:
                hdr_text += f"  {title}"
            hdr = QLabel(hdr_text)
            hdr.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 11px; font-weight: 500;"
                " background: transparent;"
            )
            hdr.setWordWrap(True)
            bl.addWidget(hdr)
            # Objectives
            for obj in objectives:
                obj_type = obj.get("Type") or ""
                payload = obj.get("Payload") or {}
                target = payload.get("TargetName") or payload.get("Target") or ""
                amount = payload.get("Amount") or payload.get("Quantity") or ""
                parts = [p for p in [obj_type, target,
                                     str(amount) if amount else ""] if p]
                if parts:
                    obj_lbl = QLabel("  " + " - ".join(parts))
                    obj_lbl.setStyleSheet(
                        f"color: {TEXT_DIM}; font-size: 10px;"
                        " background: transparent;"
                    )
                    obj_lbl.setWordWrap(True)
                    bl.addWidget(obj_lbl)
            if desc and not objectives:
                d_lbl = QLabel(f"  {desc}")
                d_lbl.setStyleSheet(
                    f"color: {TEXT_DIM}; font-size: 10px;"
                    " background: transparent;"
                )
                d_lbl.setWordWrap(True)
                bl.addWidget(d_lbl)
            layout.addWidget(box)
        layout.addStretch(1)
        return widget

    # ----- Mission: Rewards tab -----

    def _build_rewards_content(self, item: dict) -> QWidget:
        rewards = item.get("Rewards")
        if not rewards:
            return _make_centered_label("No reward information")
        widget, layout = _details_container()
        emit = self._handle_entity_click
        # Rewards can be a dict (single package) or list (choices)
        packages = rewards if isinstance(rewards, list) else [rewards]
        for pkg_idx, pkg in enumerate(packages):
            if isinstance(pkg, dict):
                if len(packages) > 1:
                    layout.addWidget(_section_label(f"Choice {pkg_idx + 1}"))
                items = pkg.get("Items") or []
                skills = pkg.get("Skills") or []
                unlocks = pkg.get("Unlocks") or []
                for ri in items:
                    name = ri.get("itemName") or ri.get("Name") or "?"
                    qty = ri.get("quantity") or ri.get("Amount")
                    rarity = ri.get("rarity") or ""
                    info = fmt_int(qty) if qty else ""
                    if rarity and rarity != "guaranteed":
                        info = f"{info} ({rarity})" if info else rarity
                    entity = {"Name": name, "Type": "Material"}
                    layout.addWidget(_acq_row(name, info, entity, emit))
                for si in skills:
                    name = si.get("skillName") or si.get("Name") or "?"
                    ped = si.get("pedValue")
                    info = f"{_fv(ped, 2)} PED" if ped else ""
                    entity = {"Name": name, "Type": "Skill"}
                    layout.addWidget(_acq_row(name, info, entity, emit))
                for u in unlocks:
                    layout.addWidget(_acq_row(
                        str(u), "Unlock", None, emit))
        layout.addStretch(1)
        return widget

    # ----- Vendor: Offers tab -----

    def _build_offers_content(self, item: dict) -> QWidget:
        offers = item.get("Offers") or []
        if not offers:
            return _make_centered_label("No offers available")
        widget, layout = _details_container()
        emit = self._handle_entity_click
        for offer in offers:
            offer_item = offer.get("Item") or {}
            name = offer_item.get("Name") or "?"
            item_type = deep_get(offer_item, "Properties", "Type") or "Material"
            is_limited = offer.get("IsLimited")
            prices = offer.get("Prices") or []
            # Price summary
            price_parts = []
            for p in prices:
                p_item = p.get("Item") or {}
                p_name = p_item.get("Name") or "?"
                p_amount = p.get("Amount")
                if p_amount:
                    price_parts.append(f"{fmt_int(p_amount)} {p_name}")
                else:
                    price_parts.append(p_name)
            info = ", ".join(price_parts) if price_parts else ""
            if is_limited:
                info = f"[L] {info}" if info else "[Limited]"
            entity = {"Name": name, "Type": item_type}
            layout.addWidget(_acq_row(name, info, entity, emit))
        layout.addStretch(1)
        return widget

    # ----- Location: Map tab -----

    def _build_map_content(self, item: dict) -> QWidget:
        """Embedded map showing the location with interactive MapCanvas."""
        from ..ui.widgets.map_canvas import MapCanvas

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(container)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        coords = deep_get(item, "Properties", "Coordinates") or {}
        planet = deep_get(item, "Planet", "Name") or ""
        name = item.get("Name") or ""
        lon = coords.get("Longitude")
        lat = coords.get("Latitude")

        # Compact header with coordinate info + buttons
        if lon is not None and lat is not None:
            hdr = QWidget()
            hdr.setStyleSheet("background: transparent;")
            hl = QHBoxLayout(hdr)
            hl.setContentsMargins(6, 2, 6, 2)
            hl.setSpacing(4)
            coord_lbl = QLabel(f"{planet}  {lon:.0f}, {lat:.0f}")
            coord_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 10px; background: transparent;"
            )
            hl.addWidget(coord_lbl)
            hl.addWidget(_overlay_waypoint_btn(planet, coords, name))
            hl.addWidget(_overlay_map_btn(planet, item.get("Id")))
            hl.addStretch(1)
            vl.addWidget(hdr)

        # MapCanvas
        canvas = MapCanvas(parent=container)
        canvas.setMinimumHeight(200)
        canvas.hide()
        vl.addWidget(canvas, 1)
        self._map_canvas = canvas

        # Loading label (shown until map data arrives)
        loading = QLabel("Loading map...")
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
        )
        vl.addWidget(loading, 1)
        self._map_loading = loading

        # Connect canvas click to open entity
        canvas.location_clicked.connect(self._on_map_location_clicked)

        # Start background fetch
        if planet:
            self._fetch_map_data(planet, item)
        else:
            loading.setText("No planet data")

        return container

    def _build_unlocks_content(self, item: dict) -> QWidget:
        """Build the Unlocked By (skills) or Skill Unlocks (professions) tab."""
        unlocks = item.get("Unlocks") or []
        if not unlocks:
            return _make_centered_label("No unlock data")

        widget, layout = _details_container()
        page_type = self._page_type_id

        if page_type == "skills":
            # Skill is unlocked BY professions
            layout.addWidget(_section_label("Unlocked By"))
            sorted_unlocks = sorted(unlocks, key=lambda u: u.get("Level") or 0)
            for u in sorted_unlocks:
                prof_name = deep_get(u, "Profession", "Name") or u.get("Name") or "?"
                level = u.get("Level")
                layout.addWidget(_stat_row(
                    prof_name,
                    f"Level {level}" if level is not None else "-",
                    entity={"Name": prof_name, "Type": "Profession"},
                    on_click=self._handle_entity_click,
                ))
        else:
            # Profession unlocks skills
            layout.addWidget(_section_label("Skill Unlocks"))
            sorted_unlocks = sorted(unlocks, key=lambda u: u.get("Level") or 0)
            for u in sorted_unlocks:
                skill_name = deep_get(u, "Skill", "Name") or u.get("Name") or "?"
                level = u.get("Level")
                layout.addWidget(_stat_row(
                    skill_name,
                    f"Level {level}" if level is not None else "-",
                    entity={"Name": skill_name, "Type": "Skill"},
                    on_click=self._handle_entity_click,
                ))

        layout.addStretch(1)
        return widget

    # ----- Pet: Effects tab -----

    def _build_effects_content(self, item: dict) -> QWidget:
        """Build the Effects tab for pets."""
        effects = item.get("Effects") or item.get("EffectsOnEquip") or []
        if not effects:
            return _make_centered_label("No effects")

        sorted_effects = sorted(
            effects,
            key=lambda e: (
                deep_get(e, "Properties", "Unlock", "Level")
                or e.get("UnlockLevel") or 0
            ),
        )

        widget, layout = _details_container()

        for e in sorted_effects:
            eff_name = e.get("Name", "Unknown")
            strength = deep_get(e, "Properties", "Strength")
            unit = deep_get(e, "Properties", "Unit") or ""
            strength_str = f"{strength}{unit}" if strength is not None else "-"

            layout.addWidget(_section_label(eff_name))
            layout.addWidget(_stat_row("Strength", strength_str))

            upkeep = deep_get(e, "Properties", "NutrioConsumptionPerHour")
            if upkeep is not None:
                layout.addWidget(_stat_row("Upkeep", f"{upkeep}/h"))

            unlock = deep_get(e, "Properties", "Unlock") or {}
            if not unlock:
                unlock_level = e.get("UnlockLevel")
                if unlock_level:
                    layout.addWidget(_stat_row("Level", str(unlock_level)))
            else:
                unlock_level = unlock.get("Level")
                if unlock_level is not None:
                    layout.addWidget(_stat_row("Level", str(unlock_level)))

                cost_parts = []
                cost_ped = unlock.get("CostPED")
                if cost_ped and cost_ped > 0:
                    cost_parts.append(f"{cost_ped:.2f} PED")
                cost_essence = unlock.get("CostEssence")
                if cost_essence and cost_essence > 0:
                    cost_parts.append(f"{cost_essence} Animal Essence")
                cost_rare = unlock.get("CostRareEssence")
                if cost_rare and cost_rare > 0:
                    cost_parts.append(f"{cost_rare} Rare Animal Essence")
                if cost_parts:
                    layout.addWidget(_stat_row("Cost", cost_parts[0]))
                    for part in cost_parts[1:]:
                        layout.addWidget(_stat_row("", part))

                criteria = unlock.get("Criteria")
                if criteria:
                    criteria_val = unlock.get("CriteriaValue")
                    crit_str = (
                        f"{criteria} ({criteria_val})"
                        if criteria_val is not None else criteria
                    )
                    layout.addWidget(_stat_row("Criteria", crit_str))

        layout.addStretch(1)
        return widget

    def _fetch_map_data(self, planet_name: str, item: dict):
        """Background: fetch planet dict, locations, and map image."""
        dc = self._data_client
        base_url = getattr(self._config, "nexus_base_url", "https://entropianexus.com")

        def fetch():
            try:
                planets = dc.get_planets()
                planet = next(
                    (p for p in planets if p.get("Name") == planet_name), None,
                )
                if not planet:
                    return

                locations = dc.get_locations_for_planet(planet_name)

                # Load planet image
                slug = re.sub(r"[^0-9a-zA-Z]", "", planet_name).lower()
                cache_dir = os.path.join(
                    os.path.dirname(__file__), "..", "data", "cache", "maps",
                )
                os.makedirs(cache_dir, exist_ok=True)
                cache_path = os.path.join(cache_dir, f"{slug}.jpg")

                if os.path.exists(cache_path):
                    pm = QPixmap(cache_path)
                    if not pm.isNull():
                        self._map_data_ready.emit(planet, pm, locations)
                        return

                import requests
                url = f"{base_url}/{slug}.jpg"
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                with open(cache_path, "wb") as f:
                    f.write(resp.content)
                pm = QPixmap(cache_path)
                if not pm.isNull():
                    self._map_data_ready.emit(planet, pm, locations)
            except Exception:
                pass

        threading.Thread(
            target=fetch, daemon=True, name="detail-overlay-map",
        ).start()

    def _on_map_data_ready(self, planet: dict, pixmap: QPixmap, locations: list):
        """Main thread: set planet data on the embedded MapCanvas."""
        canvas = self._map_canvas
        if not canvas:
            return
        canvas.set_planet(planet, pixmap, locations)
        # Center on the current location
        item = self._full_item
        if item:
            canvas.center_on(item, zoom=1.5)
            loc_id = item.get("Id")
            if loc_id:
                canvas.set_selected(loc_id)
        # Show canvas, hide loading
        canvas.show()
        if hasattr(self, "_map_loading") and self._map_loading:
            self._map_loading.hide()

    def _on_map_location_clicked(self, location: dict | None):
        """Handle click on a map location — open as entity."""
        if not location:
            return
        name = location.get("Name") or ""
        loc_type = location.get("Type") or "Location"
        if name:
            self._handle_entity_click({"Name": name, "Type": loc_type})

    # --- Content builders (Acquisition / Usage) ---

    def _build_acquisition_content(self, data: dict) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        emit = self._handle_entity_click
        pills: list[tuple[str, QWidget]] = []

        # --- Build sections (each in its own container for pill targeting) ---

        # Vendor Offers
        vendor_offers = data.get("VendorOffers") or []
        if vendor_offers:
            sec = QWidget()
            sec.setStyleSheet("background: transparent;")
            sl = QVBoxLayout(sec)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(2)
            sl.addWidget(_section_label("Vendors"))
            for offer in vendor_offers:
                v_name = deep_get(offer, "Vendor", "Name") or "?"
                planet = deep_get(offer, "Vendor", "Planet", "Name") or ""
                limited = " (Ltd)" if offer.get("IsLimited") else ""
                info = f"{limited} — {planet}" if planet else limited
                sl.addWidget(_acq_row(
                    v_name, info, {"Name": v_name, "Type": "Vendor"}, emit,
                ))
            pills.append(("Vendors", sec))
            layout.addWidget(sec)

        # Loot Sources
        loots = data.get("Loots") or []
        if loots:
            sec = QWidget()
            sec.setStyleSheet("background: transparent;")
            sl = QVBoxLayout(sec)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(2)
            sl.addWidget(_section_label("Loot Sources"))
            for loot in loots:
                mob_name = deep_get(loot, "Mob", "Name") or "?"
                maturity = deep_get(loot, "Maturity", "Name") or ""
                freq = loot.get("Frequency", "")
                parts = []
                if maturity:
                    parts.append(maturity)
                if freq:
                    parts.append(f"({freq})")
                sl.addWidget(_acq_row(
                    mob_name, " ".join(parts),
                    {"Name": mob_name, "Type": "Mob"}, emit,
                ))
            pills.append(("Loot", sec))
            layout.addWidget(sec)

        # Market (player shops — not clickable)
        shop_listings = data.get("ShopListings") or []
        if shop_listings:
            sec = QWidget()
            sec.setStyleSheet("background: transparent;")
            sl = QVBoxLayout(sec)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(2)
            sl.addWidget(_section_label("Market"))
            for listing in shop_listings:
                shop_name = deep_get(listing, "Shop", "Name") or "?"
                planet = deep_get(listing, "Shop", "Planet", "Name") or ""
                markup = listing.get("Markup")
                mu = f" {markup:.0f}%" if markup else ""
                info = f"{mu} — {planet}" if planet else mu
                sl.addWidget(_acq_row(shop_name, info, None, None))
            pills.append(("Market", sec))
            layout.addWidget(sec)

        # Crafted By (blueprints)
        blueprints = data.get("Blueprints") or []
        if blueprints:
            sec = QWidget()
            sec.setStyleSheet("background: transparent;")
            sl = QVBoxLayout(sec)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(2)
            sl.addWidget(_section_label("Crafted By"))
            for bp in blueprints:
                bp_name = bp.get("Name", "?")
                level = deep_get(bp, "Properties", "Level")
                prof = deep_get(bp, "Profession", "Name") or ""
                parts = []
                if level:
                    parts.append(f"L{level}")
                if prof:
                    parts.append(f"({prof})")
                sl.addWidget(_acq_row(
                    bp_name, " ".join(parts),
                    {"Name": bp_name, "Type": "Blueprint"}, emit,
                ))
            pills.append(("Crafted", sec))
            layout.addWidget(sec)

        # Blueprint Discovery
        bp_drops = data.get("BlueprintDrops") or []
        if bp_drops:
            sec = QWidget()
            sec.setStyleSheet("background: transparent;")
            sl = QVBoxLayout(sec)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(2)
            sl.addWidget(_section_label("BP Discovery"))
            for bp in bp_drops:
                bp_name = bp.get("Name", "?")
                level = deep_get(bp, "Properties", "Level")
                info = f"L{level}" if level else ""
                sl.addWidget(_acq_row(
                    bp_name, info,
                    {"Name": bp_name, "Type": "Blueprint"}, emit,
                ))
            pills.append(("BP Disc.", sec))
            layout.addWidget(sec)

        # Refining Recipes
        recipes = data.get("RefiningRecipes") or []
        if recipes:
            item_name = data.get("_item_name") or ""
            sec = QWidget()
            sec.setStyleSheet("background: transparent;")
            sl = QVBoxLayout(sec)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(6)
            sl.addWidget(_section_label("Refined From"))
            for recipe in recipes:
                sl.addWidget(_recipe_card(
                    recipe, emit,
                    link_product=False,
                    link_ingredients=True,
                    current_name=item_name,
                ))
            pills.append(("Refined", sec))
            layout.addWidget(sec)

        # --- Sub-nav bar (only if 2+ sections) ---
        if len(pills) >= 2:
            layout.insertWidget(0, _sub_nav_bar(pills, self._tab_scrolls.get(TAB_ACQUISITION)))

        if not pills:
            layout.addWidget(_make_centered_label("No acquisition data"))
            url = self._get_exchange_url()
            if url:
                layout.addWidget(_make_exchange_link(
                    "Create a sell order on the Exchange", url,
                ))

        layout.addStretch(1)
        return widget

    def _build_usage_content(self, data: dict) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        emit = self._handle_entity_click
        pills: list[tuple[str, QWidget]] = []

        # Blueprints using this item as material
        blueprints = data.get("Blueprints") or []
        if blueprints:
            sec = QWidget()
            sec.setStyleSheet("background: transparent;")
            sl = QVBoxLayout(sec)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(2)
            sl.addWidget(_section_label("Blueprints"))
            for bp in blueprints:
                bp_name = bp.get("Name", "?")
                level = deep_get(bp, "Properties", "Level")
                amount = bp.get("Amount")
                parts = []
                if level:
                    parts.append(f"L{level}")
                if amount:
                    parts.append(f"x{amount}")
                sl.addWidget(_acq_row(
                    bp_name, " ".join(parts),
                    {"Name": bp_name, "Type": "Blueprint"}, emit,
                ))
            pills.append(("Blueprints", sec))
            layout.addWidget(sec)

        # Missions requiring this item
        missions = data.get("Missions") or []
        if missions:
            sec = QWidget()
            sec.setStyleSheet("background: transparent;")
            sl = QVBoxLayout(sec)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(2)
            sl.addWidget(_section_label("Missions"))
            for m in missions:
                m_name = m.get("Name", "?")
                m_type = deep_get(m, "Properties", "Type") or ""
                planet = deep_get(m, "Planet", "Name") or ""
                parts = []
                if m_type:
                    parts.append(m_type)
                if planet:
                    parts.append(f"({planet})")
                sl.addWidget(_acq_row(
                    m_name, " ".join(parts),
                    {"Name": m_name, "Type": "Mission"}, emit,
                ))
            pills.append(("Missions", sec))
            layout.addWidget(sec)

        # Vendor Currency (vendors accepting this as payment)
        vendor_offers = data.get("VendorOffers") or []
        currency_offers = [
            vo for vo in vendor_offers if vo.get("Prices")
        ]
        if currency_offers:
            sec = QWidget()
            sec.setStyleSheet("background: transparent;")
            sl = QVBoxLayout(sec)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(2)
            sl.addWidget(_section_label("Vendor Currency"))
            for vo in currency_offers:
                v_name = deep_get(vo, "Vendor", "Name") or "?"
                planet = deep_get(vo, "Vendor", "Planet", "Name") or ""
                info = f"— {planet}" if planet else ""
                sl.addWidget(_acq_row(
                    v_name, info,
                    {"Name": v_name, "Type": "Vendor"}, emit,
                ))
                # Show what the vendor offers in exchange
                for price in (vo.get("Prices") or []):
                    item_name = deep_get(price, "Item", "Name")
                    item_type = deep_get(
                        price, "Item", "Properties", "Type",
                    ) or "Material"
                    amount = price.get("Amount")
                    if item_name:
                        p_info = f"x{amount}" if amount else ""
                        sl.addWidget(_acq_row(
                            f"  → {item_name}", p_info,
                            {"Name": item_name, "Type": item_type}, emit,
                        ))
            pills.append(("Vendor", sec))
            layout.addWidget(sec)

        # Refining Recipes using this item
        recipes = data.get("RefiningRecipes") or []
        if recipes:
            item_name = data.get("_item_name") or ""
            sec = QWidget()
            sec.setStyleSheet("background: transparent;")
            sl = QVBoxLayout(sec)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(6)
            sl.addWidget(_section_label("Refining"))
            for recipe in recipes:
                sl.addWidget(_recipe_card(
                    recipe, emit,
                    link_product=True,
                    link_ingredients=True,
                    current_name=item_name,
                ))
            pills.append(("Refined", sec))
            layout.addWidget(sec)

        # Sub-nav bar (only if 2+ sections)
        if len(pills) >= 2:
            layout.insertWidget(0, _sub_nav_bar(pills, self._tab_scrolls.get(TAB_USAGE)))

        if not pills:
            layout.addWidget(_make_centered_label("No usage data"))
            url = self._get_exchange_url()
            if url:
                layout.addWidget(_make_exchange_link(
                    "Create a buy order on the Exchange", url,
                ))

        layout.addStretch(1)
        return widget

    _WAYPOINT_SPAN_RE = re.compile(
        r'<span\b([^>]*?)\bdata-waypoint="([^"]*)"([^>]*)>(.*?)</span>',
        re.IGNORECASE | re.DOTALL,
    )
    _DATA_LABEL_RE = re.compile(r'data-label="([^"]*)"')

    def _build_description_content(self, desc: str) -> QWidget:
        from PyQt6.QtWidgets import QTextBrowser, QApplication, QToolTip
        from PyQt6.QtGui import QCursor

        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Check if description contains HTML tags
        has_html = bool(re.search(r"<[^>]+>", desc))

        if has_html:
            # Transform waypoint spans into clickable links
            def _replace_wp(m):
                waypoint = m.group(2)
                attrs_rest = m.group(1) + m.group(3)
                label_m = self._DATA_LABEL_RE.search(attrs_rest)
                label = label_m.group(1) if label_m else (m.group(4) or waypoint)
                return (
                    f'<a href="waypoint:{waypoint}" '
                    f'style="color: {ACCENT}; background-color: rgba(0,204,255,0.12); '
                    f'border: 1px solid {ACCENT}; border-radius: 3px; '
                    f'padding: 0 4px; font-family: Consolas, monospace; '
                    f'text-decoration: none;" '
                    f'title="Click to copy waypoint: /wp {waypoint}">'
                    f'\u29C9 {label}</a>'
                )
            processed = self._WAYPOINT_SPAN_RE.sub(_replace_wp, desc)

            browser = QTextBrowser()
            browser.setOpenExternalLinks(False)
            browser.setStyleSheet(
                f"QTextBrowser {{ background: transparent; color: {TEXT_COLOR};"
                f" font-size: 12px; border: none; }}"
                f"QTextBrowser a {{ color: {ACCENT}; }}"
            )
            browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            browser.setHtml(
                f'<div style="color: {TEXT_COLOR}; font-size: 12px;">{processed}</div>'
            )

            def _on_link(url):
                url_str = url.toString()
                if url_str.startswith("waypoint:"):
                    waypoint = url_str[len("waypoint:"):]
                    clipboard = QApplication.clipboard()
                    if clipboard:
                        clipboard.setText(f"/wp {waypoint}")
                    QToolTip.showText(
                        QCursor.pos(), "Copied!", browser, browser.rect(), 1500
                    )
                else:
                    webbrowser.open(url_str)

            browser.anchorClicked.connect(_on_link)
            # Size to content
            doc = browser.document()
            doc.setTextWidth(browser.viewport().width() or 280)
            browser.setFixedHeight(int(doc.size().height()) + 8)
            layout.addWidget(browser)
        else:
            lbl = QLabel(desc)
            lbl.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;"
            )
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

        layout.addStretch(1)
        return widget

    # --- Scroll wrapper ---

    @staticmethod
    def _make_scroll(widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:vertical {"
            "  background: transparent; width: 6px;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(100, 100, 120, 150); border-radius: 3px;"
            "  min-height: 20px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "  height: 0;"
            "}"
        )
        scroll.setWidget(widget)
        return scroll

    # --- Mouse events: click-vs-drag on title bar ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_origin = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        click_origin = self._click_origin
        self._click_origin = None
        super().mouseReleaseEvent(event)

        if click_origin and event.button() == Qt.MouseButton.LeftButton:
            delta = (
                event.globalPosition().toPoint() - click_origin
            ).manhattanLength()
            if delta < 5:
                # Click (not drag) — toggle minify if in title bar area
                click_local = self.mapFromGlobal(click_origin)
                title_bottom = self._title_bar.mapTo(
                    self, QPoint(0, self._title_bar.height()),
                ).y()
                if click_local.y() <= title_bottom:
                    self._toggle_minify()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "_calc_stats_panel"):
            self._position_calc_stats_panel()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_calc_stats_panel"):
            self._position_calc_stats_panel()

    def closeEvent(self, event):
        if hasattr(self, "_calc_stats_panel"):
            self._calc_stats_panel.close()
        super().closeEvent(event)

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, "_calc_stats_panel"):
            self._calc_stats_panel.hide()

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "_calc_stats_panel") and self._body.isVisible():
            idx = self._content_stack.currentIndex()
            if idx < len(self._tab_ids) and self._tab_ids[idx] == TAB_CALCULATOR:
                self._calc_stats_panel.show()
                self._position_calc_stats_panel()


# ---------------------------------------------------------------------------
# Module-level helpers (stateless, no self)
# ---------------------------------------------------------------------------

def _fv(value, decimals: int) -> str:
    """Format a numeric value with *decimals* decimal places, or '-'."""
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color: {SECTION_COLOR}; font-size: 10px; font-weight: bold;"
        f" background: transparent; padding: 4px 0 1px 0;"
        f" letter-spacing: 0.5px;"
    )
    return lbl


def _sub_nav_pill(label: str, scroll_area: QScrollArea, target: QWidget) -> QPushButton:
    """Small pill button that scrolls to *target* inside *scroll_area*."""
    btn = QPushButton(label)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{"
        f"  background: {BADGE_BG}; color: {TEXT_DIM}; font-size: 10px;"
        f"  border: none; border-radius: 8px; padding: 2px 6px;"
        f"}}"
        f"QPushButton:hover {{"
        f"  background: {TAB_ACTIVE_BG}; color: {ACCENT};"
        f"}}"
    )
    btn.clicked.connect(
        lambda: scroll_area.ensureWidgetVisible(target, 0, 10)
    )
    return btn


def _sub_nav_bar(
    pills: list[tuple[str, QWidget]],
    scroll_area: QScrollArea,
) -> QWidget:
    """Row of pill buttons for sub-navigation within a scroll area."""
    bar = QWidget()
    bar.setStyleSheet("background: transparent;")
    hl = QHBoxLayout(bar)
    hl.setContentsMargins(0, 2, 0, 4)
    hl.setSpacing(4)
    for label, target in pills:
        hl.addWidget(_sub_nav_pill(label, scroll_area, target))
    hl.addStretch(1)
    return bar


def _entity_click_handler(entity: dict, callback):
    """Return a mousePressEvent handler that calls *callback* with an entity dict.

    Middle-click sets ``_force_new`` so the app always opens a new overlay window.
    """
    def handler(ev):
        d = dict(entity)
        if ev.button() == Qt.MouseButton.MiddleButton:
            d["_force_new"] = True
        callback(d)
    return handler


def _stat_row(label: str, value: str, *, label_color: str = TEXT_DIM,
              highlight: bool = False,
              entity: dict | None = None,
              on_click=None) -> QWidget:
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    lbl = QLabel(label)
    if entity and on_click:
        lbl_color = ACCENT
        lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        lbl.mousePressEvent = _entity_click_handler(entity, on_click)
    else:
        lbl_color = label_color
    lbl.setStyleSheet(
        f"color: {lbl_color}; font-size: 12px; background: transparent;"
    )
    layout.addWidget(lbl)

    if highlight:
        val_color = HIGHLIGHT_COLOR
    else:
        val_color = TEXT_BRIGHT
    val = QLabel(value)
    val.setStyleSheet(
        f"color: {val_color}; font-size: 12px; font-weight: bold;"
        " background: transparent;"
    )
    val.setAlignment(Qt.AlignmentFlag.AlignRight)
    layout.addWidget(val)

    return row


def _overlay_format_ped(v) -> str:
    """Format a PED value compactly for overlay display."""
    if v is None:
        return "0"
    if v >= 1000:
        return f"{v / 1000:.1f}K"
    return f"{v:.2f}"


def _overlay_time_ago(date_str: str) -> str:
    """Convert ISO timestamp to relative time string."""
    if not date_str:
        return ""
    try:
        from datetime import datetime, timezone
        then = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - then
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h"
        days = hours // 24
        return f"{days}d"
    except (ValueError, TypeError):
        return ""


def _make_centered_label(text: str) -> QWidget:
    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(8, 8, 8, 8)

    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
    )
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(lbl)
    layout.addStretch(1)
    return widget


def _make_exchange_link(text: str, url: str) -> QPushButton:
    """Centered accent link that opens the exchange item page in the browser."""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background: transparent; border: none;"
        f" color: {ACCENT}; font-size: 11px; padding: 2px 0px; }}"
        f"QPushButton:hover {{ color: {ACCENT}; }}"
    )
    btn.clicked.connect(lambda: webbrowser.open(url))
    return btn


def _clear_layout(layout):
    """Remove and delete all child widgets from a layout."""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()


def _details_container() -> tuple[QWidget, QVBoxLayout]:
    """Create a standard container widget+layout for detail content."""
    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(6, 4, 6, 4)
    layout.setSpacing(1)
    return widget, layout


def _acq_row(
    name: str,
    info: str,
    entity: dict | None,
    on_click,
    freq_color: str | None = None,
) -> QWidget:
    """Acquisition row with optional clickable entity name.

    *entity* is an item dict ``{"Name": ..., "Type": ...}``; if provided the
    name label becomes accent-colored and clickable, emitting *on_click(entity)*.
    *freq_color* overrides the info label color (for frequency badges).
    """
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    hl = QHBoxLayout(row)
    hl.setContentsMargins(0, 1, 0, 1)
    hl.setSpacing(4)

    name_lbl = QLabel(name)
    if entity and on_click:
        name_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 12px; background: transparent;"
            " padding: 0; text-decoration: none;"
        )
        name_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        name_lbl.mousePressEvent = _entity_click_handler(entity, on_click)
    else:
        name_lbl.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;"
            " padding: 0;"
        )
    hl.addWidget(name_lbl)

    if info:
        info_c = freq_color or TEXT_DIM
        info_lbl = QLabel(info)
        info_lbl.setStyleSheet(
            f"color: {info_c}; font-size: 11px; background: transparent;"
            " padding: 0;"
        )
        hl.addWidget(info_lbl)

    hl.addStretch(1)
    return row


def _recipe_card(
    recipe: dict,
    emit,
    link_product: bool = False,
    link_ingredients: bool = True,
    current_name: str | None = None,
) -> QWidget:
    """Render a refining recipe as a styled card (matches web RefiningRecipesDisplay).

    Shows output line (``5x Material``) and ingredients line
    (``from: 10x Ore + 5x Stone``).
    """
    card = QWidget()
    card.setStyleSheet(
        f"background: {BADGE_BG};"
        f" border-left: 3px solid {ACCENT};"
        " border-radius: 6px;"
        " padding: 8px 10px;"
    )
    vl = QVBoxLayout(card)
    vl.setContentsMargins(0, 0, 0, 0)
    vl.setSpacing(4)

    # --- Output line: "{Amount}x {ProductName}" ---
    product = recipe.get("Product") or {}
    prod_name = product.get("Name") or "?"
    prod_type = deep_get(product, "Properties", "Type") or "Material"
    amount = recipe.get("Amount")
    amount_str = f"{amount}x " if amount else ""

    if link_product and prod_name != current_name and emit:
        amount_color = ACCENT
        name_html = (
            f'<span style="color:{ACCENT}; cursor:pointer;">{prod_name}</span>'
        )
    else:
        amount_color = TEXT_COLOR
        name_html = f'<span style="color:{TEXT_COLOR};">{prod_name}</span>'

    output_lbl = QLabel(
        f'<span style="color:{amount_color}; font-weight:bold;">{amount_str}</span>'
        f'{name_html}'
    )
    output_lbl.setStyleSheet(
        "font-size: 12px; background: transparent; padding: 0;"
    )
    output_lbl.setTextFormat(Qt.TextFormat.RichText)
    if link_product and prod_name != current_name and emit:
        output_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        output_lbl.mousePressEvent = _entity_click_handler(
            {"Name": prod_name, "Type": prod_type}, emit,
        )
    vl.addWidget(output_lbl)

    # --- Ingredients line: "from: 10x Ore + 5x Stone" ---
    ingredients = recipe.get("Ingredients") or []
    if ingredients:
        # Build a lookup for link-click resolution
        ing_lookup: dict[str, dict] = {}
        parts = [f'<span style="color:{TEXT_DIM};">from:</span>']
        for i, ing in enumerate(ingredients):
            if i > 0:
                parts.append(f'<span style="color:{TEXT_DIM};"> + </span>')
            ing_name = deep_get(ing, "Item", "Name") or "?"
            ing_type = deep_get(ing, "Item", "Properties", "Type") or "Material"
            ing_amount = ing.get("Amount")
            ing_amount_str = f"{ing_amount}x " if ing_amount else ""
            is_linked = (
                link_ingredients and ing_name != current_name and emit
            )
            if is_linked:
                ing_lookup[ing_name] = {"Name": ing_name, "Type": ing_type}
                parts.append(
                    f'<a href="{ing_name}" style="color:{ACCENT}; text-decoration:none;">'
                    f'{ing_amount_str}{ing_name}</a>'
                )
            else:
                parts.append(
                    f'<span style="color:{TEXT_COLOR};">{ing_amount_str}{ing_name}</span>'
                )
        ing_lbl = QLabel(" ".join(parts))
        ing_lbl.setStyleSheet(
            "font-size: 11px; background: transparent; padding: 0;"
        )
        ing_lbl.setTextFormat(Qt.TextFormat.RichText)
        ing_lbl.setWordWrap(True)
        if ing_lookup and emit:
            ing_lbl.linkActivated.connect(
                lambda name, lu=ing_lookup, cb=emit: cb(lu[name]) if name in lu else None
            )
        vl.addWidget(ing_lbl)

    return card


def _overlay_waypoint_btn(planet: str, coords: dict, name: str) -> QPushButton:
    """Compact waypoint copy button for the overlay."""
    from PyQt6.QtWidgets import QApplication

    try:
        lon = float(coords["Longitude"])
        lat = float(coords["Latitude"])
        alt = float(coords["Altitude"]) if coords.get("Altitude") is not None else 100
    except (TypeError, ValueError, KeyError):
        lon = lat = 0
        alt = 100
    clean_name = name.replace(",", "").strip()[:50]
    wp = f"/wp [{planet}, {lon:.0f}, {lat:.0f}, {alt:.0f}, {clean_name}]"
    btn = QPushButton()
    btn.setFixedSize(20, 18)
    btn.setIcon(svg_icon(_COPY_SVG, TEXT_DIM, 14))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip(wp)
    btn.setStyleSheet(
        "QPushButton { background: transparent; border: none;"
        " border-radius: 3px; padding: 0; }"
        f"QPushButton:hover {{ background-color: {TAB_HOVER_BG}; }}"
    )

    def _copy():
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(wp)
        btn.setIcon(svg_icon(_CHECK_SVG, SUCCESS_COLOR, 14))
        QTimer.singleShot(1500, lambda: btn.setIcon(svg_icon(_COPY_SVG, TEXT_DIM, 14)))

    btn.clicked.connect(_copy)
    return btn


def _overlay_map_btn(planet: str, location_id: int | None) -> QPushButton:
    """Small map button that navigates to the maps page."""
    from PyQt6.QtWidgets import QApplication

    btn = QPushButton()
    btn.setFixedSize(20, 18)
    btn.setIcon(svg_icon(_TAB_MAP_SVG, TEXT_DIM, 14))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip("Open on map")
    btn.setStyleSheet(
        "QPushButton { background: transparent; border: none;"
        " border-radius: 3px; padding: 0; }"
        f"QPushButton:hover {{ background-color: {TAB_HOVER_BG}; }}"
    )

    def _open():
        if not planet or not location_id:
            return
        # Prefer map overlay if available
        if _map_overlay_callback is not None:
            _map_overlay_callback(planet, location_id)
            return
        # Fallback: navigate to Maps tab
        app = QApplication.instance()
        if not app:
            return
        for w in app.topLevelWidgets():
            if hasattr(w, "_ensure_page"):
                from ..ui.main_window import PAGE_MAPS
                if not w.isVisible():
                    w.show()
                w.activateWindow()
                w.raise_()
                w._sidebar.set_active(PAGE_MAPS)
                maps_page = w._ensure_page(PAGE_MAPS)
                if hasattr(maps_page, "navigate_to_location"):
                    maps_page.navigate_to_location(planet, location_id)
                break

    btn.clicked.connect(_open)
    return btn


# ---------------------------------------------------------------------------
# Compact overlay damage bars (presentation only — data from shared helpers)
# ---------------------------------------------------------------------------

def _overlay_damage_bars(damage_spread: dict, label: str = "",
                         is_pct: bool = True,
                         show_total: bool = False) -> QWidget:
    """Compact horizontal damage bars using overlay theme colors."""
    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 2, 0, 2)
    layout.setSpacing(3)

    if label:
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; font-weight: 600;"
            " background: transparent; letter-spacing: 0.5px;"
        )
        layout.addWidget(lbl)

    active = [(dt, damage_spread.get(dt) or 0)
              for dt in _DAMAGE_TYPES if (damage_spread.get(dt) or 0) > 0]

    if not active:
        return widget

    if show_total:
        total = sum(v for _, v in active)
        layout.addWidget(_stat_row("Total", f"{total:.1f}"))
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(100, 100, 120, 80);")
        layout.addWidget(sep)

    max_val = max(v for _, v in active)

    for dtype, val in active:
        color = DAMAGE_COLORS.get(dtype, TEXT_DIM)
        pct = (val / max_val * 100) if max_val > 0 else 0

        row = QWidget()
        row.setStyleSheet("background: transparent;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)

        type_lbl = QLabel(dtype)
        type_lbl.setFixedWidth(_TYPE_LABEL_W)
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
        fill_stretch = max(int(pct), 1)
        empty_stretch = max(100 - fill_stretch, 0)
        bar_layout.addWidget(bar_fill, fill_stretch)
        if empty_stretch > 0:
            spacer = QWidget()
            spacer.setStyleSheet("background: transparent;")
            bar_layout.addWidget(spacer, empty_stretch)

        rl.addWidget(bar_container, 1)

        val_lbl = QLabel(f"{val:.1f}%" if is_pct else f"{val:.1f}")
        val_lbl.setFixedWidth(38)
        val_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        val_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
        )
        rl.addWidget(val_lbl)

        layout.addWidget(row)

    return widget



    return widget


# ---------------------------------------------------------------------------
# Skill section helper (shared by weapon, medical, tool builders)
# ---------------------------------------------------------------------------

def _add_skill_section(layout: QVBoxLayout, item: dict) -> None:
    """Append SiB / Profession / Level Range rows if data exists."""
    is_sib = deep_get(item, "Properties", "Skill", "IsSiB")
    profession = deep_get(item, "Profession", "Name")
    # Hit profession for weapons
    hit_prof = deep_get(item, "ProfessionHit", "Name")
    dmg_prof = deep_get(item, "ProfessionDmg", "Name")

    # Skill level ranges — try both flat and nested locations
    hit_start = (deep_get(item, "Properties", "Skill", "Hit", "LearningIntervalStart")
                 or deep_get(item, "Properties", "Skill", "LearningIntervalStart"))
    hit_end = (deep_get(item, "Properties", "Skill", "Hit", "LearningIntervalEnd")
               or deep_get(item, "Properties", "Skill", "LearningIntervalEnd"))

    if is_sib is None and not profession and not hit_prof:
        return

    layout.addWidget(_section_label("Skill"))
    if is_sib is not None:
        layout.addWidget(_stat_row(
            "SiB", fmt_bool(is_sib),
            highlight=(is_sib is True or is_sib == 1),
        ))
    if hit_prof:
        layout.addWidget(_stat_row("Hit Prof.", hit_prof))
    if dmg_prof and dmg_prof != hit_prof:
        layout.addWidget(_stat_row("Dmg Prof.", dmg_prof))
    if profession and profession != hit_prof:
        layout.addWidget(_stat_row("Profession", profession))
    if is_sib and (hit_start is not None or hit_end is not None):
        layout.addWidget(_stat_row(
            "Level Range",
            f"{fmt_int(hit_start)} - {fmt_int(hit_end)}",
        ))


# ---------------------------------------------------------------------------
# Effects section helper (shared by generic, medical, tool builders)
# ---------------------------------------------------------------------------

def _add_effects_section(layout: QVBoxLayout, item: dict,
                         keys: list[str]) -> None:
    """Append an Effects section if the item has any matching effect keys."""
    all_effects = []
    for key in keys:
        effects = item.get(key)
        if effects:
            all_effects.append((key, effects))

    if not all_effects:
        return

    layout.addWidget(_section_label("Effects"))
    label_map = {
        "EffectsOnEquip": "On Equip",
        "EffectsOnUse": "On Use",
        "EffectsOnConsume": "On Consume",
        "Effects": "Effects",
    }
    for key, effects in all_effects:
        if len(all_effects) > 1:
            sub_lbl = QLabel(label_map.get(key, key))
            sub_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 10px; font-weight: 600;"
                " background: transparent; padding: 2px 0 0 0;"
            )
            layout.addWidget(sub_lbl)
        for e in effects:
            eff_name = e.get("Name", "Unknown")
            eff_str = e.get("Strength")
            val_str = f"{eff_str}" if eff_str else ""
            layout.addWidget(_stat_row(f"  {eff_name}", val_str))


# ---------------------------------------------------------------------------
# Type-specific detail builders
# ---------------------------------------------------------------------------

def _build_weapon_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()

    dps = weapon_dps(item)
    dpp = weapon_dpp(item)
    eff = deep_get(item, "Properties", "Economy", "Efficiency")

    # Key stats
    layout.addWidget(_section_label("Key Stats"))
    layout.addWidget(_stat_row("DPS", _fv(dps, 2)))
    layout.addWidget(_stat_row("DPP", _fv(dpp, 2)))
    layout.addWidget(_stat_row("Efficiency", f"{_fv(eff, 1)}%"))

    # Performance
    eff_dmg = weapon_effective_damage(item)
    range_val = deep_get(item, "Properties", "Range")
    upm = deep_get(item, "Properties", "UsesPerMinute")
    cost = weapon_cost_per_use(item)

    total_dmg_val = weapon_total_damage(item)
    if total_dmg_val is not None and total_dmg_val > 0:
        dmg_interval = f"{total_dmg_val / 2:.1f} - {total_dmg_val:.1f}"
    else:
        dmg_interval = "-"

    layout.addWidget(_section_label("Performance"))
    layout.addWidget(_stat_row("Damage", dmg_interval))
    layout.addWidget(_stat_row("Eff. Damage", _fv(eff_dmg, 2)))
    layout.addWidget(_stat_row(
        "Range", f"{fmt_int(range_val)}m" if range_val is not None else "-"
    ))
    layout.addWidget(_stat_row("Uses/Min", fmt_int(upm)))
    layout.addWidget(_stat_row(
        "Cost/Use", f"{_fv(cost, 4)} PEC" if cost is not None else "-"
    ))

    # Economy
    max_tt = deep_get(item, "Properties", "Economy", "MaxTT")
    decay = deep_get(item, "Properties", "Economy", "Decay")
    ammo_name = deep_get(item, "Ammo", "Name")
    ammo_burn = deep_get(item, "Properties", "Economy", "AmmoBurn")
    uses = weapon_total_uses(item)

    layout.addWidget(_section_label("Economy"))
    layout.addWidget(_stat_row(
        "Max TT", f"{_fv(max_tt, 2)} PED" if max_tt is not None else "-"
    ))
    layout.addWidget(_stat_row(
        "Decay", f"{_fv(decay, 2)} PEC" if decay is not None else "-"
    ))
    if ammo_name:
        layout.addWidget(_stat_row("Ammo", ammo_name))
    if ammo_burn is not None and ammo_burn > 0:
        layout.addWidget(_stat_row("Ammo Burn", fmt_int(ammo_burn)))
    layout.addWidget(_stat_row("Uses", fmt_int(uses)))

    # Damage breakdown
    damage = deep_get(item, "Properties", "Damage")
    if damage:
        layout.addWidget(_section_label("Damage"))
        layout.addWidget(_overlay_damage_bars(damage, is_pct=False, show_total=True))

    # Skill
    _add_skill_section(layout, item)

    layout.addStretch(1)
    return widget


def _build_amplifier_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()

    eff = deep_get(item, "Properties", "Economy", "Efficiency")
    dps = weapon_dps(item)
    dpp = weapon_dpp(item)

    layout.addWidget(_section_label("Key Stats"))
    layout.addWidget(_stat_row("Efficiency", f"{_fv(eff, 1)}%"))
    layout.addWidget(_stat_row("DPS", _fv(dps, 2)))
    layout.addWidget(_stat_row("DPP", _fv(dpp, 2)))

    # Performance
    total_dmg = weapon_total_damage(item)
    eff_dmg = weapon_effective_damage(item)
    layout.addWidget(_section_label("Performance"))
    layout.addWidget(_stat_row("Total Damage", _fv(total_dmg, 1)))
    layout.addWidget(_stat_row("Eff. Damage", _fv(eff_dmg, 2)))

    # Economy
    max_tt = deep_get(item, "Properties", "Economy", "MaxTT")
    decay = deep_get(item, "Properties", "Economy", "Decay")
    ammo_burn = deep_get(item, "Properties", "Economy", "AmmoBurn")
    cost = weapon_cost_per_use(item)
    uses = weapon_total_uses(item)

    layout.addWidget(_section_label("Economy"))
    layout.addWidget(_stat_row(
        "Max TT", f"{_fv(max_tt, 2)} PED" if max_tt is not None else "-"
    ))
    layout.addWidget(_stat_row(
        "Decay", f"{_fv(decay, 2)} PEC" if decay is not None else "-"
    ))
    if ammo_burn is not None and ammo_burn > 0:
        layout.addWidget(_stat_row("Ammo Burn", fmt_int(ammo_burn)))
    layout.addWidget(_stat_row(
        "Cost/Use", f"{_fv(cost, 4)} PEC" if cost is not None else "-"
    ))
    layout.addWidget(_stat_row("Uses", fmt_int(uses)))

    # Damage breakdown
    damage = deep_get(item, "Properties", "Damage")
    if damage:
        layout.addWidget(_section_label("Damage"))
        layout.addWidget(_overlay_damage_bars(damage, is_pct=False, show_total=True))

    layout.addStretch(1)
    return widget


def _build_armor_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()

    total_def = armor_total_defense(item)
    absorption = _armor_total_absorption(item)

    layout.addWidget(_section_label("Key Stats"))
    layout.addWidget(_stat_row("Total Defense", _fv(total_def, 1)))
    layout.addWidget(_stat_row("Absorption", f"{_fv(absorption, 0)} HP"))

    # Defense breakdown
    defense = deep_get(item, "Properties", "Defense")
    if defense:
        layout.addWidget(_section_label("Defense"))
        layout.addWidget(_overlay_damage_bars(defense, is_pct=False, show_total=True))

    # Economy
    max_tt = deep_get(item, "Properties", "Economy", "MaxTT")
    min_tt = deep_get(item, "Properties", "Economy", "MinTT")
    durability = deep_get(item, "Properties", "Economy", "Durability")
    weight = deep_get(item, "Properties", "Weight")

    layout.addWidget(_section_label("Economy"))
    layout.addWidget(_stat_row(
        "Max TT", f"{_fv(max_tt, 2)} PED" if max_tt is not None else "-"
    ))
    layout.addWidget(_stat_row(
        "Min TT", f"{_fv(min_tt, 2)} PED" if min_tt is not None else "-"
    ))
    layout.addWidget(_stat_row("Durability", _fv(durability, 1)))
    layout.addWidget(_stat_row(
        "Weight", f"{fmt_int(weight)} kg" if weight is not None else "-"
    ))

    # Set effects
    set_effects = item.get("SetEffects") or []
    armors = item.get("Armors") or []
    if set_effects:
        layout.addWidget(_section_label("Set Effects"))
        for eff in set_effects:
            pieces = eff.get("MinSetPieces", "?")
            eff_name = eff.get("Name", "Unknown")
            layout.addWidget(_stat_row(f"  {pieces}-piece", eff_name))
    elif armors:
        layout.addWidget(_stat_row("Pieces", str(len(armors))))

    layout.addStretch(1)
    return widget


def _build_mob_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()

    level_range, hp_range, lowest_hpl = _maturity_stats(item)
    mob_type = item.get("Type") or "-"
    is_asteroid = mob_type == "Asteroid"

    # Key stats
    layout.addWidget(_section_label("Key Stats"))
    layout.addWidget(_stat_row(
        "Avg HP/Lvl", _fv(lowest_hpl, 2) if lowest_hpl else "N/A"
    ))
    if level_range:
        if level_range[0] == level_range[1]:
            layout.addWidget(_stat_row("Level", fmt_int(level_range[0])))
        else:
            layout.addWidget(_stat_row(
                "Level Range",
                f"{fmt_int(level_range[0])} - {fmt_int(level_range[1])}",
            ))
    if hp_range:
        if hp_range[0] == hp_range[1]:
            layout.addWidget(_stat_row("HP", fmt_int(hp_range[0])))
        else:
            layout.addWidget(_stat_row(
                "HP Range",
                f"{fmt_int(hp_range[0])} - {fmt_int(hp_range[1])}",
            ))

    # General
    layout.addWidget(_section_label("General"))
    species = deep_get(item, "Species", "Name")
    planet = deep_get(item, "Planet", "Name")
    if species:
        layout.addWidget(_stat_row("Species", species))
    if planet:
        layout.addWidget(_stat_row("Planet", planet))
    layout.addWidget(_stat_row("Type", mob_type))

    if not is_asteroid:
        apm = deep_get(item, "Properties", "AttacksPerMinute")
        atk_range = deep_get(item, "Properties", "AttackRange")
        aggro_range = deep_get(item, "Properties", "AggressionRange")
        if apm is not None:
            layout.addWidget(_stat_row("APM", _fv(apm, 1)))
        if atk_range is not None:
            layout.addWidget(_stat_row("Attack Range", f"{_fv(atk_range, 1)}m"))
        if aggro_range is not None:
            layout.addWidget(_stat_row("Aggro Range", f"{_fv(aggro_range, 1)}m"))

    sweatable = deep_get(item, "Properties", "IsSweatable")
    layout.addWidget(_stat_row(
        "Sweatable", fmt_bool(sweatable),
        highlight=(sweatable is True or sweatable == 1),
    ))

    # Damage breakdown per maturity group
    maturities = item.get("Maturities") or []
    total_mat_count = len(maturities)
    if not is_asteroid and maturities:
        primary_groups = _get_damage_groups(maturities, "Primary")
        secondary_groups = _get_damage_groups(maturities, "Secondary")
        tertiary_groups = _get_damage_groups(maturities, "Tertiary")

        if primary_groups or secondary_groups or tertiary_groups:
            layout.addWidget(_section_label("Damage"))
            for atk_name, groups in (
                ("Primary", primary_groups),
                ("Secondary", secondary_groups),
                ("Tertiary", tertiary_groups),
            ):
                if not groups:
                    continue
                for group in groups:
                    mat_label = _format_maturity_label(
                        group["maturities"], total_mat_count
                    )
                    if len(groups) == 1 and not mat_label:
                        label = atk_name
                    else:
                        label = (f"{atk_name} ({mat_label})"
                                 if mat_label else atk_name)
                    layout.addWidget(_overlay_damage_bars(
                        group["spread"], label=label
                    ))

    # Skills
    if not is_asteroid:
        def_prof = deep_get(item, "DefensiveProfession", "Name")
        scan_prof = deep_get(item, "Species", "Properties", "ScanningProfession")
        loot_prof = deep_get(item, "Species", "Properties", "LootingProfession")
        if def_prof or scan_prof or loot_prof:
            layout.addWidget(_section_label("Skills"))
            if def_prof:
                layout.addWidget(_stat_row(
                    "Defense", def_prof,
                    entity={"Name": def_prof, "Type": "Profession"},
                    on_click=on_entity,
                ))
            if scan_prof:
                layout.addWidget(_stat_row(
                    "Scanning", scan_prof,
                    entity={"Name": scan_prof, "Type": "Profession"},
                    on_click=on_entity,
                ))
            if loot_prof:
                layout.addWidget(_stat_row(
                    "Looting", loot_prof,
                    entity={"Name": loot_prof, "Type": "Profession"},
                    on_click=on_entity,
                ))

    layout.addStretch(1)
    return widget


def _build_medical_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()
    is_chip = page_type == "medicalchips"

    hps = _medical_hps(item)
    hpp = _medical_hpp(item)

    layout.addWidget(_section_label("Key Stats"))
    layout.addWidget(_stat_row("HPS", _fv(hps, 1)))
    layout.addWidget(_stat_row("HPP", _fv(hpp, 1)))

    # Healing
    max_heal = deep_get(item, "Properties", "MaxHeal")
    min_heal = deep_get(item, "Properties", "MinHeal")
    upm = deep_get(item, "Properties", "UsesPerMinute")
    reload_val = weapon_reload(item)

    layout.addWidget(_section_label("Healing"))
    layout.addWidget(_stat_row("Max Heal", _fv(max_heal, 1)))
    layout.addWidget(_stat_row("Min Heal", _fv(min_heal, 1)))
    layout.addWidget(_stat_row("Uses/Min", fmt_int(upm)))
    layout.addWidget(_stat_row(
        "Interval", f"{_fv(reload_val, 2)}s" if reload_val is not None else "-"
    ))

    # Economy
    max_tt = deep_get(item, "Properties", "Economy", "MaxTT")
    decay = deep_get(item, "Properties", "Economy", "Decay")
    ammo_burn = deep_get(item, "Properties", "Economy", "AmmoBurn")
    cost = weapon_cost_per_use(item)
    uses = weapon_total_uses(item)

    layout.addWidget(_section_label("Economy"))
    layout.addWidget(_stat_row(
        "Max TT", f"{_fv(max_tt, 2)} PED" if max_tt is not None else "-"
    ))
    layout.addWidget(_stat_row(
        "Decay", f"{_fv(decay, 2)} PEC" if decay is not None else "-"
    ))
    if is_chip and ammo_burn is not None and ammo_burn > 0:
        layout.addWidget(_stat_row("Ammo Burn", fmt_int(ammo_burn)))
    layout.addWidget(_stat_row(
        "Cost/Use", f"{_fv(cost, 4)} PEC" if cost is not None else "-"
    ))
    layout.addWidget(_stat_row("Uses", fmt_int(uses)))

    # Skill
    _add_skill_section(layout, item)

    # Mindforce (chips)
    if is_chip:
        mf_level = deep_get(item, "Properties", "Mindforce", "Level")
        mf_conc = deep_get(item, "Properties", "Mindforce", "Concentration")
        mf_cd = deep_get(item, "Properties", "Mindforce", "Cooldown")
        range_val = deep_get(item, "Properties", "Range")
        if any(v is not None for v in (mf_level, mf_conc, mf_cd, range_val)):
            layout.addWidget(_section_label("Mindforce"))
            if mf_level is not None:
                layout.addWidget(_stat_row("Level", fmt_int(mf_level)))
            if mf_conc is not None:
                layout.addWidget(_stat_row("Concentration", f"{mf_conc}s"))
            if range_val is not None:
                layout.addWidget(_stat_row("Range", f"{fmt_int(range_val)}m"))
            if mf_cd is not None:
                layout.addWidget(_stat_row("Cooldown", f"{mf_cd}s"))

    # Effects
    _add_effects_section(layout, item, ["EffectsOnEquip", "EffectsOnUse"])

    layout.addStretch(1)
    return widget


def _build_tool_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()

    depth = deep_get(item, "Properties", "Depth")
    range_val = deep_get(item, "Properties", "Range")
    efficiency = deep_get(item, "Properties", "Efficiency")
    upm = deep_get(item, "Properties", "UsesPerMinute")
    max_tt = deep_get(item, "Properties", "Economy", "MaxTT")

    # Key stats (varies by subtype)
    layout.addWidget(_section_label("Key Stats"))
    if page_type == "finders":
        layout.addWidget(_stat_row("Depth", f"{fmt_int(depth)}m"))
        layout.addWidget(_stat_row("Range", f"{fmt_int(range_val)}m"))
    elif page_type == "excavators":
        layout.addWidget(_stat_row("Efficiency", fmt_int(efficiency)))
        eff_per_ped = _excavator_eff_per_ped(item)
        layout.addWidget(_stat_row("Eff/PED", _fv(eff_per_ped, 1)))
    else:
        layout.addWidget(_stat_row("Uses/Min", fmt_int(upm)))
        layout.addWidget(_stat_row(
            "Max TT", f"{_fv(max_tt, 2)} PED" if max_tt is not None else "-"
        ))

    # Performance (all tool types)
    has_perf_data = any(v is not None for v in [upm, depth, range_val, efficiency])
    if has_perf_data and page_type not in ("finders", "excavators"):
        layout.addWidget(_section_label("Performance"))
        if depth is not None:
            layout.addWidget(_stat_row("Depth", f"{fmt_int(depth)}m"))
        if range_val is not None:
            layout.addWidget(_stat_row("Range", f"{fmt_int(range_val)}m"))
        if efficiency is not None:
            layout.addWidget(_stat_row("Efficiency", fmt_int(efficiency)))

    # Economy
    min_tt = deep_get(item, "Properties", "Economy", "MinTT")
    decay = deep_get(item, "Properties", "Economy", "Decay")
    ammo_burn = deep_get(item, "Properties", "Economy", "AmmoBurn")
    cost = weapon_cost_per_use(item)
    uses = weapon_total_uses(item)

    layout.addWidget(_section_label("Economy"))
    if page_type in ("finders", "excavators"):
        layout.addWidget(_stat_row(
            "Max TT", f"{_fv(max_tt, 2)} PED" if max_tt is not None else "-"
        ))
    layout.addWidget(_stat_row(
        "Min TT", f"{_fv(min_tt, 2)} PED" if min_tt is not None else "-"
    ))
    layout.addWidget(_stat_row(
        "Decay", f"{_fv(decay, 2)} PEC" if decay is not None else "-"
    ))
    if ammo_burn is not None and ammo_burn > 0:
        layout.addWidget(_stat_row("Ammo Burn", fmt_int(ammo_burn)))
    if cost is not None:
        layout.addWidget(_stat_row("Cost/Use", f"{_fv(cost, 4)} PEC"))
    layout.addWidget(_stat_row("Uses", fmt_int(uses)))

    # Skill
    _add_skill_section(layout, item)

    # Mindforce (teleportation/effect chips)
    mf_cd = deep_get(item, "Properties", "Mindforce", "Cooldown")
    mf_grp = deep_get(item, "Properties", "Mindforce", "CooldownGroup")
    if mf_cd is not None or mf_grp is not None:
        layout.addWidget(_section_label("Mindforce"))
        if mf_cd is not None:
            layout.addWidget(_stat_row("Cooldown", f"{mf_cd}s"))
        if mf_grp is not None:
            layout.addWidget(_stat_row("CD Group", str(mf_grp)))

    # Effects
    _add_effects_section(layout, item, ["EffectsOnEquip", "EffectsOnUse"])

    layout.addStretch(1)
    return widget


def _build_blueprint_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()

    cost = _blueprint_cost(item)
    level = deep_get(item, "Properties", "Level")
    bp_type = deep_get(item, "Properties", "Type") or "-"
    profession = deep_get(item, "Profession", "Name")
    near_success = deep_get(item, "Properties", "NearSuccessRate")

    layout.addWidget(_section_label("Key Stats"))
    layout.addWidget(_stat_row(
        "Cost", f"{_fv(cost, 2)} PED" if cost is not None else "-"
    ))
    layout.addWidget(_stat_row("Level", fmt_int(level)))

    layout.addWidget(_section_label("General"))
    layout.addWidget(_stat_row("Type", bp_type))
    product = item.get("Product") or {}
    product_name = product.get("Name")
    product_type = product.get("Type")
    if product_name:
        layout.addWidget(_stat_row("Product", product_name,
            entity={"Name": product_name, "Type": product_type},
            on_click=on_entity))
    if profession:
        layout.addWidget(_stat_row("Profession", profession,
            entity={"Name": profession, "Type": "Profession"},
            on_click=on_entity))
    if near_success is not None:
        layout.addWidget(_stat_row("Near Success", f"{near_success}%"))

    # Skill learning interval
    interval_start = deep_get(item, "Properties", "Skill", "LearningIntervalStart")
    interval_end = deep_get(item, "Properties", "Skill", "LearningIntervalEnd")
    if interval_start is not None or interval_end is not None:
        s = fmt_int(interval_start) if interval_start is not None else "?"
        e = fmt_int(interval_end) if interval_end is not None else "?"
        layout.addWidget(_stat_row("Skill Interval", f"{s} – {e}"))

    # Materials (compact list)
    materials = item.get("Materials") or []
    if materials:
        layout.addWidget(_section_label("Materials"))
        for mat in materials[:10]:
            mat_item = mat.get("Item") or {}
            mat_name = mat_item.get("Name") or "Unknown"
            mat_type = deep_get(mat_item, "Properties", "Type")
            amount = mat.get("Amount", 0)
            if mat_name and mat_name != "Unknown" and on_entity:
                layout.addWidget(_stat_row(mat_name, str(amount),
                    entity={"Name": mat_name, "Type": mat_type},
                    on_click=on_entity))
            else:
                layout.addWidget(_stat_row(mat_name, str(amount)))

    layout.addStretch(1)
    return widget


def _build_vehicle_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()

    max_speed = deep_get(item, "Properties", "MaxSpeed")
    passengers = deep_get(item, "Properties", "PassengerCount")
    max_si = deep_get(item, "Properties", "MaxStructuralIntegrity")
    vehicle_type = deep_get(item, "Properties", "Type") or "-"

    layout.addWidget(_section_label("Key Stats"))
    layout.addWidget(_stat_row(
        "Max Speed",
        f"{fmt_int(max_speed)} km/h" if max_speed is not None else "-",
    ))
    layout.addWidget(_stat_row("Passengers", fmt_int(passengers)))
    layout.addWidget(_stat_row("Max SI", fmt_int(max_si)))

    # General
    weight = deep_get(item, "Properties", "Weight")
    spawned_weight = deep_get(item, "Properties", "SpawnedWeight")

    layout.addWidget(_section_label("General"))
    layout.addWidget(_stat_row("Type", vehicle_type))
    layout.addWidget(_stat_row(
        "Weight", f"{fmt_int(weight)} kg" if weight is not None else "-"
    ))
    if spawned_weight is not None:
        layout.addWidget(_stat_row("Spawned Wt.", f"{fmt_int(spawned_weight)} kg"))

    # Economy
    max_tt = deep_get(item, "Properties", "Economy", "MaxTT")
    min_tt = deep_get(item, "Properties", "Economy", "MinTT")
    layout.addWidget(_section_label("Economy"))
    layout.addWidget(_stat_row(
        "Max TT", f"{_fv(max_tt, 2)} PED" if max_tt is not None else "-"
    ))
    layout.addWidget(_stat_row(
        "Min TT", f"{_fv(min_tt, 2)} PED" if min_tt is not None else "-"
    ))

    # Defense (if present)
    defense = deep_get(item, "Properties", "Defense")
    if defense:
        total_def = armor_total_defense(item)
        if total_def and total_def > 0:
            layout.addWidget(_section_label("Defense"))
            layout.addWidget(_overlay_damage_bars(defense, is_pct=False, show_total=True))

    layout.addStretch(1)
    return widget


def _build_pet_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()

    pet_type = deep_get(item, "Properties", "Type") or "-"
    rarity = deep_get(item, "Properties", "Rarity")
    training = deep_get(item, "Properties", "TrainingDifficulty") or \
        deep_get(item, "Properties", "Training")
    max_tt = deep_get(item, "Properties", "Economy", "MaxTT")
    taming_level = deep_get(item, "Properties", "TamingLevel")
    exportable = deep_get(item, "Properties", "ExportableLevel")
    nutrio_cap = deep_get(item, "Properties", "NutrioCapacity")
    nutrio_rate = deep_get(item, "Properties", "NutrioConsumptionPerHour")
    planet = deep_get(item, "Planet", "Name")

    layout.addWidget(_section_label("General"))
    layout.addWidget(_stat_row("Type", pet_type))
    if rarity:
        layout.addWidget(_stat_row("Rarity", rarity))
    if training:
        layout.addWidget(_stat_row("Training", training))
    if taming_level is not None:
        layout.addWidget(_stat_row("Taming Level", str(taming_level)))
    if exportable is not None and exportable > 0:
        layout.addWidget(_stat_row("Exportable", f"Lvl {exportable}"))
    if max_tt is not None:
        layout.addWidget(_stat_row("Max TT", f"{_fv(max_tt, 2)} PED"))
    if nutrio_cap is not None:
        layout.addWidget(_stat_row("Nutrio Cap.", f"{nutrio_cap / 100:.2f} PED"))
    if nutrio_rate is not None:
        layout.addWidget(_stat_row("Nutrio/Hour", f"{nutrio_rate / 100:.2f} PED"))
    if planet:
        layout.addWidget(_stat_row("Planet", planet))

    layout.addStretch(1)
    return widget


def _build_location_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()

    loc_type = deep_get(item, "Properties", "Type") or "-"
    planet = deep_get(item, "Planet", "Name") or ""
    coords = deep_get(item, "Properties", "Coordinates") or {}
    name = item.get("Name") or ""

    layout.addWidget(_section_label("General"))
    layout.addWidget(_stat_row("Type", loc_type))
    if planet:
        layout.addWidget(_stat_row("Planet", planet))

    lon = coords.get("Longitude")
    lat = coords.get("Latitude")
    if lon is not None and lat is not None:
        layout.addWidget(_stat_row("Coordinates", f"{lon:.0f}, {lat:.0f}"))
        # Waypoint + Map buttons
        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        brl = QHBoxLayout(btn_row)
        brl.setContentsMargins(0, 2, 0, 2)
        brl.setSpacing(4)
        brl.addWidget(_overlay_waypoint_btn(planet, coords, name))
        brl.addWidget(_overlay_map_btn(planet, item.get("Id")))
        brl.addStretch(1)
        layout.addWidget(btn_row)

    # Parent location
    parent = deep_get(item, "ParentLocation", "Name")
    if parent:
        layout.addWidget(_stat_row(
            "Parent", parent,
            entity={"Name": parent, "Type": "Location"},
            on_click=on_entity,
        ))

    # Type-specific
    if loc_type == "Teleporter":
        dest = deep_get(item, "Properties", "Destination", "Name")
        if dest:
            layout.addWidget(_stat_row(
                "Destination", dest,
                entity={"Name": dest, "Type": "Location"},
                on_click=on_entity,
            ))
        fee = deep_get(item, "Properties", "Fee")
        if fee is not None:
            layout.addWidget(_stat_row("Fee", f"{_fv(fee, 2)} PED"))
    elif loc_type == "Estate":
        estate_type = deep_get(item, "Properties", "EstateType")
        if estate_type:
            layout.addWidget(_stat_row("Estate Type", estate_type))
        owner = deep_get(item, "Owner", "Name")
        if owner:
            layout.addWidget(_stat_row("Owner", owner))
    elif loc_type == "Area":
        area_type = deep_get(item, "Properties", "AreaType")
        if area_type:
            layout.addWidget(_stat_row("Area Type", area_type))
        if area_type == "WaveEventArea":
            waves = item.get("Waves") or []
            if waves:
                layout.addWidget(_stat_row("Waves", str(len(waves))))

    # Facilities
    facilities = item.get("Facilities") or []
    if facilities:
        layout.addWidget(_section_label("Facilities"))
        for f in facilities[:8]:
            f_name = f.get("Name") or f.get("Type", "?")
            layout.addWidget(_stat_row(f_name, ""))

    # MobArea: show mobs + maturity range + difficulty
    area_type = deep_get(item, "Properties", "AreaType")
    if area_type == "MobArea":
        from ..ui.pages.maps_page import (
            _mob_area_difficulty, _difficulty_color, _format_mob_area_maturities,
        )

        maturities = item.get("Maturities") or item.get("Spawns") or []
        if maturities:
            # Difficulty badge
            diff = _mob_area_difficulty(item)
            if diff:
                band, label = diff
                r, g, b = _difficulty_color(band)
                layout.addWidget(_section_label("Mobs"))
                diff_badge = QLabel(label)
                diff_badge.setStyleSheet(
                    f"color: rgb({r},{g},{b}); font-size: 10px;"
                    f" background-color: rgba({r},{g},{b},30);"
                    " border-radius: 2px; padding: 1px 4px;"
                )
                layout.addWidget(diff_badge)
            else:
                layout.addWidget(_section_label("Mobs"))

            for entry in _format_mob_area_maturities(item):
                layout.addWidget(_stat_row(
                    entry["mob"], entry["display"],
                    entity={"Name": entry["mob"], "Type": "Mob"},
                    on_click=on_entity,
                ))

    layout.addStretch(1)
    return widget


def _build_profession_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()

    skills = item.get("Skills") or []
    category = deep_get(item, "Properties", "Category")

    layout.addWidget(_section_label("General"))
    if category:
        layout.addWidget(_stat_row("Category", category))
    visible_count = sum(
        1 for s in skills
        if not deep_get(s, "Skill", "Properties", "IsHidden")
    )
    hidden_count = len(skills) - visible_count
    if hidden_count:
        layout.addWidget(_stat_row("Skills", f"{visible_count} + {hidden_count} hidden"))
    else:
        layout.addWidget(_stat_row("Skills", str(len(skills))))

    if skills:
        total_weight = sum(
            (s.get("Weight") or 0) for s in skills
        )
        if total_weight > 0:
            layout.addWidget(_stat_row("Total Weight", _fv(total_weight, 1)))

        # All skills sorted by weight
        sorted_skills = sorted(
            skills, key=lambda s: s.get("Weight") or 0, reverse=True
        )
        layout.addWidget(_section_label("Skills"))
        for s in sorted_skills:
            skill_name = deep_get(s, "Skill", "Name") or s.get("Name", "?")
            is_hidden = deep_get(s, "Skill", "Properties", "IsHidden")
            weight = s.get("Weight")
            display_name = f"{skill_name}  \u2022 hidden" if is_hidden else skill_name
            layout.addWidget(_stat_row(
                display_name, f"{weight:.1f}%" if weight else "-",
                entity={"Name": skill_name, "Type": "Skill"},
                on_click=on_entity,
            ))

    layout.addStretch(1)
    return widget


def _build_skill_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()

    category = deep_get(item, "Properties", "Category")
    hp_per_point = deep_get(item, "Properties", "HealthPointsPerLevel")
    professions = item.get("Professions") or []

    is_hidden = deep_get(item, "Properties", "IsHidden")
    is_extractable = deep_get(item, "Properties", "IsExtractable")

    layout.addWidget(_section_label("General"))
    if category:
        layout.addWidget(_stat_row("Category", category))
    layout.addWidget(_stat_row("Visibility", "Hidden" if is_hidden else "Visible"))
    layout.addWidget(_stat_row("Extractable", "Yes" if is_extractable else "No"))

    if hp_per_point is not None and hp_per_point > 0:
        layout.addWidget(_section_label("Health"))
        layout.addWidget(_stat_row("HP/Point", _fv(hp_per_point, 4)))

    if professions:
        layout.addWidget(_section_label("Professions"))
        sorted_profs = sorted(
            professions, key=lambda p: p.get("Weight") or 0, reverse=True
        )
        for p in sorted_profs[:8]:
            prof_name = deep_get(p, "Profession", "Name") or p.get("Name", "?")
            weight = p.get("Weight")
            layout.addWidget(_stat_row(
                prof_name, f"{weight:.1f}%" if weight else "-",
                entity={"Name": prof_name, "Type": "Profession"},
                on_click=on_entity,
            ))

    layout.addStretch(1)
    return widget


def _build_vendor_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()

    planet = deep_get(item, "Planet", "Name") or ""
    location = deep_get(item, "Location", "Name")
    coords = deep_get(item, "Properties", "Coordinates") or {}
    name = item.get("Name") or ""
    offers = item.get("Offers") or []
    limited_count = sum(1 for o in offers if o.get("IsLimited"))

    layout.addWidget(_section_label("General"))
    if planet:
        layout.addWidget(_stat_row("Planet", planet))
    if location:
        layout.addWidget(_stat_row(
            "Location", location,
            entity={"Name": location, "Type": "Location"},
            on_click=on_entity,
        ))
    layout.addWidget(_stat_row("Offers", str(len(offers))))
    if limited_count:
        layout.addWidget(_stat_row("Limited", str(limited_count)))

    # Coordinates + waypoint/map buttons
    lon = coords.get("Longitude")
    lat = coords.get("Latitude")
    if lon is not None and lat is not None:
        layout.addWidget(_stat_row("Coordinates", f"{lon:.0f}, {lat:.0f}"))
        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        brl = QHBoxLayout(btn_row)
        brl.setContentsMargins(0, 2, 0, 2)
        brl.setSpacing(4)
        brl.addWidget(_overlay_waypoint_btn(planet, coords, name))
        brl.addWidget(_overlay_map_btn(planet, item.get("Id")))
        brl.addStretch(1)
        layout.addWidget(btn_row)

    layout.addStretch(1)
    return widget


def _build_mission_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    widget, layout = _details_container()

    mission_type = deep_get(item, "Properties", "Type") or "-"
    planet = deep_get(item, "Planet", "Name") or ""
    area = deep_get(item, "Area", "Name")
    steps = item.get("Steps") or item.get("Objectives") or []
    rewards = item.get("Rewards") or []

    layout.addWidget(_section_label("General"))
    layout.addWidget(_stat_row("Type", mission_type))
    if planet:
        layout.addWidget(_stat_row("Planet", planet))
    if area:
        layout.addWidget(_stat_row(
            "Area", area,
            entity={"Name": area, "Type": "Area"},
            on_click=on_entity,
        ))
    if steps:
        layout.addWidget(_stat_row("Steps", str(len(steps))))

    # Mission chain link
    chain = item.get("MissionChain")
    if chain:
        chain_name = chain.get("Name") or ""
        if chain_name:
            layout.addWidget(_stat_row(
                "Chain", chain_name,
                entity={"Name": chain_name, "Type": "MissionChain"},
                on_click=on_entity,
            ))

    # Start location coordinates
    start_loc = item.get("StartLocation") or {}
    start_coords = deep_get(start_loc, "Coordinates") or deep_get(
        start_loc, "Properties", "Coordinates"
    ) or {}
    start_name = start_loc.get("Name") or ""
    lon = start_coords.get("Longitude")
    lat = start_coords.get("Latitude")
    if lon is not None and lat is not None:
        layout.addWidget(_section_label("Start Location"))
        if start_name:
            layout.addWidget(_stat_row(
                "Location", start_name,
                entity={"Name": start_name, "Type": "Location"},
                on_click=on_entity,
            ))
        layout.addWidget(_stat_row("Coordinates", f"{lon:.0f}, {lat:.0f}"))
        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        brl = QHBoxLayout(btn_row)
        brl.setContentsMargins(0, 2, 0, 2)
        brl.setSpacing(4)
        brl.addWidget(_overlay_waypoint_btn(
            planet, start_coords, start_name or item.get("Name", ""),
        ))
        loc_id = start_loc.get("Id")
        if loc_id:
            brl.addWidget(_overlay_map_btn(planet, loc_id))
        brl.addStretch(1)
        layout.addWidget(btn_row)

    layout.addStretch(1)
    return widget


# ---------------------------------------------------------------------------
# Generic / config-driven builder (fallback for simple entity types)
# ---------------------------------------------------------------------------

# Config format: { sections: [(title, [(label, getter)])], effects_keys: [str],
#                   defense_grid: bool }

_GENERIC_CONFIGS: dict[str, dict] = {
    "clothing": {
        "sections": [
            ("Properties", [
                ("Type", lambda i: deep_get(i, "Properties", "Type") or "-"),
                ("Slot", lambda i: deep_get(i, "Properties", "Slot") or "-"),
                ("Gender", lambda i: deep_get(i, "Properties", "Gender") or "-"),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
            ]),
        ],
        "effects_keys": ["EffectsOnEquip", "Effects"],
    },
    "materials": {
        "sections": [
            ("Properties", [
                ("Type", lambda i: deep_get(i, "Properties", "Type") or "-"),
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
            ]),
            ("Economy", [
                ("Value", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
            ]),
        ],
        "effects_keys": [],
    },
    "enhancers": {
        "sections": [
            ("Properties", [
                ("Type", lambda i: deep_get(i, "Properties", "Type") or "-"),
                ("Tier", lambda i: fmt_int(deep_get(i, "Properties", "Tier") or i.get("Tier"))),
                ("Tool", lambda i: deep_get(i, "Properties", "Tool") or "-"),
                ("Socket", lambda i: fmt_int(deep_get(i, "Properties", "Socket"))),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Value", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Value'), 2)} PED"),
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
            ]),
        ],
        "effects_keys": [],
    },
    "stimulants": {
        "sections": [
            ("Properties", [
                ("Type", lambda i: deep_get(i, "Properties", "Type") or "-"),
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
            ]),
        ],
        "effects_keys": ["EffectsOnConsume"],
    },
    "capsules": {
        "sections": [
            ("Properties", [
                ("Mob", lambda i: deep_get(i, "Mob", "Name") or "-"),
                ("Mob Type", lambda i: deep_get(i, "Mob", "Type") or "-"),
                ("Profession", lambda i: deep_get(i, "Profession", "Name") or "-"),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
            ]),
        ],
        "effects_keys": [],
    },
    "furniture": {
        "sections": [
            ("Properties", [
                ("Type", lambda i: deep_get(i, "Properties", "Type") or "-"),
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
            ]),
        ],
        "effects_keys": [],
    },
    "storagecontainers": {
        "sections": [
            ("Capacity", [
                ("Item Capacity", lambda i: fmt_int(deep_get(i, "Properties", "ItemCapacity"))),
                ("Weight Capacity", lambda i: f"{_fv(deep_get(i, 'Properties', 'WeightCapacity'), 1)} kg"),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
            ]),
        ],
        "effects_keys": [],
    },
    "signs": {
        "sections": [
            ("Display", [
                ("Aspect Ratio", lambda i: deep_get(i, "Properties", "Display", "AspectRatio") or "-"),
                ("Item Points", lambda i: fmt_int(deep_get(i, "Properties", "ItemPoints"))),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Cost", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Cost'), 2)} PED"),
            ]),
        ],
        "effects_keys": [],
    },
    "sightsscopes": {
        "sections": [
            ("Performance", [
                ("Zoom", lambda i: f"{_fv(deep_get(i, 'Properties', 'Zoom'), 1)}x" if deep_get(i, "Properties", "Zoom") else "-"),
                ("Efficiency", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Efficiency'), 1)}%"),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Decay", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Decay'), 2)} PEC"),
                ("Uses", lambda i: fmt_int(weapon_total_uses(i))),
            ]),
        ],
        "effects_keys": ["EffectsOnEquip"],
    },
    "absorbers": {
        "sections": [
            ("Performance", [
                ("Efficiency", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Efficiency'), 1)}%"),
                ("Absorption", lambda i: f"{deep_get(i, 'Properties', 'Economy', 'Absorption') or 0:.0%}" if deep_get(i, "Properties", "Economy", "Absorption") is not None else "-"),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
                ("Decay", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Decay'), 2)} PEC"),
            ]),
        ],
        "effects_keys": ["EffectsOnEquip"],
    },
    "finderamplifiers": {
        "sections": [
            ("Performance", [
                ("Efficiency", lambda i: _fv(deep_get(i, "Properties", "Efficiency"), 1)),
                ("Decay", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Decay'), 4)} PEC"),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
                ("Uses", lambda i: fmt_int(weapon_total_uses(i))),
            ]),
        ],
        "effects_keys": ["EffectsOnEquip"],
    },
    "armorplatings": {
        "sections": [
            ("Key Stats", [
                ("Total Defense", lambda i: _fv(armor_total_defense(i), 1)),
                ("Durability", lambda i: fmt_int(deep_get(i, "Properties", "Economy", "Durability"))),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
            ]),
        ],
        "effects_keys": ["EffectsOnEquip"],
        "defense_grid": True,
    },
    "mindforceimplants": {
        "sections": [
            ("Properties", [
                ("Max Prof. Level", lambda i: fmt_int(deep_get(i, "Properties", "MaxProfessionLevel"))),
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
                ("Absorption", lambda i: f"{deep_get(i, 'Properties', 'Economy', 'Absorption') or 0:.0%}" if deep_get(i, "Properties", "Economy", "Absorption") is not None else "-"),
            ]),
        ],
        "effects_keys": ["EffectsOnEquip"],
    },
}

# Default config for unknown types
_GENERIC_DEFAULT = {
    "sections": [
        ("Economy", [
            ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
            ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
            ("Decay", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Decay'), 2)} PEC"),
            ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
        ]),
    ],
    "effects_keys": ["EffectsOnEquip", "EffectsOnUse"],
}


def _build_generic_details(item: dict, page_type: str, on_entity=None) -> QWidget:
    """Config-driven builder for simple entity types."""
    widget, layout = _details_container()

    config = _GENERIC_CONFIGS.get(page_type, _GENERIC_DEFAULT)

    # Stat sections
    for section_title, rows in config.get("sections", []):
        layout.addWidget(_section_label(section_title))
        for label, getter in rows:
            val = getter(item)
            if val and val != "-":
                layout.addWidget(_stat_row(label, val))

    # Defense grid (armor platings)
    if config.get("defense_grid"):
        defense = deep_get(item, "Properties", "Defense")
        if defense:
            layout.addWidget(_section_label("Defense"))
            layout.addWidget(_overlay_damage_bars(defense, is_pct=False, show_total=True))

    # Effects
    _add_effects_section(layout, item, config.get("effects_keys", []))

    # Set info (clothing)
    if page_type == "clothing":
        set_data = item.get("Set")
        if set_data:
            layout.addWidget(_section_label("Set"))
            set_name = set_data.get("Name")
            if set_name:
                layout.addWidget(_stat_row("Set", set_name))
            set_effects = set_data.get("EffectsOnSetEquip") or []
            for eff in set_effects:
                pieces = eff.get("MinSetPieces", "?")
                eff_name = eff.get("Name", "Unknown")
                layout.addWidget(_stat_row(f"  {pieces}-piece", eff_name))

    if layout.count() == 0:
        layout.addWidget(_make_centered_label("No details available"))

    layout.addStretch(1)
    return widget


# ---------------------------------------------------------------------------
# Type builder dispatch table
# ---------------------------------------------------------------------------

_TYPE_BUILDERS: dict[str, callable] = {
    "weapons": _build_weapon_details,
    "weaponamplifiers": _build_amplifier_details,
    "armorsets": _build_armor_details,
    "mobs": _build_mob_details,
    "medicaltools": _build_medical_details,
    "medicalchips": _build_medical_details,
    "finders": _build_tool_details,
    "excavators": _build_tool_details,
    "scanners": _build_tool_details,
    "refiners": _build_tool_details,
    "teleportationchips": _build_tool_details,
    "misctools": _build_tool_details,
    "blueprints": _build_blueprint_details,
    "vehicles": _build_vehicle_details,
    "pets": _build_pet_details,
    "locations": _build_location_details,
    "professions": _build_profession_details,
    "skills": _build_skill_details,
    "vendors": _build_vendor_details,
    "missions": _build_mission_details,
}


# ---------------------------------------------------------------------------
# Overlay-native compact calculator widgets
# ---------------------------------------------------------------------------

_TIER_BTN_SIZE = 26
_TIER_BTN_SPACING = 1
_COL_AMT = 50
_COL_MU = 70
_COL_COST = 65
_MU_SOURCE_BTN_H = 20

# Overlay-matched spinbox style
_OVERLAY_SPIN_STYLE = (
    "QDoubleSpinBox {"
    f"  background: rgba(30,30,50,200); color: {TEXT_COLOR};"
    f"  border: 1px solid rgba(80,80,110,180); border-radius: 3px;"
    "  padding: 0 2px; font-size: 12px;"
    "}"
    "QDoubleSpinBox:focus {"
    f"  border-color: {ACCENT};"
    "}"
    "QDoubleSpinBox:disabled {"
    f"  color: {TEXT_DIM};"
    "}"
    "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {"
    "  width: 0; height: 0; border: none;"
    "}"
    "QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {"
    "  image: none;"
    "}"
)


class _OverlayTiersWidget(QWidget):
    """Compact overlay-native tier calculator.

    Follows the overlay theme (transparent backgrounds, RGBA colors,
    QLabel-based rows) instead of the wiki-page QTableWidget.
    """

    _market_data_ready = pyqtSignal()
    _inventory_data_ready = pyqtSignal()
    _ingame_data_ready = pyqtSignal()

    def __init__(self, item: dict, *, nexus_client=None, parent=None):
        super().__init__(parent)
        from ..ui.widgets.weapon_detail import (
            _extrapolate_tiers, _classify_material, _fmt_ped,
            _PREF_KEY, _LOCAL_MARKUPS_PATH, _MAX_TIERS,
        )
        self._classify = _classify_material
        self._fmt_ped = _fmt_ped
        self._pref_key = _PREF_KEY
        self._local_path = _LOCAL_MARKUPS_PATH
        self._max_tiers = _MAX_TIERS

        self.setStyleSheet("background: transparent;")
        entity_type = item.get("Type", "Weapon")
        self._entity_type = entity_type
        self._nexus_client = nexus_client
        self._markup_source: str = "custom"

        # Market / inventory / in-game data (loaded async)
        self._name_to_wap: dict[str, float] = {}
        self._name_to_id: dict[str, int] = {}
        self._inv_markups: dict[int, float] = {}
        self._ingame_markups: dict[str, float] = {}  # name → markup%

        # Extrapolate and index tiers
        tiers_data = item.get("Tiers") or []
        all_tiers = _extrapolate_tiers(tiers_data, entity_type) if tiers_data else []
        self._tier_map: dict[int, dict] = {}
        for tier in all_tiers:
            t_num = deep_get(tier, "Properties", "Tier")
            if t_num is not None:
                self._tier_map[t_num] = tier

        # Per-tier markups: {tier_num: {sorted_row_idx: markup_pct}}
        self._markups: dict[int, dict[int, float]] = {}
        self._load_markups()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(3)

        # --- Tier buttons row ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(_TIER_BTN_SPACING)
        self._tier_buttons: list[QPushButton] = []
        for i in range(1, self._max_tiers + 1):
            btn = QPushButton(str(i))
            btn.setFixedSize(_TIER_BTN_SIZE, _TIER_BTN_SIZE)
            has_data = i in self._tier_map
            btn.setEnabled(has_data)
            if has_data:
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, t=i: self._select_tier(t))
            self._tier_buttons.append(btn)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # --- MU source toggle row ---
        src_row = QHBoxLayout()
        src_row.setSpacing(3)
        src_lbl = QLabel("MU:")
        src_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
        )
        src_row.addWidget(src_lbl)
        self._btn_custom = QPushButton("Custom")
        self._btn_inventory = QPushButton("Inventory")
        self._btn_ingame = QPushButton("In-Game")
        self._btn_exchange = QPushButton("Exchange")
        self._source_buttons = [
            self._btn_custom, self._btn_inventory, self._btn_ingame, self._btn_exchange,
        ]
        for btn in self._source_buttons:
            btn.setFixedHeight(_MU_SOURCE_BTN_H)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_inventory.setEnabled(False)
        self._btn_ingame.setEnabled(False)
        self._btn_exchange.setEnabled(False)
        self._btn_custom.clicked.connect(lambda: self._set_markup_source("custom"))
        self._btn_inventory.clicked.connect(lambda: self._set_markup_source("inventory"))
        self._btn_ingame.clicked.connect(lambda: self._set_markup_source("ingame"))
        self._btn_exchange.clicked.connect(lambda: self._set_markup_source("exchange"))
        for btn in self._source_buttons:
            src_row.addWidget(btn)
        src_row.addStretch()
        layout.addLayout(src_row)
        self._update_source_buttons()

        # --- Separator ---
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(100, 100, 120, 80);")
        layout.addWidget(sep)

        # --- Materials area (rebuilt on tier select) ---
        self._materials_container = QWidget()
        self._materials_container.setStyleSheet("background: transparent;")
        self._materials_layout = QVBoxLayout(self._materials_container)
        self._materials_layout.setContentsMargins(0, 0, 0, 0)
        self._materials_layout.setSpacing(1)
        layout.addWidget(self._materials_container)

        # --- Footer (no box, just label-value rows) ---
        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background-color: rgba(100, 100, 120, 80);")
        layout.addWidget(sep2)

        self._footer_container = QWidget()
        self._footer_container.setStyleSheet("background: transparent;")
        footer_layout = QVBoxLayout(self._footer_container)
        footer_layout.setContentsMargins(0, 2, 0, 0)
        footer_layout.setSpacing(1)

        self._tier_footer = self._make_footer_row("Tier 1")
        self._cumul_footer = self._make_footer_row("Up to 1")
        footer_layout.addLayout(self._tier_footer["layout"])
        footer_layout.addLayout(self._cumul_footer["layout"])
        layout.addWidget(self._footer_container)
        self._footer_container.setVisible(False)
        layout.addStretch(1)

        # Track spinboxes
        self._mu_spinboxes: list[tuple[int, QDoubleSpinBox]] = []
        self._sorted_entries: list[dict] = []

        # Debounce save
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._save_markups)

        # Cross-thread signals
        self._market_data_ready.connect(self._on_market_data_ready)
        self._inventory_data_ready.connect(self._on_inventory_data_ready)
        self._ingame_data_ready.connect(self._on_ingame_data_ready)

        # Select first available tier
        first_tier = min(self._tier_map.keys()) if self._tier_map else 1
        self._selected_tier = first_tier
        self._update_buttons()
        self._update_materials()
        self._load_source_data()

    # --- Footer helper ---

    @staticmethod
    def _make_footer_row(label_text: str) -> dict:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 6, 0)
        row.setSpacing(4)
        lbl = QLabel(label_text)
        lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
        )
        row.addWidget(lbl, 1)
        parts: dict[str, QLabel] = {}
        for key, prefix, color in [
            ("tt", "TT:", TEXT_DIM), ("mu", "MU:", TEXT_DIM),
            ("total", "Total:", ACCENT),
        ]:
            plbl = QLabel(prefix)
            plbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
            )
            row.addWidget(plbl)
            vlbl = QLabel("0.00")
            vlbl.setStyleSheet(
                f"color: {color}; font-size: 12px;"
                " font-family: monospace; background: transparent;"
            )
            vlbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            row.addWidget(vlbl)
            parts[key] = vlbl
        return {"layout": row, "label": lbl, **parts}

    # --- Tier buttons ---

    def _select_tier(self, tier_num: int):
        self._selected_tier = tier_num
        self._update_buttons()
        self._update_materials()

    def _update_buttons(self):
        for i, btn in enumerate(self._tier_buttons):
            t = i + 1
            selected = t == self._selected_tier
            has_data = t in self._tier_map
            estimated = has_data and deep_get(
                self._tier_map[t], "Properties", "IsExtrapolated",
            )
            border = "dashed" if estimated else "solid"
            if selected:
                style = (
                    f"background: {ACCENT}; color: white;"
                    f" border: 1px {border} {ACCENT}; border-radius: 4px;"
                    " font-size: 12px; font-weight: 600; padding: 0;"
                )
            elif has_data:
                style = (
                    f"background: rgba(40,40,60,180); color: {TEXT_COLOR};"
                    f" border: 1px {border} rgba(80,80,110,180); border-radius: 4px;"
                    " font-size: 12px; font-weight: 600; padding: 0;"
                )
            else:
                style = (
                    f"background: rgba(30,30,45,120); color: {TEXT_DIM};"
                    " border: 1px solid rgba(60,60,80,120); border-radius: 4px;"
                    " font-size: 12px; font-weight: 600; padding: 0;"
                )
            btn.setStyleSheet(f"QPushButton {{ {style} }}")

    # --- MU source toggle ---

    def _set_markup_source(self, source: str):
        if self._markup_source == source:
            return
        self._markup_source = source
        self._update_source_buttons()
        is_custom = source == "custom"
        for _, spinbox in self._mu_spinboxes:
            spinbox.setEnabled(is_custom)
        self._recalculate()
        self._save_timer.start()

    def _update_source_buttons(self):
        for btn, src in [
            (self._btn_custom, "custom"),
            (self._btn_inventory, "inventory"),
            (self._btn_ingame, "ingame"),
            (self._btn_exchange, "exchange"),
        ]:
            active = self._markup_source == src
            enabled = btn.isEnabled()
            if active:
                bg, fg, bc = ACCENT, "white", ACCENT
            elif not enabled:
                bg, fg, bc = "rgba(30,30,45,120)", TEXT_DIM, "rgba(60,60,80,120)"
            else:
                bg, fg, bc = "rgba(40,40,60,180)", TEXT_DIM, "rgba(80,80,110,180)"
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {bg}; color: {fg};"
                f"  border: 1px solid {bc}; border-radius: 3px;"
                f"  font-size: 12px; padding: 1px 6px;"
                f"}}"
            )

    def _get_resolved_markup(self, mat_name: str, idx: int,
                              tier_markups: dict | None = None) -> float:
        if self._markup_source == "exchange":
            wap = self._name_to_wap.get(mat_name)
            if wap is not None:
                return wap
        elif self._markup_source == "ingame":
            igm = self._ingame_markups.get(mat_name)
            if igm is not None:
                return igm
        elif self._markup_source == "inventory":
            item_id = self._name_to_id.get(mat_name)
            if item_id is not None:
                inv = self._inv_markups.get(item_id)
                if inv is not None:
                    return inv
        return (tier_markups or {}).get(idx, 100)

    # --- Market / inventory loading ---

    def _load_source_data(self):
        if not self._nexus_client:
            return

        def _fetch_market():
            try:
                items = self._nexus_client.get_exchange_items()
                if items:
                    for item in items:
                        name = item.get("n")
                        if name:
                            wap = item.get("w")
                            if wap is not None and wap > 0:
                                self._name_to_wap[name] = wap
                            iid = item.get("i")
                            if iid is not None:
                                self._name_to_id[name] = iid
                    self._market_data_ready.emit()
            except Exception:
                pass

        def _fetch_inventory():
            if not self._nexus_client.is_authenticated():
                return
            try:
                inv = self._nexus_client.get_inventory_markups()
                if inv:
                    for entry in inv:
                        iid = entry.get("item_id")
                        mu = entry.get("markup")
                        if iid is not None and mu is not None:
                            self._inv_markups[iid] = mu
                    self._inventory_data_ready.emit()
            except Exception:
                pass

        def _fetch_ingame():
            try:
                data = self._nexus_client.get_ingame_prices()
                if data:
                    for row in data:
                        name = row.get("item_name")
                        if not name:
                            continue
                        mu = (row.get("markup_1d") or row.get("markup_7d")
                              or row.get("markup_30d") or row.get("markup_365d")
                              or row.get("markup_3650d"))
                        if mu is not None:
                            self._ingame_markups[name] = float(mu)
                    self._ingame_data_ready.emit()
            except Exception:
                pass

        threading.Thread(target=_fetch_market, daemon=True, name="detail-fetch-market").start()
        threading.Thread(target=_fetch_inventory, daemon=True, name="detail-fetch-inv").start()
        threading.Thread(target=_fetch_ingame, daemon=True, name="detail-fetch-ingame").start()

    def _on_market_data_ready(self):
        self._btn_exchange.setEnabled(bool(self._name_to_wap))
        self._update_source_buttons()
        if self._markup_source == "exchange":
            self._recalculate()

    def _on_inventory_data_ready(self):
        self._btn_inventory.setEnabled(bool(self._inv_markups))
        self._update_source_buttons()
        if self._markup_source == "inventory":
            self._recalculate()

    def _on_ingame_data_ready(self):
        self._btn_ingame.setEnabled(bool(self._ingame_markups))
        self._update_source_buttons()
        if self._markup_source == "ingame":
            self._recalculate()

    # --- Markup persistence ---

    def _load_markups(self):
        stored = None
        if self._nexus_client and self._nexus_client.is_authenticated():
            try:
                prefs = self._nexus_client.get_preferences()
                if prefs and self._pref_key in prefs:
                    stored = prefs[self._pref_key]
            except Exception:
                pass
        if stored is None:
            try:
                if self._local_path.exists():
                    stored = json.loads(
                        self._local_path.read_text(encoding="utf-8")
                    )
            except Exception:
                pass
        if not stored or not isinstance(stored, dict):
            return
        source = stored.get("_source")
        if source == "market":
            source = "exchange"  # backward compat
        if source in ("custom", "inventory", "ingame", "exchange"):
            self._markup_source = source
        entity_data = stored.get(self._entity_type)
        if not entity_data or not isinstance(entity_data, dict):
            return
        for tier_str, mu_list in entity_data.items():
            if tier_str.startswith("_"):
                continue
            try:
                tier_num = int(tier_str)
            except ValueError:
                continue
            if isinstance(mu_list, list):
                self._markups[tier_num] = {
                    i: float(v) for i, v in enumerate(mu_list) if v is not None
                }

    def _save_markups(self):
        entity_data = {}
        for tier_num, mu_dict in self._markups.items():
            if not mu_dict:
                continue
            max_idx = max(mu_dict.keys()) if mu_dict else -1
            mu_list = [mu_dict.get(i, 100) for i in range(max_idx + 1)]
            entity_data[str(tier_num)] = mu_list

        all_data: dict = {}
        try:
            if self._local_path.exists():
                all_data = json.loads(
                    self._local_path.read_text(encoding="utf-8")
                )
        except Exception:
            pass
        all_data[self._entity_type] = entity_data
        if self._markup_source != "custom":
            all_data["_source"] = self._markup_source
        elif "_source" in all_data:
            del all_data["_source"]
        try:
            self._local_path.parent.mkdir(parents=True, exist_ok=True)
            self._local_path.write_text(
                json.dumps(all_data, indent=2), encoding="utf-8",
            )
        except Exception:
            pass
        if self._nexus_client and self._nexus_client.is_authenticated():
            def _push(data=all_data):
                try:
                    self._nexus_client.save_preference(self._pref_key, data)
                except Exception:
                    pass
            threading.Thread(target=_push, daemon=True, name="detail-save-markups").start()

    # --- Materials display ---

    def _update_materials(self):
        # Clear
        while self._materials_layout.count():
            w = self._materials_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._mu_spinboxes.clear()
        self._sorted_entries = []

        tier_data = self._tier_map.get(self._selected_tier)
        if not tier_data:
            lbl = QLabel("No tier data available")
            lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._materials_layout.addWidget(lbl)
            self._footer_container.setVisible(False)
            return

        materials = tier_data.get("Materials", [])

        if not materials:
            lbl = QLabel("No material data")
            lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._materials_layout.addWidget(lbl)
            self._footer_container.setVisible(False)
            return

        # Parse and sort
        entries = []
        for mat in materials:
            mat_name = deep_get(mat, "Material", "Name") or "Unknown"
            mat_tt = deep_get(mat, "Material", "Properties", "Economy", "MaxTT") or 0
            amount = mat.get("Amount", 0)
            entries.append({
                "name": mat_name, "tt": mat_tt, "amount": amount,
                "sort": self._classify(mat_name),
            })
        entries.sort(key=lambda e: e["sort"])
        self._sorted_entries = entries

        # Header row
        hdr = QWidget()
        hdr.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(0, 0, 0, 1)
        hl.setSpacing(0)
        for text, w, stretch in [
            ("Material", 0, 1), ("Amt", _COL_AMT, 0),
            ("MU%", _COL_MU, 0), ("Cost", _COL_COST, 0),
        ]:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 10px; font-weight: 600;"
                " background: transparent; letter-spacing: 0.3px;"
            )
            if stretch:
                hl.addWidget(lbl, stretch)
            else:
                lbl.setFixedWidth(w)
                hl.addWidget(lbl)
        self._materials_layout.addWidget(hdr)

        # Separator
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(100, 100, 120, 80);")
        self._materials_layout.addWidget(sep)

        # Data rows
        tier_markups = self._markups.get(self._selected_tier, {})
        is_custom = self._markup_source == "custom"

        for row_idx, entry in enumerate(entries):
            mu = self._get_resolved_markup(
                entry["name"], row_idx, tier_markups,
            )
            cost = entry["tt"] * entry["amount"] * mu / 100

            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 1, 0, 1)
            rl.setSpacing(2)

            # Material name (stretch)
            name_lbl = QLabel(entry["name"])
            name_lbl.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;"
            )
            rl.addWidget(name_lbl, 1)

            # Amount
            amt_lbl = QLabel(str(entry["amount"]))
            amt_lbl.setFixedWidth(_COL_AMT)
            amt_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
            )
            rl.addWidget(amt_lbl)

            # MU% spinbox
            spinbox = QDoubleSpinBox()
            spinbox.setDecimals(0)
            spinbox.setMinimum(100)
            spinbox.setMaximum(9999999)
            spinbox.setValue(mu)
            spinbox.setSuffix("%")
            spinbox.setFixedWidth(_COL_MU)
            spinbox.setFixedHeight(20)
            spinbox.setEnabled(is_custom)
            spinbox.setStyleSheet(_OVERLAY_SPIN_STYLE)
            spinbox.valueChanged.connect(
                lambda val, si=row_idx: self._on_markup_changed(si, val)
            )
            rl.addWidget(spinbox)
            self._mu_spinboxes.append((row_idx, spinbox))

            # Cost
            cost_lbl = QLabel(self._fmt_ped(cost))
            cost_lbl.setFixedWidth(_COL_COST)
            cost_lbl.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;"
            )
            rl.addWidget(cost_lbl)

            self._materials_layout.addWidget(row)

        self._footer_container.setVisible(True)
        self._recalculate()

    def _on_markup_changed(self, idx: int, value: float):
        if self._markup_source != "custom":
            return
        t = self._selected_tier
        if t not in self._markups:
            self._markups[t] = {}
        self._markups[t][idx] = value
        self._recalculate()
        self._save_timer.start()

    def _recalculate(self):
        if not self._sorted_entries:
            return
        tier_markups = self._markups.get(self._selected_tier, {})

        tier_tt = 0.0
        tier_total = 0.0
        # Update cost labels and spinbox values
        mat_container = self._materials_container
        # Data rows start after header + separator (indices 2+)
        row_widgets = [
            mat_container.layout().itemAt(i).widget()
            for i in range(2, mat_container.layout().count())
            if mat_container.layout().itemAt(i).widget()
        ]
        for row_idx, entry in enumerate(self._sorted_entries):
            mu = self._get_resolved_markup(
                entry["name"], row_idx, tier_markups,
            )
            base = entry["tt"] * entry["amount"]
            cost = base * mu / 100
            tier_tt += base
            tier_total += cost

            # Update spinbox
            for si, spinbox in self._mu_spinboxes:
                if si == row_idx:
                    spinbox.blockSignals(True)
                    spinbox.setValue(mu)
                    spinbox.blockSignals(False)
                    break

            # Update cost label (last QLabel in the row)
            if row_idx < len(row_widgets):
                row_w = row_widgets[row_idx]
                rl = row_w.layout()
                if rl:
                    last = rl.itemAt(rl.count() - 1)
                    if last and last.widget():
                        last.widget().setText(self._fmt_ped(cost))

        tier_mu = tier_total - tier_tt

        self._tier_footer["label"].setText(f"Tier {self._selected_tier}")
        self._tier_footer["tt"].setText(self._fmt_ped(tier_tt))
        self._tier_footer["mu"].setText(self._fmt_ped(tier_mu))
        self._tier_footer["total"].setText(self._fmt_ped(tier_total))

        # Cumulative: tiers 1 through selected
        cumul_tt = 0.0
        cumul_total = 0.0
        for t in range(1, self._selected_tier + 1):
            t_data = self._tier_map.get(t)
            if not t_data:
                continue
            t_mats = t_data.get("Materials", [])
            t_markups = self._markups.get(t, {})
            t_entries = []
            for mat in t_mats:
                mn = deep_get(mat, "Material", "Name") or "Unknown"
                t_entries.append({
                    "name": mn,
                    "tt": deep_get(mat, "Material", "Properties", "Economy", "MaxTT") or 0,
                    "amount": mat.get("Amount", 0),
                    "sort": self._classify(mn),
                })
            t_entries.sort(key=lambda e: e["sort"])
            for si, en in enumerate(t_entries):
                mu = self._get_resolved_markup(en["name"], si, t_markups)
                base = en["tt"] * en["amount"]
                cumul_tt += base
                cumul_total += base * mu / 100

        cumul_mu = cumul_total - cumul_tt
        self._cumul_footer["label"].setText(f"Up to {self._selected_tier}")
        self._cumul_footer["tt"].setText(self._fmt_ped(cumul_tt))
        self._cumul_footer["mu"].setText(self._fmt_ped(cumul_mu))
        self._cumul_footer["total"].setText(self._fmt_ped(cumul_total))


class _OverlayConstructionWidget(QWidget):
    """Compact overlay-native blueprint construction cost calculator."""

    def __init__(self, item: dict, *, nexus_client=None, parent=None):
        super().__init__(parent)
        from ..ui.widgets.blueprint_detail import (
            _BP_PREF_KEY, _LOCAL_BP_MARKUPS_PATH,
        )
        self._pref_key = _BP_PREF_KEY
        self._local_path = _LOCAL_BP_MARKUPS_PATH
        self._nexus_client = nexus_client
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(1)

        materials = item.get("Materials") or []
        if not materials:
            lbl = QLabel("No material data")
            lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
            return

        # Parse materials
        self._entries: list[dict] = []
        for idx, mat in enumerate(materials):
            mat_item = mat.get("Item") or {}
            name = mat_item.get("Name") or "Unknown"
            tt = deep_get(mat_item, "Properties", "Economy", "MaxTT") or 0
            amount = mat.get("Amount") or 0
            self._entries.append({
                "idx": idx, "name": name, "tt": tt, "amount": amount,
            })

        # Load saved markups
        self._markups: dict[int, float] = {}  # idx → markup pct
        self._all_saved: dict[str, float] = self._load_all_markups()
        for entry in self._entries:
            saved = self._all_saved.get(entry["name"])
            if saved is not None and saved != 100:
                self._markups[entry["idx"]] = saved

        # Debounce save
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._persist_markups)

        # Header
        hdr = QWidget()
        hdr.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(0, 0, 0, 1)
        hl.setSpacing(0)
        for text, w, stretch in [
            ("Ingredient", 0, 1), ("Amt", _COL_AMT, 0),
            ("MU%", _COL_MU, 0), ("Cost", _COL_COST, 0),
        ]:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 10px; font-weight: 600;"
                " background: transparent; letter-spacing: 0.3px;"
            )
            if stretch:
                hl.addWidget(lbl, stretch)
            else:
                lbl.setFixedWidth(w)
                hl.addWidget(lbl)
        layout.addWidget(hdr)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(100, 100, 120, 80);")
        layout.addWidget(sep)

        # Data rows
        self._mu_spinboxes: list[tuple[int, QDoubleSpinBox]] = []
        for entry in self._entries:
            mu = self._markups.get(entry["idx"], 100)
            line_tt = entry["tt"] * entry["amount"]
            cost = line_tt * mu / 100

            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 1, 0, 1)
            rl.setSpacing(2)

            name_lbl = QLabel(entry["name"])
            name_lbl.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;"
            )
            rl.addWidget(name_lbl, 1)

            amt_lbl = QLabel(str(entry["amount"]))
            amt_lbl.setFixedWidth(_COL_AMT)
            amt_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
            )
            rl.addWidget(amt_lbl)

            spinbox = QDoubleSpinBox()
            spinbox.setDecimals(0)
            spinbox.setMinimum(100)
            spinbox.setMaximum(9999999)
            spinbox.setValue(mu)
            spinbox.setSuffix("%")
            spinbox.setFixedWidth(_COL_MU)
            spinbox.setFixedHeight(20)
            spinbox.setStyleSheet(_OVERLAY_SPIN_STYLE)
            spinbox.valueChanged.connect(
                lambda val, i=entry["idx"]: self._on_markup_changed(i, val)
            )
            rl.addWidget(spinbox)
            self._mu_spinboxes.append((entry["idx"], spinbox))

            cost_lbl = QLabel(f"{cost:.2f}")
            cost_lbl.setFixedWidth(_COL_COST)
            cost_lbl.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;"
            )
            rl.addWidget(cost_lbl)

            layout.addWidget(row)

        # Footer separator
        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background-color: rgba(100, 100, 120, 80);")
        layout.addWidget(sep2)

        # Footer: TT / MU / Total
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 6, 0)
        footer.setSpacing(4)
        total_lbl = QLabel("Total")
        total_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
        )
        footer.addWidget(total_lbl, 1)
        for key, prefix, color in [
            ("tt", "TT:", TEXT_DIM), ("mu", "MU:", TEXT_DIM),
            ("total", "Total:", ACCENT),
        ]:
            plbl = QLabel(prefix)
            plbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
            )
            footer.addWidget(plbl)
            vlbl = QLabel("0.00")
            vlbl.setStyleSheet(
                f"color: {color}; font-size: 12px;"
                " font-family: monospace; background: transparent;"
            )
            vlbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            footer.addWidget(vlbl)
            setattr(self, f"_footer_{key}", vlbl)
        layout.addLayout(footer)
        layout.addStretch(1)
        self._recalculate()

    def _on_markup_changed(self, idx: int, value: float):
        self._markups[idx] = value
        for entry in self._entries:
            if entry["idx"] == idx:
                if value == 100:
                    self._all_saved.pop(entry["name"], None)
                else:
                    self._all_saved[entry["name"]] = value
                break
        self._recalculate()
        self._save_timer.start()

    def _load_all_markups(self) -> dict[str, float]:
        stored = None
        if self._nexus_client and self._nexus_client.is_authenticated():
            try:
                prefs = self._nexus_client.get_preferences()
                if prefs and self._pref_key in prefs:
                    stored = prefs[self._pref_key]
            except Exception:
                pass
        if stored is None:
            try:
                if self._local_path.exists():
                    stored = json.loads(
                        self._local_path.read_text(encoding="utf-8")
                    )
            except Exception:
                pass
        if not stored or not isinstance(stored, dict):
            return {}
        return {k: float(v) for k, v in stored.items()
                if isinstance(v, (int, float))}

    def _persist_markups(self):
        data = {k: v for k, v in self._all_saved.items() if v != 100}
        try:
            self._local_path.parent.mkdir(parents=True, exist_ok=True)
            self._local_path.write_text(
                json.dumps(data, indent=2), encoding="utf-8",
            )
        except Exception:
            pass
        if self._nexus_client and self._nexus_client.is_authenticated():
            def _push(d=data):
                try:
                    self._nexus_client.save_preference(self._pref_key, d)
                except Exception:
                    pass
            threading.Thread(target=_push, daemon=True, name="detail-persist-mu").start()

    def _recalculate(self):
        if not hasattr(self, "_entries") or not self._entries:
            return
        total_tt = 0.0
        total_with_mu = 0.0

        # Update cost labels — data rows start at layout index 2
        # (header=0, separator=1, then rows, then sep2, then footer)
        main_layout = self.layout()
        row_start = 2
        for row_idx, entry in enumerate(self._entries):
            mu = self._markups.get(entry["idx"], 100)
            line_tt = entry["tt"] * entry["amount"]
            cost = line_tt * mu / 100
            total_tt += line_tt
            total_with_mu += cost

            widget_idx = row_start + row_idx
            if widget_idx < main_layout.count():
                row_w = main_layout.itemAt(widget_idx).widget()
                if row_w and row_w.layout():
                    last = row_w.layout().itemAt(row_w.layout().count() - 1)
                    if last and last.widget():
                        last.widget().setText(f"{cost:.2f}")

        mu_cost = total_with_mu - total_tt
        self._footer_tt.setText(f"{total_tt:.2f}")
        self._footer_mu.setText(f"{mu_cost:.2f}")
        self._footer_total.setText(f"{total_with_mu:.2f}")


def _build_overlay_tiers(item: dict, nexus_client) -> QWidget:
    """Build a compact overlay-native tier calculator."""
    return _OverlayTiersWidget(item, nexus_client=nexus_client)


def _build_overlay_construction(item: dict, nexus_client) -> QWidget:
    """Build a compact overlay-native blueprint construction calculator."""
    return _OverlayConstructionWidget(item, nexus_client=nexus_client)

