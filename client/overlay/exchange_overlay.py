"""Exchange overlay — resizable, always-on-top overlay with browse, orders, inventory, trades."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QPushButton,
    QScrollArea, QStackedWidget, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QComboBox, QHeaderView, QSpinBox, QDoubleSpinBox,
    QCheckBox, QSizePolicy, QDialog, QFormLayout,
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QCursor

from .overlay_widget import OverlayWidget
from ..ui.icons import svg_icon, svg_pixmap
from ..core.config import save_config
from ..exchange.constants import (
    PLANETS, STATUS_COLORS, DEFAULT_PARTIAL_RATIO,
    MAX_ORDERS_PER_ITEM, compute_state,
    get_percent_undercut, get_absolute_undercut,
)
from ..exchange.order_utils import (
    is_stackable, is_percent_markup, is_absolute_markup, is_blueprint_non_l,
    is_item_tierable, is_gendered, item_has_condition, is_limited, is_pet,
    get_max_tt, get_unit_tt, compute_order_unit_price, format_ped, format_markup,
    format_ped_value, format_age, get_top_category, enrich_orders,
    TIERABLE_TYPES, GENDERED_TYPES, PLATE_SET_SIZE, ALL_CATEGORIES,
    CATEGORY_ORDER, get_category_order,
)

if TYPE_CHECKING:
    from .overlay_manager import OverlayManager
    from ..exchange.exchange_store import ExchangeStore
    from ..exchange.favourites_store import FavouritesStore

# --- Layout constants ---
MIN_WIDTH = 500
MIN_HEIGHT = 400
TITLE_H = 24
TAB_STRIP_W = 28
TAB_BTN_SIZE = 22

# --- Colors (reuse detail overlay palette) ---
BG_COLOR = "rgba(20, 20, 30, 200)"
TITLE_BG = "rgba(30, 30, 45, 220)"
TAB_BG = "rgba(25, 25, 40, 200)"
TAB_ACTIVE_BG = "rgba(60, 60, 90, 200)"
TAB_HOVER_BG = "rgba(50, 50, 70, 180)"
CONTENT_BG = "rgba(30, 30, 45, 180)"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#999999"
ACCENT = "#00ccff"
BADGE_BG = "rgba(50, 50, 70, 160)"
ROW_HOVER = "rgba(50, 50, 80, 120)"

# Status badge colors
_STATUS_LABELS = {
    'active': ('Active', STATUS_COLORS['active']),
    'stale': ('Stale', STATUS_COLORS['stale']),
    'expired': ('Expired', STATUS_COLORS['expired']),
    'terminated': ('Terminated', STATUS_COLORS['terminated']),
    'closed': ('Closed', STATUS_COLORS['closed']),
}

# --- SVG icons for tabs ---
_BROWSE_SVG = (
    '<path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0'
    ' 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5'
    ' 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>'
)
_ORDERS_SVG = (
    '<path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7'
    'v2zm0-10v2h14V7H7z"/>'
)
_INVENTORY_SVG = (
    '<path d="M20 2H4c-1 0-2 .9-2 2v3.01c0 .72.43 1.34 1 1.69V20c0 1.1 1.1 2 2 2h14'
    'c.9 0 2-.9 2-2V8.7c.57-.35 1-.97 1-1.69V4c0-1.1-1-2-2-2zm-5 12H9v-2h6v2zm5-7H4'
    'V4h16v3z"/>'
)
_TRADES_SVG = (
    '<path d="M12 5.9c1.16 0 2.1.94 2.1 2.1s-.94 2.1-2.1 2.1S9.9 9.16 9.9 8s.94-2.1'
    ' 2.1-2.1m0 9c2.97 0 6.1 1.46 6.1 2.1v1.1H5.9V17c0-.64 3.13-2.1 6.1-2.1M12 4C9.79'
    ' 4 8 5.79 8 8s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm0 9c-2.67 0-8 1.34-8 4v3h16v-3'
    'c0-2.66-5.33-4-8-4z"/>'
)

_CLOSE_SVG = (
    '<path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59'
    ' 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>'
)
_MINIMIZE_SVG = '<path d="M6 19h12v2H6z"/>'

_STAR_FILLED = '<path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>'
_STAR_OUTLINE = '<path d="M22 9.24l-7.19-.62L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24zM12 15.4l-3.76 2.27 1-4.28-3.32-2.88 4.38-.38L12 6.1l1.71 4.04 4.38.38-3.32 2.88 1 4.28L12 15.4z"/>'

_BACK_SVG = '<path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>'

# Resize grip SVG (diagonal lines)
_RESIZE_SVG = (
    '<line x1="14" y1="2" x2="2" y2="14" stroke="{color}" stroke-width="1.5"/>'
    '<line x1="14" y1="7" x2="7" y2="14" stroke="{color}" stroke-width="1.5"/>'
    '<line x1="14" y1="12" x2="12" y2="14" stroke="{color}" stroke-width="1.5"/>'
)


def _make_tree_style() -> str:
    return f"""
        QTreeWidget {{
            background: transparent;
            border: none;
            color: {TEXT_COLOR};
            font-size: 11px;
            outline: none;
        }}
        QTreeWidget::item {{
            padding: 2px 4px;
            border: none;
        }}
        QTreeWidget::item:hover {{
            background: {ROW_HOVER};
        }}
        QTreeWidget::item:selected {{
            background: {TAB_ACTIVE_BG};
        }}
        QHeaderView::section {{
            background: {TAB_BG};
            color: {TEXT_DIM};
            border: none;
            padding: 2px 4px;
            font-size: 10px;
        }}
    """


def _make_input_style() -> str:
    return f"""
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background: rgba(40, 40, 60, 200);
            border: 1px solid rgba(80, 80, 120, 150);
            border-radius: 3px;
            color: {TEXT_COLOR};
            padding: 2px 4px;
            font-size: 11px;
            min-height: 20px;
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {ACCENT};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 16px;
        }}
        QComboBox QAbstractItemView {{
            background: rgba(30, 30, 45, 240);
            color: {TEXT_COLOR};
            selection-background-color: {TAB_ACTIVE_BG};
            border: 1px solid rgba(80, 80, 120, 150);
        }}
        QCheckBox {{
            color: {TEXT_COLOR};
            font-size: 11px;
            spacing: 4px;
        }}
    """


def _make_btn(text: str, accent: bool = False, small: bool = False) -> QPushButton:
    bg = ACCENT if accent else "rgba(60, 60, 90, 200)"
    fg = "#000" if accent else TEXT_COLOR
    h = 20 if small else 24
    fs = 10 if small else 11
    btn = QPushButton(text)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {bg}; color: {fg}; border: none;
            border-radius: 3px; padding: 2px 8px;
            font-size: {fs}px; font-weight: bold;
            min-height: {h}px; max-height: {h}px;
        }}
        QPushButton:hover {{ background: {'#00aadd' if accent else 'rgba(80, 80, 110, 200)'}; }}
        QPushButton:disabled {{ background: rgba(40, 40, 60, 150); color: {TEXT_DIM}; }}
    """)
    return btn


