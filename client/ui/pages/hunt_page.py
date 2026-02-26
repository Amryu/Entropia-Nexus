"""Hunt page — tabbed interface for hunt tracking, analytics, history, and settings."""

import math
import uuid
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QTabWidget, QSpinBox, QDoubleSpinBox,
    QTreeWidget, QTreeWidgetItem, QScrollArea, QMessageBox,
    QTextEdit, QComboBox, QLineEdit,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ...core.constants import (
    EVENT_HUNT_SESSION_STARTED, EVENT_HUNT_SESSION_STOPPED,
    EVENT_HUNT_END_REQUESTED, EVENT_LOOT_BLACKLIST_CHANGED,
)


class HuntPage(QWidget):
    """Hunt tracker with tabbed interface: Current Hunt, Session, Analytics, Overlay, History, Settings."""

    MULTI_MOB_MULTIPLIER_COL = 4  # column index for Multiplier in kill log
    GLOBAL_COL = 5               # column index for Global marker in kill log
    GLOBAL_CORRELATION_WINDOW = timedelta(seconds=10)

    def __init__(self, *, signals, db, event_bus, config, config_path):
        super().__init__()
        self._signals = signals
        self._db = db
        self._event_bus = event_bus
        self._config = config
        self._config_path = config_path
        self._active_session_id = None
        self._session_start_time: datetime | None = None

        # Current Hunt tab state
        self._hunt_encounters: list[dict] = []
        self._hunt_is_multi_mob: bool = False
        self._markup_pct: float = config.hunt_markup_pct
        self._last_hunt_data: dict | None = None  # cached for markup recomputation
        self._selected_encounter_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(6)

        # Tab widget
        self._tabs = QTabWidget()
        self._build_current_hunt_tab()
        self._build_session_tab()
        self._build_analytics_tab()
        self._build_overlay_tab()
        self._build_history_tab()
        self._build_settings_tab()
        layout.addWidget(self._tabs, 1)

        # Connect signals
        signals.hunt_session_started.connect(self._on_session_started)
        signals.hunt_session_stopped.connect(self._on_session_stopped)
        signals.hunt_session_updated.connect(self._on_session_updated)
        signals.hunt_encounter_ended.connect(self._on_encounter_ended)
        signals.mob_target_changed.connect(self._on_mob_changed)
        signals.hunt_started.connect(self._on_hunt_started)
        signals.hunt_ended.connect(self._on_hunt_ended)
        signals.hunt_split.connect(self._on_hunt_split)
        signals.session_auto_timeout.connect(self._on_auto_timeout)
        signals.global_event.connect(self._on_global_event)

    # ------------------------------------------------------------------ #
    #  Tab 1: Current Session                                              #
    # ------------------------------------------------------------------ #

    def _build_session_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Controls
        controls = QHBoxLayout()

        self._stop_btn = QPushButton("Stop Session")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        controls.addWidget(self._stop_btn)

        self._end_hunt_btn = QPushButton("End Hunt")
        self._end_hunt_btn.setToolTip(
            "End the current hunt. A new hunt starts on the next kill."
        )
        self._end_hunt_btn.setEnabled(False)
        self._end_hunt_btn.clicked.connect(self._on_end_hunt)
        controls.addWidget(self._end_hunt_btn)

        controls.addStretch()
        layout.addLayout(controls)

        # Status
        self._status_label = QLabel("Session starts automatically on combat")
        layout.addWidget(self._status_label)

        # Splitter: summary + hunt tree + encounter table
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Session summary
        summary_group = QGroupBox("Session Summary")
        summary_layout = QHBoxLayout(summary_group)
        self._summary_labels = {}
        for name in ["Kills", "Hunts", "Cost", "Loot Total",
                      "Return %", "DPP", "Kills/h"]:
            col = QVBoxLayout()
            title = QLabel(name)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(title)
            val = QLabel("-")
            val.setObjectName("summaryValue")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(val)
            summary_layout.addLayout(col)
            self._summary_labels[name] = val
        splitter.addWidget(summary_group)

        # Hunt tree — shows hunts and their encounters
        hunts_group = QGroupBox("Hunts")
        hunts_layout = QVBoxLayout(hunts_group)

        self._hunt_tree = QTreeWidget()
        self._hunt_tree.setHeaderLabels([
            "Hunt / Encounter", "Mob", "Kills", "Damage",
            "Loot (PED)", "Cost", "Return %"
        ])
        self._hunt_tree.setColumnCount(7)
        self._hunt_tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._hunt_tree.setRootIsDecorated(True)
        hunts_layout.addWidget(self._hunt_tree)
        splitter.addWidget(hunts_group)

        # Encounter table (flat, for all encounters)
        encounters_group = QGroupBox("All Encounters")
        encounters_layout = QVBoxLayout(encounters_group)

        self._encounter_table = QTableWidget()
        self._encounter_table.setColumnCount(9)
        self._encounter_table.setHorizontalHeaderLabels([
            "Mob", "Source", "Damage Dealt", "Damage Taken",
            "Shots", "Crits", "Loot (PED)", "Cost", "Confidence"
        ])
        self._encounter_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._encounter_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        encounters_layout.addWidget(self._encounter_table)
        splitter.addWidget(encounters_group)

        splitter.setSizes([100, 200, 300])
        layout.addWidget(splitter, 1)

        self._tabs.addTab(tab, "Current Session")

    # ------------------------------------------------------------------ #
    #  Tab 2: Current Hunt                                                 #
    # ------------------------------------------------------------------ #

    def _build_current_hunt_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Markup row
        markup_row = QHBoxLayout()
        markup_row.addWidget(QLabel("Loot Markup:"))

        self._markup_spin = QDoubleSpinBox()
        self._markup_spin.setRange(100.0, 10000000.0)
        self._markup_spin.setDecimals(2)
        self._markup_spin.setValue(self._markup_pct)
        self._markup_spin.setSuffix(" %")
        self._markup_spin.setToolTip(
            "Markup applied to loot TT values.\n"
            "100% = no markup (TT value only).\n"
            "e.g. 135% means loot is worth 35% above TT."
        )
        self._markup_spin.valueChanged.connect(self._on_markup_changed)
        markup_row.addWidget(self._markup_spin)

        self._markup_source_label = QLabel("Custom" if self._markup_pct != 100.0 else "Default")
        self._markup_source_label.setObjectName("mutedText")
        markup_row.addWidget(self._markup_source_label)
        markup_row.addStretch()
        layout.addLayout(markup_row)

        # Hunt summary cards
        hunt_summary_group = QGroupBox("Hunt Summary")
        hunt_summary_layout = QHBoxLayout(hunt_summary_group)
        self._hunt_summary_labels = {}
        for name in ["Kills", "Cost", "Loot (TT)", "Loot (MU)",
                      "TT Return", "MU Return", "DPP", "Kills/h",
                      "Globals", "HoFs"]:
            col = QVBoxLayout()
            title = QLabel(name)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(title)
            val = QLabel("-")
            val.setObjectName("summaryValue")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(val)
            hunt_summary_layout.addLayout(col)
            self._hunt_summary_labels[name] = val
        layout.addWidget(hunt_summary_group)

        # Last kill section
        last_kill_group = QGroupBox("Last Kill")
        last_kill_layout = QHBoxLayout(last_kill_group)
        self._last_kill_labels = {}
        for name in ["Mob", "Cost", "Loot (TT)", "Loot (MU)", "Multiplier"]:
            col = QVBoxLayout()
            title = QLabel(name)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(title)
            val = QLabel("-")
            val.setObjectName("summaryValue")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(val)
            last_kill_layout.addLayout(col)
            self._last_kill_labels[name] = val
        layout.addWidget(last_kill_group)

        # Kill log table
        kill_log_group = QGroupBox("Kill Log")
        kill_log_layout = QVBoxLayout(kill_log_group)

        self._kill_log_table = QTableWidget()
        self._kill_log_table.setColumnCount(6)
        self._kill_log_table.setHorizontalHeaderLabels([
            "#", "Mob", "Loot (TT)", "Cost", "Multiplier", "Global"
        ])
        self._kill_log_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._kill_log_table.setColumnWidth(self.GLOBAL_COL, 50)
        self._kill_log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._kill_log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._kill_log_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._kill_log_table.currentCellChanged.connect(self._on_kill_selected)
        kill_log_layout.addWidget(self._kill_log_table)

        # Kill detail panel (shown on click)
        self._detail_group = QGroupBox("Kill Details")
        self._detail_group.setVisible(False)
        detail_layout = QVBoxLayout(self._detail_group)

        # Tool breakdown table
        detail_layout.addWidget(QLabel("Tool Breakdown"))
        self._tool_detail_table = QTableWidget()
        self._tool_detail_table.setColumnCount(4)
        self._tool_detail_table.setHorizontalHeaderLabels(["Tool", "Shots", "Damage", "Crits"])
        self._tool_detail_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._tool_detail_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tool_detail_table.setMaximumHeight(120)
        detail_layout.addWidget(self._tool_detail_table)

        # Loot items table
        detail_layout.addWidget(QLabel("Loot Items"))
        self._loot_items_table = QTableWidget()
        self._loot_items_table.setColumnCount(5)
        self._loot_items_table.setHorizontalHeaderLabels([
            "Item", "Qty", "Value (PED)", "Status", "Loot Table"
        ])
        self._loot_items_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._loot_items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._loot_items_table.setMaximumHeight(150)
        detail_layout.addWidget(self._loot_items_table)

        # Combat log table
        detail_layout.addWidget(QLabel("Combat Log"))
        self._combat_log_table = QTableWidget()
        self._combat_log_table.setColumnCount(4)
        self._combat_log_table.setHorizontalHeaderLabels(["Time", "Event", "Amount", "Tool"])
        self._combat_log_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._combat_log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._combat_log_table.setMaximumHeight(200)
        detail_layout.addWidget(self._combat_log_table)

        kill_log_layout.addWidget(self._detail_group)
        layout.addWidget(kill_log_group, 1)

        self._tabs.addTab(tab, "Current Hunt")

    # ------------------------------------------------------------------ #
    #  Tab 3: Analytics                                                    #
    # ------------------------------------------------------------------ #

    def _build_analytics_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Per-hunt analytics table
        self._analytics_table = QTableWidget()
        self._analytics_table.setColumnCount(8)
        self._analytics_table.setHorizontalHeaderLabels([
            "Hunt", "Mob", "Kills", "DPS", "Cost/Kill",
            "Return %", "Kill Rate (/hr)", "Tools Used"
        ])
        self._analytics_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._analytics_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        content_layout.addWidget(QLabel("Per-Hunt Statistics"))
        content_layout.addWidget(self._analytics_table)

        # Tool usage breakdown
        self._tool_table = QTableWidget()
        self._tool_table.setColumnCount(4)
        self._tool_table.setHorizontalHeaderLabels([
            "Tool", "Shots", "Damage", "Crits"
        ])
        self._tool_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._tool_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        content_layout.addWidget(QLabel("Tool Usage Breakdown"))
        content_layout.addWidget(self._tool_table)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        self._tabs.addTab(tab, "Analytics")

    # ------------------------------------------------------------------ #
    #  Tab 4: Overlay Configuration                                        #
    # ------------------------------------------------------------------ #

    def _build_overlay_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("Configure which stats appear in the hunt overlay."))

        # Placeholder — overlay field toggles
        overlay_group = QGroupBox("Overlay Fields")
        overlay_layout = QVBoxLayout(overlay_group)
        overlay_layout.addWidget(QLabel("Overlay configuration coming soon."))
        overlay_layout.addWidget(QLabel("Position and opacity can be adjusted in Settings."))
        overlay_layout.addStretch()
        layout.addWidget(overlay_group)

        layout.addStretch()
        self._tabs.addTab(tab, "Overlay")

    # ------------------------------------------------------------------ #
    #  Tab 5: History                                                      #
    # ------------------------------------------------------------------ #

    def _build_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Controls
        history_controls = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_history)
        history_controls.addWidget(refresh_btn)

        self._merge_btn = QPushButton("Merge Hunts")
        self._merge_btn.setEnabled(False)
        self._merge_btn.clicked.connect(self._on_merge_hunts)
        history_controls.addWidget(self._merge_btn)

        self._split_btn = QPushButton("Split Hunt")
        self._split_btn.setEnabled(False)
        self._split_btn.clicked.connect(self._on_split_hunt)
        history_controls.addWidget(self._split_btn)

        self._delete_btn = QPushButton("Delete Session")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete_session)
        history_controls.addWidget(self._delete_btn)

        history_controls.addStretch()
        layout.addLayout(history_controls)

        # History tree: sessions > hunts > encounters
        self._history_tree = QTreeWidget()
        self._history_tree.setHeaderLabels([
            "Session / Hunt / Encounter", "Mob", "Kills",
            "Damage", "Loot (PED)", "Start", "End"
        ])
        self._history_tree.setColumnCount(7)
        self._history_tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._history_tree.setRootIsDecorated(True)
        self._history_tree.itemSelectionChanged.connect(self._on_history_selection_changed)
        layout.addWidget(self._history_tree, 1)

        self._tabs.addTab(tab, "History")

    # ------------------------------------------------------------------ #
    #  Tab 6: Settings                                                     #
    # ------------------------------------------------------------------ #

    def _build_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Session auto-timeout
        timeout_group = QGroupBox("Session Auto-Timeout")
        timeout_layout = QHBoxLayout(timeout_group)
        timeout_layout.addWidget(QLabel("End session after inactivity (minutes):"))
        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(5, 480)
        self._timeout_spin.setValue(self._config.session_auto_timeout_ms // 60000)
        self._timeout_spin.setSuffix(" min")
        self._timeout_spin.valueChanged.connect(self._on_timeout_changed)
        timeout_layout.addWidget(self._timeout_spin)
        timeout_layout.addStretch()
        layout.addWidget(timeout_group)

        # Hunt detection
        detection_group = QGroupBox("Hunt Detection")
        detection_layout = QVBoxLayout(detection_group)

        mob_row = QHBoxLayout()
        mob_row.addWidget(QLabel("Mob type change threshold (kills):"))
        self._mob_threshold_spin = QSpinBox()
        self._mob_threshold_spin.setRange(3, 50)
        self._mob_threshold_spin.setValue(self._config.hunt_split_mob_threshold)
        self._mob_threshold_spin.setToolTip(
            "Number of consecutive kills of a new mob type before a hunt split.\n"
            "Mixed spawns (multiple mobs interleaving) never trigger splits."
        )
        self._mob_threshold_spin.valueChanged.connect(self._on_mob_threshold_changed)
        mob_row.addWidget(self._mob_threshold_spin)
        mob_row.addStretch()
        detection_layout.addLayout(mob_row)

        location_row = QHBoxLayout()
        location_row.addWidget(QLabel("Min kills at new location:"))
        self._location_kills_spin = QSpinBox()
        self._location_kills_spin.setRange(2, 30)
        self._location_kills_spin.setValue(self._config.hunt_split_min_remote_kills)
        self._location_kills_spin.setToolTip(
            "Minimum kills at a new location before confirming a location-based split."
        )
        self._location_kills_spin.valueChanged.connect(self._on_location_kills_changed)
        location_row.addWidget(self._location_kills_spin)
        location_row.addStretch()
        detection_layout.addLayout(location_row)

        layout.addWidget(detection_group)

        # Encounter timing
        timing_group = QGroupBox("Encounter Timing")
        timing_layout = QVBoxLayout(timing_group)

        close_row = QHBoxLayout()
        close_row.addWidget(QLabel("Encounter close timeout (seconds):"))
        self._close_timeout_spin = QSpinBox()
        self._close_timeout_spin.setRange(3, 120)
        self._close_timeout_spin.setValue(self._config.encounter_close_timeout_ms // 1000)
        self._close_timeout_spin.setSuffix(" s")
        self._close_timeout_spin.valueChanged.connect(self._on_close_timeout_changed)
        close_row.addWidget(self._close_timeout_spin)
        close_row.addStretch()
        timing_layout.addLayout(close_row)

        attr_row = QHBoxLayout()
        attr_row.addWidget(QLabel("Attribution window (seconds):"))
        self._attr_window_spin = QSpinBox()
        self._attr_window_spin.setRange(1, 30)
        self._attr_window_spin.setValue(self._config.attribution_window_ms // 1000)
        self._attr_window_spin.setSuffix(" s")
        self._attr_window_spin.valueChanged.connect(self._on_attr_window_changed)
        attr_row.addWidget(self._attr_window_spin)
        attr_row.addStretch()
        timing_layout.addLayout(attr_row)

        layout.addWidget(timing_group)

        # Loot blacklist editor — global
        blacklist_group = QGroupBox("Loot Blacklist")
        blacklist_layout = QVBoxLayout(blacklist_group)
        blacklist_layout.addWidget(QLabel(
            "Items listed here are never counted as loot (one per line).\n"
            "Built-in exclusions (e.g. Universal Ammo) are always applied."
        ))

        # Global blacklist
        blacklist_layout.addWidget(QLabel("Global (all mobs):"))
        self._blacklist_edit = QTextEdit()
        self._blacklist_edit.setPlainText(
            "\n".join(self._config.loot_blacklist)
        )
        self._blacklist_edit.setMaximumHeight(80)
        blacklist_layout.addWidget(self._blacklist_edit)

        # Per-mob blacklist
        blacklist_layout.addWidget(QLabel("Per-mob (select mob):"))
        mob_row = QHBoxLayout()
        self._blacklist_mob_combo = QComboBox()
        self._blacklist_mob_combo.setEditable(True)
        self._blacklist_mob_combo.setMinimumWidth(200)
        self._blacklist_mob_combo.setPlaceholderText("Type mob name...")
        self._blacklist_mob_combo.currentTextChanged.connect(
            self._on_blacklist_mob_changed
        )
        mob_row.addWidget(self._blacklist_mob_combo)
        mob_row.addStretch()
        blacklist_layout.addLayout(mob_row)

        self._blacklist_mob_edit = QTextEdit()
        self._blacklist_mob_edit.setPlaceholderText(
            "Items blacklisted only for this mob (one per line)"
        )
        self._blacklist_mob_edit.setMaximumHeight(80)
        blacklist_layout.addWidget(self._blacklist_mob_edit)

        # Populate mob combo from existing per-mob config
        for mob_name in sorted(self._config.loot_blacklist_per_mob.keys()):
            self._blacklist_mob_combo.addItem(mob_name)

        save_blacklist_btn = QPushButton("Save Blacklist")
        save_blacklist_btn.clicked.connect(self._on_save_blacklist)
        blacklist_layout.addWidget(save_blacklist_btn)

        layout.addWidget(blacklist_group)

        layout.addStretch()
        self._tabs.addTab(tab, "Settings")

    # ------------------------------------------------------------------ #
    #  Session controls                                                    #
    # ------------------------------------------------------------------ #

    def _on_stop(self):
        self._event_bus.publish(EVENT_HUNT_SESSION_STOPPED, {
            "session_id": self._active_session_id,
        })

    def _on_end_hunt(self):
        """Manually end the current hunt. A new hunt starts on the next kill."""
        self._event_bus.publish(EVENT_HUNT_END_REQUESTED, {
            "session_id": self._active_session_id,
        })

    # ------------------------------------------------------------------ #
    #  Signal handlers — session                                           #
    # ------------------------------------------------------------------ #

    def _on_session_started(self, data):
        self._active_session_id = data.get("session_id") if isinstance(data, dict) else None
        self._session_start_time = datetime.utcnow()
        self._stop_btn.setEnabled(True)
        self._end_hunt_btn.setEnabled(True)
        self._status_label.setText("Hunt in progress...")
        self._encounter_table.setRowCount(0)
        self._hunt_tree.clear()
        for label in self._summary_labels.values():
            label.setText("0")

        # Reset current hunt tab
        self._reset_current_hunt()

    def _on_session_stopped(self, data):
        self._active_session_id = None
        self._session_start_time = None
        self._stop_btn.setEnabled(False)
        self._end_hunt_btn.setEnabled(False)
        self._status_label.setText("Session starts automatically on combat")

    def _on_session_updated(self, data):
        if not isinstance(data, dict):
            return

        kills = data.get("kills", 0)
        cost = data.get("total_cost", 0)
        loot = data.get("loot_total", 0)
        damage_dealt = data.get("damage_dealt", 0)

        self._summary_labels["Kills"].setText(str(kills))
        self._summary_labels["Hunts"].setText(str(data.get("hunt_count", 0)))
        self._summary_labels["Cost"].setText(f"{cost:.2f}" if cost > 0 else "-")
        self._summary_labels["Loot Total"].setText(f"{loot:.2f}")
        self._summary_labels["Return %"].setText(
            f"{(loot / cost) * 100:.1f}%" if cost > 0 else "-"
        )
        self._summary_labels["DPP"].setText(
            f"{damage_dealt / cost:.1f}" if cost > 0 else "-"
        )

        # Kills/h — compute from session start
        if self._session_start_time and kills > 0:
            elapsed_h = (datetime.utcnow() - self._session_start_time).total_seconds() / 3600
            self._summary_labels["Kills/h"].setText(
                f"{kills / elapsed_h:.0f}" if elapsed_h > 0 else "-"
            )
        else:
            self._summary_labels["Kills/h"].setText("-")

        # Update hunt tree from summary data
        hunts = data.get("hunts", [])
        self._update_hunt_tree(hunts)

        # Update current hunt summary from the last hunt in the list
        if hunts:
            self._update_hunt_summary(hunts[-1])

    def _update_hunt_tree(self, hunts: list):
        """Rebuild the hunt tree from session summary data."""
        self._hunt_tree.clear()
        for i, hunt in enumerate(hunts):
            hunt_item = QTreeWidgetItem([
                f"Hunt {i + 1}",
                hunt.get("primary_mob", "?"),
                str(hunt.get("kill_count", 0)),
                f"{hunt.get('damage_dealt', 0):.1f}",
                f"{hunt.get('loot_total', 0):.2f}",
                f"{hunt.get('cost', 0):.2f}" if hunt.get("cost", 0) > 0 else "-",
                f"{hunt.get('return_pct', 0):.1f}%" if hunt.get("return_pct") else "-",
            ])
            self._hunt_tree.addTopLevelItem(hunt_item)

    # ------------------------------------------------------------------ #
    #  Signal handlers — encounters and hunts                              #
    # ------------------------------------------------------------------ #

    def _on_encounter_ended(self, encounter):
        if not isinstance(encounter, dict):
            return

        # Session tab — encounter table
        row = self._encounter_table.rowCount()
        self._encounter_table.insertRow(row)
        self._encounter_table.setItem(row, 0, QTableWidgetItem(encounter.get("mob_name", "?")))
        self._encounter_table.setItem(row, 1, QTableWidgetItem(encounter.get("mob_name_source", "?")))
        self._encounter_table.setItem(row, 2, QTableWidgetItem(f"{encounter.get('damage_dealt', 0):.2f}"))
        self._encounter_table.setItem(row, 3, QTableWidgetItem(f"{encounter.get('damage_taken', 0):.2f}"))
        self._encounter_table.setItem(row, 4, QTableWidgetItem(str(encounter.get("shots_fired", 0))))
        self._encounter_table.setItem(row, 5, QTableWidgetItem(str(encounter.get("critical_hits", 0))))
        self._encounter_table.setItem(row, 6, QTableWidgetItem(f"{encounter.get('loot_total_ped', 0):.2f}"))
        cost = encounter.get("cost", 0)
        self._encounter_table.setItem(row, 7, QTableWidgetItem(f"{cost:.4f}" if cost > 0 else "-"))
        self._encounter_table.setItem(row, 8, QTableWidgetItem(f"{encounter.get('confidence', 1.0):.0%}"))

        # Current Hunt tab — accumulate encounter
        self._hunt_encounters.append(encounter)
        self._check_multi_mob()
        self._update_last_kill(encounter)
        self._update_kill_log()

    def _on_hunt_started(self, data):
        if isinstance(data, dict):
            mob = data.get("primary_mob", "Unknown")
            self._status_label.setText(f"Hunt started: {mob}")

        # Reset current hunt tab for the new hunt
        self._reset_current_hunt()

    def _on_hunt_ended(self, data):
        pass  # Tree is updated via session_updated

    def _on_hunt_split(self, data):
        if isinstance(data, dict):
            old_mob = data.get("old_mob", "?")
            new_mob = data.get("new_mob", "?")
            self._status_label.setText(f"Hunt split: {old_mob} -> {new_mob}")

    def _on_auto_timeout(self, data):
        self._status_label.setText("Session ended (auto-timeout)")
        self._on_session_stopped(data)

    def _on_mob_changed(self, data):
        if isinstance(data, dict):
            mob_name = data.get("mob_name", "")
            self._status_label.setText(f"Hunting: {mob_name}")

    # ------------------------------------------------------------------ #
    #  Current Hunt tab — helpers                                          #
    # ------------------------------------------------------------------ #

    def _reset_current_hunt(self):
        """Clear all current hunt tab state."""
        self._hunt_encounters.clear()
        self._hunt_is_multi_mob = False
        self._last_hunt_data = None
        self._selected_encounter_id = None

        for label in self._hunt_summary_labels.values():
            label.setText("-")
        for label in self._last_kill_labels.values():
            label.setText("-")
        self._kill_log_table.setRowCount(0)

        # Restore multiplier column visibility
        self._kill_log_table.setColumnHidden(self.MULTI_MOB_MULTIPLIER_COL, False)

        # Hide detail panel
        self._detail_group.setVisible(False)
        self._tool_detail_table.setRowCount(0)
        self._loot_items_table.setRowCount(0)
        self._combat_log_table.setRowCount(0)

    def _update_hunt_summary(self, hunt: dict):
        """Update the Current Hunt summary cards from hunt aggregate data."""
        self._last_hunt_data = hunt
        kills = hunt.get("kill_count", 0)
        loot_tt = hunt.get("loot_total", 0)
        cost = hunt.get("cost", 0)
        damage_dealt = hunt.get("damage_dealt", 0)

        loot_mu = loot_tt * (self._markup_pct / 100)
        tt_return = (loot_tt / cost * 100) if cost > 0 else None
        mu_return = (loot_mu / cost * 100) if cost > 0 else None
        dpp = (damage_dealt / cost) if cost > 0 else None

        self._hunt_summary_labels["Kills"].setText(str(kills))
        self._hunt_summary_labels["Cost"].setText(f"{cost:.2f}" if cost > 0 else "-")
        self._hunt_summary_labels["Loot (TT)"].setText(f"{loot_tt:.2f}")
        self._hunt_summary_labels["Loot (MU)"].setText(f"{loot_mu:.2f}")
        self._hunt_summary_labels["TT Return"].setText(
            f"{tt_return:.1f}%" if tt_return is not None else "-"
        )
        self._hunt_summary_labels["MU Return"].setText(
            f"{mu_return:.1f}%" if mu_return is not None else "-"
        )
        self._hunt_summary_labels["DPP"].setText(
            f"{dpp:.1f}" if dpp is not None else "-"
        )

        # Kills/h for the current hunt
        hunt_start = hunt.get("start_time")
        if hunt_start and kills > 0:
            try:
                start = datetime.fromisoformat(hunt_start)
                elapsed_h = (datetime.utcnow() - start).total_seconds() / 3600
                self._hunt_summary_labels["Kills/h"].setText(
                    f"{kills / elapsed_h:.0f}" if elapsed_h > 0 else "-"
                )
            except (ValueError, TypeError):
                self._hunt_summary_labels["Kills/h"].setText("-")
        else:
            self._hunt_summary_labels["Kills/h"].setText("-")

        self._hunt_summary_labels["Globals"].setText(str(hunt.get("global_count", 0)))
        self._hunt_summary_labels["HoFs"].setText(str(hunt.get("hof_count", 0)))

    def _update_last_kill(self, encounter: dict):
        """Update the last kill section from the most recent encounter."""
        mob = encounter.get("mob_name", "?")
        cost = encounter.get("cost", 0)
        loot_tt = encounter.get("loot_total_ped", 0)
        loot_mu = loot_tt * (self._markup_pct / 100)
        multiplier = (loot_tt / cost) if cost > 0 else None

        self._last_kill_labels["Mob"].setText(mob)
        self._last_kill_labels["Cost"].setText(f"{cost:.4f}" if cost > 0 else "-")
        self._last_kill_labels["Loot (TT)"].setText(f"{loot_tt:.2f}")
        self._last_kill_labels["Loot (MU)"].setText(f"{loot_mu:.2f}")

        if self._hunt_is_multi_mob:
            self._last_kill_labels["Multiplier"].setText("-")
        elif multiplier is not None:
            self._last_kill_labels["Multiplier"].setText(f"{multiplier:.2f}x")
        else:
            self._last_kill_labels["Multiplier"].setText("-")

    def _update_kill_log(self):
        """Rebuild the kill log table from accumulated encounters (newest first)."""
        self._kill_log_table.setRowCount(0)
        total = len(self._hunt_encounters)
        for i, enc in enumerate(reversed(self._hunt_encounters)):
            row = self._kill_log_table.rowCount()
            self._kill_log_table.insertRow(row)

            kill_num = total - i
            cost = enc.get("cost", 0)
            loot_tt = enc.get("loot_total_ped", 0)
            multiplier = (loot_tt / cost) if cost > 0 else None

            self._kill_log_table.setItem(row, 0, QTableWidgetItem(str(kill_num)))
            self._kill_log_table.setItem(row, 1, QTableWidgetItem(enc.get("mob_name", "?")))
            self._kill_log_table.setItem(row, 2, QTableWidgetItem(f"{loot_tt:.2f}"))
            self._kill_log_table.setItem(row, 3, QTableWidgetItem(
                f"{cost:.4f}" if cost > 0 else "-"
            ))
            self._kill_log_table.setItem(row, 4, QTableWidgetItem(
                f"{multiplier:.2f}x" if multiplier is not None else "-"
            ))

            # Global column
            global_marker = self._global_marker_text(enc)
            item = QTableWidgetItem(global_marker)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if global_marker:
                item.setForeground(QColor("#FFD700"))  # gold for globals
            self._kill_log_table.setItem(row, self.GLOBAL_COL, item)

    def _check_multi_mob(self):
        """Detect if the current hunt has mixed mob types."""
        mob_names = {enc.get("mob_name", "") for enc in self._hunt_encounters}
        was_multi = self._hunt_is_multi_mob
        self._hunt_is_multi_mob = len(mob_names) > 1

        if self._hunt_is_multi_mob != was_multi:
            # Toggle multiplier column visibility
            self._kill_log_table.setColumnHidden(
                self.MULTI_MOB_MULTIPLIER_COL, self._hunt_is_multi_mob
            )

    def _on_markup_changed(self, value):
        """Handle markup spinbox change — recompute all MU values."""
        self._markup_pct = value
        self._config.hunt_markup_pct = value
        self._save_config()

        # Update source label
        self._markup_source_label.setText(
            "Custom" if value != 100.0 else "Default"
        )

        # Recompute hunt summary with new markup
        if self._last_hunt_data:
            self._update_hunt_summary(self._last_hunt_data)

        # Recompute last kill MU values
        if self._hunt_encounters:
            self._update_last_kill(self._hunt_encounters[-1])

    @staticmethod
    def _global_marker_text(enc: dict) -> str:
        """Return display text for the Global column."""
        if enc.get("is_hof"):
            return "HoF"
        if enc.get("is_global"):
            return "G"
        return ""

    def _on_kill_selected(self, row, _col, _prev_row, _prev_col):
        """Handle click on a kill log row — show detail panel."""
        if row < 0 or row >= len(self._hunt_encounters):
            self._detail_group.setVisible(False)
            return

        # Kill log is newest-first; map row back to encounter index
        enc_index = len(self._hunt_encounters) - 1 - row
        enc = self._hunt_encounters[enc_index]
        enc_id = enc.get("id")
        self._selected_encounter_id = enc_id

        # Tool breakdown — from in-memory encounter data
        tool_stats = enc.get("tool_stats", {})
        self._tool_detail_table.setRowCount(0)
        for tool_name, stats in tool_stats.items():
            r = self._tool_detail_table.rowCount()
            self._tool_detail_table.insertRow(r)
            self._tool_detail_table.setItem(r, 0, QTableWidgetItem(tool_name))
            self._tool_detail_table.setItem(r, 1, QTableWidgetItem(str(stats.get("shots", 0))))
            self._tool_detail_table.setItem(r, 2, QTableWidgetItem(f"{stats.get('damage', 0):.2f}"))
            self._tool_detail_table.setItem(r, 3, QTableWidgetItem(str(stats.get("crits", 0))))

        # Loot items — from in-memory encounter data or DB fallback
        self._loot_items_table.setRowCount(0)
        loot_items = enc.get("loot_items", [])
        if not loot_items and enc_id:
            loot_items = self._db.get_encounter_loot_items(enc_id)
        for li in loot_items:
            r = self._loot_items_table.rowCount()
            self._loot_items_table.insertRow(r)

            name = li.get("item_name", "") if isinstance(li, dict) else getattr(li, "item_name", "")
            qty = li.get("quantity", 0) if isinstance(li, dict) else getattr(li, "quantity", 0)
            val = li.get("value_ped", 0) if isinstance(li, dict) else getattr(li, "value_ped", 0)
            blacklisted = li.get("is_blacklisted", False) if isinstance(li, dict) else getattr(li, "is_blacklisted", False)
            refining = li.get("is_refining_output", False) if isinstance(li, dict) else getattr(li, "is_refining_output", False)
            in_table = li.get("is_in_loot_table", True) if isinstance(li, dict) else getattr(li, "is_in_loot_table", True)

            # DB stores booleans as integers
            blacklisted = bool(blacklisted)
            refining = bool(refining)
            in_table = bool(in_table)

            self._loot_items_table.setItem(r, 0, QTableWidgetItem(name))
            self._loot_items_table.setItem(r, 1, QTableWidgetItem(str(qty)))
            self._loot_items_table.setItem(r, 2, QTableWidgetItem(f"{val:.2f}"))

            # Status column
            if blacklisted:
                status_item = QTableWidgetItem("Blacklisted")
                status_item.setForeground(QColor("#FF4444"))
            elif refining:
                status_item = QTableWidgetItem("Refining")
                status_item.setForeground(QColor("#FFA500"))
            else:
                status_item = QTableWidgetItem("Loot")
                status_item.setForeground(QColor("#44CC44"))
            self._loot_items_table.setItem(r, 3, status_item)

            # Loot table column
            if in_table:
                table_item = QTableWidgetItem("Yes")
            else:
                table_item = QTableWidgetItem("Unknown")
                table_item.setForeground(QColor("#FFD700"))
            self._loot_items_table.setItem(r, 4, table_item)

        # Combat log — fetch from DB if encounter has an id
        self._combat_log_table.setRowCount(0)
        if enc_id:
            events = self._db.get_encounter_combat_events(enc_id)
            for ev in events:
                r = self._combat_log_table.rowCount()
                self._combat_log_table.insertRow(r)
                ts = ev.get("timestamp", "")
                if isinstance(ts, str) and len(ts) > 19:
                    ts = ts[11:19]  # extract HH:MM:SS from ISO
                elif isinstance(ts, str) and len(ts) > 11:
                    ts = ts[11:19]
                self._combat_log_table.setItem(r, 0, QTableWidgetItem(str(ts)))
                self._combat_log_table.setItem(r, 1, QTableWidgetItem(ev.get("event_type", "")))
                amount = ev.get("amount", 0)
                self._combat_log_table.setItem(r, 2, QTableWidgetItem(
                    f"{amount:.2f}" if amount else "-"
                ))
                self._combat_log_table.setItem(r, 3, QTableWidgetItem(ev.get("tool_name") or "-"))

        self._detail_group.setVisible(True)

    def _on_global_event(self, data):
        """Handle global event signal — retroactively mark matching encounter in kill log."""
        if not self._active_session_id or not self._hunt_encounters:
            return

        # Only care about kill/team_kill globals
        global_type = getattr(data, "global_type", None)
        if global_type and hasattr(global_type, "value"):
            if global_type.value not in ("kill", "team_kill"):
                return

        target = getattr(data, "target_name", "") or ""
        value = getattr(data, "value", 0)
        is_hof = getattr(data, "is_hof", False) or getattr(data, "is_ath", False)
        now = datetime.utcnow()

        # Search recent encounters (most recent first) for a match
        for i in range(len(self._hunt_encounters) - 1, -1, -1):
            enc = self._hunt_encounters[i]

            # Check timing — only recent encounters
            end_time_str = enc.get("end_time")
            if end_time_str:
                try:
                    end_time = datetime.fromisoformat(end_time_str)
                    if (now - end_time) > self.GLOBAL_CORRELATION_WINDOW:
                        break  # older encounters won't match either
                except (ValueError, TypeError):
                    pass

            loot_ped = enc.get("loot_total_ped", 0)
            if loot_ped <= 0:
                continue

            mob_name = enc.get("mob_name", "")
            # Match: loot value (floored) == global value AND mob name overlap
            if math.floor(loot_ped) == value:
                if (target.lower() in mob_name.lower()
                        or mob_name.lower() in target.lower()):
                    enc["is_global"] = True
                    enc["is_hof"] = is_hof

                    # Update the kill log row for this encounter
                    # Kill log is newest-first: row = total - 1 - i
                    row = len(self._hunt_encounters) - 1 - i
                    if 0 <= row < self._kill_log_table.rowCount():
                        marker = self._global_marker_text(enc)
                        item = QTableWidgetItem(marker)
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        if marker:
                            item.setForeground(QColor("#FFD700"))
                        self._kill_log_table.setItem(row, self.GLOBAL_COL, item)
                    break

    # ------------------------------------------------------------------ #
    #  History tab                                                         #
    # ------------------------------------------------------------------ #

    def _load_history(self):
        """Load recent sessions from the database."""
        self._history_tree.clear()
        sessions = self._db.get_recent_sessions(limit=50)
        for sess in sessions:
            session_item = QTreeWidgetItem([
                f"Session: {sess['id'][:8]}...",
                sess.get("primary_mob", "-") or "-",
                "",
                "",
                "",
                sess.get("start_time", "")[:19],
                (sess.get("end_time") or "active")[:19],
            ])
            session_item.setData(0, Qt.ItemDataRole.UserRole, {
                "type": "session", "id": sess["id"]
            })

            # Load hunts for this session
            hunts = self._db.get_session_hunts(sess["id"])
            for i, hunt in enumerate(hunts):
                hunt_item = QTreeWidgetItem([
                    f"Hunt {i + 1}",
                    hunt.get("primary_mob", "-") or "-",
                    "",
                    "",
                    "",
                    hunt.get("start_time", "")[:19],
                    (hunt.get("end_time") or "")[:19],
                ])
                hunt_item.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "hunt", "id": hunt["id"],
                    "session_id": sess["id"],
                })

                # Load encounters for this hunt
                encounters = self._db.get_hunt_encounters(hunt["id"])
                for enc in encounters:
                    enc_item = QTreeWidgetItem([
                        enc.get("mob_name", "?"),
                        enc.get("mob_name_source", "?"),
                        "1",
                        f"{enc.get('damage_dealt', 0):.1f}",
                        f"{enc.get('loot_total_ped', 0):.2f}",
                        enc.get("start_time", "")[:19],
                        (enc.get("end_time") or "")[:19],
                    ])
                    hunt_item.addChild(enc_item)

                session_item.addChild(hunt_item)

            # Also load encounters without a hunt (from before the update)
            all_encounters = self._db.get_session_encounters(sess["id"])
            orphan_encounters = [e for e in all_encounters if not e.get("hunt_id")]
            if orphan_encounters:
                orphan_item = QTreeWidgetItem(["Ungrouped Encounters", "", "", "", "", "", ""])
                for enc in orphan_encounters:
                    enc_item = QTreeWidgetItem([
                        enc.get("mob_name", "?"),
                        enc.get("mob_name_source", "?"),
                        "1",
                        f"{enc.get('damage_dealt', 0):.1f}",
                        f"{enc.get('loot_total_ped', 0):.2f}",
                        enc.get("start_time", "")[:19],
                        (enc.get("end_time") or "")[:19],
                    ])
                    orphan_item.addChild(enc_item)
                session_item.addChild(orphan_item)

            self._history_tree.addTopLevelItem(session_item)

    def _on_history_selection_changed(self):
        """Enable/disable merge/split/delete based on selection."""
        items = self._history_tree.selectedItems()
        has_session = False
        hunt_count = 0
        for item in items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                if data.get("type") == "session":
                    has_session = True
                elif data.get("type") == "hunt":
                    hunt_count += 1

        self._delete_btn.setEnabled(has_session and len(items) == 1)
        self._merge_btn.setEnabled(hunt_count >= 2)
        self._split_btn.setEnabled(hunt_count == 1)

    def _on_merge_hunts(self):
        """Merge selected hunts into the first one."""
        items = self._history_tree.selectedItems()
        hunt_ids = []
        for item in items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and data.get("type") == "hunt":
                hunt_ids.append(data["id"])

        if len(hunt_ids) < 2:
            return

        target = hunt_ids[0]
        sources = hunt_ids[1:]
        self._db.merge_hunts(target, sources)
        self._load_history()

    def _on_split_hunt(self):
        """Split a hunt at the midpoint (simple split for now)."""
        items = self._history_tree.selectedItems()
        if not items:
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict) or data.get("type") != "hunt":
            return

        hunt_id = data["id"]
        encounters = self._db.get_hunt_encounters(hunt_id)
        if len(encounters) < 2:
            return

        # Split at midpoint
        mid = len(encounters) // 2
        split_encounters = encounters[mid:]
        encounter_ids = [e["id"] for e in split_encounters]
        new_start = split_encounters[0].get("start_time", "")
        primary_mob = split_encounters[0].get("mob_name")

        new_hunt_id = str(uuid.uuid4())
        self._db.split_hunt(hunt_id, new_hunt_id, new_start, encounter_ids, primary_mob)
        self._load_history()

    def _on_delete_session(self):
        """Delete a session after confirmation."""
        items = self._history_tree.selectedItems()
        if not items:
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict) or data.get("type") != "session":
            return

        reply = QMessageBox.question(
            self, "Delete Session",
            "Are you sure you want to delete this session and all its data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._db.delete_hunt_session(data["id"])
            self._load_history()

    # ------------------------------------------------------------------ #
    #  Settings handlers                                                   #
    # ------------------------------------------------------------------ #

    def _save_config(self):
        from ...core.config import save_config
        save_config(self._config, self._config_path)

    def _on_timeout_changed(self, value):
        self._config.session_auto_timeout_ms = value * 60000
        self._save_config()

    def _on_mob_threshold_changed(self, value):
        self._config.hunt_split_mob_threshold = value
        self._save_config()

    def _on_location_kills_changed(self, value):
        self._config.hunt_split_min_remote_kills = value
        self._save_config()

    def _on_close_timeout_changed(self, value):
        self._config.encounter_close_timeout_ms = value * 1000
        self._save_config()

    def _on_attr_window_changed(self, value):
        self._config.attribution_window_ms = value * 1000
        self._save_config()

    def _on_blacklist_mob_changed(self, mob_name: str):
        """Load per-mob blacklist for the selected mob into the editor."""
        mob_name = mob_name.strip().lower()
        if not mob_name:
            self._blacklist_mob_edit.clear()
            return
        items = self._config.loot_blacklist_per_mob.get(mob_name, [])
        self._blacklist_mob_edit.setPlainText("\n".join(items))

    def _on_save_blacklist(self):
        # Save global blacklist
        global_text = self._blacklist_edit.toPlainText()
        global_items = [line.strip() for line in global_text.splitlines() if line.strip()]
        self._config.loot_blacklist = global_items

        # Save per-mob blacklist for the currently selected mob
        mob_name = self._blacklist_mob_combo.currentText().strip().lower()
        if mob_name:
            mob_text = self._blacklist_mob_edit.toPlainText()
            mob_items = [line.strip() for line in mob_text.splitlines() if line.strip()]
            if mob_items:
                self._config.loot_blacklist_per_mob[mob_name] = mob_items
                # Add to combo if not already present
                existing = [self._blacklist_mob_combo.itemText(i)
                            for i in range(self._blacklist_mob_combo.count())]
                if mob_name not in existing:
                    self._blacklist_mob_combo.addItem(mob_name)
            else:
                # Empty list — remove the mob entry
                self._config.loot_blacklist_per_mob.pop(mob_name, None)

        self._save_config()

        # Reclassify all in-memory loot items retroactively
        self._event_bus.publish(EVENT_LOOT_BLACKLIST_CHANGED, None)
