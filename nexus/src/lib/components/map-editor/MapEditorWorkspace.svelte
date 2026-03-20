<script>
  // @ts-nocheck
  import MapEditorLeaflet from './MapEditorLeaflet.svelte';
  import LocationList from './LocationList.svelte';
  import LocationEditor from './LocationEditor.svelte';
  import MobAreaEditor from './MobAreaEditor.svelte';
  import WaveEventEditor from './WaveEventEditor.svelte';
  import { isArea, DEFAULT_ALTITUDE } from './mapEditorUtils.js';
  import { SvelteMap } from 'svelte/reactivity';

  
  
  
  

  // --- DB pending changes (from all users) ---
  

  
  /**
   * @typedef {Object} Props
   * @property {any} [planet] - --- Required props ---
   * @property {any} [locations]
   * @property {any} [allMobs]
   * @property {boolean} [editMode]
   * @property {boolean} [loading]
   * @property {'admin' | 'public'} [mode]
   * @property {any} [focusLocation] - Location-like object to focus when opening editor from route mode links
   * @property {any} [focusKey] - Stable key so focus is only applied once per navigation
   * @property {Array} [dbPendingChanges]
   * @property {any} [currentUserId]
   * @property {boolean} [isAdmin]
   * @property {any} [pendingChanges] - --- Bindable state (parent reads/controls) ---
   * @property {string} [rightPanel] - 'editor' | 'mobEditor' | <any other value shows output slot>
   * @property {any} [mapComponent]
   * @property {number} [changeCount] - (deprecated, computed in parent)
   * @property {any} [dbChangeIdMap]
   * @property {import('svelte').Snippet} [output]
   */

  /** @type {Props} */
  let {
    planet = null,
    locations = [],
    allMobs = [],
    editMode = false,
    loading = false,
    mode = 'admin',
    focusLocation = null,
    focusKey = null,
    dbPendingChanges = $bindable([]),
    currentUserId = null,
    isAdmin = false,
    pendingChanges = $bindable(new SvelteMap()),
    rightPanel = $bindable('editor'),
    mapComponent = $bindable(undefined),
    changeCount = $bindable(0), // kept for reset() compat; parent should compute independently
    dbChangeIdMap = $bindable(new SvelteMap()),
    output
  } = $props();


  // --- Internal state ---
  let selectedId = $state(null);
  let isNewLocation = $state(false);
  let drawnShapeData = $state(null);
  let previewShape = $state(null);
  let mobEditorContext = $state(null);
  let filteredLocationIds = $state(null);
  let nextTempId = -1;
  let lastAppliedFocusKey = null;
  let waveEditorContext = $state(null);
  let selectedDbChange = $state(null); // DB pending change selected for read-only viewing
  let modifiedDbChanges = new Set(); // DB-seeded changes that have been locally modified

  // --- Exported method ---
  export function reset() {
    pendingChanges = new SvelteMap();
    dbChangeIdMap = new SvelteMap();
    modifiedDbChanges = new Set();
    selectedId = null;
    selectedDbChange = null;
    isNewLocation = false;
    drawnShapeData = null;
    rightPanel = 'editor';
    previewShape = null;
    mobEditorContext = null;
    waveEditorContext = null;
    filteredLocationIds = null;
    nextTempId = -1;
    changeCount = 0;
    if (mapComponent?.clearDrawnLayer) mapComponent.clearDrawnLayer();
    if (mapComponent?.rebuildDbOverlay) mapComponent.rebuildDbOverlay();
  }


  /** Extract pending mob data ({ density, maturities }) from a modified object, or null. */
  function getPendingMobData(id) {
    const m = pendingChanges.get(id)?.modified;
    return m?.density != null || m?.maturities ? { density: m.density, maturities: m.maturities } : null;
  }

  /** Extract pending wave data ({ waves }) from a modified object, or null. */
  function getPendingWaveData(id) {
    const m = pendingChanges.get(id)?.modified;
    return m?.waves ? { waves: m.waves } : null;
  }

  // Show cyan afterimage of the ORIGINAL shape for a given location
  function showAfterimageForOriginal(locId) {
    const loc = locations.find(l => l.Id === locId);
    if (!loc) { previewShape = null; return; }
    if (isArea(loc)) {
      previewShape = { shape: loc.Properties.Shape, data: loc.Properties.Data, center: null };
    } else {
      const coords = loc.Properties?.Coordinates;
      previewShape = coords
        ? { shape: null, data: null, center: { x: coords.Longitude, y: coords.Latitude } }
        : null;
    }
  }




  // --- Event handlers ---
  function handleMapSelect(id) {
    selectedId = id;
    selectedDbChange = null;
    isNewLocation = false;
    drawnShapeData = null;
    previewShape = null;
    rightPanel = 'editor';
    if (mapComponent?.clearDrawnLayer) mapComponent.clearDrawnLayer();
    // Show afterimage if this location has a pending edit
    if (selectedId && pendingChanges.has(selectedId) && pendingChanges.get(selectedId).action === 'edit') {
      showAfterimageForOriginal(selectedId);
    }
  }

  function handleSelectDbChange(change) {
    const isOwnChange = change.author_id === currentUserId;

    if (isOwnChange || isAdmin) {
      // Seed into local pending changes so the author/admin can edit
      selectedDbChange = null; // Clear read-only state from any previous DB change selection
      const data = change.data;
      const props = data?.Properties || {};
      const isAreaType = props.Shape || props.AreaType || props.Type === 'Area';

      if (change.type === 'Create') {
        // Seed as a pending add
        const tempId = -change.id;
        if (!pendingChanges.has(tempId)) {
          const modified = {
            name: data?.Name || '',
            locationType: isAreaType ? 'Area' : (props.Type || 'Location'),
            longitude: props.Coordinates?.Longitude ?? 0,
            latitude: props.Coordinates?.Latitude ?? 0,
            altitude: props.Coordinates?.Altitude ?? null,
            areaType: isAreaType ? (props.AreaType || 'MobArea') : null,
            shape: props.Shape || null,
            shapeData: props.Data || null,
            parentLocationName: data?.ParentLocation?.Name || null,
            description: props.Description || null,
            landAreaOwner: data?.Owner?.Name || props.LandAreaOwnerName || null,
            taxRateHunting: props.TaxRateHunting ?? null,
            taxRateMining: props.TaxRateMining ?? null,
            taxRateShops: props.TaxRateShops ?? null,
            tempId
          };
          // Restore mob data if persisted in the change
          if (data?.Maturities?.length || props.Density != null) {
            modified.density = props.Density ?? 4;
            modified.maturities = data.Maturities || [];
          }
          // Restore wave data if persisted in the change
          if (data?.Waves) {
            modified.waves = data.Waves;
          }
          pendingChanges.set(tempId, { action: 'edit', original: null, modified, _dbSeeded: true });
          dbChangeIdMap.set(tempId, change.id);

          if (mapComponent?.rebuildDbOverlay) mapComponent.rebuildDbOverlay();
          // Force immediate rebuild so the pending add layer exists in layerGroup
          // before updateSelection runs — rebuildDbOverlay already removed the DB
          // overlay layer, and the RAF-deferred rebuildLayers may not fire in time.
          if (mapComponent?.forceRebuild) mapComponent.forceRebuild();
        }
        selectedId = tempId;
        isNewLocation = false;
        drawnShapeData = null;
        previewShape = null;
        rightPanel = 'editor';
        if (mapComponent?.clearDrawnLayer) mapComponent.clearDrawnLayer();
        return;
      } else if (change.type === 'Update' && data?.Id) {
        // Seed as a pending edit for the existing location
        const loc = locations.find(l => l.Id === data.Id);
        if (loc) {
          const modified = {
            name: data.Name ?? loc.Name,
            locationType: isAreaType ? 'Area' : (props.Type || loc.Properties?.Type || 'Location'),
            longitude: props.Coordinates?.Longitude ?? loc.Properties?.Coordinates?.Longitude ?? 0,
            latitude: props.Coordinates?.Latitude ?? loc.Properties?.Coordinates?.Latitude ?? 0,
            altitude: props.Coordinates?.Altitude ?? loc.Properties?.Coordinates?.Altitude ?? null,
            areaType: isAreaType ? (props.AreaType || loc.Properties?.AreaType || 'MobArea') : null,
            shape: props.Shape ?? loc.Properties?.Shape ?? null,
            shapeData: props.Data ?? loc.Properties?.Data ?? null,
            parentLocationName: data.ParentLocation?.Name || loc.ParentLocation?.Name || null,
            description: props.Description ?? loc.Properties?.Description ?? null,
            landAreaOwner: data.Owner?.Name || props.LandAreaOwnerName || loc.Owner?.Name || loc.Properties?.LandAreaOwnerName || null,
            taxRateHunting: props.TaxRateHunting ?? loc.Properties?.TaxRateHunting ?? null,
            taxRateMining: props.TaxRateMining ?? loc.Properties?.TaxRateMining ?? null,
            taxRateShops: props.TaxRateShops ?? loc.Properties?.TaxRateShops ?? null,
          };
          pendingChanges.set(data.Id, { action: 'edit', original: loc, modified, _dbSeeded: true });
          dbChangeIdMap.set(data.Id, change.id);

          if (mapComponent?.rebuildDbOverlay) mapComponent.rebuildDbOverlay();
          if (mapComponent?.forceRebuild) mapComponent.forceRebuild();
          selectedId = data.Id;
          isNewLocation = false;
          drawnShapeData = null;
          rightPanel = 'editor';
          if (mapComponent?.clearDrawnLayer) mapComponent.clearDrawnLayer();
          showAfterimageForOriginal(data.Id);
          return;
        } else {
          // Location not found locally — fall back to read-only
          selectedDbChange = change;
          selectedId = `db-${change.id}`;
        }
      } else {
        // Delete or unrecognized — show read-only
        selectedDbChange = change;
        selectedId = `db-${change.id}`;
      }
    } else {
      // Other user's change — read-only
      selectedDbChange = change;
      selectedId = `db-${change.id}`;
    }

    // Read-only fallback cleanup
    isNewLocation = false;
    drawnShapeData = null;
    previewShape = null;
    rightPanel = 'editor';
    if (mapComponent?.clearDrawnLayer) mapComponent.clearDrawnLayer();
  }

  function handleListSelect(id) {
    selectedId = id;
    selectedDbChange = null;
    isNewLocation = false;
    drawnShapeData = null;
    previewShape = null;
    rightPanel = 'editor';
    if (mapComponent?.clearDrawnLayer) mapComponent.clearDrawnLayer();
    // Show afterimage if this location has a pending edit
    if (selectedId && pendingChanges.has(selectedId) && pendingChanges.get(selectedId).action === 'edit') {
      showAfterimageForOriginal(selectedId);
    }
    const loc = locations.find(l => l.Id === selectedId);
    if (loc && mapComponent) mapComponent.panToLocation(loc);
  }

  function handleFilterChange(ids) {
    filteredLocationIds = ids;
  }

  function handleDrawCreated(entropiaData) {

    // Immediately create a pending add so the shape persists on the map.
    // The user can edit details later or remove it via the Remove button.
    const tempId = nextTempId--;
    const isMarker = entropiaData.isMarker;
    const modified = {
      name: '',
      locationType: isMarker ? 'Teleporter' : 'Area',
      longitude: entropiaData.center?.x ?? 0,
      latitude: entropiaData.center?.y ?? 0,
      altitude: DEFAULT_ALTITUDE,
      areaType: isMarker ? null : 'MobArea',
      shape: entropiaData.shape || null,
      shapeData: entropiaData.data || null,
      tempId
    };

    pendingChanges.set(tempId, { action: 'edit', original: null, modified });


    // Select the new pending add for editing
    selectedId = tempId;
    isNewLocation = false;
    drawnShapeData = null;
    rightPanel = 'editor';
    previewShape = null;
  }

  function handleAddLocation(modified) {
    const tempId = nextTempId--;
    modified.tempId = tempId;
    pendingChanges.set(tempId, { action: 'edit', original: null, modified });

    isNewLocation = false;
    drawnShapeData = null;
  }

  function handleEditLocation({ original, modified }) {
    // Block editing if locked by another user (unless admin)
    if (!isAdmin && original?.Id && lockedLocationMap.has(original.Id)) return;
    // Admin editing a location with an existing pending change from another user:
    // seed the DB change ID so submission uses PUT (update) instead of POST (new).
    if (isAdmin && original?.Id && !dbChangeIdMap.has(original.Id) && lockedLocationMap.has(original.Id)) {
      const existingDbChange = lockedLocationMap.get(original.Id);
      dbChangeIdMap.set(original.Id, existingDbChange.id);
    }
    const existingChange = pendingChanges.get(original.Id);
    if (existingChange && !existingChange.original) {
      // Editing a pending add: merge into existing — new object so SvelteMap signals change
      const { _dbSeeded, ...rest } = existingChange;
      pendingChanges.set(original.Id, { ...rest, modified: { ...existingChange.modified, ...modified } });
    } else {
      // Preserve the true original from the first edit — `original` from the editor
      // is the merged selectedLocation, not the raw location from locations[].
      const trueOriginal = existingChange?.original || locations.find(l => l.Id === original.Id) || original;
      // Preserve density/maturities/waves set by the mob/wave editors (auto-save doesn't include them)
      if (existingChange?.modified?.density != null && modified.density == null) {
        modified.density = existingChange.modified.density;
      }
      if (existingChange?.modified?.maturities && !modified.maturities) {
        modified.maturities = existingChange.modified.maturities;
      }
      if (existingChange?.modified?.waves && !modified.waves) {
        modified.waves = existingChange.modified.waves;
      }
      pendingChanges.set(original.Id, { action: 'edit', original: trueOriginal, modified });
      // Show afterimage of original for committed edits
      showAfterimageForOriginal(original.Id);
    }
    // Track that this DB-seeded change was locally modified
    if (dbChangeIdMap.has(original.Id)) { modifiedDbChanges.add(original.Id); }

    // Force rebuild so the map reflects the saved state even when _editingActive blocks the reactive
    if (mapComponent?.forceRebuild) mapComponent.forceRebuild();
  }

  function handleDeleteLocation(loc) {
    pendingChanges.set(loc.Id, { action: 'delete', original: loc, modified: null });

  }

  function handleRevertLocation(loc) {
    if (loc?.Id) {
      pendingChanges.delete(loc.Id);
      modifiedDbChanges.delete(loc.Id);
    }

    previewShape = null; // Clear afterimage
    // Force rebuild: _editingActive may block the reactive rebuildLayers
    if (mapComponent?.forceRebuild) mapComponent.forceRebuild();
    // Rebuild DB overlay so un-seeded changes reappear
    if (mapComponent?.rebuildDbOverlay) mapComponent.rebuildDbOverlay();
  }

  function handleRemovePendingAdd(tempId) {
    if (tempId != null) {
      pendingChanges.delete(tempId);
      dbChangeIdMap.delete(tempId);
      modifiedDbChanges.delete(tempId);
  
      if (selectedId === tempId) {
        selectedId = null;
      }
      // Force rebuild: _editingActive may block the reactive rebuildLayers
      if (mapComponent?.forceRebuild) mapComponent.forceRebuild();
      // Rebuild DB overlay so un-seeded changes reappear
      if (mapComponent?.rebuildDbOverlay) mapComponent.rebuildDbOverlay();
    }
  }

  async function handleDeleteDbChange(tempId) {
    const dbId = dbChangeIdMap.get(tempId);
    if (!dbId) return;
    if (!confirm('Delete this submitted change? This cannot be undone.')) return;

    try {
      const { apiDelete } = await import('$lib/util.js');
      const res = await apiDelete(fetch, `/api/changes/${dbId}`);
      if (!res?.error) {
        pendingChanges.delete(tempId);
        dbChangeIdMap.delete(tempId);
        modifiedDbChanges.delete(tempId);
        // Remove from dbPendingChanges so the overlay doesn't re-render it
        const idx = dbPendingChanges.findIndex(c => c.id === dbId);
        if (idx !== -1) { dbPendingChanges.splice(idx, 1); dbPendingChanges = dbPendingChanges; }
    
        if (selectedId === tempId) {
          selectedId = null;
        }
        if (mapComponent?.forceRebuild) mapComponent.forceRebuild();
        if (mapComponent?.rebuildDbOverlay) mapComponent.rebuildDbOverlay();
        const { addToast } = await import('$lib/stores/toasts.js');
        addToast('Change deleted', { type: 'success' });
      }
    } catch (err) {
      const { addToast } = await import('$lib/stores/toasts.js');
      addToast(`Delete failed: ${err.message}`, { type: 'error' });
    }
  }

  function handleMassDelete(ids) {
    for (const id of ids) {
      const loc = locations.find(l => l.Id === id);
      if (loc) {
        pendingChanges.set(id, { action: 'delete', original: loc, modified: null });
      }
    }

  }

  /**
   * Check if preview data from the form actually differs from the original location data.
   * Used to distinguish real edits from initial form load (which replays current data).
   */
  function hasShapeChanged(loc, pd) {
    if (!pd) return false;
    if (isArea(loc)) {
      const origShape = loc.Properties?.Shape;
      const origData = loc.Properties?.Data;
      if (!origShape || !origData) return !!pd.shape;
      if (!pd.shape || !pd.data) return true;
      if (origShape !== pd.shape) return true;
      if (origShape === 'Circle') {
        return origData.x !== pd.data.x || origData.y !== pd.data.y || origData.radius !== pd.data.radius;
      } else if (origShape === 'Rectangle') {
        return origData.x !== pd.data.x || origData.y !== pd.data.y || origData.width !== pd.data.width || origData.height !== pd.data.height;
      } else if (origShape === 'Polygon') {
        const ov = origData.vertices || [], nv = pd.data?.vertices || [];
        if (ov.length !== nv.length) return true;
        return ov.some((v, i) => v !== nv[i]);
      }
      return true;
    } else {
      const coords = loc.Properties?.Coordinates;
      if (!coords) return !!pd.center;
      if (!pd.center) return true;
      return coords.Longitude !== pd.center.x || coords.Latitude !== pd.center.y;
    }
  }

  function handlePreview(pd) {
    if (isNewLocation) return;

    if (selectedId && pd) {
      // Always update the map shape to follow form data
      if (mapComponent?.updateLayerShape) {
        mapComponent.updateLayerShape(selectedId, pd);
      }
      // Show/hide afterimage based on whether form data actually differs from original
      const loc = locations.find(l => l.Id === selectedId);
      if (loc && hasShapeChanged(loc, pd)) {
        // Form data differs from original — show afterimage if not already visible
        if (!previewShape) {
          showAfterimageForOriginal(selectedId);
        }
      } else if (previewShape && !pendingChanges.has(selectedId)) {
        // Form data matches original AND no committed pending edit — clear afterimage
        previewShape = null;
      }
    } else if (selectedId && !pd) {
      if (!pendingChanges.has(selectedId)) {
        previewShape = null;
      }
    }
  }

  function handleShapeEdited({ locId, entropiaData }) {
    // Block shape editing if locked by another user (unless admin)
    if (!isAdmin && lockedLocationMap.has(locId)) return;
    // Admin editing a location with an existing pending change from another user:
    // seed the DB change ID so submission uses PUT (update) instead of POST (new).
    if (isAdmin && !dbChangeIdMap.has(locId) && lockedLocationMap.has(locId)) {
      const existingDbChange = lockedLocationMap.get(locId);
      dbChangeIdMap.set(locId, existingDbChange.id);
    }
    const loc = locations.find(l => l.Id === locId);
    const existing = pendingChanges.get(locId);

    if (!existing?.original && existing?.modified) {
      // Pending add: merge shape edits — new object so SvelteMap signals change
      const { _dbSeeded, ...rest } = existing;
      const updatedMod = {
        ...existing.modified,
        ...(entropiaData.center ? { longitude: entropiaData.center.x, latitude: entropiaData.center.y } : {}),
        ...(entropiaData.shape ? { shape: entropiaData.shape, shapeData: entropiaData.data } : {})
      };
      if (dbChangeIdMap.has(locId)) { modifiedDbChanges.add(locId); }
      pendingChanges.set(locId, { ...rest, modified: updatedMod });
  
    } else if (loc) {
      // Existing location: create/update edit change
      const modified = existing?.modified || {};
      modified.name = modified.name ?? loc.Name;
      modified.locationType = modified.locationType ?? (isArea(loc) ? 'Area' : (loc.Properties?.Type || 'Area'));
      if (modified.locationType === 'Area' && modified.areaType === undefined) {
        modified.areaType = loc.Properties?.AreaType || 'MobArea';
      }

      if (entropiaData.center) {
        modified.longitude = entropiaData.center.x;
        modified.latitude = entropiaData.center.y;
      }
      if (entropiaData.shape) {
        modified.shape = entropiaData.shape;
        modified.shapeData = entropiaData.data;
      }
      // Preserve altitude from original when not already in modified (drag doesn't change altitude)
      if (modified.altitude === undefined) {
        modified.altitude = loc.Properties?.Coordinates?.Altitude ?? DEFAULT_ALTITUDE;
      }

      if (dbChangeIdMap.has(locId)) { modifiedDbChanges.add(locId); }
      pendingChanges.set(locId, { action: 'edit', original: loc, modified });
  

      // Show afterimage of original position
      showAfterimageForOriginal(locId);
    }
  }

  function handleEditMobArea(ctx) {
    mobEditorContext = ctx;
    rightPanel = 'mobEditor';
  }

  function handleEditWaveArea(ctx) {
    waveEditorContext = ctx;
    rightPanel = 'waveEditor';
  }

  function handleWaveSave(waveData) {
    if (waveEditorContext?.location) {
      const loc = waveEditorContext.location;
      const existing = pendingChanges.get(loc.Id);
      if (existing && !existing.original) {
        // New object so SvelteMap signals the change
        pendingChanges.set(loc.Id, {
          ...existing,
          modified: { ...existing.modified, waves: waveData.waves }
        });
      } else {
        const modified = existing?.modified || {};
        modified.waves = waveData.waves;
        pendingChanges.set(loc.Id, { action: 'edit', original: loc, modified });
      }
    }

    rightPanel = 'editor';
    waveEditorContext = null;
  }

  function handleWaveCancel() {
    rightPanel = 'editor';
    waveEditorContext = null;
  }

  function handleMobSave(mobData) {
    if (mobEditorContext?.location) {
      const loc = mobEditorContext.location;
      const existing = pendingChanges.get(loc.Id);
      if (existing && !existing.original) {
        // Pending add: merge mob data — new object so SvelteMap signals the change
        pendingChanges.set(loc.Id, {
          ...existing,
          modified: { ...existing.modified, name: mobData.name, density: mobData.density, maturities: mobData.maturities }
        });
      } else {
        const modified = existing?.modified || {};
        modified.name = mobData.name;
        modified.density = mobData.density;
        modified.maturities = mobData.maturities;
        pendingChanges.set(loc.Id, { action: 'edit', original: loc, modified });
      }
    }

    rightPanel = 'editor';
    mobEditorContext = null;
  }

  function handleMobCancel() {
    rightPanel = 'editor';
    mobEditorContext = null;
  }

  function handleClone(loc) {
    if (!loc) return;

    const OFFSET = 50;
    const tempId = nextTempId--;
    const modified = {
      name: `${loc.Name || 'Location'} (copy)`,
      locationType: loc.Properties?.Type === 'Area' || isArea(loc) ? 'Area' : (loc.Properties?.Type || 'Area'),
      longitude: (loc.Properties?.Coordinates?.Longitude ?? 0) + OFFSET,
      latitude: (loc.Properties?.Coordinates?.Latitude ?? 0) + OFFSET,
      altitude: loc.Properties?.Coordinates?.Altitude ?? null,
      areaType: loc.Properties?.AreaType || null,
      shape: loc.Properties?.Shape || null,
      shapeData: loc.Properties?.Data ? offsetShapeData(JSON.parse(JSON.stringify(loc.Properties.Data)), loc.Properties.Shape, OFFSET) : null,
      tempId
    };

    pendingChanges.set(tempId, { action: 'edit', original: null, modified });

    isNewLocation = false;
    drawnShapeData = null;
  }

  function offsetShapeData(data, shape, offset) {
    if (!data) return data;
    if (shape === 'Circle' || shape === 'Rectangle') {
      data.x = (data.x || 0) + offset;
      data.y = (data.y || 0) + offset;
    } else if (shape === 'Polygon' && data.vertices) {
      data.vertices = data.vertices.map((v, i) => v + offset);
    }
    return data;
  }
  // --- Locked locations (active changes from other users) ---
  let lockedLocationMap = $derived((() => {
    const map = new Map();
    for (const c of dbPendingChanges) {
      if (c.author_id === currentUserId) continue;
      const entityId = c.data?.Id;
      if (entityId && c.type === 'Update') {
        map.set(entityId, c);
      }
    }
    return map;
  })());
  $effect(() => {
    if (focusKey && focusLocation && mapComponent && focusKey !== lastAppliedFocusKey) {
      if (focusLocation._dbChange) {
        // Route to handleSelectDbChange so admins/owners get an editable pending change
        // instead of being forced into read-only mode
        handleSelectDbChange({ detail: focusLocation._dbChange });
      } else if (focusLocation.Id != null) {
        const matched = locations.find(l => l.Id == focusLocation.Id);
        selectedId = matched ? matched.Id : focusLocation.Id;
        selectedDbChange = null;
      }
      mapComponent.panToLocation(focusLocation);
      lastAppliedFocusKey = focusKey;
    }
  });
  // --- Reactive derivations ---
  // Memoize selectedLocation to avoid emitting new object references when data hasn't changed.
  // Without this, every pendingChanges mutation re-derives a new spread object, triggering
  // downstream effects in LocationEditor even though the visible data is identical.
  let _prevSelectedJson = null;
  let _prevSelectedResult = null;
  let selectedLocation = $derived((() => {
    let result = null;
    if (!selectedId) {
      _prevSelectedJson = null;
      _prevSelectedResult = null;
      return null;
    }
    const loc = locations.find(l => l.Id === selectedId);
    if (loc) {
      // Merge pending edit data so the editor form reflects map edits
      const pending = pendingChanges.get(loc.Id);
      if (pending?.action === 'edit' && pending.modified) {
        const mod = pending.modified;
        result = {
          ...loc,
          Name: mod.name ?? loc.Name,
          _hasPendingEdit: true,
          ...(mod.waves ? { Waves: mod.waves } : loc.Waves ? { Waves: loc.Waves } : {}),
          ...(mod.parentLocationName !== undefined ? { ParentLocation: mod.parentLocationName ? { Name: mod.parentLocationName } : null } : {}),
          Owner: mod.landAreaOwner !== undefined ? (mod.landAreaOwner ? { Name: mod.landAreaOwner } : null) : (loc.Owner || null),
          Properties: {
            ...loc.Properties,
            Type: mod.locationType ? (mod.locationType === 'Area' ? 'Area' : mod.locationType) : loc.Properties?.Type,
            AreaType: mod.areaType !== undefined ? mod.areaType : loc.Properties?.AreaType,
            Shape: mod.shape ?? loc.Properties?.Shape,
            Data: mod.shapeData !== undefined ? mod.shapeData : loc.Properties?.Data,
            Description: mod.description !== undefined ? mod.description : loc.Properties?.Description,
            TaxRateHunting: mod.taxRateHunting !== undefined ? mod.taxRateHunting : loc.Properties?.TaxRateHunting,
            TaxRateMining: mod.taxRateMining !== undefined ? mod.taxRateMining : loc.Properties?.TaxRateMining,
            TaxRateShops: mod.taxRateShops !== undefined ? mod.taxRateShops : loc.Properties?.TaxRateShops,
            Coordinates: {
              ...loc.Properties?.Coordinates,
              ...(mod.longitude !== undefined ? { Longitude: mod.longitude } : {}),
              ...(mod.latitude !== undefined ? { Latitude: mod.latitude } : {}),
              ...(mod.altitude !== undefined ? { Altitude: mod.altitude } : {})
            }
          }
        };
      } else {
        result = loc;
      }
    } else {
      const pending = pendingChanges.get(selectedId);
      if (!pending?.original && pending?.modified) {
        const mod = pending.modified;
        result = {
          Id: selectedId,
          Name: mod.name || '',
          _isPendingAdd: true,
          ...(mod.waves ? { Waves: mod.waves } : {}),
          Owner: mod.landAreaOwner ? { Name: mod.landAreaOwner } : null,
          Properties: {
            Type: mod.locationType === 'Area' ? 'Area' : (mod.locationType || 'Area'),
            AreaType: mod.areaType || null,
            Coordinates: { Longitude: mod.longitude, Latitude: mod.latitude, Altitude: mod.altitude },
            Shape: mod.shape || null,
            Data: mod.shapeData || null,
            Description: mod.description || null,
            TaxRateHunting: mod.taxRateHunting ?? null,
            TaxRateMining: mod.taxRateMining ?? null,
            TaxRateShops: mod.taxRateShops ?? null,
          }
        };
      } else if (selectedDbChange) {
        // DB pending change (read-only viewing)
        const d = selectedDbChange.data;
        const props = d?.Properties || {};
        result = {
          Id: selectedId,
          Name: d?.Name || '',
          _isDbChange: true,
          Owner: d?.Owner || (props.LandAreaOwnerName ? { Name: props.LandAreaOwnerName } : null),
          Properties: {
            Type: props.Type || 'Location',
            AreaType: props.AreaType || null,
            Coordinates: props.Coordinates || {},
            Shape: props.Shape || null,
            Data: props.Data || null,
            Description: props.Description || null,
          }
        };
      }
    }
    // Memoize: return the same reference if the data hasn't changed
    const json = JSON.stringify(result);
    if (json === _prevSelectedJson) return _prevSelectedResult;
    _prevSelectedJson = json;
    _prevSelectedResult = result;
    return result;
  })());
  // Read-only when: viewing another user's DB pending change, or a non-admin
  // user selects a location locked by another user's pending change.
  let isReadOnly = $derived(!!selectedDbChange || (!isAdmin && selectedId != null
    && selectedId > 0 && lockedLocationMap.has(selectedId)));
  // Change count is computed in the parent page directly from its own $state Map
  // to avoid derived→effect→bindable propagation issues with Map mutations.
