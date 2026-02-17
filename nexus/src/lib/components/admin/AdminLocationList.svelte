<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { LOCATION_TYPES, AREA_TYPES, getEffectiveType, getTypeColor, isArea } from './adminMapUtils.js';

  export let locations = [];
  export let selectedId = null;
  export let pendingChanges = new Map();
  export let editMode = false;

  const dispatch = createEventDispatcher();

  // Filter state
  let typeFilters = {};
  let areaTypeFilters = {};
  let searchQuery = '';
  let multiSelectMode = false;
  let selectedForDeletion = new Set();

  // Initialize all filters as checked
  LOCATION_TYPES.forEach(t => typeFilters[t] = true);
  AREA_TYPES.forEach(t => areaTypeFilters[t] = true);

  function toggleAll(val) {
    LOCATION_TYPES.forEach(t => typeFilters[t] = val);
    AREA_TYPES.forEach(t => areaTypeFilters[t] = val);
    typeFilters = typeFilters;
    areaTypeFilters = areaTypeFilters;
  }

  function setPointsOnly() {
    LOCATION_TYPES.forEach(t => typeFilters[t] = true);
    AREA_TYPES.forEach(t => areaTypeFilters[t] = false);
    typeFilters = typeFilters;
    areaTypeFilters = areaTypeFilters;
  }

  function setAreasOnly() {
    LOCATION_TYPES.forEach(t => typeFilters[t] = false);
    AREA_TYPES.forEach(t => areaTypeFilters[t] = true);
    // Keep 'Area' type enabled in location types since areas are stored as Type='Area'
    typeFilters['Estate'] = false;
    typeFilters = typeFilters;
    areaTypeFilters = areaTypeFilters;
  }

  // Filter locations
  $: filteredLocations = locations.filter(loc => {
    const effectiveType = getEffectiveType(loc);
    const locType = loc.Properties?.Type;

    // Check type filters
    if (locType === 'Area' || isArea(loc)) {
      const areaType = loc.Properties?.AreaType || loc.Properties?.Type;
      if (areaType && areaTypeFilters[areaType] === false) return false;
    } else {
      if (locType && typeFilters[locType] === false) return false;
    }

    // Search
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      const name = (loc.Name || '').toLowerCase();
      if (!name.includes(q)) return false;
    }

    return true;
  });

  // Group by effective type
  $: groupedLocations = (() => {
    const groups = {};
    for (const loc of filteredLocations) {
      const type = getEffectiveType(loc);
      if (!groups[type]) groups[type] = [];
      groups[type].push(loc);
    }
    // Sort each group by name
    for (const g of Object.values(groups)) g.sort((a, b) => (a.Name || '').localeCompare(b.Name || ''));
    return groups;
  })();

  // Emit filtered IDs to parent for map visibility
  $: {
    const ids = new Set(filteredLocations.map(l => l.Id));
    dispatch('filterChange', ids);
  }

  function handleSelect(loc) {
    if (multiSelectMode) {
      if (selectedForDeletion.has(loc.Id)) {
        selectedForDeletion.delete(loc.Id);
      } else {
        selectedForDeletion.add(loc.Id);
      }
      selectedForDeletion = selectedForDeletion;
    } else {
      dispatch('select', loc.Id);
    }
  }

  function markSelectedForDeletion() {
    dispatch('massDelete', selectedForDeletion);
    selectedForDeletion = new Set();
    multiSelectMode = false;
  }

  function getChangeIndicator(locId) {
    for (const [, change] of pendingChanges) {
      if (change.original?.Id === locId) return change.action;
    }
    return null;
  }
</script>