def _status_badge(state: str) -> QLabel:
    label_text, color = _STATUS_LABELS.get(state, ('Unknown', '#666'))
    lbl = QLabel(label_text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(f"""
        background: {color}; color: #000; border-radius: 3px;
        padding: 1px 6px; font-size: 10px; font-weight: bold;
    """)
    lbl.setFixedHeight(16)
    return lbl


def _side_badge(side: str) -> QLabel:
    color = "#4ade80" if side == "SELL" else "#60a5fa"
    lbl = QLabel(side)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(f"""
        background: {color}; color: #000; border-radius: 3px;
        padding: 1px 6px; font-size: 10px; font-weight: bold;
    """)
    lbl.setFixedHeight(16)
    return lbl


# ======================================================================
# Resize grip
# ======================================================================


class _ResizeGrip(QWidget):
    """Custom resize grip for the bottom-right corner."""

    def __init__(self, overlay: ExchangeOverlay):
        super().__init__(overlay)
        self._overlay = overlay
        self._start_pos = None
        self._start_size = None
        self.setFixedSize(16, 16)
        self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(TEXT_DIM))
        pen.setWidthF(1.5)
        p.setPen(pen)
        p.drawLine(14, 2, 2, 14)
        p.drawLine(14, 7, 7, 14)
        p.drawLine(14, 12, 12, 14)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.globalPosition().toPoint()
            self._start_size = self._overlay.size()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._start_pos and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._start_pos
            new_w = max(MIN_WIDTH, self._start_size.width() + delta.x())
            new_h = max(MIN_HEIGHT, self._start_size.height() + delta.y())
            self._overlay.resize(new_w, new_h)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._start_pos is not None:
            self._start_pos = None
            self._overlay._save_size()
            event.accept()


# ======================================================================
# Main overlay
# ======================================================================


