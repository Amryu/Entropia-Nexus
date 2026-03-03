"""Exchange overlay — resizable, always-on-top overlay with browse, orders, inventory, trades."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QPushButton,
    QScrollArea, QStackedWidget, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QComboBox, QHeaderView, QSpinBox, QDoubleSpinBox,
    QCheckBox, QSizePolicy, QDialog, QFormLayout, QMenu,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle,
)
from PyQt6.QtCore import Qt, QSize, QTimer, QModelIndex, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QCursor, QPainter, QFontMetrics

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
TITLE_H = 28
TAB_STRIP_W = 28
TAB_BTN_SIZE = 22

# --- Tab indices ---
_TAB_BROWSE = 0
_TAB_FAVOURITES = 1
_TAB_ORDERS = 2
_TAB_INVENTORY = 3
_TAB_TRADES = 4

# --- Colors (match detail overlay palette) ---
BG_COLOR = "rgba(20, 20, 30, 180)"
TITLE_BG = "rgba(30, 30, 45, 200)"
TAB_BG = "rgba(25, 25, 40, 180)"
TAB_ACTIVE_BG = "rgba(60, 60, 90, 200)"
TAB_HOVER_BG = "rgba(50, 50, 70, 180)"
CONTENT_BG = "rgba(30, 30, 45, 160)"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#999999"
ACCENT = "#00ccff"
BADGE_BG = "rgba(50, 50, 70, 160)"
ROW_HOVER = "rgba(50, 50, 80, 120)"

# Button style matching detail overlay
_TITLE_BTN_STYLE = (
    "QPushButton {"
    "  background: transparent; border: none; border-radius: 3px;"
    "  padding: 0px; margin: 0px;"
    "}"
    "QPushButton:hover {"
    f"  background-color: {TAB_HOVER_BG};"
    "}"
)

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
_CHEVRON_DOWN_SVG = '<path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z"/>'
_CHEVRON_RIGHT_SVG = '<path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>'

_FAVOURITES_SVG = '<path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>'
_STAR_FILLED = _FAVOURITES_SVG
_STAR_OUTLINE = '<path d="M22 9.24l-7.19-.62L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24zM12 15.4l-3.76 2.27 1-4.28-3.32-2.88 4.38-.38L12 6.1l1.71 4.04 4.38.38-3.32 2.88 1 4.28L12 15.4z"/>'

_EXCHANGE_SVG = (
    '<path d="M4 6h16v2H4z"/>'
    '<path d="M2 8l2-2h16l2 2v1H2z"/>'
    '<path d="M4 9v10h16V9h-2v6H6V9z" opacity="0.8"/>'
    '<path d="M8 12h3v3H8z"/>'
    '<path d="M14 9h4v2h-4z" opacity="0.6"/>'
)
_BACK_SVG = '<path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>'

# Resize grip SVG (diagonal lines)
_RESIZE_SVG = (
    '<line x1="14" y1="2" x2="2" y2="14" stroke="{color}" stroke-width="1.5"/>'
    '<line x1="14" y1="7" x2="7" y2="14" stroke="{color}" stroke-width="1.5"/>'
    '<line x1="14" y1="12" x2="12" y2="14" stroke="{color}" stroke-width="1.5"/>'
)


# Colors matching the web exchange S/B display
_SELL_COLOR = QColor("#ef4444")   # red for sell count
_BUY_COLOR = QColor("#4ade80")    # green for buy count
_DIM_ALPHA = 77                   # ~0.3 opacity when count is 0
_SLASH_COLOR = QColor(TEXT_DIM)


class _SellBuyDelegate(QStyledItemDelegate):
    """Custom delegate to paint S/B column with colored sell (red) / buy (green) counts."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        # Let the style draw the default item background (hover, selection, alternating rows)
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else QApplication.style()
        option.text = ""
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, option, painter, option.widget)

        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if "/" not in text:
            return

        parts = text.split("/", 1)
        s_text = parts[0].strip()
        b_text = parts[1].strip() if len(parts) > 1 else "0"

        try:
            s_val = int(s_text)
            b_val = int(b_text)
        except ValueError:
            return

        painter.save()
        painter.setFont(option.font)
        fm = QFontMetrics(option.font)

        rect = option.rect
        slash_w = fm.horizontalAdvance("/")
        s_w = fm.horizontalAdvance(s_text)
        b_w = fm.horizontalAdvance(b_text)
        total_w = s_w + slash_w + b_w
        x_start = rect.left() + (rect.width() - total_w) // 2
        y = rect.top() + (rect.height() + fm.ascent() - fm.descent()) // 2

        # Sell count (red, dim if 0)
        sc = QColor(_SELL_COLOR)
        if s_val == 0:
            sc.setAlpha(_DIM_ALPHA)
        painter.setPen(sc)
        painter.drawText(x_start, y, s_text)

        # Slash
        painter.setPen(_SLASH_COLOR)
        painter.drawText(x_start + s_w, y, "/")

        # Buy count (green, dim if 0)
        bc = QColor(_BUY_COLOR)
        if b_val == 0:
            bc.setAlpha(_DIM_ALPHA)
        painter.setPen(bc)
        painter.drawText(x_start + s_w + slash_w, y, b_text)

        painter.restore()


