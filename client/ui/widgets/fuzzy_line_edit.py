"""FuzzyLineEdit — a QLineEdit with a fuzzy-scored popup suggestion list.

Mirrors the scoring algorithm from nexus/src/lib/search.js so that item
selection in the desktop client matches the website's SearchInput behaviour.
"""

from __future__ import annotations

import re

from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QEvent
from PyQt6.QtWidgets import QLineEdit, QListWidget, QListWidgetItem, QApplication

from ..theme import (
    MAIN_DARK, TEXT, TEXT_MUTED, BORDER, ACCENT, SECONDARY, HOVER,
)

MAX_SUGGESTIONS = 15


# ---------------------------------------------------------------------------
# Fuzzy scoring (ported from nexus/src/lib/search.js)
# ---------------------------------------------------------------------------

def _score_word_pair(name_word: str, query_word: str) -> int:
    if name_word == query_word:
        return 100
    if name_word.startswith(query_word):
        return 85 - min(len(name_word) - len(query_word), 15)
    if query_word in name_word:
        return 60
    if len(query_word) >= 3:
        qi = 0
        for ch in name_word:
            if qi < len(query_word) and ch == query_word[qi]:
                qi += 1
        if qi == len(query_word):
            return 30
    return 0


def _score_multi_word(name_lower: str, query_words: list[str]) -> int:
    name_words = [w for w in re.split(r"[\s,]+", name_lower) if w]
    total_score = 0
    matched = 0
    used: set[int] = set()

    for qw in query_words:
        best_score = 0
        best_idx = -1
        for i, nw in enumerate(name_words):
            if i in used:
                continue
            s = _score_word_pair(nw, qw)
            if s > best_score:
                best_score = s
                best_idx = i
        if best_score > 0 and best_idx >= 0:
            used.add(best_idx)
            total_score += best_score
            matched += 1

    if matched == 0:
        return 0
    ratio = matched / len(query_words)
    if ratio < 0.5:
        return 0

    avg = total_score / len(query_words)
    base = 550 + avg * 1.5
    bonus = 50 if ratio >= 1 else 0
    penalty = min(len(name_lower) * 0.5, 30)
    return round(base + bonus - penalty)


def score_search(name: str, query: str) -> int:
    """Score *name* against *query*. Higher is better, 0 means no match."""
    if not name or not query:
        return 0
    nl = name.lower()
    ql = query.lower().strip()
    if not ql:
        return 0

    # Exact
    if nl == ql:
        return 1000

    # Starts with
    if nl.startswith(ql):
        return 900 - len(nl)

    # A word starts with query
    words = nl.split()
    for i, w in enumerate(words):
        if w.startswith(ql):
            return 800 - i * 5 - len(nl)

    # Contains substring
    idx = nl.find(ql)
    if idx != -1:
        return 700 - min(idx, 50) - len(nl)

    # Multi-word
    qwords = [w for w in ql.split() if w]
    if len(qwords) > 1:
        mw = _score_multi_word(nl, qwords)
        if mw > 0:
            return mw

    # Short queries — substring only
    if len(ql) < 4:
        return 0

    # Fuzzy
    qi = 0
    score = 0
    consecutive = 0
    positions: list[int] = []
    for i, ch in enumerate(nl):
        if qi < len(ql) and ch == ql[qi]:
            positions.append(i)
            qi += 1
            consecutive += 10
            score += consecutive
            if i == 0 or nl[i - 1] in (" ", "-", "_"):
                score += 30
        else:
            consecutive = 0

    if qi == len(ql):
        spread = (positions[-1] - positions[0]) if len(positions) > 1 else 0
        if spread > len(ql) * 2:
            return 0
        return 300 + score + max(0, 50 - spread)

    ratio = qi / len(ql)
    if ratio >= 0.95 and len(ql) >= 5:
        spread = (positions[-1] - positions[0]) if len(positions) > 1 else 0
        if spread <= len(ql) * 2:
            return 100 + int(score * ratio)

    return 0


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

_POPUP_STYLE = f"""
QListWidget {{
    background-color: {SECONDARY};
    color: {TEXT};
    border: 1px solid {BORDER};
    font-size: 13px;
    padding: 2px;
}}
QListWidget::item {{
    padding: 4px 8px;
}}
QListWidget::item:hover {{
    background-color: {HOVER};
}}
QListWidget::item:selected {{
    background-color: {ACCENT};
    color: {MAIN_DARK};
}}
"""


