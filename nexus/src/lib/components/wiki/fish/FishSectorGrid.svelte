<!--
  @component FishSectorGrid
  Clickable sector grid for marking fish locations on planet maps.
  Each server tile (8x8km) is subdivided into a 4x4 sub-grid (2x2km cells).
-->
<script>
  // @ts-nocheck
  const SUB_DIVISIONS = 4;
  const RARITIES = ['Common', 'Uncommon', 'Rare', 'Very Rare', 'Extremely Rare'];
  const RARITY_COLORS = {
    'Common':         'rgba(34, 197, 94, 0.45)',
    'Uncommon':       'rgba(59, 130, 246, 0.45)',
    'Rare':           'rgba(234, 179, 8, 0.5)',
    'Very Rare':      'rgba(239, 68, 68, 0.5)',
    'Extremely Rare': 'rgba(168, 85, 247, 0.55)'
  };
  const RARITY_BORDER = {
    'Common':         '#22c55e',
    'Uncommon':       '#3b82f6',
    'Rare':           '#eab308',
    'Very Rare':      '#ef4444',
    'Extremely Rare': '#a855f7'
  };

  let {
    locations = [],
    planets = [],
    isEditMode = false,
    planetsList = null,
    onchange
  } = $props();

  let activeTabIndex = $state(0);
  let selectedCol = $state(null);
  let selectedRow = $state(null);

  function colLabel(c) {
    if (c < 26) return String.fromCharCode(65 + c);
    return String.fromCharCode(65 + Math.floor(c / 26) - 1) + String.fromCharCode(65 + (c % 26));
  }
  function rowLabel(r) { return String(r + 1); }
  function sectorNotation(c, r) { return colLabel(c) + rowLabel(r); }

  let relevantPlanets = $derived.by(() => {
    const names = (planets || []).map(p => p?.Name).filter(Boolean);
    return names.map(name => {
      const loc = (locations || []).find(l => l.PlanetName === name);
      const full = (planetsList || []).find(p => p?.Name === name);
      const fromPlanets = (planets || []).find(p => p?.Name === name);
      const w = loc?.Width ?? full?.Properties?.Map?.Width ?? fromPlanets?.Width ?? 1;
      const h = loc?.Height ?? full?.Properties?.Map?.Height ?? fromPlanets?.Height ?? 1;
      return {
        name,
        width: w * SUB_DIVISIONS,
        height: h * SUB_DIVISIONS,
        tileWidth: w,
        tileHeight: h,
        sectors: loc?.Sectors || []
      };
    });
  });

  let activePlanet = $derived(relevantPlanets[Math.min(activeTabIndex, relevantPlanets.length - 1)] ?? null);

  function findSector(sectors, col, row) {
    return sectors?.find(s => s.Col === col && s.Row === row) ?? null;
  }

  let selectedSector = $derived.by(() => {
    if (selectedCol == null || selectedRow == null || !activePlanet) return null;
    return findSector(activePlanet.sectors, selectedCol, selectedRow);
  });

  function emitChange(planetName, newSectors) {
    let newLocations = (locations || []).map(l =>
      l.PlanetName === planetName ? { ...l, Sectors: newSectors } : { ...l }
    );
    if (!newLocations.find(l => l.PlanetName === planetName)) {
      const planet = relevantPlanets.find(p => p.name === planetName);
      newLocations.push({
        PlanetName: planetName,
        Width: planet?.tileWidth ?? 1,
        Height: planet?.tileHeight ?? 1,
        Sectors: newSectors
      });
    }
    newLocations = newLocations.filter(l => l.Sectors.length > 0);
    onchange?.(newLocations);
  }

  function handleCellClick(col, row) {
    if (!isEditMode) return;
    if (!activePlanet) return;

    const existing = findSector(activePlanet.sectors, col, row);
    if (existing) {
      if (selectedCol === col && selectedRow === row) {
        const newSectors = activePlanet.sectors.filter(s => !(s.Col === col && s.Row === row));
        selectedCol = null;
        selectedRow = null;
        emitChange(activePlanet.name, newSectors);
      } else {
        selectedCol = col;
        selectedRow = row;
      }
    } else {
      const newSectors = [...activePlanet.sectors, { Col: col, Row: row, Rarity: 'Common', Note: null }];
      selectedCol = col;
      selectedRow = row;
      emitChange(activePlanet.name, newSectors);
    }
  }

  function updateSelectedRarity(rarity) {
    if (!activePlanet || selectedCol == null) return;
    const newSectors = activePlanet.sectors.map(s =>
      (s.Col === selectedCol && s.Row === selectedRow) ? { ...s, Rarity: rarity } : s
    );
    emitChange(activePlanet.name, newSectors);
  }

  function updateSelectedNote(note) {
    if (!activePlanet || selectedCol == null) return;
    const newSectors = activePlanet.sectors.map(s =>
      (s.Col === selectedCol && s.Row === selectedRow) ? { ...s, Note: note || null } : s
    );
    emitChange(activePlanet.name, newSectors);
  }

  function removeSelected() {
    if (!activePlanet || selectedCol == null) return;
    const newSectors = activePlanet.sectors.filter(s => !(s.Col === selectedCol && s.Row === selectedRow));
    selectedCol = null;
    selectedRow = null;
    emitChange(activePlanet.name, newSectors);
  }
