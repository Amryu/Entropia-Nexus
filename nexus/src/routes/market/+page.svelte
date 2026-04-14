<!--
  @component Market Dashboard
  Comprehensive dashboard with unified search, marketplace sections, exchange category browsing,
  and service type browsing. All data loaded server-side for fast initial render.
-->
<script>
  import '$lib/style.css';
  import MarketSearch from '$lib/components/MarketSearch.svelte';
  let { data } = $props();

  let featuredSections = $derived([
    {
      name: 'Exchange',
      href: '/market/exchange',
      description: 'Browse thousands of items for trading with other players',
      countLabel: 'active items',
      count: data.totalExchangeActive,
      cls: 'featured-exchange'
    },
    {
      name: 'Services',
      href: '/market/services',
      description: 'Find healing, DPS, transportation and more',
      countLabel: 'available',
      count: data.totalServices,
      cls: 'featured-services'
    }
  ]);

  let secondarySections = $derived([
    {
      name: 'Shops',
      href: '/market/shops',
      description: 'Player-owned shop inventories',
      countLabel: 'shops',
      count: data.totalShops
    },
    {
      name: 'Auction',
      href: '/market/auction',
      description: 'Bid on item sets and buyout listings',
      countLabel: 'active',
      count: data.activeAuctions
    },
    {
      name: 'Rental',
      href: '/market/rental',
      description: 'Rent equipment from other players',
      countLabel: 'available',
      count: data.availableRentals
    }
  ]);

  const serviceTypes = [
    { key: 'healing', name: 'Healing', description: 'Paramedic and healing services' },
    { key: 'dps', name: 'DPS', description: 'Damage support services' },
    { key: 'transportation', name: 'Transportation', description: 'Flights and warp services' },
    { key: 'custom', name: 'Custom', description: 'Custom player services' }
  ];

  function formatCount(n) {
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return String(n ?? 0);
  }
</script>

<svelte:head>
  <title>Market - Entropia Nexus</title>
  <meta name="description" content="Trade, buy, and sell in Entropia Universe: browse the exchange, hire services, find shops, bid on auctions, and rent equipment." />
  <link rel="canonical" href="https://entropianexus.com/market" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://entropianexus.com/market" />
  <meta property="og:title" content="Market - Entropia Nexus" />
  <meta property="og:description" content="Trade, buy, and sell in Entropia Universe: browse the exchange, hire services, find shops, bid on auctions, and rent equipment." />
  <meta property="og:image" content="https://entropianexus.com/icon.png" />
  <meta property="og:site_name" content="Entropia Nexus" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="Market - Entropia Nexus" />
  <meta name="twitter:description" content="Trade, buy, and sell in Entropia Universe: browse the exchange, hire services, find shops, bid on auctions, and rent equipment." />
  <meta name="twitter:image" content="https://entropianexus.com/icon.png" />
</svelte:head>

