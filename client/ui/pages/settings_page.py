"""Settings page — all app configuration in organized sections."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSlider, QSpinBox, QGroupBox, QFileDialog, QScrollArea,
    QFrame, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor

from ...core.config import save_config
from ...core.constants import EVENT_CONFIG_CHANGED, EVENT_REPARSE_REQUESTED
from ...core.logger import get_logger
from ..theme import TEXT_MUTED, BORDER, ACCENT

log = get_logger("Settings")

# Overlay shortcut definitions: (display label, _HOTKEY_MAP key, description)
_OVERLAY_SHORTCUTS = [
    ("Search", "f", "Ctrl+F", "Open the search overlay"),
    ("Map", "m", "Ctrl+M", "Open the map overlay"),
    ("Exchange", "e", "Ctrl+E", "Open the exchange overlay"),
    ("Notifications", "n", "Ctrl+N", "Open the notifications overlay"),
]


class SettingsPage(QWidget):
    """Application settings with sections for account, OCR, hotkeys, etc."""

    def __init__(self, *, config, config_path, event_bus, signals, oauth,
                 on_show_changelog=None):
        super().__init__()
        self._config = config
        self._config_path = config_path
        self._event_bus = event_bus
        self._signals = signals
        self._oauth = oauth
        self._on_show_changelog = on_show_changelog

        # Scroll area for all settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self._layout = QVBoxLayout(content)

        self._build_account_section()
        self._build_chat_section()
        self._build_ocr_section()
        self._build_overlay_section()
        self._build_overlay_shortcuts_section()
        self._build_about_section()
        self._build_legal_section()
        self._build_advanced_section()

        self._layout.addStretch()

        # Save button (always visible, outside Advanced)
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._save_settings)
        save_row.addWidget(save_btn)
        self._layout.addLayout(save_row)

        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        header = QLabel("Settings")
        header.setObjectName("pageHeader")
        outer.addWidget(header)
        outer.addWidget(scroll)

        # Connect auth state changes and apply current state
        signals.auth_state_changed.connect(self._on_auth_changed)
        self._on_auth_changed(oauth.auth_state)

    # --- Account ---
    def _build_account_section(self):
        group = QGroupBox("Account")
        layout = QVBoxLayout(group)

        self._auth_status = QLabel("Not logged in")
        layout.addWidget(self._auth_status)

        btn_row = QHBoxLayout()
        self._login_btn = QPushButton("Login with Entropia Nexus")
        self._login_btn.clicked.connect(self._on_login)
        btn_row.addWidget(self._login_btn)

        self._logout_btn = QPushButton("Logout")
        self._logout_btn.clicked.connect(self._on_logout)
        self._logout_btn.setEnabled(False)
        btn_row.addWidget(self._logout_btn)
        btn_row.addStretch()

        layout.addLayout(btn_row)
        self._layout.addWidget(group)

    def _on_login(self):
        self._login_btn.setEnabled(False)
        self._login_btn.setText("Logging in...")
        import threading
        threading.Thread(target=self._do_login, daemon=True).start()

    def _do_login(self):
        self._oauth.login()

    def _on_logout(self):
        self._oauth.logout()

    def _on_auth_changed(self, state):
        if state.authenticated:
            self._auth_status.setText(f"Logged in as: {state.username}")
            self._login_btn.setEnabled(False)
            self._login_btn.setText("Login with Entropia Nexus")
            self._logout_btn.setEnabled(True)
        else:
            self._auth_status.setText("Not logged in")
            self._login_btn.setEnabled(True)
            self._login_btn.setText("Login with Entropia Nexus")
            self._logout_btn.setEnabled(False)

    # --- Chat Log ---
    def _build_chat_section(self):
        group = QGroupBox("Chat Log")
        layout = QVBoxLayout(group)

        # Chat log path
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Chat log path:"))
        self._chat_path = QLineEdit(self._config.chat_log_path)
        path_row.addWidget(self._chat_path)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_chat_path)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # Poll interval
        poll_row = QHBoxLayout()
        poll_row.addWidget(QLabel("Poll interval (ms):"))
        self._poll_interval = QSpinBox()
        self._poll_interval.setRange(100, 2000)
        self._poll_interval.setValue(self._config.poll_interval_ms)
        poll_row.addWidget(self._poll_interval)
        poll_row.addStretch()
        layout.addLayout(poll_row)

        # Re-parse button
        reparse_row = QHBoxLayout()
        self._reparse_btn = QPushButton("Re-parse Chat Log")
        self._reparse_btn.setToolTip(
            "Re-read the entire chat.log from the beginning.\n"
            "Globals and trade messages will be re-submitted to the server."
        )
        self._reparse_btn.clicked.connect(self._on_reparse)
        reparse_row.addWidget(self._reparse_btn)
        reparse_row.addStretch()
        layout.addLayout(reparse_row)

        self._layout.addWidget(group)

    def _on_reparse(self):
        self._reparse_btn.setEnabled(False)
        self._reparse_btn.setText("Re-parsing...")
        self._event_bus.publish(EVENT_REPARSE_REQUESTED, None)

        # Use Qt signal (thread-safe) instead of EventBus callback which
        # would run on the background reparse thread and crash Qt.
        self._signals.catchup_complete.connect(self._on_reparse_done)

    def _on_reparse_done(self, _data):
        self._reparse_btn.setEnabled(True)
        self._reparse_btn.setText("Re-parse Chat Log")
        self._signals.catchup_complete.disconnect(self._on_reparse_done)

    def _browse_chat_path(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select chat.log", "", "Log files (*.log);;All files (*)")
        if path:
            self._chat_path.setText(path)

    # --- OCR ---
    def _build_ocr_section(self):
        group = QGroupBox("OCR")
        layout = QVBoxLayout(group)

        desc = QLabel("Configure which OCR functions are active.")
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(desc)

        self._skill_scanner_cb = QCheckBox("Skill scanner")
        self._skill_scanner_cb.setToolTip(
            "Automatically scan the in-game Skills window to read\n"
            "skill values via screen capture and OCR."
        )
        self._skill_scanner_cb.setChecked(self._config.overlay_enabled)
        layout.addWidget(self._skill_scanner_cb)

        # Scan ROI configuration
        roi_row = QHBoxLayout()
        roi_btn = QPushButton("Configure Scan ROIs")
        roi_btn.setToolTip("Adjust pixel offsets for scan debug overlay regions")
        roi_btn.clicked.connect(self._open_roi_dialog)
        roi_row.addWidget(roi_btn)
        roi_row.addStretch()
        layout.addLayout(roi_row)

        self._layout.addWidget(group)

    def _open_roi_dialog(self):
        from ..dialogs.scan_roi_dialog import ScanRoiDialog
        dlg = ScanRoiDialog(
            config=self._config,
            config_path=self._config_path,
            event_bus=self._event_bus,
            parent=self,
        )
        dlg.exec()

    # --- Overlay ---
    def _build_overlay_section(self):
        group = QGroupBox("Overlay")
        layout = QVBoxLayout(group)

        # Opacity
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Opacity:"))
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(20, 100)
        self._opacity_slider.setValue(int(self._config.overlay_opacity * 100))
        opacity_row.addWidget(self._opacity_slider)
        self._opacity_label = QLabel(f"{self._config.overlay_opacity:.0%}")
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
        opacity_row.addWidget(self._opacity_label)
        layout.addLayout(opacity_row)

        # Auto-pin detail overlays
        self._auto_pin_cb = QCheckBox("Auto-pin detail overlays")
        self._auto_pin_cb.setToolTip(
            "New detail overlays opened from search will start pinned,\n"
            "so they stay open when selecting another item."
        )
        self._auto_pin_cb.setChecked(self._config.auto_pin_detail_overlay)
        layout.addWidget(self._auto_pin_cb)

        self._layout.addWidget(group)

    # --- Overlay Shortcuts ---
    def _build_overlay_shortcuts_section(self):
        group = QGroupBox("Overlay Shortcuts")
        layout = QVBoxLayout(group)

        desc = QLabel(
            "These shortcuts are active while the game or an overlay has focus."
        )
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        for name, _key, combo, tooltip in _OVERLAY_SHORTCUTS:
            row = QHBoxLayout()
            lbl = QLabel(f"{name}:")
            lbl.setMinimumWidth(100)
            row.addWidget(lbl)
            shortcut_label = QLabel(combo)
            shortcut_label.setStyleSheet(
                f"color: {ACCENT}; font-weight: bold; font-size: 12px;"
            )
            shortcut_label.setToolTip(tooltip)
            row.addWidget(shortcut_label)
            row.addStretch()
            layout.addLayout(row)

        self._layout.addWidget(group)

    # --- About ---
    def _build_about_section(self):
        group = QGroupBox("About")
        layout = QVBoxLayout(group)

        from ...updater import get_local_version
        version = get_local_version()
        layout.addWidget(QLabel(f"Version: {version}"))

        btn_row = QHBoxLayout()
        if self._on_show_changelog:
            changelog_btn = QPushButton("View Changelog")
            changelog_btn.clicked.connect(self._on_show_changelog)
            btn_row.addWidget(changelog_btn)

        kofi_btn = QPushButton("Support on Ko-fi")
        kofi_btn.setToolTip("https://ko-fi.com/C0C21JO3B1")
        kofi_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        kofi_btn.clicked.connect(self._open_kofi)
        btn_row.addWidget(kofi_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._updates_cb = QCheckBox("Check for updates automatically")
        self._updates_cb.setChecked(self._config.check_for_updates)
        layout.addWidget(self._updates_cb)

        self._layout.addWidget(group)

    def _open_kofi(self):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl("https://ko-fi.com/C0C21JO3B1"))

    # --- Legal ---
    def _build_legal_section(self):
        group = QGroupBox("Legal")
        layout = QVBoxLayout(group)

        btn = QPushButton("View Terms of Use & Privacy Policy")
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.clicked.connect(self._show_tos)
        layout.addWidget(btn)

        self._layout.addWidget(group)

    def _show_tos(self):
        from ..dialogs.tos_dialog import TosDialog
        dlg = TosDialog(read_only=True, parent=self)
        dlg.exec()

    # --- Advanced (hidden by default) ---
    def _build_advanced_section(self):
        self._advanced_group = QGroupBox("Advanced")
        layout = QVBoxLayout(self._advanced_group)

        # Database path
        db_row = QHBoxLayout()
        db_row.addWidget(QLabel("Database path:"))
        self._db_path = QLineEdit(self._config.database_path)
        self._db_path.setReadOnly(True)
        db_row.addWidget(self._db_path)
        layout.addLayout(db_row)

        # JS utils path override
        js_row = QHBoxLayout()
        js_row.addWidget(QLabel("JS utils path (override):"))
        self._js_path = QLineEdit(self._config.js_utils_path)
        js_row.addWidget(self._js_path)
        js_browse = QPushButton("Browse")
        js_browse.clicked.connect(self._browse_js_path)
        js_row.addWidget(js_browse)
        layout.addLayout(js_row)

        # OAuth client ID
        oauth_row = QHBoxLayout()
        oauth_row.addWidget(QLabel("OAuth Client ID:"))
        self._oauth_client_id = QLineEdit(self._config.oauth_client_id)
        oauth_row.addWidget(self._oauth_client_id)
        layout.addLayout(oauth_row)

        self._advanced_group.setVisible(False)
        self._layout.addWidget(self._advanced_group)

        # Toggle button to show/hide
        toggle_btn = QPushButton("Show Advanced Settings")
        toggle_btn.setFlat(True)
        toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        toggle_btn.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; text-decoration: underline;"
            f" border: none; padding: 2px;"
        )

        def _toggle():
            visible = not self._advanced_group.isVisible()
            self._advanced_group.setVisible(visible)
            toggle_btn.setText(
                "Hide Advanced Settings" if visible else "Show Advanced Settings"
            )

        toggle_btn.clicked.connect(_toggle)
        self._layout.addWidget(toggle_btn, alignment=Qt.AlignmentFlag.AlignLeft)

    def _browse_js_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select JS utils directory")
        if path:
            self._js_path.setText(path)

    def _save_settings(self):
        """Apply all settings from the UI to config and persist."""
        self._config.chat_log_path = self._chat_path.text()
        self._config.poll_interval_ms = self._poll_interval.value()
        self._config.overlay_opacity = self._opacity_slider.value() / 100.0
        self._config.auto_pin_detail_overlay = self._auto_pin_cb.isChecked()
        self._config.overlay_enabled = self._skill_scanner_cb.isChecked()
        self._config.check_for_updates = self._updates_cb.isChecked()
        self._config.js_utils_path = self._js_path.text()
        self._config.oauth_client_id = self._oauth_client_id.text()

        save_config(self._config, self._config_path)
        self._event_bus.publish(EVENT_CONFIG_CHANGED, self._config)
        log.info("Saved")
