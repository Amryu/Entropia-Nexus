"""Bottom status bar for persistent info (trackers, inventory value, etc.)."""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QStyleOption, QStyle, QPushButton, QLabel
from PyQt6.QtGui import QPainter
from PyQt6.QtCore import pyqtSignal

from ..theme import STATUS_BAR_HEIGHT, ACCENT, ACCENT_HOVER, TEXT_MUTED


class StatusBar(QWidget):
    """Thin bar at the bottom of the main window."""

    update_restart_clicked = pyqtSignal()

    def __init__(self, *, signals=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(STATUS_BAR_HEIGHT)
        self.setObjectName("statusBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(12)

        # Catchup progress (hidden by default)
        self._catchup_label = QLabel()
        self._catchup_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._catchup_label.hide()
        layout.addWidget(self._catchup_label)

        # Pending ingestion uploads (hidden by default)
        self._ingestion_label = QLabel()
        self._ingestion_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._ingestion_label.hide()
        layout.addWidget(self._ingestion_label)

        layout.addStretch()

        # Update notification (hidden by default)
        self._update_btn = QPushButton()
        self._update_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {ACCENT};
                font-size: 11px;
                padding: 0 4px;
            }}
            QPushButton:hover {{
                color: {ACCENT_HOVER};
                text-decoration: underline;
            }}
            QPushButton:disabled {{
                color: #888;
            }}
        """)
        self._update_btn.hide()
        self._update_btn.clicked.connect(self.update_restart_clicked.emit)
        layout.addWidget(self._update_btn)

        if signals:
            signals.update_available.connect(self._on_update_available)
            signals.update_progress.connect(self._on_update_progress)
            signals.update_ready.connect(self._on_update_ready)
            signals.update_error.connect(self._on_update_error)
            signals.catchup_progress.connect(self._on_catchup_progress)
            signals.catchup_complete.connect(self._on_catchup_complete)
            signals.ingestion_status.connect(self._on_ingestion_status)

    # ------------------------------------------------------------------
    # Catchup & ingestion status
    # ------------------------------------------------------------------

    def _on_catchup_progress(self, data):
        parsed = data.get("parsed", 0)
        total = data.get("total", 1)
        pct = int(100 * parsed / total)
        self._catchup_label.setText(f"Catching up... {pct}%")
        self._catchup_label.show()

    def _on_catchup_complete(self, _data):
        self._catchup_label.hide()

    def _on_ingestion_status(self, data):
        pending = data.get("pending", 0)
        if pending > 0:
            self._ingestion_label.setText(f"{pending} pending")
            self._ingestion_label.show()
        else:
            self._ingestion_label.hide()

    # ------------------------------------------------------------------
    # Update notifications
    # ------------------------------------------------------------------

    def _on_update_available(self, data):
        size = self._format_size(data.get("download_size", 0))
        count = data.get("file_count", 0)
        self._update_btn.setText(f"Downloading update ({count} files, {size})...")
        self._update_btn.setEnabled(False)
        self._update_btn.show()

    def _on_update_progress(self, data):
        downloaded = data.get("downloaded", 0)
        total = data.get("total", 1)
        pct = int(100 * downloaded / total)
        self._update_btn.setText(f"Downloading update... {pct}%")

    def _on_update_ready(self, data):
        version = data.get("version", "?")
        self._update_btn.setText(f"Update v{version} ready \u2014 click to restart")
        self._update_btn.setEnabled(True)

    def _on_update_error(self, data):
        self._update_btn.setText(f"Update failed: {data.get('error', 'unknown')}")
        self._update_btn.setEnabled(False)

    @staticmethod
    def _format_size(size_bytes):
        for unit in ("B", "KB", "MB"):
            if abs(size_bytes) < 1024:
                return f"{size_bytes:.0f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} GB"

    def paintEvent(self, event):
        """Required for QWidget subclasses to honour stylesheet backgrounds."""
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        p.end()
