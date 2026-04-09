<!--
  @component ProfitabilityComparisonTable
  Multi-weapon comparison table for the (L) Weapon Profitability tool.
  Shows all comparison weapons vs a selected base weapon in a sortable table.
-->
<script>
  // @ts-nocheck
  import { exportCSV, exportJSON, exportTableAsImage } from './export-utils.js';
  import { formatPED, formatPct, formatNumber } from './weaponProfitability.js';

  let {
    baseWeapons = [],
    comparisonWeapons = [],
    compStats = [],
    allAnalyses = [],
    selectedBaseIndex = $bindable(0)
  } = $props();

  let sortKey = $state('netProfitabilityPED');
  let sortOrder = $state('DESC');
  let showExportMenu = $state(false);
  let tableEl = $state();

  let safeBaseIdx = $derived(Math.min(Math.max(0, selectedBaseIndex), baseWeapons.length - 1));
  let analyses = $derived(allAnalyses[safeBaseIdx] || []);

  // Build rows with index reference
  let rows = $derived.by(() => {
    return comparisonWeapons.map((cfg, i) => ({
      index: i,
      name: cfg.weaponName || `Weapon ${i + 1}`,
      mu: cfg.markupPercent ?? 100,
      efficiency: compStats[i]?.efficiency,
      dpp: compStats[i]?.dpp,
      dps: compStats[i]?.dps,
      totalUses: compStats[i]?.totalUses,
      ttCycled: analyses[i]?.compTotalCyclePED,
      savings: analyses[i]?.efficiencySavingsPED,
      premium: analyses[i]?.premiumDiffPED,
      net: analyses[i]?.netProfitabilityPED,
      breakEvenMU: analyses[i]?.breakEvenMU
    }));
  });

  // Sort rows
  let sortedRows = $derived.by(() => {
    const arr = [...rows];
    arr.sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === 'string') return sortOrder === 'ASC' ? va.localeCompare(vb) : vb.localeCompare(va);
      return sortOrder === 'ASC' ? va - vb : vb - va;
    });
    return arr;
  });

  const columns = [
    { key: 'name', label: 'Weapon', align: 'left' },
    { key: 'mu', label: 'MU%', fmt: v => v != null ? v.toFixed(1) + '%' : 'N/A' },
    { key: 'efficiency', label: 'Eff', fmt: v => v != null ? v.toFixed(1) : 'N/A' },
    { key: 'dpp', label: 'DPP', fmt: v => v != null ? v.toFixed(2) : 'N/A' },
    { key: 'dps', label: 'DPS', fmt: v => v != null ? v.toFixed(1) : 'N/A' },
    { key: 'totalUses', label: 'Uses', fmt: v => formatNumber(v) },
    { key: 'ttCycled', label: 'Total Cycle', fmt: v => v != null ? v.toFixed(2) : 'N/A' },
    { key: 'savings', label: 'Savings', fmt: v => v != null ? formatPED(v).text : 'N/A', color: v => v > 0.005 ? 'positive' : v < -0.005 ? 'negative' : '' },
    { key: 'premium', label: 'MU Cost', fmt: v => v != null ? v.toFixed(2) + ' PED' : 'N/A' },
    { key: 'net', label: 'Net', fmt: v => v != null ? formatPED(v).text : 'N/A', color: v => v > 0.005 ? 'positive' : v < -0.005 ? 'negative' : '' },
    { key: 'breakEvenMU', label: 'Breakeven MU', fmt: v => v != null ? v.toFixed(1) + '%' : 'N/A', color: (v, row) => v != null && row.mu > v ? 'negative' : '' }
  ];

  function toggleSort(key) {
    if (sortKey === key) {
      sortOrder = sortOrder === 'ASC' ? 'DESC' : 'ASC';
    } else {
      sortKey = key;
      sortOrder = 'DESC';
    }
  }

  function handleExport(format) {
    showExportMenu = false;
    const data = sortedRows.map(row => {
      const obj = {};
      for (const col of columns) {
        obj[col.label] = col.fmt ? col.fmt(row[col.key]) : row[col.key];
      }
      return obj;
    });

    if (format === 'csv') exportCSV(data, 'weapon-profitability');
    else if (format === 'json') exportJSON(data, 'weapon-profitability');
    else if (format === 'png' && tableEl) exportTableAsImage(tableEl, 'weapon-profitability');
  }
</script>

