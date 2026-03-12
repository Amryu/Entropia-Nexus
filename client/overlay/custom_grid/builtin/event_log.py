"""Event Log widget — scrolling feed of recent EventBus events."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext
from ....core.constants import (
    EVENT_SKILL_GAIN,
    EVENT_GLOBAL,
    EVENT_ENHANCER_BREAK,
    EVENT_TIER_INCREASE,
    EVENT_OWN_GLOBAL,
)
from ._common import font_title, C_ACCENT

MAX_ENTRIES = 30

_DEFAULT_EVENTS = [
    EVENT_SKILL_GAIN,
    EVENT_GLOBAL,
    EVENT_ENHANCER_BREAK,
    EVENT_TIER_INCREASE,
    EVENT_OWN_GLOBAL,
]
_EVENT_LABELS = {
    EVENT_SKILL_GAIN:    "Skill",
    EVENT_GLOBAL:        "Global",
    EVENT_ENHANCER_BREAK:"Enhancer",
    EVENT_TIER_INCREASE: "Tier",
    EVENT_OWN_GLOBAL:    "Own Global",
}


class EventLogWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.event_log"
    DISPLAY_NAME = "Event Log"
    DESCRIPTION = "Scrolling feed of recent game events (skill gains, globals, enhancer breaks, etc.)."
    DEFAULT_COLSPAN = 6
    DEFAULT_ROWSPAN = 5
    MIN_WIDTH = 120
    MIN_HEIGHT = 60

    def __init__(self, config: dict):
        super().__init__(config)
        self._list_layout: QVBoxLayout | None = None
        self._empty_label: QLabel | None = None
        self._title_label: QLabel | None = None

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)
        for evt in _DEFAULT_EVENTS:
            self._subscribe(evt, lambda data, e=evt: self._on_event(e, data))

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        outer = QVBoxLayout(w)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        self._title_label = QLabel("Events")
        self._title_label.setStyleSheet(
            f"color: {C_ACCENT}; font-weight: bold; font-size: 11px;"
        )
        outer.addWidget(self._title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:vertical { width: 4px; background: #1a1a28; }"
            "QScrollBar::handle:vertical { background: #444466; border-radius: 2px; }"
        )

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(inner)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(1)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._empty_label = QLabel("No events yet")
        self._empty_label.setStyleSheet("color: #555555; font-size: 10px; font-style: italic;")
        self._list_layout.addWidget(self._empty_label)

        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        return w

    def _on_event(self, event_type: str, data) -> None:
        if self._list_layout is None:
            return
        label = _EVENT_LABELS.get(event_type, event_type)
        text  = self._format_event(event_type, data)
        ts    = datetime.now().strftime("%H:%M:%S")
        self._add_entry(label, text, ts)

    def _format_event(self, event_type: str, data) -> str:
        if data is None:
            return ""
        if event_type == EVENT_SKILL_GAIN:
            skill = getattr(data, "skill_name", None) or (data.get("skill_name") if isinstance(data, dict) else "")
            exp   = getattr(data, "experience", None) or (data.get("experience") if isinstance(data, dict) else 0)
            return f"+{exp} {skill}" if skill else str(data)
        if event_type in (EVENT_GLOBAL, EVENT_OWN_GLOBAL):
            if isinstance(data, dict):
                name = data.get("player") or data.get("name", "")
                val  = data.get("value", 0)
                item = data.get("item") or data.get("creature", "")
                return f"{name}: {item} {val:.0f} PED" if val else str(data)
        if event_type == EVENT_ENHANCER_BREAK:
            if isinstance(data, dict):
                return data.get("enhancer_name", str(data))
        if event_type == EVENT_TIER_INCREASE:
            if isinstance(data, dict):
                return f"{data.get('item_name', '')} → Tier {data.get('tier', '')}"
        return str(data)[:60] if data else ""

    def _add_entry(self, label: str, text: str, ts: str) -> None:
        if self._list_layout is None:
            return
        if self._empty_label and self._empty_label.parent() is not None:
            self._empty_label.setParent(None)

        while self._list_layout.count() >= MAX_ENTRIES:
            item = self._list_layout.takeAt(self._list_layout.count() - 1)
            if item and item.widget():
                item.widget().deleteLater()

        row = QWidget()
        row.setStyleSheet("background: transparent;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)

        ts_lbl = QLabel(ts)
        ts_lbl.setStyleSheet("color: #555566; font-size: 9px;")
        ts_lbl.setFixedWidth(44)
        rl.addWidget(ts_lbl)

        lbl = QLabel(f"[{label}]")
        lbl.setStyleSheet("color: #4488cc; font-size: 9px;")
        lbl.setFixedWidth(56)
        rl.addWidget(lbl)

        txt = QLabel(text)
        txt.setStyleSheet("color: #c0c0c0; font-size: 10px;")
        rl.addWidget(txt, 1)

        self._list_layout.insertWidget(0, row)

    def on_resize(self, width: int, height: int) -> None:
        if self._title_label:
            self._title_label.setStyleSheet(
                f"color: {C_ACCENT}; font-weight: bold; font-size: {font_title(height)}px;"
            )
