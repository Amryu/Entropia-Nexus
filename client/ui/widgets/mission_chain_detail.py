"""Mission-chain entity detail page — type, planet, missions list, dependency graph."""

from __future__ import annotations

import threading

from PyQt6.QtCore import pyqtSignal

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    no_data_label, make_section_table,
)
from .fancy_table import ColumnDef
from ...data.wiki_columns import deep_get, get_item_name


class MissionChainDetailView(WikiDetailView):
    """Detail view for a single mission-chain entity.

    The summary list only contains ``Name``, ``Properties``, and ``Planet``.
    Missions and graph data are fetched asynchronously from
    ``/missionchains/<name>`` and populated once ready.
    """

    _chain_detail_loaded = pyqtSignal(dict)

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, parent=None):
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._chain_detail_loaded.connect(self._on_chain_detail_loaded)
        self._missions_section: DataSection | None = None
        self._deps_section: DataSection | None = None
        self._build(item)

    def _build(self, item: dict):
        name = get_item_name(item)
        chain_type = deep_get(item, "Properties", "Type") or ""
        planet = deep_get(item, "Planet", "Name") or ""

        # --- Image ---
        self._add_image_placeholder(name)
        item_id = item.get("Id")
        if item_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/missionchain/{item_id}"
            )

        # --- Badge + title ---
        subtitle_widgets = []
        subtitle_widgets.append(self._make_badge("Mission Chain"))
        if planet:
            subtitle_widgets.append(self._make_subtitle_text(planet))
        self._add_infobox_title(name, subtitle_widgets)

        # --- Tier1: Type, Planet ---
        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow("Type", chain_type or "N/A"))
        tier1.add_row(Tier1StatRow("Planet", planet or "N/A"))
        self._add_section(tier1)

        # --- General: mission count (populated after async fetch) ---
        general = InfoboxSection("General")
        self._missions_count_row = StatRow("Missions", "Loading...")
        general.add_row(self._missions_count_row)
        self._add_section(general)

        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Missions section (loading until async fetch completes) ---
        self._missions_section = DataSection(
            "Missions in Chain", expanded=True,
        )
        self._missions_section.set_loading()
        self._add_article_section(self._missions_section)

        # --- Dependencies section (loading) ---
        self._deps_section = DataSection(
            "Mission Dependencies", expanded=False,
        )
        self._deps_section.set_loading()
        self._add_article_section(self._deps_section)

        # --- Kick off async detail fetch ---
        self._fetch_chain_detail(name)

    # ------------------------------------------------------------------
    # Async chain detail fetch
    # ------------------------------------------------------------------

    def _fetch_chain_detail(self, name: str):
        """Fetch the full chain (with missions + graph) in a background thread."""
        if not self._data_client:
            self._populate_empty()
            return

        def _do():
            detail = self._data_client.get_mission_chain_detail(name)
            if detail:
                self._chain_detail_loaded.emit(detail)
            else:
                # Emit empty dict so main thread can update placeholders
                self._chain_detail_loaded.emit({})

        threading.Thread(target=_do, daemon=True, name="chain-detail").start()

    def _on_chain_detail_loaded(self, detail: dict):
        """Populate missions and dependency sections from the full chain data."""
        missions = detail.get("Missions") or []
        graph = detail.get("Graph") or {}

        # Update missions count row
        self._missions_count_row.set_value(str(len(missions)))

        # --- Missions table ---
        if missions and self._missions_section:
            self._missions_section.set_subtitle(f"{len(missions)} missions")
            flat = []
            for m in missions:
                cooldown = deep_get(m, "Properties", "CooldownDuration")
                flat.append({
                    "name": get_item_name(m),
                    "type": deep_get(m, "Properties", "Type") or "-",
                    "planet": deep_get(m, "Planet", "Name") or "-",
                    "cooldown": _format_cooldown(cooldown),
                })
            self._missions_section.set_content(make_section_table(
                [
                    ColumnDef("name", "Mission", main=True),
                    ColumnDef("type", "Type"),
                    ColumnDef("planet", "Planet"),
                    ColumnDef("cooldown", "Cooldown"),
                ],
                flat,
            ))
        elif self._missions_section:
            self._missions_section.set_content(
                no_data_label("No missions in this chain yet.")
            )
            self._missions_section.set_subtitle("No data")

        # --- Dependency graph as table ---
        edges = graph.get("edges") or []
        nodes = graph.get("nodes") or []
        if edges and nodes and self._deps_section:
            node_map = {n["Id"]: n.get("Name", f"#{n['Id']}") for n in nodes}
            flat = []
            for e in edges:
                flat.append({
                    "prerequisite": node_map.get(e["FromId"], f"#{e['FromId']}"),
                    "mission": node_map.get(e["ToId"], f"#{e['ToId']}"),
                })
            self._deps_section.set_subtitle(f"{len(flat)} dependencies")
            self._deps_section.set_content(make_section_table(
                [
                    ColumnDef("prerequisite", "Prerequisite", main=True),
                    ColumnDef("mission", "Unlocks"),
                ],
                flat,
                searchable=False,
            ))
        elif self._deps_section:
            self._deps_section.set_content(
                no_data_label("No dependency information available.")
            )
            self._deps_section.set_subtitle("No data")

    def _populate_empty(self):
        """Fill placeholders when no data_client is available."""
        self._missions_count_row.set_value("N/A")
        if self._missions_section:
            self._missions_section.set_content(
                no_data_label("No missions in this chain yet.")
            )
            self._missions_section.set_subtitle("No data")
        if self._deps_section:
            self._deps_section.set_content(
                no_data_label("No dependency information available.")
            )
            self._deps_section.set_subtitle("No data")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _format_cooldown(cd) -> str:
    """Format a CooldownDuration dict (``{hours: N}``, ``{days: N}``, etc.) to a string."""
    if not cd or not isinstance(cd, dict):
        return "-"
    parts = []
    for unit in ("days", "hours", "minutes", "seconds"):
        v = cd.get(unit)
        if v:
            label = unit if v != 1 else unit.rstrip("s")
            parts.append(f"{v} {label}")
    return ", ".join(parts) if parts else "-"
