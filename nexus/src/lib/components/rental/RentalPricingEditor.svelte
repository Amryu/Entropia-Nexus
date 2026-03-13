<!--
  @component RentalPricingEditor
  Form section for editing rental pricing: price per day, discount thresholds, deposit.
  Shows a live preview table for different durations.
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { generatePricingPreview, formatPrice } from '$lib/utils/rentalPricing.js';

  const dispatch = createEventDispatcher();

  const MAX_DISCOUNTS = 5;

  

  

  
  /**
   * @typedef {Object} Props
   * @property {number} [pricePerDay]
   * @property {Array<{minDays: number, percent: number}>} [discounts]
   * @property {number} [deposit]
   */

  /** @type {Props} */
  let { pricePerDay = $bindable(0), discounts = $bindable([]), deposit = $bindable(0) } = $props();

  let preview = $derived(pricePerDay > 0 ? generatePricingPreview(pricePerDay, discounts) : []);

  function handlePriceChange(e) {
    pricePerDay = parseFloat(e.target.value) || 0;
    emitChange();
  }

  function handleDepositChange(e) {
    deposit = parseFloat(e.target.value) || 0;
    emitChange();
  }

  function handleDiscountMinDaysChange(index, e) {
    discounts[index].minDays = parseInt(e.target.value) || 0;
    discounts = discounts;
    emitChange();
  }

  function handleDiscountPercentChange(index, e) {
    discounts[index].percent = parseFloat(e.target.value) || 0;
    discounts = discounts;
    emitChange();
  }

  function addDiscount() {
    if (discounts.length >= MAX_DISCOUNTS) return;
    discounts = [...discounts, { minDays: 7, percent: 10 }];
    emitChange();
  }

  function removeDiscount(index) {
    discounts = discounts.filter((_, i) => i !== index);
    emitChange();
  }

  function emitChange() {
    dispatch('change', { pricePerDay, discounts, deposit });
  }
</script>

<div class="pricing-editor">
  <div class="form-group">
    <label for="price-per-day">Price per Day (PED) *</label>
    <input
      type="number"
      id="price-per-day"
      value={pricePerDay || ''}
      min="0.01"
      max="100000"
      step="0.01"
      oninput={handlePriceChange}
      placeholder="e.g. 5.00"
    />
  </div>

  <div class="form-group">
    <label for="deposit">Security Deposit (PED)</label>
    <input
      type="number"
      id="deposit"
      value={deposit || ''}
      min="0"
      max="1000000"
      step="0.01"
      oninput={handleDepositChange}
      placeholder="0.00 (no deposit)"
    />
    <small>Set to 0 for no deposit</small>
  </div>

  <div class="discounts-section">
    <div class="discounts-header">
      <label>Duration Discounts</label>
      {#if discounts.length < MAX_DISCOUNTS}
        <button type="button" class="add-btn" onclick={addDiscount}>+ Add Discount</button>
      {/if}
    </div>

    {#if discounts.length === 0}
      <p class="empty-discounts">No discounts configured. Add a discount to offer reduced rates for longer rentals.</p>
    {:else}
      <div class="discount-list">
        {#each discounts as discount, i}
          <div class="discount-row">
            <div class="discount-field">
              <label for="disc-days-{i}">Min Days</label>
              <input
                type="number"
                id="disc-days-{i}"
                value={discount.minDays}
                min="2"
                max="365"
                step="1"
                oninput={(e) => handleDiscountMinDaysChange(i, e)}
              />
            </div>
            <div class="discount-field">
              <label for="disc-pct-{i}">Discount %</label>
              <input
                type="number"
                id="disc-pct-{i}"
                value={discount.percent}
                min="1"
                max="99"
                step="0.5"
                oninput={(e) => handleDiscountPercentChange(i, e)}
              />
            </div>
            <button type="button" class="remove-btn" onclick={() => removeDiscount(i)} title="Remove discount">
              &times;
            </button>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  {#if preview.length > 0}
    <div class="preview-section">
      <label>Pricing Preview</label>
      <div class="preview-table">
        <div class="preview-header">
          <span>Duration</span>
          <span>Rate/Day</span>
          <span>Discount</span>
          <span>Total</span>
        </div>
        {#each preview as row}
          <div class="preview-row" class:has-discount={row.discountPct > 0}>
            <span>{row.totalDays} day{row.totalDays !== 1 ? 's' : ''}</span>
            <span>{formatPrice(row.pricePerDay)}</span>
            <span class:discount-active={row.discountPct > 0}>
              {row.discountPct > 0 ? `-${row.discountPct}%` : '—'}
            </span>
            <span class="preview-total">{formatPrice(row.totalPrice)}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>

<style>
  .pricing-editor {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .form-group label {
    font-weight: 500;
    font-size: 0.9rem;
    color: var(--text-color);
  }

  .form-group input {
    padding: 0.5rem;
    background: var(--primary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.9rem;
    max-width: 200px;
  }

  .form-group input:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .form-group small {
    color: var(--text-muted);
    font-size: 0.8rem;
  }

  .discounts-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .discounts-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .discounts-header label {
    font-weight: 500;
    font-size: 0.9rem;
    color: var(--text-color);
  }

  .add-btn {
    background: transparent;
    border: 1px solid var(--accent-color);
    color: var(--accent-color);
    padding: 0.3rem 0.6rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 500;
  }

  .add-btn:hover {
    background: var(--accent-color);
    color: white;
  }

  .empty-discounts {
    color: var(--text-muted);
    font-size: 0.85rem;
    margin: 0;
  }

  .discount-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .discount-row {
    display: flex;
    align-items: flex-end;
    gap: 0.5rem;
  }

  .discount-field {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .discount-field label {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .discount-field input {
    width: 80px;
    padding: 0.4rem;
    background: var(--primary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.85rem;
  }

  .discount-field input:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .remove-btn {
    background: transparent;
    border: 1px solid var(--error-color);
    color: var(--error-color);
    width: 28px;
    height: 28px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1.1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-bottom: 1px;
  }

  .remove-btn:hover {
    background: var(--error-color);
    color: white;
  }

  .preview-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .preview-section label {
    font-weight: 500;
    font-size: 0.9rem;
    color: var(--text-color);
  }

  .preview-table {
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .preview-header, .preview-row {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr;
    padding: 0.4rem 0.75rem;
    font-size: 0.85rem;
  }

  .preview-header {
    background: var(--hover-color);
    font-weight: 600;
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .preview-row {
    border-top: 1px solid var(--border-color);
  }

  .preview-row.has-discount {
    background: var(--success-bg);
  }

  .discount-active {
    color: var(--success-color);
    font-weight: 500;
  }

  .preview-total {
    font-weight: 600;
  }

  @media (max-width: 480px) {
    .discount-row {
      flex-wrap: wrap;
    }

    .preview-header, .preview-row {
      font-size: 0.75rem;
      padding: 0.3rem 0.5rem;
    }
  }
</style>
