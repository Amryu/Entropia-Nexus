<!--
  @component Locations Wiki Page
  Unified wiki page for all location types with type filtering.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onDestroy } from 'svelte';
  import { encodeURIComponentSafe, getLatestPendingUpdate, loadEditDeps } from '$lib/util';
  import { getPlanetNavFilter } from '$lib/mapUtil';
  import { sanitizeHtml } from '$lib/sanitize';

  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiNavigation from '$lib/components/wiki/WikiNavigation.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';
  import WaypointInput from '$lib/components/wiki/WaypointInput.svelte';
  import WaypointCopyButton from '$lib/components/wiki/WaypointCopyButton.svelte';
  import LocationMapEmbed from '$lib/components/wiki/locations/LocationMapEmbed.svelte';
  import { getWaypoint } from '$lib/mapUtil';

  import {
    editMode,
    initEditState,
    resetEditState,
    currentEntity,
    existingPendingChange,
    viewingPendingChange,
    setExistingPendingChange,
    setViewingPendingChange,
    updateField
  } from '$lib/stores/wikiEditState.js';

  export let data;

  // Lazy-load edit dependencies when edit mode activates
  let editDepsLoading = false;
  $: if ($editMode && data.mobMaturities === null && !editDepsLoading) {
    editDepsLoading = true;
    loadEditDeps([
      { key: 'mobMaturities', url: '/api/mobmaturities' }
    ]).then(deps => {
      data = { ...data, ...deps };
      editDepsLoading = false;
    });
  }

  $: user = data.session?.user;
  $: allLocations = data.allLocations || data.locations || [];
  $: facilitiesList = data.facilitiesList || [];
  $: planetsList = data.planetsList || [];
  $: mobMaturities = data.mobMaturities || [];
  $: pendingChange = data.pendingChange;
  $: canCreateNew = data.canCreateNew ?? true;
  $: userPendingCreates = data.userPendingCreates || [];
  $: userPendingUpdates = data.userPendingUpdates || [];
  $: isCreateMode = data.isCreateMode || false;
  $: currentChangeId = $page.url.searchParams.get('changeId');
  $: disambiguation = data.disambiguation || null;

  // URL-based type (used for breadcrumbs, canonical URLs, etc.)
  $: currentType = data.type || null;

  // Local filter state - only changes when explicitly clicking filter buttons
  // Not when navigating to items (which include type in URL for disambiguation)
  let selectedFilter = null;
  let filterInitialized = false;

  // Initialize filter from URL once on mount/first data load
  $: if (!filterInitialized && data.type !== undefined) {
    selectedFilter = data.type || null;
    filterInitialized = true;
  }

  // Update filter when navigating to a filter-only URL (no item selected, not create mode)
  // This allows filter buttons to work while item clicks don't change the filter
  $: if (filterInitialized && !data.object && !isCreateMode && !disambiguation) {
    // We're on a filter view (no specific item), update the filter
    if (data.type !== selectedFilter) {
      selectedFilter = data.type || null;
    }
  }

  // Build a set of names that appear more than once for sidebar href generation
  $: duplicateNames = (() => {
    const nameCounts = {};
    for (const loc of allLocations) {
      nameCounts[loc.Name] = (nameCounts[loc.Name] || 0) + 1;
    }
    return new Set(Object.keys(nameCounts).filter(name => nameCounts[name] > 1));
  })();

  // Filter locations based on selected filter (client-side filtering)
  $: isOtherFilter = selectedFilter === 'other';
  $: selectedFilterBtn = selectedFilter ? NAV_TYPE_BUTTONS.find(b => b.slug === selectedFilter) : null;
  $: selectedFilterTypes = selectedFilterBtn?.types ?? (selectedFilter ? getTypesFromSlug(selectedFilter) : null);
  $: selectedFilterAreaTypes = selectedFilterBtn?.areaTypes ?? null;
  $: locationsList = isOtherFilter
    ? allLocations.filter(loc => {
        const locType = loc.Properties?.Type;
        return !locType || !CATEGORIZED_TYPES.has(locType);
      })
    : (selectedFilterTypes || selectedFilterAreaTypes)
      ? allLocations.filter(loc => {
          const locType = loc.Properties?.Type;
          const locAreaType = loc.Properties?.AreaType;
          if (selectedFilterAreaTypes && selectedFilterTypes) {
            return selectedFilterTypes.includes(locType) && selectedFilterAreaTypes.includes(locAreaType);
          } else if (selectedFilterAreaTypes) {
            return selectedFilterAreaTypes.includes(locAreaType);
          } else {
            return locType && selectedFilterTypes.includes(locType);
          }
        })
      : allLocations;

  $: entityType = 'Location';
  $: entity = data.object;
  $: entityId = entity?.Id ?? null;
  $: userPendingUpdate = getLatestPendingUpdate(userPendingUpdates, entityId);
  $: resolvedPendingChange = userPendingUpdate || pendingChange;
  $: canUsePendingChange = !!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve')));

  // Location type definitions (for editing/display)
  const LOCATION_TYPES = [
    { value: 'Teleporter', label: 'Teleporter' },
    { value: 'RevivalPoint', label: 'Revival Point' },
    { value: 'Npc', label: 'NPC' },
    { value: 'Interactable', label: 'Interactable' },
    { value: 'InstanceEntrance', label: 'Instance Entrance' },
    { value: 'Area', label: 'Area' },
    { value: 'Estate', label: 'Estate' },
    { value: 'Outpost', label: 'Outpost' },
    { value: 'Camp', label: 'Camp' },
    { value: 'City', label: 'City' },
    { value: 'Vendor', label: 'Vendor' }
  ];

  // Navigation type buttons (merged categories with plurals)
  const NAV_TYPE_BUTTONS = [
    { slug: 'teleporters', label: 'Teleporters', types: ['Teleporter'] },
    { slug: 'npcs', label: 'NPCs', types: ['Npc'] },
    { slug: 'areas', label: 'Areas', types: ['Area'] },
    { slug: 'estates', label: 'Estates', types: ['Estate'] },
    { slug: 'settlements', label: 'Settlements', types: ['Outpost', 'Camp', 'City'] },
    { slug: 'waveevents', label: 'Wave Events', types: ['Area'], areaTypes: ['WaveEventArea'] },
    { slug: 'instances', label: 'Instances', types: ['InstanceEntrance'] },
    { slug: 'vendors', label: 'Vendors', types: ['Vendor'] },
    { slug: 'other', label: 'Other', types: null } // Catches types not in other categories
  ];

  // All types explicitly assigned to a filter category (for "Other" exclusion)
  const CATEGORIZED_TYPES = new Set(
    NAV_TYPE_BUTTONS.filter(b => b.types).flatMap(b => b.types)
  );

  // Map URL slug to type values for filtering
  // Returns an array of types for inclusion, or null for "all"
  // For 'other', returns null (handled separately via isOtherFilter)
  function getTypesFromSlug(slug) {
    if (!slug) return null;
    if (slug === 'other') return null; // Handled by exclusion logic
    const btn = NAV_TYPE_BUTTONS.find(b => b.slug === slug);
    if (btn) return btn.types;
    // Fallback: try to match single type
    const singleType = LOCATION_TYPES.find(t => t.value.toLowerCase() === slug);
    return singleType ? [singleType.value] : null;
  }

  // Get display label for a type slug
  function getTypeLabel(slug) {
    if (!slug) return null;
    const btn = NAV_TYPE_BUTTONS.find(b => b.slug === slug);
    if (btn) return btn.label;
    const singleType = LOCATION_TYPES.find(t => t.value.toLowerCase() === slug);
    return singleType?.label || slug;
  }

  const AREA_TYPES = [
    { value: 'PvpArea', label: 'PvP Area' },
    { value: 'PvpLootArea', label: 'PvP Loot Area' },
    { value: 'MobArea', label: 'Mob Area' },
    { value: 'LandArea', label: 'Land Area' },
    { value: 'WaveEventArea', label: 'Wave Event' },
    { value: 'ZoneArea', label: 'Zone Area' },
    { value: 'CityArea', label: 'City Area' },
    { value: 'EstateArea', label: 'Estate Area' },
    { value: 'EventArea', label: 'Event Area' }
  ];

  const SHAPE_TYPES = [
    { value: 'Point', label: 'Point' },
    { value: 'Circle', label: 'Circle' },
    { value: 'Rectangle', label: 'Rectangle' },
    { value: 'Polygon', label: 'Polygon' }
  ];

  // All planets for dropdown (filter out generic "Entropia Universe" entry)
  $: planetOptions = (planetsList || [])
    .filter(p => p.Id > 0)
    .map(p => ({ value: p.Name, label: p.Name }));

  $: facilityOptions = (facilitiesList || []).map(f => ({
    value: f.Name,
    label: f.Name
  }));

  $: parentLocationOptions = (allLocations || [])
    .filter(loc => loc.Id !== activeLocation?.Id) // Exclude self
    .map(loc => ({
      value: String(loc.Id),
      label: `${loc.Name} (${loc.Properties?.Type || 'Unknown'})`
    }));

  // Get label from options by value (for SearchInput display)
  function getOptionLabel(options, value) {
    if (!value) return '';
    const opt = options.find(o => o.value === String(value));
    return opt?.label || '';
  }

  // Get default type based on selected filter
  function getDefaultType() {
    if (!selectedFilter) return 'Teleporter';
    const types = getTypesFromSlug(selectedFilter);
    // Return the first type in the filter, or Teleporter as fallback
    return types?.[0] || 'Teleporter';
  }

  // Empty location template (reactive to use current type filter)
  $: emptyLocation = {
    Id: null,
    Name: '',
    Properties: {
      Type: getDefaultType(),
      Description: '',
      Coordinates: {
        Longitude: null,
        Latitude: null,
        Altitude: null
      },
      TechnicalId: null
    },
    Planet: { Name: 'Calypso' },
    ParentLocation: null,
    Facilities: [],
    Sections: [],
    Waves: []
  };

  // Track initialization to prevent re-init during editing
  // Include currentChangeId in key to handle URL-based navigation between create changes
  // Only reinitialize when data is consistent (changeId matches existingChange.id or both are absent)
  let lastInitKey = null;
  $: {
    // Check if data is consistent - URL changeId should match loaded existingChange.id in create mode
    const dataIsConsistent = !isCreateMode || !currentChangeId || (data.existingChange?.id && String(data.existingChange.id) === String(currentChangeId));
    const initKey = `${entityType}-${entity?.Id ?? 'new'}-${isCreateMode}-${currentChangeId ?? 'none'}-${data.existingChange?.id ?? 'none'}`;
    if (user && initKey !== lastInitKey && dataIsConsistent) {
      lastInitKey = initKey;
      const existingChange = data.existingChange || null;
      const initialEntity = isCreateMode
        ? (existingChange?.data || emptyLocation)
        : entity;
      const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
      initEditState(initialEntity, entityType, isCreateMode, editChange);
    }
  }

  $: if (resolvedPendingChange) {
    setExistingPendingChange(resolvedPendingChange);
  } else {
    setExistingPendingChange(null);
    setViewingPendingChange(false);
  }

  // Detect if we're in a transitional state (URL changed but data hasn't loaded yet)
  $: isDataStale = isCreateMode && currentChangeId && data.existingChange?.id && String(data.existingChange.id) !== String(currentChangeId);

  $: activeEntity = $editMode && !isDataStale
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : entity;

  $: activeLocation = activeEntity;
  // WaveEventArea locations have Type='Area' and AreaType='WaveEventArea'
  $: locationType = activeLocation?.Properties?.AreaType === 'WaveEventArea'
    ? 'WaveEventArea'
    : (activeLocation?.Properties?.Type || 'Teleporter');

  // Settlement types that have facilities
  const SETTLEMENT_TYPES = ['Outpost', 'Camp', 'City'];
  $: isSettlement = SETTLEMENT_TYPES.includes(locationType);

  // Auto-set EstateType when type changes to Estate (required for bot extension handling)
  $: if ($editMode && locationType === 'Estate' && !activeLocation?.Properties?.EstateType) {
    updateField('Properties.EstateType', 'Apartment');
  }

  // Look up the full planet object for the map embed (needs Map properties for coordinate conversion)
  $: activePlanet = planetsList?.find(p => p.Name === activeLocation?.Planet?.Name) || null;

  // Base path for navigation - include selected filter so it persists when navigating to creates
  $: effectiveBasePath = selectedFilter
    ? `/information/locations/${selectedFilter}`
    : '/information/locations';

  // Filter pending creates to show in correct type category
  // When on a type filter, only show creates matching that type
  // When on "Other" filter, show creates with types not in other categories
  // When on "All" (no filter), show all pending creates
  $: filteredPendingCreates = isOtherFilter
    ? (userPendingCreates || []).filter(change => {
        const changeType = change.data?.Properties?.Type;
        return !changeType || !CATEGORIZED_TYPES.has(changeType);
      })
    : (selectedFilterTypes || selectedFilterAreaTypes)
      ? (userPendingCreates || []).filter(change => {
          const changeType = change.data?.Properties?.Type;
          const changeAreaType = change.data?.Properties?.AreaType;
          if (selectedFilterAreaTypes && selectedFilterTypes) {
            return selectedFilterTypes.includes(changeType) && selectedFilterAreaTypes.includes(changeAreaType);
          } else if (selectedFilterAreaTypes) {
            return selectedFilterAreaTypes.includes(changeAreaType);
          } else {
            return changeType && selectedFilterTypes.includes(changeType);
          }
        })
      : userPendingCreates || [];

  onDestroy(() => {
    resetEditState();
  });

  function getTypeSlug(type) {
    return type ? type.toLowerCase() : null;
  }

  // Type navigation buttons for WikiNavigation filters prop (href-based, displayed below search)
  // Uses selectedFilter for active state (local filter state, not URL-based)
  $: typeNavFilters = [
    { label: 'All', href: '/information/locations', active: !selectedFilter, title: 'All locations' },
    ...NAV_TYPE_BUTTONS.map(btn => ({
      label: btn.label,
      href: `/information/locations/${btn.slug}`,
      active: selectedFilter === btn.slug,
      title: btn.label
    }))
  ];

  function getSidebarHref(item, basePath) {
    const slug = encodeURIComponentSafe(item.Name);
    const typeSlug = item.Properties?.AreaType === 'WaveEventArea'
      ? 'waveevents'
      : getTypeSlug(item.Properties?.Type);
    const baseUrl = typeSlug
      ? `/information/locations/${typeSlug}/${slug}`
      : `/information/locations/${slug}`;
    // Append ?id= for duplicate names to disambiguate
    if (duplicateNames.has(item.Name)) {
      return `${baseUrl}?id=${item.Id}`;
    }
    return baseUrl;
  }

  // Planet filter (value-based, includes sub-planets)
  const planetFilters = [getPlanetNavFilter('Planet.Name')];

  $: breadcrumbs = [
    { label: 'Information', href: '/information' },
    { label: 'Locations', href: '/information/locations' },
    ...(currentType ? [{ label: getTypeLabel(currentType) || currentType, href: `/information/locations/${currentType}` }] : []),
    ...(activeEntity?.Name
      ? [{ label: activeEntity.Name }]
      : isCreateMode
        ? [{ label: 'New Location' }]
        : [])
  ];

  $: seoDescription = activeLocation?.Properties?.Description
    || `${activeLocation?.Name || 'Location'} reference data for Entropia Universe.`;

  $: canonicalUrl = activeEntity?.Name
    ? `https://entropianexus.com/information/locations/${activeLocation?.Properties?.AreaType === 'WaveEventArea' ? 'waveevents' : (getTypeSlug(activeLocation?.Properties?.Type) || '')}/${encodeURIComponentSafe(activeEntity.Name)}`
    : 'https://entropianexus.com/information/locations';

  const seoColumns = [
    { key: 'Properties.Type', header: 'Type' },
    { key: 'Planet.Name', header: 'Planet' }
  ];

  // Table columns for expanded/full-width views
  const locationColumnDefs = {
    type: {
      key: 'type',
      header: 'Type',
      width: '85px',
      filterPlaceholder: 'Teleporter',
      getValue: (item) => item.Properties?.Type,
      format: (v) => v || '-'
    },
    planet: {
      key: 'planet',
      header: 'Planet',
      width: '75px',
      filterPlaceholder: 'Calypso',
      getValue: (item) => item.Planet?.Name,
      format: (v) => v || '-'
    },
    coordinates: {
      key: 'coordinates',
      header: 'Coordinates',
      width: '110px',
      getValue: (item) => {
        const coords = item.Properties?.Coordinates;
        if (coords?.Longitude == null && coords?.Latitude == null) return null;
        return (coords.Longitude ?? 0) + (coords.Latitude ?? 0) * 100000;
      },
      format: (v, item) => {
        const coords = item?.Properties?.Coordinates;
        if (coords?.Longitude == null && coords?.Latitude == null) return '-';
        return `${coords.Longitude ?? 0}, ${coords.Latitude ?? 0}`;
      }
    },
    parent: {
      key: 'parent',
      header: 'Parent',
      width: '100px',
      getValue: (item) => item.ParentLocation?.Name,
      format: (v) => v || '-'
    },
    technicalId: {
      key: 'technicalId',
      header: 'Tech ID',
      width: '65px',
      getValue: (item) => item.Properties?.TechnicalId,
      format: (v) => v != null ? v : '-'
    }
  };

  const navTableColumns = [
    locationColumnDefs.type,
    locationColumnDefs.planet,
    locationColumnDefs.coordinates
  ];

  const navFullWidthColumns = [
    locationColumnDefs.type,
    locationColumnDefs.planet,
    locationColumnDefs.coordinates,
    locationColumnDefs.parent
  ];

  const allAvailableColumns = Object.values(locationColumnDefs);

  $: navPageTypeId = `locations-${selectedFilter || 'all'}`;

  // Facilities management
  function addFacility(facilityName) {
    const current = activeLocation?.Facilities || [];
    if (current.some(f => f.Name === facilityName)) return;
    const facility = facilitiesList.find(f => f.Name === facilityName);
    if (!facility) return;
    updateField('Facilities', [...current, { Id: facility.Id, Name: facility.Name }]);
  }

  function removeFacility(facilityName) {
    const current = activeLocation?.Facilities || [];
    updateField('Facilities', current.filter(f => f.Name !== facilityName));
  }

  // Estate sections management
  function addSection() {
    const current = activeLocation?.Sections || [];
    updateField('Sections', [...current, { Name: '', Description: null, ItemPoints: null }]);
  }

  function updateSection(index, field, value) {
    const current = activeLocation?.Sections || [];
    const updated = current.map((s, i) => i === index ? { ...s, [field]: value } : s);
    updateField('Sections', updated);
  }

  function removeSection(index) {
    const current = activeLocation?.Sections || [];
    updateField('Sections', current.filter((_, i) => i !== index));
  }

  // Wave event waves management
  let expandedWaves = {};

  function toggleWave(index) {
    expandedWaves[index] = !expandedWaves[index];
    expandedWaves = expandedWaves; // Trigger reactivity
  }

  function addWave() {
    const current = activeLocation?.Waves || [];
    const nextIndex = current.length > 0 ? Math.max(...current.map(w => w.WaveIndex)) + 1 : 1;
    const newList = [...current, { Id: null, WaveIndex: nextIndex, TimeToComplete: null, MobMaturities: [] }];
    updateField('Waves', newList);
    // Expand the new wave
    expandedWaves[newList.length - 1] = true;
  }

  function updateWave(index, field, value) {
    const current = activeLocation?.Waves || [];
    const updated = current.map((w, i) => i === index ? { ...w, [field]: value } : w);
    updateField('Waves', updated);
  }

  function removeWave(index) {
    const current = activeLocation?.Waves || [];
    updateField('Waves', current.filter((_, i) => i !== index));
    // Clean up expanded state
    delete expandedWaves[index];
  }

  function addWaveMaturity(waveIndex, maturityId) {
    const current = activeLocation?.Waves || [];
    const wave = current[waveIndex];
    if (!wave) return;
    const maturities = wave.MobMaturities || [];
    if (maturities.includes(Number(maturityId))) return;
    const updated = current.map((w, i) => i === waveIndex ? { ...w, MobMaturities: [...maturities, Number(maturityId)] } : w);
    updateField('Waves', updated);
  }

  function removeWaveMaturity(waveIndex, maturityId) {
    const current = activeLocation?.Waves || [];
    const wave = current[waveIndex];
    if (!wave) return;
    const maturities = wave.MobMaturities || [];
    const updated = current.map((w, i) => i === waveIndex ? { ...w, MobMaturities: maturities.filter(m => m !== Number(maturityId)) } : w);
    updateField('Waves', updated);
  }

  function getMaturityName(maturityId) {
    const m = mobMaturities.find(mat => mat.Id === Number(maturityId));
    return m ? `${m.Mob?.Name || 'Mob'} - ${m.Name || 'Unknown'}` : `Maturity #${maturityId}`;
  }

  // Calculate distance between two locations (2D distance)
  function getDistanceMeters(a, b) {
    const ax = a?.Properties?.Coordinates?.Longitude ?? a?.x;
    const ay = a?.Properties?.Coordinates?.Latitude ?? a?.y;
    const bx = b?.Properties?.Coordinates?.Longitude ?? b?.x;
    const by = b?.Properties?.Coordinates?.Latitude ?? b?.y;
    if (ax == null || ay == null || bx == null || by == null) return null;
    const dx = ax - bx;
    const dy = ay - by;
    return Math.sqrt(dx * dx + dy * dy);
  }

  // Get 3 closest teleporters to the current location
  function getClosestTeleporters(location, allLocs) {
    if (!location) return [];
    const teleporters = (allLocs || []).filter(
      loc => loc.Properties?.Type === 'Teleporter' &&
        loc.Planet?.Name === location.Planet?.Name // Same planet only
    );
    return teleporters
      .map(tp => ({
        ...tp,
        _distance: getDistanceMeters(location, tp)
      }))
      .filter(tp => tp._distance != null && tp.Id !== location.Id)
      .sort((a, b) => a._distance - b._distance)
      .slice(0, 3);
  }

  $: closestTeleporters = getClosestTeleporters(activeLocation, allLocations);

  // Get map URL for current location
  function getMapUrl(location) {
    if (!location?.Planet?.Name) return '/maps/calypso';
    const planetSlug = location.Planet.Name.toLowerCase().replace(/[^a-z0-9]/g, '');
    return `/maps/${planetSlug}`;
  }

  // Build waypoint value object for WaypointInput (edit mode)
  $: waypointValue = {
    planet: activeLocation?.Planet?.Name || 'Calypso',
    x: activeLocation?.Properties?.Coordinates?.Longitude ?? null,
    y: activeLocation?.Properties?.Coordinates?.Latitude ?? null,
    z: activeLocation?.Properties?.Coordinates?.Altitude ?? null,
    name: activeLocation?.Name || ''
  };

  // Build waypoint string for WaypointCopyButton (view mode)
  $: waypointString = activeLocation?.Properties?.Coordinates?.Longitude != null
    ? getWaypoint(
        activeLocation?.Planet?.Name || 'Calypso',
        activeLocation?.Properties?.Coordinates?.Longitude,
        activeLocation?.Properties?.Coordinates?.Latitude,
        activeLocation?.Properties?.Coordinates?.Altitude ?? 100,
        activeLocation?.Name || ''
      )
    : '';

  // Nearby locations for map embed (land areas and teleporters on the same planet)
  $: nearbyMapLocations = (allLocations || []).filter(loc => {
    // Must be on the same planet
    if (loc.Planet?.Name !== activeLocation?.Planet?.Name) return false;
    // Only include land areas and teleporters
    const type = loc.Properties?.Type;
    const areaType = loc.Properties?.AreaType;
    return type === 'Teleporter' || areaType === 'LandArea';
  });

  // Handle waypoint change in edit mode
  function handleWaypointChange(detail) {
    if (detail.x !== undefined) updateField('Properties.Coordinates.Longitude', detail.x);
    if (detail.y !== undefined) updateField('Properties.Coordinates.Latitude', detail.y);
    if (detail.z !== undefined) updateField('Properties.Coordinates.Altitude', detail.z);
  }

  // User search state for estate owner picker
  let ownerSearchQuery = '';
  let ownerSearchResults = [];
  let showOwnerSuggestions = false;
  let isOwnerSearching = false;
  let ownerSearchTimeout = null;
  // Local display name for owner during editing (not saved to entity)
  let selectedOwnerDisplayName = '';

  // Search users as they type (for estate owner)
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
    // Store ID as string to avoid precision loss with large Discord snowflakes
    updateField('Properties.OwnerId', u ? String(u.id) : null);
    // Keep display name locally for the editing session
    selectedOwnerDisplayName = u ? (u.eu_name || u.global_name || '') : '';
    ownerSearchQuery = '';
    ownerSearchResults = [];
    showOwnerSuggestions = false;
  }

  function clearOwner() {
    updateField('Properties.OwnerId', null);
    selectedOwnerDisplayName = '';
    ownerSearchQuery = '';
    ownerSearchResults = [];
    showOwnerSuggestions = false;
  }

  // Get owner display name - use local state in edit mode, or entity's Owner object in view mode
  $: ownerDisplayName = $editMode
    ? (selectedOwnerDisplayName || (activeLocation?.Properties?.OwnerId ? `User #${activeLocation.Properties.OwnerId}` : ''))
    : (activeLocation?.Owner?.Name || (activeLocation?.Properties?.OwnerId ? `User #${activeLocation.Properties.OwnerId}` : 'Unknown'));

  // Maturity search state (per wave)
  let maturitySearchQueries = {};
  let maturitySearchResults = {};
  let showMaturitySuggestions = {};

  function handleMaturitySearchInput(waveIdx) {
    const query = (maturitySearchQueries[waveIdx] || '').trim().toLowerCase();

    if (query.length < 2) {
      maturitySearchResults[waveIdx] = [];
      showMaturitySuggestions[waveIdx] = false;
      maturitySearchResults = maturitySearchResults;
      showMaturitySuggestions = showMaturitySuggestions;
      return;
    }

    // Get current wave's maturities to exclude
    const wave = (activeLocation?.Waves || [])[waveIdx];
    const existingIds = new Set(wave?.MobMaturities || []);

    // Filter mobMaturities client-side
    const results = (mobMaturities || [])
      .filter(m => {
        if (existingIds.has(m.Id)) return false;
        const mobName = (m.Mob?.Name || '').toLowerCase();
        const matName = (m.Name || '').toLowerCase();
        return mobName.includes(query) || matName.includes(query);
      })
      .slice(0, 15); // Limit results

    maturitySearchResults[waveIdx] = results;
    showMaturitySuggestions[waveIdx] = results.length > 0;
    maturitySearchResults = maturitySearchResults;
    showMaturitySuggestions = showMaturitySuggestions;
  }

  function selectMaturity(waveIdx, maturity) {
    addWaveMaturity(waveIdx, maturity.Id);
    maturitySearchQueries[waveIdx] = '';
    maturitySearchResults[waveIdx] = [];
    showMaturitySuggestions[waveIdx] = false;
    maturitySearchQueries = maturitySearchQueries;
    maturitySearchResults = maturitySearchResults;
    showMaturitySuggestions = showMaturitySuggestions;
  }

  function hideMaturitySuggestions(waveIdx) {
    setTimeout(() => {
      showMaturitySuggestions[waveIdx] = false;
      showMaturitySuggestions = showMaturitySuggestions;
    }, 150);
  }

  // Get current area shape (for shape data editor)
  $: currentShape = activeLocation?.Properties?.Shape || 'Point';

  // Shape data helpers
  function updateShapeData(field, value) {
    const currentData = activeLocation?.Properties?.Data || {};
    updateField('Properties.Data', { ...currentData, [field]: value });
  }

  // Parse polygon vertices from text input (comma or space-separated pairs)
  function parsePolygonVertices(text) {
    const numbers = text.match(/-?\d+\.?\d*/g);
    if (!numbers || numbers.length < 4) return null;
    const vertices = [];
    for (let i = 0; i + 1 < numbers.length; i += 2) {
      vertices.push(parseFloat(numbers[i]), parseFloat(numbers[i + 1]));
    }
    return vertices;
  }

  // Format polygon vertices for display
  function formatPolygonVertices(vertices) {
    if (!vertices || !Array.isArray(vertices)) return '';
    const pairs = [];
    for (let i = 0; i + 1 < vertices.length; i += 2) {
      pairs.push(`${vertices[i]}, ${vertices[i + 1]}`);
    }
    return pairs.join('\n');
  }

