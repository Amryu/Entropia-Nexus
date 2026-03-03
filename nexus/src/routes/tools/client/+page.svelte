<!--
  @component Client download & information page.
  Shows features, platform downloads, and changelog.
-->
<script>
  import '$lib/style.css';

  export let data;
  $: changelog = data.changelog || [];
  $: latestVersion = changelog[0]?.version || '0.1.0';

  const features = [
    {
      title: 'Entropia Nexus Wiki',
      description: 'Browse the full Entropia Nexus wiki from an in-game overlay — items, mobs, locations, professions, and more. Look up anything without leaving the game.'
    },
    {
      title: 'In-Game Overlays',
      description: 'Transparent, always-on-top overlays for quick access. Search players, view profiles, check scan results, and browse the wiki at a glance.'
    },
    {
      title: 'Exchange Market',
      description: 'Access the Entropia Nexus exchange directly from an overlay. Browse items, view orders, and place buy or sell offers without alt-tabbing.'
    },
    {
      title: 'Loadout Manager',
      description: 'Plan and compare equipment loadouts. Configure weapons, armor, enhancers, and calculate DPS, economy, and markup costs.'
    },
    {
      title: 'OCR Skill Scanner',
      description: 'Reads your in-game Skills window using computer vision. Detects skill names, ranks, points, and progress — then imports everything to your Nexus account.'
    },
    {
      title: 'Auto-Updates',
      description: 'Delta update system that only downloads changed files. The client checks for updates in the background and applies them with one click.'
    }
  ];

  const platforms = [
    {
      name: 'Windows',
      file: (v) => `/static/client/windows/entropia-nexus-${v}-windows.zip`,
      note: 'Windows 10+ (64-bit)'
    },
    {
      name: 'Linux',
      file: (v) => `/static/client/linux/entropia-nexus-${v}-linux.tar.gz`,
      note: 'x86_64, glibc 2.31+'
    }
  ];

  const typeBadge = {
    feat:    { label: 'NEW',      cls: 'badge-feat' },
    fix:     { label: 'FIX',      cls: 'badge-fix' },
    improve: { label: 'IMPROVED', cls: 'badge-improve' },
    remove:  { label: 'REMOVED',  cls: 'badge-remove' },
  };
</script>

<svelte:head>
  <title>Client - Entropia Nexus</title>
  <meta name="description" content="Download the Entropia Nexus desktop client — in-game wiki, overlays, exchange market, loadout manager, OCR skill scanner, and automatic updates." />
  <link rel="canonical" href="https://entropianexus.com/tools/client" />
</svelte:head>

