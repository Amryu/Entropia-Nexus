"""Skill Gain widget — shows recent skill gains with running total."""

from __future__ import annotations

from collections import defaultdict

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext
from ....core.constants import EVENT_SKILL_GAIN

_TITLE_STYLE = "color: #00ccff; font-weight: bold; font-size: 11px;"
_SKILL_STYLE = "color: #c0c8e0; font-size: 10px;"
_VAL_STYLE = "color: #80b8ff; font-size: 10px; font-weight: bold;"
_EMPTY_STYLE = "color: #555555; font-size: 10px; font-style: italic;"
_BTN_STYLE = (
    "QPushButton { background: #2a2a3a; color: #888; border: none; "
    "font-size: 9px; padding: 1px 4px; border-radius: 2px; }"
    "QPushButton:hover { color: #cc6666; }"
)

MAX_SKILLS = 10


class SkillGainWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.skill_gain"
    DISPLAY_NAME = "Skill Gains"
    DESCRIPTION = "Running totals of skill experience gained this session."
    DEFAULT_COLSPAN = 2
    MIN_WIDTH = 160
    MIN_HEIGHT = 60

    def __init__(self, config: dict):
        super().__init__(config)
        self._totals: dict[str, float] = defaultdict(float)
        self._rows: dict[str, QLabel] = {}  # skill_name → value label
        self._list_layout: QVBoxLayout | None = None
        self._empty_label: QLabel | None = None

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)
        self._subscribe(EVENT_SKILL_GAIN, self._on_skill_gain)

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        outer = QVBoxLayout(w)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        title_row = QHBoxLayout()
        title = QLabel("Skill Gains")
        title.setStyleSheet(_TITLE_STYLE)
        title_row.addWidget(title)
        title_row.addStretch()
        reset_btn = QPushButton("Reset")
        reset_btn.setStyleSheet(_BTN_STYLE)
        reset_btn.clicked.connect(self._reset)
        title_row.addWidget(reset_btn)
        outer.addLayout(title_row)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(1)
        self._list_layout.setContentsMargins(0, 0, 0, 0)

        self._empty_label = QLabel("No skill gains yet")
        self._empty_label.setStyleSheet(_EMPTY_STYLE)
        self._list_layout.addWidget(self._empty_label)

        outer.addLayout(self._list_layout)
        outer.addStretch()
        return w

    def _on_skill_gain(self, data) -> None:
        if not data or self._list_layout is None:
            return
        if isinstance(data, dict):
            skill = data.get("skill_name", "Unknown")
            exp = float(data.get("experience", 0))
        else:
            skill = getattr(data, "skill_name", "Unknown")
            exp = float(getattr(data, "experience", 0))

        self._totals[skill] += exp

        # Remove empty placeholder
        if self._empty_label and self._empty_label.parent() is not None:
            self._empty_label.setParent(None)

        if skill in self._rows:
            self._rows[skill].setText(f"{self._totals[skill]:,.2f}")
        else:
            # Cap at MAX_SKILLS rows
            if len(self._rows) >= MAX_SKILLS:
                return
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)

            k = QLabel(skill)
            k.setStyleSheet(_SKILL_STYLE)
            row.addWidget(k, 1)

            v = QLabel(f"{self._totals[skill]:,.2f}")
            v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            v.setStyleSheet(_VAL_STYLE)
            row.addWidget(v)

            self._list_layout.addLayout(row)
            self._rows[skill] = v

    def _reset(self) -> None:
        self._totals.clear()
        self._rows.clear()
        if self._list_layout:
            while self._list_layout.count():
                item = self._list_layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
                elif item.layout():
                    # Clean child widgets from sub-layout
                    sub = item.layout()
                    while sub.count():
                        child = sub.takeAt(0)
                        if child.widget():
                            child.widget().setParent(None)
            if self._empty_label:
                self._list_layout.addWidget(self._empty_label)
                self._empty_label.setParent(self._list_layout.parentWidget())