class _SortableItem(QTreeWidgetItem):
    """Tree item that sorts numerically for columns with numeric UserRole data."""

    def __lt__(self, other):
        tree = self.treeWidget()
        if tree is None:
            return super().__lt__(other)
        col = tree.sortColumn()
        # Try numeric sort via UserRole+10 (sort key)
        a = self.data(col, Qt.ItemDataRole.UserRole + 10)
        b = other.data(col, Qt.ItemDataRole.UserRole + 10)
        if a is not None and b is not None:
            return a < b
        return super().__lt__(other)


def _make_tree_style() -> str:
    return f"""
        QTreeWidget {{
            background: transparent;
            border: none;
            color: {TEXT_COLOR};
            font-size: 11px;
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
            color: #ffffff;
        }}
        QHeaderView::section {{
            background: {TAB_BG};
            color: {TEXT_DIM};
            border: none;
            border-right: 1px solid rgba(80, 80, 120, 80);
            padding: 4px 8px;
            font-size: 11px;
            min-height: 22px;
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


_INFO_SVG = '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>'


class ExchangeOverlay(OverlayWidget):
    """Resizable exchange overlay with tabbed sidebar."""

    open_entity = pyqtSignal(dict)  # open item in detail overlay

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
        self._quick_trade_dialog: _QuickTradeDialog | None = None

        # Restore size
        size = getattr(config, 'exchange_overlay_size', (700, 500))
        self.resize(max(MIN_WIDTH, size[0]), max(MIN_HEIGHT, size[1]))

        # Override size constraint to allow resize
        self.layout().setSizeConstraint(QVBoxLayout.SizeConstraint.SetDefaultConstraint)

        # Override base class container: remove padding, match detail overlay alpha
        self._container.setStyleSheet(
            "background-color: rgba(20, 20, 30, 180); "
            "border-radius: 8px; padding: 0px;"
        )

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
        self._store.exchange_prices_changed.connect(self._on_exchange_prices_changed)
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
        self._body = QWidget()
        body_layout = QHBoxLayout(self._body)
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

        # Tab 1: Favourites
        self._favourites_widget = self._build_favourites_view()
        self._content_stack.addWidget(self._favourites_widget)

        # Tab 2: My Orders
        self._orders_widget = self._build_orders_view()
        self._content_stack.addWidget(self._orders_widget)

        # Tab 3: Inventory
        self._inventory_widget = self._build_inventory_view()
        self._content_stack.addWidget(self._inventory_widget)

        # Tab 4: Trade Requests
        self._trades_widget = self._build_trades_view()
        self._content_stack.addWidget(self._trades_widget)

        body_layout.addWidget(self._content_stack)
        layout.addWidget(self._body, 1)

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(TITLE_H)
        bar.setStyleSheet(
            f"background-color: {TITLE_BG};"
            " border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        h = QHBoxLayout(bar)
        h.setContentsMargins(4, 0, 4, 0)
        h.setSpacing(4)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(svg_icon(_EXCHANGE_SVG, ACCENT, 14).pixmap(14, 14))
        icon_lbl.setStyleSheet("background: transparent;")
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        h.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        title = QLabel("Exchange")
        title.setStyleSheet(
            f"color: {ACCENT}; font-size: 13px; font-weight: bold; background: transparent;"
        )
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        h.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)

        # Close button
        close_btn = QPushButton()
        close_btn.setFixedSize(18, 18)
        close_btn.setIcon(svg_icon(_CLOSE_SVG, TEXT_DIM, 14))
        close_btn.setStyleSheet(_TITLE_BTN_STYLE)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self._on_close)
        h.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._title_bar = bar
        return bar

    def _build_tab_strip(self) -> QWidget:
        strip = QWidget()
        strip.setFixedWidth(TAB_STRIP_W)
        strip.setStyleSheet(f"background: {TAB_BG}; border-bottom-left-radius: 8px;")
        v = QVBoxLayout(strip)
        v.setContentsMargins(3, 4, 3, 4)
        v.setSpacing(2)

        self._tab_btns: list[QPushButton] = []
        tabs = [
            (_BROWSE_SVG, "Browse"),
            (_FAVOURITES_SVG, "Favourites"),
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
        svgs = [_BROWSE_SVG, _FAVOURITES_SVG, _ORDERS_SVG, _INVENTORY_SVG, _TRADES_SVG]
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
        self._browse_category.setMinimumContentsLength(15)
        self._browse_category.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._browse_category.currentIndexChanged.connect(self._filter_items)
        fr_layout.addWidget(self._browse_category)

        layout.addWidget(filter_row)

        # Item tree
        self._item_tree = QTreeWidget()
        self._item_tree.setHeaderLabels(["Name", "Type", "S/B", "Markup", "Updated"])
        self._item_tree.setColumnCount(5)
        self._item_tree.setRootIsDecorated(False)
        self._item_tree.setStyleSheet(_make_tree_style())
        self._item_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._item_tree.setSortingEnabled(True)
        self._item_tree.sortByColumn(4, Qt.SortOrder.DescendingOrder)
        self._item_tree.setItemDelegateForColumn(2, _SellBuyDelegate(self._item_tree))
        header = self._item_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 120)
        header.resizeSection(2, 70)
        header.resizeSection(3, 105)
        header.resizeSection(4, 60)
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

        # View details button (opens detail overlay)
        detail_btn = QPushButton()
        detail_btn.setFixedSize(22, 22)
        detail_btn.setIcon(svg_icon(_INFO_SVG, TEXT_DIM, 16))
        detail_btn.setStyleSheet(_TITLE_BTN_STYLE)
        detail_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        detail_btn.setToolTip("View item details")
        detail_btn.clicked.connect(self._open_item_detail)
        hdr_layout.addWidget(detail_btn)

        self._book_star_btn = QPushButton()
        self._book_star_btn.setFixedSize(22, 22)
        self._book_star_btn.setStyleSheet("background: transparent; border: none;")
        self._book_star_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._book_star_btn.clicked.connect(self._toggle_current_favourite)
        hdr_layout.addWidget(self._book_star_btn)

        layout.addWidget(header)

        # Metric panels
        metrics_row = QWidget()
        metrics_row.setStyleSheet("background: transparent;")
        mr_layout = QHBoxLayout(metrics_row)
        mr_layout.setContentsMargins(0, 0, 0, 0)
        mr_layout.setSpacing(4)

        metric_style = (
            f"background: {CONTENT_BG}; border-radius: 3px;"
            f" padding: 2px 6px; font-size: 10px;"
        )
        self._metric_labels: dict[str, QLabel] = {}
        for key, label in [("median", "Median"), ("p10", "10%"), ("wap", "Wt. Avg"),
                           ("best_buy", "Best Buy"), ("best_sell", "Best Sell")]:
            box = QWidget()
            bl = QVBoxLayout(box)
            bl.setContentsMargins(4, 2, 4, 2)
            bl.setSpacing(0)
            box.setStyleSheet(metric_style)

            title = QLabel(label)
            title.setStyleSheet(f"color: {TEXT_DIM}; font-size: 9px; background: transparent; padding: 0;")
            bl.addWidget(title)

            val = QLabel("\u2014")
            color = TEXT_COLOR
            if key == "best_buy":
                color = "#16a34a"
            elif key == "best_sell":
                color = ACCENT
            val.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold; background: transparent; padding: 0;")
            bl.addWidget(val)
            self._metric_labels[key] = val
            mr_layout.addWidget(box)

        mr_layout.addStretch()
        self._metrics_row = metrics_row
        self._metrics_row.hide()
        layout.addWidget(metrics_row)

        # Sell orders
        self._sell_header = self._make_section_header("Sell Orders", "_sell_tree")
        layout.addWidget(self._sell_header)

        self._sell_tree = QTreeWidget()
        self._sell_tree.setRootIsDecorated(False)
        self._sell_tree.setStyleSheet(_make_tree_style())
        self._sell_tree.itemClicked.connect(self._on_order_tree_clicked)
        self._sell_tree.itemDoubleClicked.connect(
            lambda item, col: self._on_orderbook_double_clicked(item, col, 'sell')
        )
        layout.addWidget(self._sell_tree, 1)

        # Buy orders
        self._buy_header = self._make_section_header("Buy Orders", "_buy_tree")
        layout.addWidget(self._buy_header)

        self._buy_tree = QTreeWidget()
        self._buy_tree.setRootIsDecorated(False)
        self._buy_tree.setStyleSheet(_make_tree_style())
        self._buy_tree.itemClicked.connect(self._on_order_tree_clicked)
        self._buy_tree.itemDoubleClicked.connect(
            lambda item, col: self._on_orderbook_double_clicked(item, col, 'buy')
        )
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
    # Tab 1: Favourites
    # ------------------------------------------------------------------

    def _build_favourites_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Toolbar row
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        add_folder_btn = QPushButton("+ Folder")
        add_folder_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_folder_btn.setStyleSheet(
            f"QPushButton {{ color: {ACCENT}; background: transparent;"
            f" border: 1px solid rgba(80, 80, 120, 100); border-radius: 3px;"
            f" padding: 2px 8px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {TAB_HOVER_BG}; }}"
        )
        add_folder_btn.clicked.connect(self._on_add_folder)
        toolbar.addWidget(add_folder_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Tree widget
        self._fav_tree = QTreeWidget()
        self._fav_tree.setHeaderHidden(True)
        self._fav_tree.setRootIsDecorated(True)
        self._fav_tree.setStyleSheet(_make_tree_style())
        self._fav_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._fav_tree.customContextMenuRequested.connect(self._on_fav_context_menu)
        self._fav_tree.itemDoubleClicked.connect(self._on_fav_double_clicked)
        layout.addWidget(self._fav_tree, 1)

        # Empty label
        self._fav_empty = QLabel("No favourites yet.\nStar items in the order book to add them.")
        self._fav_empty.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
        )
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

        # Folders
        for folder in folders:
            folder_item = QTreeWidgetItem()
            folder_item.setText(0, f"\U0001F4C1 {folder['name']}")
            folder_item.setData(0, Qt.ItemDataRole.UserRole, ("folder", folder["id"]))
            font = folder_item.font(0)
            font.setBold(True)
            folder_item.setFont(0, font)
            folder_item.setForeground(0, QColor(TEXT_COLOR))
            self._fav_tree.addTopLevelItem(folder_item)

            item_ids = self._favourites.get_folder_item_ids(folder["id"])
            for item_id in item_ids:
                has_items = True
                slim = lookup.get(item_id)
                name = slim.get("n", f"Item #{item_id}") if slim else f"Item #{item_id}"
                child = QTreeWidgetItem()
                child.setText(0, name)
                child.setData(0, Qt.ItemDataRole.UserRole, ("item", item_id))
                child.setForeground(0, QColor(TEXT_COLOR))
                folder_item.addChild(child)

            folder_item.setExpanded(True)

        # Root (unfiled) items
        if root_ids:
            has_items = True
            if folders:
                sep = QTreeWidgetItem()
                sep.setText(0, "── Unfiled ──")
                sep.setForeground(0, QColor(TEXT_DIM))
                sep.setFlags(Qt.ItemFlag.NoItemFlags)
                self._fav_tree.addTopLevelItem(sep)
            for item_id in root_ids:
                slim = lookup.get(item_id)
                name = slim.get("n", f"Item #{item_id}") if slim else f"Item #{item_id}"
                row = QTreeWidgetItem()
                row.setText(0, name)
                row.setData(0, Qt.ItemDataRole.UserRole, ("item", item_id))
                row.setForeground(0, QColor(TEXT_COLOR))
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

    def _on_add_folder(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "New Folder", "Folder name:",
        )
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
        menu.setStyleSheet(f"""
            QMenu {{
                background: rgba(30, 30, 45, 240); color: {TEXT_COLOR};
                border: 1px solid rgba(80, 80, 120, 150); padding: 4px;
            }}
            QMenu::item {{ padding: 4px 16px; }}
            QMenu::item:selected {{ background: {TAB_ACTIVE_BG}; }}
        """)

        if kind == "item":
            view_action = menu.addAction("View Order Book")
            remove_action = menu.addAction("Remove from Favourites")

            # Move to folder submenu
            folders = self._favourites.get_folders()
            move_menu = None
            if folders:
                move_menu = menu.addMenu("Move to Folder")
                move_menu.setStyleSheet(menu.styleSheet())
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
        self._orders_tree.setSortingEnabled(True)
        self._orders_tree.sortByColumn(6, Qt.SortOrder.DescendingOrder)
        header = self._orders_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 40)
        header.resizeSection(2, 55)
        header.resizeSection(3, 85)
        header.resizeSection(4, 70)
        header.resizeSection(5, 60)
        header.resizeSection(6, 55)
        self._orders_tree.itemDoubleClicked.connect(self._on_order_double_clicked)
        self._orders_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._orders_tree.customContextMenuRequested.connect(self._on_orders_context_menu)
        layout.addWidget(self._orders_tree, 1)

        # Auth message
        self._orders_auth_label = QLabel("Log in to view your orders")
        self._orders_auth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._orders_auth_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; background: transparent;")
        layout.addWidget(self._orders_auth_label)

        return w

    # ------------------------------------------------------------------
    # Tab 3: Inventory
    # ------------------------------------------------------------------

    def _build_inventory_view(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Search (debounced)
        self._inv_search = QLineEdit()
        self._inv_search.setPlaceholderText("Search inventory...")
        self._inv_search.setStyleSheet(_make_input_style())
        self._inv_search_timer = QTimer()
        self._inv_search_timer.setSingleShot(True)
        self._inv_search_timer.setInterval(300)
        self._inv_search_timer.timeout.connect(self._filter_inventory)
        self._inv_search.textChanged.connect(lambda: self._inv_search_timer.start())
        layout.addWidget(self._inv_search)

        # Inventory tree
        self._inv_tree = QTreeWidget()
        self._inv_tree.setHeaderLabels(["Name", "Type", "Qty", "TT Value", "Demand"])
        self._inv_tree.setColumnCount(5)
        self._inv_tree.setRootIsDecorated(False)
        self._inv_tree.setStyleSheet(_make_tree_style())
        self._inv_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._inv_tree.customContextMenuRequested.connect(self._on_inv_context_menu)
        header = self._inv_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 5):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 70)
        header.resizeSection(2, 40)
        header.resizeSection(3, 70)
        header.resizeSection(4, 70)
        self._inv_tree.itemDoubleClicked.connect(self._on_inv_double_clicked)
        layout.addWidget(self._inv_tree, 1)

        # Auth message
        self._inv_auth_label = QLabel("Log in to view your inventory")
        self._inv_auth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inv_auth_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; background: transparent;")
        layout.addWidget(self._inv_auth_label)

        return w

    # ------------------------------------------------------------------
    # Tab 4: Trade Requests
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

    def _on_exchange_prices_changed(self, item_id: int):
        if item_id == self._current_item_id:
            self._populate_metrics()

    def _reset_metrics(self):
        for lbl in self._metric_labels.values():
            lbl.setText("\u2014")
        self._metrics_row.hide()

    def _populate_metrics(self):
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

    def _on_error(self, context: str, message: str):
        pass  # Could show inline error labels

    def _on_favourites_changed(self):
        # Refresh star icons if order book is open
        if self._current_item_id:
            self._update_star_button()
        # Refresh favourites tab if active
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

            # Sell/Buy counts (display text for delegate, sort key for sorting)
            s_count = item.get('s', 0) or 0
            b_count = item.get('b', 0) or 0
            row.setText(2, f"{s_count}/{b_count}")
            row.setData(2, Qt.ItemDataRole.UserRole + 10, s_count + b_count)
            row.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)

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
            row.setText(3, mu_text)
            row.setData(3, Qt.ItemDataRole.UserRole + 10, mu_sort)
            row.setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            # Updated — composite sort key: items with orders first, then by recency
            u = item.get('u')
            row.setText(4, format_age(u))
            ts = 0.0
            if u and isinstance(u, str):
                try:
                    ts = datetime.fromisoformat(
                        u.replace('Z', '+00:00')
                    ).timestamp()
                except (ValueError, OSError):
                    pass
            has_orders = 1 if (s_count + b_count) > 0 else 0
            row.setData(4, Qt.ItemDataRole.UserRole + 10, (has_orders, ts))

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

    def _make_section_header(self, text: str, tree_attr: str) -> QWidget:
        """Create a clickable section header with chevron for collapsing a tree."""
        header = QWidget()
        header.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        header.setStyleSheet(
            f"background: transparent; border-radius: 3px;"
        )
        h = QHBoxLayout(header)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(4)

        label = QLabel(text)
        label.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; background: transparent;")
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        h.addWidget(label, 1)

        chevron = QLabel()
        chevron.setPixmap(svg_icon(_CHEVRON_DOWN_SVG, TEXT_DIM, 12).pixmap(12, 12))
        chevron.setStyleSheet("background: transparent;")
        chevron.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        h.addWidget(chevron, 0, Qt.AlignmentFlag.AlignVCenter)

        header.setProperty('_tree_attr', tree_attr)
        header.setProperty('_chevron', chevron)
        header.setProperty('_expanded', True)
        header.mousePressEvent = lambda _e, h=header: self._toggle_section(h)
        header.enterEvent = lambda _e, h=header: h.setStyleSheet(
            f"background: {ROW_HOVER}; border-radius: 3px;"
        )
        header.leaveEvent = lambda _e, h=header: h.setStyleSheet(
            f"background: transparent; border-radius: 3px;"
        )
        return header

    def _toggle_section(self, header: QWidget):
        tree_attr = header.property('_tree_attr')
        chevron = header.property('_chevron')
        expanded = header.property('_expanded')
        tree: QTreeWidget = getattr(self, tree_attr)
        expanded = not expanded
        tree.setVisible(expanded)
        chevron.setPixmap(svg_icon(
            _CHEVRON_DOWN_SVG if expanded else _CHEVRON_RIGHT_SVG, TEXT_DIM, 12
        ).pixmap(12, 12))
        header.setProperty('_expanded', expanded)

    def navigate_to_order_book(self, item_id: int):
        """Public entry point: switch to Browse tab and show the order book."""
        self._set_tab(_TAB_BROWSE)
        self._show_order_book(item_id)

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
            self._book_star_btn.setIcon(svg_icon(_STAR_FILLED, "#fbbf24", 16))
            self._book_star_btn.setToolTip("Remove from favourites")
        else:
            self._book_star_btn.setIcon(svg_icon(_STAR_OUTLINE, TEXT_DIM, 16))
            self._book_star_btn.setToolTip("Add to favourites")

    def _toggle_current_favourite(self):
        if self._current_item_id:
            self._favourites.toggle_favourite(self._current_item_id)
            self._update_star_button()

    def _open_item_detail(self):
        """Emit open_entity to open the current order book item in a detail overlay."""
        if not self._current_item_id:
            return
        slim = self._store.item_lookup.get(self._current_item_id)
        if not slim:
            return
        self.open_entity.emit({
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

    def _on_order_tree_clicked(self, item: QTreeWidgetItem, column: int):
        tree = item.treeWidget()
        seller_col = tree.property('_seller_col')
        if seller_col is not None and column == seller_col:
            seller_name = item.data(column, Qt.ItemDataRole.UserRole)
            if seller_name and seller_name != 'Unknown':
                self.open_entity.emit({"Type": "User", "Name": seller_name})

    def _populate_order_table(self, tree: QTreeWidget, orders: list[dict],
                              slim: dict | None, side: str = 'sell'):
        tree.clear()

        # Build dynamic column list
        columns = self._get_order_columns(slim, side)
        tree.setHeaderLabels([c[0] for c in columns])
        tree.setColumnCount(len(columns))

        # Find seller column index for click handling
        seller_col = next((i for i, (n, _) in enumerate(columns) if n == 'Seller'), -1)
        tree.setProperty('_seller_col', seller_col)

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

        cols.append(("Value", 65))
        mu_header = "MU (+PED)" if is_absolute_markup(slim) else "MU (%)"
        cols.append((mu_header, 80))
        cols.append(("Total", 75))
        cols.append(("Planet", 60))
        user_label = "Buyer" if side == 'buy' else "Seller"
        cols.append((user_label, 0))  # stretch
        cols.append(("Status", 50))
        cols.append(("Updated", 50))
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
            elif name.startswith('MU'):
                mu = order.get('markup')
                if mu is not None:
                    text = format_markup(mu, order.get('_is_absolute', True))
            elif name == 'Total':
                t = order.get('_total')
                text = format_ped(t) if t is not None else ''
            elif name == 'Planet':
                text = order.get('planet') or 'Any'
            elif name in ('Seller', 'Buyer'):
                text = order.get('seller_name') or str(order.get('user_id', 'Unknown'))
                row.setData(col, Qt.ItemDataRole.UserRole, text)  # store for click
                row.setForeground(col, QColor(ACCENT))
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

        # Initial sort handled by tree widget (default: Updated descending)

        # Summary
        sell_count = sum(1 for o in self._store.my_orders if o.get('type') == 'SELL' and o.get('_state') != 'closed')
        buy_count = sum(1 for o in self._store.my_orders if o.get('type') == 'BUY' and o.get('_state') != 'closed')
        self._orders_summary.setText(f"{sell_count} sell · {buy_count} buy orders")

        self._orders_tree.setSortingEnabled(False)
        for order in orders:
            row = _SortableItem()
            row.setText(0, order.get('_item_name', ''))
            row.setText(1, order.get('type', ''))
            qty = order.get('quantity', 1)
            row.setText(2, str(qty))
            row.setData(2, Qt.ItemDataRole.UserRole + 10, qty)
            mu = order.get('markup')
            if mu is not None:
                row.setText(3, format_markup(mu, order.get('_is_absolute', True)))
                try:
                    row.setData(3, Qt.ItemDataRole.UserRole + 10, float(mu))
                except (TypeError, ValueError):
                    pass
            row.setText(4, order.get('planet') or 'Any')

            state = order.get('_state', '')
            row.setText(5, state.capitalize())
            state_priority = {'active': 0, 'stale': 1, 'expired': 2, 'terminated': 3, 'closed': 4}
            row.setData(5, Qt.ItemDataRole.UserRole + 10, state_priority.get(state, 5))
            color = STATUS_COLORS.get(state, '#666')
            row.setForeground(5, QColor(color))

            updated_str = order.get('bumped_at') or order.get('updated')
            row.setText(6, format_age(updated_str))
            ts = 0.0
            if updated_str and isinstance(updated_str, str):
                try:
                    ts = datetime.fromisoformat(
                        updated_str.replace('Z', '+00:00')
                    ).timestamp()
                except (ValueError, OSError):
                    pass
            row.setData(6, Qt.ItemDataRole.UserRole + 10, ts)

            row.setData(0, Qt.ItemDataRole.UserRole, order.get('id'))
            row.setData(0, Qt.ItemDataRole.UserRole + 1, order)
            self._orders_tree.addTopLevelItem(row)
        self._orders_tree.setSortingEnabled(True)

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
        menu.setStyleSheet(f"""
            QMenu {{
                background: rgba(30, 30, 45, 240); color: {TEXT_COLOR};
                border: 1px solid rgba(80, 80, 120, 150); padding: 4px;
            }}
            QMenu::item {{ padding: 4px 16px; }}
            QMenu::item:selected {{ background: {TAB_ACTIVE_BG}; }}
        """)

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
            self._set_tab(_TAB_BROWSE)  # Switch to Browse tab
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
        menu.setStyleSheet(f"""
            QMenu {{
                background: rgba(30, 30, 45, 240); color: {TEXT_COLOR};
                border: 1px solid rgba(80, 80, 120, 150); padding: 4px;
            }}
            QMenu::item {{ padding: 4px 16px; }}
            QMenu::item:selected {{ background: {TAB_ACTIVE_BG}; }}
        """)
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
        """Open order creation/edit dialog."""
        if not self._store._client.is_authenticated():
            return
        target_id = item_id or self._current_item_id
        if not target_id:
            return

        slim = self._store.item_lookup.get(target_id)
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
        # User wants the opposite side: buy from a seller, sell to a buyer
        trade_side = 'buy' if side == 'sell' else 'sell'
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
    # Drag (title bar only) + Resize
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        # Only allow drag from title bar region
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_origin = event.globalPosition().toPoint()
            local_y = event.position().y()
            if local_y <= TITLE_H:
                self._drag_pos = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
            else:
                self._drag_pos = None

    def mouseReleaseEvent(self, event):
        click_origin = getattr(self, '_click_origin', None)
        self._click_origin = None
        super().mouseReleaseEvent(event)
        if click_origin and event.button() == Qt.MouseButton.LeftButton:
            delta = (event.globalPosition().toPoint() - click_origin).manhattanLength()
            if delta < 5:
                click_local = self.mapFromGlobal(click_origin)
                if click_local.y() <= TITLE_H:
                    self._body.setVisible(not self._body.isVisible())
                    self._position_resize_grip()

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
            else:
                # Items already cached — populate tree immediately
                self._populate_item_tree()
            if self._store._client.is_authenticated():
                self._store.load_my_orders()
                self._store.load_inventory()
                self._store.load_trade_requests()
            self._favourites.load_from_server()
            # Restore order dialog if it was open
            if self._order_dialog and not self._order_dialog.isVisible():
                self._order_dialog.show()
        else:
            self._store.stop_polling()
            # Hide order dialog along with overlay
            if self._order_dialog and self._order_dialog.isVisible():
                self._order_dialog.hide()


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
        self._drag_pos = None

        self._build_ui()
        self._load_suggestions()

        # Position near parent
        if parent:
            pos = parent.pos()
            self.move(pos.x() + 30, pos.y() + 40)

    # --- Dragging ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

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

        # Min Quantity (always visible for stackables, enabled/disabled by checkbox)
        self._min_qty_spin = QSpinBox()
        self._min_qty_spin.setRange(1, 999999)
        self._min_qty_spin.setEnabled(False)
        self._min_qty_lbl = QLabel("Min Qty:")
        self._min_qty_lbl.setStyleSheet(label_style)
        fl.addRow(self._min_qty_lbl, self._min_qty_spin)
        self._min_qty_spin.setVisible(stackable)
        self._min_qty_lbl.setVisible(stackable)
        self._partial_check.toggled.connect(self._on_partial_toggled)
        self._qty_spin.valueChanged.connect(self._update_min_qty_range)
        self._qty_spin.valueChanged.connect(self._update_price_preview)

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
        self._min_qty_spin.setEnabled(checked)
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

        if self._partial_check.isChecked() and self._min_qty_spin.isEnabled():
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


# ======================================================================
# Quick Trade Dialog (respond to existing order)
# ======================================================================


class _QuickTradeDialog(QWidget):
    """Dialog for responding to an existing order (buy from seller / sell to buyer)."""

    trade_submitted = pyqtSignal(bool, str)

    def __init__(self, *, slim: dict, order: dict, side: str,
                 store: ExchangeStore, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._slim = slim
        self._order = order
        self._side = side  # 'buy' or 'sell' — what the user is doing
        self._store = store
        self._drag_pos = None

        self._build_ui()

        if parent:
            pos = parent.pos()
            self.move(pos.x() + 30, pos.y() + 40)

    # --- Dragging ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # --- UI ---

    def _build_ui(self):
        self.setFixedWidth(340)

        container = QWidget(self)
        container.setStyleSheet(
            f"background-color: rgba(20, 20, 30, 240);"
            f" border: 1px solid rgba(80, 80, 120, 150); border-radius: 8px;"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        # --- Title bar ---
        title_row = QHBoxLayout()
        seller_name = self._order.get('seller_name') or str(self._order.get('user_id', ''))
        if self._side == 'buy':
            title_text = f"Buy from {seller_name}"
        else:
            title_text = f"Sell to {seller_name}"

        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 13px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl, 1)

        close_btn = QPushButton("\u00d7")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_DIM}; background: transparent;"
            f" border: none; font-size: 16px; font-weight: bold; }}"
            f"QPushButton:hover {{ color: {TEXT_COLOR}; }}"
        )
        close_btn.clicked.connect(self.close)
        title_row.addWidget(close_btn)
        layout.addLayout(title_row)

        # --- Item details (read-only) ---
        form = QFormLayout()
        form.setSpacing(4)
        form.setContentsMargins(0, 0, 0, 0)

        label_style = f"color: {TEXT_DIM}; font-size: 12px; background: transparent; border: none;"
        value_style = f"color: {TEXT_COLOR}; font-size: 12px; background: transparent; border: none;"

        def add_row(label_text: str, value_text: str):
            lbl = QLabel(label_text)
            lbl.setStyleSheet(label_style)
            val = QLabel(value_text)
            val.setStyleSheet(value_style)
            form.addRow(lbl, val)

        # Item name
        item_name = self._slim.get('n', '?')
        if self._slim.get('t') == 'ArmorSet':
            item_name += '  [Set]'
        add_row("Item:", item_name)

        # Planet
        planet = self._order.get('planet') or "Any"
        add_row("Planet:", planet)

        # Conditional detail fields
        details = self._order.get('details') or {}

        if details.get('Tier'):
            tier_text = str(details['Tier'])
            tir = details.get('TierIncreaseRate')
            if tir is not None:
                tier_text += f"   TiR: {tir}"
            add_row("Tier:", tier_text)

        if details.get('QualityRating') is not None:
            add_row("QR:", f"{details['QualityRating']:.2f}")

        if details.get('CurrentTT') is not None:
            add_row("Current TT:", format_ped(details['CurrentTT']))

        if details.get('Gender'):
            add_row("Gender:", details['Gender'])

        if details.get('PetLevel') is not None:
            add_row("Pet Level:", str(details['PetLevel']))

        if details.get('is_set'):
            add_row("Full Set:", "Yes")

        # Markup
        markup = self._order.get('markup', 0)
        markup_text = format_markup(markup, is_absolute_markup(self._slim))
        add_row("Markup:", markup_text)

        layout.addLayout(form)

        # --- Quantity (editable, only if stackable) ---
        max_qty = max(1, int(self._order.get('quantity', 1)))
        min_qty = max(1, int(self._order.get('min_quantity', 1)))
        min_qty = min(min_qty, max_qty)
        self._quantity = max_qty

        if is_stackable(self._slim) and max_qty > 1:
            qty_row = QHBoxLayout()
            qty_row.setSpacing(6)
            qty_lbl = QLabel("Quantity:")
            qty_lbl.setStyleSheet(label_style)
            qty_row.addWidget(qty_lbl)

            self._qty_spin = QSpinBox()
            self._qty_spin.setRange(min_qty, max_qty)
            self._qty_spin.setValue(max_qty)
            self._qty_spin.setStyleSheet(
                f"QSpinBox {{ background: rgba(40, 40, 60, 200); color: {TEXT_COLOR};"
                f" border: 1px solid rgba(80, 80, 120, 150); border-radius: 3px;"
                f" padding: 2px 4px; font-size: 12px; }}"
            )
            self._qty_spin.valueChanged.connect(self._update_price)
            qty_row.addWidget(self._qty_spin)

            hint = QLabel(f"min {min_qty} · max {max_qty}")
            hint.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; background: transparent; border: none;")
            qty_row.addWidget(hint)
            qty_row.addStretch()
            layout.addLayout(qty_row)
        else:
            self._qty_spin = None

        # --- Price summary ---
        sep = QLabel("── Price ──")
        sep.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; background: transparent; border: none;")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sep)

        price_form = QFormLayout()
        price_form.setSpacing(2)
        price_form.setContentsMargins(0, 0, 0, 0)

        self._tt_value_lbl = QLabel()
        self._tt_value_lbl.setStyleSheet(value_style)
        tt_label = QLabel("TT Value:")
        tt_label.setStyleSheet(label_style)
        price_form.addRow(tt_label, self._tt_value_lbl)

        self._markup_amount_lbl = QLabel()
        self._markup_amount_lbl.setStyleSheet(value_style)
        mk_label = QLabel("Markup:")
        mk_label.setStyleSheet(label_style)
        price_form.addRow(mk_label, self._markup_amount_lbl)

        self._total_lbl = QLabel()
        self._total_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 13px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        total_label = QLabel("Total:")
        total_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        price_form.addRow(total_label, self._total_lbl)

        layout.addLayout(price_form)

        # --- Submit button ---
        btn_text = "Buy Now" if self._side == 'buy' else "Sell Now"
        self._submit_btn = QPushButton(btn_text)
        self._submit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_color = "#4ade80" if self._side == 'buy' else "#f87171"
        self._submit_btn.setStyleSheet(
            f"QPushButton {{ color: #fff; background: {btn_color};"
            f" border: none; border-radius: 4px; padding: 6px 20px;"
            f" font-size: 13px; font-weight: bold; }}"
            f"QPushButton:hover {{ opacity: 0.9; background: {btn_color}; }}"
            f"QPushButton:disabled {{ background: rgba(80, 80, 80, 200); color: {TEXT_DIM}; }}"
        )
        self._submit_btn.clicked.connect(self._on_submit)
        layout.addWidget(self._submit_btn, alignment=Qt.AlignmentFlag.AlignRight)

        # Error label
        self._error_label = QLabel()
        self._error_label.setStyleSheet(
            f"color: #f87171; font-size: 11px; background: transparent; border: none;"
        )
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        self._update_price()

    # --- Price calculation ---

    def _update_price(self):
        qty = self._qty_spin.value() if self._qty_spin else 1
        self._quantity = qty

        unit_price = compute_order_unit_price(self._slim, self._order)
        total = unit_price * qty

        # TT value
        unit_tt = get_unit_tt(self._slim, self._order.get('details'))
        total_tt = unit_tt * qty

        self._tt_value_lbl.setText(format_ped(total_tt))
        self._markup_amount_lbl.setText(format_ped(total - total_tt))
        self._total_lbl.setText(format_ped(total))

    # --- Submit ---

    def _on_submit(self):
        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("Submitting...")
        self._error_label.hide()

        self._store.create_trade_request(
            self._order, self._quantity,
            callback=self._on_result,
        )

    def _on_result(self, success: bool, result):
        self._submit_btn.setEnabled(True)
        btn_text = "Buy Now" if self._side == 'buy' else "Sell Now"
        self._submit_btn.setText(btn_text)
        if success:
            self.trade_submitted.emit(True, "Trade request created")
            self.close()
        else:
            msg = str(result) if result else "Failed to create trade request"
            self._error_label.setText(msg)
            self._error_label.show()
            self.trade_submitted.emit(False, msg)
