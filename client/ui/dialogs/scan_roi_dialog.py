"""Dialog for adjusting scan ROI pixel offsets relative to the SKILLS template."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QGroupBox, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt

from ...core.config import AppConfig, save_config
from ...core.event_bus import EventBus
from ...core.constants import EVENT_ROI_CONFIG_CHANGED
from ...core.logger import get_logger
from ...ocr.detector import (
    DEFAULT_ROI_PIXELS, ROI_NAMES, NATIVE_TEMPLATE_W, NATIVE_TEMPLATE_H,
)
from ..theme import (
    SECONDARY, TEXT, TEXT_MUTED, ACCENT, ACCENT_HOVER, MAIN_DARK,
    BORDER, HOVER, PRIMARY,
)

log = get_logger("ScanROI")


class ScanRoiDialog(QDialog):
    """Adjust scan ROI pixel offsets with live preview via debug overlay."""

    def __init__(self, *, config: AppConfig, config_path: str,
                 event_bus: EventBus, parent=None):
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._event_bus = event_bus
        self._spinboxes: dict[str, dict[str, QSpinBox]] = {}  # {roi: {field: spinbox}}

        self.setWindowTitle("Scan ROI Configuration")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"QDialog {{ background-color: {SECONDARY}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Header
        header = QLabel(
            f"Pixel offsets from SKILLS template ({NATIVE_TEMPLATE_W}\u00d7{NATIVE_TEMPLATE_H})"
        )
        header.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(header)

        info = QLabel("Changes update the debug overlay immediately.")
        info.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        layout.addWidget(info)

        # ROI groups
        for name in ROI_NAMES:
            layout.addWidget(self._build_roi_group(name))

        # Buttons
        btn_row = QHBoxLayout()

        reset_btn = QPushButton("Reset All to Defaults")
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY}; color: {TEXT_MUTED};
                border: 1px solid {BORDER}; padding: 6px 12px;
            }}
            QPushButton:hover {{ background-color: {HOVER}; }}
        """)
        reset_btn.clicked.connect(self._reset_all)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch()

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT}; color: {MAIN_DARK};
                border: none; padding: 6px 16px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
        """)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY}; color: {TEXT};
                border: 1px solid {BORDER}; padding: 6px 12px;
            }}
            QPushButton:hover {{ background-color: {HOVER}; }}
        """)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _build_roi_group(self, name: str) -> QGroupBox:
        """Build a group box with x/y/w/h spinboxes for one ROI."""
        defaults = DEFAULT_ROI_PIXELS[name]
        current = self._config.scan_roi_overrides.get(name)
        if current and len(current) == 4:
            vals = tuple(current)
        else:
            vals = defaults

        group = QGroupBox(name)
        group.setStyleSheet(f"""
            QGroupBox {{
                color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 4px; margin-top: 8px; padding-top: 14px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 8px;
                padding: 0 4px; color: {ACCENT};
            }}
        """)

        row = QHBoxLayout(group)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(6)

        self._spinboxes[name] = {}
        fields = [("X", 0), ("Y", 1), ("W", 2), ("H", 3)]

        for label, idx in fields:
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; border: none;")
            lbl.setFixedWidth(16)
            row.addWidget(lbl)

            spin = QSpinBox()
            spin.setRange(-2000, 2000)
            spin.setValue(int(vals[idx]))
            spin.setStyleSheet(f"""
                QSpinBox {{
                    background-color: {PRIMARY}; color: {TEXT};
                    border: 1px solid {BORDER}; padding: 2px 4px;
                }}
                QSpinBox:focus {{ border-color: {ACCENT}; }}
            """)
            spin.valueChanged.connect(lambda _, n=name: self._on_value_changed(n))
            row.addWidget(spin)
            self._spinboxes[name][label.lower()] = spin

        # Per-ROI reset button
        reset_btn = QPushButton("\u21ba")
        reset_btn.setToolTip(f"Reset {name} to default")
        reset_btn.setFixedWidth(26)
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY}; color: {TEXT_MUTED};
                border: 1px solid {BORDER}; padding: 2px;
            }}
            QPushButton:hover {{ background-color: {HOVER}; color: {TEXT}; }}
        """)
        reset_btn.clicked.connect(lambda _, n=name: self._reset_one(n))
        row.addWidget(reset_btn)

        return group

    def _read_spinboxes(self, name: str) -> tuple[int, int, int, int]:
        """Read the current spinbox values for an ROI."""
        s = self._spinboxes[name]
        return (s["x"].value(), s["y"].value(), s["w"].value(), s["h"].value())

    def _read_all(self) -> dict[str, tuple[int, int, int, int]]:
        """Read all current spinbox values."""
        return {name: self._read_spinboxes(name) for name in ROI_NAMES}

    def _on_value_changed(self, name: str) -> None:
        """Publish live update when any spinbox changes."""
        self._event_bus.publish(EVENT_ROI_CONFIG_CHANGED, self._read_all())

    def _reset_one(self, name: str) -> None:
        """Reset one ROI to its default values."""
        defaults = DEFAULT_ROI_PIXELS[name]
        s = self._spinboxes[name]
        for spin in s.values():
            spin.blockSignals(True)
        s["x"].setValue(defaults[0])
        s["y"].setValue(defaults[1])
        s["w"].setValue(defaults[2])
        s["h"].setValue(defaults[3])
        for spin in s.values():
            spin.blockSignals(False)
        self._event_bus.publish(EVENT_ROI_CONFIG_CHANGED, self._read_all())

    def _reset_all(self) -> None:
        """Reset all ROIs to defaults."""
        for name in ROI_NAMES:
            defaults = DEFAULT_ROI_PIXELS[name]
            s = self._spinboxes[name]
            for spin in s.values():
                spin.blockSignals(True)
            s["x"].setValue(defaults[0])
            s["y"].setValue(defaults[1])
            s["w"].setValue(defaults[2])
            s["h"].setValue(defaults[3])
            for spin in s.values():
                spin.blockSignals(False)
        self._event_bus.publish(EVENT_ROI_CONFIG_CHANGED, self._read_all())

    def _save(self) -> None:
        """Persist current ROI values to config file."""
        overrides = {}
        for name in ROI_NAMES:
            vals = self._read_spinboxes(name)
            defaults = DEFAULT_ROI_PIXELS[name]
            # Only store if different from defaults
            if vals != defaults:
                overrides[name] = list(vals)
        self._config.scan_roi_overrides = overrides
        save_config(self._config, self._config_path)
        log.info("Saved ROI overrides: %s", overrides or "(all defaults)")
