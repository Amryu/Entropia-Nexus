<!--
  @component LocalSearchInput
  Searchable input for local option lists (MobLoots-style dropdown).
  Emits:
  - change: { value }
  - select: { value, option }
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher, onMount, onDestroy, tick } from 'svelte';

  export let value = '';
  export let placeholder = 'Search...';
  export let options = []; // array of strings or objects with { label, value }
  export let limit = 10;
  export let disabled = false;

  const dispatch = createEventDispatcher();

  let localValue = value || '';
  let results = [];
  let showResults = false;
  let highlightedIndex = -1;
  let inputEl;
  let dropdownStyle = '';

  $: localValue = value ?? '';
  $: if (showResults) {
    tick().then(updateDropdownPosition);
  }

  function normalizeOptions(list) {
    return (list || []).map(opt => {
      if (typeof opt === 'string') {
        return { label: opt, value: opt };
      }
      return { label: opt?.label ?? opt?.value ?? '', value: opt?.value ?? opt?.label ?? '' };
    });
  }

  function filterResults(query) {
    const q = query.trim().toLowerCase();
    const normalized = normalizeOptions(options);
    if (!q) return normalized.slice(0, limit);
    return normalized
      .filter(opt => opt.label.toLowerCase().includes(q) || opt.value.toLowerCase().includes(q))
      .slice(0, limit);
  }

  function handleInput(event) {
    const query = event.target.value;
    localValue = query;
    dispatch('change', { value: query });

    results = filterResults(query);
    showResults = true;
    highlightedIndex = results.length > 0 ? 0 : -1;
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

  function selectResult(option) {
    localValue = option?.value || '';
    dispatch('change', { value: localValue });
    dispatch('select', { value: localValue, option });
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
    results = filterResults(localValue);
    showResults = true;
    highlightedIndex = results.length > 0 ? 0 : -1;
  }
</script>

<div class="local-search">
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

  {#if showResults}
    <div class="search-dropdown" style={dropdownStyle}>
      {#if !results.length}
        <div class="search-status">No matches</div>
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
            <span class="result-name">{result.label}</span>
          </div>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .local-search {
    position: relative;
    width: 100%;
  }

  .local-search input {
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

  .local-search input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .local-search input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
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
