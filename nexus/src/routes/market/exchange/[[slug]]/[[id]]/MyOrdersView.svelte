<script>
  //@ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { myOrders, enrichOrders, upsertOrder } from '../../exchangeStore.js';
  import { formatPedRaw, formatMarkupForItem, isLimited, formatPedValue, itemTypeBadge, getOrderStackValue, computeUnitPrice, getTopCategory, getCategoryOrder } from '../../orderUtils';
  import { encodeURIComponentSafe } from '$lib/util.js';
  import { PLATE_SET_SIZE } from '$lib/common/itemTypes.js';
  import { goto } from '$app/navigation';
  import { createEventDispatcher, onMount } from 'svelte';
  import { addToast } from '$lib/stores/toasts.js';

  export let user = null;
  export let sideFilter = 'all'; // 'all' | 'BUY' | 'SELL'
  /** @type {Array} All slim items for item type lookup */
  export let allItems = [];

  const dispatch = createEventDispatcher();
  let loading = false;
  let bumping = false;
  let error = null;

  // Build item lookup by ID
  $: itemLookup = (() => {
    const map = new Map();
    for (const item of allItems || []) {
      if (item?.i != null) map.set(item.i, item);
    }
    return map;
  })();

  $: filteredOrders = sideFilter === 'all'
    ? $myOrders
    : $myOrders.filter(o => o.type === sideFilter);

  const STATUS_ORDER = { active: 0, stale: 1, expired: 2, closed: 3 };

  // Enrich orders with computed fields for filtering and sorting
  // Pre-sorted by status (active first, closed last) then category
  $: enrichedOrders = filteredOrders.map(o => {
    const item = itemLookup.get(o.item_id);
    const mu = o.markup != null ? Number(o.markup) : null;
    return {
      ...o,
      _category: getTopCategory(item?.t),
      _value: getOrderStackValue(item, o) ?? null,
      _total: (() => {
        const u = computeUnitPrice(item, mu, o);
        if (u == null) return null;
        // Set orders: computeUnitPrice already includes full set TT, don't multiply by qty again
        const isSet = item?.t === 'ArmorPlating' && Number(o.quantity) === PLATE_SET_SIZE;
        return isSet ? u : u * (o.quantity || 1);
      })(),
    };
  }).sort((a, b) => {
    const sa = STATUS_ORDER[a.state_display] ?? 9;
    const sb = STATUS_ORDER[b.state_display] ?? 9;
    if (sa !== sb) return sa - sb;
    return getCategoryOrder(a._category) - getCategoryOrder(b._category);
  });

  // Summary of active sell orders
  $: orderSummary = (() => {
    const sells = enrichedOrders.filter(o => o.type === 'SELL' && o.state_display !== 'closed');
    let totalTT = 0, totalValue = 0;
    for (const o of sells) {
      if (o._value != null) totalTT += o._value;
      if (o._total != null) totalValue += o._total;
    }
    return { totalTT, totalValue, count: sells.length };
  })();

  $: columns = [
    {
      key: 'item_name', header: 'Item', main: true, mobileWidth: '1fr', sortable: true, searchable: true,
      formatter: (val, row) => {
        const slim = itemLookup.get(row.item_id);
        const setBadge = slim?.t === 'ArmorPlating' && Number(row.quantity) === PLATE_SET_SIZE ? ' <span class="badge badge-subtle badge-accent">Set</span>' : '';
        return `<a class="item-link" data-action="navigate" data-item-id="${row.item_id}">${val}${itemTypeBadge(slim?.t)}${setBadge}</a>`;
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
      key: 'quantity', header: 'Qty', width: '80px', sortable: true, searchable: true, hideOnMobile: true,
      formatter: (val, row) => row.min_quantity != null && row.min_quantity < val ? `${val}/${row.min_quantity}` : val
    },
    {
      key: '_value', header: 'Value', width: '90px', sortable: true, searchable: true, hideOnMobile: true,
      formatter: (val) => formatPedValue(val)
    },
    {
      key: 'markup', header: 'Markup', width: '90px', mobileWidth: '70px', sortable: true, searchable: true,
      formatter: (val, row) => {
        const item = itemLookup.get(row?.item_id);
        if (item) return formatMarkupForItem(val, item);
        return val != null ? formatPedRaw(val) : 'N/A';
      }
    },
    {
      key: '_total', header: 'Total', width: '110px', sortable: true, searchable: true, hideOnMobile: true,
      formatter: (val) => formatPedValue(val)
    },
    { key: 'planet', header: 'Planet', width: '100px', sortable: true, searchable: true, hideOnMobile: true },
    {
      key: 'state_display', header: 'Status', width: '80px', mobileWidth: '60px', sortable: true, searchable: true,
      formatter: (val) => {
        const cls = val === 'active' ? 'badge-success' : val === 'stale' ? 'badge-warning' : 'badge-error';
        return `<span class="badge badge-subtle ${cls}">${val}</span>`;
      }
    },
    {
      key: 'bumped_at', header: 'Last Bumped', width: '120px', sortable: true, searchable: false, hideOnMobile: true,
    formatter: (val) => formatAge(val)
    },
    {
      key: '_actions', header: '', width: '120px', mobileWidth: '80px', sortable: false, searchable: false,
      cellClass: () => 'cell-center',
      formatter: (val, row) => {
        if (row.state_display === 'closed') return '';
        return `<span class="order-actions">`
          + `<button class="order-action-btn edit" data-action="edit" data-id="${row.id}">Edit</button>`
          + `<button class="order-action-btn close" data-action="close" data-id="${row.id}">Close</button>`
          + `</span>`;
      }
    },
  ];

  onMount(loadOrders);

  async function loadOrders() {
    if (!user) return;
    if ($myOrders.length === 0) loading = true;
    error = null;
    try {
      const res = await fetch('/api/market/exchange/orders');
      if (!res.ok) throw new Error('Failed to load orders');
      const data = await res.json();
      myOrders.set(enrichOrders(data));
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function formatAge(dateStr) {
    if (!dateStr) return 'N/A';
    const ts = new Date(dateStr);
    const diff = Math.max(0, Date.now() - ts.getTime());
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  }

  /**
   * Bump all eligible (active/stale) orders.
   * Returns cooldown in seconds (1hr on success, retryAfter on rate-limit, null on error).
   */
  export async function bumpAll(turnstileToken = null) {
    bumping = true;
    try {
      const res = await fetch('/api/market/exchange/orders/bump-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ turnstile_token: turnstileToken })
      });
      const data = await res.json();
      if (res.status === 429) {
        addToast(data.error || 'Rate limited');
        return data.retryAfter || 3600;
      }
      if (!res.ok) throw new Error(data.error || 'Bump failed');
      const enriched = enrichOrders(data.orders);
      const updatedMap = new Map(enriched.map(o => [o.id, o]));
      myOrders.update(current => current.map(o => updatedMap.get(o.id) || o));
      return 3600;
    } catch (e) {
      addToast(e.message);
      return null;
    } finally {
      bumping = false;
    }
  }

  function handleClose(order) {
    dispatch('close', order);
  }

  function handleEdit(order) {
    dispatch('edit', order);
  }

  /** Intercept clicks on action buttons inside FancyTable rows */
  function handleTableClick(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    e.stopPropagation();
    e.preventDefault();

    const action = btn.dataset.action;

    if (action === 'navigate') {
      const itemId = btn.dataset.itemId;
      if (itemId) goto(`/market/exchange/listings/${itemId}`);
      return;
    }

    const id = parseInt(btn.dataset.id, 10);
    const order = $myOrders.find(o => o.id === id);
    if (!order) return;

    if (action === 'edit') handleEdit(order);
    else if (action === 'close') handleClose(order);
  }

  export function refresh() {
    return loadOrders();
  }

</script>

{#if !user}
  <div class="empty-state">
    <p>Please log in to view your orders.</p>
  </div>
{:else if error}
  <div class="error-state">
    <p>{error}</p>
    <button class="btn-retry" on:click={loadOrders}>Retry</button>
  </div>
{:else if loading}
  <div class="panel-loading">Loading orders...</div>
{:else}
  <div class="orders-table" role="presentation" on:click|capture={handleTableClick}>
    <FancyTable
      columns={columns}
      data={enrichedOrders}
      rowHeight={30}
      compact={true}
      sortable={true}
      searchable={true}
      defaultSort={null}
      emptyMessage={$myOrders.length === 0 ? 'You have no orders' : sideFilter === 'all' ? 'No orders match the current filters' : `No ${sideFilter === 'BUY' ? 'buy' : 'sell'} orders`}
      rowClass={(row) => {
        const s = row.state_display;
        return s === 'closed' ? 'row-closed' : s === 'stale' ? 'row-stale' : s === 'expired' ? 'row-expired' : null;
      }}
    />
  </div>
  {#if orderSummary.count > 0}
    <div class="order-summary">
      <span>Sell Orders: <strong>{orderSummary.count}</strong></span>
      <span>Total TT: <strong>{formatPedValue(orderSummary.totalTT)}</strong></span>
      <span>Total Value: <strong>{formatPedValue(orderSummary.totalValue)}</strong></span>
    </div>
  {/if}
{/if}

<style>
  .orders-table {
    flex: 1;
    min-height: 0;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    position: relative;
    margin-top: 8px;
  }
  .order-summary {
    display: flex;
    gap: 16px;
    padding: 8px 12px;
    margin-top: 4px;
    font-size: 12px;
    color: var(--text-muted);
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }
  .order-summary strong {
    color: var(--text-color);
  }
  .panel-loading {
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    margin-top: 8px;
    font-size: 13px;
    color: var(--text-muted);
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
  .orders-table :global(.row-stale) {
    opacity: 0.7;
  }
  .orders-table :global(.row-expired) {
    opacity: 0.45;
  }
  .orders-table :global(.row-closed) {
    text-decoration: line-through;
    color: var(--text-muted);
  }

  .orders-table :global(.cell-center) {
    justify-content: center;
  }

  /* Action buttons inside FancyTable cells */
  .orders-table :global(.order-actions) {
    display: flex;
    gap: 4px;
    align-items: center;
  }
  .orders-table :global(.order-action-btn) {
    padding: 2px 6px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--text-color);
    font-size: 11px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.15s ease;
  }
  .orders-table :global(.order-action-btn:hover) {
    background: var(--hover-color);
  }
  .orders-table :global(.order-action-btn.close) {
    color: var(--error-color, #ef4444);
    border-color: var(--error-color, #ef4444);
  }
  .orders-table :global(.order-action-btn.close:hover) {
    background: rgba(239, 68, 68, 0.15);
  }
  .orders-table :global(.item-link) {
    color: var(--accent-color);
    cursor: pointer;
    text-decoration: none;
  }
  .orders-table :global(.item-link:hover) {
    text-decoration: underline;
  }
</style>
