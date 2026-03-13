<!--
  @component SetEffectsEditor
  Editor for EffectsOnSetEquip arrays in armor sets.

  Edit mode: Section-based editing where you first create piece count sections (e.g., "2 pieces"),
  then add effects within each section. Each piece count can only appear once.

  Display format: Shows "<strength><unit> <effect name>" (e.g., "+5% Speed Increase")
-->
<script>
  import { run } from 'svelte/legacy';

  // @ts-nocheck
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';
  import SearchInput from './SearchInput.svelte';
  import CreateEffectDialog from './CreateEffectDialog.svelte';

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {Array} [effects]
   * @property {string} [fieldName]
   * @property {Array} Available effects for dropdown [{Name, CanonicalName, Properties: {Unit}} [availableEffects]
   * @property {number} [maxPieces]
   */

  /** @type {Props} */
  let {
    effects = [],
    fieldName = 'EffectsOnSetEquip',
    availableEffects = [],
    maxPieces = 7
  } = $props();

  let showCreateDialog = $state(false);
  let createDialogPieceCount = $state(null);
  let localAvailableEffects = $state([]);
  run(() => {
    localAvailableEffects = [...(availableEffects || [])];
  });

  // Group effects by MinSetPieces for display and editing
  let groupedEffects = $derived((() => {
    const groups = {};
    (effects || []).forEach((e, originalIndex) => {
      const pieces = e.Values?.MinSetPieces || 1;
      if (!groups[pieces]) groups[pieces] = [];
      groups[pieces].push({ ...e, _originalIndex: originalIndex });
    });
    return Object.entries(groups)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([pieces, effs]) => ({
        pieces: Number(pieces),
        effects: effs
      }));
  })());

  // Get which piece counts are already used
  let usedPieceCounts = $derived(new Set(groupedEffects.map(g => g.pieces)));

  // Available piece counts for adding new sections
  let availablePieceCounts = $derived(Array.from({ length: maxPieces - 1 }, (_, i) => i + 2)
    .filter(n => !usedPieceCounts.has(n)));

  // Available effect options with sublabel for SearchInput
  let effectOptions = $derived(localAvailableEffects.map(e => ({
    label: e.Name,
    value: e.Name,
    sublabel: e.CanonicalName || null
  })));

  // Show section if has effects or in edit mode
  let shouldShow = $derived($editMode || (effects?.length > 0));

  // Get unit for an effect name from availableEffects list
  function getEffectUnit(effectName) {
    if (!effectName || !localAvailableEffects?.length) return '';
    const effect = localAvailableEffects.find(e => e.Name === effectName);
    return effect?.Properties?.Unit || '';
  }

  // Format effect value with unit
  function formatEffectValue(strength, unit) {
    if (strength == null) return '?';
    const prefix = strength >= 0 ? '+' : '';
    return `${prefix}${strength}${unit || ''}`;
  }

  // === Section CRUD Operations ===
  function addSection(pieceCount) {
    if (usedPieceCounts.has(pieceCount)) return;

    // Add a default effect for the new section
    const newEffect = {
      Name: '',
      Values: {
        Strength: 0,
        MinSetPieces: pieceCount
      }
    };
    updateField(fieldName, [...effects, newEffect]);
  }

  function removeSection(pieceCount) {
    // Remove all effects with this piece count
    const newEffects = effects.filter(e => e.Values?.MinSetPieces !== pieceCount);
    updateField(fieldName, newEffects);
  }

  // === Effect CRUD Operations ===
  function addEffectToSection(pieceCount) {
    const newEffect = {
      Name: '',
      Values: {
        Strength: 0,
        MinSetPieces: pieceCount
      }
    };
    updateField(fieldName, [...effects, newEffect]);
  }

  function handleCreateEffect(event) {
    const { Name, _newEffect } = event.detail;

    localAvailableEffects = [...localAvailableEffects, {
      Name,
      CanonicalName: _newEffect.CanonicalName,
      Properties: { Unit: _newEffect.Unit || '' }
    }];

    const newEffect = {
      Name,
      _newEffect,
      Values: {
        Strength: 0,
        MinSetPieces: createDialogPieceCount || (availablePieceCounts[0] ?? 2)
      }
    };

    updateField(fieldName, [...effects, newEffect]);
    showCreateDialog = false;
    createDialogPieceCount = null;
  }

  function updateEffect(originalIndex, field, value) {
    const newEffects = [...effects];
    const effect = newEffects[originalIndex];

    if (field === 'Name') {
      newEffects[originalIndex] = {
        ...effect,
        Name: value,
        Values: {
          ...effect.Values,
          Unit: getEffectUnit(value)
        }
      };
    } else if (field === 'Strength') {
      newEffects[originalIndex] = {
        ...effect,
        Values: {
          ...effect.Values,
          Strength: value
        }
      };
    }
    updateField(fieldName, newEffects);
  }

  function removeEffect(originalIndex) {
    updateField(fieldName, effects.filter((_, i) => i !== originalIndex));
  }

  // New section piece count selection
  let newSectionPieceCount = $state(2);
  run(() => {
    if (availablePieceCounts.length > 0 && !availablePieceCounts.includes(newSectionPieceCount)) {
      newSectionPieceCount = availablePieceCounts[0];
    }
  });
</script>

