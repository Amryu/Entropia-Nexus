<!--
  @component Auction Create Page
  Form to create a new auction. Creates as draft, then can activate.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { goto, beforeNavigate } from '$app/navigation';
  import { onDestroy } from 'svelte';
  import { apiPost, apiPut, apiDelete, hasItemTag, getTypeLink } from '$lib/util';
  import ItemSetDialog from '$lib/components/itemsets/ItemSetDialog.svelte';
  import AuctionDurationSelector from '$lib/components/auction/AuctionDurationSelector.svelte';
  import FeePreview from '$lib/components/auction/FeePreview.svelte';
  import ExchangeRedirectWarning from '$lib/components/auction/ExchangeRedirectWarning.svelte';
  import AuctionDisclaimerDialog from '$lib/components/auction/AuctionDisclaimerDialog.svelte';
  import { addToast } from '$lib/stores/toasts';

  const MAX_IMAGE_SIZE = 2 * 1024 * 1024; // 2MB

  let { data } = $props();

  let loadouts = $derived(data.loadouts || []);
  let disclaimerStatus = $derived(data.disclaimerStatus || {});

  // Form state
  let title = $state('');
  let description = $state('');
  let startingBid = $state('');
  let buyoutPrice = $state('');
  let buyoutOnly = $state(false);
  let durationDays = $state(7);
  let customized = $state(false);

  let itemSet = $state(null);
  let showItemSetDialog = $state(false);
  let showDisclaimer = $state(false);
  let saving = $state(false);
  let removingItemSet = $state(false);

  // Custom image upload
  let customImagePreview = $state(null);
  let uploadingImage = $state(false);

  // Track whether the auction was saved so we don't orphan the item set
  let auctionSaved = false;

  // Clean up orphaned item set when leaving the page without saving
  function cleanupOrphanedItemSet() {
    if (itemSet && !auctionSaved) {
      // Fire-and-forget delete — can't await during navigation/unload
      apiDelete(fetch, `/api/itemsets/${itemSet.id}`).catch(() => {});
    }
  }

  beforeNavigate(() => {
    cleanupOrphanedItemSet();
  });

  onDestroy(() => {
    cleanupOrphanedItemSet();
  });

  let startingBidNum = $derived(parseFloat(startingBid) || 0);
  let buyoutPriceNum = $derived(buyoutOnly ? startingBidNum : (parseFloat(buyoutPrice) || 0));
  let effectiveBuyout = $derived(buyoutOnly ? startingBidNum : (buyoutPriceNum > 0 ? buyoutPriceNum : null));

  // Check if any item in the set has a (C) tag
  let hasCustomizableItems = $derived(itemSet?.items?.some(item =>
    item.setName
      ? item.pieces?.some(p => hasItemTag(p.name, 'C'))
      : hasItemTag(item.name, 'C')
  ) ?? false);

  // Reset customized if no (C) items
  $effect(() => {
    if (!hasCustomizableItems) customized = false;
  });

  // Exchange redirect warning
  let singleNonCustomItem = $derived(!customized && itemSet && itemSet.items?.length === 1);
  let firstItemId = $derived(itemSet?.items?.[0]?.id || null);

  function handleItemSetCreated(e) {
    const result = e.detail;
    itemSet = {
      id: result.id,
      items: result.data?.items || [],
      name: result.name
    };
    addToast('Item set created', { type: 'success' });
  }

  async function removeItemSet() {
    if (!itemSet || removingItemSet) return;
    removingItemSet = true;
    try {
      const result = await apiDelete(fetch, `/api/itemsets/${itemSet.id}`);
      if (result?.error) {
        addToast(result.error, { type: 'error' });
        return;
      }
      itemSet = null;
      if (customImagePreview) URL.revokeObjectURL(customImagePreview);
      customImagePreview = null;
    } catch {
      addToast('Failed to remove item set', { type: 'error' });
    } finally {
      removingItemSet = false;
    }
  }

  function removeCustomImage() {
    if (customImagePreview) {
      URL.revokeObjectURL(customImagePreview);
      customImagePreview = null;
    }
  }

  async function handleImageUpload(e) {
    const file = e.target.files?.[0];
    if (!file || !itemSet) return;

    if (file.size > MAX_IMAGE_SIZE) {
      addToast('Image must be under 2MB', { type: 'warning' });
      return;
    }

    if (!file.type.startsWith('image/')) {
      addToast('Please select an image file', { type: 'warning' });
      return;
    }

    uploadingImage = true;
    try {
      const formData = new FormData();
      formData.append('image', file);
      formData.append('entityType', 'item-set');
      formData.append('entityId', itemSet.id);

      const res = await fetch('/api/uploads/entity-image', { method: 'POST', body: formData });
      const result = await res.json();

      if (!res.ok || result.error) {
        addToast(result.error || 'Upload failed', { type: 'error' });
        return;
      }

      customImagePreview = URL.createObjectURL(file);
      addToast('Image uploaded', { type: 'success' });
    } catch {
      addToast('Failed to upload image', { type: 'error' });
    } finally {
      uploadingImage = false;
    }
  }

  function handleDurationChange(value) {
    durationDays = value;
  }

  async function handleSave(activate = false) {
    // Check disclaimer
    if (!disclaimerStatus.seller) {
      showDisclaimer = true;
      return;
    }

    if (!title.trim()) {
      addToast('Title is required', { type: 'warning' });
      return;
    }
    if (!itemSet) {
      addToast('Please create an item set first', { type: 'warning' });
      return;
    }
    if (startingBidNum <= 0) {
      addToast('Starting bid must be greater than 0', { type: 'warning' });
      return;
    }

    saving = true;
    try {
      // Persist customized flag on item set
      if (customized) {
        const updateResult = await apiPut(fetch, `/api/itemsets/${itemSet.id}`, { customized: true });
        if (updateResult?.error) {
          addToast(updateResult.error, { type: 'error' });
          return;
        }
      }

      // Create auction
      const body = {
        title: title.trim(),
        description: description || null,
        starting_bid: startingBidNum,
        buyout_price: effectiveBuyout,
        duration_days: durationDays,
        item_set_id: itemSet.id
      };

      const result = await apiPost(fetch, '/api/auction', body);
      if (result?.error) {
        addToast(result.error, { type: 'error' });
        return;
      }
      auctionSaved = true;

      if (activate) {
        // Activate immediately
        const activateResult = await apiPut(fetch, `/api/auction/${result.id}`, {
          action: 'activate'
        });
        if (activateResult?.error) {
          addToast(`Draft created, but activation failed: ${activateResult.error}`, { type: 'warning' });
          goto(`/market/auction/${result.id}`);
          return;
        }
        addToast('Auction created and activated!', { type: 'success' });
      } else {
        addToast('Auction draft saved', { type: 'success' });
      }

      goto(`/market/auction/${result.id}`);
    } catch (err) {
      addToast('Failed to create auction', { type: 'error' });
    } finally {
      saving = false;
    }
  }

  function handleDisclaimerAccepted() {
    disclaimerStatus = { ...disclaimerStatus, seller: true };
    showDisclaimer = false;
  }
