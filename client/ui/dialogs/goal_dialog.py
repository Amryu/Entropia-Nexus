"""Dialog for creating or editing a skill/profession goal."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QDoubleSpinBox, QPushButton, QRadioButton, QButtonGroup, QFrame,
)
from PyQt6.QtCore import Qt

from ..theme import SECONDARY, TEXT_MUTED, ACCENT, BORDER

RANKLESS_CATEGORIES = {"Attributes", "Social"}


class GoalDialog(QDialog):
    """Modal dialog for adding or editing a skill/profession goal."""

    def __init__(
        self, *,
        skill_metadata: list[dict],
        professions: list[dict],
        skill_values: dict[str, float],
        profession_levels: dict[str, float],
        rank_thresholds: list[dict],
        existing_goal: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._skill_metadata = skill_metadata
        self._professions = professions
        self._skill_values = skill_values
        self._profession_levels = profession_levels
        self._rank_thresholds = sorted(
            rank_thresholds, key=lambda r: r.get("threshold", 0)
        )
        self._name_to_category = {s["Name"]: s.get("Category", "") for s in skill_metadata}
        self._existing_goal = existing_goal
        self._result: dict | None = None

        editing = existing_goal is not None
        self.setWindowTitle("Edit Goal" if editing else "Add Goal")
        self.setMinimumWidth(380)
        self.setStyleSheet(f"QDialog {{ background-color: {SECONDARY}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Goal type
        type_label = QLabel("Goal Type")
        type_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(type_label)

        type_row = QHBoxLayout()
        self._type_group = QButtonGroup(self)
        self._radio_skill = QRadioButton("Skill Points")
        self._radio_prof = QRadioButton("Profession Level")
        self._type_group.addButton(self._radio_skill, 0)
        self._type_group.addButton(self._radio_prof, 1)
        type_row.addWidget(self._radio_skill)
        type_row.addWidget(self._radio_prof)
        type_row.addStretch()
        layout.addLayout(type_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(sep)

        # Target name
        name_label = QLabel("Target")
        name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(name_label)

        self._target_combo = QComboBox()
        self._target_combo.setEditable(True)
        self._target_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._target_combo.currentTextChanged.connect(self._on_target_changed)
        layout.addWidget(self._target_combo)

        # Current value display
        self._current_label = QLabel("")
        self._current_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self._current_label)

        # Starting point section
        start_label = QLabel("Starting Point")
        start_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(start_label)

        start_row = QHBoxLayout()
        self._start_spin = QDoubleSpinBox()
        self._start_spin.setDecimals(2)
        self._start_spin.setMinimum(0.0)
        self._start_spin.setMaximum(999999.99)
        start_row.addWidget(self._start_spin, 1)

        self._reset_start_btn = QPushButton("Reset to Current")
        self._reset_start_btn.setFixedHeight(26)
        self._reset_start_btn.clicked.connect(self._on_reset_start)
        start_row.addWidget(self._reset_start_btn)
        layout.addLayout(start_row)

        self._start_hint = QLabel("")
        self._start_hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self._start_hint)

        # Target value
        val_label = QLabel("Target Value")
        val_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(val_label)

        val_row = QHBoxLayout()
        self._target_spin = QDoubleSpinBox()
        self._target_spin.setDecimals(2)
        self._target_spin.setMinimum(0.01)
        self._target_spin.setMaximum(999999.99)
        val_row.addWidget(self._target_spin, 1)

        # Rank shortcut (only for skill type)
        self._rank_combo = QComboBox()
        self._rank_combo.addItem("— or pick rank —")
        for rank in self._rank_thresholds:
            self._rank_combo.addItem(
                f"{rank['name']} ({rank['threshold']:,})",
                rank["threshold"],
            )
        self._rank_combo.currentIndexChanged.connect(self._on_rank_selected)
        val_row.addWidget(self._rank_combo)
        layout.addLayout(val_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("Save" if editing else "Add Goal")
        ok_btn.setObjectName("accentButton")
        ok_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        # Wire type toggle
        self._type_group.idToggled.connect(self._on_type_changed)

        # Populate from existing goal or defaults
        if existing_goal:
            is_prof = existing_goal["goal_type"] == "profession_level"
            (self._radio_prof if is_prof else self._radio_skill).setChecked(True)
            self._on_type_changed(1 if is_prof else 0, True)
            self._target_combo.setCurrentText(existing_goal["target_name"])
            self._target_spin.setValue(existing_goal["target_value"])
            self._start_spin.setValue(existing_goal.get("start_value") or 0)

            # Lock type and target — only target value and start point can change
            self._radio_skill.setEnabled(False)
            self._radio_prof.setEnabled(False)
            self._target_combo.setEnabled(False)

            self._update_start_hint()
        else:
            self._radio_skill.setChecked(True)
            self._on_type_changed(0, True)

    def _update_start_hint(self):
        """Update the starting point hint label with the current value."""
        name = self._target_combo.currentText().strip()
        if not name:
            self._start_hint.setText("")
            return
        is_prof = self._radio_prof.isChecked()
        if is_prof:
            current = self._profession_levels.get(name, 0)
            self._start_hint.setText(f"Current level: {current:.1f}")
        else:
            current = self._skill_values.get(name, 0)
            self._start_hint.setText(f"Current: {current:,.2f} points")

    def _on_reset_start(self):
        """Reset the starting point to the current value."""
        name = self._target_combo.currentText().strip()
        if not name:
            return
        is_prof = self._radio_prof.isChecked()
        if is_prof:
            current = self._profession_levels.get(name, 0)
        else:
            current = self._skill_values.get(name, 0)
        self._start_spin.setValue(current)

    def _on_type_changed(self, button_id: int, checked: bool):
        if not checked:
            return
        is_prof = button_id == 1
        self._rank_combo.setVisible(not is_prof)

        self._target_combo.blockSignals(True)
        self._target_combo.clear()

        if is_prof:
            names = sorted(p["Name"] for p in self._professions if p.get("Name"))
            self._target_combo.addItems(names)
            self._target_spin.setDecimals(1)
            self._target_spin.setSingleStep(1.0)
            self._start_spin.setDecimals(1)
            self._start_spin.setSingleStep(1.0)
        else:
            names = sorted(
                s["Name"] for s in self._skill_metadata
                if s.get("Name") and not s.get("IsHidden")
            )
            self._target_combo.addItems(names)
            self._target_spin.setDecimals(2)
            self._target_spin.setSingleStep(10.0)
            self._start_spin.setDecimals(2)
            self._start_spin.setSingleStep(10.0)

        self._target_combo.blockSignals(False)
        if names:
            self._target_combo.setCurrentIndex(0)
            self._on_target_changed(names[0])

    def _on_target_changed(self, name: str):
        is_prof = self._radio_prof.isChecked()
        if is_prof:
            current = self._profession_levels.get(name, 0)
            self._current_label.setText(f"Current level: {current:.1f}")
        else:
            current = self._skill_values.get(name, 0)
            category = self._name_to_category.get(name, "")
            is_rankless = category in RANKLESS_CATEGORIES
            self._rank_combo.setVisible(not is_rankless)
            rank = "" if is_rankless else self._rank_for_value(current)
            rank_text = f" ({rank})" if rank else ""
            self._current_label.setText(
                f"Current: {current:,.2f} points{rank_text}"
            )
        # For new goals, set starting point to current value on target change
        if not self._existing_goal:
            self._start_spin.setValue(current)
        self._update_start_hint()

    def _rank_for_value(self, points: float) -> str:
        """Get rank name for a given point value."""
        if not self._rank_thresholds or points <= 0:
            return ""
        rank_name = self._rank_thresholds[0]["name"]
        for rank in self._rank_thresholds:
            if points >= rank["threshold"]:
                rank_name = rank["name"]
            else:
                break
        return rank_name

    def _on_rank_selected(self, index: int):
        if index <= 0:
            return
        threshold = self._rank_combo.itemData(index)
        if threshold is not None:
            self._target_spin.setValue(float(threshold))

    def _on_accept(self):
        name = self._target_combo.currentText().strip()
        if not name:
            return

        is_prof = self._radio_prof.isChecked()
        goal_type = "profession_level" if is_prof else "skill_points"
        target_value = self._target_spin.value()
        start_value = self._start_spin.value()

        self._result = {
            "goal_type": goal_type,
            "target_name": name,
            "target_value": target_value,
            "start_value": start_value,
        }
        self.accept()

    def get_goal(self) -> dict | None:
        """Returns goal dict if user clicked OK, None if cancelled."""
        return self._result
