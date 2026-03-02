"""Pet entity detail page — rarity, training, effects with unlock costs."""

from __future__ import annotations

import threading

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    build_acquisition_content, build_usage_content, exchange_url,
)
from ..theme import TEXT_MUTED
from ...data.wiki_columns import deep_get, get_item_name, fmt_int


def _fv(value, decimals: int) -> str:
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"


def _fmt_nutrio(v):
    if v is None:
        return "-"
    return f"{v / 100:.2f} PED"


def _fmt_exportable(v):
    if v is not None and v > 0:
        return f"Lvl {v}"
    return "No"


class PetDetailView(WikiDetailView):
    """Detail view for a single pet entity."""

    _acquisition_loaded = pyqtSignal(dict)
    _usage_loaded = pyqtSignal(dict)

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, parent=None):
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._acquisition_loaded.connect(self._on_acquisition_loaded)
        self._usage_loaded.connect(self._on_usage_loaded)
        self._build(item)

    def _build(self, item: dict):
        name = get_item_name(item)
        rarity = deep_get(item, "Properties", "Rarity") or "-"

        # --- Image ---
        self._add_image_placeholder(name)
        item_id = item.get("Id")
        if item_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/pet/{item_id}"
            )

        # --- Badge + title ---
        subtitle_widgets = [self._make_badge(rarity)]
        self._add_infobox_title(name, subtitle_widgets)

        # --- Tier1: Rarity, Training ---
        training = deep_get(item, "Properties", "TrainingDifficulty") or "-"
        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow("Rarity", rarity))
        tier1.add_row(Tier1StatRow("Training", training))
        self._add_section(tier1)

        # --- Properties ---
        taming_level = deep_get(item, "Properties", "TamingLevel")
        exportable = deep_get(item, "Properties", "ExportableLevel")
        nutrio_cap = deep_get(item, "Properties", "NutrioCapacity")
        nutrio_rate = deep_get(item, "Properties", "NutrioConsumptionPerHour")
        planet = deep_get(item, "Planet", "Name")

        props = InfoboxSection("Properties")
        props.add_row(StatRow("Taming Level", fmt_int(taming_level)))
        props.add_row(StatRow("Exportable", _fmt_exportable(exportable)))
        props.add_row(StatRow("Nutrio Cap.", _fmt_nutrio(nutrio_cap)))
        if nutrio_rate is not None:
            props.add_row(StatRow("Nutrio/Hour", _fmt_nutrio(nutrio_rate)))
        if planet:
            props.add_row(StatRow("Planet", planet))
        self._add_section(props)

        # --- Effects ---
        effects = item.get("Effects") or []
        if effects:
            eff_section = InfoboxSection("Effects")
            for eff in effects:
                eff_name = eff.get("Name", "Unknown")
                strength = deep_get(eff, "Properties", "Strength")
                val_str = f"{strength}" if strength is not None else ""
                eff_section.add_row(StatRow(eff_name, val_str))

                # Unlock details
                unlock = deep_get(eff, "Properties", "Unlock")
                if unlock:
                    unlock_level = unlock.get("Level")
                    unlock_cost = unlock.get("CostPED")
                    unlock_essences = unlock.get("CostEssences")
                    if unlock_level is not None:
                        eff_section.add_row(StatRow(
                            "Unlock Level", fmt_int(unlock_level), indent=True
                        ))
                    if unlock_cost is not None:
                        eff_section.add_row(StatRow(
                            "Unlock Cost", f"{_fv(unlock_cost, 2)} PED", indent=True
                        ))
                    if unlock_essences is not None:
                        eff_section.add_row(StatRow(
                            "Essences", fmt_int(unlock_essences), indent=True
                        ))

                # Nutrio cost per effect
                eff_nutrio = deep_get(eff, "Properties", "NutrioConsumptionPerHour")
                if eff_nutrio is not None:
                    eff_section.add_row(StatRow(
                        "Nutrio/Hour", _fmt_nutrio(eff_nutrio), indent=True
                    ))

            self._add_section(eff_section)

        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

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
                target=fetch_data, daemon=True, name="pet-data-fetch"
            ).start()

    def _on_acquisition_loaded(self, data: dict):
        if not hasattr(self, "_acquisition_section"):
            return
        url = exchange_url(self._item, self._nexus_base_url, "Pet")
        self._acquisition_section.set_content(build_acquisition_content(data, exchange_link=url))

    def _on_usage_loaded(self, data: dict):
        if not hasattr(self, "_usage_section"):
            return
        url = exchange_url(self._item, self._nexus_base_url, "Pet")
        self._usage_section.set_content(build_usage_content(data, exchange_link=url))
