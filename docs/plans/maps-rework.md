# Maps Rework Plan (Google Maps‑style UX)

## Goals
- Replace the current map UI with a map‑first layout (no wiki page scaffolding).
- Provide Google Maps‑style exploration: pan/zoom, fast search, and a focused detail panel.
- Support selection via URL slug and immediate zoom/center on load.
- Keep data driven by existing API endpoints while cleaning up filtering/search behavior.

## Current Implementation Summary
- **Route:** `nexus/src/routes/maps/[[planet]]/[[slug]]/+page.svelte`
  - Layout: three columns (`MapList` left, `Map` center, `Properties` right).
  - Uses `MapList.svelte` for filters/search and list; `Map.svelte` for canvas render; `Properties` for details.
- **Data load:** `+page.js` calls:
  - `GET /locations?Planet={planet}`
  - `GET /areas?Planet={planet}`
  - `GET /mobspawns?Planet={planet}`
  - Merges into a single `locations` array (prefers MobSpawn > Area > Location on Id collisions).
- **Map rendering:** `Map.svelte` canvas, custom zoom/pan, draw shapes by `Properties.Shape`.
- **Filters/search:** `MapList.svelte` + `mapUtil.locationFilter` (string includes, no fuzzy search).
- **Planet/subarea mapping:** `MapList.svelte` contains `planetList` (main planets + sub areas).

## Relevant API Shapes (current)
- **Locations** (`/locations`)
  - `{ Id, Name, Properties: { Description, Type, Coordinates }, Planet }`
- **Areas** (`/areas`)
  - `{ Id, Name, Properties: { Description, Type, Shape, Data, Coordinates }, Planet }`
- **MobSpawns** (`/mobspawns`)
  - `{ Id, Name, Properties: { Description, Type: 'MobArea', Shape, Data, Coordinates, Density, IsShared, IsEvent, Notes }, Planet, Maturities[] }`

## Target UX / IA
- Full‑bleed map canvas with floating controls in the **top‑left** (Google Maps style).
- Controls stack:
  1) **Planet select** (main planets only: Calypso, Arkadia, Cyrene, Rocktropia, Next Island, Toulan, Monria, Space).
  2) **Area select** (selected planet + its sub‑areas; driven by existing `planetList` mapping).
  3) **Search bar** (fuzzy search across locations/areas/estates).
- Right‑side **hover panel** (infobox‑style) appears when:
  - A point/area is clicked.
  - A search result is selected.
  - A slug is present in the URL.
  - Basically when any point of interest on the map is currently selected
- Default visibility:
  - **Visible:** Teleporters + regular areas + PvP zones.
  - **Hidden by default:** Mob areas and Land Areas.
  - **Visible by default:** PvP areas (PvpArea + PvpLootArea).

## Detail Panel Content (Infobox‑style)
- Image (similar to EntityImage, show placeholder if none)
- Name
- Type
- Location (copyable waypoint)
- Top 3 closest teleporters (distance in meters using in‑game coordinates)
- Description
- Type‑specific sections (examples):
  - **MobArea:** density, shared/event flags, top maturities summary
  - **LandArea:** owner/estate info (if available)
  - **Zone/PvP:** zone type, lootable indicator
  - **Teleporters:** neighboring teleporters list (same as “closest”)

## Editing + Create Workflow (Verified Users Only)
- **Detail panel edit button:** small edit button in the panel header (match wiki style).
- **Inline edits:** use `InlineEdit` for name, type, description, and other fields in edit mode.
- **Image upload:** allow clicking the image or placeholder to upload during edit mode (reuse wiki upload behavior).
- **Create button:** small green + next to the search bar.
  - Navigates to `?mode=create`.
  - After first save, append `changeId` for the draft (create change flow).
- **Auth gating:** show edit/create UI only if user is logged in and verified; otherwise hide.

## Pending Changes Dialog (Verified Users Only)
- If the user has **any** active draft/review changes (create or update), show a button next to +.
- Button opens a dialog listing all active change entities.
- Clicking an entry:
  - Closes dialog.
  - Selects the entity on the map.
  - If **create** change: navigate to `?mode=create&changeId=<id>`.
  - If **update** change: navigate to slug and focus it.
- Dialog requirements:
  - Top right X close button in the header.
  - Follow existing dialog styling and button guidelines.
  - Include basic metadata (type + state).

## Fuzzy Search
- Replace `mapUtil.locationFilter` string includes with fuzzy scoring.
- Reuse existing fuzzy logic from `WikiNavigation` (or extract to shared utility).
- Rank results by score, prefer exact/starts‑with, then substring, then fuzzy.

## URL + Focus Behavior
- If `/:slug` exists:
  - Find matching location by Id or normalized name.
  - Center and zoom to a reasonable level so surroundings are visible.
  - Show detail panel immediately.
- Adjust zoom caps and animation speeds for smoother feel (slower zoom, faster pan).

## Implementation Plan
1) **Create shared map config + helpers**
   - Move `planetList` mapping into `$lib/mapUtil` (or new `$lib/mapData`) for reuse.
   - Add helper to normalize slugs, compute distances, and format meters.

2) **Rework map route layout**
   - Replace the 3‑column layout with:
     - Full‑bleed map canvas.
     - Floating controls top‑left.
     - Right‑side info panel (infobox styled).
   - Remove `Properties` component from map page.

3) **New Map Controls component**
   - Planet select (main planets only).
   - Sub‑area select (based on selected planet’s subareas).
   - Fuzzy search input with results list (popover or drop‑down).
   - Optional toggles for visibility categories (teleporters, areas, pvp, land, mobs).

4) **Map rendering updates**
   - Keep current canvas rendering, but add:
     - Programmatic focus/zoom method.
     - Highlight selected item distinctly.
     - Slightly slower zoom transitions and capped zoom range.

5) **Selection + focus pipeline**
   - Centralize selection state in the map route.
   - On selection:
     - Update URL (without full reload).
     - Center/zoom map to target.
     - Populate info panel.

6) **Distance to closest teleporters**
   - Filter teleporters within the same planet dataset.
   - Compute Euclidean distance using coordinates (x,y meters).
   - Sort, show top 3 with distance + link to focus.

7) **Search + filtering integration**
   - Search results list should include:
     - Name, Type badge, optional distance from current center.
     - Clicking a result focuses the map and opens info panel.
   - Default filters: teleporters + regular areas + PvP zones enabled.

8) **Style alignment**
   - Use wiki infobox patterns for the right panel (colors, typography, sectioning).
   - Controls panel styling to match site (background, borders, shadows).

## Non‑Goals
- No wiki layout or wiki sidebar usage.
- No repeating map tiles (single static map image).

## Notes / Risks
- Large location lists: fuzzy search should be optimized (precompute normalized names and/or cache scores).
- Ensure selection changes do not trigger full page reloads (use SvelteKit navigation).
- Adhere to the style guides and use info box like styling to the details panel
