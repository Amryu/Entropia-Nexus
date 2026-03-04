<script>
  // @ts-nocheck
  import { onMount } from 'svelte';

  let clients = [];
  let isLoading = true;
  let error = null;

  onMount(() => {
    loadClients();
  });

  async function loadClients() {
    isLoading = true;
    error = null;
    try {
      const response = await fetch('/api/admin/oauth/clients');
      if (!response.ok) throw new Error('Failed to load OAuth clients');
      const data = await response.json();
      clients = data.clients;
    } catch (err) {
      error = err.message;
    } finally {
      isLoading = false;
    }
  }

  function formatDate(dateStr) {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric'
    });
  }

  function formatDateTime(dateStr) {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  }
</script>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/admin">Admin</a>
    <span class="separator">/</span>
    <span>OAuth Applications</span>
  </nav>

  <div class="page-header">
    <h1>OAuth Applications</h1>
    {#if !isLoading}
      <span class="count">{clients.length} application{clients.length !== 1 ? 's' : ''}</span>
    {/if}
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if isLoading}
    <div class="loading">Loading OAuth applications...</div>
  {:else if clients.length === 0}
    <div class="empty-state">No OAuth applications registered.</div>
  {:else}
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>Application</th>
            <th>Owner</th>
            <th>Type</th>
            <th>Created</th>
            <th class="num">Active Tokens</th>
            <th class="num">Users</th>
            <th>Last Used</th>
            <th class="num">Refresh Tokens</th>
            <th>Refresh Last Used</th>
          </tr>
        </thead>
        <tbody>
          {#each clients as client}
            <tr>
              <td>
                <div class="app-name">{client.name}</div>
                {#if client.description}
                  <div class="app-desc">{client.description}</div>
                {/if}
              </td>
              <td>
                <a href="/admin/users/{client.owner_id}" class="owner-link">{client.owner_name}</a>
              </td>
              <td>
                <span class="badge" class:badge-info={client.is_confidential} class:badge-muted={!client.is_confidential}>
                  {client.is_confidential ? 'Confidential' : 'Public'}
                </span>
              </td>
              <td>{formatDate(client.created_at)}</td>
              <td class="num">{client.active_tokens}</td>
              <td class="num">{client.authorized_users}</td>
              <td class="last-used">{formatDateTime(client.last_used)}</td>
              <td class="num">{client.active_refresh_tokens}</td>
              <td class="last-used">{formatDateTime(client.refresh_last_used)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
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

  .count {
    color: var(--text-muted);
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
    white-space: nowrap;
  }

  .data-table th.num,
  .data-table td.num {
    text-align: right;
  }

  .data-table td {
    padding: 0.75rem;
    border-bottom: 1px solid var(--border-color);
    vertical-align: top;
  }

  .app-name {
    font-weight: 500;
  }

  .app-desc {
    color: var(--text-muted);
    font-size: 0.8rem;
    margin-top: 0.15rem;
  }

  .owner-link {
    color: var(--accent-color);
    text-decoration: none;
  }

  .owner-link:hover {
    text-decoration: underline;
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

  .badge-info {
    background: rgba(74, 158, 255, 0.15);
    color: var(--accent-color);
  }

  .badge-muted {
    background: rgba(74, 222, 128, 0.15);
    color: #4ade80;
  }

  .last-used {
    white-space: nowrap;
    font-size: 0.85rem;
  }

  @media (max-width: 899px) {
    .page-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }
  }
</style>
