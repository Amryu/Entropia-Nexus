<!--
  @component Vendor Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: Planet, location, offer count
  Article: Description → Offers
  Supports full wiki editing.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { onMount, onDestroy } from 'svelte';
  import { encodeURIComponentSafe } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import WaypointCopyButton from '$lib/components/wiki/WaypointCopyButton.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';

  // Vendor-specific components
  import VendorOffers from '$lib/components/wiki/vendors/VendorOffers.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  // Wiki edit state
  import {
    editMode,
    isCreateMode as isCreateModeStore,
    initEditState,
    resetEditState,
    currentEntity,
    existingPendingChange,
    viewingPendingChange,
    setExistingPendingChange,
    setViewingPendingChange,
    updateField,
    changeMetadata
  } from '$lib/stores/wikiEditState';

  export let data;

  $: vendor = data.object;
  $: user = data.session?.user;
  $: allItems = data.allItems || [];
  $: pendingChange = data.pendingChange;
  $: canCreateNew = data.canCreateNew ?? true;
  $: userPendingCreates = data.userPendingCreates || [];
  $: userPendingUpdates = data.userPendingUpdates || [];
  $: isCreateMode = data.isCreateMode || false;

  // Verified users can edit
  $: canEdit = user?.verified || user?.isAdmin;

  // Planet options for dropdown
  const planetOptions = [
    { value: 'Calypso', label: 'Calypso' },
    { value: 'ARIS', label: 'ARIS' },
    { value: 'Arkadia', label: 'Arkadia' },
    { value: 'Cyrene', label: 'Cyrene' },
    { value: 'Monria', label: 'Monria' },
    { value: 'ROCKtropia', label: 'Rocktropia' },
    { value: 'Toulan', label: 'Toulan' },
    { value: 'Next Island', label: 'Next Island' }
  ];

  // Empty vendor template for create mode
  const emptyVendor = {
    Id: null,
    Name: '',
    Planet: { Name: 'Calypso' },
    Properties: {
      Description: '',
      Coordinates: {
        Longitude: null,
        Latitude: null,
        Altitude: 100
      }
    },
    Offers: []
  };

  // Initialize edit state when user/vendor changes
  $: if (user) {
    const existingChange = data.existingChange || null;
    const initialEntity = isCreateMode
      ? (existingChange?.data || emptyVendor)
      : vendor;
    initEditState(initialEntity, 'Vendor', isCreateMode, existingChange);
  }

  // Set pending change in store when it changes
  $: if (pendingChange) {
    setExistingPendingChange(pendingChange);
  }

  // Active vendor: use currentEntity in edit mode, pendingChange data when viewing, otherwise original
  $: activeVendor = $editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : vendor;

  // Cleanup on destroy
  onDestroy(() => {
    resetEditState();
  });

  // Build navigation items from vendors
  $: navItems = allItems;

  // Navigation filters - filter by planet
  const navFilters = [
    {
      key: 'Planet.Name',
      label: 'Planet',
      values: [
        { value: 'Calypso', label: 'Calypso' },
        { value: 'ARIS', label: 'ARIS' },
        { value: 'Arkadia', label: 'Arkadia' },
        { value: 'Cyrene', label: 'Cyrene' },
        { value: 'Monria', label: 'Monria' },
        { value: 'ROCKtropia', label: 'Rocktropia' },
        { value: 'Toulan', label: 'Toulan' },
        { value: 'Next Island', label: 'Next Island' },
      ]
    }
  ];

  const navTableColumns = [
    {
      key: 'planet',
      header: 'Planet',
      width: '90px',
      filterPlaceholder: 'Calypso',
      getValue: (item) => item?.Planet?.Name,
      format: (v) => v || '-'
    },
    {
      key: 'category',
      header: 'Category',
      width: '110px',
      filterPlaceholder: 'Trade',
      getValue: (item) => getVendorCategory(item),
      format: (v) => v || '-'
    }
  ];

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Information', href: '/information' },
    { label: 'Vendors', href: '/information/vendors' },
    ...(activeVendor?.Name ? [{ label: activeVendor.Name }] : isCreateMode ? [{ label: 'New Vendor' }] : [])
  ];

  // SEO
  $: seoDescription = activeVendor?.Properties?.Description ||
    `${activeVendor?.Name || 'Vendor'} - Vendor on ${activeVendor?.Planet?.Name || 'Calypso'} in Entropia Universe.`;

  $: canonicalUrl = activeVendor?.Name
    ? `https://entropianexus.com/information/vendors/${encodeURIComponentSafe(activeVendor.Name)}`
    : 'https://entropianexus.com/information/vendors';

  // Image URL for SEO
  $: entityImageUrl = vendor?.Id ? `/api/img/vendor/${vendor.Id}` : null;

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    offers: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-vendor-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-vendor-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== VENDOR CALCULATIONS ==========
  function getOfferCount(v) {
    return v?.Offers?.length || 0;
  }

  function getLimitedCount(v) {
    if (!v?.Offers) return 0;
    return v.Offers.filter(o => o.IsLimited).length;
  }

  function getUniqueTypes(v) {
    if (!v?.Offers) return [];
    const types = new Set();
    v.Offers.forEach(o => {
      if (o.Item?.Properties?.Type) {
        types.add(o.Item.Properties.Type);
      }
    });
    return Array.from(types).sort();
  }

  function getVendorCategory(v) {
    const directCategory = v?.Category?.Name || v?.Category || v?.Properties?.Category;
    if (directCategory) return directCategory;
    const types = getUniqueTypes(v);
    if (!types || types.length === 0) return null;
    return types.length === 1 ? types[0] : 'Mixed';
  }

  function hasCoordinates(v) {
    const coords = v?.Properties?.Coordinates;
    return coords && (coords.Longitude != null || coords.Latitude != null);
  }

  function formatCoordinates(v) {
    const coords = v?.Properties?.Coordinates;
    if (!coords) return null;

    const planet = v.Planet?.Properties?.TechnicalName || v.Planet?.Name || 'Unknown';
    const lon = coords.Longitude ?? 0;
    const lat = coords.Latitude ?? 0;
    const alt = coords.Altitude ?? 100;

    return `[${planet}, ${lon}, ${lat}, ${alt}, ${v.Name}]`;
  }

  function getPlanetBadgeClass(planetName) {
    if (!planetName) return '';
    const lower = planetName.toLowerCase().replace(/\s+/g, '-');
    return `planet-${lower}`;
  }

  // Reactive calculations
  $: offerCount = getOfferCount(activeVendor);
  $: limitedCount = getLimitedCount(activeVendor);
  $: uniqueTypes = getUniqueTypes(activeVendor);
  $: hasLocation = hasCoordinates(activeVendor);
  $: coordinates = formatCoordinates(activeVendor);

  // ========== EDIT HANDLERS ==========
  function handleDescriptionChange(event) {
    updateField('Properties.Description', event.detail);
  }
