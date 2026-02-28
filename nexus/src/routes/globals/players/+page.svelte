<!--
  @component Top Players Page
  Paginated, filterable ranking of players by global event statistics.
-->
<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { encodeURIComponentSafe } from '$lib/util';
  import SearchInput from '$lib/components/SearchInput.svelte';

  const TYPE_FILTERS = [
    { value: '', label: 'All' },
    { value: 'kill,team_kill', label: 'Hunting' },
    { value: 'deposit', label: 'Mining' },
    { value: 'craft', label: 'Crafting' },
    { value: 'rare_item', label: 'Rare Find' },
    { value: 'discovery', label: 'Discovery' },
    { value: 'tier', label: 'Tier Record' },
    { value: 'examine', label: 'Instance' },
    { value: 'pvp', label: 'PvP' },
  ];

  const PERIOD_OPTIONS = [
    { value: '24h', label: '24 Hours' },
    { value: '7d', label: '7 Days' },
    { value: '30d', label: '30 Days' },
    { value: 'all', label: 'All Time' },
  ];

  // Read initial state from URL params
  const sp = $page.url.searchParams;
  let typeFilter = sp.get('type') || '';
  let playerFilter = sp.get('player') || '';
  let targetFilter = sp.get('target') || '';
  let locationFilter = sp.get('location') || '';
  let minValue = sp.get('min_value') || '';
  let hofOnly = sp.get('hof') === 'true';
  let period = sp.get('period') || '7d';
  let sortBy = sp.get('sort') || 'value';
  let currentPage = 1;

  let data = null;
  let loading = true;

  function buildParams(extra = {}) {
    const params = new URLSearchParams();
    if (typeFilter) params.set('type', typeFilter);
    if (playerFilter) params.set('player', playerFilter);
    if (targetFilter) params.set('target', targetFilter);
    if (locationFilter) params.set('location', locationFilter);
    if (minValue) params.set('min_value', minValue);
    if (hofOnly) params.set('hof', 'true');
    if (period !== 'all') params.set('period', period);
    for (const [k, v] of Object.entries(extra)) {
      params.set(k, String(v));
    }
    return params;
  }

  function buildGlobalsUrl() {
    const params = buildParams();
    const qs = params.toString();
    return qs ? `/globals?${qs}` : '/globals';
  }

  async function fetchData() {
    loading = true;
    try {
      const params = buildParams({ sort: sortBy, page: currentPage, period });
      const res = await fetch(`/api/globals/stats/players?${params}`);
      if (!res.ok) return;
      data = await res.json();
    } catch { /* ignore */ }
    loading = false;
  }

  let filterDebounce = null;
  function onFilterChange() {
    currentPage = 1;
    clearTimeout(filterDebounce);
    filterDebounce = setTimeout(fetchData, 300);
  }

  function onTypeFilter(val) {
    typeFilter = val;
    onFilterChange();
  }

  function onSortChange(val) {
    sortBy = val;
    currentPage = 1;
    fetchData();
  }

  function goToPage(p) {
    currentPage = p;
    fetchData();
  }

  function formatPedShort(value) {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
    return value.toFixed(0);
  }

  onMount(fetchData);

  // Search handlers
  let playerSearchInput;
  let targetSearchInput;
  let locationSearchInput;

  function handlePlayerSelect(e) {
    playerFilter = e.detail.name;
    onFilterChange();
  }
  function clearPlayerFilter() {
    playerFilter = '';
    if (playerSearchInput) playerSearchInput.clear();
    onFilterChange();
  }
  function handleTargetSelect(e) {
    targetFilter = e.detail.name;
    onFilterChange();
  }
  function clearTargetFilter() {
    targetFilter = '';
    if (targetSearchInput) targetSearchInput.clear();
    onFilterChange();
  }
  function handleLocationSelect(e) {
    locationFilter = e.detail.name;
    onFilterChange();
  }
  function clearLocationFilter() {
    locationFilter = '';
    if (locationSearchInput) locationSearchInput.clear();
    onFilterChange();
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
  <title>Top Players - Globals - Entropia Nexus</title>
  <meta name="description" content="Top players ranked by global events in Entropia Universe." />
</svelte:head>

<div class="ranking-page">
  <div class="page-header">
    <div class="header-top">
      <div>
        <div class="breadcrumbs">
          <a href="/">Home</a> / <a href={buildGlobalsUrl()}>Globals</a> / Top Players
        </div>
        <h1>Top Players</h1>
        <p class="page-subtitle">Players ranked by global event statistics</p>
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

  <!-- Filters -->
  <div class="filters-bar">
    <div class="type-filters">
      {#each TYPE_FILTERS as tf}
        <button class="type-btn" class:active={typeFilter === tf.value} on:click={() => onTypeFilter(tf.value)}>
          {tf.label}
        </button>
      {/each}
    </div>
    <div class="text-filters">
      <div class="filter-search">
        {#if playerFilter}
          <div class="filter-chip">
            <span>{playerFilter}</span>
            <button class="chip-clear" on:click={clearPlayerFilter}>&times;</button>
          </div>
        {:else}
          <SearchInput bind:this={playerSearchInput} placeholder="Player / Team..." endpoint="/api/globals/players" apiPrefix={false} maxPerCategory={10} maxTotal={15} on:select={handlePlayerSelect} containerClass="filter-search-input" />
        {/if}
      </div>
      <div class="filter-search">
        {#if targetFilter}
          <div class="filter-chip">
            <span>{targetFilter}</span>
            <button class="chip-clear" on:click={clearTargetFilter}>&times;</button>
          </div>
        {:else}
          <SearchInput bind:this={targetSearchInput} placeholder="Target..." endpoint="/api/globals/targets" apiPrefix={false} maxPerCategory={10} maxTotal={15} on:select={handleTargetSelect} containerClass="filter-search-input" />
        {/if}
      </div>
      <div class="filter-search">
        {#if locationFilter}
          <div class="filter-chip">
            <span>{locationFilter}</span>
            <button class="chip-clear" on:click={clearLocationFilter}>&times;</button>
          </div>
        {:else}
          <SearchInput bind:this={locationSearchInput} placeholder="Location..." endpoint="/api/globals/locations" apiPrefix={false} maxPerCategory={10} maxTotal={15} on:select={handleLocationSelect} containerClass="filter-search-input" />
        {/if}
      </div>
      <input type="number" placeholder="Min PED" bind:value={minValue} on:input={onFilterChange} class="filter-input filter-input-short" />
      <label class="hof-toggle">
        <input type="checkbox" bind:checked={hofOnly} on:change={onFilterChange} />
        HoF only
      </label>
    </div>
  </div>

  <!-- Controls row -->
  <div class="controls-row">
    <div class="period-selector">
      {#each PERIOD_OPTIONS as p}
        <button class="period-btn" class:active={period === p.value} on:click={() => { period = p.value; onFilterChange(); }}>
          {p.label}
        </button>
      {/each}
    </div>
    <div class="sort-toggle">
      <button class="sort-btn" class:active={sortBy === 'value'} on:click={() => onSortChange('value')}>By Value</button>
      <button class="sort-btn" class:active={sortBy === 'count'} on:click={() => onSortChange('count')}>By Count</button>
    </div>
  </div>

  <!-- Table -->
  {#if loading}
    <div class="table-loading"><span class="spinner"></span></div>
  {:else if !data || data.players.length === 0}
    <p class="empty-state">No players match your filters</p>
  {:else}
    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th class="col-rank">#</th>
            <th>Player</th>
            <th class="right">Count</th>
            <th class="right">Total Value</th>
          </tr>
        </thead>
        <tbody>
          {#each data.players as p, i}
            <tr>
              <td class="col-rank text-muted">{(currentPage - 1) * 50 + i + 1}</td>
              <td>
                {#if p.is_team}
                  <span class="badge-team">Team</span>
                {/if}
                <a href="/globals/player/{encodeURIComponent(p.player)}" class="player-link">{p.player}</a>
                {#if p.has_profile}
                  <a href="/users/{encodeURIComponentSafe(p.player)}" class="profile-link">View Profile &rarr;</a>
                {/if}
              </td>
              <td class="right">{p.count.toLocaleString()}</td>
              <td class="right font-mono">{formatPedShort(p.value)} PED</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    {#if data.pages > 1}
      <div class="pagination">
        <button class="page-btn" disabled={currentPage <= 1} on:click={() => goToPage(currentPage - 1)}>Previous</button>
        <span class="page-info">Page {data.page} of {data.pages}</span>
        <button class="page-btn" disabled={currentPage >= data.pages} on:click={() => goToPage(currentPage + 1)}>Next</button>
      </div>
    {/if}
  {/if}
</div>

<style>
  .ranking-page {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
    color: var(--text-color);
  }

  .page-header { margin-bottom: 24px; }

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

  .breadcrumbs {
    font-size: 0.8125rem;
    color: var(--text-muted);
    margin-bottom: 8px;
  }

  .breadcrumbs a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumbs a:hover { text-decoration: underline; }

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

  .hof-toggle input { cursor: pointer; }

  .filter-search { min-width: 140px; }

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

  .chip-clear:hover { opacity: 1; }

  /* Controls row */
  .controls-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    gap: 12px;
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

  .sort-toggle {
    display: flex;
    gap: 2px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .sort-btn {
    padding: 4px 12px;
    font-size: 0.75rem;
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

  .sort-btn:hover:not(.active) { color: var(--text-color); }

  /* Table */
  .table-wrapper {
    overflow-x: auto;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background: var(--secondary-color);
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8125rem;
  }

  .data-table th {
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

  .data-table td {
    padding: 8px 14px;
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
  }

  .data-table tr:last-child td { border-bottom: none; }

  .data-table tbody tr:nth-child(even) {
    background-color: var(--table-alt-row, rgba(255, 255, 255, 0.02));
  }

  .data-table tbody tr:hover {
    background-color: var(--hover-color);
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: -2px;
  }

  .right { text-align: right; }
  .text-muted { color: var(--text-muted); }
  .font-mono { font-variant-numeric: tabular-nums; }
  .col-rank { width: 40px; }

  .player-link {
    color: var(--text-color);
    text-decoration: none;
    font-weight: 600;
  }

  .player-link:hover {
    color: var(--accent-color);
    text-decoration: underline;
  }

  .profile-link {
    font-size: 0.6875rem;
    color: var(--accent-color);
    text-decoration: none;
    margin-left: 8px;
    white-space: nowrap;
  }

  .profile-link:hover {
    text-decoration: underline;
  }

  .badge-team {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.3px;
    background: rgba(96, 176, 255, 0.15);
    color: var(--accent-color);
    margin-right: 4px;
    vertical-align: middle;
  }

  /* Loading / Empty */
  .table-loading {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 200px;
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

  .empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
    font-size: 0.9375rem;
  }

  /* Pagination */
  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 16px;
    margin-top: 16px;
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
    .ranking-page { padding: 16px; }
  }

  @media (max-width: 599px) {
    .header-top { flex-direction: column; }
    .globals-search { width: 100%; }
    .controls-row { flex-direction: column; align-items: flex-start; }
    .filter-input { min-width: 100px; flex: 1; }
  }
</style>
