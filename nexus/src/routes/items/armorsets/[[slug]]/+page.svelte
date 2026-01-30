<!--
  @component Armor Set Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: Defense stats (9 types + total), Economy, Set Effects, Total Absorption
  Article: Description, Set Pieces, Tiering, Acquisition

  Legacy editConfig preserved in armorsets-legacy/+page.svelte
  Key structure:
  - constructor: Name, Properties (Description, Weight, Economy, Defense), Armors[], EffectsOnSetEquip[], Tiers[]
  - dependencies: ['effects']
  - controls: General, Economy, Defense (9 types), Armors (7 slots with gender support), Set Effects, Tiering
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { encodeURIComponentSafe, clampDecimals, hasItemTag, groupBy } from '$lib/util';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';

  // ArmorSet-specific component
  import ArmorSetPieces from './ArmorSetPieces.svelte';

  // Legacy components for data display
  import Tiering from '$lib/components/Tiering.svelte';
  import Acquisition from '$lib/components/Acquisition.svelte';

  export let data;

  $: armorSet = data.object;
  $: user = data.session?.user;
  $: allItems = data.allItems || [];
  $: additional = data.additional || {};

  // Build navigation items
  $: navItems = allItems;

  // Navigation filters - none for armor sets
  const navFilters = [];

  // Sidebar table columns for armor sets
  const navTableColumns = [
    {
      key: 'defense',
      header: 'Def',
      width: '55px',
      filterPlaceholder: '>50',
      getValue: (item) => getTotalDefense(item),
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    {
      key: 'absorption',
      header: 'Abs',
      width: '60px',
      filterPlaceholder: '>1000',
      getValue: (item) => getTotalAbsorption(item),
      format: (v) => v != null ? Math.round(v) : '-'
    }
  ];

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Armor Sets', href: '/items/armorsets' },
    ...(armorSet ? [{ label: armorSet.Name }] : [])
  ];

  // SEO
  $: seoDescription = armorSet?.Properties?.Description ||
    `${armorSet?.Name || 'Armor Set'} - armor set with ${getTotalDefense(armorSet)?.toFixed(1) || '?'} total defense in Entropia Universe.`;

  $: canonicalUrl = armorSet
    ? `https://entropianexus.com/items/armorsets/${encodeURIComponentSafe(armorSet.Name)}`
    : 'https://entropianexus.com/items/armorsets';

  // Check if armor set is tierable
  $: isTierable = armorSet && !hasItemTag(armorSet.Name, 'L');

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    pieces: true,
    tiering: true,
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-armorset-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-armorset-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== CALCULATOR FUNCTIONS ==========
  function getTotalDefense(item) {
    if (!item?.Properties?.Defense) return null;
    const d = item.Properties.Defense;
    return (d.Impact ?? 0) + (d.Cut ?? 0) + (d.Stab ?? 0) + (d.Penetration ?? 0) +
           (d.Shrapnel ?? 0) + (d.Burn ?? 0) + (d.Cold ?? 0) + (d.Acid ?? 0) + (d.Electric ?? 0);
  }

  function getMaxArmorDecay(item) {
    const totalDef = getTotalDefense(item);
    if (!item?.Properties?.Economy?.Durability || !totalDef) return null;
    return totalDef * ((100000 - item.Properties.Economy.Durability) / 100000) * 0.05;
  }

  function getTotalAbsorption(item) {
    const maxDecay = getMaxArmorDecay(item);
    const totalDef = getTotalDefense(item);
    if (!item?.Properties?.Economy?.MaxTT || !maxDecay) return null;
    return totalDef * ((item.Properties.Economy.MaxTT - (item.Properties.Economy.MinTT ?? 0)) / (maxDecay / 100));
  }

  // Get set effects grouped by piece count
  function getSetEffects(item) {
    if (!item?.EffectsOnSetEquip?.length) return null;
    const grouped = groupBy(item.EffectsOnSetEquip, x => x.Values.MinSetPieces);
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

  // Reactive calculations
  $: totalDefense = getTotalDefense(armorSet);
  $: maxDecay = getMaxArmorDecay(armorSet);
  $: totalAbsorption = getTotalAbsorption(armorSet);
  $: setEffects = getSetEffects(armorSet);
  $: pieceCount = armorSet?.Armors?.flat().filter(x => x?.Properties?.Gender === 'Both' || x?.Properties?.Gender === 'Male').length ?? 0;

  // Damage types for display
  const damageTypes = ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'];
</script>

<WikiSEO
  title={armorSet?.Name || 'Armor Sets'}
  description={seoDescription}
  entityType="armorset"
  entity={armorSet}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Armor Sets"
  {breadcrumbs}
  entity={armorSet}
  entityType="ArmorSet"
  basePath="/items/armorsets"
  {navItems}
  {navFilters}
  {navTableColumns}
  {user}
  editable={true}
>
  {#if armorSet}
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
          <div class="infobox-title">{armorSet.Name}</div>
          <div class="infobox-subtitle">
            <span class="type-badge">Armor Set</span>
            <span>{pieceCount} pieces</span>
          </div>
        </div>

        <!-- Primary Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Total Defense</span>
            <span class="stat-value">{totalDefense?.toFixed(1) ?? 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Absorption</span>
            <span class="stat-value">{totalAbsorption?.toFixed(0) ?? 'N/A'} HP</span>
          </div>
        </div>

        <!-- Defense Breakdown -->
        <div class="stats-section">
          <h4 class="section-title">Defense</h4>
          {#each damageTypes as type}
            {@const value = armorSet.Properties?.Defense?.[type]}
            <div class="stat-row">
              <span class="stat-label">{type}</span>
              <span class="stat-value">{value?.toFixed(1) ?? 'N/A'}</span>
            </div>
          {/each}
        </div>

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Max TT</span>
            <span class="stat-value">{armorSet.Properties?.Economy?.MaxTT != null ? `${clampDecimals(armorSet.Properties.Economy.MaxTT, 2, 8)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min TT</span>
            <span class="stat-value">{armorSet.Properties?.Economy?.MinTT != null ? `${clampDecimals(armorSet.Properties.Economy.MinTT, 2, 8)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Durability</span>
            <span class="stat-value">{armorSet.Properties?.Economy?.Durability ?? 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Max Decay</span>
            <span class="stat-value">{maxDecay?.toFixed(4) ?? 'N/A'} PEC</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">{armorSet.Properties?.Weight != null ? `${clampDecimals(armorSet.Properties.Weight, 1, 6)}kg` : 'N/A'}</span>
          </div>
        </div>

        <!-- Set Effects -->
        {#if setEffects?.length > 0}
          <div class="stats-section set-effects">
            <h4 class="section-title">Set Effects</h4>
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
        <h1 class="article-title">{armorSet.Name}</h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if armorSet.Properties?.Description}
            <div class="description-content">{armorSet.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {armorSet.Name} is an armor set providing {totalDefense?.toFixed(1) || '?'} total defense.
            </div>
          {/if}
        </div>

        <!-- Set Pieces Section -->
        {#if armorSet.Armors?.length > 0}
          <DataSection
            title="Set Pieces"
            icon=""
            bind:expanded={panelStates.pieces}
            subtitle="{pieceCount} pieces"
            on:toggle={savePanelStates}
          >
            <ArmorSetPieces {armorSet} />
          </DataSection>
        {/if}

        <!-- Tiering Section -->
        {#if isTierable}
          <DataSection
            title="Tiering"
            icon=""
            bind:expanded={panelStates.tiering}
            subtitle="{additional.tierInfo?.length || 0} tiers"
            on:toggle={savePanelStates}
          >
            <Tiering tieringInfo={additional.tierInfo} setPieceCount={pieceCount} />
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
      <h2>Armor Sets</h2>
      <p>Select an armor set from the list to view details.</p>
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
    background: linear-gradient(135deg, #5a4a7c 0%, #493963 100%);
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
    color: #e8e8f4;
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

  /* Set Effects Styling */
  .set-effects {
    padding: 12px;
  }

  .effect-group {
    margin-bottom: 12px;
  }

  .effect-group:last-child {
    margin-bottom: 0;
  }

  .effect-pieces {
    font-size: 11px;
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
    text-transform: uppercase;
    margin-bottom: 4px;
  }

  .effect-row {
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 2px 0;
    font-size: 12px;
  }

  .effect-value {
    color: var(--success-color, #4ade80);
    font-weight: 600;
    min-width: 50px;
  }

  .effect-name {
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