{#if shouldShow}
  <div class="set-effects-editor" class:editing={$editMode}>
    {#if $editMode}
      <div class="effects-edit-sections">
        {#each groupedEffects as group}
          <div class="effect-section">
            <div class="section-header">
              <span class="section-title">{group.pieces} Pieces</span>
              <button class="btn-remove-section" onclick={() => removeSection(group.pieces)} title="Remove section">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div class="section-effects">
              {#each group.effects as effect}
                <div class="effect-edit-row">
                  <div class="effect-row-top">
                    <div class="effect-search-wrapper">
                      <SearchInput
                        value={effect.Name}
                        options={effectOptions}
                        placeholder="Search effect..."
                        on:select={(e) => updateEffect(effect._originalIndex, 'Name', e.detail.value)}
                        on:change={(e) => updateEffect(effect._originalIndex, 'Name', e.detail.value)}
                      />
                    </div>
                    <button class="btn-remove-effect" onclick={() => removeEffect(effect._originalIndex)} title="Remove effect">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  </div>
                  <div class="effect-row-bottom">
                    <input
                      type="number"
                      class="effect-strength"
                      value={effect.Values?.Strength ?? 0}
                      step="0.1"
                      onchange={(e) => updateEffect(effect._originalIndex, 'Strength', parseFloat(e.target.value) || 0)}
                      title="Strength value"
                    />
                    <span class="effect-unit-display">{getEffectUnit(effect.Name)}</span>
                  </div>
                </div>
              {/each}
              <div class="btn-row">
                <button class="btn-add-effect" onclick={() => addEffectToSection(group.pieces)}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                  Add Effect
                </button>
                <button class="btn-add-effect btn-create" onclick={() => { createDialogPieceCount = group.pieces; showCreateDialog = true; }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="12" y1="18" x2="12" y2="12" />
                    <line x1="9" y1="15" x2="15" y2="15" />
                  </svg>
                  New Effect
                </button>
              </div>
            </div>
          </div>
        {/each}

        <!-- Add new section -->
        {#if availablePieceCounts.length > 0}
          <div class="add-section-row">
            <select class="section-select" bind:value={newSectionPieceCount}>
              {#each availablePieceCounts as count}
                <option value={count}>{count} Pieces</option>
              {/each}
            </select>
            <button class="btn-add-section" onclick={() => addSection(newSectionPieceCount)}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Add Section
            </button>
          </div>
        {/if}
      </div>
    {:else if groupedEffects.length > 0}
      <div class="effects-display">
        {#each groupedEffects as group}
          <div class="effect-group">
            <div class="effect-pieces">{group.pieces} Pieces</div>
            {#each group.effects as effect}
              <div class="effect-row">
                <span class="effect-value">{formatEffectValue(effect.Values?.Strength, getEffectUnit(effect.Name))}</span>
                <span class="effect-name">{effect.Name}</span>
              </div>
            {/each}
          </div>
        {/each}
      </div>
    {:else}
      <div class="no-effects">No set effects</div>
    {/if}
  </div>
{/if}

{#if showCreateDialog}
  <CreateEffectDialog
    on:create={handleCreateEffect}
    on:cancel={() => { showCreateDialog = false; createDialogPieceCount = null; }}
  />
{/if}

<style>
  .set-effects-editor {
    width: 100%;
  }

  /* Display mode styles */
  .effects-display {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .effect-group {
    padding: 10px 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
    border-left: 3px solid var(--accent-color, #4a9eff);
  }

  .effect-pieces {
    font-size: 11px;
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
    text-transform: uppercase;
    margin-bottom: 6px;
  }

  .effect-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 3px 0;
    font-size: 13px;
  }

  .effect-value {
    font-weight: 600;
    color: var(--success-color, #4ade80);
  }

  .effect-name {
    color: var(--text-color);
  }

  .no-effects {
    padding: 12px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 13px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  /* Edit mode styles */
  .effects-edit-sections {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .effect-section {
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
    border-left: 3px solid var(--accent-color, #4a9eff);
    overflow: hidden;
  }

  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background-color: var(--secondary-color);
    border-bottom: 1px solid var(--border-color, #555);
  }

  .section-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
    text-transform: uppercase;
  }

  .section-effects {
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .effect-edit-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px;
    background-color: var(--secondary-color);
    border-radius: 4px;
  }

  .effect-row-top {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .effect-search-wrapper {
    flex: 1;
    min-width: 120px;
  }

  .effect-row-bottom {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .effect-strength {
    width: 60px;
    padding: 5px 6px;
    font-size: 12px;
    text-align: left;
    background-color: var(--input-bg, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .effect-unit-display {
    font-size: 11px;
    color: var(--text-muted, #999);
    min-width: 25px;
  }

  .effect-strength:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .btn-remove-section,
  .btn-remove-effect {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--error-color, #ff6b6b);
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .btn-remove-section:hover,
  .btn-remove-effect:hover {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  .btn-row {
    display: flex;
    gap: 6px;
    margin-top: 4px;
  }

  .btn-add-effect {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 6px 10px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    font-size: 11px;
    cursor: pointer;
    transition: all 0.15s;
    flex: 1;
  }

  .btn-add-effect:hover {
    background-color: var(--hover-color);
    color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
  }

  .add-section-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px dashed var(--border-color, #555);
    border-radius: 6px;
  }

  .section-select {
    padding: 6px 10px;
    font-size: 12px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .btn-add-section {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px;
    background-color: transparent;
    border: 1px solid var(--accent-color, #4a9eff);
    border-radius: 4px;
    color: var(--accent-color, #4a9eff);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-add-section:hover {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

</style>
