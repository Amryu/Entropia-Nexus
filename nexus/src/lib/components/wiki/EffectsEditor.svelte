<!--
  @component EffectsEditor
  Generic effects array editor component.
  Supports EffectsOnEquip, EffectsOnUse, EffectsOnConsume arrays with add/edit/remove functionality.
  Based on WeaponEffects.svelte pattern.
-->
<script>
  // @ts-nocheck
  import { getTimeString } from '$lib/util';
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';

  /** @type {Array} Effects array to display/edit */
  export let effects = [];

  /** @type {string} Field path for updateField (e.g., 'EffectsOnEquip', 'EffectsOnConsume') */
  export let fieldName = 'EffectsOnEquip';

  /** @type {Array} Available effects for dropdown [{Name, Properties: {Unit}}] */
  export let availableEffects = [];

  /** @type {string} Effect type: 'equip', 'use', 'consume' - determines UI/features */
  export let effectType = 'equip';

  /** @type {string} Section title */
  export let title = '';

  /** @type {boolean} Whether to show the section even when empty */
  export let showEmpty = false;

  // Computed title based on effect type if not provided
  $: displayTitle = title || (effectType === 'equip' ? 'Effects on Equip' : effectType === 'use' ? 'Effects on Use' : 'Effects on Consume');

  // Whether effects have duration (use and consume types)
  $: hasDuration = effectType === 'use' || effectType === 'consume';

  // Sort effects alphabetically for display
  $: sortedEffects = [...(effects || [])].sort((a, b) => a.Name?.localeCompare(b.Name) || 0);

  // Available effect names for dropdowns
  $: effectOptions = (availableEffects || []).map(e => ({ value: e.Name, label: e.Name }));

  // Show section if has effects, in edit mode, or showEmpty is true
  $: shouldShow = $editMode || (effects?.length > 0) || showEmpty;

  // Get unit for an effect name from availableEffects list
  function getEffectUnit(effectName, currentEffect = null) {
    if (!effectName || !availableEffects?.length) {
      return currentEffect?.Values?.Unit || '';
    }
    const matched = availableEffects.find(e => e.Name === effectName);
    if (matched?.Properties?.Unit) return matched.Properties.Unit;
    return currentEffect?.Values?.Unit || matched?.Values?.Unit || '';
  }

  function formatEffectValue(effect) {
    const strength = effect.Values?.Strength ?? effect.Values?.Value ?? '?';
    const unit = getEffectUnit(effect.Name, effect) || effect.Values?.Unit || '';
    return `${strength}${unit}`;
  }

  function formatDuration(effect) {
    const duration = effect.Values?.DurationSeconds;
    if (!duration) return '';
    return `for ${getTimeString(duration)}`;
  }

  // === Effect CRUD Operations ===
  function updateEffect(index, field, value) {
    const newEffects = [...effects];
    if (field === 'Name') {
      newEffects[index] = {
        ...newEffects[index],
        Name: value,
        Values: {
          ...newEffects[index].Values,
          Unit: getEffectUnit(value, newEffects[index])
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
    updateField(fieldName, newEffects);
  }

  function addEffect() {
    const newEffect = {
      Name: effectOptions[0]?.value || '',
      Values: {
        Strength: 0,
        Unit: availableEffects[0]?.Properties?.Unit || ''
      }
    };

    // Add duration for use/consume effects
    if (hasDuration) {
      newEffect.Values.DurationSeconds = 0;
    }

    updateField(fieldName, [...effects, newEffect]);
  }

  function removeEffect(index) {
    updateField(fieldName, effects.filter((_, i) => i !== index));
  }

  // Get CSS class for effect type
  function getEffectClass() {
    return effectType === 'equip' ? 'equip' : 'use';
  }
</script>

{#if shouldShow}
  <div class="effects-editor" class:editing={$editMode}>
    <h4 class="effects-title">
      <span class="effects-icon">
        {#if effectType === 'equip'}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20.24 12.24a6 6 0 00-8.49-8.49L5 10.5V19h8.5z" />
            <line x1="16" y1="8" x2="2" y2="22" />
          </svg>
        {:else}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        {/if}
      </span>
      {displayTitle}
    </h4>

    {#if $editMode}
      <div class="effects-edit-list">
        {#each effects as effect, i}
          <div class="effect-edit-row" class:use={hasDuration}>
            <div class="effect-row-top">
              <select
                class="effect-select"
                value={effect.Name}
                on:change={(e) => updateEffect(i, 'Name', e.target.value)}
              >
                {#each effectOptions as opt}
                  <option value={opt.value}>{opt.label}</option>
                {/each}
              </select>
              <button class="btn-remove" on:click={() => removeEffect(i)} title="Remove effect">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div class="effect-row-bottom" class:has-duration={hasDuration}>
              <input
                type="number"
                class="effect-input"
                value={effect.Values?.Strength ?? 0}
                step="0.1"
                min="0"
                on:change={(e) => updateEffect(i, 'Strength', parseFloat(e.target.value) || 0)}
              />
              <span class="effect-unit">{getEffectUnit(effect.Name)}</span>
              {#if hasDuration}
                <span class="field-separator">for</span>
                <input
                  type="number"
                  class="effect-input"
                  value={effect.Values?.DurationSeconds ?? 0}
                  step="0.1"
                  min="0"
                  on:change={(e) => updateEffect(i, 'Duration', parseFloat(e.target.value) || 0)}
                />
                <span class="effect-unit">s</span>
              {/if}
            </div>
          </div>
        {/each}
        <button class="btn-add" on:click={addEffect}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Effect
        </button>
      </div>
    {:else if effects?.length > 0}
      <ul class="effects-list">
        {#each sortedEffects as effect}
          <li class="effect-item {getEffectClass()}">
            <span class="effect-name">{effect.Name}</span>
            <span class="effect-details">
              <span class="effect-value">{formatEffectValue(effect)}</span>
              {#if hasDuration && effect.Values?.DurationSeconds}
                <span class="effect-duration">{formatDuration(effect)}</span>
              {/if}
            </span>
          </li>
        {/each}
      </ul>
    {:else}
      <div class="no-effects">No effects</div>
    {/if}
  </div>
{/if}

<style>
  .effects-editor {
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

  .no-effects {
    padding: 8px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 14px;
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
    gap: 6px;
    flex-wrap: nowrap;
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
    .effect-item {
      padding: 6px 10px;
      font-size: 12px;
    }
  }
</style>
