<!--
  @component Rental Edit Page
  Edit an existing rental offer. Includes status controls, blocked dates, and requests.
-->
<script>
  // @ts-nocheck
  import { untrack } from 'svelte';
  import '$lib/style.css';
  import { goto, invalidateAll } from '$app/navigation';
  import { apiPut } from '$lib/util';
  import RentalStatusBadge from '$lib/components/rental/RentalStatusBadge.svelte';
  import RentalPricingEditor from '$lib/components/rental/RentalPricingEditor.svelte';
  import BlockedDatesEditor from '$lib/components/rental/BlockedDatesEditor.svelte';
  import ItemSetDisplay from '$lib/components/itemsets/ItemSetDisplay.svelte';
  import { formatPrice, formatDateDisplay } from '$lib/utils/rentalPricing.js';
  import { addToast } from '$lib/stores/toasts';

  let { data } = $props();

  let offer = $derived(data.offer);
  let planets = $derived(data.planets || []);
  let blockedDates = $derived(data.blockedDates || []);
  let requests = $derived(data.requests || []);
  let isNew = $derived(data.isNew);

  let saving = $state(false);
  let error = $state('');
  let statusChanging = $state(false);

  // Form state initialized from offer
  let title = $state('');
  let description = $state('');
  let planetId = $state('');
  let location = $state('');
  let pricePerDay = $state(0);
  let discounts = $state([]);
  let deposit = $state(0);
  let initialized = $state(false);

  $effect(() => {
    if (offer && !untrack(() => initialized)) {
      title = offer.title || '';
      description = offer.description || '';
      planetId = offer.planet_id ? String(offer.planet_id) : '';
      location = offer.location || '';
      pricePerDay = Number(offer.price_per_day) || 0;
      discounts = offer.discounts || [];
      deposit = Number(offer.deposit) || 0;
      initialized = true;
    }
  });

  let canPublish = $derived(offer?.status === 'draft' || offer?.status === 'unlisted');
  let canUnpublish = $derived(offer?.status === 'available');
  let canDelete = $derived(offer?.status !== 'deleted');
  let activeRequests = $derived(requests.filter(r => ['open', 'accepted', 'in_progress'].includes(r.status)));
  let canEditFields = $derived(offer?.status === 'draft');

  function handlePricingChange(data) {
    pricePerDay = data.pricePerDay;
    discounts = data.discounts;
    deposit = data.deposit;
  }

  async function handleSave() {
    if (!title.trim()) {
      error = 'Title is required.';
      return;
    }
    if (pricePerDay <= 0) {
      error = 'Price per day must be greater than 0.';
      return;
    }

    error = '';
    saving = true;

    try {
      const result = await apiPut(fetch, `/api/rental/${offer.id}`, {
        title: title.trim(),
        description: description || null,
        planet_id: planetId ? parseInt(planetId) : null,
        location: location.trim() || null,
        price_per_day: pricePerDay,
        discounts,
        deposit
      });

      if (result?.error) {
        error = result.error;
        return;
      }

      addToast('Offer updated.', { type: 'success' });
      await invalidateAll();
    } catch (err) {
      error = 'Failed to update offer.';
    } finally {
      saving = false;
    }
  }

  async function handleStatusChange(newStatus) {
    statusChanging = true;
    error = '';

    try {
      const result = await apiPut(fetch, `/api/rental/${offer.id}`, { status: newStatus });

      if (result?.error) {
        error = result.error;
        return;
      }

      const labels = { available: 'published', unlisted: 'unlisted', draft: 'set to draft', deleted: 'deleted' };
      addToast(`Offer ${labels[newStatus] || 'updated'}.`, { type: 'success' });

      if (newStatus === 'deleted') {
        goto('/market/rental/my');
      } else {
        await invalidateAll();
        // Re-initialize form from updated offer
        initialized = false;
      }
    } catch (err) {
      error = 'Failed to update status.';
    } finally {
      statusChanging = false;
    }
  }

</script>

