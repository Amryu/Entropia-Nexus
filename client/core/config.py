import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .constants import DEFAULT_CHAT_LOG_PATH, SCAN_ROI_VERSION
from .logger import get_logger

log = get_logger("Config")


@dataclass
class AppConfig:
    # Chat parser
    chat_log_path: str = ""
    database_path: str = "./data/nexus_client.db"
    poll_interval_ms: int = 500
    loot_group_window_ms: int = 1500

    # OCR - general
    ocr_confidence_threshold: float = 0.7
    ocr_search_margin: int = 80       # px, local-area search radius for tier-2 template matching
    ocr_adjust_margin: int = 8        # px, skills quick_adjust search radius
    ocr_idle_threshold: int = 50      # ticks with no change before entering idle mode
    ocr_idle_multiplier: int = 5      # poll interval multiplier in idle mode
    ocr_capture_backend: str = "auto"  # auto | printwindow | wgc
    ocr_auto_scan_enabled: bool = True
    scan_overlay_debug: bool = False
    scan_roi_overrides: dict = field(default_factory=dict)  # {name: [x,y,w,h]} pixel offsets from SKILLS template
    scan_roi_version: int = 0  # Tracks DEFAULT_ROI_PIXELS version; reset overrides when outdated
    ocr_trace_enabled: bool = False

    # OCR - HUD regions (x, y, w, h) for mob/tool name detection
    mob_name_region: tuple[int, int, int, int] | None = None
    tool_name_region: tuple[int, int, int, int] | None = None

    # Overlay
    hunt_overlay_position: tuple[int, int] = (50, 50)
    progress_overlay_position: tuple[int, int] = (50, 50)
    search_overlay_position: tuple[int, int] = (50, 50)
    detail_overlay_position: tuple[int, int] = (400, 50)
    map_overlay_position: tuple[int, int] = (100, 100)
    scan_summary_overlay_position: tuple[int, int] = (100, 200)
    confirm_overlay_position: tuple[int, int] = (100, 200)
    profile_overlay_position: tuple[int, int] = (450, 50)
    society_overlay_position: tuple[int, int] = (450, 50)
    exchange_overlay_position: tuple[int, int] = (100, 100)
    exchange_overlay_size: tuple[int, int] = (700, 500)
    notifications_overlay_position: tuple[int, int] = (100, 100)
    map_overlay_size: int = 1  # 0=Small, 1=Medium, 2=Large
    overlay_opacity: float = 0.85
    overlay_enabled: bool = True
    auto_pin_detail_overlay: bool = False

    # Auth
    nexus_base_url: str = "https://entropianexus.com"
    api_base_url: str = "https://api.entropianexus.com"
    oauth_client_id: str = ""
    oauth_redirect_port: int = 47832

    # Hunt tracking
    encounter_close_timeout_ms: int = 15000
    attribution_window_ms: int = 3000
    session_auto_timeout_ms: int = 3600000      # 1 hour
    hunt_split_mob_threshold: int = 10           # consecutive kills before confirming mob-type split
    hunt_split_min_remote_kills: int = 5         # kills at new location before confirming split

    # Open encounter auto-merge: auto-merge successive deaths to same mob
    auto_merge_deaths: bool = False

    # Loot blacklist — items never counted as loot
    # Global: always applied regardless of mob
    # Per-mob: only applied when hunting that specific mob (mob_name_lower -> item names)
    loot_blacklist: list[str] = field(default_factory=list)
    loot_blacklist_per_mob: dict[str, list[str]] = field(default_factory=dict)

    # Hotkeys (key combo strings, e.g. "ctrl+shift+h")
    hotkeys_enabled: bool = True
    hotkey_start_hunt: str = ""
    hotkey_stop_hunt: str = ""
    hotkey_manual_mob_name: str = ""
    hotkey_ocr_scan: str = "F7"
    hotkey_search: str = "ctrl+f"
    hotkey_map: str = "ctrl+m"
    hotkey_exchange: str = "ctrl+e"
    hotkey_notifications: str = "ctrl+n"
    hotkey_debug: str = "f3"
    hotkey_overlay_toggle: str = "f2"

    # UI
    main_window_screen_center: list | None = None
    active_loadout_id: str | None = None

    # Wiki
    wiki_column_prefs: dict = field(default_factory=dict)

    # Inventory
    inventory_prefs: dict = field(default_factory=dict)

    # Loadout JS bridge
    js_utils_path: str = ""

    # Legal
    tos_accepted_version: str = ""

    # Updates
    check_for_updates: bool = True
    update_dismissed_version: str = ""
    update_remind_at: str = ""

    # Notifications
    notification_sound_enabled: bool = True
    notification_toast_enabled: bool = True
    notification_toast_corner: str = "bottom_right"
    notification_rules: list[dict] = field(default_factory=list)
    notification_filter_self: bool = True
    trade_chat_notifications_enabled: bool = False
    trade_chat_ignore_list: list[str] = field(default_factory=list)
    trade_chat_cooldown_minutes: int = 60
    trade_chat_keywords: list[dict] = field(default_factory=list)

    # Streams
    stream_notifications_enabled: bool = True
    stream_exclude_list: list[str] = field(default_factory=list)

    # Tracker — Dailies & Events
    tracker_missions: list = field(default_factory=list)
    tracker_event_reminders: list = field(default_factory=list)

    # Dashboard — Globals feed
    dashboard_globals_min_value: float = 0.0
    dashboard_globals_blocked_types: list[str] = field(default_factory=list)

    # Dashboard — Trade feed
    dashboard_trade_blocklist: list[str] = field(default_factory=list)
    dashboard_trade_planet_filter: list[str] = field(default_factory=list)
    dashboard_trade_blacklist: list[str] = field(default_factory=list)

    # Target lock detection
    target_lock_enabled: bool = True
    target_lock_match_threshold: float = 0.90
    target_lock_roi_hp: dict = field(default_factory=lambda: {"dx": -89, "dy": -17, "w": 193, "h": 6})
    target_lock_roi_shared: dict = field(default_factory=lambda: {"dx": -125, "dy": -22, "w": 16, "h": 16})
    target_lock_roi_name: dict = field(default_factory=lambda: {"dx": -190, "dy": -40, "w": 394, "h": 14})

    # Market price window detection
    market_price_enabled: bool = True
    market_price_match_threshold: float = 0.9
    market_price_poll_interval: float = 1.0
    market_price_roi_name_row1: dict = field(default_factory=lambda: {"dx": -80, "dy": 30, "w": 340, "h": 16})
    market_price_roi_name_row2: dict = field(default_factory=lambda: {"dx": -80, "dy": 49, "w": 340, "h": 16})
    market_price_roi_first_cell: dict = field(default_factory=lambda: {"dx": 23, "dy": 112, "w": 100, "h": 14})
    market_price_cell_offset: dict = field(default_factory=lambda: {"x": 107, "y": 25})
    market_price_roi_tier: dict = field(default_factory=lambda: {"dx": 79, "dy": 252, "w": 18, "h": 14})
    market_price_digit_stpk: str = "market_digits.stpk"
    market_price_text_stpk: str = "market_text.stpk"
    market_price_text_threshold: int = 80  # brightness cutoff for text vs background noise

    # Player status (heart) detection
    player_status_enabled: bool = True
    player_status_match_threshold: float = 0.90
    player_status_roi_health: dict = field(default_factory=lambda: {"dx": 30, "dy": -9, "w": 315, "h": 12})
    player_status_roi_reload: dict = field(default_factory=lambda: {"dx": 30, "dy": 5, "w": 315, "h": 3})
    player_status_roi_buff: dict = field(default_factory=lambda: {"dx": -7, "dy": -57, "w": 459, "h": 32})
    player_status_roi_buff_small: dict = field(default_factory=lambda: {"dx": 0, "dy": 0, "w": 1, "h": 1})
    player_status_roi_tool_name: dict = field(default_factory=lambda: {"dx": 30, "dy": 13, "w": 315, "h": 14})

    # Ingestion (crowdsourced data upload/download)
    ingestion_enabled: bool = True
    ingestion_upload_interval_seconds: int = 30
    ingestion_receive_interval_seconds: int = 60


