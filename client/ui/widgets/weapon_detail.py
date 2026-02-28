"""Weapon entity detail page — Wikipedia-style infobox with all weapon stats."""

from __future__ import annotations

import threading

import re

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    section_title_label, no_data_label, make_compact_table,
    build_acquisition_content,
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

_TIER_BTN_SIZE = 40
_MAX_TIERS = 10

# Material classification for display sort order (matches web TieringEditor)
_SORT_MAT1 = 0
_SORT_MAT2 = 1
_SORT_GEM = 2
_SORT_BLAZAR = 3
_SORT_COMPONENT = 4
_SORT_UNKNOWN = 5

# Weapon-specific tiering materials (from tieringUtil.js)
_WEAPON_MAT1 = {
    "Lysterium Ingot", "Ganganite Ingot", "Caldorite Ingot",
    "Gazzurdite Ingot", "Erdorium Ingot", "Quantium Ingot",
    "Ignisium Ingot", "Durulium Ingot", "Adomasite Ingot", "Gold Ingot",
}
_WEAPON_MAT2 = {
    "Melchi Crystal", "Garcen Lubricant", "Lytairian Powder",
    "Root Acid", "Angelic Flakes", "Putty",
    "Light Liquid", "Henren Cube", "Binary Energy", "Antimagnetic Oil",
}
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
    if name in _WEAPON_MAT1:
        return _SORT_MAT1
    if name in _WEAPON_MAT2:
        return _SORT_MAT2
    return _SORT_UNKNOWN


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

    _FOOTER_STYLE = (
        f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 500;"
        f" background: transparent;"
    )
    _FOOTER_VALUE_STYLE = (
        f"color: {TEXT}; font-size: 12px; font-weight: 600;"
        f" background: transparent; font-family: monospace;"
    )
    _FOOTER_TOTAL_STYLE = (
        f"color: {ACCENT}; font-size: 12px; font-weight: 600;"
        f" background: transparent; font-family: monospace;"
    )

    def __init__(self, tiers_data: list[dict], parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._tier_map: dict[int, dict] = {}
        for tier in tiers_data:
            tier_num = deep_get(tier, "Properties", "Tier")
            if tier_num is not None:
                self._tier_map[tier_num] = tier

        # Per-tier markup storage: {tier_num: {orig_idx: markup_pct}}
        self._markups: dict[int, dict[int, float]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

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
        layout.addLayout(btn_row)

        # --- Materials container (rebuilt on tier select) ---
        self._materials_container = QWidget()
        self._materials_container.setStyleSheet("background: transparent;")
        self._materials_layout = QVBoxLayout(self._materials_container)
        self._materials_layout.setContentsMargins(0, 0, 0, 0)
        self._materials_layout.setSpacing(0)
        layout.addWidget(self._materials_container)

        # Footer summary labels (created once, updated on recalc)
        self._footer_container = QWidget()
        self._footer_container.setStyleSheet("background: transparent;")
        footer_layout = QVBoxLayout(self._footer_container)
        footer_layout.setContentsMargins(0, 8, 0, 0)
        footer_layout.setSpacing(4)

        self._tier_summary = self._make_footer_row("Current Tier")
        self._cumul_summary = self._make_footer_row("Up To Tier 1")
        footer_layout.addLayout(self._tier_summary["layout"])
        footer_layout.addLayout(self._cumul_summary["layout"])

        layout.addWidget(self._footer_container)
        self._footer_container.setVisible(False)

        # Track spinboxes for recalculation
        self._mu_spinboxes: list[tuple[int, QSpinBox]] = []  # (orig_idx, spinbox)
        self._table: QTableWidget | None = None
        self._sorted_entries: list[dict] = []

        # Select first available tier
        first_tier = min(self._tier_map.keys()) if self._tier_map else 1
        self._selected_tier = first_tier
        self._update_buttons()
        self._update_materials()

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

    def _select_tier(self, tier_num: int):
        self._selected_tier = tier_num
        self._update_buttons()
        self._update_materials()

    def _update_buttons(self):
        for i, btn in enumerate(self._tier_buttons):
            tier_num = i + 1
            is_selected = tier_num == self._selected_tier
            has_data = tier_num in self._tier_map

            if is_selected:
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background-color: {ACCENT}; color: white;"
                    f"  border: 1px solid {ACCENT}; border-radius: 6px;"
                    f"  font-weight: 600; font-size: 14px;"
                    f"}}"
                )
            elif has_data:
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background-color: {PRIMARY}; color: {TEXT};"
                    f"  border: 1px solid {BORDER}; border-radius: 6px;"
                    f"  font-weight: 600; font-size: 14px;"
                    f"}}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background-color: {PRIMARY}; color: {TEXT_MUTED};"
                    f"  border: 1px solid {BORDER}; border-radius: 6px;"
                    f"  font-weight: 600; font-size: 14px;"
                    f"}}"
                )

    def _update_materials(self):
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
            return

        materials = tier_data.get("Materials", [])
        if not materials:
            self._materials_layout.addWidget(
                _no_data_label("No material information available for this tier.")
            )
            self._footer_container.setVisible(False)
            return

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

        for row, entry in enumerate(entries):
            orig_idx = entry["orig_idx"]
            mu = tier_markups.get(orig_idx, 100)
            cost = entry["tt"] * entry["amount"] * mu / 100

            table.setItem(row, 0, QTableWidgetItem(entry["name"]))
            table.setItem(row, 1, QTableWidgetItem(f"{entry['tt']:.4f}"))
            table.setItem(row, 2, QTableWidgetItem(str(entry["amount"])))

            # MU % — editable spinbox
            spinbox = QSpinBox()
            spinbox.setMinimum(100)
            spinbox.setMaximum(99999)
            spinbox.setValue(int(mu))
            spinbox.setSuffix("%")
            spinbox.setStyleSheet(
                f"QSpinBox {{"
                f"  background-color: {PRIMARY}; color: {TEXT};"
                f"  border: 1px solid {BORDER}; border-radius: 3px;"
                f"  padding: 2px 4px; font-size: 12px;"
                f"}}"
                f"QSpinBox:focus {{"
                f"  border-color: {ACCENT};"
                f"}}"
            )
            spinbox.valueChanged.connect(
                lambda val, oi=orig_idx: self._on_markup_changed(oi, val)
            )
            table.setCellWidget(row, 3, spinbox)
            self._mu_spinboxes.append((orig_idx, spinbox))

            # Cost
            table.setItem(row, 4, QTableWidgetItem(f"{cost:.2f}"))

            table.setRowHeight(row, _TABLE_ROW_HEIGHT)

        # Column sizing
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(headers)):
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

    def _on_markup_changed(self, orig_idx: int, value: int):
        """Store markup and recalculate costs."""
        tier = self._selected_tier
        if tier not in self._markups:
            self._markups[tier] = {}
        self._markups[tier][orig_idx] = value
        self._recalculate()

    def _recalculate(self):
        """Update Cost column and footer summaries."""
        if not self._table or not self._sorted_entries:
            return

        tier_markups = self._markups.get(self._selected_tier, {})

        # Update Cost column for current tier
        tier_tt = 0.0
        tier_total = 0.0
        for row, entry in enumerate(self._sorted_entries):
            mu = tier_markups.get(entry["orig_idx"], 100)
            base = entry["tt"] * entry["amount"]
            cost = base * mu / 100
            tier_tt += base
            tier_total += cost

            cost_item = self._table.item(row, 4)
            if cost_item:
                cost_item.setText(f"{cost:.2f}")

        tier_mu = tier_total - tier_tt

        # Current tier summary
        self._tier_summary["label"].setText("Current Tier")
        self._tier_summary["tt"].setText(f"{tier_tt:.2f} PED")
        self._tier_summary["mu"].setText(f"{tier_mu:.2f} PED")
        self._tier_summary["total"].setText(f"{tier_total:.2f} PED")

        # Cumulative cost: tiers 1 through selected
        cumul_tt = 0.0
        cumul_total = 0.0
        for t in range(1, self._selected_tier + 1):
            t_data = self._tier_map.get(t)
            if not t_data:
                continue
            t_mats = t_data.get("Materials", [])
            t_markups = self._markups.get(t, {})
            for orig_idx, mat in enumerate(t_mats):
                tt = deep_get(mat, "Material", "Properties", "Economy", "MaxTT") or 0
                amount = mat.get("Amount", 0)
                mu = t_markups.get(orig_idx, 100)
                base = tt * amount
                cumul_tt += base
                cumul_total += base * mu / 100

        cumul_mu = cumul_total - cumul_tt

        self._cumul_summary["label"].setText(f"Up To Tier {self._selected_tier}")
        self._cumul_summary["tt"].setText(f"{cumul_tt:.2f} PED")
        self._cumul_summary["mu"].setText(f"{cumul_mu:.2f} PED")
        self._cumul_summary["total"].setText(f"{cumul_total:.2f} PED")


