"""Floating notification center panel with Notifications + Rules tabs."""

from __future__ import annotations

import uuid
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea,
    QPushButton, QLabel, QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QTextEdit, QGroupBox, QFrame, QSizePolicy,
    QDialog, QFormLayout, QDialogButtonBox, QGridLayout,
)
from PyQt6.QtCore import Qt, QSize, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QFont, QDesktopServices

from ..theme import (
    PRIMARY, SECONDARY, MAIN_DARK, HOVER, BORDER, BORDER_HOVER,
    TEXT, TEXT_MUTED, ACCENT, ACCENT_HOVER,
    ERROR, ERROR_BG, SUCCESS, SUCCESS_BG, WARNING, WARNING_BG,
    FONT_FAMILY,
)
from ...notifications.models import (
    Notification, GlobalNotificationRule,
    SOURCE_GLOBAL, SOURCE_TRADE_CHAT, SOURCE_NEXUS, SOURCE_SYSTEM,
    SOURCE_STREAM,
)

PANEL_WIDTH = 380
PANEL_HEIGHT = 500

_STREAM_COLOR = "#E05050"

_SOURCE_COLORS = {
    SOURCE_GLOBAL: WARNING,
    SOURCE_TRADE_CHAT: ACCENT,
    SOURCE_NEXUS: SUCCESS,
    SOURCE_SYSTEM: TEXT_MUTED,
    SOURCE_STREAM: _STREAM_COLOR,
}

_SOURCE_LABELS = {
    SOURCE_GLOBAL: "Global",
    SOURCE_TRADE_CHAT: "Trade",
    SOURCE_NEXUS: "Nexus",
    SOURCE_SYSTEM: "System",
    SOURCE_STREAM: "Stream",
}

GLOBAL_TYPE_OPTIONS = [
    ("kill", "Kill"),
    ("team_kill", "Team Kill"),
    ("deposit", "Deposit"),
    ("craft", "Craft"),
    ("rare_item", "Rare Item"),
    ("discovery", "Discovery"),
    ("tier", "Tier Record"),
    ("examine", "Instance"),
    ("pvp", "PvP"),
    ("hof", "HoF"),
    ("ath", "ATH"),
]


def _time_ago(dt: datetime) -> str:
    delta = datetime.now() - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _get_action(notif: Notification):
    """Return (label, url) for a context-dependent action, or None."""
    if notif.source == SOURCE_NEXUS:
        return ("Open on Nexus", "https://entropianexus.com")
    if notif.source == SOURCE_STREAM:
        url = notif.metadata.get("channel_url", "")
        if url and url.lower().startswith(("https://", "http://")):
            return ("Watch", url)
    return None


# =====================================================================
# Notification row
# =====================================================================

