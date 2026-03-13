<!--
  @component MassBuyDialog
  Batch buy order creation dialog for the construction calculator shopping list.
  Simplified version of MassSellDialog — only handles stackable buy orders with markup%.
  Supports inventory integration to show already-owned items and adjust quantities.
-->
<script>
  //@ts-nocheck
  import { PLANETS, MAX_BUY_ORDERS, DEFAULT_PARTIAL_RATIO } from '../../market/exchange/exchangeConstants.js';
  import { env } from '$env/dynamic/public';
  import TurnstileWidget from '$lib/components/TurnstileWidget.svelte';
  import InventoryImportDialog from '../../market/exchange/[[slug]]/[[id]]/InventoryImportDialog.svelte';
  import { addToast } from '$lib/stores/toasts.js';

  let turnstileToken = $state(null);
  let resetTurnstile = $state(false);

  
  
  
  
  
  /**
   * @typedef {Object} Props
   * @property {boolean} [show]
   * @property {Array<{ itemId: number, name: string, quantity: number, markup: number, stackable?: boolean }>} [items]
   * @property {number} [buyOrderCount]
   * @property {boolean} [isLoggedIn]
   * @property {Array} [allItems]
   * @property {Array|null} [inventoryData]
   */

  /** @type {Props} */
  let {
    show = false,
    items = [],
    buyOrderCount = $bindable(0),
    isLoggedIn = false,
    allItems = [],
    inventoryData = null,
    oncomplete,
    onclose
  } = $props();

  let orderRows = $state([]);
  let globalPlanet = $state('Calypso');
  let submitting = $state(false);
  let progress = $state(0);
  let totalOrders = $state(0);
  let progressError = $state(null);

  // User orders state (for edit detection)
  let userOrders = [];
  let ordersLoaded = $state(false);
  let ordersLoading = $state(false);

  // Inventory state
  let inventoryItems = $state([]);
  let inventoryLoaded = $state(false);
  let inventoryLoading = $state(false);
  let showInventoryImport = $state(false);
  let storageFilter = $state('all'); // 'none' | 'all' | planet name | 'inventory'







  async function loadUserOrders() {
    ordersLoading = true;
    try {
      const res = await fetch('/api/market/exchange/orders');
      if (!res.ok) throw new Error('Failed to load orders');
      const data = await res.json();
      userOrders = Array.isArray(data) ? data : (data.orders || []);
      ordersLoaded = true;
      // Update buyOrderCount from fetched data
      buyOrderCount = userOrders.filter(o => o.type === 'BUY' && o.state !== 'closed').length;
      applyExistingOrders();
    } catch (err) {
      console.error('Failed to load user orders:', err);
      ordersLoaded = true; // Prevent infinite retry loop
    } finally {
      ordersLoading = false;
    }
  }

  function applyExistingOrders() {
    if (!ordersLoaded || orderRows.length === 0) return;

    // Build lookup of existing active BUY orders by item_id
    const existingByItem = new Map();
    for (const order of userOrders) {
      if (order.type !== 'BUY' || order.state === 'closed') continue;
      if (!existingByItem.has(order.item_id)) existingByItem.set(order.item_id, []);
      existingByItem.get(order.item_id).push(order);
    }

    orderRows = orderRows.map(row => {
      if (row.covered || row.status === 'done') return row;
      const existing = existingByItem.get(row.itemId);
      if (existing && existing.length > 0) {
        // All items here are stackable — edit the existing order
        return {
          ...row,
          isEdit: true,
          existingOrderId: existing[0].id,
          markup: existing[0].markup, // Pre-fill with existing markup
        };
      }
      return row;
    });
  }

  function buildOrderRows() {
    // Preserve existing rows if re-opening with same items
    if (orderRows.length > 0 && !submitting) {
      const existingIds = new Set(orderRows.map(r => r.itemId));
      const newIds = new Set(items.map(i => i.itemId));
      if (existingIds.size === newIds.size && [...existingIds].every(id => newIds.has(id))) {
        return;
      }
    }

    orderRows = items.map((item, i) => ({
      key: `${item.itemId}_${i}`,
      itemId: item.itemId,
      itemName: item.name,
      originalQty: Math.ceil(item.quantity) || 1,
      quantity: Math.ceil(item.quantity) || 1,
      markup: item.markup || 100,
      allowPartial: (item.quantity || 1) > 1,
      minQuantity: Math.max(1, Math.floor((item.quantity || 1) * DEFAULT_PARTIAL_RATIO)),
      ownedQty: 0,
      covered: false,
      isEdit: false,
      existingOrderId: null,
      error: null,
      status: 'pending'
    }));
    progress = 0;
    totalOrders = 0;
    progressError = null;
    submitting = false;

    // If inventory was already loaded, apply it
    if (inventoryLoaded) {
      applyInventoryToRows();
    }

    // If user orders were already loaded, apply edit detection
    if (ordersLoaded) {
      applyExistingOrders();
    }
  }

  function removeRow(index) {
    orderRows = orderRows.filter((_, i) => i !== index);
    if (orderRows.length === 0) close();
  }

  // --- Inventory ---
  async function loadInventory() {
    inventoryLoading = true;
    try {
      const res = await fetch('/api/users/inventory');
      if (!res.ok) throw new Error('Failed to load');
      inventoryItems = await res.json();
      inventoryLoaded = true;
      applyInventoryToRows();
    } catch (err) {
      addToast('Failed to load inventory', { type: 'error' });
    } finally {
      inventoryLoading = false;
    }
  }

  function applyInventoryToRows() {
    const filtered = filterInventoryByStorage(inventoryItems, storageFilter);
    // Group by item_id, sum quantities
    const owned = new Map();
    for (const inv of filtered) {
      if (inv.item_id) {
        owned.set(inv.item_id, (owned.get(inv.item_id) || 0) + (inv.quantity || 0));
      }
    }
    orderRows = orderRows.map(row => {
      const ownedQty = owned.get(row.itemId) || 0;
      const remaining = Math.max(0, row.originalQty - ownedQty);
      const covered = remaining === 0;
      return {
        ...row,
        ownedQty,
        covered,
        quantity: covered ? 0 : remaining,
        minQuantity: covered ? 0 : Math.max(1, Math.floor(remaining * DEFAULT_PARTIAL_RATIO)),
        allowPartial: !covered && remaining > 1,
      };
    });
  }

  function filterInventoryByStorage(items, filter) {
    if (filter === 'none') return [];
    if (filter === 'all') return items;
    if (filter === 'inventory') return items.filter(i => !i.container || i.container === 'CARRIED');
    // Planet filter: include items on that planet + carried inventory
    return items.filter(i => {
      if (!i.container || i.container === 'CARRIED') return true;
      return i.container === filter;
    });
  }

  // --- Input clamping ---
  function clampMarkup(row) {
    if (row.markup == null || row.markup === '') { row.markup = 100; orderRows = orderRows; return; }
    row.markup = Math.max(100, Number(row.markup) || 100);
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
    if (row.covered) return null; // Skip covered rows
    if (row.markup == null || !isFinite(row.markup) || row.markup < 100) {
      return 'Markup must be at least 100%';
    }
    if (!row.quantity || row.quantity < 1) {
      return 'Quantity must be at least 1';
    }
    if (row.allowPartial && row.minQuantity != null) {
      if (row.minQuantity < 1) return 'Min quantity must be at least 1';
      if (row.minQuantity > row.quantity) return 'Min quantity cannot exceed quantity';
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
    const payload = {
      type: 'BUY',
      item_id: row.itemId,
      quantity: row.quantity || 1,
      markup: Number(row.markup) || 100,
      planet: globalPlanet,
      min_quantity: (row.allowPartial && row.minQuantity) ? row.minQuantity : null,
      details: { item_name: row.itemName },
    };
    if (row.isEdit && row.existingOrderId) {
      payload.order_id = row.existingOrderId;
    }
    return payload;
  }

  async function submit() {
    if (submitting) return;
    if (!validateAll()) return;

    if (env.PUBLIC_TURNSTILE_SITE_KEY && !turnstileToken) {
      addToast('Please complete the captcha verification', { type: 'warning' });
      return;
    }

    // Only submit non-covered rows
    const rowsToSubmit = orderRows.filter(r => !r.covered && r.status !== 'done');
    if (rowsToSubmit.length === 0) return;

    submitting = true;
    progressError = null;
    totalOrders = rowsToSubmit.length;
    progress = 0;

    orderRows = orderRows.map(r => r.covered || r.status === 'done' ? r : { ...r, status: 'submitting', error: null });

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
        orderRows = orderRows.map(r => r.covered ? r : { ...r, status: 'error', error: data.error || 'Batch request failed' });
        progressError = data.error || 'Batch request failed';
        submitting = false;
        return;
      }

      const results = data.results || [];
      let failedCount = 0;
      let submitIdx = 0;

      for (let i = 0; i < orderRows.length; i++) {
        if (orderRows[i].covered || orderRows[i].status === 'done') continue;
        const result = results[submitIdx++];
        if (result?.success) {
          orderRows[i] = { ...orderRows[i], status: 'done', error: null };
          progress++;
        } else {
          orderRows[i] = { ...orderRows[i], status: 'error', error: result?.error || 'Unknown error' };
          failedCount++;
        }
      }
      orderRows = orderRows;

      if (failedCount > 0) {
        progressError = `${failedCount} order${failedCount > 1 ? 's' : ''} failed. Review errors and retry.`;
        submitting = false;
      } else {
        submitting = false;
        const parts = [];
        const createdCount = results.filter(r => r?.action === 'created').length;
        const updatedCount = results.filter(r => r?.action === 'updated').length;
        if (createdCount > 0) parts.push(`${createdCount} created`);
        if (updatedCount > 0) parts.push(`${updatedCount} updated`);
        addToast(`${progress} buy order${progress > 1 ? 's' : ''} processed (${parts.join(', ')})`, { type: 'success' });
        oncomplete?.();
      }
    } catch (err) {
      orderRows = orderRows.map(r => r.covered || r.status === 'done' ? r : { ...r, status: 'error', error: 'Network error' });
      progressError = `Network error: ${err.message || 'Failed to reach server'}`;
      submitting = false;
    }
  }

  function retryFromError() {
    orderRows = orderRows.filter(r => r.status !== 'done');
    orderRows = orderRows.map(r => r.status === 'error' ? { ...r, status: 'pending', error: null } : r);
    progressError = null;
    progress = 0;
    totalOrders = orderRows.filter(r => !r.covered).length;
    resetTurnstile = true;
    turnstileToken = null;
  }

  function close() {
    if (submitting) return;
    ordersLoaded = false;
    onclose?.();
  }
  // Pre-populate inventory from parent if provided
  $effect(() => {
    if (show && inventoryData && !inventoryLoaded && !inventoryLoading) {
      inventoryItems = inventoryData;
      inventoryLoaded = true;
      applyInventoryToRows();
    }
  });
  // Available planets from inventory data
  let availablePlanets = $derived((() => {
    const planets = new Set();
    for (const item of inventoryItems) {
      if (item.container && item.container !== 'CARRIED') {
        planets.add(item.container);
      }
    }
    return [...planets].sort();
  })());
  // Re-apply inventory when storage filter changes
  $effect(() => {
    if (inventoryLoaded && storageFilter) {
      applyInventoryToRows();
    }
  });
  // Fetch user orders when dialog opens (for edit detection)
  $effect(() => {
    if (show && isLoggedIn && !ordersLoaded && !ordersLoading) {
      loadUserOrders();
    }
  });
  // Rebuild order rows when items change and dialog is shown
  $effect(() => {
    if (show && items.length > 0) {
      buildOrderRows();
    }
  });
  // Count of active (non-covered) rows for submit button
  let submittableRows = $derived(orderRows.filter(r => !r.covered && r.status !== 'done'));
  let newOrderCount = $derived(orderRows.filter(r => !r.isEdit && !r.covered && r.status !== 'done').length);
  let editOrderCount = $derived(orderRows.filter(r => r.isEdit && !r.covered && r.status !== 'done').length);
  let activeRowCount = $derived(submittableRows.length);
