<!--
  @component My Auctions Page
  Shows user's auctions (as seller) and bids (as bidder) in two tabs.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import AuctionStatusBadge from '$lib/components/auction/AuctionStatusBadge.svelte';
  import AuctionCountdown from '$lib/components/auction/AuctionCountdown.svelte';

  export let data;

  $: myAuctions = data.auctions || [];
  $: myBids = data.bids || [];

  let activeTab = 'auctions';
</script>

<svelte:head>
  <title>My Auctions - Market - Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/market">Market</a>
      <span>/</span>
      <a href="/market/auction">Auctions</a>
      <span>/</span>
      <span>My Auctions</span>
    </div>

    <div class="page-header">
      <h1>My Auctions</h1>
      <a href="/market/auction/create" class="btn-primary">Create Auction</a>
    </div>

    <div class="tabs">
      <button
        class="tab" class:active={activeTab === 'auctions'}
        on:click={() => activeTab = 'auctions'}
      >
        My Auctions ({myAuctions.length})
      </button>
      <button
        class="tab" class:active={activeTab === 'bids'}
        on:click={() => activeTab = 'bids'}
      >
        My Bids ({myBids.length})
      </button>
    </div>

    {#if activeTab === 'auctions'}
      {#if myAuctions.length === 0}
        <div class="empty-state">
          <p>You haven't created any auctions yet</p>
          <a href="/market/auction/create" class="btn-primary">Create Your First Auction</a>
        </div>
      {:else}
        <div class="list">
          {#each myAuctions as auction (auction.id)}
            <a href="/market/auction/{auction.id}" class="list-item">
              <div class="list-info">
                <span class="list-title">{auction.title}</span>
                <div class="list-meta">
                  <AuctionStatusBadge status={auction.status} size="small" />
                  {#if auction.status === 'active' || auction.status === 'frozen'}
                    <AuctionCountdown endsAt={auction.ends_at} frozen={auction.status === 'frozen'} size="compact" />
                  {/if}
                </div>
              </div>
              <div class="list-pricing">
                {#if auction.current_bid}
                  <span class="list-amount">{parseFloat(auction.current_bid).toFixed(2)} PED</span>
                  <span class="list-detail">{auction.bid_count} bid{auction.bid_count !== 1 ? 's' : ''}</span>
                {:else}
                  <span class="list-amount">{parseFloat(auction.starting_bid).toFixed(2)} PED</span>
                  <span class="list-detail">Starting bid</span>
                {/if}
              </div>
            </a>
          {/each}
        </div>
      {/if}
    {:else}
      {#if myBids.length === 0}
        <div class="empty-state">
          <p>You haven't bid on any auctions yet</p>
          <a href="/market/auction" class="btn-secondary">Browse Auctions</a>
        </div>
      {:else}
        <div class="list">
          {#each myBids as bid (bid.id)}
            <a href="/market/auction/{bid.id}" class="list-item">
              <div class="list-info">
                <span class="list-title">{bid.title}</span>
                <div class="list-meta">
                  <AuctionStatusBadge status={bid.status} size="small" />
                  <span class="bid-status {bid.my_bid_status}">
                    {bid.my_bid_status === 'active' ? 'Leading' :
                     bid.my_bid_status === 'won' ? 'Won' :
                     bid.my_bid_status === 'outbid' ? 'Outbid' :
                     bid.my_bid_status === 'rolled_back' ? 'Rolled back' : bid.my_bid_status}
                  </span>
                  <span class="seller-name">by {bid.seller_name || 'Unknown'}</span>
                </div>
              </div>
              <div class="list-pricing">
                <span class="list-amount">{parseFloat(bid.my_bid).toFixed(2)} PED</span>
                <span class="list-detail">Your bid</span>
                {#if bid.current_bid}
                  <span class="list-detail">Current: {parseFloat(bid.current_bid).toFixed(2)} PED</span>
                {/if}
              </div>
            </a>
          {/each}
        </div>
      {/if}
    {/if}
  </div>
</div>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    max-width: 900px;
    margin: 0 auto;
    padding: 1rem;
    padding-bottom: 2rem;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
  }

  .breadcrumb a { color: var(--accent-color); text-decoration: none; }
  .breadcrumb a:hover { text-decoration: underline; }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-color);
  }

  .tabs {
    display: flex;
    gap: 0;
    margin-bottom: 1.5rem;
    border-bottom: 2px solid var(--border-color);
  }

  .tab {
    padding: 0.75rem 1.25rem;
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-muted);
    background: none;
    border: none;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition: all 0.15s;
  }

  .tab:hover { color: var(--text-color); }

  .tab.active {
    color: var(--accent-color);
    border-bottom-color: var(--accent-color);
  }

  .list {
    display: flex;
    flex-direction: column;
    gap: 0;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }

  .list-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    padding: 0.875rem 1rem;
    border-bottom: 1px solid var(--border-color);
    text-decoration: none;
    color: inherit;
    transition: background 0.1s;
  }

  .list-item:last-child { border-bottom: none; }
  .list-item:hover { background: var(--hover-color); }

  .list-info { flex: 1; min-width: 0; }

  .list-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--text-color);
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .list-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.25rem;
    flex-wrap: wrap;
  }

  .seller-name {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .bid-status {
    font-size: 0.75rem;
    font-weight: 500;
    padding: 1px 6px;
    border-radius: 4px;
  }

  .bid-status.active {
    color: var(--success-color);
    background: var(--success-bg);
  }

  .bid-status.won {
    color: var(--accent-color);
    background: var(--hover-color);
  }

  .bid-status.outbid {
    color: var(--warning-color);
    background: var(--warning-bg);
  }

  .bid-status.rolled_back {
    color: var(--error-color);
    background: var(--error-bg);
  }

  .list-pricing {
    text-align: right;
    flex-shrink: 0;
  }

  .list-amount {
    font-weight: 700;
    font-size: 0.95rem;
    color: var(--accent-color);
    display: block;
  }

  .list-detail {
    font-size: 0.75rem;
    color: var(--text-muted);
    display: block;
  }

  .empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--text-muted);
  }

  .empty-state p {
    margin-bottom: 1rem;
  }

  .btn-primary, .btn-secondary {
    padding: 0.5rem 1rem;
    font-size: 0.85rem;
    font-weight: 500;
    border-radius: 6px;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.15s;
    display: inline-flex;
    align-items: center;
  }

  .btn-primary { background: var(--accent-color); border: 1px solid var(--accent-color); color: white; }
  .btn-primary:hover { background: var(--accent-color-hover); }

  .btn-secondary { background: transparent; border: 1px solid var(--border-color); color: var(--text-color); }
  .btn-secondary:hover { background: var(--hover-color); }

  @media (max-width: 899px) {
    .page-container { padding: 1rem; }
    .list-item { flex-direction: column; align-items: flex-start; }
    .list-pricing { text-align: left; }
  }
</style>
