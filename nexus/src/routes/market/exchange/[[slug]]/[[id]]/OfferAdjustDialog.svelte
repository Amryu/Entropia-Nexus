<script>
  //@ts-nocheck
  import { createEventDispatcher, onMount } from 'svelte';
  import { myOffers, inventory } from '../../exchangeStore.js';

  export let show = false;

  const dispatch = createEventDispatcher();

  let discrepancies = [];
  let adjustingAll = false;
  let cancellingAll = false;
  let loading = false;

  $: if (show) computeDiscrepancies();

  async function computeDiscrepancies() {
    loading = true;

    // Ensure offers are loaded
    let offers = $myOffers;
    if (!offers || offers.length === 0) {
      try {
        const res = await fetch('/api/market/exchange/offers');
        if (res.ok) {
          offers = await res.json();
          myOffers.set(offers);
        }
      } catch {}
    }

    // Only check SELL offers
    const sellOffers = (offers || []).filter(o => o.type === 'SELL');
    if (sellOffers.length === 0) {
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

    discrepancies = sellOffers
      .map(offer => {
        const invQty = invQtyMap.get(offer.item_id) || 0;
        if (offer.quantity > invQty) {
          return {
            offer,
            offerQty: offer.quantity,
            invQty,
            deficit: offer.quantity - invQty,
            item_name: offer.details?.item_name || `Item #${offer.item_id}`,
            _processing: false,
          };
        }
        return null;
      })
      .filter(Boolean);

    loading = false;
  }

  async function adjustOffer(disc) {
    disc._processing = true;
    discrepancies = discrepancies;
    try {
      const newQty = disc.invQty;
      if (newQty <= 0) {
        await cancelOffer(disc);
        return;
      }
      const res = await fetch(`/api/market/exchange/offers/${disc.offer.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quantity: newQty,
          markup: disc.offer.markup,
          planet: disc.offer.planet,
          min_quantity: disc.offer.min_quantity ? Math.min(disc.offer.min_quantity, newQty) : null,
          details: disc.offer.details,
        }),
      });
      if (!res.ok) throw new Error('Failed to adjust offer');
      discrepancies = discrepancies.filter(d => d !== disc);
      refreshOffers();
    } catch (e) {
      disc._processing = false;
      discrepancies = discrepancies;
    }
  }

  async function cancelOffer(disc) {
    disc._processing = true;
    discrepancies = discrepancies;
    try {
      const res = await fetch(`/api/market/exchange/offers/${disc.offer.id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to cancel offer');
      discrepancies = discrepancies.filter(d => d !== disc);
      refreshOffers();
    } catch (e) {
      disc._processing = false;
      discrepancies = discrepancies;
    }
  }

  async function adjustAll() {
    adjustingAll = true;
    const toProcess = [...discrepancies];
    for (const disc of toProcess) {
      await adjustOffer(disc);
    }
    adjustingAll = false;
  }

  async function cancelAll() {
    cancellingAll = true;
    const toProcess = [...discrepancies];
    for (const disc of toProcess) {
      await cancelOffer(disc);
    }
    cancellingAll = false;
  }

  async function refreshOffers() {
    try {
      const res = await fetch('/api/market/exchange/offers');
      if (res.ok) myOffers.set(await res.json());
    } catch {}
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
</script>

{#if show}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="modal-overlay" on:click|self={handleClose}>
    <div class="modal">
      <div class="modal-header">
        <h3 class="modal-title">Offer Coverage</h3>
        <button class="close-btn" on:click={handleClose}>&times;</button>
      </div>

      {#if loading}
        <p class="loading-msg">Checking offers against inventory...</p>
      {:else if discrepancies.length > 0}
        <p class="discrepancy-desc">
          These sell offers advertise more items than you currently have in inventory.
        </p>
        <div class="bulk-actions">
          <button
            class="btn-adjust"
            on:click={adjustAll}
            disabled={adjustingAll || cancellingAll}
          >{adjustingAll ? 'Adjusting...' : 'Adjust All'}</button>
          <button
            class="btn-cancel"
            on:click={cancelAll}
            disabled={adjustingAll || cancellingAll}
          >{cancellingAll ? 'Cancelling...' : 'Cancel All'}</button>
        </div>
        <div class="discrepancy-table">
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th>Offer</th>
                <th>Inventory</th>
                <th>Deficit</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each discrepancies as disc}
                <tr>
                  <td class="disc-name">{disc.item_name}</td>
                  <td>{disc.offerQty}</td>
                  <td>{disc.invQty}</td>
                  <td class="disc-deficit">-{disc.deficit}</td>
                  <td class="disc-actions">
                    {#if disc._processing}
                      <span class="processing">...</span>
                    {:else}
                      <button class="disc-btn adjust" on:click={() => adjustOffer(disc)}
                        title={disc.invQty > 0 ? `Set to ${disc.invQty}` : 'Cancel (no inventory)'}>
                        {disc.invQty > 0 ? 'Adjust' : 'Cancel'}
                      </button>
                      {#if disc.invQty > 0}
                        <button class="disc-btn cancel" on:click={() => cancelOffer(disc)}>Cancel</button>
                      {/if}
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <div class="coverage-ok">All sell offers are covered by your inventory.</div>
      {/if}

      <div class="modal-actions">
        <button class="btn-primary" on:click={handleClose}>Done</button>
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
