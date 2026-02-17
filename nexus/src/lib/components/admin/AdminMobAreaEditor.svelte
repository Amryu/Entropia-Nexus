<script>
  // @ts-nocheck
  import { createEventDispatcher, onMount } from 'svelte';
  import { generateMobAreaName } from './adminMapUtils.js';

  export let mobs = [];          // All mobs from /mobs (cached by parent)
  export let location = null;    // Existing MobArea location (if editing)
  export let isNew = false;

  const dispatch = createEventDispatcher();

  let mobSearch = '';
  let mobSearchResults = [];
  let selectedMobs = [];  // [{ mobId, mobName, maturities: [{ id, name, health, selected, isRare }] }]
  let density = 3;
  let autoName = '';
  let nameOverride = '';
  let loadingMaturities = {};

  // If editing an existing mob area, populate from its spawn data
  $: if (location && !isNew && mobs.length) {
    initFromExisting();
  }

  function initFromExisting() {
    if (!location?.Properties?.Maturities) return;
    // Group existing maturities by mob
    const matsByMob = new Map();
    for (const mat of (location.Properties.Maturities || [])) {
      const mobName = mat.Mob?.Name || 'Unknown';
      const mobId = mat.Mob?.Id || 0;
      if (!matsByMob.has(mobId)) {
        matsByMob.set(mobId, { mobId, mobName, maturities: [] });
      }
      matsByMob.get(mobId).maturities.push({
        id: mat.Id,
        name: mat.Name,
        health: mat.Health || 0,
        selected: true,
        isRare: mat.IsRare || false
      });
    }
    selectedMobs = Array.from(matsByMob.values());
    density = location.Properties?.Density ?? 3;
    nameOverride = location.Name || '';
  }

  // Search mobs
  $: {
    if (mobSearch.trim().length >= 2) {
      const q = mobSearch.trim().toLowerCase();
      mobSearchResults = mobs
        .filter(m => m.Name?.toLowerCase().includes(q))
        .filter(m => !selectedMobs.some(s => s.mobId === m.Id))
        .slice(0, 20);
    } else {
      mobSearchResults = [];
    }
  }

  // Auto-generate name
  $: {
    const entries = selectedMobs.map(m => ({
      mobName: m.mobName,
      maturities: m.maturities.filter(mat => mat.selected).map(mat => ({ name: mat.name, health: mat.health }))
    })).filter(e => e.maturities.length > 0);
    autoName = generateMobAreaName(entries);
  }

  $: effectiveName = nameOverride || autoName;

  async function addMob(mob) {
    mobSearch = '';
    mobSearchResults = [];
    const entry = { mobId: mob.Id, mobName: mob.Name, maturities: [] };
    selectedMobs = [...selectedMobs, entry];
    await loadMaturitiesForMob(entry);
  }

  async function loadMaturitiesForMob(entry) {
    if (loadingMaturities[entry.mobId]) return;
    loadingMaturities[entry.mobId] = true;
    loadingMaturities = loadingMaturities;

    try {
      const res = await fetch(`/api/proxy/mobs/${entry.mobId}`);
      if (!res.ok) throw new Error('Failed to fetch mob');
      const data = await res.json();
      const mats = (data.Maturities || []).map(m => ({
        id: m.Id,
        name: m.Name,
        health: m.Properties?.Health ?? m.Health ?? 0,
        selected: false,
        isRare: false
      })).sort((a, b) => a.health - b.health);

      selectedMobs = selectedMobs.map(m =>
        m.mobId === entry.mobId ? { ...m, maturities: mats } : m
      );
    } catch (e) {
      console.error('Failed to load maturities for mob:', entry.mobName, e);
    } finally {
      loadingMaturities[entry.mobId] = false;
      loadingMaturities = loadingMaturities;
    }
  }

  function removeMob(mobId) {
    selectedMobs = selectedMobs.filter(m => m.mobId !== mobId);
  }

  function toggleMaturity(mobId, matId) {
    selectedMobs = selectedMobs.map(m => {
      if (m.mobId !== mobId) return m;
      return {
        ...m,
        maturities: m.maturities.map(mat =>
          mat.id === matId ? { ...mat, selected: !mat.selected } : mat
        )
      };
    });
  }

  function toggleRare(mobId, matId) {
    selectedMobs = selectedMobs.map(m => {
      if (m.mobId !== mobId) return m;
      return {
        ...m,
        maturities: m.maturities.map(mat =>
          mat.id === matId ? { ...mat, isRare: !mat.isRare } : mat
        )
      };
    });
  }

  function selectAllMaturities(mobId) {
    selectedMobs = selectedMobs.map(m => {
      if (m.mobId !== mobId) return m;
      return { ...m, maturities: m.maturities.map(mat => ({ ...mat, selected: true })) };
    });
  }

  function deselectAllMaturities(mobId) {
    selectedMobs = selectedMobs.map(m => {
      if (m.mobId !== mobId) return m;
      return { ...m, maturities: m.maturities.map(mat => ({ ...mat, selected: false })) };
    });
  }

  function handleSave() {
    const maturityList = [];
    for (const mob of selectedMobs) {
      for (const mat of mob.maturities) {
        if (mat.selected) {
          maturityList.push({ maturityId: mat.id, isRare: mat.isRare });
        }
      }
    }

    dispatch('save', {
      name: effectiveName,
      density,
      maturities: maturityList
    });
  }

  function handleCancel() {
    dispatch('cancel');
  }
