<!--
  @component Tools Overview Page
  Displays category cards for tool utilities and services.
-->
<script>
  import '$lib/style.css';

  const apiDocsUrl = `${import.meta.env.VITE_API_URL}/docs/`;

  const categories = [
    {
      name: 'Loadout Manager',
      href: '/tools/loadouts',
      icon: 'LM',
      description: 'Plan and save loadouts for weapons, armor, tools, and utilities'
    },
    {
      name: 'Construction Calculator',
      href: '/tools/construction',
      icon: 'CC',
      description: 'Calculate crafting requirements, materials, and costs for blueprints'
    },
    {
      name: 'Client',
      href: '/tools/client',
      icon: 'CL',
      description: 'Desktop companion app with OCR skill scanner, in-game overlays, and auto-updates'
    },
    {
      name: 'Skills Calculator',
      href: '/tools/skills',
      icon: 'SC',
      description: 'Import skills, calculate profession levels, and optimize skill progression',
      comingSoon: true
    },
    {
      name: 'API',
      href: apiDocsUrl,
      icon: 'API',
      description: 'Developer API documentation and endpoints',
      external: true
    }
  ];
</script>

<svelte:head>
  <title>Tools - Entropia Nexus</title>
  <meta name="description" content="Utilities and tools for Entropia Nexus, including loadout management and API access." />
  <link rel="canonical" href="https://entropianexus.com/tools" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://entropianexus.com/tools" />
  <meta property="og:title" content="Tools - Entropia Nexus" />
  <meta property="og:description" content="Utilities and tools for Entropia Nexus, including loadout management and API access." />
  <meta property="og:image" content="https://entropianexus.com/icon.png" />
  <meta property="og:site_name" content="Entropia Nexus" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="Tools - Entropia Nexus" />
  <meta name="twitter:description" content="Utilities and tools for Entropia Nexus, including loadout management and API access." />
  <meta name="twitter:image" content="https://entropianexus.com/icon.png" />
</svelte:head>

<div class="tools-overview">
  <header class="page-header">
    <h1>Tools</h1>
    <p class="subtitle">Utilities and services for Entropia Universe players</p>
  </header>

  <div class="category-grid">
    {#each categories as category}
      {#if category.comingSoon}
        <div class="category-card disabled">
          <span class="category-icon">{category.icon}</span>
          <div class="category-content">
            <h2 class="category-name">{category.name} <span class="coming-soon">Coming Soon</span></h2>
            <p class="category-description">{category.description}</p>
          </div>
        </div>
      {:else if category.external}
        <a href={category.href} class="category-card" target="_blank" rel="noreferrer">
          <span class="category-icon">{category.icon}</span>
          <div class="category-content">
            <h2 class="category-name">{category.name}</h2>
            <p class="category-description">{category.description}</p>
          </div>
          <span class="category-arrow">→</span>
        </a>
      {:else}
        <a href={category.href} class="category-card">
          <span class="category-icon">{category.icon}</span>
          <div class="category-content">
            <h2 class="category-name">{category.name}</h2>
            <p class="category-description">{category.description}</p>
          </div>
          <span class="category-arrow">→</span>
        </a>
      {/if}
    {/each}
  </div>
</div>

<style>
  .tools-overview {
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

  .category-card.disabled {
    opacity: 0.55;
    cursor: default;
    pointer-events: none;
  }

  .coming-soon {
    font-size: 0.7rem;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    margin-left: 6px;
  }

  /* Mobile responsive */
  @media (max-width: 768px) {
    .tools-overview {
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
