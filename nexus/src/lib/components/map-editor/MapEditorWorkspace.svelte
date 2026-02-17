<script>
  // @ts-nocheck
  import MapEditorLeaflet from './MapEditorLeaflet.svelte';
  import LocationList from './LocationList.svelte';
  import LocationEditor from './LocationEditor.svelte';
  import MobAreaEditor from './MobAreaEditor.svelte';
  import { isArea } from './mapEditorUtils.js';

  // --- Required props ---
  export let planet = null;
  export let locations = [];
  export let allMobs = [];
  export let editMode = false;
  export let loading = false;
  /** @type {'admin' | 'public'} */
  export let mode = 'admin';

  // --- Bindable state (parent reads/controls) ---
  export let pendingChanges = new Map();
  export let rightPanel = 'editor'; // 'editor' | 'mobEditor' | <any other value shows output slot>
  export let mapComponent = undefined;
  export let changeCount = 0;

  // --- Internal state ---
  let selectedId = null;
  let isNewLocation = false;
  let drawnShapeData = null;
  let previewShape = null;
  let mobEditorContext = null;
  let filteredLocationIds = null;
  let nextTempId = -1;

  // --- Exported method ---
  export function reset() {
    pendingChanges = new Map();
    selectedId = null;
    isNewLocation = false;
    drawnShapeData = null;
    rightPanel = 'editor';
    previewShape = null;
    mobEditorContext = null;
    filteredLocationIds = null;
    nextTempId = -1;
    changeCount = 0;
  }

  // --- Reactive derivations ---
  $: selectedLocation = (() => {
    if (!selectedId) return null;
    const loc = locations.find(l => l.Id === selectedId);
    if (loc) return loc;
    const pending = pendingChanges.get(selectedId);
    if (pending?.action === 'add' && pending.modified) {
      const mod = pending.modified;
      return {
        Id: selectedId,
        Name: mod.name || '',
        _isPendingAdd: true,
        Properties: {
          Type: mod.locationType === 'Area' ? (mod.areaType || 'MobArea') : (mod.locationType || 'Area'),
          AreaType: mod.areaType || null,
          Coordinates: { Longitude: mod.longitude, Latitude: mod.latitude, Altitude: mod.altitude },
          Shape: mod.shape || null,
          Data: mod.shapeData || null,
        }
      };
    }
    return null;
  })();

  $: changeCount = pendingChanges.size;

  // --- Event handlers ---
  function handleMapSelect(e) {
    selectedId = e.detail;
    isNewLocation = false;
    drawnShapeData = null;
    previewShape = null;
    rightPanel = 'editor';
  }

  function handleListSelect(e) {
    selectedId = e.detail;
    isNewLocation = false;
    drawnShapeData = null;
    previewShape = null;
    rightPanel = 'editor';
    const loc = locations.find(l => l.Id === selectedId);
    if (loc && mapComponent) mapComponent.panToLocation(loc);
  }

  function handleFilterChange(e) {
    filteredLocationIds = e.detail;
  }

  function handleDrawCreated(e) {
    drawnShapeData = e.detail;
    isNewLocation = true;
    selectedId = null;
    rightPanel = 'editor';
  }

  function handleAddLocation(e) {
    const modified = e.detail;
    const tempId = nextTempId--;
    modified.tempId = tempId;
    pendingChanges.set(tempId, { action: 'add', original: null, modified });
    pendingChanges = pendingChanges;
    isNewLocation = false;
    drawnShapeData = null;
  }

  function handleEditLocation(e) {
    const { original, modified } = e.detail;
    pendingChanges.set(original.Id, { action: 'edit', original, modified });
    pendingChanges = pendingChanges;
  }

  function handleDeleteLocation(e) {
    const loc = e.detail;
    pendingChanges.set(loc.Id, { action: 'delete', original: loc, modified: null });
    pendingChanges = pendingChanges;
  }

  function handleRevertLocation(e) {
    const loc = e.detail;
    if (loc?.Id) pendingChanges.delete(loc.Id);
    pendingChanges = pendingChanges;
  }

  function handleRemovePendingAdd(e) {
    const tempId = e.detail;
    if (tempId != null) {
      pendingChanges.delete(tempId);
      pendingChanges = pendingChanges;
      if (selectedId === tempId) {
        selectedId = null;
      }
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

  function handlePreview(e) {
    previewShape = e.detail;
  }

  function handleShapeEdited(e) {
    const { locId, entropiaData } = e.detail;
    const loc = locations.find(l => l.Id === locId);
    if (!loc) return;

    const existing = pendingChanges.get(locId);
    const modified = existing?.modified || {};
    modified.name = modified.name ?? loc.Name;
    modified.locationType = modified.locationType ?? (isArea(loc) ? 'Area' : (loc.Properties?.Type || 'Area'));

    if (entropiaData.center) {
      modified.longitude = entropiaData.center.x;
      modified.latitude = entropiaData.center.y;
    }
    if (entropiaData.shape) {
      modified.shape = entropiaData.shape;
      modified.shapeData = entropiaData.data;
    }

    pendingChanges.set(locId, { action: 'edit', original: loc, modified });
    pendingChanges = pendingChanges;
  }

  function handleEditMobArea(e) {
    mobEditorContext = e.detail;
    rightPanel = 'mobEditor';
  }

  function handleMobSave(e) {
    const mobData = e.detail;
    if (mobEditorContext?.location) {
      const loc = mobEditorContext.location;
      const existing = pendingChanges.get(loc.Id);
      const modified = existing?.modified || {};
      modified.name = mobData.name;
      modified.mobData = { density: mobData.density, maturities: mobData.maturities };
      pendingChanges.set(loc.Id, { action: 'edit', original: loc, modified });
    } else if (mobEditorContext?.isNew && drawnShapeData) {
      drawnShapeData.mobData = { density: mobData.density, maturities: mobData.maturities };
      drawnShapeData.suggestedName = mobData.name;
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

    pendingChanges.set(tempId, { action: 'add', original: null, modified });
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
        on:select={handleMapSelect}
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
        on:save={handleMobSave}
        on:cancel={handleMobCancel}
      />
    {:else if rightPanel === 'editor'}
      <LocationEditor
        location={selectedLocation}
        isNew={isNewLocation}
        {drawnShapeData}
        {mode}
        allLocations={locations}
        on:add={handleAddLocation}
        on:edit={handleEditLocation}
        on:delete={handleDeleteLocation}
        on:revert={handleRevertLocation}
        on:removePendingAdd={handleRemovePendingAdd}
        on:editMobArea={handleEditMobArea}
        on:preview={handlePreview}
      />
    {:else}
      <slot name="output" />
    {/if}
  </div>
</div>
