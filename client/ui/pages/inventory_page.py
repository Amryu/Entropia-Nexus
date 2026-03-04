"""Inventory page — view and manage in-game inventory with list and tree views."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QStackedWidget, QHeaderView, QDialog, QFormLayout,
    QAbstractItemView, QSizePolicy, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor

from ..theme import (
    PRIMARY, SECONDARY, MAIN_DARK, HOVER, BORDER, ACCENT,
    TEXT, TEXT_MUTED, ERROR, TABLE_HEADER, TABLE_ROW_ALT,
)
import threading

from ...core.config import save_config
from ...core.inventory_utils import (
    enrich_item, get_top_category, format_ped, format_markup,
    is_absolute_markup, ALL_CATEGORIES, PLANETS,
)
from ...core.logger import get_logger

log = get_logger("Inventory")


def _display_name(segment: str) -> str:
    """Strip '#refID' suffix from a container path segment for display."""
    idx = segment.rfind('#')
    if idx > 0 and segment[idx + 1:].isdigit():
        return segment[:idx]
    return segment


# ---------------------------------------------------------------------------
# Column indices for the list table
# ---------------------------------------------------------------------------
COL_NAME = 0
COL_QTY = 1
COL_TT = 2
COL_MARKUP = 3
COL_TOTAL = 4
COL_CONTAINER = 5
COL_TYPE = 6
_NUM_COLS = 7
_COL_HEADERS = ["Name", "Qty", "TT Value", "Markup", "Total Value", "Container", "Type"]

# View mode indices
_VIEW_LIST = 0
_VIEW_TREE = 1


# ---------------------------------------------------------------------------
# Background data loader
# ---------------------------------------------------------------------------

class _DataLoader(QThread):
    """Fetch inventory, exchange slim items, markups, and in-game prices in the background."""
    finished = pyqtSignal(object, object, object, object, object)  # items, slims, markups, ingame, error

    def __init__(self, nexus_client):
        super().__init__()
        self._nc = nexus_client

    def run(self):
        try:
            items = self._nc.get_inventory()
            if items is None:
                self.finished.emit(None, None, None, None, "Failed to load inventory. Please check your login.")
                return
            slims = self._nc.get_exchange_items()
            markups = self._nc.get_inventory_markups()
            ingame = self._nc.get_ingame_prices()
            self.finished.emit(items, slims, markups, ingame, None)
        except Exception as e:
            log.error("DataLoader error: %s", e)
            self.finished.emit(None, None, None, None, str(e))


# ---------------------------------------------------------------------------
# Background markup saver
# ---------------------------------------------------------------------------

class _MarkupSaver(QThread):
    """Save or delete a markup value in the background."""
    done = pyqtSignal(bool, str)  # success, error_message

    def __init__(self, nexus_client, item_id: int, markup: float | None):
        super().__init__()
        self._nc = nexus_client
        self._item_id = item_id
        self._markup = markup

    def run(self):
        try:
            if self._markup is None:
                ok = self._nc.delete_inventory_markup(self._item_id)
            else:
                ok = self._nc.save_inventory_markups(
                    [{"item_id": self._item_id, "markup": self._markup}]
                )
            self.done.emit(ok, "" if ok else "Save failed")
        except Exception as e:
            self.done.emit(False, str(e))


# ---------------------------------------------------------------------------
# Custom tree widget item with numeric sorting
# ---------------------------------------------------------------------------

class _NumericItem(QTreeWidgetItem):
    """QTreeWidgetItem that sorts numerically when a UserRole value is set.

    Container nodes (column 0 UserRole starts with "0:") always sort
    before item leaves ("1:") regardless of sort column or direction.
    """

    def _is_container(self) -> bool:
        v = self.data(0, Qt.ItemDataRole.UserRole)
        return isinstance(v, str) and v.startswith("0:")

    def __lt__(self, other):
        # Containers always sort to the top of their parent node
        self_cont = self._is_container()
        other_cont = other._is_container() if isinstance(other, _NumericItem) else False
        if self_cont != other_cont:
            tw = self.treeWidget()
            is_asc = True
            if tw:
                is_asc = tw.header().sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
            # In ASC: container < item (True). In DESC: reversed so use False.
            return self_cont == is_asc

        col = self.treeWidget().sortColumn() if self.treeWidget() else 0
        lv = self.data(col, Qt.ItemDataRole.UserRole)
        rv = other.data(col, Qt.ItemDataRole.UserRole)
        if lv is not None and rv is not None:
            try:
                return float(lv) < float(rv)
            except (TypeError, ValueError):
                try:
                    return str(lv) < str(rv)
                except TypeError:
                    pass
        return super().__lt__(other)


# ---------------------------------------------------------------------------
# Item detail dialog
# ---------------------------------------------------------------------------

class _ItemDetailDialog(QDialog):
    """Modal dialog showing detailed info about an inventory item."""

    open_wiki = pyqtSignal(int, str, str)  # item_id, item_type, item_name

    def __init__(self, enriched: dict, parent=None):
        super().__init__(parent)
        self._item = enriched
        self.setWindowTitle(enriched.get('item_name', 'Item Details'))
        self.setMinimumWidth(380)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {SECONDARY};
                border: 1px solid {BORDER};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Name
        name_lbl = QLabel(enriched.get('item_name', ''))
        name_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT};")
        name_lbl.setWordWrap(True)
        layout.addWidget(name_lbl)

        # Type badge
        item_type = enriched.get('_type') or 'Unknown'
        category = enriched.get('_category', 'Other')
        type_lbl = QLabel(f"{get_top_category(item_type)} — {item_type}")
        type_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        layout.addWidget(type_lbl)

        # Info grid
        form = QFormLayout()
        form.setSpacing(6)
        form.setContentsMargins(0, 8, 0, 0)

        def add_row(label_text: str, value_text: str, accent: bool = False):
            label = QLabel(label_text)
            label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            value = QLabel(value_text)
            color = ACCENT if accent else TEXT
            value.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 500;")
            form.addRow(label, value)

        add_row("Quantity:", f"{enriched.get('quantity', 1):,}")

        tt = enriched.get('_tt_value')
        add_row("TT Value:", f"{format_ped(tt)} PED" if tt is not None else "N/A")

        markup = enriched.get('_markup')
        abs_markup = enriched.get('_is_absolute', True)
        if markup is not None:
            add_row("Custom Markup:", format_markup(markup, abs_markup), accent=True)

        market = enriched.get('_market_price')
        if market is not None:
            add_row("Market Price:", format_markup(market, abs_markup))

        total = enriched.get('_total_value')
        source = enriched.get('_value_source', 'default')
        source_label = {'custom': ' (custom)', 'ingame': ' (in-game)', 'exchange': ' (exchange)', 'default': ' (TT)'}
        add_row(
            "Est. Total:",
            f"{format_ped(total)} PED{source_label.get(source, '')}" if total is not None else "N/A",
            accent=source == 'custom',
        )

        container = enriched.get('container', 'Carried')
        add_row("Container:", container)

        container_path = enriched.get('container_path')
        if container_path:
            add_row("Full Path:", container_path)

        # Details (Tier, TiR, QR)
        details = enriched.get('details') or {}
        if details.get('Tier') is not None:
            add_row("Tier:", str(details['Tier']))
        if details.get('TierIncreaseRate') is not None:
            add_row("TiR:", str(details['TierIncreaseRate']))
        if details.get('QualityRating') is not None:
            add_row("QR:", str(details['QualityRating']))
        if details.get('Level') is not None:
            add_row("Level:", str(details['Level']))

        layout.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        item_id = enriched.get('item_id', 0)
        if item_id > 0:
            wiki_btn = QPushButton("Open in Wiki")
            wiki_btn.setObjectName("accentButton")
            wiki_btn.clicked.connect(lambda: self._on_wiki(item_id, item_type))
            btn_row.addWidget(wiki_btn)

        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _on_wiki(self, item_id, item_type):
        item_name = self._item.get('item_name', '')
        self.open_wiki.emit(item_id, item_type or '', item_name)
        self.accept()


# ---------------------------------------------------------------------------
# Main inventory page
# ---------------------------------------------------------------------------

_INV_PREF_KEY = "inventory.viewPrefs"


class InventoryPage(QWidget):
    """Inventory viewer with list and tree views, filtering, and markup editing."""

    def __init__(self, *, signals, oauth, nexus_client, db=None,
                 config=None, config_path=None):
        super().__init__()
        self._signals = signals
        self._oauth = oauth
        self._nexus_client = nexus_client
        self._db = db
        self._config = config
        self._config_path = config_path

        # Data
        self._raw_items: list[dict] = []
        self._enriched: list[dict] = []
        self._filtered: list[dict] = []
        self._slim_lookup: dict[int, dict] = {}
        self._markup_lookup: dict[int, float] = {}
        self._ingame_lookup: dict[str, float] = {}
        self._loading = False
        self._data_loaded = False

        # Workers
        self._loader: _DataLoader | None = None
        self._saver: _MarkupSaver | None = None

        # Markup edit state
        self._editing_item_id: int | None = None
        self._markup_save_timer = QTimer()
        self._markup_save_timer.setSingleShot(True)
        self._markup_save_timer.setInterval(400)
        self._markup_save_timer.timeout.connect(self._save_pending_markup)
        self._pending_markup_value: str = ''

        # Load saved preferences
        prefs = self._load_prefs()
        self._view_mode = prefs.get("view_mode", _VIEW_LIST)
        self._saved_planet = prefs.get("planet", "all")
        self._saved_category = prefs.get("category", "all")
        self._saved_markup_filter = prefs.get("markup_filter", "all")

        # Suppress pref save during initial UI construction
        self._suppress_pref_save = True

        # Debounce pref save timer
        self._pref_save_timer = QTimer()
        self._pref_save_timer.setSingleShot(True)
        self._pref_save_timer.setInterval(500)
        self._pref_save_timer.timeout.connect(self._persist_prefs)

        self._build_ui()
        self._connect_signals()
        self._apply_saved_filters()
        self._suppress_pref_save = False

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        # --- Header row ---
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        header_row.addStretch()

        # View toggle buttons
        toggle_style = f"""
            QPushButton {{
                background-color: {SECONDARY};
                color: {TEXT_MUTED};
                border: 1px solid {BORDER};
                padding: 4px 12px;
                font-size: 12px;
                min-height: 18px;
            }}
            QPushButton:hover {{
                background-color: {HOVER};
                color: {TEXT};
            }}
        """
        active_style = f"""
            QPushButton {{
                background-color: {ACCENT};
                color: {MAIN_DARK};
                border: 1px solid {ACCENT};
                padding: 4px 12px;
                font-size: 12px;
                font-weight: bold;
                min-height: 18px;
            }}
        """

        self._btn_list = QPushButton("List")
        self._btn_list.setStyleSheet(active_style)
        self._btn_list.clicked.connect(lambda: self._set_view(_VIEW_LIST))
        header_row.addWidget(self._btn_list)

        self._btn_tree = QPushButton("Tree")
        self._btn_tree.setStyleSheet(toggle_style)
        self._btn_tree.clicked.connect(lambda: self._set_view(_VIEW_TREE))
        header_row.addWidget(self._btn_tree)

        # Import / History buttons
        action_style = f"""
            QPushButton {{
                background-color: {SECONDARY};
                color: {TEXT_MUTED};
                border: 1px solid {BORDER};
                padding: 4px 12px;
                font-size: 12px;
                min-height: 18px;
            }}
            QPushButton:hover {{
                background-color: {HOVER};
                color: {TEXT};
            }}
        """
        self._btn_import = QPushButton("Import")
        self._btn_import.setStyleSheet(action_style)
        self._btn_import.setToolTip("Import inventory from paste or file")
        self._btn_import.clicked.connect(self._on_import_clicked)
        header_row.addWidget(self._btn_import)

        self._btn_history = QPushButton("History")
        self._btn_history.setStyleSheet(action_style)
        self._btn_history.setToolTip("View import history and portfolio value")
        self._btn_history.clicked.connect(self._on_history_clicked)
        header_row.addWidget(self._btn_history)

        self._btn_refresh = QPushButton("\u21bb")  # ↻
        self._btn_refresh.setToolTip("Refresh inventory")
        self._btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {SECONDARY};
                color: {TEXT_MUTED};
                border: 1px solid {BORDER};
                padding: 4px 8px;
                font-size: 14px;
                min-height: 18px;
                min-width: 28px;
                max-width: 28px;
            }}
            QPushButton:hover {{
                background-color: {HOVER};
                color: {TEXT};
            }}
        """)
        self._btn_refresh.clicked.connect(self._load_data)
        header_row.addWidget(self._btn_refresh)

        layout.addLayout(header_row)

        # --- Filter bar ---
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        # Planet filter
        self._planet_combo = QComboBox()
        self._planet_combo.addItem("All Planets", "all")
        self._planet_combo.setMinimumWidth(130)
        self._planet_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._planet_combo)

        # Category filter
        self._category_combo = QComboBox()
        self._category_combo.addItem("All Categories", "all")
        for cat in ALL_CATEGORIES:
            self._category_combo.addItem(cat, cat)
        self._category_combo.setMinimumWidth(130)
        self._category_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._category_combo)

        # Markup filter
        self._markup_combo = QComboBox()
        self._markup_combo.addItem("All Markups", "all")
        self._markup_combo.addItem("Has Markup", "has-markup")
        self._markup_combo.addItem("No Markup", "no-markup")
        self._markup_combo.setMinimumWidth(110)
        self._markup_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._markup_combo)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search items...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._search, 1)

        layout.addLayout(filter_row)

        # --- Summary bar ---
        self._summary = QLabel()
        self._summary.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; padding: 2px 0;")
        layout.addWidget(self._summary)

        # --- View stack ---
        self._stack = QStackedWidget()

        # List view (QTreeWidget used as flat table)
        self._table = QTreeWidget()
        self._table.setHeaderLabels(_COL_HEADERS)
        self._table.setRootIsDecorated(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setIndentation(0)
        self._table.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {PRIMARY};
                alternate-background-color: {TABLE_ROW_ALT};
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
        """)
        hdr = self._table.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for col in (COL_QTY, COL_TT, COL_MARKUP, COL_TOTAL):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_CONTAINER, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_TYPE, QHeaderView.ResizeMode.ResizeToContents)
        self._table.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._table.itemClicked.connect(self._on_item_clicked)
        self._stack.addWidget(self._table)

        # Tree view (container hierarchy)
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Items", "TT Value", "Est. Value"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setSortingEnabled(True)
        self._tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {PRIMARY};
                alternate-background-color: {TABLE_ROW_ALT};
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
        """)
        tree_hdr = self._tree.header()
        tree_hdr.setStretchLastSection(False)
        tree_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3):
            tree_hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.itemDoubleClicked.connect(self._on_tree_item_double_clicked)
        self._stack.addWidget(self._tree)

        layout.addWidget(self._stack, 1)

        # --- Status / auth prompt ---
        self._status = QLabel()
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; padding: 8px;")
        self._status.hide()
        layout.addWidget(self._status)

    def _connect_signals(self):
        self._signals.auth_state_changed.connect(self._on_auth_changed)

    # ------------------------------------------------------------------
    # View mode
    # ------------------------------------------------------------------

    def _set_view(self, mode: int):
        self._view_mode = mode
        self._stack.setCurrentIndex(mode)

        toggle_style = f"""
            QPushButton {{
                background-color: {SECONDARY};
                color: {TEXT_MUTED};
                border: 1px solid {BORDER};
                padding: 4px 12px;
                font-size: 12px;
                min-height: 18px;
            }}
            QPushButton:hover {{
                background-color: {HOVER};
                color: {TEXT};
            }}
        """
        active_style = f"""
            QPushButton {{
                background-color: {ACCENT};
                color: {MAIN_DARK};
                border: 1px solid {ACCENT};
                padding: 4px 12px;
                font-size: 12px;
                font-weight: bold;
                min-height: 18px;
            }}
        """
        self._btn_list.setStyleSheet(active_style if mode == _VIEW_LIST else toggle_style)
        self._btn_tree.setStyleSheet(active_style if mode == _VIEW_TREE else toggle_style)
        self._refresh_display()
        self._schedule_pref_save()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if not self._data_loaded and not self._loading:
            self._load_data()

    def _load_data(self):
        if not self._oauth.is_authenticated():
            self._show_status("Log in to view your inventory.")
            return

        if self._loading:
            return

        self._loading = True
        self._btn_refresh.setEnabled(False)
        self._show_status("Loading inventory...")

        self._loader = _DataLoader(self._nexus_client)
        self._loader.finished.connect(self._on_data_loaded)
        self._loader.start()

    def _on_data_loaded(self, items, slims, markups, ingame, error):
        self._loading = False
        self._btn_refresh.setEnabled(True)
        self._loader = None

        if error:
            self._show_status(error)
            return

        self._raw_items = items or []
        self._data_loaded = True

        # Build slim lookup
        self._slim_lookup = {}
        for s in (slims or []):
            if s and s.get('i') is not None:
                self._slim_lookup[s['i']] = s

        # Build markup lookup
        self._markup_lookup = {}
        for m in (markups or []):
            try:
                self._markup_lookup[m['item_id']] = float(m['markup'])
            except (ValueError, TypeError):
                pass

        # Build in-game price lookup (name → markup%)
        self._ingame_lookup = {}
        for row in (ingame or []):
            name = row.get("item_name")
            if not name:
                continue
            mu = (row.get("markup_1d") or row.get("markup_7d")
                  or row.get("markup_30d") or row.get("markup_90d")
                  or row.get("markup_365d"))
            if mu is not None:
                self._ingame_lookup[name] = float(mu)

        # Enrich items
        self._enriched = [
            enrich_item(item, self._slim_lookup, self._markup_lookup, self._ingame_lookup)
            for item in self._raw_items
        ]

        # Populate planet filter
        self._update_planet_filter()

        # Restore saved planet selection (after combo is populated)
        if self._saved_planet and self._saved_planet != "all":
            self._suppress_pref_save = True
            idx = self._planet_combo.findData(self._saved_planet)
            if idx >= 0:
                self._planet_combo.setCurrentIndex(idx)
            self._suppress_pref_save = False

        # Apply filters and display
        self._on_filter_changed()
        self._hide_status()

    def _on_auth_changed(self, _data):
        if self._oauth.is_authenticated():
            self._data_loaded = False
            if self.isVisible():
                self._load_data()
            # Check for pending offline imports
            QTimer.singleShot(500, self._check_pending_imports)
        else:
            self._raw_items = []
            self._enriched = []
            self._filtered = []
            self._data_loaded = False
            self._table.clear()
            self._tree.clear()
            self._update_summary()
            self._show_status("Log in to view your inventory.")

    def _check_pending_imports(self):
        """Check for unsynced offline imports and show conflict dialog if needed."""
        if not self._db or not self._oauth.is_authenticated():
            return
        scopes = self._oauth.auth_state.scopes
        if 'inventory:write' not in scopes:
            return

        pending = self._db.get_pending_inventory_imports()
        if not pending:
            return

        # Use the most recent pending import
        latest = pending[0]
        offline_count = latest['raw_count']
        offline_date = latest['imported_at'][:16].replace('T', ' ')

        # Check if server has an existing inventory
        server_items = self._nexus_client.get_inventory()
        online_count = len(server_items) if server_items else 0

        if online_count == 0:
            # No server inventory — auto-sync without prompting
            self._sync_pending_import(latest)
            return

        # Show conflict dialog
        from ..dialogs.inventory_conflict import (
            InventoryConflictDialog, USE_OFFLINE, USE_ONLINE,
        )
        dlg = InventoryConflictDialog(
            offline_count=offline_count,
            offline_date=offline_date,
            online_count=online_count,
            parent=self,
        )
        if dlg.exec():
            if dlg.result_code == USE_OFFLINE:
                self._sync_pending_import(latest)
            elif dlg.result_code == USE_ONLINE:
                # Discard all pending imports, keep server data
                self._db.discard_pending_inventory_imports()
                log.info("Discarded pending offline imports, keeping server inventory.")

    def _sync_pending_import(self, pending: dict):
        """Upload a pending offline import to the server."""
        all_items = pending['items'] + pending['unresolved']
        try:
            result = self._nexus_client.import_inventory(all_items, sync=True)
            if result:
                self._db.mark_pending_inventory_synced(pending['id'])
                log.info("Synced offline import #%d: %s", pending['id'], result)
                # Refresh inventory display
                self._data_loaded = False
                self._load_data()
            else:
                log.warning("Sync of offline import #%d returned no result.", pending['id'])
        except Exception as e:
            log.error("Failed to sync offline import #%d: %s", pending['id'], e)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _update_planet_filter(self):
        """Repopulate planet dropdown from loaded data."""
        self._planet_combo.blockSignals(True)
        current = self._planet_combo.currentData()
        self._planet_combo.clear()
        self._planet_combo.addItem(f"All Planets ({len(self._enriched)})", "all")

        planets: dict[str, int] = {}
        for item in self._enriched:
            c = item.get('container', 'Carried')
            planets[c] = planets.get(c, 0) + 1

        sorted_planets = sorted(planets.keys(), key=lambda p: (p == 'Carried', p))
        for p in sorted_planets:
            self._planet_combo.addItem(f"{p} ({planets[p]})", p)

        # Restore selection
        idx = self._planet_combo.findData(current)
        if idx >= 0:
            self._planet_combo.setCurrentIndex(idx)
        self._planet_combo.blockSignals(False)

    def _on_filter_changed(self, *_args):
        planet = self._planet_combo.currentData() or 'all'
        category = self._category_combo.currentData() or 'all'
        markup_filter = self._markup_combo.currentData() or 'all'
        search = self._search.text().strip().lower()

        filtered = []
        for item in self._enriched:
            if planet != 'all' and item.get('container') != planet:
                continue
            if category != 'all' and item.get('_category') != category:
                continue
            if markup_filter == 'has-markup' and item.get('_markup') is None:
                continue
            if markup_filter == 'no-markup' and item.get('_markup') is not None:
                continue
            if search and search not in (item.get('item_name') or '').lower():
                continue
            filtered.append(item)

        self._filtered = filtered
        self._update_summary()
        self._refresh_display()
        # Save filter prefs (but not the search text — that's ephemeral)
        self._schedule_pref_save()

    def _update_summary(self):
        items = self._filtered
        count = len(items)
        tt_total = sum(i.get('_tt_value') or 0 for i in items)
        est_total = sum(i.get('_total_value') or 0 for i in items)
        unknown_total = sum(
            (i.get('_tt_value') or 0) for i in items if i.get('item_id', 0) == 0
        )

        parts = [f"{count:,} items"]
        parts.append(f"TT: {format_ped(tt_total)} PED")
        parts.append(f"Est: {format_ped(est_total)} PED")
        if unknown_total > 0:
            parts.append(f"Unknown: {format_ped(unknown_total)} PED")
        self._summary.setText("  |  ".join(parts))

    # ------------------------------------------------------------------
    # Display refresh
    # ------------------------------------------------------------------

    def _refresh_display(self):
        if self._view_mode == _VIEW_LIST:
            self._populate_table()
        else:
            self._populate_tree()

    def _populate_table(self):
        self._table.setSortingEnabled(False)
        self._table.clear()
        self._table.setHeaderLabels(_COL_HEADERS)

        for item in self._filtered:
            row = _NumericItem()
            name = item.get('item_name', '')
            qty = item.get('quantity', 1) or 1
            tt = item.get('_tt_value')
            markup = item.get('_markup')
            total = item.get('_total_value')
            container = item.get('container', 'Carried')
            item_type = item.get('_type') or ''
            abs_mu = item.get('_is_absolute', True)
            source = item.get('_value_source', 'default')

            row.setText(COL_NAME, name)
            row.setData(COL_NAME, Qt.ItemDataRole.UserRole, name.lower())

            row.setText(COL_QTY, f"{qty:,}")
            row.setData(COL_QTY, Qt.ItemDataRole.UserRole, qty)

            row.setText(COL_TT, f"{format_ped(tt)}" if tt is not None else "")
            row.setData(COL_TT, Qt.ItemDataRole.UserRole, tt if tt is not None else -1)

            if markup is not None:
                row.setText(COL_MARKUP, format_markup(markup, abs_mu))
                row.setForeground(COL_MARKUP, QColor(ACCENT))
            else:
                market = item.get('_market_price')
                if market is not None:
                    row.setText(COL_MARKUP, format_markup(market, abs_mu))
                    row.setForeground(COL_MARKUP, QColor(TEXT_MUTED))
                else:
                    row.setText(COL_MARKUP, "—")
                    row.setForeground(COL_MARKUP, QColor(TEXT_MUTED))
            row.setData(COL_MARKUP, Qt.ItemDataRole.UserRole,
                        markup if markup is not None else (item.get('_market_price') or -1))

            if total is not None:
                row.setText(COL_TOTAL, format_ped(total))
                if source == 'custom':
                    row.setForeground(COL_TOTAL, QColor(ACCENT))
            else:
                row.setText(COL_TOTAL, "")
            row.setData(COL_TOTAL, Qt.ItemDataRole.UserRole, total if total is not None else -1)

            row.setText(COL_CONTAINER, container)
            row.setText(COL_TYPE, get_top_category(item_type))

            # Store enriched item reference
            row.setData(COL_NAME, Qt.ItemDataRole.UserRole + 1, item)

            self._table.addTopLevelItem(row)

        self._table.setSortingEnabled(True)

    def _populate_tree(self):
        self._tree.setSortingEnabled(False)
        self._tree.clear()

        # Resolve each item's full container path (matches web buildTree):
        #   container_path > STORAGE ({container}) > Unknown
        path_groups: dict[str, list[dict]] = {}
        for item in self._filtered:
            path = item.get('container_path')
            if not path and item.get('container'):
                path = f"STORAGE ({item['container']})"
            if not path:
                path = "Unknown"
            path_groups.setdefault(path, []).append(item)

        # Split each path on " > " and build a shared tree via _build_sub_tree.
        # First pass: group by root segment to create top-level nodes.
        roots: dict[str, dict] = {}  # root_seg → {children: {sub: items}, direct: []}
        for path, items in sorted(path_groups.items()):
            segments = [s.strip() for s in path.split(" > ")]
            root = segments[0]
            if root not in roots:
                roots[root] = {'children': {}, 'direct_items': []}
            if len(segments) > 1:
                sub = " > ".join(segments[1:])
                roots[root]['children'].setdefault(sub, []).extend(items)
            else:
                roots[root]['direct_items'].extend(items)

        # Create tree nodes
        for root_name in sorted(roots.keys()):
            root_info = roots[root_name]
            all_items = root_info['direct_items'][:]
            for child_items in root_info['children'].values():
                all_items.extend(child_items)

            root_count = len(all_items)
            root_tt = sum(i.get('_tt_value') or 0 for i in all_items)
            root_est = sum(i.get('_total_value') or 0 for i in all_items)

            root_node = _NumericItem()
            root_node.setText(0, _display_name(root_name))
            root_node.setData(0, Qt.ItemDataRole.UserRole, f"0:{root_name.lower()}")
            root_node.setText(1, str(root_count))
            root_node.setData(1, Qt.ItemDataRole.UserRole, root_count)
            root_node.setText(2, f"{format_ped(root_tt)} PED")
            root_node.setData(2, Qt.ItemDataRole.UserRole, root_tt)
            root_node.setText(3, f"{format_ped(root_est)} PED")
            root_node.setData(3, Qt.ItemDataRole.UserRole, root_est)
            root_node.setForeground(0, QColor(TEXT))
            font = root_node.font(0)
            font.setBold(True)
            root_node.setFont(0, font)

            # Sub-containers
            for sub_path in sorted(root_info['children'].keys()):
                child_items = root_info['children'][sub_path]
                sub_segments = [s.strip() for s in sub_path.split(" > ")]
                self._build_sub_tree(root_node, sub_segments, child_items)

            # Direct items at root level
            for item in sorted(root_info['direct_items'],
                               key=lambda i: (i.get('item_name') or '').lower()):
                self._add_tree_leaf(root_node, item)

            self._tree.addTopLevelItem(root_node)
            root_node.setExpanded(True)

        self._tree.setSortingEnabled(True)

    def _build_sub_tree(self, parent: QTreeWidgetItem, segments: list[str], items: list[dict]):
        """Recursively build sub-container nodes.

        Stats (count, TT, Est) are accumulated on every container level,
        so intermediate nodes show aggregate values from all descendants.
        """
        if not segments:
            for item in sorted(items, key=lambda i: (i.get('item_name') or '').lower()):
                self._add_tree_leaf(parent, item)
            return

        # Find or create the container node for segments[0]
        # Use the full segment (with #refID) as identity key stored in UserRole+2
        container_key = segments[0]
        display = _display_name(container_key)
        container_node = None
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole + 2) == container_key:
                container_node = child
                break

        if container_node is None:
            container_node = _NumericItem()
            container_node.setText(0, display)
            container_node.setData(0, Qt.ItemDataRole.UserRole, f"0:{display.lower()}")
            container_node.setData(0, Qt.ItemDataRole.UserRole + 2, container_key)
            container_node.setForeground(0, QColor(TEXT_MUTED))
            parent.addChild(container_node)

        # Accumulate stats for this container (items may arrive from
        # multiple paths, e.g. "Storage > Box1" and "Storage > Box2")
        batch_count = len(items)
        batch_tt = sum(i.get('_tt_value') or 0 for i in items)
        batch_est = sum(i.get('_total_value') or 0 for i in items)

        prev_count = container_node.data(1, Qt.ItemDataRole.UserRole) or 0
        prev_tt = container_node.data(2, Qt.ItemDataRole.UserRole) or 0
        prev_est = container_node.data(3, Qt.ItemDataRole.UserRole) or 0

        total_count = prev_count + batch_count
        total_tt = prev_tt + batch_tt
        total_est = prev_est + batch_est

        container_node.setText(1, str(total_count))
        container_node.setData(1, Qt.ItemDataRole.UserRole, total_count)
        container_node.setText(2, f"{format_ped(total_tt)} PED")
        container_node.setData(2, Qt.ItemDataRole.UserRole, total_tt)
        container_node.setText(3, f"{format_ped(total_est)} PED")
        container_node.setData(3, Qt.ItemDataRole.UserRole, total_est)

        if len(segments) == 1:
            for item in sorted(items, key=lambda i: (i.get('item_name') or '').lower()):
                self._add_tree_leaf(container_node, item)
        else:
            self._build_sub_tree(container_node, segments[1:], items)

    def _add_tree_leaf(self, parent: QTreeWidgetItem, item: dict):
        """Add an item as a leaf node in the tree."""
        leaf = _NumericItem()
        name = item.get('item_name', '')
        qty = item.get('quantity', 1) or 1
        tt = item.get('_tt_value')
        total = item.get('_total_value')

        display_name = f"{name} (x{qty:,})" if qty > 1 else name
        leaf.setText(0, display_name)
        leaf.setData(0, Qt.ItemDataRole.UserRole, f"1:{name.lower()}")
        leaf.setText(1, "")  # No count for leaf
        if tt is not None:
            leaf.setText(2, f"{format_ped(tt)} PED")
            leaf.setData(2, Qt.ItemDataRole.UserRole, tt)
        if total is not None:
            leaf.setText(3, f"{format_ped(total)} PED")
            leaf.setData(3, Qt.ItemDataRole.UserRole, total)
            if item.get('_value_source') == 'custom':
                leaf.setForeground(3, QColor(ACCENT))

        # Store enriched item reference
        leaf.setData(0, Qt.ItemDataRole.UserRole + 1, item)
        parent.addChild(leaf)

    # ------------------------------------------------------------------
    # Item interaction
    # ------------------------------------------------------------------

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle click on list table item — open markup editor on markup column."""
        if column == COL_MARKUP:
            enriched = item.data(COL_NAME, Qt.ItemDataRole.UserRole + 1)
            if enriched and enriched.get('item_id', 0) > 0:
                self._start_markup_edit(enriched)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle double-click on list table item — show detail dialog."""
        enriched = item.data(COL_NAME, Qt.ItemDataRole.UserRole + 1)
        if enriched:
            self._show_detail(enriched)

    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle double-click on tree item — show detail if leaf."""
        enriched = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if enriched:
            self._show_detail(enriched)

    def _show_detail(self, enriched: dict):
        """Show item detail dialog."""
        dlg = _ItemDetailDialog(enriched, self)
        dlg.open_wiki.connect(self._signals.inventory_open_wiki.emit)
        dlg.exec()

    # ------------------------------------------------------------------
    # Markup editing
    # ------------------------------------------------------------------

    def _start_markup_edit(self, enriched: dict):
        """Open inline markup editor for an item."""
        item_id = enriched.get('item_id', 0)
        if item_id <= 0:
            return

        abs_mu = enriched.get('_is_absolute', True)
        current = enriched.get('_markup')

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Markup")
        dlg.setMinimumWidth(280)
        dlg.setStyleSheet(f"QDialog {{ background-color: {SECONDARY}; }}")

        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)

        name_lbl = QLabel(enriched.get('item_name', ''))
        name_lbl.setStyleSheet(f"font-weight: bold; color: {TEXT};")
        layout.addWidget(name_lbl)

        hint = "Absolute (+PED)" if abs_mu else "Percentage (%)"
        hint_lbl = QLabel(f"Markup type: {hint}")
        hint_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        layout.addWidget(hint_lbl)

        input_field = QLineEdit()
        input_field.setPlaceholderText("+0.00" if abs_mu else "100.00%")
        if current is not None:
            input_field.setText(str(current))
        layout.addWidget(input_field)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self._do_save_markup(item_id, None, dlg))
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("accentButton")
        save_btn.clicked.connect(
            lambda: self._do_save_markup_from_input(item_id, input_field.text(), abs_mu, dlg)
        )
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        input_field.returnPressed.connect(save_btn.click)
        dlg.exec()

    def _do_save_markup_from_input(self, item_id: int, text: str, abs_mu: bool, dlg: QDialog):
        """Parse and save markup from input text."""
        text = text.strip().lstrip('+').rstrip('%')
        try:
            val = float(text)
        except ValueError:
            return

        # If default value, delete instead
        default = 0 if abs_mu else 100
        if val == default:
            self._do_save_markup(item_id, None, dlg)
        else:
            self._do_save_markup(item_id, val, dlg)

    def _do_save_markup(self, item_id: int, markup: float | None, dlg: QDialog):
        """Save or delete markup and update local state."""
        dlg.accept()

        # Update local state immediately
        if markup is None:
            self._markup_lookup.pop(item_id, None)
        else:
            self._markup_lookup[item_id] = markup

        # Re-enrich and refresh
        self._enriched = [
            enrich_item(item, self._slim_lookup, self._markup_lookup, getattr(self, '_ingame_lookup', None))
            for item in self._raw_items
        ]
        self._on_filter_changed()

        # Save in background
        self._saver = _MarkupSaver(self._nexus_client, item_id, markup)
        self._saver.done.connect(self._on_markup_saved)
        self._saver.start()

    def _save_pending_markup(self):
        """Timer-triggered save for debounced markup editing."""
        pass  # Reserved for future inline edit

    def _on_markup_saved(self, success: bool, error: str):
        if not success:
            log.error("Failed to save markup: %s", error)
            # Check if this is a scope/permission error
            if "403" in error or "Permission" in error or "denied" in error.lower():
                QMessageBox.warning(
                    self, "Permission Required",
                    "Saving markups requires the 'inventory:write' permission.\n"
                    "Please log out and log back in to grant this permission.",
                )
        self._saver = None

    # ------------------------------------------------------------------
    # Import / History
    # ------------------------------------------------------------------

    def _on_import_clicked(self):
        """Open the inventory import dialog. Falls back to offline mode if not authenticated."""
        is_online = False
        if self._oauth.is_authenticated():
            scopes = self._oauth.auth_state.scopes
            if 'inventory:write' in scopes:
                is_online = True
            else:
                QMessageBox.information(
                    self, "Permission Required",
                    "Online import requires the 'inventory:write' permission.\n"
                    "You can still save imports locally for later sync,\n"
                    "or log out and back in to grant this permission.",
                )

        # Ensure slim items are available for name resolution (public API, no auth needed)
        slim = self._slim_lookup
        if not slim:
            slims = self._nexus_client.get_exchange_items()
            for s in (slims or []):
                if s and s.get('i') is not None:
                    slim[s['i']] = s
            self._slim_lookup = slim

        from ..dialogs.inventory_import import InventoryImportDialog
        dlg = InventoryImportDialog(
            nexus_client=self._nexus_client if is_online else None,
            current_items=self._enriched if is_online else None,
            slim_lookup=slim,
            db=self._db,
            is_online=is_online,
            parent=self,
        )
        if dlg.exec():
            if is_online:
                # Successful online import — refresh data
                self._data_loaded = False
                self._load_data()

    def _on_history_clicked(self):
        """Open the import history dialog."""
        if not self._oauth.is_authenticated():
            QMessageBox.information(self, "Login Required", "Please log in to view history.")
            return

        from ..dialogs.inventory_history import InventoryHistoryDialog
        dlg = InventoryHistoryDialog(
            nexus_client=self._nexus_client,
            parent=self,
        )
        dlg.exec()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _show_status(self, text: str):
        self._status.setText(text)
        self._status.show()
        self._stack.hide()
        self._summary.hide()

    def _hide_status(self):
        self._status.hide()
        self._stack.show()
        self._summary.show()

    # ------------------------------------------------------------------
    # Preference persistence
    # ------------------------------------------------------------------

    def _load_prefs(self) -> dict:
        """Load inventory view preferences from server or local config."""
        # Try server first
        if (self._nexus_client
                and self._oauth and self._oauth.is_authenticated()):
            try:
                prefs = self._nexus_client.get_preferences()
                if prefs and _INV_PREF_KEY in prefs:
                    server_data = prefs[_INV_PREF_KEY]
                    if isinstance(server_data, dict):
                        # Server wins — update local
                        if self._config:
                            self._config.inventory_prefs = server_data
                            if self._config_path:
                                save_config(self._config, self._config_path)
                        return server_data
            except Exception:
                pass
        # Fall back to local config
        if self._config:
            return self._config.inventory_prefs or {}
        return {}

    def _apply_saved_filters(self):
        """Apply saved filter preferences to combo boxes after UI is built."""
        self._suppress_pref_save = True
        # View mode
        if self._view_mode == _VIEW_TREE:
            self._set_view(_VIEW_TREE)
        # Category
        idx = self._category_combo.findData(self._saved_category)
        if idx >= 0:
            self._category_combo.setCurrentIndex(idx)
        # Markup filter
        idx = self._markup_combo.findData(self._saved_markup_filter)
        if idx >= 0:
            self._markup_combo.setCurrentIndex(idx)
        # Planet is applied after data loads (combo is populated then)
        self._suppress_pref_save = False

    def _schedule_pref_save(self):
        """Restart the debounce timer for preference persistence."""
        if self._suppress_pref_save:
            return
        self._pref_save_timer.start()

    def _persist_prefs(self):
        """Save inventory view preferences to local config and server."""
        data = {
            "view_mode": self._view_mode,
            "planet": self._planet_combo.currentData() or "all",
            "category": self._category_combo.currentData() or "all",
            "markup_filter": self._markup_combo.currentData() or "all",
        }
        # Save locally
        if self._config:
            self._config.inventory_prefs = data
            if self._config_path:
                try:
                    save_config(self._config, self._config_path)
                except Exception:
                    pass
        # Push to server
        if (self._nexus_client
                and self._oauth and self._oauth.is_authenticated()):
            def _push(d=data):
                try:
                    self._nexus_client.save_preference(_INV_PREF_KEY, d)
                except Exception:
                    pass
            threading.Thread(
                target=_push, daemon=True, name="inv-pref-save"
            ).start()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        """Stop background threads."""
        self._markup_save_timer.stop()
        self._pref_save_timer.stop()
        if self._loader and self._loader.isRunning():
            self._loader.quit()
            self._loader.wait(2000)
        if self._saver and self._saver.isRunning():
            self._saver.quit()
            self._saver.wait(2000)
