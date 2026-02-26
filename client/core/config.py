import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .constants import DEFAULT_CHAT_LOG_PATH
from .logger import get_logger

log = get_logger("Config")

TESSERACT_COMMON_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


@dataclass
class AppConfig:
    # Chat parser
    chat_log_path: str = ""
    database_path: str = "./data/nexus_client.db"
    poll_interval_ms: int = 500
    loot_group_window_ms: int = 1500

    # OCR - general
    tesseract_path: str = ""
    ocr_confidence_threshold: float = 0.7

    # OCR - HUD regions (x, y, w, h) for mob/tool name detection
    mob_name_region: tuple[int, int, int, int] | None = None
    tool_name_region: tuple[int, int, int, int] | None = None

    # Overlay
    hunt_overlay_position: tuple[int, int] = (50, 50)
    progress_overlay_position: tuple[int, int] = (50, 50)
    overlay_opacity: float = 0.85

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

    # Hunt markup (custom override for loot MU calculations)
    hunt_markup_pct: float = 100.0

    # Open encounter auto-merge: auto-merge successive deaths to same mob
    auto_merge_deaths: bool = False

    # Loot blacklist — items never counted as loot
    # Global: always applied regardless of mob
    # Per-mob: only applied when hunting that specific mob (mob_name_lower -> item names)
    loot_blacklist: list[str] = field(default_factory=list)
    loot_blacklist_per_mob: dict[str, list[str]] = field(default_factory=dict)

    # Hotkeys (key combo strings, e.g. "ctrl+shift+h")
    hotkey_start_hunt: str = ""
    hotkey_stop_hunt: str = ""
    hotkey_manual_mob_name: str = ""
    hotkey_ocr_scan: str = "F7"

    # UI
    main_window_geometry: str = ""
    active_loadout_id: str | None = None

    # Wiki
    wiki_column_prefs: dict = field(default_factory=dict)

    # Loadout JS bridge
    js_utils_path: str = ""


DEFAULTS = {
    "chat_log_path": str(Path(DEFAULT_CHAT_LOG_PATH).expanduser()),
    "database_path": "./data/nexus_client.db",
    "poll_interval_ms": 500,
    "loot_group_window_ms": 1500,
    "ocr_confidence_threshold": 0.7,
    "tesseract_path": "",
    "mob_name_region": None,
    "tool_name_region": None,
    "hunt_overlay_position": [50, 50],
    "progress_overlay_position": [50, 50],
    "overlay_opacity": 0.85,
    "nexus_base_url": "https://entropianexus.com",
    "api_base_url": "https://api.entropianexus.com",
    "oauth_client_id": "",
    "oauth_redirect_port": 47832,
    "encounter_close_timeout_ms": 15000,
    "attribution_window_ms": 3000,
    "session_auto_timeout_ms": 3600000,
    "hunt_split_mob_threshold": 10,
    "hunt_split_min_remote_kills": 5,
    "hunt_markup_pct": 100.0,
    "auto_merge_deaths": False,
    "loot_blacklist": [],
    "loot_blacklist_per_mob": {},
    "hotkey_start_hunt": "",
    "hotkey_stop_hunt": "",
    "hotkey_manual_mob_name": "",
    "hotkey_ocr_scan": "F7",
    "main_window_geometry": "",
    "active_loadout_id": None,
    "wiki_column_prefs": {},
    "js_utils_path": "",
}


def load_config(config_path: str = "config.json") -> AppConfig:
    """Load config from JSON file, merging with defaults."""
    merged = dict(DEFAULTS)
    user_config = {}

    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            user_config = json.load(f)
        merged.update(user_config)

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
        "mob_name_region", "tool_name_region",
    ):
        val = merged.get(key)
        if isinstance(val, list):
            merged[key] = tuple(val)

    # Expand ~ in paths
    for key in ("chat_log_path", "database_path", "tesseract_path", "js_utils_path"):
        if merged.get(key):
            merged[key] = str(Path(merged[key]).expanduser())

    # Auto-detect tesseract if not explicitly set
    if not merged.get("tesseract_path"):
        merged["tesseract_path"] = _find_tesseract() or ""

    config = AppConfig(**{k: v for k, v in merged.items() if k in AppConfig.__dataclass_fields__})
    errors = validate_config(config)
    if errors:
        log.warning("Warnings: %s", "; ".join(errors))

    return config


def save_config(config: AppConfig, config_path: str = "config.json") -> None:
    """Save current config to JSON file."""
    data = {}
    for key, default_val in DEFAULTS.items():
        val = getattr(config, key, default_val)
        # Convert tuples to lists for JSON
        if isinstance(val, tuple):
            val = list(val)
        data[key] = val

    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)


def _find_tesseract() -> str | None:
    """Auto-detect tesseract executable from PATH and common install locations."""
    # Check PATH first
    found = shutil.which("tesseract")
    if found:
        return found

    # Check common Windows install paths
    for path in TESSERACT_COMMON_PATHS:
        if os.path.isfile(path):
            return path

    return None


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

    return errors
