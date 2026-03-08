"""Market price manual review dialog.

Opens when the OCR detects values it cannot resolve automatically:
- Markup overflow (>999999%, displayed as em dash in game)
- Ambiguous item name that couldn't be resolved by Levenshtein matching

The user can fill in the missing values and submit, or choose to skip.
A first-time tutorial explains the feature. Reviews queue up if multiple
items need attention.
"""

from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..theme import ACCENT, BORDER, SECONDARY, TEXT_MUTED, WARNING

if TYPE_CHECKING:
    from ...core.config import AppConfig

# Snooze duration for "Later" button
SNOOZE_SECONDS = 3600  # 60 minutes

PERIODS = ["1d", "7d", "30d", "365d", "3650d"]
PERIOD_LABELS = {
    "1d": "1 Day",
    "7d": "7 Days",
    "30d": "30 Days",
    "365d": "1 Year",
    "3650d": "Decade",
}


class MarketReviewDialog(QDialog):
    """Queued manual review dialog for ambiguous/overflow market price data.

    Signals:
        reviewed: emitted with (original_data, corrections, manually_reviewed_fields)
            when the user submits corrections.
        skipped: emitted with (original_data,) when Never is chosen or queue
            is dismissed — the entry should be sent as-is.
    """

    reviewed = pyqtSignal(dict, dict, list)
    skipped = pyqtSignal(dict)
    config_changed = pyqtSignal()  # tutorial/never state changed — save config

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._queue: deque[dict] = deque()
        self._current: dict | None = None
        self._snoozed_until: float = 0.0

        self.setWindowTitle("Market Price Review")
        self.setMinimumWidth(440)
        self.setStyleSheet(f"QDialog {{ background-color: {SECONDARY}; }}")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_tutorial_page())
        self._stack.addWidget(self._build_review_page())

    # ------------------------------------------------------------------
    # Tutorial page (first use)
    # ------------------------------------------------------------------

    def _build_tutorial_page(self) -> QFrame:
        page = QFrame()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Market Price Review")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        explanation = QLabel(
            "Sometimes the game displays markup values as an em dash "
            "(\u2014) when the value exceeds 999,999%. The OCR can detect "
            "this but cannot read the actual number.\n\n"
            "You can see the real value by hovering over the cell in-game "
            "(a tooltip shows all digits). This dialog asks you to type in "
            "those values manually.\n\n"
            "It also appears when two items have very similar names "
            "(e.g. ArMatrix LR-10 vs LR-15) and the OCR isn't sure "
            "which one it is."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet(f"color: {TEXT_MUTED}; line-height: 1.4;")
        layout.addWidget(explanation)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        never_btn = QPushButton("Never ask")
        never_btn.setToolTip(
            "Disable review dialogs. Scans will be submitted as-is.\n"
            "You can re-enable this in Settings > OCR > Market Price."
        )
        never_btn.clicked.connect(self._on_tutorial_never)
        btn_row.addWidget(never_btn)

        later_btn = QPushButton("Later")
        later_btn.setToolTip("Snooze for 60 minutes")
        later_btn.clicked.connect(self._on_tutorial_later)
        btn_row.addWidget(later_btn)

        yes_btn = QPushButton("Yes, help me review")
        yes_btn.setObjectName("accentButton")
        yes_btn.clicked.connect(self._on_tutorial_yes)
        btn_row.addWidget(yes_btn)

        layout.addLayout(btn_row)
        return page

    # ------------------------------------------------------------------
    # Review page
    # ------------------------------------------------------------------

    def _build_review_page(self) -> QFrame:
        page = QFrame()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # Header: item name + queue indicator
        header = QHBoxLayout()
        self._name_label = QLabel()
        self._name_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        header.addWidget(self._name_label, 1)

        self._queue_label = QLabel()
        self._queue_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        header.addWidget(self._queue_label)
        layout.addLayout(header)

        # Reason
        self._reason_label = QLabel()
        self._reason_label.setWordWrap(True)
        self._reason_label.setStyleSheet(
            f"color: {WARNING}; font-size: 11px; padding: 4px 0;"
        )
        layout.addWidget(self._reason_label)

        # Item name combo (only visible for ambiguous names)
        self._name_row = QHBoxLayout()
        self._name_row_label = QLabel("Item name:")
        self._name_row.addWidget(self._name_row_label)
        self._name_combo = QComboBox()
        self._name_combo.setMinimumWidth(250)
        self._name_row.addWidget(self._name_combo, 1)
        self._name_container = QFrame()
        name_container_layout = QVBoxLayout(self._name_container)
        name_container_layout.setContentsMargins(0, 0, 0, 0)
        name_container_layout.addLayout(self._name_row)
        layout.addWidget(self._name_container)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(sep)

        # Grid: 5 periods x 2 columns (markup, sales)
        self._markup_spins: dict[str, QDoubleSpinBox] = {}
        self._sales_spins: dict[str, QDoubleSpinBox] = {}
        self._markup_labels: dict[str, QLabel] = {}
        self._sales_labels: dict[str, QLabel] = {}

        grid_header = QHBoxLayout()
        grid_header.addWidget(QLabel("Period"), 1)
        markup_h = QLabel("Markup")
        markup_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid_header.addWidget(markup_h, 2)
        sales_h = QLabel("Sales (PED)")
        sales_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid_header.addWidget(sales_h, 2)
        layout.addLayout(grid_header)

        for period in PERIODS:
            row = QHBoxLayout()
            row.setSpacing(8)

            label = QLabel(PERIOD_LABELS.get(period, period))
            label.setMinimumWidth(60)
            row.addWidget(label, 1)

            # Markup spin
            markup_spin = QDoubleSpinBox()
            markup_spin.setDecimals(1)
            markup_spin.setRange(-1, 99_999_999)
            markup_spin.setSpecialValueText("\u2014")  # em dash for -1
            markup_spin.setFixedWidth(110)
            self._markup_spins[period] = markup_spin
            markup_lbl = QLabel()
            markup_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
            self._markup_labels[period] = markup_lbl
            markup_col = QVBoxLayout()
            markup_col.setSpacing(0)
            markup_col.addWidget(markup_spin)
            markup_col.addWidget(markup_lbl)
            row.addLayout(markup_col, 2)

            # Sales spin
            sales_spin = QDoubleSpinBox()
            sales_spin.setDecimals(2)
            sales_spin.setRange(0, 999_999_999)
            sales_spin.setFixedWidth(110)
            self._sales_spins[period] = sales_spin
            sales_lbl = QLabel()
            sales_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
            self._sales_labels[period] = sales_lbl
            sales_col = QVBoxLayout()
            sales_col.setSpacing(0)
            sales_col.addWidget(sales_spin)
            sales_col.addWidget(sales_lbl)
            row.addLayout(sales_col, 2)

            layout.addLayout(row)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        skip_btn = QPushButton("Skip")
        skip_btn.setToolTip("Send this entry as-is without corrections")
        skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(skip_btn)

        btn_row.addStretch()

        later_btn = QPushButton("Snooze 60 min")
        later_btn.setToolTip("Dismiss all pending reviews for 60 minutes")
        later_btn.clicked.connect(self._on_later)
        btn_row.addWidget(later_btn)

        submit_btn = QPushButton("Submit")
        submit_btn.setObjectName("accentButton")
        submit_btn.clicked.connect(self._on_submit)
        btn_row.addWidget(submit_btn)

        layout.addLayout(btn_row)
        return page

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, review_request: dict) -> None:
        """Add a review request to the queue. Shows the dialog if needed."""
        if not self._config.market_price_review_enabled:
            # Reviews disabled — emit skipped immediately
            self.skipped.emit(review_request.get("data", {}))
            return

        if time.monotonic() < self._snoozed_until:
            self.skipped.emit(review_request.get("data", {}))
            return

        self._queue.append(review_request)

        if not self.isVisible():
            if not self._config.market_price_review_tutorial_shown:
                self._stack.setCurrentIndex(0)
            else:
                self._stack.setCurrentIndex(1)
                self._show_current()
            self.show()
            self.raise_()
            self.activateWindow()
        else:
            # Already showing — update queue count
            self._update_queue_label()

    # ------------------------------------------------------------------
    # Tutorial handlers
    # ------------------------------------------------------------------

    def _on_tutorial_never(self):
        self._config.market_price_review_enabled = False
        self._config.market_price_review_tutorial_shown = True
        self.config_changed.emit()
        self._skip_all()
        self.hide()

    def _on_tutorial_later(self):
        self._config.market_price_review_tutorial_shown = True
        self.config_changed.emit()
        self._snoozed_until = time.monotonic() + SNOOZE_SECONDS
        self._skip_all()
        self.hide()

    def _on_tutorial_yes(self):
        self._config.market_price_review_tutorial_shown = True
        self.config_changed.emit()
        self._stack.setCurrentIndex(1)
        self._show_current()

    # ------------------------------------------------------------------
    # Review handlers
    # ------------------------------------------------------------------

    def _on_skip(self):
        if self._current:
            self.skipped.emit(self._current.get("data", {}))
        self._advance()

    def _on_later(self):
        self._snoozed_until = time.monotonic() + SNOOZE_SECONDS
        self._skip_all()
        self.hide()

    def _on_submit(self):
        if not self._current:
            return

        data = self._current.get("data", {})
        editable = self._current.get("editable_fields", [])
        corrections: dict = {}
        reviewed_fields: list[str] = []

        # Collect corrections for editable fields
        if "item_name" in editable:
            new_name = self._name_combo.currentText().strip()
            if new_name:
                reviewed_fields.append("item_name")
                if new_name != data.get("item_name", ""):
                    corrections["item_name"] = new_name

        for period in PERIODS:
            mk = f"markup_{period}"
            if mk in editable:
                val = self._markup_spins[period].value()
                if val != -1:  # user changed from overflow
                    corrections[mk] = val
                    reviewed_fields.append(mk)

            sk = f"sales_{period}"
            if sk in editable:
                val = self._sales_spins[period].value()
                corrections[sk] = val
                reviewed_fields.append(sk)

        self.reviewed.emit(data, corrections, reviewed_fields)
        self._advance()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _show_current(self):
        """Populate the review page with the next queued item."""
        if not self._queue:
            self.hide()
            return

        self._current = self._queue.popleft()
        data = self._current.get("data", {})
        editable = set(self._current.get("editable_fields", []))
        candidates = self._current.get("candidates", [])
        reason = self._current.get("reason", "")

        # Header
        name = data.get("item_name", "Unknown")
        self._name_label.setText(name)
        self._reason_label.setText(reason)
        self._update_queue_label()

        # Name combo
        has_name_edit = "item_name" in editable
        self._name_container.setVisible(has_name_edit)
        if has_name_edit:
            self._name_combo.clear()
            # Add current name first, then candidates
            self._name_combo.addItem(name)
            for c in candidates:
                if c != name:
                    self._name_combo.addItem(c)

        # Populate cells
        for period in PERIODS:
            mk_key = f"markup_{period}"
            mk_val = data.get(mk_key)
            mk_spin = self._markup_spins[period]
            mk_editable = mk_key in editable

            if mk_val is not None and mk_val != -1:
                mk_spin.setValue(mk_val)
            else:
                mk_spin.setValue(-1)  # shows em dash
            mk_spin.setEnabled(mk_editable)
            if mk_editable:
                mk_spin.setStyleSheet(f"border: 1px solid {WARNING};")
                self._markup_labels[period].setText("needs value")
            else:
                mk_spin.setStyleSheet("")
                raw = data.get(f"{mk_key}_raw", "")
                self._markup_labels[period].setText(raw)

            sk_key = f"sales_{period}"
            sk_val = data.get(sk_key)
            sk_spin = self._sales_spins[period]
            sk_editable = sk_key in editable

            sk_spin.setValue(sk_val if sk_val is not None else 0)
            sk_spin.setEnabled(sk_editable)
            if sk_editable:
                sk_spin.setStyleSheet(f"border: 1px solid {WARNING};")
                self._sales_labels[period].setText("needs value")
            else:
                sk_spin.setStyleSheet("")
                raw = data.get(f"{sk_key}_raw", "")
                self._sales_labels[period].setText(raw)

    def _advance(self):
        """Move to next queued item or hide if empty."""
        self._current = None
        if self._queue:
            self._show_current()
        else:
            self.hide()

    def _skip_all(self):
        """Skip the current item and all queued items."""
        if self._current:
            self.skipped.emit(self._current.get("data", {}))
            self._current = None
        while self._queue:
            req = self._queue.popleft()
            self.skipped.emit(req.get("data", {}))

    def _update_queue_label(self):
        remaining = len(self._queue)
        if remaining > 0:
            self._queue_label.setText(f"+{remaining} more")
        else:
            self._queue_label.setText("")

    def closeEvent(self, event):
        """Treat closing the window as snooze."""
        self._snoozed_until = time.monotonic() + SNOOZE_SECONDS
        self._skip_all()
        super().closeEvent(event)
