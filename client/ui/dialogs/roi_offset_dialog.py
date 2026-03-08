"""Generic dialog for editing ROI offset fields ({dx, dy, w, h} or {x, y})."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QGroupBox, QPushButton,
)
from PyQt6.QtCore import Qt

from ...core.config import save_config
from ..theme import (
    SECONDARY, PRIMARY, TEXT, TEXT_MUTED, ACCENT, ACCENT_HOVER, MAIN_DARK,
    BORDER, HOVER,
)

# Field definitions: (field_name, min, max)
_FIELD_RANGES = {
    "dx": (-500, 500),
    "dy": (-500, 500),
    "w": (1, 500),
    "h": (1, 500),
    "x": (1, 500),
    "y": (1, 500),
}


class RoiOffsetDialog(QDialog):
    """Dialog for editing ROI offset values stored in config.

    Parameters
    ----------
    title : str
        Dialog window title.
    roi_defs : list[tuple[str, str, list[str]]]
        Each entry is ``(display_label, config_key, [field_names])``.
        ``config_key`` is the attribute name on the config object (a dict).
        ``field_names`` are the keys within that dict (e.g. ``["dx","dy","w","h"]``).
    config : AppConfig
        The shared config object.
    config_path : str
        Path for ``save_config``.
    """

    def __init__(self, *, title: str, roi_defs, config, config_path: str,
                 parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setStyleSheet(f"QDialog {{ background-color: {SECONDARY}; }}")

        self._config = config
        self._config_path = config_path
        self._roi_defs = roi_defs
        self._spinboxes: dict[str, dict[str, QSpinBox]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        info = QLabel("Pixel offsets relative to template position.")
        info.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(info)

        for display_label, config_key, fields in roi_defs:
            layout.addWidget(
                self._build_roi_group(display_label, config_key, fields)
            )

        # Buttons
        btn_row = QHBoxLayout()

        reset_btn = QPushButton("Reset All")
        reset_btn.setStyleSheet(
            f"QPushButton {{ background-color: {PRIMARY}; color: {TEXT_MUTED};"
            f" border: 1px solid {BORDER}; padding: 6px 12px; }}"
            f"QPushButton:hover {{ background-color: {HOVER}; }}"
        )
        reset_btn.clicked.connect(self._reset_all)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch()

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT}; color: {MAIN_DARK};"
            f" border: none; padding: 6px 16px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}"
        )
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            f"QPushButton {{ background-color: {PRIMARY}; color: {TEXT};"
            f" border: 1px solid {BORDER}; padding: 6px 12px; }}"
            f"QPushButton:hover {{ background-color: {HOVER}; }}"
        )
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _build_roi_group(self, display_label: str, config_key: str,
                         fields: list[str]) -> QGroupBox:
        current = getattr(self._config, config_key, {})

        group = QGroupBox(display_label)
        group.setStyleSheet(
            f"QGroupBox {{ color: {TEXT}; border: 1px solid {BORDER};"
            f" border-radius: 4px; margin-top: 8px; padding-top: 14px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin;"
            f" left: 8px; padding: 0 4px; color: {ACCENT}; }}"
        )

        row = QHBoxLayout(group)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(6)

        self._spinboxes[config_key] = {}
        for field in fields:
            lo, hi = _FIELD_RANGES.get(field, (-500, 500))
            default = current.get(field, 0)

            lbl = QLabel(f"{field}:")
            lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px; border: none;"
            )
            lbl.setFixedWidth(20)
            row.addWidget(lbl)

            spin = QSpinBox()
            spin.setRange(lo, hi)
            spin.setValue(default)
            spin.setStyleSheet(
                f"QSpinBox {{ background-color: {PRIMARY}; color: {TEXT};"
                f" border: 1px solid {BORDER}; padding: 2px 4px; }}"
                f"QSpinBox:focus {{ border-color: {ACCENT}; }}"
            )
            row.addWidget(spin)
            self._spinboxes[config_key][field] = spin

        # Per-group reset
        reset_btn = QPushButton("\u21ba")
        reset_btn.setToolTip(f"Reset {display_label} to defaults")
        reset_btn.setFixedWidth(26)
        reset_btn.setStyleSheet(
            f"QPushButton {{ background-color: {PRIMARY}; color: {TEXT_MUTED};"
            f" border: 1px solid {BORDER}; padding: 2px; }}"
            f"QPushButton:hover {{ background-color: {HOVER}; color: {TEXT}; }}"
        )
        reset_btn.clicked.connect(
            lambda _, ck=config_key: self._reset_one(ck)
        )
        row.addWidget(reset_btn)

        return group

    def _get_defaults(self, config_key: str) -> dict:
        """Get default values from the config class default_factory."""
        from ...core.config import DEFAULTS
        return DEFAULTS.get(config_key, {})

    def _reset_one(self, config_key: str):
        defaults = self._get_defaults(config_key)
        spins = self._spinboxes[config_key]
        for field, spin in spins.items():
            spin.setValue(defaults.get(field, 0))

    def _reset_all(self):
        for config_key in self._spinboxes:
            self._reset_one(config_key)

    def _save(self):
        for config_key, spins in self._spinboxes.items():
            setattr(self._config, config_key, {
                field: spin.value() for field, spin in spins.items()
            })
        save_config(self._config, self._config_path)
        self.close()
