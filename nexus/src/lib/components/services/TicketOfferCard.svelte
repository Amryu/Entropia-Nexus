<script>
  // @ts-nocheck
  import { stripHtml } from '$lib/sanitize.js';

  /**
   * @typedef {Object} Props
   * @property {any} offer
   * @property {boolean} [isOwner]
   * @property {boolean} [purchasing]
   * @property {boolean} [showAsSingleOption] - If true, shows "Request Flight" button
   * @property {(data: any) => void} [onpurchase]
   * @property {(data: any) => void} [onrequestFlight]
   * @property {(data: any) => void} [onedit]
   */

  /** @type {Props} */
  let {
    offer,
    isOwner = false,
    purchasing = false,
    showAsSingleOption = false,
    onpurchase,
    onrequestFlight,
    onedit
  } = $props();

  function getOfferTypeLabel() {
    if (offer.uses_count) {
      return offer.uses_count === 1 ? 'Single Use' : `${offer.uses_count} Uses`;
    }
    if (offer.validity_days) {
      return offer.validity_days === 1 ? '1 Day Pass' : `${offer.validity_days} Day Pass`;
    }
    return 'Unknown';
  }

  function handlePurchase() {
    onpurchase?.(offer);
  }

  function handleRequestFlight() {
    onrequestFlight?.(offer);
  }
</script>

<div class="ticket-offer-card">
  <div class="offer-header">
    <h4 class="offer-name">{offer.name}</h4>
    <span class="offer-type">{getOfferTypeLabel()}</span>
  </div>

  {#if offer.description}
    <p class="offer-description">{stripHtml(offer.description)}</p>
  {/if}

  <div class="offer-details">
    {#if offer.uses_count}
      <div class="detail">
        <span class="detail-label">Uses:</span>
        <span class="detail-value">{offer.uses_count}</span>
      </div>
    {/if}
    {#if offer.validity_days}
      <div class="detail">
        <span class="detail-label">Valid for:</span>
        <span class="detail-value">{offer.validity_days} days</span>
      </div>
    {/if}
    {#if offer.waives_pickup_fee}
      <div class="detail waives-fee">
        <span>Waives pickup fee</span>
      </div>
    {/if}
  </div>

  <div class="offer-footer">
    <div class="price">
      <span class="price-value">{parseFloat(offer.price).toFixed(2)}</span>
      <span class="price-currency">PED</span>
    </div>

    {#if showAsSingleOption && !isOwner}
      <button class="request-btn" onclick={handleRequestFlight}>
        Request Flight
      </button>
    {:else}
      <button class="buy-btn" onclick={handlePurchase} disabled={purchasing || isOwner}>
        {purchasing ? 'Purchasing...' : 'Buy Ticket'}
      </button>
    {/if}
  </div>
</div>

<style>
  .ticket-offer-card {
    background: var(--bg-color, #1a1a1a);
    border: 1px solid #555;
    border-radius: 8px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .offer-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .offer-name {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
  }

  .offer-type {
    background: #4a9eff33;
    color: #4a9eff;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 500;
    white-space: nowrap;
  }

  .offer-description {
    margin: 0;
    font-size: 0.9rem;
    color: var(--text-muted, #888);
  }

  .offer-details {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
    font-size: 0.9rem;
  }

  .detail {
    display: flex;
    gap: 0.3rem;
  }

  .detail-label {
    color: var(--text-muted, #888);
  }

  .detail-value {
    font-weight: 500;
  }

  .waives-fee {
    color: #10b981;
    font-weight: 500;
  }

  .offer-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 0.5rem;
    padding-top: 0.75rem;
    border-top: 1px solid #444;
  }

  .price {
    display: flex;
    align-items: baseline;
    gap: 0.25rem;
  }

  .price-value {
    font-size: 1.4rem;
    font-weight: 700;
    color: #4a9eff;
  }

  .price-currency {
    font-size: 0.9rem;
    color: var(--text-muted, #888);
  }

  .buy-btn, .request-btn {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    font-size: 0.95rem;
    cursor: pointer;
    font-weight: 500;
  }

  .buy-btn {
    background: #10b981;
    color: white;
  }

  .buy-btn:hover:not(:disabled) {
    background: #059669;
  }

  .buy-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .request-btn {
    background: #4a9eff;
    color: white;
  }

  .request-btn:hover {
    background: #3a8eef;
  }
</style>
