<!--
  @component MobSpawnsEdit
  Array editor for mob spawn locations.
  Supports waypoint paste, shape configuration, density, and mob set entries
  with maturity configuration dialog.
-->
<script>
  // @ts-nocheck
  import { editMode, updateField, currentEntity } from '$lib/stores/wikiEditState.js';
  import { clickable } from '$lib/actions/clickable.js';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';

  /** @type {Array} Spawns array from the mob */
  export let spawns = [];

  /** @type {string} Field path for updateField */
  export let fieldPath = 'Spawns';

  /** @type {string} Current mob name */
  export let mobName = '';

  /** @type {Array} Available maturities from the current mob */
  export let maturities = [];

  /** @type {Array} All mobs list for shared spawn feature */
  export let allMobs = [];

  // Constants
  const DEFAULT_SPAWN_RADIUS = 100;
  const SHAPE_OPTIONS = ['Point', 'Circle', 'Rectangle', 'Polygon'];
  const DENSITY_OPTIONS = [
    { value: 1, label: 'Very Low' },
    { value: 2, label: 'Low' },
    { value: 3, label: 'Medium' },
    { value: 4, label: 'High' },
    { value: 5, label: 'Very High' }
  ];

  // Track which spawn panels are expanded
  let expandedSpawns = {};

  // Maturity dialog state: { spawnIndex, mobName } or null
  let maturityDialog = null;

  // Mob search options for SearchInput (local mode)
  $: mobSearchOptions = (allMobs || []).map(m => ({ label: m.Name, value: m.Name }));

  // === Spawn Constructor ===
  function createSpawn() {
    return {
      Properties: {
        Density: 3,
        IsShared: false,
        IsEvent: false,
        Shape: 'Point',
        Data: {
          x: 0,
          y: 0,
          radius: DEFAULT_SPAWN_RADIUS
        },
        Coordinates: {
          Altitude: 0
        }
      },
      Maturities: []
    };
  }

  // === CRUD Operations ===
  function addSpawn() {
    const newSpawn = createSpawn();
    const newList = [...spawns, newSpawn];
    updateField(fieldPath, newList);
    expandedSpawns[newList.length - 1] = true;
  }

  function removeSpawn(index) {
    const newList = spawns.filter((_, i) => i !== index);
    updateField(fieldPath, newList);
    delete expandedSpawns[index];
  }

  function updateSpawnField(spawnIndex, field, value) {
    const newList = [...spawns];
    const parts = field.split('.');
    let target = newList[spawnIndex];

    for (let i = 0; i < parts.length - 1; i++) {
      if (!target[parts[i]]) target[parts[i]] = {};
      target = target[parts[i]];
    }
    target[parts[parts.length - 1]] = value;

    updateField(fieldPath, newList);
  }

  // Parse waypoint string: [Planet, x, y, z, Name]
  function parseWaypoint(waypointStr) {
    const match = waypointStr.match(/\[([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),?\s*([^\]]*)\]/);
    if (match) {
      return {
        planet: match[1].trim(),
        x: parseFloat(match[2]) || 0,
        y: parseFloat(match[3]) || 0,
        z: parseFloat(match[4]) || 0,
        name: match[5]?.trim() || ''
      };
    }
    return null;
  }

  function handleWaypointPaste(spawnIndex, event) {
    const waypointStr = event.target.value;
    const parsed = parseWaypoint(waypointStr);

    if (parsed) {
      const newList = [...spawns];
      const spawn = newList[spawnIndex];

      // Parse existing data safely
      let data = spawn.Properties?.Data;
      if (typeof data === 'string') {
        try { data = JSON.parse(data); } catch (e) { data = {}; }
      }
      data = data || {};

      data.x = parsed.x;
      data.y = parsed.y;
      if (!data.radius) data.radius = DEFAULT_SPAWN_RADIUS;

      spawn.Properties.Data = data;
      if (!spawn.Properties.Coordinates) spawn.Properties.Coordinates = {};
      spawn.Properties.Coordinates.Altitude = parsed.z;

      updateField(fieldPath, newList);
      event.target.value = ''; // Clear the paste input
    }
  }

  function getWaypointDisplay(spawn) {
    const data = typeof spawn.Properties?.Data === 'string'
      ? JSON.parse(spawn.Properties.Data)
      : spawn.Properties?.Data;
    const x = data?.x || 0;
    const y = data?.y || 0;
    const z = spawn.Properties?.Coordinates?.Altitude || 0;
    return `[${x}, ${y}, ${z}]`;
  }

  // === Mob Entry Operations ===

  /** Get full maturities list for a mob by name */
  function getFullMaturitiesForMob(targetMobName) {
    if (targetMobName === mobName) return maturities;
    const mob = allMobs?.find(m => m.Name === targetMobName);
    return mob?.Maturities || [];
  }

  /** Sort maturities: non-bosses first, then by level/health */
  function sortMaturities(mats) {
    mats.sort((a, b) => {
      if (a.boss !== b.boss) return a.boss ? 1 : -1;
      const aLvl = a.level;
      const bLvl = b.level;
      if (aLvl != null && bLvl != null) {
        if (aLvl !== bLvl) return aLvl - bLvl;
        return (a.health || 0) - (b.health || 0);
      }
      if (aLvl != null) return -1;
      if (bLvl != null) return 1;
      return (a.health || 0) - (b.health || 0);
    });
  }

  /** Build mob entries from a spawn's Maturities array */
  function getSpawnMobEntries(spawn) {
    const spawnMats = spawn?.Maturities || [];
    const mobMap = new Map();

    // Group existing spawn maturities by mob name
    for (const entry of spawnMats) {
      const entryMobName = entry.Maturity?.Mob?.Name || mobName;
      if (!mobMap.has(entryMobName)) {
        mobMap.set(entryMobName, new Map());
      }
      if (entry.Maturity?.Name) {
        mobMap.get(entryMobName).set(entry.Maturity.Name, entry.IsRare || false);
      }
    }

    // Build full entries with all available maturities
    const entries = [];
    for (const [entryMobName, selectedMap] of mobMap) {
      const fullMats = getFullMaturitiesForMob(entryMobName);
      const matEntries = fullMats.map(m => ({
        name: m.Name,
        health: m.Properties?.Health ?? 0,
        level: m.Properties?.Level ?? null,
        boss: m.Properties?.Boss === true,
        selected: selectedMap.has(m.Name),
        isRare: selectedMap.get(m.Name) || false
      }));
      sortMaturities(matEntries);
      entries.push({ mobName: entryMobName, maturities: matEntries });
    }
    return entries;
  }

  /** Convert mob entries back to spawn.Maturities format and persist */
  function syncSpawnMaturities(spawnIndex, mobEntries) {
    const newMaturities = [];
    for (const entry of mobEntries) {
      for (const mat of entry.maturities) {
        if (mat.selected) {
          newMaturities.push({
            IsRare: mat.isRare,
            Maturity: {
              Name: mat.name,
              Mob: { Name: entry.mobName }
            }
          });
        }
      }
    }
    const newList = [...spawns];
    newList[spawnIndex].Maturities = newMaturities;
    updateField(fieldPath, newList);
  }

  /** Get selected maturity count for a mob at a spawn */
  function getSelectedCount(spawn, targetMobName) {
    return (spawn?.Maturities || []).filter(
      m => (m.Maturity?.Mob?.Name || mobName) === targetMobName
    ).length;
  }

  /** Get total maturity count for a mob */
  function getTotalCount(targetMobName) {
    return getFullMaturitiesForMob(targetMobName).length;
  }

  // === Mob Search ===

  /** Build a filter function for mob search that excludes current mob and already-added mobs */
  function getMobSearchFilter(spawn) {
    const existingMobs = new Set(
      (spawn?.Maturities || []).map(m => m.Maturity?.Mob?.Name || mobName)
    );
    existingMobs.add(mobName);
    return (opt) => !existingMobs.has(typeof opt === 'string' ? opt : opt?.label || opt?.Name);
  }

  function addMobToSpawn(spawnIndex, targetMobName) {
    // Open the maturity dialog immediately for configuration
    openMaturityDialog(spawnIndex, targetMobName);
  }

  function removeMobFromSpawn(spawnIndex, targetMobName) {
    const newList = [...spawns];
    newList[spawnIndex].Maturities = (newList[spawnIndex].Maturities || []).filter(
      m => (m.Maturity?.Mob?.Name || mobName) !== targetMobName
    );
    updateField(fieldPath, newList);
    if (maturityDialog?.spawnIndex === spawnIndex && maturityDialog?.mobName === targetMobName) {
      maturityDialog = null;
    }
  }

  function addCurrentMobToSpawn(spawnIndex) {
    // Just open the dialog for the current mob — entries will be created when user selects maturities
    openMaturityDialog(spawnIndex, mobName);
  }

  // === Maturity Dialog ===
  function openMaturityDialog(spawnIndex, targetMobName) {
    maturityDialog = { spawnIndex, mobName: targetMobName };
  }

  function closeMaturityDialog() {
    maturityDialog = null;
  }

  // Build dialog maturity entries from spawn data + full maturities
  $: dialogEntries = (() => {
    if (!maturityDialog) return [];
    const spawn = spawns[maturityDialog.spawnIndex];
    const targetMobName = maturityDialog.mobName;
    const fullMats = getFullMaturitiesForMob(targetMobName);

    // Build lookup of selected maturities
    const selectedMap = new Map();
    for (const entry of (spawn?.Maturities || [])) {
      if ((entry.Maturity?.Mob?.Name || mobName) === targetMobName && entry.Maturity?.Name) {
        selectedMap.set(entry.Maturity.Name, entry.IsRare || false);
      }
    }

    const entries = fullMats.map(m => ({
      name: m.Name,
      health: m.Properties?.Health ?? 0,
      level: m.Properties?.Level ?? null,
      boss: m.Properties?.Boss === true,
      selected: selectedMap.has(m.Name),
      isRare: selectedMap.get(m.Name) || false
    }));
    sortMaturities(entries);
    return entries;
  })();

  function toggleDialogMaturity(matName) {
    if (!maturityDialog) return;
    const { spawnIndex, mobName: targetMobName } = maturityDialog;
    const newList = [...spawns];
    const spawn = newList[spawnIndex];
    const mats = spawn.Maturities || [];

    const existingIdx = mats.findIndex(
      m => (m.Maturity?.Mob?.Name || mobName) === targetMobName && m.Maturity?.Name === matName
    );

    if (existingIdx >= 0) {
      // Remove
      mats.splice(existingIdx, 1);
    } else {
      // Add
      mats.push({
        IsRare: false,
        Maturity: { Name: matName, Mob: { Name: targetMobName } }
      });
    }
    spawn.Maturities = mats;
    updateField(fieldPath, newList);
  }

  function toggleDialogRare(matName) {
    if (!maturityDialog) return;
    const { spawnIndex, mobName: targetMobName } = maturityDialog;
    const newList = [...spawns];
    const spawn = newList[spawnIndex];
    const mat = (spawn.Maturities || []).find(
      m => (m.Maturity?.Mob?.Name || mobName) === targetMobName && m.Maturity?.Name === matName
    );
    if (mat) {
      mat.IsRare = !mat.IsRare;
      updateField(fieldPath, newList);
    }
  }

  function selectAllDialogMaturities() {
    if (!maturityDialog) return;
    const { spawnIndex, mobName: targetMobName } = maturityDialog;
    const fullMats = getFullMaturitiesForMob(targetMobName);
    const newList = [...spawns];
    const spawn = newList[spawnIndex];
    const mats = spawn.Maturities || [];

    // Find existing selected names for this mob
    const existingNames = new Set(
      mats.filter(m => (m.Maturity?.Mob?.Name || mobName) === targetMobName)
        .map(m => m.Maturity?.Name)
    );

    // Add any missing
    for (const m of fullMats) {
      if (!existingNames.has(m.Name)) {
        mats.push({
          IsRare: false,
          Maturity: { Name: m.Name, Mob: { Name: targetMobName } }
        });
      }
    }
    spawn.Maturities = mats;
    updateField(fieldPath, newList);
  }

  function deselectAllDialogMaturities() {
    if (!maturityDialog) return;
    const { spawnIndex, mobName: targetMobName } = maturityDialog;
    const newList = [...spawns];
    const spawn = newList[spawnIndex];
    spawn.Maturities = (spawn.Maturities || []).filter(
      m => (m.Maturity?.Mob?.Name || mobName) !== targetMobName
    );
    updateField(fieldPath, newList);
  }

  // === Utility ===
  function toggleSpawn(index) {
    expandedSpawns[index] = !expandedSpawns[index];
    expandedSpawns = expandedSpawns;
  }

  function getSpawnLabel(spawn, index) {
    let data = spawn.Properties?.Data;
    if (typeof data === 'string') {
      try { data = JSON.parse(data || '{}'); } catch (e) { data = {}; }
    }
    data = data || {};

    const x = data?.x ?? data?.X ?? spawn.X ?? spawn.Properties?.Coordinates?.X ?? 0;
    const y = data?.y ?? data?.Y ?? spawn.Y ?? spawn.Properties?.Coordinates?.Y ?? 0;

    const displayX = Number.isFinite(x) ? Math.round(x) : 0;
    const displayY = Number.isFinite(y) ? Math.round(y) : 0;

    return `Spawn ${index + 1} (${displayX}, ${displayY})`;
  }

  function getDensityLabel(value) {
    const opt = DENSITY_OPTIONS.find(o => o.value === value);
    return opt?.label || 'N/A';
  }

  /** Get unique mob names present in a spawn's maturities */
  function getSpawnMobNames(spawn) {
    const names = new Set();
    for (const entry of (spawn?.Maturities || [])) {
      names.add(entry.Maturity?.Mob?.Name || mobName);
    }
    return [...names];
  }

  /** Check if current mob has maturities at a spawn */
  function hasCurrentMob(spawn) {
    return (spawn?.Maturities || []).some(
      m => (m.Maturity?.Mob?.Name || mobName) === mobName
    );
  }
