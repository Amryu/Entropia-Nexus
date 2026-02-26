"""Session loadout manager — snapshots loadouts per session for cost tracking."""

import json
from datetime import datetime
from pathlib import Path

from ..core.logger import get_logger
from .session import HuntSession, SessionLoadoutEntry
from .tool_inference import ToolInferenceEngine

log = get_logger("LoadoutManager")


class SessionLoadoutManager:
    """Manages loadout snapshots for hunt sessions.

    Responsibilities:
    - Evaluates loadouts using LoadoutCalculator (owns its own JS bridge)
    - Creates snapshots on session start
    - Handles copy-on-write logic (new snapshot on loadout change + combat)
    - Loads weapon signatures into ToolInferenceEngine
    - Tracks auto-detected unknown weapons
    """

    AUTO_DETECT_THRESHOLD = 3  # Unmatched shots before creating placeholder

    def __init__(self, config, db, data_client, tool_inference: ToolInferenceEngine):
        self._config = config
        self._db = db
        self._data_client = data_client
        self._tool_inference = tool_inference
        self._calculator = None          # Lazy-init LoadoutCalculator
        self._entity_data = None         # Lazy-loaded from DataClient
        self._active_loadout = None      # Latest from EVENT or cache
        self._active_stats = None        # LoadoutStats from evaluation
        self._session = None             # Current session reference
        self._combat_since_last_snapshot = False
        self._loot_since_last_snapshot = False

        # Auto-detect unknown weapons
        self._unmatched_damage_values: list[float] = []

    @property
    def active_loadout(self):
        return self._active_loadout

    @property
    def active_stats(self):
        return self._active_stats

    def _ensure_calculator(self):
        """Lazy-init calculator + entity data (heavy: V8 context + API calls)."""
        if self._calculator is None:
            from ..loadout.calculator import LoadoutCalculator
            self._calculator = LoadoutCalculator(self._config.js_utils_path or None)
        if self._entity_data is None:
            self._entity_data = {
                "weapons": self._data_client.get_weapons() or [],
                "amplifiers": self._data_client.get_amplifiers() or [],
                "scopes_sights": self._data_client.get_scopes_and_sights() or [],
                "absorbers": self._data_client.get_absorbers() or [],
                "implants": self._data_client.get_implants() or [],
                "armors": self._data_client.get_armors() or [],
                "armor_platings": self._data_client.get_armor_platings() or [],
                "medical_tools": self._data_client.get_medical_tools() or [],
            }

    def _evaluate(self, loadout: dict):
        """Evaluate a loadout. Returns (weapon_name, stats) or (None, None)."""
        self._ensure_calculator()
        weapon_name = (loadout.get("Gear", {}).get("Weapon", {}).get("Name") or "").strip()
        if not weapon_name:
            return None, None
        try:
            stats = self._calculator.evaluate(loadout, self._entity_data)
            return weapon_name, stats
        except Exception as e:
            log.error("Loadout evaluation failed: %s", e)
            return weapon_name, None

    def load_active_loadout(self):
        """Load and cache active loadout from local file cache (no UI needed)."""
        loadout_id = self._config.active_loadout_id
        if not loadout_id:
            return
        cache_path = Path("data/cache/loadouts.json")
        if not cache_path.exists():
            return
        try:
            loadouts = json.loads(cache_path.read_text(encoding="utf-8"))
            for lo in loadouts:
                if lo.get("Id") == loadout_id:
                    self._active_loadout = lo
                    weapon_name, stats = self._evaluate(lo)
                    if stats:
                        self._active_stats = stats
                        self._tool_inference.load_from_loadout_stats(weapon_name, stats)
                    return
        except Exception as e:
            log.error("Failed to load active loadout: %s", e)

    def on_active_loadout_changed(self, loadout: dict, weapon_name: str | None, stats):
        """Called when loadout page publishes EVENT_ACTIVE_LOADOUT_CHANGED."""
        self._active_loadout = loadout
        self._active_stats = stats
        if weapon_name and stats:
            self._tool_inference.load_from_loadout_stats(weapon_name, stats)
        # If session active, check if new snapshot needed
        if self._session:
            self._maybe_create_snapshot("external_update")

    def start_session(self, session: HuntSession):
        """Create initial snapshot for a new session."""
        self._session = session
        self._combat_since_last_snapshot = False
        self._loot_since_last_snapshot = False
        self._unmatched_damage_values.clear()
        if not self._active_loadout:
            self.load_active_loadout()  # Try loading from cache
        if self._active_loadout:
            self._create_snapshot("snapshot")

    def end_session(self):
        """Clear session state."""
        self._session = None
        self._combat_since_last_snapshot = False
        self._loot_since_last_snapshot = False
        self._unmatched_damage_values.clear()

    def restore_session(self, session: HuntSession):
        """Restore session state from DB data (after restart).

        Loads weapon signatures from the latest loadout entry so cost
        tracking resumes immediately.
        """
        self._session = session
        self._combat_since_last_snapshot = False
        self._loot_since_last_snapshot = False
        self._unmatched_damage_values.clear()

        # Load weapon signatures from the latest loadout entry
        if session.loadout_entries:
            latest = session.loadout_entries[-1]
            if latest.weapon_name and latest.damage_min > 0:
                self._tool_inference.load_signature(
                    latest.weapon_name,
                    latest.damage_min,
                    latest.damage_max,
                    (latest.damage_min + latest.damage_max) / 2,
                    latest.cost_per_shot,
                )
            if latest.loadout_data:
                self._active_loadout = latest.loadout_data
        log.info("Loadout manager restored for session %s", session.id)

    def on_combat(self):
        """Mark that combat happened since last snapshot."""
        self._combat_since_last_snapshot = True

    def on_loot(self):
        """Mark that loot was received — seals the current snapshot."""
        self._loot_since_last_snapshot = True

    def on_unmatched_damage(self, damage: float):
        """Track damage values that didn't match any known weapon signature.

        After AUTO_DETECT_THRESHOLD unmatched shots, creates a placeholder
        session loadout entry for the unknown weapon.
        """
        if not self._session or damage <= 0:
            return
        self._unmatched_damage_values.append(damage)
        if len(self._unmatched_damage_values) >= self.AUTO_DETECT_THRESHOLD:
            self._create_auto_detected_entry()

    def _maybe_create_snapshot(self, source: str):
        """Create new snapshot if conditions met (combat or loot since last)."""
        if not self._session or not self._active_loadout:
            return
        if self._combat_since_last_snapshot or self._loot_since_last_snapshot:
            self._create_snapshot(source)

    def _create_snapshot(self, source: str):
        """Create and persist a loadout snapshot."""
        if not self._session:
            return
        weapon_name, stats = self._evaluate(self._active_loadout) if self._active_loadout else (None, None)
        if stats:
            self._tool_inference.load_from_loadout_stats(weapon_name, stats)
        entry = SessionLoadoutEntry(
            session_id=self._session.id,
            loadout_data=self._active_loadout or {},
            weapon_name=weapon_name,
            cost_per_shot=stats.cost if stats else 0,
            damage_min=stats.damage_interval_min if stats else 0,
            damage_max=stats.damage_interval_max if stats else 0,
            source=source,
        )
        entry.id = self._db.insert_session_loadout(
            self._session.id, entry.timestamp.isoformat(),
            json.dumps(entry.loadout_data), weapon_name,
            entry.cost_per_shot, entry.damage_min, entry.damage_max, source,
        )
        self._session.loadout_entries.append(entry)
        self._combat_since_last_snapshot = False
        self._loot_since_last_snapshot = False
        log.info("Loadout snapshot created: weapon=%s cost/shot=%.4f source=%s",
                 weapon_name, entry.cost_per_shot, source)

    def _create_auto_detected_entry(self):
        """Create a placeholder entry for an unknown weapon from observed damage."""
        if not self._session or not self._unmatched_damage_values:
            return
        damage_min = min(self._unmatched_damage_values)
        damage_max = max(self._unmatched_damage_values)
        now = datetime.utcnow()

        entry = SessionLoadoutEntry(
            session_id=self._session.id,
            timestamp=now,
            loadout_data={},
            weapon_name="Unknown weapon",
            cost_per_shot=0.0,
            damage_min=damage_min,
            damage_max=damage_max,
            source="auto_detected",
        )
        entry.id = self._db.insert_session_loadout(
            self._session.id, now.isoformat(),
            "{}", "Unknown weapon",
            0.0, damage_min, damage_max, "auto_detected",
        )
        self._session.loadout_entries.append(entry)
        self._unmatched_damage_values.clear()
        log.info("Auto-detected unknown weapon: damage range %.1f - %.1f",
                 damage_min, damage_max)
