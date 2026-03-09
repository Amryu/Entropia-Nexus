"""Settings page — all app configuration in organized sections."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSlider, QSpinBox, QDoubleSpinBox, QGroupBox, QFileDialog, QScrollArea,
    QFrame, QCheckBox, QTextEdit, QGridLayout, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor

from ...core.config import save_config
from ...core.constants import EVENT_CONFIG_CHANGED, EVENT_REPARSE_REQUESTED
from ...core.logger import get_logger
from ..theme import TEXT_MUTED, BORDER, ACCENT
from ..widgets.hotkey_input import HotkeyInput

log = get_logger("Settings")

# Overlay hotkey definitions: (display label, config_key, tooltip)
_OVERLAY_HOTKEY_DEFS = [
    ("Search", "hotkey_search", "Open the search overlay"),
    ("Map", "hotkey_map", "Open the map overlay"),
    ("Exchange", "hotkey_exchange", "Open the exchange overlay"),
    ("Notifications", "hotkey_notifications", "Open the notifications overlay"),
    ("Debug Overlay", "hotkey_debug", "Toggle OCR/target lock debug overlay"),
]

_OVERLAY_HOTKEY_DEFAULTS = {
    "hotkey_search": "ctrl+f",
    "hotkey_map": "ctrl+m",
    "hotkey_exchange": "ctrl+e",
    "hotkey_notifications": "ctrl+n",
    "hotkey_debug": "f3",
}


class SettingsPage(QWidget):
    """Application settings with sections for account, OCR, hotkeys, etc."""

    def __init__(self, *, config, config_path, event_bus, signals, oauth, db=None,
                 on_show_changelog=None):
        super().__init__()
        self._config = config
        self._config_path = config_path
        self._event_bus = event_bus
        self._signals = signals
        self._oauth = oauth
        self._db = db
        self._on_show_changelog = on_show_changelog
        self._importer = None

        # Debounce timer for auto-saving settings
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._do_save)

        # Scroll area for all settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self._layout = QVBoxLayout(content)
        self._sections: list[QWidget] = []

        self._build_account_section()
        self._build_chat_section()
        self._build_dashboard_section()
        self._build_ocr_section()
        self._build_overlay_section()
        self._build_overlay_shortcuts_section()
        self._build_screenshot_section()
        self._build_video_section()
        self._build_about_section()
        self._build_legal_section()
        self._build_advanced_section()

        self._layout.addStretch()

        scroll.setWidget(content)

        # Connect change signals for realtime auto-save
        self._chat_path.editingFinished.connect(self._schedule_save)
        self._poll_interval.valueChanged.connect(self._schedule_save)
        self._opacity_slider.valueChanged.connect(self._schedule_save)
        self._auto_pin_cb.stateChanged.connect(self._schedule_save)
        self._skill_scanner_cb.stateChanged.connect(self._schedule_save)
        self._updates_cb.stateChanged.connect(self._schedule_save)
        self._js_path.editingFinished.connect(self._schedule_save)
        self._oauth_client_id.editingFinished.connect(self._schedule_save)

        outer = QVBoxLayout(self)

        self._header = QLabel("Settings")
        self._header.setObjectName("pageHeader")
        outer.addWidget(self._header)

        # Search bar
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search settings...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setStyleSheet(
            f"QLineEdit {{ border: 1px solid {BORDER}; border-radius: 4px;"
            f" padding: 5px 8px; font-size: 12px; }}"
        )
        self._search_timer_filter = QTimer(self)
        self._search_timer_filter.setSingleShot(True)
        self._search_timer_filter.setInterval(150)
        self._search_timer_filter.timeout.connect(self._apply_search_filter)
        self._search_input.textChanged.connect(
            lambda: self._search_timer_filter.start()
        )
        outer.addWidget(self._search_input)

        outer.addWidget(scroll)

        # Build searchable text index: {section_widget: [all_text_in_section]}
        self._section_texts: dict[QWidget, list[str]] = {}
        for section in self._sections:
            texts = [section.title()] if hasattr(section, 'title') else []
            for child in section.findChildren(QLabel):
                t = child.text()
                if t:
                    texts.append(t)
            for child in section.findChildren(QCheckBox):
                t = child.text()
                if t:
                    texts.append(t)
            for child in section.findChildren(QPushButton):
                t = child.text()
                if t:
                    texts.append(t)
            self._section_texts[section] = texts

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
        self._sections.append(group)
        self._layout.addWidget(group)

    def _on_login(self):
        self._login_btn.setEnabled(False)
        self._login_btn.setText("Waiting for browser...")
        import threading
        threading.Thread(target=self._do_login, daemon=True, name="oauth-login").start()

    def _do_login(self):
        try:
            result = self._oauth.login()
            if result is not True:
                QTimer.singleShot(0, lambda: self._on_login_failed(
                    result if isinstance(result, str) else "Login failed"))
        except Exception as e:
            QTimer.singleShot(0, lambda: self._on_login_failed(str(e)))

    def _on_login_failed(self, message: str):
        self._login_btn.setEnabled(True)
        self._login_btn.setText("Login with Entropia Nexus")
        self._auth_status.setText(message)
        self._auth_status.setStyleSheet(f"color: #ff6b6b;")

    def _on_logout(self):
        self._oauth.logout()

    def _on_auth_changed(self, state):
        self._auth_status.setStyleSheet("")
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

        # Import historical log
        import_row = QHBoxLayout()
        self._import_btn = QPushButton("Import Historical Log")
        self._import_btn.setToolTip(
            "Parse a chat log file and add its globals and trade messages\n"
            "to the local database for upload. Useful for adding historical data."
        )
        self._import_btn.clicked.connect(self._on_import_historical)
        import_row.addWidget(self._import_btn)
        self._import_status = QLabel("")
        self._import_status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        import_row.addWidget(self._import_status)
        import_row.addStretch()
        layout.addLayout(import_row)

        self._sections.append(group)
        self._layout.addWidget(group)

    def _on_reparse(self):
        self._reparse_btn.setEnabled(False)
        self._import_btn.setEnabled(False)
        self._reparse_btn.setText("Re-parsing...")
        self._event_bus.publish(EVENT_REPARSE_REQUESTED, None)

        # Use Qt signal (thread-safe) instead of EventBus callback which
        # would run on the background reparse thread and crash Qt.
        self._signals.catchup_complete.connect(self._on_reparse_done)

    def _on_reparse_done(self, _data):
        self._reparse_btn.setEnabled(True)
        self._import_btn.setEnabled(True)
        self._reparse_btn.setText("Re-parse Chat Log")
        self._signals.catchup_complete.disconnect(self._on_reparse_done)

    def _on_import_historical(self):
        if not self._db:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select chat log to import", "",
            "Log files (*.log);;All files (*)",
        )
        if not path:
            return

        from ...chat_parser.importer import HistoricalImporter

        self._importer = HistoricalImporter(self._event_bus, self._db)
        self._import_btn.setEnabled(False)
        self._reparse_btn.setEnabled(False)
        self._import_btn.setText("Importing...")
        self._import_status.setText("")

        self._signals.historical_import_progress.connect(self._on_import_progress)
        self._signals.historical_import_complete.connect(self._on_import_done)

        import threading
        threading.Thread(
            target=self._importer.import_file, args=(path,),
            daemon=True, name="historical-import",
        ).start()

    def _on_import_progress(self, data):
        lines = data.get("lines", 0)
        total = data.get("total_bytes", 1)
        parsed = data.get("parsed_bytes", 0)
        pct = int(parsed / total * 100) if total else 0
        self._import_btn.setText(f"Importing... {pct}%")
        self._import_status.setText(f"{lines:,} lines parsed")

    def _on_import_done(self, data):
        self._import_btn.setEnabled(True)
        self._reparse_btn.setEnabled(True)
        self._import_btn.setText("Import Historical Log")
        self._signals.historical_import_progress.disconnect(self._on_import_progress)
        self._signals.historical_import_complete.disconnect(self._on_import_done)
        self._importer = None

        error = data.get("error")
        if error:
            self._import_status.setText(f"Error: {error}")
            self._import_status.setStyleSheet(f"color: red; font-size: 11px;")
        else:
            g = data.get("globals_found", 0)
            t = data.get("trades_found", 0)
            lines = data.get("lines_parsed", 0)
            self._import_status.setText(
                f"Done — {lines:,} lines, {g:,} globals, {t:,} trades imported"
            )
            self._import_status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")

    def _browse_chat_path(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select chat.log", "", "Log files (*.log);;All files (*)")
        if path:
            self._chat_path.setText(path)
            self._schedule_save()

    # --- Dashboard ---
    def _build_dashboard_section(self):
        from ...exchange.constants import PLANETS
        from ...chat_parser.models import GlobalType

        group = QGroupBox("Dashboard")
        self._dashboard_group = group
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        # --- Globals subsection ---
        globals_lbl = QLabel("Globals Feed")
        globals_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(globals_lbl)

        # Min value
        min_row = QHBoxLayout()
        min_row.addWidget(QLabel("Minimum value to display:"))
        self._dash_globals_min = QDoubleSpinBox()
        self._dash_globals_min.setRange(0, 999999)
        self._dash_globals_min.setDecimals(0)
        self._dash_globals_min.setValue(
            getattr(self._config, "dashboard_globals_min_value", 0)
        )
        self._dash_globals_min.setSpecialValueText("Show all")
        self._dash_globals_min.setSuffix(" PED")
        self._dash_globals_min.setFixedWidth(120)
        self._dash_globals_min.setToolTip(
            "Globals below this value won't appear in the dashboard ticker. "
            "They are still processed for notifications."
        )
        self._dash_globals_min.valueChanged.connect(self._schedule_save)
        min_row.addWidget(self._dash_globals_min)
        min_row.addStretch()
        layout.addLayout(min_row)

        # Blocked types
        blocked_lbl = QLabel("Blocked global types:")
        blocked_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(blocked_lbl)

        _type_options = [
            ("kill", "Hunt"),
            ("team_kill", "Team Hunt"),
            ("deposit", "Mining"),
            ("craft", "Crafting"),
            ("rare_item", "Rare Item"),
            ("discovery", "Discovery"),
            ("tier", "Tier Record"),
            ("examine", "Instance"),
            ("pvp", "PvP"),
        ]
        blocked = set(getattr(self._config, "dashboard_globals_blocked_types", []))
        type_grid = QGridLayout()
        type_grid.setSpacing(4)
        self._dash_globals_type_cbs: dict[str, QCheckBox] = {}
        cols = 3
        for i, (key, label) in enumerate(_type_options):
            cb = QCheckBox(label)
            cb.setChecked(key in blocked)
            cb.stateChanged.connect(self._schedule_save)
            type_grid.addWidget(cb, i // cols, i % cols)
            self._dash_globals_type_cbs[key] = cb
        layout.addLayout(type_grid)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(sep1)

        # --- Trade subsection ---
        trade_lbl = QLabel("Trade Chat Feed")
        trade_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(trade_lbl)

        # Block list (players)
        block_lbl = QLabel("Block list (one player per line):")
        block_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(block_lbl)

        self._dash_trade_blocklist = QTextEdit()
        self._dash_trade_blocklist.setFixedHeight(60)
        self._dash_trade_blocklist.setPlainText(
            "\n".join(getattr(self._config, "dashboard_trade_blocklist", []))
        )
        self._dash_trade_blocklist.textChanged.connect(self._schedule_save)
        layout.addWidget(self._dash_trade_blocklist)

        # Planet filter
        planet_lbl = QLabel("Show only channels from these planets (empty = all):")
        planet_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(planet_lbl)

        planet_grid = QGridLayout()
        planet_grid.setSpacing(4)
        active_planets = set(getattr(self._config, "dashboard_trade_planet_filter", []))
        self._dash_trade_planet_cbs: dict[str, QCheckBox] = {}
        for i, p in enumerate(PLANETS):
            cb = QCheckBox(p)
            cb.setChecked(p in active_planets)
            cb.stateChanged.connect(self._schedule_save)
            planet_grid.addWidget(cb, i // 3, i % 3)
            self._dash_trade_planet_cbs[p] = cb
        layout.addLayout(planet_grid)

        # Blacklist (keywords/regex)
        bl_lbl = QLabel("Blacklist keywords (one per line, regex supported):")
        bl_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        bl_lbl.setToolTip(
            "Messages containing any of these keywords will be hidden. "
            "Each line is treated as a case-insensitive regex pattern."
        )
        layout.addWidget(bl_lbl)

        self._dash_trade_blacklist = QTextEdit()
        self._dash_trade_blacklist.setFixedHeight(60)
        self._dash_trade_blacklist.setPlainText(
            "\n".join(getattr(self._config, "dashboard_trade_blacklist", []))
        )
        self._dash_trade_blacklist.textChanged.connect(self._schedule_save)
        layout.addWidget(self._dash_trade_blacklist)

        self._sections.append(group)
        self._layout.addWidget(group)

    # --- OCR ---
    def _build_ocr_section(self):
        group = QGroupBox("OCR")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        # -- General --
        general_lbl = QLabel("General")
        general_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(general_lbl)

        backend_row = QHBoxLayout()
        backend_row.addWidget(QLabel("Window capture backend:"))
        self._ocr_capture_backend = QComboBox()
        self._ocr_capture_backend.addItem("Auto (recommended)", "auto")
        self._ocr_capture_backend.addItem("Windows Graphics Capture (HDR-safe)", "wgc")
        self._ocr_capture_backend.addItem("BitBlt (no flicker)", "bitblt")
        self._ocr_capture_backend.addItem("PrintWindow (legacy fallback)", "printwindow")
        self._ocr_capture_backend.setToolTip(
            "Select how the game window is captured for OCR.\n"
            "Changes apply immediately.\n\n"
            "Auto: Uses WGC (borderless if supported, yellow border otherwise).\n"
            "WGC: Forces Windows Graphics Capture (no game interference).\n"
            "BitBlt: Reads window buffer directly (no flicker, no border, may be black for DX).\n"
            "PrintWindow: Forces window repaint (no border, may cause game flickering)."
        )
        current_backend = getattr(self._config, "ocr_capture_backend", "auto")
        backend_index = self._ocr_capture_backend.findData(current_backend)
        self._ocr_capture_backend.setCurrentIndex(backend_index if backend_index >= 0 else 0)
        self._ocr_capture_backend.currentIndexChanged.connect(self._schedule_save)
        backend_row.addWidget(self._ocr_capture_backend)
        backend_row.addStretch()
        layout.addLayout(backend_row)

        self._ocr_trace_cb = QCheckBox("Trace OCR")
        self._ocr_trace_cb.setToolTip(
            "Enable detailed OCR tracing. Outputs step-by-step log and\n"
            "debug images for every OCR match.\n"
            "WARNING: Generates significant data output.\n"
            "Images auto-cleanup after 3 minutes."
        )
        self._ocr_trace_cb.setChecked(self._config.ocr_trace_enabled)
        self._ocr_trace_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._ocr_trace_cb)

        reset_row = QHBoxLayout()
        reset_btn = QPushButton("Reset thresholds to defaults")
        reset_btn.setToolTip(
            "Reset all OCR match thresholds to their default values."
        )
        reset_btn.clicked.connect(self._reset_ocr_thresholds)
        reset_row.addWidget(reset_btn)
        reset_row.addStretch()
        layout.addLayout(reset_row)

        # Separator
        sep_general = QFrame()
        sep_general.setFrameShape(QFrame.Shape.HLine)
        sep_general.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(sep_general)

        # -- Skill Scanner --
        scan_lbl = QLabel("Skill Scanner")
        scan_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(scan_lbl)

        self._skill_scanner_cb = QCheckBox("Enable skill scanner")
        self._skill_scanner_cb.setToolTip(
            "Automatically scan the in-game Skills window to read\n"
            "skill values via screen capture and OCR."
        )
        self._skill_scanner_cb.setChecked(self._config.overlay_enabled)
        layout.addWidget(self._skill_scanner_cb)

        scan_roi_row = QHBoxLayout()
        scan_roi_btn = QPushButton("Configure ROIs...")
        scan_roi_btn.setToolTip("Adjust pixel offsets for scan debug overlay regions")
        scan_roi_btn.clicked.connect(self._open_scan_roi_dialog)
        scan_roi_row.addWidget(scan_roi_btn)
        scan_roi_row.addStretch()
        layout.addLayout(scan_roi_row)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(sep1)

        # -- Target Lock --
        tl_lbl = QLabel("Target Lock Detection")
        tl_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(tl_lbl)

        self._target_lock_cb = QCheckBox("Enable target lock detection")
        self._target_lock_cb.setChecked(self._config.target_lock_enabled)
        self._target_lock_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._target_lock_cb)

        tl_thresh_row = QHBoxLayout()
        tl_thresh_row.addWidget(QLabel("Match threshold:"))
        self._target_lock_threshold = QDoubleSpinBox()
        self._target_lock_threshold.setRange(0.5, 1.0)
        self._target_lock_threshold.setDecimals(2)
        self._target_lock_threshold.setSingleStep(0.05)
        self._target_lock_threshold.setValue(self._config.target_lock_match_threshold)
        self._target_lock_threshold.setFixedWidth(80)
        self._target_lock_threshold.setToolTip(
            "Minimum template matching confidence (0.5–1.0).\n"
            "Lower values detect dimmed icons but may cause false positives."
        )
        self._target_lock_threshold.valueChanged.connect(self._schedule_save)
        tl_thresh_row.addWidget(self._target_lock_threshold)
        tl_thresh_row.addStretch()
        layout.addLayout(tl_thresh_row)

        tl_roi_row = QHBoxLayout()
        tl_roi_btn = QPushButton("Configure ROIs...")
        tl_roi_btn.setToolTip("Adjust HP bar, shared icon, and name region offsets")
        tl_roi_btn.clicked.connect(self._open_target_lock_roi_dialog)
        tl_roi_row.addWidget(tl_roi_btn)
        tl_roi_row.addStretch()
        layout.addLayout(tl_roi_row)

        # Separator
        sep_ps = QFrame()
        sep_ps.setFrameShape(QFrame.Shape.HLine)
        sep_ps.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(sep_ps)

        # -- Player Status (Heart) --
        ps_lbl = QLabel("Player Status Detection")
        ps_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(ps_lbl)

        self._player_status_cb = QCheckBox("Enable player status detection")
        self._player_status_cb.setChecked(self._config.player_status_enabled)
        self._player_status_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._player_status_cb)

        ps_thresh_row = QHBoxLayout()
        ps_thresh_row.addWidget(QLabel("Match threshold:"))
        self._player_status_threshold = QDoubleSpinBox()
        self._player_status_threshold.setRange(0.5, 1.0)
        self._player_status_threshold.setDecimals(2)
        self._player_status_threshold.setSingleStep(0.05)
        self._player_status_threshold.setValue(self._config.player_status_match_threshold)
        self._player_status_threshold.setFixedWidth(80)
        self._player_status_threshold.setToolTip(
            "Minimum template matching confidence (0.5\u20131.0).\n"
            "Lower values detect dimmed icons but may cause false positives."
        )
        self._player_status_threshold.valueChanged.connect(self._schedule_save)
        ps_thresh_row.addWidget(self._player_status_threshold)
        ps_thresh_row.addStretch()
        layout.addLayout(ps_thresh_row)

        ps_roi_row = QHBoxLayout()
        ps_roi_btn = QPushButton("Configure ROIs...")
        ps_roi_btn.setToolTip("Adjust health bar, reload bar, buff bar, and tool name region offsets")
        ps_roi_btn.clicked.connect(self._open_player_status_roi_dialog)
        ps_roi_row.addWidget(ps_roi_btn)
        ps_roi_row.addStretch()
        layout.addLayout(ps_roi_row)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(sep2)

        # -- Market Price --
        mp_lbl = QLabel("Market Price Detection")
        mp_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(mp_lbl)

        self._market_price_cb = QCheckBox("Enable market price detection")
        self._market_price_cb.setChecked(self._config.market_price_enabled)
        self._market_price_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._market_price_cb)

        self._market_price_review_cb = QCheckBox(
            "Ask for manual review when values can't be read"
        )
        self._market_price_review_cb.setToolTip(
            "When enabled, a dialog prompts you to fill in markup values\n"
            "that the game shows as >999999%, or to pick the correct item\n"
            "when the name is ambiguous (e.g. ArMatrix LR-10 vs LR-15)."
        )
        self._market_price_review_cb.setChecked(
            self._config.market_price_review_enabled
        )
        self._market_price_review_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._market_price_review_cb)

        mp_thresh_row = QHBoxLayout()
        mp_thresh_row.addWidget(QLabel("Match threshold:"))
        self._market_price_threshold = QDoubleSpinBox()
        self._market_price_threshold.setRange(0.5, 1.0)
        self._market_price_threshold.setDecimals(2)
        self._market_price_threshold.setSingleStep(0.05)
        self._market_price_threshold.setValue(self._config.market_price_match_threshold)
        self._market_price_threshold.setFixedWidth(80)
        self._market_price_threshold.setToolTip(
            "Minimum template matching confidence (0.5–1.0)."
        )
        self._market_price_threshold.valueChanged.connect(self._schedule_save)
        mp_thresh_row.addWidget(self._market_price_threshold)
        mp_thresh_row.addStretch()
        layout.addLayout(mp_thresh_row)

        mp_text_row = QHBoxLayout()
        mp_text_row.addWidget(QLabel("Text brightness threshold:"))
        self._market_price_text_threshold = QSpinBox()
        self._market_price_text_threshold.setRange(20, 200)
        self._market_price_text_threshold.setSingleStep(5)
        self._market_price_text_threshold.setValue(self._config.market_price_text_threshold)
        self._market_price_text_threshold.setFixedWidth(80)
        self._market_price_text_threshold.setToolTip(
            "Pixels below this brightness are treated as background noise.\n"
            "Raise if OCR picks up background bleed; lower if text is cut off."
        )
        self._market_price_text_threshold.valueChanged.connect(self._schedule_save)
        mp_text_row.addWidget(self._market_price_text_threshold)
        mp_text_row.addStretch()
        layout.addLayout(mp_text_row)

        mp_roi_row = QHBoxLayout()
        mp_roi_btn = QPushButton("Configure ROIs...")
        mp_roi_btn.setToolTip("Adjust name, cell, and tier region offsets")
        mp_roi_btn.clicked.connect(self._open_market_price_roi_dialog)
        mp_roi_row.addWidget(mp_roi_btn)
        mp_roi_row.addStretch()
        layout.addLayout(mp_roi_row)

        self._sections.append(group)
        self._layout.addWidget(group)

    def _reset_ocr_thresholds(self):
        """Reset all OCR threshold spinboxes to their AppConfig defaults."""
        self._target_lock_threshold.setValue(0.90)
        self._player_status_threshold.setValue(0.90)
        self._market_price_threshold.setValue(0.9)
        self._market_price_text_threshold.setValue(80)
        self._schedule_save()

    def _open_scan_roi_dialog(self):
        from ..dialogs.scan_roi_dialog import ScanRoiDialog
        dlg = ScanRoiDialog(
            config=self._config,
            config_path=self._config_path,
            event_bus=self._event_bus,
            parent=self,
        )
        dlg.exec()

    def _open_target_lock_roi_dialog(self):
        from ..dialogs.roi_offset_dialog import RoiOffsetDialog
        roi_defs = [
            ("HP Bar", "target_lock_roi_hp", ["dx", "dy", "w", "h"]),
            ("Shared Icon", "target_lock_roi_shared", ["dx", "dy", "w", "h"]),
            ("Name", "target_lock_roi_name", ["dx", "dy", "w", "h"]),
        ]
        dlg = RoiOffsetDialog(
            title="Target Lock ROI Configuration",
            roi_defs=roi_defs,
            config=self._config,
            config_path=self._config_path,
            parent=self,
        )
        dlg.exec()

    def _open_market_price_roi_dialog(self):
        from ..dialogs.roi_offset_dialog import RoiOffsetDialog
        roi_defs = [
            ("Name Row 1", "market_price_roi_name_row1", ["dx", "dy", "w", "h"]),
            ("Name Row 2", "market_price_roi_name_row2", ["dx", "dy", "w", "h"]),
            ("First Cell", "market_price_roi_first_cell", ["dx", "dy", "w", "h"]),
            ("Tier", "market_price_roi_tier", ["dx", "dy", "w", "h"]),
            ("Cell Offset", "market_price_cell_offset", ["x", "y"]),
        ]
        dlg = RoiOffsetDialog(
            title="Market Price ROI Configuration",
            roi_defs=roi_defs,
            config=self._config,
            config_path=self._config_path,
            parent=self,
        )
        dlg.exec()

    def _open_player_status_roi_dialog(self):
        from ..dialogs.roi_offset_dialog import RoiOffsetDialog
        roi_defs = [
            ("Health Bar", "player_status_roi_health", ["dx", "dy", "w", "h"]),
            ("Reload Bar", "player_status_roi_reload", ["dx", "dy", "w", "h"]),
            ("Buff Bar", "player_status_roi_buff", ["dx", "dy", "w", "h"]),
            ("Buff Bar (Small)", "player_status_roi_buff_small", ["dx", "dy", "w", "h"]),
            ("Tool Name", "player_status_roi_tool_name", ["dx", "dy", "w", "h"]),
        ]
        dlg = RoiOffsetDialog(
            title="Player Status ROI Configuration",
            roi_defs=roi_defs,
            config=self._config,
            config_path=self._config_path,
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

        self._sections.append(group)
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

        # Global enable checkbox
        self._hotkeys_enabled_cb = QCheckBox("Enable overlay hotkeys")
        self._hotkeys_enabled_cb.setChecked(self._config.hotkeys_enabled)
        self._hotkeys_enabled_cb.toggled.connect(self._on_hotkeys_enabled_toggled)
        layout.addWidget(self._hotkeys_enabled_cb)

        # Per-hotkey rows
        self._hotkey_inputs: dict[str, HotkeyInput] = {}
        grid = QGridLayout()
        grid.setColumnMinimumWidth(0, 110)
        for row_idx, (label, config_key, tooltip) in enumerate(_OVERLAY_HOTKEY_DEFS):
            lbl = QLabel(f"{label}:")
            lbl.setToolTip(tooltip)
            grid.addWidget(lbl, row_idx, 0)

            hk = HotkeyInput(getattr(self._config, config_key, ""))
            hk.setToolTip(tooltip)
            hk.combo_changed.connect(self._schedule_save)
            self._hotkey_inputs[config_key] = hk
            grid.addWidget(hk, row_idx, 1)

            clear_btn = QPushButton("X")
            clear_btn.setFixedSize(28, 28)
            clear_btn.setStyleSheet("padding: 0px;")
            clear_btn.setToolTip("Clear this hotkey")
            clear_btn.clicked.connect(hk.clear_combo)
            grid.addWidget(clear_btn, row_idx, 2)

        layout.addLayout(grid)

        # Reset to defaults button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setFixedWidth(140)
        reset_btn.clicked.connect(self._reset_hotkeys_to_defaults)
        layout.addWidget(reset_btn)

        # Apply initial enabled state
        self._on_hotkeys_enabled_toggled(self._config.hotkeys_enabled)

        self._sections.append(group)
        self._layout.addWidget(group)

    def _on_hotkeys_enabled_toggled(self, enabled: bool):
        for hk in self._hotkey_inputs.values():
            hk.setEnabled(enabled)
        self._schedule_save()

    def _reset_hotkeys_to_defaults(self):
        for config_key, default in _OVERLAY_HOTKEY_DEFAULTS.items():
            if config_key in self._hotkey_inputs:
                self._hotkey_inputs[config_key].combo = default
        self._schedule_save()

    # --- Screenshots ---
    def _build_screenshot_section(self):
        group = QGroupBox("Screenshots")
        layout = QVBoxLayout(group)

        # Enable toggle
        self._screenshot_enabled_cb = QCheckBox("Enable screenshot capture")
        self._screenshot_enabled_cb.setChecked(self._config.screenshot_enabled)
        self._screenshot_enabled_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._screenshot_enabled_cb)

        # Auto on global
        self._screenshot_auto_cb = QCheckBox("Auto-capture on own global")
        self._screenshot_auto_cb.setChecked(self._config.screenshot_auto_on_global)
        self._screenshot_auto_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._screenshot_auto_cb)

        # Delay
        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("Delay after global (s):"))
        self._screenshot_delay = QDoubleSpinBox()
        self._screenshot_delay.setRange(0.5, 5.0)
        self._screenshot_delay.setSingleStep(0.5)
        self._screenshot_delay.setValue(self._config.screenshot_delay_s)
        self._screenshot_delay.valueChanged.connect(self._schedule_save)
        delay_row.addWidget(self._screenshot_delay)
        delay_row.addStretch()
        layout.addLayout(delay_row)

        # Directory
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Save directory:"))
        self._screenshot_dir = QLineEdit(self._config.screenshot_directory)
        self._screenshot_dir.setPlaceholderText("~/Pictures/Entropia Nexus Screenshots")
        self._screenshot_dir.editingFinished.connect(self._schedule_save)
        dir_row.addWidget(self._screenshot_dir)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_screenshot_dir)
        dir_row.addWidget(browse_btn)
        layout.addLayout(dir_row)

        # Daily subfolder
        self._screenshot_daily_cb = QCheckBox("Organize in daily subfolders")
        self._screenshot_daily_cb.setChecked(self._config.screenshot_daily_subfolder)
        self._screenshot_daily_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._screenshot_daily_cb)

        # Hotkey
        hotkey_row = QHBoxLayout()
        hotkey_row.addWidget(QLabel("Screenshot hotkey:"))
        self._screenshot_hotkey = HotkeyInput(self._config.hotkey_screenshot)
        self._screenshot_hotkey.combo_changed.connect(self._schedule_save)
        hotkey_row.addWidget(self._screenshot_hotkey)
        clear_btn = QPushButton("X")
        clear_btn.setFixedSize(28, 28)
        clear_btn.setStyleSheet("padding: 0px;")
        clear_btn.clicked.connect(self._screenshot_hotkey.clear_combo)
        hotkey_row.addWidget(clear_btn)
        hotkey_row.addStretch()
        layout.addLayout(hotkey_row)

        # Character name
        char_row = QHBoxLayout()
        char_row.addWidget(QLabel("Character name:"))
        self._character_name = QLineEdit(self._config.character_name)
        self._character_name.setPlaceholderText("Auto-detected when logged in")
        self._character_name.setToolTip(
            "Your Entropia Universe character name.\n"
            "Used to detect your own globals. Auto-detected from your Nexus account."
        )
        self._character_name.editingFinished.connect(self._schedule_save)
        char_row.addWidget(self._character_name)
        char_row.addStretch()
        layout.addLayout(char_row)

        # Blur regions button
        blur_btn = QPushButton("Configure Blur Regions...")
        blur_btn.setToolTip("Draw regions to blur in screenshots and video clips")
        blur_btn.clicked.connect(self._open_blur_dialog)
        blur_row = QHBoxLayout()
        blur_row.addWidget(blur_btn)
        blur_row.addStretch()
        layout.addLayout(blur_row)

        self._sections.append(group)
        self._layout.addWidget(group)

    def _browse_screenshot_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Screenshot Directory",
            self._screenshot_dir.text() or "",
        )
        if path:
            self._screenshot_dir.setText(path)
            self._schedule_save()

    def _open_blur_dialog(self):
        try:
            from ..dialogs.blur_region_dialog import BlurRegionDialog
            dialog = BlurRegionDialog(
                config=self._config,
                config_path=self._config_path,
                event_bus=self._event_bus,
                parent=self,
            )
            dialog.exec()
        except Exception as e:
            log.error("Failed to open blur dialog: %s", e)

    # --- Video ---
    def _build_video_section(self):
        group = QGroupBox("Video Clips")
        layout = QVBoxLayout(group)

        # Enable toggle
        self._clip_enabled_cb = QCheckBox("Enable video clip recording")
        self._clip_enabled_cb.setChecked(self._config.clip_enabled)
        self._clip_enabled_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._clip_enabled_cb)

        note = QLabel("Requires FFmpeg. Continuously buffers game footage for instant replay.")
        note.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        # Auto on global
        self._clip_auto_cb = QCheckBox("Auto-save clip on own global")
        self._clip_auto_cb.setChecked(self._config.clip_auto_on_global)
        self._clip_auto_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._clip_auto_cb)

        # Buffer duration
        buf_row = QHBoxLayout()
        buf_row.addWidget(QLabel("Buffer duration (s):"))
        self._clip_buffer = QSpinBox()
        self._clip_buffer.setRange(5, 60)
        self._clip_buffer.setValue(self._config.clip_buffer_seconds)
        self._clip_buffer.valueChanged.connect(self._schedule_save)
        buf_row.addWidget(self._clip_buffer)
        buf_row.addStretch()
        layout.addLayout(buf_row)

        # Post-global delay
        post_row = QHBoxLayout()
        post_row.addWidget(QLabel("Save delay after global (s):"))
        self._clip_post_global = QSpinBox()
        self._clip_post_global.setRange(0, 15)
        self._clip_post_global.setValue(self._config.clip_post_global_seconds)
        self._clip_post_global.valueChanged.connect(self._schedule_save)
        post_row.addWidget(self._clip_post_global)
        post_row.addStretch()
        layout.addLayout(post_row)

        # Directory
        cdir_row = QHBoxLayout()
        cdir_row.addWidget(QLabel("Save directory:"))
        self._clip_dir = QLineEdit(self._config.clip_directory)
        self._clip_dir.setPlaceholderText("~/Videos/Entropia Nexus Clips")
        self._clip_dir.editingFinished.connect(self._schedule_save)
        cdir_row.addWidget(self._clip_dir)
        cbrowse = QPushButton("Browse")
        cbrowse.clicked.connect(self._browse_clip_dir)
        cdir_row.addWidget(cbrowse)
        layout.addLayout(cdir_row)

        # Daily subfolder
        self._clip_daily_cb = QCheckBox("Organize in daily subfolders")
        self._clip_daily_cb.setChecked(self._config.clip_daily_subfolder)
        self._clip_daily_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._clip_daily_cb)

        # FPS / Resolution / Bitrate row
        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel("FPS:"))
        self._clip_fps = QComboBox()
        for fps in (15, 24, 30, 60):
            self._clip_fps.addItem(str(fps), fps)
        idx = self._clip_fps.findData(self._config.clip_fps)
        if idx >= 0:
            self._clip_fps.setCurrentIndex(idx)
        self._clip_fps.currentIndexChanged.connect(self._schedule_save)
        quality_row.addWidget(self._clip_fps)

        quality_row.addWidget(QLabel("Resolution:"))
        self._clip_resolution = QComboBox()
        for res in ("source", "1080p", "720p", "480p"):
            self._clip_resolution.addItem(res.capitalize() if res != "source" else "Source", res)
        idx = self._clip_resolution.findData(self._config.clip_resolution)
        if idx >= 0:
            self._clip_resolution.setCurrentIndex(idx)
        self._clip_resolution.currentIndexChanged.connect(self._schedule_save)
        quality_row.addWidget(self._clip_resolution)

        quality_row.addWidget(QLabel("Bitrate:"))
        self._clip_bitrate = QComboBox()
        for br in ("low", "medium", "high", "ultra"):
            self._clip_bitrate.addItem(br.capitalize(), br)
        idx = self._clip_bitrate.findData(self._config.clip_bitrate)
        if idx >= 0:
            self._clip_bitrate.setCurrentIndex(idx)
        self._clip_bitrate.currentIndexChanged.connect(self._schedule_save)
        quality_row.addWidget(self._clip_bitrate)
        quality_row.addStretch()
        layout.addLayout(quality_row)

        # Clip hotkey
        hotkey_row = QHBoxLayout()
        hotkey_row.addWidget(QLabel("Save clip hotkey:"))
        self._clip_hotkey = HotkeyInput(self._config.hotkey_save_clip)
        self._clip_hotkey.combo_changed.connect(self._schedule_save)
        hotkey_row.addWidget(self._clip_hotkey)
        clear_btn = QPushButton("X")
        clear_btn.setFixedSize(28, 28)
        clear_btn.setStyleSheet("padding: 0px;")
        clear_btn.clicked.connect(self._clip_hotkey.clear_combo)
        hotkey_row.addWidget(clear_btn)
        hotkey_row.addStretch()
        layout.addLayout(hotkey_row)

        # FFmpeg path
        ff_row = QHBoxLayout()
        ff_row.addWidget(QLabel("FFmpeg path:"))
        self._ffmpeg_path = QLineEdit(self._config.ffmpeg_path)
        self._ffmpeg_path.setPlaceholderText("Auto-detected from PATH")
        self._ffmpeg_path.editingFinished.connect(self._schedule_save)
        ff_row.addWidget(self._ffmpeg_path)
        ff_browse = QPushButton("Browse")
        ff_browse.clicked.connect(self._browse_ffmpeg)
        ff_row.addWidget(ff_browse)
        layout.addLayout(ff_row)

        # FFmpeg status
        self._ffmpeg_status = QLabel("")
        self._ffmpeg_status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self._ffmpeg_status)
        self._update_ffmpeg_status()

        # --- Audio sub-section ---
        audio_label = QLabel("Audio")
        audio_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(audio_label)

        self._clip_audio_cb = QCheckBox("Record system audio")
        self._clip_audio_cb.setChecked(self._config.clip_audio_enabled)
        self._clip_audio_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._clip_audio_cb)

        dev_row = QHBoxLayout()
        dev_row.addWidget(QLabel("Audio device:"))
        self._clip_audio_device = QComboBox()
        self._clip_audio_device.addItem("System Default", "")
        self._populate_audio_devices()
        self._clip_audio_device.currentIndexChanged.connect(self._schedule_save)
        dev_row.addWidget(self._clip_audio_device)
        dev_row.addStretch()
        layout.addLayout(dev_row)

        self._audio_noise_cb = QCheckBox("Noise suppression")
        self._audio_noise_cb.setChecked(self._config.clip_audio_noise_suppression)
        self._audio_noise_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._audio_noise_cb)

        self._audio_gate_cb = QCheckBox("Noise gate")
        self._audio_gate_cb.setChecked(self._config.clip_audio_noise_gate)
        self._audio_gate_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._audio_gate_cb)

        self._audio_compressor_cb = QCheckBox("Compressor")
        self._audio_compressor_cb.setChecked(self._config.clip_audio_compressor)
        self._audio_compressor_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._audio_compressor_cb)

        # --- Webcam sub-section ---
        webcam_label = QLabel("Webcam")
        webcam_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(webcam_label)

        self._clip_webcam_cb = QCheckBox("Include webcam overlay")
        self._clip_webcam_cb.setChecked(self._config.clip_webcam_enabled)
        self._clip_webcam_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._clip_webcam_cb)

        wcam_row = QHBoxLayout()
        wcam_row.addWidget(QLabel("Webcam device:"))
        self._clip_webcam_device = QSpinBox()
        self._clip_webcam_device.setRange(0, 9)
        self._clip_webcam_device.setValue(self._config.clip_webcam_device)
        self._clip_webcam_device.valueChanged.connect(self._schedule_save)
        wcam_row.addWidget(self._clip_webcam_device)

        wcam_row.addWidget(QLabel("Position:"))
        self._clip_webcam_pos = QComboBox()
        for pos in ("top_left", "top_right", "bottom_left", "bottom_right"):
            self._clip_webcam_pos.addItem(pos.replace("_", " ").title(), pos)
        idx = self._clip_webcam_pos.findData(self._config.clip_webcam_position)
        if idx >= 0:
            self._clip_webcam_pos.setCurrentIndex(idx)
        self._clip_webcam_pos.currentIndexChanged.connect(self._schedule_save)
        wcam_row.addWidget(self._clip_webcam_pos)
        wcam_row.addStretch()
        layout.addLayout(wcam_row)

        self._sections.append(group)
        self._layout.addWidget(group)

    def _browse_clip_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Clip Directory",
            self._clip_dir.text() or "",
        )
        if path:
            self._clip_dir.setText(path)
            self._schedule_save()

    def _browse_ffmpeg(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select FFmpeg Binary",
            self._ffmpeg_path.text() or "",
            "Executable (*.exe);;All Files (*)",
        )
        if path:
            self._ffmpeg_path.setText(path)
            self._schedule_save()
            self._update_ffmpeg_status()

    def _update_ffmpeg_status(self):
        try:
            from ...capture.ffmpeg import find_ffmpeg, get_version
            path = find_ffmpeg(self._ffmpeg_path.text())
            if path:
                ver = get_version(path) or "unknown version"
                self._ffmpeg_status.setText(f"Found: {ver}")
                self._ffmpeg_status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            else:
                self._ffmpeg_status.setText(
                    "FFmpeg not found. Video clips require FFmpeg — "
                    "it will be downloaded automatically when needed."
                )
                self._ffmpeg_status.setStyleSheet("color: #ff6b6b; font-size: 11px;")
        except Exception:
            self._ffmpeg_status.setText("Could not check FFmpeg status")

    def _populate_audio_devices(self):
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            current = self._config.clip_audio_device
            for i, dev in enumerate(devices):
                if dev.get("max_input_channels", 0) > 0 or dev.get("hostapi") == 0:
                    name = dev.get("name", f"Device {i}")
                    self._clip_audio_device.addItem(name, name)
            # Select current
            idx = self._clip_audio_device.findData(current)
            if idx >= 0:
                self._clip_audio_device.setCurrentIndex(idx)
        except Exception:
            pass  # sounddevice not installed or no devices

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

        self._sections.append(group)
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

        self._sections.append(group)
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
        self._sections.append(self._advanced_group)
        self._layout.addWidget(self._advanced_group)

        # Toggle button to show/hide
        self._advanced_toggle = QPushButton("Show Advanced Settings")
        self._advanced_toggle.setFlat(True)
        self._advanced_toggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._advanced_toggle.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; text-decoration: underline;"
            f" border: none; padding: 2px;"
        )

        def _toggle():
            visible = not self._advanced_group.isVisible()
            self._advanced_group.setVisible(visible)
            self._advanced_toggle.setText(
                "Hide Advanced Settings" if visible else "Show Advanced Settings"
            )

        self._advanced_toggle.clicked.connect(_toggle)
        self._layout.addWidget(self._advanced_toggle, alignment=Qt.AlignmentFlag.AlignLeft)

    def _browse_js_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select JS utils directory")
        if path:
            self._js_path.setText(path)
            self._schedule_save()

    def set_search(self, query: str):
        """Set the search bar text programmatically (triggers filtering)."""
        self._search_input.setText(query)

    def _apply_search_filter(self):
        """Show/hide sections based on search query; highlight matches."""
        query = self._search_input.text().strip().lower()
        if not query:
            # Restore default state: advanced hidden, toggle visible
            for section in self._sections:
                if section is self._advanced_group:
                    section.hide()
                else:
                    section.show()
                self._clear_highlights(section)
            self._advanced_toggle.show()
            return
        self._advanced_toggle.hide()
        for section in self._sections:
            texts = self._section_texts.get(section, [])
            match = any(query in t.lower() for t in texts)
            section.setVisible(match)
            self._clear_highlights(section)
            if match:
                self._highlight_section(section, query)

    def _highlight_section(self, section, query: str):
        """Highlight matching text in section labels."""
        from re import escape as re_escape, sub as re_sub, IGNORECASE
        pattern = re_escape(query)
        highlight = (
            f'<span style="background: {ACCENT}30; font-weight: bold;">'
            r'\g<0></span>'
        )
        for label in section.findChildren(QLabel):
            orig = label.property("_orig_text")
            if orig is None:
                orig = label.text()
                label.setProperty("_orig_text", orig)
            if query in orig.lower():
                label.setText(re_sub(pattern, highlight, orig, flags=IGNORECASE))
                label.setTextFormat(Qt.TextFormat.RichText)

    def _clear_highlights(self, section):
        """Restore original text on all labels in a section."""
        for label in section.findChildren(QLabel):
            orig = label.property("_orig_text")
            if orig is not None:
                label.setText(orig)
                label.setTextFormat(Qt.TextFormat.PlainText)
                label.setProperty("_orig_text", None)

    def _schedule_save(self, *_args):
        """Schedule a debounced save (restarts the 300ms timer on each call)."""
        self._save_timer.start()

    def _do_save(self):
        """Apply all settings from the UI to config and persist."""
        self._config.chat_log_path = self._chat_path.text()
        self._config.poll_interval_ms = self._poll_interval.value()
        self._config.overlay_opacity = self._opacity_slider.value() / 100.0
        self._config.auto_pin_detail_overlay = self._auto_pin_cb.isChecked()
        self._config.overlay_enabled = self._skill_scanner_cb.isChecked()
        self._config.ocr_capture_backend = (
            self._ocr_capture_backend.currentData() or "auto"
        )
        self._config.ocr_trace_enabled = self._ocr_trace_cb.isChecked()
        self._config.check_for_updates = self._updates_cb.isChecked()
        self._config.js_utils_path = self._js_path.text()
        self._config.oauth_client_id = self._oauth_client_id.text()

        # Dashboard — Globals
        self._config.dashboard_globals_min_value = self._dash_globals_min.value()
        self._config.dashboard_globals_blocked_types = [
            k for k, cb in self._dash_globals_type_cbs.items() if cb.isChecked()
        ]

        # Dashboard — Trade
        bl_text = self._dash_trade_blocklist.toPlainText().strip()
        self._config.dashboard_trade_blocklist = [
            n.strip() for n in bl_text.splitlines() if n.strip()
        ]
        self._config.dashboard_trade_planet_filter = [
            p for p, cb in self._dash_trade_planet_cbs.items() if cb.isChecked()
        ]
        bk_text = self._dash_trade_blacklist.toPlainText().strip()
        self._config.dashboard_trade_blacklist = [
            n.strip() for n in bk_text.splitlines() if n.strip()
        ]

        # Target Lock
        self._config.target_lock_enabled = self._target_lock_cb.isChecked()
        self._config.target_lock_match_threshold = self._target_lock_threshold.value()

        # Player Status Detection
        self._config.player_status_enabled = self._player_status_cb.isChecked()
        self._config.player_status_match_threshold = self._player_status_threshold.value()

        # Market Price Detection
        self._config.market_price_enabled = self._market_price_cb.isChecked()
        self._config.market_price_review_enabled = self._market_price_review_cb.isChecked()
        self._config.market_price_match_threshold = self._market_price_threshold.value()
        self._config.market_price_text_threshold = self._market_price_text_threshold.value()

        # Overlay Hotkeys
        self._config.hotkeys_enabled = self._hotkeys_enabled_cb.isChecked()
        for config_key, hk in self._hotkey_inputs.items():
            setattr(self._config, config_key, hk.combo)

        # Screenshots
        self._config.screenshot_enabled = self._screenshot_enabled_cb.isChecked()
        self._config.screenshot_auto_on_global = self._screenshot_auto_cb.isChecked()
        self._config.screenshot_delay_s = self._screenshot_delay.value()
        self._config.screenshot_directory = self._screenshot_dir.text()
        self._config.screenshot_daily_subfolder = self._screenshot_daily_cb.isChecked()
        self._config.hotkey_screenshot = self._screenshot_hotkey.combo
        self._config.character_name = self._character_name.text()

        # Video Clips
        self._config.clip_enabled = self._clip_enabled_cb.isChecked()
        self._config.clip_auto_on_global = self._clip_auto_cb.isChecked()
        self._config.clip_buffer_seconds = self._clip_buffer.value()
        self._config.clip_post_global_seconds = self._clip_post_global.value()
        self._config.clip_directory = self._clip_dir.text()
        self._config.clip_daily_subfolder = self._clip_daily_cb.isChecked()
        self._config.clip_fps = self._clip_fps.currentData() or 30
        self._config.clip_resolution = self._clip_resolution.currentData() or "source"
        self._config.clip_bitrate = self._clip_bitrate.currentData() or "medium"
        self._config.hotkey_save_clip = self._clip_hotkey.combo
        self._config.ffmpeg_path = self._ffmpeg_path.text()

        # Audio
        self._config.clip_audio_enabled = self._clip_audio_cb.isChecked()
        self._config.clip_audio_device = self._clip_audio_device.currentData() or ""
        self._config.clip_audio_noise_suppression = self._audio_noise_cb.isChecked()
        self._config.clip_audio_noise_gate = self._audio_gate_cb.isChecked()
        self._config.clip_audio_compressor = self._audio_compressor_cb.isChecked()

        # Webcam
        self._config.clip_webcam_enabled = self._clip_webcam_cb.isChecked()
        self._config.clip_webcam_device = self._clip_webcam_device.value()
        self._config.clip_webcam_position = self._clip_webcam_pos.currentData() or "bottom_right"

        save_config(self._config, self._config_path)
        self._event_bus.publish(EVENT_CONFIG_CHANGED, self._config)
