"""Anonymized skill data collection for community tools.

Listens for successful skill scans and skill gain events. On first clean
scan, prompts the user to opt in. Once opted in:
- Uploads a snapshot (current skill points + full gain history)
- Sends delta updates every 1000 accumulated skill points

User ID is hashed server-side; the endpoint stores no identifiable info.
"""

from __future__ import annotations

import threading

from ..api.nexus_client import RateLimitError, ServerError
from ..core.constants import (
    EVENT_CONFIG_CHANGED,
    EVENT_OCR_COMPLETE,
    EVENT_SKILL_DATA_OPTIN_PROMPT,
    EVENT_SKILL_DATA_OPTIN_RESULT,
    EVENT_SKILL_DATA_UPLOAD_STATUS,
    EVENT_SKILL_GAIN,
)
from ..core.config import save_config
from ..core.logger import get_logger
from .skill_ids import skill_name_to_id

log = get_logger("SkillDataCollector")

DELTA_THRESHOLD = 1000.0  # total skill points gained before delta upload


class SkillDataCollector:
    """Manages opt-in flow, initial snapshot upload, and delta tracking."""

    def __init__(self, *, event_bus, nexus_client, config, db, config_path,
                 oauth=None):
        self._event_bus = event_bus
        self._nexus_client = nexus_client
        self._config = config
        self._config_path = config_path
        self._db = db
        self._oauth = oauth

        self._awaiting_rescan = False
        self._pending_scan_result = None  # held until upload after opt-in
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Subscribe to events."""
        self._event_bus.subscribe(EVENT_OCR_COMPLETE, self._on_ocr_complete)
        self._event_bus.subscribe(EVENT_SKILL_GAIN, self._on_skill_gain)
        self._event_bus.subscribe(EVENT_CONFIG_CHANGED, self._on_config_changed)
        self._event_bus.subscribe(EVENT_SKILL_DATA_OPTIN_RESULT, self._on_optin_result)

        # Reconcile accumulator with DB on startup
        self._reconcile_accumulator()
        log.info(
            "Started (opted_in=%s, accumulated=%.1f, last_upload=%d)",
            self._config.skill_data_opted_in,
            self._config.skill_data_accumulated_gains,
            self._config.skill_data_last_upload_ts,
        )

    def stop(self) -> None:
        """Unsubscribe and persist state."""
        self._event_bus.unsubscribe(EVENT_OCR_COMPLETE, self._on_ocr_complete)
        self._event_bus.unsubscribe(EVENT_SKILL_GAIN, self._on_skill_gain)
        self._event_bus.unsubscribe(EVENT_CONFIG_CHANGED, self._on_config_changed)
        self._event_bus.unsubscribe(EVENT_SKILL_DATA_OPTIN_RESULT, self._on_optin_result)
        self._save_state()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_ocr_complete(self, result) -> None:
        """Handle scan completion — prompt or upload if appropriate."""
        if not self._is_full_clean_scan(result):
            return

        with self._lock:
            if self._awaiting_rescan:
                # User said skills changed → this fresh scan is the new baseline
                log.info("Re-scan complete, uploading snapshot")
                self._awaiting_rescan = False
                self._upload_snapshot_async(result)
                return

            if self._config.skill_data_opted_in:
                # Already opted in — a new clean scan is a good time for a
                # snapshot if there's meaningful data since last upload
                last = self._config.skill_data_last_upload_ts
                if last == 0:
                    # First upload after toggling on via settings
                    self._upload_snapshot_async(result)
                return

            if self._should_prompt():
                self._pending_scan_result = result
                self._event_bus.publish(EVENT_SKILL_DATA_OPTIN_PROMPT, result)

    def _on_skill_gain(self, event) -> None:
        """Accumulate skill gains and trigger delta upload at threshold."""
        if not self._config.skill_data_opted_in:
            return
        if self._config.skill_data_last_upload_ts == 0:
            return  # no initial snapshot yet

        with self._lock:
            self._config.skill_data_accumulated_gains += event.amount
            if self._config.skill_data_accumulated_gains >= DELTA_THRESHOLD:
                self._upload_delta_async()

    def _on_config_changed(self, config) -> None:
        """Track config changes (e.g. user toggled opt-in in settings)."""
        self._config = config

    # ------------------------------------------------------------------
    # Opt-in result (called from UI dialog on main thread)
    # ------------------------------------------------------------------

    def _on_optin_result(self, data) -> None:
        """Process the user's response to the opt-in dialog.

        Expected *data*: ``{"accepted": bool, "skills_changed": bool}``.
        Published by the UI after the dialog closes.
        """
        accepted = data.get("accepted", False)
        skills_changed = data.get("skills_changed", False)

        self._config.skill_data_prompt_shown = True

        if not accepted:
            self._save_state()
            log.info("User declined skill data contribution")
            return

        self._config.skill_data_opted_in = True
        self._save_state()
        log.info("User opted in to skill data contribution")

        with self._lock:
            if skills_changed:
                self._awaiting_rescan = True
                log.info("Awaiting re-scan before initial upload")
            elif self._pending_scan_result is not None:
                self._upload_snapshot_async(self._pending_scan_result)
                self._pending_scan_result = None

    # ------------------------------------------------------------------
    # Upload logic
    # ------------------------------------------------------------------

    def _upload_snapshot_async(self, scan_result) -> None:
        """Build and upload a snapshot on a background thread."""
        threading.Thread(
            target=self._do_upload_snapshot,
            args=(scan_result,),
            daemon=True,
            name="skill-data-snapshot",
        ).start()

    def _upload_delta_async(self) -> None:
        """Build and upload a delta on a background thread."""
        threading.Thread(
            target=self._do_upload_delta,
            daemon=True,
            name="skill-data-delta",
        ).start()

    def _do_upload_snapshot(self, scan_result) -> None:
        """Upload initial snapshot: current skill points + full gain history."""
        try:
            self._event_bus.publish(EVENT_SKILL_DATA_UPLOAD_STATUS, {
                "status": "uploading", "type": "snapshot",
            })

            skills = {}
            for reading in scan_result.skills:
                sid = skill_name_to_id(reading.skill_name)
                if sid is not None:
                    skills[str(sid)] = reading.current_points

            gains = self._db.get_skill_gains_raw(since_ts=0) if self._db else []

            payload = {
                "type": "snapshot",
                "scan_timestamp": int(scan_result.scan_end.timestamp())
                if scan_result.scan_end else 0,
                "skills": skills,
                "gains": gains,
            }

            result = self._nexus_client.ingest_skill_data(payload)
            if result is not None:
                import time
                self._config.skill_data_last_upload_ts = int(time.time())
                self._config.skill_data_accumulated_gains = 0.0
                self._save_state()
                log.info("Snapshot uploaded: %d skills, %d gain events",
                         len(skills), len(gains))
                self._event_bus.publish(EVENT_SKILL_DATA_UPLOAD_STATUS, {
                    "status": "success", "type": "snapshot",
                })
            else:
                log.warning("Snapshot upload returned None (client error)")
                self._event_bus.publish(EVENT_SKILL_DATA_UPLOAD_STATUS, {
                    "status": "error", "type": "snapshot",
                })

        except (RateLimitError, ServerError) as e:
            log.warning("Snapshot upload failed (will retry): %s", e)
            self._event_bus.publish(EVENT_SKILL_DATA_UPLOAD_STATUS, {
                "status": "error", "type": "snapshot",
            })
        except Exception:
            log.exception("Snapshot upload failed")
            self._event_bus.publish(EVENT_SKILL_DATA_UPLOAD_STATUS, {
                "status": "error", "type": "snapshot",
            })

    def _do_upload_delta(self) -> None:
        """Upload incremental gains since last upload."""
        try:
            since = self._config.skill_data_last_upload_ts
            gains = self._db.get_skill_gains_raw(since_ts=since) if self._db else []
            if not gains:
                self._config.skill_data_accumulated_gains = 0.0
                self._save_state()
                return

            payload = {
                "type": "delta",
                "since_ts": since,
                "gains": gains,
            }

            result = self._nexus_client.ingest_skill_data(payload)
            if result is not None:
                import time
                self._config.skill_data_last_upload_ts = int(time.time())
                self._config.skill_data_accumulated_gains = 0.0
                self._save_state()
                log.info("Delta uploaded: %d gain events", len(gains))
            else:
                log.warning("Delta upload returned None (client error)")

        except (RateLimitError, ServerError) as e:
            log.warning("Delta upload failed (will retry next threshold): %s", e)
        except Exception:
            log.exception("Delta upload failed")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_full_clean_scan(result) -> bool:
        """True if the scan found all expected skills with no mismatches."""
        if result.total_found < result.total_expected:
            return False
        return not any(s.is_mismatch for s in result.skills)

    def _should_prompt(self) -> bool:
        """True if we should show the opt-in dialog."""
        if self._config.skill_data_opted_in:
            return False
        if self._config.skill_data_prompt_shown:
            return False
        # Must be authenticated
        if self._oauth and not self._oauth.is_authenticated():
            return False
        return True

    def _reconcile_accumulator(self) -> None:
        """Reconcile the in-config accumulator with actual DB gains on startup."""
        if not self._config.skill_data_opted_in:
            return
        last = self._config.skill_data_last_upload_ts
        if last == 0 or not self._db:
            return
        try:
            totals = self._db.get_skill_gains_since(last)
            actual = sum(totals.values())
            if actual != self._config.skill_data_accumulated_gains:
                log.debug(
                    "Reconciled accumulator: config=%.1f, db=%.1f",
                    self._config.skill_data_accumulated_gains, actual,
                )
                self._config.skill_data_accumulated_gains = actual
        except Exception:
            pass

    def _save_state(self) -> None:
        """Persist config fields."""
        try:
            save_config(self._config, self._config_path)
        except Exception:
            log.debug("Failed to save config", exc_info=True)
