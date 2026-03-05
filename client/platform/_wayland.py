"""Wayland platform backend — best-effort, compositor-specific implementations.

Focus detection uses compositor-specific APIs:
- KDE Plasma: ``org.kde.KWin`` D-Bus
- Sway: ``swaymsg -t get_tree`` JSON
- Hyprland: ``hyprctl activewindow -j`` JSON
- GNOME: process-based detection only (no window introspection API)

Occlusion detection and click-through are not possible on Wayland.
Global hotkeys are not available (compositor must be configured directly).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess

log = logging.getLogger("platform.wayland")


def _detect_compositor() -> str:
    """Detect which Wayland compositor is running."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "kde" in desktop or "plasma" in desktop:
        return "kde"
    if "sway" in desktop:
        return "sway"
    if "hyprland" in desktop:
        return "hyprland"
    if "gnome" in desktop:
        return "gnome"

    # Fallback: check running processes
    try:
        result = subprocess.run(
            ["ps", "-e", "-o", "comm="],
            capture_output=True, text=True, timeout=2,
        )
        procs = result.stdout.lower()
        if "kwin" in procs:
            return "kde"
        if "sway" in procs:
            return "sway"
        if "hyprland" in procs or "Hyprland" in procs:
            return "hyprland"
        if "gnome-shell" in procs:
            return "gnome"
    except Exception:
        pass

    return "unknown"


