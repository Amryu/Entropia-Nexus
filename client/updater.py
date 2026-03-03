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


def compare_manifests(local: dict, remote: dict) -> dict:
    """Compare two manifests and return file-level changes.

    Returns dict with keys: added, changed, removed (lists of relative paths)
    and download_size (total bytes to fetch).
    """
    local_files = local.get("files", {})
    remote_files = remote.get("files", {})

    added, changed, removed = [], [], []
    download_size = 0

    for path, info in remote_files.items():
        if path not in local_files:
            added.append(path)
            download_size += info.get("size", 0)
        elif local_files[path].get("sha256") != info.get("sha256"):
            changed.append(path)
            download_size += info.get("size", 0)

    for path in local_files:
        if path not in remote_files:
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

        event_bus.subscribe(EVENT_UPDATE_APPLY, self._on_apply_requested)

    # --- Public API ---

    def start(self):
        """Start background update checking."""
        if not self._app_dir:
            log.info("Not running from frozen app — skipping update checks")
            return
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

    # --- Background loop ---

    def _run_loop(self):
        """Check immediately (after short delay), then periodically."""
        if self._stop_event.wait(timeout=_INITIAL_DELAY):
            return

        while self._running and not self._stop_event.is_set():
            try:
                if self._check():
                    self._download()
                    return  # stop checking after successful download
            except Exception as e:
                log.error("Update check failed: %s", e)
                self._event_bus.publish(EVENT_UPDATE_ERROR, {"error": str(e)})
                if self._stop_event.wait(timeout=_RETRY_INTERVAL):
                    return
                continue

            if self._stop_event.wait(timeout=_CHECK_INTERVAL):
                return

    # --- Check ---

    def _check(self) -> bool:
        """Fetch remote manifest, compare with local. Returns True if update available."""
        base_url = self._config.nexus_base_url.rstrip("/")
        manifest_url = f"{base_url}/static/client/{self._platform}/manifest.json"

        log.info("Checking for updates: %s", manifest_url)

        try:
            resp = self._session.get(manifest_url, timeout=_MANIFEST_TIMEOUT)
            resp.raise_for_status()
            self._remote_manifest = resp.json()
        except requests.RequestException as e:
            log.warning("Failed to fetch remote manifest: %s", e)
            return False

        local_manifest = load_manifest(self._app_dir / "manifest.json")
        if local_manifest is None:
            log.warning("No local manifest — full update required")
            local_manifest = {"version": "0.0.0", "files": {}}

        local_version = local_manifest.get("version", "0.0.0")
        remote_version = self._remote_manifest.get("version", "0.0.0")

        if local_version == remote_version:
            log.info("Already up to date (v%s)", local_version)
            return False

        self._diff = compare_manifests(local_manifest, self._remote_manifest)
        update_files = self._diff["added"] + self._diff["changed"]

        if not update_files and not self._diff["removed"]:
            log.info("Version changed (%s -> %s) but no file differences",
                     local_version, remote_version)
            return False

        log.warning("Update available: v%s -> v%s (%d files, %s)",
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
        url = f"{base_url}/static/client/changelog.json"
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

            file_url = f"{base_url}/static/client/{self._platform}/{rel_path}"
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

        # Write remote manifest to staging (replaces local one during apply)
        with open(staging_dir / "manifest.json", "w") as f:
            json.dump(self._remote_manifest, f, indent=2)

        self._download_complete = True
        version = self._remote_manifest.get("version", "?")
        log.warning("Update v%s downloaded and ready to apply", version)

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

        script = f'''@echo off
setlocal
:: Entropia Nexus update apply script (auto-generated, safe to delete)
set "EXE={exe_name}"
set "APP_DIR={app_dir}"
set "STAGING={staging_dir}"

echo Waiting for Entropia Nexus to close...
:wait_loop
tasklist /FI "IMAGENAME eq %EXE%" 2>NUL | find /I /N "%EXE%" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >NUL
    goto wait_loop
)

echo Applying update...
cd /d "%APP_DIR%"

:: Copy staged files over current ones
xcopy "%STAGING%\\*" "%APP_DIR%\\" /E /Y /Q >NUL 2>&1
if errorlevel 1 (
    echo ERROR: Failed to copy update files
    pause
    goto cleanup
)

:: Remove deleted files
{removals_cmds}

:cleanup
:: Clean up staging and metadata
if exist "%STAGING%" rmdir /s /q "%STAGING%"
if exist "%APP_DIR%\\_removals.json" del /f /q "%APP_DIR%\\_removals.json"

:: Relaunch
echo Starting Entropia Nexus...
start "" "%APP_DIR%\\%EXE%"

:: Self-delete
(goto) 2>nul & del "%~f0"
'''
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script)

            CREATE_NEW_PROCESS_GROUP = 0x00000200
            DETACHED_PROCESS = 0x00000008
            subprocess.Popen(
                ["cmd.exe", "/c", str(script_path)],
                creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
                close_fds=True,
                cwd=str(app_dir),
            )
            log.warning("Apply script spawned — exiting for update")
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

        script = f'''#!/bin/bash
# Entropia Nexus update apply script (auto-generated, safe to delete)
APP_DIR="{app_dir}"
STAGING="{staging_dir}"
EXE="{exe_name}"

echo "Waiting for Entropia Nexus to close (PID: {pid})..."
while kill -0 {pid} 2>/dev/null; do
    sleep 1
done

echo "Applying update..."
cd "$APP_DIR"
cp -rf "$STAGING"/* "$APP_DIR/" 2>/dev/null

# Remove deleted files
{removals_cmds}

# Clean up
rm -rf "$STAGING"
rm -f "$APP_DIR/_removals.json"
rm -f "$APP_DIR/_apply_update.sh"

echo "Starting Entropia Nexus..."
"$APP_DIR/$EXE" &
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
            log.warning("Apply script spawned — exiting for update")
            return True
        except Exception as e:
            log.error("Failed to spawn apply script: %s", e)
            return False
