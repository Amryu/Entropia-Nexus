# Svelte 5 Migration Plan

## Current State

| Package | Version |
|---|---|
| `svelte` | 4.2.7 |
| `@sveltejs/kit` | 2.0.0 |
| `@sveltejs/vite-plugin-svelte` | 3.0.0 |
| `vite` | 5.0.3 |
| `svelte-check` | 3.6.0 |

**Scale**: 292 `.svelte` files, 71 Playwright E2E tests.

## Codebase Pattern Inventory

| Pattern | Occurrences | Files | Svelte 5 Replacement |
|---|---|---|---|
| `on:event` handlers | 2,454 | 218 | `onevent` attribute syntax |
| `$:` reactive declarations | 1,839 | 217 | `$derived()` / `$derived.by()` / `$effect()` |
| `export let` props | 847 | 244 | `let { ... } = $props()` |
| `bind:` directives | 583 | 139 | Mostly unchanged; bound props need `$bindable()` |
| `createEventDispatcher` | 323 | 69 | Callback props |
| Lifecycle hooks | 248 | 101 | `$effect()` (some `onMount` still valid) |
| `use:action` | 52 | 24 | Unchanged |
| Slots | 22 | 22 | `{@render children()}` / snippets |
| `$$slots` | 2 | 2 | Check snippet prop existence |
| `svelte:component` | 5 | 5 | Direct `<Component />` with variable |
| Context API | 6 | 6 | Unchanged |

---

## Minimal Steps (Phase 0 Only)

If the goal is simply to **run on Svelte 5 without changing any components**, only Phase 0 is required. Svelte 5's legacy/compatibility mode runs all Svelte 4 syntax unchanged.

1. Update `nexus/package.json` versions (see table below)
2. Run `npm install`
3. Run `npm run build` — fix any build errors
4. Run `npm run check` — fix any svelte-check errors
5. Run Playwright tests — verify all pass
6. Done. The app is now on Svelte 5 in legacy mode.

---

## Phase 0 — Upgrade to Svelte 5 (Legacy Mode)

**Goal**: Get the project running on Svelte 5 with zero component changes.

### Version Bumps

Update `nexus/package.json`:

| Package | Current | Target | Notes |
|---|---|---|---|
| `svelte` | `^4.2.7` | `^5.0.0` | Core upgrade |
| `@sveltejs/kit` | `^2.0.0` | `^2.16.0` | Latest SvelteKit 2.x with Svelte 5 support |
| `@sveltejs/vite-plugin-svelte` | `^3.0.0` | `^5.0.0` | Required for Svelte 5 |
| `svelte-check` | `^3.6.0` | `^4.0.0` | Svelte 5 type checking |
| `vite` | `^5.0.3` | `^6.0.0` | Required by vite-plugin-svelte 5 |
| `svelte-easy-crop` | `^3.0.1` | Check npm | Only 2 files use it — verify Svelte 5 compat |
| `svelte-chartjs` | `^3.1.5` | **Remove** | Not imported anywhere — dead dependency |

### Config Changes

`nexus/svelte.config.js` — the `vitePreprocess` import may need updating depending on the vite-plugin-svelte version. Check release notes.

`nexus/vite.config.ts` — no changes needed.

### Potential Breakages to Watch

1. `$$slots` in `FancyTable.svelte` and `WikiPage.svelte` — works in legacy mode
2. `svelte:component` in 5 files — works in legacy mode
3. `export function` component methods in ~14 files (MapCanvas, SearchInput, etc.) — works in legacy mode
4. `<script context="module">` in some files — works in legacy mode

### Testing Gate

```bash
npm install
npm run build
npm run check
npm run dev          # manual smoke test
npx playwright test  # full E2E suite — all 71 tests must pass
```

**Estimated effort**: 2–4 hours.

---

## Phase 1 — Leaf Components

**Goal**: Migrate simple display components to establish patterns for the rest of the migration.

### Migration Tool

Run the official Svelte migration tool **per file or small batch** (not the entire codebase):

```bash
npx sv migrate svelte-5
```

The tool handles most mechanical transformations but can make mistakes with complex reactive patterns. Always review output.

### Tier 1 — Pure Display (no events, no slots, no bindings)

- `Skeleton.svelte`, `SkeletonTable.svelte`, `SkeletonCard.svelte`
- `RequestStatusBadge.svelte`, `OrderStatusBadge.svelte`, `AuctionStatusBadge.svelte`, `RentalStatusBadge.svelte`
- `WaypointCopyButton.svelte`, `MapLinkButton.svelte`
- `LoginToCreateButton.svelte`, `GzButton.svelte`
- `WikiSEO.svelte`

