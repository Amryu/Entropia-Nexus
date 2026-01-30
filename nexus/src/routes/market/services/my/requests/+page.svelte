<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import DashboardNav from "$lib/components/services/DashboardNav.svelte";
  import RequestStatusBadge from "$lib/components/services/RequestStatusBadge.svelte";
  import SkeletonCard from "$lib/components/SkeletonCard.svelte";
  import { goto, invalidateAll } from '$app/navigation';
  import { navigating } from '$app/stores';
  import { apiPut } from '$lib/util';

  export let data;

  // Loading state
  $: isLoading = $navigating !== null;

  $: requests = data.requests || [];
  $: statusFilter = data.statusFilter;

  let actionLoading = null;
  let actionError = null;

  const statusOptions = [
    { value: '', label: 'All Statuses' },
    { value: 'pending', label: 'Pending' },
    { value: 'negotiating', label: 'In Conversation' },
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
      custom: 'Custom'
    };
    return labels[type] || type;
  }

  function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString();
  }

  function handleStatusChange(event) {
    const status = event.target.value;
    if (status) {
      goto(`/market/services/my/requests?status=${status}`);
    } else {
      goto('/market/services/my/requests');
    }
  }

  function viewRequest(requestId) {
    goto(`/market/services/my/requests/${requestId}`);
  }

  async function closeQuestion(event, requestId) {
    event.stopPropagation();
    actionLoading = requestId;
    actionError = null;

    try {
      const response = await apiPut(fetch, `/api/services/requests/${requestId}/abort`, {});

      if (response.error) {
        actionError = response.error;
      } else {
        await invalidateAll();
      }
    } catch (err) {
      actionError = 'Failed to close question';
    } finally {
      actionLoading = null;
    }
  }

  // Helper to check if request is a question
  function isQuestion(request) {
    return request.service_notes && request.service_notes.startsWith('[QUESTION]');
  }

  // Group requests by status category - separate questions from requests
  $: questionRequests = requests.filter(r => ['pending', 'negotiating'].includes(r.status) && isQuestion(r));
  $: pendingRequests = requests.filter(r => ['pending', 'negotiating'].includes(r.status) && !isQuestion(r));
  $: activeRequests = requests.filter(r => ['accepted', 'in_progress'].includes(r.status));
  $: historyRequests = requests.filter(r => ['completed', 'cancelled', 'declined', 'aborted'].includes(r.status));
</script>

<svelte:head>
  <title>My Requests | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
