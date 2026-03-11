<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { apiCall } from '$lib/util.js';

  export let mobs = [];          // All mobs from /mobs (cached by parent)
  export let location = null;    // Existing WaveEvent location (if editing)
  export let isNew = false;
  export let pendingWaveData = null; // { waves: [...] } from pending changes

  const dispatch = createEventDispatcher();

  // Working copy of waves
  let waves = [];
  let expandedWaves = new Set();
  // mob maturity cache: mobId → [{ Id, Name, Health, Level, Boss }]
  let mobMaturityCache = {};
  // per-wave maturity search
  let waveSearchQueries = [];  // one search string per wave index
  let maturitySearchWaveIdx = null;
  let maturitySearchResults = [];

  // Initialize from pending data or existing location Waves
  $: {
    const source = pendingWaveData?.waves ?? location?.Waves ?? [];
    if (waves.length === 0 && source.length > 0) {
      waves = source.map(w => ({
        Id: w.Id ?? null,
        WaveIndex: w.WaveIndex,
        TimeToComplete: w.TimeToComplete ?? null,
        MobMaturities: [...(w.MobMaturities ?? [])]
      }));
      waveSearchQueries = waves.map(() => '');
    }
  }

  // Mob name lookup by maturity ID — built lazily from cache
  function getMaturityLabel(maturityId) {
    for (const [, maturities] of Object.entries(mobMaturityCache)) {
      const mat = maturities.find(m => m.Id === maturityId);
      if (mat) return mat.label;
    }
    return `Maturity #${maturityId}`;
  }

  async function loadMaturities(mobId) {
    if (mobMaturityCache[mobId] !== undefined) return;
    mobMaturityCache[mobId] = []; // Prevent double-fetch
    try {
      const mob = await apiCall(fetch, `/mobs/${mobId}`);
      if (mob?.Maturities) {
        mobMaturityCache[mobId] = mob.Maturities.map(m => ({
          Id: m.Id,
          Name: m.Name,
          label: `${mob.Name} - ${m.Name}`
        }));
      }
    } catch {
      // leave empty
    }
    mobMaturityCache = mobMaturityCache; // trigger reactivity
  }

  // Preload maturities for all mobs referenced in current waves
  $: {
    const referencedMobIds = new Set();
    for (const wave of waves) {
      for (const matId of wave.MobMaturities) {
        // Reverse-lookup: find which mob owns this maturity from the cache
        let found = false;
        for (const [mobId, maturities] of Object.entries(mobMaturityCache)) {
          if (maturities.some(m => m.Id === matId)) { found = true; break; }
        }
        if (!found) {
          // We don't know which mob owns this maturity yet — search mobs by maturity
          referencedMobIds.add(null); // signal that a full-scan load is needed
        }
      }
    }
  }

  function addWave() {
    const nextIndex = waves.length > 0
      ? Math.max(...waves.map(w => w.WaveIndex)) + 1
      : 1;
    waves = [...waves, { Id: null, WaveIndex: nextIndex, TimeToComplete: null, MobMaturities: [] }];
    waveSearchQueries = [...waveSearchQueries, ''];
    expandedWaves = new Set([...expandedWaves, waves.length - 1]);
  }

  function removeWave(idx) {
    waves = waves.filter((_, i) => i !== idx);
    waveSearchQueries = waveSearchQueries.filter((_, i) => i !== idx);
    if (maturitySearchWaveIdx === idx) { maturitySearchWaveIdx = null; maturitySearchResults = []; }
    expandedWaves.delete(idx);
    expandedWaves = new Set(expandedWaves);
  }

  function toggleWave(idx) {
    if (expandedWaves.has(idx)) {
      expandedWaves.delete(idx);
    } else {
      expandedWaves.add(idx);
    }
    expandedWaves = new Set(expandedWaves);
  }

  function updateWave(idx, field, value) {
    waves = waves.map((w, i) => i === idx ? { ...w, [field]: value } : w);
  }

  function removeMaturity(waveIdx, matId) {
    waves = waves.map((w, i) =>
      i === waveIdx ? { ...w, MobMaturities: w.MobMaturities.filter(m => m !== matId) } : w
    );
  }

  async function handleMaturitySearch(waveIdx) {
    maturitySearchWaveIdx = waveIdx;
    const query = (waveSearchQueries[waveIdx] ?? '').trim().toLowerCase();
    if (query.length < 2) { maturitySearchResults = []; return; }

    // Search mobs by name
    const matchingMobs = mobs.filter(m => m.Name.toLowerCase().includes(query)).slice(0, 8);
    const results = [];
    for (const mob of matchingMobs) {
      await loadMaturities(mob.Id);
      for (const mat of (mobMaturityCache[mob.Id] || [])) {
        results.push({ matId: mat.Id, label: mat.label, mobId: mob.Id });
      }
    }

    const existingSet = new Set(waves[waveIdx]?.MobMaturities ?? []);
    maturitySearchResults = results.filter(r => !existingSet.has(r.matId));
  }

  function addMaturity(waveIdx, matId) {
    if (waves[waveIdx]?.MobMaturities.includes(matId)) return;
    waves = waves.map((w, i) =>
      i === waveIdx ? { ...w, MobMaturities: [...w.MobMaturities, matId] } : w
    );
    waveSearchQueries[waveIdx] = '';
    waveSearchQueries = waveSearchQueries;
    maturitySearchResults = [];
    maturitySearchWaveIdx = null;
  }

  function handleSave() {
    dispatch('save', { waves });
  }

  function handleCancel() {
    dispatch('cancel');
  }
