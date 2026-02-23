<script>
  // @ts-nocheck
  import { invalidateAll } from '$app/navigation';

  export let data;

  let showCreateForm = false;
  let creating = false;
  let createError = '';
  let newClientResult = null;
  let rotatingSecret = null;
  let rotatedSecret = null;
  let deletingClient = null;

  // Create form fields
  let formName = '';
  let formDescription = '';
  let formWebsiteUrl = '';
  let formRedirectUri = '';

  async function createClient() {
    if (!formName.trim() || !formRedirectUri.trim()) return;
    creating = true;
    createError = '';

    try {
      const res = await fetch('/api/oauth/clients', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formName.trim(),
          description: formDescription.trim() || undefined,
          website_url: formWebsiteUrl.trim() || undefined,
          redirect_uris: formRedirectUri.split('\n').map(u => u.trim()).filter(Boolean)
        })
      });
      const result = await res.json();
      if (!res.ok) {
        createError = result.error || 'Failed to create client';
        return;
      }
      newClientResult = result;
      showCreateForm = false;
      formName = '';
      formDescription = '';
      formWebsiteUrl = '';
      formRedirectUri = '';
      await invalidateAll();
    } catch {
      createError = 'Network error';
    } finally {
      creating = false;
    }
  }

  async function rotateSecret(clientId) {
    if (!confirm('Are you sure? The old secret will stop working immediately.')) return;
    rotatingSecret = clientId;
    try {
      const res = await fetch(`/api/oauth/clients/${clientId}/rotate-secret`, { method: 'POST' });
      const result = await res.json();
      if (res.ok) {
        rotatedSecret = { clientId, secret: result.clientSecret };
      }
    } finally {
      rotatingSecret = null;
    }
  }

  async function deleteOAuthClient(clientId) {
    if (!confirm('Are you sure? This will revoke all tokens and cannot be undone.')) return;
    deletingClient = clientId;
    try {
      await fetch(`/api/oauth/clients/${clientId}`, { method: 'DELETE' });
      await invalidateAll();
    } finally {
      deletingClient = null;
    }
  }

  function dismissNewClient() {
    newClientResult = null;
  }

  function dismissRotatedSecret() {
    rotatedSecret = null;
  }
</script>

<svelte:head>
  <title>Developer Applications | Settings | Entropia Nexus</title>
</svelte:head>

