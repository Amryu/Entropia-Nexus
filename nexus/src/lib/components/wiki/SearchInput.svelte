<!--
  @component SearchInput
  Unified searchable input component supporting both local options and API search.

  Modes:
  - Local: Pass `options` array for client-side filtering
  - API: Pass `apiEndpoint` for server-side search

  Emits:
  - change: { value } - On input change
  - select: { value, data } - When an option is selected (data is the full object)

  @example Local mode with simple options
  <SearchInput
    value={selected}
    options={[{ label: 'Option A', value: 'a' }, { label: 'Option B', value: 'b' }]}
    placeholder="Select option..."
    on:select={(e) => selected = e.detail.value}
  />

  @example API mode for items
  <SearchInput
    value={itemName}
    apiEndpoint="/search/items"
    placeholder="Search item..."
    displayFn={(item) => item.Name}
    valueFn={(item) => item.Name}
    on:select={(e) => handleItemSelect(e.detail.data)}
  />
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher, onMount, onDestroy, tick } from 'svelte';
  import { browser } from '$app/environment';
  import { scoreSearchResult } from '$lib/search.js';

  /** @type {string} Current value (displayed in input) */
  export let value = '';

  /** @type {string} Placeholder text */
  export let placeholder = 'Search...';

  /** @type {number} Maximum results to show */
  export let limit = 10;

  /** @type {boolean} Whether the input is disabled */
  export let disabled = false;

  // --- Local mode props ---
  /** @type {Array<{label: string, value: string}|string>} Local options array */
  export let options = null;

  // --- API mode props ---
  /** @type {string|null} API endpoint for search (e.g., '/search/items') */
  export let apiEndpoint = null;

  /** @type {boolean} Whether to use fuzzy search (API mode) */
  export let fuzzy = true;

  /** @type {number} Minimum characters before searching (API mode) */
  export let minChars = 2;

  /** @type {number} Debounce delay in ms (API mode) */
  export let debounceMs = 250;

  /** @type {string|null} Filter to a specific item type (e.g., 'Blueprint'). Removes per-category limit. */
  export let typeFilter = null;

  /** @type {boolean} Whether to clear the input after selecting an option */
  export let clearOnSelect = false;

  // --- Filtering props ---
  /** @type {Function|null} Custom filter function: (item) => boolean */
  export let filterFn = null;

  /** @type {Array|null} Only include items with these types (for item search) */
  export let allowedTypes = null;

  /** @type {Array|null} Only include items with these names */
  export let allowedNames = null;

  // --- Display props ---
  /** @type {Function|null} Custom display function: (item) => string */
  export let displayFn = null;

  /** @type {Function|null} Custom value extraction: (item) => string */
  export let valueFn = null;

  /** @type {string} Message when no results found */
  export let emptyMessage = 'No matches';

  // --- Validation props ---
  /** @type {Array<string>|Set<string>|null} Known valid values for validation border (green/red) */
  export let validValues = null;

  const dispatch = createEventDispatcher();

  let localValue = value || '';
  let results = [];
  let isSearching = false;
  let showResults = false;
  let highlightedIndex = -1;
  let searchTimeout;
  let inputEl;
  let dropdownStyle = '';

  // Determine mode
  $: isLocalMode = options !== null && apiEndpoint === null;
  $: isApiMode = apiEndpoint !== null;

  // Validation: build a Set for O(1) lookups
  $: validSet = validValues
    ? (validValues instanceof Set ? validValues : new Set(validValues))
    : null;
  $: isValid = validSet && localValue?.trim() ? validSet.has(localValue.trim()) : null;

  // Sync external value changes
  $: localValue = value ?? '';

  // Update dropdown position when showing
  $: if (browser && showResults) {
    tick().then(updateDropdownPosition);
  }

  // --- Option Normalization (local mode) ---
  function normalizeOptions(list) {
    return (list || []).map(opt => {
      if (typeof opt === 'string') {
        return { label: opt, value: opt, _raw: opt };
      }
      return {
        label: opt?.label ?? opt?.value ?? '',
        value: opt?.value ?? opt?.label ?? '',
        _raw: opt
      };
    });
  }

  // --- Display/Value helpers ---
  function getDisplayText(item) {
    if (typeof displayFn === 'function') {
      return displayFn(item);
    }
    // For normalized local options
    if (item?.label !== undefined) {
      return item.label;
    }
    // For API results (typically have Name)
    return item?.Name || '';
  }

  function getValue(item) {
    if (typeof valueFn === 'function') {
      return valueFn(item);
    }
    // For normalized local options
    if (item?.value !== undefined) {
      return item.value;
    }
    // For API results
    return item?.Name || '';
  }

  function getRawData(item) {
    // For local options, return the original object
    if (item?._raw !== undefined) {
      return item._raw;
    }
    return item;
  }

  // --- Filtering ---
  function applyFilters(items) {
    let filtered = items || [];

    // Type filter (for items with Properties.Type or Type)
    if (Array.isArray(allowedTypes) && allowedTypes.length > 0) {
      filtered = filtered.filter(item => {
        const itemType = item?.Properties?.Type ?? item?.Type ?? item?.t;
        return allowedTypes.includes(itemType);
      });
    }

    // Name filter
    if (Array.isArray(allowedNames) && allowedNames.length > 0) {
      const nameSet = new Set(allowedNames);
      filtered = filtered.filter(item => nameSet.has(item?.Name));
    }

    // Custom filter function
    if (typeof filterFn === 'function') {
      filtered = filtered.filter(filterFn);
    }

    return filtered;
  }

  // --- Local search ---
  function filterLocalResults(query) {
    const q = query.trim().toLowerCase();
    let normalized = normalizeOptions(options);

    // Apply custom filter to raw data
    if (typeof filterFn === 'function') {
      normalized = normalized.filter(opt => filterFn(opt._raw));
    }

    if (!q) {
      // Show all options on empty query (focus behavior)
      return normalized.slice(0, limit);
    }

    return normalized
      .map(opt => ({
        ...opt,
        _score: Math.max(
          scoreSearchResult(opt.label, q),
          scoreSearchResult(String(opt.value), q)
        )
      }))
      .filter(opt => opt._score > 0)
      .sort((a, b) => b._score - a._score)
      .slice(0, limit);
  }

  // --- API search ---
  async function performApiSearch(query) {
    if (query.length < minChars) {
      results = [];
      isSearching = false;
      showResults = query.length >= minChars;
      highlightedIndex = -1;
      return;
    }

    showResults = true;

    if (!browser) {
      results = [];
      isSearching = false;
      highlightedIndex = -1;
      return;
    }

    isSearching = true;

    try {
      const params = new URLSearchParams({
        query: query,
        fuzzy: fuzzy ? 'true' : 'false',
        limit: String(limit)
      });

      // Add type filter if specified (removes per-category limit in API)
      if (typeFilter) {
        params.set('type', typeFilter);
      }

      const response = await fetch(
        import.meta.env.VITE_API_URL + `${apiEndpoint}?${params}`
      );
      const data = await response.json();
      const filtered = applyFilters(data || []);
      results = filtered;
      highlightedIndex = filtered.length > 0 ? 0 : -1;
    } catch (err) {
      results = [];
      highlightedIndex = -1;
    } finally {
      isSearching = false;
    }
  }

  // --- Dropdown positioning ---
  function updateDropdownPosition() {
    if (!inputEl || !showResults) return;
    const rect = inputEl.getBoundingClientRect();
    const top = Math.round(rect.bottom + 2);
    const left = Math.round(rect.left);
    const width = Math.round(rect.width);
    dropdownStyle = `position: fixed; top: ${top}px; left: ${left}px; width: ${width}px;`;
  }

  function handleViewportChange() {
    if (showResults) {
      updateDropdownPosition();
    }
  }

  onMount(() => {
    if (browser) {
      window.addEventListener('scroll', handleViewportChange, true);
      window.addEventListener('resize', handleViewportChange);
    }
  });

  onDestroy(() => {
    if (browser) {
      window.removeEventListener('scroll', handleViewportChange, true);
      window.removeEventListener('resize', handleViewportChange);
    }
    if (searchTimeout) clearTimeout(searchTimeout);
  });

  // --- Event handlers ---
  function handleInput(event) {
    const query = event.target.value;
    localValue = query;
    dispatch('change', { value: query });

    if (isLocalMode) {
      results = filterLocalResults(query);
      showResults = true;
      highlightedIndex = results.length > 0 ? 0 : -1;
    } else if (isApiMode) {
      if (searchTimeout) clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => performApiSearch(query), debounceMs);
    }
  }

  function handleKeydown(event) {
    if (!showResults || results.length === 0) {
      if (event.key === 'Escape') {
        closeResults();
      }
      return;
    }

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        highlightedIndex = Math.min(highlightedIndex + 1, results.length - 1);
        break;
      case 'ArrowUp':
        event.preventDefault();
        highlightedIndex = Math.max(highlightedIndex - 1, 0);
        break;
      case 'Enter':
        event.preventDefault();
        if (highlightedIndex >= 0 && highlightedIndex < results.length) {
          selectResult(results[highlightedIndex]);
        }
        break;
      case 'Escape':
        event.preventDefault();
        closeResults();
        break;
      case 'Tab':
        closeResults();
        break;
    }
  }

  function selectResult(item) {
    const selectedValue = getValue(item);
    const displayText = getDisplayText(item);
    const rawData = getRawData(item);

    localValue = clearOnSelect ? '' : displayText;
    dispatch('change', { value: clearOnSelect ? '' : displayText });
    dispatch('select', { value: selectedValue, data: rawData });
    closeResults();
  }

  function closeResults() {
    showResults = false;
    highlightedIndex = -1;
  }

  function handleBlur() {
    setTimeout(() => {
      closeResults();
    }, 200);
  }

  function handleFocus() {
    if (isLocalMode) {
      // Show options immediately on focus for local mode
      results = filterLocalResults(localValue);
      showResults = true;
      highlightedIndex = results.length > 0 ? 0 : -1;
    } else if (isApiMode) {
      // Only show if we have results and meet minChars
      if (localValue.length >= minChars && results.length > 0) {
        showResults = true;
      }
    }
  }
