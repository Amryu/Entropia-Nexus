<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import { goto, invalidateAll } from '$app/navigation';
  import { apiPost, apiPut, apiDelete } from '$lib/util';
  import TicketOfferCard from '$lib/components/services/TicketOfferCard.svelte';
  import TicketOfferEditor from '$lib/components/services/TicketOfferEditor.svelte';

  let { data } = $props();

  let service = $derived(data.service);
  let ticketOffers = $derived(data.ticketOffers || []);

  let showEditor = $state(false);
  let editingOffer = $state(null);
  let saving = $state(false);
  let error = $state('');

  function handleCreateNew() {
    editingOffer = null;
    showEditor = true;
    error = '';
  }

  function handleEdit(data) {
    editingOffer = data;
    showEditor = true;
    error = '';
  }

  function handleCancel() {
    showEditor = false;
    editingOffer = null;
    error = '';
  }

  async function handleSave(offerData) {
    saving = true;
    error = '';

    try {
      let result;
      if (offerData.id) {
        // Update existing offer
        result = await apiPut(fetch, `/api/services/${service.id}/ticket-offers/${offerData.id}`, offerData);
      } else {
        // Create new offer
        result = await apiPost(fetch, `/api/services/${service.id}/ticket-offers`, offerData);
      }

      if (result.error) {
        error = result.error;
        saving = false;
        return;
      }

      // Success - refresh data and close editor
      await invalidateAll();
      showEditor = false;
      editingOffer = null;
    } catch (e) {
      error = 'Failed to save ticket offer. Please try again.';
    } finally {
      saving = false;
    }
  }

  async function handleDelete(data) {
    const { id } = data;
    saving = true;
    error = '';

    try {
      const result = await apiDelete(fetch, `/api/services/${service.id}/ticket-offers/${id}`);

      if (result.error) {
        error = result.error;
        saving = false;
        return;
      }

      // Success - refresh data and close editor
      await invalidateAll();
      showEditor = false;
      editingOffer = null;
    } catch (e) {
      error = 'Failed to delete ticket offer. Please try again.';
    } finally {
      saving = false;
    }
  }
</script>

<svelte:head>
  <title>Manage Ticket Offers | {service.title} | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="header-row">
      <a href="/market/services/{service.id}" class="back-link">&larr; Back to Service</a>
    </div>

    <h1>Ticket Offers</h1>
    <p class="subtitle">Manage ticket pricing for <strong>{service.title}</strong></p>

    {#if error}
      <div class="error-message">{error}</div>
    {/if}

    {#if showEditor}
      <TicketOfferEditor
        offer={editingOffer}
        {saving}
        serviceMode={service.transportation_details?.service_mode || 'on_demand'}
        onsave={handleSave}
        oncancel={handleCancel}
        ondelete={handleDelete}
      />
    {:else}
      <div class="actions-bar">
        <button class="create-btn" onclick={handleCreateNew}>
          + Create New Ticket Offer
        </button>
      </div>

      {#if ticketOffers.length === 0}
        <div class="empty-state">
          <p>No ticket offers yet.</p>
          <p class="hint">Create ticket offers to let customers purchase single or multi-use passes for your transportation service.</p>
        </div>
      {:else}
        <div class="offers-grid">
          {#each ticketOffers as offer (offer.id)}
            <TicketOfferCard {offer} isOwner={true} onedit={handleEdit} />
          {/each}
        </div>
      {/if}
    {/if}

    <div class="help-section">
      <h3>How Ticket Offers Work</h3>
      <ul>
        <li><strong>Uses-based tickets:</strong> Customer gets a fixed number of trips (e.g., 1 trip, 10 trips)</li>
        <li><strong>Duration-based tickets:</strong> Customer gets unlimited trips for a period (e.g., 30 days)</li>
        <li><strong>Pending state:</strong> Tickets start as "pending" until you accept the customer's first check-in</li>
        <li><strong>Activation:</strong> Duration-based tickets start counting days from activation, not purchase</li>
        {#if service.transportation_details?.service_mode === 'on_demand' || service.transportation_details?.service_mode === 'both'}
          <li><strong>Pickup fee waiver:</strong> Optionally waive your pickup fee for ticket holders on on-demand flights</li>
        {/if}
      </ul>
    </div>
  </div>
</div>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    padding: 1rem;
    padding-bottom: 2rem;
    max-width: 900px;
    margin: 0 auto;
    box-sizing: border-box;
  }

  .header-row {
    margin-bottom: 1rem;
  }

  .back-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .back-link:hover {
    text-decoration: underline;
  }

  h1 {
    margin: 0 0 0.25rem 0;
  }

  .subtitle {
    margin: 0 0 1.5rem 0;
    color: var(--text-muted, #888);
  }

  .error-message {
    background: #fee;
    border: 1px solid #fcc;
    color: #c00;
    padding: 0.75rem 1rem;
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .actions-bar {
    margin-bottom: 1.5rem;
  }

  .create-btn {
    background: #4a9eff;
    color: white;
    border: none;
    padding: 0.75rem 1.5rem;
    border-radius: 4px;
    font-size: 1rem;
    cursor: pointer;
    font-weight: 500;
  }

  .create-btn:hover {
    background: #3a8eef;
  }

  .empty-state {
    background: var(--secondary-color);
    border: 1px dashed #666;
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
  }

  .empty-state p {
    margin: 0;
    color: var(--text-muted, #888);
  }

  .empty-state .hint {
    margin-top: 0.5rem;
    font-size: 0.9rem;
  }

  .offers-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
  }

  .help-section {
    margin-top: 2rem;
    padding: 1rem;
    background: var(--secondary-color);
    border: 1px solid #555;
    border-radius: 8px;
  }

  .help-section h3 {
    margin: 0 0 0.75rem 0;
    font-size: 1rem;
  }

  .help-section ul {
    margin: 0;
    padding-left: 1.25rem;
  }

  .help-section li {
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted, #888);
  }

  .help-section li:last-child {
    margin-bottom: 0;
  }

  .help-section strong {
    color: var(--text-color);
  }
</style>
