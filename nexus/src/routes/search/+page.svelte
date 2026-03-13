<!-- @ts-nocheck -->
<script>
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { browser } from '$app/environment';
  import { onDestroy, onMount } from 'svelte';
  import { getTypeLink, getTypeName } from '$lib/util';
  import { getColumnsForType } from '$lib/search-columns';
  import { itemTypeBadge } from '../market/exchange/orderUtils';

  let { data } = $props();

  let initialQuery = $derived(data.query || '');
  let initialResults = $derived(data.results || []);

  let searchInput = $state('');
  let debounceTimer;
  let collapsedGroups = $state({});
  let sortState = {}; // { [type]: { key, dir } }
  let isLoading = $state(false);
  let results = $state([]);
  let currentQuery = $state('');

  // Sync from SSR data on load/navigation
  $effect(() => {
    searchInput = initialQuery;
    results = initialResults;
    currentQuery = initialQuery;
  });

  onMount(() => {
    // Handle browser back/forward by listening to popstate
    const handlePopState = () => {
      const q = new URL(window.location.href).searchParams.get('q') || '';
      if (q !== currentQuery) {
        searchInput = q;
        performSearch(q);
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  });

  onDestroy(() => {
    if (debounceTimer) clearTimeout(debounceTimer);
  });

  async function performSearch(q) {
    currentQuery = q;
    if (q.length < 2) {
      results = [];
      isLoading = false;
      return;
    }
    isLoading = true;
    try {
      const response = await fetch(import.meta.env.VITE_API_URL + `/search/detailed?query=${encodeURIComponent(q)}&fuzzy=true`);
      const data = await response.json();
      results = Array.isArray(data) ? data : [];
    } catch (err) {
      console.error('Search failed:', err);
      results = [];
    } finally {
      isLoading = false;
    }
  }

  function updateUrl(q) {
    const url = q ? `/search?q=${encodeURIComponent(q)}` : '/search';
    history.replaceState(history.state, '', url);
  }

  function groupResults(results) {
    if (!results || results.length === 0) return [];
    const map = new Map();
    for (const r of results) {
      const type = r.Type;
      if (!map.has(type)) {
        map.set(type, { type, typeName: getTypeName(type), results: [], bestScore: r.Score });
      }
      map.get(type).results.push(r);
    }
    return [...map.values()].sort((a, b) => b.bestScore - a.bestScore);
  }

  function getSortedResults(results, type, columns) {
    const sort = sortState[type];
    if (!sort) return results;
    const col = columns.find(c => c.key === sort.key);
    if (!col) {
      // Sort by name
      if (sort.key === '_name') {
        return [...results].sort((a, b) => {
          const cmp = a.Name.localeCompare(b.Name);
          return sort.dir === 'asc' ? cmp : -cmp;
        });
      }
      return results;
    }
    return [...results].sort((a, b) => {
      const va = col.getValue(a);
      const vb = col.getValue(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      let cmp;
      if (typeof va === 'number' && typeof vb === 'number') {
        cmp = va - vb;
      } else {
        cmp = String(va).localeCompare(String(vb));
      }
      return sort.dir === 'asc' ? cmp : -cmp;
    });
  }

  function toggleSort(type, key) {
    const current = sortState[type];
    if (current?.key === key) {
      if (current.dir === 'asc') {
        sortState[type] = { key, dir: 'desc' };
      } else {
        // Third click removes sort
        delete sortState[type];
      }
    } else {
      sortState[type] = { key, dir: 'asc' };
    }
  }

  function getSortIndicator(type, key) {
    const sort = sortState[type];
    if (!sort || sort.key !== key) return '';
    return sort.dir === 'asc' ? ' ▲' : ' ▼';
  }

  function handleInput() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const q = searchInput.trim();
      updateUrl(q);
      performSearch(q);
    }, 300);
  }

  function handleKeydown(event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      clearTimeout(debounceTimer);
      const q = searchInput.trim();
      if (q.length >= 2) {
        updateUrl(q);
        performSearch(q);
      }
    }
  }

  function toggleGroup(type) {
    collapsedGroups[type] = !collapsedGroups[type];
  }

  function getLink(result) {
    if (result.Type === 'MobMaturity') {
      return getTypeLink(result.MobName, 'MobMaturity', result.SubType, result.MaturityId);
    }
    return getTypeLink(result.Name, result.Type, result.SubType, result.Id);
  }

  function handleRowClick(event, result) {
    // Don't navigate if clicking a link (let it handle naturally)
    if (event.target.closest('a')) return;
    const link = getLink(result);
    if (link) goto(link);
  }

  function getColumns(type) {
    const storage = browser ? localStorage : null;
    return getColumnsForType(type, storage);
  }
  // Group results by Type, preserving score order
  let groups = $derived(groupResults(results));
  let totalResults = $derived(results.length);
