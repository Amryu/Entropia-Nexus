<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import DashboardNav from "$lib/components/services/DashboardNav.svelte";
  import RequestStatusBadge from "$lib/components/services/RequestStatusBadge.svelte";
  import { goto, invalidateAll } from '$app/navigation';
  import { apiPut } from '$lib/util';

  const DISCORD_GUILD_ID = import.meta.env.VITE_DISCORD_GUILD_ID;

  export let data;

  $: service = data.service;
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

  function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString();
  }

  function handleStatusChange(event) {
    const status = event.target.value;
    if (status) {
      goto(`/market/services/my/offers/${service.id}?status=${status}`);
    } else {
      goto(`/market/services/my/offers/${service.id}`);
    }
  }

  async function updateRequestStatus(requestId, newStatus, additionalData = {}) {
    actionLoading = requestId;
    actionError = null;

    try {
      const response = await apiPut(fetch, `/api/services/my/requests/${requestId}/status`, {
        status: newStatus,
        ...additionalData
      });

      if (response.error) {
        actionError = response.error;
      } else {
        await invalidateAll();
      }
    } catch (err) {
      actionError = 'Failed to update request status';
    } finally {
      actionLoading = null;
    }
  }

  function canAccept(request) {
    return request.status === 'pending' || request.status === 'negotiating';
  }

  function canDecline(request) {
    return request.status === 'pending' || request.status === 'negotiating';
  }

  function canStart(request) {
    return request.status === 'accepted';
  }

  function canFinish(request) {
    return request.status === 'in_progress';
  }

  function canAbort(request) {
    return ['in_progress', 'accepted'].includes(request.status);
  }

  function canReactivate(request) {
    return request.status === 'aborted';
  }

  // Helper to check if request is a question
  function isQuestion(request) {
    return request.service_notes && request.service_notes.startsWith('[QUESTION]');
  }

  // Get question text from service_notes
  function getQuestionText(request) {
    if (!isQuestion(request)) return null;
    return request.service_notes.replace('[QUESTION]', '').trim();
  }

  // Group by status - separate questions from actual requests
  $: questionRequests = requests.filter(r => ['pending', 'negotiating'].includes(r.status) && isQuestion(r));
  $: pendingRequests = requests.filter(r => ['pending', 'negotiating'].includes(r.status) && !isQuestion(r));
  $: acceptedRequests = requests.filter(r => r.status === 'accepted');
  $: inProgressRequests = requests.filter(r => r.status === 'in_progress');
  $: completedRequests = requests.filter(r => r.status === 'completed');
  $: otherRequests = requests.filter(r => ['declined', 'cancelled', 'aborted'].includes(r.status));
</script>

<svelte:head>
  <title>{service.title} - Requests | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
