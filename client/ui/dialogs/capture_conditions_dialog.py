"""Dialog for configuring auto-capture trigger conditions.

Shared between screenshots and video clips.  Each has its own tab with
identical controls but separate config fields.  Opened from the settings
page with the relevant tab pre-selected.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QCheckBox, QGridLayout, QTabWidget, QWidget,
    QFrame,
)
from PyQt6.QtCore import Qt

from ...core.config import save_config
from ...core.constants import EVENT_CONFIG_CHANGED
from ...chat_parser.models import GlobalType
from ..theme import TEXT_MUTED, BORDER

# Human-readable labels for each global type
_TYPE_LABELS: dict[str, str] = {
    GlobalType.KILL.value: "Kill",
    GlobalType.TEAM_KILL.value: "Team Kill",
    GlobalType.DEPOSIT.value: "Deposit",
    GlobalType.CRAFT.value: "Craft",
    GlobalType.FISH.value: "Fish",
    GlobalType.RARE_ITEM.value: "Rare Item",
    GlobalType.DISCOVERY.value: "Discovery",
    GlobalType.TIER.value: "Tier",
    GlobalType.EXAMINE.value: "Examine",
    GlobalType.PVP.value: "PvP",
}

# Types where the PED value may be absent or meaningless
_VALUE_OPTIONAL_TYPES = {
    GlobalType.DISCOVERY.value,
    GlobalType.TIER.value,
    GlobalType.RARE_ITEM.value,
    GlobalType.PVP.value,
}


class CaptureConditionsDialog(QDialog):
    """Configure conditions for automatic screenshot / clip triggers.

    Args:
        config: The application config object.
        config_path: Path to the config file for saving.
        event_bus: EventBus for publishing config changes.
        initial_tab: ``0`` for Screenshots, ``1`` for Video Clips.
    """

    def __init__(self, *, config, config_path, event_bus,
                 initial_tab: int = 0, parent=None):
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._event_bus = event_bus

        self.setWindowTitle("Auto-Capture Conditions")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        desc = QLabel(
            "Configure which own-global events trigger automatic captures. "
            "These conditions are checked in addition to the "
            "\"auto on own global\" toggle in Settings."
        )
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Tabs
        self._tabs = QTabWidget()
        self._ss_tab = self._build_tab(
            min_ped=config.screenshot_min_ped,
            global_types=config.screenshot_global_types,
            hof_only=config.screenshot_hof_only,
            cooldown=config.screenshot_cooldown_s,
        )
        self._clip_tab = self._build_tab(
            min_ped=config.clip_min_ped,
            global_types=config.clip_global_types,
            hof_only=config.clip_hof_only,
            cooldown=config.clip_cooldown_s,
        )
        self._tabs.addTab(self._ss_tab["widget"], "Screenshots")
        self._tabs.addTab(self._clip_tab["widget"], "Video Clips")
        self._tabs.setCurrentIndex(initial_tab)
        layout.addWidget(self._tabs)

        # Dialog buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("accentButton")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Tab builder
    # ------------------------------------------------------------------

    def _build_tab(
        self, *,
        min_ped: float,
        global_types: list[str],
        hof_only: bool,
        cooldown: float,
    ) -> dict:
        """Build one conditions tab and return a dict of its widgets."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        # --- HoF only ---
        hof_cb = QCheckBox("Hall of Fame only")
        hof_cb.setChecked(hof_only)
        hof_cb.setToolTip("Only trigger when the global is a Hall of Fame entry")
        layout.addWidget(hof_cb)

        # --- Min PED ---
        grid = QGridLayout()
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 1)
        grid.setHorizontalSpacing(8)

        grid.addWidget(QLabel("Min. PED value:"), 0, 0)
        ped_spin = QDoubleSpinBox()
        ped_spin.setFixedWidth(100)
        ped_spin.setRange(0.0, 100000.0)
        ped_spin.setSingleStep(10.0)
        ped_spin.setDecimals(2)
        ped_spin.setValue(min_ped)
        ped_spin.setToolTip(
            "Minimum PED value to trigger auto-capture. "
            "0 = no minimum. Ignored for types without a PED value "
            "(Discovery, Tier, Rare Item, PvP)."
        )
        grid.addWidget(ped_spin, 0, 1)

        # Cooldown
        grid.addWidget(QLabel("Cooldown (s):"), 1, 0)
        cooldown_spin = QDoubleSpinBox()
        cooldown_spin.setFixedWidth(100)
        cooldown_spin.setRange(0.0, 300.0)
        cooldown_spin.setSingleStep(5.0)
        cooldown_spin.setDecimals(1)
        cooldown_spin.setValue(cooldown)
        cooldown_spin.setToolTip(
            "Minimum seconds between auto-captures. "
            "0 = no cooldown (capture every qualifying global)."
        )
        grid.addWidget(cooldown_spin, 1, 1)

        layout.addLayout(grid)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(sep)

        # --- Global types ---
        types_label = QLabel("Global Types")
        types_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(types_label)

        types_desc = QLabel(
            "Select which global types trigger auto-capture. "
            "If none are checked, all types are included."
        )
        types_desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        types_desc.setWordWrap(True)
        layout.addWidget(types_desc)

        # Select all / none buttons
        sel_row = QHBoxLayout()
        sel_all_btn = QPushButton("Select All")
        sel_all_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        sel_none_btn = QPushButton("Select None")
        sel_none_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        sel_row.addWidget(sel_all_btn)
        sel_row.addWidget(sel_none_btn)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        enabled_set = set(global_types) if global_types else set()
        all_checked = len(enabled_set) == 0  # empty = all

        type_cbs: dict[str, QCheckBox] = {}
        for gt in GlobalType:
            cb = QCheckBox(_TYPE_LABELS.get(gt.value, gt.value))
            cb.setChecked(all_checked or gt.value in enabled_set)
            type_cbs[gt.value] = cb
            layout.addWidget(cb)

        sel_all_btn.clicked.connect(
            lambda: [cb.setChecked(True) for cb in type_cbs.values()])
        sel_none_btn.clicked.connect(
            lambda: [cb.setChecked(False) for cb in type_cbs.values()])

        layout.addStretch()

        return {
            "widget": tab,
            "hof_cb": hof_cb,
            "ped_spin": ped_spin,
            "cooldown_spin": cooldown_spin,
            "type_cbs": type_cbs,
        }

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _read_tab(self, tab: dict) -> dict:
        """Extract condition values from a tab's widgets."""
        type_cbs = tab["type_cbs"]
        checked = [k for k, cb in type_cbs.items() if cb.isChecked()]
        # If all are checked, store empty list (= "all types")
        if len(checked) == len(type_cbs):
            checked = []
        return {
            "min_ped": tab["ped_spin"].value(),
            "global_types": checked,
            "hof_only": tab["hof_cb"].isChecked(),
            "cooldown_s": tab["cooldown_spin"].value(),
        }

    def _save(self):
        cfg = self._config

        ss = self._read_tab(self._ss_tab)
        cfg.screenshot_min_ped = ss["min_ped"]
        cfg.screenshot_global_types = ss["global_types"]
        cfg.screenshot_hof_only = ss["hof_only"]
        cfg.screenshot_cooldown_s = ss["cooldown_s"]

        clip = self._read_tab(self._clip_tab)
        cfg.clip_min_ped = clip["min_ped"]
        cfg.clip_global_types = clip["global_types"]
        cfg.clip_hof_only = clip["hof_only"]
        cfg.clip_cooldown_s = clip["cooldown_s"]

        save_config(cfg, self._config_path)
        self._event_bus.publish(EVENT_CONFIG_CHANGED, cfg)
        self.accept()
