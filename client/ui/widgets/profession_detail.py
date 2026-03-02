"""Profession entity detail page — skills, weights, unlocks."""

from __future__ import annotations

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    no_data_label, make_section_table,
)
from .fancy_table import ColumnDef
from ...data.wiki_columns import deep_get, get_item_name, fmt_int


class ProfessionDetailView(WikiDetailView):
    """Detail view for a single profession entity."""

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
                f"{self._nexus_base_url}/api/img/profession/{item_id}"
            )

        # --- Badge + title ---
        subtitle_widgets = []
        if category:
            subtitle_widgets.append(self._make_badge(category))
        self._add_infobox_title(name, subtitle_widgets if subtitle_widgets else None)

        # --- Tier1: Skills count, Total Weight ---
        skills = item.get("Skills") or []
        unlocks = item.get("Unlocks") or []
        total_weight = sum(
            (s.get("Weight") or 0) for s in skills
        )

        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow("Skills", str(len(skills))))
        tier1.add_row(Tier1StatRow("Total Weight", fmt_int(total_weight)))
        if unlocks:
            tier1.add_row(Tier1StatRow("Unlocks", str(len(unlocks))))
        self._add_section(tier1)

        # --- General ---
        general = InfoboxSection("General")
        general.add_row(StatRow("Category", category or "-"))
        hidden_count = sum(
            1 for s in skills
            if deep_get(s, "Skill", "Properties", "IsHidden")
        )
        if hidden_count:
            general.add_row(StatRow("Hidden Skills", str(hidden_count)))
        self._add_section(general)

        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Skills table ---
        skills_section = DataSection("Skill Components", expanded=True)
        if skills:
            skills_section.set_subtitle(f"{len(skills)} skills")
            flat = []
            for s in skills:
                weight = s.get("Weight") or 0
                flat.append({
                    "skill": deep_get(s, "Skill", "Name") or s.get("Name") or "",
                    "weight": weight,
                    "pct": weight / total_weight * 100 if total_weight > 0 else 0,
                })
            skills_section.set_content(make_section_table(
                [
                    ColumnDef("skill", "Skill", main=True),
                    ColumnDef("weight", "Weight", format=lambda v: fmt_int(v)),
                    ColumnDef("pct", "%", format=lambda v: f"{v:.1f}%" if v else ""),
                ],
                flat,
                default_sort=("weight", "DESC"),
            ))
        else:
            skills_section.set_content(no_data_label("No skill data available."))
            skills_section.set_subtitle("No data")
        self._add_article_section(skills_section)

        # --- Unlocks table ---
        if unlocks:
            unlock_section = DataSection("Skill Unlocks", expanded=True)
            unlock_section.set_subtitle(f"{len(unlocks)} unlocks")
            flat = []
            for u in unlocks:
                flat.append({
                    "skill": deep_get(u, "Skill", "Name") or u.get("Name") or "",
                    "level": u.get("Level"),
                })
            unlock_section.set_content(make_section_table(
                [
                    ColumnDef("skill", "Skill", main=True),
                    ColumnDef("level", "Required Level", format=lambda v: fmt_int(v)),
                ],
                flat,
                default_sort=("level", "ASC"),
            ))
            self._add_article_section(unlock_section)
