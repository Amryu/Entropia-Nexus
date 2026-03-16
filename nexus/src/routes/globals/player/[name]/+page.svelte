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
  import GlobalMediaDialog from '$lib/components/globals/GlobalMediaDialog.svelte';
  import GlobalMediaUpload from '$lib/components/globals/GlobalMediaUpload.svelte';
  import GzButton from '$lib/components/globals/GzButton.svelte';
  import Skeleton from '$lib/components/Skeleton.svelte';

  let { data } = $props();


  // Media dialog state
  let showMediaDialog = $state(false);
  let mediaDialogGlobal = $state(null);

  function openMediaDialog(g) {
    mediaDialogGlobal = g;
    showMediaDialog = true;
  }

  function onMediaUploaded(data) {
    const { type, globalId } = data;
    const update = (arr) => arr ? arr.map(g => {
      if (g.id === globalId) {
        return { ...g, media_image: type === 'image' ? true : g.media_image, media_video: type === 'video' ? true : g.media_video };
      }
      return g;
    }) : arr;
    if (playerData?.recent) playerData.recent = update(playerData.recent);
    if (playerData?.top_loots?.hunting) playerData.top_loots.hunting = update(playerData.top_loots.hunting);
    if (playerData?.top_loots?.mining) playerData.top_loots.mining = update(playerData.top_loots.mining);
    if (playerData?.top_loots?.crafting) playerData.top_loots.crafting = update(playerData.top_loots.crafting);
    if (playerData?.rare_items) playerData.rare_items = update(playerData.rare_items);
    if (playerData?.achievements) playerData.achievements = update(playerData.achievements);
    if (playerData?.pvp_events) playerData.pvp_events = update(playerData.pvp_events);
  }

  function onMediaDeleted(data) {
    const { globalId } = data;
    const update = (arr) => arr ? arr.map(g => {
      if (g.id === globalId) return { ...g, media_image: null, media_video: null };
      return g;
    }) : arr;
    if (playerData?.top_loots?.hunting) playerData.top_loots.hunting = update(playerData.top_loots.hunting);
    if (playerData?.top_loots?.mining) playerData.top_loots.mining = update(playerData.top_loots.mining);
    if (playerData?.top_loots?.crafting) playerData.top_loots.crafting = update(playerData.top_loots.crafting);
    if (playerData?.recent) playerData.recent = update(playerData.recent);
    if (playerData?.rare_items) playerData.rare_items = update(playerData.rare_items);
    if (playerData?.achievements) playerData.achievements = update(playerData.achievements);
    if (playerData?.pvp_events) playerData.pvp_events = update(playerData.pvp_events);
    showMediaDialog = false;
    mediaDialogGlobal = null;
  }

  let playerData = $state(null);
  let initialLoading = $state(true);
  let playerName = $derived(data.playerName);
  let recentSort = $state({ col: 'timestamp', asc: false });

  // Resolve streamed promise from server load function.
  // data.streamed.playerData is a promise (nested → not awaited during SSR).
  // Guard against overwriting data from fetchData() (period changes).
  let streamedResolved = false;
  $effect(() => {
    const incoming = data.streamed.playerData;
    if (incoming && typeof incoming.then === 'function') {
      initialLoading = true;
      streamedResolved = false;
      incoming.then(d => {
        if (!streamedResolved) {
          playerData = d;
          initialLoading = false;
          streamedResolved = true;
        }
      });
    } else if (!streamedResolved) {
      playerData = incoming;
      initialLoading = false;
      streamedResolved = true;
    }
  });

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
  let activeTab = $state('overview');

  let period = $state('all');
  let dateFrom = $state(null);
  let dateTo = $state(null);
  let loading = $state(false);

  function onDateRangeChange(data) {
    period = data.period;
    dateFrom = data.from;
    dateTo = data.to;
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
      } else if (res.status === 404) {
        // No data for this period — show empty summary
        playerData = { player: playerName, summary: { total_count: 0, total_value: 0, avg_value: 0, max_value: 0, hof_count: 0, ath_count: 0, kill_count: 0, team_kill_count: 0, hunting_value: 0, deposit_count: 0, mining_value: 0, craft_count: 0, crafting_value: 0, rare_count: 0, discovery_count: 0, tier_count: 0, pvp_count: 0, pvp_value: 0 }, hunting: [], mining: { resources: [] }, crafting: { items: [] }, activity: [], recent: [], achievements: [], rare_items: [], pvp_events: [], top_loots: { hunting: [], mining: [], crafting: [] }, ath_rankings: { hunting: [], mining: [], crafting: [], pvp: [] } };
      }
    } catch { /* ignore */ }
    loading = false;
    await tick();
    buildActivityChart();
  }

  // Expanded mobs (for maturity detail rows)
  let expandedMobs = $state(new Set());

  function toggleMob(key) {
    if (expandedMobs.has(key)) {
      expandedMobs.delete(key);
    } else {
      expandedMobs.add(key);
    }
    expandedMobs = new Set(expandedMobs);
  }

  // Sorting
  let huntSort = $state({ col: 'total_value', asc: false });
  let miningSort = $state({ col: 'total_value', asc: false });
  let craftSort = $state({ col: 'total_value', asc: false });


  // Pagination constants
  const PAGE_SIZE = 25;


  // Hunting tab pagination
  let huntTargetPage = $state(0);
  let huntLootPage = $state(0);
  let huntLootSort = $state({ col: 'value', asc: false });

  // Mining tab pagination
  let miningTargetPage = $state(0);
  let miningLootPage = $state(0);
  let miningLootSort = $state({ col: 'value', asc: false });

  // Crafting tab pagination
  let craftTargetPage = $state(0);
  let craftLootPage = $state(0);
  let craftLootSort = $state({ col: 'value', asc: false });

  // ATH rankings tab — auto-select category with most ranked entries
  const ATH_CATEGORIES = [
    { value: 'hunting', label: 'Hunting' },
    { value: 'mining', label: 'Mining' },
    { value: 'crafting', label: 'Crafting' },
    { value: 'pvp', label: 'PvP' },
  ];
  let athCategoryOverride = $state(null);


  // Rare finds sorting
  let rareFindSort = $state({ col: 'timestamp', asc: false });

  // PvP sorting
  let pvpSort = $state({ col: 'value', asc: false });

  // ATH pagination
  const ATH_PAGE_SIZE = 25;
  let athTotalPage = $state(0);
  let athBestPage = $state(0);
  let pagedAthByTotal = $derived(athByTotal.slice(athTotalPage * ATH_PAGE_SIZE, (athTotalPage + 1) * ATH_PAGE_SIZE));
  let pagedAthByBest = $derived(athByBest.slice(athBestPage * ATH_PAGE_SIZE, (athBestPage + 1) * ATH_PAGE_SIZE));
  let athTotalPages = $derived(Math.ceil(athByTotal.length / ATH_PAGE_SIZE));
  let athBestPages = $derived(Math.ceil(athByBest.length / ATH_PAGE_SIZE));

  // Reset ATH pagination when category changes
  $effect(() => {
    activeAthCategory;
    athTotalPage = 0;
    athBestPage = 0;
  });

  // Activity chart
  let activityCanvas = $state();
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

  // Build chart when data first becomes available (after streaming resolves)
  let chartBuilt = false;
  $effect(() => {
    if (playerData && !chartBuilt) {
      chartBuilt = true;
      tick().then(buildActivityChart);
    }
  });

  onDestroy(() => {
    if (activityChart) activityChart.destroy();
  });


  function handleSearchSelect({ name, type }) {
    if (type === 'Player' || type === 'Team') {
      goto(`/globals/player/${encodeURIComponent(name)}`);
    } else {
      goto(`/globals/target/${encodeURIComponent(name)}`);
    }
  }

  function handleSearch({ query }) {
    const q = query?.trim();
    if (q) goto(`/globals/player/${encodeURIComponent(q)}`);
  }



  const OVERVIEW_TOP_LIMIT = 10;
  let user = $derived(data?.session?.user || null);
  let summary = $derived(playerData?.summary);
  let hunting = $derived(playerData?.hunting || []);
  let mining = $derived(playerData?.mining?.resources || []);
  let crafting = $derived(playerData?.crafting?.items || []);
  let activity = $derived(playerData?.activity || []);
  let recent = $derived(playerData?.recent || []);
  let sortedRecent = $derived(recentSort.col === 'timestamp' && !recentSort.asc ? recent : sortedData(recent, recentSort));
  let achievements = $derived(playerData?.achievements || []);
  let rareItems = $derived(playerData?.rare_items || []);
  let topLoots = $derived(playerData?.top_loots || { hunting: [], mining: [], crafting: [] });
  let athRankings = $derived(playerData?.ath_rankings || { hunting: [], mining: [], crafting: [], pvp: [] });
  let isTeam = $derived(summary && summary.team_kill_count > 0 && summary.total_count === summary.team_kill_count);
  let tabs = $derived([
    ...BASE_TABS,
    ...EXTRA_TABS.filter(t => summary && summary[t.key] > 0),
    { value: 'aths', label: 'ATHs' },
  ]);
  let sortedHunting = $derived(sortedData(hunting, huntSort));
  let sortedMining = $derived(sortedData(mining, miningSort));
  let sortedCrafting = $derived(sortedData(crafting, craftSort));
  let huntTargetPages = $derived(Math.ceil(sortedHunting.length / PAGE_SIZE));
  let sortedHuntingLoots = $derived(sortedData(topLoots.hunting || [], huntLootSort));
  let huntLootPages = $derived(Math.ceil(sortedHuntingLoots.length / PAGE_SIZE));
  let pagedHunting = $derived(sortedHunting.slice(huntTargetPage * PAGE_SIZE, (huntTargetPage + 1) * PAGE_SIZE));
  let pagedHuntingLoots = $derived(sortedHuntingLoots.slice(huntLootPage * PAGE_SIZE, (huntLootPage + 1) * PAGE_SIZE));
  let miningTargetPages = $derived(Math.ceil(sortedMining.length / PAGE_SIZE));
  let sortedMiningLoots = $derived(sortedData(topLoots.mining || [], miningLootSort));
  let miningLootPages = $derived(Math.ceil(sortedMiningLoots.length / PAGE_SIZE));
  let pagedMining = $derived(sortedMining.slice(miningTargetPage * PAGE_SIZE, (miningTargetPage + 1) * PAGE_SIZE));
  let pagedMiningLoots = $derived(sortedMiningLoots.slice(miningLootPage * PAGE_SIZE, (miningLootPage + 1) * PAGE_SIZE));
  let craftTargetPages = $derived(Math.ceil(sortedCrafting.length / PAGE_SIZE));
  let sortedCraftingLoots = $derived(sortedData(topLoots.crafting || [], craftLootSort));
  let craftLootPages = $derived(Math.ceil(sortedCraftingLoots.length / PAGE_SIZE));
  let pagedCrafting = $derived(sortedCrafting.slice(craftTargetPage * PAGE_SIZE, (craftTargetPage + 1) * PAGE_SIZE));
  let pagedCraftingLoots = $derived(sortedCraftingLoots.slice(craftLootPage * PAGE_SIZE, (craftLootPage + 1) * PAGE_SIZE));
  let athCategory = $derived((() => {
    const counts = { hunting: 0, mining: 0, crafting: 0, pvp: 0 };
    for (const cat of ['hunting', 'mining', 'crafting']) {
      counts[cat] = (athRankings[cat] || []).length;
    }
    counts.pvp = (athRankings.pvp || []).length;
    const best = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
    return best[1] > 0 ? best[0] : 'hunting';
  })());
  let activeAthCategory = $derived(athCategoryOverride ?? athCategory);
  let athEntries = $derived(athRankings[activeAthCategory] || []);
  // ATH split into by_total and by_best (for hunting/mining/crafting)
  let athByTotal = $derived(activeAthCategory !== 'pvp'
    ? athEntries.filter(e => e.total_rank <= 500).sort((a, b) => a.total_rank - b.total_rank)
    : []);
  let athByBest = $derived(activeAthCategory !== 'pvp'
    ? athEntries.filter(e => e.best_rank <= 500).sort((a, b) => a.best_rank - b.best_rank)
    : []);
  let sortedRareItems = $derived(sortedData(rareItems, rareFindSort));
  let pvpEvents = $derived(playerData?.pvp_events || []);
  let sortedPvpEvents = $derived(sortedData(pvpEvents, pvpSort));
  $effect(() => {
    if (activityCanvas && activity.length && activeTab === 'overview') {
      tick().then(buildActivityChart);
    }
  });
  // Tab-specific data
  let discoveries = $derived(achievements.filter(a => a.type === 'discovery'));
  let tierRecords = $derived(achievements.filter(a => a.type === 'tier'));
  // Overview helpers
  let overviewRareItems = $derived(rareItems.slice(0, 5));
  let overviewDiscoveries = $derived(discoveries.slice(0, 5));
  let overviewTopHunting = $derived(topLoots.hunting.slice(0, OVERVIEW_TOP_LIMIT));
  let overviewTopMining = $derived(topLoots.mining.slice(0, OVERVIEW_TOP_LIMIT));
  let overviewTopCrafting = $derived(topLoots.crafting.slice(0, OVERVIEW_TOP_LIMIT));
