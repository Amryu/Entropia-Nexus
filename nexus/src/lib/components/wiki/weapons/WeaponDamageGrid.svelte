<!--
  @component WeaponDamageGrid
  Displays all 9 damage types in a grid format.
  Highlights non-zero values and shows totals.
-->
<script>
  // @ts-nocheck

  /** @type {object} Weapon entity */
  export let weapon = null;

  /** @type {boolean} Show zero values */
  export let showZeros = false;

  /** @type {boolean} Compact single-line display */
  export let compact = false;

  // Damage type definitions with colors
  const damageTypes = [
    { key: 'Impact', label: 'Impact', color: '#6b7280' },
    { key: 'Cut', label: 'Cut', color: '#ef4444' },
    { key: 'Stab', label: 'Stab', color: '#f97316' },
    { key: 'Penetration', label: 'Penetration', color: '#eab308' },
    { key: 'Shrapnel', label: 'Shrapnel', color: '#84cc16' },
    { key: 'Burn', label: 'Burn', color: '#f59e0b' },
    { key: 'Cold', label: 'Cold', color: '#06b6d4' },
    { key: 'Acid', label: 'Acid', color: '#22c55e' },
    { key: 'Electric', label: 'Electric', color: '#8b5cf6' },
  ];

  $: damage = weapon?.Properties?.Damage || {};

  $: totalDamage = damageTypes.reduce((sum, type) => sum + (damage[type.key] || 0), 0);

  $: visibleTypes = showZeros
    ? damageTypes
    : damageTypes.filter(type => damage[type.key] > 0);

  $: hasAnyDamage = visibleTypes.length > 0;

  function getDamagePercentage(value) {
    if (!totalDamage || !value) return 0;
    return (value / totalDamage) * 100;
  }
</script>

{#if hasAnyDamage}
  <div class="damage-grid" class:compact>
    {#if !compact}
      <div class="damage-total">
        <span class="total-label">Total Damage</span>
        <span class="total-value">{totalDamage.toFixed(1)}</span>
      </div>

      <div class="damage-types">
        {#each visibleTypes as type}
          {@const value = damage[type.key] || 0}
          {@const percentage = getDamagePercentage(value)}
          <div class="damage-item">
            <div class="damage-header">
              <span class="damage-type" style="color: {type.color}">{type.label}</span>
              <span class="damage-value">{value.toFixed(1)}</span>
            </div>
            <div class="damage-bar-bg">
              <div
                class="damage-bar"
                style="width: {percentage}%; background-color: {type.color}"
              ></div>
            </div>
          </div>
        {/each}
      </div>
    {:else}
      <!-- Compact inline view -->
      <div class="compact-damages">
        {#each visibleTypes as type}
          {@const value = damage[type.key] || 0}
          <span class="compact-damage" style="color: {type.color}">
            <span class="compact-label">{type.label.slice(0, 3)}</span>
            <span class="compact-value">{value.toFixed(0)}</span>
          </span>
        {/each}
        <span class="compact-total">
          <span class="compact-label">Total</span>
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

  .damage-types {
    display: grid;
    gap: 8px;
  }

  .damage-item {
    background-color: var(--bg-color, var(--primary-color));
    padding: 8px 12px;
    border-radius: 4px;
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
    gap: 8px;
    align-items: center;
  }

  .compact-damage,
  .compact-total {
    display: flex;
    gap: 4px;
    padding: 4px 8px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
    font-size: 12px;
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

  /* Mobile adjustments */
  @media (max-width: 767px) {
    .damage-item {
      padding: 6px 10px;
    }

    .damage-header {
      font-size: 12px;
    }
  }
</style>
