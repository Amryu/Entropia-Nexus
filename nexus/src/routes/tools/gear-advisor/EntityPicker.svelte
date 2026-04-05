<!--
  @component EntityPicker
  Minimal search-dropdown for picking an entity from a pre-loaded list.
  Used by Gear Advisor tools for armor / plating / mob selection.
-->
<script>
  // @ts-nocheck
  import { scoreSearchResult } from '$lib/search.js';

  let {
    entities = [],
    selected = null,
    placeholder = 'Search...',
    clearable = true,
    onselect = () => {},
    onclear = () => {}
  } = $props();

  let query = $state('');
  let isOpen = $state(false);
  let highlighted = $state(-1);
  let inputEl = $state();

  // Keep the input text in sync with the current selection when not actively typing
  $effect(() => {
    if (!isOpen && selected) {
      query = selected.Name || '';
    } else if (!isOpen && !selected) {
      query = '';
    }
  });

  let filtered = $derived.by(() => {
    const q = query.trim();
    const list = entities || [];
    if (!q) return list.slice(0, 20);
    // Fuzzy score against each entity's name; keep matches and sort desc
    const scored = [];
    for (const e of list) {
      const score = scoreSearchResult(e?.Name || '', q);
      if (score > 0) scored.push({ e, score });
    }
    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, 20).map(x => x.e);
  });

  function pick(item) {
    onselect(item);
    query = item?.Name || '';
    isOpen = false;
    highlighted = -1;
    inputEl?.blur();
  }

  function clearSelection() {
    onclear();
    query = '';
    isOpen = false;
    highlighted = -1;
    inputEl?.focus();
  }

  function handleKeydown(e) {
    if (!isOpen && (e.key === 'ArrowDown' || e.key === 'Enter')) {
      isOpen = true;
      return;
    }
    if (!isOpen) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      highlighted = Math.min(highlighted + 1, filtered.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      highlighted = Math.max(highlighted - 1, 0);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlighted >= 0 && filtered[highlighted]) {
        pick(filtered[highlighted]);
      } else if (filtered.length > 0) {
        pick(filtered[0]);
      }
    } else if (e.key === 'Escape') {
      isOpen = false;
      highlighted = -1;
      inputEl?.blur();
    }
  }
</script>

<div class="entity-picker">
  <div class="picker-input-wrap">
    <input
      bind:this={inputEl}
      type="text"
      bind:value={query}
      {placeholder}
      onfocus={() => { isOpen = true; }}
      onblur={() => setTimeout(() => { isOpen = false; }, 150)}
      oninput={() => { isOpen = true; highlighted = -1; }}
      onkeydown={handleKeydown}
      class="picker-input"
    />
    {#if clearable && selected}
      <button
        type="button"
        class="picker-clear"
        onmousedown={(e) => { e.preventDefault(); clearSelection(); }}
        title="Clear"
        aria-label="Clear selection"
      >×</button>
    {/if}
  </div>

  {#if isOpen && filtered.length > 0}
    <ul class="picker-dropdown" role="listbox">
      {#each filtered as item, i (item.Id ?? item.Name)}
        <li>
          <button
            type="button"
            class="picker-option"
            class:highlighted={i === highlighted}
            class:selected={selected && (selected.Id === item.Id || selected.Name === item.Name)}
            onmousedown={(e) => { e.preventDefault(); pick(item); }}
            onmouseenter={() => { highlighted = i; }}
          >
            {item.Name}
          </button>
        </li>
      {/each}
    </ul>
  {:else if isOpen && query.trim() && filtered.length === 0}
    <div class="picker-empty">No matches</div>
  {/if}
</div>

<style>
  .entity-picker {
    position: relative;
    width: 100%;
  }

  .picker-input-wrap {
    position: relative;
  }

  .picker-input {
    width: 100%;
    padding: 8px 30px 8px 10px;
    font-size: 13px;
    background-color: var(--bg-color, var(--secondary-color));
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
    box-sizing: border-box;
  }

  .picker-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .picker-clear {
    position: absolute;
    right: 6px;
    top: 50%;
    transform: translateY(-50%);
    width: 20px;
    height: 20px;
    padding: 0;
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 18px;
    line-height: 1;
    cursor: pointer;
    border-radius: 3px;
  }

  .picker-clear:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .picker-dropdown {
    position: absolute;
    top: calc(100% + 2px);
    left: 0;
    right: 0;
    max-height: 220px;
    overflow-y: auto;
    margin: 0;
    padding: 4px 0;
    list-style: none;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    z-index: 50;
  }

  .picker-dropdown li {
    margin: 0;
  }

  .picker-option {
    display: block;
    width: 100%;
    padding: 6px 10px;
    font-size: 13px;
    text-align: left;
    background: transparent;
    border: none;
    color: var(--text-color);
    cursor: pointer;
  }

  .picker-option:hover,
  .picker-option.highlighted {
    background-color: var(--hover-color);
  }

  .picker-option.selected {
    color: var(--accent-color);
    font-weight: 500;
  }

  .picker-empty {
    position: absolute;
    top: calc(100% + 2px);
    left: 0;
    right: 0;
    padding: 8px 10px;
    font-size: 12px;
    color: var(--text-muted);
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    z-index: 50;
  }
</style>
