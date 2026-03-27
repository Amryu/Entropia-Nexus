"""Settings page — all app configuration in organized sections."""

import sys
import threading
import time

import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSlider, QSpinBox, QDoubleSpinBox, QGroupBox, QFileDialog, QScrollArea,
    QFrame, QCheckBox, QTextEdit, QGridLayout, QComboBox, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, QObject, QEvent
from PyQt6.QtGui import QCursor, QPainter, QColor, QLinearGradient

from ...core.config import save_config
from ...core.build_flags import is_dev_build
from ...core.constants import EVENT_CONFIG_CHANGED, EVENT_REPARSE_REQUESTED
from ...core.logger import get_logger
from ..theme import TEXT_MUTED, BORDER, ACCENT
from ..widgets.hotkey_input import HotkeyInput

log = get_logger("Settings")

# Max widths for input widgets to prevent full-width stretching
_INPUT_MAX_W = 250       # QComboBox, QSpinBox, QDoubleSpinBox, HotkeyInput, QLineEdit (short)
_SLIDER_MAX_W = 300      # QSlider (gain, opacity, etc.)
_PATH_MAX_W = 400        # QLineEdit for file/directory paths

def _build_overlay_hotkey_defs() -> list[tuple[str, str, str]]:
    defs = [
        ("Toggle Overlay", "hotkey_overlay_toggle", "Show/hide all overlays"),
        ("Search", "hotkey_search", "Open the search overlay"),
        ("Map", "hotkey_map", "Open the map overlay"),
        ("Exchange", "hotkey_exchange", "Open the exchange overlay"),
        ("Notifications", "hotkey_notifications", "Open the notifications overlay"),
        ("Debug Overlay", "hotkey_debug", "Toggle OCR/target lock debug overlay"),
        ("Screenshot", "hotkey_screenshot", "Take a screenshot"),
        ("Save Clip", "hotkey_save_clip", "Save a video clip from the buffer"),
        ("Toggle Recording", "hotkey_toggle_recording", "Start/stop continuous recording"),
    ]
    if is_dev_build():
        defs.insert(
            6,
            ("Radar Recalibrate", "hotkey_radar_recalibrate", "Force radar circle re-detection"),
        )
    return defs


def _build_overlay_hotkey_defaults() -> dict[str, str]:
    defaults = {
        "hotkey_overlay_toggle": "f2",
        "hotkey_search": "ctrl+f",
        "hotkey_map": "ctrl+m",
        "hotkey_exchange": "ctrl+e",
        "hotkey_notifications": "ctrl+n",
        "hotkey_debug": "f3",
        "hotkey_screenshot": "f12",
        "hotkey_save_clip": "ctrl+shift+space",
        "hotkey_toggle_recording": "ctrl+shift+r",
    }
    if is_dev_build():
        defaults["hotkey_radar_recalibrate"] = "home"
    return defaults


# Overlay hotkey definitions: (display label, config_key, tooltip)
_OVERLAY_HOTKEY_DEFS = _build_overlay_hotkey_defs()
_OVERLAY_HOTKEY_DEFAULTS = _build_overlay_hotkey_defaults()


