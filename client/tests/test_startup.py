"""Smoke tests: verify the client starts up with all dependencies present.

Tests:
    TestNativeImports       — imports every native/C-extension dependency in-process
    TestClientStartup       — launches the real process in both headless and GUI modes,
                              verifies it survives startup, and reports loaded DLLs
    test_bundled_dll_usage  — compares loaded DLLs against the PyInstaller dist folder
                              to find candidates for exclusion (skipped if dist missing)

Usage:
    pytest client/tests/test_startup.py -v -s                  # test from source
    TEST_EXE=1 pytest client/tests/test_startup.py -v -s       # test the bundled exe
"""

import ctypes
import os
import subprocess
import sys
import time

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST_DIR = os.path.join(PROJECT_ROOT, "client", "dist", "entropia-nexus")
DIST_EXE = os.path.join(DIST_DIR, "entropia-nexus.exe")

# Seconds to wait for the process to finish initializing.
# GUI mode needs longer — splash screen, page prewarming, worker threads, etc.
STARTUP_WAIT_HEADLESS = 15
STARTUP_WAIT_GUI = 25

# Set TEST_EXE=1 to test the bundled PyInstaller exe instead of source.
USE_BUNDLED_EXE = os.environ.get("TEST_EXE", "").strip() not in ("", "0")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_loaded_dlls(pid: int) -> list[str]:
    """Return list of DLL/module paths loaded by a Windows process."""
    if sys.platform != "win32":
        pytest.skip("DLL enumeration only supported on Windows")

    from ctypes import wintypes, POINTER, byref, sizeof

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    LIST_MODULES_ALL = 0x03
    HMODULE = wintypes.HMODULE  # properly sized handle type

    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi

    # Define proper signatures to avoid 64-bit overflow
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    psapi.EnumProcessModulesEx.restype = wintypes.BOOL
    psapi.EnumProcessModulesEx.argtypes = [
        wintypes.HANDLE, POINTER(HMODULE), wintypes.DWORD,
        POINTER(wintypes.DWORD), wintypes.DWORD,
    ]
    psapi.GetModuleFileNameExW.restype = wintypes.DWORD
    psapi.GetModuleFileNameExW.argtypes = [
        wintypes.HANDLE, HMODULE, wintypes.LPWSTR, wintypes.DWORD,
    ]

    handle = kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid,
    )
    if not handle:
        return []

    try:
        modules = (HMODULE * 4096)()
        needed = wintypes.DWORD()
        if not psapi.EnumProcessModulesEx(
            handle, modules, sizeof(modules), byref(needed), LIST_MODULES_ALL,
        ):
            return []

        count = needed.value // sizeof(HMODULE)
        paths = []
        for i in range(count):
            if modules[i]:
                buf = ctypes.create_unicode_buffer(512)
                if psapi.GetModuleFileNameExW(handle, modules[i], buf, 512):
                    paths.append(buf.value)
        return paths
    finally:
        kernel32.CloseHandle(handle)


def _find_dist_dlls(dist_dir: str) -> set[str]:
    """Collect all .dll / .pyd files in the PyInstaller dist folder."""
    found = set()
    for root, _dirs, files in os.walk(dist_dir):
        for f in files:
            if f.lower().endswith((".dll", ".pyd")):
                found.add(f.lower())
    return found


def _build_launch_cmd(*, headless: bool) -> tuple[list[str], str]:
    """Return (command, cwd) for launching the client."""
    flags = ["--allow-multiple"]
    if headless:
        flags.append("--headless")
    if USE_BUNDLED_EXE:
        if not os.path.isfile(DIST_EXE):
            pytest.skip(f"Bundled exe not found: {DIST_EXE}")
        return [DIST_EXE] + flags, DIST_DIR
    return [sys.executable, "-m", "client"] + flags, PROJECT_ROOT


