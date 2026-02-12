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
  import { addToast } from '$lib/stores/toasts';

  export let data;

  $: auction = data.auction;

  // Form state (initialized from auction data)
  let title = auction?.title || '';
  let description = auction?.description || '';
  let startingBid = auction?.starting_bid ? String(parseFloat(auction.starting_bid)) : '';
  let buyoutPrice = auction?.buyout_price ? String(parseFloat(auction.buyout_price)) : '';
  let buyoutOnly = auction?.buyout_price != null && parseFloat(auction.buyout_price) === parseFloat(auction.starting_bid);
  let durationDays = auction?.duration_days || 7;

  let saving = false;

  $: startingBidNum = parseFloat(startingBid) || 0;
  $: buyoutPriceNum = buyoutOnly ? startingBidNum : (parseFloat(buyoutPrice) || 0);
  $: effectiveBuyout = buyoutOnly ? startingBidNum : (buyoutPriceNum > 0 ? buyoutPriceNum : null);

  $: items = auction?.item_set_data?.items || [];

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
            description: description.trim() || null,
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

  let showDeleteConfirm = false;

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
      <h2>Item Set</h2>
      <div class="item-set-preview">
        <span class="set-name">{auction?.item_set_name || 'Unnamed Set'}</span>
        <span class="set-count">{items.length} item{items.length !== 1 ? 's' : ''}</span>
        <div class="set-items">
          {#each items.slice(0, 8) as item}
            <div class="set-item-thumb">
              {#if item.id}
                <img src="/api/img/item/{item.id}" alt={item.name || ''} loading="lazy" />
              {/if}
            </div>
          {/each}
        </div>
      </div>
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

      <FeePreview amount={startingBidNum} />
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
        <label for="auction-desc">Description</label>
        <textarea id="auction-desc" bind:value={description} maxlength="2000" rows="4"></textarea>
      </div>
    </section>

    <!-- Actions -->
    <div class="form-actions">
      <button class="btn-danger" on:click={handleDelete} disabled={saving}>Delete Draft</button>
      <div class="actions-right">
        <button class="btn-secondary" on:click={() => goto(`/market/auction/${auction.id}`)} disabled={saving}>
          Cancel
        </button>
        <button class="btn-secondary" on:click={() => handleSave(false)} disabled={saving}>
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
        <button class="btn-primary" on:click={() => handleSave(true)} disabled={saving}>
          {saving ? 'Activating...' : 'Activate Auction'}
        </button>
      </div>
    </div>

    {#if showDeleteConfirm}
      <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
      <div class="modal-overlay" on:click|self={() => showDeleteConfirm = false}>
        <div class="confirm-dialog" role="dialog" aria-modal="true">
          <p class="confirm-message">Delete this draft auction?</p>
          <div class="confirm-actions">
            <button class="btn-secondary" on:click={() => showDeleteConfirm = false}>Cancel</button>
            <button class="btn-danger" on:click={doDelete}>Delete</button>
          </div>
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .page-container {
    max-width: 700px;
    margin: 0 auto;
    padding: 1.5rem;
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

  .form-group label {
    font-size: 0.85rem;
    color: var(--text-muted);
    font-weight: 500;
  }

  .form-group input,
  .form-group textarea {
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border-color);
    background: var(--bg-color);
    color: var(--text-color);
    border-radius: 6px;
    font-size: 0.9rem;
    box-sizing: border-box;
  }

  .form-group input:focus,
  .form-group textarea:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .form-group textarea { resize: vertical; font-family: inherit; }

  .form-row { margin-bottom: 0.75rem; }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 0.85rem;
    color: var(--text-color);
  }

  .item-set-preview {
    padding: 0.75rem;
    background: var(--hover-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
  }

  .set-name { font-weight: 600; font-size: 0.9rem; }
  .set-count { font-size: 0.8rem; color: var(--text-muted); margin-left: 0.5rem; }

  .set-items {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 0.5rem;
  }

  .set-item-thumb {
    width: 48px;
    height: 48px;
    border-radius: 4px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    overflow: hidden;
  }

  .set-item-thumb img { width: 100%; height: 100%; object-fit: cover; }

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

  .confirm-message { margin: 0 0 1rem 0; font-size: 0.9rem; line-height: 1.5; }
  .confirm-actions { display: flex; gap: 8px; justify-content: flex-end; }

  @media (max-width: 899px) {
    .page-container { padding: 1rem; }
    .form-actions { flex-direction: column; }
    .actions-right { flex-direction: column; width: 100%; }
    .actions-right button { width: 100%; text-align: center; justify-content: center; }
  }
</style>
