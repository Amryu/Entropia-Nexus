<!--
  @component Globals Page
  Filterable, live-updating view of all confirmed global events.
  Includes stats cards, activity chart, type distribution, top players/targets, and live table.
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy, tick } from 'svelte';
  import { Chart, LineController, LinearScale, PointElement, LineElement, TimeScale,
           Tooltip, Filler, BarController, BarElement, CategoryScale } from 'chart.js';
  import 'chartjs-adapter-date-fns';

  Chart.register(LineController, LinearScale, PointElement, LineElement, TimeScale,
                 Tooltip, Filler, BarController, BarElement, CategoryScale);

  import { afterNavigate, goto } from '$app/navigation';
  import { page } from '$app/stores';
  import SearchInput from '$lib/components/SearchInput.svelte';
  import GlobalsDateRangePicker from '$lib/components/globals/GlobalsDateRangePicker.svelte';
  import GlobalsTabNav from '$lib/components/globals/GlobalsTabNav.svelte';
  import { TYPE_FILTERS, TOP_LOOTS_TABS, getTypeConfig } from '$lib/data/globals-constants.js';
  import { formatPedShort, formatValue, timeAgo, getComputedCssVar, sortedData, toggleSort, sortIcon } from '$lib/utils/globalsFormat.js';
  import GlobalMediaDialog from '$lib/components/globals/GlobalMediaDialog.svelte';
  import GlobalMediaUpload from '$lib/components/globals/GlobalMediaUpload.svelte';
  import GzButton from '$lib/components/globals/GzButton.svelte';

  let { data } = $props();

  let user = $derived(data?.session?.user || null);

  // Media dialog state
  let showMediaDialog = $state(false);
  let mediaDialogGlobal = $state(null);

  function openMediaDialog(g) {
    mediaDialogGlobal = g;
    showMediaDialog = true;
  }

  function onMediaUploaded(data) {
    const { type, globalId } = data;
    const update = (arr) => arr.map(g => {
      if (g.id === globalId) {
        return { ...g, media_image: type === 'image' ? true : g.media_image, media_video: type === 'video' ? true : g.media_video };
      }
      return g;
    });
    globals = update(globals);
    if (topLoots) topLoots = update(topLoots);
  }

  function onMediaDeleted(data) {
    const { globalId } = data;
    const update = (arr) => arr.map(g => {
      if (g.id === globalId) {
        return { ...g, media_image: null, media_video: null };
      }
      return g;
    });
    globals = update(globals);
    if (topLoots) topLoots = update(topLoots);
    showMediaDialog = false;
    mediaDialogGlobal = null;
  }

  const EMPTY_SUMMARY = {
    total_count: 0, total_value: 0, avg_value: 0, max_value: 0,
    hof_count: 0, ath_count: 0,
    hunting: { count: 0, value: 0 },
    mining: { count: 0, value: 0 },
    space_mining: { count: 0, value: 0 },
    crafting: { count: 0, value: 0 },
  };

  let dataGlobals = $derived(data.globals || []);
  let dataSummary = $derived(data.summary || {});
  let globals = $state((() => [...dataGlobals])());
  let summary = $state((() => ({ ...EMPTY_SUMMARY, ...dataSummary }))());

  // Filters
  let typeFilter = $state('');
  let spaceFilter = $state('');  // '' | 'only' | 'exclude'
  let playerFilter = $state('');
  let targetFilter = $state('');
  let locationFilter = $state('');
  let minValue = $state('');
  let hofOnly = $state(false);
  let period = $state('90d');
  let dateFrom = $state(null);
  let dateTo = $state(null);

  // Sort toggles for charts
  let playersSortBy = $state('value');
  let targetsSortBy = $state('count');
  let targetsGroupBy = $state('mob');

  // Charts
  let activityCanvas = $state();
  let topPlayersCanvas = $state();
  let topTargetsCanvas = $state();
  let activityChart = null;
  let topPlayersChart = null;
  let topTargetsChart = null;

  // Stats data
  let stats = $state(null);
  let statsLoading = $state(false);

  // Top loots
  let topLoots = $state(null);
  let topLootsLoading = $state(false);
  let topLootsTab = $state('hunting');
  let topLootsPage = $state(1);
  let topLootsPages = $state(1);
  let topLootsTotal = $state(0);
  let topLootsSort = $state({ col: '', asc: false }); // empty = default server sort

  // Remember type filter when switching to special tabs
  let savedTypeFilter = '';
  let filtersDisabled = $state(false);

  // Live table
  let pollTimer = null;
  let latestTimestamp = $state(null);
  let loadingMore = $state(false);
  let tableLoading = $state(false);
  let hasMore = $state(true);
  let newIds = $state(new Set());
  let liveSort = $state({ col: 'timestamp', asc: false });
  let sortedGlobals = $derived(liveSort.col === 'timestamp' && !liveSort.asc
    ? globals
    : sortedData(globals, liveSort));

  const POLL_INTERVAL = 5000;


  // Build filter query params
  function buildParams(extra = {}) {
    const params = new URLSearchParams();
    if (typeFilter) params.set('type', typeFilter);
    if (spaceFilter) params.set('space', spaceFilter);
    if (playerFilter) params.set('player', playerFilter);
    if (targetFilter) params.set('target', targetFilter);
    if (locationFilter) params.set('location', locationFilter);
    if (minValue) params.set('min_value', minValue);
    if (hofOnly) params.set('hof', 'true');
    if (dateFrom && dateTo) {
      params.set('from', dateFrom);
      params.set('to', dateTo);
    } else if (period && period !== 'all' && period !== 'custom') {
      params.set('period', period);
    }
    for (const [k, v] of Object.entries(extra)) {
      params.set(k, String(v));
    }
    return params;
  }

  // Fetch filtered globals
  async function fetchGlobals() {
    tableLoading = true;
    try {
      const params = buildParams({ limit: 50 });
      const res = await fetch(`/api/globals?${params}`);
      if (!res.ok) return;
      const data = await res.json();
      globals = data.globals;
      hasMore = data.has_more;
      latestTimestamp = globals.length > 0 ? globals[0].timestamp : null;
    } catch { /* ignore */ }
    tableLoading = false;
  }

  // Fetch stats
  async function fetchStats() {
    statsLoading = true;
    try {
      const params = buildParams({ players_sort: playersSortBy, targets_sort: targetsSortBy, targets_group: targetsGroupBy });
      const res = await fetch(`/api/globals/stats?${params}`);
      if (!res.ok) return;
      stats = await res.json();
      summary = stats.summary;
    } catch { /* ignore */ }
    statsLoading = false;
    await tick();
    if (stats) buildCharts();
  }

  // Fetch top loots
  async function fetchTopLoots() {
    topLootsLoading = true;
    try {
      const extra = { category: topLootsTab, page: topLootsPage, limit: 20 };
      if (topLootsSort.col) {
        extra.sort = topLootsSort.col;
        extra.sort_dir = topLootsSort.asc ? 'asc' : 'desc';
      }
      // Get space filter from tab config
      const tabConfig = TOP_LOOTS_TABS.find(t => t.value === topLootsTab);
      if (tabConfig?.space) extra.space = tabConfig.space;
      const params = buildParams(extra);
      const res = await fetch(`/api/globals/stats/top-loots?${params}`);
      if (!res.ok) return;
      const data = await res.json();
      topLoots = data.items;
      topLootsPages = data.pages;
      topLootsTotal = data.total;
    } catch { /* ignore */ }
    topLootsLoading = false;
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
      topLootsPage = 1;
      fetchGlobals();
      fetchStats();
      fetchTopLoots();
    }, 300);
  }

  // Map type filter values to their matching top loots tab
  const TYPE_TO_TAB = {
    'kill,team_kill,examine': 'hunting',
    'deposit': 'mining',
    'craft': 'crafting',
  };

  function onTypeFilter(val, space = '') {
    typeFilter = val;
    spaceFilter = space;
    // Auto-select matching top loots tab
    const matchedTab = space === 'only' ? 'space_mining' : TYPE_TO_TAB[val];
    if (matchedTab && !filtersDisabled) {
      topLootsTab = matchedTab;
      topLootsPage = 1;
      topLootsSort = { col: '', asc: false };
    }
    // Mob grouping only applies to hunting
    if (val && !val.split(',').some(t => t === 'kill' || t === 'team_kill' || t === 'examine')) {
      targetsGroupBy = 'maturity';
    }
    onFilterChange();
  }

  function onTopLootsTabChange(tab) {
    const tabConfig = TOP_LOOTS_TABS.find(t => t.value === tab);
    if (tabConfig?.isSpecial) {
      if (!filtersDisabled) savedTypeFilter = typeFilter;
      filtersDisabled = true;
    } else {
      if (filtersDisabled) {
        typeFilter = savedTypeFilter;
        filtersDisabled = false;
      }
    }
    topLootsTab = tab;
    topLootsPage = 1;
    topLootsSort = { col: '', asc: false };
    fetchTopLoots();
  }

  function goToTopLootsPage(p) {
    if (p < 1 || p > topLootsPages || p === topLootsPage) return;
    topLootsPage = p;
    fetchTopLoots();
  }

  function onTopLootsSort(col) {
    topLootsSort = topLootsSort.col === col
      ? { col, asc: !topLootsSort.asc }
      : { col, asc: false };
    topLootsPage = 1;
    fetchTopLoots();
  }

  let currentTabConfig = $derived(TOP_LOOTS_TABS.find(t => t.value === topLootsTab) || TOP_LOOTS_TABS[0]);

  function onDateRangeChange(data) {
    period = data.period;
    dateFrom = data.from;
    dateTo = data.to;
    topLootsPage = 1;
    fetchStats();
    fetchTopLoots();
  }

  function onPlayersSortChange(sortBy) {
    playersSortBy = sortBy;
    fetchStats();
  }

  function onTargetsSortChange(sortBy) {
    targetsSortBy = sortBy;
    fetchStats();
  }

  function onTargetsGroupChange(group) {
    targetsGroupBy = group;
    fetchStats();
  }

  function buildFilterUrl(basePath) {
    const params = buildParams();
    const qs = params.toString();
    return qs ? `${basePath}?${qs}` : basePath;
  }

  // Filter relevance helpers — top targets works for hunting, mining, and crafting
  let isHuntingFilter = $derived(!typeFilter || typeFilter.split(',').some(t => t === 'kill' || t === 'team_kill' || t === 'examine'));

  // Get index of Y-axis label clicked (for horizontal bar charts)
  function getClickedLabelIndex(evt, chart) {
    if (!chart) return null;
    const yScale = chart.scales.y;
    if (!yScale) return null;
    const { left, right } = yScale;
    const x = evt.native?.offsetX ?? evt.x;
    const y = evt.native?.offsetY ?? evt.y;
    if (x > right) return null; // Click is in the chart area, not labels
    for (let i = 0; i < yScale.ticks.length; i++) {
      const labelY = yScale.getPixelForTick(i);
      if (Math.abs(y - labelY) < 12) return i;
    }
    return null;
  }

  // Charts
  function buildCharts() {
    if (!stats) return;
    const textMuted = getComputedCssVar('--text-muted') || '#aaa';
    const borderColor = getComputedCssVar('--border-color') || '#555';

    buildActivityChart(textMuted, borderColor);
    buildTopPlayersChart(textMuted, borderColor);

    buildTopTargetsChart(textMuted, borderColor);
  }

  function buildActivityChart(textMuted, borderColor) {
    if (!activityCanvas || !stats?.activity?.length) return;
    if (activityChart) activityChart.destroy();

    const accentColor = getComputedCssVar('--accent-color') || '#60b0ff';
    const valueColor = '#2ecc71';

    activityChart = new Chart(activityCanvas, {
      type: 'line',
      data: {
        labels: stats.activity.map(a => new Date(a.bucket)),
        datasets: [
          {
            label: 'Count',
            data: stats.activity.map(a => a.count),
            borderColor: accentColor,
            backgroundColor: accentColor + '20',
            borderWidth: 2,
            pointRadius: stats.activity.length < 30 ? 3 : 0,
            pointHoverRadius: 5,
            fill: true,
            tension: 0.1,
            yAxisID: 'y',
          },
          {
            label: 'Value (PED)',
            data: stats.activity.map(a => a.value || 0),
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
            time: { unit: stats?.bucket_unit || 'day' },
            ticks: { color: textMuted, maxTicksLimit: 8, font: { size: 11 } },
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
            borderColor: accentColor,
            borderWidth: 1,
            callbacks: { label: ctx => ctx.dataset.yAxisID === 'y1' ? `Value: ${formatPedShort(ctx.parsed.y)} PED` : `Count: ${ctx.parsed.y}` },
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
    const label = playersSortBy === 'count' ? 'Count' : 'Total Value (PED)';

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
          data: players.map(p => p[playersSortBy]),
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

  function buildTopTargetsChart(textMuted, borderColor) {
    if (!topTargetsCanvas || !stats?.top_targets?.length) return;
    if (topTargetsChart) topTargetsChart.destroy();

    const targets = stats.top_targets.slice(0, 8);
    const countLabel = typeFilter === 'deposit' ? 'Count' : typeFilter === 'craft' ? 'Count' : 'Count';
    const label = targetsSortBy === 'value' ? 'Total Value (PED)' : countLabel;
    const chartColor = typeFilter === 'deposit' ? '#60b0ff' : typeFilter === 'craft' ? '#f97316' : '#ef4444';

    topTargetsChart = new Chart(topTargetsCanvas, {
      type: 'bar',
      data: {
        labels: targets.map(t => t.target.length > 18 ? t.target.slice(0, 16) + '...' : t.target),
        datasets: [{
          label,
          data: targets.map(t => t[targetsSortBy]),
          backgroundColor: chartColor + '40',
          borderColor: chartColor,
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
          const idx = elements.length > 0 ? elements[0].index : getClickedLabelIndex(evt, topTargetsChart);
          if (idx != null && targets[idx]) {
            goto(`/globals/target/${encodeURIComponent(targets[idx].target)}`);
          }
        },
        onHover: (evt, elements) => {
          evt.native.target.style.cursor = (elements.length > 0 || getClickedLabelIndex(evt, topTargetsChart) != null) ? 'pointer' : 'default';
        },
      },
    });
  }

  afterNavigate(() => {
    // Reinitialize from SSR data on every navigation (including initial)
    globals = [...dataGlobals];
    summary = { ...EMPTY_SUMMARY, ...dataSummary };
    latestTimestamp = globals.length > 0 ? globals[0].timestamp : null;
    hasMore = globals.length >= 50;
    newIds = new Set();
    stats = null;
    topLoots = null;
    topLootsPage = 1;
    fetchStats();
    fetchTopLoots();
  });

  onMount(() => {
    pollTimer = setInterval(poll, POLL_INTERVAL);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
    if (activityChart) activityChart.destroy();
    if (topPlayersChart) topPlayersChart.destroy();
    if (topTargetsChart) topTargetsChart.destroy();
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

  let currentView = $derived($page.url.searchParams.get('view'));
  let isLiveView = $derived(currentView === 'live');

  let playerSearchInput = $state();
  let targetSearchInput = $state();
  let locationSearchInput = $state();

  function handlePlayerSelect({ name }) {
    playerFilter = name;
    onFilterChange();
  }

  function clearPlayerFilter() {
    playerFilter = '';
    if (playerSearchInput) playerSearchInput.clear();
    onFilterChange();
  }

  function handleTargetSelect({ name }) {
    targetFilter = name;
    onFilterChange();
  }

  function clearTargetFilter() {
    targetFilter = '';
    if (targetSearchInput) targetSearchInput.clear();
    onFilterChange();
  }

  function handleLocationSelect({ name }) {
    locationFilter = name;
    onFilterChange();
  }

  function clearLocationFilter() {
    locationFilter = '';
    if (locationSearchInput) locationSearchInput.clear();
    onFilterChange();
  }
</script>

<svelte:head>
  <title>Globals - Entropia Nexus</title>
  <meta name="description" content="Live global events from Entropia Universe. Track hunting, mining, crafting globals, HoF and ATH records." />
  <link rel="canonical" href="https://entropianexus.com/globals" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://entropianexus.com/globals" />
  <meta property="og:title" content="Globals - Entropia Nexus" />
  <meta property="og:description" content="Live global events from Entropia Universe. Track hunting, mining, crafting globals, HoF and ATH records." />
  <meta property="og:image" content="https://entropianexus.com/icon.png" />
  <meta property="og:site_name" content="Entropia Nexus" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="Globals - Entropia Nexus" />
  <meta name="twitter:description" content="Live global events from Entropia Universe. Track hunting, mining, crafting globals, HoF and ATH records." />
  <meta name="twitter:image" content="https://entropianexus.com/icon.png" />
</svelte:head>

<div class="globals-page">
  <div class="page-header">
    <div class="header-top">
      <div>
        <div class="breadcrumbs"><a href="/">Home</a> / Globals</div>
        <h1>Globals</h1>
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

  <!-- Filters -->
  <div class="filters-bar">
    <div class="type-filters">
      {#each TYPE_FILTERS as tf}
        <button
          class="type-btn"
          class:active={!filtersDisabled && typeFilter === tf.value && spaceFilter === (tf.space || '')}
          disabled={filtersDisabled}
          onclick={() => onTypeFilter(tf.value, tf.space || '')}
        >
          {tf.label}
        </button>
      {/each}
    </div>
    <div class="text-filters">
      <div class="filter-search">
        {#if playerFilter}
          <div class="filter-chip">
            <span>{playerFilter}</span>
            <button class="chip-clear" onclick={clearPlayerFilter}>&times;</button>
          </div>
        {:else}
          <SearchInput
            bind:this={playerSearchInput}
            placeholder="Player / Team..."
            endpoint="/api/globals/players"
            apiPrefix={false}
            maxPerCategory={10}
            maxTotal={15}
            onselect={handlePlayerSelect}
            containerClass="filter-search-input"
          />
        {/if}
      </div>
      <div class="filter-search">
        {#if targetFilter}
          <div class="filter-chip">
            <span>{targetFilter}</span>
            <button class="chip-clear" onclick={clearTargetFilter}>&times;</button>
          </div>
        {:else}
          <SearchInput
            bind:this={targetSearchInput}
            placeholder="Target..."
            endpoint="/api/globals/targets"
            apiPrefix={false}
            maxPerCategory={10}
            maxTotal={15}
            onselect={handleTargetSelect}
            containerClass="filter-search-input"
          />
        {/if}
      </div>
      <div class="filter-search">
        {#if locationFilter}
          <div class="filter-chip">
            <span>{locationFilter}</span>
            <button class="chip-clear" onclick={clearLocationFilter}>&times;</button>
          </div>
        {:else}
          <SearchInput
            bind:this={locationSearchInput}
            placeholder="Location..."
            endpoint="/api/globals/locations"
            apiPrefix={false}
            maxPerCategory={10}
            maxTotal={15}
            onselect={handleLocationSelect}
            containerClass="filter-search-input"
          />
        {/if}
      </div>
      <input type="number" placeholder="Min PED" bind:value={minValue} oninput={onFilterChange} class="filter-input filter-input-short" />
      <label class="hof-toggle" class:disabled={filtersDisabled}>
        <input type="checkbox" bind:checked={hofOnly} onchange={onFilterChange} disabled={filtersDisabled} />
        HoF only
      </label>
    </div>
  </div>

  <!-- Tab Navigation -->
  <GlobalsTabNav {buildParams} />

  {#if !isLiveView}
  <!-- Period Selector -->
  <GlobalsDateRangePicker {period} from={dateFrom} to={dateTo} onchange={onDateRangeChange} />

  <!-- Stats Cards -->
  <div class="stats-row" class:stats-loading={statsLoading}>
    <div class="stat-card">
      <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="#60b0ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
      <span class="stat-value">{summary.total_count.toLocaleString()}</span>
      <span class="stat-label">Total Globals</span>
    </div>
    <div class="stat-card">
      <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="#2ecc71" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
      <span class="stat-value">{formatPedShort(summary.total_value)} PED</span>
      <span class="stat-label">Total Value</span>
    </div>
    <div class="stat-card">
      <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="#f39c12" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
      <span class="stat-value">{formatPedShort(summary.avg_value)} PED</span>
      <span class="stat-label">Avg Value</span>
    </div>
    <div class="stat-card">
      <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="#e74c3c" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
      <span class="stat-value">{formatPedShort(summary.max_value)} PED</span>
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

  <!-- Category Breakdown -->
  <div class="stats-row category-row" class:stats-loading={statsLoading}>
    <div class="stat-card category-card">
      <span class="stat-value hunting-color">{summary.hunting.count.toLocaleString()}</span>
      <span class="stat-label">Hunting</span>
      <span class="stat-sub">{formatPedShort(summary.hunting.value)} PED</span>
    </div>
    <div class="stat-card category-card">
      <span class="stat-value mining-color">{summary.mining.count.toLocaleString()}</span>
      <span class="stat-label">Mining</span>
      <span class="stat-sub">{formatPedShort(summary.mining.value)} PED</span>
    </div>
    <div class="stat-card category-card">
      <span class="stat-value space-mining-color">{summary.space_mining.count.toLocaleString()}</span>
      <span class="stat-label">Space Mining</span>
      <span class="stat-sub">{formatPedShort(summary.space_mining.value)} PED</span>
    </div>
    <div class="stat-card category-card">
      <span class="stat-value crafting-color">{summary.crafting.count.toLocaleString()}</span>
      <span class="stat-label">Crafting</span>
      <span class="stat-sub">{formatPedShort(summary.crafting.value)} PED</span>
    </div>
  </div>

  <!-- Charts -->
  <div class="charts-section">
    <h2 class="charts-heading">Statistics</h2>

    <div class="charts-grid">
      <div class="chart-card chart-wide">
        <h3>Activity Timeline</h3>
        <div class="chart-container">
          {#if statsLoading && !stats}
            <div class="chart-loading"><span class="spinner"></span></div>
          {:else}
            <canvas bind:this={activityCanvas}></canvas>
          {/if}
        </div>
      </div>

      <div class="chart-card">
        <div class="chart-card-header">
          <h3>Top Players</h3>
          <div class="chart-controls">
            <div class="sort-toggle">
              <button class="sort-btn" class:active={playersSortBy === 'value'} onclick={() => onPlayersSortChange('value')}>Value</button>
              <button class="sort-btn" class:active={playersSortBy === 'count'} onclick={() => onPlayersSortChange('count')}>Count</button>
            </div>
            <a href={buildFilterUrl('/globals/players')} class="view-all-link">View all &rarr;</a>
          </div>
        </div>
        <div class="chart-container">
          {#if statsLoading && !stats}
            <div class="chart-loading"><span class="spinner"></span></div>
          {:else}
            <canvas bind:this={topPlayersCanvas}></canvas>
          {/if}
        </div>
      </div>

      <div class="chart-card">
        <div class="chart-card-header">
          <h3>Top Targets</h3>
          <div class="chart-controls">
            {#if isHuntingFilter}
              <div class="sort-toggle">
                <button class="sort-btn" class:active={targetsGroupBy === 'maturity'} onclick={() => onTargetsGroupChange('maturity')}>Maturities</button>
                <button class="sort-btn" class:active={targetsGroupBy === 'mob'} onclick={() => onTargetsGroupChange('mob')}>Mobs</button>
              </div>
            {/if}
            <div class="sort-toggle">
              <button class="sort-btn" class:active={targetsSortBy === 'count'} onclick={() => onTargetsSortChange('count')}>Count</button>
              <button class="sort-btn" class:active={targetsSortBy === 'value'} onclick={() => onTargetsSortChange('value')}>Value</button>
            </div>
            <a href={buildFilterUrl('/globals/targets')} class="view-all-link">View all &rarr;</a>
          </div>
        </div>
        <div class="chart-container">
          {#if statsLoading && !stats}
            <div class="chart-loading"><span class="spinner"></span></div>
          {:else}
            <canvas bind:this={topTargetsCanvas}></canvas>
          {/if}
        </div>
      </div>

    </div>
  </div>

  <!-- Top Loots -->
  <div class="section-card top-loots-section">
    <div class="top-loots-header">
      <h2>Top Globals / HoFs</h2>
      {#if topLootsTotal > 0}
        <span class="top-loots-count">{topLootsTotal.toLocaleString()} entries</span>
      {/if}
    </div>
    <div class="top-loots-tabs">
      {#each TOP_LOOTS_TABS as tab}
        <button
          class="sort-btn"
          class:active={topLootsTab === tab.value}
          class:special={tab.isSpecial}
          onclick={() => onTopLootsTabChange(tab.value)}
        >
          {tab.label}
        </button>
      {/each}
    </div>
    <div class:loading-fade={topLootsLoading}>
      {#if topLootsLoading && !topLoots}
        <div class="table-loading"><span class="spinner"></span></div>
      {:else if topLoots && topLoots.length > 0}
        <div class="table-wrapper">
          <table class="globals-table top-loots-table">
            <thead>
              <tr>
                <th class="col-rank">#</th>
                <th class="col-player sortable" onclick={() => onTopLootsSort('player')}>Player{sortIcon(topLootsSort, 'player')}</th>
                {#if topLootsTab !== 'pvp'}
                  <th class="col-target sortable" onclick={() => onTopLootsSort('target')}>{currentTabConfig.isSpecial ? 'Item' : 'Target'}{sortIcon(topLootsSort, 'target')}</th>
                {/if}
                {#if currentTabConfig.hasValue}
                  <th class="col-value right sortable" onclick={() => onTopLootsSort('value')}>Value{sortIcon(topLootsSort, 'value')}</th>
                {/if}
                <th class="col-badge"></th>
                <th class="col-media"></th>
                <th class="col-gz"></th>
                <th class="col-time sortable" onclick={() => onTopLootsSort('time')}>Time{sortIcon(topLootsSort, 'time')}</th>
              </tr>
            </thead>
            <tbody>
              {#each topLoots as loot, i}
                <tr>
                  <td class="col-rank text-muted">{(topLootsPage - 1) * 20 + i + 1}</td>
                  <td><a href="/globals/player/{encodeURIComponent(loot.player)}" class="player-link">{loot.player}</a></td>
                  {#if topLootsTab !== 'pvp'}
                    <td class="col-target-cell">
                      {#if !currentTabConfig.isSpecial}
                        <a href="/globals/target/{encodeURIComponent(loot.target)}" class="target-link">{loot.target}</a>
                      {:else}
                        {loot.target}
                      {/if}
                    </td>
                  {/if}
                  {#if currentTabConfig.hasValue}
                    <td class="right font-mono">{topLootsTab === 'pvp' ? `${Math.round(loot.value)} Kills` : loot.unit === 'PEC' ? `${(loot.value / 100).toFixed(2)} PED` : `${formatPedShort(loot.value)} PED`}</td>
                  {/if}
                  <td class="col-badge">
                    {#if loot.ath}
                      <span class="badge-ath">ATH</span>
                    {:else if loot.hof}
                      <span class="badge-hof">HoF</span>
                    {/if}
                  </td>
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
                      <GlobalMediaUpload globalId={loot.id} playerName={loot.player} {user} onuploaded={onMediaUploaded} />
                    {/if}
                  </td>
                  <td class="col-gz"><GzButton globalId={loot.id} count={loot.gz_count || 0} userGz={loot.user_gz || false} {user} compact /></td>
                  <td class="text-muted col-time" title={new Date(loot.timestamp).toLocaleString()}>{timeAgo(loot.timestamp)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        {#if topLootsPages > 1}
          <div class="pagination">
            <button class="page-btn" disabled={topLootsPage <= 1} onclick={() => goToTopLootsPage(topLootsPage - 1)}>&lsaquo;</button>
            <span class="page-info">Page {topLootsPage} of {topLootsPages}</span>
            <button class="page-btn" disabled={topLootsPage >= topLootsPages} onclick={() => goToTopLootsPage(topLootsPage + 1)}>&rsaquo;</button>
          </div>
        {/if}
      {:else}
        <p class="empty-state-sm">No entries found for this category and period</p>
      {/if}
    </div>
  </div>

  {/if}

  <!-- Live Table -->
  {#if isLiveView}
  <div class="table-section">
    <div class="live-header">
      <h2>Recent Globals</h2>
      <div class="live-type-filters">
        {#each [
          { value: '', label: 'All' },
          { value: 'kill,team_kill,examine', label: 'Hunting' },
          { value: 'deposit', label: 'Mining', space: 'exclude' },
          { value: 'deposit', label: 'Space Mining', space: 'only' },
          { value: 'craft', label: 'Crafting' },
          { value: 'rare_item', label: 'Rare Finds' },
          { value: 'discovery', label: 'Discoveries' },
          { value: 'tier', label: 'Tier Records' },
          { value: 'pvp', label: 'PvP' },
        ] as tf}
          <button
            class="type-btn"
            class:active={typeFilter === tf.value && spaceFilter === (tf.space || '')}
            onclick={() => onTypeFilter(tf.value, tf.space || '')}
          >
            {tf.label}
          </button>
        {/each}
      </div>
    </div>

    {#if tableLoading}
      <div class="table-loading"><span class="spinner"></span></div>
    {:else if globals.length === 0}
      <p class="empty-state">No globals match your filters</p>
    {:else}
      <div class="table-wrapper">
        <table class="globals-table">
          <thead>
            <tr>
              <th class="sortable col-time" onclick={() => liveSort = toggleSort(liveSort, 'timestamp')}>Time{sortIcon(liveSort, 'timestamp')}</th>
              <th class="sortable col-type" onclick={() => liveSort = toggleSort(liveSort, 'type')}>Type{sortIcon(liveSort, 'type')}</th>
              <th class="sortable" onclick={() => liveSort = toggleSort(liveSort, 'player')}>Player{sortIcon(liveSort, 'player')}</th>
              <th class="sortable" onclick={() => liveSort = toggleSort(liveSort, 'target')}>Target{sortIcon(liveSort, 'target')}</th>
              <th class="sortable right col-value" onclick={() => liveSort = toggleSort(liveSort, 'value')}>Value{sortIcon(liveSort, 'value')}</th>
              <th class="sortable col-location" onclick={() => liveSort = toggleSort(liveSort, 'location')}>Location{sortIcon(liveSort, 'location')}</th>
              <th class="col-badges"></th>
              <th class="col-media"></th>
              <th class="col-gz"></th>
            </tr>
          </thead>
          <tbody>
            {#each sortedGlobals as g (g.id)}
              {@const tc = getTypeConfig(g.type)}
              <tr class:row-new={newIds.has(g.id)}>
                <td class="col-time" title={new Date(g.timestamp).toLocaleString()}>{timeAgo(g.timestamp)}</td>
                <td class="col-type"><span class="type-badge {tc.cssClass}">{tc.label}</span></td>
                <td>
                  {#if g.type === 'team_kill'}
                    <span class="badge-team">Team</span>
                  {/if}
                  <a href="/globals/player/{encodeURIComponent(g.player)}" class="player-link">{g.player}</a>
                </td>
                <td class="col-target">
                  {#if g.target}
                    <a href="/globals/target/{encodeURIComponent(g.target)}" class="target-link">{g.target}</a>
                  {/if}
                </td>
                <td class="right col-value">{formatValue(g.value, g.unit, g.type)}</td>
                <td class="col-location">{g.location || ''}</td>
                <td class="col-badges">
                  {#if g.ath}
                    <span class="badge-ath">ATH</span>
                  {:else if g.hof}
                    <span class="badge-hof">HoF</span>
                  {/if}
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
                    <GlobalMediaUpload globalId={g.id} playerName={g.player} {user} onuploaded={onMediaUploaded} />
                  {/if}
                </td>
                <td class="col-gz"><GzButton globalId={g.id} count={g.gz_count || 0} userGz={g.user_gz || false} {user} compact /></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if hasMore}
        <div class="load-more">
          <button class="load-more-btn" onclick={loadMore} disabled={loadingMore}>
            {loadingMore ? 'Loading...' : 'Load more'}
          </button>
        </div>
      {/if}
    {/if}
  </div>
  {/if}
</div>

<GlobalMediaDialog show={showMediaDialog} global={mediaDialogGlobal} {user} onclose={() => { showMediaDialog = false; mediaDialogGlobal = null; }} ondeleted={onMediaDeleted} />

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

  .type-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  .hof-toggle.disabled {
    opacity: 0.35;
    cursor: not-allowed;
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

  .filter-search {
    min-width: 140px;
  }

  .filter-search :global(.filter-search-input .search-input) {
    padding: 6px 10px;
    font-size: 0.8125rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--primary-color);
    min-width: 140px;
  }

  .filter-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px 4px 10px;
    font-size: 0.8125rem;
    background: var(--accent-color-alpha, rgba(96, 176, 255, 0.15));
    color: var(--accent-color);
    border-radius: 6px;
    border: 1px solid var(--accent-color);
    white-space: nowrap;
  }

  .chip-clear {
    background: none;
    border: none;
    color: var(--accent-color);
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    padding: 0 2px;
    opacity: 0.7;
  }

  .chip-clear:hover {
    opacity: 1;
  }

  /* Stats Cards */
  .stats-row {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }

  .stats-row.category-row {
    grid-template-columns: repeat(4, 1fr);
    margin-bottom: 20px;
  }

  .stat-card {
    padding: 16px;
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

  .stat-sub {
    display: block;
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 2px;
    font-variant-numeric: tabular-nums;
  }

  .hunting-color { color: #ef4444; }
  .mining-color { color: #60b0ff; }
  .space-mining-color { color: #a78bfa; }
  .crafting-color { color: #f97316; }

  .stats-loading .stat-value {
    opacity: 0.4;
    transition: opacity 0.2s ease;
  }

  /* Charts */
  .charts-section {
    margin-bottom: 20px;
  }

  .charts-heading {
    margin: 0 0 16px 0;
    font-size: 1.125rem;
    font-weight: 600;
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
    min-width: 0;
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

  .chart-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    gap: 8px;
  }

  .chart-card-header h3 {
    margin: 0;
  }

  .chart-controls {
    display: flex;
    align-items: center;
    gap: 10px;
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

  .view-all-link {
    font-size: 0.75rem;
    color: var(--accent-color);
    text-decoration: none;
    white-space: nowrap;
  }

  .view-all-link:hover {
    text-decoration: underline;
  }

  .chart-container {
    position: relative;
    height: 200px;
    overflow: hidden;
  }

  .chart-loading, .table-loading {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 120px;
  }

  .chart-placeholder {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100%;
    min-height: 120px;
    color: var(--text-muted);
    font-size: 0.8125rem;
    font-style: italic;
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

  /* Table */
  /* Top loots */
  .top-loots-section {
    margin-bottom: 20px;
    padding: 20px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }

  .top-loots-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
  }

  .top-loots-header h2 {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
  }

  .top-loots-count {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .top-loots-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 2px;
    margin-bottom: 16px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
    width: fit-content;
  }

  .top-loots-tabs .sort-btn.special {
    border-left: 1px solid var(--border-color);
  }

  .top-loots-table {
    font-size: 0.8125rem;
    width: 100%;
  }
  .col-rank { width: 32px; }
  .col-badge, .col-badges { width: 48px; }
  .col-target-cell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .col-media { width: 20px; text-align: center; padding: 4px 2px !important; }
  .col-gz { width: 40px; text-align: center; padding: 4px 4px !important; }
  .col-time { width: 70px; }
  .col-location { width: 120px; }
  .top-loots-table td { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .loading-fade {
    opacity: 0.5;
    pointer-events: none;
    transition: opacity 0.15s ease;
  }

  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-top: 12px;
  }

  .page-btn {
    padding: 4px 12px;
    font-size: 0.875rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
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
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .font-mono {
    font-variant-numeric: tabular-nums;
  }

  .empty-state-sm {
    text-align: center;
    padding: 24px;
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  .table-section {
    margin-bottom: 40px;
  }

  .table-section h2 {
    margin: 0 0 12px 0;
    font-size: 1.125rem;
    font-weight: 600;
  }

  .live-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }

  .live-header h2 {
    margin: 0;
  }

  .live-type-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
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
    table-layout: fixed;
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

  .globals-table th.sortable {
    cursor: pointer;
    user-select: none;
  }

  .globals-table th.sortable:hover {
    color: var(--text-color);
  }

  .globals-table td {
    padding: 8px 14px;
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .globals-table tr:last-child td {
    border-bottom: none;
  }

  .globals-table tbody tr:nth-child(even) {
    background-color: var(--table-alt-row, rgba(255, 255, 255, 0.02));
  }

  .globals-table tbody tr:hover {
    background-color: var(--hover-color);
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: -2px;
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
  .type-space-deposit { background: rgba(167, 139, 250, 0.15); color: #a78bfa; }
  .type-craft    { background: rgba(249, 115, 22, 0.15); color: #f97316; }
  .type-rare     { background: rgba(96, 176, 255, 0.15); color: var(--accent-color); }
  .type-discovery { background: rgba(155, 89, 182, 0.15); color: #9b59b6; }
  .type-tier     { background: rgba(241, 196, 15, 0.15); color: #f1c40f; }
  .type-examine  { background: rgba(46, 204, 113, 0.15); color: #2ecc71; }
  .type-pvp      { background: rgba(231, 76, 60, 0.15);  color: #e74c3c; }

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

  .target-link {
    color: var(--text-color);
    text-decoration: none;
  }

  .target-link:hover {
    color: var(--accent-color);
    text-decoration: underline;
  }

  .col-value {
    width: 75px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .col-type { width: 65px; }

  .right {
    text-align: right;
  }

  .col-location {
    color: var(--text-muted);
  }

  .badge-hof, .badge-ath, .badge-team {
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

  .badge-team {
    background: rgba(96, 176, 255, 0.15);
    color: var(--accent-color);
    margin-right: 4px;
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
      grid-template-columns: repeat(3, 1fr);
    }

    .stats-row.category-row {
      grid-template-columns: repeat(4, 1fr);
    }

    .charts-grid {
      grid-template-columns: 1fr;
    }

    .chart-card.chart-wide {
      grid-column: 1;
    }
  }

  @media (max-width: 599px) {
    .globals-page { padding: 8px; }

    .stats-row {
      grid-template-columns: repeat(2, 1fr);
      gap: 6px;
    }

    .stats-row.category-row {
      grid-template-columns: repeat(2, 1fr);
    }

    .filter-input {
      min-width: 100px;
      flex: 1;
    }

    /* Hide less important columns on mobile */
    .col-media, .col-gz, .col-time, .col-type, .col-rank, .col-location { display: none; }

    /* Compact table cells */
    .globals-table th, .globals-table td { padding: 4px 6px; font-size: 0.75rem; }
    .col-value { width: 80px !important; }
    .col-badge, .col-badges { width: 32px !important; padding: 0 2px !important; }

    /* Compact badges */
    .badge-hof, .badge-ath, .badge-team { padding: 1px 3px; font-size: 0.5625rem; letter-spacing: 0; }
    .type-badge { padding: 1px 4px; font-size: 0.5625rem; letter-spacing: 0; }

    /* Compact charts on mobile */
    .chart-card { padding: 10px; }
    .chart-container { height: 160px; }
  }

  /* Media icon */

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
