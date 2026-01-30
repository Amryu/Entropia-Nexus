<!--
  @component WikiNavigation
  Sidebar navigation with search, filters, and virtualized item list.
  Supports expanded table view mode with sortable/filterable columns.
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher, onMount } from 'svelte';
  import { encodeURIComponentSafe } from '$lib/util';

  const dispatch = createEventDispatcher();

  /** @type {Array} Items to display in the list */
  export let items = [];

  /** @type {Array} Filter options [{key, label, values: [{value, label}]}] */
  export let filters = [];

  /** @type {string} Base path for links */
  export let basePath = '';

  /** @type {string} Navigation title */
  export let title = '';

  /** @type {string|null} Currently selected item slug */
  export let currentSlug = null;

  /** @type {boolean} Whether sidebar is in expanded table view mode */
  export let expanded = false;

  /**
   * @type {Array|null} Custom table columns for expanded view
   * Default: [{ key: 'class', header: 'Class', width: '70px' }, { key: 'maxLvl', header: 'Lvl', width: '40px' }, ...]
   * Each column: { key: string, header: string, width: string, getValue?: (item) => any, format?: (value, item) => string }
   */
  export let tableColumns = null;

  /**
   * @type {Object|null} Custom column formatters keyed by column key
   * Example: { dps: (item) => calcDps(item)?.toFixed(1) || '-' }
   */
  export let columnFormatters = null;

  /**
   * @type {Function|null} Custom function to generate item href
   * Example: (item, basePath) => `${basePath}/${item._type}/${item.Name}`
   * If null, defaults to `${basePath}/${item.Name}`
   */
  export let customGetItemHref = null;

  // Search and filter state
  let searchQuery = '';
  let activeFilters = {};
  let columnFilters = { name: '', class: '', maxLvl: '', dps: '', dpp: '' };
  let sortColumn = null;
  let sortDirection = 'asc';
  let showFilterHelp = false;

  // Virtualization state
  let listContainer;
  let scrollTop = 0;
  let containerHeight = 400;
  const ITEM_HEIGHT = 36;
  const BUFFER_SIZE = 5;

  // Initialize active filters
  $: {
    for (const filter of filters) {
      if (activeFilters[filter.key] === undefined) {
        activeFilters[filter.key] = null;
      }
    }
  }

  // Smart filter function (supports >, <, >=, <=, !, =)
  function smartFilter(value, filterStr) {
    if (!filterStr || !filterStr.trim()) return true;
    const filter = filterStr.trim().toLowerCase();
    const strValue = String(value ?? '').toLowerCase();
    const numValue = parseFloat(value);

    if (filter.startsWith('>=')) {
      const target = parseFloat(filter.slice(2));
      return !isNaN(numValue) && !isNaN(target) && numValue >= target;
    }
    if (filter.startsWith('<=')) {
      const target = parseFloat(filter.slice(2));
      return !isNaN(numValue) && !isNaN(target) && numValue <= target;
    }
    if (filter.startsWith('>')) {
      const target = parseFloat(filter.slice(1));
      return !isNaN(numValue) && !isNaN(target) && numValue > target;
    }
    if (filter.startsWith('<')) {
      const target = parseFloat(filter.slice(1));
      return !isNaN(numValue) && !isNaN(target) && numValue < target;
    }
    if (filter.startsWith('!')) {
      return !strValue.includes(filter.slice(1));
    }
    if (filter.startsWith('=')) {
      return strValue === filter.slice(1);
    }
    return strValue.includes(filter);
  }

  // Calculate effective damage for an item
  function calcEffectiveDamage(item) {
    if (!item?.Properties?.Damage) return null;
    const d = item.Properties.Damage;
    const totalDamage = (d.Impact || 0) + (d.Cut || 0) + (d.Stab || 0) + (d.Penetration || 0) +
                        (d.Shrapnel || 0) + (d.Burn || 0) + (d.Cold || 0) + (d.Acid || 0) + (d.Electric || 0);
    // Effective damage multiplier: average hit rate * normal damage + crit rate * crit damage
    const multiplier = 0.88 * 0.75 + 0.02 * 1.75;
    return totalDamage * multiplier;
  }

  // Calculate DPS for an item
  function calcDps(item) {
    if (!item?.Properties?.UsesPerMinute) return null;
    const effectiveDamage = calcEffectiveDamage(item);
    if (effectiveDamage === null) return null;
    const reload = 60 / item.Properties.UsesPerMinute;
    return effectiveDamage / reload;
  }

  // Calculate cost per use for an item
  function calcCostPerUse(item) {
    const decay = item?.Properties?.Economy?.Decay;
    const ammoBurn = item?.Properties?.Economy?.AmmoBurn ?? 0;
    if (decay === null || decay === undefined) return null;
    return decay + (ammoBurn / 100);
  }

  // Calculate DPP for an item (damage per PEC)
  function calcDpp(item) {
    const effectiveDamage = calcEffectiveDamage(item);
    const costPerUse = calcCostPerUse(item);
    if (effectiveDamage === null || costPerUse === null || costPerUse === 0) return null;
    return effectiveDamage / costPerUse;
  }

  // Get max profession level from skill intervals
  function getMaxLvl(item) {
    const skill = item?.Properties?.Skill;
    if (!skill) return null;
    // Return the highest end level from hit or dmg professions
    const hitMax = skill.Hit?.LearningIntervalEnd;
    const dmgMax = skill.Dmg?.LearningIntervalEnd;
    if (hitMax !== null && hitMax !== undefined && dmgMax !== null && dmgMax !== undefined) {
      return Math.max(hitMax, dmgMax);
    }
    return hitMax ?? dmgMax ?? null;
  }

  // Fuzzy search scoring function - greedy matching
  function fuzzyScore(name, query) {
    if (!name || !query) return 0;
    const nameLower = name.toLowerCase();
    const queryLower = query.toLowerCase();

    // Exact match
    if (nameLower === queryLower) return 1000;

    // Starts with query (high score)
    if (nameLower.startsWith(queryLower)) return 900;

    // Word starts with query (e.g., "Calypso Sword" matches "sword")
    const words = nameLower.split(/\s+/);
    for (let i = 0; i < words.length; i++) {
      if (words[i].startsWith(queryLower)) {
        return 800 - i * 5; // Less penalty for later words
      }
    }

    // Contains exact substring - minimal penalty for position
    const index = nameLower.indexOf(queryLower);
    if (index !== -1) {
      // High base score, small penalty for position
      return 700 - Math.min(index, 50);
    }

    // Fuzzy match: check if all characters appear in sequence
    let queryIdx = 0;
    let score = 0;
    let consecutiveBonus = 0;
    let matchPositions = [];

    for (let i = 0; i < nameLower.length && queryIdx < queryLower.length; i++) {
      if (nameLower[i] === queryLower[queryIdx]) {
        matchPositions.push(i);
        queryIdx++;
        consecutiveBonus += 10;
        score += consecutiveBonus;
        // Big bonus for matching at word boundaries
        if (i === 0 || nameLower[i - 1] === ' ' || nameLower[i - 1] === '-' || nameLower[i - 1] === '_') {
          score += 30;
        }
      } else {
        consecutiveBonus = 0;
      }
    }

    // If all query chars found in sequence, return fuzzy score
    if (queryIdx === queryLower.length) {
      // Bonus for compact matches (characters close together)
      const spread = matchPositions.length > 1
        ? matchPositions[matchPositions.length - 1] - matchPositions[0]
        : 0;
      const compactBonus = Math.max(0, 50 - spread);
      return 300 + score + compactBonus;
    }

    // Partial match: at least 60% of query characters found in sequence
    const matchRatio = queryIdx / queryLower.length;
    if (matchRatio >= 0.6 && queryLower.length >= 3) {
      return 100 + Math.floor(score * matchRatio);
    }

    // No match
    return 0;
  }

  // Filtered and sorted items
  $: filteredItems = (() => {
    if (!items) return [];
    let result = items;

    // Apply main search filter with fuzzy matching
    if (searchQuery && searchQuery.trim().length > 0) {
      const query = searchQuery.trim();
      // Score all items and filter those with score > 0
      result = result
        .map(item => ({
          item,
          score: Math.max(
            fuzzyScore(item.Name, query),
            fuzzyScore(item.Properties?.Type, query) * 0.5 // Type matches score lower
          )
        }))
        .filter(({ score }) => score > 0)
        .sort((a, b) => b.score - a.score) // Sort by fuzzy score
        .map(({ item }) => item);
    }

    // Apply category filters (button filters)
    for (const [key, value] of Object.entries(activeFilters)) {
      if (value !== null && value !== '') {
        result = result.filter(item => {
          const parts = key.split('.');
          let itemValue = item;
          for (const part of parts) {
            itemValue = itemValue?.[part];
          }
          return itemValue === value;
        });
      }
    }

    // Apply column filters in expanded mode
    if (expanded) {
      if (columnFilters.name) {
        result = result.filter(item => smartFilter(item.Name, columnFilters.name));
      }
      // Apply filters for each active column
      for (const column of activeColumns) {
        const filterValue = columnFilters[column.key];
        if (filterValue) {
          result = result.filter(item => {
            const value = column.getValue ? column.getValue(item) : item[column.key];
            return smartFilter(value, filterValue);
          });
        }
      }
    }

    // Apply sorting
    if (sortColumn) {
      result = [...result].sort((a, b) => {
        let aVal, bVal;

        if (sortColumn === 'name') {
          aVal = a.Name || '';
          bVal = b.Name || '';
        } else {
          // Find the column definition
          const column = activeColumns.find(c => c.key === sortColumn);
          if (column && column.getValue) {
            aVal = column.getValue(a);
            bVal = column.getValue(b);
          } else {
            aVal = a[sortColumn];
            bVal = b[sortColumn];
          }
        }

        if (aVal == null && bVal == null) return 0;
        if (aVal == null) return 1;
        if (bVal == null) return -1;

        let cmp;
        if (typeof aVal === 'number' && typeof bVal === 'number') {
          cmp = aVal - bVal;
        } else {
          cmp = String(aVal).localeCompare(String(bVal), undefined, { numeric: true });
        }
        return sortDirection === 'asc' ? cmp : -cmp;
      });
    }

    return result;
  })();

  // Virtualization calculations
  $: totalHeight = filteredItems.length * ITEM_HEIGHT;
  $: startIndex = Math.max(0, Math.floor(scrollTop / ITEM_HEIGHT) - BUFFER_SIZE);
  $: endIndex = Math.min(filteredItems.length, Math.ceil((scrollTop + containerHeight) / ITEM_HEIGHT) + BUFFER_SIZE);
  $: visibleItems = filteredItems.slice(startIndex, endIndex);
  $: offsetY = startIndex * ITEM_HEIGHT;

  function handleItemClick(item) {
    dispatch('select', { item });
  }

  function setFilter(key, value) {
    activeFilters[key] = value === activeFilters[key] ? null : value;
    activeFilters = activeFilters;
  }

  function clearFilters() {
    searchQuery = '';
    for (const key of Object.keys(activeFilters)) {
      activeFilters[key] = null;
    }
    activeFilters = activeFilters;
    columnFilters = { name: '', class: '', maxLvl: '', dps: '', dpp: '' };
  }

  function getItemHref(item) {
    if (customGetItemHref) {
      return customGetItemHref(item, basePath);
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  function handleScroll(event) {
    scrollTop = event.target.scrollTop;
  }

  function handleSort(column) {
    if (sortColumn === column) {
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      sortColumn = column;
      sortDirection = 'asc';
    }
  }

  function toggleFilterHelp() {
    showFilterHelp = !showFilterHelp;
  }

  onMount(() => {
    if (listContainer) {
      containerHeight = listContainer.clientHeight;
      const resizeObserver = new ResizeObserver(entries => {
        for (const entry of entries) {
          containerHeight = entry.contentRect.height;
        }
      });
      resizeObserver.observe(listContainer);
      return () => resizeObserver.disconnect();
    }
  });

  function formatDps(item) {
    const dps = calcDps(item);
    return dps ? dps.toFixed(1) : '-';
  }

  function formatDpp(item) {
    const dpp = calcDpp(item);
    return dpp ? dpp.toFixed(2) : '-';
  }

  function formatMaxLvl(item) {
    const lvl = getMaxLvl(item);
    return lvl !== null ? lvl : '-';
  }

  // Default columns for weapons (used when no custom columns provided)
  const defaultTableColumns = [
    { key: 'class', header: 'Class', width: '70px', getValue: (item) => item.Properties?.Class || '-' },
    { key: 'maxLvl', header: 'Lvl', width: '40px', getValue: getMaxLvl, format: (v) => v !== null ? v : '-' },
    { key: 'dps', header: 'DPS', width: '55px', getValue: calcDps, format: (v) => v ? v.toFixed(1) : '-' },
    { key: 'dpp', header: 'DPP', width: '55px', getValue: calcDpp, format: (v) => v ? v.toFixed(2) : '-' }
  ];

  // Actual columns to use (custom or default)
  $: activeColumns = tableColumns || defaultTableColumns;

  // Generate grid template from active columns
  $: gridTemplateColumns = `1fr ${activeColumns.map(c => c.width).join(' ')}`;

  // Format a cell value for display
  function formatCell(item, column) {
    // If custom formatter provided via columnFormatters prop
    if (columnFormatters && columnFormatters[column.key]) {
      return columnFormatters[column.key](item);
    }
    // If column has getValue, use it
    const value = column.getValue ? column.getValue(item) : item[column.key];
    // If column has format, apply it
    if (column.format) {
      return column.format(value, item);
    }
    return value ?? '-';
  }

  function handleToggleExpand() {
    dispatch('toggleExpand');
  }

  // Scrollbar width measurement
  let scrollbarWidth = 0;

  // Calculated column widths based on initial data
  let calculatedColumnWidths = {};
  let widthsCalculated = false;

  // Measure text width using canvas
  function measureTextWidth(text, font = '12px system-ui, -apple-system, sans-serif') {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    ctx.font = font;
    return ctx.measureText(String(text)).width;
  }

  // Calculate column widths based on initial data
  function calculateColumnWidths() {
    if (widthsCalculated || !items || items.length === 0) return;

    const headerFont = '11px system-ui, -apple-system, sans-serif';
    const cellFont = '12px system-ui, -apple-system, sans-serif';
    const padding = 16; // Extra padding for cell content
    const minWidth = 40; // Minimum column width
    const maxWidth = 120; // Maximum column width

    for (const column of activeColumns) {
      // Start with header width
      let maxTextWidth = measureTextWidth(column.header, headerFont);

      // Measure all values in the column
      for (const item of items) {
        const value = formatCell(item, column);
        const textWidth = measureTextWidth(value, cellFont);
        if (textWidth > maxTextWidth) {
          maxTextWidth = textWidth;
        }
      }

      // Clamp width between min and max, add padding
      const finalWidth = Math.max(minWidth, Math.min(maxWidth, Math.ceil(maxTextWidth + padding)));
      calculatedColumnWidths[column.key] = `${finalWidth}px`;
    }

    widthsCalculated = true;
  }

  // Get the width to use for a column (calculated or fallback to defined)
  function getColumnWidth(column) {
    if (calculatedColumnWidths[column.key]) {
      return calculatedColumnWidths[column.key];
    }
    return column.width || '60px';
  }

  // Generate grid template from active columns with calculated widths
  $: dynamicGridTemplateColumns = widthsCalculated
    ? `1fr ${activeColumns.map(c => getColumnWidth(c)).join(' ')}`
    : gridTemplateColumns;

  onMount(() => {
    // Measure scrollbar width
    const outer = document.createElement('div');
    outer.style.visibility = 'hidden';
    outer.style.overflow = 'scroll';
    outer.style.width = '100px';
    outer.style.position = 'absolute';
    document.body.appendChild(outer);
    const inner = document.createElement('div');
    inner.style.width = '100%';
    outer.appendChild(inner);
    scrollbarWidth = outer.offsetWidth - inner.offsetWidth;
    document.body.removeChild(outer);

    // Calculate column widths based on initial data
    calculateColumnWidths();
  });
</script>

<nav class="wiki-nav" class:expanded>
  <div class="nav-header">
    <h2 class="nav-title">{title}</h2>
    <button
      class="expand-btn"
      on:click={handleToggleExpand}
      title={expanded ? 'Collapse sidebar' : 'Expand to table view'}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        {#if expanded}
          <path d="M11 19l-7-7 7-7M18 19l-7-7 7-7" />
        {:else}
          <path d="M13 5l7 7-7 7M6 5l7 7-7 7" />
        {/if}
      </svg>
    </button>
  </div>

  <div class="search-box">
    <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" />
    </svg>
    <input
      type="text"
      class="search-input"
      placeholder="Search..."
      bind:value={searchQuery}
    />
    {#if searchQuery}
      <button class="clear-search" on:click={() => searchQuery = ''} aria-label="Clear search">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    {/if}
  </div>

  {#if filters.length > 0}
    <div class="filter-section">
      <!-- Check if filters are link-based (type navigation) or value-based (category filters) -->
      {#if filters[0]?.href !== undefined}
        <!-- Link-based type navigation buttons (e.g., tools: Rf, Scn, Fnd, etc.) -->
        <div class="type-nav-buttons">
          {#each filters as btn}
            <a
              href={btn.href}
              class="type-nav-btn"
              class:active={btn.active}
              title={btn.title}
            >
              {btn.label}
            </a>
          {/each}
        </div>
      {:else}
        <!-- Value-based category filters -->
        {#each filters as filter}
          <div class="filter-group">
            <span class="filter-label">{filter.label}</span>
            <div class="filter-options">
              {#each filter.values as option}
                <button
                  class="filter-btn"
                  class:active={activeFilters[filter.key] === option.value}
                  on:click={() => setFilter(filter.key, option.value)}
                >
                  {option.label}
                </button>
              {/each}
            </div>
          </div>
        {/each}

        {#if Object.values(activeFilters).some(v => v !== null)}
          <button class="clear-filters" on:click={clearFilters}>
            Clear filters
          </button>
        {/if}
      {/if}
    </div>
  {/if}

  <!-- Table header for expanded view -->
  {#if expanded}
    <div class="table-header-bar">
      <div class="table-header" style="grid-template-columns: {dynamicGridTemplateColumns} auto;">
        <button class="th sortable" class:sorted={sortColumn === 'name'} on:click={() => handleSort('name')}>
          Name {sortColumn === 'name' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
        </button>
        {#each activeColumns as column}
          <button class="th sortable" class:sorted={sortColumn === column.key} on:click={() => handleSort(column.key)}>
            {column.header} {sortColumn === column.key ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
          </button>
        {/each}
        <button class="th help-gutter" on:click={toggleFilterHelp} title="Filter help" style="width: {scrollbarWidth}px; min-width: {scrollbarWidth}px;">?</button>
      </div>
    </div>

    {#if showFilterHelp}
      <div class="filter-help">
        <div class="help-title">Smart Filter Syntax</div>
        <div class="help-item"><code>&gt;50</code> Greater than 50</div>
        <div class="help-item"><code>&lt;100</code> Less than 100</div>
        <div class="help-item"><code>&gt;=10</code> Greater or equal</div>
        <div class="help-item"><code>&lt;=20</code> Less or equal</div>
        <div class="help-item"><code>!melee</code> Does not contain</div>
        <div class="help-item"><code>=ranged</code> Exact match</div>
        <div class="help-item"><code>sword</code> Contains text</div>
      </div>
    {/if}

    <div class="table-filters" style="grid-template-columns: {dynamicGridTemplateColumns} auto;">
      <input type="text" class="col-filter" placeholder="Filter..." bind:value={columnFilters.name} />
      {#each activeColumns as column}
        <input type="text" class="col-filter" placeholder={column.filterPlaceholder || 'Filter...'} bind:value={columnFilters[column.key]} />
      {/each}
      <div class="col-filter-spacer" style="width: {scrollbarWidth}px; min-width: {scrollbarWidth}px;"></div>
    </div>
  {/if}

  <div
    class="item-list"
    bind:this={listContainer}
    on:scroll={handleScroll}
  >
    {#if filteredItems.length === 0}
      <div class="no-results">
        <p>No items found</p>
        {#if searchQuery || Object.values(activeFilters).some(v => v !== null) || Object.values(columnFilters).some(v => v)}
          <button class="clear-filters" on:click={clearFilters}>
            Clear filters
          </button>
        {/if}
      </div>
    {:else}
      <div class="virtual-list" style="height: {totalHeight}px;">
        <div class="virtual-items" style="transform: translateY({offsetY}px);">
          {#each visibleItems as item (item.Name)}
            <a
              href={getItemHref(item)}
              class="item-link"
              class:active={item.Name === currentSlug}
              class:table-row={expanded}
              on:click={() => handleItemClick(item)}
              title={item.Name}
              style={expanded ? `grid-template-columns: ${dynamicGridTemplateColumns};` : ''}
            >
              {#if expanded}
                <span class="cell cell-name" title={item.Name}>{item.Name}</span>
                {#each activeColumns as column}
                  <span class="cell cell-{column.key}">{formatCell(item, column)}</span>
                {/each}
              {:else}
                <span class="item-name" title={item.Name}>{item.Name}</span>
              {/if}
            </a>
          {/each}
        </div>
      </div>
    {/if}
  </div>

  <div class="nav-footer">
    <span class="item-count">{filteredItems.length} items</span>
  </div>
</nav>

<style>
  .wiki-nav {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    position: relative;
  }

  .nav-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    flex-shrink: 0;
    border-bottom: 1px solid var(--border-color, #555);
    background-color: var(--secondary-color);
  }

  .nav-title {
    font-size: 15px;
    font-weight: 600;
    margin: 0;
    color: var(--text-color);
  }

  .expand-btn {
    padding: 5px;
    background: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .expand-btn:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .search-box {
    position: relative;
    margin: 12px 12px 10px 12px;
    flex-shrink: 0;
  }

  .search-icon {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted, #999);
    pointer-events: none;
  }

  .search-input {
    width: 100%;
    padding: 8px 30px 8px 34px;
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    font-size: 13px;
    box-sizing: border-box;
  }

  .search-input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .search-input::placeholder {
    color: var(--text-muted, #999);
  }

  .clear-search {
    position: absolute;
    right: 6px;
    top: 50%;
    transform: translateY(-50%);
    padding: 4px;
    background: transparent;
    border: none;
    color: var(--text-muted, #999);
    cursor: pointer;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .clear-search:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .filter-section {
    margin: 0 12px 10px 12px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border-color, #555);
    flex-shrink: 0;
  }

  .filter-group {
    margin-bottom: 6px;
  }

  .filter-label {
    display: block;
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted, #999);
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .filter-options {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .filter-btn {
    padding: 3px 7px;
    font-size: 11px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .filter-btn:hover {
    background-color: var(--hover-color);
  }

  .filter-btn.active {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .clear-filters {
    display: block;
    width: 100%;
    padding: 5px;
    margin-top: 6px;
    font-size: 11px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    color: var(--text-muted, #999);
    border-radius: 4px;
    cursor: pointer;
  }

  .clear-filters:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  /* Type navigation buttons (link-based) */
  .type-nav-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .type-nav-btn {
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
    border-radius: 4px;
    text-decoration: none;
    transition: all 0.15s;
  }

  .type-nav-btn:hover {
    background-color: var(--hover-color);
  }

  .type-nav-btn.active {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  /* Table header bar with help button */
  .table-header-bar {
    display: none;
  }

  .wiki-nav.expanded .table-header-bar {
    display: block;
    padding: 0 12px;
    margin-bottom: 2px;
    flex-shrink: 0;
  }

  .table-header {
    display: grid;
    gap: 2px;
  }

  /* Help button in header gutter */
  .th.help-gutter {
    flex-shrink: 0;
    padding: 4px;
    font-size: 11px;
    font-weight: 600;
    background-color: var(--secondary-color);
    border: none;
    color: var(--text-muted, #999);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .th.help-gutter:hover {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .col-filter-spacer {
    flex-shrink: 0;
  }

  .filter-help {
    margin: 0 12px 8px 12px;
    padding: 10px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    font-size: 11px;
    flex-shrink: 0;
  }

  .help-title {
    font-weight: 600;
    color: var(--text-color);
    margin-bottom: 6px;
  }

  .help-item {
    display: flex;
    gap: 8px;
    color: var(--text-muted, #999);
    margin-bottom: 3px;
  }

  .help-item code {
    background-color: var(--secondary-color);
    padding: 1px 4px;
    border-radius: 3px;
    font-family: monospace;
    color: var(--accent-color, #4a9eff);
    min-width: 50px;
  }

  .th {
    padding: 6px 4px;
    background-color: var(--hover-color);
    border: none;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    cursor: pointer;
    text-align: left;
    border-radius: 3px;
  }

  .th.sortable:hover {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .th.sorted {
    color: var(--accent-color, #4a9eff);
  }

  .table-filters {
    display: none;
  }

  .wiki-nav.expanded .table-filters {
    display: grid;
    gap: 2px;
    padding: 0 12px;
    margin-bottom: 6px;
    flex-shrink: 0;
  }

  .col-filter {
    padding: 4px 6px;
    font-size: 11px;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    box-sizing: border-box;
    width: 100%;
  }

  .col-filter:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .col-filter::placeholder {
    color: var(--text-muted, #999);
    font-size: 10px;
  }

  .item-list {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
    margin: 0 12px 12px;
  }

  .virtual-list {
    position: relative;
  }

  .virtual-items {
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
  }

  .item-link {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 36px;
    padding: 0 8px;
    color: var(--text-color);
    text-decoration: none;
    border-radius: 4px;
    box-sizing: border-box;
  }

  .item-link:hover {
    background-color: var(--hover-color);
  }

  .item-link.active {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .item-name {
    font-size: 13px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
  }

  /* Table view styles */
  .item-link.table-row {
    display: grid;
    gap: 2px;
    padding: 0 4px;
  }

  .cell {
    font-size: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    padding: 0 2px;
    text-align: right;
    font-variant-numeric: tabular-nums;
    color: var(--text-muted, #999);
  }

  .cell-name {
    text-align: left;
    color: var(--text-color);
  }

  .item-link.table-row.active .cell {
    color: rgba(255, 255, 255, 0.7);
  }

  .item-link.table-row.active .cell-name {
    color: white;
  }

  .nav-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    border-top: 1px solid var(--border-color, #555);
    flex-shrink: 0;
  }

  .item-count {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .no-results {
    text-align: center;
    padding: 20px;
    color: var(--text-muted, #999);
  }

  .no-results p {
    margin: 0 0 10px 0;
    font-size: 13px;
  }

  /* Mobile adjustments */
  @media (max-width: 767px) {
    .nav-header {
      padding: 10px 10px 6px 10px;
    }

    .search-box {
      margin: 10px 10px 8px 10px;
    }

    .filter-section {
      margin: 0 10px 8px 10px;
    }

    .item-list {
      margin: 0 10px;
    }

    .nav-footer {
      padding: 6px 10px;
    }
  }
</style>
