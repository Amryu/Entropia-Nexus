<!--
  @component BidSection
  Bid input with Turnstile widget for placing bids on an auction.
  Handles bid placement, buyout, and disclaimer checks.
-->
<script>
  import { createEventDispatcher } from 'svelte';
  import { addToast } from '$lib/stores/toasts.js';
  import { getMinNextBid, isBuyoutOnly } from '$lib/common/auctionUtils.js';
  import TurnstileWidget from '../TurnstileWidget.svelte';

  const dispatch = createEventDispatcher();

  /** @type {object} Auction data */
  export let auction;

  /** @type {string} Turnstile site key */
  export let turnstileSiteKey = '';

  /** @type {boolean} Whether user has accepted bidder disclaimer */
  export let disclaimerAccepted = false;

  /** @type {boolean} Whether user is the seller */
  export let isSeller = false;

  let bidAmount = '';
  let turnstileToken = null;
  let resetTurnstile = false;
  let submitting = false;

  $: hasBids = auction.bid_count > 0;
  $: minBid = hasBids ? getMinNextBid(parseFloat(auction.current_bid), true) : parseFloat(auction.starting_bid);
  $: buyoutOnly = isBuyoutOnly(auction);
  $: isActive = auction.status === 'active';
  $: hasBuyout = auction.buyout_price != null;

  function handleTurnstileVerified(e) {
    turnstileToken = e.detail.token;
  }

  async function handleBid() {
    if (!turnstileToken) {
      addToast('Please complete the captcha verification', { type: 'warning' });
      return;
    }
    if (!disclaimerAccepted) {
      dispatch('needDisclaimer');
      return;
    }

    const amount = parseFloat(bidAmount);
    if (!Number.isFinite(amount) || amount < minBid) {
      addToast(`Minimum bid is ${minBid.toFixed(2)} PED`, { type: 'warning' });
      return;
    }

    submitting = true;
    try {
      const res = await fetch(`/api/auction/${auction.id}/bid`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount, turnstile_token: turnstileToken })
      });
      const data = await res.json();

      if (!res.ok) {
        addToast(data.error || 'Failed to place bid', { type: 'error' });
        resetTurnstile = true;
        return;
      }

      addToast(`Bid placed: ${amount.toFixed(2)} PED`, { type: 'success' });
      bidAmount = '';
      resetTurnstile = true;
      dispatch('bid', data);
    } catch (err) {
      addToast('Failed to place bid', { type: 'error' });
      resetTurnstile = true;
    } finally {
      submitting = false;
    }
  }

  async function handleBuyout() {
    if (!turnstileToken) {
      addToast('Please complete the captcha verification', { type: 'warning' });
      return;
    }
    if (!disclaimerAccepted) {
      dispatch('needDisclaimer');
      return;
    }

    submitting = true;
    try {
      const res = await fetch(`/api/auction/${auction.id}/buyout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ turnstile_token: turnstileToken })
      });
      const data = await res.json();

      if (!res.ok) {
        addToast(data.error || 'Failed to buy out', { type: 'error' });
        resetTurnstile = true;
        return;
      }

      addToast('Buyout successful!', { type: 'success' });
      resetTurnstile = true;
      dispatch('buyout', data);
    } catch (err) {
      addToast('Failed to buy out', { type: 'error' });
      resetTurnstile = true;
    } finally {
      submitting = false;
    }
  }
</script>

{#if !isActive}
  <div class="bid-section inactive">
    <span class="inactive-text">Bidding is not available</span>
  </div>
{:else if isSeller}
  <div class="bid-section inactive">
    <span class="inactive-text">This is your auction</span>
  </div>
{:else}
  <div class="bid-section">
    {#if !buyoutOnly}
      <div class="bid-input-row">
        <div class="bid-input-group">
          <input
            type="number"
            bind:value={bidAmount}
            placeholder={minBid.toFixed(2)}
            min={minBid}
            step="0.01"
            class="bid-input"
            disabled={submitting}
          />
          <span class="bid-currency">PED</span>
        </div>
        <button
          class="btn btn-primary"
          on:click={handleBid}
          disabled={submitting || !turnstileToken}
        >
          {submitting ? 'Placing...' : 'Place Bid'}
        </button>
      </div>
      <div class="bid-hint">Minimum: {minBid.toFixed(2)} PED</div>
    {/if}

    {#if hasBuyout}
      <button
        class="btn btn-buyout"
        on:click={handleBuyout}
        disabled={submitting || !turnstileToken}
      >
        {submitting ? 'Processing...' : `Buy Now — ${parseFloat(auction.buyout_price).toFixed(2)} PED`}
      </button>
    {/if}

    <div class="turnstile-wrapper">
      <TurnstileWidget
        siteKey={turnstileSiteKey}
        bind:token={turnstileToken}
        bind:reset={resetTurnstile}
        on:verified={handleTurnstileVerified}
      />
    </div>
  </div>
{/if}

<style>
  .bid-section {
    padding: 1rem;
    background: var(--hover-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .bid-section.inactive {
    align-items: center;
    justify-content: center;
    min-height: 80px;
  }

  .inactive-text {
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  .bid-input-row {
    display: flex;
    gap: 8px;
    align-items: stretch;
  }

  .bid-input-group {
    flex: 1;
    display: flex;
    align-items: center;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
  }

  .bid-input {
    flex: 1;
    padding: 0.5rem 0.75rem;
    border: none;
    background: transparent;
    color: var(--text-color);
    font-size: 1rem;
    outline: none;
    -moz-appearance: textfield;
  }

  .bid-input::-webkit-outer-spin-button,
  .bid-input::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }

  .bid-currency {
    padding: 0 0.75rem;
    font-size: 0.85rem;
    color: var(--text-muted);
    font-weight: 500;
  }

  .bid-hint {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .btn {
    padding: 0.5rem 1rem;
    font-size: 0.9rem;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
    border: none;
  }

  .btn:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }

  .btn-primary {
    background: var(--accent-color);
    color: white;
    white-space: nowrap;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--accent-color-hover);
  }

  .btn-buyout {
    width: 100%;
    padding: 0.6rem 1rem;
    background: var(--success-bg);
    color: var(--success-color);
    border: 1px solid var(--success-color);
    font-weight: 600;
  }

  .btn-buyout:hover:not(:disabled) {
    background: var(--success-color);
    color: white;
  }

  .turnstile-wrapper {
    display: flex;
    justify-content: center;
  }
</style>
