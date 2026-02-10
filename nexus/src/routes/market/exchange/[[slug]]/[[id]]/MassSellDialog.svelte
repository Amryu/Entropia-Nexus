<script>
  //@ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { isItemStackable, isPercentMarkup, isItemTierable, isBlueprint, isLimited, itemHasCondition } from '../../orderUtils';
  import { PLANETS, DEFAULT_PARTIAL_RATIO } from '../../exchangeConstants.js';

  export let show = false;
  export let items = []; // Array of { invItem, count }
  export let allItems = []; // Slim items for type lookup

  const dispatch = createEventDispatcher();

  let orderRows = [];
  let globalPlanet = 'Calypso';
  let submitting = false;
  let progress = 0;
  let totalOrders = 0;
  let progressError = null;

  // Unique key counter for expanded rows
  let rowKeyCounter = 0;

  // Rebuild order rows when items change and dialog is shown
  $: if (show && items.length > 0) {
    buildOrderRows();
  }

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

      for (let c = 0; c < rowCount; c++) {
        const qty = stackable ? (invItem.quantity || 1) : 1;
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
          markup: defaultMarkup,
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
          error: null,
          status: 'pending', // 'pending' | 'submitting' | 'done' | 'error'
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
    if (row.markup == null || row.markup === '') { row.markup = row.pctMarkup ? 100 : 0; orderRows = orderRows; return; }
    row.markup = Math.max(row.pctMarkup ? 100 : 0, Number(row.markup) || 0);
    orderRows = orderRows;
  }
  function clampTT(row) {
    if (row.currentTT == null || row.currentTT === '') return;
    let v = Math.max(0, Number(row.currentTT) || 0);
    if (row.maxTT != null) v = Math.min(v, row.maxTT);
    row.currentTT = Math.round(v * 100) / 100;
    orderRows = orderRows;
  }
  function clampTier(row) {
    if (row.tier == null || row.tier === '') return;
    row.tier = Math.max(0, Math.min(10, Math.round(Number(row.tier) || 0)));
    orderRows = orderRows;
  }
  function clampTiR(row) {
    if (row.tir == null || row.tir === '') return;
    const max = row.limited ? 4000 : 200;
    row.tir = Math.max(0, Math.min(max, Math.round(Number(row.tir) || 0)));
    orderRows = orderRows;
  }
  function clampQR(row) {
    if (row.qr == null || row.qr === '') return;
    row.qr = Math.max(1, Math.min(100, Math.round(Number(row.qr) || 0)));
    orderRows = orderRows;
  }
  function clampQty(row) {
    if (row.quantity == null) return;
    row.quantity = Math.max(1, Math.round(Number(row.quantity) || 1));
    if (row.allowPartial && row.minQuantity > row.quantity) row.minQuantity = row.quantity;
    orderRows = orderRows;
  }
  function clampMinQty(row) {
    if (row.minQuantity == null) return;
    row.minQuantity = Math.max(1, Math.min(row.quantity || 1, Math.round(Number(row.minQuantity) || 1)));
    orderRows = orderRows;
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
    return {
      type: 'SELL',
      item_id: row.itemId,
      quantity: row.stackable ? (row.quantity || 1) : 1,
      markup: Number(row.markup) || 0,
      planet: globalPlanet,
      min_quantity: (row.stackable && row.allowPartial && row.minQuantity) ? row.minQuantity : null,
      details,
    };
  }

  async function submit() {
    if (submitting) return;
    if (!validateAll()) return;

    submitting = true;
    progressError = null;
    totalOrders = orderRows.length;
    progress = 0;

    for (let i = 0; i < orderRows.length; i++) {
      const row = orderRows[i];
      const payload = buildPayload(row);

      orderRows[i] = { ...orderRows[i], status: 'submitting', error: null };
      orderRows = orderRows;

      try {
        const res = await fetch('/api/market/exchange/orders', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) {
          orderRows[i] = { ...orderRows[i], status: 'error', error: data.error || 'Failed to create order' };
          orderRows = orderRows;
          progressError = `Failed on "${row.itemName}": ${data.error || 'Unknown error'}`;
          submitting = false;
          return;
        }
        progress++;
        orderRows[i] = { ...orderRows[i], status: 'done' };
        orderRows = orderRows;
      } catch (err) {
        orderRows[i] = { ...orderRows[i], status: 'error', error: err.message || 'Network error' };
        orderRows = orderRows;
        progressError = `Failed on "${row.itemName}": ${err.message || 'Network error'}`;
        submitting = false;
        return;
      }
    }

    submitting = false;
    dispatch('complete');
  }

  function retryFromError() {
    orderRows = orderRows.filter(r => r.status !== 'done');
    orderRows = orderRows.map(r => r.status === 'error' ? { ...r, status: 'pending', error: null } : r);
    progressError = null;
    progress = 0;
    totalOrders = orderRows.length;
  }

  function close() {
    if (submitting) return;
    dispatch('close');
  }
