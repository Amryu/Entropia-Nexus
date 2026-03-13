<script>
  //@ts-nocheck
  import { tradeList, removeFromTradeList, clearTradeList } from '../../exchangeStore.js';
  import { formatPedValue, itemTypeBadge } from '../../orderUtils';
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  
  /**
   * @typedef {Object} Props
   * @property {Array} [allItems]
   */

  /** @type {Props} */
  let { allItems = [] } = $props();

  let itemLookup = $derived((() => {
    const map = new Map();
    for (const it of allItems || []) {
      if (it?.i != null) map.set(it.i, it);
    }
    return map;
  })());

  let checkingOut = $state(false);
  let checkoutError = $state(null);
  let checkoutResult = $state(null);

  // Group trade list items by seller
  let filteredItems = $derived($tradeList);

  let groupedBySeller = $derived((() => {
    const groups = {};
    for (const item of filteredItems) {
      const key = `${item.sellerId || 'unknown'}`;
      if (!groups[key]) {
        groups[key] = {
          sellerId: item.sellerId,
          sellerName: item.sellerName || 'Unknown',
          planet: item.planet || '',
          items: [],
          total: 0,
        };
      }
      groups[key].items.push(item);
      groups[key].total += (item.unitPrice || 0) * (item.quantity || 1);
    }
    return Object.values(groups);
  })());

  let totalPED = $derived(filteredItems.reduce((sum, item) => sum + (item.unitPrice || 0) * (item.quantity || 1), 0));
  let totalItems = $derived(filteredItems.length);

  function handleClose() {
    dispatch('close');
  }

  function handleRemove(orderId) {
    removeFromTradeList(orderId);
  }

  function handleClear() {
    clearTradeList();
  }

  async function handleCheckout() {
    if (checkingOut || filteredItems.length === 0) return;
    checkingOut = true;
    checkoutError = null;
    checkoutResult = null;

    let created = 0;
    let failed = 0;

    for (const group of groupedBySeller) {
      if (!group.sellerId) {
        failed++;
        continue;
      }
      try {
        const res = await fetch('/api/market/trade-requests', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_id: group.sellerId,
            planet: group.planet || null,
            items: group.items.map(item => ({
              offer_id: item.orderId || null,
              item_id: item.itemId,
              item_name: item.itemName || 'Unknown',
              quantity: item.quantity || 1,
              markup: item.markup || 0,
              side: item.side || 'SELL'
            }))
          })
        });
        if (res.ok) {
          created++;
        } else {
          const data = await res.json().catch(() => ({}));
          console.error('Checkout error:', data.error || res.statusText);
          failed++;
        }
      } catch (err) {
        console.error('Checkout error:', err);
        failed++;
      }
    }

    checkingOut = false;

    if (created > 0) {
      checkoutResult = `Created ${created} trade request${created !== 1 ? 's' : ''}${failed > 0 ? `, ${failed} failed` : ''} — a Discord thread will be opened shortly.`;
      clearTradeList();
    } else if (failed > 0) {
      checkoutError = `Failed to create trade requests. Make sure you have the market.trade permission.`;
    }
  }
</script>