# ---------------------------------------------------------------------------
# WeaponDetailView
# ---------------------------------------------------------------------------

class WeaponDetailView(WikiDetailView):
    """Detail view for a single weapon entity."""

    _acquisition_loaded = pyqtSignal(dict)

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, parent=None):
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._show_reload = True  # toggle: True = reload, False = uses/min
        self._acquisition_loaded.connect(self._on_acquisition_loaded)
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
            mf_level = mf.get("Level") or deep_get(item, "Properties", "Level")
            mf_conc = mf.get("Concentration")
            mf_cd = mf.get("Cooldown")
            mf_grp = mf.get("CooldownGroup")

            if mf_level is not None:
                mf_section.add_row(StatRow("Level", fmt_int(mf_level)))
            if mf_conc is not None:
                mf_section.add_row(StatRow("Concentration", f"{mf_conc}s"))
            if mf_cd is not None:
                mf_section.add_row(StatRow("Cooldown", f"{mf_cd}s"))
            if mf_grp is not None:
                mf_section.add_row(StatRow("Cooldown Group", str(mf_grp)))
            self._add_section(mf_section)

        # --- Damage Breakdown ---
        damage = deep_get(item, "Properties", "Damage")
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
            for dt in _DAMAGE_TYPES:
                val = damage.get(dt) or 0
                if val > 0:
                    color = DAMAGE_COLORS.get(dt, TEXT_MUTED)
                    dmg_section.add_row(StatRow(dt, f"{val:.1f}", label_color=color))
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
                self._tiers_section.set_content(_TiersWidget(tiers_data))
            else:
                self._tiers_section.set_content(
                    _no_data_label("No tier information available.")
                )
                self._tiers_section.set_subtitle("No data")
            self._add_article_section(self._tiers_section)

        # --- Acquisition panel ---
        self._acquisition_section = DataSection("Acquisition", expanded=True)
        self._acquisition_section.set_loading()
        self._add_article_section(self._acquisition_section)

        if self._data_client and name:
            def fetch_acq(item_name=name):
                data = self._data_client.get_acquisition(item_name)
                self._acquisition_loaded.emit(data)

            threading.Thread(
                target=fetch_acq, daemon=True, name="acq-fetch"
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

        content = self._build_acquisition_content(data)
        self._acquisition_section.set_content(content)

    def _build_acquisition_content(self, data: dict) -> QWidget:
        """Build the acquisition panel content from API data."""
        return build_acquisition_content(data)
