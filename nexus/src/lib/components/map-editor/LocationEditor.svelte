<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { addToast } from '$lib/stores/toasts.js';
  import { apiCall } from '$lib/util.js';
  import { LOCATION_TYPES, AREA_TYPES, SHAPES, isArea, getEffectiveType } from './mapEditorUtils.js';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';

  export let location = null;  // The selected location object (or null)
  export let isNew = false;    // Whether this is a newly drawn shape
  export let readOnly = false; // If true, all fields are disabled (inspect only)
  export let drawnShapeData = null;  // { shape, data, center } from drawing
  /** @type {'admin' | 'public'} */
  export let mode = 'admin';
  export let isAdmin = false;
  /** If this location is locked by another user's pending change, this is the change object */
  export let lockedBy = null;
  /** All locations on current planet (for parent picker) */
  export let allLocations = [];

  $: isLocked = !!lockedBy && !isAdmin;

  const dispatch = createEventDispatcher();

  // Edit form state
  let name = '';
  let locationType = 'Area';
  let longitude = 0;
  let latitude = 0;
  let altitude = 0;
  let areaType = 'MobArea';
  let shape = 'Polygon';
  let shapeDataJson = '';

  // Structured shape fields (Circle / Rectangle)
  let circleX = 0;
  let circleY = 0;
  let circleRadius = 100;
  let rectX = 0;
  let rectY = 0;
  let rectWidth = 100;
  let rectHeight = 100;

  // Parent location state
  let parentLocationName = '';

  // LandArea state
  let landAreaOwner = '';
  let taxRateHunting = null;
  let taxRateMining = null;
  let taxRateShops = null;

  // Related entities
  let relatedExpanded = false;
  let relatedMissions = null;
  let relatedLoading = false;

  /**
   * Parse a pasted waypoint string.
   * Supports: [Planet, x, y, z, Name] or simple x, y, z
   */
  function parseWaypoint(str) {
    // Full waypoint: [Planet, x, y, z, Name]
    const fullMatch = str.match(/\[([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,\]]+)(?:,\s*([^\]]*))?\]/);
    if (fullMatch) {
      return {
        x: parseFloat(fullMatch[2]) || 0,
        y: parseFloat(fullMatch[3]) || 0,
        z: parseFloat(fullMatch[4]) || 0,
        name: fullMatch[5]?.trim() || null
      };
    }
    // Simple: x, y, z (with or without brackets)
    const simpleMatch = str.match(/^\[?\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]?$/);
    if (simpleMatch) {
      return {
        x: parseFloat(simpleMatch[1]) || 0,
        y: parseFloat(simpleMatch[2]) || 0,
        z: parseFloat(simpleMatch[3]) || 0,
        name: null
      };
    }
    return null;
  }

  function handleCoordPaste(event) {
    const text = event.clipboardData?.getData('text') || '';
    const parsed = parseWaypoint(text);
    if (!parsed) return;
    event.preventDefault();
    longitude = parsed.x;
    latitude = parsed.y;
    altitude = parsed.z;
    if (parsed.name && !name) {
      name = parsed.name;
    }
    scheduleAutoSave();
  }

  // Track which location is loaded to avoid resetting form when same location re-renders
  let loadedLocationId = null;
  let loadedDrawnShapeRef = null;
  let _lastShapeDataRef = null;
  let _lastCoordsRef = null;

  // Parent location options for SearchInput (areas only)
  $: parentOptions = allLocations
    .filter(l => isArea(l) && l.Id !== location?.Id)
    .map(l => ({ label: l.Name, value: String(l.Id), sublabel: getEffectiveType(l) }));

  // Populate form from location or drawn data — only when the actual location changes
  $: if (location && !isNew && location.Id !== loadedLocationId) {
    loadedLocationId = location.Id;
    loadedDrawnShapeRef = null;
    name = location.Name || '';
    locationType = location.Properties?.Type === 'Area' || isArea(location) ? 'Area' : (location.Properties?.Type || 'Area');
    longitude = location.Properties?.Coordinates?.Longitude ?? 0;
    latitude = location.Properties?.Coordinates?.Latitude ?? 0;
    altitude = location.Properties?.Coordinates?.Altitude ?? 0;
    areaType = location.Properties?.AreaType || location.Properties?.Type || 'MobArea';
    shape = location.Properties?.Shape || 'Polygon';
    const existingData = location.Properties?.Data;
    if (shape === 'Circle' && existingData) {
      circleX = existingData.x ?? 0;
      circleY = existingData.y ?? 0;
      circleRadius = existingData.radius ?? 100;
      shapeDataJson = '';
    } else if (shape === 'Rectangle' && existingData) {
      rectX = existingData.x ?? 0;
      rectY = existingData.y ?? 0;
      rectWidth = existingData.width ?? 100;
      rectHeight = existingData.height ?? 100;
      shapeDataJson = '';
    } else {
      shapeDataJson = existingData ? JSON.stringify(existingData, null, 2) : '';
    }
    parentLocationName = location.ParentLocation?.Name || '';
    landAreaOwner = location.Properties?.LandAreaOwnerName || '';
    taxRateHunting = location.Properties?.TaxRateHunting ?? null;
    taxRateMining = location.Properties?.TaxRateMining ?? null;
    taxRateShops = location.Properties?.TaxRateShops ?? null;
    _lastShapeDataRef = location.Properties?.Data;
    _lastCoordsRef = location.Properties?.Coordinates;
    // Reset related data when location changes
    relatedMissions = null;
    relatedExpanded = false;
  }

  // Update shape fields when shape data changes externally (e.g., map drag/resize)
  $: if (location && location.Id === loadedLocationId && !isNew) {
    const newData = location.Properties?.Data;
    const newCoords = location.Properties?.Coordinates;
    if (newData !== _lastShapeDataRef) {
      _lastShapeDataRef = newData;
      if (newData) {
        const currentShape = location.Properties?.Shape || shape;
        if (currentShape === 'Circle') {
          circleX = newData.x ?? 0;
          circleY = newData.y ?? 0;
          circleRadius = newData.radius ?? 100;
        } else if (currentShape === 'Rectangle') {
          rectX = newData.x ?? 0;
          rectY = newData.y ?? 0;
          rectWidth = newData.width ?? 100;
          rectHeight = newData.height ?? 100;
        } else {
          shapeDataJson = JSON.stringify(newData, null, 2);
        }
      }
    }
    if (newCoords !== _lastCoordsRef) {
      _lastCoordsRef = newCoords;
      if (newCoords) {
        longitude = newCoords.Longitude ?? longitude;
        latitude = newCoords.Latitude ?? latitude;
      }
    }
  }

  // Clear tracking when deselected
  $: if (!location && !isNew) {
    loadedLocationId = null;
    loadedDrawnShapeRef = null;
    _lastShapeDataRef = null;
    _lastCoordsRef = null;
  }

  $: if (isNew && drawnShapeData && drawnShapeData !== loadedDrawnShapeRef) {
    loadedDrawnShapeRef = drawnShapeData;
    loadedLocationId = null;
    name = '';
    locationType = drawnShapeData.isMarker ? 'Teleporter' : 'Area';
    longitude = drawnShapeData.center?.x ?? 0;
    latitude = drawnShapeData.center?.y ?? 0;
    altitude = 0;
    areaType = 'MobArea';
    shape = drawnShapeData.shape || 'Polygon';
    const drawnData = drawnShapeData.data;
    if (shape === 'Circle' && drawnData) {
      circleX = drawnData.x ?? 0;
      circleY = drawnData.y ?? 0;
      circleRadius = drawnData.radius ?? 100;
      shapeDataJson = '';
    } else if (shape === 'Rectangle' && drawnData) {
      rectX = drawnData.x ?? 0;
      rectY = drawnData.y ?? 0;
      rectWidth = drawnData.width ?? 100;
      rectHeight = drawnData.height ?? 100;
      shapeDataJson = '';
    } else {
      shapeDataJson = drawnData ? JSON.stringify(drawnData, null, 2) : '';
    }
  }

  // Build shape data object from current form state
  function buildShapeData(shapeType) {
    if (shapeType === 'Circle') {
      return { x: Number(circleX), y: Number(circleY), radius: Number(circleRadius) };
    } else if (shapeType === 'Rectangle') {
      return { x: Number(rectX), y: Number(rectY), width: Number(rectWidth), height: Number(rectHeight) };
    } else if (shapeType === 'Polygon') {
      try {
        if (shapeDataJson.trim()) return JSON.parse(shapeDataJson);
      } catch { return null; }
    }
    return null;
  }

  // Dispatch preview events when form fields change (debounced)
  let previewTimeout;
  $: {
    // Track all shape-related fields for reactivity
    const _shape = shape;
    const _shapeDataJson = shapeDataJson;
    const _cX = circleX; const _cY = circleY; const _cR = circleRadius;
    const _rX = rectX; const _rY = rectY; const _rW = rectWidth; const _rH = rectHeight;
    const _lon = longitude;
    const _lat = latitude;
    const _locType = locationType;
    const _active = location || isNew;

    clearTimeout(previewTimeout);
    previewTimeout = setTimeout(() => {
      if (!_active) {
        dispatch('preview', null);
        return;
      }

      if (_locType === 'Area' && _shape) {
        let shapeData = null;
        if (_shape === 'Circle') {
          shapeData = { x: Number(_cX), y: Number(_cY), radius: Number(_cR) };
        } else if (_shape === 'Rectangle') {
          shapeData = { x: Number(_rX), y: Number(_rY), width: Number(_rW), height: Number(_rH) };
        } else if (_shape === 'Polygon') {
          try {
            if (_shapeDataJson.trim()) shapeData = JSON.parse(_shapeDataJson);
          } catch { return; } // invalid JSON — skip preview update
        }
        if (shapeData) {
          dispatch('preview', { shape: _shape, data: shapeData, center: null });
        } else {
          dispatch('preview', null);
        }
      } else if (_locType !== 'Area') {
        dispatch('preview', { shape: null, data: null, center: { x: Number(_lon), y: Number(_lat) } });
      } else {
        dispatch('preview', null);
      }
    }, 150);
  }

  // Auto-save: dispatch edit when form fields change via user interaction
  let autoSaveTimer;

  function scheduleAutoSave() {
    if (readOnly || isLocked) return;
    clearTimeout(autoSaveTimer);
    autoSaveTimer = setTimeout(dispatchAutoSave, 300);
  }

  function dispatchAutoSave() {
    if (readOnly || isLocked || !location) return;

    const modified = {
      name,
      locationType,
      longitude: Number(longitude),
      latitude: Number(latitude),
      altitude: Number(altitude) || null,
      areaType: locationType === 'Area' ? areaType : null,
      shape: locationType === 'Area' ? shape : null,
      shapeData: locationType === 'Area' ? buildShapeData(shape) : null,
      parentLocationName: parentLocationName || null,
      landAreaOwner: (isLandArea && landAreaOwner) ? landAreaOwner : null,
      taxRateHunting: isLandArea ? taxRateHunting : null,
      taxRateMining: isLandArea ? taxRateMining : null,
      taxRateShops: isLandArea ? taxRateShops : null
    };

    dispatch('edit', { original: location, modified });
  }

  function handleDelete() {
    if (!location) return;
    if (mode === 'public') {
      // In public mode: copy delete info to clipboard
      const type = getEffectiveType(location);
      const coords = location.Properties?.Coordinates;
      const coordStr = coords ? `${coords.Longitude ?? 0}, ${coords.Latitude ?? 0}, ${coords.Altitude ?? 0}` : 'N/A';
      const text = `Location: ${location.Name} (ID: ${location.Id}), Type: ${type}, Coords: ${coordStr}`;
      navigator.clipboard?.writeText(text);
      addToast('Delete info copied to clipboard', { type: 'success' });
    } else {
      dispatch('delete', location);
    }
  }

  function handleRemovePendingAdd() {
    if (!location) return;
    dispatch('removePendingAdd', location.Id);
  }

  function handleRevert() {
    dispatch('revert', location);
  }

  function handleEditMobArea() {
    dispatch('editMobArea', { location, isNew });
  }

  $: isAreaType = locationType === 'Area';
  $: isMobArea = isAreaType && areaType === 'MobArea';
  $: isLandArea = isAreaType && areaType === 'LandArea';

  async function fetchRelatedEntities() {
    if (!location?.Id || location._isPendingAdd || relatedLoading) return;
    relatedLoading = true;
    try {
      const missions = await apiCall(fetch, `/missions?StartLocationId=${location.Id}`);
      relatedMissions = missions || [];
    } catch (e) {
      relatedMissions = [];
    } finally {
      relatedLoading = false;
    }
  }

  function toggleRelated() {
    relatedExpanded = !relatedExpanded;
    if (relatedExpanded && relatedMissions === null) {
      fetchRelatedEntities();
    }
  }
