"""EventExplorerDialog — browse EventBus events and their data fields."""

from __future__ import annotations

import json
from typing import Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QSplitter, QLineEdit, QGroupBox, QTextEdit, QCheckBox, QWidget,
    QSizePolicy, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont

# ---------------------------------------------------------------------------
# Event manifest — static documentation of known events and their fields
# ---------------------------------------------------------------------------

# Each entry: (event_string, display_name, description, fields)
# fields: list of (key, type_hint, description)
_MANIFEST: list[tuple[str, str, str, list[tuple[str, str, str]]]] = [
    # ── Chat parser ─────────────────────────────────────────────────────────
    ("skill_gain", "Skill Gain",
     "A skill has increased.",
     [
         ("skill_name",    "str",   "Skill name (e.g. 'Combat Sense')"),
         ("amount",        "float", "Experience gained"),
         ("is_attribute",  "bool",  "True if attribute/general (short format)"),
         ("timestamp",     "datetime", "When the gain occurred"),
     ]),
    ("combat", "Combat",
     "A combat event was parsed from chat (hit, miss, critical).",
     [
         ("attacker",   "str",   "Name of the attacker"),
         ("target",     "str",   "Name of the target"),
         ("damage",     "float", "Damage dealt (0 on miss)"),
         ("critical",   "bool",  "True if critical hit"),
         ("miss",       "bool",  "True if missed"),
     ]),
    ("loot_group", "Loot Group",
     "A loot group was completed (all items from one drop).",
     [
         ("total_ped",  "float", "Total PED value of this drop"),
         ("items",      "list",  "List of loot item dicts"),
         ("mob",        "str",   "Mob name (if known)"),
         ("global_",    "bool",  "True if this was a global loot"),
     ]),
    ("enhancer_break", "Enhancer Break",
     "An enhancer broke during use.",
     [
         ("enhancer",   "str",   "Enhancer name"),
         ("slot",       "int",   "Slot number"),
     ]),
    ("tier_increase", "Tier Increase",
     "An item tiered up.",
     [
         ("item",       "str",   "Item name"),
         ("tier",       "int",   "New tier"),
     ]),
    ("global_", "Global Event",
     "A global/HOF announcement was parsed.",
     [
         ("player",     "str",   "Player who got the global"),
         ("mob",        "str",   "Mob or item name"),
         ("ped",        "float", "PED value"),
         ("hof",        "bool",  "True if Hall of Fame"),
         ("location",   "str",   "Planet/location string"),
     ]),
    ("player_death", "Player Death",
     "The local player was killed.",
     [
         ("mob",        "str",   "Mob that killed the player"),
         ("maturity",   "str",   "Mob maturity"),
     ]),
    ("player_revived", "Player Revived",
     "The local player was revived.",
     []),

    # ── Hunt tracking ────────────────────────────────────────────────────────
    ("hunt_session_started", "Hunt Session Started",
     "A hunt session was started.",
     [
         ("session_id", "str",   "Unique session identifier"),
         ("mob",        "str",   "Target mob name"),
         ("started_at", "float", "Unix timestamp"),
     ]),
    ("hunt_session_stopped", "Hunt Session Stopped",
     "The current hunt session ended.",
     [
         ("session_id", "str",   "Session identifier"),
         ("duration_s", "float", "Duration in seconds"),
     ]),
    ("hunt_session_updated", "Hunt Session Updated",
     "Session stats changed (periodic or on kill/loot).",
     [
         ("total_cost",  "float", "Total cost (ammo + decay) in PED"),
         ("total_loot",  "float", "Total loot in PED"),
         ("kills",       "int",   "Kill count"),
         ("returns_pct", "float", "Return percentage (loot / cost × 100)"),
     ]),
    ("hunt_encounter_started", "Encounter Started",
     "A new mob encounter began.",
     [
         ("mob",        "str",   "Mob name"),
         ("maturity",   "str",   "Mob maturity"),
     ]),
    ("hunt_encounter_ended", "Encounter Ended",
     "An encounter was resolved (kill or timeout).",
     [
         ("mob",        "str",   "Mob name"),
         ("outcome",    "str",   "'kill' | 'timeout' | 'death'"),
         ("loot_ped",   "float", "Loot received in PED"),
         ("cost_ped",   "float", "Ammo + decay spent in PED"),
     ]),
    ("mob_target_changed", "Mob Target Changed",
     "The locked target (OCR) changed.",
     [
         ("name",       "str",   "Mob display name"),
         ("maturity",   "str",   "Maturity string"),
         ("hp_pct",     "float", "HP percentage (0–100)"),
     ]),

    # ── OCR ─────────────────────────────────────────────────────────────────
    ("skill_scanned", "Skill Scanned",
     "OCR completed a full skill scan.",
     [
         ("skills",     "dict",  "Mapping of skill name → value"),
         ("count",      "int",   "Number of skills detected"),
     ]),
    ("ocr_progress", "OCR Progress",
     "OCR scan is in progress.",
     [
         ("percent",    "int",   "Completion percentage (0–100)"),
         ("page",       "str",   "Current page label"),
     ]),

    # ── Target lock ──────────────────────────────────────────────────────────
    ("target_lock_update", "Target Lock Update",
     "Target lock OCR updated.",
     [
         ("name",       "str",   "Mob name"),
         ("maturity",   "str",   "Maturity string"),
         ("hp_pct",     "float", "HP percentage (0–100)"),
         ("shared",     "bool",  "Shared damage indicator"),
     ]),
    ("target_lock_lost", "Target Lock Lost",
     "Target lock was lost (no target detected).",
     []),

    # ── Market price ─────────────────────────────────────────────────────────
    ("market_price_scan", "Market Price Scan",
     "A market price was scanned.",
     [
         ("name",       "str",   "Item name"),
         ("price",      "float", "Price in PED"),
         ("qty",        "int",   "Quantity"),
         ("tier",       "int",   "Item tier"),
     ]),

    # ── Player status ────────────────────────────────────────────────────────
    ("player_status_update", "Player Status Update",
     "Player HP/status OCR updated.",
     [
         ("hp",         "float", "Current HP"),
         ("hp_max",     "float", "Maximum HP"),
         ("hp_pct",     "float", "HP percentage (0–100)"),
         ("reload_pct", "float", "Reload progress percentage"),
     ]),

    # ── Radar ────────────────────────────────────────────────────────────────
    ("radar_coordinates", "Radar Coordinates",
     "Radar detected player coordinates.",
     [
         ("lon",        "float", "Longitude"),
         ("lat",        "float", "Latitude"),
         ("confidence", "float", "Detection confidence (0–1)"),
     ]),

    # ── Notifications / ingestion ────────────────────────────────────────────
    ("notification", "Notification",
     "An in-app notification was dispatched.",
     [
         ("title",      "str",   "Notification title"),
         ("message",    "str",   "Notification body"),
         ("level",      "str",   "'info' | 'warning' | 'error'"),
     ]),
    ("ingested_global", "Ingested Global",
     "A global event was received via the ingestion service.",
     [
         ("player",     "str",   "Player name"),
         ("mob",        "str",   "Mob/item name"),
         ("ped",        "float", "PED value"),
         ("hof",        "bool",  "True if Hall of Fame"),
     ]),

    # ── Capture ──────────────────────────────────────────────────────────────
    ("own_global", "Own Global",
     "The local player got a global.",
     [
         ("ped",        "float", "PED value"),
         ("mob",        "str",   "Mob name"),
         ("hof",        "bool",  "True if HoF"),
     ]),
    ("recording_started", "Recording Started",
     "A clip recording session began.",
     []),
    ("recording_stopped", "Recording Stopped",
     "A clip recording session ended.",
     []),
]

