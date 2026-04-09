<!--
  @component EffectSuggestionPanel
  Displays suggestion results from the beam search engine.
  Shows top combinations with "Apply" button to fill slot cards.
-->
<script>
  // @ts-nocheck
  // No external imports needed - effect data comes via props

  let {
    results = [],
    targets = {},
    loading = false,
    onFillAll = () => {},
    onApply = () => {},
    emptyOnly = $bindable(false)
  } = $props();

  let hasTargets = $derived(Object.keys(targets).length > 0);

  function formatSlotName(key) {
    const labels = {
      leftRing: 'L. Ring',
      rightRing: 'R. Ring',
      armorSet: 'Armor',
      pet: 'Pet'
    };
    return labels[key] || key;
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
</script>

<div class="suggestion-panel">
  <div class="suggestion-header">
    <h3>Suggestions</h3>
    <div class="suggestion-actions">
      <label class="empty-only-label">
        <input type="checkbox" bind:checked={emptyOnly} />
        <span>Empty slots only</span>
      </label>
      <button
        type="button"
        class="btn-fill-all"
        onclick={onFillAll}
        disabled={!hasTargets || loading}
      >
        {loading ? 'Searching...' : 'Fill All Slots'}
      </button>
    </div>
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
              onclick={() => onApply(result, emptyOnly)}
            >Apply</button>
          </div>
          <div class="result-items">
            {#each Object.entries(result.items || {}) as [key, value] (key)}
              <div class="result-slot">
                <span class="result-slot-label">{formatSlotName(key)}</span>
                <span class="result-slot-value">
                  {#if typeof value === 'object' && value?.name}
                    {value.name}
                  {:else}
                    {value || '-'}
                  {/if}
                </span>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  {:else if hasTargets}
    <div class="suggestion-empty">Click "Fill All Slots" to find optimal equipment combinations.</div>
  {:else}
    <div class="suggestion-empty">Select target effects first, then use suggestions to find matching equipment.</div>
  {/if}
</div>

<style>
  .suggestion-panel {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .suggestion-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
  }

  .suggestion-header h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .suggestion-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .empty-only-label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--text-muted);
    cursor: pointer;
  }

  .empty-only-label input {
    margin: 0;
  }

  .btn-fill-all {
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 500;
    border: 1px solid var(--accent-color);
    border-radius: 6px;
    background-color: var(--accent-color);
    color: white;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-fill-all:hover:not(:disabled) {
    opacity: 0.9;
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
  }

  .result-slot-label {
    color: var(--text-muted);
    font-weight: 500;
  }

  .result-slot-value {
    color: var(--text-color);
  }
</style>
