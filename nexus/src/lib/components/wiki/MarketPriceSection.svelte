<!--
  @component MarketPriceSection
  Self-contained market price display for wiki item pages.
  Fetches data client-side and shows a table of latest values
  plus historical markup/sales charts with period selection.
-->
<script>
  //@ts-nocheck
  import { onMount } from 'svelte';
  import { createEventDispatcher } from 'svelte';
  import DataSection from './DataSection.svelte';
  import MarketPriceChart from './MarketPriceChart.svelte';

  const dispatch = createEventDispatcher();

  /** @type {number|null} Item ID from the Items table */
  export let itemId = null;

  /** @type {string|null} Item name — fallback for unresolved items */
  export let itemName = null;

  /** @type {boolean} Expand/collapse state */
  export let expanded = true;

  const PERIODS = [
    { key: '1d', label: '1 Day' },
    { key: '7d', label: '7 Days' },
    { key: '30d', label: '30 Days' },
    { key: '365d', label: '1 Year' },
    { key: '3650d', label: '10 Years' }
  ];

  let snapshot = null;
  let loading = true;
  let historyData = [];
  let historyLoading = false;
  let historyLoaded = false;
  let selectedPeriod = '30d';
  let showCharts = false;

  function toggleSection() {
    dispatch('toggle', { expanded });
  }

  async function fetchLatest(id, name) {
    loading = true;
    snapshot = null;
    historyData = [];
    historyLoaded = false;
    showCharts = false;

    try {
      if (id) {
        const res = await fetch(`/api/market/prices/snapshots/latest?itemIds=${id}`);
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
        const res = await fetch(`/api/market/prices/snapshots/latest?name=${encodeURIComponent(name)}`);
        if (res.ok) {
          const rows = await res.json();
          if (rows.length > 0) {
            snapshot = rows[0];
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
      const res = await fetch(`/api/market/prices/snapshots/${id}?limit=750`);
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
    if (val == null) return '—';
    return `${Number(val).toFixed(2)}%`;
  }

  function formatSales(val) {
    if (val == null) return '—';
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

  // Reactive: fetch when itemId/itemName changes
  $: if (itemId || itemName) {
    fetchLatest(itemId, itemName);
  }
</script>

<DataSection title="Market Prices" bind:expanded on:toggle={toggleSection}>
  <div class="mps-content">
    {#if loading}
      <div class="mps-loading">Loading market prices...</div>
    {:else if !snapshot}
      <div class="mps-empty">No market price data available</div>
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
        {#if snapshot.confidence != null && snapshot.confidence < 0.5}
          <span class="mps-low-confidence" title="Low confidence — few submissions">Low confidence</span>
        {/if}
      </div>

      <div class="mps-chart-toggle">
        <button class="mps-chart-btn" on:click={toggleCharts}>
          {showCharts ? 'Hide Charts' : 'Show Price History'}
        </button>
      </div>

      {#if showCharts}
        <div class="mps-period-selector">
          {#each PERIODS as { key, label }}
            <button
              class="period-btn"
              class:active={selectedPeriod === key}
              on:click={() => selectPeriod(key)}
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

  /* Latest values table */
  .mps-table {
    width: 100%;
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
  }
</style>
