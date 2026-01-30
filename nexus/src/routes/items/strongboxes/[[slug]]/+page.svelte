<!--
  @component Strongboxes Wiki Page
  Wikipedia-style layout with floating infobox on the right side.

  Legacy editConfig preserved in strongboxes-legacy/+page.svelte
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe, getItemLink } from '$lib/util';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/Acquisition.svelte';

  export let data;

  $: strongbox = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};

  // All strongboxes for navigation
  $: allItems = data.items || [];

  // Build navigation items
  $: navItems = allItems;

  // No filters for strongboxes
  $: navFilters = [];

  // Sidebar table columns
  $: navTableColumns = [
    { key: 'weight', header: 'Weight', width: '60px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Weight, format: (v) => v != null ? `${v.toFixed(1)}kg` : '-' },
    { key: 'tt', header: 'TT', width: '60px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? v.toFixed(2) : '-' }
  ];

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Strongboxes', href: '/items/strongboxes' },
    ...(strongbox ? [{ label: strongbox.Name }] : [])
  ];

  // SEO
  $: seoDescription = strongbox?.Properties?.Description ||
    `${strongbox?.Name || 'Strongbox'} - Strongbox container in Entropia Universe.`;

  $: canonicalUrl = strongbox
    ? `https://entropianexus.com/items/strongboxes/${encodeURIComponentSafe(strongbox.Name)}`
    : 'https://entropianexus.com/items/strongboxes';

  // Check for loots
  $: hasLoots = strongbox?.Loots?.length > 0;

  // Rarity order for sorting
  const rarityOrder = {
    'Common': 0,
    'Uncommon': 1,
    'Rare': 2,
    'Epic': 3,
    'Supreme': 4,
    'Legendary': 5,
    'Mythical': 6
  };

  // Sort loots by rarity
  function sortByRarity(a, b) {
    const aOrder = rarityOrder[a.Rarity] ?? 99;
    const bOrder = rarityOrder[b.Rarity] ?? 99;
    return aOrder - bOrder;
  }

  // Rarity color mapping
  function getRarityColor(rarity) {
    switch (rarity) {
      case 'Common': return '#9ca3af';
      case 'Uncommon': return '#22c55e';
      case 'Rare': return '#3b82f6';
      case 'Epic': return '#a855f7';
      case 'Supreme': return '#f97316';
      case 'Legendary': return '#f59e0b';
      case 'Mythical': return '#ef4444';
      default: return '#9ca3af';
    }
  }

  // Sorted loots
  $: sortedLoots = hasLoots ? [...strongbox.Loots].sort(sortByRarity) : [];

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    loots: true,
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-strongbox-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {}
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-strongbox-panels', JSON.stringify(panelStates));
    } catch (e) {}
  }
</script>

<WikiSEO
  title={strongbox?.Name || 'Strongboxes'}
  description={seoDescription}
  entityType="Strongbox"
  entity={strongbox}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Strongboxes"
  {breadcrumbs}
  entity={strongbox}
  entityType="Strongbox"
  basePath="/items/strongboxes"
  {navItems}
  {navFilters}
  {navTableColumns}
  {user}
  editable={true}
>
  {#if strongbox}
    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <div class="icon-placeholder">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
              <rect x="3" y="6" width="18" height="14" rx="2" />
              <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              <circle cx="12" cy="13" r="2" />
            </svg>
          </div>
          <div class="infobox-title">{strongbox.Name}</div>
          <div class="infobox-subtitle">
            <span class="type-badge">Strongbox</span>
          </div>
        </div>

        <!-- Tier-1 Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">TT Value</span>
            <span class="stat-value">{strongbox.Properties?.Economy?.MaxTT != null ? `${clampDecimals(strongbox.Properties.Economy.MaxTT, 2, 8)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Weight</span>
            <span class="stat-value">{strongbox.Properties?.Weight != null ? `${clampDecimals(strongbox.Properties.Weight, 1, 6)}kg` : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Loots</span>
            <span class="stat-value">{strongbox.Loots?.length || 0} items</span>
          </div>
        </div>

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">{strongbox.Properties?.Weight != null ? `${clampDecimals(strongbox.Properties.Weight, 1, 6)}kg` : 'N/A'}</span>
          </div>
        </div>

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">TT Value</span>
            <span class="stat-value">{strongbox.Properties?.Economy?.MaxTT != null ? `${clampDecimals(strongbox.Properties.Economy.MaxTT, 2, 8)} PED` : 'N/A'}</span>
          </div>
        </div>
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">{strongbox.Name}</h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if strongbox.Properties?.Description}
            <div class="description-content">{strongbox.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {strongbox.Name} is a strongbox that can be obtained and opened in Entropia Universe.
            </div>
          {/if}
        </div>

        <!-- Loots Section -->
        {#if hasLoots}
          <DataSection
            title="Possible Loots"
            icon=""
            bind:expanded={panelStates.loots}
            on:toggle={savePanelStates}
          >
            <div class="loots-table-wrapper">
              <table class="loots-table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>Rarity</th>
                    <th>Available From</th>
                    <th>Available Until</th>
                  </tr>
                </thead>
                <tbody>
                  {#each sortedLoots as loot}
                    <tr>
                      <td class="item-name">
                        {#if loot.Item?.Name}
                          <a href={getItemLink(loot.Item)} class="item-link">{loot.Item.Name}</a>
                        {:else}
                          <span class="na-text">Unknown Item</span>
                        {/if}
                      </td>
                      <td>
                        <span class="rarity-badge" style="background-color: {getRarityColor(loot.Rarity)}">
                          {loot.Rarity || 'Unknown'}
                        </span>
                      </td>
                      <td class="date-cell">{loot.AvailableFrom || '-'}</td>
                      <td class="date-cell">{loot.AvailableUntil || '-'}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
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
      <h2>Strongboxes</h2>
      <p>Select a strongbox from the list to view details.</p>
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
    text-align: right;
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

  /* Loots table */
  .loots-table-wrapper {
    overflow-x: auto;
  }

  .loots-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  .loots-table th,
  .loots-table td {
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .loots-table th {
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.3px;
    background-color: var(--hover-color);
  }

  .loots-table td {
    color: var(--text-color);
  }

  .loots-table tbody tr:hover {
    background-color: var(--hover-color);
  }

  .item-name {
    font-weight: 500;
  }

  .item-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .item-link:hover {
    text-decoration: underline;
  }

  .na-text {
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .rarity-badge {
    display: inline-block;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
    color: white;
    border-radius: 4px;
    text-transform: uppercase;
  }

  .date-cell {
    font-size: 12px;
    color: var(--text-muted, #999);
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

    .loots-table th,
    .loots-table td {
      padding: 8px;
      font-size: 12px;
    }
  }
</style>
