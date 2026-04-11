<!--
  @component SlotSuggestionDialog
  Modal dialog showing a ranked list of suggested items for a specific equipment slot.
  Two modes: Contextual (considers other equipped items) and Standalone (item's own target contribution).
-->
<script>
  // @ts-nocheck
  import { getEffectStrength } from '$lib/utils/loadoutEffects.js';
  import { extractEquipEffects, extractArmorSetEffects, extractPetEffect } from './effectOptimizer.js';

  let {
    open = $bindable(false),
    slotLabel = '',
    slotType = 'item',
    results = [],
    targets = {},
    currentSummary = [],
    currentSlotEffects = [],
    currentSlotItemName = null,
    baselineSummary = [],
    effectsCatalog = [],
    mode = $bindable('contextual'),
    onpick = () => {},
    loading = false
  } = $props();

  // The summarizer stores a net effect under either its positive or negative
  // suffix name depending on the sign. When our target is e.g. "Critical Damage
  // Added" but the baseline is net negative, the entry name in the summary is
  // "Critical Damage Reduced" with a negative signedTotal. Look up by both.
  const SUFFIX_RULES = [
    { positive: 'Increased', negative: 'Decreased' },
    { positive: 'Added', negative: 'Reduced' }
  ];

  function findEffectEntry(summary, effectName) {
    if (!summary) return null;
    let entry = summary.find(e => e.name === effectName);
    if (entry) return entry;
    for (const rule of SUFFIX_RULES) {
      if (effectName.endsWith(' ' + rule.positive)) {
        const altName = effectName.slice(0, -rule.positive.length) + rule.negative;
        entry = summary.find(e => e.name === altName);
        if (entry) return entry;
      } else if (effectName.endsWith(' ' + rule.negative)) {
        const altName = effectName.slice(0, -rule.negative.length) + rule.positive;
        entry = summary.find(e => e.name === altName);
        if (entry) return entry;
      }
    }
    return null;
  }

  // Raw per-effect value the currently-equipped item in this slot provides
  let currentSlotValues = $derived.by(() => {
    const map = {};
    for (const e of (currentSlotEffects || [])) {
      if (!e?.Name) continue;
      map[e.Name] = getEffectStrength(e) || 0;
    }
    return map;
  });

  function handlePick(result) {
    onpick(result);
    open = false;
  }

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) open = false;
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') open = false;
  }

  // Hide Auto Loot column if already provided by current equipment
  let targetNames = $derived.by(() => {
    const names = Object.keys(targets);
    const autoLootActive = currentSummary.some(e => e.name === 'Auto Loot' && Math.abs(e.signedTotal) > 0.01);
    if (autoLootActive) return names.filter(n => n !== 'Auto Loot');
    return names;
  });

  function getEffectUnit(effectName) {
    const eff = (effectsCatalog || []).find(e => e?.Name === effectName);
    return eff?.Properties?.Unit || '';
  }

  // Returns comparison info for one target effect vs one candidate.
  // Uses SIGNED totals so debuff/buff combinations from other slots are respected.
  // status:
  //   'none'    - item has no value for this effect
  //   'normal'  - item's contribution is fully applied
  //   'overcap' - item's contribution is partially applied (some wasted past cap)
  //   'wasted'  - item contributes nothing (baseline already caps it out)
  function getEffectInfo(result, effectName) {
    const unit = getEffectUnit(effectName);
    const itemRaw = result?.itemValues?.[effectName] ?? 0;

    if (mode === 'standalone' && result.pctDetails) {
      const d = result.pctDetails.find(p => p.effectName === effectName);
      if (!d) return null;
      return {
        itemRaw,
        applied: itemRaw,
        status: itemRaw > 0 ? 'normal' : 'none',
        unit,
        target: d.targetValue,
        newTotal: null,
        currentTotal: null,
        baselineTotal: null,
        currentItemValue: 0,
        delta: 0
      };
    }

    if (result.details) {
      const d = result.details.find(p => p.effectName === effectName);
      if (!d) return null;
      const target = d.targetValue;

      const baselineEntry = findEffectEntry(baselineSummary, effectName);
      const baselineTotal = baselineEntry ? baselineEntry.signedTotal : 0;
      const summaryEntry = findEffectEntry(result.summary || [], effectName);
      const newTotal = summaryEntry ? summaryEntry.signedTotal : (baselineTotal + itemRaw);
      const currentEntry = findEffectEntry(currentSummary, effectName);
      const currentTotal = currentEntry ? currentEntry.signedTotal : 0;

      const applied = newTotal - baselineTotal;
      const delta = newTotal - currentTotal;
      const currentItemValue = currentSlotValues[effectName] || 0;

      let status;
      if (itemRaw <= 0.001) {
        status = 'none';
      } else if (applied <= 0.001) {
        status = 'wasted';
      } else if (applied < itemRaw - 0.01) {
        status = 'overcap';
      } else {
        status = 'normal';
      }

      return { itemRaw, applied, status, unit, target, newTotal, currentTotal, baselineTotal, currentItemValue, delta };
    }
    return null;
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div class="dialog-backdrop" role="dialog" tabindex="-1" aria-modal="true" onclick={handleBackdropClick} onkeydown={handleKeydown}>
    <div class="dialog-panel">
      <div class="dialog-header">
        <h3>Suggest: {slotLabel}</h3>
        <button type="button" class="dialog-close" onclick={() => open = false}>x</button>
      </div>

      <div class="dialog-mode">
        <button
          type="button"
          class="mode-btn"
          class:active={mode === 'contextual'}
          onclick={() => mode = 'contextual'}
        >With other equipment</button>
        <button
          type="button"
          class="mode-btn"
          class:active={mode === 'standalone'}
          onclick={() => mode = 'standalone'}
        >Standalone contribution</button>
      </div>

      <div class="dialog-body">
        {#if loading}
          <div class="dialog-loading">Computing suggestions...</div>
        {:else if results.length === 0}
          <div class="dialog-empty">No items found that contribute to your target effects.</div>
        {:else}
          <table class="suggest-table">
            <thead>
              <tr>
                <th class="rank-col">#</th>
                <th class="name-col">Item</th>
                {#each targetNames as effectName (effectName)}
                  <th class="effect-col" title={effectName}>
                    {effectName.replace(/ (Added|Increased|Decreased|Reduced)$/, '')}
                  </th>
                {/each}
                <th class="score-col">{mode === 'standalone' ? 'Fill %' : 'Score'}</th>
                <th class="action-col"></th>
              </tr>
            </thead>
            <tbody>
              {#each results as result, i (result.name + (result.effectKey || '') + i)}
                {@const isCurrent = currentSlotItemName && result.name === currentSlotItemName}
                <tr class="suggest-row" class:is-current={isCurrent} ondblclick={() => handlePick(result)}>
                  <td class="rank-cell">{i + 1}</td>
                  <td class="name-cell" title={result.name}>
                    {result.name}
                    {#if isCurrent}<span class="current-tag" title="Currently equipped in this slot">equipped</span>{/if}
                  </td>
                  {#each targetNames as effectName (effectName)}
                    {@const info = getEffectInfo(result, effectName)}
                    <td class="effect-cell">
                      {#if !info || info.status === 'none'}
                        <span class="effect-none" title="{result.name} has no {effectName}">-</span>
                      {:else if isCurrent}
                        <span class="effect-value" title="Currently equipped: {info.itemRaw}{info.unit}">{info.itemRaw}{info.unit}</span>
                      {:else if mode === 'contextual'}
                        {@const wasted = info.status === 'wasted'}
                        {@const deltaSign = info.delta > 0.001 ? 'pos' : info.delta < -0.001 ? 'neg' : 'zero'}
                        <span
                          class="effect-value status-{info.status}"
                          class:delta-positive={deltaSign === 'pos' && !wasted}
                          class:delta-negative={deltaSign === 'neg' && !wasted}
                          title={
                            wasted
                              ? `Cap already reached by the rest of your equipment (${info.baselineTotal.toFixed(1)}${info.unit}) - this item would add nothing.`
                              : info.status === 'overcap'
                                ? `Item has ${info.itemRaw}${info.unit}, but only +${info.applied.toFixed(1)}${info.unit} fits before overcapping. Your total would change by ${info.delta > 0 ? '+' : ''}${info.delta.toFixed(1)}${info.unit}.`
                                : `Item: ${info.itemRaw}${info.unit}. Current slot: ${info.currentItemValue}${info.unit}. Total would change by ${info.delta > 0 ? '+' : ''}${info.delta.toFixed(1)}${info.unit}.`
                          }
                        >
                          {info.itemRaw}{info.unit}
                          {#if deltaSign !== 'zero' && !wasted}
                            <span class="delta-inline">({info.delta > 0 ? '+' : ''}{info.delta.toFixed(1)})</span>
                          {/if}
                        </span>
                      {:else}
                        <span class="effect-value" title="{info.itemRaw}{info.unit}">{info.itemRaw}{info.unit}</span>
                      {/if}
                    </td>
                  {/each}
                  <td class="score-cell">
                    {#if mode === 'standalone'}
                      {result.score.toFixed(0)}%
                    {:else}
                      {result.score.toFixed(0)}
                    {/if}
                  </td>
                  <td class="action-cell">
                    <button type="button" class="pick-btn" onclick={() => handlePick(result)}>Select</button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .dialog-backdrop {
    position: fixed;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
  }

  .dialog-panel {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    max-width: 900px;
    width: 100%;
    height: 70vh;
    display: flex;
    flex-direction: column;
  }

  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-color);
  }

  .dialog-close {
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

  .dialog-close:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .dialog-mode {
    display: flex;
    border-bottom: 1px solid var(--border-color);
  }

  .mode-btn {
    flex: 1;
    padding: 10px 12px;
    font-size: 13px;
    font-weight: 500;
    border: none;
    border-right: 1px solid var(--border-color);
    background-color: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
    position: relative;
  }

  .mode-btn:last-child {
    border-right: none;
  }

  .mode-btn:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .mode-btn.active {
    background-color: color-mix(in srgb, var(--accent-color) 12%, transparent);
    color: var(--accent-color);
    font-weight: 600;
  }

  .mode-btn.active::after {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    bottom: -1px;
    height: 2px;
    background-color: var(--accent-color);
  }

  .dialog-body {
    overflow-y: auto;
    padding: 8px 0;
    flex: 1;
    min-height: 0;
  }

  .dialog-loading, .dialog-empty {
    padding: 24px 16px;
    text-align: center;
    font-size: 13px;
    color: var(--text-muted);
  }

  .suggest-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  .suggest-table th {
    padding: 6px 10px;
    text-align: left;
    font-weight: 600;
    font-size: 11px;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .suggest-table td {
    padding: 6px 10px;
    border-bottom: 1px solid color-mix(in srgb, var(--border-color) 50%, transparent);
  }

  .suggest-row {
    cursor: pointer;
    transition: background-color 0.1s;
  }

  .suggest-row:hover {
    background-color: var(--hover-color);
  }

  .suggest-row.is-current {
    background-color: color-mix(in srgb, var(--accent-color) 12%, transparent);
    box-shadow: inset 3px 0 0 var(--accent-color);
  }

  .suggest-row.is-current:hover {
    background-color: color-mix(in srgb, var(--accent-color) 18%, transparent);
  }

  .current-tag {
    display: inline-block;
    margin-left: 6px;
    padding: 0 6px;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    border-radius: 3px;
    line-height: 14px;
    vertical-align: middle;
    background-color: var(--accent-color);
    color: white;
  }

  .rank-col { width: 32px; text-align: center; }
  .rank-cell { text-align: center; color: var(--text-muted); font-weight: 600; }

  .name-col { min-width: 120px; }
  .name-cell {
    color: var(--text-color);
    font-weight: 500;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .effect-col { text-align: center; max-width: 100px; overflow: hidden; text-overflow: ellipsis; }
  .effect-cell { text-align: center; }

  .effect-value {
    font-weight: 600;
    color: var(--text-color);
    font-variant-numeric: tabular-nums;
    cursor: help;
  }

  .effect-value.delta-positive {
    color: var(--success-color, #5cb85c);
  }

  .effect-value.delta-negative {
    color: var(--danger-color, #d9534f);
  }

  .effect-value.status-overcap {
    color: var(--warning-color, #f0ad4e);
  }

  .effect-value.status-wasted {
    color: var(--text-muted);
    opacity: 0.55;
  }

  .delta-inline {
    font-size: 10px;
    font-weight: 500;
    margin-left: 3px;
    opacity: 0.85;
  }

  .effect-none {
    color: var(--text-muted);
    opacity: 0.35;
  }

  .score-col { width: 60px; text-align: right; }
  .score-cell {
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    color: var(--text-color);
  }

  .action-col { width: 70px; }
  .action-cell { text-align: right; }

  .pick-btn {
    padding: 4px 10px;
    font-size: 12px;
    border: 1px solid var(--accent-color);
    border-radius: 4px;
    background-color: transparent;
    color: var(--accent-color);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .pick-btn:hover {
    background-color: var(--accent-color);
    color: white;
  }

  @media (max-width: 600px) {
    .dialog-panel {
      max-height: 90vh;
    }

    .name-cell {
      max-width: 120px;
    }
  }
</style>
