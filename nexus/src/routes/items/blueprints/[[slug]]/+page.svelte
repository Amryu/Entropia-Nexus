<!--
  @component Blueprint Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: Level, Type, Book, Cost, Boosted, SiB, Profession, PED/h
  Article: Description, Construction (with markup calculator), Acquisition

  Legacy editConfig preserved for reference (see blueprints-legacy for full version):
  {
    constructor: () => ({
      Name: null,
      Properties: {
        Description: null, Type: null, Level: null, IsBoosted: false,
        MinimumCraftAmount: null, MaximumCraftAmount: null,
        Skill: { IsSiB: true, LearningIntervalStart: null, LearningIntervalEnd: null }
      },
      Book: { Name: null },
      Profession: { Name: null },
      Product: { Name: null },
      Materials: [],
      Drops: []
    }),
    dependencies: ['items', 'materials', 'blueprintbooks', 'professions', 'blueprints'],
    controls: [General group, Skill group, Materials list, Drops list]
  }
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { encodeURIComponentSafe, clampDecimals, getTypeLink, getItemLink } from '$lib/util';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';

  // Blueprint-specific component
  import Construction from './Construction.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/Acquisition.svelte';

  export let data;

  const craftDuration = 5; // seconds per craft cycle

  $: blueprint = data.object;
  $: user = data.session?.user;
  $: allItems = data.allItems || [];
  $: additional = data.additional || {};

  // Build navigation items
  $: navItems = allItems;

  // Navigation filters
  const navFilters = [
    {
      key: 'Properties.Type',
      label: 'Type',
      values: [
        { value: 'Weapon', label: 'Weapon' },
        { value: 'Armor', label: 'Armor' },
        { value: 'Tool', label: 'Tool' },
        { value: 'Vehicle', label: 'Vehicle' },
        { value: 'Textile', label: 'Textile' },
        { value: 'Furniture', label: 'Furniture' },
        { value: 'Attachment', label: 'Attachment' },
        { value: 'Enhancer', label: 'Enhancer' },
      ]
    }
  ];

  // Sidebar table columns for blueprints
  const navTableColumns = [
    {
      key: 'level',
      header: 'Lvl',
      width: '40px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.Level,
      format: (v) => v != null ? v : '-'
    },
    {
      key: 'type',
      header: 'Type',
      width: '70px',
      getValue: (item) => item.Properties?.Type || '-'
    }
  ];

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Blueprints', href: '/items/blueprints' },
    ...(blueprint ? [{ label: blueprint.Name }] : [])
  ];

  // SEO
  $: seoDescription = blueprint?.Properties?.Description ||
    `${blueprint?.Name || 'Blueprint'} - Level ${blueprint?.Properties?.Level || '?'} ${blueprint?.Properties?.Type || ''} blueprint in Entropia Universe.`;

  $: canonicalUrl = blueprint
    ? `https://entropianexus.com/items/blueprints/${encodeURIComponentSafe(blueprint.Name)}`
    : 'https://entropianexus.com/items/blueprints';

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    construction: true,
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-blueprint-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-blueprint-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== CALCULATOR FUNCTIONS ==========
  function getCost(bp) {
    if (!bp?.Materials?.length) return null;
    return bp.Materials.reduce((acc, mat) => {
      const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
      return acc + (matTT * (mat.Amount || 0));
    }, 0);
  }

  function getCyclePerHour(bp) {
    const cost = getCost(bp);
    if (cost === null || cost === 0) return null;
    return (3600 / craftDuration) * cost;
  }

  // Reactive calculations
  $: cost = getCost(blueprint);
  $: cyclePerHour = getCyclePerHour(blueprint);
</script>

<WikiSEO
  title={blueprint?.Name || 'Blueprints'}
  description={seoDescription}
  entityType="blueprint"
  entity={blueprint}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Blueprints"
  {breadcrumbs}
  entity={blueprint}
  entityType="Blueprint"
  basePath="/items/blueprints"
  {navItems}
  {navFilters}
  {navTableColumns}
  {user}
  editable={true}
