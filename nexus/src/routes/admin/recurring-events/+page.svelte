<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { addToast } from '$lib/stores/toasts.js';

  let events = $state([]);
  let isLoading = $state(true);
  let error = $state(null);

  // Create form
  let newName = $state('');
  let newDescription = $state('');
  let newColor = $state('#ff6b35');
  let creating = $state(false);

  // Edit state
  let editingId = $state(null);
  let editName = $state('');
  let editDescription = $state('');
  let editColor = $state('');
  let saving = $state(false);

  onMount(() => { loadEvents(); });

  async function loadEvents() {
    isLoading = true;
    error = null;
    try {
      const res = await fetch('/api/admin/recurring-events');
      if (!res.ok) throw new Error('Failed to load recurring events');
      events = await res.json();
    } catch (err) {
      error = err.message;
    } finally {
      isLoading = false;
    }
  }

  async function handleCreate() {
    if (!newName.trim()) return;
    creating = true;
    try {
      const res = await fetch('/api/admin/recurring-events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ Name: newName.trim(), Description: newDescription.trim() || null, Color: newColor })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to create');
      newName = '';
      newDescription = '';
      newColor = '#ff6b35';
      addToast('Recurring event created', 'success');
      await loadEvents();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      creating = false;
    }
  }

  function startEdit(event) {
    editingId = event.Id;
    editName = event.Name;
    editDescription = event.Description || '';
    editColor = event.Color;
  }

  function cancelEdit() {
    editingId = null;
  }

  async function handleSave() {
    if (!editName.trim()) return;
    saving = true;
    try {
      const res = await fetch(`/api/admin/recurring-events/${editingId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ Name: editName.trim(), Description: editDescription.trim() || null, Color: editColor })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to update');
      editingId = null;
      addToast('Recurring event updated', 'success');
      await loadEvents();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      saving = false;
    }
  }

  async function handleDelete(event) {
    if (!confirm(`Delete "${event.Name}"?`)) return;
    try {
      const res = await fetch(`/api/admin/recurring-events/${event.Id}`, { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to delete');
      addToast('Recurring event deleted', 'success');
      await loadEvents();
    } catch (err) {
      addToast(err.message, 'error');
    }
  }
</script>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/admin">Admin</a>
    <span class="separator">/</span>
    <span>Recurring Events</span>
  </nav>

  <div class="page-header">
    <h1>Recurring Events</h1>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  <!-- Create form -->
  <div class="create-form">
    <h3>Add Recurring Event</h3>
    <div class="form-row">
      <input type="text" bind:value={newName} placeholder="Event name (e.g. Migration)" maxlength="100" class="form-input" />
      <input type="text" bind:value={newDescription} placeholder="Description (optional)" class="form-input desc-input" />
      <label class="color-field">
        <input type="color" bind:value={newColor} />
        <span class="color-preview" style="background: {newColor}"></span>
      </label>
      <button onclick={handleCreate} disabled={creating || !newName.trim()} class="btn btn-primary">
        {creating ? 'Creating...' : 'Add'}
      </button>
    </div>
  </div>

  {#if isLoading}
    <div class="loading">Loading...</div>
  {:else if events.length === 0}
    <div class="empty-state">No recurring events yet.</div>
  {:else}
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>Color</th>
            <th>Name</th>
            <th>Description</th>
            <th>Linked Mob Areas</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each events as event}
            {#if editingId === event.Id}
              <tr class="editing-row">
                <td>
                  <label class="color-field">
                    <input type="color" bind:value={editColor} />
                    <span class="color-preview" style="background: {editColor}"></span>
                  </label>
                </td>
                <td><input type="text" bind:value={editName} maxlength="100" class="form-input inline-input" /></td>
                <td><input type="text" bind:value={editDescription} class="form-input inline-input" /></td>
                <td>{event.LinkedMobAreas}</td>
                <td class="actions-cell">
                  <button onclick={handleSave} disabled={saving || !editName.trim()} class="btn btn-sm btn-primary">Save</button>
                  <button onclick={cancelEdit} class="btn btn-sm btn-secondary">Cancel</button>
                </td>
              </tr>
            {:else}
              <tr>
                <td><span class="color-dot" style="background: {event.Color}"></span></td>
                <td class="name-cell">{event.Name}</td>
                <td class="desc-cell">{event.Description || '—'}</td>
                <td>{event.LinkedMobAreas}</td>
                <td class="actions-cell">
                  <button onclick={() => startEdit(event)} class="btn btn-sm btn-secondary">Edit</button>
                  <button onclick={() => handleDelete(event)} class="btn btn-sm btn-danger" disabled={event.LinkedMobAreas > 0}>Delete</button>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .page-container {
    max-width: 1000px;
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

  .create-form {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 1rem 1.25rem;
    margin-bottom: 1.5rem;
  }

  .create-form h3 {
    margin: 0 0 0.75rem;
    font-size: 0.9rem;
    color: var(--text-muted);
  }

  .form-row {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .form-input {
    padding: 0.4rem 0.75rem;
    background: var(--primary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.875rem;
    min-width: 160px;
  }

  .desc-input {
    flex: 1;
    min-width: 200px;
  }

  .inline-input {
    width: 100%;
    min-width: auto;
  }

  .color-field {
    position: relative;
    cursor: pointer;
    display: flex;
    align-items: center;
  }

  .color-field input[type="color"] {
    position: absolute;
    opacity: 0;
    width: 28px;
    height: 28px;
    cursor: pointer;
  }

  .color-preview {
    display: inline-block;
    width: 28px;
    height: 28px;
    border-radius: 4px;
    border: 1px solid var(--border-color);
  }

  .color-dot {
    display: inline-block;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    border: 1px solid var(--border-color);
  }

  .loading, .empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted);
  }

  .table-container {
    overflow-x: auto;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
  }

  .data-table th {
    text-align: left;
    padding: 0.75rem;
    border-bottom: 2px solid var(--border-color);
    color: var(--text-muted);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .data-table td {
    padding: 0.75rem;
    border-bottom: 1px solid var(--border-color);
    vertical-align: middle;
  }

  .name-cell {
    font-weight: 500;
  }

  .desc-cell {
    color: var(--text-muted);
  }

  .actions-cell {
    display: flex;
    gap: 0.35rem;
    white-space: nowrap;
  }

  .editing-row {
    background: var(--hover-color);
  }

  .btn {
    padding: 0.4rem 0.8rem;
    border-radius: 4px;
    border: 1px solid var(--border-color);
    cursor: pointer;
    font-size: 0.875rem;
    transition: background-color 0.15s;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-sm {
    padding: 0.25rem 0.5rem;
    font-size: 0.8rem;
  }

  .btn-primary {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .btn-primary:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .btn-secondary {
    background: var(--secondary-color);
    color: var(--text-color);
  }

  .btn-secondary:hover:not(:disabled) {
    background: var(--hover-color);
  }

  .btn-danger {
    background: var(--error-bg);
    color: var(--error-color);
    border-color: var(--error-color);
  }

  .btn-danger:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  @media (max-width: 600px) {
    .form-row {
      flex-direction: column;
      align-items: stretch;
    }

    .form-input {
      min-width: auto;
    }
  }
</style>
