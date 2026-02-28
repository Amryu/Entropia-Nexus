<!--
  @component Player Globals Detail Page
  Shows a player's globals breakdown: hunting (per-mob with maturities),
  mining (per-resource), crafting (per-item), achievements, activity chart, and recent globals.
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy, tick } from 'svelte';
  import { Chart, LineController, LinearScale, PointElement, LineElement, TimeScale,
           Tooltip, Filler, CategoryScale } from 'chart.js';
  import 'chartjs-adapter-date-fns';

  Chart.register(LineController, LinearScale, PointElement, LineElement, TimeScale,
                 Tooltip, Filler, CategoryScale);

  import { goto } from '$app/navigation';
  import SearchInput from '$lib/components/SearchInput.svelte';

  export let data;

  let playerData = data.playerData;
  let playerName = data.playerName;
  $: summary = playerData?.summary;
  $: hunting = playerData?.hunting || [];
  $: mining = playerData?.mining?.resources || [];
  $: crafting = playerData?.crafting?.items || [];
  $: activity = playerData?.activity || [];
  $: recent = playerData?.recent || [];
  $: achievements = playerData?.achievements || [];

  const PERIOD_OPTIONS = [
    { value: '24h', label: '24 Hours' },
    { value: '7d', label: '7 Days' },
    { value: '30d', label: '30 Days' },
    { value: 'all', label: 'All Time' },
  ];

  let period = 'all';
  let loading = false;

  async function fetchData() {
    loading = true;
    try {
      const params = new URLSearchParams();
      if (period !== 'all') params.set('period', period);
      const qs = params.toString();
      const res = await fetch(`/api/globals/player/${encodeURIComponent(playerName)}${qs ? '?' + qs : ''}`);
      if (res.ok) {
        playerData = await res.json();
      }
    } catch { /* ignore */ }
    loading = false;
    await tick();
    buildActivityChart();
  }

  const TYPE_CONFIG = {
    kill:       { label: 'Hunting',     cssClass: 'type-kill' },
    team_kill:  { label: 'Team Hunt',   cssClass: 'type-kill' },
    deposit:    { label: 'Mining',      cssClass: 'type-deposit' },
    craft:      { label: 'Crafting',    cssClass: 'type-craft' },
    rare_item:  { label: 'Rare Find',   cssClass: 'type-rare' },
    discovery:  { label: 'Discovery',   cssClass: 'type-discovery' },
    tier:       { label: 'Tier Record', cssClass: 'type-tier' },
    examine:    { label: 'Examined',    cssClass: 'type-examine' },
    pvp:        { label: 'PvP',         cssClass: 'type-pvp' },
  };

  // Expanded mobs (for maturity detail rows)
  let expandedMobs = new Set();

  function toggleMob(key) {
    if (expandedMobs.has(key)) {
      expandedMobs.delete(key);
    } else {
      expandedMobs.add(key);
    }
    expandedMobs = new Set(expandedMobs);
  }

  // Sorting
  let huntSort = { col: 'total_value', asc: false };
  let miningSort = { col: 'total_value', asc: false };
  let craftSort = { col: 'total_value', asc: false };

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

  $: sortedHunting = sortedData(hunting, huntSort);
  $: sortedMining = sortedData(mining, miningSort);
  $: sortedCrafting = sortedData(crafting, craftSort);

  // Activity chart
  let activityCanvas;
  let activityChart = null;

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

    // Aggregate by day (activity has type breakdowns, merge them)
    const dayMap = new Map();
    for (const a of activity) {
      const day = new Date(a.bucket).toISOString().slice(0, 10);
      dayMap.set(day, (dayMap.get(day) || 0) + a.count);
    }
    const sorted = [...dayMap.entries()].sort((a, b) => a[0].localeCompare(b[0]));

    activityChart = new Chart(activityCanvas, {
      type: 'line',
      data: {
        labels: sorted.map(([d]) => new Date(d)),
        datasets: [{
          label: 'Globals',
          data: sorted.map(([, c]) => c),
          borderColor: accentColor,
          backgroundColor: accentColor + '20',
          borderWidth: 2,
          pointRadius: sorted.length < 30 ? 3 : 0,
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

  onMount(() => {
    if (playerData) buildActivityChart();
  });

  onDestroy(() => {
    if (activityChart) activityChart.destroy();
  });

  $: if (activityCanvas && activity.length) buildActivityChart();

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
    if (type === 'pvp') return `${value} kills`;
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
  <title>{playerName} - Globals - Entropia Nexus</title>
  <meta name="description" content="Global event statistics for {playerName} in Entropia Universe." />
</svelte:head>

<div class="player-page">
  <div class="page-header">
    <div class="header-top">
      <div>
        <div class="breadcrumbs">
          <a href="/">Home</a> / <a href="/globals">Globals</a> / {playerName}
        </div>
        <h1>{playerName}</h1>
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

  {#if !playerData || !summary}
    <p class="empty-state">No globals recorded for this player</p>
  {:else}
    <!-- Period Selector -->
    <div class="period-selector">
      {#each PERIOD_OPTIONS as p}
        <button
          class="period-btn"
          class:active={period === p.value}
          disabled={loading}
          on:click={() => { period = p.value; fetchData(); }}
        >
          {p.label}
        </button>
      {/each}
    </div>

    <!-- Summary Cards -->
    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-value">{summary.total_count}</span>
        <span class="stat-label">Total Globals</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{formatPed(summary.total_value)} PED</span>
        <span class="stat-label">Total Value</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{summary.hof_count}</span>
        <span class="stat-label">Hall of Fame</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{summary.kill_count + summary.team_kill_count}</span>
        <span class="stat-label">Hunting</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{summary.deposit_count}</span>
        <span class="stat-label">Mining</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{summary.craft_count}</span>
        <span class="stat-label">Crafting</span>
      </div>
    </div>

    <!-- Activity Chart -->
    {#if activity.length > 0}
      <div class="section-card">
        <h2>Activity</h2>
        <div class="chart-container">
          <canvas bind:this={activityCanvas}></canvas>
        </div>
      </div>
    {/if}

    <!-- Hunting -->
    {#if hunting.length > 0}
      <div class="section-card">
        <h2>Hunting</h2>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th class="sortable" on:click={() => huntSort = toggleSort(huntSort, 'target')}>
                  Target{sortIcon(huntSort, 'target')}
                </th>
                <th class="sortable right" on:click={() => huntSort = toggleSort(huntSort, 'kills')}>
                  Kills{sortIcon(huntSort, 'kills')}
                </th>
                <th class="sortable right" on:click={() => huntSort = toggleSort(huntSort, 'total_value')}>
                  Total Value{sortIcon(huntSort, 'total_value')}
                </th>
                <th class="right">Avg</th>
                <th class="right">Best</th>
              </tr>
            </thead>
            <tbody>
              {#each sortedHunting as mob, i}
                {@const mobKey = mob.mob_id || mob.target || i}
                {@const hasDetails = mob.maturities && mob.maturities.length > 1}
                <tr
                  class="mob-row"
                  class:expandable={hasDetails}
                  on:click={() => hasDetails && toggleMob(mobKey)}
                >
                  <td>
                    {#if hasDetails}
                      <span class="expand-icon">{expandedMobs.has(mobKey) ? '\u25BC' : '\u25B6'}</span>
                    {/if}
                    {mob.target}
                  </td>
                  <td class="right">{mob.kills}</td>
                  <td class="right">{formatPed(mob.total_value)}</td>
                  <td class="right">{formatPed(mob.avg_value)}</td>
                  <td class="right">{formatPed(mob.best_value)}</td>
                </tr>
                {#if hasDetails && expandedMobs.has(mobKey)}
                  {#each mob.maturities as mat}
                    <tr class="maturity-row">
                      <td class="indent">{mat.target}</td>
                      <td class="right">{mat.kills}</td>
                      <td class="right">{formatPed(mat.total_value)}</td>
                      <td class="right">{formatPed(mat.avg_value)}</td>
                      <td class="right">{formatPed(mat.best_value)}</td>
                    </tr>
                  {/each}
                {/if}
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <!-- Mining -->
    {#if mining.length > 0}
      <div class="section-card">
        <h2>Mining</h2>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th class="sortable" on:click={() => miningSort = toggleSort(miningSort, 'target')}>
                  Resource{sortIcon(miningSort, 'target')}
                </th>
                <th class="sortable right" on:click={() => miningSort = toggleSort(miningSort, 'finds')}>
                  Finds{sortIcon(miningSort, 'finds')}
                </th>
                <th class="sortable right" on:click={() => miningSort = toggleSort(miningSort, 'total_value')}>
                  Total Value{sortIcon(miningSort, 'total_value')}
                </th>
                <th class="right">Avg</th>
                <th class="right">Best</th>
              </tr>
            </thead>
            <tbody>
              {#each sortedMining as res}
                <tr>
                  <td>{res.target}</td>
                  <td class="right">{res.finds}</td>
                  <td class="right">{formatPed(res.total_value)}</td>
                  <td class="right">{formatPed(res.avg_value)}</td>
                  <td class="right">{formatPed(res.best_value)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <!-- Crafting -->
    {#if crafting.length > 0}
      <div class="section-card">
        <h2>Crafting</h2>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th class="sortable" on:click={() => craftSort = toggleSort(craftSort, 'target')}>
                  Item{sortIcon(craftSort, 'target')}
                </th>
                <th class="sortable right" on:click={() => craftSort = toggleSort(craftSort, 'crafts')}>
                  Crafts{sortIcon(craftSort, 'crafts')}
                </th>
                <th class="sortable right" on:click={() => craftSort = toggleSort(craftSort, 'total_value')}>
                  Total Value{sortIcon(craftSort, 'total_value')}
                </th>
                <th class="right">Avg</th>
                <th class="right">Best</th>
              </tr>
            </thead>
            <tbody>
              {#each sortedCrafting as item}
                <tr>
                  <td>{item.target}</td>
                  <td class="right">{item.crafts}</td>
                  <td class="right">{formatPed(item.total_value)}</td>
                  <td class="right">{formatPed(item.avg_value)}</td>
                  <td class="right">{formatPed(item.best_value)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <!-- Achievements (Discovery + Tier) -->
    {#if achievements.length > 0}
      <div class="section-card">
        <h2>Achievements</h2>
        <div class="achievements-list">
          {#each achievements as ach}
            <div class="achievement-item">
              <span class="type-badge {TYPE_CONFIG[ach.type]?.cssClass || ''}">
                {TYPE_CONFIG[ach.type]?.label || ach.type}
              </span>
              <span class="achievement-target">{ach.target}</span>
              {#if ach.type === 'tier' && ach.extra?.tier}
                <span class="achievement-detail">Tier {ach.extra.tier}</span>
              {/if}
              <span class="achievement-time">{timeAgo(ach.timestamp)}</span>
            </div>
          {/each}
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
                <th>Target</th>
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
                  <td>{g.target}</td>
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
  .period-selector {
    display: flex;
    gap: 4px;
    margin-bottom: 16px;
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

  .period-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .player-page {
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

  .empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
    font-size: 0.9375rem;
  }

  /* Stats */
  .stats-row {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
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

  .mob-row.expandable {
    cursor: pointer;
  }

  .expand-icon {
    font-size: 0.625rem;
    margin-right: 6px;
    color: var(--text-muted);
  }

  .maturity-row td {
    color: var(--text-muted);
    font-size: 0.75rem;
  }

  .indent {
    padding-left: 28px !important;
  }

  .text-muted {
    color: var(--text-muted);
  }

  .font-weight-bold {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
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
  .type-examine  { background: rgba(46, 204, 113, 0.15); color: #2ecc71; }
  .type-pvp      { background: rgba(231, 76, 60, 0.15);  color: #e74c3c; }

  .badge-hof, .badge-ath {
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.3px;
  }

  .badge-hof { background: rgba(234, 179, 8, 0.15); color: #eab308; }
  .badge-ath { background: rgba(239, 68, 68, 0.2); color: #ef4444; }

  /* Achievements */
  .achievements-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .achievement-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 0.8125rem;
  }

  .achievement-target {
    flex: 1;
    font-weight: 600;
  }

  .achievement-detail {
    color: var(--text-muted);
    font-size: 0.75rem;
  }

  .achievement-time {
    color: var(--text-muted);
    font-size: 0.75rem;
  }

  /* Responsive */
  @media (max-width: 899px) {
    .player-page {
      padding: 16px;
    }

    .stats-row {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  @media (max-width: 599px) {
    .stats-row {
      grid-template-columns: repeat(2, 1fr);
    }
  }
</style>
