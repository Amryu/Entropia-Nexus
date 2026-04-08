<!--
  @component ComparisonDialog
  Side-by-side comparison of selected armor+plate ranking results against
  every maturity of the currently-selected mob, for one attack at a time.
  Columns: Maturity, Dmg, and per-set (Taken, Max Crit Dmg, Decay, Mit).
  Each column type can be toggled; per-set groups repeat uniformly.
-->
<script>
  // @ts-nocheck
  import { untrack } from 'svelte';
  import { SvelteSet } from 'svelte/reactivity';
  import {
    DEFAULT_ATTACK_NAME,
    computeDefenseLayers,
    computeLayerDecayRates,
    computeAttackBreakdown,
    sortedMaturities
  } from './armorVsMob.js';
  import { exportCSV, exportJSON, exportTableAsImage } from './export-utils.js';

  let {
    mob,
    armorRanking = [],
    iceShield = false,
    enhancers = 0,
    dmgMultiplier = 1,
    poolArmorEnhancers = {},
    poolArmorNamesActive = false,
    attackNames = [],
    selectedAttackName = $bindable(null),
    initialVisibleColumns,
    initialDefaultSelectedCount = 5,
    onclose = () => {},
    oncolumnschange = () => {}
  } = $props();

  const DEFAULT_VISIBLE_COLUMNS = {
    maturity: true, dmg: true,
    takenMin: false, takenExp: true, takenMax: false,
    crit: true, decay: true, mit: true
  };

  // Column visibility is a local copy so toggling here doesn't flicker in the
  // parent; we emit changes via oncolumnschange and the parent persists.
  // The initial value is snapshotted once (we explicitly don't want a live
  // binding back to the parent's prop).
  let visibleColumns = $state(untrack(() => ({
    ...DEFAULT_VISIBLE_COLUMNS,
    ...(initialVisibleColumns || {})
  })));
  $effect(() => {
    const _cols = visibleColumns;
    oncolumnschange({ ..._cols });
  });

  // Stable unique key per ranking result (duplicates allowed).
  function resultKey(r, i) {
    return `${r.armorSet?.Name ?? ''}|${r.plating?.Name ?? ''}|${i}`;
  }

  // Initial set selection = top-N by current ranking order.
  const initialKeys = untrack(() => {
    const n = Math.min(initialDefaultSelectedCount, armorRanking.length);
    const keys = [];
    for (let i = 0; i < n; i++) keys.push(resultKey(armorRanking[i], i));
    return keys;
  });
  const selectedKeys = new SvelteSet(initialKeys);

  function toggleResult(key) {
    if (selectedKeys.has(key)) selectedKeys.delete(key);
    else selectedKeys.add(key);
  }

  // Checked results in ranking order (stable).
  let selectedResults = $derived.by(() => {
    const out = [];
    for (let i = 0; i < armorRanking.length; i++) {
      const r = armorRanking[i];
      const key = resultKey(r, i);
      if (selectedKeys.has(key)) out.push({ r, key, i });
    }
    return out;
  });

  // Per-set precomputed defense + decay rate — recomputed when selection or
  // context (ice shield, enhancers, dmg multiplier, poolArmorEnhancers) change.
  let setContexts = $derived.by(() => {
    return selectedResults.map(({ r, key, i }) => {
      const effEnh = (poolArmorNamesActive && r.armorSet?.Name in (poolArmorEnhancers || {}))
        ? poolArmorEnhancers[r.armorSet.Name]
        : enhancers;
      const def = computeDefenseLayers(r.armorSet, r.plating, iceShield, effEnh);
      const dr = computeLayerDecayRates(r.armorSet, r.plating, iceShield);
      const label = r.plating
        ? `${r.armorSet?.Name ?? ''} + ${r.plating.Name}`
        : (r.armorSet?.Name ?? '');
      return { key, i, r, def, decayRates: dr, label };
    });
  });

  // Table body rows — one per maturity (for the currently selected attack).
  let tableRows = $derived.by(() => {
    if (!mob || !selectedAttackName) return [];
    const mats = sortedMaturities(mob);
    const out = [];
    for (const mat of mats) {
      const atk = (mat?.Attacks || []).find(
        a => (a?.Name || DEFAULT_ATTACK_NAME) === selectedAttackName
      );
      const perSet = setContexts.map(ctx => {
        if (!atk) return { hasData: false };
        const br = computeAttackBreakdown(atk, ctx.def, dmgMultiplier, ctx.decayRates);
        if (!(br.totalAvg > 0)) return { hasData: false };
        return {
          hasData: true,
          takenMin: br.takenMin,
          takenExp: br.expectedTaken,
          takenMax: br.takenMax,
          crit: br.critTaken,
          decay: br.expectedDecay,
          mit: br.mitigation
        };
      });
      out.push({
        maturityName: mat?.Name || '',
        maturityLevel: mat?.Properties?.Level ?? null,
        totalDamage: atk?.TotalDamage ?? null,
        perSet
      });
    }
    return out;
  });

  function fmt(n, digits = 1) {
    if (n == null || Number.isNaN(n)) return '—';
    return Number(n).toFixed(digits);
  }
  function fmtPct(n, digits = 0) {
    if (n == null || Number.isNaN(n)) return '—';
    return `${Number(n).toFixed(digits)}%`;
  }

  function selectAll() {
    for (let i = 0; i < armorRanking.length; i++) {
      selectedKeys.add(resultKey(armorRanking[i], i));
    }
  }
  function selectNone() {
    selectedKeys.clear();
  }
  function selectTopN(n) {
    selectedKeys.clear();
    const k = Math.min(n, armorRanking.length);
    for (let i = 0; i < k; i++) selectedKeys.add(resultKey(armorRanking[i], i));
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') onclose();
  }

  // --- Exports ----------------------------------------------------------

  let showExportMenu = $state(false);

  function exportFilenameBase() {
    const mobName = (mob?.Name || 'mob').replace(/[^A-Za-z0-9_-]+/g, '_');
    const atk = (selectedAttackName || 'attack').replace(/[^A-Za-z0-9_-]+/g, '_');
    return `gear-advisor_${mobName}_${atk}`;
  }

  function buildExportGrid() {
    // Build flat 2D grid that mirrors the visible table (respects column toggles).
    const vc = visibleColumns;
    const leadingHeaders = [];
    if (vc.maturity) leadingHeaders.push('Maturity');
    if (vc.dmg) leadingHeaders.push('Dmg');
    const perSetCols = [];
    if (vc.takenMin) perSetCols.push('Min');
    if (vc.takenExp) perSetCols.push('Exp');
    if (vc.takenMax) perSetCols.push('Max');
    if (vc.crit) perSetCols.push('Max Crit Dmg');
    if (vc.decay) perSetCols.push('Decay');
    if (vc.mit) perSetCols.push('Mit');
    // Flat header row (for CSV/JSON)
    const flatHeaders = [...leadingHeaders];
    for (const ctx of setContexts) {
      for (const c of perSetCols) flatHeaders.push(`${ctx.label} — ${c}`);
    }
    // 2-row header (for image)
    const topHeader = [];
    if (leadingHeaders.length > 0) {
      topHeader.push({ text: '', span: leadingHeaders.length });
    }
    for (const ctx of setContexts) {
      if (perSetCols.length > 0) {
        topHeader.push({ text: ctx.label, span: perSetCols.length });
      }
    }
    const bottomHeader = [...leadingHeaders];
    for (const _ of setContexts) for (const c of perSetCols) bottomHeader.push(c);

    // Data rows
    const dataRows = tableRows.map(row => {
      const out = [];
      if (vc.maturity) {
        const lvl = row.maturityLevel != null ? ` (L${row.maturityLevel})` : '';
        out.push(`${row.maturityName}${lvl}`);
      }
      if (vc.dmg) out.push(row.totalDamage != null ? fmt(row.totalDamage, 0) : null);
      row.perSet.forEach(s => {
        if (vc.takenMin) out.push(s.hasData ? fmt(s.takenMin) : null);
        if (vc.takenExp) out.push(s.hasData ? fmt(s.takenExp) : null);
        if (vc.takenMax) out.push(s.hasData ? fmt(s.takenMax) : null);
        if (vc.crit) out.push(s.hasData ? fmt(s.crit) : null);
        if (vc.decay) out.push(s.hasData ? fmt(s.decay, 3) : null);
        if (vc.mit) out.push(s.hasData ? fmtPct(s.mit * 100) : null);
      });
      return out;
    });

    // Indices of numeric columns (everything except Maturity is numeric).
    const numericCols = [];
    let idx = 0;
    if (vc.maturity) idx++;
    for (let j = idx; j < flatHeaders.length; j++) numericCols.push(j);

    return { flatHeaders, topHeader, bottomHeader, dataRows, numericCols };
  }

  function doExport(format) {
    showExportMenu = false;
    const grid = buildExportGrid();
    const base = exportFilenameBase();
    if (format === 'csv') {
      exportCSV(base, grid.flatHeaders, grid.dataRows);
    } else if (format === 'json') {
      const json = {
        mob: mob?.Name ?? null,
        attack: selectedAttackName,
        sets: setContexts.map(ctx => ({
          armor: ctx.r.armorSet?.Name ?? null,
          plating: ctx.r.plating?.Name ?? null
        })),
        columns: { ...visibleColumns },
        rows: tableRows.map(row => ({
          maturity: row.maturityName,
          level: row.maturityLevel,
          totalDamage: row.totalDamage,
          perSet: row.perSet.map((s, i) => ({
            set: setContexts[i]?.label ?? null,
            ...(s.hasData ? {
              takenMin: s.takenMin,
              takenExp: s.takenExp,
              takenMax: s.takenMax,
              crit: s.crit,
              decay: s.decay,
              mitigation: s.mit
            } : { hasData: false })
          }))
        }))
      };
      exportJSON(base, json);
    } else if (format === 'png') {
      exportTableAsImage(
        base,
        [grid.topHeader, grid.bottomHeader],
        grid.dataRows,
        {
          title: `${mob?.Name ?? ''} — ${selectedAttackName ?? ''}`,
          numericCols: grid.numericCols
        }
      );
    }
  }

  function toggleExportMenu(e) {
    e.stopPropagation();
    showExportMenu = !showExportMenu;
  }
  function closeExportMenu() {
    showExportMenu = false;
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div
  class="cmp-dialog-backdrop"
  onclick={onclose}
  role="presentation"
>
  <div
    class="cmp-dialog"
    onclick={(e) => { e.stopPropagation(); closeExportMenu(); }}
    onkeydown={(e) => e.stopPropagation()}
    role="dialog"
    aria-modal="true"
    aria-labelledby="compare-title"
    tabindex="-1"
  >
    <header class="dialog-header">
      <h3 id="compare-title">Compare armor sets{mob ? ` vs ${mob.Name}` : ''}</h3>
      <button class="close-btn" onclick={onclose} aria-label="Close">×</button>
    </header>

    <div class="dialog-toolbar">
      {#if attackNames.length > 1}
        <fieldset class="attack-picker">
          <legend>Attack</legend>
          {#each attackNames as name}
            <label class="attack-chip" class:active={selectedAttackName === name}>
              <input type="radio" bind:group={selectedAttackName} value={name} />
              <span>{name}</span>
            </label>
          {/each}
        </fieldset>
      {/if}

      <fieldset class="col-toggles">
        <legend>Columns</legend>
        <label><input type="checkbox" bind:checked={visibleColumns.maturity} /><span>Maturity</span></label>
        <label><input type="checkbox" bind:checked={visibleColumns.dmg} /><span>Dmg</span></label>
        <label title="Damage taken at the lowest roll (50% of base damage)"><input type="checkbox" bind:checked={visibleColumns.takenMin} /><span>Min</span></label>
        <label title="Expected damage taken (integrated over the 50%–100% damage roll range)"><input type="checkbox" bind:checked={visibleColumns.takenExp} /><span>Exp</span></label>
        <label title="Damage taken at the highest roll (100% of base damage)"><input type="checkbox" bind:checked={visibleColumns.takenMax} /><span>Max</span></label>
        <label><input type="checkbox" bind:checked={visibleColumns.crit} /><span>Crit</span></label>
        <label><input type="checkbox" bind:checked={visibleColumns.decay} /><span>Decay</span></label>
        <label><input type="checkbox" bind:checked={visibleColumns.mit} /><span>Mit</span></label>
      </fieldset>

      <div class="export-wrap" onclick={(e) => e.stopPropagation()} role="presentation">
        <button
          type="button"
          class="export-btn"
          onclick={toggleExportMenu}
          disabled={selectedResults.length === 0 || tableRows.length === 0}
          aria-haspopup="menu"
          aria-expanded={showExportMenu}
        >Export ▾</button>
        {#if showExportMenu}
          <div class="export-menu" role="menu">
            <button role="menuitem" onclick={() => doExport('csv')}>CSV</button>
            <button role="menuitem" onclick={() => doExport('json')}>JSON</button>
            <button role="menuitem" onclick={() => doExport('png')}>PNG image</button>
          </div>
        {/if}
      </div>
    </div>

    <div class="dialog-body">
      <aside class="pick-column" aria-label="Select sets">
        <div class="pick-header">
          <span class="count">{selectedKeys.size} / {armorRanking.length} selected</span>
          <div class="pick-actions">
            <button class="link-btn" onclick={() => selectTopN(5)}>Top 5</button>
            <button class="link-btn" onclick={selectAll}>All</button>
            <button class="link-btn" onclick={selectNone}>None</button>
          </div>
        </div>
        <div class="pick-list">
          {#each armorRanking as r, i (resultKey(r, i))}
            {@const key = resultKey(r, i)}
            <label class="pick-item" class:checked={selectedKeys.has(key)}>
              <input
                type="checkbox"
                checked={selectedKeys.has(key)}
                onchange={() => toggleResult(key)}
              />
              <span class="pick-rank">#{i + 1}</span>
              <span class="pick-name">
                {r.armorSet?.Name ?? ''}{#if r.plating}&nbsp;<span class="pick-plate">+ {r.plating.Name}</span>{/if}
              </span>
            </label>
          {/each}
        </div>
      </aside>

      <section class="table-pane" aria-label="Comparison table">
        {#if selectedResults.length === 0}
          <div class="empty-pane">Select one or more sets to compare.</div>
        {:else if tableRows.length === 0}
          <div class="empty-pane">No data for this mob.</div>
        {:else}
          <div class="table-scroll">
            <table class="cmp-table">
              <thead>
                <tr>
                  {#if visibleColumns.maturity}
                    <th rowspan="2" class="sticky-mat">Maturity</th>
                  {/if}
                  {#if visibleColumns.dmg}
                    <th rowspan="2" class="num dmg-col">Dmg</th>
                  {/if}
                  {#each setContexts as ctx (ctx.key)}
                    {@const perSetColSpan =
                      (visibleColumns.takenMin ? 1 : 0) +
                      (visibleColumns.takenExp ? 1 : 0) +
                      (visibleColumns.takenMax ? 1 : 0) +
                      (visibleColumns.crit ? 1 : 0) +
                      (visibleColumns.decay ? 1 : 0) +
                      (visibleColumns.mit ? 1 : 0)}
                    {#if perSetColSpan > 0}
                      <th class="set-group" colspan={perSetColSpan} title={ctx.label}>{ctx.label}</th>
                    {/if}
                  {/each}
                </tr>
                <tr>
                  {#each setContexts as ctx (ctx.key + ':sub')}
                    {#if visibleColumns.takenMin}<th class="num sub" title="Damage taken at the lowest roll (50% of base damage)">Min</th>{/if}
                    {#if visibleColumns.takenExp}<th class="num sub" title="Expected damage taken (integrated over the 50%–100% damage roll range)">Exp</th>{/if}
                    {#if visibleColumns.takenMax}<th class="num sub" title="Damage taken at the highest roll (100% of base damage)">Max</th>{/if}
                    {#if visibleColumns.crit}<th class="num sub" title="Max crit damage taken">Crit</th>{/if}
                    {#if visibleColumns.decay}<th class="num sub" title="Armor/plate decay per attack (PEC)">Decay</th>{/if}
                    {#if visibleColumns.mit}<th class="num sub">Mit</th>{/if}
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each tableRows as row, r (r)}
                  <tr>
                    {#if visibleColumns.maturity}
                      <td class="sticky-mat">
                        <span class="cell-main">{row.maturityName}</span>
                        {#if row.maturityLevel != null}<span class="cell-sub">L{row.maturityLevel}</span>{/if}
                      </td>
                    {/if}
                    {#if visibleColumns.dmg}
                      <td class="num dmg-col" class:muted={row.totalDamage == null}>
                        {row.totalDamage != null ? fmt(row.totalDamage, 0) : '—'}
                      </td>
                    {/if}
                    {#each row.perSet as s, si (si)}
                      {#if visibleColumns.takenMin}
                        <td class="num" class:muted={!s.hasData}>{s.hasData ? fmt(s.takenMin) : '—'}</td>
                      {/if}
                      {#if visibleColumns.takenExp}
                        <td class="num" class:muted={!s.hasData}>{s.hasData ? fmt(s.takenExp) : '—'}</td>
                      {/if}
                      {#if visibleColumns.takenMax}
                        <td class="num" class:muted={!s.hasData}>{s.hasData ? fmt(s.takenMax) : '—'}</td>
                      {/if}
                      {#if visibleColumns.crit}
                        <td class="num crit-cell" class:muted={!s.hasData}>{s.hasData ? fmt(s.crit) : '—'}</td>
                      {/if}
                      {#if visibleColumns.decay}
                        <td class="num decay-cell" class:muted={!s.hasData}>{s.hasData ? fmt(s.decay, 3) : '—'}</td>
                      {/if}
                      {#if visibleColumns.mit}
                        <td class="num mit-cell" class:muted={!s.hasData}>{s.hasData ? fmtPct(s.mit * 100) : '—'}</td>
                      {/if}
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </section>
    </div>

    <footer class="dialog-footer">
      <p class="hint">Per-set columns repeat for each selected set. Toggle column visibility to slim down the table.</p>
      <button class="btn" onclick={onclose}>Close</button>
    </footer>
  </div>
</div>

<style>
  .cmp-dialog-backdrop {
    position: fixed;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    z-index: 200;
  }

  .cmp-dialog {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 100%;
    max-width: 1200px;
    height: min(88vh, 820px);
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
    background-color: var(--primary-color);
    border-radius: 8px 8px 0 0;
  }
  .dialog-header h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
  }

  .close-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 22px;
    line-height: 1;
    padding: 2px 8px;
    cursor: pointer;
    border-radius: 4px;
  }
  .close-btn:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .dialog-toolbar {
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-color);
    background-color: color-mix(in srgb, var(--primary-color) 40%, transparent);
  }

  .attack-picker,
  .col-toggles {
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 4px 8px 4px 6px;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    background-color: var(--primary-color);
  }
  .attack-picker legend,
  .col-toggles legend {
    float: none;
    font-size: 10px;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.4px;
    padding: 0 6px 0 2px;
    width: auto;
  }

  .attack-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    font-size: 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    cursor: pointer;
    white-space: nowrap;
  }
  .attack-chip:hover { background-color: var(--hover-color); }
  .attack-chip.active {
    background-color: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
  }
  .attack-chip input { display: none; }

  .col-toggles label {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--text-color);
    cursor: pointer;
    white-space: nowrap;
  }
  .col-toggles input { margin: 0; }

  .export-wrap {
    position: relative;
    margin-left: auto;
  }
  .export-btn {
    padding: 6px 12px;
    font-size: 12px;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
    cursor: pointer;
  }
  .export-btn:hover:not(:disabled) { background-color: var(--hover-color); }
  .export-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .export-menu {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    min-width: 140px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    padding: 4px;
    z-index: 10;
    display: flex;
    flex-direction: column;
  }
  .export-menu button {
    text-align: left;
    padding: 6px 10px;
    font-size: 12px;
    background: transparent;
    border: none;
    color: var(--text-color);
    cursor: pointer;
    border-radius: 4px;
  }
  .export-menu button:hover { background-color: var(--hover-color); }

  .dialog-body {
    display: grid;
    grid-template-columns: 260px 1fr;
    gap: 12px;
    padding: 12px 14px;
    overflow: hidden;
    min-height: 0;
    flex: 1;
  }

  .pick-column {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-height: 0;
  }
  .pick-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .count { font-size: 11px; color: var(--text-muted); }
  .pick-actions { display: flex; gap: 6px; }
  .link-btn {
    background: transparent;
    border: none;
    color: var(--accent-color);
    font-size: 11px;
    padding: 2px 4px;
    cursor: pointer;
  }
  .link-btn:hover { text-decoration: underline; }

  .pick-list {
    flex: 1 1 0;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--primary-color);
    min-height: 0;
  }

  .pick-item {
    display: grid;
    grid-template-columns: auto auto 1fr;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    font-size: 12px;
    cursor: pointer;
    border-bottom: 1px solid color-mix(in srgb, var(--border-color) 40%, transparent);
  }
  .pick-item:last-child { border-bottom: none; }
  .pick-item:hover { background-color: var(--hover-color); }
  .pick-item input { margin: 0; }
  .pick-item.checked { background-color: color-mix(in srgb, var(--accent-color) 12%, transparent); }

  .pick-rank {
    font-size: 10px;
    color: var(--text-muted);
    min-width: 24px;
  }
  .pick-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }
  .pick-plate { color: var(--text-muted); font-size: 11px; }

  .table-pane {
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
  }

  .empty-pane {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1;
    color: var(--text-muted);
    font-size: 13px;
    border: 1px dashed var(--border-color);
    border-radius: 6px;
  }

  .table-scroll {
    flex: 1 1 0;
    overflow: auto;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--primary-color);
    min-height: 0;
  }

  .cmp-table {
    width: auto;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 12px;
  }
  .cmp-table th,
  .cmp-table td {
    padding: 6px 10px;
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
  }
  .cmp-table thead th {
    background-color: var(--primary-color);
    color: var(--text-muted);
    font-weight: 500;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    line-height: 1.1;
    vertical-align: middle;
  }
  .cmp-table thead tr:first-child th.set-group {
    border-left: 1px solid var(--border-color);
    text-align: center;
    color: var(--text-color);
    background-color: color-mix(in srgb, var(--accent-color) 14%, var(--primary-color));
  }
  .cmp-table thead tr:nth-child(2) th {
    border-bottom: 1px solid var(--border-color);
  }
  .cmp-table thead th.sub { font-size: 10px; }
  .cmp-table thead th[title] {
    text-decoration: underline dotted var(--text-muted);
    text-underline-offset: 3px;
    cursor: help;
  }
  .cmp-table tbody tr:nth-child(even) td {
    background-color: color-mix(in srgb, var(--primary-color) 40%, var(--secondary-color));
  }
  .cmp-table tbody tr:hover td { background-color: var(--hover-color); }

  .cmp-table .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .cmp-table .muted { color: var(--text-muted); }
  .cmp-table .crit-cell { color: var(--damage-cut, #e06060); font-weight: 600; }
  .cmp-table .decay-cell { color: var(--warning-color, #fbbf24); }
  .cmp-table .mit-cell { color: var(--accent-color); font-weight: 600; }

  .cmp-table .cell-main { display: inline; }
  .cmp-table .cell-sub { margin-left: 6px; font-size: 10px; color: var(--text-muted); }

  /* Sticky Maturity column — Dmg flows naturally to avoid overlap with
     the first per-set column group. */
  .cmp-table .sticky-mat {
    position: sticky;
    left: 0;
    min-width: 110px;
    background-color: var(--secondary-color);
    z-index: 3;
    box-shadow: 1px 0 0 0 var(--border-color);
  }
  .cmp-table thead .sticky-mat { z-index: 4; background-color: var(--primary-color); }
  .cmp-table .dmg-col { min-width: 56px; }

  .dialog-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 16px;
    border-top: 1px solid var(--border-color);
    background-color: var(--primary-color);
    border-radius: 0 0 8px 8px;
    gap: 12px;
    flex-wrap: wrap;
  }
  .hint { margin: 0; font-size: 11px; color: var(--text-muted); flex: 1; min-width: 200px; }
  .btn {
    padding: 6px 12px;
    font-size: 12px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
    cursor: pointer;
  }
  .btn:hover { background-color: var(--hover-color); }

  @media (max-width: 860px) {
    .dialog-body {
      grid-template-columns: 1fr;
      grid-template-rows: 160px 1fr;
    }
    .cmp-dialog { height: 92vh; }
  }
</style>