</script>

<svelte:head>
  <title>{playerName} - Globals - Entropia Nexus</title>
  <meta name="description" content="Global event statistics for {playerName} in Entropia Universe." />
  <link rel="canonical" href="https://entropianexus.com/globals/player/{encodeURIComponent(playerName)}" />
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
          onselect={handleSearchSelect}
          onsearch={handleSearch}
        />
      </div>
    </div>
  </div>

  {#if initialLoading}
    <div class="skeleton-container">
      <div class="skeleton-stats">
        <Skeleton variant="rect" height="80px" />
        <Skeleton variant="rect" height="80px" />
        <Skeleton variant="rect" height="80px" />
        <Skeleton variant="rect" height="80px" />
      </div>
      <Skeleton variant="rect" height="200px" />
      <Skeleton variant="rect" height="300px" />
    </div>
  {:else if !playerData || !summary}
    <p class="empty-state">No globals recorded for this player</p>
  {:else}
  <div class:loading-fade={loading}>
    <!-- Period Selector -->
    <GlobalsDateRangePicker {period} from={dateFrom} to={dateTo} disabled={loading} onchange={onDateRangeChange} />

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
      <button class="stat-card category-card clickable" onclick={() => activeTab = 'hunting'}>
        <span class="stat-value hunting-color">{(summary.kill_count + summary.team_kill_count).toLocaleString()}</span>
        <span class="stat-label">Hunting</span>
        <span class="stat-sub">{formatPed(summary.hunting_value)} PED</span>
      </button>
      <button class="stat-card category-card clickable" onclick={() => activeTab = 'mining'}>
        <span class="stat-value mining-color">{summary.deposit_count.toLocaleString()}</span>
        <span class="stat-label">Mining</span>
        <span class="stat-sub">{formatPed(summary.mining_value)} PED</span>
      </button>
      <button class="stat-card category-card clickable" onclick={() => activeTab = 'crafting'}>
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
            onclick={() => activeTab = tab.value}
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
          <div class="section-card overview-category">
            <div class="overview-cat-header">
              <h2>Top Hunting Loots</h2>
              <button class="view-all-btn" onclick={() => activeTab = 'hunting'}>View all &rarr;</button>
            </div>
            {#if overviewTopHunting.length > 0}
              <div class="top-loots-list">
                {#each overviewTopHunting as loot, i}
                  <div class="top-loot-item">
                    <span class="top-loot-rank">{i + 1}</span>
                    <a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link top-loot-target" title={loot.target}>{loot.target}</a>
                    <span class="top-loot-value">{formatPed(loot.value)} PED</span>
                    <span class="badge-slot">{#if loot.ath}<span class="badge-ath">ATH</span>{:else if loot.hof}<span class="badge-hof">HoF</span>{/if}</span>
                    <span class="top-loot-actions">
                      {#if loot.media_image || loot.media_video}
                        <button class="media-icon-btn" title="View media" onclick={() => openMediaDialog(loot)}>
                          {#if loot.media_image}
                            <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                          {:else}
                            <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                          {/if}
                        </button>
                      {:else if user}
                        <GlobalMediaUpload globalId={loot.id} {playerName} {user} onuploaded={onMediaUploaded} />
                      {/if}
                      <GzButton globalId={loot.id} count={loot.gz_count || 0} userGz={loot.user_gz || false} {user} compact />
                    </span>
                  </div>
                {/each}
              </div>
            {:else}
              <p class="empty-state-sm">No hunting globals recorded</p>
            {/if}
          </div>

          <div class="section-card overview-category">
            <div class="overview-cat-header">
              <h2>Top Mining Loots</h2>
              <button class="view-all-btn" onclick={() => activeTab = 'mining'}>View all &rarr;</button>
            </div>
            {#if overviewTopMining.length > 0}
              <div class="top-loots-list">
                {#each overviewTopMining as loot, i}
                  <div class="top-loot-item">
                    <span class="top-loot-rank">{i + 1}</span>
                    <a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link top-loot-target" title={loot.target}>{loot.target}</a>
                    <span class="top-loot-value">{formatPed(loot.value)} PED</span>
                    <span class="badge-slot">{#if loot.ath}<span class="badge-ath">ATH</span>{:else if loot.hof}<span class="badge-hof">HoF</span>{/if}</span>
                    <span class="top-loot-actions">
                      {#if loot.media_image || loot.media_video}
                        <button class="media-icon-btn" title="View media" onclick={() => openMediaDialog(loot)}>
                          {#if loot.media_image}
                            <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                          {:else}
                            <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                          {/if}
                        </button>
                      {:else if user}
                        <GlobalMediaUpload globalId={loot.id} {playerName} {user} onuploaded={onMediaUploaded} />
                      {/if}
                      <GzButton globalId={loot.id} count={loot.gz_count || 0} userGz={loot.user_gz || false} {user} compact />
                    </span>
                  </div>
                {/each}
              </div>
            {:else}
              <p class="empty-state-sm">No mining globals recorded</p>
            {/if}
          </div>

          <div class="section-card overview-category">
            <div class="overview-cat-header">
              <h2>Top Crafting Loots</h2>
              <button class="view-all-btn" onclick={() => activeTab = 'crafting'}>View all &rarr;</button>
            </div>
            {#if overviewTopCrafting.length > 0}
              <div class="top-loots-list">
                {#each overviewTopCrafting as loot, i}
                  <div class="top-loot-item">
                    <span class="top-loot-rank">{i + 1}</span>
                    <a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link top-loot-target" title={loot.target}>{loot.target}</a>
                    <span class="top-loot-value">{formatPed(loot.value)} PED</span>
                    <span class="badge-slot">{#if loot.ath}<span class="badge-ath">ATH</span>{:else if loot.hof}<span class="badge-hof">HoF</span>{/if}</span>
                    <span class="top-loot-actions">
                      {#if loot.media_image || loot.media_video}
                        <button class="media-icon-btn" title="View media" onclick={() => openMediaDialog(loot)}>
                          {#if loot.media_image}
                            <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                          {:else}
                            <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                          {/if}
                        </button>
                      {:else if user}
                        <GlobalMediaUpload globalId={loot.id} {playerName} {user} onuploaded={onMediaUploaded} />
                      {/if}
                      <GzButton globalId={loot.id} count={loot.gz_count || 0} userGz={loot.user_gz || false} {user} compact />
                    </span>
                  </div>
                {/each}
              </div>
            {:else}
              <p class="empty-state-sm">No crafting globals recorded</p>
            {/if}
          </div>
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
                      <th class="right col-value">Value</th>
                      <th class="col-badge"></th>
                      <th class="col-media"></th>
                      <th class="col-gz"></th>
                      <th class="col-time">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each overviewRareItems as item}
                      <tr>
                        <td>{item.target}</td>
                        <td class="right">{formatPed(item.value)} PED</td>
                        <td class="col-badge">{#if item.ath}<span class="badge-ath">ATH</span>{:else if item.hof}<span class="badge-hof">HoF</span>{/if}</td>
                        <td class="col-media">
                          {#if item.media_image || item.media_video}
                            <button class="media-icon-btn" title="View media" onclick={() => openMediaDialog(item)}>
                              {#if item.media_image}
                                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                              {:else}
                                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                              {/if}
                            </button>
                          {:else if user}
                            <GlobalMediaUpload globalId={item.id} {playerName} {user} onuploaded={onMediaUploaded} />
                          {/if}
                        </td>
                        <td class="col-gz"><GzButton globalId={item.id} count={item.gz_count || 0} userGz={item.user_gz || false} {user} compact /></td>
                        <td class="text-muted col-time" title={new Date(item.timestamp).toLocaleString()}>{timeAgo(item.timestamp)}</td>
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
                    <span class="achievement-target">{ach.target}{#if ach.location}&nbsp;<span class="achievement-location">in {ach.location}</span>{/if}</span>
                    <span class="achievement-actions">
                      {#if ach.media_image || ach.media_video}
                        <button class="media-icon-btn" title="View media" onclick={() => openMediaDialog(ach)}>
                          {#if ach.media_image}
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                          {:else}
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                          {/if}
                        </button>
                      {:else if user}
                        <GlobalMediaUpload globalId={ach.id} {playerName} {user} onuploaded={onMediaUploaded} />
                      {/if}
                      <GzButton globalId={ach.id} count={ach.gz_count || 0} userGz={ach.user_gz || false} {user} compact />
                    </span>
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
        <div class="section-card">
          <h2>Activity</h2>
          {#if activity.length > 0}
            <div class="chart-container">
              <canvas bind:this={activityCanvas}></canvas>
            </div>
          {:else}
            <p class="empty-state-sm">No activity data for this period</p>
          {/if}
        </div>

        <!-- Recent Globals -->
        <div class="section-card">
          <h2>Recent Globals</h2>
          {#if recent.length > 0}
            <div class="table-wrapper">
              <table class="data-table">
                <thead>
                  <tr>
                    <th class="sortable col-time" onclick={() => recentSort = toggleSort(recentSort, 'timestamp')}>Time{sortIcon(recentSort, 'timestamp')}</th>
                    <th class="sortable col-type" onclick={() => recentSort = toggleSort(recentSort, 'type')}>Type{sortIcon(recentSort, 'type')}</th>
                    <th class="sortable" onclick={() => recentSort = toggleSort(recentSort, 'target')}>Target{sortIcon(recentSort, 'target')}</th>
                    <th class="sortable right col-value" onclick={() => recentSort = toggleSort(recentSort, 'value')}>Value{sortIcon(recentSort, 'value')}</th>
                    <th class="col-badge"></th>
                    <th class="col-media"></th>
                    <th class="col-gz"></th>
                  </tr>
                </thead>
                <tbody>
                  {#each sortedRecent as g}
                    {@const tc = TYPE_CONFIG[g.type] || { label: g.type, cssClass: '' }}
                    <tr>
                      <td class="text-muted col-time" title={new Date(g.timestamp).toLocaleString()}>{timeAgo(g.timestamp)}</td>
                      <td class="col-type"><span class="type-badge {tc.cssClass}">{tc.label}</span></td>
                      <td><a href="/globals/target/{encodeURIComponent(g.target)}" class="target-link">{g.target}</a></td>
                      <td class="right font-weight-bold">{formatValue(g.value, g.unit, g.type)}</td>
                      <td class="col-badge">
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
                        {:else if user}
                          <GlobalMediaUpload globalId={g.id} {playerName} {user} onuploaded={onMediaUploaded} />
                        {/if}
                      </td>
                      <td class="col-gz"><GzButton globalId={g.id} count={g.gz_count || 0} userGz={g.user_gz || false} {user} compact /></td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {:else}
            <p class="empty-state-sm">No recent globals for this period</p>
          {/if}
        </div>

      <!-- === HUNTING TAB === -->
      {:else if activeTab === 'hunting'}
        <div class="tab-side-by-side">
          <div class="section-card">
            <h2 class="section-title-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="22" y1="2" x2="12" y2="12"/></svg>
              Mob Breakdown
            </h2>
            {#if hunting.length > 0}
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th class="sortable" onclick={() => { huntSort = toggleSort(huntSort, 'target'); huntTargetPage = 0; }}>
                        Target{sortIcon(huntSort, 'target')}
                      </th>
                      <th class="sortable right col-value" onclick={() => { huntSort = toggleSort(huntSort, 'kills'); huntTargetPage = 0; }}>
                        Kills{sortIcon(huntSort, 'kills')}
                      </th>
                      <th class="sortable right col-value" onclick={() => { huntSort = toggleSort(huntSort, 'total_value'); huntTargetPage = 0; }}>
                        Total{sortIcon(huntSort, 'total_value')}
                      </th>
                      <th class="right col-value col-hide-mobile">Best</th>
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
                        onclick={() => hasDetails && toggleMob(mobKey)}
                      >
                        <td>
                          {#if hasDetails}
                            <span class="expand-icon">{expandedMobs.has(mobKey) ? '\u25BC' : '\u25B6'}</span>
                          {/if}
                          <a href="/globals/target/{encodeURIComponent(displayName)}" class="target-link" onclick={(e) => e.stopPropagation()}>{displayName}</a>
                        </td>
                        <td class="right">{mob.kills}</td>
                        <td class="right">{formatPed(mob.total_value)}</td>
                        <td class="right col-hide-mobile">{formatPed(mob.best_value)}</td>
                      </tr>
                      {#if hasDetails && expandedMobs.has(mobKey)}
                        {#each mob.maturities as mat}
                          <tr class="maturity-row">
                            <td class="indent"><a href="/globals/target/{encodeURIComponent(mat.target)}" class="target-link">{mat.target}</a></td>
                            <td class="right">{mat.kills}</td>
                            <td class="right">{formatPed(mat.total_value)}</td>
                            <td class="right col-hide-mobile">{formatPed(mat.best_value)}</td>
                          </tr>
                        {/each}
                      {/if}
                    {/each}
                  </tbody>
                </table>
              </div>
              {#if huntTargetPages > 1}
                <div class="pagination">
                  <button disabled={huntTargetPage === 0} onclick={() => huntTargetPage--}>&laquo; Prev</button>
                  <span>{huntTargetPage + 1} / {huntTargetPages}</span>
                  <button disabled={huntTargetPage >= huntTargetPages - 1} onclick={() => huntTargetPage++}>Next &raquo;</button>
                </div>
              {/if}
            {:else}
              <p class="empty-state-sm">No hunting globals for this period</p>
            {/if}
          </div>

          <div class="section-card">
            <h2 class="section-title-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
              Top Individual Loots
            </h2>
            {#if topLoots.hunting.length > 0}
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th class="col-rank right">#</th>
                      <th class="sortable" onclick={() => { huntLootSort = toggleSort(huntLootSort, 'target'); huntLootPage = 0; }}>Target{sortIcon(huntLootSort, 'target')}</th>
                      <th class="sortable right col-value" onclick={() => { huntLootSort = toggleSort(huntLootSort, 'value'); huntLootPage = 0; }}>Value{sortIcon(huntLootSort, 'value')}</th>
                      <th class="col-badge"></th>
                      <th class="col-media"></th>
                      <th class="col-gz"></th>
                      <th class="sortable col-time" onclick={() => { huntLootSort = toggleSort(huntLootSort, 'timestamp'); huntLootPage = 0; }}>Time{sortIcon(huntLootSort, 'timestamp')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each pagedHuntingLoots as loot, i}
                      <tr>
                        <td class="col-rank text-muted">{huntLootPage * PAGE_SIZE + i + 1}</td>
                        <td><a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link">{loot.target}</a></td>
                        <td class="right font-weight-bold">{formatPed(loot.value)} PED</td>
                        <td class="col-badge">{#if loot.ath}<span class="badge-ath">ATH</span>{:else if loot.hof}<span class="badge-hof">HoF</span>{/if}</td>
                        <td class="col-media">
                          {#if loot.media_image || loot.media_video}
                            <button class="media-icon-btn" title="View media" onclick={() => openMediaDialog(loot)}>
                              {#if loot.media_image}
                                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                              {:else}
                                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                              {/if}
                            </button>
                          {:else if user}
                            <GlobalMediaUpload globalId={loot.id} {playerName} {user} onuploaded={onMediaUploaded} />
                          {/if}
                        </td>
                        <td class="col-gz"><GzButton globalId={loot.id} count={loot.gz_count || 0} userGz={loot.user_gz || false} {user} compact /></td>
                        <td class="text-muted col-time" title={new Date(loot.timestamp).toLocaleString()}>{timeAgo(loot.timestamp)}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
              {#if huntLootPages > 1}
                <div class="pagination">
                  <button disabled={huntLootPage === 0} onclick={() => huntLootPage--}>&laquo; Prev</button>
                  <span>{huntLootPage + 1} / {huntLootPages}</span>
                  <button disabled={huntLootPage >= huntLootPages - 1} onclick={() => huntLootPage++}>Next &raquo;</button>
                </div>
              {/if}
            {:else}
              <p class="empty-state-sm">No hunting HoFs recorded</p>
            {/if}
          </div>
        </div>

      <!-- === MINING TAB === -->
      {:else if activeTab === 'mining'}
        <div class="tab-side-by-side">
          <div class="section-card">
            <h2 class="section-title-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="#60b0ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 22l10-10"/><path d="M16 8l-4 4"/><path d="M22 2l-5.5 5.5"/><circle cx="18" cy="6" r="3"/></svg>
              Resource Breakdown
            </h2>
            {#if mining.length > 0}
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th class="sortable" onclick={() => { miningSort = toggleSort(miningSort, 'target'); miningTargetPage = 0; }}>
                        Resource{sortIcon(miningSort, 'target')}
                      </th>
                      <th class="sortable right col-value" onclick={() => { miningSort = toggleSort(miningSort, 'finds'); miningTargetPage = 0; }}>
                        Finds{sortIcon(miningSort, 'finds')}
                      </th>
                      <th class="sortable right col-value" onclick={() => { miningSort = toggleSort(miningSort, 'total_value'); miningTargetPage = 0; }}>
                        Total{sortIcon(miningSort, 'total_value')}
                      </th>
                      <th class="right col-value col-hide-mobile">Best</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each pagedMining as res}
                      <tr>
                        <td><a href="/globals/target/{encodeURIComponent(res.target)}" class="target-link">{res.target}</a></td>
                        <td class="right">{res.finds}</td>
                        <td class="right">{formatPed(res.total_value)}</td>
                        <td class="right col-hide-mobile">{formatPed(res.best_value)}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
              {#if miningTargetPages > 1}
                <div class="pagination">
                  <button disabled={miningTargetPage === 0} onclick={() => miningTargetPage--}>&laquo; Prev</button>
                  <span>{miningTargetPage + 1} / {miningTargetPages}</span>
                  <button disabled={miningTargetPage >= miningTargetPages - 1} onclick={() => miningTargetPage++}>Next &raquo;</button>
                </div>
              {/if}
            {:else}
              <p class="empty-state-sm">No mining globals for this period</p>
            {/if}
          </div>

          <div class="section-card">
            <h2 class="section-title-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="#60b0ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
              Top Individual Loots
            </h2>
            {#if topLoots.mining.length > 0}
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th class="col-rank right">#</th>
                      <th class="sortable" onclick={() => { miningLootSort = toggleSort(miningLootSort, 'target'); miningLootPage = 0; }}>Resource{sortIcon(miningLootSort, 'target')}</th>
                      <th class="sortable right col-value" onclick={() => { miningLootSort = toggleSort(miningLootSort, 'value'); miningLootPage = 0; }}>Value{sortIcon(miningLootSort, 'value')}</th>
                      <th class="col-badge"></th>
                      <th class="col-media"></th>
                      <th class="col-gz"></th>
                      <th class="sortable col-time" onclick={() => { miningLootSort = toggleSort(miningLootSort, 'timestamp'); miningLootPage = 0; }}>Time{sortIcon(miningLootSort, 'timestamp')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each pagedMiningLoots as loot, i}
                      <tr>
                        <td class="col-rank text-muted">{miningLootPage * PAGE_SIZE + i + 1}</td>
                        <td><a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link">{loot.target}</a></td>
                        <td class="right font-weight-bold">{formatPed(loot.value)} PED</td>
                        <td class="col-badge">{#if loot.ath}<span class="badge-ath">ATH</span>{:else if loot.hof}<span class="badge-hof">HoF</span>{/if}</td>
                        <td class="col-media">
                          {#if loot.media_image || loot.media_video}
                            <button class="media-icon-btn" title="View media" onclick={() => openMediaDialog(loot)}>
                              {#if loot.media_image}
                                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                              {:else}
                                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                              {/if}
                            </button>
                          {:else if user}
                            <GlobalMediaUpload globalId={loot.id} {playerName} {user} onuploaded={onMediaUploaded} />
                          {/if}
                        </td>
                        <td class="col-gz"><GzButton globalId={loot.id} count={loot.gz_count || 0} userGz={loot.user_gz || false} {user} compact /></td>
                        <td class="text-muted col-time" title={new Date(loot.timestamp).toLocaleString()}>{timeAgo(loot.timestamp)}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
              {#if miningLootPages > 1}
                <div class="pagination">
                  <button disabled={miningLootPage === 0} onclick={() => miningLootPage--}>&laquo; Prev</button>
                  <span>{miningLootPage + 1} / {miningLootPages}</span>
                  <button disabled={miningLootPage >= miningLootPages - 1} onclick={() => miningLootPage++}>Next &raquo;</button>
                </div>
              {/if}
            {:else}
              <p class="empty-state-sm">No mining HoFs recorded</p>
            {/if}
          </div>
        </div>

      <!-- === CRAFTING TAB === -->
      {:else if activeTab === 'crafting'}
        <div class="tab-side-by-side">
          <div class="section-card">
            <h2 class="section-title-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
              Item Breakdown
            </h2>
            {#if crafting.length > 0}
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th class="sortable" onclick={() => { craftSort = toggleSort(craftSort, 'target'); craftTargetPage = 0; }}>
                        Item{sortIcon(craftSort, 'target')}
                      </th>
                      <th class="sortable right col-value" onclick={() => { craftSort = toggleSort(craftSort, 'crafts'); craftTargetPage = 0; }}>
                        Crafts{sortIcon(craftSort, 'crafts')}
                      </th>
                      <th class="sortable right col-value" onclick={() => { craftSort = toggleSort(craftSort, 'total_value'); craftTargetPage = 0; }}>
                        Total{sortIcon(craftSort, 'total_value')}
                      </th>
                      <th class="right col-value col-hide-mobile">Best</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each pagedCrafting as item}
                      <tr>
                        <td><a href="/globals/target/{encodeURIComponent(item.target)}" class="target-link">{item.target}</a></td>
                        <td class="right">{item.crafts}</td>
                        <td class="right">{formatPed(item.total_value)}</td>
                        <td class="right col-hide-mobile">{formatPed(item.best_value)}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
              {#if craftTargetPages > 1}
                <div class="pagination">
                  <button disabled={craftTargetPage === 0} onclick={() => craftTargetPage--}>&laquo; Prev</button>
                  <span>{craftTargetPage + 1} / {craftTargetPages}</span>
                  <button disabled={craftTargetPage >= craftTargetPages - 1} onclick={() => craftTargetPage++}>Next &raquo;</button>
                </div>
              {/if}
            {:else}
              <p class="empty-state-sm">No crafting globals for this period</p>
            {/if}
          </div>

          <div class="section-card">
            <h2 class="section-title-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
              Top Individual Loots
            </h2>
            {#if topLoots.crafting.length > 0}
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th class="col-rank right">#</th>
                      <th class="sortable" onclick={() => { craftLootSort = toggleSort(craftLootSort, 'target'); craftLootPage = 0; }}>Item{sortIcon(craftLootSort, 'target')}</th>
                      <th class="sortable right col-value" onclick={() => { craftLootSort = toggleSort(craftLootSort, 'value'); craftLootPage = 0; }}>Value{sortIcon(craftLootSort, 'value')}</th>
                      <th class="col-badge"></th>
                      <th class="col-media"></th>
                      <th class="col-gz"></th>
                      <th class="sortable col-time" onclick={() => { craftLootSort = toggleSort(craftLootSort, 'timestamp'); craftLootPage = 0; }}>Time{sortIcon(craftLootSort, 'timestamp')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each pagedCraftingLoots as loot, i}
                      <tr>
                        <td class="col-rank text-muted">{craftLootPage * PAGE_SIZE + i + 1}</td>
                        <td><a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link">{loot.target}</a></td>
                        <td class="right font-weight-bold">{formatPed(loot.value)} PED</td>
                        <td class="col-badge">{#if loot.ath}<span class="badge-ath">ATH</span>{:else if loot.hof}<span class="badge-hof">HoF</span>{/if}</td>
                        <td class="col-media">
                          {#if loot.media_image || loot.media_video}
                            <button class="media-icon-btn" title="View media" onclick={() => openMediaDialog(loot)}>
                              {#if loot.media_image}
                                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                              {:else}
                                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                              {/if}
                            </button>
                          {:else if user}
                            <GlobalMediaUpload globalId={loot.id} {playerName} {user} onuploaded={onMediaUploaded} />
                          {/if}
                        </td>
                        <td class="col-gz"><GzButton globalId={loot.id} count={loot.gz_count || 0} userGz={loot.user_gz || false} {user} compact /></td>
                        <td class="text-muted col-time" title={new Date(loot.timestamp).toLocaleString()}>{timeAgo(loot.timestamp)}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
              {#if craftLootPages > 1}
                <div class="pagination">
                  <button disabled={craftLootPage === 0} onclick={() => craftLootPage--}>&laquo; Prev</button>
                  <span>{craftLootPage + 1} / {craftLootPages}</span>
                  <button disabled={craftLootPage >= craftLootPages - 1} onclick={() => craftLootPage++}>Next &raquo;</button>
                </div>
              {/if}
            {:else}
              <p class="empty-state-sm">No crafting HoFs recorded</p>
            {/if}
          </div>
        </div>

      <!-- === RARE FINDS TAB === -->
      {:else if activeTab === 'rare'}
        <div class="section-card">
          <h2>Rare Finds ({summary.rare_count.toLocaleString()})</h2>
          {#if rareItems.length > 0}
            <div class="table-wrapper">
              <table class="data-table">
                <thead>
                  <tr>
                    <th class="sortable" onclick={() => rareFindSort = toggleSort(rareFindSort, 'target')}>Item{sortIcon(rareFindSort, 'target')}</th>
                    <th class="sortable right col-value" onclick={() => rareFindSort = toggleSort(rareFindSort, 'value')}>Value{sortIcon(rareFindSort, 'value')}</th>
                    <th class="col-badge"></th>
                    <th class="col-media"></th>
                    <th class="col-gz"></th>
                    <th class="sortable col-time" onclick={() => rareFindSort = toggleSort(rareFindSort, 'timestamp')}>Time{sortIcon(rareFindSort, 'timestamp')}</th>
                  </tr>
                </thead>
                <tbody>
                  {#each sortedRareItems as item}
                    <tr>
                      <td>{item.target}</td>
                      <td class="right font-weight-bold">{formatPed(item.value)} PED</td>
                      <td class="col-badge">{#if item.ath}<span class="badge-ath">ATH</span>{:else if item.hof}<span class="badge-hof">HoF</span>{/if}</td>
                      <td class="col-media">
                        {#if item.media_image || item.media_video}
                          <button class="media-icon-btn" title="View media" onclick={() => openMediaDialog(item)}>
                            {#if item.media_image}
                              <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                            {:else}
                              <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                            {/if}
                          </button>
                        {:else if user}
                          <GlobalMediaUpload globalId={item.id} {playerName} {user} onuploaded={onMediaUploaded} />
                        {/if}
                      </td>
                      <td class="col-gz"><GzButton globalId={item.id} count={item.gz_count || 0} userGz={item.user_gz || false} {user} compact /></td>
                      <td class="text-muted col-time" title={new Date(item.timestamp).toLocaleString()}>{timeAgo(item.timestamp)}</td>
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
                  <span class="achievement-target">{ach.target}{#if ach.location}&nbsp;<span class="achievement-location">in {ach.location}</span>{/if}</span>
                  {#if ach.hof}<span class="badge-hof">HoF</span>{/if}
                  {#if ach.ath}<span class="badge-ath">ATH</span>{/if}
                  <span class="achievement-actions">
                    {#if ach.media_image || ach.media_video}
                      <button class="media-icon-btn" title="View media" onclick={() => openMediaDialog(ach)}>
                        {#if ach.media_image}
                          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                        {:else}
                          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                        {/if}
                      </button>
                    {:else if user}
                      <GlobalMediaUpload globalId={ach.id} {playerName} {user} onuploaded={onMediaUploaded} />
                    {/if}
                    <GzButton globalId={ach.id} count={ach.gz_count || 0} userGz={ach.user_gz || false} {user} compact />
                  </span>
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
                  <span class="achievement-actions">
                    {#if ach.media_image || ach.media_video}
                      <button class="media-icon-btn" title="View media" onclick={() => openMediaDialog(ach)}>
                        {#if ach.media_image}
                          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                        {:else}
                          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                        {/if}
                      </button>
                    {:else if user}
                      <GlobalMediaUpload globalId={ach.id} {playerName} {user} onuploaded={onMediaUploaded} />
                    {/if}
                    <GzButton globalId={ach.id} count={ach.gz_count || 0} userGz={ach.user_gz || false} {user} compact />
                  </span>
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
          <h2>PvP ({summary.pvp_count.toLocaleString()} globals, {Math.round(summary.pvp_value)} Kills)</h2>
          {#if pvpEvents.length > 0}
            <div class="table-wrapper">
              <table class="data-table">
                <thead>
                  <tr>
                    <th class="sortable right col-value" onclick={() => pvpSort = toggleSort(pvpSort, 'value')}>Value{sortIcon(pvpSort, 'value')}</th>
                    <th class="col-badge"></th>
                    <th class="col-media"></th>
                    <th class="col-gz"></th>
                    <th class="sortable col-time" onclick={() => pvpSort = toggleSort(pvpSort, 'timestamp')}>Time{sortIcon(pvpSort, 'timestamp')}</th>
                  </tr>
                </thead>
                <tbody>
                  {#each sortedPvpEvents as g}
                    <tr>
                      <td class="right font-weight-bold">{Math.round(g.value)} Kills</td>
                      <td class="col-badge">
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
                        {:else if user}
                          <GlobalMediaUpload globalId={g.id} {playerName} {user} onuploaded={onMediaUploaded} />
                        {/if}
                      </td>
                      <td class="col-gz"><GzButton globalId={g.id} count={g.gz_count || 0} userGz={g.user_gz || false} {user} compact /></td>
                      <td class="text-muted col-time" title={new Date(g.timestamp).toLocaleString()}>{timeAgo(g.timestamp)}</td>
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
        <!-- ATH Rankings — show targets where this player ranks in top 500 -->
        <div class="section-card">
          <div class="ath-header">
            <h2 class="section-title-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="#eab308" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
              Personal ATH Rankings
            </h2>
            <div class="sort-toggle desktop-only">
              {#each ATH_CATEGORIES as cat}
                <button class="sort-btn" class:active={activeAthCategory === cat.value} onclick={() => { athCategoryOverride = cat.value; }}>{cat.label}</button>
              {/each}
            </div>
            <select class="sort-select mobile-only" value={activeAthCategory} onchange={(e) => { athCategoryOverride = e.target.value; }}>
              {#each ATH_CATEGORIES as cat}
                <option value={cat.value}>{cat.label}</option>
              {/each}
            </select>
          </div>

          {#if activeAthCategory === 'pvp'}
            <!-- PvP HoF rankings -->
            {#if athRankings.pvp.length > 0}
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th class="col-rank">Rank</th>
                      <th class="right col-value">Value</th>
                      <th class="col-badge"></th>
                      <th class="col-media"></th>
                      <th class="col-gz"></th>
                      <th class="col-time">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each athRankings.pvp as entry}
                      <tr>
                        <td class="col-rank"><span class="rank-badge" class:rank-ruby={entry.rank <= 1} class:rank-diamond={entry.rank > 1 && entry.rank <= 10} class:rank-gold={entry.rank > 10 && entry.rank <= 50} class:rank-silver={entry.rank > 50 && entry.rank <= 200} class:rank-bronze={entry.rank > 200 && entry.rank <= 500}>#{entry.rank}</span></td>
                        <td class="right font-weight-bold">{Math.round(entry.value)} Kills</td>
                        <td class="col-badge">{#if entry.ath}<span class="badge-ath">ATH</span>{:else if entry.hof}<span class="badge-hof">HoF</span>{/if}</td>
                        <td class="col-media">
                          {#if entry.media_image || entry.media_video}
                            <button class="media-icon-btn" title="View media" onclick={() => openMediaDialog(entry)}>
                              {#if entry.media_image}
                                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                              {:else}
                                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                              {/if}
                            </button>
                          {:else if user}
                            <GlobalMediaUpload globalId={entry.id} {playerName} {user} onuploaded={onMediaUploaded} />
                          {/if}
                        </td>
                        <td class="col-gz"><GzButton globalId={entry.id} count={entry.gz_count || 0} userGz={entry.user_gz || false} {user} compact /></td>
                        <td class="text-muted col-time" title={new Date(entry.timestamp).toLocaleString()}>{timeAgo(entry.timestamp)}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {:else}
              <p class="empty-state-sm">No PvP rankings for this player</p>
            {/if}
          {:else}
            <!-- Hunting / Mining / Crafting rankings -->
            {#if athByTotal.length === 0 && athByBest.length === 0}
              <p class="empty-state-sm">No top 500 rankings for {activeAthCategory} targets</p>
            {:else}
              <div class="ath-targets-grid">
                <div class="section-card-inner">
                  <h3 class="section-subtitle">By Single Loot</h3>
                  {#if athByBest.length > 0}
                    <div class="ath-count">{athByBest.length} target{athByBest.length !== 1 ? 's' : ''} ranked</div>
                    <div class="table-wrapper">
                      <table class="data-table">
                        <thead>
                          <tr>
                            <th class="col-rank">Rank</th>
                            <th>Target</th>
                            <th class="right col-count">#</th>
                            <th class="right col-value">Best Loot</th>
                          </tr>
                        </thead>
                        <tbody>
                          {#each pagedAthByBest as t}
                            <tr>
                              <td class="col-rank"><span class="rank-badge" class:rank-ruby={t.best_rank <= 1} class:rank-diamond={t.best_rank > 1 && t.best_rank <= 10} class:rank-gold={t.best_rank > 10 && t.best_rank <= 50} class:rank-silver={t.best_rank > 50 && t.best_rank <= 200} class:rank-bronze={t.best_rank > 200 && t.best_rank <= 500}>#{t.best_rank}</span></td>
                              <td><a href="/globals/target/{encodeURIComponent(t.target)}" class="target-link">{t.best_target || t.target}</a></td>
                              <td class="right col-count">{t.count}</td>
                              <td class="right font-weight-bold">{formatPed(t.best_value)} PED</td>
                            </tr>
                          {/each}
                        </tbody>
                      </table>
                    </div>
                    {#if athBestPages > 1}
                      <div class="pagination">
                        <button class="page-btn" disabled={athBestPage === 0} onclick={() => athBestPage--}>&laquo; Prev</button>
                        <span class="page-info">{athBestPage + 1} / {athBestPages}</span>
                        <button class="page-btn" disabled={athBestPage >= athBestPages - 1} onclick={() => athBestPage++}>Next &raquo;</button>
                      </div>
                    {/if}
                  {:else}
                    <p class="empty-state-sm">No single loot rankings</p>
                  {/if}
                </div>

                <div class="section-card-inner">
                  <h3 class="section-subtitle">By Total Value</h3>
                  {#if athByTotal.length > 0}
                    <div class="ath-count">{athByTotal.length} target{athByTotal.length !== 1 ? 's' : ''} ranked</div>
                    <div class="table-wrapper">
                      <table class="data-table">
                        <thead>
                          <tr>
                            <th class="col-rank">Rank</th>
                            <th>Target</th>
                            <th class="right col-count">#</th>
                            <th class="right col-value">Total Value</th>
                          </tr>
                        </thead>
                        <tbody>
                          {#each pagedAthByTotal as t}
                            <tr>
                              <td class="col-rank"><span class="rank-badge" class:rank-ruby={t.total_rank <= 1} class:rank-diamond={t.total_rank > 1 && t.total_rank <= 10} class:rank-gold={t.total_rank > 10 && t.total_rank <= 50} class:rank-silver={t.total_rank > 50 && t.total_rank <= 200} class:rank-bronze={t.total_rank > 200 && t.total_rank <= 500}>#{t.total_rank}</span></td>
                              <td><a href="/globals/target/{encodeURIComponent(t.target)}" class="target-link">{t.target}</a></td>
                              <td class="right col-count">{t.count}</td>
                              <td class="right font-weight-bold">{formatPed(t.total_value)} PED</td>
                            </tr>
                          {/each}
                        </tbody>
                      </table>
                    </div>
                    {#if athTotalPages > 1}
                      <div class="pagination">
                        <button class="page-btn" disabled={athTotalPage === 0} onclick={() => athTotalPage--}>&laquo; Prev</button>
                        <span class="page-info">{athTotalPage + 1} / {athTotalPages}</span>
                        <button class="page-btn" disabled={athTotalPage >= athTotalPages - 1} onclick={() => athTotalPage++}>Next &raquo;</button>
                      </div>
                    {/if}
                  {:else}
                    <p class="empty-state-sm">No total value rankings</p>
                  {/if}
                </div>
              </div>
            {/if}
          {/if}
        </div>
      {/if}
    </div>
  </div>
  {/if}
</div>

<GlobalMediaDialog show={showMediaDialog} global={mediaDialogGlobal} {user} onclose={() => { showMediaDialog = false; mediaDialogGlobal = null; }} ondeleted={onMediaDeleted} />

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

  .skeleton-container {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 16px 0;
  }

  .skeleton-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
  }

  @media (max-width: 640px) {
    .skeleton-stats {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  .loading-fade {
    opacity: 0.5;
    pointer-events: none;
    transition: opacity 0.15s ease;
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

  .top-loot-target {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
    flex: 1;
  }

  .top-loot-value {
    flex-shrink: 0;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .top-loot-actions {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
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
    min-width: 0;
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
    table-layout: fixed;
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
    overflow: hidden;
    text-overflow: ellipsis;
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
    background: rgba(255, 255, 255, 0.02);
  }
  .maturity-row td:first-child {
    border-left: 2px solid var(--accent-color);
  }

  .indent {
    padding-left: 26px !important;
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

  .mobile-only { display: none; }

  .sort-select {
    padding: 4px 8px;
    font-size: 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    cursor: pointer;
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

  .ath-targets-grid .section-card-inner {
    margin-bottom: 0;
  }

  .section-card-inner {
    padding: 16px;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }

  .section-subtitle {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-muted);
    margin: 0 0 12px 0;
  }

  .rank-badge {
    font-weight: 700;
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .rank-badge.rank-ruby {
    color: #e0115f;
    animation: shimmer-ruby 2s ease-in-out infinite;
  }
  .rank-badge.rank-diamond {
    color: #b9f2ff;
    animation: shimmer-diamond 2.5s ease-in-out infinite;
  }
  .rank-badge.rank-gold { color: #eab308; }
  .rank-badge.rank-silver { color: #c0c0c0; }
  .rank-badge.rank-bronze { color: #cd7f32; }

  @keyframes shimmer-ruby {
    0%, 100% { color: #e0115f; text-shadow: 0 0 4px rgba(224, 17, 95, 0.3); }
    50% { color: #ff4d8d; text-shadow: 0 0 8px rgba(224, 17, 95, 0.6); }
  }

  @keyframes shimmer-diamond {
    0%, 100% { color: #b9f2ff; text-shadow: 0 0 4px rgba(185, 242, 255, 0.3); }
    50% { color: #e0f9ff; text-shadow: 0 0 8px rgba(185, 242, 255, 0.6); }
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

  .badge-slot {
    display: inline-block;
    min-width: 28px;
    flex-shrink: 0;
  }

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

  .achievement-location {
    font-weight: 400;
    color: var(--text-muted);
    font-size: 0.8125rem;
  }

  .ath-count {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-bottom: 8px;
  }

  .achievement-detail {
    color: var(--text-muted);
    font-size: 0.75rem;
  }

  .achievement-actions {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
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
    .player-page { padding: 8px; }
    .section-card { padding: 10px; }

    .stats-row {
      grid-template-columns: repeat(2, 1fr);
      gap: 6px;
    }

    .stats-row.category-row {
      grid-template-columns: 1fr;
    }

    .player-tab-nav {
      overflow-x: auto;
      scrollbar-width: none;
    }
    .player-tab-nav::-webkit-scrollbar { display: none; }

    .tab-link {
      flex-shrink: 0;
      padding: 8px 12px;
      font-size: 0.8125rem;
    }

    /* Hide less important columns on mobile — keep target + value + badge */
    .col-media, .col-gz, .col-time, .col-type, .col-rank, .col-hide-mobile { display: none; }

    /* Compact table cells — keep 6px horizontal padding so text doesn't touch edges */
    .data-table th, .data-table td { padding: 4px 6px; font-size: 0.75rem; }
    .col-value { width: 80px !important; }
    .col-count { width: 24px; }

    /* Compact badge on mobile */
    .col-badge { width: 24px !important; padding: 0 2px !important; }
    .badge-hof, .badge-ath { padding: 1px 3px; font-size: 0.5625rem; letter-spacing: 0; }

    /* Compact type badge */
    .type-badge { padding: 1px 4px; font-size: 0.5625rem; letter-spacing: 0; }

    /* Achievement rows: hide secondary elements on mobile */
    .achievement-item { flex-wrap: wrap; gap: 4px 8px; padding: 6px 8px; font-size: 0.75rem; }
    .achievement-actions, .achievement-time { display: none; }

    /* Top loot rows: hide rank, actions on mobile */
    .top-loot-rank, .top-loot-actions { display: none; }
    .top-loot-item { padding: 4px 6px; font-size: 0.75rem; }

    /* Section titles */
    .section-card h2, .section-title-icon { font-size: 0.875rem; }
    .section-subtitle { font-size: 0.8125rem; }

    .desktop-only { display: none !important; }
    .mobile-only { display: block !important; }
  }

  .col-value { width: 75px; }
  .col-count { width: 40px; }
  .col-badge { width: 48px; padding-left: 4px !important; padding-right: 4px !important; }
  .col-media {
    width: 20px;
    text-align: center;
    padding: 4px 2px !important;
  }
  .col-gz {
    width: 40px;
    text-align: center;
    padding: 4px 4px !important;
  }
  .col-time { width: 55px; }
  .col-type { width: 65px; }

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
</style>
