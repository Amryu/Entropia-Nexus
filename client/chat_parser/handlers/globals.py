from ...core.constants import (
    EVENT_GLOBAL,
    GLOBAL_ATH_KEYWORD,
    GLOBAL_CRAFT_PATTERN,
    GLOBAL_DEPOSIT_PATTERN,
    GLOBAL_HOF_SUFFIX,
    GLOBAL_KILL_PATTERN,
    GLOBAL_RARE_PATTERN,
    GLOBAL_TEAM_KILL_PATTERN,
)
from ..models import GlobalEvent, GlobalType, ParsedLine
from .base import BaseHandler


class GlobalsHandler(BaseHandler):
    """Handles global announcement messages (kills, deposits, crafts, rare items)."""

    def can_handle(self, parsed_line: ParsedLine) -> bool:
        return parsed_line.channel == "Globals" and parsed_line.username == ""

    def handle(self, parsed_line: ParsedLine) -> None:
        msg = parsed_line.message
        is_hof = GLOBAL_HOF_SUFFIX in msg
        is_ath = GLOBAL_ATH_KEYWORD in msg

        event = None

        # Team kill (must check before regular kill)
        match = GLOBAL_TEAM_KILL_PATTERN.search(msg)
        if match:
            location = self._extract_location(msg, match.end())
            event = GlobalEvent(
                timestamp=parsed_line.timestamp,
                global_type=GlobalType.TEAM_KILL,
                player_name=match.group(1),
                target_name=match.group(2),
                value=float(match.group(3)),
                value_unit="PED",
                location=location,
                is_hof=is_hof,
                is_ath=is_ath,
            )
        if not event:
            # Rare item (check before kill since "has found" is distinct)
            match = GLOBAL_RARE_PATTERN.search(msg)
            if match:
                event = GlobalEvent(
                    timestamp=parsed_line.timestamp,
                    global_type=GlobalType.RARE_ITEM,
                    player_name=match.group(1),
                    target_name=match.group(2),
                    value=float(match.group(3)),
                    value_unit=match.group(4),
                    is_hof=is_hof,
                    is_ath=is_ath,
                )
        if not event:
            # Deposit
            match = GLOBAL_DEPOSIT_PATTERN.search(msg)
            if match:
                location = self._extract_location(msg, match.end())
                event = GlobalEvent(
                    timestamp=parsed_line.timestamp,
                    global_type=GlobalType.DEPOSIT,
                    player_name=match.group(1),
                    target_name=match.group(2),
                    value=float(match.group(3)),
                    value_unit="PED",
                    location=location,
                    is_hof=is_hof,
                    is_ath=is_ath,
                )
        if not event:
            # Craft
            match = GLOBAL_CRAFT_PATTERN.search(msg)
            if match:
                event = GlobalEvent(
                    timestamp=parsed_line.timestamp,
                    global_type=GlobalType.CRAFT,
                    player_name=match.group(1),
                    target_name=match.group(2),
                    value=float(match.group(3)),
                    value_unit="PED",
                    is_hof=is_hof,
                    is_ath=is_ath,
                )
        if not event:
            # Regular kill
            match = GLOBAL_KILL_PATTERN.search(msg)
            if match:
                location = self._extract_location(msg, match.end())
                event = GlobalEvent(
                    timestamp=parsed_line.timestamp,
                    global_type=GlobalType.KILL,
                    player_name=match.group(1),
                    target_name=match.group(2),
                    value=float(match.group(3)),
                    value_unit="PED",
                    location=location,
                    is_hof=is_hof,
                    is_ath=is_ath,
                )

        if event:
            self._event_bus.publish(EVENT_GLOBAL, event)
            self._db.insert_global(
                timestamp=event.timestamp.isoformat(),
                global_type=event.global_type.value,
                player_name=event.player_name,
                target_name=event.target_name,
                value=event.value,
                value_unit=event.value_unit,
                location=event.location,
                is_hof=event.is_hof,
                is_ath=event.is_ath,
            )

    @staticmethod
    def _extract_location(msg: str, after_pos: int) -> str | None:
        """Extract location from ' at <Location>!' suffix after the main pattern match.

        The remainder after the match can be:
          '!'                                    -> no location
          ' at Takuta Plateau!'                  -> location
          '! A record has been added...'         -> no location, HoF
          ' at F.O.M.A.! A record has been...'  -> location + HoF
        """
        remainder = msg[after_pos:]
        # Check for ' at ' which indicates a location follows
        if not remainder.startswith(" at "):
            return None

        loc = remainder[4:]  # skip ' at '
        # Remove known suffixes from the end
        for suffix in [
            " A record has been added to the Hall of Fame!",
        ]:
            idx = loc.find(suffix)
            if idx != -1:
                loc = loc[:idx]
        loc = loc.rstrip("! ")
        return loc if loc else None