# Build lookup by event string
_MANIFEST_MAP: dict[str, tuple] = {entry[0]: entry for entry in _MANIFEST}

_STYLE = """
    QDialog       { background: #1a1a2e; }
    QSplitter::handle { background: #333355; }
    QListWidget   { background: #141422; color: #cccccc; border: 1px solid #333355;
                    border-radius: 4px; font-size: 12px; }
    QListWidget::item:selected { background: #2a3a5a; color: #e0e0e0; }
    QListWidget::item:hover    { background: #1e2e46; }
    QTreeWidget   { background: #141422; color: #cccccc; border: 1px solid #333355;
                    border-radius: 4px; font-size: 11px; }
    QTreeWidget::item:selected { background: #2a3a5a; }
    QTreeWidget QHeaderView::section { background: #1e1e30; color: #888; border: none;
                    padding: 3px 6px; font-size: 10px; }
    QLabel        { color: #cccccc; font-size: 12px; background: transparent; }
    QLineEdit     { background: #252535; color: #e0e0e0; border: 1px solid #555;
                    border-radius: 4px; padding: 3px 6px; font-size: 12px; }
    QPushButton   { background: #333350; color: #e0e0e0; border: 1px solid #555;
                    border-radius: 4px; padding: 4px 12px; font-size: 12px; }
    QPushButton:hover   { background: #404060; }
    QPushButton:pressed { background: #252540; }
    QTextEdit     { background: #141422; color: #aaccaa; border: 1px solid #333355;
                    border-radius: 4px; font-size: 11px; font-family: monospace; }
    QCheckBox     { color: #cccccc; font-size: 12px; }
    QGroupBox     { color: #00ccff; border: 1px solid #333355; border-radius: 4px;
                    margin-top: 8px; padding-top: 6px; font-size: 11px; }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; top: 2px; }
"""


