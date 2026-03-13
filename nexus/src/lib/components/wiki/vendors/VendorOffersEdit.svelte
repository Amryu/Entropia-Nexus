<!--
  @component VendorOffersEdit
  Array editor for vendor item offers.
  Supports item search autocomplete for both offer items and price items.
  Each offer can have multiple prices (special costs) with nested editing.
  Uses SearchInput for item name search.
-->
<script>
  // @ts-nocheck
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';

  

  
  /**
   * @typedef {Object} Props
   * @property {Array} [offers]
   * @property {string} [fieldPath]
   */

  /** @type {Props} */
  let { offers = [], fieldPath = 'Offers' } = $props();

  // === Constructors ===
  function createOffer() {
    return {
      Item: { Name: '' },
      IsLimited: false,
      Value: null,
      Prices: [{ Item: { Name: '' }, Amount: null }]
    };
  }

  function createPrice() {
    return { Item: { Name: '' }, Amount: null };
  }

  // === Offer CRUD ===
  function addOffer() {
    updateField(fieldPath, [...offers, createOffer()]);
  }

  function removeOffer(index) {
    updateField(fieldPath, offers.filter((_, i) => i !== index));
  }

  function updateOfferField(index, field, value) {
    const newList = [...offers];
    const offer = newList[index];

    if (field === 'Item.Name') {
      if (!offer.Item) offer.Item = {};
      offer.Item.Name = value;
    } else {
      offer[field] = value;
    }

    updateField(fieldPath, newList);
  }

  // === Price CRUD (nested within offer) ===
  function addPrice(offerIndex) {
    const newList = [...offers];
    if (!newList[offerIndex].Prices) newList[offerIndex].Prices = [];
    newList[offerIndex].Prices = [...newList[offerIndex].Prices, createPrice()];
    updateField(fieldPath, newList);
  }

  function removePrice(offerIndex, priceIndex) {
    const newList = [...offers];
    newList[offerIndex].Prices = newList[offerIndex].Prices.filter((_, i) => i !== priceIndex);
    updateField(fieldPath, newList);
  }

  function updatePriceField(offerIndex, priceIndex, field, value) {
    const newList = [...offers];
    const price = newList[offerIndex].Prices[priceIndex];

    if (field === 'Item.Name') {
      if (!price.Item) price.Item = {};
      price.Item.Name = value;
    } else {
      price[field] = value;
    }

    updateField(fieldPath, newList);
  }
</script>

