"""Delta update system — checks for updates, downloads changed files, stages for apply."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import requests

from .core.constants import (
    EVENT_UPDATE_APPLY,
    EVENT_UPDATE_AVAILABLE,
    EVENT_UPDATE_PROGRESS,
    EVENT_UPDATE_READY,
    EVENT_UPDATE_ERROR,
    EVENT_GROUP_DOWNLOAD_PROGRESS,
    EVENT_GROUP_DOWNLOAD_COMPLETE,
    EVENT_GROUP_DOWNLOAD_ERROR,
)
from .core.logger import get_logger

log = get_logger("Updater")

# Timings (seconds)
_INITIAL_DELAY = 5
_CHECK_INTERVAL = 3600       # 1 hour
_RETRY_INTERVAL = 300        # 5 minutes after failure

# HTTP
_MANIFEST_TIMEOUT = 15
_DOWNLOAD_TIMEOUT = 60
_CHUNK_SIZE = 65536

# After this many consecutive check failures, notify the user once and stop.
_MAX_CONSECUTIVE_FAILURES = 3


def get_app_dir() -> Path | None:
    """Return the directory containing the running exe, or None when running from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return None


def get_platform() -> str:
    """Return the platform string matching server hosting path."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def get_local_version() -> str:
    """Read the bundled VERSION file."""
    version_path = Path(__file__).parent / "VERSION"
    try:
        return version_path.read_text().strip()
    except FileNotFoundError:
        return "0.0.0"


def load_bundled_changelog() -> list[dict]:
    """Load the bundled changelog.json from the app data."""
    path = Path(__file__).parent / "data" / "changelog.json"
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def merge_changelogs(bundled: list[dict], remote: list[dict]) -> list[dict]:
    """Merge bundled and remote changelogs, deduplicated by version, sorted newest first."""
    seen: dict[str, dict] = {}
    for entry in remote + bundled:
        v = entry.get("version", "")
        if v and v not in seen:
            seen[v] = entry
    result = list(seen.values())
    result.sort(key=lambda e: [int(p) for p in e.get("version", "0").split(".")],
                reverse=True)
    return result


def load_manifest(path: Path) -> dict | None:
    """Read and parse a manifest.json file. Returns None on any error."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
        log.warning("Failed to load manifest at %s: %s", path, e)
        return None


def compare_manifests(
    local: dict, remote: dict, skip_groups: set[str] | None = None,
) -> dict:
    """Compare two manifests and return file-level changes.

    Returns dict with keys: added, changed, removed (lists of relative paths)
    and download_size (total bytes to fetch).

    If *skip_groups* is provided, files whose ``"group"`` value is in that set
    are excluded from all change lists (added, changed, removed).
    """
    local_files = local.get("files", {})
    remote_files = remote.get("files", {})
    skip = skip_groups or set()

    added, changed, removed = [], [], []
    download_size = 0

    for path, info in remote_files.items():
        if info.get("group") in skip:
            continue
        if path not in local_files:
            added.append(path)
            download_size += info.get("size", 0)
        elif local_files[path].get("sha256") != info.get("sha256"):
            changed.append(path)
            download_size += info.get("size", 0)

    for path, info in local_files.items():
        if path not in remote_files:
            # Don't remove files in a skipped group — they may still be
            # locally installed from a previous version or on-demand download.
            if info.get("group") in skip:
                continue
            removed.append(path)

    return {
        "added": added,
        "changed": changed,
        "removed": removed,
        "download_size": download_size,
    }


def _format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


