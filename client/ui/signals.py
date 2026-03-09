"""Qt signals bridge — routes EventBus events to the Qt main thread."""

from PyQt6.QtCore import QObject, pyqtSignal

from ..core.constants import (
    EVENT_API_SCOPE_ERROR,
    EVENT_AUTH_STATE_CHANGED,
    EVENT_CATCHUP_COMPLETE,
    EVENT_CATCHUP_PROGRESS,
    EVENT_COMBAT,
    EVENT_CONFIG_CHANGED,
    EVENT_ENHANCER_BREAK,
    EVENT_TIER_INCREASE,
    EVENT_GLOBAL,
    EVENT_HISTORICAL_IMPORT_COMPLETE,
    EVENT_HISTORICAL_IMPORT_PROGRESS,
    EVENT_HUNT_ENCOUNTER_ENDED,
    EVENT_HUNT_ENCOUNTER_STARTED,
    EVENT_HUNT_SESSION_STARTED,
    EVENT_HUNT_SESSION_STOPPED,
    EVENT_HUNT_SESSION_UPDATED,
    EVENT_HUNT_STARTED,
    EVENT_HUNT_ENDED,
    EVENT_HUNT_SPLIT,
    EVENT_SESSION_AUTO_TIMEOUT,
    EVENT_INGESTED_GLOBAL,
    EVENT_INGESTED_TRADE,
    EVENT_INGESTION_STATUS,
    EVENT_LOOT_GROUP,
    EVENT_MOB_TARGET_CHANGED,
    EVENT_ACTIVE_TOOL_CHANGED,
    EVENT_NOTIFICATION,
    EVENT_TRADE_REQUEST,
    EVENT_OCR_COMPLETE,
    EVENT_OCR_PAGE_CHANGED,
    EVENT_OCR_PROGRESS,
    EVENT_SKILL_GAIN,
    EVENT_SKILL_SCANNED,
    EVENT_SKILLS_UPLOADED,
    EVENT_SKILLS_UPLOAD_FAILED,
    EVENT_TRADE_CHAT,
    EVENT_HOTKEY_TRIGGERED,
    EVENT_UPDATE_AVAILABLE,
    EVENT_UPDATE_PROGRESS,
    EVENT_UPDATE_READY,
    EVENT_UPDATE_ERROR,
    EVENT_SCREENSHOT_SAVED,
    EVENT_CLIP_SAVED,
    EVENT_CAPTURE_ERROR,
    EVENT_OWN_GLOBAL,
)


class AppSignals(QObject):
    """Qt signals that bridge EventBus events to the main thread.

    Worker threads publish events via EventBus. This object re-emits them as
    Qt signals, which Qt marshals to the main thread automatically when
    connected to slots on widgets.
    """

    # Auth
    auth_state_changed = pyqtSignal(object)
    api_scope_error = pyqtSignal(object)

    # Chat parser
    skill_gain = pyqtSignal(object)
    combat_event = pyqtSignal(object)
    loot_group = pyqtSignal(object)
    enhancer_break = pyqtSignal(object)
    tier_increase = pyqtSignal(object)
    global_event = pyqtSignal(object)
    trade_chat = pyqtSignal(object)

    # OCR
    ocr_progress = pyqtSignal(object)
    ocr_complete = pyqtSignal(object)
    skill_scanned = pyqtSignal(object)
    ocr_page_changed = pyqtSignal(object)

    # Skills upload
    skills_uploaded = pyqtSignal(object)
    skills_upload_failed = pyqtSignal(object)

    # Hunt
    hunt_session_started = pyqtSignal(object)
    hunt_session_stopped = pyqtSignal(object)
    hunt_encounter_started = pyqtSignal(object)
    hunt_encounter_ended = pyqtSignal(object)
    hunt_session_updated = pyqtSignal(object)
    hunt_started = pyqtSignal(object)
    hunt_ended = pyqtSignal(object)
    hunt_split = pyqtSignal(object)
    session_auto_timeout = pyqtSignal(object)
    mob_target_changed = pyqtSignal(object)
    active_tool_changed = pyqtSignal(object)

    # Config
    config_changed = pyqtSignal(object)

    # Hotkeys
    hotkey_triggered = pyqtSignal(object)

    # Chat watcher lifecycle
    catchup_complete = pyqtSignal(object)
    catchup_progress = pyqtSignal(object)   # {"parsed": N, "total": N}

    # Historical import
    historical_import_progress = pyqtSignal(object)  # {"parsed_bytes", "total_bytes", "lines"}
    historical_import_complete = pyqtSignal(object)   # {"lines_parsed", "globals_found", "trades_found"}

    # News
    new_news_post = pyqtSignal(str, str)  # (title, summary)

    # Updates
    update_available = pyqtSignal(object)   # {"version", "download_size", "file_count"}
    update_progress = pyqtSignal(object)    # {"downloaded", "total", "current_file"}
    update_ready = pyqtSignal(object)       # {"version"}
    update_error = pyqtSignal(object)       # {"error"}

    # Notifications
    notification = pyqtSignal(object)  # Notification dataclass
    trade_request = pyqtSignal(object)  # New trade request dict

    # Ingestion (server-distributed data)
    ingested_global = pyqtSignal(object)   # dict from server
    ingested_trade = pyqtSignal(object)    # dict from server
    ingestion_status = pyqtSignal(object)  # {"pending": N}

    # Inventory
    inventory_open_wiki = pyqtSignal(int, str, str)  # (item_id, item_type, item_name)

    # Capture (screenshots / video clips)
    screenshot_saved = pyqtSignal(object)   # {"path": str, "timestamp": str}
    clip_saved = pyqtSignal(object)         # {"path": str, "duration": float}
    capture_error = pyqtSignal(object)      # {"error": str}
    own_global = pyqtSignal(object)         # GlobalEvent for own player

    # Open entity in detail overlay (dict with Name, Type)
    open_entity_overlay = pyqtSignal(dict)


