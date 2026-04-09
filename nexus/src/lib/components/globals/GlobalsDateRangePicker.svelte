<!--
  @component GlobalsDateRangePicker
  Period preset buttons (24h, 7d, 30d, 90d, 1y, All) plus a custom date range option.
  Dispatches `change` with { period, from, to } when the selection changes.
-->
<script>
  import { PERIOD_OPTIONS } from '$lib/data/globals-constants.js';

  
  
  
  
  /**
   * @typedef {Object} Props
   * @property {string} [period] - Currently active preset period
   * @property {any} [from] - Custom range start (YYYY-MM-DD string or null)
   * @property {any} [to] - Custom range end (YYYY-MM-DD string or null)
   * @property {boolean} [disabled] - Whether controls should be disabled (e.g. during loading)
   * @property {(data: {period: string, from: any, to: any}) => void} [onchange] - Called when selection changes
   */

  /** @type {Props} */
  let {
    period = $bindable('90d'),
    from = $bindable(null),
    to = $bindable(null),
    disabled = false,
    onchange
  } = $props();

  let showCustom = $state(!!(from && to));

  function selectPreset(value) {
    showCustom = false;
    from = null;
    to = null;
    period = value;
    onchange?.({ period, from: null, to: null });
  }

  function openCustom() {
    showCustom = true;
  }

  function onCustomChange() {
    if (from && to) {
      period = 'custom';
      onchange?.({ period: 'custom', from, to });
    }
  }
</script>

<div class="date-range-picker">
  <div class="presets desktop-only">
    {#each PERIOD_OPTIONS as p}
      <button
        class="period-btn"
        class:active={!showCustom && period === p.value}
        {disabled}
        onclick={() => selectPreset(p.value)}
      >
        {p.label}
      </button>
    {/each}
    <button
      class="period-btn"
      class:active={showCustom}
      {disabled}
      onclick={openCustom}
    >
      Custom
    </button>
  </div>
  <select class="period-select mobile-only" value={showCustom ? 'custom' : period} {disabled} onchange={(e) => /** @type {HTMLSelectElement} */ (e.target).value === 'custom' ? openCustom() : selectPreset(/** @type {HTMLSelectElement} */ (e.target).value)}>
    {#each PERIOD_OPTIONS as p}
      <option value={p.value}>{p.label}</option>
    {/each}
    <option value="custom">Custom</option>
  </select>
  {#if showCustom}
    <div class="custom-range">
      <input
        type="date"
        class="date-input"
        bind:value={from}
        onchange={onCustomChange}
        {disabled}
      />
      <span class="range-separator">to</span>
      <input
        type="date"
        class="date-input"
        bind:value={to}
        onchange={onCustomChange}
        {disabled}
      />
    </div>
  {/if}
</div>

<style>
  .date-range-picker {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
  }

  .presets {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  .period-btn {
    padding: 4px 12px;
    font-size: 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
  }

  .period-btn:hover:not(:disabled) {
    border-color: var(--accent-color);
    color: var(--text-color);
  }

  .period-btn.active {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: #fff;
  }

  .period-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .custom-range {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .date-input {
    padding: 4px 8px;
    font-size: 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    color-scheme: dark;
  }

  .date-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .range-separator {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .mobile-only { display: none; }

  .period-select {
    padding: 4px 8px;
    font-size: 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    cursor: pointer;
  }

  @media (max-width: 599px) {
    .desktop-only { display: none !important; }
    .mobile-only { display: block !important; }
  }
</style>