</script>

{#if show}
  <div class="modal-overlay" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) close(); }}>
    <div class="modal">
      <div class="modal-header">
        <h3>Mass Buy Orders</h3>
        <button class="close-btn" onclick={close} disabled={submitting}>&times;</button>
      </div>

      <div class="global-settings">
        <label for="massBuyPlanet">Planet</label>
        <select id="massBuyPlanet" bind:value={globalPlanet} disabled={submitting} class="field-select">
          {#each PLANETS as p}
            <option>{p}</option>
          {/each}
        </select>
        {#if isLoggedIn}
          <span class="settings-spacer"></span>
          {#if !inventoryLoaded}
            <button class="btn-sm" onclick={loadInventory} disabled={inventoryLoading || submitting}>
              {inventoryLoading ? 'Loading...' : 'Check Inventory'}
            </button>
            <button class="btn-sm" onclick={() => showInventoryImport = true} disabled={submitting}>
              Import
            </button>
          {:else}
            <select bind:value={storageFilter} class="field-select" disabled={submitting}>
              <option value="none">No Inventory</option>
              <option value="all">All storages</option>
              <option value="inventory">Carried only</option>
              {#if availablePlanets.length > 0}
                <optgroup label="Planet">
                  {#each availablePlanets as planet}
                    <option value={planet}>{planet}</option>
                  {/each}
                </optgroup>
              {/if}
            </select>
            <button class="btn-sm" onclick={loadInventory} disabled={inventoryLoading || submitting} title="Refresh">
              {inventoryLoading ? '...' : '↻'}
            </button>
            <button class="btn-sm" onclick={() => showInventoryImport = true} disabled={submitting}>
              Re-import
            </button>
          {/if}
        {/if}
      </div>

      <div class="batch-info">
        {buyOrderCount + newOrderCount} / {MAX_BUY_ORDERS} buy orders after this batch{#if editOrderCount > 0} ({editOrderCount} edit{editOrderCount !== 1 ? 's' : ''}){/if}
      </div>

      <div class="order-rows-container">
        {#each orderRows as row, i (row.key)}
          <div class="order-row" class:error={row.error} class:done={row.status === 'done'} class:submitting={row.status === 'submitting'} class:covered={row.covered}>
            <div class="row-header">
              <span class="row-name" title={row.itemName}>
                {row.itemName}
                {#if inventoryLoaded && row.ownedQty > 0 && !row.covered}
                  <span class="owned-badge">Have {row.ownedQty}</span>
                {/if}
              </span>
              {#if row.covered}
                <span class="covered-badge">Covered</span>
              {:else if row.isEdit}
                <span class="edit-badge">Edit</span>
              {/if}
              <span class="row-status">
                {#if row.status === 'done'}
                  <span class="status-done">&#10003;</span>
                {:else if row.status === 'submitting'}
                  <span class="status-submitting">...</span>
                {:else if row.status === 'error'}
                  <span class="status-error">!</span>
                {/if}
              </span>
              {#if !submitting && !row.covered}
                <button class="row-remove" onclick={() => removeRow(i)} title="Remove">&times;</button>
              {/if}
            </div>
            {#if !row.covered}
              <div class="row-fields">
                <div class="field">
                  <label>Markup (%)</label>
                  <input
                    type="number"
                    min="100"
                    step="1"
                    bind:value={row.markup}
                    disabled={submitting || row.status === 'done'}
                    class="field-input"
                    class:field-error={row.error && row.error.includes('Markup')}
                    onchange={() => clampMarkup(row)}
                  />
                </div>
                <div class="field">
                  <label>Qty</label>
                  <input
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
            Processing {totalOrders} orders...
          {:else if progress === totalOrders && !progressError}
            All {totalOrders} orders processed!
          {:else if progressError}
            {progress} of {totalOrders} processed. {progressError}
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
        {#if !progressError && submittableRows.length > 0}
          <button class="btn-submit" onclick={submit} disabled={submitting || submittableRows.length === 0 || (env.PUBLIC_TURNSTILE_SITE_KEY && !turnstileToken)}>
            {submitting ? 'Submitting...' : `Submit ${submittableRows.length} Order${submittableRows.length !== 1 ? 's' : ''}${editOrderCount > 0 ? ` (${editOrderCount} edit${editOrderCount !== 1 ? 's' : ''})` : ''}`}
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- Inventory Import Dialog (layered on top) -->
<InventoryImportDialog
  show={showInventoryImport}
  {allItems}
  onclose={() => showInventoryImport = false}
  onimported={() => {
    showInventoryImport = false;
    loadInventory();
  }}
/>

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 999;
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
    flex-wrap: wrap;
  }
  .global-settings label {
    color: var(--text-muted);
    font-weight: 500;
  }
  .settings-spacer { flex: 1; }
  .field-select {
    padding: 4px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    font-size: 12px;
  }
  .field-select:disabled { opacity: 0.5; }
  .btn-sm {
    padding: 3px 10px;
    font-size: 11px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }
  .btn-sm:hover:not(:disabled) {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }
  .btn-sm:disabled { opacity: 0.5; cursor: not-allowed; }

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
  .order-row.error { border-color: var(--error-color); }
  .order-row.done { opacity: 0.5; border-color: var(--success-color); }
  .order-row.submitting { border-color: var(--accent-color); }
  .order-row.covered {
    opacity: 0.45;
    border-style: dashed;
  }
  .order-row.covered .row-name {
    text-decoration: line-through;
  }

  .row-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
  }
  .order-row.covered .row-header {
    margin-bottom: 0;
  }
  .row-name {
    flex: 1;
    font-size: 13px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .covered-badge {
    font-size: 10px;
    color: var(--success-color, #22c55e);
    background: rgba(34, 197, 94, 0.1);
    padding: 1px 6px;
    border-radius: 3px;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .edit-badge {
    font-size: 10px;
    color: var(--accent-color, #3b82f6);
    background: rgba(59, 130, 246, 0.1);
    padding: 1px 6px;
    border-radius: 3px;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .owned-badge {
    font-size: 10px;
    color: var(--success-color, #22c55e);
    white-space: nowrap;
    margin-left: 4px;
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
  .field-input:focus { border-color: var(--accent-color); outline: none; }
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
  .partial-label input[type="checkbox"] { margin: 0; }

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
    .row-fields { gap: 6px; }
    .field-input { width: 70px; }
    .field-input.field-sm { width: 55px; }
    .field-input.field-xs { width: 45px; }
  }
</style>