<div class="comparison-table-view">
  <!-- Header row: base selector + export -->
  <div class="table-controls">
    <label class="base-selector">
      <span>Base:</span>
      <select class="selector" bind:value={selectedBaseIndex}>
        {#each baseWeapons as bw, i}
          <option value={i}>{bw.weaponName || `Base ${i + 1}`}</option>
        {/each}
      </select>
    </label>

    <div class="export-container">
      <button type="button" class="export-btn"
        onclick={() => { showExportMenu = !showExportMenu; }}>
        Export ▾
      </button>
      {#if showExportMenu}
        <div class="export-menu">
          <button type="button" onclick={() => handleExport('csv')}>CSV</button>
          <button type="button" onclick={() => handleExport('json')}>JSON</button>
          <button type="button" onclick={() => handleExport('png')}>PNG</button>
        </div>
      {/if}
    </div>
  </div>

  <!-- Table -->
  <div class="table-scroll" bind:this={tableEl}>
    <table class="profitability-table">
      <thead>
        <tr>
          {#each columns as col}
            <th class="sortable" class:sorted={sortKey === col.key}
              style:text-align={col.align || 'right'}
              onclick={() => toggleSort(col.key)}>
              {col.label}
              {#if sortKey === col.key}
                <span class="sort-arrow">{sortOrder === 'ASC' ? '▲' : '▼'}</span>
              {/if}
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each sortedRows as row (row.index)}
          <tr>
            {#each columns as col}
              {@const value = row[col.key]}
              {@const colorClass = col.color ? col.color(value, row) : ''}
              <td style:text-align={col.align || 'right'}
                class={colorClass}>
                {col.fmt ? col.fmt(value) : (value ?? 'N/A')}
              </td>
            {/each}
          </tr>
        {/each}
        {#if sortedRows.length === 0}
          <tr>
            <td colspan={columns.length} class="empty-cell">No comparison weapons added.</td>
          </tr>
        {/if}
      </tbody>
    </table>
  </div>
</div>

<style>
  .comparison-table-view {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .table-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .base-selector {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--text-muted);
  }

  .selector {
    padding: 5px 8px;
    font-size: 13px;
    background: var(--bg-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    max-width: 220px;
  }

  .export-container {
    position: relative;
  }

  .export-btn {
    padding: 5px 12px;
    font-size: 12px;
    border: 1px solid var(--border-color);
    background: var(--bg-color);
    color: var(--text-muted);
    cursor: pointer;
    border-radius: 4px;
  }

  .export-btn:hover {
    background: var(--hover-color);
  }

  .export-menu {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    z-index: 50;
    display: flex;
    flex-direction: column;
    padding: 4px;
    min-width: 80px;
  }

  .export-menu button {
    padding: 6px 12px;
    font-size: 12px;
    text-align: left;
    background: transparent;
    border: none;
    color: var(--text-color);
    cursor: pointer;
    border-radius: 4px;
  }

  .export-menu button:hover {
    background: var(--hover-color);
  }

  .table-scroll {
    overflow-x: auto;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }

  .profitability-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    white-space: nowrap;
  }

  .profitability-table thead {
    background: var(--bg-color);
  }

  .profitability-table th {
    padding: 8px 12px;
    font-weight: 600;
    font-size: 12px;
    color: var(--text-muted);
    border-bottom: 2px solid var(--border-color);
    cursor: pointer;
    user-select: none;
    position: relative;
  }

  .profitability-table th.sortable:hover {
    color: var(--text-color);
  }

  .profitability-table th.sorted {
    color: var(--accent-color);
  }

  .sort-arrow {
    font-size: 10px;
    margin-left: 4px;
  }

  .profitability-table td {
    padding: 6px 12px;
    border-bottom: 1px solid var(--border-color);
    color: var(--text-color);
    font-variant-numeric: tabular-nums;
  }

  .profitability-table tbody tr:hover {
    background: var(--hover-color);
  }

  .profitability-table tbody tr:last-child td {
    border-bottom: none;
  }

  td.positive { color: var(--success-color, #27ae60); font-weight: 600; }
  td.negative { color: var(--danger-color, #e74c3c); font-weight: 600; }

  .empty-cell {
    text-align: center;
    color: var(--text-muted);
    padding: 24px 12px;
  }

  @media (max-width: 768px) {
    .profitability-table {
      font-size: 12px;
    }

    .profitability-table th,
    .profitability-table td {
      padding: 5px 8px;
    }
  }
</style>