DEFAULTS = {
    "chat_log_path": str(Path(DEFAULT_CHAT_LOG_PATH).expanduser()),
    "database_path": "./data/nexus_client.db",
    "poll_interval_ms": 500,
    "loot_group_window_ms": 1500,
    "ocr_confidence_threshold": 0.7,
    "ocr_search_margin": 80,
    "ocr_adjust_margin": 8,
    "ocr_idle_threshold": 50,
    "ocr_idle_multiplier": 5,
    "ocr_capture_backend": "auto",
    "ocr_auto_scan_enabled": True,
    "scan_overlay_debug": False,
    "scan_roi_overrides": {},
    "scan_roi_version": 0,
    "mob_name_region": None,
    "tool_name_region": None,
    "hunt_overlay_position": [50, 50],
    "progress_overlay_position": [50, 50],
    "search_overlay_position": [50, 50],
    "detail_overlay_position": [400, 50],
    "exchange_overlay_position": [100, 100],
    "exchange_overlay_size": [700, 500],
    "notifications_overlay_position": [100, 100],
    "map_overlay_position": [100, 100],
    "scan_summary_overlay_position": [100, 200],
    "confirm_overlay_position": [100, 200],
    "profile_overlay_position": [450, 50],
    "society_overlay_position": [450, 50],
    "map_overlay_size": 1,
    "overlay_opacity": 0.85,
    "overlay_enabled": True,
    "auto_pin_detail_overlay": False,
    "nexus_base_url": "https://entropianexus.com",
    "api_base_url": "https://api.entropianexus.com",
    "oauth_client_id": "",
    "oauth_redirect_port": 47832,
    "encounter_close_timeout_ms": 15000,
    "attribution_window_ms": 3000,
    "session_auto_timeout_ms": 3600000,
    "hunt_split_mob_threshold": 10,
    "hunt_split_min_remote_kills": 5,
    "auto_merge_deaths": False,
    "loot_blacklist": [],
    "loot_blacklist_per_mob": {},
    "hotkeys_enabled": True,
    "hotkey_start_hunt": "",
    "hotkey_stop_hunt": "",
    "hotkey_manual_mob_name": "",
    "hotkey_ocr_scan": "F7",
    "hotkey_search": "ctrl+f",
    "hotkey_map": "ctrl+m",
    "hotkey_exchange": "ctrl+e",
    "hotkey_notifications": "ctrl+n",
    "hotkey_debug": "f3",
    "hotkey_overlay_toggle": "f2",
    "main_window_screen_center": None,
    "active_loadout_id": None,
    "wiki_column_prefs": {},
    "inventory_prefs": {},
    "js_utils_path": "",
    "tos_accepted_version": "",
    "check_for_updates": True,
    "update_dismissed_version": "",
    "update_remind_at": "",
    "notification_sound_enabled": True,
    "notification_toast_enabled": True,
    "notification_toast_corner": "bottom_right",
    "notification_rules": [],
    "notification_filter_self": True,
    "trade_chat_notifications_enabled": False,
    "trade_chat_ignore_list": [],
    "trade_chat_cooldown_minutes": 60,
    "trade_chat_keywords": [],
    "stream_notifications_enabled": True,
    "stream_exclude_list": [],
    "dashboard_globals_min_value": 0.0,
    "dashboard_globals_blocked_types": [],
    "dashboard_trade_blocklist": [],
    "dashboard_trade_planet_filter": [],
    "dashboard_trade_blacklist": [],
    "target_lock_enabled": True,
    "target_lock_match_threshold": 0.90,
    "target_lock_roi_hp": {"dx": -89, "dy": -17, "w": 193, "h": 6},
    "target_lock_roi_shared": {"dx": -125, "dy": -22, "w": 16, "h": 16},
    "target_lock_roi_name": {"dx": -190, "dy": -40, "w": 394, "h": 14},
    "market_price_enabled": True,
    "market_price_match_threshold": 0.9,
    "market_price_poll_interval": 1.0,
    "market_price_roi_name_row1": {"dx": -80, "dy": 30, "w": 340, "h": 16},
    "market_price_roi_name_row2": {"dx": -80, "dy": 49, "w": 340, "h": 16},
    "market_price_roi_first_cell": {"dx": 23, "dy": 112, "w": 100, "h": 14},
    "market_price_cell_offset": {"x": 107, "y": 25},
    "market_price_roi_tier": {"dx": 79, "dy": 252, "w": 18, "h": 14},
    "market_price_digit_stpk": "market_digits.stpk",
    "market_price_text_stpk": "market_text.stpk",
    "market_price_text_threshold": 80,
    "player_status_enabled": True,
    "player_status_match_threshold": 0.90,
    "player_status_roi_health": {"dx": 30, "dy": -9, "w": 315, "h": 12},
    "player_status_roi_reload": {"dx": 30, "dy": 5, "w": 315, "h": 3},
    "player_status_roi_buff": {"dx": -7, "dy": -57, "w": 459, "h": 32},
    "player_status_roi_buff_small": {"dx": 0, "dy": 0, "w": 1, "h": 1},
    "player_status_roi_tool_name": {"dx": 30, "dy": 13, "w": 315, "h": 14},
    "ingestion_enabled": True,
    "ingestion_upload_interval_seconds": 30,
    "ingestion_receive_interval_seconds": 60,
}


