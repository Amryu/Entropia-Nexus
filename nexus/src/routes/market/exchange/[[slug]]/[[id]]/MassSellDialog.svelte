<script>
  //@ts-nocheck
  import { isItemStackable, isPercentMarkup, isItemTierable, isBlueprint, isLimited, itemHasCondition, itemTypeBadge } from '../../orderUtils';
  import { PLANETS, DEFAULT_PARTIAL_RATIO, MAX_SELL_ORDERS, MAX_ORDERS_PER_ITEM } from '../../exchangeConstants.js';
  import { myOrders, upsertOrder } from '../../exchangeStore.js';
  import { env } from '$env/dynamic/public';
  import TurnstileWidget from '$lib/components/TurnstileWidget.svelte';
  import { addToast } from '$lib/stores/toasts.js';

  let turnstileToken = $state(null);
  let resetTurnstile = $state(false);

  /**
   * @typedef {Object} Props
   * @property {boolean} [show]
   * @property {any} [items] - Array of { invItem, count }
   * @property {any} [allItems] - Slim items for type lookup
   * @property {number} [sellOrderCount] - Current number of active sell orders
   * @property {() => void} [onclose]
   * @property {() => void} [oncomplete]
   */

  /** @type {Props} */
  let {
    show = false,
    items = [],
    allItems = [],
    sellOrderCount = 0,
    onclose,
    oncomplete,
  } = $props();

  let orderRows = $state([]);
  let globalPlanet = $state('Calypso');
  let submitting = $state(false);
  let progress = $state(0);
  let totalOrders = $state(0);
  let progressError = $state(null);

  // Unique key counter for expanded rows
  let rowKeyCounter = 0;


  function buildOrderRows() {
    // Preserve existing rows if re-opening (cancel preserves state)
    if (orderRows.length > 0 && !submitting) {
      const existingIds = new Set(orderRows.map(r => r.invItem.id));
      const newIds = new Set(items.map(i => i.invItem.id));
      if (existingIds.size === newIds.size && [...existingIds].every(id => newIds.has(id))) {
        return; // Same items, keep current state
      }
    }

    rowKeyCounter = 0;
    const rows = [];

    // Build lookup of existing active SELL orders by item_id
    const existingOrdersByItem = new Map();
    for (const order of ($myOrders || [])) {
      if (order.type !== 'SELL' || order.state === 'closed') continue;
      if (!existingOrdersByItem.has(order.item_id)) existingOrdersByItem.set(order.item_id, []);
      existingOrdersByItem.get(order.item_id).push(order);
    }
    // Track how many new rows have been generated per item (for non-stackable limit tracking)
    const newRowCountByItem = new Map();

    for (const { invItem, count } of items) {
      const slim = (allItems || []).find(si => si?.i === invItem.item_id);
      const stackable = isItemStackable(slim);
      const pctMarkup = isPercentMarkup(slim);
      const tierable = isItemTierable(slim);
      const blueprint = isBlueprint(slim);
      const hasCond = itemHasCondition(slim) && !blueprint;
      const limited = isLimited(slim);

      // Default markup from median price, or fallback
      const defaultMarkup = pctMarkup
        ? (slim?.m != null ? Number(slim.m) : 100)
        : (slim?.m != null ? Number(slim.m) : 0);

      // Parse inventory details for pre-fill
      const details = typeof invItem.details === 'string'
        ? (() => { try { return JSON.parse(invItem.details); } catch { return {}; } })()
        : (invItem.details || {});

      // For non-fungible items with count > 1, expand into individual rows
      const rowCount = stackable ? 1 : count;
      // Per-item TT for non-fungible stacks: divide combined TT by stack quantity
      const perItemTT = (!stackable && invItem.value != null && invItem.quantity > 0)
        ? Math.round(Number(invItem.value) / invItem.quantity * 100) / 100
        : null;

      const existingOrders = existingOrdersByItem.get(invItem.item_id) || [];
      const existingCount = existingOrders.length;

      for (let c = 0; c < rowCount; c++) {
        const qty = stackable ? (invItem.quantity || 1) : 1;

        // Determine if this row should edit an existing order or is blocked
        let isEdit = false;
        let existingOrderId = null;
        let blocked = false;
        let blockError = null;

        if (stackable && existingCount > 0) {
          // Stackable: limit 1 per item, edit the existing order
          isEdit = true;
          existingOrderId = existingOrders[0].id;
        } else if (!stackable) {
          // Non-stackable: check if per-item limit is reached
          const newForItem = newRowCountByItem.get(invItem.item_id) || 0;
          if (existingCount + newForItem >= MAX_ORDERS_PER_ITEM) {
            blocked = true;
            blockError = `Maximum ${MAX_ORDERS_PER_ITEM} sell orders for this item reached`;
          } else {
            newRowCountByItem.set(invItem.item_id, newForItem + 1);
          }
        }

        rows.push({
          key: `${invItem.id}_${rowKeyCounter++}`,
          invItem,
          itemName: invItem.item_name || '',
          itemId: invItem.item_id,
          itemType: slim?.t || null,
          stackable,
          pctMarkup,
          tierable,
          blueprint,
          hasCond,
          limited,
          // For edits, use existing order's markup; for new, use default
          markup: isEdit ? existingOrders[0].markup : defaultMarkup,
          quantity: qty,
          allowPartial: stackable && qty > 1,
          minQuantity: stackable ? Math.max(1, Math.floor(qty * DEFAULT_PARTIAL_RATIO)) : null,
          currentTT: stackable
            ? (invItem.value != null ? Number(invItem.value) : null)
            : perItemTT,
          maxTT: slim?.v ?? null,
          tier: details.Tier != null ? Number(details.Tier) : (tierable ? 0 : null),
          tir: details.TierIncreaseRate != null ? Number(details.TierIncreaseRate) : (tierable ? 1 : null),
          qr: details.QualityRating != null ? Number(details.QualityRating) : (blueprint && !limited ? 1 : null),
          isEdit,
          existingOrderId,
          blocked,
          error: blockError,
          status: blocked ? 'blocked' : 'pending',
        });
      }
    }

    orderRows = rows;
    progress = 0;
    totalOrders = 0;
    progressError = null;
    submitting = false;
  }

  function removeRow(index) {
    orderRows = orderRows.filter((_, i) => i !== index);
    if (orderRows.length === 0) close();
  }

  // --- Input clamping (on blur) ---
  function clampMarkup(row) {
    if (row.markup == null || row.markup === '') { row.markup = row.pctMarkup ? 100 : 0; return; }
    row.markup = Math.max(row.pctMarkup ? 100 : 0, Number(row.markup) || 0);
  }
  function clampTT(row) {
    if (row.currentTT == null || row.currentTT === '') return;
    let v = Math.max(0, Number(row.currentTT) || 0);
    if (row.maxTT != null) v = Math.min(v, row.maxTT);
    row.currentTT = Math.round(v * 100) / 100;
  }
  function clampTier(row) {
    if (row.tier == null || row.tier === '') return;
    row.tier = Math.max(0, Math.min(10, Math.round(Number(row.tier) || 0)));
  }
  function clampTiR(row) {
    if (row.tir == null || row.tir === '') return;
    const max = row.limited ? 4000 : 200;
    row.tir = Math.max(0, Math.min(max, Math.round(Number(row.tir) || 0)));
  }
  function clampQR(row) {
    if (row.qr == null || row.qr === '') return;
    row.qr = Math.max(1, Math.min(100, Math.round(Number(row.qr) || 0)));
  }
  function clampQty(row) {
    if (row.quantity == null) return;
    row.quantity = Math.max(1, Math.round(Number(row.quantity) || 1));
    if (row.allowPartial && row.minQuantity > row.quantity) row.minQuantity = row.quantity;
  }
  function clampMinQty(row) {
    if (row.minQuantity == null) return;
    row.minQuantity = Math.max(1, Math.min(row.quantity || 1, Math.round(Number(row.minQuantity) || 1)));
  }

  function validateRow(row) {
    if (row.pctMarkup) {
      if (row.markup == null || !isFinite(row.markup) || row.markup < 100) {
        return 'Markup must be at least 100%';
      }
    } else {
      if (row.markup == null || !isFinite(row.markup) || row.markup < 0) {
        return 'Markup must be at least +0';
      }
    }
    if (row.stackable && (!row.quantity || row.quantity < 1)) {
      return 'Quantity must be at least 1';
    }
    if (row.stackable && row.allowPartial && row.minQuantity != null) {
      if (row.minQuantity < 1) return 'Min quantity must be at least 1';
      if (row.minQuantity > row.quantity) return 'Min quantity cannot exceed quantity';
    }
    if (row.hasCond && row.currentTT != null) {
      if (row.currentTT < 0) return 'Current TT cannot be negative';
      if (row.maxTT != null && row.currentTT > row.maxTT) return 'Current TT exceeds Max TT';
    }
    if (row.tierable) {
      if (row.tier != null && (row.tier < 0 || row.tier > 10)) return 'Tier must be 0-10';
      const maxTir = row.limited ? 4000 : 200;
      if (row.tir != null && (row.tir < 0 || row.tir > maxTir)) return `TiR must be 0-${maxTir}`;
    }
    if (row.blueprint && !row.limited && row.qr != null) {
      if (row.qr < 1 || row.qr > 100) return 'QR must be 1-100';
    }
    return null;
  }


  function validateAll() {
    let valid = true;
    orderRows = orderRows.map(row => {
      if (row.blocked) return row; // Skip validation for blocked rows
      const err = validateRow(row);
      if (err) valid = false;
      return { ...row, error: err };
    });
    return valid;
  }

  function buildPayload(row) {
    const details = { item_name: row.itemName };
    if (row.tierable) {
      if (row.tier != null) details.Tier = Math.round(row.tier);
      if (row.tir != null) details.TierIncreaseRate = Math.round(row.tir);
    }
    if (row.blueprint && !row.limited && row.qr != null) {
      details.QualityRating = Math.round(row.qr);
    }
    if (row.hasCond && row.currentTT != null) {
      details.CurrentTT = Number(row.currentTT);
    }
    const payload = {
      type: 'SELL',
      item_id: row.itemId,
      quantity: row.stackable ? (row.quantity || 1) : 1,
      markup: Number(row.markup) || 0,
      planet: globalPlanet,
      min_quantity: (row.stackable && row.allowPartial && row.minQuantity) ? row.minQuantity : null,
      details,
    };
    if (row.isEdit && row.existingOrderId) {
      payload.order_id = row.existingOrderId;
    }
    return payload;
  }

  async function submit() {
    if (submitting) return;
    if (!validateAll()) return;

    // Require Turnstile verification
    if (env.PUBLIC_TURNSTILE_SITE_KEY && !turnstileToken) {
      addToast('Please complete the captcha verification', { type: 'warning' });
      return;
    }

    submitting = true;
    progressError = null;

    // Only submit non-blocked rows
    const rowsToSubmit = orderRows.filter(r => !r.blocked && r.status !== 'done');
    totalOrders = rowsToSubmit.length;
    progress = 0;

    // Mark submittable rows as submitting
    orderRows = orderRows.map(r => r.blocked || r.status === 'done' ? r : { ...r, status: 'submitting', error: null });

    const payloads = rowsToSubmit.map(row => buildPayload(row));

    try {
      const res = await fetch('/api/market/exchange/orders/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          orders: payloads,
          turnstile_token: turnstileToken,
        }),
      });

      // Reset Turnstile for potential retry
      resetTurnstile = true;
      turnstileToken = null;

      const data = await res.json();

      if (!res.ok && !data.results) {
        // Batch-level error (auth, rate limit, turnstile, etc.)
        orderRows = orderRows.map(r => r.blocked ? r : { ...r, status: 'error', error: data.error || 'Batch request failed' });
        progressError = data.error || 'Batch request failed';
        submitting = false;
        return;
      }

      // Process per-order results — map back to submittable rows
      const results = data.results || [];
      let failedCount = 0;
      let resultIdx = 0;

      for (let i = 0; i < orderRows.length; i++) {
        if (orderRows[i].blocked || orderRows[i].status === 'done') continue;
        const result = results[resultIdx++];
        if (result?.success) {
          orderRows[i] = { ...orderRows[i], status: 'done', error: null };
          if (result.order) upsertOrder(result.order);
          progress++;
        } else {
          orderRows[i] = { ...orderRows[i], status: 'error', error: result?.error || 'Unknown error' };
          failedCount++;
        }
      }

      if (failedCount > 0) {
        progressError = `${failedCount} order${failedCount > 1 ? 's' : ''} failed. Review errors and retry.`;
        submitting = false;
      } else {
        submitting = false;
        oncomplete?.();
      }
    } catch (err) {
      orderRows = orderRows.map(r => (r.blocked || r.status === 'done') ? r : { ...r, status: 'error', error: 'Network error' });
      progressError = `Network error: ${err.message || 'Failed to reach server'}`;
      submitting = false;
    }
  }

  function retryFromError() {
    orderRows = orderRows.filter(r => r.status !== 'done' && !r.blocked);
    orderRows = orderRows.map(r => r.status === 'error' ? { ...r, status: 'pending', error: null } : r);
    progressError = null;
    progress = 0;
    totalOrders = orderRows.length;
    // Reset Turnstile for fresh token
    resetTurnstile = true;
    turnstileToken = null;
  }

  function close() {
    if (submitting) return;
    onclose?.();
  }
  // Rebuild order rows when items change and dialog is shown
  $effect(() => {
    if (show && items.length > 0) {
      buildOrderRows();
    }
  });
  // Submittable rows: not blocked, not already done
  let submittableRows = $derived(orderRows.filter(r => !r.blocked && r.status !== 'done'));
  let newOrderCount = $derived(orderRows.filter(r => !r.isEdit && !r.blocked && r.status !== 'done').length);
  let editOrderCount = $derived(orderRows.filter(r => r.isEdit && !r.blocked && r.status !== 'done').length);
