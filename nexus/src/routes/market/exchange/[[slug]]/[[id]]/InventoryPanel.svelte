<script>
  //@ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import InventoryItemDialog from './InventoryItemDialog.svelte';
  import { inventory, myOffers } from '../../exchangeStore.js';
  import { createEventDispatcher, onMount } from 'svelte';

  export let user = null;
  export let allItems = [];

  const dispatch = createEventDispatcher();

  let loading = false;
  let error = null;

  // Config dialog state
  let showConfigDialog = false;
  let configItem = null;

  const columns = [
    { key: 'item_name', header: 'Item', main: true, sortable: true, searchable: true },
    { key: 'quantity', header: 'Qty', width: '60px', sortable: true, searchable: false },
    {
      key: 'value', header: 'Value', width: '80px', sortable: true, searchable: false,
      hideOnMobile: true,
      formatter: (val) => val != null ? Number(val).toFixed(2) : '<span style="opacity:0.4">\u2014</span>'
    },
    {
      key: 'container', header: 'Container', width: '140px', sortable: true, searchable: true,
      hideOnMobile: true,
      formatter: (val) => val || '<span style="opacity:0.4">Inventory</span>'
    },
    {
      key: '_actions', header: '', width: '110px', sortable: false, searchable: false,
      formatter: (val, row) => {
        return `<span class="inv-actions">`
          + `<button class="inv-action-btn config" data-action="config" data-id="${row.id}" title="Edit details">&#9881;</button>`
          + `<button class="inv-action-btn sell" data-action="sell" data-id="${row.id}" title="Create sell offer">&#36;</button>`
          + `<button class="inv-action-btn remove" data-action="remove" data-id="${row.id}" title="Remove">&#x2715;</button>`
          + `</span>`;
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
      // Remove from store directly
      inventory.update(inv => inv.filter(i => i.id !== item.id));
    } catch (e) {
      error = e.message;
    }
  }

  function handleConfig(item) {
    configItem = item;
    showConfigDialog = true;
  }

  function handleSell(invItem) {
    // Check for existing sell offer for this item
    const existingOffer = ($myOffers || []).find(
      o => o.type === 'SELL' && o.item_id === invItem.item_id
    );

    dispatch('sell', {
      invItem,
      existingOffer: existingOffer || null,
    });
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
    else if (action === 'config') handleConfig(item);
    else if (action === 'sell') handleSell(item);
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
{/if}

<InventoryItemDialog
  show={showConfigDialog}
  item={configItem}
  {allItems}
  on:close={() => { showConfigDialog = false; }}
/>

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

  /* Action buttons inside FancyTable cells */
  .inventory-table :global(.inv-actions) {
    display: flex;
    gap: 4px;
    align-items: center;
  }
  .inventory-table :global(.inv-action-btn) {
    width: 26px;
    height: 24px;
    padding: 0;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--text-muted);
    font-size: 13px;
    cursor: pointer;
    line-height: 1;
    transition: all 0.15s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .inventory-table :global(.inv-action-btn:hover) {
    color: var(--text-color);
    border-color: var(--border-hover);
    background: var(--hover-color);
  }
  .inventory-table :global(.inv-action-btn.sell) {
    color: var(--success-color);
    border-color: var(--success-color);
    font-weight: 600;
  }
  .inventory-table :global(.inv-action-btn.sell:hover) {
    background: var(--success-bg);
  }
  .inventory-table :global(.inv-action-btn.remove) {
    color: var(--error-color);
    border-color: var(--error-color);
  }
  .inventory-table :global(.inv-action-btn.remove:hover) {
    background: rgba(239, 68, 68, 0.15);
  }
</style>
