"""Tool entity detail page — covers finders, excavators, scanners, refiners,
teleportation chips, effect chips, and misc tools."""

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
    _excavator_eff_per_ped,
)


def _fv(value, decimals: int) -> str:
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"


# Map page_type_id → (display name, image path segment)
_TOOL_TYPE_INFO: dict[str, tuple[str, str]] = {
    "finders":            ("Finder",             "finder"),
    "excavators":         ("Excavator",          "excavator"),
    "scanners":           ("Scanner",            "scanner"),
    "refiners":           ("Refiner",            "refiner"),
    "teleportationchips": ("Teleportation Chip", "teleportationchip"),
    "misctools":          ("Misc. Tool",         "misctool"),
}


class ToolDetailView(WikiDetailView):
    """Detail view for tool entities (all subtypes)."""

    _acquisition_loaded = pyqtSignal(dict)
    _usage_loaded = pyqtSignal(dict)

    def __init__(self, item: dict, *, page_type_id: str = "finders",
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
        display_name, image_type = _TOOL_TYPE_INFO.get(
            self._page_type_id, ("Tool", "tool")
        )

        # --- Image ---
        self._add_image_placeholder(name)
        item_id = item.get("Id")
        if item_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/{image_type}/{item_id}"
            )

        # --- Badge + title ---
        subtitle_widgets = [self._make_badge(display_name)]
        self._add_infobox_title(name, subtitle_widgets)

        # --- Tier1 (varies by subtype) ---
        tier1 = InfoboxSection(tier1=True)
        depth = deep_get(item, "Properties", "Depth")
        range_val = deep_get(item, "Properties", "Range")
        efficiency = deep_get(item, "Properties", "Efficiency")
        upm = deep_get(item, "Properties", "UsesPerMinute")
        max_tt = deep_get(item, "Properties", "Economy", "MaxTT")

        if self._page_type_id == "finders":
            tier1.add_row(Tier1StatRow("Depth", f"{fmt_int(depth)}m"))
            tier1.add_row(Tier1StatRow("Range", f"{fmt_int(range_val)}m"))
        elif self._page_type_id == "excavators":
            tier1.add_row(Tier1StatRow("Efficiency", fmt_int(efficiency)))
            eff_per_ped = _excavator_eff_per_ped(item)
            tier1.add_row(Tier1StatRow("Eff/PED", _fv(eff_per_ped, 1)))
        else:
            tier1.add_row(Tier1StatRow("UPM", fmt_int(upm)))
            tier1.add_row(Tier1StatRow(
                "Max TT", f"{_fv(max_tt, 2)} PED" if max_tt is not None else "-"
            ))
        self._add_section(tier1)

        # --- Performance (conditional fields) ---
        has_perf_data = any(v is not None for v in [upm, depth, range_val, efficiency])
        if has_perf_data:
            perf = InfoboxSection("Performance")
            perf.add_row(StatRow("Uses/Min", fmt_int(upm)))
            if depth is not None:
                perf.add_row(StatRow("Depth", f"{fmt_int(depth)}m"))
            if range_val is not None:
                perf.add_row(StatRow("Range", f"{fmt_int(range_val)}m"))
            if efficiency is not None:
                perf.add_row(StatRow("Efficiency", fmt_int(efficiency)))
                eff_per_ped = _excavator_eff_per_ped(item)
                if eff_per_ped is not None:
                    perf.add_row(StatRow("Eff/PED", _fv(eff_per_ped, 1)))
            self._add_section(perf)

        # --- Economy ---
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
        if ammo_burn is not None and ammo_burn > 0:
            econ.add_row(StatRow("Ammo Burn", fmt_int(ammo_burn)))
        if cost is not None:
            econ.add_row(StatRow("Cost/Use", f"{_fv(cost, 4)} PEC"))
        econ.add_row(StatRow("Uses", fmt_int(uses)))
        self._add_section(econ)

        # --- Skill (if applicable) ---
        is_sib = deep_get(item, "Properties", "Skill", "IsSiB")
        profession = deep_get(item, "Profession", "Name")
        skill_start = deep_get(item, "Properties", "Skill", "LearningIntervalStart")
        if skill_start is None:
            skill_start = deep_get(item, "Properties", "Skill", "Hit", "LearningIntervalStart")
        skill_end = deep_get(item, "Properties", "Skill", "LearningIntervalEnd")
        if skill_end is None:
            skill_end = deep_get(item, "Properties", "Skill", "Hit", "LearningIntervalEnd")

        if is_sib is not None or profession:
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

        # --- Mindforce (teleportation/effect chips) ---
        mf = deep_get(item, "Properties", "Mindforce")
        if mf:
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
        props_section = InfoboxSection("Properties")
        props_section.add_row(StatRow(
            "Weight", f"{fmt_int(weight)} kg" if weight is not None else "-"
        ))
        self._add_section(props_section)

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
                _et = {
                    "finders": "Finder",
                    "excavators": "Excavator",
                }.get(self._page_type_id, "Weapon")
                tiers_section.set_content(_TiersWidget(
                    tiers_data, entity_type=_et,
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
                target=fetch_data, daemon=True, name="tool-data-fetch"
            ).start()

    def _on_acquisition_loaded(self, data: dict):
        if not hasattr(self, "_acquisition_section"):
            return
        et = PAGE_TYPE_TO_ENTITY.get(self._page_type_id, "")
        url = exchange_url(self._item, self._nexus_base_url, et)
        self._acquisition_section.set_content(build_acquisition_content(data, exchange_link=url))

    def _on_usage_loaded(self, data: dict):
        if not hasattr(self, "_usage_section"):
            return
        et = PAGE_TYPE_TO_ENTITY.get(self._page_type_id, "")
        url = exchange_url(self._item, self._nexus_base_url, et)
        self._usage_section.set_content(build_usage_content(data, exchange_link=url))
