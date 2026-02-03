# Loadout Calculations Reuse / Dedup Plan

## Goal
- Ensure the loadout manager (and share route) use `$lib/utils/loadoutCalculations.js` as the single source of truth for numeric/stat calculations.
- Move "loadout evaluation" (effects aggregation, cap enforcement, cancellation rules) out of the Svelte routes into reusable utils.
- Keep the Svelte routes focused on UI state + wrapper code (resolving entities, wiring inputs, formatting).

## Current State (as of 2026-02-03)
- `nexus/src/lib/utils/loadoutCalculations.js` is already used for many core computations in:
  - `nexus/src/routes/tools/loadouts/+page.svelte`
  - `nexus/src/routes/tools/loadouts/[share_code]/+page.svelte`
  - `nexus/src/lib/components/services/serviceCalculations.js`
- However, `nexus/src/routes/tools/loadouts/+page.svelte` still contains substantial duplicated / bespoke logic:
  - "Picker preview" stats (DPS/DPP/cost/uses) computed ad-hoc from item properties.
  - Effects aggregation + caps + cancellation rules for "Active Effects" (needs reuse and consistency with calculations).
  - Various helper calculations (markup cost, etc.) that are not centralized.

## Principles / Boundaries
- `loadoutCalculations.js` stays "pure": no Svelte stores, no DOM, no fetch. All inputs are passed in.
- Page code should not implement formulas (only:
  - resolve entities from the loaded tables
  - pass the correct arguments
  - format numbers/labels
  - mutate loadout state and call save/touch helpers)
- Effects capping must be enforced consistently in BOTH:
  - displayed "Active Effects"
  - derived combat stats (damage/reload/crit chance/crit damage, etc.)

## Phase 1: Inventory + Contract Definition
1. Identify all computation hotspots in:
   - `nexus/src/routes/tools/loadouts/+page.svelte`
   - `nexus/src/routes/tools/loadouts/[share_code]/+page.svelte`
   - any other consumers that derive stats from gear/effects
2. For each hotspot, define the desired function contract (inputs/outputs) that can live in utils.

Deliverable:
- A short mapping list in this plan (or a follow-up PR note) of "route function -> util function".

## Phase 2: Extract "Item Preview" Calculations into loadoutCalculations.js
Move the ad-hoc picker preview helpers from `nexus/src/routes/tools/loadouts/+page.svelte` into `nexus/src/lib/utils/loadoutCalculations.js` as reusable functions, for example:
- `calculateItemTotalDamage(item)`
- `calculateItemReloadSeconds(item)`
- `calculateItemCostPerUse(item)`
- `calculateItemEffectiveDamagePreview(item, { hitAbility, critChance, critDamage })`
- `calculateItemDpsPreview(item, opts)`
- `calculateItemDppPreview(item, opts)`
- `calculateItemTotalUses(item)`
- `calculateAbsorberTotalUses(absorber, weapon)`

Notes:
- Keep defaults matching current UI behavior (the preview uses simplified assumptions).
- Keep these functions tolerant of missing properties (return `null` where current code does).

## Phase 3: Create Shared "Effects" Utility (Caps + Cancellation)
Create a new utility module for effect aggregation/capping that is NOT Svelte-specific:
- Suggested file: `nexus/src/lib/utils/loadoutEffects.js`

Responsibilities:
1. Normalize/collapse effects that cancel each other out:
   - Contradicting prefixes:
     - multiplicative: `Increased` vs `Decreased`
     - additive: `Added` vs `Reduced`
   - Rule: if both exist for the same base effect, only the higher-magnitude one survives and its sign is kept.
2. Apply limits from effects metadata:
   - `Limits.Item` caps equipable sources (weapon/armor/sets/clothing/etc.)
   - `Limits.Action` caps pets + consumables
   - Bonus stats are an exception: they ignore item/action caps but still respect `Limits.Total`
   - "Negative or null caps" are treated as no cap
