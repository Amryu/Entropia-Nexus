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
    mode = $bindable('contextual'),
    onpick = () => {},
    loading = false
  } = $props();

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

  let targetNames = $derived(Object.keys(targets));

  function getEffectBadges(result) {
    if (mode === 'standalone' && result.pctDetails) {
      return result.pctDetails
        .filter(d => d.achieved > 0)
        .map(d => ({
          name: d.effectName,
          label: `${d.achieved}/${d.targetValue}`,
          pct: d.pct,
          isPerfect: Math.abs(d.pct - 100) < 0.5,
          isOver: d.pct > 100.5,
        }));
    }
    if (result.details) {
      return result.details.map(d => ({
        name: d.effectName,
        label: `${d.achieved.toFixed(1)}/${d.targetValue}`,
        pct: d.ratio * 100,
        isPerfect: Math.abs(d.diff) < 0.01,
        isOver: d.diff > 0.01,
      }));
    }
    return [];
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div class="dialog-backdrop" role="dialog" aria-modal="true" onclick={handleBackdropClick} onkeydown={handleKeydown}>
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
                <tr class="suggest-row" ondblclick={() => handlePick(result)}>
                  <td class="rank-cell">{i + 1}</td>
                  <td class="name-cell" title={result.name}>{result.name}</td>
                  {#each targetNames as effectName (effectName)}
                    {@const badge = getEffectBadges(result).find(b => b.name === effectName)}
                    <td class="effect-cell">
                      {#if badge}
                        <span
                          class="effect-badge"
                          class:perfect={badge.isPerfect}
                          class:over={badge.isOver}
                          class:under={!badge.isPerfect && !badge.isOver}
                        >{badge.label}</span>
                      {:else}
                        <span class="effect-badge none">-</span>
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
    gap: 0;
    padding: 8px 16px;
    border-bottom: 1px solid var(--border-color);
  }

  .mode-btn {
    flex: 1;
    padding: 6px 12px;
    font-size: 13px;
    border: 1px solid var(--border-color);
    background-color: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .mode-btn:first-child {
    border-radius: 6px 0 0 6px;
  }

  .mode-btn:last-child {
    border-radius: 0 6px 6px 0;
    border-left: none;
  }

  .mode-btn:hover {
    background-color: var(--hover-color);
  }

  .mode-btn.active {
    background-color: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
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

  .effect-badge {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }

  .effect-badge.perfect {
    background-color: color-mix(in srgb, var(--success-color, #5cb85c) 20%, transparent);
    color: var(--success-color, #5cb85c);
  }

  .effect-badge.over {
    background-color: color-mix(in srgb, var(--danger-color, #d9534f) 20%, transparent);
    color: var(--danger-color, #d9534f);
  }

  .effect-badge.under {
    background-color: color-mix(in srgb, var(--warning-color, #f0ad4e) 20%, transparent);
    color: var(--warning-color, #f0ad4e);
  }

  .effect-badge.none {
    color: var(--text-muted);
    opacity: 0.5;
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
