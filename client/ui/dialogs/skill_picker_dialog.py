"""Dialog for picking skills to display on the dashboard chart."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QAbstractItemView, QPushButton, QLineEdit, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ..theme import (
    ACCENT, BORDER, HOVER, PRIMARY, SECONDARY, TEXT, TEXT_MUTED,
    TABLE_ROW_ALT,
)
from ..widgets.fuzzy_line_edit import score_search
from ...skills.skill_ids import name_to_id_map


class SkillPickerDialog(QDialog):
    """Modal dialog for selecting skills to chart on the dashboard.

    Supports multi-select with presets (category, profession, top gaining).
    """

    def __init__(
        self, *,
        skill_metadata: list[dict],
        professions: list[dict],
        skill_values: dict[str, float],
        top_gaining_skill_ids: list[int],
        preselected_ids: list[int] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Pick Skills to Chart")
        self.setMinimumSize(600, 450)
        self.resize(700, 520)

        self._skill_metadata = skill_metadata
        self._professions = professions
        self._skill_values = skill_values
        self._top_ids = set(top_gaining_skill_ids)
        self._nm = name_to_id_map()
        self._accepted = False

        # Build skill list (non-hidden only)
        self._skills = [
            s for s in skill_metadata if not s.get("IsHidden")
        ]
        self._skills.sort(key=lambda s: (s.get("Category", ""), s["Name"]))

        # Checked state: skill_id → bool
        self._checked: dict[int, bool] = {}
        presel = set(preselected_ids) if preselected_ids else set()
        for s in self._skills:
            sid = self._nm.get(s["Name"])
            if sid is not None:
                self._checked[sid] = sid in presel

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # --- Presets row ---
        presets = QHBoxLayout()
        presets.setSpacing(8)
        presets.addWidget(QLabel("Presets:"))

        self._preset_top = QPushButton("Top Gaining")
        self._preset_top.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preset_top.clicked.connect(self._apply_top_preset)
        presets.addWidget(self._preset_top)

        self._cat_combo = QComboBox()
        self._cat_combo.addItem("Category…")
        categories = sorted({s.get("Category", "") for s in self._skills} - {""})
        self._cat_combo.addItems(categories)
        self._cat_combo.currentIndexChanged.connect(self._on_category_preset)
        presets.addWidget(self._cat_combo)

        self._prof_combo = QComboBox()
        self._prof_combo.addItem("Profession…")
        prof_names = sorted(p["Name"] for p in professions if p.get("Name"))
        self._prof_combo.addItems(prof_names)
        self._prof_combo.currentIndexChanged.connect(self._on_profession_preset)
        presets.addWidget(self._prof_combo)

        clear_btn = QPushButton("Clear All")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_all)
        presets.addWidget(clear_btn)

        presets.addStretch()
        root.addLayout(presets)

        # --- Search ---
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search skills…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        self._search.setStyleSheet(
            f"QLineEdit {{ background: {PRIMARY}; color: {TEXT}; "
            f"border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 8px; }}"
        )
        root.addWidget(self._search)

        # --- Table ---
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Name", "Category", "Current"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.resizeSection(1, 120)
        hdr.resizeSection(2, 100)

        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {SECONDARY};
                alternate-background-color: {TABLE_ROW_ALT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                gridline-color: {BORDER};
                color: {TEXT};
            }}
            QTableWidget::item {{
                padding: 2px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {HOVER};
                color: {TEXT};
            }}
            QHeaderView::section {{
                background-color: {PRIMARY};
                color: {TEXT_MUTED};
                font-weight: 600;
                font-size: 11px;
                border: none;
                border-bottom: 1px solid {BORDER};
                padding: 4px 8px;
            }}
        """)
        self._table.cellClicked.connect(self._on_cell_clicked)
        root.addWidget(self._table, 1)

        # --- Bottom row ---
        bottom = QHBoxLayout()
        self._selected_label = QLabel()
        self._selected_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        bottom.addWidget(self._selected_label)
        bottom.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("accentButton")
        ok_btn.clicked.connect(self._on_accept)
        bottom.addWidget(ok_btn)
        root.addLayout(bottom)

        self.setStyleSheet(f"QDialog {{ background-color: {SECONDARY}; }}")

        self._populate(self._skills)
        self._update_selected_count()
        self._search.setFocus()

    # ── Population ────────────────────────────────────────────────────────

    def _populate(self, skills: list[dict]):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(skills))
        for i, skill in enumerate(skills):
            name = skill["Name"]
            sid = self._nm.get(name)
            checked = self._checked.get(sid, False) if sid is not None else False

            name_item = QTableWidgetItem(name)
            name_item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
            name_item.setData(Qt.ItemDataRole.UserRole, sid)
            self._table.setItem(i, 0, name_item)

            cat_item = QTableWidgetItem(skill.get("Category", ""))
            self._table.setItem(i, 1, cat_item)

            val = self._skill_values.get(name, 0)
            val_item = QTableWidgetItem(f"{val:,.2f}")
            val_item.setData(Qt.ItemDataRole.UserRole + 1, val)
            val_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(i, 2, val_item)
        self._table.setSortingEnabled(True)

    def _apply_filter(self, text: str):
        query = text.strip()
        if not query:
            self._populate(self._skills)
            return
        scored = []
        for skill in self._skills:
            s = score_search(skill["Name"], query)
            if s > 0:
                scored.append((s, skill))
        scored.sort(key=lambda x: x[0], reverse=True)
        self._populate([sk for _, sk in scored])

    # ── Presets ────────────────────────────────────────────────────────────

    def _apply_top_preset(self):
        self._clear_all_silent()
        for sid in self._top_ids:
            if sid in self._checked:
                self._checked[sid] = True
        self._sync_table_checks()
        self._update_selected_count()

    def _on_category_preset(self, index: int):
        if index <= 0:
            return
        category = self._cat_combo.currentText()
        self._cat_combo.blockSignals(True)
        self._cat_combo.setCurrentIndex(0)
        self._cat_combo.blockSignals(False)

        self._clear_all_silent()
        for skill in self._skills:
            if skill.get("Category") == category:
                sid = self._nm.get(skill["Name"])
                if sid is not None:
                    self._checked[sid] = True
        self._sync_table_checks()
        self._update_selected_count()

    def _on_profession_preset(self, index: int):
        if index <= 0:
            return
        prof_name = self._prof_combo.currentText()
        self._prof_combo.blockSignals(True)
        self._prof_combo.setCurrentIndex(0)
        self._prof_combo.blockSignals(False)

        prof = next(
            (p for p in self._professions if p.get("Name") == prof_name), None
        )
        if not prof:
            return

        self._clear_all_silent()
        for sk in prof.get("Skills", []):
            sid = self._nm.get(sk.get("Name", ""))
            if sid is not None and sid in self._checked:
                self._checked[sid] = True
        self._sync_table_checks()
        self._update_selected_count()

    def _clear_all(self):
        self._clear_all_silent()
        self._sync_table_checks()
        self._update_selected_count()

    def _clear_all_silent(self):
        for sid in self._checked:
            self._checked[sid] = False

    def _sync_table_checks(self):
        """Sync table checkbox visuals from self._checked state."""
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 0)
            if item is None:
                continue
            sid = item.data(Qt.ItemDataRole.UserRole)
            if sid is not None:
                item.setCheckState(
                    Qt.CheckState.Checked if self._checked.get(sid, False)
                    else Qt.CheckState.Unchecked
                )

    # ── Interaction ───────────────────────────────────────────────────────

    def _on_cell_clicked(self, row: int, _col: int):
        item = self._table.item(row, 0)
        if item is None:
            return
        sid = item.data(Qt.ItemDataRole.UserRole)
        if sid is None:
            return
        # Toggle
        new_state = not self._checked.get(sid, False)
        self._checked[sid] = new_state
        item.setCheckState(
            Qt.CheckState.Checked if new_state else Qt.CheckState.Unchecked
        )
        self._update_selected_count()

    def _update_selected_count(self):
        count = sum(1 for v in self._checked.values() if v)
        self._selected_label.setText(f"Selected: {count} skill{'s' if count != 1 else ''}")

    def _on_accept(self):
        self._accepted = True
        self.accept()

    # ── Public API ────────────────────────────────────────────────────────

    def get_selected_skill_ids(self) -> list[int]:
        """Return list of checked skill IDs, or empty if cancelled."""
        if not self._accepted:
            return []
        return [sid for sid, checked in self._checked.items() if checked]
