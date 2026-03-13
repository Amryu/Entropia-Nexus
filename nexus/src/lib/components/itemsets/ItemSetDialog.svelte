<!--
  @component ItemSetDialog
  Modal dialog for creating and editing item sets.
  Supports item search, armor/clothing set quick-add, and per-item metadata editing.
-->
<script>
  // @ts-nocheck
  import { slide } from 'svelte/transition';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';
  import ItemMetaEditor from './ItemMetaEditor.svelte';
  import SetEntry from './SetEntry.svelte';
  import { apiPost, apiPut, apiCall } from '$lib/util.js';
  import { addToast } from '$lib/stores/toasts.js';
  import { TIERABLE_TYPES, CONDITION_TYPES, isLimitedByName } from '$lib/common/itemTypes.js';

  const MAX_ITEMS = 100;

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {boolean} [show]
   * @property {object|null} [itemSet]
   * @property {string|null} [loadoutId]
   * @property {Set|null} [allowedItemTypes]
   * @property {boolean} [hideName]
   */

  /** @type {Props} */
  let {
    show = $bindable(false),
    itemSet = null,
    loadoutId = null,
    allowedItemTypes = null,
    hideName = false,
    onclose,
    onsave
  } = $props();

  // Internal state
  let name = $state('');
  let items = $state([]);
  let saving = $state(false);
  let expandedMeta = $state({});  // Track which items have expanded metadata
  let excludeLimited = $state(true);

  // Derived: convert Set to array for SearchInput's allowedTypes prop
  let allowedTypesArray = $derived(allowedItemTypes ? Array.from(allowedItemTypes) : null);
  let limitedFilterFn = $derived(excludeLimited ? (item) => !isLimitedByName(item.Name) : null);
  let showSetButton = $derived(!allowedItemTypes || allowedItemTypes.has('Armor'));

  // Initialize state when dialog opens or itemSet changes
  $effect(() => {
    if (show) {
      if (itemSet) {
        name = itemSet.name || '';
        items = JSON.parse(JSON.stringify(itemSet.data?.items || []));
      } else {
        name = '';
        items = [];
      }
      saving = false;
      expandedMeta = {};
      showSetSearch = false;
      armorSetOptions = null;
    }
  });

  let itemCount = $derived(items.reduce((count, item) => {
    if (item.setType) return count + 1;
    return count + 1;
  }, 0));

  let canSave = $derived((hideName || name.trim().length > 0) && items.length > 0);

  function handleKeydown(event) {
    if (event.key === 'Escape') close();
  }

  function handleBackdropClick(event) {
    if (event.target === event.currentTarget) close();
  }

  function close() {
    if (saving) return;
    show = false;
    onclose?.();
  }

  // === Item Management ===
  function addItem(searchResult) {
    if (itemCount >= MAX_ITEMS) {
      addToast(`Maximum ${MAX_ITEMS} items per set.`, { type: 'warning' });
      return;
    }

    const entry = {
      itemId: searchResult.Id || null,
      type: searchResult.Type || '',
      name: searchResult.Name || '',
      quantity: 1,
      meta: {}
    };

    items = [...items, entry];
  }

  function updateItem(index, field, value) {
    const updated = [...items];
    updated[index] = { ...updated[index], [field]: value };
    items = updated;
  }

  function updateItemMeta(index, newMeta) {
    const updated = [...items];
    updated[index] = { ...updated[index], meta: newMeta };
    items = updated;
  }

  function removeItem(index) {
    items = items.filter((_, i) => i !== index);
  }

  function toggleMeta(index) {
    expandedMeta = { ...expandedMeta, [index]: !expandedMeta[index] };
  }

  // === Set Quick-Add ===
  let showSetSearch = $state(false);
  let armorSetOptions = $state(null);

  async function loadArmorSets() {
    if (armorSetOptions !== null) return;
    try {
      const armorSets = await apiCall(fetch, '/armorsets');
      if (Array.isArray(armorSets)) {
        armorSetOptions = armorSets.map(s => ({ label: s.Name, value: String(s.Id), Id: s.Id, Name: s.Name }));
      } else {
        armorSetOptions = [];
      }
    } catch {
      armorSetOptions = [];
    }
  }

  function toggleSetSearch() {
    showSetSearch = !showSetSearch;
    if (showSetSearch) loadArmorSets();
  }

  async function addArmorSet(set) {
    if (itemCount >= MAX_ITEMS) {
      addToast(`Maximum ${MAX_ITEMS} items per set.`, { type: 'warning' });
      return;
    }

    // Fetch full set data to get pieces
    const fullSet = await apiCall(fetch, `/armorsets/${set.Id}`);
    if (!fullSet) {
      addToast('Failed to load armor set data.');
      return;
    }

    const pieces = [];
    if (Array.isArray(fullSet.Armors)) {
      for (const slotGroup of fullSet.Armors) {
        if (!Array.isArray(slotGroup)) continue;
        for (const piece of slotGroup) {
          pieces.push({
            itemId: null,
            name: piece.Name || '',
            slot: piece.Properties?.Slot || '',
            gender: piece.Properties?.Gender === 'Both' ? undefined : piece.Properties?.Gender,
            meta: {}
          });
        }
      }
    }

    const entry = {
      setType: 'ArmorSet',
      setId: fullSet.Id,
      setName: fullSet.Name,
      pieces
    };

    items = [...items, entry];
    showSetSearch = false;
  }

  function updateSetEntry(index, updatedEntry) {
    const updated = [...items];
    updated[index] = updatedEntry;
    items = updated;
  }

  function removeSetEntry(index) {
    items = items.filter((_, i) => i !== index);
  }

  // === Meta Detection Helpers ===
  function hasMetaFields(item) {
    if (item.setType) return false;
    const type = item.type || '';
    const name = item.name || '';
    const isLimited = isLimitedByName(name);
    return TIERABLE_TYPES.has(type) && !isLimited
      || CONDITION_TYPES.has(type)
      || (type === 'Blueprint' && !isLimited)
      || type === 'Pet';
  }

  // === Save ===
  async function save() {
    if (!canSave || saving) return;
    saving = true;

    try {
      const payload = {
        name: name.trim(),
        data: { items }
      };

      let result;
      if (itemSet?.id) {
        result = await apiPut(fetch, `/api/itemsets/${itemSet.id}`, payload);
      } else {
        if (loadoutId) payload.loadout_id = loadoutId;
        result = await apiPost(fetch, '/api/itemsets', payload);
      }

      if (result?.error) {
        addToast(result.error);
        saving = false;
        return;
      }

      onsave?.(result);
      show = false;
    } catch (err) {
      addToast('Failed to save item set.');
      console.error('Error saving item set:', err);
    }
    saving = false;
  }

