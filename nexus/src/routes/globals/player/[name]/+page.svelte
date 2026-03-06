<!--
  @component Player Globals Detail Page
  Tabbed view of a player's globals: Overview, Hunting, Mining, Crafting, ATHs.
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
  import GlobalsDateRangePicker from '$lib/components/globals/GlobalsDateRangePicker.svelte';
  import { TYPE_CONFIG } from '$lib/data/globals-constants.js';
  import { formatPed, formatValue, timeAgo, getComputedCssVar, sortedData, toggleSort, sortIcon } from '$lib/utils/globalsFormat.js';

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
  $: rareItems = playerData?.rare_items || [];
  $: topLoots = playerData?.top_loots || { hunting: [], mining: [], crafting: [] };
  $: athTargets = playerData?.ath_targets || { by_total: [], by_best: [] };
  $: isTeam = summary && summary.team_kill_count > 0 && summary.total_count === summary.team_kill_count;

  // Tabs - base tabs always shown, extra tabs conditional on data
  const BASE_TABS = [
    { value: 'overview', label: 'Overview' },
    { value: 'hunting', label: 'Hunting' },
    { value: 'mining', label: 'Mining' },
    { value: 'crafting', label: 'Crafting' },
  ];
  const EXTRA_TABS = [
    { value: 'rare', label: 'Rare Finds', key: 'rare_count' },
    { value: 'discoveries', label: 'Discoveries', key: 'discovery_count' },
    { value: 'tier', label: 'Tier Records', key: 'tier_count' },
    { value: 'pvp', label: 'PvP', key: 'pvp_count' },
  ];
  $: tabs = [
    ...BASE_TABS,
    ...EXTRA_TABS.filter(t => summary && summary[t.key] > 0),
    { value: 'aths', label: 'ATHs' },
  ];
  let activeTab = 'overview';

  let period = 'all';
  let dateFrom = null;
  let dateTo = null;
  let loading = false;

  function onDateRangeChange(e) {
    period = e.detail.period;
    dateFrom = e.detail.from;
    dateTo = e.detail.to;
    fetchData();
  }

  async function fetchData() {
    loading = true;
    try {
      const params = new URLSearchParams();
      if (dateFrom && dateTo) {
        params.set('from', dateFrom);
        params.set('to', dateTo);
      } else if (period !== 'all' && period !== 'custom') {
        params.set('period', period);
      }
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

  $: sortedHunting = sortedData(hunting, huntSort);
  $: sortedMining = sortedData(mining, miningSort);
  $: sortedCrafting = sortedData(crafting, craftSort);

  // Pagination constants
  const PAGE_SIZE = 25;
  const ATH_TARGETS_PAGE_SIZE = 10;

  // Hunting tab pagination
  let huntTargetPage = 0;
  let huntLootPage = 0;
  $: huntTargetPages = Math.ceil(sortedHunting.length / PAGE_SIZE);
  $: huntLootPages = Math.ceil((topLoots.hunting?.length || 0) / PAGE_SIZE);
  $: pagedHunting = sortedHunting.slice(huntTargetPage * PAGE_SIZE, (huntTargetPage + 1) * PAGE_SIZE);
  $: pagedHuntingLoots = (topLoots.hunting || []).slice(huntLootPage * PAGE_SIZE, (huntLootPage + 1) * PAGE_SIZE);

  // Mining tab pagination
  let miningTargetPage = 0;
  let miningLootPage = 0;
  $: miningTargetPages = Math.ceil(sortedMining.length / PAGE_SIZE);
  $: miningLootPages = Math.ceil((topLoots.mining?.length || 0) / PAGE_SIZE);
  $: pagedMining = sortedMining.slice(miningTargetPage * PAGE_SIZE, (miningTargetPage + 1) * PAGE_SIZE);
  $: pagedMiningLoots = (topLoots.mining || []).slice(miningLootPage * PAGE_SIZE, (miningLootPage + 1) * PAGE_SIZE);

  // Crafting tab pagination
  let craftTargetPage = 0;
  let craftLootPage = 0;
  $: craftTargetPages = Math.ceil(sortedCrafting.length / PAGE_SIZE);
  $: craftLootPages = Math.ceil((topLoots.crafting?.length || 0) / PAGE_SIZE);
  $: pagedCrafting = sortedCrafting.slice(craftTargetPage * PAGE_SIZE, (craftTargetPage + 1) * PAGE_SIZE);
  $: pagedCraftingLoots = (topLoots.crafting || []).slice(craftLootPage * PAGE_SIZE, (craftLootPage + 1) * PAGE_SIZE);

  // ATH tab sort — auto-select category with highest single loot
  $: athCategory = (() => {
    const hMax = topLoots.hunting?.[0]?.value || 0;
    const mMax = topLoots.mining?.[0]?.value || 0;
    const cMax = topLoots.crafting?.[0]?.value || 0;
    if (mMax > hMax && mMax >= cMax) return 'mining';
    if (cMax > hMax && cMax > mMax) return 'crafting';
    return 'hunting';
  })();
  let athCategoryOverride = null;
  $: activeAthCategory = athCategoryOverride ?? athCategory;
  $: athLoots = topLoots[activeAthCategory] || [];

  // ATH pagination
  let athLootPage = 0;
  let athTotalPage = 0;
  let athBestPage = 0;
  $: athLootPages = Math.ceil(athLoots.length / PAGE_SIZE);
  $: pagedAthLoots = athLoots.slice(athLootPage * PAGE_SIZE, (athLootPage + 1) * PAGE_SIZE);
  $: athTotalPages = Math.ceil((athTargets.by_total?.length || 0) / ATH_TARGETS_PAGE_SIZE);
  $: athBestPages = Math.ceil((athTargets.by_best?.length || 0) / ATH_TARGETS_PAGE_SIZE);
  $: pagedAthTotal = (athTargets.by_total || []).slice(athTotalPage * ATH_TARGETS_PAGE_SIZE, (athTotalPage + 1) * ATH_TARGETS_PAGE_SIZE);
  $: pagedAthBest = (athTargets.by_best || []).slice(athBestPage * ATH_TARGETS_PAGE_SIZE, (athBestPage + 1) * ATH_TARGETS_PAGE_SIZE);

  // Reset pagination when category changes
  $: if (activeAthCategory) athLootPage = 0;

  // Activity chart
  let activityCanvas;
  let activityChart = null;

  function buildActivityChart() {
    if (!activityCanvas || !activity.length) return;
    if (activityChart) activityChart.destroy();

    const accentColor = getComputedCssVar('--accent-color') || '#60b0ff';
    const textMuted = getComputedCssVar('--text-muted') || '#aaa';
    const borderColor = getComputedCssVar('--border-color') || '#555';
    const chartUnit = playerData?.bucket_unit || 'day';

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
          tension: 0.1,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            type: 'time',
            time: { unit: chartUnit },
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

  $: if (activityCanvas && activity.length && activeTab === 'overview') {
    tick().then(buildActivityChart);
  }

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

  // Tab-specific data
  $: discoveries = achievements.filter(a => a.type === 'discovery');
  $: tierRecords = achievements.filter(a => a.type === 'tier');
  $: pvpEvents = playerData?.pvp_events || [];

  // Overview helpers
  $: overviewRareItems = rareItems.slice(0, 5);
  $: overviewDiscoveries = discoveries.slice(0, 5);
  $: overviewTopHunting = topLoots.hunting.slice(0, OVERVIEW_TOP_LIMIT);
  $: overviewTopMining = topLoots.mining.slice(0, OVERVIEW_TOP_LIMIT);
  $: overviewTopCrafting = topLoots.crafting.slice(0, OVERVIEW_TOP_LIMIT);

  const OVERVIEW_TOP_LIMIT = 3;
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
        <div class="title-row">
          <h1>{playerName}</h1>
          {#if isTeam}
            <span class="badge-team-header">Team</span>
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

  {#if !playerData || !summary}
    <p class="empty-state">No globals recorded for this player</p>
  {:else}
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

    <!-- Category Breakdown (clickable to switch tabs) -->
    <div class="stats-row category-row">
      <button class="stat-card category-card clickable" on:click={() => activeTab = 'hunting'}>
        <span class="stat-value hunting-color">{(summary.kill_count + summary.team_kill_count).toLocaleString()}</span>
        <span class="stat-label">Hunting</span>
        <span class="stat-sub">{formatPed(summary.hunting_value)} PED</span>
      </button>
      <button class="stat-card category-card clickable" on:click={() => activeTab = 'mining'}>
        <span class="stat-value mining-color">{summary.deposit_count.toLocaleString()}</span>
        <span class="stat-label">Mining</span>
        <span class="stat-sub">{formatPed(summary.mining_value)} PED</span>
      </button>
      <button class="stat-card category-card clickable" on:click={() => activeTab = 'crafting'}>
        <span class="stat-value crafting-color">{summary.craft_count.toLocaleString()}</span>
        <span class="stat-label">Crafting</span>
        <span class="stat-sub">{formatPed(summary.crafting_value)} PED</span>
      </button>
    </div>

    <!-- Tab Navigation -->
    {#if !isTeam}
      <nav class="player-tab-nav">
        {#each tabs as tab}
          <button
            class="tab-link"
            class:active={activeTab === tab.value}
            on:click={() => activeTab = tab.value}
          >
            {tab.label}
          </button>
        {/each}
      </nav>
    {/if}

    <!-- Tab Content -->
    <div class="tab-content" class:loading-fade={loading}>
      <!-- === OVERVIEW TAB === -->
      {#if activeTab === 'overview'}
        <!-- Top 3 per category -->
        <div class="overview-categories">
          {#if overviewTopHunting.length > 0}
            <div class="section-card overview-category">
              <div class="overview-cat-header">
                <h2>Top Hunting Loots</h2>
                <button class="view-all-btn" on:click={() => activeTab = 'hunting'}>View all &rarr;</button>
              </div>
              <div class="top-loots-list">
                {#each overviewTopHunting as loot, i}
                  <div class="top-loot-item">
                    <span class="top-loot-rank">{i + 1}</span>
                    <a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link">{loot.target}</a>
                    <span class="top-loot-value">{formatPed(loot.value)} PED</span>
                    {#if loot.ath}<span class="badge-ath">ATH</span>{:else if loot.hof}<span class="badge-hof">HoF</span>{/if}
                    <span class="top-loot-time">{timeAgo(loot.timestamp)}</span>
                  </div>
                {/each}
              </div>
            </div>
          {/if}

          {#if overviewTopMining.length > 0}
            <div class="section-card overview-category">
              <div class="overview-cat-header">
                <h2>Top Mining Loots</h2>
                <button class="view-all-btn" on:click={() => activeTab = 'mining'}>View all &rarr;</button>
              </div>
              <div class="top-loots-list">
                {#each overviewTopMining as loot, i}
                  <div class="top-loot-item">
                    <span class="top-loot-rank">{i + 1}</span>
                    <a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link">{loot.target}</a>
                    <span class="top-loot-value">{formatPed(loot.value)} PED</span>
                    {#if loot.ath}<span class="badge-ath">ATH</span>{:else if loot.hof}<span class="badge-hof">HoF</span>{/if}
                    <span class="top-loot-time">{timeAgo(loot.timestamp)}</span>
                  </div>
                {/each}
              </div>
            </div>
          {/if}

          {#if overviewTopCrafting.length > 0}
            <div class="section-card overview-category">
              <div class="overview-cat-header">
                <h2>Top Crafting Loots</h2>
                <button class="view-all-btn" on:click={() => activeTab = 'crafting'}>View all &rarr;</button>
              </div>
              <div class="top-loots-list">
                {#each overviewTopCrafting as loot, i}
                  <div class="top-loot-item">
                    <span class="top-loot-rank">{i + 1}</span>
                    <a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link">{loot.target}</a>
                    <span class="top-loot-value">{formatPed(loot.value)} PED</span>
                    {#if loot.ath}<span class="badge-ath">ATH</span>{:else if loot.hof}<span class="badge-hof">HoF</span>{/if}
                    <span class="top-loot-time">{timeAgo(loot.timestamp)}</span>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>

        <!-- Rare Finds + Discoveries -->
        <div class="overview-specials">
          <div class="section-card">
            <h2>Recent Rare Finds</h2>
            {#if overviewRareItems.length > 0}
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th class="right">Value</th>
                      <th>Time</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each overviewRareItems as item}
                      <tr>
                        <td>{item.target}</td>
                        <td class="right">{formatPed(item.value)} PED</td>
                        <td class="text-muted" title={new Date(item.timestamp).toLocaleString()}>{timeAgo(item.timestamp)}</td>
                        <td>
                          {#if item.ath}<span class="badge-ath">ATH</span>{:else if item.hof}<span class="badge-hof">HoF</span>{/if}
                        </td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {:else}
              <p class="empty-state-sm">No rare finds recorded</p>
            {/if}
          </div>

          <div class="section-card">
            <h2>Recent Discoveries</h2>
            {#if overviewDiscoveries.length > 0}
              <div class="achievements-list">
                {#each overviewDiscoveries as ach}
                  <div class="achievement-item">
                    <span class="type-badge type-discovery">Discovery</span>
                    <span class="achievement-target">{ach.target}</span>
                    <span class="achievement-time">{timeAgo(ach.timestamp)}</span>
                  </div>
                {/each}
              </div>
            {:else}
              <p class="empty-state-sm">No discoveries recorded</p>
            {/if}
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
                      <td><a href="/globals/target/{encodeURIComponent(g.target)}" class="target-link">{g.target}</a></td>
                      <td class="right font-weight-bold">{formatValue(g.value, g.unit, g.type)}</td>
                      <td>
                        {#if g.ath}<span class="badge-ath">ATH</span>{:else if g.hof}<span class="badge-hof">HoF</span>{/if}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          </div>
        {/if}

      <!-- === HUNTING TAB === -->
      {:else if activeTab === 'hunting'}
        {#if hunting.length > 0}
          <div class="tab-side-by-side">
            <div class="section-card">
              <h2 class="section-title-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="22" y1="2" x2="12" y2="12"/></svg>
                Mob Breakdown
              </h2>
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th class="sortable" on:click={() => { huntSort = toggleSort(huntSort, 'target'); huntTargetPage = 0; }}>
                        Target{sortIcon(huntSort, 'target')}
                      </th>
                      <th class="sortable right" on:click={() => { huntSort = toggleSort(huntSort, 'kills'); huntTargetPage = 0; }}>
                        Kills{sortIcon(huntSort, 'kills')}
                      </th>
                      <th class="sortable right" on:click={() => { huntSort = toggleSort(huntSort, 'total_value'); huntTargetPage = 0; }}>
                        Total{sortIcon(huntSort, 'total_value')}
                      </th>
                      <th class="right">Best</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each pagedHunting as mob, i}
                      {@const mobKey = mob.mob_id || mob.target || (huntTargetPage * PAGE_SIZE + i)}
                      {@const hasDetails = mob.maturities && mob.maturities.length > 1}
                      {@const displayName = hasDetails ? mob.target : (mob.maturities?.[0]?.target || mob.target)}
                      <tr
                        class="mob-row"
                        class:expandable={hasDetails}
                        on:click={() => hasDetails && toggleMob(mobKey)}
                      >
                        <td>
                          {#if hasDetails}
                            <span class="expand-icon">{expandedMobs.has(mobKey) ? '\u25BC' : '\u25B6'}</span>
                          {/if}
                          <a href="/globals/target/{encodeURIComponent(displayName)}" class="target-link" on:click|stopPropagation>{displayName}</a>
                        </td>
                        <td class="right">{mob.kills}</td>
                        <td class="right">{formatPed(mob.total_value)}</td>
                        <td class="right">{formatPed(mob.best_value)}</td>
                      </tr>
                      {#if hasDetails && expandedMobs.has(mobKey)}
                        {#each mob.maturities as mat}
                          <tr class="maturity-row">
                            <td class="indent"><a href="/globals/target/{encodeURIComponent(mat.target)}" class="target-link">{mat.target}</a></td>
                            <td class="right">{mat.kills}</td>
                            <td class="right">{formatPed(mat.total_value)}</td>
                            <td class="right">{formatPed(mat.best_value)}</td>
                          </tr>
                        {/each}
                      {/if}
                    {/each}
                  </tbody>
                </table>
              </div>
              {#if huntTargetPages > 1}
                <div class="pagination">
                  <button disabled={huntTargetPage === 0} on:click={() => huntTargetPage--}>&laquo; Prev</button>
                  <span>{huntTargetPage + 1} / {huntTargetPages}</span>
                  <button disabled={huntTargetPage >= huntTargetPages - 1} on:click={() => huntTargetPage++}>Next &raquo;</button>
                </div>
              {/if}
            </div>

            {#if topLoots.hunting.length > 0}
              <div class="section-card">
                <h2 class="section-title-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
                  Top Individual Loots
                </h2>
                <div class="table-wrapper">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th class="col-rank">#</th>
                        <th>Target</th>
                        <th class="right">Value</th>
                        <th></th>
                        <th>Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each pagedHuntingLoots as loot, i}
                        <tr>
                          <td class="col-rank text-muted">{huntLootPage * PAGE_SIZE + i + 1}</td>
                          <td><a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link">{loot.target}</a></td>
                          <td class="right font-weight-bold">{formatPed(loot.value)} PED</td>
                          <td>{#if loot.ath}<span class="badge-ath">ATH</span>{:else if loot.hof}<span class="badge-hof">HoF</span>{/if}</td>
                          <td class="text-muted" title={new Date(loot.timestamp).toLocaleString()}>{timeAgo(loot.timestamp)}</td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
                {#if huntLootPages > 1}
                  <div class="pagination">
                    <button disabled={huntLootPage === 0} on:click={() => huntLootPage--}>&laquo; Prev</button>
                    <span>{huntLootPage + 1} / {huntLootPages}</span>
                    <button disabled={huntLootPage >= huntLootPages - 1} on:click={() => huntLootPage++}>Next &raquo;</button>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {:else}
          <p class="empty-state-sm">No hunting globals found for this period</p>
        {/if}

      <!-- === MINING TAB === -->
      {:else if activeTab === 'mining'}
        {#if mining.length > 0}
          <div class="tab-side-by-side">
            <div class="section-card">
              <h2 class="section-title-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="#60b0ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 22l10-10"/><path d="M16 8l-4 4"/><path d="M22 2l-5.5 5.5"/><circle cx="18" cy="6" r="3"/></svg>
                Resource Breakdown
              </h2>
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th class="sortable" on:click={() => { miningSort = toggleSort(miningSort, 'target'); miningTargetPage = 0; }}>
                        Resource{sortIcon(miningSort, 'target')}
                      </th>
                      <th class="sortable right" on:click={() => { miningSort = toggleSort(miningSort, 'finds'); miningTargetPage = 0; }}>
                        Finds{sortIcon(miningSort, 'finds')}
                      </th>
                      <th class="sortable right" on:click={() => { miningSort = toggleSort(miningSort, 'total_value'); miningTargetPage = 0; }}>
                        Total{sortIcon(miningSort, 'total_value')}
                      </th>
                      <th class="right">Best</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each pagedMining as res}
                      <tr>
                        <td><a href="/globals/target/{encodeURIComponent(res.target)}" class="target-link">{res.target}</a></td>
                        <td class="right">{res.finds}</td>
                        <td class="right">{formatPed(res.total_value)}</td>
                        <td class="right">{formatPed(res.best_value)}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
              {#if miningTargetPages > 1}
                <div class="pagination">
                  <button disabled={miningTargetPage === 0} on:click={() => miningTargetPage--}>&laquo; Prev</button>
                  <span>{miningTargetPage + 1} / {miningTargetPages}</span>
                  <button disabled={miningTargetPage >= miningTargetPages - 1} on:click={() => miningTargetPage++}>Next &raquo;</button>
                </div>
              {/if}
            </div>

            {#if topLoots.mining.length > 0}
              <div class="section-card">
                <h2 class="section-title-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="#60b0ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
                  Top Individual Loots
                </h2>
                <div class="table-wrapper">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th class="col-rank">#</th>
                        <th>Resource</th>
                        <th class="right">Value</th>
                        <th></th>
                        <th>Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each pagedMiningLoots as loot, i}
                        <tr>
                          <td class="col-rank text-muted">{miningLootPage * PAGE_SIZE + i + 1}</td>
                          <td><a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link">{loot.target}</a></td>
                          <td class="right font-weight-bold">{formatPed(loot.value)} PED</td>
                          <td>{#if loot.ath}<span class="badge-ath">ATH</span>{:else if loot.hof}<span class="badge-hof">HoF</span>{/if}</td>
                          <td class="text-muted" title={new Date(loot.timestamp).toLocaleString()}>{timeAgo(loot.timestamp)}</td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
                {#if miningLootPages > 1}
                  <div class="pagination">
                    <button disabled={miningLootPage === 0} on:click={() => miningLootPage--}>&laquo; Prev</button>
                    <span>{miningLootPage + 1} / {miningLootPages}</span>
                    <button disabled={miningLootPage >= miningLootPages - 1} on:click={() => miningLootPage++}>Next &raquo;</button>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {:else}
          <p class="empty-state-sm">No mining globals found for this period</p>
        {/if}

      <!-- === CRAFTING TAB === -->
      {:else if activeTab === 'crafting'}
        {#if crafting.length > 0}
          <div class="tab-side-by-side">
            <div class="section-card">
              <h2 class="section-title-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
                Item Breakdown
              </h2>
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th class="sortable" on:click={() => { craftSort = toggleSort(craftSort, 'target'); craftTargetPage = 0; }}>
                        Item{sortIcon(craftSort, 'target')}
                      </th>
                      <th class="sortable right" on:click={() => { craftSort = toggleSort(craftSort, 'crafts'); craftTargetPage = 0; }}>
                        Crafts{sortIcon(craftSort, 'crafts')}
                      </th>
                      <th class="sortable right" on:click={() => { craftSort = toggleSort(craftSort, 'total_value'); craftTargetPage = 0; }}>
                        Total{sortIcon(craftSort, 'total_value')}
                      </th>
                      <th class="right">Best</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each pagedCrafting as item}
                      <tr>
                        <td><a href="/globals/target/{encodeURIComponent(item.target)}" class="target-link">{item.target}</a></td>
                        <td class="right">{item.crafts}</td>
                        <td class="right">{formatPed(item.total_value)}</td>
                        <td class="right">{formatPed(item.best_value)}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
              {#if craftTargetPages > 1}
                <div class="pagination">
                  <button disabled={craftTargetPage === 0} on:click={() => craftTargetPage--}>&laquo; Prev</button>
                  <span>{craftTargetPage + 1} / {craftTargetPages}</span>
                  <button disabled={craftTargetPage >= craftTargetPages - 1} on:click={() => craftTargetPage++}>Next &raquo;</button>
                </div>
              {/if}
            </div>

            {#if topLoots.crafting.length > 0}
              <div class="section-card">
                <h2 class="section-title-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
                  Top Individual Loots
                </h2>
                <div class="table-wrapper">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th class="col-rank">#</th>
                        <th>Item</th>
                        <th class="right">Value</th>
                        <th></th>
                        <th>Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each pagedCraftingLoots as loot, i}
                        <tr>
                          <td class="col-rank text-muted">{craftLootPage * PAGE_SIZE + i + 1}</td>
                          <td><a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link">{loot.target}</a></td>
                          <td class="right font-weight-bold">{formatPed(loot.value)} PED</td>
                          <td>{#if loot.ath}<span class="badge-ath">ATH</span>{:else if loot.hof}<span class="badge-hof">HoF</span>{/if}</td>
                          <td class="text-muted" title={new Date(loot.timestamp).toLocaleString()}>{timeAgo(loot.timestamp)}</td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
                {#if craftLootPages > 1}
                  <div class="pagination">
                    <button disabled={craftLootPage === 0} on:click={() => craftLootPage--}>&laquo; Prev</button>
                    <span>{craftLootPage + 1} / {craftLootPages}</span>
                    <button disabled={craftLootPage >= craftLootPages - 1} on:click={() => craftLootPage++}>Next &raquo;</button>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {:else}
          <p class="empty-state-sm">No crafting globals found for this period</p>
        {/if}

      <!-- === RARE FINDS TAB === -->
      {:else if activeTab === 'rare'}
        <div class="section-card">
          <h2>Rare Finds ({summary.rare_count.toLocaleString()})</h2>
          {#if rareItems.length > 0}
            <div class="table-wrapper">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th class="right">Value</th>
                    <th>Time</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {#each rareItems as item}
                    <tr>
                      <td>{item.target}</td>
                      <td class="right font-weight-bold">{formatPed(item.value)} PED</td>
                      <td class="text-muted" title={new Date(item.timestamp).toLocaleString()}>{timeAgo(item.timestamp)}</td>
                      <td>
                        {#if item.ath}<span class="badge-ath">ATH</span>{:else if item.hof}<span class="badge-hof">HoF</span>{/if}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {:else}
            <p class="empty-state-sm">No rare finds recorded for this period</p>
          {/if}
        </div>

      <!-- === DISCOVERIES TAB === -->
      {:else if activeTab === 'discoveries'}
        <div class="section-card">
          <h2>Discoveries ({summary.discovery_count.toLocaleString()})</h2>
          {#if discoveries.length > 0}
            <div class="achievements-list">
              {#each discoveries as ach}
                <div class="achievement-item">
                  <span class="type-badge type-discovery">Discovery</span>
                  <span class="achievement-target">{ach.target}</span>
                  {#if ach.hof}<span class="badge-hof">HoF</span>{/if}
                  {#if ach.ath}<span class="badge-ath">ATH</span>{/if}
                  <span class="achievement-time">{timeAgo(ach.timestamp)}</span>
                </div>
              {/each}
            </div>
          {:else}
            <p class="empty-state-sm">No discoveries recorded for this period</p>
          {/if}
        </div>

      <!-- === TIER RECORDS TAB === -->
      {:else if activeTab === 'tier'}
        <div class="section-card">
          <h2>Tier Records ({summary.tier_count.toLocaleString()})</h2>
          {#if tierRecords.length > 0}
            <div class="achievements-list">
              {#each tierRecords as ach}
                <div class="achievement-item">
                  <span class="type-badge type-tier">Tier</span>
                  <span class="achievement-target">{ach.target}</span>
                  {#if ach.extra?.tier}
                    <span class="achievement-detail">Tier {ach.extra.tier}</span>
                  {/if}
                  {#if ach.hof}<span class="badge-hof">HoF</span>{/if}
                  <span class="achievement-time">{timeAgo(ach.timestamp)}</span>
                </div>
              {/each}
            </div>
          {:else}
            <p class="empty-state-sm">No tier records for this period</p>
          {/if}
        </div>

      <!-- === PVP TAB === -->
      {:else if activeTab === 'pvp'}
        <div class="section-card">
          <h2>PvP ({summary.pvp_count.toLocaleString()} globals, {formatPed(summary.pvp_value)} PED)</h2>
          {#if pvpEvents.length > 0}
            <div class="table-wrapper">
              <table class="data-table">
                <thead>
                  <tr>
                    <th class="right">Value</th>
                    <th></th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {#each pvpEvents as g}
                    <tr>
                      <td class="right font-weight-bold">{formatPed(g.value)} PED</td>
                      <td>
                        {#if g.ath}<span class="badge-ath">ATH</span>{:else if g.hof}<span class="badge-hof">HoF</span>{/if}
                      </td>
                      <td class="text-muted" title={new Date(g.timestamp).toLocaleString()}>{timeAgo(g.timestamp)}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {:else}
            <p class="empty-state-sm">No PvP globals recorded for this period</p>
          {/if}
        </div>

      <!-- === ATHS TAB === -->
      {:else if activeTab === 'aths'}
        <!-- Top individual loots by category -->
        <div class="section-card">
          <div class="ath-header">
            <h2 class="section-title-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="#eab308" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
              Personal Records
            </h2>
            <div class="sort-toggle">
              <button class="sort-btn" class:active={activeAthCategory === 'hunting'} on:click={() => { athCategoryOverride = 'hunting'; athLootPage = 0; }}>Hunting</button>
              <button class="sort-btn" class:active={activeAthCategory === 'mining'} on:click={() => { athCategoryOverride = 'mining'; athLootPage = 0; }}>Mining</button>
              <button class="sort-btn" class:active={activeAthCategory === 'crafting'} on:click={() => { athCategoryOverride = 'crafting'; athLootPage = 0; }}>Crafting</button>
            </div>
          </div>
          {#if athLoots.length > 0}
            <div class="table-wrapper">
              <table class="data-table">
                <thead>
                  <tr>
                    <th class="col-rank">#</th>
                    <th>Target</th>
                    <th class="right">Value</th>
                    <th></th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {#each pagedAthLoots as loot, i}
                    <tr>
                      <td class="col-rank text-muted">{athLootPage * PAGE_SIZE + i + 1}</td>
                      <td><a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link">{loot.target}</a></td>
                      <td class="right font-weight-bold">{formatPed(loot.value)} PED</td>
                      <td>{#if loot.ath}<span class="badge-ath">ATH</span>{:else if loot.hof}<span class="badge-hof">HoF</span>{/if}</td>
                      <td class="text-muted" title={new Date(loot.timestamp).toLocaleString()}>{timeAgo(loot.timestamp)}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
            {#if athLootPages > 1}
              <div class="pagination">
                <button disabled={athLootPage === 0} on:click={() => athLootPage--}>&laquo; Prev</button>
                <span>{athLootPage + 1} / {athLootPages}</span>
                <button disabled={athLootPage >= athLootPages - 1} on:click={() => athLootPage++}>Next &raquo;</button>
              </div>
            {/if}
          {:else}
            <p class="empty-state-sm">No {activeAthCategory} records found for this period</p>
          {/if}
        </div>

        <!-- Per-target ATH -->
        <div class="ath-targets-grid">
          <div class="section-card">
            <h2 class="section-title-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="#2ecc71" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
              Top Targets by Total Value
            </h2>
            {#if athTargets.by_total.length > 0}
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th class="col-rank">#</th>
                      <th>Target</th>
                      <th class="right">Count</th>
                      <th class="right">Total</th>
                      <th class="right">Best</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each pagedAthTotal as t, i}
                      <tr>
                        <td class="col-rank text-muted">{athTotalPage * ATH_TARGETS_PAGE_SIZE + i + 1}</td>
                        <td><a href="/globals/target/{encodeURIComponent(t.target)}" class="target-link">{t.target}</a></td>
                        <td class="right">{t.count}</td>
                        <td class="right font-weight-bold">{formatPed(t.total_value)} PED</td>
                        <td class="right">{formatPed(t.best_value)} PED</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
              {#if athTotalPages > 1}
                <div class="pagination">
                  <button disabled={athTotalPage === 0} on:click={() => athTotalPage--}>&laquo; Prev</button>
                  <span>{athTotalPage + 1} / {athTotalPages}</span>
                  <button disabled={athTotalPage >= athTotalPages - 1} on:click={() => athTotalPage++}>Next &raquo;</button>
                </div>
              {/if}
            {:else}
              <p class="empty-state-sm">No target data available</p>
            {/if}
          </div>

          <div class="section-card">
            <h2 class="section-title-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="#e74c3c" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
              Top Targets by Single Loot
            </h2>
            {#if athTargets.by_best.length > 0}
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th class="col-rank">#</th>
                      <th>Target</th>
                      <th class="right">Count</th>
                      <th class="right">Best</th>
                      <th class="right">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each pagedAthBest as t, i}
                      <tr>
                        <td class="col-rank text-muted">{athBestPage * ATH_TARGETS_PAGE_SIZE + i + 1}</td>
                        <td><a href="/globals/target/{encodeURIComponent(t.target)}" class="target-link">{t.target}</a></td>
                        <td class="right">{t.count}</td>
                        <td class="right font-weight-bold">{formatPed(t.best_value)} PED</td>
                        <td class="right">{formatPed(t.total_value)} PED</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
              {#if athBestPages > 1}
                <div class="pagination">
                  <button disabled={athBestPage === 0} on:click={() => athBestPage--}>&laquo; Prev</button>
                  <span>{athBestPage + 1} / {athBestPages}</span>
                  <button disabled={athBestPage >= athBestPages - 1} on:click={() => athBestPage++}>Next &raquo;</button>
                </div>
              {/if}
            {:else}
              <p class="empty-state-sm">No target data available</p>
            {/if}
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
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

  .title-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
  }

  h1 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
  }

  .badge-team-header {
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.3px;
    text-transform: uppercase;
    background: rgba(96, 176, 255, 0.15);
    color: var(--accent-color);
  }

  .empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
    font-size: 0.9375rem;
  }

  .empty-state-sm {
    text-align: center;
    padding: 24px;
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  /* Stats */
  .stats-row {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }

  .stats-row.category-row {
    grid-template-columns: repeat(3, 1fr);
    margin-bottom: 20px;
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

  .stat-card.clickable {
    cursor: pointer;
    transition: border-color 0.15s ease;
  }

  .stat-card.clickable:hover {
    border-color: var(--accent-color);
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

  .stat-sub {
    display: block;
    font-size: 0.6875rem;
    color: var(--text-muted);
    margin-top: 2px;
    font-variant-numeric: tabular-nums;
  }

  .hunting-color { color: #ef4444; }
  .mining-color { color: #60b0ff; }
  .crafting-color { color: #f97316; }

  /* Tab Navigation */
  .player-tab-nav {
    display: flex;
    gap: 2px;
    margin-bottom: 20px;
    border-bottom: 1px solid var(--border-color);
  }

  .tab-link {
    padding: 10px 20px;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-muted);
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: all 0.15s ease;
    margin-bottom: -1px;
  }

  .tab-link:hover {
    color: var(--text-color);
  }

  .tab-link.active {
    color: var(--accent-color);
    border-bottom-color: var(--accent-color);
    font-weight: 600;
  }

  .loading-fade {
    opacity: 0.5;
    pointer-events: none;
    transition: opacity 0.15s ease;
  }

  /* Overview categories */
  .overview-categories {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 16px;
  }

  .overview-cat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    gap: 8px;
  }

  .overview-cat-header h2 {
    margin: 0;
    font-size: 0.875rem;
  }

  .view-all-btn {
    font-size: 0.75rem;
    color: var(--accent-color);
    background: none;
    border: none;
    cursor: pointer;
    white-space: nowrap;
  }

  .view-all-btn:hover {
    text-decoration: underline;
  }

  .top-loots-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .top-loot-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border-radius: 4px;
    font-size: 0.8125rem;
    border: 1px solid var(--border-color);
  }

  .top-loot-rank {
    font-size: 0.6875rem;
    color: var(--text-muted);
    min-width: 14px;
    text-align: center;
  }

  .top-loot-value {
    margin-left: auto;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .top-loot-time {
    font-size: 0.6875rem;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .overview-specials {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-bottom: 16px;
  }

  /* Side-by-side tab layout */
  .tab-side-by-side {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    align-items: start;
  }

  .tab-side-by-side .section-card {
    margin-bottom: 0;
  }

  /* Section title with icon */
  .section-title-icon {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .section-title-icon svg {
    width: 20px;
    height: 20px;
    flex-shrink: 0;
    opacity: 0.85;
  }

  /* Pagination */
  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-top: 12px;
    font-size: 0.8125rem;
  }

  .pagination button {
    padding: 4px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--secondary-color);
    color: var(--text-color);
    cursor: pointer;
    font-size: 0.75rem;
    transition: border-color 0.15s ease;
  }

  .pagination button:hover:not(:disabled) {
    border-color: var(--accent-color);
  }

  .pagination button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .pagination span {
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
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

  .overview-category {
    margin-bottom: 0;
  }

  .overview-specials .section-card {
    margin-bottom: 0;
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

  .col-rank {
    width: 32px;
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

  .target-link {
    color: var(--text-color);
    text-decoration: none;
  }

  .target-link:hover {
    color: var(--accent-color);
    text-decoration: underline;
  }

  .text-muted {
    color: var(--text-muted);
  }

  .font-weight-bold {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  /* Sort toggle */
  .sort-toggle {
    display: flex;
    gap: 2px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .sort-btn {
    padding: 4px 12px;
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

  /* ATH header */
  .ath-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    gap: 12px;
  }

  .ath-header h2 {
    margin: 0;
  }

  .ath-targets-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-bottom: 16px;
  }

  .ath-targets-grid .section-card {
    margin-bottom: 0;
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

    .stats-row.category-row {
      grid-template-columns: repeat(3, 1fr);
    }

    .overview-categories {
      grid-template-columns: 1fr;
    }

    .overview-specials {
      grid-template-columns: 1fr;
    }

    .ath-targets-grid {
      grid-template-columns: 1fr;
    }

    .tab-side-by-side {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 599px) {
    .stats-row {
      grid-template-columns: repeat(2, 1fr);
    }

    .stats-row.category-row {
      grid-template-columns: 1fr;
    }

    .player-tab-nav {
      overflow-x: auto;
    }
  }
</style>
