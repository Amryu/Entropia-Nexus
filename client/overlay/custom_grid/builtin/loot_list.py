"""Loot List widget — scrolling feed of recent loot drops."""

from __future__ import annotations

from collections import deque

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext
from ....core.constants import EVENT_LOOT_GROUP

_TITLE_STYLE = "color: #00ccff; font-weight: bold; font-size: 11px;"
_ITEM_STYLE = "color: #e0e0e0; font-size: 10px;"
_VALUE_STYLE = "color: #aaddaa; font-size: 10px;"
_EMPTY_STYLE = "color: #666666; font-size: 10px; font-style: italic;"

MAX_ENTRIES = 20


class LootListWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.loot_list"
    DISPLAY_NAME = "Loot List"
    DESCRIPTION = "Shows a scrolling feed of the most recent loot drops."
    DEFAULT_COLSPAN = 2
    MIN_WIDTH = 160
    MIN_HEIGHT = 80

    def __init__(self, config: dict):
        super().__init__(config)
        self._entries: deque[str] = deque(maxlen=MAX_ENTRIES)
        self._list_widget: QWidget | None = None
        self._list_layout: QVBoxLayout | None = None

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)
        self._subscribe(EVENT_LOOT_GROUP, self._on_loot)

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        outer = QVBoxLayout(w)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        title = QLabel("Loot")
        title.setStyleSheet(_TITLE_STYLE)
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:vertical { width: 4px; background: #1a1a28; }"
            "QScrollBar::handle:vertical { background: #444466; border-radius: 2px; }"
        )

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(1)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._empty_label = QLabel("No loot yet")
        self._empty_label.setStyleSheet(_EMPTY_STYLE)
        self._list_layout.addWidget(self._empty_label)

        scroll.setWidget(self._list_widget)
        outer.addWidget(scroll, 1)
        return w

    def _on_loot(self, data) -> None:
        if not data or self._list_layout is None:
            return
        items = data.get("items", [])
        for item in items:
            name = item.get("item_name", "Unknown")
            qty = item.get("quantity", 1)
            value = item.get("value_ped", 0.0)
            self._add_entry(name, qty, value)

    def _add_entry(self, name: str, qty: int, value: float) -> None:
        if self._list_layout is None:
            return

        # Remove empty placeholder
        if self._empty_label.parent() is not None:
            self._empty_label.setParent(None)

        # Trim oldest if over max
        while self._list_layout.count() >= MAX_ENTRIES:
            item = self._list_layout.takeAt(self._list_layout.count() - 1)
            if item and item.widget():
                item.widget().deleteLater()

        row = QWidget()
        row.setStyleSheet("background: transparent;")
        from PyQt6.QtWidgets import QHBoxLayout
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)

        name_text = f"{name}" if qty <= 1 else f"{name} x{qty}"
        name_lbl = QLabel(name_text)
        name_lbl.setStyleSheet(_ITEM_STYLE)
        name_lbl.setWordWrap(False)
        rl.addWidget(name_lbl, 1)

        val_lbl = QLabel(f"{value:.2f}")
        val_lbl.setStyleSheet(_VALUE_STYLE)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        rl.addWidget(val_lbl)

        # Insert at top (most recent first)
        self._list_layout.insertWidget(0, row)
