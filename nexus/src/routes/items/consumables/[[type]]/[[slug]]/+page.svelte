<!--
  @component Consumables Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Handles 2 subtypes: stimulants, capsules

  Legacy editConfig preserved in consumables-legacy/+page.svelte
  Key structure:
  - stimulants: Name, Properties (Description, Weight, Type, Economy), EffectsOnConsume[]
  - capsules: Name, Properties (Economy, MinProfessionLevel), Mob, Profession
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe, getTimeString, getTypeLink, groupBy } from '$lib/util';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/Acquisition.svelte';

  export let data;

  $: consumable = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};

  // For multi-type pages, data.items is an object keyed by type
  // When no type is selected, show all items from all types (with _type added for linking)
  $: allItems = (() => {
    if (!data.items) return [];
    if (additional.type && data.items[additional.type]) {
      return data.items[additional.type];
    }
    // No type selected - combine all items from all types, adding _type for correct linking
    const combined = [];
    for (const [type, items] of Object.entries(data.items)) {
      for (const item of items) {
        combined.push({ ...item, _type: type });
      }
    }
    return combined;
  })();

  // Type navigation buttons
  const typeButtons = [
    { label: 'Stimulants', title: 'Stimulants', type: 'stimulants' },
    { label: 'Capsules', title: 'Creature Control Capsules', type: 'capsules' }
  ];

  // Type name mapping
  function getTypeName(type) {
    switch (type) {
      case 'stimulants': return 'Stimulant';
      case 'capsules': return 'Creature Control Capsule';
      default: return 'Consumable';
    }
  }

  // Entity type for editing
  function getEntityType(type) {
    switch (type) {
      case 'stimulants': return 'Consumable';
      case 'capsules': return 'Capsule';
      default: return 'Consumable';
    }
  }

  // Build navigation items
  $: navItems = allItems;

  // Navigation filters - type buttons with deselection support
  $: navFilters = typeButtons.map(btn => ({
    label: btn.label,
    title: btn.title,
    type: btn.type,
    active: additional.type === btn.type,
    href: additional.type === btn.type ? '/items/consumables' : `/items/consumables/${btn.type}`
  }));

  // Type-specific sidebar table columns
  function getNavTableColumns(type) {
    switch (type) {
      case 'stimulants':
        return [
          { key: 'type', header: 'Type', width: '60px', filterPlaceholder: 'Pill', getValue: (item) => item.Properties?.Type, format: (v) => v || '-' },
          { key: 'value', header: 'TT', width: '55px', filterPlaceholder: '>0.1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 2, 4) : '-' }
        ];
      case 'capsules':
        return [
          { key: 'mob', header: 'Mob', width: '100px', filterPlaceholder: 'Atrox', getValue: (item) => item.Mob?.Name, format: (v) => v || '-' },
          { key: 'value', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 2, 4) : '-' }
        ];
      default:
        return [
          { key: 'category', header: 'Cat', width: '70px', filterPlaceholder: 'Stim', getValue: (item) => item._type === 'stimulants' ? 'Stim' : 'Cap', format: (v) => v || '-' },
          { key: 'value', header: 'TT', width: '55px', filterPlaceholder: '>0.1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 2, 4) : '-' }
        ];
    }
  }

  $: navTableColumns = getNavTableColumns(additional.type);

  // Custom href generator for items - handles _type property for "all items" view
  function getItemHref(item, basePath) {
    const type = item._type || additional.type;
    if (type) {
      return `/items/consumables/${type}/${encodeURIComponentSafe(item.Name)}`;
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Consumables', href: '/items/consumables' },
    ...(additional.type ? [{ label: getTypeName(additional.type) + 's', href: `/items/consumables/${additional.type}` }] : []),
    ...(consumable ? [{ label: consumable.Name }] : [])
  ];

  // SEO
  $: seoDescription = consumable?.Properties?.Description ||
    `${consumable?.Name || 'Consumable'} - ${getTypeName(additional.type)} in Entropia Universe.`;

  $: canonicalUrl = consumable
    ? `https://entropianexus.com/items/consumables/${additional.type}/${encodeURIComponentSafe(consumable.Name)}`
    : additional.type
    ? `https://entropianexus.com/items/consumables/${additional.type}`
    : 'https://entropianexus.com/items/consumables';

  // Check if item has effects (stimulants only)
  $: hasConsumeEffects = consumable?.EffectsOnConsume?.length > 0;

  // Format effects grouped by duration
  function getFormattedEffects(item) {
    if (!item?.EffectsOnConsume?.length) return null;
    const grouped = groupBy(item.EffectsOnConsume, x => x.Values.DurationSeconds);
    return Object.entries(grouped)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([duration, effects]) => ({
        duration: Number(duration),
        effects: effects.map(e => ({
          name: e.Name,
          strength: e.Values.Strength,
          unit: e.Values.Unit || ''
        }))
      }));
  }

  $: formattedEffects = getFormattedEffects(consumable);

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-consumable-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-consumable-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }
</script>

