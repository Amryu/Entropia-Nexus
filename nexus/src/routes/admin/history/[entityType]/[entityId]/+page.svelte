<script>
  // @ts-nocheck
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { apiCall, getTypeName, getTypeLink } from '$lib/util.js';
  import ChangeDataViewer from '$lib/components/ChangeDataViewer.svelte';
  import { clickable } from '$lib/actions/clickable.js';

  $: entityType = $page.params.entityType;
  $: entityId = $page.params.entityId;

  let changes = [];
  let originalVersion = null;
  let auditHistory = [];
  let entityName = '';
  let isLoading = true;
  let error = null;

  // Diff comparison state
  let leftVersion = null;  // 'original', 'audit-{timestamp}', or 'change-{id}'
  let rightVersion = null;
  let leftData = null;
  let rightData = null;

  onMount(async () => {
    await loadEntityHistory();
  });

  async function loadEntityHistory() {
    isLoading = true;
    error = null;

    try {
      // Load changes from entity-changes API
      const changesData = await apiCall(fetch, `/entity-changes/${entityType}/${encodeURIComponent(entityId)}`);
      if (changesData) {
        changes = changesData.changes || [];
        entityName = changesData.entityName || entityId;
      }

      // Try to load audit history (original version) via SvelteKit proxy (applies schema validation)
      // Only if we have a numeric entity ID
      if (/^\d+$/.test(entityId)) {
        const auditResponse = await fetch(`/api/admin/audit/${entityType}/${entityId}`);
        if (auditResponse.ok) {
          const auditData = await auditResponse.json();
          if (auditData?.history) {
            auditHistory = auditData.history;
          }
        }

        const originalResponse = await fetch(`/api/admin/audit/${entityType}/${entityId}/original`);
        if (originalResponse.ok) {
          const originalData = await originalResponse.json();
          if (originalData?.original) {
            originalVersion = originalData.original;
          }
        }
      }

      // Set default comparison: original (if available) vs latest change
      if (changes.length > 0) {
        rightVersion = `change-${changes[changes.length - 1].id}`;
        rightData = changes[changes.length - 1].data;

        if (originalVersion) {
          leftVersion = 'original';
          leftData = originalVersion.Data;
        } else if (changes.length > 1) {
          leftVersion = `change-${changes[0].id}`;
          leftData = changes[0].data;
        }
      }
    } catch (err) {
      error = err.message || 'Failed to load entity history';
    } finally {
      isLoading = false;
    }
  }

  function getVersionOptions() {
    const options = [];

    // Original version from audit
    if (originalVersion) {
      options.push({
        value: 'original',
        label: `Original (${formatDate(originalVersion.Timestamp)})`,
        data: originalVersion.Data,
        type: 'audit'
      });
    }

    // Audit history entries (excluding original if it's Insert)
    auditHistory.forEach((entry, i) => {
      // Skip if it's the same as original
      if (originalVersion && entry.Timestamp === originalVersion.Timestamp) return;

      options.push({
        value: `audit-${entry.Timestamp}`,
        label: `${entry.Operation} (${formatDate(entry.Timestamp)})`,
        data: entry.Data,
        type: 'audit'
      });
    });

    // Change request versions
    changes.forEach((change, i) => {
      options.push({
        value: `change-${change.id}`,
        label: `Change #${change.id} - ${change.type} (${formatDate(change.createdAt)}) [${change.state}]`,
        data: change.data,
        type: 'change'
      });
    });

    return options;
  }

  function setLeftVersion(value) {
    leftVersion = value;
    const options = getVersionOptions();
    const selected = options.find(o => o.value === value);
    leftData = selected?.data || null;
  }

  function setRightVersion(value) {
    rightVersion = value;
    const options = getVersionOptions();
    const selected = options.find(o => o.value === value);
    rightData = selected?.data || null;
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function goBack() {
    goto('/admin/history');
  }

  function getStateClass(state) {
    switch (state) {
      case 'Approved': return 'state-approved';
      case 'Denied': return 'state-denied';
      case 'Pending': return 'state-pending';
      default: return 'state-draft';
    }
  }

  function viewChange(changeId) {
    goto(`/admin/changes/${changeId}`);
  }

  $: versionOptions = getVersionOptions();
  $: wikiLink = entityName ? getTypeLink(entityName, entityType) : null;

  // Audit data is already schema-validated (extra properties stripped by proxy).
  // Change data from the changes system doesn't have extra API fields.
  $: normalizedLeft = leftData ? JSON.parse(JSON.stringify(leftData)) : null;
  $: normalizedRight = rightData ? JSON.parse(JSON.stringify(rightData)) : null;
</script>

<svelte:head>
  <title>{entityName || entityId} History | Admin | Entropia Nexus</title>
</svelte:head>

<style>
  .history-detail {
    max-width: 1400px;
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

  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 24px;
    gap: 16px;
    flex-wrap: wrap;
  }

  .header-left h1 {
    margin: 0 0 8px 0;
    font-size: 24px;
    color: var(--text-color);
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .entity-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 14px;
    color: var(--text-muted);
  }

  .type-badge {
    padding: 3px 10px;
    background-color: var(--hover-color);
    border-radius: 4px;
    font-size: 12px;
    color: var(--accent-color);
  }

  .wiki-link {
    color: var(--accent-color);
    text-decoration: none;
    font-size: 13px;
  }

  .wiki-link:hover {
    text-decoration: underline;
  }

  .back-btn {
    padding: 8px 16px;
    background-color: var(--hover-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .back-btn:hover {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .section {
    margin-bottom: 32px;
  }

  .section h2 {
    margin: 0 0 16px 0;
    font-size: 18px;
    color: var(--text-color);
  }

  /* Changes timeline */
  .changes-timeline {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }

  .timeline-item {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 18px;
    border-bottom: 1px solid var(--border-color);
    cursor: pointer;
    transition: background-color 0.15s ease;
  }

  .timeline-item:last-child {
    border-bottom: none;
  }

  .timeline-item:hover {
    background-color: var(--hover-color);
  }

  .timeline-marker {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .timeline-marker.audit { background-color: #8b5cf6; }
  .timeline-marker.change { background-color: var(--accent-color); }

  .timeline-content {
    flex: 1;
    min-width: 0;
  }

  .timeline-title {
    font-weight: 500;
    color: var(--text-color);
    margin-bottom: 4px;
  }

  .timeline-meta {
    font-size: 12px;
    color: var(--text-muted);
  }

  .state-badge {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
  }

  .state-approved { background-color: rgba(34, 197, 94, 0.2); color: var(--success-color); }
  .state-denied { background-color: rgba(239, 68, 68, 0.2); color: var(--error-color); }
  .state-pending { background-color: rgba(245, 158, 11, 0.2); color: var(--warning-color); }
  .state-draft { background-color: var(--hover-color); color: var(--text-muted); }

  /* Comparison section */
  .comparison-section {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 20px;
  }

  .comparison-header {
    display: flex;
    gap: 16px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }

  .version-select-group {
    flex: 1;
    min-width: 250px;
  }

  .version-select-group label {
    display: block;
    font-size: 12px;
    color: var(--text-muted);
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .version-select {
    width: 100%;
    padding: 10px 14px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--primary-color);
    color: var(--text-color);
    font-size: 14px;
  }

  .comparison-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }

  .comparison-column {
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
  }

  .comparison-column-header {
    padding: 12px 16px;
    background-color: var(--hover-color);
    border-bottom: 1px solid var(--border-color);
    font-weight: 500;
    font-size: 13px;
    color: var(--text-muted);
  }

  .comparison-column-content {
    max-height: 600px;
    overflow-y: auto;
  }

  .no-data {
    padding: 40px;
    text-align: center;
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

  /* Mobile responsive */
  @media (max-width: 900px) {
    .comparison-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 768px) {
    .page-header {
      flex-direction: column;
    }

    .header-left h1 {
      font-size: 20px;
    }

    .back-btn {
      width: 100%;
    }

    .breadcrumb {
      font-size: 12px;
      flex-wrap: wrap;
    }

    .timeline-item {
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
      padding: 12px 14px;
    }

    .comparison-header {
      flex-direction: column;
    }

    .version-select-group {
      min-width: unset;
    }
  }
</style>

<div class="history-detail">
  <div class="breadcrumb">
    <a href="/admin">Admin</a>
    <span>/</span>
    <a href="/admin/history">Entity History</a>
    <span>/</span>
    <span>{entityName || entityId}</span>
  </div>

  {#if isLoading}
    <div class="loading">Loading entity history...</div>
  {:else if error}
    <div class="error">Error: {error}</div>
  {:else}
    <div class="page-header">
      <div class="header-left">
        <h1>
          {entityName || entityId}
        </h1>
        <div class="entity-meta">
          <span class="type-badge">{getTypeName(entityType)}</span>
          {#if /^\d+$/.test(entityId)}
            <span>ID: {entityId}</span>
          {/if}
          {#if wikiLink}
            <a href={wikiLink} class="wiki-link">View Wiki Page</a>
          {/if}
        </div>
      </div>
      <button class="back-btn" on:click={goBack}>Back to Search</button>
    </div>

    {#if changes.length === 0 && auditHistory.length === 0}
      <div class="no-data">No history found for this entity</div>
    {:else}
      <div class="section">
        <h2>Change Timeline ({changes.length} changes{auditHistory.length > 0 ? `, ${auditHistory.length} audit records` : ''})</h2>
        <div class="changes-timeline">
          {#if originalVersion}
            <div class="timeline-item">
              <div class="timeline-marker audit"></div>
              <div class="timeline-content">
                <div class="timeline-title">Original Creation</div>
                <div class="timeline-meta">
                  {formatDate(originalVersion.Timestamp)}
                  {#if originalVersion.UserId}
                    <span> by {originalVersion.UserId}</span>
                  {/if}
                </div>
              </div>
            </div>
          {/if}

          {#each changes as change}
            <div class="timeline-item" use:clickable on:click={() => viewChange(change.id)}>
              <div class="timeline-marker change"></div>
              <div class="timeline-content">
                <div class="timeline-title">
                  Change #{change.id} - {change.type}
                </div>
                <div class="timeline-meta">
                  {formatDate(change.createdAt)}
                  <span class="state-badge {getStateClass(change.state)}">{change.state}</span>
                </div>
              </div>
            </div>
          {/each}
        </div>
      </div>

      {#if versionOptions.length >= 2}
        <div class="section">
          <h2>Compare Versions</h2>
          <div class="comparison-section">
            <div class="comparison-header">
              <div class="version-select-group">
                <label>Left (Previous)</label>
                <select class="version-select" value={leftVersion} on:change={(e) => setLeftVersion(e.target.value)}>
                  <option value="">Select version...</option>
                  {#each versionOptions as option}
                    <option value={option.value}>{option.label}</option>
                  {/each}
                </select>
              </div>
              <div class="version-select-group">
                <label>Right (Current)</label>
                <select class="version-select" value={rightVersion} on:change={(e) => setRightVersion(e.target.value)}>
                  <option value="">Select version...</option>
                  {#each versionOptions as option}
                    <option value={option.value}>{option.label}</option>
                  {/each}
                </select>
              </div>
            </div>

            <div class="comparison-grid">
              <div class="comparison-column">
                <div class="comparison-column-header">
                  {leftVersion ? versionOptions.find(o => o.value === leftVersion)?.label : 'Select a version'}
                </div>
                <div class="comparison-column-content">
                  {#if normalizedLeft}
                    <ChangeDataViewer data={normalizedLeft} entity={entityType} />
                  {:else}
                    <div class="no-data">Select a version to compare</div>
                  {/if}
                </div>
              </div>

              <div class="comparison-column">
                <div class="comparison-column-header">
                  {rightVersion ? versionOptions.find(o => o.value === rightVersion)?.label : 'Select a version'}
                </div>
                <div class="comparison-column-content">
                  {#if normalizedRight}
                    <ChangeDataViewer
                      data={normalizedRight}
                      previousData={normalizedLeft}
                      entity={entityType}
                    />
                  {:else}
                    <div class="no-data">Select a version to compare</div>
                  {/if}
                </div>
              </div>
            </div>
          </div>
        </div>
      {:else if versionOptions.length === 1}
        <div class="section">
          <h2>Data</h2>
          <div class="comparison-section">
            <ChangeDataViewer data={versionOptions[0].data} entity={entityType} />
          </div>
        </div>
      {/if}
    {/if}
  {/if}
</div>