</script>

<style>
  .mob-editor {
    display: flex;
    flex-direction: column;
    gap: 10px;
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
  .field-input:focus { outline: none; border-color: var(--accent-color); }

  .auto-name {
    font-size: 11px;
    color: var(--text-muted);
    word-break: break-all;
  }

  .mob-search-wrap {
    position: relative;
  }

  .mob-results {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    max-height: 200px;
    overflow-y: auto;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    z-index: 10;
  }

  .mob-result {
    padding: 6px 8px;
    font-size: 12px;
    cursor: pointer;
    color: var(--text-color);
  }
  .mob-result:hover { background: var(--hover-color); }

  .mob-entry {
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .mob-entry-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 8px;
    background: var(--secondary-color);
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  .mob-entry-header button {
    font-size: 11px;
    padding: 2px 6px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
  }
  .mob-entry-header button:hover { background: var(--hover-color); }
  .mob-entry-header .remove-btn { color: #ef4444; border-color: #ef4444; }

  .mat-actions {
    display: flex;
    gap: 4px;
    padding: 4px 8px;
    border-bottom: 1px solid var(--border-color);
  }
  .mat-actions button {
    font-size: 10px;
    padding: 2px 6px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background: var(--primary-color);
    color: var(--text-muted);
    cursor: pointer;
  }

  .mat-list {
    padding: 4px 8px;
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .mat-chip {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 6px;
    border: 1px solid var(--border-color);
    border-radius: 12px;
    font-size: 11px;
    cursor: pointer;
    color: var(--text-muted);
    background: transparent;
  }
  .mat-chip.selected {
    background: rgba(59, 130, 246, 0.2);
    border-color: var(--accent-color);
    color: var(--text-color);
  }
  .mat-chip .rare-badge {
    font-size: 9px;
    color: #eab308;
    cursor: pointer;
    padding: 0 2px;
  }

  .mat-loading {
    padding: 8px;
    font-size: 11px;
    color: var(--text-muted);
    text-align: center;
  }

  .density-row {
    display: flex;
    gap: 4px;
    align-items: center;
  }

  .density-btn {
    padding: 4px 10px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    background: var(--primary-color);
    color: var(--text-muted);
  }
  .density-btn.active { background: var(--accent-color); color: white; border-color: var(--accent-color); }

  .actions {
    display: flex;
    gap: 4px;
    margin-top: 8px;
  }

  .btn {
    flex: 1;
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
  .btn-primary { background: var(--accent-color); color: white; border-color: var(--accent-color); }
</style>

<div class="mob-editor">
  <h3 class="editor-title">Mob Area Editor</h3>

  <div class="field-group">
    <span class="field-label">Generated Name</span>
    <div class="auto-name">{autoName || '(select mobs and maturities)'}</div>
    <input class="field-input" type="text" bind:value={nameOverride} placeholder="Override name (optional)" />
  </div>

  <div class="field-group">
    <span class="field-label">Density</span>
    <div class="density-row">
      <button class="density-btn" class:active={density === 1} on:click={() => density = 1}>1 Low</button>
      <button class="density-btn" class:active={density === 2} on:click={() => density = 2}>2 Med</button>
      <button class="density-btn" class:active={density === 3} on:click={() => density = 3}>3 High</button>
    </div>
  </div>

  <div class="field-group">
    <span class="field-label">Add Mob</span>
    <div class="mob-search-wrap">
      <input class="field-input" type="text" bind:value={mobSearch} placeholder="Search mobs..." />
      {#if mobSearchResults.length > 0}
        <div class="mob-results">
          {#each mobSearchResults as mob}
            <div class="mob-result" on:click={() => addMob(mob)} on:keydown={(e) => e.key === 'Enter' && addMob(mob)} role="button" tabindex="0">
              {mob.Name}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>

  {#each selectedMobs as mob}
    <div class="mob-entry">
      <div class="mob-entry-header">
        <span>{mob.mobName}</span>
        <div style="display:flex;gap:4px">
          <button class="remove-btn" on:click={() => removeMob(mob.mobId)}>Remove</button>
        </div>
      </div>
      {#if loadingMaturities[mob.mobId]}
        <div class="mat-loading">Loading maturities...</div>
      {:else if mob.maturities.length > 0}
        <div class="mat-actions">
          <button on:click={() => selectAllMaturities(mob.mobId)}>All</button>
          <button on:click={() => deselectAllMaturities(mob.mobId)}>None</button>
        </div>
        <div class="mat-list">
          {#each mob.maturities as mat}
            <button
              class="mat-chip"
              class:selected={mat.selected}
              on:click={() => toggleMaturity(mob.mobId, mat.id)}
              title="HP: {mat.health}"
            >
              {mat.name}
              {#if mat.selected}
                <!-- svelte-ignore a11y-click-events-have-key-events -->
                <span class="rare-badge" on:click|stopPropagation={() => toggleRare(mob.mobId, mat.id)} title="Toggle rare">
                  {mat.isRare ? 'R' : 'r'}
                </span>
              {/if}
            </button>
          {/each}
        </div>
      {:else}
        <div class="mat-loading">No maturities found</div>
      {/if}
    </div>
  {/each}

  <div class="actions">
    <button class="btn btn-primary" on:click={handleSave}>Save Mob Data</button>
    <button class="btn" on:click={handleCancel}>Cancel</button>
  </div>
</div>
