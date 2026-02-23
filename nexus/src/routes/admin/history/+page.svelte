<script>
  // @ts-nocheck
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { apiCall, getTypeName } from '$lib/util.js';
  import { clickable } from '$lib/actions/clickable.js';

  let searchQuery = '';
  let selectedType = '';
  let results = [];
  let entityTypes = [];
  let isLoading = false;
  let isLoadingTypes = true;
  let error = null;
  let total = 0;
  let offset = 0;
  const limit = 50;

  onMount(async () => {
    try {
      // Use /api/ prefix to call local SvelteKit API (not external API)
      const response = await fetch('/api/admin/entity-changes/types');
      if (response.ok) {
        const data = await response.json();
        if (data?.types) {
          entityTypes = data.types;
        }
      }
    } catch (err) {
      console.error('Failed to load entity types:', err);
    } finally {
      isLoadingTypes = false;
    }

    // Load initial results
    await search();
  });

  async function search(resetOffset = true) {
    if (resetOffset) offset = 0;
    isLoading = true;
    error = null;

    try {
      const params = new URLSearchParams();
      if (searchQuery) params.set('q', searchQuery);
      if (selectedType) params.set('type', selectedType);
      params.set('limit', String(limit));
      params.set('offset', String(offset));

      // Use /api/ prefix to call local SvelteKit API
      const response = await fetch(`/api/admin/entity-changes/search?${params}`);
      if (response.ok) {
        const data = await response.json();
        results = data.results || [];
        total = data.total || 0;
      } else {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'Failed to search');
      }
    } catch (err) {
      error = err.message;
    } finally {
      isLoading = false;
    }
  }

  function handleSearch() {
    search(true);
  }

  function handleKeydown(event) {
    if (event.key === 'Enter') {
      handleSearch();
    }
  }

  function handleTypeChange() {
    search(true);
  }

  function loadMore() {
    offset += limit;
    search(false);
  }

  function loadPrevious() {
    offset = Math.max(0, offset - limit);
    search(false);
  }

  function viewEntity(item) {
    if (item.entityId) {
      goto(`/admin/history/${item.entityType}/${item.entityId}`);
    } else {
      // For Create changes without an ID, use the name
      goto(`/admin/history/${item.entityType}/${encodeURIComponent(item.entityName)}`);
    }
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  }
</script>

<svelte:head>
  <title>Entity History | Admin | Entropia Nexus</title>
</svelte:head>

