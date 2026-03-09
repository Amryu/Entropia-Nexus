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
  import GlobalsDateRangePicker from '$lib/components/globals/GlobalsDateRangePicker.svelte';
  import { TYPE_CONFIG } from '$lib/data/globals-constants.js';
  import { formatPed, formatPedShort, formatValue, timeAgo, getComputedCssVar, sortedData, toggleSort, sortIcon } from '$lib/utils/globalsFormat.js';

  export let data;

  $: ({ targetData: initialData, targetName } = data);

  let summary = null;
  let topPlayers = [];
  let activity = [];
  let recent = [];
  let recentSort = { col: 'timestamp', asc: false };
  $: sortedRecent = recentSort.col === 'timestamp' && !recentSort.asc ? recent : sortedData(recent, recentSort);
  let primaryType = null;
  let maturities = [];
  let wikiUrl = null;

  let period = 'all';
  let dateFrom = null;
  let dateTo = null;
  let loading = false;

  function onDateRangeChange(e) {
    period = e.detail.period;
    dateFrom = e.detail.from;
    dateTo = e.detail.to;
    refetchData();
  }

  // Selected maturity filter
  let selectedMaturities = [];
  let maturityDropdownOpen = false;

  // Top Players chart sort toggle
  let playerChartSortBy = 'value';

  // Leaderboard
  let leaderboardSort = 'value';
  let leaderboardPage = 1;
  let leaderboard = null;
  let leaderboardLoading = false;

  async function fetchLeaderboard() {
    leaderboardLoading = true;
    try {
      const params = new URLSearchParams();
      params.set('sort', leaderboardSort);
      params.set('page', String(leaderboardPage));
      if (selectedMaturities.length > 0) {
        params.set('maturities', selectedMaturities.join(','));
      }
      if (dateFrom && dateTo) {
        params.set('from', dateFrom);
        params.set('to', dateTo);
      } else if (period !== 'all' && period !== 'custom') {
        params.set('period', period);
      }
      const res = await fetch(`/api/globals/target/${encodeURIComponent(targetName)}/leaderboard?${params}`);
      if (res.ok) leaderboard = await res.json();
    } catch { /* ignore */ }
    leaderboardLoading = false;
  }

  function onLeaderboardSortChange(sort) {
    leaderboardSort = sort;
    leaderboardPage = 1;
    fetchLeaderboard();
  }

  function goToLeaderboardPage(p) {
    leaderboardPage = p;
    fetchLeaderboard();
  }

  function applyData(d) {
    summary = d?.summary;
    topPlayers = d?.top_players || [];
    activity = d?.activity || [];
    recent = d?.recent || [];
    primaryType = d?.primary_type;
    maturities = d?.maturities || [];
    wikiUrl = d?.wiki_url || null;
  }

  // Apply initial SSR data — inlined so Svelte tracks write dependencies
  // (applyData is opaque to the compiler, breaking SSR reactive ordering)
  $: if (initialData) {
    summary = initialData.summary;
    topPlayers = initialData.top_players || [];
    activity = initialData.activity || [];
    recent = initialData.recent || [];
    primaryType = initialData.primary_type;
    maturities = initialData.maturities || [];
    wikiUrl = initialData.wiki_url || null;
  }

  async function refetchData() {
    loading = true;
    try {
      const params = new URLSearchParams();
      if (selectedMaturities.length > 0) {
        params.set('maturities', selectedMaturities.join(','));
      }
      if (dateFrom && dateTo) {
        params.set('from', dateFrom);
        params.set('to', dateTo);
      } else if (period !== 'all' && period !== 'custom') {
        params.set('period', period);
      }
      const res = await fetch(`/api/globals/target/${encodeURIComponent(targetName)}?${params}`);
      if (!res.ok) return;
      const d = await res.json();
      // Preserve the full maturities list and wiki URL from initial load
      const fullMaturities = maturities;
      const fullWikiUrl = wikiUrl;
      applyData(d);
      maturities = fullMaturities;
      wikiUrl = fullWikiUrl;
      await tick();
      buildCharts();
      leaderboardPage = 1;
      fetchLeaderboard();
    } catch { /* ignore */ }
    loading = false;
  }

  function toggleMaturity(target) {
    if (selectedMaturities.includes(target)) {
      selectedMaturities = selectedMaturities.filter(m => m !== target);
    } else {
      selectedMaturities = [...selectedMaturities, target];
    }
    refetchData();
  }

  function clearMaturityFilter() {
    selectedMaturities = [];
    refetchData();
  }

  // Charts
  let activityCanvas;
  let topPlayersCanvas;
  let activityChart = null;
  let topPlayersChart = null;

  function buildActivityChart() {
    if (!activityCanvas || !activity.length) return;
    if (activityChart) activityChart.destroy();

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
            time: { unit: initialData?.bucket_unit || 'day' },
            ticks: { color: textMuted, maxTicksLimit: 10, font: { size: 11 } },
            grid: { color: borderColor + '30' },
          },
          y: {
            beginAtZero: true,
            position: 'left',
            title: { display: true, text: 'Count', color: textMuted, font: { size: 11 } },
            ticks: { color: textMuted, font: { size: 11 } },
            grid: { color: borderColor + '30' },
          },
          y1: {
            beginAtZero: true,
            position: 'right',
            title: { display: true, text: 'PED', color: textMuted, font: { size: 11 } },
            ticks: { color: textMuted, font: { size: 11 }, callback: v => formatPedShort(v) },
            grid: { display: false },
          },
        },
        plugins: {
          legend: { display: true, labels: { color: textMuted, font: { size: 11 }, usePointStyle: true, pointStyle: 'line' } },
          tooltip: {
            backgroundColor: 'rgba(0,0,0,0.85)',
            callbacks: { label: ctx => ctx.dataset.yAxisID === 'y1' ? `Value: ${formatPedShort(ctx.parsed.y)} PED` : `Count: ${ctx.parsed.y}` },
          },
        },
      },
    });
  }

  // Get index of Y-axis label clicked (for horizontal bar charts)
  function getClickedLabelIndex(evt, chart) {
    if (!chart) return null;
    const yScale = chart.scales.y;
    if (!yScale) return null;
    const { right } = yScale;
    const x = evt.native?.offsetX ?? evt.x;
    const y = evt.native?.offsetY ?? evt.y;
    if (x > right) return null;
    for (let i = 0; i < yScale.ticks.length; i++) {
      const labelY = yScale.getPixelForTick(i);
      if (Math.abs(y - labelY) < 12) return i;
    }
    return null;
  }

  function buildTopPlayersChart() {
    if (!topPlayersCanvas || !topPlayers.length) return;
    if (topPlayersChart) topPlayersChart.destroy();

    const accentColor = getComputedCssVar('--accent-color') || '#60b0ff';
    const textMuted = getComputedCssVar('--text-muted') || '#aaa';
    const borderColor = getComputedCssVar('--border-color') || '#555';

    const sorted = [...topPlayers].sort((a, b) => b[playerChartSortBy] - a[playerChartSortBy]);
    const players = sorted.slice(0, 8);
    const label = playerChartSortBy === 'count' ? 'Count' : 'Total Value (PED)';

    topPlayersChart = new Chart(topPlayersCanvas, {
      type: 'bar',
      data: {
        labels: players.map(p => {
          const maxLen = p.is_team ? 14 : 18;
          const name = p.player.length > maxLen ? p.player.slice(0, maxLen - 2) + '...' : p.player;
          return p.is_team ? '[T] ' + name : name;
        }),
        datasets: [{
          label,
          data: players.map(p => p[playerChartSortBy]),
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
        onClick: (evt, elements) => {
          const idx = elements.length > 0 ? elements[0].index : getClickedLabelIndex(evt, topPlayersChart);
          if (idx != null && players[idx]) {
            goto(`/globals/player/${encodeURIComponent(players[idx].player)}`);
          }
        },
        onHover: (evt, elements) => {
          evt.native.target.style.cursor = (elements.length > 0 || getClickedLabelIndex(evt, topPlayersChart) != null) ? 'pointer' : 'default';
        },
      },
    });
  }

  async function buildCharts() {
    await tick();
    buildActivityChart();
    buildTopPlayersChart();
  }

  onMount(() => {
    if (initialData) {
      buildCharts();
      fetchLeaderboard();
    }
  });

  onDestroy(() => {
    if (activityChart) activityChart.destroy();
    if (topPlayersChart) topPlayersChart.destroy();
  });

  function handleSearchSelect(e) {
    const { name, type } = e.detail;
    if (type === 'Player' || type === 'Team') {
      goto(`/globals/player/${encodeURIComponent(name)}`);
    } else {
      goto(`/globals/target/${encodeURIComponent(name)}`);
    }
  }

  function handleSearch(e) {
    const query = e.detail.query?.trim();
    if (query) goto(`/globals/player/${encodeURIComponent(query)}`);
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
          {#if wikiUrl}
            <a href={wikiUrl} class="wiki-link">View on Wiki &rarr;</a>
          {/if}
        </div>
      </div>
      <div class="globals-search">
        <SearchInput
          placeholder="Search players, teams, mobs, resources..."
          endpoint="/api/globals/search"
          apiPrefix={false}
          on:select={handleSearchSelect}
          on:search={handleSearch}
        />
      </div>
    </div>
  </div>

  {#if !initialData || !summary}
    <p class="empty-state">No globals recorded for this target</p>
  {:else}
    <!-- Maturity Filter -->
    {#if maturities.length > 0}
      <div class="maturity-filter">
        <div class="maturity-header">
          <span class="maturity-label">Filter by maturity</span>
          {#if selectedMaturities.length > 0}
            <button class="maturity-clear" on:click={clearMaturityFilter}>Clear filter</button>
          {/if}
        </div>
        <div class="maturity-chips">
          {#each maturities as m}
            <button
              class="maturity-chip"
              class:selected={selectedMaturities.includes(m.target)}
              on:click={() => toggleMaturity(m.target)}
            >
              {m.target}
              <span class="maturity-count">({m.count})</span>
            </button>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Period Selector -->
    <GlobalsDateRangePicker {period} from={dateFrom} to={dateTo} disabled={loading} on:change={onDateRangeChange} />

    <!-- Summary Cards -->
    <div class="stats-row">
      <div class="stat-card">
        <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="#60b0ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
        <span class="stat-value">{summary.total_count.toLocaleString()}</span>
        <span class="stat-label">Total Globals</span>
      </div>
      <div class="stat-card">
        <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="#2ecc71" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        <span class="stat-value">{formatPed(summary.total_value)} PED</span>
        <span class="stat-label">Total Value</span>
      </div>
      <div class="stat-card">
        <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="#f39c12" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
        <span class="stat-value">{formatPed(summary.avg_value)} PED</span>
        <span class="stat-label">Avg Value</span>
      </div>
      <div class="stat-card">
        <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="#e74c3c" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
        <span class="stat-value">{formatPed(summary.max_value)} PED</span>
        <span class="stat-label">Highest Loot</span>
      </div>
      <div class="stat-card">
        <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="#eab308" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        <span class="stat-value">{summary.hof_count.toLocaleString()}</span>
        <span class="stat-label">Hall of Fame</span>
      </div>
      <div class="stat-card">
        <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="#9b59b6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5C7 4 7 7 7 7"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5C17 4 17 7 17 7"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>
        <span class="stat-value">{summary.ath_count.toLocaleString()}</span>
        <span class="stat-label">All-Time Highs</span>
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

    <!-- Top Players + Recent Globals side by side -->
    <div class="chart-recent-grid">
      {#if topPlayers.length > 0}
        <div class="section-card">
          <div class="chart-card-header">
            <h2>Top Players</h2>
            <div class="sort-toggle">
              <button class="sort-btn" class:active={playerChartSortBy === 'value'} on:click={() => { playerChartSortBy = 'value'; buildTopPlayersChart(); }}>Value</button>
              <button class="sort-btn" class:active={playerChartSortBy === 'count'} on:click={() => { playerChartSortBy = 'count'; buildTopPlayersChart(); }}>Count</button>
            </div>
          </div>
          <div class="chart-container">
            <canvas bind:this={topPlayersCanvas}></canvas>
          </div>
        </div>
      {/if}

      {#if recent.length > 0}
        <div class="section-card recent-compact">
          <h2>Recent Globals</h2>
          <div class="table-wrapper">
            <table class="data-table compact-table">
              <thead>
                <tr>
                  <th class="sortable" on:click={() => recentSort = toggleSort(recentSort, 'player')}>Player{sortIcon(recentSort, 'player')}</th>
                  <th class="sortable right" on:click={() => recentSort = toggleSort(recentSort, 'value')}>Value{sortIcon(recentSort, 'value')}</th>
                  <th></th>
                  <th class="sortable" on:click={() => recentSort = toggleSort(recentSort, 'timestamp')}>Time{sortIcon(recentSort, 'timestamp')}</th>
                </tr>
              </thead>
              <tbody>
                {#each sortedRecent as g}
                  <tr>
                    <td>
                      {#if g.type === 'team_kill'}<span class="badge-team">T</span>{/if}
                      <a href="/globals/player/{encodeURIComponent(g.player)}" class="player-link">{g.player}</a>
                    </td>
                    <td class="right font-weight-bold">{formatValue(g.value, g.unit, g.type)}</td>
                    <td>
                      {#if g.ath}<span class="badge-ath">ATH</span>{:else if g.hof}<span class="badge-hof">HoF</span>{/if}
                    </td>
                    <td class="text-muted">{timeAgo(g.timestamp)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/if}
    </div>

    <!-- Player Leaderboard -->
    <div class="section-card">
      <div class="leaderboard-header">
        <h2>Leaderboard</h2>
        <div class="sort-toggle">
          <button class="sort-btn" class:active={leaderboardSort === 'value'} on:click={() => onLeaderboardSortChange('value')}>By Value</button>
          <button class="sort-btn" class:active={leaderboardSort === 'count'} on:click={() => onLeaderboardSortChange('count')}>By Count</button>
          <button class="sort-btn" class:active={leaderboardSort === 'best'} on:click={() => onLeaderboardSortChange('best')}>By Highest</button>
        </div>
      </div>
      {#if leaderboardLoading && !leaderboard}
        <div class="table-loading"><span class="spinner"></span></div>
      {:else if leaderboard && leaderboard.players.length > 0}
        <div class="table-wrapper" class:loading-fade={leaderboardLoading}>
          <table class="data-table">
            <thead>
              <tr>
                <th class="col-rank">#</th>
                <th>Player</th>
                <th class="right">Count</th>
                <th class="right">Total Value</th>
                <th class="right">Best</th>
              </tr>
            </thead>
            <tbody>
              {#each leaderboard.players as p, i}
                <tr>
                  <td class="col-rank text-muted">{(leaderboardPage - 1) * 20 + i + 1}</td>
                  <td>
                    {#if p.is_team}
                      <span class="badge-team">Team</span>
                    {/if}
                    <a href="/globals/player/{encodeURIComponent(p.player)}" class="player-link">{p.player}</a>
                  </td>
                  <td class="right">{p.count.toLocaleString()}</td>
                  <td class="right font-mono">{formatPed(p.value)} PED</td>
                  <td class="right font-mono">{formatPed(p.best_value)} PED</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        {#if leaderboard.pages > 1}
          <div class="pagination">
            <button class="page-btn" disabled={leaderboardPage <= 1} on:click={() => goToLeaderboardPage(leaderboardPage - 1)}>Previous</button>
            <span class="page-info">Page {leaderboard.page} of {leaderboard.pages}</span>
            <button class="page-btn" disabled={leaderboardPage >= leaderboard.pages} on:click={() => goToLeaderboardPage(leaderboardPage + 1)}>Next</button>
          </div>
        {/if}
      {:else}
        <p class="empty-state-sm">No player data available</p>
      {/if}
    </div>
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

  .wiki-link {
    font-size: 0.8125rem;
    color: var(--accent-color);
    text-decoration: none;
    white-space: nowrap;
  }

  .wiki-link:hover {
    text-decoration: underline;
  }

  /* Maturity filter */
  .maturity-filter {
    margin-bottom: 20px;
    padding: 12px 16px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }

  .maturity-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .maturity-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    font-weight: 600;
  }

  .maturity-clear {
    font-size: 0.75rem;
    color: var(--accent-color);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .maturity-clear:hover {
    text-decoration: underline;
  }

  .maturity-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .maturity-chip {
    padding: 4px 10px;
    font-size: 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .maturity-chip:hover {
    border-color: var(--accent-color);
    color: var(--text-color);
  }

  .maturity-chip.selected {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: #fff;
  }

  .maturity-count {
    opacity: 0.7;
    margin-left: 2px;
  }

  /* Period selector */
  /* Chart card header with sort toggle */
  .chart-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .chart-card-header h2 {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
  }

  .sort-toggle {
    display: flex;
    gap: 2px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .sort-btn {
    padding: 2px 10px;
    font-size: 0.6875rem;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .sort-btn.active {
    background: var(--accent-color);
    color: #fff;
  }

  .sort-btn:hover:not(.active) {
    color: var(--text-color);
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
    margin-bottom: 16px;
  }

  .stat-card {
    padding: 14px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    text-align: center;
  }

  .stat-icon {
    width: 20px;
    height: 20px;
    margin-bottom: 4px;
    opacity: 0.85;
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

  /* Top players + recent globals side by side */
  .chart-recent-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
  }

  .chart-recent-grid .section-card {
    margin-bottom: 0;
  }

  /* Compact recent table */
  .compact-table th,
  .compact-table td {
    padding: 5px 8px;
    font-size: 0.75rem;
  }

  .recent-compact {
    display: flex;
    flex-direction: column;
    max-height: 400px;
  }

  .recent-compact .table-wrapper {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
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
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: -2px;
  }

  .text-muted {
    color: var(--text-muted);
  }

  .font-weight-bold {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .player-link, .target-link {
    color: var(--text-color);
    text-decoration: none;
    font-weight: 600;
  }

  .player-link:hover, .target-link:hover {
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
  .type-examine  { background: rgba(46, 204, 113, 0.15); color: #2ecc71; }
  .type-pvp      { background: rgba(231, 76, 60, 0.15);  color: #e74c3c; }

  .badge-hof, .badge-ath, .badge-team {
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.3px;
  }

  .badge-hof { background: rgba(234, 179, 8, 0.15); color: #eab308; }
  .badge-ath { background: rgba(239, 68, 68, 0.2); color: #ef4444; }

  .badge-team {
    background: rgba(96, 176, 255, 0.15);
    color: var(--accent-color);
    margin-right: 4px;
  }

  /* Leaderboard */
  .leaderboard-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    gap: 12px;
  }

  .leaderboard-header h2 {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
  }

  .col-rank { width: 40px; }
  .font-mono { font-variant-numeric: tabular-nums; }

  .table-loading {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 120px;
  }

  .spinner {
    display: inline-block;
    width: 24px;
    height: 24px;
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

  .empty-state-sm {
    text-align: center;
    padding: 24px;
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 16px;
    margin-top: 12px;
  }

  .page-btn {
    padding: 6px 16px;
    font-size: 0.8125rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .page-btn:hover:not(:disabled) {
    border-color: var(--accent-color);
    color: var(--text-color);
  }

  .page-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .page-info {
    font-size: 0.8125rem;
    color: var(--text-muted);
  }

  /* Responsive */
  @media (max-width: 899px) {
    .target-page {
      padding: 16px;
    }

    .stats-row {
      grid-template-columns: repeat(3, 1fr);
    }

    .chart-recent-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
