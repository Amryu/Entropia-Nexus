<script>
  //@ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import FancyTable from '$lib/components/FancyTable.svelte';
  import ValueChart from './ValueChart.svelte';
  import { formatPedRaw } from '../../market/exchange/orderUtils';

  const dispatch = createEventDispatcher();

  let imports = [];
  let valueHistory = [];
  let loading = true;
  let loadingMore = false;
  let hasMore = true;
  let expandedId = null;
  let expandedDeltas = [];
  let loadingDeltas = false;

  const PAGE_SIZE = 20;

  const deltaColumns = [
    {
      key: 'delta_type', header: 'Change', sortable: true, width: '80px',
      formatter: (v) => `<span class="badge badge-subtle badge-${v === 'added' ? 'success' : v === 'removed' ? 'error' : 'warning'}">${v}</span>`,
    },
    { key: 'item_name', header: 'Item', main: true, sortable: true, searchable: true },
    {
      key: 'old_quantity', header: 'Old Qty', sortable: true, width: '70px',
      formatter: (v) => v != null ? v.toLocaleString() : '-',
    },
    {
      key: 'new_quantity', header: 'New Qty', sortable: true, width: '70px',
      formatter: (v) => v != null ? v.toLocaleString() : '-',
    },
    {
      key: 'container', header: 'Storage', sortable: true, width: '90px', hideOnMobile: true,
      formatter: (v) => v || '-',
    },
  ];

  async function loadData() {
    loading = true;
    try {
      const [importsRes, valueRes] = await Promise.all([
        fetch(`/api/users/inventory/imports?limit=${PAGE_SIZE}&offset=0`),
        fetch('/api/users/inventory/imports/value-history'),
      ]);

      if (importsRes.ok) {
        imports = await importsRes.json();
        hasMore = imports.length >= PAGE_SIZE;
      }
      if (valueRes.ok) {
        valueHistory = await valueRes.json();
      }
    } catch (err) {
      console.error('Error loading import history:', err);
    } finally {
      loading = false;
    }
  }

  async function loadMore() {
    loadingMore = true;
    try {
      const res = await fetch(`/api/users/inventory/imports?limit=${PAGE_SIZE}&offset=${imports.length}`);
      if (res.ok) {
        const more = await res.json();
        imports = [...imports, ...more];
        hasMore = more.length >= PAGE_SIZE;
      }
    } catch (err) {
      console.error('Error loading more imports:', err);
    } finally {
      loadingMore = false;
    }
  }

  async function toggleExpand(importRow) {
    if (expandedId === importRow.id) {
      expandedId = null;
      expandedDeltas = [];
      return;
    }

    expandedId = importRow.id;
    expandedDeltas = [];
    loadingDeltas = true;

    try {
      const res = await fetch(`/api/users/inventory/imports/${importRow.id}/deltas`);
      if (res.ok) {
        expandedDeltas = await res.json();
      }
    } catch (err) {
      console.error('Error loading deltas:', err);
    } finally {
      loadingDeltas = false;
    }
  }

  function formatDate(dateStr) {
    return new Date(dateStr).toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  function handleClose() {
    dispatch('close');
  }

  // Load on mount
  loadData();
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="modal-overlay" on:click|self={handleClose}>
  <div class="history-modal">
    <div class="history-header">
      <h2>Import History</h2>
      <button class="close-btn" on:click={handleClose}>&times;</button>
    </div>

    {#if loading}
      <p class="loading-msg">Loading history...</p>
    {:else}
      <!-- Value chart -->
      <ValueChart data={valueHistory} />

      <!-- Import list -->
      <div class="import-list">
        {#each imports as imp (imp.id)}
          <div class="import-row" class:expanded={expandedId === imp.id}>
            <div class="import-summary" on:click={() => toggleExpand(imp)}>
              <div class="import-date">{formatDate(imp.imported_at)}</div>
              <div class="import-stats">
                <span>{imp.item_count} items</span>
                {#if imp.estimated_value != null || imp.total_value != null}
                  {@const estVal = imp.estimated_value != null ? Number(imp.estimated_value) : null}
                  {@const ttVal = imp.total_value != null ? Number(imp.total_value) : null}
                  {@const unknownVal = imp.unknown_value != null ? Number(imp.unknown_value) : 0}
                  {@const displayTotal = (estVal != null ? estVal : (ttVal ?? 0)) + unknownVal}
                  <span class="import-value">{formatPedRaw(displayTotal)} PED</span>
                  {#if estVal != null && ttVal != null && Math.abs(estVal - ttVal) > 0.01}
                    <span class="import-secondary" title="TT Value">({formatPedRaw(ttVal)} TT)</span>
                  {/if}
                  {#if unknownVal > 0}
                    <span class="import-unknown" title="Unknown items value (at 100% MU)">+{formatPedRaw(unknownVal)} unknown</span>
                  {/if}
                {/if}
              </div>
              <div class="import-changes">
                {#if imp.summary}
                  {#if imp.summary.added}<span class="badge badge-subtle badge-success">+{imp.summary.added}</span>{/if}
                  {#if imp.summary.updated}<span class="badge badge-subtle badge-warning">~{imp.summary.updated}</span>{/if}
                  {#if imp.summary.removed}<span class="badge badge-subtle badge-error">-{imp.summary.removed}</span>{/if}
                {/if}
              </div>
              <span class="expand-icon">{expandedId === imp.id ? '▾' : '▸'}</span>
            </div>

            {#if expandedId === imp.id}
              <div class="import-deltas">
                {#if loadingDeltas}
                  <p class="loading-msg">Loading changes...</p>
                {:else if expandedDeltas.length > 0}
                  <FancyTable
                    columns={deltaColumns}
                    data={expandedDeltas}
                    rowHeight={36}
                    compact={true}
                    emptyMessage="No changes"
                  />
                {:else}
                  <p class="text-muted" style="text-align:center;padding:0.5rem;">No item changes recorded</p>
                {/if}
              </div>
            {/if}
          </div>
        {/each}

        {#if imports.length === 0}
          <p class="text-muted" style="text-align:center;padding:2rem;">No imports yet</p>
        {/if}

        {#if hasMore}
          <div class="load-more">
            <button class="btn btn-ghost btn-sm" on:click={loadMore} disabled={loadingMore}>
              {loadingMore ? 'Loading...' : 'Load more'}
            </button>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: flex-start;
    z-index: 1000;
    padding: 2rem 1rem;
    overflow-y: auto;
  }

  .history-modal {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    width: 700px;
    max-width: 100%;
    max-height: calc(100vh - 4rem);
    overflow-y: auto;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }

  .history-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }

  .history-header h2 {
    margin: 0;
    font-size: 1.25rem;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 22px;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }
  .close-btn:hover { color: var(--text-color); }

  .loading-msg {
    color: var(--text-muted);
    font-size: 13px;
    text-align: center;
    padding: 1rem 0;
  }

  .import-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  .import-row {
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
  }
  .import-row.expanded {
    border-color: var(--accent-color);
  }

  .import-summary {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.6rem 0.75rem;
    cursor: pointer;
    transition: background 0.15s;
  }
  .import-summary:hover {
    background: var(--bg-color);
  }

  .import-date {
    font-size: 0.82rem;
    white-space: nowrap;
    min-width: 150px;
  }

  .import-stats {
    display: flex;
    gap: 0.75rem;
    font-size: 0.82rem;
    flex: 1;
  }

  .import-value {
    font-weight: 500;
  }

  .import-secondary {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .import-unknown {
    font-size: 0.75rem;
    color: var(--warning-color);
  }

  .import-changes {
    display: flex;
    gap: 0.25rem;
  }

  .expand-icon {
    color: var(--text-muted);
    font-size: 12px;
    flex-shrink: 0;
  }

  .import-deltas {
    border-top: 1px solid var(--border-color);
    padding: 0.5rem;
    max-height: 300px;
    overflow-y: auto;
  }

  .load-more {
    text-align: center;
    padding: 0.5rem 0;
  }

  .load-more .btn {
    padding: 0.3rem 0.6rem;
    border-radius: 4px;
    font-size: 0.8rem;
    cursor: pointer;
    background: transparent;
    color: var(--text-muted);
    border: 1px solid var(--border-color);
  }

  .load-more .btn:hover:not(:disabled) {
    background: var(--hover-color);
    color: var(--text-color);
  }

  .load-more .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .text-muted {
    color: var(--text-muted);
  }

  @media (max-width: 600px) {
    .import-summary {
      flex-wrap: wrap;
    }
    .import-date {
      min-width: auto;
    }
  }
</style>
