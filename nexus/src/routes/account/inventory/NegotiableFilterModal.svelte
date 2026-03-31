<script>
  //@ts-nocheck
  import { getTopCategory, itemTypeBadge } from '../../market/exchange/orderUtils';

  /**
   * @typedef {Object} Props
   * @property {boolean} [show]
   * @property {object|null} [node] - The container tree node being configured
   * @property {Array} [items] - All inventory items within this container
   * @property {Map} [itemLookup] - item_id → slim item
   * @property {object|null} [existingFilter] - Current filter config for this node
   * @property {() => void} [onclose]
   * @property {(filter: object|null) => void} [onsave]
   */

  /** @type {Props} */
  let {
    show = false,
    node = null,
    items = [],
    itemLookup = new Map(),
    existingFilter = null,
    onclose,
    onsave,
  } = $props();

  const ALL_CATEGORIES = [
    'Weapons', 'Armor', 'Tools', 'Enhancers', 'Clothes',
    'Blueprints', 'Materials', 'Consumables', 'Vehicles', 'Pets',
    'Skill Implants', 'Furnishings', 'Strongboxes', 'Other'
  ];

  let mode = $state('all'); // 'all' | 'whitelist' | 'blacklist' | 'match'
  let selectedIds = $state(new Set());
  let substring = $state('');
  let useRegex = $state(false);
  let negateMatch = $state(false);
  let selectedTypes = $state(new Set());
  let searchTerm = $state('');
  let regexError = $state(null);

  // Initialize from existing filter when modal opens
  $effect(() => {
    if (show) {
      if (!existingFilter) {
        mode = 'all';
        selectedIds = new Set();
        substring = '';
        useRegex = false;
        selectedTypes = new Set();
      } else {
        mode = existingFilter.mode || 'all';
        if (mode === 'whitelist' || mode === 'blacklist') {
          selectedIds = new Set(existingFilter.itemIds || []);
        } else {
          selectedIds = new Set();
        }
        if (mode === 'match') {
          substring = existingFilter.substring || '';
          useRegex = !!existingFilter.useRegex;
          negateMatch = !!existingFilter.negate;
          selectedTypes = new Set(existingFilter.itemTypes || []);
        } else {
          substring = '';
          useRegex = false;
          negateMatch = false;
          selectedTypes = new Set();
        }
      }
      searchTerm = '';
      regexError = null;
    }
  });

  // Deduplicated items for the list (unique by item_id)
  let uniqueItems = $derived((() => {
    const seen = new Map();
    for (const item of items) {
      if (!item.item_id || item.item_id === 0) continue;
      const slim = itemLookup.get(item.item_id);
      if (slim?.ut) continue; // skip untradeable items
      if (!seen.has(item.item_id)) {
        seen.set(item.item_id, {
          item_id: item.item_id,
          item_name: slim?.n || item.item_name,
          type: slim?.t || null,
          category: getTopCategory(slim?.t),
          quantity: item.quantity || 1,
        });
      } else {
        // Accumulate quantity for stackables
        seen.get(item.item_id).quantity += (item.quantity || 1);
      }
    }
    return [...seen.values()].sort((a, b) => a.item_name.localeCompare(b.item_name));
  })());

  // Filter the list by search
  let filteredItems = $derived((() => {
    if (!searchTerm) return uniqueItems;
    const lower = searchTerm.toLowerCase();
    return uniqueItems.filter(i => i.item_name.toLowerCase().includes(lower));
  })());

  // Items matching the current filter criteria
  let matchedItems = $derived((() => {
    if (mode === 'all') return uniqueItems;
    if (mode === 'whitelist') return uniqueItems.filter(i => selectedIds.has(i.item_id));
    if (mode === 'blacklist') return uniqueItems.filter(i => !selectedIds.has(i.item_id));
    if (mode === 'match') {
      return uniqueItems.filter(item => {
        let nameMatch = true;
        if (substring) {
          if (useRegex) {
            try { nameMatch = new RegExp(substring, 'i').test(item.item_name); } catch { nameMatch = false; }
          } else {
            nameMatch = item.item_name.toLowerCase().includes(substring.toLowerCase());
          }
        }
        let typeMatch = true;
        if (selectedTypes.size > 0) {
          typeMatch = item.category ? selectedTypes.has(item.category) : false;
        }
        const result = nameMatch && typeMatch;
        return negateMatch ? !result : result;
      });
    }
    return [];
  })());

  let matchCount = $derived(matchedItems.length);

  // Validate regex
  $effect(() => {
    if (useRegex && substring) {
      try { new RegExp(substring); regexError = null; } catch (e) { regexError = e.message; }
    } else {
      regexError = null;
    }
  });

  function toggleId(id) {
    if (selectedIds.has(id)) {
      selectedIds.delete(id);
    } else {
      selectedIds.add(id);
    }
    selectedIds = new Set(selectedIds); // trigger reactivity
  }

  function toggleType(cat) {
    if (selectedTypes.has(cat)) {
      selectedTypes.delete(cat);
    } else {
      selectedTypes.add(cat);
    }
    selectedTypes = new Set(selectedTypes);
  }

  function save() {
    if (mode === 'all') {
      onsave?.(null);
    } else if (mode === 'whitelist' || mode === 'blacklist') {
      onsave?.({ mode, itemIds: [...selectedIds] });
    } else if (mode === 'match') {
      onsave?.({
        mode: 'match',
        substring: substring.replace(/[\x00-\x1f]/g, '').trim().slice(0, 200),
        useRegex,
        negate: negateMatch,
        itemTypes: [...selectedTypes],
      });
    }
  }
