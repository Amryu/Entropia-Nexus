<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { apiPost, apiPut } from '$lib/util.js';
  import { addToast } from '$lib/stores/toasts.js';
  import { getEffectiveType } from './mapEditorUtils.js';

  export let pendingChanges = new Map();
  export let planet = null;

  const dispatch = createEventDispatcher();

  let submitting = false;
  let changeStatuses = {}; // changeKey → 'pending' | 'submitting' | 'success' | 'error'

  $: changeList = Array.from(pendingChanges.entries()).map(([key, change]) => ({
    key,
    ...change
  }));

  $: addCount = changeList.filter(c => c.action === 'add').length;
  $: editCount = changeList.filter(c => c.action === 'edit').length;
  $: deleteCount = changeList.filter(c => c.action === 'delete').length;

  function buildEntityBody(change) {
    const mod = change.modified;
    if (!mod) return null;

    const isArea = mod.locationType === 'Area';

    if (isArea) {
      // Submit as Area entity
      return {
        Id: change.action === 'edit' ? change.original?.Id : null,
        Name: mod.name,
        Properties: {
          Description: null,
          Type: mod.areaType || null,
          Shape: mod.shape || null,
          Data: mod.shapeData || null,
          Coordinates: {
            Longitude: mod.longitude ?? null,
            Latitude: mod.latitude ?? null,
            Altitude: mod.altitude ?? null
          }
        },
        Planet: { Name: planet?.Name }
      };
    } else {
      // Submit as Location entity
      const body = {
        Id: change.action === 'edit' ? change.original?.Id : null,
        Name: mod.name,
        Properties: {
          Type: mod.locationType || 'Teleporter',
          Coordinates: {
            Longitude: mod.longitude ?? null,
            Latitude: mod.latitude ?? null,
            Altitude: mod.altitude ?? null
          }
        },
        Planet: { Name: planet?.Name }
      };
      return body;
    }
  }

  async function submitChange(change) {
    const key = change.key;
    changeStatuses[key] = 'submitting';
    changeStatuses = changeStatuses;

    try {
      const isArea = change.modified?.locationType === 'Area';
      const entityType = isArea ? 'Area' : 'Location';
      const changeType = change.action === 'add' ? 'Create' : 'Update';
      const body = buildEntityBody(change);

      if (!body) {
        changeStatuses[key] = 'error';
        changeStatuses = changeStatuses;
        return false;
      }

      const result = await apiPost(
        fetch,
        `/api/changes?type=${changeType}&entity=${entityType}&state=Pending`,
        body
      );

      if (result?.id) {
        changeStatuses[key] = 'success';
        changeStatuses = changeStatuses;
        return true;
      } else {
        changeStatuses[key] = 'error';
        changeStatuses = changeStatuses;
        addToast(`Failed to submit: ${result?.error || 'Unknown error'}`, { type: 'error' });
        return false;
      }
    } catch (e) {
      changeStatuses[key] = 'error';
      changeStatuses = changeStatuses;
      addToast(`Submit error: ${e.message}`, { type: 'error' });
      return false;
    }
  }

  async function submitAll() {
    submitting = true;
    let successCount = 0;

    for (const change of changeList) {
      // Skip deletes — info-only in public mode
      if (change.action === 'delete') continue;
      // Skip already submitted
      if (changeStatuses[change.key] === 'success') continue;

      const ok = await submitChange(change);
      if (ok) successCount++;
    }

    submitting = false;

    if (successCount > 0) {
      addToast(`Submitted ${successCount} change(s) for review`, { type: 'success' });
    }
  }

  function clearAll() {
    dispatch('clear');
    changeStatuses = {};
  }

  function getActionLabel(action) {
    if (action === 'add') return '+';
    if (action === 'edit') return '~';
    if (action === 'delete') return 'info';
    return '?';
  }

  function getActionColor(action) {
    if (action === 'add') return '#22c55e';
    if (action === 'edit') return '#f97316';
    if (action === 'delete') return '#94a3b8';
    return '#6b7280';
  }

  function getStatusIcon(key) {
    const s = changeStatuses[key];
    if (s === 'submitting') return '...';
    if (s === 'success') return 'OK';
    if (s === 'error') return '!!';
    return '';
  }
