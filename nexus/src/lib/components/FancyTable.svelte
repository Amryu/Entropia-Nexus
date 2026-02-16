<script>
  // @ts-nocheck
  import { createEventDispatcher, onMount, onDestroy, tick } from 'svelte';

  /**
   * FancyTable - A modern table component with virtualization and lazy loading
   *
   * Props:
   * - columns: Array of column definitions
   *   { key: string, header: string, sortable?: boolean, searchable?: boolean, width?: string,
   *     widthBasis?: 'content' | 'header' | 'both', formatter?: (value, row) => string,
   *     cellClass?: (value, row) => string, hideOnMobile?: boolean, mobileWidth?: string,
   *     main?: boolean, rawValue?: boolean, sortValue?: (row) => any, sortFn?: (a, b) => number,
   *     sortPhases?: Array<{ sortValue: (row) => any, order: 'ASC'|'DESC', color?: string }> }
   *   - main: If true, column grows to fill available space using minmax(width, 1fr)
   *   - rawValue: If true, renders value as text instead of HTML (allows reactive content)
   * - data: Array of row objects (for non-lazy mode)
   * - fetchData: async (offset, limit, sortBy, sortOrder, filters) => { rows, total } (for lazy loading)
   * - rowHeight: Height of each row in pixels (default: 44)
   * - pageSize: Number of rows to fetch at a time (default: 50)
   * - sortable: Enable sorting (default: true)
   * - searchable: Enable search inputs (default: true)
   * - stickyHeader: Keep header visible when scrolling (default: true)
   * - emptyMessage: Message to show when no data (default: 'No data available')
   * - loading: External loading state
   * - defaultWidthBasis: 'content' | 'header' | 'both' (default: 'both')
   * - horizontalScroll: Enable horizontal scrolling (default: true)
   *
   * Events:
   * - rowClick: { row, index }
   * - rowHover: { row, index } | null
   * - sort: { column, order }
   */

  export let columns = [];
  export let data = [];
  export let fetchData = null; // async (offset, limit, sortBy, sortOrder, filters) => { rows, total }
  export let rowHeight = 44;
  export let pageSize = 50;
  export let sortable = true;
  export let searchable = true;
  export let stickyHeader = true;
  export let emptyMessage = 'No data available';
  export let loading = false;
  export let defaultWidthBasis = 'both';
  export let horizontalScroll = true;
  export let compact = false;

  /** @type {{ column: string, order: 'ASC'|'DESC' }|null} Initial sort to apply */
  export let defaultSort = null;

  /**
   * @type {(row: object) => string|null} Function to generate extra CSS classes for rows
   * Example: (row) => row.boss ? 'boss-row' : null
   */
  export let rowClass = null;

  /**
   * @type {Array|null} Footer rows for displaying aggregates
   * Each row: Array of cell values matching columns, or object with key->value
   * Example: [{ label: 'Total', tt: '10.00', mu: '115%', total: '11.50' }]
   */
  export let footer = null;

  /**
   * @type {string|null} Footer label column key (which column contains the row label)
   * If set, that column spans any unlabeled columns before it
   */
  export let footerLabelKey = null;

  const dispatch = createEventDispatcher();

  // Internal state
  let containerEl;
  let scrollEl;
  let headerEl;
  let footerEl;
  let internalData = [];
  let totalRows = 0;
  let sortColumn = defaultSort?.column ?? null;
  let sortOrder = defaultSort?.order ?? 'ASC';
  let sortPhaseIdx = 0;
  let userSorted = false;

  // React to external defaultSort changes (e.g. viewport switch) unless user manually sorted
  $: if (!userSorted && defaultSort && (defaultSort.column !== sortColumn || defaultSort.order !== sortOrder)) {
    sortColumn = defaultSort.column ?? null;
    sortOrder = defaultSort.order ?? 'ASC';
    sortPhaseIdx = 0;
  }
  let filters = {};
  let filterTimeouts = {};
  let isLoading = false;
  let loadedRanges = new Set(); // Track which page ranges have been loaded
  let visibleStart = 0;
  let visibleEnd = 0;
  let containerHeight = 0;
  let scrollbarWidth = 0;
  let resizeObserver;

  // Track mobile state (must be before computed values that depend on it)
  let isMobile = false;

  function updateMobileState() {
    isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;
  }

  // Computed
  $: isLazyMode = typeof fetchData === 'function';
  $: displayData = isLazyMode ? internalData : filteredSortedData;
  $: totalCount = isLazyMode ? totalRows : filteredSortedData.length;
  // Use smaller row height on mobile
  $: effectiveRowHeight = isMobile ? Math.min(rowHeight, 32) : rowHeight;
  $: totalHeight = totalCount * effectiveRowHeight;
  $: headerHeight = (searchable ? 2 : 1) * effectiveRowHeight;
  $: contentHeight = containerHeight > 0
    ? Math.max(effectiveRowHeight, Math.floor(containerHeight / effectiveRowHeight) * effectiveRowHeight)
    : 0;
  $: visibleCapacity = contentHeight > 0 ? Math.floor(contentHeight / effectiveRowHeight) : 0;
  $: fillRowCount = totalCount > 0 ? Math.max(0, visibleCapacity - totalCount) : 0;
  $: virtualContainerHeight = Math.max(totalHeight, contentHeight || 0);

  // Filter and sort data in non-lazy mode
  $: filteredSortedData = (() => {
    if (isLazyMode) return [];

    let result = [...data];

    // Apply filters
    for (const [key, value] of Object.entries(filters)) {
      if (value && value.trim()) {
        const filterValue = value.toLowerCase().trim();
        result = result.filter(row => {
          const cellValue = String(row[key] ?? '').toLowerCase();

          // Support filter operators
          if (filterValue.startsWith('!')) {
            return !cellValue.includes(filterValue.slice(1));
          }
          if (filterValue.startsWith('>=')) {
            return parseFloat(cellValue) >= parseFloat(filterValue.slice(2));
          }
          if (filterValue.startsWith('<=')) {
            return parseFloat(cellValue) <= parseFloat(filterValue.slice(2));
          }
          if (filterValue.startsWith('>')) {
            return parseFloat(cellValue) > parseFloat(filterValue.slice(1));
          }
          if (filterValue.startsWith('<')) {
            return parseFloat(cellValue) < parseFloat(filterValue.slice(1));
          }
          if (filterValue.startsWith('=')) {
            return cellValue === filterValue.slice(1);
          }
          return cellValue.includes(filterValue);
        });
      }
    }

    // Apply sorting
    if (sortColumn) {
      const columnDef = columns.find(col => col.key === sortColumn);
      const phaseSortValue = columnDef?.sortPhases?.[sortPhaseIdx]?.sortValue;
      result.sort((a, b) => {
        if (columnDef?.sortFn) {
          const cmp = columnDef.sortFn(a, b);
          return sortOrder === 'ASC' ? cmp : -cmp;
        }

        const aVal = phaseSortValue ? phaseSortValue(a) : (columnDef?.sortValue ? columnDef.sortValue(a) : a[sortColumn]);
        const bVal = phaseSortValue ? phaseSortValue(b) : (columnDef?.sortValue ? columnDef.sortValue(b) : b[sortColumn]);

        // Handle nulls
        if (aVal == null && bVal == null) return 0;
        if (aVal == null) return 1;
        if (bVal == null) return -1;

        // Numeric comparison
        if (typeof aVal === 'number' && typeof bVal === 'number') {
          return sortOrder === 'ASC' ? aVal - bVal : bVal - aVal;
        }

        // String comparison
        const comparison = String(aVal).localeCompare(String(bVal), undefined, { numeric: true });
        return sortOrder === 'ASC' ? comparison : -comparison;
      });
    }

    return result;
  })();

  // Initialize
  onMount(() => {
    // Initialize mobile state first
    updateMobileState();
    window.addEventListener('resize', updateMobileState);

    if (isLazyMode) {
      loadInitialData();
    }

    if (scrollEl) {
      updateVisibleRange();
      updateScrollbarWidth();
      if (typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver(() => {
          updateVisibleRange();
          updateScrollbarWidth();
        });
        resizeObserver.observe(scrollEl);
      }
    }
  });

  onDestroy(() => {
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
    if (scrollRafId) {
      cancelAnimationFrame(scrollRafId);
      scrollRafId = null;
    }
    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', updateMobileState);
    }
    Object.values(filterTimeouts).forEach(clearTimeout);
  });

  // When display data changes (data, filters, sort, columns), recalculate visible range after DOM update
  $: if (displayData && !isLazyMode) {
    tick().then(() => {
      if (scrollEl) updateVisibleRange();
    });
  }

  async function loadInitialData() {
    if (!isLazyMode) return;

    isLoading = true;
    try {
      const result = await fetchData(0, pageSize, sortColumn, sortOrder, filters);
      internalData = result.rows || [];
      totalRows = result.total || internalData.length;
      loadedRanges.clear();
      loadedRanges.add(0);
    } catch (err) {
      console.error('FancyTable: Failed to load initial data', err);
    } finally {
      isLoading = false;
    }
  }

  async function loadMore(pageIndex) {
    if (!isLazyMode || loadedRanges.has(pageIndex) || isLoading) return;

    isLoading = true;
    loadedRanges.add(pageIndex);

    try {
      const offset = pageIndex * pageSize;
      const result = await fetchData(offset, pageSize, sortColumn, sortOrder, filters);
      const newRows = result.rows || [];

      // Merge new rows into internal data at correct positions
      for (let i = 0; i < newRows.length; i++) {
        internalData[offset + i] = newRows[i];
      }
      internalData = internalData; // Trigger reactivity

      if (result.total != null) {
        totalRows = result.total;
      }
    } catch (err) {
      console.error('FancyTable: Failed to load more data', err);
      loadedRanges.delete(pageIndex);
    } finally {
      isLoading = false;
    }
  }

  let scrollRafId = null;

  function handleScroll() {
    if (scrollRafId) return;
    scrollRafId = requestAnimationFrame(() => {
      scrollRafId = null;
      updateVisibleRange();
      syncHorizontalScroll();

      if (isLazyMode) {
        // Check if we need to load more data
        const startPage = Math.floor(visibleStart / pageSize);
        const endPage = Math.floor(visibleEnd / pageSize);

        for (let p = startPage; p <= endPage; p++) {
          if (!loadedRanges.has(p)) {
            loadMore(p);
          }
        }
      }
    });
  }

  function syncHorizontalScroll() {
    if (!horizontalScroll || !scrollEl) return;
    const scrollLeft = scrollEl.scrollLeft;
    if (headerEl) headerEl.scrollLeft = scrollLeft;
    if (footerEl) footerEl.scrollLeft = scrollLeft;
  }

  function updateVisibleRange() {
    if (!scrollEl) return;

    const scrollTop = scrollEl.scrollTop;
    containerHeight = scrollEl.clientHeight;

    // Calculate visible row range with generous buffer for smooth scrolling
    const buffer = Math.max(10, Math.ceil(containerHeight / effectiveRowHeight));
    visibleStart = Math.max(0, Math.floor(scrollTop / effectiveRowHeight) - buffer);
    visibleEnd = Math.min(totalCount, Math.ceil((scrollTop + containerHeight) / effectiveRowHeight) + buffer);

    updateScrollbarWidth();
  }

  function updateScrollbarWidth() {
    if (!scrollEl || !containerEl) return;
    const width = scrollEl.offsetWidth - scrollEl.clientWidth;
    if (width !== scrollbarWidth) {
      scrollbarWidth = width;
      containerEl.style.setProperty('--scrollbar-width', `${width}px`);
    }
  }

  function handleSort(column) {
    if (!sortable || column.sortable === false) return;
    userSorted = true;

    if (column.sortPhases?.length) {
      // Cycle through sort phases (e.g. sell DESC → sell ASC → buy DESC → buy ASC)
      if (sortColumn === column.key) {
        sortPhaseIdx = (sortPhaseIdx + 1) % column.sortPhases.length;
      } else {
        sortPhaseIdx = 0;
      }
      sortColumn = column.key;
      sortOrder = column.sortPhases[sortPhaseIdx].order;
    } else {
      if (sortColumn === column.key) {
        sortOrder = sortOrder === 'ASC' ? 'DESC' : 'ASC';
      } else {
        sortColumn = column.key;
        sortOrder = 'ASC';
      }
      sortPhaseIdx = 0;
    }

    dispatch('sort', { column: sortColumn, order: sortOrder });

    if (isLazyMode) {
      // Reset and reload with new sort
      internalData = [];
      loadedRanges.clear();
      loadInitialData();
    }
  }

  function handleFilterInput(columnKey, value) {
    // Debounce filter input
    if (filterTimeouts[columnKey]) {
      clearTimeout(filterTimeouts[columnKey]);
    }

    filterTimeouts[columnKey] = setTimeout(() => {
      filters[columnKey] = value;
      filters = filters; // Trigger reactivity

      if (isLazyMode) {
        // Reset and reload with new filters
        internalData = [];
        loadedRanges.clear();
        loadInitialData();
      }
    }, 300);
  }

  function handleRowClick(row, index) {
    dispatch('rowClick', { row, index });
  }

  function handleRowHover(row, index) {
    dispatch('rowHover', row ? { row, index } : null);
  }

  function getCellValue(row, column) {
    const value = row[column.key];
    if (column.formatter) {
      return column.formatter(value, row);
    }
    return value ?? '';
  }

  function stripHtml(value) {
    return String(value ?? '')
      .replace(/<[^>]*>/g, '')
      .replace(/&nbsp;/g, ' ');
  }

  function getCellText(row, column) {
    if (!row) return '';
    if (column.component) return String(row[column.key] ?? '');
    return stripHtml(getCellValue(row, column));
  }

  function getCellClass(row, column) {
    if (column.cellClass) {
      return column.cellClass(row[column.key], row);
    }
    return '';
  }

  // Visible rows for virtual rendering
  $: visibleRows = (() => {
    const count = displayData.length;
    if (count === 0) return [];
    let start = Math.min(visibleStart, count);
    let end = Math.min(visibleEnd, count);
    // If visible range is empty/invalid but we have data, show initial rows
    // (happens when data arrives before updateVisibleRange runs)
    if (end <= start) {
      start = 0;
      end = Math.min(count, 50);
    }
    return displayData.slice(start, end).map((row, i) => ({
      row,
      index: start + i,
      top: (start + i) * effectiveRowHeight
    }));
  })();

  // Calculate auto widths for columns without explicit width
  // Sample up to 200 rows instead of iterating all data for performance
  $: columnAutoWidths = columns.reduce((acc, column) => {
    if (column.width) return acc;

    const basis = column.widthBasis || defaultWidthBasis;
    const headerText = stripHtml(column.header ?? '');
    const headerLength = headerText.length;
    let contentLength = 0;

    if (basis !== 'header') {
      const sampleSize = Math.min(displayData.length, 200);
      for (let i = 0; i < sampleSize; i++) {
        const row = displayData[i];
        if (!row) continue;
        const cellText = getCellText(row, column);
        if (cellText) {
          contentLength = Math.max(contentLength, cellText.length);
        }
      }
    }

    const length = basis === 'header'
      ? headerLength
      : basis === 'both'
      ? Math.max(headerLength, contentLength)
      : contentLength;
    // Use smaller minimum and padding on mobile
    const minLength = isMobile ? 2 : 4;
    const padding = isMobile ? 20 : 32; // 10px each side mobile, 16px each side desktop
    const safeLength = Math.max(minLength, length);
    acc[column.key] = `calc(${safeLength}ch + ${padding}px)`;
    return acc;
  }, {});

  // Compute grid-template-columns from column widths
  // - main columns use minmax() to allow growing with available space
  // - use mobileWidth on mobile for responsive layouts
  $: gridTemplateColumns = columns
    .filter(col => (!isMobile || !col.hideOnMobile) && (isMobile || !col.hideOnDesktop))
    .map(col => {
      const width = (isMobile && col.mobileWidth)
        ? col.mobileWidth
        : (col.width || columnAutoWidths[col.key] || '1fr');
      // Main columns should grow to fill available space
      if (col.main) {
        // Explicit width → use as minimum; auto-computed → use 0 so table can shrink in narrow containers
        const hasExplicitWidth = col.width || (isMobile && col.mobileWidth);
        if (!hasExplicitWidth || width.includes('fr')) {
          return 'minmax(0, 1fr)';
        }
        return `minmax(${width}, 1fr)`;
      }
      return width;
    })
    .join(' ');
