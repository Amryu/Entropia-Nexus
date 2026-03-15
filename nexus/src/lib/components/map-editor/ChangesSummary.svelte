<script>
  // @ts-nocheck
  import { apiPost, apiPut, apiDelete } from '$lib/util.js';
  import { addToast } from '$lib/stores/toasts.js';
  import { getEffectiveType, DEFAULT_ALTITUDE } from './mapEditorUtils.js';
  import { SvelteMap } from 'svelte/reactivity';

  
  /**
   * @typedef {Object} Props
   * @property {any} [pendingChanges]
   * @property {any} [planet]
   * @property {boolean} [isAdmin]
   * @property {any} [dbChangeIdMap] - Maps local pending change key → DB change ID for PUT updates
   */

  /** @type {Props} */
  let {
    pendingChanges = $bindable(new SvelteMap()),
    planet = null,
    isAdmin = false,
    dbChangeIdMap = new SvelteMap(),
    onchangeCreated,
    onsubmitted,
    onclear,
    onremoved,
    ondbChangeDeleted
  } = $props();

  let submitting = $state(false);
  let directApplying = $state(false);
  let changeStatuses = $state({}); // changeKey → 'pending' | 'submitting' | 'success' | 'error'

  let changeList = $derived(Array.from(pendingChanges.entries())
    .filter(([, change]) => !change._dbSeeded)
    .map(([key, change]) => ({ key, ...change })));

  let addCount = $derived(changeList.filter(c => c.action !== 'delete' && !c.original && !dbChangeIdMap.has(c.key)).length);
  let editCount = $derived(changeList.filter(c => c.action !== 'delete' && (c.original || dbChangeIdMap.has(c.key))).length);
  let deleteCount = $derived(changeList.filter(c => c.action === 'delete').length);

  /** Validate a single change. Returns an error string or null. */
  function validateChange(change) {
    if (change.action === 'delete') return null;
    const mod = change.modified;
    if (!mod) return null;

    const name = mod.name || change.original?.Name || '';
    if (!name.trim()) return 'Name is required';

    const effectiveLocationType = mod.locationType ||
      ((change.original?.Properties?.Shape || change.original?.Properties?.AreaType || change.original?.Properties?.Type === 'Area') ? 'Area' : change.original?.Properties?.Type) ||
      null;
    const effectiveAreaType = mod.areaType ?? change.original?.Properties?.AreaType ?? null;

    if (effectiveLocationType === 'Area' && effectiveAreaType === 'MobArea') {
      // Check pending mob data, or fall back to original location's maturities
      const hasMobs = mod.maturities?.length || change.original?.Maturities?.length;
      if (!hasMobs) return 'Mob area requires at least one mob maturity';
    }

    if (effectiveLocationType === 'Area' && effectiveAreaType === 'WaveEventArea') {
      // Check pending wave data, or fall back to original location's waves
      const waves = mod.waves ?? change.original?.Waves;
      if (!waves?.length) return 'Wave event area requires at least one wave';
      for (const wave of waves) {
        if (!wave.MobMaturities?.length) return `Wave ${wave.WaveIndex} has no maturities`;
      }
    }

    return null;
  }

  let validationErrors = $derived((() => {
    const errors = {};
    for (const change of changeList) {
      const err = validateChange(change);
      if (err) errors[change.key] = err;
    }
    return errors;
  })());

  let hasValidationErrors = $derived(Object.keys(validationErrors).length > 0);

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

    // Fall back to original data for fields not present in modified
    const orig = change.original || null;
    const origProps = orig?.Properties;
    const origCoords = origProps?.Coordinates;

    const effectiveLocationType = mod.locationType ||
      ((origProps?.Shape || origProps?.AreaType || origProps?.Type === 'Area') ? 'Area' : origProps?.Type) ||
      null;
    if (!effectiveLocationType) return null;
    const isArea = effectiveLocationType === 'Area';
    const props = {
      Type: isArea ? 'Area' : effectiveLocationType,
      Coordinates: {
        Longitude: mod.longitude ?? origCoords?.Longitude ?? null,
        Latitude: mod.latitude ?? origCoords?.Latitude ?? null,
        Altitude: mod.altitude !== undefined ? mod.altitude : (origCoords?.Altitude ?? DEFAULT_ALTITUDE)
      },
      Description: mod.description !== undefined ? (mod.description || null) : (origProps?.Description || null)
    };

    if (isArea) {
      props.AreaType = mod.areaType ?? origProps?.AreaType ?? null;
      props.Shape = mod.shape ?? origProps?.Shape ?? null;
      props.Data = mod.shapeData !== undefined ? mod.shapeData : (origProps?.Data ?? null);

      // LandArea extension fields
      const effectiveAreaType = props.AreaType;
      if (effectiveAreaType === 'LandArea') {
        props.TaxRateHunting = mod.taxRateHunting !== undefined ? mod.taxRateHunting : (origProps?.TaxRateHunting ?? null);
        props.TaxRateMining = mod.taxRateMining !== undefined ? mod.taxRateMining : (origProps?.TaxRateMining ?? null);
        props.TaxRateShops = mod.taxRateShops !== undefined ? mod.taxRateShops : (origProps?.TaxRateShops ?? null);
        const ownerName = mod.landAreaOwner !== undefined ? mod.landAreaOwner : origProps?.LandAreaOwnerName;
        if (ownerName) props.LandAreaOwnerName = ownerName;
      }

      // Density: use pending value if set, otherwise preserve original
      if (mod.density != null) {
        props.Density = mod.density;
      } else if (origProps?.Density != null) {
        props.Density = origProps.Density;
      }

      // MobArea boolean flags
      if (mod.isEvent != null) props.IsEvent = mod.isEvent;
      else if (origProps?.IsEvent != null) props.IsEvent = origProps.IsEvent;
      if (mod.isShared != null) props.IsShared = mod.isShared;
      else if (origProps?.IsShared != null) props.IsShared = origProps.IsShared;
    }

    const body = {
      Id: change.original?.Id || null,
      Name: mod.name ?? orig?.Name ?? '',
      Properties: props,
      Planet: { Name: planet?.Name }
    };

    // MobArea maturities (stored at body level, not in Properties)
    if (mod.maturities) {
      body.Maturities = mod.maturities;
    }

    // WaveEvent wave data (stored at body level, not in Properties)
    if (props.AreaType === 'WaveEventArea' && mod.waves) {
      body.Waves = mod.waves;
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

    try {
      const changeType = change.action === 'delete' ? 'Delete' : ((change.original?.Id || dbChangeIdMap.has(change.key)) ? 'Update' : 'Create');
      const body = buildEntityBody(change);

      if (!body) {
        changeStatuses[key] = 'error';
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
        // After first POST, store the DB change ID so re-submissions use PUT
        if (!existingChangeId) {
          onchangeCreated?.({ key, changeId: result.id });
        }
        changeStatuses[key] = 'success';
        return true;
      } else {
        changeStatuses[key] = 'error';
        addToast(`Failed to submit: ${result?.error || 'Unknown error'}`, { type: 'error' });
        return false;
      }
    } catch (e) {
      changeStatuses[key] = 'error';
      addToast(`Submit error: ${e.message}`, { type: 'error' });
      return false;
    }
  }

  async function submitAll() {
    if (hasValidationErrors) {
      addToast('Fix validation errors before submitting', { type: 'error' });
      return;
    }

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
      onsubmitted?.();
    }
  }

  async function directApplyAll() {
    if (hasValidationErrors) {
      addToast('Fix validation errors before applying', { type: 'error' });
      return;
    }
    if (!confirm(`Directly apply ${changeList.length} change(s)? This will be applied immediately.`)) return;
    directApplying = true;
    let successCount = 0;

    for (const change of changeList) {
      if (changeStatuses[change.key] === 'success') continue;

      const key = change.key;
      changeStatuses[key] = 'submitting';

      try {
        const changeType = change.action === 'delete' ? 'Delete' : ((change.original?.Id || dbChangeIdMap.has(change.key)) ? 'Update' : 'Create');
        const body = buildEntityBody(change);

        if (!body) {
          changeStatuses[key] = 'error';
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
          if (!existingChangeId) {
            onchangeCreated?.({ key, changeId: result.id });
          }
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
    }

    directApplying = false;

    if (successCount > 0) {
      addToast(`Directly applied ${successCount} change(s)`, { type: 'success' });
      onsubmitted?.();
    }
  }

  function clearAll() {
    onclear?.();
    changeStatuses = {};
  }

  async function deleteDbChange(key) {
    const dbId = dbChangeIdMap.get(key);
    if (!dbId) return;
    if (!confirm('Delete this submitted change? This cannot be undone.')) return;

    changeStatuses[key] = 'submitting';

    try {
      const res = await apiDelete(fetch, `/api/changes/${dbId}`);
      if (!res?.error) {
        // 204 No Content → apiDelete returns null on success
        pendingChanges.delete(key);
        dbChangeIdMap.delete(key);
        delete changeStatuses[key];
        addToast('Change deleted', { type: 'success' });
        ondbChangeDeleted?.({ key, dbId });
        onsubmitted?.();
      } else {
        changeStatuses[key] = 'error';
        addToast(`Delete failed: ${res.error}`, { type: 'error' });
      }
    } catch (e) {
      changeStatuses[key] = 'error';
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
    const origProps = change.original?.Properties || null;
    const effectiveLocationType = mod.locationType ||
      ((origProps?.Shape || origProps?.AreaType || origProps?.Type === 'Area') ? 'Area' : origProps?.Type) ||
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

  .change-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .change-row.has-error {
    background: rgba(239, 68, 68, 0.06);
  }

  .validation-error {
    font-size: 10px;
    color: #ef4444;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
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
          <span class="badge delete">{deleteCount} deletion{deleteCount > 1 ? 's' : ''}</span>
        {/if}
      </div>
    </div>

    <div class="changes-list">
      {#each changeList as change (change.key)}
        {@const name = change.modified?.name || change.original?.Name || '(Unnamed)'}
        {@const type = change.action === 'delete' ? getEffectiveType(change.original) : (change.modified?.areaType || change.modified?.locationType || '')}
        {@const statusKey = changeStatuses[change.key]}
        {@const hasDbChange = dbChangeIdMap.has(change.key)}
        {@const displayAction = change.action === 'delete' ? 'delete' : ((change.original || dbChangeIdMap.has(change.key)) ? 'edit' : 'add')}
        {@const validationError = validationErrors[change.key]}
        <div class="change-row" class:has-error={!!validationError}>
          <span class="action-indicator" style="color: {getActionColor(displayAction)}">{getActionLabel(displayAction)}</span>
          <div class="change-info">
            <span class="change-name">{name}</span>
            {#if validationError}
              <span class="validation-error">{validationError}</span>
            {/if}
          </div>
          <span class="change-type">{type}</span>
          {#if statusKey}
            <span class="status-indicator {statusKey}">{getStatusIcon(change.key)}</span>
          {/if}
          {#if hasDbChange}
            <button class="row-delete-btn" title="Delete submitted change" onclick={() => deleteDbChange(change.key)} disabled={submitting || directApplying}>×</button>
          {:else}
            <button class="row-remove-btn" title="Revert" onclick={() => { pendingChanges.delete(change.key); onremoved?.(change.key); }}>×</button>
          {/if}
        </div>
      {/each}
    </div>

    <div class="changes-actions">
      {#if isAdmin}
        <button class="btn btn-apply" onclick={directApplyAll} disabled={submitting || directApplying || changeList.length === 0 || hasValidationErrors}>
          {directApplying ? 'Applying...' : `Direct Apply ${changeList.length} Change(s)`}
        </button>
      {/if}
      <button class="btn btn-primary" onclick={submitAll} disabled={submitting || directApplying || changeList.length === 0 || hasValidationErrors}>
        {submitting ? 'Submitting...' : `Submit ${changeList.length} Change(s)`}
      </button>
      <button class="btn btn-danger" onclick={clearAll} disabled={submitting || directApplying}>
        Clear All
      </button>
    </div>
  </div>
{/if}
