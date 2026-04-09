<!--
  @component EffectSetCompare
  Left sidebar panel for managing saved equipment effect sets.
  Provides Create/Delete/Clone/Import/Export at the top, set list below.
-->
<script>
  // @ts-nocheck
  import { buildDefaultSetName } from './effectOptimizer.js';

  let {
    savedSets = $bindable([]),
    activeSetId = $bindable(null),
    currentSlots = {},
    currentTargets = {},
    currentSummary = [],
    onload = () => {},
    ondelete = () => {}
  } = $props();

  let editingName = $state(null);
  let editValue = $state('');

  function createSet() {
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
    activeSetId = newSet.id;
  }

  function cloneSet() {
    if (!activeSetId) return;
    const source = savedSets.find(s => s.id === activeSetId);
    if (!source) return;
    const clone = {
      ...JSON.parse(JSON.stringify(source)),
      id: Date.now().toString(36),
      name: source.name + ' (copy)',
      savedAt: new Date().toISOString()
    };
    savedSets = [...savedSets, clone];
    activeSetId = clone.id;
  }

  function deleteActiveSet() {
    if (!activeSetId) return;
    const idx = savedSets.findIndex(s => s.id === activeSetId);
    savedSets = savedSets.filter(s => s.id !== activeSetId);
    ondelete(activeSetId);
    // Select next or previous set
    if (savedSets.length > 0) {
      activeSetId = savedSets[Math.min(idx, savedSets.length - 1)]?.id ?? null;
      const set = savedSets.find(s => s.id === activeSetId);
      if (set) onload(set);
    } else {
      activeSetId = null;
    }
  }

  function exportSets() {
    const data = JSON.stringify(savedSets, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'effect-optimizer-sets.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  function importSets() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
      const file = e.target?.files?.[0];
      if (!file) return;
      try {
        const text = await file.text();
        const imported = JSON.parse(text);
        if (!Array.isArray(imported)) return;
        // Assign new IDs to avoid conflicts
        const newSets = imported.map(s => ({
          ...s,
          id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
          savedAt: new Date().toISOString()
        }));
        savedSets = [...savedSets, ...newSets];
      } catch { /* ignore invalid files */ }
    };
    input.click();
  }

  function selectSet(set) {
    activeSetId = set.id;
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

  function updateActiveSet() {
    if (!activeSetId) return;
    savedSets = savedSets.map(s => s.id === activeSetId ? {
      ...s,
      slots: JSON.parse(JSON.stringify(currentSlots)),
      targets: { ...currentTargets },
      summary: currentSummary.map(e => ({ name: e.name, value: e.signedTotal, unit: e.unit })),
      savedAt: new Date().toISOString()
    } : s);
  }
</script>

<div class="set-sidebar">
  <div class="set-toolbar">
    <button type="button" class="toolbar-btn" onclick={createSet} title="Create new set">Create</button>
    <button type="button" class="toolbar-btn" onclick={cloneSet} disabled={!activeSetId} title="Clone selected set">Clone</button>
    <button type="button" class="toolbar-btn" onclick={updateActiveSet} disabled={!activeSetId} title="Save current config to selected set">Save</button>
    <button type="button" class="toolbar-btn btn-danger-subtle" onclick={deleteActiveSet} disabled={!activeSetId} title="Delete selected set">Delete</button>
    <button type="button" class="toolbar-btn" onclick={importSets} title="Import sets from file">Import</button>
    <button type="button" class="toolbar-btn" onclick={exportSets} disabled={savedSets.length === 0} title="Export all sets">Export</button>
  </div>

  <div class="set-list">
    {#if savedSets.length === 0}
      <div class="set-empty">No saved sets</div>
    {:else}
      {#each savedSets as set (set.id)}
        <button
          type="button"
          class="set-item"
          class:active={set.id === activeSetId}
          onclick={() => selectSet(set)}
          ondblclick={() => startRename(set)}
        >
          {#if editingName === set.id}
            <!-- svelte-ignore a11y_autofocus -->
            <input
              class="rename-input"
              type="text"
              bind:value={editValue}
              onkeydown={(e) => { if (e.key === 'Enter') finishRename(set.id); if (e.key === 'Escape') editingName = null; }}
              onblur={() => finishRename(set.id)}
              onclick={(e) => e.stopPropagation()}
              autofocus
            />
          {:else}
            <span class="set-name">{set.name}</span>
            <span class="set-meta">
              {set.summary?.filter(e => Math.abs(e.value) > 0.01).length || 0} effects
            </span>
          {/if}
        </button>
      {/each}
    {/if}
  </div>
</div>

<style>
  .set-sidebar {
    display: flex;
    flex-direction: column;
    gap: 6px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background-color: var(--secondary-color);
    padding: 10px;
    flex: 1 1 0;
    min-height: 0;
    overflow: hidden;
  }

  .set-toolbar {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color);
  }

  .toolbar-btn {
    padding: 6px 4px;
    font-size: 12px;
    border: 1px solid var(--border-color);
    border-radius: 5px;
    background-color: transparent;
    color: var(--text-muted);
    cursor: pointer;
    text-align: center;
    transition: all 0.1s ease;
  }

  .toolbar-btn:hover:not(:disabled) {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .toolbar-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-danger-subtle:hover:not(:disabled) {
    color: var(--danger-color, #d9534f);
    border-color: var(--danger-color, #d9534f);
  }

  /* toolbar-spacer removed - using grid layout */
  .toolbar-spacer {
    display: none;
  }

  .set-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .set-empty {
    font-size: 11px;
    color: var(--text-muted);
    text-align: center;
    padding: 8px 0;
  }

  .set-item {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 1px;
    padding: 5px 8px;
    border: 1px solid transparent;
    border-radius: 4px;
    background-color: transparent;
    color: var(--text-color);
    cursor: pointer;
    text-align: left;
    width: 100%;
    transition: all 0.1s ease;
  }

  .set-item:hover {
    background-color: var(--hover-color);
  }

  .set-item.active {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .set-name {
    font-size: 12px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    width: 100%;
  }

  .set-meta {
    font-size: 10px;
    opacity: 0.7;
  }

  .rename-input {
    padding: 2px 4px;
    font-size: 12px;
    background-color: var(--bg-color);
    border: 1px solid var(--accent-color);
    border-radius: 3px;
    color: var(--text-color);
    width: 100%;
    box-sizing: border-box;
  }
</style>