>
  {#if blueprint}
    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <div class="icon-placeholder">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
              <rect x="3" y="3" width="18" height="18" rx="2" />
            </svg>
          </div>
          <div class="infobox-title">{blueprint.Name}</div>
          <div class="infobox-subtitle">
            <span class="type-badge">{blueprint.Properties?.Type || 'Blueprint'}</span>
            <span>Level {blueprint.Properties?.Level ?? '?'}</span>
          </div>
        </div>

        <!-- Primary Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Cost</span>
            <span class="stat-value">{cost !== null ? `${cost.toFixed(2)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Product</span>
            <span class="stat-value">
              {#if blueprint.Product?.Name}
                <a href={getItemLink(blueprint.Product)} class="tier1-link">{blueprint.Product.Name}</a>
              {:else}
                N/A
              {/if}
            </span>
          </div>
        </div>

        <!-- General Info -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">0.1kg</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Level</span>
            <span class="stat-value">{blueprint.Properties?.Level ?? 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Type</span>
            <span class="stat-value">{blueprint.Properties?.Type ?? 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Book</span>
            <span class="stat-value">{blueprint.Book?.Name ?? 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Product</span>
            <span class="stat-value">
              {#if blueprint.Product?.Name}
                <a href={getItemLink(blueprint.Product)} class="item-link">{blueprint.Product.Name}</a>
              {:else}
                N/A
              {/if}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Amount</span>
            <span class="stat-value">{blueprint.Properties?.MinimumCraftAmount ?? '?'} - {blueprint.Properties?.MaximumCraftAmount ?? '?'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Boosted</span>
            <span class="stat-value" class:highlight-yes={blueprint.Properties?.IsBoosted}>{blueprint.Properties?.IsBoosted ? 'Yes' : 'No'}</span>
          </div>
        </div>

        <!-- Skill Info -->
        <div class="stats-section">
          <h4 class="section-title">Skill</h4>
          <div class="stat-row">
            <span class="stat-label">SiB</span>
            <span class="stat-value" class:highlight-yes={blueprint.Properties?.Skill?.IsSiB}>{blueprint.Properties?.Skill?.IsSiB ? 'Yes' : 'No'}</span>
          </div>
          {#if blueprint.Profession?.Name}
            <div class="stat-row">
              <span class="stat-label">Profession</span>
              <span class="stat-value">
                <a href={getTypeLink(blueprint.Profession.Name, 'Profession')} class="profession-link">{blueprint.Profession.Name}</a>
              </span>
            </div>
            <div class="stat-row indent">
              <span class="stat-label">Level Range</span>
              <span class="stat-value">{blueprint.Properties?.Skill?.LearningIntervalStart ?? '?'} - {blueprint.Properties?.Skill?.LearningIntervalEnd ?? '?'}</span>
            </div>
          {/if}
        </div>
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">{blueprint.Name}</h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if blueprint.Properties?.Description}
            <div class="description-content">{blueprint.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {blueprint.Name} is a level {blueprint.Properties?.Level ?? '?'} {blueprint.Properties?.Type?.toLowerCase() || ''} blueprint.
            </div>
          {/if}
        </div>

        <!-- Construction Section -->
        {#if blueprint.Materials?.length > 0}
          <DataSection
            title="Construction"
            icon=""
            bind:expanded={panelStates.construction}
            subtitle="{blueprint.Materials.length} materials"
            on:toggle={savePanelStates}
          >
            <Construction {blueprint} />
          </DataSection>
        {/if}

        <!-- Acquisition Section -->
        {#if additional.acquisition}
          <DataSection
            title="Acquisition"
            icon=""
            bind:expanded={panelStates.acquisition}
            on:toggle={savePanelStates}
          >
            <Acquisition acquisition={additional.acquisition} />
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Blueprints</h2>
      <p>Select a blueprint from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .layout-a {
    position: relative;
    width: 100%;
  }

  /* Clearfix to ensure spacing after floated infobox */
  .layout-a::after {
    content: '';
    display: block;
    clear: both;
  }

  /* Floating infobox - Wikipedia style */
  .wiki-infobox-float {
    float: right;
    width: 300px;
    margin: 0 0 0 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 16px;
  }

  .infobox-header {
    text-align: center;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .icon-placeholder {
    width: 80px;
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--bg-color, var(--primary-color));
    border: 2px dashed var(--border-color, #555);
    border-radius: 8px;
    color: var(--text-muted, #999);
    margin: 0 auto 12px;
  }

  .infobox-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
  }

  .infobox-subtitle {
    font-size: 12px;
    color: var(--text-muted, #999);
    margin-top: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .type-badge {
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 4px;
    text-transform: uppercase;
  }

  /* Stats sections */
  .stats-section {
    padding: 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  .stats-section.tier-1 {
    background: linear-gradient(135deg, #7c5a4a 0%, #634939 100%);
    padding: 14px;
  }

  .stats-section.tier-1 .stat-row.primary {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    padding: 8px 12px;
    margin-bottom: 6px;
  }

  .stats-section.tier-1 .stat-row.primary:last-child {
    margin-bottom: 0;
  }

  .stats-section.tier-1 .stat-label {
    color: rgba(255, 255, 255, 0.9);
    font-size: 13px;
    text-transform: uppercase;
    font-weight: 500;
  }

  .stats-section.tier-1 .stat-value {
    color: #f4e8e8;
    font-size: 18px;
    font-weight: 700;
  }

  .stats-section.tier-1 .tier1-link {
    color: #f4e8e8;
    text-decoration: none;
    font-size: 14px;
    font-weight: 600;
  }

  .stats-section.tier-1 .tier1-link:hover {
    text-decoration: underline;
  }

  .section-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 10px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 4px 0;
    font-size: 13px;
  }

  .stat-row.indent {
    padding-left: 12px;
  }

  .stat-row.indent .stat-label {
    font-size: 11px;
  }

  .stat-label {
    color: var(--text-muted, #999);
  }

  .stat-value {
    font-weight: 500;
    color: var(--text-color);
    text-align: right;
  }

  .stat-value.highlight-yes {
    color: var(--success-color, #4ade80);
  }

  .profession-link,
  .item-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .profession-link:hover,
  .item-link:hover {
    text-decoration: underline;
  }

  .wiki-article {
    overflow: hidden; /* Contains floated infobox */
  }

  .article-title {
    font-size: 32px;
    font-weight: 600;
    margin: 0 0 16px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--accent-color, #4a9eff);
  }

  .description-panel {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
  }

  .description-content {
    font-size: 15px;
    line-height: 1.6;
    color: var(--text-color);
  }

  .description-content.placeholder {
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .no-selection {
    text-align: center;
    padding: 60px 20px;
  }

  .no-selection h2 {
    font-size: 28px;
    margin-bottom: 12px;
  }

  .no-selection p {
    color: var(--text-muted, #999);
    margin: 8px 0;
  }

  /* Tablet adjustments */
  @media (max-width: 1023px) {
    .wiki-infobox-float {
      width: 270px;
      margin-left: 16px;
      padding: 14px;
    }
  }

  /* Mobile adjustments */
  @media (max-width: 767px) {
    .layout-a {
      max-width: 100%;
    }

    .wiki-infobox-float {
      float: none;
      width: auto;
      margin: 0 0 16px 0;
    }

    /* Hide article title on mobile - redundant with infobox */
    .article-title {
      display: none;
    }

    .infobox-title {
      font-size: 16px;
    }

    .icon-placeholder {
      width: 60px;
      height: 60px;
    }

    .icon-placeholder svg {
      width: 36px;
      height: 36px;
    }
  }
</style>
