<script>
  //@ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { page } from '$app/stores';
  import { getMaxTT, isAbsoluteMarkup } from '../../orderUtils';
  import { hasCondition } from '$lib/shopUtils';

  /** @type {boolean} */
  export let show = false;

  /** @type {object|null} The offer being responded to */
  export let offer = null;

  /** @type {'buy'|'sell'} What the user is doing (buy = responding to a sell offer) */
  export let side = 'buy';

  /** @type {object|null} Item details for display */
  export let item = null;

  const dispatch = createEventDispatcher();

  let quantity = 1;
  let submitting = false;
  let error = null;

  $: if (show && offer) {
    quantity = offer.quantity || 1;
    error = null;
    submitting = false;
  }

  $: minQty = offer?.min_quantity || 1;
  $: maxQty = offer?.quantity || 1;
  $: isOwnOrder = (() => {
    const userId = $page?.data?.session?.user?.id;
    const sellerId = offer?.user_id ?? offer?.SellerId ?? offer?.UserId ?? null;
    return userId && sellerId && String(userId) === String(sellerId);
  })();
  $: qtyValid = quantity >= minQty && quantity <= maxQty;

  $: isCond = hasCondition(item);
  $: maxTT = getMaxTT(item);

  $: markupDisplay = (() => {
    const mu = offer?.markup;
    if (mu == null) return 'N/A';
    return isCond ? `+${Number(mu).toFixed(2)} PED` : `${Number(mu).toFixed(1)}%`;
  })();

  // Compute unit price (TT + MU per unit)
  $: unitPrice = (() => {
    if (maxTT == null || offer?.markup == null) return null;
    return isCond ? maxTT + offer.markup : maxTT * (offer.markup / 100);
  })();

  // Compute total TT and total price for the selected quantity
  $: totalTT = maxTT != null ? maxTT * quantity : null;
  $: totalPrice = unitPrice != null ? unitPrice * quantity : null;

  $: partnerLabel = side === 'buy' ? 'Seller' : 'Buyer';
  $: actionLabel = side === 'buy' ? 'Buy Now' : 'Sell Now';
  $: canConfirm = !submitting && !isOwnOrder && qtyValid;

  function close() {
    dispatch('close');
  }

  async function confirm() {
    if (!canConfirm) return;
    submitting = true;
    error = null;

    try {
      dispatch('confirm', {
        offer,
        quantity,
        side
      });
    } catch (err) {
      error = err.message || 'Failed to create trade request';
      submitting = false;
    }
  }

  function fmt(v) {
    return typeof v === 'number' && isFinite(v) ? v.toFixed(2) : 'N/A';
  }
</script>

{#if show && offer}
  <div
    class="modal-overlay"
    role="button"
    tabindex="-1"
    on:click|self={close}
    on:keydown={(e) => e.key === 'Escape' && close()}
  >
    <div class="quick-trade-dialog">
      <div class="dialog-header">
        <h3>{side === 'buy' ? 'Buy Item' : 'Sell Item'}</h3>
        <button class="close-btn" on:click={close}>&times;</button>
      </div>

      <div class="dialog-body">
        <div class="info-row">
          <span class="info-label">Item</span>
          <span class="info-value">{offer.details?.item_name || item?.Name || 'Unknown'}</span>
        </div>
        <div class="info-row">
          <span class="info-label">{partnerLabel}</span>
          <span class="info-value">{offer.seller_name || 'Unknown'}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Planet</span>
          <span class="info-value">{offer.planet || 'Any'}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Markup</span>
          <span class="info-value">{markupDisplay}</span>
        </div>

        <div class="quantity-row">
          <label for="tradeQty">Quantity</label>
          <input
            id="tradeQty"
            type="number"
            min={minQty}
            max={maxQty}
            bind:value={quantity}
          />
          <span class="qty-hint">
            {#if minQty < maxQty}Min: {minQty}, Max: {maxQty}{:else}Fixed: {maxQty}{/if}
          </span>
        </div>

        {#if maxTT != null}
          <div class="price-summary">
            <div class="price-row">
              <span class="price-label">TT Value</span>
              <span class="price-value">{fmt(totalTT)} PED</span>
            </div>
            <div class="price-row total">
              <span class="price-label">Total (TT+MU)</span>
              <span class="price-value highlight">{fmt(totalPrice)} PED</span>
            </div>
          </div>
        {/if}

        {#if isOwnOrder}
          <div class="error-message">This is your own order.</div>
        {:else if !qtyValid}
          <div class="error-message">Quantity must be between {minQty} and {maxQty}.</div>
        {/if}

        {#if error}
          <div class="error-message">{error}</div>
        {/if}
      </div>

      <div class="dialog-actions">
        <button class="btn btn-secondary" on:click={close}>Cancel</button>
        <button
          class="btn {side === 'buy' ? 'btn-buy' : 'btn-sell'}"
          on:click={confirm}
          disabled={!canConfirm}
        >
          {submitting ? 'Sending...' : actionLabel}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .quick-trade-dialog {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 380px;
    max-width: 95vw;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  }
  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
  }
  .dialog-header h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: var(--text-color);
  }
  .close-btn {
    background: none;
    border: none;
    font-size: 20px;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }
  .close-btn:hover { color: var(--text-color); }
  .dialog-body {
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
  }
  .info-label {
    color: var(--text-muted);
    font-weight: 500;
  }
  .info-value {
    color: var(--text-color);
    font-weight: 500;
  }
  .quantity-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
  }
  .quantity-row label {
    color: var(--text-muted);
    font-weight: 500;
    min-width: 60px;
  }
  .quantity-row input {
    width: 80px;
    padding: 4px 8px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-color);
    color: var(--text-color);
    font-size: 13px;
  }
  .qty-hint {
    color: var(--text-muted);
    font-size: 11px;
  }
  .price-summary {
    background: var(--hover-color);
    border-radius: 6px;
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .price-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
  }
  .price-label {
    color: var(--text-muted);
  }
  .price-value {
    color: var(--text-color);
    font-weight: 500;
  }
  .price-row.total {
    font-size: 13px;
    padding-top: 4px;
    border-top: 1px solid var(--border-color);
  }
  .price-value.highlight {
    color: var(--accent-color);
    font-weight: 600;
  }
  .error-message {
    color: var(--error-color, #ef4444);
    font-size: 12px;
    padding: 6px 8px;
    background: var(--error-bg, rgba(239, 68, 68, 0.1));
    border-radius: 4px;
  }
  .dialog-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    padding: 12px 16px;
    border-top: 1px solid var(--border-color);
  }
  .btn {
    padding: 6px 16px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .btn-secondary {
    background: var(--bg-color);
    color: var(--text-color);
  }
  .btn-secondary:hover:not(:disabled) {
    background: var(--hover-color);
  }
  .btn-buy {
    background: var(--success-color, #16a34a);
    color: white;
    border-color: var(--success-color, #16a34a);
  }
  .btn-buy:hover:not(:disabled) { opacity: 0.9; }
  .btn-sell {
    background: var(--error-color, #ef4444);
    color: white;
    border-color: var(--error-color, #ef4444);
  }
  .btn-sell:hover:not(:disabled) { opacity: 0.9; }
</style>
