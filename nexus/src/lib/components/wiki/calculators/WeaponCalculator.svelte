<!--
  @component WeaponCalculator
  Calculates and displays weapon DPS, DPP, Cost, and other derived stats.
  Includes skill level slider that affects calculated values.
-->
<script>
  // @ts-nocheck
  import { clampDecimals } from '$lib/util';

  /** @type {object} Weapon entity */
  export let weapon = null;

  /** @type {boolean} Show skill slider */
  export let showSkillSlider = true;

  /** @type {boolean} Compact mode (fewer displayed stats) */
  export let compact = false;

  /** @type {string} Layout variant: 'inline', 'grid', 'list' */
  export let variant = 'grid';

  // Skill level state (0-100%)
  let skillLevel = 75;

  // Calculator functions
  function getTotalDamage(item) {
    if (!item?.Properties?.Damage) return null;
    const d = item.Properties.Damage;
    return (d.Impact || 0) + (d.Cut || 0) + (d.Stab || 0) + (d.Penetration || 0) +
           (d.Shrapnel || 0) + (d.Burn || 0) + (d.Cold || 0) + (d.Acid || 0) + (d.Electric || 0);
  }

  function getEffectiveDamage(item, skill = 75) {
    const totalDamage = getTotalDamage(item);
    if (totalDamage === null || totalDamage === 0) return null;

    // Damage scaling based on skill level
    // At 0% skill: ~66% of max damage (0.88*0.75)
    // At 100% skill: ~90% of max damage (0.88*0.75 + 0.12*1.75)
    const minMultiplier = 0.88 * 0.75;
    const maxMultiplier = 0.88 * 0.75 + 0.12 * 1.75;
    const multiplier = minMultiplier + (maxMultiplier - minMultiplier) * (skill / 100);

    return totalDamage * multiplier;
  }

  function getReload(item) {
    if (!item?.Properties?.UsesPerMinute) return null;
    return 60 / item.Properties.UsesPerMinute;
  }

  function getCost(item) {
    const decay = item?.Properties?.Economy?.Decay;
    const ammoBurn = item?.Properties?.Economy?.AmmoBurn ?? 0;
    if (decay === null || decay === undefined) return null;
    return decay + (ammoBurn / 100);
  }

  function getDps(item, skill = 75) {
    const reload = getReload(item);
    const effectiveDamage = getEffectiveDamage(item, skill);
    if (effectiveDamage === null || reload === null) return null;
    return effectiveDamage / reload;
  }

  function getDpp(item, skill = 75) {
    const cost = getCost(item);
    const effectiveDamage = getEffectiveDamage(item, skill);
    if (cost === null || cost === 0 || effectiveDamage === null) return null;
    return effectiveDamage / cost;
  }

  function getTotalUses(item) {
    const maxTT = item?.Properties?.Economy?.MaxTT;
    const minTT = item?.Properties?.Economy?.MinTT ?? 0;
    const decay = item?.Properties?.Economy?.Decay;
    if (maxTT === null || maxTT === undefined || decay === null || decay === undefined || decay === 0) return null;
    return Math.floor((maxTT - minTT) / (decay / 100));
  }

  function getCyclePerRepair(item) {
    const totalUses = getTotalUses(item);
    const cost = getCost(item);
    if (totalUses === null || cost === null) return null;
    return totalUses * (cost / 100);
  }

  function getCyclePerHour(item) {
    const reload = getReload(item);
    const cost = getCost(item);
    if (reload === null || cost === null) return null;
    return (3600 / reload) * (cost / 100);
  }

  function getTimeToBreak(item) {
    const cyclePerRepair = getCyclePerRepair(item);
    const cyclePerHour = getCyclePerHour(item);
    if (cyclePerRepair === null || cyclePerHour === null || cyclePerHour === 0) return null;
    return cyclePerRepair / cyclePerHour;
  }

  // Reactive calculations
  $: totalDamage = getTotalDamage(weapon);
  $: effectiveDamage = getEffectiveDamage(weapon, skillLevel);
  $: reload = getReload(weapon);
  $: cost = getCost(weapon);
  $: dps = getDps(weapon, skillLevel);
  $: dpp = getDpp(weapon, skillLevel);
  $: totalUses = getTotalUses(weapon);
  $: cyclePerRepair = getCyclePerRepair(weapon);
  $: cyclePerHour = getCyclePerHour(weapon);
  $: timeToBreak = getTimeToBreak(weapon);
  $: usesPerMinute = reload ? clampDecimals(60 / reload, 0, 2) : null;

  // Format helpers
  function formatValue(value, decimals = 2, suffix = '') {
    if (value === null || value === undefined) return 'N/A';
    return `${value.toFixed(decimals)}${suffix}`;
  }
</script>

