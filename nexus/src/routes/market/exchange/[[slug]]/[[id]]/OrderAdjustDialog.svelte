<script>
  import { run, self } from 'svelte/legacy';

  //@ts-nocheck
  import { createEventDispatcher, onMount } from 'svelte';
  import { myOrders, inventory, enrichOrders, upsertOrder } from '../../exchangeStore.js';

  /**
   * @typedef {Object} Props
   * @property {boolean} [show]
   */

  /** @type {Props} */
  let { show = false } = $props();

  const dispatch = createEventDispatcher();

  let discrepancies = $state([]);
  let adjustingAll = $state(false);
  let cancellingAll = $state(false);
  let loading = $state(false);


  async function computeDiscrepancies() {
    loading = true;

    // Ensure orders are loaded
    let orders = $myOrders;
    if (!orders || orders.length === 0) {
      try {
        const res = await fetch('/api/market/exchange/orders');
        if (res.ok) {
          orders = enrichOrders(await res.json());
          myOrders.set(orders);
        }
      } catch {}
    }

    // Only check active SELL orders (exclude closed/terminated)
    const sellOrders = (orders || []).filter(o => o.type === 'SELL' && o.state_display !== 'closed' && o.state_display !== 'terminated');
    if (sellOrders.length === 0) {
      discrepancies = [];
      loading = false;
      return;
    }

    // Build inventory quantity map by item_id
    const invQtyMap = new Map();
    for (const item of ($inventory || [])) {
      if (item.item_id > 0) {
        invQtyMap.set(item.item_id, (invQtyMap.get(item.item_id) || 0) + item.quantity);
      }
    }

    discrepancies = sellOrders
      .map(order => {
        const invQty = invQtyMap.get(order.item_id) || 0;
        if (order.quantity > invQty) {
          return {
            order,
            orderQty: order.quantity,
            invQty,
            deficit: order.quantity - invQty,
            item_name: order.details?.item_name || `Item #${order.item_id}`,
            _processing: false,
          };
        }
        return null;
      })
      .filter(Boolean);

    loading = false;
  }

  async function adjustOrder(disc) {
    disc._processing = true;
    discrepancies = discrepancies;
    try {
      const newQty = disc.invQty;
      if (newQty <= 0) {
        await cancelOrder(disc);
        return;
      }
      const res = await fetch(`/api/market/exchange/orders/${disc.order.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quantity: newQty,
          markup: disc.order.markup,
          planet: disc.order.planet,
          min_quantity: disc.order.min_quantity ? Math.min(disc.order.min_quantity, newQty) : null,
          details: disc.order.details,
        }),
      });
      if (!res.ok) throw new Error('Failed to adjust order');
      const data = await res.json();
      upsertOrder(data);
      discrepancies = discrepancies.filter(d => d !== disc);
    } catch (e) {
      disc._processing = false;
      discrepancies = discrepancies;
    }
  }

  async function cancelOrder(disc) {
    disc._processing = true;
    discrepancies = discrepancies;
    try {
      const res = await fetch(`/api/market/exchange/orders/${disc.order.id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to cancel order');
      const data = await res.json();
      upsertOrder(data);
      discrepancies = discrepancies.filter(d => d !== disc);
    } catch (e) {
      disc._processing = false;
      discrepancies = discrepancies;
    }
  }

  async function adjustAll() {
    adjustingAll = true;
    const toProcess = [...discrepancies];
    for (const disc of toProcess) {
      await adjustOrder(disc);
    }
    adjustingAll = false;
  }

  async function cancelAll() {
    cancellingAll = true;
    const toProcess = [...discrepancies];
    for (const disc of toProcess) {
      await cancelOrder(disc);
    }
    cancellingAll = false;
  }

  function handleClose() {
    dispatch('close');
  }

  /** Expose discrepancy count for the parent to show a badge */
  export function getDiscrepancyCount() {
    return discrepancies.length;
  }

  /** Recompute from outside (e.g. after inventory refresh) */
  export function refresh() {
    if (show) computeDiscrepancies();
  }
  run(() => {
    if (show) computeDiscrepancies();
  });
</script>

{#if show}
  <div class="modal-overlay" role="presentation" onclick={self(handleClose)}>
    <div class="modal">
      <div class="modal-header">
        <h3 class="modal-title">Order Coverage</h3>
        <button class="close-btn" onclick={handleClose}>&times;</button>
      </div>

      {#if loading}
        <p class="loading-msg">Checking orders against inventory...</p>
      {:else if discrepancies.length > 0}
        <p class="discrepancy-desc">
          These sell orders advertise more items than you currently have in inventory.
        </p>
        <div class="bulk-actions">
          <button
            class="btn-adjust"
            onclick={adjustAll}
            disabled={adjustingAll || cancellingAll}
          >{adjustingAll ? 'Adjusting...' : 'Adjust All'}</button>
          <button
            class="btn-cancel"
            onclick={cancelAll}
            disabled={adjustingAll || cancellingAll}
          >{cancellingAll ? 'Cancelling...' : 'Cancel All'}</button>
        </div>
        <div class="discrepancy-table">
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th>Order</th>
                <th>Inventory</th>
                <th>Deficit</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each discrepancies as disc}
                <tr>
                  <td class="disc-name">{disc.item_name}</td>
                  <td>{disc.orderQty}</td>
                  <td>{disc.invQty}</td>
                  <td class="disc-deficit">-{disc.deficit}</td>
                  <td class="disc-actions">
                    {#if disc._processing}
                      <span class="processing">...</span>
                    {:else}
                      <button class="disc-btn adjust" onclick={() => adjustOrder(disc)}
                        title={disc.invQty > 0 ? `Set to ${disc.invQty}` : 'Cancel (no inventory)'}>
                        {disc.invQty > 0 ? 'Adjust' : 'Cancel'}
                      </button>
                      {#if disc.invQty > 0}
                        <button class="disc-btn cancel" onclick={() => cancelOrder(disc)}>Cancel</button>
                      {/if}
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <div class="coverage-ok">All sell orders are covered by your inventory.</div>
      {/if}

      <div class="modal-actions">
        <button class="btn-primary" onclick={handleClose}>Done</button>
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
    width: 550px;
    max-width: calc(100% - 32px);
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
    overflow-y: auto;
  }
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }
  .modal-title {
    margin: 0;
    font-size: 18px;
  }
  .close-btn {
    background: none;
    border: none;
    font-size: 22px;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }
  .close-btn:hover { color: var(--text-color); }

  .loading-msg {
    color: var(--text-muted);
    font-size: 13px;
    text-align: center;
    padding: 1rem 0;
  }
  .discrepancy-desc {
    margin: 0 0 8px 0;
    font-size: 13px;
    color: var(--text-muted);
  }
  .bulk-actions {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
  }
  .btn-adjust, .btn-cancel {
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    border: 1px solid var(--border-color);
  }
  .btn-adjust {
    background: var(--warning-bg);
    color: var(--warning-color);
    border-color: var(--warning-color);
  }
  .btn-adjust:hover:not(:disabled) { opacity: 0.85; }
  .btn-cancel {
    background: var(--error-bg);
    color: var(--error-color);
    border-color: var(--error-color);
  }
  .btn-cancel:hover:not(:disabled) { opacity: 0.85; }
  .btn-adjust:disabled, .btn-cancel:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .discrepancy-table {
    max-height: 350px;
    overflow-y: auto;
  }
  .discrepancy-table table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  .discrepancy-table th {
    text-align: left;
    padding: 4px 8px;
    border-bottom: 1px solid var(--border-color);
    font-weight: 500;
    color: var(--text-muted);
    font-size: 11px;
  }
  .discrepancy-table td {
    padding: 4px 8px;
    border-bottom: 1px solid var(--border-color);
  }
  .disc-name {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .disc-deficit {
    color: var(--error-color);
    font-weight: 600;
  }
  .disc-actions {
    display: flex;
    gap: 4px;
  }
  .disc-btn {
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 11px;
    cursor: pointer;
    border: 1px solid var(--border-color);
    background: transparent;
    color: var(--text-color);
  }
  .disc-btn.adjust {
    color: var(--warning-color);
    border-color: var(--warning-color);
  }
  .disc-btn.cancel {
    color: var(--error-color);
    border-color: var(--error-color);
  }
  .disc-btn:hover { opacity: 0.8; }

  .coverage-ok {
    margin: 8px 0;
    padding: 0.75rem 1rem;
    background: var(--success-bg);
    border-radius: 4px;
    color: var(--success-color);
    font-size: 13px;
    text-align: center;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 12px;
  }
  .btn-primary {
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    border: 1px solid var(--accent-color);
    background: var(--accent-color);
    color: white;
  }
  .btn-primary:hover { opacity: 0.9; }
</style>
