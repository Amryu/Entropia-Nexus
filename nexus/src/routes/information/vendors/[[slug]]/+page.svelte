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
  import { encodeURIComponentSafe, getLatestPendingUpdate } from '$lib/util';
  import { getPlanetNavFilter } from '$lib/mapUtil';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import WaypointCopyButton from '$lib/components/wiki/WaypointCopyButton.svelte';
  import WaypointInput from '$lib/components/wiki/WaypointInput.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import { getWaypoint } from '$lib/mapUtil';

  // Vendor-specific components
  import VendorOffers from '$lib/components/wiki/vendors/VendorOffers.svelte';
  import VendorOffersEdit from '$lib/components/wiki/vendors/VendorOffersEdit.svelte';

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

  let { data } = $props();

  let vendor = $derived(data.object);
  let user = $derived(data.session?.user);
  let allItems = $derived(data.allItems || []);
  let pendingChange = $derived(data.pendingChange);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  let isCreateMode = $derived(data.isCreateMode || false);
  let vendorEntityId = $derived(vendor?.Id ?? vendor?.ItemId);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, vendorEntityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  let canUsePendingChange = $derived(!!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))));

  // Verified users can edit
  let canEdit = $derived(user?.verified || user?.grants?.includes('wiki.edit'));

  // Planet options for dropdown
  const planetOptions = [
    { value: 'Calypso', label: 'Calypso' },
    { value: 'ARIS', label: 'ARIS' },
    { value: 'Arkadia', label: 'Arkadia' },
    { value: 'Cyrene', label: 'Cyrene' },
    { value: 'Monria', label: 'Monria' },
    { value: 'ROCKtropia', label: 'Rocktropia' },
    { value: 'Toulan', label: 'Toulan' },
    { value: 'Next Island', label: 'Next Island' },
    { value: 'Space', label: 'Space' }
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
  $effect(() => {
    if (user) {
      const existingChange = data.existingChange || null;
      const initialEntity = isCreateMode
        ? (existingChange?.data || emptyVendor)
        : vendor;
      const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
      initEditState(initialEntity, 'Vendor', isCreateMode, editChange);
    }
  });

  // Set pending change in store when it changes
  $effect(() => {
    if (resolvedPendingChange) {
      setExistingPendingChange(resolvedPendingChange);
    } else {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
    }
  });

  // Active vendor: use currentEntity in edit mode, pendingChange data when viewing, otherwise original
  let activeVendor = $derived($editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : vendor);

  // Cleanup on destroy
  onDestroy(() => {
    resetEditState();
  });

  // Build navigation items from vendors
  let navItems = $derived(allItems);

  // Navigation filters - filter by planet (includes sub-planets)
  const navFilters = [getPlanetNavFilter('Planet.Name')];

  const vendorColumnDefs = {
    planet: {
      key: 'planet',
      header: 'Planet',
      width: '90px',
      filterPlaceholder: 'Calypso',
      getValue: (item) => item?.Planet?.Name,
      format: (v) => v || '-'
    },
    category: {
      key: 'category',
      header: 'Category',
      width: '110px',
      filterPlaceholder: 'Trade',
      getValue: (item) => getVendorCategory(item),
      format: (v) => v || '-'
    },
    offers: {
      key: 'offers',
      header: 'Offers',
      width: '55px',
      filterPlaceholder: '>0',
      getValue: (item) => item?.Offers?.length || 0,
      format: (v) => v != null ? v : '-'
    },
    limited: {
      key: 'limited',
      header: 'Limited',
      width: '60px',
      filterPlaceholder: '>0',
      getValue: (item) => item?.Offers?.filter(o => o.IsLimited).length || 0,
      format: (v) => v > 0 ? v : '-'
    }
  };

  const navTableColumns = [
    vendorColumnDefs.planet,
    vendorColumnDefs.category,
    vendorColumnDefs.offers
  ];

  const navFullWidthColumns = [
    ...navTableColumns,
    vendorColumnDefs.limited
  ];

  const allAvailableColumns = Object.values(vendorColumnDefs);

  // Breadcrumbs
  let breadcrumbs = $derived([
    { label: 'Information', href: '/information' },
    { label: 'Vendors', href: '/information/vendors' },
    ...(activeVendor?.Name ? [{ label: activeVendor.Name }] : isCreateMode ? [{ label: 'New Vendor' }] : [])
  ]);

  // SEO
  let seoDescription = $derived(activeVendor?.Properties?.Description ||
    `${activeVendor?.Name || 'Vendor'} - Vendor on ${activeVendor?.Planet?.Name || 'Calypso'} in Entropia Universe.`);

  let canonicalUrl = $derived(activeVendor?.Name
    ? `https://entropianexus.com/information/vendors/${encodeURIComponentSafe(activeVendor.Name)}`
    : 'https://entropianexus.com/information/vendors');

  // Image URL for SEO
  let entityImageUrl = $derived(vendor?.Id ? `/api/img/vendor/${vendor.Id}` : null);

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = $state({
    offers: true
  });

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

  function getPlanetBadgeClass(planetName) {
    if (!planetName) return '';
    const lower = planetName.toLowerCase().replace(/\s+/g, '-');
    return `planet-${lower}`;
  }

  // Reactive calculations
  let offerCount = $derived(getOfferCount(activeVendor));
  let limitedCount = $derived(getLimitedCount(activeVendor));
  let uniqueTypes = $derived(getUniqueTypes(activeVendor));
  let hasLocation = $derived(hasCoordinates(activeVendor));

  // Build waypoint value object for WaypointInput (edit mode)
  let waypointValue = $derived({
    planet: activeVendor?.Planet?.Name || 'Calypso',
    x: activeVendor?.Properties?.Coordinates?.Longitude ?? null,
    y: activeVendor?.Properties?.Coordinates?.Latitude ?? null,
    z: activeVendor?.Properties?.Coordinates?.Altitude ?? null,
    name: activeVendor?.Name || ''
  });

  // Build waypoint string for WaypointCopyButton (view mode)
  let waypointString = $derived(activeVendor?.Properties?.Coordinates?.Longitude != null
    ? getWaypoint(
        activeVendor?.Planet?.Name || 'Calypso',
        activeVendor?.Properties?.Coordinates?.Longitude,
        activeVendor?.Properties?.Coordinates?.Latitude,
        activeVendor?.Properties?.Coordinates?.Altitude ?? 100,
        activeVendor?.Name || ''
      )
    : '');

  // ========== EDIT HANDLERS ==========
  function handleWaypointChange(detail) {
    if (detail.x !== undefined) updateField('Properties.Coordinates.Longitude', detail.x);
    if (detail.y !== undefined) updateField('Properties.Coordinates.Latitude', detail.y);
    if (detail.z !== undefined) updateField('Properties.Coordinates.Altitude', detail.z);
  }

  function handleDescriptionChange(data) {
    updateField('Properties.Description', data);
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
  basePath="/information/vendors"
  {navItems}
  {navFilters}
  {navTableColumns}
  {navFullWidthColumns}
  navAllAvailableColumns={allAvailableColumns}
  navPageTypeId="vendors"
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
            <button class="banner-btn" onclick={() => setViewingPendingChange(false)}>
              View Current
            </button>
          {:else}
            <button class="banner-btn primary" onclick={() => setViewingPendingChange(true)}>
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
        <div class="stats-section tier-1 tier-blue">
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
            <WaypointInput
              value={waypointValue}
              planetLocked={true}
              nameLocked={true}
              hidePlanet={true}
              hideName={true}
              onchange={handleWaypointChange}
            />
          {:else if hasLocation}
            <div class="coordinates-display">
              <span class="coordinates-label">Waypoint</span>
              <WaypointCopyButton waypoint={waypointString} />
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
              onchange={handleDescriptionChange}
              placeholder="Enter a description for this vendor..."
              showWaypoints={true}
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
        <DataSection
          title="Offers"
          icon=""
          bind:expanded={panelStates.offers}
          subtitle="{offerCount} item{offerCount !== 1 ? 's' : ''}"
          ontoggle={savePanelStates}
        >
          {#if $editMode}
            <VendorOffersEdit offers={activeVendor?.Offers || []} fieldPath="Offers" />
          {:else}
            <VendorOffers offers={activeVendor?.Offers || []} />
          {/if}
        </DataSection>
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


  /* Mobile adjustments */
  @media (max-width: 899px) {
    .pending-change-banner {
      flex-direction: column;
      gap: 12px;
      align-items: flex-start;
    }
  }
</style>