</script>

<style>
  .editor-container {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
    height: 100%;
    overflow-y: auto;
  }

  .editor-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
    margin: 0;
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .field-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .field-input {
    padding: 6px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 13px;
    width: 100%;
    box-sizing: border-box;
  }

  .field-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  select.field-input {
    cursor: pointer;
  }

  textarea.field-input {
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 11px;
    resize: vertical;
    min-height: 60px;
  }

  .coord-row {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 4px;
  }

  .field-hint {
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
    font-size: 11px;
    margin-left: 6px;
    color: var(--accent-color);
    opacity: 0.65;
  }

  .lock-notice {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 10px 12px;
    margin-top: 4px;
    background: rgba(168, 85, 247, 0.1);
    border: 1px solid rgba(168, 85, 247, 0.3);
    border-radius: 4px;
    font-size: 12px;
    color: var(--text-color);
  }
  .lock-icon { font-size: 16px; flex-shrink: 0; }
  .lock-title { font-weight: 600; margin-bottom: 2px; }
  .lock-detail { color: var(--text-muted); font-size: 11px; }

  .actions {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 8px;
  }

  .btn {
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    text-align: center;
    background: var(--secondary-color);
    color: var(--text-color);
  }
  .btn:hover:not(:disabled) { background: var(--hover-color); }
  .btn:disabled { opacity: 0.5; cursor: default; }

  .btn-primary {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }
  .btn-primary:hover { opacity: 0.9; }

  .btn-danger {
    border-color: #ef4444;
    color: #ef4444;
  }
  .btn-danger:hover { background: rgba(239, 68, 68, 0.15); }

  .btn-mob {
    border-color: #eab308;
    color: #eab308;
  }
  .btn-mob:hover { background: rgba(234, 179, 8, 0.15); }

  .section-divider {
    border-top: 1px solid var(--border-color);
    margin: 4px 0;
  }

  .no-selection {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    font-size: 13px;
    text-align: center;
    padding: 20px;
  }

  .related-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 6px 0;
    border: none;
    background: none;
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    cursor: pointer;
  }
  .related-toggle:hover { color: var(--text-color); }

  .related-toggle-arrow {
    font-size: 10px;
    transition: transform 0.15s ease;
  }

  .related-section {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .related-loading, .related-empty {
    font-size: 12px;
    color: var(--text-muted);
    padding: 4px 0;
  }

  .related-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .related-item {
    font-size: 12px;
    color: var(--accent-color);
    text-decoration: none;
    padding: 2px 0;
  }
  .related-item:hover { text-decoration: underline; }
</style>

{#if !location && !isNew}
  <div class="no-selection">
    Select a location on the map or in the list, or draw a new shape to edit.
  </div>
{:else}
  <div class="editor-container" on:input={scheduleAutoSave} on:change={scheduleAutoSave}>
    <h3 class="editor-title">{isNew ? 'New Location' : readOnly ? (location?.Name || '') : `Edit: ${location?.Name || ''}`}</h3>

    <div class="field-group">
      <span class="field-label">Name</span>
      <input class="field-input" type="text" bind:value={name} placeholder="Location name" disabled={readOnly || isMobArea} title={isMobArea ? 'Mob area names are auto-generated — edit via Mob Spawns' : ''} />
    </div>

    <div class="field-group">
      <span class="field-label">Type</span>
      <select class="field-input" bind:value={locationType} disabled={readOnly}>
        {#each LOCATION_TYPES as t}
          <option value={t}>{t}</option>
        {/each}
        <option value="Area">Area</option>
      </select>
    </div>

    <div class="field-group">
      <span class="field-label">Coordinates <span class="field-hint">paste waypoint</span></span>
      <div class="coord-row">
        <input class="field-input" type="number" bind:value={longitude} placeholder="Lon" title="Longitude" disabled={readOnly} on:paste={handleCoordPaste} />
        <input class="field-input" type="number" bind:value={latitude} placeholder="Lat" title="Latitude" disabled={readOnly} on:paste={handleCoordPaste} />
        <input class="field-input" type="number" bind:value={altitude} placeholder="Alt" title="Altitude" disabled={readOnly} on:paste={handleCoordPaste} />
      </div>
    </div>

    {#if isAreaType}
      <div class="section-divider"></div>

      <div class="field-group">
        <span class="field-label">Area Type</span>
        <select class="field-input" bind:value={areaType} disabled={readOnly}>
          {#each AREA_TYPES as t}
            <option value={t}>{t}</option>
          {/each}
        </select>
      </div>

      <div class="field-group">
        <span class="field-label">Shape</span>
        <select class="field-input" bind:value={shape} disabled={readOnly}>
          {#each SHAPES as s}
            <option value={s}>{s}</option>
          {/each}
        </select>
      </div>

      {#if shape === 'Circle'}
        <div class="field-group">
          <span class="field-label">Center</span>
          <div class="coord-row" style="grid-template-columns: 1fr 1fr;">
            <input class="field-input" type="number" bind:value={circleX} placeholder="X" title="Center X" disabled={readOnly} />
            <input class="field-input" type="number" bind:value={circleY} placeholder="Y" title="Center Y" disabled={readOnly} />
          </div>
        </div>
        <div class="field-group">
          <span class="field-label">Radius</span>
          <input class="field-input" type="number" bind:value={circleRadius} min="1" placeholder="Radius" title="Radius" disabled={readOnly} />
        </div>
      {:else if shape === 'Rectangle'}
        <div class="field-group">
          <span class="field-label">Origin</span>
          <div class="coord-row" style="grid-template-columns: 1fr 1fr;">
            <input class="field-input" type="number" bind:value={rectX} placeholder="X" title="Origin X" disabled={readOnly} />
            <input class="field-input" type="number" bind:value={rectY} placeholder="Y" title="Origin Y" disabled={readOnly} />
          </div>
        </div>
        <div class="field-group">
          <span class="field-label">Size</span>
          <div class="coord-row" style="grid-template-columns: 1fr 1fr;">
            <input class="field-input" type="number" bind:value={rectWidth} min="1" placeholder="Width" title="Width" disabled={readOnly} />
            <input class="field-input" type="number" bind:value={rectHeight} min="1" placeholder="Height" title="Height" disabled={readOnly} />
          </div>
        </div>
      {:else}
        <div class="field-group">
          <span class="field-label">Shape Data (JSON)</span>
          <textarea class="field-input" bind:value={shapeDataJson} rows="4" disabled={readOnly}></textarea>
        </div>
      {/if}

      {#if isMobArea}
        {#if !readOnly}
          <button class="btn btn-mob" on:click={handleEditMobArea}>
            Edit Mob Spawns
          </button>
        {/if}
      {/if}

      {#if isLandArea}
        <div class="section-divider"></div>
        <div class="field-group">
          <span class="field-label">Land Area Owner</span>
          <input class="field-input" type="text" bind:value={landAreaOwner} placeholder="Player name (resolved on approval)" disabled={readOnly} />
        </div>
        <div class="field-group">
          <span class="field-label">Tax Rates (%)</span>
          <div class="coord-row">
            <input class="field-input" type="number" bind:value={taxRateHunting} min="0" max="5" step="0.1" placeholder="Hunt" title="Hunting Tax %" disabled={readOnly} />
            <input class="field-input" type="number" bind:value={taxRateMining} min="0" max="5" step="0.1" placeholder="Mine" title="Mining Tax %" disabled={readOnly} />
            <input class="field-input" type="number" bind:value={taxRateShops} min="0" max="5" step="0.1" placeholder="Shop" title="Shops Tax %" disabled={readOnly} />
          </div>
        </div>
      {/if}
    {/if}

    <div class="section-divider"></div>

    <!-- Parent Location -->
    <div class="field-group">
      <span class="field-label">Parent Location</span>
      {#if allLocations.length > 0}
        <SearchInput
          value={parentLocationName}
          options={parentOptions}
          placeholder="Search parent area..."
          limit={15}
          disabled={readOnly}
          on:change={(e) => { parentLocationName = e.detail.value; scheduleAutoSave(); }}
          on:select={(e) => { parentLocationName = e.detail.data?.label || e.detail.value; scheduleAutoSave(); }}
        />
      {:else}
        <input class="field-input" type="text" bind:value={parentLocationName} placeholder="Parent area name" disabled={readOnly} />
      {/if}
    </div>

    <div class="section-divider"></div>

    {#if isLocked}
      <div class="lock-notice">
        <span class="lock-icon">&#x1F512;</span>
        <div>
          <div class="lock-title">Locked by another user</div>
          <div class="lock-detail">{lockedBy.author_name || lockedBy.author_eu_name || 'Another user'} has a pending {lockedBy.state?.toLowerCase() || ''} change for this location.</div>
        </div>
      </div>
    {/if}

    {#if !readOnly}
      <div class="actions">
        {#if !isNew && location?._isPendingAdd}
          <button class="btn btn-danger" on:click={handleRemovePendingAdd}>
            Remove
          </button>
        {:else if !isNew}
          <button class="btn btn-danger" on:click={handleDelete} disabled={isLocked}
            title={mode === 'public' ? 'Copies location details to your clipboard — send this to an admin if you believe this location should be deleted' : null}
          >
            {mode === 'public' ? 'Copy Delete Info' : 'Mark for Deletion'}
          </button>
          <button class="btn" on:click={handleRevert}>Revert Changes</button>
        {/if}
      </div>
    {/if}

    <!-- Related Entities (read-only, collapsible) -->
    {#if !isNew && location?.Id}
      <div class="section-divider"></div>
      <button class="related-toggle" on:click={toggleRelated}>
        <span class="related-toggle-label">Related Entities</span>
        <span class="related-toggle-arrow" class:expanded={relatedExpanded}>{relatedExpanded ? '\u25B2' : '\u25BC'}</span>
      </button>
      {#if relatedExpanded}
        <div class="related-section">
          {#if relatedLoading}
            <div class="related-loading">Loading...</div>
          {:else if relatedMissions !== null}
            {#if relatedMissions.length > 0}
              <span class="field-label">Missions ({relatedMissions.length})</span>
              <div class="related-list">
                {#each relatedMissions as mission}
                  <a class="related-item" href="/information/missions/{mission.Id}" target="_blank" rel="noopener">
                    {mission.Name}
                  </a>
                {/each}
              </div>
            {:else}
              <div class="related-empty">No related entities found.</div>
            {/if}
          {/if}
        </div>
      {/if}
    {/if}
  </div>
{/if}
