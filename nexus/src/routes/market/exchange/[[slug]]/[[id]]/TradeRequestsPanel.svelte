<script>
  //@ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { tradeRequests } from '../../exchangeStore.js';

  const DISCORD_GUILD_ID = import.meta.env.VITE_DISCORD_GUILD_ID;

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

  function getDiscordThreadUrl(threadId) {
    if (!threadId || !DISCORD_GUILD_ID) return null;
    return `https://discord.com/channels/${DISCORD_GUILD_ID}/${threadId}`;
  }

  const columns = [
    {
      key: 'partner_name', header: 'Partner', main: true, sortable: true, searchable: false,
      formatter: (v) => v || 'Unknown'
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
      key: '_actions', header: '', width: '120px', sortable: false, searchable: false,
      cellClass: () => 'cell-center',
      formatter: (v, row) => {
        const btns = [];
        const threadUrl = getDiscordThreadUrl(row?.discord_thread_id);
        if (threadUrl) {
          btns.push(`<a href="${threadUrl}" target="_blank" rel="noopener noreferrer" class="cell-button trade-action-btn discord-link">Discord</a>`);
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
    }
  }
</script>

{#if error}
  <div class="panel-error">{error}</div>
{:else}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="trade-requests-panel" on:click|capture={handleClick}>
    <FancyTable
      {columns}
      data={$tradeRequests}
      rowHeight={30}
      compact={true}
      sortable={true}
      searchable={false}
      emptyMessage="No trade requests yet. Use Buy/Sell buttons on the order book to create one."
    />
  </div>
{/if}

<style>
  .trade-requests-panel {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    margin-top: 8px;
  }
  .panel-error {
    padding: 24px;
    text-align: center;
    font-size: 13px;
    color: var(--error-color, #ef4444);
  }
  .trade-requests-panel :global(.cell-center) {
    justify-content: center;
  }
  .trade-requests-panel :global(.trade-action-btn) {
    font-size: 11px;
    padding: 2px 6px;
    color: var(--accent-color);
    border-color: var(--accent-color);
    text-decoration: none;
  }
  .trade-requests-panel :global(.trade-action-btn:hover) {
    background: rgba(59, 130, 246, 0.15);
  }
  .trade-requests-panel :global(.discord-link) {
    display: inline-flex;
    align-items: center;
  }
  .trade-requests-panel :global(.cancel-btn) {
    color: var(--error-color, #ef4444);
    border-color: var(--error-color, #ef4444);
  }
  .trade-requests-panel :global(.cancel-btn:hover) {
    background: rgba(239, 68, 68, 0.15);
  }
</style>
