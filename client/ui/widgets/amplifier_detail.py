"""Weapon amplifier entity detail page — damage, DPS/DPP, economy, tiers."""

from __future__ import annotations

import threading

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    no_data_label, build_acquisition_content, build_usage_content, exchange_url,
)
from ..theme import DAMAGE_COLORS, TEXT_MUTED
from ...data.wiki_columns import (
    deep_get, get_item_name, fmt_int, fmt_bool, _DAMAGE_TYPES,
    weapon_total_damage, weapon_effective_damage,
    weapon_dps, weapon_dpp, weapon_cost_per_use, weapon_total_uses,
)


def _fv(value, decimals: int) -> str:
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"


class AmplifierDetailView(WikiDetailView):
    """Detail view for a single weapon amplifier entity."""

    _acquisition_loaded = pyqtSignal(dict)
    _usage_loaded = pyqtSignal(dict)

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, nexus_client=None, parent=None):
        self._nexus_client = nexus_client
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._acquisition_loaded.connect(self._on_acquisition_loaded)
        self._usage_loaded.connect(self._on_usage_loaded)
        self._build(item)

    def _build(self, item: dict):
        name = get_item_name(item)
        amp_type = deep_get(item, "Properties", "Type") or "-"

        # --- Image ---
        self._add_image_placeholder(name)
        item_id = item.get("Id")
        if item_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/weaponamplifier/{item_id}"
            )

        # --- Badge + title ---
        subtitle_widgets = [self._make_badge(amp_type)]
        self._add_infobox_title(name, subtitle_widgets)

        # --- Tier1: Efficiency, DPS, DPP ---
        eff = deep_get(item, "Properties", "Economy", "Efficiency")
        dps = weapon_dps(item)
        dpp = weapon_dpp(item)

        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow("Efficiency", f"{_fv(eff, 1)}%"))
        tier1.add_row(Tier1StatRow("DPS", _fv(dps, 2)))
        tier1.add_row(Tier1StatRow("DPP", _fv(dpp, 2)))
        self._add_section(tier1)

        # --- Performance ---
        total_dmg = weapon_total_damage(item)
        eff_dmg = weapon_effective_damage(item)

        perf = InfoboxSection("Performance")
        perf.add_row(StatRow("Total Damage", _fv(total_dmg, 1)))
        perf.add_row(StatRow("Eff. Damage", _fv(eff_dmg, 2)))
        self._add_section(perf)

        # --- Economy ---
        max_tt = deep_get(item, "Properties", "Economy", "MaxTT")
        min_tt = deep_get(item, "Properties", "Economy", "MinTT")
        decay = deep_get(item, "Properties", "Economy", "Decay")
        ammo_burn = deep_get(item, "Properties", "Economy", "AmmoBurn")
        cost = weapon_cost_per_use(item)
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
        if ammo_burn is not None and ammo_burn > 0:
            econ.add_row(StatRow("Ammo Burn", fmt_int(ammo_burn)))
        econ.add_row(StatRow(
            "Cost/Use", f"{_fv(cost, 4)} PEC" if cost is not None else "-"
        ))
        econ.add_row(StatRow("Uses", fmt_int(uses)))
        self._add_section(econ)

        # --- Properties ---
        weight = deep_get(item, "Properties", "Weight")
        props = InfoboxSection("Properties")
        props.add_row(StatRow("Type", amp_type))
        props.add_row(StatRow(
            "Weight", f"{fmt_int(weight)} kg" if weight is not None else "-"
        ))
        self._add_section(props)

        # --- Damage Breakdown ---
        damage = deep_get(item, "Properties", "Damage")
        dmg_section = InfoboxSection("Damage")
        if damage:
            total = sum(damage.get(dt) or 0 for dt in _DAMAGE_TYPES)
            if total > 0:
                dmg_section.add_row(StatRow("Total", f"{total:.1f}"))
                from PyQt6.QtWidgets import QWidget as _QW
                sep = _QW()
                sep.setFixedHeight(1)
                from ..theme import BORDER
                sep.setStyleSheet(f"background-color: {BORDER}; margin: 4px 0;")
                dmg_section.add_widget(sep)
            for dt in _DAMAGE_TYPES:
                val = damage.get(dt) or 0
                if val > 0:
                    color = DAMAGE_COLORS.get(dt, TEXT_MUTED)
                    dmg_section.add_row(StatRow(dt, f"{val:.1f}", label_color=color))
        self._add_section(dmg_section)

        # --- Effects ---
        effects_equip = item.get("EffectsOnEquip") or []
        effects_use = item.get("EffectsOnUse") or []
        if effects_equip or effects_use:
            from PyQt6.QtWidgets import QLabel
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

        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Tiers panel (non-L items only) ---
        is_limited = name.endswith("(L)") if name else False
        if not is_limited:
            tiers_data = item.get("Tiers") or []
            tiers_section = DataSection("Tiers", expanded=True)
            if tiers_data:
                tiers_section.set_subtitle(f"{len(tiers_data)} tiers")
                from .weapon_detail import _TiersWidget
                tiers_section.set_content(_TiersWidget(
                    tiers_data, entity_type="Weapon",
                    nexus_client=self._nexus_client,
                ))
            else:
                tiers_section.set_content(
                    no_data_label("No tier information available.")
                )
                tiers_section.set_subtitle("No data")
            self._add_article_section(tiers_section)

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
                target=fetch_data, daemon=True, name="amp-data-fetch"
            ).start()

    def _on_acquisition_loaded(self, data: dict):
        if not hasattr(self, "_acquisition_section"):
            return
        url = exchange_url(self._item, self._nexus_base_url, "WeaponAmplifier")
        self._acquisition_section.set_content(build_acquisition_content(
            data, exchange_link=url, on_navigate=self.entity_navigate.emit))

    def _on_usage_loaded(self, data: dict):
        if not hasattr(self, "_usage_section"):
            return
        url = exchange_url(self._item, self._nexus_base_url, "WeaponAmplifier")
        self._usage_section.set_content(build_usage_content(
            data, exchange_link=url, on_navigate=self.entity_navigate.emit))