class WaylandBackend:
    """Best-effort Wayland backend with compositor-specific focus detection."""

    def __init__(self):
        self._compositor = _detect_compositor()
        self._geometry_cache: dict = {}  # {wid: (x, y, w, h)} populated by find
        log.info("Wayland backend initialised (compositor: %s)", self._compositor)

    # ------------------------------------------------------------------
    # Capability queries
    # ------------------------------------------------------------------

    def supports_focus_detection(self) -> bool:
        # GNOME has no introspection API — fall back
        return self._compositor in ("kde", "sway", "hyprland")

    def supports_global_hotkeys(self) -> bool:
        # No universal Wayland global hotkey API
        return False

    # ------------------------------------------------------------------
    # Focus detection
    # ------------------------------------------------------------------

    def get_foreground_window_title(self) -> str:
        try:
            if self._compositor == "kde":
                return self._kde_active_title()
            if self._compositor == "sway":
                return self._sway_active_title()
            if self._compositor == "hyprland":
                return self._hyprland_active_title()
        except Exception as e:
            log.debug("Failed to get foreground title: %s", e)
        return ""

    def get_foreground_window_id(self) -> int:
        # Wayland doesn't expose numeric window IDs in a universal way
        # Return a sentinel so callers can still check != 0
        title = self.get_foreground_window_title()
        return hash(title) if title else 0

    def find_window_by_title_prefix(self, prefix: str) -> int | None:
        try:
            if self._compositor == "sway":
                return self._sway_find_by_prefix(prefix)
            if self._compositor == "hyprland":
                return self._hyprland_find_by_prefix(prefix)
            if self._compositor == "kde":
                return self._kde_find_by_prefix(prefix)
        except Exception:
            pass
        return None

    def is_window_visible(self, wid: int) -> bool:
        return False  # Can't query arbitrary windows on Wayland

    def is_window_minimized(self, wid: int) -> bool:
        return False

    def get_window_geometry(self, wid: int) -> tuple[int, int, int, int] | None:
        return self._geometry_cache.get(wid)

    def get_window_pid(self, wid: int) -> int:
        return 0

    # ------------------------------------------------------------------
    # Occlusion — not possible on Wayland
    # ------------------------------------------------------------------

    def is_window_occluded(self, target_wid: int, ignore_wids: set[int]) -> bool:
        return False

    # ------------------------------------------------------------------
    # Window manipulation
    # ------------------------------------------------------------------

    def set_click_through(self, wid: int) -> bool:
        return False  # Not possible on Wayland

    def set_no_activate(self, wid: int) -> bool:
        return False  # Not needed on Wayland

    def bring_to_foreground(self, wid: int) -> bool:
        try:
            if self._compositor == "sway":
                return self._sway_focus_window(wid)
            if self._compositor == "hyprland":
                return self._hyprland_focus_window(wid)
        except Exception as e:
            log.debug("Failed to bring window to foreground: %s", e)
        return False

    def release_focus_to(self, title_prefix: str) -> bool:
        try:
            if self._compositor == "kde":
                return self._kde_focus_by_prefix(title_prefix)
            wid = self.find_window_by_title_prefix(title_prefix)
            if wid is not None:
                return self.bring_to_foreground(wid)
        except Exception as e:
            log.debug("Failed to release focus: %s", e)
        return False

    # ------------------------------------------------------------------
    # Decoration
    # ------------------------------------------------------------------

    def enable_shadow(self, wid: int) -> bool:
        return False  # Compositor handles shadows

    # ------------------------------------------------------------------
    # Hotkeys — not available on Wayland
    # ------------------------------------------------------------------

    def register_hotkey_hook(self, callback) -> bool:
        log.info(
            "Global hotkeys not available on Wayland. "
            "Configure compositor shortcuts instead."
        )
        return False

    def unregister_hotkey_hook(self, callback=None) -> bool:
        return False

    # ------------------------------------------------------------------
    # Desktop integration
    # ------------------------------------------------------------------

    def set_app_id(self, app_id: str) -> None:
        try:
            from PyQt6.QtGui import QGuiApplication
            QGuiApplication.setDesktopFileName("entropia-nexus")
        except Exception:
            pass

    def flash_taskbar(self, wid: int) -> None:
        pass  # Qt's QApplication.alert() handles this

    # ------------------------------------------------------------------
    # Compositor-specific implementations
    # ------------------------------------------------------------------

    def _kde_active_title(self) -> str:
        """KDE Plasma: query org.kde.KWin D-Bus for active window."""
        result = subprocess.run(
            [
                "dbus-send", "--session", "--dest=org.kde.KWin",
                "--print-reply", "/Scripting",
                "org.kde.kwin.Scripting.evaluateScript",
                "string:workspace.activeWindow.caption",
            ],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            # Parse D-Bus reply — look for string value
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("string"):
                    return line.split('"')[1] if '"' in line else ""
        return ""

    def _sway_active_title(self) -> str:
        """Sway: parse swaymsg -t get_tree for focused window."""
        result = subprocess.run(
            ["swaymsg", "-t", "get_tree"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            tree = json.loads(result.stdout)
            node = self._sway_find_focused(tree)
            if node:
                return node.get("name", "")
        return ""

    def _sway_find_focused(self, node: dict) -> dict | None:
        """Recursively find the focused node in a Sway tree."""
        if node.get("focused"):
            return node
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            result = self._sway_find_focused(child)
            if result:
                return result
        return None

    def _sway_find_by_prefix(self, prefix: str) -> int | None:
        """Find a Sway window by title prefix, return its con_id."""
        result = subprocess.run(
            ["swaymsg", "-t", "get_tree"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            tree = json.loads(result.stdout)
            node = self._sway_walk_for_prefix(tree, prefix)
            if node:
                con_id = node.get("id", 0)
                rect = node.get("rect")
                if rect and con_id:
                    self._geometry_cache[con_id] = (
                        rect.get("x", 0), rect.get("y", 0),
                        rect.get("width", 0), rect.get("height", 0),
                    )
                return con_id
        return None

    def _sway_walk_for_prefix(self, node: dict, prefix: str) -> dict | None:
        name = node.get("name", "")
        if name and name.startswith(prefix):
            return node
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            result = self._sway_walk_for_prefix(child, prefix)
            if result:
                return result
        return None

    def _hyprland_active_title(self) -> str:
        """Hyprland: parse hyprctl activewindow -j."""
        result = subprocess.run(
            ["hyprctl", "activewindow", "-j"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("title", "")
        return ""

    def _hyprland_find_by_prefix(self, prefix: str) -> int | None:
        """Find a Hyprland window by title prefix."""
        result = subprocess.run(
            ["hyprctl", "clients", "-j"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            clients = json.loads(result.stdout)
            for client in clients:
                title = client.get("title", "")
                if title.startswith(prefix):
                    address = client.get("address", 0)
                    at = client.get("at")
                    size = client.get("size")
                    if at and size and address:
                        self._geometry_cache[address] = (
                            at[0], at[1], size[0], size[1],
                        )
                    return address
        return None

    # ------------------------------------------------------------------
    # KDE — window finding and focus via KWin scripting
    # ------------------------------------------------------------------

    def _kde_find_by_prefix(self, prefix: str) -> int | None:
        """KDE Plasma: find window by title prefix via KWin scripting."""
        safe = prefix.replace("\\", "\\\\").replace("'", "\\'")
        script = (
            "var wins = workspace.windowList();"
            "var r = '';"
            "for (var i = 0; i < wins.length; i++) {"
            "  var w = wins[i];"
            f"  if (w.caption.startsWith('{safe}')) {{"
            "    var g = w.frameGeometry;"
            "    r = w.caption + '|' + g.x + '|' + g.y + '|' + g.width + '|' + g.height;"
            "    break;"
            "  }"
            "}"
            "r;"
        )
        result = subprocess.run(
            [
                "dbus-send", "--session", "--dest=org.kde.KWin",
                "--print-reply", "/Scripting",
                "org.kde.kwin.Scripting.evaluateScript",
                f"string:{script}",
            ],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("string") and '"' in line:
                    value = line.split('"')[1]
                    if not value:
                        return None
                    parts = value.split("|")
                    wid = hash(parts[0])
                    if len(parts) == 5:
                        try:
                            self._geometry_cache[wid] = (
                                int(parts[1]), int(parts[2]),
                                int(parts[3]), int(parts[4]),
                            )
                        except (ValueError, IndexError):
                            pass
                    return wid
        return None

    def _kde_focus_by_prefix(self, prefix: str) -> bool:
        """KDE Plasma: activate window by title prefix via KWin scripting."""
        safe = prefix.replace("\\", "\\\\").replace("'", "\\'")
        script = (
            "var wins = workspace.windowList();"
            "for (var i = 0; i < wins.length; i++) {"
            f"  if (wins[i].caption.startsWith('{safe}')) {{"
            "    workspace.activeWindow = wins[i];"
            "    break;"
            "  }"
            "}"
        )
        result = subprocess.run(
            [
                "dbus-send", "--session", "--dest=org.kde.KWin",
                "--print-reply", "/Scripting",
                "org.kde.kwin.Scripting.evaluateScript",
                f"string:{script}",
            ],
            capture_output=True, text=True, timeout=2,
        )
        return result.returncode == 0

    # ------------------------------------------------------------------
    # Sway / Hyprland — focus control
    # ------------------------------------------------------------------

    def _sway_focus_window(self, con_id: int) -> bool:
        """Focus a Sway window by its con_id."""
        result = subprocess.run(
            ["swaymsg", f"[con_id={con_id}]", "focus"],
            capture_output=True, text=True, timeout=2,
        )
        return result.returncode == 0

    def _hyprland_focus_window(self, address) -> bool:
        """Focus a Hyprland window by its address."""
        result = subprocess.run(
            ["hyprctl", "dispatch", "focuswindow", f"address:{address}"],
            capture_output=True, text=True, timeout=2,
        )
        return result.returncode == 0
