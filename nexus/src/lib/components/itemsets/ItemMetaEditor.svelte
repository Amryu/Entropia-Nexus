<!--
  @component ItemMetaEditor
  Inline metadata editor for a single item in an item set.
  Detects item type and shows relevant fields (tier, TiR, currentTT, QR, gender, pet data).
-->
<script>
  // @ts-nocheck
  import { TIERABLE_TYPES, CONDITION_TYPES, isLimitedByName } from '$lib/common/itemTypes.js';
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {object} Item entry: { itemId, type, name, quantity, meta } item
   * @property {string|null} [itemGender]
   * @property {number|null} [maxTT]
   * @property {number|null} [minTT]
   * @property {Array} [petEffects]
   */

  /** @type {Props} */
  let {
    item,
    itemGender = null,
    maxTT = null,
    minTT = null,
    petEffects = []
  } = $props();

  let meta = $derived(item?.meta || {});
  let type = $derived(item?.type || '');
  let name = $derived(item?.name || '');
  let isLimited = $derived(isLimitedByName(name));
  let isTierable = $derived(TIERABLE_TYPES.has(type) && !isLimited);
  let hasCondition = $derived(CONDITION_TYPES.has(type));
  let isBlueprint = $derived(type === 'Blueprint' && !isLimited);
  let isUnisex = $derived(itemGender === 'Both');
  let isPet = $derived(type === 'Pet');
  let maxTTKnown = $derived(maxTT != null && maxTT > 0);

  function updateMeta(field, value) {
    const newMeta = { ...meta, [field]: value };
    dispatch('change', newMeta);
  }

  function updatePetField(field, value) {
    const pet = { ...(meta.pet || {}), [field]: value };
    dispatch('change', { ...meta, pet });
  }

  function updatePetSkill(skillName, value) {
    const skills = { ...(meta.pet?.skills || {}), [skillName]: value };
    const pet = { ...(meta.pet || {}), skills };
    dispatch('change', { ...meta, pet });
  }
</script>

<div class="item-meta-editor">
  {#if isTierable}
    <div class="meta-row">
      <label class="meta-label">Tier</label>
      <input
        type="number"
        class="meta-input meta-input-small"
        value={meta.tier ?? ''}
        min="0"
        max="9"
        step="1"
        placeholder="0"
        onchange={(e) => updateMeta('tier', e.target.value === '' ? null : Math.floor(Number(e.target.value)))}
      />
    </div>
    <div class="meta-row">
      <label class="meta-label">TiR</label>
      <input
        type="number"
        class="meta-input meta-input-small"
        value={meta.tiR ?? ''}
        min="0"
        step="0.01"
        placeholder="0.00"
        onchange={(e) => updateMeta('tiR', e.target.value === '' ? null : Number(e.target.value))}
      />
    </div>
  {/if}

  {#if hasCondition}
    <div class="meta-row">
      <label class="meta-label">TT</label>
      <input
        type="number"
        class="meta-input"
        value={meta.currentTT ?? ''}
        min="0"
        max={maxTTKnown ? maxTT : 10000}
        step="0.01"
        placeholder={maxTTKnown ? `0 - ${maxTT}` : '0.00'}
        onchange={(e) => updateMeta('currentTT', e.target.value === '' ? null : Number(e.target.value))}
      />
      {#if !maxTTKnown}
        <span class="meta-warning" title="MaxTT unknown, value is not clamped">?</span>
      {/if}
    </div>
  {/if}

  {#if isBlueprint}
    <div class="meta-row">
      <label class="meta-label">QR</label>
      <input
        type="number"
        class="meta-input meta-input-small"
        value={meta.qr ?? ''}
        min="0.01"
        max="1"
        step="0.0001"
        placeholder="0.0100"
        onchange={(e) => updateMeta('qr', e.target.value === '' ? null : Number(e.target.value))}
      />
    </div>
  {/if}

  {#if isUnisex}
    <div class="meta-row">
      <label class="meta-label">Gender</label>
      <select
        class="meta-select"
        value={meta.gender || ''}
        onchange={(e) => updateMeta('gender', e.target.value || null)}
      >
        <option value="">Select...</option>
        <option value="Male">Male</option>
        <option value="Female">Female</option>
      </select>
    </div>
  {/if}

  {#if isPet}
    <div class="meta-row">
      <label class="meta-label">Level</label>
      <input
        type="number"
        class="meta-input meta-input-small"
        value={meta.pet?.level ?? ''}
        min="0"
        max="200"
        step="1"
        placeholder="0"
        onchange={(e) => updatePetField('level', e.target.value === '' ? null : Math.floor(Number(e.target.value)))}
      />
    </div>
    <div class="meta-row">
      <label class="meta-label">Fed</label>
      <input
        type="number"
        class="meta-input"
        value={meta.pet?.currentTT ?? ''}
        min="0"
        step="0.01"
        placeholder="0.00"
        onchange={(e) => updatePetField('currentTT', e.target.value === '' ? null : Number(e.target.value))}
      />
    </div>
    {#if petEffects.length > 0}
      <div class="meta-pet-skills">
        <span class="meta-label">Skills</span>
        <div class="pet-skill-list">
          {#each petEffects as effect}
            <label class="pet-skill-toggle">
              <input
                type="checkbox"
                checked={meta.pet?.skills?.[effect] ?? false}
                onchange={(e) => updatePetSkill(effect, e.target.checked)}
              />
              <span>{effect}</span>
            </label>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</div>

<style>
  .item-meta-editor {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 12px;
    align-items: center;
  }

  .meta-row {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .meta-label {
    font-size: 11px;
    color: var(--text-muted, #999);
    white-space: nowrap;
  }

  .meta-input {
    width: 80px;
    padding: 4px 6px;
    font-size: 12px;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
  }

  .meta-input-small {
    width: 55px;
  }

  .meta-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .meta-select {
    padding: 4px 6px;
    font-size: 12px;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
  }

  .meta-select:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .meta-warning {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    font-size: 11px;
    font-weight: 600;
    border-radius: 50%;
    background-color: var(--warning-bg);
    color: var(--warning-color);
    cursor: help;
    flex-shrink: 0;
  }

  .meta-pet-skills {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .pet-skill-list {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 8px;
  }

  .pet-skill-toggle {
    display: flex;
    align-items: center;
    gap: 3px;
    font-size: 11px;
    color: var(--text-color);
    cursor: pointer;
  }

  .pet-skill-toggle input[type="checkbox"] {
    width: 14px;
    height: 14px;
    accent-color: var(--accent-color);
  }

  /* Remove spinner arrows on number inputs */
  .meta-input::-webkit-outer-spin-button,
  .meta-input::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }
  .meta-input[type=number] {
    -moz-appearance: textfield;
  }
</style>