def _try_load_json(path: str) -> dict | None:
    """Try to load a JSON file, returning None on any failure."""
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        log.warning("Config file %s is not a JSON object", path)
        return None
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Failed to read %s: %s", path, e)
        return None


def load_config(config_path: str = "config.json") -> AppConfig:
    """Load config from JSON file, merging with defaults."""
    merged = dict(DEFAULTS)
    user_config = {}

    backup_path = config_path + ".bak"

    if os.path.exists(config_path):
        user_config = _try_load_json(config_path)

        if user_config is None and os.path.exists(backup_path):
            log.warning("Config corrupted, restoring from backup")
            user_config = _try_load_json(backup_path)
            if user_config is not None:
                try:
                    shutil.copy2(backup_path, config_path)
                except OSError as e:
                    log.error("Failed to restore backup: %s", e)

        if user_config is None:
            log.error("Config and backup both unreadable, using defaults")
            user_config = {}

        merged.update(user_config)

    # Migrate trade_chat_cooldown_seconds → trade_chat_cooldown_minutes
    if "trade_chat_cooldown_seconds" in user_config and "trade_chat_cooldown_minutes" not in user_config:
        secs = user_config["trade_chat_cooldown_seconds"]
        merged["trade_chat_cooldown_minutes"] = max(1, secs // 60)
    merged.pop("trade_chat_cooldown_seconds", None)

    # Reset stale ROI overrides when defaults change
    if merged.get("scan_roi_version", 0) < SCAN_ROI_VERSION:
        merged["scan_roi_overrides"] = {}
        merged["scan_roi_version"] = SCAN_ROI_VERSION

    # Migrate legacy overlay_position → per-overlay keys
    if "overlay_position" in user_config:
        old_pos = user_config["overlay_position"]
        if "hunt_overlay_position" not in user_config:
            merged["hunt_overlay_position"] = old_pos
        if "progress_overlay_position" not in user_config:
            merged["progress_overlay_position"] = old_pos

    # Convert list fields to tuples
    for key in (
        "hunt_overlay_position", "progress_overlay_position",
        "search_overlay_position", "detail_overlay_position",
        "exchange_overlay_position", "exchange_overlay_size",
        "notifications_overlay_position",
        "map_overlay_position", "scan_summary_overlay_position",
        "confirm_overlay_position", "profile_overlay_position",
        "society_overlay_position",
        "mob_name_region", "tool_name_region",
    ):
        val = merged.get(key)
        if isinstance(val, list):
            merged[key] = tuple(val)

    # Expand ~ in paths
    for key in ("chat_log_path", "database_path", "js_utils_path"):
        if merged.get(key):
            merged[key] = str(Path(merged[key]).expanduser())

    config = AppConfig(**{k: v for k, v in merged.items() if k in AppConfig.__dataclass_fields__})
    errors = validate_config(config)
    if errors:
        log.warning("Warnings: %s", "; ".join(errors))

    return config


def save_config(config: AppConfig, config_path: str = "config.json") -> None:
    """Save current config to JSON file (atomic write with backup)."""
    data = {}
    for key, default_val in DEFAULTS.items():
        val = getattr(config, key, default_val)
        if isinstance(val, tuple):
            val = list(val)
        data[key] = val

    tmp_path = config_path + ".tmp"
    backup_path = config_path + ".bak"

    try:
        # Backup current config (if it exists and has content)
        if os.path.isfile(config_path) and os.path.getsize(config_path) > 0:
            shutil.copy2(config_path, backup_path)

        # Write to temp file, then atomic rename
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, config_path)
    except Exception as e:
        log.error("Failed to save config: %s", e)
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


def validate_config(config: AppConfig) -> list[str]:
    """Return list of validation warnings."""
    errors = []

    if not config.chat_log_path:
        errors.append("chat_log_path is not set")
    elif not os.path.exists(config.chat_log_path):
        errors.append(f"chat_log_path does not exist: {config.chat_log_path}")

    if not 0.0 <= config.overlay_opacity <= 1.0:
        errors.append(f"overlay_opacity must be 0.0-1.0, got {config.overlay_opacity}")

    if config.poll_interval_ms < 100:
        errors.append(f"poll_interval_ms must be >= 100, got {config.poll_interval_ms}")

    if not 0.0 <= config.ocr_confidence_threshold <= 1.0:
        errors.append(f"ocr_confidence_threshold must be 0.0-1.0, got {config.ocr_confidence_threshold}")

    if config.ocr_capture_backend not in {"auto", "printwindow", "wgc"}:
        errors.append(
            "ocr_capture_backend must be one of: auto, printwindow, wgc "
            f"(got {config.ocr_capture_backend})",
        )

    return errors
