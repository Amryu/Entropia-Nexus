<!--
  @component PoolSelectionDialog
  Modal for narrowing the armor/plate candidate pool used by the armor ranking.
  Each checkbox list is independent — selecting nothing in a list means "use all".
-->
<script>
  // @ts-nocheck
  import { untrack } from 'svelte';
  import { scoreSearchResult } from '$lib/search.js';

  const MAX_ENHANCERS = 10;

  let {
    armorSets = [],
    armorPlatings = [],
    initialArmorNames = [],
    initialPlateNames = [],
    initialArmorEnhancers = {},
    defaultEnhancers = 0,
    onclose = () => {},
    onapply = () => {}
  } = $props();

  // Working copies — committed to parent only on Apply
  let selectedArmors = $state(new Set(initialArmorNames));
  let selectedPlates = $state(new Set(initialPlateNames));
  // Per-armor enhancer count (overrides global when armor is selected)
  let armorEnhancers = $state({ ...initialArmorEnhancers });
  let armorQuery = $state('');
  let plateQuery = $state('');

  // Snapshot of "what was selected last time the query changed". The list is
  // partitioned against this so the order stays stable while the user clicks
  // checkboxes; it only re-shuffles when they type/clear the search.
  let armorSelectionSnapshot = $state(new Set(initialArmorNames));
  let platesSelectionSnapshot = $state(new Set(initialPlateNames));
  $effect(() => {
    const _q = armorQuery;
    armorSelectionSnapshot = new Set(untrack(() => selectedArmors));
  });
  $effect(() => {
    const _q = plateQuery;
    platesSelectionSnapshot = new Set(untrack(() => selectedPlates));
  });

  // Sort selected items to the top of each list so the user can always see
  // their current selection at a glance. Sort order within each group stays
  // the same (search-score desc for queries, alphabetical otherwise).
  function partitionSelected(items, isSelected, sortFn) {
    const selected = [];
    const rest = [];
    for (const item of items) {
      (isSelected(item) ? selected : rest).push(item);
    }
    selected.sort(sortFn);
    rest.sort(sortFn);
    return [...selected, ...rest];
  }

  let filteredArmors = $derived.by(() => {
    const q = armorQuery.trim();
    const snap = armorSelectionSnapshot;
    const alphaSort = (a, b) => (a.Name || '').localeCompare(b.Name || '');
    if (!q) {
      return partitionSelected(armorSets, a => snap.has(a.Name), alphaSort);
    }
    const scored = [];
    for (const a of armorSets) {
      const s = scoreSearchResult(a.Name || '', q);
      if (s > 0) scored.push({ a, s });
    }
    const byScore = (x, y) => y.s - x.s;
    return partitionSelected(scored, ({ a }) => snap.has(a.Name), byScore).map(x => x.a);
  });

  let filteredPlates = $derived.by(() => {
    const q = plateQuery.trim();
    const snap = platesSelectionSnapshot;
    const alphaSort = (a, b) => (a.Name || '').localeCompare(b.Name || '');
    if (!q) {
      return partitionSelected(armorPlatings, p => snap.has(p.Name), alphaSort);
    }
    const scored = [];
    for (const p of armorPlatings) {
      const s = scoreSearchResult(p.Name || '', q);
      if (s > 0) scored.push({ p, s });
    }
    const byScore = (x, y) => y.s - x.s;
    return partitionSelected(scored, ({ p }) => snap.has(p.Name), byScore).map(x => x.p);
  });

  function toggleArmor(name) {
    if (selectedArmors.has(name)) {
      selectedArmors.delete(name);
    } else {
      selectedArmors.add(name);
      // Seed per-armor enhancer to the current global default if not yet set
      if (armorEnhancers[name] == null) {
        armorEnhancers[name] = defaultEnhancers;
      }
    }
    selectedArmors = new Set(selectedArmors);
  }

  function setArmorEnhancer(name, raw) {
    const n = Number.parseInt(raw, 10);
    const clamped = !Number.isFinite(n) ? 0 : Math.max(0, Math.min(MAX_ENHANCERS, n));
    armorEnhancers = { ...armorEnhancers, [name]: clamped };
  }

  function togglePlate(name) {
    if (selectedPlates.has(name)) selectedPlates.delete(name);
    else selectedPlates.add(name);
    selectedPlates = new Set(selectedPlates);
  }

  function clearArmors() {
    selectedArmors = new Set();
  }
  function clearPlates() {
    selectedPlates = new Set();
  }
  function clearAll() {
    selectedArmors = new Set();
    selectedPlates = new Set();
  }

  function apply() {
    // Emit enhancer overrides only for currently-selected armors
    const enhancerOverrides = {};
    for (const name of selectedArmors) {
      if (armorEnhancers[name] != null) enhancerOverrides[name] = armorEnhancers[name];
    }
    onapply({
      armorNames: Array.from(selectedArmors),
      plateNames: Array.from(selectedPlates),
      armorEnhancers: enhancerOverrides
    });
    onclose();
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') onclose();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="pool-dialog-backdrop" onclick={onclose} role="presentation">
  <div class="pool-dialog" onclick={(e) => e.stopPropagation()} role="dialog" aria-label="Configure pool">
    <header class="dialog-header">
      <h3>Configure candidate pool</h3>
      <button class="close-btn" onclick={onclose} aria-label="Close">×</button>
    </header>

    <div class="dialog-body">
      <!-- Armor column -->
      <section class="pool-column">
        <div class="column-header">
          <h4>Armor sets</h4>
          <span class="count">
            {#if selectedArmors.size === 0}all {armorSets.length}{:else}{selectedArmors.size} of {armorSets.length}{/if}
          </span>
        </div>
        <input
          type="text"
          class="pool-search"
          placeholder="Search armor sets..."
          bind:value={armorQuery}
        />
        <div class="pool-list">
          {#each filteredArmors as armor (armor.Name)}
            {@const isSel = selectedArmors.has(armor.Name)}
            <label class="pool-item pool-item--armor">
              <input
                type="checkbox"
                checked={isSel}
                onchange={() => toggleArmor(armor.Name)}
              />
              <span class="item-name">{armor.Name}</span>
              <span class="enh-wrap" title="Defense enhancers for this armor">
                <span class="enh-label">enh</span>
                <input
                  type="number"
                  class="enh-input"
                  min="0"
                  max={MAX_ENHANCERS}
                  value={armorEnhancers[armor.Name] ?? defaultEnhancers}
                  oninput={(e) => setArmorEnhancer(armor.Name, e.target.value)}
                  disabled={!isSel}
                  onclick={(e) => e.preventDefault()}
                />
              </span>
            </label>
          {/each}
          {#if filteredArmors.length === 0}
            <p class="pool-empty">No matches</p>
          {/if}
        </div>
        {#if selectedArmors.size > 0}
          <button class="link-btn" onclick={clearArmors}>Clear armor selection</button>
        {/if}
      </section>

      <!-- Plate column -->
      <section class="pool-column">
        <div class="column-header">
          <h4>Armor plates</h4>
          <span class="count">
            {#if selectedPlates.size === 0}all {armorPlatings.length}{:else}{selectedPlates.size} of {armorPlatings.length}{/if}
          </span>
        </div>
        <input
          type="text"
          class="pool-search"
          placeholder="Search plates..."
          bind:value={plateQuery}
        />
        <div class="pool-list">
          {#each filteredPlates as plate (plate.Name)}
            <label class="pool-item">
              <input
                type="checkbox"
                checked={selectedPlates.has(plate.Name)}
                onchange={() => togglePlate(plate.Name)}
              />
              <span>{plate.Name}</span>
            </label>
          {/each}
          {#if filteredPlates.length === 0}
            <p class="pool-empty">No matches</p>
          {/if}
        </div>
        {#if selectedPlates.size > 0}
          <button class="link-btn" onclick={clearPlates}>Clear plate selection</button>
        {/if}
      </section>
    </div>

    <footer class="dialog-footer">
      <p class="hint">Unselected column = use all. Selecting armors bumps the plate rank depth to 10 per armor.</p>
      <div class="footer-actions">
        <button class="btn" onclick={clearAll}>Clear all</button>
        <button class="btn" onclick={onclose}>Cancel</button>
        <button class="btn btn-primary" onclick={apply}>Apply</button>
      </div>
    </footer>
  </div>
</div>

<style>
  .pool-dialog-backdrop {
    position: fixed;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    z-index: 200;
  }

  .pool-dialog {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 100%;
    max-width: 880px;
    height: min(80vh, 680px);
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
    background-color: var(--primary-color);
    border-radius: 8px 8px 0 0;
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
  }

  .close-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 22px;
    line-height: 1;
    padding: 2px 8px;
    cursor: pointer;
    border-radius: 4px;
  }
  .close-btn:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .dialog-body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    padding: 16px;
    overflow: hidden;
    min-height: 0;
    flex: 1;
  }

  .pool-column {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 0;
  }

  .column-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }

  .column-header h4 {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
  }

  .count {
    font-size: 11px;
    color: var(--text-muted);
  }

  .pool-search {
    padding: 6px 10px;
    font-size: 12px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
  }
  .pool-search:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .pool-list {
    flex: 1 1 0;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--primary-color);
    min-height: 0;
  }

  .pool-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 10px;
    font-size: 12px;
    cursor: pointer;
    border-bottom: 1px solid color-mix(in srgb, var(--border-color) 40%, transparent);
  }
  .pool-item:last-child { border-bottom: none; }
  .pool-item:hover { background-color: var(--hover-color); }
  .pool-item input { margin: 0; }

  .pool-item--armor {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 8px;
    align-items: center;
  }

  .pool-item .item-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }

  .enh-wrap {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }

  .enh-label {
    font-size: 10px;
    color: var(--text-muted);
  }

  .enh-input {
    width: 44px;
    padding: 2px 4px;
    font-size: 11px;
    background-color: var(--bg-color, var(--secondary-color));
    border: 1px solid var(--border-color);
    border-radius: 3px;
    color: var(--text-color);
  }
  .enh-input:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .pool-empty {
    margin: 0;
    padding: 16px;
    text-align: center;
    font-size: 11px;
    color: var(--text-muted);
  }

  .link-btn {
    background: transparent;
    border: none;
    color: var(--accent-color);
    font-size: 11px;
    padding: 2px 0;
    cursor: pointer;
    text-align: left;
    align-self: flex-start;
  }
  .link-btn:hover { text-decoration: underline; }

  .dialog-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 16px;
    border-top: 1px solid var(--border-color);
    background-color: var(--primary-color);
    border-radius: 0 0 8px 8px;
    gap: 12px;
    flex-wrap: wrap;
  }

  .hint {
    margin: 0;
    font-size: 11px;
    color: var(--text-muted);
    flex: 1;
    min-width: 200px;
  }

  .footer-actions {
    display: flex;
    gap: 6px;
  }

  .btn {
    padding: 6px 12px;
    font-size: 12px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
    cursor: pointer;
  }
  .btn:hover { background-color: var(--hover-color); }

  .btn-primary {
    background-color: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
  }
  .btn-primary:hover { filter: brightness(1.1); }

  @media (max-width: 699px) {
    .pool-dialog {
      height: 90vh;
    }
    .dialog-body {
      grid-template-columns: 1fr;
      grid-template-rows: 1fr 1fr;
    }
  }
</style>
