<!--
  @component WeaponEconomy
  Displays weapon economy stats: TT values, decay, cost, ammo.
  Grouped layout:
  - Row 1: Max TT + Min TT
  - Row 2: Cost/Use + Decay + Ammo Burn
  - Row 3: Reload/Uses per min (toggleable) + Ammo
-->
<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { clampDecimals } from '$lib/util';

  /** @type {object} Weapon entity */
  export let weapon = null;

  /** @type {boolean} Compact mode */
  export let compact = false;

  $: economy = weapon?.Properties?.Economy || {};
  $: ammo = weapon?.Ammo;

  // Calculate cost per use
  $: costPerUse = economy.Decay !== null && economy.Decay !== undefined
    ? economy.Decay + ((economy.AmmoBurn || 0) / 100)
    : null;

  // Calculate reload time
  $: reload = weapon?.Properties?.UsesPerMinute
    ? 60 / weapon.Properties.UsesPerMinute
    : null;

  // Toggle state for Reload vs Uses/min - default to showing Reload
  let showReload = true;

  // Load preference from localStorage on mount
  onMount(() => {
    try {
      const stored = localStorage.getItem('weapon-economy-show-reload');
      if (stored !== null) {
        showReload = stored === 'true';
      }
    } catch (e) {
      // localStorage not available, use default
    }
  });

  // Toggle and persist preference
  function toggleReloadUsesMin() {
    showReload = !showReload;
    try {
      localStorage.setItem('weapon-economy-show-reload', String(showReload));
    } catch (e) {
      // localStorage not available, ignore
    }
  }

  // Format helpers
  function formatPED(value, decimals = 2) {
    if (value === null || value === undefined) return 'N/A';
    return `${clampDecimals(value, decimals, 8)} PED`;
  }

  function formatPEC(value, decimals = 4) {
    if (value === null || value === undefined) return 'N/A';
    return `${value.toFixed(decimals)} PEC`;
  }
</script>

<div class="weapon-economy" class:compact>
  <!-- Group 1: Max + Min TT -->
  <div class="economy-row">
    <div class="economy-item">
      <span class="economy-label">Max TT</span>
      <span class="economy-value">{formatPED(economy.MaxTT)}</span>
    </div>
    <div class="economy-item">
      <span class="economy-label">Min TT</span>
      <span class="economy-value">{formatPED(economy.MinTT)}</span>
    </div>
  </div>

  <!-- Group 2: Cost/Use + Decay + Ammo Burn -->
  <div class="economy-row">
    <div class="economy-item highlight">
      <span class="economy-label">Cost/Use</span>
      <span class="economy-value">{formatPEC(costPerUse)}</span>
    </div>
    <div class="economy-item">
      <span class="economy-label">Decay</span>
      <span class="economy-value">{formatPEC(economy.Decay)}</span>
    </div>
    {#if ammo?.Name}
      <div class="economy-item">
        <span class="economy-label">Ammo Burn</span>
        <span class="economy-value">{economy.AmmoBurn ?? 'N/A'}</span>
      </div>
    {/if}
  </div>

  {#if !compact}
    <!-- Group 3: Reload/Uses toggle + Ammo -->
    <div class="economy-row last-row">
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="economy-item toggleable" on:click={toggleReloadUsesMin} title="Click to toggle between Reload and Uses/min">
        {#if showReload}
          <span class="economy-label">
            Reload
            <span class="toggle-hint">&#x21c4;</span>
          </span>
          <span class="economy-value">{reload ? `${reload.toFixed(2)}s` : 'N/A'}</span>
        {:else}
          <span class="economy-label">
            Uses/min
            <span class="toggle-hint">&#x21c4;</span>
          </span>
          <span class="economy-value">{weapon?.Properties?.UsesPerMinute ? clampDecimals(weapon.Properties.UsesPerMinute, 0, 2) : 'N/A'}</span>
        {/if}
      </div>
      {#if ammo?.Name}
        <div class="economy-item ammo-item">
          <span class="economy-label">Ammo</span>
          <span class="economy-value">{ammo.Name}</span>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .weapon-economy {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .economy-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .economy-row.last-row {
    margin-top: 4px;
    padding-top: 8px;
    border-top: 1px dashed var(--border-color, #555);
  }

  .economy-item {
    flex: 1;
    min-width: 120px;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 8px 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
    font-size: 13px;
  }

  .economy-item.highlight {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .economy-item.highlight .economy-label {
    color: rgba(255, 255, 255, 0.8);
  }

  .economy-item.highlight .economy-value {
    color: white;
  }

  .economy-item.ammo-item {
    flex: 2;
    min-width: 200px;
  }

  .economy-item.toggleable {
    cursor: pointer;
    transition: background-color 0.15s;
    user-select: none;
  }

  .economy-item.toggleable:hover {
    background-color: var(--hover-color);
  }

  .toggle-hint {
    font-size: 10px;
    color: var(--text-muted, #999);
    margin-left: 4px;
    opacity: 0.7;
  }

  .economy-item.toggleable:hover .toggle-hint {
    opacity: 1;
  }

  .economy-label {
    color: var(--text-muted, #999);
    font-size: 12px;
    display: flex;
    align-items: center;
  }

  .economy-value {
    font-weight: 600;
    color: var(--text-color);
  }

  /* Compact mode */
  .weapon-economy.compact .economy-row {
    flex-wrap: wrap;
  }

  .weapon-economy.compact .economy-item {
    min-width: 100px;
    padding: 6px 10px;
    font-size: 12px;
  }

  .weapon-economy.compact .economy-item.ammo-item {
    min-width: 150px;
  }

  /* Mobile adjustments */
  @media (max-width: 767px) {
    .economy-item {
      min-width: calc(50% - 4px);
      padding: 6px 10px;
      font-size: 12px;
    }

    .economy-item.ammo-item {
      flex: 1 1 100%;
      min-width: 100%;
    }
  }
</style>
