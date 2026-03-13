# Svelte 5 Legacy Cleanup Plan

The codebase was auto-migrated from Svelte 4 to Svelte 5 with compatibility mode. The migration tool wrapped old reactive patterns in `run()` from `svelte/legacy` and kept `createEventDispatcher` + `on:event` syntax. All of these need converting to native Svelte 5 patterns.

## Current State

| Category | Occurrences | Files | Status |
|---|---|---|---|
| `run()` from `svelte/legacy` | ~302 | 96 | **DONE** — all converted to `$effect()` |
| `createEventDispatcher` | ~146 | 64 | **DONE** — all converted to callback props |
| `on:event` on components | ~46 | 15+ | **DONE** — all converted to `onevent={handler}` (2 remain on third-party `svelte-easy-crop`) |
| `svelte/legacy` event modifiers | ~217 | 62 | **DONE** — `createBubbler`, `stopPropagation`, `self`, `preventDefault` all inlined |
| `svelte/legacy` imports | — | 0 | **DONE** — zero imports remain |
| `$$slots` / `<slot>` / `afterUpdate` | 0 | 0 | Already done |

## Conversion Patterns

### `run()` → `$effect()` / `$derived()`

**Self-referencing blocks** (read + write same `$state`) cause `legacy_recursive_reactive_block` warnings. Fix with `untrack()`:

```svelte
// Before (causes warning)
run(() => {
  if (someReactive && someReactive !== lastValue) {
    lastValue = someReactive;
    doSomething();
  }
});

// After
$effect(() => {
  if (someReactive && someReactive !== untrack(() => lastValue)) {
    lastValue = someReactive;
    doSomething();
  }
});
```

**Pure computations** should use `$derived()` instead of `$effect()`:

```svelte
// Before
let doubled;
run(() => { doubled = count * 2; });

// After
let doubled = $derived(count * 2);
```

### `createEventDispatcher` → Callback Props

```svelte
// Before (child)
import { createEventDispatcher } from 'svelte';
const dispatch = createEventDispatcher();
dispatch('select', item);

// After (child)
let { onselect } = $props();
onselect?.(item);

// Before (parent)
<Child on:select={handler} />

// After (parent) — handler receives data directly, NOT event.detail
<Child onselect={handler} />
```

### `on:event` on Components → Callback Props

Same pattern as above. Every `on:x={handler}` on a component tag becomes `onx={handler}`. The handler signature changes: data comes as direct argument, not `event.detail`.

## Phase 1 — Core Shared Components

These are used everywhere. Migrate first to establish patterns and reduce cascading changes later.

**Target files (12):**

| File | `run()` | `dispatch` | Notes |
|---|---|---|---|
| `lib/components/Table.svelte` | 3 | yes | Used by dozens of pages |
| `lib/components/FancyTable.svelte` | 3 | yes | Wiki sidebar tables |
| `lib/components/BrowseList.svelte` | 2 | yes | Entity browse pages |
| `lib/components/NavList.svelte` | 2 | yes | Navigation lists |
| `lib/components/SearchInput.svelte` | 1 | — | Search across site |
| `lib/components/wiki/SearchInput.svelte` | 2 | yes | Wiki search |
| `lib/components/EditForm.svelte` | 3 | yes | Wiki edit forms |
| `lib/components/EditFormControlGroup.svelte` | 1 | yes | Form field groups |
| `lib/components/EntityViewer.svelte` | 1 | — | Entity display |
| `lib/components/VirtualTableRow.svelte` | 6 | yes | Virtual scroll rows |
| `lib/components/TurnstileWidget.svelte` | 1 | — | Auth widget |
| `lib/components/RangeSlider.svelte` | — | yes | Slider input |

**Verification:** After each component, run `npm run build` and check that all pages using the component still function. Run relevant Playwright tests.

## Phase 2 — Wiki Entity Pages (~25 pages)

Nearly all wiki entity pages share the same `run()` patterns:
1. **editDepsLoading** — lazy-load edit deps (self-referencing)
2. **lastInitKey** — init edit state on entity change (self-referencing)
3. **pendingChange init** — set store from derived (no self-ref, simple `$effect`)
4. **previousEntityId** — exit edit mode on navigation (self-referencing)
5. **Smart inference** — auto-select fields when options narrow (self-referencing, weapons/tools only)

**Already fixed:** `weapons/[[slug]]/+page.svelte` (template for others)

**Remaining (pattern identical to weapons):**

