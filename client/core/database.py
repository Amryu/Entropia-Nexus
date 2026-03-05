import os
import sqlite3
import threading
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS skill_gains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    amount REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS combat_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    amount REAL,
    session_id TEXT
);

CREATE TABLE IF NOT EXISTS loot_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    total_value_ped REAL NOT NULL,
    session_id TEXT
);

CREATE TABLE IF NOT EXISTS loot_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES loot_groups(id),
    item_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    value_ped REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS enhancer_breaks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    enhancer_name TEXT NOT NULL,
    item_name TEXT NOT NULL,
    remaining INTEGER NOT NULL,
    shrapnel_ped REAL NOT NULL,
    session_id TEXT
);

CREATE TABLE IF NOT EXISTS globals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    global_type TEXT NOT NULL,
    player_name TEXT NOT NULL,
    target_name TEXT NOT NULL,
    value REAL NOT NULL,
    value_unit TEXT NOT NULL,
    location TEXT,
    is_hof INTEGER NOT NULL,
    is_ath INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    channel TEXT NOT NULL,
    username TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_timestamp TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    rank TEXT NOT NULL,
    current_points REAL NOT NULL,
    progress_percent REAL NOT NULL,
    category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parser_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    file_path TEXT NOT NULL,
    byte_offset INTEGER NOT NULL,
    last_line_number INTEGER NOT NULL,
    last_timestamp TEXT,
    file_hash TEXT
);

CREATE TABLE IF NOT EXISTS pending_ingestion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    data TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_combat_events_timestamp ON combat_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_loot_groups_timestamp ON loot_groups(timestamp);
CREATE INDEX IF NOT EXISTS idx_globals_timestamp ON globals(timestamp);
CREATE INDEX IF NOT EXISTS idx_skill_snapshots_timestamp ON skill_snapshots(scan_timestamp);
CREATE INDEX IF NOT EXISTS idx_skill_snapshots_name ON skill_snapshots(skill_name);

