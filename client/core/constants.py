import re

# Event names — Chat parser
EVENT_SKILL_GAIN = "skill_gain"
EVENT_COMBAT = "combat"
EVENT_LOOT_GROUP = "loot_group"
EVENT_ENHANCER_BREAK = "enhancer_break"
EVENT_TIER_INCREASE = "tier_increase"
EVENT_GLOBAL = "global"
EVENT_TRADE_CHAT = "trade_chat"
EVENT_PARSER_ERROR = "parser_error"

# Event names — OCR
EVENT_OCR_PROGRESS = "ocr_progress"
EVENT_OCR_COMPLETE = "ocr_complete"

# Event names — Auth
EVENT_AUTH_STATE_CHANGED = "auth_state_changed"

# Event names — Hunt tracking
EVENT_HUNT_SESSION_STARTED = "hunt_session_started"
EVENT_HUNT_SESSION_STOPPED = "hunt_session_stopped"
EVENT_HUNT_ENCOUNTER_STARTED = "hunt_encounter_started"
EVENT_HUNT_ENCOUNTER_ENDED = "hunt_encounter_ended"
EVENT_HUNT_SESSION_UPDATED = "hunt_session_updated"
EVENT_MOB_TARGET_CHANGED = "mob_target_changed"
EVENT_ACTIVE_TOOL_CHANGED = "active_tool_changed"
EVENT_HUNT_STARTED = "hunt_started"
EVENT_HUNT_ENDED = "hunt_ended"
EVENT_HUNT_UPDATED = "hunt_updated"
EVENT_HUNT_SPLIT = "hunt_split"
EVENT_HUNT_MERGED = "hunt_merged"
EVENT_HUNT_END_REQUESTED = "hunt_end_requested"
EVENT_SESSION_AUTO_TIMEOUT = "session_auto_timeout"
EVENT_LOOT_BLACKLIST_CHANGED = "loot_blacklist_changed"
EVENT_ACTIVE_LOADOUT_CHANGED = "active_loadout_changed"
EVENT_SESSION_LOADOUT_UPDATED = "session_loadout_updated"
EVENT_PLAYER_DEATH = "player_death"
EVENT_PLAYER_REVIVED = "player_revived"
EVENT_OPEN_ENCOUNTER_UPDATED = "open_encounter_updated"

# Event names — Skills upload
EVENT_SKILLS_UPLOADED = "skills_uploaded"
EVENT_SKILLS_UPLOAD_FAILED = "skills_upload_failed"

# Event names — Config / Hotkeys
EVENT_CONFIG_CHANGED = "config_changed"
EVENT_HOTKEY_TRIGGERED = "hotkey_triggered"
EVENT_CATCHUP_COMPLETE = "catchup_complete"

# Debug events
EVENT_DEBUG_REGIONS = "debug_regions"      # Window/sidebar/table/pagination bounds
EVENT_DEBUG_ROW = "debug_row"              # Individual row OCR result

# Overlay coordination events (OCR <-> overlays)
EVENT_OCR_OVERLAYS_HIDE = "ocr_overlays_hide"   # data: callable (call when hidden)
EVENT_OCR_OVERLAYS_SHOW = "ocr_overlays_show"    # data: None
EVENT_OCR_PAGE_CHANGED = "ocr_page_changed"      # data: None (clear checkmarks)

# Chat log line format
LINE_PATTERN = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) '
    r'\[([^\]]*)\] '
    r'\[([^\]]*)\] '
    r'(.*)$'
)

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# HTML entities in chat log
HTML_ENTITIES = {
    "&quot;": '"',
    "&apos;": "'",
    "&#91;": "[",
    "&amp;": "&",
    "&gt;": ">",
    "&lt;": "<",
}

# Skill gain patterns
SKILL_EXP_PATTERN = re.compile(
    r'^You have gained ([\d.]+) experience in your (.+) skill$'
)
SKILL_DIRECT_PATTERN = re.compile(
    r'^You have gained ([\d.]+) ([A-Z][\w ]+)$'
)

# Combat patterns (order matters: crit before regular damage)
COMBAT_CRIT_PATTERN = re.compile(
    r'^Critical hit - Additional damage! You inflicted ([\d.]+) points of damage$'
)
COMBAT_DAMAGE_DEALT_PATTERN = re.compile(
    r'^You inflicted ([\d.]+) points of damage$'
)
COMBAT_DAMAGE_RECEIVED_PATTERN = re.compile(
    r'^You took ([\d.]+) points of damage$'
)
COMBAT_SELF_HEAL_PATTERN = re.compile(
    r'^You healed yourself ([\d.]+) points$'
)
COMBAT_DEFLECT_PATTERN = re.compile(r'^Damage deflected!$')
COMBAT_PLAYER_EVADE_PATTERN = re.compile(r'^You Evaded the attack$')
COMBAT_PLAYER_DODGE_PATTERN = re.compile(r'^You Dodged the attack$')
COMBAT_PLAYER_JAM_PATTERN = re.compile(r'^You Jammed the attack$')
COMBAT_MOB_MISS_PATTERN = re.compile(r'^The attack missed you$')
COMBAT_TARGET_JAM_PATTERN = re.compile(r'^The target Jammed your attack$')
COMBAT_TARGET_DODGE_PATTERN = re.compile(r'^The target Dodged your attack$')
COMBAT_TARGET_EVADE_PATTERN = re.compile(r'^The target Evaded your attack$')

# Tier increase pattern
TIER_INCREASE_PATTERN = re.compile(
    r'^Your (.+?) has reached tier ([\d.]+)$'
)

# Enhancer break pattern
ENHANCER_BREAK_PATTERN = re.compile(
    r'^Your enhancer (.+?) on your (.+?) broke\. '
    r'You have (\d+) enhancers remaining on the item\. '
    r'You received ([\d.]+) PED Shrapnel\.\s*$'
)

# Loot pattern
LOOT_PATTERN = re.compile(
    r'^You received (.+?) x \((\d+)\) Value: ([\d.]+) PED$'
)

# Global patterns (check team kill before regular kill)
# Kill/team patterns don't include '!' since location may come between PED and !
GLOBAL_TEAM_KILL_PATTERN = re.compile(
    r'^Team "(.+?)" killed a creature \((.+?)\) with a value of ([\d.]+) PED'
)
GLOBAL_KILL_PATTERN = re.compile(
    r'^(.+?) killed a creature \((.+?)\) with a value of ([\d.]+) PED'
)
GLOBAL_DEPOSIT_PATTERN = re.compile(
    r'^(.+?) found a deposit \((.+?)\) with a value of ([\d.]+) PED'
)
GLOBAL_CRAFT_PATTERN = re.compile(
    r'^(.+?) constructed an item \((.+?)\) worth ([\d.]+) PED!'
)
GLOBAL_RARE_PATTERN = re.compile(
    r'^(.+?) has found a rare item \((.+?)\) with a value of ([\d.]+) (PED|PEC)!'
)

GLOBAL_HOF_SUFFIX = "A record has been added to the Hall of Fame"
GLOBAL_ATH_KEYWORD = "ALL TIME HIGH"

# Death / revival patterns
DEATH_PATTERN = re.compile(r'^You were killed by the \w+ (.+)$')
REVIVAL_PATTERN = re.compile(r'^You have been revived$')

# Trade channel detection
TRADE_CHANNEL_PATTERN = re.compile(r'trade|trading', re.IGNORECASE)

# Default chat.log path
DEFAULT_CHAT_LOG_PATH = "~/Documents/Entropia Universe/chat.log"