<svelte:head>
  <title>Edit {offer?.title || 'Offer'} - Market - Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/market">Market</a>
      <span>/</span>
      <a href="/market/rental">Item Rentals</a>
      <span>/</span>
      <a href="/market/rental/{offer?.id}">Offer</a>
      <span>/</span>
      <span>Edit</span>
    </div>

    <button class="back-btn" onclick={() => goto('/market/rental/my')}>
      &larr; Back to My Rentals
    </button>

    {#if isNew}
      <div class="new-banner">
        Your offer has been created as a <strong>draft</strong>. Configure pricing, blocked dates, and publish when ready.
      </div>
    {/if}

    {#if !offer}
      <div class="error-state">
        <h2>Offer not found</h2>
        <p>This offer may have been deleted or you don't have access.</p>
      </div>
    {:else}
      <div class="edit-header">
        <h1>Edit Offer</h1>
        <RentalStatusBadge status={offer.status} type="offer" size="large" />
      </div>

      {#if error}
        <div class="error-banner">{error}</div>
      {/if}

      <!-- Status Controls -->
      <div class="status-controls">
        {#if canPublish}
          <button class="btn-publish" onclick={() => handleStatusChange('available')} disabled={statusChanging}>
            Publish
          </button>
        {/if}
        {#if canUnpublish}
          <button class="btn-secondary" onclick={() => handleStatusChange('unlisted')} disabled={statusChanging}>
            Unpublish
          </button>
        {/if}
        {#if offer.status === 'available' && activeRequests.length === 0}
          <button class="btn-secondary" onclick={() => handleStatusChange('draft')} disabled={statusChanging}>
            Back to Draft
          </button>
        {/if}
        {#if canDelete && activeRequests.length === 0}
          <button class="btn-delete" onclick={() => { if (confirm('Are you sure you want to delete this offer? This cannot be undone.')) handleStatusChange('deleted'); }} disabled={statusChanging}>
            Delete Offer
          </button>
        {/if}
      </div>

      <form onsubmit={(e) => { e.preventDefault(); handleSave(e); }} class="edit-form">
        <!-- Item Set (read-only since linked) -->
        {#if offer.item_set}
          <div class="form-section">
            <h2>Linked Item Set</h2>
            <ItemSetDisplay itemSet={offer.item_set} />
            <small class="link-note">Item set is locked while linked to this offer.</small>
          </div>
        {/if}

        <!-- Basic Info -->
        <div class="form-section">
          <h2>Basic Info</h2>

          <div class="form-group">
            <label for="title">Title *</label>
            <input type="text" id="title" bind:value={title} maxlength="120" disabled={!canEditFields} />
          </div>

          <div class="form-group">
            <label>Description</label>
            {#await import('$lib/components/wiki/RichTextEditor.svelte') then { default: RichTextEditor }}
              <RichTextEditor
                content={description}
                placeholder="Describe the rental terms, conditions, etc."
                showHeadings={false}
                showCodeBlock={false}
                showVideo={false}
                showImages={false}
                disabled={!canEditFields}
                onchange={(data) => description = data}
              />
            {/await}
          </div>
        </div>

        <!-- Location -->
        <div class="form-section">
          <h2>Location</h2>

          <div class="form-group">
            <label for="planet">Planet</label>
            <select id="planet" bind:value={planetId} disabled={!canEditFields}>
              <option value="">— Any Planet —</option>
              {#each planets as planet}
                <option value={planet.Id}>{planet.Name}</option>
              {/each}
            </select>
          </div>

          <div class="form-group">
            <label for="location">Pickup/Return Location</label>
            <input type="text" id="location" bind:value={location} maxlength="200" disabled={!canEditFields} />
          </div>
        </div>

        <!-- Pricing -->
        <div class="form-section">
          <h2>Pricing</h2>
          {#if canEditFields}
            <RentalPricingEditor
              {pricePerDay}
              {discounts}
              {deposit}
              onchange={handlePricingChange}
            />
          {:else}
            <div class="read-only-pricing">
              <div class="detail-row">
                <span class="detail-label">Price per Day:</span>
                <span class="detail-value">{formatPrice(pricePerDay)}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Deposit:</span>
                <span class="detail-value">{formatPrice(deposit)}</span>
              </div>
              {#if discounts.length > 0}
                <div class="detail-row">
                  <span class="detail-label">Discounts:</span>
                  <span class="detail-value">
                    {discounts.map(d => `${d.percent}% off ${d.minDays}+ days`).join(', ')}
                  </span>
                </div>
              {/if}
              <small class="edit-note">Pricing can only be edited in draft status.</small>
            </div>
          {/if}
        </div>

        {#if canEditFields}
          <div class="form-actions">
            <button type="submit" class="save-btn" disabled={saving}>
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        {/if}
      </form>

      <!-- Blocked Dates -->
      <div class="form-section">
        <h2>Blocked Dates</h2>
        <BlockedDatesEditor
          offerId={offer.id}
          {blockedDates}
        />
      </div>

      <!-- Incoming Requests -->
      <div class="form-section">
        <h2>Requests ({requests.length})</h2>
        {#if requests.length === 0}
          <p class="empty-text">No rental requests yet.</p>
        {:else}
          <div class="requests-list">
            {#each requests as req}
              <div class="request-card">
                <div class="request-info">
                  <div class="request-header">
                    <span class="requester">{req.requester_name || 'Unknown'}</span>
                    <RentalStatusBadge status={req.status} type="request" size="small" />
                  </div>
                  <div class="request-dates">
                    {formatDateDisplay(req.start_date)} &ndash; {formatDateDisplay(req.end_date)}
                    <span class="request-days">({req.total_days} day{req.total_days !== 1 ? 's' : ''})</span>
                  </div>
                  <div class="request-price">
                    Total: {formatPrice(req.total_price)}
                    {#if Number(req.discount_pct) > 0}
                      <span class="discount-tag">-{req.discount_pct}%</span>
                    {/if}
                  </div>
                </div>
                <a href="/market/rental/requests/{req.id}" class="request-link">
                  View &rarr;
                </a>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>

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
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .back-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
    cursor: pointer;
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .back-btn:hover {
    background: var(--hover-color);
    border-color: var(--border-hover);
  }

  .new-banner {
    background: var(--success-bg);
    color: var(--success-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    border: 1px solid var(--success-color);
    margin-bottom: 1rem;
    font-size: 0.9rem;
  }

  .error-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted);
  }

  .edit-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .edit-header h1 {
    margin: 0;
    font-size: 1.75rem;
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    border: 1px solid var(--error-color);
    margin-bottom: 1rem;
  }

  .status-controls {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
  }

  .status-controls button {
    padding: 0.5rem 1rem;
    border-radius: 4px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
  }

  .status-controls button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-publish {
    background: var(--success-color);
    color: white;
    border: none;
  }

  .btn-publish:hover:not(:disabled) {
    background: var(--button-success-hover);
  }

  .btn-secondary {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .btn-secondary:hover:not(:disabled) {
    background: var(--hover-color);
  }

  .btn-delete {
    background: var(--error-bg);
    color: var(--error-color);
    border: 1px solid var(--error-color);
  }

  .btn-delete:hover:not(:disabled) {
    background: var(--error-color);
    color: white;
  }

  .edit-form {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    margin-bottom: 1.5rem;
  }

  .form-section {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1.5rem;
  }

  .edit-form .form-section {
    margin-bottom: 0;
  }

  .form-section h2 {
    margin: 0 0 1rem;
    font-size: 1.1rem;
    font-weight: 600;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-group:last-child {
    margin-bottom: 0;
  }

  .form-group label {
    display: block;
    font-weight: 500;
    font-size: 0.9rem;
    color: var(--text-color);
    margin-bottom: 0.25rem;
  }

  .form-group input,
  .form-group select,
  .form-group textarea {
    width: 100%;
    padding: 0.5rem;
    background: var(--primary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.9rem;
    box-sizing: border-box;
    font-family: inherit;
  }

  .form-group textarea {
    resize: vertical;
  }

  .form-group input:focus,
  .form-group select:focus,
  .form-group textarea:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .form-group input:disabled,
  .form-group select:disabled,
  .form-group textarea:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .link-note, .edit-note {
    display: block;
    margin-top: 0.5rem;
    color: var(--text-muted);
    font-size: 0.8rem;
  }

  .read-only-pricing {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .detail-row {
    display: flex;
    gap: 0.5rem;
    font-size: 0.95rem;
  }

  .detail-label {
    color: var(--text-muted);
  }

  .detail-value {
    font-weight: 500;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
  }

  .save-btn {
    padding: 0.5rem 1.25rem;
    background: var(--accent-color);
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
  }

  .save-btn:hover:not(:disabled) {
    background: var(--accent-color-hover);
  }

  .save-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .empty-text {
    color: var(--text-muted);
    font-size: 0.9rem;
    margin: 0;
  }

  .requests-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .request-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    gap: 1rem;
  }

  .request-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    min-width: 0;
  }

  .request-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .requester {
    font-weight: 500;
    font-size: 0.95rem;
  }

  .request-dates {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .request-days {
    font-size: 0.8rem;
  }

  .request-price {
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .discount-tag {
    background: var(--success-bg);
    color: var(--success-color);
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .request-link {
    color: var(--accent-color);
    text-decoration: none;
    font-size: 0.9rem;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .request-link:hover {
    text-decoration: underline;
  }

  @media (max-width: 768px) {
    .status-controls {
      flex-direction: column;
    }

    .status-controls button {
      width: 100%;
    }

    .request-card {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
