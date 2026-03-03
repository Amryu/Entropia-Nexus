"""Exchange page — browse items, order books, my orders, inventory, trade requests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QTreeWidget, QTreeWidgetItem, QLineEdit,
    QComboBox, QHeaderView, QSpinBox, QDoubleSpinBox, QCheckBox,
    QFormLayout, QSizePolicy, QMenu,
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor

from ..theme import (
    PRIMARY, SECONDARY, MAIN_DARK, HOVER, BORDER, ACCENT,
    TEXT, TEXT_MUTED, ERROR, TABLE_HEADER, TABLE_ROW_ALT,
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
_TAB_FAVOURITES = 1
_TAB_ORDERS = 2
_TAB_INVENTORY = 3
_TAB_TRADES = 4

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


_TREE_STYLE = f"""
    QTreeWidget {{
        background-color: {PRIMARY};
        alternate-background-color: {TABLE_ROW_ALT};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 4px;
    }}
    QTreeWidget::item {{
        padding: 2px 4px;
        min-height: 24px;
    }}
    QTreeWidget::item:selected {{
        background-color: {ACCENT};
        color: white;
    }}
    QTreeWidget::item:hover {{
        background-color: {HOVER};
    }}
    QHeaderView::section {{
        background-color: {TABLE_HEADER};
        color: {TEXT};
        border: none;
        border-right: 1px solid {BORDER};
        border-bottom: 1px solid {BORDER};
        padding: 4px 8px;
        font-weight: bold;
    }}