<style>
  .history-page {
    max-width: 1200px;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    font-size: 14px;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .breadcrumb span {
    color: var(--text-muted);
  }

  h1 {
    margin: 0 0 8px 0;
    font-size: 28px;
    color: var(--text-color);
  }

  .subtitle {
    color: var(--text-muted);
    margin: 0 0 24px 0;
    font-size: 14px;
  }

  .search-controls {
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
    flex-wrap: wrap;
  }

  .search-input {
    flex: 1;
    min-width: 200px;
    padding: 10px 14px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 14px;
  }

  .search-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .type-select {
    padding: 10px 14px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 14px;
    min-width: 180px;
  }

  .search-btn {
    padding: 10px 20px;
    background-color: var(--accent-color);
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    cursor: pointer;
    transition: background-color 0.15s ease;
  }

  .search-btn:hover {
    background-color: var(--accent-color-hover);
  }

  .results-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    color: var(--text-muted);
    font-size: 14px;
  }

  .results-list {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }

  .result-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    border-bottom: 1px solid var(--border-color);
    cursor: pointer;
    transition: background-color 0.15s ease;
    gap: 16px;
  }

  .result-item:last-child {
    border-bottom: none;
  }

  .result-item:hover {
    background-color: var(--hover-color);
  }

  .result-main {
    flex: 1;
    min-width: 0;
  }

  .result-name {
    font-weight: 500;
    color: var(--text-color);
    margin-bottom: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .result-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 12px;
    color: var(--text-muted);
    flex-wrap: wrap;
  }

  .type-badge {
    display: inline-block;
    padding: 2px 8px;
    background-color: var(--hover-color);
    border-radius: 4px;
    font-size: 11px;
    color: var(--accent-color);
  }

  .result-stats {
    text-align: right;
    flex-shrink: 0;
  }

  .change-count {
    font-size: 20px;
    font-weight: bold;
    color: var(--accent-color);
  }

  .change-label {
    font-size: 11px;
    color: var(--text-muted);
  }

  .pagination {
    display: flex;
    justify-content: center;
    gap: 12px;
    margin-top: 20px;
  }

  .pagination button {
    padding: 8px 16px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .pagination button:hover:not(:disabled) {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .pagination button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .loading, .error, .empty {
    text-align: center;
    padding: 40px;
    color: var(--text-muted);
  }

  .error {
    color: var(--error-color);
  }

  /* Mobile responsive */
  @media (max-width: 768px) {
    h1 {
      font-size: 22px;
    }

    .subtitle {
      font-size: 13px;
    }

    .breadcrumb {
      font-size: 12px;
      flex-wrap: wrap;
    }

    .search-controls {
      flex-direction: column;
    }

    .search-input,
    .type-select {
      width: 100%;
      min-width: unset;
    }

    .result-item {
      flex-direction: column;
      align-items: flex-start;
      gap: 12px;
      padding: 12px 14px;
    }

    .result-stats {
      text-align: left;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .change-count {
      font-size: 16px;
    }

    .change-label {
      font-size: 12px;
    }

    .pagination {
      flex-direction: column;
    }

    .pagination button {
      width: 100%;
    }
  }
</style>

<div class="history-page">
  <div class="breadcrumb">
    <a href="/admin">Admin</a>
    <span>/</span>
    <span>Entity History</span>
  </div>

  <h1>Entity History</h1>
  <p class="subtitle">Search for entities with change requests and view their complete history</p>

  <div class="search-controls">
    <input
      type="text"
      class="search-input"
      placeholder="Search by entity name..."
      bind:value={searchQuery}
      on:keydown={handleKeydown}
    />
    <select class="type-select" bind:value={selectedType} on:change={handleTypeChange}>
      <option value="">All Types</option>
      {#each entityTypes as type}
        <option value={type.entityType}>{getTypeName(type.entityType)} ({type.count})</option>
      {/each}
    </select>
    <button class="search-btn" on:click={handleSearch} disabled={isLoading}>
      {isLoading ? 'Searching...' : 'Search'}
    </button>
  </div>

  {#if error}
    <div class="error">Error: {error}</div>
  {:else if isLoading && results.length === 0}
    <div class="loading">Loading...</div>
  {:else if results.length === 0}
    <div class="empty">No entities with change requests found</div>
  {:else}
    <div class="results-info">
      <span>Showing {offset + 1}-{Math.min(offset + results.length, total)} of {total} entities</span>
    </div>

    <div class="results-list">
      {#each results as item}
        <div class="result-item" use:clickable on:click={() => viewEntity(item)}>
          <div class="result-main">
            <div class="result-name">{item.entityName || 'Unnamed'}</div>
            <div class="result-meta">
              <span class="type-badge">{getTypeName(item.entityType)}</span>
              {#if item.entityId}
                <span>ID: {item.entityId}</span>
              {/if}
              <span>First: {formatDate(item.firstChange)}</span>
              <span>Last: {formatDate(item.lastChange)}</span>
            </div>
          </div>
          <div class="result-stats">
            <div class="change-count">{item.changeCount}</div>
            <div class="change-label">change{item.changeCount !== 1 ? 's' : ''}</div>
          </div>
        </div>
      {/each}
    </div>

    {#if total > limit}
      <div class="pagination">
        <button on:click={loadPrevious} disabled={offset === 0 || isLoading}>
          Previous
        </button>
        <button on:click={loadMore} disabled={offset + results.length >= total || isLoading}>
          Next
        </button>
      </div>
    {/if}
  {/if}
</div>
