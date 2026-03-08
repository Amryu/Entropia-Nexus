# Client Development Guidelines

PyQt6 desktop application. Read `ui/theme.py` and `core/event_bus.py` before writing new code.

---

## 1. Threading & Background Work

**Everything expensive runs off the main thread.** Network calls, file I/O, database bulk operations, image processing — never block the UI.

### `threading.Thread` (fire-and-forget)

```python
def _load_items(self):
    def _do():
        try:
            items = self._client.get_items()
            self._items_loaded.emit(items)  # signal back to UI
        except Exception as e:
            log.error("Failed to load items: %s", e)

    threading.Thread(target=_do, daemon=True, name="load-items").start()
```

### `QThread` (when you need progress/result signals)

```python
class _DataLoader(QThread):
    finished = pyqtSignal(object, str)  # result, error

    def __init__(self, client):
        super().__init__()
        self._client = client

    def run(self):
        try:
            result = self._client.fetch()
            self.finished.emit(result, "")
        except Exception as e:
            self.finished.emit(None, str(e))

# Usage:
worker = _DataLoader(client)
worker.finished.connect(self._on_loaded)
worker.start()
```

### Rules

- Always `daemon=True` on background threads
- Always give threads a descriptive `name=` — crash reports list active threads
- Use `QTimer` for periodic polling, not busy-wait threads
- Protect shared mutable state with `threading.Lock()`
- Use `threading.Event.wait(timeout=...)` for efficient blocking — not `time.sleep` loops

---

## 2. Thread-to-UI Communication

Background threads must **never** touch Qt widgets directly. Two communication paths:

### Path A: pyqtSignal (widget-local)

Emit from `QThread.run()`, connect in the widget constructor. Qt auto-marshals to the main thread.

### Path B: EventBus → AppSignals (app-wide)

```
Background thread                    Main thread
       │                                  │
       ├─ event_bus.publish(EVENT_X, data) │
       │                                  │
       │    signals.py wires:             │
       │    event_bus ──► AppSignals.x ───► widget._on_x()
```

```python
# In a widget:
class MyWidget(QWidget):
    def __init__(self, signals: AppSignals):
        super().__init__()
        signals.skill_gain.connect(self._on_skill_gain)

    def _on_skill_gain(self, data):
        # Runs on main thread — safe to update widgets
        self._label.setText(f"+{data.amount}")
```

- `event_bus.subscribe()` returns `None` — to unsubscribe, call `event_bus.unsubscribe(event_type, callback)`
- Add new app-wide events to `core/constants.py` and wire in `ui/signals.py`

---

## 3. UI Consistency

### Colors

Import from `ui/theme.py` — never hardcode hex values.

```python
from ..theme import ACCENT, TEXT_MUTED, BORDER, SECONDARY
```

Key constants: `PRIMARY`, `SECONDARY`, `MAIN_DARK`, `HOVER`, `ACCENT`, `ACCENT_HOVER`, `TEXT`, `TEXT_MUTED`, `BORDER`, `ERROR`, `SUCCESS`, `WARNING`.

### Global QSS Object Names

The global stylesheet (`theme.get_stylesheet()`) targets these object names:

| Object Name | Effect | Usage |
|-------------|--------|-------|
| `pageHeader` | 18px bold | `label.setObjectName("pageHeader")` |
| `accentButton` | Blue accent background | `btn.setObjectName("accentButton")` |
| `mutedText` | Muted italic | `label.setObjectName("mutedText")` |
| `summaryValue` | 16px bold | `label.setObjectName("summaryValue")` |

### Spacing

- Page/dialog outer margins: `layout.setContentsMargins(24, 20, 24, 20)`
- Between items: `layout.setSpacing(8)` (general), `setSpacing(12)` (sections)
- Frameless containers: `setContentsMargins(0, 0, 0, 0)` + `setSpacing(0)`

### Dialogs

```python
class MyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Title")
        self.setMinimumSize(520, 400)
        self.setStyleSheet(f"QDialog {{ background-color: {SECONDARY}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
```

Use `QStackedWidget` for multi-page dialog flows.

### ScrollArea

```python
scroll = QScrollArea()
scroll.setWidgetResizable(True)  # required
scroll.setStyleSheet("QScrollArea { border: none; }")
```

### Pages

Pages are lazy-loaded via factory functions in `main_window.py`'s `_page_factories` dict. Add new pages there.

### QSS Performance

Pre-compute style strings at module level — don't build f-string QSS inside loops:

```python
# Good — computed once
_CARD_STYLE = f"background: {SECONDARY}; border: 1px solid {BORDER}; border-radius: 6px;"

# Bad — recomputed every iteration
for item in items:
    widget.setStyleSheet(f"background: {SECONDARY}; ...")
```

