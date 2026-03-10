"""SQLite-backed disk cache for API endpoint responses.

Replaces the old per-endpoint JSON file cache with a single SQLite database
that stores items individually with indexed columns for targeted lookups.
"""

import json
import os
import sqlite3
import threading
import time
from collections.abc import Iterator
from pathlib import Path

from ..core.logger import get_logger

log = get_logger("CacheDB")

# SQLite >= 3.45 supports jsonb() for compact binary JSON storage.
_HAS_JSONB = sqlite3.sqlite_version_info >= (3, 45, 0)

SCHEMA = """
CREATE TABLE IF NOT EXISTS cache_meta (
    endpoint    TEXT PRIMARY KEY,
    fetched_at  REAL NOT NULL,
    is_list     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cache_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint    TEXT NOT NULL,
    data        BLOB NOT NULL,
    name        TEXT GENERATED ALWAYS AS (
                    COALESCE(json_extract(data, '$.DisplayName'), json_extract(data, '$.Name'))
                ) VIRTUAL,
    type        TEXT GENERATED ALWAYS AS (json_extract(data, '$.Type')) VIRTUAL,
    entity_type TEXT GENERATED ALWAYS AS (json_extract(data, '$.EntityType')) VIRTUAL
);

CREATE INDEX IF NOT EXISTS idx_cache_items_endpoint ON cache_items(endpoint);
CREATE INDEX IF NOT EXISTS idx_cache_items_name ON cache_items(name);
CREATE INDEX IF NOT EXISTS idx_cache_items_type ON cache_items(type);
"""


class CacheDB:
    """SQLite cache layer for API endpoint data. Thread-safe via internal lock."""

    def __init__(self, db_path: Path):
        os.makedirs(db_path.parent, exist_ok=True)
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA cache_size=-8000")  # 8 MB page cache
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._migrate()

    def _migrate(self):
        """Add columns that may be missing from older databases."""
        try:
            self._conn.execute(
                "ALTER TABLE cache_meta ADD COLUMN is_list INTEGER NOT NULL DEFAULT 1"
            )
            # Column was missing — clear cache since dict endpoints were stored
            # incorrectly before this column existed.
            self._conn.execute("DELETE FROM cache_items")
            self._conn.execute("DELETE FROM cache_meta")
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

    def get(self, endpoint: str, max_age: float) -> list | dict | None:
        """Return cached data for *endpoint* if fresher than *max_age* seconds.

        Returns the original response shape (list or dict).
        Returns ``None`` on cache miss or stale data.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT fetched_at, is_list FROM cache_meta WHERE endpoint = ?",
                (endpoint,),
            ).fetchone()
            if row is None or (time.time() - row[0]) >= max_age:
                return None
            rows = self._conn.execute(
                "SELECT json(data) FROM cache_items WHERE endpoint = ?",
                (endpoint,),
            ).fetchall()
        items = [json.loads(r[0]) for r in rows]
        if not row[1] and len(items) == 1:
            return items[0]  # Originally a dict, unwrap
        return items

    def get_iter(self, endpoint: str, max_age: float) -> Iterator[dict] | None:
        """Like :meth:`get` but returns a lazy iterator over items.

        The meta-check happens under the lock; iteration proceeds outside the
        lock since WAL readers don't block writers.  Returns ``None`` on miss.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT fetched_at FROM cache_meta WHERE endpoint = ?",
                (endpoint,),
            ).fetchone()
            if row is None or (time.time() - row[0]) >= max_age:
                return None

        # Cursor iteration outside lock — WAL allows concurrent readers.
        cursor = self._conn.execute(
            "SELECT json(data) FROM cache_items WHERE endpoint = ?",
            (endpoint,),
        )
        return (json.loads(r[0]) for r in cursor)

    def get_stale(self, endpoint: str) -> list | dict | None:
        """Return cached data regardless of age (fallback for API failures).

        Returns ``None`` if there is no data at all for *endpoint*.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT fetched_at, is_list FROM cache_meta WHERE endpoint = ?",
                (endpoint,),
            ).fetchone()
            if row is None:
                return None
            rows = self._conn.execute(
                "SELECT json(data) FROM cache_items WHERE endpoint = ?",
                (endpoint,),
            ).fetchall()
        items = [json.loads(r[0]) for r in rows]
        if not row[1] and len(items) == 1:
            return items[0]
        return items

    def put(self, endpoint: str, items: list[dict], *, is_list: bool = True) -> None:
        """Store *items* for *endpoint*, replacing any existing data."""
        now = time.time()
        encode = "jsonb(?)" if _HAS_JSONB else "?"
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN")
            try:
                cur.execute(
                    "DELETE FROM cache_items WHERE endpoint = ?", (endpoint,)
                )
                cur.executemany(
                    f"INSERT INTO cache_items (endpoint, data) VALUES (?, {encode})",
                    [(endpoint, json.dumps(item)) for item in items],
                )
                cur.execute(
                    "INSERT OR REPLACE INTO cache_meta (endpoint, fetched_at, is_list) "
                    "VALUES (?, ?, ?)",
                    (endpoint, now, 1 if is_list else 0),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def delete(self, endpoint: str) -> None:
        """Remove all cached data for a single *endpoint*."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN")
            try:
                cur.execute(
                    "DELETE FROM cache_items WHERE endpoint = ?", (endpoint,)
                )
                cur.execute(
                    "DELETE FROM cache_meta WHERE endpoint = ?", (endpoint,)
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def clear(self) -> None:
        """Remove all cached data for every endpoint."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN")
            try:
                cur.execute("DELETE FROM cache_items")
                cur.execute("DELETE FROM cache_meta")
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def close(self) -> None:
        """Close the database connection."""
        try:
            self._conn.close()
        except Exception:
            pass
