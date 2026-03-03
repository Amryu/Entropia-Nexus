"""Abstract protocol for platform-specific backends.

Each backend implements this interface for its display server (Win32, X11,
Wayland) or returns no-op defaults (fallback).
"""

from __future__ import annotations

from typing import Protocol


class PlatformBackend(Protocol):
    """Unified API for platform-specific window management."""

    # --- Capability queries ---

    def supports_focus_detection(self) -> bool:
        """True if the backend can detect the foreground window."""
        ...

    def supports_global_hotkeys(self) -> bool:
        """True if the backend can register system-wide hotkeys."""
        ...

    # --- Focus detection ---

    def get_foreground_window_title(self) -> str:
        """Return the title of the currently focused window."""
        ...

    def get_foreground_window_id(self) -> int:
        """Return the window ID (HWND / XID) of the foreground window."""
        ...

    def find_window_by_title_prefix(self, prefix: str) -> int | None:
        """Find and return the first visible window whose title starts with *prefix*."""
        ...

    def is_window_visible(self, wid: int) -> bool:
        """True if the window is visible (not destroyed/hidden)."""
        ...

    def is_window_minimized(self, wid: int) -> bool:
        """True if the window is minimized / iconic."""
        ...

    def get_window_geometry(self, wid: int) -> tuple[int, int, int, int] | None:
        """Return (x, y, width, height) in screen coords, or None."""
        ...

    def get_window_pid(self, wid: int) -> int:
        """Return the process ID that owns the window."""
        ...

    # --- Occlusion ---

    def is_window_occluded(self, target_wid: int, ignore_wids: set[int]) -> bool:
        """True if *target_wid* is hidden behind another app window.

        Windows in *ignore_wids* (e.g. our own overlays) are skipped.
        """
        ...

    # --- Window manipulation ---

    def set_click_through(self, wid: int) -> bool:
        """Make the window pass all mouse events to the window below.

        Returns True on success.
        """
        ...

    def bring_to_foreground(self, wid: int) -> bool:
        """Activate the window and bring it to the front.

        Returns True on success.
        """
        ...

    def release_focus_to(self, title_prefix: str) -> bool:
        """Find the first window matching *title_prefix* and activate it.

        Returns True on success.
        """
        ...

    # --- Decoration ---

    def enable_shadow(self, wid: int) -> bool:
        """Apply a drop shadow to the frameless window.

        Returns True on success.
        """
        ...

    # --- Hotkeys ---

    def register_hotkey_hook(self, callback) -> bool:
        """Install a low-level keyboard hook; *callback* receives key events.

        Returns True on success.
        """
        ...

    def unregister_hotkey_hook(self) -> bool:
        """Remove the keyboard hook installed by :meth:`register_hotkey_hook`.

        Returns True on success.
        """
        ...

    # --- Desktop integration ---

    def set_app_id(self, app_id: str) -> None:
        """Set the application identifier for taskbar grouping."""
        ...

    def flash_taskbar(self, wid: int) -> None:
        """Flash the taskbar entry for *wid* to attract attention."""
        ...
