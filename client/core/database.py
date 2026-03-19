import hashlib
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


def compute_file_hash(file_path: str) -> str | None:
    """Compute SHA-256 hash of a file. Returns hex digest or None on error."""
    try:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


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

CREATE TABLE IF NOT EXISTS local_skill_values (
    skill_name TEXT PRIMARY KEY,
    current_points REAL NOT NULL,
    updated_at TEXT NOT NULL,
    dirty INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS local_skill_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_at TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    old_value REAL,
    new_value REAL NOT NULL,
    source TEXT NOT NULL
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
CREATE INDEX IF NOT EXISTS idx_local_skill_values_updated ON local_skill_values(updated_at);
CREATE INDEX IF NOT EXISTS idx_local_skill_values_dirty ON local_skill_values(dirty);
CREATE INDEX IF NOT EXISTS idx_local_skill_history_imported ON local_skill_history(imported_at);
CREATE INDEX IF NOT EXISTS idx_local_skill_history_name ON local_skill_history(skill_name);

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

CREATE TABLE IF NOT EXISTS session_loadout_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES hunt_sessions(id),
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    description TEXT,
    loadout_data TEXT,
    enhancer_delta TEXT,
    tool_name TEXT,
    cost_per_shot REAL,
    damage_min REAL,
    damage_max REAL
);

CREATE INDEX IF NOT EXISTS idx_session_loadout_events_session ON session_loadout_events(session_id);

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

CREATE TABLE IF NOT EXISTS skill_gains_hourly (
    hour_ts INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    event_count INTEGER NOT NULL,
    PRIMARY KEY (hour_ts, skill_id)
);

CREATE TABLE IF NOT EXISTS skill_gains_daily (
    day_ts INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    event_count INTEGER NOT NULL,
    PRIMARY KEY (day_ts, skill_id)
);

CREATE TABLE IF NOT EXISTS skill_gains_rollup_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_hourly_id INTEGER NOT NULL DEFAULT 0,
    last_daily_hour_ts INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS skill_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_type TEXT NOT NULL,
    target_name TEXT NOT NULL,
    target_value REAL NOT NULL,
    start_value REAL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tracker_missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL,
    planet TEXT,
    cooldown_duration TEXT,
    cooldown_starts_on TEXT DEFAULT 'Completion',
    cooldown_ms INTEGER NOT NULL DEFAULT 86400000,
    sort_order INTEGER NOT NULL DEFAULT 0,
    cooldown_started_at TEXT,
    notify INTEGER NOT NULL DEFAULT 1,
    notify_minutes_before INTEGER NOT NULL DEFAULT 5,
    start_location TEXT,
    has_expiry INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS custom_dailies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cooldown_duration TEXT NOT NULL DEFAULT '1 day',
    cooldown_starts_on TEXT NOT NULL DEFAULT 'Completion',
    cooldown_ms INTEGER NOT NULL DEFAULT 86400000,
    sort_order INTEGER NOT NULL DEFAULT 0,
    cooldown_started_at TEXT,
    notify INTEGER NOT NULL DEFAULT 1,
    notify_minutes_before INTEGER NOT NULL DEFAULT 5,
    waypoint TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,
    file_type TEXT NOT NULL DEFAULT 'screenshot',
    created_at TEXT NOT NULL,
    global_id INTEGER REFERENCES globals(id),
    notes TEXT,
    upload_status TEXT NOT NULL DEFAULT 'none',
    server_global_id INTEGER,
    uploaded_at TEXT,
    video_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_screenshots_path ON screenshots(file_path);
CREATE INDEX IF NOT EXISTS idx_screenshots_global ON screenshots(global_id);

CREATE TABLE IF NOT EXISTS loot_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    item_name TEXT NOT NULL,
    item_id INTEGER,
    quantity INTEGER NOT NULL,
    value_ped REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_loot_events_timestamp ON loot_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_loot_events_item_name ON loot_events(item_name);
"""

# Indexes that depend on columns added by _migrate()
_POST_MIGRATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_skill_gains_covering ON skill_gains(ts, skill_id, amount);
CREATE INDEX IF NOT EXISTS idx_skill_snapshots_name_id ON skill_snapshots(skill_name, id);
CREATE INDEX IF NOT EXISTS idx_mob_encounters_hunt ON mob_encounters(hunt_id);
CREATE INDEX IF NOT EXISTS idx_trade_messages_timestamp ON trade_messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_screenshots_hash ON screenshots(file_hash);
"""

