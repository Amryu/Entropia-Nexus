import unittest
from unittest.mock import MagicMock

from client.core.event_bus import EventBus


class TestEventBus(unittest.TestCase):

    def setUp(self):
        self.bus = EventBus()

    def test_subscribe_and_publish(self):
        cb = MagicMock()
        self.bus.subscribe("test", cb)
        self.bus.publish("test", {"key": "value"})
        cb.assert_called_once_with({"key": "value"})

    def test_multiple_subscribers(self):
        cb1 = MagicMock()
        cb2 = MagicMock()
        self.bus.subscribe("test", cb1)
        self.bus.subscribe("test", cb2)
        self.bus.publish("test", 42)
        cb1.assert_called_once_with(42)
        cb2.assert_called_once_with(42)

    def test_unsubscribe(self):
        cb = MagicMock()
        self.bus.subscribe("test", cb)
        self.bus.unsubscribe("test", cb)
        self.bus.publish("test", "data")
        cb.assert_not_called()

    def test_unsubscribe_nonexistent(self):
        cb = MagicMock()
        # Should not raise
        self.bus.unsubscribe("test", cb)

    def test_duplicate_subscribe_ignored(self):
        cb = MagicMock()
        self.bus.subscribe("test", cb)
        self.bus.subscribe("test", cb)
        self.bus.publish("test", None)
        cb.assert_called_once_with(None)

    def test_publish_no_subscribers(self):
        # Should not raise
        self.bus.publish("nonexistent", "data")

    def test_callback_exception_does_not_block_others(self):
        bad_cb = MagicMock(side_effect=RuntimeError("boom"))
        good_cb = MagicMock()
        self.bus.subscribe("test", bad_cb)
        self.bus.subscribe("test", good_cb)
        self.bus.publish("test", "data")
        bad_cb.assert_called_once()
        good_cb.assert_called_once_with("data")

    def test_publish_passes_none_by_default(self):
        cb = MagicMock()
        self.bus.subscribe("test", cb)
        self.bus.publish("test")
        cb.assert_called_once_with(None)

    def test_separate_event_types(self):
        cb_a = MagicMock()
        cb_b = MagicMock()
        self.bus.subscribe("a", cb_a)
        self.bus.subscribe("b", cb_b)
        self.bus.publish("a", "data_a")
        cb_a.assert_called_once_with("data_a")
        cb_b.assert_not_called()


if __name__ == "__main__":
    unittest.main()