### Tier 2 — Props + Simple Events

- `DashboardNav.svelte`
- `GuideNavigation.svelte`
- `Properties.svelte`

### Tier 3 — Components with `createEventDispatcher`

Start with components that dispatch few events:

- `AuctionCountdown.svelte` (dispatches `expired`)
- `AuctionDurationSelector.svelte` (dispatches `change`)
- `FeePreview.svelte` (pure display)
- `ExchangeRedirectWarning.svelte` (dispatches `close`)

### Per-Component Workflow

1. Run `npx sv migrate svelte-5` on the single file
2. Review the auto-migration output
3. Fix any issues the tool missed
4. `npm run check`
5. Run relevant Playwright tests
6. Commit

**Estimated effort**: 1–2 days.

---

## Phase 2 — Core Shared Components

**Goal**: Migrate high-consumer shared components. These block downstream page migration.

### Priority Order

1. **`DataSection.svelte`** (~30 consumers)
   - `export let expanded` → `$bindable()` (parents use `bind:expanded`)
   - `createEventDispatcher` → callback prop `ontoggle`
   - Named slot `actions` + default slot → snippets

2. **`TurnstileWidget.svelte`** (used by auction/exchange security flows)
   - `export let token`, `export let reset` → both need `$bindable()`
   - `createEventDispatcher` for `verified`, `error`, `expired` → callback props
   - `$: if (reset && browser)` → `$effect()`

3. **`Tooltip.svelte`**, **`BrowseList.svelte`**, **`NavList.svelte`**
   - `createEventDispatcher` → callback props

4. **`Table.svelte`**, **`VirtualTableRow.svelte`**
   - `createEventDispatcher`, slots → snippets

5. **`EditFormControlGroup.svelte`**
   - 7 `bind:value` instances, `createEventDispatcher`

### Testing After Each Component

- `DataSection`: run all wiki tests
- `TurnstileWidget`: run auction and exchange tests
- `SearchInput`: run `tests/search-page.spec.ts`, `tests/market/market-search.spec.ts`

**Estimated effort**: 3–5 days.

---

## Phase 3 — Complex Subsystems

### 3A: FancyTable.svelte

The most complex single component: 17 reactive declarations, 5 event dispatches, `$$slots`, `svelte:component`, virtual scrolling.

**Steps:**
1. Convert 18 `export let` props → `let { ... } = $props()`
2. Convert `createEventDispatcher` → callback props (`onRowClick`, `onRowHover`, `onSort`)
3. Convert 17 `$:` declarations → `$derived()` / `$derived.by()`
4. Side-effect reactives → `$effect()`
5. `$$slots.cell` → check if `cell` snippet prop is defined
6. `svelte:component this={column.component}` → direct `<Component />` render
7. Slots → `{@render cell({ column, row, value })}`

**Risk**: Array mutation reactivity. `internalData = internalData` trigger pattern won't be needed with `$state` proxies. `let internalData = []` becomes `let internalData = $state([])`.

**Tests**: `tests/exchange/exchange-categories.spec.ts`, `tests/market/market-search.spec.ts`, any test rendering a FancyTable.

### 3B: Wiki Editor System (60+ components)

**Migration order:**
1. Display-only: `WikiSEO`, `WaypointCopyButton`, `MapLinkButton`
2. Data display: `WeaponDamageGrid`, `MobDamageGrid`, `VendorOffers`, `ShopInventory`, `MobMaturities`, `MobLoots`, `MobLocations`
3. Chrome: `WikiHeader`, `WikiNavigation`, `MobileDrawer`, `EntityInfobox`
4. Editors: all `*Edit.svelte` and `*Editor.svelte` files
5. `WikiPage.svelte` (last — has `$$slots`, slots, complex lifecycle)
6. Image system: `ImageUploader`, `ImageUploadDialog`, `ImageCropper` (svelte-easy-crop dep)

**Store compatibility**: `wikiEditState.js` uses `svelte/store` writable/derived. The `$storeName` auto-subscription works in both legacy and runes mode. No urgent store migration needed.

### 3C: Exchange System

Files in `nexus/src/routes/market/exchange/[[slug]]/[[id]]/`:
- `ExchangeBrowser.svelte`, `OrderDialog.svelte`, `QuickTradeDialog.svelte`
- `OrderBookTable.svelte`, `MyOrdersView.svelte`, `UserOrdersPanel.svelte`
- `InventoryPanel.svelte`, `MassSellDialog.svelte`, `BulkTradeDialog.svelte`
- `CartSummary.svelte`, `PriceHistoryChart.svelte`, `CategoryTree.svelte`

