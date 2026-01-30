<!--
  @component WeaponEffects
  Displays weapon effects on equip and on use.
-->
<script>
  // @ts-nocheck
  import { getTimeString } from '$lib/util';

  /** @type {object} Weapon entity */
  export let weapon = null;

  /** @type {boolean} Show both equip and use effects together */
  export let combined = false;

  /** @type {string} Which effects to show: 'all', 'equip', 'use' */
  export let show = 'all';

  $: effectsOnEquip = weapon?.EffectsOnEquip || [];
  $: effectsOnUse = weapon?.EffectsOnUse || [];

  $: showEquip = show === 'all' || show === 'equip';
  $: showUse = show === 'all' || show === 'use';

  $: hasEffects = (showEquip && effectsOnEquip.length > 0) || (showUse && effectsOnUse.length > 0);

  // Sort effects alphabetically
  $: sortedEquipEffects = [...effectsOnEquip].sort((a, b) => a.Name?.localeCompare(b.Name) || 0);
  $: sortedUseEffects = [...effectsOnUse].sort((a, b) => a.Name?.localeCompare(b.Name) || 0);

  function formatEffectValue(effect) {
    const strength = effect.Values?.Strength ?? '?';
    const unit = effect.Values?.Unit ?? '';
    return `${strength}${unit}`;
  }

  function formatDuration(effect) {
    const duration = effect.Values?.DurationSeconds;
    if (!duration) return '';
    return `for ${getTimeString(duration)}`;
  }
</script>

{#if hasEffects}
  <div class="weapon-effects" class:combined>
    {#if showEquip && effectsOnEquip.length > 0}
      <div class="effects-section">
        {#if !combined || show === 'all'}
          <h4 class="effects-title">
            <span class="effects-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20.24 12.24a6 6 0 00-8.49-8.49L5 10.5V19h8.5z" />
                <line x1="16" y1="8" x2="2" y2="22" />
              </svg>
            </span>
            Effects on Equip
          </h4>
        {/if}
        <ul class="effects-list">
          {#each sortedEquipEffects as effect}
            <li class="effect-item equip">
              <span class="effect-name">{effect.Name}</span>
              <span class="effect-value">{formatEffectValue(effect)}</span>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    {#if showUse && effectsOnUse.length > 0}
      <div class="effects-section">
        {#if !combined || show === 'all'}
          <h4 class="effects-title">
            <span class="effects-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
            </span>
            Effects on Use
          </h4>
        {/if}
        <ul class="effects-list">
          {#each sortedUseEffects as effect}
            <li class="effect-item use">
              <span class="effect-name">{effect.Name}</span>
              <span class="effect-details">
                <span class="effect-value">{formatEffectValue(effect)}</span>
                {#if effect.Values?.DurationSeconds}
                  <span class="effect-duration">{formatDuration(effect)}</span>
                {/if}
              </span>
            </li>
          {/each}
        </ul>
      </div>
    {/if}
  </div>
{:else}
  <div class="no-effects">No effects</div>
{/if}

<style>
  .weapon-effects {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .weapon-effects.combined {
    flex-direction: row;
    flex-wrap: wrap;
  }

  .weapon-effects.combined .effects-section {
    flex: 1;
    min-width: 200px;
  }

  .effects-section {
    width: 100%;
  }

  .effects-title {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0 0 8px 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .effects-icon {
    display: flex;
    color: var(--accent-color, #4a9eff);
  }

  .effects-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .effect-item {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 8px 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
    font-size: 13px;
    border-left: 3px solid transparent;
  }

  .effect-item.equip {
    border-left-color: var(--success-color, #4ade80);
  }

  .effect-item.use {
    border-left-color: var(--warning-color, #fbbf24);
  }

  .effect-name {
    color: var(--text-color);
    font-weight: 500;
  }

  .effect-details {
    display: flex;
    align-items: baseline;
    gap: 6px;
  }

  .effect-value {
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
  }

  .effect-duration {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .no-effects {
    padding: 12px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 14px;
  }

  /* Mobile adjustments */
  @media (max-width: 767px) {
    .weapon-effects.combined {
      flex-direction: column;
    }

    .effect-item {
      padding: 6px 10px;
      font-size: 12px;
    }
  }
</style>
