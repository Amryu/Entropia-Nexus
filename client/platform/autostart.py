"""Cross-platform auto-start registration (Windows + Linux).

Windows: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
Linux:   ~/.config/autostart/entropia-nexus.desktop  (XDG autostart)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("autostart")

_APP_NAME = "Entropia Nexus Client"
_DESKTOP_FILENAME = "entropia-nexus.desktop"


def _get_launch_command(*, minimized: bool = True) -> list[str]:
    """Return the command list to launch the client on startup."""
    if getattr(sys, "frozen", False):
        cmd = [sys.executable]
    else:
        cmd = [sys.executable, "-m", "client"]
    if minimized:
        cmd.append("--minimized")
    return cmd


def is_enabled() -> bool:
    """Check whether auto-start is currently registered."""
    if sys.platform == "win32":
        return _win_is_enabled()
    return _linux_is_enabled()


def set_enabled(enabled: bool, *, minimized: bool = True) -> None:
    """Enable or disable auto-start for the current platform."""
    if sys.platform == "win32":
        _win_set_enabled(enabled, minimized=minimized)
    else:
        _linux_set_enabled(enabled, minimized=minimized)


# ---------------------------------------------------------------------------
# Windows — Registry
# ---------------------------------------------------------------------------

_WIN_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WIN_LEGACY_NAME = "EntropiaNexus"  # pre-0.4.2 registry key name


def _win_remove_legacy() -> None:
    """Remove the old 'EntropiaNexus' registry entry if it exists."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_REG_PATH, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _WIN_LEGACY_NAME)
            log.info("Removed legacy autostart entry '%s'", _WIN_LEGACY_NAME)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _win_is_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_REG_PATH, 0,
                            winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError as e:
        log.warning("Failed to read autostart registry: %s", e)
        return False


def _win_set_enabled(enabled: bool, *, minimized: bool = True) -> None:
    _win_remove_legacy()
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_REG_PATH, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enabled:
                cmd = _get_launch_command(minimized=minimized)
                # Quote each part that contains spaces
                value = " ".join(
                    f'"{part}"' if " " in part else part for part in cmd
                )
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, value)
                log.info("Auto-start enabled (registry): %s", value)
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                    log.info("Auto-start disabled (registry)")
                except FileNotFoundError:
                    pass  # Already removed
    except OSError as e:
        log.error("Failed to update autostart registry: %s", e)


# ---------------------------------------------------------------------------
# Linux — XDG autostart .desktop file
# ---------------------------------------------------------------------------

def _desktop_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if not xdg:
        xdg = str(Path.home() / ".config")
    return Path(xdg) / "autostart" / _DESKTOP_FILENAME


def _linux_is_enabled() -> bool:
    path = _desktop_path()
    if not path.exists():
        return False
    try:
        content = path.read_text(encoding="utf-8")
        # Check it's not disabled via Hidden=true
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.lower() == "hidden=true":
                return False
        return True
    except OSError:
        return False


def _linux_set_enabled(enabled: bool, *, minimized: bool = True) -> None:
    path = _desktop_path()
    if enabled:
        cmd = _get_launch_command(minimized=minimized)
        exec_line = " ".join(cmd)
        content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Entropia Nexus\n"
            "Comment=Entropia Nexus Desktop Client\n"
            f"Exec={exec_line}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            log.info("Auto-start enabled (XDG): %s", path)
        except OSError as e:
            log.error("Failed to write autostart desktop file: %s", e)
    else:
        try:
            path.unlink(missing_ok=True)
            log.info("Auto-start disabled (XDG)")
        except OSError as e:
            log.error("Failed to remove autostart desktop file: %s", e)
