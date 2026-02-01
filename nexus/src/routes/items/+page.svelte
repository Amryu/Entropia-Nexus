<!--
  @component Items Overview Page
  Displays category cards for all item types with quick navigation.
-->
<script>
  import '$lib/style.css';

  const categories = [
    {
      name: 'Weapons',
      href: '/items/weapons',
      icon: '⚔️',
      description: 'Combat weapons including melee, ranged, BLP and laser weapons'
    },
    {
      name: 'Armor Sets',
      href: '/items/armorsets',
      icon: '🛡️',
      description: 'Protective armor sets with piece stats and set bonuses'
    },
    {
      name: 'Clothing',
      href: '/items/clothing',
      icon: '👕',
      description: 'Wearable items including cosmetics and buff equipment'
    },
    {
      name: 'Attachments',
      href: '/items/attachments',
      icon: '🔧',
      description: 'Weapon enhancements: amplifiers, scopes, sights, and absorbers'
    },
    {
      name: 'Medical Tools',
      href: '/items/medicaltools',
      icon: '💊',
      description: 'Healing equipment including FAPs and healing chips'
    },
    {
      name: 'Tools',
      href: '/items/tools',
      icon: '⛏️',
      description: 'Mining and crafting equipment: finders, excavators, refiners'
    },
    {
      name: 'Materials',
      href: '/items/materials',
      icon: '💎',
      description: 'Crafting resources: ores, enmatter, animal materials'
    },
    {
      name: 'Blueprints',
      href: '/items/blueprints',
      icon: '📋',
      description: 'Crafting recipes with material requirements and QR info'
    },
    {
      name: 'Consumables',
      href: '/items/consumables',
      icon: '🧪',
      description: 'Single-use items: pills, nutrio bars, stimulants'
    },
    {
      name: 'Vehicles',
      href: '/items/vehicles',
      icon: '🚗',
      description: 'Transportation: ground, air, and water vehicles'
    },
    {
      name: 'Pets',
      href: '/items/pets',
      icon: '🐾',
      description: 'Companion creatures with skills and buff effects'
    },
    {
      name: 'Furnishings',
      href: '/items/furnishings',
      icon: '🪑',
      description: 'Estate decorations: furniture, decorations, and signs'
    },
    {
      name: 'Strongboxes',
      href: '/items/strongboxes',
      icon: '📦',
      description: 'Strongboxes acquirable from the EU shop and events'
    }
  ];
</script>

<svelte:head>
  <title>Items - Entropia Nexus</title>
  <meta name="description" content="Browse all Entropia Universe items: weapons, armor, tools, materials, blueprints, and more." />
  <link rel="canonical" href="https://entropianexus.com/items" />
</svelte:head>

<div class="items-overview">
  <header class="page-header">
    <h1>Items Database</h1>
    <p class="subtitle">Browse all Entropia Universe items by category</p>
  </header>

  <div class="category-grid">
    {#each categories as category}
      <a href={category.href} class="category-card">
        <span class="category-icon">{category.icon}</span>
        <div class="category-content">
          <h2 class="category-name">{category.name}</h2>
          <p class="category-description">{category.description}</p>
        </div>
        <span class="category-arrow">→</span>
      </a>
    {/each}
  </div>
</div>

<style>
  .items-overview {
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

  .category-card:hover {
    border-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .category-icon {
    font-size: 2rem;
    flex-shrink: 0;
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--primary-color);
    border-radius: 8px;
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
    .items-overview {
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
      font-size: 1.5rem;
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
