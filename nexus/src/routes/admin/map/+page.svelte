<script>
  // @ts-nocheck
  import { browser } from '$app/environment';
  import { apiCall } from '$lib/util.js';
  import AdminMapLeaflet from '$lib/components/admin/AdminMapLeaflet.svelte';
  import AdminLocationList from '$lib/components/admin/AdminLocationList.svelte';
  import AdminLocationEditor from '$lib/components/admin/AdminLocationEditor.svelte';
  import AdminMobAreaEditor from '$lib/components/admin/AdminMobAreaEditor.svelte';
  import AdminSqlOutput from '$lib/components/admin/AdminSqlOutput.svelte';
  import { isArea } from '$lib/components/admin/adminMapUtils.js';

  export let data;

  // State
  let selectedPlanet = null;
  let locations = [];
  let allMobs = [];
  let loading = false;
  let editMode = false;
  let selectedId = null;
  let filteredLocationIds = null;
  let pendingChanges = new Map();
  let rightPanel = 'editor'; // 'editor' | 'sql' | 'mobEditor'
  let isNewLocation = false;
  let drawnShapeData = null;
  let mobEditorContext = null;
  let mapComponent;
  let previewShape = null;

  let nextTempId = -1;

  $: planets = (data.planets || []).filter(p => p.Properties?.Map?.Width);
  $: selectedLocation = selectedId ? locations.find(l => l.Id === selectedId) : null;
  $: changeCount = pendingChanges.size;

  async function loadPlanetData(planet) {
    if (!planet || !browser) return;
    loading = true;
    selectedId = null;
    isNewLocation = false;
    drawnShapeData = null;

    try {
      const [locs, areas, mobSpawns] = await Promise.all([
        apiCall(fetch, `/locations?Planet=${planet.Name}`),
        apiCall(fetch, `/areas?Planet=${planet.Name}`),
        apiCall(fetch, `/mobspawns?Planet=${planet.Name}`)
      ]);

      // Merge — same logic as public map +page.js
      const byId = {};
      for (const loc of (locs || [])) byId[loc.Id] = loc;
      for (const area of (areas || [])) {
        byId[area.Id] = area;
        const offsetId = area.Id + 200000;
        if (byId[offsetId] && !byId[offsetId].Properties?.Shape) delete byId[offsetId];
      }
      for (const ms of (mobSpawns || [])) byId[ms.Id] = ms;

      locations = Object.values(byId);

      // Load mobs once (cached)
      if (!allMobs.length) {
        const mobsData = await apiCall(fetch, '/mobs');
        allMobs = mobsData || [];
      }
    } catch (e) {
      console.error('Failed to load planet data:', e);
    } finally {
      loading = false;
    }

    // Trigger map image load after data
    if (mapComponent) {
      // Small delay to ensure reactive updates propagate
      setTimeout(() => mapComponent.loadPlanetImage(), 50);
    }
  }

  function handlePlanetChange(e) {
    const planetId = Number(e.target.value);
    selectedPlanet = planets.find(p => p.Id === planetId) || null;
    pendingChanges = new Map();
    if (selectedPlanet) loadPlanetData(selectedPlanet);
  }

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
    // Pan map to location
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
      // Editing existing
      const loc = mobEditorContext.location;
      const existing = pendingChanges.get(loc.Id);
      const modified = existing?.modified || {};
      modified.name = mobData.name;
      modified.mobData = { density: mobData.density, maturities: mobData.maturities };
      pendingChanges.set(loc.Id, { action: 'edit', original: loc, modified });
    } else if (mobEditorContext?.isNew && drawnShapeData) {
      // For a new location, store mob data to be used when adding
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
</script>

<style>
  .admin-map-page {
    display: flex;
    flex-direction: column;
    height: calc(100% + 48px);
    overflow: hidden;
    margin: -24px; /* offset admin-content padding */
  }

  .toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 16px;
    background: var(--secondary-color);
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .toolbar select {
    padding: 6px 10px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 13px;
  }

  .toolbar-label {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  .mode-toggle {
    display: flex;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .mode-toggle button {
    padding: 6px 12px;
    font-size: 12px;
    border: none;
    background: var(--primary-color);
    color: var(--text-muted);
    cursor: pointer;
  }
  .mode-toggle button:not(:last-child) { border-right: 1px solid var(--border-color); }
  .mode-toggle button.active { background: var(--accent-color); color: white; }

  .sql-toggle {
    margin-left: auto;
    position: relative;
    padding: 6px 12px;
    font-size: 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    cursor: pointer;
  }
  .sql-toggle.active { border-color: var(--accent-color); color: var(--accent-color); }

  .badge {
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

  .main-content {
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

<div class="admin-map-page">
  <div class="toolbar">
    <span class="toolbar-label">Planet:</span>
    <select on:change={handlePlanetChange} value={selectedPlanet?.Id ?? ''}>
      <option value="" disabled>Select planet...</option>
      {#each planets as planet}
        <option value={planet.Id}>{planet.Name}</option>
      {/each}
    </select>

    <div class="mode-toggle">
      <button class:active={!editMode} on:click={() => editMode = false}>View</button>
      <button class:active={editMode} on:click={() => editMode = true}>Edit</button>
    </div>

    <button
      class="sql-toggle"
      class:active={rightPanel === 'sql'}
      on:click={() => rightPanel = rightPanel === 'sql' ? 'editor' : 'sql'}
    >
      SQL Output
      {#if changeCount > 0}
        <span class="badge">{changeCount}</span>
      {/if}
    </button>
  </div>

  <div class="main-content">
    <div class="left-sidebar">
      {#if selectedPlanet}
        <AdminLocationList
          {locations}
          {selectedId}
          {pendingChanges}
          {editMode}
          on:select={handleListSelect}
          on:filterChange={handleFilterChange}
          on:massDelete={handleMassDelete}
        />
      {/if}
    </div>

    <div class="map-area">
      {#if selectedPlanet}
        <AdminMapLeaflet
          bind:this={mapComponent}
          planet={selectedPlanet}
          {locations}
          {filteredLocationIds}
          {selectedId}
          {pendingChanges}
          {editMode}
          {previewShape}
          on:select={handleMapSelect}
          on:drawCreated={handleDrawCreated}
          on:shapeEdited={handleShapeEdited}
        />
        {#if loading}
          <div class="loading-overlay">Loading map data...</div>
        {/if}
      {:else}
        <div class="no-planet">Select a planet to load the map.</div>
      {/if}
    </div>

    <div class="right-panel">
      {#if rightPanel === 'sql'}
        <AdminSqlOutput {pendingChanges} planetId={selectedPlanet?.Id} />
      {:else if rightPanel === 'mobEditor'}
        <AdminMobAreaEditor
          mobs={allMobs}
          location={mobEditorContext?.location}
          isNew={mobEditorContext?.isNew || false}
          on:save={handleMobSave}
          on:cancel={handleMobCancel}
        />
      {:else}
        <AdminLocationEditor
          location={selectedLocation}
          isNew={isNewLocation}
          {drawnShapeData}
          on:add={handleAddLocation}
          on:edit={handleEditLocation}
          on:delete={handleDeleteLocation}
          on:revert={handleRevertLocation}
          on:editMobArea={handleEditMobArea}
          on:preview={handlePreview}
        />
      {/if}
    </div>
  </div>
</div>
