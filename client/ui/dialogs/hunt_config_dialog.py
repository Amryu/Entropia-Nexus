"""Hunt configuration dialog — loadout, enhancers, tools, and exclusions."""

import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QComboBox, QSpinBox, QGridLayout,
    QGroupBox, QLineEdit, QCheckBox, QScrollArea, QDoubleSpinBox,
    QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt

from ..theme import (
    PRIMARY, SECONDARY, HOVER, TEXT, TEXT_MUTED, ACCENT, ACCENT_HOVER,
    BORDER, SUCCESS, ERROR,
)
from ...core.constants import EVENT_TOOL_COST_FILTER_CHANGED
from ...core.config import save_config
from ...core.logger import get_logger

log = get_logger("HuntConfig")


class HuntConfigDialog(QDialog):
    """Dialog for configuring the hunting session loadout, enhancers, and tools."""

    def __init__(self, *, config, db, event_bus, parent=None):
        super().__init__(parent)
        self._config = config
        self._db = db
        self._event_bus = event_bus

        self.setWindowTitle("Hunt Configuration")
        self.setMinimumWidth(500)
        self.setMinimumHeight(450)
        self.setStyleSheet(
            f"QDialog {{ background: {PRIMARY}; color: {TEXT}; }}"
            f"QTabWidget::pane {{ border: 1px solid {BORDER}; background: {PRIMARY}; }}"
            f"QTabBar::tab {{ background: {SECONDARY}; color: {TEXT_MUTED}; padding: 8px 16px;"
            f"  border: 1px solid {BORDER}; border-bottom: none; }}"
            f"QTabBar::tab:selected {{ background: {PRIMARY}; color: {ACCENT}; font-weight: bold; }}"
            f"QGroupBox {{ border: 1px solid {BORDER}; border-radius: 4px;"
            f"  margin-top: 8px; padding-top: 16px; color: {TEXT}; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; }}"
            f"QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {{"
            f"  background: {SECONDARY}; color: {TEXT}; border: 1px solid {BORDER};"
            f"  border-radius: 3px; padding: 2px 4px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        tabs = QTabWidget()
        tabs.addTab(self._build_loadout_tab(), "Loadout")
        tabs.addTab(self._build_enhancers_tab(), "Enhancers")
        tabs.addTab(self._build_tools_tab(), "Tools")
        tabs.addTab(self._build_exclusions_tab(), "Exclusions")
        layout.addWidget(tabs)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: {SECONDARY}; color: {TEXT};"
            f"  border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 24px; }}"
            f"QPushButton:hover {{ background: {HOVER}; }}"
        )
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    # -- Loadout tab ----------------------------------------------------------

    def _build_loadout_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # Loadout selector
        layout.addWidget(QLabel("Select active loadout:"))
        self._loadout_combo = QComboBox()
        self._loadout_combo.setFixedHeight(28)
        self._loadout_map = {}  # index → loadout dict

        cache_path = Path(__file__).parent.parent.parent / "data" / "cache" / "loadouts.json"
        if cache_path.exists():
            try:
                loadouts = json.loads(cache_path.read_text(encoding="utf-8"))
                for i, lo in enumerate(loadouts):
                    name = lo.get("Name", f"Loadout {i+1}")
                    weapon = lo.get("Gear", {}).get("Weapon", {}).get("Name", "")
                    label = f"{name} — {weapon}" if weapon else name
                    self._loadout_combo.addItem(label)
                    self._loadout_map[i] = lo

                # Select the active loadout
                active_id = self._config.active_loadout_id
                if active_id:
                    for i, lo in enumerate(loadouts):
                        if lo.get("Id") == active_id:
                            self._loadout_combo.setCurrentIndex(i)
                            break
            except Exception as e:
                log.error("Failed to load loadouts: %s", e)

        layout.addWidget(self._loadout_combo)

        # Info area
        self._loadout_info = QLabel("Select a loadout to see details.")
        self._loadout_info.setWordWrap(True)
        self._loadout_info.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; padding: 8px;"
            f"background: {SECONDARY}; border: 1px solid {BORDER}; border-radius: 4px;"
        )
        layout.addWidget(self._loadout_info)

        self._loadout_combo.currentIndexChanged.connect(self._on_loadout_selected)
        if self._loadout_combo.count() > 0:
            self._on_loadout_selected(self._loadout_combo.currentIndex())

        layout.addStretch()
        return tab

    def _on_loadout_selected(self, index):
        lo = self._loadout_map.get(index)
        if not lo:
            return
        gear = lo.get("Gear", {})
        weapon = gear.get("Weapon", {}).get("Name", "None")
        healing = gear.get("Healing", {}).get("Name", "None")
        armor_set = gear.get("Armor", {}).get("Set", "None")
        enh = gear.get("Weapon", {}).get("Enhancers", {})
        enh_str = ", ".join(f"{k}: {v}" for k, v in enh.items() if v) or "None"

        self._loadout_info.setText(
            f"Weapon: {weapon}\n"
            f"Healing: {healing}\n"
            f"Armor: {armor_set}\n"
            f"Weapon Enhancers: {enh_str}"
        )

    # -- Enhancers tab --------------------------------------------------------

    def _build_enhancers_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel("Set your current enhancer counts. These override the loadout's "
                       "values and are decremented automatically when enhancers break.")
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; border: none;")
        layout.addWidget(info)

        self._enhancer_spins = {}

        # Weapon enhancers
        weapon_group = QGroupBox("Weapon")
        wg = QGridLayout(weapon_group)
        for i, (label, key) in enumerate([
            ("Damage", "weapon_damage"),
            ("Economy", "weapon_economy"),
            ("Accuracy", "weapon_accuracy"),
            ("Range", "weapon_range"),
            ("Skill Mod", "weapon_skill_mod"),
        ]):
            wg.addWidget(QLabel(label), i, 0)
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setFixedWidth(70)
            self._enhancer_spins[key] = spin
            wg.addWidget(spin, i, 1)
        layout.addWidget(weapon_group)

        # Armor enhancers
        armor_group = QGroupBox("Armor")
        ag = QGridLayout(armor_group)
        for i, (label, key) in enumerate([
            ("Defense", "armor_defense"),
            ("Durability", "armor_durability"),
        ]):
            ag.addWidget(QLabel(label), i, 0)
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setFixedWidth(70)
            self._enhancer_spins[key] = spin
            ag.addWidget(spin, i, 1)
        layout.addWidget(armor_group)

        # Healing enhancers
        heal_group = QGroupBox("Healing")
        hg = QGridLayout(heal_group)
        for i, (label, key) in enumerate([
            ("Heal", "healing_heal"),
            ("Economy", "healing_economy"),
            ("Skill Mod", "healing_skill_mod"),
        ]):
            hg.addWidget(QLabel(label), i, 0)
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setFixedWidth(70)
            self._enhancer_spins[key] = spin
            hg.addWidget(spin, i, 1)
        layout.addWidget(heal_group)

        layout.addStretch()
        return tab

    # -- Tools tab ------------------------------------------------------------

    def _build_tools_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel("Register additional tools that aren't part of your loadout. "
                       "These will be tracked for cost and damage attribution.")
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; border: none;")
        layout.addWidget(info)

        self._tools_list = QListWidget()
        self._tools_list.setStyleSheet(
            f"QListWidget {{ background: {SECONDARY}; color: {TEXT};"
            f"  border: 1px solid {BORDER}; border-radius: 4px; }}"
            f"QListWidget::item {{ padding: 4px; }}"
        )
        layout.addWidget(self._tools_list, 1)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Tool")
        add_btn.setFixedHeight(28)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: #fff; border: none;"
            f"  border-radius: 4px; padding: 4px 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {ACCENT_HOVER}; }}"
        )
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return tab

    # -- Exclusions tab -------------------------------------------------------

    def _build_exclusions_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel("Excluded tools and categories are not tracked for cost. "
                       "Combat events are still recorded.")
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; border: none;")
        layout.addWidget(info)

        # Mode selector
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Filter mode:"))
        self._filter_mode = QComboBox()
        self._filter_mode.addItems(["Blacklist (exclude listed)", "Whitelist (only listed)"])
        self._filter_mode.setCurrentIndex(
            0 if getattr(self._config, "tool_cost_filter_mode", "blacklist") == "blacklist" else 1
        )
        mode_row.addWidget(self._filter_mode)
        layout.addLayout(mode_row)

        # Tool list
        layout.addWidget(QLabel("Tools:"))
        self._exclusion_list = QListWidget()
        self._exclusion_list.setStyleSheet(
            f"QListWidget {{ background: {SECONDARY}; color: {TEXT};"
            f"  border: 1px solid {BORDER}; border-radius: 4px; }}"
        )
        current_list = getattr(self._config, "tool_cost_filter_list", [])
        for tool in current_list:
            self._exclusion_list.addItem(tool)
        layout.addWidget(self._exclusion_list, 1)

        # Add/remove
        btn_row = QHBoxLayout()
        self._excl_input = QLineEdit()
        self._excl_input.setPlaceholderText("Tool name...")
        self._excl_input.setFixedHeight(28)
        btn_row.addWidget(self._excl_input, 1)

        add_btn = QPushButton("Add")
        add_btn.setFixedHeight(28)
        add_btn.clicked.connect(self._add_exclusion)
        btn_row.addWidget(add_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setFixedHeight(28)
        remove_btn.clicked.connect(self._remove_exclusion)
        btn_row.addWidget(remove_btn)
        layout.addLayout(btn_row)

        layout.addStretch()
        return tab

    def _add_exclusion(self):
        name = self._excl_input.text().strip()
        if name:
            self._exclusion_list.addItem(name)
            self._excl_input.clear()
            self._save_exclusions()

    def _remove_exclusion(self):
        item = self._exclusion_list.currentItem()
        if item:
            self._exclusion_list.takeItem(self._exclusion_list.row(item))
            self._save_exclusions()

    def _save_exclusions(self):
        tools = [self._exclusion_list.item(i).text()
                 for i in range(self._exclusion_list.count())]
        mode = "blacklist" if self._filter_mode.currentIndex() == 0 else "whitelist"
        self._config.tool_cost_filter_mode = mode
        self._config.tool_cost_filter_list = tools
        save_config(self._config, self._config.config_path if hasattr(self._config, 'config_path') else None)
        self._event_bus.publish(EVENT_TOOL_COST_FILTER_CHANGED, None)
