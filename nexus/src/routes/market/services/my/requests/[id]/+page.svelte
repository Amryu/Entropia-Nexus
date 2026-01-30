<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import DashboardNav from "$lib/components/services/DashboardNav.svelte";
  import RequestStatusBadge from "$lib/components/services/RequestStatusBadge.svelte";
  import { goto, invalidateAll } from '$app/navigation';
  import { apiPut } from '$lib/util';

  const DISCORD_GUILD_ID = import.meta.env.VITE_DISCORD_GUILD_ID;

  export let data;

  $: request = data.request;

  let actionLoading = false;
  let actionError = null;
  let reviewScore = null;
  let reviewComment = '';
  let showReviewForm = false;

  // Question helpers
  function isQuestion(req) {
    return req.service_notes && req.service_notes.startsWith('[QUESTION]');
  }

  function getQuestionText(req) {
    if (!isQuestion(req)) return null;
    return req.service_notes.replace('[QUESTION]', '').trim();
  }

  $: isQuestionRequest = isQuestion(request);
  $: questionText = getQuestionText(request);

  function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString();
  }

  function getServiceTypeLabel(type) {
    const labels = {
      healing: 'Healing',
      dps: 'DPS',
      transportation: 'Transport',
      custom: 'Custom'
    };
    return labels[type] || type;
  }

  async function closeQuestion() {
    if (!confirm('Are you sure you want to close this question?')) return;

    actionLoading = true;
    actionError = null;

    try {
      const response = await apiPut(fetch, `/api/services/requests/${request.id}/abort`, {});
      if (response.error) {
        actionError = response.error;
      } else {
        await invalidateAll();
        goto('/market/services/my/requests');
      }
    } catch (err) {
      actionError = 'Failed to close question';
    } finally {
      actionLoading = false;
    }
  }

  async function cancelRequest() {
    if (!confirm('Are you sure you want to cancel this request?')) return;

    actionLoading = true;
    actionError = null;

    try {
      const response = await apiPut(fetch, `/api/services/requests/${request.id}/cancel`, {});
      if (response.error) {
        actionError = response.error;
      } else {
        await invalidateAll();
      }
    } catch (err) {
      actionError = 'Failed to cancel request';
    } finally {
      actionLoading = false;
    }
  }

  async function abortRequest() {
    if (!confirm('Are you sure you want to abort this request? This can be reversed by the provider.')) return;

    actionLoading = true;
    actionError = null;

    try {
      const response = await apiPut(fetch, `/api/services/requests/${request.id}/abort`, {});
      if (response.error) {
        actionError = response.error;
      } else {
        await invalidateAll();
      }
    } catch (err) {
      actionError = 'Failed to abort request';
    } finally {
      actionLoading = false;
    }
  }

  async function completeRequest() {
    actionLoading = true;
    actionError = null;

    try {
      const response = await apiPut(fetch, `/api/services/requests/${request.id}/complete`, {
        review_score: reviewScore,
        review_comment: reviewComment || null
      });
      if (response.error) {
        actionError = response.error;
      } else {
        await invalidateAll();
        showReviewForm = false;
      }
    } catch (err) {
      actionError = 'Failed to complete request';
    } finally {
      actionLoading = false;
    }
  }

  function canCancel(req) {
    return ['pending', 'negotiating', 'accepted'].includes(req.status);
  }

  function canAbort(req) {
    return req.status === 'in_progress';
  }

  function canComplete(req) {
    // Customer can mark as completed after provider finishes
    return req.status === 'completed' && !req.review_score;
  }

  function needsReview(req) {
    return req.status === 'completed' && !req.review_score;
  }
</script>

<svelte:head>
  <title>{isQuestionRequest ? 'Question' : 'Request'} Details | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
