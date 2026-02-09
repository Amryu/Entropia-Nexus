<script>
  //@ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { tradeList } from '../../exchangeStore.js';
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  /** @type {{ id: number|string, name: string } | null} */
  export let user = null;

  let offers = [];
  let loading = false;
  let error = null;
  export let sideFilter = 'all'; // 'all' | 'BUY' | 'SELL'

  $: if (user?.id) loadOffers(user.id);

  $: filteredOffers = sideFilter === 'all'
    ? offers
    : offers.filter(o => o.type === sideFilter);

  // Set of offer IDs already in the trade list
  $: tradeListOfferIds = new Set($tradeList.map(i => i.offerId));

  async function loadOffers(userId) {
    loading = true;
    error = null;
    offers = [];
    try {
      const res = await fetch(`/api/market/exchange/offers/user/${userId}`);
      if (!res.ok) throw new Error('Failed to load offers');
      offers = await res.json();
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  export function refresh() {
    if (user?.id) loadOffers(user.id);
  }

  let columns = [
    {
      key: 'details', header: 'Item', main: true, sortable: true, searchable: false,
      formatter: (v) => v?.item_name || 'Unknown'
    },
    {
      key: 'type', header: 'Side', width: '60px', sortable: true, searchable: false,
      formatter: (v) => {
        const cls = v === 'BUY' ? 'badge-success' : 'badge-error';
        return `<span class="badge badge-subtle ${cls}">${v === 'BUY' ? 'Buy' : 'Sell'}</span>`;
      }
    },
    { key: 'quantity', header: 'Qty', width: '60px', sortable: true, searchable: false },
    {
      key: 'markup', header: 'Markup', width: '80px', sortable: true, searchable: false,
      formatter: (v) => v != null ? Number(v).toFixed(1) : 'N/A'
    },
    { key: 'planet', header: 'Planet', width: '90px', sortable: true, searchable: false },
    {
      key: '_action', header: '', width: '60px', sortable: false, searchable: false,
      formatter: (v, row) => {
        const offerId = row?.id ?? 0;
        const inList = tradeListOfferIds.has(offerId);
        if (inList) {
          return `<span class="cell-badge added-badge">Added</span>`;
        }
        const side = row?.type === 'SELL' ? 'buy' : 'sell';
        const label = side === 'buy' ? 'Buy' : 'Sell';
        const cls = side === 'buy' ? 'buy-offer-btn' : 'sell-offer-btn';
        return `<button class="cell-button ${cls}" data-offer-action="${offerId}" data-action-side="${side}">${label}</button>`;
      }
    }
  ];

  // Rebuild columns reactively when tradeListOfferIds changes
  $: {
    tradeListOfferIds;
    columns = columns;
  }

  function handleClick(e) {
    const btn = e.target.closest('[data-offer-action]');
    if (!btn) return;
    e.stopPropagation();
    e.preventDefault();

    const offerId = parseInt(btn.dataset.offerAction, 10);
    const side = btn.dataset.actionSide;
    const offer = offers.find(o => o.id === offerId);
    if (!offer) return;

    dispatch('offerAction', {
      offerId: offer.id,
      itemId: offer.item_id,
      itemName: offer.details?.item_name || 'Unknown',
      sellerId: user?.id,
      sellerName: offer.seller_name || user?.name || 'Unknown',
      planet: offer.planet || '',
      quantity: offer.quantity || 1,
      unitPrice: Number(offer.markup) || 0,
      markup: Number(offer.markup) || 0,
      side: offer.type || 'SELL',
      offer,
    });
  }

</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="user-offers-panel" on:click|capture={handleClick}>

  {#if loading}
    <div class="panel-loading">Loading offers...</div>
  {:else if error}
    <div class="panel-error">{error}</div>
  {:else if filteredOffers.length === 0}
    <div class="panel-empty">{offers.length === 0 ? 'No active offers' : 'No matching offers'}</div>
  {:else}
    <FancyTable
      {columns}
      data={filteredOffers}
      rowHeight={30}
      compact={true}
      sortable={true}
      searchable={false}
      emptyMessage="No offers"
    />
  {/if}
</div>

<style>
  .user-offers-panel {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .panel-loading, .panel-error, .panel-empty {
    padding: 24px;
    text-align: center;
    font-size: 13px;
    color: var(--text-muted);
  }
  .panel-error {
    color: var(--error-color, #ef4444);
  }
  .user-offers-panel :global(.buy-offer-btn) {
    color: var(--success-color, #16a34a);
    border-color: var(--success-color, #16a34a);
    font-size: 10px;
  }
  .user-offers-panel :global(.buy-offer-btn:hover) {
    background: rgba(22, 163, 74, 0.15);
  }
  .user-offers-panel :global(.sell-offer-btn) {
    color: var(--error-color, #ef4444);
    border-color: var(--error-color, #ef4444);
    font-size: 10px;
  }
  .user-offers-panel :global(.sell-offer-btn:hover) {
    background: rgba(239, 68, 68, 0.15);
  }
  .user-offers-panel :global(.added-badge) {
    font-size: 10px;
    color: var(--text-muted);
    font-style: italic;
  }
</style>
