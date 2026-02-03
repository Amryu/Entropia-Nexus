# Share Loadout Read-Only Parity Plan

## Goal
Bring the share page (`/tools/loadouts/[share_code]`) up to parity with the main loadout page (`/tools/loadouts`) while remaining read‑only. The share view should reuse the same layout, visuals, and display components so it feels like the main page with inputs removed.

## Current State (Research Notes)
### Share Page
- **File:** `nexus/src/routes/tools/loadouts/[share_code]/+page.svelte`
- **Styles:** `nexus/src/routes/tools/loadouts/[share_code]/share.css` + `nexus/src/routes/tools/loadouts/loadouts.css`
- **Layout:**
  - Custom sidebar + top action button (copy) with unique styling.
  - Infobox uses bespoke “Loadout Stats” layout (different from main loadouts panel).
  - Main content uses `DataSection` with plain key/value grids.
  - Missing mobile panel structure and many of the main page UI affordances.
- **Behavior:**
  - Read‑only by virtue of being a separate template, not shared components.
  - Uses same evaluation pipeline as main page (`evaluateLoadout`, entity loading).

### Main Loadout Page
- **File:** `nexus/src/routes/tools/loadouts/+page.svelte`
- **Styles:** `nexus/src/routes/tools/loadouts/loadouts.css` (large shared UI system)
- **Layout:**
  - Sidebar with search, source switching, list, buttons.
  - Floating infobox card with tier‑1 stats and effects panels.
  - Main content panels for weapons, armor, accessories, settings, etc.
  - Mobile panel slider with toolbar.
  - Compare mode and picker dialogs.
- **Components used heavily:** `DataSection`, `FancyTable`, `EffectsEditor`

## Gaps to Close
1. **Sidebar and header styling:** Share sidebar + header action button don’t match loadout UI system.
2. **Infobox stats layout:** Share page uses a different stats hierarchy and styling.
3. **Content sections:** Share page uses ad‑hoc “details” grid instead of the main display panels.
4. **Mobile layout:** Share view lacks the mobile panel layout/controls.
5. **Consistent read‑only rendering:** Share page should be the same structural markup as main loadouts, but with inputs replaced by formatted display.

## Reuse/Extraction Opportunities
### Reuse (without extraction)
- **CSS:** Reuse classes from `loadouts.css` wherever possible.
- **Markup:** Copy/align sections from main page, removing inputs and event handlers.

### Potential Shared Helpers/Components
- **Read‑only “display panels”:**
  - Stats section markup (tier‑1 + secondary stats) from main page.
  - Equipment grids (weapons/armor/accessories) from main page, but non‑editable.
- **Sidebar block** (read‑only version):
  - Title, meta, back link, and copy actions styled with existing sidebar classes.
- **Content header**: replicate main page header action styling for “Make a copy”.

## Proposed Implementation Approach
1. **Align layout structure**
   - In share page, swap current structure to match main page layout:
     - Use `.loadout-sidebar` and `.loadout-header-actions` classes (with read‑only content).
     - Use `.loadout-infobox-card` layout for stats.
     - Use same `.loadout-article` panel structure as main page.
2. **Replace input UI with display UI**
   - Replace info grids with the main page display components:
     - Read‑only stats panels using existing `.stats-section` markup.
     - Equipment panels reusing the same markup as the main page (no buttons/inputs).
3. **Unify CSS**
   - Move/merge share page styles into `loadouts.css` where possible.
   - Remove `share.css` where duplicated (or limit it to share‑only tweaks).
4. **Mobile parity**
   - Use the same mobile panel/toolbar layout as main page (without interactive controls).
   - Ensure loadout stats and panels are shown via mobile panel structure.
5. **Read‑only safeguards**
   - Strip input handlers, autosave, compare mode, and picker dialogs.
   - For actions: allow only “Make a copy” and “Back to loadouts”.

## Target Files / Touch Points
- `nexus/src/routes/tools/loadouts/[share_code]/+page.svelte`
- `nexus/src/routes/tools/loadouts/[share_code]/share.css` (likely to shrink or remove)
- `nexus/src/routes/tools/loadouts/loadouts.css`
- Potential new shared components under `nexus/src/lib/components/` if needed

## Risks / Considerations
- **Duplication risk:** Copying main page markup may cause drift. Prefer shared components or refactor shared blocks.
- **Mobile behavior:** Share page doesn’t need editing, but should respect the same responsive panel layout.
- **Data shape parity:** Ensure share page uses the same derived stats and formatting helpers used in main page.

## Next Steps (Implementation Tasks)
1. Port main loadout header + sidebar structure into share page.
2. Replace share infobox with main loadout infobox markup (read‑only).
3. Replace detail grids with main page equipment panels (display only).
4. Fold share styles into `loadouts.css` and remove redundant share styles.
5. Add mobile panel layout for share (no compare/edit).
6. Visual review on desktop + mobile breakpoints.
