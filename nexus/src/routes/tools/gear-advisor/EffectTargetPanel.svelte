<!--
  @component EffectTargetPanel
  Preset buttons + custom target builder for the Effect Optimizer.
  Emits targets as a plain object { effectName: targetValue }.
-->
<script>
  // @ts-nocheck
  import { EFFECT_PRESETS, getTargetableEffects } from './effectOptimizer.js';

  let {
    targets = $bindable({}),
    priorities = $bindable([]),
    effectsCatalog = [],
    effectCaps = {}
  } = $props();

  let customRows = $state([]);

  function getEffectiveCap(effectName) {
    const caps = effectCaps[effectName];
    if (!caps) return 100;
    const item = caps.item ?? Infinity;
    const total = caps.total ?? Infinity;
    const effective = Math.min(item, total);
    return Number.isFinite(effective) ? effective : 100;
  }

  function getEffectUnit(effectName) {
    const eff = effectsCatalog.find(e => e?.Name === effectName);
    return eff?.Properties?.Unit || '';
  }

  let targetableEffects = $derived(getTargetableEffects(effectsCatalog));

  // Track which presets are active based on current targets
  let activePresets = $derived.by(() => {
    const active = new Set();
    for (const preset of EFFECT_PRESETS) {
      const keys = Object.keys(preset.targets);
      if (keys.length === 0) continue;
      const allMatch = keys.every(k => targets[k] != null && Math.abs(targets[k] - preset.targets[k]) < 0.01);
      if (allMatch) active.add(preset.id);
    }
    return active;
  });

  function togglePreset(preset) {
    const newTargets = { ...targets };
    let newPriorities = [...priorities];
    if (activePresets.has(preset.id)) {
      for (const key of Object.keys(preset.targets)) {
        delete newTargets[key];
        newPriorities = newPriorities.filter(p => p !== key);
      }
    } else {
      for (const [key, value] of Object.entries(preset.targets)) {
        newTargets[key] = value;
        if (!newPriorities.includes(key)) newPriorities.push(key);
      }
    }
    targets = newTargets;
    priorities = newPriorities;
  }

  function addCustomRow() {
    // Find an effect not already targeted
    const usedNames = new Set([...Object.keys(targets), ...customRows.map(r => r.effectName)]);
    const available = targetableEffects.find(e => !usedNames.has(e.Name));
    if (!available) return;
    const cap = getEffectiveCap(available.Name);
    customRows = [...customRows, { effectName: available.Name, value: cap }];
    targets = { ...targets, [available.Name]: cap };
    if (!priorities.includes(available.Name)) priorities = [...priorities, available.Name];
  }

  function removeCustomRow(index) {
    const row = customRows[index];
    const newTargets = { ...targets };
    delete newTargets[row.effectName];
    targets = newTargets;
    priorities = priorities.filter(p => p !== row.effectName);
    customRows = customRows.filter((_, i) => i !== index);
  }

  function updateCustomEffect(index, newEffectName) {
    const oldName = customRows[index].effectName;
    const cap = getEffectiveCap(newEffectName);
    const newTargets = { ...targets };
    delete newTargets[oldName];
    newTargets[newEffectName] = cap;
    targets = newTargets;
    priorities = priorities.map(p => p === oldName ? newEffectName : p);
    customRows = customRows.map((r, i) => i === index ? { effectName: newEffectName, value: cap } : r);
  }

  function updateCustomValue(index, newValue) {
    const parsed = Number(newValue);
    if (!Number.isFinite(parsed) || parsed <= 0) return;
    const row = customRows[index];
    targets = { ...targets, [row.effectName]: parsed };
    customRows = customRows.map((r, i) => i === index ? { ...r, value: parsed } : r);
  }

  function clearAll() {
    targets = {};
    priorities = [];
    customRows = [];
  }

  function movePriority(effectName, direction) {
    const idx = priorities.indexOf(effectName);
    if (idx < 0) return;
    const newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= priorities.length) return;
    const arr = [...priorities];
    [arr[idx], arr[newIdx]] = [arr[newIdx], arr[idx]];
    priorities = arr;
  }
</script>

