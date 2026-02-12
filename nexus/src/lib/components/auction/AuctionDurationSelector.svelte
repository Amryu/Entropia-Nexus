<!--
  @component AuctionDurationSelector
  Duration picker for auction creation/editing.
  Respects buyout-only 365 day max vs 30 day normal max.
-->
<script>
  import { createEventDispatcher } from 'svelte';
  import { getMaxDuration } from '$lib/common/auctionUtils.js';

  const dispatch = createEventDispatcher();

  /** @type {number} Current duration in days */
  export let value = 7;

  /** @type {number|null} Buyout price (null if none) */
  export let buyoutPrice = null;

  /** @type {number} Starting bid */
  export let startingBid = 0;

  $: maxDuration = getMaxDuration({ starting_bid: startingBid, buyout_price: buyoutPrice });
  $: presets = maxDuration > 30
    ? [1, 3, 7, 14, 30, 90, 180, 365]
    : [1, 3, 7, 14, 30];

  // Clamp value if max changes
  $: if (value > maxDuration) {
    value = maxDuration;
    dispatch('change', value);
  }

  function handlePreset(days) {
    value = days;
    dispatch('change', value);
  }

  function handleInput(e) {
    const v = parseInt(e.target.value, 10);
    if (Number.isFinite(v) && v >= 1 && v <= maxDuration) {
      value = v;
      dispatch('change', value);
    }
  }
</script>

<div class="duration-selector">
  <label class="duration-label">Duration</label>
  <div class="presets">
    {#each presets as days}
      <button
        class="preset-btn"
        class:active={value === days}
        on:click={() => handlePreset(days)}
        disabled={days > maxDuration}
      >
        {days}d
      </button>
    {/each}
  </div>
  <div class="custom-input">
    <input
      type="number"
      {value}
      min="1"
      max={maxDuration}
      on:input={handleInput}
      class="duration-input"
    />
    <span class="duration-unit">days (max {maxDuration})</span>
  </div>
</div>

<style>
  .duration-selector {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .duration-label {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-muted);
  }

  .presets {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .preset-btn {
    padding: 0.35rem 0.75rem;
    font-size: 0.8rem;
    border: 1px solid var(--border-color);
    background: var(--secondary-color);
    color: var(--text-color);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .preset-btn:hover:not(:disabled) {
    border-color: var(--accent-color);
  }

  .preset-btn.active {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
  }

  .preset-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .custom-input {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .duration-input {
    width: 80px;
    padding: 0.4rem 0.5rem;
    font-size: 0.85rem;
    border: 1px solid var(--border-color);
    background: var(--secondary-color);
    color: var(--text-color);
    border-radius: 6px;
    -moz-appearance: textfield;
  }

  .duration-input::-webkit-outer-spin-button,
  .duration-input::-webkit-inner-spin-button {
    -webkit-appearance: none;
  }

  .duration-unit {
    font-size: 0.8rem;
    color: var(--text-muted);
  }
</style>