<style>
  .location-list-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .filters-section {
    padding: 8px;
    border-bottom: 1px solid var(--border-color);
    overflow-y: auto;
    max-height: 40%;
    flex-shrink: 0;
  }

  .filter-header {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    margin: 4px 0;
  }

  .filter-row {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: var(--text-color);
    padding: 1px 0;
  }

  .filter-row input[type="checkbox"] {
    margin: 0;
    padding: 0;
    width: 14px;
    height: 14px;
    flex-shrink: 0;
    vertical-align: middle;
  }

  .filter-row .color-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .quick-toggles {
    display: flex;
    gap: 4px;
    margin-bottom: 6px;
    flex-wrap: wrap;
  }

  .quick-toggles button {
    font-size: 10px;
    padding: 2px 6px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background: var(--secondary-color);
    color: var(--text-muted);
    cursor: pointer;
  }
  .quick-toggles button:hover { background: var(--hover-color); }

  .area-filters {
    padding-left: 12px;
  }

  .search-section {
    padding: 8px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .search-input {
    width: 100%;
    padding: 6px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 13px;
    box-sizing: border-box;
  }

  .list-section {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
  }

  .group-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    color: var(--text-muted);
    background: var(--secondary-color);
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .group-count {
    font-size: 10px;
    background: var(--border-color);
    padding: 1px 5px;
    border-radius: 8px;
  }

  .location-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    font-size: 12px;
    color: var(--text-color);
    cursor: pointer;
    border-left: 3px solid transparent;
  }

  .location-row:hover { background: var(--hover-color); }
  .location-row.selected { background: rgba(59, 130, 246, 0.15); border-left-color: var(--accent-color); }
  .location-row.multi-selected { background: rgba(239, 68, 68, 0.15); border-left-color: #ef4444; }

  .change-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .change-dot.delete { background: #ef4444; }
  .change-dot.edit { background: #f97316; }
  .change-dot.add { background: #22c55e; }

  .loc-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .loc-name.deleted { text-decoration: line-through; color: var(--text-muted); }

  .mass-actions {
    padding: 8px;
    border-top: 1px solid var(--border-color);
    display: flex;
    gap: 4px;
    flex-shrink: 0;
  }

  .mass-actions button {
    flex: 1;
    padding: 6px;
    font-size: 11px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    cursor: pointer;
    background: var(--secondary-color);
    color: var(--text-color);
  }
  .mass-actions button:hover { background: var(--hover-color); }
  .mass-actions .delete-btn { border-color: #ef4444; color: #ef4444; }
  .mass-actions .delete-btn:hover { background: rgba(239, 68, 68, 0.15); }

  .total-count {
    padding: 4px 8px;
    font-size: 11px;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border-color);
  }
</style>

<div class="location-list-container">
  <div class="filters-section">
    <div class="quick-toggles">
      <button on:click={() => toggleAll(true)}>All</button>
      <button on:click={() => toggleAll(false)}>None</button>
      <button on:click={setPointsOnly}>Points</button>
      <button on:click={setAreasOnly}>Areas</button>
    </div>

    <div class="filter-header">Location Types</div>
    {#each LOCATION_TYPES as type}
      <label class="filter-row">
        <input type="checkbox" bind:checked={typeFilters[type]} />
        <span class="color-dot" style="background:{getTypeColor(type)}"></span>
        {type}
      </label>
    {/each}

    <div class="filter-header" style="margin-top:6px">Area Types</div>
    <div class="area-filters">
      {#each AREA_TYPES as type}
        <label class="filter-row">
          <input type="checkbox" bind:checked={areaTypeFilters[type]} />
          <span class="color-dot" style="background:{getTypeColor(type)}"></span>
          {type}
        </label>
      {/each}
    </div>
  </div>

  <div class="search-section">
    <input class="search-input" type="text" placeholder="Search locations..." bind:value={searchQuery} />
  </div>

  <div class="total-count">
    {filteredLocations.length} / {locations.length} locations
  </div>

  <div class="list-section">
    {#each Object.entries(groupedLocations) as [type, locs]}
      <div class="group-header">
        <span>{type}</span>
        <span class="group-count">{locs.length}</span>
      </div>
      {#each locs as loc}
        {@const changeType = getChangeIndicator(loc.Id)}
        <div
          class="location-row"
          class:selected={selectedId === loc.Id}
          class:multi-selected={multiSelectMode && selectedForDeletion.has(loc.Id)}
          on:click={() => handleSelect(loc)}
          on:keydown={(e) => e.key === 'Enter' && handleSelect(loc)}
          role="button"
          tabindex="0"
        >
          {#if multiSelectMode}
            <input type="checkbox" checked={selectedForDeletion.has(loc.Id)} on:click|stopPropagation />
          {/if}
          {#if changeType}
            <span class="change-dot {changeType}"></span>
          {/if}
          <span class="loc-name" class:deleted={changeType === 'delete'}>{loc.Name}</span>
        </div>
      {/each}
    {/each}
  </div>

  {#if editMode}
    <div class="mass-actions">
      {#if multiSelectMode}
        <button class="delete-btn" on:click={markSelectedForDeletion} disabled={selectedForDeletion.size === 0}>
          Delete Selected ({selectedForDeletion.size})
        </button>
        <button on:click={() => { multiSelectMode = false; selectedForDeletion = new Set(); }}>Cancel</button>
      {:else}
        <button on:click={() => { multiSelectMode = true; }}>Multi-Select</button>
      {/if}
    </div>
  {/if}
</div>
