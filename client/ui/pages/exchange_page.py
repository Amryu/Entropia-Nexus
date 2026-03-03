"""Exchange page — browse items, order books, my orders, inventory, trade requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QTreeWidget, QTreeWidgetItem, QLineEdit,
    QComboBox, QHeaderView, QSpinBox, QDoubleSpinBox, QCheckBox,
    QFormLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QCursor

from ..theme import (
    PRIMARY, SECONDARY, MAIN_DARK, HOVER, BORDER, ACCENT,
    TEXT, TEXT_MUTED, ERROR, TABLE_HEADER, TABLE_ROW_ALT,
    PAGE_HEADER_OBJECT_NAME,
)
from ...exchange.constants import (
    PLANETS, STATUS_COLORS, DEFAULT_PARTIAL_RATIO,
    MAX_ORDERS_PER_ITEM, compute_state,
    get_percent_undercut, get_absolute_undercut,
)
from ...exchange.order_utils import (
    is_stackable, is_percent_markup, is_absolute_markup, is_blueprint_non_l,
    is_item_tierable, is_gendered, item_has_condition, is_limited, is_pet,
    get_max_tt, get_unit_tt, compute_order_unit_price, format_ped, format_markup,
    format_ped_value, format_age, get_top_category, enrich_orders,
    TIERABLE_TYPES, GENDERED_TYPES, PLATE_SET_SIZE, ALL_CATEGORIES,
    CATEGORY_ORDER, get_category_order,
)
from ..icons import svg_icon, svg_pixmap
from ...core.logger import get_logger

if TYPE_CHECKING:
    from ..signals import AppSignals
    from ...exchange.exchange_store import ExchangeStore
    from ...exchange.favourites_store import FavouritesStore

log = get_logger("ExchangePage")

# Tab indices
_TAB_BROWSE = 0
_TAB_ORDERS = 1
_TAB_INVENTORY = 2
_TAB_TRADES = 3

# Status badge labels and colors (same as overlay)
_STATUS_LABELS = {
    'active': ('Active', STATUS_COLORS['active']),
    'stale': ('Stale', STATUS_COLORS['stale']),
    'expired': ('Expired', STATUS_COLORS['expired']),
    'terminated': ('Terminated', STATUS_COLORS['terminated']),
    'closed': ('Closed', STATUS_COLORS['closed']),
}

# SVG for star icon
_STAR_FILLED = '<path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>'
_STAR_OUTLINE = '<path d="M22 9.24l-7.19-.62L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24zM12 15.4l-3.76 2.27 1-4.28-3.32-2.88 4.38-.38L12 6.1l1.71 4.04 4.38.38-3.32 2.88 1 4.28L12 15.4z"/>'
_BACK_SVG = '<path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>'


def _tab_btn(text: str, active: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setCheckable(True)
    btn.setChecked(active)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            color: {TEXT_MUTED};
            border: none;
            border-bottom: 2px solid transparent;
            padding: 6px 16px;
            font-size: 13px;
            font-weight: bold;
        }}
        QPushButton:checked {{
            color: {ACCENT};
            border-bottom: 2px solid {ACCENT};
        }}
        QPushButton:hover:!checked {{
            color: {TEXT};
        }}
    """)
    return btn


