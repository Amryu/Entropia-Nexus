<!--
  @component Auction Detail Page
  Shows auction info, pricing, bid section, bid history, item set, and admin controls.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { invalidateAll } from '$app/navigation';
  import { addToast } from '$lib/stores/toasts.js';
  import AuctionStatusBadge from '$lib/components/auction/AuctionStatusBadge.svelte';
  import AuctionPricePanel from '$lib/components/auction/AuctionPricePanel.svelte';
  import BidSection from '$lib/components/auction/BidSection.svelte';
  import BidHistoryPanel from '$lib/components/auction/BidHistoryPanel.svelte';
  import AuctionDisclaimerDialog from '$lib/components/auction/AuctionDisclaimerDialog.svelte';
  import ItemSetDisplay from '$lib/components/itemsets/ItemSetDisplay.svelte';
  import { getTypeLink } from '$lib/util.js';
  import { globalIdToEntityId } from '$lib/common/itemTypes.js';
  import { sanitizeMarketHtml, containsHtml } from '$lib/sanitize.js';

  const MAX_GRID_ITEMS = 10;

  export let data;

  let customImageVisible = true;

  $: auction = data.auction;
  $: bids = auction?.bids || [];
  $: user = data.session?.user;
  $: isAdmin = user?.grants?.includes('admin.panel') || user?.administrator;
  $: isSeller = user && String(user.id) === String(auction?.seller_id);
  $: disclaimerStatus = data.disclaimerStatus || {};
  $: auditLog = data.auditLog || [];
  $: turnstileSiteKey = data.turnstileSiteKey || '';

  $: items = auction?.item_set_data?.items || [];
  $: isActive = auction?.status === 'active';
  $: isFrozen = auction?.status === 'frozen';
  $: isEnded = auction?.status === 'ended';

  let showDisclaimer = false;
  let disclaimerRole = 'bidder';
  let adminReason = '';
  let adminSubmitting = false;
  let showAuditLog = false;

  // Confirmation state (replaces native confirm())
  let confirmAction = null;
  let confirmMessage = '';

  function requestConfirm(message, action) {
    confirmMessage = message;
    confirmAction = action;
  }

  function handleConfirmYes() {
    const action = confirmAction;
    confirmAction = null;
    confirmMessage = '';
    if (action) action();
  }

  function handleConfirmNo() {
    confirmAction = null;
    confirmMessage = '';
  }

  function handleNeedDisclaimer() {
    disclaimerRole = 'bidder';
    showDisclaimer = true;
  }

  async function handleDisclaimerAccepted() {
    showDisclaimer = false;
    disclaimerStatus = { ...disclaimerStatus, [disclaimerRole]: true };
  }

  async function handleBidOrBuyout() {
    await invalidateAll();
  }

  // Settle auction
  async function handleSettle() {
    try {
      const res = await fetch(`/api/auction/${auction.id}/settle`, { method: 'POST' });
      const result = await res.json();
      if (!res.ok) {
        addToast(result.error || 'Failed to settle', { type: 'error' });
        return;
      }
      addToast('Auction settled successfully', { type: 'success' });
      await invalidateAll();
    } catch {
      addToast('Failed to settle auction', { type: 'error' });
    }
  }

  // Cancel auction (owner, active with no bids)
  $: canCancel = isSeller && auction?.status === 'active' && (auction?.bid_count || 0) === 0;

  function handleCancel() {
    requestConfirm('Cancel this auction? This cannot be undone.', async () => {
      try {
        const res = await fetch(`/api/auction/${auction.id}`, { method: 'DELETE' });
        const result = await res.json();
        if (!res.ok) {
          addToast(result.error || 'Failed to cancel', { type: 'error' });
          return;
        }
        addToast('Auction cancelled', { type: 'success' });
        await invalidateAll();
      } catch {
        addToast('Failed to cancel auction', { type: 'error' });
      }
    });
  }

  // Admin: freeze/unfreeze
  async function handleFreeze() {
    if (!adminReason.trim()) {
      addToast('Reason is required', { type: 'warning' });
      return;
    }
    adminSubmitting = true;
    try {
      const res = await fetch(`/api/auction/${auction.id}/admin/freeze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: adminReason })
      });
      const result = await res.json();
      if (!res.ok) {
        addToast(result.error || 'Failed', { type: 'error' });
        return;
      }
      addToast(auction.status === 'frozen' ? 'Auction unfrozen' : 'Auction frozen', { type: 'success' });
      adminReason = '';
      await invalidateAll();
    } catch {
      addToast('Failed', { type: 'error' });
    } finally {
      adminSubmitting = false;
    }
  }

  // Admin: cancel
  async function handleAdminCancel() {
    if (!adminReason.trim()) {
      addToast('Reason is required', { type: 'warning' });
      return;
    }
    requestConfirm('Are you sure you want to cancel this auction? This cannot be undone.', doAdminCancel);
  }

  async function doAdminCancel() {
    adminSubmitting = true;
    try {
      const res = await fetch(`/api/auction/${auction.id}/admin/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: adminReason })
      });
      const result = await res.json();
      if (!res.ok) {
        addToast(result.error || 'Failed to cancel', { type: 'error' });
        return;
      }
      addToast('Auction cancelled by admin', { type: 'success' });
      adminReason = '';
      await invalidateAll();
    } catch {
      addToast('Failed to cancel', { type: 'error' });
    } finally {
      adminSubmitting = false;
    }
  }

  // Admin: rollback
  let pendingRollback = null;

  async function handleRollback(e) {
    const { bidId, amount } = e.detail;
    if (!adminReason.trim()) {
      addToast('Enter a reason in the admin panel below', { type: 'warning' });
      return;
    }
    pendingRollback = { bidId, amount };
    requestConfirm(`Rollback all bids after ${parseFloat(amount).toFixed(2)} PED? This cannot be undone.`, doRollback);
  }

  async function doRollback() {
    const { bidId } = pendingRollback;
    pendingRollback = null;
    adminSubmitting = true;
    try {
      const res = await fetch(`/api/auction/${auction.id}/admin/rollback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_bid_id: bidId, reason: adminReason })
      });
      const result = await res.json();
      if (!res.ok) {
        addToast(result.error || 'Rollback failed', { type: 'error' });
        return;
      }
      addToast('Bids rolled back', { type: 'success' });
      adminReason = '';
      await invalidateAll();
    } catch {
      addToast('Rollback failed', { type: 'error' });
    } finally {
      adminSubmitting = false;
    }
  }

  async function handleRollbackAll() {
    if (!adminReason.trim()) {
      addToast('Reason is required', { type: 'warning' });
      return;
    }
    requestConfirm('Rollback ALL bids? This cannot be undone.', doRollbackAll);
  }

  async function doRollbackAll() {
    adminSubmitting = true;
    try {
      const res = await fetch(`/api/auction/${auction.id}/admin/rollback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_bid_id: null, reason: adminReason })
      });
      const result = await res.json();
      if (!res.ok) {
        addToast(result.error || 'Rollback failed', { type: 'error' });
        return;
      }
      addToast('All bids rolled back', { type: 'success' });
      adminReason = '';
      await invalidateAll();
    } catch {
      addToast('Rollback failed', { type: 'error' });
    } finally {
      adminSubmitting = false;
    }
  }
