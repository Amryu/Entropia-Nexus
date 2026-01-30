<!--
  @component Vehicles Wiki Page
  Wikipedia-style layout with floating infobox on the right side.

  Legacy editConfig preserved in vehicles-legacy/+page.svelte
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

  // Legacy components for data display
  import Acquisition from '$lib/components/Acquisition.svelte';

  export let data;

  $: vehicle = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};

  // All vehicles for navigation
  $: allItems = data.items || [];

  // Build navigation items
  $: navItems = allItems;

  // Type filters for sidebar
  // NOTE: Currently disabled because Type column is NULL for all vehicles in the database.
  // Re-enable once vehicle type data is populated.
  $: navFilters = [];

  // Sidebar table columns
  $: navTableColumns = [
    { key: 'type', header: 'Type', width: '55px', filterPlaceholder: 'Land', getValue: (item) => item.Properties?.Type, format: (v) => v ? v.slice(0, 4) : '-' },
    { key: 'speed', header: 'Speed', width: '60px', filterPlaceholder: '>50', getValue: (item) => item.Properties?.MaxSpeed, format: (v) => v != null ? v.toFixed(0) : '-' }
  ];

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Vehicles', href: '/items/vehicles' },
    ...(vehicle ? [{ label: vehicle.Name }] : [])
  ];

  // SEO
  $: seoDescription = vehicle?.Properties?.Description ||
    `${vehicle?.Name || 'Vehicle'} - ${vehicle?.Properties?.Type || ''} vehicle in Entropia Universe.`;

  $: canonicalUrl = vehicle
    ? `https://entropianexus.com/items/vehicles/${encodeURIComponentSafe(vehicle.Name)}`
    : 'https://entropianexus.com/items/vehicles';

  // ========== CALCULATION FUNCTIONS ==========
  function getTotalDefense(item) {
    if (!item?.Properties?.Defense) return 0;
    const d = item.Properties.Defense;
    return (d.Impact ?? 0) + (d.Cut ?? 0) + (d.Stab ?? 0) + (d.Penetration ?? 0) +
           (d.Shrapnel ?? 0) + (d.Burn ?? 0) + (d.Cold ?? 0) + (d.Acid ?? 0) + (d.Electric ?? 0);
  }

  // ========== COMPUTED VALUES ==========
  $: totalDefense = getTotalDefense(vehicle);

  // Defense types for grid display
  const defenseTypes = ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'];

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    defense: true,
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-vehicle-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {}
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-vehicle-panels', JSON.stringify(panelStates));
    } catch (e) {}
  }
</script>

<WikiSEO
  title={vehicle?.Name || 'Vehicles'}
  description={seoDescription}
  entityType="Vehicle"
  entity={vehicle}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Vehicles"
  {breadcrumbs}
  entity={vehicle}
  entityType="Vehicle"
  basePath="/items/vehicles"
  {navItems}
  {navFilters}
  {navTableColumns}
  {user}
  editable={true}