<div class="page-container">
  <div class="breadcrumb">
    <a href="/market/services/my">My Services</a>
    <span>/</span>
    <a href="/market/services/my/offers">My Offers</a>
    <span>/</span>
    <span>{service.title}</span>
  </div>

  <div class="header-row">
    <div class="header-info">
      <h1>{service.title}</h1>
      <span class="service-status" class:busy={service.is_busy}>
        {service.is_busy ? 'Currently Busy' : 'Available'}
      </span>
    </div>
    <div class="header-actions">
      <a href="/market/services/{service.id}/edit" class="btn secondary">Edit Service</a>
      <a href="/market/services/{service.id}/availability" class="btn secondary">Availability</a>
    </div>
  </div>

  <DashboardNav />

  <div class="controls">
    <div class="filter-group">
      <label for="status-filter">Filter:</label>
      <select id="status-filter" value={statusFilter || ''} on:change={handleStatusChange}>
        {#each statusOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </div>
    <span class="request-count">{requests.length} requests</span>
  </div>

  {#if actionError}
    <div class="error-banner">{actionError}</div>
  {/if}

  {#if requests.length === 0}
    <div class="empty-state">
      <p>No requests match the current filter.</p>
    </div>
  {:else}
    {#if questionRequests.length > 0}
      <div class="section">
        <h2>Questions ({questionRequests.length})</h2>
        <div class="request-list">
          {#each questionRequests as request}
            <div class="request-card question-card">
              <div class="request-header">
                <div class="requester-info">
                  <span class="requester-name">{request.requester_name}</span>
                  <span class="request-date">Asked {formatDateTime(request.created_at)}</span>
                </div>
                <span class="question-badge">Question</span>
              </div>

              <div class="question-text">
                <p>{getQuestionText(request)}</p>
              </div>

              {#if request.discord_thread_id}
                <div class="request-details">
                  <div class="detail discord">
                    <span class="label">Discord:</span>
                    <a href="https://discord.com/channels/{DISCORD_GUILD_ID}/{request.discord_thread_id}" target="_blank" rel="noopener">
                      View Thread
                    </a>
                  </div>
                </div>
              {/if}

              <div class="question-actions">
                <span class="question-actions-note">Respond in the Discord thread. The customer can convert this to a request from there.</span>
                <button
                  class="btn secondary"
                  disabled={actionLoading === request.id}
                  on:click={() => updateRequestStatus(request.id, 'cancelled')}
                >
                  {actionLoading === request.id ? 'Processing...' : 'Close Question'}
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
            <div class="request-card">
              <div class="request-header">
                <div class="requester-info">
                  <span class="requester-name">{request.requester_name}</span>
                  <span class="request-date">Requested {formatDateTime(request.created_at)}</span>
                </div>
                <RequestStatusBadge status={request.status} />
              </div>

              <div class="request-details">
                {#if request.requested_start}
                  <div class="detail">
                    <span class="label">Requested time:</span>
                    <span>{formatDateTime(request.requested_start)}</span>
                  </div>
                {/if}
                {#if request.requested_duration_minutes}
                  <div class="detail">
                    <span class="label">Duration:</span>
                    <span>{request.requested_duration_minutes} minutes{request.is_open_ended ? ' (open-ended)' : ''}</span>
                  </div>
                {/if}
                {#if request.discord_thread_id}
                  <div class="detail discord">
                    <span class="label">Discord:</span>
                    <a href="https://discord.com/channels/{DISCORD_GUILD_ID}/{request.discord_thread_id}" target="_blank" rel="noopener">
                      View Thread
                    </a>
                  </div>
                {/if}
              </div>

              <div class="request-actions">
                {#if request.status === 'pending'}
                  <button
                    class="btn primary"
                    disabled={actionLoading === request.id}
                    on:click={() => updateRequestStatus(request.id, 'negotiating')}
                  >
                    {actionLoading === request.id ? 'Processing...' : 'Start Conversation'}
                  </button>
                {:else if request.status === 'negotiating'}
                  <button
                    class="btn primary"
                    disabled={actionLoading === request.id}
                    on:click={() => updateRequestStatus(request.id, 'accepted')}
                  >
                    {actionLoading === request.id ? 'Processing...' : 'Accept'}
                  </button>
                {/if}
                {#if canDecline(request)}
                  <button
                    class="btn danger"
                    disabled={actionLoading === request.id}
                    on:click={() => updateRequestStatus(request.id, 'declined')}
                  >
                    Decline
                  </button>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if acceptedRequests.length > 0}
      <div class="section">
        <h2>Accepted ({acceptedRequests.length})</h2>
        <div class="request-list">
          {#each acceptedRequests as request}
            <div class="request-card">
              <div class="request-header">
                <div class="requester-info">
                  <span class="requester-name">{request.requester_name}</span>
                  <span class="request-date">{formatDateTime(request.final_start || request.requested_start)}</span>
                </div>
                <RequestStatusBadge status={request.status} />
              </div>

              <div class="request-actions">
                {#if canStart(request)}
                  <button
                    class="btn primary"
                    disabled={actionLoading === request.id}
                    on:click={() => updateRequestStatus(request.id, 'in_progress', { actual_start: new Date().toISOString() })}
                  >
                    Start Service
                  </button>
                {/if}
                <button
                  class="btn secondary"
                  disabled={actionLoading === request.id}
                  on:click={() => updateRequestStatus(request.id, 'cancelled')}
                >
                  Cancel
                </button>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if inProgressRequests.length > 0}
      <div class="section">
        <h2>In Progress ({inProgressRequests.length})</h2>
        <div class="request-list">
          {#each inProgressRequests as request}
            <div class="request-card active">
              <div class="request-header">
                <div class="requester-info">
                  <span class="requester-name">{request.requester_name}</span>
                  <span class="request-date">Started {formatDateTime(request.actual_start)}</span>
                </div>
                <RequestStatusBadge status={request.status} />
              </div>

              <div class="request-actions">
                {#if canFinish(request)}
                  <button
                    class="btn primary"
                    disabled={actionLoading === request.id}
                    on:click={() => goto(`/market/services/my/offers/${service.id}/finish/${request.id}`)}
                  >
                    Finish
                  </button>
                {/if}
                {#if canAbort(request)}
                  <button
                    class="btn danger"
                    disabled={actionLoading === request.id}
                    on:click={() => updateRequestStatus(request.id, 'aborted')}
                  >
                    Abort
                  </button>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if completedRequests.length > 0}
      <div class="section">
        <h2>Completed ({completedRequests.length})</h2>
        <div class="request-list">
          {#each completedRequests as request}
            <div class="request-card completed">
              <div class="request-header">
                <div class="requester-info">
                  <span class="requester-name">{request.requester_name}</span>
                  <span class="request-date">{formatDateTime(request.actual_end || request.updated_at)}</span>
                </div>
                <RequestStatusBadge status={request.status} />
              </div>
              <div class="request-details">
                {#if request.actual_payment}
                  <div class="detail">
                    <span class="label">Payment:</span>
                    <span>{request.actual_payment} PED</span>
                  </div>
                {/if}
                {#if request.review_score}
                  <div class="detail">
                    <span class="label">Rating:</span>
                    <span>{request.review_score}/10</span>
                  </div>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if otherRequests.length > 0}
      <div class="section">
        <h2>Other ({otherRequests.length})</h2>
        <div class="request-list">
          {#each otherRequests as request}
            <div class="request-card other">
              <div class="request-header">
                <div class="requester-info">
                  <span class="requester-name">{request.requester_name}</span>
                  <span class="request-date">{formatDateTime(request.updated_at)}</span>
                </div>
                <RequestStatusBadge status={request.status} />
              </div>
              {#if canReactivate(request)}
                <div class="request-actions">
                  <button
                    class="btn secondary"
                    disabled={actionLoading === request.id}
                    on:click={() => updateRequestStatus(request.id, 'pending')}
                  >
                    Reactivate
                  </button>
                </div>
              {/if}
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
    align-items: flex-start;
    margin-bottom: 1.5rem;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .header-info h1 {
    margin: 0 0 0.25rem 0;
  }

  .service-status {
    font-size: 0.9rem;
    color: var(--success-color);
  }

  .service-status.busy {
    color: var(--error-color);
  }

  .header-actions {
    display: flex;
    gap: 0.5rem;
  }

  .btn {
    padding: 0.5rem 1rem;
    border-radius: 4px;
    text-decoration: none;
    font-size: 0.9rem;
    cursor: pointer;
    border: 1px solid transparent;
  }

  .btn.primary {
    background: var(--accent-color, #4a9eff);
    color: white;
    border-color: var(--accent-color, #4a9eff);
  }

  .btn.primary:hover:not(:disabled) {
    background: var(--accent-color-hover, #3a8eef);
  }

  .btn.secondary {
    background: var(--bg-color, #fff);
    color: var(--text-color, #333);
    border-color: var(--border-color, #ccc);
  }

  .btn.secondary:hover:not(:disabled) {
    background: var(--hover-color, #f0f0f0);
  }

  .btn.danger {
    background: var(--error-bg);
    color: var(--error-color);
    border-color: var(--error-color);
  }

  .btn.danger:hover:not(:disabled) {
    background: var(--error-bg);
    filter: brightness(0.9);
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .controls {
    display: flex;
    justify-content: space-between;
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
  }

  .request-count {
    font-size: 0.9rem;
    color: var(--text-muted, #666);
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
  }

  .request-card.active {
    border-color: var(--success-color);
    background: var(--success-bg);
  }

  .request-card.completed {
    opacity: 0.85;
  }

  .request-card.other {
    opacity: 0.7;
  }

  .request-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 0.75rem;
  }

  .requester-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .requester-name {
    font-weight: 600;
  }

  .request-date {
    font-size: 0.85rem;
    color: var(--text-muted, #666);
  }

  .request-details {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    margin-bottom: 0.75rem;
    font-size: 0.9rem;
  }

  .detail {
    display: flex;
    gap: 0.5rem;
  }

  .detail .label {
    color: var(--text-muted, #666);
  }

  .detail.discord a {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .detail.discord a:hover {
    text-decoration: underline;
  }

  .request-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  /* Question card styles */
  .request-card.question-card {
    border-color: #8b5cf6;
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.05) 0%, rgba(139, 92, 246, 0.02) 100%);
  }

  .question-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-weight: 500;
    font-size: 0.875rem;
    color: #8b5cf6;
    background-color: #ede9fe;
  }

  .question-text {
    background: var(--bg-secondary, #f5f5f5);
    border-radius: 4px;
    padding: 0.75rem;
    margin-bottom: 0.75rem;
    border-left: 3px solid #8b5cf6;
  }

  .question-text p {
    margin: 0;
    font-style: italic;
    color: var(--text-color, #333);
  }

  .question-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--border-color, #e5e5e5);
  }

  .question-actions-note {
    font-size: 0.85rem;
    color: var(--text-muted, #666);
  }

  @media (max-width: 600px) {
    .header-row {
      flex-direction: column;
    }

    .header-actions {
      width: 100%;
    }

    .header-actions .btn {
      flex: 1;
      text-align: center;
    }
  }
</style>