</script>

<style>
  .workspace {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .left-sidebar {
    width: 280px;
    flex-shrink: 0;
    border-right: 1px solid var(--border-color);
    background: var(--secondary-color);
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .map-area {
    flex: 1;
    min-width: 0;
    position: relative;
  }

  .right-panel {
    width: 320px;
    flex-shrink: 0;
    border-left: 1px solid var(--border-color);
    background: var(--secondary-color);
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .loading-overlay {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.5);
    color: white;
    font-size: 16px;
    z-index: 100;
  }

  .no-planet {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    font-size: 16px;
  }
</style>

<div class="workspace">
  <div class="left-sidebar">
    {#if planet}
      <LocationList
        {locations}
        {selectedId}
        {pendingChanges}
        {editMode}
        {mode}
        onselect={handleListSelect}
        onfilterChange={handleFilterChange}
        onmassDelete={handleMassDelete}
      />
    {/if}
  </div>

  <div class="map-area">
    {#if planet}
      <MapEditorLeaflet
        bind:this={mapComponent}
        {planet}
        {locations}
        {filteredLocationIds}
        {selectedId}
        {pendingChanges}
        {editMode}
        {previewShape}
        {dbPendingChanges}
        {currentUserId}
        {isAdmin}
        {lockedLocationMap}
        onselect={handleMapSelect}
        onselectDbChange={handleSelectDbChange}
        ondrawCreated={handleDrawCreated}
        onshapeEdited={handleShapeEdited}
        onclone={handleClone}
      />
      {#if loading}
        <div class="loading-overlay">Loading map data...</div>
      {/if}
    {:else}
      <div class="no-planet">Select a planet to load the map.</div>
    {/if}
  </div>

  <div class="right-panel">
    {#if rightPanel === 'mobEditor'}
      <MobAreaEditor
        mobs={allMobs}
        location={mobEditorContext?.location}
        isNew={mobEditorContext?.isNew || false}
        pendingMobData={mobEditorContext?.location ? getPendingMobData(mobEditorContext.location.Id) : null}
        onsave={handleMobSave}
        oncancel={handleMobCancel}
      />
    {:else if rightPanel === 'waveEditor'}
      <WaveEventEditor
        mobs={allMobs}
        location={waveEditorContext?.location}
        isNew={waveEditorContext?.isNew || false}
        pendingWaveData={waveEditorContext?.location ? getPendingWaveData(waveEditorContext.location.Id) : null}
        onsave={handleWaveSave}
        oncancel={handleWaveCancel}
      />
    {:else if rightPanel === 'editor'}
      <LocationEditor
        location={selectedLocation}
        isNew={isNewLocation}
        readOnly={isReadOnly}
        {drawnShapeData}
        {mode}
        {isAdmin}
        lockedBy={selectedLocation?.Id ? lockedLocationMap.get(selectedLocation.Id) : null}
        allLocations={locations}
        isDbChange={selectedId != null && dbChangeIdMap.has(selectedId)}
        pendingMobData={getPendingMobData(selectedLocation?.Id ?? selectedId)}
        pendingWaveData={getPendingWaveData(selectedLocation?.Id ?? selectedId)}
        onedit={handleEditLocation}
        ondelete={handleDeleteLocation}
        onrevert={handleRevertLocation}
        onremovePendingAdd={handleRemovePendingAdd}
        ondeleteDbChange={handleDeleteDbChange}
        oneditMobArea={handleEditMobArea}
        oneditWaveArea={handleEditWaveArea}
        onpreview={handlePreview}
      />
    {:else}
      {@render output?.()}
    {/if}
  </div>
</div>
