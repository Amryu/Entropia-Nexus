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

    Configuration
    -------------
    Override ``configure(parent, **kwargs)`` to open a settings dialog.
    Return a dict on accept (may include ``"__slot__"`` with colspan/rowspan
    overrides); return ``None`` to cancel.

    Override ``on_config_changed(config)`` to apply a new config dict to the
    live widget.  The base implementation merges the dict into
    ``_widget_config``; call ``super()`` to use this behaviour.

    Resize constraints
    ------------------
    Set ``MIN_COLSPAN`` / ``MIN_ROWSPAN`` and ``MAX_COLSPAN`` / ``MAX_ROWSPAN``
    (0 = unbounded) on the subclass to constrain edge-drag resizing.
    """

    # Class-level metadata — override in subclasses
    WIDGET_ID: str = "com.example.widget"
    DISPLAY_NAME: str = "Widget"
    DESCRIPTION: str = ""
    DEFAULT_COLSPAN: int = 1
    DEFAULT_ROWSPAN: int = 1
    MIN_WIDTH: int = 80
    MIN_HEIGHT: int = 40

    # Resize constraints (in tiles; 0 = unbounded)
    MIN_COLSPAN: int = 1
    MIN_ROWSPAN: int = 1
    MAX_COLSPAN: int = 0
    MAX_ROWSPAN: int = 0

    def __init__(self, config: dict):
        self._widget_config: dict = dict(config) if config else {}
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
        return dict(self._widget_config)

    def on_resize(self, width: int, height: int) -> None:
        """Called when the cell containing this widget is resized."""

    # --- Configuration ---

    def configure(self, parent: QWidget, **kwargs) -> dict | None:
        """Open a configuration dialog.

        ``kwargs`` contains layout hints from the overlay:
          - ``current_colspan`` / ``current_rowspan``: current slot size
          - ``max_cols`` / ``max_rows``: maximum allowed values

        Return a config dict on accept (may include a ``"__slot__"`` key with
        ``colspan`` and/or ``rowspan`` to request a layout change), or
        ``None`` to cancel.

        The default implementation returns ``None`` (no config dialog).
        """
        return None

    def on_config_changed(self, config: dict) -> None:
        """Apply a new configuration dict to the live widget.

        The overlay calls this after ``configure()`` returns a non-None result.
        The base implementation merges the dict into ``_widget_config``.
        Subclasses should call ``super()`` then refresh their display.
        """
        self._widget_config.update(config)

    # --- EventBus subscription helper ---

    def _subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe to an EventBus event and track it for teardown."""
        if self._context is None:
            raise RuntimeError(
                "_subscribe() called before setup() — call super().setup(context) first"
            )
        self._context.event_bus.subscribe(event_type, callback)
        self._subscriptions.append((event_type, callback))

    def _unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe a previously registered callback and remove from tracking."""
        try:
            if self._context:
                self._context.event_bus.unsubscribe(event_type, callback)
        except Exception:
            pass
        self._subscriptions = [
            (e, c) for e, c in self._subscriptions
            if not (e == event_type and c is callback)
        ]
