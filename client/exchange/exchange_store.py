"""Shared exchange data store — used by both overlay and page."""

from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ..core.logger import get_logger
from .order_utils import enrich_orders, is_absolute_markup, format_markup, format_age, get_top_category

if TYPE_CHECKING:
    from ..api.nexus_client import NexusClient

log = get_logger("ExchangeStore")

# Sort key names used by get_sorted_items()
SORT_NAME = "name"
SORT_TYPE = "type"
SORT_SELL = "sell"
SORT_BUY = "buy"
SORT_ORDERS = "orders"        # sell + buy combined (overlay S/B column)
SORT_MARKUP = "markup"
SORT_UPDATED = "updated"

_MAX_DETAIL_CACHE = 100  # Max items in per-item order/price caches


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
    exchange_prices_changed = pyqtSignal(int)    # item_id
    loading_changed = pyqtSignal(str, bool)       # (what, is_loading)
    error_occurred = pyqtSignal(str, str)          # (context, message)

    def __init__(self, nexus_client: NexusClient, event_bus=None):
        super().__init__()
        self._client = nexus_client
        self._event_bus = event_bus

        # Data
        self._items: list[dict] = []
        self._item_lookup: dict[int, dict] = {}
        # Pre-sorted item lists (one per sort key, built in background thread)
        self._sorted_asc: dict[str, list[dict]] = {}
        self._sorted_desc: dict[str, list[dict]] = {}
        self._my_orders: list[dict] = []
        self._inventory: list[dict] = []
        self._trade_requests: list[dict] = []
        self._item_orders_cache: OrderedDict[int, dict] = OrderedDict()
        self._exchange_prices_cache: OrderedDict[int, dict] = OrderedDict()
        self._initial_trade_load = True

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
        data = self._item_orders_cache.get(item_id)
        if data is not None:
            self._item_orders_cache.move_to_end(item_id)
        return data

    def get_exchange_prices(self, item_id: int) -> dict | None:
        """Get cached exchange price data for an item."""
        data = self._exchange_prices_cache.get(item_id)
        if data is not None:
            self._exchange_prices_cache.move_to_end(item_id)
        return data

    def is_loading(self, what: str) -> bool:
        return self._loading.get(what, False)

    # ------------------------------------------------------------------
    # Loading — items (public, no auth)
    # ------------------------------------------------------------------

    def get_sorted_items(self, sort_key: str, descending: bool = False) -> list[dict]:
        """Return items pre-sorted by *sort_key*. Falls back to unsorted list."""
        bucket = self._sorted_desc if descending else self._sorted_asc
        return bucket.get(sort_key, self._items)

    def load_items(self):
        """Fetch exchange items (public, no auth). Call once on startup."""
        self._set_loading("items", True)

        def _do():
            try:
                items = self._client.get_exchange_items()
                self._items = items or []
                self._item_lookup = {item['i']: item for item in self._items if 'i' in item}
                self._enrich_and_sort()
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

        threading.Thread(target=_do, daemon=True, name="exch-load-items").start()

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

        threading.Thread(target=_do, daemon=True, name="exch-load-orders").start()

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

        threading.Thread(target=_do, daemon=True, name="exch-load-inventory").start()

    def load_trade_requests(self):
        """Fetch user's trade requests (requires auth)."""
        if not self._client.is_authenticated():
            return
        self._set_loading("trades", True)

        def _do():
            try:
                data = self._client.get_trade_requests()
                if data is not None:
                    new_list = data if isinstance(data, list) else []
                    # Detect newly added trade requests
                    if self._event_bus and not self._initial_trade_load:
                        old_ids = {r.get('id') for r in self._trade_requests}
                        for req in new_list:
                            if req.get('id') not in old_ids:
                                from ..core.constants import EVENT_TRADE_REQUEST
                                self._event_bus.publish(EVENT_TRADE_REQUEST, req)
                    self._initial_trade_load = False
                    self._trade_requests = new_list
                self._set_loading("trades", False)
                self.trade_requests_changed.emit()
            except Exception as e:
                log.error("Failed to load trade requests: %s", e)
                self._set_loading("trades", False)
                self.error_occurred.emit("trades", str(e))

        threading.Thread(target=_do, daemon=True, name="exch-load-trades").start()

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
                    if len(self._item_orders_cache) > _MAX_DETAIL_CACHE:
                        self._item_orders_cache.popitem(last=False)
                self._set_loading(f"item_orders_{item_id}", False)
                self.item_orders_changed.emit(item_id)
            except Exception as e:
                log.error("Failed to load item orders %s: %s", item_id, e)
                self._set_loading(f"item_orders_{item_id}", False)
                self.error_occurred.emit("item_orders", str(e))

        threading.Thread(target=_do, daemon=True, name="exch-item-orders").start()

    def load_exchange_prices(self, item_id: int):
        """Fetch exchange price data for an item (public, no auth)."""
        def _do():
            try:
                data = self._client.get_exchange_prices(item_id)
                if data is not None:
                    self._exchange_prices_cache[item_id] = data
                    if len(self._exchange_prices_cache) > _MAX_DETAIL_CACHE:
                        self._exchange_prices_cache.popitem(last=False)
                self.exchange_prices_changed.emit(item_id)
            except Exception as e:
                log.error("Failed to load exchange prices %s: %s", item_id, e)

        threading.Thread(target=_do, daemon=True, name="exch-load-prices").start()

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

        threading.Thread(target=_do, daemon=True, name="exch-create-order").start()

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

        threading.Thread(target=_do, daemon=True, name="exch-edit-order").start()

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

        threading.Thread(target=_do, daemon=True, name="exch-close-order").start()

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

        threading.Thread(target=_do, daemon=True, name="exch-bump-all").start()

    def create_trade_request(self, order: dict, quantity: int, callback=None):
        """Send a trade request responding to an order.

        callback(success: bool, result_or_error: dict|str)
        """
        def _do():
            try:
                item_name = order.get('_item_name') or f"Item #{order.get('item_id')}"
                result = self._client.create_trade_request(
                    target_id=order.get('user_id'),
                    planet=order.get('planet'),
                    items=[{
                        "offer_id": order.get('id'),
                        "item_id": order.get('item_id'),
                        "item_name": item_name,
                        "quantity": quantity,
                        "markup": order.get('markup'),
                        "side": order.get('type'),  # 'BUY' or 'SELL'
                    }],
                )
                if result:
                    self._poll_trade_requests()
                    if callback:
                        callback(True, result)
                else:
                    if callback:
                        callback(False, "No response from server")
            except Exception as e:
                error_msg = self._extract_error(e)
                log.error("Failed to create trade request: %s", error_msg)
                if callback:
                    callback(False, error_msg)

        threading.Thread(target=_do, daemon=True, name="exch-create-trade").start()

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

        threading.Thread(target=_do, daemon=True, name="exch-cancel-trade").start()

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
    # Pre-sorting (runs in background thread)
    # ------------------------------------------------------------------

    def _enrich_and_sort(self):
        """Pre-compute sort keys and display values, then build sorted lists.

        Called from the background fetch thread so the main thread never sorts.
        """
        for item in self._items:
            name = item.get('n', '')
            s = item.get('s', 0) or 0
            b = item.get('b', 0) or 0

            # Markup sort value
            mu_val = item.get('m')
            if mu_val is None:
                mu_val = item.get('bb')
            if mu_val is None:
                mu_val = item.get('bs')
            mu_sort = 0.0
            mu_text = ''
            if mu_val is not None:
                try:
                    mu_sort = float(mu_val)
                except (TypeError, ValueError):
                    pass
                mu_text = format_markup(mu_val, is_absolute_markup(item))
            elif item.get('ns'):
                # Item has only negotiable sell offers (no priced ones)
                mu_text = 'Negotiable'

            # Updated sort value (composite: has_orders first, then timestamp)
            u = item.get('u')
            ts = 0.0
            if u and isinstance(u, str):
                try:
                    ts = datetime.fromisoformat(
                        u.replace('Z', '+00:00')
                    ).timestamp()
                except (ValueError, OSError):
                    pass
            has_orders = 1 if (s + b) > 0 else 0

            # Store pre-computed values
            item['_sk_name'] = name.lower()
            item['_sk_sell'] = s
            item['_sk_buy'] = b
            item['_sk_orders'] = s + b
            item['_sk_mu'] = mu_sort
            item['_sk_mu_text'] = mu_text
            item['_sk_updated'] = (has_orders, ts)
            item['_sk_updated_text'] = format_age(u)
            item['_sk_category'] = get_top_category(item.get('t', ''))

        # Build one sorted list per key (ascending). Descending is reversed copy.
        keys = {
            SORT_NAME:    lambda it: it['_sk_name'],
            SORT_TYPE:    lambda it: (it.get('t', ''), it['_sk_name']),
            SORT_SELL:    lambda it: it['_sk_sell'],
            SORT_BUY:     lambda it: it['_sk_buy'],
            SORT_ORDERS:  lambda it: it['_sk_orders'],
            SORT_MARKUP:  lambda it: it['_sk_mu'],
            SORT_UPDATED: lambda it: it['_sk_updated'],
        }
        sorted_asc = {}
        sorted_desc = {}
        for key_name, key_fn in keys.items():
            asc = sorted(self._items, key=key_fn)
            sorted_asc[key_name] = asc
            sorted_desc[key_name] = asc[::-1]

        self._sorted_asc = sorted_asc
        self._sorted_desc = sorted_desc

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
