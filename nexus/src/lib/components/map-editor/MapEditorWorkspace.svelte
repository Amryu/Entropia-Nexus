<script>
  // @ts-nocheck
  import MapEditorLeaflet from './MapEditorLeaflet.svelte';
  import LocationList from './LocationList.svelte';
  import LocationEditor from './LocationEditor.svelte';
  import MobAreaEditor from './MobAreaEditor.svelte';
  import WaveEventEditor from './WaveEventEditor.svelte';
  import { isArea } from './mapEditorUtils.js';

  // --- Required props ---
  export let planet = null;
  export let locations = [];
  export let allMobs = [];
  export let editMode = false;
  export let loading = false;
  /** @type {'admin' | 'public'} */
  export let mode = 'admin';
  /** Location-like object to focus when opening editor from route mode links */
  export let focusLocation = null;
  /** Stable key so focus is only applied once per navigation */
  export let focusKey = null;

  // --- DB pending changes (from all users) ---
  /** @type {Array} All pending changes for this planet from the database */
  export let dbPendingChanges = [];
  export let currentUserId = null;
  export let isAdmin = false;

  // --- Bindable state (parent reads/controls) ---
  export let pendingChanges = new Map();
  export let rightPanel = 'editor'; // 'editor' | 'mobEditor' | <any other value shows output slot>
  export let mapComponent = undefined;
  export let changeCount = 0;
  export let dbChangeIdMap = new Map();

  // --- Locked locations (active changes from other users) ---
  $: lockedLocationMap = (() => {
    const map = new Map();
    for (const c of dbPendingChanges) {
      if (c.author_id === currentUserId) continue;
      const entityId = c.data?.Id;
      if (entityId && c.type === 'Update') {
        map.set(entityId, c);
      }
    }
    return map;
  })();

  // --- Internal state ---
  let selectedId = null;
  let isNewLocation = false;
  let drawnShapeData = null;
  let previewShape = null;
  let mobEditorContext = null;
  let filteredLocationIds = null;
  let nextTempId = -1;
  let lastAppliedFocusKey = null;
  let waveEditorContext = null;
  let selectedDbChange = null; // DB pending change selected for read-only viewing
  let modifiedDbChanges = new Set(); // DB-seeded changes that have been locally modified

  // --- Exported method ---
  export function reset() {
    pendingChanges = new Map();
    dbChangeIdMap = new Map();
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

  // --- Reactive derivations ---
  $: selectedLocation = (() => {
    if (!selectedId) return null;
    const loc = locations.find(l => l.Id === selectedId);
    if (loc) {
      // Merge pending edit data so the editor form reflects map edits
      const pending = pendingChanges.get(loc.Id);
      if (pending?.action === 'edit' && pending.modified) {
        const mod = pending.modified;
        return {
          ...loc,
          Name: mod.name ?? loc.Name,
          _hasPendingEdit: true,
          ...(mod.waveData ? { Waves: mod.waveData.waves } : loc.Waves ? { Waves: loc.Waves } : {}),
          ...(mod.parentLocationName !== undefined ? { ParentLocation: mod.parentLocationName ? { Name: mod.parentLocationName } : null } : {}),
          Properties: {
            ...loc.Properties,
            Type: mod.locationType ? (mod.locationType === 'Area' ? 'Area' : mod.locationType) : loc.Properties?.Type,
            AreaType: mod.areaType !== undefined ? mod.areaType : loc.Properties?.AreaType,
            Shape: mod.shape ?? loc.Properties?.Shape,
            Data: mod.shapeData !== undefined ? mod.shapeData : loc.Properties?.Data,
            Description: mod.description !== undefined ? mod.description : loc.Properties?.Description,
            Coordinates: {
              ...loc.Properties?.Coordinates,
              ...(mod.longitude !== undefined ? { Longitude: mod.longitude } : {}),
              ...(mod.latitude !== undefined ? { Latitude: mod.latitude } : {}),
              ...(mod.altitude !== undefined ? { Altitude: mod.altitude } : {})
            }
          }
        };
      }
      return loc;
    }
    const pending = pendingChanges.get(selectedId);
    if (!pending?.original && pending?.modified) {
      const mod = pending.modified;
      return {
        Id: selectedId,
        Name: mod.name || '',
        _isPendingAdd: true,
        ...(mod.waveData ? { Waves: mod.waveData.waves } : {}),
        Properties: {
          Type: mod.locationType === 'Area' ? (mod.areaType || 'MobArea') : (mod.locationType || 'Area'),
          AreaType: mod.areaType || null,
          Coordinates: { Longitude: mod.longitude, Latitude: mod.latitude, Altitude: mod.altitude },
          Shape: mod.shape || null,
          Data: mod.shapeData || null,
          Description: mod.description || null,
        }
      };
    }
    // DB pending change (read-only viewing)
    if (selectedDbChange) {
      const d = selectedDbChange.data;
      const props = d?.Properties || {};
      return {
        Id: selectedId,
        Name: d?.Name || '',
        _isDbChange: true,
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
    return null;
  })();

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

  // Read-only when: viewing another user's DB pending change, or a non-admin
  // user selects a location locked by another user's pending change.
  $: isReadOnly = !!selectedDbChange || (!isAdmin && selectedId != null
    && selectedId > 0 && lockedLocationMap.has(selectedId));

  // Count pending changes excluding DB-seeded but unmodified entries
  $: changeCount = Array.from(pendingChanges.values()).filter(c => !c._dbSeeded).length;

  $: if (focusKey && focusLocation && mapComponent && focusKey !== lastAppliedFocusKey) {
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

  // --- Event handlers ---
  function handleMapSelect(e) {
    selectedId = e.detail;
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

  function handleSelectDbChange(e) {
    const change = e.detail;
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
            tempId
          };
          // Restore mob data if persisted in the change
          if (props.MobData || props.Density != null) {
            modified.mobData = { density: props.Density ?? 4, maturities: props.MobData || [] };
          }
          // Restore wave data if persisted in the change
          if (data?.Waves) {
            modified.waveData = { waves: data.Waves };
          }
          pendingChanges.set(tempId, { action: 'edit', original: null, modified, _dbSeeded: true });
          dbChangeIdMap.set(tempId, change.id);
          pendingChanges = pendingChanges;
          if (mapComponent?.rebuildDbOverlay) mapComponent.rebuildDbOverlay();
        }
        selectedId = tempId;
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
          };
          pendingChanges.set(data.Id, { action: 'edit', original: loc, modified, _dbSeeded: true });
          dbChangeIdMap.set(data.Id, change.id);
          pendingChanges = pendingChanges;
          if (mapComponent?.rebuildDbOverlay) mapComponent.rebuildDbOverlay();
          selectedId = data.Id;
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

    isNewLocation = false;
    drawnShapeData = null;
    previewShape = null;
    rightPanel = 'editor';
    if (mapComponent?.clearDrawnLayer) mapComponent.clearDrawnLayer();
  }

  function handleListSelect(e) {
    selectedId = e.detail;
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

  function handleFilterChange(e) {
    filteredLocationIds = e.detail;
  }

  function handleDrawCreated(e) {
    const entropiaData = e.detail;

    // Immediately create a pending add so the shape persists on the map.
    // The user can edit details later or remove it via the Remove button.
    const tempId = nextTempId--;
    const isMarker = entropiaData.isMarker;
    const modified = {
      name: '',
      locationType: isMarker ? 'Teleporter' : 'Area',
      longitude: entropiaData.center?.x ?? 0,
      latitude: entropiaData.center?.y ?? 0,
      altitude: 0,
      areaType: isMarker ? null : 'MobArea',
      shape: entropiaData.shape || null,
      shapeData: entropiaData.data || null,
      tempId
    };

    pendingChanges.set(tempId, { action: 'edit', original: null, modified });
    pendingChanges = pendingChanges;

    // Select the new pending add for editing
    selectedId = tempId;
    isNewLocation = false;
    drawnShapeData = null;
    rightPanel = 'editor';
    previewShape = null;
  }

  function handleAddLocation(e) {
    const modified = e.detail;
    const tempId = nextTempId--;
    modified.tempId = tempId;
    pendingChanges.set(tempId, { action: 'edit', original: null, modified });
    pendingChanges = pendingChanges;
    isNewLocation = false;
    drawnShapeData = null;
  }

  function handleEditLocation(e) {
    const { original, modified } = e.detail;
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
      // Editing a pending add: merge into the existing entry
      Object.assign(existingChange.modified, modified);
      delete existingChange._dbSeeded;
      pendingChanges.set(original.Id, existingChange);
    } else {
      // Preserve the true original from the first edit — `original` from the editor
      // is the merged selectedLocation, not the raw location from locations[].
      const trueOriginal = existingChange?.original || locations.find(l => l.Id === original.Id) || original;
      pendingChanges.set(original.Id, { action: 'edit', original: trueOriginal, modified });
      // Show afterimage of original for committed edits
      showAfterimageForOriginal(original.Id);
    }
    // Track that this DB-seeded change was locally modified
    if (dbChangeIdMap.has(original.Id)) { modifiedDbChanges.add(original.Id); modifiedDbChanges = modifiedDbChanges; }
    pendingChanges = pendingChanges;
    // Force rebuild so the map reflects the saved state even when _editingActive blocks the reactive
    if (mapComponent?.forceRebuild) mapComponent.forceRebuild();
  }

  function handleDeleteLocation(e) {
    const loc = e.detail;
    pendingChanges.set(loc.Id, { action: 'delete', original: loc, modified: null });
    pendingChanges = pendingChanges;
  }

  function handleRevertLocation(e) {
    const loc = e.detail;
    if (loc?.Id) {
      pendingChanges.delete(loc.Id);
      if (modifiedDbChanges.delete(loc.Id)) modifiedDbChanges = modifiedDbChanges;
    }
    pendingChanges = pendingChanges;
    previewShape = null; // Clear afterimage
    // Force rebuild: _editingActive may block the reactive rebuildLayers
    if (mapComponent?.forceRebuild) mapComponent.forceRebuild();
    // Rebuild DB overlay so un-seeded changes reappear
    if (mapComponent?.rebuildDbOverlay) mapComponent.rebuildDbOverlay();
  }

  function handleRemovePendingAdd(e) {
    const tempId = e.detail;
    if (tempId != null) {
      pendingChanges.delete(tempId);
      dbChangeIdMap.delete(tempId);
      modifiedDbChanges.delete(tempId);
      pendingChanges = pendingChanges;
      if (selectedId === tempId) {
        selectedId = null;
      }
      // Force rebuild: _editingActive may block the reactive rebuildLayers
      if (mapComponent?.forceRebuild) mapComponent.forceRebuild();
      // Rebuild DB overlay so un-seeded changes reappear
      if (mapComponent?.rebuildDbOverlay) mapComponent.rebuildDbOverlay();
    }
  }

  async function handleDeleteDbChange(e) {
    const tempId = e.detail;
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
        pendingChanges = pendingChanges;
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

  function handleMassDelete(e) {
    const ids = e.detail;
    for (const id of ids) {
      const loc = locations.find(l => l.Id === id);
      if (loc) {
        pendingChanges.set(id, { action: 'delete', original: loc, modified: null });
      }
    }
    pendingChanges = pendingChanges;
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

  function handlePreview(e) {
    const pd = e.detail;
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

  function handleShapeEdited(e) {
    const { locId, entropiaData } = e.detail;
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
      // Pending add: update the modified data in place
      const modified = existing.modified;
      if (entropiaData.center) {
        modified.longitude = entropiaData.center.x;
        modified.latitude = entropiaData.center.y;
      }
      if (entropiaData.shape) {
        modified.shape = entropiaData.shape;
        modified.shapeData = entropiaData.data;
      }
      delete existing._dbSeeded;
      if (dbChangeIdMap.has(locId)) { modifiedDbChanges.add(locId); modifiedDbChanges = modifiedDbChanges; }
      pendingChanges.set(locId, existing);
      pendingChanges = pendingChanges;
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
        modified.altitude = loc.Properties?.Coordinates?.Altitude ?? 100;
      }

      if (dbChangeIdMap.has(locId)) { modifiedDbChanges.add(locId); modifiedDbChanges = modifiedDbChanges; }
      pendingChanges.set(locId, { action: 'edit', original: loc, modified });
      pendingChanges = pendingChanges;

      // Show afterimage of original position
      showAfterimageForOriginal(locId);
    }
  }

  function handleEditMobArea(e) {
    mobEditorContext = e.detail;
    rightPanel = 'mobEditor';
  }

  function handleEditWaveArea(e) {
    waveEditorContext = e.detail;
    rightPanel = 'waveEditor';
  }

  function handleWaveSave(e) {
    const waveData = e.detail;
    if (waveEditorContext?.location) {
      const loc = waveEditorContext.location;
      const existing = pendingChanges.get(loc.Id);
      if (!existing?.original) {
        existing.modified.waveData = { waves: waveData.waves };
        pendingChanges.set(loc.Id, existing);
      } else {
        const modified = existing?.modified || {};
        modified.waveData = { waves: waveData.waves };
        pendingChanges.set(loc.Id, { action: 'edit', original: loc, modified });
      }
    }
    pendingChanges = pendingChanges;
    rightPanel = 'editor';
    waveEditorContext = null;
  }

  function handleWaveCancel() {
    rightPanel = 'editor';
    waveEditorContext = null;
  }

  function handleMobSave(e) {
    const mobData = e.detail;
    if (mobEditorContext?.location) {
      const loc = mobEditorContext.location;
      const existing = pendingChanges.get(loc.Id);
      if (existing && !existing.original) {
        // Pending add: merge mob data into existing entry
        existing.modified.name = mobData.name;
        existing.modified.mobData = { density: mobData.density, maturities: mobData.maturities };
        pendingChanges.set(loc.Id, existing);
      } else {
        const modified = existing?.modified || {};
        modified.name = mobData.name;
        modified.mobData = { density: mobData.density, maturities: mobData.maturities };
        pendingChanges.set(loc.Id, { action: 'edit', original: loc, modified });
      }
    }
    pendingChanges = pendingChanges;
    rightPanel = 'editor';
    mobEditorContext = null;
  }

  function handleMobCancel() {
    rightPanel = 'editor';
    mobEditorContext = null;
  }

  function handleClone(e) {
    const loc = e.detail;
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
    pendingChanges = pendingChanges;
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
        on:select={handleListSelect}
        on:filterChange={handleFilterChange}
        on:massDelete={handleMassDelete}
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
        on:select={handleMapSelect}
        on:selectDbChange={handleSelectDbChange}
        on:drawCreated={handleDrawCreated}
        on:shapeEdited={handleShapeEdited}
        on:clone={handleClone}
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
        pendingMobData={mobEditorContext?.location ? pendingChanges.get(mobEditorContext.location.Id)?.modified?.mobData : null}
        on:save={handleMobSave}
        on:cancel={handleMobCancel}
      />
    {:else if rightPanel === 'waveEditor'}
      <WaveEventEditor
        mobs={allMobs}
        location={waveEditorContext?.location}
        isNew={waveEditorContext?.isNew || false}
        pendingWaveData={waveEditorContext?.location ? pendingChanges.get(waveEditorContext.location.Id)?.modified?.waveData : null}
        on:save={handleWaveSave}
        on:cancel={handleWaveCancel}
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
        on:add={handleAddLocation}
        on:edit={handleEditLocation}
        on:delete={handleDeleteLocation}
        on:revert={handleRevertLocation}
        on:removePendingAdd={handleRemovePendingAdd}
        on:deleteDbChange={handleDeleteDbChange}
        on:editMobArea={handleEditMobArea}
        on:editWaveArea={handleEditWaveArea}
        on:preview={handlePreview}
      />
    {:else}
      <slot name="output" />
    {/if}
  </div>
</div>
