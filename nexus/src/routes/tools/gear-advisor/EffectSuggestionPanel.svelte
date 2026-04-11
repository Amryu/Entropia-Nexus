<!--
  @component EffectSuggestionPanel
  Sidebar optimizer panel. Shows top gear combinations from the beam search.
  Alternatives (items with identical buffs) are collapsed into a single badge
  that opens a popover for picking between them.
-->
<script>
  // @ts-nocheck
  let {
    results = [],
    targets = {},
    loading = false,
    onFillAll = () => {},
    onApply = () => {},
    onSwapAlternative = () => {},
    onOpenDialog = () => {}
  } = $props();

  let hasTargets = $derived(Object.keys(targets).length > 0);
  let openPopover = $state(null); // `${resultIdx}:${slotKey}`

  function formatSlotName(key) {
    const labels = {
      leftRing: 'L. Ring',
      rightRing: 'R. Ring',
      armorSet: 'Armor',
      pet: 'Pet',
      weapon: 'Weapon',
      amplifier: 'Amp',
      visionAttachment: 'Scope',
      absorber: 'Abs',
      implant: 'Impl'
    };
    if (key.startsWith('clothing:')) return key.slice('clothing:'.length);
    return labels[key] || key;
  }

  function valueName(value) {
    if (value == null) return '';
    return (typeof value === 'object') ? (value.name ?? '') : value;
  }

  function sameValue(a, b) {
    return valueName(a) === valueName(b);
  }

  function getResultEffects(result) {
    if (!result?.details) return [];
    return result.details.map(d => ({
      name: d.effectName,
      achieved: d.achieved,
      target: d.targetValue,
      isPerfect: Math.abs(d.diff) < 0.01,
      isOver: d.diff > 0.01,
      isUnder: d.diff < -0.01
    }));
  }

  function togglePopover(resultIdx, slotKey) {
    const id = `${resultIdx}:${slotKey}`;
    openPopover = openPopover === id ? null : id;
  }

  function pickAlternative(resultIdx, slotKey, value) {
    onSwapAlternative(resultIdx, slotKey, value);
    openPopover = null;
  }

  function onWindowClick(e) {
    if (openPopover == null) return;
    const t = e.target;
    if (t && typeof t.closest === 'function' && t.closest('.alt-badge, .alt-popover')) return;
    openPopover = null;
  }
</script>

<svelte:window onclick={onWindowClick} />

