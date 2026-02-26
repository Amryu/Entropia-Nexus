"""Inventory page — view and manage in-game inventory."""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ..theme import TEXT_MUTED, PAGE_HEADER_OBJECT_NAME


class InventoryPage(QWidget):
    """Inventory viewer — placeholder for future implementation."""

    def __init__(self, *, signals, oauth, nexus_client):
        super().__init__()
        self._signals = signals
        self._oauth = oauth
        self._nexus_client = nexus_client

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)

        header = QLabel("Inventory")
        header.setObjectName(PAGE_HEADER_OBJECT_NAME)
        layout.addWidget(header)

        placeholder = QLabel("Coming soon — import and manage your inventory here.")
        placeholder.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px;")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder, 1)
