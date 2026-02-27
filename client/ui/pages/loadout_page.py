"""Loadout page — full loadout editor with calculated stats."""

from __future__ import annotations

import json
import re
import copy
import threading
import uuid
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QSpinBox, QDoubleSpinBox, QTabWidget, QScrollArea,
    QFrame, QSplitter, QInputDialog, QFileDialog, QMessageBox, QDialog,
    QDialogButtonBox, QLineEdit, QCheckBox, QApplication, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QColor, QBrush

from ...core.logger import get_logger
from ..widgets.fuzzy_line_edit import FuzzyLineEdit
from ..theme import ACCENT, ERROR, MAIN_DARK, SECONDARY, TEXT, TEXT_MUTED
from ..icons import svg_icon

log = get_logger("Loadout")

MAX_SETS = 10
RECALC_DELAY_MS = 300
AUTOSAVE_DELAY_MS = 2000
POLL_INTERVAL_MS = 30_000
LABEL_WIDTH = 100
ENHANCER_COLS = 3


# ---------------------------------------------------------------------------
# Server ↔ Client format conversion
# ---------------------------------------------------------------------------
# Server returns: { id, name, data: {Gear, Skill, Markup, ...}, public, share_code, ... }
# Client uses:    { Id, Name, Gear, Skill, Markup, ..., public, share_code }
# The loadout content lives inside `data` on the server but is flat in the client.

def _unwrap_server_record(record: dict) -> dict:
    """Convert a server loadout record to the flat client format."""
    data = record.get("data")
    if not isinstance(data, dict):
        # Already in client format (e.g. from cache or local create)
        return record
    # Merge metadata onto the loadout content
    loadout = dict(data)
    loadout["Id"] = record.get("id") or record.get("Id")
    loadout["public"] = record.get("public", False)
    loadout["share_code"] = record.get("share_code", "")
    return loadout


def _wrap_for_server(loadout: dict) -> dict:
    """Convert the flat client loadout to the server request format."""
    return {
        "name": loadout.get("Name", "New Loadout"),
        "data": loadout,
        "public": bool(loadout.get("public", False)),
    }


def _unwrap_server_list(records: list[dict]) -> list[dict]:
    """Convert a list of server records to client format."""
    return [_unwrap_server_record(r) for r in records]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_loadout_label(loadout: dict) -> str:
    """Auto-name a loadout from weapon / armor set (matches website logic)."""
    name = (loadout.get("Name") or "").strip()
    if name and name != "New Loadout":
        return name
    weapon = (loadout.get("Gear", {}).get("Weapon", {}).get("Name") or "").strip()
    armor = (loadout.get("Gear", {}).get("Armor", {}).get("SetName") or "").strip()
    if weapon and armor:
        return f"{weapon} ({armor})"
    if weapon:
        return weapon
    return name or "New Loadout"


def _is_ring_slot(slot: str) -> bool:
    return bool(re.search(r"ring|finger", slot or "", re.IGNORECASE))


def _entity_names(items: list[dict]) -> list[str]:
    return sorted({
        item.get("Name", item.get("Properties", {}).get("Name", ""))
        for item in items if item
    } - {""})


def _is_limited_name(name: str) -> bool:
    """Check if an item name has the (L) tag — i.e. limited."""
    if not name:
        return False
    m = re.match(r'^(.*) \(([^)]*)\)$', name)
    return 'L' in m.group(2).split(',') if m else False


def _make_markup_spin() -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(0, 100000)
    spin.setValue(100)
    spin.setDecimals(2)
    spin.setSuffix("%")
    spin.setFixedWidth(90)
    return spin


# ---------------------------------------------------------------------------
# LoadoutPage
# ---------------------------------------------------------------------------

