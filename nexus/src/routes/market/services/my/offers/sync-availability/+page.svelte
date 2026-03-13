<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import DashboardNav from "$lib/components/services/DashboardNav.svelte";
  import { goto } from '$app/navigation';
  import { apiPost } from '$lib/util';

  let { data } = $props();

  let services = $derived(data.services || []);

  let sourceServiceId = $state(null);
  let targetServiceIds = $state([]);
  let syncMode = $state('copy'); // 'copy' or 'new'
  let loading = $state(false);
  let error = $state(null);
  let success = $state(false);

  function toggleTarget(serviceId) {
    if (targetServiceIds.includes(serviceId)) {
      targetServiceIds = targetServiceIds.filter(id => id !== serviceId);
    } else {
      targetServiceIds = [...targetServiceIds, serviceId];
    }
  }

  function selectAllTargets() {
    targetServiceIds = services
      .filter(s => s.id !== sourceServiceId)
      .map(s => s.id);
  }

  function deselectAllTargets() {
    targetServiceIds = [];
  }

  async function handleSync() {
    if (targetServiceIds.length === 0) {
      error = 'Please select at least one target service.';
      return;
    }

    if (syncMode === 'copy' && !sourceServiceId) {
      error = 'Please select a source service to copy from.';
      return;
    }

    loading = true;
    error = null;
    success = false;

    try {
      const response = await apiPost(fetch, '/api/services/my/sync-availability', {
        sourceServiceId: syncMode === 'copy' ? sourceServiceId : null,
        targetServiceIds
      });

      if (response.error) {
        error = response.error;
      } else {
        success = true;
        setTimeout(() => {
          goto('/market/services/my/offers');
        }, 2000);
      }
    } catch (err) {
      error = 'Failed to sync availability. Please try again.';
    } finally {
      loading = false;
    }
  }

  function getServiceTypeLabel(type) {
    const labels = {
      healing: 'Healing',
      dps: 'DPS',
      transportation: 'Transport',
      custom: 'Custom'
    };
    return labels[type] || type;
  }
</script>

<svelte:head>
  <title>Sync Availability | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
