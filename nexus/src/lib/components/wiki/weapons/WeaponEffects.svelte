<!--
  @component WeaponEffects
  Displays weapon effects on equip and on use.
  Supports inline editing when in edit mode.
-->
<script>
  // @ts-nocheck
  import { getTimeString } from '$lib/util';
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';

  /** @type {object} Weapon entity */
  export let weapon = null;

  /** @type {boolean} Show both equip and use effects together */
  export let combined = false;

  /** @type {string} Which effects to show: 'all', 'equip', 'use' */
  export let show = 'all';

  /** @type {Array} Available effects for dropdown */
  export let effects = [];

  $: effectsOnEquip = weapon?.EffectsOnEquip || [];
  $: effectsOnUse = weapon?.EffectsOnUse || [];

  $: showEquip = show === 'all' || show === 'equip';
  $: showUse = show === 'all' || show === 'use';

  $: hasEffects = $editMode || (showEquip && effectsOnEquip.length > 0) || (showUse && effectsOnUse.length > 0);

  // Sort effects alphabetically
  $: sortedEquipEffects = [...effectsOnEquip].sort((a, b) => a.Name?.localeCompare(b.Name) || 0);
  $: sortedUseEffects = [...effectsOnUse].sort((a, b) => a.Name?.localeCompare(b.Name) || 0);

  // Available effect names for dropdowns
  $: effectOptions = effects.map(e => ({ value: e.Name, label: e.Name }));

  function formatEffectValue(effect) {
    const strength = effect.Values?.Strength ?? '?';
    const unit = getEffectUnit(effect.Name);
    return `${strength}${unit}`;
  }

  function formatDuration(effect) {
    const duration = effect.Values?.DurationSeconds;
    if (!duration) return '';
    return `for ${getTimeString(duration)}`;
  }

  // Get unit for an effect name from effects list
  function getEffectUnit(effectName) {
    if (!effectName || !effects?.length) return '';
    const effect = effects.find(e => e.Name === effectName);
    return effect?.Properties?.Unit || '';
  }

  // === Equip Effects Editing ===
  function updateEquipEffect(index, field, value) {
    const newEffects = [...effectsOnEquip];
    if (field === 'Name') {
      newEffects[index] = {
        ...newEffects[index],
        Name: value,
        Values: {
          ...newEffects[index].Values,
          Unit: getEffectUnit(value)
        }
      };
    } else if (field === 'Strength') {
      newEffects[index] = {
        ...newEffects[index],
        Values: {
          ...newEffects[index].Values,
          Strength: value
        }
      };
    }
    updateField('EffectsOnEquip', newEffects);
  }

  function addEquipEffect() {
    const newEffects = [...effectsOnEquip, {
      Name: effects[0]?.Name || '',
      Values: {
        Strength: 0,
        Unit: effects[0]?.Unit || ''
      }
    }];
    updateField('EffectsOnEquip', newEffects);
  }

  function removeEquipEffect(index) {
    const newEffects = effectsOnEquip.filter((_, i) => i !== index);
    updateField('EffectsOnEquip', newEffects);
  }

  // === Use Effects Editing ===
  function updateUseEffect(index, field, value) {
    const newEffects = [...effectsOnUse];
    if (field === 'Name') {
      newEffects[index] = {
        ...newEffects[index],
        Name: value,
        Values: {
          ...newEffects[index].Values,
          Unit: getEffectUnit(value)
        }
      };
    } else if (field === 'Strength') {
      newEffects[index] = {
        ...newEffects[index],
        Values: {
          ...newEffects[index].Values,
          Strength: value
        }
      };
    } else if (field === 'Duration') {
      newEffects[index] = {
        ...newEffects[index],
        Values: {
          ...newEffects[index].Values,
          DurationSeconds: value
        }
      };
    }
    updateField('EffectsOnUse', newEffects);
  }

  function addUseEffect() {
    const newEffects = [...effectsOnUse, {
      Name: effects[0]?.Name || '',
      Values: {
        Strength: 0,
        Unit: effects[0]?.Unit || '',
        DurationSeconds: 0
      }
    }];
    updateField('EffectsOnUse', newEffects);
  }

  function removeUseEffect(index) {
    const newEffects = effectsOnUse.filter((_, i) => i !== index);
    updateField('EffectsOnUse', newEffects);
  }
</script>

