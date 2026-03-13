<script>
  import { createBubbler, stopPropagation } from 'svelte/legacy';

  const bubble = createBubbler();
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { encodeURIComponentSafe } from '$lib/util';
  import { clickable } from '$lib/actions/clickable.js';

  let changes = $state([]);
  let total = $state(0);
  let currentPage = $state(1);
  let totalPages = $state(1);
  let isLoading = $state(true);
  let error = $state(null);

  // Filters
  let stateFilter = $state('');
  let entityFilter = $state('');
  let searchFilter = $state('');
  let searchTimeout = null;

  // Entity types grouped by category
  const entityCategories = {
    'Items': ['Weapon', 'ArmorSet', 'MedicalTool', 'MedicalChip', 'Refiner', 'Scanner', 'Finder', 'Excavator', 'TeleportChip', 'EffectChip', 'MiscTool', 'WeaponAmplifier', 'WeaponVisionAttachment', 'Absorber', 'FinderAmplifier', 'ArmorPlating', 'MindforceImplant', 'Blueprint', 'Material', 'Pet', 'Consumable', 'CreatureControlCapsule', 'Vehicle', 'Furniture', 'Decoration', 'StorageContainer', 'Sign', 'Clothing'],
    'Information': ['Mob', 'Vendor', 'RefiningRecipe'],
    'Market': ['Shop']
  };

  const stateOptions = ['Draft', 'Pending', 'Approved', 'Denied', 'Deleted', 'DirectApply', 'ApplyFailed'];

  onMount(() => {
    // Read initial filters from URL
    const urlState = $page.url.searchParams.get('state');
    if (urlState) stateFilter = urlState;

    const urlEntity = $page.url.searchParams.get('entity');
    if (urlEntity) entityFilter = urlEntity;

    const urlSearch = $page.url.searchParams.get('search');
    if (urlSearch) searchFilter = urlSearch;

    const urlPage = $page.url.searchParams.get('page');
    if (urlPage) currentPage = parseInt(urlPage);

    loadChanges();
  });

  async function loadChanges() {
    isLoading = true;
    error = null;

    try {
      const params = new URLSearchParams();
      params.set('page', String(currentPage));
      params.set('limit', '20');

      if (stateFilter) params.set('state', stateFilter);
      if (entityFilter) params.set('entity', entityFilter);
      if (searchFilter) params.set('search', searchFilter);

      const response = await fetch(`/api/admin/changes?${params}`);
      if (!response.ok) throw new Error('Failed to load changes');

      const data = await response.json();
      changes = data.changes;
      total = data.total;
      totalPages = data.totalPages;
      currentPage = data.page;

      // Update URL
      updateUrl();
    } catch (err) {
      error = err.message;
    } finally {
      isLoading = false;
    }
  }

  function updateUrl() {
    const params = new URLSearchParams();
    if (stateFilter) params.set('state', stateFilter);
    if (entityFilter) params.set('entity', entityFilter);
    if (searchFilter) params.set('search', searchFilter);
    if (currentPage > 1) params.set('page', String(currentPage));

    const url = params.toString() ? `/admin/changes?${params}` : '/admin/changes';
    goto(url, { replaceState: true, keepFocus: true });
  }

  function handleFilterChange() {
    currentPage = 1;
    loadChanges();
  }

  function handleSearchInput() {
    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      currentPage = 1;
      loadChanges();
    }, 300);
  }

  function clearFilters() {
    stateFilter = '';
    entityFilter = '';
    searchFilter = '';
    currentPage = 1;
    loadChanges();
  }

  function getStateClass(state) {
    switch (state) {
      case 'Pending': return 'state-pending';
      case 'DirectApply': return 'state-pending';
      case 'Approved': return 'state-approved';
      case 'Denied': return 'state-denied';
      case 'ApplyFailed': return 'state-denied';
      case 'Draft': return 'state-draft';
      case 'Deleted': return 'state-deleted';
      default: return '';
    }
  }

  function getTypeClass(type) {
    switch (type) {
      case 'Create': return 'type-create';
      case 'Update': return 'type-update';
      case 'Delete': return 'type-delete';
      default: return '';
    }
  }

  function getProfileUrl(id, euName) {
    if (!id && !euName) return null;
    return `/admin/users/${encodeURIComponentSafe(String(id))}`;
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString();
  }
</script>

<svelte:head>
  <title>Changes | Admin | Entropia Nexus</title>
</svelte:head>