</script>

<style>
  .wave-editor {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    flex: 1;
    height: 100%;
    min-height: 0;
    overflow-y: auto;
    box-sizing: border-box;
  }

  .editor-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
    margin: 0;
  }

  .location-name {
    font-size: 12px;
    color: var(--text-muted);
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .wave-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .wave-item {
    border: 1px solid var(--border-color);
    border-radius: 4px;
  }

  .wave-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    cursor: pointer;
    background: var(--secondary-color);
    user-select: none;
    border-radius: 3px 3px 0 0;
  }

  .wave-header:hover {
    background: var(--hover-color);
  }

  .expand-icon {
    font-size: 10px;
    color: var(--text-muted);
    width: 10px;
    flex-shrink: 0;
  }

  .wave-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-color);
    flex: 1;
  }

  .wave-summary {
    font-size: 11px;
    color: var(--text-muted);
  }

  .wave-remove {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 2px 4px;
    font-size: 14px;
    line-height: 1;
    border-radius: 3px;
  }

  .wave-remove:hover {
    color: var(--danger-color, #ef4444);
    background: rgba(239, 68, 68, 0.1);
  }

  .wave-body {
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-top: 1px solid var(--border-color);
    background: var(--primary-color);
    border-radius: 0 0 3px 3px;
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
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    padding: 4px 8px;
    font-size: 12px;
    width: 100%;
    box-sizing: border-box;
  }

  .field-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .maturity-list {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .maturity-chip {
    display: flex;
    align-items: center;
    gap: 4px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 2px 8px;
    font-size: 11px;
    color: var(--text-color);
  }

  .maturity-chip button {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0;
    font-size: 12px;
    line-height: 1;
  }

  .maturity-chip button:hover {
    color: var(--danger-color, #ef4444);
  }

  .search-wrap {
    position: relative;
  }

  .search-results {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    z-index: 10;
    max-height: 150px;
    overflow-y: auto;
  }

  .search-result-item {
    padding: 5px 8px;
    font-size: 12px;
    cursor: pointer;
    color: var(--text-color);
  }

  .search-result-item:hover {
    background: var(--hover-color);
  }

  .empty-waves {
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
    padding: 16px 0;
  }

  .actions {
    display: flex;
    gap: 6px;
  }

  .btn {
    padding: 6px 12px;
    border-radius: 4px;
    border: 1px solid var(--border-color);
    font-size: 12px;
    cursor: pointer;
    background: var(--secondary-color);
    color: var(--text-color);
  }

  .btn:hover {
    background: var(--hover-color);
  }

  .btn-primary {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .btn-primary:hover {
    opacity: 0.9;
  }

  .btn-add-wave {
    font-size: 12px;
    padding: 5px 10px;
    border-radius: 4px;
    border: 1px dashed var(--border-color);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    width: 100%;
    text-align: center;
  }

  .btn-add-wave:hover {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }

  .divider {
    height: 1px;
    background: var(--border-color);
    margin: 2px 0;
  }
</style>

<div class="wave-editor">
  <h3 class="editor-title">Wave Spawns</h3>
  {#if location?.Name}
    <p class="location-name">{location.Name}</p>
  {/if}

  <div class="divider"></div>

  <div class="wave-list">
    {#if waves.length === 0}
      <div class="empty-waves">No waves defined. Add a wave to get started.</div>
    {/if}

    {#each waves as wave, idx}
      <div class="wave-item">
        <div class="wave-header" on:click={() => toggleWave(idx)} role="button" tabindex="0" on:keydown={e => e.key === 'Enter' && toggleWave(idx)}>
          <span class="expand-icon">{expandedWaves.has(idx) ? '▼' : '▶'}</span>
          <span class="wave-label">Wave {wave.WaveIndex}</span>
          <span class="wave-summary">
            {#if wave.TimeToComplete}{wave.TimeToComplete} min · {/if}{wave.MobMaturities.length} mob{wave.MobMaturities.length !== 1 ? 's' : ''}
          </span>
          <button class="wave-remove" on:click|stopPropagation={() => removeWave(idx)} title="Remove wave">×</button>
        </div>

        {#if expandedWaves.has(idx)}
          <div class="wave-body">
            <div class="field-group">
              <span class="field-label">Wave Index</span>
              <input
                class="field-input"
                type="number"
                min="1"
                value={wave.WaveIndex}
                on:change={e => updateWave(idx, 'WaveIndex', parseInt(e.target.value) || wave.WaveIndex)}
              />
            </div>

            <div class="field-group">
              <span class="field-label">Time to Complete (min)</span>
              <input
                class="field-input"
                type="number"
                min="1"
                placeholder="No limit"
                value={wave.TimeToComplete ?? ''}
                on:change={e => updateWave(idx, 'TimeToComplete', e.target.value ? parseInt(e.target.value) : null)}
              />
            </div>

            <div class="field-group">
              <span class="field-label">Mob Maturities</span>
              <div class="maturity-list">
                {#each wave.MobMaturities as matId}
                  <span class="maturity-chip">
                    {getMaturityLabel(matId)}
                    <button on:click={() => removeMaturity(idx, matId)} title="Remove">×</button>
                  </span>
                {/each}
              </div>

              <div class="search-wrap">
                <input
                  class="field-input"
                  type="text"
                  placeholder="Search mob name to add..."
                  bind:value={waveSearchQueries[idx]}
                  on:input={() => handleMaturitySearch(idx)}
                  on:focus={() => { maturitySearchWaveIdx = idx; }}
                />
                {#if maturitySearchWaveIdx === idx && maturitySearchResults.length > 0}
                  <div class="search-results">
                    {#each maturitySearchResults as result}
                      <div
                        class="search-result-item"
                        on:click={() => addMaturity(idx, result.matId)}
                        role="button"
                        tabindex="0"
                        on:keydown={e => e.key === 'Enter' && addMaturity(idx, result.matId)}
                      >
                        {result.label}
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            </div>
          </div>
        {/if}
      </div>
    {/each}

    <button class="btn-add-wave" on:click={addWave}>+ Add Wave</button>
  </div>

  <div style="flex: 1"></div>

  <div class="divider"></div>

  <div class="actions">
    <button class="btn btn-primary" on:click={handleSave}>Save</button>
    <button class="btn" on:click={handleCancel}>Cancel</button>
  </div>
</div>
