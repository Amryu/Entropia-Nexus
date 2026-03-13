<script lang="ts">
  import { stopPropagation } from 'svelte/legacy';

  // @ts-nocheck
  import '$lib/style.css';
  import DashboardNav from "$lib/components/services/DashboardNav.svelte";
  import RequestStatusBadge from "$lib/components/services/RequestStatusBadge.svelte";
  import SkeletonCard from "$lib/components/SkeletonCard.svelte";
  import { goto, invalidateAll } from '$app/navigation';
  import { page, navigating } from '$app/stores';
  import { apiPut } from '$lib/util';

  let { data } = $props();

  // Loading state during data refresh
  let refreshing = $state(false);
  let isLoading = $derived($navigating !== null || refreshing);

  let services = $derived(data.services || []);
  let incomingRequests = $derived(data.incomingRequests || []);
  let statusFilter = $derived(data.statusFilter);

  let togglingService = $state(null);
  let toggleError = $state(null);

  const statusOptions = [
    { value: '', label: 'All Statuses' },
    { value: 'pending', label: 'Pending' },
    { value: 'accepted', label: 'Accepted' },
    { value: 'in_progress', label: 'In Progress' },
    { value: 'completed', label: 'Completed' },
    { value: 'cancelled', label: 'Cancelled' },
    { value: 'declined', label: 'Declined' },
    { value: 'aborted', label: 'Aborted' }
  ];

  function getServiceTypeLabel(type) {
    const labels = {
      healing: 'Healing',
      dps: 'DPS',
      transportation: 'Transport',
      crafting: 'Crafting',
      hunting: 'Hunting',
      mining: 'Mining',
      custom: 'Custom'
    };
    return labels[type] || type;
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
  }

  function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString();
  }

  function handleStatusChange(event) {
    const status = event.target.value;
    if (status) {
      goto(`/market/services/my/offers?status=${status}`);
    } else {
      goto('/market/services/my/offers');
    }
  }

  function viewServiceDetail(serviceId) {
    goto(`/market/services/my/offers/${serviceId}`);
  }

  function editService(serviceId) {
    goto(`/market/services/${serviceId}/edit`);
  }

  async function toggleServiceActive(service) {
    const newState = !service.is_active;
    toggleError = null;

    // When deactivating, check for pending requests
    if (!newState) {
      const pendingRequests = service.requests?.filter(r => r.status === 'pending') || [];
      const activeRequests = service.requests?.filter(r => ['accepted', 'in_progress'].includes(r.status)) || [];

      if (activeRequests.length > 0) {
        toggleError = `Cannot deactivate "${service.title}" - there are ${activeRequests.length} active request(s). Please complete or abort them first.`;
        return;
      }

      if (pendingRequests.length > 0) {
        if (!confirm(`Deactivating "${service.title}" will decline ${pendingRequests.length} pending request(s). Continue?`)) {
          return;
        }
      } else {
        if (!confirm(`Are you sure you want to deactivate "${service.title}"? It will no longer be visible to others.`)) {
          return;
        }
      }
    }

    togglingService = service.id;
    try {
      const response = await apiPut(fetch, `/api/services/${service.id}`, {
        is_active: newState
      });
      if (response.error) {
        toggleError = response.error;
      } else {
        refreshing = true;
        await invalidateAll();
        refreshing = false;
      }
    } catch (err) {
      console.error('Failed to toggle service status', err);
      toggleError = 'Failed to update service status. Please try again.';
    } finally {
      togglingService = null;
    }
  }

  // Helper to check if request is a question
  function isQuestion(request) {
    return request.service_notes && request.service_notes.startsWith('[QUESTION]');
  }

  // Group requests by service
  let requestsByService = $derived(services.map(service => ({
    ...service,
    requests: incomingRequests.filter(r => r.service_id === service.id)
  })));

  let activeServices = $derived(requestsByService.filter(s => s.is_active));
  let inactiveServices = $derived(requestsByService.filter(s => !s.is_active));
</script>

<svelte:head>
  <title>My Offers | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
