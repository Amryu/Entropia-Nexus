"""Shared exchange data store — used by both overlay and page."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ..core.logger import get_logger
from .order_utils import enrich_orders

if TYPE_CHECKING:
    from ..api.nexus_client import NexusClient

log = get_logger("ExchangeStore")


class ExchangeStore(QObject):
    """Central data store for exchange items, orders, inventory, and trade requests.

    Shared singleton between ExchangeOverlay and ExchangePage.
    Uses background threads for network calls and emits signals on the main thread.
    Consumer-counted polling: starts when any consumer connects, stops when all disconnect.
    """

    # Signals
    items_changed = pyqtSignal()
    my_orders_changed = pyqtSignal()
    inventory_changed = pyqtSignal()
    trade_requests_changed = pyqtSignal()
    item_orders_changed = pyqtSignal(int)        # item_id
    loading_changed = pyqtSignal(str, bool)       # (what, is_loading)
    error_occurred = pyqtSignal(str, str)          # (context, message)

    def __init__(self, nexus_client: NexusClient):
        super().__init__()
        self._client = nexus_client

        # Data
        self._items: list[dict] = []
        self._item_lookup: dict[int, dict] = {}
        self._my_orders: list[dict] = []
        self._inventory: list[dict] = []
        self._trade_requests: list[dict] = []
        self._item_orders_cache: dict[int, dict] = {}

        # Polling
        self._consumer_count = 0
        self._orders_timer = QTimer()
        self._orders_timer.timeout.connect(self._poll_my_orders)
        self._inventory_timer = QTimer()
        self._inventory_timer.timeout.connect(self._poll_inventory)
        self._trades_timer = QTimer()
        self._trades_timer.timeout.connect(self._poll_trade_requests)

        # Loading states
        self._loading: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def items(self) -> list[dict]:
        return self._items

    @property
    def item_lookup(self) -> dict[int, dict]:
        return self._item_lookup

    @property
    def my_orders(self) -> list[dict]:
        return self._my_orders

    @property
    def inventory(self) -> list[dict]:
        return self._inventory

    @property
    def trade_requests(self) -> list[dict]:
        return self._trade_requests

    def get_item_orders(self, item_id: int) -> dict | None:
        """Get cached order book for an item."""
        return self._item_orders_cache.get(item_id)

    def is_loading(self, what: str) -> bool:
        return self._loading.get(what, False)

    # ------------------------------------------------------------------
    # Loading — items (public, no auth)
    # ------------------------------------------------------------------

    def load_items(self):
        """Fetch exchange items (public, no auth). Call once on startup."""
        self._set_loading("items", True)

        def _do():
            try:
                items = self._client.get_exchange_items()
                self._items = items or []
                self._item_lookup = {item['i']: item for item in self._items if 'i' in item}
                self._set_loading("items", False)
                self.items_changed.emit()
                # Re-enrich orders that were loaded before items were available
                if self._my_orders:
                    raw = [{k: v for k, v in o.items() if not k.startswith('_')} for o in self._my_orders]
                    self._my_orders = enrich_orders(raw, self._item_lookup)
                    self.my_orders_changed.emit()
                # Re-emit inventory_changed so names resolve now that items are available
                if self._inventory:
                    self.inventory_changed.emit()
            except Exception as e:
                log.error("Failed to load exchange items: %s", e)
                self._set_loading("items", False)
                self.error_occurred.emit("items", str(e))

        threading.Thread(target=_do, daemon=True).start()

    # ------------------------------------------------------------------
    # Loading — auth-required data
    # ------------------------------------------------------------------

    def load_my_orders(self):
        """Fetch user's exchange orders (requires auth)."""
        if not self._client.is_authenticated():
            return
        self._set_loading("orders", True)

        def _do():
            try:
                data = self._client.get_my_orders()
                if data is not None:
                    self._my_orders = enrich_orders(
                        data if isinstance(data, list) else [],
                        self._item_lookup,
                    )
                self._set_loading("orders", False)
                self.my_orders_changed.emit()
            except Exception as e:
                log.error("Failed to load my orders: %s", e)
                self._set_loading("orders", False)
                self.error_occurred.emit("orders", str(e))

        threading.Thread(target=_do, daemon=True).start()

    def load_inventory(self):
        """Fetch user's inventory (requires auth)."""
        if not self._client.is_authenticated():
            return
        self._set_loading("inventory", True)

        def _do():
            try:
                data = self._client.get_inventory()
                if data is not None:
                    self._inventory = data if isinstance(data, list) else []
                self._set_loading("inventory", False)
                self.inventory_changed.emit()
            except Exception as e:
                log.error("Failed to load inventory: %s", e)
                self._set_loading("inventory", False)
                self.error_occurred.emit("inventory", str(e))

        threading.Thread(target=_do, daemon=True).start()

    def load_trade_requests(self):
        """Fetch user's trade requests (requires auth)."""
        if not self._client.is_authenticated():
            return
        self._set_loading("trades", True)

        def _do():
            try:
                data = self._client.get_trade_requests()
                if data is not None:
                    self._trade_requests = data if isinstance(data, list) else []
                self._set_loading("trades", False)
                self.trade_requests_changed.emit()
            except Exception as e:
                log.error("Failed to load trade requests: %s", e)
                self._set_loading("trades", False)
                self.error_occurred.emit("trades", str(e))

        threading.Thread(target=_do, daemon=True).start()

    # ------------------------------------------------------------------
    # Loading — item order book (public)
    # ------------------------------------------------------------------

    def load_item_orders(self, item_id: int):
        """Fetch order book for a specific item (public, no auth)."""
        self._set_loading(f"item_orders_{item_id}", True)

        def _do():
            try:
                data = self._client.get_item_orders(item_id)
                if data is not None:
                    # Enrich buy and sell orders
                    buy = enrich_orders(data.get('buy', []), self._item_lookup)
                    sell = enrich_orders(data.get('sell', []), self._item_lookup)
                    self._item_orders_cache[item_id] = {'buy': buy, 'sell': sell}
                self._set_loading(f"item_orders_{item_id}", False)
                self.item_orders_changed.emit(item_id)
            except Exception as e:
                log.error("Failed to load item orders %s: %s", item_id, e)
                self._set_loading(f"item_orders_{item_id}", False)
                self.error_occurred.emit("item_orders", str(e))

        threading.Thread(target=_do, daemon=True).start()

    # ------------------------------------------------------------------
    # Write operations (auth required)
    # ------------------------------------------------------------------

    def create_order(self, data: dict, callback=None):
        """Create a new exchange order in a background thread.

        callback(success: bool, result_or_error: dict|str)
        """
        def _do():
            try:
                result = self._client.create_order(data)
                if result:
                    # Refresh orders
                    self._poll_my_orders()
                    if callback:
                        callback(True, result)
                else:
                    if callback:
                        callback(False, "No response from server")
            except Exception as e:
                error_msg = self._extract_error(e)
                log.error("Failed to create order: %s", error_msg)
                if callback:
                    callback(False, error_msg)

        threading.Thread(target=_do, daemon=True).start()

    def edit_order(self, order_id: int, data: dict, callback=None):
        """Edit an exchange order in a background thread."""
        def _do():
            try:
                result = self._client.edit_order(order_id, data)
                if result:
                    self._poll_my_orders()
                    if callback:
                        callback(True, result)
                else:
                    if callback:
                        callback(False, "No response from server")
            except Exception as e:
                error_msg = self._extract_error(e)
                log.error("Failed to edit order %s: %s", order_id, error_msg)
                if callback:
                    callback(False, error_msg)

        threading.Thread(target=_do, daemon=True).start()

    def close_order(self, order_id: int, callback=None):
        """Close an exchange order in a background thread."""
        def _do():
            try:
                success = self._client.close_order(order_id)
                if success:
                    self._poll_my_orders()
                if callback:
                    callback(success, "Order closed" if success else "Failed to close order")
            except Exception as e:
                error_msg = self._extract_error(e)
                log.error("Failed to close order %s: %s", order_id, error_msg)
                if callback:
                    callback(False, error_msg)

        threading.Thread(target=_do, daemon=True).start()

    def bump_order(self, order_id: int, callback=None):
        """Bump an order by editing with same data (resets bumped_at)."""
        # Find the order to get its current data
        order = None
        for o in self._my_orders:
            if o.get('id') == order_id:
                order = o
                break
        if not order:
            if callback:
                callback(False, "Order not found")
            return

        data = {
            'quantity': order.get('quantity', 1),
            'markup': order.get('markup', 0),
            'planet': order.get('planet'),
            'details': order.get('details'),
        }
        if order.get('min_quantity'):
            data['min_quantity'] = order['min_quantity']

        self.edit_order(order_id, data, callback)

    def bump_all_orders(self, callback=None):
        """Bump all eligible orders."""
        def _do():
            try:
                result = self._client.bump_all_orders()
                if result:
                    self._poll_my_orders()
                    if callback:
                        callback(True, result)
                else:
                    if callback:
                        callback(False, "No response from server")
            except Exception as e:
                error_msg = self._extract_error(e)
                log.error("Failed to bump all orders: %s", error_msg)
                if callback:
                    callback(False, error_msg)

        threading.Thread(target=_do, daemon=True).start()

    def cancel_trade_request(self, request_id: int, callback=None):
        """Cancel a trade request."""
        def _do():
            try:
                success = self._client.cancel_trade_request(request_id)
                if success:
                    self._poll_trade_requests()
                if callback:
                    callback(success, "Cancelled" if success else "Failed")
            except Exception as e:
                error_msg = self._extract_error(e)
                if callback:
                    callback(False, error_msg)

        threading.Thread(target=_do, daemon=True).start()

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def start_polling(self):
        """Start polling (consumer-counted). Call when overlay/page becomes visible."""
        self._consumer_count += 1
        if self._consumer_count == 1:
            from .constants import (
                POLL_ORDERS_MS, POLL_INVENTORY_MS, POLL_TRADE_REQUESTS_MS,
            )
            self._orders_timer.start(POLL_ORDERS_MS)
            self._inventory_timer.start(POLL_INVENTORY_MS)
            self._trades_timer.start(POLL_TRADE_REQUESTS_MS)
            log.debug("Exchange polling started (consumers: %d)", self._consumer_count)

    def stop_polling(self):
        """Stop polling (consumer-counted). Call when overlay/page becomes hidden."""
        self._consumer_count = max(0, self._consumer_count - 1)
        if self._consumer_count == 0:
            self._orders_timer.stop()
            self._inventory_timer.stop()
            self._trades_timer.stop()
            log.debug("Exchange polling stopped")

    def _poll_my_orders(self):
        """Timer callback — refresh my orders."""
        if self._client.is_authenticated():
            self.load_my_orders()

    def _poll_inventory(self):
        """Timer callback — refresh inventory."""
        if self._client.is_authenticated():
            self.load_inventory()

    def _poll_trade_requests(self):
        """Timer callback — refresh trade requests."""
        if self._client.is_authenticated():
            self.load_trade_requests()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_loading(self, what: str, loading: bool):
        self._loading[what] = loading
        self.loading_changed.emit(what, loading)

    @staticmethod
    def _extract_error(e: Exception) -> str:
        """Extract user-friendly error message from an exception."""
        import requests as _requests
        if isinstance(e, _requests.HTTPError) and e.response is not None:
            try:
                body = e.response.json()
                return body.get('error', str(e))
            except Exception:
                return f"HTTP {e.response.status_code}: {e.response.reason}"
        return str(e)