</script>

<style>
  .changes-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .changes-header {
    padding: 12px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .changes-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
    margin: 0 0 8px 0;
  }

  .summary-badges {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .badge {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
  }
  .badge.add { background: rgba(34, 197, 94, 0.15); color: #22c55e; }
  .badge.edit { background: rgba(249, 115, 22, 0.15); color: #f97316; }
  .badge.delete { background: rgba(148, 163, 184, 0.15); color: #94a3b8; }

  .changes-list {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
  }

  .change-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    font-size: 12px;
    color: var(--text-color);
    border-bottom: 1px solid var(--border-color);
  }

  .action-indicator {
    font-size: 11px;
    font-weight: 700;
    width: 20px;
    text-align: center;
    flex-shrink: 0;
  }

  .change-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .change-type {
    font-size: 10px;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .status-indicator {
    font-size: 10px;
    font-weight: 600;
    flex-shrink: 0;
    min-width: 20px;
    text-align: center;
  }
  .status-indicator.success { color: #22c55e; }
  .status-indicator.error { color: #ef4444; }
  .status-indicator.submitting { color: var(--accent-color); }

  .changes-actions {
    padding: 12px;
    border-top: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex-shrink: 0;
  }

  .btn {
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    text-align: center;
    background: var(--secondary-color);
    color: var(--text-color);
  }
  .btn:hover { background: var(--hover-color); }
  .btn:disabled { opacity: 0.5; cursor: default; }

  .btn-primary {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }
  .btn-primary:hover:not(:disabled) { opacity: 0.9; }

  .btn-danger {
    border-color: #ef4444;
    color: #ef4444;
  }
  .btn-danger:hover:not(:disabled) { background: rgba(239, 68, 68, 0.15); }

  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    font-size: 13px;
    text-align: center;
    padding: 20px;
  }

  .delete-note {
    font-size: 11px;
    color: var(--text-muted);
    padding: 0 12px 4px;
  }
</style>

{#if changeList.length === 0}
  <div class="empty-state">
    No pending changes. Draw or edit shapes to create changes.
  </div>
{:else}
  <div class="changes-container">
    <div class="changes-header">
      <h3 class="changes-title">Pending Changes</h3>
      <div class="summary-badges">
        {#if addCount > 0}
          <span class="badge add">+{addCount} add{addCount > 1 ? 's' : ''}</span>
        {/if}
        {#if editCount > 0}
          <span class="badge edit">~{editCount} edit{editCount > 1 ? 's' : ''}</span>
        {/if}
        {#if deleteCount > 0}
          <span class="badge delete">{deleteCount} info-only</span>
        {/if}
      </div>
    </div>

    <div class="changes-list">
      {#each changeList as change (change.key)}
        {@const name = change.modified?.name || change.original?.Name || 'Unknown'}
        {@const type = change.action === 'delete' ? getEffectiveType(change.original) : (change.modified?.areaType || change.modified?.locationType || '')}
        {@const statusKey = changeStatuses[change.key]}
        <div class="change-row">
          <span class="action-indicator" style="color: {getActionColor(change.action)}">{getActionLabel(change.action)}</span>
          <span class="change-name">{name}</span>
          <span class="change-type">{type}</span>
          {#if statusKey}
            <span class="status-indicator {statusKey}">{getStatusIcon(change.key)}</span>
          {/if}
        </div>
      {/each}
    </div>

    {#if deleteCount > 0}
      <div class="delete-note">
        Delete entries are info-only. Use "Copy Delete Info" on individual locations, or Multi-Select to copy.
      </div>
    {/if}

    <div class="changes-actions">
      <button class="btn btn-primary" on:click={submitAll} disabled={submitting || (addCount + editCount === 0)}>
        {submitting ? 'Submitting...' : `Submit ${addCount + editCount} Change(s)`}
      </button>
      <button class="btn btn-danger" on:click={clearAll} disabled={submitting}>
        Clear All
      </button>
    </div>
  </div>
{/if}
