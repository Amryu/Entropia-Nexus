<!--
  @component WikiNavigation
  Sidebar navigation with search, filters, and virtualized item list.
  Supports expanded table view mode with sortable/filterable columns.
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher, onMount, afterUpdate, tick } from 'svelte';
  import { goto } from '$app/navigation';
  import { browser } from '$app/environment';
  import { encodeURIComponentSafe } from '$lib/util';
  import ColumnConfigDialog from './ColumnConfigDialog.svelte';

  const dispatch = createEventDispatcher();

  /** @type {Array} Items to display in the list */
  export let items = [];

  /** @type {Array} Filter options [{key, label, values: [{value, label}], multiSelect?: boolean, filterFn?: Function}] */
  export let filters = [];

  /** @type {Array} Link-based navigation buttons [{label, href, active, title}] - shown separately from value filters */
  export let linkFilters = [];

  /** @type {string} Base path for links */
  export let basePath = '';

  /** @type {string} Navigation title */
  export let title = '';

  /** @type {string|null} Currently selected item slug */
  export let currentSlug = null;

  /** @type {number|string|null} Currently selected item ID (for disambiguation when multiple items have same name) */
  export let currentItemId = null;

  /** @type {string|null} Currently selected change ID (for pending creates) */
  export let currentChangeId = null;

  /** @type {boolean} Whether sidebar is in expanded table view mode */
  export let expanded = false;

  /** @type {boolean} Whether sidebar is in full-width mode (takes entire page width, content hidden) */
  export let fullWidth = false;

  /**
   * @type {Array|null} Custom table columns for expanded view
   * Default: [{ key: 'class', header: 'Class', width: '70px' }, { key: 'maxLvl', header: 'Lvl', width: '40px' }, ...]
   * Each column: { key: string, header: string, width: string, getValue?: (item) => any, format?: (value, item) => string }
   */
  export let tableColumns = null;

  /**
   * @type {Array|null} Additional table columns shown only in full-width mode
   * Falls back to tableColumns if not provided
   */
  export let fullWidthColumns = null;

  /**
   * @type {Array|null} All possible columns for this page type (superset for column configuration)
   * When provided, enables column configuration UI (Columns.../Reset buttons)
   */
  export let allAvailableColumns = null;

  /**
   * @type {string} Unique ID for localStorage key (e.g. 'weapons', 'tools-scanners')
   */
  export let pageTypeId = '';

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

  /**
   * @type {Array} User's pending create changes to show at top of list
   * Each item should have: { id, data: { Name, ... }, state: 'Draft'|'Pending' }
   */
  export let userPendingCreates = [];

  /**
   * @type {Array} User's pending update changes to highlight in list
   * Each item should have: { id, data: { Id|ItemId }, state: 'Draft'|'Pending' }
   */
  export let userPendingUpdates = [];

  // Search and filter state
  let searchQuery = '';
  let activeFilters = {};
  let columnFilters = { name: '' };
  let sortColumn = null;
  let sortDirection = 'asc';
  let showFilterHelp = false;
  let openFilterHelp = null; // Track which filter's help popover is open

  // Keyboard navigation state
  let highlightedIndex = -1;
  let hasKeyboardInput = false; // Track if user has interacted with keyboard navigation
  let lastSearchQueryForHighlight = ''; // Track search query to detect actual typing vs re-renders

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
        // Use array for multi-select filters, null for single-select
        activeFilters[filter.key] = filter.multiSelect ? [] : null;
      }
    }
  }

  // Initialize column filter keys from active columns
  $: {
    for (const column of activeColumns) {
      if (columnFilters[column.key] === undefined) {
        columnFilters[column.key] = '';
      }
    }
  }

  // Check if an item is the currently selected item
  // Handles all three matching modes: changeId, itemId, and slug (Name)
  function isCurrentItem(item) {
    if (currentChangeId && item._isPendingCreate && item._changeId === currentChangeId) return true;
    if (currentItemId != null && (item.Id ?? item.ItemId) === currentItemId) return true;
    if (currentSlug && item.Name === currentSlug) return true;
    return false;
  }

  // Helper to find current item index (handles both slugs and changeIds)
  function findCurrentItemIndex(items) {
    return items.findIndex(item => isCurrentItem(item));
  }

  // Reactive current item key - forces template re-render when selection changes
  // This ensures item highlighting updates immediately on navigation
  $: currentItemKey = currentChangeId
    ? `change-${currentChangeId}`
    : (currentItemId != null
      ? `id-${currentItemId}`
      : (currentSlug
        ? `slug-${currentSlug}`
        : null));

  // Get item key for comparison (used for keyboard navigation and other lookups)
  function getItemKey(item) {
    if (item._isPendingCreate) return `change-${item._changeId}`;
    const id = item.Id ?? item.ItemId;
    if (id != null) return `id-${id}`;
    return `slug-${item.Name}`;
  }

  // Optimistic click highlighting - immediately highlights clicked item
  // before navigation data loads and props update
  let clickedItemKey = null;

  function handleItemClick(item) {
    clickedItemKey = getItemKey(item);
  }

  // F5 reload: track whether initial scroll position has been set
  let initialPositionDone = false;

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

  // Search scoring function - prioritizes exact and substring matches
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

    // For short queries (< 4 chars), only match substrings - no fuzzy matching
    // This prevents "fox" from matching "Atrox" via fuzzy
    if (queryLower.length < 4) {
      return 0;
    }

    // Fuzzy match: check if all characters appear in sequence
    // Only enable for longer queries and require compact matches
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

    // If all query chars found in sequence, check if it's a good match
    if (queryIdx === queryLower.length) {
      // Calculate spread (how scattered the match is)
      const spread = matchPositions.length > 1
        ? matchPositions[matchPositions.length - 1] - matchPositions[0]
        : 0;

      // Reject if match is too spread out (more than 2x query length)
      // This prevents "atrox" from matching "Avatar of Greed Guardian" via a/t/r/o/x scattered
      if (spread > queryLower.length * 2) {
        return 0;
      }

      const compactBonus = Math.max(0, 50 - spread);
      return 300 + score + compactBonus;
    }

    // Partial match: at least 95% of query characters found in sequence
    // Only for longer queries (5+ chars)
    const matchRatio = queryIdx / queryLower.length;
    if (matchRatio >= 0.95 && queryLower.length >= 5) {
      // Also check spread for partial matches
      const spread = matchPositions.length > 1
        ? matchPositions[matchPositions.length - 1] - matchPositions[0]
        : 0;
      if (spread <= queryLower.length * 2) {
        return 100 + Math.floor(score * matchRatio);
      }
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
    for (const filter of filters) {
      const value = activeFilters[filter.key];

      // Skip if no filter value
      if (value === null || value === '' || (Array.isArray(value) && value.length === 0)) {
        continue;
      }

      // Use custom filter function if provided
      if (filter.filterFn) {
        result = result.filter(item => filter.filterFn(item, value));
        // Apply custom sort function if provided (sort by match quality)
        if (filter.sortFn) {
          result = [...result].sort((a, b) => filter.sortFn(b, value) - filter.sortFn(a, value));
        }
        continue;
      }

      // Default filtering behavior
      if (Array.isArray(value)) {
        // Multi-select: item must match any of the selected values
        result = result.filter(item => {
          const parts = filter.key.split('.');
          let itemValue = item;
          for (const part of parts) {
            itemValue = itemValue?.[part];
          }
          return value.includes(itemValue);
        });
      } else {
        // Single-select
        result = result.filter(item => {
          const parts = filter.key.split('.');
          let itemValue = item;
          for (const part of parts) {
            itemValue = itemValue?.[part];
          }
          return itemValue === value;
        });
      }
    }

    // Apply column filters in table view mode (expanded or full-width)
    if (showTableView) {
      if (columnFilters.name) {
        result = result.filter(item => smartFilter(item.Name, columnFilters.name));
      }
      // Apply filters for each active column (filter on displayed value so Yes/No etc. work)
      for (const column of activeColumns) {
        const filterValue = columnFilters[column.key];
        if (filterValue) {
          result = result.filter(item => {
            const displayValue = formatCell(item, column);
            return smartFilter(displayValue, filterValue);
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

    const updateMap = {};
    if (userPendingUpdates && userPendingUpdates.length > 0) {
      userPendingUpdates.forEach(change => {
        const changeEntityId = change.data?.Id ?? change.data?.ItemId;
        if (changeEntityId) {
          updateMap[String(changeEntityId)] = {
            _changeId: change.id,
            _changeState: change.state
          };
        }
      });
    }

    const itemsWithUpdates = Object.keys(updateMap).length > 0
      ? result.map(item => {
        const itemEntityId = item?.Id ?? item?.ItemId;
        if (itemEntityId && updateMap[String(itemEntityId)]) {
          return {
            ...item,
            _hasPendingUpdate: true,
            ...updateMap[String(itemEntityId)]
          };
        }
        return item;
      })
      : result;

    // Prepend user's pending creates at the top (with special marker)
    if (userPendingCreates && userPendingCreates.length > 0) {
      const pendingItems = userPendingCreates.map(change => ({
        ...change.data,
        _isPendingCreate: true,
        _changeId: change.id,
        _changeState: change.state,
        // Use temporary name for display if no name set
        Name: change.data?.Name || '[Unnamed]'
      }));
      return [...pendingItems, ...itemsWithUpdates];
    }

    return itemsWithUpdates;
  })();

  // Virtualization calculations
  $: totalHeight = filteredItems.length * ITEM_HEIGHT;
  $: startIndex = Math.max(0, Math.floor(scrollTop / ITEM_HEIGHT) - BUFFER_SIZE);
  $: endIndex = Math.min(filteredItems.length, Math.ceil((scrollTop + containerHeight) / ITEM_HEIGHT) + BUFFER_SIZE);
  $: visibleItems = filteredItems.slice(startIndex, endIndex);
  $: offsetY = startIndex * ITEM_HEIGHT;


  function setFilter(key, value, isMultiSelect = false) {
    if (isMultiSelect) {
      // Toggle value in array for multi-select
      const current = activeFilters[key] || [];
      const idx = current.indexOf(value);
      if (idx === -1) {
        activeFilters[key] = [...current, value];
      } else {
        activeFilters[key] = current.filter(v => v !== value);
      }
    } else {
      // Single-select toggle
      activeFilters[key] = value === activeFilters[key] ? null : value;
    }
    activeFilters = activeFilters;
  }

  function clearFilters() {
    searchQuery = '';
    highlightedIndex = -1;
    hasKeyboardInput = false; // Reset keyboard state when clearing filters
    lastSearchQueryForHighlight = ''; // Reset search tracking
    for (const filter of filters) {
      // Reset to array for multi-select, null for single-select
      activeFilters[filter.key] = filter.multiSelect ? [] : null;
    }
    activeFilters = activeFilters;
    // Reset all column filters
    const resetFilters = { name: '' };
    for (const column of activeColumns) {
      resetFilters[column.key] = '';
    }
    columnFilters = resetFilters;
  }

  function getItemHref(item) {
    // Pending create changes link to the create page with change ID
    if (item._isPendingCreate) {
      return `${basePath}?mode=create&changeId=${item._changeId}`;
    }
    if (customGetItemHref) {
      return customGetItemHref(item, basePath);
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  function handleScroll(event) {
    scrollTop = event.target.scrollTop;
  }

  // Shared keyboard navigation logic for both search input and item list
  function handleKeyboardNavigation(event) {
    if (filteredItems.length === 0) {
      if (event.key === 'Escape') {
        searchQuery = '';
        highlightedIndex = -1;
      }
      return;
    }

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        hasKeyboardInput = true;
        // Start from current item if no highlight yet
        if (highlightedIndex < 0) {
          const currentIndex = findCurrentItemIndex(filteredItems);
          highlightedIndex = currentIndex >= 0 ? currentIndex : 0;
        } else {
          highlightedIndex = Math.min(highlightedIndex + 1, filteredItems.length - 1);
        }
        scrollToHighlighted();
        break;

      case 'ArrowUp':
        event.preventDefault();
        hasKeyboardInput = true;
        // Start from current item if no highlight yet
        if (highlightedIndex < 0) {
          const currentIndex = findCurrentItemIndex(filteredItems);
          highlightedIndex = currentIndex >= 0 ? currentIndex : 0;
        } else {
          highlightedIndex = Math.max(highlightedIndex - 1, 0);
        }
        scrollToHighlighted();
        break;

      case 'Enter':
        event.preventDefault();
        if (highlightedIndex >= 0 && highlightedIndex < filteredItems.length) {
          const item = filteredItems[highlightedIndex];
          // Mark that we want to keep focus on the list after navigation
          shouldFocusListAfterUpdate = true;
          // Navigate to the item using SvelteKit routing (no full page refresh)
          goto(getItemHref(item));
        }
        break;

      case 'Escape':
        event.preventDefault();
        searchQuery = '';
        highlightedIndex = -1;
        hasKeyboardInput = false; // Reset keyboard state on escape
        lastSearchQueryForHighlight = ''; // Reset search tracking
        break;
    }
  }

  // Keyboard navigation for search results
  function handleSearchKeydown(event) {
    handleKeyboardNavigation(event);
  }

  // Keyboard navigation for item list (when focused via click)
  function handleListKeydown(event) {
    handleKeyboardNavigation(event);
  }

  // Track if we should focus the list after navigation/update
  let shouldFocusListAfterUpdate = false;

  // Handle click on item list container to enable keyboard navigation
  function handleListClick(event) {
    // Mark that we want to focus the list (will be done in afterUpdate to ensure DOM is ready)
    shouldFocusListAfterUpdate = true;
    // Also try immediate focus for clicks on empty space
    if (listContainer) {
      listContainer.focus();
    }
  }

  // Scroll highlighted item into view within the virtualized list
  function scrollToHighlighted() {
    if (!listContainer || highlightedIndex < 0) return;

    const itemTop = highlightedIndex * ITEM_HEIGHT;
    const itemBottom = itemTop + ITEM_HEIGHT;
    const viewTop = scrollTop;
    const viewBottom = scrollTop + containerHeight;

    if (itemTop < viewTop) {
      // Scroll up to show item
      listContainer.scrollTop = itemTop;
    } else if (itemBottom > viewBottom) {
      // Scroll down to show item
      listContainer.scrollTop = itemBottom - containerHeight;
    }
  }

  // Set highlighted index based on search state and keyboard interaction
  // Only show highlight when user has actively started navigating (typing search or pressing arrow keys)
  $: if (searchQuery !== undefined) {
    if (filteredItems.length === 0) {
      highlightedIndex = -1;
      lastSearchQueryForHighlight = searchQuery;
    } else if (searchQuery.trim().length > 0) {
      // Only reset to first result when search query actually changes (user is typing)
      // Not on re-renders with same query (e.g., after navigation)
      if (searchQuery !== lastSearchQueryForHighlight) {
        highlightedIndex = 0;
        hasKeyboardInput = true; // Searching counts as keyboard interaction
        lastSearchQueryForHighlight = searchQuery;
      }
    } else if (!hasKeyboardInput) {
      // No search and no keyboard input yet - don't show highlight
      highlightedIndex = -1;
      lastSearchQueryForHighlight = searchQuery;
    }
    // If hasKeyboardInput is true but no search, keep current highlightedIndex (set by arrow keys)
  }

  // Scroll to the currently selected item if it's outside the visible viewport
  async function scrollToCurrentItem() {
    if ((!currentSlug && !currentChangeId && currentItemId == null) || !listContainer || filteredItems.length === 0) {
      initialPositionDone = true;
      return;
    }

    // Find the index of the current item in the filtered list
    const currentIndex = findCurrentItemIndex(filteredItems);
    if (currentIndex === -1) {
      initialPositionDone = true;
      return;
    }

    // Wait for DOM to update
    await tick();

    // Check if container still exists after tick
    if (!listContainer) {
      initialPositionDone = true;
      return;
    }

    const itemTop = currentIndex * ITEM_HEIGHT;
    const itemBottom = itemTop + ITEM_HEIGHT;
    const viewTop = listContainer.scrollTop;
    const viewBottom = viewTop + containerHeight;

    // Only scroll if the item is not fully visible in the viewport
    if (itemTop >= viewTop && itemBottom <= viewBottom) {
      initialPositionDone = true;
      return;
    }

    // Scroll to position the current item in view (centered if possible)
    const targetScroll = Math.max(0, itemTop - containerHeight / 2 + ITEM_HEIGHT / 2);
    listContainer.scrollTop = targetScroll;
    initialPositionDone = true;
  }

  // Track last scrolled-to item key to avoid redundant scroll attempts
  let lastScrolledKey = null;

  // Scroll to current item on selection change (initial load or navigation)
  // Also handle deferred focus for keyboard navigation
  afterUpdate(() => {
    if (currentItemKey && currentItemKey !== lastScrolledKey && filteredItems.length > 0 && listContainer) {
      lastScrolledKey = currentItemKey;
      clickedItemKey = null;
      scrollToCurrentItem();
    } else if (!currentItemKey) {
      lastScrolledKey = null;
      if (!initialPositionDone && items != null) {
        initialPositionDone = true;
      }
    }

    // Focus the list if user clicked on it and we're waiting for navigation to complete
    if (shouldFocusListAfterUpdate && listContainer) {
      shouldFocusListAfterUpdate = false;
      // Use requestAnimationFrame to ensure DOM is fully updated
      requestAnimationFrame(() => {
        if (listContainer && document.activeElement !== listContainer) {
          listContainer.focus();
        }
      });
    }
  });

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

  // Column configuration state
  let userColumnSelection = null; // null = defaults, string[] = user's ordered column keys
  let showColumnDialog = false;

  // localStorage key for column preferences
  $: storageKey = pageTypeId ? `wiki-nav-columns-${pageTypeId}` : '';

  // Load user column selection from localStorage when pageTypeId changes
  $: if (browser && storageKey) {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const keys = JSON.parse(stored);
        if (Array.isArray(keys) && keys.length > 0 && allAvailableColumns) {
          // Validate keys against available columns
          const validKeys = new Set(allAvailableColumns.map(c => c.key));
          const filtered = keys.filter(k => validKeys.has(k));
          userColumnSelection = filtered.length > 0 ? filtered : null;
        } else {
          userColumnSelection = null;
        }
      } else {
        userColumnSelection = null;
      }
    } catch {
      userColumnSelection = null;
    }
  }

  // Save user column selection to localStorage
  function saveColumnSelection(keys) {
    if (!browser || !storageKey) return;
    if (keys && keys.length > 0) {
      localStorage.setItem(storageKey, JSON.stringify(keys));
    } else {
      localStorage.removeItem(storageKey);
    }
  }

  // Build column lookup from allAvailableColumns
  $: availableColumnMap = allAvailableColumns
    ? Object.fromEntries(allAvailableColumns.map(c => [c.key, c]))
    : {};

  // Resolve user-configured columns from keys
  $: userConfiguredColumns = userColumnSelection
    ? userColumnSelection.map(k => availableColumnMap[k]).filter(Boolean)
    : null;

  // Actual columns to use: user-configured > full-width/table defaults
  $: activeColumns = (() => {
    if (userConfiguredColumns) {
      return fullWidth ? userConfiguredColumns : userConfiguredColumns.slice(0, 5);
    }
    return (fullWidth && fullWidthColumns) ? fullWidthColumns : (tableColumns || defaultTableColumns);
  })();

  $: hasCustomColumns = userColumnSelection !== null;

  function handleOpenColumnDialog() {
    showColumnDialog = true;
  }

  function handleResetColumns() {
    userColumnSelection = null;
    saveColumnSelection(null);
    // Clear sort/filter state for columns that may no longer exist
    sortColumn = null;
    sortDirection = 'asc';
    widthsCalculated = false;
    calculatedColumnWidths = {};
  }

  function handleColumnDialogApply(event) {
    const { columnKeys } = event.detail;
    userColumnSelection = columnKeys;
    saveColumnSelection(columnKeys);
    showColumnDialog = false;
    // Reset widths and sort for new column set
    widthsCalculated = false;
    calculatedColumnWidths = {};
    // Clear sort if the sorted column was removed
    if (sortColumn && !columnKeys.includes(sortColumn) && sortColumn !== 'name') {
      sortColumn = null;
    }
    // Clear column filters for removed columns
    for (const key of Object.keys(columnFilters)) {
      if (key !== 'name' && !columnKeys.includes(key)) {
        delete columnFilters[key];
      }
    }
    columnFilters = columnFilters;
  }

  function handleColumnDialogCancel() {
    showColumnDialog = false;
  }

  // Direct column header drag-and-drop (full-width mode only)
  let headerDragIndex = null;
  let headerDragOverIndex = null;
  let headerMouseDownX = 0;
  let headerMouseDownY = 0;
  let headerDragStarted = false;

  function handleHeaderMouseDown(e, colIndex) {
    // Only in full-width mode with configurable columns
    if (!fullWidth || !allAvailableColumns) return;
    headerMouseDownX = e.clientX;
    headerMouseDownY = e.clientY;
    headerDragIndex = colIndex;
    headerDragStarted = false;

    const handleMouseMove = (me) => {
      const dx = me.clientX - headerMouseDownX;
      const dy = me.clientY - headerMouseDownY;
      if (!headerDragStarted && Math.sqrt(dx * dx + dy * dy) > 5) {
        headerDragStarted = true;
      }
    };

    const handleMouseUp = (me) => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);

      if (!headerDragStarted) {
        // Was a click, not a drag - trigger sort
        // colIndex is 0-based for activeColumns, but 'name' is handled separately
        const column = activeColumns[colIndex];
        if (column) {
          handleSort(column.key);
        }
      } else if (headerDragIndex !== null && headerDragOverIndex !== null && headerDragIndex !== headerDragOverIndex) {
        // Was a drag - reorder columns
        reorderColumns(headerDragIndex, headerDragOverIndex);
      }

      headerDragIndex = null;
      headerDragOverIndex = null;
      headerDragStarted = false;
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }

  function handleHeaderDragOver(e, colIndex) {
    if (headerDragStarted && headerDragIndex !== null) {
      e.preventDefault();
      headerDragOverIndex = colIndex;
    }
  }

  function reorderColumns(fromIndex, toIndex) {
    // Get current column keys (either user-configured or from defaults)
    let keys = userConfiguredColumns
      ? userConfiguredColumns.map(c => c.key)
      : activeColumns.map(c => c.key);

    if (fromIndex < 0 || fromIndex >= keys.length || toIndex < 0 || toIndex >= keys.length) return;

    const updated = [...keys];
    const [moved] = updated.splice(fromIndex, 1);
    updated.splice(toIndex, 0, moved);

    // If user didn't have custom columns yet, we need all columns, not just the visible slice
    if (!userConfiguredColumns && allAvailableColumns) {
      // In expanded mode we only show first 5, but we should save all
      const defaultKeys = (fullWidth && fullWidthColumns)
        ? fullWidthColumns.map(c => c.key)
        : (tableColumns || defaultTableColumns).map(c => c.key);
      // If expanded mode (not fullWidth), we reordered the first 5 but need to keep the rest
      if (!fullWidth) {
        const remainingKeys = defaultKeys.slice(5);
        userColumnSelection = [...updated, ...remainingKeys];
      } else {
        userColumnSelection = updated;
      }
    } else {
      userColumnSelection = userConfiguredColumns
        ? (() => {
            const all = [...userConfiguredColumns.map(c => c.key)];
            const [m] = all.splice(fromIndex, 1);
            all.splice(toIndex, 0, m);
            return all;
          })()
        : updated;
    }

    saveColumnSelection(userColumnSelection);
    widthsCalculated = false;
    calculatedColumnWidths = {};
  }

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

  // Table view is active when either expanded or full-width mode is on
  $: showTableView = expanded || fullWidth;

  function handleToggleExpand() {
    dispatch('toggleExpand');
  }

  function handleToggleFullWidth() {
    dispatch('toggleFullWidth');
  }

  // Scrollbar width measurement
  let scrollbarWidth = 0;

  // Calculated column widths based on initial data
  let calculatedColumnWidths = {};
  let widthsCalculated = false;

  // Measure text width using canvas
  let measureCanvas;
  function measureTextWidth(text, font = '12px system-ui, -apple-system, sans-serif', letterSpacing = 0) {
    if (!browser) return 0;
    if (!measureCanvas) measureCanvas = document.createElement('canvas');
    const ctx = measureCanvas.getContext('2d');
    ctx.font = font;
    const baseWidth = ctx.measureText(String(text)).width;
    // Account for letter-spacing (applied between each character)
    const spacingExtra = letterSpacing * Math.max(0, String(text).length - 1);
    return baseWidth + spacingExtra;
  }

  function parseColumnWidth(width) {
    if (!width) return null;
    const match = String(width).trim().match(/^(\d+(?:\.\d+)?)px$/i);
    return match ? Number(match[1]) : null;
  }

  // Calculate column widths based on initial data (only needed for table view)
  function calculateColumnWidths() {
    if (widthsCalculated || !showTableView || !items || items.length === 0) return;

    // Font specs matching .th CSS: font-weight 600, 11px, uppercase, letter-spacing 0.3px
    const headerFont = '600 11px system-ui, -apple-system, sans-serif';
    const headerLetterSpacing = 0.3;
    const headerPadding = 8; // .th padding: 6px 4px → 8px horizontal
    // Font specs matching .cell CSS: 12px, padding: 0 2px → 4px horizontal
    const cellFont = '12px system-ui, -apple-system, sans-serif';
    const cellPadding = 8; // 4px CSS padding + 4px extra breathing room
    const minWidth = 40;
    const maxWidth = 160;
    const sourceItems = visibleItems?.length ? visibleItems : [];
    if (sourceItems.length === 0) return;

    for (const column of activeColumns) {
      // Measure header width (uppercase + sort arrow + letter-spacing)
      const headerText = (column.header + ' ▲').toUpperCase();
      const headerWidth = measureTextWidth(headerText, headerFont, headerLetterSpacing) + headerPadding;

      // Measure all cell values in the column
      let maxCellWidth = 0;
      for (const item of sourceItems) {
        const value = formatCell(item, column);
        const textWidth = measureTextWidth(value, cellFont);
        if (textWidth > maxCellWidth) {
          maxCellWidth = textWidth;
        }
      }
      maxCellWidth += cellPadding;

      // Use the wider of header vs cell content, plus extra breathing room
      const contentWidth = Math.max(headerWidth, maxCellWidth) + 20;
      const finalWidth = Math.max(minWidth, Math.min(maxWidth, Math.ceil(contentWidth)));
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

  // Recalculate column widths when columns change (e.g. switching between expanded and full-width)
  $: if (activeColumns) {
    widthsCalculated = false;
    calculatedColumnWidths = {};
  }

  // Calculate column widths when table view is enabled (run in background to avoid blocking UI)
  $: if (browser && showTableView && !widthsCalculated && items && items.length > 0) {
    // Use requestIdleCallback to run calculation when browser is idle
    if (typeof requestIdleCallback !== 'undefined') {
      requestIdleCallback(() => calculateColumnWidths(), { timeout: 1000 });
    } else {
      // Fallback for browsers without requestIdleCallback
      setTimeout(() => calculateColumnWidths(), 0);
    }
  }

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

<nav class="wiki-nav" class:expanded={showTableView} class:full-width={fullWidth}>
  <div class="nav-header">
    <h2 class="nav-title">{title}</h2>
    <div class="header-buttons hide-on-mobile">
      {#if !fullWidth}
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
      {/if}
      <button
        class="expand-btn"
        class:active={fullWidth}
        on:click={handleToggleFullWidth}
        title={fullWidth ? 'Exit full-width mode' : 'Full-width table view'}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          {#if fullWidth}
            <path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7" />
          {:else}
            <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
          {/if}
        </svg>
      </button>
    </div>
  </div>

  <!-- Slot for custom content between header and search (e.g., view toggles) -->
  <slot name="after-header"></slot>

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
      on:keydown={handleSearchKeydown}
    />
    {#if searchQuery}
      <button class="clear-search" on:click={() => { searchQuery = ''; highlightedIndex = -1; hasKeyboardInput = false; lastSearchQueryForHighlight = ''; }} aria-label="Clear search">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    {/if}
  </div>

  {#if linkFilters.length > 0 || filters.length > 0 || (showTableView && allAvailableColumns)}
    <div class="filter-section">
      <!-- Link-based type navigation buttons (with column config inline) -->
      {#if linkFilters.length > 0}
        <div class="type-nav-buttons">
          {#each linkFilters as btn}
            <a
              href={btn.href}
              class="type-nav-btn"
              class:active={btn.active}
              title={btn.title}
            >
              {btn.label}
            </a>
          {/each}
          {#if showTableView && allAvailableColumns}
            <span class="column-config-inline">
              <button class="column-config-btn" on:click={handleOpenColumnDialog} title="Configure columns">Columns...</button>
              {#if hasCustomColumns}
                <button class="column-config-btn reset" on:click={handleResetColumns} title="Reset to default columns">Reset</button>
              {/if}
            </span>
          {/if}
        </div>
      {:else if filters.length > 0 && filters[0]?.href !== undefined}
        <!-- Legacy: Link-based type navigation in filters prop -->
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
          {#if showTableView && allAvailableColumns}
            <span class="column-config-inline">
              <button class="column-config-btn" on:click={handleOpenColumnDialog} title="Configure columns">Columns...</button>
              {#if hasCustomColumns}
                <button class="column-config-btn reset" on:click={handleResetColumns} title="Reset to default columns">Reset</button>
              {/if}
            </span>
          {/if}
        </div>
      {:else if showTableView && allAvailableColumns && filters.length === 0}
        <!-- Column config only (no filter buttons on this page) -->
        <div class="column-config-actions">
          <button class="column-config-btn" on:click={handleOpenColumnDialog} title="Configure columns">Columns...</button>
          {#if hasCustomColumns}
            <button class="column-config-btn reset" on:click={handleResetColumns} title="Reset to default columns">Reset</button>
          {/if}
        </div>
      {/if}
      {#if filters.length > 0 && filters[0]?.href === undefined}
        <!-- Value-based category filters -->
        {#each filters as filter, filterIdx}
          <div class="filter-group">
            <div class="filter-label-row">
              <span class="filter-label">{filter.label}</span>
              {#if filter.helpText}
                <button
                  class="filter-help-btn"
                  class:active={openFilterHelp === filter.key}
                  on:click={() => openFilterHelp = openFilterHelp === filter.key ? null : filter.key}
                  title="Filter info"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                    <line x1="12" y1="17" x2="12.01" y2="17" />
                  </svg>
                </button>
              {/if}
              {#if filterIdx === 0 && showTableView && allAvailableColumns && linkFilters.length === 0}
                <span class="column-config-inline">
                  <button class="column-config-btn" on:click={handleOpenColumnDialog} title="Configure columns">Columns...</button>
                  {#if hasCustomColumns}
                    <button class="column-config-btn reset" on:click={handleResetColumns} title="Reset to default columns">Reset</button>
                  {/if}
                </span>
              {/if}
            </div>
            {#if filter.helpText && openFilterHelp === filter.key}
              <div class="filter-help-popover">
                {#each filter.helpText as line}
                  <div class="help-line">{line}</div>
                {/each}
              </div>
            {/if}
            <div class="filter-options">
              {#each filter.values as option}
                <button
                  class="filter-btn"
                  class:active={filter.multiSelect
                    ? (activeFilters[filter.key] || []).includes(option.value)
                    : activeFilters[filter.key] === option.value}
                  on:click={() => setFilter(filter.key, option.value, filter.multiSelect)}
                >
                  {option.label}
                </button>
              {/each}
            </div>
          </div>
        {/each}

        {#if Object.values(activeFilters).some(v => v !== null && (Array.isArray(v) ? v.length > 0 : true))}
          <button class="clear-filters" on:click={clearFilters}>
            Clear filters
          </button>
        {/if}
      {/if}
    </div>
  {/if}

  <!-- Table header for expanded/full-width view -->
  {#if showTableView}
    <div class="table-header-bar">
      <div class="table-header" style="grid-template-columns: {dynamicGridTemplateColumns} auto;">
        <button class="th sortable" class:sorted={sortColumn === 'name'} on:click={() => handleSort('name')}>
          Name {sortColumn === 'name' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
        </button>
        {#each activeColumns as column, colIdx}
          <button
            class="th sortable"
            class:sorted={sortColumn === column.key}
            class:header-drag-over={headerDragStarted && headerDragOverIndex === colIdx && headerDragIndex !== colIdx}
            on:click={(e) => { if (!fullWidth || !allAvailableColumns) handleSort(column.key); }}
            on:mousedown={(e) => handleHeaderMouseDown(e, colIdx)}
            on:mouseover={(e) => handleHeaderDragOver(e, colIdx)}
            on:focus={() => {}}
          >
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
    on:keydown={handleListKeydown}
    on:click={handleListClick}
    tabindex="0"
    role="listbox"
    aria-label="Item list"
  >
    {#if items === null || items === undefined}
      <!-- Loading state -->
      <div class="loading-skeleton">
        {#each Array(20) as _, i}
          <div class="skeleton-item" style="animation-delay: {i * 0.05}s"></div>
        {/each}
      </div>
    {:else if filteredItems.length === 0}
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
          {#each visibleItems as item, localIndex (item._isPendingCreate ? `pending-${item._changeId}` : (item.Id ?? item.Name))}
            {@const globalIndex = startIndex + localIndex}
            <a
              href={getItemHref(item)}
              class="item-link"
              class:active={clickedItemKey ? clickedItemKey === getItemKey(item) : (currentItemKey && isCurrentItem(item))}
              class:highlighted={globalIndex === highlightedIndex}
              class:table-row={showTableView}
              class:alt-row={showTableView && globalIndex % 2 === 1}
              class:pending-create={item._isPendingCreate}
              class:pending-draft={item._isPendingCreate && item._changeState === 'Draft'}
              class:pending-review={item._isPendingCreate && item._changeState === 'Pending'}
              class:pending-update={item._hasPendingUpdate}
              class:pending-update-draft={item._hasPendingUpdate && item._changeState === 'Draft'}
              class:pending-update-review={item._hasPendingUpdate && item._changeState === 'Pending'}
              on:click={() => handleItemClick(item)}
              on:mouseenter={() => { highlightedIndex = globalIndex; hasKeyboardInput = true; }}
              title={item._isPendingCreate
                ? `${item.Name} (${item._changeState})`
                : item._hasPendingUpdate
                  ? `${item.Name} (${item._changeState})`
                  : item.Name}
              style={showTableView ? `grid-template-columns: ${dynamicGridTemplateColumns};` : ''}
            >
              {#if showTableView}
                <span class="cell cell-name" title={item.Name}>
                  {#if item._isPendingCreate}
                    <span class="pending-badge" class:draft={item._changeState === 'Draft'} class:review={item._changeState === 'Pending'}>
                      {item._changeState === 'Draft' ? 'Draft' : 'Review'}
                    </span>
                  {:else if item._hasPendingUpdate}
                    <span class="pending-badge update" class:draft={item._changeState === 'Draft'} class:review={item._changeState === 'Pending'}>
                      {item._changeState === 'Draft' ? 'Draft' : 'Review'}
                    </span>
                  {/if}
                  {item.Name}
                </span>
                {#each activeColumns as column}
                  <span class="cell cell-{column.key}">{formatCell(item, column)}</span>
                {/each}
              {:else}
                <span class="item-name" title={item.Name}>
                  {#if item._isPendingCreate}
                    <span class="pending-badge" class:draft={item._changeState === 'Draft'} class:review={item._changeState === 'Pending'}>
                      {item._changeState === 'Draft' ? 'Draft' : 'Review'}
                    </span>
                  {:else if item._hasPendingUpdate}
                    <span class="pending-badge update" class:draft={item._changeState === 'Draft'} class:review={item._changeState === 'Pending'}>
                      {item._changeState === 'Draft' ? 'Draft' : 'Review'}
                    </span>
                  {/if}
                  {item.Name}
                </span>
              {/if}
            </a>
          {/each}
        </div>
      </div>
    {/if}
    {#if !initialPositionDone && items != null && items.length > 0}
      <div class="loading-overlay">
        {#each Array(20) as _, i}
          <div class="skeleton-item" style="animation-delay: {i * 0.05}s"></div>
        {/each}
      </div>
    {/if}
  </div>

  <div class="nav-footer">
    <span class="item-count">{filteredItems.length} items</span>
  </div>

  {#if showColumnDialog && allAvailableColumns}
    <ColumnConfigDialog
      visibleColumns={userConfiguredColumns || activeColumns}
      allColumns={allAvailableColumns}
      on:apply={handleColumnDialogApply}
      on:cancel={handleColumnDialogCancel}
    />
  {/if}
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
    min-height: 28px;
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

  .header-buttons {
    display: flex;
    gap: 4px;
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

  .expand-btn.active {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
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

  .filter-label-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
  }

  .filter-label {
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .filter-help-btn {
    padding: 2px;
    background: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 50%;
    color: var(--text-muted, #999);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
  }

  .filter-help-btn:hover,
  .filter-help-btn.active {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .filter-help-popover {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    padding: 8px 10px;
    margin-bottom: 8px;
    font-size: 11px;
  }

  .filter-help-popover .help-line {
    color: var(--text-color);
    padding: 2px 0;
  }

  .filter-help-popover .help-line:first-child {
    padding-top: 0;
  }

  .filter-help-popover .help-line:last-child {
    padding-bottom: 0;
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
    margin-bottom: 10px;
  }

  /* Remove bottom margin if type-nav-buttons is the last child (no filters following) */
  .type-nav-buttons:last-child {
    margin-bottom: 0;
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

  /* Column config buttons inline with type nav buttons */
  .column-config-inline {
    display: inline-flex;
    gap: 4px;
    margin-left: auto;
  }

  /* Column config buttons standalone (no filter buttons) */
  .column-config-actions {
    display: flex;
    justify-content: flex-end;
    gap: 6px;
    margin-bottom: 6px;
  }

  .filter-section:has(.column-config-actions:only-child) {
    padding-bottom: 6px;
  }

  .column-config-btn {
    padding: 4px 10px;
    font-size: 12px;
    background: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    cursor: pointer;
    transition: all 0.15s;
  }

  .column-config-btn:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
  }

  .column-config-btn.reset {
    border-style: dashed;
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

  .th.header-drag-over {
    border-left: 2px solid var(--accent-color, #4a9eff);
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
    opacity: 0.5;
    font-size: 10px;
  }

  .item-list {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
    margin: 0 12px 12px;
    position: relative;
  }

  /* Force scrollbar to always be visible in expanded table mode for consistent column alignment */
  .wiki-nav.expanded .item-list {
    overflow-y: scroll;
  }

  .item-list:focus {
    outline: none;
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

  .item-link.active:hover {
    background-color: var(--accent-color-hover, #3a8eef);
    color: white;
  }

  .item-link.highlighted {
    background-color: var(--hover-color);
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: -2px;
  }

  .item-link.highlighted.active {
    background-color: var(--accent-color, #4a9eff);
    color: white;
    outline: 2px solid var(--text-color, white);
  }

  /* Pending create items */
  .item-link.pending-create {
    border-left: 3px solid var(--success-color, #16a34a);
    padding-left: 5px;
  }

  .item-link.pending-update {
    border-left: 3px solid var(--warning-color, #f59e0b);
    padding-left: 5px;
  }

  .pending-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 16px;
    padding: 0 6px;
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    border-radius: 3px;
    margin-right: 6px;
    margin-bottom: 1px;
    flex-shrink: 0;
    color: #fff;
    text-align: center;
    line-height: 1;
  }

  .pending-badge.draft {
    background-color: #1e40af;
    color: #fff;
  }

  .pending-badge.review {
    background-color: var(--success-color, #16a34a);
    color: #fff;
  }

  .pending-badge.update {
    background-color: var(--warning-color, #f59e0b);
    color: white;
  }

  .pending-badge.update.draft {
    background-color: #1e40af;
    color: #fff;
  }

  .pending-badge.update.review {
    background-color: var(--warning-color, #f59e0b);
    color: white;
  }

  .item-name {
    display: flex;
    align-items: center;
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

  .item-link.table-row.alt-row {
    background-color: var(--table-alt-row, rgba(255, 255, 255, 0.02));
  }

  .item-link.table-row:hover {
    background-color: var(--hover-color);
  }

  .item-link.table-row.active {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .item-link.table-row.active:hover {
    background-color: var(--accent-color-hover, #3a8eef);
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
    display: flex;
    align-items: center;
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

  /* Loading skeleton */
  .loading-skeleton {
    padding: 4px 0;
  }

  .skeleton-item {
    height: 28px;
    margin: 4px 0;
    background: linear-gradient(
      90deg,
      var(--hover-color) 25%,
      var(--secondary-color) 50%,
      var(--hover-color) 75%
    );
    background-size: 200% 100%;
    border-radius: 4px;
    animation: skeleton-pulse 1.5s ease-in-out infinite;
  }

  @keyframes skeleton-pulse {
    0% {
      background-position: 200% 0;
    }
    100% {
      background-position: -200% 0;
    }
  }

  .loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: var(--secondary-color);
    z-index: 1;
    padding: 4px 0;
  }

  /* Mobile adjustments - aligned with global 900px breakpoint */
  @media (max-width: 899px) {
    .hide-on-mobile {
      display: none !important;
    }

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
