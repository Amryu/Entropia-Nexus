<script>
  // @ts-nocheck
  import { createEventDispatcher, onMount } from 'svelte';
  import { generateMobAreaName } from './adminMapUtils.js';
  import { formatMobSpawnDisplayName } from '$lib/mapUtil.js';

  export let mobs = [];          // All mobs from /mobs (cached by parent)
  export let location = null;    // Existing MobArea location (if editing)
  export let isNew = false;

  const dispatch = createEventDispatcher();

  let mobSearch = '';
  let mobSearchResults = [];
  let selectedMobs = [];  // [{ mobId, mobName, maturities: [{ id, name, health, level, boss, selected, isRare }] }]
  let density = 3;
  let autoName = '';
  let nameOverride = '';
  let loadingMaturities = {};
  let maturityDialog = null; // { mobId } when dialog is open

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
        level: mat.Level ?? mat.Properties?.Level ?? null,
        boss: mat.Properties?.Boss === true || mat.Boss === true,
        selected: true,
        isRare: mat.IsRare || false
      });
    }
    selectedMobs = Array.from(matsByMob.values());
    // Sort maturities within each mob
    for (const mob of selectedMobs) {
      sortMaturities(mob.maturities);
    }
    density = location.Properties?.Density ?? 3;
    nameOverride = location.Name || '';
  }

  function sortMaturities(mats) {
    mats.sort((a, b) => {
      // Bosses at bottom
      if (a.boss !== b.boss) return a.boss ? 1 : -1;
      // Level ascending (nulls at end)
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

  // Auto-generate name (DB format stays same)
  $: {
    const entries = selectedMobs.map(m => ({
      mobName: m.mobName,
      maturities: m.maturities.filter(mat => mat.selected).map(mat => ({ name: mat.name, health: mat.health }))
    })).filter(e => e.maturities.length > 0);
    autoName = generateMobAreaName(entries);
  }

  // Display name (simplified format)
  $: displayName = autoName ? formatMobSpawnDisplayName(autoName) : '';

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
        level: m.Properties?.Level ?? null,
        boss: m.Properties?.Boss === true,
        selected: false,
        isRare: false
      }));
      sortMaturities(mats);

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
    if (maturityDialog?.mobId === mobId) maturityDialog = null;
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

  function getSelectedCount(mob) {
    return mob.maturities.filter(m => m.selected).length;
  }

  function openMaturityDialog(mobId) {
    maturityDialog = { mobId };
  }

  function closeMaturityDialog() {
    maturityDialog = null;
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

  $: dialogMob = maturityDialog ? selectedMobs.find(m => m.mobId === maturityDialog.mobId) : null;
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

  .name-display {
    font-size: 12px;
    color: var(--text-color);
    word-break: break-all;
    font-weight: 500;
  }

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

  .mob-entry-actions {
    display: flex;
    gap: 4px;
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

  .mob-entry-body {
    padding: 6px 8px;
    border-top: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .configure-btn {
    flex: 1;
    padding: 6px 10px;
    border: 1px solid var(--accent-color);
    border-radius: 4px;
    background: rgba(59, 130, 246, 0.1);
    color: var(--accent-color);
    font-size: 12px;
    cursor: pointer;
    text-align: center;
  }
  .configure-btn:hover { background: rgba(59, 130, 246, 0.2); }
  .configure-btn:disabled { opacity: 0.5; cursor: default; }

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
    border: 1px solid var(--border-color);
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
    border-bottom: 1px solid var(--border-color);
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .dialog-close {
    background: none;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 16px;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
  }
  .dialog-close:hover { background: var(--hover-color); color: var(--text-color); }

  .dialog-actions {
    display: flex;
    gap: 4px;
    padding: 8px 16px;
    border-bottom: 1px solid var(--border-color);
  }

  .dialog-actions button {
    font-size: 11px;
    padding: 3px 8px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background: var(--primary-color);
    color: var(--text-muted);
    cursor: pointer;
  }
  .dialog-actions button:hover { background: var(--hover-color); }

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
    color: var(--text-muted);
    background: var(--primary-color);
    border-bottom: 1px solid var(--border-color);
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
    border-bottom: 1px solid var(--border-color);
    font-size: 12px;
    color: var(--text-color);
  }
  .mat-row:hover { background: var(--hover-color); }
  .mat-row.disabled { opacity: 0.5; }
  .mat-row.boss { background: rgba(255, 193, 7, 0.08); }
  .mat-row.boss:hover { background: rgba(255, 193, 7, 0.15); }

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
    color: var(--text-muted);
  }

  .rare-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .rare-btn {
    font-size: 10px;
    padding: 1px 5px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background: transparent;
    color: var(--text-muted);
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
    border-top: 1px solid var(--border-color);
    display: flex;
    justify-content: flex-end;
  }

  .dialog-footer button {
    padding: 6px 16px;
    border: none;
    border-radius: 4px;
    background: var(--accent-color);
    color: white;
    font-size: 12px;
    cursor: pointer;
  }
  .dialog-footer button:hover { opacity: 0.9; }

  .dialog-empty {
    padding: 20px;
    text-align: center;
    color: var(--text-muted);
    font-size: 12px;
  }
</style>

<div class="mob-editor">
  <h3 class="editor-title">Mob Area Editor</h3>

  <div class="field-group">
    <span class="field-label">Display Name</span>
    <div class="name-display">{displayName || '(select mobs and maturities)'}</div>
    <span class="field-label" style="margin-top: 4px;">DB Name</span>
    <div class="auto-name">{autoName || '—'}</div>
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
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <div class="mob-result" on:click={() => addMob(mob)} role="button" tabindex="0">
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
        <div class="mob-entry-actions">
          <button class="remove-btn" on:click={() => removeMob(mob.mobId)}>Remove</button>
        </div>
      </div>
      <div class="mob-entry-body">
        {#if loadingMaturities[mob.mobId]}
          <div class="mat-loading" style="flex:1">Loading maturities...</div>
        {:else}
          <button
            class="configure-btn"
            disabled={mob.maturities.length === 0}
            on:click={() => openMaturityDialog(mob.mobId)}
          >
            Configure Maturities ({getSelectedCount(mob)}/{mob.maturities.length})
          </button>
        {/if}
      </div>
    </div>
  {/each}

  <div class="actions">
    <button class="btn btn-primary" on:click={handleSave}>Save Mob Data</button>
    <button class="btn" on:click={handleCancel}>Cancel</button>
  </div>
</div>

<!-- Maturity Configuration Dialog -->
{#if maturityDialog && dialogMob}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="dialog-overlay" on:click={closeMaturityDialog}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="maturity-dialog" on:click|stopPropagation>
      <div class="dialog-header">
        <h3>{dialogMob.mobName}</h3>
        <button class="dialog-close" on:click={closeMaturityDialog}>×</button>
      </div>

      <div class="dialog-actions">
        <button on:click={() => selectAllMaturities(dialogMob.mobId)}>All</button>
        <button on:click={() => deselectAllMaturities(dialogMob.mobId)}>None</button>
      </div>

      <div class="dialog-content">
        {#if dialogMob.maturities.length === 0}
          <div class="dialog-empty">No maturities found for this mob.</div>
        {:else}
          <div class="mat-list-header">
            <span></span>
            <span>Maturity</span>
            <span>Lv / HP</span>
            <span>Rare</span>
          </div>
          {#each dialogMob.maturities as mat (mat.id)}
            <div class="mat-row" class:disabled={!mat.selected} class:boss={mat.boss}>
              <label>
                <input
                  type="checkbox"
                  checked={mat.selected}
                  on:change={() => toggleMaturity(dialogMob.mobId, mat.id)}
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
                    on:click={() => toggleRare(dialogMob.mobId, mat.id)}
                    title="Toggle rare spawn"
                  >R</button>
                {/if}
              </div>
            </div>
          {/each}
        {/if}
      </div>

      <div class="dialog-footer">
        <button on:click={closeMaturityDialog}>Done</button>
      </div>
    </div>
  </div>
{/if}