</script>

<svelte:window onkeydown={handleKeydown} />

{#if show}
  <div class="modal-backdrop" role="presentation" onclick={handleBackdropClick}>
    <div class="modal" role="dialog" aria-modal="true" aria-label="Item Set Editor">
      <!-- Header -->
      <div class="modal-header">
        {#if hideName}
          <h3 class="modal-title">Item Set</h3>
        {:else}
          <input
            class="name-input"
            type="text"
            bind:value={name}
            placeholder="Item Set Name..."
            maxlength="120"
          />
        {/if}
        <button class="modal-close" onclick={close}>&times;</button>
      </div>

      <!-- Search Bar -->
      <div class="modal-search">
        <div class="search-row">
          <div class="search-main">
            <SearchInput
              value=""
              apiEndpoint="/search/items"
              placeholder="Search items..."
              displayFn={(item) => `${item.Name} (${item.Type})`}
              allowedTypes={allowedTypesArray}
              filterFn={limitedFilterFn}
              clearOnSelect={true}
              onselect={(e) => addItem(e.data)}
            />
          </div>
          <button
            class="btn-filter-limited"
            class:active={excludeLimited}
            onclick={() => excludeLimited = !excludeLimited}
            title={excludeLimited ? 'Showing unlimited only — click to include (L) items' : 'Showing all items — click to exclude (L) items'}
          >
            (L)
          </button>
          {#if showSetButton}
            <button
              class="btn-set-add"
              class:active={showSetSearch}
              onclick={toggleSetSearch}
              title="Add armor/clothing set"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
              Set
            </button>
          {/if}
        </div>

        {#if showSetSearch}
          <div class="set-search-row" transition:slide={{ duration: 150 }}>
            <SearchInput
              value=""
              options={armorSetOptions || []}
              placeholder="Search armor sets..."
              filterFn={limitedFilterFn}
              clearOnSelect={true}
              onselect={(e) => addArmorSet(e.data)}
            />
          </div>
        {/if}
      </div>

      <!-- Item List -->
      <div class="modal-body">
        {#if items.length === 0}
          <div class="empty-state">
            Search and add items to build your set.
          </div>
        {:else}
          <div class="item-list">
            {#each items as item, index (index)}
              {#if item.setType}
                <SetEntry
                  entry={item}
                  onupdate={(data) => updateSetEntry(index, data)}
                  onremove={() => removeSetEntry(index)}
                />
              {:else}
                <div class="item-row">
                  <div class="item-main">
                    <button class="btn-remove" onclick={() => removeItem(index)} title="Remove item">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                    <span class="item-type-badge">{item.type}</span>
                    <span class="item-name">{item.name}</span>
                    <div class="item-quantity">
                      <span class="quantity-prefix">x</span>
                      <input
                        type="number"
                        class="quantity-input"
                        value={item.quantity}
                        min="1"
                        max="9999999"
                        onchange={(e) => updateItem(index, 'quantity', Math.max(1, parseInt(e.target.value) || 1))}
                      />
                    </div>
                    {#if hasMetaFields(item)}
                      <button
                        class="btn-meta-toggle"
                        class:active={expandedMeta[index]}
                        onclick={() => toggleMeta(index)}
                        title="Edit metadata"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M12 20h9" />
                          <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                        </svg>
                      </button>
                    {/if}
                  </div>
                  {#if expandedMeta[index] && hasMetaFields(item)}
                    <div class="item-meta" transition:slide={{ duration: 150 }}>
                      <ItemMetaEditor
                        {item}
                        onchange={(data) => updateItemMeta(index, data)}
                      />
                    </div>
                  {/if}
                </div>
              {/if}
            {/each}
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="modal-footer">
        <span class="item-count">Items: {itemCount}/{MAX_ITEMS}</span>
        <div class="footer-actions">
          <button class="btn-cancel" onclick={close}>Cancel</button>
          <button class="btn-save" onclick={save} disabled={!canSave || saving}>
            {saving ? 'Saving...' : (itemSet ? 'Update' : 'Create')}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 1rem;
  }

  .modal {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 100%;
    max-width: 700px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }

  /* Header */
  .modal-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .modal-title {
    flex: 1;
    margin: 0;
    font-size: 16px;
    font-weight: 600;
  }

  .name-input {
    flex: 1;
    padding: 8px 12px;
    font-size: 16px;
    font-weight: 600;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
  }

  .name-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .modal-close {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 24px;
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
    flex-shrink: 0;
  }

  .modal-close:hover {
    color: var(--text-color);
  }

  /* Search */
  .modal-search {
    padding: 12px 20px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .search-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .search-main {
    flex: 1;
    min-width: 0;
  }

  .btn-filter-limited {
    padding: 7px 10px;
    font-size: 12px;
    font-weight: 700;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-muted);
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.15s;
    text-decoration: line-through;
  }

  .btn-filter-limited.active {
    border-color: var(--error-color);
    color: var(--error-color);
  }

  .btn-filter-limited:not(.active) {
    text-decoration: none;
    color: var(--text-muted);
  }

  .btn-set-add {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 7px 12px;
    font-size: 12px;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-muted);
    cursor: pointer;
    white-space: nowrap;
    flex-shrink: 0;
    transition: all 0.15s;
  }

  .btn-set-add:hover,
  .btn-set-add.active {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }

  .set-search-row {
    margin-top: 8px;
    position: relative;
  }


  /* Body */
  .modal-body {
    flex: 1;
    overflow-y: auto;
    padding: 12px 20px;
    min-height: 150px;
  }

  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 120px;
    color: var(--text-muted);
    font-size: 14px;
  }

  .item-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  /* Item Row */
  .item-row {
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
  }

  .item-main {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
  }

  .btn-remove {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 3px;
    background: transparent;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--error-color);
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.15s;
  }

  .btn-remove:hover {
    background-color: var(--error-color);
    color: white;
    border-color: var(--error-color);
  }

  .item-type-badge {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 3px;
    background-color: var(--hover-color);
    color: var(--text-muted);
    flex-shrink: 0;
    max-width: 80px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-name {
    font-size: 13px;
    color: var(--text-color);
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-quantity {
    display: flex;
    align-items: center;
    gap: 2px;
    flex-shrink: 0;
  }

  .quantity-prefix {
    font-size: 12px;
    color: var(--text-muted);
  }

  .quantity-input {
    width: 50px;
    padding: 3px 5px;
    font-size: 12px;
    text-align: center;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
  }

  .quantity-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .btn-meta-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
    background: transparent;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-muted);
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.15s;
  }

  .btn-meta-toggle:hover,
  .btn-meta-toggle.active {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }

  .item-meta {
    padding: 8px 10px 10px 36px;
    border-top: 1px solid var(--border-color);
  }

  /* Footer */
  .modal-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    border-top: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .item-count {
    font-size: 12px;
    color: var(--text-muted);
  }

  .footer-actions {
    display: flex;
    gap: 8px;
  }

  .btn-cancel {
    padding: 8px 16px;
    font-size: 13px;
    background: transparent;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-cancel:hover {
    background-color: var(--hover-color);
  }

  .btn-save {
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
    background-color: var(--accent-color);
    border: 1px solid var(--accent-color);
    border-radius: 6px;
    color: white;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-save:hover:not(:disabled) {
    background-color: var(--accent-color-hover);
  }

  .btn-save:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Remove spinner arrows */
  .quantity-input::-webkit-outer-spin-button,
  .quantity-input::-webkit-inner-spin-button {
    appearance: none;
    -webkit-appearance: none;
    margin: 0;
  }
  .quantity-input[type=number] {
    appearance: textfield;
    -moz-appearance: textfield;
  }

  /* Mobile */
  @media (max-width: 899px) {
    .modal {
      max-height: 95vh;
    }

    .modal-header {
      padding: 12px 14px;
    }

    .name-input {
      font-size: 14px;
      padding: 6px 10px;
    }

    .modal-search {
      padding: 10px 14px;
    }

    .modal-body {
      padding: 10px 14px;
    }

    .modal-footer {
      padding: 10px 14px;
    }

    .item-type-badge {
      display: none;
    }

    .item-meta {
      padding-left: 10px;
    }
  }
</style>
