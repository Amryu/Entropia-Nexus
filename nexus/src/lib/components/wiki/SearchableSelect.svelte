<!--
  @component SearchableSelect
  A searchable dropdown component for selecting from a list of options.

  Features:
  - Type to filter options
  - Keyboard navigation (up/down arrows, Enter to select, Escape to close)
  - Proper dropdown positioning
  - Supports both value/label options

  @example
  <SearchableSelect
    value={selectedValue}
    options={[{ value: 'a', label: 'Option A' }, { value: 'b', label: 'Option B' }]}
    placeholder="Search..."
    on:change={(e) => handleChange(e.detail.value)}
  />
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher, onMount, tick } from 'svelte';

  const dispatch = createEventDispatcher();

  /** @type {string} Current selected value */
  export let value = '';

  /** @type {Array<{value: string, label: string}>} Options to select from */
  export let options = [];

  /** @type {string} Placeholder text */
  export let placeholder = 'Search...';

  /** @type {boolean} Whether the component is disabled */
  export let disabled = false;

  /** @type {string} Additional CSS class */
  export let className = '';

  // Internal state
  let inputElement;
  let containerElement;
  let searchQuery = '';
  let isOpen = false;
  let highlightedIndex = -1;

  // Get display value from current value
  $: displayValue = options.find(o => o.value === value)?.label || value || '';

  // Filter options based on search query
  $: filteredOptions = searchQuery
    ? options.filter(o =>
        o.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
        o.value.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : options;

  // Reset highlight when filtered options change
  $: if (filteredOptions) {
    highlightedIndex = filteredOptions.length > 0 ? 0 : -1;
  }

  function openDropdown() {
    if (disabled) return;
    isOpen = true;
    searchQuery = '';
    highlightedIndex = filteredOptions.length > 0 ? 0 : -1;
    tick().then(() => inputElement?.focus());
  }

  function closeDropdown() {
    isOpen = false;
    searchQuery = '';
    highlightedIndex = -1;
  }

  function selectOption(option) {
    value = option.value;
    dispatch('change', { value: option.value, label: option.label });
    closeDropdown();
  }

  function handleInput(event) {
    searchQuery = event.target.value;
  }

  function handleKeydown(event) {
    if (!isOpen) {
      if (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown') {
        event.preventDefault();
        openDropdown();
      }
      return;
    }

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        highlightedIndex = Math.min(highlightedIndex + 1, filteredOptions.length - 1);
        scrollToHighlighted();
        break;

      case 'ArrowUp':
        event.preventDefault();
        highlightedIndex = Math.max(highlightedIndex - 1, 0);
        scrollToHighlighted();
        break;

      case 'Enter':
        event.preventDefault();
        if (highlightedIndex >= 0 && highlightedIndex < filteredOptions.length) {
          selectOption(filteredOptions[highlightedIndex]);
        }
        break;

      case 'Escape':
        event.preventDefault();
        closeDropdown();
        break;

      case 'Tab':
        closeDropdown();
        break;
    }
  }

  function scrollToHighlighted() {
    tick().then(() => {
      const container = containerElement?.querySelector('.searchable-select-dropdown');
      const highlighted = container?.querySelector('.option-item.highlighted');
      if (container && highlighted) {
        highlighted.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    });
  }

  function handleBlur(event) {
    // Delay to allow click on options
    setTimeout(() => {
      // Check if focus is still within our component
      if (!containerElement?.contains(document.activeElement)) {
        closeDropdown();
      }
    }, 150);
  }

  function handleOptionClick(option) {
    selectOption(option);
  }

  function handleOptionMouseEnter(index) {
    highlightedIndex = index;
  }

  function handleContainerClick(event) {
    if (!isOpen) {
      openDropdown();
    }
  }
</script>

<div
  class="searchable-select {className}"
  class:open={isOpen}
  class:disabled
  bind:this={containerElement}
>
  {#if isOpen}
    <input
      bind:this={inputElement}
      type="text"
      class="searchable-select-input"
      value={searchQuery}
      {placeholder}
      on:input={handleInput}
      on:keydown={handleKeydown}
      on:blur={handleBlur}
      autocomplete="off"
      spellcheck="false"
    />
  {:else}
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div
      class="searchable-select-display"
      on:click={handleContainerClick}
      on:keydown={handleKeydown}
      tabindex={disabled ? -1 : 0}
    >
      <span class="display-text" class:placeholder={!displayValue}>
        {displayValue || placeholder}
      </span>
      <span class="dropdown-arrow">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6,9 12,15 18,9"></polyline>
        </svg>
      </span>
    </div>
  {/if}

  {#if isOpen}
    <div class="searchable-select-dropdown">
      {#if filteredOptions.length === 0}
        <div class="no-options">No matches found</div>
      {:else}
        {#each filteredOptions as option, index}
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div
            class="option-item"
            class:highlighted={index === highlightedIndex}
            class:selected={option.value === value}
            on:click={() => handleOptionClick(option)}
            on:mouseenter={() => handleOptionMouseEnter(index)}
          >
            {option.label}
          </div>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .searchable-select {
    position: relative;
    display: inline-block;
    min-width: 120px;
  }

  .searchable-select.disabled {
    opacity: 0.6;
    pointer-events: none;
  }

  .searchable-select-display {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 4px 8px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    cursor: pointer;
    min-height: 28px;
  }

  .searchable-select-display:hover {
    border-color: var(--accent-color, #4a9eff);
  }

  .searchable-select-display:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .display-text {
    font-size: 13px;
    color: var(--text-color);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .display-text.placeholder {
    color: var(--text-muted, #999);
  }

  .dropdown-arrow {
    display: flex;
    align-items: center;
    color: var(--text-muted, #999);
    flex-shrink: 0;
  }

  .searchable-select-input {
    width: 100%;
    padding: 4px 8px;
    font-size: 13px;
    background-color: var(--bg-secondary, var(--secondary-color));
    border: 1px solid var(--accent-color, #4a9eff);
    border-radius: 4px;
    color: var(--text-color);
    min-height: 28px;
  }

  .searchable-select-input:focus {
    outline: none;
  }

  .searchable-select-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    z-index: 100;
    max-height: 200px;
    overflow-y: auto;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.3);
    margin-top: 4px;
  }

  .option-item {
    padding: 8px 12px;
    font-size: 13px;
    color: var(--text-color);
    cursor: pointer;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .option-item:last-child {
    border-bottom: none;
  }

  .option-item:hover,
  .option-item.highlighted {
    background-color: var(--hover-color);
  }

  .option-item.highlighted {
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: -2px;
  }

  .option-item.selected {
    background-color: rgba(74, 158, 255, 0.1);
    font-weight: 500;
  }

  .no-options {
    padding: 12px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 13px;
  }
</style>
