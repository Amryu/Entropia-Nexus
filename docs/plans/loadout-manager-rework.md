# Loadout Manager Visual Rework + Account Sync Plan

## Goals
- Rework the Loadout Manager UI to match wiki layout/styling (content header, left sidebar, infobox).
- Add a New button in the content header, remove Edit, add a Share button (UI now, behavior later).
- Keep full functional parity for weapon/armor inputs and calculations.
- Add Accessories panel (left/right rings prominent, other clothing, one pet slot).
- Persist loadouts in localStorage for logged-out users and in the DB for logged-in users (with sync).
- Public/private sharing via share link; view-only for other users; allow �Make a copy.�

## References
- Style guidance: `docs/ui-styling.md`, `docs/wiki-components.md`.
- Current loadout page: `nexus/src/routes/tools/loadouts/+page.svelte`.
- Menu link behavior: `nexus/src/lib/components/Menu.svelte`.

## Scope / Non-Goals
- Not changing existing loadout calculations or item selection logic.
- No implementation of Share backend in this pass beyond the UI wiring (Share dialog will be functional, but share link logic will be implemented as part of this plan).

## Phase 1 � UI Layout Migration
1. **Layout baseline**
   - Replace current layout with the wiki layout skeleton:
     - Content header (title + actions).
     - Left sidebar for Loadouts list.
     - Right infobox (no entity image) for computed stats.
     - Center article area for panels.
   - Prefer existing wiki components (`WikiPage`, `WikiNavigation`, `EntityInfobox` or equivalent) over new ones.

2. **Content header actions**
   - Add `New` button and `Share` button to header.
   - Remove any Edit control.
   - Share button opens a dialog (see Phase 3).

3. **Panels**
   - Create panel groupings that mirror wiki style (`DataSection`):
     - **Weapons** (current weapon panel content, styling aligned to wiki panels).
     - **Armor** (current armor set + plates inputs; maintain all existing inputs and behavior).
     - **Accessories** (new):
       - Left ring and right ring prominently placed at the top.
       - Other clothing slots grouped below (necklace, belt, face mask, glasses, etc as available).
       - One pet slot.
   - Ensure all inputs/controls retain existing functionality and validation.

4. **Infobox (stats-only)**
   - Use wiki infobox style but hide the entity image.
   - Display computed stats (DPS, DPP, defense, etc) in a tiered infobox layout consistent with wiki pages.

## Phase 2 � Data Model + Storage
1. **DB migration (nexus-users)**
   - Create new table `loadouts` with:
     - `id UUID PRIMARY KEY`
     - `user_id BIGINT NOT NULL`
     - `name TEXT NOT NULL`
     - `data JSONB NOT NULL`
     - `public BOOLEAN NOT NULL DEFAULT false`
     - `share_code TEXT UNIQUE`
     - `created_at TIMESTAMP NOT NULL DEFAULT now()`
     - `last_update TIMESTAMP NOT NULL DEFAULT now()`
   - Migration file: `sql/nexus-users/migrations/015_loadouts.sql`.
   - Add indexes on `user_id`, `share_code`.

2. **Data size / security**
   - Enforce max JSON payload size of **20KB** in the API (request body length + serialized size).
   - Sanitize JSON payloads:
     - Strip unknown top-level keys.
     - Validate required shape (name, gear, markup) with safe defaults.
     - Normalize strings and clamp numeric ranges where needed.

## Phase 3 � API + Auth
1. **Endpoints** (`/api/tools/loadout`)
   - `GET /api/tools/loadout` ? list current user�s loadouts (summary: id, name, public, share_code, last_update).
   - `POST /api/tools/loadout` ? create new loadout.
   - `GET /api/tools/loadout/[id]` ? fetch one loadout for current user.
   - `PUT /api/tools/loadout/[id]` ? update loadout (debounced autosave target).
   - `DELETE /api/tools/loadout/[id]` ? delete.
   - `GET /api/tools/loadout/share/[share_code]` ? public read-only loadout.
   - `POST /api/tools/loadout/import` ? bulk import local loadouts (for first-time sync).

2. **Authorization**
   - Any authenticated user (including unverified/locked) can create/update/delete their own loadouts.
   - Public share endpoints are read-only.

3. **Limits**
   - Enforce **max 500 loadouts** per user in DB.
   - Local storage remains unlimited.

4. **Share codes**
   - Generate unique short codes (base62 random, 8�12 chars) when `public=true` and share_code is empty.
   - Unset `public` should keep code but treat as private.

## Phase 4 � Client Sync & UX
1. **Load/Save rules**
   - Logged-out: localStorage only (current behavior).
   - Logged-in: load from API; autosave to API with debounce (e.g., 800�1200ms).
   - Show �unsaved changes� indicator and `beforeunload` warning if autosave fails or pending.

2. **Import prompt**
   - When user logs in and DB loadouts count is 0 but localStorage has entries:
     - Show modal prompt: �Import local loadouts into your account?�
     - On accept: call import endpoint (respect 500 limit).
     - On decline: keep local only (no merge).
     - This dialog remains accessible via the Import button (extra Import from local storage (<number of loadouts>) button)

3. **Share dialog (UI now, behavior hooked)**
   - Dialog lets user toggle public/private.
   - If public, show share link and copy button.
   - Share link: `/tools/loadouts/<share_code>`.

4. **Share route**
   - Add route: `nexus/src/routes/tools/loadouts/[share_code]/+page.svelte`.
   - Read-only view using same layout; no edit controls.
   - Add �Make a copy� CTA (creates a new loadout under user or localStorage if logged-out).

## Phase 5 � Tests & QA
- API tests: auth, size limit, 500 limit, share view.
- UI regression: layout matches wiki style, mobile behavior, no header navigation on mobile menu.
- Sync flows: import prompt, autosave, share link view-only behavior.

## Deliverables Checklist
- `docs/plans/loadout-manager-rework.md` (this plan).
- UI refactor in `nexus/src/routes/tools/loadouts/+page.svelte` plus new components if needed.
- New migration in `sql/nexus-users/migrations/015_loadouts.sql`.
- API endpoints under `nexus/src/routes/api/tools/loadout/*`.
- New share route `nexus/src/routes/tools/loadouts/[share_code]/+page.svelte`.
- Client sync logic + import dialog.

## Open Questions
- Confirm list of accessory slots (besides left/right ring and pet) to include.
  - Answer: can be any clothing piece. User can choose 1 item per "Slot"
- Preferred autosave debounce duration and whether manual Save should also exist.
  - Answer: 10s, yes keep manual save button (the button visualizes the save with a countdown)
- Whether to preserve existing localStorage data after successful import.
  - Answer: After successful import no. In the side-bar make a toggle to switch between Local and Online view. Defaults to Online for logged in users. For logged out users "Online" is grayed out and they are locked to local. Add a tooltip over "Online" to tell them they need to log in to use this.