<div class="page-container">
  <div class="breadcrumb">
    <a href="/market/services/my">My Services</a>
    <span>/</span>
    <a href="/market/services/my/requests">My Requests</a>
    <span>/</span>
    <span>{isQuestionRequest ? 'Question' : 'Request'} #{request.id}</span>
  </div>

  <div class="header-row">
    <div class="header-info">
      <h1>{request.service_title}</h1>
      <span class="provider">by {request.provider_name}</span>
    </div>
    {#if isQuestionRequest}
      <span class="question-badge large">Question</span>
    {:else}
      <RequestStatusBadge status={request.status} size="large" />
    {/if}
  </div>

  <DashboardNav />

  {#if actionError}
    <div class="error-banner">{actionError}</div>
  {/if}

  {#if isQuestionRequest}
    <!-- Simplified view for questions -->
    <div class="content-grid">
      <div class="main-content">
        <div class="card question-card">
          <h2>Your Question</h2>
          <div class="question-content">
            <p>{questionText}</p>
          </div>
          <div class="question-meta">
            <span class="question-date">Asked {formatDateTime(request.created_at)}</span>
          </div>
        </div>

        {#if request.discord_thread_id}
          <div class="card">
            <h2>Discussion</h2>
            <p class="discussion-hint">Continue the conversation in the Discord thread. When you're ready to book the service, use the <strong>Submit Request</strong> button there.</p>
            <a
              href="https://discord.com/channels/{DISCORD_GUILD_ID}/{request.discord_thread_id}"
              target="_blank"
              rel="noopener"
              class="discord-link"
            >
              Open Discord Thread
            </a>
          </div>
        {/if}
      </div>

      <div class="sidebar">
        <div class="card">
          <h3>Service</h3>
          <div class="service-info">
            <span class="service-title">{request.service_title}</span>
            <span class="service-type">{getServiceTypeLabel(request.service_type)}</span>
            <a href="/market/services/{request.service_id}" class="view-service">View Service</a>
          </div>
        </div>

        {#if ['pending', 'negotiating'].includes(request.status)}
          <div class="card">
            <h3>Actions</h3>
            <div class="action-buttons">
              <button
                class="btn secondary full-width"
                disabled={actionLoading}
                on:click={closeQuestion}
              >
                {actionLoading ? 'Processing...' : 'Close Question'}
              </button>
            </div>
          </div>
        {/if}
      </div>
    </div>
  {:else}
    <!-- Full view for regular requests -->
    <div class="content-grid">
      <div class="main-content">
        <!-- Request Timeline -->
        <div class="card">
          <h2>Request Details</h2>
          <div class="timeline">
            <div class="timeline-item">
              <span class="timeline-label">Requested</span>
              <span class="timeline-value">{formatDateTime(request.created_at)}</span>
            </div>

            {#if request.requested_start}
              <div class="timeline-item">
                <span class="timeline-label">Requested Start</span>
                <span class="timeline-value">{formatDateTime(request.requested_start)}</span>
              </div>
            {/if}

            {#if request.final_start}
              <div class="timeline-item">
                <span class="timeline-label">Scheduled Start</span>
                <span class="timeline-value">{formatDateTime(request.final_start)}</span>
              </div>
            {/if}

            {#if request.actual_start}
              <div class="timeline-item">
                <span class="timeline-label">Actually Started</span>
                <span class="timeline-value">{formatDateTime(request.actual_start)}</span>
              </div>
            {/if}

            {#if request.actual_end}
              <div class="timeline-item">
                <span class="timeline-label">Finished</span>
                <span class="timeline-value">{formatDateTime(request.actual_end)}</span>
              </div>
            {/if}
          </div>
        </div>

        <!-- Cost Information -->
        <div class="card">
          <h2>Cost Information</h2>
          <div class="info-grid">
            {#if request.final_price}
              <div class="info-item">
                <span class="info-label">Estimated Cost</span>
                <span class="info-value">{request.final_price} PED</span>
              </div>
            {/if}

            {#if request.actual_payment}
              <div class="info-item highlight">
                <span class="info-label">Actual Payment</span>
                <span class="info-value">{request.actual_payment} PED</span>
              </div>
            {/if}

            {#if request.actual_decay_ped}
              <div class="info-item">
                <span class="info-label">Tool Decay</span>
                <span class="info-value">{request.actual_decay_ped} PED</span>
              </div>
            {/if}

            {#if request.requested_duration_minutes}
              <div class="info-item">
                <span class="info-label">Duration</span>
                <span class="info-value">
                  {request.requested_duration_minutes} min
                  {#if request.is_open_ended}(open-ended){/if}
                </span>
              </div>
            {/if}
          </div>
        </div>

        <!-- Discord Thread -->
        {#if request.discord_thread_id}
          <div class="card">
            <h2>Communication</h2>
            <a
              href="https://discord.com/channels/{DISCORD_GUILD_ID}/{request.discord_thread_id}"
              target="_blank"
              rel="noopener"
              class="discord-link"
            >
              Open Discord Thread
            </a>
          </div>
        {/if}

        <!-- Service Notes -->
        {#if request.service_notes}
          <div class="card">
            <h2>Notes</h2>
            <p class="notes">{request.service_notes}</p>
          </div>
        {/if}

        <!-- Review Section -->
        {#if request.review_score}
          <div class="card">
            <h2>Your Review</h2>
            <div class="review">
              <span class="rating">{request.review_score}/10</span>
              {#if request.review_comment}
                <p class="review-comment">{request.review_comment}</p>
              {/if}
            </div>
          </div>
        {:else if needsReview(request)}
          <div class="card">
            <h2>Leave a Review</h2>
            {#if showReviewForm}
              <div class="review-form">
                <div class="form-group">
                  <label for="rating">Rating (1-10)</label>
                  <input
                    type="number"
                    id="rating"
                    min="1"
                    max="10"
                    bind:value={reviewScore}
                    placeholder="1-10"
                  />
                </div>
                <div class="form-group">
                  <label for="comment">Comment (optional)</label>
                  <textarea
                    id="comment"
                    rows="3"
                    bind:value={reviewComment}
                    placeholder="Share your experience..."
                  ></textarea>
                </div>
                <div class="form-actions">
                  <button class="btn secondary" on:click={() => showReviewForm = false}>Cancel</button>
                  <button
                    class="btn primary"
                    disabled={!reviewScore || reviewScore < 1 || reviewScore > 10 || actionLoading}
                    on:click={completeRequest}
                  >
                    Submit Review
                  </button>
                </div>
              </div>
            {:else}
              <button class="btn primary" on:click={() => showReviewForm = true}>
                Write a Review
              </button>
            {/if}
          </div>
        {/if}
      </div>

      <div class="sidebar">
        <!-- Service Info -->
        <div class="card">
          <h3>Service</h3>
          <div class="service-info">
            <span class="service-title">{request.service_title}</span>
            <span class="service-type">{getServiceTypeLabel(request.service_type)}</span>
            <a href="/market/services/{request.service_id}" class="view-service">View Service</a>
          </div>
        </div>

        <!-- Actions -->
        <div class="card">
          <h3>Actions</h3>
          <div class="action-buttons">
            {#if canCancel(request)}
              <button
                class="btn danger full-width"
                disabled={actionLoading}
                on:click={cancelRequest}
              >
                Cancel Request
              </button>
            {/if}

            {#if canAbort(request)}
              <button
                class="btn danger full-width"
                disabled={actionLoading}
                on:click={abortRequest}
              >
                Abort Service
              </button>
            {/if}
          </div>
        </div>
      </div>
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
    padding: 1rem;
    max-width: 1200px;
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

  .header-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1.5rem;
  }

  .header-info h1 {
    margin: 0 0 0.25rem 0;
  }

  .provider {
    color: var(--text-muted, #666);
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .content-grid {
    display: grid;
    grid-template-columns: 1fr 300px;
    gap: 1.5rem;
  }

  .card {
    background: var(--bg-color, #fff);
    border: 1px solid var(--border-color, #e5e5e5);
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1rem;
  }

  .card h2 {
    margin: 0 0 1rem 0;
    font-size: 1rem;
  }

  .card h3 {
    margin: 0 0 0.75rem 0;
    font-size: 0.95rem;
  }

  .timeline {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .timeline-item {
    display: flex;
    justify-content: space-between;
    font-size: 0.9rem;
  }

  .timeline-label {
    color: var(--text-muted, #666);
  }

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
    font-size: 1.25rem;
  }

  .info-label {
    font-size: 0.85rem;
    color: var(--text-muted, #666);
  }

  .info-value {
    font-weight: 500;
  }

  .discord-link {
    display: inline-block;
    padding: 0.5rem 1rem;
    background: #5865f2;
    color: white;
    text-decoration: none;
    border-radius: 4px;
  }

  .discord-link:hover {
    background: #4752c4;
  }

  .notes {
    margin: 0;
    color: var(--text-color, #333);
    line-height: 1.5;
  }

  .review {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .rating {
    font-size: 1.5rem;
    font-weight: 600;
    color: #f59e0b;
  }

  .review-comment {
    margin: 0;
    color: var(--text-muted, #666);
    font-style: italic;
  }

  .review-form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .form-group label {
    font-size: 0.9rem;
    color: var(--text-muted, #666);
  }

  .form-group input,
  .form-group textarea {
    padding: 0.5rem;
    border: 1px solid var(--border-color, #ccc);
    border-radius: 4px;
    font-size: 1rem;
  }

  .form-actions {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
  }

  .service-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .service-title {
    font-weight: 500;
  }

  .service-type {
    font-size: 0.85rem;
    color: var(--text-muted, #666);
  }

  .view-service {
    margin-top: 0.5rem;
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
    font-size: 0.9rem;
  }

  .action-buttons {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .btn {
    padding: 0.5rem 1rem;
    border-radius: 4px;
    border: 1px solid transparent;
    cursor: pointer;
    font-size: 0.9rem;
  }

  .btn.primary {
    background: var(--accent-color, #4a9eff);
    color: white;
  }

  .btn.secondary {
    background: var(--bg-color, #fff);
    color: var(--text-color, #333);
    border-color: var(--border-color, #ccc);
  }

  .btn.danger {
    background: var(--error-bg);
    color: var(--error-color);
    border-color: var(--error-color);
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn.full-width {
    width: 100%;
  }

  /* Question-specific styles */
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

  .question-badge.large {
    padding: 0.375rem 1rem;
    font-size: 1rem;
  }

  .card.question-card {
    border-color: #8b5cf6;
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.05) 0%, rgba(139, 92, 246, 0.02) 100%);
  }

  .question-content {
    background: var(--bg-secondary, #f5f5f5);
    border-radius: 4px;
    padding: 1rem;
    margin-bottom: 0.75rem;
    border-left: 3px solid #8b5cf6;
  }

  .question-content p {
    margin: 0;
    font-size: 1.05rem;
    line-height: 1.6;
    color: var(--text-color, #333);
  }

  .question-meta {
    font-size: 0.85rem;
    color: var(--text-muted, #666);
  }

  .discussion-hint {
    margin: 0 0 1rem 0;
    color: var(--text-muted, #666);
    font-size: 0.9rem;
    line-height: 1.5;
  }

  @media (max-width: 768px) {
    .content-grid {
      grid-template-columns: 1fr;
    }

    .info-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
