<!--
  @component RentalOfferCard
  Card for the rental listing page showing offer summary.
-->
<script>
  // @ts-nocheck
  import RentalStatusBadge from './RentalStatusBadge.svelte';
  import { formatPrice } from '$lib/utils/rentalPricing.js';
  import { stripHtml } from '$lib/sanitize.js';

  

  

  
  /**
   * @typedef {Object} Props
   * @property {object} offer
   * @property {boolean} [showStatus]
   * @property {object|null} Planets lookup map { id: name } [planets]
   */

  /** @type {Props} */
  let { offer, showStatus = false, planets = null } = $props();


  function getBestDiscount(discounts) {
    if (!Array.isArray(discounts) || discounts.length === 0) return null;
    let best = null;
    for (const d of discounts) {
      if (d.percent > 0 && d.minDays > 0) {
        if (!best || d.percent > best.percent) best = d;
      }
    }
    return best;
  }
  let itemCount = $derived(offer.item_count ?? 0);
  let planetName = $derived(planets && offer.planet_id ? planets[offer.planet_id] : null);
  let bestDiscount = $derived(getBestDiscount(offer.discounts));
</script>

<a href="/market/rental/{offer.id}" class="rental-offer-card">
  <div class="card-header">
    <h4 class="card-title">{offer.title}</h4>
    <div class="card-badges">
      {#if showStatus}
        <RentalStatusBadge status={offer.status} type="offer" size="small" />
      {/if}
      {#if itemCount > 0}
        <span class="item-count-badge">{itemCount} item{itemCount !== 1 ? 's' : ''}</span>
      {/if}
    </div>
  </div>

  {#if offer.description}
    <p class="card-description">{stripHtml(offer.description)}</p>
  {/if}

  <div class="card-details">
    {#if planetName}
      <div class="detail">
        <span class="detail-label">Planet:</span>
        <span class="detail-value">{planetName}</span>
      </div>
    {/if}
    {#if offer.location}
      <div class="detail">
        <span class="detail-label">Location:</span>
        <span class="detail-value">{offer.location}</span>
      </div>
    {/if}
    {#if offer.owner_name}
      <div class="detail">
        <span class="detail-label">Owner:</span>
        <span class="detail-value">{offer.owner_name}</span>
      </div>
    {/if}
  </div>

  <div class="card-footer">
    <div class="price">
      <span class="price-value">{parseFloat(offer.price_per_day).toFixed(2)}</span>
      <span class="price-unit">PED/day</span>
    </div>

    <div class="footer-badges">
      {#if bestDiscount}
        <span class="discount-badge">-{bestDiscount.percent}% @ {bestDiscount.minDays}+ days</span>
      {/if}
      {#if Number(offer.deposit) > 0}
        <span class="deposit-badge">Deposit: {formatPrice(offer.deposit)}</span>
      {/if}
    </div>
  </div>
</a>

<style>
  .rental-offer-card {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    text-decoration: none;
    color: var(--text-color);
    transition: border-color 0.2s ease, background-color 0.2s ease;
  }

  .rental-offer-card:hover {
    border-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .card-title {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .card-badges {
    display: flex;
    gap: 0.4rem;
    flex-shrink: 0;
    align-items: center;
  }

  .item-count-badge {
    background: var(--accent-color);
    color: white;
    padding: 0.125rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    white-space: nowrap;
  }

  .card-description {
    margin: 0;
    font-size: 0.9rem;
    color: var(--text-muted);
    display: -webkit-box;
    line-clamp: 2;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .card-details {
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
    color: var(--text-muted);
  }

  .detail-value {
    font-weight: 500;
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 0.25rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--border-color);
  }

  .price {
    display: flex;
    align-items: baseline;
    gap: 0.25rem;
  }

  .price-value {
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--accent-color);
  }

  .price-unit {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .footer-badges {
    display: flex;
    gap: 0.4rem;
    align-items: center;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .discount-badge {
    background: var(--success-bg);
    color: var(--success-color);
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
    white-space: nowrap;
  }

  .deposit-badge {
    background: var(--warning-bg);
    color: var(--warning-color);
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
    white-space: nowrap;
  }

  @media (max-width: 600px) {
    .card-footer {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }

    .footer-badges {
      justify-content: flex-start;
    }
  }
</style>
