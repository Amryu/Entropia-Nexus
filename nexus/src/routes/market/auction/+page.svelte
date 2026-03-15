<!--
  @component Auction Listing Page
  Browse active auctions with search and filters.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import AuctionCard from '$lib/components/auction/AuctionCard.svelte';
  import LoginToCreateButton from '$lib/components/LoginToCreateButton.svelte';

  let { data } = $props();

  let auctions = $derived(data.auctions || []);
  let total = $derived(data.total || 0);
  let filters = $derived(data.filters || {});
  let user = $derived(data.session?.user);
  let isVerified = $derived(!!user?.verified);
  let limit = $derived(data.limit);
  let totalPages = $derived(Math.ceil(total / limit));

  let searchInput = $state('');
  let searchTimeout;

  // Re-sync search input from page data on navigation
  $effect(() => {
    searchInput = filters?.search || '';
  });

  function updateFilter(key, value) {
    const url = new URL($page.url);
    if (value) {
      url.searchParams.set(key, value);
    } else {
      url.searchParams.delete(key);
    }
    if (key !== 'page') url.searchParams.delete('page');
    goto(url.pathname + url.search);
  }

  function handleSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      updateFilter('search', searchInput.trim());
    }, 300);
  }

  function handleSort(e) {
    updateFilter('sort', e.target.value);
  }

  function handleStatusFilter(e) {
    updateFilter('status', e.target.value);
  }

  function goToPage(p) {
    updateFilter('page', String(p));
  }
</script>

<svelte:head>
  <title>Auctions - Market - Entropia Nexus</title>
  <meta name="description" content="Browse and bid on item auctions in Entropia Universe." />
  <link rel="canonical" href="https://entropianexus.com/market/auction" />
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/market">Market</a>
      <span>/</span>
      <span>Auctions</span>
    </div>

    <div class="page-header">
      <div class="header-left">
        <h1>Auctions</h1>
        <p class="subtitle">Bid on item sets from other players</p>
      </div>
      <div class="header-actions">
        {#if isVerified}
          <a href="/market/auction/my" class="btn-secondary">My Auctions</a>
          <a href="/market/auction/create" class="btn-primary">Create Auction</a>
        {:else}
          <LoginToCreateButton {user} label="Login to create auction" createUrl="/market/auction/create" />
        {/if}
      </div>
    </div>

    <div class="filters">
      <div class="filter-group">
        <input
          type="text"
          bind:value={searchInput}
          oninput={handleSearch}
          placeholder="Search auctions..."
          class="search-input"
        />
      </div>
      <div class="filter-group">
        <select value={filters.status} onchange={handleStatusFilter}>
          <option value="active">Active</option>
          <option value="ended">Ended</option>
          <option value="settled">Settled</option>
        </select>
      </div>
      <div class="filter-group">
        <select value={filters.sort} onchange={handleSort}>
          <option value="ends_at">Ending Soon</option>
          <option value="created_at">Newest</option>
          <option value="current_bid">Highest Bid</option>
          <option value="bid_count">Most Bids</option>
          <option value="starting_bid">Starting Price</option>
        </select>
      </div>
    </div>

    {#if auctions.length === 0}
      <div class="empty-state">
        <p>No auctions found</p>
        {#if filters.search}
          <button class="btn-secondary" onclick={() => { searchInput = ''; updateFilter('search', ''); }}>
            Clear search
          </button>
        {/if}
      </div>
    {:else}
      <div class="auction-grid">
        {#each auctions as auction (auction.id)}
          <AuctionCard {auction} />
        {/each}
      </div>

      {#if totalPages > 1}
        <div class="pagination">
          <button
            class="page-btn"
            disabled={filters.page <= 1}
            onclick={() => goToPage(filters.page - 1)}
          >
            Previous
          </button>
          <span class="page-info">Page {filters.page} of {totalPages}</span>
          <button
            class="page-btn"
            disabled={filters.page >= totalPages}
            onclick={() => goToPage(filters.page + 1)}
          >
            Next
          </button>
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
    flex-wrap: wrap;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
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
    gap: 1rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
  }

  .header-left h1 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-color);
  }

  .subtitle {
    margin: 0.25rem 0 0 0;
    font-size: 0.9rem;
    color: var(--text-muted);
  }

  .header-actions {
    display: flex;
    gap: 0.5rem;
    flex-shrink: 0;
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

  .btn-primary {
    background: var(--accent-color);
    border: 1px solid var(--accent-color);
    color: white;
  }

  .btn-primary:hover {
    background: var(--accent-color-hover);
  }

  .btn-secondary {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .btn-secondary:hover {
    background: var(--hover-color);
  }

  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
  }

  .filter-group select,
  .search-input {
    padding: 0.5rem 0.75rem;
    font-size: 0.85rem;
    border: 1px solid var(--border-color);
    background: var(--secondary-color);
    color: var(--text-color);
    border-radius: 6px;
    box-sizing: border-box;
  }

  .filter-group select:focus,
  .search-input:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .filter-group select option {
    background-color: var(--secondary-color);
    color: var(--text-color);
  }

  .search-input {
    min-width: 200px;
  }

  .auction-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 1rem;
  }

  .empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--text-muted);
  }

  .empty-state p {
    font-size: 1rem;
    margin-bottom: 1rem;
  }

  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 1rem;
    margin-top: 2rem;
    padding: 1rem 0;
  }

  .page-btn {
    padding: 0.4rem 0.8rem;
    font-size: 0.85rem;
    border: 1px solid var(--border-color);
    background: var(--secondary-color);
    color: var(--text-color);
    border-radius: 6px;
    cursor: pointer;
  }

  .page-btn:hover:not(:disabled) {
    background: var(--hover-color);
  }

  .page-btn:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }

  .page-info {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  @media (max-width: 899px) {
    .page-container {
      padding: 1rem;
      padding-bottom: 2rem;
    }

    .page-header {
      flex-direction: column;
    }

    .auction-grid {
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    }
  }
</style>
