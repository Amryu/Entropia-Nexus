<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { encodeURIComponentSafe } from '$lib/util';

  let stats = null;
  let isLoading = true;
  let error = null;

  onMount(async () => {
    try {
      const response = await fetch('/api/admin/stats');
      if (!response.ok) throw new Error('Failed to load stats');
      stats = await response.json();
    } catch (err) {
      error = err.message;
    } finally {
      isLoading = false;
    }

  });

  function getStateColor(state) {
    switch (state) {
      case 'Pending': return 'var(--warning-color)';
      case 'Approved': return 'var(--success-color)';
      case 'Denied': return 'var(--error-color)';
      case 'Draft': return 'var(--text-muted)';
      default: return 'var(--text-color)';
    }
  }

  // Group entities by category
  function categorizeEntity(entity) {
    const categories = {
      'Items': ['Weapon', 'ArmorSet', 'MedicalTool', 'MedicalChip', 'Refiner', 'Scanner', 'Finder', 'Excavator', 'TeleportChip', 'EffectChip', 'MiscTool', 'WeaponAmplifier', 'WeaponVisionAttachment', 'Absorber', 'FinderAmplifier', 'ArmorPlating', 'MindforceImplant', 'Blueprint', 'Material', 'Pet', 'Consumable', 'CreatureControlCapsule', 'Vehicle', 'Furniture', 'Decoration', 'StorageContainer', 'Sign', 'Clothing'],
      'Information': ['Mob', 'Vendor', 'RefiningRecipe'],
      'Market': ['Shop']
    };

    for (const [category, entities] of Object.entries(categories)) {
      if (entities.includes(entity)) return category;
    }
    return 'Other';
  }

  function getProfileUrl(contributor) {
    if (!contributor) return '/admin/users';
    return `/admin/users/${encodeURIComponentSafe(String(contributor.id))}`;
  }
</script>

<svelte:head>
  <title>Admin Dashboard | Entropia Nexus</title>
</svelte:head>

