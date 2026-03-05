"""No-op fallback backend for unsupported platforms.

All feature queries return False, all operations are silent no-ops.
"""

from __future__ import annotations


class FallbackBackend:
    """Graceful degradation — features are disabled but the app runs."""

    # --- Capability queries ---

    def supports_focus_detection(self) -> bool:
        return False

    def supports_global_hotkeys(self) -> bool:
        return False

    # --- Focus detection (always empty / zero) ---

    def get_foreground_window_title(self) -> str:
        return ""

    def get_foreground_window_id(self) -> int:
        return 0

    def find_window_by_title_prefix(self, prefix: str) -> int | None:
        return None

    def is_window_visible(self, wid: int) -> bool:
        return False

    def is_window_minimized(self, wid: int) -> bool:
        return False

    def get_window_geometry(self, wid: int) -> tuple[int, int, int, int] | None:
        return None

    def get_window_pid(self, wid: int) -> int:
        return 0

    # --- Occlusion ---

    def is_window_occluded(self, target_wid: int, ignore_wids: set[int]) -> bool:
        return False

    # --- Window manipulation ---

    def set_click_through(self, wid: int) -> bool:
        return False

    def set_no_activate(self, wid: int) -> bool:
        return False

    def bring_to_foreground(self, wid: int) -> bool:
        return False

    def release_focus_to(self, title_prefix: str) -> bool:
        return False

    # --- Decoration ---

    def enable_shadow(self, wid: int) -> bool:
        return False

    # --- Hotkeys ---

    def register_hotkey_hook(self, callback) -> bool:
        return False

    def unregister_hotkey_hook(self) -> bool:
        return False

    # --- Desktop integration ---

    def set_app_id(self, app_id: str) -> None:
        pass

    def flash_taskbar(self, wid: int) -> None:
        pass