class _NotificationRow(QFrame):
    """Single notification item — click to expand/collapse."""

    clicked = pyqtSignal(str)  # notification id (for mark-read)

    def __init__(self, notif: Notification, parent=None):
        super().__init__(parent)
        self._notif = notif
        self._expanded = False
        self._marked_read = notif.read
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(56)
        self.setMaximumHeight(56)

        color = _SOURCE_COLORS.get(notif.source, TEXT_MUTED)
        self._update_bg()

        main = QVBoxLayout(self)
        main.setContentsMargins(8, 4, 8, 4)
        main.setSpacing(4)

        # --- Header row (always visible) ---
        header = QHBoxLayout()
        header.setSpacing(8)

        # Unread dot
        self._dot = QLabel()
        self._dot.setFixedSize(8, 8)
        self._update_dot()
        header.addWidget(self._dot)

        # Source label
        src_lbl = QLabel(_SOURCE_LABELS.get(notif.source, "?"))
        src_lbl.setFixedWidth(42)
        src_lbl.setStyleSheet(
            f"color: {color}; font-size: 10px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        header.addWidget(src_lbl)

        # Title + elided body (collapsed view)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)

        self._title_lbl = QLabel(notif.title)
        self._title_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        self._title_lbl.setMaximumWidth(200)
        fm = self._title_lbl.fontMetrics()
        self._title_lbl.setText(
            fm.elidedText(notif.title, Qt.TextElideMode.ElideRight, 200)
        )
        text_col.addWidget(self._title_lbl)

        self._body_short = QLabel(notif.body)
        self._body_short.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px;"
            f" background: transparent; border: none;"
        )
        self._body_short.setMaximumWidth(200)
        fm2 = self._body_short.fontMetrics()
        self._body_short.setText(
            fm2.elidedText(notif.body, Qt.TextElideMode.ElideRight, 200)
        )
        text_col.addWidget(self._body_short)

        header.addLayout(text_col, stretch=1)

        # Time ago
        time_lbl = QLabel(_time_ago(notif.timestamp))
        time_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px;"
            f" background: transparent; border: none;"
        )
        header.addWidget(time_lbl)

        main.addLayout(header)

        # --- Expanded area (hidden by default) ---
        self._expanded_area = QWidget()
        self._expanded_area.setStyleSheet("border: none; background: transparent;")
        exp_layout = QVBoxLayout(self._expanded_area)
        exp_layout.setContentsMargins(58, 0, 8, 4)  # indent past dot+src
        exp_layout.setSpacing(6)

        # Full title
        title_full = QLabel(notif.title)
        title_full.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        title_full.setWordWrap(True)
        exp_layout.addWidget(title_full)

        # Full body
        if notif.body:
            body_full = QLabel(notif.body)
            body_full.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px;"
                f" background: transparent; border: none;"
            )
            body_full.setWordWrap(True)
            exp_layout.addWidget(body_full)

        # Action button
        action = _get_action(notif)
        if action:
            label, url = action
            action_btn = QPushButton(label)
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_btn.setFixedWidth(120)
            action_btn.setStyleSheet(
                f"QPushButton {{ color: {TEXT}; background: {ACCENT};"
                f" border: none; border-radius: 3px; padding: 4px 10px;"
                f" font-size: 11px; }}"
                f"QPushButton:hover {{ background: {ACCENT_HOVER}; }}"
            )
            action_btn.clicked.connect(
                lambda _checked, u=url: QDesktopServices.openUrl(QUrl(u))
            )
            exp_layout.addWidget(action_btn)

        self._expanded_area.hide()
        main.addWidget(self._expanded_area)

    def _update_bg(self):
        bg = MAIN_DARK if self._marked_read else SECONDARY
        self.setStyleSheet(
            f"_NotificationRow {{ background: {bg};"
            f" border-bottom: 1px solid {BORDER}; border-radius: 0px; }}"
            f"_NotificationRow:hover {{ background: {HOVER}; }}"
        )

    def _update_dot(self):
        if not self._marked_read:
            self._dot.setStyleSheet(
                f"background: {ACCENT}; border-radius: 4px; border: none;"
            )
        else:
            self._dot.setStyleSheet("background: transparent; border: none;")

    def mousePressEvent(self, event):
        # Mark as read on first interaction
        if not self._marked_read:
            self._marked_read = True
            self._update_dot()
            self._update_bg()
            self.clicked.emit(self._notif.id)

        # Toggle expanded
        self._expanded = not self._expanded
        if self._expanded:
            self._body_short.hide()
            self._title_lbl.hide()
            self._expanded_area.show()
            self.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
        else:
            self._expanded_area.hide()
            self._body_short.show()
            self._title_lbl.show()
            self.setMaximumHeight(56)

        super().mousePressEvent(event)


# =====================================================================
# Rule row
# =====================================================================

def _build_rule_summary(rule: GlobalNotificationRule) -> str:
    """Build a short one-line summary string for a rule."""
    parts: list[str] = []

    # Action + priority
    action = "Notify" if rule.action == "notify" else "Suppress"
    if rule.priority and rule.priority > 0:
        action += f" P{rule.priority}"
    parts.append(action)

    # Filters
    filters: list[str] = []
    if rule.player_name:
        filters.append(f"Player: {rule.player_name}")
    if rule.mob_name:
        filters.append(f"Mob: {rule.mob_name}")
    if rule.item_name:
        filters.append(f"Item: {rule.item_name}")
    if rule.min_value and rule.min_value > 0:
        filters.append(f">={rule.min_value:g} PED")
    if filters:
        parts.append(", ".join(filters))

    # Types
    active = rule.global_types or []
    if active and len(active) < len(GLOBAL_TYPE_OPTIONS):
        type_map = dict(GLOBAL_TYPE_OPTIONS)
        labels = [type_map[k] for k in active if k in type_map]
        if labels:
            parts.append(", ".join(labels))
    elif not active:
        parts.append("All types")

    return " | ".join(parts)