<div class="page-container">
  <div class="breadcrumb">
    <a href="/market/services/my">My Services</a>
    <span>/</span>
    <span>My Requests</span>
  </div>

  <div class="header-row">
    <h1>My Requests</h1>
  </div>

  <DashboardNav />

  <div class="controls">
    <div class="filter-group">
      <label for="status-filter">Filter by status:</label>
      <select id="status-filter" value={statusFilter || ''} on:change={handleStatusChange}>
        {#each statusOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </div>
  </div>

  {#if actionError}
    <div class="error-banner">{actionError}</div>
  {/if}

  {#if requests.length === 0}
    <div class="empty-state">
      <p>You haven't made any service requests yet.</p>
      <a href="/market/services" class="browse-link">Browse services</a>
    </div>
  {:else}
    {#if questionRequests.length > 0}
      <div class="section">
        <h2>Your Questions ({questionRequests.length})</h2>
        <div class="request-list">
          {#each questionRequests as request}
            <div class="request-card question-card" on:click={() => viewRequest(request.id)} on:keypress={(e) => e.key === 'Enter' && viewRequest(request.id)} role="button" tabindex="0">
              <div class="request-main">
                <div class="request-info">
                  <span class="service-title">{request.service_title}</span>
                  <span class="provider">by {request.provider_name}</span>
                </div>
                <div class="request-meta">
                  <span class="service-type">{getServiceTypeLabel(request.service_type)}</span>
                  <span class="question-badge">Question</span>
                </div>
              </div>
              <div class="request-details">
                <span class="date">Asked: {formatDateTime(request.created_at)}</span>
                <button
                  class="close-btn"
                  disabled={actionLoading === request.id}
                  on:click={(e) => closeQuestion(e, request.id)}
                >
                  {actionLoading === request.id ? '...' : 'Close'}
                </button>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if pendingRequests.length > 0}
      <div class="section">
        <h2>Pending / In Conversation ({pendingRequests.length})</h2>
        <div class="request-list">
          {#each pendingRequests as request}
            <div class="request-card" on:click={() => viewRequest(request.id)} on:keypress={(e) => e.key === 'Enter' && viewRequest(request.id)} role="button" tabindex="0">
              <div class="request-main">
                <div class="request-info">
                  <span class="service-title">{request.service_title}</span>
                  <span class="provider">by {request.provider_name}</span>
                </div>
                <div class="request-meta">
                  <span class="service-type">{getServiceTypeLabel(request.service_type)}</span>
                  <RequestStatusBadge status={request.status} size="small" />
                </div>
              </div>
              <div class="request-details">
                <span class="date">Requested: {formatDateTime(request.created_at)}</span>
                {#if request.requested_start}
                  <span class="scheduled">Scheduled: {formatDateTime(request.requested_start)}</span>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if activeRequests.length > 0}
      <div class="section">
        <h2>Active ({activeRequests.length})</h2>
        <div class="request-list">
          {#each activeRequests as request}
            <div class="request-card" on:click={() => viewRequest(request.id)} on:keypress={(e) => e.key === 'Enter' && viewRequest(request.id)} role="button" tabindex="0">
              <div class="request-main">
                <div class="request-info">
                  <span class="service-title">{request.service_title}</span>
                  <span class="provider">by {request.provider_name}</span>
                </div>
                <div class="request-meta">
                  <span class="service-type">{getServiceTypeLabel(request.service_type)}</span>
                  <RequestStatusBadge status={request.status} size="small" />
                </div>
              </div>
              <div class="request-details">
                {#if request.final_start}
                  <span class="scheduled">Start: {formatDateTime(request.final_start)}</span>
                {/if}
                {#if request.final_price}
                  <span class="price">Est. cost: {request.final_price} PED</span>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if historyRequests.length > 0}
      <div class="section">
        <h2>History ({historyRequests.length})</h2>
        <div class="request-list">
          {#each historyRequests as request}
            <div class="request-card history" on:click={() => viewRequest(request.id)} on:keypress={(e) => e.key === 'Enter' && viewRequest(request.id)} role="button" tabindex="0">
              <div class="request-main">
                <div class="request-info">
                  <span class="service-title">{request.service_title}</span>
                  <span class="provider">by {request.provider_name}</span>
                </div>
                <div class="request-meta">
                  <span class="service-type">{getServiceTypeLabel(request.service_type)}</span>
                  <RequestStatusBadge status={request.status} size="small" />
                </div>
              </div>
              <div class="request-details">
                <span class="date">{formatDateTime(request.updated_at || request.created_at)}</span>
                {#if request.actual_payment}
                  <span class="price">Paid: {request.actual_payment} PED</span>
                {/if}
                {#if request.review_score}
                  <span class="rating">Rating: {request.review_score}/10</span>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </div>
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

  .header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  h1 {
    margin: 0;
  }

  .controls {
    display: flex;
    justify-content: flex-start;
    align-items: center;
    margin-bottom: 1.5rem;
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

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    margin-bottom: 1rem;
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
    margin: 0 0 1rem 0;
    font-size: 1.1rem;
  }

  .request-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .request-card {
    border: 1px solid var(--border-color, #e5e5e5);
    border-radius: 8px;
    padding: 1rem;
    background: var(--bg-color, #fff);
    cursor: pointer;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }

  .request-card:hover {
    border-color: var(--accent-color, #4a9eff);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  }

  .request-card.history {
    opacity: 0.85;
  }

  .request-main {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 0.5rem;
  }

  .request-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .service-title {
    font-weight: 600;
    font-size: 1rem;
  }

  .provider {
    font-size: 0.85rem;
    color: var(--text-muted, #666);
  }

  .request-meta {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .service-type {
    font-size: 0.8rem;
    color: var(--text-muted, #666);
    background: var(--bg-secondary, #f5f5f5);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
  }

  .request-details {
    display: flex;
    gap: 1.5rem;
    font-size: 0.85rem;
    color: var(--text-muted, #666);
  }

  .price {
    color: var(--text-color, #333);
    font-weight: 500;
  }

  .rating {
    color: var(--warning-color, #f59e0b);
  }

  /* Question card styles */
  .request-card.question-card {
    border-color: var(--accent-color, #8b5cf6);
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.05) 0%, rgba(139, 92, 246, 0.02) 100%);
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

  .close-btn {
    margin-left: auto;
    padding: 0.25rem 0.75rem;
    font-size: 0.8rem;
    border: 1px solid var(--border-color, #ccc);
    border-radius: 4px;
    background: var(--bg-color, #fff);
    color: var(--text-muted, #666);
    cursor: pointer;
  }

  .close-btn:hover:not(:disabled) {
    background: var(--hover-color, #f0f0f0);
    color: var(--text-color, #333);
  }

  .close-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
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

    .request-main {
      flex-direction: column;
      gap: 0.5rem;
    }

    .request-meta {
      justify-content: flex-start;
    }

    .request-details {
      flex-wrap: wrap;
      gap: 0.5rem;
    }

    .section h2 {
      font-size: 1rem;
    }

    .service-title {
      font-size: 0.95rem;
    }
  }
</style>
