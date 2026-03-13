<!--
  @component Auction Edit Page
  Edit a draft auction's pricing, duration, title, description.
  Can also activate the auction from here.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { goto } from '$app/navigation';
  import AuctionDurationSelector from '$lib/components/auction/AuctionDurationSelector.svelte';
  import FeePreview from '$lib/components/auction/FeePreview.svelte';
  import ItemSetDisplay from '$lib/components/itemsets/ItemSetDisplay.svelte';
  import { addToast } from '$lib/stores/toasts';

  let { data } = $props();

  let auction = $derived(data.auction);

  // Form state - re-sync when auction data changes (e.g. navigation)
  let title = $state('');
  let description = $state('');
  let startingBid = $state('');
  let buyoutPrice = $state('');
  let buyoutOnly = $state(false);
  let durationDays = $state(7);

  $effect(() => {
    const a = auction;
    title = a?.title || '';
    description = a?.description || '';
    startingBid = a?.starting_bid ? String(parseFloat(a.starting_bid)) : '';
    buyoutPrice = a?.buyout_price ? String(parseFloat(a.buyout_price)) : '';
    buyoutOnly = a?.buyout_price != null && parseFloat(a.buyout_price) === parseFloat(a.starting_bid);
    durationDays = a?.duration_days || 7;
  });

  let saving = $state(false);

  let startingBidNum = $derived(parseFloat(startingBid) || 0);
  let buyoutPriceNum = $derived(buyoutOnly ? startingBidNum : (parseFloat(buyoutPrice) || 0));
  let effectiveBuyout = $derived(buyoutOnly ? startingBidNum : (buyoutPriceNum > 0 ? buyoutPriceNum : null));

  async function handleSave(activate = false) {
    if (!title.trim()) {
      addToast('Title is required', { type: 'warning' });
      return;
    }
    if (startingBidNum <= 0) {
      addToast('Starting bid must be greater than 0', { type: 'warning' });
      return;
    }

    saving = true;
    try {
      const body = activate
        ? { action: 'activate' }
        : {
            title: title.trim(),
            description: description || null,
            starting_bid: startingBidNum,
            buyout_price: effectiveBuyout,
            duration_days: durationDays,
            item_set_id: auction.item_set_id
          };

      const res = await fetch(`/api/auction/${auction.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const result = await res.json();

      if (!res.ok) {
        addToast(result.error || 'Failed to save', { type: 'error' });
        return;
      }

      addToast(activate ? 'Auction activated!' : 'Changes saved', { type: 'success' });
      goto(`/market/auction/${auction.id}`);
    } catch {
      addToast('Failed to save auction', { type: 'error' });
    } finally {
      saving = false;
    }
  }

  let showDeleteConfirm = $state(false);
  let showActivateConfirm = $state(false);

  async function handleDelete() {
    showDeleteConfirm = true;
  }

  async function doDelete() {
    showDeleteConfirm = false;
    saving = true;
    try {
      const res = await fetch(`/api/auction/${auction.id}`, { method: 'DELETE' });
      const result = await res.json();
      if (!res.ok) {
        addToast(result.error || 'Failed to delete', { type: 'error' });
        return;
      }
      addToast('Draft deleted', { type: 'success' });
      goto('/market/auction/my');
    } catch {
      addToast('Failed to delete', { type: 'error' });
    } finally {
      saving = false;
    }
  }
</script>

<svelte:head>
  <title>Edit Auction - Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/market">Market</a>
      <span>/</span>
      <a href="/market/auction">Auctions</a>
      <span>/</span>
      <a href="/market/auction/{auction?.id}">Details</a>
      <span>/</span>
      <span>Edit</span>
    </div>

    <h1>Edit Draft Auction</h1>

    <!-- Item Set (read-only here) -->
    <section class="form-section">
      <h2>Items</h2>
      <ItemSetDisplay
        itemSet={{ data: auction?.item_set_data }}
        showHeader={false}
        linkItems
      />
    </section>

    <!-- Pricing -->
    <section class="form-section">
      <h2>Pricing</h2>
      <div class="form-group">
        <label for="starting-bid">Starting Bid (PED)</label>
        <input
          id="starting-bid"
          type="number"
          bind:value={startingBid}
          min="0.01"
          step="0.01"
          placeholder="0.00"
        />
      </div>

      <div class="form-row">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={buyoutOnly} />
          <span>Buyout Only</span>
        </label>
      </div>

      {#if !buyoutOnly}
        <div class="form-group">
          <label for="buyout-price">Buyout Price (PED, optional)</label>
          <input
            id="buyout-price"
            type="number"
            bind:value={buyoutPrice}
            min={startingBid || '0.01'}
            step="0.01"
            placeholder="Optional"
          />
        </div>
      {/if}

      <!-- Fee temporarily hidden
      <FeePreview amount={startingBidNum} />
      -->
    </section>

    <!-- Duration -->
    <section class="form-section">
      <h2>Duration</h2>
      <AuctionDurationSelector
        bind:value={durationDays}
        buyoutPrice={effectiveBuyout}
        startingBid={startingBidNum}
      />
    </section>

    <!-- Title & Description -->
    <section class="form-section">
      <h2>Details</h2>
      <div class="form-group">
        <label for="auction-title">Title</label>
        <input id="auction-title" type="text" bind:value={title} maxlength="120" />
      </div>
      <div class="form-group">
        <span class="form-label">Description</span>
        {#await import('$lib/components/wiki/RichTextEditor.svelte') then { default: RichTextEditor }}
          <RichTextEditor
            content={description}
            placeholder="Describe your item(s)..."
            showHeadings={false}
            showCodeBlock={false}
            showVideo={false}
            showImages={false}
            onchange={(data) => description = data}
          />
        {/await}
      </div>
    </section>

    <!-- Actions -->
    <div class="form-actions">
      <button class="btn-danger" onclick={handleDelete} disabled={saving}>Delete Draft</button>
      <div class="actions-right">
        <button class="btn-secondary" onclick={() => goto(`/market/auction/${auction.id}`)} disabled={saving}>
          Cancel
        </button>
        <button class="btn-secondary" onclick={() => handleSave(false)} disabled={saving}>
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
        <button class="btn-primary" onclick={() => showActivateConfirm = true} disabled={saving}>
          {saving ? 'Activating...' : 'Activate Auction'}
        </button>
      </div>
    </div>

    {#if showDeleteConfirm}
      <div class="modal-overlay" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) showDeleteConfirm = false; }}>
        <div class="confirm-dialog" role="dialog" aria-modal="true">
          <p class="confirm-message">Delete this draft auction?</p>
          <div class="confirm-actions">
            <button class="btn-secondary" onclick={() => showDeleteConfirm = false}>Cancel</button>
            <button class="btn-danger" onclick={doDelete}>Delete</button>
          </div>
        </div>
      </div>
    {/if}

    {#if showActivateConfirm}
      <div class="modal-overlay" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) showActivateConfirm = false; }}>
        <div class="confirm-dialog" role="dialog" aria-modal="true">
          <p class="confirm-message">Are you sure you want to activate this auction?</p>
          <p class="confirm-warning">Once a bid is placed, the auction cannot be cancelled or edited. Make sure your pricing, duration, and item set are correct before proceeding.</p>
          <div class="confirm-actions">
            <button class="btn-secondary" onclick={() => showActivateConfirm = false}>Cancel</button>
            <button class="btn-primary" onclick={() => { showActivateConfirm = false; handleSave(true); }}>Activate Auction</button>
          </div>
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .page-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 1rem;
    padding-bottom: 2rem;
  }

  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
  }

  .breadcrumb a { color: var(--accent-color); text-decoration: none; }
  .breadcrumb a:hover { text-decoration: underline; }

  h1 {
    margin: 0 0 1.5rem 0;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-color);
  }

  .form-section {
    margin-bottom: 1.5rem;
    padding: 1.25rem;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }

  .form-section h2 {
    margin: 0 0 1rem 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    margin-bottom: 0.75rem;
  }

  .form-group label,
  .form-group .form-label {
    font-size: 0.85rem;
    color: var(--text-muted);
    font-weight: 500;
  }

  .form-group input {
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border-color);
    background: var(--bg-color);
    color: var(--text-color);
    border-radius: 6px;
    font-size: 0.9rem;
    box-sizing: border-box;
  }

  .form-group input:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .form-row { margin-bottom: 0.75rem; }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 0.85rem;
    color: var(--text-color);
  }

  .form-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  .actions-right {
    display: flex;
    gap: 0.5rem;
  }

  .btn-primary, .btn-secondary, .btn-danger {
    padding: 0.5rem 1rem;
    font-size: 0.9rem;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-primary { background: var(--accent-color); border: 1px solid var(--accent-color); color: white; }
  .btn-primary:hover:not(:disabled) { background: var(--accent-color-hover); }

  .btn-secondary { background: transparent; border: 1px solid var(--border-color); color: var(--text-color); }
  .btn-secondary:hover:not(:disabled) { background: var(--hover-color); }

  .btn-danger { background: var(--error-bg); border: 1px solid var(--error-color); color: var(--error-color); }
  .btn-danger:hover:not(:disabled) { background: var(--error-color); color: white; }

  .btn-primary:disabled, .btn-secondary:disabled, .btn-danger:disabled { opacity: 0.7; cursor: not-allowed; }

  /* Confirmation dialog */
  .modal-overlay {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 3;
  }

  .confirm-dialog {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    width: 420px;
    max-width: calc(100% - 32px);
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }

  .confirm-message { margin: 0 0 0.5rem 0; font-size: 0.9rem; line-height: 1.5; }
  .confirm-warning { margin: 0 0 1rem 0; font-size: 0.8rem; line-height: 1.5; color: var(--text-muted); }
  .confirm-actions { display: flex; gap: 8px; justify-content: flex-end; }

  @media (max-width: 899px) {
    .page-container { padding: 1rem; padding-bottom: 2rem; }
    .form-actions { flex-direction: column; }
    .actions-right { flex-direction: column; width: 100%; }
    .actions-right button { width: 100%; text-align: center; justify-content: center; }
  }
</style>
