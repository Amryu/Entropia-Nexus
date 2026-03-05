"""Compact fuzzy-search combo widget for the calculator tab."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QLineEdit, QVBoxLayout, QLabel, QHBoxLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QEvent
from PyQt6.QtGui import QKeyEvent

from .detail_overlay import (
    BG_COLOR, TEXT_COLOR, TEXT_DIM, ACCENT, CONTENT_BG, BADGE_BG,
)

_MAX_RESULTS = 8


# ---------------------------------------------------------------------------
# Fuzzy scoring (ported from maps_page.py)
# ---------------------------------------------------------------------------

def _fuzzy_score(name: str, query: str) -> int:
    if not name or not query:
        return 0
    name_l = name.lower()
    query_l = query.lower()

    if name_l == query_l:
        return 1000
    if name_l.startswith(query_l):
        return 900

    words = name_l.split()
    for i, w in enumerate(words):
        if w.startswith(query_l):
            return 800 - i * 5

    idx = name_l.find(query_l)
    if idx != -1:
        return 700 - min(idx, 50)

    if len(query_l) < 4:
        return 0

    query_idx = 0
    score = 0
    consecutive_bonus = 0
    match_positions: list[int] = []

    for i, ch in enumerate(name_l):
        if query_idx < len(query_l) and ch == query_l[query_idx]:
            match_positions.append(i)
            query_idx += 1
            consecutive_bonus += 10
            score += consecutive_bonus
            if i == 0 or name_l[i - 1] in (" ", "-", "_"):
                score += 30
        else:
            consecutive_bonus = 0

    if query_idx == len(query_l):
        spread = (match_positions[-1] - match_positions[0]) if len(match_positions) > 1 else 0
        if spread > len(query_l) * 2:
            return 0
        compact_bonus = max(0, 50 - spread)
        return 300 + score + compact_bonus

    match_ratio = query_idx / len(query_l)
    if match_ratio >= 0.95 and len(query_l) >= 5:
        spread = (match_positions[-1] - match_positions[0]) if len(match_positions) > 1 else 0
        if spread <= len(query_l) * 2:
            return 100 + int(score * match_ratio)

    return 0


def _item_name(item: dict) -> str:
    return item.get("DisplayName") or item.get("Name") or ""


# ---------------------------------------------------------------------------
# Popup dropdown
# ---------------------------------------------------------------------------

_ROW_STYLE = (
    f"color: {TEXT_COLOR}; font-size: 13px; padding: 3px 6px;"
    f" background: transparent;"
)
_ROW_HOVER_STYLE = (
    f"color: {TEXT_COLOR}; font-size: 13px; padding: 3px 6px;"
    f" background-color: rgba(60, 60, 90, 180);"
    f" border-radius: 3px;"
)


class _ResultPopup(QWidget):
    """Top-level frameless dropdown showing fuzzy-search results."""

    result_clicked = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Inner container provides the opaque background
        self._container = QWidget()
        self._container.setStyleSheet(
            f"background-color: rgba(20, 20, 30, 240);"
            f" border: 1px solid #555555;"
            f" border-radius: 4px;"
        )
        outer.addWidget(self._container)

        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(0)

        self._rows: list[QLabel] = []
        self._items: list[dict] = []
        self._row_colors: list[str | None] = []
        self._highlight_idx = -1

    def set_results(self, items: list[dict], color_fn=None):
        """Update displayed results. color_fn(item) -> color string or None."""
        # Clear existing rows — hide + delete so they don't affect sizeHint
        for row in self._rows:
            row.hide()
            self._layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._items = items
        self._row_colors.clear()
        self._highlight_idx = -1

        for item in items:
            color = color_fn(item) if color_fn else None
            self._row_colors.append(color)
            text_color = color or TEXT_COLOR
            style = (
                f"color: {text_color}; font-size: 13px; padding: 3px 6px;"
                f" background: transparent;"
            )
            lbl = QLabel(_item_name(item))
            lbl.setStyleSheet(style)
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.mousePressEvent = lambda _e, it=item: self.result_clicked.emit(it)
            self._layout.addWidget(lbl)
            self._rows.append(lbl)

        # Force immediate layout + resize so the popup shrinks properly
        self._layout.activate()
        self._container.adjustSize()
        self.adjustSize()

    def highlight(self, idx: int):
        if self._highlight_idx >= 0 and self._highlight_idx < len(self._rows):
            color = self._row_colors[self._highlight_idx] if self._highlight_idx < len(self._row_colors) else None
            text_c = color or TEXT_COLOR
            self._rows[self._highlight_idx].setStyleSheet(
                f"color: {text_c}; font-size: 13px; padding: 3px 6px;"
                f" background: transparent;"
            )
        self._highlight_idx = max(-1, min(idx, len(self._rows) - 1))
        if self._highlight_idx >= 0:
            color = self._row_colors[self._highlight_idx] if self._highlight_idx < len(self._row_colors) else None
            text_c = color or TEXT_COLOR
            self._rows[self._highlight_idx].setStyleSheet(
                f"color: {text_c}; font-size: 13px; padding: 3px 6px;"
                f" background-color: rgba(60, 60, 90, 180);"
                f" border-radius: 3px;"
            )

    def highlighted_item(self) -> dict | None:
        if 0 <= self._highlight_idx < len(self._items):
            return self._items[self._highlight_idx]
        return None

    @property
    def highlight_index(self) -> int:
        return self._highlight_idx

    @property
    def result_count(self) -> int:
        return len(self._items)


# ---------------------------------------------------------------------------
# CalcSearchInput — the main widget
# ---------------------------------------------------------------------------

_INPUT_STYLE = (
    f"QLineEdit {{"
    f"  color: {TEXT_COLOR}; font-size: 13px;"
    f"  background-color: rgba(20, 20, 35, 200);"
    f"  border: 1px solid #444444; border-radius: 3px;"
    f"  padding: 2px 4px;"
    f"}}"
    f"QLineEdit:focus {{"
    f"  border-color: {ACCENT};"
    f"}}"
)

_CLEAR_BTN_STYLE = (
    f"QLabel {{"
    f"  color: {TEXT_DIM}; font-size: 12px; padding: 0px 2px;"
    f"  background: transparent;"
    f"}}"
    f"QLabel:hover {{"
    f"  color: {TEXT_COLOR};"
    f"}}"
)


class CalcSearchInput(QWidget):
    """Compact search input with fuzzy-match popup for entity selection.

    Signals:
        item_selected(dict): Emitted when an item is selected (or cleared → {}).
    """

    item_selected = pyqtSignal(dict)

    def __init__(
        self,
        items: list[dict] | None = None,
        placeholder: str = "Search...",
        parent: QWidget | None = None,
        color_fn=None,
    ):
        super().__init__(parent)
        self._all_items: list[dict] = items or []
        self._selected: dict | None = None
        self._color_fn = color_fn  # Optional: item -> color string or None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.setStyleSheet(_INPUT_STYLE)
        self._input.setFixedHeight(22)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.installEventFilter(self)
        layout.addWidget(self._input, 1)

        self._clear_lbl = QLabel("\u00d7")
        self._clear_lbl.setStyleSheet(_CLEAR_BTN_STYLE)
        self._clear_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_lbl.setFixedSize(16, 22)
        self._clear_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._clear_lbl.mousePressEvent = lambda _e: self.clear_selection()
        self._clear_lbl.hide()
        layout.addWidget(self._clear_lbl, 0)

        self._popup = _ResultPopup()
        self._popup.result_clicked.connect(self._select_item)

        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self._update_results)

        # Delayed blur dismiss — allows popup click to register first
        self._blur_timer = QTimer()
        self._blur_timer.setSingleShot(True)
        self._blur_timer.setInterval(150)
        self._blur_timer.timeout.connect(self._on_blur_timeout)

    # --- Public API ---

    def set_items(self, items: list[dict]):
        self._all_items = items

    def set_color_fn(self, color_fn):
        """Update the color callback for dropdown items."""
        self._color_fn = color_fn

    def clear_selection(self):
        self._selected = None
        self._input.blockSignals(True)
        self._input.clear()
        self._input.blockSignals(False)
        self._clear_lbl.hide()
        self._popup.hide()
        self.item_selected.emit({})

    def selected_item(self) -> dict | None:
        return self._selected

    def selected_name(self) -> str | None:
        if self._selected:
            return _item_name(self._selected) or None
        return None

    # --- Private ---

    def _on_text_changed(self, text: str):
        if self._selected:
            self._selected = None
            self._clear_lbl.hide()
            self.item_selected.emit({})
        self._debounce.start()

    def _update_results(self):
        query = self._input.text().strip()
        if not query or not self._all_items:
            self._popup.hide()
            return

        scored = []
        for item in self._all_items:
            name = _item_name(item)
            s = _fuzzy_score(name, query)
            if s > 0:
                scored.append((s, item))
        scored.sort(key=lambda t: t[0], reverse=True)
        results = [item for _, item in scored[:_MAX_RESULTS]]

        if not results:
            self._popup.hide()
            return

        self._popup.set_results(results, color_fn=self._color_fn)
        self._position_popup()
        self._popup.show()
        self._popup.raise_()

    def _position_popup(self):
        global_pos = self._input.mapToGlobal(
            self._input.rect().bottomLeft()
        )
        self._popup.move(global_pos.x(), global_pos.y() + 2)
        self._popup.setFixedWidth(self._input.width())

    def _select_item(self, item: dict):
        self._blur_timer.stop()
        self._selected = item
        name = _item_name(item)
        self._input.blockSignals(True)
        self._input.setText(name)
        self._input.blockSignals(False)
        self._clear_lbl.show()
        self._popup.hide()
        self.item_selected.emit(item)

    def _on_blur_timeout(self):
        if self._popup.isVisible():
            self._popup.hide()

    # --- Event filter for keyboard nav + focus out ---

    def eventFilter(self, obj, event):
        if obj is self._input:
            if event.type() == QEvent.Type.FocusOut:
                self._blur_timer.start()
                return False

            if event.type() == QEvent.Type.KeyPress and self._popup.isVisible():
                if event.isAutoRepeat():
                    return True
                key = event.key()
                if key == Qt.Key.Key_Down:
                    idx = self._popup.highlight_index + 1
                    self._popup.highlight(min(idx, self._popup.result_count - 1))
                    return True
                if key == Qt.Key.Key_Up:
                    idx = self._popup.highlight_index - 1
                    self._popup.highlight(max(idx, 0))
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    item = self._popup.highlighted_item()
                    if item:
                        self._select_item(item)
                    return True
                if key == Qt.Key.Key_Escape:
                    self._popup.hide()
                    return True

        return super().eventFilter(obj, event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._blur_timer.stop()
        if self._selected:
            self._input.selectAll()

    def hideEvent(self, event):
        self._popup.hide()
        super().hideEvent(event)
