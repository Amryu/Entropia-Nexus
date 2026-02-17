<script>
  // @ts-nocheck
  import { browser } from '$app/environment';
  import { apiCall } from '$lib/util.js';
  import MapEditorWorkspace from '$lib/components/map-editor/MapEditorWorkspace.svelte';
  import AdminSqlOutput from '$lib/components/admin/AdminSqlOutput.svelte';

  export let data;

  // Admin-specific state
  let selectedPlanet = null;
  let locations = [];
  let allMobs = [];
  let loading = false;
  let editMode = false;
  let workspace;

  // Bound from workspace
  let pendingChanges = new Map();
  let rightPanel = 'editor';
  let mapComponent;
  let changeCount = 0;

  $: planets = (data.planets || []).filter(p => p.Properties?.Map?.Width);

  async function loadPlanetData(planet) {
    if (!planet || !browser) return;
    loading = true;
    workspace?.reset();

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
      setTimeout(() => mapComponent.loadPlanetImage(), 50);
    }
  }

  function handlePlanetChange(e) {
    const planetId = Number(e.target.value);
    selectedPlanet = planets.find(p => p.Id === planetId) || null;
    pendingChanges = new Map();
    if (selectedPlanet) loadPlanetData(selectedPlanet);
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

  <MapEditorWorkspace
    bind:this={workspace}
    planet={selectedPlanet}
    {locations}
    {allMobs}
    {editMode}
    {loading}
    mode="admin"
    bind:pendingChanges
    bind:rightPanel
    bind:mapComponent
    bind:changeCount
  >
    <svelte:fragment slot="output">
      <AdminSqlOutput {pendingChanges} planetId={selectedPlanet?.Id} />
    </svelte:fragment>
  </MapEditorWorkspace>
</div>
