<!--
  @component Globals Page
  Filterable, live-updating view of all confirmed global events.
  Includes stats cards, activity chart, type distribution, top players/targets, and live table.
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy } from 'svelte';
  import { Chart, LineController, LinearScale, PointElement, LineElement, TimeScale,
           Tooltip, Filler, BarController, BarElement, CategoryScale,
           ArcElement, DoughnutController, Legend } from 'chart.js';
  import 'chartjs-adapter-date-fns';

  Chart.register(LineController, LinearScale, PointElement, LineElement, TimeScale,
                 Tooltip, Filler, BarController, BarElement, CategoryScale,
                 ArcElement, DoughnutController, Legend);

  export let data;

  const EMPTY_SUMMARY = { total_count: 0, total_value: 0, hof_count: 0, ath_count: 0 };

  const TYPE_CONFIG = {
    kill:       { label: 'Hunting',    cssClass: 'type-kill',      color: '#ef4444' },
    team_kill:  { label: 'Team Hunt',  cssClass: 'type-kill',      color: '#ef4444' },
    deposit:    { label: 'Mining',     cssClass: 'type-deposit',   color: '#60b0ff' },
    craft:      { label: 'Crafting',   cssClass: 'type-craft',     color: '#f97316' },
    rare_item:  { label: 'Rare Find',  cssClass: 'type-rare',      color: '#60b0ff' },
    discovery:  { label: 'Discovery',  cssClass: 'type-discovery', color: '#9b59b6' },
    tier:       { label: 'Tier Record', cssClass: 'type-tier',     color: '#f1c40f' },
  };

  const TYPE_FILTERS = [
    { value: '', label: 'All' },
    { value: 'kill,team_kill', label: 'Hunting' },
    { value: 'deposit', label: 'Mining' },
    { value: 'craft', label: 'Crafting' },
    { value: 'rare_item', label: 'Rare Find' },
    { value: 'discovery', label: 'Discovery' },
    { value: 'tier', label: 'Tier Record' },
  ];

  const PERIOD_OPTIONS = [
    { value: '24h', label: '24 Hours' },
    { value: '7d', label: '7 Days' },
    { value: '30d', label: '30 Days' },
    { value: 'all', label: 'All Time' },
  ];

  let globals = [...(data.globals || [])];
  let summary = { ...EMPTY_SUMMARY, ...(data.summary || {}) };

  // Filters
  let typeFilter = '';
  let playerFilter = '';
  let targetFilter = '';
  let minValue = '';
  let hofOnly = false;
  let period = '7d';

  // Charts
  let activityCanvas;
  let typeCanvas;
  let topPlayersCanvas;
  let topTargetsCanvas;
  let activityChart = null;
  let typeChart = null;
  let topPlayersChart = null;
  let topTargetsChart = null;

  // Stats data
  let stats = null;
  let statsLoading = false;

  // Live table
  let pollTimer = null;
  let latestTimestamp = globals.length > 0 ? globals[0].timestamp : null;
  let loadingMore = false;
  let hasMore = globals.length >= 50;
  let newIds = new Set();

  const POLL_INTERVAL = 5000;

  function timeAgo(dateStr) {
    const now = Date.now();
    const then = new Date(dateStr).getTime();
    const diff = now - then;
    const seconds = Math.floor(diff / 1000);
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  function formatValue(value, unit, type) {
    if (type === 'discovery') return '';
    if (type === 'tier' && unit === 'TIER') return `Tier ${value}`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K PED`;
    return `${value.toFixed(2)} PED`;
  }

  function formatPedShort(value) {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
    return value.toFixed(0);
  }

  function getComputedCssVar(name) {
    if (typeof getComputedStyle === 'undefined') return null;
    return getComputedStyle(document.documentElement).getPropertyValue(name)?.trim() || null;
  }

  // Build filter query params
  function buildParams(extra = {}) {
    const params = new URLSearchParams();
    if (typeFilter) params.set('type', typeFilter);
    if (playerFilter) params.set('player', playerFilter);
    if (targetFilter) params.set('target', targetFilter);
    if (minValue) params.set('min_value', minValue);
    if (hofOnly) params.set('hof', 'true');
    for (const [k, v] of Object.entries(extra)) {
      params.set(k, String(v));
    }
    return params;
  }

  // Fetch filtered globals
  async function fetchGlobals() {
    try {
      const params = buildParams({ limit: 50 });
      const res = await fetch(`/api/globals?${params}`);
      if (!res.ok) return;
      const data = await res.json();
      globals = data.globals;
      hasMore = data.has_more;
      latestTimestamp = globals.length > 0 ? globals[0].timestamp : null;
    } catch { /* ignore */ }
  }

  // Fetch stats
  async function fetchStats() {
    statsLoading = true;
    try {
      const params = new URLSearchParams({ period });
      if (typeFilter) params.set('type', typeFilter);
      if (playerFilter) params.set('player', playerFilter);
      const res = await fetch(`/api/globals/stats?${params}`);
      if (!res.ok) return;
      stats = await res.json();
      buildCharts();
    } catch { /* ignore */ }
    statsLoading = false;
  }

  // Load more (cursor pagination)
  async function loadMore() {
    if (loadingMore || !hasMore || globals.length === 0) return;
    loadingMore = true;
    try {
      const lastTs = globals[globals.length - 1].timestamp;
      const params = buildParams({ limit: 50, before: lastTs });
      const res = await fetch(`/api/globals?${params}`);
      if (!res.ok) return;
      const data = await res.json();
      globals = [...globals, ...data.globals];
      hasMore = data.has_more;
    } catch { /* ignore */ }
    loadingMore = false;
  }

  // Poll for new entries
  async function poll() {
    if (!latestTimestamp) return;
    try {
      const params = buildParams({ since: latestTimestamp, limit: 20 });
      const res = await fetch(`/api/globals?${params}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.globals && data.globals.length > 0) {
        const incoming = data.globals.filter(g =>
          !globals.some(existing => existing.id === g.id)
        );
        for (const g of incoming) newIds.add(g.id);
        globals = [...incoming, ...globals];
        latestTimestamp = globals[0].timestamp;
        if (incoming.length > 0) {
          setTimeout(() => { newIds = new Set(); }, 600);
        }
      }
    } catch { /* ignore */ }
  }

  // Apply filters
  let filterDebounce = null;
  function onFilterChange() {
    clearTimeout(filterDebounce);
    filterDebounce = setTimeout(() => {
      fetchGlobals();
      fetchStats();
    }, 300);
  }

  function onTypeFilter(val) {
    typeFilter = val;
    onFilterChange();
  }

  function onPeriodChange() {
    fetchStats();
  }

  // Charts
  function buildCharts() {
    if (!stats) return;
    const textMuted = getComputedCssVar('--text-muted') || '#aaa';
    const borderColor = getComputedCssVar('--border-color') || '#555';

    buildActivityChart(textMuted, borderColor);
    buildTypeChart();
    buildTopPlayersChart(textMuted, borderColor);
    buildTopTargetsChart(textMuted, borderColor);
  }

  function buildActivityChart(textMuted, borderColor) {
    if (!activityCanvas || !stats?.activity?.length) return;
    if (activityChart) activityChart.destroy();

    const accentColor = getComputedCssVar('--accent-color') || '#60b0ff';

    activityChart = new Chart(activityCanvas, {
      type: 'line',
      data: {
        labels: stats.activity.map(a => new Date(a.bucket)),
        datasets: [{
          label: 'Globals',
          data: stats.activity.map(a => a.count),
          borderColor: accentColor,
          backgroundColor: accentColor + '20',
          borderWidth: 2,
          pointRadius: stats.activity.length < 30 ? 3 : 0,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.3,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            type: 'time',
            time: { unit: period === '24h' ? 'hour' : 'day' },
            ticks: { color: textMuted, maxTicksLimit: 8, font: { size: 11 } },
            grid: { color: borderColor + '30' },
          },
          y: {
            beginAtZero: true,
            ticks: { color: textMuted, font: { size: 11 } },
            grid: { color: borderColor + '30' },
          },
        },
        plugins: { legend: { display: false }, tooltip: { backgroundColor: 'rgba(0,0,0,0.85)', borderColor: accentColor, borderWidth: 1 } },
      },
    });
  }

  function buildTypeChart() {
    if (!typeCanvas || !stats?.by_type?.length) return;
    if (typeChart) typeChart.destroy();

    const types = stats.by_type;
    const colors = types.map(t => TYPE_CONFIG[t.type]?.color || '#888');

    typeChart = new Chart(typeCanvas, {
      type: 'doughnut',
      data: {
        labels: types.map(t => TYPE_CONFIG[t.type]?.label || t.type),
        datasets: [{
          data: types.map(t => t.count),
          backgroundColor: colors.map(c => c + '30'),
          borderColor: colors,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: { color: getComputedCssVar('--text-color') || '#fff', font: { size: 11 }, padding: 12 },
          },
        },
      },
    });
  }

  function buildTopPlayersChart(textMuted, borderColor) {
    if (!topPlayersCanvas || !stats?.top_players?.length) return;
    if (topPlayersChart) topPlayersChart.destroy();

    const accentColor = getComputedCssVar('--accent-color') || '#60b0ff';
    const players = stats.top_players.slice(0, 8);

    topPlayersChart = new Chart(topPlayersCanvas, {
      type: 'bar',
      data: {
        labels: players.map(p => p.player.length > 18 ? p.player.slice(0, 16) + '...' : p.player),
        datasets: [{
          label: 'Total Value (PED)',
          data: players.map(p => p.value),
          backgroundColor: accentColor + '40',
          borderColor: accentColor,
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        scales: {
          x: { ticks: { color: textMuted, font: { size: 11 } }, grid: { color: borderColor + '30' } },
          y: { ticks: { color: textMuted, font: { size: 11 } }, grid: { display: false } },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  function buildTopTargetsChart(textMuted, borderColor) {
    if (!topTargetsCanvas || !stats?.top_targets?.length) return;
    if (topTargetsChart) topTargetsChart.destroy();

    const targets = stats.top_targets.slice(0, 8);

    topTargetsChart = new Chart(topTargetsCanvas, {
      type: 'bar',
      data: {
        labels: targets.map(t => t.target.length > 18 ? t.target.slice(0, 16) + '...' : t.target),
        datasets: [{
          label: 'Kill Count',
          data: targets.map(t => t.count),
          backgroundColor: '#ef444440',
          borderColor: '#ef4444',
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        scales: {
          x: { ticks: { color: textMuted, font: { size: 11 } }, grid: { color: borderColor + '30' } },
          y: { ticks: { color: textMuted, font: { size: 11 } }, grid: { display: false } },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  onMount(() => {
    fetchStats();
    pollTimer = setInterval(poll, POLL_INTERVAL);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
    if (activityChart) activityChart.destroy();
    if (typeChart) typeChart.destroy();
    if (topPlayersChart) topPlayersChart.destroy();
    if (topTargetsChart) topTargetsChart.destroy();
  });

  function getTypeConfig(type) {
    return TYPE_CONFIG[type] || { label: type, cssClass: '', color: '#888' };
  }
</script>

<svelte:head>
  <title>Globals - Entropia Nexus</title>
  <meta name="description" content="Live global events from Entropia Universe. Track hunting, mining, crafting globals, HoF and ATH records." />
</svelte:head>

<div class="globals-page">
  <div class="page-header">
    <div class="breadcrumbs"><a href="/">Home</a> / Globals</div>
    <h1>Globals</h1>
    <p class="page-subtitle">Live global events from Entropia Universe</p>
  </div>

  <!-- Filters -->
  <div class="filters-bar">
    <div class="type-filters">
      {#each TYPE_FILTERS as tf}
        <button
          class="type-btn"
          class:active={typeFilter === tf.value}
          on:click={() => onTypeFilter(tf.value)}
        >
          {tf.label}
        </button>
      {/each}
    </div>
    <div class="text-filters">
      <input type="text" placeholder="Player / Team..." bind:value={playerFilter} on:input={onFilterChange} class="filter-input" />
      <input type="text" placeholder="Target..." bind:value={targetFilter} on:input={onFilterChange} class="filter-input" />
      <input type="number" placeholder="Min PED" bind:value={minValue} on:input={onFilterChange} class="filter-input filter-input-short" />
      <label class="hof-toggle">
        <input type="checkbox" bind:checked={hofOnly} on:change={onFilterChange} />
        HoF only
      </label>
    </div>
  </div>

  <!-- Stats Cards -->
  <div class="stats-row">
    <div class="stat-card">
      <span class="stat-value">{summary.total_count.toLocaleString()}</span>
      <span class="stat-label">Total Globals</span>
    </div>
    <div class="stat-card">
      <span class="stat-value">{formatPedShort(summary.total_value)} PED</span>
      <span class="stat-label">Total Value</span>
    </div>
    <div class="stat-card">
      <span class="stat-value">{summary.hof_count.toLocaleString()}</span>
      <span class="stat-label">Hall of Fame</span>
    </div>
    <div class="stat-card">
      <span class="stat-value">{summary.ath_count.toLocaleString()}</span>
      <span class="stat-label">All-Time Highs</span>
    </div>
  </div>

  <!-- Charts -->
  <div class="charts-section">
    <div class="chart-header">
      <h2>Statistics</h2>
      <div class="period-selector">
        {#each PERIOD_OPTIONS as p}
          <button
            class="period-btn"
            class:active={period === p.value}
            on:click={() => { period = p.value; onPeriodChange(); }}
          >
            {p.label}
          </button>
        {/each}
      </div>
    </div>

    <div class="charts-grid">
      <div class="chart-card chart-wide">
        <h3>Activity Timeline</h3>
        <div class="chart-container">
          <canvas bind:this={activityCanvas}></canvas>
        </div>
      </div>

      <div class="chart-card">
        <h3>Type Distribution</h3>
        <div class="chart-container chart-square">
          <canvas bind:this={typeCanvas}></canvas>
        </div>
      </div>

      <div class="chart-card">
        <h3>Top Players (by Value)</h3>
        <div class="chart-container">
          <canvas bind:this={topPlayersCanvas}></canvas>
        </div>
      </div>

      <div class="chart-card">
        <h3>Top Targets (by Count)</h3>
        <div class="chart-container">
          <canvas bind:this={topTargetsCanvas}></canvas>
        </div>
      </div>
    </div>
  </div>

  <!-- Live Table -->
  <div class="table-section">
    <h2>Recent Globals</h2>

    {#if globals.length === 0}
      <p class="empty-state">No globals match your filters</p>
    {:else}
      <div class="table-wrapper">
        <table class="globals-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Type</th>
              <th>Player</th>
              <th>Target</th>
              <th class="right">Value</th>
              <th>Location</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each globals as g (g.id)}
              {@const tc = getTypeConfig(g.type)}
              <tr class:row-new={newIds.has(g.id)}>
                <td class="col-time" title={new Date(g.timestamp).toLocaleString()}>{timeAgo(g.timestamp)}</td>
                <td><span class="type-badge {tc.cssClass}">{tc.label}</span></td>
                <td>
                  <a href="/globals/player/{encodeURIComponent(g.player)}" class="player-link">{g.player}</a>
                </td>
                <td class="col-target">{g.target}</td>
                <td class="right col-value">{formatValue(g.value, g.unit, g.type)}</td>
                <td class="col-location">{g.location || ''}</td>
                <td class="col-badges">
                  {#if g.ath}
                    <span class="badge-ath">ATH</span>
                  {:else if g.hof}
                    <span class="badge-hof">HoF</span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if hasMore}
        <div class="load-more">
          <button class="load-more-btn" on:click={loadMore} disabled={loadingMore}>
            {loadingMore ? 'Loading...' : 'Load more'}
          </button>
        </div>
      {/if}
    {/if}
  </div>
</div>

<style>
  .globals-page {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
    color: var(--text-color);
  }

  .page-header {
    margin-bottom: 24px;
  }

  .breadcrumbs {
    font-size: 0.8125rem;
    color: var(--text-muted);
    margin-bottom: 8px;
  }

  .breadcrumbs a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumbs a:hover {
    text-decoration: underline;
  }

  h1 {
    margin: 0 0 4px 0;
    font-size: 1.5rem;
    font-weight: 600;
  }

  .page-subtitle {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  /* Filters */
  .filters-bar {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 20px;
    padding: 16px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }

  .type-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .type-btn {
    padding: 6px 14px;
    font-size: 0.8125rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .type-btn:hover {
    border-color: var(--accent-color);
    color: var(--text-color);
  }

  .type-btn.active {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: #fff;
  }

  .text-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }

  .filter-input {
    padding: 6px 10px;
    font-size: 0.8125rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--primary-color);
    color: var(--text-color);
    min-width: 140px;
  }

  .filter-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .filter-input-short {
    min-width: 80px;
    max-width: 100px;
  }

  .hof-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.8125rem;
    color: var(--text-muted);
    cursor: pointer;
  }

  .hof-toggle input {
    cursor: pointer;
  }

  /* Stats Cards */
  .stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 24px;
  }

  .stat-card {
    padding: 16px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    text-align: center;
  }

  .stat-value {
    display: block;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-color);
    font-variant-numeric: tabular-nums;
  }

  .stat-label {
    display: block;
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  /* Charts */
  .charts-section {
    margin-bottom: 24px;
  }

  .chart-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .chart-header h2 {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
  }

  .period-selector {
    display: flex;
    gap: 4px;
  }

  .period-btn {
    padding: 4px 12px;
    font-size: 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
  }

  .period-btn:hover {
    border-color: var(--accent-color);
    color: var(--text-color);
  }

  .period-btn.active {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: #fff;
  }

  .charts-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }

  .chart-card {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 16px;
  }

  .chart-card.chart-wide {
    grid-column: 1 / -1;
  }

  .chart-card h3 {
    margin: 0 0 12px 0;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-muted);
  }

  .chart-container {
    position: relative;
    height: 200px;
  }

  .chart-container.chart-square {
    height: 220px;
  }

  /* Table */
  .table-section {
    margin-bottom: 40px;
  }

  .table-section h2 {
    margin: 0 0 12px 0;
    font-size: 1.125rem;
    font-weight: 600;
  }

  .empty-state {
    text-align: center;
    padding: 40px;
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  .table-wrapper {
    overflow-x: auto;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background: var(--secondary-color);
  }

  .globals-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8125rem;
  }

  .globals-table th {
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .globals-table th.right {
    text-align: right;
  }

  .globals-table td {
    padding: 8px 14px;
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
  }

  .globals-table tr:last-child td {
    border-bottom: none;
  }

  .globals-table tr:hover {
    background-color: var(--hover-color);
  }

  .globals-table tr.row-new {
    animation: row-fade-in 0.4s ease-out;
    background-color: rgba(59, 130, 246, 0.06);
  }

  @keyframes row-fade-in {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .col-time {
    color: var(--text-muted);
    min-width: 70px;
  }

  .type-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .type-kill     { background: rgba(239, 68, 68, 0.15);  color: #ef4444; }
  .type-deposit  { background: rgba(59, 130, 246, 0.15); color: #60b0ff; }
  .type-craft    { background: rgba(249, 115, 22, 0.15); color: #f97316; }
  .type-rare     { background: rgba(96, 176, 255, 0.15); color: var(--accent-color); }
  .type-discovery { background: rgba(155, 89, 182, 0.15); color: #9b59b6; }
  .type-tier     { background: rgba(241, 196, 15, 0.15); color: #f1c40f; }

  .player-link {
    color: var(--text-color);
    text-decoration: none;
    font-weight: 600;
  }

  .player-link:hover {
    color: var(--accent-color);
    text-decoration: underline;
  }

  .col-target {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .col-value {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .right {
    text-align: right;
  }

  .col-location {
    color: var(--text-muted);
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .col-badges {
    min-width: 32px;
  }

  .badge-hof, .badge-ath {
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.3px;
  }

  .badge-hof {
    background: rgba(234, 179, 8, 0.15);
    color: #eab308;
  }

  .badge-ath {
    background: rgba(239, 68, 68, 0.2);
    color: #ef4444;
  }

  .load-more {
    display: flex;
    justify-content: center;
    margin-top: 12px;
  }

  .load-more-btn {
    padding: 8px 24px;
    font-size: 0.8125rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .load-more-btn:hover:not(:disabled) {
    border-color: var(--accent-color);
    color: var(--text-color);
  }

  .load-more-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  /* Responsive */
  @media (max-width: 899px) {
    .globals-page {
      padding: 16px;
    }

    .stats-row {
      grid-template-columns: repeat(2, 1fr);
    }

    .charts-grid {
      grid-template-columns: 1fr;
    }

    .chart-card.chart-wide {
      grid-column: 1;
    }
  }

  @media (max-width: 599px) {
    .stats-row {
      grid-template-columns: 1fr 1fr;
    }

    .filter-input {
      min-width: 100px;
      flex: 1;
    }

    .globals-table th:nth-child(6),
    .globals-table td:nth-child(6) {
      display: none;
    }
  }
</style>
