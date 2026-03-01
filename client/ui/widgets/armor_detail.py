"""Armor set entity detail page — defense breakdown, set pieces, and tiers."""

from __future__ import annotations

import threading

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    DefenseBreakdownWidget, no_data_label, make_compact_table,
    build_acquisition_content,
)
from ..theme import TEXT_MUTED, DAMAGE_COLORS
from ...data.wiki_columns import (
    deep_get, get_item_name, armor_total_defense, _armor_total_absorption,
    _DAMAGE_TYPES, fmt_int, fmt_bool,
)


def _fv(value, decimals: int) -> str:
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"


class ArmorSetDetailView(WikiDetailView):
    """Detail view for a single armor set entity."""

    _acquisition_loaded = pyqtSignal(dict)

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, nexus_client=None, parent=None):
        self._nexus_client = nexus_client
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._acquisition_loaded.connect(self._on_acquisition_loaded)
        self._build(item)

    def _build(self, item: dict):
        name = get_item_name(item)

        # --- Image ---
        self._add_image_placeholder(name)
        item_id = item.get("Id")
        if item_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/armorset/{item_id}"
            )

        # --- Badge + title ---
        armors = item.get("Armors") or []
        piece_count = len(armors)
        subtitle_widgets = [
            self._make_badge("Armor Set"),
        ]
        if piece_count:
            subtitle_widgets.append(
                self._make_subtitle_text(f"{piece_count} pieces")
            )
        self._add_infobox_title(name, subtitle_widgets)

        # --- Tier1: Total Defense, Absorption ---
        total_def = armor_total_defense(item)
        absorption = _armor_total_absorption(item)

        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow("Defense", _fv(total_def, 1)))
        tier1.add_row(Tier1StatRow("Absorption", f"{_fv(absorption, 0)} HP"))
        self._add_section(tier1)

        # --- Defense breakdown ---
        defense = deep_get(item, "Properties", "Defense")
        if defense:
            def_section = InfoboxSection("Defense")
            def_section.add_widget(DefenseBreakdownWidget(defense))
            self._add_section(def_section)

        # --- Economy ---
        max_tt = deep_get(item, "Properties", "Economy", "MaxTT")
        min_tt = deep_get(item, "Properties", "Economy", "MinTT")
        durability = deep_get(item, "Properties", "Economy", "Durability")
        weight = deep_get(item, "Properties", "Weight")

        econ = InfoboxSection("Economy")
        econ.add_row(StatRow(
            "Max TT", f"{_fv(max_tt, 2)} PED" if max_tt is not None else "-"
        ))
        econ.add_row(StatRow(
            "Min TT", f"{_fv(min_tt, 2)} PED" if min_tt is not None else "-"
        ))
        econ.add_row(StatRow("Durability", _fv(durability, 1)))
        econ.add_row(StatRow(
            "Weight", f"{fmt_int(weight)} kg" if weight is not None else "-"
        ))
        self._add_section(econ)

        # --- Set Effects ---
        set_effects = item.get("EffectsOnSetEquip") or []
        if set_effects:
            eff_section = InfoboxSection("Set Effects")
            # Group by MinSetPieces
            by_pieces: dict[int, list] = {}
            for eff in set_effects:
                pieces = eff.get("MinSetPieces", 0)
                by_pieces.setdefault(pieces, []).append(eff)
            for pieces in sorted(by_pieces.keys()):
                sub_lbl = QLabel(f"{pieces}-Piece Bonus")
                sub_lbl.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600;"
                    " background: transparent; margin-top: 4px;"
                )
                eff_section.add_widget(sub_lbl)
                for eff in by_pieces[pieces]:
                    eff_section.add_row(StatRow(
                        eff.get("Name", "Unknown"), "", indent=True
                    ))
            self._add_section(eff_section)

        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Set Pieces table ---
        if armors:
            pieces_section = DataSection("Set Pieces", expanded=True)
            pieces_section.set_subtitle(f"{piece_count} pieces")
            headers = ["Slot", "Name", "Gender", "Weight", "Max TT"]
            rows = []
            for armor in armors:
                slot = deep_get(armor, "Properties", "Slot") or "-"
                a_name = armor.get("Name") or "-"
                gender = deep_get(armor, "Properties", "Gender") or "-"
                a_weight = deep_get(armor, "Properties", "Weight")
                a_maxtt = deep_get(armor, "Properties", "Economy", "MaxTT")
                rows.append([
                    slot, a_name, gender,
                    f"{fmt_int(a_weight)} kg" if a_weight is not None else "-",
                    f"{_fv(a_maxtt, 2)}" if a_maxtt is not None else "-",
                ])
            pieces_section.set_content(make_compact_table(headers, rows))
            self._add_article_section(pieces_section)

        # --- Tiers panel (non-L items only) ---
        is_limited = name.endswith("(L)") if name else False
        if not is_limited:
            tiers_data = item.get("Tiers") or []
            tiers_section = DataSection("Tiers", expanded=True)
            if tiers_data:
                tiers_section.set_subtitle(f"{len(tiers_data)} tiers")
                # Reuse weapon tier widget
                from .weapon_detail import _TiersWidget
                tiers_section.set_content(_TiersWidget(
                    tiers_data, entity_type="ArmorSet",
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

        if self._data_client and name:
            def fetch_acq(item_name=name):
                data = self._data_client.get_acquisition(item_name)
                self._acquisition_loaded.emit(data)

            threading.Thread(
                target=fetch_acq, daemon=True, name="armor-acq-fetch"
            ).start()

    def _on_acquisition_loaded(self, data: dict):
        if not hasattr(self, "_acquisition_section"):
            return
        content = build_acquisition_content(data)
        self._acquisition_section.set_content(content)
