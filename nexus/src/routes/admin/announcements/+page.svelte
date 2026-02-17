<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  let announcements = [];
  let total = 0;
  let currentPage = 1;
  let isLoading = true;
  let error = null;

  onMount(() => {
    loadAnnouncements();
  });

  async function loadAnnouncements() {
    isLoading = true;
    error = null;
    try {
      const response = await fetch(`/api/admin/announcements?page=${currentPage}&limit=20`);
      if (!response.ok) throw new Error('Failed to load announcements');
      const data = await response.json();
      announcements = data.announcements;
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
</script>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/admin">Admin</a>
    <span class="separator">/</span>
    <span>Announcements</span>
  </nav>

  <div class="page-header">
    <h1>Announcements</h1>
    <button class="action-btn" on:click={() => goto('/admin/announcements/new')}>
      New Announcement
    </button>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if isLoading}
    <div class="loading">Loading announcements...</div>
  {:else if announcements.length === 0}
    <div class="empty-state">No announcements yet. Create one to get started.</div>
  {:else}
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Status</th>
            <th>Author</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {#each announcements as item}
            <tr class="clickable-row" on:click={() => goto(`/admin/announcements/${item.id}`)}>
              <td class="title-cell">
                {item.title}
                {#if item.pinned}
                  <span class="badge badge-info">Pinned</span>
                {/if}
              </td>
              <td>
                {#if item.published}
                  <span class="badge badge-success">Published</span>
                {:else}
                  <span class="badge badge-muted">Draft</span>
                {/if}
              </td>
              <td>{item.author_name || '—'}</td>
              <td>{formatDate(item.created_at)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if total > 20}
      <div class="pagination">
        <button disabled={currentPage <= 1} on:click={() => { currentPage--; loadAnnouncements(); }}>Previous</button>
        <span>Page {currentPage} of {Math.ceil(total / 20)}</span>
        <button disabled={currentPage >= Math.ceil(total / 20)} on:click={() => { currentPage++; loadAnnouncements(); }}>Next</button>
      </div>
    {/if}
  {/if}
</div>

<style>
  .page-container {
    padding: 1rem;
    padding-bottom: 2rem;
    max-width: 1200px;
    margin: 0 auto;
    height: 100%;
    overflow-y: auto;
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

  .action-btn {
    padding: 0.5rem 1rem;
    background-color: var(--accent-color);
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
  }

  .action-btn:hover {
    background-color: var(--accent-color-hover);
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
    display: flex;
    align-items: center;
    gap: 0.5rem;
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
