<script>
  //@ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { page } from '$app/stores';
  import { getMaxTT, isAbsoluteMarkup, isItemTierable, isBlueprint, isLimited, formatMarkupValue, formatPedValue, isPet, isBlueprintNonL, getUnitTT, computeUnitPrice, getPetLevel } from '../../orderUtils';
  import { hasCondition } from '$lib/shopUtils';

  /** @type {boolean} */
  export let show = false;

  /** @type {object|null} The order being responded to */
  export let order = null;

  /** @type {'buy'|'sell'} What the user is doing (buy = responding to a sell order) */
  export let side = 'buy';

  /** @type {object|null} Item details for display */
  export let item = null;

  /** Whether to show the "Add to Trade List" button */
  export let showAddToList = false;

  const dispatch = createEventDispatcher();

  let quantity = 1;
  let submitting = false;
  let error = null;
  let minQty = 1;
  let maxQty = 1;
  let effectiveMinQty = 1;
  let currentOrderId = null;
  let initializedOrderId = null;
  let wasOpen = false;
  let qtyNumber = 1;

  /** Called by parent to signal that the async operation failed */
  export function setError(msg) {
    error = msg || 'Something went wrong';
    submitting = false;
  }

  $: minQty = Math.max(1, Math.floor(Number(order?.min_quantity ?? 1) || 1));
  $: maxQty = Math.max(1, Math.floor(Number(order?.quantity ?? 1) || 1));
  $: effectiveMinQty = Math.min(minQty, maxQty);
  $: currentOrderId = order?.id ?? order?.Id ?? null;
  $: if (show && order) {
    if (!wasOpen || initializedOrderId !== currentOrderId) {
      quantity = maxQty;
      error = null;
      submitting = false;
      initializedOrderId = currentOrderId;
    }
    wasOpen = true;
  }
  $: if (!show && wasOpen) {
    wasOpen = false;
    initializedOrderId = null;
  }

  $: isOwnOrder = (() => {
    const userId = $page?.data?.session?.user?.id;
    const sellerId = order?.user_id ?? order?.SellerId ?? order?.UserId ?? null;
    return userId && sellerId && String(userId) === String(sellerId);
  })();
  $: qtyNumber = Number(quantity);
  $: qtyValid = Number.isInteger(qtyNumber) && qtyNumber >= effectiveMinQty && qtyNumber <= maxQty;

  $: isCond = hasCondition(item);
  $: isAbsMu = isAbsoluteMarkup(item);
  $: isBpNonL = isBlueprintNonL(item);
  $: maxTT = getMaxTT(item);
  $: isPetItem = isPet(item) || isPet(order);
  $: petLevel = getPetLevel(order);

  $: markupDisplay = formatMarkupValue(order?.markup, isAbsMu);

  // Non-L BP TT value is QR/100, not MaxTT
  $: bpTTValue = isBpNonL ? (Number(order?.details?.QualityRating) || 0) / 100 : null;

  // Compute unit price (TT + MU per unit)
  $: unitPrice = (() => {
    if (order?.markup == null) return null;
    if (isBpNonL) return bpTTValue + order.markup;
    if (maxTT == null) return null;
    return isAbsMu ? maxTT + order.markup : maxTT * (order.markup / 100);
  })();

  // Compute total TT and total price for the selected quantity
  $: totalTT = isBpNonL ? bpTTValue * quantity : (maxTT != null ? maxTT * quantity : null);
  $: totalPrice = unitPrice != null ? unitPrice * quantity : null;

  // Item metadata for display
  $: tierable = isItemTierable(item);
  $: blueprint = isBlueprint(item);
  $: orderTier = order?.details?.Tier ?? order?.details?.tier ?? null;
  $: orderTiR = order?.details?.TierIncreaseRate ?? order?.details?.tir ?? null;
  $: orderQR = order?.details?.QualityRating ?? null;
  $: orderCurrentTT = order?.details?.CurrentTT ?? null;

  $: partnerLabel = side === 'buy' ? 'Seller' : 'Buyer';
  $: actionLabel = side === 'buy' ? 'Buy Now' : 'Sell Now';
  $: canConfirm = !submitting && !isOwnOrder && qtyValid;

  function getNormalizedQuantity() {
    const parsed = Math.floor(Number(quantity));
    if (!Number.isFinite(parsed)) return null;
    return Math.max(effectiveMinQty, Math.min(maxQty, parsed));
  }

  function normalizeQuantity() {
    const normalized = getNormalizedQuantity();
    quantity = normalized ?? effectiveMinQty;
  }

  function close() {
    dispatch('close');
  }

  async function confirm() {
    if (!canConfirm) return;
    const normalized = getNormalizedQuantity();
    if (normalized == null) return;
    quantity = normalized;
    submitting = true;
    error = null;

    try {
      dispatch('confirm', {
        order,
        quantity: normalized,
        side
      });
    } catch (err) {
      error = err.message || 'Failed to create trade request';
      submitting = false;
    }
  }

  function fmtPed(v) {
    return formatPedValue(v);
  }
