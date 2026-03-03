"""Update dialog — changelog, update/remind/dismiss actions."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QProgressBar, QStackedWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..theme import (
    PRIMARY, SECONDARY, MAIN_DARK, TEXT, TEXT_MUTED, ACCENT, BORDER, HOVER,
    ERROR,
)
from ..icons import svg_icon, UPDATE
from ...updater import (
    get_local_version, load_bundled_changelog, merge_changelogs, _format_size,
)
from ...core.logger import get_logger

log = get_logger("UpdateDialog")

# Change type → (label, color)
_CHANGE_COLORS = {
    "feat": ("#60b0ff", "NEW"),
    "fix": ("#e8a838", "FIX"),
    "improve": ("#16a34a", "IMPROVED"),
    "remove": ("#ff6b6b", "REMOVED"),
}

# Page indices in the stacked widget
_PAGE_MAIN = 0
_PAGE_CHANGELOG = 1
_PAGE_PROGRESS = 2


class UpdateDialog(QDialog):
    """Dialog showing available update with changelog and action buttons.

    Signals:
        update_requested: User clicked "Update Now"
        remind_requested: User clicked "Remind Later"
        dismiss_requested(str): User clicked "Dismiss" (emits version string)
    """

    update_requested = pyqtSignal()
    remind_requested = pyqtSignal()
    dismiss_requested = pyqtSignal(str)

    def __init__(
        self,
        *,
        update_data: dict | None = None,
        changelog_only: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._update_data = update_data or {}
        self._changelog_only = changelog_only

        version = self._update_data.get("version", "")
        self.setWindowTitle(
            "Changelog" if changelog_only else f"Update Available — v{version}"
        )
        self.setMinimumSize(520, 400)
        self.resize(560, 500)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {SECONDARY}; }}
            QLabel {{ background: transparent; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        # Pages
        self._stack.addWidget(self._build_main_page())
        self._stack.addWidget(self._build_changelog_page())
        self._stack.addWidget(self._build_progress_page())

        if changelog_only:
            self._stack.setCurrentIndex(_PAGE_CHANGELOG)
        else:
            self._stack.setCurrentIndex(_PAGE_MAIN)

    # ------------------------------------------------------------------
    # Main update page
    # ------------------------------------------------------------------

    def _build_main_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Header row: icon + title
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        icon_label = QLabel()
        icon_label.setPixmap(svg_icon(UPDATE, ACCENT, 32).pixmap(32, 32))
        icon_label.setFixedSize(32, 32)
        header_row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        version = self._update_data.get("version", "?")
        title = QLabel(f"Entropia Nexus v{version}")
        title.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: bold;")
        header_text.addWidget(title)

        current = self._update_data.get(
            "current_version", get_local_version()
        )
        size = self._update_data.get("download_size", 0)
        file_count = self._update_data.get("file_count", 0)
        subtitle_parts = [f"Current: v{current}"]
        if size:
            subtitle_parts.append(f"{_format_size(size)}")
        if file_count:
            subtitle_parts.append(f"{file_count} files")
        subtitle = QLabel(" \u2022 ".join(subtitle_parts))
        subtitle.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        header_text.addWidget(subtitle)
        header_row.addLayout(header_text, 1)
        layout.addLayout(header_row)

        # Separator
        layout.addWidget(self._separator())

        # "What's new" label
        whats_new = QLabel("What's new")
        whats_new.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; font-weight: bold;"
        )
        layout.addWidget(whats_new)

        # Changelog entries for new versions only
        remote_changelog = self._update_data.get("changelog", [])
        new_entries = [
            e for e in remote_changelog
            if e.get("version", "") > current
        ]

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: {PRIMARY}; border-radius: 6px; }}
            QScrollBar:vertical {{
                background: {PRIMARY}; width: 8px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER}; border-radius: 4px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        content = QWidget()
        content.setStyleSheet(f"background: {PRIMARY};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(12, 8, 12, 8)
        cl.setSpacing(4)

        if new_entries:
            for entry in new_entries:
                self._render_version_entry(cl, entry)
        else:
            no_data = QLabel("Changelog not available for this version.")
            no_data.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            cl.addWidget(no_data)

        cl.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # "View Full Changelog" link
        full_link = QPushButton("View Full Changelog")
        full_link.setCursor(Qt.CursorShape.PointingHandCursor)
        full_link.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {ACCENT}; font-size: 12px; text-align: left;
                padding: 4px 0px;
            }}
            QPushButton:hover {{ text-decoration: underline; }}
        """)
        full_link.clicked.connect(
            lambda: self._stack.setCurrentIndex(_PAGE_CHANGELOG)
        )
        layout.addWidget(full_link)

        # Action buttons
        layout.addWidget(self._separator())
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.setStyleSheet(self._secondary_btn_style())
        dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss_btn.clicked.connect(self._on_dismiss)
        btn_row.addWidget(dismiss_btn)

        remind_btn = QPushButton("Remind Later")
        remind_btn.setStyleSheet(self._secondary_btn_style())
        remind_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remind_btn.clicked.connect(self._on_remind)
        btn_row.addWidget(remind_btn)

        btn_row.addStretch()

        self._update_btn = QPushButton("Update Now")
        self._update_btn.setStyleSheet(self._primary_btn_style())
        self._update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_btn.clicked.connect(self._on_update)
        btn_row.addWidget(self._update_btn)

        layout.addLayout(btn_row)
        return page

    # ------------------------------------------------------------------
    # Full changelog page
    # ------------------------------------------------------------------

    def _build_changelog_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Header with back button
        header_row = QHBoxLayout()
        if not self._changelog_only:
            back_btn = QPushButton("\u2190 Back")
            back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            back_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    color: {ACCENT}; font-size: 12px; padding: 4px 8px;
                }}
                QPushButton:hover {{ text-decoration: underline; }}
            """)
            back_btn.clicked.connect(
                lambda: self._stack.setCurrentIndex(_PAGE_MAIN)
            )
            header_row.addWidget(back_btn)
        title = QLabel("Changelog")
        title.setStyleSheet(
            f"color: {TEXT}; font-size: 16px; font-weight: bold;"
        )
        header_row.addWidget(title)
        header_row.addStretch()
        layout.addLayout(header_row)

        layout.addWidget(self._separator())

        # Scrollable list of all versions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: {PRIMARY}; border-radius: 6px; }}
            QScrollBar:vertical {{
                background: {PRIMARY}; width: 8px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER}; border-radius: 4px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        content = QWidget()
        content.setStyleSheet(f"background: {PRIMARY};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(12, 8, 12, 8)
        cl.setSpacing(4)

        remote_changelog = self._update_data.get("changelog", [])
        bundled = load_bundled_changelog()
        merged = merge_changelogs(bundled, remote_changelog)

        if merged:
            for entry in merged:
                self._render_version_entry(cl, entry)
        else:
            no_data = QLabel("No changelog data available.")
            no_data.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            cl.addWidget(no_data)

        cl.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # Close button (changelog-only mode)
        if self._changelog_only:
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            close_btn = QPushButton("Close")
            close_btn.setStyleSheet(self._secondary_btn_style())
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.clicked.connect(self.close)
            btn_row.addWidget(close_btn)
            layout.addLayout(btn_row)

        return page

    # ------------------------------------------------------------------
    # Progress page
    # ------------------------------------------------------------------

    def _build_progress_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        layout.addStretch()

        self._progress_title = QLabel("Preparing update...")
        self._progress_title.setStyleSheet(
            f"color: {TEXT}; font-size: 14px; font-weight: bold;"
        )
        self._progress_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._progress_title)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {PRIMARY};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self._progress_bar)

        self._progress_file = QLabel("")
        self._progress_file.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px;"
        )
        self._progress_file.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._progress_file)

        layout.addStretch()
        return page

    # ------------------------------------------------------------------
    # Public: progress updates from main window
    # ------------------------------------------------------------------

    def on_update_progress(self, data: dict):
        """Called by main window when download progress event fires."""
        self._stack.setCurrentIndex(_PAGE_PROGRESS)
        downloaded = data.get("downloaded", 0)
        total = data.get("total", 1)
        current_file = data.get("current_file", "")
        pct = int(downloaded / total * 100) if total > 0 else 0
        self._progress_bar.setValue(pct)
        self._progress_title.setText(f"Downloading {downloaded}/{total} files...")
        self._progress_file.setText(current_file)

    def on_update_ready(self, data: dict):
        """Called when download is complete and ready to apply."""
        self._progress_bar.setValue(100)
        version = data.get("version", "?")
        self._progress_title.setText(f"Update v{version} ready. Restarting...")
        self._progress_file.setText("")

    def on_update_error(self, data: dict):
        """Called when an update error occurs."""
        error = data.get("error", "Unknown error")
        self._progress_title.setText("Update failed")
        self._progress_title.setStyleSheet(
            f"color: {ERROR}; font-size: 14px; font-weight: bold;"
        )
        self._progress_file.setText(str(error))

    # ------------------------------------------------------------------
    # Internal actions
    # ------------------------------------------------------------------

    def _on_update(self):
        self._update_btn.setEnabled(False)
        self._update_btn.setText("Updating...")
        self._stack.setCurrentIndex(_PAGE_PROGRESS)
        self.update_requested.emit()

    def _on_remind(self):
        self.remind_requested.emit()
        self.close()

    def _on_dismiss(self):
        version = self._update_data.get("version", "")
        self.dismiss_requested.emit(version)
        self.close()

    # ------------------------------------------------------------------
    # Changelog rendering helpers
    # ------------------------------------------------------------------

    def _render_version_entry(self, layout: QVBoxLayout, entry: dict):
        """Render a single version entry into the layout."""
        version = entry.get("version", "?")
        date = entry.get("date", "")
        changes = entry.get("changes", [])

        # Version header
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        ver_label = QLabel(f"v{version}")
        ver_label.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; font-weight: bold;"
        )
        header_row.addWidget(ver_label)

        if date:
            date_label = QLabel(date)
            date_label.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px;"
            )
            header_row.addWidget(date_label)

        header_row.addStretch()
        layout.addLayout(header_row)

        # Change items
        for change in changes:
            change_type = change.get("type", "")
            text = change.get("text", "")

            row = QHBoxLayout()
            row.setContentsMargins(8, 0, 0, 0)
            row.setSpacing(6)

            # Type badge
            color, label_text = _CHANGE_COLORS.get(
                change_type, (TEXT_MUTED, change_type.upper() or "OTHER")
            )
            badge = QLabel(label_text)
            badge.setFixedWidth(68)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"color: {color}; font-size: 10px; font-weight: bold;"
                f" background-color: {MAIN_DARK}; border-radius: 3px;"
                f" padding: 2px 4px;"
            )
            row.addWidget(badge)

            # Text (supports rich text / markdown-like formatting)
            text_label = QLabel(text)
            text_label.setWordWrap(True)
            text_label.setTextFormat(Qt.TextFormat.RichText)
            text_label.setStyleSheet(
                f"color: {TEXT}; font-size: 12px;"
            )
            row.addWidget(text_label, 1)

            layout.addLayout(row)

        # Spacer between versions
        spacer = QWidget()
        spacer.setFixedHeight(8)
        layout.addWidget(spacer)

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {BORDER}; max-height: 1px;")
        return sep

    @staticmethod
    def _primary_btn_style() -> str:
        return f"""
            QPushButton {{
                background-color: {ACCENT};
                color: {TEXT};
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #4a9ae8;
            }}
            QPushButton:disabled {{
                background-color: {BORDER};
                color: {TEXT_MUTED};
            }}
        """

    @staticmethod
    def _secondary_btn_style() -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_MUTED};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {HOVER};
                color: {TEXT};
            }}
        """