</script>

<svelte:head>
  <title>{currentQuery ? `Search: ${currentQuery}` : 'Search'} - Entropia Nexus</title>
</svelte:head>

<div class="search-page">
  <div class="search-header">
    <h1>Search</h1>
    <div class="search-input-container">
      <!-- svelte-ignore a11y_autofocus -- search page's primary purpose is searching; autofocus is intentional UX -->
      <input
        type="text"
        class="search-input"
        placeholder="Search items, mobs, skills, users..."
        bind:value={searchInput}
        oninput={handleInput}
        onkeydown={handleKeydown}
        autofocus
      />
      {#if isLoading}
        <div class="search-spinner"></div>
      {/if}
    </div>
  </div>

  <div class="search-results">
    {#if !currentQuery || currentQuery.length < 2}
      <p class="search-empty">Start typing to search across the entire database.</p>
    {:else if isLoading && totalResults === 0}
      <div class="search-loading">
        <div class="skeleton-row"></div>
        <div class="skeleton-row"></div>
        <div class="skeleton-row"></div>
      </div>
    {:else if totalResults === 0}
      <p class="search-empty">No results found for "{currentQuery}".</p>
    {:else}
      <p class="search-summary">Found {totalResults} result{totalResults !== 1 ? 's' : ''} for "{currentQuery}"</p>

      {#each groups as group (group.type)}
        {@const { columns } = getColumns(group.type)}
        {@const isCollapsed = collapsedGroups[group.type]}
        {@const sorted = getSortedResults(group.results, group.type, columns)}
        <div class="search-group">
          <button class="group-header" onclick={() => toggleGroup(group.type)}>
            <span class="group-toggle">{isCollapsed ? '▸' : '▾'}</span>
            <span class="group-name">{group.typeName}</span>
            <span class="group-count">{group.results.length}</span>
          </button>

          {#if !isCollapsed}
            <div class="group-content">
              <div class="table-wrapper">
                <table class="search-table">
                  <thead>
                    <tr>
                      <th class="col-name sortable" onclick={() => toggleSort(group.type, '_name')}>
                        Name{getSortIndicator(group.type, '_name')}
                      </th>
                      {#each columns as col}
                        <th class="sortable" style="width: {col.width}" onclick={() => toggleSort(group.type, col.key)}>
                          {col.header}{getSortIndicator(group.type, col.key)}
                        </th>
                      {/each}
                    </tr>
                  </thead>
                  <tbody>
                    {#each sorted as result, i}
                      {@const link = getLink(result)}
                      <tr
                        class:alt={i % 2 === 1}
                        class:clickable={!!link}
                        onclick={(e) => handleRowClick(e, result)}
                      >
                        <td class="col-name">
                          {#if link}
                            <a href={link}>{result.DisplayName || result.Name}{@html itemTypeBadge(result.Type)}</a>
                          {:else}
                            {result.DisplayName || result.Name}{@html itemTypeBadge(result.Type)}
                          {/if}
                        </td>
                        {#each columns as col}
                          <td style="width: {col.width}">{col.format(col.getValue(result))}</td>
                        {/each}
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            </div>
          {/if}
        </div>
      {/each}
    {/if}
  </div>
</div>

<style>
  .search-page {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1.5rem 1rem;
    min-height: 100%;
  }

  .search-header {
    margin-bottom: 1.5rem;
  }

  .search-header h1 {
    margin: 0 0 0.75rem;
    font-size: 1.5rem;
    color: var(--text-color);
  }

  .search-input-container {
    position: relative;
  }

  .search-input {
    width: 100%;
    padding: 0.6rem 0.75rem;
    font-size: 1rem;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    outline: none;
    box-sizing: border-box;
  }

  .search-input:focus {
    border-color: var(--accent-color);
  }

  .search-input::placeholder {
    color: var(--text-muted);
  }

  .search-spinner {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    width: 18px;
    height: 18px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: translateY(-50%) rotate(360deg); }
  }

  .search-empty {
    color: var(--text-muted);
    font-size: 0.95rem;
    margin-top: 1rem;
  }

  .search-summary {
    color: var(--text-muted);
    font-size: 0.9rem;
    margin: 0 0 1rem;
  }

  .search-loading {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  .skeleton-row {
    height: 28px;
    background: linear-gradient(90deg, var(--bg-secondary, var(--secondary-color)) 25%, var(--hover-color) 50%, var(--bg-secondary, var(--secondary-color)) 75%);
    background-size: 200% 100%;
    animation: skeleton-shimmer 1.5s ease-in-out infinite;
    border-radius: 4px;
  }

  @keyframes skeleton-shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  /* Group sections */
  .search-group {
    margin-bottom: 0.5rem;
  }

  .group-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.4rem 0.75rem;
    background: var(--hover-color);
    border: none;
    border-bottom: 1px solid var(--border-color);
    cursor: pointer;
    color: var(--text-color);
    font-size: 0.9rem;
    font-weight: 600;
    text-align: left;
    border-radius: 4px 4px 0 0;
  }

  .group-header:hover {
    background: var(--secondary-color);
  }

  .group-toggle {
    font-size: 0.8rem;
    width: 1em;
    flex-shrink: 0;
  }

  .group-name {
    flex: 1;
  }

  .group-count {
    font-size: 0.75rem;
    font-weight: normal;
    color: var(--text-muted);
    background: var(--secondary-color);
    padding: 0.1rem 0.4rem;
    border-radius: 10px;
  }

  .group-content {
    border: 1px solid var(--border-color);
    border-top: none;
    border-radius: 0 0 4px 4px;
  }

  /* Table styles */
  .table-wrapper {
    overflow-x: auto;
  }

  .search-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
  }

  .search-table th {
    padding: 0.25rem 0.5rem;
    text-align: left;
    font-weight: 600;
    color: var(--text-muted);
    background: var(--table-header-color);
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
    font-size: 0.75rem;
  }

  .search-table th.sortable {
    cursor: pointer;
    user-select: none;
  }

  .search-table th.sortable:hover {
    color: var(--text-color);
  }

  .search-table td {
    padding: 0.2rem 0.5rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .search-table tbody tr {
    background: var(--table-row-color);
  }

  .search-table tbody tr.alt {
    background: var(--table-row-color-alt);
  }

  .search-table tbody tr:hover {
    background: var(--table-row-hover-color);
  }

  .search-table tbody tr.clickable {
    cursor: pointer;
  }

  .col-name {
    min-width: 150px;
    max-width: 300px;
  }

  .search-table a {
    color: var(--text-color);
    text-decoration: none;
  }

  .search-table a:hover {
    text-decoration: underline;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .search-page {
      padding: 1rem 0.5rem;
    }

    .search-header h1 {
      font-size: 1.25rem;
    }

    .col-name {
      min-width: 120px;
    }

    .search-table th:nth-child(n+5),
    .search-table td:nth-child(n+5) {
      display: none;
    }
  }

  @media (max-width: 480px) {
    .search-table th:nth-child(n+4),
    .search-table td:nth-child(n+4) {
      display: none;
    }
  }
</style>
