<!--
  @component Target Globals Detail Page
  Shows globals for a specific target (mob, resource, crafted item, etc.):
  summary stats, activity chart, top players, and recent globals.
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy, tick } from 'svelte';
  import { Chart, LineController, LinearScale, PointElement, LineElement, TimeScale,
           Tooltip, Filler, BarController, BarElement, CategoryScale } from 'chart.js';
  import 'chartjs-adapter-date-fns';

  Chart.register(LineController, LinearScale, PointElement, LineElement, TimeScale,
                 Tooltip, Filler, BarController, BarElement, CategoryScale);

  import { goto } from '$app/navigation';
  import SearchInput from '$lib/components/SearchInput.svelte';

  export let data;

  $: ({ targetData, targetName } = data);
  $: summary = targetData?.summary;
  $: topPlayers = targetData?.top_players || [];
  $: activity = targetData?.activity || [];
  $: recent = targetData?.recent || [];
  $: primaryType = targetData?.primary_type;

  const TYPE_CONFIG = {
    kill:       { label: 'Hunting',     cssClass: 'type-kill' },
    team_kill:  { label: 'Team Hunt',   cssClass: 'type-kill' },
    deposit:    { label: 'Mining',      cssClass: 'type-deposit' },
    craft:      { label: 'Crafting',    cssClass: 'type-craft' },
    rare_item:  { label: 'Rare Find',   cssClass: 'type-rare' },
    discovery:  { label: 'Discovery',   cssClass: 'type-discovery' },
    tier:       { label: 'Tier Record', cssClass: 'type-tier' },
  };

  // Sorting
  let playerSort = { col: 'value', asc: false };

  function sortedData(arr, sort) {
    return [...arr].sort((a, b) => {
      const va = a[sort.col] ?? 0;
      const vb = b[sort.col] ?? 0;
      if (typeof va === 'string') return sort.asc ? va.localeCompare(vb) : vb.localeCompare(va);
      return sort.asc ? va - vb : vb - va;
    });
  }

  function toggleSort(sortState, col) {
    if (sortState.col === col) {
      sortState.asc = !sortState.asc;
    } else {
      sortState.col = col;
      sortState.asc = false;
    }
    return { ...sortState };
  }

  $: sortedPlayers = sortedData(topPlayers, playerSort);

  // Charts
  let activityCanvas;
  let topPlayersCanvas;
  let activityChart = null;
  let topPlayersChart = null;

  function getComputedCssVar(name) {
    if (typeof getComputedStyle === 'undefined') return null;
    return getComputedStyle(document.documentElement).getPropertyValue(name)?.trim() || null;
  }

  function buildActivityChart() {
    if (!activityCanvas || !activity.length) return;
    if (activityChart) activityChart.destroy();

    const accentColor = getComputedCssVar('--accent-color') || '#60b0ff';
    const textMuted = getComputedCssVar('--text-muted') || '#aaa';
    const borderColor = getComputedCssVar('--border-color') || '#555';

    activityChart = new Chart(activityCanvas, {
      type: 'line',
      data: {
        labels: activity.map(a => new Date(a.bucket)),
        datasets: [{
          label: 'Globals',
          data: activity.map(a => a.count),
          borderColor: accentColor,
          backgroundColor: accentColor + '20',
          borderWidth: 2,
          pointRadius: activity.length < 30 ? 3 : 0,
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
            time: { unit: 'day' },
            ticks: { color: textMuted, maxTicksLimit: 10, font: { size: 11 } },
            grid: { color: borderColor + '30' },
          },
          y: {
            beginAtZero: true,
            ticks: { color: textMuted, font: { size: 11 } },
            grid: { color: borderColor + '30' },
          },
        },
        plugins: { legend: { display: false }, tooltip: { backgroundColor: 'rgba(0,0,0,0.85)' } },
      },
    });
  }

  function buildTopPlayersChart() {
    if (!topPlayersCanvas || !topPlayers.length) return;
    if (topPlayersChart) topPlayersChart.destroy();

    const accentColor = getComputedCssVar('--accent-color') || '#60b0ff';
    const textMuted = getComputedCssVar('--text-muted') || '#aaa';
    const borderColor = getComputedCssVar('--border-color') || '#555';

    const players = topPlayers.slice(0, 8);

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

  async function buildCharts() {
    await tick();
    buildActivityChart();
    buildTopPlayersChart();
  }

  onMount(() => {
    if (targetData) buildCharts();
  });

  onDestroy(() => {
    if (activityChart) activityChart.destroy();
    if (topPlayersChart) topPlayersChart.destroy();
  });

  function timeAgo(dateStr) {
    const now = Date.now();
    const then = new Date(dateStr).getTime();
    const diff = now - then;
    const minutes = Math.floor(diff / 60000);
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

  function formatPed(v) {
    if (v >= 1000) return `${(v / 1000).toFixed(1)}K`;
    return v.toFixed(2);
  }

  function sortIcon(sortState, col) {
    if (sortState.col !== col) return '';
    return sortState.asc ? ' \u25B2' : ' \u25BC';
  }

  function handleSearchSelect(e) {
    const { name, type } = e.detail;
    if (type === 'Player' || type === 'Team') {
      goto(`/globals/player/${encodeURIComponent(name)}`);
    } else {
      goto(`/globals/target/${encodeURIComponent(name)}`);
    }
  }
</script>

<svelte:head>
  <title>{targetName} - Globals - Entropia Nexus</title>
  <meta name="description" content="Global event statistics for {targetName} in Entropia Universe." />
</svelte:head>

<div class="target-page">
  <div class="page-header">
    <div class="header-top">
      <div>
        <div class="breadcrumbs">
          <a href="/">Home</a> / <a href="/globals">Globals</a> / {targetName}
        </div>
        <div class="title-row">
          <h1>{targetName}</h1>
          {#if primaryType}
            {@const tc = TYPE_CONFIG[primaryType]}
            {#if tc}
              <span class="type-badge {tc.cssClass}">{tc.label}</span>
            {/if}
          {/if}
        </div>
        <p class="page-subtitle">Global event statistics</p>
      </div>
      <div class="globals-search">
        <SearchInput
          placeholder="Search players, teams, mobs, resources..."
          endpoint="/api/globals/search"
          apiPrefix={false}
          on:select={handleSearchSelect}
        />
      </div>
    </div>
  </div>

  {#if !targetData || !summary}
    <p class="empty-state">No globals recorded for this target</p>
  {:else}
    <!-- Summary Cards -->
    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-value">{summary.total_count.toLocaleString()}</span>
        <span class="stat-label">Total Globals</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{formatPed(summary.total_value)} PED</span>
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

    <!-- Charts Row -->
    <div class="charts-grid">
      {#if activity.length > 0}
        <div class="section-card chart-wide">
          <h2>Activity</h2>
          <div class="chart-container">
            <canvas bind:this={activityCanvas}></canvas>
          </div>
        </div>
      {/if}

      {#if topPlayers.length > 0}
        <div class="section-card">
          <h2>Top Players (by Value)</h2>
          <div class="chart-container">
            <canvas bind:this={topPlayersCanvas}></canvas>
          </div>
        </div>
      {/if}
    </div>

    <!-- Top Players Table -->
    {#if topPlayers.length > 0}
      <div class="section-card">
        <h2>Players</h2>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th class="sortable" on:click={() => playerSort = toggleSort(playerSort, 'player')}>
                  Player{sortIcon(playerSort, 'player')}
                </th>
                <th class="sortable right" on:click={() => playerSort = toggleSort(playerSort, 'count')}>
                  Count{sortIcon(playerSort, 'count')}
                </th>
                <th class="sortable right" on:click={() => playerSort = toggleSort(playerSort, 'value')}>
                  Total Value{sortIcon(playerSort, 'value')}
                </th>
                <th class="right">Best</th>
              </tr>
            </thead>
            <tbody>
              {#each sortedPlayers as p}
                <tr>
                  <td>
                    <a href="/globals/player/{encodeURIComponent(p.player)}" class="player-link">{p.player}</a>
                  </td>
                  <td class="right">{p.count}</td>
                  <td class="right">{formatPed(p.value)}</td>
                  <td class="right">{formatPed(p.best_value)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <!-- Recent Globals -->
    {#if recent.length > 0}
      <div class="section-card">
        <h2>Recent Globals</h2>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Type</th>
                <th>Player</th>
                <th class="right">Value</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each recent as g}
                {@const tc = TYPE_CONFIG[g.type] || { label: g.type, cssClass: '' }}
                <tr>
                  <td class="text-muted" title={new Date(g.timestamp).toLocaleString()}>{timeAgo(g.timestamp)}</td>
                  <td><span class="type-badge {tc.cssClass}">{tc.label}</span></td>
                  <td>
                    <a href="/globals/player/{encodeURIComponent(g.player)}" class="player-link">{g.player}</a>
                  </td>
                  <td class="right font-weight-bold">{formatValue(g.value, g.unit, g.type)}</td>
                  <td>
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
      </div>
    {/if}
  {/if}
</div>

<style>
  .target-page {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
    color: var(--text-color);
  }

  .page-header {
    margin-bottom: 24px;
  }

  .header-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
  }

  .globals-search {
    flex-shrink: 0;
    width: 300px;
    padding-top: 4px;
  }

  @media (max-width: 600px) {
    .header-top {
      flex-direction: column;
    }
    .globals-search {
      width: 100%;
    }
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

  .title-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 4px;
  }

  h1 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
  }

  .page-subtitle {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  .empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
    font-size: 0.9375rem;
  }

  /* Stats */
  .stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 24px;
  }

  .stat-card {
    padding: 14px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    text-align: center;
  }

  .stat-value {
    display: block;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-color);
    font-variant-numeric: tabular-nums;
  }

  .stat-label {
    display: block;
    font-size: 0.6875rem;
    color: var(--text-muted);
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  /* Charts grid */
  .charts-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-bottom: 16px;
  }

  .chart-wide {
    grid-column: 1 / -1;
  }

  /* Section cards */
  .section-card {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
  }

  .section-card h2 {
    margin: 0 0 12px 0;
    font-size: 1.125rem;
    font-weight: 600;
  }

  .chart-container {
    position: relative;
    height: 200px;
  }

  /* Tables */
  .table-wrapper {
    overflow-x: auto;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8125rem;
  }

  .data-table th {
    padding: 8px 12px;
    text-align: left;
    font-weight: 600;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border-color);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    white-space: nowrap;
  }

  .data-table th.sortable {
    cursor: pointer;
    user-select: none;
  }

  .data-table th.sortable:hover {
    color: var(--text-color);
  }

  .data-table th.right, .data-table td.right {
    text-align: right;
  }

  .data-table td {
    padding: 8px 12px;
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
  }

  .data-table tr:last-child td {
    border-bottom: none;
  }

  .data-table tbody tr:nth-child(even) {
    background-color: var(--table-alt-row, rgba(255, 255, 255, 0.02));
  }

  .data-table tr:hover {
    background-color: var(--hover-color);
  }

  .text-muted {
    color: var(--text-muted);
  }

  .font-weight-bold {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .player-link {
    color: var(--text-color);
    text-decoration: none;
    font-weight: 600;
  }

  .player-link:hover {
    color: var(--accent-color);
    text-decoration: underline;
  }

  /* Type badges */
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

  .badge-hof, .badge-ath {
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.3px;
  }

  .badge-hof { background: rgba(234, 179, 8, 0.15); color: #eab308; }
  .badge-ath { background: rgba(239, 68, 68, 0.2); color: #ef4444; }

  /* Responsive */
  @media (max-width: 899px) {
    .target-page {
      padding: 16px;
    }

    .stats-row {
      grid-template-columns: repeat(2, 1fr);
    }

    .charts-grid {
      grid-template-columns: 1fr;
    }

    .chart-wide {
      grid-column: 1;
    }
  }
</style>
