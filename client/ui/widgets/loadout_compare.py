"""Loadout comparison table widget for the loadout editor page."""

from __future__ import annotations

import copy
import itertools
import queue
import re
import threading
from collections import Counter
from dataclasses import dataclass, field

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QCheckBox, QAbstractItemView, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QMetaObject
from PyQt6.QtGui import QColor, QAction

from ...core.logger import get_logger
from ..theme import (
    ACCENT, ACCENT_LIGHT, BORDER, ERROR, HOVER, MAIN_DARK, PRIMARY,
    SECONDARY, SUCCESS, TEXT, TEXT_MUTED,
)

log = get_logger("Compare")

# ── Constants ────────────────────────────────────────────────────────

MAX_PERMUTATIONS = 500

# ── Column definitions ────────────────────────────────────────────────

ALL_WEAPON_COLUMNS = [
    ("Name", "name", None),
    ("Eff %", "efficiency", True),
    ("DPS", "dps", True),
    ("DPP", "dpp", True),
    ("Crit %", "crit_chance", True),
    ("Crit Dmg", "crit_damage", True),
    ("Reload", "reload", False),
    ("Damage", "total_damage", True),
    ("Eff Dmg", "effective_damage", True),
    ("Range", "range", True),
    ("Cost", "cost", False),
    ("Decay", "decay", False),
    ("Ammo", "ammo_burn", False),
    ("Uses", "lowest_total_uses", True),
]

ALL_ARMOR_COLUMNS = [
    ("Name", "name", None),
    ("Defense", "total_defense", True),
    ("Types", "top_defense_types", None),
    ("Absorb", "total_absorption", True),
    ("Block %", "block_chance", True),
]

# Columns shown by default (by attr name)
DEFAULT_WEAPON_VISIBLE = {
    "name", "efficiency", "dps", "dpp", "crit_chance", "crit_damage",
    "total_damage", "effective_damage", "range", "cost", "decay",
    "ammo_burn", "lowest_total_uses",
}
DEFAULT_ARMOR_VISIBLE = {
    "name", "total_defense", "top_defense_types", "total_absorption",
    "block_chance",
}


@dataclass
class CompareRow:
    """A single row in the comparison table."""
    name: str = ""
    loadout_id: str = ""
    is_anchor: bool = False
    set_indices: dict = field(default_factory=dict)
    stats: object = None  # LoadoutStats