</script>

{#if relevantPlanets.length === 0}
  <p class="muted">Add planets to this fish to set sector locations.</p>
{:else}
  {#if relevantPlanets.length > 1}
    <div class="planet-tabs">
      {#each relevantPlanets as planet, i}
        <button
          class="planet-tab"
          class:active={activeTabIndex === i}
          onclick={() => { activeTabIndex = i; selectedCol = null; selectedRow = null; }}
        >
          {planet.name}
          {#if planet.sectors.length > 0}
            <span class="sector-count">{planet.sectors.length}</span>
          {/if}
        </button>
      {/each}
    </div>
  {:else}
    <div class="planet-single">{relevantPlanets[0].name}</div>
  {/if}

  {#if activePlanet}
    <div class="grid-container" style="max-width: {Math.min(activePlanet.width * 20 + 28, 800)}px;">
      <div class="sector-grid"
        style="grid-template-columns: 24px repeat({activePlanet.width}, 1fr); grid-template-rows: 20px repeat({activePlanet.height}, 1fr);"
      >
        <div class="grid-corner"></div>
        {#each Array(activePlanet.width) as _, col}
          <div class="col-label" class:tile-boundary={col % SUB_DIVISIONS === 0}>{col % SUB_DIVISIONS === 0 ? colLabel(col) : ''}</div>
        {/each}

        {#each Array(activePlanet.height) as _, ri}
          {@const row = activePlanet.height - 1 - ri}
          <div class="row-label" class:tile-boundary={row % SUB_DIVISIONS === 0}>{row % SUB_DIVISIONS === 0 ? rowLabel(row) : ''}</div>
          {#each Array(activePlanet.width) as _, col}
            {@const sector = findSector(activePlanet.sectors, col, row)}
            {@const isSelected = isEditMode && selectedCol === col && selectedRow === row}
            <button
              class="sector-cell"
              class:active={!!sector}
              class:selected={isSelected}
              class:border-right={col % SUB_DIVISIONS === SUB_DIVISIONS - 1}
              class:border-bottom={row % SUB_DIVISIONS === 0}
              class:border-left={col % SUB_DIVISIONS === 0}
              class:border-top={row % SUB_DIVISIONS === SUB_DIVISIONS - 1}
              style={sector ? `background-color: ${RARITY_COLORS[sector.Rarity]};` : ''}
              title={sector ? `${sectorNotation(col, row)}: ${sector.Rarity}${sector.Note ? ' - ' + sector.Note : ''}` : sectorNotation(col, row)}
              onclick={() => handleCellClick(col, row)}
              disabled={!isEditMode && !sector}
            ></button>
          {/each}
        {/each}
      </div>
    </div>

    <!-- Rarity legend -->
    <div class="legend">
      {#each RARITIES as r}
        <div class="legend-item">
          <span class="legend-swatch" style="background-color: {RARITY_COLORS[r]}; border-color: {RARITY_BORDER[r]};"></span>
          <span>{r}</span>
        </div>
      {/each}
    </div>

    <!-- Edit panel for selected sector -->
    {#if isEditMode && selectedSector}
      <div class="sector-detail">
        <div class="detail-header">
          <strong>{sectorNotation(selectedCol, selectedRow)}</strong>
          <button type="button" class="remove-btn" onclick={removeSelected}>Remove</button>
        </div>
        <div class="detail-row">
          <label>Rarity</label>
          <select value={selectedSector.Rarity} onchange={(e) => updateSelectedRarity(e.currentTarget.value)}>
            {#each RARITIES as r}
              <option value={r}>{r}</option>
            {/each}
          </select>
        </div>
        <div class="detail-row">
          <label>Note</label>
          <input type="text" value={selectedSector.Note || ''} placeholder="Optional note..."
            onchange={(e) => updateSelectedNote(e.currentTarget.value)} />
        </div>
      </div>
    {/if}
  {/if}
{/if}

<style>
  .muted {
    color: var(--text-muted, #999);
    font-style: italic;
    margin: 0;
  }

  .planet-tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }

  .planet-tab {
    padding: 6px 14px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    color: var(--text-color);
    transition: all 0.15s;
  }

  .planet-tab.active {
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-color: var(--accent-color, #4a9eff);
  }

  .planet-tab:hover:not(.active) {
    background-color: var(--hover-color);
  }

  .sector-count {
    font-size: 11px;
    margin-left: 4px;
    opacity: 0.7;
  }

  .planet-single {
    font-weight: 600;
    font-size: 13px;
    margin-bottom: 8px;
    color: var(--text-muted, #999);
  }

  .grid-container {
    overflow-x: auto;
    margin-bottom: 10px;
  }

  .sector-grid {
    display: grid;
    gap: 0;
    width: fit-content;
  }

  .grid-corner {
    /* empty top-left cell */
  }

  .col-label, .row-label {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 9px;
    font-weight: 600;
    color: var(--text-muted, #999);
    user-select: none;
  }

  .col-label {
    padding-bottom: 2px;
  }

  .row-label {
    padding-right: 2px;
    min-width: 24px;
  }

  .sector-cell {
    aspect-ratio: 1;
    min-width: 10px;
    min-height: 10px;
    border: 1px solid var(--border-color-subtle, rgba(128, 128, 128, 0.15));
    background: transparent;
    cursor: default;
    padding: 0;
    transition: background-color 0.1s;
  }

  .sector-cell.border-right { border-right: 2px solid var(--border-color, #555); }
  .sector-cell.border-bottom { border-bottom: 2px solid var(--border-color, #555); }
  .sector-cell.border-left { border-left: 2px solid var(--border-color, #555); }
  .sector-cell.border-top { border-top: 2px solid var(--border-color, #555); }

  .sector-cell.active {
    cursor: pointer;
  }

  .sector-cell.selected {
    box-shadow: inset 0 0 0 2px var(--accent-color, #4a9eff);
  }

  .sector-cell:not(:disabled):hover {
    background-color: var(--hover-color, rgba(128, 128, 128, 0.12));
    cursor: pointer;
  }

  .sector-cell:disabled {
    cursor: default;
  }

  .legend {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 10px;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    color: var(--text-muted, #999);
  }

  .legend-swatch {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid;
  }

  .sector-detail {
    background-color: var(--secondary-color, var(--bg-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: 360px;
  }

  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 14px;
  }

  .detail-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .detail-row label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted, #999);
    min-width: 50px;
  }

  .detail-row select,
  .detail-row input {
    flex: 1;
    padding: 4px 8px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    font-size: 13px;
  }

  .detail-row select:focus,
  .detail-row input:focus {
    border-color: var(--accent-color, #4a9eff);
    outline: none;
  }

  .remove-btn {
    padding: 3px 10px;
    font-size: 11px;
    background: transparent;
    color: var(--error-color, #ef4444);
    border: 1px solid var(--error-color, #ef4444);
    border-radius: 4px;
    cursor: pointer;
  }

  .remove-btn:hover {
    background-color: rgba(239, 68, 68, 0.15);
  }
</style>
