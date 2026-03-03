"""Skill entity detail page — category, HP increase, professions, unlocks."""

from __future__ import annotations

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    no_data_label, make_section_table,
)
from .fancy_table import ColumnDef
from ...data.wiki_columns import deep_get, get_item_name, fmt_int


class SkillDetailView(WikiDetailView):
    """Detail view for a single skill entity."""

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, parent=None):
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._build(item)

    def _build(self, item: dict):
        name = get_item_name(item)
        category = deep_get(item, "Category", "Name") or ""

        # --- Image ---
        self._add_image_placeholder(name)
        item_id = item.get("Id")
        if item_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/skill/{item_id}"
            )

        # --- Badge + title ---
        subtitle_widgets = []
        if category:
            subtitle_widgets.append(self._make_badge(category))
        self._add_infobox_title(name, subtitle_widgets if subtitle_widgets else None)

        # --- Tier1: Points/HP, Professions count ---
        hp_increase = deep_get(item, "Properties", "HpIncrease") or 0
        professions = item.get("Professions") or []

        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow(
            "Points/HP", str(hp_increase) if hp_increase > 0 else "N/A"
        ))
        tier1.add_row(Tier1StatRow("Professions", str(len(professions))))
        self._add_section(tier1)

        # --- Properties ---
        is_hidden = deep_get(item, "Properties", "IsHidden")
        is_extractable = deep_get(item, "Properties", "IsExtractable")
        unlocks = item.get("Unlocks") or []

        props = InfoboxSection("Properties")
        props.add_row(StatRow("Category", category or "-"))
        props.add_row(StatRow(
            "Visibility", "Hidden" if is_hidden else "Visible",
        ))
        props.add_row(StatRow(
            "Extractable", "Yes" if is_extractable else "No",
            highlight=bool(is_extractable),
        ))
        if unlocks:
            props.add_row(StatRow("Unlock Required", "Yes"))
        self._add_section(props)

        # --- Health Points (conditional) ---
        if hp_increase > 0:
            hp_section = InfoboxSection("Health Points")
            hp_section.add_row(StatRow("Points per HP", str(hp_increase)))
            self._add_section(hp_section)

        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Professions table ---
        prof_section = DataSection("Affected Professions", expanded=True)
        if professions:
            prof_section.set_subtitle(f"{len(professions)} professions")
            flat = []
            for p in professions:
                flat.append({
                    "profession": deep_get(p, "Profession", "Name") or p.get("Name") or "",
                    "weight": p.get("Weight"),
                })
            table = make_section_table(
                [
                    ColumnDef("profession", "Profession", main=True),
                    ColumnDef("weight", "Weight", format=lambda v: fmt_int(v)),
                ],
                flat,
                default_sort=("weight", "DESC"),
            )
            table.row_activated.connect(
                lambda row, _idx: self.entity_navigate.emit(
                    {"Name": row.get("profession", ""), "Type": "Profession"}
                )
            )
            prof_section.set_content(table)
        else:
            prof_section.set_content(no_data_label("No profession data available."))
            prof_section.set_subtitle("No data")
        self._add_article_section(prof_section)

        # --- Unlocks table ---
        if unlocks:
            unlock_section = DataSection("Unlocked By", expanded=True)
            unlock_section.set_subtitle(f"{len(unlocks)} unlocks")
            flat = []
            for u in unlocks:
                flat.append({
                    "profession": deep_get(u, "Profession", "Name") or u.get("Name") or "",
                    "level": u.get("Level"),
                })
            table = make_section_table(
                [
                    ColumnDef("profession", "Profession", main=True),
                    ColumnDef("level", "Level", format=lambda v: fmt_int(v)),
                ],
                flat,
                default_sort=("level", "ASC"),
            )
            table.row_activated.connect(
                lambda row, _idx: self.entity_navigate.emit(
                    {"Name": row.get("profession", ""), "Type": "Profession"}
                )
            )
            unlock_section.set_content(table)
            self._add_article_section(unlock_section)
