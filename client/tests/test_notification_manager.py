"""Tests for the notification manager."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field

from client.chat_parser.models import GlobalEvent, GlobalType, TradeChatMessage
from client.notifications.manager import NotificationManager
from client.notifications.models import SOURCE_GLOBAL, SOURCE_TRADE_CHAT


@dataclass
class _FakeConfig:
    notification_rules: list = field(default_factory=list)
    trade_chat_notifications_enabled: bool = False
    trade_chat_ignore_list: list = field(default_factory=list)
    trade_chat_cooldown_minutes: int = 5
    trade_chat_keywords: list = field(default_factory=list)
    notification_sound_enabled: bool = True
    notification_toast_enabled: bool = True


def _make_global(player="Player1", target="Atrox Old", value=100.0,
                 is_hof=False, is_ath=False, global_type=GlobalType.KILL):
    return GlobalEvent(
        timestamp=datetime.now(),
        global_type=global_type,
        player_name=player,
        target_name=target,
        value=value,
        value_unit="PED",
        location=None,
        is_hof=is_hof,
        is_ath=is_ath,
    )


def _make_trade(username="Trader1", message="Selling [Adjusted Pixie (M)]",
                channel="Trade"):
    return TradeChatMessage(
        timestamp=datetime.now(),
        channel=channel,
        username=username,
        message=message,
    )


class TestNotificationManagerGlobals(unittest.TestCase):
    """Test global event notification processing."""

    def setUp(self):
        self.config = _FakeConfig()
        self.bus = MagicMock()
        self.manager = NotificationManager(
            config=self.config, event_bus=self.bus
        )
        self.manager.set_live()
        self.received = []
        self.manager.on_notification(lambda n: self.received.append(n))

    def tearDown(self):
        self.manager.cleanup()

    def test_no_rules_no_notification(self):
        self.manager._on_global_event(_make_global())
        self.assertEqual(len(self.received), 0)

    def test_matching_rule_creates_notification(self):
        from client.notifications.models import GlobalNotificationRule
        rules = [GlobalNotificationRule(id="1", action="notify", min_value=50)]
        self.manager.update_rules(rules)
        self.manager._on_global_event(_make_global(value=100))
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0].source, SOURCE_GLOBAL)
        self.assertIn("Player1", self.received[0].title)

    def test_suppress_rule_blocks_notification(self):
        from client.notifications.models import GlobalNotificationRule
        rules = [
            GlobalNotificationRule(id="1", action="notify", priority=10),
            GlobalNotificationRule(id="2", action="suppress", priority=100,
                                   player_name="Blocked"),
        ]
        self.manager.update_rules(rules)
        self.manager._on_global_event(_make_global(player="Blocked"))
        self.assertEqual(len(self.received), 0)
        # Other players go through
        self.manager._on_global_event(_make_global(player="Other"))
        self.assertEqual(len(self.received), 1)

    def test_not_live_ignores_events(self):
        from client.notifications.models import GlobalNotificationRule
        manager = NotificationManager(config=self.config, event_bus=self.bus)
        manager.update_rules([GlobalNotificationRule(id="1", action="notify")])
        received = []
        manager.on_notification(lambda n: received.append(n))
        # Not live yet
        manager._on_global_event(_make_global())
        self.assertEqual(len(received), 0)
        # After live
        manager.set_live()
        manager._on_global_event(_make_global())
        self.assertEqual(len(received), 1)
        manager.cleanup()

    def test_hof_gets_high_priority(self):
        from client.notifications.models import GlobalNotificationRule
        self.manager.update_rules([
            GlobalNotificationRule(id="1", action="notify")
        ])
        self.manager._on_global_event(_make_global(is_hof=True))
        self.assertEqual(self.received[0].priority, "high")
        self.assertIn("HoF", self.received[0].title)

    def test_ath_gets_high_priority(self):
        from client.notifications.models import GlobalNotificationRule
        self.manager.update_rules([
            GlobalNotificationRule(id="1", action="notify")
        ])
        self.manager._on_global_event(_make_global(is_ath=True))
        self.assertEqual(self.received[0].priority, "high")
        self.assertIn("ATH", self.received[0].title)


class TestNotificationManagerTradeChat(unittest.TestCase):
    """Test trade chat notification processing."""

    def setUp(self):
        self.config = _FakeConfig(trade_chat_notifications_enabled=True)
        self.bus = MagicMock()
        self.manager = NotificationManager(
            config=self.config, event_bus=self.bus
        )
        self.manager.set_live()
        self.received = []
        self.manager.on_notification(lambda n: self.received.append(n))

    def tearDown(self):
        self.manager.cleanup()

    def test_trade_disabled_no_notification(self):
        self.config.trade_chat_notifications_enabled = False
        self.manager._on_trade_chat(_make_trade())
        self.assertEqual(len(self.received), 0)

    def test_item_mention_creates_notification(self):
        self.manager._on_trade_chat(_make_trade(
            message="Selling [Adjusted Pixie (M)] 150%"
        ))
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0].source, SOURCE_TRADE_CHAT)
        self.assertIn("Adjusted Pixie", self.received[0].body)

    def test_no_brackets_no_notification(self):
        self.manager._on_trade_chat(_make_trade(
            message="Selling stuff cheap"
        ))
        self.assertEqual(len(self.received), 0)

    def test_cooldown_prevents_duplicate(self):
        msg = _make_trade(message="Selling [Pixie (M)]")
        self.manager._on_trade_chat(msg)
        self.assertEqual(len(self.received), 1)
        # Same player+item within cooldown
        self.manager._on_trade_chat(msg)
        self.assertEqual(len(self.received), 1)

    def test_different_item_not_cooled_down(self):
        self.manager._on_trade_chat(_make_trade(
            message="Selling [Pixie (M)]"
        ))
        self.manager._on_trade_chat(_make_trade(
            message="Selling [Gremlin (M)]"
        ))
        self.assertEqual(len(self.received), 2)

    def test_different_player_not_cooled_down(self):
        self.manager._on_trade_chat(_make_trade(
            username="Player1", message="Selling [Pixie (M)]"
        ))
        self.manager._on_trade_chat(_make_trade(
            username="Player2", message="Selling [Pixie (M)]"
        ))
        self.assertEqual(len(self.received), 2)

    def test_ignore_list(self):
        self.manager.update_trade_ignore(["SpamBot"])
        self.manager._on_trade_chat(_make_trade(
            username="SpamBot", message="Selling [Pixie (M)]"
        ))
        self.assertEqual(len(self.received), 0)

    def test_ignore_list_case_insensitive(self):
        self.manager.update_trade_ignore(["spambot"])
        self.manager._on_trade_chat(_make_trade(
            username="SpamBot", message="Selling [Pixie (M)]"
        ))
        self.assertEqual(len(self.received), 0)

    def test_waypoint_pattern_skipped(self):
        self.manager._on_trade_chat(_make_trade(
            message="TP here [Camp Icarus, 123, 456, 789, Waypoint]"
        ))
        self.assertEqual(len(self.received), 0)

    def test_multiple_items_in_message(self):
        self.manager._on_trade_chat(_make_trade(
            message="Selling [Pixie (M)] and [Gremlin (M)]"
        ))
        self.assertEqual(len(self.received), 2)


class TestNotificationManagerStorage(unittest.TestCase):
    """Test notification storage and read state."""

    def setUp(self):
        self.config = _FakeConfig()
        self.bus = MagicMock()
        self.manager = NotificationManager(
            config=self.config, event_bus=self.bus
        )
        self.manager.set_live()

    def tearDown(self):
        self.manager.cleanup()

    def test_get_notifications_empty(self):
        self.assertEqual(self.manager.get_notifications(), [])

    def test_unread_count(self):
        from client.notifications.models import GlobalNotificationRule
        self.manager.update_rules([GlobalNotificationRule(id="1", action="notify")])
        self.manager._on_global_event(_make_global())
        self.manager._on_global_event(_make_global())
        self.assertEqual(self.manager.get_unread_count(), 2)

    def test_mark_read(self):
        from client.notifications.models import GlobalNotificationRule
        self.manager.update_rules([GlobalNotificationRule(id="1", action="notify")])
        self.manager._on_global_event(_make_global())
        notifs = self.manager.get_notifications()
        self.manager.mark_read(notifs[0].id)
        self.assertEqual(self.manager.get_unread_count(), 0)

    def test_mark_all_read(self):
        from client.notifications.models import GlobalNotificationRule
        self.manager.update_rules([GlobalNotificationRule(id="1", action="notify")])
        self.manager._on_global_event(_make_global())
        self.manager._on_global_event(_make_global())
        self.manager.mark_all_read()
        self.assertEqual(self.manager.get_unread_count(), 0)

    def test_most_recent_first(self):
        from client.notifications.models import GlobalNotificationRule
        self.manager.update_rules([GlobalNotificationRule(id="1", action="notify")])
        self.manager._on_global_event(_make_global(player="First"))
        self.manager._on_global_event(_make_global(player="Second"))
        notifs = self.manager.get_notifications()
        self.assertIn("Second", notifs[0].title)
        self.assertIn("First", notifs[1].title)


class TestNotificationManagerServerNotifications(unittest.TestCase):
    """Test server notification polling and first-poll catchup."""

    def setUp(self):
        self.config = _FakeConfig()
        self.bus = MagicMock()
        self.nexus_client = MagicMock()
        self.manager = NotificationManager(
            config=self.config, event_bus=self.bus,
            nexus_client=self.nexus_client,
        )
        self.received = []
        self.manager.on_notification(lambda n: self.received.append(n))

    def tearDown(self):
        self.manager.cleanup()

    def test_first_poll_seeds_without_notifying(self):
        """First poll populates seen IDs without creating notifications."""
        self.nexus_client.get_notifications.return_value = {
            "rows": [
                {"id": 1, "type": "Society", "message": "Old msg 1"},
                {"id": 2, "type": "Rental", "message": "Old msg 2"},
            ]
        }
        self.manager.poll_server_notifications()
        self.assertEqual(len(self.received), 0)
        self.assertTrue(self.manager._server_notif_initialized)
        self.assertEqual(self.manager._seen_server_ids, {1, 2})

    def test_second_poll_notifies_new_ids(self):
        """After first poll, new notification IDs trigger notifications."""
        self.nexus_client.get_notifications.return_value = {
            "rows": [{"id": 1, "type": "Society", "message": "Old msg"}]
        }
        self.manager.poll_server_notifications()  # first poll, no notify
        self.assertEqual(len(self.received), 0)

        self.nexus_client.get_notifications.return_value = {
            "rows": [
                {"id": 1, "type": "Society", "message": "Old msg"},
                {"id": 3, "type": "Rental", "message": "New msg"},
            ]
        }
        self.manager.poll_server_notifications()  # second poll
        self.assertEqual(len(self.received), 1)
        self.assertIn("Rental", self.received[0].title)

    def test_already_seen_not_duplicated(self):
        """IDs seen on first poll are not re-notified on subsequent polls."""
        self.nexus_client.get_notifications.return_value = {
            "rows": [{"id": 1, "type": "Society", "message": "Msg"}]
        }
        self.manager.poll_server_notifications()  # first poll
        self.manager.poll_server_notifications()  # second poll, same data
        self.manager.poll_server_notifications()  # third poll
        self.assertEqual(len(self.received), 0)


class TestNotificationManagerStreams(unittest.TestCase):
    """Test stream notification polling and deduplication."""

    def setUp(self):
        self.config = _FakeConfig()
        self.config.stream_notifications_enabled = True
        self.config.stream_exclude_list = []
        self.bus = MagicMock()
        self.nexus_client = MagicMock()
        self.manager = NotificationManager(
            config=self.config, event_bus=self.bus,
            nexus_client=self.nexus_client,
        )
        self.manager.set_live()
        self.received = []
        self.manager.on_notification(lambda n: self.received.append(n))

    def tearDown(self):
        self.manager.cleanup()

    def _make_creators(self, live_ids):
        """Helper to create creator list; live_ids are the ones that are live."""
        creators = []
        for cid in [1, 2, 3]:
            creators.append({
                "id": cid,
                "name": f"Streamer{cid}",
                "platform": "twitch",
                "channel_url": f"https://twitch.tv/streamer{cid}",
                "is_live": cid in live_ids,
                "stream_title": f"Stream {cid}" if cid in live_ids else None,
                "game_name": "Entropia Universe" if cid in live_ids else None,
                "viewer_count": 10 * cid if cid in live_ids else 0,
            })
        return creators

    def test_first_poll_no_notifications(self):
        """First poll populates known-live set without notifying."""
        self.nexus_client.get_streams.return_value = self._make_creators([1, 2])
        self.manager.poll_streams()
        self.assertEqual(len(self.received), 0)
        self.assertTrue(self.manager._streams_initialized)
        self.assertEqual(self.manager._known_live, {1, 2})

    def test_new_stream_triggers_notification(self):
        """After first poll, newly live stream triggers notification."""
        self.nexus_client.get_streams.return_value = self._make_creators([1])
        self.manager.poll_streams()  # first poll
        self.assertEqual(len(self.received), 0)

        self.nexus_client.get_streams.return_value = self._make_creators([1, 2])
        self.manager.poll_streams()  # second poll
        self.assertEqual(len(self.received), 1)
        self.assertIn("Streamer2", self.received[0].title)

    def test_still_live_no_double_notification(self):
        """A stream that stays live doesn't re-notify."""
        self.nexus_client.get_streams.return_value = self._make_creators([1])
        self.manager.poll_streams()  # first poll

        self.nexus_client.get_streams.return_value = self._make_creators([1])
        self.manager.poll_streams()  # still live
        self.manager.poll_streams()  # still live
        self.assertEqual(len(self.received), 0)

    def test_stream_ends_and_restarts(self):
        """Stream going offline then back online triggers new notification."""
        self.nexus_client.get_streams.return_value = self._make_creators([1])
        self.manager.poll_streams()  # first poll, no notify

        self.nexus_client.get_streams.return_value = self._make_creators([])
        self.manager.poll_streams()  # stream went offline

        self.nexus_client.get_streams.return_value = self._make_creators([1])
        self.manager.poll_streams()  # back online
        self.assertEqual(len(self.received), 1)
        self.assertIn("Streamer1", self.received[0].title)

    def test_exclude_list(self):
        """Excluded streamers don't trigger notifications."""
        self.manager.update_stream_exclude(["Streamer2"])
        self.nexus_client.get_streams.return_value = self._make_creators([])
        self.manager.poll_streams()  # first poll

        self.nexus_client.get_streams.return_value = self._make_creators([1, 2])
        self.manager.poll_streams()
        self.assertEqual(len(self.received), 1)
        self.assertIn("Streamer1", self.received[0].title)

    def test_exclude_list_case_insensitive(self):
        self.manager.update_stream_exclude(["streamer1"])
        self.nexus_client.get_streams.return_value = self._make_creators([])
        self.manager.poll_streams()

        self.nexus_client.get_streams.return_value = self._make_creators([1])
        self.manager.poll_streams()
        self.assertEqual(len(self.received), 0)

    def test_disabled_skips_polling(self):
        self.config.stream_notifications_enabled = False
        self.nexus_client.get_streams.return_value = self._make_creators([])
        self.manager.poll_streams()

        self.nexus_client.get_streams.return_value = self._make_creators([1])
        self.manager.poll_streams()
        self.assertEqual(len(self.received), 0)

    def test_api_returns_none(self):
        """Gracefully handles API failure."""
        self.nexus_client.get_streams.return_value = None
        self.manager.poll_streams()
        self.assertEqual(len(self.received), 0)
        self.assertFalse(self.manager._streams_initialized)

    def test_notification_metadata(self):
        """Stream notification has correct metadata."""
        self.nexus_client.get_streams.return_value = self._make_creators([])
        self.manager.poll_streams()

        self.nexus_client.get_streams.return_value = self._make_creators([2])
        self.manager.poll_streams()
        self.assertEqual(len(self.received), 1)
        notif = self.received[0]
        self.assertEqual(notif.metadata["creator_id"], 2)
        self.assertEqual(notif.metadata["platform"], "twitch")
        self.assertIn("twitch.tv", notif.metadata["channel_url"])


if __name__ == "__main__":
    unittest.main()
