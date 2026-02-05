<!--
  @component MobLootsEdit
  Array editor for mob loot drops.
  Supports item search autocomplete, maturity selection, and frequency dropdown.
  Following the editConfig pattern from mobs-legacy.
-->
<script>
  // @ts-nocheck
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';
  import { browser } from '$app/environment';
  import { tick, onMount, onDestroy } from 'svelte';

  /** @type {Array} Loots array from the mob */
  export let loots = [];

  /** @type {string} Field path for updateField */
  export let fieldPath = 'Loots';

  /** @type {Array} Available maturities from the current mob */
  export let maturities = [];

  /** @type {Array} All items for validation */
  export let allItems = [];

  // Frequency options (from legacy config)
  const FREQUENCY_OPTIONS = [
    'Always',
    'Very often',
    'Often',
    'Common',
    'Uncommon',
    'Rare',
    'Very rare',
    'Extremely rare'
  ];

  // Color mapping for frequencies
  const FREQUENCY_COLORS = {
    'Always': { bg: 'rgba(22, 163, 74, 0.25)', color: '#22c55e' },
    'Very often': { bg: 'rgba(34, 197, 94, 0.25)', color: '#4ade80' },
    'Often': { bg: 'rgba(101, 163, 13, 0.25)', color: '#84cc16' },
    'Common': { bg: 'rgba(202, 138, 4, 0.25)', color: '#eab308' },
    'Uncommon': { bg: 'rgba(234, 88, 12, 0.25)', color: '#f97316' },
    'Rare': { bg: 'rgba(220, 38, 38, 0.25)', color: '#ef4444' },
    'Very rare': { bg: 'rgba(190, 18, 60, 0.25)', color: '#f43f5e' },
    'Extremely rare': { bg: 'rgba(147, 51, 234, 0.25)', color: '#a855f7' }
  };

  // Item name lookup set for validation
  $: itemNamesSet = new Set((allItems || []).map(i => i.Name));

  // Search state per loot item
  let searchStates = {};
  let searchTimeouts = {};
  let inputRefs = {};
  let dropdownStyles = {};

  // === Loot Constructor ===
  function createLoot() {
    return {
      Item: {
        Name: ''
      },
      Maturity: {
        Name: maturities[0]?.Name || null
      },
      Frequency: 'Common',
      IsEvent: false
    };
  }

  // === CRUD Operations ===
  function addLoot() {
    const newLoot = createLoot();
    updateField(fieldPath, [...loots, newLoot]);
  }

  function removeLoot(index) {
    updateField(fieldPath, loots.filter((_, i) => i !== index));
    // Clean up search state
    delete searchStates[index];
    if (searchTimeouts[index]) clearTimeout(searchTimeouts[index]);
    delete searchTimeouts[index];
  }

  function updateLootField(index, field, value) {
    const newList = [...loots];
    const loot = newList[index];

    if (field === 'Item.Name') {
      if (!loot.Item) loot.Item = {};
      loot.Item.Name = value;
    } else if (field === 'Maturity.Name') {
      if (!loot.Maturity) loot.Maturity = {};
      loot.Maturity.Name = value;
    } else {
      loot[field] = value;
    }

    updateField(fieldPath, newList);
  }

  // Validate item name against items list
  function isValidItem(itemName) {
    if (!itemName) return false;
    return itemNamesSet.has(itemName);
  }

  function getFrequencyStyle(frequency) {
    const style = FREQUENCY_COLORS[frequency] || { bg: 'var(--hover-color)', color: 'var(--text-muted)' };
    return `background-color: ${style.bg}; color: ${style.color};`;
  }

  // === Search Functions ===
  function getSearchState(index) {
    if (!searchStates[index]) {
      searchStates[index] = {
        query: '',
        results: [],
        isSearching: false,
        showResults: false,
        highlightedIndex: -1
      };
    }
    return searchStates[index];
  }

  function updateDropdownPosition(index) {
    const input = inputRefs[index];
    if (!input) return;
    const rect = input.getBoundingClientRect();
    const top = Math.round(rect.bottom + 2);
    const left = Math.round(rect.left);
    const width = Math.round(rect.width);
    dropdownStyles[index] = `position: fixed; top: ${top}px; left: ${left}px; width: ${width}px;`;
    dropdownStyles = dropdownStyles;
  }

  function updateOpenDropdowns() {
    Object.keys(searchStates).forEach((key) => {
      const idx = Number(key);
      if (searchStates[idx]?.showResults) {
        updateDropdownPosition(idx);
      }
    });
  }

  function handleViewportChange() {
    updateOpenDropdowns();
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
  });

  async function performSearch(index, query) {
    if (!browser || query.length < 2) {
      searchStates[index] = {
        ...getSearchState(index),
        results: [],
        isSearching: false,
        showResults: query.length >= 2
      };
      searchStates = searchStates;
      return;
    }

    searchStates[index] = {
      ...getSearchState(index),
      isSearching: true,
      showResults: true
    };
    searchStates = searchStates;

    try {
      const response = await fetch(
        import.meta.env.VITE_API_URL + `/search/items?query=${encodeURIComponent(query)}&fuzzy=true&limit=10`
      );
      const data = await response.json();

      searchStates[index] = {
        ...getSearchState(index),
        results: data || [],
        isSearching: false,
        highlightedIndex: data?.length > 0 ? 0 : -1
      };
      searchStates = searchStates;
      tick().then(() => updateDropdownPosition(index));
    } catch (err) {
      console.error('Item search failed:', err);
      searchStates[index] = {
        ...getSearchState(index),
        results: [],
        isSearching: false
      };
      searchStates = searchStates;
    }
  }

  function handleSearchInput(index, event) {
    const query = event.target.value;
    updateLootField(index, 'Item.Name', query);

    // Clear previous timeout
    if (searchTimeouts[index]) clearTimeout(searchTimeouts[index]);

    // Debounce search
    searchTimeouts[index] = setTimeout(() => {
      performSearch(index, query);
    }, 250);
  }

  function handleSearchKeydown(index, event) {
    const state = getSearchState(index);
    if (!state.showResults || state.results.length === 0) {
      if (event.key === 'Escape') {
        closeSearch(index);
      }
      return;
    }

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        searchStates[index] = {
          ...state,
          highlightedIndex: Math.min(state.highlightedIndex + 1, state.results.length - 1)
        };
        searchStates = searchStates;
        break;

      case 'ArrowUp':
        event.preventDefault();
        searchStates[index] = {
          ...state,
          highlightedIndex: Math.max(state.highlightedIndex - 1, 0)
        };
        searchStates = searchStates;
        break;

      case 'Enter':
        event.preventDefault();
        if (state.highlightedIndex >= 0 && state.highlightedIndex < state.results.length) {
          selectSearchResult(index, state.results[state.highlightedIndex]);
        }
        break;

      case 'Escape':
        event.preventDefault();
        closeSearch(index);
        break;

      case 'Tab':
        closeSearch(index);
        break;
    }
  }

  function selectSearchResult(index, result) {
    updateLootField(index, 'Item.Name', result.Name);
    closeSearch(index);
  }

  function closeSearch(index) {
    searchStates[index] = {
      ...getSearchState(index),
      showResults: false,
      highlightedIndex: -1
    };
    searchStates = searchStates;
  }

  function handleSearchBlur(index) {
    // Delay to allow click on results
    setTimeout(() => {
      closeSearch(index);
    }, 200);
  }

  function handleSearchFocus(index) {
    const state = getSearchState(index);
    const currentValue = loots[index]?.Item?.Name || '';
    if (currentValue.length >= 2 && state.results.length > 0) {
      searchStates[index] = { ...state, showResults: true };
      searchStates = searchStates;
      tick().then(() => updateDropdownPosition(index));
    }
  }

  function handleResultClick(index, result) {
    selectSearchResult(index, result);
  }

  function handleResultMouseEnter(index, resultIndex) {
    searchStates[index] = {
      ...getSearchState(index),
      highlightedIndex: resultIndex
    };
    searchStates = searchStates;
  }
