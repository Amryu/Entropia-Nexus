<!--
  @component SearchInput
  Reusable search input component with keyboard navigation and categorized results.

  Features:
  - Debounced search (configurable delay)
  - Keyboard navigation (up/down arrows, Enter to select, Escape to close)
  - Score-based ranking (exact matches first)
  - Categorized results with smart limiting
  - Supports both dropdown and fullscreen modes

  @example
  <SearchInput
    placeholder="Search items..."
    on:select={(e) => goto(e.detail.url)}
    on:close={() => handleClose()}
  />
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import { getTypeLink, getTypeName } from '$lib/util';
  import { scoreSearchResult } from '$lib/search.js';

  const dispatch = createEventDispatcher();

  /** @type {string} Placeholder text */
  export let placeholder = 'Search...';

  /** @type {string} Current search query (bindable) */
  export let value = '';

  /** @type {number} Debounce delay in ms */
  export let debounceMs = 300;

  /** @type {'dropdown' | 'fullscreen'} Display mode */
  export let mode = 'dropdown';

  /** @type {boolean} Whether the input is disabled */
  export let disabled = false;

  /** @type {string} Additional CSS class for the container */
  export let containerClass = '';

  /** @type {number} Maximum results per category */
  export let maxPerCategory = 5;

  /** @type {number} Maximum total results */
  export let maxTotal = 20;

  /** @type {boolean} Show results dropdown */
  export let showResults = false;

  /** @type {string} Search API endpoint (default: /search, use /search/items for items-only) */
  export let endpoint = '/search';

  /** @type {boolean} Whether to prepend VITE_API_URL to the endpoint (false for SvelteKit routes) */
  export let apiPrefix = true;

  /** @type {boolean} Whether to show results area on focus (useful for mobile) */
  export let showOnFocus = false;

  // Internal state
  let inputElement;
  let searchResults = [];
  let isSearching = false;
  let highlightedIndex = -1;
  let searchTimeout;
  let flatResults = []; // Flattened results for keyboard navigation
  let preventBlurClose = false; // Prevent blur from closing when context menu opens
  let hasUsedArrowKeys = false; // Track if arrow keys were used for selection

  // Cleanup on destroy
  onDestroy(() => {
    if (searchTimeout) clearTimeout(searchTimeout);
  });

  function rankSearchResults(results, query) {
    // Re-score client-side using the shared algorithm for consistent ranking
    // This ensures exact matches always float to the top
    return results
      .map(result => ({
        ...result,
        _score: scoreSearchResult(result.Name, query) || result.Score || 0
      }))
      .filter(r => r._score > 0)
      .sort((a, b) => {
        if (b._score !== a._score) return b._score - a._score;
        return a.Name.length - b.Name.length;
      });
  }

  function categorizeResults(results) {
    const categories = {};
    let totalShown = 0;

    for (const result of results) {
      const category = getTypeName(result.Type) || 'Other';
      if (!categories[category]) {
        categories[category] = [];
      }
      categories[category].push(result);
    }

    // Sort categories by highest score (first item's score, since results are pre-sorted)
    const sortedCategories = Object.keys(categories).sort((a, b) => {
      const scoreA = categories[a][0]?._score || 0;
      const scoreB = categories[b][0]?._score || 0;
      return scoreB - scoreA; // Highest score first
    });

    // Build ordered result with limits
    const orderedCategories = {};
    for (const cat of sortedCategories) {
      const remaining = maxTotal - totalShown;
      if (remaining <= 0) {
        continue; // Skip categories when we've hit the total limit
      }
      const limit = Math.min(maxPerCategory, remaining);
      const items = categories[cat].slice(0, limit);
      if (items.length > 0) {
        orderedCategories[cat] = items;
        totalShown += items.length;
      }
    }

    return orderedCategories;
  }

  // Search API ID offsets for non-item entity types
  const SEARCH_ID_OFFSETS = { Location: 8_000_000_000, Vendor: 5_000_000_000 };

  /** Compute the raw entity ID by stripping the search API offset */
  function getRawId(result) {
    const offset = SEARCH_ID_OFFSETS[result.Type];
    return offset ? result.Id - offset : null;
  }

  // Build flat list for keyboard navigation
  $: categorizedResults = categorizeResults(searchResults);
  $: {
    flatResults = [];
    for (const category of Object.keys(categorizedResults)) {
      for (const result of categorizedResults[category]) {
        flatResults.push({
          ...result,
          _category: category,
          _url: getTypeLink(result.Name, result.Type, result.SubType, getRawId(result))
        });
      }
    }
    // Don't auto-select — let user explicitly choose with arrow keys
    highlightedIndex = -1;
  }

  async function performSearch() {
    // Only run on client side
    if (!browser) return;

    if (value.length < 2) {
      searchResults = [];
      showResults = false;
      return;
    }

    isSearching = true;
    showResults = true;

    try {
      const base = apiPrefix ? import.meta.env.VITE_API_URL : '';
      const response = await fetch(base + `${endpoint}?query=${encodeURIComponent(value)}&fuzzy=true`);
      const data = await response.json();
      // Ensure data is an array before processing
      const resultsArray = Array.isArray(data) ? data : [];
      searchResults = rankSearchResults(resultsArray, value);
    } catch (err) {
      console.error('Search failed:', err);
      searchResults = [];
    } finally {
      isSearching = false;
    }
  }

  function handleInput(event) {
    // Strip game client brackets from pasted names like "[Item Name]"
    let raw = event.target.value;
    const cleaned = raw.replace(/^\[/, '').replace(/\]$/, '');
    if (cleaned !== raw) {
      event.target.value = cleaned;
    }
    value = cleaned;
    highlightedIndex = -1;
    hasUsedArrowKeys = false;

    if (searchTimeout) clearTimeout(searchTimeout);

    if (value.length < 2) {
      searchResults = [];
      isSearching = false; // Reset spinner when value is too short
      // Keep results area open if showOnFocus is enabled, but don't hide otherwise
      if (!showOnFocus) {
        showResults = false;
      }
      return;
    }

    isSearching = true;
    showResults = true;
    searchTimeout = setTimeout(performSearch, debounceMs);
  }

  function handleKeydown(event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      if (hasUsedArrowKeys && highlightedIndex >= 0 && highlightedIndex < flatResults.length) {
        // Arrow key selection made — navigate to that result
        selectResult(flatResults[highlightedIndex]);
      } else if (value.trim().length >= 2) {
        // No arrow key selection — go to dedicated search page
        dispatch('search', { query: value });
        closeResults();
      }
      return;
    }

    if (!showResults || flatResults.length === 0) {
      if (event.key === 'Escape') {
        closeResults();
        dispatch('close');
      }
      return;
    }

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        hasUsedArrowKeys = true;
        highlightedIndex = Math.min(highlightedIndex + 1, flatResults.length - 1);
        scrollToHighlighted();
        break;

      case 'ArrowUp':
        event.preventDefault();
        hasUsedArrowKeys = true;
        highlightedIndex = Math.max(highlightedIndex - 1, 0);
        scrollToHighlighted();
        break;

      case 'Escape':
        event.preventDefault();
        closeResults();
        dispatch('close');
        break;

      case 'Tab':
        // Allow Tab to move focus away, but close results
        closeResults();
        break;
    }
  }

  function scrollToHighlighted() {
    // Scroll highlighted item into view
    const container = document.querySelector('.search-results-container');
    const highlighted = document.querySelector('.search-result-item.highlighted');
    if (container && highlighted) {
      highlighted.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  function selectResult(result) {
    dispatch('select', {
      id: result.Id,
      name: result.Name,
      type: result.Type,
      subType: result.SubType,
      url: result._url || getTypeLink(result.Name, result.Type, result.SubType, getRawId(result))
    });
    closeResults();
  }

  function closeResults() {
    showResults = false;
    highlightedIndex = -1;
  }

  function handleBlur() {
    // Delay to allow click on results
    setTimeout(() => {
      if (mode === 'dropdown' && !preventBlurClose) {
        closeResults();
      }
      preventBlurClose = false;
    }, 200);
  }

  function handleFocus() {
    if (showOnFocus) {
      // For mobile: show results area immediately on focus
      showResults = true;
    } else if (value.length >= 2 && searchResults.length > 0) {
      showResults = true;
    }
    dispatch('focus');
  }

  function handleResultClick(event, result) {
    // Only handle left-click - let middle/right click work naturally as links
    if (event.button === 0) {
      event.preventDefault();
      selectResult(result);
    }
  }

  function handleResultMouseEnter(index) {
    highlightedIndex = index;
  }

  function handleResultMouseDown(event) {
    // Prevent blur from closing results when middle-clicking or right-clicking
    // This keeps results open for opening multiple tabs or using context menu
    if (event.button === 1 || event.button === 2) {
      preventBlurClose = true;
    }
  }

  // Expose methods
  export function focus() {
    inputElement?.focus();
  }

  export function clear() {
    value = '';
    searchResults = [];
    showResults = false;
    highlightedIndex = -1;
  }
</script>

<div class="search-input-container {containerClass}" class:fullscreen-mode={mode === 'fullscreen'}>
  <div class="search-input-wrapper">
    <input
      bind:this={inputElement}
      type="text"
      class="search-input"
      class:fullscreen={mode === 'fullscreen'}
      {placeholder}
      {disabled}
      value={value}
      on:input={handleInput}
      on:keydown={handleKeydown}
      on:blur={handleBlur}
      on:focus={handleFocus}
      autocomplete="off"
      spellcheck="false"
    />
    {#if isSearching}
      <span class="search-spinner"></span>
    {/if}
  </div>

  {#if showResults}
    <div class="search-results-container" class:fullscreen={mode === 'fullscreen'}>
      {#if value.length < 2}
        <div class="search-prompt">Start typing to see results</div>
      {:else if isSearching && searchResults.length === 0}
        <div class="search-loading">Searching...</div>
      {:else if flatResults.length === 0 && !isSearching}
        <div class="search-empty">No results found for "{value}"</div>
      {:else}
        {#each Object.keys(categorizedResults) as category}
          <div class="search-category">{category}</div>
          {#each categorizedResults[category] as result, i}
            {@const globalIndex = flatResults.findIndex(r => r.Id === result.Id)}
            {@const resultUrl = getTypeLink(result.Name, result.Type, result.SubType, getRawId(result))}
            <a
              href={resultUrl}
              class="search-result-item"
              class:highlighted={globalIndex === highlightedIndex}
              on:mousedown={handleResultMouseDown}
              on:click={(e) => handleResultClick(e, result)}
              on:mouseenter={() => handleResultMouseEnter(globalIndex)}
            >
              <span class="search-result-name">{result.DisplayName || result.Name}</span>
              <span class="search-result-type">{getTypeName(result.Type)}</span>
            </a>
          {/each}
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .search-input-container {
    position: relative;
    width: 100%;
  }

  .search-input-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .search-input {
    width: 100%;
    font-size: 14px;
    padding: 8px 12px;
    padding-right: 32px;
    border-radius: 4px;
    border: 1px solid var(--border-color);
    background-color: var(--bg-color);
    color: var(--text-color);
    box-sizing: border-box;
  }

  .search-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .search-input.fullscreen {
    font-size: 16px;
    padding: 12px 16px;
    padding-right: 40px;
    border-radius: 8px;
    background-color: var(--secondary-color);
  }

  .search-spinner {
    position: absolute;
    right: 10px;
    width: 16px;
    height: 16px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .search-results-container {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    z-index: 100;
    max-height: 400px;
    overflow-y: auto;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    box-shadow: 0px 8px 16px rgba(0, 0, 0, 0.3);
    margin-top: 4px;
  }

  .search-results-container.fullscreen {
    position: relative;
    max-height: none;
    border: none;
    box-shadow: none;
    margin-top: 0;
    border-radius: 0;
  }

  .search-category {
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    color: var(--text-muted);
    background-color: var(--hover-color);
    border-bottom: 1px solid var(--border-color);
    letter-spacing: 0.5px;
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .search-result-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    cursor: pointer;
    border-bottom: 1px solid var(--border-color);
    transition: background-color 0.1s ease;
    text-decoration: none;
    color: inherit;
  }

  .search-result-item:last-child {
    border-bottom: none;
  }

  .search-result-item:visited {
    color: inherit;
  }

  .search-result-item:hover,
  .search-result-item.highlighted {
    background-color: var(--hover-color);
  }

  .search-result-item.highlighted {
    outline: 2px solid var(--accent-color);
    outline-offset: -2px;
  }

  .search-result-name {
    font-size: 14px;
    color: var(--text-color);
  }

  .search-result-type {
    font-size: 11px;
    color: var(--text-muted);
    padding: 2px 6px;
    background-color: var(--primary-color);
    border-radius: 3px;
    flex-shrink: 0;
    margin-left: 8px;
  }

  .search-loading,
  .search-empty,
  .search-prompt {
    padding: 16px;
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
  }

  /* Fullscreen mode adjustments */
  .fullscreen-mode .search-results-container {
    flex: 1;
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .search-result-item {
      padding: 14px 16px;
    }

    .search-category {
      padding: 12px 16px;
      font-size: 12px;
    }
  }
</style>
