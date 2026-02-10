<script>
  //@ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { myOrders, enrichOrders } from '../../exchangeStore.js';
  import { encodeURIComponentSafe } from '$lib/util.js';
  import { goto } from '$app/navigation';
  import { createEventDispatcher, onMount } from 'svelte';

  export let user = null;
  export let sideFilter = 'all'; // 'all' | 'BUY' | 'SELL'

  const dispatch = createEventDispatcher();
  let loading = false;
  let bumping = false;
  let error = null;

  $: filteredOrders = sideFilter === 'all'
    ? $myOrders
    : $myOrders.filter(o => o.type === sideFilter);

  const columns = [
    {
      key: 'item_name', header: 'Item', main: true, sortable: true, searchable: true,
      formatter: (val, row) => `<a class="item-link" data-action="navigate" data-item-name="${val}" data-item-id="${row.item_id}">${val}</a>`
    },
    {
      key: 'type', header: 'Side', width: '70px', sortable: true, searchable: false,
      formatter: (val) => {
        const cls = val === 'BUY' ? 'badge-success' : 'badge-error';
        return `<span class="badge badge-subtle ${cls}">${val === 'BUY' ? 'Buy' : 'Sell'}</span>`;
      }
    },
    { key: 'quantity', header: 'Qty', width: '70px', sortable: true, searchable: false },
    {
      key: 'markup', header: 'Markup', width: '90px', sortable: true, searchable: false,
      formatter: (val) => val != null ? Number(val).toFixed(2) : 'N/A'
    },
    { key: 'planet', header: 'Planet', width: '100px', sortable: true, searchable: true },
    {
      key: 'state_display', header: 'Status', width: '80px', sortable: true, searchable: true,
      formatter: (val) => {
        const cls = val === 'active' ? 'badge-success' : val === 'stale' ? 'badge-warning' : 'badge-error';
        return `<span class="badge badge-subtle ${cls}">${val}</span>`;
      }
    },
    {
      key: 'bumped_at', header: 'Last Bumped', width: '120px', sortable: true, searchable: false,
      formatter: (val) => formatAge(val)
    },
    {
      key: '_actions', header: '', width: '120px', sortable: false, searchable: false,
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
    loading = true;
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

  /** Bump all eligible (active/stale) orders */
  export async function bumpAll() {
    const eligible = $myOrders.filter(o => {
      const s = o.computed_state || computeState(o.bumped_at);
      return s !== 'terminated' && s !== 'closed';
    });
    if (eligible.length === 0) return;

    bumping = true;
    error = null;
    let failed = 0;
    for (const order of eligible) {
      try {
        const res = await fetch(`/api/market/exchange/orders/${order.id}/bump`, { method: 'POST' });
        if (!res.ok) failed++;
      } catch { failed++; }
    }
    bumping = false;
    if (failed > 0) error = `Failed to bump ${failed} order(s)`;
    await loadOrders();
  }

  async function handleClose(order) {
    try {
      const res = await fetch(`/api/market/exchange/orders/${order.id}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Close failed');
      }
      await loadOrders();
    } catch (e) {
      error = e.message;
    }
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
      const name = btn.dataset.itemName;
      const itemId = btn.dataset.itemId;
      if (name) goto(`/market/exchange/listings/${encodeURIComponentSafe(name)}`);
      else if (itemId) goto(`/market/exchange/listings/${itemId}`);
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
{:else}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="orders-table" on:click|capture={handleTableClick}>
    <FancyTable
      columns={columns}
      data={filteredOrders}
      rowHeight={30}
      compact={true}
      sortable={true}
      searchable={true}
      emptyMessage={sideFilter === 'all' ? 'You have no orders' : `No ${sideFilter === 'BUY' ? 'buy' : 'sell'} orders`}
      rowClass={(row) => {
        const s = row.state_display;
        return s === 'closed' ? 'row-closed' : s === 'stale' ? 'row-stale' : s === 'expired' ? 'row-expired' : null;
      }}
    />
  </div>
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
    opacity: 0.35;
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
