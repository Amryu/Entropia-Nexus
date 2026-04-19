# General

- Prefer existing components before creating new; make new controls discoverable
- Write notes in /claude for big tasks
- Playwright testing: dev.entropianexus.com (API: 3000, Frontend: 3001)
- Avoid magic numbers — use constants
- Question approach, estimate success. <80% certain? Ask, not guess.
- After implementing, hunt further fixes/optimizations — consistency, redundancy, security
- After feature add, consolidate code, cut line count (not by complicating lines)
- Never use `nexusPool` in frontend except per comment next to it

# Database

- `/sql/<db>/dumps`: structure dumps (maybe outdated)
- `/sql/<db>/migrations`: dev changes — check for missing tables
- Create migration files for schema changes, never modify directly
- Local/test DBs NOT synced with prod — don't trust MCP results for prod data
- Prod data lives in `_prod`-suffixed MCP tools (`mcp__postgres-nexus-prod__query`, `mcp__postgres-nexus-users-prod__query`). Non-suffixed `mcp__postgres-nexus__query` / `mcp__postgres-nexus-users__query` point at local dev.
- Migrations = schema source of truth

# Client Config (`client/core/config.py`)

- `AppConfig` is `@dataclass` — add new fields with defaults directly (e.g. `field_name: type = default`)
- **CRITICAL**: New fields must go in `DEFAULTS` dict (~line 311). `save_config` iterates `DEFAULTS`, not dataclass fields — missing entries not persisted.
- **Tuple fields** (positions, ROIs) stored as JSON arrays. Add field name to list-to-tuple conversion loop (~line 620) for load-back conversion.
- **Migrations**: Remove/rename old fields via `merged.pop("old_key", None)` before `AppConfig()` constructor (see existing migrations ~line 540+).
- Save with `save_config(config, config_path)` + `event_bus.publish(EVENT_CONFIG_CHANGED, config)`.

# Guidelines

- Read project-specific `guidelines.md` before work
- Never use `alert()` — use notifications/dialogs
- Ensure consistency: headers, breadcrumbs, back nav (buttons, not links)
- URL shortening upkeep required: new public/pseudo-page route added/changed? Update `nexus/src/lib/server/short-url.js` mappings, keep `nexus/scripts/verify-short-route-coverage.mjs` passing.

# Client Threading (PyQt6)

Full patterns in `client/guidelines.md` §1–2. Key rules:

## What blocks the main thread (FreezeDetector triggers at 0.5s)
- HoughCircles / image processing, network calls, file I/O, database bulk ops, ONNX model loading

## Getting results back to the UI

Use **one** — nothing else:

1. **`QThread` + `pyqtSignal`** (preferred for one-shot work with result):
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

## Broken patterns — never use
- `QTimer.singleShot(0, callback)` from background thread — timers thread-local, callback never fires on main loop
- Bare `threading.Thread` calling `widget.setText()` or any Qt method directly — undefined behavior / crashes
- `QMetaObject.invokeMethod` from raw threads — fragile, prefer signals

# Svelte 5

- **`{@const}` placement**: Must be direct child of `{#each}`, `{#if}`, `{:else if}`, `{:else}`, `{#snippet}`, `{:then}`, `{:catch}`, `<svelte:fragment>`, `<svelte:boundary>` or `<Component>`. NEVER inside `<tr>`, `<div>`, other HTML elements. Place right after `{#each ... as item}` before `<tr>`/`<div>`.
- **`$effect` does NOT run during SSR** — don't rely for initial state. Streamed data: init state to null, resolve promises in `$effect` on client.
- **Use `SvelteMap` / `SvelteSet` / `SvelteDate` / `SvelteURL`** from `svelte/reactivity` when you need reactive Map/Set/Date/URL that's *mutated* (`.set`, `.add`, `.delete`, `.clear`). Plain `Map`/`Set` wrapped in `$state(...)` do NOT re-render on mutation — must reassign new instance each time. Use plain collections in `$state` only if always replacing wholesale (never call mutation methods).
- **Capturing props in `$state(...)` initializers** triggers `state_referenced_locally` warnings — Svelte can't tell live binding vs one-time snapshot. Snapshot intended? Wrap initializer in `untrack(() => ...)` from `svelte` to document intent, silence warning.

# UI/Theming

- Always use CSS variables from `nexus/src/lib/style.css` — never hardcode colors
- Ensure contrast in light/dark modes (controls, dropdowns, hover states)
- See `docs/ui-styling.md` for patterns (forms, dialogs, notifications, tables, etc.)

# Security

- API endpoints: verify privileges, validate input both frontend/backend
- Adding/changing/removing OAuth-accessible API endpoints? Update `nexus/src/lib/data/api-docs.md` to sync user-facing API reference

# Documentation

- Update docs in `/docs` when implementing features; keep synced
- Document database usage, API endpoints

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

Auto commit when substantial work done or fix confirmed. Skip obvious experiments/debug attempts (anything incomplete). Avoid stray scripts, passwords, unwanted files/data.

## Client Release Checklist

Files for version bump:
1. `client/VERSION` — single line with version number (e.g. `0.4.1`)
2. `client/data/changelog.json` — prepend new version entry with date, changes
3. Git tag: `client-X.Y.Z` on release commit

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

Make sites mobile-friendly on create/rework. Elements accessible, respect network data usage.

# Database Access (Test DBs Only)

Test DB credentials in `.env` files. DO NOT modify normal dev databases (except test users in nexus-users).