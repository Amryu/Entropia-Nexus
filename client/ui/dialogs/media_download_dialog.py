"""Dialog for downloading optional video/audio components on demand."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..theme import (
    PRIMARY, SECONDARY, TEXT, TEXT_MUTED,
    ACCENT, ACCENT_HOVER, BORDER, HOVER, ERROR,
)
from ..icons import svg_icon, UPDATE
from ...core.logger import get_logger
from ...updater import _format_size

log = get_logger("MediaDownloadDialog")

_GROUP_NAME = "video"


class MediaDownloadDialog(QDialog):
    """Modal dialog that offers to download optional video/audio components.

    Shows an explanation, download size, and progress bar.
    Accepts on successful download, rejects on cancel or error.
    """

    _size_ready = pyqtSignal(int)

    def __init__(self, *, updater, signals, parent=None):
        super().__init__(parent)
        self._updater = updater
        self._signals = signals
        self._downloading = False
        self._size_ready.connect(self._on_size_ready)

        self.setWindowTitle("Video Components Required")
        self.setMinimumWidth(440)
        self.setFixedHeight(260)
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

        title = QLabel("Additional Components Needed")
        title.setStyleSheet(f"color: {TEXT}; font-size: 15px; font-weight: bold;")
        header.addWidget(title, 1)
        layout.addLayout(header)

        # Explanation
        desc = QLabel(
            "Video capture, audio recording, and gallery playback require "
            "additional libraries that are not currently installed.\n\n"
            "These will be downloaded from the Entropia Nexus update server."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        layout.addWidget(desc)

        # Size label (populated asynchronously)
        self._size_label = QLabel("Calculating download size...")
        self._size_label.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        layout.addWidget(self._size_label)

        # Progress bar (hidden initially)
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

        self._progress_file = QLabel("")
        self._progress_file.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._progress_file.setWordWrap(True)
        self._progress_file.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred,
        )
        self._progress_file.hide()
        layout.addWidget(self._progress_file)

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

        # Compute download size in background
        self._download_btn.setEnabled(False)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._fetch_size)

    def _fetch_size(self):
        """Fetch the download size (may involve a network call)."""
        import threading

        def _worker():
            size = self._updater.get_group_download_size(_GROUP_NAME)
            self._size_ready.emit(size)

        threading.Thread(target=_worker, daemon=True, name="group-size").start()

    def _on_size_ready(self, size: int):
        """Called on the main thread with the computed download size."""
        if size > 0:
            self._size_label.setText(f"Download size: {_format_size(size)}")
            self._download_btn.setEnabled(True)
        else:
            self._size_label.setText(
                "Components are already installed or the server is unreachable."
            )
            # If size is 0 and group IS installed, just accept
            if self._updater.is_group_installed(_GROUP_NAME):
                self.accept()

    def _start_download(self):
        """Initiate the group download."""
        self._downloading = True
        self._download_btn.setEnabled(False)
        self._download_btn.setText("Downloading...")
        self._progress_bar.show()
        self._progress_file.show()

        self._signals.group_download_progress.connect(self._on_progress)
        self._signals.group_download_complete.connect(self._on_complete)
        self._signals.group_download_error.connect(self._on_error)

        self._updater.download_group(_GROUP_NAME)

    def _on_progress(self, data: dict):
        if data.get("group") != _GROUP_NAME:
            return
        downloaded = data.get("downloaded", 0)
        total = data.get("total", 1)
        pct = int((downloaded + 1) / total * 100) if total > 0 else 0
        self._progress_bar.setValue(pct)
        self._size_label.setText(f"Downloading file {downloaded + 1} of {total}...")
        self._progress_file.setText(data.get("current_file", ""))

    def _on_complete(self, data: dict):
        if data.get("group") != _GROUP_NAME:
            return
        self._downloading = False
        self._progress_bar.setValue(100)
        self._size_label.setText("Download complete!")
        self._progress_file.hide()
        self._disconnect_signals()
        self.accept()

    def _on_error(self, data: dict):
        if data.get("group") != _GROUP_NAME:
            return
        self._downloading = False
        error = data.get("error", "Unknown error")
        self._size_label.setText(f"Download failed: {error}")
        self._size_label.setStyleSheet(f"color: {ERROR}; font-size: 12px;")
        self._download_btn.setText("Retry")
        self._download_btn.setEnabled(True)
        self._progress_bar.setValue(0)
        self._progress_file.hide()
        self._disconnect_signals()

    def _disconnect_signals(self):
        try:
            self._signals.group_download_progress.disconnect(self._on_progress)
            self._signals.group_download_complete.disconnect(self._on_complete)
            self._signals.group_download_error.disconnect(self._on_error)
        except (TypeError, RuntimeError):
            pass

    def reject(self):
        if self._downloading:
            return  # don't allow closing during active download
        self._disconnect_signals()
        super().reject()

    def closeEvent(self, event):
        if self._downloading:
            event.ignore()
            return
        self._disconnect_signals()
        super().closeEvent(event)


class FFmpegDownloadDialog(QDialog):
    """Modal dialog for downloading the FFmpeg binary."""

    _progress_signal = pyqtSignal(int, int)  # downloaded, total
    _done_signal = pyqtSignal(str)  # path or empty on failure
    _error_signal = pyqtSignal(str)

    def __init__(self, *, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._downloading = False
        self._result_path = ""

        self._progress_signal.connect(self._on_progress)
        self._done_signal.connect(self._on_done)
        self._error_signal.connect(self._on_error)

        self.setWindowTitle("FFmpeg Required")
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
        title = QLabel("FFmpeg Download Required")
        title.setStyleSheet(f"color: {TEXT}; font-size: 15px; font-weight: bold;")
        header.addWidget(title, 1)
        layout.addLayout(header)

        desc = QLabel(
            "Video clip recording and audio processing require FFmpeg, "
            "which will be downloaded automatically (~100 MB)."
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
        self._status_label.setText("Downloading FFmpeg...")

        import threading
        threading.Thread(
            target=self._download_worker, daemon=True, name="ffmpeg-download",
        ).start()

    def _download_worker(self):
        try:
            from ...capture.ffmpeg import download_ffmpeg
            path = download_ffmpeg(
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
                f"Downloading FFmpeg... {_format_size(downloaded)} / {_format_size(total)}"
            )

    def _on_done(self, path: str):
        self._downloading = False
        if path:
            self._status_label.setText("FFmpeg downloaded successfully!")
            self._result_path = path
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


def _ensure_ffmpeg(config, parent=None) -> bool:
    """Check if FFmpeg is available; prompt download if not.

    Returns True if FFmpeg is available, False if user cancelled.
    """
    from ...capture.ffmpeg import find_ffmpeg
    if find_ffmpeg(getattr(config, "ffmpeg_path", "")):
        return True
    dialog = FFmpegDownloadDialog(config=config, parent=parent)
    return dialog.exec() == QDialog.DialogCode.Accepted


def ensure_media_libraries(config, event_bus, signals, parent=None) -> bool:
    """Check if video/audio libraries and FFmpeg are installed; prompt if not.

    Call this before enabling video capture features. Returns True if
    everything is available, False if the user cancelled or download failed.

    When running from source (not frozen), skips the library group check
    (pip deps are present) but still checks for FFmpeg.
    """
    if getattr(sys, "frozen", False):
        from ...updater import UpdateChecker
        checker = UpdateChecker(config, event_bus)
        try:
            if not checker.is_group_installed(_GROUP_NAME):
                dialog = MediaDownloadDialog(
                    updater=checker, signals=signals, parent=parent,
                )
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return False
        finally:
            checker._session.close()

    # Ensure FFmpeg is available (needed for clip encoding in all modes)
    if not _ensure_ffmpeg(config, parent=parent):
        return False

    # Pre-download the RNNoise noise-suppression model (~2 MB).
    # Done here so clip writing never needs a network call.
    from ...capture.ffmpeg import find_rnnoise_model, download_rnnoise_model
    if not find_rnnoise_model():
        log.info("Pre-downloading RNNoise model...")
        download_rnnoise_model()

    return True
