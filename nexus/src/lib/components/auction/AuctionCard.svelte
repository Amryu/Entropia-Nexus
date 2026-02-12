<!--
  @component AuctionCard
  Card component for auction listings.
  Shows title, item images, current bid, time left, status badge.
-->
<script>
  import AuctionStatusBadge from './AuctionStatusBadge.svelte';
  import AuctionCountdown from './AuctionCountdown.svelte';
  import { isBuyoutOnly } from '$lib/common/auctionUtils.js';
  import { globalIdToEntityId } from '$lib/common/itemTypes.js';

  /** @type {object} Auction data */
  export let auction;

  $: buyoutOnly = isBuyoutOnly(auction);
  $: hasBids = auction.bid_count > 0;
  $: isActive = auction.status === 'active';
  $: isFrozen = auction.status === 'frozen';
  $: items = auction.item_set_data?.items || [];
  $: firstItem = items[0] || null;
  $: firstItemEntityId = (firstItem?.itemId && firstItem?.type)
    ? globalIdToEntityId(firstItem.itemId, firstItem.type)
    : null;
  $: imageUrl = (firstItemEntityId != null && firstItem?.type)
    ? `/api/img/${firstItem.type.toLowerCase()}/${firstItemEntityId}`
    : null;
</script>

<a href="/market/auction/{auction.id}" class="auction-card">
  <div class="card-image">
    {#if imageUrl}
      <img src={imageUrl} alt="" loading="lazy" />
    {:else}
      <div class="no-image">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
      </div>
    {/if}
    {#if items.length > 1}
      <span class="item-count">+{items.length - 1}</span>
    {/if}
  </div>

  <div class="card-body">
    <div class="card-header">
      <h3 class="card-title">{auction.title}</h3>
      <AuctionStatusBadge status={auction.status} size="small" />
    </div>

    <div class="card-meta">
      <span class="seller">{auction.seller_name || 'Unknown'}</span>
      {#if auction.item_set_customized}
        <span class="customized-tag">C</span>
      {/if}
    </div>

    <div class="card-pricing">
      {#if buyoutOnly}
        <div class="price-main">
          <span class="price-label">Buy Now</span>
          <span class="price-value">{parseFloat(auction.buyout_price).toFixed(2)} PED</span>
        </div>
      {:else}
        <div class="price-main">
          <span class="price-label">{hasBids ? 'Current Bid' : 'Starting At'}</span>
          <span class="price-value">
            {parseFloat(hasBids ? auction.current_bid : auction.starting_bid).toFixed(2)} PED
          </span>
        </div>
        {#if auction.buyout_price}
          <div class="price-secondary">
            Buyout: {parseFloat(auction.buyout_price).toFixed(2)} PED
          </div>
        {/if}
      {/if}
    </div>

    <div class="card-footer">
      {#if isActive || isFrozen}
        <AuctionCountdown endsAt={auction.ends_at} frozen={isFrozen} size="compact" />
      {/if}
      <span class="bid-count">{auction.bid_count} bid{auction.bid_count !== 1 ? 's' : ''}</span>
    </div>
  </div>
</a>

<style>
  .auction-card {
    display: flex;
    flex-direction: column;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    text-decoration: none;
    color: inherit;
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .auction-card:hover {
    border-color: var(--accent-color);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }

  .card-image {
    position: relative;
    width: 100%;
    aspect-ratio: 1;
    background: var(--hover-color);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }

  .card-image img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .no-image {
    color: var(--text-muted);
  }

  .item-count {
    position: absolute;
    bottom: 6px;
    right: 6px;
    background: rgba(0, 0, 0, 0.7);
    color: white;
    font-size: 0.75rem;
    padding: 2px 6px;
    border-radius: 4px;
  }

  .card-body {
    padding: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    flex: 1;
  }

  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 6px;
  }

  .card-title {
    margin: 0;
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-color);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
  }

  .card-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .customized-tag {
    background: var(--warning-bg);
    color: var(--warning-color);
    font-size: 0.7rem;
    font-weight: 600;
    padding: 1px 4px;
    border-radius: 3px;
  }

  .card-pricing {
    margin-top: 0.25rem;
  }

  .price-main {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .price-label {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .price-value {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--accent-color);
    font-variant-numeric: tabular-nums;
  }

  .price-secondary {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-align: right;
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: auto;
    padding-top: 0.4rem;
    border-top: 1px solid var(--border-color);
  }

  .bid-count {
    font-size: 0.75rem;
    color: var(--text-muted);
  }
</style>
