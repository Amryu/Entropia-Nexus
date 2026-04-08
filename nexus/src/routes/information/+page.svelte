<!--
  @component Information Overview Page
  Displays category cards for all information types with quick navigation.
-->
<script>
  import '$lib/style.css';
  import AdSlot from '$lib/components/AdSlot.svelte';

  const categories = [
    {
      name: 'Mobs',
      href: '/information/mobs',
      icon: 'MOB',
      description: 'Creature database with maturities, spawns, loots, and codex calculator'
    },
    {
      name: 'Missions',
      href: '/information/missions',
      icon: 'MSN',
      description: 'Mission and mission chain reference data with steps and rewards'
    },
    {
      name: 'Professions',
      href: '/information/professions',
      icon: 'PRO',
      description: 'Character profession skill trees and level requirements'
    },
    {
      name: 'Skills',
      href: '/information/skills',
      icon: 'SKL',
      description: 'Individual character skills with profession contributions'
    },
    {
      name: 'Vendors',
      href: '/information/vendors',
      icon: 'VND',
      description: 'NPC trade terminal vendors with locations and offers'
    },
    {
      name: 'Locations',
      href: '/information/locations',
      icon: 'LOC',
      description: 'Teleporters, areas, estates, outposts, and other locations'
    },
    {
      name: 'Enumerations',
      href: '/information/enumerations',
      icon: 'ENUM',
      description: 'Built-in and custom name/value datasets shown as flattened reference tables'
    }
  ];
</script>

<svelte:head>
  <title>Information - Entropia Nexus</title>
  <meta name="description" content="Browse Entropia Universe reference data: missions, mobs, professions, skills, vendors, locations, and enumerations." />
  <link rel="canonical" href="https://entropianexus.com/information" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://entropianexus.com/information" />
  <meta property="og:title" content="Information - Entropia Nexus" />
  <meta property="og:description" content="Browse Entropia Universe reference data: missions, mobs, professions, skills, vendors, locations, and enumerations." />
  <meta property="og:image" content="https://entropianexus.com/icon.png" />
  <meta property="og:site_name" content="Entropia Nexus" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="Information - Entropia Nexus" />
  <meta name="twitter:description" content="Browse Entropia Universe reference data: missions, mobs, professions, skills, vendors, locations, and enumerations." />
  <meta name="twitter:image" content="https://entropianexus.com/icon.png" />
</svelte:head>

<div class="information-overview">
  <header class="page-header">
    <h1>Information</h1>
    <p class="subtitle">Reference data for Entropia Universe game mechanics</p>
  </header>

  <a href="/information/guides" class="guide-banner">
    <span class="guide-banner-icon">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
      </svg>
    </span>
    <div class="guide-banner-content">
      <h2 class="guide-banner-title">Guides</h2>
      <p class="guide-banner-description">Step-by-step guides and tutorials for Entropia Universe</p>
    </div>
    <span class="guide-banner-arrow">&rarr;</span>
  </a>

  <div class="category-grid">
    {#each categories as category}
      <a href={category.href} class="category-card">
        <span class="category-icon">{category.icon}</span>
        <div class="category-content">
          <h2 class="category-name">{category.name}</h2>
          <p class="category-description">{category.description}</p>
        </div>
        <span class="category-arrow">&rarr;</span>
      </a>
    {/each}
  </div>

  <div class="ad-placement">
    <AdSlot adSlot="9076572564" adFormat="auto" />
  </div>
</div>

<style>
  .ad-placement {
    max-width: 728px;
    margin: 32px auto 0;
  }

  .information-overview {
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

  .guide-banner {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px 24px;
    margin-bottom: 24px;
    background-color: var(--secondary-color);
    border: 2px solid var(--accent-color);
    border-radius: 8px;
    text-decoration: none;
    color: var(--text-color);
    transition: background-color 0.2s ease;
  }

  .guide-banner:hover {
    background-color: var(--hover-color);
  }

  .guide-banner-icon {
    flex-shrink: 0;
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--accent-color);
    border-radius: 8px;
    color: var(--primary-color);
  }

  .guide-banner-content {
    flex: 1;
    min-width: 0;
  }

  .guide-banner-title {
    margin: 0 0 4px 0;
    font-size: 1.2rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .guide-banner-description {
    margin: 0;
    font-size: 0.9rem;
    color: var(--text-muted);
  }

  .guide-banner-arrow {
    font-size: 1.5rem;
    color: var(--accent-color);
    flex-shrink: 0;
    transition: transform 0.2s ease;
  }

  .guide-banner:hover .guide-banner-arrow {
    transform: translateX(4px);
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

  .category-card:hover {
    border-color: var(--accent-color);
    background-color: var(--hover-color);
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

  .category-card:hover .category-arrow {
    transform: translateX(4px);
    color: var(--accent-color);
  }

  /* Mobile responsive */
  @media (max-width: 768px) {
    .information-overview {
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
