<!--
  @component My Rentals Dashboard
  Tabs for user's own rental offers and outgoing requests.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { goto } from '$app/navigation';
  import RentalStatusBadge from '$lib/components/rental/RentalStatusBadge.svelte';
  import { formatPrice } from '$lib/utils/rentalPricing.js';

  export let data;

  $: offers = data.offers || [];
  $: requests = data.requests || [];
  $: user = data.session?.user;
  $: isVerified = !!user?.verified;

  let activeTab = 'offers';

  function formatDateDisplay(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
</script>

<svelte:head>
  <title>My Rentals - Market - Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/market">Market</a>
      <span>/</span>
      <a href="/market/rental">Item Rentals</a>
      <span>/</span>
      <span>My Rentals</span>
    </div>

    <div class="page-header">
      <h1>My Rentals</h1>
      {#if isVerified}
        <a href="/market/rental/create" class="btn-primary">Create Offer</a>
      {/if}
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button
        class="tab"
        class:active={activeTab === 'offers'}
        on:click={() => activeTab = 'offers'}
      >
        My Offers ({offers.length})
      </button>
      <button
        class="tab"
        class:active={activeTab === 'requests'}
        on:click={() => activeTab = 'requests'}
      >
        My Requests ({requests.length})
      </button>
    </div>

    <!-- My Offers Tab -->
    {#if activeTab === 'offers'}
      {#if offers.length === 0}
        <div class="empty-state">
          <p>You haven't created any rental offers yet.</p>
          {#if isVerified}
            <p><a href="/market/rental/create">Create your first offer</a></p>
          {/if}
        </div>
      {:else}
        <div class="list">
          {#each offers as offer (offer.id)}
            <div class="list-item">
              <div class="item-info">
                <div class="item-header">
                  <a href="/market/rental/{offer.id}/edit" class="item-title">{offer.title}</a>
                  <RentalStatusBadge status={offer.status} type="offer" size="small" />
                </div>
                <div class="item-meta">
                  <span>{formatPrice(offer.price_per_day)}/day</span>
                  {#if Number(offer.deposit) > 0}
                    <span>Deposit: {formatPrice(offer.deposit)}</span>
                  {/if}
                </div>
              </div>
              <a href="/market/rental/{offer.id}/edit" class="item-action">
                Edit &rarr;
              </a>
            </div>
          {/each}
        </div>
      {/if}
    {/if}

    <!-- My Requests Tab -->
    {#if activeTab === 'requests'}
      {#if requests.length === 0}
        <div class="empty-state">
          <p>You haven't made any rental requests.</p>
          <p><a href="/market/rental">Browse available rentals</a></p>
        </div>
      {:else}
        <div class="list">
          {#each requests as req (req.id)}
            <div class="list-item">
              <div class="item-info">
                <div class="item-header">
                  <span class="item-title">{req.offer_title || 'Rental'}</span>
                  <RentalStatusBadge status={req.status} type="request" size="small" />
                </div>
                <div class="item-meta">
                  <span>{formatDateDisplay(req.start_date)} &ndash; {formatDateDisplay(req.end_date)}</span>
                  <span>{req.total_days} day{req.total_days !== 1 ? 's' : ''}</span>
                  <span>Total: {formatPrice(req.total_price)}</span>
                </div>
                {#if req.owner_name}
                  <div class="item-owner">Owner: {req.owner_name}</div>
                {/if}
              </div>
              <a href="/market/rental/requests/{req.id}" class="item-action">
                View &rarr;
              </a>
            </div>
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

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    margin: 0;
    font-size: 1.75rem;
  }

  .btn-primary {
    padding: 0.5rem 1rem;
    background: var(--accent-color);
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 0.9rem;
    font-weight: 500;
    text-decoration: none;
    white-space: nowrap;
  }

  .btn-primary:hover {
    background: var(--accent-color-hover);
  }

  .tabs {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 1.5rem;
  }

  .tab {
    padding: 0.75rem 1.25rem;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 0.95rem;
    font-weight: 500;
    position: relative;
  }

  .tab:hover {
    color: var(--text-color);
  }

  .tab.active {
    color: var(--accent-color);
  }

  .tab.active::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--accent-color);
  }

  .empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--text-muted);
  }

  .empty-state a {
    color: var(--accent-color);
  }

  .list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .list-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    gap: 1rem;
  }

  .item-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    min-width: 0;
  }

  .item-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .item-title {
    font-weight: 600;
    font-size: 1rem;
    color: var(--text-color);
    text-decoration: none;
  }

  a.item-title:hover {
    color: var(--accent-color);
  }

  .item-meta {
    display: flex;
    gap: 0.75rem;
    font-size: 0.85rem;
    color: var(--text-muted);
    flex-wrap: wrap;
  }

  .item-owner {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .item-action {
    color: var(--accent-color);
    text-decoration: none;
    font-size: 0.9rem;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .item-action:hover {
    text-decoration: underline;
  }

  @media (max-width: 768px) {
    .list-item {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
