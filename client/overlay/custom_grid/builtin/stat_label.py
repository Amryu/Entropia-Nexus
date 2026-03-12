"""Stat Label widget — configurable label showing a key/value pair."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext
from ._common import font_big, font_label, C_DIM


class StatLabelWidget(GridWidget):
    """A simple label widget displaying a configurable key/value pair.

    Widget config keys:
        label  (str): The label/key text shown above the value.
        value  (str): Initial value text.
        color  (str): Optional CSS color for the value (e.g. "#00ff88").
    """

    WIDGET_ID = "com.entropianexus.stat_label"
    DISPLAY_NAME = "Stat Label"
    DESCRIPTION = "A simple key/value label. Useful as a static display or custom indicator."
    DEFAULT_COLSPAN = 3
    DEFAULT_ROWSPAN = 2
    MIN_WIDTH = 60
    MIN_HEIGHT = 36

    def __init__(self, config: dict):
        super().__init__(config)
        self._key_label: QLabel | None = None
        self._val_label: QLabel | None = None
        self._val_color = config.get("color", "#e0e0e0")

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)

    def create_widget(self, parent: QWidget) -> QWidget:
        label_text = self._widget_config.get("label", "Stat")
        value_text = self._widget_config.get("value", "—")

        w = QWidget(parent)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(1)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._key_label = QLabel(label_text)
        self._key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._key_label.setStyleSheet(f"color: {C_DIM}; font-size: 10px;")
        layout.addWidget(self._key_label)

        self._val_label = QLabel(value_text)
        self._val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._val_label.setStyleSheet(
            f"color: {self._val_color}; font-size: 14px; font-weight: bold;"
        )
        layout.addWidget(self._val_label)

        return w

    def set_value(self, text: str) -> None:
        """Update the displayed value text programmatically."""
        if self._val_label:
            self._val_label.setText(text)

    def on_resize(self, width: int, height: int) -> None:
        if self._key_label:
            self._key_label.setStyleSheet(
                f"color: {C_DIM}; font-size: {font_label(height)}px;"
            )
        if self._val_label:
            self._val_label.setStyleSheet(
                f"color: {self._val_color}; font-size: {font_big(height)}px; font-weight: bold;"
            )

    def get_config(self) -> dict:
        return {
            "label": self._widget_config.get("label", "Stat"),
            "value": self._val_label.text() if self._val_label else "—",
            "color": self._val_color,
        }
