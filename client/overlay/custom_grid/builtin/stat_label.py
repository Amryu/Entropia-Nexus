"""Stat Label widget — configurable label showing a key/value pair."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext

_KEY_STYLE = "color: #888888; font-size: 10px;"
_VAL_STYLE = "color: #e0e0e0; font-size: 14px; font-weight: bold;"


class StatLabelWidget(GridWidget):
    """A simple label widget displaying a configurable key/value pair.

    The value can be updated at runtime from other widgets or external code
    by calling ``set_value()``.  By itself it shows static configured text.

    Widget config keys:
        label  (str): The label/key text shown above the value.
        value  (str): Initial value text.
        color  (str): Optional CSS color for the value (e.g. "#00ff88").
    """

    WIDGET_ID = "com.entropianexus.stat_label"
    DISPLAY_NAME = "Stat Label"
    DESCRIPTION = "A simple key/value label. Useful as a static display or custom indicator."
    MIN_WIDTH = 80
    MIN_HEIGHT = 44

    def __init__(self, config: dict):
        super().__init__(config)
        self._val_label: QLabel | None = None

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)

    def create_widget(self, parent: QWidget) -> QWidget:
        label_text = self._widget_config.get("label", "Stat")
        value_text = self._widget_config.get("value", "—")
        color = self._widget_config.get("color", "#e0e0e0")

        w = QWidget(parent)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(1)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        key_lbl = QLabel(label_text)
        key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        key_lbl.setStyleSheet(_KEY_STYLE)
        layout.addWidget(key_lbl)

        self._val_label = QLabel(value_text)
        self._val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._val_label.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: bold;"
        )
        layout.addWidget(self._val_label)

        return w

    def set_value(self, text: str) -> None:
        """Update the displayed value text programmatically."""
        if self._val_label:
            self._val_label.setText(text)

    def get_config(self) -> dict:
        return {
            "label": self._widget_config.get("label", "Stat"),
            "value": self._val_label.text() if self._val_label else "—",
            "color": self._widget_config.get("color", "#e0e0e0"),
        }