class _RuleEditDialog(QDialog):
    """Modal dialog for editing a single GlobalNotificationRule."""

    _EDIT_STYLE = (
        f"QLineEdit {{ background: {MAIN_DARK}; color: {TEXT}; font-size: 12px;"
        f" border: 1px solid {BORDER}; border-radius: 3px; padding: 3px 6px; }}"
    )

    def __init__(self, rule: GlobalNotificationRule, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Rule")
        self.setFixedWidth(320)
        self.setStyleSheet(
            f"QDialog {{ background: {PRIMARY}; color: {TEXT}; }}"
            f"QLabel {{ color: {TEXT}; font-size: 12px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Enabled
        self._enabled_cb = QCheckBox("Enabled")
        self._enabled_cb.setChecked(rule.enabled)
        self._enabled_cb.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        form.addRow(self._enabled_cb)

        # Action
        self._action_combo = QComboBox()
        self._action_combo.addItems(["Notify", "Suppress"])
        self._action_combo.setCurrentIndex(0 if rule.action == "notify" else 1)
        self._action_combo.setStyleSheet(f"font-size: 12px;")
        form.addRow("Action:", self._action_combo)

        # Priority
        self._priority_spin = QSpinBox()
        self._priority_spin.setRange(0, 999)
        self._priority_spin.setValue(rule.priority)
        self._priority_spin.setStyleSheet(f"font-size: 12px;")
        self._priority_spin.setToolTip("Higher priority rules are checked first")
        form.addRow("Priority:", self._priority_spin)

        # Player
        self._player_edit = QLineEdit(rule.player_name or "")
        self._player_edit.setPlaceholderText("Any player")
        self._player_edit.setStyleSheet(self._EDIT_STYLE)
        form.addRow("Player:", self._player_edit)

        # Mob
        self._mob_edit = QLineEdit(rule.mob_name or "")
        self._mob_edit.setPlaceholderText("Any mob")
        self._mob_edit.setStyleSheet(self._EDIT_STYLE)
        form.addRow("Mob:", self._mob_edit)

        # Item
        self._item_edit = QLineEdit(rule.item_name or "")
        self._item_edit.setPlaceholderText("Any item")
        self._item_edit.setStyleSheet(self._EDIT_STYLE)
        form.addRow("Item:", self._item_edit)

        # Min value
        self._value_spin = QDoubleSpinBox()
        self._value_spin.setRange(0, 999999)
        self._value_spin.setDecimals(0)
        self._value_spin.setValue(rule.min_value or 0)
        self._value_spin.setSpecialValueText("Any")
        self._value_spin.setSuffix(" PED")
        self._value_spin.setStyleSheet(f"font-size: 12px;")
        self._value_spin.setToolTip("Minimum PED value (0 = any)")
        form.addRow("Min value:", self._value_spin)

        layout.addLayout(form)

        # Type checkboxes in a grid (3 columns)
        types_label = QLabel("Event types:")
        types_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: bold;")
        layout.addWidget(types_label)

        type_grid = QGridLayout()
        type_grid.setSpacing(4)
        active_types = set(rule.global_types or [])
        self._type_cbs: dict[str, QCheckBox] = {}
        cols = 3
        for i, (type_key, type_label) in enumerate(GLOBAL_TYPE_OPTIONS):
            cb = QCheckBox(type_label)
            cb.setChecked(type_key in active_types)
            cb.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            type_grid.addWidget(cb, i // cols, i % cols)
            self._type_cbs[type_key] = cb
        layout.addLayout(type_grid)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setStyleSheet(
            f"QPushButton {{ color: {TEXT}; background: {SECONDARY};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" padding: 5px 16px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {HOVER}; }}"
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._rule_id = rule.id

    def to_rule(self) -> GlobalNotificationRule:
        """Read dialog state into a rule."""
        player = self._player_edit.text().strip() or None
        mob = self._mob_edit.text().strip() or None
        item = self._item_edit.text().strip() or None
        min_val = self._value_spin.value() if self._value_spin.value() > 0 else None
        active_types = [k for k, cb in self._type_cbs.items() if cb.isChecked()]
        return GlobalNotificationRule(
            id=self._rule_id,
            enabled=self._enabled_cb.isChecked(),
            action="notify" if self._action_combo.currentIndex() == 0 else "suppress",
            priority=self._priority_spin.value(),
            player_name=player,
            mob_name=mob,
            item_name=item,
            min_value=min_val,
            global_types=active_types if active_types else None,
        )


class _RuleSummaryRow(QFrame):
    """Compact summary row for a single GlobalNotificationRule."""

    removed = pyqtSignal(str)   # rule id
    edited = pyqtSignal(str)    # rule id

    def __init__(self, rule: GlobalNotificationRule, parent=None):
        super().__init__(parent)
        self._rule = rule
        self.rule_id = rule.id
        self.setStyleSheet(
            f"_RuleSummaryRow {{ background: {MAIN_DARK}; border: 1px solid {BORDER};"
            f" border-radius: 4px; }}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(6)

        # Enabled checkbox
        self._enabled_cb = QCheckBox()
        self._enabled_cb.setChecked(rule.enabled)
        self._enabled_cb.setFixedWidth(16)
        self._enabled_cb.stateChanged.connect(self._on_enabled_changed)
        row.addWidget(self._enabled_cb)

        # Summary label
        self._summary_lbl = QLabel()
        self._summary_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 11px; border: none; background: transparent;"
        )
        self._update_summary()
        row.addWidget(self._summary_lbl, stretch=1)

        # Edit button
        edit_btn = QPushButton("Edit")
        edit_btn.setFixedSize(36, 20)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setStyleSheet(
            f"QPushButton {{ color: {ACCENT}; background: transparent;"
            f" border: 1px solid {BORDER}; border-radius: 2px;"
            f" font-size: 10px; padding: 0; }}"
            f"QPushButton:hover {{ background: {HOVER}; }}"
        )
        edit_btn.clicked.connect(lambda: self.edited.emit(self.rule_id))
        row.addWidget(edit_btn)

        # Delete button
        del_btn = QPushButton("X")
        del_btn.setFixedSize(20, 20)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            f"QPushButton {{ color: {ERROR}; background: transparent;"
            f" border: 1px solid {BORDER}; border-radius: 2px;"
            f" font-size: 10px; font-weight: bold; padding: 0; }}"
            f"QPushButton:hover {{ background: {ERROR_BG}; }}"
        )
        del_btn.clicked.connect(lambda: self.removed.emit(self.rule_id))
        row.addWidget(del_btn)

    def _on_enabled_changed(self, state):
        self._rule.enabled = bool(state)
        self._update_summary()

    def _update_summary(self):
        text = _build_rule_summary(self._rule)
        fm = self._summary_lbl.fontMetrics()
        max_w = PANEL_WIDTH - 110  # checkbox + edit + delete + margins
        elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, max_w)
        self._summary_lbl.setText(elided)
        self._summary_lbl.setToolTip(text)
        if not self._rule.enabled:
            self._summary_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px; border: none; background: transparent;"
            )
        else:
            self._summary_lbl.setStyleSheet(
                f"color: {TEXT}; font-size: 11px; border: none; background: transparent;"
            )

    def update_rule(self, rule: GlobalNotificationRule):
        """Replace the stored rule and refresh the summary."""
        self._rule = rule
        self._enabled_cb.setChecked(rule.enabled)
        self._update_summary()

    def to_rule(self) -> GlobalNotificationRule:
        """Return the current rule (enabled state kept in sync via checkbox)."""
        return self._rule


