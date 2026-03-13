<!--
  @component Rental Request Detail
  View details and manage a rental request. Works for both requester and offer owner.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { goto, invalidateAll } from '$app/navigation';
  import { apiPut } from '$lib/util';
  import RentalStatusBadge from '$lib/components/rental/RentalStatusBadge.svelte';
  import { formatPrice, formatDateDisplay } from '$lib/utils/rentalPricing.js';
  import { addToast } from '$lib/stores/toasts';

  let { data } = $props();

  let req = $derived(data.request);
  let user = $derived(data.session?.user);
  let isOwner = $derived(user && req && (String(user.id) === String(req.offer_owner_id) || user.grants?.includes('admin.panel')));
  let isRequester = $derived(user && req && String(user.id) === String(req.requester_id));
  let extensions = $derived(req?.extensions || []);

  // Action permissions
  let canCancel = $derived(isRequester && req?.status === 'open');
  let canAccept = $derived(isOwner && req?.status === 'open');
  let canReject = $derived(isOwner && req?.status === 'open');
  let canStart = $derived(isOwner && req?.status === 'accepted');
  let canComplete = $derived(isOwner && req?.status === 'in_progress');
  let hasActions = $derived(canCancel || canAccept || canReject || canStart || canComplete);

  let actionLoading = $state(false);
  let actionError = $state('');

  async function updateStatus(newStatus, confirmMsg) {
    if (confirmMsg && !confirm(confirmMsg)) return;

    actionLoading = true;
    actionError = '';

    try {
      const result = await apiPut(fetch, `/api/rental/requests/${req.id}`, { status: newStatus });
      if (result?.error) {
        actionError = result.error;
        return;
      }
      const labels = {
        accepted: 'accepted', rejected: 'rejected', in_progress: 'started',
        completed: 'completed', cancelled: 'cancelled'
      };
      addToast(`Request ${labels[newStatus] || 'updated'}.`, { type: 'success' });
      await invalidateAll();
    } catch {
      actionError = 'Failed to update request.';
    } finally {
      actionLoading = false;
    }
  }

  function formatDateTime(dateStr) {
    if (!dateStr) return '\u2014';
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return '\u2014';
    return d.toLocaleString();
  }
</script>

