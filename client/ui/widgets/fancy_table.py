"""FancyTable — virtualised, sortable, filterable table widget.

Feature parity with the website's FancyTable.svelte: content-based auto-width,
multi-phase sort, per-column filters with operator syntax, row recycling for
fast scrolling, optional footer, and responsive compact mode.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QFontMetrics

from ..theme import (
    TEXT, TEXT_MUTED, BORDER, SECONDARY, PRIMARY, HOVER, ACCENT,
    TABLE_HEADER, TABLE_ROW, TABLE_ROW_ALT, MAIN_DARK,
)
from ..icons import svg_icon, SETTINGS

# Blue-tinted hover — matches website rgba(59, 130, 246, 0.15) over PRIMARY
_ROW_HOVER_COLOR = "#263042"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class SortPhase:
    """One phase in a multi-phase sort cycle."""
    sort_value: Callable[[dict], Any]
    order: str = "ASC"           # "ASC" | "DESC"
    color: str | None = None     # optional indicator color


@dataclass
class ColumnDef:
    """Column definition — mirrors the website's FancyTable column config."""
    key: str
    header: str
    width: str | None = None             # "60px", "1fr", or None=auto
    width_basis: str = "both"            # "content" | "header" | "both"
    main: bool = False                   # grows to fill remaining space
    sortable: bool = True
    searchable: bool = True

    # Value extraction
    get_value: Callable[[dict], Any] | None = None
    format: Callable[[Any], str] | None = None
    sort_value: Callable[[dict], Any] | None = None
    sort_fn: Callable[[Any, Any], int] | None = None
    sort_phases: list[SortPhase] | None = None

    # Appearance
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft
    cell_class: Callable[[Any, dict], str] | None = None


def column_def_from_dict(d: dict) -> ColumnDef:
    """Convert a legacy wiki_columns dict to a ColumnDef."""
    fields = {f for f in ColumnDef.__dataclass_fields__}
    return ColumnDef(**{k: v for k, v in d.items() if k in fields})


# ---------------------------------------------------------------------------
# Filter matching (reuse from wiki_table)
# ---------------------------------------------------------------------------

_OP_RE = re.compile(r"^(>=|<=|>|<|=|!)(.+)$")


def _matches_filter(raw_value, display_text: str, filter_text: str) -> bool:
    """Check if a cell value matches a filter expression."""
    filter_text = filter_text.strip()
    if not filter_text:
        return True

    m = _OP_RE.match(filter_text)
    if m:
        op, operand = m.group(1), m.group(2).strip()

        if op in (">", "<", ">=", "<="):
            try:
                threshold = float(operand)
            except ValueError:
                return True
            if raw_value is None or not isinstance(raw_value, (int, float)):
                return False
            if op == ">":
                return raw_value > threshold
            if op == "<":
                return raw_value < threshold
            if op == ">=":
                return raw_value >= threshold
            if op == "<=":
                return raw_value <= threshold

        if op == "=":
            return display_text.lower() == operand.lower()

        if op == "!":
            return operand.lower() not in display_text.lower()

    return filter_text.lower() in display_text.lower()


# ---------------------------------------------------------------------------
# Cache builder
# ---------------------------------------------------------------------------

def build_fancy_cache(
    items: list[dict],
    columns: list[ColumnDef],
) -> tuple[list[list[tuple]], list[bool]]:
    """Build (raw, display) cache for items x columns. Thread-safe.

    Returns (cache, numeric) where cache[row][col] = (raw, display)
    and numeric[col] = True if the column holds numeric data.
    """
    cache: list[list[tuple]] = []
    for item in items:
        row: list[tuple] = []
        for col in columns:
            if col.get_value is not None:
                raw = col.get_value(item)
            else:
                raw = item.get(col.key)
            if col.format is not None:
                display = str(col.format(raw))
            else:
                display = str(raw) if raw is not None else ""
            row.append((raw, display))
        cache.append(row)

    num_cols = len(columns)
    numeric = [False] * num_cols
    for col_idx in range(num_cols):
        for row in cache:
            raw = row[col_idx][0]
            if raw is not None:
                numeric[col_idx] = isinstance(raw, (int, float))
                break

    return cache, numeric


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROW_HEIGHT_DEFAULT = 28
FILTER_HEIGHT = 26
FILTER_DEBOUNCE_MS = 200
COMPACT_COLUMN_COUNT = 5
COMPACT_WIDTH_BREAKPOINT = 1200  # window width below which condensed columns are used
COMPACT_HYSTERESIS = 20
COLUMN_WIDTH_PADDING = 38  # cell padding (16) + sort indicator (14) + spacing (4) + margin (4)
MIN_COLUMN_WIDTH = 50
MIN_MAIN_COLUMN_WIDTH = 150
SCROLL_BUFFER_ROWS = 10
RESIZE_GRIP_WIDTH = 5    # px from right edge of header cell for resize handle
DRAG_THRESHOLD = 5       # px movement before header drag starts
MIN_RESIZE_WIDTH = 30    # minimum column width during resize

_SORT_ASC = "\u25B2"   # ▲
_SORT_DESC = "\u25BC"  # ▼


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hidden_scroll_area(fixed_height: int | None = None) -> QScrollArea:
    """Create a QScrollArea with no visible scrollbars."""
    sa = QScrollArea()
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setWidgetResizable(False)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    sa.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    if fixed_height is not None:
        sa.setFixedHeight(fixed_height)
    return sa


# ---------------------------------------------------------------------------
# Internal widgets
# ---------------------------------------------------------------------------