"""


class _SortableItem(QTreeWidgetItem):
    """Tree item that sorts numerically for columns with numeric sort keys."""

    def __lt__(self, other):
        tree = self.treeWidget()
        if tree is None:
            return super().__lt__(other)
        col = tree.sortColumn()
        a = self.data(col, Qt.ItemDataRole.UserRole + 10)
        b = other.data(col, Qt.ItemDataRole.UserRole + 10)
        if a is not None and b is not None:
            return a < b
        return super().__lt__(other)


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
        self._store.exchange_prices_changed.connect(self._on_exchange_prices_changed)
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

        # Tab bar
        tab_bar = QWidget()
        tab_bar.setStyleSheet(f"background: {PRIMARY}; border-bottom: 1px solid {BORDER};")
        tb_layout = QHBoxLayout(tab_bar)
        tb_layout.setContentsMargins(16, 0, 16, 0)
        tb_layout.setSpacing(0)

        self._tab_btns: list[QPushButton] = []
        for i, label in enumerate(["Browse", "Favourites", "My Orders", "Inventory", "Trades"]):
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

        self._favourites_widget = self._build_favourites_view()
        self._content_stack.addWidget(self._favourites_widget)

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
        if index == _TAB_FAVOURITES:
            self._populate_favourites()
        elif index == _TAB_ORDERS:
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
        self._browse_category.setMinimumContentsLength(15)
        self._browse_category.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._browse_category.currentIndexChanged.connect(self._filter_items)
        fr_layout.addWidget(self._browse_category)

        layout.addWidget(filter_row)

        # Item tree
        self._item_tree = QTreeWidget()
        self._item_tree.setStyleSheet(_TREE_STYLE)
        self._item_tree.setHeaderLabels(["Name", "Type", "Sell", "Buy", "Markup", "Updated"])
        self._item_tree.setColumnCount(6)
        self._item_tree.setRootIsDecorated(False)
        self._item_tree.setAlternatingRowColors(True)
        self._item_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._item_tree.setSortingEnabled(True)
        self._item_tree.sortByColumn(5, Qt.SortOrder.DescendingOrder)
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

        # View item details button
        _INFO_SVG = '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>'
        detail_btn = QPushButton()
        detail_btn.setFixedSize(28, 28)
        detail_btn.setIcon(svg_icon(_INFO_SVG, TEXT_MUTED, 18))
        detail_btn.setStyleSheet(f"background: transparent; border: none; border-radius: 4px;")
        detail_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        detail_btn.setToolTip("View item details")
        detail_btn.clicked.connect(self._open_item_detail)
        hdr_layout.addWidget(detail_btn)

        self._book_star_btn = QPushButton()
        self._book_star_btn.setFixedSize(28, 28)
        self._book_star_btn.setStyleSheet("background: transparent; border: none;")
        self._book_star_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._book_star_btn.clicked.connect(self._toggle_current_favourite)
        hdr_layout.addWidget(self._book_star_btn)

        layout.addWidget(hdr)

        # Metric panels
        metrics_row = QWidget()
        mr_layout = QHBoxLayout(metrics_row)
        mr_layout.setContentsMargins(0, 0, 0, 0)
        mr_layout.setSpacing(6)

        metric_style = (
            f"background-color: {MAIN_DARK}; border-radius: 4px;"
            f" padding: 4px 8px; font-size: 11px;"
        )
        self._metric_labels: dict[str, QLabel] = {}
        for key, label in [("median", "Median"), ("p10", "10%"), ("wap", "Wt. Avg"),
                           ("best_buy", "Best Buy"), ("best_sell", "Best Sell")]:
            box = QWidget()
            bl = QVBoxLayout(box)
            bl.setContentsMargins(6, 3, 6, 3)
            bl.setSpacing(1)
            box.setStyleSheet(metric_style)

            title = QLabel(label)
            title.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; background: transparent; padding: 0;")
            bl.addWidget(title)

            val = QLabel("\u2014")
            color = TEXT
            if key == "best_buy":
                color = "#16a34a"
            elif key == "best_sell":
                color = ACCENT
            val.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold; background: transparent; padding: 0;")
            bl.addWidget(val)
            self._metric_labels[key] = val
            mr_layout.addWidget(box)

        mr_layout.addStretch()
        self._metrics_row = metrics_row
        self._metrics_row.hide()
        layout.addWidget(metrics_row)

        # Sell orders
        sell_label = QLabel("Sell Orders")
        sell_label.setStyleSheet(f"color: {ACCENT}; font-size: 13px; font-weight: bold;")
        layout.addWidget(sell_label)

        self._sell_tree = QTreeWidget()
        self._sell_tree.setStyleSheet(_TREE_STYLE)
        self._sell_tree.setRootIsDecorated(False)
        self._sell_tree.setAlternatingRowColors(True)
        self._sell_tree.itemDoubleClicked.connect(
            lambda item, col: self._on_orderbook_double_clicked(item, col, 'sell')
        )
        layout.addWidget(self._sell_tree, 1)

        # Buy orders
        buy_label = QLabel("Buy Orders")
        buy_label.setStyleSheet(f"color: {ACCENT}; font-size: 13px; font-weight: bold;")
        layout.addWidget(buy_label)

        self._buy_tree = QTreeWidget()
        self._buy_tree.setStyleSheet(_TREE_STYLE)
        self._buy_tree.setRootIsDecorated(False)
        self._buy_tree.setAlternatingRowColors(True)
        self._buy_tree.itemDoubleClicked.connect(
            lambda item, col: self._on_orderbook_double_clicked(item, col, 'buy')
        )
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
    # Tab 1: Favourites
    # ------------------------------------------------------------------

    def _build_favourites_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        add_folder_btn = _action_btn("+ Folder")
        add_folder_btn.clicked.connect(self._on_add_fav_folder)
        toolbar.addWidget(add_folder_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Tree
        self._fav_tree = QTreeWidget()
        self._fav_tree.setHeaderHidden(True)
        self._fav_tree.setRootIsDecorated(True)
        self._fav_tree.setStyleSheet(_TREE_STYLE)
        self._fav_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._fav_tree.customContextMenuRequested.connect(self._on_fav_context_menu)
        self._fav_tree.itemDoubleClicked.connect(self._on_fav_double_clicked)
        layout.addWidget(self._fav_tree, 1)

        # Empty state
        self._fav_empty = QLabel("No favourites yet.\nStar items in the order book to add them.")
        self._fav_empty.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        self._fav_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fav_empty.setWordWrap(True)
        layout.addWidget(self._fav_empty)
        self._fav_empty.hide()

        return w

    def _populate_favourites(self):
        self._fav_tree.clear()
        folders = self._favourites.get_folders()
        root_ids = self._favourites.get_root_item_ids()
        lookup = self._store.item_lookup

        has_items = False

        for folder in folders:
            folder_item = QTreeWidgetItem()
            folder_item.setText(0, f"\U0001F4C1 {folder['name']}")
            folder_item.setData(0, Qt.ItemDataRole.UserRole, ("folder", folder["id"]))
            font = folder_item.font(0)
            font.setBold(True)
            folder_item.setFont(0, font)
            self._fav_tree.addTopLevelItem(folder_item)

            item_ids = self._favourites.get_folder_item_ids(folder["id"])
            for item_id in item_ids:
                has_items = True
                slim = lookup.get(item_id)
                name = slim.get("n", f"Item #{item_id}") if slim else f"Item #{item_id}"
                child = QTreeWidgetItem()
                child.setText(0, name)
                child.setData(0, Qt.ItemDataRole.UserRole, ("item", item_id))
                folder_item.addChild(child)

            folder_item.setExpanded(True)

        if root_ids:
            has_items = True
            if folders:
                sep = QTreeWidgetItem()
                sep.setText(0, "── Unfiled ──")
                sep.setForeground(0, QColor(TEXT_MUTED))
                sep.setFlags(Qt.ItemFlag.NoItemFlags)
                self._fav_tree.addTopLevelItem(sep)
            for item_id in root_ids:
                slim = lookup.get(item_id)
                name = slim.get("n", f"Item #{item_id}") if slim else f"Item #{item_id}"
                row = QTreeWidgetItem()
                row.setText(0, name)
                row.setData(0, Qt.ItemDataRole.UserRole, ("item", item_id))
                self._fav_tree.addTopLevelItem(row)

        self._fav_tree.setVisible(has_items or bool(folders))
        self._fav_empty.setVisible(not has_items and not folders)

    def _on_fav_double_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, value = data
        if kind == "item":
            self._set_tab(_TAB_BROWSE)
            self._show_order_book(value)

    def _on_add_fav_folder(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name.strip():
            self._favourites.create_folder(name.strip())

    def _on_fav_context_menu(self, pos):
        item = self._fav_tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, value = data

        menu = QMenu(self)

        if kind == "item":
            view_action = menu.addAction("View Order Book")
            remove_action = menu.addAction("Remove from Favourites")

            folders = self._favourites.get_folders()
            move_menu = None
            if folders:
                move_menu = menu.addMenu("Move to Folder")
                for folder in folders:
                    move_menu.addAction(folder["name"]).setData(folder["id"])

            action = menu.exec(self._fav_tree.viewport().mapToGlobal(pos))
            if action == view_action:
                self._set_tab(_TAB_BROWSE)
                self._show_order_book(value)
            elif action == remove_action:
                self._favourites.remove_favourite(value)
            elif move_menu and action and action.data():
                self._favourites.move_to_folder(value, action.data())

        elif kind == "folder":
            rename_action = menu.addAction("Rename")
            delete_action = menu.addAction("Delete")

            action = menu.exec(self._fav_tree.viewport().mapToGlobal(pos))
            if action == rename_action:
                from PyQt6.QtWidgets import QInputDialog
                name, ok = QInputDialog.getText(
                    self, "Rename Folder", "Folder name:",
                    text=item.text(0).replace("\U0001F4C1 ", ""),
                )
                if ok and name.strip():
                    self._favourites.rename_folder(value, name.strip())
            elif action == delete_action:
                self._favourites.delete_folder(value, keep_items=True)

    # ------------------------------------------------------------------
    # Tab 2: My Orders
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
        self._orders_tree.setStyleSheet(_TREE_STYLE)
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
        self._orders_tree.itemDoubleClicked.connect(self._on_order_double_clicked)
        self._orders_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._orders_tree.customContextMenuRequested.connect(self._on_orders_context_menu)
        layout.addWidget(self._orders_tree, 1)

        # Auth message
        self._orders_auth_label = QLabel("Log in to view your orders")
        self._orders_auth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._orders_auth_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        layout.addWidget(self._orders_auth_label)

        return w

    # ------------------------------------------------------------------
    # Tab 3: Inventory
    # ------------------------------------------------------------------

    def _build_inventory_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        self._inv_search = QLineEdit()
        self._inv_search.setPlaceholderText("Search inventory...")
        self._inv_search_timer = QTimer()
        self._inv_search_timer.setSingleShot(True)
        self._inv_search_timer.setInterval(300)
        self._inv_search_timer.timeout.connect(self._filter_inventory)
        self._inv_search.textChanged.connect(lambda: self._inv_search_timer.start())
        layout.addWidget(self._inv_search)

        self._inv_tree = QTreeWidget()
        self._inv_tree.setStyleSheet(_TREE_STYLE)
        self._inv_tree.setHeaderLabels(["Name", "Type", "Qty", "TT Value", "Demand"])
        self._inv_tree.setColumnCount(5)
        self._inv_tree.setRootIsDecorated(False)
        self._inv_tree.setAlternatingRowColors(True)
        self._inv_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._inv_tree.customContextMenuRequested.connect(self._on_inv_context_menu)
        header = self._inv_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, width in [(1, 90), (2, 60), (3, 90), (4, 90)]:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(i, width)
        self._inv_tree.itemDoubleClicked.connect(self._on_inv_double_clicked)
        layout.addWidget(self._inv_tree, 1)

        # Auth message
        self._inv_auth_label = QLabel("Log in to view your inventory")
        self._inv_auth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inv_auth_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        layout.addWidget(self._inv_auth_label)

        return w

    # ------------------------------------------------------------------
    # Tab 4: Trade Requests
    # ------------------------------------------------------------------

    def _build_trades_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        self._trades_tree = QTreeWidget()
        self._trades_tree.setStyleSheet(_TREE_STYLE)
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

    def _on_exchange_prices_changed(self, item_id: int):
        if item_id == self._current_item_id:
            self._populate_metrics()

    def _reset_metrics(self):
        """Reset metric labels to placeholder."""
        for lbl in self._metric_labels.values():
            lbl.setText("\u2014")
        self._metrics_row.hide()

    def _populate_metrics(self):
        """Fill metric panels from cached exchange prices."""
        if not self._current_item_id:
            return
        data = self._store.get_exchange_prices(self._current_item_id)
        if not data:
            return

        slim = self._store.item_lookup.get(self._current_item_id)
        is_abs = is_absolute_markup(slim) if slim else True

        period = data.get('period') or {}
        buy = data.get('buy') or {}
        sell = data.get('sell') or {}

        def _fmt(val):
            if val is None:
                return "\u2014"
            return format_markup(float(val), is_abs)

        self._metric_labels['median'].setText(_fmt(period.get('median')))
        self._metric_labels['p10'].setText(_fmt(period.get('p10')))
        self._metric_labels['wap'].setText(_fmt(period.get('wap')))
        self._metric_labels['best_buy'].setText(_fmt(buy.get('best_markup')))
        self._metric_labels['best_sell'].setText(_fmt(sell.get('best_markup')))
        self._metrics_row.show()

    def _on_loading_changed(self, what: str, loading: bool):
        if what.startswith("item_orders_") and self._current_item_id:
            self._book_loading.setVisible(loading)

    def _on_favourites_changed(self):
        if self._current_item_id:
            self._update_star_button()
        if self._active_tab == _TAB_FAVOURITES:
            self._populate_favourites()

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

        self._item_tree.setSortingEnabled(False)
        self._item_tree.setUpdatesEnabled(False)
        self._item_tree.clear()
        for item in self._store.items:
            name = item.get('n', '')
            item_type = item.get('t', '')
            category = get_top_category(item_type)

            if search and search not in name.lower():
                continue
            if selected_cat and category != selected_cat:
                continue

            row = _SortableItem()
            row.setText(0, name)
            row.setText(1, item_type)

            s_count = item.get('s', 0) or 0
            b_count = item.get('b', 0) or 0
            row.setText(2, str(s_count) if s_count else "")
            row.setData(2, Qt.ItemDataRole.UserRole + 10, s_count)
            if s_count:
                row.setForeground(2, QColor("#ef4444"))
            row.setText(3, str(b_count) if b_count else "")
            row.setData(3, Qt.ItemDataRole.UserRole + 10, b_count)
            if b_count:
                row.setForeground(3, QColor("#4ade80"))

            # Markup fallback: median → best buy → best sell
            mu_val = item.get('m')  # median from price snapshots
            if mu_val is None:
                mu_val = item.get('bb')  # best buy markup
            if mu_val is None:
                mu_val = item.get('bs')  # best sell markup
            mu_text = ''
            mu_sort = 0.0
            if mu_val is not None:
                mu_text = format_markup(mu_val, is_absolute_markup(item))
                try:
                    mu_sort = float(mu_val)
                except (TypeError, ValueError):
                    pass
            row.setText(4, mu_text)
            row.setData(4, Qt.ItemDataRole.UserRole + 10, mu_sort)

            # Updated — composite sort key: items with orders first, then by recency
            u = item.get('u')
            row.setText(5, format_age(u))
            ts = 0.0
            if u and isinstance(u, str):
                try:
                    ts = datetime.fromisoformat(
                        u.replace('Z', '+00:00')
                    ).timestamp()
                except (ValueError, OSError):
                    pass
            has_orders = 1 if (s_count + b_count) > 0 else 0
            row.setData(5, Qt.ItemDataRole.UserRole + 10, (has_orders, ts))

            row.setData(0, Qt.ItemDataRole.UserRole, item.get('i'))
            self._item_tree.addTopLevelItem(row)

        self._item_tree.setUpdatesEnabled(True)
        self._item_tree.setSortingEnabled(True)

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
        self._store.load_exchange_prices(item_id)
        self._reset_metrics()

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

    def _open_item_detail(self):
        """Open the current order book item in a detail overlay."""
        if not self._current_item_id:
            return
        slim = self._store.item_lookup.get(self._current_item_id)
        if not slim:
            return
        self._signals.open_entity_overlay.emit({
            "Name": slim.get('n', ''),
            "Type": slim.get('t', ''),
        })

    def _populate_order_book(self):
        if not self._current_item_id:
            return
        self._book_loading.hide()
        data = self._store.get_item_orders(self._current_item_id)
        if not data:
            return

        slim = self._store.item_lookup.get(self._current_item_id)
        self._populate_order_table(self._sell_tree, data.get('sell', []), slim, 'sell')
        self._populate_order_table(self._buy_tree, data.get('buy', []), slim, 'buy')

    def _populate_order_table(self, tree: QTreeWidget, orders: list[dict],
                              slim: dict | None, side: str = 'sell'):
        tree.clear()

        columns = self._get_order_columns(slim, side)
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

    def _get_order_columns(self, slim: dict | None, side: str = 'sell') -> list[tuple[str, int]]:
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
        user_label = "Buyer" if side == 'buy' else "Seller"
        cols.append((user_label, 0))  # stretch
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
            elif name in ('Seller', 'Buyer'):
                text = order.get('seller_name') or str(order.get('user_id', ''))
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

    def _on_order_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Double-click on own order: edit if active/stale, else navigate to orderbook."""
        order = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not order:
            return
        state = order.get('_state', '')
        if state in ('active', 'stale'):
            side = order.get('type', 'SELL').lower()
            self._open_order_dialog(side, order=order)
        else:
            item_id = order.get('item_id')
            if item_id:
                self._set_tab(_TAB_BROWSE)
                self._show_order_book(item_id)

    def _on_orders_context_menu(self, pos):
        """Right-click context menu for My Orders."""
        item = self._orders_tree.itemAt(pos)
        if not item:
            return
        order = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not order:
            return

        menu = QMenu(self)
        state = order.get('_state', '')
        editable = state in ('active', 'stale')

        if editable:
            edit_action = menu.addAction("Edit")
        view_action = menu.addAction("View Order Book")
        if editable:
            close_action = menu.addAction("Close")

        action = menu.exec(self._orders_tree.viewport().mapToGlobal(pos))
        if not action:
            return

        if editable and action == edit_action:
            self._open_order_dialog(order['type'], order=order)
        elif action == view_action:
            item_id = order.get('item_id')
            if item_id:
                self._set_tab(_TAB_BROWSE)
                self._show_order_book(item_id)
        elif editable and action == close_action:
            self._store.close_order(order['id'])

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
        self._inv_tree.setUpdatesEnabled(False)
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
            try:
                value = float(value) if value is not None else None
            except (TypeError, ValueError):
                value = None
            row.setText(3, format_ped(value) if value is not None else '')

            # Buy demand: best buy markup + count
            buy_count = slim.get('b', 0) if slim else 0
            if buy_count:
                best_buy = slim.get('bb')
                if best_buy is not None:
                    demand_text = f"{format_markup(best_buy, is_absolute_markup(slim))} ({buy_count})"
                else:
                    demand_text = str(buy_count)
                row.setText(4, demand_text)
                row.setForeground(4, QColor("#4ade80"))

            row.setData(0, Qt.ItemDataRole.UserRole, item_id)
            row.setData(0, Qt.ItemDataRole.UserRole + 1, inv_item)
            self._inv_tree.addTopLevelItem(row)

        self._inv_tree.setUpdatesEnabled(True)

    def _on_inv_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Navigate to order book for the inventory item."""
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        if item_id:
            self._set_tab(_TAB_BROWSE)
            self._show_order_book(item_id)

    def _sell_inventory_item(self, item_id: int):
        """Open order dialog to create a sell order for an inventory item."""
        self._open_order_dialog("SELL", item_id=item_id)

    def _on_inv_context_menu(self, pos):
        """Show right-click context menu for inventory items."""
        item = self._inv_tree.itemAt(pos)
        if not item:
            return
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not item_id:
            return

        menu = QMenu(self)
        sell_action = menu.addAction("Sell")
        view_action = menu.addAction("View Order Book")

        action = menu.exec(self._inv_tree.viewport().mapToGlobal(pos))
        if action == sell_action:
            self._sell_inventory_item(item_id)
        elif action == view_action:
            self._set_tab(_TAB_BROWSE)
            self._show_order_book(item_id)

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

    def _open_order_dialog(self, side: str, order: dict | None = None, item_id: int | None = None):
        if not self._store._client.is_authenticated():
            return
        target_id = item_id or self._current_item_id
        if not target_id:
            return

        slim = self._store.item_lookup.get(target_id)
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
    # Quick Trade (respond to orderbook order)
    # ------------------------------------------------------------------

    def _on_orderbook_double_clicked(self, item: QTreeWidgetItem, column: int, side: str):
        """Double-click on an order in the orderbook → open quick trade dialog."""
        order = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not order:
            return
        slim = self._store.item_lookup.get(self._current_item_id)
        if not slim:
            return
        trade_side = 'buy' if side == 'sell' else 'sell'
        from ..overlay.exchange_overlay import _QuickTradeDialog
        dialog = _QuickTradeDialog(
            slim=slim, order=order, side=trade_side,
            store=self._store, parent=self,
        )
        dialog.trade_submitted.connect(self._on_trade_submitted)
        dialog.show()
        self._quick_trade_dialog = dialog

    def _on_trade_submitted(self, success: bool, message: str):
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
        else:
            self._populate_item_tree()
        if self._store._client.is_authenticated():
            self._store.load_my_orders()
        self._favourites.load_from_server()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._store.stop_polling()

    def cleanup(self):
        self._store.stop_polling()
