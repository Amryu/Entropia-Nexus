"""Config-driven detail view for simple wiki entity types.

Covers: clothing, materials, enhancers, stimulants, capsules, furniture,
decorations, storage containers, signs, strongboxes, sights/scopes,
absorbers, finder amplifiers, armor platings, mindforce implants, and
any other "items"-type entities.
"""

from __future__ import annotations

import threading

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    DefenseBreakdownWidget, no_data_label, build_acquisition_content,
    build_usage_content, exchange_url, PAGE_TYPE_TO_ENTITY,
)
from ..theme import TEXT_MUTED
from ...data.wiki_columns import (
    deep_get, get_item_name, fmt_int, fmt_bool, _get_min_level,
    armor_total_defense, _armor_total_absorption, weapon_total_uses,
)


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

def _fv(value, decimals: int) -> str:
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"


def _fmt_nutrio(v):
    if v is None:
        return "-"
    return f"{v / 100:.2f} PED"


def _fmt_pct(v):
    """Format as percentage (value is 0-1 fraction)."""
    if v is None:
        return "-"
    return f"{v * 100:.0f}%"


def _fmt_zoom(v):
    if v is None:
        return "-"
    return f"{v:.1f}x"


def _fmt_skill_pct(v):
    if v is None:
        return "-"
    return f"{v}%"


# ---------------------------------------------------------------------------
# Image type mapping — page_type_id → API image path segment
# ---------------------------------------------------------------------------

_IMAGE_TYPE_MAP: dict[str, str | None] = {
    "items": None,
    "clothing": "clothing",
    "materials": "material",
    "enhancers": "enhancer",
    "stimulants": "stimulant",
    "capsules": "capsule",
    "furniture": "furniture",
    "storagecontainers": "storagecontainer",
    "signs": "sign",
    "sightsscopes": "scope",
    "absorbers": "absorber",
    "finderamplifiers": "finderamplifier",
    "armorplatings": "armorplating",
    "mindforceimplants": "implant",
}


# ---------------------------------------------------------------------------
# Per-type configuration
# ---------------------------------------------------------------------------
# Each config defines:
#   badge_getter: callable(item) → str for the badge label
#   tier1: list of (label, callable(item) → str) for the blue gradient section
#   sections: list of (title, rows) where rows is list of (label, callable(item) → str)
#   effects_keys: list of item keys to check for effects arrays
#   show_set_info: whether to show clothing set info
#   show_acquisition: whether to show acquisition panel

def _type_config_items() -> dict:
    return {
        "badge_getter": lambda i: deep_get(i, "Properties", "Type") or "",
        "tier1": [
            ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
        ],
        "sections": [
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
                ("Decay", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Decay'), 2)} PEC"),
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
            ]),
        ],
        "effects_keys": ["EffectsOnEquip", "EffectsOnUse"],
        "show_set_info": False,
        "show_acquisition": True,
    }


def _type_config_clothing() -> dict:
    return {
        "badge_getter": lambda i: deep_get(i, "Properties", "Slot") or "",
        "tier1": [
            ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
        ],
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
        "show_set_info": True,
        "show_acquisition": True,
    }


