<!--
  @component DamageBreakdownGrid
  Displays all 9 damage types in a grid format.
  Highlights non-zero values and shows totals.
  Supports inline editing when in edit mode.
-->
<script>
  // @ts-nocheck
  import { editMode } from '$lib/stores/wikiEditState.js';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';

  

  

  
  /**
   * @typedef {Object} Props
   * @property {object} [weapon]
   * @property {boolean} [showZeros]
   * @property {boolean} [compact]
   */

  /**
   * @typedef {Object} Props
   * @property {object} [weapon]
   * @property {boolean} [showZeros]
   * @property {boolean} [compact]
   * @property {boolean} [isMining]
   */

  /** @type {Props} */
  let { weapon = null, showZeros = false, compact = false, isMining = false } = $props();

  // Damage type definitions with CSS variable references for colors
  // Colors are defined globally in style.css as --damage-{type}
  // Mining weapons/amps use the Impact column but display as "Mining"
  let damageTypes = $derived([
    { key: 'Impact', label: isMining ? 'Mining' : 'Impact', short: isMining ? 'Min' : 'Imp', colorVar: '--damage-impact' },
    { key: 'Cut', label: 'Cut', short: 'Cut', colorVar: '--damage-cut' },
    { key: 'Stab', label: 'Stab', short: 'Stb', colorVar: '--damage-stab' },
    { key: 'Penetration', label: 'Penetration', short: 'Pen', colorVar: '--damage-penetration' },
    { key: 'Shrapnel', label: 'Shrapnel', short: 'Shr', colorVar: '--damage-shrapnel' },
    { key: 'Burn', label: 'Burn', short: 'Brn', colorVar: '--damage-burn' },
    { key: 'Cold', label: 'Cold', short: 'Cld', colorVar: '--damage-cold' },
    { key: 'Acid', label: 'Acid', short: 'Acd', colorVar: '--damage-acid' },
    { key: 'Electric', label: 'Electric', short: 'Elc', colorVar: '--damage-electric' },
  ]);

  let damage = $derived(weapon?.Properties?.Damage || {});

  let totalDamage = $derived(damageTypes.reduce((sum, type) => sum + (damage[type.key] || 0), 0));

  // Find the maximum damage value for bar scaling
  let maxDamage = $derived(Math.max(...damageTypes.map(type => damage[type.key] || 0), 0));

  // Mining: only show Mining (Impact). Edit mode: show all unless mining. View: non-zero only.
  let visibleTypes = $derived(isMining
    ? damageTypes.filter(type => type.key === 'Impact')
    : ($editMode || showZeros)
      ? damageTypes
      : damageTypes.filter(type => damage[type.key] > 0));

  // In edit mode, always show the grid even if no damage
  let hasAnyDamage = $derived($editMode || visibleTypes.length > 0);

  // Calculate bar percentage relative to max value (highest = 100%)
  function getDamagePercentage(value) {
    if (!maxDamage || !value) return 0;
    return (value / maxDamage) * 100;
  }
</script>

{#if hasAnyDamage}
  <div class="damage-grid" class:compact class:editing={$editMode}>
    {#if !compact}
      <div class="damage-total">
        <span class="total-label">Total Damage</span>
        <span class="total-value">{totalDamage.toFixed(1)}</span>
      </div>

      {#if $editMode}
        <!-- Edit mode: compact 3-column grid with short labels -->
        <div class="damage-edit-grid">
          {#each visibleTypes as type}
            {@const value = damage[type.key] || 0}
            <div class="damage-edit-item" class:has-value={value > 0}>
              <span class="damage-edit-label" style="color: var({type.colorVar})" title={type.label}>
                {type.short}
              </span>
              <InlineEdit
                value={value || null}
                path="Properties.Damage.{type.key}"
                type="number"
                min={0}
                step={0.1}
                placeholder="0"
              />
            </div>
          {/each}
        </div>
      {:else}
        <!-- View mode: list with bars -->
        <div class="damage-types">
          {#each visibleTypes as type}
            {@const value = damage[type.key] || 0}
            {@const percentage = getDamagePercentage(value)}
            <div class="damage-item" class:has-value={value > 0}>
              <div class="damage-header">
                <span class="damage-type" style="color: var({type.colorVar})">{type.label}</span>
                <span class="damage-value">{value.toFixed(1)}</span>
              </div>
              <div class="damage-bar-bg">
                <div
                  class="damage-bar"
                  style="width: {percentage}%; background-color: var({type.colorVar})"
                ></div>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    {:else}
      <!-- Compact inline view (not editable) -->
      <div class="compact-damages">
        {#each visibleTypes as type}
          {@const value = damage[type.key] || 0}
          <span class="compact-damage" style="color: var({type.colorVar})">
            <span class="compact-label">{type.short}</span>
            <span class="compact-value">{value.toFixed(0)}</span>
          </span>
        {/each}
        <span class="compact-total">
          <span class="compact-label">Tot</span>
          <span class="compact-value">{totalDamage.toFixed(0)}</span>
        </span>
      </div>
    {/if}
  </div>
{:else}
  <div class="no-damage">No damage data available</div>
{/if}

<style>
  .damage-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .damage-total {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 10px 14px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
    font-size: 15px;
  }

  .total-label {
    font-weight: 500;
    color: var(--text-color);
  }

  .total-value {
    font-weight: 700;
    font-size: 18px;
    color: var(--accent-color, #4a9eff);
  }

  /* Edit mode grid - always 3 columns, compact */
  .damage-edit-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
  }

  .damage-edit-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 6px 8px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
  }

  .damage-edit-item:not(.has-value) {
    opacity: 0.6;
  }

  .damage-edit-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .damage-edit-item :global(.inline-edit) {
    width: auto;
  }

  .damage-edit-item :global(.inline-edit input) {
    width: 55px;
    max-width: 55px;
    padding: 4px 6px;
    font-size: 13px;
    text-align: left;
  }

  /* View mode styles */
  .damage-types {
    display: grid;
    gap: 8px;
  }

  .damage-item {
    background-color: var(--bg-color, var(--primary-color));
    padding: 8px 12px;
    border-radius: 4px;
  }

  .damage-item:not(.has-value) {
    opacity: 0.5;
  }

  .damage-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 4px;
    font-size: 13px;
  }

  .damage-type {
    font-weight: 500;
  }

  .damage-value {
    font-weight: 600;
    color: var(--text-color);
  }

  .damage-bar-bg {
    height: 4px;
    background-color: var(--secondary-color);
    border-radius: 2px;
    overflow: hidden;
  }

  .damage-bar {
    height: 100%;
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  /* Compact mode */
  .damage-grid.compact {
    flex-direction: row;
  }

  .compact-damages {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }

  .compact-damage,
  .compact-total {
    display: flex;
    gap: 4px;
    padding: 4px 6px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
    font-size: 11px;
  }

  .compact-label {
    opacity: 0.8;
  }

  .compact-value {
    font-weight: 600;
  }

  .compact-total {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .compact-total .compact-label {
    color: rgba(255, 255, 255, 0.8);
  }

  .no-damage {
    padding: 12px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 14px;
  }

  /* Responsive: 2 columns on very narrow */
  @media (max-width: 350px) {
    .damage-edit-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .damage-item {
      padding: 6px 10px;
    }

    .damage-header {
      font-size: 12px;
    }
  }
</style>
