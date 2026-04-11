<!--
  @component OptimizerDialog
  Full-screen version of the gear optimizer. Provides:
  - Explanation of locking + scoring
  - Per-slot lock toggles for every slot (primary, secondary, clothing)
  - Richer results list with alternatives popovers
-->
<script>
  // @ts-nocheck
  let {
    open = $bindable(false),
    allSlotKeys = [],
    unlockedSlotIds,
    slotLabels = {},
    currentItems = {},
    results = [],
    targets = {},
    loading = false,
    onToggleLock = () => {},
    onLockAll = () => {},
    onUnlockAll = () => {},
    onResetLocks = () => {},
    onRun = () => {},
    onApply = () => {},
    onSwapAlternative = () => {}
  } = $props();

  let hasTargets = $derived(Object.keys(targets).length > 0);
  let openPopover = $state(null);

  function close() { open = false; }

  function backdropClick(e) {
    if (e.target === e.currentTarget) close();
  }

  function onKeydown(e) {
    if (e.key === 'Escape') close();
  }

  function formatSlotLabel(key) {
    if (slotLabels[key]) return slotLabels[key];
    if (key.startsWith('clothing:')) return key.slice('clothing:'.length);
    return key;
  }

  function currentItemFor(key) {
    if (key.startsWith('clothing:')) {
      const slotName = key.slice('clothing:'.length);
      return currentItems.clothing?.[slotName] || null;
    }
    return currentItems[key] ?? null;
  }

  function isUnlocked(key) {
    return unlockedSlotIds?.has(key) ?? false;
  }

  function valueName(value) {
    if (value == null) return '';
    return (typeof value === 'object') ? (value.name ?? '') : value;
  }

  function sameValue(a, b) {
    return valueName(a) === valueName(b);
  }

  function formatResultSlotName(key) {
    return formatSlotLabel(key);
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

  function applyAndClose(result) {
    onApply(result);
  }

  function onWindowClick(e) {
    if (openPopover == null) return;
    const t = e.target;
    if (t && typeof t.closest === 'function' && t.closest('.alt-badge, .alt-popover')) return;
    openPopover = null;
  }
</script>

<svelte:window onkeydown={onKeydown} onclick={onWindowClick} />

{#if open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="dialog-backdrop" role="dialog" tabindex="-1" aria-modal="true" onclick={backdropClick}>
    <div class="dialog-panel">
      <div class="dialog-header">
        <h3>Optimizer</h3>
        <button type="button" class="dialog-close" onclick={close}>x</button>
      </div>

      <div class="dialog-explain">
        <p>
          <strong>Open / Closed:</strong> A <em>closed</em> slot keeps its current item - its buffs still count toward totals, but the optimizer will not replace it. <em>Open</em> slots are the ones the optimizer will fill or swap.
        </p>
        <p>
          <strong>Scoring:</strong> Combinations are scored by how closely total buffs match your targets (priorities weighted higher). Overcapping is penalized by default. Results are diversified so the top list is not filled with near-duplicates.
        </p>
        <p>
          <strong>Alternatives:</strong> When multiple items provide identical buffs, they are collapsed into one result. A highlighted badge on a slot indicates alternatives exist - click it to swap between them without re-running the optimizer.
        </p>
      </div>

      <div class="dialog-section">
        <div class="section-header">
          <h4>Slots</h4>
          <div class="lock-actions">
            <button type="button" class="lock-action-btn" onclick={onUnlockAll}>Open all</button>
            <button type="button" class="lock-action-btn" onclick={onLockAll}>Close all</button>
            <button type="button" class="lock-action-btn" onclick={onResetLocks}>Reset defaults</button>
          </div>
        </div>

        <div class="slot-grid">
          {#each allSlotKeys as key (key)}
            {@const open = isUnlocked(key)}
            {@const current = currentItemFor(key)}
            <button
              type="button"
              class="slot-cell"
              class:open
              onclick={() => onToggleLock(key)}
              title={open ? 'Open - optimizer will try to improve this slot' : 'Closed - current item stays'}
            >
              <span class="slot-lock-indicator" aria-hidden="true"></span>
              <span class="slot-cell-body">
                <span class="slot-cell-label">{formatSlotLabel(key)}</span>
                <span class="slot-cell-current">{current || '(empty)'}</span>
              </span>
            </button>
          {/each}
        </div>
      </div>

      <div class="dialog-section">
        <div class="section-header">
          <h4>Results</h4>
          <button
            type="button"
            class="btn-run"
            onclick={onRun}
            disabled={!hasTargets || loading}
          >
            {loading ? 'Searching...' : 'Run optimizer'}
          </button>
        </div>

        {#if loading}
          <div class="dialog-loading">Searching for optimal combinations...</div>
        {:else if !hasTargets}
          <div class="dialog-empty">Select target effects first.</div>
        {:else if results.length === 0}
          <div class="dialog-empty">No results yet. Click "Run optimizer".</div>
        {:else}
          <div class="results-list">
            {#each results as result, i (i)}
              {@const effs = getResultEffects(result)}
              <div class="result-row">
                <div class="result-row-head">
                  <span class="result-rank">#{i + 1}</span>
                  <div class="result-effects">
                    {#each effs as eff (eff.name)}
                      <span
                        class="eff-badge"
                        class:perfect={eff.isPerfect}
                        class:over={eff.isOver}
                        class:under={eff.isUnder}
                      >
                        <span class="eff-name">{eff.name}</span>
                        <span class="eff-val">{eff.achieved.toFixed(1)}/{eff.target}</span>
                      </span>
                    {/each}
                  </div>
                  <button type="button" class="btn-apply" onclick={() => applyAndClose(result)}>Apply</button>
                </div>
                <div class="result-row-slots">
                  {#each Object.entries(result.items || {}) as [key, value] (key)}
                    {@const alts = result.alternatives?.[key] || []}
                    {@const hasAlts = alts.length > 1}
                    <div class="result-slot-cell">
                      <span class="result-slot-label">{formatResultSlotName(key)}</span>
                      <span class="result-slot-name">{valueName(value) || '-'}</span>
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
                              >{valueName(alt)}</button>
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
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .dialog-backdrop {
    position: fixed;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.6);
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  .dialog-panel {
    background-color: var(--bg-color);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    max-width: 1100px;
    width: 100%;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
    background-color: var(--secondary-color);
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-color);
  }

  .dialog-close {
    background: transparent;
    border: none;
    font-size: 16px;
    color: var(--text-muted);
    cursor: pointer;
    padding: 4px 8px;
  }

  .dialog-close:hover {
    color: var(--text-color);
  }

  .dialog-explain {
    padding: 12px 16px;
    font-size: 12px;
    color: var(--text-muted);
    background-color: var(--secondary-color);
    border-bottom: 1px solid var(--border-color);
  }

  .dialog-explain p {
    margin: 0 0 6px 0;
    line-height: 1.45;
  }

  .dialog-explain p:last-child {
    margin-bottom: 0;
  }

  .dialog-explain strong {
    color: var(--text-color);
  }

  .dialog-section {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
    flex: 0 0 auto;
  }

  .dialog-section:last-child {
    border-bottom: none;
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
  }

  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
  }

  .section-header h4 {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  .lock-actions {
    display: flex;
    gap: 6px;
  }

  .lock-action-btn {
    padding: 4px 10px;
    font-size: 11px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: transparent;
    color: var(--text-color);
    cursor: pointer;
  }

  .lock-action-btn:hover {
    background-color: var(--hover-color);
  }

  .slot-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 8px;
  }

  .slot-cell {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    cursor: pointer;
    text-align: left;
    transition: all 0.1s ease;
  }

  .slot-cell:hover {
    background-color: var(--hover-color);
  }

  .slot-cell.open {
    border-color: var(--accent-color);
    background-color: color-mix(in srgb, var(--accent-color) 10%, transparent);
  }

  .slot-lock-indicator {
    position: relative;
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 1.5px solid var(--border-color);
    border-radius: 50%;
    flex-shrink: 0;
  }

  .slot-lock-indicator::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background-color: var(--accent-color);
    transform: translate(-50%, -50%);
    opacity: 0;
    transition: opacity 0.15s ease;
  }

  .slot-cell.open .slot-lock-indicator {
    border-color: var(--accent-color);
  }

  .slot-cell.open .slot-lock-indicator::before {
    opacity: 1;
  }

  .slot-cell-body {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    flex: 1;
  }

  .slot-cell-label {
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .slot-cell-current {
    font-size: 12px;
    color: var(--text-color);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .btn-run {
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
    border: 1px solid var(--accent-color);
    border-radius: 6px;
    background-color: var(--accent-color);
    color: white;
    cursor: pointer;
  }

  .btn-run:hover:not(:disabled) {
    opacity: 0.9;
  }

  .btn-run:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .dialog-loading, .dialog-empty {
    font-size: 13px;
    color: var(--text-muted);
    text-align: center;
    padding: 20px 0;
  }

  .results-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .result-row {
    padding: 10px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--secondary-color);
  }

  .result-row-head {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }

  .result-rank {
    font-size: 12px;
    font-weight: 700;
    color: var(--text-muted);
    min-width: 24px;
  }

  .result-effects {
    flex: 1;
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .eff-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    font-size: 11px;
    border-radius: 4px;
    background-color: var(--bg-color);
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  .eff-badge .eff-name {
    font-weight: 500;
  }

  .eff-badge.perfect {
    background-color: color-mix(in srgb, var(--success-color, #5cb85c) 20%, transparent);
    color: var(--success-color, #5cb85c);
  }

  .eff-badge.over {
    background-color: color-mix(in srgb, var(--danger-color, #d9534f) 20%, transparent);
    color: var(--danger-color, #d9534f);
  }

  .eff-badge.under {
    background-color: color-mix(in srgb, var(--warning-color, #f0ad4e) 20%, transparent);
    color: var(--warning-color, #f0ad4e);
  }

  .btn-apply {
    padding: 5px 14px;
    font-size: 12px;
    border: 1px solid var(--accent-color);
    border-radius: 4px;
    background-color: transparent;
    color: var(--accent-color);
    cursor: pointer;
  }

  .btn-apply:hover {
    background-color: var(--accent-color);
    color: white;
  }

  .result-row-slots {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 6px 12px;
  }

  .result-slot-cell {
    display: flex;
    align-items: baseline;
    gap: 6px;
    font-size: 12px;
    position: relative;
    min-width: 0;
  }

  .result-slot-label {
    color: var(--text-muted);
    font-weight: 500;
    white-space: nowrap;
  }

  .result-slot-name {
    color: var(--text-color);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
  }

  .alt-badge {
    padding: 0 6px;
    font-size: 10px;
    font-weight: 700;
    border: 1px solid var(--accent-color);
    border-radius: 8px;
    background-color: color-mix(in srgb, var(--accent-color) 18%, transparent);
    color: var(--accent-color);
    cursor: pointer;
    line-height: 16px;
    height: 16px;
    display: inline-flex;
    align-items: center;
    flex-shrink: 0;
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
    min-width: 200px;
    max-width: 280px;
    padding: 4px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--bg-color);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
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
    padding: 5px 8px;
    font-size: 12px;
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