</script>

<svelte:head>
  <title>{auction?.title || 'Auction'} - Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/market">Market</a>
      <span>/</span>
      <a href="/market/auction">Auctions</a>
      <span>/</span>
      <span>{auction?.title || 'Details'}</span>
    </div>

    {#if !auction}
      <div class="empty-state">Auction not found</div>
    {:else}
      <div class="auction-header">
        <div class="header-info">
          <h1>{auction.title}</h1>
          <div class="header-meta">
            <AuctionStatusBadge status={auction.status} />
            <span class="seller">by {auction.seller_name || 'Unknown'}</span>
            {#if auction.item_set_customized}
              <span class="customized-tag">Customized</span>
            {/if}
          </div>
        </div>
        {#if isSeller && (auction.status === 'draft' || canCancel)}
          <div class="header-actions">
            {#if auction.status === 'draft'}
              <a href="/market/auction/{auction.id}/edit" class="btn-secondary">Edit</a>
            {/if}
            {#if canCancel}
              <button class="btn-danger" on:click={handleCancel}>Cancel Auction</button>
            {/if}
          </div>
        {/if}
      </div>

      <div class="auction-layout">
        <div class="auction-main">
          <!-- Price Panel + Bid Section -->
          <div class="auction-panels">
            <AuctionPricePanel {auction} />
            <BidSection
              {auction}
              {turnstileSiteKey}
              disclaimerAccepted={disclaimerStatus?.bidder || false}
              {isSeller}
              on:bid={handleBidOrBuyout}
              on:buyout={handleBidOrBuyout}
              on:needDisclaimer={handleNeedDisclaimer}
            />
          </div>

          <!-- Seller actions -->
          {#if isSeller && isEnded}
            <div class="seller-actions">
              <button class="btn-primary" on:click={handleSettle}>Settle Auction</button>
              <span class="settle-hint">Confirm the trade is complete</span>
            </div>
          {/if}

          <!-- Description -->
          {#if auction.description}
            <div class="section">
              <h2 class="section-title">Description</h2>
              {#if containsHtml(auction.description)}
                <div class="description description-content">{@html sanitizeMarketHtml(auction.description)}</div>
              {:else}
                <p class="description">{auction.description}</p>
              {/if}
            </div>
          {/if}

          <!-- Item Set -->
          <div class="section">
            <h2 class="section-title">Items</h2>
            {#if auction.item_set_customized}
              <div class="custom-image-float">
                {#if customImageVisible}
                  <img
                    src="/api/img/item-set/{auction.item_set_id}"
                    alt="Customized item preview"
                    class="custom-image"
                    loading="lazy"
                    on:error={() => customImageVisible = false}
                  />
                {:else}
                  <div class="custom-image-placeholder">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                      <rect x="3" y="3" width="18" height="18" rx="2" />
                      <circle cx="8.5" cy="8.5" r="1.5" />
                      <path d="M21 15l-5-5L5 21" />
                    </svg>
                    <span>No custom image uploaded</span>
                  </div>
                {/if}
              </div>
            {/if}
            {#if items.length === 0}
              <p class="muted">No items in set</p>
            {:else if items.length <= MAX_GRID_ITEMS}
              <div class="item-grid">
                {#each items as item}
                  {@const href = item.setType ? getTypeLink(item.setName, item.setType) : getTypeLink(item.name, item.type)}
                  <a href={href} class="item-card" class:no-link={!href}>
                    <div class="item-image">
                      {#if item.itemId && item.type && globalIdToEntityId(item.itemId, item.type) != null}
                        <img src="/api/img/{item.type.toLowerCase()}/{globalIdToEntityId(item.itemId, item.type)}" alt={item.name || ''} loading="lazy" />
                      {:else}
                        <svg class="item-placeholder" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                          <rect x="3" y="3" width="18" height="18" rx="2" />
                          <circle cx="8.5" cy="8.5" r="1.5" />
                          <path d="M21 15l-5-5L5 21" />
                        </svg>
                      {/if}
                    </div>
                    <div class="item-info">
                      <span class="item-name">{item.setName || item.name || 'Unknown Item'}</span>
                      {#if item.quantity > 1}
                        <span class="item-qty">x{item.quantity}</span>
                      {/if}
                    </div>
                  </a>
                {/each}
              </div>
            {:else}
              <ItemSetDisplay
                itemSet={{ data: auction.item_set_data }}
                showHeader={false}
                linkItems
              />
            {/if}
          </div>

          <!-- Bid History -->
          <BidHistoryPanel {bids} {isAdmin} on:rollback={handleRollback} />
        </div>
      </div>

      <!-- Admin Controls -->
      {#if isAdmin}
        <div class="admin-panel">
          <h2 class="section-title">Admin Controls</h2>
          <div class="admin-reason">
            <label for="admin-reason">Reason (required for actions)</label>
            <input
              id="admin-reason"
              type="text"
              bind:value={adminReason}
              placeholder="Enter reason..."
              class="reason-input"
            />
          </div>
          <div class="admin-actions">
            {#if isActive || isFrozen}
              <button
                class="btn-warning"
                on:click={handleFreeze}
                disabled={adminSubmitting}
              >
                {isFrozen ? 'Unfreeze' : 'Freeze'}
              </button>
            {/if}
            {#if auction.status !== 'settled' && auction.status !== 'cancelled'}
              <button
                class="btn-danger"
                on:click={handleAdminCancel}
                disabled={adminSubmitting}
              >
                Force Cancel
              </button>
            {/if}
            {#if auction.bid_count > 0}
              <button
                class="btn-danger"
                on:click={handleRollbackAll}
                disabled={adminSubmitting}
              >
                Rollback All Bids
              </button>
            {/if}
          </div>

          <!-- Audit Log -->
          <div class="audit-section">
            <button class="btn-secondary audit-toggle" on:click={() => showAuditLog = !showAuditLog}>
              {showAuditLog ? 'Hide' : 'Show'} Audit Log ({auditLog.length} entries)
            </button>
            {#if showAuditLog}
              <div class="audit-log">
                {#each auditLog as entry}
                  <div class="audit-entry">
                    <span class="audit-action">{entry.action}</span>
                    <span class="audit-user">{entry.user_name || 'System'}</span>
                    <span class="audit-time">{new Date(entry.created_at).toLocaleString()}</span>
                    {#if entry.details}
                      <pre class="audit-details">{JSON.stringify(entry.details, null, 2)}</pre>
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <AuctionDisclaimerDialog
        bind:open={showDisclaimer}
        role={disclaimerRole}
        on:accepted={handleDisclaimerAccepted}
      />

      <!-- Confirmation dialog (replaces native confirm()) -->
      {#if confirmAction}
        <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
        <div class="modal-overlay" on:click|self={handleConfirmNo}>
          <div class="confirm-dialog" role="dialog" aria-modal="true">
            <p class="confirm-message">{confirmMessage}</p>
            <div class="confirm-actions">
              <button class="btn-secondary" on:click={handleConfirmNo}>Cancel</button>
              <button class="btn-danger" on:click={handleConfirmYes}>Confirm</button>
            </div>
          </div>
        </div>
      {/if}
    {/if}
  </div>
</div>

<style>
  .page-container {
    max-width: 1200px;
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

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .auction-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .auction-header h1 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-color);
  }

  .header-meta {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 0.5rem;
    flex-wrap: wrap;
  }

  .seller {
    font-size: 0.9rem;
    color: var(--text-muted);
  }

  .customized-tag {
    background: var(--warning-bg);
    color: var(--warning-color);
    font-size: 0.75rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
  }

  .header-actions {
    flex-shrink: 0;
  }

  .auction-panels {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .seller-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    background: var(--success-bg);
    border: 1px solid var(--success-color);
    border-radius: 8px;
    margin-bottom: 1.5rem;
  }

  .settle-hint {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .section {
    margin-bottom: 1.5rem;
  }

  .section-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-color);
    margin: 0 0 0.75rem 0;
  }

  .description {
    font-size: 0.9rem;
    color: var(--text-color);
    line-height: 1.6;
    white-space: pre-wrap;
    margin: 0;
  }

  .custom-image-float {
    float: right;
    max-width: 280px;
    margin: 0 0 0.75rem 1rem;
  }

  .custom-image {
    width: 100%;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background: var(--hover-color);
    object-fit: contain;
  }

  .custom-image-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 2rem;
    background: var(--hover-color);
    border: 1px dashed var(--border-color);
    border-radius: 8px;
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  .muted {
    color: var(--text-muted);
    font-size: 0.9rem;
    margin: 0;
  }

  /* Item Grid */
  .item-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 8px;
  }

  .item-card {
    display: flex;
    flex-direction: column;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
    text-decoration: none;
    color: inherit;
    transition: border-color 0.15s;
  }

  .item-card:hover:not(.no-link) {
    border-color: var(--accent-color);
  }

  .item-card.no-link {
    pointer-events: none;
  }

  .item-image {
    width: 100%;
    aspect-ratio: 1;
    background: var(--hover-color);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }

  .item-image img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .item-placeholder {
    color: var(--text-muted);
    opacity: 0.4;
  }

  .item-info {
    padding: 6px 8px;
    display: flex;
    align-items: baseline;
    gap: 4px;
    min-width: 0;
  }

  .item-name {
    font-size: 0.8rem;
    color: var(--text-color);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
  }

  .item-qty {
    font-size: 0.75rem;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  /* Admin Panel */
  .admin-panel {
    margin-top: 2rem;
    padding: 1.25rem;
    background: var(--error-bg);
    border: 1px solid var(--error-color);
    border-radius: 8px;
  }

  .admin-panel .section-title {
    color: var(--error-color);
  }

  .admin-reason {
    margin-bottom: 0.75rem;
  }

  .admin-reason label {
    display: block;
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-bottom: 0.25rem;
  }

  .reason-input {
    width: 100%;
    box-sizing: border-box;
    padding: 0.5rem;
    border: 1px solid var(--border-color);
    background: var(--secondary-color);
    color: var(--text-color);
    border-radius: 6px;
    font-size: 0.85rem;
  }

  .reason-input:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .admin-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }

  .btn-primary, .btn-secondary, .btn-warning, .btn-danger {
    padding: 0.5rem 1rem;
    font-size: 0.85rem;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
    border: none;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
  }

  .btn-primary {
    background: var(--accent-color);
    color: white;
  }

  .btn-secondary {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .btn-secondary:hover { background: var(--hover-color); }

  .btn-warning {
    background: var(--warning-bg);
    color: var(--warning-color);
    border: 1px solid var(--warning-color);
  }

  .btn-warning:hover:not(:disabled) {
    background: var(--warning-color);
    color: white;
  }

  .btn-danger {
    background: var(--error-bg);
    color: var(--error-color);
    border: 1px solid var(--error-color);
  }

  .btn-danger:hover:not(:disabled) {
    background: var(--error-color);
    color: white;
  }

  .btn-primary:disabled, .btn-warning:disabled, .btn-danger:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }

  .audit-section {
    margin-top: 0.75rem;
  }

  .audit-toggle {
    font-size: 0.8rem;
  }

  .audit-log {
    margin-top: 0.75rem;
    max-height: 400px;
    overflow-y: auto;
  }

  .audit-entry {
    padding: 0.5rem;
    border-bottom: 1px solid var(--border-color);
    font-size: 0.8rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: baseline;
  }

  .audit-action {
    font-weight: 600;
    color: var(--text-color);
  }

  .audit-user {
    color: var(--accent-color);
  }

  .audit-time {
    color: var(--text-muted);
    font-size: 0.75rem;
  }

  .audit-details {
    width: 100%;
    margin: 0.25rem 0 0 0;
    padding: 0.5rem;
    background: var(--secondary-color);
    border-radius: 4px;
    font-size: 0.7rem;
    overflow-x: auto;
    color: var(--text-muted);
  }

  .empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted);
  }

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

  .confirm-message {
    margin: 0 0 1rem 0;
    font-size: 0.9rem;
    line-height: 1.5;
  }

  .confirm-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }

  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  @media (max-width: 899px) {
    .page-container { padding: 1rem; padding-bottom: 2rem; }
    .auction-panels { grid-template-columns: 1fr; }
    .auction-header { flex-direction: column; }
    .item-grid { grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); }
    .custom-image-float {
      float: none;
      max-width: 100%;
      margin: 0 0 0.75rem 0;
      text-align: center;
    }
    .custom-image-float .custom-image {
      max-width: 280px;
    }
  }
</style>