class _ScrollBlocker(QObject):
    """Block wheel events on unfocused widgets to prevent accidental changes while scrolling."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and not obj.hasFocus():
            return True
        return False


# Audio level meter constants
_METER_HEIGHT = 10
_METER_UPDATE_MS = 50  # ~20 fps
_METER_SNAPSHOT_S = 0.05  # 50ms window for peak calculation

# Colours: green → yellow → red
_METER_GREEN = QColor(76, 175, 80)
_METER_YELLOW = QColor(255, 193, 7)
_METER_RED = QColor(244, 67, 54)
_METER_BG = QColor(40, 40, 50)


class _LevelBar(QWidget):
    """Horizontal audio level bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = 0.0  # 0.0 – 1.0
        self._peak = 0.0
        self._peak_decay = 0.0
        self.setFixedHeight(_METER_HEIGHT)
        self.setFixedWidth(_SLIDER_MAX_W)

    def set_level(self, level: float) -> None:
        """Set the current level (0.0 – 1.0) and repaint."""
        self._level = max(0.0, min(1.0, level))
        if self._level >= self._peak:
            self._peak = self._level
            self._peak_decay = 0.0
        else:
            self._peak_decay += _METER_UPDATE_MS / 1000.0
            if self._peak_decay > 0.5:
                self._peak = max(self._level, self._peak - 0.02)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_METER_BG)
        p.drawRoundedRect(0, 0, w, h, 3, 3)

        fill_w = int(w * self._level)
        if fill_w > 0:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, _METER_GREEN)
            grad.setColorAt(0.6, _METER_YELLOW)
            grad.setColorAt(1.0, _METER_RED)
            p.setBrush(grad)
            p.drawRoundedRect(0, 0, fill_w, h, 3, 3)

        # Peak hold indicator (white line)
        peak_x = int(w * self._peak)
        if peak_x > 2:
            p.setPen(QColor(255, 255, 255, 200))
            p.drawLine(peak_x, 1, peak_x, h - 1)

        p.end()


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
        self._audio_check = None  # AudioCheck instance (set in _build_video_section)

        # Audio level meters (created in _build_video_section)
        self._game_level_bar = None
        self._mic_level_bar = None
        self._game_meter_buf = None          # AudioBuffer (loopback)
        self._mic_filtered_meter = None      # _FilteredMicMeter
        self._meter_timer = None

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

        self._build_startup_section()
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

        # Prevent scroll wheel from accidentally changing values on sliders,
        # spinboxes, and comboboxes while scrolling the page.
        self._scroll_blocker = _ScrollBlocker(self)
        for w in content.findChildren(
            (QSlider, QSpinBox, QDoubleSpinBox, QComboBox)
        ):
            w.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            w.installEventFilter(self._scroll_blocker)

        scroll.setWidget(content)

        # Connect change signals for realtime auto-save
        self._start_on_boot_cb.stateChanged.connect(self._schedule_save)
        self._start_minimized_cb.stateChanged.connect(self._schedule_save)
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
                tip = child.toolTip()
                if tip:
                    texts.append(tip)
            for child in section.findChildren(QPushButton):
                t = child.text()
                if t:
                    texts.append(t)
                tip = child.toolTip()
                if tip:
                    texts.append(tip)
            self._section_texts[section] = texts

        # Connect auth state changes and apply current state
        signals.auth_state_changed.connect(self._on_auth_changed)
        self._on_auth_changed(oauth.auth_state)

    # --- Startup ---
    def _build_startup_section(self):
        group = QGroupBox("Startup")
        layout = QVBoxLayout(group)

        self._start_on_boot_cb = QCheckBox("Start on PC startup")
        self._start_on_boot_cb.setToolTip(
            "Automatically launch Entropia Nexus when you log in to your computer"
        )
        self._start_on_boot_cb.setChecked(self._config.start_on_boot)
        layout.addWidget(self._start_on_boot_cb)

        self._start_minimized_cb = QCheckBox("Start minimized")
        self._start_minimized_cb.setToolTip(
            "Start the application minimized to the system tray"
        )
        self._start_minimized_cb.setChecked(self._config.start_minimized)
        layout.addWidget(self._start_minimized_cb)

        self._sections.append(group)
        self._layout.addWidget(group)

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

        # Grid for label+input pairs
        grid = QGridLayout()
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 1)
        grid.setHorizontalSpacing(8)
        row = 0

        # Chat log path
        grid.addWidget(QLabel("Chat log path:"), row, 0)
        path_w = QWidget()
        path_h = QHBoxLayout(path_w)
        path_h.setContentsMargins(0, 0, 0, 0)
        self._chat_path = QLineEdit(self._config.chat_log_path)
        self._chat_path.setFixedWidth(_PATH_MAX_W)
        path_h.addWidget(self._chat_path)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_chat_path)
        path_h.addWidget(browse_btn)
        grid.addWidget(path_w, row, 1, 1, 2)
        row += 1

        # Poll interval
        grid.addWidget(QLabel("Poll interval (ms):"), row, 0)
        self._poll_interval = QSpinBox()
        self._poll_interval.setFixedWidth(_INPUT_MAX_W)
        self._poll_interval.setRange(100, 2000)
        self._poll_interval.setValue(self._config.poll_interval_ms)
        grid.addWidget(self._poll_interval, row, 1)

        layout.addLayout(grid)

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
        dash_grid = QGridLayout()
        dash_grid.setColumnStretch(0, 0)
        dash_grid.setColumnStretch(1, 0)
        dash_grid.setColumnStretch(2, 1)
        dash_grid.setHorizontalSpacing(8)

        dash_grid.addWidget(QLabel("Minimum value to display:"), 0, 0)
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
        dash_grid.addWidget(self._dash_globals_min, 0, 1)
        layout.addLayout(dash_grid)

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

        gen_grid = QGridLayout()
        gen_grid.setColumnStretch(0, 0)
        gen_grid.setColumnStretch(1, 0)
        gen_grid.setColumnStretch(2, 1)
        gen_grid.setHorizontalSpacing(8)

        gen_grid.addWidget(QLabel("Window capture backend:"), 0, 0)
        self._ocr_capture_backend = QComboBox()
        self._ocr_capture_backend.setFixedWidth(_INPUT_MAX_W)
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
        self._ocr_capture_backend.currentIndexChanged.connect(
            self._on_capture_backend_changed,
        )
        gen_grid.addWidget(self._ocr_capture_backend, 0, 1)
        layout.addLayout(gen_grid)

        self._hdr_cb = QCheckBox("HDR Compatibility Mode")
        self._hdr_cb.setToolTip(
            "Applies tone correction (CLAHE) to captured frames to restore\n"
            "contrast lost during HDR → SDR conversion.\n\n"
            "Enable if your display uses HDR and OCR or screenshots\n"
            "appear washed out."
        )
        self._hdr_cb.setChecked(getattr(self._config, "hdr_compatibility_mode", False))
        self._hdr_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._hdr_cb)

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

        tl_grid = QGridLayout()
        tl_grid.setColumnStretch(0, 0)
        tl_grid.setColumnStretch(1, 0)
        tl_grid.setColumnStretch(2, 1)
        tl_grid.setHorizontalSpacing(8)

        tl_grid.addWidget(QLabel("Match threshold:"), 0, 0)
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
        tl_grid.addWidget(self._target_lock_threshold, 0, 1)
        layout.addLayout(tl_grid)

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

        ps_grid = QGridLayout()
        ps_grid.setColumnStretch(0, 0)
        ps_grid.setColumnStretch(1, 0)
        ps_grid.setColumnStretch(2, 1)
        ps_grid.setHorizontalSpacing(8)

        ps_grid.addWidget(QLabel("Match threshold:"), 0, 0)
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
        ps_grid.addWidget(self._player_status_threshold, 0, 1)
        layout.addLayout(ps_grid)

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

        mp_grid = QGridLayout()
        mp_grid.setColumnStretch(0, 0)
        mp_grid.setColumnStretch(1, 0)
        mp_grid.setColumnStretch(2, 1)
        mp_grid.setHorizontalSpacing(8)
        mp_row = 0

        mp_grid.addWidget(QLabel("Match threshold:"), mp_row, 0)
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
        mp_grid.addWidget(self._market_price_threshold, mp_row, 1)
        mp_row += 1

        mp_grid.addWidget(QLabel("Text brightness threshold:"), mp_row, 0)
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
        mp_grid.addWidget(self._market_price_text_threshold, mp_row, 1)
        layout.addLayout(mp_grid)

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
        ov_grid = QGridLayout()
        ov_grid.setColumnStretch(0, 0)
        ov_grid.setColumnStretch(1, 0)
        ov_grid.setColumnStretch(2, 1)
        ov_grid.setHorizontalSpacing(8)

        ov_grid.addWidget(QLabel("Opacity:"), 0, 0)
        slider_w = QWidget()
        slider_h = QHBoxLayout(slider_w)
        slider_h.setContentsMargins(0, 0, 0, 0)
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setFixedWidth(_SLIDER_MAX_W)
        self._opacity_slider.setRange(20, 100)
        self._opacity_slider.setValue(int(self._config.overlay_opacity * 100))
        slider_h.addWidget(self._opacity_slider)
        self._opacity_label = QLabel(f"{self._config.overlay_opacity:.0%}")
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
        slider_h.addWidget(self._opacity_label)
        ov_grid.addWidget(slider_w, 0, 1)
        layout.addLayout(ov_grid)

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
        group = QGroupBox("Hotkeys")
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
            hk.setMaximumWidth(_INPUT_MAX_W)
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

        # Auto on global + conditions button
        auto_row = QHBoxLayout()
        self._screenshot_auto_cb = QCheckBox("Auto-capture on own global")
        self._screenshot_auto_cb.setChecked(self._config.screenshot_auto_on_global)
        self._screenshot_auto_cb.stateChanged.connect(self._schedule_save)
        auto_row.addWidget(self._screenshot_auto_cb)
        ss_conditions_btn = QPushButton("Conditions...")
        ss_conditions_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        ss_conditions_btn.setToolTip("Configure which globals trigger auto-capture")
        ss_conditions_btn.clicked.connect(lambda: self._open_capture_conditions(0))
        auto_row.addWidget(ss_conditions_btn)
        auto_row.addStretch()
        layout.addLayout(auto_row)

        # Sound feedback
        self._screenshot_sound_cb = QCheckBox("Play sound on capture")
        self._screenshot_sound_cb.setChecked(self._config.screenshot_sound_enabled)
        self._screenshot_sound_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._screenshot_sound_cb)

        # Daily subfolder
        self._screenshot_daily_cb = QCheckBox("Organize in daily subfolders")
        self._screenshot_daily_cb.setChecked(self._config.screenshot_daily_subfolder)
        self._screenshot_daily_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._screenshot_daily_cb)

        # Grid for label+input pairs
        grid = QGridLayout()
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 1)  # absorbs remaining space
        grid.setHorizontalSpacing(8)
        row = 0

        # Screenshot size
        grid.addWidget(QLabel("Screenshot size:"), row, 0)
        self._screenshot_size = QComboBox()
        self._screenshot_size.setFixedWidth(_INPUT_MAX_W)
        for pct in (100, 75, 50, 25):
            self._screenshot_size.addItem(f"{pct}%", pct)
        cur_pct = self._config.screenshot_size_pct
        idx = self._screenshot_size.findData(cur_pct)
        self._screenshot_size.setCurrentIndex(idx if idx >= 0 else 0)
        self._screenshot_size.currentIndexChanged.connect(self._schedule_save)
        grid.addWidget(self._screenshot_size, row, 1)
        row += 1

        # Delay
        grid.addWidget(QLabel("Delay after global (s):"), row, 0)
        self._screenshot_delay = QDoubleSpinBox()
        self._screenshot_delay.setFixedWidth(_INPUT_MAX_W)
        self._screenshot_delay.setDecimals(4)
        self._screenshot_delay.setRange(0.0, 5.0)
        self._screenshot_delay.setSingleStep(0.1)
        self._screenshot_delay.setValue(self._config.screenshot_delay_s)
        self._screenshot_delay.valueChanged.connect(self._schedule_save)
        grid.addWidget(self._screenshot_delay, row, 1)
        row += 1

        # Directory
        grid.addWidget(QLabel("Save directory:"), row, 0)
        dir_w = QWidget()
        dir_h = QHBoxLayout(dir_w)
        dir_h.setContentsMargins(0, 0, 0, 0)
        self._screenshot_dir = QLineEdit(self._config.screenshot_directory)
        self._screenshot_dir.setFixedWidth(_PATH_MAX_W)
        self._screenshot_dir.setPlaceholderText("~/Pictures/Entropia Nexus Screenshots")
        self._screenshot_dir.editingFinished.connect(self._schedule_save)
        dir_h.addWidget(self._screenshot_dir)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_screenshot_dir)
        dir_h.addWidget(browse_btn)
        grid.addWidget(dir_w, row, 1, 1, 2)
        row += 1

        # Character name
        grid.addWidget(QLabel("Character name:"), row, 0)
        self._character_name = QLineEdit(self._config.character_name)
        self._character_name.setFixedWidth(_INPUT_MAX_W)
        self._character_name.setPlaceholderText("Auto-detected when logged in")
        self._character_name.setToolTip(
            "Your Entropia Universe character name.\n"
            "Used to detect your own globals. Auto-detected from your Nexus account."
        )
        self._character_name.editingFinished.connect(self._schedule_save)
        grid.addWidget(self._character_name, row, 1)

        layout.addLayout(grid)

        # Blur region config dialog
        blur_btn = QPushButton("Configure Blur Regions...")
        blur_btn.setToolTip(
            "Draw rectangles on a live game preview to define areas\n"
            "that will be blurred in both screenshots and video clips."
        )
        blur_btn.clicked.connect(self._open_blur_region_dialog)
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

    def _find_frame_distributor(self):
        """Find the frame distributor from the main window."""
        try:
            app = __import__("PyQt6").QtWidgets.QApplication.instance()
            for widget in app.topLevelWidgets():
                fd = getattr(widget, "_frame_distributor", None)
                if fd is not None:
                    return fd
        except Exception:
            pass
        return None

    def _open_capture_conditions(self, tab_index: int = 0):
        try:
            from ..dialogs.capture_conditions_dialog import CaptureConditionsDialog
            dialog = CaptureConditionsDialog(
                config=self._config,
                config_path=self._config_path,
                event_bus=self._event_bus,
                initial_tab=tab_index,
                parent=self,
            )
            dialog.exec()
        except Exception as e:
            log.error("Failed to open capture conditions dialog: %s", e)

    def _open_blur_region_dialog(self):
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
            log.error("Failed to open blur region dialog: %s", e)

    def _open_video_config_dialog(self):
        # Raise existing dialog if already open
        if (hasattr(self, "_video_config_dialog")
                and self._video_config_dialog is not None):
            self._video_config_dialog.raise_()
            self._video_config_dialog.activateWindow()
            return
        try:
            from ..dialogs.video_config_dialog import VideoConfigDialog
            fd = self._find_frame_distributor()
            dialog = VideoConfigDialog(
                config=self._config,
                config_path=self._config_path,
                event_bus=self._event_bus,
                frame_distributor=fd,
                parent=self,
            )
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.destroyed.connect(self._on_video_config_dialog_closed)
            self._video_config_dialog = dialog
            dialog.show()
        except Exception as e:
            log.error("Failed to open video config dialog: %s", e)

    def _on_video_config_dialog_closed(self):
        self._video_config_dialog = None

    def _on_capture_enabled_changed(self, state):
        if state == Qt.CheckState.Checked.value:
            from ..dialogs.media_download_dialog import ensure_media_libraries
            if not ensure_media_libraries(
                self._config, self._event_bus, self._signals, parent=self,
            ):
                # User cancelled — revert the checkbox without re-triggering
                self._capture_enabled_cb.blockSignals(True)
                self._capture_enabled_cb.setChecked(False)
                self._capture_enabled_cb.blockSignals(False)
                return
            # FFmpeg may have just been downloaded — refresh status label
            self._update_ffmpeg_status()
        self._update_capture_ui_state()
        self._schedule_save()

    def _on_clip_enabled_changed(self, state):
        self._update_capture_ui_state()
        self._schedule_save()

    def _on_obs_enabled_changed(self, state):
        if state == Qt.CheckState.Checked.value:
            self._maybe_ask_replay_buffer_management()
        self._update_obs_ui_state()
        self._schedule_save()

    def _maybe_ask_replay_buffer_management(self):
        """Ask the user once whether to auto-manage the OBS Replay Buffer."""
        if self._config.obs_replay_buffer_asked:
            return

        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Replay Buffer Management",
            "Should this client automatically start and stop the OBS\n"
            "Replay Buffer when Entropia Universe opens and closes?\n\n"
            "You can change this later in the OBS settings.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        manage = reply == QMessageBox.StandardButton.Yes
        self._obs_manage_replay_cb.setChecked(manage)

    def _update_obs_ui_state(self):
        """Alias kept for any external callers; delegates to _update_capture_ui_state."""
        self._update_capture_ui_state()

    def _update_capture_ui_state(self):
        """Enable/disable widgets based on capture_enabled (master), clip_enabled, and OBS mode."""
        capture_on = self._capture_enabled_cb.isChecked()
        clip_on = self._clip_enabled_cb.isChecked()
        obs_on = self._obs_enabled_cb.isChecked()
        any_capture = capture_on or obs_on
        # Clip enable checkbox requires some capture backend
        self._clip_enabled_cb.setEnabled(any_capture)
        # OBS section requires capture to be enabled
        for w in getattr(self, "_obs_widgets", []):
            w.setEnabled(capture_on)
        # Internal capture widgets disabled when OBS is active or capture is off
        for w in getattr(self, "_internal_capture_widgets", []):
            w.setEnabled(capture_on and not obs_on)
        # Clip-specific widgets enabled when clip is on AND some capture backend is active
        for w in getattr(self, "_clip_only_widgets", []):
            w.setEnabled(any_capture and clip_on)

    @staticmethod
    def _load_obs_password() -> str:
        try:
            import keyring
            return keyring.get_password("EntropiaNexusClient", "obs_password") or ""
        except Exception:
            return ""

    def _on_obs_password_changed(self):
        """Save the OBS password to the system keyring."""
        from ...capture.obs_client import save_obs_password
        save_obs_password(self._obs_password.text())

    def _test_obs_connection(self):
        """Test OBS WebSocket connection with current settings."""
        self._obs_status_label.setText("Connecting...")
        self._obs_status_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")

        host = self._obs_host.text() or "localhost"
        port = self._obs_port.value()
        password = self._obs_password.text()

        def _test():
            try:
                import obsws_python as obsws
            except ImportError:
                self._obs_status_label.setText(
                    "obsws-python not installed. Install with: pip install obsws-python"
                )
                return

            try:
                cl = obsws.ReqClient(
                    host=host, port=port, password=password, timeout=5,
                )
                version = cl.get_version()
                obs_ver = getattr(version, "obs_version", "?")
                ws_ver = getattr(version, "obs_web_socket_version", "?")
                cl.disconnect()
                self._obs_status_label.setText(
                    f"Connected! OBS {obs_ver}, WebSocket {ws_ver}"
                )
                self._obs_status_label.setStyleSheet(
                    "color: #4caf50; font-size: 11px;"
                )
            except Exception as exc:
                self._obs_status_label.setText(f"Connection failed: {exc}")
                self._obs_status_label.setStyleSheet(
                    "color: #ff6b6b; font-size: 11px;"
                )

        threading.Thread(target=_test, daemon=True, name="obs-test").start()

    def _on_obs_connected(self, data):
        host = data.get("host", "?")
        port = data.get("port", "?")
        self._obs_status_label.setText(f"Connected to {host}:{port}")
        self._obs_status_label.setStyleSheet("color: #4caf50; font-size: 11px;")

    def _on_obs_disconnected(self, data):
        reason = data.get("reason", "unknown")
        self._obs_status_label.setText(f"Disconnected: {reason}")
        self._obs_status_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")

    # --- Video ---
    def _build_video_section(self):
        group = QGroupBox("Video")
        layout = QVBoxLayout(group)

        # Capture enable toggle (master gate for all capture infrastructure)
        self._capture_enabled_cb = QCheckBox("Enable Video Capture")
        self._capture_enabled_cb.setChecked(
            getattr(self._config, "capture_enabled", False))
        self._capture_enabled_cb.stateChanged.connect(self._on_capture_enabled_changed)
        layout.addWidget(self._capture_enabled_cb)

        self._capture_note = QLabel(
            "Requires FFmpeg. Enables internal recording, OBS integration, "
            "audio capture, and webcam overlay."
        )
        self._capture_note.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._capture_note.setWordWrap(True)
        layout.addWidget(self._capture_note)

        # Clip enable toggle (sub-gate for clipping only)
        self._clip_enabled_cb = QCheckBox("Enable Clipping (Replay Buffering)")
        self._clip_enabled_cb.setChecked(self._config.clip_enabled)
        self._clip_enabled_cb.setToolTip(
            "Enables the clip button, clip hotkey, auto-clip on global, "
            "and OBS replay buffer management.\n"
            "Requires Video Capture to be enabled for internal clipping."
        )
        self._clip_enabled_cb.stateChanged.connect(self._on_clip_enabled_changed)
        layout.addWidget(self._clip_enabled_cb)

        self._clip_note = QLabel(
            "Continuously buffers game footage so clips can be saved on demand or on global."
        )
        self._clip_note.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._clip_note.setWordWrap(True)
        layout.addWidget(self._clip_note)

        # --- OBS Studio integration ---
        obs_sep = QLabel("OBS Studio")
        obs_sep.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(obs_sep)

        self._obs_enabled_cb = QCheckBox("Use OBS Studio for video capture")
        self._obs_enabled_cb.setChecked(self._config.obs_enabled)
        self._obs_enabled_cb.setToolTip(
            "Delegate video recording and replay buffer to OBS Studio.\n"
            "OBS must be running with obs-websocket enabled (built-in since OBS 28).\n"
            "Screenshots will still be handled by Entropia Nexus."
        )
        self._obs_enabled_cb.stateChanged.connect(self._on_obs_enabled_changed)
        layout.addWidget(self._obs_enabled_cb)

        obs_note = QLabel(
            "Requires OBS 28+ with Replay Buffer enabled. "
            "Replaces internal video capture, audio, and webcam."
        )
        obs_note.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        obs_note.setWordWrap(True)
        layout.addWidget(obs_note)

        obs_grid = QGridLayout()
        obs_grid.setColumnStretch(0, 0)
        obs_grid.setColumnStretch(1, 0)
        obs_grid.setColumnStretch(2, 1)
        obs_grid.setHorizontalSpacing(8)

        obs_grid.addWidget(QLabel("Host:"), 0, 0)
        self._obs_host = QLineEdit(self._config.obs_host)
        self._obs_host.setFixedWidth(_INPUT_MAX_W)
        self._obs_host.setPlaceholderText("localhost")
        self._obs_host.editingFinished.connect(self._schedule_save)
        obs_grid.addWidget(self._obs_host, 0, 1)

        obs_grid.addWidget(QLabel("Port:"), 1, 0)
        self._obs_port = QSpinBox()
        self._obs_port.setFixedWidth(_INPUT_MAX_W)
        self._obs_port.setRange(1, 65535)
        self._obs_port.setValue(self._config.obs_port)
        self._obs_port.valueChanged.connect(self._schedule_save)
        obs_grid.addWidget(self._obs_port, 1, 1)

        obs_grid.addWidget(QLabel("Password:"), 2, 0)
        self._obs_password = QLineEdit(self._load_obs_password())
        self._obs_password.setFixedWidth(_INPUT_MAX_W)
        self._obs_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._obs_password.setPlaceholderText("(from OBS WebSocket settings)")
        self._obs_password.editingFinished.connect(self._on_obs_password_changed)
        obs_grid.addWidget(self._obs_password, 2, 1)

        layout.addLayout(obs_grid)

        # OBS status + test button
        obs_status_row = QHBoxLayout()
        self._obs_status_label = QLabel("")
        self._obs_status_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        obs_status_row.addWidget(self._obs_status_label)
        obs_status_row.addStretch()
        self._obs_test_btn = QPushButton("Test Connection")
        self._obs_test_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self._obs_test_btn.clicked.connect(self._test_obs_connection)
        obs_status_row.addWidget(self._obs_test_btn)
        layout.addLayout(obs_status_row)

        # Manage replay buffer checkbox
        self._obs_manage_replay_cb = QCheckBox(
            "Auto start/stop Replay Buffer with game")
        self._obs_manage_replay_cb.setChecked(
            self._config.obs_manage_replay_buffer)
        self._obs_manage_replay_cb.setToolTip(
            "Start the OBS Replay Buffer when Entropia Universe opens,\n"
            "stop it when the game or this client exits.")
        self._obs_manage_replay_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._obs_manage_replay_cb)

        # OBS widgets — disabled when capture is off
        self._obs_widgets = [
            self._obs_enabled_cb, self._obs_host, self._obs_port,
            self._obs_password, self._obs_test_btn,
            self._obs_manage_replay_cb,
        ]

        # Track OBS connection events for live status
        self._signals.obs_connected.connect(self._on_obs_connected)
        self._signals.obs_disconnected.connect(self._on_obs_disconnected)

        # Internal-only widgets (populated below) — disabled when OBS is on or capture is off
        self._internal_capture_widgets = []
        # Clip-only widgets — disabled when clip_enabled is off
        self._clip_only_widgets = []

        # Auto on global + conditions button (clip-specific)
        clip_auto_row = QHBoxLayout()
        self._clip_auto_cb = QCheckBox("Auto-save clip on own global")
        self._clip_auto_cb.setChecked(self._config.clip_auto_on_global)
        self._clip_auto_cb.stateChanged.connect(self._schedule_save)
        clip_auto_row.addWidget(self._clip_auto_cb)
        clip_conditions_btn = QPushButton("Conditions...")
        clip_conditions_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        clip_conditions_btn.setToolTip("Configure which globals trigger auto-capture")
        clip_conditions_btn.clicked.connect(lambda: self._open_capture_conditions(1))
        clip_auto_row.addWidget(clip_conditions_btn)
        clip_auto_row.addStretch()
        layout.addLayout(clip_auto_row)
        self._clip_only_widgets += [self._clip_auto_cb, clip_conditions_btn]

        # Sound feedback (clip-specific)
        self._clip_sound_cb = QCheckBox("Play sound on clip save")
        self._clip_sound_cb.setChecked(self._config.clip_sound_enabled)
        self._clip_sound_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._clip_sound_cb)
        self._clip_only_widgets.append(self._clip_sound_cb)

        # Daily subfolder
        self._clip_daily_cb = QCheckBox("Organize in daily subfolders")
        self._clip_daily_cb.setChecked(self._config.clip_daily_subfolder)
        self._clip_daily_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._clip_daily_cb)

        # Grid for label+input pairs
        grid = QGridLayout()
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 1)  # absorbs remaining space
        grid.setHorizontalSpacing(8)
        row = 0

        # Buffer duration
        grid.addWidget(QLabel("Buffer duration (s):"), row, 0)
        self._clip_buffer = QSpinBox()
        self._clip_buffer.setFixedWidth(_INPUT_MAX_W)
        self._clip_buffer.setRange(5, 60)
        self._clip_buffer.setValue(self._config.clip_buffer_seconds)
        self._clip_buffer.valueChanged.connect(self._schedule_save)
        grid.addWidget(self._clip_buffer, row, 1)
        row += 1

        # Post-global delay
        grid.addWidget(QLabel("Save delay after global (s):"), row, 0)
        self._clip_post_global = QDoubleSpinBox()
        self._clip_post_global.setFixedWidth(_INPUT_MAX_W)
        self._clip_post_global.setDecimals(4)
        self._clip_post_global.setRange(0.0, 15.0)
        self._clip_post_global.setSingleStep(0.1)
        self._clip_post_global.setValue(self._config.clip_post_global_seconds)
        self._clip_post_global.valueChanged.connect(self._schedule_save)
        grid.addWidget(self._clip_post_global, row, 1)
        row += 1

        # Directory
        grid.addWidget(QLabel("Save directory:"), row, 0)
        cdir_w = QWidget()
        cdir_h = QHBoxLayout(cdir_w)
        cdir_h.setContentsMargins(0, 0, 0, 0)
        self._clip_dir = QLineEdit(self._config.clip_directory)
        self._clip_dir.setFixedWidth(_PATH_MAX_W)
        self._clip_dir.setPlaceholderText("~/Videos/Entropia Nexus Clips")
        self._clip_dir.editingFinished.connect(self._schedule_save)
        cdir_h.addWidget(self._clip_dir)
        cbrowse = QPushButton("Browse")
        cbrowse.clicked.connect(self._browse_clip_dir)
        cdir_h.addWidget(cbrowse)
        grid.addWidget(cdir_w, row, 1, 1, 2)
        row += 1

        # Encoding priority
        grid.addWidget(QLabel("Encoding priority:"), row, 0)
        self._encode_priority = QComboBox()
        self._encode_priority.setFixedWidth(_INPUT_MAX_W)
        self._encode_priority.addItem("Normal — fastest encoding", "normal")
        self._encode_priority.addItem("Below Normal — yields to game (recommended)", "below_normal")
        self._encode_priority.addItem("Idle — only encodes when CPU is free", "idle")
        _ep = getattr(self._config, "clip_encode_priority", "below_normal")
        _ep_idx = self._encode_priority.findData(_ep)
        if _ep_idx >= 0:
            self._encode_priority.setCurrentIndex(_ep_idx)
        self._encode_priority.setToolTip(
            "Controls how much CPU the encoder is allowed to use while the game is running.\n"
            "Below Normal lets the OS automatically back off encoding whenever the game\n"
            "requests CPU — no polling needed, the scheduler handles it.\n"
            "Idle only encodes during truly idle moments (slowest but least intrusive)."
        )
        self._encode_priority.currentIndexChanged.connect(self._schedule_save)
        grid.addWidget(self._encode_priority, row, 1)
        row += 1

        # FFmpeg path
        grid.addWidget(QLabel("FFmpeg path:"), row, 0)
        ff_w = QWidget()
        ff_h = QHBoxLayout(ff_w)
        ff_h.setContentsMargins(0, 0, 0, 0)
        self._ffmpeg_path = QLineEdit(self._config.ffmpeg_path)
        self._ffmpeg_path.setFixedWidth(_PATH_MAX_W)
        self._ffmpeg_path.setPlaceholderText("Auto-detected from PATH")
        self._ffmpeg_path.editingFinished.connect(self._schedule_save)
        ff_h.addWidget(self._ffmpeg_path)
        ff_browse = QPushButton("Browse")
        ff_browse.clicked.connect(self._browse_ffmpeg)
        ff_h.addWidget(ff_browse)
        grid.addWidget(ff_w, row, 1, 1, 2)

        layout.addLayout(grid)

        # FFmpeg status
        self._ffmpeg_status = QLabel("")
        self._ffmpeg_status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self._ffmpeg_status)
        self._update_ffmpeg_status()

        # --- System Audio sub-section ---
        game_audio_label = QLabel("System Audio")
        game_audio_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(game_audio_label)

        self._clip_audio_cb = QCheckBox("Record system audio")
        self._clip_audio_cb.setChecked(self._config.clip_audio_enabled)
        self._clip_audio_cb.setToolTip(
            "Captures audio from your output device via WASAPI loopback.\n"
            "This includes all sounds playing through the selected device."
        )
        self._clip_audio_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._clip_audio_cb)

        audio_grid = QGridLayout()
        audio_grid.setColumnStretch(0, 0)
        audio_grid.setColumnStretch(1, 0)
        audio_grid.setColumnStretch(2, 1)
        audio_grid.setHorizontalSpacing(8)

        audio_grid.addWidget(QLabel("Output device:"), 0, 0)
        self._clip_audio_device = QComboBox()
        self._clip_audio_device.setFixedWidth(_INPUT_MAX_W)
        self._clip_audio_device.addItem("System Default", "")
        self._populate_output_devices()
        self._clip_audio_device.currentIndexChanged.connect(self._on_audio_device_changed)
        audio_grid.addWidget(self._clip_audio_device, 0, 1)

        # System audio gain
        audio_grid.addWidget(QLabel("Game volume:"), 1, 0)
        game_gain_w = QWidget()
        game_gain_h = QHBoxLayout(game_gain_w)
        game_gain_h.setContentsMargins(0, 0, 0, 0)
        self._game_gain_slider = QSlider(Qt.Orientation.Horizontal)
        self._game_gain_slider.setFixedWidth(_SLIDER_MAX_W)
        self._game_gain_slider.setRange(0, 300)
        self._game_gain_slider.setValue(int(self._config.clip_audio_game_gain * 100))
        self._game_gain_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._game_gain_slider.setTickInterval(50)
        self._game_gain_slider.valueChanged.connect(self._on_game_gain_changed)
        game_gain_h.addWidget(self._game_gain_slider)
        self._game_gain_label = QLabel(f"{int(self._config.clip_audio_game_gain * 100)}%")
        self._game_gain_label.setFixedWidth(40)
        game_gain_h.addWidget(self._game_gain_label)
        audio_grid.addWidget(game_gain_w, 1, 1)

        # System audio level meter
        audio_grid.addWidget(QLabel("Level:"), 2, 0)
        self._game_level_bar = _LevelBar()
        audio_grid.addWidget(self._game_level_bar, 2, 1)

        layout.addLayout(audio_grid)

        # --- Microphone sub-section ---
        mic_label = QLabel("Microphone")
        mic_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(mic_label)

        self._clip_mic_cb = QCheckBox("Record microphone")
        self._clip_mic_cb.setChecked(self._config.clip_mic_enabled)
        self._clip_mic_cb.stateChanged.connect(self._schedule_save)
        layout.addWidget(self._clip_mic_cb)

        mic_grid = QGridLayout()
        mic_grid.setColumnStretch(0, 0)
        mic_grid.setColumnStretch(1, 0)
        mic_grid.setColumnStretch(2, 1)
        mic_grid.setHorizontalSpacing(8)

        mic_grid.addWidget(QLabel("Microphone:"), 0, 0)
        self._clip_mic_device = QComboBox()
        self._clip_mic_device.setFixedWidth(_INPUT_MAX_W)
        self._clip_mic_device.addItem("System Default", "")
        self._populate_input_devices()
        self._clip_mic_device.currentIndexChanged.connect(self._on_mic_device_changed)
        mic_grid.addWidget(self._clip_mic_device, 0, 1)

        # Mic gain
        mic_grid.addWidget(QLabel("Mic volume:"), 1, 0)
        mic_gain_w = QWidget()
        mic_gain_h = QHBoxLayout(mic_gain_w)
        mic_gain_h.setContentsMargins(0, 0, 0, 0)
        self._mic_gain_slider = QSlider(Qt.Orientation.Horizontal)
        self._mic_gain_slider.setFixedWidth(_SLIDER_MAX_W)
        self._mic_gain_slider.setRange(0, 300)
        self._mic_gain_slider.setValue(int(self._config.clip_audio_mic_gain * 100))
        self._mic_gain_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._mic_gain_slider.setTickInterval(50)
        self._mic_gain_slider.valueChanged.connect(self._on_mic_gain_changed)
        mic_gain_h.addWidget(self._mic_gain_slider)
        self._mic_gain_label = QLabel(f"{int(self._config.clip_audio_mic_gain * 100)}%")
        self._mic_gain_label.setFixedWidth(40)
        mic_gain_h.addWidget(self._mic_gain_label)
        mic_grid.addWidget(mic_gain_w, 1, 1)

        # Mic level meter
        mic_grid.addWidget(QLabel("Level:"), 2, 0)
        self._mic_level_bar = _LevelBar()
        mic_grid.addWidget(self._mic_level_bar, 2, 1)

        layout.addLayout(mic_grid)

        # Mic filter settings button
        filter_row = QHBoxLayout()
        filter_btn = QPushButton("Filter Settings...")
        filter_btn.setToolTip(
            "Configure noise suppression, noise gate, and compressor\n"
            "filters for the microphone track. Includes audio check."
        )
        filter_btn.clicked.connect(self._open_mic_filter_dialog)
        filter_row.addWidget(filter_btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Video capture config dialog (resolution, webcam, blur, background)
        config_btn = QPushButton("Configure Video Capture...")
        config_btn.setToolTip(
            "Open the video capture configuration dialog with live preview.\n"
            "Set resolution, webcam overlay, blur regions, and background."
        )
        config_btn.clicked.connect(self._open_video_config_dialog)
        config_row = QHBoxLayout()
        config_row.addWidget(config_btn)
        config_row.addStretch()
        layout.addLayout(config_row)

        # Clip-only widgets: buffer and post-global delay (not needed for recording)
        self._clip_only_widgets += [self._clip_buffer, self._clip_post_global]

        # Internal capture widgets: disabled when OBS is active (OBS handles these)
        self._internal_capture_widgets = [
            self._clip_dir, cbrowse,
            self._clip_daily_cb,
            self._encode_priority,
            self._ffmpeg_path, self._ffmpeg_status,
            self._clip_audio_cb, self._clip_audio_device,
            self._game_gain_slider,
            self._clip_mic_cb, self._clip_mic_device,
            self._mic_gain_slider,
            filter_btn, config_btn,
        ]
        self._update_capture_ui_state()

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
                    "FFmpeg not found. Video clips require FFmpeg \u2014 "
                    "it will be downloaded automatically when needed."
                )
                self._ffmpeg_status.setStyleSheet("color: #ff6b6b; font-size: 11px;")
        except Exception:
            self._ffmpeg_status.setText("Could not check FFmpeg status")

    # --- Audio device helpers ---

    def _populate_output_devices(self):
        """Populate the system audio output device dropdown."""
        try:
            from ...capture.audio_buffer import AudioBuffer
            devices = AudioBuffer.get_output_devices()
            current = self._config.clip_audio_device
            for dev in devices:
                name = dev.get("name", f"Device {dev['index']}")
                self._clip_audio_device.addItem(name, name)
            idx = self._clip_audio_device.findData(current)
            if idx >= 0:
                self._clip_audio_device.setCurrentIndex(idx)
        except Exception:
            pass

    def _populate_input_devices(self):
        """Populate the microphone input device dropdown."""
        try:
            from ...capture.audio_buffer import AudioBuffer
            devices = AudioBuffer.get_input_devices()
            current = self._config.clip_mic_device
            for dev in devices:
                name = dev.get("name", f"Device {dev['index']}")
                self._clip_mic_device.addItem(name, name)
            idx = self._clip_mic_device.findData(current)
            if idx >= 0:
                self._clip_mic_device.setCurrentIndex(idx)
        except Exception:
            pass

    # --- Gain slider handlers ---

    def _on_game_gain_changed(self, value):
        self._game_gain_label.setText(f"{value}%")
        self._schedule_save()

    def _on_mic_gain_changed(self, value):
        self._mic_gain_label.setText(f"{value}%")
        self._schedule_save()

    def _on_audio_device_changed(self, _idx):
        """Update system audio device and restart meter."""
        self._schedule_save()
        if self._game_meter_buf is not None:
            self._restart_game_meter()

    def _on_mic_device_changed(self, _idx):
        """Update mic device immediately when the dropdown changes."""
        self._schedule_save()
        if self._mic_filtered_meter is not None:
            self._restart_mic_meter()

    # --- Audio level meters ---

    def _build_mic_filter_dict(self) -> dict:
        """Build mic filter dict from current config values."""
        c = self._config
        return {
            "noise_suppression": getattr(c, "clip_audio_noise_suppression", False),
            "noise_gate": getattr(c, "clip_audio_noise_gate", False),
            "compressor": getattr(c, "clip_audio_compressor", False),
            "ns_mix": getattr(c, "clip_audio_ns_mix", 1.0),
            "gate_threshold": getattr(c, "clip_audio_gate_threshold", 0.01),
            "gate_ratio": getattr(c, "clip_audio_gate_ratio", 10.0),
            "gate_attack": getattr(c, "clip_audio_gate_attack", 5.0),
            "gate_release": getattr(c, "clip_audio_gate_release", 200.0),
            "comp_threshold": getattr(c, "clip_audio_comp_threshold", -20.0),
            "comp_ratio": getattr(c, "clip_audio_comp_ratio", 4.0),
            "comp_attack": getattr(c, "clip_audio_comp_attack", 5.0),
            "comp_release": getattr(c, "clip_audio_comp_release", 100.0),
        }

    def _start_meters(self) -> None:
        """Start audio level meter buffers and polling timer."""
        if self._meter_timer is not None:
            return  # already running

        # Start buffers in background to avoid WASAPI device open lag
        threading.Thread(
            target=self._open_meter_buffers, daemon=True,
            name="meter-start",
        ).start()

        self._meter_timer = QTimer(self)
        self._meter_timer.setInterval(_METER_UPDATE_MS)
        self._meter_timer.timeout.connect(self._update_meters)
        self._meter_timer.start()

    def _open_meter_buffers(self) -> None:
        """Open audio meter buffers (runs in background thread)."""
        from ...capture.audio_buffer import AudioBuffer

        # System audio (loopback)
        try:
            device = self._clip_audio_device.currentData() or None
            buf = AudioBuffer(device=device, loopback=True)
            buf.start()
            self._game_meter_buf = buf
        except Exception as e:
            log.debug("System audio meter failed: %s", e)

        # Mic — filtered through FFmpeg pipeline
        try:
            from ..dialogs.audio_filter_dialogs import _FilteredMicMeter
            mic_device = self._clip_mic_device.currentData() or None
            mic_gain = self._config.clip_audio_mic_gain
            meter = _FilteredMicMeter(
                mic_device=mic_device,
                mic_gain=mic_gain,
                filters=self._build_mic_filter_dict(),
                ffmpeg_path=self._config.ffmpeg_path,
            )
            meter.start()
            self._mic_filtered_meter = meter
        except Exception as e:
            log.debug("Mic filtered meter failed: %s", e)

    def _stop_meters(self) -> None:
        """Stop audio level meters and release resources."""
        if self._meter_timer is not None:
            self._meter_timer.stop()
            self._meter_timer = None

        # Stop buffers in background to avoid WASAPI lag
        game_buf = self._game_meter_buf
        mic_meter = self._mic_filtered_meter
        self._game_meter_buf = None
        self._mic_filtered_meter = None

        if game_buf or mic_meter:
            def _stop():
                for obj in (game_buf, mic_meter):
                    if obj is not None:
                        try:
                            obj.stop()
                        except Exception:
                            pass
            threading.Thread(target=_stop, daemon=True, name="meter-stop").start()

        if self._game_level_bar:
            self._game_level_bar.set_level(0.0)
        if self._mic_level_bar:
            self._mic_level_bar.set_level(0.0)

    def _restart_game_meter(self) -> None:
        """Restart system audio meter with the currently selected device."""
        old = self._game_meter_buf
        self._game_meter_buf = None

        def _swap():
            if old is not None:
                try:
                    old.stop()
                except Exception:
                    pass
            try:
                from ...capture.audio_buffer import AudioBuffer
                device = self._clip_audio_device.currentData() or None
                buf = AudioBuffer(device=device, loopback=True)
                buf.start()
                self._game_meter_buf = buf
            except Exception as e:
                log.debug("Could not restart game meter: %s", e)

        threading.Thread(target=_swap, daemon=True, name="meter-game-restart").start()

    def _restart_mic_meter(self) -> None:
        """Restart filtered mic meter with current device and filters."""
        old = self._mic_filtered_meter
        self._mic_filtered_meter = None

        def _swap():
            if old is not None:
                try:
                    old.stop()
                except Exception:
                    pass
            try:
                from ..dialogs.audio_filter_dialogs import _FilteredMicMeter
                mic_device = self._clip_mic_device.currentData() or None
                mic_gain = self._config.clip_audio_mic_gain
                meter = _FilteredMicMeter(
                    mic_device=mic_device,
                    mic_gain=mic_gain,
                    filters=self._build_mic_filter_dict(),
                    ffmpeg_path=self._config.ffmpeg_path,
                )
                meter.start()
                self._mic_filtered_meter = meter
            except Exception as e:
                log.debug("Could not restart mic meter: %s", e)

        threading.Thread(target=_swap, daemon=True, name="meter-mic-restart").start()

    def _update_meters(self) -> None:
        """Poll audio buffers and update level bars."""
        now = time.monotonic()
        start = now - _METER_SNAPSHOT_S

        # System audio — uses AudioBuffer.snapshot()
        buf = self._game_meter_buf
        if buf is not None and self._game_level_bar is not None:
            pcm = buf.snapshot(start, now)
            if pcm is not None and len(pcm) > 0:
                gain = self._game_gain_slider.value() / 100.0
                peak = float(np.max(np.abs(pcm))) * gain
                self._game_level_bar.set_level(min(1.0, peak))
            else:
                self._game_level_bar.set_level(0.0)

        # Mic — uses _FilteredMicMeter.peak property
        meter = self._mic_filtered_meter
        if meter is not None and self._mic_level_bar is not None:
            gain = self._mic_gain_slider.value() / 100.0
            peak = meter.peak * gain
            self._mic_level_bar.set_level(min(1.0, peak))

    def showEvent(self, event):
        super().showEvent(event)
        self._start_meters()

    def hideEvent(self, event):
        self._stop_meters()
        super().hideEvent(event)

    # --- Mic filter dialog ---

    def _open_mic_filter_dialog(self):
        try:
            from ..dialogs.audio_filter_dialogs import MicFilterDialog
            dialog = MicFilterDialog(
                config=self._config, config_path=self._config_path,
                event_bus=self._event_bus, parent=self,
            )
            if dialog.exec():
                # Sync mic gain slider — dialog may have changed it
                self._mic_gain_slider.setValue(int(self._config.clip_audio_mic_gain * 100))
            # Restart mic meter with potentially updated filters
            self._restart_mic_meter()
        except Exception as e:
            log.error("Failed to open mic filter dialog: %s", e)

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

        # Grid for label+input pairs
        adv_grid = QGridLayout()
        adv_grid.setColumnStretch(0, 0)
        adv_grid.setColumnStretch(1, 0)
        adv_grid.setColumnStretch(2, 1)
        adv_grid.setHorizontalSpacing(8)
        adv_row = 0

        # Database path
        adv_grid.addWidget(QLabel("Database path:"), adv_row, 0)
        self._db_path = QLineEdit(self._config.database_path)
        self._db_path.setFixedWidth(_PATH_MAX_W)
        self._db_path.setReadOnly(True)
        adv_grid.addWidget(self._db_path, adv_row, 1)
        adv_row += 1

        # JS utils path override
        adv_grid.addWidget(QLabel("JS utils path (override):"), adv_row, 0)
        js_w = QWidget()
        js_h = QHBoxLayout(js_w)
        js_h.setContentsMargins(0, 0, 0, 0)
        self._js_path = QLineEdit(self._config.js_utils_path)
        self._js_path.setFixedWidth(_PATH_MAX_W)
        js_h.addWidget(self._js_path)
        js_browse = QPushButton("Browse")
        js_browse.clicked.connect(self._browse_js_path)
        js_h.addWidget(js_browse)
        adv_grid.addWidget(js_w, adv_row, 1, 1, 2)
        adv_row += 1

        # OAuth client ID
        adv_grid.addWidget(QLabel("OAuth Client ID:"), adv_row, 0)
        self._oauth_client_id = QLineEdit(self._config.oauth_client_id)
        self._oauth_client_id.setFixedWidth(_PATH_MAX_W)
        adv_grid.addWidget(self._oauth_client_id, adv_row, 1)
        adv_row += 1

        # Twitch Client ID override
        adv_grid.addWidget(QLabel("Twitch Client ID:"), adv_row, 0)
        self._twitch_client_id = QLineEdit(self._config.twitch_client_id)
        self._twitch_client_id.setFixedWidth(_PATH_MAX_W)
        self._twitch_client_id.setPlaceholderText("(built-in default)")
        adv_grid.addWidget(self._twitch_client_id, adv_row, 1)

        layout.addLayout(adv_grid)

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

    # Windows build that introduced GraphicsCaptureSession.MinUpdateInterval
    _WGC_MIN_UPDATE_INTERVAL_BUILD = 22621

    def _on_capture_backend_changed(self, _index: int) -> None:
        """Handle capture backend combo change — warn about WGC on older OS."""
        backend = self._ocr_capture_backend.currentData()
        if (backend == "wgc"
                and sys.platform == "win32"
                and sys.getwindowsversion().build < self._WGC_MIN_UPDATE_INTERVAL_BUILD):
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("WGC Resource Warning")
            dlg.setText(
                "On this version of Windows, WGC runs continuously at your "
                "display's refresh rate and cannot be throttled by the OS.\n\n"
                "This causes significant CPU and GPU usage even when only "
                "a few frames per second are needed (e.g. OCR-only mode).\n\n"
                "BitBlt is recommended as a lightweight alternative.\n"
                "It works well for most setups unless your game "
                "window renders black with it."
            )
            switch_btn = dlg.addButton(
                "Switch to BitBlt", QMessageBox.ButtonRole.AcceptRole,
            )
            dlg.addButton(
                "Keep WGC", QMessageBox.ButtonRole.RejectRole,
            )
            dlg.setDefaultButton(switch_btn)
            dlg.exec()
            if dlg.clickedButton() == switch_btn:
                idx = self._ocr_capture_backend.findData("bitblt")
                if idx >= 0:
                    self._ocr_capture_backend.setCurrentIndex(idx)
                return  # setCurrentIndex triggers this handler again → save
        self._schedule_save()

    def _schedule_save(self, *_args):
        """Schedule a debounced save (restarts the 300ms timer on each call)."""
        self._save_timer.start()

    def _do_save(self):
        """Apply all settings from the UI to config and persist."""
        # Startup
        boot_changed = self._config.start_on_boot != self._start_on_boot_cb.isChecked()
        self._config.start_on_boot = self._start_on_boot_cb.isChecked()
        self._config.start_minimized = self._start_minimized_cb.isChecked()
        if boot_changed:
            from ...platform.autostart import set_enabled
            set_enabled(self._config.start_on_boot)

        self._config.chat_log_path = self._chat_path.text()
        self._config.poll_interval_ms = self._poll_interval.value()
        self._config.overlay_opacity = self._opacity_slider.value() / 100.0
        self._config.auto_pin_detail_overlay = self._auto_pin_cb.isChecked()
        self._config.overlay_enabled = self._skill_scanner_cb.isChecked()
        self._config.ocr_capture_backend = (
            self._ocr_capture_backend.currentData() or "auto"
        )
        self._config.hdr_compatibility_mode = self._hdr_cb.isChecked()
        self._config.ocr_trace_enabled = self._ocr_trace_cb.isChecked()
        self._config.check_for_updates = self._updates_cb.isChecked()
        self._config.js_utils_path = self._js_path.text()
        self._config.oauth_client_id = self._oauth_client_id.text()
        self._config.twitch_client_id = self._twitch_client_id.text()

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
        self._config.screenshot_size_pct = self._screenshot_size.currentData()
        self._config.screenshot_sound_enabled = self._screenshot_sound_cb.isChecked()
        self._config.character_name = self._character_name.text()

        # OBS Studio
        self._config.obs_enabled = self._obs_enabled_cb.isChecked()
        self._config.obs_host = self._obs_host.text() or "localhost"
        self._config.obs_port = self._obs_port.value()
        self._config.obs_manage_replay_buffer = self._obs_manage_replay_cb.isChecked()
        if self._config.obs_enabled:
            self._config.obs_replay_buffer_asked = True
        # Password saved to keyring in _on_obs_password_changed(), not in config

        # Video Capture + Clips (resolution/fps/bitrate/webcam-enable/blur/background
        # are saved by VideoConfigDialog directly)
        self._config.capture_enabled = self._capture_enabled_cb.isChecked()
        self._config.clip_enabled = self._clip_enabled_cb.isChecked()
        self._config.clip_auto_on_global = self._clip_auto_cb.isChecked()
        self._config.clip_buffer_seconds = self._clip_buffer.value()
        self._config.clip_post_global_seconds = self._clip_post_global.value()
        self._config.clip_directory = self._clip_dir.text()
        self._config.clip_daily_subfolder = self._clip_daily_cb.isChecked()
        self._config.clip_sound_enabled = self._clip_sound_cb.isChecked()
        self._config.clip_encode_priority = self._encode_priority.currentData() or "below_normal"
        self._config.ffmpeg_path = self._ffmpeg_path.text()

        # System Audio
        self._config.clip_audio_enabled = self._clip_audio_cb.isChecked()
        self._config.clip_audio_device = self._clip_audio_device.currentData() or ""
        self._config.clip_audio_game_gain = self._game_gain_slider.value() / 100.0

        # Microphone
        self._config.clip_mic_enabled = self._clip_mic_cb.isChecked()
        self._config.clip_mic_device = self._clip_mic_device.currentData() or ""
        self._config.clip_audio_mic_gain = self._mic_gain_slider.value() / 100.0

        save_config(self._config, self._config_path)
        self._event_bus.publish(EVENT_CONFIG_CHANGED, self._config)
