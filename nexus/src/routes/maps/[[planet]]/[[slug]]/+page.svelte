<script>
  //@ts-nocheck
  import '$lib/style.css';

  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { onDestroy, onMount } from 'svelte';
  import { loading } from '../../../../stores';
  import { apiCall, getErrorMessage, getLatestPendingUpdate } from '$lib/util';
  import {
    fuzzyScore,
    getMainPlanetNames,
    getPlanetGroupByType,
    normalizePlanetSlug,
    getWaypointFromLocation,
    getMobAreaShortName,
    getMobAreaDifficulty,
    formatMobAreaMaturities,
    planetGroups
  } from '$lib/mapUtil';

  import MapCanvas from '$lib/components/MapCanvas.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import WaypointCopyButton from '$lib/components/wiki/WaypointCopyButton.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';

  // Map Editor components (Leaflet-based edit mode) — loaded dynamically to avoid SSR issues
  import { browser } from '$app/environment';

  let MapEditorWorkspace, ChangesSummary;

  if (browser) {
    Promise.all([
      import('$lib/components/map-editor/MapEditorWorkspace.svelte'),
      import('$lib/components/map-editor/ChangesSummary.svelte'),
    ]).then(([mew, cs]) => {
      MapEditorWorkspace = mew.default;
      ChangesSummary = cs.default;
    });
  }

  import {
    editMode,
    isCreateMode as isCreateModeStore,
    initEditState,
    resetEditState,
    currentEntity,
    changeMetadata,
    existingPendingChange,
    viewingPendingChange,
    setExistingPendingChange,
    setViewingPendingChange,
    updateField,
    startEdit,
    cancelEdit
  } from '$lib/stores/wikiEditState';

  export let data;

  let mapRef;
  let currentSlug = null;
  let searchQuery = '';
  let searchOpen = false;
  let selectedLocation = null;
  let hoveredLocation = null;
  let lastFocusedId = null;
  let pendingDialogOpen = false;
  let selectedMainPlanet = '';
  let selectedSubArea = '';
  let subAreas = [];
  let createEntityType = 'Location';
  let lastCreateEntityType = null;
  let lastPlanetGroup = null;
  let lastPlanetSlug = null;
  let polygonVerticesInput = '';
  let lastInitKey = null;
  let isMobile = false;
  let panelExpanded = false;
  let panelClosing = false;
  let touchStartY = 0;
  let touchDeltaY = 0;
  let apartmentDetails = {};
  let apartmentFetches = new Set();
  let apartmentDetailsLoaded = new Set();
  let selectedDetails = null;
  let pendingEditId = null;
  let changeIdParam = null;
  let searchResultsHovered = false;
  let searchSelectedIndex = -1;
  let panelLoading = false;
  let activatingLeaflet = false;
  let autoLeafletHandledKey = null;

  // --- Leaflet Edit Mode state ---
  let leafletEditMode = false;
  let editorPendingChanges = new Map();
  let editorRightPanel = 'editor';
  let editorChangeCount = 0;
  let editorDbChangeIdMap = new Map();
  let allMobs = [];
  let seededChangeId = null;
  let planetPendingOverride = null;

  async function handleChangesSubmitted() {
    editorPendingChanges = new Map();
    editorDbChangeIdMap = new Map();
    seededChangeId = null;
    try {
      const res = await fetch(`/api/changes?entity=Location,Area&state=Pending,Draft&planet=${encodeURIComponent(currentPlanet.Name)}&limit=100`);
      planetPendingOverride = res.ok ? await res.json() : [];
    } catch {
      planetPendingOverride = [];
    }
  }

  async function activateEditMode() {
    if (leafletEditMode || activatingLeaflet) return;
    activatingLeaflet = true;
    try {
      if (!allMobs.length) {
        const mobsData = await apiCall(fetch, '/mobs');
        allMobs = mobsData || [];
      }
      leafletEditMode = true;
    } finally {
      activatingLeaflet = false;
    }
  }

  function deactivateEditMode() {
    // Don't count the seeded Create change as an unsaved local change
    const hasUnsavedChanges = seededChangeId
      ? editorPendingChanges.size > 1 || (editorPendingChanges.size === 1 && !editorPendingChanges.has(-seededChangeId))
      : editorPendingChanges.size > 0;
    if (hasUnsavedChanges) {
      if (!confirm('You have unsaved changes. Exit edit mode?')) return;
    }
    leafletEditMode = false;
    editorPendingChanges = new Map();
    editorRightPanel = 'editor';
    seededChangeId = null;
  }

  const mainPlanets = getMainPlanetNames();

  const ESTATE_ID_OFFSET = 300000;
  const DEFAULT_VISIBLE_LOCATION_TYPES = new Set(['Teleporter']);
  const DEFAULT_VISIBLE_AREA_TYPES = new Set(['PvpArea', 'PvpLootArea', 'ZoneArea']);

  $: user = data.session?.user;
  $: canEdit = user?.verified || user?.grants?.includes('wiki.edit');
  $: isEditAllowed = canEdit && !isMobile;
  $: routeMode = ($page.url.searchParams.get('mode') || '').toLowerCase();
  $: routeChangeId = $page.url.searchParams.get('changeId');
  $: shouldAutoOpenLeaflet = !!currentPlanet && isEditAllowed && (routeMode === 'edit' || routeMode === 'create');
  $: autoLeafletKey = `${$page.url.pathname}|${routeMode}|${routeChangeId || ''}`;
  $: canCreateNew = data.canCreateNew ?? true;
  $: pendingChange = data.pendingChange;
  $: userPendingCreates = data.userPendingCreates || [];
  $: userPendingUpdates = data.userPendingUpdates || [];
  $: hasPendingChanges = userPendingCreates.length + userPendingUpdates.length > 0;
  $: locationEntityId = selectedLocation?.Id ?? selectedLocation?.ItemId;
  $: userPendingUpdate = getLatestPendingUpdate(userPendingUpdates, locationEntityId);
  $: resolvedPendingChange = userPendingUpdate || pendingChange;
  $: canUsePendingChange = !!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve')));

  $: locations = data?.additional?.locations || [];
  // Pre-compute difficulty for MobArea locations
  $: if (locations.length) {
    for (const loc of locations) {
      if (loc.Properties?.Type === 'MobArea' && !loc._difficulty) {
        loc._difficulty = getMobAreaDifficulty(loc.Maturities);
      }
    }
  }
  $: error = data.error;
  $: currentPlanet = data?.additional?.planet;
  $: isCreateMode = data.isCreateMode || false;
  $: effectiveCreateMode = isCreateMode && isEditAllowed;
  $: if (data.existingChange?.entity === 'Area' || data.existingChange?.entity === 'Location' || data.existingChange?.entity === 'Apartment') {
    createEntityType = data.existingChange.entity;
  }

  function convertChangeToModified(changeData, tempId) {
    if (!changeData?.Properties) return null;
    const props = changeData.Properties;
    const coords = props.Coordinates || {};
    const isArea = props.Shape || String(props.Type || '').endsWith('Area');
    const modified = {
      name: changeData.Name || '',
      locationType: isArea ? 'Area' : (props.Type || 'Location'),
      longitude: coords.Longitude ?? 0,
      latitude: coords.Latitude ?? 0,
      altitude: coords.Altitude ?? null,
      areaType: isArea ? (props.AreaType || props.Type || 'MobArea') : null,
      shape: props.Shape || null,
      shapeData: props.Data || null,
      description: props.Description || null,
      tempId
    };
    // Restore mob data if persisted in the change
    if (props.MobData || props.Density != null) {
      modified.mobData = { density: props.Density ?? 4, maturities: props.MobData || [] };
    }
    return modified;
  }

  function buildLeafletFocusLocation(locLike) {
    if (!locLike?.Properties) return null;
    const props = locLike.Properties || {};
    const coords = props.Coordinates || {};
    return {
      Id: locLike.Id ?? locLike.ItemId ?? null,
      Name: locLike.Name || '',
      Properties: {
        ...props,
        Coordinates: {
          Longitude: coords.Longitude ?? null,
          Latitude: coords.Latitude ?? null,
          Altitude: coords.Altitude ?? null
        },
        Shape: props.Shape || null,
        Data: props.Data || null
      }
    };
  }

  function isAreaType(type) {
    if (!type) return false;
    return String(type).endsWith('Area');
  }

  function isApartmentType(type) {
    return String(type) === 'Apartment';
  }

  function getApartmentBaseId(location) {
    if (!location?.Id) return null;
    const id = Number(location.Id);
    if (!Number.isFinite(id)) return null;
    return id > ESTATE_ID_OFFSET ? id - ESTATE_ID_OFFSET : id;
  }

  function getApartmentViewId(id) {
    if (id === null || id === undefined || id === '') return id;
    const numericId = Number(id);
    if (!Number.isFinite(numericId)) return id;
    return numericId + ESTATE_ID_OFFSET;
  }

  function findLocationBySlug(slug, list) {
    if (!slug || !list) return null;
    let found = list.find((l) => l.Id == slug);
    if (found) return found;
    const norm = (s) => s?.toString().replace(/[_\s]+/g, '').toLowerCase();
    return list.find((l) => norm(l.Name) === norm(slug));
  }

  function getEntityTypeForLocation(location) {
    if (!location) return null;
    if (location?.Properties?.Type === 'MobArea') return null;
    if (location?.Properties?.Type === 'Shop') return null;
    if (location?.Properties?.Type === 'Apartment') return 'Apartment';
    if (location?.Properties?.Shape || location?.Properties?.Type?.endsWith('Area')) {
      return 'Area';
    }
    return 'Location';
  }

  function buildEmptyLocation() {
    return {
      Id: null,
      Name: '',
      Properties: {
        Description: null,
        Type: 'Location',
        Coordinates: { Longitude: null, Latitude: null, Altitude: 100 }
      },
      Planet: {
        Name: currentPlanet?.Name || '',
        Properties: { TechnicalName: currentPlanet?.Properties?.TechnicalName || normalizePlanetSlug(currentPlanet?.Name) }
      }
    };
  }

  function buildEmptyArea() {
    return {
      Id: null,
      Name: '',
      Properties: {
        Description: null,
        Type: 'ZoneArea',
        Shape: 'Rectangle',
        Data: null,
        Coordinates: { Longitude: null, Latitude: null, Altitude: 100 }
      },
      Planet: {
        Name: currentPlanet?.Name || '',
        Properties: { TechnicalName: currentPlanet?.Properties?.TechnicalName || normalizePlanetSlug(currentPlanet?.Name) }
      }
    };
  }

  function buildEmptyApartment() {
    return {
      Id: null,
      Name: '',
      Properties: {
        Description: null,
        Type: 'Apartment',
        Coordinates: { Longitude: null, Latitude: null, Altitude: 100 }
      },
      Planet: {
        Name: currentPlanet?.Name || '',
        Properties: { TechnicalName: currentPlanet?.Properties?.TechnicalName || normalizePlanetSlug(currentPlanet?.Name) }
      },
      Sections: [],
      MaxGuests: null,
      OwnerId: null
    };
  }

  function getTypeOptions(list, currentType = '') {
    const unique = new Set(['Location', 'Apartment']);
    (list || []).forEach((loc) => {
      const type = loc?.Properties?.Type;
      if (!type || type === 'Shop') {
        return;
      }
      unique.add(type);
    });
    if (currentType) {
      unique.add(currentType);
    }
    return Array.from(unique).sort().map((type) => ({
      value: type,
      label: type
    }));
  }

  async function fetchApartmentDetails(location) {
    if (typeof window === 'undefined') return;
    if (!location?.Id) return;
    if (apartmentDetailsLoaded.has(location.Id)) return;
    if (apartmentFetches.has(location.Id)) return;
    const baseId = getApartmentBaseId(location);
    if (baseId == null || !Number.isFinite(baseId)) return;
    apartmentFetches.add(location.Id);
    try {
      const data = await apiCall(fetch, `/apartments/${baseId}`);
      if (data) {
        apartmentDetails = { ...apartmentDetails, [location.Id]: data };
      }
    } catch (err) {
      console.warn('Failed to fetch apartment details', err);
    } finally {
      apartmentFetches.delete(location.Id);
      apartmentDetailsLoaded.add(location.Id);
    }
  }

  const shapeOptions = [
    { value: 'Circle', label: 'Circle' },
    { value: 'Rectangle', label: 'Rectangle' },
    { value: 'Polygon', label: 'Polygon' }
  ];

  function getDefaultShapeData(shape) {
    if (shape === 'Circle') {
      return { x: 0, y: 0, radius: 50 };
    }
    if (shape === 'Polygon') {
      return { vertices: [] };
    }
    return { x: 0, y: 0, width: 100, height: 100 };
  }

  function ensureAreaDefaults() {
    if (!$editMode) return;
    if (!activeLocation?.Properties) return;
    if (!isAreaEntity) return;
    if (!activeLocation?.Properties?.Shape) {
      updateField('Properties.Shape', 'Rectangle');
    }
    if (!activeLocation?.Properties?.Data) {
      updateField('Properties.Data', getDefaultShapeData(activeLocation?.Properties?.Shape || 'Rectangle'));
    }
  }

  $: if (locations) {
    const slug = $page.params.slug;
    if (!slug) {
      currentSlug = null;
      selectedLocation = null;
      if (isMobile) {
        panelExpanded = false;
      }
    } else if (slug !== currentSlug && !isCreateMode) {
      currentSlug = slug;
      // Only update selectedLocation if it doesn't already match the slug.
      // This prevents a race condition where the URL updates before new locations
      // data arrives, which would clear the selection set by selectLocation().
      if (!selectedLocation || selectedLocation.Id != slug) {
        const found = findLocationBySlug(slug, locations) || data.object;
        selectedLocation = found;
      }
    }
  }

  $: if (resolvedPendingChange) {
    setExistingPendingChange(resolvedPendingChange);
  } else {
    setExistingPendingChange(null);
    setViewingPendingChange(false);
  }

  $: if (selectedLocation && isApartmentType(selectedLocation?.Properties?.Type)) {
    const viewId = selectedLocation.Id;
    selectedDetails = apartmentDetails[viewId] || null;
    if (!apartmentDetailsLoaded.has(viewId) && !selectedDetails) {
      fetchApartmentDetails(selectedLocation);
    }
  } else {
    selectedDetails = null;
  }

  $: if (pendingEditId && selectedDetails && selectedLocation?.Id === pendingEditId) {
    pendingEditId = null;
    startEdit();
  }

  $: if (pendingEditId && selectedLocation?.Id !== pendingEditId) {
    pendingEditId = null;
  }

  $: activeLocation = $editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : (selectedDetails || selectedLocation);

  $: selectedEntityType = effectiveCreateMode
    ? createEntityType
    : getEntityTypeForLocation(selectedLocation);

  $: activeEntityType = selectedEntityType;
  $: isAreaEntity = !!activeLocation?.Properties?.Shape || isAreaType(activeLocation?.Properties?.Type);
  $: isApartmentEntity = isApartmentType(activeLocation?.Properties?.Type) || activeEntityType === 'Apartment';
  $: hasLocationContent = $editMode || (!isMobile && !!activeLocation?.Properties?.Coordinates);
  $: typeOptions = getTypeOptions(locations, activeLocation?.Properties?.Type || '');
  $: if (effectiveCreateMode && $editMode && activeLocation?.Properties?.Type) {
    if (isAreaType(activeLocation.Properties.Type)) {
      createEntityType = 'Area';
    } else if (isApartmentType(activeLocation.Properties.Type)) {
      createEntityType = 'Apartment';
    } else {
      createEntityType = 'Location';
    }
  }

  $: if (effectiveCreateMode && $editMode && createEntityType && createEntityType !== lastCreateEntityType) {
    changeMetadata.update((meta) => ({ ...meta, entity: createEntityType }));
    lastCreateEntityType = createEntityType;
  }

  $: if (isEditAllowed && effectiveCreateMode && data.existingChange?.id) {
    // Ensure create changes load immediately when the matching change id arrives.
    const changeId = changeIdParam || $page.url.searchParams.get('changeId');
    if (changeId && String(data.existingChange.id) === String(changeId)) {
      const initKey = `create-${data.existingChange.id}`;
      if (initKey !== lastInitKey) {
        const entityType = data.existingChange.entity || createEntityType || 'Location';
        const initialData = data.existingChange.data || buildEmptyLocation();
        initEditState(initialData, entityType, true, data.existingChange);
        lastInitKey = initKey;
      }
    }
  }

  $: if (isMobile && $editMode) {
    cancelEdit();
  }
  $: ensureAreaDefaults();

  $: if (isEditAllowed) {
    changeIdParam = $page.url.searchParams.get('changeId');
    const detailKey = selectedDetails && !$editMode ? 'detail' : 'basic';
    const initKey = isCreateMode
      ? `create-${data.existingChange?.id ?? 'new'}`
      : `view-${selectedLocation?.Id ?? 'none'}-${selectedEntityType ?? 'none'}-${detailKey}-${resolvedPendingChange?.id || 'none'}`;
    if (initKey !== lastInitKey) {
      if (effectiveCreateMode) {
        const hasMatchingChange = !changeIdParam || (data.existingChange?.id && String(data.existingChange.id) === String(changeIdParam));
        if (hasMatchingChange) {
          if (!data.existingChange?.id) {
            resetEditState();
          }
          const template =
            createEntityType === 'Area'
              ? buildEmptyArea()
              : createEntityType === 'Apartment'
                ? buildEmptyApartment()
                : buildEmptyLocation();
          const initialData = data.existingChange?.data || template;
          initEditState(initialData, createEntityType, true, data.existingChange || null);
        }
      } else if (selectedLocation && selectedEntityType) {
        if (selectedEntityType !== 'Apartment' || selectedDetails) {
          const viewEntity = selectedDetails || selectedLocation;
          initEditState(viewEntity, selectedEntityType, false, canUsePendingChange ? resolvedPendingChange : null);
        }
      }
      lastInitKey = initKey;
    }
  }

  $: if (mapRef && selectedLocation?.Id && selectedLocation.Id !== lastFocusedId) {
    lastFocusedId = selectedLocation.Id;
    mapRef.focusOnLocation(selectedLocation);
  }

  $: canEditExistingChange = data.existingChange?.id && (
    data.existingChange.author_id === user?.id ||
    user?.grants?.includes('wiki.approve')
  );

  $: leafletFocusLocation = (() => {
    if (!shouldAutoOpenLeaflet) return null;
    if (routeMode === 'create' && data.existingChange?.data) {
      const focus = buildLeafletFocusLocation(data.existingChange.data);
      if (focus && data.existingChange.id) {
        // Author/admin: select the seeded editable pending add
        // Normal reviewer: select the read-only DB change overlay
        focus.Id = canEditExistingChange ? -data.existingChange.id : `db-${data.existingChange.id}`;
        focus._dbChange = canEditExistingChange ? null : data.existingChange;
      }
      return focus;
    }
    if (routeMode === 'edit' && selectedLocation) {
      return selectedLocation;
    }
    if (selectedLocation) return selectedLocation;
    return null;
  })();

  $: leafletFocusKey = shouldAutoOpenLeaflet
    ? `${$page.url.pathname}|${routeMode}|${routeChangeId || ''}`
    : null;

  // Seed editorPendingChanges for author/admin viewing an existing Create change
  $: if (leafletEditMode && data.existingChange?.id && data.existingChange.type === 'Create'
      && canEditExistingChange && seededChangeId !== data.existingChange.id) {
    seededChangeId = data.existingChange.id;
    const tempId = -data.existingChange.id;
    const modified = convertChangeToModified(data.existingChange.data, tempId);
    if (modified) {
      editorPendingChanges.set(tempId, { action: 'add', original: null, modified });
      editorPendingChanges = editorPendingChanges;
    }
  }

  $: if (shouldAutoOpenLeaflet && autoLeafletHandledKey !== autoLeafletKey && !leafletEditMode) {
    autoLeafletHandledKey = autoLeafletKey;
    activateEditMode();
  }

  $: if (currentPlanet) {
    const group = getPlanetGroupByType($page.params.planet) || getPlanetGroupByType(normalizePlanetSlug(currentPlanet.Name));
    const planetSlug = $page.params.planet;
    if (group && (group.groupName !== lastPlanetGroup || planetSlug !== lastPlanetSlug)) {
      selectedMainPlanet = group.groupName;
      subAreas = group.list;
      const match = group.list.find((entry) => entry._type === planetSlug);
      selectedSubArea = match ? match._type : group.list[0]?._type;
      lastPlanetGroup = group.groupName;
      lastPlanetSlug = planetSlug;
    }
  }

  $: if (!currentPlanet && !selectedMainPlanet && mainPlanets.length > 0) {
    selectedMainPlanet = mainPlanets[0];
    subAreas = planetGroups[selectedMainPlanet] || [];
    selectedSubArea = subAreas[0]?._type || '';
  }

  function getDisplayName(loc) {
    if (loc.Properties?.Type === 'MobArea') return getMobAreaShortName(loc.Name);
    return loc.Name;
  }

  $: searchResults = (() => {
    const query = searchQuery.trim();
    if (!query) return [];
    return locations
      .map((item) => ({
        item,
        score: Math.max(
          fuzzyScore(item.Name, query),
          item.Properties?.Type === 'MobArea' ? fuzzyScore(getMobAreaShortName(item.Name), query) : 0,
          fuzzyScore(item.Properties?.Type, query) * 0.4
        )
      }))
      .filter((entry) => entry.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 20)
      .map((entry) => entry.item);
  })();

  $: if (!searchQuery.trim()) {
    searchOpen = false;
  }

  // Reset keyboard selection when results change
  $: searchResults, searchSelectedIndex = -1;

  // Clear hover state when search closes
  $: if (!searchOpen && searchResultsHovered) {
    searchResultsHovered = false;
    hoveredLocation = null;
  }

  function handleMainPlanetChange() {
    const group = planetGroups[selectedMainPlanet] || [];
    const target = group[0]?._type;
    if (target) {
      goto(`/maps/${target}`);
    }
  }

  function handleSubAreaChange() {
    if (selectedSubArea) {
      goto(`/maps/${selectedSubArea}`);
    }
  }

  async function selectLocation(location, options = {}) {
    if (!location) return;
    const isNewLocation = !selectedLocation || selectedLocation.Id !== location.Id;
    if (isNewLocation) {
      panelLoading = true;
    }
    selectedLocation = location;

    // Start animation immediately (before network call)
    if (options.focus) {
      mapRef?.focusOnLocation(location);
    }

    // Navigate (this triggers data reload but animation already started)
    const targetPlanet = location.Planet?.Name || currentPlanet?.Name;
    const planetSlug = normalizePlanetSlug(targetPlanet);
    if (planetSlug && location.Id) {
      await goto(`/maps/${planetSlug}/${location.Id}`, { noScroll: true });
    }

    // Clear loading state after navigation completes
    if (isNewLocation) {
      panelLoading = false;
    }
  }

  function handleCreate() {
    if (!isEditAllowed || !canCreateNew) return;
    if (isCreateMode && data.existingChange?.id) {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
      resetEditState();
      createEntityType = 'Location';
      const template = buildEmptyLocation();
      initEditState(template, createEntityType, true, null);
      return;
    }
    goto(`/maps/${$page.params.planet}?mode=create`);
  }

  function handleEdit() {
    if (!isEditAllowed || !activeLocation) return;
    if (isApartmentEntity && !selectedDetails) {
      pendingEditId = selectedLocation?.Id ?? null;
      fetchApartmentDetails(selectedLocation);
      return;
    }
    startEdit(activeLocation);
  }

  function handleCancelEdit() {
    cancelEdit();
  }

  function handlePendingSelect(change) {
    pendingDialogOpen = false;
    const planetSlug = normalizePlanetSlug(change?.data?.Planet?.Name || currentPlanet?.Name);
    if (!planetSlug) return;
    if (change?.type === 'Create' || change?.data?.Id == null) {
      goto(`/maps/${planetSlug}?mode=create&changeId=${change.id}`);
      return;
    }
    const isApartmentChange = change?.entity === 'Apartment' || isApartmentType(change?.data?.Properties?.Type);
    const targetId = isApartmentChange ? getApartmentViewId(change.data.Id) : change.data.Id;
    goto(`/maps/${planetSlug}/${targetId}`);
  }

  function getDistanceMeters(a, b) {
    if (!a?.Properties?.Coordinates || !b?.Properties?.Coordinates) return null;
    const dx = (a.Properties.Coordinates.Longitude ?? 0) - (b.Properties.Coordinates.Longitude ?? 0);
    const dy = (a.Properties.Coordinates.Latitude ?? 0) - (b.Properties.Coordinates.Latitude ?? 0);
    return Math.sqrt(dx * dx + dy * dy);
  }

  function getClosestTeleporters(location) {
    if (!location) return [];
    const teleporters = locations.filter((loc) => loc.Properties?.Type === 'Teleporter');
    return teleporters
      .map((tp) => ({
        ...tp,
        _distance: getDistanceMeters(location, tp)
      }))
      .filter((tp) => tp._distance != null && tp.Id !== location.Id)
      .sort((a, b) => a._distance - b._distance)
      .slice(0, 3);
  }

  $: closestTeleporters = getClosestTeleporters(activeLocation);

  function isDefaultVisibleType(type) {
    if (!type) return false;
    if (type === 'MobArea') return false;
    if (type.endsWith('Area')) {
      return DEFAULT_VISIBLE_AREA_TYPES.has(type);
    }
    return DEFAULT_VISIBLE_LOCATION_TYPES.has(type);
  }

  $: filteredLocations = (() => {
    const base = (locations || []).filter((loc) => isDefaultVisibleType(loc?.Properties?.Type));
    if (selectedLocation && !base.some((loc) => loc.Id === selectedLocation.Id)) {
      return [...base, selectedLocation];
    }
    return base;
  })();

  function formatCoord(value) {
    if (value === null || value === undefined || Number.isNaN(value)) return '—';
    return Number(value).toFixed(2);
  }

  function formatCoordInt(value) {
    if (value === null || value === undefined || Number.isNaN(value)) return formatCoord(value);
    return Number(value).toFixed(0);
  }

  // Fill percentages for difficulty/density bars: 5%, 30%, 55%, 80%, 100%
  const BAR_FILLS = [5, 30, 55, 80, 100];
  const DIFFICULTY_COLORS = [
    'rgb(100, 230, 50)',
    'rgb(200, 230, 0)',
    'rgb(255, 200, 0)',
    'rgb(255, 120, 0)',
    'rgb(255, 50, 30)',
  ];

  function difficultyBarFill(band) {
    if (band === 5) return 100; // Boss: full bar
    return BAR_FILLS[band] ?? 5;
  }

  function difficultyBarGradient(band) {
    // Gradient includes only colors up to current band
    const colors = DIFFICULTY_COLORS.slice(0, band + 1);
    return colors.length === 1 ? colors[0] : `linear-gradient(to right, ${colors.join(', ')})`;
  }

  function densityBarFill(value) {
    const v = Number(value);
    if (!v || v < 1) return 5;
    return BAR_FILLS[Math.min(v, 5) - 1];
  }

  function handleWaypointPaste(event) {
    if (!event?.clipboardData) return;
    const text = event.clipboardData.getData('text');
    if (!text) return;
    const match = text.match(/\[([^\]]+)\]/);
    const payload = match ? match[1] : text;
    const parts = payload.split(',').map((part) => part.trim());
    if (parts.length < 5) return;
    const x = parseFloat(parts[1]);
    const y = parseFloat(parts[2]);
    const z = parseFloat(parts[3]);
    if (Number.isNaN(x) || Number.isNaN(y) || Number.isNaN(z)) return;
    event.preventDefault();
    updateField('Properties.Coordinates.Longitude', x);
    updateField('Properties.Coordinates.Latitude', y);
    updateField('Properties.Coordinates.Altitude', z);
    const name = parts.slice(4).join(',').trim();
    if (name && !activeLocation?.Name?.trim()) {
      updateField('Name', name);
    }
  }

  function handleShapeChange(value) {
    const nextShape = value || 'Rectangle';
    updateField('Properties.Shape', nextShape);
    if (!activeLocation?.Properties?.Data || activeLocation.Properties.Shape !== nextShape) {
      updateField('Properties.Data', getDefaultShapeData(nextShape));
    }
  }

  function handlePolygonVerticesChange(event) {
    const raw = event.target.value;
    polygonVerticesInput = raw;
    const values = raw.split(/[\s,]+/).map((val) => parseFloat(val)).filter((val) => !Number.isNaN(val));
    updateField('Properties.Data.vertices', values);
  }

  function updateApartmentSection(index, field, value) {
    const sections = ($currentEntity?.Sections || []).map((section, idx) => {
      if (idx !== index) return section;
      const next = { ...section, [field]: value };
      if (field === 'ItemPoints') {
        next.MaxItemPoints = value;
      }
      return next;
    });
    updateField('Sections', sections);
  }

  function addApartmentSection() {
    const sections = [...($currentEntity?.Sections || [])];
    sections.push({
      Name: '',
      Description: null,
      ItemPoints: null,
      MaxItemPoints: null
    });
    updateField('Sections', sections);
  }

  function removeApartmentSection(index) {
    const sections = ($currentEntity?.Sections || []).filter((_, idx) => idx !== index);
    updateField('Sections', sections);
  }

  $: if (isAreaEntity && activeLocation?.Properties?.Data?.vertices) {
    polygonVerticesInput = activeLocation.Properties.Data.vertices.join(', ');
  }

  function handlePanelToggle() {
    if (!isMobile) return;
    panelExpanded = !panelExpanded;
  }

  function handlePanelTouchStart(event) {
    if (!isMobile) return;
    touchStartY = event.touches[0].clientY;
    touchDeltaY = 0;
  }

  function handlePanelTouchMove(event) {
    if (!isMobile) return;
    touchDeltaY = event.touches[0].clientY - touchStartY;
  }

  function handlePanelTouchEnd() {
    if (!isMobile) return;
    if (touchDeltaY < -40) {
      panelExpanded = true;
    } else if (touchDeltaY > 40) {
      if (!panelExpanded) {
        closePanelAndClear();
        touchDeltaY = 0;
        return;
      }
      panelExpanded = false;
    }
    touchDeltaY = 0;
  }

  function handleSearchBlur() {
    // Allow clicks on results before closing
    setTimeout(() => {
      // On desktop, keep the dropdown open so the user can inspect the map while browsing results
      if (!isMobile && searchQuery.trim()) return;
      searchOpen = false;
    }, 120);
  }

  function handleSearchKeydown(e) {
    if (e.key === 'Escape') {
      searchOpen = false;
      e.target.blur();
      return;
    }
    if (searchResults.length === 0) return;

    // Open results dropdown on arrow navigation
    if (!searchOpen && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      searchOpen = true;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      searchSelectedIndex = Math.min(searchSelectedIndex + 1, searchResults.length - 1);
      hoveredLocation = searchResults[searchSelectedIndex];
      scrollSearchResultIntoView(searchSelectedIndex);
      mapRef?.panTo(searchResults[searchSelectedIndex]);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      searchSelectedIndex = Math.max(searchSelectedIndex - 1, 0);
      hoveredLocation = searchResults[searchSelectedIndex];
      scrollSearchResultIntoView(searchSelectedIndex);
      mapRef?.panTo(searchResults[searchSelectedIndex]);
    } else if (e.key === 'Enter' && searchSelectedIndex >= 0) {
      e.preventDefault();
      if (isMobile) searchOpen = false;
      selectLocation(searchResults[searchSelectedIndex], { focus: true });
    }
  }

  function scrollSearchResultIntoView(index) {
    requestAnimationFrame(() => {
      const container = document.querySelector('.search-results');
      if (!container) return;
      const buttons = container.querySelectorAll('.search-result');
      buttons[index]?.scrollIntoView({ block: 'nearest' });
    });
  }

  function clearSelection() {
    selectedLocation = null;
    if (currentPlanet?.Name) {
      const planetSlug = normalizePlanetSlug(currentPlanet.Name);
      goto(`/maps/${planetSlug}`, { noScroll: true });
    }
  }

  function closePanelAndClear() {
    panelClosing = true;
    setTimeout(() => {
      panelClosing = false;
      clearSelection();
    }, 220);
  }

  $: if (selectedLocation) {
    panelClosing = false;
  }

  $: if (isMobile && (selectedLocation || effectiveCreateMode)) {
    panelClosing = false;
  }

  onMount(() => {
    if (typeof window === 'undefined') return;
    const media = window.matchMedia('(max-width: 899px)');
    const update = () => {
      isMobile = media.matches;
      if (!isMobile) {
        panelExpanded = false;
      }
    };
    update();
    media.addEventListener?.('change', update);
    return () => media.removeEventListener?.('change', update);
  });

  onDestroy(() => {
    resetEditState();
  });