| File | `run()` |
|---|---|
| `items/vehicles/[[slug]]/+page.svelte` | 3 |
| `items/tools/[[type]]/[[slug]]/+page.svelte` | 5 |
| `items/strongboxes/[[slug]]/+page.svelte` | 3 |
| `items/pets/[[slug]]/+page.svelte` | 3 |
| `items/medicaltools/[[type]]/[[slug]]/+page.svelte` | 5 |
| `items/materials/[[slug]]/+page.svelte` | 3 |
| `items/furnishings/[[type]]/[[slug]]/+page.svelte` | 4 |
| `items/consumables/[[type]]/[[slug]]/+page.svelte` | 5 |
| `items/clothing/[[slug]]/+page.svelte` | 3 |
| `items/blueprints/[[slug]]/+page.svelte` | 3 |
| `items/blueprints/[[slug]]/Construction.svelte` | 1 |
| `items/attachments/[[type]]/[[slug]]/+page.svelte` | 5 |
| `items/armorsets/[[slug]]/+page.svelte` | 3 |
| `information/vendors/[[slug]]/+page.svelte` | 2 |
| `information/skills/[[slug]]/+page.svelte` | 5 |
| `information/professions/[[slug]]/+page.svelte` | 2 |
| `information/locations/[[type]]/[[slug]]/+page.svelte` | 6 |
| `information/guides/[[slug]]/+page.svelte` | 2 |
| `information/missions/[[slug]]/+page.svelte` | 6 |
| `information/mobs/[[slug]]/+page.svelte` | 5 |

**Verification:** Build + spot-check a few entity pages in browser. Run wiki-related Playwright tests.

## Phase 3 — Wiki Sub-Components

Components used within wiki pages that still have `run()` or `createEventDispatcher`.

| File | `run()` | `dispatch` |
|---|---|---|
| `wiki/EntityInfobox.svelte` | 2 | yes |
| `wiki/EntityImageUpload.svelte` | ~~3~~ **done** | — |
| `wiki/InlineEdit.svelte` | 2 | yes |
| `wiki/RichTextEditor.svelte` | **22** | yes |
| `wiki/MarketPriceSection.svelte` | 3 | yes |
| `wiki/MarketPriceChart.svelte` | 1 | — |
| `wiki/DataSection.svelte` | — | yes |
| `wiki/EffectsEditor.svelte` | 1 | — |
| `wiki/SetEffectsEditor.svelte` | 2 | — |
| `wiki/PetEffectsEditor.svelte` | 1 | — |
| `wiki/WaypointInput.svelte` | 2 | yes |
| `wiki/ColumnConfigDialog.svelte` | — | yes |
| `wiki/CreateEffectDialog.svelte` | — | yes |
| `wiki/ImageCropper.svelte` | — | yes |
| `wiki/ImageUploadDialog.svelte` | — | yes |
| `wiki/ImageUploader.svelte` | — | yes |
| `wiki/WikiHeader.svelte` | — | yes |
| `wiki/MobileDrawer.svelte` | — | yes |
| `wiki/mobs/MobMaturities.svelte` | 1 | — |
| `wiki/mobs/MobGlobals.svelte` | 2 | — |
| `wiki/mobs/CreateSpeciesDialog.svelte` | — | yes |
| `wiki/missions/MissionMapEmbed.svelte` | 1 | — |
| `wiki/missions/ChainEditorDialog.svelte` | 1 | yes |
| `wiki/locations/LocationMapEmbed.svelte` | 2 | — |
| `wiki/shops/ShopInventoryDialog.svelte` | 1 | yes |
| `wiki/shops/ShopManagersDialog.svelte` | 1 | yes |
| `wiki/shops/ShopOwnerDialog.svelte` | 1 | yes |

**RichTextEditor** (22 `run()` calls) is the most complex component. Migrate last in this phase. Many of its `run()` blocks may be convertible to `$derived()`.

**Verification:** Full wiki editing test — create/edit entities, upload images, use rich text editor.

## Phase 4 — Exchange & Market System

| File | `run()` | `dispatch` |
|---|---|---|
| `exchange/ExchangeBrowser.svelte` | **8** (done) | — |
| `exchange/QuickTradeDialog.svelte` | 7 | yes |
| `exchange/OrderDialog.svelte` | 1 | yes |
| `exchange/OrderAdjustDialog.svelte` | 1 | yes |
| `exchange/MassSellDialog.svelte` | 1 | yes |
| `exchange/InventoryItemDialog.svelte` | 1 | yes |
| `exchange/PriceHistoryChart.svelte` | 1 | — |
| `exchange/UserOrdersPanel.svelte` | 1 | yes |
| `exchange/TradeRequestsPanel.svelte` | 1 | — |
| `exchange/BulkTradeDialog.svelte` | — | yes |
| `exchange/CartSummary.svelte` | — | yes |
| `exchange/InventoryImportDialog.svelte` | — | yes |
| `exchange/InventoryPanel.svelte` | — | yes |
| `exchange/MyOrdersView.svelte` | — | yes |
| `exchange/OrderBookTable.svelte` | — | yes |
| `market/shops/[[slug]]/+page.svelte` | 3 | — |
| `market/services/[[slug]]/+page.svelte` | 6 | — |
| `market/services/[id]/edit/+page.svelte` | 1 | — |
| `market/services/[id]/flights/.../+page.svelte` | 1 | — |
| `market/services/create/+page.svelte` | 1 | — |
| `market/rental/[id]/edit/+page.svelte` | 1 | — |
| `market/auction/create/+page.svelte` | 1 | — |
| `auction/AuctionDurationSelector.svelte` | 1 | yes |
| `auction/AuctionDisclaimerDialog.svelte` | — | yes |
| `auction/BidHistoryPanel.svelte` | — | yes |
| `auction/BidSection.svelte` | — | yes |
| `auction/ExchangeRedirectWarning.svelte` | — | yes |
| `rental/RentalRequestDialog.svelte` | 1 | yes |
| `rental/BlockedDatesEditor.svelte` | — | yes |
| `rental/DateRangePicker.svelte` | — | yes |
| `rental/RentalCalendar.svelte` | — | yes |
| `rental/RentalPricingEditor.svelte` | — | yes |
| `services/EquipmentEditor.svelte` | 2 | — |
| `services/AvailabilityCalendar.svelte` | — | yes |
| `services/TicketOfferCard.svelte` | — | yes |
| `services/TicketOfferEditor.svelte` | — | yes |

