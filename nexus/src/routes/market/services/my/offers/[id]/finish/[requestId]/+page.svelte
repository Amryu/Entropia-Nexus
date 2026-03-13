<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import DashboardNav from "$lib/components/services/DashboardNav.svelte";
  import RequestStatusBadge from "$lib/components/services/RequestStatusBadge.svelte";
  import { goto } from '$app/navigation';
  import { apiPut } from '$lib/util';

  let { data } = $props();

  let service = $derived(data.service);
  let request = $derived(data.request);

  let loading = $state(false);
  let error = $state(null);

  // Form fields
  let actualEnd = $state(new Date().toISOString().slice(0, 16)); // datetime-local format
  let actualStart = $state(request.actual_start
    ? new Date(request.actual_start).toISOString().slice(0, 16)
    : new Date().toISOString().slice(0, 16));
  let actualPayment = $state(request.final_payment || request.estimated_payment || '');
  let providerNotes = $state('');
  let breakMinutes = $state('');
  let actualDecay = $state('');

  // Check if this is a DPS/heal service that needs break/decay tracking
  let isDurationService = $derived(service.type === 'healing' || service.type === 'dps');

  // Calculate duration
  let durationMinutes = $derived(actualStart && actualEnd
    ? Math.round((new Date(actualEnd) - new Date(actualStart)) / (1000 * 60))
    : 0);

  function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString();
  }

  async function handleFinish() {
    if (durationMinutes < 0) {
      error = 'End time cannot be before start time';
      return;
    }

    loading = true;
    error = null;

    try {
      const payload = {
        status: 'completed',
        actual_start: new Date(actualStart).toISOString(),
        actual_end: new Date(actualEnd).toISOString(),
        actual_payment: actualPayment ? parseFloat(actualPayment) : null,
        service_notes: providerNotes || null
      };

      // Add DPS/heal-specific fields
      if (isDurationService) {
        if (breakMinutes) {
          payload.break_minutes = parseInt(breakMinutes);
        }
        if (actualDecay) {
          payload.actual_decay_ped = parseFloat(actualDecay);
        }
      }

      const response = await apiPut(fetch, `/api/services/my/requests/${request.id}/status`, payload);

      if (response.error) {
        error = response.error;
      } else {
        goto(`/market/services/my/offers/${service.id}`);
      }
    } catch (err) {
      error = 'Failed to complete request. Please try again.';
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Finish Request | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
<div class="page-container">
  <div class="breadcrumb">
    <a href="/market/services/my">My Services</a>
    <span>/</span>
    <a href="/market/services/my/offers">My Offers</a>
    <span>/</span>
    <a href="/market/services/my/offers/{service.id}">{service.title}</a>
    <span>/</span>
    <span>Finish Request</span>
  </div>

  <h1>Finish Request</h1>

  <DashboardNav />

  <div class="finish-form">
    <div class="request-summary">
      <h2>Request Details</h2>
      <div class="summary-grid">
        <div class="summary-item">
          <span class="label">Requester</span>
          <span class="value">{request.requester_name}</span>
        </div>
        <div class="summary-item">
          <span class="label">Status</span>
          <RequestStatusBadge status={request.status} />
        </div>
        <div class="summary-item">
          <span class="label">Original Start</span>
          <span class="value">{formatDateTime(request.actual_start || request.requested_start)}</span>
        </div>
        {#if request.requested_duration_minutes}
          <div class="summary-item">
            <span class="label">Requested Duration</span>
            <span class="value">{request.requested_duration_minutes} minutes</span>
          </div>
        {/if}
        {#if request.estimated_payment}
          <div class="summary-item">
            <span class="label">Estimated Payment</span>
            <span class="value">{request.estimated_payment} PED</span>
          </div>
        {/if}
      </div>
    </div>

    {#if error}
      <div class="error-banner">{error}</div>
    {/if}

    <div class="form-section">
      <h2>Final Details</h2>

      <div class="form-row">
        <div class="form-group">
          <label for="actual-start">Actual Start Time</label>
          <input
            type="datetime-local"
            id="actual-start"
            bind:value={actualStart}
          />
          <span class="help-text">Correct if the service started at a different time</span>
        </div>

        <div class="form-group">
          <label for="actual-end">End Time</label>
          <input
            type="datetime-local"
            id="actual-end"
            bind:value={actualEnd}
          />
        </div>
      </div>

      <div class="duration-display" class:negative={durationMinutes < 0}>
        <span class="label">Duration:</span>
        <span class="value">
          {#if durationMinutes >= 60}
            {Math.floor(durationMinutes / 60)}h {durationMinutes % 60}m
          {:else}
            {durationMinutes} minutes
          {/if}
        </span>
      </div>

      <div class="form-group">
        <label for="actual-payment">Payment Received (PED)</label>
        <input
          type="number"
          id="actual-payment"
          bind:value={actualPayment}
          step="0.01"
          min="0"
          placeholder="0.00"
        />
        <span class="help-text">Leave blank if no payment was received</span>
      </div>

      {#if isDurationService}
        <div class="form-row">
          <div class="form-group">
            <label for="break-minutes">Break Time (minutes)</label>
            <input
              type="number"
              id="break-minutes"
              bind:value={breakMinutes}
              min="0"
              step="1"
              placeholder="0"
            />
            <span class="help-text">Total time spent on breaks during the session</span>
          </div>

          <div class="form-group">
            <label for="actual-decay">Tool Decay (PED)</label>
            <input
              type="number"
              id="actual-decay"
              bind:value={actualDecay}
              step="0.01"
              min="0"
              placeholder="0.00"
            />
            <span class="help-text">Actual decay cost for this session</span>
          </div>
        </div>

        {#if breakMinutes && parseInt(breakMinutes) > 0}
          <div class="effective-duration">
            <span class="label">Effective Duration:</span>
            <span class="value">
              {#if (durationMinutes - parseInt(breakMinutes)) >= 60}
                {Math.floor((durationMinutes - parseInt(breakMinutes)) / 60)}h {(durationMinutes - parseInt(breakMinutes)) % 60}m
              {:else}
                {durationMinutes - parseInt(breakMinutes)} minutes
              {/if}
            </span>
            <span class="note">(excluding breaks)</span>
          </div>
        {/if}
      {/if}

      <div class="form-group">
        <label for="provider-notes">Notes (optional)</label>
        <textarea
          id="provider-notes"
          bind:value={providerNotes}
          rows="3"
          placeholder="Any additional notes about this service..."
        ></textarea>
      </div>
    </div>

    <div class="form-actions">
      <a href="/market/services/my/offers/{service.id}" class="btn secondary">Cancel</a>
      <button
        type="button"
        class="btn primary"
        disabled={loading || durationMinutes < 0}
        onclick={handleFinish}
      >
        {loading ? 'Completing...' : 'Complete Request'}
      </button>
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
    padding: 1rem;
    max-width: 800px;
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

  h1 {
    margin: 0 0 1.5rem 0;
  }

  .finish-form {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .request-summary {
    background: var(--bg-secondary, #f5f5f5);
    border: 1px solid var(--border-color, #e5e5e5);
    border-radius: 8px;
    padding: 1.25rem;
  }

  .request-summary h2 {
    margin: 0 0 1rem 0;
    font-size: 1rem;
  }

  .summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
  }

  .summary-item {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .summary-item .label {
    font-size: 0.85rem;
    color: var(--text-muted, #666);
  }

  .summary-item .value {
    font-weight: 500;
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
  }

  .form-section {
    background: var(--bg-color, #fff);
    border: 1px solid var(--border-color, #e5e5e5);
    border-radius: 8px;
    padding: 1.25rem;
  }

  .form-section h2 {
    margin: 0 0 1.25rem 0;
    font-size: 1rem;
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  @media (max-width: 600px) {
    .form-row {
      grid-template-columns: 1fr;
    }
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    margin-bottom: 1rem;
  }

  .form-group label {
    font-weight: 500;
    font-size: 0.9rem;
  }

  .form-group input,
  .form-group textarea {
    padding: 0.625rem;
    border: 1px solid var(--border-color, #ccc);
    border-radius: 4px;
    font-size: 1rem;
    background: var(--bg-color, #fff);
  }

  .form-group input:focus,
  .form-group textarea:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .help-text {
    font-size: 0.8rem;
    color: var(--text-muted, #666);
  }

  .duration-display {
    display: flex;
    gap: 0.5rem;
    padding: 0.75rem;
    background: var(--success-bg);
    color: var(--success-color);
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .duration-display.negative {
    background: var(--error-bg);
    color: var(--error-color);
  }

  .duration-display .label {
    color: var(--text-muted, #666);
  }

  .duration-display .value {
    font-weight: 600;
  }

  .effective-duration {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    padding: 0.75rem;
    background: var(--bg-secondary, #f5f5f5);
    border-radius: 4px;
    margin-bottom: 1rem;
    font-size: 0.9rem;
  }

  .effective-duration .label {
    color: var(--text-muted, #666);
  }

  .effective-duration .value {
    font-weight: 600;
  }

  .effective-duration .note {
    color: var(--text-muted, #666);
    font-size: 0.85rem;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
  }

  .btn {
    padding: 0.625rem 1.25rem;
    border-radius: 4px;
    text-decoration: none;
    font-size: 0.95rem;
    cursor: pointer;
    border: 1px solid transparent;
  }

  .btn.primary {
    background: var(--accent-color, #4a9eff);
    color: white;
  }

  .btn.primary:hover:not(:disabled) {
    background: var(--accent-color-hover, #3a8eef);
  }

  .btn.secondary {
    background: var(--bg-color, #fff);
    color: var(--text-color, #333);
    border-color: var(--border-color, #ccc);
  }

  .btn.secondary:hover {
    background: var(--hover-color, #f0f0f0);
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