</script>

<div class="spawns-edit">
  <div class="section-header">
    <h4 class="section-title">Spawns ({spawns?.length || 0})</h4>
  </div>

  <div class="spawns-list">
    {#each spawns as spawn, spawnIndex}
      <div class="spawn-item" class:expanded={expandedSpawns[spawnIndex]}>
        <button
          class="spawn-header"
          on:click={() => toggleSpawn(spawnIndex)}
          type="button"
        >
          <span class="expand-icon">{expandedSpawns[spawnIndex] ? '▼' : '▶'}</span>
          <span class="spawn-name">{getSpawnLabel(spawn, spawnIndex)}</span>
          <span class="spawn-summary">
            <span class="density-badge density-{spawn.Properties?.Density || 3}">
              {getDensityLabel(spawn.Properties?.Density)}
            </span>
            {#if spawn.Properties?.IsEvent}
              <span class="event-badge">Event</span>
            {/if}
            {#if spawn.Properties?.IsShared}
              <span class="shared-badge">Shared</span>
            {/if}
          </span>
          <div class="spawn-actions">
            <button
              class="btn-icon danger"
              on:click|stopPropagation={() => removeSpawn(spawnIndex)}
              title="Remove spawn"
              type="button"
            >×</button>
          </div>
        </button>

        {#if expandedSpawns[spawnIndex]}
          <div class="spawn-content">
            <!-- General Fields -->
            <div class="field-group">
              <h5 class="group-title">General</h5>
              <div class="field-grid">
                <label class="field">
                  <span class="field-label">Shape</span>
                  <select
                    value={spawn.Properties?.Shape || 'Point'}
                    on:change={(e) => updateSpawnField(spawnIndex, 'Properties.Shape', e.target.value)}
                  >
                    {#each SHAPE_OPTIONS as shape}
                      <option value={shape}>{shape}</option>
                    {/each}
                  </select>
                </label>
                <label class="field">
                  <span class="field-label">Density</span>
                  <select
                    value={spawn.Properties?.Density || 3}
                    on:change={(e) => updateSpawnField(spawnIndex, 'Properties.Density', parseInt(e.target.value))}
                  >
                    {#each DENSITY_OPTIONS as opt}
                      <option value={opt.value}>{opt.label}</option>
                    {/each}
                  </select>
                </label>
                <label class="field checkbox-field">
                  <input
                    type="checkbox"
                    checked={spawn.Properties?.IsShared || false}
                    on:change={(e) => updateSpawnField(spawnIndex, 'Properties.IsShared', e.target.checked)}
                  />
                  <span class="field-label">Is Shared</span>
                </label>
                <label class="field checkbox-field">
                  <input
                    type="checkbox"
                    checked={spawn.Properties?.IsEvent || false}
                    on:change={(e) => updateSpawnField(spawnIndex, 'Properties.IsEvent', e.target.checked)}
                  />
                  <span class="field-label">Is Event</span>
                </label>
              </div>
            </div>

            <!-- Coordinates -->
            <div class="field-group">
              <h5 class="group-title">Coordinates</h5>
              {#if spawn.Properties?.Shape === 'Point'}
                <div class="waypoint-section">
                  <input
                    type="text"
                    class="waypoint-paste"
                    placeholder="Paste waypoint: [Planet, X, Y, Z, Name]"
                    on:change={(e) => handleWaypointPaste(spawnIndex, e)}
                  />
                  <div class="waypoint-display">
                    Current: {getWaypointDisplay(spawn)}
                  </div>
                  <div class="field-grid coords-manual">
                    <label class="field compact">
                      <span class="field-label-mini">X</span>
                      <input
                        type="number"
                        value={typeof spawn.Properties?.Data === 'string'
                          ? JSON.parse(spawn.Properties.Data || '{}').x || 0
                          : spawn.Properties?.Data?.x || 0}
                        on:input={(e) => {
                          const data = typeof spawn.Properties?.Data === 'string'
                            ? JSON.parse(spawn.Properties.Data || '{}')
                            : { ...spawn.Properties?.Data } || {};
                          data.x = parseFloat(e.target.value) || 0;
                          updateSpawnField(spawnIndex, 'Properties.Data', data);
                        }}
                      />
                    </label>
                    <label class="field compact">
                      <span class="field-label-mini">Y</span>
                      <input
                        type="number"
                        value={typeof spawn.Properties?.Data === 'string'
                          ? JSON.parse(spawn.Properties.Data || '{}').y || 0
                          : spawn.Properties?.Data?.y || 0}
                        on:input={(e) => {
                          const data = typeof spawn.Properties?.Data === 'string'
                            ? JSON.parse(spawn.Properties.Data || '{}')
                            : { ...spawn.Properties?.Data } || {};
                          data.y = parseFloat(e.target.value) || 0;
                          updateSpawnField(spawnIndex, 'Properties.Data', data);
                        }}
                      />
                    </label>
                    <label class="field compact">
                      <span class="field-label-mini">Z (Alt)</span>
                      <input
                        type="number"
                        value={spawn.Properties?.Coordinates?.Altitude || 0}
                        on:input={(e) => updateSpawnField(spawnIndex, 'Properties.Coordinates.Altitude', parseFloat(e.target.value) || 0)}
                      />
                    </label>
                  </div>
                </div>
              {:else}
                <div class="field-grid">
                  <label class="field full-width">
                    <span class="field-label">Shape Data (JSON)</span>
                    <textarea
                      value={typeof spawn.Properties?.Data === 'string'
                        ? spawn.Properties.Data
                        : JSON.stringify(spawn.Properties?.Data || {}, null, 2)}
                      on:input={(e) => {
                        try {
                          const parsed = JSON.parse(e.target.value);
                          updateSpawnField(spawnIndex, 'Properties.Data', parsed);
                        } catch (err) {
                          updateSpawnField(spawnIndex, 'Properties.Data', e.target.value);
                        }
                      }}
                      rows="4"
                    />
                  </label>
                  <label class="field">
                    <span class="field-label">Altitude</span>
                    <input
                      type="number"
                      value={spawn.Properties?.Coordinates?.Altitude || 0}
                      on:input={(e) => updateSpawnField(spawnIndex, 'Properties.Coordinates.Altitude', parseFloat(e.target.value) || 0)}
                    />
                  </label>
                </div>
              {/if}
            </div>

            <!-- Mobs at Spawn -->
            <div class="field-group">
              <h5 class="group-title">Mobs at Spawn ({spawn.Maturities?.length || 0} maturities)</h5>

              <div class="mob-entries">
                <!-- Current mob entry (always shown if it has maturities, or as "add" prompt) -->
                {#if hasCurrentMob(spawn)}
                  <div class="mob-entry">
                    <div class="mob-entry-header">
                      <span class="mob-entry-name">{mobName} <span class="current-badge">current</span></span>
                      <div class="mob-entry-actions">
                        <button
                          class="configure-btn"
                          on:click={() => openMaturityDialog(spawnIndex, mobName)}
                          type="button"
                        >
                          Configure ({getSelectedCount(spawn, mobName)}/{getTotalCount(mobName)})
                        </button>
                        <button
                          class="btn-icon danger small"
                          on:click={() => removeMobFromSpawn(spawnIndex, mobName)}
                          title="Remove all maturities of this mob"
                          type="button"
                        >×</button>
                      </div>
                    </div>
                  </div>
                {:else}
                  <button
                    class="btn-add-mob"
                    on:click={() => addCurrentMobToSpawn(spawnIndex)}
                    type="button"
                  >
                    <span>+</span> Add {mobName} (current mob)
                  </button>
                {/if}

                <!-- Other mob entries -->
                {#each getSpawnMobNames(spawn).filter(n => n !== mobName) as otherMobName}
                  <div class="mob-entry other">
                    <div class="mob-entry-header">
                      <span class="mob-entry-name">{otherMobName}</span>
                      <div class="mob-entry-actions">
                        <button
                          class="configure-btn"
                          on:click={() => openMaturityDialog(spawnIndex, otherMobName)}
                          type="button"
                        >
                          Configure ({getSelectedCount(spawn, otherMobName)}/{getTotalCount(otherMobName)})
                        </button>
                        <button
                          class="btn-icon danger small"
                          on:click={() => removeMobFromSpawn(spawnIndex, otherMobName)}
                          title="Remove mob"
                          type="button"
                        >×</button>
                      </div>
                    </div>
                  </div>
                {/each}

                <!-- Add other mob search -->
                <div class="mob-search-wrap">
                  <SearchInput
                    value=""
                    options={mobSearchOptions}
                    placeholder="Search to add another mob..."
                    clearOnSelect
                    filterFn={getMobSearchFilter(spawn)}
                    on:select={(e) => addMobToSpawn(spawnIndex, e.detail.value)}
                  />
                </div>
              </div>
            </div>
          </div>
        {/if}
      </div>
    {/each}

    <button class="btn-add" on:click={addSpawn} type="button">
      <span>+</span> Add Spawn
    </button>
  </div>
</div>

<!-- Maturity Configuration Dialog -->
{#if maturityDialog}
  <div class="dialog-overlay" role="presentation" on:click={closeMaturityDialog}>
    <div class="maturity-dialog" role="dialog" on:click|stopPropagation>
      <div class="dialog-header">
        <h3>{maturityDialog.mobName}</h3>
        <button class="dialog-close" on:click={closeMaturityDialog} type="button">×</button>
      </div>

      <div class="dialog-actions">
        <button on:click={selectAllDialogMaturities} type="button">All</button>
        <button on:click={deselectAllDialogMaturities} type="button">None</button>
      </div>

      <div class="dialog-content">
        {#if dialogEntries.length === 0}
          <div class="dialog-empty">No maturities found for this mob.</div>
        {:else}
          <div class="mat-list-header">
            <span></span>
            <span>Maturity</span>
            <span>Lv / HP</span>
            <span>Rare</span>
          </div>
          {#each dialogEntries as mat (mat.name)}
            <div class="mat-row" class:disabled={!mat.selected} class:boss={mat.boss}>
              <label>
                <input
                  type="checkbox"
                  checked={mat.selected}
                  on:change={() => toggleDialogMaturity(mat.name)}
                />
              </label>
              <span class="mat-name">
                {mat.name}
                {#if mat.boss}
                  <span class="boss-badge">Boss</span>
                {/if}
              </span>
              <span class="mat-stats">
                {mat.level ?? '?'} / {mat.health ?? '?'}
              </span>
              <div class="rare-toggle">
                {#if mat.selected}
                  <button
                    class="rare-btn"
                    class:active={mat.isRare}
                    on:click={() => toggleDialogRare(mat.name)}
                    title="Toggle rare spawn"
                    type="button"
                  >R</button>
                {/if}
              </div>
            </div>
          {/each}
        {/if}
      </div>

      <div class="dialog-footer">
        <button on:click={closeMaturityDialog} type="button">Done</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .spawns-edit {
    width: 100%;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .section-title {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  .spawns-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .spawn-item {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    overflow: hidden;
  }

  .spawn-item.expanded {
    border-color: var(--accent-color, #4a9eff);
  }

  .spawn-header {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 6px 10px;
    background: none;
    border: none;
    color: var(--text-color);
    cursor: pointer;
    text-align: left;
    font-size: 12px;
    transition: background-color 0.15s;
  }

  .spawn-header:hover {
    background-color: var(--hover-color);
  }

  .expand-icon {
    font-size: 9px;
    color: var(--text-muted, #999);
    width: 12px;
    flex-shrink: 0;
  }

  .spawn-name {
    font-weight: 600;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .spawn-summary {
    display: flex;
    gap: 4px;
    align-items: center;
    flex-shrink: 0;
  }

  .density-badge,
  .event-badge,
  .shared-badge {
    font-size: 9px;
    padding: 1px 4px;
    border-radius: 2px;
    font-weight: 500;
  }

  .density-badge.density-1 {
    background-color: rgba(148, 163, 184, 0.25);
    color: #94a3b8;
  }

  .density-badge.density-2 {
    background-color: rgba(202, 138, 4, 0.25);
    color: #eab308;
  }

  .density-badge.density-3 {
    background-color: rgba(22, 163, 74, 0.25);
    color: #22c55e;
  }

  .density-badge.density-4 {
    background-color: rgba(220, 38, 38, 0.25);
    color: #ef4444;
  }

  .density-badge.density-5 {
    background-color: rgba(168, 85, 247, 0.25);
    color: #a855f7;
  }

  .event-badge {
    background-color: var(--warning-bg, rgba(251, 191, 36, 0.15));
    color: var(--warning-color, #fbbf24);
  }

  .shared-badge {
    background-color: rgba(74, 158, 255, 0.15);
    color: var(--accent-color, #4a9eff);
  }

  .spawn-actions {
    display: flex;
    gap: 2px;
    margin-left: 4px;
    flex-shrink: 0;
  }

  .spawn-content {
    padding: 10px;
    border-top: 1px solid var(--border-color, #555);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .group-title {
    margin: 0;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .field-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
    align-items: end;
  }

  .field-grid.coords-manual {
    grid-template-columns: repeat(3, 1fr);
    margin-top: 6px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .field.compact {
    gap: 1px;
  }

  .field.full-width {
    grid-column: 1 / -1;
  }

  .field-label {
    font-size: 12px;
    color: var(--text-muted, #999);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .field-label-mini {
    font-size: 11px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
  }

  .field input[type="number"],
  .field select,
  .field textarea {
    padding: 4px 6px;
    font-size: 12px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-color);
    width: 100%;
    font-family: inherit;
    box-sizing: border-box;
    height: 26px;
  }

  .field textarea {
    height: auto;
    min-height: 60px;
  }

  .field select option {
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
  }

  .field input:focus,
  .field select:focus,
  .field textarea:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .checkbox-field {
    flex-direction: row;
    align-items: center;
    gap: 4px;
    height: 26px;
    justify-content: flex-start;
  }

  .checkbox-field input[type="checkbox"] {
    width: 14px;
    height: 14px;
    cursor: pointer;
    flex-shrink: 0;
  }

  /* Waypoint section */
  .waypoint-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .waypoint-paste {
    padding: 6px 8px;
    font-size: 11px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px dashed var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-color);
    height: 28px;
    box-sizing: border-box;
  }

  .waypoint-paste::placeholder {
    color: var(--text-muted, #999);
  }

  .waypoint-display {
    font-size: 11px;
    color: var(--text-muted, #999);
    font-family: monospace;
  }

  /* Mob entries */
  .mob-entries {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .mob-entry {
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    overflow: hidden;
  }

  .mob-entry.other {
    background-color: rgba(74, 158, 255, 0.05);
    border-color: rgba(74, 158, 255, 0.3);
  }

  .mob-entry-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 8px;
    background: var(--secondary-color);
    gap: 8px;
  }

  .mob-entry-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .current-badge {
    font-size: 9px;
    font-weight: 500;
    color: var(--text-muted, #999);
    padding: 1px 4px;
    border: 1px solid var(--border-color, #555);
    border-radius: 2px;
    vertical-align: middle;
  }

  .mob-entry-actions {
    display: flex;
    gap: 4px;
    align-items: center;
    flex-shrink: 0;
  }

  .configure-btn {
    padding: 4px 10px;
    border: 1px solid var(--accent-color, #4a9eff);
    border-radius: 4px;
    background: rgba(59, 130, 246, 0.1);
    color: var(--accent-color, #4a9eff);
    font-size: 11px;
    cursor: pointer;
    text-align: center;
    white-space: nowrap;
  }

  .configure-btn:hover {
    background: rgba(59, 130, 246, 0.2);
  }

  .btn-add-mob {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 6px 10px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    font-size: 11px;
    line-height: 1;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-add-mob:hover {
    background-color: var(--hover-color);
    color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
  }

  /* Mob search */
  .mob-search-wrap {
    position: relative;
  }

  /* Buttons */
  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    background: none;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .btn-icon:hover:not(:disabled) {
    background-color: var(--hover-color);
    color: var(--text-color);
    border-color: var(--text-color);
  }

  .btn-icon.danger:hover:not(:disabled) {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  .btn-icon.small {
    width: 18px;
    height: 18px;
    font-size: 12px;
  }

  .btn-add {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 6px 10px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    font-size: 11px;
    line-height: 1;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-add:hover {
    background-color: var(--hover-color);
    color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
  }

  /* Dialog styles */
  .dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .maturity-dialog {
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    width: 90%;
    max-width: 460px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .dialog-close {
    background: none;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 16px;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
  }

  .dialog-close:hover {
    background: var(--hover-color);
    color: var(--text-color);
  }

  .dialog-actions {
    display: flex;
    gap: 4px;
    padding: 8px 16px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .dialog-actions button {
    font-size: 11px;
    padding: 3px 8px;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    background: var(--primary-color);
    color: var(--text-muted, #999);
    cursor: pointer;
  }

  .dialog-actions button:hover {
    background: var(--hover-color);
  }

  .dialog-content {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
  }

  .mat-list-header {
    display: grid;
    grid-template-columns: 40px 1fr 70px 45px;
    gap: 6px;
    padding: 6px 16px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: var(--text-muted, #999);
    background: var(--primary-color);
    border-bottom: 1px solid var(--border-color, #555);
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .mat-row {
    display: grid;
    grid-template-columns: 40px 1fr 70px 45px;
    gap: 6px;
    padding: 5px 16px;
    align-items: center;
    border-bottom: 1px solid var(--border-color, #555);
    font-size: 12px;
    color: var(--text-color);
  }

  .mat-row:hover {
    background: var(--hover-color);
  }

  .mat-row.disabled {
    opacity: 0.5;
  }

  .mat-row.boss {
    background: rgba(255, 193, 7, 0.08);
  }

  .mat-row.boss:hover {
    background: rgba(255, 193, 7, 0.15);
  }

  .mat-row input[type="checkbox"] {
    width: 14px;
    height: 14px;
    cursor: pointer;
    margin: 0;
  }

  .mat-name {
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .boss-badge {
    font-size: 9px;
    padding: 1px 4px;
    background: var(--warning-color, #ffc107);
    color: #000;
    border-radius: 3px;
    font-weight: 600;
    flex-shrink: 0;
  }

  .mat-stats {
    font-family: monospace;
    font-size: 11px;
    color: var(--text-muted, #999);
  }

  .rare-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .rare-btn {
    font-size: 10px;
    padding: 1px 5px;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    background: transparent;
    color: var(--text-muted, #999);
    cursor: pointer;
  }

  .rare-btn.active {
    background: rgba(234, 179, 8, 0.2);
    border-color: #eab308;
    color: #eab308;
    font-weight: 600;
  }

  .dialog-footer {
    padding: 10px 16px;
    border-top: 1px solid var(--border-color, #555);
    display: flex;
    justify-content: flex-end;
  }

  .dialog-footer button {
    padding: 6px 16px;
    border: none;
    border-radius: 4px;
    background: var(--accent-color, #4a9eff);
    color: white;
    font-size: 12px;
    cursor: pointer;
  }

  .dialog-footer button:hover {
    opacity: 0.9;
  }

  .dialog-empty {
    padding: 20px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 12px;
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .spawn-summary {
      display: none;
    }

    .field-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .mob-entry-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 4px;
    }

    .mob-entry-actions {
      width: 100%;
    }

    .configure-btn {
      flex: 1;
    }
  }
</style>
