<!--
  @component EffectSlotCard
  Reusable equipment slot card with EntityPicker, effect preview, MU config,
  and per-slot suggestion button.
-->
<script>
  // @ts-nocheck
  import EntityPicker from './EntityPicker.svelte';
  import { extractEquipEffects, extractArmorSetEffects, extractPetEffect, getPetEffectKey } from './effectOptimizer.js';
  import { getEffectStrength } from '$lib/utils/loadoutEffects.js';
  import { hasCondition } from '$lib/shopUtils.js';

  let {
    label = '',
    slotType = 'item',
    entities = [],
    selected = $bindable(null),
    markupData = {},
    markupSource = $bindable('custom'),
    markupPercent = $bindable(100),
    effectsCatalog = [],
    armorSetPieces = $bindable(7),
    petActiveEffect = $bindable(null),
    excludeName = null,
    onselect = () => {},
    onclear = () => {},
    onmuSourceChange = null,
    onmuValueChange = null,
    onsuggest = null,
    suggesting = false,
    compact = false
  } = $props();

  let selectedEntity = $derived(
    selected ? entities.find(e => e.Name === selected) || null : null
  );

  let effects = $derived.by(() => {
    if (!selectedEntity) return [];
    if (slotType === 'armorSet') {
      return extractArmorSetEffects(selectedEntity, armorSetPieces);
    }
    if (slotType === 'pet') {
      if (!petActiveEffect) return [];
      const eff = extractPetEffect(selectedEntity, petActiveEffect);
      return eff ? [eff] : [];
    }
    return extractEquipEffects(selectedEntity);
  });

  let allPetEffects = $derived(
    slotType === 'pet' && selectedEntity?.Effects ? selectedEntity.Effects : []
  );

  // Filter out excluded items (e.g., prevent same ring in both slots)
  let filteredEntities = $derived(
    excludeName ? entities.filter(e => e.Name !== excludeName) : entities
  );

  function handleSelect(item) {
    selected = item?.Name ?? null;
    if (slotType === 'pet' && item?.Effects?.length > 0) {
      petActiveEffect = getPetEffectKey(item.Effects[0]);
    }
    onselect(item);
  }

  function handleClear() {
    selected = null;
    if (slotType === 'pet') petActiveEffect = null;
    onclear();
  }

  function resolveMarkup(itemName, source, customValue) {
    const fallbackDefault = isAbsoluteMU ? 0 : 100;
    if (!itemName) return customValue ?? fallbackDefault;
    // Try the selected source
    if (source !== 'custom') {
      if (source === 'inventory' && markupData.inventoryMap) {
        const id = markupData.nameToId?.get(itemName);
        if (id != null && markupData.inventoryMap.has(id)) return markupData.inventoryMap.get(id);
      }
      if (source === 'ingame' && markupData.ingameMap?.has(itemName)) return markupData.ingameMap.get(itemName);
      if (source === 'exchange' && markupData.wapByName?.has(itemName)) return markupData.wapByName.get(itemName);
    }
    // Custom mode or fallback: use custom value, then try fallback chain
    if (customValue != null && customValue !== '' && customValue !== fallbackDefault) return customValue;
    if (markupData.inventoryMap) {
      const id = markupData.nameToId?.get(itemName);
      if (id != null && markupData.inventoryMap.has(id)) return markupData.inventoryMap.get(id);
    }
    if (markupData.ingameMap?.has(itemName)) return markupData.ingameMap.get(itemName);
    if (markupData.wapByName?.has(itemName)) return markupData.wapByName.get(itemName);
    return customValue ?? fallbackDefault;
  }

  // Absolute MU: items with MaxTT (condition items like rings, weapons, pets, armor)
  // hasCondition checks Properties.Type against CONDITION_TYPES, but clothing subtypes
  // (Ring, Gloves, etc.) aren't in that set. Fall back to checking for MaxTT existence.
  // Absolute MU: items with MaxTT (condition items like rings, weapons, pets, armor)
  // hasCondition checks Properties.Type against CONDITION_TYPES, but clothing subtypes
  // (Ring, Gloves, etc.) aren't in that set. Fall back to checking for MaxTT existence.
  let isAbsoluteMU = $derived.by(() => {
    if (!selectedEntity) return false;
    if (hasCondition(selectedEntity)) return true;
    const tt = selectedEntity.Properties?.Economy?.MaxTT ?? selectedEntity.Properties?.MaxTT ?? null;
    return tt != null && tt > 0;
  });

  let editingMU = $state(false);

  // Determine which fallback source is being used when custom is empty
  let fallbackSource = $derived.by(() => {
    if (markupSource !== 'custom') return null;
    const def = isAbsoluteMU ? 0 : 100;
    if (markupPercent != null && markupPercent !== '' && markupPercent !== def) return null;
    if (!selected) return null;
    if (markupData.inventoryMap) {
      const id = markupData.nameToId?.get(selected);
      if (id != null && markupData.inventoryMap.has(id)) return 'INV';
    }
    if (markupData.ingameMap?.has(selected)) return 'IGM';
    if (markupData.wapByName?.has(selected)) return 'EXC';
    return null;
  });

  let resolvedMarkup = $derived(resolveMarkup(selected, markupSource, markupPercent));
  let hasCustomValue = $derived.by(() => {
    const def = isAbsoluteMU ? 0 : 100;
    return markupPercent != null && markupPercent !== '' && markupPercent !== def;
  });

  function formatMU(value) {
    if (isAbsoluteMU) return `+${Number(value)?.toFixed?.(2) ?? '0.00'} PED`;
    return `${Number(value)?.toFixed?.(1) ?? '100'}%`;
  }

  function startEditMU() {
    if (markupSource !== 'custom') return;
    editingMU = true;
  }

  function commitMU(e) {
    editingMU = false;
    const val = e.target.value.trim();
    if (val === '') {
      // Clear to reset to fallback
      markupPercent = isAbsoluteMU ? 0 : 100;
      if (onmuValueChange) onmuValueChange(markupPercent);
    } else {
      const parsed = Number(val);
      if (Number.isFinite(parsed)) {
        markupPercent = parsed;
        if (onmuValueChange) onmuValueChange(parsed);
      }
    }
  }

  function handleMUKeydown(e) {
    if (e.key === 'Enter') e.target.blur();
    else if (e.key === 'Escape') { editingMU = false; }
  }

  function autofocus(node) { node.focus(); node.select(); }

  const MU_SOURCES = [
    { key: 'custom', label: 'Custom' },
    { key: 'inventory', label: 'Inventory' },
    { key: 'ingame', label: 'In-Game' },
    { key: 'exchange', label: 'Exchange' },
  ];
