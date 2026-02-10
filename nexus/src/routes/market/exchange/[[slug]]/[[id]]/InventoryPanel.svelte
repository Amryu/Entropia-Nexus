<script>
  //@ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import InventoryItemDialog from './InventoryItemDialog.svelte';
  import { inventory, myOrders, enrichOrders } from '../../exchangeStore.js';
  import { isItemStackable } from '../../orderUtils';
  import { MAX_ORDERS_PER_SIDE } from '../../exchangeConstants.js';
  import { encodeURIComponentSafe } from '$lib/util.js';
  import { goto } from '$app/navigation';
  import { createEventDispatcher, onMount } from 'svelte';

  const MAX_ORDERS_PER_ITEM = 5;

  export let user = null;
  export let allItems = [];

  const dispatch = createEventDispatcher();

  let loading = false;
  let error = null;

  // Config dialog state
  let showConfigDialog = false;
  let configItem = null;

  // Mass sell mode
  let massSellMode = false;
  let massSellList = new Map(); // Map<inventory_id, { invItem, count }>

  $: totalMassSellOrders = (() => {
    let total = 0;
    for (const entry of massSellList.values()) total += entry.count;
    return total;
  })();

  export function setMassSellMode(enabled) {
    massSellMode = enabled;
    if (!massSellMode) massSellList = new Map();
  }

  function getItemLimit(itemId) {
    const slim = (allItems || []).find(si => si?.i === itemId);
    return isItemStackable(slim) ? 1 : MAX_ORDERS_PER_ITEM;
  }

  // Count existing sell orders for this user
  $: existingSellCount = ($myOrders || []).filter(o => o.type === 'SELL').length;

  // Count mass sell orders for a specific item_id across all selections
  function getMassSellCountForItem(itemId) {
    let count = 0;
    for (const entry of massSellList.values()) {
      if (entry.invItem.item_id === itemId) count += entry.count;
    }
    return count;
  }

  // Check if one more order can be added for this item: per-item limit (5) and global limit (200)
  function canAddItem(invItem) {
    const limit = getItemLimit(invItem.item_id);
    const existingForItem = OrdersByItemId.get(invItem.item_id)?.sell || 0;
    const massSellForItem = getMassSellCountForItem(invItem.item_id);
    if (existingForItem + massSellForItem >= limit) return { allowed: false, reason: `Maximum ${limit} sell order${limit > 1 ? 's' : ''} per item reached` };
    if (existingSellCount + totalMassSellOrders >= MAX_ORDERS_PER_SIDE) return { allowed: false, reason: `Maximum ${MAX_ORDERS_PER_SIDE} sell orders reached` };
    return { allowed: true, reason: '' };
  }

  function addToMassSell(invItem) {
    const { allowed } = canAddItem(invItem);
    if (!allowed) return;
    massSellList.set(invItem.id, { invItem, count: 1 });
    massSellList = massSellList; // trigger reactivity
  }

  function removeFromMassSell(invItemId) {
    massSellList.delete(invItemId);
    massSellList = massSellList;
  }

  function adjustMassSellCount(invItem, delta) {
    const entry = massSellList.get(invItem.id);
    if (!entry) return;
    const newCount = entry.count + delta;
    if (newCount <= 0) {
      removeFromMassSell(invItem.id);
      return;
    }
    if (delta > 0 && !canAddItem(invItem).allowed) return;
    entry.count = newCount;
    massSellList = massSellList;
  }

  function openMassSellDialog() {
    dispatch('massSell', { items: Array.from(massSellList.values()) });
  }

  // Build order count lookup: item_id → { buy, sell }
  $: OrdersByItemId = (() => {
    const map = new Map();
    for (const order of ($myOrders || [])) {
      if (!map.has(order.item_id)) {
        map.set(order.item_id, { buy: 0, sell: 0 });
      }
      const entry = map.get(order.item_id);
      if (order.type === 'BUY') entry.buy++;
      else if (order.type === 'SELL') entry.sell++;
    }
    return map;
  })();

  // Sort inventory: items with active sell orders first
  $: sortedInventory = [...($inventory || [])].sort((a, b) => {
    const aOrders = OrdersByItemId.get(a.item_id)?.sell || 0;
    const bOrders = OrdersByItemId.get(b.item_id)?.sell || 0;
    if (aOrders > 0 && bOrders === 0) return -1;
    if (aOrders === 0 && bOrders > 0) return 1;
    return 0;
  });

  $: columns = (() => {
    // Reference dependencies to trigger re-evaluation
    OrdersByItemId;
    massSellMode;
    massSellList;
    return [
      {
        key: 'item_name', header: 'Item', main: true, sortable: true, searchable: true,
        formatter: (val, row) => `<a class="item-link" data-action="navigate" data-item-name="${val}" data-item-id="${row.item_id}">${val}</a>`
      },
      {
        key: '_orders', header: 'Orders', width: '70px', sortable: true, searchable: false,
        hideOnMobile: true,
        sortValue: (row) => {
          const info = OrdersByItemId.get(row.item_id);
          const sell = info?.sell || 0;
          const limit = getItemLimit(row.item_id);
          // Items with active orders first, then by fullness ratio
          return sell > 0 ? 1 + sell / limit : 0;
        },
        formatter: (val, row) => {
          const info = OrdersByItemId.get(row.item_id);
          const sell = info?.sell || 0;
          const limit = getItemLimit(row.item_id);
          const full = sell >= limit ? ' full' : '';
          const active = sell > 0 ? ' active' : '';
          return `<span class="inv-order-badge${full}${active}">${sell}/${limit}</span>`;
        }
      },
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
          if (massSellMode) {
            const entry = massSellList.get(row.id);
            if (entry) {
              const limit = getItemLimit(row.item_id);
              if (limit <= 1) {
                // Fungible: just checkmark + remove
                return `<span class="inv-actions">`
                  + `<span class="mass-sell-check">&#10003;</span>`
                  + `<button class="inv-action-btn mass-remove" data-action="mass-remove" data-id="${row.id}" title="Remove from list">&#x2715;</button>`
                  + `</span>`;
              }
              // Non-fungible: -/count/+
              const { allowed } = canAddItem(row);
              return `<span class="inv-actions mass-counter">`
                + `<button class="inv-action-btn mass-minus" data-action="mass-minus" data-id="${row.id}">&#8722;</button>`
                + `<span class="mass-count">${entry.count}</span>`
                + `<button class="inv-action-btn mass-plus" data-action="mass-plus" data-id="${row.id}"${!allowed ? ' disabled' : ''}>+</button>`
                + `</span>`;
            }
            const { allowed, reason } = canAddItem(row);
            if (!allowed) {
              return `<span class="inv-actions"><button class="inv-action-btn mass-add" disabled title="${reason}">Add</button></span>`;
            }
            return `<span class="inv-actions">`
              + `<button class="inv-action-btn mass-add" data-action="mass-add" data-id="${row.id}" title="Add to mass sell list">Add</button>`
              + `</span>`;
          }
          return `<span class="inv-actions">`
            + `<button class="inv-action-btn config" data-action="config" data-id="${row.id}" title="Edit details">&#9881;</button>`
            + `<button class="inv-action-btn sell" data-action="sell" data-id="${row.id}" title="Create sell order">&#36;</button>`
            + `<button class="inv-action-btn remove" data-action="remove" data-id="${row.id}" title="Remove">&#x2715;</button>`
            + `</span>`;
        }
      },
    ];
  })();

  onMount(() => {
    loadInventory();
    loadOrders();
  });

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

  async function loadOrders() {
    if (!user || $myOrders.length > 0) return;
    try {
      const res = await fetch('/api/market/exchange/orders');
      if (!res.ok) return;
      myOrders.set(enrichOrders(await res.json()));
    } catch { /* ignore — orders column just stays empty */ }
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
      // Also remove from mass sell list if present
      if (massSellList.has(item.id)) {
        massSellList.delete(item.id);
        massSellList = massSellList;
      }
    } catch (e) {
      error = e.message;
    }
  }

  function handleConfig(item) {
    configItem = item;
    showConfigDialog = true;
  }

  function handleSell(invItem) {
    // Check for existing sell order for this item
    const existingOrder = ($myOrders || []).find(
      o => o.type === 'SELL' && o.item_id === invItem.item_id
    );

    dispatch('sell', {
      invItem,
      existingOrder: existingOrder || null,
    });
  }

  /** Intercept clicks on action buttons inside FancyTable rows */
  function handleTableClick(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    e.stopPropagation();
    e.preventDefault();

    const action = btn.dataset.action;

    if (action === 'navigate') {
      const name = btn.dataset.itemName;
      const itemId = btn.dataset.itemId;
      if (name) goto(`/market/exchange/listings/${encodeURIComponentSafe(name)}`);
      else if (itemId) goto(`/market/exchange/listings/${itemId}`);
      return;
    }

    const id = parseInt(btn.dataset.id, 10);
    const item = $inventory.find(i => i.id === id);
    if (!item) return;

    if (action === 'remove') handleRemove(item);
    else if (action === 'config') handleConfig(item);
    else if (action === 'sell') handleSell(item);
    else if (action === 'mass-add') addToMassSell(item);
    else if (action === 'mass-remove') removeFromMassSell(item.id);
    else if (action === 'mass-minus') adjustMassSellCount(item, -1);
    else if (action === 'mass-plus') adjustMassSellCount(item, 1);
  }

  export function refresh() {
    loadInventory();
  }

  export function clearMassSell() {
    massSellList = new Map();
    massSellMode = false;
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
      data={sortedInventory}
      rowHeight={36}
      compact={true}
      sortable={true}
      searchable={true}
      emptyMessage="No items in your inventory. Use Import to add items."
    />
    {#if massSellMode && massSellList.size > 0}
      <div class="mass-sell-bar">
        <span class="mass-sell-bar-text">{massSellList.size} items, {totalMassSellOrders} orders</span>
        <button class="mass-sell-submit" on:click={openMassSellDialog}>Configure &amp; Submit</button>
      </div>
    {/if}
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

  /* Mass sell action buttons */
  .inventory-table :global(.inv-action-btn.mass-add) {
    width: auto;
    padding: 0 8px;
    font-size: 11px;
    font-weight: 500;
    color: var(--success-color);
    border-color: var(--success-color);
  }
  .inventory-table :global(.inv-action-btn.mass-add:hover) {
    background: var(--success-bg);
  }
  .inventory-table :global(.inv-action-btn.mass-remove) {
    color: var(--error-color);
    border-color: var(--error-color);
  }
  .inventory-table :global(.inv-action-btn.mass-remove:hover) {
    background: rgba(239, 68, 68, 0.15);
  }
  .inventory-table :global(.mass-sell-check) {
    color: var(--success-color);
    font-size: 14px;
    font-weight: 600;
  }
  .inventory-table :global(.mass-counter) {
    gap: 2px;
  }
  .inventory-table :global(.mass-count) {
    font-size: 12px;
    font-weight: 600;
    min-width: 18px;
    text-align: center;
    color: var(--text-color);
  }
  .inventory-table :global(.inv-action-btn.mass-minus),
  .inventory-table :global(.inv-action-btn.mass-plus) {
    width: 22px;
    height: 22px;
    font-size: 14px;
  }
  .inventory-table :global(.inv-action-btn:disabled) {
    opacity: 0.3;
    cursor: not-allowed;
  }

  /* Mass sell floating bar */
  .mass-sell-bar {
    position: sticky;
    bottom: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: var(--secondary-color);
    border-top: 1px solid var(--border-color);
    z-index: 5;
  }
  .mass-sell-bar-text {
    font-size: 12px;
    color: var(--text-muted);
  }
  .mass-sell-submit {
    padding: 6px 14px;
    border: 1px solid var(--accent-color);
    border-radius: 6px;
    background: var(--accent-color);
    color: white;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .mass-sell-submit:hover {
    background: var(--accent-color-hover);
  }

  /* Order indicator badges */
  .inventory-table :global(.inv-order-badge) {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    background: transparent;
  }
  .inventory-table :global(.inv-order-badge.active) {
    background: rgba(59, 130, 246, 0.15);
    color: var(--accent-color);
  }
  .inventory-table :global(.inv-order-badge.full) {
    background: rgba(245, 158, 11, 0.2);
    color: var(--warning-color);
  }
  .inventory-table :global(.item-link) {
    color: var(--accent-color);
    cursor: pointer;
    text-decoration: none;
  }
  .inventory-table :global(.item-link:hover) {
    text-decoration: underline;
  }
</style>
