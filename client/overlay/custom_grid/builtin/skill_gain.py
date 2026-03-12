"""Skill Gain widget — shows recent skill gains with running total.

Config keys
-----------
mode            str   "all" | "category" | "skills"
category        str   Category name when mode=category (e.g. "Combat").
skills          list  List of skill names when mode=skills.
show_attributes bool  Include attribute gains (default True).
sort_by         str   "gain" | "name" | "recent"
goal_total      float Total gain goal; 0 = disabled.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QCheckBox,
    QDoubleSpinBox, QSpinBox, QGroupBox, QListWidget, QListWidgetItem,
    QLineEdit, QProgressBar, QSizePolicy,
)
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext
from ....core.constants import EVENT_SKILL_GAIN
from ._common import font_title, font_label, C_ACCENT, C_BLUE, C_GREEN

_MAX_VISIBLE_SKILLS = 30

_BTN_STYLE = (
    "QPushButton { background: #2a2a3a; color: #888; border: none; "
    "font-size: 9px; padding: 1px 4px; border-radius: 2px; }"
    "QPushButton:hover { color: #cc6666; }"
)

_DIALOG_STYLE = """
    QDialog       { background: #1a1a2e; }
    QGroupBox     { color: #00ccff; border: 1px solid #333355; border-radius: 4px;
                    margin-top: 8px; padding-top: 6px; font-size: 11px; }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; top: 2px; }
    QLabel        { color: #cccccc; font-size: 11px; }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                    background: #252535; color: #e0e0e0;
                    border: 1px solid #555; border-radius: 4px;
                    padding: 3px 6px; font-size: 11px; }
    QCheckBox     { color: #cccccc; font-size: 11px; }
    QCheckBox::indicator { width: 14px; height: 14px; }
    QListWidget   { background: #141422; color: #cccccc; border: 1px solid #333355;
                    border-radius: 4px; font-size: 11px; }
    QListWidget::item:selected { background: #2a3a5a; color: #e0e0e0; }
    QPushButton   { background: #333350; color: #e0e0e0;
                    border: 1px solid #555; border-radius: 4px;
                    padding: 4px 14px; font-size: 11px; }
    QPushButton:hover   { background: #404060; }
    QPushButton:pressed { background: #252540; }
    QProgressBar  { background: #252535; border: 1px solid #555; border-radius: 3px;
                    text-align: center; color: #e0e0e0; font-size: 10px; }
    QProgressBar::chunk { background: #305090; border-radius: 2px; }
"""

_GOAL_BAR_STYLE = (
    "QProgressBar { background: #1a1a2e; border: 1px solid #333355;"
    " border-radius: 3px; text-align: center; color: #aaa; font-size: 9px; }"
    "QProgressBar::chunk { background: qlineargradient("
    "x1:0, y1:0, x2:1, y2:0, stop:0 #305090, stop:1 #40a060);"
    " border-radius: 2px; }"
)

# ---------------------------------------------------------------------------
# Skill reference data (categories)
# ---------------------------------------------------------------------------

_REF_PATH = Path(__file__).parent.parent.parent.parent / "data" / "skill_reference.json"


def _load_skill_ref() -> list[dict]:
    try:
        with open(_REF_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _skill_categories() -> list[str]:
    cats: set[str] = set()
    for entry in _load_skill_ref():
        c = entry.get("category")
        if c:
            cats.add(c)
    return sorted(cats)


def _skills_in_category(category: str) -> set[str]:
    return {
        e["name"] for e in _load_skill_ref()
        if e.get("category") == category
    }


def _all_skill_names() -> list[str]:
    return sorted(e["name"] for e in _load_skill_ref())


def _is_attribute(skill_name: str) -> bool:
    for e in _load_skill_ref():
        if e["name"] == skill_name:
            return e.get("category") == "Attributes"
    return False


# ---------------------------------------------------------------------------
# Config dialog
# ---------------------------------------------------------------------------

class _SkillGainConfigDialog(QDialog):
    def __init__(
        self,
        cfg: dict,
        *,
        parent=None,
        current_colspan: int = 5,
        current_rowspan: int = 5,
        max_cols: int = 50,
        max_rows: int = 50,
        widget_max_cols: int = 0,
        widget_max_rows: int = 0,
    ):
        super().__init__(parent)
        self.setWindowTitle("Configure Skill Gains")
        self.setMinimumWidth(400)
        self.setStyleSheet(_DIALOG_STYLE)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        eff_max_cols = min(max_cols, widget_max_cols) if widget_max_cols > 0 else max_cols
        eff_max_rows = min(max_rows, widget_max_rows) if widget_max_rows > 0 else max_rows

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(14, 14, 14, 14)

        # ── Filter ───────────────────────────────────────────────────────────
        filter_group = QGroupBox("Filter")
        filter_form = QFormLayout(filter_group)
        filter_form.setSpacing(6)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["All Skills", "Category", "Specific Skills"])
        mode = cfg.get("mode", "all")
        self._mode_combo.setCurrentText(
            {"all": "All Skills", "category": "Category", "skills": "Specific Skills"}.get(mode, "All Skills")
        )
        filter_form.addRow("Show:", self._mode_combo)

        # Category selector
        self._cat_combo = QComboBox()
        self._cat_combo.addItems(_skill_categories())
        self._cat_combo.setCurrentText(cfg.get("category", "Combat"))
        filter_form.addRow("Category:", self._cat_combo)

        # Specific skills list
        self._skills_filter = QLineEdit()
        self._skills_filter.setPlaceholderText("Search skills…")
        self._skills_filter.textChanged.connect(self._filter_skills_list)
        filter_form.addRow("", self._skills_filter)

        self._skills_list = QListWidget()
        self._skills_list.setMaximumHeight(140)
        selected_skills = set(cfg.get("skills", []))
        for name in _all_skill_names():
            item = QListWidgetItem(name)
            item.setCheckState(
                Qt.CheckState.Checked if name in selected_skills else Qt.CheckState.Unchecked
            )
            self._skills_list.addItem(item)
        filter_form.addRow("Skills:", self._skills_list)

        self._attr_check = QCheckBox("Include attribute gains")
        self._attr_check.setChecked(cfg.get("show_attributes", True))
        filter_form.addRow("", self._attr_check)

        root.addWidget(filter_group)

        # Wire mode visibility
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self._on_mode_changed(self._mode_combo.currentText())

        # ── Display ──────────────────────────────────────────────────────────
        disp_group = QGroupBox("Display")
        disp_form = QFormLayout(disp_group)
        disp_form.setSpacing(6)

        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["By Gain (descending)", "By Name", "By Recent"])
        sort_by = cfg.get("sort_by", "gain")
        self._sort_combo.setCurrentText(
            {"gain": "By Gain (descending)", "name": "By Name", "recent": "By Recent"}.get(sort_by, "By Gain (descending)")
        )
        disp_form.addRow("Sort:", self._sort_combo)

        root.addWidget(disp_group)

        # ── Goal ─────────────────────────────────────────────────────────────
        goal_group = QGroupBox("Goal")
        goal_form = QFormLayout(goal_group)
        goal_form.setSpacing(6)

        self._goal_spin = QDoubleSpinBox()
        self._goal_spin.setRange(0.0, 999999.0)
        self._goal_spin.setDecimals(2)
        self._goal_spin.setSpecialValueText("Disabled")
        self._goal_spin.setSuffix(" total exp")
        self._goal_spin.setValue(cfg.get("goal_total", 0.0))
        goal_form.addRow("Total gain goal:", self._goal_spin)

        root.addWidget(goal_group)

        # ── Size ─────────────────────────────────────────────────────────────
        size_group = QGroupBox("Size (tiles)")
        size_form = QFormLayout(size_group)
        size_form.setSpacing(6)

        self._cs_spin = QSpinBox()
        self._cs_spin.setRange(1, eff_max_cols)
        self._cs_spin.setValue(current_colspan)
        size_form.addRow("Width (colspan):", self._cs_spin)

        self._rs_spin = QSpinBox()
        self._rs_spin.setRange(1, eff_max_rows)
        self._rs_spin.setValue(current_rowspan)
        size_form.addRow("Height (rowspan):", self._rs_spin)

        root.addWidget(size_group)

        # ── Buttons ──────────────────────────────────────────────────────────
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setStyleSheet(
                "QPushButton { background: #305090; border-color: #4070b0; }"
                "QPushButton:hover { background: #3a60a8; }"
            )
        root.addWidget(btns)

    def _on_mode_changed(self, text: str) -> None:
        is_cat = text == "Category"
        is_skills = text == "Specific Skills"
        self._cat_combo.setVisible(is_cat)
        # Find the label for cat_combo and hide it too
        self._skills_filter.setVisible(is_skills)
        self._skills_list.setVisible(is_skills)
        self.setMinimumHeight(0)
        self.adjustSize()

    def _filter_skills_list(self, text: str) -> None:
        q = text.lower().strip()
        for i in range(self._skills_list.count()):
            item = self._skills_list.item(i)
            if item:
                item.setHidden(q != "" and q not in item.text().lower())

    def get_result(self) -> dict:
        mode_text = self._mode_combo.currentText()
        mode = {"All Skills": "all", "Category": "category", "Specific Skills": "skills"}.get(mode_text, "all")

        sort_text = self._sort_combo.currentText()
        sort_by = {"By Gain (descending)": "gain", "By Name": "name", "By Recent": "recent"}.get(sort_text, "gain")

        selected_skills = []
        for i in range(self._skills_list.count()):
            item = self._skills_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected_skills.append(item.text())

        return {
            "mode": mode,
            "category": self._cat_combo.currentText(),
            "skills": selected_skills,
            "show_attributes": self._attr_check.isChecked(),
            "sort_by": sort_by,
            "goal_total": self._goal_spin.value(),
            "__slot__": {
                "colspan": self._cs_spin.value(),
                "rowspan": self._rs_spin.value(),
            },
        }


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class SkillGainWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.skill_gain"
    DISPLAY_NAME = "Skill Gains"
    DESCRIPTION = "Running totals of skill experience gained this session."
    DEFAULT_COLSPAN = 5
    DEFAULT_ROWSPAN = 5
    MIN_COLSPAN = 2
    MIN_ROWSPAN = 2

    def __init__(self, config: dict):
        super().__init__(config)
        self._totals: dict[str, float] = defaultdict(float)
        self._order: list[str] = []  # insertion order for "recent" sort
        self._rows: dict[str, QLabel] = {}
        self._key_labels: dict[str, QLabel] = {}
        self._list_layout: QVBoxLayout | None = None
        self._title_label: QLabel | None = None
        self._empty_label: QLabel | None = None
        self._goal_bar: QProgressBar | None = None
        # Build filter sets
        self._rebuild_filter()

    def _rebuild_filter(self) -> None:
        """Build the set of accepted skill names from config."""
        cfg = self._widget_config
        mode = cfg.get("mode", "all")
        self._show_attrs = cfg.get("show_attributes", True)
        if mode == "category":
            self._accepted: set[str] | None = _skills_in_category(cfg.get("category", ""))
        elif mode == "skills":
            self._accepted = set(cfg.get("skills", []))
        else:
            self._accepted = None  # accept all

    def _passes_filter(self, skill_name: str, is_attr: bool) -> bool:
        if not self._show_attrs and is_attr:
            return False
        if self._accepted is not None and skill_name not in self._accepted:
            return False
        return True

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)
        self._subscribe(EVENT_SKILL_GAIN, self._on_skill_gain)

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        outer = QVBoxLayout(w)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        title_row = QHBoxLayout()
        self._title_label = QLabel("Skill Gains")
        self._title_label.setStyleSheet(
            f"color: {C_ACCENT}; font-weight: bold; font-size: 11px;"
        )
        title_row.addWidget(self._title_label)
        title_row.addStretch()
        reset_btn = QPushButton("Reset")
        reset_btn.setStyleSheet(_BTN_STYLE)
        reset_btn.clicked.connect(self._reset)
        title_row.addWidget(reset_btn)
        outer.addLayout(title_row)

        # Goal progress bar (hidden when goal=0)
        self._goal_bar = QProgressBar()
        self._goal_bar.setFixedHeight(14)
        self._goal_bar.setStyleSheet(_GOAL_BAR_STYLE)
        self._goal_bar.setRange(0, 1000)
        self._goal_bar.setValue(0)
        goal = self._widget_config.get("goal_total", 0.0)
        self._goal_bar.setVisible(goal > 0)
        outer.addWidget(self._goal_bar)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(1)
        self._list_layout.setContentsMargins(0, 0, 0, 0)

        self._empty_label = QLabel("No skill gains yet")
        self._empty_label.setStyleSheet("color: #555555; font-size: 10px; font-style: italic;")
        self._list_layout.addWidget(self._empty_label)

        outer.addLayout(self._list_layout)
        outer.addStretch()
        return w

    # --- Event handling ---

    def _on_skill_gain(self, data) -> None:
        if not data or self._list_layout is None:
            return

        # SkillGainEvent dataclass: .skill_name, .amount, .is_attribute
        skill = getattr(data, "skill_name", None)
        amount = float(getattr(data, "amount", 0))
        is_attr = bool(getattr(data, "is_attribute", False))

        if skill is None or amount <= 0:
            return

        if not self._passes_filter(skill, is_attr):
            return

        self._totals[skill] += amount
        if skill not in self._order:
            self._order.append(skill)

        if self._empty_label and self._empty_label.isVisible():
            self._empty_label.hide()

        if skill in self._rows:
            self._rows[skill].setText(f"{self._totals[skill]:,.4f}")
        else:
            if len(self._rows) >= _MAX_VISIBLE_SKILLS:
                return
            self._add_skill_row(skill)

        self._resort()
        self._update_goal()

    def _add_skill_row(self, skill: str) -> None:
        row_w = QWidget()
        row_w.setObjectName(f"skill_{skill}")
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        k = QLabel(skill)
        k.setStyleSheet("color: #c0c8e0; font-size: 10px;")
        row.addWidget(k, 1)

        v = QLabel(f"{self._totals[skill]:,.4f}")
        v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        v.setStyleSheet(f"color: {C_BLUE}; font-size: 10px; font-weight: bold;")
        row.addWidget(v)

        self._list_layout.addWidget(row_w)
        self._rows[skill] = v
        self._key_labels[skill] = k

    def _resort(self) -> None:
        if self._list_layout is None:
            return
        sort_by = self._widget_config.get("sort_by", "gain")

        if sort_by == "name":
            ordered = sorted(self._rows.keys())
        elif sort_by == "recent":
            ordered = list(self._order)
        else:  # gain (descending)
            ordered = sorted(self._rows.keys(), key=lambda s: self._totals[s], reverse=True)

        for i, skill in enumerate(ordered):
            key_lbl = self._key_labels.get(skill)
            if key_lbl and key_lbl.parent():
                row_w = key_lbl.parent()
                self._list_layout.removeWidget(row_w)
                self._list_layout.insertWidget(i, row_w)

    def _update_goal(self) -> None:
        goal = self._widget_config.get("goal_total", 0.0)
        if not self._goal_bar or goal <= 0:
            return
        total = sum(self._totals.values())
        pct = min(total / goal, 1.0)
        self._goal_bar.setValue(int(pct * 1000))
        self._goal_bar.setFormat(f"{total:,.2f} / {goal:,.2f}  ({pct * 100:.1f}%)")

    # --- Reset ---

    def _reset(self) -> None:
        self._totals.clear()
        self._order.clear()
        self._rows.clear()
        self._key_labels.clear()
        if self._list_layout:
            while self._list_layout.count():
                item = self._list_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.setParent(None)
                    w.deleteLater()
            if self._empty_label:
                self._list_layout.addWidget(self._empty_label)
                self._empty_label.show()
        if self._goal_bar:
            self._goal_bar.setValue(0)

    # --- Configuration ---

    def configure(self, parent: QWidget, **kwargs) -> dict | None:
        dlg = _SkillGainConfigDialog(
            self._widget_config,
            parent=parent,
            current_colspan=kwargs.get("current_colspan", self.DEFAULT_COLSPAN),
            current_rowspan=kwargs.get("current_rowspan", self.DEFAULT_ROWSPAN),
            max_cols=kwargs.get("max_cols", 50),
            max_rows=kwargs.get("max_rows", 50),
            widget_max_cols=self.MAX_COLSPAN,
            widget_max_rows=self.MAX_ROWSPAN,
        )
        return dlg.get_result() if dlg.exec() else None

    def on_config_changed(self, config: dict) -> None:
        super().on_config_changed(config)
        self._rebuild_filter()

        # Update goal bar visibility
        goal = self._widget_config.get("goal_total", 0.0)
        if self._goal_bar:
            self._goal_bar.setVisible(goal > 0)

        # Re-filter: hide rows that no longer pass, show ones that do
        # (new gains will be filtered on arrival; existing ones we leave visible
        # since they were valid when captured — reset clears them)
        self._resort()
        self._update_goal()

    def on_resize(self, width: int, height: int) -> None:
        fs = font_label(height)
        if self._title_label:
            self._title_label.setStyleSheet(
                f"color: {C_ACCENT}; font-weight: bold; font-size: {font_title(height)}px;"
            )
        for k in self._key_labels.values():
            k.setStyleSheet(f"color: #c0c8e0; font-size: {fs}px;")
        for v in self._rows.values():
            v.setStyleSheet(f"color: {C_BLUE}; font-size: {fs}px; font-weight: bold;")

    def get_config(self) -> dict:
        return dict(self._widget_config)
