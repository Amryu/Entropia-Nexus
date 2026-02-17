<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { addToast } from '$lib/stores/toasts.js';
  import { LOCATION_TYPES, AREA_TYPES, SHAPES, isArea, getEffectiveType } from './adminMapUtils.js';

  export let location = null;  // The selected location object (or null)
  export let isNew = false;    // Whether this is a newly drawn shape
  export let drawnShapeData = null;  // { shape, data, center } from drawing

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

  // Populate form from location or drawn data
  $: if (location && !isNew) {
    name = location.Name || '';
    locationType = location.Properties?.Type === 'Area' || isArea(location) ? 'Area' : (location.Properties?.Type || 'Area');
    longitude = location.Properties?.Coordinates?.Longitude ?? 0;
    latitude = location.Properties?.Coordinates?.Latitude ?? 0;
    altitude = location.Properties?.Coordinates?.Altitude ?? 0;
    areaType = location.Properties?.AreaType || location.Properties?.Type || 'MobArea';
    shape = location.Properties?.Shape || 'Polygon';
    shapeDataJson = location.Properties?.Data ? JSON.stringify(location.Properties.Data, null, 2) : '';
  }

  $: if (isNew && drawnShapeData) {
    name = '';
    locationType = drawnShapeData.isMarker ? 'Teleporter' : 'Area';
    longitude = drawnShapeData.center?.x ?? 0;
    latitude = drawnShapeData.center?.y ?? 0;
    altitude = 0;
    areaType = 'MobArea';
    shape = drawnShapeData.shape || 'Polygon';
    shapeDataJson = drawnShapeData.data ? JSON.stringify(drawnShapeData.data, null, 2) : '';
  }

  // Dispatch preview events when form fields change (debounced)
  let previewTimeout;
  $: {
    const _shape = shape;
    const _shapeDataJson = shapeDataJson;
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

      let parsedData = null;
      try {
        if (_shapeDataJson.trim()) parsedData = JSON.parse(_shapeDataJson);
      } catch { return; } // invalid JSON — skip preview update

      if (_locType === 'Area' && _shape && parsedData) {
        dispatch('preview', { shape: _shape, data: parsedData, center: null });
      } else if (_locType !== 'Area') {
        dispatch('preview', { shape: null, data: null, center: { x: Number(_lon), y: Number(_lat) } });
      } else {
        dispatch('preview', null);
      }
    }, 150);
  }

  function handleSave() {
    let shapeData = null;
    try {
      if (shapeDataJson.trim()) shapeData = JSON.parse(shapeDataJson);
    } catch (e) {
      addToast('Invalid shape data JSON', { type: 'error' });
      return;
    }

    const modified = {
      name,
      locationType,
      longitude: Number(longitude),
      latitude: Number(latitude),
      altitude: Number(altitude) || null,
      areaType: locationType === 'Area' ? areaType : null,
      shape: locationType === 'Area' ? shape : null,
      shapeData: locationType === 'Area' ? shapeData : null
    };

    if (isNew) {
      dispatch('add', modified);
    } else {
      dispatch('edit', { original: location, modified });
    }
  }

  function handleDelete() {
    if (location) {
      dispatch('delete', location);
    }
  }

  function handleRevert() {
    dispatch('revert', location);
  }

  function handleEditMobArea() {
    dispatch('editMobArea', { location, isNew });
  }

  $: isAreaType = locationType === 'Area';
  $: isMobArea = isAreaType && areaType === 'MobArea';
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
  .btn:hover { background: var(--hover-color); }

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
</style>

{#if !location && !isNew}
  <div class="no-selection">
    Select a location on the map or in the list, or draw a new shape to edit.
  </div>
{:else}
  <div class="editor-container">
    <h3 class="editor-title">{isNew ? 'New Location' : `Edit: ${location?.Name || ''}`}</h3>

    <div class="field-group">
      <span class="field-label">Name</span>
      <input class="field-input" type="text" bind:value={name} placeholder="Location name" />
    </div>

    <div class="field-group">
      <span class="field-label">Type</span>
      <select class="field-input" bind:value={locationType}>
        {#each LOCATION_TYPES as t}
          <option value={t}>{t}</option>
        {/each}
        <option value="Area">Area</option>
      </select>
    </div>

    <div class="field-group">
      <span class="field-label">Coordinates</span>
      <div class="coord-row">
        <input class="field-input" type="number" bind:value={longitude} placeholder="Lon" title="Longitude" />
        <input class="field-input" type="number" bind:value={latitude} placeholder="Lat" title="Latitude" />
        <input class="field-input" type="number" bind:value={altitude} placeholder="Alt" title="Altitude" />
      </div>
    </div>

    {#if isAreaType}
      <div class="section-divider"></div>

      <div class="field-group">
        <span class="field-label">Area Type</span>
        <select class="field-input" bind:value={areaType}>
          {#each AREA_TYPES as t}
            <option value={t}>{t}</option>
          {/each}
        </select>
      </div>

      <div class="field-group">
        <span class="field-label">Shape</span>
        <select class="field-input" bind:value={shape}>
          {#each SHAPES as s}
            <option value={s}>{s}</option>
          {/each}
        </select>
      </div>

      <div class="field-group">
        <span class="field-label">Shape Data (JSON)</span>
        <textarea class="field-input" bind:value={shapeDataJson} rows="4"></textarea>
      </div>

      {#if isMobArea}
        <button class="btn btn-mob" on:click={handleEditMobArea}>
          Edit Mob Spawns
        </button>
      {/if}
    {/if}

    <div class="section-divider"></div>

    <div class="actions">
      <button class="btn btn-primary" on:click={handleSave}>
        {isNew ? 'Add Location' : 'Save Changes'}
      </button>
      {#if !isNew}
        <button class="btn btn-danger" on:click={handleDelete}>Mark for Deletion</button>
        <button class="btn" on:click={handleRevert}>Revert Changes</button>
      {/if}
    </div>
  </div>
{/if}