<div class="target-panel">
  <div class="target-header">
    <h3>Target Effects</h3>
    {#if Object.keys(targets).length > 0}
      <button type="button" class="btn-clear" onclick={clearAll}>Clear all</button>
    {/if}
  </div>

  <div class="preset-row">
    {#each EFFECT_PRESETS as preset (preset.id)}
      <button
        type="button"
        class="preset-btn"
        class:active={activePresets.has(preset.id)}
        onclick={() => togglePreset(preset)}
        title={Object.entries(preset.targets).map(([k, v]) => `${k}: ${v}${getEffectUnit(k)}`).join(', ')}
      >
        {preset.label}
      </button>
    {/each}
  </div>

  {#if priorities.length > 1}
    <div class="priority-order">
      <span class="priority-label">Priority:</span>
      {#each priorities as effectName, i (effectName)}
        <div class="priority-item">
          <span class="priority-rank">{i + 1}.</span>
          <span class="priority-name">{effectName}</span>
          <button type="button" class="priority-btn" disabled={i === 0} onclick={() => movePriority(effectName, -1)} title="Higher priority">^</button>
          <button type="button" class="priority-btn" disabled={i === priorities.length - 1} onclick={() => movePriority(effectName, 1)} title="Lower priority">v</button>
        </div>
      {/each}
    </div>
  {/if}

  {#if customRows.length > 0}
    <div class="custom-targets">
      {#each customRows as row, i (i)}
        <div class="custom-row">
          <select
            class="effect-select"
            value={row.effectName}
            onchange={(e) => updateCustomEffect(i, e.target.value)}
          >
            {#each targetableEffects as effect (effect.Name)}
              <option value={effect.Name} disabled={effect.Name !== row.effectName && targets[effect.Name] != null}>
                {effect.Name}
              </option>
            {/each}
          </select>
          <input
            type="number"
            class="target-input"
            value={row.value}
            min="0.1"
            step="0.5"
            onchange={(e) => updateCustomValue(i, e.target.value)}
          />
          <span class="target-unit">{effectsCatalog.find(e => e.Name === row.effectName)?.Properties?.Unit || ''}</span>
          <button type="button" class="btn-icon-sm" onclick={() => removeCustomRow(i)} title="Remove">x</button>
        </div>
      {/each}
    </div>
  {/if}

  <button type="button" class="btn-add-custom" onclick={addCustomRow}>
    + Custom target
  </button>
</div>

<style>
  .target-panel {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .target-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .target-header h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .btn-clear {
    padding: 4px 10px;
    font-size: 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--secondary-color);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-clear:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .priority-order {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: 6px 8px;
    background-color: var(--bg-color);
    border-radius: 6px;
  }

  .priority-label {
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 500;
    margin-bottom: 2px;
  }

  .priority-item {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
  }

  .priority-rank {
    color: var(--text-muted);
    font-weight: 600;
    min-width: 18px;
  }

  .priority-name {
    flex: 1;
    min-width: 0;
    color: var(--text-color);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .priority-btn {
    width: 18px;
    height: 18px;
    padding: 0;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background-color: transparent;
    color: var(--text-muted);
    font-size: 10px;
    line-height: 1;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .priority-btn:hover:not(:disabled) {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .priority-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .preset-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .preset-btn {
    padding: 5px 10px;
    font-size: 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
  }

  .preset-btn:hover {
    background-color: var(--hover-color);
  }

  .preset-btn.active {
    background-color: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
  }

  .custom-targets {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .custom-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .effect-select {
    flex: 1;
    min-width: 0;
    padding: 5px 8px;
    font-size: 12px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
  }

  .target-input {
    width: 70px;
    padding: 5px 8px;
    font-size: 12px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
    text-align: right;
  }

  .target-unit {
    font-size: 11px;
    color: var(--text-muted);
    min-width: 16px;
  }

  .btn-icon-sm {
    width: 22px;
    height: 22px;
    padding: 0;
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 14px;
    cursor: pointer;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .btn-icon-sm:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .btn-add-custom {
    align-self: flex-start;
    padding: 4px 10px;
    font-size: 12px;
    border: 1px dashed var(--border-color);
    border-radius: 6px;
    background-color: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-add-custom:hover {
    color: var(--text-color);
    border-color: var(--text-muted);
    background-color: var(--hover-color);
  }
</style>
