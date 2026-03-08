"""Armor set entity detail page — defense breakdown, set pieces, and tiers."""

from __future__ import annotations

import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    DefenseBreakdownWidget, no_data_label, make_section_table,
    build_acquisition_content, build_usage_content, exchange_url,
    build_market_prices_content,
)
from .fancy_table import ColumnDef
from ..theme import TEXT_MUTED, ACCENT, BORDER, SECONDARY, DAMAGE_COLORS
from ...data.wiki_columns import (
    deep_get, get_item_name, armor_total_defense, _armor_total_absorption,
    _DAMAGE_TYPES, fmt_int, fmt_bool,
)


_SLOT_ORDER = ["Head", "Torso", "Arms", "Hands", "Legs", "Shins", "Feet"]


def _extract_armor_pieces(item: dict) -> list[dict]:
    """Extract a flat list of {name, slot, gender} from ArmorSet.Armors.

    Handles both array-of-arrays (schema) and flat array (legacy) formats.
    """
    armors = item.get("Armors") or []
    pieces: list[dict] = []
    for entry in armors:
        if isinstance(entry, list):
            # Array-of-arrays: entry is [variant1, variant2]
            for armor in entry:
                if not isinstance(armor, dict) or not armor.get("Name"):
                    continue
                pieces.append({
                    "name": armor["Name"],
                    "slot": deep_get(armor, "Properties", "Slot") or "",
                    "gender": deep_get(armor, "Properties", "Gender") or "Both",
                })
        elif isinstance(entry, dict) and entry.get("Name"):
            # Flat array: entry is an armor piece dict
            pieces.append({
                "name": entry["Name"],
                "slot": deep_get(entry, "Properties", "Slot") or "",
                "gender": deep_get(entry, "Properties", "Gender") or "Both",
            })
    return pieces


def _group_pieces_by_slot(
    pieces: list[dict],
) -> dict[str, dict]:
    """Group pieces into {slot: {male: piece|None, female: piece|None}}."""
    by_slot: dict[str, dict] = {}
    for p in pieces:
        slot = p.get("slot", "")
        if slot not in by_slot:
            by_slot[slot] = {"male": None, "female": None}
        gender = p.get("gender", "Both")
        if gender in ("Both", "Male"):
            by_slot[slot]["male"] = p
        if gender in ("Both", "Female"):
            by_slot[slot]["female"] = p
    return by_slot


def _mps_btn_style(active: bool) -> str:
    """Button style for piece/gender selector buttons."""
    if active:
        return (
            f"QPushButton {{ background: {ACCENT}; color: #fff; font-size: 12px;"
            f" border: 1px solid {ACCENT}; border-radius: 4px; padding: 2px 10px; }}"
            f"QPushButton:hover {{ background: {ACCENT}; }}"
        )
    return (
        f"QPushButton {{ background: transparent; color: {TEXT_MUTED}; font-size: 12px;"
        f" border: 1px solid {BORDER}; border-radius: 4px; padding: 2px 10px; }}"
        f"QPushButton:hover {{ background: {SECONDARY}; }}"
    )


def _fv(value, decimals: int) -> str:
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"


