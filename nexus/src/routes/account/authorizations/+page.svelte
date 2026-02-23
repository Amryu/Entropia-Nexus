<script>
  // @ts-nocheck
  import { invalidateAll } from '$app/navigation';

  export let data;

  let revoking = null;

  async function revokeAuthorization(clientId, appName) {
    if (!confirm(`Revoke access for "${appName}"? The app will no longer be able to access your account.`)) return;
    revoking = clientId;
    try {
      await fetch(`/api/oauth/authorizations/${clientId}`, { method: 'DELETE' });
      await invalidateAll();
    } finally {
      revoking = null;
    }
  }
</script>

<svelte:head>
  <title>Authorized Applications | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="page-header">
      <h1>Authorized Applications</h1>
      <p class="subtitle">Applications you have granted access to your Entropia Nexus account.</p>
    </div>

    {#if data.authorizations.length === 0}
      <div class="empty-state">
        <p>You haven't authorized any applications yet.</p>
      </div>
    {:else}
      <div class="auth-list">
        {#each data.authorizations as auth (auth.client_id)}
          <div class="auth-card">
            <div class="auth-info">
              <h3>{auth.name}</h3>
              {#if auth.description}
                <p class="auth-desc">{auth.description}</p>
              {/if}
              {#if auth.website_url}
                <a href={auth.website_url} target="_blank" rel="noopener" class="auth-url">{auth.website_url}</a>
              {/if}
              <div class="scopes">
                <span class="scopes-label">Permissions:</span>
                {#each auth.scopes as scope}
                  <span class="scope-badge" class:write={scope.endsWith(':write')}>{scope}</span>
                {/each}
              </div>
              <div class="auth-date">
                Authorized {new Date(auth.authorized_at).toLocaleDateString()}
              </div>
            </div>
            <div class="auth-actions">
              <button
                class="btn-revoke"
                on:click={() => revokeAuthorization(auth.client_id, auth.name)}
                disabled={revoking === auth.client_id}
              >
                {revoking === auth.client_id ? 'Revoking...' : 'Revoke Access'}
              </button>
            </div>
          </div>
        {/each}
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

  .empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-secondary);
  }

  .auth-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .auth-card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.25rem;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
  }

  .auth-info h3 {
    margin: 0 0 0.25rem;
    font-size: 1rem;
    color: var(--text-primary);
  }

  .auth-desc {
    margin: 0 0 0.5rem;
    color: var(--text-secondary);
    font-size: 0.85rem;
  }

  .auth-url {
    color: var(--accent-color);
    font-size: 0.85rem;
    text-decoration: none;
    display: block;
    margin-bottom: 0.5rem;
  }

  .scopes {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.375rem;
    margin-bottom: 0.5rem;
  }

  .scopes-label {
    color: var(--text-secondary);
    font-size: 0.8rem;
  }

  .scope-badge {
    font-size: 0.75rem;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    background: var(--hover-bg);
    color: var(--text-primary);
    font-family: monospace;
  }

  .scope-badge.write {
    background: rgba(224, 160, 0, 0.15);
    color: var(--color-warning, #e0a000);
  }

  .auth-date {
    color: var(--text-secondary);
    font-size: 0.8rem;
  }

  .btn-revoke {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-size: 0.85rem;
    cursor: pointer;
    background: transparent;
    border: 1px solid var(--color-error, #e04040);
    color: var(--color-error, #e04040);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .btn-revoke:hover:not(:disabled) {
    background: rgba(224, 64, 64, 0.1);
  }

  .btn-revoke:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (max-width: 600px) {
    .auth-card {
      flex-direction: column;
    }
  }
</style>
