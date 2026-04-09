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
    effectsCatalog = [],
    effectCaps = {}
  } = $props();

  let customRows = $state([]);

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
    if (activePresets.has(preset.id)) {
      // Remove this preset's targets
      for (const key of Object.keys(preset.targets)) {
        delete newTargets[key];
      }
    } else {
      // Add this preset's targets
      for (const [key, value] of Object.entries(preset.targets)) {
        newTargets[key] = value;
      }
    }
    targets = newTargets;
  }

  function addCustomRow() {
    // Find an effect not already targeted
    const usedNames = new Set([...Object.keys(targets), ...customRows.map(r => r.effectName)]);
    const available = targetableEffects.find(e => !usedNames.has(e.Name));
    if (!available) return;
    const cap = effectCaps[available.Name]?.total ?? 100;
    customRows = [...customRows, { effectName: available.Name, value: cap }];
    targets = { ...targets, [available.Name]: cap };
  }

  function removeCustomRow(index) {
    const row = customRows[index];
    const newTargets = { ...targets };
    delete newTargets[row.effectName];
    targets = newTargets;
    customRows = customRows.filter((_, i) => i !== index);
  }

  function updateCustomEffect(index, newEffectName) {
    const oldName = customRows[index].effectName;
    const cap = effectCaps[newEffectName]?.total ?? 100;
    const newTargets = { ...targets };
    delete newTargets[oldName];
    newTargets[newEffectName] = cap;
    targets = newTargets;
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
    customRows = [];
  }
</script>

<div class="target-panel">
  <div class="target-header">
    <h3>Target Effects</h3>
    {#if Object.keys(targets).length > 0}
      <button type="button" class="btn-text" onclick={clearAll}>Clear all</button>
    {/if}
  </div>

  <div class="preset-row">
    {#each EFFECT_PRESETS as preset (preset.id)}
      <button
        type="button"
        class="preset-btn"
        class:active={activePresets.has(preset.id)}
        onclick={() => togglePreset(preset)}
        title={Object.entries(preset.targets).map(([k, v]) => `${k}: ${v}`).join(', ')}
      >
        {preset.label}
      </button>
    {/each}
  </div>

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

  .btn-text {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 12px;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
  }

  .btn-text:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
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
