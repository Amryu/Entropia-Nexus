<!--
  @component EffectTargetPanel
  Preset buttons + custom target builder for the Effect Optimizer.
  Emits targets as a plain object { effectName: targetValue }.
-->
<script>
  // @ts-nocheck
  import { EFFECT_PRESETS, categorizeEffects } from './effectOptimizer.js';

  let {
    targets = $bindable({}),
    priorities = $bindable([]),
    effectsCatalog = [],
    effectCaps = {}
  } = $props();

  let customRows = $state([]);
  let pickerOpen = $state(false);
  let pickerCallback = $state(null);

  function getEffectiveCap(effectName) {
    const caps = effectCaps[effectName];
    if (!caps) return null;
    const item = caps.item ?? Infinity;
    const total = caps.total ?? Infinity;
    const effective = Math.min(item, total);
    return Number.isFinite(effective) ? effective : null;
  }

  function getEffectUnit(effectName) {
    const eff = effectsCatalog.find(e => e?.Name === effectName);
    return eff?.Properties?.Unit || '';
  }

  let categories = $derived(categorizeEffects(effectsCatalog, effectCaps));
  let usedNames = $derived(new Set(Object.keys(targets)));

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

  function openPicker(callback) {
    pickerCallback = callback;
    pickerOpen = true;
  }

  function handlePickEffect(effectName) {
    pickerOpen = false;
    if (pickerCallback) pickerCallback(effectName);
    pickerCallback = null;
  }

  function addCustomTarget() {
    openPicker((effectName) => {
      const cap = getEffectiveCap(effectName);
      const value = cap ?? 100;
      customRows = [...customRows, { effectName, value }];
      targets = { ...targets, [effectName]: value };
      if (!priorities.includes(effectName)) priorities = [...priorities, effectName];
    });
  }

  function changeCustomEffect(index) {
    const oldName = customRows[index].effectName;
    openPicker((newEffectName) => {
      const cap = getEffectiveCap(newEffectName);
      const value = cap ?? 100;
      const newTargets = { ...targets };
      delete newTargets[oldName];
      newTargets[newEffectName] = value;
      targets = newTargets;
      priorities = priorities.map(p => p === oldName ? newEffectName : p);
      customRows = customRows.map((r, i) => i === index ? { effectName: newEffectName, value } : r);
    });
  }

  function removeCustomRow(index) {
    const row = customRows[index];
    const newTargets = { ...targets };
    delete newTargets[row.effectName];
    targets = newTargets;
    priorities = priorities.filter(p => p !== row.effectName);
    customRows = customRows.filter((_, i) => i !== index);
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

  const CATEGORY_LABELS = [
    { key: 'offensive', label: 'Offensive' },
    { key: 'defensive', label: 'Defensive' },
    { key: 'utility', label: 'Utility' },
    { key: 'misc', label: 'Other' },
  ];
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
          <button type="button" class="effect-name-btn" onclick={() => changeCustomEffect(i)} title="Change effect">
            {row.effectName}
          </button>
          <input
            type="number"
            class="target-input"
            value={row.value}
            min="0.1"
            step="0.5"
            onchange={(e) => updateCustomValue(i, e.target.value)}
          />
          <span class="target-unit">{getEffectUnit(row.effectName)}</span>
          <button type="button" class="btn-icon-sm" onclick={() => removeCustomRow(i)} title="Remove">x</button>
        </div>
      {/each}
    </div>
  {/if}

  <button type="button" class="btn-add-custom" onclick={addCustomTarget}>
    + Custom target
  </button>
</div>

<!-- Effect picker dialog -->
{#if pickerOpen}
  <div class="picker-backdrop" role="dialog" aria-modal="true" onclick={(e) => { if (e.target === e.currentTarget) pickerOpen = false; }} onkeydown={(e) => { if (e.key === 'Escape') pickerOpen = false; }}>
    <div class="picker-panel">
      <div class="picker-header">
        <h3>Select Effect</h3>
        <button type="button" class="picker-close" onclick={() => pickerOpen = false}>x</button>
      </div>
      <div class="picker-body">
        {#each CATEGORY_LABELS as cat (cat.key)}
          {@const items = categories[cat.key] || []}
          {#if items.length > 0}
            <div class="picker-category">
              <h4 class="picker-cat-label">{cat.label}</h4>
              <div class="picker-items">
                {#each items as effect (effect.name)}
                  {@const disabled = usedNames.has(effect.name)}
                  <button
                    type="button"
                    class="picker-item"
                    {disabled}
                    onclick={() => handlePickEffect(effect.name)}
                  >
                    <span class="picker-item-name">{effect.name}</span>
                    <span class="picker-item-caps">
                      {#if effect.itemCap != null}
                        <span class="cap-badge" title="Item cap">Item: {effect.itemCap}{effect.unit}</span>
                      {/if}
                      {#if effect.totalCap != null}
                        <span class="cap-badge" title="Total cap">Total: {effect.totalCap}{effect.unit}</span>
                      {/if}
                      {#if effect.itemCap == null && effect.totalCap == null}
                        <span class="cap-badge none">No cap</span>
                      {/if}
                    </span>
                  </button>
                {/each}
              </div>
            </div>
          {/if}
        {/each}
      </div>
    </div>
  </div>
{/if}

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

  .effect-name-btn {
    flex: 1;
    min-width: 0;
    padding: 5px 8px;
    font-size: 12px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
    cursor: pointer;
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    transition: all 0.15s ease;
  }

  .effect-name-btn:hover {
    background-color: var(--hover-color);
    border-color: var(--accent-color);
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

  /* ===== Effect picker dialog ===== */

  .picker-backdrop {
    position: fixed;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
  }

  .picker-panel {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    max-width: 600px;
    width: 100%;
    max-height: 75vh;
    display: flex;
    flex-direction: column;
  }

  .picker-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
  }

  .picker-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-color);
  }

  .picker-close {
    width: 28px;
    height: 28px;
    padding: 0;
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 18px;
    cursor: pointer;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .picker-close:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .picker-body {
    overflow-y: auto;
    padding: 8px 16px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .picker-category {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .picker-cat-label {
    margin: 0;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding-bottom: 2px;
    border-bottom: 1px solid var(--border-color);
  }

  .picker-items {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .picker-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 6px 10px;
    border: none;
    border-radius: 6px;
    background-color: transparent;
    color: var(--text-color);
    cursor: pointer;
    text-align: left;
    width: 100%;
    transition: background-color 0.1s;
    font-size: 13px;
  }

  .picker-item:hover:not(:disabled) {
    background-color: var(--hover-color);
  }

  .picker-item:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  .picker-item-name {
    flex: 1;
    min-width: 0;
  }

  .picker-item-caps {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }

  .cap-badge {
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 4px;
    background-color: var(--bg-color);
    color: var(--text-muted);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  .cap-badge.none {
    opacity: 0.5;
  }
</style>
