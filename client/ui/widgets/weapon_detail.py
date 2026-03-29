"""Weapon entity detail page — Wikipedia-style infobox with all weapon stats."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import re

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    section_title_label, no_data_label, make_compact_table,
    build_acquisition_content, build_usage_content, exchange_url,
    _TABLE_MAX_HEIGHT, _TABLE_ROW_HEIGHT,
)
from ..theme import (
    PRIMARY, SECONDARY, BORDER, HOVER, TEXT, TEXT_MUTED, ACCENT, DAMAGE_COLORS,
)
from ...data.wiki_columns import (
    deep_get, get_item_name, _DAMAGE_TYPES,
    weapon_total_damage, weapon_effective_damage, weapon_reload,
    weapon_cost_per_use, weapon_dps, weapon_dpp, weapon_total_uses,
    fmt, fmt_int, fmt_bool,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TIER_BTN_SIZE = 32
_MAX_TIERS = 10
_PREF_KEY = "wiki.tierMarkups"
_LOCAL_MARKUPS_PATH = Path(__file__).parent.parent.parent / "data" / "tier_markups.json"

# ---------------------------------------------------------------------------
# Material value lookup (from tieringUtil.js)
# ---------------------------------------------------------------------------

_MAT_VALUES: dict[str, float] = {
    "Tier 1 Component": 0.10, "Tier 2 Component": 0.14, "Tier 3 Component": 0.20,
    "Tier 4 Component": 0.27, "Tier 5 Component": 0.40, "Tier 6 Component": 0.50,
    "Tier 7 Component": 0.70, "Tier 8 Component": 1.00, "Tier 9 Component": 1.40,
    "Tier 10 Component": 2.00,
    "Pile of Garnets": 0.15, "Pile of Opals": 0.20, "Pile of Emeralds": 0.30,
    "Pile of Rubies": 0.40, "Pile of Diamonds": 0.50,
    "Blazar Fragment": 0.00001,
    "Lysterium Ingot": 0.03, "Ganganite Ingot": 0.36, "Caldorite Ingot": 0.51,
    "Gazzurdite Ingot": 0.75, "Erdorium Ingot": 1.20, "Quantium Ingot": 1.80,
    "Ignisium Ingot": 2.10, "Durulium Ingot": 2.40, "Adomasite Ingot": 1.80,
    "Gold Ingot": 3.00,
    "Blausariam Ingot": 0.12, "Frigulite Ingot": 0.36, "Megan Ingot": 0.54,
    "Himi Ingot": 0.426,
    "Melchi Crystal": 0.04, "Garcen Lubricant": 0.20, "Lytairian Powder": 0.38,
    "Root Acid": 0.64, "Angelic Flakes": 1.00, "Putty": 0.78,
    "Light Liquid": 0.84, "Henren Cube": 1.26, "Binary Energy": 1.50,
    "Antimagnetic Oil": 2.00,
    "Oil": 0.02, "Typonolic Gas": 0.30, "Ares Powder": 0.52,
    "Magerian Spray": 0.50, "Medical Compress": 0.18,
    "Simple 1 Conductors": 0.30, "Simple 1 Plastic Springs": 0.40,
    "Simple 1 Plastic Ruds": 0.50, "Simple 2 Conductors": 0.65,
    "Simple 2 Plastic Springs": 0.75, "Simple 2 Plastic Ruds": 0.95,
    "Simple 3 Conductors": 1.10, "Simple 3 Plastic Springs": 1.30,
    "Simple 3 Plastic Ruds": 1.40, "Simple 4 Conductors": 1.50,
    "Animal Muscle Oil": 0.03, "Animal Eye Oil": 0.05, "Animal Thyroid Oil": 0.10,
    "Animal Adrenal Oil": 0.20, "Animal Pancreas Oil": 0.50,
    "Animal Liver Oil": 1.00, "Animal Kidney Oil": 2.00,
    "<Unknown Material>": 0.01,
}

_GENERIC_MATS = {
    "Components": [
        "Tier 1 Component", "Tier 2 Component", "Tier 3 Component",
        "Tier 4 Component", "Tier 5 Component", "Tier 6 Component",
        "Tier 7 Component", "Tier 8 Component", "Tier 9 Component",
        "Tier 10 Component",
    ],
    "Gems": [
        "Pile of Garnets", "Pile of Garnets", "Pile of Opals", "Pile of Opals",
        "Pile of Emeralds", "Pile of Emeralds", "Pile of Rubies", "Pile of Rubies",
        "Pile of Diamonds", "Pile of Diamonds",
    ],
    "Fragments": ["Blazar Fragment"] * 10,
}

_WEAPON_MATS = {
    "Material1": [
        "Lysterium Ingot", "Ganganite Ingot", "Caldorite Ingot",
        "Gazzurdite Ingot", "Erdorium Ingot", "Quantium Ingot",
        "Ignisium Ingot", "Durulium Ingot", "Adomasite Ingot", "Gold Ingot",
    ],
    "Material2": [
        "Melchi Crystal", "Garcen Lubricant", "Lytairian Powder",
        "Root Acid", "Angelic Flakes", "Putty",
        "Light Liquid", "Henren Cube", "Binary Energy", "Antimagnetic Oil",
    ],
}

_ARMOR_MATS = {
    "Material1": [
        "Blausariam Ingot", "Frigulite Ingot", "Megan Ingot",
        "Erdorium Ingot", "Erdorium Ingot", "Quantium Ingot",
        "<Unknown Material>", "<Unknown Material>", "<Unknown Material>",
        "<Unknown Material>",
    ],
    "Material2": [
        "Oil", "Typonolic Gas", "Ares Powder", "Magerian Spray",
        "Angelic Flakes", "Putty", "<Unknown Material>", "<Unknown Material>",
        "<Unknown Material>", "<Unknown Material>",
    ],
}

_MEDICAL_TOOL_MATS = {
    "Material1": [
        "Lysterium Ingot", "Ganganite Ingot", "Caldorite Ingot",
        "Gazzurdite Ingot", "Erdorium Ingot", "Quantium Ingot",
        "Ignisium Ingot", "Durulium Ingot", "Adomasite Ingot", "Gold Ingot",
    ],
    "Material2": [
        "Medical Compress", "Medical Compress", "Medical Compress",
        "Himi Ingot", "Himi Ingot", "<Unknown Material>",
        "<Unknown Material>", "<Unknown Material>", "<Unknown Material>",
        "<Unknown Material>",
    ],
}

_FINDER_MATS = {
    "Material1": [
        "Simple 1 Conductors", "Simple 1 Plastic Springs", "Simple 1 Plastic Ruds",
        "Simple 2 Conductors", "Simple 2 Plastic Springs", "Simple 2 Plastic Ruds",
        "Simple 3 Conductors", "Simple 3 Plastic Springs", "Simple 3 Plastic Ruds",
        "Simple 4 Conductors",
    ],
    "Material2": [
        "Animal Muscle Oil", "Animal Eye Oil", "Animal Thyroid Oil",
        "Animal Adrenal Oil", "Animal Pancreas Oil", "Animal Pancreas Oil",
        "Animal Liver Oil", "Animal Liver Oil", "Animal Kidney Oil",
        "Animal Kidney Oil",
    ],
}

_EXCAVATOR_MATS = {
    "Material1": [
        "Simple 1 Conductors", "Simple 1 Plastic Springs", "Simple 1 Plastic Ruds",
        "Simple 2 Conductors", "Simple 2 Plastic Springs", "Simple 2 Plastic Ruds",
        "Simple 3 Conductors", "Simple 3 Plastic Springs", "Simple 3 Plastic Ruds",
        "Simple 4 Conductors",
    ],
    "Material2": [
        "Oil", "Typonolic Gas", "Ares Powder", "Magerian Spray",
        "Angelic Flakes", "Putty", "<Unknown Material>", "<Unknown Material>",
        "<Unknown Material>", "<Unknown Material>",
    ],
}

_TYPE_MATS: dict[str, dict] = {
    "Weapon": _WEAPON_MATS,
    "ArmorSet": _ARMOR_MATS,
    "MedicalTool": _MEDICAL_TOOL_MATS,
    "Finder": _FINDER_MATS,
    "Excavator": _EXCAVATOR_MATS,
}


def _get_material_arrays(entity_type: str) -> dict:
    return _TYPE_MATS.get(entity_type, _WEAPON_MATS)

# Material classification for display sort order (matches web TieringEditor)
_SORT_MAT1 = 0
_SORT_MAT2 = 1
_SORT_GEM = 2
_SORT_BLAZAR = 3
_SORT_COMPONENT = 4
_SORT_UNKNOWN = 5

# Build sets of all Material1/Material2 names across all item types
_ALL_MAT1: set[str] = set()
_ALL_MAT2: set[str] = set()
for _tm in _TYPE_MATS.values():
    _ALL_MAT1.update(_tm["Material1"])
    _ALL_MAT2.update(_tm["Material2"])
_ALL_MAT1.discard("<Unknown Material>")
_ALL_MAT2.discard("<Unknown Material>")

_RE_TIER_COMPONENT = re.compile(r"^Tier \d+ Component$")


def _classify_material(name: str) -> int:
    """Return sort priority for a tier material name."""
    if not name or name == "<Unknown Material>":
        return _SORT_UNKNOWN
    if name == "Blazar Fragment":
        return _SORT_BLAZAR
    if name.startswith("Pile of "):
        return _SORT_GEM
    if _RE_TIER_COMPONENT.match(name):
        return _SORT_COMPONENT
    if name in _ALL_MAT1:
        return _SORT_MAT1
    if name in _ALL_MAT2:
        return _SORT_MAT2
    return _SORT_UNKNOWN


def _fmt_ped(value: float) -> str:
    """Format PED value, avoiding negative zero."""
    rounded = round(value, 2)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.2f}"


def _extrapolate_tiers(tiers_data: list[dict], entity_type: str) -> list[dict]:
    """Fill missing tiers 1-10 with interpolated data (matches web extrapolateTiers)."""
    if not tiers_data:
        return []

    result = list(tiers_data)
    mat_arrays = _get_material_arrays(entity_type)

    # Find reference tier (most complete materials)
    ref = max(result, key=lambda t: len(t.get("Materials") or []))
    ref_mats = ref.get("Materials") or []
    if len(ref_mats) < 3:
        return result

    base_tier_num = deep_get(ref, "Properties", "Tier") or 1

    # Find Blazar Fragment count and compute base ratios
    blazar_count = 1
    for m in ref_mats:
        if deep_get(m, "Material", "Name") == "Blazar Fragment":
            blazar_count = m.get("Amount", 1)
            break
    min_blazar = round(blazar_count / base_tier_num)

    # Per-fragment cost ratios for each material
    min_mat_values: dict[str, float] = {}
    for m in ref_mats:
        mat_name = deep_get(m, "Material", "Name")
        mat_tt = deep_get(m, "Material", "Properties", "Economy", "MaxTT") or _MAT_VALUES.get(mat_name, 0)
        if mat_name and mat_tt:
            min_mat_values[mat_name] = (m.get("Amount", 0) * mat_tt) / blazar_count

    # Extract base name
    ref_name = ref.get("Name", "")
    match = re.match(r"^(.*?)(?=Tier [1-9]|Tier 10)", ref_name)
    base_name = match.group(1).strip() if match else ref_name

    existing = {deep_get(t, "Properties", "Tier") for t in result}

    for i in range(1, _MAX_TIERS + 1):
        if i in existing:
            # Skip tiers that already have enough materials
            existing_tier = next((t for t in result if deep_get(t, "Properties", "Tier") == i), None)
            if existing_tier and len(existing_tier.get("Materials") or []) >= 3:
                continue

        def _scaled_amount(base_mat_name: str, target_mat_name: str, tier: int) -> int:
            base_val = min_mat_values.get(base_mat_name, 0.1)
            target_tt = _MAT_VALUES.get(target_mat_name, 0.1) or 0.1
            return round(base_val * min_blazar * tier / target_tt)

        comp_name = _GENERIC_MATS["Components"][i - 1]
        gem_name = _GENERIC_MATS["Gems"][i - 1]
        mat1_name = mat_arrays["Material1"][i - 1]
        mat2_name = mat_arrays["Material2"][i - 1]

        new_tier = {
            "Name": f"{base_name} Tier {i}".strip(),
            "Properties": {"Tier": i, "IsExtrapolated": True},
            "Materials": [
                {"Material": {"Name": comp_name, "Properties": {"Economy": {"MaxTT": _MAT_VALUES.get(comp_name, 0)}}},
                 "Amount": _scaled_amount(_GENERIC_MATS["Components"][base_tier_num - 1], comp_name, i)},
                {"Material": {"Name": gem_name, "Properties": {"Economy": {"MaxTT": _MAT_VALUES.get(gem_name, 0)}}},
                 "Amount": _scaled_amount(_GENERIC_MATS["Gems"][base_tier_num - 1], gem_name, i)},
                {"Material": {"Name": "Blazar Fragment", "Properties": {"Economy": {"MaxTT": 0.00001}}},
                 "Amount": min_blazar * i},
                {"Material": {"Name": mat1_name, "Properties": {"Economy": {"MaxTT": _MAT_VALUES.get(mat1_name, 0)}}},
                 "Amount": _scaled_amount(mat_arrays["Material1"][base_tier_num - 1], mat1_name, i)},
                {"Material": {"Name": mat2_name, "Properties": {"Economy": {"MaxTT": _MAT_VALUES.get(mat2_name, 0)}}},
                 "Amount": _scaled_amount(mat_arrays["Material2"][base_tier_num - 1], mat2_name, i)},
            ],
        }
        result.append(new_tier)

    result.sort(key=lambda t: deep_get(t, "Properties", "Tier") or 0)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fv(value, decimals: int) -> str:
    """Format a numeric value with *decimals* decimal places, or '-'."""
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"



# Aliases for backward compatibility within this module
_section_title_label = section_title_label
_no_data_label = no_data_label
_make_compact_table = make_compact_table


# ---------------------------------------------------------------------------
# TiersWidget — tier selector + materials table
# ---------------------------------------------------------------------------

class _TiersWidget(QWidget):
    """Tier selector buttons with materials table and markup calculator."""

    _market_data_ready = pyqtSignal()
    _inventory_data_ready = pyqtSignal()
    _ingame_data_ready = pyqtSignal()

    _FOOTER_STYLE = (
        f"color: {TEXT_MUTED}; font-size: 13px; font-weight: 500;"
        f" background: transparent; border: none;"
    )
    _FOOTER_VALUE_STYLE = (
        f"color: {TEXT}; font-size: 13px; font-weight: 600;"
        f" background: transparent; font-family: monospace; border: none;"
    )
    _FOOTER_TOTAL_STYLE = (
        f"color: {ACCENT}; font-size: 13px; font-weight: 600;"
        f" background: transparent; font-family: monospace; border: none;"
    )

    def __init__(self, tiers_data: list[dict], *, entity_type: str = "Weapon",
                 nexus_client=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._entity_type = entity_type
        self._nexus_client = nexus_client
        self._markup_source: str = "custom"  # custom | inventory | ingame | exchange

        # Market/inventory/in-game data (loaded async)
        self._name_to_wap: dict[str, float] = {}
        self._name_to_id: dict[str, int] = {}
        self._inv_markups: dict[int, float] = {}
        self._ingame_markups: dict[str, float] = {}  # name → markup%

        # Extrapolate missing tiers
        all_tiers = _extrapolate_tiers(tiers_data, entity_type) if tiers_data else []

        self._tier_map: dict[int, dict] = {}
        for tier in all_tiers:
            tier_num = deep_get(tier, "Properties", "Tier")
            if tier_num is not None:
                self._tier_map[tier_num] = tier

        # Per-tier markup storage: {tier_num: {sorted_row_idx: markup_pct}}
        self._markups: dict[int, dict[int, float]] = {}
        self._load_markups()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # --- Tier buttons row ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._tier_buttons: list[QPushButton] = []

        for i in range(1, _MAX_TIERS + 1):
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

        # --- Markup source toggle (right side of tier row) ---
        source_label = QLabel("MU:")
        source_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;"
        )
        btn_row.addWidget(source_label)
        self._btn_custom = QPushButton("Custom")
        self._btn_inventory = QPushButton("Inventory")
        self._btn_ingame = QPushButton("In-Game")
        self._btn_exchange = QPushButton("Exchange")
        self._source_buttons = [
            self._btn_custom, self._btn_inventory, self._btn_ingame, self._btn_exchange
        ]
        for btn in self._source_buttons:
            btn.setFixedHeight(_TIER_BTN_SIZE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_inventory.setEnabled(False)
        self._btn_ingame.setEnabled(False)
        self._btn_exchange.setEnabled(False)
        self._btn_custom.clicked.connect(lambda: self._set_markup_source("custom"))
        self._btn_inventory.clicked.connect(lambda: self._set_markup_source("inventory"))
        self._btn_ingame.clicked.connect(lambda: self._set_markup_source("ingame"))
        self._btn_exchange.clicked.connect(lambda: self._set_markup_source("exchange"))
        btn_row.addWidget(self._btn_custom)
        btn_row.addWidget(self._btn_inventory)
        btn_row.addWidget(self._btn_ingame)
        btn_row.addWidget(self._btn_exchange)
        layout.addLayout(btn_row)
        self._update_source_buttons()

        # --- Estimated label (shown for interpolated tiers) ---
        self._estimated_label = QLabel("Estimated — based on known tier data")
        self._estimated_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; font-style: italic;"
            f" background: transparent; padding: 2px 0;"
        )
        self._estimated_label.setVisible(False)
        layout.addWidget(self._estimated_label)

        # --- Materials container (rebuilt on tier select) ---
        self._materials_container = QWidget()
        self._materials_container.setStyleSheet("background: transparent;")
        self._materials_layout = QVBoxLayout(self._materials_container)
        self._materials_layout.setContentsMargins(0, 0, 0, 0)
        self._materials_layout.setSpacing(0)
        layout.addWidget(self._materials_container)

        # Footer summary labels (created once, updated on recalc)
        self._footer_container = QWidget()
        self._footer_container.setStyleSheet(
            f"background: {SECONDARY}; border: 1px solid {BORDER};"
            f" border-radius: 6px;"
        )
        footer_layout = QVBoxLayout(self._footer_container)
        footer_layout.setContentsMargins(10, 8, 10, 8)
        footer_layout.setSpacing(6)

        self._tier_summary = self._make_footer_row("Current Tier")
        self._cumul_summary = self._make_footer_row("Up To Tier 1")
        footer_layout.addLayout(self._tier_summary["layout"])
        footer_layout.addLayout(self._cumul_summary["layout"])

        layout.addWidget(self._footer_container)
        self._footer_container.setVisible(False)

        # Track spinboxes for recalculation
        self._mu_spinboxes: list[tuple[int, QDoubleSpinBox]] = []
        self._table: QTableWidget | None = None
        self._sorted_entries: list[dict] = []

        # Debounce timer for saving markups
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._save_markups)

        # Connect market/inventory data signals
        self._market_data_ready.connect(self._on_market_data_ready)
        self._inventory_data_ready.connect(self._on_inventory_data_ready)
        self._ingame_data_ready.connect(self._on_ingame_data_ready)

        # Select first available tier
        first_tier = min(self._tier_map.keys()) if self._tier_map else 1
        self._selected_tier = first_tier
        self._update_buttons()
        self._update_materials()

        # Load market/inventory data in background
        self._load_source_data()

    @staticmethod
    def _make_footer_row(label_text: str) -> dict:
        """Create a horizontal summary row with label + TT + MU + Total."""
        row = QHBoxLayout()
        row.setSpacing(8)

        label = QLabel(label_text)
        label.setStyleSheet(_TiersWidget._FOOTER_STYLE)
        row.addWidget(label, 1)

        tt_lbl = QLabel("TT:")
        tt_lbl.setStyleSheet(_TiersWidget._FOOTER_STYLE)
        row.addWidget(tt_lbl)
        tt_val = QLabel("0.00 PED")
        tt_val.setStyleSheet(_TiersWidget._FOOTER_VALUE_STYLE)
        tt_val.setMinimumWidth(80)
        tt_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(tt_val)

        mu_lbl = QLabel("MU:")
        mu_lbl.setStyleSheet(_TiersWidget._FOOTER_STYLE)
        row.addWidget(mu_lbl)
        mu_val = QLabel("0.00 PED")
        mu_val.setStyleSheet(_TiersWidget._FOOTER_VALUE_STYLE)
        mu_val.setMinimumWidth(80)
        mu_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(mu_val)

        total_lbl = QLabel("Total:")
        total_lbl.setStyleSheet(_TiersWidget._FOOTER_STYLE)
        row.addWidget(total_lbl)
        total_val = QLabel("0.00 PED")
        total_val.setStyleSheet(_TiersWidget._FOOTER_TOTAL_STYLE)
        total_val.setMinimumWidth(80)
        total_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(total_val)

        return {"layout": row, "label": label, "tt": tt_val, "mu": mu_val, "total": total_val}

    # --- Markup source toggle ---

    def _set_markup_source(self, source: str):
        if self._markup_source == source:
            return
        self._markup_source = source
        self._update_source_buttons()
        is_custom = source == "custom"
        for _, spinbox in self._mu_spinboxes:
            spinbox.setEnabled(is_custom)
        self._recalculate()
        self._schedule_save()

    def _update_source_buttons(self):
        for btn, src in [
            (self._btn_custom, "custom"),
            (self._btn_inventory, "inventory"),
            (self._btn_ingame, "ingame"),
            (self._btn_exchange, "exchange"),
        ]:
            is_active = self._markup_source == src
            is_enabled = btn.isEnabled()
            if is_active:
                bg = ACCENT
                fg = "white"
                border_color = ACCENT
            elif not is_enabled:
                bg = PRIMARY
                fg = BORDER  # grayed out
                border_color = BORDER
            else:
                bg = PRIMARY
                fg = TEXT_MUTED
                border_color = BORDER
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {bg}; color: {fg};"
                f"  border: 1px solid {border_color}; border-radius: 4px;"
                f"  font-size: 11px; padding: 2px 8px;"
                f"}}"
            )

    def _get_resolved_markup(self, mat_name: str, sorted_idx: int,
                              tier_markups: dict | None = None) -> float:
        """Resolve markup for a material based on current source mode."""
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
        # Fallback to custom markup
        mu = (tier_markups or {}).get(sorted_idx, 100)
        return mu

    def _load_source_data(self):
        """Load market and inventory data in background threads."""
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
                            item_id = item.get("i")
                            if item_id is not None:
                                self._name_to_id[name] = item_id
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

        threading.Thread(
            target=_fetch_market, daemon=True, name="tier-market"
        ).start()
        threading.Thread(
            target=_fetch_inventory, daemon=True, name="tier-inventory"
        ).start()
        threading.Thread(
            target=_fetch_ingame, daemon=True, name="tier-ingame"
        ).start()

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
        """Load saved markups from server (if authenticated) or local file."""
        stored = None
        if self._nexus_client and self._nexus_client.is_authenticated():
            try:
                prefs = self._nexus_client.get_preferences()
                if prefs and _PREF_KEY in prefs:
                    stored = prefs[_PREF_KEY]
            except Exception:
                pass
        if stored is None:
            try:
                if _LOCAL_MARKUPS_PATH.exists():
                    stored = json.loads(
                        _LOCAL_MARKUPS_PATH.read_text(encoding="utf-8")
                    )
            except Exception:
                pass
        if not stored or not isinstance(stored, dict):
            return
        # Restore markup source preference
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
                    i: float(v) for i, v in enumerate(mu_list)
                }

    def _save_markups(self):
        """Persist markups to local file (and server if authenticated)."""
        entity_data = {}
        for tier_num, mu_dict in self._markups.items():
            if not mu_dict:
                continue
            max_idx = max(mu_dict.keys()) if mu_dict else -1
            mu_list = [mu_dict.get(i, 100) for i in range(max_idx + 1)]
            entity_data[str(tier_num)] = mu_list

        all_data: dict = {}
        try:
            if _LOCAL_MARKUPS_PATH.exists():
                all_data = json.loads(
                    _LOCAL_MARKUPS_PATH.read_text(encoding="utf-8")
                )
        except Exception:
            pass
        all_data[self._entity_type] = entity_data
        if self._markup_source != "custom":
            all_data["_source"] = self._markup_source
        elif "_source" in all_data:
            del all_data["_source"]

        try:
            _LOCAL_MARKUPS_PATH.parent.mkdir(parents=True, exist_ok=True)
            _LOCAL_MARKUPS_PATH.write_text(
                json.dumps(all_data, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

        if self._nexus_client and self._nexus_client.is_authenticated():
            def _push(data=all_data):
                try:
                    self._nexus_client.save_preference(_PREF_KEY, data)
                except Exception:
                    pass
            threading.Thread(
                target=_push, daemon=True, name="tier-mu-save"
            ).start()

    def _schedule_save(self):
        """Restart the debounce timer for markup persistence."""
        self._save_timer.start()

    # --- Tier selection ---

    def _select_tier(self, tier_num: int):
        self._selected_tier = tier_num
        self._update_buttons()
        self._update_materials()

    def _update_buttons(self):
        for i, btn in enumerate(self._tier_buttons):
            tier_num = i + 1
            is_selected = tier_num == self._selected_tier
            has_data = tier_num in self._tier_map
            is_estimated = has_data and deep_get(
                self._tier_map[tier_num], "Properties", "IsExtrapolated"
            )

            border_style = "dashed" if is_estimated else "solid"
            if is_selected:
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background-color: {ACCENT}; color: white;"
                    f"  border: 1px {border_style} {ACCENT}; border-radius: 6px;"
                    f"  font-weight: 600; font-size: 13px; padding: 0;"
                    f"}}"
                )
            elif has_data:
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background-color: {PRIMARY}; color: {TEXT};"
                    f"  border: 1px {border_style} {BORDER}; border-radius: 6px;"
                    f"  font-weight: 600; font-size: 13px; padding: 0;"
                    f"}}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background-color: {PRIMARY}; color: {TEXT_MUTED};"
                    f"  border: 1px solid {BORDER}; border-radius: 6px;"
                    f"  font-weight: 600; font-size: 13px; padding: 0;"
                    f"}}"
                )

    def _update_materials(self):
        # Lock height to prevent parent scroll area from jumping
        self._materials_container.setMinimumHeight(
            self._materials_container.height()
        )

        # Clear previous table
        while self._materials_layout.count():
            item = self._materials_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._mu_spinboxes.clear()
        self._table = None
        self._sorted_entries = []

        tier_data = self._tier_map.get(self._selected_tier)
        if not tier_data:
            self._materials_layout.addWidget(
                _no_data_label("No material information available for this tier.")
            )
            self._footer_container.setVisible(False)
            self._estimated_label.setVisible(False)
            self._materials_container.setMinimumHeight(0)
            return

        materials = tier_data.get("Materials", [])
        if not materials:
            self._materials_layout.addWidget(
                _no_data_label("No material information available for this tier.")
            )
            self._footer_container.setVisible(False)
            self._estimated_label.setVisible(False)
            self._materials_container.setMinimumHeight(0)
            return

        # Show "Estimated" label for interpolated tiers
        is_estimated = deep_get(tier_data, "Properties", "IsExtrapolated")
        self._estimated_label.setVisible(bool(is_estimated))

        # Parse and sort materials by category
        entries = []
        for orig_idx, mat in enumerate(materials):
            mat_name = deep_get(mat, "Material", "Name") or "Unknown"
            mat_tt = deep_get(mat, "Material", "Properties", "Economy", "MaxTT") or 0
            amount = mat.get("Amount", 0)
            entries.append({
                "orig_idx": orig_idx,
                "name": mat_name,
                "tt": mat_tt,
                "amount": amount,
                "sort": _classify_material(mat_name),
            })
        entries.sort(key=lambda e: e["sort"])
        self._sorted_entries = entries

        # Build 5-column table
        headers = ["Material", "TT", "Amount", "MU %", "Cost"]
        num_rows = len(entries)
        table = QTableWidget(num_rows, len(headers))
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

        tier_markups = self._markups.get(self._selected_tier, {})
        is_custom = self._markup_source == "custom"

        for row, entry in enumerate(entries):
            mu = self._get_resolved_markup(
                entry["name"], row, tier_markups
            )
            cost = entry["tt"] * entry["amount"] * mu / 100

            table.setItem(row, 0, QTableWidgetItem(entry["name"]))
            table.setItem(row, 1, QTableWidgetItem(f"{entry['tt']:.4f}"))
            table.setItem(row, 2, QTableWidgetItem(str(entry["amount"])))

            # MU % — editable spinbox
            spinbox = QDoubleSpinBox()
            spinbox.setDecimals(2)
            spinbox.setMinimum(100)
            spinbox.setMaximum(9999999.99)
            spinbox.setValue(mu)
            spinbox.setSuffix("%")
            spinbox.setFixedHeight(_TABLE_ROW_HEIGHT - 4)
            spinbox.setEnabled(is_custom)
            spinbox.setStyleSheet(
                f"QDoubleSpinBox {{"
                f"  background-color: {PRIMARY}; color: {TEXT};"
                f"  border: 1px solid {BORDER}; border-radius: 3px;"
                f"  padding: 2px 6px; font-size: 12px;"
                f"}}"
                f"QDoubleSpinBox:focus {{"
                f"  border-color: {ACCENT};"
                f"}}"
                f"QDoubleSpinBox:disabled {{"
                f"  color: {TEXT_MUTED};"
                f"}}"
                f"QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{"
                f"  width: 0; height: 0; border: none;"
                f"}}"
                f"QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {{"
                f"  image: none;"
                f"}}"
            )
            spinbox.valueChanged.connect(
                lambda val, si=row: self._on_markup_changed(si, val)
            )
            table.setCellWidget(row, 3, spinbox)
            self._mu_spinboxes.append((row, spinbox))

            # Cost
            table.setItem(row, 4, QTableWidgetItem(_fmt_ped(cost)))

            table.setRowHeight(row, _TABLE_ROW_HEIGHT)

        # Column sizing
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(headers)):
            if i == 3:  # MU % — fixed width for padding around input
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                header.resizeSection(i, 120)
            elif i == 4:  # Cost — fixed width to avoid resizing on value changes
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                header.resizeSection(i, 120)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        # Right-align numeric columns
        for row in range(num_rows):
            for col in (1, 2, 4):
                item = table.item(row, col)
                if item:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )

        content_height = _TABLE_ROW_HEIGHT + num_rows * _TABLE_ROW_HEIGHT + 4
        table.setFixedHeight(min(content_height, _TABLE_MAX_HEIGHT))

        self._table = table
        self._materials_layout.addWidget(table)

        # Show footer and recalculate
        self._footer_container.setVisible(True)
        self._recalculate()
        self._materials_container.setMinimumHeight(0)

    def _on_markup_changed(self, sorted_idx: int, value: float):
        """Store markup and recalculate costs (only in custom mode)."""
        if self._markup_source != "custom":
            return
        tier = self._selected_tier
        if tier not in self._markups:
            self._markups[tier] = {}
        self._markups[tier][sorted_idx] = value
        self._recalculate()
        self._schedule_save()

    def _recalculate(self):
        """Update Cost column and footer summaries."""
        if not self._table or not self._sorted_entries:
            return

        tier_markups = self._markups.get(self._selected_tier, {})

        # Update Cost column and spinbox values for current tier
        tier_tt = 0.0
        tier_total = 0.0
        for row, entry in enumerate(self._sorted_entries):
            mu = self._get_resolved_markup(
                entry["name"], row, tier_markups
            )
            base = entry["tt"] * entry["amount"]
            cost = base * mu / 100
            tier_tt += base
            tier_total += cost

            cost_item = self._table.item(row, 4)
            if cost_item:
                cost_item.setText(_fmt_ped(cost))

            # Update spinbox value when source changes
            for si, spinbox in self._mu_spinboxes:
                if si == row:
                    spinbox.blockSignals(True)
                    spinbox.setValue(mu)
                    spinbox.blockSignals(False)
                    break

        tier_mu = tier_total - tier_tt

        # Current tier summary
        self._tier_summary["label"].setText("Current Tier")
        self._tier_summary["tt"].setText(f"{_fmt_ped(tier_tt)} PED")
        self._tier_summary["mu"].setText(f"{_fmt_ped(tier_mu)} PED")
        self._tier_summary["total"].setText(f"{_fmt_ped(tier_total)} PED")

        # Cumulative cost: tiers 1 through selected
        cumul_tt = 0.0
        cumul_total = 0.0
        for t in range(1, self._selected_tier + 1):
            t_data = self._tier_map.get(t)
            if not t_data:
                continue
            t_mats = t_data.get("Materials", [])
            t_markups = self._markups.get(t, {})

            # Sort the same way to match stored markup indices
            t_entries = []
            for mat in t_mats:
                mat_name = deep_get(mat, "Material", "Name") or "Unknown"
                t_entries.append({
                    "name": mat_name,
                    "tt": deep_get(mat, "Material", "Properties", "Economy", "MaxTT") or 0,
                    "amount": mat.get("Amount", 0),
                    "sort": _classify_material(mat_name),
                })
            t_entries.sort(key=lambda e: e["sort"])

            for sorted_idx, entry in enumerate(t_entries):
                mu = self._get_resolved_markup(
                    entry["name"], sorted_idx, t_markups
                )
                base = entry["tt"] * entry["amount"]
                cumul_tt += base
                cumul_total += base * mu / 100

        cumul_mu = cumul_total - cumul_tt

        self._cumul_summary["label"].setText(f"Up To Tier {self._selected_tier}")
        self._cumul_summary["tt"].setText(f"{_fmt_ped(cumul_tt)} PED")
        self._cumul_summary["mu"].setText(f"{_fmt_ped(cumul_mu)} PED")
        self._cumul_summary["total"].setText(f"{_fmt_ped(cumul_total)} PED")


# ---------------------------------------------------------------------------
# WeaponDetailView
# ---------------------------------------------------------------------------

class WeaponDetailView(WikiDetailView):
    """Detail view for a single weapon entity."""

    _acquisition_loaded = pyqtSignal(dict)
    _usage_loaded = pyqtSignal(dict)

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, nexus_client=None, parent=None):
        self._nexus_client = nexus_client
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._show_reload = True  # toggle: True = reload, False = uses/min
        self._acquisition_loaded.connect(self._on_acquisition_loaded)
        self._usage_loaded.connect(self._on_usage_loaded)
        self._build(item)

    def _build(self, item: dict):
        name = get_item_name(item)
        weapon_class = deep_get(item, "Properties", "Class") or "-"
        category = deep_get(item, "Properties", "Category") or "-"
        weapon_type = deep_get(item, "Properties", "Type") or "-"

        # --- Infobox header: image, name, subtitle ---
        self._add_image_placeholder(name)

        # Start async image load
        weapon_id = item.get("Id")
        if weapon_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/weapon/{weapon_id}"
            )

        subtitle_widgets = [
            self._make_badge(weapon_class),
            self._make_subtitle_text(category),
            self._make_subtitle_text("·"),
            self._make_subtitle_text(weapon_type),
        ]
        self._add_infobox_title(name, subtitle_widgets)

        # --- Tier 1: Efficiency, DPS, DPP (blue gradient) ---
        eff = deep_get(item, "Properties", "Economy", "Efficiency")
        dps = weapon_dps(item)
        dpp = weapon_dpp(item)

        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow("Efficiency", f"{_fv(eff, 1)}%"))
        tier1.add_row(Tier1StatRow("DPS", _fv(dps, 2)))
        tier1.add_row(Tier1StatRow("DPP", _fv(dpp, 2)))
        self._add_section(tier1)

        # --- Performance ---
        eff_dmg = weapon_effective_damage(item)
        range_val = deep_get(item, "Properties", "Range")
        reload_val = weapon_reload(item)
        upm = deep_get(item, "Properties", "UsesPerMinute")
        cost = weapon_cost_per_use(item)

        perf = InfoboxSection("Performance")

        perf.add_row(StatRow("Eff. Dmg", _fv(eff_dmg, 2)))
        perf.add_row(StatRow(
            "Range", f"{fmt_int(range_val)}m" if range_val is not None else "-"
        ))

        # Toggleable reload / uses per min row
        self._reload_row = StatRow(
            "Reload",
            f"{_fv(reload_val, 2)}s" if reload_val is not None else "-",
            toggleable=True,
        )
        self._reload_row.clicked.connect(self._toggle_reload)
        self._upm_value = fmt_int(upm)
        self._reload_value = (
            f"{_fv(reload_val, 2)}s" if reload_val is not None else "-"
        )
        perf.add_row(self._reload_row)

        perf.add_row(StatRow(
            "Cost/Use", f"{_fv(cost, 4)} PEC" if cost is not None else "-"
        ))
        self._add_section(perf)

        # --- Economy ---
        max_tt = deep_get(item, "Properties", "Economy", "MaxTT")
        min_tt = deep_get(item, "Properties", "Economy", "MinTT")
        decay = deep_get(item, "Properties", "Economy", "Decay")
        ammo_burn = deep_get(item, "Properties", "Economy", "AmmoBurn")
        ammo_name = deep_get(item, "Ammo", "Name")
        uses = weapon_total_uses(item)

        econ = InfoboxSection("Economy")
        econ.add_row(StatRow(
            "Eff.", f"{_fv(eff, 1)}%" if eff is not None else "-"
        ))
        econ.add_row(StatRow(
            "Max TT", f"{_fv(max_tt, 2)} PED" if max_tt is not None else "-"
        ))
        econ.add_row(StatRow(
            "Min TT", f"{_fv(min_tt, 2)} PED" if min_tt is not None else "-"
        ))
        econ.add_row(StatRow(
            "Decay", f"{_fv(decay, 2)} PEC" if decay is not None else "-"
        ))
        if ammo_name:
            econ.add_row(StatRow("Ammo", ammo_name))
        if ammo_burn is not None and ammo_burn > 0:
            econ.add_row(StatRow("Burn", fmt_int(ammo_burn)))
        econ.add_row(StatRow("Uses", fmt_int(uses)))
        self._add_section(econ)

        # --- Properties ---
        weight = deep_get(item, "Properties", "Weight")
        impact_radius = deep_get(item, "Properties", "ImpactRadius")
        attachment_type = deep_get(item, "AttachmentType", "Name")

        props = InfoboxSection("Properties")
        props.add_row(StatRow("Class", weapon_class))
        props.add_row(StatRow("Category", category))
        props.add_row(StatRow("Type", weapon_type))
        if weapon_class == "Attached" and attachment_type:
            props.add_row(StatRow("Attach.", attachment_type))
        props.add_row(StatRow(
            "Weight",
            f"{fmt_int(weight)} kg" if weight is not None else "-",
        ))
        if weapon_type == "Explosive" and impact_radius is not None:
            props.add_row(StatRow("Radius", f"{fmt_int(impact_radius)}m"))
        self._add_section(props)

        # --- Skilling ---
        is_sib = deep_get(item, "Properties", "Skill", "IsSiB")
        hit_prof = deep_get(item, "ProfessionHit", "Name")
        dmg_prof = deep_get(item, "ProfessionDmg", "Name")
        hit_min = deep_get(item, "Properties", "Skill", "Hit", "LearningIntervalStart")
        hit_max = deep_get(item, "Properties", "Skill", "Hit", "LearningIntervalEnd")
        dmg_min = deep_get(item, "Properties", "Skill", "Dmg", "LearningIntervalStart")
        dmg_max = deep_get(item, "Properties", "Skill", "Dmg", "LearningIntervalEnd")

        skill = InfoboxSection("Skilling")
        skill.add_row(StatRow(
            "SiB", fmt_bool(is_sib), highlight=(is_sib is True or is_sib == 1)
        ))
        if hit_prof:
            skill.add_row(StatRow("Hit Prof.", hit_prof))
        if is_sib and (hit_min is not None or hit_max is not None):
            skill.add_row(StatRow(
                "Hit Range",
                f"{fmt_int(hit_min)} - {fmt_int(hit_max)}",
                indent=True,
            ))
        if dmg_prof:
            skill.add_row(StatRow("Dmg Prof.", dmg_prof))
        if is_sib and (dmg_min is not None or dmg_max is not None):
            skill.add_row(StatRow(
                "Dmg Range",
                f"{fmt_int(dmg_min)} - {fmt_int(dmg_max)}",
                indent=True,
            ))
        self._add_section(skill)

        # --- Mindforce (conditional) ---
        mf = deep_get(item, "Properties", "Mindforce")
        if weapon_class == "Mindforce" and mf:
            mf_section = InfoboxSection("Mindforce")
            mf_section.add_row(StatRow("Level", fmt_int(mf.get("Level"))))
            mf_section.add_row(StatRow(
                "Concentration",
                f"{mf.get('Concentration')}s" if mf.get("Concentration") is not None else "-",
            ))
            mf_section.add_row(StatRow(
                "Cooldown",
                f"{mf.get('Cooldown')}s" if mf.get("Cooldown") is not None else "-",
            ))
            mf_section.add_row(StatRow(
                "CD Group",
                str(mf.get("CooldownGroup")) if mf.get("CooldownGroup") is not None else "-",
            ))
            self._add_section(mf_section)

        # --- Damage Breakdown ---
        damage = deep_get(item, "Properties", "Damage")
        is_mining_weapon = weapon_type.startswith("Mining Laser")
        dmg_section = InfoboxSection("Damage")
        if damage:
            total = sum(damage.get(dt) or 0 for dt in _DAMAGE_TYPES)
            if total > 0:
                dmg_section.add_row(StatRow("Total", f"{total:.1f}"))
                # Thin separator between total and per-type rows
                sep = QWidget()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background-color: {BORDER}; margin: 4px 0;")
                dmg_section.add_widget(sep)
            visible_types = ["Impact"] if is_mining_weapon else _DAMAGE_TYPES
            for dt in visible_types:
                val = damage.get(dt) or 0
                if val > 0:
                    color = DAMAGE_COLORS.get(dt, TEXT_MUTED)
                    label = "Mining" if is_mining_weapon and dt == "Impact" else dt
                    dmg_section.add_row(StatRow(label, f"{val:.1f}", label_color=color))
        self._add_section(dmg_section)

        # --- Effects (conditional) ---
        effects_equip = item.get("EffectsOnEquip") or []
        effects_use = item.get("EffectsOnUse") or []
        if effects_equip or effects_use:
            eff_section = InfoboxSection("Effects")
            if effects_equip:
                sub_lbl = QLabel("On Equip")
                sub_lbl.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600;"
                    " background: transparent; margin-top: 4px;"
                )
                eff_section.add_widget(sub_lbl)
                for e in effects_equip:
                    eff_section.add_row(StatRow(
                        e.get("Name", "Unknown"), "", indent=True
                    ))
            if effects_use:
                sub_lbl = QLabel("On Use")
                sub_lbl.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600;"
                    " background: transparent; margin-top: 4px;"
                )
                eff_section.add_widget(sub_lbl)
                for e in effects_use:
                    eff_section.add_row(StatRow(
                        e.get("Name", "Unknown"), "", indent=True
                    ))
            self._add_section(eff_section)

        # Stretch at bottom of infobox
        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Tiers panel (only for non-limited items) ---
        is_limited = name.endswith("(L)") if name else False
        if not is_limited:
            tiers_data = item.get("Tiers") or []
            self._tiers_section = DataSection("Tiers", expanded=True)
            if tiers_data:
                self._tiers_section.set_subtitle(f"{len(tiers_data)} tiers")
                self._tiers_section.set_content(_TiersWidget(
                    tiers_data, entity_type="Weapon",
                    nexus_client=self._nexus_client,
                ))
            else:
                self._tiers_section.set_content(
                    _no_data_label("No tier information available.")
                )
                self._tiers_section.set_subtitle("No data")
            self._add_article_section(self._tiers_section)

        # --- Market Prices panel ---
        self._setup_market_prices_section()

        # --- Acquisition panel ---
        self._acquisition_section = DataSection("Acquisition", expanded=True)
        self._acquisition_section.set_loading()
        self._add_article_section(self._acquisition_section)

        # --- Usage panel ---
        self._usage_section = DataSection("Usage", expanded=True)
        self._usage_section.set_loading()
        self._add_article_section(self._usage_section)

        if self._data_client and name:
            def fetch_data(item_name=name):
                acq_data = self._data_client.get_acquisition(item_name)
                self._acquisition_loaded.emit(acq_data)
                usage_data = self._data_client.get_usage(item_name)
                self._usage_loaded.emit(usage_data)

            threading.Thread(
                target=fetch_data, daemon=True, name="weapon-data-fetch"
            ).start()

    # --- Toggle reload / uses per min ---

    def _toggle_reload(self):
        self._show_reload = not self._show_reload
        if self._show_reload:
            self._reload_row._value_label.setText(self._reload_value)
            # Update label via direct access
            lbl = self._reload_row.layout().itemAt(0).widget()
            if lbl:
                lbl.setText("Reload")
        else:
            self._reload_row._value_label.setText(self._upm_value)
            lbl = self._reload_row.layout().itemAt(0).widget()
            if lbl:
                lbl.setText("Uses/min")

    # --- Async data handlers ---

    def _on_acquisition_loaded(self, data: dict):
        """Handle acquisition data arriving from background thread."""
        if not hasattr(self, "_acquisition_section"):
            return
        url = exchange_url(self._item, self._nexus_base_url, "Weapon")
        self._acquisition_section.set_content(build_acquisition_content(
            data, exchange_link=url, on_navigate=self.entity_navigate.emit))

    def _on_usage_loaded(self, data: dict):
        if not hasattr(self, "_usage_section"):
            return
        url = exchange_url(self._item, self._nexus_base_url, "Weapon")
        self._usage_section.set_content(build_usage_content(
            data, exchange_link=url, on_navigate=self.entity_navigate.emit))