def wire_signals(event_bus, signals: AppSignals) -> None:
    """Subscribe EventBus events to Qt signal emissions."""
    _WIRING = {
        EVENT_API_SCOPE_ERROR: signals.api_scope_error,
        EVENT_AUTH_STATE_CHANGED: signals.auth_state_changed,
        EVENT_SKILL_GAIN: signals.skill_gain,
        EVENT_COMBAT: signals.combat_event,
        EVENT_LOOT_GROUP: signals.loot_group,
        EVENT_ENHANCER_BREAK: signals.enhancer_break,
        EVENT_TIER_INCREASE: signals.tier_increase,
        EVENT_GLOBAL: signals.global_event,
        EVENT_TRADE_CHAT: signals.trade_chat,
        EVENT_OCR_PROGRESS: signals.ocr_progress,
        EVENT_OCR_COMPLETE: signals.ocr_complete,
        EVENT_SKILL_SCANNED: signals.skill_scanned,
        EVENT_OCR_PAGE_CHANGED: signals.ocr_page_changed,
        EVENT_SKILLS_UPLOADED: signals.skills_uploaded,
        EVENT_SKILLS_UPLOAD_FAILED: signals.skills_upload_failed,
        EVENT_HUNT_SESSION_STARTED: signals.hunt_session_started,
        EVENT_HUNT_SESSION_STOPPED: signals.hunt_session_stopped,
        EVENT_HUNT_ENCOUNTER_STARTED: signals.hunt_encounter_started,
        EVENT_HUNT_ENCOUNTER_ENDED: signals.hunt_encounter_ended,
        EVENT_HUNT_SESSION_UPDATED: signals.hunt_session_updated,
        EVENT_HUNT_STARTED: signals.hunt_started,
        EVENT_HUNT_ENDED: signals.hunt_ended,
        EVENT_HUNT_SPLIT: signals.hunt_split,
        EVENT_SESSION_AUTO_TIMEOUT: signals.session_auto_timeout,
        EVENT_MOB_TARGET_CHANGED: signals.mob_target_changed,
        EVENT_ACTIVE_TOOL_CHANGED: signals.active_tool_changed,
        EVENT_CONFIG_CHANGED: signals.config_changed,
        EVENT_HOTKEY_TRIGGERED: signals.hotkey_triggered,
        EVENT_CATCHUP_COMPLETE: signals.catchup_complete,
        EVENT_CATCHUP_PROGRESS: signals.catchup_progress,
        EVENT_UPDATE_AVAILABLE: signals.update_available,
        EVENT_UPDATE_PROGRESS: signals.update_progress,
        EVENT_UPDATE_READY: signals.update_ready,
        EVENT_UPDATE_ERROR: signals.update_error,
        EVENT_NOTIFICATION: signals.notification,
        EVENT_TRADE_REQUEST: signals.trade_request,
        EVENT_INGESTED_GLOBAL: signals.ingested_global,
        EVENT_INGESTED_TRADE: signals.ingested_trade,
        EVENT_INGESTION_STATUS: signals.ingestion_status,
        EVENT_HISTORICAL_IMPORT_PROGRESS: signals.historical_import_progress,
        EVENT_HISTORICAL_IMPORT_COMPLETE: signals.historical_import_complete,
        EVENT_SCREENSHOT_SAVED: signals.screenshot_saved,
        EVENT_CLIP_SAVED: signals.clip_saved,
        EVENT_CAPTURE_ERROR: signals.capture_error,
        EVENT_OWN_GLOBAL: signals.own_global,
    }

    for event_name, signal in _WIRING.items():
        event_bus.subscribe(event_name, lambda data, sig=signal: sig.emit(data))