<div class="page-container">
  <div class="breadcrumb">
    <a href="/market/services/my">My Services</a>
    <span>/</span>
    <a href="/market/services/my/offers">My Offers</a>
    <span>/</span>
    <span>Sync Availability</span>
  </div>

  <h1>Sync Availability</h1>

  <DashboardNav />

  {#if services.length < 2}
    <div class="notice">
      <p>You need at least 2 active services to sync availability between them.</p>
      <a href="/market/services/create">Create another service</a>
    </div>
  {:else}
    <div class="sync-form">
      {#if error}
        <div class="error-banner">{error}</div>
      {/if}

      {#if success}
        <div class="success-banner">
          Availability synced successfully! Redirecting...
        </div>
      {/if}

      <div class="form-section">
        <h2>Sync Mode</h2>
        <div class="radio-group">
          <label class="radio-option">
            <input type="radio" bind:group={syncMode} value="copy" />
            <span class="radio-label">Copy from existing service</span>
            <span class="radio-description">Copy availability schedule from one service to others</span>
          </label>
        </div>
      </div>

      {#if syncMode === 'copy'}
        <div class="form-section">
          <h2>Source Service</h2>
          <p class="section-description">Select the service to copy availability from</p>
          <div class="service-list source">
            {#each services as service}
              <label class="service-option" class:selected={sourceServiceId === service.id}>
                <input
                  type="radio"
                  bind:group={sourceServiceId}
                  value={service.id}
                />
                <span class="service-title">{service.title}</span>
                <span class="service-type">{getServiceTypeLabel(service.type)}</span>
              </label>
            {/each}
          </div>
        </div>
      {/if}

      <div class="form-section">
        <div class="section-header">
          <h2>Target Services</h2>
          <div class="select-actions">
            <button type="button" class="text-btn" onclick={selectAllTargets}>Select all</button>
            <button type="button" class="text-btn" onclick={deselectAllTargets}>Deselect all</button>
          </div>
        </div>
        <p class="section-description">Select which services should receive the new availability</p>
        <div class="service-list target">
          {#each services.filter(s => s.id !== sourceServiceId) as service}
            <label class="service-option" class:selected={targetServiceIds.includes(service.id)}>
              <input
                type="checkbox"
                checked={targetServiceIds.includes(service.id)}
                onchange={() => toggleTarget(service.id)}
              />
              <span class="service-title">{service.title}</span>
              <span class="service-type">{getServiceTypeLabel(service.type)}</span>
            </label>
          {/each}
        </div>
      </div>

      <div class="form-actions">
        <a href="/market/services/my/offers" class="btn secondary">Cancel</a>
        <button
          type="button"
          class="btn primary"
          disabled={loading || targetServiceIds.length === 0 || (syncMode === 'copy' && !sourceServiceId)}
          onclick={handleSync}
        >
          {loading ? 'Syncing...' : `Sync to ${targetServiceIds.length} service${targetServiceIds.length !== 1 ? 's' : ''}`}
        </button>
      </div>
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
    padding: 1rem;
    max-width: 800px;
    margin: 0 auto;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted, #666);
    margin-bottom: 1rem;
  }

  .breadcrumb a {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  h1 {
    margin: 0 0 1.5rem 0;
  }

  .notice {
    background: var(--bg-secondary, #f5f5f5);
    border: 1px solid var(--border-color, #ccc);
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
  }

  .notice a {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .sync-form {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
  }

  .success-banner {
    background: var(--success-bg);
    color: var(--success-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
  }

  .form-section {
    background: var(--bg-color, #fff);
    border: 1px solid var(--border-color, #e5e5e5);
    border-radius: 8px;
    padding: 1.25rem;
  }

  .form-section h2 {
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .section-description {
    margin: 0 0 1rem 0;
    font-size: 0.9rem;
    color: var(--text-muted, #666);
  }

  .select-actions {
    display: flex;
    gap: 1rem;
  }

  .text-btn {
    background: none;
    border: none;
    color: var(--accent-color, #4a9eff);
    cursor: pointer;
    font-size: 0.9rem;
    padding: 0;
  }

  .text-btn:hover {
    text-decoration: underline;
  }

  .radio-group {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .radio-option {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    padding: 0.75rem;
    border: 1px solid var(--border-color, #e5e5e5);
    border-radius: 6px;
    cursor: pointer;
  }

  .radio-option:hover {
    border-color: var(--accent-color, #4a9eff);
  }

  .radio-option input {
    display: none;
  }

  .radio-label {
    font-weight: 500;
  }

  .radio-description {
    font-size: 0.85rem;
    color: var(--text-muted, #666);
  }

  .service-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .service-option {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem;
    border: 1px solid var(--border-color, #e5e5e5);
    border-radius: 6px;
    cursor: pointer;
    transition: border-color 0.15s ease, background-color 0.15s ease;
  }

  .service-option:hover {
    border-color: var(--accent-color, #4a9eff);
  }

  .service-option.selected {
    border-color: var(--accent-color, #4a9eff);
    background: rgba(74, 158, 255, 0.05);
  }

  .service-option input {
    margin: 0;
  }

  .service-title {
    flex: 1;
    font-weight: 500;
  }

  .service-type {
    font-size: 0.85rem;
    color: var(--text-muted, #666);
    background: var(--bg-secondary, #f5f5f5);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
  }

  .btn {
    padding: 0.625rem 1.25rem;
    border-radius: 4px;
    text-decoration: none;
    font-size: 0.95rem;
    cursor: pointer;
    border: 1px solid transparent;
  }

  .btn.primary {
    background: var(--accent-color, #4a9eff);
    color: white;
  }

  .btn.primary:hover:not(:disabled) {
    background: var(--accent-color-hover, #3a8eef);
  }

  .btn.secondary {
    background: var(--bg-color, #fff);
    color: var(--text-color, #333);
    border-color: var(--border-color, #ccc);
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