</script>

<WikiSEO
  title={activeVendor?.Name || 'Vendors'}
  description={seoDescription}
  entityType="vendor"
  entity={activeVendor}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={activeVendor}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Vendors"
  {breadcrumbs}
  entity={activeVendor}
  entityType="Vendor"
  basePath="/information/vendors"
  {navItems}
  {navFilters}
  {navTableColumns}
  {user}
  editable={true}
  {canEdit}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
>
  {#if activeVendor || isCreateMode}
    <!-- Pending Change Banner -->
    {#if $existingPendingChange && !$editMode && !isCreateMode}
      <div class="pending-change-banner">
        <div class="banner-content">
          <span class="banner-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
          </span>
          <span class="banner-text">
            This vendor has a pending change by <strong>{$existingPendingChange.author_name || 'Unknown'}</strong>
            ({$existingPendingChange.state})
          </span>
        </div>
        <div class="banner-actions">
          {#if $viewingPendingChange}
            <button class="banner-btn" on:click={() => setViewingPendingChange(false)}>
              View Current
            </button>
          {:else}
            <button class="banner-btn primary" on:click={() => setViewingPendingChange(true)}>
              View Pending
            </button>
          {/if}
        </div>
      </div>
    {/if}

    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <EntityImageUpload
            entityId={activeVendor?.Id}
            entityName={activeVendor?.Name}
            entityType="vendor"
            {user}
            isEditMode={$editMode}
            {isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit
              type="text"
              value={activeVendor?.Name || ''}
              path="Name"
              placeholder="Enter vendor name"
            />
          </div>
          <div class="infobox-subtitle">
            <span class="planet-badge {getPlanetBadgeClass(activeVendor?.Planet?.Name)}">
              {activeVendor?.Planet?.Name || 'Calypso'}
            </span>
          </div>
        </div>

        <!-- Key Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Offers</span>
            <span class="stat-value">{offerCount}</span>
          </div>
          {#if limitedCount > 0}
            <div class="stat-row primary">
              <span class="stat-label">Limited</span>
              <span class="stat-value">{limitedCount}</span>
            </div>
          {/if}
        </div>

        <!-- Location -->
        <div class="stats-section">
          <h4 class="section-title">Location</h4>
          <div class="stat-row">
            <span class="stat-label">Planet</span>
            <span class="stat-value">
              <InlineEdit
                type="select"
                value={activeVendor?.Planet?.Name || 'Calypso'}
                path="Planet.Name"
                options={planetOptions}
              />
            </span>
          </div>
          {#if $editMode}
            <div class="stat-row">
              <span class="stat-label">Longitude</span>
              <span class="stat-value">
                <InlineEdit
                  type="number"
                  value={activeVendor?.Properties?.Coordinates?.Longitude ?? ''}
                  path="Properties.Coordinates.Longitude"
                  step={1}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Latitude</span>
              <span class="stat-value">
                <InlineEdit
                  type="number"
                  value={activeVendor?.Properties?.Coordinates?.Latitude ?? ''}
                  path="Properties.Coordinates.Latitude"
                  step={1}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Altitude</span>
              <span class="stat-value">
                <InlineEdit
                  type="number"
                  value={activeVendor?.Properties?.Coordinates?.Altitude ?? 100}
                  path="Properties.Coordinates.Altitude"
                  step={1}
                />
              </span>
            </div>
          {:else if hasLocation}
            <div class="coordinates-display">
              <span class="coordinates-label">Waypoint</span>
              <WaypointCopyButton waypoint={coordinates} />
            </div>
          {:else}
            <div class="stat-row">
              <span class="stat-label">Coordinates</span>
              <span class="stat-value muted">Not available</span>
            </div>
          {/if}
        </div>

        <!-- Item Types -->
        {#if uniqueTypes.length > 0}
          <div class="stats-section">
            <h4 class="section-title">Item Types</h4>
            <div class="type-tags">
              {#each uniqueTypes as type}
                <span class="type-tag">{type}</span>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Quick Link to Map -->
        {#if hasLocation && activeVendor?.Planet?.Name}
          <a href="/maps/{activeVendor.Planet.Name.toLowerCase().replace(/\s+/g, '')}" class="map-link-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"></polygon>
              <line x1="8" y1="2" x2="8" y2="18"></line>
              <line x1="16" y1="6" x2="16" y2="22"></line>
            </svg>
            <span>View on Map</span>
          </a>
        {/if}
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          <InlineEdit
            type="text"
            value={activeVendor?.Name || ''}
            path="Name"
            placeholder="Enter vendor name"
          />
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeVendor?.Properties?.Description || ''}
              on:change={handleDescriptionChange}
              placeholder="Enter a description for this vendor..."
            />
          {:else if activeVendor?.Properties?.Description}
            <div class="description-content">{@html sanitizeHtml(activeVendor.Properties.Description)}</div>
          {:else}
            <div class="description-content placeholder">
              {activeVendor?.Name || 'This vendor'} is a vendor located on {activeVendor?.Planet?.Name || 'Calypso'}.
              {#if offerCount > 0}
                They offer {offerCount} different item{offerCount !== 1 ? 's' : ''} for sale.
              {/if}
            </div>
          {/if}
        </div>

        <!-- Offers Section -->
        {#if !isCreateMode}
          <DataSection
            title="Offers"
            icon=""
            bind:expanded={panelStates.offers}
            subtitle="{offerCount} item{offerCount !== 1 ? 's' : ''}"
            on:toggle={savePanelStates}
          >
            <VendorOffers offers={activeVendor?.Offers || []} />
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Vendors</h2>
      <p>Select a vendor from the list to view details.</p>
      <p class="hint">Vendors sell various items including weapons, tools, and materials.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .pending-change-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background-color: var(--warning-bg, #fef3c7);
    border: 1px solid var(--warning-border, #f59e0b);
    border-radius: 8px;
    margin-bottom: 16px;
  }

  :global(.dark) .pending-change-banner {
    background-color: rgba(245, 158, 11, 0.1);
    border-color: rgba(245, 158, 11, 0.3);
  }

  .banner-content {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .banner-icon {
    color: var(--warning-color, #d97706);
  }

  .banner-text {
    font-size: 14px;
    color: var(--text-color);
  }

  .banner-actions {
    display: flex;
    gap: 8px;
  }

  .banner-btn {
    padding: 6px 12px;
    font-size: 13px;
    border-radius: 4px;
    border: 1px solid var(--border-color, #555);
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.15s;
  }

  .banner-btn:hover {
    background-color: var(--secondary-color);
  }

  .banner-btn.primary {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .banner-btn.primary:hover {
    opacity: 0.9;
  }

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

  .infobox-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
  }

  .infobox-subtitle {
    font-size: 12px;
    color: var(--text-muted, #999);
    margin-top: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .planet-badge {
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 4px;
    text-transform: uppercase;
  }

  /* Planet-specific colors */
  .planet-badge.planet-calypso {
    background-color: #22c55e;
  }

  .planet-badge.planet-arkadia {
    background-color: #3b82f6;
  }

  .planet-badge.planet-cyrene {
    background-color: #a855f7;
  }

  .planet-badge.planet-monria {
    background-color: #6b7280;
  }

  .planet-badge.planet-rocktropia {
    background-color: #ef4444;
  }

  .planet-badge.planet-toulan {
    background-color: #f59e0b;
  }

  .planet-badge.planet-next-island {
    background-color: #14b8a6;
  }

  .planet-badge.planet-aris {
    background-color: #8b5cf6;
  }

  /* Stats sections */
  .stats-section {
    padding: 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  .stats-section.tier-1 {
    background: linear-gradient(135deg, #3a6d99 0%, #2d5577 100%);
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
    color: #e8f4ff;
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

  .stat-value.muted {
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .coordinates-display {
    margin-top: 8px;
  }

  .coordinates-label {
    display: block;
    font-size: 12px;
    color: var(--text-muted, #999);
    margin-bottom: 4px;
  }

  .coordinates-value {
    display: block;
    font-size: 11px;
    font-family: monospace;
    padding: 8px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    word-break: break-all;
    color: var(--accent-color, #4a9eff);
  }

  .type-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .type-tag {
    display: inline-block;
    padding: 3px 8px;
    font-size: 10px;
    font-weight: 500;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .map-link-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 16px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    color: var(--text-color);
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.15s;
  }

  .map-link-btn:hover {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .map-link-btn svg {
    flex-shrink: 0;
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

  .no-selection .hint {
    font-size: 14px;
    margin-top: 16px;
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

    .pending-change-banner {
      flex-direction: column;
      gap: 12px;
      align-items: flex-start;
    }
  }
</style>