<svelte:head>
  <title>Request #{req?.id} - Rentals - Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/market">Market</a>
      <span>/</span>
      <a href="/market/rental">Item Rentals</a>
      <span>/</span>
      <a href="/market/rental/my">My Rentals</a>
      <span>/</span>
      <span>Request #{req?.id}</span>
    </div>

    <button class="back-btn" onclick={() => goto('/market/rental/my')}>
      &larr; Back to My Rentals
    </button>

    <div class="header-row">
      <h1>{req.offer_title || 'Rental Request'}</h1>
      <RentalStatusBadge status={req.status} type="request" size="large" />
    </div>

    {#if actionError}
      <div class="error-banner">{actionError}</div>
    {/if}

    <div class="content-grid">
      <!-- Main Column -->
      <div class="main-content">
        <!-- Rental Period -->
        <div class="card">
          <h2>Rental Period</h2>
          <div class="detail-rows">
            <div class="detail-row">
              <span class="detail-label">Start Date</span>
              <span class="detail-value">{formatDateDisplay(req.start_date)}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">End Date</span>
              <span class="detail-value">{formatDateDisplay(req.end_date)}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">Duration</span>
              <span class="detail-value">{req.total_days} day{req.total_days !== 1 ? 's' : ''}</span>
            </div>
            {#if req.actual_return_date}
              <div class="detail-row">
                <span class="detail-label">Actual Return</span>
                <span class="detail-value">{formatDateDisplay(req.actual_return_date)}</span>
              </div>
            {/if}
            <div class="detail-row">
              <span class="detail-label">Requested</span>
              <span class="detail-value">{formatDateTime(req.created_at)}</span>
            </div>
          </div>
        </div>

        <!-- Pricing -->
        <div class="card">
          <h2>Pricing</h2>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Price / Day</span>
              <span class="info-value">{formatPrice(req.price_per_day)}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Discount</span>
              <span class="info-value">{Number(req.discount_pct) > 0 ? `-${req.discount_pct}%` : 'None'}</span>
            </div>
            <div class="info-item highlight">
              <span class="info-label">Total Price</span>
              <span class="info-value">{formatPrice(req.total_price)}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Deposit</span>
              <span class="info-value">{formatPrice(req.deposit || req.offer_deposit)}</span>
            </div>
          </div>
        </div>

        <!-- Notes -->
        {#if req.requester_note || req.owner_note}
          <div class="card">
            <h2>Notes</h2>
            {#if req.requester_note}
              <div class="note-section">
                <span class="note-label">Requester Note</span>
                <p class="note-text">{req.requester_note}</p>
              </div>
            {/if}
            {#if req.owner_note}
              <div class="note-section">
                <span class="note-label">Owner Note</span>
                <p class="note-text">{req.owner_note}</p>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Extensions -->
        {#if extensions.length > 0}
          <div class="card">
            <h2>Extensions</h2>
            <div class="extensions-list">
              {#each extensions as ext}
                <div class="extension-item">
                  <div class="extension-dates">
                    {formatDateDisplay(ext.previous_end)} &rarr; {formatDateDisplay(ext.new_end)}
                    <span class="extension-days">(+{ext.extra_days} day{ext.extra_days !== 1 ? 's' : ''})</span>
                  </div>
                  <div class="extension-meta">
                    <span>+{formatPrice(ext.extra_price)}</span>
                    {#if ext.retroactive}
                      <span class="retroactive-badge">Retroactive</span>
                    {/if}
                  </div>
                  {#if ext.note}
                    <div class="extension-note">{ext.note}</div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>

      <!-- Sidebar -->
      <div class="sidebar">
        <!-- Offer -->
        <div class="card">
          <h3>Offer</h3>
          <div class="sidebar-info">
            <span class="sidebar-title">{req.offer_title}</span>
            <a href="/market/rental/{req.offer_id}" class="sidebar-link">View Offer</a>
          </div>
        </div>

        <!-- Contact -->
        <div class="card">
          <h3>Contact</h3>
          {#if isRequester}
            <div class="contact-info">
              <span class="contact-label">Owner</span>
              <span class="contact-name">{req.owner_name || '\u2014'}</span>
              {#if req.owner_username}
                <span class="contact-discord">Discord: {req.owner_username}</span>
              {/if}
            </div>
          {:else}
            <div class="contact-info">
              <span class="contact-label">Requester</span>
              <span class="contact-name">{req.requester_name || '\u2014'}</span>
              {#if req.requester_username}
                <span class="contact-discord">Discord: {req.requester_username}</span>
              {/if}
            </div>
          {/if}
        </div>

        <!-- Actions -->
        {#if hasActions}
          <div class="card">
            <h3>Actions</h3>
            <div class="action-buttons">
              {#if canAccept}
                <button
                  class="btn-publish"
                  disabled={actionLoading}
                  onclick={() => updateStatus('accepted', 'Accept this rental request?')}
                >
                  Accept
                </button>
              {/if}
              {#if canReject}
                <button
                  class="btn-delete"
                  disabled={actionLoading}
                  onclick={() => updateStatus('rejected', 'Reject this rental request?')}
                >
                  Reject
                </button>
              {/if}
              {#if canStart}
                <button
                  class="btn-primary"
                  disabled={actionLoading}
                  onclick={() => updateStatus('in_progress', 'Mark this rental as started? This means the item has been handed over.')}
                >
                  Start Rental
                </button>
              {/if}
              {#if canComplete}
                <button
                  class="btn-primary"
                  disabled={actionLoading}
                  onclick={() => updateStatus('completed', 'Mark this rental as completed? This means the item has been returned.')}
                >
                  Mark Complete
                </button>
              {/if}
              {#if canCancel}
                <button
                  class="btn-delete"
                  disabled={actionLoading}
                  onclick={() => updateStatus('cancelled', 'Cancel this rental request?')}
                >
                  Cancel Request
                </button>
              {/if}
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    max-width: 1000px;
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

  .header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .header-row h1 {
    margin: 0;
    font-size: 1.5rem;
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    border: 1px solid var(--error-color);
    margin-bottom: 1rem;
  }

  .content-grid {
    display: grid;
    grid-template-columns: 1fr 280px;
    gap: 1.5rem;
  }

  .card {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1rem;
  }

  .card h2 {
    margin: 0 0 1rem 0;
    font-size: 1.1rem;
    font-weight: 600;
  }

  .card h3 {
    margin: 0 0 0.75rem 0;
    font-size: 0.95rem;
  }

  /* Detail rows (timeline-style) */
  .detail-rows {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .detail-row {
    display: flex;
    gap: 0.5rem;
    font-size: 0.95rem;
  }

  .detail-label {
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .detail-value {
    font-weight: 500;
  }

  /* Pricing grid */
  .info-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
  }

  .info-item {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .info-item.highlight .info-value {
    color: var(--success-color);
    font-weight: 600;
    font-size: 1.1rem;
  }

  .info-label {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .info-value {
    font-weight: 500;
  }

  /* Notes */
  .note-section {
    margin-bottom: 0.75rem;
  }

  .note-section:last-child {
    margin-bottom: 0;
  }

  .note-label {
    font-size: 0.85rem;
    color: var(--text-muted);
    display: block;
    margin-bottom: 0.25rem;
  }

  .note-text {
    margin: 0;
    line-height: 1.5;
  }

  /* Extensions */
  .extensions-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .extension-item {
    padding: 0.75rem;
    background: var(--hover-color);
    border-radius: 4px;
  }

  .extension-dates {
    font-weight: 500;
    font-size: 0.9rem;
    margin-bottom: 0.25rem;
  }

  .extension-days {
    color: var(--text-muted);
    font-weight: 400;
  }

  .extension-meta {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .retroactive-badge {
    padding: 0.125rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--accent-color);
    background-color: var(--hover-color);
    border: 1px solid var(--accent-color);
  }

  .extension-note {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
    font-style: italic;
  }

  /* Sidebar */
  .sidebar-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .sidebar-title {
    font-weight: 500;
  }

  .sidebar-link {
    color: var(--accent-color);
    text-decoration: none;
    font-size: 0.9rem;
    margin-top: 0.25rem;
  }

  .sidebar-link:hover {
    text-decoration: underline;
  }

  /* Contact */
  .contact-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .contact-label {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .contact-name {
    font-weight: 500;
  }

  .contact-discord {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  /* Actions */
  .action-buttons {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .action-buttons button {
    padding: 0.5rem 1rem;
    border-radius: 4px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    width: 100%;
  }

  .action-buttons button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-primary {
    background: var(--accent-color);
    color: white;
    border: none;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--accent-color-hover);
  }

  .btn-publish {
    background: var(--success-color);
    color: white;
    border: none;
  }

  .btn-publish:hover:not(:disabled) {
    background: var(--button-success-hover);
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

  @media (max-width: 768px) {
    .content-grid {
      grid-template-columns: 1fr;
    }

    .info-grid {
      grid-template-columns: 1fr;
    }

    .header-row {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