</script>

{#if show}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="modal-overlay" on:click|self={close}>
    <div class="modal">
      <div class="modal-header">
        <h3>Mass Sell Orders</h3>
        <button class="close-btn" on:click={close} disabled={submitting}>&times;</button>
      </div>

      <div class="global-settings">
        <label for="massSellPlanet">Planet</label>
        <select id="massSellPlanet" bind:value={globalPlanet} disabled={submitting} class="field-select">
          {#each PLANETS as p}
            <option>{p}</option>
          {/each}
        </select>
      </div>

      <div class="order-rows-container">
        {#each orderRows as row, i (row.key)}
          <div class="order-row" class:error={row.error} class:done={row.status === 'done'} class:submitting={row.status === 'submitting'}>
            <div class="row-header">
              <span class="row-name" title={row.itemName}>
                {row.itemName}
              </span>
              <span class="row-status">
                {#if row.status === 'done'}
                  <span class="status-done">&#10003;</span>
                {:else if row.status === 'submitting'}
                  <span class="status-submitting">...</span>
                {:else if row.status === 'error'}
                  <span class="status-error">!</span>
                {/if}
              </span>
              {#if !submitting}
                <button class="row-remove" on:click={() => removeRow(i)} title="Remove">&times;</button>
              {/if}
            </div>
            <div class="row-fields">
              <div class="field">
                <label>Markup{row.pctMarkup ? ' (%)' : ' (+PED)'}</label>
                <input
                  type="number"
                  min={row.pctMarkup ? 100 : 0}
                  step={row.pctMarkup ? 1 : 0.01}
                  bind:value={row.markup}
                  disabled={submitting || row.status === 'done'}
                  class="field-input"
                  class:field-error={row.error && row.error.includes('Markup')}
                  on:change={() => clampMarkup(row)}
                />
              </div>
              {#if row.stackable}
                <div class="field">
                  <label>Qty</label>
                  <input
                    type="number"
                    min="1"
                    bind:value={row.quantity}
                    disabled={submitting || row.status === 'done'}
                    class="field-input field-sm"
                    class:field-error={row.error && row.error.includes('Quantity')}
                    on:change={() => clampQty(row)}
                  />
                </div>
                <div class="field field-partial">
                  <label class="partial-label">
                    <input
                      type="checkbox"
                      bind:checked={row.allowPartial}
                      disabled={submitting || row.status === 'done'}
                      on:change={() => {
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
                      on:change={() => clampMinQty(row)}
                    />
                  {/if}
                </div>
              {/if}
              {#if row.hasCond}
                <div class="field">
                  <label>TT</label>
                  <input
                    type="number"
                    min="0"
                    max={row.maxTT ?? undefined}
                    step="0.01"
                    bind:value={row.currentTT}
                    disabled={submitting || row.status === 'done'}
                    class="field-input field-sm"
                    class:field-error={row.error && row.error.includes('TT')}
                    on:change={() => clampTT(row)}
                  />
                </div>
              {/if}
              {#if row.tierable}
                <div class="field">
                  <label>Tier</label>
                  <input
                    type="number"
                    min="0"
                    max="10"
                    step="1"
                    bind:value={row.tier}
                    disabled={submitting || row.status === 'done'}
                    class="field-input field-xs"
                    on:change={() => clampTier(row)}
                  />
                </div>
                <div class="field">
                  <label>TiR</label>
                  <input
                    type="number"
                    min="0"
                    max={row.limited ? 4000 : 200}
                    step="1"
                    bind:value={row.tir}
                    disabled={submitting || row.status === 'done'}
                    class="field-input field-xs"
                    on:change={() => clampTiR(row)}
                  />
                </div>
              {/if}
              {#if row.blueprint && !row.limited}
                <div class="field">
                  <label>QR</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    step="1"
                    bind:value={row.qr}
                    disabled={submitting || row.status === 'done'}
                    class="field-input field-xs"
                    on:change={() => clampQR(row)}
                  />
                </div>
              {/if}
            </div>
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
            Creating order {progress + 1} of {totalOrders}...
          {:else if progress === totalOrders && !progressError}
            All {totalOrders} orders created!
          {:else if progressError}
            {progressError}
          {/if}
        </div>
      {/if}

      <div class="modal-footer">
        <button class="btn-cancel" on:click={close} disabled={submitting}>
          {progress > 0 && !progressError ? 'Done' : 'Cancel'}
        </button>
        <span class="footer-spacer"></span>
        {#if progressError}
          <button class="btn-retry" on:click={retryFromError}>Retry Remaining</button>
        {/if}
        {#if !progressError && progress < orderRows.length}
          <button class="btn-submit" on:click={submit} disabled={submitting || orderRows.length === 0}>
            {submitting ? 'Submitting...' : `Submit ${orderRows.length} Orders`}
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
