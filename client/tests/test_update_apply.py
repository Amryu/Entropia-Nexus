"""End-to-end update apply simulation.

Exercises the EXACT same script template and launch flags as updater.py:
  1. Spawns a real process (copy of cmd.exe named entropia-nexus.exe)
  2. Launches the apply script detached (DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
  3. Terminates the "app" so the tasklist wait loop exits
  4. Waits for the script to copy, clean up, and relaunch
  5. Verifies files, log, and relaunch sentinel

Usage:
    python -m client.tests.test_update_apply
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_TIMEOUT = 30  # seconds to wait for the apply script to finish


def main():
    # Use a short path — xcopy under DETACHED_PROCESS fails with errorlevel 4
    # on long paths through %TEMP% (AppData\Local\Temp\...).
    tmp = Path("C:/Temp/nexus_update_e2e")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    print(f"Test directory: {tmp}")
    relaunched_proc = None

    try:
        app_dir = tmp / "entropia-nexus"
        app_dir.mkdir()

        # -- Fake exe: copy of cmd.exe so tasklist sees "entropia-nexus.exe" --
        exe_path = app_dir / "entropia-nexus.exe"
        shutil.copy2(os.path.join(os.environ["SYSTEMROOT"], "System32", "cmd.exe"),
                      str(exe_path))

        # -- Fake _internal tree --
        internal = app_dir / "_internal" / "client"
        internal.mkdir(parents=True)
        (internal / "VERSION").write_text("0.1.0")
        (internal / "data").mkdir()
        (internal / "data" / "changelog.json").write_text('[{"version":"0.1.0"}]')
        (app_dir / "_internal" / "lib.dll").write_text("unchanged-lib")
        (app_dir / "_internal" / "old_module.pyc").write_text("to-be-removed")

        # Fake manifest
        with open(app_dir / "manifest.json", "w") as f:
            json.dump({"version": "0.1.0", "files": {}}, f)

        # -- Staging directory (_update) --
        staging = app_dir / "_update"
        staging.mkdir()
        (staging / "_internal" / "client" / "data").mkdir(parents=True)
        (staging / "_internal" / "client" / "VERSION").write_text("0.1.1")
        (staging / "_internal" / "client" / "data" / "changelog.json").write_text(
            '[{"version":"0.1.1"},{"version":"0.1.0"}]'
        )
        # Updated exe: a .cmd-content file won't run as .exe, so just copy
        # the same cmd.exe — the content change is tested via VERSION/manifest.
        shutil.copy2(str(exe_path), str(staging / "entropia-nexus.exe"))
        with open(staging / "manifest.json", "w") as f:
            json.dump({"version": "0.1.1", "files": {}}, f)
        with open(staging / "_removals.json", "w") as f:
            json.dump(["_internal/old_module.pyc"], f)

        # -- Launch the fake "app" process --
        print("Launching fake app process...")
        app_proc = subprocess.Popen(
            [str(exe_path), "/c", "ping -n 120 127.0.0.1 >NUL"],
            creationflags=0x00000200,  # CREATE_NEW_PROCESS_GROUP
        )
        print(f"  PID: {app_proc.pid}, image: entropia-nexus.exe")

        # Verify tasklist can see it
        time.sleep(0.5)
        check = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq entropia-nexus.exe"],
            capture_output=True,
        )
        if b"entropia-nexus.exe" not in check.stdout:
            print("FAIL: tasklist cannot find entropia-nexus.exe")
            app_proc.kill()
            return 1
        print("  Visible in tasklist: yes")

        # -- Generate apply script (EXACT same template as updater.py) --
        exe_name = "entropia-nexus.exe"
        log_path = app_dir / "_update.log"
        script_path = app_dir / "_apply_update.cmd"

        removals_cmds = ""
        with open(staging / "_removals.json") as f:
            for rel in json.load(f):
                safe = rel.replace("/", "\\")
                removals_cmds += f'if exist "{safe}" del /f /q "{safe}"\n'

        script = f'''@echo off
setlocal EnableDelayedExpansion
:: Entropia Nexus update apply script (auto-generated, safe to delete)
set "EXE={exe_name}"
set "APP_DIR={app_dir}"
set "STAGING={staging}"
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

:: Relaunch — in test, this opens a new cmd window (our exe is cmd.exe)
echo [%date% %time%] Starting %EXE%... >> "%LOG%"
start "" "%APP_DIR%\\%EXE%"

echo [%date% %time%] Apply script finished >> "%LOG%"
:: Self-delete (log file preserved for post-update check)
(goto) 2>nul & del "%~f0"
'''
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        # -- Launch apply script DETACHED (same as real updater code) --
        print("\nLaunching apply script (detached)...")
        subprocess.Popen(
            ["cmd.exe", "/c", str(script_path)],
            creationflags=0x00000200 | 0x08000000,  # CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            close_fds=True,
            cwd=str(app_dir),
        )

        # -- Kill the "app" after a short delay (simulates QApplication.quit()) --
        time.sleep(2)
        print("Terminating fake app process...")
        app_proc.terminate()
        app_proc.wait(timeout=5)
        print(f"  App exited with code {app_proc.returncode}")

        # -- Wait for apply script to finish --
        print("\nWaiting for apply script to complete...")
        deadline = time.time() + _TIMEOUT
        finished = False
        while time.time() < deadline:
            if log_path.exists():
                content = log_path.read_text(errors="replace")
                if "Apply script finished" in content:
                    finished = True
                    break
            time.sleep(0.5)

        if not finished:
            print("FAIL: Apply script did not finish within timeout")
            if log_path.exists():
                print(f"\nPartial log:\n{log_path.read_text(errors='replace')}")
            return 1

        # -- Kill the relaunched process (it's a cmd.exe window) --
        time.sleep(1)
        kill_result = subprocess.run(
            ["taskkill", "/F", "/IM", "entropia-nexus.exe"],
            capture_output=True,
        )
        if b"SUCCESS" in kill_result.stdout:
            print("  Killed relaunched process")

        # -- Print the log --
        print(f"\n--- _update.log ---")
        log_content = log_path.read_text(errors="replace")
        print(log_content.encode("ascii", errors="replace").decode("ascii"))

        # -- Verify --
        print("--- Verification ---")
        errors = []

        def check(ok, label, detail=""):
            if ok:
                print(f"  OK   {label}")
            else:
                errors.append(f"{label}: {detail}")
                print(f"  FAIL {label}: {detail}")

        # Log contains all expected phases
        check("Process closed" in log_content, "Wait loop completed")
        check("Copying files" in log_content, "Copy started")
        check("Copy complete" in log_content, "Copy succeeded")
        check("Cleaning up" in log_content, "Cleanup ran")
        check("Starting entropia-nexus.exe" in log_content, "Relaunch attempted")
        check("Apply script finished" in log_content, "Script completed")

        # Files updated
        v = (app_dir / "_internal" / "client" / "VERSION")
        check(v.exists() and v.read_text().strip() == "0.1.1",
              "VERSION updated to 0.1.1",
              v.read_text().strip() if v.exists() else "missing")

        m = app_dir / "manifest.json"
        mdata = json.loads(m.read_text()) if m.exists() else {}
        check(mdata.get("version") == "0.1.1",
              "manifest.json updated",
              f"version={mdata.get('version')}")

        # Unchanged file preserved
        lib = app_dir / "_internal" / "lib.dll"
        check(lib.exists() and lib.read_text() == "unchanged-lib",
              "Unchanged file preserved (lib.dll)")

        # Removed file gone
        old = app_dir / "_internal" / "old_module.pyc"
        check(not old.exists(), "Removed file deleted (old_module.pyc)")

        # Staging cleaned up
        check(not staging.exists(), "_update/ staging removed")
        check(not (app_dir / "_removals.json").exists(), "_removals.json removed")

        # Apply script self-deleted
        check(not script_path.exists(), "_apply_update.cmd self-deleted")

        if errors:
            print(f"\nFAILED: {len(errors)} error(s)")
            for e in errors:
                print(f"  - {e}")
            return 1

        print(f"\nPASSED: Full end-to-end update simulation OK")
        return 0

    finally:
        # Clean up any leftover processes
        subprocess.run(["taskkill", "/F", "/IM", "entropia-nexus.exe"],
                       capture_output=True)
        time.sleep(0.5)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
