<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { apiPost, apiPut, apiDelete } from '$lib/util.js';
  import { addToast } from '$lib/stores/toasts.js';
  import { getEffectiveType } from './mapEditorUtils.js';

  export let pendingChanges = new Map();
  export let planet = null;
  export let isAdmin = false;
  /** Maps local pending change key → DB change ID for PUT updates */
  export let dbChangeIdMap = new Map();

  const dispatch = createEventDispatcher();

  let submitting = false;
  let directApplying = false;
  let changeStatuses = {}; // changeKey → 'pending' | 'submitting' | 'success' | 'error'

  $: changeList = Array.from(pendingChanges.entries()).map(([key, change]) => ({
    key,
    ...change
  }));

  $: addCount = changeList.filter(c => c.action === 'add').length;
  $: editCount = changeList.filter(c => c.action === 'edit').length;
  $: deleteCount = changeList.filter(c => c.action === 'delete').length;

  function buildEntityBody(change) {
    // Delete changes: construct body from original
    if (change.action === 'delete') {
      const orig = change.original;
      if (!orig) return null;
      return {
        Id: orig.Id,
        Name: orig.Name,
        Properties: {
          Type: orig.Properties?.Type || 'Area',
          Coordinates: {
            Longitude: orig.Properties?.Coordinates?.Longitude ?? null,
            Latitude: orig.Properties?.Coordinates?.Latitude ?? null,
            Altitude: orig.Properties?.Coordinates?.Altitude ?? null
          }
        },
        Planet: { Name: planet?.Name }
      };
    }

    const mod = change.modified;
    if (!mod) return null;

    // For edits, fall back to original data for fields not present in modified
    const orig = change.action === 'edit' ? change.original : null;
    const origProps = orig?.Properties;
    const origCoords = origProps?.Coordinates;

    const effectiveLocationType = mod.locationType ||
      ((origProps?.Shape || String(origProps?.Type || '').endsWith('Area')) ? 'Area' : origProps?.Type) ||
      null;
    if (!effectiveLocationType) return null;
    const isArea = effectiveLocationType === 'Area';
    const props = {
      Type: isArea ? 'Area' : effectiveLocationType,
      Coordinates: {
        Longitude: mod.longitude ?? origCoords?.Longitude ?? null,
        Latitude: mod.latitude ?? origCoords?.Latitude ?? null,
        Altitude: mod.altitude !== undefined ? mod.altitude : (origCoords?.Altitude ?? 100)
      },
      Description: mod.description !== undefined ? (mod.description || null) : (origProps?.Description || null)
    };

    if (isArea) {
      props.AreaType = mod.areaType || null;
      props.Shape = mod.shape || null;
      props.Data = mod.shapeData || null;

      // LandArea extension fields
      if (mod.areaType === 'LandArea') {
        props.TaxRateHunting = mod.taxRateHunting !== undefined ? mod.taxRateHunting : (origProps?.TaxRateHunting ?? null);
        props.TaxRateMining = mod.taxRateMining !== undefined ? mod.taxRateMining : (origProps?.TaxRateMining ?? null);
        props.TaxRateShops = mod.taxRateShops !== undefined ? mod.taxRateShops : (origProps?.TaxRateShops ?? null);
        const ownerName = mod.landAreaOwner !== undefined ? mod.landAreaOwner : origProps?.LandAreaOwnerName;
        if (ownerName) props.LandAreaOwnerName = ownerName;
      }

      // MobArea mob data (density + maturity selections)
      if (mod.mobData) {
        props.Density = mod.mobData.density ?? null;
        props.MobData = mod.mobData.maturities ?? null;
      }
    }

    const body = {
      Id: change.action === 'edit' ? change.original?.Id : null,
      Name: mod.name,
      Properties: props,
      Planet: { Name: planet?.Name }
    };

    // WaveEvent wave data (stored at body level, not in Properties)
    if (mod.areaType === 'WaveEvent' && mod.waveData) {
      body.Waves = mod.waveData.waves ?? [];
    }

    const parentName = mod.parentLocationName !== undefined ? mod.parentLocationName : orig?.ParentLocation?.Name;
    if (parentName) {
      body.ParentLocation = { Name: parentName };
    }

    return body;
  }

  async function submitChange(change) {
    const key = change.key;
    changeStatuses[key] = 'submitting';
    changeStatuses = changeStatuses;

    try {
      const changeType = change.action === 'add' ? 'Create' : (change.action === 'delete' ? 'Delete' : 'Update');
      const body = buildEntityBody(change);

      if (!body) {
        changeStatuses[key] = 'error';
        changeStatuses = changeStatuses;
        return false;
      }

      const existingChangeId = dbChangeIdMap.get(key);
      const entityType = body ? getEntityType(change) : 'Location';
      let result;
      if (existingChangeId) {
        // Update existing change via PUT
        result = await apiPut(
          fetch,
          `/api/changes/${existingChangeId}`,
          body
        );
      } else {
        result = await apiPost(
          fetch,
          `/api/changes?type=${changeType}&entity=${entityType}&state=Pending`,
          body
        );
      }

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
      // Skip already submitted
      if (changeStatuses[change.key] === 'success') continue;

      const ok = await submitChange(change);
      if (ok) successCount++;
    }

    submitting = false;

    if (successCount > 0) {
      addToast(`Submitted ${successCount} change(s) for review`, { type: 'success' });
      dispatch('submitted');
    }
  }

  async function directApplyAll() {
    if (!confirm(`Directly apply ${changeList.length} change(s)? This will be applied immediately.`)) return;
    directApplying = true;
    let successCount = 0;

    for (const change of changeList) {
      if (changeStatuses[change.key] === 'success') continue;

      const key = change.key;
      changeStatuses[key] = 'submitting';
      changeStatuses = changeStatuses;

      try {
        const changeType = change.action === 'add' ? 'Create' : (change.action === 'delete' ? 'Delete' : 'Update');
        const body = buildEntityBody(change);

        if (!body) {
          changeStatuses[key] = 'error';
          changeStatuses = changeStatuses;
          continue;
        }

        const existingChangeId = dbChangeIdMap.get(key);
        const entityType = body ? getEntityType(change) : 'Location';
        let result;
        if (existingChangeId) {
          result = await apiPut(
            fetch,
            `/api/changes/${existingChangeId}?state=DirectApply`,
            body
          );
        } else {
          result = await apiPost(
            fetch,
            `/api/changes?type=${changeType}&entity=${entityType}&state=DirectApply`,
            body
          );
        }

        if (result?.id) {
          changeStatuses[key] = 'success';
          successCount++;
        } else {
          changeStatuses[key] = 'error';
          addToast(`Failed to apply: ${result?.error || 'Unknown error'}`, { type: 'error' });
        }
      } catch (e) {
        changeStatuses[key] = 'error';
        addToast(`Apply error: ${e.message}`, { type: 'error' });
      }
      changeStatuses = changeStatuses;
    }

    directApplying = false;

    if (successCount > 0) {
      addToast(`Directly applied ${successCount} change(s)`, { type: 'success' });
      dispatch('submitted');
    }
  }

  function clearAll() {
    dispatch('clear');
    changeStatuses = {};
  }

  async function deleteDbChange(key) {
    const dbId = dbChangeIdMap.get(key);
    if (!dbId) return;
    if (!confirm('Delete this submitted change? This cannot be undone.')) return;

    changeStatuses[key] = 'submitting';
    changeStatuses = changeStatuses;

    try {
      const res = await apiDelete(fetch, `/api/changes/${dbId}`);
      if (!res?.error) {
        // 204 No Content → apiDelete returns null on success
        pendingChanges.delete(key);
        dbChangeIdMap.delete(key);
        pendingChanges = pendingChanges;
        delete changeStatuses[key];
        changeStatuses = changeStatuses;
        addToast('Change deleted', { type: 'success' });
        dispatch('dbChangeDeleted', { key, dbId });
        dispatch('submitted');
      } else {
        changeStatuses[key] = 'error';
        changeStatuses = changeStatuses;
        addToast(`Delete failed: ${res.error}`, { type: 'error' });
      }
    } catch (e) {
      changeStatuses[key] = 'error';
      changeStatuses = changeStatuses;
      addToast(`Delete error: ${e.message}`, { type: 'error' });
    }
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

  function getEntityType(change) {
    const mod = change.modified;
    if (!mod) return 'Location';
    const origProps = change.action === 'edit' ? change.original?.Properties : null;
    const effectiveLocationType = mod.locationType ||
      ((origProps?.Shape || String(origProps?.Type || '').endsWith('Area')) ? 'Area' : origProps?.Type) ||
      null;
    return effectiveLocationType === 'Area' ? 'Area' : 'Location';
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

  .btn-apply {
    background: #22c55e;
    color: white;
    border-color: #22c55e;
  }
  .btn-apply:hover:not(:disabled) { opacity: 0.9; }

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

  .row-delete-btn,
  .row-remove-btn {
    flex-shrink: 0;
    width: 18px;
    height: 18px;
    padding: 0;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background: transparent;
    cursor: pointer;
    font-size: 12px;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .row-delete-btn { color: #ef4444; border-color: #ef4444; }
  .row-delete-btn:hover:not(:disabled) { background: rgba(239, 68, 68, 0.15); }
  .row-delete-btn:disabled { opacity: 0.5; cursor: default; }
  .row-remove-btn { color: var(--text-muted); }
  .row-remove-btn:hover { background: var(--hover-color); color: var(--text-color); }
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
        {@const hasDbChange = dbChangeIdMap.has(change.key)}
        {@const displayAction = hasDbChange && change.action === 'add' ? 'edit' : change.action}
        <div class="change-row">
          <span class="action-indicator" style="color: {getActionColor(displayAction)}">{getActionLabel(displayAction)}</span>
          <span class="change-name">{name}</span>
          <span class="change-type">{type}</span>
          {#if statusKey}
            <span class="status-indicator {statusKey}">{getStatusIcon(change.key)}</span>
          {/if}
          {#if hasDbChange}
            <button class="row-delete-btn" title="Delete submitted change" on:click={() => deleteDbChange(change.key)} disabled={submitting || directApplying}>×</button>
          {:else}
            <button class="row-remove-btn" title="Revert" on:click={() => { pendingChanges.delete(change.key); pendingChanges = pendingChanges; dispatch('removed', change.key); }}>×</button>
          {/if}
        </div>
      {/each}
    </div>

    <div class="changes-actions">
      {#if isAdmin}
        <button class="btn btn-apply" on:click={directApplyAll} disabled={submitting || directApplying || changeList.length === 0}>
          {directApplying ? 'Applying...' : `Direct Apply ${changeList.length} Change(s)`}
        </button>
      {/if}
      <button class="btn btn-primary" on:click={submitAll} disabled={submitting || directApplying || changeList.length === 0}>
        {submitting ? 'Submitting...' : `Submit ${changeList.length} Change(s)`}
      </button>
      <button class="btn btn-danger" on:click={clearAll} disabled={submitting || directApplying}>
        Clear All
      </button>
    </div>
  </div>
{/if}
