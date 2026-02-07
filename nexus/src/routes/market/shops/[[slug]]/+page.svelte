<!--
  @component Shop Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: Owner, Planet, location, inventory stats
  Article: Description → Inventory (by section)

  Special: Shops have two editing models:
  - Wiki data (Name, Description): Uses standard wiki changes workflow
  - Owner data (managers, inventory): Uses existing dialogs with direct save
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { onMount, onDestroy } from 'svelte';
  import { encodeURIComponentSafe, apiCall, getLatestPendingUpdate } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import WaypointCopyButton from '$lib/components/wiki/WaypointCopyButton.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';

  // Shop-specific components
  import ShopInventory from '$lib/components/wiki/shops/ShopInventory.svelte';
  import ShopManagersDialog from '$lib/components/wiki/shops/ShopManagersDialog.svelte';
  import ShopInventoryDialog from '$lib/components/wiki/shops/ShopInventoryDialog.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  // Wiki edit state
  import {
    editMode,
    isCreateMode as createModeStore,
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

  $: shop = data.object;
  $: user = data.session?.user;
  $: pendingChange = data.pendingChange;
  $: isCreateMode = data.isCreateMode || false;
  $: canCreateNew = data.canCreateNew ?? true;
  $: userPendingCreates = data.userPendingCreates || [];

  $: userPendingUpdates = data.userPendingUpdates || [];
  $: shopEntityId = shop?.Id ?? shop?.ItemId;
  $: userPendingUpdate = getLatestPendingUpdate(userPendingUpdates, shopEntityId);
  $: resolvedPendingChange = userPendingUpdate || pendingChange;
  $: canUsePendingChange = !!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user.grants?.includes('wiki.approve')));
  // Constants for section names (matches legacy)
  const SECTION_NAMES = ['Indoor', 'Display', 'Additional'];

  // Empty entity template for create mode
  const emptyEntity = {
    Id: null,
    Name: '',
    Description: '',
    Planet: { Name: 'Calypso' },
    Coordinates: {
      Longitude: null,
      Latitude: null,
      Altitude: null
    },
    Owner: null,
    OwnerId: null,
    Managers: [],
    InventoryGroups: [],
    Sections: [
      { Name: SECTION_NAMES[0], ItemPoints: null, Description: null },
      { Name: SECTION_NAMES[1], ItemPoints: null, Description: null }
    ],
    MaxGuests: null,
    HasAdditionalArea: false
  };

  // Check if shop has an owner (used to disable certain fields)
  $: hasOwner = activeEntity?.Owner?.Name != null;

  // Check if shop has Additional area
  $: hasAdditionalArea = activeEntity?.Sections?.some(s => s.Name === SECTION_NAMES[2]) || activeEntity?.HasAdditionalArea || false;

  // Owner search state for shop owner picker
  let ownerSearchQuery = '';
  let ownerSearchResults = [];
  let showOwnerSuggestions = false;
  let isOwnerSearching = false;
  let ownerSearchTimeout = null;
  // Local display name for owner during editing (not saved to entity)
  let selectedOwnerDisplayName = '';

  // Search users as they type (for shop owner)
  async function handleOwnerSearchInput() {
    if (ownerSearchQuery.trim().length < 2) {
      ownerSearchResults = [];
      showOwnerSuggestions = false;
      return;
    }

    if (ownerSearchTimeout) clearTimeout(ownerSearchTimeout);

    ownerSearchTimeout = setTimeout(async () => {
      isOwnerSearching = true;
      try {
        const response = await fetch(`/api/users/search?q=${encodeURIComponent(ownerSearchQuery.trim())}&limit=10`);
        const data = await response.json();

        if (response.ok) {
          ownerSearchResults = data.users || [];
          showOwnerSuggestions = ownerSearchResults.length > 0;
        }
      } catch (err) {
        console.error('Owner search failed:', err);
      } finally {
        isOwnerSearching = false;
      }
    }, 300);
  }

  function selectOwner(u) {
    // Store only the ID in OwnerId (as the schema expects)
    updateField('OwnerId', u ? Number(u.id) : null);
    // Keep display name locally for the editing session
    selectedOwnerDisplayName = u ? (u.eu_name || u.global_name || '') : '';
    ownerSearchQuery = '';
    ownerSearchResults = [];
    showOwnerSuggestions = false;
  }

  function clearOwner() {
    updateField('OwnerId', null);
    selectedOwnerDisplayName = '';
    ownerSearchQuery = '';
    ownerSearchResults = [];
    showOwnerSuggestions = false;
  }

  // Get owner display name - use local state in edit mode, or entity's Owner object in view mode
  $: ownerDisplayName = $editMode
    ? (selectedOwnerDisplayName || (activeEntity?.OwnerId ? `User #${activeEntity.OwnerId}` : ''))
    : (activeEntity?.Owner?.Name || (activeEntity?.OwnerId ? `User #${activeEntity.OwnerId}` : 'No Owner'));

  // Handle HasAdditionalArea toggle
  function handleAdditionalAreaChange(event) {
    const isChecked = event.detail.value;
    const currentSections = $currentEntity?.Sections || [];

    if (isChecked) {
      // Add Additional section if not present
      if (!currentSections.find(s => s.Name === SECTION_NAMES[2])) {
        updateField('Sections', [...currentSections, { Name: SECTION_NAMES[2], ItemPoints: null, MaxItemPoints: null, Description: null }]);
      }
    } else {
      // Remove Additional section
      updateField('Sections', currentSections.filter(s => s.Name !== SECTION_NAMES[2]));
    }
    updateField('HasAdditionalArea', isChecked);
  }

  // Handle MaxItemPoints change for a section
  function handleSectionPointsChange(sectionName, value) {
    const currentSections = $currentEntity?.Sections || [];
    const updatedSections = currentSections.map(s => {
      if (s.Name === sectionName) {
        return { ...s, ItemPoints: value, MaxItemPoints: value };
      }
      return s;
    });
    updateField('Sections', updatedSections);
  }

  // Get MaxItemPoints for a section
  function getSectionPoints(entity, sectionName) {
    const section = entity?.Sections?.find(s => s.Name === sectionName);
    return section?.ItemPoints ?? section?.MaxItemPoints ?? null;
  }

  // Wiki edit permissions - verified users can edit wiki data
  $: canEditWiki = user?.verified || user?.administrator;

  // Initialize edit state when user or entity changes
  $: if (user) {
    const editChange = isCreateMode ? (data.existingChange || null) : (canUsePendingChange ? resolvedPendingChange : null);
    initEditState(
      isCreateMode ? (data.existingChange?.data || emptyEntity) : shop,
      'Shop',
      isCreateMode,
      editChange
    );
  }

  // Set pending change when available
  $: if (resolvedPendingChange) {
    setExistingPendingChange(resolvedPendingChange);
    // Auto-enable viewing pending change for author or admin
    if (user && (resolvedPendingChange.author_id === user.id || user.grants?.includes('wiki.approve'))) {
      setViewingPendingChange(true);
    }
  } else {
    setExistingPendingChange(null);
    setViewingPendingChange(false);
  }

  // Active entity - shows edited data in edit mode, pending change data when viewing, otherwise original
  $: activeEntity = $editMode
    ? $currentEntity
    : $viewingPendingChange && $existingPendingChange?.data
      ? $existingPendingChange.data
      : shop;

  // Cleanup on destroy
  onDestroy(() => {
    resetEditState();
  });
  $: allItems = data.allItems || [];

  // Build navigation items from shops
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

  const shopColumnDefs = {
    location: {
      key: 'location',
      header: 'Location',
      width: '150px',
      filterPlaceholder: 'Calypso',
      getValue: (item) => getLocationShort(item),
      format: (v) => v || '-'
    },
    owner: {
      key: 'owner',
      header: 'Owner',
      width: '110px',
      filterPlaceholder: 'Owner',
      getValue: (item) => item?.Owner?.Name,
      format: (v) => v || '-'
    },
    items: {
      key: 'items',
      header: 'Items',
      width: '55px',
      filterPlaceholder: '>0',
      getValue: (item) => item?.InventoryGroups?.reduce((acc, g) => acc + (g?.Items?.length || 0), 0) || 0,
      format: (v) => v != null ? v : '-'
    },
    planet: {
      key: 'planet',
      header: 'Planet',
      width: '80px',
      filterPlaceholder: 'Calypso',
      getValue: (item) => item?.Planet?.Name,
      format: (v) => v || '-'
    },
    sections: {
      key: 'sections',
      header: 'Sections',
      width: '65px',
      filterPlaceholder: '>1',
      getValue: (item) => item?.Sections?.length || 0,
      format: (v) => v != null ? v : '-'
    }
  };

  const navTableColumns = [
    shopColumnDefs.location,
    shopColumnDefs.owner,
    shopColumnDefs.items
  ];

  const navFullWidthColumns = [
    ...navTableColumns,
    shopColumnDefs.planet,
    shopColumnDefs.sections
  ];

  const allAvailableColumns = Object.values(shopColumnDefs);

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Market', href: '/market' },
    { label: 'Shops', href: '/market/shops' },
    ...(activeEntity?.Name ? [{ label: activeEntity.Name }] : [])
  ];

  // SEO
  $: seoDescription = activeEntity?.Description ||
    `${activeEntity?.Name || 'Shop'} - Player shop on ${activeEntity?.Planet?.Name || 'Calypso'} in Entropia Universe.`;

  $: canonicalUrl = activeEntity?.Name
    ? `https://entropianexus.com/market/shops/${encodeURIComponentSafe(activeEntity.Name)}`
    : 'https://entropianexus.com/market/shops';

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    inventory: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-shop-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }

    // Fetch item details for the shop's inventory
    if (shop?.InventoryGroups) {
      fetchItemDetails();
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-shop-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== ITEM DETAILS FETCHING ==========
  let itemDetails = {};
  let itemsLoading = false;

  async function fetchItemDetails() {
    if (!shop?.InventoryGroups) return;

    const ids = Array.from(new Set(
      shop.InventoryGroups
        .flatMap(g => (g?.Items || []).map(i => i.ItemId ?? i.item_id))
        .filter(Boolean)
    ));

    if (ids.length === 0) {
      itemDetails = {};
      return;
    }

    itemsLoading = true;
    try {
      const results = await apiCall(fetch, `/items?Ids=${ids.join(',')}`);
      const map = {};
      (results || []).forEach(item => {
        if (item?.Id) map[item.Id] = item;
      });
      itemDetails = map;
    } catch (e) {
      console.error('Failed to fetch item details:', e);
      itemDetails = {};
    }
    itemsLoading = false;
  }

  // Refetch when shop changes
  $: if (shop?.Id) {
    fetchItemDetails();
  }

  // ========== SHOP CALCULATIONS ==========
  function getTotalItems(s) {
    if (!s?.InventoryGroups) return 0;
    return s.InventoryGroups.reduce((acc, g) => acc + (g?.Items?.length || 0), 0);
  }

  function getTotalGroups(s) {
    return s?.InventoryGroups?.filter(g => g?.Items?.length > 0).length || 0;
  }

  function hasCoordinates(s) {
    const coords = s?.Coordinates;
    return coords && (coords.Longitude != null || coords.Latitude != null);
  }

  function formatCoordinates(s) {
    const coords = s?.Coordinates;
    if (!coords) return null;

    const planet = s.Planet?.Properties?.TechnicalName || s.Planet?.Name || 'Unknown';
    const lon = coords.Longitude ?? 0;
    const lat = coords.Latitude ?? 0;
    const alt = coords.Altitude ?? 100;

    return `[${planet}, ${lon}, ${lat}, ${alt}, ${s.Name}]`;
  }

  function getPlanetBadgeClass(planetName) {
    if (!planetName) return '';
    const lower = planetName.toLowerCase().replace(/\s+/g, '-');
    return `planet-${lower}`;
  }

  function getSectionNames(s) {
    if (!s?.Sections) return [];
    return s.Sections.map(sec => sec.Name).filter(Boolean);
  }

  function getLocationShort(s) {
    const planet = s?.Planet?.Name;
    const coords = s?.Coordinates;
    const lon = coords?.Longitude;
    const lat = coords?.Latitude;
    if (lon != null || lat != null) {
      const coordPart = [lon, lat].filter(v => v != null).join(', ');
      return planet ? `${planet} ${coordPart}` : coordPart;
    }
    return planet || null;
  }

  // Check if user is the shop owner
  function isShopOwner(s, u) {
    if (!s || !u?.verified) return false;
    if (u?.administrator) return true;
    return s?.OwnerId === u?.id;
  }

  // Check if user can edit this shop (owner or manager)
  function canUserEditShop(s, u) {
    if (!s || !u?.verified) return false;
    if (u?.administrator) return true;

    // Owner check
    if (s?.OwnerId === u?.id) return true;

    // Manager check
    return s?.Managers?.some(manager => manager.user_id === u?.id) || false;
  }

  // Reactive calculations - use activeEntity for display
  $: totalItems = getTotalItems(activeEntity);
  $: totalGroups = getTotalGroups(activeEntity);
  $: hasLocation = hasCoordinates(activeEntity);
  $: coordinates = formatCoordinates(activeEntity);
  $: sectionNames = getSectionNames(activeEntity);
  // Owner/manager permissions still based on original shop data
  $: canEdit = canUserEditShop(shop, user);
  $: isOwner = isShopOwner(shop, user);

  // ========== DIALOG STATE ==========
  let managersDialogOpen = false;
  let inventoryDialogOpen = false;
  let shopManagers = [];

  // Fetch managers when opening dialog
  async function openManagersDialog() {
    if (!shop?.Name) return;

    try {
      const response = await fetch(`/api/shops/${encodeURIComponent(shop.Name)}/managers`);
      const result = await response.json();
      if (response.ok) {
        shopManagers = result.Managers || [];
      } else {
        console.error('Failed to fetch managers:', result.error);
        shopManagers = [];
      }
    } catch (e) {
      console.error('Error fetching managers:', e);
      shopManagers = [];
    }

    managersDialogOpen = true;
  }

  function openInventoryDialog() {
    inventoryDialogOpen = true;
  }

  function handleManagersSaved(event) {
    // Reload the page to get fresh data
    window.location.reload();
  }

  function handleInventorySaved(event) {
    // Reload the page to get fresh data
    window.location.reload();
  }
</script>

<WikiSEO
  title={activeEntity?.Name || 'Shops'}
  description={seoDescription}
  entityType="shop"
  entity={activeEntity}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Shops"
  {breadcrumbs}
  entity={activeEntity}
  entityType="Shop"
  basePath="/market/shops"
  {navItems}
  {navFilters}
  {navTableColumns}
  {navFullWidthColumns}
  navAllAvailableColumns={allAvailableColumns}
  navPageTypeId="shops"
  {user}
  editable={true}
  canEdit={canEditWiki}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
>
  {#if shop}
    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <EntityImageUpload
            entityId={activeEntity?.Id}
            entityName={activeEntity?.Name}
            entityType="shop"
            {user}
            isEditMode={$editMode}
            isCreateMode={isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit
              value={activeEntity?.Name || ''}
              path="Name"
              type="text"
              placeholder="Shop Name"
              required
            />
          </div>
          <div class="infobox-subtitle">
            <span class="planet-badge {getPlanetBadgeClass(activeEntity?.Planet?.Name)}">
              {activeEntity?.Planet?.Name || 'Unknown'}
            </span>
          </div>
        </div>

        <!-- Key Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Items</span>
            <span class="stat-value">{totalItems}</span>
          </div>
          {#if totalGroups > 0}
            <div class="stat-row primary">
              <span class="stat-label">Sections</span>
              <span class="stat-value">{totalGroups}</span>
            </div>
          {/if}
        </div>

        <!-- Owner Info -->
        <div class="stats-section">
          <div class="section-header-row">
            <h4 class="section-title">Owner</h4>
            {#if isOwner}
              <button class="edit-section-btn" on:click={openManagersDialog} title="Manage shop managers">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                  <circle cx="9" cy="7" r="4"></circle>
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                  <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                </svg>
              </button>
            {/if}
          </div>
          <div class="stat-row">
            <span class="stat-label">Name</span>
            <span class="stat-value">
              {#if $editMode}
                <div class="owner-picker">
                  {#if activeEntity?.OwnerId || selectedOwnerDisplayName}
                    <div class="selected-owner-chip">
                      <span class="owner-name">{ownerDisplayName}</span>
                      <button type="button" class="chip-remove" on:click={clearOwner}>×</button>
                    </div>
                  {:else}
                    <div class="owner-search-wrapper">
                      <input
                        type="text"
                        class="owner-search-input"
                        bind:value={ownerSearchQuery}
                        on:input={handleOwnerSearchInput}
                        on:focus={() => { if (ownerSearchResults.length > 0) showOwnerSuggestions = true; }}
                        on:blur={() => { setTimeout(() => showOwnerSuggestions = false, 150); }}
                        placeholder="Search for owner..."
                        autocomplete="off"
                      />
                      {#if isOwnerSearching}
                        <span class="search-spinner-small"></span>
                      {/if}
                    </div>
                    {#if showOwnerSuggestions && ownerSearchResults.length > 0}
                      <div class="owner-suggestions">
                        {#each ownerSearchResults as result}
                          <button
                            type="button"
                            class="owner-suggestion-item"
                            on:click={() => selectOwner(result)}
                          >
                            <span class="suggestion-name">{result.global_name || result.username}</span>
                            {#if result.eu_name}
                              <span class="suggestion-eu">EU: {result.eu_name}</span>
                            {/if}
                          </button>
                        {/each}
                      </div>
                    {/if}
                  {/if}
                </div>
              {:else}
                {ownerDisplayName}
              {/if}
            </span>
          </div>
          {#if activeEntity?.MaxGuests != null || $editMode}
            <div class="stat-row">
              <span class="stat-label">Max Guests</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.MaxGuests}
                  path="MaxGuests"
                  type="number"
                  min={0}
                />
              </span>
            </div>
          {/if}
          {#if activeEntity?.Managers?.length > 0}
            <div class="stat-row">
              <span class="stat-label">Managers</span>
              <span class="stat-value">{activeEntity.Managers.length}</span>
            </div>
          {/if}
        </div>

        <!-- Location -->
        <div class="stats-section">
          <h4 class="section-title">Location</h4>
          <div class="stat-row">
            <span class="stat-label">Planet</span>
            <span class="stat-value">
              {#if $editMode && !hasOwner}
                <!-- Planet editable only when no owner exists -->
                <InlineEdit
                  value={activeEntity?.Planet?.Name}
                  path="Planet.Name"
                  type="select"
                  options={[
                    { value: 'Calypso', label: 'Calypso' },
                    { value: 'ARIS', label: 'ARIS' },
                    { value: 'Arkadia', label: 'Arkadia' },
                    { value: 'Cyrene', label: 'Cyrene' },
                    { value: 'Monria', label: 'Monria' },
                    { value: 'ROCKtropia', label: 'Rocktropia' },
                    { value: 'Toulan', label: 'Toulan' },
                    { value: 'Next Island', label: 'Next Island' }
                  ]}
                />
              {:else}
                {activeEntity?.Planet?.Name || 'N/A'}
              {/if}
            </span>
          </div>
          {#if $editMode && !hasOwner}
            <!-- Coordinates editable only when no owner exists -->
            <div class="stat-row">
              <span class="stat-label">Longitude</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Coordinates?.Longitude}
                  path="Coordinates.Longitude"
                  type="number"
                  step={1}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Latitude</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Coordinates?.Latitude}
                  path="Coordinates.Latitude"
                  type="number"
                  step={1}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Altitude</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Coordinates?.Altitude}
                  path="Coordinates.Altitude"
                  type="number"
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

        <!-- Estate Areas -->
        {#if $editMode || sectionNames.length > 0}
          <div class="stats-section">
            <h4 class="section-title">Estate Areas</h4>
            {#if $editMode}
              <!-- Editable sections with MaxItemPoints -->
              <div class="section-edit-grid">
                <!-- Indoor (always present) -->
                <div class="section-edit-row">
                  <span class="section-name">Indoor</span>
                  <div class="section-points">
                    <InlineEdit
                      value={getSectionPoints(activeEntity, 'Indoor')}
                      type="number"
                      min={0}
                      step={1}
                      placeholder="Max Points"
                      on:change={(e) => handleSectionPointsChange('Indoor', e.detail.value)}
                    />
                    <span class="points-label">pts</span>
                  </div>
                </div>
                <!-- Display (always present) -->
                <div class="section-edit-row">
                  <span class="section-name">Display</span>
                  <div class="section-points">
                    <InlineEdit
                      value={getSectionPoints(activeEntity, 'Display')}
                      type="number"
                      min={0}
                      step={1}
                      placeholder="Max Points"
                      on:change={(e) => handleSectionPointsChange('Display', e.detail.value)}
                    />
                    <span class="points-label">pts</span>
                  </div>
                </div>
                <!-- Additional Area toggle -->
                <div class="section-edit-row additional-toggle">
                  <span class="section-name">
                    <InlineEdit
                      value={hasAdditionalArea}
                      type="checkbox"
                      on:change={handleAdditionalAreaChange}
                    />
                    <span class="toggle-label">Has Additional Area</span>
                  </span>
                </div>
                <!-- Additional (conditional) -->
                {#if hasAdditionalArea}
                  <div class="section-edit-row">
                    <span class="section-name">Additional</span>
                    <div class="section-points">
                      <InlineEdit
                        value={getSectionPoints(activeEntity, 'Additional')}
                        type="number"
                        min={0}
                        step={1}
                        placeholder="Max Points"
                        on:change={(e) => handleSectionPointsChange('Additional', e.detail.value)}
                      />
                      <span class="points-label">pts</span>
                    </div>
                  </div>
                {/if}
              </div>
            {:else}
              <!-- View mode: show section tags with optional points -->
              <div class="type-tags">
                {#each activeEntity?.Sections || [] as section}
                  {@const points = section.ItemPoints ?? section.MaxItemPoints}
                  <span class="type-tag" title={points != null ? `Max ${points} points` : ''}>
                    {section.Name}
                    {#if points != null}
                      <span class="tag-points">({points})</span>
                    {/if}
                  </span>
                {/each}
              </div>
            {/if}
          </div>
        {/if}

        <!-- Quick Link to Map -->
        {#if hasLocation && activeEntity?.Planet?.Name}
          <a href="/maps/{activeEntity.Planet.Name.toLowerCase().replace(/\s+/g, '')}" class="map-link-btn">
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
        <!-- Pending Change Banner -->
        {#if $existingPendingChange && !$editMode}
          <PendingChangeBanner
            pendingChange={$existingPendingChange}
            viewing={$viewingPendingChange}
            onToggle={() => setViewingPendingChange(!$viewingPendingChange)}
          />
        {/if}

        <h1 class="article-title">
          <InlineEdit
            value={activeEntity?.Name}
            type="text"
            path="Name"
            placeholder="Shop name"
          />
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={$currentEntity?.Description || ''}
              on:change={(e) => updateField('Description', e.detail)}
              placeholder="Describe this shop..."
            />
          {:else if activeEntity?.Description}
            <div class="description-content">{@html sanitizeHtml(activeEntity.Description)}</div>
          {:else}
            <div class="description-content placeholder">
              {activeEntity?.Name || 'This shop'} is a player-owned shop located on {activeEntity?.Planet?.Name || 'Calypso'}.
              {#if activeEntity?.Owner?.Name}
                It is owned by {activeEntity.Owner.Name}.
              {/if}
              {#if totalItems > 0}
                Currently stocking {totalItems} item{totalItems !== 1 ? 's' : ''} for sale.
              {:else}
                The owner has not yet added any items for display.
              {/if}
            </div>
          {/if}
        </div>

        <!-- Inventory Section -->
        <DataSection
          title="Inventory"
          icon=""
          bind:expanded={panelStates.inventory}
          subtitle="{totalItems} item{totalItems !== 1 ? 's' : ''}"
          on:toggle={savePanelStates}
        >
          <svelte:fragment slot="actions">
            {#if canEdit}
              <button class="edit-btn" on:click={openInventoryDialog} title="Edit inventory">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
                <span>Edit</span>
              </button>
            {/if}
          </svelte:fragment>
          {#if itemsLoading}
            <div class="loading-indicator">Loading inventory...</div>
          {:else}
            <ShopInventory
              inventoryGroups={activeEntity?.InventoryGroups}
              {itemDetails}
            />
          {/if}
        </DataSection>
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Shops</h2>
      <p>Select a shop from the list to view details.</p>
      <p class="hint">Player-owned shops sell various items at player-set prices.</p>
    </div>
  {/if}
</WikiPage>

<!-- Dialogs -->
{#if shop}
  <ShopManagersDialog
    shopName={shop.Name}
    bind:open={managersDialogOpen}
    managers={shopManagers}
    on:close={() => managersDialogOpen = false}
    on:saved={handleManagersSaved}
  />

  <ShopInventoryDialog
    shopName={shop.Name}
    bind:open={inventoryDialogOpen}
    inventoryGroups={shop.InventoryGroups || []}
    {itemDetails}
    on:close={() => inventoryDialogOpen = false}
    on:saved={handleInventorySaved}
  />
{/if}

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

  .entity-icon-wrapper {
    position: relative;
    width: 100%;
    aspect-ratio: 1;
    margin-bottom: 12px;
    box-sizing: border-box;
  }

  .icon-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--bg-color, var(--primary-color));
    border: 2px dashed var(--border-color, #555);
    border-radius: 8px;
    color: var(--text-muted, #999);
    box-sizing: border-box;
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

  .section-header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .section-header-row .section-title {
    margin: 0;
    padding-bottom: 0;
    border-bottom: none;
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

  .edit-section-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    background-color: var(--accent-color, #4a9eff);
    border: none;
    border-radius: 4px;
    color: white;
    cursor: pointer;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  }

  .edit-section-btn:hover {
    background-color: var(--accent-color-hover, #3a8eef) !important;
    transform: scale(1.05);
  }

  .edit-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 500;
    background-color: var(--accent-color, #4a9eff);
    border: none;
    border-radius: 4px;
    color: white;
    cursor: pointer;
  }

  .edit-btn:hover {
    background-color: var(--accent-color-hover, #3a8eef) !important;
  }

  .edit-btn svg {
    flex-shrink: 0;
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

  .type-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .type-tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    font-size: 13px;
    font-weight: 500;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .tag-points {
    font-size: 11px;
    color: var(--text-muted, #999);
    font-weight: 400;
  }

  /* Section editing grid */
  .section-edit-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .section-edit-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 8px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
    border: 1px solid var(--border-color, #555);
  }

  .section-edit-row :global(.edit-input),
  .section-edit-row :global(.edit-select) {
    font-size: 13px;
    padding: 4px 8px;
  }

  .section-edit-row.additional-toggle {
    background-color: transparent;
    border: none;
    padding: 4px 0;
  }

  .section-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-color);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .toggle-label {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .section-points {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .points-label {
    font-size: 11px;
    color: var(--text-muted, #999);
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

  /* Pending Change Banner */
  .pending-change-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 16px;
    background-color: var(--warning-bg, #fef3c7);
    border: 1px solid var(--warning-border, #f59e0b);
    border-radius: 8px;
    margin-bottom: 16px;
  }

  .pending-info {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 14px;
    color: var(--warning-text, #92400e);
  }

  .pending-info svg {
    flex-shrink: 0;
    stroke: var(--warning-text, #92400e);
  }

  .toggle-pending-btn {
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 500;
    background-color: var(--bg-color, white);
    border: 1px solid var(--warning-border, #f59e0b);
    border-radius: 4px;
    color: var(--warning-text, #92400e);
    cursor: pointer;
    white-space: nowrap;
  }

  .toggle-pending-btn:hover {
    background-color: var(--warning-border, #f59e0b);
    color: white;
  }

  .toggle-pending-btn.active {
    background-color: var(--warning-border, #f59e0b);
    color: white;
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

  .loading-indicator {
    text-align: center;
    padding: 40px 20px;
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

  /* Owner picker styles */
  .owner-picker {
    position: relative;
    width: 100%;
  }

  .selected-owner-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    background: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    font-size: 12px;
  }

  .owner-name {
    color: var(--text-color);
  }

  .chip-remove {
    background: transparent;
    border: none;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 14px;
    font-weight: bold;
    padding: 0;
    line-height: 1;
    width: 18px;
    height: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    transition: all 0.15s;
  }

  .chip-remove:hover {
    color: white;
    background: var(--error-color, #ef4444);
  }

  .owner-search-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .owner-search-input {
    width: 100%;
    padding: 6px 10px;
    font-size: 12px;
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .search-spinner-small {
    position: absolute;
    right: 8px;
    width: 12px;
    height: 12px;
    border: 2px solid var(--border-color, #555);
    border-top-color: var(--accent-color, #4a9eff);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .owner-suggestions {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    margin-top: 4px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    max-height: 200px;
    overflow-y: auto;
    z-index: 100;
  }

  .owner-suggestion-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    width: 100%;
    padding: 8px 10px;
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
    color: var(--text-color);
    transition: background-color 0.15s;
  }

  .owner-suggestion-item:hover {
    background: var(--hover-color);
  }

  .suggestion-name {
    font-size: 13px;
    font-weight: 500;
  }

  .suggestion-eu {
    font-size: 11px;
    color: var(--text-muted, #999);
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

    .entity-icon-wrapper {
      max-width: 320px;
      margin: 0 auto 12px;
    }

    .edit-btn {
      padding: 5px 10px;
      font-size: 12px;
    }

    .edit-btn span {
      display: none;
    }

    .edit-section-btn {
      width: 26px;
      height: 26px;
    }
  }
</style>