### No `alert()`

Use `NotificationCenter` for in-app messages or `QMessageBox` for critical modal dialogs.

---

## 4. Logging

```python
from ..core.logger import get_logger
log = get_logger("ModuleName")

log.error("Connection failed: %s", err)     # always shown
log.warning("Retrying in %ds", delay)        # always shown
log.info("Loaded %d items", count)           # verbose mode only
log.debug("Raw response: %s", resp)          # verbose mode only
```

- Use `%s` formatting in log calls (deferred evaluation), not f-strings
- Never let logging failures crash the app — the logger handles this internally
- File log: `~/.entropia-nexus/client.log` — WARNING+ only, 256 KB rolling, 1-hour retention

---

## 5. Error Handling

- Catch specific exceptions when possible; broad `Exception` only at thread/module boundaries
- API client methods return `None` on failure — callers check for `None` instead of catching
- Define custom exceptions for specific recoverable errors (e.g., `RateLimitError` with `retry_after`)
- The crash handler (`core/crash_handler.py`) catches uncaught exceptions on both main and background threads, sanitizes file paths to protect privacy, and shows a diagnostic dialog

---

## 6. Code Style

### Module Header

Every module starts with:

```python
from __future__ import annotations
```

### Type Hints

```python
def fetch_data(self, item_id: int, *, force: bool = False) -> dict | None:
```

### Data Models

```python
@dataclass
class SkillGainEvent:
    timestamp: datetime
    skill_name: str
    amount: float
    is_attribute: bool
```

Use `Enum` for fixed sets:

```python
class MessageType(Enum):
    SKILL_GAIN = "skill_gain"
    DAMAGE_DEALT = "damage_dealt"
```

### Naming

- Private methods/attributes: `_underscore_prefix`
- Constants: `UPPER_SNAKE_CASE` in dedicated modules (`core/constants.py`, `ui/theme.py`)
- Properties via `@property` / `@x.setter` for validated access

### Import Order

1. Standard library (`import os`, `import threading`)
2. Third-party (`from PyQt6.QtWidgets import ...`)
3. Relative imports (`from ..core.logger import get_logger`)

---

## 7. Chat Parser Handlers

Inherit from `BaseHandler` (`chat_parser/handlers/base.py`):

```python
class MyHandler(BaseHandler):
    def can_handle(self, parsed_line: ParsedLine) -> bool:
        return (parsed_line.channel == "System"
                and parsed_line.message.startswith("Some pattern"))

    def handle(self, parsed_line: ParsedLine) -> None:
        event = SomeEvent(...)
        if not self.suppress_events:
            self._event_bus.publish(EVENT_SOMETHING, event)
        self._db.insert_event(event)
```

---

## 8. Configuration

- Add new settings to `AppConfig` dataclass in `core/config.py` with sensible defaults
- Config is JSON-backed, saved atomically (write `.tmp` → fsync → rename → `.bak` backup)
- Bump `SCAN_ROI_VERSION` when OCR ROI default regions change

---

## 9. Testing

```python
class TestMyHandler(unittest.TestCase):
    def setUp(self):
        self.bus = MagicMock()
        self.db = MagicMock()
        self.handler = MyHandler(self.bus, self.db)

    def test_handles_event(self):
        line = _make_line("You have gained 0.1234 experience")
        self.handler.handle(line)

        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.amount, 0.1234)
        self.bus.publish.assert_called_once()
```

- Framework: `unittest` with `unittest.mock.MagicMock`
- Test files: `client/tests/test_*.py`
- Mock `EventBus` and `Database` — never hit real I/O in tests

---

## 10. Database

- SQLite via `core/database.py` — single connection, protected by `threading.Lock()`
- Always use parameterized queries — never string interpolation
- Heavy DB operations (bulk inserts, pruning) must run on background threads

---

## Key Reference Files

| File | Purpose |
|------|---------|
| `ui/theme.py` | Color constants, layout dimensions, global QSS |
| `ui/signals.py` | EventBus → Qt signal bridge (~40 signals) |
| `ui/main_window.py` | Root window, page stacking, navigation history |
| `core/event_bus.py` | Thread-safe publish/subscribe |
| `core/logger.py` | Centralized logging with ring buffer |
| `core/config.py` | AppConfig dataclass, atomic JSON save |
| `core/crash_handler.py` | Global exception hooks, crash reports |
| `core/database.py` | SQLite wrapper with thread lock |
| `core/constants.py` | Event name constants |
| `chat_parser/handlers/base.py` | BaseHandler ABC |
