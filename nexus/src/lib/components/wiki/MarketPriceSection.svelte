<!--
  @component MarketPriceSection
  Self-contained market price display for wiki item pages.
  Fetches data client-side and shows a table of latest values
  plus historical markup/sales charts with period selection.

  For armor sets, accepts a `pieces` prop to show a piece/gender
  selector, fetching per-piece market data by name.

  For tierable entity types, shows a tier selector (0-10) that
  filters market price data by tier.
-->
<script>
  //@ts-nocheck
  import { onMount, untrack } from 'svelte';
  import { browser } from '$app/environment';
  import DataSection from './DataSection.svelte';
  import MarketPriceChart from './MarketPriceChart.svelte';
  import { TIERABLE_TYPES, STACKABLE_TYPES, CONDITION_TYPES } from '$lib/common/itemTypes.js';

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {number|null} [itemId]
   * @property {string|null} [itemName]
   * @property {boolean} [expanded]
   * @property {Array<{name: string, slot: string, gender: string}>|null} [pieces] - Armor set pieces for piece-level market price selection.
When provided, a slot/gender selector is shown and prices are fetched per piece.
   * @property {string|null} [entityType] - Entity type (e.g. "Weapon", "ArmorSet"). When tierable, a tier selector is shown.
   * @property {Function} [ontoggle]
   */

  /** @type {Props} */
  let {
    itemId = null,
    itemName = null,
    expanded = $bindable(true),
    pieces = null,
    entityType = null,
    ontoggle
  } = $props();

  const PERIODS = [
    { key: '1d', label: '1 Day' },
    { key: '7d', label: '7 Days' },
    { key: '30d', label: '30 Days' },
    { key: '365d', label: '1 Year' },
    { key: '3650d', label: '10 Years' }
  ];

  const SLOT_ORDER = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];
  const TIER_OPTIONS = Array.from({ length: 11 }, (_, i) => i); // 0-10

  let snapshot = $state(null);
  let loading = $state(true);
  let historyData = $state([]);
  let historyLoading = $state(false);
  let historyLoaded = false;
  let selectedPeriod = $state('30d');
  let showCharts = $state(false);

  // Piece selector state
  let selectedSlot = $state(null);
  let selectedGender = $state('male');

  // Tier selector state
  let selectedTier = $state(0);

  // Determine if tier selector should be shown
  let showTierSelector = $derived(entityType && TIERABLE_TYPES.has(entityType));

  // Absolute markup items: non-stackable UL condition items, non-L blueprints
  let isAbsMarkup = $derived(() => {
    if (!entityType) return false;
    if (STACKABLE_TYPES.has(entityType)) return false;
    if (entityType === 'Blueprint') return !/\(.*L.*\)/.test(itemName || '');
    if (CONDITION_TYPES.has(entityType)) return !/\(.*L.*\)/.test(itemName || '');
    return true;
  });

  function toggleSection() {
    ontoggle?.({ expanded });
  }

  // --- Piece helpers ---

  /** Organize flat pieces array into { [slot]: { male, female } } */
  function buildPiecesBySlot(pcs) {
    const result = {};
    for (const slot of SLOT_ORDER) result[slot] = { male: null, female: null };
    for (const p of pcs) {
      const slot = p.slot;
      if (!result[slot]) continue;
      if (p.gender === 'Both' || p.gender === 'Male') result[slot].male = p;
      if (p.gender === 'Both' || p.gender === 'Female') result[slot].female = p;
    }
    // Keep only slots that have at least one piece
    const filtered = {};
    for (const [slot, v] of Object.entries(result)) {
      if (v.male || v.female) filtered[slot] = v;
    }
    return filtered;
  }

  let piecesBySlot = $derived(pieces ? buildPiecesBySlot(pieces) : null);
  let availableSlots = $derived(piecesBySlot ? SLOT_ORDER.filter(s => piecesBySlot[s]) : []);

  // Auto-select first slot when pieces change
  $effect(() => {
    if (availableSlots.length > 0 && (!untrack(() => selectedSlot) || !piecesBySlot?.[untrack(() => selectedSlot)])) {
      selectedSlot = availableSlots[0];
    }
  });

  // Check if selected slot has distinct gender variants
  let slotHasGenderVariants = $derived((() => {
    if (!piecesBySlot || !selectedSlot) return false;
    const entry = piecesBySlot[selectedSlot];
    if (!entry?.male || !entry?.female) return false;
    return entry.male.name !== entry.female.name;
  })());

  // Resolve active piece name for fetching
  let activePieceName = $derived((() => {
    if (!piecesBySlot || !selectedSlot) return null;
    const entry = piecesBySlot[selectedSlot];
    if (!entry) return null;
    if (slotHasGenderVariants) {
      const pick = selectedGender === 'female' ? entry.female : entry.male;
      return pick?.name || entry.male?.name || entry.female?.name || null;
    }
    return entry.male?.name || entry.female?.name || null;
  })());

  function selectSlot(slot) {
    selectedSlot = slot;
    // Reset gender to male when switching slots
    selectedGender = 'male';
  }

  function selectGender(gender) {
    selectedGender = gender;
  }

  function selectTier(tier) {
    selectedTier = tier;
  }

  // --- Data fetching ---

  /** Build tier query string fragment */
  function tierQuery() {
    if (showTierSelector) return `&tier=${selectedTier}`;
    return '';
  }

  async function fetchLatest(id, name) {
    loading = true;
    snapshot = null;
    historyData = [];
    historyLoaded = false;
    showCharts = false;

    try {
      if (id) {
        const res = await fetch(`/api/market/prices/snapshots/latest?itemIds=${id}${tierQuery()}`);
        if (res.ok) {
          const rows = await res.json();
          if (rows.length > 0) {
            snapshot = rows[0];
            loading = false;
            return;
          }
        }
      }
      // Fallback: try by name
      if (name) {
        const res = await fetch(`/api/market/prices/snapshots/latest?name=${encodeURIComponent(name)}${tierQuery()}`);
        if (res.ok) {
          const data = await res.json();
          // Name endpoint may return object or array
          if (Array.isArray(data)) {
            if (data.length > 0) snapshot = data[0];
          } else if (data && data.item_id) {
            snapshot = data;
          }
        }
      }
    } catch (e) {
      console.error('[MarketPriceSection] Failed to fetch latest:', e);
    }
    loading = false;
  }

  async function fetchHistory() {
    if (historyLoaded || !snapshot) return;
    const id = snapshot.item_id || itemId;
    if (!id) return;

    historyLoading = true;
    try {
      const res = await fetch(`/api/market/prices/snapshots/${id}?limit=750${tierQuery()}`);
      if (res.ok) {
        historyData = await res.json();
      }
    } catch (e) {
      console.error('[MarketPriceSection] Failed to fetch history:', e);
    }
    historyLoaded = true;
    historyLoading = false;
  }

  function toggleCharts() {
    showCharts = !showCharts;
    if (showCharts && !historyLoaded) {
      fetchHistory();
    }
  }

  function selectPeriod(key) {
    selectedPeriod = key;
    if (!historyLoaded) {
      fetchHistory();
    }
  }

  function formatMarkup(val) {
    if (val == null) return '\u2014';
    return isAbsMarkup() ? `+${Number(val).toFixed(2)}` : `${Number(val).toFixed(2)}%`;
  }

  function formatSales(val) {
    if (val == null) return '\u2014';
    return Number(val).toLocaleString();
  }

  function timeAgo(dateStr) {
    if (!dateStr) return '';
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  }

  // Reactive: fetch when piece, item, or tier changes (client-side only)
  // Reference selectedTier to track it as a dependency for refetch on tier change.
  $effect(() => {
    if (browser && pieces && activePieceName) {
      selectedTier;
      fetchLatest(null, activePieceName);
    }
  });
  $effect(() => {
    if (browser && !pieces && (itemId || itemName)) {
      selectedTier;
      fetchLatest(itemId, itemName);
    }
  });