class FuzzyLineEdit(QLineEdit):
    """Line edit with a fuzzy-scored dropdown suggestion list.

    Usage::

        field = FuzzyLineEdit(placeholder="Select weapon...")
        field.set_items(["Arsonistic Chip I", "ArMatrix LR-30 (L)", ...])
        field.item_selected.connect(on_weapon_changed)
    """

    item_selected = pyqtSignal(str)  # emitted when user picks a suggestion

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self._items: list[str] = []
        self._block_filter = False

        # Popup created lazily on first use to avoid expensive QListWidget
        # construction for all ~15 FuzzyLineEdits during page init.
        self._popup: QListWidget | None = None

        self.textChanged.connect(self._on_text_changed)
        self._watched_window = None

    def _ensure_popup(self) -> QListWidget:
        if self._popup is None:
            self._popup = QListWidget()
            self._popup.setWindowFlags(
                Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
            )
            self._popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._popup.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self._popup.setStyleSheet(_POPUP_STYLE)
            self._popup.itemClicked.connect(self._on_item_clicked)
            self._popup.hide()
        return self._popup

    # --- public API ---

    def set_items(self, items: list[str]) -> None:
        self._items = items

    def set_value(self, value: str) -> None:
        """Set text without triggering the filter popup."""
        self._block_filter = True
        self.setText(value or "")
        self._block_filter = False

    def clear_selection(self) -> None:
        self._block_filter = True
        self.clear()
        self._block_filter = False
        if self._popup is not None:
            self._popup.hide()

    def current_value(self) -> str:
        return self.text().strip()

    # --- internal ---

    def _on_text_changed(self, text: str) -> None:
        if self._block_filter:
            return
        query = text.strip()
        if not query:
            if self._popup is not None:
                self._popup.hide()
            return
        self._show_suggestions(query)

    def _show_suggestions(self, query: str) -> None:
        scored: list[tuple[int, str]] = []
        for name in self._items:
            s = score_search(name, query)
            if s > 0:
                scored.append((s, name))
        scored.sort(key=lambda t: (-t[0], len(t[1])))
        scored = scored[:MAX_SUGGESTIONS]

        if not scored:
            if self._popup is not None:
                self._popup.hide()
            return

        popup = self._ensure_popup()
        popup.blockSignals(True)
        popup.clear()
        for _, name in scored:
            popup.addItem(name)
        popup.blockSignals(False)

        # Position below the line edit
        pos = self.mapToGlobal(QPoint(0, self.height()))
        popup.setFixedWidth(max(self.width(), 300))
        row_h = 28
        h = min(len(scored) * row_h + 6, 400)
        popup.setFixedHeight(h)
        popup.move(pos)
        popup.show()
        popup.raise_()

        # Watch top-level window for move/resize to dismiss popup
        win = self.window()
        if win and win is not self._watched_window:
            if self._watched_window:
                self._watched_window.removeEventFilter(self)
            win.installEventFilter(self)
            self._watched_window = win

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        text = item.text()
        self._block_filter = True
        self.setText(text)
        self._block_filter = False
        self._popup.hide()
        self.item_selected.emit(text)

    def keyPressEvent(self, event):
        key = event.key()
        if self._popup is not None and self._popup.isVisible():
            if key == Qt.Key.Key_Down:
                row = self._popup.currentRow()
                if row < self._popup.count() - 1:
                    self._popup.setCurrentRow(row + 1)
                return
            if key == Qt.Key.Key_Up:
                row = self._popup.currentRow()
                if row > 0:
                    self._popup.setCurrentRow(row - 1)
                return
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                cur = self._popup.currentItem()
                if cur:
                    self._on_item_clicked(cur)
                    return
            if key == Qt.Key.Key_Escape:
                self._popup.hide()
                return
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # If text matches an item exactly, emit selection
            text = self.text().strip()
            if text and text in self._items:
                self.item_selected.emit(text)
            return

        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        # Small delay so click on popup registers before hiding
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(150, self._maybe_hide_popup)
        super().focusOutEvent(event)

    def _maybe_hide_popup(self) -> None:
        if self._popup is not None and not self._popup.underMouse():
            self._popup.hide()

    def hideEvent(self, event):
        if self._popup is not None:
            self._popup.hide()
        super().hideEvent(event)

    def eventFilter(self, obj, event):
        """Close popup when the top-level window moves or resizes."""
        etype = event.type()
        if etype in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.WindowStateChange):
            if self._popup is not None:
                self._popup.hide()
        return super().eventFilter(obj, event)
