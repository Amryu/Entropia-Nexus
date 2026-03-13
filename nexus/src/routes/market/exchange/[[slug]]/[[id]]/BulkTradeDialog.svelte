<script>
  //@ts-nocheck
  import { isPercentMarkup, formatMarkupValue } from '../../orderUtils';









  /**
   * @typedef {Object} Props
   * @property {boolean} [show]
   * @property {string} [itemName]
   * @property {object|null} [item]
   * @property {Array} [orderBookOrders]
   * @property {Array} [planets]
   * @property {() => void} [onclose]
   * @property {(data: any) => void} [onbulkSubmit]
   */

  /** @type {Props} */
  let {
    show = false,
    itemName = '',
    item = null,
    orderBookOrders = [],
    planets = ['Calypso', 'Arkadia', 'Cyrene', 'Monria', 'Next Island', 'Rocktropia', 'Toulan'],
    onclose,
    onbulkSubmit,
  } = $props();

  let activeTab = $state('buy'); // 'buy' | 'sell'
  let quantity = $state(1);
  let minOrder = $state(0);
  let maxTraders = $state(5);
  let planet = $state('All Planets');
  let submitting = false;
  let error = null;


  function computeMatches(orders, tab, qty, minOrderQty, maxTradersLimit, planetFilter) {
    if (!orders || !qty || qty <= 0) return { matched: [], totalFilled: 0, remaining: 0 };

    const opposingSide = tab === 'buy' ? 'SELL' : 'BUY';
    let candidates = orders.filter(o => o.type === opposingSide);

    if (planetFilter && planetFilter !== 'All Planets') {
      candidates = candidates.filter(o => o.planet === planetFilter);
    }
    if (minOrderQty > 0) {
      candidates = candidates.filter(o => (o.quantity || 0) >= minOrderQty);
    }

    // Sort: best markup first (lowest for buy, highest for sell)
    if (tab === 'buy') {
      candidates.sort((a, b) => (a.markup || 0) - (b.markup || 0));
    } else {
      candidates.sort((a, b) => (b.markup || 0) - (a.markup || 0));
    }

    const traderLimit = maxTradersLimit === 0 ? Infinity : maxTradersLimit;
    const result = [];
    let totalFilled = 0;
    let tradersUsed = 0;

    for (const order of candidates) {
      if (tradersUsed >= traderLimit) break;
      if (totalFilled >= qty) break;

      const remaining = qty - totalFilled;
      const fillQty = Math.min(remaining, order.quantity || 1);
      const orderMin = order.min_quantity || 1;

      // Skip orders where fill amount doesn't meet the offer's minimum quantity
      if (fillQty < orderMin) continue;

      result.push({ ...order, fillQuantity: fillQty });
      totalFilled += fillQty;
      tradersUsed++;
    }

    return { matched: result, totalFilled, remaining: Math.max(0, qty - totalFilled) };
  }

  function close() {
    onclose?.();
  }

  function submit() {
    if (submitting || matched.matched.length === 0) return;
    onbulkSubmit?.({
      type: activeTab === 'buy' ? 'Buy' : 'Sell',
      matches: matched.matched,
      planet: planet === 'All Planets' ? null : planet
    });
  }
  let matched = $derived(computeMatches(orderBookOrders, activeTab, quantity, minOrder, maxTraders, planet));
</script>