# =====================================================================
# Notifications tab
# =====================================================================

class _NotificationsTab(QWidget):
    """Shows the notification list with mark-all-read button."""

    def __init__(self, manager, on_read_change=None, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._on_read_change = on_read_change
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(10, 8, 10, 8)
        title = QLabel("Notifications")
        title.setStyleSheet(
            f"color: {TEXT}; font-size: 14px; font-weight: bold; border: none;"
        )
        header.addWidget(title)
        header.addStretch()
        self._mark_all_btn = QPushButton("Mark all read")
        self._mark_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mark_all_btn.setStyleSheet(
            f"QPushButton {{ color: {ACCENT}; background: transparent;"
            f" border: none; font-size: 11px; }}"
            f"QPushButton:hover {{ color: {ACCENT_HOVER}; }}"
        )
        self._mark_all_btn.clicked.connect(self._on_mark_all)
        header.addWidget(self._mark_all_btn)
        layout.addLayout(header)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {PRIMARY}; }}"
        )
        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_widget)
        layout.addWidget(scroll)

        self._rows: list[_NotificationRow] = []

    def refresh(self):
        """Rebuild the notification list from the manager."""
        for row in self._rows:
            self._list_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        notifications = self._manager.get_notifications(limit=50)
        for notif in notifications:
            row = _NotificationRow(notif)
            row.clicked.connect(self._on_row_clicked)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows.append(row)

    def _on_row_clicked(self, notif_id: str):
        self._manager.mark_read(notif_id)
        if self._on_read_change:
            self._on_read_change()

    def _on_mark_all(self):
        self._manager.mark_all_read()
        self.refresh()
        if self._on_read_change:
            self._on_read_change()