</script>

{#if show}
  <div
    class="filter-overlay"
    role="button"
    tabindex="-1"
    onclick={(e) => e.target === e.currentTarget && onclose?.()}
    onkeydown={(e) => e.key === 'Escape' && onclose?.()}
  >
    <div class="filter-modal">
      <div class="filter-header">
        <h4>Configure Filter</h4>
        <span class="filter-preview">{matchCount} item{matchCount !== 1 ? 's' : ''} will be listed</span>
        <button class="close-btn" onclick={() => onclose?.()}>&times;</button>
      </div>

      <div class="filter-body">
        <div class="mode-selector">
          <label class="mode-option">
            <input type="radio" bind:group={mode} value="all" />
            Include all items
          </label>
          <label class="mode-option">
            <input type="radio" bind:group={mode} value="whitelist" />
            Include specific items
          </label>
          <label class="mode-option">
            <input type="radio" bind:group={mode} value="blacklist" />
            Exclude specific items
          </label>
          <label class="mode-option">
            <input type="radio" bind:group={mode} value="match" />
            Match by pattern
          </label>
        </div>

        {#if mode === 'whitelist' || mode === 'blacklist'}
          <div class="item-list-section">
            <input
              type="text"
              class="search-input"
              placeholder="Search items..."
              bind:value={searchTerm}
            />
            <div class="item-list">
              {#each filteredItems as item (item.item_id)}
                <label class="item-row">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(item.item_id)}
                    onchange={() => toggleId(item.item_id)}
                  />
                  <span class="item-name">{item.item_name}</span>
                  {#if item.type}
                    <span class="item-type-badge">{item.category}</span>
                  {/if}
                  <span class="item-qty">x{item.quantity.toLocaleString()}</span>
                </label>
              {/each}
              {#if filteredItems.length === 0}
                <p class="empty-text">No items match your search</p>
              {/if}
            </div>
            <div class="selection-hint">
              {mode === 'whitelist' ? 'Checked items will be listed' : 'Checked items will be excluded'}
              ({selectedIds.size} selected)
            </div>
          </div>
        {:else if mode === 'match'}
          <div class="match-section">
            <div class="match-row">
              <label class="match-label">
                Pattern
                <input
                  type="text"
                  class="match-input"
                  placeholder="Enter substring or regex..."
                  bind:value={substring}
                  maxlength="200"
                />
              </label>
              <label class="regex-toggle">
                <input type="checkbox" bind:checked={useRegex} />
                Regex
              </label>
              <label class="regex-toggle">
                <input type="checkbox" bind:checked={negateMatch} />
                Negate
              </label>
            </div>
            {#if regexError}
              <p class="error-text">{regexError}</p>
            {/if}

            <div class="type-filters">
              <span class="type-label">Item types:</span>
              <div class="type-grid">
                {#each ALL_CATEGORIES as cat}
                  <label class="type-chip" class:active={selectedTypes.has(cat)}>
                    <input
                      type="checkbox"
                      checked={selectedTypes.has(cat)}
                      onchange={() => toggleType(cat)}
                    />
                    {cat}
                  </label>
                {/each}
              </div>
              {#if selectedTypes.size === 0}
                <span class="type-hint">No type filter = all types included</span>
              {/if}
            </div>

          </div>
        {/if}

        {#if mode === 'all' || mode === 'match'}
          <div class="match-preview">
            <span class="match-preview-label">{matchedItems.length} item{matchedItems.length !== 1 ? 's' : ''}</span>
            <div class="match-preview-list">
              {#each matchedItems as item (item.item_id)}
                <div class="match-preview-row">
                  <span class="item-name">{item.item_name}</span>
                  {#if item.category}
                    <span class="item-type-badge">{item.category}</span>
                  {/if}
                  <span class="item-qty">x{item.quantity.toLocaleString()}</span>
                </div>
              {/each}
              {#if matchedItems.length === 0 && mode === 'match'}
                <p class="empty-text">No items match the current pattern</p>
              {/if}
            </div>
          </div>
        {/if}
      </div>

      <div class="filter-actions">
        <button class="btn btn-secondary" onclick={() => onclose?.()}>Cancel</button>
        <button class="btn btn-primary" onclick={save} disabled={regexError != null}>
          Save Filter
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .filter-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1100;
  }

  .filter-modal {
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 520px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
  }

  .filter-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border-color);
  }

  .filter-header h4 {
    margin: 0;
    font-size: 1rem;
  }

  .filter-preview {
    flex: 1;
    text-align: right;
    font-size: 0.8rem;
    color: var(--accent-color);
    font-weight: 500;
  }

  .close-btn {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 1.2rem;
    cursor: pointer;
    padding: 0 4px;
  }

  .close-btn:hover {
    color: var(--text-color);
  }

  .filter-body {
    padding: 1rem;
    overflow-y: auto;
    flex: 1;
  }

  .mode-selector {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    margin-bottom: 1rem;
  }

  .mode-option {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .item-list-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .search-input, .match-input {
    width: 100%;
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--secondary-color);
    color: var(--text-color);
    font-size: 0.85rem;
    box-sizing: border-box;
  }

  .search-input:focus, .match-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .item-list {
    max-height: 300px;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--secondary-color);
  }

  .item-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0.6rem;
    cursor: pointer;
    font-size: 0.82rem;
  }

  .item-row:hover {
    background: var(--hover-color);
  }

  .item-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-type-badge {
    font-size: 0.7rem;
    color: var(--text-muted);
    padding: 1px 4px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    white-space: nowrap;
  }

  .item-qty {
    font-size: 0.75rem;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .selection-hint {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .empty-text {
    text-align: center;
    color: var(--text-muted);
    padding: 1rem;
    margin: 0;
    font-size: 0.82rem;
  }

  .match-section {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .match-row {
    display: flex;
    gap: 0.75rem;
    align-items: flex-end;
  }

  .match-label {
    flex: 1;
    font-size: 0.82rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .regex-toggle {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.8rem;
    white-space: nowrap;
    padding-bottom: 0.4rem;
  }

  .error-text {
    color: var(--error-color);
    font-size: 0.75rem;
    margin: 0;
  }

  .type-filters {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .type-label {
    font-size: 0.82rem;
    color: var(--text-muted);
  }

  .type-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }

  .type-chip {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    padding: 2px 6px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    cursor: pointer;
    user-select: none;
    transition: background 0.1s, border-color 0.1s;
  }

  .type-chip:hover {
    background: var(--hover-color);
  }

  .type-chip.active {
    border-color: var(--accent-color);
    background: var(--accent-color);
    color: #fff;
  }

  .type-chip input {
    display: none;
  }

  .type-hint {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-style: italic;
  }

  .match-preview {
    margin-top: 0.5rem;
  }

  .match-preview-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    display: block;
    margin-bottom: 0.25rem;
  }

  .match-preview-list {
    max-height: 200px;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--secondary-color);
  }

  .match-preview-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0.6rem;
    font-size: 0.8rem;
  }

  .match-preview-row:hover {
    background: var(--hover-color);
  }

  .filter-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    border-top: 1px solid var(--border-color);
  }

  .btn {
    padding: 0.4rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
  }

  .btn-secondary {
    background: var(--secondary-color);
    color: var(--text-color);
  }

  .btn-primary {
    background: var(--accent-color);
    color: #fff;
    border-color: var(--accent-color);
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