class LoadoutCompareWidget(QWidget):
    """Side-by-side loadout comparison table with set permutation support."""

    # Emitted when user clicks a row that represents a set permutation
    set_switch_requested = pyqtSignal(dict)  # {section: index, ...}
    # Emitted when set section checkboxes change (parent should re-evaluate)
    set_sections_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[CompareRow] = []
        self._compare_type = "weapons"
        self._display_mode = "values"  # "values" | "delta"
        self._anchor_stats = None
        self._set_mode = False
        self._set_sections: set[str] = set()
        self._js_path: str | None = None
        self._entity_data: dict = {}
        self._truncated = False
        self._pending_result = None
        self._work_queue: queue.Queue = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._visible_weapon_cols: set[str] = set(DEFAULT_WEAPON_VISIBLE)
        self._visible_armor_cols: set[str] = set(DEFAULT_ARMOR_VISIBLE)
        self._eval_generation = 0  # Incremented to cancel stale batches

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self._type_combo = QComboBox()
        self._type_combo.addItems(["Weapons", "Armor"])
        self._type_combo.setFixedWidth(100)
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        toolbar.addWidget(self._type_combo)

        self._display_combo = QComboBox()
        self._display_combo.addItems(["Values", "Delta"])
        self._display_combo.setFixedWidth(80)
        self._display_combo.currentTextChanged.connect(self._on_display_changed)
        toolbar.addWidget(self._display_combo)

        # Columns button with checkable menu
        self._cols_btn = QPushButton("Columns")
        self._cols_btn.setStyleSheet("padding: 2px 10px; font-size: 12px;")
        self._cols_menu = QMenu(self)
        self._cols_btn.clicked.connect(
            lambda: self._cols_menu.exec(
                self._cols_btn.mapToGlobal(self._cols_btn.rect().bottomLeft())
            )
        )
        self._rebuild_columns_menu()
        toolbar.addWidget(self._cols_btn)

        # Sets button
        self._sets_btn = QPushButton("Sets")
        self._sets_btn.setCheckable(True)
        self._sets_btn.setFixedHeight(26)
        self._sets_btn.setStyleSheet("padding: 2px 10px; font-size: 12px;")
        self._sets_btn.clicked.connect(self._on_sets_toggled)
        toolbar.addWidget(self._sets_btn)

        self._sets_menu_widget = QWidget()
        self._sets_menu_layout = QVBoxLayout(self._sets_menu_widget)
        self._sets_menu_layout.setContentsMargins(4, 4, 4, 4)
        self._sets_menu_layout.setSpacing(2)
        self._sets_menu_widget.hide()
        self._set_checkboxes: dict[str, QCheckBox] = {}

        self._perm_label = QLabel()
        self._perm_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        toolbar.addWidget(self._perm_label)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Sets selection panel (hidden by default)
        layout.addWidget(self._sets_menu_widget)

        # Table
        self._table = QTableWidget()
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {MAIN_DARK};
                alternate-background-color: {PRIMARY};
                gridline-color: {BORDER};
                border: 1px solid {BORDER};
                border-radius: 4px;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
            }}
            QTableWidget::item:selected {{
                background-color: {HOVER};
            }}
            QHeaderView::section {{
                background-color: {SECONDARY};
                color: {TEXT};
                border: none;
                border-right: 1px solid {BORDER};
                border-bottom: 1px solid {BORDER};
                padding: 4px 6px;
                font-size: 11px;
                font-weight: 600;
            }}
        """)
        self._table.cellClicked.connect(self._on_row_clicked)
        layout.addWidget(self._table, 1)

        # Loading overlay (centered on table)
        self._loading_label = QLabel("Evaluating\u2026", self._table)
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setStyleSheet(
            f"background: transparent; color: {TEXT_MUTED}; font-size: 13px;"
        )
        self._loading_label.hide()

    # ── Public API ────────────────────────────────────────────────────

    def set_js_path(self, js_path: str | None):
        self._js_path = js_path

    def set_entity_data(self, entity_data: dict):
        self._entity_data = entity_data

    def cleanup(self):
        """Cancel any running evaluation and stop the worker thread."""
        self._eval_generation += 1
        if self._worker_thread is not None:
            self._work_queue.put(None)  # Sentinel to stop thread

    def _ensure_worker(self):
        """Start the persistent evaluation worker thread if not already running."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._worker_thread = threading.Thread(
            target=self._eval_worker, daemon=True, name="compare-eval",
        )
        self._worker_thread.start()

    def _eval_worker(self):
        """Persistent worker: waits for jobs, evaluates, pushes results."""
        from ...loadout.calculator import LoadoutCalculator
        calc = None
        calc_js_path = None

        while True:
            job = self._work_queue.get()
            if job is None:
                break  # Shutdown sentinel

            gen, work, entity_data, js_path, truncated = job

            # (Re)create calculator if js_path changed
            if calc is None or js_path != calc_js_path:
                try:
                    calc = LoadoutCalculator(js_path)
                    calc_js_path = js_path
                except Exception:
                    log.exception("Failed to create LoadoutCalculator in worker")
                    continue

            rows = []
            anchor_stats = None
            cancelled = False
            for lo, name, is_anchor, set_indices in work:
                if self._eval_generation != gen:
                    cancelled = True
                    break
                try:
                    stats = calc.evaluate(lo, entity_data)
                except Exception:
                    stats = None
                row = CompareRow(
                    name=name,
                    loadout_id=lo.get("Id", ""),
                    is_anchor=is_anchor,
                    set_indices=set_indices,
                    stats=stats,
                )
                if is_anchor:
                    anchor_stats = stats
                rows.append(row)

            if cancelled or self._eval_generation != gen:
                continue

            self._pending_result = (gen, rows, anchor_stats, truncated)
            QMetaObject.invokeMethod(
                self, "_on_eval_complete",
                Qt.ConnectionType.QueuedConnection,
            )

    def update_comparison(
        self,
        loadouts: list[dict],
        current_loadout: dict | None,
        active_set_indices: dict | None = None,
    ):
        """Rebuild comparison table from loadout list (threaded to avoid UI freeze)."""
        self._rows.clear()
        self._anchor_stats = None
        self._truncated = False
        self._eval_generation += 1
        gen = self._eval_generation

        if not loadouts:
            self._loading_label.hide()
            self._refresh_table()
            return

        # Build the work items (lightweight — no evaluation yet)
        work: list[tuple] = []  # (loadout_dict, name, is_anchor, set_indices)
        truncated = False
        if self._set_mode and current_loadout and self._set_sections:
            count = 0
            for perm_lo, set_indices, label in self._iter_permutations(current_loadout):
                if count >= MAX_PERMUTATIONS:
                    truncated = True
                    break
                is_anchor = False
                if active_set_indices:
                    is_anchor = all(
                        set_indices.get(s) == active_set_indices.get(s)
                        for s in self._set_sections
                        if s in set_indices
                    )
                work.append((perm_lo, label, is_anchor, set_indices))
                count += 1
        else:
            for lo in loadouts:
                is_anchor = (
                    current_loadout is not None
                    and lo.get("Id") == current_loadout.get("Id")
                )
                work.append((lo, self._get_loadout_label(lo), is_anchor, {}))

        # Show loading state
        self._perm_label.setText(f"Evaluating {len(work)} loadouts\u2026")
        self._table.setRowCount(0)
        self._loading_label.setText(f"Evaluating {len(work)} loadouts\u2026")
        self._loading_label.resize(self._table.viewport().size())
        self._loading_label.show()

        # Drain any stale jobs and submit new work
        while not self._work_queue.empty():
            try:
                self._work_queue.get_nowait()
            except queue.Empty:
                break
        self._ensure_worker()
        self._work_queue.put((gen, work, self._entity_data, self._js_path, truncated))

    def update_set_options(self, loadout: dict | None):
        """Update the set section checkboxes based on current loadout."""
        # Clear existing checkboxes
        for cb in self._set_checkboxes.values():
            self._sets_menu_layout.removeWidget(cb)
            cb.deleteLater()
        self._set_checkboxes.clear()

        if not loadout or not loadout.get("Sets"):
            self._sets_btn.setEnabled(False)
            return

        has_any = False
        for section in ["Weapon", "Armor", "Healing", "Accessories"]:
            sets = loadout.get("Sets", {}).get(section, [])
            if isinstance(sets, list) and len(sets) > 1:
                has_any = True
                cb = QCheckBox(f"{section} ({len(sets)} sets)")
                cb.setChecked(section in self._set_sections)
                cb.stateChanged.connect(
                    lambda state, s=section: self._on_set_section_toggled(s, state)
                )
                self._sets_menu_layout.addWidget(cb)
                self._set_checkboxes[section] = cb

        self._sets_btn.setEnabled(has_any)
        if not has_any:
            self._set_sections.clear()
            self._set_mode = False
            self._sets_btn.setChecked(False)
            self._sets_menu_widget.hide()

    # ── Internal ──────────────────────────────────────────────────────

    @pyqtSlot()
    def _on_eval_complete(self):
        """Receive evaluation results from the worker thread."""
        result = self._pending_result
        if result is None:
            return
        self._pending_result = None
        gen, rows, anchor_stats, truncated = result
        if gen != self._eval_generation:
            return
        self._rows = rows
        self._anchor_stats = anchor_stats
        self._truncated = truncated
        self._loading_label.hide()
        self._refresh_table()

    def _get_loadout_label(self, lo: dict) -> str:
        name = lo.get("Name")
        if name and name != "New Loadout":
            return name
        weapon = (lo.get("Gear") or {}).get("Weapon", {}).get("Name")
        armor = (lo.get("Gear") or {}).get("Armor", {}).get("SetName")
        if weapon and armor:
            return f"{weapon} ({armor})"
        if weapon:
            return weapon
        return name or "New Loadout"

    def _iter_permutations(self, loadout: dict):
        """Yield (clone, set_indices, label) lazily via cartesian product."""
        section_order = [s for s in ["Weapon", "Armor", "Healing", "Accessories"]
                         if s in self._set_sections]

        # Pre-compute deduplicated labels per section
        section_labels: dict[str, list[str]] = {}
        section_sets = []
        for section in section_order:
            sets = loadout.get("Sets", {}).get(section, [])
            if not isinstance(sets, list) or len(sets) < 2:
                section_sets.append([(section, None, -1)])
            else:
                section_sets.append([(section, entry, i) for i, entry in enumerate(sets)])
                raw = [self._get_set_entry_label(section, entry, i)
                       for i, entry in enumerate(sets)]
                counts = Counter(raw)
                seen: dict[str, int] = {}
                deduped = []
                for lbl in raw:
                    if counts[lbl] > 1:
                        seen[lbl] = seen.get(lbl, 0) + 1
                        deduped.append(f"{lbl} ({seen[lbl]})")
                    else:
                        deduped.append(lbl)
                section_labels[section] = deduped

        for idx, combo in enumerate(itertools.product(*section_sets)):
            clone = copy.deepcopy(loadout)
            set_indices = {}
            name_parts = []
            for section, entry, i in combo:
                if entry is not None:
                    self._apply_set_to_loadout(section, clone, entry)
                    set_indices[section] = i
                    labels = section_labels.get(section)
                    name_parts.append(
                        labels[i] if labels and 0 <= i < len(labels)
                        else self._get_set_entry_label(section, entry, i)
                    )

            perm_id = f"{loadout.get('Id', '')}::perm::{idx}"
            clone["Id"] = perm_id
            label = " + ".join(name_parts) or clone.get("Name", "Permutation")
            yield (clone, set_indices, label)

    @staticmethod
    def _get_set_entry_label(section: str, entry: dict, idx: int) -> str:
        """Get display label for a set entry, falling back to main tool name."""
        name = (entry.get("name") or "").strip()
        # Only use user-assigned names (skip auto-generated "Set N")
        if name and not re.match(r"^Set \d+$", name):
            return name
        gear = entry.get("gear", {})
        if section == "Weapon":
            return gear.get("Name") or f"Weapon Set {idx + 1}"
        if section == "Armor":
            return gear.get("SetName") or f"Armor Set {idx + 1}"
        if section == "Healing":
            return gear.get("Name") or f"Healing Set {idx + 1}"
        if section == "Accessories":
            parts = []
            for c in (gear.get("Clothing") or []):
                n = c.get("Name", "") if isinstance(c, dict) else str(c)
                if n:
                    parts.append(n)
            for c in (gear.get("Consumables") or []):
                n = c.get("Name", "") if isinstance(c, dict) else str(c)
                if n:
                    parts.append(n)
            pet_name = (gear.get("Pet") or {}).get("Name")
            if pet_name:
                parts.append(pet_name)
            if not parts:
                return f"Accessories Set {idx + 1}"
            text = ", ".join(parts)
            if len(text) > 150:
                text = text[:147] + "..."
            return text
        return f"Set {idx + 1}"

    def _apply_set_to_loadout(self, section: str, loadout: dict, entry: dict):
        """Apply a set entry's gear/markup to a loadout dict (mirrors website applySectionData)."""
        gear = entry.get("gear", {})
        markup = entry.get("markup", {})
        if section == "Weapon":
            loadout["Gear"]["Weapon"] = gear
            for k in ("Weapon", "Ammo", "Amplifier", "Absorber", "Scope",
                       "Sight", "ScopeSight", "Matrix", "Implant"):
                if k in markup:
                    loadout["Markup"][k] = markup[k]
        elif section == "Armor":
            loadout["Gear"]["Armor"] = gear
            for k in ("ArmorSet", "PlateSet", "Armors", "Plates"):
                if k in markup:
                    loadout["Markup"][k] = markup[k]
        elif section == "Healing":
            loadout["Gear"]["Healing"] = gear
            if "HealingTool" in markup:
                loadout["Markup"]["HealingTool"] = markup["HealingTool"]
        elif section == "Accessories":
            loadout["Gear"]["Clothing"] = gear.get("Clothing", [])
            loadout["Gear"]["Consumables"] = gear.get("Consumables", [])
            loadout["Gear"]["Pet"] = gear.get("Pet", {"Name": None, "Effect": None})

    def _columns(self):
        if self._compare_type == "weapons":
            visible = self._visible_weapon_cols
            return [c for c in ALL_WEAPON_COLUMNS if c[1] in visible]
        visible = self._visible_armor_cols
        return [c for c in ALL_ARMOR_COLUMNS if c[1] in visible]

    def _refresh_table(self):
        cols = self._columns()
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels([c[0] for c in cols])
        self._table.setRowCount(len(self._rows))

        for row_idx, row in enumerate(self._rows):
            for col_idx, (header, attr, higher_is_better) in enumerate(cols):
                if attr == "name":
                    item = QTableWidgetItem(row.name)
                    if row.is_anchor:
                        item.setForeground(QColor(ACCENT))
                else:
                    value = getattr(row.stats, attr, None) if row.stats else None
                    anchor_value = getattr(self._anchor_stats, attr, None) if self._anchor_stats else None

                    if self._display_mode == "delta" and anchor_value is not None and value is not None and higher_is_better is not None:
                        delta = value - anchor_value
                        text = self._format_delta(delta, attr)
                        item = QTableWidgetItem(text)
                        item.setData(Qt.ItemDataRole.UserRole, delta)
                        if abs(delta) > 0.001:
                            good = (delta > 0) == higher_is_better
                            item.setForeground(QColor(SUCCESS if good else ERROR))
                    else:
                        text = self._format_value(value, attr)
                        item = QTableWidgetItem(text)
                        if value is not None:
                            item.setData(Qt.ItemDataRole.UserRole, value)

                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                if row.is_anchor:
                    item.setBackground(QColor(ACCENT_LIGHT))

                self._table.setItem(row_idx, col_idx, item)

        # Resize columns
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(cols)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        # Update permutation count label
        if self._set_mode:
            text = f"{len(self._rows)} permutation{'s' if len(self._rows) != 1 else ''}"
            if self._truncated:
                text += f" (limited to {MAX_PERMUTATIONS})"
            self._perm_label.setText(text)
        else:
            self._perm_label.setText("")

    @staticmethod
    def _format_value(value, attr: str) -> str:
        if value is None:
            return "-"
        if attr == "top_defense_types":
            return str(value) if value else "-"
        if isinstance(value, float):
            if attr in ("efficiency", "block_chance"):
                return f"{value:.1f}%"
            if attr == "crit_chance":
                return f"{value * 100:.1f}%"
            if attr == "crit_damage":
                return f"{value * 100:.0f}%"
            return f"{value:.4f}" if attr in ("dps", "dpp") else f"{value:.2f}"
        return str(value)

    @staticmethod
    def _format_delta(delta: float, attr: str = "") -> str:
        # Scale crit values (stored as decimals/multipliers) to percentage display
        if attr in ("crit_chance", "crit_damage"):
            delta = delta * 100
        sign = "+" if delta > 0 else ""
        return f"{sign}{delta:.2f}"

    def _rebuild_columns_menu(self):
        """Rebuild the Columns dropdown menu with checkboxes for current type."""
        self._cols_menu.clear()
        if self._compare_type == "weapons":
            all_cols = ALL_WEAPON_COLUMNS
            visible = self._visible_weapon_cols
        else:
            all_cols = ALL_ARMOR_COLUMNS
            visible = self._visible_armor_cols
        for header, attr, _ in all_cols:
            if attr == "name":
                continue  # Name column is always shown
            action = QAction(header, self._cols_menu)
            action.setCheckable(True)
            action.setChecked(attr in visible)
            action.toggled.connect(lambda checked, a=attr: self._on_column_toggled(a, checked))
            self._cols_menu.addAction(action)

    def _on_column_toggled(self, attr: str, checked: bool):
        visible = (self._visible_weapon_cols if self._compare_type == "weapons"
                   else self._visible_armor_cols)
        if checked:
            visible.add(attr)
        else:
            visible.discard(attr)
        self._refresh_table()

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_type_changed(self, text: str):
        self._compare_type = "weapons" if text == "Weapons" else "armor"
        self._rebuild_columns_menu()
        self._refresh_table()

    def _on_display_changed(self, text: str):
        self._display_mode = "values" if text == "Values" else "delta"
        self._refresh_table()

    def _on_sets_toggled(self):
        show = self._sets_btn.isChecked()
        self._sets_menu_widget.setVisible(show)

    def _on_set_section_toggled(self, section: str, state: int):
        if state == Qt.CheckState.Checked.value:
            self._set_sections.add(section)
        else:
            self._set_sections.discard(section)
        self._set_mode = len(self._set_sections) > 0
        self.set_sections_changed.emit()

    def _on_row_clicked(self, row: int, col: int):
        if row < 0 or row >= len(self._rows):
            return
        compare_row = self._rows[row]
        if compare_row.set_indices:
            self.set_switch_requested.emit(compare_row.set_indices)
