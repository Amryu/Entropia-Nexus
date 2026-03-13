<script>
  import { stopPropagation } from 'svelte/legacy';

  // @ts-nocheck
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { addToast } from '$lib/stores/toasts';

  let creators = $state([]);
  let isLoading = $state(true);
  let error = $state(null);

  const platformLabels = { youtube: 'YouTube', twitch: 'Twitch', kick: 'Kick' };
  const platformColors = { youtube: '#FF0000', twitch: '#9146FF', kick: '#53FC18' };

  onMount(() => {
    loadCreators();
  });

  async function loadCreators() {
    isLoading = true;
    error = null;
    try {
      const response = await fetch('/api/admin/creators');
      if (!response.ok) throw new Error('Failed to load creators');
      const data = await response.json();
      creators = data;
    } catch (err) {
      error = err.message;
    } finally {
      isLoading = false;
    }
  }

  async function toggleActive(creator) {
    try {
      const response = await fetch(`/api/admin/creators/${creator.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active: !creator.active })
      });
      if (!response.ok) throw new Error('Failed to update');
      creator.active = !creator.active;
      creators = creators;
      addToast(`Creator ${creator.active ? 'activated' : 'deactivated'}`, 'success');
    } catch (err) {
      addToast(err.message, 'error');
    }
  }

  async function refreshCreator(creator) {
    try {
      creator._refreshing = true;
      creators = creators;
      const response = await fetch(`/api/admin/creators/${creator.id}/refresh`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Refresh failed');
      Object.assign(creator, data);
      creator._refreshing = false;
      creators = creators;
      addToast('Creator data refreshed', 'success');
    } catch (err) {
      creator._refreshing = false;
      creators = creators;
      addToast(err.message, 'error');
    }
  }

  function formatCachedAt(dateStr) {
    if (!dateStr) return 'Never';
    const d = new Date(dateStr);
    const diff = Date.now() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }
</script>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/admin">Admin</a>
    <span class="separator">/</span>
    <span>Creators</span>
  </nav>

  <div class="page-header">
    <h1>Content Creators</h1>
    <button class="action-btn" onclick={() => goto('/admin/creators/new')}>
      Add Creator
    </button>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if isLoading}
    <div class="loading">Loading creators...</div>
  {:else if creators.length === 0}
    <div class="empty-state">No content creators yet. Add one to get started.</div>
  {:else}
    <div class="creators-list">
      {#each creators as creator}
        <div class="creator-row" class:inactive={!creator.active}>
          <div class="creator-main" onclick={() => goto(`/admin/creators/${creator.id}`)} role="button" tabindex="0" onkeypress={(e) => e.key === 'Enter' && goto(`/admin/creators/${creator.id}`)}>
            <div class="creator-avatar">
              {#if creator.avatar_url || creator.cached_data?.channelAvatar || creator.cached_data?.avatar}
                <img src={creator.cached_data?.channelAvatar || creator.cached_data?.avatar || creator.avatar_url} alt={creator.name} />
              {:else}
                <div class="avatar-placeholder">{creator.name.charAt(0).toUpperCase()}</div>
              {/if}
            </div>
            <div class="creator-info">
              <div class="creator-name-row">
                <span class="creator-name">{creator.cached_data?.channelName || creator.cached_data?.displayName || creator.name}</span>
                <span class="platform-badge" style="color: {platformColors[creator.platform]}">
                  {platformLabels[creator.platform]}
                </span>
                {#if !creator.active}
                  <span class="badge badge-muted">Inactive</span>
                {/if}
              </div>
              <div class="creator-meta">
                <span>Order: {creator.display_order}</span>
                <span>Cached: {formatCachedAt(creator.cached_at)}</span>
                {#if creator.added_by_name}
                  <span>Added by {creator.added_by_name}</span>
                {/if}
              </div>
            </div>
          </div>
          <div class="creator-actions">
            {#if creator.platform !== 'kick'}
              <button class="btn-icon" title="Refresh data" onclick={stopPropagation(() => refreshCreator(creator))} disabled={creator._refreshing}>
                {creator._refreshing ? '...' : 'Refresh'}
              </button>
            {/if}
            <button class="btn-icon" class:active-toggle={creator.active} title={creator.active ? 'Deactivate' : 'Activate'} onclick={stopPropagation(() => toggleActive(creator))}>
              {creator.active ? 'On' : 'Off'}
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .page-container {
    max-width: 1200px;
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
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
    margin: 0;
  }

  .action-btn {
    padding: 0.5rem 1rem;
    background-color: var(--accent-color);
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
  }

  .action-btn:hover {
    background-color: var(--accent-color-hover);
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    border: 1px solid var(--error-color);
    margin-bottom: 1rem;
  }

  .loading, .empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted);
  }

  .creators-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .creator-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    transition: border-color 0.15s;
  }

  .creator-row:hover {
    border-color: var(--accent-color);
  }

  .creator-row.inactive {
    opacity: 0.6;
  }

  .creator-main {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
    min-width: 0;
    cursor: pointer;
  }

  .creator-avatar {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    overflow: hidden;
  }

  .creator-avatar img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .avatar-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--primary-color);
    color: var(--text-muted);
    font-weight: 700;
    font-size: 1rem;
  }

  .creator-info {
    flex: 1;
    min-width: 0;
  }

  .creator-name-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .creator-name {
    font-weight: 600;
    font-size: 0.9375rem;
  }

  .platform-badge {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .badge {
    display: inline-flex;
    padding: 0.1rem 0.4rem;
    border-radius: 9999px;
    font-size: 0.65rem;
    font-weight: 600;
  }

  .badge-muted {
    background: var(--hover-color);
    color: var(--text-muted);
  }

  .creator-meta {
    display: flex;
    gap: 0.75rem;
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 2px;
  }

  .creator-actions {
    display: flex;
    gap: 0.375rem;
    flex-shrink: 0;
  }

  .btn-icon {
    padding: 0.35rem 0.6rem;
    font-size: 0.75rem;
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-icon:hover:not(:disabled) {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }

  .btn-icon:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .active-toggle {
    background: rgba(34, 197, 94, 0.15);
    border-color: rgba(34, 197, 94, 0.3);
    color: #22c55e;
  }

  @media (max-width: 899px) {
    .page-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.75rem;
    }

    .creator-meta {
      flex-wrap: wrap;
    }
  }
</style>
