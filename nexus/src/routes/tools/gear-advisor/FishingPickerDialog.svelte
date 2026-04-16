<!--
  @component FishingPickerDialog
  Modal table for browsing and selecting fishing rods or attachments.
  Shows all items with their stats in a sortable table.
-->
<script>
  // @ts-nocheck
  import { scoreSearchResult } from '$lib/search.js';

  let {
    open = $bindable(false),
    title = 'Select Item',
    entities = [],
    columns = [],
    selected = null,
    onselect = () => {}
  } = $props();

  let query = $state('');
  let sortKey = $state('Name');
  let sortAsc = $state(true);

  function resolve(entity, col) {
    if (col.key === 'Name') return entity.Name;
    const parts = col.key.split('.');
    let v = entity;
    for (const p of parts) { v = v?.[p]; if (v == null) return null; }
    return v;
  }

  let filtered = $derived.by(() => {
    let list = entities;
    const q = query.trim();
    if (q) {
      const scored = [];
      for (const e of list) {
        const score = scoreSearchResult(e?.Name || '', q);
        if (score > 0) scored.push({ e, score });
      }
      scored.sort((a, b) => b.score - a.score);
      list = scored.map(x => x.e);
    }
    if (!q && sortKey) {
      const col = columns.find(c => c.key === sortKey);
      list = [...list].sort((a, b) => {
        const va = resolve(a, col || { key: sortKey });
        const vb = resolve(b, col || { key: sortKey });
        if (va == null && vb == null) return 0;
        if (va == null) return 1;
        if (vb == null) return -1;
        if (typeof va === 'string') return sortAsc ? va.localeCompare(vb, undefined, { numeric: true }) : vb.localeCompare(va, undefined, { numeric: true });
        return sortAsc ? va - vb : vb - va;
      });
    }
    return list;
  });

  function toggleSort(key) {
    if (sortKey === key) sortAsc = !sortAsc;
    else { sortKey = key; sortAsc = true; }
  }

  function pick(entity) {
    onselect(entity);
    open = false;
  }

  function handleBackdrop(e) {
    if (e.target === e.currentTarget) open = false;
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') open = false;
  }

  function fmt(v, col) {
    if (v == null) return '-';
    if (col.suffix) return (Number.isInteger(v) ? v.toString() : v.toFixed(1)) + ' ' + col.suffix;
    if (typeof v === 'boolean') return v ? 'Yes' : 'No';
    if (typeof v === 'number') return Number.isInteger(v) ? v.toString() : v.toFixed(1);
    return String(v);
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div class="dialog-backdrop" role="dialog" tabindex="-1" aria-modal="true"
       onclick={handleBackdrop} onkeydown={handleKeydown}>
    <div class="dialog-panel" onclick={(e) => e.stopPropagation()}>
      <div class="dialog-header">
        <h3>{title}</h3>
        <button type="button" class="dialog-close" onclick={() => open = false}>&times;</button>
      </div>

      <div class="dialog-search">
        <!-- svelte-ignore a11y_autofocus -->
        <input
          type="text"
          class="search-input"
          placeholder="Filter by name..."
          bind:value={query}
          autofocus
        />
        <span class="result-count">{filtered.length} items</span>
      </div>

      <div class="dialog-body">
        <table class="picker-table">
          <thead>
            <tr>
              {#each columns as col (col.key)}
                <th class="col-{col.align || 'left'}"
                    onclick={() => toggleSort(col.key)}>
                  {col.label}
                  {#if sortKey === col.key}
                    <span class="sort-arrow">{sortAsc ? '\u25B2' : '\u25BC'}</span>
                  {/if}
                </th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each filtered as entity (entity.Id ?? entity.Name)}
              {@const isSel = selected && (selected === entity.Name || selected?.Name === entity.Name)}
              <tr class:is-selected={isSel} onclick={() => pick(entity)} ondblclick={() => pick(entity)}>
                {#each columns as col (col.key)}
                  {@const val = resolve(entity, col)}
                  <td class="col-{col.align || 'left'}">{fmt(val, col)}</td>
                {/each}
              </tr>
            {/each}
            {#if filtered.length === 0}
              <tr><td colspan={columns.length} class="empty-row">No items match your filter</td></tr>
            {/if}
          </tbody>
        </table>
      </div>
    </div>
  </div>
{/if}

<style>
  .dialog-backdrop {
    position: fixed;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
  }

  .dialog-panel {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    max-width: 900px;
    width: 100%;
    height: 75vh;
    display: flex;
    flex-direction: column;
  }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: var(--text-color);
  }

  .dialog-close {
    background: transparent;
    border: none;
    font-size: 20px;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }

  .dialog-close:hover {
    color: var(--text-color);
  }

  .dialog-search {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-bottom: 1px solid var(--border-color);
  }

  .search-input {
    flex: 1;
    padding: 6px 10px;
    font-size: 13px;
    background-color: var(--bg-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
  }

  .search-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .result-count {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .dialog-body {
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .picker-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  .picker-table thead {
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .picker-table th {
    padding: 8px 10px;
    font-weight: 600;
    color: var(--text-muted);
    background-color: var(--secondary-color);
    border-bottom: 2px solid var(--border-color);
    cursor: pointer;
    white-space: nowrap;
    user-select: none;
  }

  .picker-table th:hover {
    color: var(--text-color);
  }

  .sort-arrow {
    font-size: 9px;
    margin-left: 3px;
  }

  .picker-table td {
    padding: 6px 10px;
    border-bottom: 1px solid var(--border-color);
    color: var(--text-color);
    white-space: nowrap;
  }

  .picker-table tbody tr {
    cursor: pointer;
    transition: background-color 0.08s ease;
  }

  .picker-table tbody tr:hover {
    background-color: var(--hover-color);
  }

  .picker-table tbody tr.is-selected {
    background-color: color-mix(in srgb, var(--accent-color) 20%, transparent);
  }

  .col-right {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .col-center {
    text-align: center;
  }

  .empty-row {
    text-align: center;
    color: var(--text-muted);
    padding: 20px 10px;
  }

  @media (max-width: 600px) {
    .dialog-panel {
      max-height: 90vh;
    }
  }
</style>