<div class="weapon-calculator" class:compact class:variant-inline={variant === 'inline'} class:variant-grid={variant === 'grid'} class:variant-list={variant === 'list'}>
  {#if showSkillSlider}
    <div class="skill-slider-section">
      <label class="slider-label">
        <span class="slider-label-text">Skill Level</span>
        <span class="slider-value">{skillLevel}%</span>
      </label>
      <div class="slider-container">
        <input
          type="range"
          class="wiki-slider"
          min="0"
          max="100"
          bind:value={skillLevel}
        />
        <div class="slider-marks">
          <span>0%</span>
          <span>50%</span>
          <span>100%</span>
        </div>
      </div>
    </div>
  {/if}

  <div class="calculated-stats">
    <div class="stat-group primary-stats">
      <div class="stat-item highlight">
        <span class="stat-label">DPS</span>
        <span class="stat-value">{formatValue(dps, 2, '/s')}</span>
      </div>
      <div class="stat-item highlight">
        <span class="stat-label">DPP</span>
        <span class="stat-value">{formatValue(dpp, 4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Eff. Damage</span>
        <span class="stat-value">{formatValue(effectiveDamage, 1)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Cost/Use</span>
        <span class="stat-value">{formatValue(cost, 4, ' PEC')}</span>
      </div>
    </div>

    {#if !compact}
      <div class="stat-group secondary-stats">
        <div class="stat-item">
          <span class="stat-label">Total Damage</span>
          <span class="stat-value">{formatValue(totalDamage, 1)}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Reload</span>
          <span class="stat-value">{formatValue(reload, 2, 's')}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Uses/min</span>
          <span class="stat-value">{usesPerMinute ?? 'N/A'}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Total Uses</span>
          <span class="stat-value">{totalUses ?? 'N/A'}</span>
        </div>
      </div>

      <div class="stat-group economy-stats">
        <div class="stat-item">
          <span class="stat-label">PED/repair</span>
          <span class="stat-value">{formatValue(cyclePerRepair, 2, ' PED')}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">PED/hour</span>
          <span class="stat-value">{formatValue(cyclePerHour, 2, ' PED')}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Time to break</span>
          <span class="stat-value">{formatValue(timeToBreak, 2, 'h')}</span>
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .weapon-calculator {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .skill-slider-section {
    padding: 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  .slider-label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-size: 14px;
  }

  .slider-label-text {
    color: var(--text-muted, #999);
  }

  .slider-value {
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
  }

  .slider-container {
    position: relative;
  }

  .wiki-slider {
    width: 100%;
    -webkit-appearance: none;
    appearance: none;
    height: 6px;
    border-radius: 3px;
    background-color: var(--secondary-color);
    outline: none;
  }

  .wiki-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background-color: var(--accent-color, #4a9eff);
    cursor: pointer;
    border: 2px solid var(--bg-color, var(--primary-color));
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  }

  .wiki-slider::-moz-range-thumb {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background-color: var(--accent-color, #4a9eff);
    cursor: pointer;
    border: 2px solid var(--bg-color, var(--primary-color));
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  }

  .slider-marks {
    display: flex;
    justify-content: space-between;
    margin-top: 4px;
    font-size: 11px;
    color: var(--text-muted, #999);
  }

  .calculated-stats {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .stat-group {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 8px;
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 8px 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
    font-size: 13px;
  }

  .stat-item.highlight {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .stat-item.highlight .stat-label {
    color: rgba(255, 255, 255, 0.8);
  }

  .stat-label {
    color: var(--text-muted, #999);
    font-size: 12px;
  }

  .stat-value {
    font-weight: 600;
    color: var(--text-color);
  }

  .stat-item.highlight .stat-value {
    color: white;
  }

  /* Compact mode */
  .weapon-calculator.compact .calculated-stats {
    gap: 8px;
  }

  .weapon-calculator.compact .stat-group {
    grid-template-columns: repeat(2, 1fr);
  }

  /* Inline variant */
  .weapon-calculator.variant-inline {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 12px;
  }

  .weapon-calculator.variant-inline .skill-slider-section {
    flex: 0 0 200px;
  }

  .weapon-calculator.variant-inline .calculated-stats {
    flex: 1;
    min-width: 300px;
  }

  /* List variant */
  .weapon-calculator.variant-list .stat-group {
    display: flex;
    flex-direction: column;
  }

  .weapon-calculator.variant-list .stat-item {
    padding: 6px 10px;
  }

  /* Mobile adjustments - aligned with global 900px breakpoint */
  @media (max-width: 899px) {
    .stat-group {
      grid-template-columns: repeat(2, 1fr);
    }

    .stat-item {
      padding: 6px 10px;
      font-size: 12px;
    }

    .weapon-calculator.variant-inline {
      flex-direction: column;
    }

    .weapon-calculator.variant-inline .skill-slider-section {
      flex: 1;
      width: 100%;
    }
  }
</style>
