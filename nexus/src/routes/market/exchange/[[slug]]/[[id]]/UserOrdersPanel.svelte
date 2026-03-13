<script>
  import { run } from 'svelte/legacy';

  //@ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { goto } from '$app/navigation';
  import { tradeList } from '../../exchangeStore.js';
  import { isAbsoluteMarkup, formatMarkupForItem, formatPedValue, isBlueprintNonL, getOrderStackValue, computeUnitPrice, itemTypeBadge, getTopCategory, getCategoryOrder } from '../../orderUtils';
  import { encodeURIComponentSafe } from '$lib/util.js';
  import { PLATE_SET_SIZE } from '$lib/common/itemTypes.js';
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  

  
  

  let orders = $state([]);
  let loading = $state(false);
  let error = $state(null);
  /**
   * @typedef {Object} Props
   * @property {{ id: number|string, name: string } | null} [user]
   * @property {Array} [allItems]
   * @property {boolean} [canTrade]
   * @property {string} [sideFilter] - 'all' | 'BUY' | 'SELL'
   */

  /** @type {Props} */
  let {
    user = null,
    allItems = [],
    canTrade = true,
    sideFilter = 'all'
  } = $props();






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

  /** Format order detail tags (Tier, TiR, QR, Level, Gender, Set) */
  function formatDetailTags(row) {
    const d = row?.details;
    if (!d) return '';
    const tags = [];

    if (d.Tier != null) tags.push(`<span class="detail-tag">T${d.Tier}</span>`);
    if (d.TierIncreaseRate != null) tags.push(`<span class="detail-tag">TiR ${d.TierIncreaseRate}</span>`);
    if (d.QualityRating != null) tags.push(`<span class="detail-tag">QR ${d.QualityRating}</span>`);
    if (d.Pet?.Level != null) tags.push(`<span class="detail-tag">Lv ${d.Pet.Level}</span>`);
    if (d.Gender) tags.push(`<span class="detail-tag">${d.Gender}</span>`);
    if (Number(row.quantity) === PLATE_SET_SIZE) tags.push(`<span class="detail-tag">Set</span>`);

    if (tags.length === 0) return '';
    return `<span class="detail-tags">${tags.join('')}</span>`;
  }


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

  run(() => {
    if (user?.id) loadOrders(user.id);
  });
  // Build item lookup by ID: item_id -> slim item { i, n, t, v, ... }
  let itemLookup = $derived((() => {
    const map = new Map();
    for (const item of allItems || []) {
      if (item?.i != null) map.set(item.i, item);
    }
    return map;
  })());
  let filteredOrders = $derived(sideFilter === 'all'
    ? orders
    : orders.filter(o => o.type === sideFilter));
  // Enrich orders with computed fields for filtering and sorting
  let enrichedOrders = $derived(filteredOrders.map(o => {
    const item = itemLookup.get(o.item_id);
    const mu = o.markup != null ? Number(o.markup) : null;
    return {
      ...o,
      _item_name: o.details?.item_name || 'Unknown',
      _category: getTopCategory(item?.t),
      _value: getOrderStackValue(item, o) ?? null,
      _total: (() => {
        const u = computeUnitPrice(item, mu, o);
        if (u == null) return null;
        const isSet = item?.t === 'ArmorPlating' && Number(o.quantity) === PLATE_SET_SIZE;
        return isSet ? u : u * (o.quantity || 1);
      })(),
    };
  }));
  // Set of order IDs already in the trade list
  let tradeListOrderIds = $derived(new Set($tradeList.map(i => i.orderId)));
  let columns = $derived((() => {
    const cols = [
      {
        key: '_item_name', header: 'Item', main: true, sortable: true, searchable: true,
        formatter: (v, row) => {
          const slim = itemLookup.get(row?.item_id);
          return v + itemTypeBadge(slim?.t);
        }
      },
      {
        key: 'type', header: 'Side', width: '55px', mobileWidth: '40px', sortable: true, searchable: false,
        formatter: (val) => {
          const cls = val === 'BUY' ? 'badge-success' : 'badge-error';
          return `<span class="badge badge-subtle ${cls}">${val === 'BUY' ? 'Buy' : 'Sell'}</span>`;
        }
      },
      {
        key: '_category', header: 'Category', width: '110px', sortable: true, searchable: true, hideOnMobile: true,
        sortValue: (row) => getCategoryOrder(row._category)
      },
      {
        key: '_details', header: 'Details', width: '150px', mobileWidth: '100px', sortable: false, searchable: false,
        formatter: (v, row) => formatDetailTags(row)
      },
      { key: 'quantity', header: 'Qty', width: '90px', sortable: true, searchable: true, hideOnMobile: true },
      {
        key: '_value', header: 'Value', width: '90px', sortable: true, searchable: true, hideOnMobile: true,
        formatter: (val) => formatPedValue(val)
      },
      {
        key: 'markup', header: 'Markup', width: '100px', mobileWidth: '80px', sortable: true, searchable: true,
        formatter: (v, row) => {
          const item = itemLookup.get(row?.item_id);
          return formatMarkupForItem(v, item);
        }
      },
      {
        key: '_total', header: 'Total', width: '120px', sortable: true, searchable: true, hideOnMobile: true,
        formatter: (val) => formatPedValue(val)
      },
      { key: 'planet', header: 'Planet', width: '80px', sortable: true, searchable: true, hideOnMobile: true },
    ];
    cols.push({
      key: '_action', header: '', width: '55px', sortable: false, searchable: false,
      cellClass: () => 'cell-center',
      formatter: canTrade ? (v, row) => {
        const orderId = row?.id ?? 0;
        const inList = tradeListOrderIds.has(orderId);
        if (inList) {
          return `<span class="cell-badge added-badge">Added</span>`;
        }
        const side = row?.type === 'SELL' ? 'buy' : 'sell';
        const label = side === 'buy' ? 'Buy' : 'Sell';
        const cls = side === 'buy' ? 'buy-order-btn' : 'sell-order-btn';
        return `<button class="cell-button ${cls}" data-order-action="${orderId}" data-action-side="${side}">${label}</button>`;
      } : () => ''
    });
    // Force re-evaluation when tradeListOrderIds changes
    tradeListOrderIds;
    canTrade;
    return cols;
  })());
</script>

<div class="user-orders-panel" role="presentation" onclickcapture={handleClick}>

  {#if loading}
    <div class="panel-loading">Loading orders...</div>
  {:else if error}
    <div class="panel-error">{error}</div>
  {:else}
    <FancyTable
      {columns}
      data={enrichedOrders}
      rowHeight={30}
      compact={true}
      sortable={true}
      searchable={true}
      defaultSort={{ column: '_category', order: 'ASC' }}
      emptyMessage={orders.length === 0 ? 'No active orders' : 'No matching orders'}
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

  /* Detail tags */
  .user-orders-panel :global(.detail-tags) {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
    align-items: center;
  }
  .user-orders-panel :global(.detail-tag) {
    font-size: 11px;
    padding: 2px 5px;
    border-radius: 3px;
    background: var(--accent-color-bg);
    color: var(--accent-color);
    white-space: nowrap;
  }
</style>
