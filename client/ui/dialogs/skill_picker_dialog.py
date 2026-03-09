"""Dialog for picking skills or professions to display on the dashboard chart."""

from __future__ import annotations

import dataclasses

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QAbstractItemView, QPushButton, QLineEdit, QCheckBox,
    QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ..theme import (
    ACCENT, BORDER, HOVER, PRIMARY, SECONDARY, TEXT, TEXT_MUTED,
    TABLE_ROW_ALT,
)
from ..widgets.fuzzy_line_edit import score_search
from ...skills.skill_ids import name_to_id_map


@dataclasses.dataclass
class PickerResult:
    """Result from the picker dialog."""
    mode: str                       # "skills" | "professions"
    skill_ids: list[int]            # populated in skills mode
    profession_names: list[str]     # populated in professions mode


class SkillPickerDialog(QDialog):
    """Modal dialog for selecting skills or professions to chart.

    Supports multi-select with presets (category, profession/skill, top gaining).
    Mode toggle switches between picking individual skills or professions.
    """

    def __init__(
        self, *,
        skill_metadata: list[dict],
        professions: list[dict],
        skill_values: dict[str, float],
        profession_levels: dict[str, float] | None = None,
        top_gaining_skill_ids: list[int],
        preselected_ids: list[int] | None = None,
        preselected_prof_names: list[str] | None = None,
        initial_mode: str = "skills",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Pick Skills to Chart")
        self.setMinimumSize(600, 450)
        self.resize(700, 520)

        self._skill_metadata = skill_metadata
        self._professions = professions
        self._skill_values = skill_values
        self._profession_levels = profession_levels or {}
        self._top_ids = set(top_gaining_skill_ids)
        self._nm = name_to_id_map()
        self._accepted = False
        self._current_mode = initial_mode  # "skills" | "professions"

        # Build skill list (non-hidden only)
        self._skills = [
            s for s in skill_metadata if not s.get("IsHidden")
        ]
        self._skills.sort(key=lambda s: (s.get("Category", ""), s["Name"]))

        # Build profession rows (with category)
        self._prof_rows = []
        for prof in sorted(professions, key=lambda p: p.get("Name", "")):
            name = prof.get("Name", "")
            if not name:
                continue
            self._prof_rows.append({
                "name": name,
                "category": prof.get("Category") or "Uncategorized",
                "level": self._profession_levels.get(name, 0.0),
                "skill_count": len(prof.get("Skills", [])),
            })

        # Build reverse map: skill_name → set of profession names
        self._skill_to_profs: dict[str, set[str]] = {}
        for prof in professions:
            pname = prof.get("Name", "")
            if not pname:
                continue
            for sk in prof.get("Skills", []):
                sk_name = sk.get("Name", "")
                if sk_name:
                    self._skill_to_profs.setdefault(sk_name, set()).add(pname)

        # Top gaining profession names (professions with at least one top skill)
        id_to_name = {v: k for k, v in self._nm.items()}
        top_skill_names = {id_to_name[sid] for sid in self._top_ids if sid in id_to_name}
        self._top_prof_names: set[str] = set()
        for sk_name in top_skill_names:
            self._top_prof_names.update(self._skill_to_profs.get(sk_name, set()))

        # Checked state: skill_id → bool (skills mode)
        self._checked: dict[int, bool] = {}
        presel = set(preselected_ids) if preselected_ids else set()
        for s in self._skills:
            sid = self._nm.get(s["Name"])
            if sid is not None:
                self._checked[sid] = sid in presel

        # Checked state: profession_name → bool (professions mode)
        self._prof_checked: dict[str, bool] = {}
        presel_profs = set(preselected_prof_names) if preselected_prof_names else set()
        for row in self._prof_rows:
            self._prof_checked[row["name"]] = row["name"] in presel_profs

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # --- Mode toggle ---
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self._mode_group = QButtonGroup(self)
        self._radio_skills = QRadioButton("Skills")
        self._radio_professions = QRadioButton("Professions")
        self._mode_group.addButton(self._radio_skills, 0)
        self._mode_group.addButton(self._radio_professions, 1)
        if not professions:
            self._radio_professions.setEnabled(False)
        mode_row.addWidget(self._radio_skills)
        mode_row.addWidget(self._radio_professions)
        mode_row.addStretch()
        root.addLayout(mode_row)

        # --- Presets row ---
        presets = QHBoxLayout()
        presets.setSpacing(8)
        presets.addWidget(QLabel("Presets:"))

        # Shared: Top Gaining (mode-aware handler)
        self._preset_top = QPushButton("Top Gaining")
        self._preset_top.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preset_top.clicked.connect(self._apply_top_preset)
        presets.addWidget(self._preset_top)

        # Skills mode: Category dropdown
        self._cat_combo = QComboBox()
        self._cat_combo.addItem("Category\u2026")
        categories = sorted({s.get("Category", "") for s in self._skills} - {""})
        self._cat_combo.addItems(categories)
        self._cat_combo.currentIndexChanged.connect(self._on_category_preset)
        presets.addWidget(self._cat_combo)

        # Skills mode: Profession dropdown
        self._prof_combo = QComboBox()
        self._prof_combo.addItem("Profession\u2026")
        prof_names = sorted(p["Name"] for p in professions if p.get("Name"))
        self._prof_combo.addItems(prof_names)
        self._prof_combo.currentIndexChanged.connect(self._on_profession_preset)
        presets.addWidget(self._prof_combo)

        # Professions mode: Category dropdown
        self._prof_cat_combo = QComboBox()
        self._prof_cat_combo.addItem("Category\u2026")
        prof_categories = sorted(
            {r["category"] for r in self._prof_rows} - {"Uncategorized"}
        )
        if any(r["category"] == "Uncategorized" for r in self._prof_rows):
            prof_categories.append("Uncategorized")
        self._prof_cat_combo.addItems(prof_categories)
        self._prof_cat_combo.currentIndexChanged.connect(self._on_prof_category_preset)
        self._prof_cat_combo.hide()
        presets.addWidget(self._prof_cat_combo)

        # Professions mode: Skill dropdown (pick a skill → select related professions)
        self._prof_skill_combo = QComboBox()
        self._prof_skill_combo.addItem("Skill\u2026")
        skill_names_with_profs = sorted(self._skill_to_profs.keys())
        self._prof_skill_combo.addItems(skill_names_with_profs)
        self._prof_skill_combo.currentIndexChanged.connect(self._on_skill_preset)
        self._prof_skill_combo.hide()
        presets.addWidget(self._prof_skill_combo)

        # Shared: Clear All
        clear_btn = QPushButton("Clear All")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_all)
        presets.addWidget(clear_btn)

        presets.addStretch()
        root.addLayout(presets)

        # --- Search ---
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search skills\u2026")
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

        # Connect mode toggle and set initial mode
        self._mode_group.idToggled.connect(self._on_mode_changed)
        if initial_mode == "professions" and professions:
            self._radio_professions.setChecked(True)
        else:
            self._radio_skills.setChecked(True)
            # Trigger initial population if already checked (no signal fires)
            self._apply_mode("skills")

        self._search.setFocus()

    # ── Mode switching ─────────────────────────────────────────────────────

    def _on_mode_changed(self, button_id: int, checked: bool):
        if not checked:
            return
        mode = "professions" if button_id == 1 else "skills"
        self._apply_mode(mode)

    def _apply_mode(self, mode: str):
        self._current_mode = mode
        is_prof = mode == "professions"

        # Toggle preset visibility per mode
        self._cat_combo.setVisible(not is_prof)
        self._prof_combo.setVisible(not is_prof)
        self._prof_cat_combo.setVisible(is_prof)
        self._prof_skill_combo.setVisible(is_prof)

        # Update search
        self._search.setPlaceholderText(
            "Search professions\u2026" if is_prof else "Search skills\u2026"
        )
        self._search.clear()

        # Reconfigure table
        if is_prof:
            self._table.setColumnCount(3)
            self._table.setHorizontalHeaderLabels(["Name", "Level", "Skills"])
            hdr = self._table.horizontalHeader()
            hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            hdr.resizeSection(1, 80)
            hdr.resizeSection(2, 60)
            self._populate_professions(self._prof_rows)
        else:
            self._table.setColumnCount(3)
            self._table.setHorizontalHeaderLabels(["Name", "Category", "Current"])
            hdr = self._table.horizontalHeader()
            hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            hdr.resizeSection(1, 120)
            hdr.resizeSection(2, 100)
            self._populate(self._skills)

        self._update_selected_count()

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

    def _populate_professions(self, prof_rows: list[dict]):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(prof_rows))
        for i, row in enumerate(prof_rows):
            name = row["name"]
            checked = self._prof_checked.get(name, False)

            name_item = QTableWidgetItem(name)
            name_item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
            self._table.setItem(i, 0, name_item)

            level = row["level"]
            level_item = QTableWidgetItem(f"Lv {level:.1f}")
            level_item.setData(Qt.ItemDataRole.UserRole + 1, level)
            level_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(i, 1, level_item)

            count_item = QTableWidgetItem(str(row["skill_count"]))
            count_item.setData(Qt.ItemDataRole.UserRole + 1, row["skill_count"])
            count_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(i, 2, count_item)
        self._table.setSortingEnabled(True)

    def _apply_filter(self, text: str):
        query = text.strip()
        if self._current_mode == "professions":
            if not query:
                self._populate_professions(self._prof_rows)
                return
            scored = []
            for row in self._prof_rows:
                s = score_search(row["name"], query)
                if s > 0:
                    scored.append((s, row))
            scored.sort(key=lambda x: x[0], reverse=True)
            self._populate_professions([r for _, r in scored])
        else:
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
        if self._current_mode == "professions":
            for name in self._top_prof_names:
                if name in self._prof_checked:
                    self._prof_checked[name] = True
        else:
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

    def _on_prof_category_preset(self, index: int):
        """Profession mode: select all professions in a category."""
        if index <= 0:
            return
        category = self._prof_cat_combo.currentText()
        self._prof_cat_combo.blockSignals(True)
        self._prof_cat_combo.setCurrentIndex(0)
        self._prof_cat_combo.blockSignals(False)

        self._clear_all_silent()
        for row in self._prof_rows:
            if row["category"] == category:
                self._prof_checked[row["name"]] = True
        self._sync_table_checks()
        self._update_selected_count()

    def _on_skill_preset(self, index: int):
        """Profession mode: select all professions containing a given skill."""
        if index <= 0:
            return
        skill_name = self._prof_skill_combo.currentText()
        self._prof_skill_combo.blockSignals(True)
        self._prof_skill_combo.setCurrentIndex(0)
        self._prof_skill_combo.blockSignals(False)

        related = self._skill_to_profs.get(skill_name, set())
        if not related:
            return

        self._clear_all_silent()
        for name in related:
            if name in self._prof_checked:
                self._prof_checked[name] = True
        self._sync_table_checks()
        self._update_selected_count()

    def _clear_all(self):
        self._clear_all_silent()
        self._sync_table_checks()
        self._update_selected_count()

    def _clear_all_silent(self):
        if self._current_mode == "professions":
            for name in self._prof_checked:
                self._prof_checked[name] = False
        else:
            for sid in self._checked:
                self._checked[sid] = False

    def _sync_table_checks(self):
        """Sync table checkbox visuals from checked state."""
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 0)
            if item is None:
                continue
            if self._current_mode == "professions":
                name = item.text()
                checked = self._prof_checked.get(name, False)
            else:
                sid = item.data(Qt.ItemDataRole.UserRole)
                checked = self._checked.get(sid, False) if sid is not None else False
            item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )

    # ── Interaction ───────────────────────────────────────────────────────

    def _on_cell_clicked(self, row: int, _col: int):
        item = self._table.item(row, 0)
        if item is None:
            return
        if self._current_mode == "professions":
            name = item.text()
            new_state = not self._prof_checked.get(name, False)
            self._prof_checked[name] = new_state
        else:
            sid = item.data(Qt.ItemDataRole.UserRole)
            if sid is None:
                return
            new_state = not self._checked.get(sid, False)
            self._checked[sid] = new_state
        item.setCheckState(
            Qt.CheckState.Checked if new_state else Qt.CheckState.Unchecked
        )
        self._update_selected_count()

    def _update_selected_count(self):
        if self._current_mode == "professions":
            count = sum(1 for v in self._prof_checked.values() if v)
            label = "profession" if count == 1 else "professions"
        else:
            count = sum(1 for v in self._checked.values() if v)
            label = "skill" if count == 1 else "skills"
        self._selected_label.setText(f"Selected: {count} {label}")

    def _on_accept(self):
        self._accepted = True
        self.accept()

    # ── Public API ────────────────────────────────────────────────────────

    def get_result(self) -> PickerResult | None:
        """Return the picker result, or None if cancelled."""
        if not self._accepted:
            return None
        if self._current_mode == "professions":
            names = [n for n, c in self._prof_checked.items() if c]
            return PickerResult(mode="professions", skill_ids=[], profession_names=names)
        ids = [sid for sid, c in self._checked.items() if c]
        return PickerResult(mode="skills", skill_ids=ids, profession_names=[])