<style>
  .changes-page {
    max-width: 1400px;
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

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
  }

  h1 {
    margin: 0;
    font-size: 24px;
    color: var(--text-color);
  }

  .filters {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
    align-items: center;
  }

  .filter-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .filter-group label {
    font-size: 11px;
    text-transform: uppercase;
    color: var(--text-muted);
    letter-spacing: 0.5px;
  }

  .filter-group select,
  .filter-group input {
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 14px;
    min-width: 150px;
  }

  .filter-group input {
    min-width: 200px;
  }

  .btn-clear {
    padding: 8px 16px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--hover-color);
    color: var(--text-color);
    font-size: 14px;
    cursor: pointer;
    align-self: flex-end;
    transition: all 0.15s ease;
  }

  .btn-clear:hover {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .results-info {
    font-size: 13px;
    color: var(--text-muted);
    margin-bottom: 16px;
  }

  .changes-table {
    width: 100%;
    border-collapse: collapse;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    font-size: 14px;
  }

  .changes-table th,
  .changes-table td {
    padding: 12px 16px;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
  }

  .changes-table th {
    background-color: var(--hover-color);
    font-weight: 600;
    color: var(--text-color);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .changes-table tbody tr {
    cursor: pointer;
    transition: background-color 0.1s ease;
  }

  .changes-table tbody tr:hover {
    background-color: rgba(59, 130, 246, 0.1);
  }

  .changes-table tbody tr:last-child td {
    border-bottom: none;
  }

  .badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
  }

  .state-pending {
    background-color: rgba(245, 158, 11, 0.2);
    color: var(--warning-color);
  }

  .state-approved {
    background-color: rgba(16, 185, 129, 0.2);
    color: var(--success-color);
  }

  .state-denied {
    background-color: rgba(239, 68, 68, 0.2);
    color: var(--error-color);
  }

  .state-draft {
    background-color: var(--hover-color);
    color: var(--text-muted);
  }

  .state-deleted {
    background-color: rgba(107, 114, 128, 0.2);
    color: #6b7280;
  }

  .type-create {
    background-color: rgba(34, 197, 94, 0.2);
    color: #22c55e;
  }

  .type-update {
    background-color: rgba(59, 130, 246, 0.2);
    color: var(--accent-color);
  }

  .type-delete {
    background-color: rgba(239, 68, 68, 0.2);
    color: var(--error-color);
  }

  .author-cell {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .author-link {
    color: var(--accent-color);
    text-decoration: none;
  }

  .author-link:hover {
    text-decoration: underline;
  }

  .author-avatar {
    width: 24px;
    height: 24px;
    border-radius: 50%;
  }

  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    margin-top: 20px;
  }

  .btn-page {
    padding: 8px 16px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--hover-color);
    color: var(--text-color);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-page:hover:not(:disabled) {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .btn-page:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .page-info {
    font-size: 14px;
    color: var(--text-muted);
  }

  .loading, .error, .empty {
    text-align: center;
    padding: 40px;
    color: var(--text-muted);
  }

  .error {
    color: var(--error-color);
  }

  .entity-name {
    font-weight: 500;
    color: var(--text-color);
  }

  .entity-type {
    font-size: 12px;
    color: var(--text-muted);
  }

  /* Mobile responsive */
  @media (max-width: 900px) {
    .changes-table {
      display: none;
    }

    .mobile-cards {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .mobile-card {
      background-color: var(--secondary-color);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 12px;
      cursor: pointer;
      transition: background-color 0.1s ease;
    }

    .mobile-card:hover {
      background-color: rgba(59, 130, 246, 0.1);
    }

    .mobile-card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 8px;
      margin-bottom: 8px;
    }

    .mobile-card-title {
      flex: 1;
      min-width: 0;
    }

    .mobile-card-title .entity-name {
      font-size: 14px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .mobile-card-badges {
      display: flex;
      gap: 6px;
      flex-shrink: 0;
    }

    .mobile-card-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 16px;
      font-size: 12px;
      color: var(--text-muted);
    }

    .mobile-card-meta-item {
      display: flex;
      gap: 4px;
    }

    .mobile-card-meta-label {
      color: var(--text-muted);
    }

    .mobile-card-meta-value {
      color: var(--text-color);
    }
  }

  @media (min-width: 901px) {
    .mobile-cards {
      display: none;
    }
  }

  @media (max-width: 768px) {
    .breadcrumb {
      font-size: 12px;
      flex-wrap: wrap;
    }

    h1 {
      font-size: 20px;
    }

    .filters {
      flex-direction: column;
      align-items: stretch;
    }

    .filter-group {
      width: 100%;
    }

    .filter-group select,
    .filter-group input {
      width: 100%;
      min-width: unset;
    }

    .btn-clear {
      align-self: stretch;
      text-align: center;
    }

    .pagination {
      gap: 8px;
    }

    .btn-page {
      padding: 6px 12px;
      font-size: 13px;
    }

    .page-info {
      font-size: 12px;
    }
  }
</style>

<div class="changes-page">
  <div class="breadcrumb">
    <a href="/admin">Admin</a>
    <span>/</span>
    <span>Changes</span>
  </div>

  <div class="page-header">
    <h1>Change Monitoring</h1>
  </div>

  <div class="filters">
    <div class="filter-group">
      <label>State</label>
      <select bind:value={stateFilter} onchange={handleFilterChange}>
        <option value="">All States</option>
        {#each stateOptions as state}
          <option value={state}>{state}</option>
        {/each}
      </select>
    </div>

    <div class="filter-group">
      <label>Entity Type</label>
      <select bind:value={entityFilter} onchange={handleFilterChange}>
        <option value="">All Entities</option>
        {#each Object.entries(entityCategories) as [category, entities]}
          <optgroup label={category}>
            {#each entities as entity}
              <option value={entity}>{entity}</option>
            {/each}
          </optgroup>
        {/each}
      </select>
    </div>

    <div class="filter-group">
      <label>Search by Name</label>
      <input
        type="text"
        placeholder="Search..."
        bind:value={searchFilter}
        oninput={handleSearchInput}
      />
    </div>

    {#if stateFilter || entityFilter || searchFilter}
      <button class="btn-clear" onclick={clearFilters}>Clear Filters</button>
    {/if}
  </div>

  {#if !isLoading}
    <p class="results-info">
      Showing {changes.length} of {total} changes
      {#if stateFilter || entityFilter || searchFilter}
        (filtered)
      {/if}
    </p>
  {/if}

  {#if isLoading}
    <div class="loading">Loading changes...</div>
  {:else if error}
    <div class="error">Error: {error}</div>
  {:else if changes.length === 0}
    <div class="empty">No changes found matching your filters.</div>
  {:else}
    <table class="changes-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Entity</th>
          <th>Type</th>
          <th>State</th>
          <th>Author</th>
          <th>Created</th>
          <th>Reviewed</th>
        </tr>
      </thead>
      <tbody>
        {#each changes as change}
          <tr onclick={() => goto(`/admin/changes/${change.id}`)}>
            <td>#{change.id}</td>
            <td>
              <div class="entity-name">{change.entityName}</div>
              <div class="entity-type">{change.entity}</div>
            </td>
            <td>
              <span class="badge {getTypeClass(change.type)}">{change.type}</span>
            </td>
            <td>
              <span class="badge {getStateClass(change.state)}">{change.state}</span>
            </td>
            <td>
              <div class="author-cell">
                {#if getProfileUrl(change.author_id, change.author_eu_name)}
                  <a
                    class="author-link"
                    href={getProfileUrl(change.author_id, change.author_eu_name)}
                    onclick={stopPropagation(bubble('click'))}
                  >
                    {change.author_name || 'Unknown'}
                  </a>
                {:else}
                  <span>{change.author_name || 'Unknown'}</span>
                {/if}
              </div>
            </td>
            <td>{formatDate(change.created_at || change.last_update)}</td>
            <td>
              {#if change.reviewed_at}
                {#if getProfileUrl(change.reviewed_by, null)}
                  <a
                    class="author-link"
                    href={getProfileUrl(change.reviewed_by, null)}
                    onclick={stopPropagation(bubble('click'))}
                  >
                    {change.reviewer_name || 'Unknown'}
                  </a>
                {:else}
                  <div>{change.reviewer_name || 'Unknown'}</div>
                {/if}
                <div class="entity-type">{formatDate(change.reviewed_at)}</div>
              {:else}
                -
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>

    <!-- Mobile card view -->
    <div class="mobile-cards">
      {#each changes as change}
        <div class="mobile-card" use:clickable onclick={() => goto(`/admin/changes/${change.id}`)}>
          <div class="mobile-card-header">
            <div class="mobile-card-title">
              <div class="entity-name">{change.entityName}</div>
              <div class="entity-type">{change.entity} • #{change.id}</div>
            </div>
            <div class="mobile-card-badges">
              <span class="badge {getTypeClass(change.type)}">{change.type}</span>
              <span class="badge {getStateClass(change.state)}">{change.state}</span>
            </div>
          </div>
          <div class="mobile-card-meta">
            <div class="mobile-card-meta-item">
              <span class="mobile-card-meta-label">By:</span>
              {#if getProfileUrl(change.author_id, change.author_eu_name)}
                <a
                  class="mobile-card-meta-value author-link"
                  href={getProfileUrl(change.author_id, change.author_eu_name)}
                  onclick={stopPropagation(bubble('click'))}
                >
                  {change.author_name || 'Unknown'}
                </a>
              {:else}
                <span class="mobile-card-meta-value">{change.author_name || 'Unknown'}</span>
              {/if}
            </div>
            <div class="mobile-card-meta-item">
              <span class="mobile-card-meta-label">Created:</span>
              <span class="mobile-card-meta-value">{formatDate(change.created_at || change.last_update)}</span>
            </div>
          </div>
        </div>
      {/each}
    </div>

    {#if totalPages > 1}
      <div class="pagination">
        <button
          class="btn-page"
          disabled={currentPage <= 1}
          onclick={() => { currentPage--; loadChanges(); }}
        >
          Previous
        </button>
        <span class="page-info">Page {currentPage} of {totalPages}</span>
        <button
          class="btn-page"
          disabled={currentPage >= totalPages}
          onclick={() => { currentPage++; loadChanges(); }}
        >
          Next
        </button>
      </div>
    {/if}
  {/if}
</div>
