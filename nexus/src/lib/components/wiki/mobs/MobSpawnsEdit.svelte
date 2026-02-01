<!--
  @component MobSpawnsEdit
  Array editor for mob spawn locations.
  Supports waypoint paste, shape configuration, density, and nested maturities.
  Following the editConfig pattern from mobs-legacy.
-->
<script>
  // @ts-nocheck
  import { editMode, updateField, currentEntity } from '$lib/stores/wikiEditState.js';

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
    { value: 1, label: 'Low' },
    { value: 2, label: 'Medium' },
    { value: 3, label: 'High' }
  ];

  // Track which spawn panels are expanded
  let expandedSpawns = {};

  // === Spawn Constructor ===
  function createSpawn() {
    return {
      Properties: {
        Density: 2,
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

  // === Spawn Maturity Constructor ===
  function createSpawnMaturity() {
    return {
      IsRare: false,
      Maturity: {
        Name: maturities[0]?.Name || null,
        Mob: {
          Name: mobName
        }
      }
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

  // === Spawn Maturity Operations ===
  function addSpawnMaturity(spawnIndex) {
    const newList = [...spawns];
    const mats = newList[spawnIndex].Maturities || [];
    mats.push(createSpawnMaturity());
    newList[spawnIndex].Maturities = mats;
    updateField(fieldPath, newList);
  }

  function removeSpawnMaturity(spawnIndex, matIndex) {
    const newList = [...spawns];
    newList[spawnIndex].Maturities = newList[spawnIndex].Maturities.filter((_, i) => i !== matIndex);
    updateField(fieldPath, newList);
  }

  function updateSpawnMaturity(spawnIndex, matIndex, field, value) {
    const newList = [...spawns];
    const mat = newList[spawnIndex].Maturities[matIndex];

    if (field === 'Mob.Name') {
      if (!mat.Maturity) mat.Maturity = {};
      if (!mat.Maturity.Mob) mat.Maturity.Mob = {};
      mat.Maturity.Mob.Name = value;
      // Reset maturity name when mob changes
      mat.Maturity.Name = null;
    } else if (field === 'Maturity.Name') {
      if (!mat.Maturity) mat.Maturity = {};
      mat.Maturity.Name = value;
    } else if (field === 'IsRare') {
      mat.IsRare = value;
    }

    updateField(fieldPath, newList);
  }

  // Get maturities for a selected mob
  function getMaturitiesForMob(selectedMobName) {
    if (selectedMobName === mobName) {
      return maturities;
    }
    const mob = allMobs?.find(m => m.Name === selectedMobName);
    return mob?.Maturities || [];
  }

  function toggleSpawn(index) {
    expandedSpawns[index] = !expandedSpawns[index];
    expandedSpawns = expandedSpawns;
  }

  function getSpawnLabel(spawn, index) {
    // Try multiple data formats
    let data = spawn.Properties?.Data;
    if (typeof data === 'string') {
      try { data = JSON.parse(data || '{}'); } catch (e) { data = {}; }
    }
    data = data || {};

    // Also check for X/Y directly on spawn or in Coordinates
    const x = data?.x ?? data?.X ?? spawn.X ?? spawn.Properties?.Coordinates?.X ?? 0;
    const y = data?.y ?? data?.Y ?? spawn.Y ?? spawn.Properties?.Coordinates?.Y ?? 0;

    // Format with Math.round for cleaner display
    const displayX = Number.isFinite(x) ? Math.round(x) : 0;
    const displayY = Number.isFinite(y) ? Math.round(y) : 0;

    return `Spawn ${index + 1} (${displayX}, ${displayY})`;
  }

  function getDensityLabel(value) {
    const opt = DENSITY_OPTIONS.find(o => o.value === value);
    return opt?.label || 'N/A';
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
            <span class="density-badge density-{spawn.Properties?.Density || 2}">
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
                    value={spawn.Properties?.Density || 2}
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

            <!-- Maturities at Spawn -->
            <div class="field-group">
              <h5 class="group-title">Maturities at Spawn ({spawn.Maturities?.length || 0})</h5>
              <div class="spawn-maturities-list">
                {#each spawn.Maturities || [] as spawnMat, matIndex}
                  <div class="spawn-maturity-item" class:other-mob={spawnMat.Maturity?.Mob?.Name && spawnMat.Maturity.Mob.Name !== mobName}>
                    <div class="spawn-mat-fields">
                      <label class="field">
                        <span class="field-label">Mob</span>
                        <select
                          value={spawnMat.Maturity?.Mob?.Name || mobName}
                          on:change={(e) => updateSpawnMaturity(spawnIndex, matIndex, 'Mob.Name', e.target.value)}
                        >
                          <option value={mobName}>{mobName} (current)</option>
                          {#each (allMobs || []).filter(m => m.Name !== mobName) as otherMob}
                            <option value={otherMob.Name}>{otherMob.Name}</option>
                          {/each}
                        </select>
                      </label>
                      <label class="field">
                        <span class="field-label">Maturity</span>
                        <select
                          value={spawnMat.Maturity?.Name || ''}
                          on:change={(e) => updateSpawnMaturity(spawnIndex, matIndex, 'Maturity.Name', e.target.value)}
                        >
                          <option value="">-- Select --</option>
                          {#each getMaturitiesForMob(spawnMat.Maturity?.Mob?.Name || mobName) as mat}
                            <option value={mat.Name}>{mat.Name}</option>
                          {/each}
                        </select>
                      </label>
                      <label class="field checkbox-field">
                        <input
                          type="checkbox"
                          checked={spawnMat.IsRare || false}
                          on:change={(e) => updateSpawnMaturity(spawnIndex, matIndex, 'IsRare', e.target.checked)}
                        />
                        <span class="field-label">Rare</span>
                      </label>
                    </div>
                    <button
                      class="btn-icon danger small"
                      on:click={() => removeSpawnMaturity(spawnIndex, matIndex)}
                      title="Remove maturity"
                      type="button"
                    >×</button>
                  </div>
                {/each}
                <button class="btn-add" on:click={() => addSpawnMaturity(spawnIndex)} type="button">
                  <span>+</span> Add Maturity
                </button>
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
    background-color: rgba(202, 138, 4, 0.25);
    color: #eab308;
  }

  .density-badge.density-2 {
    background-color: rgba(22, 163, 74, 0.25);
    color: #22c55e;
  }

  .density-badge.density-3 {
    background-color: rgba(220, 38, 38, 0.25);
    color: #ef4444;
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

  .field input[type="text"],
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

  /* Spawn maturities */
  .spawn-maturities-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .spawn-maturity-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
  }

  .spawn-maturity-item.other-mob {
    background-color: rgba(74, 158, 255, 0.1);
    border-color: rgba(74, 158, 255, 0.3);
  }

  .spawn-mat-fields {
    display: flex;
    gap: 6px;
    flex: 1;
    align-items: flex-end;
    flex-wrap: wrap;
  }

  .spawn-mat-fields .field {
    flex: 1;
    min-width: 80px;
    max-width: 150px;
  }

  .spawn-mat-fields .checkbox-field {
    flex: 0 0 auto;
    min-width: auto;
    max-width: none;
    height: 28px;
    margin-bottom: 0;
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

  .btn-add.primary {
    margin-top: 4px;
    padding: 8px 12px;
    font-size: 12px;
    border-style: solid;
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .btn-add.primary:hover {
    opacity: 0.9;
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .spawn-summary {
      display: none;
    }

    .field-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .spawn-mat-fields {
      flex-direction: column;
      align-items: stretch;
    }

    .spawn-mat-fields .field {
      max-width: none;
      width: 100%;
    }
  }
</style>
