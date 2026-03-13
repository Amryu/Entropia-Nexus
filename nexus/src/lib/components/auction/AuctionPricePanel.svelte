<!--
  @component AuctionPricePanel
  Displays auction pricing info: current bid, starting bid, buyout, min next bid, fee estimate.
-->
<script>
  import { getMinNextBid, calculateAuctionFee, isBuyoutOnly } from '$lib/common/auctionUtils.js';
  import AuctionCountdown from './AuctionCountdown.svelte';

  
  /**
   * @typedef {Object} Props
   * @property {object} auction
   */

  /** @type {Props} */
  let { auction } = $props();

  let hasBids = $derived(auction.bid_count > 0);
  let currentAmount = $derived(hasBids ? parseFloat(auction.current_bid) : parseFloat(auction.starting_bid));
  let minNext = $derived(hasBids ? getMinNextBid(parseFloat(auction.current_bid), true) : parseFloat(auction.starting_bid));
  let fee = $derived(calculateAuctionFee(currentAmount));
  let buyoutOnly = $derived(isBuyoutOnly(auction));
  let isActive = $derived(auction.status === 'active');
  let isFrozen = $derived(auction.status === 'frozen');
</script>

<div class="price-panel">
  {#if buyoutOnly}
    <div class="price-row main">
      <span class="price-label">Buy Now</span>
      <span class="price-amount">{parseFloat(auction.buyout_price).toFixed(2)} PED</span>
    </div>
  {:else}
    {#if hasBids}
      <div class="price-row main">
        <span class="price-label">Current Bid</span>
        <span class="price-amount">{parseFloat(auction.current_bid).toFixed(2)} PED</span>
      </div>
    {:else}
      <div class="price-row main">
        <span class="price-label">Starting Bid</span>
        <span class="price-amount">{parseFloat(auction.starting_bid).toFixed(2)} PED</span>
      </div>
    {/if}

    {#if isActive && !buyoutOnly}
      <div class="price-row">
        <span class="price-label">Min. Next Bid</span>
        <span class="price-value">{minNext.toFixed(2)} PED</span>
      </div>
    {/if}

    {#if auction.buyout_price}
      <div class="price-row">
        <span class="price-label">Buy Now</span>
        <span class="price-value">{parseFloat(auction.buyout_price).toFixed(2)} PED</span>
      </div>
    {/if}
  {/if}

  <div class="price-row">
    <span class="price-label">Bids</span>
    <span class="price-value">{auction.bid_count}</span>
  </div>

  {#if isActive || isFrozen}
    <div class="price-row">
      <span class="price-label">Time Left</span>
      <AuctionCountdown endsAt={auction.ends_at} frozen={isFrozen} />
    </div>
  {/if}

  <!-- Fee temporarily hidden
  {#if fee > 0}
    <div class="price-row muted">
      <span class="price-label">Est. Fee</span>
      <span class="price-value muted">{fee.toFixed(2)} PED</span>
    </div>
  {/if}
  -->
</div>

<style>
  .price-panel {
    padding: 1rem;
    background: var(--hover-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .price-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  .price-row.main {
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 0.25rem;
  }

  .price-label {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .price-amount {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--accent-color);
  }

  .price-value {
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-color);
  }

  .price-value.muted,
  .price-row.muted .price-label {
    color: var(--text-muted);
    font-size: 0.8rem;
  }
</style>
