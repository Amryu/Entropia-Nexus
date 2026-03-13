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
    onselect={(e) => selected = e.value}
  />

  @example API mode for items
  <SearchInput
    value={itemName}
    apiEndpoint="/search/items"
    placeholder="Search item..."
    displayFn={(item) => item.Name}
    valueFn={(item) => item.Name}
    onselect={(e) => handleItemSelect(e.data)}
  />
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy, tick } from 'svelte';
  import { browser } from '$app/environment';
  import { scoreSearchResult } from '$lib/search.js';

  

  

  

  

  // --- Local mode props ---
  

  // --- API mode props ---
  

  

  

  

  

  

  

  // --- Filtering props ---
  

  

  

  // --- Display props ---
  

  

  

  // --- Validation props ---
  
  /**
   * @typedef {Object} Props
   * @property {string} [value]
   * @property {string} [placeholder]
   * @property {number} [limit]
   * @property {boolean} [disabled]
   * @property {Array<{label: string, value: string}|string>} [options]
   * @property {string|null} [apiEndpoint]
   * @property {boolean} [fuzzy]
   * @property {number} [minChars]
   * @property {number} [debounceMs]
   * @property {string|null} [typeFilter]
   * @property {Object|null} [apiParams]
   * @property {boolean} [clearOnSelect]
   * @property {Function|null} [filterFn]
   * @property {Array|null} [allowedTypes]
   * @property {Array|null} [allowedNames]
   * @property {Function|null} [displayFn]
   * @property {Function|null} [valueFn]
   * @property {string} [emptyMessage]
   * @property {Array<string>|Set<string>|null} [validValues]
   * @property {Function} [onchange]
   * @property {Function} [onselect]
   */

  /** @type {Props} */
  let {
    value = '',
    placeholder = 'Search...',
    limit = 10,
    disabled = false,
    options = null,
    apiEndpoint = null,
    fuzzy = true,
    minChars = 2,
    debounceMs = 250,
    typeFilter = null,
    apiParams = null,
    clearOnSelect = false,
    filterFn = null,
    allowedTypes = null,
    allowedNames = null,
    displayFn = null,
    valueFn = null,
    emptyMessage = 'No matches',
    validValues = null,
    onchange,
    onselect
  } = $props();

  let localValue = $state('');
  let results = $state([]);
  let isSearching = $state(false);
  let showResults = $state(false);
  let highlightedIndex = $state(-1);
  let searchTimeout;
  let inputEl = $state();
  let dropdownStyle = $state('');





  // --- Option Normalization (local mode) ---
  function normalizeOptions(list) {
    return (list || []).map(opt => {
      if (typeof opt === 'string') {
        return { label: opt, value: opt, _raw: opt };
      }
      return {
        label: opt?.label ?? opt?.value ?? '',
        value: opt?.value ?? opt?.label ?? '',
        sublabel: opt?.sublabel ?? null,
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
          scoreSearchResult(String(opt.value), q),
          opt.sublabel ? scoreSearchResult(opt.sublabel, q) : 0
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

      // Add any extra API parameters
      if (apiParams) {
        for (const [key, val] of Object.entries(apiParams)) {
          params.set(key, val);
        }
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
    // Strip game client brackets from pasted names like "[Item Name]"
    let raw = event.target.value;
    const cleaned = raw.replace(/^\[/, '').replace(/\]$/, '');
    if (cleaned !== raw) {
      event.target.value = cleaned;
    }
    const query = cleaned;
    localValue = query;
    onchange?.({ value: query });

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
    onchange?.({ value: clearOnSelect ? '' : displayText });
    onselect?.({ value: selectedValue, data: rawData });
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
  // Determine mode
  let isLocalMode = $derived(options !== null && apiEndpoint === null);
  let isApiMode = $derived(apiEndpoint !== null);
  // Validation: build a Set for O(1) lookups
  let validSet = $derived(validValues
    ? (validValues instanceof Set ? validValues : new Set(validValues))
    : null);
  // Sync external value changes
  $effect(() => {
    localValue = value ?? '';
  });
  let isValid = $derived(validSet && localValue?.trim() ? validSet.has(localValue.trim()) : null);
  // Update dropdown position when showing
  $effect(() => {
    if (browser && showResults) {
      tick().then(updateDropdownPosition);
    }
  });
</script>

<div class="search-input">
  <div class="input-wrapper">
    <input
      bind:this={inputEl}
      type="text"
      value={localValue}
      oninput={handleInput}
      onkeydown={handleKeydown}
      onblur={handleBlur}
      onfocus={handleFocus}
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
          <div
            class="search-result"
            class:highlighted={resultIndex === highlightedIndex}
            role="button"
            tabindex="0"
            onclick={() => selectResult(result)}
            onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), selectResult(result))}
            onmouseenter={() => highlightedIndex = resultIndex}
          >
            <span class="result-name">{getDisplayText(result)}</span>
            {#if result.sublabel}
              <span class="result-sublabel">{result.sublabel}</span>
            {/if}
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

  .result-sublabel {
    display: block;
    font-size: 10px;
    color: var(--text-muted, #999);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-top: 1px;
  }
</style>
