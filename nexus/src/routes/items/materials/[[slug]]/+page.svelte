<!--
  @component Material Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: Weight, Value
  Article: Description, Acquisition, Usage

  Legacy editConfig preserved for reference:
  {
    constructor: () => ({
      Name: '',
      Properties: {
        Description: null,
        Weight: null,
        Economy: { MaxTT: null }
      },
      RefiningRecipes: []
    }),
    dependencies: ['materials'],
    controls: [
      { label: 'General', type: 'group', controls: [
        { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
        { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
        { label: 'Weight', type: 'number', '_get': x => x.Properties.Weight, '_set': (x, v) => x.Properties.Weight = v }
      ]},
      { label: 'Economy', type: 'group', controls: [
        { label: 'Value', type: 'number', '_get': x => x.Properties.Economy.MaxTT, '_set': (x, v) => x.Properties.Economy.MaxTT = v }
      ]},
      { label: 'Refining Recipes', type: 'list', config: {
        constructor: () => ({ Amount: 1, Ingredients: [] }),
        dependencies: ['items'],
        controls: [
          { label: 'Product Amount', type: 'number', step: '1', min: '1', '_get': x => x.Amount, '_set': (x, v) => x.Amount = v },
          { label: 'Ingredients', type: 'list', config: {
            constructor: () => ({ Item: { Name: null }, Amount: 1 }),
            controls: [
              { label: 'Item', type: 'input-validator', validator: (v, d) => d.items.find(y => y.Name === v), '_get': (x, d) => x.Item?.Name ?? '', '_set': (x, v, d) => x.Item.Name = v },
              { label: 'Ingredient Amount', type: 'number', step: '1', min: '1', '_get': x => x.Amount, '_set': (x, v) => x.Amount = v }
            ]
          }, '_get': x => x.Ingredients, '_set': (x, v) => x.Ingredients = v }
        ]
      }, '_get': x => x.RefiningRecipes || [], '_set': (x, v) => x.RefiningRecipes = v }
    ]
  }
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { encodeURIComponentSafe, clampDecimals } from '$lib/util';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/Acquisition.svelte';
  import Usage from '$lib/components/Usage.svelte';

  export let data;

  $: material = data.object;
  $: user = data.session?.user;
  $: allItems = data.allItems || [];
  $: additional = data.additional || {};

  // Build navigation items
  $: navItems = allItems;

  // Navigation filters - none for materials (simple list)
  const navFilters = [];

  // Sidebar table columns for materials
  const navTableColumns = [
    {
      key: 'value',
      header: 'Value',
      width: '70px',
      filterPlaceholder: '>0.01',
      getValue: (item) => item.Properties?.Economy?.MaxTT,
      format: (v) => v != null ? clampDecimals(v, 2, 4) : '-'
    },
    {
      key: 'weight',
      header: 'Wt',
      width: '50px',
      filterPlaceholder: '<1',
      getValue: (item) => item.Properties?.Weight,
      format: (v) => v != null ? clampDecimals(v, 1, 3) : '-'
    }
  ];

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Materials', href: '/items/materials' },
    ...(material ? [{ label: material.Name }] : [])
  ];

  // SEO
  $: seoDescription = material?.Properties?.Description ||
    `${material?.Name || 'Material'} - crafting material in Entropia Universe.`;

  $: canonicalUrl = material
    ? `https://entropianexus.com/items/materials/${encodeURIComponentSafe(material.Name)}`
    : 'https://entropianexus.com/items/materials';

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    acquisition: true,
    usage: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-material-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-material-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== VALUE FORMATTERS ==========
  function formatWeight(weight) {
    if (weight == null) return 'N/A';
    return `${clampDecimals(weight, 1, 6)}kg`;
  }

  function formatValue(value) {
    if (value == null) return 'N/A';
    return `${clampDecimals(value, 2, 8)} PED`;
  }
</script>

<WikiSEO
  title={material?.Name || 'Materials'}
  description={seoDescription}
  entityType="material"
  entity={material}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Materials"
  {breadcrumbs}
  entity={material}
  entityType="Material"
  basePath="/items/materials"
  {navItems}
  {navFilters}
  {navTableColumns}
  {user}
  editable={true}
>
  {#if material}
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
          <div class="infobox-title">{material.Name}</div>
          <div class="infobox-subtitle">
            <span class="type-badge">Material</span>
          </div>
        </div>

        <!-- Primary Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Value</span>
            <span class="stat-value">{formatValue(material.Properties?.Economy?.MaxTT)}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Weight</span>
            <span class="stat-value">{formatWeight(material.Properties?.Weight)}</span>
          </div>
        </div>
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">{material.Name}</h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if material.Properties?.Description}
            <div class="description-content">{material.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {material.Name} is a material used in crafting and other activities.
            </div>
          {/if}
        </div>

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

        <!-- Usage Section -->
        {#if additional.usage}
          <DataSection
            title="Usage"
            icon=""
            bind:expanded={panelStates.usage}
            on:toggle={savePanelStates}
          >
            <Usage item={material} usage={additional.usage} />
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Materials</h2>
      <p>Select a material from the list to view details.</p>
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
    width: 280px;
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
    background: linear-gradient(135deg, #4a7c59 0%, #3a6349 100%);
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
    color: #e8f4e8;
    font-size: 18px;
    font-weight: 700;
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 4px 0;
    font-size: 13px;
  }

  .stat-label {
    color: var(--text-muted, #999);
  }

  .stat-value {
    font-weight: 500;
    color: var(--text-color);
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
      width: 260px;
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
