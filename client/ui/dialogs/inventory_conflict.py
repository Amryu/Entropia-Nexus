"""Conflict resolution dialog for online vs offline inventory imports."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt

from ..theme import (
    PRIMARY, SECONDARY, HOVER, BORDER, ACCENT, ACCENT_HOVER,
    TEXT, TEXT_MUTED, MAIN_DARK,
)
from ...core.logger import get_logger

log = get_logger("InventoryConflict")

# Dialog result codes
USE_OFFLINE = 1
USE_ONLINE = 2


class InventoryConflictDialog(QDialog):
    """Shown when a pending offline import exists and the user logs in.

    Lets the user choose between:
    - Using the offline import (upload to server)
    - Using the online inventory (discard local)
    """

    def __init__(
        self,
        *,
        offline_count: int,
        offline_date: str,
        online_count: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._result_code = 0

        self.setWindowTitle("Inventory Conflict")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"QDialog {{ background-color: {SECONDARY}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("Pending Offline Import")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT};")
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "You have a locally saved inventory import that hasn't been synced yet.\n"
            "Choose how to proceed:"
        )
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Info cards
        offline_info = self._make_info_card(
            "Local Import",
            f"{offline_count:,} items",
            f"Saved {offline_date}",
        )
        layout.addWidget(offline_info)

        if online_count is not None:
            online_info = self._make_info_card(
                "Server Inventory",
                f"{online_count:,} items",
                "Currently on server",
            )
            layout.addWidget(online_info)

        layout.addSpacing(4)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SECONDARY}; color: {TEXT_MUTED};
                border: 1px solid {BORDER}; padding: 6px 16px;
                font-size: 13px; min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: {HOVER}; color: {TEXT};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        btn_row.addStretch()

        online_btn = QPushButton("Use Online")
        online_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SECONDARY}; color: {TEXT};
                border: 1px solid {BORDER}; padding: 6px 16px;
                font-size: 13px; font-weight: bold; min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: {HOVER};
            }}
        """)
        online_btn.setToolTip("Discard local import and keep server inventory")
        online_btn.clicked.connect(self._use_online)
        btn_row.addWidget(online_btn)

        offline_btn = QPushButton("Use Offline")
        offline_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT}; color: {MAIN_DARK};
                border: 1px solid {ACCENT}; padding: 6px 16px;
                font-size: 13px; font-weight: bold; min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_HOVER};
            }}
        """)
        offline_btn.setToolTip("Upload local import to replace server inventory")
        offline_btn.clicked.connect(self._use_offline)
        btn_row.addWidget(offline_btn)

        layout.addLayout(btn_row)

    def _make_info_card(self, title: str, count: str, subtitle: str) -> QLabel:
        lbl = QLabel(f"<b>{title}</b><br>{count}<br>"
                     f"<span style='color: {TEXT_MUTED}; font-size: 11px;'>{subtitle}</span>")
        lbl.setStyleSheet(
            f"background: {PRIMARY}; border: 1px solid {BORDER};"
            f" border-radius: 6px; padding: 10px; color: {TEXT}; font-size: 13px;"
        )
        lbl.setTextFormat(Qt.TextFormat.RichText)
        return lbl

    def _use_offline(self):
        self._result_code = USE_OFFLINE
        self.accept()

    def _use_online(self):
        self._result_code = USE_ONLINE
        self.accept()

    @property
    def result_code(self) -> int:
        return self._result_code
