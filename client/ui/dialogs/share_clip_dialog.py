"""Dialog for sharing a video clip to a Nexus global via an external video platform."""

from __future__ import annotations

import webbrowser

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QApplication,
)
from PyQt6.QtCore import Qt

from ..theme import (
    PRIMARY, SECONDARY, TEXT, TEXT_MUTED,
    ACCENT, ACCENT_HOVER, BORDER, HOVER, ERROR,
    SUCCESS, BADGE_HOF, BADGE_ATH,
)
from ..icons import svg_icon, UPLOAD, LINK, CLIP
from ...core.logger import get_logger

log = get_logger("ShareClipDialog")

# Upload page URLs for each platform
_PLATFORMS = [
    {
        "name": "YouTube",
        "url": "https://www.youtube.com/upload",
        "tip": "Upload your clip, then copy the video URL.",
    },
    {
        "name": "Twitch",
        "url": None,  # Clips are created from live streams
        "tip": "Twitch clips are created from live streams.\nCopy the clip URL from your Twitch dashboard.",
    },
    {
        "name": "Vimeo",
        "url": "https://vimeo.com/upload",
        "tip": "Upload your clip, then copy the video URL.",
    },
]


class ShareClipDialog(QDialog):
    """Modal dialog for sharing a clip to a Nexus global.

    Flow:
    1. User clicks a platform button → clip path copied to clipboard + browser opens
    2. User uploads the clip on the external platform
    3. User pastes the resulting video URL and clicks "Link to Global"
    """

    def __init__(self, *, clip_info: dict, nexus_client, database, parent=None):
        """
        Args:
            clip_info: Dict from get_screenshot_by_path with keys: id, file_path,
                       server_global_id, target_name, value, is_hof, is_ath, etc.
            nexus_client: NexusClient instance for API calls.
            database: Database instance for local updates.
        """
        super().__init__(parent)
        self._clip_info = clip_info
        self._nexus_client = nexus_client
        self._db = database
        self._linked = False

        self.setWindowTitle("Share Clip to Nexus")
        self.setMinimumWidth(460)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {SECONDARY}; }}
            QLabel {{ background: transparent; color: {TEXT}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # --- Header: global info ---
        header = QHBoxLayout()
        header.setSpacing(10)
        icon_label = QLabel()
        icon_label.setPixmap(svg_icon(CLIP, ACCENT, 24).pixmap(24, 24))
        icon_label.setFixedSize(24, 24)
        header.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        target = clip_info.get("target_name") or "Global"
        title_parts = [target]
        if clip_info.get("is_ath"):
            title_parts.append("(ATH)")
        elif clip_info.get("is_hof"):
            title_parts.append("(HoF)")

        title_lbl = QLabel(" ".join(title_parts))
        title_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT};")
        header_text.addWidget(title_lbl)

        value = clip_info.get("value")
        if value:
            val_str = f"{float(value) / 100:.2f} PED" if isinstance(value, int) and value > 1000 else f"{float(value):.2f} PED"
            val_lbl = QLabel(val_str)
            val_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED};")
            header_text.addWidget(val_lbl)

        header.addLayout(header_text, 1)
        layout.addLayout(header)

        # --- Separator ---
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER};")
        layout.addWidget(sep)

        # --- Step 1: Upload to platform ---
        step1_lbl = QLabel("1. Upload your clip to a video platform")
        step1_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {TEXT};")
        layout.addWidget(step1_lbl)

        hint_lbl = QLabel("Click a platform to open it and copy the clip path to your clipboard.")
        hint_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED};")
        hint_lbl.setWordWrap(True)
        layout.addWidget(hint_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for platform in _PLATFORMS:
            btn = QPushButton(platform["name"])
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {HOVER};
                    color: {TEXT};
                    border: 1px solid {BORDER};
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {ACCENT};
                    color: white;
                    border-color: {ACCENT};
                }}
            """)
            btn.setToolTip(platform["tip"])
            btn.clicked.connect(lambda checked, p=platform: self._on_platform_click(p))
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        self._status_lbl.setWordWrap(True)
        layout.addWidget(self._status_lbl)

        # --- Step 2: Paste video URL ---
        step2_lbl = QLabel("2. Paste the video URL after uploading")
        step2_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {TEXT};")
        layout.addWidget(step2_lbl)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self._url_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {PRIMARY};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 8px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT};
            }}
        """)
        self._url_input.returnPressed.connect(self._on_link)
        url_row.addWidget(self._url_input, 1)

        self._link_btn = QPushButton("Link to Global")
        self._link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._link_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background-color: {HOVER};
                color: {TEXT_MUTED};
            }}
        """)
        self._link_btn.clicked.connect(self._on_link)
        url_row.addWidget(self._link_btn)
        layout.addLayout(url_row)

        self._result_lbl = QLabel("")
        self._result_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED};")
        self._result_lbl.setWordWrap(True)
        layout.addWidget(self._result_lbl)

        layout.addStretch()

    @property
    def was_linked(self) -> bool:
        """Whether a video was successfully linked during this dialog session."""
        return self._linked

    def _on_platform_click(self, platform: dict) -> None:
        """Copy clip path to clipboard and open the platform's upload page."""
        clip_path = self._clip_info.get("file_path", "")
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(clip_path)

        if platform["url"]:
            webbrowser.open(platform["url"])
            self._status_lbl.setText(
                f"Clip path copied to clipboard. {platform['name']} opened in your browser."
            )
            self._status_lbl.setStyleSheet(f"font-size: 11px; color: {ACCENT};")
        else:
            self._status_lbl.setText(
                f"Clip path copied to clipboard. {platform['tip']}"
            )
            self._status_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")

    def _on_link(self) -> None:
        """Submit the video URL to the Nexus API and update local DB."""
        url = self._url_input.text().strip()
        if not url:
            return

        server_global_id = self._clip_info.get("server_global_id")
        if not server_global_id:
            self._result_lbl.setText("Error: This clip is not linked to a server global.")
            self._result_lbl.setStyleSheet(f"font-size: 12px; color: {ERROR};")
            return

        self._link_btn.setEnabled(False)
        self._link_btn.setText("Linking...")

        try:
            result = self._nexus_client.submit_global_video(server_global_id, url)
            if result and result.get("success"):
                # Update local database
                screenshot_id = self._clip_info.get("id")
                if screenshot_id and self._db:
                    self._db.update_screenshot_video_url(screenshot_id, url)
                    self._db.update_screenshot_upload(screenshot_id, "uploaded")

                self._linked = True
                self._result_lbl.setText("Video linked successfully!")
                self._result_lbl.setStyleSheet(f"font-size: 12px; color: {SUCCESS};")
                self._url_input.setEnabled(False)
                self._link_btn.setText("Linked")
            elif result and result.get("error"):
                self._result_lbl.setText(result["error"])
                self._result_lbl.setStyleSheet(f"font-size: 12px; color: {ERROR};")
                self._link_btn.setEnabled(True)
                self._link_btn.setText("Link to Global")
            else:
                self._result_lbl.setText("Failed to link video. Please try again.")
                self._result_lbl.setStyleSheet(f"font-size: 12px; color: {ERROR};")
                self._link_btn.setEnabled(True)
                self._link_btn.setText("Link to Global")
        except Exception as e:
            log.error("Failed to link video: %s", e)
            self._result_lbl.setText(f"Error: {e}")
            self._result_lbl.setStyleSheet(f"font-size: 12px; color: {ERROR};")
            self._link_btn.setEnabled(True)
            self._link_btn.setText("Link to Global")