### 3D: Auction, Services, Rental, Maps

Lower priority — migrate as capacity allows.

**Estimated effort**: 2–3 weeks.

---

## Phase 4 — Route/Page Components

Page components are consumers of shared components. Migrate after their children.

**Common transformation:**
```svelte
<!-- Before -->
<script>
  export let data;
</script>
<slot />

<!-- After -->
<script>
  let { data, children } = $props();
</script>
{@render children()}
```

**Root layout** (`+layout.svelte`):
- `export let data` → `let { data, children } = $props()`
- `<slot />` → `{@render children()}`

**Order**: Simple pages first → complex pages (exchange, loadout calculator, wiki entity pages) last.

**Estimated effort**: 1–2 weeks.

---

## Phase 5 — Store Migration (Optional)

The `svelte/store` API is **not deprecated** in Svelte 5. Stores (`toasts.js`, `wikiEditState.js`, `preferences.js`) continue working indefinitely.

**Optional migration** to runes-based state:
1. Rename files to `.svelte.js` extension
2. Replace `writable(x)` with `let value = $state(x)` and export getter/setter
3. Replace `derived` with `$derived`

**Recommendation**: Defer unless you want cleaner APIs or fine-grained reactivity benefits.

**Estimated effort**: 2–3 days.

---

## Phase 6 — Cleanup

1. Remove `svelte-chartjs` from `package.json` (unused)
2. Update or replace `svelte-easy-crop` if no Svelte 5 version exists
3. Audit for remaining `$:`, `on:`, `createEventDispatcher`, `export let` — should be zero
4. Run full Playwright suite
5. Run `npm run check` — should be clean

**Estimated effort**: 1–2 days.

---

## Pattern Transformation Reference

### Props

```svelte
<!-- Before -->
<script>
  export let title;
  export let count = 0;
</script>

<!-- After -->
<script>
  let { title, count = 0 } = $props();
</script>
```

### Reactive Declarations

```svelte
<!-- Before -->
<script>
  $: doubled = count * 2;
  $: items = data.filter(d => d.active);
  $: complexValue = (() => {
    // multi-line logic
    return result;
  })();
</script>

<!-- After -->
<script>
  let doubled = $derived(count * 2);
  let items = $derived(data.filter(d => d.active));
  let complexValue = $derived.by(() => {
    // multi-line logic
    return result;
  });
</script>
```

### Reactive Side Effects

```svelte
<!-- Before -->
<script>
  $: if (reset && browser) {
    resetWidget();
    reset = false;
  }
</script>

<!-- After -->
<script>
  $effect(() => {
    if (reset && browser) {
      resetWidget();
      reset = false;
    }
  });
</script>
```

### Event Dispatching

```svelte
<!-- Before -->
<script>
  import { createEventDispatcher } from 'svelte';
  const dispatch = createEventDispatcher();
</script>
<button on:click={() => dispatch('toggle', { expanded })}>Toggle</button>

<!-- Parent: <DataSection on:toggle={handleToggle}> -->

<!-- After -->
<script>
  let { ontoggle } = $props();
</script>
<button onclick={() => ontoggle?.({ expanded })}>Toggle</button>

<!-- Parent: <DataSection ontoggle={handleToggle}> -->
```

### Event Handlers

```svelte
<!-- Before -->
<button on:click={handler}>Click</button>
<button on:click|preventDefault={handler}>Click</button>
<input on:input={(e) => update(e.target.value)} />

<!-- After -->
<button onclick={handler}>Click</button>
<button onclick={(e) => { e.preventDefault(); handler(e); }}>Click</button>
<input oninput={(e) => update(e.target.value)} />
```

### Slots → Snippets

```svelte
<!-- Before (child) -->
<div>
  <slot />
  <slot name="actions" />
</div>

<!-- After (child) -->
<script>
  let { children, actions } = $props();
</script>
<div>
  {@render children()}
  {#if actions}{@render actions()}{/if}
</div>

<!-- Before (parent) -->
<DataSection>
  <p>Content</p>
  <svelte:fragment slot="actions">
    <button>Edit</button>
  </svelte:fragment>
</DataSection>

<!-- After (parent) -->
<DataSection>
  {#snippet actions()}
    <button>Edit</button>
  {/snippet}
  <p>Content</p>
</DataSection>
```

### Slot Props → Snippet Parameters

