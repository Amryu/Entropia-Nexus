"""Blueprint entity detail page — infobox with materials table and markup calculator."""

from __future__ import annotations

import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    section_title_label, no_data_label, make_compact_table,
    build_acquisition_content,
    _TABLE_MAX_HEIGHT, _TABLE_ROW_HEIGHT,
)
from ..theme import (
    PRIMARY, SECONDARY, BORDER, HOVER, TEXT, TEXT_MUTED, ACCENT,
)
from ...data.wiki_columns import (
    deep_get, get_item_name, _blueprint_cost, fmt_int, fmt_bool,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fv(value, decimals: int) -> str:
    """Format a numeric value with *decimals* decimal places, or '-'."""
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"


# ---------------------------------------------------------------------------
# MaterialsWidget — materials table with markup calculator
# ---------------------------------------------------------------------------

class _MaterialsWidget(QWidget):
    """Blueprint materials table with interactive markup calculator."""

    _FOOTER_STYLE = (
        f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 500;"
        f" background: transparent;"
    )
    _FOOTER_VALUE_STYLE = (
        f"color: {TEXT}; font-size: 12px; font-weight: 600;"
        f" background: transparent; font-family: monospace;"
    )
    _FOOTER_TOTAL_STYLE = (
        f"color: {ACCENT}; font-size: 12px; font-weight: 600;"
        f" background: transparent; font-family: monospace;"
    )

    def __init__(self, materials: list[dict], parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._materials = materials
        self._markups: dict[int, float] = {}  # idx → markup %

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        if not materials:
            layout.addWidget(no_data_label("No material information available."))
            return

        # Parse materials
        self._entries: list[dict] = []
        for idx, mat in enumerate(materials):
            item = mat.get("Item") or {}
            name = item.get("Name") or "Unknown"
            tt = deep_get(item, "Properties", "Economy", "MaxTT") or 0
            amount = mat.get("Amount") or 0
            self._entries.append({
                "idx": idx,
                "name": name,
                "tt": tt,
                "amount": amount,
            })

        # Build table: Ingredient | Amount | TT | MU % | Cost
        headers = ["Ingredient", "Amount", "TT", "MU %", "Cost"]
        num_rows = len(self._entries)
        table = QTableWidget(num_rows, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {SECONDARY};
                alternate-background-color: {PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                font-size: 13px;
                color: {TEXT};
            }}
            QTableWidget::item {{
                padding: 4px 10px;
                border-bottom: 1px solid {BORDER};
            }}
            QHeaderView::section {{
                background-color: {HOVER};
                color: {TEXT_MUTED};
                border: none;
                border-right: 1px solid {BORDER};
                border-bottom: 1px solid {BORDER};
                padding: 6px 10px;
                font-weight: 600;
                font-size: 11px;
            }}
        """)

        self._mu_spinboxes: list[tuple[int, QSpinBox]] = []

        for row, entry in enumerate(self._entries):
            mu = self._markups.get(entry["idx"], 100)
            line_tt = entry["tt"] * entry["amount"]
            cost = line_tt * mu / 100

            table.setItem(row, 0, QTableWidgetItem(entry["name"]))
            table.setItem(row, 1, QTableWidgetItem(str(entry["amount"])))
            table.setItem(row, 2, QTableWidgetItem(f"{line_tt:.4f}"))

            # MU % — editable spinbox
            spinbox = QSpinBox()
            spinbox.setMinimum(100)
            spinbox.setMaximum(99999)
            spinbox.setValue(int(mu))
            spinbox.setSuffix("%")
            spinbox.setStyleSheet(
                f"QSpinBox {{"
                f"  background-color: {PRIMARY}; color: {TEXT};"
                f"  border: 1px solid {BORDER}; border-radius: 3px;"
                f"  padding: 2px 4px; font-size: 12px;"
                f"}}"
                f"QSpinBox:focus {{"
                f"  border-color: {ACCENT};"
                f"}}"
            )
            spinbox.valueChanged.connect(
                lambda val, i=entry["idx"]: self._on_markup_changed(i, val)
            )
            table.setCellWidget(row, 3, spinbox)
            self._mu_spinboxes.append((entry["idx"], spinbox))

            table.setItem(row, 4, QTableWidgetItem(f"{cost:.2f}"))
            table.setRowHeight(row, _TABLE_ROW_HEIGHT)

        # Column sizing
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(headers)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        # Right-align numeric columns
        for row in range(num_rows):
            for col in (1, 2, 4):
                item = table.item(row, col)
                if item:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )

        content_height = _TABLE_ROW_HEIGHT + num_rows * _TABLE_ROW_HEIGHT + 4
        table.setFixedHeight(min(content_height, _TABLE_MAX_HEIGHT))

        self._table = table
        layout.addWidget(table)

        # Footer summary
        footer = QHBoxLayout()
        footer.setSpacing(8)

        sum_label = QLabel("Total")
        sum_label.setStyleSheet(self._FOOTER_STYLE)
        footer.addWidget(sum_label, 1)

        tt_lbl = QLabel("TT:")
        tt_lbl.setStyleSheet(self._FOOTER_STYLE)
        footer.addWidget(tt_lbl)
        self._total_tt = QLabel("0.00 PED")
        self._total_tt.setStyleSheet(self._FOOTER_VALUE_STYLE)
        self._total_tt.setMinimumWidth(80)
        self._total_tt.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        footer.addWidget(self._total_tt)

        mu_lbl = QLabel("MU:")
        mu_lbl.setStyleSheet(self._FOOTER_STYLE)
        footer.addWidget(mu_lbl)
        self._total_mu = QLabel("0.00 PED")
        self._total_mu.setStyleSheet(self._FOOTER_VALUE_STYLE)
        self._total_mu.setMinimumWidth(80)
        self._total_mu.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        footer.addWidget(self._total_mu)

        total_lbl = QLabel("Total:")
        total_lbl.setStyleSheet(self._FOOTER_STYLE)
        footer.addWidget(total_lbl)
        self._grand_total = QLabel("0.00 PED")
        self._grand_total.setStyleSheet(self._FOOTER_TOTAL_STYLE)
        self._grand_total.setMinimumWidth(80)
        self._grand_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        footer.addWidget(self._grand_total)

        layout.addLayout(footer)
        self._recalculate()

    def _on_markup_changed(self, idx: int, value: int):
        self._markups[idx] = value
        self._recalculate()

    def _recalculate(self):
        if not hasattr(self, "_table") or not self._entries:
            return

        total_tt = 0.0
        total_with_mu = 0.0

        for row, entry in enumerate(self._entries):
            mu = self._markups.get(entry["idx"], 100)
            line_tt = entry["tt"] * entry["amount"]
            cost = line_tt * mu / 100
            total_tt += line_tt
            total_with_mu += cost

            cost_item = self._table.item(row, 4)
            if cost_item:
                cost_item.setText(f"{cost:.2f}")

        mu_cost = total_with_mu - total_tt
        self._total_tt.setText(f"{total_tt:.2f} PED")
        self._total_mu.setText(f"{mu_cost:.2f} PED")
        self._grand_total.setText(f"{total_with_mu:.2f} PED")


# ---------------------------------------------------------------------------
# BlueprintDetailView
# ---------------------------------------------------------------------------

class BlueprintDetailView(WikiDetailView):
    """Detail view for a single blueprint entity."""

    _acquisition_loaded = pyqtSignal(dict)

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, parent=None):
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._acquisition_loaded.connect(self._on_acquisition_loaded)
        self._build(item)

    def _build(self, item: dict):
        name = get_item_name(item)
        bp_type = deep_get(item, "Properties", "Type") or "-"
        level = deep_get(item, "Properties", "Level")

        # --- Infobox header: image, name, subtitle ---
        self._add_image_placeholder(name)

        bp_id = item.get("Id")
        if bp_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/blueprint/{bp_id}"
            )

        subtitle_widgets = [
            self._make_badge(bp_type),
        ]
        if level is not None:
            subtitle_widgets.append(self._make_subtitle_text(f"Level {level}"))

        self._add_infobox_title(name, subtitle_widgets)

        # --- Tier 1: Cost, Product (blue gradient) ---
        cost = _blueprint_cost(item)
        product_name = deep_get(item, "Product", "Name") or "-"

        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow(
            "Cost", f"{_fv(cost, 2)} PED" if cost is not None else "-"
        ))
        tier1.add_row(Tier1StatRow("Level", str(level) if level is not None else "-"))
        self._add_section(tier1)

        # --- General Info ---
        weight = deep_get(item, "Properties", "Weight")
        book_name = deep_get(item, "Book", "Name") or "-"
        min_amount = deep_get(item, "Properties", "MinimumCraftAmount")
        max_amount = deep_get(item, "Properties", "MaximumCraftAmount")
        is_boosted = deep_get(item, "Properties", "IsBoosted")

        # Format craft amount range
        if min_amount is not None and max_amount is not None:
            if min_amount == max_amount:
                amount_str = str(min_amount)
            else:
                amount_str = f"{min_amount} - {max_amount}"
        elif min_amount is not None:
            amount_str = str(min_amount)
        elif max_amount is not None:
            amount_str = str(max_amount)
        else:
            amount_str = "-"

        general = InfoboxSection("General")
        general.add_row(StatRow(
            "Weight",
            f"{_fv(weight, 1)} kg" if weight is not None else "0.1 kg",
        ))
        general.add_row(StatRow("Level", fmt_int(level)))
        general.add_row(StatRow("Type", bp_type))
        general.add_row(StatRow("Book", book_name))
        general.add_row(StatRow("Product", product_name))
        general.add_row(StatRow("Amount", amount_str))
        general.add_row(StatRow(
            "Boosted", fmt_bool(is_boosted),
            highlight=(is_boosted is True or is_boosted == 1),
        ))
        self._add_section(general)

        # --- Skill Info ---
        is_sib = deep_get(item, "Properties", "Skill", "IsSiB")
        profession_name = deep_get(item, "Profession", "Name") or "-"
        level_start = deep_get(item, "Properties", "Skill", "LearningIntervalStart")
        level_end = deep_get(item, "Properties", "Skill", "LearningIntervalEnd")

        skill = InfoboxSection("Skill")
        skill.add_row(StatRow(
            "SiB", fmt_bool(is_sib),
            highlight=(is_sib is True or is_sib == 1),
        ))
        skill.add_row(StatRow("Profession", profession_name))
        if is_sib and (level_start is not None or level_end is not None):
            skill.add_row(StatRow(
                "Level Range",
                f"{fmt_int(level_start)} - {fmt_int(level_end)}",
                indent=True,
            ))
        self._add_section(skill)

        # Stretch at bottom of infobox
        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Construction panel (materials table) ---
        materials = item.get("Materials") or []
        construction_section = DataSection("Construction", expanded=True)
        if materials:
            construction_section.set_subtitle(f"{len(materials)} materials")
            construction_section.set_content(_MaterialsWidget(materials))
        else:
            construction_section.set_content(
                no_data_label("No material information available.")
            )
            construction_section.set_subtitle("No data")
        self._add_article_section(construction_section)

        # --- Acquisition panel ---
        self._acquisition_section = DataSection("Acquisition", expanded=True)
        self._acquisition_section.set_loading()
        self._add_article_section(self._acquisition_section)

        if self._data_client and name:
            def fetch_acq(item_name=name):
                data = self._data_client.get_acquisition(item_name)
                self._acquisition_loaded.emit(data)

            threading.Thread(
                target=fetch_acq, daemon=True, name="bp-acq-fetch"
            ).start()

        # --- Drops panel ---
        drops = item.get("Drops") or []
        drops_section = DataSection("Drops", expanded=True)
        if drops:
            drops_section.set_subtitle(f"{len(drops)} blueprints")
            headers = ["Blueprint"]
            rows = [[d.get("Name", "Unknown")] for d in drops]
            drops_section.set_content(make_compact_table(headers, rows))
        else:
            drops_section.set_content(
                no_data_label("No blueprint drops available.")
            )
            drops_section.set_subtitle("No data")
        self._add_article_section(drops_section)

    # --- Async data handlers ---

    def _on_acquisition_loaded(self, data: dict):
        """Handle acquisition data arriving from background thread."""
        if not hasattr(self, "_acquisition_section"):
            return
        content = build_acquisition_content(data)
        self._acquisition_section.set_content(content)
