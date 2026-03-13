<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { addToast } from '$lib/stores/toasts';

  const id = $page.params.id;

  let event = $state(null);
  let isLoading = $state(true);
  let saving = $state(false);
  let error = $state(null);

  // Edit form fields
  let title = $state('');
  let description = $state('');
  let start_date = $state('');
  let end_date = $state('');
  let location = $state('');
  let type = $state('player_run');
  let link = $state('');
  let image_url = $state('');

  let denyReason = $state('');
  let showDenyDialog = $state(false);
  let approving = $state(false);
  let denying = $state(false);
  let deleting = $state(false);

  onMount(async () => {
    try {
      const response = await fetch(`/api/admin/events/${id}`);
      if (!response.ok) throw new Error('Event not found');
      const data = await response.json();
      event = data;
      title = data.title || '';
      description = data.description || '';
      start_date = data.start_date ? toLocalDatetime(data.start_date) : '';
      end_date = data.end_date ? toLocalDatetime(data.end_date) : '';
      location = data.location || '';
      type = data.type || 'player_run';
      link = data.link || '';
      image_url = data.image_url || '';
    } catch (err) {
      error = err.message;
    } finally {
      isLoading = false;
    }
  });

  function toLocalDatetime(dateStr) {
    const d = new Date(dateStr);
    const offset = d.getTimezoneOffset();
    const local = new Date(d.getTime() - offset * 60000);
    return local.toISOString().slice(0, 16);
  }

  function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  }

  async function handleSave() {
    if (!title.trim()) {
      error = 'Title is required';
      return;
    }

    saving = true;
    error = null;

    try {
      const body = {
        title: title.trim(),
        description: description.trim() || null,
        start_date: start_date ? new Date(start_date).toISOString() : null,
        end_date: end_date ? new Date(end_date).toISOString() : null,
        location: location.trim() || null,
        type,
        link: link.trim() || null,
        image_url: image_url.trim() || null
      };

      const response = await fetch(`/api/admin/events/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Failed to save');

      event = data;
      addToast('Event updated', 'success');
    } catch (err) {
      error = err.message;
    } finally {
      saving = false;
    }
  }

  async function handleApprove() {
    approving = true;
    error = null;

    try {
      const response = await fetch(`/api/admin/events/${id}/approve`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Failed to approve');

      event = data;
      addToast('Event approved', 'success');
    } catch (err) {
      error = err.message;
    } finally {
      approving = false;
    }
  }

  async function handleDeny() {
    denying = true;
    error = null;

    try {
      const response = await fetch(`/api/admin/events/${id}/deny`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: denyReason.trim() || null })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Failed to deny');

      event = data;
      showDenyDialog = false;
      denyReason = '';
      addToast('Event denied', 'success');
    } catch (err) {
      error = err.message;
    } finally {
      denying = false;
    }
  }

  async function handleDelete() {
    if (!confirm('Are you sure you want to delete this event?')) return;

    deleting = true;
    error = null;

    try {
      const response = await fetch(`/api/admin/events/${id}`, { method: 'DELETE' });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to delete');
      }
      addToast('Event deleted', 'success');
      goto('/admin/events');
    } catch (err) {
      error = err.message;
      deleting = false;
    }
  }
</script>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/admin">Admin</a>
    <span class="separator">/</span>
    <a href="/admin/events">Events</a>
    <span class="separator">/</span>
    <span>Detail</span>
  </nav>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if isLoading}
    <div class="loading">Loading...</div>
  {:else if event}
    <!-- State banner -->
    <div class="state-banner" class:pending={event.state === 'pending'} class:approved={event.state === 'approved'} class:denied={event.state === 'denied'}>
      <div class="state-info">
        <span class="state-label">
          {event.state === 'pending' ? 'Pending Review' : event.state === 'approved' ? 'Approved' : 'Denied'}
        </span>
        {#if event.submitted_by_name}
          <span class="state-meta">Submitted by {event.submitted_by_name}</span>
        {/if}
        {#if event.admin_note}
          <span class="state-meta">Note: {event.admin_note}</span>
        {/if}
      </div>
      {#if event.state === 'pending'}
        <div class="state-actions">
          <button class="btn btn-success" onclick={handleApprove} disabled={approving}>
            {approving ? 'Approving...' : 'Approve'}
          </button>
          <button class="btn btn-danger-outline" onclick={() => { showDenyDialog = true; }}>
            Deny
          </button>
        </div>
      {/if}
    </div>

    <!-- Deny dialog -->
    {#if showDenyDialog}
      <div class="dialog-overlay" role="presentation" onclick={() => { showDenyDialog = false; }} onkeydown={(e) => e.key === 'Escape' && (showDenyDialog = false)}>
        <div class="dialog" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()} role="dialog" tabindex="-1" aria-modal="true">
          <h3>Deny Event</h3>
          <div class="form-group">
            <label for="deny-reason">Reason (optional)</label>
            <textarea id="deny-reason" bind:value={denyReason} rows="3" placeholder="Reason for denying this event"></textarea>
          </div>
          <div class="dialog-actions">
            <button class="btn btn-cancel" onclick={() => { showDenyDialog = false; }}>Cancel</button>
            <button class="btn btn-danger" onclick={handleDeny} disabled={denying}>
              {denying ? 'Denying...' : 'Deny Event'}
            </button>
          </div>
        </div>
      </div>
    {/if}

    <!-- Edit form -->
    <div class="page-header">
      <h1>Edit Event</h1>
    </div>

    <div class="form-card">
      <div class="form-group">
        <label for="title">Title <span class="required">*</span></label>
        <input id="title" type="text" bind:value={title} maxlength="200" />
      </div>

      <div class="form-group">
        <label for="description">Description</label>
        <textarea id="description" bind:value={description} maxlength="2000" rows="4" placeholder="Event description"></textarea>
        <span class="hint">{description.length}/2000</span>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label for="start_date">Start Date <span class="required">*</span></label>
          <input id="start_date" type="datetime-local" bind:value={start_date} />
        </div>
        <div class="form-group">
          <label for="end_date">End Date</label>
          <input id="end_date" type="datetime-local" bind:value={end_date} />
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label for="location">Location</label>
          <input id="location" type="text" bind:value={location} maxlength="200" placeholder="e.g. Twin Peaks, Calypso" />
        </div>
        <div class="form-group">
          <label for="type">Type</label>
          <select id="type" bind:value={type}>
            <option value="player_run">Player Run</option>
            <option value="official">Official</option>
          </select>
        </div>
      </div>

      <div class="form-group">
        <label for="link">Link</label>
        <input id="link" type="url" bind:value={link} placeholder="https://..." />
      </div>

      <div class="form-group">
        <label for="image_url">Image URL</label>
        <input id="image_url" type="url" bind:value={image_url} placeholder="https://..." />
      </div>

      <div class="form-actions">
        <button class="btn btn-cancel" onclick={() => goto('/admin/events')}>Back</button>
        <button class="btn btn-danger" onclick={handleDelete} disabled={deleting}>
          {deleting ? 'Deleting...' : 'Delete'}
        </button>
        <button class="btn btn-primary" onclick={handleSave} disabled={saving || !title.trim()}>
          {saving ? 'Saving...' : 'Save'}
        </button>
      </div>
    </div>
  {/if}
</div>

<style>
  .page-container {
    max-width: 800px;
    padding-bottom: 2rem;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .separator {
    color: var(--text-muted);
  }

  .page-header {
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
    margin: 0;
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    border: 1px solid var(--error-color);
    margin-bottom: 1rem;
  }

  .loading {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted);
  }

  /* State banner */
  .state-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .state-banner.pending {
    background: rgba(234, 179, 8, 0.1);
    border: 1px solid rgba(234, 179, 8, 0.3);
  }

  .state-banner.approved {
    background: var(--success-bg);
    border: 1px solid var(--success-color);
  }

  .state-banner.denied {
    background: var(--error-bg);
    border: 1px solid var(--error-color);
  }

  .state-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .state-label {
    font-weight: 600;
    font-size: 0.9375rem;
  }

  .state-meta {
    font-size: 0.8125rem;
    color: var(--text-muted);
  }

  .state-actions {
    display: flex;
    gap: 0.5rem;
  }

  /* Form card */
  .form-card {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
  }

  .form-group {
    margin-bottom: 1.25rem;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.375rem;
    font-weight: 500;
    font-size: 0.875rem;
  }

  .required {
    color: var(--error-color);
  }

  .form-group input,
  .form-group textarea,
  .form-group select {
    width: 100%;
    padding: 0.5rem;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.875rem;
    box-sizing: border-box;
  }

  .form-group input:focus,
  .form-group textarea:focus,
  .form-group select:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .hint {
    display: block;
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
    text-align: right;
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-color);
  }

  /* Buttons */
  .btn {
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-cancel {
    background-color: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .btn-cancel:hover:not(:disabled) {
    background-color: var(--hover-color);
  }

  .btn-primary {
    background-color: var(--accent-color);
    border: 1px solid var(--accent-color);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background-color: var(--accent-color-hover);
  }

  .btn-success {
    background-color: var(--success-color);
    border: 1px solid var(--success-color);
    color: white;
  }

  .btn-success:hover:not(:disabled) {
    filter: brightness(0.9);
  }

  .btn-danger {
    background-color: var(--error-color);
    border: 1px solid var(--error-color);
    color: white;
  }

  .btn-danger:hover:not(:disabled) {
    filter: brightness(0.9);
  }

  .btn-danger-outline {
    background-color: transparent;
    border: 1px solid var(--error-color);
    color: var(--error-color);
  }

  .btn-danger-outline:hover:not(:disabled) {
    background-color: var(--error-bg);
  }

  /* Dialog */
  .dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }

  .dialog {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    width: 100%;
    max-width: 480px;
    margin: 1rem;
  }

  .dialog h3 {
    margin: 0 0 1rem 0;
    font-size: 1.125rem;
  }

  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  @media (max-width: 899px) {
    .form-row {
      grid-template-columns: 1fr;
    }

    .state-banner {
      flex-direction: column;
      align-items: flex-start;
    }

    .form-actions {
      flex-direction: column;
    }

    .form-actions .btn {
      width: 100%;
      text-align: center;
    }
  }
</style>
