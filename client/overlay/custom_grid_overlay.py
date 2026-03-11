"""CustomGridOverlay — user-configurable tile-based modular grid overlay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, QPoint, QSize
from PyQt6.QtGui import QPainter, QColor, QPen

from .overlay_widget import OverlayWidget
from .custom_grid.widget_registry import WidgetRegistry
from .custom_grid.grid_widget import GridWidget, WidgetContext
from .custom_grid.cell_container import CellContainer
from .custom_grid.widget_picker_dialog import WidgetPickerDialog
from ..core.config import save_config
from ..ui.icons import svg_icon
from ..core.logger import get_logger

if TYPE_CHECKING:
    from .overlay_manager import OverlayManager

log = get_logger("CustomGridOverlay")

_LAYOUT_VERSION = 1

# --- Colours matching the existing overlay palette ---
BG_COLOR = "rgba(20, 20, 30, 180)"
TITLE_BG = "rgba(30, 30, 45, 200)"
TAB_HOVER_BG = "rgba(50, 50, 70, 180)"
TAB_ACTIVE_BG = "rgba(60, 60, 90, 200)"
CONTENT_BG = "rgba(22, 22, 34, 190)"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#999999"
ACCENT = "#00ccff"
GRID_LINE_COLOR = QColor(55, 55, 80, 160)
GRID_BG = QColor(18, 18, 28, 220)

_TITLE_H = 24
_FOOTER_H = 22

_TILE_SIZES = [20, 30, 40]  # S, M, L pixels per tile
_TILE_LABELS = ["S", "M", "L"]
_TILE_TOOLTIPS = ["Small (20 px/tile)", "Medium (30 px/tile)", "Large (40 px/tile)"]
_MIN_TILES = 1
_MAX_TILES = 20

# --- SVG icons ---
_CLOSE_SVG = (
    '<path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59'
    ' 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>'
)
_GRID_SVG = (
    '<path d="M3 3v18h18V3H3zm8 16H5v-6h6v6zm0-8H5V5h6v6zm8 8h-6v-6h6v6z'
    'm0-8h-6V5h6v6z"/>'
)
_EDIT_SVG = (
    '<path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c'
    '.39-.39.39-1.02 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75'
    ' 3.75 1.83-1.83z"/>'
)
_PLUS_SVG = '<path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>'
_IMPORT_SVG = '<path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>'
_EXPORT_SVG = '<path d="M5 15H3v4a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-4h-2v4H5v-4zm8-9.83l2.59 2.58L17 6.34 12 1.17 7 6.34l1.41 1.41L11 5.17V15h2V5.17z"/>'

_BTN_STYLE = (
    "QPushButton {"
    "  background: transparent; border: none; border-radius: 3px;"
    "  padding: 0px; margin: 0px;"
    "}"
    f"QPushButton:hover {{ background-color: {TAB_HOVER_BG}; }}"
    f"QPushButton:checked {{ background-color: {TAB_ACTIVE_BG}; }}"
)
_FOOTER_BTN_STYLE = (
    f"QPushButton {{ background: transparent; color: {TEXT_DIM}; border: none;"
    "  border-radius: 3px; padding: 1px 6px; font-size: 10px; }}"
    f"QPushButton:hover {{ background: {TAB_HOVER_BG}; color: {TEXT_COLOR}; }}"
)
_TILE_COUNT_STYLE = (
    f"color: {TEXT_COLOR}; font-size: 10px; font-weight: bold; padding: 0 3px;"
)


class _SlotEntry:
    """Tracks one placed widget with its tile-grid position."""

    __slots__ = ("grid_widget", "container", "col", "row", "colspan", "rowspan")

    def __init__(
        self,
        grid_widget: GridWidget,
        container: CellContainer,
        col: int,
        row: int,
        colspan: int,
        rowspan: int,
    ):
        self.grid_widget = grid_widget
        self.container = container
        self.col = col
        self.row = row
        self.colspan = colspan
        self.rowspan = rowspan


class _GridCanvas(QWidget):
    """Fixed-size tile canvas that owns and positions CellContainer children.

    All grid interaction (drag to move, right-click menu) is handled here
    so that widget containers can be WA_TransparentForMouseEvents in edit mode.
    """

    def __init__(self, parent: QWidget, save_fn: Callable):
        super().__init__(parent)
        self._save_fn = save_fn
        self._slots: list[_SlotEntry] = []
        self._edit_mode = False
        self._tile_px = _TILE_SIZES[0]
        self._cols = 6
        self._rows = 4
        self._drag_slot: _SlotEntry | None = None
        self._drag_offset = QPoint()
        self._add_widget_fn: Callable | None = None  # called with (col, row)
        self.setMouseTracking(True)
        self._apply_size()

    def set_grid(self, cols: int, rows: int, tile_px: int) -> None:
        self._cols = max(_MIN_TILES, min(_MAX_TILES, cols))
        self._rows = max(_MIN_TILES, min(_MAX_TILES, rows))
        self._tile_px = tile_px
        self._apply_size()
        self._layout_slots()

    def _apply_size(self) -> None:
        w = self._cols * self._tile_px
        h = self._rows * self._tile_px
        self.setFixedSize(w, h)

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled
        for slot in self._slots:
            slot.container.set_edit_mode(enabled)
        self.update()

    # --- Slot management ---

    def add_slot(self, slot: _SlotEntry) -> None:
        self._slots.append(slot)
        slot.container.setParent(self)
        self._place_slot(slot)
        slot.container.show()

    def remove_slot(self, slot: _SlotEntry) -> None:
        if slot in self._slots:
            self._slots.remove(slot)
        slot.container.setParent(None)
        slot.container.deleteLater()

    def _place_slot(self, slot: _SlotEntry) -> None:
        t = self._tile_px
        slot.container.setGeometry(
            slot.col * t,
            slot.row * t,
            slot.colspan * t,
            slot.rowspan * t,
        )

    def _layout_slots(self) -> None:
        for slot in self._slots:
            self._place_slot(slot)

    # --- Position queries ---

    def _slot_at(self, pos: QPoint) -> _SlotEntry | None:
        t = self._tile_px
        col = pos.x() // t
        row = pos.y() // t
        for slot in self._slots:
            if (slot.col <= col < slot.col + slot.colspan
                    and slot.row <= row < slot.row + slot.rowspan):
                return slot
        return None

    def _tile_at(self, pos: QPoint) -> tuple[int, int]:
        t = self._tile_px
        return pos.x() // t, pos.y() // t

    # --- Occupancy helpers ---

    def _overlaps(self, exclude: _SlotEntry, col: int, row: int) -> bool:
        cs = exclude.colspan
        rs = exclude.rowspan
        for slot in self._slots:
            if slot is exclude:
                continue
            if (col < slot.col + slot.colspan and col + cs > slot.col
                    and row < slot.row + slot.rowspan and row + rs > slot.row):
                return True
        return False

    def find_free_position(self, colspan: int, rowspan: int) -> tuple[int, int] | None:
        """Return first (col, row) that fits colspan×rowspan without overlap."""
        occupied: set[tuple[int, int]] = set()
        for slot in self._slots:
            for r in range(slot.row, slot.row + slot.rowspan):
                for c in range(slot.col, slot.col + slot.colspan):
                    occupied.add((c, r))
        for row in range(self._rows - rowspan + 1):
            for col in range(self._cols - colspan + 1):
                if all(
                    (c, r) not in occupied
                    for r in range(row, row + rowspan)
                    for c in range(col, col + colspan)
                ):
                    return col, row
        return None

    # --- Mouse events (edit mode only) ---

    def mousePressEvent(self, event):
        if not self._edit_mode:
            return
        pos = event.position().toPoint()

        if event.button() == Qt.MouseButton.LeftButton:
            slot = self._slot_at(pos)
            if slot:
                self._drag_slot = slot
                t = self._tile_px
                self._drag_offset = pos - QPoint(slot.col * t, slot.row * t)
                slot.container.raise_()

        elif event.button() == Qt.MouseButton.RightButton:
            slot = self._slot_at(pos)
            self._show_context_menu(slot, event.globalPosition().toPoint(), pos)

    def mouseMoveEvent(self, event):
        if self._drag_slot and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.position().toPoint() - self._drag_offset
            self._drag_slot.container.move(
                max(0, min(new_pos.x(), self.width() - self._drag_slot.colspan * self._tile_px)),
                max(0, min(new_pos.y(), self.height() - self._drag_slot.rowspan * self._tile_px)),
            )

    def mouseReleaseEvent(self, event):
        if not (self._drag_slot and event.button() == Qt.MouseButton.LeftButton):
            return
        slot = self._drag_slot
        self._drag_slot = None

        t = self._tile_px
        new_col = max(0, min(self._cols - slot.colspan, round(slot.container.x() / t)))
        new_row = max(0, min(self._rows - slot.rowspan, round(slot.container.y() / t)))
        if not self._overlaps(slot, new_col, new_row):
            slot.col = new_col
            slot.row = new_row
        self._place_slot(slot)
        self._save_fn()

    # --- Context menu ---

    def _show_context_menu(
        self,
        slot: _SlotEntry | None,
        global_pos: QPoint,
        local_pos: QPoint,
    ) -> None:
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1e1e2d; color: #e0e0e0; border: 1px solid #555; }"
            "QMenu::item { padding: 4px 20px; }"
            "QMenu::item:selected { background: #333355; }"
        )
        if slot:
            menu.addAction("Replace…", lambda: self._replace_slot(slot))
            menu.addSeparator()
            menu.addAction("Move left",  lambda: self._move_slot(slot, -1, 0))
            menu.addAction("Move right", lambda: self._move_slot(slot,  1, 0))
            menu.addAction("Move up",    lambda: self._move_slot(slot,  0, -1))
            menu.addAction("Move down",  lambda: self._move_slot(slot,  0,  1))
            menu.addSeparator()
            rm = menu.addAction("Remove", lambda: self._request_remove(slot))
            rm.setIcon(menu.style().standardIcon(
                menu.style().StandardPixmap.SP_DialogDiscardButton
            ))
        else:
            col, row = self._tile_at(local_pos)
            menu.addAction(
                "Add Widget here…",
                lambda: self._add_widget_at(col, row),
            )
        menu.exec(global_pos)

    def _move_slot(self, slot: _SlotEntry, dc: int, dr: int) -> None:
        nc = max(0, min(self._cols - slot.colspan, slot.col + dc))
        nr = max(0, min(self._rows - slot.rowspan, slot.row + dr))
        if not self._overlaps(slot, nc, nr):
            slot.col = nc
            slot.row = nr
            self._place_slot(slot)
            self._save_fn()

    def _request_remove(self, slot: _SlotEntry) -> None:
        if self._remove_fn:
            self._remove_fn(slot)

    def _replace_slot(self, slot: _SlotEntry) -> None:
        if self._replace_fn:
            self._replace_fn(slot)

    def _add_widget_at(self, col: int, row: int) -> None:
        if self._add_widget_fn:
            self._add_widget_fn(col, row)

    # --- Paint ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(0, 0, self.width(), self.height(), GRID_BG)

        if not self._edit_mode:
            return

        # Grid lines
        pen = QPen(GRID_LINE_COLOR, 1)
        pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(pen)
        t = self._tile_px
        for c in range(self._cols + 1):
            x = c * t
            painter.drawLine(x, 0, x, self.height())
        for r in range(self._rows + 1):
            y = r * t
            painter.drawLine(0, y, self.width(), y)

    # Callbacks set by CustomGridOverlay after construction
    _remove_fn: Callable | None = None
    _replace_fn: Callable | None = None


class CustomGridOverlay(OverlayWidget):
    """Modular tile-based grid overlay.

    The grid is N cols × M rows tiles, each tile ``tile_px`` pixels wide/tall.
    Tile size is set by S/M/L buttons (20/30/40 px) in the title bar.
    Grid dimensions are adjusted by the +/- controls in the footer (edit mode).

    Each *GridWidget* occupies a user-defined rectangular region (col, row,
    colspan, rowspan).  Widgets are dragged to new positions in edit mode.
    """

    def __init__(
        self,
        *,
        config,
        config_path: str,
        event_bus,
        data_client=None,
        exchange_store=None,
        hunt_tracker=None,
        manager: OverlayManager | None = None,
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="custom_grid_overlay_position",
            manager=manager,
        )
        self._event_bus = event_bus
        self._data_client = data_client
        self._exchange_store = exchange_store
        self._hunt_tracker = hunt_tracker
        self._edit_mode = False
        self._minified = False
        self._click_origin: QPoint | None = None

        # Widget registry
        user_dir = Path(config.database_path).parent / "custom_widgets"
        self._registry = WidgetRegistry(user_dir)
        self._registry.discover()

        # Override OverlayWidget container — children handle styling
        self._container.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self._container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar
        self._title_bar = self._build_title_bar()
        main_layout.addWidget(self._title_bar)

        # Body (hidden when minified)
        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self._grid_canvas = _GridCanvas(self._body, self._save_widgets)
        self._grid_canvas._remove_fn = self._remove_slot
        self._grid_canvas._replace_fn = self._replace_slot
        self._grid_canvas._add_widget_fn = self._add_widget_at
        body_layout.addWidget(self._grid_canvas)

        # Footer (edit mode controls)
        self._footer = self._build_footer()
        body_layout.addWidget(self._footer)
        self._footer.hide()

        main_layout.addWidget(self._body)

        # Apply initial grid from config
        self._sync_grid_to_config()
        self._restore_widgets()

    # --- Title bar ---

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(_TITLE_H)
        bar.setStyleSheet(
            f"background-color: {TITLE_BG};"
            " border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        # Grid icon
        icon_lbl = QLabel()
        icon_lbl.setPixmap(svg_icon(_GRID_SVG, ACCENT, 14).pixmap(14, 14))
        icon_lbl.setStyleSheet("background: transparent;")
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        # Title
        title_lbl = QLabel("Custom Grid")
        title_lbl.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            " background: transparent;"
        )
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(title_lbl, 1, Qt.AlignmentFlag.AlignVCenter)

        # Tile size buttons [S][M][L]
        tile_idx = getattr(self._config, "custom_grid_overlay_tile_size", 0)
        self._tile_buttons: list[QPushButton] = []
        for i, label in enumerate(_TILE_LABELS):
            btn = QPushButton(label)
            btn.setFixedSize(18, 18)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(_TILE_TOOLTIPS[i])
            btn.setStyleSheet(self._tile_btn_style(i == tile_idx))
            btn.clicked.connect(lambda _, idx=i: self._set_tile_size(idx))
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)
            self._tile_buttons.append(btn)

        # Edit toggle
        self._edit_btn = QPushButton()
        self._edit_btn.setFixedSize(18, 18)
        self._edit_btn.setCheckable(True)
        self._edit_btn.setIcon(svg_icon(_EDIT_SVG, TEXT_DIM, 12))
        self._edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._edit_btn.setToolTip("Edit layout")
        self._edit_btn.setStyleSheet(_BTN_STYLE)
        self._edit_btn.toggled.connect(self._set_edit_mode)
        layout.addWidget(self._edit_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Close
        close_btn = QPushButton()
        close_btn.setFixedSize(18, 18)
        close_btn.setIcon(svg_icon(_CLOSE_SVG, TEXT_DIM, 14))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Hide")
        close_btn.setStyleSheet(_BTN_STYLE)
        close_btn.clicked.connect(lambda: self.set_wants_visible(False))
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return bar

    @staticmethod
    def _tile_btn_style(active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ color: {ACCENT}; font-size: 10px; font-weight: 700;"
                f" background: {TAB_ACTIVE_BG}; border: 1px solid {ACCENT};"
                " border-radius: 3px; padding: 0px; }}"
            )
        return (
            f"QPushButton {{ color: {TEXT_DIM}; font-size: 10px; font-weight: 600;"
            f" background: transparent; border: 1px solid transparent;"
            " border-radius: 3px; padding: 0px; }}"
            f"QPushButton:hover {{ color: {TEXT_COLOR}; background: {TAB_HOVER_BG}; }}"
        )

    # --- Footer (edit mode controls) ---

    def _build_footer(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(_FOOTER_H)
        bar.setStyleSheet(
            f"background-color: {TITLE_BG};"
            " border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(4)

        # Add widget
        add_btn = QPushButton()
        add_btn.setFixedSize(16, 16)
        add_btn.setIcon(svg_icon(_PLUS_SVG, TEXT_DIM, 12))
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setToolTip("Add widget")
        add_btn.setStyleSheet(_BTN_STYLE)
        add_btn.clicked.connect(lambda: self._add_widget_at(None, None))
        layout.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Import / Export
        imp_btn = QPushButton()
        imp_btn.setFixedSize(16, 16)
        imp_btn.setIcon(svg_icon(_IMPORT_SVG, TEXT_DIM, 12))
        imp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        imp_btn.setToolTip("Import layout")
        imp_btn.setStyleSheet(_BTN_STYLE)
        imp_btn.clicked.connect(self._import_layout)
        layout.addWidget(imp_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        exp_btn = QPushButton()
        exp_btn.setFixedSize(16, 16)
        exp_btn.setIcon(svg_icon(_EXPORT_SVG, TEXT_DIM, 12))
        exp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exp_btn.setToolTip("Export layout")
        exp_btn.setStyleSheet(_BTN_STYLE)
        exp_btn.clicked.connect(self._export_layout)
        layout.addWidget(exp_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch()

        # Cols control
        col_lbl = QLabel("W:")
        col_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        layout.addWidget(col_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        col_dec = QPushButton("-")
        col_dec.setFixedSize(14, 14)
        col_dec.setStyleSheet(_FOOTER_BTN_STYLE)
        col_dec.clicked.connect(lambda: self._change_cols(-1))
        layout.addWidget(col_dec, 0, Qt.AlignmentFlag.AlignVCenter)

        self._col_count_lbl = QLabel(str(self._config.custom_grid_overlay_cols))
        self._col_count_lbl.setFixedWidth(18)
        self._col_count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._col_count_lbl.setStyleSheet(_TILE_COUNT_STYLE)
        layout.addWidget(self._col_count_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        col_inc = QPushButton("+")
        col_inc.setFixedSize(14, 14)
        col_inc.setStyleSheet(_FOOTER_BTN_STYLE)
        col_inc.clicked.connect(lambda: self._change_cols(1))
        layout.addWidget(col_inc, 0, Qt.AlignmentFlag.AlignVCenter)

        # Rows control
        row_lbl = QLabel("H:")
        row_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; margin-left: 6px;")
        layout.addWidget(row_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        row_dec = QPushButton("-")
        row_dec.setFixedSize(14, 14)
        row_dec.setStyleSheet(_FOOTER_BTN_STYLE)
        row_dec.clicked.connect(lambda: self._change_rows(-1))
        layout.addWidget(row_dec, 0, Qt.AlignmentFlag.AlignVCenter)

        self._row_count_lbl = QLabel(str(self._config.custom_grid_overlay_rows))
        self._row_count_lbl.setFixedWidth(18)
        self._row_count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._row_count_lbl.setStyleSheet(_TILE_COUNT_STYLE)
        layout.addWidget(self._row_count_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        row_inc = QPushButton("+")
        row_inc.setFixedSize(14, 14)
        row_inc.setStyleSheet(_FOOTER_BTN_STYLE)
        row_inc.clicked.connect(lambda: self._change_rows(1))
        layout.addWidget(row_inc, 0, Qt.AlignmentFlag.AlignVCenter)

        return bar

    # --- Tile size ---

    def _set_tile_size(self, idx: int) -> None:
        if idx == getattr(self._config, "custom_grid_overlay_tile_size", 0):
            return
        self._config.custom_grid_overlay_tile_size = idx
        for i, btn in enumerate(self._tile_buttons):
            btn.setStyleSheet(self._tile_btn_style(i == idx))
        self._sync_grid_to_config()
        save_config(self._config, self._config_path)

    # --- Grid dimensions ---

    def _change_cols(self, delta: int) -> None:
        new_val = max(_MIN_TILES, min(_MAX_TILES,
                      self._config.custom_grid_overlay_cols + delta))
        self._config.custom_grid_overlay_cols = new_val
        self._col_count_lbl.setText(str(new_val))
        self._sync_grid_to_config()
        save_config(self._config, self._config_path)

    def _change_rows(self, delta: int) -> None:
        new_val = max(_MIN_TILES, min(_MAX_TILES,
                      self._config.custom_grid_overlay_rows + delta))
        self._config.custom_grid_overlay_rows = new_val
        self._row_count_lbl.setText(str(new_val))
        self._sync_grid_to_config()
        save_config(self._config, self._config_path)

    def _sync_grid_to_config(self) -> None:
        """Apply grid dimensions + tile size from config and resize the overlay."""
        cols = getattr(self._config, "custom_grid_overlay_cols", 6)
        rows = getattr(self._config, "custom_grid_overlay_rows", 4)
        tile_idx = getattr(self._config, "custom_grid_overlay_tile_size", 0)
        tile_px = _TILE_SIZES[max(0, min(2, tile_idx))]
        self._grid_canvas.set_grid(cols, rows, tile_px)
        self._apply_size()

    def _apply_size(self) -> None:
        if self._minified:
            return  # Minified — size locked to _TITLE_H; don't override
        canvas_w = self._grid_canvas.width()
        footer_h = _FOOTER_H if self._edit_mode else 0
        self.setFixedSize(canvas_w, _TITLE_H + self._grid_canvas.height() + footer_h)

    # --- Edit mode ---

    def _set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled
        self._grid_canvas.set_edit_mode(enabled)
        self._footer.setVisible(enabled)
        self._apply_size()

        # Update title bar border radius for active edit state
        if self._minified:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG}; border-radius: 8px;"
            )
        else:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG};"
                " border-top-left-radius: 8px; border-top-right-radius: 8px;"
            )

    # --- Collapse / expand (click title bar) ---

    def _toggle_minify(self) -> None:
        expanding = self._minified
        self._minified = not expanding
        self._body.setVisible(expanding)
        if expanding:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG};"
                " border-top-left-radius: 8px; border-top-right-radius: 8px;"
            )
            self._apply_size()
        else:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG}; border-radius: 8px;"
            )
            self.setFixedSize(self.width(), _TITLE_H)

    # --- Widget lifecycle ---

    def _make_context(self) -> WidgetContext:
        return WidgetContext(
            event_bus=self._event_bus,
            data_client=self._data_client,
            exchange_store=self._exchange_store,
            hunt_tracker=self._hunt_tracker,
            config=self._config,
        )

    def _instantiate(
        self,
        cls: type[GridWidget],
        widget_config: dict,
        col: int,
        row: int,
        colspan: int,
        rowspan: int,
    ) -> _SlotEntry | None:
        context = self._make_context()
        gw = cls(widget_config)
        try:
            gw.setup(context)
        except Exception as e:
            log.error("Widget %s setup() failed: %s", cls.WIDGET_ID, e)

        q_widget = None
        try:
            q_widget = gw.create_widget(self._grid_canvas)
        except Exception as e:
            log.error("Widget %s create_widget() failed: %s", cls.WIDGET_ID, e)

        container = CellContainer(gw, q_widget, self._grid_canvas)
        container.set_edit_mode(self._edit_mode)

        slot = _SlotEntry(gw, container, col, row, colspan, rowspan)
        self._grid_canvas.add_slot(slot)
        return slot

    def _add_widget_at(self, col: int | None, row: int | None) -> None:
        dlg = WidgetPickerDialog(self._registry, parent=self)
        if not (dlg.exec() and dlg.selected_class()):
            return
        cls = dlg.selected_class()
        cs = max(1, min(cls.DEFAULT_COLSPAN,
                        self._config.custom_grid_overlay_cols))
        rs = max(1, min(cls.DEFAULT_ROWSPAN,
                        self._config.custom_grid_overlay_rows))
        if col is None or row is None:
            pos = self._grid_canvas.find_free_position(cs, rs)
            if pos is None:
                QMessageBox.information(self, "No Space", "No free space for this widget.")
                return
            col, row = pos
        # Clamp to grid
        col = max(0, min(col, self._config.custom_grid_overlay_cols - cs))
        row = max(0, min(row, self._config.custom_grid_overlay_rows - rs))
        self._instantiate(cls, {}, col, row, cs, rs)
        self._save_widgets()

    def _remove_slot(self, slot: _SlotEntry) -> None:
        try:
            slot.grid_widget.teardown()
        except Exception as e:
            log.error("Widget teardown() failed: %s", e)
        self._grid_canvas.remove_slot(slot)
        self._save_widgets()

    def _replace_slot(self, slot: _SlotEntry) -> None:
        dlg = WidgetPickerDialog(self._registry, parent=self)
        if not (dlg.exec() and dlg.selected_class()):
            return
        col, row, cs, rs = slot.col, slot.row, slot.colspan, slot.rowspan
        self._remove_slot(slot)
        cls = dlg.selected_class()
        self._instantiate(cls, {}, col, row, cls.DEFAULT_COLSPAN, cls.DEFAULT_ROWSPAN)
        self._save_widgets()

    # --- Persistence ---

    def _restore_widgets(self) -> None:
        entries = getattr(self._config, "custom_grid_overlay_widgets", []) or []
        for entry in entries:
            widget_id = entry.get("id")
            if not widget_id:
                continue
            cls = self._registry.get_by_id(widget_id)
            if cls is None:
                log.warning("Unknown widget ID '%s' — skipping", widget_id)
                continue
            self._instantiate(
                cls,
                entry.get("config", {}),
                entry.get("col", 0),
                entry.get("row", 0),
                entry.get("colspan", cls.DEFAULT_COLSPAN),
                entry.get("rowspan", cls.DEFAULT_ROWSPAN),
            )

    def _save_widgets(self) -> None:
        entries = []
        for slot in self._grid_canvas._slots:
            try:
                widget_cfg = slot.grid_widget.get_config()
            except Exception:
                widget_cfg = {}
            entries.append({
                "id":      slot.grid_widget.WIDGET_ID,
                "col":     slot.col,
                "row":     slot.row,
                "colspan": slot.colspan,
                "rowspan": slot.rowspan,
                "config":  widget_cfg,
            })
        self._config.custom_grid_overlay_widgets = entries
        save_config(self._config, self._config_path)

    # --- Import / Export ---

    def _export_layout(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Layout", "custom_grid_layout.json", "JSON Files (*.json)"
        )
        if not path:
            return
        layout = {
            "version": _LAYOUT_VERSION,
            "cols": self._config.custom_grid_overlay_cols,
            "rows": self._config.custom_grid_overlay_rows,
            "tile_size": self._config.custom_grid_overlay_tile_size,
            "widgets": [
                {
                    "id":      s.grid_widget.WIDGET_ID,
                    "col":     s.col,
                    "row":     s.row,
                    "colspan": s.colspan,
                    "rowspan": s.rowspan,
                    "config":  s.grid_widget.get_config(),
                }
                for s in self._grid_canvas._slots
            ],
        }
        try:
            Path(path).write_text(json.dumps(layout, indent=2), encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _import_layout(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Layout", "", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))
            return
        if not isinstance(data, dict) or "widgets" not in data:
            QMessageBox.warning(self, "Import Failed", "Invalid layout file.")
            return
        if self._grid_canvas._slots:
            reply = QMessageBox.question(
                self, "Replace Layout",
                "This will replace your current layout. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        for slot in list(self._grid_canvas._slots):
            try:
                slot.grid_widget.teardown()
            except Exception:
                pass
            self._grid_canvas.remove_slot(slot)

        if "cols" in data:
            self._config.custom_grid_overlay_cols = max(_MIN_TILES, min(_MAX_TILES, int(data["cols"])))
        if "rows" in data:
            self._config.custom_grid_overlay_rows = max(_MIN_TILES, min(_MAX_TILES, int(data["rows"])))
        if "tile_size" in data:
            self._config.custom_grid_overlay_tile_size = max(0, min(2, int(data["tile_size"])))

        self._sync_grid_to_config()
        self._col_count_lbl.setText(str(self._config.custom_grid_overlay_cols))
        self._row_count_lbl.setText(str(self._config.custom_grid_overlay_rows))

        for entry in data.get("widgets", []):
            cls = self._registry.get_by_id(entry.get("id"))
            if cls is None:
                continue
            self._instantiate(
                cls,
                entry.get("config", {}),
                entry.get("col", 0),
                entry.get("row", 0),
                entry.get("colspan", cls.DEFAULT_COLSPAN),
                entry.get("rowspan", cls.DEFAULT_ROWSPAN),
            )
        self._save_widgets()

    # --- Mouse events: drag overlay / click-to-collapse ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_origin = event.globalPosition().toPoint()
            # Allow drag only from title bar
            if event.position().y() <= _TITLE_H:
                self._drag_pos = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
            else:
                self._drag_pos = None

    def mouseReleaseEvent(self, event):
        click_origin = self._click_origin
        self._click_origin = None
        super().mouseReleaseEvent(event)

        if click_origin and event.button() == Qt.MouseButton.LeftButton:
            delta = (
                event.globalPosition().toPoint() - click_origin
            ).manhattanLength()
            if delta < 5:
                click_local = self.mapFromGlobal(click_origin)
                title_bottom = self._title_bar.mapTo(
                    self, QPoint(0, self._title_bar.height())
                ).y()
                if click_local.y() <= title_bottom:
                    self._toggle_minify()

    # --- Cleanup ---

    def closeEvent(self, event):
        self._save_widgets()
        for slot in list(self._grid_canvas._slots):
            try:
                slot.grid_widget.teardown()
            except Exception as e:
                log.error("Widget teardown on close failed: %s", e)
        super().closeEvent(event)