</script>

<svelte:head>
  <title>Entropia Nexus - {currentPlanet?.Name || 'Map'} Map</title>
  <meta name="description" content="Interactive map for {currentPlanet?.Name || 'Entropia Universe'}." />
  <link rel="canonical" href="https://entropianexus.com/maps/{normalizePlanetSlug(currentPlanet?.Name)}" />
</svelte:head>

<div class="map-page">
  <div class="map-canvas">
    {#if error == null}
      {#if $loading}
        <div class="loading">
          <div class="spinner"></div>
        </div>
      {/if}
      {#if currentPlanet}
        <MapCanvas
          bind:this={mapRef}
          mapName={currentPlanet?.Name}
          planet={currentPlanet}
          locations={locations}
          bind:selected={selectedLocation}
          bind:hovered={hoveredLocation}
          searchResults={searchOpen ? searchResults : []}
        />
      {:else}
        <div class="map-empty">
          <h2>Select a planet to begin</h2>
          <p>Use the planet selector to load a map.</p>
        </div>
      {/if}
    {:else}
      <div class="info error"><h2>{error}</h2><br />{getErrorMessage(error)}</div>
    {/if}
  </div>

  <div class="map-controls">
    <div class="control-row">
      <div class="control-group">
        <label>Planet</label>
        <select bind:value={selectedMainPlanet} on:change={handleMainPlanetChange}>
          {#each mainPlanets as planetName}
            <option value={planetName}>{planetGroups[planetName]?.[0]?.Name || planetName}</option>
          {/each}
        </select>
      </div>
      <div class="control-group">
        <label>Area</label>
        <select bind:value={selectedSubArea} on:change={handleSubAreaChange}>
          {#each subAreas as area}
            <option value={area._type}>{area.Name}</option>
          {/each}
        </select>
      </div>
    </div>

    <div class="search-row">
      <input
        class="search-input"
        type="text"
        placeholder="Search locations..."
        bind:value={searchQuery}
        on:focus={() => searchOpen = true}
        on:blur={handleSearchBlur}
        on:keydown={handleSearchKeydown}
      />

      {#if isEditAllowed}
        <button class="create-btn" on:click={handleCreate} title={canCreateNew ? 'Create new location/area' : 'Create limit reached'} disabled={!canCreateNew}>
          +
        </button>
        {#if hasPendingChanges}
          <button class="pending-btn" on:click={() => pendingDialogOpen = true} title="Your pending changes">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <path d="M12 6v6l4 2"></path>
            </svg>
          </button>
        {/if}
      {/if}
    </div>

    {#if searchOpen && searchResults.length > 0}
      <div
        class="search-results"
        on:mouseenter={() => searchResultsHovered = true}
        on:mouseleave={() => { searchResultsHovered = false; hoveredLocation = null; }}
      >
        {#each searchResults as result, index}
          <button
            class="search-result"
            class:active={searchSelectedIndex === index}
            on:click={() => { searchSelectedIndex = index; if (isMobile) searchOpen = false; selectLocation(result, { focus: true }); }}
            on:mouseenter={() => { searchSelectedIndex = index; hoveredLocation = result; mapRef?.panTo(result); }}
            on:mouseleave={() => {}}
          >
            <span class="result-index">{index + 1}</span>
            <span class="result-name" style={result._difficulty?.color ? `color: ${result._difficulty.color}` : ''}>{getDisplayName(result)}</span>
            <span class="result-type">{result.Properties?.Type || 'Location'}</span>
          </button>
        {/each}
      </div>
    {/if}
  </div>

  {#if activeLocation || effectiveCreateMode}
    <aside
      class="map-info-panel"
      class:editing={$editMode && isEditAllowed}
      class:mobile={isMobile}
      class:expanded={panelExpanded}
      class:closing={panelClosing}
      on:touchstart={handlePanelTouchStart}
      on:touchmove={handlePanelTouchMove}
      on:touchend={handlePanelTouchEnd}
    >
      {#if panelLoading}
        <div class="panel-loading-overlay">
          <div class="loading-spinner"></div>
        </div>
      {/if}
      {#if $existingPendingChange && !$editMode && !effectiveCreateMode}
        <PendingChangeBanner
          pendingChange={$existingPendingChange}
          viewing={$viewingPendingChange}
          onToggle={() => setViewingPendingChange(!$viewingPendingChange)}
        />
      {/if}
      <div class="info-header">
        {#if isMobile}
          <button class="panel-grip" on:click={handlePanelToggle} aria-label="Toggle details">
            <span class="grip-bar"></span>
          </button>
        {/if}
        <div class="header-main">
          <div class="header-text">
            <div class="info-title-row">
              <div class="info-title" style={activeLocation?._difficulty?.color ? `color: ${activeLocation._difficulty.color}` : ''}>
                <InlineEdit
                  value={$editMode ? (activeLocation?.Name || '') : getDisplayName(activeLocation)}
                  path="Name"
                  type="text"
                  placeholder="Location name"
                />
              </div>
              {#if isEditAllowed && !effectiveCreateMode && activeEntityType}
                {#if $editMode}
                  <button class="icon-btn" on:click={handleCancelEdit} title="Cancel editing">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                {:else}
                  <button class="icon-btn" on:click={handleEdit} title="Edit location">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                      <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                    </svg>
                  </button>
                {/if}
              {/if}
            </div>
            <div class="info-subtitle">
              {#if $editMode && effectiveCreateMode && !data.existingChange?.id}
                <InlineEdit
                  value={activeLocation?.Properties?.Type || ''}
                  path="Properties.Type"
                  type="select"
                  options={typeOptions}
                  placeholder="Select type"
                  editable={true}
                />
              {:else}
                <span class="type-label">{activeLocation?.Properties?.Type || 'Location'}</span>
              {/if}
            </div>
            {#if isMobile}
              <div class="mobile-compact-coords">
                <span class="coords-label">Long/Lat</span>
                <span class="coords-value">
                  {formatCoordInt(activeLocation?.Properties?.Coordinates?.Longitude)} /
                  {formatCoordInt(activeLocation?.Properties?.Coordinates?.Latitude)}
                </span>
              </div>
            {/if}
          </div>
        </div>
      </div>

      {#if !isMobile || panelExpanded}
        <div class="panel-body">
          {#if hasLocationContent}
            <div class="info-section">
              <h4>Location</h4>
              {#if !$editMode && !isMobile}
              <div class="stat-row waypoint-row">
                <span class="stat-value">
                  {#if activeLocation?.Properties?.Coordinates}
                    <WaypointCopyButton waypoint={getWaypointFromLocation(activeLocation)} />
                  {/if}
                  </span>
                </div>
              {/if}
              {#if $editMode && !isAreaEntity}
                <div class="stat-row coords-row" on:paste={handleWaypointPaste}>
                  <span class="stat-label">Coordinates</span>
                  <span class="coord-inputs">
                    <InlineEdit type="number" value={activeLocation?.Properties?.Coordinates?.Longitude ?? ''} path="Properties.Coordinates.Longitude" step={1} placeholder="Lon" />
                    <InlineEdit type="number" value={activeLocation?.Properties?.Coordinates?.Latitude ?? ''} path="Properties.Coordinates.Latitude" step={1} placeholder="Lat" />
                    <InlineEdit type="number" value={activeLocation?.Properties?.Coordinates?.Altitude ?? 100} path="Properties.Coordinates.Altitude" step={1} placeholder="Alt" />
                  </span>
                </div>
              {:else if $editMode && isAreaEntity}
                {#if activeLocation?.Properties?.Shape === 'Circle'}
                  <div class="stat-row">
                    <span class="stat-label">Center (X/Y)</span>
                    <span class="coord-inputs">
                      <InlineEdit type="number" value={activeLocation?.Properties?.Data?.x ?? 0} path="Properties.Data.x" step={1} placeholder="X" />
                      <InlineEdit type="number" value={activeLocation?.Properties?.Data?.y ?? 0} path="Properties.Data.y" step={1} placeholder="Y" />
                    </span>
                  </div>
                  <div class="stat-row">
                    <span class="stat-label">Radius</span>
                    <span class="stat-value">
                      <InlineEdit type="number" value={activeLocation?.Properties?.Data?.radius ?? 0} path="Properties.Data.radius" step={1} />
                    </span>
                  </div>
                {:else if activeLocation?.Properties?.Shape === 'Rectangle'}
                  <div class="stat-row">
                    <span class="stat-label">Origin (X/Y)</span>
                    <span class="coord-inputs">
                      <InlineEdit type="number" value={activeLocation?.Properties?.Data?.x ?? 0} path="Properties.Data.x" step={1} placeholder="X" />
                      <InlineEdit type="number" value={activeLocation?.Properties?.Data?.y ?? 0} path="Properties.Data.y" step={1} placeholder="Y" />
                    </span>
                  </div>
                  <div class="stat-row">
                    <span class="stat-label">Size (W/H)</span>
                    <span class="coord-inputs">
                      <InlineEdit type="number" value={activeLocation?.Properties?.Data?.width ?? 0} path="Properties.Data.width" step={1} placeholder="W" />
                      <InlineEdit type="number" value={activeLocation?.Properties?.Data?.height ?? 0} path="Properties.Data.height" step={1} placeholder="H" />
                    </span>
                  </div>
                {:else}
                  <div class="stat-row">
                    <span class="stat-label">Vertices</span>
                    <span class="stat-value">
                      <textarea
                        class="polygon-input"
                        placeholder="x1, y1, x2, y2..."
                        value={polygonVerticesInput}
                        on:input={handlePolygonVerticesChange}
                      />
                    </span>
                  </div>
                {/if}
              {/if}
            </div>
          {/if}

            {#if isApartmentEntity}
              <div class="info-section">
                <h4>Estate Areas</h4>
                {#if $editMode}
                  <div class="section-edit-grid">
                    {#each $currentEntity?.Sections || [] as section, index (index)}
                      <div class="section-edit-row">
                        <input
                          class="section-edit-input"
                          type="text"
                          value={section?.Name || ''}
                          placeholder="Section name"
                          on:input={(event) => updateApartmentSection(index, 'Name', event.target.value)}
                        />
                        <div class="section-points">
                          <input
                            class="section-edit-input section-points-input"
                            type="number"
                            min="0"
                            step="1"
                            value={section?.ItemPoints ?? section?.MaxItemPoints ?? ''}
                            placeholder="Points"
                            on:input={(event) => {
                              const raw = event.target.value;
                              const parsed = raw === '' ? null : Number(raw);
                              updateApartmentSection(index, 'ItemPoints', Number.isNaN(parsed) ? null : parsed);
                            }}
                          />
                          <span class="points-label">pts</span>
                        </div>
                        <button class="section-remove" on:click={() => removeApartmentSection(index)} aria-label="Remove section">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                          </svg>
                        </button>
                      </div>
                    {/each}
                    <button class="section-add" on:click={addApartmentSection}>
                      + Add section
                    </button>
                  </div>
                {:else}
                  {#if (activeLocation?.Sections || []).length === 0}
                    <div class="muted">No areas defined.</div>
                  {:else}
                    <div class="type-tags">
                      {#each activeLocation?.Sections || [] as section}
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
                {/if}
              </div>
            {/if}

            {#if !$editMode}
              <div class="info-section">
                <h4>Closest Teleporters</h4>
                {#if closestTeleporters.length === 0}
                  <div class="muted">No teleporters found.</div>
                {:else}
                  <div class="teleporter-list">
                    {#each closestTeleporters as teleporter}
                      <button class="teleporter-item"
                        on:click={() => selectLocation(teleporter, { focus: true })}
                        on:mouseenter={() => { hoveredLocation = teleporter; mapRef?.panTo(teleporter); }}
                        on:mouseleave={() => { hoveredLocation = null; if (selectedLocation) mapRef?.panTo(selectedLocation); }}
                      >
                        <span>{teleporter.Name}</span>
                        <span class="teleporter-distance">{teleporter._distance?.toFixed(0)} m</span>
                      </button>
                    {/each}
                  </div>
                {/if}
              </div>
            {/if}

          {#if activeLocation?.Properties?.Type === 'MobArea'}
            <div class="info-section">
              <h4>Mob Area</h4>
              {#if activeLocation._difficulty}
                {@const diff = activeLocation._difficulty}
                {@const isBoss = diff.band === 5}
                <div class="stat-row">
                  <span class="stat-label">Difficulty</span>
                  <div class="stat-bar-wrap">
                    {#if isBoss}<span class="boss-badge">Boss</span>{/if}
                    <div class="stat-bar-track">
                      <div class="stat-bar-fill" style="width: {difficultyBarFill(diff.band)}%; background: {isBoss ? 'rgb(180, 80, 220)' : difficultyBarGradient(diff.band)};"></div>
                    </div>
                  </div>
                </div>
              {/if}
              {#if activeLocation?.Properties?.Density != null}
                <div class="stat-row">
                  <span class="stat-label">Density</span>
                  <div class="stat-bar-wrap">
                    <div class="stat-bar-track">
                      <div class="stat-bar-fill density-bar-fill" style="width: {densityBarFill(activeLocation.Properties.Density)}%;"></div>
                    </div>
                  </div>
                </div>
              {/if}
              <div class="stat-row">
                <span class="stat-label">Shared</span>
                <span class="stat-value">{activeLocation?.Properties?.IsShared ? 'Yes' : 'No'}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Event</span>
                <span class="stat-value">{activeLocation?.Properties?.IsEvent ? 'Yes' : 'No'}</span>
              </div>
              {#if activeLocation?.Maturities?.length}
                {@const mobEntries = formatMobAreaMaturities(activeLocation.Maturities)}
                {#if mobEntries.length}
                  <div class="mob-types-list">
                    {#each mobEntries as entry}
                      <div class="mob-type-row">
                        <a class="mob-name-link" href="/information/mobs/{entry.mobSlug || ''}">{entry.mob}</a>
                        {#if entry.display}
                          <span class="mob-mat-range">- {entry.display}</span>
                        {/if}
                      </div>
                    {/each}
                  </div>
                {/if}
              {/if}
              {#if activeLocation?.Properties?.Notes}
                <div class="description-text">{activeLocation.Properties.Notes}</div>
              {/if}
            </div>
          {/if}

          <div class="info-section">
            <h4>Description</h4>
            {#if $editMode}
              <InlineEdit
                value={activeLocation?.Properties?.Description || ''}
                path="Properties.Description"
                type="textarea"
                placeholder="Describe this location..."
              />
            {:else if activeLocation?.Properties?.Description}
              <div class="description-text">{activeLocation.Properties.Description}</div>
            {:else}
              <div class="muted">No description available.</div>
            {/if}
          </div>
        </div>
      {/if}
    </aside>
  {/if}

  {#if pendingDialogOpen}
    <div
      class="dialog-backdrop"
      on:click={() => pendingDialogOpen = false}
      on:keydown={(e) => e.key === 'Escape' && (pendingDialogOpen = false)}
    >
      <div class="dialog dialog-compact" on:click|stopPropagation>
        <div class="dialog-header">
          <h3>Your Drafts & Reviews</h3>
          <button class="close-btn" on:click={() => pendingDialogOpen = false} aria-label="Close dialog">
            ×
          </button>
        </div>
        <div class="dialog-body">
          <div class="pending-list">
            {#each [...userPendingCreates, ...userPendingUpdates] as change}
              <button class="pending-item" on:click={() => handlePendingSelect(change)}>
                <div class="pending-name">{change.data?.Name || 'Unnamed'}</div>
                <div class="pending-meta">{change.entity} - {change.state}</div>
              </button>
            {/each}
          </div>
        </div>
      </div>
    </div>
  {/if}

  <!-- Edit Mode Button (bottom-right, desktop only) -->
  {#if canEdit && !isMobile && currentPlanet && !leafletEditMode}
    <button class="edit-mode-btn" on:click={activateEditMode} title="Open Leaflet map editor">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
        <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
      </svg>
      Edit Mode
    </button>
  {/if}

  <!-- Leaflet Editor Layout (replaces canvas view) -->
  {#if leafletEditMode && MapEditorWorkspace}
    <div class="leaflet-editor-overlay">
      <div class="editor-toolbar">
        <span class="editor-toolbar-label">{currentPlanet?.Name || 'Map'} — Edit Mode</span>

        <div class="editor-toolbar-right">
          <button
            class="editor-toolbar-btn"
            class:active={editorRightPanel === 'changes'}
            on:click={() => editorRightPanel = editorRightPanel === 'changes' ? 'editor' : 'changes'}
          >
            Changes
            {#if editorChangeCount > 0}
              <span class="editor-badge">{editorChangeCount}</span>
            {/if}
          </button>
          <button class="editor-toolbar-btn editor-exit-btn" on:click={deactivateEditMode}>
            Exit Edit Mode
          </button>
        </div>
      </div>

      <svelte:component this={MapEditorWorkspace}
        planet={currentPlanet}
        {locations}
        {allMobs}
        editMode={true}
        mode="public"
        dbPendingChanges={planetPendingOverride ?? data.planetPendingChanges ?? []}
        currentUserId={user?.id}
        isAdmin={user?.grants?.includes('wiki.approve') || false}
        focusLocation={leafletFocusLocation}
        focusKey={leafletFocusKey}
        bind:pendingChanges={editorPendingChanges}
        bind:rightPanel={editorRightPanel}
        bind:changeCount={editorChangeCount}
        bind:dbChangeIdMap={editorDbChangeIdMap}
      >
        <svelte:fragment slot="output">
          <svelte:component this={ChangesSummary}
            pendingChanges={editorPendingChanges}
            planet={currentPlanet}
            isAdmin={user?.grants?.includes('admin.panel') || user?.administrator || false}
            dbChangeIdMap={editorDbChangeIdMap}
            on:clear={() => { editorPendingChanges = new Map(); editorDbChangeIdMap = new Map(); }}
            on:submitted={handleChangesSubmitted}
            on:removed={() => { editorPendingChanges = editorPendingChanges; }}
            on:dbChangeDeleted={(e) => {
              if (planetPendingOverride) {
                planetPendingOverride = planetPendingOverride.filter(c => c.id !== e.detail.dbId);
              } else if (data.planetPendingChanges) {
                data.planetPendingChanges = data.planetPendingChanges.filter(c => c.id !== e.detail.dbId);
              }
              editorPendingChanges = editorPendingChanges;
            }}
          />
        </svelte:fragment>
      </svelte:component>
    </div>
  {/if}
</div>

<style>
  .map-page {
    position: relative;
    height: 100%;
    width: 100%;
    overflow: hidden;
    background-color: var(--primary-color);
  }

  .map-canvas {
    position: absolute;
    inset: 0;
  }

  .map-empty {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: var(--text-muted, #999);
    text-align: center;
    padding: 24px;
  }

  .map-controls {
    position: absolute;
    top: 16px;
    left: 16px;
    width: 320px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 10px;
    padding: 12px;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.25);
    z-index: 20;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .control-row {
    display: flex;
    gap: 10px;
  }

  .control-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex: 1 1 0;
    min-width: 0;
    width: 0; /* Forces flex items to respect flex-basis and not grow based on content */
  }

  .control-group label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .control-group select {
    width: 100%;
    max-width: 100%;
    min-width: 0;
    box-sizing: border-box;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
    border-radius: 6px;
    padding: 6px 8px;
    font-size: 13px;
  }

  .search-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .search-input {
    flex: 1;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 13px;
  }

  .create-btn {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    border: none;
    background-color: var(--success-color, #4ade80);
    color: #0b3d1e;
    font-weight: 700;
    font-size: 18px;
    line-height: 1;
    cursor: pointer;
  }

  .create-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .pending-btn {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    border: 1px solid var(--border-color, #555);
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .search-results {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    max-height: min(520px, calc(100vh - 200px));
    overflow-y: auto;
  }

  .search-result {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border: none;
    background: transparent;
    color: var(--text-color);
    text-align: left;
    cursor: pointer;
  }

  .search-result:hover,
  .search-result.active {
    background-color: var(--hover-color);
  }

  .result-index {
    flex-shrink: 0;
    width: 20px;
    text-align: right;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted, #999);
  }

  .result-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .result-type {
    flex-shrink: 0;
    color: var(--text-muted, #999);
    font-size: 11px;
  }

  .map-info-panel {
    position: absolute;
    top: 16px;
    right: 16px;
    width: 320px;
    max-height: calc(100% - 32px);
    overflow-y: auto;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 12px;
    padding: 14px;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.25);
    z-index: 20;
  }

  .panel-loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: color-mix(in srgb, var(--secondary-color) 90%, transparent);
    backdrop-filter: blur(2px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10;
    border-radius: 12px;
  }

  .loading-spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border-color, #555);
    border-top-color: var(--accent-color, #4a9eff);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .map-info-panel:not(.mobile) :global(.entity-icon-wrapper) {
    max-width: min(160px, 20vh);
    margin-left: auto;
    margin-right: auto;
  }

  .map-info-panel.editing {
    max-height: calc(100% - 32px - 72px);
  }

  .map-info-panel.mobile {
    --panel-margin: 12px;
    --panel-collapsed-height: 160px;
    --menu-height: 56px;
    position: fixed;
    left: 50%;
    right: auto;
    top: calc(100% - var(--panel-collapsed-height) - var(--panel-margin));
    bottom: var(--panel-margin);
    width: min(280px, calc(100vw - 32px));
    height: var(--panel-collapsed-height);
    overflow: hidden;
    padding: 12px 14px;
    border-radius: 16px;
    transform: translateX(-50%);
    transition: top 0.22s ease, left 0.22s ease, right 0.22s ease, height 0.22s ease, width 0.22s ease, transform 0.22s ease, opacity 0.22s ease;
  }

  .map-info-panel.mobile :global(.entity-icon-wrapper) {
    max-width: 128px;
    margin: 0;
    flex: 0 0 auto;
    align-self: center;
    transition: max-width 0.22s ease, margin 0.22s ease;
  }

  .map-info-panel.mobile.expanded :global(.entity-icon-wrapper) {
    max-width: 110px;
    margin: 0 auto 8px;
  }

  .map-info-panel.mobile:not(.expanded) .info-header {
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }

  .map-info-panel.mobile.expanded {
    left: 50%;
    right: auto;
    top: calc(var(--menu-height) + var(--panel-margin));
    bottom: var(--panel-margin);
    width: min(280px, calc(100vw - 32px));
    height: calc(100% - (var(--menu-height) + var(--panel-margin) * 2));
    z-index: 25;
    transform: translateX(-50%);
  }

  .map-info-panel.mobile:not(.expanded).closing {
    transform: translateX(-50%) translateY(110%);
    opacity: 0;
  }

  .map-info-panel.mobile.expanded.closing {
    transform: translateX(-50%) translateY(110%);
    opacity: 0;
  }

  .panel-body {
    overflow-y: auto;
    max-height: calc(100% - 140px);
  }

  .map-info-panel.mobile .panel-body {
    max-height: calc(100% - 170px);
  }

  .panel-grip {
    width: 100%;
    background: transparent;
    border: none;
    display: flex;
    justify-content: center;
    padding: 0 0 6px 0;
  }

  .map-info-panel.mobile .panel-grip {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    z-index: 2;
  }

  .grip-bar {
    width: 44px;
    height: 4px;
    border-radius: 999px;
    background-color: var(--border-color, #555);
  }

  .header-main {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .header-text {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }

  .map-info-panel.mobile .header-main {
    flex-direction: row;
    align-items: center;
    gap: 10px;
    transition: gap 0.22s ease;
  }

  .map-info-panel.mobile.expanded .header-main {
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }

  .map-info-panel.mobile .header-text {
    flex: 1 1 auto;
  }

  .map-info-panel.mobile.expanded .header-text {
    width: 100%;
  }

  .mobile-compact-coords {
    display: flex;
    align-items: baseline;
    gap: 6px;
    font-size: 11px;
    margin-top: 4px;
    color: var(--text-muted, #999);
    max-height: 20px;
    overflow: hidden;
    opacity: 1;
    transition: max-height 0.22s ease, opacity 0.22s ease, margin-top 0.22s ease;
  }

  .mobile-compact-coords .coords-label {
    color: var(--text-muted, #999);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }

  .mobile-compact-coords .coords-value {
    color: var(--text-color);
    font-weight: 500;
  }


  .info-header {
    border-bottom: 1px solid var(--border-color, #555);
    padding-bottom: 10px;
    margin-bottom: 10px;
  }

  .map-info-panel.mobile .info-header {
    position: relative;
  }

  .map-info-panel.mobile.expanded .info-header {
    padding-top: 18px;
  }

  .info-title-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
  }

  .info-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
  }

  .info-subtitle {
    font-size: 12px;
    color: var(--text-muted, #999);
    margin-top: 4px;
  }

  .type-label {
    color: var(--text-muted, #999);
  }

  .icon-btn {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    border: 1px solid var(--border-color, #555);
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .info-section {
    margin-top: 12px;
  }

  .info-section h4 {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 6px;
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
    font-size: 10px;
    font-weight: 500;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .tag-points {
    font-size: 9px;
    color: var(--text-muted, #999);
    font-weight: 400;
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    font-size: 13px;
    margin-bottom: 6px;
    align-items: center;
  }

  .coords-row .stat-label {
    align-self: flex-start;
    padding-top: 6px;
  }

  .waypoint-row .stat-value {
    width: 100%;
  }

  .stat-bar-wrap {
    width: 140px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    align-items: flex-end;
  }

  .boss-badge {
    font-size: 10px;
    font-weight: 700;
    color: rgb(180, 80, 220);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .stat-bar-track {
    width: 100%;
    height: 7px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    overflow: hidden;
  }

  .stat-bar-fill {
    height: 100%;
    border-radius: 4px;
  }

  .density-bar-fill {
    background: rgb(100, 160, 220);
  }

  .waypoint-row :global(.waypoint-btn) {
    width: 100%;
    justify-content: flex-start;
  }

  .map-info-panel :global(.inline-edit) {
    width: 100%;
  }

  .stat-label {
    color: var(--text-muted, #999);
  }

  .stat-value {
    color: var(--text-color);
  }

  .coords-row {
    align-items: flex-start;
  }

  .coord-inputs {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px;
    width: 100%;
  }

  .section-edit-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .section-edit-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 88px 26px;
    gap: 8px;
    align-items: center;
    padding: 6px 8px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
    border: 1px solid var(--border-color, #555);
  }

  .section-edit-input {
    padding: 4px 8px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    font-size: 12px;
    font-family: inherit;
    min-width: 0;
  }

  .section-edit-input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .section-points {
    display: flex;
    align-items: center;
    gap: 4px;
    width: 88px;
  }

  .section-points-input {
    width: 64px;
  }

  .points-label {
    font-size: 11px;
    color: var(--text-muted, #999);
  }

  .section-remove {
    width: 26px;
    height: 26px;
    border-radius: 6px;
    border: 1px solid var(--border-color, #555);
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-muted, #999);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .section-remove:hover {
    color: var(--text-color);
    border-color: var(--accent-color, #4a9eff);
  }

  .section-add {
    align-self: flex-start;
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px dashed var(--border-color, #555);
    background-color: transparent;
    color: var(--text-muted, #999);
    font-size: 12px;
    cursor: pointer;
  }

  .section-add:hover {
    color: var(--text-color);
    border-color: var(--accent-color, #4a9eff);
  }

  .polygon-input {
    width: 100%;
    min-height: 70px;
    padding: 6px 8px;
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    font-size: 12px;
    font-family: inherit;
  }

  .muted {
    color: var(--text-muted, #999);
  }

  .teleporter-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .teleporter-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border: 1px solid var(--border-color, #555);
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
    color: var(--text-color);
    cursor: pointer;
    transition: border-color 0.15s, background-color 0.15s;
  }

  .teleporter-item:hover {
    border-color: var(--accent-color, #4dabf7);
    background-color: var(--hover-color, rgba(255, 255, 255, 0.05));
  }

  .teleporter-distance {
    font-size: 11px;
    color: var(--text-muted, #999);
  }

  .description-text {
    font-size: 13px;
    line-height: 1.5;
    color: var(--text-color);
  }

  .mob-types-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 8px;
  }

  .mob-type-row {
    font-size: 12px;
    line-height: 1.4;
  }

  .mob-name-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
    font-weight: 500;
  }

  .mob-name-link:hover {
    text-decoration: underline;
  }

  .mob-mat-range {
    color: var(--text-muted, #999);
  }

  .dialog-backdrop {
    position: fixed;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
    padding: 20px;
  }

  .dialog {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 10px;
    width: min(520px, 92vw);
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  }

  .dialog.dialog-compact {
    width: min(520px, 92vw);
  }

  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-color);
  }

  .close-btn {
    background: none;
    border: none;
    padding: 4px;
    cursor: pointer;
    color: var(--text-muted, #999);
    border-radius: 4px;
  }

  .close-btn:hover {
    color: var(--text-color);
    background-color: var(--hover-color) !important;
  }

  .dialog-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px 18px;
    font-size: 13px;
    color: var(--text-color);
    flex: 1;
    min-height: 0;
    overflow: auto;
  }

  .pending-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .pending-item {
    text-align: left;
    padding: 10px 12px;
    border: 1px solid var(--border-color, #555);
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 8px;
    color: var(--text-color);
    cursor: pointer;
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }

  .pending-item:hover {
    background-color: var(--hover-color);
    border-color: var(--accent-color, #4a9eff);
  }

  .pending-name {
    font-weight: 600;
  }

  .pending-meta {
    font-size: 11px;
    color: var(--text-muted, #999);
    margin-top: 4px;
  }

  @media (max-width: 899px) {
    .map-controls {
      left: 50%;
      right: auto;
      width: min(282px, calc(100vw - 32px));
      transform: translateX(-50%);
    }

    .map-controls .control-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .map-controls .control-row .control-group {
      gap: 4px;
      width: auto;
      min-width: 0;
    }

    .dialog-backdrop {
      padding: 8px;
      align-items: center;
    }

    .dialog {
      width: 100%;
      max-width: 100%;
      max-height: 92vh;
    }

    .dialog-header,
    .dialog-body {
      padding: 12px 16px;
    }

    .map-info-panel {
      position: fixed;
      left: 50%;
      right: auto;
      top: auto;
      bottom: 12px;
      width: min(280px, calc(100vw - 32px));
      max-height: none;
      transform: translateX(-50%);
    }

    .map-info-panel.editing {
      bottom: 12px;
      max-height: 200px;
      padding-bottom: 12px;
    }

    .edit-mode-btn {
      display: none;
    }
  }

  /* --- Edit Mode Button --- */

  .edit-mode-btn {
    position: absolute;
    bottom: 20px;
    right: 20px;
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 16px;
    border: none;
    border-radius: 8px;
    background: var(--accent-color);
    color: white;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    transition: opacity 0.15s ease;
  }
  .edit-mode-btn:hover { opacity: 0.9; }

  /* --- Leaflet Editor Overlay --- */

  .leaflet-editor-overlay {
    position: absolute;
    inset: 0;
    z-index: 30;
    display: flex;
    flex-direction: column;
    background: var(--primary-color);
  }

  .editor-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 16px;
    background: var(--secondary-color);
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .editor-toolbar-label {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  .editor-toolbar-right {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .editor-toolbar-btn {
    position: relative;
    padding: 6px 12px;
    font-size: 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    cursor: pointer;
  }
  .editor-toolbar-btn:hover { background: var(--hover-color); }
  .editor-toolbar-btn.active { border-color: var(--accent-color); color: var(--accent-color); }

  .editor-exit-btn {
    border-color: #ef4444;
    color: #ef4444;
  }
  .editor-exit-btn:hover { background: rgba(239, 68, 68, 0.15); }

  .editor-badge {
    position: absolute;
    top: -6px;
    right: -6px;
    min-width: 16px;
    height: 16px;
    padding: 0 4px;
    border-radius: 8px;
    background: #ef4444;
    color: white;
    font-size: 10px;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
  }

</style>