def _format_value(v: Any) -> str:
    """Format a value for display in the live capture panel."""
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False, default=str)[:200]
    if isinstance(v, (list, tuple)):
        return json.dumps(v, ensure_ascii=False, default=str)[:200]
    return repr(v)


class EventExplorerDialog(QDialog):
    """Browse EventBus events, see their fields, and optionally capture live data.

    On accept, ``selected_event`` and ``selected_field`` hold the chosen values.
    """

    def __init__(self, event_bus=None, initial_event: str = "", initial_field: str = "", parent=None):
        super().__init__(parent)
        self._event_bus = event_bus
        self._live_sub  = None       # current live subscription callback
        self._live_event: str = ""   # event we're subscribed to
        self._live_items: list[dict] = []
        self._live_timer = QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.timeout.connect(self._flush_live)

        self.selected_event: str = initial_event
        self.selected_field: str = initial_field

        self.setWindowTitle("Event Explorer")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(760, 560)

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Search bar ───────────────────────────────────────────────────────
        search_row = QHBoxLayout()
        search_lbl = QLabel("🔍")
        search_lbl.setFixedWidth(20)
        search_row.addWidget(search_lbl)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter events…")
        self._search.textChanged.connect(self._apply_filter)
        search_row.addWidget(self._search)
        root.addLayout(search_row)

        # ── Main splitter (event list | detail panel) ────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        # Left: event list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        list_lbl = QLabel("Events")
        list_lbl.setStyleSheet("color: #888; font-size: 10px;")
        left_layout.addWidget(list_lbl)
        self._event_list = QListWidget()
        self._event_list.setSortingEnabled(False)
        self._event_list.currentItemChanged.connect(self._on_event_selected)
        left_layout.addWidget(self._event_list)
        splitter.addWidget(left)

        # Right: detail panel
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # Event name + description
        self._detail_name = QLabel("")
        self._detail_name.setStyleSheet(
            "color: #00ccff; font-size: 14px; font-weight: bold;"
        )
        self._detail_name.setWordWrap(True)
        self._detail_desc = QLabel("")
        self._detail_desc.setWordWrap(True)
        self._detail_desc.setStyleSheet("color: #aaaacc; font-size: 11px;")
        right_layout.addWidget(self._detail_name)
        right_layout.addWidget(self._detail_desc)

        # Event string (copyable)
        ev_row = QHBoxLayout()
        ev_lbl = QLabel("Event string:")
        ev_lbl.setStyleSheet("color: #888; font-size: 10px;")
        self._ev_string_lbl = QLabel("")
        self._ev_string_lbl.setStyleSheet(
            "color: #e0e0e0; font-family: monospace; font-size: 11px;"
            " background: #252535; border-radius: 3px; padding: 2px 6px;"
        )
        ev_row.addWidget(ev_lbl)
        ev_row.addWidget(self._ev_string_lbl)
        ev_row.addStretch()
        right_layout.addLayout(ev_row)

        # Known fields tree
        fields_lbl = QLabel("Known fields")
        fields_lbl.setStyleSheet("color: #888; font-size: 10px; margin-top: 4px;")
        right_layout.addWidget(fields_lbl)

        self._fields_tree = QTreeWidget()
        self._fields_tree.setHeaderLabels(["Field", "Type", "Description"])
        self._fields_tree.setColumnWidth(0, 130)
        self._fields_tree.setColumnWidth(1, 70)
        self._fields_tree.setRootIsDecorated(False)
        self._fields_tree.setAlternatingRowColors(True)
        self._fields_tree.setMaximumHeight(160)
        self._fields_tree.itemClicked.connect(self._on_field_clicked)
        right_layout.addWidget(self._fields_tree)

        # Selected field indicator
        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("Selected:"))
        self._sel_event_lbl = QLabel("—")
        self._sel_event_lbl.setStyleSheet(
            "color: #00ccff; font-family: monospace; font-size: 11px;"
            " background: #1a2a40; border-radius: 3px; padding: 2px 6px;"
        )
        self._sel_field_lbl = QLabel("—")
        self._sel_field_lbl.setStyleSheet(
            "color: #aaddaa; font-family: monospace; font-size: 11px;"
            " background: #1a2a1a; border-radius: 3px; padding: 2px 6px;"
        )
        sel_row.addWidget(self._sel_event_lbl)
        dot_lbl = QLabel("·")
        dot_lbl.setStyleSheet("color: #666;")
        sel_row.addWidget(dot_lbl)
        sel_row.addWidget(self._sel_field_lbl)
        sel_row.addStretch()
        right_layout.addLayout(sel_row)

        # Live capture section
        if self._event_bus is not None:
            live_group = QGroupBox("Live Capture")
            live_layout = QVBoxLayout(live_group)
            live_layout.setSpacing(4)

            live_ctrl = QHBoxLayout()
            self._live_check = QCheckBox("Subscribe to selected event")
            self._live_check.stateChanged.connect(self._on_live_toggled)
            live_ctrl.addWidget(self._live_check)
            live_ctrl.addStretch()
            clear_btn = QPushButton("Clear")
            clear_btn.setFixedHeight(22)
            clear_btn.clicked.connect(self._clear_live)
            live_ctrl.addWidget(clear_btn)
            live_layout.addLayout(live_ctrl)

            self._live_hint = QLabel(
                "Enable to see real event data. Trigger an in-game action to capture."
            )
            self._live_hint.setStyleSheet("color: #666688; font-size: 10px;")
            self._live_hint.setWordWrap(True)
            live_layout.addWidget(self._live_hint)

            self._live_log = QTextEdit()
            self._live_log.setReadOnly(True)
            self._live_log.setMaximumHeight(130)
            self._live_log.setPlaceholderText("Waiting for events…")
            live_layout.addWidget(self._live_log)

            right_layout.addWidget(live_group)
        else:
            self._live_check = None
            self._live_log   = None

        right_layout.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([220, 520])
        root.addWidget(splitter, 1)

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        use_btn = QPushButton("Use Selected")
        use_btn.setStyleSheet(
            "QPushButton { background: #305090; border-color: #4070b0; }"
            "QPushButton:hover { background: #3a60a8; }"
        )
        use_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(use_btn)
        root.addLayout(btn_row)

        # Populate list
        self._populate_list()

        # Restore initial selection
        if initial_event:
            self._select_event_str(initial_event)
            if initial_field:
                self.selected_field = initial_field
                self._sel_field_lbl.setText(initial_field or "—")

    # ── Event list ───────────────────────────────────────────────────────────

    def _populate_list(self) -> None:
        self._event_list.clear()
        q = self._search.text().lower().strip()
        for event_str, display, desc, fields in _MANIFEST:
            if q and q not in event_str.lower() and q not in display.lower():
                continue
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, event_str)
            item.setToolTip(f"{event_str}\n{desc}")
            self._event_list.addItem(item)

    def _apply_filter(self) -> None:
        self._populate_list()

    def _select_event_str(self, event_str: str) -> None:
        for i in range(self._event_list.count()):
            item = self._event_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == event_str:
                self._event_list.setCurrentItem(item)
                return

    # ── Event detail ─────────────────────────────────────────────────────────

    def _on_event_selected(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            return
        event_str = current.data(Qt.ItemDataRole.UserRole)
        self.selected_event = event_str
        self._sel_event_lbl.setText(event_str)

        entry = _MANIFEST_MAP.get(event_str)
        if entry:
            _, display, desc, fields = entry
            self._detail_name.setText(display)
            self._detail_desc.setText(desc)
            self._ev_string_lbl.setText(f'"{event_str}"')
            self._populate_fields(fields)
        else:
            self._detail_name.setText(event_str)
            self._detail_desc.setText("")
            self._ev_string_lbl.setText(f'"{event_str}"')
            self._populate_fields([])

        # Update live subscription
        if self._live_check and self._live_check.isChecked():
            self._stop_live()
            self._start_live(event_str)

    def _populate_fields(self, fields: list[tuple[str, str, str]]) -> None:
        self._fields_tree.clear()
        if not fields:
            no_item = QTreeWidgetItem(["(none documented)", "", ""])
            no_item.setForeground(0, QColor("#666688"))
            self._fields_tree.addTopLevelItem(no_item)
            return
        for key, type_hint, desc in fields:
            item = QTreeWidgetItem([key, type_hint, desc])
            item.setForeground(0, QColor("#aaddaa"))
            item.setForeground(1, QColor("#8888cc"))
            self._fields_tree.addTopLevelItem(item)
        self._fields_tree.resizeColumnToContents(0)

    def _on_field_clicked(self, item: QTreeWidgetItem, col: int) -> None:
        key = item.text(0)
        if key.startswith("("):
            return
        self.selected_field = key
        self._sel_field_lbl.setText(key)

    # ── Live capture ─────────────────────────────────────────────────────────

    def _on_live_toggled(self, state: int) -> None:
        if state == Qt.CheckState.Checked.value:
            self._start_live(self.selected_event)
        else:
            self._stop_live()

    def _start_live(self, event_str: str) -> None:
        if not event_str or self._event_bus is None:
            return
        self._stop_live()
        self._live_event = event_str

        def _cb(data):
            self._live_items.append(data)
            # Batch updates: flush after 200ms to avoid flooding
            if not self._live_timer.isActive():
                self._live_timer.start(200)

        self._live_sub = _cb
        self._event_bus.subscribe(event_str, _cb)
        if self._live_log:
            self._live_log.append(f"<span style='color:#666688'>Subscribed to \"{event_str}\"</span>")

    def _stop_live(self) -> None:
        if self._live_sub and self._live_event and self._event_bus:
            try:
                self._event_bus.unsubscribe(self._live_event, self._live_sub)
            except Exception:
                pass
        self._live_sub = None
        self._live_event = ""

    def _flush_live(self) -> None:
        if not self._live_log:
            return
        items, self._live_items = self._live_items, []
        for data in items:
            if isinstance(data, dict):
                lines = []
                for k, v in data.items():
                    lines.append(
                        f"<span style='color:#aaddaa'>{k}</span>"
                        f"<span style='color:#888'> = </span>"
                        f"<span style='color:#ddcc88'>{_format_value(v)}</span>"
                    )
                self._live_log.append("<br>".join(lines) + "<hr style='border-color:#333'>")
            else:
                self._live_log.append(
                    f"<span style='color:#ddcc88'>{_format_value(data)}</span>"
                    "<hr style='border-color:#333'>"
                )
            # Also add unknown keys to field tree
            if isinstance(data, dict):
                self._merge_live_fields(data)
        # Auto-scroll to bottom
        sb = self._live_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _merge_live_fields(self, data: dict) -> None:
        """Add any new keys from live data to the fields tree (marked as live)."""
        existing_keys = set()
        for i in range(self._fields_tree.topLevelItemCount()):
            item = self._fields_tree.topLevelItem(i)
            if item:
                existing_keys.add(item.text(0))

        for key, val in data.items():
            if key in existing_keys or key.startswith("("):
                continue
            type_hint = type(val).__name__
            item = QTreeWidgetItem([key, type_hint, "(detected live)"])
            item.setForeground(0, QColor("#ddaa44"))
            item.setForeground(1, QColor("#8888cc"))
            item.setForeground(2, QColor("#666644"))
            self._fields_tree.addTopLevelItem(item)
            existing_keys.add(key)

    def _clear_live(self) -> None:
        if self._live_log:
            self._live_log.clear()

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._stop_live()
        super().closeEvent(event)

    def reject(self):
        self._stop_live()
        super().reject()