</script>

{#if show && order}
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
          <span class="info-value">{order.details?.item_name || item?.Name || 'Unknown'}</span>
        </div>
        <div class="info-row">
          <span class="info-label">{partnerLabel}</span>
          <span class="info-value">{order.seller_name || 'Unknown'}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Planet</span>
          <span class="info-value">{order.planet || 'Any'}</span>
        </div>

        {#if tierable && (orderTier != null || orderTiR != null)}
          <div class="info-row">
            <span class="info-label">Tier</span>
            <span class="info-value">{orderTier ?? 'N/A'}</span>
          </div>
          <div class="info-row">
            <span class="info-label">TiR</span>
            <span class="info-value">{orderTiR ?? 'N/A'}</span>
          </div>
        {/if}

        {#if blueprint && orderQR != null}
          <div class="info-row">
            <span class="info-label">QR</span>
            <span class="info-value">{Number(orderQR).toFixed(2)}</span>
          </div>
        {/if}

        {#if isCond && !blueprint && orderCurrentTT != null}
          <div class="info-row">
            <span class="info-label">Current TT</span>
            <span class="info-value">{fmtPed(Number(orderCurrentTT))}</span>
          </div>
        {/if}

        {#if isPetItem && petLevel != null}
          <div class="info-row">
            <span class="info-label">Level</span>
            <span class="info-value">{petLevel}</span>
          </div>
        {/if}

        <div class="info-row">
          <span class="info-label">Markup</span>
          <span class="info-value markup">{markupDisplay}</span>
        </div>

        <div class="quantity-row">
          <label for="tradeQty">Quantity</label>
          <input
            id="tradeQty"
            type="number"
            step="1"
            min={effectiveMinQty}
            max={maxQty}
            bind:value={quantity}
            on:blur={normalizeQuantity}
          />
          <span class="qty-hint">
            {#if effectiveMinQty < maxQty}
              Owner minimum: {effectiveMinQty}. Available up to {maxQty}.
            {:else}
              Fixed quantity: {maxQty} (owner minimum equals available).
            {/if}
          </span>
        </div>

        {#if maxTT != null}
          <div class="price-summary">
            <div class="price-row">
              <span class="price-label">TT Value</span>
              <span class="price-value">{fmtPed(totalTT)}</span>
            </div>
            <div class="price-row">
              <span class="price-label">Markup</span>
              <span class="price-value">{isAbsMu ? fmtPed(order?.markup) : fmtPed(totalPrice - totalTT)}</span>
            </div>
            <div class="price-row total">
              <span class="price-label">Total Price</span>
              <span class="price-value highlight">{fmtPed(totalPrice)}</span>
            </div>
          </div>
        {/if}

        {#if isOwnOrder}
          <div class="own-order-notice">This is your own order.</div>
        {:else if !qtyValid}
          <div class="error-message">Quantity must be between {effectiveMinQty} and {maxQty}.</div>
        {/if}

        {#if error}
          <div class="error-message">{error}</div>
        {/if}
      </div>

      <div class="dialog-actions">
        <button class="btn btn-secondary" on:click={close}>Cancel</button>
        {#if isOwnOrder}
          <button
            class="btn btn-edit"
            on:click={() => dispatch('editOwn', { order })}
          >
            Edit Order
          </button>
        {:else}
          {#if showAddToList}
            <button
              class="btn btn-list"
              on:click={() => dispatch('addToList', { order, quantity: getNormalizedQuantity() ?? quantity, side })}
              disabled={submitting || !qtyValid}
            >
              Add to Trade List
            </button>
          {/if}
          <button
            class="btn {side === 'buy' ? 'btn-buy' : 'btn-sell'}"
            on:click={confirm}
            disabled={!canConfirm}
          >
            {submitting ? 'Sending...' : actionLabel}
          </button>
        {/if}
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
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: 8px;
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
  .info-value.markup {
    font-weight: 600;
    color: var(--accent-color);
  }
  .own-order-notice {
    color: var(--text-muted);
    font-size: 12px;
    padding: 6px 8px;
    background: var(--hover-color);
    border-radius: 4px;
    text-align: center;
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
  .btn-list {
    background: transparent;
    color: var(--accent-color);
    border-color: var(--accent-color);
  }
  .btn-list:hover:not(:disabled) {
    background: rgba(59, 130, 246, 0.1);
  }
  .btn-edit {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }
  .btn-edit:hover:not(:disabled) { opacity: 0.9; }
</style>