{#if show}
  <div
    class="modal-overlay"
    role="button"
    tabindex="0"
    onclick={(e) => { if (e.target.classList.contains('modal-overlay')) close(); }}
    onkeydown={(e) => { if (e.key === 'Escape') close(); }}
  >
    <div class="modal">
      <div class="item-name">{itemName}</div>

      <div class="tab-bar">
        <button class="tab" class:active={activeTab === 'buy'} onclick={() => activeTab = 'buy'}>
          Bulk Buy
        </button>
        <button class="tab" class:active={activeTab === 'sell'} onclick={() => activeTab = 'sell'}>
          Bulk Sell
        </button>
      </div>

      <div class="bulk-form">
        <div class="form-row">
          <label for="bulkQty">Quantity Needed</label>
          <input id="bulkQty" type="number" min="1" bind:value={quantity} />
        </div>
        <div class="form-row">
          <label for="bulkMinOrder">Min Order Qty</label>
          <input id="bulkMinOrder" type="number" min="0" bind:value={minOrder} placeholder="0 = any" />
        </div>
        <div class="form-row">
          <label for="bulkMaxTraders">Max Traders</label>
          <div class="slider-row">
            <input id="bulkMaxTraders" type="range" min="0" max="20" bind:value={maxTraders} />
            <span class="slider-value">{maxTraders === 0 ? 'No limit' : maxTraders}</span>
          </div>
        </div>
        <div class="form-row">
          <label for="bulkPlanet">Planet</label>
          <select id="bulkPlanet" bind:value={planet} class="filter-select select-center">
            <option>All Planets</option>
            {#each planets as p}
              <option>{p}</option>
            {/each}
          </select>
        </div>
      </div>

      <div class="bulk-preview">
        <div class="bulk-preview-header">
          <span class="bulk-preview-title">Matching Orders</span>
          <span class="bulk-preview-summary">
            {matched.totalFilled} / {quantity || 0} filled
            {#if matched.remaining > 0}
              <span class="bulk-warning">({matched.remaining} remaining)</span>
            {/if}
          </span>
        </div>
        {#if matched.matched.length > 0}
          <div class="bulk-table">
            <div class="bulk-row bulk-header-row">
              <span class="bulk-cell name-cell">{activeTab === 'buy' ? 'Seller' : 'Buyer'}</span>
              <span class="bulk-cell">Qty</span>
              <span class="bulk-cell">Min</span>
              <span class="bulk-cell">Markup</span>
              <span class="bulk-cell">Planet</span>
            </div>
            {#each matched.matched as match}
              <div class="bulk-row">
                <span class="bulk-cell name-cell">{match.seller_name || 'Unknown'}</span>
                <span class="bulk-cell">{match.fillQuantity}</span>
                <span class="bulk-cell">{match.min_quantity || 1}</span>
                <span class="bulk-cell">{formatMarkupValue(match.markup, !isPercentMarkup(item))}</span>
                <span class="bulk-cell">{match.planet || 'Any'}</span>
              </div>
            {/each}
          </div>
        {:else}
          <div class="bulk-empty">No matching orders found</div>
        {/if}
      </div>

      {#if error}
        <div class="bulk-error">{error}</div>
      {/if}

      <div class="actions">
        <span class="actions-spacer"></span>
        <button onclick={close}>Cancel</button>
        <button
          class="submit-btn {activeTab === 'buy' ? 'submit-buy' : 'submit-sell'}"
          onclick={submit}
          disabled={submitting || matched.matched.length === 0}
          title="Send trade requests to all matched {activeTab === 'buy' ? 'sellers' : 'buyers'}"
        >
          {submitting ? 'Sending...' : `Bulk ${activeTab === 'buy' ? 'Buy' : 'Sell'} Now`}
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
    justify-content: center;
    align-items: center;
    z-index: 1000;
  }
  .modal {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    width: 480px;
    max-width: calc(100% - 32px);
    max-height: 85vh;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .item-name {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-color);
    text-align: center;
  }
  .tab-bar {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 8px;
  }
  .tab {
    flex: 1;
    padding: 6px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px 6px 0 0;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 13px;
    transition: all 0.15s;
  }
  .tab.active {
    background: var(--accent-color);
    color: white;
    border-bottom-color: transparent;
  }
  .tab:hover:not(.active) {
    background: var(--hover-color);
  }
  .bulk-form {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .form-row {
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: 8px;
    align-items: center;
  }
  .form-row label {
    font-size: 13px;
    color: var(--text-muted);
  }
  .form-row input[type="number"],
  .form-row select {
    padding: 6px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 13px;
  }
  .slider-row {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .slider-row input[type="range"] {
    flex: 1;
  }
  .slider-value {
    font-size: 12px;
    min-width: 50px;
    text-align: center;
    color: var(--text-muted);
  }
  .bulk-preview {
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
  }
  .bulk-preview-header {
    display: flex;
    justify-content: space-between;
    padding: 8px 10px;
    background: var(--hover-color);
    font-size: 12px;
  }
  .bulk-preview-title {
    font-weight: 600;
    color: var(--text-color);
  }
  .bulk-preview-summary {
    color: var(--text-muted);
  }
  .bulk-warning {
    color: var(--warning-color, #f59e0b);
  }
  .bulk-table {
    height: 200px;
    overflow-y: auto;
  }
  .bulk-row {
    display: flex;
    padding: 4px 10px;
    font-size: 12px;
    border-top: 1px solid var(--border-color);
  }
  .bulk-header-row {
    font-weight: 600;
    color: var(--text-muted);
    background: var(--hover-color);
  }
  .bulk-cell {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .name-cell { flex: 2; }
  .bulk-empty {
    height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    font-size: 12px;
  }
  .bulk-error {
    color: var(--error-color, #ef4444);
    font-size: 12px;
    padding: 6px 8px;
    background: rgba(239, 68, 68, 0.1);
    border-radius: 4px;
  }
  .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 1rem;
    padding-top: 12px;
    border-top: 1px solid var(--border-color);
  }
  .actions-spacer {
    flex: 1;
  }
  .actions button {
    padding: 8px 18px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }
  .actions button:hover:not(:disabled) {
    background: var(--hover-color);
  }
  .actions button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .actions .submit-btn {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
  }
  .actions .submit-btn:hover:not(:disabled) {
    background: var(--accent-color-hover);
  }
</style>