```svelte
<!-- Before (child) -->
<slot name="cell" {column} {row} value={row[column.key]} />

<!-- After (child) -->
<script>
  let { cell } = $props();
</script>
{@render cell({ column, row, value: row[column.key] })}

<!-- Before (parent) -->
<FancyTable>
  <div slot="cell" let:column let:row let:value>
    {value}
  </div>
</FancyTable>

<!-- After (parent) -->
<FancyTable>
  {#snippet cell({ column, row, value })}
    <div>{value}</div>
  {/snippet}
</FancyTable>
```

### $$slots → Snippet Check

```svelte
<!-- Before -->
{#if $$slots.cell && column.slotted}
  <slot name="cell" {column} {row} />
{/if}

<!-- After -->
{#if cell && column.slotted}
  {@render cell({ column, row })}
{/if}
```

### Bindable Props

```svelte
<!-- Before -->
<script>
  export let expanded = false;
</script>

<!-- After -->
<script>
  let { expanded = $bindable(false) } = $props();
</script>
```

### svelte:component → Direct Render

```svelte
<!-- Before -->
<svelte:component this={column.component} {row} value={row[column.key]} />

<!-- After -->
{@const Component = column.component}
<Component {row} value={row[column.key]} />
```

### Lifecycle Hooks

```svelte
<!-- Before -->
<script>
  import { onMount, onDestroy } from 'svelte';

  let interval;
  onMount(() => {
    interval = setInterval(update, 1000);
  });
  onDestroy(() => {
    clearInterval(interval);
  });
</script>

<!-- After -->
<script>
  let interval;
  $effect(() => {
    interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  });
</script>
```

Note: `onMount` still works in Svelte 5 and is valid for code that should only run on the client. `$effect` also only runs on the client and returns a cleanup function (replacing `onDestroy`).

### script context="module"

```svelte
<!-- Before -->
<script context="module">
  export const prerender = true;
</script>

<!-- After -->
<script module>
  export const prerender = true;
</script>
```

---

## Risk Matrix

| Risk | Impact | Files Affected | Mitigation |
|---|---|---|---|
| `svelte-easy-crop` incompatible with Svelte 5 | Medium | 2 (`ImageCropper`, `ImageUploadDialog`) | Keep in legacy mode or reimplement with canvas |
| `export function` component methods | Medium | ~14 files | Keep in legacy mode until refactored; use bindable object pattern |
| Array mutation reactivity changes | High | `FancyTable.svelte`, exchange components | Use `$state()` for mutable arrays; test virtual scrolling thoroughly |
| `$$slots` removal | Low | 2 (`FancyTable`, `WikiPage`) | Convert to snippet existence checks |
| Event modifier syntax (`on:click\|preventDefault`) | Low | ~50 occurrences | Inline `e.preventDefault()` in handler |
| `bind:prop` requires `$bindable()` | Medium | `DataSection` (30 consumers), `TurnstileWidget` | Grep for `bind:expanded` etc. before migrating each component |
| Store `$` prefix collision with runes | Low | All store consumers | No actual collision — `$storeName` works in runes mode for stores |

---

## Testing Strategy

| Phase | Approach | Pass Criteria |
|---|---|---|
| Phase 0 | Full Playwright suite | 100% pass |
| Phase 1 | Targeted tests per component batch | Related tests pass |
| Phase 2 | Subsystem tests (wiki, exchange, auction) | All related tests pass |
| Phase 3 | Subsystem + manual testing for complex UIs | Performance parity, all tests pass |
| Phase 4 | Full suite after every 10–15 pages | 100% pass |
| Phase 6 | Full suite, `npm run check` | 100% pass, zero warnings |

---

## Timeline Estimate

| Phase | Duration | Cumulative |
|---|---|---|
| Phase 0: Svelte 5 in legacy mode | 2–4 hours | Day 1 |
| Phase 1: Leaf components | 1–2 days | Day 2–3 |
| Phase 2: Core shared components | 3–5 days | Week 1–2 |
| Phase 3: Complex subsystems | 2–3 weeks | Week 2–5 |
| Phase 4: Route/page components | 1–2 weeks | Week 5–7 |
| Phase 5: Store migration (optional) | 2–3 days | Week 7–8 |
| Phase 6: Cleanup | 1–2 days | Week 8 |

**Total**: 6–8 weeks part-time, 3–4 weeks full-time.

**Critical path**: Phase 0 → Phase 2 (shared components block Phase 3 and 4). Phase 3 subsystems can be done in parallel.
