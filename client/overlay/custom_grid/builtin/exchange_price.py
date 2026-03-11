"""Exchange Price widget — live exchange price for a configured item."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext

_TITLE_STYLE = "color: #00ccff; font-weight: bold; font-size: 11px;"
_NAME_STYLE = "color: #cccccc; font-size: 10px;"
_PRICE_STYLE = "color: #aaddaa; font-size: 14px; font-weight: bold;"
_MARKUP_STYLE = "color: #888888; font-size: 10px;"
_IDLE_STYLE = "color: #555555; font-size: 10px; font-style: italic;"


class ExchangePriceWidget(GridWidget):
    """Shows live exchange price (WAP) for a configured item.

    Widget config keys:
        item_id  (int): The item ID to monitor.
        item_name (str): Display name (shown before data loads).
    """

    WIDGET_ID = "com.entropianexus.exchange_price"
    DISPLAY_NAME = "Exchange Price"
    DESCRIPTION = "Shows the live exchange Weighted Average Price for a chosen item."
    MIN_WIDTH = 120
    MIN_HEIGHT = 60

    def __init__(self, config: dict):
        super().__init__(config)
        self._item_id: int | None = config.get("item_id")
        self._item_name: str = config.get("item_name", "—")
        self._price_label: QLabel | None = None
        self._markup_label: QLabel | None = None
        self._name_label: QLabel | None = None

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)
        # Connect to ExchangeStore if available
        if context.exchange_store is not None and self._item_id is not None:
            store = context.exchange_store
            try:
                store.exchange_prices_changed.connect(self._on_prices_changed)
            except Exception:
                pass

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Exchange")
        title.setStyleSheet(_TITLE_STYLE)
        layout.addWidget(title)

        self._name_label = QLabel(self._item_name)
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setStyleSheet(_NAME_STYLE)
        self._name_label.setWordWrap(True)
        layout.addWidget(self._name_label)

        self._price_label = QLabel("—")
        self._price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._price_label.setStyleSheet(_PRICE_STYLE)
        layout.addWidget(self._price_label)

        self._markup_label = QLabel("")
        self._markup_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._markup_label.setStyleSheet(_MARKUP_STYLE)
        layout.addWidget(self._markup_label)

        if self._item_id is None:
            if self._price_label:
                self._price_label.setText("No item set")
                self._price_label.setStyleSheet(_IDLE_STYLE)

        return w

    def _on_prices_changed(self, item_id: int) -> None:
        if item_id != self._item_id or self._context is None:
            return
        store = self._context.exchange_store
        if store is None:
            return
        try:
            prices = store.get_exchange_prices(item_id)
            if prices:
                wap = prices.get("wap") or prices.get("price")
                markup = prices.get("markup")
                if wap is not None and self._price_label:
                    self._price_label.setText(f"{wap:.4f} PED")
                    self._price_label.setStyleSheet(_PRICE_STYLE)
                if markup is not None and self._markup_label:
                    self._markup_label.setText(f"{markup:.1f}%")
        except Exception:
            pass

    def teardown(self) -> None:
        if self._context and self._context.exchange_store:
            try:
                self._context.exchange_store.exchange_prices_changed.disconnect(
                    self._on_prices_changed
                )
            except Exception:
                pass
        super().teardown()

    def get_config(self) -> dict:
        return {
            "item_id": self._item_id,
            "item_name": self._item_name,
        }
