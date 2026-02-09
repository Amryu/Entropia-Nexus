<script>
  //@ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { tradeRequests } from '../../exchangeStore.js';

  /** @type {object|null} Current user */
  export let user = null;

  let loading = false;
  let error = null;

  $: if (user?.id) loadTradeRequests();

  async function loadTradeRequests() {
    loading = true;
    error = null;
    try {
      const res = await fetch('/api/market/trade-requests');
      if (!res.ok) throw new Error('Failed to load trade requests');
      const data = await res.json();
      tradeRequests.set(data);
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  export function refresh() {
    if (user?.id) loadTradeRequests();
  }

  function getPartnerName(req) {
    if (!user) return 'Unknown';
    return String(req.requester_id) === String(user.id)
      ? (req.target_name || 'Unknown')
      : (req.requester_name || 'Unknown');
  }

  function formatAge(dateStr) {
    if (!dateStr) return 'N/A';
    const ts = new Date(dateStr);
    const diff = Math.max(0, Date.now() - ts.getTime());
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    const days = Math.floor(hrs / 24);
    return `${days}d`;
  }

  const columns = [
    {
      key: '_partner', header: 'Partner', main: true, sortable: true, searchable: false,
      formatter: (v, row) => getPartnerName(row)
    },
    {
      key: 'item_count', header: 'Items', width: '50px', sortable: true, searchable: false,
      formatter: (v) => v || 0
    },
    {
      key: 'status', header: 'Status', width: '80px', sortable: true, searchable: false,
      formatter: (v) => {
        const statusMap = {
          pending: 'badge-warning',
          active: 'badge-success',
          completed: 'badge-info',
          cancelled: 'badge-error',
          expired: 'badge-error'
        };
        const cls = statusMap[v] || '';
        return `<span class="badge badge-subtle ${cls}">${v || 'unknown'}</span>`;
      }
    },
    {
      key: 'created_at', header: 'Created', width: '70px', sortable: true, searchable: false,
      formatter: (v) => formatAge(v)
    },
    {
      key: '_actions', header: '', width: '90px', sortable: false, searchable: false,
      formatter: (v, row) => {
        const btns = [];
        if (row?.discord_thread_id) {
          btns.push(`<button class="cell-button trade-action-btn" data-trade-view="${row.id}">View</button>`);
        }
        if ((row?.status === 'pending' || row?.status === 'active') && user) {
          btns.push(`<button class="cell-button trade-action-btn cancel-btn" data-trade-cancel="${row.id}">Cancel</button>`);
        }
        return btns.join(' ');
      }
    }
  ];

  async function handleCancel(requestId) {
    try {
      const res = await fetch(`/api/market/trade-requests/${requestId}/cancel`, { method: 'POST' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || 'Failed to cancel');
      }
      loadTradeRequests();
    } catch (err) {
      console.error('Cancel error:', err);
    }
  }

  function handleClick(e) {
    const cancelBtn = e.target.closest('[data-trade-cancel]');
    if (cancelBtn) {
      e.stopPropagation();
      e.preventDefault();
      const id = parseInt(cancelBtn.dataset.tradeCancel, 10);
      if (id) handleCancel(id);
      return;
    }

    const viewBtn = e.target.closest('[data-trade-view]');
    if (viewBtn) {
      e.stopPropagation();
      e.preventDefault();
      // Thread view — could open Discord link in future
      const id = parseInt(viewBtn.dataset.tradeView, 10);
      const req = $tradeRequests.find(r => r.id === id);
      if (req?.discord_thread_id) {
        // Discord thread links aren't accessible from web, so just show info
        console.log('Trade request thread:', req.discord_thread_id);
      }
    }
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="trade-requests-panel" on:click|capture={handleClick}>
  {#if loading}
    <div class="panel-loading">Loading trade requests...</div>
  {:else if error}
    <div class="panel-error">{error}</div>
  {:else if $tradeRequests.length === 0}
    <div class="panel-empty">No trade requests yet. Use Buy/Sell buttons on the order book to create one.</div>
  {:else}
    <FancyTable
      {columns}
      data={$tradeRequests}
      rowHeight={30}
      compact={true}
      sortable={true}
      searchable={false}
      emptyMessage="No trade requests"
    />
  {/if}
</div>

<style>
  .trade-requests-panel {
    flex: 1;
    min-height: 0;
    overflow: hidden;
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
  .trade-requests-panel :global(.trade-action-btn) {
    font-size: 10px;
    padding: 2px 8px;
    color: var(--accent-color);
    border-color: var(--accent-color);
  }
  .trade-requests-panel :global(.trade-action-btn:hover) {
    background: rgba(59, 130, 246, 0.15);
  }
  .trade-requests-panel :global(.cancel-btn) {
    color: var(--error-color, #ef4444);
    border-color: var(--error-color, #ef4444);
  }
  .trade-requests-panel :global(.cancel-btn:hover) {
    background: rgba(239, 68, 68, 0.15);
  }
</style>