<style>
  .dashboard {
    max-width: 1200px;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    font-size: 14px;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .breadcrumb span {
    color: var(--text-muted);
  }

  h1 {
    margin: 0 0 8px 0;
    font-size: 28px;
    color: var(--text-color);
  }

  .subtitle {
    color: var(--text-muted);
    margin: 0 0 24px 0;
    font-size: 14px;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
  }

  .stat-card {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 20px;
  }

  .stat-card h3 {
    margin: 0 0 8px 0;
    font-size: 14px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .stat-value {
    font-size: 32px;
    font-weight: bold;
    margin: 0;
  }

  .stat-pending {
    color: var(--warning-color);
  }

  .stat-approved {
    color: var(--success-color);
  }

  .stat-denied {
    color: var(--error-color);
  }

  .section {
    margin-bottom: 32px;
  }

  .section h2 {
    margin: 0 0 16px 0;
    font-size: 20px;
    color: var(--text-color);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .contributors-list {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }

  .contributor-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
    text-decoration: none;
    color: var(--text-color);
  }

  .contributor-item:last-child {
    border-bottom: none;
  }

  .contributor-rank {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background-color: var(--hover-color);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: bold;
    color: var(--text-muted);
  }

  .contributor-rank.top-3 {
    background-color: rgba(245, 158, 11, 0.2);
    color: var(--warning-color);
  }

  .contributor-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    object-fit: cover;
  }

  .contributor-name {
    flex: 1;
  }

  .contributor-name strong {
    display: block;
    font-size: 14px;
    color: var(--text-color);
  }

  .contributor-name small {
    color: var(--text-muted);
    font-size: 12px;
  }

  .contributor-stats {
    text-align: right;
  }

  .contributor-stats .approved {
    font-weight: bold;
    color: var(--success-color);
  }

  .contributor-stats small {
    color: var(--text-muted);
    font-size: 12px;
  }

  .entity-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
  }

  .entity-category {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 16px;
  }

  .entity-category h4 {
    margin: 0 0 12px 0;
    font-size: 14px;
    color: var(--text-color);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .entity-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    font-size: 13px;
  }

  .entity-name {
    color: var(--text-color);
  }

  .entity-count {
    color: var(--text-muted);
  }

  .loading, .error {
    text-align: center;
    padding: 40px;
    color: var(--text-muted);
  }

  .error {
    color: var(--error-color);
  }

  .quick-actions {
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
  }

  .action-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background-color: var(--accent-color);
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    cursor: pointer;
    text-decoration: none;
    transition: background-color 0.15s ease;
  }

  .action-btn:hover {
    background-color: var(--accent-color-hover);
  }

  .action-btn.secondary {
    background-color: var(--hover-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
  }

  .action-btn.secondary:hover {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  /* Mobile responsive */
  @media (max-width: 768px) {
    h1 {
      font-size: 22px;
    }

    .subtitle {
      font-size: 13px;
    }

    .breadcrumb {
      font-size: 12px;
      flex-wrap: wrap;
    }

    .quick-actions {
      flex-direction: column;
      gap: 8px;
    }

    .action-btn {
      justify-content: center;
      padding: 12px 16px;
    }

    .stats-grid {
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
    }

    .stat-card {
      padding: 14px;
    }

    .stat-card h3 {
      font-size: 11px;
    }

    .stat-value {
      font-size: 24px;
    }

    .section h2 {
      font-size: 18px;
    }

    .contributor-item {
      padding: 10px 12px;
      gap: 10px;
    }

    .contributor-avatar {
      width: 32px;
      height: 32px;
    }

    .contributor-name strong {
      font-size: 13px;
    }

    .entity-stats {
      grid-template-columns: 1fr;
    }

    .entity-category {
      padding: 12px;
    }
  }

  @media (max-width: 400px) {
    .stats-grid {
      grid-template-columns: 1fr;
    }
  }
</style>

<div class="dashboard">
  <div class="breadcrumb">
    <a href="/admin">Admin</a>
    <span>/</span>
    <span>Dashboard</span>
  </div>

  <h1>Admin Dashboard</h1>
  <p class="subtitle">Monitor changes, manage users, and view platform statistics</p>

  <div class="quick-actions">
    <a href="/admin/changes?state=Pending" class="action-btn">
      📝 Review Pending Changes
    </a>
    <a href="/admin/users" class="action-btn secondary">
      👥 Manage Users
    </a>
    <a href="/admin/history" class="action-btn secondary">
      📜 Entity History
    </a>
  </div>

  {#if isLoading}
    <div class="loading">Loading statistics...</div>
  {:else if error}
    <div class="error">Error: {error}</div>
  {:else if stats}
    <div class="stats-grid">
      <div class="stat-card">
        <h3>Pending Review</h3>
        <p class="stat-value stat-pending">{stats.changes?.byState?.Pending || 0}</p>
      </div>
      <div class="stat-card">
        <h3>Approved</h3>
        <p class="stat-value stat-approved">{stats.changes?.byState?.Approved || 0}</p>
      </div>
      <div class="stat-card">
        <h3>Denied</h3>
        <p class="stat-value stat-denied">{stats.changes?.byState?.Denied || 0}</p>
      </div>
      <div class="stat-card">
        <h3>Drafts</h3>
        <p class="stat-value" style="color: var(--text-muted)">{stats.changes?.byState?.Draft || 0}</p>
      </div>
    </div>

    <div class="section">
      <h2>🏆 Top Contributors</h2>
      <div class="contributors-list">
        {#if stats.topContributors?.length > 0}
          {#each stats.topContributors as contributor, i}
            <a class="contributor-item" href={getProfileUrl(contributor)}>
              <span class="contributor-rank" class:top-3={i < 3}>{i + 1}</span>
              <img
                src={contributor.avatar ? `https://cdn.discordapp.com/avatars/${contributor.id}/${contributor.avatar}.png` : `https://cdn.discordapp.com/embed/avatars/${Number(BigInt(contributor.id) % 5n)}.png`}
                alt=""
                class="contributor-avatar"
              />
              <div class="contributor-name">
                <strong>{contributor.global_name || 'Unknown'}</strong>
                {#if contributor.eu_name}
                  <small>{contributor.eu_name}</small>
                {/if}
              </div>
              <div class="contributor-stats">
                <span class="approved">{contributor.approved_count}</span>
                <small> / {contributor.total_count} changes</small>
              </div>
            </a>
          {/each}
        {:else}
          <div class="contributor-item">
            <span style="color: var(--text-muted)">No contributions yet</span>
          </div>
        {/if}
      </div>
    </div>

    {#if stats.changes?.byEntity && Object.keys(stats.changes.byEntity).length > 0}
      <div class="section">
        <h2>📊 Changes by Entity Type</h2>
        <div class="entity-stats">
          {#each ['Items', 'Information', 'Market'] as category}
            {@const entities = Object.entries(stats.changes.byEntity).filter(([e]) => categorizeEntity(e) === category)}
            {#if entities.length > 0}
              <div class="entity-category">
                <h4>{category}</h4>
                {#each entities as [entityName, entityStats]}
                  <div class="entity-row">
                    <span class="entity-name">{entityName}</span>
                    <span class="entity-count">
                      {entityStats.total}
                      {#if entityStats.byState?.Pending}
                        <span style="color: var(--warning-color)">({entityStats.byState.Pending} pending)</span>
                      {/if}
                    </span>
                  </div>
                {/each}
              </div>
            {/if}
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</div>
