"""Skill data synchronization with Nexus server and local-first persistence."""

from __future__ import annotations

from ..core.logger import get_logger

log = get_logger("SkillSync")


class SkillDataManager:
    """Manages skill values and metadata with server sync."""

    def __init__(self, data_client, nexus_client=None, db=None):
        self._data_client = data_client
        self._nexus_client = nexus_client
        self._db = db

        # Skill values: {skill_name: raw_points}
        self._skill_values: dict[str, float] = {}
        self._synced = False

        # Metadata caches (from public API)
        self._skill_metadata: list[dict] | None = None
        self._professions: list[dict] | None = None
        self._skill_ranks: list[dict] | None = None

    def _persist_local_values(
        self,
        skill_values: dict[str, float],
        *,
        source: str,
        dirty: bool,
    ) -> None:
        if not self._db or not skill_values:
            return
        try:
            self._db.upsert_local_skill_values(
                skill_values,
                source=source,
                dirty=dirty,
            )
        except Exception as e:
            log.error("Failed to persist local skill values (%s): %s", source, e)

    def _sync_to_remote(self, *, track_import: bool) -> bool:
        if not self._nexus_client:
            return True
        try:
            result = self._nexus_client.upload_skills(
                self._skill_values,
                track_import=track_import,
            )
            if result is not None:
                self._persist_local_values(
                    self._skill_values,
                    source="remote_sync",
                    dirty=False,
                )
                return True
            return False
        except Exception as e:
            log.error("Failed to upload skills: %s", e)
            return False

    @property
    def skill_values(self) -> dict[str, float]:
        return self._skill_values

    @property
    def is_synced(self) -> bool:
        return self._synced

    @property
    def skill_metadata(self) -> list[dict]:
        if self._skill_metadata is None:
            self.refresh_metadata()
        return self._skill_metadata or []

    @property
    def professions(self) -> list[dict]:
        if self._professions is None:
            self.refresh_metadata()
        return self._professions or []

    @property
    def skill_ranks(self) -> list[dict]:
        if self._skill_ranks is None:
            self._skill_ranks = self._data_client.get_skill_ranks() or []
        return self._skill_ranks

    def refresh_metadata(self) -> bool:
        """Fetch skill/profession metadata from public API."""
        try:
            skills_raw = self._data_client.get_skills() or []
            profs_raw = self._data_client.get_professions() or []

            # Normalize skill metadata (match website format)
            self._skill_metadata = [
                {
                    "Name": s.get("Name", ""),
                    "Category": (s.get("Category", {}) or {}).get("Name") if isinstance(s.get("Category"), dict) else s.get("Category"),
                    "HPIncrease": (s.get("Properties") or {}).get("HpIncrease"),
                    "IsExtractable": (s.get("Properties") or {}).get("IsExtractable", True),
                    "IsHidden": (s.get("Properties") or {}).get("IsHidden", False),
                    "Professions": [
                        {
                            "Name": (p.get("Profession") or {}).get("Name", p.get("Name", "")),
                            "Weight": p.get("Weight") or 0,
                        }
                        for p in (s.get("Professions") or [])
                    ],
                }
                for s in skills_raw
                if s.get("Name")
            ]

            # Normalize profession metadata
            self._professions = [
                {
                    "Name": p.get("Name", ""),
                    "Category": (p.get("Category", {}) or {}).get("Name") if isinstance(p.get("Category"), dict) else p.get("Category"),
                    "Skills": [
                        {
                            "Name": (sk.get("Skill") or {}).get("Name", sk.get("Name", "")),
                            "Weight": sk.get("Weight") or 0,
                        }
                        for sk in (p.get("Skills") or [])
                    ],
                }
                for p in profs_raw
                if p.get("Name")
            ]

            log.info("Metadata refreshed: %d skills, %d professions",
                     len(self._skill_metadata), len(self._professions))
            return True
        except Exception as e:
            log.error("Failed to refresh metadata: %s", e)
            return False

    def sync_from_nexus(self) -> bool:
        """Fetch user skill values from Nexus (requires authentication).

        Returns True on success, False on failure.
        """
        if not self._nexus_client:
            return False

        try:
            local_values: dict[str, float] = {}
            dirty_local: dict[str, float] = {}
            if self._db:
                try:
                    local_values = self._db.get_local_skill_values()
                    dirty_local = self._db.get_dirty_local_skill_values()
                except Exception as e:
                    log.error("Failed to read local skill cache before sync: %s", e)

            result = self._nexus_client.get_skills()
            if result and isinstance(result, dict):
                skills = result.get("skills")
                if isinstance(skills, dict):
                    remote_values = {
                        k: float(v) for k, v in skills.items()
                        if isinstance(v, (int, float))
                    }

                    merged_values = dict(remote_values)
                    for name, value in local_values.items():
                        merged_values.setdefault(name, float(value))
                    for name, value in dirty_local.items():
                        merged_values[name] = float(value)

                    self._skill_values = merged_values

                    if dirty_local:
                        # Offline/local edits win and are pushed back to server.
                        uploaded = self._nexus_client.upload_skills(
                            merged_values, track_import=True
                        )
                        if uploaded is not None:
                            self._persist_local_values(
                                merged_values,
                                source="sync_pull_push",
                                dirty=False,
                            )
                            log.info(
                                "Synced %d skills from Nexus and pushed %d pending local changes",
                                len(merged_values),
                                len(dirty_local),
                            )
                        else:
                            clean_remote = {
                                k: v for k, v in merged_values.items()
                                if k not in dirty_local
                            }
                            self._persist_local_values(
                                clean_remote,
                                source="sync_pull",
                                dirty=False,
                            )
                            self._persist_local_values(
                                dirty_local,
                                source="sync_pending",
                                dirty=True,
                            )
                            log.warning(
                                "Synced %d skills from Nexus but %d local changes are still pending upload",
                                len(merged_values),
                                len(dirty_local),
                            )
                    else:
                        self._persist_local_values(
                            merged_values,
                            source="sync_pull",
                            dirty=False,
                        )
                        log.info("Synced %d skills from Nexus", len(merged_values))

                    self._synced = True
                    return True
            return False
        except Exception as e:
            log.error("Failed to sync from Nexus: %s", e)
            return False

    def load_from_local(self) -> bool:
        """Load latest skill values from local database."""
        if not self._db:
            return False
        try:
            values = self._db.get_latest_skill_values()
            if not values:
                return False
            self._skill_values = {k: float(v) for k, v in values.items()}
            log.info("Loaded %d skills from local DB", len(self._skill_values))
            return True
        except Exception as e:
            log.error("Failed to load skills from local DB: %s", e)
            return False

    def apply_correction(self, skill_name: str, new_value: float) -> bool:
        """Apply a manual correction to a skill value.

        This updates the local state and saves to server without tracking an import
        (trackImport=false), since corrections are not new scan versions.
        """
        self._skill_values[skill_name] = new_value
        self._persist_local_values(
            {skill_name: new_value},
            source="manual_correction",
            dirty=True,
        )

        if not self._nexus_client:
            return True

        ok = self._sync_to_remote(track_import=False)
        if not ok:
            log.error("Failed to save correction to remote API")
        return ok

    def get_skill_value(self, name: str) -> float:
        """Get a single skill's raw points value."""
        return self._skill_values.get(name, 0)

    def get_all_values(self) -> dict[str, float]:
        """Get all skill values."""
        return dict(self._skill_values)

    def sync_scan_results(self, scanned_skills: list) -> dict:
        """Compare scanned skills against persisted values, compute delta.

        Compares against DB values (not in-memory) because _on_skill_scanned
        updates the in-memory dict during scanning for live UI refresh.

        Returns {
            "changes": {skill_name: new_value, ...},
            "shrunk": {skill_name: (old_value, new_value), ...},
            "total_scanned": int,
        }
        """
        # Read persisted values from DB — the in-memory dict was already
        # overwritten during scanning for live display updates.
        persisted: dict[str, float] = {}
        if self._db:
            try:
                persisted = self._db.get_local_skill_values()
            except Exception:
                pass

        changes = {}
        shrunk = {}
        for skill in scanned_skills:
            name = skill.skill_name
            new_val = skill.current_points
            old_val = persisted.get(name, 0)
            if new_val != old_val:
                changes[name] = new_val
                if new_val < old_val:
                    shrunk[name] = (old_val, new_val)
        return {
            "changes": changes,
            "shrunk": shrunk,
            "total_scanned": len(scanned_skills),
        }

    def apply_scan_results(self, scanned_skills: list) -> bool:
        """Apply scanned skills to local state and upload as tracked import.

        Updates _skill_values with scanned values and uploads full dict
        with track_import=True to create a new version on the server.
        """
        changed: dict[str, float] = {}
        for skill in scanned_skills:
            self._skill_values[skill.skill_name] = skill.current_points
            changed[skill.skill_name] = skill.current_points
        self._persist_local_values(
            changed,
            source="scan_complete",
            dirty=True,
        )

        if not self._nexus_client:
            return True

        ok = self._sync_to_remote(track_import=True)
        if not ok:
            log.error("Failed to upload scan results to remote API")
        return ok

    def apply_imported_values(self, imported: dict[str, float]) -> bool:
        """Apply imported values locally and sync to server when available."""
        if not imported:
            return True

        normalized: dict[str, float] = {}
        for name, value in imported.items():
            try:
                normalized[str(name)] = float(value)
            except (TypeError, ValueError):
                continue

        if not normalized:
            return False

        self._skill_values.update(normalized)
        self._persist_local_values(
            normalized,
            source="manual_import",
            dirty=True,
        )

        if not self._nexus_client:
            return True

        ok = self._sync_to_remote(track_import=True)
        if not ok:
            log.error("Imported values saved locally but failed to sync to remote API")
        return ok

    def get_skill_history(self, skill_names=None, from_date=None, to_date=None):
        """Fetch per-skill history from server.

        Returns list of {imported_at, skill_name, new_value} or None.
        """
        if self._nexus_client:
            try:
                remote = self._nexus_client.get_skill_history(
                    skill_names=skill_names, from_date=from_date, to_date=to_date
                )
                if remote is not None:
                    return remote
            except Exception as e:
                log.error("Failed to fetch skill history from server: %s", e)

        if self._db:
            try:
                return self._db.get_local_skill_history(
                    skill_names=skill_names, from_date=from_date, to_date=to_date
                ) or None
            except Exception as e:
                log.error("Failed to fetch skill history from local DB: %s", e)

        return None
