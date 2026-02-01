<!--
  @component MobSearchInput
  Lightweight searchable input for selecting mobs from a provided list.
  Emits:
  - change: { value }
  - select: { value, mob }
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';

  export let value = '';
  export let placeholder = 'Search mob...';
  export let options = []; // array of mob objects with Name
  export let limit = 10;
  export let disabled = false;

  const dispatch = createEventDispatcher();

  let localValue = value || '';
  let results = [];
  let showResults = false;
  let highlightedIndex = -1;

  $: localValue = value ?? '';

  function filterResults(query) {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return (options || [])
      .filter(m => m?.Name?.toLowerCase().includes(q))
      .slice(0, limit);
  }

  function handleInput(event) {
    const query = event.target.value;
    localValue = query;
    dispatch('change', { value: query });

    results = filterResults(query);
    showResults = query.length > 0;
    highlightedIndex = results.length > 0 ? 0 : -1;
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

  function selectResult(mob) {
    localValue = mob?.Name || '';
    dispatch('change', { value: localValue });
    dispatch('select', { value: localValue, mob });
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
    if (localValue.length > 0 && results.length > 0) {
      showResults = true;
    }
  }
</script>

<div class="mob-search">
  <input
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
    <div class="search-dropdown">
      {#if !results.length}
        <div class="search-status">No mobs found</div>
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
  .mob-search {
    position: relative;
    width: 100%;
  }

  .mob-search input {
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

  .mob-search input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .mob-search input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .search-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    z-index: 100;
    max-height: 200px;
    overflow-y: auto;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.3);
    margin-top: 2px;
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
