<script>
  //@ts-nocheck
  import '$lib/style.css';

  import { page } from '$app/stores';
  import { goto, beforeNavigate } from '$app/navigation';
  import { onMount, untrack } from 'svelte';
  import { SvelteMap } from 'svelte/reactivity';
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
  import WaypointCopyButton from '$lib/components/wiki/WaypointCopyButton.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';

  // Map Editor components (Leaflet-based edit mode) — loaded dynamically to avoid SSR issues
  import { browser } from '$app/environment';

  let MapEditorWorkspace = $state(), ChangesSummary = $state();

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
    existingPendingChange,
    viewingPendingChange,
    setExistingPendingChange,
    setViewingPendingChange
  } from '$lib/stores/wikiEditState';

  let { data = $bindable() } = $props();

  let mapRef = $state();
  let currentSlug = $state(null);
  let searchQuery = $state('');
  let searchOpen = $state(false);
  let selectedLocation = $state(null);
  let hoveredLocation = $state(null);
  let lastFocusedId = null;
  let pendingDialogOpen = $state(false);
  let selectedMainPlanet = $state('');
  let selectedSubArea = $state('');
  let subAreas = $state([]);
  let lastPlanetGroup = null;
  let lastPlanetSlug = null;
  let isMobile = $state(false);
  let panelExpanded = $state(false);
  let panelClosing = $state(false);
  let touchStartY = 0;
  let touchDeltaY = 0;
  let apartmentDetails = $state({});
  let apartmentFetches = new Set();
  let apartmentDetailsLoaded = new Set();
  let selectedDetails = $state(null);
  let searchResultsHovered = $state(false);
  let searchSelectedIndex = $state(-1);
  let panelLoading = $state(false);
  let activatingLeaflet = false;
  let autoLeafletHandledKey = null;

  // --- Leaflet Edit Mode state ---
  let leafletEditMode = $state(false);
  let editorPendingChanges = $state(new SvelteMap());
  let editorRightPanel = $state('editor');
  let editorChangeCount = $derived(Array.from(editorPendingChanges.values()).filter(c => !c._dbSeeded).length);
  let editorDbChangeIdMap = $state(new SvelteMap());
  let allMobs = $state([]);
  let seededChangeId = null;
  let planetPendingOverride = $state(null);
  let manualEditFocus = $state(null);
  let manualEditFocusKey = $state(null);

  async function handleChangesSubmitted() {
    editorPendingChanges = new SvelteMap();
    editorDbChangeIdMap = new SvelteMap();
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

  /** Check if there are real unsaved local changes in the editor */
  function hasUnsavedEditorChanges() {
    if (!leafletEditMode) return false;
    const realChangeCount = Array.from(editorPendingChanges.values()).filter(c => !c._dbSeeded).length;
    return seededChangeId
      ? realChangeCount > 1 || (realChangeCount === 1 && !editorPendingChanges.has(-seededChangeId))
      : realChangeCount > 0;
  }

  function deactivateEditMode() {
    if (hasUnsavedEditorChanges()) {
      if (!confirm('You have unsaved changes. Discard and exit edit mode?')) return;
    }
    leafletEditMode = false;
    editorPendingChanges = new SvelteMap();
    editorRightPanel = 'editor';
    seededChangeId = null;
    manualEditFocus = null;
    manualEditFocusKey = null;
  }

  // Guard against navigating away with unsaved changes (in-app navigation)
  beforeNavigate(({ cancel, to }) => {
    if (!leafletEditMode) return;

    const isSameRoute = to?.route?.id === $page.route.id;
    const targetPlanet = to?.params?.planet;
    const currentPlanetSlug = $page.params.planet;
    const isPlanetChange = isSameRoute && targetPlanet && targetPlanet !== currentPlanetSlug;

    if (isPlanetChange) {
      if (hasUnsavedEditorChanges()) {
        if (!confirm('You have unsaved changes. Discard and switch planet?')) {
          cancel();
          return;
        }
      }
      // Reset editor state — new planet data will load via SvelteKit
      editorPendingChanges = new SvelteMap();
      editorDbChangeIdMap = new SvelteMap();
      editorRightPanel = 'editor';
      seededChangeId = null;
      manualEditFocus = null;
      manualEditFocusKey = null;
      return;
    }

    if (isSameRoute) return; // same planet, same route — allow

    if (hasUnsavedEditorChanges()) {
      if (!confirm('You have unsaved map editor changes. Discard and leave this page?')) {
        cancel();
      }
    }
  });

  /** Switch planet while in edit mode — prompt if unsaved changes */
  function switchEditorPlanet(slug) {
    if (!slug) return;
    const currentSlugNorm = normalizePlanetSlug(currentPlanet?.Name);
    if (slug === currentSlugNorm) return;
    if (hasUnsavedEditorChanges()) {
      if (!confirm('You have unsaved changes. Discard and switch planet?')) return;
    }
    // Reset editor state before navigating
    editorPendingChanges = new SvelteMap();
    editorDbChangeIdMap = new SvelteMap();
    editorRightPanel = 'editor';
    seededChangeId = null;
    manualEditFocus = null;
    manualEditFocusKey = null;
    goto(`/maps/${slug}?mode=edit`);
  }

  // Build flat list of all planets for the editor dropdown
  const allMapPlanets = Object.entries(planetGroups).flatMap(([group, planets]) =>
    planets.map(p => ({ ...p, group: group === 'NextIsland' ? 'Next Island' : group }))
  );

  const mainPlanets = getMainPlanetNames();

  const ESTATE_ID_OFFSET = 300000;
  const DEFAULT_VISIBLE_LOCATION_TYPES = new Set(['Teleporter']);
  const DEFAULT_VISIBLE_AREA_TYPES = new Set(['PvpArea', 'PvpLootArea', 'ZoneArea']);



  function convertChangeToModified(changeData, tempId) {
    if (!changeData?.Properties) return null;
    const props = changeData.Properties;
    const coords = props.Coordinates || {};
    const isArea = props.Shape || props.AreaType || props.Type === 'Area';
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
    if (changeData?.Maturities?.length || props.Density != null) {
      modified.mobData = { density: props.Density ?? 4, maturities: changeData.Maturities || [] };
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
    if (location?.Properties?.AreaType === 'MobArea') return null;
    if (location?.Properties?.Type === 'Shop') return null;
    if (location?.Properties?.Type === 'Apartment') return 'Apartment';
    if (location?.Properties?.Type === 'Area' || location?.Properties?.Shape) {
      return 'Area';
    }
    return 'Location';
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















  function getDisplayName(loc) {
    if (loc.Properties?.AreaType === 'MobArea') return getMobAreaShortName(loc.Name);
    return loc.Name;
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
    goto(`/maps/${$page.params.planet}?mode=create`);
  }

  async function handleEdit() {
    if (!isEditAllowed || !activeLocation) return;
    const loc = selectedLocation || activeLocation;
    manualEditFocus = loc;
    manualEditFocusKey = `edit-${loc.Id}-${Date.now()}`;
    await activateEditMode();
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


  function isDefaultVisibleType(loc) {
    const type = loc?.Properties?.Type;
    const areaType = loc?.Properties?.AreaType;
    if (!type) return false;
    if (areaType === 'MobArea') return false;
    if (type === 'Area' || areaType) {
      return DEFAULT_VISIBLE_AREA_TYPES.has(areaType);
    }
    return DEFAULT_VISIBLE_LOCATION_TYPES.has(type);
  }


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

  let user = $derived(data.session?.user);
  let canEdit = $derived(user?.verified || user?.grants?.includes('wiki.edit'));
  let isEditAllowed = $derived(canEdit && !isMobile);
  let routeMode = $derived(($page.url.searchParams.get('mode') || '').toLowerCase());
  let routeChangeId = $derived($page.url.searchParams.get('changeId'));
  let currentPlanet = $derived(data?.additional?.planet);
  let shouldAutoOpenLeaflet = $derived(!!currentPlanet && isEditAllowed && (routeMode === 'edit' || routeMode === 'create'));
  let autoLeafletKey = $derived(`${$page.url.pathname}|${routeMode}|${routeChangeId || ''}`);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let pendingChange = $derived(data.pendingChange);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  let hasPendingChanges = $derived(userPendingCreates.length + userPendingUpdates.length > 0);
  let locations = $derived(data?.additional?.locations || []);
  let isCreateMode = $derived(data.isCreateMode || false);
  $effect(() => {
    if (locations) {
      const slug = $page.params.slug;
      if (!slug) {
        currentSlug = null;
        selectedLocation = null;
        if (isMobile) {
          panelExpanded = false;
        }
      } else if (slug !== untrack(() => currentSlug) && !isCreateMode) {
        currentSlug = slug;
        // Only update selectedLocation if it doesn't already match the slug.
        // This prevents a race condition where the URL updates before new locations
        // data arrives, which would clear the selection set by selectLocation().
        if (!untrack(() => selectedLocation) || untrack(() => selectedLocation).Id != slug) {
          const found = findLocationBySlug(slug, locations) || data.object;
          selectedLocation = found;
        }
      }
    }
  });
  let locationEntityId = $derived(selectedLocation?.Id ?? selectedLocation?.ItemId);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, locationEntityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  // Pre-compute difficulty for MobArea locations
  $effect(() => {
    if (locations.length) {
      for (const loc of locations) {
        if (loc.Properties?.AreaType === 'MobArea' && !loc._difficulty) {
          loc._difficulty = getMobAreaDifficulty(loc.Maturities);
        }
      }
    }
  });
  let error = $derived(data.error);
  let effectiveCreateMode = $derived(isCreateMode && isEditAllowed);
  $effect(() => {
    if (resolvedPendingChange) {
      setExistingPendingChange(resolvedPendingChange);
    } else {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
    }
  });
  $effect(() => {
    if (selectedLocation && isApartmentType(selectedLocation?.Properties?.Type)) {
      const viewId = selectedLocation.Id;
      selectedDetails = apartmentDetails[viewId] || null;
      if (!apartmentDetailsLoaded.has(viewId) && !selectedDetails) {
        fetchApartmentDetails(selectedLocation);
      }
    } else {
      selectedDetails = null;
    }
  });
  let activeLocation = $derived(($viewingPendingChange && $existingPendingChange?.data)
    ? $existingPendingChange.data
    : (selectedDetails || selectedLocation));
  let selectedEntityType = $derived(getEntityTypeForLocation(selectedLocation));
  let activeEntityType = $derived(selectedEntityType);
  let isAreaEntity = $derived(!!activeLocation?.Properties?.Shape || isAreaType(activeLocation?.Properties?.Type));
  let isApartmentEntity = $derived(isApartmentType(activeLocation?.Properties?.Type) || activeEntityType === 'Apartment');
  let hasLocationContent = $derived(!isMobile && !!activeLocation?.Properties?.Coordinates);
  $effect(() => {
    if (mapRef && selectedLocation?.Id && selectedLocation.Id !== untrack(() => lastFocusedId)) {
      lastFocusedId = selectedLocation.Id;
      mapRef.focusOnLocation(selectedLocation);
    }
  });
  let canEditExistingChange = $derived(data.existingChange?.id && (
    data.existingChange.author_id === user?.id ||
    user?.grants?.includes('wiki.approve')
  ));
  let leafletFocusLocation = $derived((() => {
    if (manualEditFocus) return manualEditFocus;
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
  })());
  let leafletFocusKey = $derived(manualEditFocusKey
    || (shouldAutoOpenLeaflet ? `${$page.url.pathname}|${routeMode}|${routeChangeId || ''}` : null));
  // Seed editorPendingChanges for author/admin viewing an existing Create change
  $effect(() => {
    if (leafletEditMode && data.existingChange?.id && data.existingChange.type === 'Create'
        && canEditExistingChange && untrack(() => seededChangeId) !== data.existingChange.id) {
      seededChangeId = data.existingChange.id;
      const tempId = -data.existingChange.id;
      const modified = convertChangeToModified(data.existingChange.data, tempId);
      if (modified) {
        editorPendingChanges.set(tempId, { action: 'add', original: null, modified });
      }
    }
  });
  $effect(() => {
    if (shouldAutoOpenLeaflet && untrack(() => autoLeafletHandledKey) !== autoLeafletKey && !leafletEditMode) {
      autoLeafletHandledKey = autoLeafletKey;
      activateEditMode();
    }
  });
  $effect(() => {
    if (currentPlanet) {
      const group = getPlanetGroupByType($page.params.planet) || getPlanetGroupByType(normalizePlanetSlug(currentPlanet.Name));
      const planetSlug = $page.params.planet;
      if (group && (group.groupName !== untrack(() => lastPlanetGroup) || planetSlug !== untrack(() => lastPlanetSlug))) {
        selectedMainPlanet = group.groupName;
        subAreas = group.list;
        const match = group.list.find((entry) => entry._type === planetSlug);
        selectedSubArea = match ? match._type : group.list[0]?._type;
        lastPlanetGroup = group.groupName;
        lastPlanetSlug = planetSlug;
      }
    }
  });
  $effect(() => {
    if (!currentPlanet && !untrack(() => selectedMainPlanet) && mainPlanets.length > 0) {
      selectedMainPlanet = mainPlanets[0];
      subAreas = planetGroups[selectedMainPlanet] || [];
      selectedSubArea = subAreas[0]?._type || '';
    }
  });
  let searchResults = $derived((() => {
    const query = searchQuery.trim();
    if (!query) return [];
    return locations
      .map((item) => ({
        item,
        score: Math.max(
          fuzzyScore(item.Name, query),
          item.Properties?.AreaType === 'MobArea' ? fuzzyScore(getMobAreaShortName(item.Name), query) : 0,
          fuzzyScore(item.Properties?.Type, query) * 0.4
        )
      }))
      .filter((entry) => entry.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 20)
      .map((entry) => entry.item);
  })());
  $effect(() => {
    if (!searchQuery.trim()) {
      searchOpen = false;
    }
  });
  // Reset keyboard selection when results change
  $effect(() => {
    searchResults, searchSelectedIndex = -1;
  });
  // Clear hover state when search closes
  $effect(() => {
    if (!searchOpen && untrack(() => searchResultsHovered)) {
      searchResultsHovered = false;
      hoveredLocation = null;
    }
  });
  let closestTeleporters = $derived(getClosestTeleporters(activeLocation));
  let filteredLocations = $derived((() => {
    const base = (locations || []).filter((loc) => isDefaultVisibleType(loc));
    if (selectedLocation && !base.some((loc) => loc.Id === selectedLocation.Id)) {
      return [...base, selectedLocation];
    }
    return base;
  })());
  $effect(() => {
    if (selectedLocation) {
      panelClosing = false;
    }
  });
  $effect(() => {
    if (isMobile && (selectedLocation || effectiveCreateMode)) {
      panelClosing = false;
    }
  });
</script>

<svelte:head>
  <title>{currentPlanet ? `${currentPlanet.Name} Map` : 'Maps'} - Entropia Nexus</title>
  <meta name="description" content="{currentPlanet ? `Interactive map for ${currentPlanet.Name}.` : 'Interactive maps for every planet and moon in Entropia Universe.'}" />
  {#if currentPlanet}
    <link rel="canonical" href="https://entropianexus.com/maps/{normalizePlanetSlug(currentPlanet.Name)}" />
  {:else}
    <link rel="canonical" href="https://entropianexus.com/maps" />
  {/if}
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
        <div class="maps-overview">
          <header class="overview-header">
            <h1>Maps</h1>
            <p class="overview-subtitle">Interactive maps for Entropia Universe planets and moons</p>
          </header>
          <div class="planet-grid">
            {#each Object.entries(planetGroups) as [groupName, planets]}
              {@const main = planets[0]}
              {@const subs = planets.slice(1)}
              <div class="planet-group">
                <a href="/maps/{main._type}" class="planet-card main">
                  <img src="/{main._type}.jpg" alt={main.Name} class="planet-image" loading="lazy" />
                  <div class="planet-overlay">
                    <span class="planet-name">{main.Name}</span>
                  </div>
                </a>
                {#if subs.length > 0}
                  <div class="sub-planets">
                    {#each subs as sub}
                      <a href="/maps/{sub._type}" class="planet-card sub">
                        <img src="/{sub._type}.jpg" alt={sub.Name} class="sub-planet-image" loading="lazy" />
                        <div class="planet-overlay">
                          <span class="planet-name">{sub.Name}</span>
                        </div>
                      </a>
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}
    {:else}
      <div class="info error"><h2>{error}</h2><br />{getErrorMessage(error)}</div>
    {/if}
  </div>

  {#if currentPlanet}
  <div class="map-controls">
    <div class="control-row">
      <div class="control-group">
        <label for="map-planet">Planet</label>
        <select id="map-planet" bind:value={selectedMainPlanet} onchange={handleMainPlanetChange}>
          {#each mainPlanets as planetName}
            <option value={planetName}>{planetGroups[planetName]?.[0]?.Name || planetName}</option>
          {/each}
        </select>
      </div>
      <div class="control-group">
        <label for="map-area">Area</label>
        <select id="map-area" bind:value={selectedSubArea} onchange={handleSubAreaChange}>
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
        onfocus={() => searchOpen = true}
        onblur={handleSearchBlur}
        onkeydown={handleSearchKeydown}
      />

      {#if isEditAllowed}
        <button class="create-btn" onclick={handleCreate} title={canCreateNew ? 'Create new location/area' : 'Create limit reached'} disabled={!canCreateNew}>
          +
        </button>
        {#if hasPendingChanges}
          <button class="pending-btn" onclick={() => pendingDialogOpen = true} title="Your pending changes">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <path d="M12 6v6l4 2"></path>
            </svg>
          </button>
        {/if}
      {/if}
    </div>

    {#if searchOpen && searchResults.length > 0}
      <!-- svelte-ignore a11y_no_static_element_interactions -- mouse hover tracking for search results dropdown; keyboard nav handled via parent input -->
      <div
        class="search-results"
        onmouseenter={() => searchResultsHovered = true}
        onmouseleave={() => { searchResultsHovered = false; hoveredLocation = null; }}
      >
        {#each searchResults as result, index}
          <button
            class="search-result"
            class:active={searchSelectedIndex === index}
            onclick={() => { searchSelectedIndex = index; if (isMobile) searchOpen = false; selectLocation(result, { focus: true }); }}
            onmouseenter={() => { searchSelectedIndex = index; hoveredLocation = result; mapRef?.panTo(result); }}
            onmouseleave={() => {}}
          >
            <span class="result-index">{index + 1}</span>
            <span class="result-name" style={result._difficulty?.color ? `color: ${result._difficulty.color}` : ''}>{getDisplayName(result)}</span>
            <span class="result-type">{result.Properties?.Type || 'Location'}</span>
          </button>
        {/each}
      </div>
    {/if}
  </div>
  {/if}

  {#if activeLocation && !($existingPendingChange && !effectiveCreateMode)}
    <aside
      class="map-info-panel"
      class:mobile={isMobile}
      class:expanded={panelExpanded}
      class:closing={panelClosing}
      ontouchstart={handlePanelTouchStart}
      ontouchmove={handlePanelTouchMove}
      ontouchend={handlePanelTouchEnd}
    >
      {#if panelLoading}
        <div class="panel-loading-overlay">
          <div class="loading-spinner"></div>
        </div>
      {/if}
      <div class="info-header">
        {#if isMobile}
          <button class="panel-grip" onclick={handlePanelToggle} aria-label="Toggle details">
            <span class="grip-bar"></span>
          </button>
        {/if}
        <div class="header-main">
          <div class="header-text">
            <div class="info-title-row">
              <div class="info-title" style={activeLocation?._difficulty?.color ? `color: ${activeLocation._difficulty.color}` : ''}>
                {getDisplayName(activeLocation)}
              </div>
              {#if isEditAllowed && activeEntityType}
                <button class="icon-btn" onclick={handleEdit} title="Edit location">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                </button>
              {/if}
            </div>
            <div class="info-subtitle">
              <span class="type-label">{activeLocation?.Properties?.Type || 'Location'}</span>
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
              {#if !isMobile}
              <div class="stat-row waypoint-row">
                <span class="stat-value">
                  {#if activeLocation?.Properties?.Coordinates}
                    <WaypointCopyButton waypoint={getWaypointFromLocation(activeLocation)} />
                  {/if}
                  </span>
                </div>
              {/if}
            </div>
          {/if}

            {#if isApartmentEntity}
              <div class="info-section">
                <h4>Estate Areas</h4>
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
              </div>
            {/if}

            <div class="info-section">
              <h4>Closest Teleporters</h4>
                {#if closestTeleporters.length === 0}
                  <div class="muted">No teleporters found.</div>
                {:else}
                  <div class="teleporter-list">
                    {#each closestTeleporters as teleporter}
                      <button class="teleporter-item"
                        onclick={() => selectLocation(teleporter, { focus: true })}
                        onmouseenter={() => { hoveredLocation = teleporter; mapRef?.panTo(teleporter); }}
                        onmouseleave={() => { hoveredLocation = null; if (selectedLocation) mapRef?.panTo(selectedLocation); }}
                      >
                        <span class="teleporter-name">{teleporter.Name}</span>
                        <span class="teleporter-distance">{teleporter._distance?.toFixed(0)} m</span>
                      </button>
                    {/each}
                  </div>
                {/if}
              </div>

          {#if activeLocation?.Properties?.AreaType === 'MobArea'}
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
                <div class="description-text">{@html activeLocation.Properties.Notes}</div>
              {/if}
            </div>
          {/if}

          {#if activeLocation?.Properties?.AreaType === 'LandArea'}
            <div class="info-section">
              <h4>Land Area</h4>
              <div class="stat-row">
                <span class="stat-label">Hunting Tax</span>
                <span class="stat-value">
                  {activeLocation?.Properties?.TaxRateHunting != null ? `${activeLocation.Properties.TaxRateHunting}%` : '—'}
                </span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Mining Tax</span>
                <span class="stat-value">
                  {activeLocation?.Properties?.TaxRateMining != null ? `${activeLocation.Properties.TaxRateMining}%` : '—'}
                </span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Shops Tax</span>
                <span class="stat-value">
                  {activeLocation?.Properties?.TaxRateShops != null ? `${activeLocation.Properties.TaxRateShops}%` : '—'}
                </span>
              </div>
            </div>
          {/if}

          <div class="info-section">
            <h4>Description</h4>
            {#if activeLocation?.Properties?.Description}
              <div class="description-text">{@html activeLocation.Properties.Description}</div>
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
      role="presentation"
      onclick={() => pendingDialogOpen = false}
      onkeydown={(e) => e.key === 'Escape' && (pendingDialogOpen = false)}
    >
      <div class="dialog dialog-compact" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
        <div class="dialog-header">
          <h3>Your Drafts & Reviews</h3>
          <button class="close-btn" onclick={() => pendingDialogOpen = false} aria-label="Close dialog">
            ×
          </button>
        </div>
        <div class="dialog-body">
          <div class="pending-list">
            {#each [...userPendingCreates, ...userPendingUpdates] as change}
              <button class="pending-item" onclick={() => handlePendingSelect(change)}>
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
    <button class="edit-mode-btn" onclick={activateEditMode} title="Open Leaflet map editor">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
        <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
      </svg>
      Edit Mode
    </button>
  {/if}

  <!-- Leaflet Editor Layout (replaces canvas view) -->
  {#if leafletEditMode && MapEditorWorkspace}
    {@const isSubEditor = editorRightPanel === 'mobEditor' || editorRightPanel === 'waveEditor'}
    <div class="leaflet-editor-overlay">
      <div class="editor-toolbar">
        <div class="editor-toolbar-left">
          <select
            class="editor-planet-select"
            value={normalizePlanetSlug(currentPlanet?.Name)}
            onchange={(e) => switchEditorPlanet(e.target.value)}
          >
            {#each allMapPlanets as planet}
              <option value={planet._type}>{planet.Name}</option>
            {/each}
          </select>
          <span class="editor-toolbar-mode">Edit Mode</span>
        </div>

        <div class="editor-toolbar-right">
          <button
            class="editor-toolbar-btn"
            class:active={editorRightPanel === 'changes'}
            disabled={isSubEditor}
            title={isSubEditor ? 'Save or cancel the current editor first' : ''}
            onclick={() => {
              if (isSubEditor) return;
              editorRightPanel = editorRightPanel === 'changes' ? 'editor' : 'changes';
            }}
          >
            Changes
            {#if editorChangeCount > 0}
              <span class="editor-badge">{editorChangeCount}</span>
            {/if}
          </button>
          <button class="editor-toolbar-btn editor-exit-btn" onclick={deactivateEditMode}>
            Exit Edit Mode
          </button>
        </div>
      </div>

      <MapEditorWorkspace
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
        bind:dbChangeIdMap={editorDbChangeIdMap}
      >
        {#snippet output()}
              
            <ChangesSummary
              pendingChanges={editorPendingChanges}
              planet={currentPlanet}
              isAdmin={user?.grants?.includes('admin.panel') || user?.administrator || false}
              dbChangeIdMap={editorDbChangeIdMap}
              onclear={() => { editorPendingChanges = new SvelteMap(); editorDbChangeIdMap = new SvelteMap(); }}
              onsubmitted={handleChangesSubmitted}
              onremoved={() => {}}
              onchangeCreated={(ev) => {
                editorDbChangeIdMap.set(ev.key, ev.changeId);
              }}
              ondbChangeDeleted={(ev) => {
                if (planetPendingOverride) {
                  planetPendingOverride = planetPendingOverride.filter(c => c.id !== ev.dbId);
                } else if (data.planetPendingChanges) {
                  data.planetPendingChanges = data.planetPendingChanges.filter(c => c.id !== ev.dbId);
                }
              }}
            />
          
              {/snippet}
      </MapEditorWorkspace>
    </div>
  {/if}
</div>

<svelte:window onbeforeunload={(e) => {
  if (hasUnsavedEditorChanges()) {
    e.preventDefault();
    return '';
  }
}} />

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

  .maps-overview {
    width: 100%;
    height: 100%;
    overflow-y: auto;
    padding: 24px;
    max-width: 1200px;
    margin: 0 auto;
  }

  .overview-header {
    text-align: center;
    margin-bottom: 32px;
  }

  .overview-header h1 {
    margin: 0 0 8px 0;
    color: var(--text-color);
    font-size: 2rem;
  }

  .overview-subtitle {
    margin: 0;
    color: var(--text-muted);
    font-size: 1.1rem;
  }

  .planet-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 24px;
  }

  .planet-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .planet-card {
    position: relative;
    display: block;
    overflow: hidden;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    text-decoration: none;
    transition: border-color 0.2s ease, transform 0.2s ease;
  }

  .planet-card:hover {
    border-color: var(--accent-color);
    transform: translateY(-2px);
  }

  .planet-card.main {
    aspect-ratio: 16 / 10;
  }

  .planet-image,
  .sub-planet-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .planet-overlay {
    position: absolute;
    inset: 0;
    background: linear-gradient(to top, rgba(0, 0, 0, 0.7) 0%, transparent 60%);
    display: flex;
    align-items: flex-end;
    padding: 12px;
  }

  .planet-name {
    color: #fff;
    font-size: 1.1rem;
    font-weight: 600;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
  }

  .sub-planets {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 8px;
  }

  .planet-card.sub {
    aspect-ratio: 4 / 3;
  }

  .planet-card.sub .planet-name {
    font-size: 0.8rem;
  }

  .planet-card.sub .planet-overlay {
    padding: 8px;
  }

  @media (max-width: 768px) {
    .maps-overview {
      padding: 16px;
    }

    .overview-header h1 {
      font-size: 1.5rem;
    }

    .overview-subtitle {
      font-size: 1rem;
    }

    .planet-grid {
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
    }
  }

  @media (max-width: 480px) {
    .planet-grid {
      grid-template-columns: 1fr;
    }
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

  .stat-label {
    color: var(--text-muted, #999);
  }

  .stat-value {
    color: var(--text-color);
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

  .teleporter-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }

  .teleporter-distance {
    font-size: 11px;
    color: var(--text-muted, #999);
    flex-shrink: 0;
  }

  .description-text {
    font-size: 13px;
    line-height: 1.5;
    color: var(--text-color);
    overflow-wrap: break-word;
    word-break: break-word;
  }

  .description-text :global(img) {
    max-width: 100%;
    height: auto;
    border-radius: 4px;
  }

  .description-text :global(h1),
  .description-text :global(h2),
  .description-text :global(h3),
  .description-text :global(h4) {
    font-size: 14px;
    margin: 8px 0 4px;
  }

  .description-text :global(p) {
    margin: 4px 0;
  }

  .description-text :global(a) {
    color: var(--accent-color, #4a9eff);
  }

  .description-text :global(table) {
    width: 100%;
    font-size: 12px;
    border-collapse: collapse;
  }

  .description-text :global(td),
  .description-text :global(th) {
    padding: 2px 4px;
    border: 1px solid var(--border-color);
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

  .editor-toolbar-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .editor-planet-select {
    padding: 4px 8px;
    font-size: 13px;
    font-weight: 600;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    cursor: pointer;
  }
  .editor-planet-select:focus { outline: none; border-color: var(--accent-color); }

  .editor-toolbar-mode {
    font-size: 12px;
    color: var(--text-muted);
    font-weight: 500;
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