>
  {#if vehicle}
    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <div class="icon-placeholder">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
              <rect x="3" y="7" width="18" height="10" rx="2" />
              <circle cx="7" cy="17" r="2" />
              <circle cx="17" cy="17" r="2" />
            </svg>
          </div>
          <div class="infobox-title">{vehicle.Name}</div>
          <div class="infobox-subtitle">
            <span class="type-badge">{vehicle.Properties?.Type || 'Vehicle'}</span>
          </div>
        </div>

        <!-- Tier-1 Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Max Speed</span>
            <span class="stat-value">{vehicle.Properties?.MaxSpeed != null ? `${vehicle.Properties.MaxSpeed.toFixed(2)} km/h` : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Passengers</span>
            <span class="stat-value">{vehicle.Properties?.PassengerCount ?? 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Max. SI</span>
            <span class="stat-value">{vehicle.Properties?.MaxStructuralIntegrity ?? 'N/A'}</span>
          </div>
        </div>

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">{vehicle.Properties?.Weight != null ? `${clampDecimals(vehicle.Properties.Weight, 1, 6)}kg` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Spawned Weight</span>
            <span class="stat-value">{vehicle.Properties?.SpawnedWeight != null ? `${vehicle.Properties.SpawnedWeight.toFixed(1)}kg` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Type</span>
            <span class="stat-value">{vehicle.Properties?.Type ?? 'N/A'}</span>
          </div>
        </div>

        <!-- Vehicle Stats -->
        <div class="stats-section">
          <h4 class="section-title">Vehicle</h4>
          <div class="stat-row">
            <span class="stat-label">Passengers</span>
            <span class="stat-value">{vehicle.Properties?.PassengerCount ?? 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Item Capacity</span>
            <span class="stat-value">{vehicle.Properties?.ItemCapacity ?? 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Weight Capacity</span>
            <span class="stat-value">{vehicle.Properties?.WeightCapacity != null ? `${vehicle.Properties.WeightCapacity.toFixed(1)}kg` : 'N/A'}</span>
          </div>
          {#if vehicle.Properties?.Type === 'Land' || vehicle.Properties?.Type === 'Amphibious'}
            <div class="stat-row">
              <span class="stat-label">Wheel Grip</span>
              <span class="stat-value">{vehicle.Properties?.WheelGrip ?? 'N/A'}</span>
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Engine Power</span>
            <span class="stat-value">{vehicle.Properties?.EnginePower ?? 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Max. Speed</span>
            <span class="stat-value">{vehicle.Properties?.MaxSpeed != null ? `${vehicle.Properties.MaxSpeed.toFixed(2)} km/h` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Max. SI</span>
            <span class="stat-value">{vehicle.Properties?.MaxStructuralIntegrity ?? 'N/A'}</span>
          </div>
          {#if vehicle.AttachmentSlots?.length > 0}
            <div class="stat-row">
              <span class="stat-label">Attachment Slots</span>
              <span class="stat-value">{vehicle.AttachmentSlots.map(x => x.Name).join(', ')}</span>
            </div>
          {/if}
        </div>

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Max. TT</span>
            <span class="stat-value">{vehicle.Properties?.Economy?.MaxTT != null ? `${clampDecimals(vehicle.Properties.Economy.MaxTT, 2, 8)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min. TT</span>
            <span class="stat-value">{vehicle.Properties?.Economy?.MinTT != null ? `${clampDecimals(vehicle.Properties.Economy.MinTT, 2, 8)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Durability</span>
            <span class="stat-value">{vehicle.Properties?.Economy?.Durability ?? 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Fuel</span>
            <span class="stat-value">{vehicle.Fuel?.Name ?? 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Consumption (Active)</span>
            <span class="stat-value">{vehicle.Properties?.Economy?.FuelConsumptionActive != null ? `${vehicle.Properties.Economy.FuelConsumptionActive.toFixed(2)} PED/km` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Consumption (Passive)</span>
            <span class="stat-value">{vehicle.Properties?.Economy?.FuelConsumptionPassive != null ? `${vehicle.Properties.Economy.FuelConsumptionPassive.toFixed(2)} PED/min` : 'N/A'}</span>
          </div>
        </div>

        <!-- Defense Grid in Infobox -->
        {#if totalDefense > 0}
          <div class="stats-section">
            <h4 class="section-title">Defense</h4>
            <div class="infobox-defense-grid">
              {#each defenseTypes as dtype}
                {#if vehicle.Properties?.Defense?.[dtype] > 0}
                  <div class="mini-defense-item">
                    <span class="mini-defense-label">{dtype}</span>
                    <span class="mini-defense-value">{vehicle.Properties.Defense[dtype].toFixed(1)}</span>
                  </div>
                {/if}
              {/each}
            </div>
            <!-- Total Defense Full-Width Box -->
            <div class="defense-total-box">
              <span class="defense-total-label">Total Defense</span>
              <span class="defense-total-value">{totalDefense.toFixed(1)}</span>
            </div>
          </div>
        {/if}
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">{vehicle.Name}</h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if vehicle.Properties?.Description}
            <div class="description-content">{vehicle.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {vehicle.Name} is a {vehicle.Properties?.Type?.toLowerCase() || ''} vehicle in Entropia Universe.
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
      <h2>Vehicles</h2>
      <p>Select a vehicle from the list to view details.</p>
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
    word-break: break-word;
    max-width: 60%;
  }

  /* Mini defense grid for infobox */
  .infobox-defense-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
  }

  .mini-defense-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 6px 4px;
    background-color: var(--secondary-color);
    border-radius: 4px;
    border: 1px solid var(--border-color, #555);
  }

  .mini-defense-label {
    font-size: 9px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .mini-defense-value {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  /* Total defense full-width box */
  .defense-total-box {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
    padding: 10px 12px;
    background-color: var(--accent-color, #4a9eff);
    border-radius: 6px;
  }

  .defense-total-label {
    font-size: 12px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.9);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .defense-total-value {
    font-size: 18px;
    font-weight: 700;
    color: white;
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