</script>

<div class="search-input">
  <div class="input-wrapper">
    <input
      bind:this={inputEl}
      type="text"
      value={localValue}
      on:input={handleInput}
      on:keydown={handleKeydown}
      on:blur={handleBlur}
      on:focus={handleFocus}
      {placeholder}
      autocomplete="off"
      spellcheck="false"
      {disabled}
      class:valid={isValid === true}
      class:invalid={isValid === false}
      class:has-icon={validSet !== null || isSearching}
    />
    {#if isSearching}
      <span class="search-spinner"></span>
    {:else if isValid === true}
      <span class="validation-icon valid" title="Valid item">✓</span>
    {:else if isValid === false}
      <span class="validation-icon invalid" title="Item not found">⚠</span>
    {/if}
  </div>

  {#if showResults}
    <div class="search-dropdown" style={dropdownStyle}>
      {#if isSearching}
        <div class="search-status">Searching...</div>
      {:else if !results.length}
        <div class="search-status">{emptyMessage}</div>
      {:else}
        {#each results as result, resultIndex}
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div
            class="search-result"
            class:highlighted={resultIndex === highlightedIndex}
            on:click={() => selectResult(result)}
            on:mouseenter={() => highlightedIndex = resultIndex}
          >
            <span class="result-name">{getDisplayText(result)}</span>
          </div>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .search-input {
    position: relative;
    width: 100%;
  }

  .input-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .input-wrapper input {
    padding: 4px 6px;
    font-size: 12px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-color);
    width: 100%;
    box-sizing: border-box;
    height: 28px;
  }

  .input-wrapper input.has-icon {
    padding-right: 26px;
  }

  .input-wrapper input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .input-wrapper input.valid {
    border-color: var(--success-color, #22c55e);
  }

  .input-wrapper input.invalid {
    border-color: var(--error-color, #ef4444);
  }

  .input-wrapper input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .validation-icon {
    position: absolute;
    right: 6px;
    font-size: 12px;
    pointer-events: none;
  }

  .validation-icon.valid {
    color: var(--success-color, #22c55e);
  }

  .validation-icon.invalid {
    color: var(--error-color, #ef4444);
  }

  .search-spinner {
    position: absolute;
    right: 6px;
    width: 12px;
    height: 12px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .search-dropdown {
    position: fixed;
    z-index: 1000;
    max-height: 200px;
    overflow-y: auto;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.3);
  }

  .search-status {
    padding: 10px 12px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 12px;
  }

  .search-result {
    padding: 8px 10px;
    font-size: 12px;
    color: var(--text-color);
    cursor: pointer;
    border-bottom: 1px solid var(--border-color, #555);
    text-align: left;
  }

  .search-result:last-child {
    border-bottom: none;
  }

  .search-result:hover,
  .search-result.highlighted {
    background-color: var(--hover-color);
  }

  .search-result.highlighted {
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: -2px;
  }

  .result-name {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    display: block;
  }
</style>