class _HeaderCell(QWidget):
    """Clickable header cell with sort indicator, drag-to-reorder, and edge resize."""

    clicked = pyqtSignal(int)              # sort click (col_idx)
    drag_started = pyqtSignal(int)         # col_idx
    drag_moved = pyqtSignal(int, int)      # col_idx, global_x
    drag_finished = pyqtSignal(int, int)   # col_idx, global_x
    resize_moved = pyqtSignal(int, int)    # col_idx, global_x
    resize_finished = pyqtSignal(int)      # col_idx

    def __init__(self, col_idx: int, text: str, sortable: bool,
                 reorderable: bool = False, resizable: bool = False,
                 parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._col_idx = col_idx
        self._sortable = sortable
        self._reorderable = reorderable
        self._resizable = resizable
        self._press_pos = None
        self._dragging = False
        self._resizing = False
        if sortable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        if resizable:
            self.setMouseTracking(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)

        self._label = QLabel(text)
        self._label.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; font-weight: bold;"
            " background: transparent;"
        )
        layout.addWidget(self._label, 1)

        self._indicator = QLabel("")
        self._indicator.setStyleSheet(
            f"color: {ACCENT}; font-size: 10px; background: transparent;"
        )
        self._indicator.setFixedWidth(14)
        layout.addWidget(self._indicator)

    def set_sort_indicator(self, direction: str | None, color: str | None = None):
        """Set the sort indicator. direction: 'ASC', 'DESC', or None."""
        if direction is None:
            self._indicator.setText("")
            return
        arrow = _SORT_ASC if direction == "ASC" else _SORT_DESC
        self._indicator.setText(arrow)
        c = color or ACCENT
        self._indicator.setStyleSheet(
            f"color: {c}; font-size: 10px; background: transparent;"
        )

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self._press_pos = event.position()
        self._dragging = False
        self._resizing = False
        # Right-edge press → resize
        if self._resizable and event.position().x() >= self.width() - RESIZE_GRIP_WIDTH:
            self._resizing = True
            return
        # Otherwise potential click or drag-reorder

    def mouseMoveEvent(self, event):
        # Cursor hint when hovering (no button pressed)
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            if self._resizable and event.position().x() >= self.width() - RESIZE_GRIP_WIDTH:
                self.setCursor(Qt.CursorShape.SplitHCursor)
            elif self._sortable:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.unsetCursor()
            return
        if self._resizing:
            self.resize_moved.emit(self._col_idx, int(event.globalPosition().x()))
            return
        if self._press_pos is None:
            return
        if not self._dragging and self._reorderable:
            delta = event.position().x() - self._press_pos.x()
            if abs(delta) > DRAG_THRESHOLD:
                self._dragging = True
                self.drag_started.emit(self._col_idx)
        if self._dragging:
            self.drag_moved.emit(self._col_idx, int(event.globalPosition().x()))

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._resizing:
            self.resize_finished.emit(self._col_idx)
            self._resizing = False
            self._press_pos = None
            return
        if self._dragging:
            self.drag_finished.emit(self._col_idx, int(event.globalPosition().x()))
            self._dragging = False
            self._press_pos = None
            return
        # Plain click → sort
        self._press_pos = None
        if self._sortable:
            self.clicked.emit(self._col_idx)


class _TableRow(QWidget):
    """Recyclable row widget with pre-created cell labels."""

    def __init__(self, col_count: int, row_height: int, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(row_height)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._cells: list[QLabel] = []
        for _ in range(col_count):
            lbl = QLabel("")
            lbl.setStyleSheet(
                f"color: {TEXT}; font-size: 12px; padding: 0 8px;"
                " background: transparent;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._layout.addWidget(lbl)
            self._cells.append(lbl)

        self._layout.addStretch()

        self._display_index: int = -1
        self._data_index: int = -1

    def configure_columns(self, widths: list[int], alignments: list[Qt.AlignmentFlag],
                          row_width: int | None = None):
        """Set column widths and alignments.

        *row_width* overrides the total fixed width of the row widget so it
        fills the viewport.  The trailing addStretch() handles the gap.
        """
        self._cell_widths = list(widths)
        total = 0
        for i, lbl in enumerate(self._cells):
            if i < len(widths):
                lbl.setFixedWidth(widths[i])
                total += widths[i]
                alignment = alignments[i] if i < len(alignments) else Qt.AlignmentFlag.AlignLeft
                lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | alignment)
        self.setFixedWidth(row_width if row_width is not None else total)

    def set_data(
        self,
        display_index: int,
        data_index: int,
        texts: list[str],
        bg_color: str,
    ):
        """Fill cell contents and position."""
        self._display_index = display_index
        self._data_index = data_index
        widths = getattr(self, "_cell_widths", [])
        for i, lbl in enumerate(self._cells):
            if i < len(texts):
                text = texts[i]
                w = widths[i] if i < len(widths) else 0
                if w > 16:
                    fm = lbl.fontMetrics()
                    # Account for padding (8px each side from stylesheet)
                    elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, w - 16)
                    lbl.setText(elided)
                else:
                    lbl.setText(text)
            else:
                lbl.setText("")
        self.setStyleSheet(f"background-color: {bg_color};")

    @property
    def display_index(self) -> int:
        return self._display_index

    @property
    def data_index(self) -> int:
        return self._data_index


# ---------------------------------------------------------------------------
# FancyTable
# ---------------------------------------------------------------------------

