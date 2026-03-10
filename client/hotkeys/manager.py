"""Global hotkey manager using the keyboard library."""

from ..core.constants import EVENT_HOTKEY_TRIGGERED
from ..core.logger import get_logger
from ..platform import backend as _platform

log = get_logger("Hotkeys")

# Maps config field names to action identifiers
HOTKEY_ACTIONS = {
    # Hunt hotkeys disabled
    # "hotkey_start_hunt": "start_hunt",
    # "hotkey_stop_hunt": "stop_hunt",
    # "hotkey_manual_mob_name": "manual_mob_name",
    # "hotkey_ocr_scan": "ocr_scan",
    "hotkey_screenshot": "screenshot",
    "hotkey_save_clip": "save_clip",
    "hotkey_toggle_recording": "toggle_recording",
}


class HotkeyManager:
    """Registers global keyboard hooks for configurable hotkeys.

    Hotkey combos are stored in AppConfig as strings (e.g., "ctrl+shift+h").
    When triggered, publishes EVENT_HOTKEY_TRIGGERED with the action name.
    """

    def __init__(self, config, event_bus):
        self._config = config
        self._event_bus = event_bus
        self._registered = []

    def start(self):
        """Register all configured hotkeys."""
        if not _platform.supports_global_hotkeys():
            return
        try:
            import keyboard
        except ImportError:
            log.warning("keyboard library not installed — skipping")
            return

        for config_key, action in HOTKEY_ACTIONS.items():
            combo = getattr(self._config, config_key, "")
            if not combo:
                continue

            try:
                keyboard.add_hotkey(
                    combo,
                    lambda a=action: self._event_bus.publish(
                        EVENT_HOTKEY_TRIGGERED, {"action": a}
                    ),
                )
                self._registered.append(combo)
                log.info("Registered: %s -> %s", combo, action)
            except Exception as e:
                log.warning("Failed to register %s: %s", combo, e)

    def stop(self):
        """Unregister all hotkeys."""
        try:
            import keyboard
            for combo in self._registered:
                try:
                    keyboard.remove_hotkey(combo)
                except Exception:
                    pass
            self._registered.clear()
        except ImportError:
            pass

    def reload(self, config):
        """Re-register hotkeys after config change."""
        self.stop()
        self._config = config
        self.start()