<div class="page-container">
  <div class="breadcrumb">
    <a href="/market/services/my">My Services</a>
    <span>/</span>
    <span>My Offers</span>
  </div>

  <div class="header-row">
    <h1>My Offers</h1>
    <a href="/market/services/create" class="create-button">+ Create Service</a>
  </div>

  <DashboardNav />

  {#if toggleError}
    <div class="error-banner">
      {toggleError}
      <button class="dismiss-btn" onclick={() => toggleError = null}>&times;</button>
    </div>
  {/if}

  <div class="controls">
    <div class="filter-group">
      <label for="status-filter">Filter by request status:</label>
      <select id="status-filter" value={statusFilter || ''} onchange={handleStatusChange}>
        {#each statusOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </div>
    <a href="/market/services/my/offers/sync-availability" class="sync-btn">Sync Availability</a>
  </div>

  {#if services.length === 0}
    <div class="empty-state">
      <p>You haven't created any services yet.</p>
      <a href="/market/services/create" class="create-link">Create your first service</a>
    </div>
  {:else}
    {#each activeServices as service}
      <div class="service-card">
        <div class="service-header" onclick={() => viewServiceDetail(service.id)} onkeypress={(e) => e.key === 'Enter' && viewServiceDetail(service.id)} role="button" tabindex="0">
          <div class="service-info">
            <h3>{service.title}</h3>
            <span class="service-type">{getServiceTypeLabel(service.type)}</span>
            <span class="service-status" class:busy={service.is_busy}>
              {service.is_busy ? 'Busy' : 'Available'}
            </span>
          </div>
          <div class="service-actions">
            <button class="small-btn" onclick={stopPropagation(() => editService(service.id))}>Edit</button>
            <button class="small-btn" onclick={stopPropagation(() => goto(`/market/services/${service.id}/availability`))}>Availability</button>
            <button
              class="small-btn toggle-btn"
              onclick={stopPropagation(() => toggleServiceActive(service))}
              disabled={togglingService === service.id}
            >
              {togglingService === service.id ? '...' : 'Deactivate'}
            </button>
          </div>
        </div>

        {#if service.requests.length > 0}
          <div class="requests-section">
            <h4>Incoming Requests ({service.requests.length})</h4>
            <div class="request-list">
              {#each service.requests.slice(0, 5) as request}
                <div class="request-row" class:question-row={isQuestion(request)} onclick={() => viewServiceDetail(service.id)} onkeypress={(e) => e.key === 'Enter' && viewServiceDetail(service.id)} role="button" tabindex="0">
                  <span class="requester">{request.requester_name}</span>
                  <span class="request-date">{formatDateTime(request.created_at)}</span>
                  {#if isQuestion(request)}
                    <span class="question-badge">Question</span>
                  {:else}
                    <RequestStatusBadge status={request.status} size="small" />
                  {/if}
                </div>
              {/each}
              {#if service.requests.length > 5}
                <a href="/market/services/my/offers/{service.id}" class="view-more">
                  View all {service.requests.length} requests
                </a>
              {/if}
            </div>
          </div>
        {:else}
          <div class="no-requests">No requests for this service</div>
        {/if}
      </div>
    {/each}

    {#if inactiveServices.length > 0}
      <h2 class="section-title">Inactive Services ({inactiveServices.length})</h2>
      {#each inactiveServices as service}
        <div class="service-card inactive">
          <div class="service-header" onclick={() => viewServiceDetail(service.id)} onkeypress={(e) => e.key === 'Enter' && viewServiceDetail(service.id)} role="button" tabindex="0">
            <div class="service-info">
              <h3>{service.title}</h3>
              <span class="service-type">{getServiceTypeLabel(service.type)}</span>
              <span class="inactive-badge">Inactive</span>
            </div>
            <div class="service-actions">
              <button class="small-btn" onclick={stopPropagation(() => editService(service.id))}>Edit</button>
              <button
                class="small-btn toggle-btn activate"
                onclick={stopPropagation(() => toggleServiceActive(service))}
                disabled={togglingService === service.id}
              >
                {togglingService === service.id ? '...' : 'Activate'}
              </button>
            </div>
          </div>
        </div>
      {/each}
    {/if}
  {/if}
</div>
</div>

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

  .error-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--error-bg, #fee2e2);
    border: 1px solid var(--error-color, #ef4444);
    color: var(--error-color, #dc2626);
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin-bottom: 1rem;
  }

  .dismiss-btn {
    background: none;
    border: none;
    color: var(--error-color, #dc2626);
    font-size: 1.25rem;
    cursor: pointer;
    padding: 0;
    line-height: 1;
  }

  .dismiss-btn:hover {
    opacity: 0.7;
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

  .create-button {
    background: var(--accent-color, #4a9eff);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    text-decoration: none;
    font-weight: 500;
  }

  .create-button:hover {
    background: var(--accent-color-hover, #3a8eef);
  }

  .controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .filter-group {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .filter-group label {
    font-size: 0.9rem;
    color: var(--text-muted, #666);
  }

  .filter-group select {
    padding: 0.5rem;
    border: 1px solid var(--border-color, #ccc);
    border-radius: 4px;
    background: var(--bg-color, #fff);
  }

  .sync-btn {
    padding: 0.5rem 1rem;
    background: var(--bg-secondary, #f5f5f5);
    border: 1px solid var(--border-color, #ccc);
    border-radius: 4px;
    text-decoration: none;
    color: var(--text-color, #333);
    font-size: 0.9rem;
  }

  .sync-btn:hover {
    background: var(--hover-color, #e8e8e8);
  }

  .empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted, #888);
  }

  .create-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .service-card {
    border: 1px solid var(--border-color, #e5e5e5);
    border-radius: 8px;
    margin-bottom: 1rem;
    background: var(--bg-color, #fff);
  }

  .service-card.inactive {
    opacity: 0.7;
  }

  .service-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    cursor: pointer;
  }

  .service-header:hover {
    background: var(--hover-color, #f9f9f9);
  }

  .service-info {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .service-info h3 {
    margin: 0;
    font-size: 1.1rem;
  }

  .service-type {
    font-size: 0.85rem;
    color: var(--text-muted, #666);
    background: var(--bg-secondary, #f5f5f5);
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
  }

  .service-status {
    font-size: 0.85rem;
    color: var(--success-color);
  }

  .service-status.busy {
    color: var(--error-color);
  }

  .inactive-badge {
    font-size: 0.85rem;
    color: var(--text-muted, #888);
    background: var(--bg-secondary, #f0f0f0);
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
  }

  .service-actions {
    display: flex;
    gap: 0.5rem;
  }

  .small-btn {
    padding: 0.375rem 0.75rem;
    font-size: 0.85rem;
    border: 1px solid var(--border-color, #ccc);
    background: var(--bg-color, #fff);
    border-radius: 4px;
    cursor: pointer;
  }

  .small-btn:hover {
    background: var(--hover-color, #f0f0f0);
  }

  .small-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .toggle-btn {
    background: var(--warning-bg);
    color: var(--warning-color);
    border-color: var(--warning-color);
  }

  .toggle-btn.activate {
    background: var(--success-bg);
    color: var(--success-color);
    border-color: var(--success-color);
  }

  .requests-section {
    border-top: 1px solid var(--border-color, #e5e5e5);
    padding: 1rem;
  }

  .requests-section h4 {
    margin: 0 0 0.75rem 0;
    font-size: 0.95rem;
    color: var(--text-muted, #666);
  }

  .request-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .request-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0.75rem;
    background: var(--bg-secondary, #f9f9f9);
    border-radius: 4px;
    cursor: pointer;
  }

  .request-row:hover {
    background: var(--hover-color, #f0f0f0);
  }

  .requester {
    font-weight: 500;
  }

  .request-date {
    font-size: 0.85rem;
    color: var(--text-muted, #666);
  }

  .view-more {
    display: block;
    text-align: center;
    padding: 0.5rem;
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
    font-size: 0.9rem;
  }

  .view-more:hover {
    text-decoration: underline;
  }

  .no-requests {
    padding: 1rem;
    text-align: center;
    color: var(--text-muted, #888);
    font-size: 0.9rem;
    border-top: 1px solid var(--border-color, #e5e5e5);
  }

  .section-title {
    margin: 2rem 0 1rem 0;
    font-size: 1.1rem;
    color: var(--text-muted, #666);
  }

  /* Question styles */
  .request-row.question-row {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.08) 0%, rgba(139, 92, 246, 0.04) 100%);
    border: 1px solid rgba(139, 92, 246, 0.3);
  }

  .request-row.question-row:hover {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.12) 0%, rgba(139, 92, 246, 0.06) 100%);
  }

  .question-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.5rem;
    border-radius: 9999px;
    font-weight: 500;
    font-size: 0.75rem;
    color: #a78bfa;
    background-color: rgba(139, 92, 246, 0.2);
    border: 1px solid rgba(139, 92, 246, 0.5);
  }

  /* Dropdown styling for proper contrast */
  .filter-group select {
    color: var(--text-color, #333);
    background-color: var(--bg-color, #fff);
  }

  .filter-group select option {
    color: var(--text-color, #333);
    background-color: var(--bg-color, #fff);
  }

  /* Mobile styles */
  @media (max-width: 600px) {
    .page-container {
      padding: 0.75rem;
    }

    h1 {
      font-size: 1.5rem;
    }

    .header-row {
      flex-direction: column;
      align-items: stretch;
      gap: 1rem;
    }

    .create-button {
      text-align: center;
    }

    .controls {
      flex-direction: column;
      align-items: stretch;
    }

    .filter-group {
      flex-direction: column;
      align-items: stretch;
      gap: 0.25rem;
    }

    .filter-group select {
      width: 100%;
    }

    .sync-btn {
      text-align: center;
    }

    .service-header {
      flex-direction: column;
      align-items: stretch;
      gap: 0.75rem;
    }

    .service-info {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }

    .service-info h3 {
      font-size: 1rem;
    }

    .service-actions {
      flex-wrap: wrap;
      justify-content: flex-start;
    }

    .small-btn {
      flex: 1;
      min-width: 80px;
      text-align: center;
    }

    .request-row {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.25rem;
    }

    .request-date {
      order: -1;
      font-size: 0.8rem;
    }

    .section-title {
      font-size: 1rem;
    }
  }
</style>
