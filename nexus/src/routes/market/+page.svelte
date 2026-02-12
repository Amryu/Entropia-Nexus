<!--
  @component Market Overview Page
  Displays category cards for all market sections with quick navigation.
  Disabled sections (Auction) shown with reduced opacity and "Coming Soon" badge.
-->
<script>
  import '$lib/style.css';

  const categories = [
    {
      name: 'Exchange',
      href: '/market/exchange',
      icon: 'EXC',
      description: 'Player-to-player item trading with buy and sell orders'
    },
    {
      name: 'Services',
      href: '/market/services',
      icon: 'SVC',
      description: 'Browse and offer services to other players'
    },
    {
      name: 'Shops',
      href: '/market/shops',
      icon: 'SHP',
      description: 'Player-owned shops and their inventories'
    },
    {
      name: 'Auction',
      href: '/market/auction',
      icon: 'AUC',
      description: 'Bid on item sets and buyout listings from other players'
    },
    {
      name: 'Rental',
      href: '/market/rental',
      icon: 'RNT',
      description: 'Equipment rental marketplace'
    }
  ];
</script>

<svelte:head>
  <title>Market - Entropia Nexus</title>
  <meta name="description" content="Trade, buy, and sell in Entropia Universe: player exchange, services, shops, and more." />
  <link rel="canonical" href="https://entropianexus.com/market" />
</svelte:head>

<div class="market-overview">
  <header class="page-header">
    <h1>Market</h1>
    <p class="subtitle">Trade, buy, and sell in Entropia Universe</p>
  </header>

  <div class="category-grid">
    {#each categories as category}
      {#if category.disabled}
        <div class="category-card disabled">
          <span class="category-icon">{category.icon}</span>
          <div class="category-content">
            <h2 class="category-name">
              {category.name}
              <span class="coming-soon-badge">Coming Soon</span>
            </h2>
            <p class="category-description">{category.description}</p>
          </div>
        </div>
      {:else}
        <a href={category.href} class="category-card">
          <span class="category-icon">{category.icon}</span>
          <div class="category-content">
            <h2 class="category-name">{category.name}</h2>
            <p class="category-description">{category.description}</p>
          </div>
          <span class="category-arrow">&rarr;</span>
        </a>
      {/if}
    {/each}
  </div>
</div>

<style>
  .market-overview {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
  }

  .page-header {
    text-align: center;
    margin-bottom: 32px;
  }

  .page-header h1 {
    margin: 0 0 8px 0;
    color: var(--text-color);
    font-size: 2rem;
  }

  .subtitle {
    margin: 0;
    color: var(--text-muted);
    font-size: 1.1rem;
  }

  .category-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
  }

  .category-card {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    text-decoration: none;
    color: var(--text-color);
    transition: border-color 0.2s ease, background-color 0.2s ease;
  }

  .category-card:not(.disabled):hover {
    border-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .category-card.disabled {
    opacity: 0.4;
    cursor: default;
  }

  .category-icon {
    font-size: 1rem;
    font-weight: 700;
    flex-shrink: 0;
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--primary-color);
    border-radius: 8px;
    letter-spacing: 0.5px;
  }

  .category-content {
    flex: 1;
    min-width: 0;
  }

  .category-name {
    margin: 0 0 4px 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-color);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .coming-soon-badge {
    font-size: 0.7rem;
    font-weight: 500;
    padding: 2px 8px;
    border-radius: 4px;
    background-color: var(--border-color);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .category-description {
    margin: 0;
    font-size: 0.875rem;
    color: var(--text-muted);
    line-height: 1.4;
  }

  .category-arrow {
    font-size: 1.25rem;
    color: var(--text-muted);
    flex-shrink: 0;
    transition: transform 0.2s ease;
  }

  .category-card:not(.disabled):hover .category-arrow {
    transform: translateX(4px);
    color: var(--accent-color);
  }

  /* Mobile responsive */
  @media (max-width: 768px) {
    .market-overview {
      padding: 16px;
    }

    .page-header h1 {
      font-size: 1.5rem;
    }

    .subtitle {
      font-size: 1rem;
    }

    .category-grid {
      grid-template-columns: 1fr;
    }

    .category-card {
      padding: 16px;
    }

    .category-icon {
      width: 40px;
      height: 40px;
    }

    .category-name {
      font-size: 1rem;
    }

    .category-description {
      font-size: 0.8125rem;
    }
  }
</style>