class LoadoutPage(QWidget):
    """Full loadout editor matching website functionality + hunt integration."""

    def __init__(self, *, signals, config, config_path, oauth, nexus_client, data_client,
                 event_bus=None):
        super().__init__()
        self._signals = signals
        self._config = config
        self._config_path = config_path
        self._oauth = oauth
        self._nexus_client = nexus_client
        self._data_client = data_client
        self._event_bus = event_bus
        self._loadouts: list[dict] = []
        self._current_loadout: dict | None = None
        self._entity_data: dict = {}
        self._calculator = None
        self._applying = False  # True while populating UI from loadout data
        self._dirty = False     # True when UI has unsaved changes
        self._saved_last_update: dict[str, str] = {}  # loadout_id → last_update
        self._save_in_flight = False

        # Set management
        self._active_set_indices = {"Weapon": 0, "Armor": 0, "Healing": 0, "Accessories": 0}
        self._set_combos: dict[str, QComboBox] = {}
        self._set_add_btns: dict[str, QPushButton] = {}
        self._set_rename_btns: dict[str, QPushButton] = {}
        self._set_delete_btns: dict[str, QPushButton] = {}

        # Weapon field row widgets (for show/hide by weapon class)
        self._weapon_field_rows: dict[str, QWidget] = {}

        # Inline markup: key → (container_widget, spin)
        self._markup_containers: dict[str, QWidget] = {}
        self._markup_spins: dict[str, QDoubleSpinBox] = {}

        # Accessories state (synced from/to loadout data)
        self._clothing_items: list[dict] = []   # [{Name, Slot, Side?}]
        self._consumable_items: list[dict] = []  # [{Name}]
        self._pet_effect_value: str | None = None

        # Recalculation debounce timer
        self._recalc_timer = QTimer()
        self._recalc_timer.setSingleShot(True)
        self._recalc_timer.setInterval(RECALC_DELAY_MS)
        self._recalc_timer.timeout.connect(self._on_gear_changed)

        # Auto-save debounce timer
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(AUTOSAVE_DELAY_MS)
        self._save_timer.timeout.connect(self._auto_save)

        # Local loadout cache
        self._cache_path = Path(__file__).parent.parent.parent / "data" / "cache" / "loadouts.json"

        # Periodic server poll
        self._poll_timer = QTimer()
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_loadouts)

        # --- Build UI ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(6)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Loadout:"))
        self._loadout_combo = QComboBox()
        self._loadout_combo.setMinimumWidth(250)
        self._loadout_combo.currentIndexChanged.connect(self._on_loadout_selected)
        toolbar.addWidget(self._loadout_combo)

        for label, handler in [
            ("New", self._on_new_loadout),
            ("Refresh", self._on_refresh),
            ("Set as Active for Hunt", self._on_set_active),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            toolbar.addWidget(btn)

        # Overflow menu for less-frequent actions
        more_btn = QPushButton("...")
        more_btn.setStyleSheet("padding: 6px 8px; letter-spacing: 2px;")
        more_btn.setToolTip("More actions")
        more_menu = QMenu(self)
        for label, handler in [
            ("Clone", self._on_clone),
            ("Import", self._on_import),
            ("Export", self._on_export),
            ("Share", self._on_share),
        ]:
            more_menu.addAction(label, handler)
        more_menu.addSeparator()
        delete_action = more_menu.addAction("Delete", self._on_delete)
        delete_action.setIcon(svg_icon(
            '<path d="M6 4V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1h4v2H2V4h4z'
            'M4 7h16l-1 15H5L4 7zm5 2v10h2V9H9zm4 0v10h2V9h-2z"/>',
            ERROR, 16,
        ))
        more_btn.clicked.connect(
            lambda: more_menu.exec(more_btn.mapToGlobal(more_btn.rect().bottomLeft()))
        )
        toolbar.addWidget(more_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Splitter: editor tabs | stats
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._editor_tabs = QTabWidget()
        self._build_weapon_tab()
        self._build_armor_tab()
        self._build_healing_tab()
        self._build_accessories_tab()
        self._build_settings_tab()

        editor_wrapper = QWidget()
        ew_layout = QHBoxLayout(editor_wrapper)
        ew_layout.setContentsMargins(0, 0, 8, 0)
        ew_layout.addWidget(self._editor_tabs)
        splitter.addWidget(editor_wrapper)

        stats_scroll = QScrollArea()
        stats_scroll.setWidgetResizable(True)
        stats_scroll.setFrameShape(QFrame.Shape.NoFrame)
        stats_scroll.setMinimumWidth(300)
        self._stats_widget = QWidget()
        self._stats_layout = QVBoxLayout(self._stats_widget)
        self._build_stats_display()
        stats_scroll.setWidget(self._stats_widget)

        splitter.addWidget(stats_scroll)
        splitter.setSizes([600, 350])
        layout.addWidget(splitter, 1)

        # Signals
        signals.auth_state_changed.connect(self._on_auth_changed)

        # Load entity data (chains into loadout fetch when done)
        self._load_entity_data()

    # ------------------------------------------------------------------
    # Helpers for building rows with inline markup
    # ------------------------------------------------------------------

    def _make_gear_row(self, label_text: str, field: FuzzyLineEdit,
                       markup_key: str, indent=False) -> QWidget:
        """Row: [Label] [FuzzyLineEdit stretch] [MU% container (hidden)]."""
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)

        lbl = QLabel(f"     {label_text}:" if indent else f"{label_text}:")
        lbl.setFixedWidth(LABEL_WIDTH)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if indent:
            lbl.setStyleSheet(f"color: {TEXT_MUTED};")
        hl.addWidget(lbl)
        hl.addWidget(field, 1)

        # Inline markup
        mu_container = QWidget()
        mu_hl = QHBoxLayout(mu_container)
        mu_hl.setContentsMargins(0, 0, 0, 0)
        mu_hl.setSpacing(2)
        mu_lbl = QLabel("MU%")
        mu_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        mu_hl.addWidget(mu_lbl)
        mu_spin = _make_markup_spin()
        mu_spin.valueChanged.connect(self._schedule_recalc)
        mu_hl.addWidget(mu_spin)
        hl.addWidget(mu_container)
        mu_container.hide()

        self._markup_containers[markup_key] = mu_container
        self._markup_spins[markup_key] = mu_spin

        field.textChanged.connect(lambda text: self._update_markup(markup_key, text))
        return row

    def _make_ammo_mu_row(self) -> QWidget:
        """Ammo markup row — visible whenever a weapon is selected."""
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)
        lbl = QLabel("Ammo MU%:")
        lbl.setFixedWidth(LABEL_WIDTH)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl.setStyleSheet(f"color: {TEXT_MUTED};")
        hl.addWidget(lbl)
        spin = _make_markup_spin()
        spin.valueChanged.connect(self._schedule_recalc)
        hl.addWidget(spin)
        hl.addStretch()
        self._markup_spins["Ammo"] = spin
        self._markup_containers["Ammo"] = row
        row.hide()
        return row

    def _make_enhancer_group(self, title: str, names: list[str],
                             storage: dict[str, QSpinBox]) -> QGroupBox:
        """Enhancers in a wrapping grid (ENHANCER_COLS pairs per row)."""
        group = QGroupBox(title)
        grid = QGridLayout(group)
        grid.setSpacing(4)
        for i, name in enumerate(names):
            r, c = divmod(i, ENHANCER_COLS)
            grid.addWidget(QLabel(f"{name}:"), r, c * 2)
            spin = QSpinBox()
            spin.setRange(0, 10)
            spin.valueChanged.connect(self._schedule_recalc)
            grid.addWidget(spin, r, c * 2 + 1)
            storage[name] = spin
        return group

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    @staticmethod
    def _scrollable_tab(tab: QWidget) -> QScrollArea:
        """Wrap a tab content widget in a transparent scroll area."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setWidget(tab)
        return scroll

    def _build_weapon_tab(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(8, 4, 8, 4)

        outer.addWidget(self._build_set_bar("Weapon"))

        vbox = QVBoxLayout()
        vbox.setSpacing(4)

        # Weapon (always visible)
        self._weapon_field = FuzzyLineEdit("Select weapon...")
        self._weapon_field.textChanged.connect(self._schedule_recalc)
        self._weapon_field.textChanged.connect(self._on_weapon_changed)
        vbox.addWidget(self._make_gear_row("Weapon", self._weapon_field, "Weapon"))

        # Ammo MU% row
        vbox.addWidget(self._make_ammo_mu_row())

        # Amplifier (always visible)
        self._amp_field = FuzzyLineEdit("Select amplifier...")
        self._amp_field.textChanged.connect(self._schedule_recalc)
        vbox.addWidget(self._make_gear_row("Amplifier", self._amp_field, "Amplifier"))

        # Absorber (Ranged)
        self._absorber_field = FuzzyLineEdit("Select absorber...")
        self._absorber_field.textChanged.connect(self._schedule_recalc)
        absorber_row = self._make_gear_row("Absorber", self._absorber_field, "Absorber")
        self._weapon_field_rows["Absorber"] = absorber_row
        absorber_row.hide()
        vbox.addWidget(absorber_row)

        # Scope (Ranged)
        self._scope_field = FuzzyLineEdit("Select scope...")
        self._scope_field.textChanged.connect(self._schedule_recalc)
        self._scope_field.textChanged.connect(self._on_scope_changed)
        scope_row = self._make_gear_row("Scope", self._scope_field, "Scope")
        self._weapon_field_rows["Scope"] = scope_row
        scope_row.hide()
        vbox.addWidget(scope_row)

        # Scope Sight (Ranged, indented)
        self._scope_sight_field = FuzzyLineEdit("Select sight for scope...")
        self._scope_sight_field.setEnabled(False)
        self._scope_sight_field.textChanged.connect(self._schedule_recalc)
        ss_row = self._make_gear_row("Scope Sight", self._scope_sight_field, "ScopeSight", indent=True)
        self._weapon_field_rows["ScopeSight"] = ss_row
        ss_row.hide()
        vbox.addWidget(ss_row)

        # Sight (Ranged)
        self._sight_field = FuzzyLineEdit("Select sight...")
        self._sight_field.textChanged.connect(self._schedule_recalc)
        sight_row = self._make_gear_row("Sight", self._sight_field, "Sight")
        self._weapon_field_rows["Sight"] = sight_row
        sight_row.hide()
        vbox.addWidget(sight_row)

        # Matrix (Melee)
        self._matrix_field = FuzzyLineEdit("Select matrix (melee)...")
        self._matrix_field.textChanged.connect(self._schedule_recalc)
        matrix_row = self._make_gear_row("Matrix", self._matrix_field, "Matrix")
        self._weapon_field_rows["Matrix"] = matrix_row
        matrix_row.hide()
        vbox.addWidget(matrix_row)

        # Implant (Mindforce)
        self._implant_field = FuzzyLineEdit("Select implant (MF)...")
        self._implant_field.textChanged.connect(self._schedule_recalc)
        implant_row = self._make_gear_row("Implant", self._implant_field, "Implant")
        self._weapon_field_rows["Implant"] = implant_row
        implant_row.hide()
        vbox.addWidget(implant_row)

        outer.addLayout(vbox)

        # Enhancers (wrapping grid)
        self._weapon_enhancers: dict[str, QSpinBox] = {}
        outer.addWidget(self._make_enhancer_group(
            "Enhancers", ["Damage", "Accuracy", "Range", "Economy", "SkillMod"],
            self._weapon_enhancers,
        ))

        outer.addStretch()
        self._editor_tabs.addTab(self._scrollable_tab(tab), "Weapon")

    def _build_armor_tab(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(8, 4, 8, 4)

        outer.addWidget(self._build_set_bar("Armor"))

        vbox = QVBoxLayout()
        vbox.setSpacing(4)

        self._armor_set_field = FuzzyLineEdit("Select armor set...")
        self._armor_set_field.textChanged.connect(self._schedule_recalc)
        vbox.addWidget(self._make_gear_row("Armor Set", self._armor_set_field, "ArmorSet"))

        self._plate_field = FuzzyLineEdit("Select plating...")
        self._plate_field.textChanged.connect(self._schedule_recalc)
        vbox.addWidget(self._make_gear_row("Plating", self._plate_field, "PlateSet"))

        outer.addLayout(vbox)

        # Enhancers (wrapping grid)
        self._armor_enhancers: dict[str, QSpinBox] = {}
        outer.addWidget(self._make_enhancer_group(
            "Enhancers", ["Defense", "Durability"], self._armor_enhancers,
        ))

        outer.addStretch()
        self._editor_tabs.addTab(self._scrollable_tab(tab), "Armor")

    def _build_healing_tab(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(8, 4, 8, 4)

        outer.addWidget(self._build_set_bar("Healing"))

        vbox = QVBoxLayout()
        vbox.setSpacing(4)

        self._heal_field = FuzzyLineEdit("Select healing tool...")
        self._heal_field.textChanged.connect(self._schedule_recalc)
        vbox.addWidget(self._make_gear_row("Healing Tool", self._heal_field, "HealingTool"))

        outer.addLayout(vbox)

        # Enhancers (wrapping grid)
        self._heal_enhancers: dict[str, QSpinBox] = {}
        outer.addWidget(self._make_enhancer_group(
            "Enhancers", ["Heal", "Economy", "SkillMod"], self._heal_enhancers,
        ))

        outer.addStretch()
        self._editor_tabs.addTab(self._scrollable_tab(tab), "Healing")

    def _build_accessories_tab(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(8, 4, 8, 4)

        outer.addWidget(self._build_set_bar("Accessories"))

        # --- Rings & Pet ---
        rp_group = QGroupBox("Rings && Pet")
        rp_layout = QGridLayout(rp_group)
        rp_layout.setColumnStretch(1, 1)

        self._left_ring_field = FuzzyLineEdit("Select left ring...")
        self._left_ring_field.item_selected.connect(lambda name: self._set_ring("Left", name))
        rp_layout.addWidget(QLabel("Left Ring:"), 0, 0, Qt.AlignmentFlag.AlignRight)
        rp_layout.addWidget(self._left_ring_field, 0, 1)

        self._right_ring_field = FuzzyLineEdit("Select right ring...")
        self._right_ring_field.item_selected.connect(lambda name: self._set_ring("Right", name))
        rp_layout.addWidget(QLabel("Right Ring:"), 1, 0, Qt.AlignmentFlag.AlignRight)
        rp_layout.addWidget(self._right_ring_field, 1, 1)

        self._pet_field = FuzzyLineEdit("Select pet...")
        self._pet_field.textChanged.connect(self._on_pet_changed)
        rp_layout.addWidget(QLabel("Pet:"), 2, 0, Qt.AlignmentFlag.AlignRight)
        rp_layout.addWidget(self._pet_field, 2, 1)

        outer.addWidget(rp_group)

        # Pet effects container
        self._pet_effects_container = QWidget()
        self._pet_effects_layout = QVBoxLayout(self._pet_effects_container)
        self._pet_effects_layout.setContentsMargins(0, 0, 0, 0)
        self._pet_effects_label = QLabel("Select a pet to view abilities.")
        self._pet_effects_label.setStyleSheet(f"color: {TEXT_MUTED}; font-style: italic;")
        self._pet_effects_layout.addWidget(self._pet_effects_label)
        outer.addWidget(self._pet_effects_container)

        # --- Clothing ---
        cloth_group = QGroupBox("Clothing")
        cloth_layout = QVBoxLayout(cloth_group)
        hint = QLabel("Slots are unique. Picking a piece for an occupied slot replaces it.")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        hint.setWordWrap(True)
        cloth_layout.addWidget(hint)

        self._clothing_search = FuzzyLineEdit("Search clothing to add...")
        self._clothing_search.item_selected.connect(self._add_clothing_by_name)
        cloth_layout.addWidget(self._clothing_search)

        self._clothing_list_container = QWidget()
        self._clothing_list_layout = QVBoxLayout(self._clothing_list_container)
        self._clothing_list_layout.setContentsMargins(0, 0, 0, 0)
        self._clothing_list_layout.setSpacing(2)
        cloth_layout.addWidget(self._clothing_list_container)
        outer.addWidget(cloth_group)

        # --- Consumables ---
        cons_group = QGroupBox("Consumables")
        cons_layout = QVBoxLayout(cons_group)
        hint2 = QLabel("Only the strongest consumable effect per type is applied.")
        hint2.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        hint2.setWordWrap(True)
        cons_layout.addWidget(hint2)

        self._consumable_search = FuzzyLineEdit("Search consumable to add...")
        self._consumable_search.item_selected.connect(self._add_consumable_by_name)
        cons_layout.addWidget(self._consumable_search)

        self._consumable_list_container = QWidget()
        self._consumable_list_layout = QVBoxLayout(self._consumable_list_container)
        self._consumable_list_layout.setContentsMargins(0, 0, 0, 0)
        self._consumable_list_layout.setSpacing(2)
        cons_layout.addWidget(self._consumable_list_container)
        outer.addWidget(cons_group)

        outer.addStretch()
        self._editor_tabs.addTab(self._scrollable_tab(tab), "Accessories")

    def _build_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 4, 8, 4)

        # Profession Levels
        skills_group = QGroupBox("Profession Levels")
        sg = QGridLayout(skills_group)
        sg.setColumnStretch(1, 1)
        self._skill_inputs: dict[str, QSpinBox] = {}
        for i, (name, label) in enumerate([("Hit", "Hit Profession"), ("Dmg", "Dmg Profession"), ("Heal", "Heal Profession")]):
            sg.addWidget(QLabel(f"{label}:"), i, 0, Qt.AlignmentFlag.AlignRight)
            spin = QSpinBox()
            spin.setRange(0, 50000)
            spin.setValue(200)
            spin.valueChanged.connect(self._schedule_recalc)
            sg.addWidget(spin, i, 1)
            self._skill_inputs[name] = spin
        layout.addWidget(skills_group)

        # Bonus Stats
        bonus_group = QGroupBox("Bonus Stats")
        bg = QGridLayout(bonus_group)
        bg.setColumnStretch(1, 1)
        self._bonus_inputs: dict[str, QDoubleSpinBox] = {}
        for i, (key, label) in enumerate([
            ("BonusDamage", "% Damage"),
            ("BonusCritChance", "% Crit Chance"),
            ("BonusCritDamage", "% Crit Damage"),
            ("BonusReload", "% Reload"),
        ]):
            bg.addWidget(QLabel(f"{label}:"), i, 0, Qt.AlignmentFlag.AlignRight)
            spin = QDoubleSpinBox()
            spin.setRange(-1000, 1000)
            spin.setDecimals(2)
            spin.setValue(0)
            spin.valueChanged.connect(self._schedule_recalc)
            bg.addWidget(spin, i, 1)
            self._bonus_inputs[key] = spin
        layout.addWidget(bonus_group)

        layout.addStretch()
        self._editor_tabs.addTab(self._scrollable_tab(tab), "Settings")

    # ------------------------------------------------------------------
    # Stats display
    # ------------------------------------------------------------------

    def _build_stats_display(self):
        def _add_group(title, stat_names):
            group = QGroupBox(title)
            glayout = QVBoxLayout(group)
            labels = {}
            for name in stat_names:
                row = QHBoxLayout()
                nlbl = QLabel(f"{name}:")
                nlbl.setMinimumWidth(120)
                row.addWidget(nlbl)
                vlbl = QLabel("-")
                vlbl.setAlignment(Qt.AlignmentFlag.AlignRight)
                row.addWidget(vlbl)
                glayout.addLayout(row)
                labels[name] = vlbl
            self._stats_layout.addWidget(group)
            return labels

        def _add_tier1(stat_names):
            """Add highlighted primary stats (Efficiency, DPS, DPP)."""
            container = QWidget()
            container.setStyleSheet(
                f"border: 1px solid {ACCENT}; border-radius: 6px; padding: 4px;"
            )
            hlayout = QHBoxLayout(container)
            hlayout.setContentsMargins(4, 4, 4, 4)
            hlayout.setSpacing(8)
            labels = {}
            for name in stat_names:
                cell = QVBoxLayout()
                cell.setSpacing(2)
                nlbl = QLabel(name.upper())
                nlbl.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600; "
                    f"border: none; letter-spacing: 1px;"
                )
                nlbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.addWidget(nlbl)
                vlbl = QLabel("-")
                vlbl.setStyleSheet(
                    f"font-size: 16px; font-weight: bold; color: {ACCENT}; border: none;"
                )
                vlbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.addWidget(vlbl)
                hlayout.addLayout(cell)
                labels[name] = vlbl
            self._stats_layout.addWidget(container)
            return labels

        # Tier-1 highlighted stats
        self._tier1_stats = _add_tier1(["Efficiency", "DPS", "DPP"])

        # Sections in website order
        self._off_stats = _add_group("Offense", [
            "Total Damage", "Range", "Crit Chance", "Crit Damage",
            "Effective Damage", "Reload", "Cost",
        ])
        self._econ_stats = _add_group("Economy", [
            "Decay", "Ammo Burn", "Weapon Cost", "Total Uses",
        ])
        self._heal_stats = _add_group("Healing", [
            "Total Heal", "Effective Heal", "Heal Reload",
            "HPS", "HPP", "Heal Total Uses",
        ])
        self._def_stats = _add_group("Defense", [
            "Armor Defense", "Plate Defense", "Total Defense",
            "Block Chance", "Total Absorption", "Top Types",
        ])
        self._skill_stats = _add_group("Skill", [
            "Hit Ability", "Crit Ability",
        ])
        self._stats_layout.addStretch()

    # ------------------------------------------------------------------
    # Set tab bar
    # ------------------------------------------------------------------

    def _build_set_bar(self, section: str) -> QWidget:
        bar = QWidget()
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(0, 0, 0, 2)
        hl.setSpacing(4)

        combo = QComboBox()
        combo.setMinimumWidth(150)
        combo.currentIndexChanged.connect(
            lambda idx: self._on_set_combo_changed(section, idx)
        )
        combo.hide()
        hl.addWidget(combo)
        self._set_combos[section] = combo

        add_btn = QPushButton("+ Add Set")
        add_btn.setFixedHeight(24)
        add_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        add_btn.clicked.connect(lambda: self._add_set(section))
        hl.addWidget(add_btn)
        self._set_add_btns[section] = add_btn

        rename_btn = QPushButton("Rename")
        rename_btn.setFixedHeight(24)
        rename_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        rename_btn.clicked.connect(lambda: self._rename_set(section))
        rename_btn.hide()
        hl.addWidget(rename_btn)
        self._set_rename_btns[section] = rename_btn

        delete_btn = QPushButton("Delete")
        delete_btn.setFixedHeight(24)
        delete_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        delete_btn.clicked.connect(lambda: self._delete_set(section))
        delete_btn.hide()
        hl.addWidget(delete_btn)
        self._set_delete_btns[section] = delete_btn

        hl.addStretch()
        self._refresh_set_bar(section)
        return bar

    def _refresh_set_bar(self, section: str):
        combo = self._set_combos.get(section)
        if not combo:
            return

        sets = self._get_sets(section) or []
        active = self._active_set_indices.get(section, 0)
        multi = len(sets) >= 2

        # Combo: only visible when 2+ sets
        combo.blockSignals(True)
        combo.clear()
        if multi:
            for i, entry in enumerate(sets):
                name = entry.get("name") or f"Set {i + 1}"
                if entry.get("isDefault"):
                    name += " \u2605"
                combo.addItem(name)
            combo.setCurrentIndex(min(active, len(sets) - 1))
        combo.blockSignals(False)
        combo.setVisible(multi)

        self._set_add_btns[section].setVisible(True)
        self._set_rename_btns[section].setVisible(multi)
        self._set_delete_btns[section].setVisible(multi)

    # ------------------------------------------------------------------
    # Set management
    # ------------------------------------------------------------------

    def _get_sets(self, section: str) -> list | None:
        if not self._current_loadout:
            return None
        return self._current_loadout.get("Sets", {}).get(section)

    def _ensure_sets(self, section: str) -> list:
        lo = self._current_loadout
        if not lo:
            return []
        if not lo.get("Sets"):
            lo["Sets"] = {"Weapon": [], "Armor": [], "Healing": [], "Accessories": []}
        sets = lo["Sets"].get(section)
        if not sets:
            sets = []
            lo["Sets"][section] = sets
        return sets

    def _on_set_combo_changed(self, section: str, index: int):
        sets = self._get_sets(section) or []
        if 0 <= index < len(sets):
            self._switch_set(section, index)

    def _add_set(self, section: str):
        if not self._current_loadout:
            return
        sets = self._ensure_sets(section)
        if len(sets) >= MAX_SETS:
            return

        # If no sets exist yet, save current state as set 0 first
        if not sets:
            sets.append({
                "name": "Set 1",
                "isDefault": True,
                "gear": self._extract_section_gear(section),
                "markup": self._extract_section_markup(section),
            })
            self._active_set_indices[section] = 0

        # Copy current set
        active = self._active_set_indices.get(section, 0)
        if 0 <= active < len(sets):
            new_entry = copy.deepcopy(sets[active])
            new_entry["name"] = f"Set {len(sets) + 1}"
            new_entry["isDefault"] = False
        else:
            new_entry = self._make_empty_set_entry(section, len(sets) + 1)

        sets.append(new_entry)
        self._active_set_indices[section] = len(sets) - 1
        self._refresh_set_bar(section)

    def _make_empty_set_entry(self, section: str, num: int) -> dict:
        from ...loadout.models import create_empty_loadout
        empty = create_empty_loadout()
        gear_map = {
            "Weapon": empty["Gear"]["Weapon"],
            "Armor": empty["Gear"]["Armor"],
            "Healing": empty["Gear"]["Healing"],
            "Accessories": {
                "Clothing": [], "Consumables": [],
                "Pet": {"Name": None, "Effect": None},
            },
        }
        markup_map = {
            "Weapon": {k: empty["Markup"][k] for k in
                       ("Weapon", "Ammo", "Amplifier", "Scope", "Sight",
                        "ScopeSight", "Absorber", "Matrix", "Implant")},
            "Armor": {"ArmorSet": 100, "PlateSet": 100},
            "Healing": {"HealingTool": 100},
            "Accessories": {},
        }
        return {
            "name": f"Set {num}",
            "isDefault": False,
            "gear": gear_map.get(section, {}),
            "markup": markup_map.get(section, {}),
        }

    def _switch_set(self, section: str, index: int):
        if not self._current_loadout:
            return
        sets = self._get_sets(section)
        if not sets or index < 0 or index >= len(sets):
            return

        old_idx = self._active_set_indices.get(section, 0)
        if old_idx == index:
            return

        # Save current into old set
        if 0 <= old_idx < len(sets):
            sets[old_idx]["gear"] = self._extract_section_gear(section)
            sets[old_idx]["markup"] = self._extract_section_markup(section)

        self._active_set_indices[section] = index

        # Apply new set data to UI
        entry = sets[index]
        self._applying = True
        self._apply_section_gear(section, entry.get("gear", {}))
        self._apply_section_markup(section, entry.get("markup", {}))
        self._applying = False

        self._refresh_set_bar(section)
        self._on_gear_changed()

    def _delete_set(self, section: str):
        sets = self._get_sets(section)
        if not sets or len(sets) <= 1:
            return
        active = self._active_set_indices.get(section, 0)
        sets.pop(active)
        self._active_set_indices[section] = max(0, active - 1)

        # Apply the now-active set
        new_active = self._active_set_indices[section]
        if 0 <= new_active < len(sets):
            self._applying = True
            self._apply_section_gear(section, sets[new_active].get("gear", {}))
            self._apply_section_markup(section, sets[new_active].get("markup", {}))
            self._applying = False
        self._refresh_set_bar(section)
        self._on_gear_changed()

    def _rename_set(self, section: str):
        sets = self._get_sets(section)
        active = self._active_set_indices.get(section, 0)
        if not sets or active >= len(sets):
            return
        current = sets[active].get("name", f"Set {active + 1}")
        name, ok = QInputDialog.getText(self, "Rename Set", "Name:", text=current)
        if ok and name.strip():
            sets[active]["name"] = name.strip()
            self._refresh_set_bar(section)

    # --- Extract / apply section data ---

    def _extract_section_gear(self, section: str) -> dict:
        if section == "Weapon":
            return {
                "Name": self._weapon_field.current_value() or None,
                "Amplifier": {"Name": self._amp_field.current_value() or None},
                "Absorber": {"Name": self._absorber_field.current_value() or None},
                "Scope": {
                    "Name": self._scope_field.current_value() or None,
                    "Sight": {"Name": self._scope_sight_field.current_value() or None},
                },
                "Sight": {"Name": self._sight_field.current_value() or None},
                "Matrix": {"Name": self._matrix_field.current_value() or None},
                "Implant": {"Name": self._implant_field.current_value() or None},
                "Enhancers": {k: s.value() for k, s in self._weapon_enhancers.items()},
            }
        if section == "Armor":
            return {
                "SetName": self._armor_set_field.current_value() or None,
                "PlateName": self._plate_field.current_value() or None,
                "Enhancers": {k: s.value() for k, s in self._armor_enhancers.items()},
            }
        if section == "Healing":
            return {
                "Name": self._heal_field.current_value() or None,
                "Enhancers": {k: s.value() for k, s in self._heal_enhancers.items()},
            }
        if section == "Accessories":
            return {
                "Clothing": copy.deepcopy(self._clothing_items),
                "Consumables": copy.deepcopy(self._consumable_items),
                "Pet": {
                    "Name": self._pet_field.current_value() or None,
                    "Effect": self._current_pet_effect,
                },
            }
        return {}

    def _extract_section_markup(self, section: str) -> dict:
        if section == "Weapon":
            keys = ("Weapon", "Ammo", "Amplifier", "Scope", "Sight",
                    "ScopeSight", "Absorber", "Matrix", "Implant")
            return {k: self._markup_spins[k].value() for k in keys if k in self._markup_spins}
        if section == "Armor":
            return {k: self._markup_spins[k].value()
                    for k in ("ArmorSet", "PlateSet") if k in self._markup_spins}
        if section == "Healing":
            if "HealingTool" in self._markup_spins:
                return {"HealingTool": self._markup_spins["HealingTool"].value()}
        return {}

    def _apply_section_gear(self, section: str, gear: dict):
        if section == "Weapon":
            self._weapon_field.set_value(gear.get("Name") or "")
            self._amp_field.set_value((gear.get("Amplifier") or {}).get("Name") or "")
            self._absorber_field.set_value((gear.get("Absorber") or {}).get("Name") or "")
            scope = gear.get("Scope") or {}
            self._scope_field.set_value(scope.get("Name") or "")
            self._scope_sight_field.set_value((scope.get("Sight") or {}).get("Name") or "")
            self._sight_field.set_value((gear.get("Sight") or {}).get("Name") or "")
            self._matrix_field.set_value((gear.get("Matrix") or {}).get("Name") or "")
            self._implant_field.set_value((gear.get("Implant") or {}).get("Name") or "")
            enh = gear.get("Enhancers") or {}
            for k, spin in self._weapon_enhancers.items():
                spin.setValue(enh.get(k, 0))
        elif section == "Armor":
            self._armor_set_field.set_value(gear.get("SetName") or "")
            self._plate_field.set_value(gear.get("PlateName") or "")
            enh = gear.get("Enhancers") or {}
            for k, spin in self._armor_enhancers.items():
                spin.setValue(enh.get(k, 0))
        elif section == "Healing":
            self._heal_field.set_value(gear.get("Name") or "")
            enh = gear.get("Enhancers") or {}
            for k, spin in self._heal_enhancers.items():
                spin.setValue(enh.get(k, 0))
        elif section == "Accessories":
            self._clothing_items = list(gear.get("Clothing") or [])
            self._consumable_items = list(gear.get("Consumables") or [])
            pet = gear.get("Pet") or {}
            self._pet_field.set_value(pet.get("Name") or "")
            self._current_pet_effect = pet.get("Effect")
            self._refresh_clothing_list()
            self._refresh_consumables_list()
            self._refresh_pet_effects()

    def _apply_section_markup(self, section: str, markup: dict):
        if section == "Weapon":
            for k in ("Weapon", "Ammo", "Amplifier", "Scope", "Sight",
                       "ScopeSight", "Absorber", "Matrix", "Implant"):
                if k in self._markup_spins:
                    self._markup_spins[k].setValue(markup.get(k, 100))
        elif section == "Armor":
            for k in ("ArmorSet", "PlateSet"):
                if k in self._markup_spins:
                    self._markup_spins[k].setValue(markup.get(k, 100))
        elif section == "Healing":
            if "HealingTool" in self._markup_spins:
                self._markup_spins["HealingTool"].setValue(markup.get("HealingTool", 100))

    # ------------------------------------------------------------------
    # Weapon class → show/hide fields
    # ------------------------------------------------------------------

    def _on_weapon_changed(self, text: str):
        if self._applying:
            return
        self._update_weapon_fields()
        self._update_loadout_combo_label()

    def _update_weapon_fields(self):
        """Show/hide weapon attachment fields based on weapon class."""
        weapon_name = self._weapon_field.current_value()
        weapon_class = None
        if weapon_name:
            weapons = self._entity_data.get("weapons", [])
            weapon = next((w for w in weapons if w.get("Name") == weapon_name), None)
            if weapon:
                weapon_class = (weapon.get("Properties") or {}).get("Class")

        # Ammo MU% visible when weapon selected
        ammo_container = self._markup_containers.get("Ammo")
        if ammo_container:
            ammo_container.setVisible(bool(weapon_name))

        # Ranged: Absorber, Scope, ScopeSight, Sight
        is_ranged = weapon_class == "Ranged"
        for key in ("Absorber", "Scope", "ScopeSight", "Sight"):
            row = self._weapon_field_rows.get(key)
            if row:
                row.setVisible(is_ranged)

        # Melee: Matrix
        row = self._weapon_field_rows.get("Matrix")
        if row:
            row.setVisible(weapon_class == "Melee")

        # Mindforce: Implant
        row = self._weapon_field_rows.get("Implant")
        if row:
            row.setVisible(weapon_class == "Mindforce")

        # Update markup for weapon/amp (they're always visible)
        self._update_markup("Weapon", weapon_name)
        self._update_markup("Amplifier", self._amp_field.current_value())

    # ------------------------------------------------------------------
    # Markup visibility — show for (L) items, lock to 100% otherwise
    # ------------------------------------------------------------------

    def _update_markup(self, key: str, text: str):
        container = self._markup_containers.get(key)
        spin = self._markup_spins.get(key)
        if not container or not spin:
            return
        # Ammo is handled separately in _update_weapon_fields
        if key == "Ammo":
            return

        name = (text or "").strip()
        is_limited = _is_limited_name(name)

        # For weapon attachments, check if the parent row is visible
        row = self._weapon_field_rows.get(key)
        row_visible = row.isVisible() if row else True

        if name and row_visible and is_limited:
            container.show()
            spin.setEnabled(True)
        else:
            # Not (L) or empty/hidden: hide markup, lock value to 100%
            container.hide()
            if not is_limited:
                spin.setValue(100)

    # ------------------------------------------------------------------
    # Scope changed → enable/disable scope sight
    # ------------------------------------------------------------------

    def _on_scope_changed(self, text: str):
        has_scope = bool(text.strip())
        self._scope_sight_field.setEnabled(has_scope)
        if not has_scope:
            self._scope_sight_field.clear_selection()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_entity_data(self):
        def fetch():
            self._entity_data = {
                "weapons": self._data_client.get_weapons(),
                "amplifiers": self._data_client.get_amplifiers(),
                "scopes_sights": self._data_client.get_scopes_and_sights(),
                "absorbers": self._data_client.get_absorbers(),
                "implants": self._data_client.get_implants(),
                "armor_sets": self._data_client.get_armor_sets(),
                "armors": self._data_client.get_armors(),
                "armor_platings": self._data_client.get_armor_platings(),
                "enhancers": self._data_client.get_enhancers(),
                "medical_tools": self._data_client.get_medical_tools(),
                "clothing": self._data_client.get_clothing(),
                "pets": self._data_client.get_pets(),
                "stimulants": self._data_client.get_stimulants(),
                "effects": self._data_client.get_effects(),
            }
            from PyQt6.QtCore import QMetaObject, Qt as QtConst
            QMetaObject.invokeMethod(self, "_populate_fields",
                                     QtConst.ConnectionType.QueuedConnection)

        threading.Thread(target=fetch, daemon=True).start()

    @pyqtSlot()
    def _populate_fields(self):
        """Populate FuzzyLineEdit items from entity data (main thread)."""
        weapons = self._entity_data.get("weapons", [])
        self._weapon_field.set_items(_entity_names(weapons))

        amps = self._entity_data.get("amplifiers", [])
        # Separate amplifiers from matrices
        amp_names = sorted({
            item.get("Name", "") for item in amps
            if item and item.get("Properties", {}).get("Type") != "Matrix"
        } - {""})
        matrix_names = sorted({
            item.get("Name", "") for item in amps
            if item and item.get("Properties", {}).get("Type") == "Matrix"
        } - {""})
        self._amp_field.set_items(amp_names)
        self._matrix_field.set_items(matrix_names)

        sv = self._entity_data.get("scopes_sights", [])
        scope_names = sorted({
            item.get("Name", "") for item in sv
            if item.get("Properties", {}).get("Type") == "Scope"
        } - {""})
        sight_names = sorted({
            item.get("Name", "") for item in sv
            if item.get("Properties", {}).get("Type") == "Sight"
        } - {""})
        self._scope_field.set_items(scope_names)
        self._scope_sight_field.set_items(sight_names)
        self._sight_field.set_items(sight_names)

        self._absorber_field.set_items(_entity_names(self._entity_data.get("absorbers", [])))
        self._implant_field.set_items(_entity_names(self._entity_data.get("implants", [])))
        self._armor_set_field.set_items(_entity_names(self._entity_data.get("armor_sets", [])))
        self._plate_field.set_items(_entity_names(self._entity_data.get("armor_platings", [])))
        self._heal_field.set_items(_entity_names(self._entity_data.get("medical_tools", [])))
        self._pet_field.set_items(_entity_names(self._entity_data.get("pets", [])))

        # Clothing: split rings from general clothing
        all_clothing = self._entity_data.get("clothing", [])
        ring_names_left = sorted({
            item.get("Name", "") for item in all_clothing
            if _is_ring_slot(item.get("Properties", {}).get("Slot", ""))
            and "left" in (item.get("Properties", {}).get("Slot", "")).lower()
        } - {""})
        ring_names_right = sorted({
            item.get("Name", "") for item in all_clothing
            if _is_ring_slot(item.get("Properties", {}).get("Slot", ""))
            and "right" in (item.get("Properties", {}).get("Slot", "")).lower()
        } - {""})
        non_ring_clothing = sorted({
            item.get("Name", "") for item in all_clothing
            if not _is_ring_slot(item.get("Properties", {}).get("Slot", ""))
        } - {""})
        self._left_ring_field.set_items(ring_names_left)
        self._right_ring_field.set_items(ring_names_right)
        self._clothing_search.set_items(non_ring_clothing)

        self._consumable_search.set_items(_entity_names(self._entity_data.get("stimulants", [])))

        # Load cached loadouts first (instant), then sync from server
        cached = self._load_from_cache()
        if cached:
            self._loadouts = cached
            self._update_loadout_list()
        self._on_refresh()

        # Start periodic polling
        self._poll_timer.start()

    # ------------------------------------------------------------------
    # Recalculation
    # ------------------------------------------------------------------

    def _schedule_recalc(self, *_args):
        if self._applying:
            return
        self._dirty = True
        self._recalc_timer.start()
        self._save_timer.start()

    def _on_gear_changed(self):
        if not self._calculator:
            try:
                from ...loadout.calculator import LoadoutCalculator
                self._calculator = LoadoutCalculator(self._config.js_utils_path or None)
            except Exception as e:
                log.error("JS bridge init failed: %s", e)
                return

        loadout = self._build_loadout_from_ui()
        try:
            stats = self._calculator.evaluate(loadout, self._entity_data)
            self._update_stats_display(stats)
        except Exception as e:
            log.error("Calculation error: %s", e)
            return

        # Publish if this is the active loadout (for hunt tracker cost tracking)
        if (self._current_loadout
                and self._current_loadout.get("Id") == self._config.active_loadout_id):
            self._publish_active_loadout()

    # ------------------------------------------------------------------
    # Build / Apply loadout
    # ------------------------------------------------------------------

    def _build_loadout_from_ui(self) -> dict:
        scope_name = self._scope_field.current_value() or None
        return {
            "Id": self._current_loadout.get("Id") if self._current_loadout else None,
            "Name": self._current_loadout.get("Name", "New Loadout") if self._current_loadout else "New Loadout",
            "Properties": {
                k: spin.value() for k, spin in self._bonus_inputs.items()
            },
            "Gear": {
                "Weapon": {
                    "Name": self._weapon_field.current_value() or None,
                    "Amplifier": {"Name": self._amp_field.current_value() or None},
                    "Absorber": {"Name": self._absorber_field.current_value() or None},
                    "Scope": {
                        "Name": scope_name,
                        "Sight": {"Name": self._scope_sight_field.current_value() or None} if scope_name else {"Name": None},
                    },
                    "Sight": {"Name": self._sight_field.current_value() or None},
                    "Matrix": {"Name": self._matrix_field.current_value() or None},
                    "Implant": {"Name": self._implant_field.current_value() or None},
                    "Enhancers": {k: s.value() for k, s in self._weapon_enhancers.items()},
                },
                "Armor": {
                    "SetName": self._armor_set_field.current_value() or None,
                    "PlateName": self._plate_field.current_value() or None,
                    "ManageIndividual": False,
                    "Enhancers": {k: s.value() for k, s in self._armor_enhancers.items()},
                },
                "Healing": {
                    "Name": self._heal_field.current_value() or None,
                    "Enhancers": {k: s.value() for k, s in self._heal_enhancers.items()},
                },
                "Clothing": copy.deepcopy(self._clothing_items),
                "Consumables": copy.deepcopy(self._consumable_items),
                "Pet": {
                    "Name": self._pet_field.current_value() or None,
                    "Effect": self._current_pet_effect,
                },
            },
            "Sets": self._current_loadout.get("Sets", {
                "Weapon": [], "Armor": [], "Healing": [], "Accessories": [],
            }) if self._current_loadout else {
                "Weapon": [], "Armor": [], "Healing": [], "Accessories": [],
            },
            "Skill": {k: s.value() for k, s in self._skill_inputs.items()},
            "Markup": self._collect_all_markup(),
        }

    def _collect_all_markup(self) -> dict:
        markup = {}
        for key in ("Weapon", "Ammo", "Amplifier", "Scope", "Sight",
                     "ScopeSight", "Absorber", "Matrix", "Implant",
                     "ArmorSet", "PlateSet", "HealingTool"):
            spin = self._markup_spins.get(key)
            if spin:
                markup[key] = spin.value()
        # Preserve per-slot armor/plate markup from loadout
        if self._current_loadout:
            existing = self._current_loadout.get("Markup", {})
            markup["Armors"] = existing.get("Armors", {})
            markup["Plates"] = existing.get("Plates", {})
        else:
            markup["Armors"] = {}
            markup["Plates"] = {}
        return markup

    @property
    def _current_pet_effect(self) -> str | None:
        return getattr(self, "_pet_effect_value", None)

    @_current_pet_effect.setter
    def _current_pet_effect(self, value: str | None):
        self._pet_effect_value = value

    def _apply_loadout_to_ui(self, loadout: dict):
        self._applying = True

        gear = loadout.get("Gear", {})
        weapon = gear.get("Weapon", {})
        armor = gear.get("Armor", {})
        healing = gear.get("Healing", {})
        skill = loadout.get("Skill", {})
        markup = loadout.get("Markup", {})
        props = loadout.get("Properties", {})

        # Weapon
        self._weapon_field.set_value(weapon.get("Name") or "")
        self._amp_field.set_value((weapon.get("Amplifier") or {}).get("Name") or "")
        self._absorber_field.set_value((weapon.get("Absorber") or {}).get("Name") or "")
        scope = weapon.get("Scope") or {}
        self._scope_field.set_value(scope.get("Name") or "")
        self._scope_sight_field.set_value((scope.get("Sight") or {}).get("Name") or "")
        self._sight_field.set_value((weapon.get("Sight") or {}).get("Name") or "")
        self._matrix_field.set_value((weapon.get("Matrix") or {}).get("Name") or "")
        self._implant_field.set_value((weapon.get("Implant") or {}).get("Name") or "")

        for k, spin in self._weapon_enhancers.items():
            spin.setValue((weapon.get("Enhancers") or {}).get(k, 0))

        # Armor
        self._armor_set_field.set_value(armor.get("SetName") or "")
        self._plate_field.set_value(armor.get("PlateName") or "")
        for k, spin in self._armor_enhancers.items():
            spin.setValue((armor.get("Enhancers") or {}).get(k, 0))

        # Healing
        self._heal_field.set_value(healing.get("Name") or "")
        for k, spin in self._heal_enhancers.items():
            spin.setValue((healing.get("Enhancers") or {}).get(k, 0))

        # Settings
        for k, spin in self._skill_inputs.items():
            spin.setValue(skill.get(k, 200))
        for k, spin in self._bonus_inputs.items():
            spin.setValue(props.get(k, 0))

        # Markup — apply to all inline spins
        for key in ("Weapon", "Ammo", "Amplifier", "Scope", "Sight",
                     "ScopeSight", "Absorber", "Matrix", "Implant",
                     "ArmorSet", "PlateSet", "HealingTool"):
            spin = self._markup_spins.get(key)
            if spin:
                spin.setValue(markup.get(key, 100))

        # Accessories
        self._clothing_items = list(gear.get("Clothing") or [])
        self._consumable_items = [
            ({"Name": e} if isinstance(e, str) else e)
            for e in (gear.get("Consumables") or [])
        ]
        pet = gear.get("Pet") or {}
        self._pet_field.set_value(pet.get("Name") or "")
        self._current_pet_effect = pet.get("Effect")

        # Populate ring fields from clothing
        left_ring = next(
            (c for c in self._clothing_items
             if _is_ring_slot(c.get("Slot", "")) and c.get("Side") == "Left"),
            None,
        )
        right_ring = next(
            (c for c in self._clothing_items
             if _is_ring_slot(c.get("Slot", "")) and c.get("Side") == "Right"),
            None,
        )
        self._left_ring_field.set_value(left_ring["Name"] if left_ring else "")
        self._right_ring_field.set_value(right_ring["Name"] if right_ring else "")

        self._refresh_clothing_list()
        self._refresh_consumables_list()
        self._refresh_pet_effects()

        # Set bars
        self._active_set_indices = {"Weapon": 0, "Armor": 0, "Healing": 0, "Accessories": 0}
        sets = loadout.get("Sets") or {}
        for section in ("Weapon", "Armor", "Healing", "Accessories"):
            section_sets = sets.get(section) or []
            # Find default set
            for i, entry in enumerate(section_sets):
                if entry.get("isDefault"):
                    self._active_set_indices[section] = i
                    break
            self._refresh_set_bar(section)

        # Update weapon field visibility + markup while still in _applying mode
        # so that signals from these updates don't set _dirty.
        self._update_weapon_fields()
        self._update_markup("ArmorSet", self._armor_set_field.current_value())
        self._update_markup("PlateSet", self._plate_field.current_value())
        self._update_markup("HealingTool", self._heal_field.current_value())

        self._applying = False
        self._dirty = False

        self._on_gear_changed()

    # ------------------------------------------------------------------
    # Accessories helpers
    # ------------------------------------------------------------------

    def _refresh_clothing_list(self):
        layout = self._clothing_list_layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        non_ring = [c for c in self._clothing_items if not _is_ring_slot(c.get("Slot", ""))]
        if not non_ring:
            lbl = QLabel("No clothing selected.")
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-style: italic;")
            layout.addWidget(lbl)
            return

        for entry in non_ring:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            name_lbl = QLabel(entry.get("Name", "?"))
            slot_lbl = QLabel(entry.get("Slot", ""))
            slot_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            rl.addWidget(name_lbl)
            rl.addWidget(slot_lbl)
            rl.addStretch()
            rm_btn = QPushButton("Remove")
            rm_btn.setFixedHeight(20)
            rm_btn.setStyleSheet("padding: 1px 6px; font-size: 11px;")
            rm_btn.clicked.connect(
                lambda _, n=entry.get("Name", ""), s=entry.get("Slot", ""):
                    self._remove_clothing(n, s)
            )
            rl.addWidget(rm_btn)
            layout.addWidget(row)

    def _refresh_consumables_list(self):
        layout = self._consumable_list_layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        if not self._consumable_items:
            lbl = QLabel("No consumables selected.")
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-style: italic;")
            layout.addWidget(lbl)
            return

        for entry in self._consumable_items:
            name = entry.get("Name", entry) if isinstance(entry, dict) else str(entry)
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.addWidget(QLabel(name))
            rl.addStretch()
            rm_btn = QPushButton("Remove")
            rm_btn.setFixedHeight(20)
            rm_btn.setStyleSheet("padding: 1px 6px; font-size: 11px;")
            rm_btn.clicked.connect(lambda _, n=name: self._remove_consumable(n))
            rl.addWidget(rm_btn)
            layout.addWidget(row)

    def _refresh_pet_effects(self):
        layout = self._pet_effects_layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        pet_name = self._pet_field.current_value()
        if not pet_name:
            lbl = QLabel("Select a pet to view abilities.")
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-style: italic;")
            layout.addWidget(lbl)
            return

        pets = self._entity_data.get("pets", [])
        pet = next((p for p in pets if p.get("Name") == pet_name), None)
        effects = (pet.get("Effects") or []) if pet else []

        if not effects:
            lbl = QLabel("No abilities available for this pet.")
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-style: italic;")
            layout.addWidget(lbl)
            return

        grid = QGridLayout()
        grid.setSpacing(4)
        cols = 3
        for i, effect in enumerate(effects):
            ename = effect.get("Name") or f"Effect {i + 1}"
            props = effect.get("Properties") or {}
            vals = effect.get("Values") or {}
            strength = props.get("Strength") or vals.get("Strength") or vals.get("Value") or 0
            unit = props.get("Unit", "")
            upkeep = props.get("NutrioConsumptionPerHour")
            level = (props.get("Unlock") or {}).get("Level")
            effect_key = f"{ename}::{strength}"

            is_active = self._current_pet_effect in (effect_key, ename)
            btn = QPushButton()
            btn.setMinimumHeight(60)
            lines = [ename]
            lines.append(f"Strength: {strength}{unit}" if strength else "Strength: —")
            lines.append(f"Upkeep: {upkeep}/h" if upkeep is not None else "Upkeep: N/A")
            if level is not None:
                lines.append(f"Unlock: Lv {level}")
            btn.setText("\n".join(lines))
            btn.setStyleSheet(
                f"text-align: left; padding: 8px 8px; font-size: 11px; "
                f"background-color: {ACCENT if is_active else SECONDARY}; "
                f"color: {MAIN_DARK if is_active else TEXT};"
            )
            btn.clicked.connect(lambda _, ek=effect_key: self._toggle_pet_effect(ek))
            r, c = divmod(i, cols)
            grid.addWidget(btn, r, c)

        container = QWidget()
        container.setLayout(grid)
        layout.addWidget(container)

    def _add_clothing_by_name(self, name: str):
        """Add clothing item by name, looking up its slot from entity data."""
        all_clothing = self._entity_data.get("clothing", [])
        item = next((c for c in all_clothing if c.get("Name") == name), None)
        if not item:
            return
        slot = item.get("Properties", {}).get("Slot", "Unknown")
        if _is_ring_slot(slot):
            return  # Use ring fields instead

        # Replace if same slot (unless Unknown)
        if slot and slot != "Unknown":
            self._clothing_items = [
                c for c in self._clothing_items
                if c.get("Slot") != slot or _is_ring_slot(c.get("Slot", ""))
            ]
        self._clothing_items.append({"Name": name, "Slot": slot})
        self._clothing_search.clear_selection()
        self._refresh_clothing_list()
        self._schedule_recalc()

    def _remove_clothing(self, name: str, slot: str):
        self._clothing_items = [
            c for c in self._clothing_items
            if not (c.get("Name") == name and c.get("Slot") == slot)
        ]
        self._refresh_clothing_list()
        self._schedule_recalc()

    def _add_consumable_by_name(self, name: str):
        # Avoid duplicates
        if any(c.get("Name") == name for c in self._consumable_items):
            return
        self._consumable_items.append({"Name": name})
        self._consumable_search.clear_selection()
        self._refresh_consumables_list()
        self._schedule_recalc()

    def _remove_consumable(self, name: str):
        self._consumable_items = [c for c in self._consumable_items if c.get("Name") != name]
        self._refresh_consumables_list()
        self._schedule_recalc()

    def _set_ring(self, side: str, name: str):
        """Set a ring (Left or Right) — updates clothing list."""
        # Remove existing ring for this side
        self._clothing_items = [
            c for c in self._clothing_items
            if not (_is_ring_slot(c.get("Slot", "")) and c.get("Side") == side)
        ]
        if name:
            all_clothing = self._entity_data.get("clothing", [])
            item = next((c for c in all_clothing if c.get("Name") == name), None)
            slot = item.get("Properties", {}).get("Slot", "Ring") if item else "Ring"
            self._clothing_items.append({"Name": name, "Slot": slot, "Side": side})
        self._schedule_recalc()

    def _on_pet_changed(self, _text: str):
        if self._applying:
            return
        self._current_pet_effect = None
        self._refresh_pet_effects()
        self._schedule_recalc()

    def _toggle_pet_effect(self, effect_key: str):
        if self._current_pet_effect == effect_key:
            self._current_pet_effect = None
        else:
            self._current_pet_effect = effect_key
        self._refresh_pet_effects()
        self._schedule_recalc()

    # ------------------------------------------------------------------
    # Stats display
    # ------------------------------------------------------------------

    def _update_stats_display(self, stats):
        if not stats:
            return

        # (attribute, suffix, formatter)
        # Formatters: None = auto, "pec" = 4dp PEC, "pct" = ×100 %, "pct_raw" = raw %,
        #             "hit" = X.X/10.0, "int" = integer, "str" = string as-is
        STAT_DEFS: dict[str, tuple[str, str, str | None]] = {
            # Tier-1
            "Efficiency": ("efficiency", "%", "pct_raw"),
            "DPS": ("dps", "", None),
            "DPP": ("dpp", "", None),
            # Offensive
            "Total Damage": ("total_damage", "", None),
            "Effective Damage": ("effective_damage", "", None),
            "Crit Chance": ("crit_chance", "%", "pct"),
            "Crit Damage": ("crit_damage", "%", "pct"),
            "Range": ("range", " m", None),
            "Reload": ("reload", " s", None),
            "Cost": ("cost", " PEC", "pec"),
            # Economy
            "Decay": ("decay", " PEC", "pec"),
            "Ammo Burn": ("ammo_burn", "", "int"),
            "Weapon Cost": ("weapon_cost", " PEC", "pec"),
            "Total Uses": ("lowest_total_uses", "", "int"),
            # Defense
            "Armor Defense": ("armor_defense", "", None),
            "Plate Defense": ("plate_defense", "", None),
            "Total Defense": ("total_defense", "", None),
            "Top Types": ("top_defense_types", "", "str"),
            "Total Absorption": ("total_absorption", " HP", None),
            "Block Chance": ("block_chance", "%", "pct_raw"),
            # Healing
            "Total Heal": ("total_heal", "", None),
            "Effective Heal": ("effective_heal", "", None),
            "HPS": ("hps", "", None),
            "HPP": ("hpp", "", None),
            "Heal Reload": ("heal_reload", " s", None),
            "Heal Total Uses": ("heal_total_uses", "", "int"),
            # Skill
            "Hit Ability": ("hit_ability", "/10.0", "hit"),
            "Crit Ability": ("crit_ability", "/10.0", "hit"),
        }

        def _fmt(val, suffix, fmt):
            if val is None:
                return "-"
            if fmt == "str":
                return str(val) if val else "-"
            if fmt == "int":
                return f"{int(val)}{suffix}" if val else "-"
            if fmt == "pec":
                return f"{val:.4f}{suffix}" if val else "-"
            if fmt == "pct":
                return f"{val * 100:.1f}{suffix}" if val else "-"
            if fmt == "pct_raw":
                return f"{val:.1f}{suffix}" if val else "-"
            if fmt == "hit":
                return f"{val:.1f}{suffix}" if val else "-"
            if isinstance(val, float):
                return f"{val:.2f}{suffix}"
            return f"{val}{suffix}"

        all_labels = (
            self._tier1_stats, self._off_stats, self._econ_stats,
            self._heal_stats, self._def_stats, self._skill_stats,
        )
        for labels_dict in all_labels:
            for display_name, vlbl in labels_dict.items():
                defn = STAT_DEFS.get(display_name)
                if not defn:
                    continue
                attr, suffix, fmt = defn
                val = getattr(stats, attr, None)
                vlbl.setText(_fmt(val, suffix, fmt))

    # ------------------------------------------------------------------
    # Loadout management
    # ------------------------------------------------------------------

    def _on_loadout_selected(self, index, *, _prompt=True):
        if index < 0 or index >= len(self._loadouts):
            return

        # Prompt if the previous loadout has unsaved changes (user-initiated only)
        if _prompt and self._dirty and self._current_loadout:
            label = _get_loadout_label(self._current_loadout)
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f'"{label}" has unsaved changes.\n\nSave before switching?',
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                # Revert combo to the previous loadout
                prev_idx = self._loadouts.index(self._current_loadout) \
                    if self._current_loadout in self._loadouts else -1
                if prev_idx >= 0:
                    self._loadout_combo.blockSignals(True)
                    self._loadout_combo.setCurrentIndex(prev_idx)
                    self._loadout_combo.blockSignals(False)
                return
            if reply == QMessageBox.StandardButton.Save:
                self._save_timer.stop()
                self._auto_save()

        self._dirty = False
        self._current_loadout = self._loadouts[index]
        self._apply_loadout_to_ui(self._current_loadout)

    def _update_loadout_combo_label(self):
        """Refresh the current loadout's combo text from live UI state."""
        idx = self._loadout_combo.currentIndex()
        if idx < 0 or not self._current_loadout:
            return
        loadout = self._build_loadout_from_ui()
        label = _get_loadout_label(loadout)
        active_id = self._config.active_loadout_id
        if active_id and self._current_loadout.get("Id") == active_id:
            label = f"\u2605 {label}"
        self._loadout_combo.setItemText(idx, label)

    def _on_new_loadout(self):
        from ...loadout.models import create_empty_loadout
        new_loadout = create_empty_loadout()
        new_loadout["Name"] = f"Loadout {len(self._loadouts) + 1}"
        self._loadouts.append(new_loadout)
        self._loadout_combo.addItem(_get_loadout_label(new_loadout))
        self._loadout_combo.setCurrentIndex(len(self._loadouts) - 1)

    # ------------------------------------------------------------------
    # Export / Import / Clone / Share
    # ------------------------------------------------------------------

    def _on_export(self):
        """Export the current loadout to a JSON file."""
        if not self._current_loadout:
            return
        loadout = self._build_loadout_from_ui()
        # Preserve server metadata
        for key in ("Id", "share_code", "public"):
            if self._current_loadout.get(key) is not None:
                loadout[key] = self._current_loadout[key]

        default_name = (_get_loadout_label(loadout) or "loadout") + ".json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Loadout", default_name,
            "JSON files (*.json);;All files (*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(
                json.dumps(loadout, indent=2, default=str), encoding="utf-8",
            )
            log.info("Exported loadout to %s", path)
        except Exception as e:
            log.error("Export failed: %s", e)
            QMessageBox.warning(self, "Export Failed", str(e))

    def _on_import(self):
        """Import a loadout from a JSON file or a share code."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Import Loadout")
        dlg_layout = QVBoxLayout(dlg)

        dlg_layout.addWidget(QLabel("Import from a JSON file or paste a share code / URL:"))

        code_row = QHBoxLayout()
        code_input = QLineEdit()
        code_input.setPlaceholderText("Share code or URL (e.g. a1b2c3d4e5)")
        code_row.addWidget(code_input)
        fetch_btn = QPushButton("Fetch")
        code_row.addWidget(fetch_btn)
        dlg_layout.addLayout(code_row)

        file_btn = QPushButton("Import from File...")
        dlg_layout.addWidget(file_btn)

        status_label = QLabel("")
        status_label.setWordWrap(True)
        dlg_layout.addWidget(status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.reject)
        dlg_layout.addWidget(buttons)

        def on_import_file():
            path, _ = QFileDialog.getOpenFileName(
                dlg, "Import Loadout", "",
                "JSON files (*.json);;All files (*)",
            )
            if not path:
                return
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    status_label.setText("Invalid loadout file.")
                    return
                self._add_imported_loadout(data)
                status_label.setText(f"Imported: {_get_loadout_label(data)}")
            except Exception as e:
                status_label.setText(f"Error: {e}")

        def on_fetch_code():
            raw = code_input.text().strip()
            if not raw:
                return
            # Extract share code from URL or raw input
            code = raw.rsplit("/", 1)[-1].strip()
            if not code:
                return
            status_label.setText("Fetching...")
            fetch_btn.setEnabled(False)

            def on_done():
                fetch_btn.setEnabled(True)
                result = getattr(self, "_pending_shared_import", None)
                code_val = getattr(self, "_pending_shared_code", "")
                self._pending_shared_import = None
                self._pending_shared_code = None
                if result:
                    loadout_data = result.get("data", result)
                    if isinstance(loadout_data, str):
                        loadout_data = json.loads(loadout_data)
                    # Create a copy (not linked to original)
                    loadout_data["Id"] = str(uuid.uuid4())
                    original_name = loadout_data.get("Name") or result.get("name", "")
                    loadout_data["Name"] = f"Copy of {original_name}" if original_name else "Imported Loadout"
                    self._add_imported_loadout(loadout_data)
                    status_label.setText(f"Imported: {_get_loadout_label(loadout_data)}")
                else:
                    status_label.setText(f"Share code '{code_val}' not found.")

            def fetch():
                try:
                    result = self._nexus_client.get_shared_loadout(code)
                    self._pending_shared_import = result
                    self._pending_shared_code = code
                except Exception as e:
                    log.error("Fetch shared loadout failed: %s", e)
                    self._pending_shared_import = None
                    self._pending_shared_code = code
                QTimer.singleShot(0, on_done)

            threading.Thread(target=fetch, daemon=True).start()

        fetch_btn.clicked.connect(on_fetch_code)
        file_btn.clicked.connect(on_import_file)
        dlg.exec()

    def _add_imported_loadout(self, data: dict):
        """Add an imported loadout to the list and select it."""
        # Generate a new local ID if missing
        if not data.get("Id"):
            data["Id"] = str(uuid.uuid4())
        # Strip server-specific fields from the copy
        data.pop("share_code", None)
        data.pop("public", None)

        self._loadouts.append(data)
        self._loadout_combo.addItem(_get_loadout_label(data))
        self._loadout_combo.setCurrentIndex(len(self._loadouts) - 1)
        self._save_to_cache()

        # Push to server if authenticated
        if self._oauth.is_authenticated():
            payload = _wrap_for_server(data)
            def push():
                try:
                    result = self._nexus_client.create_loadout(payload)
                    if result:
                        new_record = _unwrap_server_record(result)
                        new_id = new_record.get("Id")
                        if new_id:
                            data["Id"] = new_id
                except Exception as e:
                    log.error("Import push failed: %s", e)
            threading.Thread(target=push, daemon=True).start()

    def _on_clone(self):
        """Clone the current loadout (deep copy with new ID)."""
        if not self._current_loadout:
            return

        # Save pending changes first
        if self._dirty:
            self._save_timer.stop()
            self._auto_save()

        clone = copy.deepcopy(self._current_loadout)
        clone["Id"] = str(uuid.uuid4())
        original_name = clone.get("Name") or _get_loadout_label(self._current_loadout)
        clone["Name"] = f"{original_name} (copy)"
        # New clone is not shared
        clone.pop("share_code", None)
        clone.pop("public", None)

        # Push to server if authenticated
        if self._oauth.is_authenticated():
            payload = _wrap_for_server(clone)
            def push():
                try:
                    result = self._nexus_client.create_loadout(payload)
                    if result:
                        new_record = _unwrap_server_record(result)
                        new_id = new_record.get("Id")
                        if new_id:
                            clone["Id"] = new_id
                except Exception as e:
                    log.error("Clone push failed: %s", e)
            threading.Thread(target=push, daemon=True).start()

        self._loadouts.append(clone)
        self._loadout_combo.addItem(_get_loadout_label(clone))
        self._loadout_combo.setCurrentIndex(len(self._loadouts) - 1)
        self._save_to_cache()

    def _on_delete(self):
        """Delete the current loadout with confirmation."""
        if not self._current_loadout:
            return

        label = _get_loadout_label(self._current_loadout)
        reply = QMessageBox.warning(
            self, "Delete Loadout",
            f'Are you sure you want to delete "{label}"?\n\nThis cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        loadout_id = self._current_loadout.get("Id")
        idx = self._loadout_combo.currentIndex()

        # Delete from server if authenticated and has a server ID
        if loadout_id and self._oauth.is_authenticated():
            def delete_remote():
                try:
                    self._nexus_client.delete_loadout(loadout_id)
                except Exception as e:
                    log.error("Delete from server failed: %s", e)
            threading.Thread(target=delete_remote, daemon=True).start()

        # Remove from local list
        self._dirty = False
        self._save_timer.stop()
        if loadout_id:
            self._saved_last_update.pop(loadout_id, None)
        if 0 <= idx < len(self._loadouts):
            self._loadouts.pop(idx)

        self._save_to_cache()

        # Update combo
        self._loadout_combo.blockSignals(True)
        self._loadout_combo.removeItem(idx)
        self._loadout_combo.blockSignals(False)

        if self._loadouts:
            new_idx = min(idx, len(self._loadouts) - 1)
            self._loadout_combo.setCurrentIndex(new_idx)
            self._on_loadout_selected(new_idx, _prompt=False)
        else:
            self._current_loadout = None

    def _on_share(self):
        """Toggle sharing for the current loadout. Shows a dialog with the share URL."""
        if not self._current_loadout:
            return
        if not self._oauth.is_authenticated():
            QMessageBox.information(
                self, "Share", "You must be logged in to share loadouts.",
            )
            return

        loadout_id = self._current_loadout.get("Id")
        if not loadout_id:
            QMessageBox.information(
                self, "Share", "Save the loadout first before sharing.",
            )
            return

        # Save pending changes first
        if self._dirty:
            self._save_timer.stop()
            self._auto_save()

        is_public = bool(self._current_loadout.get("public", False))
        share_code = self._current_loadout.get("share_code", "")

        dlg = QDialog(self)
        dlg.setWindowTitle("Share Loadout")
        dlg_layout = QVBoxLayout(dlg)

        public_check = QCheckBox("Public link")
        public_check.setChecked(is_public)
        dlg_layout.addWidget(public_check)

        url_row = QHBoxLayout()
        url_label = QLineEdit()
        url_label.setReadOnly(True)
        url_row.addWidget(url_label)
        copy_btn = QPushButton("Copy")
        url_row.addWidget(copy_btn)
        dlg_layout.addLayout(url_row)

        status_label = QLabel("")
        status_label.setWordWrap(True)
        dlg_layout.addWidget(status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.reject)
        dlg_layout.addWidget(buttons)

        base_url = self._config.nexus_base_url.rstrip("/")

        def update_url_display():
            code = self._current_loadout.get("share_code", "")
            if public_check.isChecked() and code:
                url = f"{base_url}/tools/loadouts/{code}"
                url_label.setText(url)
                url_label.setEnabled(True)
                copy_btn.setEnabled(True)
            else:
                url_label.setText("")
                url_label.setEnabled(False)
                copy_btn.setEnabled(not public_check.isChecked())

        def on_toggle(checked):
            status_label.setText("Saving...")
            public_check.setEnabled(False)

            def push():
                try:
                    result = self._nexus_client.save_loadout(loadout_id, {
                        "name": self._current_loadout.get("Name", "New Loadout"),
                        "data": self._current_loadout,
                        "public": checked,
                    })
                    if result:
                        self._current_loadout["public"] = result.get("public", checked)
                        self._current_loadout["share_code"] = result.get("share_code", "")
                except Exception as e:
                    log.error("Share toggle failed: %s", e)
                QTimer.singleShot(0, on_toggle_done)

            def on_toggle_done():
                public_check.setEnabled(True)
                update_url_display()
                if self._current_loadout.get("share_code") and checked:
                    status_label.setText("Sharing enabled.")
                elif not checked:
                    status_label.setText("Sharing disabled.")
                else:
                    status_label.setText("Failed to enable sharing.")

            threading.Thread(target=push, daemon=True).start()

        def on_copy():
            text = url_label.text()
            if text:
                QApplication.clipboard().setText(text)
                status_label.setText("Copied to clipboard.")

        public_check.toggled.connect(on_toggle)
        copy_btn.clicked.connect(on_copy)
        update_url_display()
        dlg.exec()

    def _auto_save(self):
        """Auto-save: sync current loadout back into _loadouts, cache locally, push to server."""
        if not self._current_loadout:
            return
        self._dirty = False
        idx = self._loadout_combo.currentIndex()
        loadout = self._build_loadout_from_ui()
        # Preserve server ID
        if self._current_loadout.get("Id"):
            loadout["Id"] = self._current_loadout["Id"]
        self._current_loadout.update(loadout)
        if 0 <= idx < len(self._loadouts):
            self._loadouts[idx] = self._current_loadout

        # Always cache locally
        self._save_to_cache()

        # Sync to server if authenticated
        if self._oauth.is_authenticated():
            lo = copy.deepcopy(self._current_loadout)
            payload = _wrap_for_server(lo)
            self._save_in_flight = True
            def push():
                try:
                    if lo.get("Id"):
                        result = self._nexus_client.save_loadout(lo["Id"], payload)
                        if result and "last_update" in result:
                            self._saved_last_update[lo["Id"]] = result["last_update"]
                    else:
                        result = self._nexus_client.create_loadout(payload)
                        if result:
                            new_record = _unwrap_server_record(result)
                            new_id = new_record.get("Id")
                            if new_id:
                                lo["Id"] = new_id
                                self._current_loadout["Id"] = new_id
                                if "last_update" in result:
                                    self._saved_last_update[new_id] = result["last_update"]
                except Exception as e:
                    log.error("Auto-save push failed: %s", e)
                finally:
                    self._save_in_flight = False
            threading.Thread(target=push, daemon=True).start()

    def _save_to_cache(self):
        """Persist all loadouts to local JSON cache."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps(self._loadouts, default=str, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.error("Cache write failed: %s", e)

    def _load_from_cache(self) -> list[dict]:
        """Load loadouts from local JSON cache."""
        try:
            if self._cache_path.exists():
                return json.loads(self._cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.error("Cache read failed: %s", e)
        return []

    def _on_save(self):
        """Manual save — triggers an immediate auto-save."""
        self._save_timer.stop()
        self._auto_save()

    def _on_refresh(self):
        if self._oauth.is_authenticated():
            def fetch():
                loadouts = self._nexus_client.get_loadouts()
                if loadouts is not None:
                    for rec in loadouts:
                        lo_id = rec.get("id") or rec.get("Id")
                        if lo_id and "last_update" in rec:
                            self._saved_last_update[lo_id] = rec["last_update"]
                    self._loadouts = _unwrap_server_list(loadouts)
                    self._save_to_cache()
                    from PyQt6.QtCore import QMetaObject, Qt as QtConst
                    QMetaObject.invokeMethod(self, "_update_loadout_list",
                                             QtConst.ConnectionType.QueuedConnection)
            threading.Thread(target=fetch, daemon=True).start()
        else:
            # Offline: load from local cache
            cached = self._load_from_cache()
            if cached:
                self._loadouts = cached
                self._update_loadout_list()

    @pyqtSlot()
    def _update_loadout_list(self):
        self._loadout_combo.blockSignals(True)
        self._loadout_combo.clear()
        active_id = self._config.active_loadout_id
        accent_color = QColor(ACCENT)
        for i, lo in enumerate(self._loadouts):
            label = _get_loadout_label(lo)
            if lo.get("Id") and lo["Id"] == active_id:
                label = f"\u2605 {label}"  # Star prefix for active loadout
            self._loadout_combo.addItem(label)
            if lo.get("Id") and lo["Id"] == active_id:
                self._loadout_combo.setItemData(i, QBrush(accent_color), Qt.ItemDataRole.ForegroundRole)
        self._loadout_combo.blockSignals(False)

        if not self._loadouts:
            return

        # Restore last-active loadout from config
        target_idx = 0
        if active_id:
            for i, lo in enumerate(self._loadouts):
                if lo.get("Id") == active_id:
                    target_idx = i
                    break

        self._loadout_combo.setCurrentIndex(target_idx)
        self._on_loadout_selected(target_idx, _prompt=False)

    def _refresh_loadout_combo_styling(self):
        """Re-apply active loadout highlighting without changing selection."""
        active_id = self._config.active_loadout_id
        accent_color = QColor(ACCENT)
        default_color = QColor(TEXT)
        self._loadout_combo.blockSignals(True)
        for i, lo in enumerate(self._loadouts):
            label = _get_loadout_label(lo)
            is_active = lo.get("Id") and lo["Id"] == active_id
            if is_active:
                label = f"\u2605 {label}"
            self._loadout_combo.setItemText(i, label)
            self._loadout_combo.setItemData(
                i, QBrush(accent_color if is_active else default_color),
                Qt.ItemDataRole.ForegroundRole,
            )
        self._loadout_combo.blockSignals(False)

    def _on_set_active(self):
        if self._current_loadout:
            self._config.active_loadout_id = self._current_loadout.get("Id")
            from ...core.config import save_config
            save_config(self._config, self._config_path)
            self._refresh_loadout_combo_styling()
            self._publish_active_loadout()

    def _publish_active_loadout(self):
        """Publish active loadout change event for the hunt tracker."""
        if not self._event_bus:
            return
        loadout = self.get_active_loadout()
        if not loadout:
            return
        weapon_name = (loadout.get("Gear", {}).get("Weapon", {}).get("Name") or "").strip()
        stats = None
        if self._calculator and self._entity_data:
            try:
                stats = self._calculator.evaluate(loadout, self._entity_data)
            except Exception:
                pass
        from ...core.constants import EVENT_ACTIVE_LOADOUT_CHANGED
        self._event_bus.publish(EVENT_ACTIVE_LOADOUT_CHANGED, {
            "loadout": loadout,
            "weapon_name": weapon_name,
            "stats": stats,
        })

    def _on_auth_changed(self, state):
        if state.authenticated:
            self._on_refresh()

    # ------------------------------------------------------------------
    # Periodic polling & conflict resolution
    # ------------------------------------------------------------------

    def _poll_loadouts(self):
        """Fetch loadouts from server and merge with local state."""
        if not self._oauth.is_authenticated():
            return

        self._poll_timer.stop()  # Pause during fetch + merge

        def fetch():
            try:
                remote = self._nexus_client.get_loadouts()
                if remote is not None:
                    timestamps = {}
                    for rec in remote:
                        lo_id = rec.get("id") or rec.get("Id")
                        if lo_id and "last_update" in rec:
                            timestamps[lo_id] = rec["last_update"]
                    self._pending_remote = _unwrap_server_list(remote)
                    self._pending_remote_timestamps = timestamps
                    from PyQt6.QtCore import QMetaObject, Qt as QtConst
                    QMetaObject.invokeMethod(
                        self, "_merge_remote_loadouts",
                        QtConst.ConnectionType.QueuedConnection,
                    )
                else:
                    self._poll_timer.start()
            except Exception as e:
                log.error("Poll fetch failed: %s", e)
                self._poll_timer.start()

        threading.Thread(target=fetch, daemon=True).start()

    @pyqtSlot()
    def _merge_remote_loadouts(self):
        """Merge fetched remote loadouts with local state, asking on conflicts."""
        remote = getattr(self, "_pending_remote", None)
        if remote is None:
            self._poll_timer.start()
            return
        self._pending_remote = None

        remote_by_id = {lo["Id"]: lo for lo in remote if lo.get("Id")}
        current_id = self._current_loadout.get("Id") if self._current_loadout else None
        remote_timestamps = getattr(self, "_pending_remote_timestamps", {})

        # Detect conflict on the currently-edited loadout via last_update
        conflict_resolved_use_remote = False
        if current_id and current_id in remote_by_id:
            remote_lu = remote_timestamps.get(current_id)
            saved_lu = self._saved_last_update.get(current_id)
            if (saved_lu and remote_lu and remote_lu != saved_lu
                    and not self._save_in_flight):
                label = _get_loadout_label(self._current_loadout)
                msg = QMessageBox(self)
                msg.setWindowTitle("Loadout Conflict")
                msg.setText(
                    f'"{label}" has been modified on the server.\n\n'
                    "Keep your local changes or use the server version?"
                )
                keep_btn = msg.addButton("Keep Local", QMessageBox.ButtonRole.AcceptRole)
                msg.addButton("Use Server", QMessageBox.ButtonRole.DestructiveRole)
                msg.exec()
                conflict_resolved_use_remote = msg.clickedButton() is not keep_btn

        # Update tracked timestamps to latest remote values
        self._saved_last_update.update(remote_timestamps)

        # Build merged list: remote order, with conflict resolution applied
        merged: list[dict] = []
        seen_ids: set = set()
        for lo in remote:
            lo_id = lo.get("Id")
            if lo_id:
                seen_ids.add(lo_id)
                if lo_id == current_id and not conflict_resolved_use_remote:
                    merged.append(self._current_loadout)
                else:
                    merged.append(lo)

        # Keep local-only loadouts (not yet pushed to server)
        for lo in self._loadouts:
            if not lo.get("Id"):
                merged.append(lo)

        self._loadouts = merged
        self._save_to_cache()

        # Refresh combo while preserving selection
        active_id = self._config.active_loadout_id
        accent_color = QColor(ACCENT)
        self._loadout_combo.blockSignals(True)
        self._loadout_combo.clear()
        for i, lo in enumerate(self._loadouts):
            label = _get_loadout_label(lo)
            is_active = lo.get("Id") and lo["Id"] == active_id
            if is_active:
                label = f"\u2605 {label}"
            self._loadout_combo.addItem(label)
            if is_active:
                self._loadout_combo.setItemData(i, QBrush(accent_color), Qt.ItemDataRole.ForegroundRole)
        self._loadout_combo.blockSignals(False)

        # Restore selection
        restored = False
        if current_id:
            for i, lo in enumerate(self._loadouts):
                if lo.get("Id") == current_id:
                    self._loadout_combo.setCurrentIndex(i)
                    self._current_loadout = lo
                    if conflict_resolved_use_remote:
                        self._apply_loadout_to_ui(lo)
                    restored = True
                    break
        if not restored and self._loadouts:
            self._loadout_combo.setCurrentIndex(0)
            self._on_loadout_selected(0, _prompt=False)

        self._poll_timer.start()  # Resume polling

    def cleanup(self):
        """Stop timers and flush pending saves before shutdown."""
        self._poll_timer.stop()
        self._recalc_timer.stop()
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._auto_save()  # Flush immediately

    def get_active_loadout(self) -> dict | None:
        if self._config.active_loadout_id:
            for lo in self._loadouts:
                if lo.get("Id") == self._config.active_loadout_id:
                    return lo
        return self._current_loadout
