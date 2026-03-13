<!--
  @component DateRangePicker
  Compact date range picker for selecting rental periods.
  Shows pricing preview based on selected dates.
-->
<script>
  // @ts-nocheck
  import { countDays, calculateRentalPrice, formatPrice } from '$lib/utils/rentalPricing.js';



  

  

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {string|null} [minDate]
   * @property {string|null} [maxDate]
   * @property {Set<string>} [unavailableDates]
   * @property {string|null} [selectedStart]
   * @property {string|null} [selectedEnd]
   * @property {number} [pricePerDay]
   * @property {Array} [discounts]
   * @property {number} [deposit]
   * @property {(data: {start: string|null, end: string|null}) => void} [onchange]
   */

  /** @type {Props} */
  let {
    minDate = null,
    maxDate = null,
    unavailableDates = new Set(),
    selectedStart = $bindable(null),
    selectedEnd = $bindable(null),
    pricePerDay = 0,
    discounts = [],
    deposit = 0,
    onchange
  } = $props();


  function getToday() {
    return toDateStr(new Date());
  }

  function getMaxDate() {
    const d = new Date();
    d.setFullYear(d.getFullYear() + 1);
    return toDateStr(d);
  }

  function toDateStr(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  function checkConflict(start, end) {
    const s = new Date(start + 'T00:00:00');
    const e = new Date(end + 'T00:00:00');
    for (let d = new Date(s); d <= e; d.setDate(d.getDate() + 1)) {
      if (unavailableDates.has(toDateStr(d))) return true;
    }
    return false;
  }

  function handleStartChange(e) {
    selectedStart = e.target.value || null;
    if (selectedStart && selectedEnd && selectedEnd < selectedStart) {
      selectedEnd = null;
    }
    onchange?.({ start: selectedStart, end: selectedEnd });
  }

  function handleEndChange(e) {
    selectedEnd = e.target.value || null;
    if (selectedStart && selectedEnd && selectedEnd < selectedStart) {
      selectedStart = selectedEnd;
      selectedEnd = null;
    }
    onchange?.({ start: selectedStart, end: selectedEnd });
  }
  let effectiveMin = $derived(minDate || getToday());
  let effectiveMax = $derived(maxDate || getMaxDate());
  let totalDays = $derived(selectedStart && selectedEnd ? countDays(selectedStart, selectedEnd) : 0);
  let pricing = $derived(totalDays > 0 ? calculateRentalPrice(pricePerDay, discounts, totalDays) : null);
  let hasConflict = $derived(selectedStart && selectedEnd ? checkConflict(selectedStart, selectedEnd) : false);
</script>

<div class="date-range-picker">
  <div class="date-inputs">
    <div class="date-field">
      <label for="rental-start">Start Date</label>
      <input
        type="date"
        id="rental-start"
        value={selectedStart || ''}
        min={effectiveMin}
        max={effectiveMax}
        onchange={handleStartChange}
      />
    </div>
    <div class="date-separator">&rarr;</div>
    <div class="date-field">
      <label for="rental-end">End Date</label>
      <input
        type="date"
        id="rental-end"
        value={selectedEnd || ''}
        min={selectedStart || effectiveMin}
        max={effectiveMax}
        onchange={handleEndChange}
      />
    </div>
  </div>

  {#if totalDays > 0}
    <div class="pricing-preview" class:conflict={hasConflict}>
      {#if hasConflict}
        <div class="conflict-warning">
          Selected dates include unavailable days. Please adjust your selection.
        </div>
      {:else}
        <div class="pricing-row">
          <span class="pricing-label">Duration:</span>
          <span class="pricing-value">{totalDays} day{totalDays !== 1 ? 's' : ''}</span>
        </div>
        <div class="pricing-row">
          <span class="pricing-label">Rate:</span>
          <span class="pricing-value">
            {formatPrice(pricing.pricePerDay)}/day
            {#if pricing.discountPct > 0}
              <span class="discount-tag">-{pricing.discountPct}%</span>
            {/if}
          </span>
        </div>
        <div class="pricing-row total">
          <span class="pricing-label">Total:</span>
          <span class="pricing-value">{formatPrice(pricing.totalPrice)}</span>
        </div>
        {#if deposit > 0}
          <div class="pricing-row deposit">
            <span class="pricing-label">Deposit:</span>
            <span class="pricing-value">{formatPrice(deposit)}</span>
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  .date-range-picker {
    width: 100%;
  }

  .date-inputs {
    display: flex;
    align-items: flex-end;
    gap: 0.75rem;
  }

  .date-field {
    flex: 1;
  }

  .date-field label {
    display: block;
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-muted);
    margin-bottom: 0.25rem;
  }

  .date-field input {
    width: 100%;
    padding: 0.5rem;
    background: var(--primary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.9rem;
    box-sizing: border-box;
  }

  .date-field input:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .date-separator {
    padding-bottom: 0.5rem;
    color: var(--text-muted);
    font-size: 1.2rem;
    flex-shrink: 0;
  }

  .pricing-preview {
    margin-top: 1rem;
    padding: 0.75rem;
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
  }

  .pricing-preview.conflict {
    border-color: var(--error-color);
  }

  .conflict-warning {
    color: var(--error-color);
    font-size: 0.85rem;
  }

  .pricing-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.2rem 0;
    font-size: 0.9rem;
  }

  .pricing-label {
    color: var(--text-muted);
  }

  .pricing-value {
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .pricing-row.total {
    margin-top: 0.25rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--border-color);
    font-size: 1rem;
    font-weight: 600;
  }

  .pricing-row.total .pricing-value {
    color: var(--accent-color);
    font-weight: 700;
  }

  .pricing-row.deposit {
    font-size: 0.85rem;
  }

  .pricing-row.deposit .pricing-value {
    color: var(--warning-color);
  }

  .discount-tag {
    background: var(--success-bg);
    color: var(--success-color);
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  @media (max-width: 480px) {
    .date-inputs {
      flex-direction: column;
      align-items: stretch;
    }

    .date-separator {
      text-align: center;
      padding: 0;
    }
  }
</style>
