<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { addToast } from '$lib/stores/toasts';

  const id = $page.params.id;
  const isNew = id === 'new';

  let name = $state('');
  let platform = $state('youtube');
  let channel_id = $state('');
  let channel_url = $state('');
  let description = $state('');
  let avatar_url = $state('');
  let active = $state(true);
  let display_order = $state(0);
  let youtube_playlist_id = $state('');

  let isLoading = $state(!isNew);
  let saving = $state(false);
  let deleting = $state(false);
  let error = $state(null);

  onMount(async () => {
    if (!isNew) {
      try {
        const response = await fetch(`/api/admin/creators/${id}`);
        if (!response.ok) throw new Error('Creator not found');
        const data = await response.json();
        name = data.name || '';
        platform = data.platform || 'youtube';
        channel_id = data.channel_id || '';
        channel_url = data.channel_url || '';
        description = data.description || '';
        avatar_url = data.avatar_url || '';
        active = data.active !== false;
        display_order = data.display_order || 0;
        youtube_playlist_id = data.youtube_playlist_id || '';
      } catch (err) {
        error = err.message;
      } finally {
        isLoading = false;
      }
    }
  });

  async function handleSave() {
    if (!name.trim()) {
      error = 'Name is required';
      return;
    }
    if (!channel_url.trim()) {
      error = 'Channel URL is required';
      return;
    }

    saving = true;
    error = null;

    try {
      const body = {
        name: name.trim(),
        platform,
        channel_id: channel_id.trim() || null,
        channel_url: channel_url.trim(),
        description: description.trim() || null,
        avatar_url: avatar_url.trim() || null,
        active,
        display_order: parseInt(display_order, 10) || 0,
        youtube_playlist_id: youtube_playlist_id.trim() || null
      };

      let response;
      if (isNew) {
        response = await fetch('/api/admin/creators', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
      } else {
        response = await fetch(`/api/admin/creators/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
      }

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Failed to save');

      addToast(isNew ? 'Creator added' : 'Creator updated', 'success');

      if (isNew && data.id) {
        goto(`/admin/creators/${data.id}`, { replaceState: true });
      }
    } catch (err) {
      error = err.message;
    } finally {
      saving = false;
    }
  }

  async function handleDelete() {
    if (!confirm('Are you sure you want to delete this creator?')) return;

    deleting = true;
    error = null;

    try {
      const response = await fetch(`/api/admin/creators/${id}`, { method: 'DELETE' });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to delete');
      }
      addToast('Creator deleted', 'success');
      goto('/admin/creators');
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
    <a href="/admin/creators">Creators</a>
    <span class="separator">/</span>
    <span>{isNew ? 'New' : 'Edit'}</span>
  </nav>

  <div class="page-header">
    <h1>{isNew ? 'Add Creator' : 'Edit Creator'}</h1>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if isLoading}
    <div class="loading">Loading...</div>
  {:else}
    <div class="form-card">
      <div class="form-group">
        <label for="name">Name <span class="required">*</span></label>
        <input id="name" type="text" bind:value={name} placeholder="Channel/creator name" />
      </div>

      <div class="form-row">
        <div class="form-group">
          <label for="platform">Platform <span class="required">*</span></label>
          <select id="platform" bind:value={platform}>
            <option value="youtube">YouTube</option>
            <option value="twitch">Twitch</option>
            <option value="kick">Kick</option>
          </select>
        </div>
        <div class="form-group">
          <label for="display_order">Display Order</label>
          <input id="display_order" type="number" bind:value={display_order} min="0" />
          <span class="hint">Lower numbers appear first</span>
        </div>
      </div>

      <div class="form-group">
        <label for="channel_url">Channel URL <span class="required">*</span></label>
        <input id="channel_url" type="url" bind:value={channel_url} placeholder="https://www.youtube.com/@channelname" />
      </div>

      <div class="form-group">
        <label for="channel_id">Channel ID</label>
        <input id="channel_id" type="text" bind:value={channel_id} placeholder={platform === 'youtube' ? 'UCxxxxxxxxx (YouTube channel ID)' : platform === 'twitch' ? 'username (Twitch login)' : ''} />
        <span class="hint">
          {#if platform === 'youtube'}
            Required for YouTube enrichment. Find it in the channel URL or via YouTube settings.
          {:else if platform === 'twitch'}
            Twitch login name. If empty, will be extracted from the channel URL.
          {:else}
            Not used for Kick.
          {/if}
        </span>
      </div>

      {#if platform === 'youtube'}
        <div class="form-group">
          <label for="youtube_playlist_id">Playlist ID (optional)</label>
          <input id="youtube_playlist_id" type="text" bind:value={youtube_playlist_id} placeholder="PLxxxxxxxxx" />
          <span class="hint">If set, only videos from this playlist will be shown and trigger notifications. Leave empty for all uploads.</span>
        </div>
      {/if}

      <div class="form-group">
        <label for="description">Description</label>
        <textarea id="description" bind:value={description} rows="2" placeholder="Brief description of the creator"></textarea>
      </div>

      <div class="form-group">
        <label for="avatar_url">Avatar URL (fallback)</label>
        <input id="avatar_url" type="url" bind:value={avatar_url} placeholder="https://..." />
        <span class="hint">Used if API enrichment doesn't provide an avatar</span>
      </div>

      <div class="form-row-toggles">
        <label class="toggle-label">
          <input type="checkbox" bind:checked={active} />
          <span>Active</span>
          <span class="hint-inline">Visible on the landing page</span>
        </label>
      </div>

      <div class="form-actions">
        <button class="btn btn-cancel" onclick={() => goto('/admin/creators')}>
          Cancel
        </button>

        {#if !isNew}
          <button class="btn btn-danger" onclick={handleDelete} disabled={deleting}>
            {deleting ? 'Deleting...' : 'Delete'}
          </button>
        {/if}

        <button class="btn btn-primary" onclick={handleSave} disabled={saving || !name.trim() || !channel_url.trim()}>
          {saving ? 'Saving...' : isNew ? 'Add Creator' : 'Save'}
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
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }

  .form-row-toggles {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
  }

  .toggle-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    font-size: 0.875rem;
  }

  .toggle-label input[type="checkbox"] {
    width: 1rem;
    height: 1rem;
    accent-color: var(--accent-color);
  }

  .hint-inline {
    color: var(--text-muted);
    font-size: 0.75rem;
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

  .btn-danger {
    background-color: var(--error-color);
    border: 1px solid var(--error-color);
    color: white;
  }

  .btn-danger:hover:not(:disabled) {
    filter: brightness(0.9);
  }

  @media (max-width: 899px) {
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
