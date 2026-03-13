<script>
  // @ts-nocheck
  import { invalidateAll } from '$app/navigation';

  let { data } = $props();

  let showCreateForm = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let newClientResult = $state(null);
  let rotatingSecret = $state(null);
  let rotatedSecret = $state(null);
  let deletingClient = $state(null);

  // Create form fields
  let formName = $state('');
  let formDescription = $state('');
  let formWebsiteUrl = $state('');
  let formRedirectUri = $state('');
  let formIsConfidential = $state(true);

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
          redirect_uris: formRedirectUri.split('\n').map(u => u.trim()).filter(Boolean),
          is_confidential: formIsConfidential
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
      formIsConfidential = true;
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

  // URL builder state per client
  let urlBuilderOpen = $state({});
  let selectedScopes = $state({});
  let selectedRedirectUri = $state({});
  let copied = $state({});

  // Group scopes by category (base name before colon)
  let scopeGroups = $derived((() => {
    const groups = new Map();
    for (const scope of data.scopes) {
      const [category] = scope.key.split(':');
      if (!groups.has(category)) groups.set(category, []);
      groups.get(category).push(scope);
    }
    return [...groups.entries()].map(([name, scopes]) => ({ name, scopes }));
  })());

  function toggleUrlBuilder(clientId) {
    urlBuilderOpen[clientId] = !urlBuilderOpen[clientId];
    if (!selectedScopes[clientId]) selectedScopes[clientId] = {};
  }

  function toggleScope(clientId, scopeKey) {
    if (!selectedScopes[clientId]) selectedScopes[clientId] = {};
    selectedScopes[clientId][scopeKey] = !selectedScopes[clientId][scopeKey];
  }

  function getAuthUrl(client, scopeState, redirectState) {
    const scopes = Object.entries(scopeState[client.id] || {})
      .filter(([, v]) => v)
      .map(([k]) => k)
      .join(' ');
    const redirectUri = redirectState[client.id] || client.redirect_uris[0] || '';
    const params = new URLSearchParams({
      response_type: 'code',
      client_id: client.id,
      redirect_uri: redirectUri,
      scope: scopes || '<SCOPES>',
      state: '<STATE>',
      code_challenge: '<CODE_CHALLENGE>',
      code_challenge_method: 'S256'
    });
    return `${location.origin}/oauth/authorize?${params.toString()}`;
  }

  async function copyUrl(clientId, url) {
    try {
      await navigator.clipboard.writeText(url);
      copied[clientId] = true;
      setTimeout(() => { copied[clientId] = false; copied = copied; }, 2000);
    } catch {}
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
      {#if newClientResult.clientSecret}
        <p>Save your client secret now. It will not be shown again.</p>
      {:else}
        <p>Your public client has been created. No client secret is needed.</p>
      {/if}
      <div class="secret-field">
        <label>Client ID</label>
        <code>{newClientResult.clientId}</code>
      </div>
      {#if newClientResult.clientSecret}
        <div class="secret-field">
          <label>Client Secret</label>
          <code>{newClientResult.clientSecret}</code>
        </div>
      {/if}
      <button class="btn-secondary" onclick={dismissNewClient}>
        {newClientResult.clientSecret ? "I've saved it" : 'Done'}
      </button>
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
      <button class="btn-secondary" onclick={dismissRotatedSecret}>I've saved it</button>
    </div>
  {/if}

  <div class="clients-header">
    <span class="count">{data.clients.length} / {data.maxClients} applications</span>
    {#if data.clients.length < data.maxClients}
      <button class="btn-primary" onclick={() => showCreateForm = !showCreateForm}>
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
      <div class="form-group">
        <label>Client Type</label>
        <div class="type-selector">
          <label class="type-option" class:selected={formIsConfidential}>
            <input type="radio" bind:group={formIsConfidential} value={true} />
            <div class="type-content">
              <span class="type-name">Confidential</span>
              <span class="type-desc">Server-side apps that can securely store a client secret</span>
            </div>
          </label>
          <label class="type-option" class:selected={!formIsConfidential}>
            <input type="radio" bind:group={formIsConfidential} value={false} />
            <div class="type-content">
              <span class="type-name">Public</span>
              <span class="type-desc">Browser-based or native apps that cannot store a secret (PKCE only)</span>
            </div>
          </label>
        </div>
      </div>
      {#if createError}
        <div class="error-msg">{createError}</div>
      {/if}
      <button class="btn-primary" onclick={createClient} disabled={creating || !formName.trim() || !formRedirectUri.trim()}>
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
          <!-- Authorization URL Builder -->
          <div class="url-builder-section">
            <button class="btn-url-builder" onclick={() => toggleUrlBuilder(client.id)}>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
              </svg>
              {urlBuilderOpen[client.id] ? 'Hide Authorization URL' : 'Authorization URL'}
            </button>

            {#if urlBuilderOpen[client.id]}
              <div class="url-builder">
                <p class="url-builder-desc">Select the scopes your application needs. Users will be asked to approve these permissions.</p>

                {#if client.redirect_uris.length > 1}
                  <div class="redirect-select">
                    <label for="redirect-{client.id}">Redirect URI</label>
                    <select id="redirect-{client.id}" bind:value={selectedRedirectUri[client.id]}>
                      {#each client.redirect_uris as uri}
                        <option value={uri}>{uri}</option>
                      {/each}
                    </select>
                  </div>
                {/if}

                <div class="scope-picker">
                  {#each scopeGroups as group}
                    <div class="scope-group">
                      <span class="scope-group-name">{group.name}</span>
                      <div class="scope-group-items">
                        {#each group.scopes as scope}
                          <label class="scope-option" class:write={scope.key.endsWith(':write')}>
                            <input
                              type="checkbox"
                              checked={selectedScopes[client.id]?.[scope.key] || false}
                              onchange={() => toggleScope(client.id, scope.key)}
                            />
                            <span class="scope-key">{scope.key}</span>
                            <span class="scope-desc">{scope.description}</span>
                          </label>
                        {/each}
                      </div>
                    </div>
                  {/each}
                </div>

                <div class="generated-url">
                  <div class="url-header">
                    <label>Generated URL</label>
                    <button class="btn-copy" onclick={() => copyUrl(client.id, getAuthUrl(client, selectedScopes, selectedRedirectUri))}>
                      {copied[client.id] ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                  <code class="url-display">{getAuthUrl(client, selectedScopes, selectedRedirectUri)}</code>
                </div>

                <p class="url-note">
                  Replace <code>&lt;STATE&gt;</code> with a random string and <code>&lt;CODE_CHALLENGE&gt;</code> with a Base64url-encoded SHA-256 hash of your code verifier (PKCE).
                </p>
              </div>
            {/if}
          </div>

          <div class="client-actions">
            {#if client.is_confidential}
              <button class="btn-secondary" onclick={() => rotateSecret(client.id)} disabled={rotatingSecret === client.id}>
                {rotatingSecret === client.id ? 'Rotating...' : 'Rotate Secret'}
              </button>
            {/if}
            <button class="btn-danger" onclick={() => deleteOAuthClient(client.id)} disabled={deletingClient === client.id}>
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

  .type-selector {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .type-option {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    cursor: pointer;
    transition: border-color 0.15s;
  }

  .type-option:hover {
    border-color: var(--accent-color);
  }

  .type-option.selected {
    border-color: var(--accent-color);
    background: rgba(74, 158, 255, 0.05);
  }

  .type-option input[type="radio"] {
    margin: 0.15rem 0 0;
    cursor: pointer;
  }

  .type-content {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .type-name {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .type-desc {
    font-size: 0.8rem;
    color: var(--text-secondary);
    line-height: 1.35;
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

  /* URL Builder */

  .url-builder-section {
    margin: 0.75rem 0;
  }

  .btn-url-builder {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.4rem 0.75rem;
    border-radius: 6px;
    font-size: 0.8rem;
    cursor: pointer;
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--accent-color);
  }

  .btn-url-builder:hover {
    background: var(--hover-bg);
  }

  .url-builder {
    margin-top: 0.75rem;
    padding: 1rem;
    background: var(--hover-bg);
    border-radius: 6px;
    border: 1px solid var(--border-color);
  }

  .url-builder-desc {
    margin: 0 0 0.75rem;
    font-size: 0.8rem;
    color: var(--text-secondary);
  }

  .redirect-select {
    margin-bottom: 0.75rem;
  }

  .redirect-select label {
    display: block;
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 0.25rem;
  }

  .redirect-select select {
    width: 100%;
    padding: 0.4rem 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--input-bg);
    color: var(--text-primary);
    font-size: 0.8rem;
    font-family: monospace;
  }

  .scope-picker {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    margin-bottom: 0.75rem;
  }

  .scope-group {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .scope-group-name {
    min-width: 80px;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: capitalize;
    padding-top: 0.25rem;
    flex-shrink: 0;
  }

  .scope-group-items {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.75rem;
  }

  .scope-option {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.8rem;
    cursor: pointer;
    padding: 0.2rem 0;
  }

  .scope-option input[type="checkbox"] {
    margin: 0;
    cursor: pointer;
  }

  .scope-key {
    font-family: monospace;
    font-size: 0.75rem;
    color: var(--text-primary);
  }

  .scope-option.write .scope-key {
    color: var(--color-warning, #e0a000);
  }

  .scope-desc {
    font-size: 0.7rem;
    color: var(--text-secondary);
  }

  .generated-url {
    margin-bottom: 0.5rem;
  }

  .url-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.25rem;
  }

  .url-header label {
    font-size: 0.8rem;
    color: var(--text-secondary);
    font-weight: 500;
  }

  .btn-copy {
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-size: 0.75rem;
    cursor: pointer;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
  }

  .btn-copy:hover {
    background: var(--hover-bg);
  }

  .url-display {
    display: block;
    padding: 0.5rem;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.75rem;
    word-break: break-all;
    user-select: all;
    line-height: 1.4;
  }

  .url-note {
    margin: 0;
    font-size: 0.75rem;
    color: var(--text-secondary);
    line-height: 1.4;
  }

  .url-note code {
    font-size: 0.7rem;
    background: var(--card-bg);
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
  }

  @media (max-width: 600px) {
    .scope-group {
      flex-direction: column;
      gap: 0.15rem;
    }

    .scope-group-name {
      min-width: unset;
    }
  }
</style>
