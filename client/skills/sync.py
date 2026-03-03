"""Skill data synchronization with Nexus server.

Skills are synced from Nexus when authenticated. Manual edits are corrections
only (not new versions). New versions are only added by scanning (triggering a delta).
"""

from __future__ import annotations

from ..core.logger import get_logger

log = get_logger("SkillSync")


class SkillDataManager:
    """Manages skill values and metadata with server sync."""

    def __init__(self, data_client, nexus_client=None):
        self._data_client = data_client
        self._nexus_client = nexus_client

        # Skill values: {skill_name: raw_points}
        self._skill_values: dict[str, float] = {}
        self._synced = False

        # Metadata caches (from public API)
        self._skill_metadata: list[dict] | None = None
        self._professions: list[dict] | None = None
        self._skill_ranks: list[dict] | None = None

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
            result = self._nexus_client.get_skills()
            if result and isinstance(result, dict):
                skills = result.get("skills")
                if isinstance(skills, dict):
                    self._skill_values = {
                        k: float(v) for k, v in skills.items()
                        if isinstance(v, (int, float))
                    }
                    self._synced = True
                    log.info("Synced %d skills from Nexus", len(self._skill_values))
                    return True
            return False
        except Exception as e:
            log.error("Failed to sync from Nexus: %s", e)
            return False

    def apply_correction(self, skill_name: str, new_value: float) -> bool:
        """Apply a manual correction to a skill value.

        This updates the local state and saves to server without tracking an import
        (trackImport=false), since corrections are not new scan versions.
        """
        self._skill_values[skill_name] = new_value

        if not self._nexus_client:
            return True

        try:
            result = self._nexus_client.upload_skills(
                self._skill_values, track_import=False
            )
            return result is not None
        except Exception as e:
            log.error("Failed to save correction: %s", e)
            return False

    def get_skill_value(self, name: str) -> float:
        """Get a single skill's raw points value."""
        return self._skill_values.get(name, 0)

    def get_all_values(self) -> dict[str, float]:
        """Get all skill values."""
        return dict(self._skill_values)

    def sync_scan_results(self, scanned_skills: list) -> dict:
        """Compare scanned skills against current values, compute delta.

        Returns {
            "changes": {skill_name: new_value, ...},
            "shrunk": {skill_name: (old_value, new_value), ...},
            "total_scanned": int,
        }
        """
        changes = {}
        shrunk = {}
        for skill in scanned_skills:
            name = skill.skill_name
            new_val = skill.current_points
            old_val = self._skill_values.get(name, 0)
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
        for skill in scanned_skills:
            self._skill_values[skill.skill_name] = skill.current_points

        if not self._nexus_client:
            return True

        try:
            result = self._nexus_client.upload_skills(
                self._skill_values, track_import=True
            )
            return result is not None
        except Exception as e:
            log.error("Failed to upload scan results: %s", e)
            return False

    def get_skill_history(self, skill_names=None, from_date=None, to_date=None):
        """Fetch per-skill history from server.

        Returns list of {imported_at, skill_name, new_value} or None.
        """
        if not self._nexus_client:
            return None
        try:
            return self._nexus_client.get_skill_history(
                skill_names=skill_names, from_date=from_date, to_date=to_date
            )
        except Exception as e:
            log.error("Failed to fetch skill history: %s", e)
            return None