<div class="cart-summary">
  <div class="cart-header">
    <button class="back-btn" onclick={handleClose}>Back</button>
    <h2>Trade List</h2>
    <div class="header-actions">
      <button class="btn-clear" onclick={handleClear} disabled={$tradeList.length === 0}>Clear</button>
    </div>
  </div>

  {#if $tradeList.length === 0}
    <div class="empty-state">
      <p>Your trade list is empty. Add items from the order book or seller orders.</p>
    </div>
  {:else}
    <div class="cart-body">
      {#each groupedBySeller as group}
        <div class="seller-group">
          <div class="seller-header">
            <span class="seller-name">{group.sellerName}</span>
            {#if group.planet}
              <span class="seller-planet">{group.planet}</span>
            {/if}
            <span class="seller-total">{formatPedValue(group.total)}</span>
          </div>
          {#each group.items as item}
            <div class="cart-item">
              <div class="item-info">
                <span class="item-name">
                  <span class="badge badge-subtle {item.side === 'BUY' ? 'badge-success' : 'badge-error'} side-badge">{item.side === 'BUY' ? 'Buy' : 'Sell'}</span>
                  {item.itemName || 'Unknown Item'}{@html itemTypeBadge(itemLookup.get(item.itemId)?.t)}
                </span>
                <span class="item-details">
                  {item.quantity || 1}x @ {formatPedValue(item.unitPrice || 0)}
                  {#if item.markup != null}
                    <span class="item-markup">({item.markup}% MU)</span>
                  {/if}
                </span>
              </div>
              <div class="item-total">
                {formatPedValue((item.unitPrice || 0) * (item.quantity || 1))}
              </div>
              <button class="remove-btn" onclick={() => handleRemove(item.orderId)} title="Remove">&times;</button>
            </div>
          {/each}
        </div>
      {/each}
    </div>

    <div class="cart-footer">
      {#if checkoutError}
        <div class="checkout-error">{checkoutError}</div>
      {/if}
      {#if checkoutResult}
        <div class="checkout-success">{checkoutResult}</div>
      {/if}
      <div class="cart-totals">
        <span>{totalItems} item{totalItems !== 1 ? 's' : ''} from {groupedBySeller.length} seller{groupedBySeller.length !== 1 ? 's' : ''}</span>
        <span class="total-amount">{formatPedValue(totalPED)}</span>
      </div>
      <button
        class="checkout-btn"
        onclick={handleCheckout}
        disabled={checkingOut || filteredItems.length === 0}
      >
        {checkingOut ? 'Sending...' : `Checkout (${groupedBySeller.length} trade request${groupedBySeller.length !== 1 ? 's' : ''})`}
      </button>
    </div>
  {/if}
</div>

<style>
  .cart-summary {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }
  .cart-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    flex-shrink: 0;
    border-bottom: 1px solid var(--border-color);
  }
  .cart-header h2 {
    margin: 0;
    flex: 1;
    font-size: 16px;
    font-weight: 600;
  }
  .header-actions {
    display: flex;
    gap: 6px;
  }
  .back-btn {
    display: inline-flex;
    align-items: center;
    padding: 6px 14px;
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
    cursor: pointer;
    border-radius: 6px;
    font-size: 13px;
    transition: all 0.2s ease;
  }
  .back-btn:hover { background: var(--hover-color); border-color: var(--border-hover); }
  .btn-clear {
    padding: 6px 14px;
    border: 1px solid var(--error-color);
    border-radius: 6px;
    background: transparent;
    color: var(--error-color);
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s ease;
  }
  .btn-clear:hover:not(:disabled) { background: rgba(239, 68, 68, 0.1); border-color: var(--error-color); }
  .btn-clear:disabled { opacity: 0.7; cursor: not-allowed; }

  .cart-body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 8px 12px;
  }
  .seller-group {
    margin-bottom: 8px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }
  .seller-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--hover-color);
    font-size: 13px;
    font-weight: 600;
  }
  .seller-name {
    flex: 1;
  }
  .seller-planet {
    font-size: 10px;
    padding: 2px 8px;
    background: rgba(59, 130, 246, 0.12);
    color: var(--accent-color);
    border-radius: 10px;
    font-weight: 500;
  }
  .seller-total {
    font-weight: 600;
    color: var(--accent-color);
    font-size: 13px;
  }

  .cart-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-top: 1px solid var(--border-color);
    transition: background-color 0.15s ease;
  }
  .cart-item:hover {
    background: var(--hover-color);
  }
  .item-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  .item-name {
    font-size: 13px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .item-details {
    font-size: 11px;
    color: var(--text-muted);
  }
  .item-markup {
    color: var(--text-muted);
  }
  .item-total {
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
  }
  .remove-btn {
    padding: 2px 6px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--error-color);
    font-size: 16px;
    line-height: 1;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .remove-btn:hover {
    background: rgba(239, 68, 68, 0.15);
    border-color: var(--error-color);
  }

  .cart-footer {
    padding: 12px 16px;
    border-top: 1px solid var(--border-color);
    flex-shrink: 0;
    background: var(--hover-color);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .cart-totals {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
  }
  .total-amount {
    font-weight: 700;
    font-size: 16px;
    color: var(--accent-color);
  }
  .checkout-btn {
    width: 100%;
    padding: 8px 16px;
    border: 1px solid var(--accent-color);
    border-radius: 6px;
    background: var(--accent-color);
    color: white;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .checkout-btn:hover:not(:disabled) {
    opacity: 0.9;
  }
  .checkout-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .checkout-error {
    padding: 6px 8px;
    border-radius: 4px;
    font-size: 12px;
    color: var(--error-color, #ef4444);
    background: var(--error-bg, rgba(239, 68, 68, 0.1));
  }
  .checkout-success {
    padding: 6px 8px;
    border-radius: 4px;
    font-size: 12px;
    color: var(--success-color, #16a34a);
    background: rgba(22, 163, 74, 0.1);
  }

  .empty-state {
    text-align: center;
    padding: 3rem 2rem;
    color: var(--text-muted);
  }
</style>