def _action_btn(text: str, accent: bool = False) -> QPushButton:
    bg = ACCENT if accent else HOVER
    fg = "#000" if accent else TEXT
    btn = QPushButton(text)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {bg}; color: {fg}; border: none;
            border-radius: 4px; padding: 4px 12px;
            font-size: 12px; font-weight: bold;
            min-height: 26px;
        }}
        QPushButton:hover {{ background: {'#00aadd' if accent else BORDER}; }}
        QPushButton:disabled {{ background: {MAIN_DARK}; color: {TEXT_MUTED}; }}
    """)
    return btn


class ExchangePage(QWidget):
    """Main client page for the Exchange market."""

    navigation_changed = pyqtSignal(object)

    def __init__(self, *, signals: AppSignals, exchange_store: ExchangeStore,
                 favourites_store: FavouritesStore, config, parent=None):
        super().__init__(parent)
        self._signals = signals
        self._store = exchange_store
        self._favourites = favourites_store
        self._config = config
        self._active_tab = _TAB_BROWSE
        self._current_item_id: int | None = None
        self._order_dialog = None

        self._build_ui()

        # Connect store signals
        self._store.items_changed.connect(self._on_items_changed)
        self._store.my_orders_changed.connect(self._on_orders_changed)
        self._store.inventory_changed.connect(self._on_inventory_changed)
        self._store.trade_requests_changed.connect(self._on_trades_changed)
        self._store.item_orders_changed.connect(self._on_item_orders_changed)
        self._store.loading_changed.connect(self._on_loading_changed)
        self._favourites.changed.connect(self._on_favourites_changed)

        # Auth state changes
        signals.auth_state_changed.connect(lambda _: self._update_auth_visibility())

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        header = QLabel("Exchange")
        header.setObjectName(PAGE_HEADER_OBJECT_NAME)
        outer.addWidget(header)

        # Tab bar
        tab_bar = QWidget()
        tab_bar.setStyleSheet(f"background: {PRIMARY}; border-bottom: 1px solid {BORDER};")
        tb_layout = QHBoxLayout(tab_bar)
        tb_layout.setContentsMargins(16, 0, 16, 0)
        tb_layout.setSpacing(0)

        self._tab_btns: list[QPushButton] = []
        for i, label in enumerate(["Browse", "My Orders", "Inventory", "Trades"]):
            btn = _tab_btn(label, active=(i == 0))
            btn.clicked.connect(lambda _, idx=i: self._set_tab(idx))
            tb_layout.addWidget(btn)
            self._tab_btns.append(btn)
        tb_layout.addStretch()

        outer.addWidget(tab_bar)

        # Content stack
        self._content_stack = QStackedWidget()

        self._browse_widget = self._build_browse_view()
        self._content_stack.addWidget(self._browse_widget)

        self._orders_widget = self._build_orders_view()
        self._content_stack.addWidget(self._orders_widget)

        self._inventory_widget = self._build_inventory_view()
        self._content_stack.addWidget(self._inventory_widget)

        self._trades_widget = self._build_trades_view()
        self._content_stack.addWidget(self._trades_widget)

        outer.addWidget(self._content_stack, 1)

    def _set_tab(self, index: int):
        self._active_tab = index
        self._content_stack.setCurrentIndex(index)
        for i, btn in enumerate(self._tab_btns):
            btn.setChecked(i == index)
        # Refresh data
        if index == _TAB_ORDERS:
            self._store.load_my_orders()
        elif index == _TAB_INVENTORY:
            self._store.load_inventory()
        elif index == _TAB_TRADES:
            self._store.load_trade_requests()

    # ------------------------------------------------------------------
    # Tab 0: Browse
    # ------------------------------------------------------------------

    def _build_browse_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Browse has two sub-views
        self._browse_stack = QStackedWidget()

        self._browse_stack.addWidget(self._build_item_list_view())
        self._browse_stack.addWidget(self._build_order_book_view())

        layout.addWidget(self._browse_stack, 1)
        return w

    def _build_item_list_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Filter row
        filter_row = QWidget()
        fr_layout = QHBoxLayout(filter_row)
        fr_layout.setContentsMargins(0, 0, 0, 0)
        fr_layout.setSpacing(8)

        self._browse_search = QLineEdit()
        self._browse_search.setPlaceholderText("Search items...")
        self._browse_search.textChanged.connect(self._filter_items)
        fr_layout.addWidget(self._browse_search, 1)

        self._browse_category = QComboBox()
        self._browse_category.addItem("All Categories")
        for cat in CATEGORY_ORDER:
            self._browse_category.addItem(cat)
        self._browse_category.currentIndexChanged.connect(self._filter_items)
        fr_layout.addWidget(self._browse_category)

        layout.addWidget(filter_row)

        # Item tree
        self._item_tree = QTreeWidget()
        self._item_tree.setHeaderLabels(["Name", "Type", "Sell", "Buy", "Markup", "Updated"])
        self._item_tree.setColumnCount(6)
        self._item_tree.setRootIsDecorated(False)
        self._item_tree.setAlternatingRowColors(True)
        self._item_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        header = self._item_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, width in [(1, 90), (2, 50), (3, 50), (4, 100), (5, 80)]:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(i, width)
        self._item_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._item_tree, 1)

        return w

    def _build_order_book_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header: back + item name + star
        hdr = QWidget()
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(8)

        back_btn = QPushButton()
        back_btn.setFixedSize(28, 28)
        back_btn.setIcon(svg_icon(_BACK_SVG, TEXT, 18))
        back_btn.setStyleSheet(f"background: transparent; border: none;")
        back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back_btn.setToolTip("Back to listings")
        back_btn.clicked.connect(self._back_to_listings)
        hdr_layout.addWidget(back_btn)

        self._book_item_label = QLabel()
        self._book_item_label.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: bold;")
        hdr_layout.addWidget(self._book_item_label, 1)

        self._book_star_btn = QPushButton()
        self._book_star_btn.setFixedSize(28, 28)
        self._book_star_btn.setStyleSheet("background: transparent; border: none;")
        self._book_star_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._book_star_btn.clicked.connect(self._toggle_current_favourite)
        hdr_layout.addWidget(self._book_star_btn)

        layout.addWidget(hdr)

        # Sell orders
        sell_label = QLabel("Sell Orders")
        sell_label.setStyleSheet(f"color: {ACCENT}; font-size: 13px; font-weight: bold;")
        layout.addWidget(sell_label)

        self._sell_tree = QTreeWidget()
        self._sell_tree.setRootIsDecorated(False)
        self._sell_tree.setAlternatingRowColors(True)
        layout.addWidget(self._sell_tree, 1)

        # Buy orders
        buy_label = QLabel("Buy Orders")
        buy_label.setStyleSheet(f"color: {ACCENT}; font-size: 13px; font-weight: bold;")
        layout.addWidget(buy_label)

        self._buy_tree = QTreeWidget()
        self._buy_tree.setRootIsDecorated(False)
        self._buy_tree.setAlternatingRowColors(True)
        layout.addWidget(self._buy_tree, 1)

        # Action buttons
        btn_row = QWidget()
        br_layout = QHBoxLayout(btn_row)
        br_layout.setContentsMargins(0, 4, 0, 0)
        br_layout.setSpacing(8)

        self._create_sell_btn = _action_btn("Create Sell Order", accent=True)
        self._create_sell_btn.clicked.connect(lambda: self._open_order_dialog("SELL"))
        br_layout.addWidget(self._create_sell_btn)

        self._create_buy_btn = _action_btn("Create Buy Order")
        self._create_buy_btn.clicked.connect(lambda: self._open_order_dialog("BUY"))
        br_layout.addWidget(self._create_buy_btn)

        br_layout.addStretch()
        layout.addWidget(btn_row)

        # Loading label
        self._book_loading = QLabel("Loading order book...")
        self._book_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._book_loading.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        self._book_loading.hide()
        layout.addWidget(self._book_loading)

        return w

    # ------------------------------------------------------------------
    # Tab 1: My Orders
    # ------------------------------------------------------------------

    def _build_orders_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Filter row
        filter_row = QWidget()
        fr_layout = QHBoxLayout(filter_row)
        fr_layout.setContentsMargins(0, 0, 0, 0)
        fr_layout.setSpacing(8)

        self._orders_filter = "all"
        self._order_filter_btns_list: list[QPushButton] = []
        for label, filt in [("All", "all"), ("Buy", "BUY"), ("Sell", "SELL")]:
            btn = _action_btn(label)
            btn.clicked.connect(lambda _, f=filt: self._set_order_filter(f))
            fr_layout.addWidget(btn)
            self._order_filter_btns_list.append(btn)

        fr_layout.addStretch()

        self._bump_all_btn = _action_btn("Bump All")
        self._bump_all_btn.clicked.connect(self._on_bump_all)
        fr_layout.addWidget(self._bump_all_btn)

        layout.addWidget(filter_row)

        # Summary
        self._orders_summary = QLabel()
        self._orders_summary.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        layout.addWidget(self._orders_summary)

        # Orders tree
        self._orders_tree = QTreeWidget()
        self._orders_tree.setHeaderLabels(
            ["Item", "Side", "Qty", "Markup", "Planet", "Status", "Updated"]
        )
        self._orders_tree.setColumnCount(7)
        self._orders_tree.setRootIsDecorated(False)
        self._orders_tree.setAlternatingRowColors(True)
        header = self._orders_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, width in [(1, 50), (2, 60), (3, 100), (4, 80), (5, 80), (6, 80)]:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(i, width)
        layout.addWidget(self._orders_tree, 1)

        # Auth message
        self._orders_auth_label = QLabel("Log in to view your orders")
        self._orders_auth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._orders_auth_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        layout.addWidget(self._orders_auth_label)

        return w

    # ------------------------------------------------------------------
    # Tab 2: Inventory
    # ------------------------------------------------------------------

    def _build_inventory_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        self._inv_search = QLineEdit()
        self._inv_search.setPlaceholderText("Search inventory...")
        self._inv_search.textChanged.connect(self._filter_inventory)
        layout.addWidget(self._inv_search)

        self._inv_tree = QTreeWidget()
        self._inv_tree.setHeaderLabels(["Name", "Type", "Qty", "TT Value", "Orders"])
        self._inv_tree.setColumnCount(5)
        self._inv_tree.setRootIsDecorated(False)
        self._inv_tree.setAlternatingRowColors(True)
        header = self._inv_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, width in [(1, 90), (2, 60), (3, 90), (4, 60)]:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(i, width)
        layout.addWidget(self._inv_tree, 1)

        # Auth message
        self._inv_auth_label = QLabel("Log in to view your inventory")
        self._inv_auth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inv_auth_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        layout.addWidget(self._inv_auth_label)

        return w

    # ------------------------------------------------------------------
    # Tab 3: Trade Requests
    # ------------------------------------------------------------------

    def _build_trades_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        self._trades_tree = QTreeWidget()
        self._trades_tree.setHeaderLabels(["Partner", "Items", "Status", "Created"])
        self._trades_tree.setColumnCount(4)
        self._trades_tree.setRootIsDecorated(False)
        self._trades_tree.setAlternatingRowColors(True)
        header = self._trades_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, width in [(1, 60), (2, 80), (3, 80)]:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(i, width)
        layout.addWidget(self._trades_tree, 1)

        # Auth message
        self._trades_auth_label = QLabel("Log in to view trade requests")
        self._trades_auth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._trades_auth_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        layout.addWidget(self._trades_auth_label)

        return w

    # ------------------------------------------------------------------
    # Data handlers
    # ------------------------------------------------------------------

    def _on_items_changed(self):
        self._populate_item_tree()

    def _on_orders_changed(self):
        self._populate_orders_tree()

    def _on_inventory_changed(self):
        self._populate_inventory_tree()

    def _on_trades_changed(self):
        self._populate_trades_tree()

    def _on_item_orders_changed(self, item_id: int):
        if item_id == self._current_item_id:
            self._populate_order_book()

    def _on_loading_changed(self, what: str, loading: bool):
        if what.startswith("item_orders_") and self._current_item_id:
            self._book_loading.setVisible(loading)

    def _on_favourites_changed(self):
        if self._current_item_id:
            self._update_star_button()

    def _update_auth_visibility(self):
        authed = self._store._client.is_authenticated()
        self._orders_auth_label.setVisible(not authed)
        self._orders_tree.setVisible(authed)
        self._inv_auth_label.setVisible(not authed)
        self._inv_tree.setVisible(authed)
        self._trades_auth_label.setVisible(not authed)
        self._trades_tree.setVisible(authed)
        self._create_sell_btn.setEnabled(authed)
        self._create_buy_btn.setEnabled(authed)
        self._bump_all_btn.setEnabled(authed)

    # ------------------------------------------------------------------
    # Populate: Item listing
    # ------------------------------------------------------------------

    def _populate_item_tree(self):
        self._filter_items()

    def _filter_items(self):
        search = self._browse_search.text().strip().lower()
        cat_idx = self._browse_category.currentIndex()
        selected_cat = CATEGORY_ORDER[cat_idx - 1] if cat_idx > 0 else None

        self._item_tree.clear()
        for item in self._store.items:
            name = item.get('n', '')
            item_type = item.get('t', '')
            category = get_top_category(item_type)

            if search and search not in name.lower():
                continue
            if selected_cat and category != selected_cat:
                continue

            row = QTreeWidgetItem()
            row.setText(0, name)
            row.setText(1, item_type)

            s_count = item.get('s', 0) or 0
            b_count = item.get('b', 0) or 0
            row.setText(2, str(s_count) if s_count else "")
            row.setText(3, str(b_count) if b_count else "")

            # Best markup
            sell_mu = item.get('sv')
            buy_mu = item.get('bv')
            mu_text = ''
            if sell_mu is not None:
                mu_text = format_markup(sell_mu, is_absolute_markup(item))
            elif buy_mu is not None:
                mu_text = format_markup(buy_mu, is_absolute_markup(item))
            row.setText(4, mu_text)

            # Updated
            row.setText(5, format_age(item.get('ut')))

            row.setData(0, Qt.ItemDataRole.UserRole, item.get('i'))
            self._item_tree.addTopLevelItem(row)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        if item_id is not None:
            self._show_order_book(item_id)

    # ------------------------------------------------------------------
    # Order book view
    # ------------------------------------------------------------------

    def _show_order_book(self, item_id: int):
        self._current_item_id = item_id
        slim = self._store.item_lookup.get(item_id)
        name = slim.get('n', f'Item #{item_id}') if slim else f'Item #{item_id}'
        item_type = slim.get('t', '') if slim else ''
        max_tt = get_max_tt(slim) if slim else None
        tt_str = f" · {format_ped(max_tt)} PED" if max_tt is not None else ""
        self._book_item_label.setText(f"{name} ({item_type}){tt_str}")

        self._update_star_button()
        self._update_auth_visibility()
        self._browse_stack.setCurrentIndex(1)
        self._book_loading.show()
        self._store.load_item_orders(item_id)

    def _back_to_listings(self):
        self._current_item_id = None
        self._browse_stack.setCurrentIndex(0)

    def _update_star_button(self):
        if self._current_item_id and self._favourites.is_favourite(self._current_item_id):
            self._book_star_btn.setIcon(svg_icon(_STAR_FILLED, "#fbbf24", 18))
            self._book_star_btn.setToolTip("Remove from favourites")
        else:
            self._book_star_btn.setIcon(svg_icon(_STAR_OUTLINE, TEXT_MUTED, 18))
            self._book_star_btn.setToolTip("Add to favourites")

    def _toggle_current_favourite(self):
        if self._current_item_id:
            self._favourites.toggle_favourite(self._current_item_id)
            self._update_star_button()

    def _populate_order_book(self):
        if not self._current_item_id:
            return
        self._book_loading.hide()
        data = self._store.get_item_orders(self._current_item_id)
        if not data:
            return

        slim = self._store.item_lookup.get(self._current_item_id)
        self._populate_order_table(self._sell_tree, data.get('sell', []), slim)
        self._populate_order_table(self._buy_tree, data.get('buy', []), slim)

    def _populate_order_table(self, tree: QTreeWidget, orders: list[dict],
                              slim: dict | None):
        tree.clear()

        columns = self._get_order_columns(slim)
        tree.setHeaderLabels([c[0] for c in columns])
        tree.setColumnCount(len(columns))

        header = tree.header()
        header.setStretchLastSection(False)
        for i, (_, width) in enumerate(columns):
            if width == 0:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                header.resizeSection(i, width)

        for order in orders:
            row = QTreeWidgetItem()
            self._fill_order_row(row, order, columns, slim)
            tree.addTopLevelItem(row)

    def _get_order_columns(self, slim: dict | None) -> list[tuple[str, int]]:
        cols: list[tuple[str, int]] = []

        if is_stackable(slim):
            cols.append(("Qty", 60))

        if is_item_tierable(slim):
            cols.append(("Tier", 45))
            cols.append(("TiR", 45))

        if is_gendered(slim):
            cols.append(("Gender", 60))

        if slim and slim.get('t') == 'ArmorPlating':
            cols.append(("Set", 40))

        if is_pet(slim):
            cols.append(("Lvl", 40))

        if is_blueprint_non_l(slim):
            cols.append(("QR", 40))

        cols.append(("Value", 70))
        cols.append(("Markup", 90))
        cols.append(("Total", 80))
        cols.append(("Planet", 70))
        cols.append(("Seller", 0))  # stretch
        cols.append(("Status", 70))
        cols.append(("Updated", 70))
        return cols

    def _fill_order_row(self, row: QTreeWidgetItem, order: dict,
                        columns: list[tuple[str, int]], slim: dict | None):
        details = order.get('details') or {}
        col = 0
        for name, _ in columns:
            text = ''
            if name == 'Qty':
                text = str(order.get('quantity', 1))
            elif name == 'Tier':
                text = str(details.get('Tier', ''))
            elif name == 'TiR':
                text = str(details.get('TierIncreaseRate', ''))
            elif name == 'Gender':
                text = details.get('Gender', '')
            elif name == 'Set':
                text = "Yes" if details.get('is_set') else ""
            elif name == 'Lvl':
                pet = details.get('Pet') or {}
                text = str(pet.get('Level', ''))
            elif name == 'QR':
                text = str(details.get('QualityRating', ''))
            elif name == 'Value':
                v = order.get('_value')
                text = format_ped(v) if v is not None else ''
            elif name == 'Markup':
                mu = order.get('markup')
                if mu is not None:
                    text = format_markup(mu, order.get('_is_absolute', True))
            elif name == 'Total':
                t = order.get('_total')
                text = format_ped(t) if t is not None else ''
            elif name == 'Planet':
                text = order.get('planet') or 'Any'
            elif name == 'Seller':
                text = order.get('username') or str(order.get('user_id', ''))
            elif name == 'Status':
                text = (order.get('_state') or '').capitalize()
            elif name == 'Updated':
                text = format_age(order.get('bumped_at') or order.get('updated'))
            row.setText(col, text)

            if name == 'Status':
                state = order.get('_state', '')
                color = STATUS_COLORS.get(state, '#666')
                row.setForeground(col, QColor(color))

            col += 1

    # ------------------------------------------------------------------
    # Populate: My Orders
    # ------------------------------------------------------------------

    def _set_order_filter(self, filt: str):
        self._orders_filter = filt
        self._populate_orders_tree()

    def _populate_orders_tree(self):
        self._update_auth_visibility()
        if not self._store._client.is_authenticated():
            return

        self._orders_tree.clear()
        orders = self._store.my_orders

        if self._orders_filter == "BUY":
            orders = [o for o in orders if o.get('type') == 'BUY']
        elif self._orders_filter == "SELL":
            orders = [o for o in orders if o.get('type') == 'SELL']

        state_priority = {'active': 0, 'stale': 1, 'expired': 2, 'terminated': 3, 'closed': 4}
        orders.sort(key=lambda o: (
            state_priority.get(o.get('_state', ''), 5),
            o.get('_category_order', 99),
        ))

        sell_count = sum(1 for o in self._store.my_orders if o.get('type') == 'SELL' and o.get('_state') != 'closed')
        buy_count = sum(1 for o in self._store.my_orders if o.get('type') == 'BUY' and o.get('_state') != 'closed')
        self._orders_summary.setText(f"{sell_count} sell · {buy_count} buy orders")

        for order in orders:
            row = QTreeWidgetItem()
            row.setText(0, order.get('_item_name', ''))
            row.setText(1, order.get('type', ''))
            row.setText(2, str(order.get('quantity', 1)))
            mu = order.get('markup')
            if mu is not None:
                row.setText(3, format_markup(mu, order.get('_is_absolute', True)))
            row.setText(4, order.get('planet') or 'Any')

            state = order.get('_state', '')
            row.setText(5, state.capitalize())
            color = STATUS_COLORS.get(state, '#666')
            row.setForeground(5, QColor(color))

            row.setText(6, format_age(order.get('bumped_at') or order.get('updated')))

            row.setData(0, Qt.ItemDataRole.UserRole, order.get('id'))
            row.setData(0, Qt.ItemDataRole.UserRole + 1, order)
            self._orders_tree.addTopLevelItem(row)

    def _on_bump_all(self):
        self._bump_all_btn.setEnabled(False)
        self._bump_all_btn.setText("Bumping...")

        def cb(success, result):
            self._bump_all_btn.setEnabled(True)
            self._bump_all_btn.setText("Bump All")

        self._store.bump_all_orders(callback=cb)

    # ------------------------------------------------------------------
    # Populate: Inventory
    # ------------------------------------------------------------------

    def _populate_inventory_tree(self):
        self._update_auth_visibility()
        self._filter_inventory()

    def _filter_inventory(self):
        if not self._store._client.is_authenticated():
            return

        search = self._inv_search.text().strip().lower()
        self._inv_tree.clear()

        for inv_item in self._store.inventory:
            item_id = inv_item.get('item_id', 0)
            slim = self._store.item_lookup.get(item_id)
            name = slim.get('n', f'#{item_id}') if slim else f'#{item_id}'
            item_type = slim.get('t', '') if slim else ''

            if search and search not in name.lower():
                continue

            row = QTreeWidgetItem()
            row.setText(0, name)
            row.setText(1, item_type)
            row.setText(2, str(inv_item.get('quantity', 1)))
            value = inv_item.get('value')
            row.setText(3, format_ped(value) if value is not None else '')

            sell_count = slim.get('s', 0) if slim else 0
            row.setText(4, str(sell_count) if sell_count else '')

            row.setData(0, Qt.ItemDataRole.UserRole, item_id)
            row.setData(0, Qt.ItemDataRole.UserRole + 1, inv_item)
            self._inv_tree.addTopLevelItem(row)

    # ------------------------------------------------------------------
    # Populate: Trade Requests
    # ------------------------------------------------------------------

    def _populate_trades_tree(self):
        self._update_auth_visibility()
        if not self._store._client.is_authenticated():
            return

        self._trades_tree.clear()
        for tr in self._store.trade_requests:
            row = QTreeWidgetItem()
            row.setText(0, tr.get('partner_name') or str(tr.get('partner_id', '')))
            row.setText(1, str(tr.get('item_count', 0)))
            status = tr.get('status', '')
            row.setText(2, status.capitalize())
            row.setText(3, format_age(tr.get('created_at')))
            row.setData(0, Qt.ItemDataRole.UserRole, tr.get('id'))
            self._trades_tree.addTopLevelItem(row)

    # ------------------------------------------------------------------
    # Order Dialog
    # ------------------------------------------------------------------

    def _open_order_dialog(self, side: str, order: dict | None = None):
        if not self._store._client.is_authenticated():
            return
        if not self._current_item_id:
            return

        slim = self._store.item_lookup.get(self._current_item_id)
        if not slim:
            return

        from ...overlay.exchange_overlay import _OrderDialog
        dialog = _OrderDialog(
            slim=slim,
            side=side,
            order=order,
            store=self._store,
            parent=self.window(),
        )
        dialog.order_submitted.connect(self._on_order_submitted)
        dialog.show()
        self._order_dialog = dialog

    def _on_order_submitted(self, success: bool, message: str):
        if success and self._current_item_id:
            self._store.load_item_orders(self._current_item_id)

    # ------------------------------------------------------------------
    # Visibility hooks
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self._update_auth_visibility()
        self._store.start_polling()
        if not self._store.items:
            self._store.load_items()
        if self._store._client.is_authenticated():
            self._store.load_my_orders()
        self._favourites.load_from_server()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._store.stop_polling()

    def cleanup(self):
        self._store.stop_polling()
