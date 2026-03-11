"""GridWidget base class and WidgetContext for CustomGridOverlay."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6.QtWidgets import QWidget

if TYPE_CHECKING:
    from ...core.event_bus import EventBus
    from ...api.data_client import DataClient
    from ...exchange.exchange_store import ExchangeStore


class WidgetContext:
    """Injected dependencies available to all GridWidgets."""

    def __init__(
        self,
        *,
        event_bus: 'EventBus',
        data_client: 'DataClient | None' = None,
        exchange_store: 'ExchangeStore | None' = None,
        hunt_tracker=None,
        config=None,
    ):
        self.event_bus = event_bus
        self.data_client = data_client
        self.exchange_store = exchange_store
        self.hunt_tracker = hunt_tracker  # May be None if hunt module is disabled
        self.config = config


class GridWidget:
    """Abstract base class for all CustomGridOverlay widgets.

    Subclasses must implement ``create_widget(parent)``.
    Use ``_subscribe()`` inside ``setup()`` to subscribe to EventBus events;
    all subscriptions are automatically cleaned up by ``teardown()``.

    Example::

        class MyWidget(GridWidget):
            WIDGET_ID = "com.example.my_widget"
            DISPLAY_NAME = "My Widget"
            DESCRIPTION = "Shows something useful."
            MIN_WIDTH = 120
            MIN_HEIGHT = 50

            def setup(self, context):
                super().setup(context)
                self._label = None
                self._subscribe(EVENT_LOOT_GROUP, self._on_loot)

            def create_widget(self, parent):
                from PyQt6.QtWidgets import QLabel
                self._label = QLabel("Waiting...", parent)
                self._label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
                return self._label

            def _on_loot(self, data):
                if self._label:
                    self._label.setText(f"Loot: {data.get('total_ped', 0):.2f} PED")
    """

    # Class-level metadata — override in subclasses
    WIDGET_ID: str = "com.example.widget"
    DISPLAY_NAME: str = "Widget"
    DESCRIPTION: str = ""
    DEFAULT_COLSPAN: int = 1
    DEFAULT_ROWSPAN: int = 1
    MIN_WIDTH: int = 80
    MIN_HEIGHT: int = 40

    def __init__(self, config: dict):
        self._widget_config: dict = config or {}
        self._context: WidgetContext | None = None
        self._subscriptions: list[tuple[str, Callable]] = []

    # --- Lifecycle ---

    def setup(self, context: WidgetContext) -> None:
        """Called after the widget is placed in the grid.

        Subscribe to EventBus events here via ``self._subscribe()``.
        Always call ``super().setup(context)`` first.
        """
        self._context = context

    def create_widget(self, parent: QWidget) -> QWidget:
        """Build and return the visual QWidget. Must be overridden."""
        raise NotImplementedError(
            f"{type(self).__name__}.create_widget() not implemented"
        )

    def teardown(self) -> None:
        """Called before the widget is removed from the grid.

        Unsubscribes all EventBus listeners registered via ``_subscribe()``.
        Override to add extra cleanup, but always call ``super().teardown()``.
        """
        for event_type, cb in self._subscriptions:
            try:
                if self._context:
                    self._context.event_bus.unsubscribe(event_type, cb)
            except Exception:
                pass
        self._subscriptions.clear()
        self._context = None

    def get_config(self) -> dict:
        """Return serializable config dict for persistence.

        Override to persist widget-specific settings across sessions.
        """
        return {}

    def on_resize(self, width: int, height: int) -> None:
        """Called when the cell containing this widget is resized.

        Override to react to size changes.
        """

    # --- EventBus subscription helper ---

    def _subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe to an EventBus event and track it for teardown."""
        if self._context is None:
            raise RuntimeError(
                "_subscribe() called before setup() — call super().setup(context) first"
            )
        self._context.event_bus.subscribe(event_type, callback)
        self._subscriptions.append((event_type, callback))
