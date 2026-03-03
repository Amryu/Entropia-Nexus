"""Pet entity detail page — rarity, training, effects with unlock costs."""

from __future__ import annotations

import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    build_acquisition_content, build_usage_content, exchange_url,
)
from ..theme import PRIMARY, BORDER, TEXT, TEXT_MUTED, ACCENT

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

        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Pet Skills panel (collapsible, below infobox) ---
        effects = item.get("Effects") or []
        if effects:
            skills_section = DataSection("Pet Skills", expanded=True)
            skills_section.set_content(self._build_skills_widget(effects))
            self._add_article_section(skills_section)

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

    def _build_skills_widget(self, effects: list) -> QWidget:
        """Build pet skills as a responsive card grid."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)

        sorted_effects = sorted(
            effects,
            key=lambda e: deep_get(e, "Properties", "Unlock", "Level") or 0,
        )

        # 2-column grid (minimum 2 cards per row)
        cols = 2
        for i, eff in enumerate(sorted_effects):
            card = self._build_skill_card(eff)
            grid.addWidget(card, i // cols, i % cols)

        # Make columns stretch equally
        for c in range(cols):
            grid.setColumnStretch(c, 1)

        return container

    def _build_skill_card(self, eff: dict) -> QWidget:
        """Build a single compact skill card."""
        from PyQt6.QtWidgets import QHBoxLayout

        eff_name = eff.get("Name", "Unknown")
        strength = deep_get(eff, "Properties", "Strength")
        unit = deep_get(eff, "Properties", "Unit") or ""
        val_str = f"{strength}{unit}" if strength is not None else "-"
        unlock = deep_get(eff, "Properties", "Unlock") or {}
        unlock_level = unlock.get("Level")

        card = QWidget()
        card.setStyleSheet(
            f"QWidget#skillCard {{"
            f"  background-color: {PRIMARY};"
            f"  border: 1px solid {BORDER};"
            f"  border-radius: 6px;"
            f"}}"
        )
        card.setObjectName("skillCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        # Top row: Skill name + Level badge
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        title = QLabel(eff_name)
        title.setWordWrap(True)
        title.setStyleSheet(
            f"color: {ACCENT}; font-size: 13px; font-weight: 600;"
            " background: transparent;"
        )
        top_row.addWidget(title, 1)
        if unlock_level is not None:
            level_lbl = QLabel(f"Lvl {unlock_level}")
            level_lbl.setStyleSheet(
                f"color: {TEXT}; font-size: 13px; font-weight: 700;"
                " background: transparent;"
            )
            top_row.addWidget(level_lbl, 0)
        layout.addLayout(top_row)

        # Strength value (prominent)
        strength_lbl = QLabel(val_str)
        strength_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 15px; font-weight: 700;"
            " background: transparent; margin: 2px 0;"
        )
        layout.addWidget(strength_lbl)

        # Secondary details (each on its own line)
        _muted_style = (
            f"color: {TEXT_MUTED}; font-size: 11px;"
            " background: transparent;"
        )

        eff_nutrio = deep_get(eff, "Properties", "NutrioConsumptionPerHour")
        if eff_nutrio is not None:
            upkeep_lbl = QLabel(f"Upkeep {eff_nutrio}/h")
            upkeep_lbl.setStyleSheet(_muted_style)
            layout.addWidget(upkeep_lbl)

        cost_parts = []
        cost_ped = unlock.get("CostPED")
        if cost_ped and cost_ped > 0:
            cost_parts.append(f"{_fv(cost_ped, 2)} PED")
        cost_essence = unlock.get("CostEssence")
        if cost_essence and cost_essence > 0:
            cost_parts.append(f"{fmt_int(cost_essence)} Animal Essence")
        cost_rare = unlock.get("CostRareEssence")
        if cost_rare and cost_rare > 0:
            cost_parts.append(f"{fmt_int(cost_rare)} Rare Animal Essence")
        if cost_parts:
            cost_lbl = QLabel("Cost: " + ", ".join(cost_parts))
            cost_lbl.setWordWrap(True)
            cost_lbl.setStyleSheet(_muted_style)
            layout.addWidget(cost_lbl)

        criteria = unlock.get("Criteria")
        if criteria:
            criteria_val = unlock.get("CriteriaValue")
            crit_str = (
                f"{criteria} ({fmt_int(criteria_val)})"
                if criteria_val is not None else criteria
            )
            crit_lbl = QLabel(crit_str)
            crit_lbl.setWordWrap(True)
            crit_lbl.setStyleSheet(_muted_style)
            layout.addWidget(crit_lbl)

        return card

    def _on_acquisition_loaded(self, data: dict):
        if not hasattr(self, "_acquisition_section"):
            return
        url = exchange_url(self._item, self._nexus_base_url, "Pet")
        self._acquisition_section.set_content(build_acquisition_content(
            data, exchange_link=url, on_navigate=self.entity_navigate.emit))

    def _on_usage_loaded(self, data: dict):
        if not hasattr(self, "_usage_section"):
            return
        url = exchange_url(self._item, self._nexus_base_url, "Pet")
        self._usage_section.set_content(build_usage_content(
            data, exchange_link=url, on_navigate=self.entity_navigate.emit))
