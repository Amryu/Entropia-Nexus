"""Exchange Price widget — live exchange price for a configured item."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext
from ._common import font_value, font_label, font_title, C_ACCENT, C_GREEN, C_DIM


class ExchangePriceWidget(GridWidget):
    """Shows live exchange price (WAP) for a configured item.

    Widget config keys:
        item_id   (int): The item ID to monitor.
        item_name (str): Display name (shown before data loads).
    """

    WIDGET_ID = "com.entropianexus.exchange_price"
    DISPLAY_NAME = "Exchange Price"
    DESCRIPTION = "Shows the live exchange Weighted Average Price for a chosen item."
    DEFAULT_COLSPAN = 4
    DEFAULT_ROWSPAN = 3
    MIN_WIDTH = 80
    MIN_HEIGHT = 40

    def __init__(self, config: dict):
        super().__init__(config)
        self._item_id: int | None = config.get("item_id")
        self._item_name: str = config.get("item_name", "—")
        self._title_label: QLabel | None = None
        self._name_label: QLabel | None = None
        self._price_label: QLabel | None = None
        self._markup_label: QLabel | None = None

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)
        if context.exchange_store is not None and self._item_id is not None:
            try:
                context.exchange_store.exchange_prices_changed.connect(
                    self._on_prices_changed
                )
            except Exception:
                pass

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title_label = QLabel("Exchange")
        self._title_label.setStyleSheet(
            f"color: {C_ACCENT}; font-weight: bold; font-size: 11px;"
        )
        layout.addWidget(self._title_label)

        self._name_label = QLabel(self._item_name)
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setStyleSheet(f"color: #cccccc; font-size: 10px;")
        self._name_label.setWordWrap(True)
        layout.addWidget(self._name_label)

        self._price_label = QLabel("—" if self._item_id is not None else "No item set")
        self._price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._price_label.setStyleSheet(
            f"color: {C_GREEN}; font-size: 14px; font-weight: bold;"
        )
        layout.addWidget(self._price_label)

        self._markup_label = QLabel("")
        self._markup_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._markup_label.setStyleSheet(f"color: {C_DIM}; font-size: 10px;")
        layout.addWidget(self._markup_label)

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
                    self._price_label.setStyleSheet(
                        f"color: {C_GREEN}; font-size: 14px; font-weight: bold;"
                    )
                if markup is not None and self._markup_label:
                    self._markup_label.setText(f"{markup:.1f}%")
        except Exception:
            pass

    def on_resize(self, width: int, height: int) -> None:
        fs_price = font_value(height)
        fs_lbl   = font_label(height)
        fs_ttl   = font_title(height)
        if self._title_label:
            self._title_label.setStyleSheet(
                f"color: {C_ACCENT}; font-weight: bold; font-size: {fs_ttl}px;"
            )
        if self._name_label:
            self._name_label.setStyleSheet(f"color: #cccccc; font-size: {fs_lbl}px;")
        if self._price_label:
            # Preserve colour
            current = self._price_label.styleSheet()
            color = C_GREEN if C_GREEN in current else "#999999"
            self._price_label.setStyleSheet(
                f"color: {color}; font-size: {fs_price}px; font-weight: bold;"
            )
        if self._markup_label:
            self._markup_label.setStyleSheet(f"color: {C_DIM}; font-size: {fs_lbl}px;")

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
        return {"item_id": self._item_id, "item_name": self._item_name}
