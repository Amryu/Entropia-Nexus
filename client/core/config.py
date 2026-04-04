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
    ocr_capture_backend: str = "auto"  # auto | bitblt | printwindow | wgc
    capture_backend_choice_made: bool = False  # one-time capture backend dialog
    hdr_compatibility_mode: bool = False  # CLAHE tone correction for HDR displays
    ocr_auto_scan_enabled: bool = True
    scan_overlay_debug: bool = False
    scan_roi_overrides: dict = field(default_factory=dict)  # {name: [x,y,w,h]} pixel offsets from SKILLS template
    scan_roi_version: int = 0  # Tracks DEFAULT_ROI_PIXELS version; reset overrides when outdated
    ocr_trace_enabled: bool = False
    radar_enabled: bool = False
    radar_last_circle: list | None = None  # [cx, cy, r] persisted calibration
    radar_digit_stpk: str = "radar_digits.stpk"
    radar_origin_offset: tuple[int, int] | None = None          # (dx, dy) circle-center → HUD origin at 1x
    radar_lon_roi: tuple[int, int, int, int] | None = None      # (x, y, w, h) from origin at 1x
    radar_lat_roi: tuple[int, int, int, int] | None = None      # (x, y, w, h) from origin at 1x

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
    recording_bar_overlay_position: tuple[int, int] = (50, 150)
    recording_bar_setup_shown: bool = False
    gallery_overlay_position: tuple[int, int] = (100, 100)
    gallery_overlay_size: tuple[int, int] = (350, 500)
    map_overlay_size: int = 1  # 0=Small, 1=Medium, 2=Large
    stream_overlay_position: tuple[int, int] = (100, 100)
    stream_overlay_size_preset: int = 1  # 0=Small, 1=Medium, 2=Large
    stream_overlay_chat_visible: bool = True
    stream_overlay_volume: int = 80
    stream_custom_streamers: list[str] = field(default_factory=list)
    overlay_opacity: float = 0.85
    overlay_enabled: bool = True
    auto_pin_detail_overlay: bool = False

    # Custom grid overlays (multiple named grids)
    # Each entry: {"id": str, "name": str, "position": [x, y], "cols": int,
    #              "rows": int, "tile_size": int, "widgets": list}
    custom_grids: list = field(default_factory=list)

    # Auth
    nexus_base_url: str = "https://entropianexus.com"
    api_base_url: str = "https://api.entropianexus.com"
    oauth_client_id: str = ""
    oauth_redirect_port: int = 47832

    # Hunt tracking
    encounter_close_timeout_ms: int = 180000       # 3 min — wait for loot after last combat event
    loot_close_timeout_ms: int = 3000            # faster timeout after loot received
    max_encounter_duration_ms: int = 600000      # 10 min hard cap — prevents stuck encounters
    attribution_window_ms: int = 3000
    session_auto_timeout_ms: int = 3600000       # 1 hour
    hunt_split_mob_threshold: int = 10           # consecutive kills before confirming mob-type split
    hunt_split_min_remote_kills: int = 5         # kills at new location before confirming split

    # Open encounter auto-merge: auto-merge successive deaths to same mob
    auto_merge_deaths: bool = False

    # Reload-based tool correlation
    reload_correlation_window_ms: int = 500   # max ms between damage event and reload drop
    reload_correlation_enabled: bool = True

    # Tool cost filter — controls which tools contribute to hunt cost
    # "blacklist": include all except listed; "whitelist": include only listed
    tool_cost_filter_mode: str = "blacklist"
    tool_cost_filter_list: list[str] = field(default_factory=list)

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
    hotkey_radar_recalibrate: str = "home"
    hotkey_recording_bar: str = "ctrl+r"
    hotkey_gallery: str = "ctrl+g"

    # UI
    main_window_screen_center: list | None = None
    active_loadout_id: str | None = None
    overamp_mode: str = "percent"  # 'percent' or 'delta'
    mob_maturity_loadout_id: str | None = None

    # Wiki
    wiki_column_prefs: dict = field(default_factory=dict)

    # Inventory
    inventory_prefs: dict = field(default_factory=dict)

    # Loadout JS bridge
    js_utils_path: str = ""

    # Legal
    tos_accepted_version: str = ""

    # Startup
    start_on_boot: bool = False
    start_minimized: bool = False

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
    twitch_client_id: str = ""

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
    target_lock_enabled: bool = False
    target_lock_match_threshold: float = 0.90
    target_lock_roi_hp: dict = field(default_factory=lambda: {"dx": -89, "dy": -17, "w": 193, "h": 6})
    target_lock_roi_shared: dict = field(default_factory=lambda: {"dx": -125, "dy": -22, "w": 16, "h": 16})
    target_lock_roi_name: dict = field(default_factory=lambda: {"dx": -190, "dy": -40, "w": 394, "h": 14})
    target_lock_name_min_confidence: float = 0.3   # ONNX min confidence for mob name
    target_lock_name_debounce: int = 2             # consecutive frames before accepting name change

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
    market_clipboard_enabled: bool = True  # monitor clipboard for copied market data

    # Player status (heart) detection
    player_status_enabled: bool = False
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

    # Character name (fallback for own-global detection when not logged in)
    character_name: str = ""

    # Screenshots
    screenshot_enabled: bool = True
    screenshot_auto_on_global: bool = True
    screenshot_delay_s: float = 1.0
    screenshot_directory: str = ""          # empty = ~/Pictures/Entropia Nexus Screenshots
    screenshot_daily_subfolder: bool = True
    screenshot_size_pct: int = 100          # 25, 50, 75, or 100 (% of source resolution)
    hotkey_screenshot: str = "f12"

    # Auto-screenshot conditions (checked when own global detected)
    screenshot_min_ped: float = 0.0                 # 0 = no minimum
    screenshot_global_types: list[str] = field(      # empty = all types
        default_factory=list)
    screenshot_hof_only: bool = False
    screenshot_cooldown_s: float = 0.0              # 0 = no cooldown
    screenshot_sound_enabled: bool = True           # play shutter sound on screenshot

    # Video capture (master gate for all capture infrastructure)
    capture_enabled: bool = False           # gates frame subscription, audio, webcam, OBS, recording

    # Video clips (sub-gate: clipping button, hotkey, replay buffer, auto-clip)
    clip_enabled: bool = False              # off by default (needs FFmpeg + resources)
    clip_auto_on_global: bool = True
    clip_buffer_seconds: int = 15
    clip_post_global_seconds: float = 5.0

    # Auto-clip conditions (checked when own global detected)
    clip_min_ped: float = 0.0                       # 0 = no minimum
    clip_global_types: list[str] = field(            # empty = all types
        default_factory=list)
    clip_hof_only: bool = False
    clip_cooldown_s: float = 0.0                    # 0 = no cooldown
    clip_sound_enabled: bool = True                 # play chime on clip/recording save
    clip_directory: str = ""                # empty = ~/Videos/Entropia Nexus Clips
    clip_daily_subfolder: bool = True
    clip_capture_backend: str = "auto"      # auto | bitblt | wgc
    clip_fps: int = 30
    clip_resolution: str = "source"         # source | 1080p | 720p | 480p
    clip_bitrate: str = "medium"            # low | medium | high | ultra
    clip_scaling: str = "cubic"             # lanczos | linear | cubic | area | nearest
    clip_encode_priority: str = "below_normal"  # normal | below_normal | idle
    clip_encode_threads: int = 0               # 0 = auto (1/4 of CPU cores)
    clip_encode_first: bool = True             # encode-first pipeline (instant clip saves)
    clip_video_encoder: str = "libx264"        # libx264 | h264_nvenc | hevc_nvenc | h264_amf | h264_qsv | ...
    hotkey_save_clip: str = "ctrl+shift+space"
    hotkey_toggle_recording: str = "ctrl+shift+r"
    ffmpeg_path: str = ""                   # manual override for FFmpeg binary

    # Audio — Game/system audio (for video clips)
    clip_audio_enabled: bool = False
    clip_audio_process_capture: bool = True  # capture game audio only (Win10 2004+)
    clip_audio_device: str = ""             # empty = system default loopback
    clip_audio_game_gain: float = 1.0       # 0.0 to 3.0 (1.0 = unity)
    clip_audio_noise_suppression: bool = True
    clip_audio_noise_gate: bool = True
    clip_audio_compressor: bool = True

    # Audio filter parameters — Noise Suppression (arnndn / RNNoise)
    clip_audio_ns_mix: float = 1.0                  # 0.0 = bypass, 1.0 = fully denoised

    # Audio filter parameters — Noise Gate (agate)
    clip_audio_gate_threshold: float = 0.01
    clip_audio_gate_ratio: float = 2.0
    clip_audio_gate_attack: float = 10.0            # ms
    clip_audio_gate_release: float = 100.0          # ms

    # Audio filter parameters — Compressor (acompressor)
    clip_audio_comp_threshold: float = -20.0        # dB
    clip_audio_comp_ratio: float = 4.0
    clip_audio_comp_attack: float = 5.0             # ms
    clip_audio_comp_release: float = 100.0          # ms

    # Audio — Microphone
    clip_mic_enabled: bool = False
    clip_mic_device: str = ""               # empty = system default
    clip_audio_mic_gain: float = 1.0        # 0.0 to 3.0

    # Webcam (for video clips)
    clip_webcam_enabled: bool = False
    clip_webcam_device: int = 0
    clip_webcam_fps: int = 0               # webcam capture FPS (0 = match output)
    clip_webcam_keep_ready: bool = False   # keep webcam open (claimed) even when not recording
    clip_webcam_scale: float = 0.2          # webcam size as fraction of frame width
    clip_webcam_position_x: float = 0.88    # normalized center X (0.0-1.0)
    clip_webcam_position_y: float = 0.85    # normalized center Y (0.0-1.0)

    # Webcam crop (normalized 0.0-1.0 within the webcam frame)
    clip_webcam_crop_x: float = 0.0
    clip_webcam_crop_y: float = 0.0
    clip_webcam_crop_w: float = 1.0         # 1.0 = full width (no crop)
    clip_webcam_crop_h: float = 1.0         # 1.0 = full height (no crop)

    # Webcam chroma key (green screen removal)
    clip_webcam_chroma_enabled: bool = False
    clip_webcam_chroma_color: str = "#00ff00"   # hex color to key out
    clip_webcam_chroma_threshold: int = 40      # color distance threshold (0-255)
    clip_webcam_chroma_smoothing: int = 5       # edge smoothing kernel size

    # OBS Studio integration (delegates capture/encoding to OBS)
    obs_enabled: bool = False               # use OBS instead of internal capture
    obs_host: str = "localhost"             # obs-websocket host
    obs_port: int = 4455                    # obs-websocket port (default for OBS 28+)
    obs_manage_replay_buffer: bool = False  # auto start/stop replay buffer with EU client
    obs_replay_buffer_asked: bool = False  # whether the user was asked about replay management

    # Blur/privacy regions for captures
    capture_blur_regions: list[dict] = field(default_factory=list)  # [{x, y, w, h}] normalized 0.0-1.0

    # Blur dialog background image/video (stretched to fill when no game frame)
    capture_preview_background: str = ""    # path to image or video file


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
    "capture_backend_choice_made": False,
    "hdr_compatibility_mode": False,
    "ocr_auto_scan_enabled": True,
    "ocr_trace_enabled": False,
    "radar_enabled": False,
    "radar_last_circle": None,
    "radar_digit_stpk": "radar_digits.stpk",
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
    "recording_bar_overlay_position": [50, 150],
    "recording_bar_setup_shown": False,
    "gallery_overlay_position": [100, 100],
    "gallery_overlay_size": [350, 500],
    "map_overlay_position": [100, 100],
    "scan_summary_overlay_position": [100, 200],
    "confirm_overlay_position": [100, 200],
    "profile_overlay_position": [450, 50],
    "society_overlay_position": [450, 50],
    "map_overlay_size": 1,
    "stream_overlay_position": [100, 100],
    "stream_overlay_size_preset": 1,
    "stream_overlay_chat_visible": True,
    "stream_overlay_volume": 80,
    "stream_custom_streamers": [],
    "overlay_opacity": 0.85,
    "overlay_enabled": True,
    "auto_pin_detail_overlay": False,
    "custom_grids": [],
    "nexus_base_url": "https://entropianexus.com",
    "api_base_url": "https://api.entropianexus.com",
    "oauth_client_id": "",
    "oauth_redirect_port": 47832,
    "encounter_close_timeout_ms": 180000,
    "loot_close_timeout_ms": 3000,
    "max_encounter_duration_ms": 600000,
    "attribution_window_ms": 3000,
    "session_auto_timeout_ms": 3600000,
    "hunt_split_mob_threshold": 10,
    "hunt_split_min_remote_kills": 5,
    "auto_merge_deaths": False,
    "reload_correlation_window_ms": 500,
    "reload_correlation_enabled": True,
    "tool_cost_filter_mode": "blacklist",
    "tool_cost_filter_list": [],
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
    "hotkey_radar_recalibrate": "home",
    "hotkey_recording_bar": "ctrl+r",
    "hotkey_gallery": "ctrl+g",
    "main_window_screen_center": None,
    "active_loadout_id": None,
    "overamp_mode": "percent",
    "mob_maturity_loadout_id": None,
    "wiki_column_prefs": {},
    "inventory_prefs": {},
    "js_utils_path": "",
    "tos_accepted_version": "",
    "start_on_boot": False,
    "start_minimized": False,
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
    "twitch_client_id": "",
    "tracker_missions": [],
    "tracker_event_reminders": [],
    "dashboard_globals_min_value": 0.0,
    "dashboard_globals_blocked_types": [],
    "dashboard_trade_blocklist": [],
    "dashboard_trade_planet_filter": [],
    "dashboard_trade_blacklist": [],
    "target_lock_enabled": False,
    "target_lock_match_threshold": 0.90,
    "target_lock_roi_hp": {"dx": -89, "dy": -17, "w": 193, "h": 6},
    "target_lock_roi_shared": {"dx": -125, "dy": -22, "w": 16, "h": 16},
    "target_lock_roi_name": {"dx": -190, "dy": -40, "w": 394, "h": 14},
    "target_lock_name_min_confidence": 0.3,
    "target_lock_name_debounce": 2,
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
    "market_clipboard_enabled": True,
    "player_status_enabled": False,
    "player_status_match_threshold": 0.90,
    "player_status_roi_health": {"dx": 30, "dy": -9, "w": 315, "h": 12},
    "player_status_roi_reload": {"dx": 30, "dy": 5, "w": 315, "h": 3},
    "player_status_roi_buff": {"dx": -7, "dy": -57, "w": 459, "h": 32},
    "player_status_roi_buff_small": {"dx": 0, "dy": 0, "w": 1, "h": 1},
    "player_status_roi_tool_name": {"dx": 30, "dy": 13, "w": 315, "h": 14},
    "ingestion_enabled": True,
    "ingestion_upload_interval_seconds": 30,
    "ingestion_receive_interval_seconds": 60,
    "character_name": "",
    "screenshot_enabled": True,
    "screenshot_auto_on_global": True,
    "screenshot_delay_s": 1.0,
    "screenshot_directory": "",
    "screenshot_daily_subfolder": True,
    "hotkey_screenshot": "f12",
    "screenshot_min_ped": 0.0,
    "screenshot_global_types": [],
    "screenshot_hof_only": False,
    "screenshot_cooldown_s": 0.0,
    "screenshot_size_pct": 100,
    "screenshot_sound_enabled": True,
    "capture_enabled": False,
    "clip_enabled": False,
    "clip_auto_on_global": True,
    "clip_buffer_seconds": 15,
    "clip_post_global_seconds": 5.0,
    "clip_min_ped": 0.0,
    "clip_global_types": [],
    "clip_hof_only": False,
    "clip_cooldown_s": 0.0,
    "clip_sound_enabled": True,
    "clip_directory": "",
    "clip_daily_subfolder": True,
    "clip_capture_backend": "auto",
    "clip_fps": 30,
    "clip_resolution": "source",
    "clip_bitrate": "medium",
    "clip_scaling": "cubic",
    "clip_encode_priority": "below_normal",
    "clip_encode_threads": 0,
    "clip_encode_first": True,
    "clip_video_encoder": "libx264",
    "hotkey_save_clip": "ctrl+shift+space",
    "hotkey_toggle_recording": "ctrl+shift+r",
    "ffmpeg_path": "",
    "clip_audio_enabled": False,
    "clip_audio_process_capture": True,
    "clip_audio_device": "",
    "clip_audio_game_gain": 1.0,
    "clip_audio_noise_suppression": True,
    "clip_audio_noise_gate": True,
    "clip_audio_compressor": True,
    "clip_audio_ns_mix": 1.0,
    "clip_audio_gate_threshold": 0.01,
    "clip_audio_gate_ratio": 2.0,
    "clip_audio_gate_attack": 10.0,
    "clip_audio_gate_release": 100.0,
    "clip_audio_comp_threshold": -20.0,
    "clip_audio_comp_ratio": 4.0,
    "clip_audio_comp_attack": 5.0,
    "clip_audio_comp_release": 100.0,
    "clip_mic_enabled": False,
    "clip_mic_device": "",
    "clip_audio_mic_gain": 1.0,
    "clip_webcam_enabled": False,
    "clip_webcam_device": 0,
    "clip_webcam_fps": 0,
    "clip_webcam_keep_ready": False,
    "clip_webcam_scale": 0.2,
    "clip_webcam_position_x": 0.88,
    "clip_webcam_position_y": 0.85,
    "clip_webcam_crop_x": 0.0,
    "clip_webcam_crop_y": 0.0,
    "clip_webcam_crop_w": 1.0,
    "clip_webcam_crop_h": 1.0,
    "clip_webcam_chroma_enabled": False,
    "clip_webcam_chroma_color": "#00ff00",
    "clip_webcam_chroma_threshold": 40,
    "clip_webcam_chroma_smoothing": 5,
    "capture_blur_regions": [],
    "capture_preview_background": "",
    "obs_enabled": False,
    "obs_host": "localhost",
    "obs_port": 4455,
    "obs_manage_replay_buffer": False,
    "obs_replay_buffer_asked": False,
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

    # Migrate clip_webcam_position (corner enum) → clip_webcam_position_x/y
    if "clip_webcam_position" in user_config and "clip_webcam_position_x" not in user_config:
        _pos_map = {
            "top_left": (0.12, 0.15),
            "top_right": (0.88, 0.15),
            "bottom_left": (0.12, 0.85),
            "bottom_right": (0.88, 0.85),
        }
        old_pos = user_config["clip_webcam_position"]
        px, py = _pos_map.get(old_pos, (0.88, 0.85))
        merged["clip_webcam_position_x"] = px
        merged["clip_webcam_position_y"] = py
    merged.pop("clip_webcam_position", None)

    # Migrate clip_audio_ns_level (afftdn) → clip_audio_ns_mix (arnndn)
    if "clip_audio_ns_level" in user_config and "clip_audio_ns_mix" not in user_config:
        merged["clip_audio_ns_mix"] = 1.0  # arnndn default (fully denoised)
    merged.pop("clip_audio_ns_level", None)

    # Reset stale ROI overrides when defaults change
    if merged.get("scan_roi_version", 0) < SCAN_ROI_VERSION:
        merged["scan_roi_overrides"] = {}
        merged["scan_roi_version"] = SCAN_ROI_VERSION

    # Migrate flat custom_grid_overlay_* → custom_grids list
    if "custom_grid_overlay_widgets" in user_config and "custom_grids" not in user_config:
        old_pos = user_config.get("custom_grid_overlay_position", [200, 200])
        entry = {
            "id": "default",
            "name": "Custom Grid",
            "position": list(old_pos) if isinstance(old_pos, (list, tuple)) else [200, 200],
            "cols": user_config.get("custom_grid_overlay_cols", 12),
            "rows": user_config.get("custom_grid_overlay_rows", 12),
            "tile_size": user_config.get("custom_grid_overlay_tile_size", 0),
            "widgets": user_config.get("custom_grid_overlay_widgets", []),
        }
        merged["custom_grids"] = [entry]
    for _old_key in (
        "custom_grid_overlay_position", "custom_grid_overlay_cols",
        "custom_grid_overlay_rows", "custom_grid_overlay_tile_size",
        "custom_grid_overlay_widgets",
        "market_price_review_enabled",
        "market_price_review_tutorial_shown",
    ):
        merged.pop(_old_key, None)

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
        "recording_bar_overlay_position", "gallery_overlay_position",
        "gallery_overlay_size", "stream_overlay_position",
        "mob_name_region", "tool_name_region",
        "radar_origin_offset", "radar_lon_roi", "radar_lat_roi",
    ):
        val = merged.get(key)
        if isinstance(val, list):
            merged[key] = tuple(val)

    # Expand ~ in paths
    for key in ("chat_log_path", "database_path", "js_utils_path",
                "screenshot_directory", "clip_directory", "ffmpeg_path"):
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

    _valid_backends = {"auto", "bitblt", "printwindow", "wgc"}
    if config.ocr_capture_backend not in _valid_backends:
        errors.append(
            "ocr_capture_backend must be one of: auto, bitblt, printwindow, wgc "
            f"(got {config.ocr_capture_backend})",
        )
    _valid_clip_backends = {"auto", "bitblt", "wgc"}
    if config.clip_capture_backend not in _valid_clip_backends:
        errors.append(
            "clip_capture_backend must be one of: auto, bitblt, wgc "
            f"(got {config.clip_capture_backend})",
        )
    _valid_scaling = {"lanczos", "linear", "cubic", "area", "nearest"}
    if getattr(config, "clip_scaling", "lanczos") not in _valid_scaling:
        errors.append(
            f"clip_scaling must be one of: {', '.join(sorted(_valid_scaling))} "
            f"(got {config.clip_scaling})",
        )

    return errors