# Drop old single-column skill_gains indexes superseded by the covering index.
_DROP_OLD_SKILL_GAINS_INDEXES = """
DROP INDEX IF EXISTS idx_skill_gains_ts;
DROP INDEX IF EXISTS idx_skill_gains_skill;
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
        self._conn.executescript(_DROP_OLD_SKILL_GAINS_INDEXES)
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
            ("mob_encounters", "mob_id", "INTEGER"),
            ("mob_encounters", "is_shared_loot", "INTEGER"),
            ("encounter_loot_items", "item_id", "INTEGER"),
            ("encounter_loot_items", "is_enhancer_shrapnel", "INTEGER DEFAULT 0"),
            ("encounter_tool_stats", "tool_id", "INTEGER"),
            ("session_loadouts", "crit_damage", "REAL DEFAULT 1.0"),
            ("parser_state", "file_hash", "TEXT"),
            ("screenshots", "file_hash", "TEXT"),
        ]
        for table, column, col_def in migrations:
            try:
                self._conn.execute(
                    f'ALTER TABLE {table} ADD COLUMN {column} {col_def}'
                )
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Dedup indexes — only run the expensive DELETE if the unique index
        # doesn't exist yet (first run after migration).  Once the index is
        # created, duplicates can no longer be inserted so the dedup is a no-op.
        dedup_indexes = [
            ("idx_globals_dedup", "globals",
             "timestamp, global_type, player_name, target_name, value"),
            ("idx_trade_messages_dedup", "trade_messages",
             "timestamp, channel, username, message"),
        ]
        existing_indexes = {
            row[0] for row in
            self._conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
        for idx_name, table, columns in dedup_indexes:
            if idx_name in existing_indexes:
                continue  # Already deduplicated
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
                pass

        # Rename youtube_url → video_url (multi-platform video support)
        try:
            self._conn.execute(
                "ALTER TABLE screenshots RENAME COLUMN youtube_url TO video_url"
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # Already renamed or column doesn't exist

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
        # Pre-serialize JSON outside the lock to reduce hold time
        serialized = [(event_type, json.dumps(item)) for item in items]
        with self._lock:
            self._conn.execute("DELETE FROM pending_ingestion WHERE type = ?", (event_type,))
            self._conn.executemany(
                "INSERT INTO pending_ingestion (type, data) VALUES (?, ?)",
                serialized,
            )
            self._conn.commit()

    def load_pending_ingestion(self, event_type: str) -> list[dict]:
        """Load pending ingestion items from a previous session."""
        import json
        with self._lock:
            cur = self._conn.execute(
                "SELECT data FROM pending_ingestion WHERE type = ? ORDER BY id", (event_type,)
            )
            raw = [row[0] for row in cur.fetchall()]
        # JSON parsing outside the lock to reduce hold time
        return [json.loads(r) for r in raw]

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

    def get_skill_gains_before(self, before_ts: int) -> dict[int, float]:
        """Sum skill gains per skill_id before a Unix timestamp.

        Returns {skill_id: total_amount}.
        """
        with self._lock:
            cur = self._conn.execute(
                "SELECT skill_id, SUM(amount) FROM skill_gains "
                "WHERE ts < ? GROUP BY skill_id",
                (before_ts,)
            )
            return {row[0]: row[1] for row in cur.fetchall()}

    def get_last_scan_timestamp(self) -> int | None:
        """Get the Unix timestamp of the most recent local skill value update."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT MAX(strftime('%s', updated_at)) FROM local_skill_values"
            )
            row = cur.fetchone()
            return int(row[0]) if row and row[0] else None

    def get_last_sync_timestamp(self) -> int | None:
        """Get Unix timestamp of the most recent local skill value update."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT MAX(strftime('%s', updated_at)) FROM local_skill_values"
            )
            row = cur.fetchone()
            return int(row[0]) if row and row[0] else None

    # Skill gains rollup
    def refresh_skill_rollups(self) -> None:
        """Incrementally refresh hourly and daily rollup tables.

        Processes only new skill_gains rows since last rollup.
        Safe to call frequently — no-ops when there is nothing new.
        """
        with self._lock:
            # Ensure state row exists
            self._conn.execute(
                "INSERT OR IGNORE INTO skill_gains_rollup_state (id, last_hourly_id, last_daily_hour_ts) "
                "VALUES (1, 0, 0)"
            )
            row = self._conn.execute(
                "SELECT last_hourly_id, last_daily_hour_ts FROM skill_gains_rollup_state WHERE id = 1"
            ).fetchone()
            last_hourly_id = row[0]
            last_daily_hour_ts = row[1]

            # Aggregate new skill_gains rows into hourly buckets
            new_rows = self._conn.execute(
                "SELECT MAX(id), skill_id, (ts / 3600) * 3600 AS hour_ts, "
                "SUM(amount), COUNT(*) "
                "FROM skill_gains WHERE id > ? "
                "GROUP BY skill_id, hour_ts",
                (last_hourly_id,),
            ).fetchall()

            if new_rows:
                self._conn.executemany(
                    "INSERT INTO skill_gains_hourly (hour_ts, skill_id, total_amount, event_count) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(hour_ts, skill_id) DO UPDATE SET "
                    "total_amount = total_amount + excluded.total_amount, "
                    "event_count = event_count + excluded.event_count",
                    [(r[2], r[1], r[3], r[4]) for r in new_rows],
                )
                new_last_id = max(r[0] for r in new_rows)
                self._conn.execute(
                    "UPDATE skill_gains_rollup_state SET last_hourly_id = ? WHERE id = 1",
                    (new_last_id,),
                )

            # Roll hourly into daily
            daily_rows = self._conn.execute(
                "SELECT skill_id, (hour_ts / 86400) * 86400 AS day_ts, "
                "SUM(total_amount), SUM(event_count) "
                "FROM skill_gains_hourly WHERE hour_ts > ? "
                "GROUP BY skill_id, day_ts",
                (last_daily_hour_ts,),
            ).fetchall()

            if daily_rows:
                self._conn.executemany(
                    "INSERT INTO skill_gains_daily (day_ts, skill_id, total_amount, event_count) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(day_ts, skill_id) DO UPDATE SET "
                    "total_amount = excluded.total_amount, "
                    "event_count = excluded.event_count",
                    [(r[1], r[0], r[2], r[3]) for r in daily_rows],
                )
                max_hour_ts = self._conn.execute(
                    "SELECT MAX(hour_ts) FROM skill_gains_hourly"
                ).fetchone()[0] or 0
                self._conn.execute(
                    "UPDATE skill_gains_rollup_state SET last_daily_hour_ts = ? WHERE id = 1",
                    (max_hour_ts,),
                )

            self._conn.commit()

    def get_skill_gains_timeseries(
        self,
        skill_ids: list[int] | None,
        from_ts: int,
        to_ts: int | None = None,
    ) -> list[dict]:
        """Get time-series skill gains for charting.

        Automatically selects raw events (<24h), hourly (<7d), or daily rollup.
        Returns [{ts, skill_id, amount}, ...] ordered by ts.
        """
        if to_ts is None:
            import time
            to_ts = int(time.time())

        span = to_ts - from_ts

        if span < 86400:
            # Raw individual events for sub-day granularity
            sql = "SELECT ts, skill_id, amount FROM skill_gains WHERE ts >= ? AND ts <= ?"
            params: list = [from_ts, to_ts]
            if skill_ids:
                placeholders = ",".join("?" for _ in skill_ids)
                sql += f" AND skill_id IN ({placeholders})"
                params.extend(skill_ids)
            sql += " ORDER BY ts"
        elif span < 7 * 86400:
            table = "skill_gains_hourly"
            ts_col = "hour_ts"
            bucket_from = (from_ts // 3600) * 3600
            sql = (
                f"SELECT {ts_col}, skill_id, total_amount "
                f"FROM {table} WHERE {ts_col} >= ? AND {ts_col} <= ?"
            )
            params = [bucket_from, to_ts]
            if skill_ids:
                placeholders = ",".join("?" for _ in skill_ids)
                sql += f" AND skill_id IN ({placeholders})"
                params.extend(skill_ids)
            sql += f" ORDER BY {ts_col}"
        else:
            table = "skill_gains_daily"
            ts_col = "day_ts"
            bucket_from = (from_ts // 86400) * 86400
            sql = (
                f"SELECT {ts_col}, skill_id, total_amount "
                f"FROM {table} WHERE {ts_col} >= ? AND {ts_col} <= ?"
            )
            params = [bucket_from, to_ts]
            if skill_ids:
                placeholders = ",".join("?" for _ in skill_ids)
                sql += f" AND skill_id IN ({placeholders})"
                params.extend(skill_ids)
            sql += f" ORDER BY {ts_col}"

        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return [
                {"ts": row[0], "skill_id": row[1], "amount": row[2]}
                for row in cur.fetchall()
            ]

    def get_top_gaining_skills(
        self,
        from_ts: int,
        to_ts: int | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Get top N skills by total gain in a time period.

        Automatically selects raw events, hourly, or daily table.
        Returns [{skill_id, total_amount}, ...] sorted desc.
        """
        if to_ts is None:
            import time
            to_ts = int(time.time())

        span = to_ts - from_ts
        if span < 86400:
            sql = (
                "SELECT skill_id, SUM(amount) AS total "
                "FROM skill_gains "
                "WHERE ts >= ? AND ts <= ? "
                "GROUP BY skill_id ORDER BY total DESC LIMIT ?"
            )
            params = (from_ts, to_ts, limit)
        elif span < 7 * 86400:
            bucket_from = (from_ts // 3600) * 3600
            sql = (
                "SELECT skill_id, SUM(total_amount) AS total "
                "FROM skill_gains_hourly "
                "WHERE hour_ts >= ? AND hour_ts <= ? "
                "GROUP BY skill_id ORDER BY total DESC LIMIT ?"
            )
            params = (bucket_from, to_ts, limit)
        else:
            day_from = (from_ts // 86400) * 86400
            sql = (
                "SELECT skill_id, SUM(total_amount) AS total "
                "FROM skill_gains_daily "
                "WHERE day_ts >= ? AND day_ts <= ? "
                "GROUP BY skill_id ORDER BY total DESC LIMIT ?"
            )
            params = (day_from, to_ts, limit)

        with self._lock:
            cur = self._conn.execute(sql, params)
            return [
                {"skill_id": row[0], "total_amount": row[1]}
                for row in cur.fetchall()
            ]

    # Skill goals
    def get_active_goals(self) -> list[dict]:
        """Get all active goals, ordered by sort_order."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT id, goal_type, target_name, target_value, start_value, "
                "created_at, completed_at, sort_order "
                "FROM skill_goals WHERE is_active = 1 ORDER BY sort_order, id"
            )
            return [
                {
                    "id": r[0], "goal_type": r[1], "target_name": r[2],
                    "target_value": r[3], "start_value": r[4],
                    "created_at": r[5], "completed_at": r[6],
                    "sort_order": r[7],
                }
                for r in cur.fetchall()
            ]

    def add_goal(
        self, goal_type: str, target_name: str, target_value: float,
        start_value: float | None = None,
    ) -> int:
        """Add a new goal. Returns the goal ID."""
        from datetime import datetime, timezone
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO skill_goals "
                "(goal_type, target_name, target_value, start_value, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (goal_type, target_name, target_value, start_value,
                 datetime.now(timezone.utc).isoformat()),
            )
            self._conn.commit()
            return cur.lastrowid

    def update_goal(self, goal_id: int, **kwargs) -> None:
        """Update goal fields (target_value, is_active, sort_order, etc.)."""
        allowed = {"target_value", "start_value", "is_active", "sort_order", "completed_at"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with self._lock:
            self._conn.execute(
                f"UPDATE skill_goals SET {set_clause} WHERE id = ?",
                (*updates.values(), goal_id),
            )
            self._conn.commit()

    def delete_goal(self, goal_id: int) -> None:
        """Delete a goal permanently."""
        with self._lock:
            self._conn.execute("DELETE FROM skill_goals WHERE id = ?", (goal_id,))
            self._conn.commit()

    def complete_goal(self, goal_id: int) -> None:
        """Mark a goal as completed with current timestamp."""
        from datetime import datetime, timezone
        with self._lock:
            self._conn.execute(
                "UPDATE skill_goals SET completed_at = ?, is_active = 0 WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), goal_id),
            )
            self._conn.commit()

    # Tracker missions
    def get_tracked_missions(self) -> list[dict]:
        """Get all tracked missions ordered by sort_order."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT mission_id, name, planet, cooldown_duration, "
                "cooldown_starts_on, cooldown_ms, sort_order, cooldown_started_at, "
                "notify, notify_minutes_before, start_location, has_expiry "
                "FROM tracker_missions ORDER BY sort_order, id"
            )
            import json
            results = []
            for r in cur.fetchall():
                loc = None
                if r[10]:
                    try:
                        loc = json.loads(r[10])
                    except (json.JSONDecodeError, TypeError):
                        pass
                results.append({
                    "id": r[0], "name": r[1], "planet": r[2],
                    "cooldown_duration": r[3], "cooldown_starts_on": r[4],
                    "cooldown_ms": r[5], "order": r[6],
                    "cooldown_started_at": r[7],
                    "notify": bool(r[8]), "notify_minutes_before": r[9],
                    "start_location": loc, "has_expiry": bool(r[11]),
                })
            return results

    def upsert_tracked_mission(self, m: dict) -> None:
        """Insert or update a tracked mission."""
        import json
        loc_json = json.dumps(m.get("start_location")) if m.get("start_location") else None
        with self._lock:
            self._conn.execute(
                "INSERT INTO tracker_missions "
                "(mission_id, name, planet, cooldown_duration, cooldown_starts_on, "
                "cooldown_ms, sort_order, cooldown_started_at, notify, "
                "notify_minutes_before, start_location, has_expiry, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(mission_id) DO UPDATE SET "
                "name=excluded.name, planet=excluded.planet, "
                "cooldown_duration=excluded.cooldown_duration, "
                "cooldown_starts_on=excluded.cooldown_starts_on, "
                "cooldown_ms=excluded.cooldown_ms, sort_order=excluded.sort_order, "
                "cooldown_started_at=excluded.cooldown_started_at, "
                "notify=excluded.notify, notify_minutes_before=excluded.notify_minutes_before, "
                "start_location=excluded.start_location, has_expiry=excluded.has_expiry",
                (
                    m["id"], m.get("name", "?"), m.get("planet"),
                    m.get("cooldown_duration"), m.get("cooldown_starts_on", "Completion"),
                    m.get("cooldown_ms", 86_400_000), m.get("order", 0),
                    m.get("cooldown_started_at"), int(m.get("notify", True)),
                    m.get("notify_minutes_before", 5), loc_json,
                    int(m.get("has_expiry", False)),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self._conn.commit()

    def save_tracked_missions(self, missions: list[dict]) -> None:
        """Replace all tracked missions atomically."""
        import json
        with self._lock:
            self._conn.execute("DELETE FROM tracker_missions")
            for m in missions:
                loc_json = json.dumps(m.get("start_location")) if m.get("start_location") else None
                self._conn.execute(
                    "INSERT INTO tracker_missions "
                    "(mission_id, name, planet, cooldown_duration, cooldown_starts_on, "
                    "cooldown_ms, sort_order, cooldown_started_at, notify, "
                    "notify_minutes_before, start_location, has_expiry, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        m["id"], m.get("name", "?"), m.get("planet"),
                        m.get("cooldown_duration"),
                        m.get("cooldown_starts_on", "Completion"),
                        m.get("cooldown_ms", 86_400_000), m.get("order", 0),
                        m.get("cooldown_started_at"), int(m.get("notify", True)),
                        m.get("notify_minutes_before", 5), loc_json,
                        int(m.get("has_expiry", False)),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            self._conn.commit()

    def delete_tracked_mission(self, mission_id: int) -> None:
        """Remove a tracked mission by its API mission_id."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM tracker_missions WHERE mission_id = ?", (mission_id,)
            )
            self._conn.commit()

    # Custom dailies
    def get_custom_dailies(self) -> list[dict]:
        """Get all custom dailies ordered by sort_order."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT id, name, cooldown_duration, cooldown_starts_on, "
                "cooldown_ms, sort_order, cooldown_started_at, notify, "
                "notify_minutes_before, waypoint, enabled "
                "FROM custom_dailies ORDER BY sort_order, id"
            )
            results = []
            for r in cur.fetchall():
                results.append({
                    "id": f"c_{r[0]}",
                    "is_custom": True,
                    "name": r[1],
                    "cooldown_duration": r[2],
                    "cooldown_starts_on": r[3],
                    "cooldown_ms": r[4],
                    "order": r[5],
                    "cooldown_started_at": r[6],
                    "notify": bool(r[7]),
                    "notify_minutes_before": r[8],
                    "waypoint": r[9] or "",
                    "enabled": bool(r[10]),
                    "has_expiry": False,
                })
            return results

    def save_custom_dailies(self, dailies: list[dict]) -> None:
        """Replace all custom dailies atomically."""
        with self._lock:
            self._conn.execute("DELETE FROM custom_dailies")
            for m in dailies:
                raw_id = m["id"]
                if isinstance(raw_id, str) and raw_id.startswith("c_"):
                    raw_id = int(raw_id[2:])
                self._conn.execute(
                    "INSERT INTO custom_dailies "
                    "(id, name, cooldown_duration, cooldown_starts_on, "
                    "cooldown_ms, sort_order, cooldown_started_at, notify, "
                    "notify_minutes_before, waypoint, enabled, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        raw_id, m.get("name", "?"),
                        m.get("cooldown_duration", "1 day"),
                        m.get("cooldown_starts_on", "Completion"),
                        m.get("cooldown_ms", 86_400_000), m.get("order", 0),
                        m.get("cooldown_started_at"), int(m.get("notify", True)),
                        m.get("notify_minutes_before", 5),
                        m.get("waypoint", ""),
                        int(m.get("enabled", True)),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            self._conn.commit()

    def delete_custom_daily(self, daily_id: int) -> None:
        """Remove a custom daily by its integer id."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM custom_dailies WHERE id = ?", (daily_id,)
            )
            self._conn.commit()

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

    # Loot events (standalone, tracker-agnostic)
    def insert_loot_events(self, events: list[tuple]):
        """Batch insert loot events.

        Each tuple: (timestamp_iso, item_name, item_id_or_None, quantity, value_ped).
        """
        if not events:
            return
        with self._lock:
            self._conn.executemany(
                "INSERT INTO loot_events (timestamp, item_name, item_id, quantity, value_ped) "
                "VALUES (?, ?, ?, ?, ?)",
                events,
            )
            self._auto_commit()

    def get_loot_events_in_range(self, from_ts: str, to_ts: str) -> list[dict]:
        """Get all loot events between two ISO timestamps (inclusive)."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM loot_events WHERE timestamp >= ? AND timestamp <= ? "
                "ORDER BY timestamp, id",
                (from_ts, to_ts),
            )
            rows = [dict(r) for r in cur.fetchall()]
            self._conn.row_factory = None
            return rows

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

    def get_all_trades(self, max_age_hours: int = 0) -> list[dict]:
        """Read trade messages from the local DB (for ingestion re-submission).

        Args:
            max_age_hours: If > 0, only return trades newer than this many hours.
                          0 means return all (used by reparse).
        """
        with self._lock:
            if max_age_hours > 0:
                cur = self._conn.execute(
                    "SELECT timestamp, channel, username, message FROM trade_messages "
                    "WHERE timestamp >= datetime('now', ? || ' hours') ORDER BY id",
                    (f"-{max_age_hours}",),
                )
            else:
                cur = self._conn.execute(
                    "SELECT timestamp, channel, username, message FROM trade_messages ORDER BY id"
                )
            return [
                {"timestamp": r[0], "channel": r[1], "username": r[2], "message": r[3]}
                for r in cur.fetchall()
            ]

    def iter_globals(self, batch_size: int = 2000):
        """Yield globals in batches to avoid loading the entire table into RAM."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT timestamp, global_type, player_name, target_name, "
                "value, value_unit, location, is_hof, is_ath FROM globals ORDER BY id"
            )
            while True:
                rows = cur.fetchmany(batch_size)
                if not rows:
                    break
                for r in rows:
                    yield {
                        "timestamp": r[0], "type": r[1], "player": r[2],
                        "target": r[3], "value": r[4], "unit": r[5],
                        "location": r[6], "hof": bool(r[7]), "ath": bool(r[8]),
                    }

    def iter_trades(self, max_age_hours: int = 0, batch_size: int = 2000):
        """Yield trade messages in batches to avoid loading all into RAM."""
        with self._lock:
            if max_age_hours > 0:
                cur = self._conn.execute(
                    "SELECT timestamp, channel, username, message FROM trade_messages "
                    "WHERE timestamp >= datetime('now', ? || ' hours') ORDER BY id",
                    (f"-{max_age_hours}",),
                )
            else:
                cur = self._conn.execute(
                    "SELECT timestamp, channel, username, message "
                    "FROM trade_messages ORDER BY id"
                )
            while True:
                rows = cur.fetchmany(batch_size)
                if not rows:
                    break
                for r in rows:
                    yield {
                        "timestamp": r[0], "channel": r[1],
                        "username": r[2], "message": r[3],
                    }

    def count_globals(self) -> int:
        """Return the number of globals in the local DB."""
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM globals")
            return cur.fetchone()[0]

    def count_trades(self, max_age_hours: int = 0) -> int:
        """Return the number of trade messages in the local DB."""
        with self._lock:
            if max_age_hours > 0:
                cur = self._conn.execute(
                    "SELECT COUNT(*) FROM trade_messages "
                    "WHERE timestamp >= datetime('now', ? || ' hours')",
                    (f"-{max_age_hours}",),
                )
            else:
                cur = self._conn.execute("SELECT COUNT(*) FROM trade_messages")
            return cur.fetchone()[0]

    def fetch_globals_batch(self, limit: int = 500) -> list[dict]:
        """Fetch up to *limit* globals ordered by id. Lock-safe (no cursor leak)."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT timestamp, global_type, player_name, target_name, "
                "value, value_unit, location, is_hof, is_ath "
                "FROM globals ORDER BY id LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        return [
            {"timestamp": r[0], "type": r[1], "player": r[2],
             "target": r[3], "value": r[4], "unit": r[5],
             "location": r[6], "hof": bool(r[7]), "ath": bool(r[8])}
            for r in rows
        ]

    def fetch_trades_batch(self, limit: int = 500, max_age_hours: int = 0) -> list[dict]:
        """Fetch up to *limit* trade messages ordered by id. Lock-safe."""
        with self._lock:
            if max_age_hours > 0:
                cur = self._conn.execute(
                    "SELECT timestamp, channel, username, message "
                    "FROM trade_messages "
                    "WHERE timestamp >= datetime('now', ? || ' hours') "
                    "ORDER BY id LIMIT ?",
                    (f"-{max_age_hours}", limit),
                )
            else:
                cur = self._conn.execute(
                    "SELECT timestamp, channel, username, message "
                    "FROM trade_messages ORDER BY id LIMIT ?",
                    (limit,),
                )
            rows = cur.fetchall()
        return [
            {"timestamp": r[0], "channel": r[1],
             "username": r[2], "message": r[3]}
            for r in rows
        ]

    # Trade messages
    def insert_trade_message(self, timestamp: str, channel: str, username: str, message: str):
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO trade_messages (timestamp, channel, username, message) VALUES (?, ?, ?, ?)",
                (timestamp, channel, username, message)
            )
            self._auto_commit()

    def upsert_local_skill_values(
        self,
        skill_values: dict[str, float],
        *,
        source: str = "local",
        dirty: bool = False,
        imported_at: str | None = None,
    ) -> int:
        """Upsert latest local skill values and append change history rows.

        Returns number of rows where value changed (insert/update).
        """
        if not skill_values:
            return 0

        ts = imported_at or datetime.now(timezone.utc).isoformat()
        changed = 0
        dirty_int = 1 if dirty else 0

        # Pre-parse values outside the lock to reduce hold time
        parsed = []
        for skill_name, raw_value in skill_values.items():
            try:
                parsed.append((skill_name, float(raw_value)))
            except (TypeError, ValueError):
                continue

        with self._lock:
            # Single bulk fetch replaces N per-skill SELECTs
            cur = self._conn.execute(
                "SELECT skill_name, current_points FROM local_skill_values"
            )
            existing = {row[0]: float(row[1]) for row in cur.fetchall()}

            # Categorise into batches
            new_values = []
            new_history = []
            changed_values = []
            changed_history = []
            unchanged_touch = []

            for skill_name, new_value in parsed:
                if skill_name not in existing:
                    new_values.append((skill_name, new_value, ts, dirty_int))
                    new_history.append((ts, skill_name, None, new_value, source))
                    changed += 1
                else:
                    old_value = existing[skill_name]
                    if abs(old_value - new_value) > 1e-9:
                        changed_values.append((new_value, ts, dirty_int, skill_name))
                        changed_history.append((ts, skill_name, old_value, new_value, source))
                        changed += 1
                    else:
                        unchanged_touch.append((ts, dirty_int, skill_name))

            if new_values:
                self._conn.executemany(
                    "INSERT INTO local_skill_values (skill_name, current_points, updated_at, dirty) "
                    "VALUES (?, ?, ?, ?)",
                    new_values,
                )
            if new_history:
                self._conn.executemany(
                    "INSERT INTO local_skill_history (imported_at, skill_name, old_value, new_value, source) "
                    "VALUES (?, ?, ?, ?, ?)",
                    new_history,
                )
            if changed_values:
                self._conn.executemany(
                    "UPDATE local_skill_values "
                    "SET current_points = ?, updated_at = ?, dirty = ? "
                    "WHERE skill_name = ?",
                    changed_values,
                )
            if changed_history:
                self._conn.executemany(
                    "INSERT INTO local_skill_history (imported_at, skill_name, old_value, new_value, source) "
                    "VALUES (?, ?, ?, ?, ?)",
                    changed_history,
                )
            if unchanged_touch:
                self._conn.executemany(
                    "UPDATE local_skill_values SET updated_at = ?, dirty = ? "
                    "WHERE skill_name = ?",
                    unchanged_touch,
                )

            self._auto_commit()

        return changed

    def get_local_skill_values(self) -> dict[str, float]:
        """Get latest local skill values tracked for sync."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT skill_name, current_points "
                "FROM local_skill_values ORDER BY skill_name"
            )
            return {row[0]: float(row[1]) for row in cur.fetchall()}

    def get_dirty_local_skill_values(self) -> dict[str, float]:
        """Get locally changed values that are pending remote sync."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT skill_name, current_points "
                "FROM local_skill_values WHERE dirty = 1 ORDER BY skill_name"
            )
            return {row[0]: float(row[1]) for row in cur.fetchall()}

    def mark_local_skill_values_clean(self, skill_names: list[str] | None = None):
        """Clear dirty flags for all or specific skills."""
        with self._lock:
            if skill_names:
                placeholders = ",".join("?" for _ in skill_names)
                self._conn.execute(
                    f"UPDATE local_skill_values SET dirty = 0 "
                    f"WHERE skill_name IN ({placeholders})",
                    tuple(skill_names),
                )
            else:
                self._conn.execute("UPDATE local_skill_values SET dirty = 0")
            self._auto_commit()

    def get_latest_skill_values(self) -> dict[str, float]:
        """Get latest known value per skill from local storage."""
        return self.get_local_skill_values()

    def get_local_skill_history(
        self,
        skill_names: list[str] | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict]:
        """Get local skill history from sync-state changes.

        Returns list of dicts matching server history shape:
        {imported_at, skill_name, new_value}
        """
        sql = (
            "SELECT imported_at, skill_name, new_value "
            "FROM local_skill_history WHERE 1=1"
        )
        params: list = []

        if skill_names:
            placeholders = ",".join("?" for _ in skill_names)
            sql += f" AND skill_name IN ({placeholders})"
            params.extend(skill_names)

        if from_date:
            sql += " AND datetime(imported_at) >= datetime(?)"
            params.append(from_date)

        if to_date:
            sql += " AND datetime(imported_at) <= datetime(?)"
            params.append(to_date)

        sql += " ORDER BY datetime(imported_at) DESC, id DESC"

        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return [
                {
                    "imported_at": row[0],
                    "skill_name": row[1],
                    "new_value": float(row[2]),
                }
                for row in cur.fetchall()
            ]

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
                "is_blacklisted, is_refining_output, is_in_loot_table, "
                "is_enhancer_shrapnel) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (encounter_id, li.item_name, li.quantity, li.value_ped,
                     int(li.is_blacklisted), int(li.is_refining_output),
                     int(li.is_in_loot_table),
                     int(getattr(li, 'is_enhancer_shrapnel', False)))
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

    def get_recent_sessions(self, limit: int = 50) -> list[dict]:
        """Get recent hunt sessions with aggregate stats."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute("""
                SELECT s.*,
                       COUNT(CASE WHEN e.outcome = 'kill' THEN 1 END) AS kills,
                       COUNT(CASE WHEN e.death_count > 0 THEN 1 END) AS deaths,
                       COALESCE(SUM(e.cost), 0) AS total_cost,
                       COALESCE(SUM(e.loot_total_ped), 0) AS total_loot
                FROM hunt_sessions s
                LEFT JOIN mob_encounters e ON e.session_id = s.id
                    AND e.outcome NOT IN ('merged')
                GROUP BY s.id
                ORDER BY s.start_time DESC
                LIMIT ?
            """, (limit,))
            rows = [dict(r) for r in cur.fetchall()]
            self._conn.row_factory = None
            return rows

    def get_session_hunts_with_stats(self, session_id: str) -> list[dict]:
        """Get hunts within a session with aggregate stats."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute("""
                SELECT h.*,
                       COUNT(CASE WHEN e.outcome = 'kill' THEN 1 END) AS kills,
                       COALESCE(SUM(e.cost), 0) AS total_cost,
                       COALESCE(SUM(e.loot_total_ped), 0) AS total_loot
                FROM hunts h
                LEFT JOIN mob_encounters e ON e.hunt_id = h.id
                    AND e.outcome NOT IN ('merged')
                WHERE h.session_id = ?
                GROUP BY h.id
                ORDER BY h.start_time ASC
            """, (session_id,))
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

    # Session loadout events (enhancer tracking, loadout history)
    def insert_loadout_event(self, session_id: str, timestamp: str,
                             event_type: str, description: str = None,
                             loadout_data: str = None, enhancer_delta: str = None,
                             tool_name: str = None, cost_per_shot: float = None,
                             damage_min: float = None, damage_max: float = None) -> int:
        """Insert a loadout event and return its ID."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO session_loadout_events "
                "(session_id, timestamp, event_type, description, loadout_data, "
                "enhancer_delta, tool_name, cost_per_shot, damage_min, damage_max) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, timestamp, event_type, description, loadout_data,
                 enhancer_delta, tool_name, cost_per_shot, damage_min, damage_max)
            )
            self._auto_commit()
            return cur.lastrowid

    def get_session_loadout_events(self, session_id: str) -> list[dict]:
        """Get all loadout events for a session, ordered by timestamp."""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT * FROM session_loadout_events WHERE session_id = ? "
                "ORDER BY timestamp",
                (session_id,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            self._conn.row_factory = None
            return rows

    def update_loadout_event(self, event_id: int, **kwargs):
        """Update a loadout event by ID."""
        if not kwargs:
            return
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [event_id]
        with self._lock:
            self._conn.execute(
                f"UPDATE session_loadout_events SET {set_clause} WHERE id = ?",
                tuple(values)
            )
            self._auto_commit()

    def delete_loadout_event(self, event_id: int):
        """Delete a loadout event by ID."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM session_loadout_events WHERE id = ?",
                (event_id,)
            )
            self._auto_commit()

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
        # Pre-serialize JSON outside the lock to reduce hold time
        items_json = json.dumps(items)
        unresolved_json = json.dumps(unresolved)
        ts = datetime.now().isoformat()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO pending_inventory_import (items, unresolved, raw_count, imported_at) "
                "VALUES (?, ?, ?, ?)",
                (items_json, unresolved_json, raw_count, ts)
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
            raw_rows = [dict(r) for r in cur.fetchall()]
            self._conn.row_factory = None

        # JSON parsing outside the lock to reduce hold time
        for d in raw_rows:
            d['items'] = json.loads(d['items'])
            d['unresolved'] = json.loads(d['unresolved'])
        return raw_rows

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

        Uses a temp table + batched DELETE for efficiency (single statement
        instead of one DELETE per item).
        """
        if not items:
            return 0
        with self._lock:
            self._conn.execute(
                "CREATE TEMP TABLE IF NOT EXISTS _del_globals "
                "(timestamp TEXT, global_type TEXT, player_name TEXT, "
                "target_name TEXT, value REAL)"
            )
            self._conn.execute("DELETE FROM _del_globals")
            self._conn.executemany(
                "INSERT INTO _del_globals VALUES (?, ?, ?, ?, ?)",
                ((i["timestamp"], i["type"], i["player"], i["target"], i["value"])
                 for i in items),
            )
            cur = self._conn.execute(
                "DELETE FROM globals WHERE EXISTS ("
                "SELECT 1 FROM _del_globals d "
                "WHERE d.timestamp = globals.timestamp "
                "AND d.global_type = globals.global_type "
                "AND d.player_name = globals.player_name "
                "AND d.target_name = globals.target_name "
                "AND d.value = globals.value)"
            )
            deleted = cur.rowcount
            self._conn.commit()
        return deleted

    def delete_ingested_trades(self, items: list[dict]) -> int:
        """Delete specific trade messages confirmed processed by the server.

        Uses a temp table + batched DELETE for efficiency.
        """
        if not items:
            return 0
        with self._lock:
            self._conn.execute(
                "CREATE TEMP TABLE IF NOT EXISTS _del_trades "
                "(timestamp TEXT, channel TEXT, username TEXT, message TEXT)"
            )
            self._conn.execute("DELETE FROM _del_trades")
            self._conn.executemany(
                "INSERT INTO _del_trades VALUES (?, ?, ?, ?)",
                ((i["timestamp"], i["channel"], i["username"], i["message"])
                 for i in items),
            )
            cur = self._conn.execute(
                "DELETE FROM trade_messages WHERE EXISTS ("
                "SELECT 1 FROM _del_trades d "
                "WHERE d.timestamp = trade_messages.timestamp "
                "AND d.channel = trade_messages.channel "
                "AND d.username = trade_messages.username "
                "AND d.message = trade_messages.message)"
            )
            deleted = cur.rowcount
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

    def prune_old_data(self) -> dict[str, int]:
        """Delete old parsed data that is no longer needed.

        - Trade messages older than 2 days (server rejects them anyway)
        - Combat events (no longer recorded; clear any legacy data)
        - Loot groups/items (no longer recorded; clear any legacy data)

        Skill gains are kept permanently.

        Returns dict of {table_name: rows_deleted}.
        """
        deleted = {}
        with self._lock:
            # Trade messages older than 2 days are never uploadable
            cur = self._conn.execute(
                "DELETE FROM trade_messages WHERE timestamp < datetime('now', '-2 days')"
            )
            if cur.rowcount > 0:
                deleted["trade_messages"] = cur.rowcount
            # Combat events are no longer recorded — clear legacy data
            cur = self._conn.execute("DELETE FROM combat_events")
            if cur.rowcount > 0:
                deleted["combat_events"] = cur.rowcount
            # Loot data is no longer recorded — clear legacy data
            cur = self._conn.execute("DELETE FROM loot_items")
            if cur.rowcount > 0:
                deleted["loot_items"] = cur.rowcount
            cur = self._conn.execute("DELETE FROM loot_groups")
            if cur.rowcount > 0:
                deleted["loot_groups"] = cur.rowcount
            if deleted:
                self._conn.commit()
        return deleted

    def vacuum(self) -> None:
        """Reclaim disk space after large deletes. Must run outside a transaction."""
        with self._lock:
            self._conn.execute("VACUUM")

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

    # ------------------------------------------------------------------
    # Screenshots
    # ------------------------------------------------------------------

    def insert_screenshot(self, file_path: str, file_type: str, created_at: str,
                          global_id: int | None = None,
                          file_hash: str | None = None) -> int:
        """Insert a screenshot/clip record. Returns the new row ID."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO screenshots "
                "(file_path, file_type, created_at, global_id, file_hash) "
                "VALUES (?, ?, ?, ?, ?)",
                (file_path, file_type, created_at, global_id, file_hash),
            )
            self._auto_commit()
            return cur.lastrowid

    def update_screenshot_notes(self, screenshot_id: int, notes: str) -> None:
        """Update the notes for a screenshot."""
        with self._lock:
            self._conn.execute(
                "UPDATE screenshots SET notes = ? WHERE id = ?",
                (notes, screenshot_id),
            )
            self._auto_commit()

    def update_screenshot_notes_by_path(self, file_path: str, notes: str) -> None:
        """Update notes for a screenshot identified by file path."""
        with self._lock:
            self._conn.execute(
                "UPDATE screenshots SET notes = ? WHERE file_path = ?",
                (notes, file_path),
            )
            self._auto_commit()

    def update_screenshot_upload(self, screenshot_id: int, status: str,
                                 server_global_id: int | None = None) -> None:
        """Update upload status and optional server-side global ID."""
        with self._lock:
            if server_global_id is not None:
                self._conn.execute(
                    "UPDATE screenshots SET upload_status = ?, server_global_id = ?, "
                    "uploaded_at = ? WHERE id = ?",
                    (status, server_global_id,
                     datetime.now(timezone.utc).isoformat(), screenshot_id),
                )
            else:
                self._conn.execute(
                    "UPDATE screenshots SET upload_status = ? WHERE id = ?",
                    (status, screenshot_id),
                )
            self._auto_commit()

    def update_screenshot_video_url(self, screenshot_id: int, video_url: str) -> None:
        """Update the video URL for a screenshot/clip record."""
        with self._lock:
            self._conn.execute(
                "UPDATE screenshots SET video_url = ? WHERE id = ?",
                (video_url, screenshot_id),
            )
            self._auto_commit()

    def update_screenshot_hash(self, screenshot_id: int, file_hash: str) -> None:
        """Set the file hash on an existing screenshot record."""
        with self._lock:
            self._conn.execute(
                "UPDATE screenshots SET file_hash = ? WHERE id = ?",
                (file_hash, screenshot_id),
            )
            self._auto_commit()

    def get_uploaded_screenshot_by_hash(self, file_hash: str) -> dict | None:
        """Find an uploaded screenshot with matching hash."""
        if not file_hash:
            return None
        with self._lock:
            cur = self._conn.execute(
                "SELECT id, file_path, uploaded_at FROM screenshots "
                "WHERE file_hash = ? AND upload_status = 'uploaded' LIMIT 1",
                (file_hash,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"id": row[0], "file_path": row[1], "uploaded_at": row[2]}

    def get_screenshot_by_path(self, file_path: str) -> dict | None:
        """Get screenshot record by file path."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT s.id, s.file_path, s.file_type, s.created_at, "
                "s.global_id, s.notes, s.upload_status, s.server_global_id, "
                "s.uploaded_at, s.video_url, "
                "g.global_type, g.is_hof, g.is_ath, g.player_name, g.target_name, g.value, "
                "s.file_hash "
                "FROM screenshots s "
                "LEFT JOIN globals g ON s.global_id = g.id "
                "WHERE s.file_path = ?",
                (file_path,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0], "file_path": row[1], "file_type": row[2],
                "created_at": row[3], "global_id": row[4], "notes": row[5],
                "upload_status": row[6], "server_global_id": row[7],
                "uploaded_at": row[8], "video_url": row[9],
                "global_type": row[10], "is_hof": bool(row[11]) if row[11] is not None else False,
                "is_ath": bool(row[12]) if row[12] is not None else False,
                "player_name": row[13], "target_name": row[14], "value": row[15],
                "file_hash": row[16],
            }

    def get_screenshot_info_batch(self, paths: list[str]) -> dict[str, dict]:
        """Bulk fetch screenshot info keyed by file path.

        Returns {path: {id, has_notes, global_type, is_hof, is_ath, upload_status, ...}}.
        """
        if not paths:
            return {}
        with self._lock:
            placeholders = ",".join("?" for _ in paths)
            cur = self._conn.execute(
                f"SELECT s.file_path, s.id, s.notes, s.upload_status, "
                f"s.server_global_id, s.global_id, "
                f"g.global_type, g.is_hof, g.is_ath, s.video_url, s.file_hash, "
                f"g.target_name, g.value "
                f"FROM screenshots s "
                f"LEFT JOIN globals g ON s.global_id = g.id "
                f"WHERE s.file_path IN ({placeholders})",
                tuple(paths),
            )
            result = {}
            for row in cur.fetchall():
                result[row[0]] = {
                    "id": row[1],
                    "has_notes": bool(row[2]),
                    "global_type": row[6],
                    "is_hof": bool(row[7]) if row[7] is not None else False,
                    "is_ath": bool(row[8]) if row[8] is not None else False,
                    "upload_status": row[3] or "none",
                    "server_global_id": row[4],
                    "global_id": row[5],
                    "video_url": row[9],
                    "file_hash": row[10],
                    "target_name": row[11],
                    "value": row[12],
                }
            return result

    def find_recent_own_global(self, timestamp_iso: str, player_name: str,
                               target_name: str, window_seconds: int = 30) -> int | None:
        """Find a global matching the given criteria within a time window.

        Returns the globals.id or None.
        """
        with self._lock:
            cur = self._conn.execute(
                "SELECT id FROM globals "
                "WHERE player_name = ? AND target_name = ? "
                "AND abs(julianday(timestamp) - julianday(?)) * 86400 < ? "
                "ORDER BY abs(julianday(timestamp) - julianday(?)) "
                "LIMIT 1",
                (player_name, target_name, timestamp_iso, window_seconds, timestamp_iso),
            )
            row = cur.fetchone()
            return row[0] if row else None

    def delete_screenshot_by_path(self, file_path: str) -> None:
        """Delete a screenshot record by file path."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM screenshots WHERE file_path = ?", (file_path,)
            )
            self._auto_commit()
