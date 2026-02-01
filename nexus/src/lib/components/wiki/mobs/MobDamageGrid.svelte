<!--
  @component MobDamageGrid
  Displays mob damage type breakdown as bars.
-->
<script>
  // @ts-nocheck
  export let damageSpread = null;
  export let label = '';

  const damageTypes = [
    { key: 'Impact', color: '#60a5fa' },
    { key: 'Cut', color: '#f87171' },
    { key: 'Stab', color: '#4ade80' },
    { key: 'Penetration', color: '#fbbf24' },
    { key: 'Shrapnel', color: '#a78bfa' },
    { key: 'Burn', color: '#fb923c' },
    { key: 'Cold', color: '#22d3ee' },
    { key: 'Acid', color: '#a3e635' },
    { key: 'Electric', color: '#c084fc' }
  ];

  $: activeDamage = damageSpread
    ? damageTypes.filter(d => damageSpread[d.key] && damageSpread[d.key] > 0)
    : [];

  $: maxValue = activeDamage.length > 0
    ? Math.max(...activeDamage.map(d => damageSpread[d.key]))
    : 100;
</script>

{#if label}
  <div class="damage-label">{label}</div>
{/if}

<div class="damage-grid">
  {#if activeDamage.length === 0}
    <div class="no-damage">No damage data</div>
  {:else}
    {#each activeDamage as damage}
      {@const value = damageSpread[damage.key] || 0}
      {@const percent = maxValue > 0 ? (value / maxValue) * 100 : 0}
      <div class="damage-row">
        <span class="damage-type" style="color: {damage.color}">{damage.key}</span>
        <div class="damage-bar-container">
          <div
            class="damage-bar"
            style="width: {percent}%; background-color: {damage.color}"
          ></div>
        </div>
        <span class="damage-value">{value.toFixed(1)}%</span>
      </div>
    {/each}
  {/if}
</div>

<style>
  .damage-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted, #999);
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .damage-grid {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 10px;
  }

  .damage-grid:last-child {
    margin-bottom: 0;
  }

  .damage-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
  }

  .damage-type {
    width: 70px;
    font-weight: 500;
    flex-shrink: 0;
  }

  .damage-bar-container {
    flex: 1;
    height: 8px;
    background-color: var(--bg-color, rgba(0, 0, 0, 0.2));
    border-radius: 4px;
    overflow: hidden;
  }

  .damage-bar {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s ease;
  }

  .damage-value {
    width: 45px;
    text-align: right;
    color: var(--text-muted, #999);
    flex-shrink: 0;
  }

  .no-damage {
    color: var(--text-muted, #999);
    font-style: italic;
    font-size: 12px;
    padding: 8px 0;
  }
</style>
