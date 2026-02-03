# Loadouts: Comparison Rework (FancyTable)

## Goals
- Replace the current comparison table with `FancyTable`.
- Provide:
  - per-column filtering + sorting
  - global name search
  - ability to hide/unhide specific loadout rows
  - value mode vs delta mode (anchor = currently selected loadout)
  - weapon compare vs armor compare
- Desktop-only configurability of which compare metrics (columns) are shown, persisted in localStorage.
- Mobile:
  - very compact, minimal columns
  - keep layout reactive and avoid heavy scrolling
- UX:
  - clicking a row activates that loadout
  - when the compare overview is visible, hide the mobile carousel overview strip
  - do not auto-switch the active mobile panel to "weapons" when entering compare

## Current State
- Compare is currently rendered in `nexus/src/routes/tools/loadouts/+page.svelte` using the legacy `Table` component.
- Core stats now come from `evaluateLoadout()` in `nexus/src/lib/utils/loadoutEvaluator.js`.

## Design / UX
### Entry + layout
- Keep the existing Compare button in the content-header.
- Compare view becomes a dedicated "Compare" panel/overlay in the main content area.
  - Desktop: show as a full-width section in the article area (no carousel interaction).
  - Mobile: show as a full-screen section within the article area; hide the carousel overview strip while open.

### Compare mode selector
- Add a toggle: `Weapons` | `Armor`.
- Add a display toggle: `Values` | `Delta`.
  - Delta anchor = the currently selected loadout.
  - If no loadout is selected, delta mode is disabled or falls back to values mode.

### Row hide/unhide
- Each row gets a "visibility" control (icon button) to hide/unhide.
- Hidden rows are excluded from the table by default.
- Provide a compact "Hidden loadouts" affordance:
  - a small pill/button (e.g. "Hidden (3)") opening a popover/list to re-enable.
  - Alternatively: a checkbox "Show hidden" that reveals them with a muted style.
- Persist hidden state in-memory only for now (optional follow-up: localStorage).

### Desktop: configurable shown metrics (columns)
- Compare is row-oriented (each row = loadout), so "shown rows" maps to "shown metrics/columns".
- Add a compact "Columns" control (desktop only) that opens a small popover panel:
  - checkbox list for available columns per compare type (Weapons / Armor)
  - Reset action to restore defaults
- Persist selection in localStorage so the user's preferred compare view is remembered.
  - Keys:
    - `nexus.loadouts.compare.columns.weapons`
    - `nexus.loadouts.compare.columns.armor`
  - Value: JSON array of column keys, e.g. `["Name","DPS","DPP","Efficiency"]`.

### Cell content not cut off
- FancyTable uses fixed row heights (virtualized), so cells cannot freely wrap without breaking virtualization.
- Ensure content is readable without truncation artifacts:
  - Make the Name column `main: true` so it gets the most horizontal space.
  - Add `title=` tooltips for truncated text cells (Name + any text columns).
  - For very narrow viewports (mobile), show only the Name column in addition to the minimal stats columns (already required).
  - Avoid layout bugs where the last column is hidden by the scrollbar (verify with FancyTable scrollbar padding).

### Clicking rows
- `FancyTable` emits `rowClick`; clicking a row sets that loadout as active.
- Option: keep compare open (default) so the user can click multiple rows quickly.

## Data / Computation Model
### Inputs
- `loadouts`: list of loadout objects (local or online).
- `activeLoadoutKey` / active selected loadout object (anchor).
- Entities + effects catalog already loaded in the route:
  - entities tables (weapons, armor, etc.)
  - `effectsCatalog` + `effectCaps`

### Caching
- `evaluateLoadout()` is relatively expensive; avoid recomputing on every render.
- Maintain a map: `evaluationByLoadoutId: Map<string, { stats, effects, offensiveTotals }>`
  - Key = `loadout.Id` for local loadouts; for online use the same `data.Id` (already normalized).
  - Recompute when:
    - entitiesVersion changes
    - effectsCatalog/effectCaps changes
    - loadoutVersion changes (or the specific loadout object changes)
