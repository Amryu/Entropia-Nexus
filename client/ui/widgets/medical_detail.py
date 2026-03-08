"""Medical tool/chip entity detail page — HPS, HPP, heal stats, economy."""

from __future__ import annotations

import threading

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    no_data_label, build_acquisition_content, build_usage_content,
    exchange_url, PAGE_TYPE_TO_ENTITY,
)
from ..theme import TEXT_MUTED
from ...data.wiki_columns import (
    deep_get, get_item_name, fmt_int, fmt_bool,
    weapon_reload, weapon_cost_per_use, weapon_total_uses,
    _medical_hps, _medical_hpp, _medical_effective_healing,
)


def _fv(value, decimals: int) -> str:
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"


# Image type mapping for medical subtypes
_MEDICAL_IMAGE_TYPE = {
    "medicaltools": "medicaltool",
    "medicalchips": "medicalchip",
}


class MedicalDetailView(WikiDetailView):
    """Detail view for medical tools and medical chips."""

    _acquisition_loaded = pyqtSignal(dict)
    _usage_loaded = pyqtSignal(dict)

    def __init__(self, item: dict, *, page_type_id: str = "medicaltools",
                 nexus_base_url: str = "", data_client=None,
                 nexus_client=None, parent=None):
        self._nexus_client = nexus_client
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._page_type_id = page_type_id
        self._acquisition_loaded.connect(self._on_acquisition_loaded)
        self._usage_loaded.connect(self._on_usage_loaded)
        self._build(item)

    def _build(self, item: dict):
        name = get_item_name(item)
        is_chip = self._page_type_id == "medicalchips"

        # --- Image ---
        self._add_image_placeholder(name)
        item_id = item.get("Id")
        image_type = _MEDICAL_IMAGE_TYPE.get(self._page_type_id, "medicaltool")
        if item_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/{image_type}/{item_id}"
            )

        # --- Badge + title ---
        badge_text = "Medical Chip" if is_chip else "Medical Tool"
        subtitle_widgets = [self._make_badge(badge_text)]
        self._add_infobox_title(name, subtitle_widgets)

        # --- Tier1: HPS, HPP ---
        hps = _medical_hps(item)
        hpp = _medical_hpp(item)

        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow("HPS", _fv(hps, 1)))
        tier1.add_row(Tier1StatRow("HPP", _fv(hpp, 1)))
        self._add_section(tier1)

        # --- Healing ---
        max_heal = deep_get(item, "Properties", "MaxHeal")
        min_heal = deep_get(item, "Properties", "MinHeal")
        upm = deep_get(item, "Properties", "UsesPerMinute")
        reload_val = weapon_reload(item)

        healing = InfoboxSection("Healing")
        healing.add_row(StatRow("Max Heal", _fv(max_heal, 1)))
        healing.add_row(StatRow("Min Heal", _fv(min_heal, 1)))
        healing.add_row(StatRow("Uses/Min", fmt_int(upm)))
        healing.add_row(StatRow(
            "Interval",
            f"{_fv(reload_val, 2)}s" if reload_val is not None else "-",
        ))
        self._add_section(healing)

        # --- Economy ---
        max_tt = deep_get(item, "Properties", "Economy", "MaxTT")
        min_tt = deep_get(item, "Properties", "Economy", "MinTT")
        decay = deep_get(item, "Properties", "Economy", "Decay")
        ammo_burn = deep_get(item, "Properties", "Economy", "AmmoBurn")
        cost = weapon_cost_per_use(item)
        uses = weapon_total_uses(item)

        econ = InfoboxSection("Economy")
        econ.add_row(StatRow(
            "Max TT", f"{_fv(max_tt, 2)} PED" if max_tt is not None else "-"
        ))
        econ.add_row(StatRow(
            "Min TT", f"{_fv(min_tt, 2)} PED" if min_tt is not None else "-"
        ))
        econ.add_row(StatRow(
            "Decay", f"{_fv(decay, 2)} PEC" if decay is not None else "-"
        ))
        if is_chip and ammo_burn is not None and ammo_burn > 0:
            econ.add_row(StatRow("Ammo Burn", fmt_int(ammo_burn)))
        econ.add_row(StatRow(
            "Cost/Use", f"{_fv(cost, 4)} PEC" if cost is not None else "-"
        ))
        econ.add_row(StatRow("Uses", fmt_int(uses)))
        self._add_section(econ)

        # --- Skill ---
        is_sib = deep_get(item, "Properties", "Skill", "IsSiB")
        profession = deep_get(item, "Profession", "Name")
        skill_start = deep_get(item, "Properties", "Skill", "LearningIntervalStart")
        if skill_start is None:
            skill_start = deep_get(item, "Properties", "Skill", "Hit", "LearningIntervalStart")
        skill_end = deep_get(item, "Properties", "Skill", "LearningIntervalEnd")
        if skill_end is None:
            skill_end = deep_get(item, "Properties", "Skill", "Hit", "LearningIntervalEnd")

        skill = InfoboxSection("Skill")
        skill.add_row(StatRow(
            "SiB", fmt_bool(is_sib),
            highlight=(is_sib is True or is_sib == 1),
        ))
        if profession:
            skill.add_row(StatRow("Profession", profession))
        if is_sib and (skill_start is not None or skill_end is not None):
            skill.add_row(StatRow(
                "Level Range",
                f"{fmt_int(skill_start)} - {fmt_int(skill_end)}",
                indent=True,
            ))
        self._add_section(skill)

        # --- Mindforce (chips) ---
        if is_chip:
            mf_level = deep_get(item, "Properties", "Mindforce", "Level")
            mf_conc = deep_get(item, "Properties", "Mindforce", "Concentration")
            mf_cd = deep_get(item, "Properties", "Mindforce", "Cooldown")
            mf_grp = deep_get(item, "Properties", "Mindforce", "CooldownGroup")
            range_val = deep_get(item, "Properties", "Range")

            mf_section = InfoboxSection("Mindforce")
            mf_section.add_row(StatRow("Level", fmt_int(mf_level)))
            mf_section.add_row(StatRow(
                "Concentration", f"{mf_conc}s" if mf_conc is not None else "-",
            ))
            if range_val is not None:
                mf_section.add_row(StatRow("Range", f"{fmt_int(range_val)}m"))
            mf_section.add_row(StatRow(
                "Cooldown", f"{mf_cd}s" if mf_cd is not None else "-",
            ))
            mf_section.add_row(StatRow(
                "CD Group", str(mf_grp) if mf_grp is not None else "-",
            ))
            self._add_section(mf_section)

        # --- Effects ---
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

        # --- Properties ---
        weight = deep_get(item, "Properties", "Weight")
        props = InfoboxSection("Properties")
        props.add_row(StatRow(
            "Weight", f"{fmt_int(weight)} kg" if weight is not None else "-"
        ))
        self._add_section(props)

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
                    tiers_data, entity_type="MedicalTool",
                    nexus_client=self._nexus_client,
                ))
            else:
                tiers_section.set_content(
                    no_data_label("No tier information available.")
                )
                tiers_section.set_subtitle("No data")
            self._add_article_section(tiers_section)

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
                target=fetch_data, daemon=True, name="med-data-fetch"
            ).start()

    def _on_acquisition_loaded(self, data: dict):
        if not hasattr(self, "_acquisition_section"):
            return
        et = PAGE_TYPE_TO_ENTITY.get(self._page_type_id, "")
        url = exchange_url(self._item, self._nexus_base_url, et)
        self._acquisition_section.set_content(build_acquisition_content(
            data, exchange_link=url, on_navigate=self.entity_navigate.emit))

    def _on_usage_loaded(self, data: dict):
        if not hasattr(self, "_usage_section"):
            return
        et = PAGE_TYPE_TO_ENTITY.get(self._page_type_id, "")
        url = exchange_url(self._item, self._nexus_base_url, et)
        self._usage_section.set_content(build_usage_content(
            data, exchange_link=url, on_navigate=self.entity_navigate.emit))
