<!--
  @component Furnishings Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Handles 4 subtypes: furniture, decorations, storagecontainers, signs

  Legacy editConfig preserved in furnishings-legacy/+page.svelte
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe } from '$lib/util';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/Acquisition.svelte';

  export let data;

  $: furnishing = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};

  // For multi-type pages, data.items is an object keyed by type
  $: allItems = (() => {
    if (!data.items) return [];
    if (additional.type && data.items[additional.type]) {
      return data.items[additional.type];
    }
    // No type selected - combine all items from all types
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
    { label: 'Furniture', title: 'Furniture', type: 'furniture' },
    { label: 'Decor', title: 'Decorations', type: 'decorations' },
    { label: 'Storage', title: 'Storage Containers', type: 'storagecontainers' },
    { label: 'Signs', title: 'Signs', type: 'signs' }
  ];

  // Type name mapping
  function getTypeName(type) {
    switch (type) {
      case 'furniture': return 'Furniture';
      case 'decorations': return 'Decoration';
      case 'storagecontainers': return 'Storage Container';
      case 'signs': return 'Sign';
      default: return 'Furnishing';
    }
  }

  // Entity type for editing
  function getEntityType(type) {
    switch (type) {
      case 'furniture': return 'Furniture';
      case 'decorations': return 'Decoration';
      case 'storagecontainers': return 'StorageContainer';
      case 'signs': return 'Sign';
      default: return null;
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
    href: additional.type === btn.type ? '/items/furnishings' : `/items/furnishings/${btn.type}`
  }));

  // Type-specific sidebar table columns
  function getNavTableColumns(type) {
    switch (type) {
      case 'furniture':
      case 'decorations':
        return [
          { key: 'type', header: 'Type', width: '60px', filterPlaceholder: 'Chair', getValue: (item) => item.Properties?.Type, format: (v) => v ? v.slice(0, 6) : '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      case 'storagecontainers':
        return [
          { key: 'cap', header: 'Items', width: '55px', filterPlaceholder: '>50', getValue: (item) => item.Properties?.ItemCapacity, format: (v) => v ?? '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      case 'signs':
        return [
          { key: 'ratio', header: 'Ratio', width: '55px', filterPlaceholder: '16:9', getValue: (item) => item.Properties?.Display?.AspectRatio, format: (v) => v || '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      default:
        return [
          { key: 'cat', header: 'Cat', width: '60px', filterPlaceholder: 'Furn', getValue: (item) => getTypeName(item._type || additional.type).slice(0, 6), format: (v) => v || '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
    }
  }

  $: navTableColumns = getNavTableColumns(additional.type);

  // Custom href generator for items
  function getItemHref(item, basePath) {
    const type = item._type || additional.type;
    if (type) {
      return `/items/furnishings/${type}/${encodeURIComponentSafe(item.Name)}`;
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Furnishings', href: '/items/furnishings' },
    ...(additional.type ? [{ label: getTypeName(additional.type) + (additional.type !== 'furniture' ? 's' : ''), href: `/items/furnishings/${additional.type}` }] : []),
    ...(furnishing ? [{ label: furnishing.Name }] : [])
  ];

  // SEO
  $: seoDescription = furnishing?.Properties?.Description ||
    `${furnishing?.Name || 'Furnishing'} - ${getTypeName(additional.type)} in Entropia Universe.`;

  $: canonicalUrl = furnishing
    ? `https://entropianexus.com/items/furnishings/${additional.type}/${encodeURIComponentSafe(furnishing.Name)}`
    : additional.type
    ? `https://entropianexus.com/items/furnishings/${additional.type}`
    : 'https://entropianexus.com/items/furnishings';

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-furnishing-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {}
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-furnishing-panels', JSON.stringify(panelStates));
    } catch (e) {}
  }
</script>

<WikiSEO
  title={furnishing?.Name || `${getTypeName(additional.type)}s`}
  description={seoDescription}
  entityType={getEntityType(additional.type)}
  entity={furnishing}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Furnishings"
  {breadcrumbs}
  entity={furnishing}
  entityType={getEntityType(additional.type)}
  basePath="/items/furnishings/{additional.type || ''}"
  {navItems}
  {navFilters}
  {navTableColumns}
  navGetItemHref={getItemHref}
  {user}
  editable={true}
>
  {#if furnishing}
    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <div class="icon-placeholder">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
              <rect x="4" y="8" width="16" height="10" rx="1" />
              <path d="M6 8V6a2 2 0 012-2h8a2 2 0 012 2v2" />
              <line x1="4" y1="18" x2="4" y2="20" />
              <line x1="20" y1="18" x2="20" y2="20" />
            </svg>
          </div>
          <div class="infobox-title">{furnishing.Name}</div>
          <div class="infobox-subtitle">
            <span class="type-badge">{getTypeName(additional.type)}</span>
          </div>
        </div>

        <!-- Tier-1 Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">TT Value</span>
            <span class="stat-value">{furnishing.Properties?.Economy?.MaxTT != null ? `${clampDecimals(furnishing.Properties.Economy.MaxTT, 2, 4)} PED` : 'N/A'}</span>
          </div>

          {#if additional.type === 'storagecontainers'}
            <div class="stat-row primary">
              <span class="stat-label">Item Capacity</span>
              <span class="stat-value">{furnishing.Properties?.ItemCapacity ?? 'N/A'}</span>
            </div>
          {:else if additional.type === 'signs'}
            <div class="stat-row primary">
              <span class="stat-label">Aspect Ratio</span>
              <span class="stat-value">{furnishing.Properties?.Display?.AspectRatio ?? 'N/A'}</span>
            </div>
          {:else if furnishing.Properties?.Type}
            <div class="stat-row primary">
              <span class="stat-label">Type</span>
              <span class="stat-value">{furnishing.Properties.Type}</span>
            </div>
          {/if}
        </div>

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">{furnishing.Properties?.Weight != null ? `${clampDecimals(furnishing.Properties.Weight, 1, 6)}kg` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Category</span>
            <span class="stat-value">{getTypeName(additional.type)}</span>
          </div>
          {#if (additional.type === 'furniture' || additional.type === 'decorations') && furnishing.Properties?.Type}
            <div class="stat-row">
              <span class="stat-label">Type</span>
              <span class="stat-value">{furnishing.Properties.Type}</span>
            </div>
          {/if}
          {#if additional.type === 'signs'}
            <div class="stat-row">
              <span class="stat-label">Item Points</span>
              <span class="stat-value">{furnishing.Properties?.ItemPoints ?? 'N/A'}</span>
            </div>
          {/if}
          {#if additional.type === 'storagecontainers'}
            <div class="stat-row">
              <span class="stat-label">Item Capacity</span>
              <span class="stat-value">{furnishing.Properties?.ItemCapacity ?? 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Weight Capacity</span>
              <span class="stat-value">{furnishing.Properties?.WeightCapacity != null ? `${clampDecimals(furnishing.Properties.WeightCapacity, 1, 6)}kg` : 'N/A'}</span>
            </div>
          {/if}
        </div>

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Max. TT</span>
            <span class="stat-value">{furnishing.Properties?.Economy?.MaxTT != null ? `${clampDecimals(furnishing.Properties.Economy.MaxTT, 2, 8)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min. TT</span>
            <span class="stat-value">{furnishing.Properties?.Economy?.MinTT != null ? `${clampDecimals(furnishing.Properties.Economy.MinTT, 2, 8)} PED` : 'N/A'}</span>
          </div>
          {#if additional.type === 'signs'}
            <div class="stat-row">
              <span class="stat-label">Cost</span>
              <span class="stat-value">{furnishing.Properties?.Economy?.Cost != null ? `${furnishing.Properties.Economy.Cost.toFixed(2)} PEC` : 'N/A'}</span>
            </div>
          {/if}
        </div>

        <!-- Display Stats (signs only) -->
        {#if additional.type === 'signs'}
          <div class="stats-section">
            <h4 class="section-title">Display</h4>
            <div class="stat-row">
              <span class="stat-label">Aspect Ratio</span>
              <span class="stat-value">{furnishing.Properties?.Display?.AspectRatio ?? 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Local Content</span>
              <span class="stat-value feature-flag" class:yes={furnishing.Properties?.Display?.CanShowLocalContent}>{furnishing.Properties?.Display?.CanShowLocalContent ? 'Yes' : 'No'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Images & Text</span>
              <span class="stat-value feature-flag" class:yes={furnishing.Properties?.Display?.CanShowImagesAndText}>{furnishing.Properties?.Display?.CanShowImagesAndText ? 'Yes' : 'No'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Effects</span>
              <span class="stat-value feature-flag" class:yes={furnishing.Properties?.Display?.CanShowEffects}>{furnishing.Properties?.Display?.CanShowEffects ? 'Yes' : 'No'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Multimedia</span>
              <span class="stat-value feature-flag" class:yes={furnishing.Properties?.Display?.CanShowMultimedia}>{furnishing.Properties?.Display?.CanShowMultimedia ? 'Yes' : 'No'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Participant Content</span>
              <span class="stat-value feature-flag" class:yes={furnishing.Properties?.Display?.CanShowParticipantContent}>{furnishing.Properties?.Display?.CanShowParticipantContent ? 'Yes' : 'No'}</span>
            </div>
          </div>
        {/if}
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">{furnishing.Name}</h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if furnishing.Properties?.Description}
            <div class="description-content">{furnishing.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {furnishing.Name} is a {getTypeName(additional.type).toLowerCase()} in Entropia Universe.
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
      <h2>{additional.type ? getTypeName(additional.type) + (additional.type !== 'furniture' ? 's' : '') : 'Furnishings'}</h2>
      <p>Select a {additional.type ? getTypeName(additional.type).toLowerCase() : 'furnishing'} from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .layout-a {
    position: relative;
    width: 100%;
  }

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

  .stat-value.feature-flag {
    color: var(--text-muted, #999);
  }

  .stat-value.feature-flag.yes {
    color: #4ade80;
    font-weight: 600;
  }

  .wiki-article {
    overflow: hidden;
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
