<!--
  @component Pets Wiki Page
  Wikipedia-style layout with floating infobox on the right side.

  Legacy editConfig preserved in pets-legacy/+page.svelte
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe, getTypeLink } from '$lib/util';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';

  export let data;

  $: pet = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};

  // All pets for navigation
  $: allItems = data.items || [];

  // Build navigation items
  $: navItems = allItems;

  // Rarity filters for sidebar
  $: navFilters = [
    { key: 'Properties.Rarity', label: 'Rarity', values: [
      { value: 'Common', label: 'Common' },
      { value: 'Uncommon', label: 'Uncommon' },
      { value: 'Rare', label: 'Rare' },
      { value: 'Epic', label: 'Epic' },
      { value: 'Legendary', label: 'Legendary' }
    ]}
  ];

  // Sidebar table columns
  $: navTableColumns = [
    { key: 'rarity', header: 'Rarity', width: '60px', filterPlaceholder: 'Rare', getValue: (item) => item.Properties?.Rarity, format: (v) => v ? v.slice(0, 4) : '-' },
    { key: 'planet', header: 'Planet', width: '60px', filterPlaceholder: 'Cal', getValue: (item) => item.Planet?.Name, format: (v) => v ? v.slice(0, 4) : '-' }
  ];

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Pets', href: '/items/pets' },
    ...(pet ? [{ label: pet.Name }] : [])
  ];

  // SEO
  $: seoDescription = pet?.Properties?.Description ||
    `${pet?.Name || 'Pet'} - ${pet?.Properties?.Rarity || ''} pet in Entropia Universe.`;

  $: canonicalUrl = pet
    ? `https://entropianexus.com/items/pets/${encodeURIComponentSafe(pet.Name)}`
    : 'https://entropianexus.com/items/pets';

  // Check for effects
  $: hasEffects = pet?.Effects?.length > 0;

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    skills: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-pet-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {}
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-pet-panels', JSON.stringify(panelStates));
    } catch (e) {}
  }

  // Rarity color mapping
  function getRarityColor(rarity) {
    switch (rarity) {
      case 'Common': return '#9ca3af';
      case 'Uncommon': return '#22c55e';
      case 'Rare': return '#3b82f6';
      case 'Epic': return '#a855f7';
      case 'Legendary': return '#f59e0b';
      case 'Mythic': return '#ef4444';
      case 'Unique': return '#ec4899';
      default: return '#9ca3af';
    }
  }
</script>

<WikiSEO
  title={pet?.Name || 'Pets'}
  description={seoDescription}
  entityType="Pet"
  entity={pet}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Pets"
  {breadcrumbs}
  entity={pet}
  entityType="Pet"
  basePath="/items/pets"
  {navItems}
  {navFilters}
  {navTableColumns}
  {user}
  editable={true}
