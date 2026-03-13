<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import DashboardNav from "$lib/components/services/DashboardNav.svelte";
  import SkeletonCard from "$lib/components/SkeletonCard.svelte";
  import { goto, invalidateAll } from '$app/navigation';
  import { navigating } from '$app/stores';

  let { data } = $props();

  // Loading state
  let isLoading = $derived($navigating !== null);

  let ownedTickets = $derived(data.ownedTickets || []);
  let issuedTickets = $derived(data.issuedTickets || []);
  let expiredTickets = $derived(data.expiredTickets || []);
  let expiredIssuedTickets = $derived(data.expiredIssuedTickets || []);
  let hasTransportServices = $derived(data.hasTransportServices);

  let activeTab = $state('owned');

  // Ticket extension dialog state
  let showExtendDialog = $state(false);
  let selectedTicket = $state(null);
  let extendAction = $state('extend_uses');
  let additionalUses = $state(1);
  let additionalDays = $state(7);
  let saving = $state(false);
  let error = $state('');

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
  }

  function getTicketStatus(ticket) {
    if (ticket.status === 'expired' || (ticket.valid_until && new Date(ticket.valid_until) < new Date())) {
      return 'expired';
    }
    if (ticket.uses_remaining === 0) {
      return 'used';
    }
    return 'active';
  }

  function getStatusClass(status) {
    return {
      active: 'status-active',
      expired: 'status-expired',
      used: 'status-used'
    }[status] || '';
  }

  function getUsesDisplay(ticket) {
    if (ticket.uses_remaining === -1) return 'Unlimited';
    return `${ticket.uses_remaining} / ${ticket.uses_total}`;
  }

  // Group owned tickets by active/expired
  let activeTickets = $derived(ownedTickets.filter(t => getTicketStatus(t) === 'active'));
  let usedOrExpiredTickets = $derived(ownedTickets.filter(t => getTicketStatus(t) !== 'active'));

  function openExtendDialog(ticket) {
    selectedTicket = ticket;
    const status = getTicketStatus(ticket);
    extendAction = status === 'expired' ? 'reactivate' : 'extend_uses';
    additionalUses = 1;
    additionalDays = 7;
    error = '';
    showExtendDialog = true;
  }

  function closeExtendDialog() {
    showExtendDialog = false;
    selectedTicket = null;
    error = '';
  }

  async function handleCancelTicket() {
    if (!selectedTicket) return;
    if (!confirm('Are you sure you want to cancel this ticket? This action is permanent. Coordinate refunds with the customer separately.')) return;

    saving = true;
    error = '';

    try {
      const response = await fetch(`/api/tickets/${selectedTicket.id}/extend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'cancel' })
      });

      const result = await response.json();
      if (result.error) {
        error = result.error;
      } else {
        closeExtendDialog();
        await invalidateAll();
      }
    } catch (e) {
      error = 'Failed to cancel ticket. Please try again.';
    } finally {
      saving = false;
    }
  }

  async function submitExtension() {
    if (!selectedTicket) return;

    saving = true;
    error = '';

    try {
      const body = { action: extendAction };

      if (extendAction === 'extend_uses') {
        body.additionalUses = additionalUses;
      } else if (extendAction === 'extend_validity') {
        body.additionalDays = additionalDays;
      } else if (extendAction === 'reactivate') {
        body.additionalDays = additionalDays;
        if (additionalUses > 0) {
          body.additionalUses = additionalUses;
        }
      }

      const response = await fetch(`/api/tickets/${selectedTicket.id}/extend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      const result = await response.json();
      if (result.error) {
        error = result.error;
      } else {
        closeExtendDialog();
        await invalidateAll();
      }
    } catch (e) {
      error = 'Failed to extend ticket. Please try again.';
    } finally {
      saving = false;
    }
  }
</script>

<svelte:head>
  <title>My Tickets | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
<div class="page-container">
  <div class="breadcrumb">
    <a href="/market/services/my">My Services</a>
    <span>/</span>
    <span>Tickets</span>
  </div>

  <div class="header-row">
    <h1>Tickets</h1>
  </div>

  <DashboardNav />

  {#if hasTransportServices}
    <div class="tab-row">
      <button class="tab" class:active={activeTab === 'owned'} onclick={() => activeTab = 'owned'}>
        My Tickets
      </button>
      <button class="tab" class:active={activeTab === 'issued'} onclick={() => activeTab = 'issued'}>
        Issued Tickets
      </button>
    </div>
  {/if}

  {#if activeTab === 'owned'}
    {#if ownedTickets.length === 0 && expiredTickets.length === 0}
      <div class="empty-state">
        <p>You don't have any transportation tickets.</p>
        <a href="/market/services/transportation" class="browse-link">Browse transportation services</a>
      </div>
    {:else}
      {#if activeTickets.length > 0}
        <div class="section">
          <h2>Active Tickets ({activeTickets.length})</h2>
          <div class="ticket-grid">
            {#each activeTickets as ticket}
              <div class="ticket-card">
                <div class="ticket-header">
                  <span class="ticket-name">{ticket.offer_name || 'Ticket'}</span>
                  <span class="ticket-status {getStatusClass('active')}">Active</span>
                </div>
                <div class="ticket-service">{ticket.service_title}</div>
                <div class="ticket-details">
                  <div class="detail-row">
                    <span class="label">Uses remaining:</span>
                    <span class="value">{getUsesDisplay(ticket)}</span>
                  </div>
                  {#if ticket.valid_until}
                    <div class="detail-row">
                      <span class="label">Expires:</span>
                      <span class="value">{formatDate(ticket.valid_until)}</span>
                    </div>
                  {/if}
                  <div class="detail-row">
                    <span class="label">Purchased:</span>
                    <span class="value">{formatDate(ticket.created_at)}</span>
                  </div>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if expiredTickets.length > 0}
        <div class="section">
          <h2>Recently Expired</h2>
          <p class="section-description">Your most recent expired ticket for each service</p>
          <div class="ticket-grid">
            {#each expiredTickets as ticket}
              <div class="ticket-card expired">
                <div class="ticket-header">
                  <span class="ticket-name">{ticket.offer_name || 'Ticket'}</span>
                  <span class="ticket-status {getStatusClass('expired')}">Expired</span>
                </div>
                <div class="ticket-service">{ticket.service_title}</div>
                <div class="ticket-details">
                  <div class="detail-row">
                    <span class="label">Expired:</span>
                    <span class="value">{formatDate(ticket.valid_until)}</span>
                  </div>
                </div>
                <button class="rebuy-btn" onclick={() => goto(`/market/services/${ticket.service_id}`)}>
                  Buy New Ticket
                </button>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if usedOrExpiredTickets.length > 0}
        <div class="section">
          <h2>History ({usedOrExpiredTickets.length})</h2>
          <div class="ticket-list">
            {#each usedOrExpiredTickets as ticket}
              <div class="ticket-row">
                <span class="service">{ticket.service_title}</span>
                <span class="name">{ticket.offer_name}</span>
                <span class="status {getStatusClass(getTicketStatus(ticket))}">{getTicketStatus(ticket)}</span>
                <span class="date">{formatDate(ticket.created_at)}</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    {/if}
  {:else if activeTab === 'issued'}
    {#if issuedTickets.length === 0 && expiredIssuedTickets.length === 0}
      <div class="empty-state">
        <p>No tickets have been purchased for your transportation services yet.</p>
      </div>
    {:else}
      {#if issuedTickets.length > 0}
        <div class="section">
          <h2>Active Issued Tickets ({issuedTickets.length})</h2>
          <p class="section-description">Click a ticket to extend it</p>
          <div class="ticket-list issued">
            {#each issuedTickets as ticket}
              <div class="ticket-row clickable" onclick={() => openExtendDialog(ticket)} onkeypress={(e) => e.key === 'Enter' && openExtendDialog(ticket)} role="button" tabindex="0">
                <span class="buyer">{ticket.buyer_name}</span>
                <span class="service">{ticket.service_title}</span>
                <span class="name">{ticket.offer_name}</span>
                <span class="uses">{getUsesDisplay(ticket)}</span>
                <span class="status {getStatusClass(getTicketStatus(ticket))}">{getTicketStatus(ticket)}</span>
                <span class="date">{formatDate(ticket.created_at)}</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if expiredIssuedTickets.length > 0}
        <div class="section">
          <h2>Recently Expired ({expiredIssuedTickets.length})</h2>
          <p class="section-description">Click to reactivate an expired ticket</p>
          <div class="ticket-list issued">
            {#each expiredIssuedTickets as ticket}
              <div class="ticket-row clickable expired-row" onclick={() => openExtendDialog(ticket)} onkeypress={(e) => e.key === 'Enter' && openExtendDialog(ticket)} role="button" tabindex="0">
                <span class="buyer">{ticket.buyer_name}</span>
                <span class="service">{ticket.service_title}</span>
                <span class="name">{ticket.offer_name}</span>
                <span class="uses">{getUsesDisplay(ticket)}</span>
                <span class="status {getStatusClass('expired')}">expired</span>
                <span class="date">{formatDate(ticket.valid_until)}</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    {/if}
  {/if}
</div>
</div>

<!-- Ticket Extension Dialog -->
{#if showExtendDialog && selectedTicket}
  <div class="dialog-overlay" onclick={closeExtendDialog} onkeypress={(e) => e.key === 'Escape' && closeExtendDialog()}>
    <div class="dialog" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
      <div class="dialog-header">
        <h2>{getTicketStatus(selectedTicket) === 'expired' ? 'Reactivate Ticket' : 'Extend Ticket'}</h2>
        <button class="close-btn" onclick={closeExtendDialog}>&times;</button>
      </div>

      <div class="dialog-body">
        <div class="ticket-info">
          <p><strong>Customer:</strong> {selectedTicket.buyer_name}</p>
          <p><strong>Ticket:</strong> {selectedTicket.offer_name}</p>
          <p><strong>Service:</strong> {selectedTicket.service_title}</p>
          <p><strong>Current uses:</strong> {getUsesDisplay(selectedTicket)}</p>
          {#if selectedTicket.valid_until}
            <p><strong>{getTicketStatus(selectedTicket) === 'expired' ? 'Expired' : 'Expires'}:</strong> {formatDate(selectedTicket.valid_until)}</p>
          {/if}
        </div>

        {#if error}
          <div class="error-message">{error}</div>
        {/if}

        {#if getTicketStatus(selectedTicket) === 'expired'}
          <div class="form-group">
            <label>Reactivate with:</label>
            <div class="input-row">
              <input type="number" bind:value={additionalDays} min="1" max="365" /> days validity
            </div>
            <div class="input-row">
              <input type="number" bind:value={additionalUses} min="0" max="100" /> additional uses (optional)
            </div>
          </div>
        {:else}
          <div class="form-group">
            <label>Extension type:</label>
            <div class="radio-group">
              <label class="radio-option">
                <input type="radio" bind:group={extendAction} value="extend_uses" />
                Add uses
              </label>
              {#if selectedTicket.valid_until}
                <label class="radio-option">
                  <input type="radio" bind:group={extendAction} value="extend_validity" />
                  Extend validity
                </label>
              {/if}
            </div>
          </div>

          {#if extendAction === 'extend_uses'}
            <div class="form-group">
              <label>Additional uses:</label>
              <input type="number" bind:value={additionalUses} min="1" max="100" />
            </div>
          {:else if extendAction === 'extend_validity'}
            <div class="form-group">
              <label>Additional days:</label>
              <input type="number" bind:value={additionalDays} min="1" max="365" />
            </div>
          {/if}
        {/if}
      </div>

      {#if selectedTicket.status !== 'cancelled'}
        <div class="cancel-ticket-section">
          <button class="cancel-ticket-btn" onclick={handleCancelTicket} disabled={saving}>
            Cancel This Ticket
          </button>
          <small>Cancelling is permanent. Coordinate refunds with the customer separately.</small>
        </div>
      {/if}

      <div class="dialog-footer">
        <button class="cancel-btn" onclick={closeExtendDialog} disabled={saving}>Close</button>
        {#if selectedTicket.status !== 'cancelled'}
          <button class="confirm-btn" onclick={submitExtension} disabled={saving}>
            {saving ? 'Processing...' : (getTicketStatus(selectedTicket) === 'expired' ? 'Reactivate' : 'Extend')}
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }
  .page-container {
    padding: 1rem;
    max-width: 1000px;
    margin: 0 auto;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted, #666);
    margin-bottom: 1rem;
  }

  .breadcrumb a {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  h1 {
    margin: 0;
  }

  .tab-row {
    display: flex;
    gap: 0;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid var(--border-color, #ccc);
  }

  .tab {
    padding: 0.75rem 1.5rem;
    border: none;
    background: none;
    cursor: pointer;
    font-size: 1rem;
    color: var(--text-muted, #666);
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
  }

  .tab:hover {
    color: var(--text-color, #333);
  }

  .tab.active {
    color: var(--accent-color, #4a9eff);
    border-bottom-color: var(--accent-color, #4a9eff);
  }

  .empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted, #888);
  }

  .browse-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .section {
    margin-bottom: 2rem;
  }

  .section h2 {
    margin: 0 0 0.5rem 0;
    font-size: 1.1rem;
  }

  .section-description {
    margin: 0 0 1rem 0;
    font-size: 0.9rem;
    color: var(--text-muted, #666);
  }

  .ticket-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
  }

  .ticket-card {
    border: 1px solid var(--border-color, #e5e5e5);
    border-radius: 8px;
    padding: 1rem;
    background: var(--bg-color, #fff);
  }

  .ticket-card.expired {
    opacity: 0.8;
    border-style: dashed;
  }

  .ticket-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .ticket-name {
    font-weight: 600;
  }

  .ticket-status {
    font-size: 0.8rem;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
  }

  .status-active {
    background: var(--success-bg);
    color: var(--success-color);
  }

  .status-expired {
    background: var(--error-bg);
    color: var(--error-color);
  }

  .status-used {
    background: var(--secondary-color);
    color: var(--text-muted);
  }

  .ticket-service {
    font-size: 0.9rem;
    color: var(--text-muted, #666);
    margin-bottom: 0.75rem;
  }

  .ticket-details {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .detail-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
  }

  .detail-row .label {
    color: var(--text-muted, #666);
  }

  .detail-row .value {
    font-weight: 500;
  }

  .rebuy-btn {
    width: 100%;
    margin-top: 1rem;
    padding: 0.5rem;
    background: var(--accent-color, #4a9eff);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
  }

  .rebuy-btn:hover {
    background: var(--accent-color-hover, #3a8eef);
  }

  .ticket-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .ticket-row {
    display: grid;
    grid-template-columns: 1fr 1fr 80px 100px;
    gap: 1rem;
    padding: 0.75rem;
    background: var(--bg-secondary, #f9f9f9);
    border-radius: 4px;
    font-size: 0.9rem;
    align-items: center;
  }

  .ticket-row.clickable {
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .ticket-row.clickable:hover {
    background: var(--hover-color, #e9e9e9);
  }

  .ticket-row.expired-row {
    opacity: 0.7;
    border: 1px dashed var(--border-color, #ccc);
  }

  .ticket-list.issued .ticket-row {
    grid-template-columns: 120px 1fr 100px 80px 80px 100px;
  }

  .ticket-row .buyer {
    font-weight: 500;
  }

  .ticket-row .service {
    color: var(--text-color, #333);
  }

  .ticket-row .name {
    color: var(--text-muted, #666);
  }

  .ticket-row .uses {
    text-align: center;
  }

  .ticket-row .status {
    text-align: center;
    font-size: 0.8rem;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
  }

  .ticket-row .date {
    text-align: right;
    color: var(--text-muted, #666);
  }

  /* Dialog styles */
  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .dialog {
    background: var(--bg-color, #2a2a2a);
    border-radius: 8px;
    width: 90%;
    max-width: 450px;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid var(--border-color, #444);
  }

  .dialog-header h2 {
    margin: 0;
    font-size: 1.25rem;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: var(--text-muted, #888);
    line-height: 1;
  }

  .close-btn:hover {
    color: var(--text-color, #fff);
  }

  .dialog-body {
    padding: 1.5rem;
  }

  .ticket-info {
    margin-bottom: 1.5rem;
    padding: 1rem;
    background: var(--bg-secondary, #333);
    border-radius: 6px;
  }

  .ticket-info p {
    margin: 0.25rem 0;
    font-size: 0.9rem;
  }

  .error-message {
    background: var(--error-bg, #5a2a2a);
    color: var(--error-color, #ff6b6b);
    padding: 0.75rem;
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
  }

  .form-group input[type="number"] {
    width: 80px;
    padding: 0.5rem;
    border: 1px solid var(--border-color, #444);
    border-radius: 4px;
    background: var(--bg-secondary, #333);
    color: var(--text-color, #fff);
    font-size: 1rem;
  }

  .input-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .radio-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .radio-option {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    font-weight: normal;
  }

  .cancel-ticket-section {
    padding: 0 1.5rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .cancel-ticket-section small {
    color: var(--text-muted, #888);
    font-size: 0.8rem;
  }

  .cancel-ticket-btn {
    padding: 0.5rem 1rem;
    border: 1px solid var(--error-color, #ff6b6b);
    border-radius: 4px;
    background: transparent;
    color: var(--error-color, #ff6b6b);
    cursor: pointer;
    font-size: 0.85rem;
    width: fit-content;
  }

  .cancel-ticket-btn:hover:not(:disabled) {
    background: var(--error-bg, #5a2a2a);
  }

  .cancel-ticket-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
    padding: 1rem 1.5rem;
    border-top: 1px solid var(--border-color, #444);
  }

  .cancel-btn, .confirm-btn {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
  }

  .cancel-btn {
    background: var(--secondary-color, #555);
    color: var(--text-color, #fff);
  }

  .confirm-btn {
    background: var(--accent-color, #4a9eff);
    color: white;
  }

  .confirm-btn:hover:not(:disabled) {
    background: var(--accent-color-hover, #3a8eef);
  }

  .confirm-btn:disabled, .cancel-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  /* Mobile styles */
  @media (max-width: 600px) {
    .page-container {
      padding: 0.75rem;
    }

    h1 {
      font-size: 1.5rem;
    }

    .tab-row {
      overflow-x: auto;
    }

    .tab {
      padding: 0.5rem 1rem;
      font-size: 0.9rem;
      white-space: nowrap;
    }

    .ticket-grid {
      grid-template-columns: 1fr;
    }

    .ticket-row {
      grid-template-columns: 1fr;
      gap: 0.25rem;
      padding: 0.75rem;
    }

    .ticket-list.issued .ticket-row {
      grid-template-columns: 1fr;
    }

    .ticket-row .service,
    .ticket-row .name,
    .ticket-row .buyer {
      font-size: 0.9rem;
    }

    .ticket-row .status,
    .ticket-row .uses,
    .ticket-row .date {
      text-align: left;
    }

    .dialog {
      width: 95%;
      max-height: 85vh;
    }

    .dialog-header {
      padding: 0.75rem 1rem;
    }

    .dialog-header h2 {
      font-size: 1.1rem;
    }

    .dialog-body {
      padding: 1rem;
    }

    .dialog-footer {
      padding: 0.75rem 1rem;
      flex-direction: column;
    }

    .cancel-btn, .confirm-btn {
      width: 100%;
    }

    .section h2 {
      font-size: 1rem;
    }
  }
</style>
