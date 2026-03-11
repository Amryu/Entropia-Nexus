"""Button widget — a clickable button that publishes an EventBus event."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton

from ..grid_widget import GridWidget, WidgetContext

_BTN_STYLE = (
    "QPushButton { background: #2a3050; color: #c0d0f0; border: 1px solid #4466aa; "
    "border-radius: 4px; padding: 4px 12px; font-size: 11px; }"
    "QPushButton:hover { background: #364070; }"
    "QPushButton:pressed { background: #202840; }"
)

# Default event published on click (from constants — use a generic hotkey trigger)
_DEFAULT_EVENT = "custom_grid_button_clicked"


class ButtonWidget(GridWidget):
    """A button that publishes an EventBus event when clicked.

    Widget config keys:
        label     (str): Button label text.
        event     (str): EventBus event to publish on click.
        event_data (any): Optional data to publish with the event.
    """

    WIDGET_ID = "com.entropianexus.button"
    DISPLAY_NAME = "Button"
    DESCRIPTION = "A clickable button that publishes an EventBus event on click."
    MIN_WIDTH = 80
    MIN_HEIGHT = 40

    def __init__(self, config: dict):
        super().__init__(config)
        self._event_to_publish = config.get("event", _DEFAULT_EVENT)
        self._event_data = config.get("event_data")
        self._btn_label = config.get("label", "Click")

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 6, 6, 6)

        btn = QPushButton(self._btn_label)
        btn.setStyleSheet(_BTN_STYLE)
        btn.clicked.connect(self._on_click)
        layout.addWidget(btn)

        return w

    def _on_click(self) -> None:
        if self._context:
            self._context.event_bus.publish(self._event_to_publish, self._event_data)

    def get_config(self) -> dict:
        return {
            "label": self._btn_label,
            "event": self._event_to_publish,
            "event_data": self._event_data,
        }
