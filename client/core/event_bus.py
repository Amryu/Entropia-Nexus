import threading
from collections import defaultdict
from typing import Any, Callable

from .logger import get_logger

log = get_logger("EventBus")


class EventBus:
    """Thread-safe publish/subscribe event bus for inter-module communication."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass

    def publish(self, event_type: str, data: Any = None) -> None:
        with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))
        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                log.error("Error in callback for '%s': %s", event_type, e)