3. Produce a display-ready model for the UI (but not actual UI):
   - `valueTotal` (after all caps)
   - `valueItemRaw`, `valueItemCapped`
   - `valueActionRaw`, `valueActionCapped`
   - `valueBonusRaw`
   - `isPositive` from `effect.Properties.IsPositive` (do not infer from name)
   - `isCapped` + `isOverCapped` flags for item/action/total

Suggested core functions:
- `buildEffectIndex(effects)` -> map by id and optionally by name
- `aggregateLoadoutEffects(contributions, effectIndex, options)` -> aggregated + capped totals
- `cancelContradictingEffects(effects)` -> normalized list (prefix cancellation)

Inputs:
- "Contributions" should be explicit (no implicit loadout traversal inside this module):
  - `{ effectId, strength, source: 'item' | 'action' | 'bonus', meta?: {...} }`

## Phase 4: Create "Loadout Evaluation" Wrapper Using loadoutCalculations.js
Create a single reusable evaluator that:
- walks the loadout structure
- resolves item entities (weapon/attachments/armor/plates/clothing/pet/consumables)
- produces:
  - computed combat stats (DPS/DPP/etc.) using `loadoutCalculations.js`
  - active effects list using `loadoutEffects.js`
  - the "configured" combat stats derived from the capped effects totals

Suggested file:
- `nexus/src/lib/utils/loadoutEvaluator.js`

Key API:
- `evaluateLoadout(loadout, resolvedEntities, effectIndex, options)` -> `{ stats, activeEffects, groupedEffects, warnings }`

`evaluateLoadout` should be the one place that decides:
- what counts as "item" vs "action"
- how to combine equipment/pet/consumable/bonus contributions
- how to pass the final capped totals into `loadoutCalculations.js` calls (bonusDamagePercent, bonusReloadPercent, etc.)

## Phase 5: Refactor Routes to Use the Evaluator
1. `nexus/src/routes/tools/loadouts/+page.svelte`
   - Replace local effect aggregation and preview calculations with calls to:
     - `evaluateLoadout(...)`
     - `LoadoutCalc.*` preview helpers (Phase 2)
   - Keep only wrapper functions:
     - resolving entities from already-loaded tables
     - routing mutations to `touchLoadouts()` / `markDirty()`
     - formatting for display
2. `nexus/src/routes/tools/loadouts/[share_code]/+page.svelte`
   - Use the same evaluator so that "view-only" stats match the main page.

## Phase 6: Adopt Everywhere Else (Optional, But Recommended)
- Audit `nexus/src/lib/components/services/serviceCalculations.js` and `nexus/src/routes/market/services/[[slug]]/+page.svelte`
  - Ensure they use the same evaluator if they display "Active Effects" or need cap enforcement.
  - If they only need raw weapon/armor formulas, keep them on `loadoutCalculations.js` only.

## Tests / Validation
Add unit tests for `loadoutEffects.js` and `loadoutEvaluator.js`:
- Caps:
  - item/action/total caps apply correctly
  - negative/null caps are treated as uncapped
  - bonus ignores item/action but respects total
- Cancellation:
  - Increased vs Decreased chooses the higher magnitude and keeps correct sign
  - Added vs Reduced behaves similarly
- Display model:
  - `IsPositive` drives green/red for the value (not the prefix)
  - Expanded breakdown shows denominators with the correct sign (e.g. negative effects show `.../-25%`)

Manual validation checklist:
- Load an existing loadout and verify no stat changes vs current behavior.
- Overcap indicators appear and expanded breakdown values match the rules.
- Share route stats/effects match main route.

## Rollout / Risk Management
- Do extraction in small steps:
  1) item preview helpers
  2) effect aggregator util
  3) evaluator
  4) route refactor
- Keep a temporary compatibility layer during the refactor:
  - old computed values can be logged side-by-side for a short period to confirm parity.

## Done When
- `nexus/src/routes/tools/loadouts/+page.svelte` contains no formulas for:
  - item preview stats
  - active effect aggregation/cancellation/capping
  - derived combat bonus application
- Both `/tools/loadouts` and `/tools/loadouts/[share_code]` obtain their computed stats and active effects from the shared utils.
- `loadoutCalculations.js` (and related utils) are used consistently and route code is primarily glue/UI.

