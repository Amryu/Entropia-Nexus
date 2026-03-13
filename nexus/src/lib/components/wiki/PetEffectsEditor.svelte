<!--
  @component PetEffectsEditor
  Editor for pet Effects arrays with complex unlock conditions.

  Each effect has:
  - Name: Effect name (from availableEffects)
  - Properties.Strength: Effect strength value
  - Properties.Unit: Unit (from effect definition)
  - Properties.NutrioConsumptionPerHour: Upkeep cost
  - Properties.Unlock: { Level, CostPED, CostEssence, CostRareEssence, Criteria, CriteriaValue }
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
   */

  /** @type {Props} */
  let { effects = [], fieldName = 'Effects', availableEffects = [] } = $props();

  let showCreateDialog = $state(false);
  let localAvailableEffects = $state([]);
  run(() => {
    localAvailableEffects = [...(availableEffects || [])];
  });

  // Sort effects by unlock level for display
  let sortedEffects = $derived([...(effects || [])].sort((a, b) =>
    (a.Properties?.Unlock?.Level || 0) - (b.Properties?.Unlock?.Level || 0)
  ));

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

  // Format effect strength display
  function formatStrength(effect) {
    const strength = effect.Properties?.Strength ?? '?';
    const unit = getEffectUnit(effect.Name);
    return `${strength}${unit}`;
  }

  // === Effect CRUD Operations ===
  function addEffect() {
    const newEffect = {
      Name: '',
      Properties: {
        Strength: 0,
        Unit: '',
        NutrioConsumptionPerHour: 0,
        Unlock: {
          Level: 1,
          CostPED: 0,
          CostEssence: 0,
          CostRareEssence: 0,
          Criteria: null,
          CriteriaValue: null
        }
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
      Properties: {
        Strength: 0,
        Unit: _newEffect.Unit || '',
        NutrioConsumptionPerHour: 0,
        Unlock: {
          Level: 1,
          CostPED: 0,
          CostEssence: 0,
          CostRareEssence: 0,
          Criteria: null,
          CriteriaValue: null
        }
      }
    };

    updateField(fieldName, [...effects, newEffect]);
    showCreateDialog = false;
  }

  function updateEffect(index, path, value) {
    const newEffects = JSON.parse(JSON.stringify(effects));
    const effect = newEffects[index];

    if (path === 'Name') {
      effect.Name = value;
      effect.Properties.Unit = getEffectUnit(value);
    } else {
      // Handle nested paths like 'Properties.Strength' or 'Properties.Unlock.Level'
      const keys = path.split('.');
      let obj = effect;
      for (let i = 0; i < keys.length - 1; i++) {
        if (!obj[keys[i]]) obj[keys[i]] = {};
        obj = obj[keys[i]];
      }
      obj[keys[keys.length - 1]] = value;
    }

    updateField(fieldName, newEffects);
  }

  function removeEffect(index) {
    updateField(fieldName, effects.filter((_, i) => i !== index));
  }

  // Expanded state for each effect's unlock section
  let expandedUnlock = $state({});

  function toggleUnlock(index) {
    expandedUnlock[index] = !expandedUnlock[index];
    expandedUnlock = expandedUnlock;
  }
</script>

{#if shouldShow}
  <div class="pet-effects-editor" class:editing={$editMode}>
    {#if $editMode}
      <div class="effects-edit-list">
        {#each effects as effect, i}
          <div class="effect-card">
            <div class="effect-main-row">
              <div class="effect-search-wrapper">
                <SearchInput
                  value={effect.Name}
                  options={effectOptions}
                  placeholder="Search effect..."
                  on:select={(e) => updateEffect(i, 'Name', e.detail.value)}
                  on:change={(e) => updateEffect(i, 'Name', e.detail.value)}
                />
              </div>
              <button class="btn-remove" onclick={() => removeEffect(i)} title="Remove effect">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <div class="effect-fields-row">
              <div class="field-group">
                <label>Strength</label>
                <div class="input-with-unit">
                  <input
                    type="number"
                    value={effect.Properties?.Strength ?? 0}
                    step="0.1"
                    onchange={(e) => updateEffect(i, 'Properties.Strength', parseFloat(e.target.value) || 0)}
                  />
                  <span class="unit">{getEffectUnit(effect.Name)}</span>
                </div>
              </div>
              <div class="field-group">
                <label>Upkeep</label>
                <div class="input-with-unit">
                  <input
                    type="number"
                    value={effect.Properties?.NutrioConsumptionPerHour ?? 0}
                    step="1"
                    min="0"
                    onchange={(e) => updateEffect(i, 'Properties.NutrioConsumptionPerHour', parseFloat(e.target.value) || 0)}
                  />
                  <span class="unit">/h</span>
                </div>
              </div>
            </div>

            <!-- Unlock conditions -->
            <div class="unlock-section">
              <button class="unlock-toggle" onclick={() => toggleUnlock(i)}>
                <svg class="chevron" class:expanded={expandedUnlock[i]} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
                Unlock Conditions
                <span class="unlock-summary">
                  Lv{effect.Properties?.Unlock?.Level || 1}
                  {#if effect.Properties?.Unlock?.CostPED > 0}
                    | {effect.Properties.Unlock.CostPED} PED
                  {/if}
                </span>
              </button>

              {#if expandedUnlock[i]}
                <div class="unlock-fields">
                  <div class="unlock-row">
                    <div class="field-group small">
                      <label>Level</label>
                      <input
                        type="number"
                        value={effect.Properties?.Unlock?.Level ?? 1}
                        min="1"
                        onchange={(e) => updateEffect(i, 'Properties.Unlock.Level', parseInt(e.target.value) || 1)}
                      />
                    </div>
                    <div class="field-group small">
                      <label>PED Cost</label>
                      <input
                        type="number"
                        value={effect.Properties?.Unlock?.CostPED ?? 0}
                        min="0"
                        step="0.01"
                        onchange={(e) => updateEffect(i, 'Properties.Unlock.CostPED', parseFloat(e.target.value) || 0)}
                      />
                    </div>
                  </div>
                  <div class="unlock-row">
                    <div class="field-group small">
                      <label>Essence Cost</label>
                      <input
                        type="number"
                        value={effect.Properties?.Unlock?.CostEssence ?? 0}
                        min="0"
                        onchange={(e) => updateEffect(i, 'Properties.Unlock.CostEssence', parseInt(e.target.value) || 0)}
                      />
                    </div>
                    <div class="field-group small">
                      <label>Rare Essence</label>
                      <input
                        type="number"
                        value={effect.Properties?.Unlock?.CostRareEssence ?? 0}
                        min="0"
                        onchange={(e) => updateEffect(i, 'Properties.Unlock.CostRareEssence', parseInt(e.target.value) || 0)}
                      />
                    </div>
                  </div>
                  <div class="unlock-row criteria-row">
                    <div class="field-group">
                      <label>Criteria</label>
                      <input
                        type="text"
                        value={effect.Properties?.Unlock?.Criteria || ''}
                        placeholder="e.g., Hunt creatures"
                        onchange={(e) => updateEffect(i, 'Properties.Unlock.Criteria', e.target.value || null)}
                      />
                    </div>
                    <div class="field-group small">
                      <label>Amount</label>
                      <input
                        type="number"
                        value={effect.Properties?.Unlock?.CriteriaValue ?? ''}
                        min="0"
                        placeholder="—"
                        onchange={(e) => updateEffect(i, 'Properties.Unlock.CriteriaValue', e.target.value ? parseInt(e.target.value) : null)}
                      />
                    </div>
                  </div>
                </div>
              {/if}
            </div>
          </div>
        {/each}

        <div class="btn-row">
          <button class="btn-add" onclick={addEffect}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Add Effect
          </button>
          <button class="btn-add btn-create" onclick={() => showCreateDialog = true}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="12" y1="18" x2="12" y2="12" />
              <line x1="9" y1="15" x2="15" y2="15" />
            </svg>
            Create New Effect
          </button>
        </div>
      </div>
    {:else if effects?.length > 0}
      <div class="effects-card-grid">
        {#each sortedEffects as effect}
          {@const unlock = effect.Properties?.Unlock || {}}
          {@const costParts = [
            ...(unlock.CostPED > 0 ? [`${unlock.CostPED} PED`] : []),
            ...(unlock.CostEssence > 0 ? [`${unlock.CostEssence} Animal Essence`] : []),
            ...(unlock.CostRareEssence > 0 ? [`${unlock.CostRareEssence} Rare Animal Essence`] : []),
          ]}
          <div class="skill-card">
            <div class="skill-card-top">
              <span class="skill-name">{effect.Name}</span>
              {#if unlock.Level != null}
                <span class="skill-level">Lvl {unlock.Level}</span>
              {/if}
            </div>
            <div class="skill-strength">{formatStrength(effect)}</div>
            {#if effect.Properties?.NutrioConsumptionPerHour != null}
              <div class="skill-detail">Upkeep {effect.Properties.NutrioConsumptionPerHour}/h</div>
            {/if}
            {#if costParts.length > 0}
              <div class="skill-detail">Cost: {costParts.join(', ')}</div>
            {/if}
            {#if unlock.Criteria}
              <div class="skill-detail">
                {unlock.Criteria}{unlock.CriteriaValue != null ? ` (${unlock.CriteriaValue})` : ''}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {:else}
      <div class="no-effects">No pet effects defined</div>
    {/if}
  </div>
{/if}

{#if showCreateDialog}
  <CreateEffectDialog
    on:create={handleCreateEffect}
    on:cancel={() => showCreateDialog = false}
  />
{/if}

<style>
  .pet-effects-editor {
    width: 100%;
  }

  /* Edit mode styles */
  .effects-edit-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .effect-card {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .effect-main-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .effect-search-wrapper {
    flex: 1;
    min-width: 120px;
  }

  .effect-fields-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
    min-width: 0;
  }

  .field-group.small {
    flex: 0 0 auto;
    min-width: 90px;
  }

  .field-group label {
    font-size: 11px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .input-with-unit {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .input-with-unit input {
    width: 70px;
    padding: 5px 6px;
    font-size: 12px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .input-with-unit .unit {
    font-size: 11px;
    color: var(--text-muted, #999);
  }

  .field-group input {
    padding: 5px 6px;
    font-size: 12px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .field-group input[type="text"] {
    width: 100%;
    box-sizing: border-box;
  }

  .field-group input[type="number"] {
    width: 70px;
    box-sizing: border-box;
  }

  .field-group.small input[type="number"] {
    width: 100%;
  }

  .field-group input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  /* Unlock section */
  .unlock-section {
    border-top: 1px solid var(--border-color, #555);
    padding-top: 8px;
  }

  .unlock-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 6px 8px;
    font-size: 12px;
    font-weight: 500;
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    cursor: pointer;
    transition: all 0.15s;
  }

  .unlock-toggle:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .chevron {
    transition: transform 0.15s;
  }

  .chevron.expanded {
    transform: rotate(90deg);
  }

  .unlock-summary {
    margin-left: auto;
    font-size: 11px;
    color: var(--text-muted, #999);
  }

  .unlock-fields {
    margin-top: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px;
    background-color: var(--secondary-color);
    border-radius: 4px;
  }

  .unlock-row {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    align-items: end;
  }

  .criteria-row {
    flex-wrap: wrap;
  }

  .criteria-row .field-group:first-child {
    grid-column: 1 / 2;
  }

  .criteria-row .field-group.small {
    grid-column: 2 / 3;
  }

  .criteria-row {
    grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  }

  .btn-remove {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--error-color, #ff6b6b);
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .btn-remove:hover {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  .btn-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .btn-add {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px 12px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
    flex: 1;
  }

  .btn-add:hover {
    background-color: var(--hover-color);
    color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
  }

  /* View mode — card grid */
  .effects-card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr));
    gap: 8px;
  }

  .skill-card {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .skill-card-top {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .skill-name {
    flex: 1;
    color: var(--accent-color, #60b0ff);
    font-size: 13px;
    font-weight: 600;
  }

  .skill-level {
    color: var(--text-color, white);
    font-size: 13px;
    font-weight: 700;
    white-space: nowrap;
  }

  .skill-strength {
    color: var(--text-color, white);
    font-size: 15px;
    font-weight: 700;
    margin: 2px 0;
  }

  .skill-detail {
    color: var(--text-muted, #999);
    font-size: 11px;
  }

  .no-effects {
    padding: 20px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 13px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .effects-card-grid {
      grid-template-columns: 1fr 1fr;
    }

    .effect-fields-row {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .field-group {
      min-width: 0;
    }

    .unlock-row {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .criteria-row {
      grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
    }

    .criteria-row .field-group:first-child {
      grid-column: 1 / 2;
    }
  }

  @media (max-width: 480px) {
    .effects-card-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