<div class="page-container">
  <div class="page-header">
    <h1>Developer Applications</h1>
    <p class="subtitle">Register OAuth applications that can access the Entropia Nexus API on behalf of users.</p>
  </div>

  {#if newClientResult}
    <div class="secret-banner">
      <h3>Application Created</h3>
      <p>Save your client secret now. It will not be shown again.</p>
      <div class="secret-field">
        <label>Client ID</label>
        <code>{newClientResult.clientId}</code>
      </div>
      <div class="secret-field">
        <label>Client Secret</label>
        <code>{newClientResult.clientSecret}</code>
      </div>
      <button class="btn-secondary" on:click={dismissNewClient}>I've saved it</button>
    </div>
  {/if}

  {#if rotatedSecret}
    <div class="secret-banner">
      <h3>Secret Rotated</h3>
      <p>Save your new client secret now. It will not be shown again.</p>
      <div class="secret-field">
        <label>New Client Secret</label>
        <code>{rotatedSecret.secret}</code>
      </div>
      <button class="btn-secondary" on:click={dismissRotatedSecret}>I've saved it</button>
    </div>
  {/if}

  <div class="clients-header">
    <span class="count">{data.clients.length} / {data.maxClients} applications</span>
    {#if data.clients.length < data.maxClients}
      <button class="btn-primary" on:click={() => showCreateForm = !showCreateForm}>
        {showCreateForm ? 'Cancel' : 'New Application'}
      </button>
    {/if}
  </div>

  {#if showCreateForm}
    <div class="create-form">
      <div class="form-group">
        <label for="name">Application Name *</label>
        <input id="name" type="text" bind:value={formName} maxlength="100" placeholder="My App" />
      </div>
      <div class="form-group">
        <label for="description">Description</label>
        <input id="description" type="text" bind:value={formDescription} maxlength="500" placeholder="What does your app do?" />
      </div>
      <div class="form-group">
        <label for="website">Website URL</label>
        <input id="website" type="url" bind:value={formWebsiteUrl} placeholder="https://example.com" />
      </div>
      <div class="form-group">
        <label for="redirects">Redirect URIs * (one per line)</label>
        <textarea id="redirects" bind:value={formRedirectUri} rows="3" placeholder="https://example.com/callback"></textarea>
      </div>
      {#if createError}
        <div class="error-msg">{createError}</div>
      {/if}
      <button class="btn-primary" on:click={createClient} disabled={creating || !formName.trim() || !formRedirectUri.trim()}>
        {creating ? 'Creating...' : 'Create Application'}
      </button>
    </div>
  {/if}

  {#if data.clients.length === 0 && !showCreateForm}
    <div class="empty-state">
      <p>No applications registered yet.</p>
    </div>
  {:else}
    <div class="clients-list">
      {#each data.clients as client (client.id)}
        <div class="client-card">
          <div class="client-header">
            <h3>{client.name}</h3>
            {#if client.description}
              <p class="client-desc">{client.description}</p>
            {/if}
          </div>
          <div class="client-details">
            <div class="detail">
              <span class="label">Client ID</span>
              <code>{client.id}</code>
            </div>
            {#if client.website_url}
              <div class="detail">
                <span class="label">Website</span>
                <a href={client.website_url} target="_blank" rel="noopener">{client.website_url}</a>
              </div>
            {/if}
            <div class="detail">
              <span class="label">Redirect URIs</span>
              <div class="uri-list">
                {#each client.redirect_uris as uri}
                  <code class="uri">{uri}</code>
                {/each}
              </div>
            </div>
            <div class="detail">
              <span class="label">Type</span>
              <span>{client.is_confidential ? 'Confidential' : 'Public'}</span>
            </div>
            <div class="detail">
              <span class="label">Created</span>
              <span>{new Date(client.created_at).toLocaleDateString()}</span>
            </div>
          </div>
          <div class="client-actions">
            <button class="btn-secondary" on:click={() => rotateSecret(client.id)} disabled={rotatingSecret === client.id}>
              {rotatingSecret === client.id ? 'Rotating...' : 'Rotate Secret'}
            </button>
            <button class="btn-danger" on:click={() => deleteOAuthClient(client.id)} disabled={deletingClient === client.id}>
              {deletingClient === client.id ? 'Deleting...' : 'Delete'}
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .page-container {
    max-width: 700px;
    margin: 0 auto;
    padding: 2rem 1rem;
    padding-bottom: 2rem;
  }

  .page-header {
    margin-bottom: 1.5rem;
  }

  h1 {
    font-size: 1.5rem;
    color: var(--text-primary);
    margin: 0 0 0.25rem;
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: 0.9rem;
    margin: 0;
  }

  .secret-banner {
    background: var(--color-warning-bg, rgba(224, 160, 0, 0.1));
    border: 1px solid var(--color-warning, #e0a000);
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1.5rem;
  }

  .secret-banner h3 {
    margin: 0 0 0.5rem;
    color: var(--color-warning, #e0a000);
    font-size: 1rem;
  }

  .secret-banner p {
    margin: 0 0 1rem;
    color: var(--text-secondary);
    font-size: 0.85rem;
  }

  .secret-field {
    margin-bottom: 0.75rem;
  }

  .secret-field label {
    display: block;
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 0.25rem;
  }

  .secret-field code {
    display: block;
    padding: 0.5rem;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.8rem;
    word-break: break-all;
    user-select: all;
  }

  .clients-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }

  .count {
    color: var(--text-secondary);
    font-size: 0.85rem;
  }

  .create-form {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1.5rem;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-group label {
    display: block;
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-bottom: 0.25rem;
  }

  .form-group input,
  .form-group textarea {
    width: 100%;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--input-bg);
    color: var(--text-primary);
    font-size: 0.9rem;
    box-sizing: border-box;
  }

  .form-group textarea {
    resize: vertical;
    font-family: monospace;
    font-size: 0.85rem;
  }

  .error-msg {
    color: var(--color-error, #e04040);
    font-size: 0.85rem;
    margin-bottom: 0.75rem;
  }

  .empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-secondary);
  }

  .clients-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .client-card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.25rem;
  }

  .client-header h3 {
    margin: 0 0 0.25rem;
    font-size: 1rem;
    color: var(--text-primary);
  }

  .client-desc {
    margin: 0;
    color: var(--text-secondary);
    font-size: 0.85rem;
  }

  .client-details {
    margin: 1rem 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .detail {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    font-size: 0.85rem;
  }

  .detail .label {
    color: var(--text-secondary);
    min-width: 100px;
    flex-shrink: 0;
  }

  .detail code {
    font-size: 0.8rem;
    word-break: break-all;
  }

  .detail a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .uri-list {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .uri {
    font-size: 0.8rem;
    color: var(--text-primary);
  }

  .client-actions {
    display: flex;
    gap: 0.5rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--border-color);
  }

  .btn-primary {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    border: none;
    background: var(--accent-color);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    opacity: 0.9;
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-size: 0.85rem;
    cursor: pointer;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
  }

  .btn-secondary:hover:not(:disabled) {
    background: var(--hover-bg);
  }

  .btn-danger {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-size: 0.85rem;
    cursor: pointer;
    background: transparent;
    border: 1px solid var(--color-error, #e04040);
    color: var(--color-error, #e04040);
  }

  .btn-danger:hover:not(:disabled) {
    background: rgba(224, 64, 64, 0.1);
  }

  .btn-danger:disabled,
  .btn-secondary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