<div class="offers-edit">
  <div class="section-header">
    <h4 class="section-title">Offers ({offers?.length || 0})</h4>
  </div>

  <div class="offers-list">
    {#each offers as offer, index (index)}
      <div class="offer-item">
        <div class="offer-main">
          <div class="offer-fields">
            <div class="field item-field">
              <span class="field-label">Item Name</span>
              <SearchInput
                value={offer.Item?.Name || ''}
                placeholder="Search item..."
                apiEndpoint="/search/items"
                displayFn={(item) => item?.Name || ''}
                on:change={(e) => updateOfferField(index, 'Item.Name', e.detail.value)}
                on:select={(e) => updateOfferField(index, 'Item.Name', e.detail.data?.Name || e.detail.value)}
              />
            </div>

            <label class="field value-field">
              <span class="field-label">Value (PED)</span>
              <input
                type="number"
                min="0"
                step="0.0001"
                value={offer.Value ?? ''}
                oninput={(e) => updateOfferField(index, 'Value', e.target.value ? parseFloat(e.target.value) : null)}
                placeholder="0.00"
              />
            </label>

            <label class="field checkbox-field">
              <input
                type="checkbox"
                checked={offer.IsLimited || false}
                onchange={(e) => updateOfferField(index, 'IsLimited', e.target.checked)}
              />
              <span class="field-label">Limited</span>
            </label>
          </div>

          <button
            class="btn-icon danger"
            onclick={() => removeOffer(index)}
            title="Remove offer"
            type="button"
          >×</button>
        </div>

        {#if (offer.Prices && offer.Prices.length > 0) || true}
          <div class="prices-section">
            <span class="field-label prices-label">Special Costs</span>
            <div class="prices-list">
              {#each (offer.Prices || []) as price, priceIndex (priceIndex)}
                <div class="price-row">
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={price.Amount ?? ''}
                    oninput={(e) => updatePriceField(index, priceIndex, 'Amount', e.target.value ? parseInt(e.target.value) : null)}
                    placeholder="Amt"
                    class="price-amount"
                  />
                  <span class="price-separator">×</span>
                  <div class="price-item-search">
                    <SearchInput
                      value={price.Item?.Name || ''}
                      placeholder="Price item..."
                      apiEndpoint="/search/items"
                      displayFn={(item) => item?.Name || ''}
                      on:change={(e) => updatePriceField(index, priceIndex, 'Item.Name', e.detail.value)}
                      on:select={(e) => updatePriceField(index, priceIndex, 'Item.Name', e.detail.data?.Name || e.detail.value)}
                    />
                  </div>
                  <button
                    class="btn-icon danger btn-remove-price"
                    onclick={() => removePrice(index, priceIndex)}
                    title="Remove price"
                    type="button"
                  >×</button>
                </div>
              {/each}
              <button
                class="btn-add-price"
                onclick={() => addPrice(index)}
                type="button"
              >+ Price</button>
            </div>
          </div>
        {/if}
      </div>
    {/each}

    <button class="btn-add" onclick={addOffer} type="button">
      <span>+</span> Add Offer
    </button>
  </div>
</div>

<style>
  .offers-edit {
    width: 100%;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .section-title {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  .offers-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .offer-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 6px 8px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
  }

  .offer-main {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .offer-fields {
    display: flex;
    gap: 6px;
    flex: 1;
    flex-wrap: wrap;
    align-items: flex-end;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }

  .field.item-field {
    flex: 2;
    min-width: 140px;
    max-width: 220px;
  }

  .field.value-field {
    flex: 1;
    min-width: 80px;
    max-width: 110px;
  }

  .field-label {
    font-size: 12px;
    color: var(--text-muted, #999);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .field input[type="number"] {
    padding: 4px 6px;
    font-size: 12px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-color);
    width: 100%;
    box-sizing: border-box;
    height: 28px;
  }

  .field input[type="number"]:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .checkbox-field {
    flex-direction: row;
    align-items: center;
    gap: 4px;
    min-width: auto;
    flex: 0 0 auto;
    height: 28px;
    margin-top: auto;
  }

  .checkbox-field .field-label {
    margin-top: 0;
  }

  .checkbox-field input[type="checkbox"] {
    width: 14px;
    height: 14px;
    cursor: pointer;
    flex-shrink: 0;
  }

  /* Prices sub-section */
  .prices-section {
    padding-left: 10px;
    border-left: 2px solid var(--border-color, #555);
    margin-left: 4px;
  }

  .prices-label {
    font-weight: 500;
    margin-bottom: 2px;
    display: block;
  }

  .prices-list {
    display: flex;
    flex-direction: column;
    gap: 3px;
    margin-top: 3px;
  }

  .price-row {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .price-amount {
    width: 64px;
    min-width: 64px;
    padding: 4px 6px;
    font-size: 12px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-color);
    box-sizing: border-box;
    height: 28px;
  }

  .price-amount:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .price-separator {
    font-size: 11px;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .price-item-search {
    flex: 1;
    min-width: 120px;
    max-width: 200px;
  }

  .btn-remove-price {
    width: 20px;
    height: 20px;
    font-size: 11px;
  }

  .btn-add-price {
    display: inline-flex;
    align-items: center;
    padding: 3px 8px;
    font-size: 11px;
    line-height: 1;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    color: var(--text-muted, #999);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s;
    align-self: flex-start;
    margin-top: 2px;
  }

  .btn-add-price:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
    background-color: var(--hover-color);
  }

  /* Buttons */
  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    background: none;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .btn-icon:hover:not(:disabled) {
    background-color: var(--hover-color);
    color: var(--text-color);
    border-color: var(--text-color);
  }

  .btn-icon.danger:hover:not(:disabled) {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  .btn-add {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 8px 12px;
    font-size: 12px;
    line-height: 1;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    color: var(--text-muted, #999);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s;
    margin-top: 4px;
  }

  .btn-add:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
    background-color: var(--hover-color);
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .offer-main {
      flex-direction: column;
      align-items: stretch;
      gap: 6px;
    }

    .offer-fields {
      flex-direction: column;
      align-items: stretch;
    }

    .field,
    .field.item-field,
    .field.value-field {
      max-width: none;
      width: 100%;
    }

    .checkbox-field {
      align-self: flex-start;
    }

    .offer-main > .btn-icon {
      align-self: flex-end;
    }

    .price-item-search {
      max-width: none;
    }
  }
</style>
