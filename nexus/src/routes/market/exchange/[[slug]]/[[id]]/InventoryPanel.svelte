<script>
  //@ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { inventory } from '../../exchangeStore.js';
  import { onMount } from 'svelte';

  export let user = null;

  let loading = false;
  let error = null;

  const columns = [
    { key: 'item_name', header: 'Item', main: true, sortable: true, searchable: true },
    { key: 'quantity', header: 'Qty', width: '60px', sortable: true, searchable: false },
    {
      key: 'value', header: 'Value', width: '80px', sortable: true, searchable: false,
      hideOnMobile: true,
      formatter: (val) => val != null ? Number(val).toFixed(2) : '<span style="opacity:0.4">—</span>'
    },
    {
      key: 'container', header: 'Container', width: '140px', sortable: true, searchable: true,
      hideOnMobile: true,
      formatter: (val) => val || '<span style="opacity:0.4">—</span>'
    },
    {
      key: '_actions', header: '', width: '50px', sortable: false, searchable: false,
      formatter: (val, row) => {
        return `<button class="inv-remove-btn" data-action="remove" data-id="${row.id}" title="Remove">&#x2715;</button>`;
      }
    },
  ];

  onMount(loadInventory);

  async function loadInventory() {
    if (!user) return;
    loading = true;
    error = null;
    try {
      const res = await fetch('/api/users/inventory');
      if (!res.ok) throw new Error('Failed to load inventory');
      const data = await res.json();
      inventory.set(data || []);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function handleRemove(item) {
    try {
      const res = await fetch(`/api/users/inventory/${item.id}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Delete failed');
      }
      await loadInventory();
    } catch (e) {
      error = e.message;
    }
  }

  /** Intercept clicks on action buttons inside FancyTable rows */
  function handleTableClick(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    e.stopPropagation();
    e.preventDefault();

    const action = btn.dataset.action;
    const id = parseInt(btn.dataset.id, 10);
    const item = $inventory.find(i => i.id === id);
    if (!item) return;

    if (action === 'remove') handleRemove(item);
  }

  export function refresh() {
    loadInventory();
  }
</script>

{#if !user}
  <div class="empty-state">
    <p>Please log in to view your inventory.</p>
  </div>
{:else if error}
  <div class="error-state">
    <p>{error}</p>
    <button class="btn-retry" on:click={loadInventory}>Retry</button>
  </div>
{:else}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="inventory-table" on:click|capture={handleTableClick}>
    <FancyTable
      columns={columns}
      data={$inventory}
      rowHeight={36}
      compact={true}
      sortable={true}
      searchable={true}
      emptyMessage="No items in your inventory. Use Import to add items."
    />
  </div>

  {#if $inventory.length > 0}
    <div class="info-bar">
      <p class="item-count">{$inventory.length} item{$inventory.length !== 1 ? 's' : ''}</p>
    </div>
  {/if}
{/if}

<style>
  .inventory-table {
    flex: 1;
    min-height: 0;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    position: relative;
  }
  .empty-state, .error-state {
    text-align: center;
    padding: 3rem 2rem;
    color: var(--text-muted);
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }
  .error-state { color: var(--error-color); }
  .btn-retry {
    padding: 6px 14px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: transparent;
    color: var(--text-color);
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s ease;
  }
  .btn-retry:hover { background: var(--hover-color); border-color: var(--border-hover); }
  .info-bar {
    display: flex;
    align-items: center;
    padding: 6px 16px;
    flex-shrink: 0;
  }
  .item-count {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
  }

  /* Remove button inside FancyTable cells */
  .inventory-table :global(.inv-remove-btn) {
    padding: 2px 6px;
    border: 1px solid var(--error-color, #ef4444);
    border-radius: 4px;
    background: transparent;
    color: var(--error-color, #ef4444);
    font-size: 12px;
    cursor: pointer;
    line-height: 1;
    transition: all 0.15s ease;
  }
  .inventory-table :global(.inv-remove-btn:hover) {
    background: rgba(239, 68, 68, 0.15);
  }
</style>
