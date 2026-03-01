"""Mission entity detail page — type, planet, steps, rewards."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    no_data_label, make_compact_table,
)
from ..theme import TEXT_MUTED
from ...data.wiki_columns import deep_get, get_item_name, fmt_int


class MissionDetailView(WikiDetailView):
    """Detail view for a single mission entity."""

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, parent=None):
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._build(item)

    def _build(self, item: dict):
        name = get_item_name(item)
        mission_type = deep_get(item, "Properties", "Type") or ""
        planet = deep_get(item, "Planet", "Name") or ""

        # --- Image ---
        self._add_image_placeholder(name)
        item_id = item.get("Id")
        if item_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/mission/{item_id}"
            )

        # --- Badge + title ---
        subtitle_widgets = []
        if mission_type:
            subtitle_widgets.append(self._make_badge(mission_type))
        if planet:
            subtitle_widgets.append(self._make_subtitle_text(planet))
        self._add_infobox_title(name, subtitle_widgets if subtitle_widgets else None)

        # --- Tier1: Type, Planet ---
        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow("Type", mission_type or "N/A"))
        tier1.add_row(Tier1StatRow("Planet", planet or "N/A"))
        self._add_section(tier1)

        # --- General ---
        chain = deep_get(item, "MissionChain", "Name")
        cooldown = deep_get(item, "Properties", "CooldownDuration")
        event = deep_get(item, "Event", "Name")

        general = InfoboxSection("General")
        if chain:
            general.add_row(StatRow("Mission Chain", chain))
        if event:
            general.add_row(StatRow("Event", event))
        if cooldown:
            general.add_row(StatRow("Cooldown", str(cooldown)))
        self._add_section(general)

        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Steps section ---
        steps = item.get("Steps") or []
        steps_section = DataSection("Steps", expanded=True)
        if steps:
            steps_section.set_subtitle(f"{len(steps)} steps")
            headers = ["#", "Objective", "Target", "Amount"]
            rows = []
            for i, step in enumerate(steps, 1):
                objective = step.get("Objective") or step.get("Type") or "-"
                target = deep_get(step, "Target", "Name") or step.get("Target") or "-"
                amount = step.get("Amount")
                rows.append([
                    str(i),
                    str(objective),
                    str(target),
                    fmt_int(amount) if amount else "-",
                ])
            steps_section.set_content(make_compact_table(headers, rows))
        else:
            steps_section.set_content(no_data_label("No step information available."))
            steps_section.set_subtitle("No data")
        self._add_article_section(steps_section)

        # --- Rewards section ---
        rewards = item.get("Rewards") or {}
        reward_items = rewards.get("Items") or []
        reward_skills = rewards.get("Skills") or []
        reward_unlocks = rewards.get("Unlocks") or []
        has_rewards = reward_items or reward_skills or reward_unlocks

        rewards_section = DataSection("Rewards", expanded=True)
        if has_rewards:
            reward_rows = []
            for r in reward_items:
                r_name = deep_get(r, "Item", "Name") or r.get("Name") or "Unknown"
                qty = r.get("Amount") or r.get("Quantity")
                reward_rows.append([r_name, fmt_int(qty) if qty else "-", "Item"])
            for r in reward_skills:
                r_name = deep_get(r, "Skill", "Name") or r.get("Name") or "Unknown"
                amount = r.get("Amount")
                reward_rows.append([r_name, fmt_int(amount) if amount else "-", "Skill"])
            for r in reward_unlocks:
                r_name = r.get("Name") or "Unknown"
                reward_rows.append([r_name, "-", "Unlock"])

            rewards_section.set_subtitle(f"{len(reward_rows)} rewards")
            headers = ["Reward", "Amount", "Type"]
            rewards_section.set_content(make_compact_table(headers, reward_rows))
        else:
            rewards_section.set_content(no_data_label("No reward information available."))
            rewards_section.set_subtitle("No data")
        self._add_article_section(rewards_section)

        # --- Dependencies section ---
        deps = item.get("Dependencies") or {}
        prereqs = deps.get("Prerequisites") or []
        dependents = deps.get("Dependents") or []
        if prereqs or dependents:
            dep_section = DataSection("Dependencies", expanded=False)
            rows = []
            for p in prereqs:
                p_name = deep_get(p, "Mission", "Name") or p.get("Name") or "Unknown"
                rows.append([p_name, "Prerequisite"])
            for d in dependents:
                d_name = deep_get(d, "Mission", "Name") or d.get("Name") or "Unknown"
                rows.append([d_name, "Dependent"])
            dep_section.set_subtitle(f"{len(rows)} links")
            dep_section.set_content(make_compact_table(["Mission", "Relation"], rows))
            self._add_article_section(dep_section)
