<script>
  // @ts-nocheck
  import { goto } from '$app/navigation';
  import { addToast } from '$lib/stores/toasts';

  let title = '';
  let description = '';
  let start_date = '';
  let end_date = '';
  let location = '';
  let type = 'player_run';
  let link = '';

  let submitting = false;
  let error = null;

  async function handleSubmit() {
    if (!title.trim()) {
      error = 'Title is required';
      return;
    }
    if (!start_date) {
      error = 'Start date is required';
      return;
    }

    submitting = true;
    error = null;

    try {
      const body = {
        title: title.trim(),
        description: description.trim() || null,
        start_date: new Date(start_date).toISOString(),
        end_date: end_date ? new Date(end_date).toISOString() : null,
        location: location.trim() || null,
        type,
        link: link.trim() || null
      };

      const response = await fetch('/api/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Failed to submit event');

      addToast('Event submitted for review', 'success');
      goto('/');
    } catch (err) {
      error = err.message;
    } finally {
      submitting = false;
    }
  }
</script>

<svelte:head>
  <title>Submit Event - Entropia Nexus</title>
</svelte:head>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/">Home</a>
    <span class="separator">/</span>
    <span>Submit Event</span>
  </nav>

  <div class="page-header">
    <h1>Submit an Event</h1>
    <p class="page-subtitle">
      Submit a community event for review. Once approved by an admin, it will appear on the landing page.
    </p>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  <div class="form-card">
    <div class="form-group">
      <label for="title">Event Title <span class="required">*</span></label>
      <input id="title" type="text" bind:value={title} maxlength="200" placeholder="What is the event called?" />
    </div>

    <div class="form-group">
      <label for="description">Description</label>
      <textarea id="description" bind:value={description} maxlength="2000" rows="4" placeholder="Describe the event, rules, prizes, etc."></textarea>
      <span class="hint">{description.length}/2000</span>
    </div>

    <div class="form-row">
      <div class="form-group">
        <label for="start_date">Start Date & Time <span class="required">*</span></label>
        <input id="start_date" type="datetime-local" bind:value={start_date} />
      </div>
      <div class="form-group">
        <label for="end_date">End Date & Time</label>
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
          <option value="player_run">Player Run Event</option>
          <option value="official">Official Event</option>
        </select>
      </div>
    </div>

    <div class="form-group">
      <label for="link">Link (optional)</label>
      <input id="link" type="url" bind:value={link} placeholder="https://forum.entropiauniverse.com/..." />
      <span class="hint">Forum post, signup page, or other details</span>
    </div>

    <div class="form-actions">
      <button class="btn btn-cancel" on:click={() => goto('/')}>Cancel</button>
      <button class="btn btn-primary" on:click={handleSubmit} disabled={submitting || !title.trim() || !start_date}>
        {submitting ? 'Submitting...' : 'Submit Event'}
      </button>
    </div>
  </div>
</div>

<style>
  .page-container {
    padding: 2rem 1.5rem;
    padding-bottom: 3rem;
    max-width: 700px;
    margin: 0 auto;
    height: 100%;
    overflow-y: auto;
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
    margin: 0 0 0.5rem 0;
  }

  .page-subtitle {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.9375rem;
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    border: 1px solid var(--error-color);
    margin-bottom: 1rem;
  }

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

  @media (max-width: 599px) {
    .page-container {
      padding: 1rem;
    }

    .form-row {
      grid-template-columns: 1fr;
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
