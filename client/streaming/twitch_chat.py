"""Read-only Twitch IRC chat client via WebSocket.

Connects anonymously (no auth required) and emits parsed messages
via pyqtSignal for the overlay to consume.
"""

from __future__ import annotations

import re
import time

from PyQt6.QtCore import QThread, pyqtSignal

from ..core.logger import get_logger

log = get_logger("TwitchChat")

_WS_URL = "wss://irc-ws.chat.twitch.tv:443"
_ANON_NICK = "justinfan12345"
_MAX_RETRIES = 3
_RETRY_DELAY = 5  # seconds

# IRC message parsing
_TAG_RE = re.compile(r"@(\S+)")
_PREFIX_RE = re.compile(r":(\S+)")
_PRIVMSG_RE = re.compile(
    r"^(?:@(\S+)\s+)?:(\S+)\s+PRIVMSG\s+#(\S+)\s+:(.*)$"
)

try:
    from websockets.sync.client import connect as ws_connect
    from websockets.exceptions import ConnectionClosed
    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False


def has_websockets() -> bool:
    return _WS_AVAILABLE


def parse_tags(tag_str: str) -> dict[str, str]:
    """Parse IRC tags string into a dict."""
    tags = {}
    for part in tag_str.split(";"):
        if "=" in part:
            key, _, val = part.partition("=")
            tags[key] = val
        else:
            tags[part] = ""
    return tags


def parse_emotes_tag(emotes_str: str) -> list[dict]:
    """Parse the 'emotes' IRC tag into a list of {id, start, end} dicts.

    Format: ``emoteId:start-end,start-end/emoteId:start-end``
    Returns sorted by start position (ascending).
    """
    if not emotes_str:
        return []

    result = []
    for group in emotes_str.split("/"):
        if ":" not in group:
            continue
        emote_id, _, positions = group.partition(":")
        for pos in positions.split(","):
            if "-" not in pos:
                continue
            start_s, _, end_s = pos.partition("-")
            try:
                result.append({
                    "id": emote_id,
                    "start": int(start_s),
                    "end": int(end_s),
                })
            except ValueError:
                continue

    result.sort(key=lambda e: e["start"])
    return result


def parse_badges_tag(badges_str: str) -> list[str]:
    """Parse the 'badges' IRC tag into a list of badge type strings.

    Format: ``broadcaster/1,subscriber/12,moderator/1``
    Returns: ``["broadcaster", "subscriber", "moderator"]``
    """
    if not badges_str:
        return []
    result = []
    for badge in badges_str.split(","):
        if "/" in badge:
            badge_type, _, _ = badge.partition("/")
            result.append(badge_type)
    return result


class TwitchChatClient(QThread):
    """Read-only Twitch IRC chat client running on a QThread.

    Signals:
        message_received(dict): Parsed chat message with keys:
            display_name, color, badges, emotes, message, timestamp
        connected(): Successfully connected and joined channel
        disconnected(str): Disconnected with reason string
    """

    message_received = pyqtSignal(dict)
    connected = pyqtSignal()
    disconnected = pyqtSignal(str)

    def __init__(self, channel: str, parent=None):
        super().__init__(parent)
        self._channel = channel.lower().lstrip("#")
        self._running = False

    def stop(self):
        """Signal the thread to stop."""
        self._running = False

    def run(self):
        if not _WS_AVAILABLE:
            self.disconnected.emit("websockets library not installed")
            return

        self._running = True
        retries = 0

        while self._running and retries < _MAX_RETRIES:
            try:
                self._run_connection()
                # Clean exit (stop() was called)
                if not self._running:
                    break
            except Exception as exc:
                log.debug("Chat connection error: %s", exc)

            retries += 1
            if self._running and retries < _MAX_RETRIES:
                log.debug("Reconnecting in %ds (attempt %d/%d)",
                          _RETRY_DELAY, retries + 1, _MAX_RETRIES)
                # Interruptible sleep
                for _ in range(int(_RETRY_DELAY * 10)):
                    if not self._running:
                        break
                    time.sleep(0.1)

        if self._running:
            self.disconnected.emit("max retries exceeded")
        else:
            self.disconnected.emit("stopped")

    def _run_connection(self):
        """Single connection lifecycle."""
        with ws_connect(_WS_URL) as ws:
            # Request tags and commands capabilities
            ws.send("CAP REQ :twitch.tv/tags twitch.tv/commands")
            ws.send(f"NICK {_ANON_NICK}")
            ws.send(f"JOIN #{self._channel}")

            self.connected.emit()
            log.debug("Joined #%s", self._channel)

            while self._running:
                try:
                    raw = ws.recv(timeout=1.0)
                except TimeoutError:
                    continue
                except ConnectionClosed:
                    self.disconnected.emit("connection closed")
                    return

                if not raw:
                    continue

                for line in raw.split("\r\n"):
                    if not line:
                        continue
                    self._handle_line(line, ws)

    def _handle_line(self, line: str, ws):
        """Process a single IRC line."""
        # PING keepalive
        if line.startswith("PING"):
            ws.send("PONG :tmi.twitch.tv")
            return

        # PRIVMSG (chat message)
        match = _PRIVMSG_RE.match(line)
        if match:
            tag_str, _user, _channel, message = match.groups()
            tags = parse_tags(tag_str) if tag_str else {}

            self.message_received.emit({
                "display_name": tags.get("display-name", ""),
                "color": tags.get("color", ""),
                "badges": parse_badges_tag(tags.get("badges", "")),
                "emotes": parse_emotes_tag(tags.get("emotes", "")),
                "message": message,
                "timestamp": time.time(),
            })
