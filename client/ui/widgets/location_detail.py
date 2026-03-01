"""Location entity detail page — type-specific (teleporter, area, estate, etc.)."""

from __future__ import annotations

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    WaypointCopyButton, no_data_label, make_compact_table,
)
from ...data.wiki_columns import deep_get, get_item_name, fmt_int


class LocationDetailView(WikiDetailView):
    """Detail view for a single location entity (multi-type)."""

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, parent=None):
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._build(item)

    def _build(self, item: dict):
        name = get_item_name(item)
        loc_type = deep_get(item, "Properties", "Type") or ""
        planet = deep_get(item, "Planet", "Name") or ""

        # --- Image ---
        self._add_image_placeholder(name)
        item_id = item.get("Id")
        if item_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/location/{item_id}"
            )

        # --- Badge + title ---
        subtitle_widgets = []
        if loc_type:
            subtitle_widgets.append(self._make_badge(loc_type))
        if planet:
            subtitle_widgets.append(self._make_subtitle_text(planet))
        self._add_infobox_title(name, subtitle_widgets if subtitle_widgets else None)

        # --- Tier1: Type, Planet ---
        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow("Type", loc_type or "N/A"))
        tier1.add_row(Tier1StatRow("Planet", planet or "N/A"))
        self._add_section(tier1)

        # --- General ---
        general = InfoboxSection("General")
        coords = deep_get(item, "Properties", "Coordinates")
        if coords and coords.get("Longitude") is not None:
            general.add_widget(WaypointCopyButton(planet, coords, name))
        parent_loc = deep_get(item, "ParentLocation", "Name")
        if parent_loc:
            general.add_row(StatRow("Parent", parent_loc))
        tech_id = deep_get(item, "Properties", "TechnicalId")
        if tech_id:
            general.add_row(StatRow("Technical ID", str(tech_id)))
        self._add_section(general)

        # --- Type-specific sections ---
        if loc_type == "Teleporter":
            dest = deep_get(item, "Destination", "Name")
            if dest:
                tp_section = InfoboxSection("Teleporter")
                tp_section.add_row(StatRow("Destination", dest))
                self._add_section(tp_section)

        elif loc_type in ("Apartment", "Estate", "House", "Villa", "Penthouse"):
            estate_type = deep_get(item, "Properties", "EstateType")
            owner_id = deep_get(item, "Properties", "OwnerId")
            if estate_type or owner_id:
                estate_section = InfoboxSection("Estate")
                if estate_type:
                    estate_section.add_row(StatRow("Estate Type", estate_type))
                if owner_id is not None:
                    estate_section.add_row(StatRow("Owner ID", str(owner_id)))
                self._add_section(estate_section)

        elif loc_type in ("Outpost", "Camp", "City", "Settlement"):
            facilities = item.get("Facilities") or []
            if facilities:
                fac_section = InfoboxSection("Facilities")
                for f in facilities:
                    f_name = f.get("Name") or f if isinstance(f, str) else str(f)
                    fac_section.add_row(StatRow(str(f_name), ""))
                self._add_section(fac_section)

        elif loc_type == "Area":
            area_type = deep_get(item, "Properties", "AreaType")
            shape = deep_get(item, "Properties", "Shape")
            if area_type or shape:
                area_section = InfoboxSection("Area")
                if area_type:
                    area_section.add_row(StatRow("Area Type", area_type))
                if shape:
                    area_section.add_row(StatRow("Shape", shape))
                self._add_section(area_section)

        elif loc_type == "WaveEvent":
            waves = item.get("Waves") or []
            if waves:
                wave_section = InfoboxSection("Wave Event")
                wave_section.add_row(StatRow("Waves", str(len(waves))))
                self._add_section(wave_section)

        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Facilities table (for settlements with detailed data) ---
        if loc_type in ("Outpost", "Camp", "City", "Settlement"):
            facilities = item.get("Facilities") or []
            if facilities and len(facilities) > 3:
                fac_section = DataSection("Facilities", expanded=True)
                fac_section.set_subtitle(f"{len(facilities)} facilities")
                headers = ["Facility"]
                rows = [[f.get("Name") or str(f)] for f in facilities]
                fac_section.set_content(make_compact_table(headers, rows))
                self._add_article_section(fac_section)

        # --- Waves table (for wave events) ---
        if loc_type == "WaveEvent":
            waves = item.get("Waves") or []
            if waves:
                wave_section = DataSection("Waves", expanded=True)
                wave_section.set_subtitle(f"{len(waves)} waves")
                headers = ["Wave", "Mobs", "Notes"]
                rows = []
                for i, w in enumerate(waves, 1):
                    mob_names = []
                    for m in (w.get("Mobs") or []):
                        mob_names.append(
                            deep_get(m, "Mob", "Name") or m.get("Name") or "Unknown"
                        )
                    rows.append([
                        str(i),
                        ", ".join(mob_names) if mob_names else "-",
                        w.get("Notes") or "-",
                    ])
                wave_section.set_content(make_compact_table(headers, rows))
                self._add_article_section(wave_section)
