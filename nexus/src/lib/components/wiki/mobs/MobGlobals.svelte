<!--
  @component MobGlobals
  Globals section for a mob detail page — shows activity chart, recent globals, and top globals.
  Self-contained: fetches data on mount, manages its own chart and period selection.
-->
<script>
  import { run } from 'svelte/legacy';

  // @ts-nocheck
  import { onMount, onDestroy, tick } from 'svelte';
  import { Chart, LineController, LinearScale, PointElement, LineElement, TimeScale, Tooltip, Filler } from 'chart.js';
  import 'chartjs-adapter-date-fns';

  Chart.register(LineController, LinearScale, PointElement, LineElement, TimeScale, Tooltip, Filler);

  import { formatPed, formatPedShort, timeAgo, getComputedCssVar, sortedData, toggleSort, sortIcon } from '$lib/utils/globalsFormat.js';
  import GlobalMediaDialog from '$lib/components/globals/GlobalMediaDialog.svelte';
  import GlobalMediaUpload from '$lib/components/globals/GlobalMediaUpload.svelte';

  /**
   * @typedef {Object} Props
   * @property {string} [mobName]
   */

  /** @type {Props} */
  let { mobName = '' } = $props();

  let globalsData = $state(null);
  let loading = $state(false);
  let period = $state('30d');
  let mounted = $state(false);
  let lastLoadedMobName = $state('');
  let refreshTimer = $state(null);
  const REFRESH_INTERVAL = 15000;

  // Chart
  let activityCanvas = $state();
  let activityChart = $state(null);

  // Top section toggle
  let topView = $state('total'); // 'total', 'count', or 'highest'

  // Pagination
  const PAGE_SIZE = 10;
  let topPage = $state(1);
  let recentPage = $state(1);

  // Recent table sort
  let recentSort = $state({ col: 'timestamp', asc: false });

  // Media dialog
  let showMediaDialog = $state(false);
  let mediaDialogGlobal = $state(null);

  function openMediaDialog(g) {
    mediaDialogGlobal = g;
    showMediaDialog = true;
  }

  let summary = $derived(globalsData?.summary || null);
  let activity = $derived(globalsData?.activity || []);
  let topPlayers = $derived(globalsData?.top_players || []);
  let recent = $derived(globalsData?.recent || []);
  let bucketUnit = $derived(globalsData?.bucket_unit || 'day');
  let sortedRecent = $derived(recentSort.col === 'timestamp' && !recentSort.asc ? recent : sortedData(recent, recentSort));

  // Top sorted views
  let topByHighest = $derived([...topPlayers].sort((a, b) => (b.best_value || 0) - (a.best_value || 0)));
  let topByCount = $derived([...topPlayers].sort((a, b) => (b.count || 0) - (a.count || 0)));
  let allTop = $derived(topView === 'total' ? topPlayers
    : topView === 'count' ? topByCount
    : topByHighest);
  let topPages = $derived(Math.ceil(allTop.length / PAGE_SIZE));
  let displayedTop = $derived(allTop.slice((topPage - 1) * PAGE_SIZE, topPage * PAGE_SIZE));

  // Recent pagination
  let recentPages = $derived(Math.ceil(sortedRecent.length / PAGE_SIZE));
  let displayedRecent = $derived(sortedRecent.slice((recentPage - 1) * PAGE_SIZE, recentPage * PAGE_SIZE));

  async function loadGlobalsData() {
    if (!mobName) return;
    loading = true;
    clearInterval(refreshTimer);
    try {
      const params = new URLSearchParams();
      if (period !== 'all') params.set('period', period);
      const res = await fetch(`/api/globals/target/${encodeURIComponent(mobName)}?${params}`);
      if (res.ok) {
        globalsData = await res.json();
        await tick();
        buildActivityChart();
      } else {
        globalsData = null;
      }
    } catch { /* ignore */ }
    loading = false;
    scheduleRefresh();
  }

  /** Lightweight refresh — updates recent globals + summary without rebuilding chart. */
  async function refreshRecent() {
    if (!mobName || !globalsData) return;
    try {
      const params = new URLSearchParams();
      if (period !== 'all') params.set('period', period);
      const res = await fetch(`/api/globals/target/${encodeURIComponent(mobName)}?${params}`);
      if (!res.ok) return;
      const d = await res.json();
      // Update recent and summary only — keep chart stable
      globalsData = { ...globalsData, recent: d.recent, summary: d.summary, top_players: d.top_players };
    } catch { /* ignore */ }
  }

  function scheduleRefresh() {
    clearInterval(refreshTimer);
    refreshTimer = setInterval(refreshRecent, REFRESH_INTERVAL);
  }

  function changePeriod(newPeriod) {
    if (newPeriod === period) return;
    period = newPeriod;
    topPage = 1;
    recentPage = 1;
    loadGlobalsData();
  }

  function buildActivityChart() {
    if (activityChart) {
      activityChart.destroy();
      activityChart = null;
    }
    if (!activityCanvas || !activity.length) return;

    const accentColor = getComputedCssVar('--accent-color') || '#60b0ff';
    const valueColor = '#2ecc71';
    const textMuted = getComputedCssVar('--text-muted') || '#aaa';
    const borderColor = getComputedCssVar('--border-color') || '#555';

    activityChart = new Chart(activityCanvas, {
      type: 'line',
      data: {
        labels: activity.map(a => new Date(a.bucket)),
        datasets: [
          {
            label: 'Count',
            data: activity.map(a => a.count),
            borderColor: accentColor,
            backgroundColor: accentColor + '20',
            borderWidth: 2,
            pointRadius: activity.length < 30 ? 3 : 0,
            pointHoverRadius: 5,
            fill: true,
            tension: 0.1,
            yAxisID: 'y',
          },
          {
            label: 'Value (PED)',
            data: activity.map(a => a.value || 0),
            borderColor: valueColor,
            backgroundColor: valueColor + '20',
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 5,
            fill: false,
            tension: 0.1,
            borderDash: [4, 2],
            yAxisID: 'y1',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: {
            type: 'time',
            time: { unit: bucketUnit },
            ticks: { color: textMuted, maxTicksLimit: 8, font: { size: 11 } },
            grid: { color: borderColor + '30' },
          },
          y: {
            beginAtZero: true,
            position: 'left',
            title: { display: true, text: 'Count', color: textMuted, font: { size: 10 } },
            ticks: { color: textMuted, font: { size: 11 } },
            grid: { color: borderColor + '30' },
          },
          y1: {
            beginAtZero: true,
            position: 'right',
            title: { display: true, text: 'PED', color: textMuted, font: { size: 10 } },
            ticks: { color: textMuted, font: { size: 11 }, callback: v => formatPedShort(v) },
            grid: { display: false },
          },
        },
        plugins: {
          legend: { display: true, labels: { color: textMuted, font: { size: 10 }, usePointStyle: true, pointStyle: 'line' } },
          tooltip: {
            backgroundColor: 'rgba(0,0,0,0.85)',
            borderColor: accentColor,
            borderWidth: 1,
            callbacks: { label: ctx => ctx.dataset.yAxisID === 'y1' ? `Value: ${formatPedShort(ctx.parsed.y)} PED` : `Count: ${ctx.parsed.y}` },
          },
        },
      },
    });
  }

  onMount(() => {
    mounted = true;
    lastLoadedMobName = mobName || '';
    loadGlobalsData();
  });

  // Reload globals when navigating to a different mob within the same page instance.
  run(() => {
    if (mounted && mobName && mobName !== lastLoadedMobName) {
      lastLoadedMobName = mobName;
      globalsData = null;
      topPage = 1;
      recentPage = 1;
      recentSort = { col: 'timestamp', asc: false };
      loadGlobalsData();
    }
  });

  run(() => {
    if (mounted && !mobName && lastLoadedMobName) {
      lastLoadedMobName = '';
      globalsData = null;
      clearInterval(refreshTimer);
      if (activityChart) {
        activityChart.destroy();
        activityChart = null;
      }
    }
  });

  onDestroy(() => {
    clearInterval(refreshTimer);
    if (activityChart) activityChart.destroy();
  });
</script>

<div class="mob-globals">
  <!-- Period selector -->
  <div class="period-row">
    <span class="period-label">Period</span>
    <div class="period-toggle">
      {#each ['24h', '7d', '30d', '90d', '1y', 'all'] as p}
        <button class="period-btn" class:active={period === p} onclick={() => changePeriod(p)}>{p}</button>
      {/each}
    </div>
  </div>

  {#if loading && !globalsData}
    <div class="loading-state"><span class="spinner"></span></div>
  {:else if !summary || summary.total_count === 0}
    <p class="empty-state">No globals recorded for this mob</p>
  {:else}
    <!-- Summary stats row -->
    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-value">{summary.total_count.toLocaleString()}</span>
        <span class="stat-label">Globals</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{formatPed(summary.total_value)} PED</span>
        <span class="stat-label">Total Value</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{formatPed(summary.avg_value)} PED</span>
        <span class="stat-label">Average</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{formatPed(summary.max_value)} PED</span>
        <span class="stat-label">Highest</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{summary.hof_count.toLocaleString()}</span>
        <span class="stat-label">HoF</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{summary.ath_count.toLocaleString()}</span>
        <span class="stat-label">ATH</span>
      </div>
    </div>

    <!-- Activity chart -->
    {#if activity.length > 0}
      <div class="chart-section">
        <h3>Activity</h3>
        <div class="chart-container" class:loading-fade={loading}>
          <canvas bind:this={activityCanvas}></canvas>
        </div>
      </div>
    {/if}

    <!-- Top + Recent grid -->
    <div class="grid-row">
      {#if topPlayers.length > 0}
        <div class="grid-card">
          <div class="card-header">
            <h3>Top Players</h3>
            <div class="view-toggle">
              <button class="toggle-btn" class:active={topView === 'total'} onclick={() => { topView = 'total'; topPage = 1; }}>Total</button>
              <button class="toggle-btn" class:active={topView === 'count'} onclick={() => { topView = 'count'; topPage = 1; }}>Count</button>
              <button class="toggle-btn" class:active={topView === 'highest'} onclick={() => { topView = 'highest'; topPage = 1; }}>Highest</button>
            </div>
          </div>
          <div class="table-wrapper">
            <table class="data-table compact">
              <thead>
                <tr>
                  <th class="col-rank">#</th>
                  <th>Player</th>
                  <th class="right">Count</th>
                  <th class="right">{topView === 'highest' ? 'Best' : 'Total'}</th>
                </tr>
              </thead>
              <tbody>
                {#each displayedTop as p, i}
                  <tr>
                    <td class="col-rank text-muted">{(topPage - 1) * PAGE_SIZE + i + 1}</td>
                    <td>
                      {#if p.is_team}<span class="badge-team">T</span>{/if}
                      <a href="/globals/player/{encodeURIComponent(p.player)}" class="player-link">{p.player}</a>
                    </td>
                    <td class="right">{p.count.toLocaleString()}</td>
                    <td class="right font-mono">{formatPed(topView === 'highest' ? p.best_value : p.value)} PED</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
          {#if topPages > 1}
            <div class="pagination">
              <button class="page-btn" disabled={topPage <= 1} onclick={() => topPage--}>&lsaquo;</button>
              <span class="page-info">{topPage} / {topPages}</span>
              <button class="page-btn" disabled={topPage >= topPages} onclick={() => topPage++}>&rsaquo;</button>
            </div>
          {/if}
        </div>
      {/if}

      {#if recent.length > 0}
        <div class="grid-card">
          <h3>Recent Globals</h3>
          <div class="table-wrapper">
            <table class="data-table compact">
              <thead>
                <tr>
                  <th class="sortable" onclick={() => { recentSort = toggleSort(recentSort, 'player'); recentPage = 1; }}>Player{sortIcon(recentSort, 'player')}</th>
                  <th class="sortable right" onclick={() => { recentSort = toggleSort(recentSort, 'value'); recentPage = 1; }}>Value{sortIcon(recentSort, 'value')}</th>
                  <th></th>
                  <th class="col-media"></th>
                  <th class="sortable" onclick={() => { recentSort = toggleSort(recentSort, 'timestamp'); recentPage = 1; }}>Time{sortIcon(recentSort, 'timestamp')}</th>
                </tr>
              </thead>
              <tbody>
                {#each displayedRecent as g}
                  <tr>
                    <td>
                      {#if g.type === 'team_kill'}<span class="badge-team">T</span>{/if}
                      <a href="/globals/player/{encodeURIComponent(g.player)}" class="player-link">{g.player}</a>
                    </td>
                    <td class="right font-bold">{formatPed(g.value)} PED</td>
                    <td>
                      {#if g.ath}<span class="badge-ath">ATH</span>{:else if g.hof}<span class="badge-hof">HoF</span>{/if}
                    </td>
                    <td class="col-media">
                      {#if g.media_image || g.media_video}
                        <button class="media-icon-btn" title="View media" onclick={() => openMediaDialog(g)}>
                          {#if g.media_image}
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                          {:else}
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                          {/if}
                        </button>
                      {/if}
                    </td>
                    <td class="text-muted">{timeAgo(g.timestamp)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
          {#if recentPages > 1}
            <div class="pagination">
              <button class="page-btn" disabled={recentPage <= 1} onclick={() => recentPage--}>&lsaquo;</button>
              <span class="page-info">{recentPage} / {recentPages}</span>
              <button class="page-btn" disabled={recentPage >= recentPages} onclick={() => recentPage++}>&rsaquo;</button>
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Full details link -->
    <a href="/globals/target/{encodeURIComponent(mobName)}" class="detail-link">View full globals details &rarr;</a>
  {/if}
</div>

<GlobalMediaDialog show={showMediaDialog} global={mediaDialogGlobal} on:close={() => { showMediaDialog = false; mediaDialogGlobal = null; }} />

<style>
  .mob-globals {
    color: var(--text-color);
  }

  /* Period selector */
  .period-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
  }

  .period-label {
    font-size: 0.6875rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    font-weight: 600;
  }

  .period-toggle {
    display: flex;
    gap: 2px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .period-btn {
    padding: 3px 12px;
    font-size: 0.6875rem;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .period-btn.active {
    background: var(--accent-color);
    color: #fff;
  }

  .period-btn:hover:not(.active) {
    color: var(--text-color);
  }

  /* Stats row */
  .stats-row {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 8px;
    margin-bottom: 14px;
  }

  .stat-card {
    padding: 10px 8px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    text-align: center;
  }

  .stat-value {
    display: block;
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-color);
    font-variant-numeric: tabular-nums;
  }

  .stat-label {
    display: block;
    font-size: 0.625rem;
    color: var(--text-muted);
    margin-top: 2px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  /* Chart */
  .chart-section {
    margin-bottom: 14px;
  }

  .chart-section h3 {
    margin: 0 0 8px 0;
    font-size: 0.875rem;
    font-weight: 600;
  }

  .chart-container {
    position: relative;
    height: 160px;
  }

  /* Grid */
  .grid-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 14px;
  }

  .grid-card {
    min-width: 0;
  }

  .grid-card h3 {
    margin: 0 0 8px 0;
    font-size: 0.875rem;
    font-weight: 600;
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .card-header h3 {
    margin: 0;
  }

  .view-toggle {
    display: flex;
    gap: 2px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .toggle-btn {
    padding: 2px 8px;
    font-size: 0.625rem;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .toggle-btn.active {
    background: var(--accent-color);
    color: #fff;
  }

  .toggle-btn:hover:not(.active) {
    color: var(--text-color);
  }

  /* Tables */
  .table-wrapper {
    overflow-x: auto;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
  }

  .data-table.compact th,
  .data-table.compact td {
    padding: 4px 8px;
    font-size: 0.75rem;
  }

  .data-table th {
    text-align: left;
    font-weight: 600;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border-color);
    font-size: 0.6875rem;
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

  .data-table td {
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
  }

  .data-table tr:last-child td {
    border-bottom: none;
  }

  .data-table tr:hover {
    background-color: var(--hover-color);
  }

  .right {
    text-align: right;
  }

  .text-muted {
    color: var(--text-muted);
  }

  .font-bold {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .font-mono {
    font-variant-numeric: tabular-nums;
  }

  .col-rank {
    width: 28px;
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

  /* Badges */
  .badge-hof, .badge-ath, .badge-team {
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.3px;
  }

  .badge-hof { background: rgba(234, 179, 8, 0.15); color: #eab308; }
  .badge-ath { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
  .badge-team { background: rgba(96, 176, 255, 0.15); color: var(--accent-color); margin-right: 3px; }

  /* States */
  .loading-state {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 80px;
  }

  .spinner {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .loading-fade {
    opacity: 0.5;
    pointer-events: none;
    transition: opacity 0.2s ease;
  }

  .empty-state {
    text-align: center;
    padding: 24px;
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  /* Pagination */
  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
  }

  .page-btn {
    padding: 2px 8px;
    font-size: 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
    line-height: 1;
  }

  .page-btn:hover:not(:disabled) {
    border-color: var(--accent-color);
    color: var(--text-color);
  }

  .page-btn:disabled {
    opacity: 0.3;
    cursor: default;
  }

  .page-info {
    font-size: 0.6875rem;
    color: var(--text-muted);
  }

  /* Detail link */
  .detail-link {
    display: inline-block;
    font-size: 0.8125rem;
    color: var(--accent-color);
    text-decoration: none;
  }

  .detail-link:hover {
    text-decoration: underline;
  }

  .col-media {
    width: 28px;
    text-align: center;
  }

  .media-icon-btn {
    background: none;
    border: none;
    color: var(--accent-color);
    cursor: pointer;
    padding: 2px;
    border-radius: 3px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    opacity: 0.7;
    transition: opacity 0.15s;
  }

  .media-icon-btn:hover {
    opacity: 1;
  }

  /* Responsive */
  @media (max-width: 899px) {
    .stats-row {
      grid-template-columns: repeat(3, 1fr);
    }

    .grid-row {
      grid-template-columns: 1fr;
    }
  }
</style>
