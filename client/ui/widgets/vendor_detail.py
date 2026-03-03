"""Vendor entity detail page — planet, coordinates, offers."""

from __future__ import annotations

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    WaypointCopyButton, no_data_label, make_section_table,
)
from .fancy_table import ColumnDef
from ...data.wiki_columns import deep_get, get_item_name, fmt_int


class VendorDetailView(WikiDetailView):
    """Detail view for a single vendor entity."""

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, parent=None):
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._build(item)

    def _build(self, item: dict):
        name = get_item_name(item)
        planet = deep_get(item, "Planet", "Name") or ""

        # --- Image ---
        self._add_image_placeholder(name)
        item_id = item.get("Id")
        if item_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/vendor/{item_id}"
            )

        # --- Badge + title ---
        subtitle_widgets = []
        if planet:
            subtitle_widgets.append(self._make_badge(planet))
        self._add_infobox_title(name, subtitle_widgets if subtitle_widgets else None)

        # --- Tier1: Offers count, Limited count ---
        offers = item.get("Offers") or []
        limited_count = sum(1 for o in offers if o.get("IsLimited"))

        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow("Offers", str(len(offers))))
        if limited_count:
            tier1.add_row(Tier1StatRow("Limited", str(limited_count)))
        self._add_section(tier1)

        # --- General ---
        general = InfoboxSection("General")
        general.add_row(StatRow("Planet", planet or "-"))
        coords = deep_get(item, "Properties", "Coordinates")
        if coords and coords.get("Longitude") is not None:
            general.add_widget(WaypointCopyButton(planet, coords, name))
        self._add_section(general)

        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Offers table ---
        offers_section = DataSection("Offers", expanded=True)
        if offers:
            offers_section.set_subtitle(f"{len(offers)} offers")
            flat = []
            for o in offers:
                flat.append({
                    "item": deep_get(o, "Item", "Name") or o.get("Name") or "-",
                    "_type": deep_get(o, "Item", "Type") or "Material",
                    "quantity": o.get("Quantity"),
                    "limited": o.get("IsLimited"),
                })
            table = make_section_table(
                [
                    ColumnDef("item", "Item", main=True),
                    ColumnDef("quantity", "Quantity", format=lambda v: fmt_int(v) if v else "-"),
                    ColumnDef("limited", "Limited", format=lambda v: "Yes" if v else "No"),
                ],
                flat,
            )
            table.row_activated.connect(
                lambda row, _idx: self.entity_navigate.emit(
                    {"Name": row.get("item", ""), "Type": row.get("_type", "Material")}
                )
            )
            offers_section.set_content(table)
        else:
            offers_section.set_content(no_data_label("No offers available."))
            offers_section.set_subtitle("No data")
        self._add_article_section(offers_section)