class UpdateChecker:
    """Background worker that checks for updates, downloads deltas, and stages them.

    Lifecycle:
        1. start()             — spawns background thread
        2. _check()            — fetches remote manifest, compares with local
        3. _download()         — downloads changed files to _update/ staging dir
        4. prepare_and_apply() — generates apply script, spawns it, exits app

    The background thread runs steps 1-3 automatically. Step 4 is triggered
    by the user via EVENT_UPDATE_APPLY.
    """

    def __init__(self, config, event_bus):
        self._config = config
        self._event_bus = event_bus
        self._session = requests.Session()
        self._running = False
        self._stop_event = threading.Event()
        self._thread = None

        self._app_dir = get_app_dir()
        self._platform = get_platform()

        self._remote_manifest = None
        self._diff = None
        self._download_complete = False
        self._skip_groups: set[str] = set()

        event_bus.subscribe(EVENT_UPDATE_APPLY, self._on_apply_requested)

    # --- Public API ---

    def start(self):
        """Start background update checking."""
        if not self._app_dir:
            log.info("Not running from frozen app — skipping update checks")
            return

        # Post-update cleanup: if _update.log exists, the previous update
        # apply script ran.  Log its contents for diagnostics, then delete.
        self._cleanup_update_log()

        if not self._config.check_for_updates:
            log.info("Update checks disabled in config")
            return
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="update-checker",
        )
        self._thread.start()
        log.info("Update checker started")

    def stop(self):
        """Stop the background thread and close HTTP session."""
        self._running = False
        self._stop_event.set()
        self._session.close()
        self._event_bus.unsubscribe(EVENT_UPDATE_APPLY, self._on_apply_requested)
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def _cleanup_update_log(self):
        """Read and remove _update.log left by a previous apply script."""
        log_path = self._app_dir / "_update.log"
        if not log_path.exists():
            return
        try:
            contents = log_path.read_text(encoding="utf-8", errors="replace").strip()
            if contents:
                log.info("Previous update log:\n%s", contents)
            log_path.unlink()
            log.info("Cleaned up _update.log")
        except OSError as e:
            log.warning("Failed to clean up _update.log: %s", e)

        # Also clean up leftover staging dir or apply script
        for leftover in ("_update", "_apply_update.cmd", "_apply_update.sh"):
            p = self._app_dir / leftover
            try:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                elif p.exists():
                    p.unlink()
            except OSError:
                pass

    # --- Background loop ---

    def _run_loop(self):
        """Check immediately (after short delay), then periodically."""
        if self._stop_event.wait(timeout=_INITIAL_DELAY):
            return

        consecutive_failures = 0

        while self._running and not self._stop_event.is_set():
            try:
                result = self._check()
                if result is True:
                    self._download()
                    return  # stop checking after successful download
                elif result is None:
                    # Check failed (e.g. network error, 404)
                    consecutive_failures += 1
                else:
                    # Up to date — reset counter
                    consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                log.error("Update check failed: %s", e)
                self._event_bus.publish(EVENT_UPDATE_ERROR, {"error": str(e)})

            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                log.error("Update checks failed %d times — giving up", consecutive_failures)
                self._event_bus.publish(EVENT_UPDATE_ERROR, {
                    "error": "Update checks are failing repeatedly. "
                             "You may need to download the latest version manually.",
                    "critical": True,
                })
                return  # stop the checker entirely

            wait = _RETRY_INTERVAL if consecutive_failures > 0 else _CHECK_INTERVAL
            if self._stop_event.wait(timeout=wait):
                return

    # --- Check ---

    def _check(self) -> bool | None:
        """Fetch remote manifest, compare with local.

        Returns True if update available, False if up to date, None on failure.
        """
        base_url = self._config.nexus_base_url.rstrip("/")
        manifest_url = f"{base_url}/client/{self._platform}/manifest.json"

        log.info("Checking for updates: %s", manifest_url)

        try:
            resp = self._session.get(manifest_url, timeout=_MANIFEST_TIMEOUT)
            resp.raise_for_status()
            self._remote_manifest = resp.json()
        except requests.RequestException as e:
            log.warning("Failed to fetch remote manifest: %s", e)
            return None

        local_manifest = load_manifest(self._app_dir / "manifest.json")
        if local_manifest is None:
            log.warning("No local manifest — full update required")
            local_manifest = {"version": "0.0.0", "files": {}}

        local_version = local_manifest.get("version", "0.0.0")
        remote_version = self._remote_manifest.get("version", "0.0.0")

        if local_version == remote_version:
            log.info("Already up to date (v%s)", local_version)
            return False

        # Skip optional groups the user hasn't enabled to save bandwidth
        self._skip_groups = set()
        if not getattr(self._config, "capture_enabled", False):
            self._skip_groups.add("video")

        self._diff = compare_manifests(
            local_manifest, self._remote_manifest,
            skip_groups=self._skip_groups,
        )
        update_files = self._diff["added"] + self._diff["changed"]

        if not update_files and not self._diff["removed"]:
            log.info("Version changed (%s -> %s) but no file differences",
                     local_version, remote_version)
            return False

        log.info("Update available: v%s -> v%s (%d files, %s)",
                     local_version, remote_version,
                     len(update_files),
                     _format_size(self._diff["download_size"]))

        # Fetch remote changelog for the update dialog
        remote_changelog = self._fetch_changelog(base_url)

        self._event_bus.publish(EVENT_UPDATE_AVAILABLE, {
            "version": remote_version,
            "current_version": local_version,
            "download_size": self._diff["download_size"],
            "file_count": len(update_files),
            "changelog": remote_changelog,
        })
        return True

    def _fetch_changelog(self, base_url: str) -> list[dict]:
        """Download the remote changelog.json (platform-independent)."""
        url = f"{base_url}/client/changelog.json"
        try:
            resp = self._session.get(url, timeout=_MANIFEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.warning("Failed to fetch remote changelog: %s", e)
            return []

    # --- Download ---

    def _download(self):
        """Download all changed/added files to the _update/ staging directory."""
        staging_dir = self._app_dir / "_update"

        # Clean any previous partial staging
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)

        update_files = self._diff["added"] + self._diff["changed"]
        total = len(update_files)
        base_url = self._config.nexus_base_url.rstrip("/")
        remote_files = self._remote_manifest.get("files", {})

        for i, rel_path in enumerate(update_files):
            if not self._running:
                log.warning("Download cancelled")
                return

            self._event_bus.publish(EVENT_UPDATE_PROGRESS, {
                "downloaded": i,
                "total": total,
                "current_file": rel_path,
            })

            file_url = f"{base_url}/client/{self._platform}/{rel_path}"
            dest = staging_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)

            expected_hash = remote_files.get(rel_path, {}).get("sha256")

            try:
                resp = self._session.get(file_url, timeout=_DOWNLOAD_TIMEOUT, stream=True)
                resp.raise_for_status()

                tmp_path = dest.with_suffix(dest.suffix + ".tmp")
                h = hashlib.sha256()
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                        f.write(chunk)
                        h.update(chunk)

                actual_hash = h.hexdigest()
                if expected_hash and actual_hash != expected_hash:
                    tmp_path.unlink(missing_ok=True)
                    raise ValueError(
                        f"Hash mismatch for {rel_path}: "
                        f"expected {expected_hash[:12]}..., got {actual_hash[:12]}..."
                    )

                if dest.exists():
                    dest.unlink()
                tmp_path.rename(dest)

            except Exception as e:
                log.error("Failed to download %s: %s", rel_path, e)
                self._event_bus.publish(EVENT_UPDATE_ERROR, {
                    "error": f"Failed to download {rel_path}: {e}",
                })
                shutil.rmtree(staging_dir, ignore_errors=True)
                return

        # Write removal list for the apply script
        if self._diff["removed"]:
            with open(staging_dir / "_removals.json", "w") as f:
                json.dump(self._diff["removed"], f)

        # Write manifest to staging.  For skipped groups, preserve existing
        # local entries so the manifest still tracks files that are physically
        # present but were not updated in this delta.
        stored_manifest = {
            k: v for k, v in self._remote_manifest.items() if k != "files"
        }
        stored_files = {
            path: info
            for path, info in self._remote_manifest.get("files", {}).items()
            if info.get("group") not in self._skip_groups
        }
        if self._skip_groups:
            local_manifest = load_manifest(self._app_dir / "manifest.json") or {}
            remote_files = self._remote_manifest.get("files", {})
            for path, info in local_manifest.get("files", {}).items():
                if path in stored_files:
                    continue
                # Preserve local entry if it belongs to a skipped group.
                # Check both the local tag and the remote tag (handles
                # upgrade from old manifests that didn't have group tags).
                local_group = info.get("group")
                remote_group = remote_files.get(path, {}).get("group")
                if local_group in self._skip_groups or remote_group in self._skip_groups:
                    preserved = info.copy()
                    # Backfill group tag from remote if local is untagged
                    if remote_group and not local_group:
                        preserved["group"] = remote_group
                    stored_files[path] = preserved
        stored_manifest["files"] = stored_files
        with open(staging_dir / "manifest.json", "w") as f:
            json.dump(stored_manifest, f, indent=2)

        self._download_complete = True
        version = self._remote_manifest.get("version", "?")
        log.info("Update v%s downloaded and ready to apply", version)

        self._event_bus.publish(EVENT_UPDATE_READY, {"version": version})

    # --- Apply ---

    def _on_apply_requested(self, _data):
        """Handle EVENT_UPDATE_APPLY — generate script, spawn it, quit app."""
        if not self._download_complete or not self._app_dir:
            return

        staging_dir = self._app_dir / "_update"
        if not staging_dir.exists():
            log.error("Staging directory missing")
            return

        ok = (self._apply_windows(staging_dir) if sys.platform == "win32"
              else self._apply_unix(staging_dir))

        if ok:
            from PyQt6.QtWidgets import QApplication
            QApplication.quit()

    def _apply_windows(self, staging_dir: Path) -> bool:
        """Generate and launch a .cmd script for Windows update."""
        app_dir = self._app_dir
        exe_name = Path(sys.executable).name
        script_path = app_dir / "_apply_update.cmd"

        # Build removal commands from _removals.json
        removals_cmds = ""
        removals_file = staging_dir / "_removals.json"
        if removals_file.exists():
            with open(removals_file) as f:
                for rel in json.load(f):
                    safe = rel.replace("/", "\\")
                    removals_cmds += f'if exist "{safe}" del /f /q "{safe}"\n'

        log_path = app_dir / "_update.log"

        script = f'''@echo off
setlocal EnableDelayedExpansion
:: Entropia Nexus update apply script (auto-generated, safe to delete)
set "EXE={exe_name}"
set "APP_DIR={app_dir}"
set "STAGING={staging_dir}"
set "LOG={log_path}"

echo [%date% %time%] Update apply script started > "%LOG%"
echo [%date% %time%] EXE=%EXE% >> "%LOG%"
echo [%date% %time%] APP_DIR=%APP_DIR% >> "%LOG%"
echo [%date% %time%] STAGING=%STAGING% >> "%LOG%"

echo [%date% %time%] Waiting for process to close... >> "%LOG%"
:wait_loop
tasklist /FI "IMAGENAME eq %EXE%" 2>NUL | findstr /I "%EXE%" >NUL
if !ERRORLEVEL! equ 0 (
    ping -n 2 127.0.0.1 >NUL
    goto wait_loop
)
echo [%date% %time%] Process closed >> "%LOG%"

cd /d "%APP_DIR%"

:: Copy staged files over current ones
echo [%date% %time%] Copying files from staging... >> "%LOG%"
xcopy "%STAGING%\\*" "%APP_DIR%\\." /E /Y /Q /I >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: xcopy failed with errorlevel !ERRORLEVEL! >> "%LOG%"
    goto cleanup
)
echo [%date% %time%] Copy complete >> "%LOG%"

:: Remove deleted files
{removals_cmds}

:cleanup
:: Clean up staging and metadata
echo [%date% %time%] Cleaning up staging directory... >> "%LOG%"
if exist "%STAGING%" rmdir /s /q "%STAGING%"
if exist "%APP_DIR%\\_removals.json" del /f /q "%APP_DIR%\\_removals.json"

:: Relaunch
echo [%date% %time%] Starting %EXE%... >> "%LOG%"
start "" "%APP_DIR%\\%EXE%"

echo [%date% %time%] Apply script finished >> "%LOG%"
:: Self-delete (log file preserved for post-update check)
(goto) 2>nul & del "%~f0"
'''
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script)

            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000
            subprocess.Popen(
                ["cmd.exe", "/c", str(script_path)],
                creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
                close_fds=True,
                cwd=str(app_dir),
            )
            log.info("Apply script spawned — exiting for update")
            return True
        except Exception as e:
            log.error("Failed to spawn apply script: %s", e)
            return False

    def _apply_unix(self, staging_dir: Path) -> bool:
        """Generate and launch a .sh script for Linux/macOS update."""
        app_dir = self._app_dir
        exe_name = Path(sys.executable).name
        script_path = app_dir / "_apply_update.sh"
        pid = os.getpid()

        # Build removal commands from _removals.json
        removals_cmds = ""
        removals_file = staging_dir / "_removals.json"
        if removals_file.exists():
            with open(removals_file) as f:
                for rel in json.load(f):
                    removals_cmds += f'rm -f "{rel}"\n'

        log_file = app_dir / "_update.log"

        script = f'''#!/bin/bash
# Entropia Nexus update apply script (auto-generated, safe to delete)
APP_DIR="{app_dir}"
STAGING="{staging_dir}"
EXE="{exe_name}"
LOG="{log_file}"

ts() {{ date "+[%Y-%m-%d %H:%M:%S]"; }}

echo "$(ts) Update apply script started" > "$LOG"
echo "$(ts) APP_DIR=$APP_DIR" >> "$LOG"
echo "$(ts) STAGING=$STAGING" >> "$LOG"
echo "$(ts) EXE=$EXE" >> "$LOG"

echo "$(ts) Waiting for process to close (PID: {pid})..." >> "$LOG"
while kill -0 {pid} 2>/dev/null; do
    sleep 1
done
echo "$(ts) Process closed" >> "$LOG"

cd "$APP_DIR"

echo "$(ts) Copying files from staging..." >> "$LOG"
cp -rf "$STAGING"/* "$APP_DIR/" >> "$LOG" 2>&1
echo "$(ts) Copy complete" >> "$LOG"

# Remove deleted files
{removals_cmds}

# Clean up
echo "$(ts) Cleaning up staging directory..." >> "$LOG"
rm -rf "$STAGING"
rm -f "$APP_DIR/_removals.json"
rm -f "$APP_DIR/_apply_update.sh"

echo "$(ts) Starting $EXE..." >> "$LOG"
"$APP_DIR/$EXE" &
echo "$(ts) Apply script finished" >> "$LOG"
exit 0
'''
        try:
            with open(script_path, "w") as f:
                f.write(script)
            os.chmod(script_path, 0o755)

            subprocess.Popen(
                ["/bin/bash", str(script_path)],
                start_new_session=True,
                close_fds=True,
                cwd=str(app_dir),
            )
            log.info("Apply script spawned — exiting for update")
            return True
        except Exception as e:
            log.error("Failed to spawn apply script: %s", e)
            return False

    # --- Optional component groups ---

    def is_group_installed(self, group_name: str) -> bool:
        """Check whether an optional group's files are present in the local manifest."""
        if not self._app_dir:
            return True  # not frozen — pip packages cover it
        manifest = load_manifest(self._app_dir / "manifest.json")
        if manifest is None:
            return False
        # Old manifests (pre-groups era) included all files unconditionally.
        # Treat them as having all groups installed.
        if "groups" not in manifest:
            return True
        files = manifest.get("files", {})
        return any(info.get("group") == group_name for info in files.values())

    def get_group_download_size(self, group_name: str) -> int:
        """Return bytes needed to install/update a group, fetching remote manifest if needed.

        Returns 0 if all files are up to date or the remote manifest is unavailable.
        """
        remote = self._remote_manifest
        if remote is None:
            remote = self._fetch_remote_manifest()
            if remote is None:
                return 0

        local = load_manifest(self._app_dir / "manifest.json") if self._app_dir else None
        local_files = (local or {}).get("files", {})
        remote_files = remote.get("files", {})

        total = 0
        for path, info in remote_files.items():
            if info.get("group") != group_name:
                continue
            if path in local_files and local_files[path].get("sha256") == info.get("sha256"):
                continue
            total += info.get("size", 0)
        return total

    def download_group(self, group_name: str) -> None:
        """Download files for an optional group in a background thread."""
        if not self._app_dir:
            return
        threading.Thread(
            target=self._download_group_worker,
            args=(group_name,),
            daemon=True,
            name=f"download-group-{group_name}",
        ).start()

    def _fetch_remote_manifest(self) -> dict | None:
        """Fetch the remote manifest from the server."""
        base_url = self._config.nexus_base_url.rstrip("/")
        url = f"{base_url}/client/{self._platform}/manifest.json"
        try:
            resp = self._session.get(url, timeout=_MANIFEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.warning("Failed to fetch remote manifest: %s", e)
            return None

    def _download_group_worker(self, group_name: str) -> None:
        """Background worker to download a specific group's files."""
        remote = self._remote_manifest
        if remote is None:
            remote = self._fetch_remote_manifest()
        if remote is None:
            self._event_bus.publish(EVENT_GROUP_DOWNLOAD_ERROR, {
                "group": group_name,
                "error": "Could not reach the update server.",
            })
            return

        local = load_manifest(self._app_dir / "manifest.json") or {"files": {}}
        local_files = local.get("files", {})
        remote_files = remote.get("files", {})

        # Find files in target group that need downloading
        to_download = []
        for path, info in remote_files.items():
            if info.get("group") != group_name:
                continue
            if path in local_files and local_files[path].get("sha256") == info.get("sha256"):
                continue
            to_download.append(path)

        if not to_download:
            self._event_bus.publish(EVENT_GROUP_DOWNLOAD_COMPLETE, {
                "group": group_name,
            })
            return

        base_url = self._config.nexus_base_url.rstrip("/")
        total = len(to_download)

        for i, rel_path in enumerate(to_download):
            self._event_bus.publish(EVENT_GROUP_DOWNLOAD_PROGRESS, {
                "group": group_name,
                "downloaded": i,
                "total": total,
                "current_file": rel_path,
            })

            file_url = f"{base_url}/client/{self._platform}/{rel_path}"
            dest = self._app_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)

            expected_hash = remote_files.get(rel_path, {}).get("sha256")

            try:
                resp = self._session.get(file_url, timeout=_DOWNLOAD_TIMEOUT, stream=True)
                resp.raise_for_status()

                tmp_path = dest.with_suffix(dest.suffix + ".tmp")
                h = hashlib.sha256()
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                        f.write(chunk)
                        h.update(chunk)

                actual_hash = h.hexdigest()
                if expected_hash and actual_hash != expected_hash:
                    tmp_path.unlink(missing_ok=True)
                    raise ValueError(
                        f"Hash mismatch for {rel_path}: "
                        f"expected {expected_hash[:12]}..., got {actual_hash[:12]}..."
                    )

                if dest.exists():
                    dest.unlink()
                tmp_path.rename(dest)

            except Exception as e:
                log.error("Group download failed for %s: %s", rel_path, e)
                self._event_bus.publish(EVENT_GROUP_DOWNLOAD_ERROR, {
                    "group": group_name,
                    "error": f"Failed to download {rel_path}: {e}",
                })
                return

        # Update local manifest with the new group files
        local = load_manifest(self._app_dir / "manifest.json") or {
            "version": get_local_version(), "files": {},
        }
        for path in to_download:
            local["files"][path] = remote_files[path]
        # Also copy group metadata
        if "groups" not in local:
            local["groups"] = {}
        for gname, ginfo in remote.get("groups", {}).items():
            local["groups"][gname] = ginfo
        with open(self._app_dir / "manifest.json", "w") as f:
            json.dump(local, f, indent=2)

        log.info("Group '%s' downloaded: %d files", group_name, total)
        self._event_bus.publish(EVENT_GROUP_DOWNLOAD_COMPLETE, {
            "group": group_name,
        })
