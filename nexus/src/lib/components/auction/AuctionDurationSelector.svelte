<!--
  @component AuctionDurationSelector
  Duration picker for auction creation/editing.
  Respects buyout-only 365 day max vs 30 day normal max.
-->
<script>
  import { getMaxDuration } from '$lib/common/auctionUtils.js';



  

  
  /**
   * @typedef {Object} Props
   * @property {number} [value]
   * @property {number|null} [buyoutPrice]
   * @property {number} [startingBid]
   * @property {(value: number) => void} [onchange]
   */

  /** @type {Props} */
  let { value = $bindable(7), buyoutPrice = null, startingBid = 0, onchange } = $props();

  let maxDuration = $derived(getMaxDuration({ starting_bid: startingBid, buyout_price: buyoutPrice }));
  let presets = $derived(maxDuration > 30
    ? [1, 3, 7, 14, 30, 90, 180, 365]
    : [1, 3, 7, 14, 30]);

  // Clamp value if max changes
  $effect(() => {
    if (value > maxDuration) {
      value = maxDuration;
      onchange?.(value);
    }
  });

  function handlePreset(days) {
    value = days;
    onchange?.(value);
  }

  function handleInput(e) {
    const v = parseInt(e.target.value, 10);
    if (Number.isFinite(v) && v >= 1 && v <= maxDuration) {
      value = v;
      onchange?.(value);
    }
  }
</script>

<div class="duration-selector">
  <label class="duration-label" for="auction-duration">Duration</label>
  <div class="presets">
    {#each presets as days}
      <button
        class="preset-btn"
        class:active={value === days}
        onclick={() => handlePreset(days)}
        disabled={days > maxDuration}
      >
        {days}d
      </button>
    {/each}
  </div>
  <div class="custom-input">
    <input
      type="number"
      id="auction-duration"
      {value}
      min="1"
      max={maxDuration}
      oninput={handleInput}
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
    appearance: textfield;
    -moz-appearance: textfield;
  }

  .duration-input::-webkit-outer-spin-button,
  .duration-input::-webkit-inner-spin-button {
    appearance: none;
    -webkit-appearance: none;
  }

  .duration-unit {
    font-size: 0.8rem;
    color: var(--text-muted);
  }
</style>