**Verification:** Exchange order placement, auction creation, shop browsing, rental/service editing. Run exchange Playwright tests.

## Phase 5 — Map System

| File | `run()` | `dispatch` |
|---|---|---|
| `maps/[[planet]]/[[slug]]/+page.svelte` | **14** | — |
| `lib/components/MapCanvas.svelte` | **9** | — |
| `lib/components/MapList.svelte` | 4 | — |
| `map-editor/MapEditorLeaflet.svelte` | 7 | yes |
| `map-editor/MapEditorWorkspace.svelte` | 2 | — |
| `map-editor/MobAreaEditor.svelte` | 3 | yes |
| `map-editor/LocationEditor.svelte` | 5 | yes |
| `map-editor/LocationList.svelte` | 1 | yes |
| `map-editor/WaveEventEditor.svelte` | 2 | yes |
| `map-editor/ChangesSummary.svelte` | — | yes |

**Verification:** Map navigation, location selection, map editor editing/saving.

## Phase 6 — Heavy Pages & Remaining

| File | `run()` | Notes |
|---|---|---|
| `tools/loadouts/[[slug]]/+page.svelte` | **23** | Most complex page |
| `users/[identifier]/+page.svelte` | **20** | User profile |
| `tools/construction/[[planId]]/+page.svelte` | 3 | |
| `tools/construction/MassBuyDialog.svelte` | 4 | |
| `tools/skills/[[slug]]/+page.svelte` | 4 | |
| `+layout.svelte` | 2 | Root layout |
| `account/inventory/+page.svelte` | 1 | |
| `account/inventory/ItemDetailDialog.svelte` | 1 | |
| `account/inventory/VirtualGrid.svelte` | 1 | |
| `admin/changes/[id]/+page.svelte` | 1 | |
| `globals/player/[name]/+page.svelte` | 1 | |
| `globals/target/[name]/+page.svelte` | 1 | |

**Remaining dispatch-only files:**
`lib/components/ItemPicker.svelte`, `lib/components/JsonCompareDialog.svelte`, `lib/components/TextViewerDialog.svelte`, `lib/components/Tooltip.svelte`, `lib/components/InventoryEditForm.svelte`, `lib/components/ManagerEditForm.svelte`, `lib/components/LoadoutList.svelte`, `lib/components/guides/GuideNavigation.svelte`, `lib/components/globals/GlobalMediaDialog.svelte`, `lib/components/globals/GlobalMediaUpload.svelte`, `lib/components/globals/GlobalsDateRangePicker.svelte`, `lib/components/itemsets/ItemMetaEditor.svelte`, `lib/components/itemsets/ItemSetDialog.svelte`, `lib/components/itemsets/SetEntry.svelte`

**Verification:** Full site regression — loadouts, construction, user profiles, inventory, admin.

## Already Completed

- [x] Svelte 5 upgrade with compatibility mode (package bumps, build passing)
- [x] Auto-migration run on all 292 .svelte files
- [x] All `@migration-task` comments resolved
- [x] HTML validity fixes (nested buttons, tbody in custom elements, text in tr)
- [x] Broken self-import paths fixed (6 recursive components)
- [x] Corrupted `<svelte:options>` tags removed
- [x] `bind:object` in `#each` loop fix
- [x] WikiNavigation.svelte — full manual migration
- [x] WikiPage.svelte — full manual migration (slots → snippets, events → callback props)
- [x] `$$slots`, `<slot>`, `afterUpdate`/`beforeUpdate` — all zero remaining
- [x] **ALL `run()` → `$effect()` conversion complete** — 302 occurrences across 96 files, all converted with appropriate `untrack()` for self-referencing patterns. Zero `run()` imports remain.
