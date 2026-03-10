<script>
  // @ts-nocheck
  import { generateAllSql } from './adminMapUtils.js';
  import { apiPost } from '$lib/util.js';
  import { addToast } from '$lib/stores/toasts.js';
  import { getEffectiveType } from '$lib/components/map-editor/mapEditorUtils.js';

  export let pendingChanges = new Map();
  export let planetId = null;
  export let planet = null;

  let directApplying = false;
  let changeStatuses = {}; // changeKey → 'submitting' | 'success' | 'error'

  $: sql = generateAllSql(pendingChanges, planetId);
  $: changeCount = pendingChanges.size;

  $: changeList = Array.from(pendingChanges.entries()).map(([key, change]) => ({
    key,
    ...change
  }));

  $: stats = (() => {
    let adds = 0, edits = 0, deletes = 0;
    for (const [, c] of pendingChanges) {
      if (c.action === 'add') adds++;
      else if (c.action === 'edit') edits++;
      else if (c.action === 'delete') deletes++;
    }
    return { adds, edits, deletes };
  })();

  function buildEntityBody(change) {
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

    const isArea = mod.locationType === 'Area';

    const props = {
      Type: isArea ? 'Area' : (mod.locationType || 'Teleporter'),
      Coordinates: {
        Longitude: mod.longitude ?? null,
        Latitude: mod.latitude ?? null,
        Altitude: mod.altitude ?? null
      }
    };

    if (isArea) {
      props.AreaType = mod.areaType || null;
      props.Shape = mod.shape || null;
      props.Data = mod.shapeData || null;

      if (mod.areaType === 'LandArea') {
        props.TaxRateHunting = mod.taxRateHunting ?? null;
        props.TaxRateMining = mod.taxRateMining ?? null;
        props.TaxRateShops = mod.taxRateShops ?? null;
        if (mod.landAreaOwner) props.LandAreaOwnerName = mod.landAreaOwner;
      }
    }

    const body = {
      Id: change.action === 'edit' ? change.original?.Id : null,
      Name: mod.name,
      Properties: props,
      Planet: { Name: planet?.Name }
    };

    if (mod.parentLocationName) {
      body.ParentLocation = { Name: mod.parentLocationName };
    }

    return body;
  }

  async function directApplyAll() {
    if (!confirm(`Directly apply ${changeCount} change(s)? This will be applied immediately.`)) return;
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

        const result = await apiPost(
          fetch,
          `/api/changes?type=${changeType}&entity=Location&state=DirectApply`,
          body
        );

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
    }
  }

  function copyToClipboard() {
    navigator.clipboard.writeText(sql).catch(() => {});
  }

  function downloadSql() {
    const blob = new Blob([sql], { type: 'text/sql' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `admin-map-changes-${new Date().toISOString().slice(0, 10)}.sql`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function clearAll() {
    if (confirm(`Clear all ${changeCount} pending changes?`)) {
      pendingChanges.clear();
      pendingChanges = pendingChanges;
      changeStatuses = {};
    }
  }

  function getStatusIcon(key) {
    const s = changeStatuses[key];
    if (s === 'submitting') return '...';
    if (s === 'success') return 'OK';
    if (s === 'error') return '!!';
    return '';
  }

  function getActionColor(action) {
    if (action === 'add') return '#22c55e';
    if (action === 'edit') return '#f97316';
    if (action === 'delete') return '#ef4444';
    return '#6b7280';
  }
</script>

<style>
  .sql-output {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .sql-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .sql-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .stats {
    display: flex;
    gap: 8px;
    font-size: 11px;
  }
  .stat-add { color: #22c55e; }
  .stat-edit { color: #f97316; }
  .stat-delete { color: #ef4444; }

  .sql-actions {
    display: flex;
    gap: 4px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
    flex-wrap: wrap;
  }

  .sql-actions button {
    padding: 6px 10px;
    font-size: 11px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    cursor: pointer;
    background: var(--secondary-color);
    color: var(--text-color);
  }
  .sql-actions button:hover:not(:disabled) { background: var(--hover-color); }
  .sql-actions button:disabled { opacity: 0.5; cursor: default; }
  .sql-actions .clear-btn { color: #ef4444; border-color: #ef4444; }
  .sql-actions .apply-btn { background: #22c55e; color: white; border-color: #22c55e; }
  .sql-actions .apply-btn:hover:not(:disabled) { opacity: 0.9; background: #22c55e; }

  .change-list {
    border-bottom: 1px solid var(--border-color);
    max-height: 150px;
    overflow-y: auto;
    flex-shrink: 0;
  }

  .change-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    font-size: 11px;
    color: var(--text-color);
    border-bottom: 1px solid var(--border-color);
  }
  .change-row:last-child { border-bottom: none; }

  .action-indicator {
    font-weight: 700;
    width: 14px;
    text-align: center;
    flex-shrink: 0;
  }

  .change-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .status-indicator {
    font-size: 10px;
    font-weight: 600;
    flex-shrink: 0;
    min-width: 18px;
    text-align: center;
  }
  .status-indicator.success { color: #22c55e; }
  .status-indicator.error { color: #ef4444; }
  .status-indicator.submitting { color: var(--accent-color); }

  .sql-content {
    flex: 1;
    overflow-y: auto;
    padding: 8px 12px;
    min-height: 0;
  }

  pre {
    margin: 0;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 11px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-all;
    color: var(--text-color);
  }

  /* Simple SQL syntax coloring */
  pre :global(.kw) { color: #569cd6; }
  pre :global(.str) { color: #ce9178; }
  pre :global(.comment) { color: #6a9955; }
  pre :global(.num) { color: #b5cea8; }

  .no-changes {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    font-size: 13px;
  }
</style>

<div class="sql-output">
  <div class="sql-header">
    <span class="sql-title">SQL Output</span>
    <div class="stats">
      {#if stats.adds}<span class="stat-add">+{stats.adds}</span>{/if}
      {#if stats.edits}<span class="stat-edit">~{stats.edits}</span>{/if}
      {#if stats.deletes}<span class="stat-delete">-{stats.deletes}</span>{/if}
    </div>
  </div>

  <div class="sql-actions">
    <button class="apply-btn" on:click={directApplyAll} disabled={changeCount === 0 || directApplying}>
      {directApplying ? 'Applying...' : 'Direct Apply'}
    </button>
    <button on:click={copyToClipboard} disabled={changeCount === 0}>Copy All</button>
    <button on:click={downloadSql} disabled={changeCount === 0}>Download .sql</button>
    <button class="clear-btn" on:click={clearAll} disabled={changeCount === 0 || directApplying}>Clear All</button>
  </div>

  {#if Object.keys(changeStatuses).length > 0}
    <div class="change-list">
      {#each changeList as change (change.key)}
        {@const name = change.modified?.name || change.original?.Name || 'Unknown'}
        {@const statusKey = changeStatuses[change.key]}
        {#if statusKey}
          <div class="change-row">
            <span class="action-indicator" style="color: {getActionColor(change.action)}">
              {change.action === 'add' ? '+' : change.action === 'edit' ? '~' : '-'}
            </span>
            <span class="change-name">{name}</span>
            <span class="status-indicator {statusKey}">{getStatusIcon(change.key)}</span>
          </div>
        {/if}
      {/each}
    </div>
  {/if}

  <div class="sql-content">
    {#if changeCount === 0}
      <div class="no-changes">No pending changes. Edit locations or draw new shapes to generate SQL.</div>
    {:else}
      <pre>{sql}</pre>
    {/if}
  </div>
</div>