<div class="market-dashboard">
  <!-- Header + Search -->
  <header class="dashboard-header">
    <h1>Market</h1>
    <MarketSearch />
  </header>

  <!-- Featured Marketplace Sections (Exchange + Services) -->
  <div class="featured-grid">
    {#each featuredSections as section}
      <a href={section.href} class="featured-card {section.cls}">
        <div class="featured-top">
          <h2 class="featured-name">{section.name}</h2>
          <span class="featured-arrow">&rarr;</span>
        </div>
        <p class="featured-description">{section.description}</p>
        <div class="featured-bottom">
          <span class="featured-count">{formatCount(section.count)}</span>
          <span class="featured-count-label">{section.countLabel}</span>
        </div>
      </a>
    {/each}
  </div>

  <!-- Secondary Marketplace Sections (Shops, Auction, Rental) -->
  <div class="secondary-grid">
    {#each secondarySections as section}
      <a href={section.href} class="secondary-card">
        <h3 class="secondary-name">{section.name}</h3>
        <p class="secondary-description">{section.description}</p>
        <div class="secondary-bottom">
          <span class="secondary-count">{formatCount(section.count)}</span>
          <span class="secondary-count-label">{section.countLabel}</span>
        </div>
      </a>
    {/each}
  </div>

  <!-- Browse Exchange Categories -->
  {#if data.exchangeCategories.length > 0}
    <section class="dashboard-section">
      <div class="section-header">
        <h2 class="section-title">Browse Exchange</h2>
        <a href="/market/exchange" class="section-link">View all &rarr;</a>
      </div>
      <div class="category-grid">
        {#each data.exchangeCategories as category}
          <a
            href="/market/exchange/{category.key}"
            class="category-card"
            class:category-empty={category.activeCount === 0}
            onclick={() => typeof sessionStorage !== 'undefined' && sessionStorage.setItem('exchangeCategory', category.key)}
          >
            <span class="category-name">{category.name}</span>
            <span class="category-count">{formatCount(category.activeCount)} {category.activeCount === 1 ? 'item' : 'items'}</span>
          </a>
        {/each}
      </div>
    </section>
  {/if}

  <!-- PCF Trade -->
  {#if data.forumStats.total_active > 0}
    <section class="dashboard-section">
      <div class="section-header">
        <h2 class="section-title">PCF Trade</h2>
        <a href="/market/forum" class="section-link">Browse all &rarr;</a>
      </div>
      <div class="forum-grid">
        <a href="/market/forum?type=selling" class="forum-card">
          <span class="forum-card-name">Selling</span>
          <span class="forum-card-desc">Items listed for sale on PCF</span>
          <span class="forum-card-count">{formatCount(data.forumStats.sell_count)} threads</span>
        </a>
        <a href="/market/forum?type=buying" class="forum-card">
          <span class="forum-card-name">Buying</span>
          <span class="forum-card-desc">Items wanted by other players</span>
          <span class="forum-card-count">{formatCount(data.forumStats.buy_count)} threads</span>
        </a>
      </div>
    </section>
  {/if}

  <!-- Browse & Offer Services -->
  <section class="dashboard-section">
    <div class="section-header">
      <h2 class="section-title">Browse & Offer Services</h2>
      <a href="/market/services" class="section-link">Browse all &rarr;</a>
    </div>
    <div class="service-grid">
      {#each serviceTypes as stype}
        <a href="/market/services/{stype.key}" class="service-card">
          <span class="service-name">{stype.name}</span>
          <span class="service-description">{stype.description}</span>
          <span class="service-count">{data.serviceCounts[stype.key]} available</span>
        </a>
      {/each}
    </div>
  </section>
</div>

<style>
  .market-dashboard {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
    padding-bottom: 2rem;
  }

  /* Header + Search */
  .dashboard-header {
    text-align: center;
    margin-bottom: 40px;
  }

  .dashboard-header h1 {
    margin: 0 0 20px 0;
    color: var(--text-color);
    font-size: 2rem;
  }

  /* Featured Cards (Exchange + Services) */
  .featured-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-bottom: 16px;
  }

  .featured-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 24px;
    background-color: var(--secondary-color);
    border: 2px solid var(--accent-color);
    border-radius: 12px;
    text-decoration: none;
    color: var(--text-color);
    transition: background-color 0.2s ease, box-shadow 0.2s ease;
  }

  .featured-card:hover {
    background-color: var(--hover-color);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .featured-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .featured-name {
    margin: 0;
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--text-color);
  }

  .featured-arrow {
    font-size: 1.3rem;
    color: var(--accent-color);
    transition: transform 0.2s ease;
  }

  .featured-card:hover .featured-arrow {
    transform: translateX(4px);
  }

  .featured-description {
    margin: 0;
    font-size: 0.9rem;
    color: var(--text-muted);
    line-height: 1.4;
  }

  .featured-bottom {
    display: flex;
    align-items: baseline;
    gap: 6px;
    margin-top: auto;
  }

  .featured-count {
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--accent-color);
    line-height: 1;
  }

  .featured-count-label {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  /* Secondary Cards (Shops, Auction, Rental) */
  .secondary-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 40px;
  }

  .secondary-card {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 20px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    text-decoration: none;
    color: var(--text-color);
    transition: border-color 0.2s ease, background-color 0.2s ease;
  }

  .secondary-card:hover {
    border-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .secondary-name {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .secondary-description {
    margin: 0;
    font-size: 0.8rem;
    color: var(--text-muted);
    line-height: 1.3;
  }

  .secondary-bottom {
    display: flex;
    align-items: baseline;
    gap: 6px;
    margin-top: auto;
  }

  .secondary-count {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--accent-color);
    line-height: 1;
  }

  .secondary-count-label {
    font-size: 0.7rem;
    color: var(--text-muted);
  }

  /* Sections */
  .dashboard-section {
    margin-bottom: 40px;
  }

  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .section-title {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .section-link {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--accent-color);
    text-decoration: none;
    transition: opacity 0.2s ease;
  }

  .section-link:hover {
    opacity: 0.8;
  }

  /* Exchange Category Grid */
  .category-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
  }

  .category-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 20px 14px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-left: 3px solid var(--border-color);
    border-radius: 8px;
    text-decoration: none;
    color: var(--text-color);
    transition: border-color 0.2s ease, background-color 0.2s ease, border-left-color 0.2s ease;
    text-align: center;
  }

  .category-card:hover {
    border-color: var(--accent-color);
    border-left-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .category-empty {
    opacity: 0.5;
  }

  .category-name {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .category-count {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  /* Service Type Grid */
  .service-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
  }

  .service-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 20px 14px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-left: 3px solid var(--border-color);
    border-radius: 8px;
    text-decoration: none;
    color: var(--text-color);
    transition: border-color 0.2s ease, background-color 0.2s ease, border-left-color 0.2s ease;
    text-align: center;
  }

  .service-card:hover {
    border-color: var(--accent-color);
    border-left-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .service-name {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .service-description {
    font-size: 0.8rem;
    color: var(--text-muted);
    line-height: 1.3;
  }

  .service-count {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--accent-color);
    margin-top: auto;
  }

  /* Forum Trade Grid */
  .forum-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
  }

  .forum-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 20px 14px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-left: 3px solid var(--border-color);
    border-radius: 8px;
    text-decoration: none;
    color: var(--text-color);
    transition: border-color 0.2s ease, background-color 0.2s ease, border-left-color 0.2s ease;
    text-align: center;
  }

  .forum-card:hover {
    border-color: var(--accent-color);
    border-left-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .forum-card-name {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .forum-card-desc {
    font-size: 0.8rem;
    color: var(--text-muted);
    line-height: 1.3;
  }

  .forum-card-count {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--accent-color);
    margin-top: auto;
  }

  /* Responsive */
  @media (max-width: 900px) {
    .market-dashboard {
      padding: 16px;
    }

    .dashboard-header h1 {
      font-size: 1.5rem;
    }

    .featured-grid {
      grid-template-columns: 1fr;
    }

    .secondary-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .category-grid {
      grid-template-columns: repeat(3, 1fr);
    }

    .service-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (max-width: 600px) {
    .secondary-grid {
      grid-template-columns: 1fr;
    }

    .category-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .service-grid {
      grid-template-columns: 1fr;
    }

    .forum-grid {
      grid-template-columns: 1fr;
    }

    .featured-description,
    .secondary-description,
    .forum-card-desc {
      display: none;
    }
  }
</style>
