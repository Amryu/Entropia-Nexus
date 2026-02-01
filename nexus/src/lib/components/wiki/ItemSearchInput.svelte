<!--
  @component ItemSearchInput
  Searchable item input using the MobLoots search pattern.
  Emits:
  - change: { value }
  - select: { value, item }
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher, onMount, onDestroy, tick } from 'svelte';
  import { browser } from '$app/environment';

  export let value = '';
  export let placeholder = 'Search item...';
  export let limit = 10;
  export let fuzzy = true;
  export let disabled = false;
  export let allowedTypes = null; // array of item Types
  export let allowedNames = null; // array of item Names

  const dispatch = createEventDispatcher();

  let localValue = value || '';
  let results = [];
  let isSearching = false;
  let showResults = false;
  let highlightedIndex = -1;
  let searchTimeout;
  let inputEl;
  let dropdownStyle = '';

  $: localValue = value ?? '';
  $: if (showResults) {
    tick().then(updateDropdownPosition);
  }

  function filterResults(items) {
    let filtered = items || [];
    if (Array.isArray(allowedTypes) && allowedTypes.length > 0) {
      filtered = filtered.filter(item => {
        const itemType = item?.Properties?.Type ?? item?.Type ?? item?.t;
        return allowedTypes.includes(itemType);
      });
    }
    if (Array.isArray(allowedNames) && allowedNames.length > 0) {
      const nameSet = new Set(allowedNames);
      filtered = filtered.filter(item => nameSet.has(item?.Name));
    }
    return filtered;
  }

  async function performSearch(query) {
    if (query.length < 2) {
      results = [];
      isSearching = false;
      showResults = query.length >= 2;
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
      const response = await fetch(
        import.meta.env.VITE_API_URL + `/search/items?query=${encodeURIComponent(query)}&fuzzy=${fuzzy ? 'true' : 'false'}&limit=${limit}`
      );
      const data = await response.json();
      const filtered = filterResults(data || []);
      results = filtered;
      highlightedIndex = filtered.length > 0 ? 0 : -1;
    } catch (err) {
      results = [];
      highlightedIndex = -1;
    } finally {
      isSearching = false;
    }
  }

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
    window.addEventListener('scroll', handleViewportChange, true);
    window.addEventListener('resize', handleViewportChange);
  });

  onDestroy(() => {
    window.removeEventListener('scroll', handleViewportChange, true);
    window.removeEventListener('resize', handleViewportChange);
  });

  function handleInput(event) {
    const query = event.target.value;
    localValue = query;
    dispatch('change', { value: query });

    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => performSearch(query), 250);
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
    localValue = item?.Name || '';
    dispatch('change', { value: localValue });
    dispatch('select', { value: localValue, item });
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
    if (localValue.length >= 2 && results.length > 0) {
      showResults = true;
    }
  }
</script>

<div class="item-search">
  <div class="input-with-validation">
    <input
      bind:this={inputEl}
      type="text"
      value={localValue}
      on:input={handleInput}
      on:keydown={handleKeydown}
      on:blur={handleBlur}
      on:focus={handleFocus}
      placeholder={placeholder}
      autocomplete="off"
      spellcheck="false"
      disabled={disabled}
    />
    {#if isSearching}
      <span class="search-spinner"></span>
    {/if}
  </div>

  {#if showResults}
    <div class="search-dropdown" style={dropdownStyle}>
      {#if isSearching}
        <div class="search-status">Searching...</div>
      {:else if !results.length}
        <div class="search-status">No items found</div>
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
            <span class="result-name">{result.Name}</span>
          </div>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .item-search {
    position: relative;
    width: 100%;
  }

  .input-with-validation {
    position: relative;
    display: flex;
    align-items: center;
  }

  .input-with-validation input {
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

  .input-with-validation input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .input-with-validation input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
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
