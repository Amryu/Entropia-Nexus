"""Tool cost filter — controls which tools contribute to hunt cost tracking.

Tools aren't limited to combat weapons: healing tools (FAPs), mining equipment,
crafting tools, etc. may be used during a hunt. This filter determines which
tool uses count toward the hunt's cost.
"""

from ..core.logger import get_logger

log = get_logger("ToolFilter")


class ToolFilter:
    """Determines whether a tool's cost should be included in hunt tracking.

    Supports two modes:
    - blacklist: include all tools EXCEPT those in the list
    - whitelist: include ONLY tools in the list

    Tool names are matched case-insensitively.
    """

    def __init__(self, config):
        self._config = config
        self._reload_filter()

    def _reload_filter(self):
        """Rebuild the filter set from config."""
        mode = getattr(self._config, 'tool_cost_filter_mode', 'blacklist')
        raw_list = getattr(self._config, 'tool_cost_filter_list', [])
        self._mode = mode if mode in ("blacklist", "whitelist") else "blacklist"
        self._tool_set = {name.lower() for name in raw_list}

    def should_include_cost(self, tool_name: str | None) -> bool:
        """Check if a tool's cost should count toward hunt cost.

        Args:
            tool_name: The tool name to check. None/"Unknown" are included
                       in blacklist mode (unknown = not blacklisted), excluded
                       in whitelist mode (not explicitly listed).

        Returns:
            True if the tool's cost should be included.
        """
        if not tool_name or tool_name == "Unknown":
            return self._mode == "blacklist"

        name_lower = tool_name.lower()
        if self._mode == "whitelist":
            return name_lower in self._tool_set
        else:  # blacklist
            return name_lower not in self._tool_set

    def on_config_changed(self):
        """Re-read filter settings from config."""
        self._reload_filter()