CREATE TABLE IF NOT EXISTS hunt_sessions (
    id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT,
    loadout_id TEXT,
    primary_mob TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS hunts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES hunt_sessions(id),
    start_time TEXT NOT NULL,
    end_time TEXT,
    primary_mob TEXT,
    location_label TEXT,
    total_cost REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS mob_encounters (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES hunt_sessions(id),
    hunt_id TEXT REFERENCES hunts(id),
    mob_name TEXT NOT NULL,
    mob_name_source TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    damage_dealt REAL DEFAULT 0,
    damage_taken REAL DEFAULT 0,
    heals_received REAL DEFAULT 0,
    loot_total_ped REAL DEFAULT 0,
    shots_fired INTEGER DEFAULT 0,
    critical_hits INTEGER DEFAULT 0,
    cost REAL DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    player_avoids INTEGER DEFAULT 0,
    target_avoids INTEGER DEFAULT 0,
    mob_misses INTEGER DEFAULT 0,
    deflects INTEGER DEFAULT 0,
    blocks INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS encounter_tool_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    encounter_id TEXT NOT NULL REFERENCES mob_encounters(id),
    tool_name TEXT NOT NULL,
    shots_fired INTEGER DEFAULT 0,
    damage_dealt REAL DEFAULT 0,
    critical_hits INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS combat_event_details (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES mob_encounters(id),
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    amount REAL DEFAULT 0,
    tool_name TEXT,
    tool_source TEXT,
    inferred_confidence REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tier_increases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    item_name TEXT NOT NULL,
    tier REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS encounter_loot_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    encounter_id TEXT NOT NULL REFERENCES mob_encounters(id),
    item_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    value_ped REAL NOT NULL,
    is_blacklisted INTEGER DEFAULT 0,
    is_refining_output INTEGER DEFAULT 0,
    is_in_loot_table INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS session_loadouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES hunt_sessions(id),
    timestamp TEXT NOT NULL,
    loadout_data TEXT NOT NULL,
    weapon_name TEXT,
    cost_per_shot REAL DEFAULT 0,
    damage_min REAL DEFAULT 0,
    damage_max REAL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'snapshot'
);

CREATE INDEX IF NOT EXISTS idx_tier_increases_timestamp ON tier_increases(timestamp);
CREATE INDEX IF NOT EXISTS idx_tier_increases_item ON tier_increases(item_name);
CREATE INDEX IF NOT EXISTS idx_hunt_sessions_start ON hunt_sessions(start_time);
CREATE INDEX IF NOT EXISTS idx_hunts_session ON hunts(session_id);
CREATE INDEX IF NOT EXISTS idx_mob_encounters_session ON mob_encounters(session_id);
CREATE INDEX IF NOT EXISTS idx_encounter_tool_stats_encounter ON encounter_tool_stats(encounter_id);
CREATE INDEX IF NOT EXISTS idx_combat_event_details_encounter ON combat_event_details(encounter_id);
CREATE INDEX IF NOT EXISTS idx_combat_event_details_timestamp ON combat_event_details(timestamp);
CREATE INDEX IF NOT EXISTS idx_encounter_loot_items_encounter ON encounter_loot_items(encounter_id);
CREATE INDEX IF NOT EXISTS idx_session_loadouts_session ON session_loadouts(session_id);

CREATE TABLE IF NOT EXISTS custom_item_markups (
    item_name TEXT PRIMARY KEY,
    markup_value REAL NOT NULL,
    markup_type TEXT NOT NULL DEFAULT 'percentage',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_inventory_import (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    items TEXT NOT NULL,
    unresolved TEXT NOT NULL,
    raw_count INTEGER NOT NULL,
    imported_at TEXT NOT NULL,
    synced INTEGER DEFAULT 0
);
"""

# Indexes that depend on columns added by _migrate()
_POST_MIGRATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_skill_gains_ts ON skill_gains(ts);
CREATE INDEX IF NOT EXISTS idx_skill_gains_skill ON skill_gains(skill_id);
CREATE INDEX IF NOT EXISTS idx_mob_encounters_hunt ON mob_encounters(hunt_id);
"""


class Database:
    """SQLite persistence layer. Thread-safe via internal lock."""

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._db_path = db_path
        self._lock = threading.Lock()
        self._batch_mode = False
        self._batch_count = 0
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._migrate()
        self._conn.executescript(_POST_MIGRATE_INDEXES)
        self._conn.commit()

    def _migrate(self):
        """Add columns that may be missing from older databases."""
        migrations = [
            ("mob_encounters", "hunt_id", "TEXT REFERENCES hunts(id)"),
            ("mob_encounters", "is_global", "INTEGER DEFAULT 0"),
            ("mob_encounters", "is_hof", "INTEGER DEFAULT 0"),
            ("mob_encounters", "cost", "REAL DEFAULT 0"),
            ("mob_encounters", "player_avoids", "INTEGER DEFAULT 0"),
            ("mob_encounters", "target_avoids", "INTEGER DEFAULT 0"),
            ("mob_encounters", "mob_misses", "INTEGER DEFAULT 0"),
            ("mob_encounters", "deflects", "INTEGER DEFAULT 0"),
            ("mob_encounters", "blocks", "INTEGER DEFAULT 0"),
            ("mob_encounters", "outcome", "TEXT DEFAULT 'kill'"),
            ("mob_encounters", "death_count", "INTEGER DEFAULT 0"),
            ("mob_encounters", "killed_by_mob", "TEXT"),
            ("mob_encounters", "is_open_ended", "INTEGER DEFAULT 0"),
            ("mob_encounters", "merged_into", "TEXT"),
            ("mob_encounters", "merged_from", "TEXT"),  # JSON array of encounter IDs
            ("session_loadouts", "crit_damage", "REAL DEFAULT 1.0"),
            ("parser_state", "file_hash", "TEXT"),
        ]
        for table, column, col_def in migrations:
            try:
                self._conn.execute(
                    f'ALTER TABLE {table} ADD COLUMN {column} {col_def}'
                )
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Dedup indexes — remove duplicates first (keep lowest rowid), then create unique index
        dedup_indexes = [
            ("idx_globals_dedup", "globals",
             "timestamp, global_type, player_name, target_name, value"),
            ("idx_trade_messages_dedup", "trade_messages",
             "timestamp, channel, username, message"),
        ]
        for idx_name, table, columns in dedup_indexes:
            try:
                self._conn.execute(
                    f"DELETE FROM {table} WHERE rowid NOT IN "
                    f"(SELECT MIN(rowid) FROM {table} GROUP BY {columns})"
                )
                self._conn.execute(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})"
                )
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # Index already exists

        self._migrate_skill_gains_v2()

    def _migrate_skill_gains_v2(self):
        """Migrate skill_gains from TEXT-based to compact integer format."""
        try:
            cur = self._conn.execute("PRAGMA table_info(skill_gains)")
            columns = {row[1] for row in cur.fetchall()}
        except Exception:
            return

        if "skill_name" not in columns:
            return  # Already migrated or fresh DB

        from ..skills.skill_ids import name_to_id_map
        from datetime import datetime
        name_map = name_to_id_map()

        cur = self._conn.execute(
            "SELECT timestamp, skill_name, amount FROM skill_gains"
        )
        old_rows = cur.fetchall()

        self._conn.execute("DROP TABLE IF EXISTS skill_gains_v2")
        self._conn.execute("""
            CREATE TABLE skill_gains_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                skill_id INTEGER NOT NULL,
                amount REAL NOT NULL
            )
        """)

        migrated = []
        for ts_text, skill_name, amount in old_rows:
            skill_id = name_map.get(skill_name)
            if skill_id is None:
                continue
            try:
                dt = datetime.fromisoformat(ts_text)
                unix_ts = int(dt.timestamp())
            except (ValueError, TypeError):
                continue
            migrated.append((unix_ts, skill_id, amount))

        if migrated:
            self._conn.executemany(
                "INSERT INTO skill_gains_v2 (ts, skill_id, amount) VALUES (?, ?, ?)",
                migrated,
            )

        # Drop old indexes, swap tables
        self._conn.execute("DROP INDEX IF EXISTS idx_skill_gains_timestamp")
        self._conn.execute("DROP INDEX IF EXISTS idx_skill_gains_name")
        self._conn.execute("DROP TABLE skill_gains")
        self._conn.execute("ALTER TABLE skill_gains_v2 RENAME TO skill_gains")
        self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executemany(sql, params_list)

    def commit(self):
        with self._lock:
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()

    _BATCH_COMMIT_INTERVAL = 500  # commit every N writes to avoid holding WAL lock too long

    def _auto_commit(self):
        """Commit unless in batch mode. Must be called inside self._lock."""
        if not self._batch_mode:
            self._conn.commit()
        else:
            self._batch_count += 1
            if self._batch_count >= self._BATCH_COMMIT_INTERVAL:
                self._conn.commit()
                self._batch_count = 0

    def begin_batch(self):
        """Enter batch mode — defer commits until end_batch() for bulk inserts."""
        self._batch_mode = True
        self._batch_count = 0

    def end_batch(self):
        """Exit batch mode and commit all deferred writes."""
        with self._lock:
            self._conn.commit()
        self._batch_mode = False
        self._batch_count = 0

    # Parser state management
    def get_parser_state(self, file_path: str) -> tuple[int, int, str | None] | None:
        """Returns (byte_offset, last_line_number, file_hash) or None if no state exists."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT byte_offset, last_line_number, file_hash FROM parser_state WHERE id = 1 AND file_path = ?",
                (file_path,)
            )
            row = cur.fetchone()
            return (row[0], row[1], row[2]) if row else None

    def save_parser_state(self, file_path: str, byte_offset: int, last_line_number: int,
                          last_timestamp: str = None, file_hash: str = None):
        with self._lock:
            self._conn.execute(
                """INSERT INTO parser_state (id, file_path, byte_offset, last_line_number, last_timestamp, file_hash)
                   VALUES (1, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       file_path = excluded.file_path,
                       byte_offset = excluded.byte_offset,
                       last_line_number = excluded.last_line_number,
                       last_timestamp = excluded.last_timestamp,
                       file_hash = excluded.file_hash""",
                (file_path, byte_offset, last_line_number, last_timestamp, file_hash)
            )
            self._auto_commit()

    # Pending ingestion (crash recovery)
    def save_pending_ingestion(self, event_type: str, items: list[dict]):
        """Persist pending ingestion items so they survive a crash."""
        import json
        with self._lock:
            self._conn.execute("DELETE FROM pending_ingestion WHERE type = ?", (event_type,))
            for item in items:
                self._conn.execute(
                    "INSERT INTO pending_ingestion (type, data) VALUES (?, ?)",
                    (event_type, json.dumps(item))
                )
            self._conn.commit()

    def load_pending_ingestion(self, event_type: str) -> list[dict]:
        """Load pending ingestion items from a previous session."""
        import json
        with self._lock:
            cur = self._conn.execute(
                "SELECT data FROM pending_ingestion WHERE type = ? ORDER BY id", (event_type,)
            )
            return [json.loads(row[0]) for row in cur.fetchall()]

    def clear_pending_ingestion(self, event_type: str):
        """Clear pending ingestion items after successful upload."""
        with self._lock:
            self._conn.execute("DELETE FROM pending_ingestion WHERE type = ?", (event_type,))
            self._conn.commit()

    # Skill gains
    def insert_skill_gain(self, ts: int, skill_id: int, amount: float):
        """Insert a skill gain event. ts is Unix timestamp, skill_id from skill_reference."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO skill_gains (ts, skill_id, amount) VALUES (?, ?, ?)",
                (ts, skill_id, amount)
            )
            self._auto_commit()

    def get_skill_gains_since(self, since_ts: int) -> dict[int, float]:
        """Sum skill gains per skill_id since a Unix timestamp.

        Returns {skill_id: total_amount}.
        """
        with self._lock:
            cur = self._conn.execute(
                "SELECT skill_id, SUM(amount) FROM skill_gains "
                "WHERE ts >= ? GROUP BY skill_id",
                (since_ts,)
            )
            return {row[0]: row[1] for row in cur.fetchall()}

    def get_last_scan_timestamp(self) -> int | None:
        """Get the Unix timestamp of the most recent skill snapshot scan."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT MAX(scan_timestamp) FROM skill_snapshots"
            )
            row = cur.fetchone()
            if row and row[0]:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(row[0])
                    return int(dt.timestamp())
                except (ValueError, TypeError):
                    return None
            return None

    # Combat events
    def insert_combat_event(self, timestamp: str, event_type: str, amount: float = None, session_id: str = None):
        with self._lock:
            self._conn.execute(
                "INSERT INTO combat_events (timestamp, event_type, amount, session_id) VALUES (?, ?, ?, ?)",
                (timestamp, event_type, amount, session_id)
            )
            self._auto_commit()

    # Loot
    def insert_loot_group(self, timestamp: str, total_value: float, items: list[tuple], session_id: str = None) -> int:
        """Insert a loot group and its items. Returns the group id."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO loot_groups (timestamp, total_value_ped, session_id) VALUES (?, ?, ?)",
                (timestamp, total_value, session_id)
            )
            group_id = cur.lastrowid
            self._conn.executemany(
                "INSERT INTO loot_items (group_id, item_name, quantity, value_ped) VALUES (?, ?, ?, ?)",
                [(group_id, name, qty, val) for name, qty, val in items]
            )
            self._auto_commit()
            return group_id

    # Enhancer breaks
    def insert_enhancer_break(self, timestamp: str, enhancer_name: str, item_name: str,
                              remaining: int, shrapnel_ped: float, session_id: str = None):
        with self._lock:
            self._conn.execute(
                "INSERT INTO enhancer_breaks (timestamp, enhancer_name, item_name, remaining, shrapnel_ped, session_id) VALUES (?, ?, ?, ?, ?, ?)",
                (timestamp, enhancer_name, item_name, remaining, shrapnel_ped, session_id)
            )
            self._auto_commit()

    # Tier increases
    def insert_tier_increase(self, timestamp: str, item_name: str, tier: float):
        with self._lock:
            self._conn.execute(
                "INSERT INTO tier_increases (timestamp, item_name, tier) VALUES (?, ?, ?)",
                (timestamp, item_name, tier)
            )
            self._auto_commit()

    # Globals
    def insert_global(self, timestamp: str, global_type: str, player_name: str, target_name: str,
                      value: float, value_unit: str, location: str = None,
                      is_hof: bool = False, is_ath: bool = False):
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO globals (timestamp, global_type, player_name, target_name, value, value_unit, location, is_hof, is_ath) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (timestamp, global_type, player_name, target_name, value, value_unit, location, int(is_hof), int(is_ath))
            )
            self._auto_commit()

    def get_recent_globals(self, minutes: int = 5) -> list[dict]:
        """Get globals from the last N minutes for occurrence tracker seeding."""
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        with self._lock:
            cur = self._conn.execute(
                "SELECT timestamp, global_type, player_name, target_name, "
                "value, value_unit, location, is_hof, is_ath "
                "FROM globals WHERE timestamp > ? ORDER BY timestamp",
                (cutoff,)
            )
            return [
                {
                    "timestamp": r[0], "type": r[1], "player": r[2], "target": r[3],
                    "value": r[4], "unit": r[5], "location": r[6],
                    "hof": bool(r[7]), "ath": bool(r[8]),
                }
                for r in cur.fetchall()
            ]

    def get_all_globals(self) -> list[dict]:
        """Read all globals from the local DB (for ingestion re-submission)."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT timestamp, global_type, player_name, target_name, "
                "value, value_unit, location, is_hof, is_ath FROM globals ORDER BY id"
            )
            return [
                {
                    "timestamp": r[0], "type": r[1], "player": r[2], "target": r[3],
                    "value": r[4], "unit": r[5], "location": r[6],
                    "hof": bool(r[7]), "ath": bool(r[8]),
                }
                for r in cur.fetchall()
            ]

    def get_all_trades(self) -> list[dict]:
        """Read all trade messages from the local DB (for ingestion re-submission)."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT timestamp, channel, username, message FROM trade_messages ORDER BY id"
            )
            return [
                {"timestamp": r[0], "channel": r[1], "username": r[2], "message": r[3]}
                for r in cur.fetchall()
            ]

    # Trade messages
    def insert_trade_message(self, timestamp: str, channel: str, username: str, message: str):
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO trade_messages (timestamp, channel, username, message) VALUES (?, ?, ?, ?)",
                (timestamp, channel, username, message)
            )
            self._auto_commit()

    # Skill snapshots
    def insert_skill_snapshot(self, scan_timestamp: str, skill_name: str, rank: str,
                              current_points: float, progress_percent: float, category: str):
        with self._lock:
            self._conn.execute(
                "INSERT INTO skill_snapshots (scan_timestamp, skill_name, rank, current_points, progress_percent, category) VALUES (?, ?, ?, ?, ?, ?)",
                (scan_timestamp, skill_name, rank, current_points, progress_percent, category)
            )
            self._auto_commit()

    # Hunt sessions
    def insert_hunt_session(self, session_id: str, start_time: str, loadout_id: str = None,
                            primary_mob: str = None):
        with self._lock:
            self._conn.execute(
                "INSERT INTO hunt_sessions (id, start_time, loadout_id, primary_mob) VALUES (?, ?, ?, ?)",
                (session_id, start_time, loadout_id, primary_mob)
            )
            self._auto_commit()

    def end_hunt_session(self, session_id: str, end_time: str, notes: str = None):
        with self._lock:
            self._conn.execute(
                "UPDATE hunt_sessions SET end_time = ?, notes = ? WHERE id = ?",
                (end_time, notes, session_id)
            )
            self._auto_commit()

    # Hunts
    def insert_hunt(self, hunt_id: str, session_id: str, start_time: str,
                    primary_mob: str = None, location_label: str = None):
        with self._lock:
            self._conn.execute(
                "INSERT INTO hunts (id, session_id, start_time, primary_mob, location_label) VALUES (?, ?, ?, ?, ?)",
                (hunt_id, session_id, start_time, primary_mob, location_label)
            )
            self._auto_commit()

    def end_hunt(self, hunt_id: str, end_time: str, total_cost: float = 0):
        with self._lock:
            self._conn.execute(
                "UPDATE hunts SET end_time = ?, total_cost = ? WHERE id = ?",
                (end_time, total_cost, hunt_id)
            )
            self._auto_commit()

    def get_session_hunts(self, session_id: str) -> list[dict]:
        """Get all hunts for a session."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM hunts WHERE session_id = ? ORDER BY start_time",
                (session_id,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            self._conn.row_factory = None
            return rows

    def get_hunt_encounters(self, hunt_id: str) -> list[dict]:
        """Get all encounters for a hunt."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM mob_encounters WHERE hunt_id = ? ORDER BY start_time",
                (hunt_id,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            self._conn.row_factory = None
            return rows

    def merge_hunts(self, target_hunt_id: str, source_hunt_ids: list[str]):
        """Merge source hunts into target by reassigning encounters."""
        with self._lock:
            for source_id in source_hunt_ids:
                self._conn.execute(
                    "UPDATE mob_encounters SET hunt_id = ? WHERE hunt_id = ?",
                    (target_hunt_id, source_id)
                )
                self._conn.execute("DELETE FROM hunts WHERE id = ?", (source_id,))
            self._auto_commit()

    def split_hunt(self, hunt_id: str, new_hunt_id: str, new_hunt_start_time: str,
                   encounter_ids: list[str], primary_mob: str = None):
        """Split encounters from an existing hunt into a new hunt."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO hunts (id, session_id, start_time, primary_mob) "
                "SELECT ?, session_id, ?, ? FROM hunts WHERE id = ?",
                (new_hunt_id, new_hunt_start_time, primary_mob, hunt_id)
            )
            placeholders = ",".join("?" * len(encounter_ids))
            self._conn.execute(
                f"UPDATE mob_encounters SET hunt_id = ? WHERE id IN ({placeholders})",
                (new_hunt_id, *encounter_ids)
            )
            self._auto_commit()

    # Mob encounters
    def insert_mob_encounter(self, encounter_id: str, session_id: str, mob_name: str,
                             mob_name_source: str, start_time: str, hunt_id: str = None):
        with self._lock:
            self._conn.execute(
                "INSERT INTO mob_encounters (id, session_id, hunt_id, mob_name, mob_name_source, start_time) VALUES (?, ?, ?, ?, ?, ?)",
                (encounter_id, session_id, hunt_id, mob_name, mob_name_source, start_time)
            )
            self._auto_commit()

    def update_mob_encounter(self, encounter_id: str, **kwargs):
        """Update encounter fields. Accepts any column name as keyword argument."""
        if not kwargs:
            return
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [encounter_id]
        with self._lock:
            self._conn.execute(
                f"UPDATE mob_encounters SET {set_clause} WHERE id = ?",
                tuple(values)
            )
            self._auto_commit()

    # Encounter tool stats
    def upsert_encounter_tool_stat(self, encounter_id: str, tool_name: str,
                                   shots_delta: int = 0, damage_delta: float = 0,
                                   crits_delta: int = 0):
        """Increment tool stats for an encounter, inserting if needed."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT id, shots_fired, damage_dealt, critical_hits FROM encounter_tool_stats WHERE encounter_id = ? AND tool_name = ?",
                (encounter_id, tool_name)
            )
            row = cur.fetchone()
            if row:
                self._conn.execute(
                    "UPDATE encounter_tool_stats SET shots_fired = ?, damage_dealt = ?, critical_hits = ? WHERE id = ?",
                    (row[1] + shots_delta, row[2] + damage_delta, row[3] + crits_delta, row[0])
                )
            else:
                self._conn.execute(
                    "INSERT INTO encounter_tool_stats (encounter_id, tool_name, shots_fired, damage_dealt, critical_hits) VALUES (?, ?, ?, ?, ?)",
                    (encounter_id, tool_name, shots_delta, damage_delta, crits_delta)
                )
            self._auto_commit()

    def get_hunt_session(self, session_id: str) -> dict | None:
        """Get a hunt session by ID."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute("SELECT * FROM hunt_sessions WHERE id = ?", (session_id,))
            row = cur.fetchone()
            self._conn.row_factory = None
            return dict(row) if row else None

    def get_incomplete_session(self) -> dict | None:
        """Get the most recent session with no end_time (incomplete)."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM hunt_sessions WHERE end_time IS NULL "
                "ORDER BY start_time DESC LIMIT 1"
            )
            row = cur.fetchone()
            self._conn.row_factory = None
            return dict(row) if row else None

    def get_session_encounters(self, session_id: str) -> list[dict]:
        """Get all encounters for a hunt session."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM mob_encounters WHERE session_id = ? ORDER BY start_time",
                (session_id,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            self._conn.row_factory = None
            return rows

    def get_encounter_tool_stats(self, encounter_id: str) -> list[dict]:
        """Get tool stats for an encounter."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM encounter_tool_stats WHERE encounter_id = ? ORDER BY damage_dealt DESC",
                (encounter_id,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            self._conn.row_factory = None
            return rows

    def get_encounter_combat_events(self, encounter_id: str) -> list[dict]:
        """Get all combat events for an encounter, ordered by timestamp."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM combat_event_details WHERE encounter_id = ? ORDER BY timestamp",
                (encounter_id,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            self._conn.row_factory = None
            return rows

    # Encounter loot items
    def insert_encounter_loot_items(self, encounter_id: str, items: list):
        """Batch insert loot items for an encounter."""
        with self._lock:
            self._conn.executemany(
                "INSERT INTO encounter_loot_items "
                "(encounter_id, item_name, quantity, value_ped, "
                "is_blacklisted, is_refining_output, is_in_loot_table) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (encounter_id, li.item_name, li.quantity, li.value_ped,
                     int(li.is_blacklisted), int(li.is_refining_output),
                     int(li.is_in_loot_table))
                    for li in items
                ]
            )
            self._auto_commit()

    def get_encounter_loot_items(self, encounter_id: str) -> list[dict]:
        """Get all loot items for an encounter."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM encounter_loot_items WHERE encounter_id = ? "
                "ORDER BY value_ped DESC",
                (encounter_id,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            self._conn.row_factory = None
            return rows

    # Combat event details
    def insert_combat_event_detail(self, event_id: str, encounter_id: str, timestamp: str,
                                   event_type: str, amount: float = 0,
                                   tool_name: str = None, tool_source: str = None,
                                   confidence: float = 0):
        with self._lock:
            self._conn.execute(
                "INSERT INTO combat_event_details (id, encounter_id, timestamp, event_type, amount, tool_name, tool_source, inferred_confidence) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, encounter_id, timestamp, event_type, amount, tool_name, tool_source, confidence)
            )
            self._auto_commit()

    def update_combat_event_tool(self, event_id: str, tool_name: str,
                                 tool_source: str, confidence: float):
        """Retroactive enrichment — update tool info on a buffered event."""
        with self._lock:
            self._conn.execute(
                "UPDATE combat_event_details SET tool_name = ?, tool_source = ?, inferred_confidence = ? WHERE id = ?",
                (tool_name, tool_source, confidence, event_id)
            )
            self._auto_commit()

    def get_recent_sessions(self, limit: int = 20) -> list[dict]:
        """Get recent hunt sessions for the History tab."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM hunt_sessions ORDER BY start_time DESC LIMIT ?",
                (limit,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            self._conn.row_factory = None
            return rows

    def update_encounter_hunt(self, encounter_id: str, hunt_id: str):
        """Assign an encounter to a hunt."""
        with self._lock:
            self._conn.execute(
                "UPDATE mob_encounters SET hunt_id = ? WHERE id = ?",
                (hunt_id, encounter_id)
            )
            self._auto_commit()

    def delete_hunt_session(self, session_id: str):
        """Delete a session and all associated data."""
        with self._lock:
            # Delete in dependency order
            self._conn.execute(
                "DELETE FROM encounter_loot_items WHERE encounter_id IN "
                "(SELECT id FROM mob_encounters WHERE session_id = ?)",
                (session_id,)
            )
            self._conn.execute(
                "DELETE FROM combat_event_details WHERE encounter_id IN "
                "(SELECT id FROM mob_encounters WHERE session_id = ?)",
                (session_id,)
            )
            self._conn.execute(
                "DELETE FROM encounter_tool_stats WHERE encounter_id IN "
                "(SELECT id FROM mob_encounters WHERE session_id = ?)",
                (session_id,)
            )
            self._conn.execute(
                "DELETE FROM session_loadouts WHERE session_id = ?",
                (session_id,)
            )
            self._conn.execute(
                "DELETE FROM mob_encounters WHERE session_id = ?", (session_id,)
            )
            self._conn.execute(
                "DELETE FROM hunts WHERE session_id = ?", (session_id,)
            )
            self._conn.execute(
                "DELETE FROM hunt_sessions WHERE id = ?", (session_id,)
            )
            self._auto_commit()

    # Session loadouts
    def insert_session_loadout(self, session_id: str, timestamp: str,
                               loadout_data_json: str, weapon_name: str = None,
                               cost_per_shot: float = 0, damage_min: float = 0,
                               damage_max: float = 0, source: str = "snapshot",
                               crit_damage: float = 1.0) -> int:
        """Insert a session loadout snapshot. Returns the auto-increment ID."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO session_loadouts "
                "(session_id, timestamp, loadout_data, weapon_name, "
                "cost_per_shot, damage_min, damage_max, source, crit_damage) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, timestamp, loadout_data_json, weapon_name,
                 cost_per_shot, damage_min, damage_max, source, crit_damage)
            )
            self._auto_commit()
            return cur.lastrowid

    def update_session_loadout(self, loadout_id: int, **kwargs):
        """Update a session loadout entry. Accepts any column as keyword."""
        if not kwargs:
            return
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [loadout_id]
        with self._lock:
            self._conn.execute(
                f"UPDATE session_loadouts SET {set_clause} WHERE id = ?",
                tuple(values)
            )
            self._auto_commit()

    def get_session_loadouts(self, session_id: str) -> list[dict]:
        """Get all loadout snapshots for a session, ordered by timestamp."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM session_loadouts WHERE session_id = ? "
                "ORDER BY timestamp",
                (session_id,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            self._conn.row_factory = None
            return rows

    def get_latest_session_loadout(self, session_id: str) -> dict | None:
        """Get the most recent loadout snapshot for a session."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM session_loadouts WHERE session_id = ? "
                "ORDER BY timestamp DESC LIMIT 1",
                (session_id,)
            )
            row = cur.fetchone()
            self._conn.row_factory = None
            return dict(row) if row else None

    # Custom item markups
    def get_custom_markup(self, item_name: str) -> dict | None:
        """Get a custom markup for an item by name."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM custom_item_markups WHERE item_name = ?",
                (item_name,)
            )
            row = cur.fetchone()
            self._conn.row_factory = None
            return dict(row) if row else None

    def set_custom_markup(self, item_name: str, markup_value: float,
                          markup_type: str, updated_at: str) -> None:
        """Set or update a custom markup for an item."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO custom_item_markups (item_name, markup_value, markup_type, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(item_name) DO UPDATE SET "
                "markup_value = excluded.markup_value, "
                "markup_type = excluded.markup_type, "
                "updated_at = excluded.updated_at",
                (item_name, markup_value, markup_type, updated_at)
            )
            self._auto_commit()

    def remove_custom_markup(self, item_name: str) -> None:
        """Remove a custom markup for an item."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM custom_item_markups WHERE item_name = ?",
                (item_name,)
            )
            self._auto_commit()

    # Pending inventory imports (offline fallback)
    def save_pending_inventory_import(self, items: list[dict], unresolved: list[dict],
                                       raw_count: int) -> int:
        """Save a pending inventory import for later sync. Returns the row ID."""
        import json
        from datetime import datetime
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO pending_inventory_import (items, unresolved, raw_count, imported_at) "
                "VALUES (?, ?, ?, ?)",
                (json.dumps(items), json.dumps(unresolved), raw_count,
                 datetime.now().isoformat())
            )
            self._auto_commit()
            return cur.lastrowid

    def get_pending_inventory_imports(self) -> list[dict]:
        """Get all unsynced pending inventory imports."""
        import json
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM pending_inventory_import WHERE synced = 0 "
                "ORDER BY imported_at DESC"
            )
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d['items'] = json.loads(d['items'])
                d['unresolved'] = json.loads(d['unresolved'])
                rows.append(d)
            self._conn.row_factory = None
            return rows

    def mark_pending_inventory_synced(self, import_id: int):
        """Mark a pending import as synced."""
        with self._lock:
            self._conn.execute(
                "UPDATE pending_inventory_import SET synced = 1 WHERE id = ?",
                (import_id,)
            )
            self._auto_commit()

    def discard_pending_inventory_imports(self):
        """Discard all unsynced pending imports."""
        with self._lock:
            self._conn.execute(
                "UPDATE pending_inventory_import SET synced = 1 WHERE synced = 0"
            )
            self._auto_commit()

    def delete_ingested_globals(self, items: list[dict]) -> int:
        """Delete specific globals confirmed processed by the server.

        Uses the dedup key (timestamp, global_type, player_name, target_name, value)
        to identify rows. Returns number of rows deleted.
        """
        deleted = 0
        with self._lock:
            for item in items:
                cur = self._conn.execute(
                    "DELETE FROM globals WHERE timestamp = ? AND global_type = ? "
                    "AND player_name = ? AND target_name = ? AND value = ?",
                    (item["timestamp"], item["type"], item["player"],
                     item["target"], item["value"]),
                )
                deleted += cur.rowcount
            self._conn.commit()
        return deleted

    def delete_ingested_trades(self, items: list[dict]) -> int:
        """Delete specific trade messages confirmed processed by the server.

        Uses the dedup key (timestamp, channel, username, message)
        to identify rows. Returns number of rows deleted.
        """
        deleted = 0
        with self._lock:
            for item in items:
                cur = self._conn.execute(
                    "DELETE FROM trade_messages WHERE timestamp = ? AND channel = ? "
                    "AND username = ? AND message = ?",
                    (item["timestamp"], item["channel"], item["username"],
                     item["message"]),
                )
                deleted += cur.rowcount
            self._conn.commit()
        return deleted

    def clear_parsed_data(self) -> None:
        """Delete all chat-parsed data before a full reparse.

        Clears everything including deduped tables (globals, trade_messages)
        because changes to parsing (e.g. HTML entity decoding) can alter
        the values used in unique constraints, causing duplicates.
        """
        with self._lock:
            # Child tables first (foreign key dependencies)
            self._conn.execute("DELETE FROM encounter_loot_items")
            self._conn.execute("DELETE FROM combat_event_details")
            self._conn.execute("DELETE FROM encounter_tool_stats")
            self._conn.execute("DELETE FROM session_loadouts")
            self._conn.execute("DELETE FROM mob_encounters")
            self._conn.execute("DELETE FROM hunts")
            self._conn.execute("DELETE FROM hunt_sessions")
            # Standalone parsed-data tables
            self._conn.execute("DELETE FROM loot_items")
            self._conn.execute("DELETE FROM loot_groups")
            self._conn.execute("DELETE FROM combat_events")
            self._conn.execute("DELETE FROM skill_gains")
            self._conn.execute("DELETE FROM enhancer_breaks")
            self._conn.execute("DELETE FROM tier_increases")
            # Deduped tables — also cleared to avoid stale/misencoded rows
            self._conn.execute("DELETE FROM globals")
            self._conn.execute("DELETE FROM trade_messages")
            self._conn.commit()

    def get_all_custom_markups(self) -> list[dict]:
        """Get all custom markups."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM custom_item_markups ORDER BY item_name"
            )
            rows = [dict(r) for r in cur.fetchall()]
            self._conn.row_factory = None
            return rows
