"""CustomGridOverlay — user-configurable tile-based modular grid overlay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QCheckBox,
)
from PyQt6.QtCore import Qt, QPoint, QSize, QFileSystemWatcher, QTimer
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
_PANEL_GAP = 4        # px gap between overlay right edge and floating edit panel

_TILE_SIZES = [20, 30, 40]  # S, M, L pixels per tile
_TILE_LABELS = ["S", "M", "L"]
_TILE_TOOLTIPS = ["Small (20 px/tile)", "Medium (30 px/tile)", "Large (40 px/tile)"]
_MIN_COLS = 4
_MIN_ROWS = 1
_MAX_TILES = 50
_RESIZE_HIT_PX = 8   # pixels from an edge that count as a resize handle

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
    f"QPushButton {{ background: transparent; color: {TEXT_COLOR}; border: 1px solid #555;"
    "  border-radius: 3px; padding: 0px 4px; font-size: 13px; font-weight: bold; }}"
    f"QPushButton:hover {{ background: {TAB_HOVER_BG}; border-color: #888; }}"
)
_TILE_COUNT_STYLE = (
    f"color: {TEXT_COLOR}; font-size: 11px; font-weight: bold; padding: 0 4px;"
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
        # Drag state
        self._drag_slot: _SlotEntry | None = None
        self._drag_offset = QPoint()
        # Resize state
        self._resize_slot: _SlotEntry | None = None
        self._resize_edge: str = ""
        self._resize_orig: tuple[int, int, int, int] = (0, 0, 0, 0)  # col,row,cs,rs
        self._add_widget_fn: Callable | None = None
        self.setMouseTracking(True)
        self._apply_size()

    def set_grid(self, cols: int, rows: int, tile_px: int) -> None:
        self._cols = max(1, min(_MAX_TILES, cols))
        self._rows = max(1, min(_MAX_TILES, rows))
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
        if not enabled:
            self.unsetCursor()
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
        w, h = slot.colspan * t, slot.rowspan * t
        slot.container.setGeometry(slot.col * t, slot.row * t, w, h)
        try:
            slot.grid_widget.on_resize(w, h)
        except Exception:
            pass

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
        return self._overlaps_rect(exclude, col, row, exclude.colspan, exclude.rowspan)

    def _overlaps_rect(
        self, exclude: _SlotEntry, col: int, row: int, cs: int, rs: int
    ) -> bool:
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

    # --- Resize handle detection ---

    def _resize_edge_at(self, slot: _SlotEntry, pos: QPoint) -> str:
        """Return which resize edge/corner the cursor is over, or '' for none."""
        t  = self._tile_px
        x  = pos.x() - slot.col * t
        y  = pos.y() - slot.row * t
        w  = slot.colspan  * t
        h  = slot.rowspan  * t
        hp = _RESIZE_HIT_PX

        right  = abs(x - w) <= hp
        bottom = abs(y - h) <= hp
        top    = 0 <= y <= hp
        left   = 0 <= x <= hp

        if right and bottom: return "se"
        if left  and bottom: return "sw"
        if right and top:    return "ne"
        if left  and top:    return "nw"
        if right:  return "e"
        if bottom: return "s"
        if left:   return "w"
        if top:    return "n"
        return ""

    @staticmethod
    def _cursor_for_edge(edge: str) -> Qt.CursorShape:
        return {
            "e":  Qt.CursorShape.SizeHorCursor,
            "w":  Qt.CursorShape.SizeHorCursor,
            "n":  Qt.CursorShape.SizeVerCursor,
            "s":  Qt.CursorShape.SizeVerCursor,
            "ne": Qt.CursorShape.SizeBDiagCursor,
            "sw": Qt.CursorShape.SizeBDiagCursor,
            "nw": Qt.CursorShape.SizeFDiagCursor,
            "se": Qt.CursorShape.SizeFDiagCursor,
        }.get(edge, Qt.CursorShape.SizeAllCursor)

    # --- Mouse events (edit mode only) ---

    def mousePressEvent(self, event):
        if not self._edit_mode:
            return
        pos = event.position().toPoint()

        if event.button() == Qt.MouseButton.LeftButton:
            slot = self._slot_at(pos)
            if slot:
                edge = self._resize_edge_at(slot, pos)
                if edge:
                    self._resize_slot = slot
                    self._resize_edge = edge
                    self._resize_orig = (slot.col, slot.row, slot.colspan, slot.rowspan)
                    slot.container.raise_()
                else:
                    self._drag_slot   = slot
                    t = self._tile_px
                    self._drag_offset = pos - QPoint(slot.col * t, slot.row * t)
                    slot.container.raise_()

        elif event.button() == Qt.MouseButton.RightButton:
            slot = self._slot_at(pos)
            self._show_context_menu(slot, event.globalPosition().toPoint(), pos)

    def mouseMoveEvent(self, event):
        pos     = event.position().toPoint()
        buttons = event.buttons()

        if self._drag_slot and buttons & Qt.MouseButton.LeftButton:
            new_pos = pos - self._drag_offset
            self._drag_slot.container.move(
                max(0, min(new_pos.x(), self.width()  - self._drag_slot.colspan  * self._tile_px)),
                max(0, min(new_pos.y(), self.height() - self._drag_slot.rowspan  * self._tile_px)),
            )
            return

        if self._resize_slot and buttons & Qt.MouseButton.LeftButton:
            self._update_resize_visual(pos)
            return

        # Cursor feedback when idle
        if self._edit_mode:
            slot = self._slot_at(pos)
            if slot:
                edge = self._resize_edge_at(slot, pos)
                self.setCursor(self._cursor_for_edge(edge) if edge else Qt.CursorShape.SizeAllCursor)
            else:
                self.unsetCursor()

    def _update_resize_visual(self, pos: QPoint) -> None:
        """Update container geometry visually during a resize drag (no snap yet)."""
        slot  = self._resize_slot
        edge  = self._resize_edge
        t     = self._tile_px
        gw    = slot.grid_widget
        orig_col, orig_row, orig_cs, orig_rs = self._resize_orig

        # Compute new col/row/cs/rs from mouse position
        new_col, new_row, new_cs, new_rs = orig_col, orig_row, orig_cs, orig_rs

        if "e" in edge:
            new_cs = max(gw.MIN_COLSPAN, round((pos.x() - orig_col * t) / t))
            if gw.MAX_COLSPAN > 0:
                new_cs = min(new_cs, gw.MAX_COLSPAN)
            new_cs = min(new_cs, self._cols - orig_col)

        if "w" in edge:
            raw = max(0, min(orig_col + orig_cs - gw.MIN_COLSPAN, round(pos.x() / t)))
            new_col = raw
            new_cs  = orig_col + orig_cs - new_col
            if gw.MAX_COLSPAN > 0:
                new_cs = min(new_cs, gw.MAX_COLSPAN)

        if "s" in edge:
            new_rs = max(gw.MIN_ROWSPAN, round((pos.y() - orig_row * t) / t))
            if gw.MAX_ROWSPAN > 0:
                new_rs = min(new_rs, gw.MAX_ROWSPAN)
            new_rs = min(new_rs, self._rows - orig_row)

        if "n" in edge:
            raw = max(0, min(orig_row + orig_rs - gw.MIN_ROWSPAN, round(pos.y() / t)))
            new_row = raw
            new_rs  = orig_row + orig_rs - new_row
            if gw.MAX_ROWSPAN > 0:
                new_rs = min(new_rs, gw.MAX_ROWSPAN)

        slot.container.setGeometry(new_col * t, new_row * t, new_cs * t, new_rs * t)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # --- Finish drag ---
        if self._drag_slot:
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
            return

        # --- Finish resize ---
        if self._resize_slot:
            slot = self._resize_slot
            self._resize_slot = None
            orig_col, orig_row, orig_cs, orig_rs = self._resize_orig

            t = self._tile_px
            # Read final geometry from the container (set by _update_resize_visual)
            new_col = round(slot.container.x() / t)
            new_row = round(slot.container.y() / t)
            new_cs  = round(slot.container.width()  / t)
            new_rs  = round(slot.container.height() / t)

            # Clamp to grid
            new_col = max(0, min(new_col, self._cols - 1))
            new_row = max(0, min(new_row, self._rows - 1))
            new_cs  = max(1, min(new_cs,  self._cols - new_col))
            new_rs  = max(1, min(new_rs,  self._rows - new_row))

            if not self._overlaps_rect(slot, new_col, new_row, new_cs, new_rs):
                slot.col     = new_col
                slot.row     = new_row
                slot.colspan = new_cs
                slot.rowspan = new_rs
            # Snap back to committed position (either new or original on overlap)
            self._place_slot(slot)
            self._save_fn()

    def mouseDoubleClickEvent(self, event):
        if not self._edit_mode or event.button() != Qt.MouseButton.LeftButton:
            return
        slot = self._slot_at(event.position().toPoint())
        if slot:
            self._request_configure(slot)

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
            menu.addAction("Configure…", lambda: self._request_configure(slot))
            menu.addSeparator()
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

    def _request_configure(self, slot: _SlotEntry) -> None:
        if self._configure_fn:
            self._configure_fn(slot)

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
    _remove_fn:    Callable | None = None
    _replace_fn:   Callable | None = None
    _configure_fn: Callable | None = None


_PANEL_STYLE = (
    f"background-color: {TITLE_BG};"
    " border-radius: 6px;"
    " border: 1px solid #444460;"
)
_PANEL_SEP_STYLE = "background: #333355;"


class _EditSidePanel(QWidget):
    """Floating side panel shown to the right of the overlay when edit mode is active.

    Creates buttons/labels and assigns them back to the overlay so existing
    ``_set_tile_size``, ``_change_cols``, ``_change_rows`` methods keep working.
    """

    def __init__(self, overlay: "CustomGridOverlay"):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint,
        )
        self._overlay = overlay
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(_PANEL_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 8, 6, 8)
        root.setSpacing(4)

        # ── Tile size ────────────────────────────────────────────────────────
        tile_hdr = QLabel("Tile")
        tile_hdr.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 9px; background: transparent;"
        )
        tile_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(tile_hdr)

        tile_row = QHBoxLayout()
        tile_row.setSpacing(2)
        tile_idx = overlay._grid_cfg.get("tile_size", 0)
        overlay._tile_buttons = []
        for i, label in enumerate(_TILE_LABELS):
            btn = QPushButton(label)
            btn.setFixedSize(22, 22)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(_TILE_TOOLTIPS[i])
            btn.setStyleSheet(overlay._tile_btn_style(i == tile_idx))
            btn.clicked.connect(lambda _, idx=i: overlay._set_tile_size(idx))
            tile_row.addWidget(btn)
            overlay._tile_buttons.append(btn)
        root.addLayout(tile_row)

        root.addWidget(self._sep())

        # ── Grid dimensions ──────────────────────────────────────────────────
        for axis_lbl, count_attr, inc_fn, dec_fn, init_val in [
            ("W", "_col_count_lbl",
             lambda: overlay._change_cols(1), lambda: overlay._change_cols(-1),
             overlay._grid_cfg.get("cols", 12)),
            ("H", "_row_count_lbl",
             lambda: overlay._change_rows(1), lambda: overlay._change_rows(-1),
             overlay._grid_cfg.get("rows", 12)),
        ]:
            hdr = QLabel(axis_lbl)
            hdr.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 9px; background: transparent;"
            )
            hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root.addWidget(hdr)

            dim_row = QHBoxLayout()
            dim_row.setSpacing(2)

            dec_btn = QPushButton("−")
            dec_btn.setFixedSize(22, 22)
            dec_btn.setStyleSheet(_FOOTER_BTN_STYLE)
            dec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            dec_btn.clicked.connect(dec_fn)
            dim_row.addWidget(dec_btn)

            count_lbl = QLabel(str(init_val))
            count_lbl.setFixedWidth(26)
            count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            count_lbl.setStyleSheet(_TILE_COUNT_STYLE)
            dim_row.addWidget(count_lbl)
            setattr(overlay, count_attr, count_lbl)

            inc_btn = QPushButton("+")
            inc_btn.setFixedSize(22, 22)
            inc_btn.setStyleSheet(_FOOTER_BTN_STYLE)
            inc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            inc_btn.clicked.connect(inc_fn)
            dim_row.addWidget(inc_btn)

            root.addLayout(dim_row)

        root.addWidget(self._sep())

        # ── Action buttons ───────────────────────────────────────────────────
        for icon_svg, label, fn in [
            (_PLUS_SVG,   "Add",    lambda: overlay._add_widget_at(None, None)),
            (_IMPORT_SVG, "Import", overlay._import_layout),
            (_EXPORT_SVG, "Export", overlay._export_layout),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setIcon(svg_icon(icon_svg, TEXT_DIM, 12))
            btn.setStyleSheet(_FOOTER_BTN_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(fn)
            root.addWidget(btn)

        root.addWidget(self._sep())

        # ── Developer: hot-reload toggle ─────────────────────────────────────
        self._hotswap_check = QCheckBox("Hot-reload")
        self._hotswap_check.setToolTip(
            "Watch widget source files and reload on save.\n"
            "Only enable while developing widgets."
        )
        self._hotswap_check.setStyleSheet(
            f"QCheckBox {{ color: {TEXT_DIM}; font-size: 9px; background: transparent; }}"
            " QCheckBox::indicator { width: 12px; height: 12px; }"
        )
        self._hotswap_check.setChecked(overlay._hotswap_enabled)
        self._hotswap_check.toggled.connect(overlay._set_hotswap)
        root.addWidget(self._hotswap_check)

        self.adjustSize()

    @staticmethod
    def _sep() -> QWidget:
        w = QWidget()
        w.setFixedHeight(1)
        w.setStyleSheet(_PANEL_SEP_STYLE)
        return w

    def reposition(self) -> None:
        """Place the panel to the right of the overlay."""
        ov = self._overlay
        self.move(ov.x() + ov.width() + _PANEL_GAP, ov.y())


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
        grid_id: str,
        config,
        config_path: str,
        event_bus,
        data_client=None,
        exchange_store=None,
        hunt_tracker=None,
        manager: OverlayManager | None = None,
    ):
        # Must be set before super().__init__ so _build_title_bar/_build_footer can access _grid_cfg
        self._grid_id = grid_id
        super().__init__(
            config=config,
            config_path=config_path,
            position_key=f"__grid_{grid_id}__",  # dummy key — position handled via _grid_cfg
            manager=manager,
        )
        # Restore actual per-grid position (overrides OverlayWidget default (50,50))
        _gpos = self._grid_cfg.get("position", [200, 200])
        self.move(int(_gpos[0]), int(_gpos[1]))
        self._event_bus = event_bus
        self._data_client = data_client
        self._exchange_store = exchange_store
        self._hunt_tracker = hunt_tracker
        self._edit_mode = False
        self._minified = False
        self._click_origin: QPoint | None = None
        self._edit_panel: _EditSidePanel | None = None
        # Populated by _EditSidePanel when first created
        self._tile_buttons: list[QPushButton] = []
        self._col_count_lbl: QLabel | None = None
        self._row_count_lbl: QLabel | None = None

        # Widget registry
        user_dir = Path(config.database_path).parent / "custom_widgets"
        self._registry = WidgetRegistry(user_dir)
        self._registry.discover()

        # Hotswap (off by default — toggled in edit panel)
        self._hotswap_enabled = False
        self._file_watcher = QFileSystemWatcher(self)
        self._file_watcher.fileChanged.connect(self._on_widget_file_changed)
        self._hotswap_timer = QTimer(self)
        self._hotswap_timer.setSingleShot(True)
        self._hotswap_timer.setInterval(300)
        self._hotswap_timer.timeout.connect(self._process_hotswap)
        self._pending_hotswap_files: set[str] = set()

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
        self._grid_canvas._remove_fn    = self._remove_slot
        self._grid_canvas._replace_fn   = self._replace_slot
        self._grid_canvas._configure_fn = self._configure_slot
        self._grid_canvas._add_widget_fn = self._add_widget_at
        body_layout.addWidget(self._grid_canvas)

        main_layout.addWidget(self._body)

        # Apply initial grid from config
        self._sync_grid_to_config()
        self._restore_widgets()

    # --- Per-grid config accessor ---

    @property
    def _grid_cfg(self) -> dict:
        """Return (and lazily create) this grid's config dict in config.custom_grids."""
        for g in self._config.custom_grids:
            if g.get("id") == self._grid_id:
                return g
        entry = {
            "id": self._grid_id, "name": "Custom Grid",
            "position": [200, 200], "cols": 12, "rows": 12,
            "tile_size": 0, "widgets": [],
        }
        self._config.custom_grids.append(entry)
        return entry

    def _save_position(self) -> None:
        """Override: persist position into the per-grid config entry."""
        self._grid_cfg["position"] = [self.x(), self.y()]
        save_config(self._config, self._config_path)

    def rename(self, name: str) -> None:
        """Update the grid name in config and title bar."""
        self._grid_cfg["name"] = name
        self._name_label.setText(name)
        save_config(self._config, self._config_path)

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

        # Title (shows grid name, updated by rename())
        self._name_label = QLabel(self._grid_cfg.get("name", "Custom Grid"))
        self._name_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            " background: transparent;"
        )
        self._name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._name_label, 1, Qt.AlignmentFlag.AlignVCenter)

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

    # --- Tile size ---

    def _set_tile_size(self, idx: int) -> None:
        if idx == self._grid_cfg.get("tile_size", 0):
            return
        self._grid_cfg["tile_size"] = idx
        for i, btn in enumerate(self._tile_buttons):
            btn.setStyleSheet(self._tile_btn_style(i == idx))
        self._sync_grid_to_config()
        save_config(self._config, self._config_path)

    # --- Grid dimensions ---

    def _change_cols(self, delta: int) -> None:
        new_val = max(_MIN_COLS, min(_MAX_TILES,
                      self._grid_cfg.get("cols", 12) + delta))
        self._grid_cfg["cols"] = new_val
        if self._col_count_lbl is not None:
            self._col_count_lbl.setText(str(new_val))
        self._sync_grid_to_config()
        save_config(self._config, self._config_path)

    def _change_rows(self, delta: int) -> None:
        new_val = max(_MIN_ROWS, min(_MAX_TILES,
                      self._grid_cfg.get("rows", 12) + delta))
        self._grid_cfg["rows"] = new_val
        if self._row_count_lbl is not None:
            self._row_count_lbl.setText(str(new_val))
        self._sync_grid_to_config()
        save_config(self._config, self._config_path)

    def _sync_grid_to_config(self) -> None:
        """Apply grid dimensions + tile size from config and resize the overlay."""
        cols = self._grid_cfg.get("cols", 12)
        rows = self._grid_cfg.get("rows", 12)
        tile_idx = self._grid_cfg.get("tile_size", 0)
        tile_px = _TILE_SIZES[max(0, min(2, tile_idx))]
        self._grid_canvas.set_grid(cols, rows, tile_px)
        self._apply_size()

    def _apply_size(self) -> None:
        if self._minified:
            return  # Minified — size locked to _TITLE_H; don't override
        canvas_w = self._grid_canvas.width()
        self.setFixedSize(canvas_w, _TITLE_H + self._grid_canvas.height())
        # Reposition the side panel — setFixedSize changes width but doesn't
        # trigger moveEvent, so the panel would lag behind.
        if self._edit_panel is not None and self._edit_panel.isVisible():
            self._edit_panel.reposition()

    # --- Edit mode ---

    def _set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled
        self._grid_canvas.set_edit_mode(enabled)

        if enabled:
            if self._edit_panel is None:
                self._edit_panel = _EditSidePanel(self)
            self._edit_panel.reposition()
            self._edit_panel.show()
        else:
            if self._edit_panel is not None:
                self._edit_panel.hide()

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
            # Re-show edit panel if edit mode is active
            if self._edit_mode and self._edit_panel is not None:
                self._edit_panel.reposition()
                self._edit_panel.show()
        else:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG}; border-radius: 8px;"
            )
            self.setFixedSize(self.width(), _TITLE_H)
            if self._edit_panel is not None:
                self._edit_panel.hide()

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
        cols = self._grid_cfg.get("cols", 12)
        rows = self._grid_cfg.get("rows", 12)
        cs = max(1, min(cls.DEFAULT_COLSPAN, cols))
        rs = max(1, min(cls.DEFAULT_ROWSPAN, rows))
        if col is None or row is None:
            pos = self._grid_canvas.find_free_position(cs, rs)
            if pos is None:
                QMessageBox.information(self, "No Space", "No free space for this widget.")
                return
            col, row = pos
        # Clamp to grid
        col = max(0, min(col, cols - cs))
        row = max(0, min(row, rows - rs))
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
        col, row = slot.col, slot.row
        self._remove_slot(slot)
        cls = dlg.selected_class()
        self._instantiate(cls, {}, col, row, cls.DEFAULT_COLSPAN, cls.DEFAULT_ROWSPAN)
        self._save_widgets()

    def _configure_slot(self, slot: _SlotEntry) -> None:
        cols = self._grid_cfg.get("cols", 12)
        rows = self._grid_cfg.get("rows", 12)
        new_cfg = slot.grid_widget.configure(
            self,
            current_colspan=slot.colspan,
            current_rowspan=slot.rowspan,
            max_cols=max(1, cols - slot.col),
            max_rows=max(1, rows - slot.row),
        )
        if new_cfg is None:
            return

        # Handle optional layout changes embedded in the config
        slot_changes = new_cfg.pop("__slot__", {})
        new_cs = slot_changes.get("colspan")
        new_rs = slot_changes.get("rowspan")
        if new_cs is not None or new_rs is not None:
            old_cs, old_rs = slot.colspan, slot.rowspan
            target_cs = max(1, min(cols - slot.col, new_cs or old_cs))
            target_rs = max(1, min(rows - slot.row, new_rs or old_rs))
            if not self._grid_canvas._overlaps_rect(slot, slot.col, slot.row, target_cs, target_rs):
                slot.colspan = target_cs
                slot.rowspan = target_rs
            self._grid_canvas._place_slot(slot)

        slot.grid_widget.on_config_changed(new_cfg)
        self._save_widgets()

    # --- Widget hot-reload ---

    def _set_hotswap(self, enabled: bool) -> None:
        """Enable or disable file watching for widget hot-reload."""
        self._hotswap_enabled = enabled
        if enabled:
            paths = self._registry.get_watched_paths()
            if paths:
                self._file_watcher.addPaths(paths)
            log.info("Hotswap enabled — watching %d file(s)", len(paths))
        else:
            watched = self._file_watcher.files()
            if watched:
                self._file_watcher.removePaths(watched)
            self._pending_hotswap_files.clear()
            log.info("Hotswap disabled")

    def _on_widget_file_changed(self, path: str) -> None:
        """Debounced handler for widget source file changes."""
        if not self._hotswap_enabled:
            return
        self._pending_hotswap_files.add(path)
        # Some OS/editors cause the watcher to drop the path after modification
        if path not in self._file_watcher.files():
            self._file_watcher.addPath(path)
        if not self._hotswap_timer.isActive():
            self._hotswap_timer.start()

    def _process_hotswap(self) -> None:
        """Reload changed files and re-instantiate affected widgets."""
        files = list(self._pending_hotswap_files)
        self._pending_hotswap_files.clear()

        for file_path in files:
            fname = Path(file_path).name
            updated_ids, error = self._registry.reload_file(file_path)
            if error:
                log.warning("Hotswap %s failed: %s", fname, error)
                continue
            if not updated_ids:
                log.info("Hotswap %s: no widget classes found", fname)
                continue
            log.info("Hotswap %s: reloaded %s", fname, ", ".join(updated_ids))
            for widget_id in updated_ids:
                self._hotswap_widget(widget_id)

    def _hotswap_widget(self, widget_id: str) -> None:
        """Tear down and re-instantiate all slots using *widget_id*."""
        new_cls = self._registry.get_by_id(widget_id)
        if new_cls is None:
            return
        affected = [
            s for s in list(self._grid_canvas._slots)
            if s.grid_widget.WIDGET_ID == widget_id
        ]
        for slot in affected:
            # Preserve config and position
            try:
                cfg = slot.grid_widget.get_config()
            except Exception:
                cfg = {}
            col, row, cs, rs = slot.col, slot.row, slot.colspan, slot.rowspan

            # Teardown old instance
            try:
                slot.grid_widget.teardown()
            except Exception as e:
                log.error("Hotswap teardown failed for %s: %s", widget_id, e)
            self._grid_canvas.remove_slot(slot)

            # Instantiate new instance
            new_slot = self._instantiate(new_cls, cfg, col, row, cs, rs)
            if new_slot is None:
                log.error("Hotswap re-instantiate failed for %s", widget_id)
        self._save_widgets()

    # --- Persistence ---

    def _restore_widgets(self) -> None:
        entries = self._grid_cfg.get("widgets", []) or []
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
        self._grid_cfg["widgets"] = entries
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
            "cols": self._grid_cfg.get("cols", 12),
            "rows": self._grid_cfg.get("rows", 12),
            "tile_size": self._grid_cfg.get("tile_size", 0),
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
            self._grid_cfg["cols"] = max(_MIN_TILES, min(_MAX_TILES, int(data["cols"])))
        if "rows" in data:
            self._grid_cfg["rows"] = max(_MIN_TILES, min(_MAX_TILES, int(data["rows"])))
        if "tile_size" in data:
            self._grid_cfg["tile_size"] = max(0, min(2, int(data["tile_size"])))

        self._sync_grid_to_config()
        if self._col_count_lbl is not None:
            self._col_count_lbl.setText(str(self._grid_cfg.get("cols", 12)))
        if self._row_count_lbl is not None:
            self._row_count_lbl.setText(str(self._grid_cfg.get("rows", 12)))

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

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if self._edit_panel is not None and self._edit_panel.isVisible():
            self._edit_panel.reposition()

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
        # Stop hotswap watcher
        self._set_hotswap(False)
        # Exit edit mode before closing
        if self._edit_mode:
            self._edit_btn.setChecked(False)
        if self._edit_panel is not None:
            self._edit_panel.close()
            self._edit_panel = None
        self._save_widgets()
        for slot in list(self._grid_canvas._slots):
            try:
                slot.grid_widget.teardown()
            except Exception as e:
                log.error("Widget teardown on close failed: %s", e)
        super().closeEvent(event)