</script>

<WikiSEO
  title={activeEntity?.Name || 'Locations'}
  description={seoDescription}
  entityType="location"
  entity={activeEntity}
  imageUrl={null}
  sidebarColumns={seoColumns}
  sidebarEntity={activeEntity}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Locations"
  {breadcrumbs}
  entity={activeEntity}
  basePath={effectiveBasePath}
  {user}
  editable={true}
  canEdit={user?.verified || user?.grants?.includes('wiki.edit')}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
  {editDepsLoading}
>
  <svelte:fragment slot="sidebar">
    <WikiNavigation
      items={locationsList}
      linkFilters={typeNavFilters}
      filters={planetFilters}
      basePath={effectiveBasePath}
      title="Locations"
      currentSlug={activeEntity?.Name}
      currentItemId={activeEntity?.Id}
      {currentChangeId}
      customGetItemHref={getSidebarHref}
      userPendingCreates={filteredPendingCreates}
      {userPendingUpdates}
      tableColumns={navTableColumns}
      fullWidthColumns={navFullWidthColumns}
      allAvailableColumns={allAvailableColumns}
      pageTypeId={navPageTypeId}
    />
  </svelte:fragment>

  {#if disambiguation && disambiguation.length > 0}
    <div class="disambiguation-panel">
      <h2>"{disambiguation[0].Name}" refers to multiple locations</h2>
      <p>Please select the specific location you're looking for:</p>
      <ul class="disambiguation-list">
        {#each disambiguation as loc}
          <li>
            <a href="{getSidebarHref(loc, '/information/locations')}">
              <span class="loc-name">{loc.Name}</span>
              <span class="loc-details">
                {loc.Properties?.Type || 'Location'}
                {#if loc.Planet?.Name}on {loc.Planet.Name}{/if}
                {#if loc.Properties?.Coordinates?.Longitude != null}
                  · ({loc.Properties.Coordinates.Longitude}, {loc.Properties.Coordinates.Latitude})
                {/if}
              </span>
            </a>
          </li>
        {/each}
      </ul>
    </div>
  {:else if activeEntity || isCreateMode}
    {#if $existingPendingChange && !$editMode && !isCreateMode}
      <div class="pending-change-banner">
        <div class="banner-content">
          <span class="banner-text">
            This location has a pending change by <strong>{$existingPendingChange.author_name || 'Unknown'}</strong>
            ({$existingPendingChange.state})
          </span>
        </div>
        <div class="banner-actions">
          {#if $viewingPendingChange}
            <button class="banner-btn" on:click={() => setViewingPendingChange(false)}>View Current</button>
          {:else}
            <button class="banner-btn primary" on:click={() => setViewingPendingChange(true)}>View Pending</button>
          {/if}
        </div>
      </div>
    {/if}

    <div class="layout-a">
      <aside class="wiki-infobox-float">
        <div class="infobox-header">
          <div class="infobox-title">
            <InlineEdit
              value={activeEntity?.Name || ''}
              path="Name"
              type="text"
              placeholder="Location name"
            />
          </div>
          <div class="infobox-subtitle">
            <span>{LOCATION_TYPES.find(t => t.value === locationType)?.label || locationType}</span>
            <span>{activeLocation?.Planet?.Name || 'Unknown'}</span>
          </div>
        </div>

        <div class="stats-section">
          <h4 class="section-title">Details</h4>
          <div class="stat-row">
            <span class="stat-label">Type</span>
            <span class="stat-value">
              <InlineEdit
                value={locationType}
                path="Properties.Type"
                type="select"
                options={LOCATION_TYPES}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Planet</span>
            <span class="stat-value">
              <InlineEdit
                value={activeLocation?.Planet?.Name || 'Calypso'}
                path="Planet.Name"
                type="select"
                options={planetOptions}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Parent</span>
            <span class="stat-value">
              {#if $editMode}
                <SearchInput
                  value={getOptionLabel([{ value: '', label: 'None' }, ...parentLocationOptions], activeLocation?.ParentLocation?.Id)}
                  options={[{ value: '', label: 'None' }, ...parentLocationOptions]}
                  placeholder="Select parent location"
                  on:select={(e) => {
                    const locId = e.detail.value ? Number(e.detail.value) : null;
                    if (locId) {
                      const loc = allLocations.find(l => l.Id === locId);
                      updateField('ParentLocation', loc ? { Id: loc.Id, Name: loc.Name } : null);
                    } else {
                      updateField('ParentLocation', null);
                    }
                  }}
                />
              {:else}
                {activeLocation?.ParentLocation?.Name || 'None'}
              {/if}
            </span>
          </div>
        </div>

        {#if activeLocation?.Properties?.Coordinates?.Longitude != null || $editMode}
          <div class="stats-section waypoint-section">
            <h4 class="section-title">Waypoint</h4>
            {#if $editMode}
              <WaypointInput
                value={waypointValue}
                planetLocked={true}
                nameLocked={true}
                hidePlanet={true}
                hideName={true}
                on:change={(e) => handleWaypointChange(e.detail)}
              />
            {:else}
              <WaypointCopyButton waypoint={waypointString} />
            {/if}
          </div>
        {/if}

        {#if locationType === 'Area'}
          <div class="stats-section">
            <h4 class="section-title">Area Details</h4>
            <div class="stat-row">
              <span class="stat-label">Area Type</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeLocation?.Properties?.AreaType || ''}
                  path="Properties.AreaType"
                  type="select"
                  options={AREA_TYPES}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Shape</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeLocation?.Properties?.Shape || ''}
                  path="Properties.Shape"
                  type="select"
                  options={SHAPE_TYPES}
                />
              </span>
            </div>
          </div>

          <!-- Shape Data Editor (only in edit mode) -->
          {#if $editMode && currentShape && currentShape !== 'Point'}
            <div class="stats-section shape-data-section">
              <h4 class="section-title">Shape Data</h4>

              {#if currentShape === 'Circle'}
                <div class="stat-row">
                  <span class="stat-label">Center X</span>
                  <span class="stat-value">
                    <input
                      type="number"
                      class="shape-input"
                      value={activeLocation?.Properties?.Data?.x ?? ''}
                      placeholder="X coordinate"
                      on:input={(e) => updateShapeData('x', e.target.value ? Number(e.target.value) : null)}
                    />
                  </span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">Center Y</span>
                  <span class="stat-value">
                    <input
                      type="number"
                      class="shape-input"
                      value={activeLocation?.Properties?.Data?.y ?? ''}
                      placeholder="Y coordinate"
                      on:input={(e) => updateShapeData('y', e.target.value ? Number(e.target.value) : null)}
                    />
                  </span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">Radius</span>
                  <span class="stat-value">
                    <input
                      type="number"
                      class="shape-input"
                      value={activeLocation?.Properties?.Data?.radius ?? ''}
                      placeholder="Radius"
                      on:input={(e) => updateShapeData('radius', e.target.value ? Number(e.target.value) : null)}
                    />
                  </span>
                </div>
              {:else if currentShape === 'Rectangle'}
                <div class="stat-row">
                  <span class="stat-label">X (Left)</span>
                  <span class="stat-value">
                    <input
                      type="number"
                      class="shape-input"
                      value={activeLocation?.Properties?.Data?.x ?? ''}
                      placeholder="X coordinate"
                      on:input={(e) => updateShapeData('x', e.target.value ? Number(e.target.value) : null)}
                    />
                  </span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">Y (Bottom)</span>
                  <span class="stat-value">
                    <input
                      type="number"
                      class="shape-input"
                      value={activeLocation?.Properties?.Data?.y ?? ''}
                      placeholder="Y coordinate"
                      on:input={(e) => updateShapeData('y', e.target.value ? Number(e.target.value) : null)}
                    />
                  </span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">Width</span>
                  <span class="stat-value">
                    <input
                      type="number"
                      class="shape-input"
                      value={activeLocation?.Properties?.Data?.width ?? ''}
                      placeholder="Width"
                      on:input={(e) => updateShapeData('width', e.target.value ? Number(e.target.value) : null)}
                    />
                  </span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">Height</span>
                  <span class="stat-value">
                    <input
                      type="number"
                      class="shape-input"
                      value={activeLocation?.Properties?.Data?.height ?? ''}
                      placeholder="Height"
                      on:input={(e) => updateShapeData('height', e.target.value ? Number(e.target.value) : null)}
                    />
                  </span>
                </div>
              {:else if currentShape === 'Polygon'}
                <div class="polygon-editor">
                  <label class="polygon-label">Vertices (X, Y pairs, one per line)</label>
                  <textarea
                    class="polygon-textarea"
                    placeholder="e.g.&#10;1000, 2000&#10;1500, 2500&#10;1200, 3000"
                    value={formatPolygonVertices(activeLocation?.Properties?.Data?.vertices)}
                    on:input={(e) => {
                      const vertices = parsePolygonVertices(e.target.value);
                      if (vertices) updateShapeData('vertices', vertices);
                    }}
                  ></textarea>
                  <span class="polygon-hint">
                    Enter coordinates as X, Y pairs (one pair per line or comma-separated)
                  </span>
                </div>
              {/if}
            </div>
          {/if}

          <!-- Shape Data Display (view mode) -->
          {#if !$editMode && currentShape && currentShape !== 'Point' && activeLocation?.Properties?.Data}
            <div class="stats-section">
              <h4 class="section-title">Shape Data</h4>
              {#if currentShape === 'Circle'}
                <div class="stat-row">
                  <span class="stat-label">Center</span>
                  <span class="stat-value">({activeLocation.Properties.Data.x}, {activeLocation.Properties.Data.y})</span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">Radius</span>
                  <span class="stat-value">{activeLocation.Properties.Data.radius} m</span>
                </div>
              {:else if currentShape === 'Rectangle'}
                <div class="stat-row">
                  <span class="stat-label">Position</span>
                  <span class="stat-value">({activeLocation.Properties.Data.x}, {activeLocation.Properties.Data.y})</span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">Size</span>
                  <span class="stat-value">{activeLocation.Properties.Data.width} × {activeLocation.Properties.Data.height} m</span>
                </div>
              {:else if currentShape === 'Polygon'}
                <div class="stat-row">
                  <span class="stat-label">Vertices</span>
                  <span class="stat-value">{(activeLocation.Properties.Data.vertices?.length || 0) / 2} points</span>
                </div>
              {/if}
            </div>
          {/if}
        {/if}

        {#if locationType === 'Estate'}
          <div class="stats-section">
            <h4 class="section-title">Estate Details</h4>
            <div class="stat-row">
              <span class="stat-label">Estate Type</span>
              <span class="stat-value">
                {#if $editMode}
                  <select class="locked-select" disabled>
                    <option value="Apartment" selected>Apartment</option>
                  </select>
                {:else}
                  Apartment
                {/if}
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Owner</span>
              <span class="stat-value">
                {#if $editMode}
                  <div class="owner-picker">
                    {#if activeLocation?.Properties?.OwnerId || selectedOwnerDisplayName}
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
            <div class="stat-row">
              <span class="stat-label">Item Trade</span>
              <span class="stat-value">
                {#if $editMode}
                  <label class="checkbox-label">
                    <input
                      type="checkbox"
                      checked={activeLocation?.Properties?.ItemTradeAvailable || false}
                      on:change={(e) => updateField('Properties.ItemTradeAvailable', e.target.checked)}
                    />
                    <span class="checkbox-text">{activeLocation?.Properties?.ItemTradeAvailable ? 'Enabled' : 'Disabled'}</span>
                  </label>
                {:else}
                  {activeLocation?.Properties?.ItemTradeAvailable ? 'Yes' : 'No'}
                {/if}
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Max Guests</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeLocation?.Properties?.MaxGuests ?? ''}
                  path="Properties.MaxGuests"
                  type="number"
                  placeholder="Max guests"
                />
              </span>
            </div>
          </div>
        {/if}

        {#if !$editMode && closestTeleporters.length > 0}
          <div class="stats-section">
            <h4 class="section-title">Closest Teleporters</h4>
            <div class="teleporter-list">
              {#each closestTeleporters as tp}
                <a href="/information/locations/teleporter/{encodeURIComponentSafe(tp.Name)}{duplicateNames.has(tp.Name) ? `?id=${tp.Id}` : ''}" class="teleporter-item">
                  <span class="tp-name">{tp.Name}</span>
                  <span class="tp-distance">{tp._distance?.toFixed(0)} m</span>
                </a>
              {/each}
            </div>
          </div>
        {/if}

        <!-- View on Map button -->
        {#if activeLocation?.Properties?.Coordinates?.Longitude != null}
          <a href="{getMapUrl(activeLocation)}" class="map-link-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"></polygon>
              <line x1="8" y1="2" x2="8" y2="18"></line>
              <line x1="16" y1="6" x2="16" y2="22"></line>
            </svg>
            <span>View on Map</span>
          </a>
        {/if}
      </aside>

      <article class="wiki-article" class:editing={$editMode}>
        <h1 class="article-title">
          <InlineEdit
            value={activeEntity?.Name || ''}
            path="Name"
            type="text"
            placeholder="Location name"
          />
        </h1>

        <!-- Map Section (first, no wrapper) -->
        {#if activeLocation?.Properties?.Coordinates?.Longitude != null && !$editMode && activePlanet}
          <div class="map-embed-container">
            <LocationMapEmbed
              location={activeLocation}
              planet={activePlanet}
              height={500}
              nearbyLocations={nearbyMapLocations}
            />
          </div>
        {/if}

        <!-- Facilities Section (only for settlements: Outpost, Camp, City) -->
        {#if isSettlement}
          <DataSection title="Facilities" subtitle="{activeLocation?.Facilities?.length || 0} available" icon="" allowOverflow={$editMode}>
            {#if $editMode}
              <div class="facilities-editor">
                {#if (activeLocation?.Facilities || []).length > 0}
                  <div class="facility-chips">
                    {#each activeLocation?.Facilities || [] as facility}
                      <span class="facility-chip">
                        {facility.Name}
                        <button type="button" class="chip-remove" on:click={() => removeFacility(facility.Name)}>×</button>
                      </span>
                    {/each}
                  </div>
                {/if}
                <SearchInput
                  value=""
                  options={facilityOptions.filter(f => !(activeLocation?.Facilities || []).some(af => af.Name === f.value))}
                  placeholder="Add facility..."
                  on:select={(e) => { if (e.detail.value) addFacility(e.detail.value); }}
                />
              </div>
            {:else if activeLocation?.Facilities?.length}
              <div class="facility-chips">
                {#each activeLocation.Facilities as facility}
                  <span class="facility-chip">{facility.Name}</span>
                {/each}
              </div>
            {:else}
              <div class="empty-text">No facilities listed.</div>
            {/if}
          </DataSection>
        {/if}

        <!-- Waves (for WaveEvent type) -->
        {#if locationType === 'WaveEventArea'}
          <DataSection title="Waves" subtitle="{activeLocation?.Waves?.length || 0} waves" icon="" allowOverflow={$editMode}>
            {#if $editMode}
              <div class="waves-editor">
                {#each activeLocation?.Waves || [] as wave, idx}
                  {@const isExpanded = expandedWaves[idx]}
                  <div class="wave-item" class:expanded={isExpanded}>
                    <button
                      class="wave-item-header"
                      on:click={() => toggleWave(idx)}
                      type="button"
                    >
                      <span class="expand-icon">{isExpanded ? '▼' : '▶'}</span>
                      <span class="wave-label">Wave {wave.WaveIndex}</span>
                      <span class="wave-summary">
                        {#if wave.TimeToComplete}{wave.TimeToComplete} min{/if}
                        {#if wave.MobMaturities?.length}· {wave.MobMaturities.length} mobs{/if}
                      </span>
                      <div class="wave-actions">
                        <button
                          class="btn-icon danger"
                          on:click|stopPropagation={() => removeWave(idx)}
                          title="Remove wave"
                          type="button"
                        >×</button>
                      </div>
                    </button>

                    {#if isExpanded}
                      <div class="wave-content">
                        <div class="wave-field-grid">
                          <label class="wave-field">
                            <span class="field-label">Time to Complete (min)</span>
                            <input
                              type="number"
                              value={wave.TimeToComplete ?? ''}
                              placeholder="Minutes"
                              on:input={(e) => updateWave(idx, 'TimeToComplete', e.target.value ? Number(e.target.value) : null)}
                            />
                          </label>
                        </div>

                        <div class="wave-maturities-section">
                          <span class="field-label">Mob Maturities ({wave.MobMaturities?.length || 0})</span>
                          <div class="wave-maturities">
                            {#each wave.MobMaturities || [] as matId}
                              <span class="maturity-chip">
                                {getMaturityName(matId)}
                                <button type="button" class="chip-remove" on:click={() => removeWaveMaturity(idx, matId)}>×</button>
                              </span>
                            {/each}
                          </div>
                          <div class="maturity-search-wrapper">
                            <input
                              type="text"
                              class="maturity-search-input"
                              bind:value={maturitySearchQueries[idx]}
                              on:input={() => handleMaturitySearchInput(idx)}
                              on:focus={() => handleMaturitySearchInput(idx)}
                              on:blur={() => hideMaturitySuggestions(idx)}
                              placeholder="Search maturities..."
                              autocomplete="off"
                            />
                            {#if showMaturitySuggestions[idx] && maturitySearchResults[idx]?.length > 0}
                              <div class="maturity-suggestions">
                                {#each maturitySearchResults[idx] as mat}
                                  <button
                                    type="button"
                                    class="maturity-suggestion-item"
                                    on:mousedown|preventDefault={() => selectMaturity(idx, mat)}
                                  >
                                    <span class="suggestion-mob">{mat.Mob?.Name || 'Unknown'}</span>
                                    <span class="suggestion-mat">{mat.Name || 'Unknown'}</span>
                                  </button>
                                {/each}
                              </div>
                            {/if}
                          </div>
                        </div>
                      </div>
                    {/if}
                  </div>
                {/each}
                <button type="button" class="btn-add" on:click={addWave}>
                  <span>+</span> Add Wave
                </button>
              </div>
            {:else if activeLocation?.Waves?.length}
              <div class="waves-list">
                {#each activeLocation.Waves as wave}
                  <div class="wave-block view">
                    <div class="wave-header">
                      <span class="wave-number">Wave {wave.WaveIndex}</span>
                      {#if wave.TimeToComplete}
                        <span class="wave-time">{wave.TimeToComplete} min</span>
                      {/if}
                    </div>
                    {#if wave.MobMaturities?.length}
                      <ul class="wave-mobs">
                        {#each wave.MobMaturities as matId}
                          <li>{getMaturityName(matId)}</li>
                        {/each}
                      </ul>
                    {:else}
                      <div class="empty-text">No mobs assigned.</div>
                    {/if}
                  </div>
                {/each}
              </div>
            {:else}
              <div class="empty-text">No waves defined.</div>
            {/if}
          </DataSection>
        {/if}

        <!-- Description Section -->
        {#if $editMode || activeLocation?.Properties?.Description}
          <DataSection title="Description" subtitle="" icon="">
            {#if $editMode}
              <RichTextEditor
                content={activeLocation?.Properties?.Description || ''}
                on:change={(e) => updateField('Properties.Description', e.detail)}
                placeholder="Describe this location..."
                showWaypoints={true}
              />
            {:else}
              <div class="description-content">{@html sanitizeHtml(activeLocation.Properties.Description)}</div>
            {/if}
          </DataSection>
        {/if}

        <!-- Estate Sections (for Estate type) -->
        {#if locationType === 'Estate'}
          <DataSection title="Sections" subtitle="{activeLocation?.Sections?.length || 0} sections" icon="">
            {#if $editMode}
              <div class="sections-editor">
                {#each activeLocation?.Sections || [] as section, idx}
                  <div class="section-row">
                    <input
                      type="text"
                      class="section-name"
                      value={section.Name}
                      placeholder="Section name"
                      on:input={(e) => updateSection(idx, 'Name', e.target.value)}
                    />
                    <input
                      type="number"
                      class="section-points"
                      value={section.ItemPoints ?? ''}
                      placeholder="Item points"
                      on:input={(e) => updateSection(idx, 'ItemPoints', e.target.value ? Number(e.target.value) : null)}
                    />
                    <button type="button" class="delete-btn small" on:click={() => removeSection(idx)}>Remove</button>
                  </div>
                {/each}
                <button type="button" class="btn-add" on:click={addSection}>
                  <span>+</span> Add Section
                </button>
              </div>
            {:else if activeLocation?.Sections?.length}
              <ul class="sections-list">
                {#each activeLocation.Sections as section}
                  <li>
                    <strong>{section.Name}</strong>
                    {#if section.ItemPoints}
                      <span class="section-points-display">({section.ItemPoints} item points)</span>
                    {/if}
                  </li>
                {/each}
              </ul>
            {:else}
              <div class="empty-text">No sections defined.</div>
            {/if}
          </DataSection>
        {/if}

      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Locations</h2>
      <p>Select a location from the list to view details.</p>
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

  .banner-content {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .banner-text {
    font-size: 14px;
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
  }

  .banner-btn.primary {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  /* Teleporter list in infobox */
  .teleporter-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .teleporter-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 8px;
    background: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    text-decoration: none;
    color: var(--text-color);
    font-size: 12px;
    transition: border-color 0.15s;
  }

  .teleporter-item:hover {
    border-color: var(--accent-color, #4a9eff);
  }

  .tp-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tp-distance {
    color: var(--text-muted, #999);
    font-size: 11px;
    margin-left: 8px;
    flex-shrink: 0;
  }

  .wiki-article.editing {
    overflow: visible;
    display: flow-root;
  }

  /* Map embed container (no DataSection wrapper) */
  .map-embed-container {
    margin-bottom: 16px;
  }

  /* Facilities */
  .facilities-editor {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;
  }

  .facilities-editor :global(.searchable-select) {
    width: 100%;
  }

  .facility-chips,
  .wave-maturities {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .facility-chip,
  .maturity-chip {
    background: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 13px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
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

  /* Sections */
  .sections-editor {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .section-row {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .section-name {
    flex: 2;
    padding: 6px 10px;
    font-size: 13px;
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .section-points {
    flex: 1;
    padding: 6px 10px;
    font-size: 13px;
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .sections-list {
    padding-left: 18px;
  }

  .section-points-display {
    font-size: 12px;
    color: var(--text-muted, #999);
    margin-left: 6px;
  }

  /* Waves */
  .waves-editor {
    display: flex;
    flex-direction: column;
    gap: 6px;
    overflow: visible;
  }

  .waves-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  /* Collapsible wave items (edit mode) */
  .wave-item {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    overflow: visible;
  }

  .wave-item.expanded {
    border-color: var(--accent-color, #4a9eff);
    overflow: visible;
  }

  .wave-item-header {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 8px 10px;
    background: none;
    border: none;
    color: var(--text-color);
    cursor: pointer;
    text-align: left;
    font-size: 13px;
    transition: background-color 0.15s;
  }

  .wave-item-header:hover {
    background-color: var(--hover-color);
  }

  .wave-item-header .expand-icon {
    font-size: 10px;
    color: var(--text-muted, #999);
    width: 14px;
    flex-shrink: 0;
  }

  .wave-label {
    font-weight: 600;
    flex: 1;
    min-width: 0;
  }

  .wave-summary {
    font-size: 12px;
    color: var(--text-muted, #999);
    flex-shrink: 0;
  }

  .wave-actions {
    display: flex;
    gap: 4px;
    margin-left: 8px;
    flex-shrink: 0;
  }

  .wave-content {
    padding: 12px;
    border-top: 1px solid var(--border-color, #555);
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow: visible;
  }

  .wave-field-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .wave-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .wave-field .field-label {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .wave-field input {
    padding: 6px 10px;
    font-size: 13px;
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    width: 100%;
    box-sizing: border-box;
    min-width: 0;
  }

  .wave-field input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .wave-maturities-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow: visible;
  }

  .wave-maturities-section .field-label {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  /* Maturity search input */
  .maturity-search-wrapper {
    position: relative;
  }

  .maturity-search-input {
    width: 100%;
    padding: 8px 12px;
    font-size: 13px;
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    box-sizing: border-box;
  }

  .maturity-search-input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .maturity-suggestions {
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

  .maturity-suggestion-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 12px;
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
    color: var(--text-color);
    transition: background-color 0.15s;
  }

  .maturity-suggestion-item:hover {
    background: var(--hover-color);
  }

  .suggestion-mob {
    font-size: 13px;
    font-weight: 500;
  }

  .suggestion-mat {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  /* View mode wave blocks */
  .wave-block {
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    padding: 12px;
    background: var(--bg-color, var(--primary-color));
  }

  .wave-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .wave-number {
    font-weight: 600;
    font-size: 14px;
  }

  .wave-time {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .wave-mobs {
    padding-left: 18px;
    margin: 0;
    font-size: 13px;
  }

  /* Icon button for waves */
  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    background: none;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 14px;
    line-height: 1;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .btn-icon:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
    border-color: var(--text-color);
  }

  .btn-icon.danger:hover {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  /* Buttons */
  .btn-add {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 8px 12px;
    font-size: 12px;
    line-height: 1;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    color: var(--text-muted, #999);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s;
    margin-top: 8px;
  }

  .btn-add:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
    background-color: var(--hover-color);
  }

  .delete-btn {
    padding: 4px 8px;
    font-size: 11px;
    background: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    cursor: pointer;
  }

  .delete-btn:hover {
    border-color: var(--error-color, #ef4444);
    color: var(--error-color, #ef4444);
  }

  .empty-text {
    font-size: 12px;
    color: var(--text-muted, #999);
    font-style: italic;
  }

  /* Disambiguation panel */
  .disambiguation-panel {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 24px;
    max-width: 600px;
    margin: 0 auto;
  }

  .disambiguation-panel h2 {
    margin: 0 0 12px 0;
    font-size: 20px;
    color: var(--text-color);
  }

  .disambiguation-panel p {
    margin: 0 0 16px 0;
    color: var(--text-muted, #999);
  }

  .disambiguation-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .disambiguation-list li a {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 12px 16px;
    background: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    text-decoration: none;
    transition: border-color 0.15s, background-color 0.15s;
  }

  .disambiguation-list li a:hover {
    border-color: var(--accent-color, #4a9eff);
    background-color: var(--hover-color, rgba(74, 158, 255, 0.1));
  }

  .disambiguation-list .loc-name {
    font-weight: 600;
    font-size: 15px;
    color: var(--text-color);
  }

  .disambiguation-list .loc-details {
    font-size: 13px;
    color: var(--text-muted, #999);
  }

  /* Shape data editor styles */
  .shape-data-section {
    margin-top: 0;
  }

  .shape-input {
    width: 100%;
    padding: 6px 10px;
    font-size: 13px;
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .polygon-editor {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .polygon-label {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .polygon-textarea {
    width: 100%;
    min-height: 100px;
    padding: 8px 10px;
    font-size: 13px;
    font-family: monospace;
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    resize: vertical;
  }

  .polygon-hint {
    font-size: 11px;
    color: var(--text-muted, #999);
    font-style: italic;
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

  /* Locked select (disabled dropdown) */
  .locked-select {
    padding: 4px 8px;
    font-size: 13px;
    background: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    cursor: not-allowed;
    opacity: 0.7;
  }

  /* Checkbox label */
  .checkbox-label {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 13px;
  }

  .checkbox-label input[type="checkbox"] {
    width: 16px;
    height: 16px;
    cursor: pointer;
    accent-color: var(--accent-color, #4a9eff);
  }

  .checkbox-text {
    color: var(--text-color);
  }

</style>