</script>

<DataSection title="Market Prices" bind:expanded ontoggle={toggleSection}>
  <div class="mps-content">
    {#if showTierSelector}
      <div class="mps-tier-selector">
        <div class="mps-tier-buttons">
          {#each TIER_OPTIONS as tier}
            <button
              class="tier-btn"
              class:active={selectedTier === tier}
              onclick={() => selectTier(tier)}
            >{tier}</button>
          {/each}
        </div>
      </div>
    {/if}

    {#if piecesBySlot}
      <div class="mps-piece-selector">
        <div class="mps-slot-buttons">
          {#each availableSlots as slot}
            <button
              class="slot-btn"
              class:active={selectedSlot === slot}
              onclick={() => selectSlot(slot)}
            >{slot}</button>
          {/each}
        </div>
        {#if slotHasGenderVariants}
          <div class="mps-gender-toggle">
            <button
              class="gender-btn"
              class:active={selectedGender === 'male'}
              onclick={() => selectGender('male')}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="10" cy="14" r="5"/><line x1="14" y1="10" x2="21" y2="3"/><polyline points="15,3 21,3 21,9"/>
              </svg>
              Male
            </button>
            <button
              class="gender-btn"
              class:active={selectedGender === 'female'}
              onclick={() => selectGender('female')}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="8" r="5"/><line x1="12" y1="13" x2="12" y2="21"/><line x1="9" y1="18" x2="15" y2="18"/>
              </svg>
              Female
            </button>
          </div>
        {/if}
      </div>
    {/if}

    {#if loading}
      <div class="mps-loading">Loading market prices...</div>
    {:else if !snapshot}
      <div class="mps-empty">No market price data available{showTierSelector && selectedTier > 0 ? ` for Tier ${selectedTier}` : ''}</div>
    {:else}
      <table class="mps-table">
        <thead>
          <tr>
            <th>Period</th>
            <th class="num">Markup</th>
            <th class="num">Sales</th>
          </tr>
        </thead>
        <tbody>
          {#each PERIODS as { key, label }}
            <tr class:active={showCharts && selectedPeriod === key}>
              <td>{label}</td>
              <td class="num">{formatMarkup(snapshot[`markup_${key}`])}</td>
              <td class="num">{formatSales(snapshot[`sales_${key}`])}</td>
            </tr>
          {/each}
        </tbody>
      </table>

      <div class="mps-meta">
        <span class="mps-updated">Updated {timeAgo(snapshot.recorded_at)}</span>
        {#if snapshot.tier != null && snapshot.tier > 0}
          <span class="mps-tier-badge">Tier {snapshot.tier}</span>
        {/if}
        {#if snapshot.confidence != null && snapshot.confidence < 0.5}
          <span class="mps-low-confidence" title="Low confidence — few submissions">Low confidence</span>
        {/if}
      </div>

      <div class="mps-chart-toggle">
        <button class="mps-chart-btn" onclick={toggleCharts}>
          {showCharts ? 'Hide Charts' : 'Show Price History'}
        </button>
      </div>

      {#if showCharts}
        <div class="mps-period-selector">
          {#each PERIODS as { key, label }}
            <button
              class="period-btn"
              class:active={selectedPeriod === key}
              onclick={() => selectPeriod(key)}
            >{label}</button>
          {/each}
        </div>

        <div class="mps-charts">
          <div class="mps-chart-col">
            <MarketPriceChart
              data={historyData}
              period={selectedPeriod}
              field="markup"
              title="Markup"
              loading={historyLoading}
            />
          </div>
          <div class="mps-chart-col">
            <MarketPriceChart
              data={historyData}
              period={selectedPeriod}
              field="sales"
              title="Sales"
              loading={historyLoading}
            />
          </div>
        </div>
      {/if}
    {/if}
  </div>
</DataSection>

<style>
  .mps-content {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .mps-loading, .mps-empty {
    color: var(--text-muted);
    font-size: 13px;
    padding: 8px 0;
  }

  /* Tier selector */
  .mps-tier-selector {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .mps-tier-buttons {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  .tier-btn {
    background: var(--hover-color);
    color: var(--text-muted);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
    min-width: 30px;
    text-align: center;
  }

  .tier-btn:hover {
    color: var(--text-color);
    background: var(--border-color);
  }

  .tier-btn.active {
    background: var(--accent-color);
    color: #fff;
    border-color: var(--accent-color);
  }

  /* Piece selector (armor sets) */
  .mps-piece-selector {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .mps-slot-buttons {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  .slot-btn {
    background: var(--hover-color);
    color: var(--text-muted);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .slot-btn:hover {
    color: var(--text-color);
    background: var(--border-color);
  }

  .slot-btn.active {
    background: var(--accent-color);
    color: #fff;
    border-color: var(--accent-color);
  }

  .mps-gender-toggle {
    display: flex;
    gap: 8px;
  }

  .gender-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    font-size: 12px;
    background-color: transparent;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }

  .gender-btn:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .gender-btn.active {
    background-color: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
  }

  /* Latest values table */
  .mps-table {
    width: auto;
    border-collapse: collapse;
    font-size: 14px;
  }

  .mps-table th {
    text-align: left;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    padding: 4px 8px 8px;
    border-bottom: 1px solid var(--border-color);
  }

  .mps-table th.num,
  .mps-table td.num {
    text-align: right;
  }

  .mps-table td {
    padding: 6px 8px;
    border-bottom: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .mps-table tr:last-child td {
    border-bottom: none;
  }

  .mps-table tr.active {
    background: var(--hover-color);
  }

  /* Meta info */
  .mps-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 12px;
  }

  .mps-updated {
    color: var(--text-muted);
  }

  .mps-tier-badge {
    color: var(--text-muted);
    font-weight: 500;
  }

  .mps-low-confidence {
    color: var(--warning-color, #e8a838);
    font-weight: 500;
  }

  /* Chart toggle button */
  .mps-chart-toggle {
    display: flex;
  }

  .mps-chart-btn {
    background: var(--hover-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 13px;
    cursor: pointer;
    transition: background 0.15s;
  }

  .mps-chart-btn:hover {
    background: var(--border-color);
  }

  /* Period selector */
  .mps-period-selector {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  .period-btn {
    background: var(--hover-color);
    color: var(--text-muted);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .period-btn:hover {
    color: var(--text-color);
    background: var(--border-color);
  }

  .period-btn.active {
    background: var(--accent-color);
    color: #fff;
    border-color: var(--accent-color);
  }

  /* Charts grid */
  .mps-charts {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    min-height: 200px;
  }

  .mps-chart-col {
    display: flex;
    flex-direction: column;
    min-height: 180px;
  }

  @media (max-width: 899px) {
    .mps-charts {
      grid-template-columns: 1fr;
    }

    .mps-table {
      font-size: 13px;
    }

    .mps-slot-buttons, .mps-tier-buttons {
      gap: 3px;
    }

    .slot-btn, .tier-btn {
      padding: 3px 8px;
      font-size: 11px;
    }
  }
</style>
