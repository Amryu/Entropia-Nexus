<script>
  
  /**
   * @typedef {Object} Props
   * @property {any} data
   */

  /** @type {Props} */
  let { data } = $props();

  const { client, scopeInfo, effectiveScopes, redirectUri, state, codeChallenge, codeChallengeMethod } = data;
  const hasWriteScopes = scopeInfo.some(s => s.isWrite && s.available);
</script>

<svelte:head>
  <title>Authorize {client.name} | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="consent-card">
      <div class="header">
        <div class="icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
          </svg>
        </div>
        <h1>Authorize Application</h1>
      </div>

      <div class="app-info">
        <h2 class="app-name">{client.name}</h2>
        {#if client.description}
          <p class="app-description">{client.description}</p>
        {/if}
        {#if client.website_url}
          <a href={client.website_url} target="_blank" rel="noopener" class="app-url">{client.website_url}</a>
        {/if}
      </div>

      <div class="permissions">
        <h3>This application is requesting access to:</h3>
        <ul class="scope-list">
          {#each scopeInfo as scope}
            <li class="scope-item" class:unavailable={!scope.available} class:write={scope.isWrite}>
              <span class="scope-icon">
                {#if scope.isWrite}
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                  </svg>
                {:else}
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                    <circle cx="12" cy="12" r="3"></circle>
                  </svg>
                {/if}
              </span>
              <span class="scope-text">
                {scope.description}
                {#if !scope.available}
                  <span class="scope-unavailable">(you lack the required permission)</span>
                {/if}
              </span>
            </li>
          {/each}
        </ul>
      </div>

      {#if hasWriteScopes}
        <div class="warning">
          This application is requesting write access. It will be able to make changes on your behalf.
        </div>
      {/if}

      <div class="actions">
        <form method="POST" action="?/authorize">
          <input type="hidden" name="client_id" value={client.id} />
          <input type="hidden" name="redirect_uri" value={redirectUri} />
          <input type="hidden" name="scope" value={effectiveScopes.join(' ')} />
          <input type="hidden" name="state" value={state} />
          <input type="hidden" name="code_challenge" value={codeChallenge} />
          <button type="submit" class="btn-authorize" disabled={effectiveScopes.length === 0}>
            Authorize
          </button>
        </form>
        <form method="POST" action="?/deny">
          <input type="hidden" name="client_id" value={client.id} />
          <input type="hidden" name="redirect_uri" value={redirectUri} />
          <input type="hidden" name="state" value={state} />
          <button type="submit" class="btn-deny">Deny</button>
        </form>
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
    max-width: 500px;
    margin: 0 auto;
    padding: 2rem 1rem;
    padding-bottom: 2rem;
  }

  .consent-card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 2rem;
  }

  .header {
    text-align: center;
    margin-bottom: 1.5rem;
  }

  .icon {
    color: var(--accent-color);
    margin-bottom: 0.5rem;
  }

  h1 {
    font-size: 1.25rem;
    color: var(--text-primary);
    margin: 0;
  }

  .app-info {
    text-align: center;
    margin-bottom: 1.5rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border-color);
  }

  .app-name {
    font-size: 1.1rem;
    color: var(--text-primary);
    margin: 0 0 0.5rem;
  }

  .app-description {
    color: var(--text-secondary);
    font-size: 0.9rem;
    margin: 0 0 0.5rem;
  }

  .app-url {
    color: var(--accent-color);
    font-size: 0.85rem;
    text-decoration: none;
  }

  .app-url:hover {
    text-decoration: underline;
  }

  .permissions h3 {
    font-size: 0.9rem;
    color: var(--text-secondary);
    margin: 0 0 0.75rem;
    font-weight: 500;
  }

  .scope-list {
    list-style: none;
    padding: 0;
    margin: 0 0 1.5rem;
  }

  .scope-item {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.5rem 0;
    font-size: 0.9rem;
    color: var(--text-primary);
  }

  .scope-item.unavailable {
    opacity: 0.5;
    text-decoration: line-through;
  }

  .scope-item.write .scope-icon {
    color: var(--color-warning, #e0a000);
  }

  .scope-icon {
    color: var(--text-secondary);
    flex-shrink: 0;
    margin-top: 2px;
  }

  .scope-unavailable {
    color: var(--color-error, #e04040);
    font-size: 0.8rem;
    font-style: italic;
  }

  .warning {
    background: var(--color-warning-bg, rgba(224, 160, 0, 0.1));
    border: 1px solid var(--color-warning, #e0a000);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: var(--color-warning, #e0a000);
    margin-bottom: 1.5rem;
  }

  .actions {
    display: flex;
    gap: 0.75rem;
  }

  .actions form {
    flex: 1;
  }

  .btn-authorize,
  .btn-deny {
    width: 100%;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: opacity 0.15s;
  }

  .btn-authorize {
    background: var(--accent-color);
    color: white;
  }

  .btn-authorize:hover:not(:disabled) {
    opacity: 0.9;
  }

  .btn-authorize:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-deny {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
  }

  .btn-deny:hover {
    background: var(--hover-bg);
  }
</style>
