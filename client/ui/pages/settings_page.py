"""Settings page — all app configuration in organized sections."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSlider, QSpinBox, QGroupBox, QFileDialog, QScrollArea, QKeySequenceEdit,
    QDoubleSpinBox, QFrame, QCheckBox,
)
from PyQt6.QtCore import Qt

from ...core.config import save_config
from ...core.constants import EVENT_CONFIG_CHANGED, EVENT_REPARSE_REQUESTED
from ...core.logger import get_logger

log = get_logger("Settings")


class SettingsPage(QWidget):
    """Application settings with sections for account, OCR, hotkeys, etc."""

    def __init__(self, *, config, config_path, event_bus, signals, oauth):
        super().__init__()
        self._config = config
        self._config_path = config_path
        self._event_bus = event_bus
        self._signals = signals
        self._oauth = oauth

        # Scroll area for all settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self._layout = QVBoxLayout(content)

        self._build_account_section()
        self._build_chat_section()
        self._build_ocr_section()
        self._build_hunt_section()
        self._build_hotkeys_section()
        self._build_overlay_section()
        self._build_advanced_section()

        self._layout.addStretch()
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
            "Globals and trade messages will be re-submitted to the server.\n"
            "Hunt tracking and other trackers are not affected."
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

        # Tesseract path
        tess_row = QHBoxLayout()
        tess_row.addWidget(QLabel("Tesseract path:"))
        self._tesseract_path = QLineEdit(self._config.tesseract_path)
        tess_row.addWidget(self._tesseract_path)
        tess_browse = QPushButton("Browse")
        tess_browse.clicked.connect(self._browse_tesseract)
        tess_row.addWidget(tess_browse)
        layout.addLayout(tess_row)

        # Confidence threshold
        conf_row = QHBoxLayout()
        conf_row.addWidget(QLabel("Confidence threshold:"))
        self._ocr_confidence = QDoubleSpinBox()
        self._ocr_confidence.setRange(0.5, 1.0)
        self._ocr_confidence.setSingleStep(0.05)
        self._ocr_confidence.setValue(self._config.ocr_confidence_threshold)
        conf_row.addWidget(self._ocr_confidence)
        conf_row.addStretch()
        layout.addLayout(conf_row)

        # Mob detection info
        mob_info = QLabel("Mob name detection: automatic (nameplate scanning)")
        mob_info.setObjectName("mutedText")
        layout.addWidget(mob_info)

        # Tool name region calibration
        region_row = QHBoxLayout()
        self._calibrate_tool_btn = QPushButton("Calibrate Tool Name Region")
        self._calibrate_tool_btn.setToolTip("Draw a rectangle over the active tool name area")
        region_row.addWidget(self._calibrate_tool_btn)
        region_row.addStretch()
        layout.addLayout(region_row)

        tool_region_text = self._format_region(self._config.tool_name_region)
        self._tool_region_label = QLabel(f"Tool name region: {tool_region_text}")
        layout.addWidget(self._tool_region_label)

        self._layout.addWidget(group)

    def _browse_tesseract(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Tesseract executable", "",
            "Executables (*.exe);;All files (*)"
        )
        if path:
            self._tesseract_path.setText(path)

    @staticmethod
    def _format_region(region):
        if region:
            return f"({region[0]}, {region[1]}, {region[2]}x{region[3]})"
        return "Not configured"

    # --- Hunt Tracking ---
    def _build_hunt_section(self):
        group = QGroupBox("Hunt Tracking")
        layout = QVBoxLayout(group)

        # Attribution window
        attr_row = QHBoxLayout()
        attr_row.addWidget(QLabel("Attribution window (ms):"))
        self._attribution_window = QSpinBox()
        self._attribution_window.setRange(500, 10000)
        self._attribution_window.setValue(self._config.attribution_window_ms)
        attr_row.addWidget(self._attribution_window)
        attr_row.addStretch()
        layout.addLayout(attr_row)

        # Encounter close timeout
        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel("Encounter close timeout (ms):"))
        self._encounter_timeout = QSpinBox()
        self._encounter_timeout.setRange(5000, 60000)
        self._encounter_timeout.setSingleStep(1000)
        self._encounter_timeout.setValue(self._config.encounter_close_timeout_ms)
        timeout_row.addWidget(self._encounter_timeout)
        timeout_row.addStretch()
        layout.addLayout(timeout_row)

        self._layout.addWidget(group)

    # --- Hotkeys ---
    def _build_hotkeys_section(self):
        group = QGroupBox("Hotkeys")
        layout = QVBoxLayout(group)

        self._hotkey_inputs = {}
        hotkey_defs = [
            ("OCR Scan", "hotkey_ocr_scan"),
            ("Start Hunt", "hotkey_start_hunt"),
            ("Stop Hunt", "hotkey_stop_hunt"),
            ("Manual Mob Name", "hotkey_manual_mob_name"),
        ]

        for label_text, config_key in hotkey_defs:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{label_text}:"))
            key_edit = QKeySequenceEdit()
            current = getattr(self._config, config_key, "")
            if current:
                from PyQt6.QtGui import QKeySequence
                key_edit.setKeySequence(QKeySequence(current))
            row.addWidget(key_edit)

            clear_btn = QPushButton("Clear")
            clear_btn.clicked.connect(lambda checked, ke=key_edit: ke.clear())
            row.addWidget(clear_btn)
            row.addStretch()
            layout.addLayout(row)
            self._hotkey_inputs[config_key] = key_edit

        self._layout.addWidget(group)

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

    # --- Advanced ---
    def _build_advanced_section(self):
        group = QGroupBox("Advanced")
        layout = QVBoxLayout(group)

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

        self._layout.addWidget(group)

        # Save button
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._save_settings)
        save_row.addWidget(save_btn)
        self._layout.addLayout(save_row)

    def _browse_js_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select JS utils directory")
        if path:
            self._js_path.setText(path)

    def _save_settings(self):
        """Apply all settings from the UI to config and persist."""
        self._config.chat_log_path = self._chat_path.text()
        self._config.poll_interval_ms = self._poll_interval.value()
        self._config.tesseract_path = self._tesseract_path.text()
        self._config.ocr_confidence_threshold = self._ocr_confidence.value()
        self._config.attribution_window_ms = self._attribution_window.value()
        self._config.encounter_close_timeout_ms = self._encounter_timeout.value()
        self._config.overlay_opacity = self._opacity_slider.value() / 100.0
        self._config.auto_pin_detail_overlay = self._auto_pin_cb.isChecked()
        self._config.js_utils_path = self._js_path.text()
        self._config.oauth_client_id = self._oauth_client_id.text()

        # Hotkeys
        for config_key, key_edit in self._hotkey_inputs.items():
            seq = key_edit.keySequence().toString()
            setattr(self._config, config_key, seq)

        save_config(self._config, self._config_path)
        self._event_bus.publish(EVENT_CONFIG_CHANGED, self._config)
        log.info("Saved")