class FancyTable(QWidget):
    """Virtualised, sortable, filterable table with content-based column sizing."""

    row_clicked = pyqtSignal(dict, int)      # (row_data, row_index)
    row_hover = pyqtSignal(object)           # dict or None
    row_activated = pyqtSignal(dict, int)    # double-click (row_data, row_index)
    sort_changed = pyqtSignal(str, str)      # (column_key, direction)
    columns_reordered = pyqtSignal(list)     # [column_key, ...]

    def __init__(
        self,
        columns: list[ColumnDef],
        row_height: int = ROW_HEIGHT_DEFAULT,
        sortable: bool = True,
        searchable: bool = True,
        compact_threshold: int = COMPACT_COLUMN_COUNT,
        default_sort: tuple[str, str] | None = None,
        row_class: Callable[[dict], str | None] | None = None,
        empty_message: str = "No data available",
        max_visible_rows: int | None = None,
        show_toolbar: bool = True,
        reorderable: bool = False,
        resizable: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._all_columns = list(columns)
        self._active_columns = list(columns)
        self._row_height = row_height
        self._sortable = sortable
        self._searchable = searchable
        self._compact_threshold = compact_threshold
        self._default_sort = default_sort
        self._row_class_fn = row_class
        self._empty_message = empty_message
        self._max_visible_rows = max_visible_rows
        self._show_toolbar = show_toolbar
        self._reorderable = reorderable
        self._resizable = resizable

        # Data
        self._items: list[dict] = []
        self._cache: list[list[tuple]] = []
        self._numeric: list[bool] = []
        self._col_widths: list[int] = []
        self._col_alignments: list[Qt.AlignmentFlag] = []

        # Sort state
        self._sort_col_idx: int | None = None
        self._sort_direction: str = "ASC"
        self._sort_phase_idx: int = 0

        # Index pipeline
        self._sorted_indices: list[int] = []
        self._filtered_indices: list[int] = []  # = display_indices
        self._col_filters: list[str] = []

        # Compact mode
        self._compact = False
        self._full_col_keys: list[str] = [c.key for c in columns]

        # Virtualisation
        self._row_pool: list[_TableRow] = []
        self._active_rows: dict[int, _TableRow] = {}
        self._last_render_range: tuple[int, int] = (-1, -1)

        self._build_ui()

        # Debounce timers
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(FILTER_DEBOUNCE_MS)
        self._filter_timer.timeout.connect(self._apply_filters)

        self._compact_timer = QTimer(self)
        self._compact_timer.setSingleShot(True)
        self._compact_timer.setInterval(150)
        self._compact_timer.timeout.connect(self._check_compact_mode)

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- Toolbar --
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 4)
        toolbar.setSpacing(8)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        toolbar.addWidget(self._count_label)
        toolbar.addStretch()

        _toolbar_btn_style = (
            f"QPushButton {{ font-size: 16px; padding: 0; border: 1px solid {BORDER};"
            f" border-radius: 4px; background: {SECONDARY}; }}"
            f"QPushButton:hover {{ background: {PRIMARY}; }}"
        )

        self._compact_hint = QLabel("Widen window to show more columns")
        self._compact_hint.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; font-style: italic;"
        )
        self._compact_hint.hide()
        toolbar.addWidget(self._compact_hint)

        self._new_btn = QPushButton("+")
        self._new_btn.setToolTip("Create new entry")
        self._new_btn.setFixedSize(28, 28)
        self._new_btn.setStyleSheet(_toolbar_btn_style)
        self._new_btn.hide()
        toolbar.addWidget(self._new_btn)

        self._config_btn = QPushButton()
        self._config_btn.setToolTip("Configure columns")
        self._config_btn.setFixedSize(28, 28)
        self._config_btn.setIcon(svg_icon(SETTINGS, TEXT_MUTED, 14))
        self._config_btn.setStyleSheet(_toolbar_btn_style)
        toolbar.addWidget(self._config_btn)

        self._toolbar_widget = QWidget()
        self._toolbar_widget.setLayout(toolbar)
        if not self._show_toolbar:
            self._toolbar_widget.hide()
        root.addWidget(self._toolbar_widget)

        # -- Header scroll area (no visible scrollbars) --
        self._header_scroll = _make_hidden_scroll_area(fixed_height=self._row_height)
        self._header_inner = QWidget()
        self._header_inner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._header_inner.setStyleSheet(
            f"background-color: {TABLE_HEADER};"
        )
        self._header_inner.setFixedHeight(self._row_height)
        self._header_layout = QHBoxLayout(self._header_inner)
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(0)
        self._header_cells: list[_HeaderCell] = []
        # Drop indicator for column reorder
        self._drop_indicator = QFrame(self._header_inner)
        self._drop_indicator.setFixedWidth(2)
        self._drop_indicator.setStyleSheet(f"background-color: {ACCENT};")
        self._drop_indicator.hide()
        self._header_scroll.setWidget(self._header_inner)
        root.addWidget(self._header_scroll)

        # Separator below header
        header_sep = QFrame()
        header_sep.setFrameShape(QFrame.Shape.HLine)
        header_sep.setFixedHeight(1)
        header_sep.setStyleSheet(f"background-color: {BORDER}; border: none;")
        root.addWidget(header_sep)

        # -- Filter scroll area (no visible scrollbars) --
        self._filter_scroll = _make_hidden_scroll_area(fixed_height=FILTER_HEIGHT)
        self._filter_inner = QWidget()
        self._filter_inner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._filter_inner.setStyleSheet(f"background-color: {MAIN_DARK};")
        self._filter_inner.setFixedHeight(FILTER_HEIGHT)
        self._filter_layout = QHBoxLayout(self._filter_inner)
        self._filter_layout.setContentsMargins(0, 0, 0, 0)
        self._filter_layout.setSpacing(0)
        self._filter_inputs: list[QLineEdit] = []
        self._filter_scroll.setWidget(self._filter_inner)

        if self._searchable:
            root.addWidget(self._filter_scroll)

            filter_sep = QFrame()
            filter_sep.setFrameShape(QFrame.Shape.HLine)
            filter_sep.setFixedHeight(1)
            filter_sep.setStyleSheet(f"background-color: {BORDER}; border: none;")
            root.addWidget(filter_sep)

        # -- Body scroll area (both H and V scrollbars) --
        self._body_scroll = QScrollArea()
        self._body_scroll.setWidgetResizable(False)
        self._body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._body_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._body_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._virtual_container = QWidget()
        self._virtual_container.setStyleSheet(f"background-color: {PRIMARY};")
        self._body_scroll.setWidget(self._virtual_container)

        root.addWidget(self._body_scroll, 1)

        # -- Empty message (overlaid when no rows) --
        self._empty_label = QLabel(self._empty_message)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px; padding: 32px;"
        )
        self._empty_label.hide()
        root.addWidget(self._empty_label)

        # -- Footer scroll area (no visible scrollbars, hidden by default) --
        self._footer_scroll = _make_hidden_scroll_area()
        self._footer_inner = QWidget()
        self._footer_inner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._footer_inner.setStyleSheet(f"background-color: {TABLE_HEADER};")
        self._footer_layout = QVBoxLayout(self._footer_inner)
        self._footer_layout.setContentsMargins(0, 0, 0, 0)
        self._footer_layout.setSpacing(0)
        self._footer_scroll.setWidget(self._footer_inner)
        self._footer_scroll.hide()
        root.addWidget(self._footer_scroll)

        # Scrollbar width constant — matches QScrollBar:vertical { width: 10px } in theme
        self._sb_width = 10

        # -- Sync horizontal scroll: body drives header + filter + footer --
        self._body_scroll.horizontalScrollBar().valueChanged.connect(self._on_h_scroll)

        # -- Vertical scroll drives row rendering --
        self._body_scroll.verticalScrollBar().valueChanged.connect(self._on_v_scroll)

    def _on_h_scroll(self, value: int):
        """Sync header, filter, and footer with body horizontal scroll."""
        self._header_scroll.horizontalScrollBar().setValue(value)
        self._filter_scroll.horizontalScrollBar().setValue(value)
        self._footer_scroll.horizontalScrollBar().setValue(value)

    def _on_v_scroll(self):
        """Handle vertical scroll — re-render visible rows."""
        self._render_visible()

    def _sync_scrollbar_margin(self):
        """Reserve right margin on header/filter/footer only when the body has a vertical scrollbar."""
        has_sb = self._body_scroll.verticalScrollBar().isVisible()
        margin = self._sb_width if has_sb else 0
        self._header_scroll.setViewportMargins(0, 0, margin, 0)
        self._filter_scroll.setViewportMargins(0, 0, margin, 0)
        self._footer_scroll.setViewportMargins(0, 0, margin, 0)

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def set_data(
        self,
        items: list[dict],
        cache: list[list[tuple]] | None = None,
        numeric: list[bool] | None = None,
    ):
        """Populate the table with data.

        If *cache*/*numeric* are supplied (pre-computed on a background
        thread), the per-cell computation is skipped.
        """
        self._items = items

        if cache is not None and numeric is not None:
            self._cache = cache
            self._numeric = numeric
        else:
            self._cache, self._numeric = build_fancy_cache(items, self._active_columns)

        # Detect whether columns changed (same count = data-only refresh)
        columns_changed = len(self._header_cells) != len(self._active_columns)

        # Init index pipeline
        self._sorted_indices = list(range(len(self._cache)))
        if columns_changed:
            self._col_filters = [""] * len(self._active_columns)

        # Apply default sort
        if self._default_sort:
            key, direction = self._default_sort
            for i, col in enumerate(self._active_columns):
                if col.key == key:
                    self._sort_col_idx = i
                    self._sort_direction = direction
                    self._sort_phase_idx = 0
                    break
            self._sort()
        else:
            self._sort_col_idx = None

        self._filter()

        # Auto-size columns
        self._auto_size_columns()

        # If viewport has real dimensions, render immediately (revalidation
        # path where the widget is already on screen).  Otherwise defer all
        # widget creation to _deferred_layout — building headers, filters,
        # and rows here would be wasted because _deferred_layout will
        # rebuild them once the widget is visible and has a real viewport.
        if self._body_scroll.viewport().width() > 0:
            if columns_changed:
                self._rebuild_header()
                self._rebuild_filters()
            else:
                # Data-only refresh: update widths on existing cells
                # without recreating widgets (avoids focus theft).
                self._update_column_widths()
            self._recycle_all_rows()
            self._update_virtual_size()
            self._render_visible()
        else:
            QTimer.singleShot(0, self._deferred_layout)

        self._update_count_label()

        # Check compact after layout settles
        self._compact = False
        QTimer.singleShot(0, self._check_compact_mode)

    def set_loading(self):
        """Show loading state."""
        self._count_label.setText("Loading...")
        self._items = []
        self._cache = []
        self._filtered_indices = []
        self._recycle_all_rows()
        self._update_virtual_size()
        self._empty_label.setText("Loading...")
        self._empty_label.show()

    def set_columns(self, columns: list[ColumnDef]):
        """Replace the column definitions.  Caller must follow with set_data()."""
        self._all_columns = list(columns)
        self._active_columns = list(columns)
        self._full_col_keys = [c.key for c in columns]
        self._compact = False

    def set_footer(self, rows: list[dict], label_key: str | None = None):
        """Set footer aggregate rows."""
        # Clear old
        while self._footer_layout.count():
            item = self._footer_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not rows:
            self._footer_scroll.hide()
            return

        total_w = self._total_column_width()
        for row_data in rows:
            row_widget = QWidget()
            row_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            row_widget.setFixedHeight(self._row_height)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)

            for i, col in enumerate(self._active_columns):
                if col.get_value is not None:
                    raw = col.get_value(row_data)
                else:
                    raw = row_data.get(col.key)
                if col.format is not None:
                    text = str(col.format(raw))
                else:
                    text = str(raw) if raw is not None else ""

                lbl = QLabel(text)
                is_label = label_key and col.key == label_key
                color = TEXT_MUTED if is_label else TEXT
                lbl.setStyleSheet(
                    f"color: {color}; font-size: 12px; font-weight: bold;"
                    f" padding: 0 8px; background: transparent;"
                )
                width = self._col_widths[i] if i < len(self._col_widths) else MIN_COLUMN_WIDTH
                lbl.setFixedWidth(width)
                alignment = self._col_alignments[i] if i < len(self._col_alignments) else Qt.AlignmentFlag.AlignLeft
                lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | alignment)
                row_layout.addWidget(lbl)

            row_layout.addStretch()
            self._footer_layout.addWidget(row_widget)

        footer_h = self._row_height * len(rows)
        self._footer_inner.setFixedSize(total_w, footer_h)
        self._footer_scroll.setFixedHeight(footer_h)
        self._footer_scroll.show()

    def get_active_column_keys(self) -> list[str]:
        """Return the list of currently active column keys."""
        return [c.key for c in self._active_columns]

    def display_count(self) -> int:
        """Number of rows after filtering."""
        return len(self._filtered_indices)

    def total_count(self) -> int:
        """Total number of rows."""
        return len(self._cache)

    @property
    def config_button(self) -> QPushButton:
        """Expose the config button so callers can connect to it."""
        return self._config_btn

    @property
    def new_button(self) -> QPushButton:
        """Expose the new-entry button (hidden by default)."""
        return self._new_btn

    # -----------------------------------------------------------------------
    # Column auto-sizing
    # -----------------------------------------------------------------------

    def _auto_size_columns(self):
        """Calculate column widths by sampling content."""
        fm = QFontMetrics(self.font())
        col_count = len(self._active_columns)
        self._col_widths = [0] * col_count
        self._col_alignments = [Qt.AlignmentFlag.AlignLeft] * col_count

        sample_rows = self._cache[:200]

        for col_idx, col_def in enumerate(self._active_columns):
            # Alignment
            if col_def.alignment != Qt.AlignmentFlag.AlignLeft:
                self._col_alignments[col_idx] = col_def.alignment
            elif self._numeric[col_idx] if col_idx < len(self._numeric) else False:
                self._col_alignments[col_idx] = Qt.AlignmentFlag.AlignRight

            # Fixed width
            if col_def.width and col_def.width.endswith("px"):
                try:
                    self._col_widths[col_idx] = int(col_def.width[:-2])
                    continue
                except ValueError:
                    pass

            basis = col_def.width_basis
            max_chars = 4  # minimum

            if basis in ("header", "both"):
                max_chars = max(max_chars, len(col_def.header))

            if basis in ("content", "both"):
                for row in sample_rows:
                    if col_idx < len(row):
                        display = row[col_idx][1]
                        max_chars = max(max_chars, len(display))

            self._col_widths[col_idx] = fm.horizontalAdvance("x" * min(max_chars, 40)) + COLUMN_WIDTH_PADDING

        # Enforce minimum (higher minimum for the main/name column)
        for i in range(col_count):
            min_w = MIN_MAIN_COLUMN_WIDTH if self._active_columns[i].main else MIN_COLUMN_WIDTH
            if self._col_widths[i] < min_w:
                self._col_widths[i] = min_w

        # Fit main column to viewport: shrink or grow to fill available space
        viewport_w = self._body_scroll.viewport().width()
        if viewport_w > 0:
            main_idx = next((i for i, c in enumerate(self._active_columns) if c.main), None)
            if main_idx is not None:
                # Reserve space for vertical scrollbar when rows exceed max_visible_rows
                row_count = len(self._filtered_indices) if self._filtered_indices else len(self._items)
                needs_vscroll = (self._max_visible_rows is not None
                                 and row_count > self._max_visible_rows)
                sb_reserve = self._sb_width if needs_vscroll else 0
                other_width = sum(w for i, w in enumerate(self._col_widths) if i != main_idx)
                available = viewport_w - other_width - sb_reserve
                self._col_widths[main_idx] = max(available, MIN_MAIN_COLUMN_WIDTH)

    def _deferred_layout(self, _retries: int = 3):
        """Re-render after the viewport has its real dimensions."""
        if not self._items:
            return
        # Viewport may still be 0 if the widget hasn't been shown yet
        # (e.g. set_data() called before _swap_content makes it visible).
        # Retry a few times to let the event loop process the show.
        if self._body_scroll.viewport().width() <= 0:
            if _retries > 0:
                QTimer.singleShot(0, lambda: self._deferred_layout(_retries - 1))
            return
        self._auto_size_columns()
        columns_changed = len(self._header_cells) != len(self._active_columns)
        if columns_changed:
            self._rebuild_header()
            self._rebuild_filters()
        else:
            self._update_column_widths()
        self._recycle_all_rows()
        self._update_virtual_size()
        self._render_visible()

    def _total_column_width(self) -> int:
        """Sum of all column widths."""
        return sum(self._col_widths)

    # -----------------------------------------------------------------------
    # Header / filter rebuild
    # -----------------------------------------------------------------------

    def _rebuild_header(self):
        """Rebuild header cells to match active columns."""
        for cell in self._header_cells:
            cell.deleteLater()
        self._header_cells.clear()
        # Remove old stretch item if present
        while self._header_layout.count():
            item = self._header_layout.takeAt(0)

        total_w = self._total_column_width()

        for i, col in enumerate(self._active_columns):
            cell = _HeaderCell(
                i, col.header, col.sortable and self._sortable,
                reorderable=self._reorderable, resizable=self._resizable,
            )
            cell.setFixedWidth(self._col_widths[i] if i < len(self._col_widths) else MIN_COLUMN_WIDTH)
            cell.setFixedHeight(self._row_height)
            cell.clicked.connect(self._on_header_clicked)
            cell.drag_moved.connect(self._on_header_drag_moved)
            cell.drag_finished.connect(self._on_header_drag_finished)
            cell.resize_moved.connect(self._on_header_resize_moved)
            cell.resize_finished.connect(self._on_header_resize_finished)
            self._header_layout.addWidget(cell)
            self._header_cells.append(cell)

        self._header_layout.addStretch()
        self._update_sort_indicators()

        # Set inner widget to at least viewport width
        viewport_w = self._body_scroll.viewport().width()
        self._header_inner.setFixedWidth(max(total_w, viewport_w))

    def _rebuild_filters(self):
        """Rebuild filter inputs to match active columns."""
        for inp in self._filter_inputs:
            inp.deleteLater()
        self._filter_inputs.clear()
        while self._filter_layout.count():
            self._filter_layout.takeAt(0)

        total_w = self._total_column_width()

        for i, col in enumerate(self._active_columns):
            inp = QLineEdit()
            inp.setPlaceholderText("Filter...")
            inp.setFixedHeight(FILTER_HEIGHT - 2)
            inp.setFixedWidth(self._col_widths[i] if i < len(self._col_widths) else MIN_COLUMN_WIDTH)
            inp.setTextMargins(4, 0, 4, 0)
            inp.setStyleSheet(
                f"font-size: 11px;"
                f" background-color: {MAIN_DARK}; color: {TEXT};"
                f" border: none; border-right: 1px solid {BORDER};"
            )
            if not (col.searchable and self._searchable):
                inp.setEnabled(False)
                inp.setPlaceholderText("")
            inp.textChanged.connect(self._on_filter_changed)
            self._filter_layout.addWidget(inp)
            self._filter_inputs.append(inp)

        self._filter_layout.addStretch()
        viewport_w = self._body_scroll.viewport().width()
        self._filter_inner.setFixedWidth(max(total_w, viewport_w))

        # Restore filter texts (e.g. after column reorder)
        for i, inp in enumerate(self._filter_inputs):
            if i < len(self._col_filters) and self._col_filters[i]:
                inp.blockSignals(True)
                inp.setText(self._col_filters[i])
                inp.blockSignals(False)

    def _update_column_widths(self):
        """Update widths on existing header cells and filter inputs.

        Used during data-only refreshes (e.g. pagination) to avoid
        recreating widgets and the focus-stealing that entails.
        """
        total_w = self._total_column_width()
        viewport_w = self._body_scroll.viewport().width()
        inner_w = max(total_w, viewport_w)
        for i, cell in enumerate(self._header_cells):
            if i < len(self._col_widths):
                cell.setFixedWidth(self._col_widths[i])
        for i, inp in enumerate(self._filter_inputs):
            if i < len(self._col_widths):
                inp.setFixedWidth(self._col_widths[i])
        self._header_inner.setFixedWidth(inner_w)
        self._filter_inner.setFixedWidth(inner_w)

    # -----------------------------------------------------------------------
    # Sorting
    # -----------------------------------------------------------------------

    def _on_header_clicked(self, col_idx: int):
        """Handle header click — toggle sort or cycle phase."""
        col = self._active_columns[col_idx]
        if not col.sortable or not self._sortable:
            return

        if col.sort_phases:
            if self._sort_col_idx == col_idx:
                self._sort_phase_idx = (self._sort_phase_idx + 1) % len(col.sort_phases)
            else:
                self._sort_col_idx = col_idx
                self._sort_phase_idx = 0
            phase = col.sort_phases[self._sort_phase_idx]
            self._sort_direction = phase.order
        else:
            if self._sort_col_idx == col_idx:
                self._sort_direction = "DESC" if self._sort_direction == "ASC" else "ASC"
            else:
                self._sort_col_idx = col_idx
                self._sort_direction = "ASC"
                self._sort_phase_idx = 0

        self._sort()
        self._filter()
        self._update_sort_indicators()
        self._recycle_all_rows()
        self._update_virtual_size()
        self._render_visible()
        self._update_count_label()

        if self._sort_col_idx is not None:
            self.sort_changed.emit(
                self._active_columns[self._sort_col_idx].key,
                self._sort_direction,
            )

    def _sort(self):
        """Sort the data by current sort column."""
        if self._sort_col_idx is None:
            self._sorted_indices = list(range(len(self._cache)))
            return

        col_idx = self._sort_col_idx
        col = self._active_columns[col_idx]

        # Determine sort key function
        if col.sort_phases and self._sort_phase_idx < len(col.sort_phases):
            phase = col.sort_phases[self._sort_phase_idx]
            raw_key = phase.sort_value
        elif col.sort_value:
            raw_key = col.sort_value
        else:
            raw_key = None

        is_desc = self._sort_direction == "DESC"

        def safe_key(row_idx):
            if raw_key:
                v = raw_key(self._items[row_idx])
            else:
                v = self._cache[row_idx][col_idx][0]
            # None/empty always sorts to bottom regardless of direction.
            # For DESC (reverse=True), we need (False, ...) for None so
            # it ends up at the end after reversal.
            is_empty = v is None or v == "" or v == "-"
            if is_desc:
                return (not is_empty, v if not is_empty else 0)
            return (is_empty, v if not is_empty else 0)

        if col.sort_fn:
            import functools
            def _is_empty(v):
                return v is None or v == "" or v == "-"

            def cmp_wrapper(a, b):
                va = raw_key(self._items[a]) if raw_key else self._cache[a][col_idx][0]
                vb = raw_key(self._items[b]) if raw_key else self._cache[b][col_idx][0]
                a_empty, b_empty = _is_empty(va), _is_empty(vb)
                if a_empty and b_empty:
                    return 0
                if a_empty:
                    return 1
                if b_empty:
                    return -1
                return col.sort_fn(va, vb)
            self._sorted_indices = sorted(
                range(len(self._cache)),
                key=functools.cmp_to_key(cmp_wrapper),
                reverse=(self._sort_direction == "DESC"),
            )
        else:
            self._sorted_indices = sorted(
                range(len(self._cache)),
                key=safe_key,
                reverse=(self._sort_direction == "DESC"),
            )

    def _update_sort_indicators(self):
        """Update all header cell sort indicators."""
        for i, cell in enumerate(self._header_cells):
            if i == self._sort_col_idx:
                col = self._active_columns[i]
                color = None
                if col.sort_phases and self._sort_phase_idx < len(col.sort_phases):
                    color = col.sort_phases[self._sort_phase_idx].color
                cell.set_sort_indicator(self._sort_direction, color)
            else:
                cell.set_sort_indicator(None)

    # -----------------------------------------------------------------------
    # Column reorder (header drag)
    # -----------------------------------------------------------------------

    def _on_header_drag_moved(self, col_idx: int, global_x: int):
        """Show drop indicator at the target insertion position."""
        local_x = self._header_inner.mapFromGlobal(QPoint(global_x, 0)).x()
        target = self._find_drop_index(local_x)
        x_pos = sum(self._col_widths[:target])
        self._drop_indicator.setFixedHeight(self._row_height)
        self._drop_indicator.move(x_pos - 1, 0)
        self._drop_indicator.show()
        self._drop_indicator.raise_()

    def _on_header_drag_finished(self, col_idx: int, global_x: int):
        """Perform column reorder on drag release."""
        self._drop_indicator.hide()
        local_x = self._header_inner.mapFromGlobal(QPoint(global_x, 0)).x()
        target = self._find_drop_index(local_x)
        if target != col_idx and target != col_idx + 1:
            # Adjust target for pop/insert semantics
            to_idx = target if target < col_idx else target - 1
            self._reorder_column(col_idx, to_idx)

    def _find_drop_index(self, local_x: int) -> int:
        """Find insertion index from x position in header."""
        cum = 0
        for i, w in enumerate(self._col_widths):
            mid = cum + w // 2
            if local_x < mid:
                return i
            cum += w
        return len(self._col_widths)

    def _reorder_column(self, from_idx: int, to_idx: int):
        """Move a column from one position to another, updating all state."""
        if from_idx == to_idx:
            return

        def _move(lst, f, t):
            item = lst.pop(f)
            lst.insert(t, item)

        _move(self._active_columns, from_idx, to_idx)
        if not self._compact:
            _move(self._all_columns, from_idx, to_idx)
        _move(self._col_widths, from_idx, to_idx)
        _move(self._col_alignments, from_idx, to_idx)
        _move(self._numeric, from_idx, to_idx)
        for row in self._cache:
            _move(row, from_idx, to_idx)

        # Remap sort column index
        if self._sort_col_idx is not None:
            if self._sort_col_idx == from_idx:
                self._sort_col_idx = to_idx
            elif from_idx < self._sort_col_idx <= to_idx:
                self._sort_col_idx -= 1
            elif to_idx <= self._sort_col_idx < from_idx:
                self._sort_col_idx += 1

        # Remap filter texts
        if len(self._col_filters) > max(from_idx, to_idx):
            _move(self._col_filters, from_idx, to_idx)

        # Rebuild UI
        self._rebuild_header()
        self._rebuild_filters()
        self._recycle_all_rows()
        self._render_visible()

        self.columns_reordered.emit([c.key for c in self._active_columns])

    # -----------------------------------------------------------------------
    # Column resize (header edge drag)
    # -----------------------------------------------------------------------

    def _on_header_resize_moved(self, col_idx: int, global_x: int):
        """Live-update column width while dragging the header edge."""
        if col_idx >= len(self._header_cells):
            return
        cell = self._header_cells[col_idx]
        cell_left = cell.mapToGlobal(QPoint(0, 0)).x()
        new_w = max(global_x - cell_left, MIN_RESIZE_WIDTH)
        self._col_widths[col_idx] = new_w
        # Update in-place for smooth feedback
        cell.setFixedWidth(new_w)
        if col_idx < len(self._filter_inputs):
            self._filter_inputs[col_idx].setFixedWidth(new_w)
        # Update container widths
        total_w = self._total_column_width()
        viewport_w = self._body_scroll.viewport().width()
        w = max(total_w, viewport_w)
        self._header_inner.setFixedWidth(w)
        self._filter_inner.setFixedWidth(w)
        # Re-render rows
        self._recycle_all_rows()
        self._update_virtual_size()
        self._render_visible()

    def _on_header_resize_finished(self, col_idx: int):
        """Finalize column resize (already applied live)."""
        pass

    # -----------------------------------------------------------------------
    # Filtering
    # -----------------------------------------------------------------------

    def _on_filter_changed(self):
        """Schedule filter application with debounce."""
        self._filter_timer.start()

    def _apply_filters(self):
        """Push current filter texts into the pipeline."""
        self._col_filters = [inp.text() for inp in self._filter_inputs]
        self._filter()
        self._recycle_all_rows()
        self._update_virtual_size()
        self._render_visible()
        self._update_count_label()

    def _filter(self):
        """Filter sorted indices by column filters."""
        if not any(f.strip() for f in self._col_filters):
            self._filtered_indices = list(self._sorted_indices)
            return

        result = []
        for row_idx in self._sorted_indices:
            if self._row_matches_filters(row_idx):
                result.append(row_idx)
        self._filtered_indices = result

    def _row_matches_filters(self, row_idx: int) -> bool:
        """Check if a row matches all active column filters."""
        for col_idx, ft in enumerate(self._col_filters):
            if not ft.strip():
                continue
            if col_idx >= len(self._cache[row_idx]):
                continue
            raw, display = self._cache[row_idx][col_idx]
            if not _matches_filter(raw, display, ft):
                return False
        return True

    # -----------------------------------------------------------------------
    # Virtualisation
    # -----------------------------------------------------------------------

    def _update_virtual_size(self):
        """Set the virtual container size to accommodate all filtered rows."""
        count = len(self._filtered_indices)
        total_w = self._total_column_width()
        viewport_w = self._body_scroll.viewport().width()
        h = max(count * self._row_height, 1)
        self._virtual_container.setFixedSize(max(total_w, viewport_w), h)

        # Cap body scroll area height when max_visible_rows is set
        if self._max_visible_rows is not None:
            max_h = self._max_visible_rows * self._row_height
            actual_h = min(count * self._row_height, max_h) if count > 0 else self._row_height
            # +2 for border allowance
            self._body_scroll.setFixedHeight(actual_h + 2)

        # Show/hide empty message
        if count == 0 and self._items:
            self._empty_label.setText("No results matching filters")
            self._empty_label.show()
        elif count == 0:
            self._empty_label.setText(self._empty_message)
            self._empty_label.show()
        else:
            self._empty_label.hide()

        # Sync now (catches already-settled layouts) and after Qt processes
        # the size change (scrollbar visibility may lag by one event loop tick).
        self._sync_scrollbar_margin()
        QTimer.singleShot(0, self._sync_scrollbar_margin)

    def _render_visible(self):
        """Render only the rows visible in the viewport + buffer."""
        if not self._filtered_indices:
            self._recycle_all_rows()
            return

        scroll_top = self._body_scroll.verticalScrollBar().value()
        viewport_height = self._body_scroll.viewport().height()
        if viewport_height <= 0:
            return

        first_visible = scroll_top // self._row_height
        last_visible = (scroll_top + viewport_height) // self._row_height

        render_start = max(0, first_visible - SCROLL_BUFFER_ROWS)
        render_end = min(len(self._filtered_indices), last_visible + SCROLL_BUFFER_ROWS + 1)

        if (render_start, render_end) == self._last_render_range:
            return
        self._last_render_range = (render_start, render_end)

        needed = set(range(render_start, render_end))
        current = set(self._active_rows.keys())

        # Recycle rows no longer needed
        to_recycle = current - needed
        for di in to_recycle:
            row = self._active_rows.pop(di)
            row.hide()
            self._row_pool.append(row)

        # Assign rows for new indices
        col_count = len(self._active_columns)
        viewport_w = self._body_scroll.viewport().width()
        row_width = max(self._total_column_width(), viewport_w)
        for di in sorted(needed - current):
            row = self._get_or_create_row(col_count)
            data_idx = self._filtered_indices[di]

            # Get display texts
            texts = []
            for ci in range(col_count):
                if ci < len(self._cache[data_idx]):
                    texts.append(self._cache[data_idx][ci][1])
                else:
                    texts.append("")

            # Alternating row color
            bg = TABLE_ROW_ALT if (di % 2 == 1) else PRIMARY

            row.configure_columns(self._col_widths, self._col_alignments, row_width)
            row.set_data(di, data_idx, texts, bg)
            row.move(0, di * self._row_height)
            row.show()
            self._active_rows[di] = row

    def _get_or_create_row(self, col_count: int) -> _TableRow:
        """Get a row from the pool or create a new one."""
        if self._row_pool:
            row = self._row_pool.pop()
            if len(row._cells) != col_count:
                row.deleteLater()
                return self._create_row(col_count)
            return row
        return self._create_row(col_count)

    def _create_row(self, col_count: int) -> _TableRow:
        """Create a new row widget parented to the virtual container."""
        row = _TableRow(col_count, self._row_height, self._virtual_container)
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.mousePressEvent = lambda event, r=row: self._on_row_mouse_press(event, r)
        row.mouseDoubleClickEvent = lambda event, r=row: self._on_row_double_click(event, r)
        row.enterEvent = lambda event, r=row: self._on_row_enter(event, r)
        row.leaveEvent = lambda event, r=row: self._on_row_leave(event, r)
        return row

    def _recycle_all_rows(self):
        """Return all active rows to the pool."""
        for row in self._active_rows.values():
            row.hide()
            self._row_pool.append(row)
        self._active_rows.clear()
        self._last_render_range = (-1, -1)

    # -----------------------------------------------------------------------
    # Row interaction
    # -----------------------------------------------------------------------

    def _on_row_mouse_press(self, event, row: _TableRow):
        if event.button() == Qt.MouseButton.LeftButton:
            data_idx = row.data_index
            if 0 <= data_idx < len(self._items):
                self.row_clicked.emit(self._items[data_idx], data_idx)

    def _on_row_double_click(self, event, row: _TableRow):
        if event.button() == Qt.MouseButton.LeftButton:
            data_idx = row.data_index
            if 0 <= data_idx < len(self._items):
                self.row_activated.emit(self._items[data_idx], data_idx)

    def _on_row_enter(self, event, row: _TableRow):
        row.setStyleSheet(f"background-color: {_ROW_HOVER_COLOR};")
        data_idx = row.data_index
        if 0 <= data_idx < len(self._items):
            self.row_hover.emit(self._items[data_idx])

    def _on_row_leave(self, event, row: _TableRow):
        bg = TABLE_ROW_ALT if (row.display_index % 2 == 1) else PRIMARY
        row.setStyleSheet(f"background-color: {bg};")
        self.row_hover.emit(None)

    # -----------------------------------------------------------------------
    # Compact mode
    # -----------------------------------------------------------------------

    def _estimate_full_width(self) -> int:
        """Estimate total width if all columns were shown."""
        fm = QFontMetrics(self.font())
        total = 0
        for col in self._all_columns:
            if col.width and col.width.endswith("px"):
                try:
                    total += int(col.width[:-2])
                    continue
                except ValueError:
                    pass
            total += fm.horizontalAdvance("x" * len(col.header)) + COLUMN_WIDTH_PADDING
        return total

    def _check_compact_mode(self):
        """Auto-compact columns when the window is narrower than the breakpoint."""
        if not self._items or len(self._all_columns) <= self._compact_threshold:
            return

        window = self.window()
        if not window:
            return
        ww = window.width()

        if self._compact:
            if ww >= COMPACT_WIDTH_BREAKPOINT + COMPACT_HYSTERESIS:
                self._compact = False
                self._active_columns = list(self._all_columns)
                self._rebuild_after_column_change()
        else:
            if ww < COMPACT_WIDTH_BREAKPOINT:
                self._compact = True
                self._active_columns = self._all_columns[:self._compact_threshold]
                self._rebuild_after_column_change()

    def _rebuild_after_column_change(self):
        """Re-cache and re-render after the active column set changes."""
        self._cache, self._numeric = build_fancy_cache(self._items, self._active_columns)

        if self._sort_col_idx is not None:
            if self._sort_col_idx >= len(self._active_columns):
                self._sort_col_idx = None

        self._sorted_indices = list(range(len(self._cache)))
        self._col_filters = [""] * len(self._active_columns)

        if self._sort_col_idx is not None:
            self._sort()
        self._filter()

        self._auto_size_columns()
        self._rebuild_header()
        self._rebuild_filters()
        self._recycle_all_rows()
        self._update_virtual_size()
        self._render_visible()
        self._update_count_label()

    def showEvent(self, event):
        """Trigger deferred layout when the widget first becomes visible."""
        super().showEvent(event)
        if self._items:
            QTimer.singleShot(0, self._deferred_layout)

    def resizeEvent(self, event):
        """Re-check compact mode and update layout on resize."""
        super().resizeEvent(event)
        if self._items:
            self._compact_timer.start()
            self._auto_size_columns()
            self._rebuild_header()
            self._rebuild_filters()
            self._recycle_all_rows()
            self._update_virtual_size()
        self._last_render_range = (-1, -1)
        QTimer.singleShot(0, self._render_visible)

    # -----------------------------------------------------------------------
    # Count label
    # -----------------------------------------------------------------------

    def _update_count_label(self):
        total = len(self._items)
        visible = len(self._filtered_indices)
        parts = []
        if visible != total:
            parts.append(f"{visible} / {total} items")
        else:
            parts.append(f"{total} items")
        if self._compact:
            parts.append(
                f"{len(self._active_columns)} of "
                f"{len(self._all_columns)} columns"
            )
        self._count_label.setText(" \u00b7 ".join(parts))
        self._compact_hint.setVisible(self._compact)
