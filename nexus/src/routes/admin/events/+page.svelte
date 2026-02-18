<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  let events = [];
  let total = 0;
  let currentPage = 1;
  let stateFilter = '';
  let isLoading = true;
  let error = null;

  onMount(() => {
    loadEvents();
  });

  async function loadEvents() {
    isLoading = true;
    error = null;
    try {
      let url = `/api/admin/events?page=${currentPage}&limit=20`;
      if (stateFilter) url += `&state=${stateFilter}`;
      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to load events');
      const data = await response.json();
      events = data.events;
      total = data.total;
    } catch (err) {
      error = err.message;
    } finally {
      isLoading = false;
    }
  }

  function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  }

  function handleFilterChange() {
    currentPage = 1;
    loadEvents();
  }
</script>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/admin">Admin</a>
    <span class="separator">/</span>
    <span>Events</span>
  </nav>

  <div class="page-header">
    <h1>Events</h1>
    <div class="header-actions">
      <select class="state-filter" bind:value={stateFilter} on:change={handleFilterChange}>
        <option value="">All States</option>
        <option value="pending">Pending</option>
        <option value="approved">Approved</option>
        <option value="denied">Denied</option>
      </select>
    </div>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if isLoading}
    <div class="loading">Loading events...</div>
  {:else if events.length === 0}
    <div class="empty-state">No events found{stateFilter ? ` with state "${stateFilter}"` : ''}.</div>
  {:else}
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Type</th>
            <th>Start Date</th>
            <th>State</th>
            <th>Submitted By</th>
          </tr>
        </thead>
        <tbody>
          {#each events as event}
            <tr class="clickable-row" on:click={() => goto(`/admin/events/${event.id}`)}>
              <td class="title-cell">{event.title}</td>
              <td>
                <span class="badge" class:badge-info={event.type === 'official'} class:badge-muted={event.type !== 'official'}>
                  {event.type === 'official' ? 'Official' : 'Player Run'}
                </span>
              </td>
              <td>{formatDate(event.start_date)}</td>
              <td>
                {#if event.state === 'pending'}
                  <span class="badge badge-warning">Pending</span>
                {:else if event.state === 'approved'}
                  <span class="badge badge-success">Approved</span>
                {:else}
                  <span class="badge badge-danger">Denied</span>
                {/if}
              </td>
              <td>{event.submitted_by_name || '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if total > 20}
      <div class="pagination">
        <button disabled={currentPage <= 1} on:click={() => { currentPage--; loadEvents(); }}>Previous</button>
        <span>Page {currentPage} of {Math.ceil(total / 20)}</span>
        <button disabled={currentPage >= Math.ceil(total / 20)} on:click={() => { currentPage++; loadEvents(); }}>Next</button>
      </div>
    {/if}
  {/if}
</div>

<style>
  .page-container {
    max-width: 1200px;
    padding-bottom: 2rem;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .separator {
    color: var(--text-muted);
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
    margin: 0;
  }

  .header-actions {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .state-filter {
    padding: 0.4rem 0.75rem;
    background-color: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    border: 1px solid var(--error-color);
    margin-bottom: 1rem;
  }

  .loading, .empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted);
  }

  .table-container {
    overflow-x: auto;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
  }

  .data-table th {
    text-align: left;
    padding: 0.75rem;
    border-bottom: 2px solid var(--border-color);
    color: var(--text-muted);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .data-table td {
    padding: 0.75rem;
    border-bottom: 1px solid var(--border-color);
  }

  .clickable-row {
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .clickable-row:hover {
    background-color: var(--hover-color);
  }

  .title-cell {
    font-weight: 500;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    padding: 0.15rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 600;
    white-space: nowrap;
  }

  .badge-success {
    background: var(--success-bg);
    color: var(--success-color);
  }

  .badge-warning {
    background: rgba(234, 179, 8, 0.15);
    color: #eab308;
  }

  .badge-danger {
    background: var(--error-bg);
    color: var(--error-color);
  }

  .badge-muted {
    background: var(--hover-color);
    color: var(--text-muted);
  }

  .badge-info {
    background: rgba(74, 158, 255, 0.15);
    color: var(--accent-color);
  }

  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 1rem;
    margin-top: 1.5rem;
  }

  .pagination button {
    padding: 0.4rem 0.8rem;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    cursor: pointer;
  }

  .pagination button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .pagination span {
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  @media (max-width: 899px) {
    .page-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.75rem;
    }
  }
</style>
