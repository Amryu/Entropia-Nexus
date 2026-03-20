# General

- Prefer existing components before creating new ones; make new controls easily discoverable
- Write notes in /claude for big tasks
- Playwright testing: dev.entropianexus.com (API: 3000, Frontend: 3001)
- Avoid magic numbers - use constants
- Question your approach and estimate success rate. If less than 80% certain, ask instead of guessing.
- After implementing, look for further steps that need fixing or optimizing — especially consistency, redundancy, and security issues.
- After every feature addition, check if there is potential to consolidate existing code and find opportunities to reduce the line count (do not reduce line count by making lines more complicated)
- Never use `nexusPool` in the frontend except for the purpose stated in the comment next to it

# Database

- `/sql/<db>/dumps`: structure dumps (may be outdated)
- `/sql/<db>/migrations`: changes during development - check here for missing tables
- Create migration files for schema changes, never modify directly
- Local/test databases are NOT in sync with production — do not rely on MCP query results for production data
- Production data lives in the non-test MCP tools (`mcp__postgres-nexus__query`, `mcp__postgres-nexus-users__query`)
- Migrations are the source of truth for schema

# Client Config (`client/core/config.py`)

- `AppConfig` is a `@dataclass` — add new fields with defaults directly (e.g. `field_name: type = default`)
- **CRITICAL**: New fields must also be added to the `DEFAULTS` dict (~line 311). `save_config` iterates `DEFAULTS`, not the dataclass fields — missing entries won't be persisted.
- **Tuple fields** (positions, ROIs) are stored as JSON arrays. Add the field name to the list-to-tuple conversion loop (~line 620) so they're converted back on load.
- **Migrations**: Remove/rename old fields via `merged.pop("old_key", None)` before the `AppConfig()` constructor (see existing migrations around line 540+).
- Save with `save_config(config, config_path)` + `event_bus.publish(EVENT_CONFIG_CHANGED, config)`.

# Guidelines

- Read project-specific `guidelines.md` before working
- Never use `alert()` - use notifications or dialogs
- Ensure consistency: headers, breadcrumbs, back navigation (buttons, not links)
- URL shortening maintenance is required: whenever a new public page route or pseudo-page route is added/changed, update `nexus/src/lib/server/short-url.js` mappings and keep `nexus/scripts/verify-short-route-coverage.mjs` passing.

# Client Threading (PyQt6)

Full patterns in `client/guidelines.md` §1–2. Key rules:

## What blocks the main thread (FreezeDetector triggers at 0.5s)
- HoughCircles / image processing, network calls, file I/O, database bulk ops, ONNX model loading

## Getting results back to the UI

Use **one** of these — nothing else:

1. **`QThread` + `pyqtSignal`** (preferred for one-shot work with a result):
   ```python
   class _Worker(QThread):
       finished = pyqtSignal(object)
       def run(self):
           self.finished.emit(heavy_work())

   self._worker = _Worker(parent=self)
   self._worker.finished.connect(self._on_result)  # runs on main thread
   self._worker.start()
   ```

2. **`threading.Thread` + `pyqtSignal`** (fire-and-forget, emit signal from thread):
   ```python
   # Widget must define: _items_loaded = pyqtSignal(object)
   threading.Thread(target=lambda: self._items_loaded.emit(fetch()), daemon=True, name="load-items").start()
   ```

3. **EventBus → AppSignals** (app-wide cross-module, see `ui/signals.py`):
   ```
   background thread → event_bus.publish(EVENT_X) → AppSignals.x → widget._on_x()
   ```

## Broken patterns — never use these
- `QTimer.singleShot(0, callback)` from a background thread — timers are thread-local, callback never fires on the main event loop
- Bare `threading.Thread` calling `widget.setText()` or any Qt method directly — undefined behavior / crashes
- `QMetaObject.invokeMethod` from raw threads — fragile, prefer signals

# Svelte 5

- **`{@const}` placement**: Must be a direct child of `{#each}`, `{#if}`, `{:else if}`, `{:else}`, `{#snippet}`, `{:then}`, `{:catch}`, `<svelte:fragment>`, `<svelte:boundary>` or `<Component>`. NEVER place inside `<tr>`, `<div>`, or other HTML elements. Place it right after `{#each ... as item}` before the `<tr>`/`<div>`.
- **`$effect` does NOT run during SSR** — don't rely on it for initial state. For streamed data, initialize state to null and resolve promises in `$effect` on the client.

# UI/Theming

- Always use CSS variables from `nexus/src/lib/style.css` - never hardcode colors
- Ensure proper contrast in light/dark modes (controls, dropdowns, hover states)
- See `docs/ui-styling.md` for patterns (forms, dialogs, notifications, tables, etc.)

# Security

- API endpoints: verify privileges, validate input on both frontend and backend
- When adding, changing, or removing OAuth-accessible API endpoints, update `nexus/src/lib/data/api-docs.md` to keep the user-facing API reference in sync

# Documentation

- Update docs in `/docs` when implementing features; keep in sync
- Document database usage and API endpoints

| File | Description |
|------|-------------|
| `docs/site-overview.md` | Architecture, project structure |
| `docs/ui-styling.md` | CSS variables, component patterns |
| `docs/services.md` | Services marketplace |
| `docs/market.md` | Exchange and shop systems |
| `docs/tools.md` | Loadout calculator |
| `docs/items.md` | Item database |
| `docs/information.md` | Professions, skills, vendors, mobs |
| `docs/maps.md` | Interactive planet maps |
| `docs/missions.md` | Missions system |
| `docs/api.md` | Frontend API reference |
| `docs/search.md` | Search scoring algorithm |
| `docs/skill-scanner.md` | Client OCR skill scanner pipeline |
| `docs/market-price-scanner.md` | Client OCR market price pipeline |
| `docs/capture.md` | Client capture system (clips, recording, screenshots) |

# Versioning

Auto commit changes when substantial work has been done or a fix has been confirmed. Do not commit obvious experiments or debugging attempts (whenever something is incomplete). Be careful to not include any stray script files, passwords or other unwanted files/data.

## Client Release Checklist

Files to update for a version bump:
1. `client/VERSION` — single line with version number (e.g. `0.4.1`)
2. `client/data/changelog.json` — prepend new version entry with date and changes
3. Git tag: `client-X.Y.Z` on the release commit

# Testing

Create/update e2e tests when editing code.

## Timeout Constants (`tests/test-constants.ts`)

| Constant | Value | Use Case |
|----------|-------|----------|
| `TIMEOUT_INSTANT` | 500ms | Client-side only (dialogs, filtering) |
| `TIMEOUT_SHORT` | 1000ms | Client computation (rendering, sorting) |
| `TIMEOUT_MEDIUM` | 3000ms | API calls, page navigation |
| `TIMEOUT_LONG` | 10000ms | Initial loads, auth, large data |
| `TIMEOUT_CACHE` | 60000ms | Exchange cache build on first request |

## Test Users

| ID | Type | Use Case |
|----|------|----------|
| `verified1-3` | Verified | Standard user testing |
| `unverified1-3` | Unverified | Restriction testing |
| `admin` | Admin | Admin functionality |

Use `tests/fixtures/auth.ts` for Playwright: `verifiedUser`, `loginAs('admin')`, etc.

# Responsiveness

Make sites mobile-friendly when creating/reworking. Elements should be accessible, respect network data usage.

# Database Access (Test DBs Only)

Test DB credentials are in the `.env` files. DO NOT modify normal development databases (except test users in nexus-users).