# =====================================================================
# Rules tab
# =====================================================================

class _RulesTab(QWidget):
    """Configuration tab for notification rules and settings."""

    saved = pyqtSignal()  # emitted when user clicks Save

    def __init__(self, manager, config, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {PRIMARY}; }}"
        )
        container = QWidget()
        self._container_layout = QVBoxLayout(container)
        self._container_layout.setContentsMargins(10, 8, 10, 8)
        self._container_layout.setSpacing(10)

        # --- Global Notifications ---
        globals_group = QGroupBox("Global Notifications")
        globals_group.setStyleSheet(self._group_style())
        globals_layout = QVBoxLayout(globals_group)
        globals_layout.setSpacing(6)

        add_btn = QPushButton("+ Add Rule")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(
            f"QPushButton {{ color: {ACCENT}; background: transparent;"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" padding: 4px 12px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {HOVER}; }}"
        )
        add_btn.clicked.connect(self._add_rule)
        globals_layout.addWidget(add_btn)

        self._rules_layout = QVBoxLayout()
        self._rules_layout.setSpacing(4)
        globals_layout.addLayout(self._rules_layout)
        self._rule_rows: list[_RuleSummaryRow] = []

        self._container_layout.addWidget(globals_group)

        # Load existing rules
        for rule_dict in getattr(config, "notification_rules", []):
            try:
                rule = GlobalNotificationRule.from_dict(rule_dict)
                self._add_rule_row(rule)
            except Exception:
                pass

        # --- Trade Chat ---
        trade_group = QGroupBox("Trade Chat Notifications")
        trade_group.setStyleSheet(self._group_style())
        trade_layout = QVBoxLayout(trade_group)
        trade_layout.setSpacing(6)

        self._trade_enabled_cb = QCheckBox("Enable trade chat notifications")
        self._trade_enabled_cb.setChecked(
            getattr(config, "trade_chat_notifications_enabled", False)
        )
        self._trade_enabled_cb.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        trade_layout.addWidget(self._trade_enabled_cb)

        cd_row = QHBoxLayout()
        cd_lbl = QLabel("Cooldown per player+item (seconds):")
        cd_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; border: none;")
        cd_row.addWidget(cd_lbl)
        self._cooldown_spin = QSpinBox()
        self._cooldown_spin.setRange(30, 3600)
        self._cooldown_spin.setValue(
            getattr(config, "trade_chat_cooldown_seconds", 300)
        )
        self._cooldown_spin.setFixedWidth(80)
        cd_row.addWidget(self._cooldown_spin)
        cd_row.addStretch()
        trade_layout.addLayout(cd_row)

        self._container_layout.addWidget(trade_group)

        # --- Trade Ignore List ---
        ignore_group = QGroupBox("Trade Chat Ignore List")
        ignore_group.setStyleSheet(self._group_style())
        ignore_layout = QVBoxLayout(ignore_group)

        ignore_hint = QLabel("One player name per line. Messages from these players are hidden.")
        ignore_hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; border: none;")
        ignore_hint.setWordWrap(True)
        ignore_layout.addWidget(ignore_hint)

        self._ignore_edit = QTextEdit()
        self._ignore_edit.setFixedHeight(80)
        self._ignore_edit.setPlainText(
            "\n".join(getattr(config, "trade_chat_ignore_list", []))
        )
        self._ignore_edit.setStyleSheet(
            f"QTextEdit {{ background: {MAIN_DARK}; color: {TEXT};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" font-size: 12px; padding: 4px; }}"
        )
        ignore_layout.addWidget(self._ignore_edit)

        self._container_layout.addWidget(ignore_group)

        # --- Streams ---
        streams_group = QGroupBox("Stream Notifications")
        streams_group.setStyleSheet(self._group_style())
        streams_layout = QVBoxLayout(streams_group)
        streams_layout.setSpacing(6)

        self._stream_enabled_cb = QCheckBox("Notify when Nexus streamers go live")
        self._stream_enabled_cb.setChecked(
            getattr(config, "stream_notifications_enabled", True)
        )
        self._stream_enabled_cb.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        streams_layout.addWidget(self._stream_enabled_cb)

        exclude_hint = QLabel(
            "Exclude streamers (one name per line). "
            "These streamers won't trigger notifications."
        )
        exclude_hint.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; border: none;"
        )
        exclude_hint.setWordWrap(True)
        streams_layout.addWidget(exclude_hint)

        self._stream_exclude_edit = QTextEdit()
        self._stream_exclude_edit.setFixedHeight(60)
        self._stream_exclude_edit.setPlainText(
            "\n".join(getattr(config, "stream_exclude_list", []))
        )
        self._stream_exclude_edit.setStyleSheet(
            f"QTextEdit {{ background: {MAIN_DARK}; color: {TEXT};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" font-size: 12px; padding: 4px; }}"
        )
        streams_layout.addWidget(self._stream_exclude_edit)

        self._container_layout.addWidget(streams_group)

        # --- Delivery ---
        delivery_group = QGroupBox("Delivery")
        delivery_group.setStyleSheet(self._group_style())
        delivery_layout = QVBoxLayout(delivery_group)

        self._toast_cb = QCheckBox("Toast notifications (in-game when overlay active, OS otherwise)")
        self._toast_cb.setChecked(getattr(config, "notification_toast_enabled", True))
        self._toast_cb.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        delivery_layout.addWidget(self._toast_cb)

        # Toast corner position
        toast_corner_row = QHBoxLayout()
        toast_corner_row.setContentsMargins(20, 0, 0, 0)
        toast_corner_lbl = QLabel("In-game toast position:")
        toast_corner_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; border: none;"
        )
        toast_corner_row.addWidget(toast_corner_lbl)
        self._toast_corner_combo = QComboBox()
        self._toast_corner_combo.addItems([
            "Bottom Right", "Bottom Left", "Top Right", "Top Left",
        ])
        _corner_index = {
            "bottom_right": 0, "bottom_left": 1, "top_right": 2, "top_left": 3,
        }
        current_corner = getattr(config, "notification_toast_corner", "bottom_right")
        self._toast_corner_combo.setCurrentIndex(_corner_index.get(current_corner, 0))
        self._toast_corner_combo.setFixedWidth(120)
        toast_corner_row.addWidget(self._toast_corner_combo)
        toast_corner_row.addStretch()
        delivery_layout.addLayout(toast_corner_row)

        self._sound_cb = QCheckBox("Notification sound")
        self._sound_cb.setChecked(getattr(config, "notification_sound_enabled", True))
        self._sound_cb.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        delivery_layout.addWidget(self._sound_cb)

        self._container_layout.addWidget(delivery_group)

        # Save button
        save_btn = QPushButton("Save")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setFixedWidth(100)
        save_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT}; background: {ACCENT};"
            f" border: none; border-radius: 4px; padding: 6px 16px;"
            f" font-size: 12px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {ACCENT_HOVER}; }}"
        )
        save_btn.clicked.connect(self._on_save)
        self._container_layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self._container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _group_style(self) -> str:
        return (
            f"QGroupBox {{ color: {ACCENT}; font-size: 12px; font-weight: bold;"
            f" border: 1px solid {BORDER}; border-radius: 6px;"
            f" margin-top: 8px; padding-top: 16px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin;"
            f" left: 10px; padding: 0 4px; }}"
        )

    def _add_rule(self):
        rule = GlobalNotificationRule(id=str(uuid.uuid4()))
        dlg = _RuleEditDialog(rule, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._add_rule_row(dlg.to_rule())

    def _add_rule_row(self, rule: GlobalNotificationRule):
        row = _RuleSummaryRow(rule)
        row.removed.connect(self._remove_rule)
        row.edited.connect(self._edit_rule)
        self._rules_layout.addWidget(row)
        self._rule_rows.append(row)

    def _edit_rule(self, rule_id: str):
        for row in self._rule_rows:
            if row.rule_id == rule_id:
                dlg = _RuleEditDialog(row.to_rule(), parent=self)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    row.update_rule(dlg.to_rule())
                break

    def _remove_rule(self, rule_id: str):
        for row in self._rule_rows:
            if row.rule_id == rule_id:
                self._rules_layout.removeWidget(row)
                row.deleteLater()
                self._rule_rows.remove(row)
                break

    def _on_save(self):
        from ...core.config import save_config

        # Collect rules
        rules = [row.to_rule() for row in self._rule_rows]
        self._config.notification_rules = [r.to_dict() for r in rules]

        # Trade chat settings
        self._config.trade_chat_notifications_enabled = self._trade_enabled_cb.isChecked()
        self._config.trade_chat_cooldown_seconds = self._cooldown_spin.value()

        # Ignore list
        text = self._ignore_edit.toPlainText().strip()
        names = [n.strip() for n in text.splitlines() if n.strip()]
        self._config.trade_chat_ignore_list = names

        # Stream settings
        self._config.stream_notifications_enabled = self._stream_enabled_cb.isChecked()
        exclude_text = self._stream_exclude_edit.toPlainText().strip()
        exclude_names = [n.strip() for n in exclude_text.splitlines() if n.strip()]
        self._config.stream_exclude_list = exclude_names

        # Delivery
        self._config.notification_toast_enabled = self._toast_cb.isChecked()
        _corner_values = ["bottom_right", "bottom_left", "top_right", "top_left"]
        self._config.notification_toast_corner = _corner_values[
            self._toast_corner_combo.currentIndex()
        ]
        self._config.notification_sound_enabled = self._sound_cb.isChecked()

        save_config(self._config)

        # Update manager
        self._manager.update_rules(rules)
        self._manager.update_trade_ignore(names)
        self._manager.update_stream_exclude(exclude_names)

        self.saved.emit()


# =====================================================================
# Notification center (floating panel)
# =====================================================================

class NotificationCenter(QWidget):
    """Floating panel anchored to sidebar, showing notifications and rules."""

    read_state_changed = pyqtSignal()

    def __init__(self, *, manager, config, parent=None):
        super().__init__(parent)
        self._manager = manager
        self.setFixedSize(PANEL_WIDTH, PANEL_HEIGHT)
        self.setStyleSheet(
            f"NotificationCenter {{ background: {PRIMARY};"
            f" border: 1px solid {BORDER}; border-radius: 8px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; background: {PRIMARY}; }}"
            f"QTabBar::tab {{ background: {SECONDARY}; color: {TEXT_MUTED};"
            f" padding: 6px 16px; border: none;"
            f" border-bottom: 2px solid transparent; font-size: 12px; }}"
            f"QTabBar::tab:selected {{ color: {TEXT};"
            f" border-bottom: 2px solid {ACCENT}; }}"
            f"QTabBar::tab:hover {{ background: {HOVER}; }}"
        )

        self._notif_tab = _NotificationsTab(
            manager,
            on_read_change=lambda: self.read_state_changed.emit(),
        )
        self._rules_tab = _RulesTab(manager, config)

        self._tabs.addTab(self._notif_tab, "Notifications")
        self._tabs.addTab(self._rules_tab, "Rules")

        layout.addWidget(self._tabs)

    def showEvent(self, event):
        super().showEvent(event)
        self._notif_tab.refresh()

    def refresh(self):
        """Refresh the notifications list (called when new notifications arrive)."""
        if self.isVisible():
            self._notif_tab.refresh()