<WikiSEO
  title={consumable?.Name || `${getTypeName(additional.type)}s`}
  description={seoDescription}
  entityType={getEntityType(additional.type)}
  entity={consumable}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Consumables"
  {breadcrumbs}
  entity={consumable}
  entityType={getEntityType(additional.type)}
  basePath="/items/consumables/{additional.type || ''}"
  {navItems}
  {navFilters}
  {navTableColumns}
  navGetItemHref={getItemHref}
  {user}
  editable={true}
>
  {#if consumable}
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
          <div class="infobox-title">{consumable.Name}</div>
          <div class="infobox-subtitle">
            <span class="type-badge">{getTypeName(additional.type)}</span>
          </div>
        </div>

        <!-- Tier-1 Stats (type-specific primary stats) -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">TT Value</span>
            <span class="stat-value">{consumable.Properties?.Economy?.MaxTT != null ? `${clampDecimals(consumable.Properties.Economy.MaxTT, 2, 4)} PED` : 'N/A'}</span>
          </div>
          {#if additional.type === 'stimulants'}
            <div class="stat-row primary">
              <span class="stat-label">Type</span>
              <span class="stat-value">{consumable.Properties?.Type || 'N/A'}</span>
            </div>
          {:else if additional.type === 'capsules'}
            <div class="stat-row primary">
              <span class="stat-label">Creature</span>
              <span class="stat-value">{consumable.Mob?.Name || 'N/A'}</span>
            </div>
          {/if}
        </div>

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          {#if additional.type === 'stimulants'}
            <div class="stat-row">
              <span class="stat-label">Weight</span>
              <span class="stat-value">{consumable.Properties?.Weight != null ? `${clampDecimals(consumable.Properties.Weight, 1, 6)}kg` : 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Type</span>
              <span class="stat-value">{consumable.Properties?.Type || 'N/A'}</span>
            </div>
          {:else if additional.type === 'capsules'}
            <div class="stat-row">
              <span class="stat-label">Creature</span>
              <span class="stat-value">
                {#if consumable.Mob?.Name}
                  <a href={getTypeLink(consumable.Mob.Name, 'Mob')} class="entity-link">{consumable.Mob.Name}</a>
                {:else}
                  N/A
                {/if}
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Profession</span>
              <span class="stat-value">
                {#if consumable.Profession?.Name}
                  <a href={getTypeLink(consumable.Profession.Name, 'Profession')} class="entity-link">{consumable.Profession.Name}</a>
                {:else}
                  N/A
                {/if}
              </span>
            </div>
            {#if consumable.Properties?.MinProfessionLevel != null}
              <div class="stat-row">
                <span class="stat-label">Min. Level</span>
                <span class="stat-value">{consumable.Properties.MinProfessionLevel}</span>
              </div>
            {/if}
          {/if}
        </div>

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Value</span>
            <span class="stat-value">{consumable.Properties?.Economy?.MaxTT != null ? `${clampDecimals(consumable.Properties.Economy.MaxTT, 2, 8)} PED` : 'N/A'}</span>
          </div>
        </div>

        <!-- Effects on Consume (stimulants only) - placed after Economy -->
        {#if additional.type === 'stimulants' && hasConsumeEffects && formattedEffects}
          <div class="stats-section effects-section">
            <h4 class="section-title">Effects on Consume</h4>
            {#each formattedEffects as group}
              <div class="effect-group">
                {#if group.duration > 0}
                  <div class="effect-duration">Duration: {getTimeString(group.duration)}</div>
                {/if}
                {#each group.effects as effect}
                  <div class="stat-row">
                    <span class="stat-label">{effect.name}</span>
                    <span class="stat-value effect-value">{effect.strength}{effect.unit}</span>
                  </div>
                {/each}
              </div>
            {/each}
          </div>
        {/if}
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">{consumable.Name}</h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if consumable.Properties?.Description}
            <div class="description-content">{consumable.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {consumable.Name} is a {getTypeName(additional.type).toLowerCase()} used in Entropia Universe.
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
      <h2>{additional.type ? getTypeName(additional.type) + 's' : 'Consumables'}</h2>
      <p>Select a {additional.type ? getTypeName(additional.type).toLowerCase() : 'consumable'} from the list to view details.</p>
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

  .entity-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .entity-link:hover {
    text-decoration: underline;
  }

  /* Effects styling */
  .effects-section .effect-group {
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px dashed var(--border-color, #555);
  }

  .effects-section .effect-group:last-child {
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
  }

  .effect-duration {
    font-size: 11px;
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
    text-transform: uppercase;
    margin-bottom: 6px;
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
