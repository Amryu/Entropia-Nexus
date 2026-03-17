"""Dialog for downloading the mpv-2.dll (libmpv) binary on demand."""

from __future__ import annotations

import threading

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..ui.theme import (
    PRIMARY, SECONDARY, TEXT, TEXT_MUTED,
    ACCENT, ACCENT_HOVER, BORDER, HOVER, ERROR,
)
from ..ui.icons import svg_icon, UPDATE
from ..core.logger import get_logger

log = get_logger("MpvDownloadDialog")


def _format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


class MpvDownloadDialog(QDialog):
    """Modal dialog for downloading the mpv-2.dll binary (~30 MB)."""

    _progress_signal = pyqtSignal(int, int)   # downloaded, total
    _done_signal = pyqtSignal(str)            # path or empty on failure
    _error_signal = pyqtSignal(str)

    def __init__(self, *, parent=None):
        super().__init__(parent)
        self._downloading = False
        self._result_path = ""

        self._progress_signal.connect(self._on_progress)
        self._done_signal.connect(self._on_done)
        self._error_signal.connect(self._on_error)

        self.setWindowTitle("mpv Required")
        self.setMinimumWidth(440)
        self.setFixedHeight(220)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {SECONDARY}; }}
            QLabel {{ background: transparent; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        header.setSpacing(10)
        icon_label = QLabel()
        icon_label.setPixmap(svg_icon(UPDATE, ACCENT, 28).pixmap(28, 28))
        icon_label.setFixedSize(28, 28)
        header.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        title = QLabel("mpv Download Required")
        title.setStyleSheet(f"color: {TEXT}; font-size: 15px; font-weight: bold;")
        header.addWidget(title, 1)
        layout.addLayout(header)

        desc = QLabel(
            "Stream playback requires the mpv video library (libmpv), "
            "which will be downloaded automatically (~30 MB)."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        layout.addWidget(desc)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        layout.addWidget(self._status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {PRIMARY};
                border: none; border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT};
                border-radius: 4px;
            }}
        """)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_MUTED};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 8px 16px; font-size: 12px;
            }}
            QPushButton:hover {{
                background: {HOVER}; color: {TEXT};
            }}
        """)
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()

        self._download_btn = QPushButton("Download")
        self._download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT}; color: {TEXT};
                border: none; border-radius: 4px;
                padding: 8px 20px; font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
            QPushButton:disabled {{
                background-color: {BORDER}; color: {TEXT_MUTED};
            }}
        """)
        self._download_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self._download_btn)
        layout.addLayout(btn_row)

    def _start_download(self):
        self._downloading = True
        self._download_btn.setEnabled(False)
        self._download_btn.setText("Downloading...")
        self._progress_bar.show()
        self._status_label.setText("Downloading mpv...")
        self._status_label.setStyleSheet(f"color: {TEXT}; font-size: 12px;")

        threading.Thread(
            target=self._download_worker, daemon=True, name="mpv-download",
        ).start()

    def _download_worker(self):
        try:
            from .stream_player import download_mpv_dll
            path = download_mpv_dll(
                progress_callback=lambda d, t: self._progress_signal.emit(d, t),
            )
            self._done_signal.emit(path or "")
        except Exception as e:
            self._error_signal.emit(str(e))

    def _on_progress(self, downloaded: int, total: int):
        if total > 0:
            pct = int(downloaded / total * 100)
            self._progress_bar.setValue(pct)
            self._status_label.setText(
                f"Downloading mpv... {_format_size(downloaded)} / {_format_size(total)}"
            )

    def _on_done(self, path: str):
        self._downloading = False
        if path:
            self._status_label.setText("mpv downloaded successfully!")
            self._result_path = path

            # Add the directory to PATH so import mpv works
            import os
            dll_dir = os.path.dirname(path)
            os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")

            self.accept()
        else:
            self._status_label.setText("Download failed.")
            self._status_label.setStyleSheet(f"color: {ERROR}; font-size: 12px;")
            self._download_btn.setText("Retry")
            self._download_btn.setEnabled(True)
            self._progress_bar.setValue(0)

    def _on_error(self, error: str):
        self._downloading = False
        self._status_label.setText(f"Download failed: {error}")
        self._status_label.setStyleSheet(f"color: {ERROR}; font-size: 12px;")
        self._download_btn.setText("Retry")
        self._download_btn.setEnabled(True)
        self._progress_bar.setValue(0)

    def reject(self):
        if self._downloading:
            return
        super().reject()

    def closeEvent(self, event):
        if self._downloading:
            event.ignore()
            return
        super().closeEvent(event)
