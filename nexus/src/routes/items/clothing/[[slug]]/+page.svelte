<!--
  @component Clothing Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: All stats including effects
  Article: Description → Acquisition

  Legacy editConfig preserved in clothing-legacy/+page.svelte
  Key structure:
  - constructor: Name, Properties (Description, Weight, Type, Slot, Gender, Economy), Set, EffectsOnEquip[]
  - dependencies: ['effects', 'equipsets']
  - controls: General, Economy, Set (with Name and EffectsOnSetEquip), Equip Effects
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe, groupBy } from '$lib/util';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/Acquisition.svelte';

  export let data;

  $: clothing = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};
  $: allItems = data.allItems || [];

  // Build navigation items
  $: navItems = allItems;

  // Navigation filters - none for clothing (simple list)
  const navFilters = [];

  // Sidebar table columns for clothing
  const navTableColumns = [
    {
      key: 'slot',
      header: 'Slot',
      width: '70px',
      filterPlaceholder: 'Head',
      getValue: (item) => item.Properties?.Slot,
      format: (v) => v || '-'
    },
    {
      key: 'value',
      header: 'TT',
      width: '60px',
      filterPlaceholder: '>1',
      getValue: (item) => item.Properties?.Economy?.MaxTT,
      format: (v) => v != null ? clampDecimals(v, 2, 4) : '-'
    }
  ];

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Clothing', href: '/items/clothing' },
    ...(clothing ? [{ label: clothing.Name }] : [])
  ];

  // SEO
  $: seoDescription = clothing?.Properties?.Description ||
    `${clothing?.Name || 'Clothing'} - ${clothing?.Properties?.Type || ''} ${clothing?.Properties?.Slot || ''} clothing in Entropia Universe.`;

  $: canonicalUrl = clothing
    ? `https://entropianexus.com/items/clothing/${encodeURIComponentSafe(clothing.Name)}`
    : 'https://entropianexus.com/items/clothing';

  // Check if item has effects
  $: hasEquipEffects = clothing?.EffectsOnEquip?.length > 0;
  $: hasSetEffects = clothing?.Set?.EffectsOnSetEquip?.length > 0;

  // Get set effects grouped by piece count
  function getSetEffects(item) {
    if (!item?.Set?.EffectsOnSetEquip?.length) return null;
    const grouped = groupBy(item.Set.EffectsOnSetEquip, x => x.Values.MinSetPieces);
    return Object.entries(grouped)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([pieces, effects]) => ({
        pieces: Number(pieces),
        effects: effects.map(e => ({
          name: e.Name,
          strength: e.Values.Strength,
          unit: e.Values.Unit || ''
        }))
      }));
  }

  $: setEffects = getSetEffects(clothing);

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-clothing-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-clothing-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }
</script>

<WikiSEO
  title={clothing?.Name || 'Clothing'}
  description={seoDescription}
  entityType="Clothing"
  entity={clothing}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Clothing"
  {breadcrumbs}
  entity={clothing}
  entityType="Clothing"
  basePath="/items/clothing"
  {navItems}
  {navFilters}
  {navTableColumns}
  {user}
  editable={true}
>
  {#if clothing}
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
          <div class="infobox-title">{clothing.Name}</div>
          <div class="infobox-subtitle">
            <span class="type-badge">{clothing.Properties?.Type || 'Clothing'}</span>
            {#if clothing.Properties?.Slot}
              <span>{clothing.Properties.Slot}</span>
            {/if}
          </div>
        </div>

        <!-- Primary Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">TT Value</span>
            <span class="stat-value">{clothing.Properties?.Economy?.MaxTT != null ? `${clampDecimals(clothing.Properties.Economy.MaxTT, 2, 4)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Weight</span>
            <span class="stat-value">{clothing.Properties?.Weight != null ? `${clampDecimals(clothing.Properties.Weight, 1, 6)}kg` : 'N/A'}</span>
          </div>
        </div>

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Type</span>
            <span class="stat-value">{clothing.Properties?.Type || 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Slot</span>
            <span class="stat-value">{clothing.Properties?.Slot || 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Gender</span>
            <span class="stat-value">{clothing.Properties?.Gender || 'N/A'}</span>
          </div>
        </div>

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Max TT</span>
            <span class="stat-value">{clothing.Properties?.Economy?.MaxTT != null ? `${clampDecimals(clothing.Properties.Economy.MaxTT, 2, 8)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min TT</span>
            <span class="stat-value">{clothing.Properties?.Economy?.MinTT != null ? `${clampDecimals(clothing.Properties.Economy.MinTT, 2, 8)} PED` : '0.00 PED'}</span>
          </div>
        </div>

        <!-- Equip Effects -->
        {#if hasEquipEffects}
          <div class="stats-section effects-section">
            <h4 class="section-title">Effects on Equip</h4>
            {#each clothing.EffectsOnEquip.sort((a,b) => a.Name.localeCompare(b.Name)) as effect}
              <div class="stat-row">
                <span class="stat-label">{effect.Name}</span>
                <span class="stat-value effect-value">{effect.Values.Strength}{effect.Values.Unit}</span>
              </div>
            {/each}
          </div>
        {/if}

        <!-- Set Effects -->
        {#if hasSetEffects && setEffects}
          <div class="stats-section set-effects">
            <h4 class="section-title">Set: {clothing.Set.Name}</h4>
            {#each setEffects as group}
              <div class="effect-group">
                <div class="effect-pieces">{group.pieces} Pieces</div>
                {#each group.effects as effect}
                  <div class="effect-row">
                    <span class="effect-value">+{effect.strength}{effect.unit}</span>
                    <span class="effect-name">{effect.name}</span>
                  </div>
                {/each}
              </div>
            {/each}
          </div>
        {/if}
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">{clothing.Name}</h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if clothing.Properties?.Description}
            <div class="description-content">{clothing.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {clothing.Name} is a {clothing.Properties?.Type?.toLowerCase() || ''} clothing item worn on the {clothing.Properties?.Slot?.toLowerCase() || 'body'}.
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
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Clothing</h2>
      <p>Select a clothing item from the list to view details.</p>
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

  .stat-label {
    color: var(--text-muted, #999);
  }

  .stat-value {
    font-weight: 500;
    color: var(--text-color);
  }

  .stat-value.effect-value {
    color: var(--accent-color, #4a9eff);
  }

  /* Set Effects styling */
  .set-effects .effect-group {
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px dashed var(--border-color, #555);
  }

  .set-effects .effect-group:last-child {
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
  }

  .effect-pieces {
    font-size: 11px;
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
    text-transform: uppercase;
    margin-bottom: 6px;
  }

  .effect-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 2px 0;
    font-size: 12px;
  }

  .effect-row .effect-value {
    color: var(--success-color, #4ade80);
    font-weight: 600;
    min-width: 50px;
  }

  .effect-row .effect-name {
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
      width: 280px;
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