</script>

<svelte:head>
  <title>Create Auction - Market - Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/market">Market</a>
      <span>/</span>
      <a href="/market/auction">Auctions</a>
      <span>/</span>
      <span>Create</span>
    </div>

    <h1>Create Auction</h1>

    <!-- Item Set Section -->
    <section class="form-section">
      <h2>Item Set</h2>
      {#if itemSet}
        <div class="item-set-preview">
          <ul class="set-item-list">
            {#each (itemSet.items || []) as item}
              {#if item.setName}
                {@const setHref = getTypeLink(item.setName, item.setType)}
                <li class="set-item-entry set-entry">
                  {#if setHref}
                    <a href={setHref} class="item-link">{item.setName}</a>
                  {:else}
                    <span class="item-name">{item.setName}</span>
                  {/if}
                  <span class="item-detail">{item.setType === 'ArmorSet' ? 'Armor' : 'Clothing'} set — {item.pieces?.length || 0} pieces</span>
                </li>
              {:else}
                {@const itemHref = getTypeLink(item.name, item.type)}
                <li class="set-item-entry">
                  {#if itemHref}
                    <a href={itemHref} class="item-link">{item.name}</a>
                  {:else}
                    <span class="item-name">{item.name}</span>
                  {/if}
                  {#if item.quantity > 1}
                    <span class="item-detail">x{item.quantity}</span>
                  {/if}
                </li>
              {/if}
            {/each}
          </ul>
          <div class="set-actions">
            <label class="checkbox-label" class:disabled={!hasCustomizableItems}>
              <input type="checkbox" bind:checked={customized} disabled={!hasCustomizableItems} />
              <span>Customized (C) — items have custom modifications</span>
            </label>
            <button class="btn-danger-sm" onclick={removeItemSet} disabled={removingItemSet}>
              Remove
            </button>
          </div>
          {#if customized}
            <div class="custom-image-upload">
              <label class="upload-label">Custom Image (optional)</label>
              {#if customImagePreview}
                <div class="image-preview-row">
                  <img src={customImagePreview} alt="Custom item preview" class="image-preview" />
                  <button class="btn-danger-sm" onclick={removeCustomImage}>Remove</button>
                </div>
              {:else}
                <label class="upload-area" class:uploading={uploadingImage}>
                  <input type="file" accept="image/*" onchange={handleImageUpload} disabled={uploadingImage} />
                  {#if uploadingImage}
                    <span>Uploading...</span>
                  {:else}
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                    <span>Upload a screenshot of your customized item(s)</span>
                  {/if}
                </label>
              {/if}
            </div>
          {/if}
        </div>
      {:else}
        <button class="btn-secondary" onclick={() => showItemSetDialog = true}>
          Create Item Set
        </button>
      {/if}
    </section>

    <!-- Exchange Redirect Warning -->
    <ExchangeRedirectWarning visible={singleNonCustomItem} itemId={firstItemId} />

    <!-- Pricing Section -->
    <section class="form-section">
      <h2>Pricing</h2>
      <div class="form-row">
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
      </div>

      <div class="form-row">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={buyoutOnly} />
          <span>Buyout Only (no bidding, direct purchase)</span>
        </label>
      </div>

      {#if !buyoutOnly}
        <div class="form-row">
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
        </div>
      {/if}

      <!-- Fee temporarily hidden
      <FeePreview amount={startingBidNum} />
      -->
    </section>

    <!-- Duration Section -->
    <section class="form-section">
      <h2>Duration</h2>
      <AuctionDurationSelector
        bind:value={durationDays}
        buyoutPrice={effectiveBuyout}
        startingBid={startingBidNum}
        onchange={handleDurationChange}
      />
    </section>

    <!-- Title & Description -->
    <section class="form-section">
      <h2>Details</h2>
      <div class="form-group">
        <label for="auction-title">Title</label>
        <input
          id="auction-title"
          type="text"
          bind:value={title}
          maxlength="120"
          placeholder="Auction title..."
        />
      </div>
      <div class="form-group">
        <label>Description (optional)</label>
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
      <button class="btn-secondary" onclick={() => goto('/market/auction')} disabled={saving}>
        Cancel
      </button>
      <button class="btn-secondary" onclick={() => handleSave(false)} disabled={saving || !itemSet}>
        {saving ? 'Saving...' : 'Save Draft'}
      </button>
      <button class="btn-primary" onclick={() => handleSave(true)} disabled={saving || !itemSet}>
        {saving ? 'Creating...' : 'Create & Activate'}
      </button>
    </div>
  </div>
</div>

<ItemSetDialog
  bind:show={showItemSetDialog}
  hideName
  onsave={handleItemSetCreated}
/>

<AuctionDisclaimerDialog
  bind:open={showDisclaimer}
  role="seller"
  onaccepted={() => handleDisclaimerAccepted()}
/>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 1rem;
    padding-bottom: 2rem;
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

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

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

  .form-row {
    margin-bottom: 0.75rem;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
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

  .form-group textarea {
    resize: vertical;
    font-family: inherit;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 0.85rem;
    color: var(--text-color);
  }

  .checkbox-label.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Item Set Preview */
  .item-set-preview {
    padding: 0.75rem;
    background: var(--hover-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
  }

  .set-item-list {
    list-style: none;
    margin: 0 0 0.5rem 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .set-item-entry {
    display: flex;
    align-items: baseline;
    gap: 6px;
    font-size: 0.85rem;
    color: var(--text-color);
  }

  .set-item-entry .item-name {
    font-weight: 500;
  }

  .set-item-entry .item-link {
    font-weight: 500;
    color: var(--accent-color);
    text-decoration: none;
  }

  .set-item-entry .item-link:hover {
    text-decoration: underline;
  }

  .set-item-entry .item-detail {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .set-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .btn-danger-sm {
    padding: 4px 10px;
    font-size: 0.8rem;
    background: var(--error-bg);
    color: var(--error-color);
    border: 1px solid var(--error-color);
    border-radius: 4px;
    cursor: pointer;
  }

  .btn-danger-sm:hover:not(:disabled) { background: var(--error-color); color: white; }
  .btn-danger-sm:disabled { opacity: 0.7; cursor: not-allowed; }

  /* Custom image upload */
  .custom-image-upload {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--border-color);
  }

  .upload-label {
    display: block;
    font-size: 0.85rem;
    color: var(--text-muted);
    font-weight: 500;
    margin-bottom: 0.5rem;
  }

  .upload-area {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 1rem;
    border: 2px dashed var(--border-color);
    border-radius: 6px;
    cursor: pointer;
    color: var(--text-muted);
    font-size: 0.85rem;
    transition: border-color 0.15s, background-color 0.15s;
  }

  .upload-area:hover {
    border-color: var(--accent-color);
    background: var(--hover-color);
  }

  .upload-area.uploading {
    opacity: 0.7;
    cursor: wait;
  }

  .upload-area input[type="file"] {
    display: none;
  }

  .image-preview-row {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .image-preview {
    max-width: 160px;
    max-height: 160px;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    object-fit: contain;
    background: var(--bg-color);
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  .btn-primary, .btn-secondary {
    padding: 0.5rem 1rem;
    font-size: 0.9rem;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-primary {
    background: var(--accent-color);
    border: 1px solid var(--accent-color);
    color: white;
  }

  .btn-primary:hover:not(:disabled) { background: var(--accent-color-hover); }

  .btn-secondary {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .btn-secondary:hover:not(:disabled) { background: var(--hover-color); }

  .btn-primary:disabled, .btn-secondary:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }

  @media (max-width: 899px) {
    .page-container { padding: 1rem; padding-bottom: 2rem; }
    .form-actions { flex-direction: column; }
    .form-actions .btn-primary,
    .form-actions .btn-secondary { width: 100%; text-align: center; justify-content: center; }
  }
</style>