def _launch_and_collect(capsys, *, headless: bool, label: str) -> set[str]:
    """Launch the client, verify it stays alive, print & return loaded DLL names."""
    cmd, cwd = _build_launch_cmd(headless=headless)
    wait = STARTUP_WAIT_HEADLESS if headless else STARTUP_WAIT_GUI

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd,
    )
    try:
        time.sleep(wait)

        retcode = proc.poll()
        if retcode is not None:
            stdout = proc.stdout.read().decode(errors="replace")
            stderr = proc.stderr.read().decode(errors="replace")
            pytest.fail(
                f"Client ({label}) exited with code {retcode} during startup.\n"
                f"--- stdout ---\n{stdout}\n"
                f"--- stderr ---\n{stderr}"
            )

        # Process is alive — startup succeeded.
        dlls = _get_loaded_dlls(proc.pid)
        dll_names = {os.path.basename(d).lower() for d in dlls}

        with capsys.disabled():
            print(f"\n{'=' * 70}")
            print(f"{label} — PID {proc.pid} — loaded {len(dlls)} modules")
            print(f"{'=' * 70}")
            for dll in sorted(dlls, key=str.lower):
                print(f"  {dll}")

        return dll_names

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNativeImports:
    """Fast in-process check that every native dependency can be imported."""

    def test_opencv(self):
        import cv2  # noqa: F401

    def test_onnxruntime(self):
        import onnxruntime  # noqa: F401

    def test_numpy(self):
        import numpy  # noqa: F401

    def test_pillow(self):
        from PIL import Image  # noqa: F401

    def test_mss(self):
        import mss  # noqa: F401

    def test_pyqt6_core(self):
        from PyQt6 import QtWidgets, QtCore, QtGui, QtNetwork  # noqa: F401

    def test_pyqt6_extras(self):
        from PyQt6 import QtSvg, QtMultimedia, QtMultimediaWidgets  # noqa: F401

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_keyboard(self):
        import keyboard  # noqa: F401

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_sounddevice(self):
        import sounddevice  # noqa: F401

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_windows_capture(self):
        import windows_capture  # noqa: F401

    def test_requests(self):
        import requests  # noqa: F401

    def test_keyring(self):
        import keyring  # noqa: F401

    def test_watchdog(self):
        import watchdog  # noqa: F401

    def test_obsws(self):
        import obsws_python  # noqa: F401


class TestClientStartup:
    """Launch the actual client process and verify it survives startup."""

    def test_headless(self, capsys):
        """Headless mode should start without crashing."""
        names = _launch_and_collect(capsys, headless=True, label="Headless")
        self.__class__._headless_dlls = names

    def test_gui(self, capsys):
        """GUI mode should start without crashing."""
        names = _launch_and_collect(capsys, headless=False, label="GUI")
        self.__class__._gui_dlls = names

    def test_bundled_dll_usage(self, capsys):
        """Compare loaded DLLs against PyInstaller dist to find unused bundles."""
        if not os.path.isdir(DIST_DIR):
            pytest.skip(f"PyInstaller dist not found at {DIST_DIR}")

        headless = getattr(self.__class__, "_headless_dlls", set())
        gui = getattr(self.__class__, "_gui_dlls", set())
        loaded = headless | gui
        if not loaded:
            pytest.skip("test_headless and/or test_gui must run first (use -v -s)")

        bundled = _find_dist_dlls(DIST_DIR)
        unused = sorted(bundled - loaded)
        gui_only = sorted(gui - headless) if headless and gui else []

        with capsys.disabled():
            print(f"\n{'=' * 70}")
            print(f"Bundled: {len(bundled)}  |  Loaded (union): {len(loaded)}  |  "
                  f"Potentially unused: {len(unused)}")
            print(f"{'=' * 70}")

            if gui_only:
                print(f"\nGUI-only modules ({len(gui_only)} — loaded in GUI but not headless):")
                for name in gui_only:
                    print(f"  {name}")

            if unused:
                print(f"\nBundled but never loaded ({len(unused)} — candidates for exclusion):")
                for name in unused:
                    print(f"  {name}")
            else:
                print("\nAll bundled DLLs were loaded.")