</script>

<style>
  .fancy-table-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    width: 100%;
    max-width: 100%;
    min-width: 0; /* Allow flex item to shrink below content size */
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    box-sizing: border-box;
    font-size: 14px;
  }

  .table-header {
    flex-shrink: 0;
    min-width: 0; /* Allow flex item to shrink below content size */
    background-color: var(--hover-color);
    border-bottom: 1px solid var(--border-color);
  }

  .table-header.sticky {
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .header-row, .filter-row {
    display: grid;
    align-items: stretch;
    padding-right: var(--scrollbar-width, 0px);
    box-sizing: border-box;
  }

  .horizontal-scroll .header-row,
  .horizontal-scroll .filter-row {
    display: inline-grid;
    min-width: 100%;
  }

  .header-cell {
    padding: 12px 16px;
    font-weight: 600;
    color: var(--text-color);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    gap: 4px;
    border-right: 1px solid var(--border-color);
    box-sizing: border-box;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .header-cell:last-child {
    border-right: none;
  }

  .header-cell.sortable {
    cursor: pointer;
    transition: background-color 0.15s ease;
    user-select: none;
  }

  .header-cell.sortable:hover {
    background-color: rgba(59, 130, 246, 0.2);
  }

  .header-cell.sorted {
    background-color: rgba(59, 130, 246, 0.15);
    color: var(--accent-color);
  }

  .sort-indicator {
    font-size: 10px;
    margin-left: 4px;
  }

  .filter-row {
    background-color: var(--secondary-color);
    border-bottom: 1px solid var(--border-color);
  }

  .filter-cell {
    padding: 8px;
    border-right: 1px solid var(--border-color);
    box-sizing: border-box;
  }

  .filter-cell:last-child {
    border-right: none;
  }

  .filter-input {
    width: 100%;
    padding: 6px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--bg-color);
    color: var(--text-color);
    font-size: 12px;
    box-sizing: border-box;
  }

  .filter-input::placeholder {
    opacity: 0.5;
  }

  .filter-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .table-body {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    position: relative;
    min-width: 0; /* Allow flex item to shrink below content size */
  }

  .table-body.horizontal-scroll {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  /* Ensure header has same scrollbar space as body */
  .table-header {
    overflow-y: hidden;
    overflow-x: hidden;
  }

  .table-header.horizontal-scroll {
    overflow-x: auto;
    scrollbar-width: none; /* Firefox */
    -ms-overflow-style: none; /* IE/Edge */
  }

  .table-header.horizontal-scroll::-webkit-scrollbar {
    display: none; /* Chrome/Safari/Opera */
  }

  /* Hide scrollbar in header (we just want the space reserved) */
  .table-header::-webkit-scrollbar {
    background: transparent;
  }

  .table-header::-webkit-scrollbar-thumb {
    background: transparent;
  }

  /* Firefox */
  .table-header {
    scrollbar-color: transparent transparent;
  }

  .virtual-container {
    position: relative;
    width: 100%;
    contain: layout style;
  }

  .horizontal-scroll .virtual-container {
    display: inline-block;
    min-width: 100%;
  }

  .table-row {
    display: grid;
    align-items: stretch;
    position: absolute;
    left: 0;
    right: 0;
    cursor: pointer;
    border-bottom: 1px solid var(--border-color);
    box-sizing: border-box;
    contain: layout style;
  }

  .horizontal-scroll .table-row {
    right: auto;
    min-width: 100%;
  }

  .table-row:hover {
    background-color: rgba(59, 130, 246, 0.1);
  }

  .table-row.even {
    background-color: var(--secondary-color);
  }

  .table-row.odd {
    background-color: color-mix(in srgb, var(--primary-color) 30%, var(--secondary-color) 70%);
  }

  .table-row:hover {
    background-color: rgba(59, 130, 246, 0.15);
  }

  .table-row.last-row {
    border-bottom: none;
  }

  .table-row.empty {
    pointer-events: none;
  }

  .table-row.empty:hover {
    background-color: inherit;
  }

  .table-cell {
    padding: 12px 16px;
    color: var(--text-color);
    display: flex;
    align-items: center;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    border-right: 1px solid var(--border-color);
    box-sizing: border-box;
    min-width: 0;
  }

  .table-cell:last-child {
    border-right: none;
  }

  .loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 5;
  }

  .loading-spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    color: var(--text-muted);
  }

  .empty-icon {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.5;
  }

  .empty-text {
    font-size: 14px;
  }

  .table-footer {
    flex-shrink: 0;
    min-width: 0; /* Allow flex item to shrink below content size */
    background-color: var(--hover-color);
    border-top: 2px solid var(--border-color);
    overflow-y: hidden;
    overflow-x: hidden;
  }

  .table-footer.horizontal-scroll {
    overflow-x: auto;
    scrollbar-width: none; /* Firefox */
    -ms-overflow-style: none; /* IE/Edge */
  }

  .table-footer.horizontal-scroll::-webkit-scrollbar {
    display: none; /* Chrome/Safari/Opera */
  }

  /* Hide scrollbar in footer (we just want the space reserved) */
  .table-footer::-webkit-scrollbar {
    background: transparent;
  }

  .table-footer::-webkit-scrollbar-thumb {
    background: transparent;
  }

  /* Firefox */
  .table-footer {
    scrollbar-color: transparent transparent;
  }

  .footer-row {
    display: grid;
    align-items: stretch;
    border-bottom: 1px solid var(--border-color);
    padding-right: var(--scrollbar-width, 0px);
    box-sizing: border-box;
  }

  .horizontal-scroll .footer-row {
    display: inline-grid;
    min-width: 100%;
  }

  .footer-row:last-child {
    border-bottom: none;
  }

  .footer-cell {
    padding: 10px 16px;
    font-weight: 600;
    color: var(--text-color);
    display: flex;
    align-items: center;
    border-right: 1px solid var(--border-color);
    box-sizing: border-box;
  }

  .footer-cell:last-child {
    border-right: none;
  }

  .footer-cell.label-cell {
    color: var(--text-muted);
    font-weight: 500;
  }

  .results-info {
    padding: 8px 16px;
    font-size: 12px;
    color: var(--text-muted);
    background-color: var(--hover-color);
    border-top: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  /* Status badge styles (commonly used) */
  :global(.fancy-table-container .status-badge) {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
  }

  :global(.fancy-table-container .status-badge.success) {
    background-color: rgba(16, 185, 129, 0.2);
    color: var(--success-color);
  }

  :global(.fancy-table-container .status-badge.warning) {
    background-color: rgba(245, 158, 11, 0.2);
    color: var(--warning-color);
  }

  :global(.fancy-table-container .status-badge.error) {
    background-color: rgba(239, 68, 68, 0.2);
    color: var(--error-color);
  }

  :global(.fancy-table-container .status-badge.info) {
    background-color: rgba(59, 130, 246, 0.2);
    color: var(--accent-color);
  }

  :global(.fancy-table-container .status-badge.muted) {
    background-color: var(--hover-color);
    color: var(--text-muted);
  }

  /* Compact mode */
  .fancy-table-container.compact {
    font-size: 13px;
  }

  .compact .header-cell {
    padding: 6px 10px;
    font-size: 11px;
  }

  .compact .filter-cell {
    padding: 4px 6px;
  }

  .compact .filter-input {
    padding: 4px 6px;
    font-size: 11px;
  }

  .compact .table-cell {
    padding: 4px 10px;
  }

  .compact .footer-cell {
    padding: 6px 10px;
  }

  .compact .empty-state {
    padding: 24px 16px;
  }

  /* Desktop: hide mobile-only columns */
  @media (min-width: 769px) {
    .hide-on-desktop {
      display: none !important;
    }
  }

  /* Mobile styles */
  @media (max-width: 768px) {
    .fancy-table-container {
      font-size: 12px;
      border-radius: 6px;
    }

    .table-header {
      border-bottom-width: 1px;
    }

    .header-cell {
      padding: 6px 10px;
      font-size: 10px;
      letter-spacing: 0.3px;
    }

    .filter-cell {
      padding: 4px 6px;
    }

    .filter-input {
      padding: 3px 6px;
      font-size: 11px;
      border-radius: 3px;
    }

    .table-cell {
      padding: 6px 10px;
      font-size: 12px;
      /* Keep flex for vertical centering, allow text wrapping */
      display: flex;
      align-items: center;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      min-height: 0;
    }

    .footer-cell {
      padding: 6px 10px;
    }

    .results-info {
      padding: 6px 10px;
      font-size: 11px;
    }

    .empty-state {
      padding: 24px 12px;
    }

    .empty-icon {
      font-size: 32px;
      margin-bottom: 8px;
    }

    .empty-text {
      font-size: 12px;
    }

    .hide-on-mobile {
      display: none !important;
    }

    /* Disable horizontal scroll on mobile — columns are already sized to fit */
    .table-body.horizontal-scroll {
      overflow-x: hidden;
    }
    .horizontal-scroll .virtual-container {
      display: block;
      min-width: auto;
    }
    .horizontal-scroll .table-row {
      right: 0;
      min-width: auto;
    }
    .horizontal-scroll .header-row,
    .horizontal-scroll .filter-row {
      display: grid;
      min-width: auto;
    }
    .horizontal-scroll .footer-row {
      display: grid;
      min-width: auto;
    }
    .table-header.horizontal-scroll,
    .table-footer.horizontal-scroll {
      overflow-x: hidden;
    }
  }
</style>

<div class="fancy-table-container" class:compact bind:this={containerEl}>
  <!-- Header -->
  <div class="table-header" class:sticky={stickyHeader} class:horizontal-scroll={horizontalScroll} bind:this={headerEl}>
    <div class="header-row" style="grid-template-columns: {gridTemplateColumns};">
      {#each columns as column}
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <div
          class="header-cell"
          class:sortable={sortable && column.sortable !== false}
          class:sorted={sortColumn === column.key}
          class:hide-on-mobile={column.hideOnMobile}
          class:hide-on-desktop={column.hideOnDesktop}
          on:click={() => handleSort(column)}
        >
          {column.header}
          {#if sortColumn === column.key}
            {@const phaseColor = column.sortPhases?.[sortPhaseIdx]?.color}
            <span class="sort-indicator" style={phaseColor ? `color: ${phaseColor}` : ''}>{sortOrder === 'ASC' ? '▲' : '▼'}</span>
          {/if}
        </div>
      {/each}
    </div>

    {#if searchable}
      <div class="filter-row" style="grid-template-columns: {gridTemplateColumns};">
        {#each columns as column}
          <div class="filter-cell" class:hide-on-mobile={column.hideOnMobile}
          class:hide-on-desktop={column.hideOnDesktop}>
            {#if column.searchable !== false}
              <input
                type="text"
                class="filter-input"
                placeholder="Filter..."
                on:input={(e) => handleFilterInput(column.key, e.target.value)}
              />
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Body -->
  <div
    class="table-body"
    class:horizontal-scroll={horizontalScroll}
    bind:this={scrollEl}
    on:scroll={handleScroll}
  >
    {#if (isLoading || loading) && displayData.length === 0}
      <div class="loading-overlay">
        <div class="loading-spinner"></div>
      </div>
    {:else if displayData.length === 0}
      <div class="empty-state">
        <div class="empty-icon">📭</div>
        <div class="empty-text">{emptyMessage}</div>
      </div>
    {:else}
      <div class="virtual-container" style="height: {virtualContainerHeight}px;">
        {#each visibleRows as { row, index, top } (index)}
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <!-- svelte-ignore a11y-mouse-events-have-key-events -->
          <div
            class="table-row {rowClass ? (rowClass(row) || '') : ''}"
            class:even={index % 2 === 0}
            class:odd={index % 2 === 1}
            class:last-row={index === totalCount - 1}
            style="top: {top}px; height: {effectiveRowHeight}px; grid-template-columns: {gridTemplateColumns};"
            on:click={() => handleRowClick(row, index)}
            on:mouseover={() => handleRowHover(row, index)}
            on:mouseout={() => handleRowHover(null, null)}
          >
            {#each columns as column}
              <div class="table-cell {getCellClass(row, column)}" class:hide-on-mobile={column.hideOnMobile}
          class:hide-on-desktop={column.hideOnDesktop}>
                {#if column.component}
                  <svelte:component this={column.component} {row} value={row[column.key]} />
                {:else if column.rawValue}
                  {getCellValue(row, column)}
                {:else}
                  {@html getCellValue(row, column)}
                {/if}
              </div>
            {/each}
          </div>
        {/each}

        {#if fillRowCount > 0}
          {#each Array(fillRowCount) as _, i}
            {@const emptyIndex = totalCount + i}
            <div
              class="table-row empty"
              class:even={emptyIndex % 2 === 0}
              class:odd={emptyIndex % 2 === 1}
              style="top: {emptyIndex * effectiveRowHeight}px; height: {effectiveRowHeight}px; grid-template-columns: {gridTemplateColumns};"
            >
              {#each columns as column}
                <div class="table-cell" class:hide-on-mobile={column.hideOnMobile}
          class:hide-on-desktop={column.hideOnDesktop}></div>
              {/each}
            </div>
          {/each}
        {/if}
      </div>

      {#if isLoading && displayData.length > 0}
        <div class="loading-overlay" style="background: transparent;">
          <div class="loading-spinner"></div>
        </div>
      {/if}
    {/if}
  </div>

  <!-- Custom Footer Rows -->
  {#if footer && footer.length > 0 && displayData.length > 0}
    <div class="table-footer" class:horizontal-scroll={horizontalScroll} bind:this={footerEl}>
      {#each footer as footerRow}
        <div class="footer-row" style="grid-template-columns: {gridTemplateColumns};">
          {#each columns as column, colIndex}
            {@const value = footerRow[column.key]}
            {@const isLabelCell = column.key === footerLabelKey}
            <div
              class="footer-cell"
              class:label-cell={isLabelCell}
              class:hide-on-mobile={column.hideOnMobile}
          class:hide-on-desktop={column.hideOnDesktop}
            >
              {#if value !== undefined}
                {value}
              {/if}
            </div>
          {/each}
        </div>
      {/each}
    </div>
  {/if}

  <!-- Footer with count -->
  {#if totalCount > 0}
    <div class="results-info">
      {#if isLazyMode}
        Showing {Math.min(visibleEnd, totalCount)} of {totalCount} rows
      {:else}
        {totalCount} {totalCount === 1 ? 'row' : 'rows'}
      {/if}
    </div>
  {/if}
</div>