class ArmorSetDetailView(WikiDetailView):
    """Detail view for a single armor set entity."""

    _acquisition_loaded = pyqtSignal(dict)
    _usage_loaded = pyqtSignal(dict)

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, nexus_client=None, parent=None):
        self._nexus_client = nexus_client
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._acquisition_loaded.connect(self._on_acquisition_loaded)
        self._usage_loaded.connect(self._on_usage_loaded)
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
            flat = []
            for entry in armors:
                # Armors is a list of variant groups (list-of-lists);
                # each group holds gender variants for one slot.
                variants = entry if isinstance(entry, list) else [entry]
                for armor in variants:
                    if not isinstance(armor, dict):
                        continue
                    flat.append({
                        "slot": deep_get(armor, "Properties", "Slot") or "",
                        "name": armor.get("Name") or "",
                        "gender": deep_get(armor, "Properties", "Gender") or "",
                        "weight": deep_get(armor, "Properties", "Weight"),
                        "maxtt": deep_get(armor, "Properties", "Economy", "MaxTT"),
                    })
            pieces_section.set_content(make_section_table(
                [
                    ColumnDef("slot", "Slot"),
                    ColumnDef("name", "Name", main=True),
                    ColumnDef("gender", "Gender"),
                    ColumnDef("weight", "Weight", format=lambda v: f"{fmt_int(v)} kg" if v is not None else ""),
                    ColumnDef("maxtt", "Max TT", format=lambda v: _fv(v, 2) if v is not None else ""),
                ],
                flat,
            ))
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

        # --- Market Prices panel ---
        self._setup_market_prices_section()

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
                target=fetch_data, daemon=True, name="armor-data-fetch"
            ).start()

    def _on_acquisition_loaded(self, data: dict):
        if not hasattr(self, "_acquisition_section"):
            return
        url = exchange_url(self._item, self._nexus_base_url, "Armor")
        self._acquisition_section.set_content(build_acquisition_content(
            data, exchange_link=url, on_navigate=self.entity_navigate.emit))

    def _on_usage_loaded(self, data: dict):
        if not hasattr(self, "_usage_section"):
            return
        url = exchange_url(self._item, self._nexus_base_url, "Armor")
        self._usage_section.set_content(build_usage_content(
            data, exchange_link=url, on_navigate=self.entity_navigate.emit))

    # ------------------------------------------------------------------
    # Market Prices — piece/gender selector for armor sets
    # ------------------------------------------------------------------

    def _setup_market_prices_section(self):
        """Override: market prices with piece/gender selector for armor sets."""
        nc = getattr(self, "_nexus_client", None)
        if not nc:
            return

        pieces = _extract_armor_pieces(self._item)
        if not pieces:
            # No pieces — fall back to parent (set-level lookup)
            super()._setup_market_prices_section()
            return

        self._mps_pieces = pieces
        self._mps_by_slot = _group_pieces_by_slot(pieces)
        self._mps_ordered_slots = [
            s for s in _SLOT_ORDER if s in self._mps_by_slot
        ]
        self._mps_selected_slot = self._mps_ordered_slots[0] if self._mps_ordered_slots else ""
        self._mps_selected_gender = "male"

        self._mps_section = DataSection("Market Prices", expanded=True)
        self._mps_section.set_loading()
        self._add_article_section(self._mps_section)
        self._market_prices_loaded.connect(self._on_market_prices_loaded)

        # Fetch for default piece
        self._fetch_mps_for_current_piece()

    def _fetch_mps_for_current_piece(self):
        """Fetch market prices for the currently selected armor piece."""
        nc = getattr(self, "_nexus_client", None)
        if not nc:
            return
        entry = self._mps_by_slot.get(self._mps_selected_slot, {})
        has_gender = (
            entry.get("male") and entry.get("female")
            and entry["male"]["name"] != entry["female"]["name"]
        )
        if has_gender:
            pick = entry.get(self._mps_selected_gender) or entry.get("male")
        else:
            pick = entry.get("male") or entry.get("female")
        piece_name = pick["name"] if pick else None
        if not piece_name:
            return

        def fetch(name=piece_name):
            rows = nc.get_item_market_prices_by_name(name)
            self._market_prices_loaded.emit(rows[0] if rows else None)

        threading.Thread(
            target=fetch, daemon=True, name="wiki-detail-mps",
        ).start()

    def _on_market_prices_loaded(self, snapshot):
        if not hasattr(self, "_mps_section"):
            return
        # Build combined widget: piece selector + table
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        wlayout = QVBoxLayout(wrapper)
        wlayout.setContentsMargins(0, 0, 0, 0)
        wlayout.setSpacing(8)

        wlayout.addWidget(self._build_mps_piece_selector())
        wlayout.addWidget(build_market_prices_content(snapshot))

        self._mps_section.set_content(wrapper)

    def _build_mps_piece_selector(self) -> QWidget:
        """Build slot + gender buttons for armor set piece selection."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        # Slot buttons
        slot_row = QWidget()
        slot_row.setStyleSheet("background: transparent;")
        slot_layout = QHBoxLayout(slot_row)
        slot_layout.setContentsMargins(0, 0, 0, 0)
        slot_layout.setSpacing(3)
        for slot in self._mps_ordered_slots:
            btn = QPushButton(slot)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            active = slot == self._mps_selected_slot
            btn.setStyleSheet(_mps_btn_style(active))
            btn.setFixedHeight(26)
            btn.clicked.connect(
                lambda checked=False, s=slot: self._on_mps_slot_clicked(s)
            )
            slot_layout.addWidget(btn)
        slot_layout.addStretch(1)
        vbox.addWidget(slot_row)

        # Gender toggle (only if selected slot has distinct M/F variants)
        entry = self._mps_by_slot.get(self._mps_selected_slot, {})
        has_gender = (
            entry.get("male") and entry.get("female")
            and entry["male"]["name"] != entry["female"]["name"]
        )
        if has_gender:
            gender_row = QWidget()
            gender_row.setStyleSheet("background: transparent;")
            gender_layout = QHBoxLayout(gender_row)
            gender_layout.setContentsMargins(0, 0, 0, 0)
            gender_layout.setSpacing(6)
            for g, label in [("male", "Male"), ("female", "Female")]:
                btn = QPushButton(label)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                active = g == self._mps_selected_gender
                btn.setStyleSheet(_mps_btn_style(active))
                btn.setFixedHeight(26)
                btn.clicked.connect(
                    lambda checked=False, gv=g: self._on_mps_gender_clicked(gv)
                )
                gender_layout.addWidget(btn)
            gender_layout.addStretch(1)
            vbox.addWidget(gender_row)

        return container

    def _on_mps_slot_clicked(self, slot: str):
        self._mps_selected_slot = slot
        self._mps_selected_gender = "male"
        self._mps_section.set_loading()
        self._fetch_mps_for_current_piece()

    def _on_mps_gender_clicked(self, gender: str):
        self._mps_selected_gender = gender
        self._mps_section.set_loading()
        self._fetch_mps_for_current_piece()