class ExchangeOverlay(OverlayWidget):
    """Resizable exchange overlay with tabbed sidebar."""

    def __init__(
        self,
        *,
        config,
        config_path: str,
        store: ExchangeStore,
        favourites: FavouritesStore,
        manager: OverlayManager | None = None,
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="exchange_overlay_position",
            manager=manager,
        )
        self._store = store
        self._favourites = favourites
        self._active_tab = 0
        self._current_item_id: int | None = None  # for order book view
        self._order_dialog: _OrderDialog | None = None

        # Restore size
        size = getattr(config, 'exchange_overlay_size', (700, 500))
        self.resize(max(MIN_WIDTH, size[0]), max(MIN_HEIGHT, size[1]))

        # Override size constraint to allow resize
        self.layout().setSizeConstraint(QVBoxLayout.SizeConstraint.SetDefaultConstraint)

        # Build UI inside _container
        self._build_ui()

        # Resize grip
        self._resize_grip = _ResizeGrip(self)
        self._position_resize_grip()

        # Connect store signals
        self._store.items_changed.connect(self._on_items_changed)
        self._store.my_orders_changed.connect(self._on_orders_changed)
        self._store.inventory_changed.connect(self._on_inventory_changed)
        self._store.trade_requests_changed.connect(self._on_trades_changed)
        self._store.item_orders_changed.connect(self._on_item_orders_changed)
        self._store.loading_changed.connect(self._on_loading_changed)
        self._store.error_occurred.connect(self._on_error)
        self._favourites.changed.connect(self._on_favourites_changed)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        title_bar = self._build_title_bar()
        layout.addWidget(title_bar)

        # Main area: tab strip + content
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Tab strip
        tab_strip = self._build_tab_strip()
        body_layout.addWidget(tab_strip)

        # Content stack
        self._content_stack = QStackedWidget()
        self._content_stack.setStyleSheet(f"background: {CONTENT_BG};")

        # Tab 0: Browse
        self._browse_widget = self._build_browse_view()
        self._content_stack.addWidget(self._browse_widget)

        # Tab 1: My Orders
        self._orders_widget = self._build_orders_view()
        self._content_stack.addWidget(self._orders_widget)

        # Tab 2: Inventory
        self._inventory_widget = self._build_inventory_view()
        self._content_stack.addWidget(self._inventory_widget)

        # Tab 3: Trade Requests
        self._trades_widget = self._build_trades_view()
        self._content_stack.addWidget(self._trades_widget)

        body_layout.addWidget(self._content_stack)
        layout.addWidget(body, 1)

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(TITLE_H)
        bar.setStyleSheet(f"background: {TITLE_BG}; border-radius: 8px 8px 0 0;")
        h = QHBoxLayout(bar)
        h.setContentsMargins(8, 0, 4, 0)
        h.setSpacing(4)

        title = QLabel("Exchange")
        title.setStyleSheet(f"color: {ACCENT}; font-size: 12px; font-weight: bold; background: transparent;")
        h.addWidget(title)
        h.addStretch()

        # Minimize button
        min_btn = QPushButton()
        min_btn.setFixedSize(18, 18)
        min_btn.setIcon(svg_icon(_MINIMIZE_SVG, TEXT_DIM, 14))
        min_btn.setStyleSheet("background: transparent; border: none;")
        min_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        min_btn.setToolTip("Minimize")
        min_btn.clicked.connect(self._on_minimize)
        h.addWidget(min_btn)

        # Close button
        close_btn = QPushButton()
        close_btn.setFixedSize(18, 18)
        close_btn.setIcon(svg_icon(_CLOSE_SVG, TEXT_DIM, 14))
        close_btn.setStyleSheet("background: transparent; border: none;")
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self._on_close)
        h.addWidget(close_btn)

        self._title_bar = bar
        return bar

    def _build_tab_strip(self) -> QWidget:
        strip = QWidget()
        strip.setFixedWidth(TAB_STRIP_W)
        strip.setStyleSheet(f"background: {TAB_BG};")
        v = QVBoxLayout(strip)
        v.setContentsMargins(3, 4, 3, 4)
        v.setSpacing(4)

        self._tab_btns: list[QPushButton] = []
        tabs = [
            (_BROWSE_SVG, "Browse"),
            (_ORDERS_SVG, "My Orders"),
            (_INVENTORY_SVG, "Inventory"),
            (_TRADES_SVG, "Trade Requests"),
        ]
        for i, (svg, tooltip) in enumerate(tabs):
            btn = QPushButton()
            btn.setFixedSize(TAB_BTN_SIZE, TAB_BTN_SIZE)
            btn.setToolTip(tooltip)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _, idx=i: self._set_tab(idx))
            v.addWidget(btn)
            self._tab_btns.append(btn)

        v.addStretch()
        self._update_tab_styles()
        return strip

    def _update_tab_styles(self):
        svgs = [_BROWSE_SVG, _ORDERS_SVG, _INVENTORY_SVG, _TRADES_SVG]
        for i, btn in enumerate(self._tab_btns):
            active = i == self._active_tab
            bg = TAB_ACTIVE_BG if active else "transparent"
            color = ACCENT if active else TEXT_DIM
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {bg}; border: none; border-radius: 4px;
                }}
                QPushButton:hover {{ background: {TAB_HOVER_BG}; }}
            """)
            btn.setIcon(svg_icon(svgs[i], color, 16))
            btn.setIconSize(QSize(16, 16))

    def _set_tab(self, index: int):
        self._active_tab = index
        self._content_stack.setCurrentIndex(index)
        self._update_tab_styles()
        # Refresh data for the active tab
        if index == 1:
            self._store.load_my_orders()
        elif index == 2:
            self._store.load_inventory()
        elif index == 3:
            self._store.load_trade_requests()

    # ------------------------------------------------------------------
    # Tab 0: Browse
    # ------------------------------------------------------------------

    def _build_browse_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Browse has two sub-views: item list and order book
        self._browse_stack = QStackedWidget()

        # Sub-view 0: Item list
        list_widget = self._build_item_list_view()
        self._browse_stack.addWidget(list_widget)

        # Sub-view 1: Order book
        book_widget = self._build_order_book_view()
        self._browse_stack.addWidget(book_widget)

        layout.addWidget(self._browse_stack, 1)
        return w

    def _build_item_list_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Filter row
        filter_row = QWidget()
        fr_layout = QHBoxLayout(filter_row)
        fr_layout.setContentsMargins(0, 0, 0, 0)
        fr_layout.setSpacing(4)

        self._browse_search = QLineEdit()
        self._browse_search.setPlaceholderText("Search items...")
        self._browse_search.setStyleSheet(_make_input_style())
        self._browse_search.textChanged.connect(self._filter_items)
        fr_layout.addWidget(self._browse_search, 1)

        self._browse_category = QComboBox()
        self._browse_category.addItem("All Categories")
        for cat in CATEGORY_ORDER:
            self._browse_category.addItem(cat)
        self._browse_category.setStyleSheet(_make_input_style())
        self._browse_category.currentIndexChanged.connect(self._filter_items)
        fr_layout.addWidget(self._browse_category)

        layout.addWidget(filter_row)

        # Item tree
        self._item_tree = QTreeWidget()
        self._item_tree.setHeaderLabels(["Name", "Type", "S/B", "Markup"])
        self._item_tree.setColumnCount(4)
        self._item_tree.setRootIsDecorated(False)
        self._item_tree.setStyleSheet(_make_tree_style())
        self._item_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        header = self._item_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 70)
        header.resizeSection(2, 50)
        header.resizeSection(3, 80)
        self._item_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._item_tree, 1)

        return w

    def _build_order_book_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header: back + item name + star
        header = QWidget()
        hdr_layout = QHBoxLayout(header)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(4)

        back_btn = QPushButton()
        back_btn.setFixedSize(22, 22)
        back_btn.setIcon(svg_icon(_BACK_SVG, TEXT_COLOR, 16))
        back_btn.setStyleSheet("background: transparent; border: none;")
        back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back_btn.setToolTip("Back to listings")
        back_btn.clicked.connect(self._back_to_listings)
        hdr_layout.addWidget(back_btn)

        self._book_item_label = QLabel()
        self._book_item_label.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 12px; font-weight: bold; background: transparent;")
        hdr_layout.addWidget(self._book_item_label, 1)

        self._book_star_btn = QPushButton()
        self._book_star_btn.setFixedSize(22, 22)
        self._book_star_btn.setStyleSheet("background: transparent; border: none;")
        self._book_star_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._book_star_btn.clicked.connect(self._toggle_current_favourite)
        hdr_layout.addWidget(self._book_star_btn)

        layout.addWidget(header)

        # Sell orders
        sell_label = QLabel("Sell Orders")
        sell_label.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; background: transparent; padding: 2px 0;")
        layout.addWidget(sell_label)

        self._sell_tree = QTreeWidget()
        self._sell_tree.setRootIsDecorated(False)
        self._sell_tree.setStyleSheet(_make_tree_style())
        layout.addWidget(self._sell_tree, 1)

        # Buy orders
        buy_label = QLabel("Buy Orders")
        buy_label.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; background: transparent; padding: 2px 0;")
        layout.addWidget(buy_label)

        self._buy_tree = QTreeWidget()
        self._buy_tree.setRootIsDecorated(False)
        self._buy_tree.setStyleSheet(_make_tree_style())
        layout.addWidget(self._buy_tree, 1)

        # Action buttons
        btn_row = QWidget()
        br_layout = QHBoxLayout(btn_row)
        br_layout.setContentsMargins(0, 2, 0, 0)
        br_layout.setSpacing(4)

        self._create_sell_btn = _make_btn("Create Sell Order", accent=True, small=True)
        self._create_sell_btn.clicked.connect(lambda: self._open_order_dialog("SELL"))
        br_layout.addWidget(self._create_sell_btn)

        self._create_buy_btn = _make_btn("Create Buy Order", small=True)
        self._create_buy_btn.clicked.connect(lambda: self._open_order_dialog("BUY"))
        br_layout.addWidget(self._create_buy_btn)

        layout.addWidget(btn_row)

        # Loading label
        self._book_loading = QLabel("Loading...")
        self._book_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._book_loading.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; background: transparent;")
        self._book_loading.hide()
        layout.addWidget(self._book_loading)

        return w

    # ------------------------------------------------------------------
    # Tab 1: My Orders
    # ------------------------------------------------------------------

    def _build_orders_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Filter row
        filter_row = QWidget()
        fr_layout = QHBoxLayout(filter_row)
        fr_layout.setContentsMargins(0, 0, 0, 0)
        fr_layout.setSpacing(4)

        self._orders_filter = "all"
        for label, filt in [("All", "all"), ("Buy", "BUY"), ("Sell", "SELL")]:
            btn = _make_btn(label, accent=(filt == "all"), small=True)
            btn.clicked.connect(lambda _, f=filt: self._set_order_filter(f))
            fr_layout.addWidget(btn)
        self._order_filter_btns = fr_layout

        fr_layout.addStretch()

        bump_all_btn = _make_btn("Bump All", small=True)
        bump_all_btn.clicked.connect(self._on_bump_all)
        fr_layout.addWidget(bump_all_btn)
        self._bump_all_btn = bump_all_btn

        layout.addWidget(filter_row)

        # Summary
        self._orders_summary = QLabel()
        self._orders_summary.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; background: transparent;")
        layout.addWidget(self._orders_summary)

        # Orders tree
        self._orders_tree = QTreeWidget()
        self._orders_tree.setHeaderLabels(["Item", "Side", "Qty", "Markup", "Planet", "Status", "Updated"])
        self._orders_tree.setColumnCount(7)
        self._orders_tree.setRootIsDecorated(False)
        self._orders_tree.setStyleSheet(_make_tree_style())
        header = self._orders_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 40)
        header.resizeSection(2, 40)
        header.resizeSection(3, 70)
        header.resizeSection(4, 60)
        header.resizeSection(5, 60)
        header.resizeSection(6, 50)
        layout.addWidget(self._orders_tree, 1)

        # Auth message
        self._orders_auth_label = QLabel("Log in to view your orders")
        self._orders_auth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._orders_auth_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; background: transparent;")
        layout.addWidget(self._orders_auth_label)

        return w

    # ------------------------------------------------------------------
    # Tab 2: Inventory
    # ------------------------------------------------------------------

    def _build_inventory_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Search
        self._inv_search = QLineEdit()
        self._inv_search.setPlaceholderText("Search inventory...")
        self._inv_search.setStyleSheet(_make_input_style())
        self._inv_search.textChanged.connect(self._filter_inventory)
        layout.addWidget(self._inv_search)

        # Inventory tree
        self._inv_tree = QTreeWidget()
        self._inv_tree.setHeaderLabels(["Name", "Type", "Qty", "TT Value", "Orders"])
        self._inv_tree.setColumnCount(5)
        self._inv_tree.setRootIsDecorated(False)
        self._inv_tree.setStyleSheet(_make_tree_style())
        header = self._inv_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 5):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 70)
        header.resizeSection(2, 40)
        header.resizeSection(3, 70)
        header.resizeSection(4, 50)
        layout.addWidget(self._inv_tree, 1)

        # Auth message
        self._inv_auth_label = QLabel("Log in to view your inventory")
        self._inv_auth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inv_auth_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; background: transparent;")
        layout.addWidget(self._inv_auth_label)

        return w

    # ------------------------------------------------------------------
    # Tab 3: Trade Requests
    # ------------------------------------------------------------------

    def _build_trades_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._trades_tree = QTreeWidget()
        self._trades_tree.setHeaderLabels(["Partner", "Items", "Status", "Created"])
        self._trades_tree.setColumnCount(4)
        self._trades_tree.setRootIsDecorated(False)
        self._trades_tree.setStyleSheet(_make_tree_style())
        header = self._trades_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 4):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 40)
        header.resizeSection(2, 60)
        header.resizeSection(3, 50)
        layout.addWidget(self._trades_tree, 1)

        # Auth message
        self._trades_auth_label = QLabel("Log in to view trade requests")
        self._trades_auth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._trades_auth_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; background: transparent;")
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

    def _on_error(self, context: str, message: str):
        pass  # Could show inline error labels

    def _on_favourites_changed(self):
        # Refresh star icons if order book is open
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
        # Write buttons
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

            # Sell/Buy counts
            s_count = item.get('s', 0) or 0
            b_count = item.get('b', 0) or 0
            row.setText(2, f"{s_count}/{b_count}")

            # Best markup
            sell_mu = item.get('sv')
            buy_mu = item.get('bv')
            mu_text = ''
            if sell_mu is not None:
                mu_text = format_markup(sell_mu, is_absolute_markup(item))
            elif buy_mu is not None:
                mu_text = format_markup(buy_mu, is_absolute_markup(item))
            row.setText(3, mu_text)

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
            self._book_star_btn.setIcon(svg_icon(_STAR_FILLED, "#fbbf24", 16))
            self._book_star_btn.setToolTip("Remove from favourites")
        else:
            self._book_star_btn.setIcon(svg_icon(_STAR_OUTLINE, TEXT_DIM, 16))
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

    def _populate_order_table(self, tree: QTreeWidget, orders: list[dict], slim: dict | None):
        tree.clear()

        # Build dynamic column list
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
        """Build column list based on item type. Returns [(name, width)]. width=0 means stretch."""
        cols: list[tuple[str, int]] = []

        if is_stackable(slim):
            cols.append(("Qty", 40))

        if is_item_tierable(slim):
            cols.append(("Tier", 35))
            cols.append(("TiR", 35))

        if is_gendered(slim):
            cols.append(("Gender", 45))

        if slim and slim.get('t') == 'ArmorPlating':
            cols.append(("Set", 30))

        if is_pet(slim):
            cols.append(("Lvl", 30))

        if is_blueprint_non_l(slim):
            cols.append(("QR", 30))

        cols.append(("Value", 55))
        cols.append(("Markup", 65))
        cols.append(("Total", 60))
        cols.append(("Planet", 50))
        cols.append(("Seller", 0))  # stretch
        cols.append(("Status", 50))
        cols.append(("Updated", 45))
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

            # Color status column
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

        # Filter
        if self._orders_filter == "BUY":
            orders = [o for o in orders if o.get('type') == 'BUY']
        elif self._orders_filter == "SELL":
            orders = [o for o in orders if o.get('type') == 'SELL']

        # Sort: status priority, then category
        state_priority = {'active': 0, 'stale': 1, 'expired': 2, 'terminated': 3, 'closed': 4}
        orders.sort(key=lambda o: (
            state_priority.get(o.get('_state', ''), 5),
            o.get('_category_order', 99),
        ))

        # Summary
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

            # Existing sell order count for this item
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
        """Open order creation/edit dialog."""
        if not self._store._client.is_authenticated():
            return
        if not self._current_item_id:
            return

        slim = self._store.item_lookup.get(self._current_item_id)
        if not slim:
            return

        dialog = _OrderDialog(
            slim=slim,
            side=side,
            order=order,
            store=self._store,
            parent=self,
        )
        dialog.order_submitted.connect(self._on_order_submitted)
        dialog.show()
        self._order_dialog = dialog

    def _on_order_submitted(self, success: bool, message: str):
        if success and self._current_item_id:
            # Refresh order book
            self._store.load_item_orders(self._current_item_id)

    # ------------------------------------------------------------------
    # Drag (title bar only) + Resize
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        # Only allow drag from title bar region
        if event.button() == Qt.MouseButton.LeftButton:
            local_y = event.position().y()
            if local_y <= TITLE_H:
                self._drag_pos = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
            else:
                self._drag_pos = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_resize_grip()

    def _position_resize_grip(self):
        if hasattr(self, '_resize_grip'):
            self._resize_grip.move(
                self.width() - self._resize_grip.width() - 2,
                self.height() - self._resize_grip.height() - 2,
            )

    def _save_size(self):
        self._config.exchange_overlay_size = (self.width(), self.height())
        save_config(self._config, self._config_path)

    def _on_minimize(self):
        self.set_wants_visible(False)

    def _on_close(self):
        self.set_wants_visible(False)

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------

    def set_wants_visible(self, visible: bool):
        super().set_wants_visible(visible)
        if visible:
            self._update_auth_visibility()
            self._store.start_polling()
            if not self._store.items:
                self._store.load_items()
            if self._store._client.is_authenticated():
                self._store.load_my_orders()
                self._store.load_inventory()
                self._store.load_trade_requests()
            self._favourites.load_from_server()
        else:
            self._store.stop_polling()


# ======================================================================
# Order Dialog
# ======================================================================


class _OrderDialog(QWidget):
    """Modal-style order creation/edit dialog."""

    order_submitted = pyqtSignal(bool, str)

    def __init__(self, *, slim: dict, side: str, order: dict | None,
                 store: ExchangeStore, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._slim = slim
        self._side = side
        self._order = order  # None for create, dict for edit
        self._store = store

        self._build_ui()
        self._load_suggestions()

        # Position near parent
        if parent:
            pos = parent.pos()
            self.move(pos.x() + 30, pos.y() + 40)

    def _build_ui(self):
        container = QWidget(self)
        container.setStyleSheet(
            f"background-color: rgba(25, 25, 40, 240); border-radius: 8px; padding: 8px;"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # Title
        mode = "Edit Order" if self._order else "Create Order"
        title = QLabel(f"{mode} — {self._side}")
        title.setStyleSheet(f"color: {ACCENT}; font-size: 13px; font-weight: bold;")
        layout.addWidget(title)

        # Item info
        name = self._slim.get('n', '')
        item_type = self._slim.get('t', '')
        max_tt = get_max_tt(self._slim)
        tt_str = f" · MaxTT: {format_ped(max_tt)} PED" if max_tt is not None else ""
        info = QLabel(f"{name} ({item_type}){tt_str}")
        info.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Form
        form = QWidget()
        form.setStyleSheet(_make_input_style())
        fl = QFormLayout(form)
        fl.setContentsMargins(0, 4, 0, 0)
        fl.setSpacing(4)
        fl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        label_style = f"color: {TEXT_DIM}; font-size: 11px;"

        # Planet
        self._planet_combo = QComboBox()
        self._planet_combo.addItem("Any Planet")
        for p in PLANETS:
            self._planet_combo.addItem(p)
        lbl = QLabel("Planet:")
        lbl.setStyleSheet(label_style)
        fl.addRow(lbl, self._planet_combo)

        # Quantity (stackable only)
        self._qty_spin = QSpinBox()
        self._qty_spin.setRange(1, 999999)
        self._qty_spin.setValue(1)
        self._qty_lbl = QLabel("Quantity:")
        self._qty_lbl.setStyleSheet(label_style)
        fl.addRow(self._qty_lbl, self._qty_spin)
        stackable = is_stackable(self._slim)
        self._qty_spin.setVisible(stackable)
        self._qty_lbl.setVisible(stackable)

        # Allow Partial
        self._partial_check = QCheckBox("Allow partial trades")
        self._partial_lbl = QLabel("")
        fl.addRow(self._partial_lbl, self._partial_check)
        self._partial_check.setVisible(stackable)
        self._partial_lbl.setVisible(stackable)

        # Min Quantity
        self._min_qty_spin = QSpinBox()
        self._min_qty_spin.setRange(1, 999999)
        self._min_qty_lbl = QLabel("Min Qty:")
        self._min_qty_lbl.setStyleSheet(label_style)
        fl.addRow(self._min_qty_lbl, self._min_qty_spin)
        self._min_qty_spin.setVisible(False)
        self._min_qty_lbl.setVisible(False)
        self._partial_check.toggled.connect(self._on_partial_toggled)
        self._qty_spin.valueChanged.connect(self._update_min_qty_range)

        # Gender (gendered only)
        self._gender_combo = QComboBox()
        self._gender_combo.addItems(["Male", "Female"])
        self._gender_lbl = QLabel("Gender:")
        self._gender_lbl.setStyleSheet(label_style)
        fl.addRow(self._gender_lbl, self._gender_combo)
        gendered = is_gendered(self._slim)
        self._gender_combo.setVisible(gendered)
        self._gender_lbl.setVisible(gendered)
        # If item has fixed gender, disable combo
        item_gender = self._slim.get('g')
        if item_gender in ('Male', 'Female'):
            self._gender_combo.setCurrentText(item_gender)
            self._gender_combo.setEnabled(False)
        elif item_gender == 'Neutral' or not item_gender:
            self._gender_combo.setVisible(False)
            self._gender_lbl.setVisible(False)

        # Tier (tierable only)
        self._tier_spin = QSpinBox()
        self._tier_spin.setRange(0, 10)
        tier_label = "Min. Tier:" if self._side == "BUY" else "Tier:"
        self._tier_lbl = QLabel(tier_label)
        self._tier_lbl.setStyleSheet(label_style)
        fl.addRow(self._tier_lbl, self._tier_spin)
        tierable = is_item_tierable(self._slim)
        self._tier_spin.setVisible(tierable)
        self._tier_lbl.setVisible(tierable)

        # TiR (tierable only)
        self._tir_spin = QSpinBox()
        max_tir = 4000 if is_limited(self._slim.get('n', '')) else 200
        self._tir_spin.setRange(0, max_tir)
        tir_label = "Min. TiR:" if self._side == "BUY" else "TiR:"
        self._tir_lbl = QLabel(tir_label)
        self._tir_lbl.setStyleSheet(label_style)
        fl.addRow(self._tir_lbl, self._tir_spin)
        self._tir_spin.setVisible(tierable)
        self._tir_lbl.setVisible(tierable)

        # QR (non-L blueprint only)
        bp_non_l = is_blueprint_non_l(self._slim)
        if bp_non_l and self._side == "BUY":
            self._qr_combo = QComboBox()
            ranges = ["0-9", "10-19", "20-29", "30-39", "40-49",
                       "50-59", "60-69", "70-79", "80-89", "90-99", "100"]
            self._qr_combo.addItems(ranges)
            self._qr_lbl = QLabel("QR Range:")
            self._qr_lbl.setStyleSheet(label_style)
            fl.addRow(self._qr_lbl, self._qr_combo)
            self._qr_spin = None
        elif bp_non_l:
            self._qr_spin = QSpinBox()
            self._qr_spin.setRange(1, 100)
            self._qr_lbl = QLabel("QR:")
            self._qr_lbl.setStyleSheet(label_style)
            fl.addRow(self._qr_lbl, self._qr_spin)
            self._qr_combo = None
        else:
            self._qr_spin = None
            self._qr_combo = None

        # CurrentTT (condition items, non-stackable)
        has_cond = item_has_condition(self._slim) and not is_stackable(self._slim)
        self._tt_spin = QDoubleSpinBox()
        self._tt_spin.setDecimals(2)
        self._tt_spin.setRange(0, max_tt or 999)
        if max_tt:
            self._tt_spin.setValue(max_tt)
        self._tt_lbl = QLabel("Current TT:")
        self._tt_lbl.setStyleSheet(label_style)
        fl.addRow(self._tt_lbl, self._tt_spin)
        self._tt_spin.setVisible(has_cond)
        self._tt_lbl.setVisible(has_cond)

        # Full Set (ArmorPlating)
        self._set_check = QCheckBox(f"Full set ({PLATE_SET_SIZE})")
        self._set_lbl = QLabel("")
        fl.addRow(self._set_lbl, self._set_check)
        is_plating = self._slim.get('t') == 'ArmorPlating'
        self._set_check.setVisible(is_plating)
        self._set_lbl.setVisible(is_plating)

        # Pet Level
        self._pet_spin = QSpinBox()
        self._pet_spin.setRange(0, 999)
        self._pet_lbl = QLabel("Pet Level:")
        self._pet_lbl.setStyleSheet(label_style)
        fl.addRow(self._pet_lbl, self._pet_spin)
        is_pet_item = is_pet(self._slim)
        self._pet_spin.setVisible(is_pet_item)
        self._pet_lbl.setVisible(is_pet_item)

        # Markup
        self._is_percent = is_percent_markup(self._slim)
        self._markup_spin = QDoubleSpinBox()
        self._markup_spin.setDecimals(2)
        if self._is_percent:
            self._markup_spin.setRange(100.0, 99999999.0)
            self._markup_spin.setValue(100.0)
            self._markup_spin.setSuffix(" %")
        else:
            self._markup_spin.setRange(0.0, 99999999.0)
            self._markup_spin.setValue(0.0)
            self._markup_spin.setSuffix(" PED")
        self._markup_spin.setSingleStep(0.01)
        mu_lbl = QLabel("Markup:")
        mu_lbl.setStyleSheet(label_style)
        fl.addRow(mu_lbl, self._markup_spin)
        self._markup_spin.valueChanged.connect(self._update_price_preview)

        layout.addWidget(form)

        # Suggestion buttons
        self._suggest_row = QWidget()
        sr_layout = QHBoxLayout(self._suggest_row)
        sr_layout.setContentsMargins(0, 0, 0, 0)
        sr_layout.setSpacing(4)
        self._match_btn = _make_btn("Match Best", small=True)
        self._match_btn.clicked.connect(self._on_match_best)
        sr_layout.addWidget(self._match_btn)
        undercut_text = "Undercut" if self._side == "SELL" else "Outbid"
        self._undercut_btn = _make_btn(undercut_text, small=True)
        self._undercut_btn.clicked.connect(self._on_undercut)
        sr_layout.addWidget(self._undercut_btn)
        sr_layout.addStretch()
        self._suggest_row.hide()
        layout.addWidget(self._suggest_row)

        # Price preview
        self._price_label = QLabel()
        self._price_label.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold;")
        layout.addWidget(self._price_label)

        # Error label
        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: #ef4444; font-size: 10px;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        # Action buttons
        btn_row = QWidget()
        br = QHBoxLayout(btn_row)
        br.setContentsMargins(0, 4, 0, 0)
        br.setSpacing(4)

        submit_text = "Save" if self._order else "Create"
        self._submit_btn = _make_btn(submit_text, accent=True)
        self._submit_btn.clicked.connect(self._on_submit)
        br.addWidget(self._submit_btn)

        cancel_btn = _make_btn("Cancel")
        cancel_btn.clicked.connect(self.close)
        br.addWidget(cancel_btn)
        br.addStretch()
        layout.addWidget(btn_row)

        self.setFixedWidth(340)

        # Pre-fill for edit mode
        if self._order:
            self._prefill_order()

        self._update_price_preview()

    def _prefill_order(self):
        o = self._order
        if not o:
            return
        # Planet
        planet = o.get('planet')
        if planet:
            idx = self._planet_combo.findText(planet)
            if idx >= 0:
                self._planet_combo.setCurrentIndex(idx)
        # Quantity
        self._qty_spin.setValue(o.get('quantity', 1))
        # Min quantity
        if o.get('min_quantity'):
            self._partial_check.setChecked(True)
            self._min_qty_spin.setValue(o['min_quantity'])
        # Markup
        self._markup_spin.setValue(o.get('markup', 100 if self._is_percent else 0))
        # Details
        details = o.get('details') or {}
        if details.get('Gender'):
            self._gender_combo.setCurrentText(details['Gender'])
        if details.get('Tier') is not None:
            self._tier_spin.setValue(int(details['Tier']))
        if details.get('TierIncreaseRate') is not None:
            self._tir_spin.setValue(int(details['TierIncreaseRate']))
        if details.get('QualityRating') is not None:
            if self._qr_spin:
                self._qr_spin.setValue(int(details['QualityRating']))
        if details.get('CurrentTT') is not None:
            self._tt_spin.setValue(float(details['CurrentTT']))
        if details.get('is_set'):
            self._set_check.setChecked(True)
        pet = details.get('Pet') or {}
        if pet.get('Level') is not None:
            self._pet_spin.setValue(int(pet['Level']))

    def _on_partial_toggled(self, checked):
        self._min_qty_spin.setVisible(checked)
        self._min_qty_lbl.setVisible(checked)
        if checked:
            qty = self._qty_spin.value()
            self._min_qty_spin.setValue(max(1, int(qty * DEFAULT_PARTIAL_RATIO)))
            self._update_min_qty_range()

    def _update_min_qty_range(self):
        self._min_qty_spin.setMaximum(self._qty_spin.value())

    def _update_price_preview(self):
        mu = self._markup_spin.value()
        max_tt = get_max_tt(self._slim)
        if max_tt is None:
            self._price_label.setText("")
            return

        # Build a pseudo-order for computation
        pseudo = {'details': self._build_details(), 'quantity': self._qty_spin.value()}
        unit = compute_order_unit_price(self._slim, mu, pseudo)
        if unit is not None:
            text = f"Unit: {format_ped(unit)} PED"
            if is_stackable(self._slim):
                qty = self._qty_spin.value()
                total = unit * qty
                text += f" · Total: {format_ped(total)} PED"
            self._price_label.setText(text)
        else:
            self._price_label.setText("")

    # --- Suggestions ---

    def _load_suggestions(self):
        """Load order book for undercut suggestions."""
        item_id = self._slim.get('i')
        if item_id:
            self._store.item_orders_changed.connect(self._on_suggestions_loaded)
            # Use cached if available, otherwise load
            cached = self._store.get_item_orders(item_id)
            if cached:
                self._apply_suggestions(cached)
            else:
                self._store.load_item_orders(item_id)

    def _on_suggestions_loaded(self, item_id: int):
        if item_id == self._slim.get('i'):
            data = self._store.get_item_orders(item_id)
            if data:
                self._apply_suggestions(data)

    def _apply_suggestions(self, data: dict):
        self._best_buy = None
        self._best_sell = None

        buy_orders = data.get('buy', [])
        sell_orders = data.get('sell', [])

        if buy_orders:
            markups = [o.get('markup', 0) for o in buy_orders if o.get('markup') is not None]
            if markups:
                self._best_buy = max(markups)

        if sell_orders:
            markups = [o.get('markup', 0) for o in sell_orders if o.get('markup') is not None]
            if markups:
                self._best_sell = min(markups)

        # Show suggestion buttons if relevant orders exist
        if self._side == "SELL" and self._best_sell is not None:
            self._suggest_row.show()
        elif self._side == "BUY" and self._best_buy is not None:
            self._suggest_row.show()
        else:
            self._suggest_row.hide()

    def _on_match_best(self):
        if self._side == "SELL" and self._best_sell is not None:
            self._markup_spin.setValue(self._best_sell)
        elif self._side == "BUY" and self._best_buy is not None:
            self._markup_spin.setValue(self._best_buy)

    def _on_undercut(self):
        if self._side == "SELL" and self._best_sell is not None:
            if self._is_percent:
                amount = get_percent_undercut(self._best_sell)
                new_val = max(100.0, round(self._best_sell - amount, 2))
            else:
                amount = get_absolute_undercut(self._best_sell)
                new_val = max(0.0, round(self._best_sell - amount, 2))
            self._markup_spin.setValue(new_val)
        elif self._side == "BUY" and self._best_buy is not None:
            if self._is_percent:
                amount = get_percent_undercut(self._best_buy)
            else:
                amount = get_absolute_undercut(self._best_buy)
            new_val = round(self._best_buy + amount, 2)
            self._markup_spin.setValue(new_val)

    # --- Submit ---

    def _build_details(self) -> dict | None:
        details = {}
        if is_item_tierable(self._slim) and self._tier_spin.isVisible():
            t = self._tier_spin.value()
            if t > 0:
                details['Tier'] = t
            tir = self._tir_spin.value()
            if tir > 0:
                details['TierIncreaseRate'] = tir

        if self._qr_spin and self._qr_spin.isVisible():
            details['QualityRating'] = self._qr_spin.value()
        elif self._qr_combo and hasattr(self, '_qr_combo'):
            # Buy QR range — store as the range string
            details['QualityRating'] = self._qr_combo.currentText()

        if self._tt_spin.isVisible():
            details['CurrentTT'] = round(self._tt_spin.value(), 2)

        if self._set_check.isVisible() and self._set_check.isChecked():
            details['is_set'] = True

        if self._pet_spin.isVisible():
            lvl = self._pet_spin.value()
            if lvl > 0:
                details['Pet'] = {'Level': lvl}

        if self._gender_combo.isVisible() and self._gender_combo.isEnabled():
            details['Gender'] = self._gender_combo.currentText()

        return details if details else None

    def _on_submit(self):
        self._error_label.hide()
        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("Submitting...")

        planet = self._planet_combo.currentText()
        if planet == "Any Planet":
            planet = None

        data = {
            'markup': round(self._markup_spin.value(), 2),
            'quantity': self._qty_spin.value() if is_stackable(self._slim) else 1,
            'planet': planet,
            'details': self._build_details(),
        }

        if self._partial_check.isChecked() and self._min_qty_spin.isVisible():
            data['min_quantity'] = self._min_qty_spin.value()

        if self._order:
            # Edit mode
            self._store.edit_order(self._order['id'], data, callback=self._on_result)
        else:
            # Create mode
            data['type'] = self._side
            data['item_id'] = self._slim.get('i')
            self._store.create_order(data, callback=self._on_result)

    def _on_result(self, success: bool, result):
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("Save" if self._order else "Create")
        if success:
            self.order_submitted.emit(True, "Success")
            self.close()
        else:
            self._error_label.setText(str(result))
            self._error_label.show()
            self.order_submitted.emit(False, str(result))
