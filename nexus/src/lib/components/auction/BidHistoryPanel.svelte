<!--
  @component BidHistoryPanel
  Scrollable list of bids for an auction.
  Highlights the current winning bid and shows rolled-back bids.
-->
<script>
  /** @type {Array} Bid history from API */
  export let bids = [];

  /** @type {boolean} Whether current user is admin (shows rollback points) */
  export let isAdmin = false;

  import { createEventDispatcher } from 'svelte';
  const dispatch = createEventDispatcher();

  function formatTimeAgo(dateStr) {
    const diff = Date.now() - new Date(dateStr).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  function getStatusClass(status) {
    switch (status) {
      case 'active': return 'winning';
      case 'won': return 'won';
      case 'rolled_back': return 'rolled-back';
      default: return '';
    }
  }
</script>

<div class="bid-history">
  <h3 class="section-title">Bid History</h3>
  {#if bids.length === 0}
    <div class="empty">No bids yet</div>
  {:else}
    <div class="bid-list">
      {#each bids as bid}
        <div class="bid-item {getStatusClass(bid.status)}">
          <div class="bid-info">
            <span class="bidder-name">{bid.bidder_name || 'Anonymous'}</span>
            {#if bid.status === 'rolled_back'}
              <span class="bid-status-tag">Rolled back</span>
            {:else if bid.status === 'won'}
              <span class="bid-status-tag won">Winner</span>
            {:else if bid.status === 'active'}
              <span class="bid-status-tag active">Leading</span>
            {/if}
          </div>
          <div class="bid-details">
            <span class="bid-amount">{parseFloat(bid.amount).toFixed(2)} PED</span>
            <span class="bid-time">{formatTimeAgo(bid.created_at)}</span>
          </div>
          {#if isAdmin && bid.status !== 'rolled_back'}
            <button
              class="rollback-btn"
              title="Rollback to this bid"
              on:click={() => dispatch('rollback', { bidId: bid.id, amount: bid.amount })}
            >
              Rollback here
            </button>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .bid-history {
    background: var(--hover-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }

  .section-title {
    margin: 0;
    padding: 0.75rem 1rem;
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-color);
    border-bottom: 1px solid var(--border-color);
  }

  .empty {
    padding: 1.5rem;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  .bid-list {
    max-height: 300px;
    overflow-y: auto;
  }

  .bid-item {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    padding: 0.6rem 1rem;
    border-bottom: 1px solid var(--border-color);
  }

  .bid-item:last-child {
    border-bottom: none;
  }

  .bid-item.winning {
    background: var(--success-bg);
  }

  .bid-item.won {
    background: var(--accent-color-bg);
  }

  .bid-item.rolled-back {
    opacity: 0.5;
    text-decoration: line-through;
  }

  .bid-info {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }

  .bidder-name {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-color);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .bid-status-tag {
    font-size: 0.7rem;
    padding: 1px 6px;
    border-radius: 4px;
    background: var(--hover-color);
    color: var(--text-muted);
    white-space: nowrap;
  }

  .bid-status-tag.active {
    background: var(--success-bg);
    color: var(--success-color);
  }

  .bid-status-tag.won {
    background: var(--accent-color-bg);
    color: var(--accent-color);
  }

  .bid-details {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .bid-amount {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-color);
    font-variant-numeric: tabular-nums;
  }

  .bid-time {
    font-size: 0.75rem;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .rollback-btn {
    font-size: 0.7rem;
    padding: 2px 8px;
    border: 1px solid var(--error-color);
    background: var(--error-bg);
    color: var(--error-color);
    border-radius: 4px;
    cursor: pointer;
    white-space: nowrap;
  }

  .rollback-btn:hover {
    background: var(--error-color);
    color: white;
  }
</style>
