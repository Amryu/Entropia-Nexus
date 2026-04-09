<!--
  @component EffectSetCompare
  Save/load/compare named equipment effect sets.
  Shows saved sets as a list and a side-by-side comparison grid.
-->
<script>
  // @ts-nocheck
  import { buildDefaultSetName } from './effectOptimizer.js';

  let {
    savedSets = $bindable([]),
    currentSlots = {},
    currentTargets = {},
    currentSummary = [],
    onload = () => {},
    ondelete = () => {}
  } = $props();

  let compareMode = $state(false);
  let selectedForCompare = $state(new Set());
  let editingName = $state(null);
  let editValue = $state('');

  function saveCurrentSet() {
    const name = buildDefaultSetName(currentSlots);
    const newSet = {
      id: Date.now().toString(36),
      name,
      slots: JSON.parse(JSON.stringify(currentSlots)),
      targets: { ...currentTargets },
      summary: currentSummary.map(e => ({ name: e.name, value: e.signedTotal, unit: e.unit })),
      savedAt: new Date().toISOString()
    };
    savedSets = [...savedSets, newSet];
  }

  function deleteSet(id) {
    savedSets = savedSets.filter(s => s.id !== id);
    selectedForCompare.delete(id);
    selectedForCompare = new Set(selectedForCompare);
    ondelete(id);
  }

  function loadSet(set) {
    onload(set);
  }

  function startRename(set) {
    editingName = set.id;
    editValue = set.name;
  }

  function finishRename(id) {
    if (editValue.trim()) {
      savedSets = savedSets.map(s => s.id === id ? { ...s, name: editValue.trim() } : s);
    }
    editingName = null;
    editValue = '';
  }

  function toggleCompare(id) {
    if (selectedForCompare.has(id)) {
      selectedForCompare.delete(id);
    } else {
      selectedForCompare.add(id);
    }
    selectedForCompare = new Set(selectedForCompare);
  }

  let compareSets = $derived(
    savedSets.filter(s => selectedForCompare.has(s.id))
  );

  // Collect all unique effect names across selected sets
  let compareEffectNames = $derived.by(() => {
    const names = new Set();
    for (const set of compareSets) {
      for (const eff of (set.summary || [])) {
        if (eff.name) names.add(eff.name);
      }
    }
    return [...names].sort();
  });
</script>

<div class="set-compare">
  <div class="set-header">
    <h3>Saved Sets</h3>
    <div class="set-actions">
      {#if savedSets.length >= 2}
        <button
          type="button"
          class="btn-text"
          onclick={() => { compareMode = !compareMode; }}
        >{compareMode ? 'Done' : 'Compare'}</button>
      {/if}
      <button type="button" class="btn-save" onclick={saveCurrentSet}>Save Current</button>
    </div>
  </div>

  {#if savedSets.length === 0}
    <div class="set-empty">No saved sets yet. Configure equipment above and save to compare later.</div>
  {:else}
    <div class="set-list">
      {#each savedSets as set (set.id)}
        <div class="set-item" class:selected={selectedForCompare.has(set.id)}>
          {#if compareMode}
            <label class="compare-check">
              <input type="checkbox" checked={selectedForCompare.has(set.id)} onchange={() => toggleCompare(set.id)} />
            </label>
          {/if}
          <div class="set-info">
            {#if editingName === set.id}
              <input
                class="rename-input"
                type="text"
                bind:value={editValue}
                onkeydown={(e) => { if (e.key === 'Enter') finishRename(set.id); if (e.key === 'Escape') editingName = null; }}
                onblur={() => finishRename(set.id)}
              />
            {:else}
              <span class="set-name" ondblclick={() => startRename(set)}>{set.name}</span>
            {/if}
            <span class="set-meta">
              {set.summary?.filter(e => Math.abs(e.value) > 0.01).length || 0} effects
            </span>
          </div>
          <div class="set-item-actions">
            <button type="button" class="btn-sm" onclick={() => loadSet(set)} title="Load this set">Load</button>
            <button type="button" class="btn-sm btn-danger" onclick={() => deleteSet(set.id)} title="Delete">Del</button>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  {#if compareMode && compareSets.length >= 2}
    <div class="compare-grid">
      <table class="compare-table">
        <thead>
          <tr>
            <th class="compare-effect-col">Effect</th>
            {#each compareSets as set (set.id)}
              <th class="compare-set-col">{set.name}</th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each compareEffectNames as effectName (effectName)}
            <tr>
              <td class="compare-effect-name">{effectName}</td>
              {#each compareSets as set (set.id)}
                {@const eff = set.summary?.find(e => e.name === effectName)}
                <td class="compare-value">
                  {#if eff}
                    {eff.value > 0 ? '+' : ''}{eff.value.toFixed(1)}{eff.unit || ''}
                  {:else}
                    -
                  {/if}
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .set-compare {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .set-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .set-header h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .set-actions {
    display: flex;
    gap: 6px;
  }

  .btn-text {
    background: none;
    border: none;
    color: var(--accent-color);
    font-size: 12px;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
  }

  .btn-text:hover {
    background-color: var(--hover-color);
  }

  .btn-save {
    padding: 4px 10px;
    font-size: 12px;
    border: 1px solid var(--accent-color);
    border-radius: 6px;
    background-color: var(--accent-color);
    color: white;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-save:hover {
    opacity: 0.9;
  }

  .set-empty {
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
    padding: 12px 0;
  }

  .set-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .set-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--bg-color);
  }

  .set-item.selected {
    border-color: var(--accent-color);
  }

  .compare-check input {
    margin: 0;
  }

  .set-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .set-name {
    font-size: 13px;
    color: var(--text-color);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: default;
  }

  .set-meta {
    font-size: 10px;
    color: var(--text-muted);
  }

  .rename-input {
    padding: 2px 6px;
    font-size: 13px;
    background-color: var(--secondary-color);
    border: 1px solid var(--accent-color);
    border-radius: 4px;
    color: var(--text-color);
    width: 100%;
  }

  .set-item-actions {
    display: flex;
    gap: 4px;
  }

  .btn-sm {
    padding: 2px 8px;
    font-size: 11px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.1s ease;
  }

  .btn-sm:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .btn-danger:hover {
    color: var(--danger-color, #d9534f);
    border-color: var(--danger-color, #d9534f);
  }

  .compare-grid {
    overflow-x: auto;
    margin-top: 4px;
  }

  .compare-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  .compare-table th, .compare-table td {
    padding: 4px 8px;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
  }

  .compare-table th {
    font-weight: 600;
    color: var(--text-muted);
    font-size: 11px;
    white-space: nowrap;
  }

  .compare-effect-col {
    min-width: 140px;
  }

  .compare-set-col {
    min-width: 80px;
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .compare-effect-name {
    color: var(--text-color);
    font-weight: 500;
  }

  .compare-value {
    font-variant-numeric: tabular-nums;
    color: var(--text-color);
  }
</style>
