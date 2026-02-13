<script>
  //@ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { goto } from '$app/navigation';
  import { tradeList } from '../../exchangeStore.js';
  import { isAbsoluteMarkup, formatMarkupForItem, formatPedValue, isBlueprintNonL, getUnitTT, computeUnitPrice } from '../../orderUtils';
  import { encodeURIComponentSafe } from '$lib/util.js';
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  /** @type {{ id: number|string, name: string } | null} */
  export let user = null;

  /** @type {Array} All slim items from the exchange categorized data */
  export let allItems = [];
  /** @type {boolean} Whether buy/sell action buttons should be shown */
  export let canTrade = true;

  let orders = [];
  let loading = false;
  let error = null;
  export let sideFilter = 'all'; // 'all' | 'BUY' | 'SELL'

  $: if (user?.id) loadOrders(user.id);

  // Build item lookup by ID: item_id -> slim item { i, n, t, v, ... }
  $: itemLookup = (() => {
    const map = new Map();
    for (const item of allItems || []) {
      if (item?.i != null) map.set(item.i, item);
    }
    return map;
  })();

  $: filteredOrders = sideFilter === 'all'
    ? orders
    : orders.filter(o => o.type === sideFilter);

  // Set of order IDs already in the trade list
  $: tradeListOrderIds = new Set($tradeList.map(i => i.orderId));

  async function loadOrders(userId) {
    loading = true;
    error = null;
    orders = [];
    try {
      const res = await fetch(`/api/market/exchange/orders/user/${userId}`);
      if (!res.ok) throw new Error('Failed to load orders');
      orders = await res.json();
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  export function refresh() {
    if (user?.id) loadOrders(user.id);
  }

  $: columns = (() => {
    const cols = [
      {
        key: 'details', header: 'Item', main: true, sortable: true, searchable: false,
        formatter: (v) => v?.item_name || 'Unknown'
      },
      {
        key: 'type', header: 'Side', width: '55px', sortable: true, searchable: false,
        formatter: (v) => {
          const cls = v === 'BUY' ? 'badge-success' : 'badge-error';
          return `<span class="badge badge-subtle ${cls}">${v === 'BUY' ? 'Buy' : 'Sell'}</span>`;
        }
      },
      { key: 'quantity', header: 'Qty', width: '90px', sortable: true, searchable: false },
      {
        key: '_tt', header: 'TT', width: '90px', sortable: true, searchable: false,
        formatter: (v, row) => {
          const item = itemLookup.get(row?.item_id);
          const tt = getUnitTT(item, row);
          return formatPedValue(tt);
        }
      },
      {
        key: 'markup', header: 'Markup', width: '100px', sortable: true, searchable: false,
        formatter: (v, row) => {
          const item = itemLookup.get(row?.item_id);
          return formatMarkupForItem(v, item);
        }
      },
      {
        key: '_total', header: 'Total', width: '120px', sortable: true, searchable: false,
        formatter: (v, row) => {
          const item = itemLookup.get(row?.item_id);
          const mu = row?.markup != null ? Number(row.markup) : null;
          const unitPrice = computeUnitPrice(item, mu, row);
          if (unitPrice == null) return 'N/A';
          const qty = row?.quantity ?? 1;
          return formatPedValue(unitPrice * qty);
        }
      },
      { key: 'planet', header: 'Planet', width: '80px', sortable: true, searchable: false },
    ];
    if (canTrade) {
      cols.push({
        key: '_action', header: '', width: '55px', sortable: false, searchable: false,
        cellClass: () => 'cell-center',
        formatter: (v, row) => {
          const orderId = row?.id ?? 0;
          const inList = tradeListOrderIds.has(orderId);
          if (inList) {
            return `<span class="cell-badge added-badge">Added</span>`;
          }
          const side = row?.type === 'SELL' ? 'buy' : 'sell';
          const label = side === 'buy' ? 'Buy' : 'Sell';
          const cls = side === 'buy' ? 'buy-order-btn' : 'sell-order-btn';
          return `<button class="cell-button ${cls}" data-order-action="${orderId}" data-action-side="${side}">${label}</button>`;
        }
      });
    }
    // Force re-evaluation when tradeListOrderIds changes
    tradeListOrderIds;
    canTrade;
    return cols;
  })();

  function handleClick(e) {
    if (!canTrade) return;
    const btn = e.target.closest('[data-order-action]');
    if (!btn) return;
    e.stopPropagation();
    e.preventDefault();

    const orderId = parseInt(btn.dataset.orderAction, 10);
    const side = btn.dataset.actionSide;
    const order = orders.find(o => o.id === orderId);
    if (!order) return;

    dispatch('orderAction', {
      orderId: order.id,
      itemId: order.item_id,
      itemName: order.details?.item_name || 'Unknown',
      sellerId: user?.id,
      sellerName: order.seller_name || user?.name || 'Unknown',
      planet: order.planet || '',
      quantity: order.quantity || 1,
      unitPrice: Number(order.markup) || 0,
      markup: Number(order.markup) || 0,
      side: order.type || 'SELL',
      order,
    });
  }

  function handleRowClick(e) {
    const row = e.detail?.row;
    if (!row) return;
    const item = itemLookup.get(row.item_id);
    const name = item?.n || row.details?.item_name;
    if (name) {
      goto(`/market/exchange/listings/${encodeURIComponentSafe(name)}`);
    } else if (row.item_id) {
      goto(`/market/exchange/listings/${row.item_id}`);
    }
  }

</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="user-orders-panel" on:click|capture={handleClick}>

  {#if loading}
    <div class="panel-loading">Loading orders...</div>
  {:else if error}
    <div class="panel-error">{error}</div>
  {:else if filteredOrders.length === 0}
    <div class="panel-empty">{orders.length === 0 ? 'No active orders' : 'No matching orders'}</div>
  {:else}
    <FancyTable
      {columns}
      data={filteredOrders}
      rowHeight={30}
      compact={true}
      sortable={true}
      searchable={false}
      emptyMessage="No orders"
      on:rowClick={handleRowClick}
    />
  {/if}
</div>

<style>
  .user-orders-panel {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .panel-loading, .panel-error, .panel-empty {
    padding: 24px;
    text-align: center;
    font-size: 13px;
    color: var(--text-muted);
  }
  .panel-error {
    color: var(--error-color, #ef4444);
  }
  .user-orders-panel :global(.cell-center) {
    justify-content: center;
  }
  .user-orders-panel :global(.buy-order-btn) {
    color: var(--success-color, #16a34a);
    border-color: var(--success-color, #16a34a);
  }
  .user-orders-panel :global(.buy-order-btn:hover) {
    background: rgba(22, 163, 74, 0.15);
  }
  .user-orders-panel :global(.sell-order-btn) {
    color: var(--error-color, #ef4444);
    border-color: var(--error-color, #ef4444);
  }
  .user-orders-panel :global(.sell-order-btn:hover) {
    background: rgba(239, 68, 68, 0.15);
  }
  .user-orders-panel :global(.added-badge) {
    font-size: 11px;
    color: var(--text-muted);
    font-style: italic;
  }
</style>