</script>

{#if show}
  <div class="modal-overlay" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) close(); }}>
    <div class="modal">
      <div class="modal-header">
        <h3>Mass Sell Orders</h3>
        <button class="close-btn" onclick={close} disabled={submitting}>&times;</button>
      </div>

      <div class="global-settings">
        <label for="massSellPlanet">Planet</label>
        <select id="massSellPlanet" bind:value={globalPlanet} disabled={submitting} class="field-select">
          {#each PLANETS as p}
            <option>{p}</option>
          {/each}
        </select>
      </div>

      <div class="batch-info">
        {sellOrderCount + newOrderCount} / {MAX_SELL_ORDERS} sell orders after this batch{#if editOrderCount > 0} ({editOrderCount} edit{editOrderCount !== 1 ? 's' : ''}){/if}
      </div>

      <div class="order-rows-container">
        {#each orderRows as row, i (row.key)}
          <div class="order-row" class:error={row.error && !row.blocked} class:done={row.status === 'done'} class:submitting={row.status === 'submitting'} class:blocked={row.blocked}>
            <div class="row-header">
              <span class="row-name" title={row.itemName}>
                {row.itemName}{@html itemTypeBadge(row.itemType)}
              </span>
              {#if row.isEdit}
                <span class="edit-badge">Edit</span>
              {/if}
              {#if row.blocked}
                <span class="blocked-badge">Limit</span>
              {/if}
              <span class="row-status">
                {#if row.status === 'done'}
                  <span class="status-done">&#10003;</span>
                {:else if row.status === 'submitting'}
                  <span class="status-submitting">...</span>
                {:else if row.error && !row.blocked}
                  <span class="status-error">!</span>
                {/if}
              </span>
              {#if !submitting && !row.blocked}
                <button class="row-remove" onclick={() => removeRow(i)} title="Remove">&times;</button>
              {/if}
            </div>
            {#if !row.blocked}
            <div class="row-fields">
              <div class="field">
                <label for="mass-markup-{row.key}">Markup{row.pctMarkup ? ' (%)' : ' (+PED)'}</label>
                <input
                  id="mass-markup-{row.key}"
                  type="number"
                  min={row.pctMarkup ? 100 : 0}
                  step={row.pctMarkup ? 1 : 0.01}
                  bind:value={row.markup}
                  disabled={submitting || row.status === 'done'}
                  class="field-input"
                  class:field-error={row.error && row.error.includes('Markup')}
                  onchange={() => clampMarkup(row)}
                />
              </div>
              {#if row.stackable}
                <div class="field">
                  <label for="mass-qty-{row.key}">Qty</label>
                  <input
                    id="mass-qty-{row.key}"
                    type="number"
                    min="1"
                    bind:value={row.quantity}
                    disabled={submitting || row.status === 'done'}
                    class="field-input field-sm"
                    class:field-error={row.error && row.error.includes('Quantity')}
                    onchange={() => clampQty(row)}
                  />
                </div>
                <div class="field field-partial">
                  <label class="partial-label">
                    <input
                      type="checkbox"
                      bind:checked={row.allowPartial}
                      disabled={submitting || row.status === 'done'}
                      onchange={() => {
                        if (row.allowPartial) {
                          row.minQuantity = Math.max(1, Math.floor((row.quantity || 1) * DEFAULT_PARTIAL_RATIO));
                        } else {
                          row.minQuantity = null;
                        }
                      }}
                    />
                    Partial
                  </label>
                  {#if row.allowPartial}
                    <input
                      type="number"
                      min="1"
                      max={row.quantity || 1}
                      bind:value={row.minQuantity}
                      disabled={submitting || row.status === 'done'}
                      class="field-input field-xs"
                      class:field-error={row.error && row.error.includes('Min')}
                      placeholder="Min"
                      onchange={() => clampMinQty(row)}
                    />
                  {/if}
                </div>
              {/if}
              {#if row.hasCond}
                <div class="field">
                  <label for="mass-tt-{row.key}">TT</label>
                  <input
                    id="mass-tt-{row.key}"
                    type="number"
                    min="0"
                    max={row.maxTT ?? undefined}
                    step="0.01"
                    bind:value={row.currentTT}
                    disabled={submitting || row.status === 'done'}
                    class="field-input field-sm"
                    class:field-error={row.error && row.error.includes('TT')}
                    onchange={() => clampTT(row)}
                  />
                </div>
              {/if}
              {#if row.tierable}
                <div class="field">
                  <label for="mass-tier-{row.key}">Tier</label>
                  <input
                    id="mass-tier-{row.key}"
                    type="number"
                    min="0"
                    max="10"
                    step="1"
                    bind:value={row.tier}
                    disabled={submitting || row.status === 'done'}
                    class="field-input field-xs"
                    onchange={() => clampTier(row)}
                  />
                </div>
                <div class="field">
                  <label for="mass-tir-{row.key}">TiR</label>
                  <input
                    id="mass-tir-{row.key}"
                    type="number"
                    min="0"
                    max={row.limited ? 4000 : 200}
                    step="1"
                    bind:value={row.tir}
                    disabled={submitting || row.status === 'done'}
                    class="field-input field-xs"
                    onchange={() => clampTiR(row)}
                  />
                </div>
              {/if}
              {#if row.blueprint && !row.limited}
                <div class="field">
                  <label for="mass-qr-{row.key}">QR</label>
                  <input
                    id="mass-qr-{row.key}"
                    type="number"
                    min="1"
                    max="100"
                    step="1"
                    bind:value={row.qr}
                    disabled={submitting || row.status === 'done'}
                    class="field-input field-xs"
                    onchange={() => clampQR(row)}
                  />
                </div>
              {/if}
            </div>
            {/if}
            {#if row.error}
              <div class="row-error-msg">{row.error}</div>
            {/if}
          </div>
        {/each}
      </div>

      {#if submitting || progress > 0}
        <div class="progress-bar">
          <div class="progress-fill" style="width: {totalOrders > 0 ? (progress / totalOrders * 100) : 0}%"></div>
        </div>
        <div class="progress-text">
          {#if submitting}
            Submitting {totalOrders} order{totalOrders !== 1 ? 's' : ''}...
          {:else if progress === totalOrders && !progressError}
            All {totalOrders} order{totalOrders !== 1 ? 's' : ''} submitted!
          {:else if progressError}
            {progress} of {totalOrders} submitted. {progressError}
          {/if}
        </div>
      {/if}

      {#if env.PUBLIC_TURNSTILE_SITE_KEY}
        <div class="turnstile-section">
          <TurnstileWidget
            siteKey={env.PUBLIC_TURNSTILE_SITE_KEY}
            bind:token={turnstileToken}
            bind:reset={resetTurnstile}
          />
        </div>
      {/if}

      <div class="modal-footer">
        <button class="btn-cancel" onclick={close} disabled={submitting}>
          {progress > 0 && !progressError ? 'Done' : 'Cancel'}
        </button>
        <span class="footer-spacer"></span>
        {#if progressError}
          <button class="btn-retry" onclick={retryFromError} disabled={env.PUBLIC_TURNSTILE_SITE_KEY && !turnstileToken}>Retry Remaining</button>
        {/if}
        {#if !progressError && submittableRows.length > 0 && progress < submittableRows.length}
          <button class="btn-submit" onclick={submit} disabled={submitting || submittableRows.length === 0 || (env.PUBLIC_TURNSTILE_SITE_KEY && !turnstileToken)}>
            {submitting ? 'Submitting...' : `Submit ${submittableRows.length} Order${submittableRows.length !== 1 ? 's' : ''}${editOrderCount > 0 ? ` (${editOrderCount} edit${editOrderCount !== 1 ? 's' : ''})` : ''}`}
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 20;
  }
  .modal {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 560px;
    max-width: calc(100% - 32px);
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
  }
  .modal-header h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
  }
  .close-btn {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 20px;
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }
  .close-btn:hover { color: var(--text-color); }
  .close-btn:disabled { opacity: 0.3; cursor: not-allowed; }

  .global-settings {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-bottom: 1px solid var(--border-color);
    font-size: 12px;
  }
  .global-settings label {
    color: var(--text-muted);
    font-weight: 500;
  }
  .field-select {
    padding: 4px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    font-size: 12px;
  }
  .field-select:disabled { opacity: 0.5; }

  .batch-info {
    font-size: 11px;
    color: var(--text-muted);
    padding: 4px 16px;
    border-bottom: 1px solid var(--border-color);
  }

  .order-rows-container {
    flex: 1;
    overflow-y: auto;
    padding: 8px 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-height: 0;
    max-height: 50vh;
  }

  .order-row {
    padding: 8px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-color, var(--primary-color));
    transition: border-color 0.15s ease, opacity 0.15s ease;
  }
  .order-row.error {
    border-color: var(--error-color);
  }
  .order-row.done {
    opacity: 0.5;
    border-color: var(--success-color);
  }
  .order-row.submitting {
    border-color: var(--accent-color);
  }
  .order-row.blocked {
    opacity: 0.45;
    border-style: dashed;
  }
  .order-row.blocked .row-name {
    text-decoration: line-through;
  }

  .row-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
  }
  .row-name {
    flex: 1;
    font-size: 13px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .row-status {
    font-size: 14px;
    width: 18px;
    text-align: center;
  }
  .status-done { color: var(--success-color); font-weight: 600; }
  .status-submitting { color: var(--accent-color); }
  .status-error { color: var(--error-color); font-weight: 600; }
  .row-remove {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 16px;
    cursor: pointer;
    padding: 0 2px;
    line-height: 1;
  }
  .row-remove:hover { color: var(--error-color); }
  .edit-badge {
    font-size: 10px;
    color: var(--accent-color);
    background: rgba(59, 130, 246, 0.15);
    padding: 1px 6px;
    border-radius: 3px;
    white-space: nowrap;
    flex-shrink: 0;
    font-weight: 600;
  }
  .blocked-badge {
    font-size: 10px;
    color: var(--error-color);
    background: rgba(239, 68, 68, 0.15);
    padding: 1px 6px;
    border-radius: 3px;
    white-space: nowrap;
    flex-shrink: 0;
    font-weight: 600;
  }

  .row-fields {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    align-items: flex-end;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .field label {
    font-size: 10px;
    color: var(--text-muted);
    font-weight: 500;
  }
  .field-input {
    padding: 4px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    font-size: 12px;
    width: 90px;
    transition: border-color 0.15s ease;
  }
  .field-input:focus {
    border-color: var(--accent-color);
    outline: none;
  }
  .field-input:disabled { opacity: 0.5; cursor: not-allowed; }
  .field-input.field-sm { width: 70px; }
  .field-input.field-xs { width: 55px; }
  .field-input.field-error { border-color: var(--error-color); }

  .field-partial {
    flex-direction: row;
    align-items: center;
    gap: 6px;
  }
  .partial-label {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--text-muted);
    cursor: pointer;
    white-space: nowrap;
  }
  .partial-label input[type="checkbox"] {
    margin: 0;
  }

  .row-error-msg {
    font-size: 11px;
    color: var(--error-color);
    margin-top: 4px;
  }

  .progress-bar {
    height: 3px;
    background: var(--border-color);
    border-radius: 2px;
    margin: 0 16px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: var(--accent-color);
    transition: width 0.3s ease;
    border-radius: 2px;
  }
  .progress-text {
    font-size: 11px;
    color: var(--text-muted);
    text-align: center;
    padding: 4px 16px;
  }

  .turnstile-section {
    padding: 8px 16px 0;
  }

  .modal-footer {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    border-top: 1px solid var(--border-color);
  }
  .footer-spacer { flex: 1; }
  .btn-cancel, .btn-retry, .btn-submit {
    padding: 6px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .btn-cancel {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }
  .btn-cancel:hover:not(:disabled) { background: var(--hover-color); }
  .btn-cancel:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-retry {
    background: transparent;
    border: 1px solid var(--warning-color);
    color: var(--warning-color);
  }
  .btn-retry:hover { background: rgba(245, 158, 11, 0.1); }
  .btn-submit {
    background: var(--accent-color);
    border: 1px solid var(--accent-color);
    color: white;
  }
  .btn-submit:hover:not(:disabled) { background: var(--accent-color-hover); }
  .btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }

  @media (max-width: 600px) {
    .modal {
      width: 100%;
      max-width: 100%;
      max-height: 100vh;
      border-radius: 0;
    }
    .row-fields {
      gap: 6px;
    }
    .field-input { width: 70px; }
    .field-input.field-sm { width: 55px; }
    .field-input.field-xs { width: 45px; }
  }
</style>