<div class="suggestion-panel">
  <div class="suggestion-actions">
    <button
      type="button"
      class="btn-open-dialog"
      onclick={onOpenDialog}
      title="Open the optimizer for fine-tuning"
    >
      Open Optimizer
    </button>
    <button
      type="button"
      class="btn-fill-all"
      onclick={onFillAll}
      disabled={!hasTargets || loading}
    >
      {loading ? 'Searching...' : 'Quick Optimize'}
    </button>
  </div>

  {#if loading}
    <div class="suggestion-loading">Searching for optimal combinations...</div>
  {:else if results.length > 0}
    <div class="suggestion-results">
      {#each results as result, i (i)}
        {@const effs = getResultEffects(result)}
        <div class="result-card">
          <div class="result-header">
            <span class="result-rank">#{i + 1}</span>
            <span class="result-score" title="Score: {result.score?.toFixed(0)}">
              {#each effs as eff (eff.name)}
                <span
                  class="result-effect-badge"
                  class:perfect={eff.isPerfect}
                  class:over={eff.isOver}
                  class:under={eff.isUnder}
                >
                  {eff.achieved.toFixed(1)}/{eff.target}
                </span>
              {/each}
            </span>
            <button
              type="button"
              class="btn-apply"
              onclick={() => onApply(result)}
            >Apply</button>
          </div>
          <div class="result-items">
            {#each Object.entries(result.items || {}) as [key, value] (key)}
              {@const alts = result.alternatives?.[key] || []}
              {@const hasAlts = alts.length > 1}
              <div class="result-slot">
                <span class="result-slot-label">{formatSlotName(key)}</span>
                <span class="result-slot-value">
                  {valueName(value) || '-'}
                </span>
                {#if hasAlts}
                  <button
                    type="button"
                    class="alt-badge"
                    title="{alts.length - 1} alternative{alts.length - 1 === 1 ? '' : 's'} with the same buffs"
                    onclick={(e) => { e.stopPropagation(); togglePopover(i, key); }}
                  >+{alts.length - 1}</button>
                  {#if openPopover === `${i}:${key}`}
                    <!-- svelte-ignore a11y_click_events_have_key_events -->
                    <div class="alt-popover" onclick={(e) => e.stopPropagation()} role="menu" tabindex="-1">
                      <div class="alt-popover-title">Alternatives (same buffs)</div>
                      {#each alts as alt (valueName(alt))}
                        <button
                          type="button"
                          class="alt-popover-item"
                          class:active={sameValue(alt, value)}
                          onclick={() => pickAlternative(i, key, alt)}
                        >
                          {valueName(alt)}
                        </button>
                      {/each}
                    </div>
                  {/if}
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  {:else if hasTargets}
    <div class="suggestion-empty">Click "Quick Optimize" or open the optimizer.</div>
  {:else}
    <div class="suggestion-empty">Select target effects first, then use the optimizer to find matching equipment.</div>
  {/if}
</div>

<style>
  .suggestion-panel {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .suggestion-actions {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .btn-open-dialog {
    padding: 10px 12px;
    font-size: 13px;
    font-weight: 600;
    border: 1px solid var(--accent-color);
    border-radius: 6px;
    background-color: var(--accent-color);
    color: white;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-open-dialog:hover {
    opacity: 0.9;
  }

  .btn-fill-all {
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: transparent;
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-fill-all:hover:not(:disabled) {
    background-color: var(--hover-color);
  }

  .btn-fill-all:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .suggestion-loading, .suggestion-empty {
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
    padding: 12px 0;
  }

  .suggestion-results {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .result-card {
    padding: 8px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--bg-color);
  }

  .result-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }

  .result-rank {
    font-size: 11px;
    font-weight: 700;
    color: var(--text-muted);
    min-width: 20px;
  }

  .result-score {
    flex: 1;
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  .result-effect-badge {
    font-size: 10px;
    padding: 1px 5px;
    border-radius: 3px;
    background-color: var(--secondary-color);
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  .result-effect-badge.perfect {
    background-color: color-mix(in srgb, var(--success-color, #5cb85c) 20%, transparent);
    color: var(--success-color, #5cb85c);
  }

  .result-effect-badge.over {
    background-color: color-mix(in srgb, var(--danger-color, #d9534f) 20%, transparent);
    color: var(--danger-color, #d9534f);
  }

  .result-effect-badge.under {
    background-color: color-mix(in srgb, var(--warning-color, #f0ad4e) 20%, transparent);
    color: var(--warning-color, #f0ad4e);
  }

  .btn-apply {
    padding: 3px 10px;
    font-size: 11px;
    border: 1px solid var(--accent-color);
    border-radius: 4px;
    background-color: transparent;
    color: var(--accent-color);
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
  }

  .btn-apply:hover {
    background-color: var(--accent-color);
    color: white;
  }

  .result-items {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 12px;
  }

  .result-slot {
    display: flex;
    gap: 4px;
    align-items: baseline;
    font-size: 11px;
    position: relative;
  }

  .result-slot-label {
    color: var(--text-muted);
    font-weight: 500;
  }

  .result-slot-value {
    color: var(--text-color);
  }

  .alt-badge {
    padding: 0 5px;
    font-size: 10px;
    font-weight: 600;
    border: 1px solid var(--accent-color);
    border-radius: 8px;
    background-color: color-mix(in srgb, var(--accent-color) 15%, transparent);
    color: var(--accent-color);
    cursor: pointer;
    line-height: 14px;
    height: 14px;
    display: inline-flex;
    align-items: center;
  }

  .alt-badge:hover {
    background-color: var(--accent-color);
    color: white;
  }

  .alt-popover {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    z-index: 50;
    min-width: 180px;
    max-width: 260px;
    padding: 4px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--bg-color);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .alt-popover-title {
    font-size: 10px;
    color: var(--text-muted);
    padding: 4px 6px 2px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .alt-popover-item {
    text-align: left;
    padding: 4px 6px;
    font-size: 11px;
    border: none;
    border-radius: 4px;
    background-color: transparent;
    color: var(--text-color);
    cursor: pointer;
  }

  .alt-popover-item:hover {
    background-color: var(--hover-color);
  }

  .alt-popover-item.active {
    background-color: color-mix(in srgb, var(--accent-color) 20%, transparent);
    color: var(--accent-color);
    font-weight: 600;
  }
</style>
