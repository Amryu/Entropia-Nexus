<!--
  @component MobDamageGrid
  Displays mob damage type breakdown as bars.
-->
<script>
  // @ts-nocheck
  import MissingFieldCTA from '$lib/components/wiki/MissingFieldCTA.svelte';

  /**
   * @typedef {Object} Props
   * @property {any} [damageSpread]
   * @property {string} [label]
   * @property {(() => void) | null} [onContribute]
   */

  /** @type {Props} */
  let { damageSpread = null, label = '', onContribute = null } = $props();

  const damageTypes = [
    { key: 'Impact', color: 'var(--damage-impact)' },
    { key: 'Cut', color: 'var(--damage-cut)' },
    { key: 'Stab', color: 'var(--damage-stab)' },
    { key: 'Penetration', color: 'var(--damage-penetration)' },
    { key: 'Shrapnel', color: 'var(--damage-shrapnel)' },
    { key: 'Burn', color: 'var(--damage-burn)' },
    { key: 'Cold', color: 'var(--damage-cold)' },
    { key: 'Acid', color: 'var(--damage-acid)' },
    { key: 'Electric', color: 'var(--damage-electric)' }
  ];

  let activeDamage = $derived(damageSpread
    ? damageTypes.filter(d => damageSpread[d.key] && damageSpread[d.key] > 0)
    : []);

  let maxValue = $derived(activeDamage.length > 0
    ? Math.max(...activeDamage.map(d => damageSpread[d.key]))
    : 100);
</script>

{#if label}
  <div class="damage-label">{label}</div>
{/if}

<div class="damage-grid">
  {#if activeDamage.length === 0}
    <div class="no-damage">
      No damage data{#if onContribute}&nbsp;<MissingFieldCTA field="damage types" category="mob" compact onContribute={onContribute} />{/if}
    </div>
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
