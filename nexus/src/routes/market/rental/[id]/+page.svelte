<!--
  @component Rental Detail Page
  Shows a rental offer with item set, pricing, calendar, and request button.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { goto } from '$app/navigation';
  import RentalStatusBadge from '$lib/components/rental/RentalStatusBadge.svelte';
  import RentalCalendar from '$lib/components/rental/RentalCalendar.svelte';
  import RentalRequestDialog from '$lib/components/rental/RentalRequestDialog.svelte';
  import ItemSetDisplay from '$lib/components/itemsets/ItemSetDisplay.svelte';
  import { generatePricingPreview, formatPrice } from '$lib/utils/rentalPricing.js';
  import { addToast } from '$lib/stores/toasts';

  export let data;

  $: offer = data.offer;
  $: availability = data.availability || { blockedDates: [], bookedDates: [] };
  $: user = data.session?.user;
  $: isOwner = user && offer && String(user.id) === String(offer.user_id);
  $: isVerified = !!user?.verified;
  $: canRequest = isVerified && !isOwner && offer?.status === 'available';

  $: pricingPreview = offer ? generatePricingPreview(Number(offer.price_per_day), offer.discounts || []) : [];

  // Build unavailable dates set for the request dialog
  $: unavailableDates = buildUnavailableDates(availability);

  let showRequestDialog = false;
  let selectedStart = null;
  let selectedEnd = null;

  function buildUnavailableDates(avail) {
    const set = new Set();
    for (const range of [...(avail.blockedDates || []), ...(avail.bookedDates || [])]) {
      const start = new Date(range.start + 'T00:00:00');
      const end = new Date(range.end + 'T00:00:00');
      for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        set.add(`${y}-${m}-${day}`);
      }
    }
    return set;
  }

  function handleCalendarSelect(e) {
    selectedStart = e.detail.start;
    selectedEnd = e.detail.end;
  }

  function handleRequestSubmit(e) {
    addToast('Rental request submitted successfully!', { type: 'success' });
    showRequestDialog = false;
    // Reload page to reflect updated availability
    goto(`/market/rental/${offer.id}`, { invalidateAll: true });
  }
</script>

