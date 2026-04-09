<!--
  @component EffectTotalsBar
  Aggregated effects summary with progress bars and cap indicators.
  Shows targeted effects with progress, and non-targeted effects as informational.
-->
<script>
  // @ts-nocheck

  let {
    summary = [],
    targets = {},
    effectCaps = {},
    effectsCatalog = [],
    totalCost = { items: [], total: 0 }
  } = $props();

  function getUnitForEffect(name, summaryEntry) {
    if (summaryEntry?.unit) return summaryEntry.unit;
    const catalog = effectsCatalog.find(e => e?.Name === name);
    return catalog?.Properties?.Unit || '';
  }

  let targetEntries = $derived.by(() => {
    const entries = [];
    for (const [name, target] of Object.entries(targets)) {
      const entry = summary.find(e => e.name === name);
      const achieved = entry ? Math.abs(entry.signedTotal) : 0;
      const caps = effectCaps[name];
      const itemCap = caps?.item ?? null;
      const totalCap = caps?.total ?? null;
      const cap = (itemCap != null && totalCap != null) ? Math.min(itemCap, totalCap)
        : itemCap ?? totalCap;
      const unit = getUnitForEffect(name, entry);
      const ratio = target > 0 ? Math.min(achieved / target, 1.5) : 0;
      const isOvercapped = achieved > target + 0.01;
      const isPerfect = Math.abs(achieved - target) < 0.01;
      const isCapped = cap != null && Math.abs(achieved - cap) < 0.01;
      entries.push({ name, target, achieved, cap, unit, ratio, isOvercapped, isPerfect, isCapped });
    }
    return entries;
  });

  let otherEffects = $derived.by(() => {
    const targetNames = new Set(Object.keys(targets));
    return summary
      .filter(e => !targetNames.has(e.name) && Math.abs(e.signedTotal) > 0.01)
      .map(e => ({
        name: e.name,
        value: e.signedTotal,
        unit: e.unit || '',
        cappedAny: e.cappedAny || false
      }));
  });

  function statusClass(entry) {
    if (entry.isPerfect || entry.isCapped) return 'perfect';
    if (entry.isOvercapped) return 'overcapped';
    return 'under';
  }
</script>

<div class="totals-bar">
  {#if targetEntries.length > 0}
    <div class="target-effects">
      {#each targetEntries as entry (entry.name)}
        <div class="effect-item {statusClass(entry)}">
          <div class="effect-label">
            <span class="effect-name" title={entry.name}>{entry.name}</span>
            <span class="effect-values">
              {entry.achieved.toFixed(1)}{entry.unit}
              <span class="effect-target">/ {entry.target}{entry.unit}</span>
            </span>
          </div>
          <div class="progress-track">
            <div
              class="progress-fill {statusClass(entry)}"
              style="width: {Math.min(entry.ratio * 100, 100)}%"
            ></div>
            {#if entry.isOvercapped}
              <div
                class="progress-overcap"
                style="width: {Math.min((entry.achieved - entry.target) / entry.target * 100, 50)}%; left: 100%"
              ></div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <div class="empty-hint">Select target effects above to see progress</div>
  {/if}

  {#if otherEffects.length > 0}
    <div class="other-effects">
      <span class="other-label">Also active:</span>
      {#each otherEffects as eff (eff.name)}
        <span class="other-badge" class:capped={eff.cappedAny} title={eff.name}>
          {eff.name}: {eff.value > 0 ? '+' : ''}{eff.value.toFixed(1)}{eff.unit}
        </span>
      {/each}
    </div>
  {/if}

  {#if totalCost.items.length > 0}
    <div class="cost-summary">
      <div class="cost-items">
        {#each totalCost.items as item (item.name)}
          <div class="cost-item">
            <span class="cost-name">{item.name}</span>
            <span class="cost-detail">
              {#if item.isAbsolute}
                {item.tt.toFixed(2)} TT + {item.mu.toFixed(2)} MU
              {:else}
                {item.tt.toFixed(2)} TT x {item.mu.toFixed(1)}%
              {/if}
              = <strong>{item.cost.toFixed(2)} PED</strong>
            </span>
          </div>
        {/each}
      </div>
      <div class="cost-total">
        <span>Total estimated cost</span>
        <strong>{totalCost.total.toFixed(2)} PED</strong>
      </div>
    </div>
  {/if}
</div>

<style>
  .totals-bar {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background-color: var(--secondary-color);
  }

  .target-effects {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .effect-item {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .effect-label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
  }

  .effect-name {
    color: var(--text-color);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 60%;
  }

  .effect-values {
    font-variant-numeric: tabular-nums;
    color: var(--text-color);
    font-weight: 600;
  }

  .effect-target {
    font-weight: 400;
    color: var(--text-muted);
  }

  .progress-track {
    position: relative;
    height: 6px;
    background-color: var(--bg-color);
    border-radius: 3px;
    overflow: visible;
  }

  .progress-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.2s ease;
  }

  .progress-fill.under {
    background-color: var(--warning-color, #f0ad4e);
  }

  .progress-fill.perfect {
    background-color: var(--success-color, #5cb85c);
  }

  .progress-fill.overcapped {
    background-color: var(--danger-color, #d9534f);
  }

  .progress-overcap {
    position: absolute;
    top: 0;
    height: 100%;
    background-color: var(--danger-color, #d9534f);
    opacity: 0.4;
    border-radius: 0 3px 3px 0;
  }

  .effect-item.perfect .effect-values {
    color: var(--success-color, #5cb85c);
  }

  .effect-item.overcapped .effect-values {
    color: var(--danger-color, #d9534f);
  }

  .empty-hint {
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
    padding: 4px 0;
  }

  .other-effects {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
    padding-top: 4px;
    border-top: 1px solid var(--border-color);
  }

  .other-label {
    font-size: 11px;
    color: var(--text-muted);
    margin-right: 2px;
  }

  .other-badge {
    font-size: 12px;
    padding: 3px 8px;
    border-radius: 4px;
    background-color: var(--bg-color);
    color: var(--text-muted);
    white-space: nowrap;
  }

  .other-badge.capped {
    border: 1px solid var(--warning-color, #f0ad4e);
    color: var(--warning-color, #f0ad4e);
  }

  .cost-summary {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding-top: 6px;
    border-top: 1px solid var(--border-color);
  }

  .cost-items {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .cost-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
  }

  .cost-name {
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 50%;
  }

  .cost-detail {
    font-variant-numeric: tabular-nums;
    color: var(--text-color);
  }

  .cost-total {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    padding-top: 4px;
    border-top: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .cost-total strong {
    font-variant-numeric: tabular-nums;
  }
</style>
