<script>
  //@ts-nocheck
  import { page } from '$app/stores';
  import { getMaxTT, isAbsoluteMarkup, isItemTierable, isBlueprint, isLimited, formatMarkupValue, formatPedValue, isPet, isBlueprintNonL, getUnitTT, computeUnitPrice, getPetLevel } from '../../orderUtils';
  import { hasCondition } from '$lib/shopUtils';
  import { encodeURIComponentSafe } from '$lib/util.js';
  import { PLATE_SET_SIZE } from '$lib/common/itemTypes.js';








  /**
   * @typedef {Object} Props
   * @property {boolean} [show]
   * @property {object|null} [order]
   * @property {'buy'|'sell'} [side]
   * @property {object|null} [item]
   * @property {boolean} [showAddToList] - Whether to show the "Add to Trade List" button
   * @property {() => void} [onclose]
   * @property {(data: any) => void} [onconfirm]
   * @property {(data: any) => void} [oneditOwn]
   * @property {(data: any) => void} [onaddToList]
   */

  /** @type {Props} */
  let {
    show = false,
    order = null,
    side = 'buy',
    item = null,
    showAddToList = false,
    onclose,
    onconfirm,
    oneditOwn,
    onaddToList,
  } = $props();

  let quantity = $state(1);
  let proposedMarkup = $state('');
  let submitting = $state(false);
  let error = $state(null);
  let minQty = $state(1);
  let maxQty = $state(1);
  let effectiveMinQty = $state(1);
  let currentOrderId = $state(null);
  let initializedOrderId = $state(null);
  let wasOpen = $state(false);
  let qtyNumber = $state(1);

  /** Called by parent to signal that the async operation failed */
  export function setError(msg) {
    error = msg || 'Something went wrong';
    submitting = false;
  }

  $effect(() => {
    minQty = Math.max(1, Math.floor(Number(order?.min_quantity ?? 1) || 1));
  });
  $effect(() => {
    maxQty = Math.max(1, Math.floor(Number(order?.quantity ?? 1) || 1));
  });
  $effect(() => {
    effectiveMinQty = Math.min(minQty, maxQty);
  });
  $effect(() => {
    currentOrderId = order?.id ?? order?.Id ?? null;
  });
  $effect(() => {
    if (show && order) {
      if (!wasOpen || initializedOrderId !== currentOrderId) {
        quantity = maxQty;
        proposedMarkup = '';
        error = null;
        submitting = false;
        initializedOrderId = currentOrderId;
      }
      wasOpen = true;
    }
  });
  $effect(() => {
    if (!show && wasOpen) {
      wasOpen = false;
      initializedOrderId = null;
    }
  });

  let isOwnOrder = $derived((() => {
    const userId = $page?.data?.session?.user?.id;
    const sellerId = order?.user_id ?? order?.SellerId ?? order?.UserId ?? null;
    return userId && sellerId && String(userId) === String(sellerId);
  })());
  $effect(() => {
    qtyNumber = Number(quantity);
  });
  let qtyValid = $derived(Number.isInteger(qtyNumber) && qtyNumber >= effectiveMinQty && qtyNumber <= maxQty);

  let isCond = $derived(hasCondition(item));
  let isAbsMu = $derived(isAbsoluteMarkup(item));
  let isBpNonL = $derived(isBlueprintNonL(item));
  let maxTT = $derived(getMaxTT(item));
  let isPetItem = $derived(isPet(item) || isPet(order));
  let petLevel = $derived(getPetLevel(order));

  let markupDisplay = $derived(formatMarkupValue(order?.markup, isAbsMu));

  // Non-L BP TT value is QR/100, not MaxTT
  let bpTTValue = $derived(isBpNonL ? (Number(order?.details?.QualityRating) || 0) / 100 : null);

  let itemType = $derived(item?.Properties?.Type ?? item?.Type ?? item?.t ?? null);
  let isSet = $derived(itemType === 'ArmorPlating' && Number(order?.quantity) === PLATE_SET_SIZE);

  // Compute unit price (TT + MU per unit; for sets, includes all plates)
  let unitPrice = $derived((() => {
    if (order?.markup == null) return null;
    const mu = Number(order.markup);
    if (isBpNonL) return bpTTValue + mu;
    if (maxTT == null) return null;
    // Armor plate sets: TT value covers all 7 plates
    const tt = isSet ? maxTT * PLATE_SET_SIZE : maxTT;
    return isAbsMu ? tt + mu : tt * (mu / 100);
  })());

  // Compute total TT and total price for the selected quantity
  let totalTT = $derived(isBpNonL ? bpTTValue * quantity : (maxTT != null ? maxTT * quantity : null));
  // For sets, unitPrice already covers the full set; don't multiply by qty again
  let totalPrice = $derived(unitPrice != null ? (isSet ? unitPrice : unitPrice * quantity) : null);

  // Item metadata for display
  let tierable = $derived(isItemTierable(item));
  let blueprint = $derived(isBlueprint(item));
  let orderTier = $derived(order?.details?.Tier ?? order?.details?.tier ?? null);
  let orderTiR = $derived(order?.details?.TierIncreaseRate ?? order?.details?.tir ?? null);
  let orderQR = $derived(order?.details?.QualityRating ?? null);
  let orderCurrentTT = $derived(order?.details?.CurrentTT ?? null);

  let isNegotiable = $derived(order?.markup === null);
  let proposedMarkupNum = $derived(Number(proposedMarkup));
  let proposedMarkupValid = $derived(!isNegotiable || (Number.isFinite(proposedMarkupNum) && proposedMarkupNum >= 0));

  let partnerLabel = $derived(side === 'buy' ? 'Seller' : 'Buyer');
  let actionLabel = $derived(isNegotiable ? 'Propose Trade' : (side === 'buy' ? 'Buy Now' : 'Sell Now'));
  let canConfirm = $derived(!submitting && !isOwnOrder && qtyValid && proposedMarkupValid);

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
    onclose?.();
  }

  async function confirm() {
    if (!canConfirm) return;
    const normalized = getNormalizedQuantity();
    if (normalized == null) return;
    quantity = normalized;
    submitting = true;
    error = null;

    try {
      onconfirm?.({
        order,
        quantity: normalized,
        side,
        proposedMarkup: isNegotiable ? proposedMarkupNum : undefined,
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
    onclick={(e) => { if (e.target === e.currentTarget) close(); }}
    onkeydown={(e) => e.key === 'Escape' && close()}
  >
    <div class="quick-trade-dialog">
      <div class="dialog-header">
        <h3>{side === 'buy' ? 'Buy Item' : 'Sell Item'}</h3>
        <button class="close-btn" onclick={close}>&times;</button>
      </div>

      <div class="dialog-body">
        <div class="info-row">
          <span class="info-label">Item</span>
          <span class="info-value">{order.details?.item_name || item?.Name || 'Unknown'}</span>
        </div>
        <div class="info-row">
          <span class="info-label">{partnerLabel}</span>
          <span class="info-value">
            {#if order.seller_name}
              <a
                class="partner-link"
                href="/market/exchange/orders/{encodeURIComponentSafe(order.seller_name)}"
                target="_blank"
                rel="noopener"
              >{order.seller_name}</a>
            {:else}
              Unknown
            {/if}
          </span>
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

        {#if isNegotiable}
          <div class="info-row">
            <span class="info-label">Markup</span>
            <span class="info-value negotiable-text">Negotiable</span>
          </div>
          <div class="info-row">
            <label class="info-label" for="proposedMarkup">Propose {isAbsMu ? '(+PED)' : '(%)'}</label>
            <span class="qty-field">
              <input
                id="proposedMarkup"
                type="number"
                step="0.01"
                min="0"
                bind:value={proposedMarkup}
                placeholder={isAbsMu ? '+0.00' : '100.00'}
              />
              <span class="qty-hint">Your proposed price for this item</span>
            </span>
          </div>
        {:else}
          <div class="info-row">
            <span class="info-label">Markup</span>
            <span class="info-value markup">{markupDisplay}</span>
          </div>
        {/if}

        <div class="info-row">
          <label class="info-label" for="tradeQty">Quantity</label>
          <span class="qty-field">
            <input
              id="tradeQty"
              type="number"
              step="1"
              min={effectiveMinQty}
              max={maxQty}
              bind:value={quantity}
              onblur={normalizeQuantity}
            />
            <span class="qty-hint">
              {#if effectiveMinQty < maxQty}
                min {effectiveMinQty}, max {maxQty}
              {:else}
                fixed: {maxQty}
              {/if}
            </span>
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
        <button class="btn btn-secondary" onclick={close}>Cancel</button>
        {#if isOwnOrder}
          <button
            class="btn btn-edit"
            onclick={() => oneditOwn?.({ order })}
          >
            Edit Order
          </button>
        {:else}
          {#if showAddToList}
            <button
              class="btn btn-list"
              onclick={() => onaddToList?.({ order, quantity: getNormalizedQuantity() ?? quantity, side })}
              disabled={submitting || !qtyValid}
            >
              Add to Trade List
            </button>
          {/if}
          <button
            class="btn {side === 'buy' ? 'btn-buy' : 'btn-sell'}"
            onclick={confirm}
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
  .qty-field {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .qty-field input {
    width: 70px;
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
  .partner-link {
    color: var(--accent-color);
    text-decoration: none;
  }
  .partner-link:hover {
    text-decoration: underline;
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

  .info-value.negotiable-text {
    font-style: italic;
    color: var(--text-muted);
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