{#if hasEffects}
  <div class="weapon-effects" class:combined class:editing={$editMode}>
    {#if showEquip}
      <div class="effects-section">
        {#if !combined || show === 'all'}
          <h4 class="effects-title">
            <span class="effects-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20.24 12.24a6 6 0 00-8.49-8.49L5 10.5V19h8.5z" />
                <line x1="16" y1="8" x2="2" y2="22" />
              </svg>
            </span>
            Effects on Equip
          </h4>
        {/if}

        {#if $editMode}
          <div class="effects-edit-list">
            {#each effectsOnEquip as effect, i}
              <div class="effect-edit-row">
                <div class="effect-row-top">
                  <select
                    class="effect-select"
                    value={effect.Name}
                    on:change={(e) => updateEquipEffect(i, 'Name', e.target.value)}
                  >
                    {#each effectOptions as opt}
                      <option value={opt.value}>{opt.label}</option>
                    {/each}
                  </select>
                  <button class="btn-remove" on:click={() => removeEquipEffect(i)} title="Remove effect">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                </div>
                <div class="effect-row-bottom equip-values">
                  <input
                    type="number"
                    class="effect-input"
                    value={effect.Values?.Strength ?? 0}
                    step="0.1"
                    min="0"
                    on:change={(e) => updateEquipEffect(i, 'Strength', parseFloat(e.target.value) || 0)}
                  />
                  <span class="effect-unit">{getEffectUnit(effect.Name)}</span>
                </div>
              </div>
            {/each}
            <button class="btn-add" on:click={addEquipEffect}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Add Effect
            </button>
          </div>
        {:else if effectsOnEquip.length > 0}
          <ul class="effects-list">
            {#each sortedEquipEffects as effect}
              <li class="effect-item equip">
                <span class="effect-name">{effect.Name}</span>
                <span class="effect-value">{formatEffectValue(effect)}</span>
              </li>
            {/each}
          </ul>
        {:else}
          <div class="no-effects-inline">No equip effects</div>
        {/if}
      </div>
    {/if}

    {#if showUse}
      <div class="effects-section">
        {#if !combined || show === 'all'}
          <h4 class="effects-title">
            <span class="effects-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
            </span>
            Effects on Use
          </h4>
        {/if}

        {#if $editMode}
          <div class="effects-edit-list">
            {#each effectsOnUse as effect, i}
              <div class="effect-edit-row use">
                <div class="effect-row-top">
                  <select
                    class="effect-select"
                    value={effect.Name}
                    on:change={(e) => updateUseEffect(i, 'Name', e.target.value)}
                  >
                    {#each effectOptions as opt}
                      <option value={opt.value}>{opt.label}</option>
                    {/each}
                  </select>
                  <button class="btn-remove" on:click={() => removeUseEffect(i)} title="Remove effect">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                </div>
                <div class="effect-row-bottom use-values">
                  <input
                    type="number"
                    class="effect-input"
                    value={effect.Values?.Strength ?? 0}
                    step="0.1"
                    min="0"
                    on:change={(e) => updateUseEffect(i, 'Strength', parseFloat(e.target.value) || 0)}
                  />
                  <span class="effect-unit">{getEffectUnit(effect.Name)}</span>
                  <span class="field-separator">for</span>
                  <input
                    type="number"
                    class="effect-input"
                    value={effect.Values?.DurationSeconds ?? 0}
                    step="0.1"
                    min="0"
                    on:change={(e) => updateUseEffect(i, 'Duration', parseFloat(e.target.value) || 0)}
                  />
                  <span class="effect-unit">s</span>
                </div>
              </div>
            {/each}
            <button class="btn-add" on:click={addUseEffect}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Add Effect
            </button>
          </div>
        {:else if effectsOnUse.length > 0}
          <ul class="effects-list">
            {#each sortedUseEffects as effect}
              <li class="effect-item use">
                <span class="effect-name">{effect.Name}</span>
                <span class="effect-details">
                  <span class="effect-value">{formatEffectValue(effect)}</span>
                  {#if effect.Values?.DurationSeconds}
                    <span class="effect-duration">{formatDuration(effect)}</span>
                  {/if}
                </span>
              </li>
            {/each}
          </ul>
        {:else}
          <div class="no-effects-inline">No use effects</div>
        {/if}
      </div>
    {/if}
  </div>
{:else}
  <div class="no-effects">No effects</div>
{/if}

<style>
  .weapon-effects {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .weapon-effects.combined {
    flex-direction: row;
    flex-wrap: wrap;
  }

  .weapon-effects.combined .effects-section {
    flex: 1;
    min-width: 200px;
  }

  .effects-section {
    width: 100%;
  }

  .effects-title {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0 0 8px 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .effects-icon {
    display: flex;
    color: var(--accent-color, #4a9eff);
  }

  .effects-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .effect-item {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 8px 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
    font-size: 13px;
    border-left: 3px solid transparent;
  }

  .effect-item.equip {
    border-left-color: var(--success-color, #4ade80);
  }

  .effect-item.use {
    border-left-color: var(--warning-color, #fbbf24);
  }

  .effect-name {
    color: var(--text-color);
    font-weight: 500;
  }

  .effect-details {
    display: flex;
    align-items: baseline;
    gap: 6px;
  }

  .effect-value {
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
  }

  .effect-duration {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .no-effects,
  .no-effects-inline {
    padding: 12px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 14px;
  }

  .no-effects-inline {
    padding: 8px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
  }

  /* Edit mode styles */
  .effects-edit-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .effect-edit-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px 10px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
    border-left: 3px solid var(--success-color, #4ade80);
  }

  .effect-edit-row.use {
    border-left-color: var(--warning-color, #fbbf24);
  }

  .effect-row-top {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .effect-row-bottom {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .effect-row-bottom.use-values,
  .effect-row-bottom.equip-values {
    flex-wrap: nowrap;
    gap: 6px;
  }

  .effect-field {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .field-label {
    font-size: 11px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .effect-select {
    flex: 1;
    min-width: 120px;
    padding: 6px 8px;
    font-size: 13px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .effect-input {
    width: 60px;
    padding: 5px 6px;
    font-size: 13px;
    text-align: left;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .effect-unit {
    font-size: 12px;
    color: var(--text-muted, #999);
    min-width: 12px;
  }

  .field-separator {
    font-size: 12px;
    color: var(--text-muted, #999);
    margin: 0 2px;
  }

  .btn-remove {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    padding: 0;
    margin-left: auto;
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

  .btn-add {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 8px 12px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-add:hover {
    background-color: var(--hover-color);
    color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
  }

  /* Mobile adjustments - aligned with global 900px breakpoint */
  @media (max-width: 899px) {
    .weapon-effects.combined {
      flex-direction: column;
    }

    .effect-item {
      padding: 6px 10px;
      font-size: 12px;
    }
  }
</style>