def _type_config_materials() -> dict:
    return {
        "badge_getter": lambda i: deep_get(i, "Properties", "Type") or "",
        "tier1": [
            ("Value", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
        ],
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
        "show_set_info": False,
        "show_acquisition": True,
    }


def _type_config_enhancers() -> dict:
    return {
        "badge_getter": lambda i: deep_get(i, "Properties", "Type") or "",
        "tier1": [],
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
        "show_set_info": False,
        "show_acquisition": True,
    }


def _type_config_stimulants() -> dict:
    return {
        "badge_getter": lambda i: deep_get(i, "Properties", "Type") or "",
        "tier1": [
            ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
        ],
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
        "show_set_info": False,
        "show_acquisition": True,
    }


def _type_config_capsules() -> dict:
    return {
        "badge_getter": lambda i: "",
        "tier1": [
            ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
        ],
        "sections": [
            ("Properties", [
                ("Mob", lambda i: deep_get(i, "Mob", "Name") or "-"),
                ("Mob Type", lambda i: deep_get(i, "Mob", "Type") or "-"),
                ("Profession", lambda i: deep_get(i, "Profession", "Name") or "-"),
                ("Min Level", lambda i: fmt_int(_get_min_level(i))),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
            ]),
        ],
        "effects_keys": [],
        "show_set_info": False,
        "show_acquisition": True,
    }


def _type_config_furniture() -> dict:
    return {
        "badge_getter": lambda i: deep_get(i, "Properties", "Type") or "",
        "tier1": [
            ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
        ],
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
        "show_set_info": False,
        "show_acquisition": True,
    }


def _type_config_storagecontainers() -> dict:
    return {
        "badge_getter": lambda i: "",
        "tier1": [
            ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
        ],
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
        "show_set_info": False,
        "show_acquisition": True,
    }


def _type_config_signs() -> dict:
    return {
        "badge_getter": lambda i: "",
        "tier1": [
            ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
        ],
        "sections": [
            ("Display", [
                ("Aspect Ratio", lambda i: deep_get(i, "Properties", "Display", "AspectRatio") or "-"),
                ("Item Points", lambda i: fmt_int(deep_get(i, "Properties", "ItemPoints"))),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
                ("Cost", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Cost'), 2)} PED"),
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
            ]),
        ],
        "effects_keys": [],
        "show_set_info": False,
        "show_acquisition": True,
    }


def _type_config_sightsscopes() -> dict:
    return {
        "badge_getter": lambda i: deep_get(i, "Properties", "Type") or "",
        "tier1": [
            ("Efficiency", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Efficiency'), 1)}%"),
            ("Zoom", lambda i: _fmt_zoom(deep_get(i, "Properties", "Zoom"))),
        ],
        "sections": [
            ("General", [
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
                ("Decay", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Decay'), 2)} PEC"),
                ("Total Uses", lambda i: fmt_int(weapon_total_uses(i))),
            ]),
            ("Skill", [
                ("Skill Mod", lambda i: _fmt_skill_pct(deep_get(i, "Properties", "SkillModification"))),
                ("Skill Bonus", lambda i: _fmt_skill_pct(deep_get(i, "Properties", "SkillBonus"))),
            ]),
        ],
        "effects_keys": ["EffectsOnEquip"],
        "show_set_info": False,
        "show_acquisition": True,
    }


def _type_config_absorbers() -> dict:
    return {
        "badge_getter": lambda i: "",
        "tier1": [
            ("Efficiency", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Efficiency'), 1)}%"),
            ("Absorption", lambda i: _fmt_pct(deep_get(i, "Properties", "Economy", "Absorption"))),
        ],
        "sections": [
            ("General", [
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
                ("Absorption", lambda i: _fmt_pct(deep_get(i, "Properties", "Economy", "Absorption"))),
            ]),
            ("Economy", [
                ("Efficiency", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Efficiency'), 1)}%"),
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
            ]),
        ],
        "effects_keys": ["EffectsOnEquip"],
        "show_set_info": False,
        "show_acquisition": True,
    }


def _type_config_finderamplifiers() -> dict:
    return {
        "badge_getter": lambda i: "",
        "tier1": [
            ("Efficiency", lambda i: _fv(deep_get(i, "Properties", "Efficiency"), 1)),
            ("Decay", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'Decay'), 4)} PEC"),
        ],
        "sections": [
            ("General", [
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
                ("Total Uses", lambda i: fmt_int(weapon_total_uses(i))),
            ]),
            ("Skill", [
                ("Min. Prof. Level", lambda i: fmt_int(deep_get(i, "Properties", "MinProfessionLevel"))),
            ]),
        ],
        "effects_keys": ["EffectsOnEquip"],
        "show_set_info": False,
        "show_acquisition": True,
    }


def _type_config_armorplatings() -> dict:
    return {
        "badge_getter": lambda i: "",
        "tier1": [
            ("Total Defense", lambda i: _fv(armor_total_defense(i), 1)),
            ("Durability", lambda i: fmt_int(deep_get(i, "Properties", "Economy", "Durability"))),
        ],
        "sections": [
            ("General", [
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
                ("Durability", lambda i: fmt_int(deep_get(i, "Properties", "Economy", "Durability"))),
                ("Total Absorption", lambda i: f"{_fv(_armor_total_absorption(i), 1)} HP"),
            ]),
        ],
        "effects_keys": ["EffectsOnEquip"],
        "show_set_info": False,
        "show_acquisition": True,
        "defense_grid": True,
    }


def _type_config_mindforceimplants() -> dict:
    return {
        "badge_getter": lambda i: "",
        "tier1": [
            ("TT Value", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
            ("Absorption", lambda i: _fmt_pct(deep_get(i, "Properties", "Economy", "Absorption"))),
        ],
        "sections": [
            ("General", [
                ("Weight", lambda i: f"{fmt_int(deep_get(i, 'Properties', 'Weight'))} kg"),
                ("Max Prof. Level", lambda i: fmt_int(deep_get(i, "Properties", "MaxProfessionLevel"))),
            ]),
            ("Economy", [
                ("Max TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MaxTT'), 2)} PED"),
                ("Min TT", lambda i: f"{_fv(deep_get(i, 'Properties', 'Economy', 'MinTT'), 2)} PED"),
                ("Absorption", lambda i: _fmt_pct(deep_get(i, "Properties", "Economy", "Absorption"))),
            ]),
        ],
        "effects_keys": ["EffectsOnEquip"],
        "show_set_info": False,
        "show_acquisition": True,
    }


_TYPE_CONFIGS: dict[str, callable] = {
    "items": _type_config_items,
    "clothing": _type_config_clothing,
    "materials": _type_config_materials,
    "enhancers": _type_config_enhancers,
    "stimulants": _type_config_stimulants,
    "capsules": _type_config_capsules,
    "furniture": _type_config_furniture,
    "storagecontainers": _type_config_storagecontainers,
    "signs": _type_config_signs,
    "sightsscopes": _type_config_sightsscopes,
    "absorbers": _type_config_absorbers,
    "finderamplifiers": _type_config_finderamplifiers,
    "armorplatings": _type_config_armorplatings,
    "mindforceimplants": _type_config_mindforceimplants,
}


# ---------------------------------------------------------------------------
# GenericItemDetailView
# ---------------------------------------------------------------------------

class GenericItemDetailView(WikiDetailView):
    """Config-driven detail view for simple entity types."""

    _acquisition_loaded = pyqtSignal(dict)
    _usage_loaded = pyqtSignal(dict)

    def __init__(self, item: dict, *, page_type_id: str = "items",
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

        # Get config for this type (fall back to generic items)
        config_fn = _TYPE_CONFIGS.get(self._page_type_id, _type_config_items)
        config = config_fn()

        # --- Image ---
        self._add_image_placeholder(name)

        item_id = item.get("Id")
        image_type = _IMAGE_TYPE_MAP.get(self._page_type_id)
        if item_id and self._nexus_base_url and image_type:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/{image_type}/{item_id}"
            )

        # --- Badge + title ---
        subtitle_widgets = []
        badge_text = config["badge_getter"](item)
        if badge_text:
            subtitle_widgets.append(self._make_badge(badge_text))
        self._add_infobox_title(name, subtitle_widgets if subtitle_widgets else None)

        # --- Tier1 section ---
        if config["tier1"]:
            tier1 = InfoboxSection(tier1=True)
            for label, getter in config["tier1"]:
                tier1.add_row(Tier1StatRow(label, getter(item)))
            self._add_section(tier1)

        # --- Stat sections ---
        for section_title, rows in config["sections"]:
            section = InfoboxSection(section_title)
            for label, getter in rows:
                val = getter(item)
                section.add_row(StatRow(label, val if val else "-"))
            self._add_section(section)

        # --- Defense grid (armor platings) ---
        if config.get("defense_grid"):
            defense = deep_get(item, "Properties", "Defense")
            if defense:
                def_section = InfoboxSection("Defense")
                def_section.add_widget(DefenseBreakdownWidget(defense))
                self._add_section(def_section)

        # --- Effects section ---
        all_effects = []
        for key in config["effects_keys"]:
            effects = item.get(key)
            if effects:
                all_effects.append((key, effects))

        if all_effects:
            eff_section = InfoboxSection("Effects")
            for key, effects in all_effects:
                # Sub-label for different effect types
                if len(all_effects) > 1:
                    label_map = {
                        "EffectsOnEquip": "On Equip",
                        "EffectsOnUse": "On Use",
                        "EffectsOnConsume": "On Consume",
                        "Effects": "Effects",
                    }
                    sub_lbl = QLabel(label_map.get(key, key))
                    sub_lbl.setStyleSheet(
                        f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600;"
                        " background: transparent; margin-top: 4px;"
                    )
                    eff_section.add_widget(sub_lbl)
                for e in effects:
                    eff_name = e.get("Name", "Unknown")
                    eff_str = e.get("Strength")
                    val_str = f"{eff_str}" if eff_str else ""
                    eff_section.add_row(StatRow(eff_name, val_str, indent=True))
            self._add_section(eff_section)

        # --- Set info (clothing only) ---
        if config["show_set_info"]:
            set_data = item.get("Set")
            if set_data:
                set_section = InfoboxSection("Set")
                set_name = set_data.get("Name")
                if set_name:
                    set_section.add_row(StatRow("Set", set_name))
                set_effects = set_data.get("EffectsOnSetEquip") or []
                for eff in set_effects:
                    pieces = eff.get("MinSetPieces", "?")
                    eff_name = eff.get("Name", "Unknown")
                    set_section.add_row(StatRow(
                        f"{pieces}-piece", eff_name, indent=True
                    ))
                self._add_section(set_section)

        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Market Prices panel ---
        self._setup_market_prices_section()

        # --- Acquisition panel ---
        if config["show_acquisition"]:
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
                    target=fetch_data, daemon=True, name="generic-data-fetch"
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