- Build table rows from cached evaluations.

### Delta calculations
- Delta values are derived from numeric stats:
  - `delta = value - anchorValue`
- Columns must declare `higherIsBetter` so delta coloring makes sense:
  - Weapons:
    - DPS: higher is better
    - DPP: higher is better
    - Efficiency: higher is better
    - Reload: lower is better
    - Cost/Decay/Ammo: lower is better
  - Armor:
    - Total Defense: higher is better
    - Total Absorption: higher is better
    - Block: higher is better
- UI formatting:
  - store underlying cell values as numbers for correct sorting
  - use column `formatter` to display units and +/- in delta mode

## Columns
### Weapons (desktop)
- Name (loadout name; sticky)
- DPS
- DPP
- Efficiency
- Reload (s)
- Total Damage
- Effective Damage
- Range (m)
- Cost (PEC)
- Decay (PEC)
- Ammo (shots/PEC; whatever the current units are in the stats)

### Armor (desktop)
- Name
- Total Defense
- Defense Types (short): top defenses ordered by value (e.g. "Imp/Cut/Shr")
- Total Absorption (HP)
- Block (%)

### Mobile column sets
- Weapons mobile: Name, Efficiency, DPS, DPP (everything else `hideOnMobile: true`)
- Armor mobile: Name, Total Defense, Defense Types (short)
  - Defense Types should be very compact (3-letter abbreviations), already ordered.

## Required Enhancements to Evaluator
### Armor defense type breakdown
- `loadoutEvaluator.js` currently returns totals only.
- Add an optional `armorDefenseByType` (and/or a `topDefenseTypes` preformatted string) to `stats`:
  - sum defense types across equipped armor pieces + plates
  - apply defense enhancer scaling consistently with existing total defense logic
  - output:
    - `stats.defenseByType: { Impact, Cut, Stab, Penetration, Shrapnel, Burn, Cold, Acid, Electric }`
    - `stats.topDefenseTypesShort: string` (e.g. "Imp/Cut/Shr")

## FancyTable Integration Notes
- Use `FancyTable` features:
  - `searchable` for global filtering by loadout name
  - filter row for per-column filters (already supported)
  - sorting by column
  - `hideOnMobile` for column suppression
  - `rowClick` to activate a loadout
- Provide `rowHeight` smaller in compare view (mobile even smaller).

## Implementation Steps
1. UI skeleton
   - Replace the current `Table` compare section with a `FancyTable` compare view.
   - Add toggles: compare type (Weapons/Armor), display (Values/Delta), hidden rows control.
   - Add desktop-only "Columns" popover and load/save column selection to localStorage.
2. Row model + cache
   - Add cached evaluations for all loadouts.
   - Build row objects for each compare type.
3. Delta mode
   - Anchor = selected loadout evaluation.
   - Implement formatter + coloring based on `higherIsBetter`.
4. Row hide/unhide
   - Add a first column "visibility" icon button and implement hidden set tracking.
5. Mobile behavior
   - hide carousel overview strip when compare view is open
   - keep current active mobile panel (do not auto-switch to weapons)
   - ensure columns collapse to the minimal set and row height is reduced
6. Armor defense types
   - Extend `loadoutEvaluator.js` stats to include defense-by-type breakdown and a short string for the table.

## Tests / QA
- Manual:
  - Values vs Delta produces correct numbers (anchor = selected loadout).
  - Sorting works numerically (not lexicographically).
  - Column filters work (including operators).
  - Hide/unhide rows works and persists while compare view is open.
  - Row click sets active loadout.
  - Mobile shows only the required columns and remains compact; carousel overview strip is hidden in compare view.
- Automated (follow-up):
  - Add/extend Playwright tests around:
    - compare view opens
    - row click activates loadout
    - mobile column visibility (weapons vs armor)
    - delta mode toggle