>
  {#if pet}
    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <div class="icon-placeholder">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
              <circle cx="12" cy="10" r="6" />
              <path d="M12 16v4M8 20h8" />
              <circle cx="9" cy="9" r="1" fill="currentColor" />
              <circle cx="15" cy="9" r="1" fill="currentColor" />
            </svg>
          </div>
          <div class="infobox-title">{pet.Name}</div>
          <div class="infobox-subtitle">
            <span class="type-badge" style="background-color: {getRarityColor(pet.Properties?.Rarity)}">{pet.Properties?.Rarity || 'Pet'}</span>
          </div>
        </div>

        <!-- Tier-1 Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Rarity</span>
            <span class="stat-value">{pet.Properties?.Rarity ?? 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Training</span>
            <span class="stat-value">{pet.Properties?.TrainingDifficulty ?? 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Taming Level</span>
            <span class="stat-value">{pet.Properties?.TamingLevel ?? 'N/A'}</span>
          </div>
        </div>

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Rarity</span>
            <span class="stat-value">{pet.Properties?.Rarity ?? 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Training Difficulty</span>
            <span class="stat-value">{pet.Properties?.TrainingDifficulty ?? 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Planet</span>
            <span class="stat-value">{pet.Planet?.Name ?? 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Exportable</span>
            <span class="stat-value">{pet.Properties?.ExportableLevel > 0 ? `Level ${pet.Properties.ExportableLevel}` : 'No'}</span>
          </div>
        </div>

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Nutrio Capacity</span>
            <span class="stat-value">{pet.Properties?.NutrioCapacity != null ? `${(pet.Properties.NutrioCapacity / 100).toFixed(2)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Nutrio Consumption</span>
            <span class="stat-value">{pet.Properties?.NutrioConsumptionPerHour != null ? `${(pet.Properties.NutrioConsumptionPerHour / 100).toFixed(2)} PED/h` : 'N/A'}</span>
          </div>
        </div>

        <!-- Skill Stats -->
        <div class="stats-section">
          <h4 class="section-title">Skill</h4>
          <div class="stat-row">
            <span class="stat-label">Profession</span>
            <span class="stat-value links">
              <a href={getTypeLink('Animal Tamer', 'Profession')} class="entity-link">Animal Tamer</a>
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Taming Level</span>
            <span class="stat-value">{pet.Properties?.TamingLevel ?? 'N/A'}</span>
          </div>
        </div>
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">{pet.Name}</h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if pet.Properties?.Description}
            <div class="description-content">{pet.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {pet.Name} is a {pet.Properties?.Rarity?.toLowerCase() || ''} pet that can be tamed in Entropia Universe.
            </div>
          {/if}
        </div>

        <!-- Pet Skills/Effects Section -->
        {#if hasEffects}
          <DataSection
            title="Pet Skills"
            icon=""
            bind:expanded={panelStates.skills}
            on:toggle={savePanelStates}
          >
            <div class="effects-table-wrapper">
              <table class="effects-table">
                <thead>
                  <tr>
                    <th>Effect</th>
                    <th>Upkeep</th>
                    <th>Level</th>
                    <th>Cost</th>
                    <th>Criteria</th>
                  </tr>
                </thead>
                <tbody>
                  {#each pet.Effects as effect}
                    <tr>
                      <td class="effect-name">
                        {effect.Properties?.Strength ?? ''}{effect.Properties?.Unit ?? ''} {effect.Name}
                      </td>
                      <td>{effect.Properties?.NutrioConsumptionPerHour ?? 'N/A'}/h</td>
                      <td>{effect.Properties?.Unlock?.Level ?? 'N/A'}</td>
                      <td class="cost-cell">
                        {#if effect.Properties?.Unlock?.CostPED != null}
                          <div>{effect.Properties.Unlock.CostPED} PED</div>
                        {/if}
                        {#if effect.Properties?.Unlock?.CostEssence != null}
                          <div>{effect.Properties.Unlock.CostEssence} Animal Essence</div>
                        {/if}
                        {#if effect.Properties?.Unlock?.CostRareEssence != null}
                          <div>{effect.Properties.Unlock.CostRareEssence} Rare Animal Essence</div>
                        {/if}
                        {#if effect.Properties?.Unlock?.CostPED == null && effect.Properties?.Unlock?.CostEssence == null && effect.Properties?.Unlock?.CostRareEssence == null}
                          N/A
                        {/if}
                      </td>
                      <td class="criteria-cell">
                        {#if effect.Properties?.Unlock?.Criteria != null}
                          <div>{effect.Properties.Unlock.Criteria}</div>
                          {#if effect.Properties?.Unlock?.CriteriaValue != null}
                            <div class="criteria-value">Amount: {effect.Properties.Unlock.CriteriaValue}</div>
                          {/if}
                        {:else}
                          N/A
                        {/if}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Pets</h2>
      <p>Select a pet from the list to view details.</p>
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

  .stat-value.links {
    text-align: right;
    font-size: 12px;
  }

  .entity-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .entity-link:hover {
    text-decoration: underline;
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

  /* Effects table */
  .effects-table-wrapper {
    overflow-x: auto;
  }

  .effects-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  .effects-table th,
  .effects-table td {
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .effects-table th {
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.3px;
    background-color: var(--hover-color);
  }

  .effects-table td {
    color: var(--text-color);
  }

  .effects-table tbody tr:hover {
    background-color: var(--hover-color);
  }

  .effect-name {
    font-weight: 500;
    color: var(--accent-color, #4a9eff);
  }

  .cost-cell,
  .criteria-cell {
    font-size: 12px;
    line-height: 1.4;
  }

  .criteria-value {
    color: var(--text-muted, #999);
    font-size: 11px;
    margin-top: 2px;
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

    .effects-table th,
    .effects-table td {
      padding: 8px;
      font-size: 12px;
    }
  }
</style>