</script>

<div class="loots-edit">
  <div class="section-header">
    <h4 class="section-title">Loots ({loots?.length || 0})</h4>
  </div>

  <div class="loots-list">
    {#each loots as loot, index (index)}
      <div class="loot-item" class:invalid-item={loot.Item?.Name && !isValidItem(loot.Item.Name)}>
        <div class="loot-fields">
          <div class="field item-field">
            <span class="field-label">Item Name</span>
            <div class="search-wrapper">
              <div class="input-with-validation">
                <input
                  bind:this={inputRefs[index]}
                  type="text"
                  value={loot.Item?.Name || ''}
                  on:input={(e) => handleSearchInput(index, e)}
                  on:keydown={(e) => handleSearchKeydown(index, e)}
                  on:blur={() => handleSearchBlur(index)}
                  on:focus={() => handleSearchFocus(index)}
                  placeholder="Search item..."
                  class:invalid={loot.Item?.Name && !isValidItem(loot.Item.Name)}
                  autocomplete="off"
                  spellcheck="false"
                />
                {#if searchStates[index]?.isSearching}
                  <span class="search-spinner"></span>
                {:else if loot.Item?.Name && !isValidItem(loot.Item.Name)}
                  <span class="validation-icon" title="Item not found in database">⚠</span>
                {:else if loot.Item?.Name && isValidItem(loot.Item.Name)}
                  <span class="validation-icon valid" title="Valid item">✓</span>
                {/if}
              </div>

              {#if searchStates[index]?.showResults}
                <div class="search-dropdown" style={dropdownStyles[index]}>
                  {#if searchStates[index]?.isSearching}
                    <div class="search-status">Searching...</div>
                  {:else if !searchStates[index]?.results?.length}
                    <div class="search-status">No items found</div>
                  {:else}
                    {#each searchStates[index].results as result, resultIndex}
                      <!-- svelte-ignore a11y-click-events-have-key-events -->
                      <!-- svelte-ignore a11y-no-static-element-interactions -->
                      <div
                        class="search-result"
                        class:highlighted={resultIndex === searchStates[index]?.highlightedIndex}
                        on:click={() => handleResultClick(index, result)}
                        on:mouseenter={() => handleResultMouseEnter(index, resultIndex)}
                      >
                        <span class="result-name">{result.Name}</span>
                      </div>
                    {/each}
                  {/if}
                </div>
              {/if}
            </div>
          </div>

          <label class="field">
            <span class="field-label">Least Maturity</span>
            <select
              value={loot.Maturity?.Name || ''}
              on:change={(e) => updateLootField(index, 'Maturity.Name', e.target.value)}
            >
              <option value="">-- Any --</option>
              {#each maturities as mat}
                <option value={mat.Name}>{mat.Name}</option>
              {/each}
            </select>
          </label>

          <label class="field">
            <span class="field-label">Frequency</span>
            <select
              value={loot.Frequency || 'Common'}
              on:change={(e) => updateLootField(index, 'Frequency', e.target.value)}
              style={getFrequencyStyle(loot.Frequency)}
            >
              {#each FREQUENCY_OPTIONS as freq}
                <option value={freq}>{freq}</option>
              {/each}
            </select>
          </label>

          <label class="field checkbox-field">
            <input
              type="checkbox"
              checked={loot.IsEvent || false}
              on:change={(e) => updateLootField(index, 'IsEvent', e.target.checked)}
            />
            <span class="field-label">Event</span>
          </label>
        </div>

        <button
          class="btn-icon danger"
          on:click={() => removeLoot(index)}
          title="Remove loot"
          type="button"
        >×</button>
      </div>
    {/each}

    <button class="btn-add" on:click={addLoot} type="button">
      <span>+</span> Add Loot
    </button>
  </div>
</div>

<style>
  .loots-edit {
    width: 100%;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .section-title {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  .loots-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .loot-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
  }

  .loot-item.invalid-item {
    border-color: var(--warning-color, #fbbf24);
    background-color: rgba(251, 191, 36, 0.05);
  }

  .loot-fields {
    display: flex;
    gap: 6px;
    flex: 1;
    flex-wrap: wrap;
    align-items: flex-end;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }

  .field.item-field {
    flex: 2;
    min-width: 140px;
    max-width: 220px;
  }

  .field:not(.item-field):not(.checkbox-field) {
    flex: 1;
    min-width: 90px;
    max-width: 130px;
  }

  .field-label {
    font-size: 12px;
    color: var(--text-muted, #999);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .field input[type="text"],
  .field select {
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

  .field select option {
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
  }

  .field input:focus,
  .field select:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .field input.invalid {
    border-color: var(--warning-color, #fbbf24);
  }

  .checkbox-field {
    flex-direction: row;
    align-items: center;
    gap: 4px;
    min-width: auto;
    flex: 0 0 auto;
    height: 28px;
    margin-top: auto;
  }

  .checkbox-field .field-label {
    margin-top: 0;
  }

  .checkbox-field input[type="checkbox"] {
    width: 14px;
    height: 14px;
    cursor: pointer;
    flex-shrink: 0;
  }

  /* Search wrapper and dropdown */
  .search-wrapper {
    position: relative;
    width: 100%;
  }

  .input-with-validation {
    position: relative;
    display: flex;
    align-items: center;
  }

  .input-with-validation input {
    padding-right: 26px;
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

  .validation-icon {
    position: absolute;
    right: 6px;
    font-size: 12px;
    color: var(--warning-color, #fbbf24);
  }

  .validation-icon.valid {
    color: var(--success-color, #22c55e);
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

  /* Buttons */
  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    background: none;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .btn-icon:hover:not(:disabled) {
    background-color: var(--hover-color);
    color: var(--text-color);
    border-color: var(--text-color);
  }

  .btn-icon.danger:hover:not(:disabled) {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  .btn-add {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 8px 12px;
    font-size: 12px;
    line-height: 1;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    color: var(--text-muted, #999);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s;
    margin-top: 4px;
  }

  .btn-add:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
    background-color: var(--hover-color);
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .loot-item {
      flex-direction: column;
      align-items: stretch;
      gap: 6px;
    }

    .loot-fields {
      flex-direction: column;
      align-items: stretch;
    }

    .field,
    .field.item-field,
    .field:not(.item-field):not(.checkbox-field) {
      max-width: none;
      width: 100%;
    }

    .checkbox-field {
      align-self: flex-start;
    }

    .btn-icon {
      align-self: flex-end;
    }
  }
</style>
