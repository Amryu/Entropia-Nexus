<script>
  // @ts-nocheck
  import { generateAllSql } from './adminMapUtils.js';

  export let pendingChanges = new Map();
  export let planetId = null;

  $: sql = generateAllSql(pendingChanges, planetId);
  $: changeCount = pendingChanges.size;

  $: stats = (() => {
    let adds = 0, edits = 0, deletes = 0;
    for (const [, c] of pendingChanges) {
      if (c.action === 'add') adds++;
      else if (c.action === 'edit') edits++;
      else if (c.action === 'delete') deletes++;
    }
    return { adds, edits, deletes };
  })();

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
    }
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
  .sql-actions button:hover { background: var(--hover-color); }
  .sql-actions .clear-btn { color: #ef4444; border-color: #ef4444; }

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
    <button on:click={copyToClipboard} disabled={changeCount === 0}>Copy All</button>
    <button on:click={downloadSql} disabled={changeCount === 0}>Download .sql</button>
    <button class="clear-btn" on:click={clearAll} disabled={changeCount === 0}>Clear All</button>
  </div>

  <div class="sql-content">
    {#if changeCount === 0}
      <div class="no-changes">No pending changes. Edit locations or draw new shapes to generate SQL.</div>
    {:else}
      <pre>{sql}</pre>
    {/if}
  </div>
</div>
