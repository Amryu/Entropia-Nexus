<!--
  @component Promo Library
  Card grid of user's promos with create/delete actions.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { goto, invalidateAll } from '$app/navigation';
  import { addToast } from '$lib/stores/toasts';

  let { data } = $props();

  let promos = $derived(data.promos ?? []);
  let deleting = $state(null);

  function formatDate(d) {
    if (!d) return '';
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function typeLabel(t) {
    return t === 'placement' ? 'Placement' : 'Featured Post';
  }

  async function deletePromo(id) {
    if (!confirm('Are you sure you want to delete this promo? This cannot be undone.')) return;
    deleting = id;
    try {
      const res = await fetch(`/api/promos/${id}`, { method: 'DELETE' });
      const result = await res.json();
      if (!res.ok) {
        addToast(result?.error || 'Failed to delete promo', 'error');
        return;
      }
      addToast('Promo deleted', 'success');
      await invalidateAll();
    } catch {
      addToast('Network error', 'error');
    } finally {
      deleting = null;
    }
  }
</script>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/account">Account</a>
      <span>/</span>
      <a href="/account/settings/promos">Promos</a>
      <span>/</span>
      <span>Library</span>
    </div>

    <div class="page-header">
      <h1>My Promos</h1>
      <a href="/account/settings/promos/library/new" class="btn-primary">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Create Promo
      </a>
    </div>

    {#if promos.length === 0}
      <div class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
        <p>No promos yet. Create your first promo to get started.</p>
        <a href="/account/settings/promos/library/new" class="btn-primary">Create Promo</a>
      </div>
    {:else}
      <div class="card-grid">
        {#each promos as promo}
          <div class="promo-card">
            <div class="card-header">
              <span class="type-badge" class:placement={promo.promo_type === 'placement'} class:featured={promo.promo_type === 'featured_post'}>
                {typeLabel(promo.promo_type)}
              </span>
              <span class="card-date">{formatDate(promo.created_at)}</span>
            </div>
            <h3 class="card-name">{promo.name}</h3>
            {#if promo.summary}
              <p class="card-summary">{promo.summary}</p>
            {/if}
            <div class="card-actions">
              <a href="/account/settings/promos/library/{promo.id}" class="btn-secondary">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                Edit
              </a>
              <button
                class="btn-danger"
                disabled={deleting === promo.id}
                onclick={() => deletePromo(promo.id)}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                {deleting === promo.id ? 'Deleting...' : 'Delete'}
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
    max-width: 900px;
    margin: 0 auto;
    padding: 1.5rem;
    padding-bottom: 2rem;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .page-header h1 {
    margin: 0;
    font-size: 1.75rem;
    color: var(--text-color);
  }

  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 1rem;
    background: var(--accent-color);
    color: #fff;
    border: none;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 600;
    text-decoration: none;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .btn-primary:hover {
    opacity: 0.9;
  }

  .btn-secondary {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.375rem 0.75rem;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 5px;
    font-size: 0.8125rem;
    text-decoration: none;
    cursor: pointer;
    transition: border-color 0.15s;
  }

  .btn-secondary:hover {
    border-color: var(--accent-color);
  }

  .btn-danger {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.375rem 0.75rem;
    background: transparent;
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 5px;
    font-size: 0.8125rem;
    cursor: pointer;
    transition: background 0.15s;
  }

  .btn-danger:hover {
    background: rgba(239, 68, 68, 0.1);
  }

  .btn-danger:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 3rem 1rem;
    gap: 1rem;
    color: var(--text-muted);
  }

  .empty-state p {
    margin: 0;
    max-width: 300px;
    font-size: 0.9rem;
  }

  .card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 0.75rem;
  }

  .promo-card {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
  }

  .type-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .type-badge.placement {
    background-color: rgba(59, 130, 246, 0.15);
    color: #3b82f6;
  }

  .type-badge.featured {
    background-color: rgba(168, 85, 247, 0.15);
    color: #a855f7;
  }

  .card-date {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .card-name {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .card-summary {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--text-muted);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .card-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: auto;
    padding-top: 0.75rem;
    border-top: 1px solid var(--border-color);
  }

  @media (max-width: 768px) {
    .card-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
