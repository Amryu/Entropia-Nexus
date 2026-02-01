<!--
  @component HistoryPanel
  Displays entity change history in a compact panel format.
  Used within wiki pages to show recent changes and link to full history.
-->
<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { apiCall } from '$lib/util.js';

  /** @type {string} Entity type (e.g., 'weapon', 'mob') */
  export let entityType = '';

  /** @type {number|string} Entity ID */
  export let entityId = '';

  /** @type {string} Entity name for display */
  export let entityName = '';

  /** @type {number} Max number of changes to show */
  export let maxItems = 5;

  let changes = [];
  let isLoading = true;
  let error = null;

  onMount(async () => {
    if (entityType && entityId) {
      await loadHistory();
    }
  });

  async function loadHistory() {
    isLoading = true;
    error = null;

    try {
      const data = await apiCall(fetch, `/entity-changes/${entityType}/${encodeURIComponent(entityId)}`);
      if (data?.changes) {
        // Sort by date descending and take maxItems
        changes = data.changes
          .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
          .slice(0, maxItems);
      }
    } catch (err) {
      // If 404 or no changes, that's ok - just show empty
      if (err.status !== 404) {
        error = err.message || 'Failed to load history';
      }
    } finally {
      isLoading = false;
    }
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;

    // Within last 24 hours, show relative time
    if (diff < 24 * 60 * 60 * 1000) {
      const hours = Math.floor(diff / (60 * 60 * 1000));
      if (hours === 0) {
        const minutes = Math.floor(diff / (60 * 1000));
        return minutes <= 1 ? 'Just now' : `${minutes}m ago`;
      }
      return `${hours}h ago`;
    }

    // Within last 7 days, show day name
    if (diff < 7 * 24 * 60 * 60 * 1000) {
      const days = Math.floor(diff / (24 * 60 * 60 * 1000));
      return `${days}d ago`;
    }

    // Otherwise show date
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
    });
  }

  function getTypeIcon(type) {
    switch (type?.toLowerCase()) {
      case 'create': return '+';
      case 'update': return '~';
      case 'delete': return '-';
      default: return '?';
    }
  }

  function getStateClass(state) {
    switch (state) {
      case 'Approved': return 'state-approved';
      case 'Denied': return 'state-denied';
      case 'Pending': return 'state-pending';
      default: return 'state-draft';
    }
  }

  $: adminHistoryUrl = `/admin/history/${entityType}/${encodeURIComponent(entityId)}`;
</script>

<div class="history-panel">
  <div class="panel-header">
    <h4>Recent Changes</h4>
    {#if changes.length > 0}
      <a href={adminHistoryUrl} class="view-all">View all</a>
    {/if}
  </div>

  <div class="panel-content">
    {#if isLoading}
      <div class="loading">
        <div class="spinner"></div>
        <span>Loading...</span>
      </div>
    {:else if error}
      <div class="error">{error}</div>
    {:else if changes.length === 0}
      <div class="empty">No changes recorded</div>
    {:else}
      <ul class="changes-list">
        {#each changes as change}
          <li class="change-item">
            <span class="change-icon" class:create={change.type === 'Create'} class:update={change.type === 'Update'} class:delete={change.type === 'Delete'}>
              {getTypeIcon(change.type)}
            </span>
            <div class="change-info">
              <span class="change-type">{change.type}</span>
              <span class="change-date">{formatDate(change.createdAt)}</span>
            </div>
            <span class="state-badge {getStateClass(change.state)}">{change.state}</span>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</div>

<style>
  .history-panel {
    background-color: var(--secondary-color, #2a2a2a);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    overflow: hidden;
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color, #555);
    background-color: var(--tertiary-color, #333);
  }

  .panel-header h4 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color, #fff);
  }

  .view-all {
    font-size: 12px;
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .view-all:hover {
    text-decoration: underline;
  }

  .panel-content {
    padding: 8px;
  }

  .loading, .error, .empty {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 24px 16px;
    color: var(--text-muted, #999);
    font-size: 13px;
    text-align: center;
  }

  .error {
    color: var(--error-color, #ef4444);
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.2);
    border-top-color: var(--accent-color, #4a9eff);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .changes-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .change-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 8px;
    border-radius: 4px;
    transition: background-color 0.15s;
  }

  .change-item:hover {
    background-color: var(--hover-color, #444);
  }

  .change-icon {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    font-size: 14px;
    font-weight: 600;
    flex-shrink: 0;
  }

  .change-icon.create {
    background-color: rgba(74, 222, 128, 0.2);
    color: var(--success-color, #4ade80);
  }

  .change-icon.update {
    background-color: rgba(74, 158, 255, 0.2);
    color: var(--accent-color, #4a9eff);
  }

  .change-icon.delete {
    background-color: rgba(239, 68, 68, 0.2);
    color: var(--error-color, #ef4444);
  }

  .change-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .change-type {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-color, #fff);
  }

  .change-date {
    font-size: 11px;
    color: var(--text-muted, #999);
  }

  .state-badge {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    flex-shrink: 0;
  }

  .state-approved {
    background-color: rgba(74, 222, 128, 0.2);
    color: var(--success-color, #4ade80);
  }

  .state-denied {
    background-color: rgba(239, 68, 68, 0.2);
    color: var(--error-color, #ef4444);
  }

  .state-pending {
    background-color: rgba(245, 158, 11, 0.2);
    color: var(--warning-color, #f59e0b);
  }

  .state-draft {
    background-color: var(--hover-color, #444);
    color: var(--text-muted, #999);
  }

  /* Mobile - aligned with global 900px breakpoint */
  @media (max-width: 899px) {
    .panel-header {
      padding: 10px 12px;
    }

    .panel-content {
      padding: 6px;
    }

    .change-item {
      padding: 8px 6px;
    }
  }
</style>