<div class="client-page">
  <!-- Header -->
  <header class="page-header">
    <nav class="breadcrumbs">
      <a href="/tools">Tools</a>
      <span class="sep">/</span>
      <span>Client</span>
    </nav>
    <h1>Entropia Nexus Client</h1>
    <p class="subtitle">Desktop companion app for Entropia Universe</p>
  </header>

  <!-- Features -->
  <section class="section">
    <h2 class="section-title">Features</h2>
    <div class="features-grid">
      {#each features as feature}
        <div class="feature-card">
          <h3 class="feature-title">{feature.title}</h3>
          <p class="feature-desc">{feature.description}</p>
        </div>
      {/each}
    </div>
  </section>

  <!-- Downloads -->
  <section class="section">
    <h2 class="section-title">Download <span class="version-tag">v{latestVersion}</span></h2>
    <div class="downloads-grid">
      {#each platforms as platform}
        <a href={platform.file(latestVersion)} class="download-card" download>
          <span class="download-icon">
            {#if platform.name === 'Windows'}
              <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor">
                <path d="M3 12.5l7.5-1.03V5.5L3 6.53V12.5zm0 5.97l7.5.97V13.5L3 14.5v3.97zM11.5 19.6L21 21V13.5l-9.5.03V19.6zM11.5 4.4V11.5L21 11.47V3L11.5 4.4z"/>
              </svg>
            {:else}
              <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C9.8 2 8.2 3.4 8 5.2c-.7.3-1.2.8-1.6 1.5C5 7 4 8.2 4 9.7c0 .8.3 1.5.7 2.1-.4.7-.7 1.5-.7 2.3 0 1.8 1.1 3.3 2.7 3.8.2 1.7 1.5 3.1 3.3 3.1.7 0 1.3-.2 1.8-.6.1 0 .1.1.2.1.1-.1.1-.1.2-.1.5.4 1.1.6 1.8.6 1.8 0 3.1-1.4 3.3-3.1 1.6-.5 2.7-2 2.7-3.8 0-.8-.3-1.6-.7-2.3.4-.6.7-1.3.7-2.1 0-1.5-1-2.7-2.4-3-.4-.7-.9-1.2-1.6-1.5C15.8 3.4 14.2 2 12 2zm-1.5 4c.6 0 1 .4 1 1v3c0 .6-.4 1-1 1s-1-.4-1-1V7c0-.6.4-1 1-1zm3 0c.6 0 1 .4 1 1v3c0 .6-.4 1-1 1s-1-.4-1-1V7c0-.6.4-1 1-1zm-1.5 7c1.1 0 2.2.4 2.8 1.1.2.2.2.5 0 .7-.5.5-1.6.8-2.8.8s-2.3-.3-2.8-.8c-.2-.2-.2-.5 0-.7.6-.7 1.7-1.1 2.8-1.1z"/>
              </svg>
            {/if}
          </span>
          <div class="download-info">
            <span class="download-name">{platform.name}</span>
            <span class="download-note">{platform.note}</span>
          </div>
          <span class="download-arrow">↓</span>
        </a>
      {/each}
    </div>
    <p class="download-hint">
      After downloading, extract the archive and run the executable.
      The client will auto-update itself for future releases.
    </p>
  </section>

  <!-- Changelog -->
  {#if changelog.length > 0}
    <section class="section">
      <h2 class="section-title">Changelog</h2>
      <div class="changelog">
        {#each changelog as release}
          <div class="release">
            <div class="release-header">
              <span class="release-version">v{release.version}</span>
              {#if release.date}
                <span class="release-date">{release.date}</span>
              {/if}
            </div>
            <ul class="release-changes">
              {#each release.changes as change}
                <li class="change-item">
                  <span class="change-badge {typeBadge[change.type]?.cls || 'badge-feat'}">
                    {typeBadge[change.type]?.label || change.type.toUpperCase()}
                  </span>
                  <span class="change-text">{change.text}</span>
                </li>
              {/each}
            </ul>
          </div>
        {/each}
      </div>
    </section>
  {/if}
</div>

<style>
  .client-page {
    max-width: 900px;
    margin: 0 auto;
    padding: 24px;
  }

  /* Header */
  .page-header {
    margin-bottom: 32px;
  }

  .breadcrumbs {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-bottom: 8px;
  }

  .breadcrumbs a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumbs a:hover {
    text-decoration: underline;
  }

  .breadcrumbs .sep {
    margin: 0 6px;
    opacity: 0.5;
  }

  .page-header h1 {
    margin: 0 0 8px 0;
    font-size: 2rem;
    color: var(--text-color);
  }

  .subtitle {
    margin: 0;
    color: var(--text-muted);
    font-size: 1.1rem;
  }

  /* Sections */
  .section {
    margin-bottom: 40px;
  }

  .section-title {
    font-size: 1.3rem;
    font-weight: 600;
    color: var(--text-color);
    margin: 0 0 16px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color);
  }

  /* Features */
  .features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }

  .feature-card {
    padding: 20px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }

  .feature-title {
    margin: 0 0 8px 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .feature-desc {
    margin: 0;
    font-size: 0.875rem;
    color: var(--text-muted);
    line-height: 1.5;
  }

  /* Downloads */
  .version-tag {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--accent-color);
    margin-left: 8px;
  }

  .downloads-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 16px;
  }

  .download-card {
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

  .download-card:hover {
    border-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .download-icon {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
  }

  .download-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .download-name {
    font-weight: 600;
    font-size: 1rem;
  }

  .download-note {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .download-arrow {
    font-size: 1.5rem;
    color: var(--text-muted);
    flex-shrink: 0;
    transition: transform 0.2s ease;
  }

  .download-card:hover .download-arrow {
    transform: translateY(3px);
    color: var(--accent-color);
  }

  .download-hint {
    margin-top: 12px;
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  /* Changelog */
  .changelog {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .release-header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 8px;
  }

  .release-version {
    font-weight: 700;
    font-size: 1.1rem;
    color: var(--text-color);
  }

  .release-date {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .release-changes {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .change-item {
    display: flex;
    align-items: baseline;
    gap: 10px;
    font-size: 0.9rem;
    color: var(--text-color);
  }

  .change-badge {
    font-size: 0.65rem;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    flex-shrink: 0;
  }

  .badge-feat {
    background-color: var(--accent-color);
    color: #000;
  }

  .badge-fix {
    background-color: var(--warning-color);
    color: #000;
  }

  .badge-improve {
    background-color: var(--success-color);
    color: #fff;
  }

  .badge-remove {
    background-color: #ef4444;
    color: #fff;
  }

  /* Mobile */
  @media (max-width: 768px) {
    .client-page {
      padding: 16px;
    }

    .page-header h1 {
      font-size: 1.5rem;
    }

    .subtitle {
      font-size: 1rem;
    }

    .features-grid,
    .downloads-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