<svelte:head>
  <title>{offer?.title || 'Rental Offer'} - Market - Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/market">Market</a>
      <span>/</span>
      <a href="/market/rental">Item Rentals</a>
      <span>/</span>
      <span>{offer?.title || 'Offer'}</span>
    </div>

    <button class="back-btn" on:click={() => goto('/market/rental')}>
      &larr; Back to Listings
    </button>

    {#if !offer}
      <div class="error-state">
        <h2>Offer not found</h2>
        <p>This rental offer may have been removed or doesn't exist.</p>
      </div>
    {:else}
      <div class="offer-detail">
        <div class="offer-header">
          <div class="header-info">
            <h1>{offer.title}</h1>
            <div class="header-meta">
              <RentalStatusBadge status={offer.status} type="offer" />
              {#if offer.owner_name}
                <span class="owner">by {offer.owner_name}</span>
              {/if}
            </div>
          </div>
          <div class="header-actions">
            {#if isOwner}
              <a href="/market/rental/{offer.id}/edit" class="btn-secondary">Edit Offer</a>
            {/if}
            {#if canRequest}
              <button class="btn-primary" on:click={() => showRequestDialog = true}>
                Request Rental
              </button>
            {/if}
          </div>
        </div>

        {#if offer.description}
          <div class="section">
            <p class="description">{offer.description}</p>
          </div>
        {/if}

        <div class="detail-grid">
          <!-- Left column: Item set + details -->
          <div class="detail-main">
            {#if offer.item_set}
              <div class="section">
                <h2>Items for Rent</h2>
                <ItemSetDisplay itemSet={offer.item_set} showHeader={false} />
              </div>
            {/if}

            <div class="section">
              <h2>Details</h2>
              <div class="details-list">
                {#if offer.planet_name}
                  <div class="detail-row">
                    <span class="detail-label">Planet:</span>
                    <span class="detail-value">{offer.planet_name}</span>
                  </div>
                {/if}
                {#if offer.location}
                  <div class="detail-row">
                    <span class="detail-label">Pickup/Return:</span>
                    <span class="detail-value">{offer.location}</span>
                  </div>
                {/if}
                <div class="detail-row">
                  <span class="detail-label">Deposit:</span>
                  <span class="detail-value">{formatPrice(offer.deposit)}</span>
                </div>
              </div>
            </div>

            <!-- Pricing table -->
            <div class="section">
              <h2>Pricing</h2>
              <div class="pricing-info">
                <div class="base-price">
                  <span class="price-value">{parseFloat(offer.price_per_day).toFixed(2)}</span>
                  <span class="price-unit">PED/day</span>
                </div>
              </div>

              {#if pricingPreview.length > 0}
                <div class="pricing-table">
                  <div class="pricing-header">
                    <span>Duration</span>
                    <span>Rate/Day</span>
                    <span>Discount</span>
                    <span>Total</span>
                  </div>
                  {#each pricingPreview as row}
                    <div class="pricing-row" class:has-discount={row.discountPct > 0}>
                      <span>{row.totalDays} day{row.totalDays !== 1 ? 's' : ''}</span>
                      <span>{formatPrice(row.pricePerDay)}</span>
                      <span class:discount-active={row.discountPct > 0}>
                        {row.discountPct > 0 ? `-${row.discountPct}%` : '—'}
                      </span>
                      <span class="row-total">{formatPrice(row.totalPrice)}</span>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          </div>

          <!-- Right column: Calendar -->
          <div class="detail-sidebar">
            <div class="section">
              <h2>Availability</h2>
              <RentalCalendar
                blockedDates={availability.blockedDates?.map(d => ({ start: d.start, end: d.end })) || []}
                bookedDates={availability.bookedDates?.map(d => ({ start: d.start, end: d.end })) || []}
                selectable={canRequest}
                bind:selectedStart
                bind:selectedEnd
                months={1}
                on:select={handleCalendarSelect}
              />
            </div>
          </div>
        </div>
      </div>
    {/if}

    {#if offer && canRequest}
      <RentalRequestDialog
        bind:show={showRequestDialog}
        {offer}
        {unavailableDates}
        on:submit={handleRequestSubmit}
      />
    {/if}
  </div>
</div>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1rem;
    padding-bottom: 2rem;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .back-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
    cursor: pointer;
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .back-btn:hover {
    background: var(--hover-color);
    border-color: var(--border-hover);
  }

  .error-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted);
  }

  .offer-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .offer-header h1 {
    margin: 0 0 0.4rem;
    font-size: 1.75rem;
  }

  .header-meta {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .owner {
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  .header-actions {
    display: flex;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .btn-primary, .btn-secondary {
    padding: 0.5rem 1rem;
    border-radius: 4px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    text-decoration: none;
    white-space: nowrap;
  }

  .btn-primary {
    background: var(--accent-color);
    color: white;
    border: none;
  }

  .btn-primary:hover {
    background: var(--accent-color-hover);
  }

  .btn-secondary {
    background: transparent;
    color: var(--text-color);
    border: 1px solid var(--border-color);
  }

  .btn-secondary:hover {
    background: var(--hover-color);
  }

  .description {
    color: var(--text-color);
    line-height: 1.6;
    margin: 0;
    white-space: pre-wrap;
  }

  .detail-grid {
    display: grid;
    grid-template-columns: 1fr 350px;
    gap: 1.5rem;
  }

  .section {
    margin-bottom: 1.5rem;
  }

  .section h2 {
    margin: 0 0 0.75rem;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .details-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .detail-row {
    display: flex;
    gap: 0.5rem;
    font-size: 0.95rem;
  }

  .detail-label {
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .detail-value {
    font-weight: 500;
  }

  .pricing-info {
    margin-bottom: 1rem;
  }

  .base-price {
    display: flex;
    align-items: baseline;
    gap: 0.3rem;
  }

  .base-price .price-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--accent-color);
  }

  .base-price .price-unit {
    font-size: 0.95rem;
    color: var(--text-muted);
  }

  .pricing-table {
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .pricing-header, .pricing-row {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr;
    padding: 0.5rem 0.75rem;
    font-size: 0.9rem;
  }

  .pricing-header {
    background: var(--hover-color);
    font-weight: 600;
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .pricing-row {
    border-top: 1px solid var(--border-color);
  }

  .pricing-row.has-discount {
    background: var(--success-bg);
  }

  .discount-active {
    color: var(--success-color);
    font-weight: 500;
  }

  .row-total {
    font-weight: 600;
  }

  @media (max-width: 768px) {
    .offer-header {
      flex-direction: column;
    }

    .detail-grid {
      grid-template-columns: 1fr;
    }

    .header-actions {
      width: 100%;
    }

    .btn-primary, .btn-secondary {
      flex: 1;
      text-align: center;
    }

    .pricing-header, .pricing-row {
      font-size: 0.8rem;
      padding: 0.4rem 0.5rem;
    }
  }
</style>
