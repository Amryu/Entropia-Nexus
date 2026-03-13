<!--
  @component Rental Listing Page
  Browse available rental offers with planet filter.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import RentalOfferCard from '$lib/components/rental/RentalOfferCard.svelte';
  import LoginToCreateButton from '$lib/components/LoginToCreateButton.svelte';

  let { data } = $props();

  let offers = $derived(data.offers || []);
  let planets = $derived(data.planets || []);
  let filters = $derived(data.filters || {});
  let user = $derived(data.session?.user);
  let isVerified = $derived(!!user?.verified);

  let planetMap = $derived(Object.fromEntries(planets.map(p => [p.Id, p.Name])));

  let searchQuery = $state('');

  let filteredOffers = $derived(offers.filter(o => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return o.title?.toLowerCase().includes(q) || o.owner_name?.toLowerCase().includes(q);
  }));

  function handlePlanetFilter(e) {
    const planetId = e.target.value;
    const url = new URL($page.url);
    if (planetId) {
      url.searchParams.set('planet_id', planetId);
    } else {
      url.searchParams.delete('planet_id');
    }
    url.searchParams.delete('page');
    goto(url.pathname + url.search);
  }
</script>

<svelte:head>
  <title>Item Rentals - Market - Entropia Nexus</title>
  <meta name="description" content="Rent equipment from other players in Entropia Universe. Browse available items for rent." />
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/market">Market</a>
      <span>/</span>
      <span>Item Rentals</span>
    </div>

    <div class="page-header">
      <div class="header-left">
        <h1>Item Rentals</h1>
        <p class="subtitle">Rent equipment from other players</p>
      </div>
      <div class="header-actions">
        {#if isVerified}
          <a href="/market/rental/my" class="btn-secondary">My Rentals</a>
          <a href="/market/rental/create" class="btn-primary">Create Offer</a>
        {:else}
          <LoginToCreateButton {user} label="Login to create offer" createUrl="/market/rental/create" />
        {/if}
      </div>
    </div>

    <div class="filters">
      <div class="filter-group">
        <select value={filters.planet_id || ''} onchange={handlePlanetFilter}>
          <option value="">All Planets</option>
          {#each planets as planet}
            <option value={planet.Id}>{planet.Name}</option>
          {/each}
        </select>
      </div>
      <div class="filter-group">
        <input
          type="text"
          placeholder="Search by title or owner..."
          bind:value={searchQuery}
        />
      </div>
    </div>

    {#if filteredOffers.length === 0}
      <div class="empty-state">
        <p>No rental offers found.</p>
        {#if isVerified}
          <p>Be the first to <a href="/market/rental/create">create a rental offer</a>!</p>
        {/if}
      </div>
    {:else}
      <div class="offers-grid">
        {#each filteredOffers as offer (offer.id)}
          <RentalOfferCard {offer} planets={planetMap} />
        {/each}
      </div>
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
    align-items: flex-start;
    margin-bottom: 1.5rem;
    gap: 1rem;
  }

  .header-left h1 {
    margin: 0 0 0.25rem;
    font-size: 1.75rem;
  }

  .subtitle {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.95rem;
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

  .filters {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
  }

  .filter-group select,
  .filter-group input {
    padding: 0.5rem 0.75rem;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.9rem;
    min-width: 180px;
    box-sizing: border-box;
  }

  .filter-group select:focus,
  .filter-group input:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .offers-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 1rem;
  }

  .empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--text-muted);
  }

  .empty-state a {
    color: var(--accent-color);
  }

  @media (max-width: 768px) {
    .page-header {
      flex-direction: column;
    }

    .header-actions {
      width: 100%;
    }

    .btn-primary, .btn-secondary {
      flex: 1;
      text-align: center;
    }

    .filters {
      flex-direction: column;
    }

    .filter-group select,
    .filter-group input {
      width: 100%;
      min-width: unset;
    }

    .offers-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