</script>

<div class="slot-card" class:compact>
  <div class="slot-header">
    <span class="slot-label">{label}</span>
    {#if onsuggest}
      <button
        type="button"
        class="btn-suggest"
        onclick={onsuggest}
        disabled={suggesting}
        title="Suggest best item for this slot"
      >
        {suggesting ? '...' : 'Suggest'}
      </button>
    {/if}
  </div>

  {#if entities.length === 0}
    <div class="empty-slot">No items with effects</div>
  {:else}
    <EntityPicker
      entities={filteredEntities}
      selected={selectedEntity}
      placeholder="Search {label.toLowerCase()}..."
      onselect={handleSelect}
      onclear={handleClear}
    />
  {/if}

  {#if slotType === 'armorSet' && selectedEntity}
    {@const breakpoints = [...new Set(
      (selectedEntity.EffectsOnSetEquip || [])
        .map(e => e?.Values?.MinSetPieces ?? e?.MinSetPieces ?? 0)
        .filter(n => n > 0)
    )].sort((a, b) => a - b)}
    <div class="pieces-row">
      <label class="pieces-label">Pieces equipped</label>
      <select class="pieces-select" bind:value={armorSetPieces}>
        {#each breakpoints as n}
          <option value={n}>{n}</option>
        {/each}
      </select>
    </div>
  {/if}

  {#if slotType === 'pet' && selectedEntity && allPetEffects.length > 0}
    <div class="pet-effect-row">
      <label class="pet-effect-label">Active buff</label>
      <select
        class="pet-effect-select"
        value={petActiveEffect}
        onchange={(e) => { petActiveEffect = e.target.value; }}
      >
        {#each allPetEffects as eff (getPetEffectKey(eff))}
          <option value={getPetEffectKey(eff)}>
            {eff.Name} ({getEffectStrength(eff)}{eff.Properties?.Unit || eff.Values?.Unit || ''})
          </option>
        {/each}
      </select>
    </div>
  {/if}

  {#if effects.length > 0}
    <div class="effect-preview">
      {#each effects as eff (eff.Name)}
        <div class="effect-row">
          <span class="effect-name">{eff.Name}</span>
          <span class="effect-value">
            {getEffectStrength(eff)}{eff.Values?.Unit || eff.Properties?.Unit || ''}
          </span>
        </div>
      {/each}
    </div>
  {/if}

  {#if selectedEntity}
    <div class="mu-section">
      <div class="mu-source-toggle">
        {#each MU_SOURCES as src (src.key)}
          <button
            type="button"
            class="mu-btn"
            class:active={markupSource === src.key}
            onclick={() => { markupSource = src.key; if (onmuSourceChange) onmuSourceChange(src.key); }}
          >{src.label}</button>
        {/each}
      </div>
      <div class="mu-value-row">
        <span class="mu-label">Markup:</span>
        {#if markupSource === 'custom' && editingMU}
          <input
            type="number"
            class="mu-edit-input"
            value={hasCustomValue ? markupPercent : ''}
            placeholder={formatMU(resolvedMarkup)}
            min={isAbsoluteMU ? 0 : 100}
            step={isAbsoluteMU ? 0.01 : 1}
            inputmode="decimal"
            onblur={commitMU}
            onkeydown={handleMUKeydown}
            use:autofocus
          />
          <span class="mu-unit">{isAbsoluteMU ? 'PED' : '%'}</span>
        {:else if markupSource === 'custom'}
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <span
            class="mu-value-editable"
            class:is-fallback={!hasCustomValue}
            onclick={startEditMU}
            onkeydown={(e) => { if (e.key === 'Enter') startEditMU(); }}
            role="button"
            tabindex="0"
          >{formatMU(resolvedMarkup)}</span>
          {#if fallbackSource}
            <span class="mu-source-badge" title="Using {fallbackSource === 'INV' ? 'inventory' : fallbackSource === 'IGM' ? 'in-game' : 'exchange'} value">{fallbackSource}</span>
          {/if}
        {:else}
          <span class="mu-value-readonly">{formatMU(resolvedMarkup)}</span>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .slot-card {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background-color: var(--secondary-color);
    min-width: 0;
  }

  .slot-card.compact {
    padding: 8px;
    gap: 4px;
  }

  .empty-slot {
    padding: 8px 10px;
    font-size: 12px;
    color: var(--text-muted);
    background-color: var(--bg-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    text-align: center;
    opacity: 0.6;
  }

  .slot-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .slot-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .btn-suggest {
    padding: 2px 8px;
    font-size: 11px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: transparent;
    color: var(--accent-color);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-suggest:hover:not(:disabled) {
    background-color: var(--accent-color);
    color: white;
  }

  .btn-suggest:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .pieces-row, .pet-effect-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .pieces-label, .pet-effect-label {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .pieces-select {
    width: 50px;
    padding: 3px 6px;
    font-size: 12px;
    background-color: var(--bg-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
  }

  .pet-effect-select {
    flex: 1;
    min-width: 0;
    padding: 3px 6px;
    font-size: 12px;
    background-color: var(--bg-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
  }

  .effect-preview {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 4px 6px;
    background-color: var(--bg-color);
    border-radius: 4px;
  }

  .effect-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
  }

  .effect-name {
    color: var(--text-muted);
  }

  .effect-value {
    color: var(--text-color);
    font-weight: 500;
    font-variant-numeric: tabular-nums;
  }

  .mu-section {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .mu-source-toggle {
    display: flex;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .mu-btn {
    flex: 1;
    padding: 3px 4px;
    font-size: 11px;
    border: none;
    border-right: 1px solid var(--border-color);
    background-color: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.1s ease;
    text-align: center;
    white-space: nowrap;
  }

  .mu-btn:last-child {
    border-right: none;
  }

  .mu-btn:hover {
    background-color: var(--hover-color);
  }

  .mu-btn.active {
    background-color: var(--accent-color);
    color: white;
  }

  .mu-value-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .mu-label {
    font-size: 11px;
    color: var(--text-muted);
  }

  .mu-value-editable {
    font-size: 13px;
    color: var(--text-color);
    font-variant-numeric: tabular-nums;
    border-bottom: 1px dashed var(--text-muted);
    cursor: pointer;
    padding-bottom: 1px;
  }

  .mu-value-editable:hover {
    border-bottom-color: var(--accent-color);
    color: var(--accent-color);
  }

  .mu-value-editable.is-fallback {
    opacity: 0.6;
  }

  .mu-value-readonly {
    font-size: 13px;
    color: var(--text-color);
    font-variant-numeric: tabular-nums;
  }

  .mu-edit-input {
    width: 70px;
    padding: 2px 6px;
    font-size: 13px;
    background-color: var(--bg-color);
    border: 1px solid var(--accent-color);
    border-radius: 4px;
    color: var(--text-color);
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .mu-unit {
    font-size: 11px;
    color: var(--text-muted);
  }

  .mu-source-badge {
    font-size: 9px;
    color: var(--text-muted);
    margin-left: 3px;
    padding: 0 3px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    vertical-align: middle;
  }
</style>
