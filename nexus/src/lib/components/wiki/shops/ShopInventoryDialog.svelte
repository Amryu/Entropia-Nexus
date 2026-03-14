<!--
  @component ShopInventoryDialog
  Dialog for managing shop inventory. Owner and managers can access this.
  Supports multiple custom groups, item search, and efficient handling of many items.
  Groups are user-defined (not tied to estate areas).
-->
<script>
  // @ts-nocheck
  import { apiCall } from '$lib/util';
  import { isPercentMarkupType } from '$lib/common/itemTypes.js';
  import SearchInput from '$lib/components/SearchInput.svelte';

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {string} [shopName] - Shop name/identifier for API calls
   * @property {boolean} [open] - Whether the dialog is open
   * @property {any} [inventoryGroups] - Current inventory groups from shop data
   * @property {any} [itemDetails] - Item details map (ItemId -> Item object) for looking up names
   * @property {() => void} [onclose]
   * @property {(data: any) => void} [onsaved]
   */

  /** @type {Props} */
  let {
    shopName = '',
    open = $bindable(false),
    inventoryGroups = [],
    itemDetails = {},
    onclose,
    onsaved
  } = $props();

  // Constants
  const MIN_STACK_SIZE = 1;
  const MAX_STACK_SIZE = 999999;
  const MIN_MARKUP = 0;
  const MAX_MARKUP = 100000;

  // Local state
  let localGroups = $state([]);
  let activeGroupIndex = $state(0);
  let saving = $state(false);
  let error = $state(null);
  let success = $state(null);

  // Item search state
  let itemSearchQuery = $state('');

  // New group state
  let showNewGroupInput = $state(false);
  let newGroupName = $state('');

  // Edit group name state
  let editingGroupIndex = $state(null);
  let editGroupName = $state('');

  // Edit item state
  let editingItemIndex = $state(null);

  // Group edit mode - when false, hides reorder/rename/delete controls for cleaner UI
  let groupEditMode = $state(false);


  function initializeGroups() {
    // Copy existing inventory groups (user-defined, not estate-based)
    if (inventoryGroups && inventoryGroups.length > 0) {
      localGroups = inventoryGroups.map(group => ({
        Name: group.Name || group.name || 'Inventory',
        Items: (group.Items || []).map(item => {
          const itemId = item.ItemId ?? item.item_id;
          // Look up item name from itemDetails map
          const itemInfo = itemDetails[itemId];
          const itemName = item.ItemName || item.itemName || itemInfo?.Name || 'Unknown';
          return {
            ItemId: itemId,
            ItemName: itemName,
            ItemType: itemInfo?.Type || null,
            ItemSubType: itemInfo?.SubType || null,
            StackSize: item.StackSize ?? item.stack_size ?? 1,
            Markup: item.Markup ?? item.markup ?? 100,
            SortOrder: item.SortOrder ?? item.sort_order ?? 0
          };
        })
      }));
    } else {
      // Start with one default group if none exist
      localGroups = [{
        Name: 'Inventory',
        Items: []
      }];
    }

    activeGroupIndex = 0;
  }

  function isPercentMarkup(item) {
    return isPercentMarkupType(item.ItemType, item.ItemName, item.ItemSubType);
  }

  function getMarkupUnit(item) {
    return isPercentMarkup(item) ? '%' : 'PED';
  }

  function close() {
    open = false;
    onclose?.();
  }

  // Group management
  function addGroup() {
    const name = newGroupName.trim();
    if (!name) {
      error = 'Please enter a group name.';
      return;
    }

    // Check for duplicate group names
    if (localGroups.some(g => g.Name.toLowerCase() === name.toLowerCase())) {
      error = `A group named "${name}" already exists.`;
      return;
    }

    localGroups = [...localGroups, { Name: name, Items: [] }];
    activeGroupIndex = localGroups.length - 1;
    newGroupName = '';
    showNewGroupInput = false;
    error = null;
  }

  function deleteGroup(index) {
    if (localGroups.length <= 1) {
      error = 'You must have at least one group.';
      return;
    }

    localGroups = localGroups.filter((_, i) => i !== index);
    if (activeGroupIndex >= localGroups.length) {
      activeGroupIndex = localGroups.length - 1;
    }
    error = null;
  }

  function handleNewGroupKeydown(event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      addGroup();
    } else if (event.key === 'Escape') {
      showNewGroupInput = false;
      newGroupName = '';
    }
  }

  // Start editing a group name
  function startEditGroupName(index) {
    editingGroupIndex = index;
    editGroupName = localGroups[index].Name;
  }

  // Save the edited group name
  function saveGroupName() {
    if (editingGroupIndex === null) return;

    const name = editGroupName.trim();
    if (!name) {
      error = 'Group name cannot be empty.';
      return;
    }

    // Check for duplicate names (excluding current group)
    if (localGroups.some((g, i) => i !== editingGroupIndex && g.Name.toLowerCase() === name.toLowerCase())) {
      error = `A group named "${name}" already exists.`;
      return;
    }

    localGroups[editingGroupIndex].Name = name;
    localGroups = [...localGroups];
    editingGroupIndex = null;
    editGroupName = '';
    error = null;
  }

  // Cancel editing group name
  function cancelEditGroupName() {
    editingGroupIndex = null;
    editGroupName = '';
  }

  function handleEditGroupKeydown(event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      saveGroupName();
    } else if (event.key === 'Escape') {
      cancelEditGroupName();
    }
  }

  // Handle item selection from SearchInput
  function handleItemSelect({ id, name, type, subType }) {
    selectItem({ Id: id, Name: name, Type: type, SubType: subType });
  }

  function selectItem(item) {
    const group = localGroups[activeGroupIndex];

    // The search API returns Id with the proper offset already applied
    const itemId = item.Id;

    if (!itemId) {
      error = `Could not find item "${item.Name}" in database.`;
      itemSearchQuery = '';
      return;
    }

    // Add item with defaults
    group.Items = [...group.Items, {
      ItemId: itemId,
      ItemName: item.Name,
      ItemType: item.Type || null,
      ItemSubType: item.SubType || null,
      StackSize: 1,
      Markup: 100,
      SortOrder: group.Items.length
    }];

    localGroups = [...localGroups];
    itemSearchQuery = '';
    error = null;

    // Start editing the new item
    editingItemIndex = group.Items.length - 1;
  }

  function removeItem(groupIndex, itemIndex) {
    localGroups[groupIndex].Items = localGroups[groupIndex].Items.filter((_, i) => i !== itemIndex);
    localGroups = [...localGroups];
    if (editingItemIndex === itemIndex) {
      editingItemIndex = null;
    }
  }

  // Reorder items within a group
  function moveItem(groupIndex, itemIndex, direction) {
    const items = localGroups[groupIndex].Items;
    const newIndex = itemIndex + direction;

    if (newIndex < 0 || newIndex >= items.length) return;

    // Swap items
    [items[itemIndex], items[newIndex]] = [items[newIndex], items[itemIndex]];

    // Update sort orders
    items.forEach((item, idx) => {
      item.SortOrder = idx;
    });

    localGroups = [...localGroups];

    // Update editing index if needed
    if (editingItemIndex === itemIndex) {
      editingItemIndex = newIndex;
    } else if (editingItemIndex === newIndex) {
      editingItemIndex = itemIndex;
    }
  }

  // Reorder groups
  function moveGroup(groupIndex, direction) {
    const newIndex = groupIndex + direction;

    if (newIndex < 0 || newIndex >= localGroups.length) return;

    // Swap groups
    [localGroups[groupIndex], localGroups[newIndex]] = [localGroups[newIndex], localGroups[groupIndex]];
    localGroups = [...localGroups];

    // Update active group index to follow the moved group
    if (activeGroupIndex === groupIndex) {
      activeGroupIndex = newIndex;
    } else if (activeGroupIndex === newIndex) {
      activeGroupIndex = groupIndex;
    }
  }

  function updateItem(groupIndex, itemIndex, field, value) {
    const item = localGroups[groupIndex].Items[itemIndex];

    if (field === 'StackSize') {
      item.StackSize = Math.min(MAX_STACK_SIZE, Math.max(MIN_STACK_SIZE, parseInt(value) || 1));
    } else if (field === 'Markup') {
      item.Markup = Math.min(MAX_MARKUP, Math.max(MIN_MARKUP, parseFloat(value) || 100));
    }

    localGroups = [...localGroups];
  }

  function validateItem(item) {
    const errors = [];
    if (!item.ItemId) errors.push('Item is required');
    if (item.StackSize < MIN_STACK_SIZE || item.StackSize > MAX_STACK_SIZE) {
      errors.push(`Stack size must be ${MIN_STACK_SIZE}-${MAX_STACK_SIZE}`);
    }
    if (item.Markup < MIN_MARKUP || item.Markup > MAX_MARKUP) {
      const unit = getMarkupUnit(item);
      errors.push(`Markup must be ${MIN_MARKUP}-${MAX_MARKUP} ${unit}`);
    }
    return errors;
  }


  async function save() {
    if (saving) return;

    // Validate all items
    for (const group of localGroups) {
      for (const item of group.Items) {
        const errors = validateItem(item);
        if (errors.length > 0) {
          error = `Invalid item in ${group.Name}: ${errors.join(', ')}`;
          return;
        }
      }
    }

    saving = true;
    error = null;
    success = null;

    try {
      const response = await fetch(`/api/shops/${encodeURIComponent(shopName)}/inventory`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          InventoryGroups: localGroups.map(g => ({
            Name: g.Name,
            Items: g.Items.map((item, idx) => ({
              ItemId: item.ItemId,
              StackSize: item.StackSize,
              Markup: item.Markup,
              SortOrder: idx
            }))
          }))
        })
      });

      const result = await response.json();

      if (!response.ok) {
        error = result.error || 'Failed to update inventory';
      } else {
        success = 'Inventory updated successfully';
        onsaved?.({ inventoryGroups: localGroups });
        setTimeout(() => {
          close();
        }, 1000);
      }
    } catch (e) {
      error = 'Network error. Please try again.';
    } finally {
      saving = false;
    }
  }

  function handleBackdropClick(event) {
    if (event.target === event.currentTarget) {
      close();
    }
  }

  // Initialize groups when dialog opens
  $effect(() => {
    if (open) {
      initializeGroups();
      error = null;
      success = null;
      itemSearchQuery = '';
      editingItemIndex = null;
      editingGroupIndex = null;
      editGroupName = '';
      showNewGroupInput = false;
      newGroupName = '';
      groupEditMode = false; // Reset edit mode when dialog opens
    }
  });
  // Reactive total items count - updates when localGroups changes
  let totalItems = $derived(localGroups.reduce((sum, g) => sum + (g?.Items?.length ?? 0), 0));
</script>

{#if open}
  <div class="dialog-backdrop" role="presentation" onclick={handleBackdropClick}>
    <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="inventory-dialog-title">
      <div class="dialog-header">
        <h3 id="inventory-dialog-title">Edit Shop Inventory</h3>
        <button class="close-btn" onclick={close} aria-label="Close dialog">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div class="dialog-body">
        <!-- Group Tabs -->
        <div class="groups-row">
          <div class="group-tabs">
            {#each localGroups as group, index}
              <div class="group-tab-wrapper">
                <!-- Reorder left button (only if multiple groups and this is active, and edit mode is on) -->
                {#if groupEditMode && activeGroupIndex === index && localGroups.length > 1}
                  <button
                    class="reorder-group-btn"
                    onclick={(e) => { e.stopPropagation(); moveGroup(index, -1); }}
                    disabled={saving || index === 0}
                    title="Move group left"
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M15 18l-6-6 6-6" />
                    </svg>
                  </button>
                {/if}
                {#if editingGroupIndex === index}
                  <div class="edit-group-name-wrapper">
                    <input
                      type="text"
                      bind:value={editGroupName}
                      onkeydown={handleEditGroupKeydown}
                      class="edit-group-input"
                      disabled={saving}
                    />
                    <button class="edit-group-confirm" onclick={saveGroupName} disabled={!editGroupName.trim() || saving} title="Save">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                    </button>
                    <button class="edit-group-cancel" onclick={cancelEditGroupName} title="Cancel">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                      </svg>
                    </button>
                  </div>
                {:else}
                  <button
                    class="group-tab"
                    class:active={activeGroupIndex === index}
                    onclick={() => { activeGroupIndex = index; editingItemIndex = null; }}
                    ondblclick={(e) => { e.stopPropagation(); startEditGroupName(index); }}
                    disabled={saving}
                    title="Double-click to rename"
                  >
                    {group.Name}
                    <span class="item-count">{group.Items.length}</span>
                  </button>
                {/if}
                {#if groupEditMode && activeGroupIndex === index && editingGroupIndex !== index}
                  <!-- Reorder right button (only if multiple groups) -->
                  {#if localGroups.length > 1}
                    <button
                      class="reorder-group-btn"
                      onclick={(e) => { e.stopPropagation(); moveGroup(index, 1); }}
                      disabled={saving || index === localGroups.length - 1}
                      title="Move group right"
                    >
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 18l6-6-6-6" />
                      </svg>
                    </button>
                  {/if}
                  <!-- Group action buttons -->
                  <div class="group-action-buttons">
                    <button
                      class="group-action-btn rename"
                      onclick={(e) => { e.stopPropagation(); startEditGroupName(index); }}
                      disabled={saving}
                      title="Rename group"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                      </svg>
                    </button>
                    {#if localGroups.length > 1}
                      <button
                        class="group-action-btn delete"
                        onclick={(e) => { e.stopPropagation(); deleteGroup(index); }}
                        disabled={saving}
                        title="Delete group"
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <polyline points="3 6 5 6 21 6"></polyline>
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                      </button>
                    {/if}
                  </div>
                {/if}
              </div>
            {/each}

            {#if showNewGroupInput}
              <div class="new-group-input-wrapper">
                <input
                  type="text"
                  bind:value={newGroupName}
                  onkeydown={handleNewGroupKeydown}
                  placeholder="Group name..."
                  class="new-group-input"
                  disabled={saving}
                />
                <button class="add-group-confirm" onclick={addGroup} disabled={!newGroupName.trim() || saving} aria-label="Confirm add group">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                </button>
                <button class="add-group-cancel" onclick={() => { showNewGroupInput = false; newGroupName = ''; }} aria-label="Cancel add group">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>
            {:else}
              <button class="add-group-btn" onclick={() => showNewGroupInput = true} disabled={saving} title="Add new group">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="12" y1="5" x2="12" y2="19"></line>
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
              </button>
            {/if}

            <!-- Group Edit Mode Toggle -->
            <button
              class="edit-mode-toggle"
              class:active={groupEditMode}
              onclick={() => groupEditMode = !groupEditMode}
              disabled={saving}
              title={groupEditMode ? 'Exit group edit mode' : 'Edit groups (reorder, rename, delete)'}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
              </svg>
              <span class="edit-mode-label">{groupEditMode ? 'Done' : 'Edit'}</span>
            </button>
          </div>
        </div>

        <!-- Add Item Search -->
        <div class="add-item-section">
          <span class="search-label">Add Item</span>
          <SearchInput
            bind:value={itemSearchQuery}
            placeholder="Search items by name..."
            mode="dropdown"
            containerClass="inventory-search"
            endpoint="/search/items"
            disabled={saving}
            onselect={handleItemSelect}
          />
        </div>

        <!-- Items List -->
        <div class="items-section">
          <div class="items-header">
            <span class="col-order"></span>
            <span class="col-item">Item</span>
            <span class="col-stack">Stack</span>
            <span class="col-markup">Markup</span>
            <span class="col-actions"></span>
          </div>

          <div class="items-list">
            {#if localGroups[activeGroupIndex]?.Items?.length === 0}
              <div class="no-items">No items in this group. Use the search above to add items.</div>
            {:else if localGroups[activeGroupIndex]?.Items}
              {#each localGroups[activeGroupIndex].Items as item, index}
                <div class="item-row" class:editing={editingItemIndex === index}>
                  <span class="col-order">
                    <div class="reorder-btns">
                      <button
                        class="reorder-btn"
                        onclick={() => moveItem(activeGroupIndex, index, -1)}
                        disabled={saving || index === 0}
                        title="Move up"
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M18 15l-6-6-6 6" />
                        </svg>
                      </button>
                      <button
                        class="reorder-btn"
                        onclick={() => moveItem(activeGroupIndex, index, 1)}
                        disabled={saving || index === localGroups[activeGroupIndex].Items.length - 1}
                        title="Move down"
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M6 9l6 6 6-6" />
                        </svg>
                      </button>
                    </div>
                  </span>
                  <span class="col-item item-name" title={item.ItemName}>
                    {item.ItemName}
                  </span>
                  <span class="col-stack">
                    <input
                      type="number"
                      class="compact-input"
                      value={item.StackSize}
                      oninput={(e) => updateItem(activeGroupIndex, index, 'StackSize', e.target.value)}
                      onfocus={() => editingItemIndex = index}
                      min={MIN_STACK_SIZE}
                      max={MAX_STACK_SIZE}
                      disabled={saving}
                    />
                  </span>
                  <span class="col-markup">
                    <input
                      type="number"
                      class="compact-input"
                      value={item.Markup}
                      oninput={(e) => updateItem(activeGroupIndex, index, 'Markup', e.target.value)}
                      onfocus={() => editingItemIndex = index}
                      min={MIN_MARKUP}
                      max={MAX_MARKUP}
                      step="0.01"
                      disabled={saving}
                    />
                    <span class="markup-unit">{getMarkupUnit(item)}</span>
                  </span>
                  <span class="col-actions">
                    <button
                      class="remove-btn"
                      onclick={() => removeItem(activeGroupIndex, index)}
                      disabled={saving}
                      aria-label="Remove item"
                      title="Remove item"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      </svg>
                    </button>
                  </span>
                </div>
              {/each}
            {/if}
          </div>
        </div>

        <!-- Status Messages -->
        {#if error}
          <div class="message error">{error}</div>
        {/if}
        {#if success}
          <div class="message success">{success}</div>
        {/if}
      </div>

      <div class="dialog-footer">
        <div class="footer-info">
          Total: {totalItems} item{totalItems !== 1 ? 's' : ''}
        </div>
        <div class="footer-actions">
          <button class="cancel-btn" onclick={close} disabled={saving}>
            Cancel
          </button>
          <button class="save-btn" onclick={save} disabled={saving}>
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .dialog-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
  }

  .dialog {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    width: 100%;
    max-width: 650px;
    height: 80vh;
    max-height: 700px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color, #555);
    flex-shrink: 0;
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
  }

  .close-btn {
    background: none;
    border: none;
    padding: 4px;
    cursor: pointer;
    color: var(--text-muted, #999);
    border-radius: 4px;
  }

  .close-btn:hover {
    color: var(--text-color);
    background-color: var(--hover-color) !important;
  }

  .dialog-body {
    padding: 16px 20px;
    overflow: hidden;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  /* Group Tabs */
  .groups-row {
    margin-bottom: 16px;
  }

  .group-tabs {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
    align-items: center;
  }

  .group-tab-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .group-tab {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 500;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    cursor: pointer;
    white-space: nowrap;
  }

  .group-tab:hover:not(:disabled) {
    background-color: var(--hover-color) !important;
    color: var(--text-color);
  }

  .group-tab.active {
    background-color: var(--accent-color, #4a9eff) !important;
    border-color: var(--accent-color, #4a9eff);
    color: white;
    /* No extra padding - action buttons are siblings, not overlaid */
  }

  .item-count {
    padding: 2px 6px;
    font-size: 11px;
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 10px;
  }

  /* Group Action Buttons Container */
  .group-action-buttons {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: 4px;
  }

  .group-action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    padding: 0;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  }

  .group-action-btn.rename {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .group-action-btn.rename:hover:not(:disabled) {
    background-color: var(--accent-color-hover, #3a8eef) !important;
  }

  .group-action-btn.delete {
    background-color: var(--error-color, #ff6b6b);
    color: white;
  }

  .group-action-btn.delete:hover:not(:disabled) {
    background-color: #ff5252 !important;
  }

  .group-action-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .add-group-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px dashed var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    cursor: pointer;
  }

  .add-group-btn:hover:not(:disabled) {
    background-color: var(--hover-color) !important;
    color: var(--text-color);
    border-style: solid;
  }

  .new-group-input-wrapper {
    display: flex;
    gap: 4px;
    align-items: center;
  }

  .new-group-input {
    width: 120px;
    padding: 6px 10px;
    font-size: 13px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--accent-color, #4a9eff);
    border-radius: 4px;
    color: var(--text-color);
  }

  .new-group-input:focus {
    outline: none;
  }

  .add-group-confirm,
  .add-group-cancel {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }

  .add-group-confirm {
    background-color: var(--success-color, #4ade80);
    color: white;
  }

  .add-group-confirm:hover:not(:disabled) {
    background-color: #3bc96f !important;
  }

  .add-group-confirm:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .add-group-cancel {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    color: var(--text-muted, #999);
  }

  .add-group-cancel:hover {
    background-color: var(--hover-color) !important;
    color: var(--text-color);
  }

  /* Edit Mode Toggle */
  .edit-mode-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    cursor: pointer;
    margin-left: auto;
    white-space: nowrap;
  }

  .edit-mode-toggle:hover:not(:disabled) {
    background-color: var(--hover-color) !important;
    color: var(--text-color);
    border-color: var(--accent-color, #4a9eff);
  }

  .edit-mode-toggle.active {
    background-color: var(--accent-color, #4a9eff) !important;
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .edit-mode-toggle.active:hover:not(:disabled) {
    background-color: var(--accent-color-hover, #3a8eef) !important;
  }

  .edit-mode-toggle:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .edit-mode-label {
    display: inline;
  }

  /* Add Item Search */
  .add-item-section {
    margin-bottom: 16px;
    position: relative;
  }

  .search-label {
    display: block;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted, #999);
    margin-bottom: 6px;
  }

  /* Inventory search styling via SearchInput */
  :global(.inventory-search .search-input) {
    width: 100%;
    padding: 10px 12px;
    padding-right: 32px;
    font-size: 14px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    box-sizing: border-box;
  }

  :global(.inventory-search .search-results-container) {
    max-height: 200px;
  }

  /* Items List */
  .items-section {
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
  }

  .items-header {
    display: grid;
    grid-template-columns: 36px 1fr 80px 120px 36px;
    gap: 8px;
    padding: 8px 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-bottom: 1px solid var(--border-color, #555);
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    flex-shrink: 0;
  }

  .items-list {
    flex: 1;
    overflow-y: auto;
    min-height: 100px;
  }

  .no-items {
    padding: 30px 20px;
    text-align: center;
    color: var(--text-muted, #999);
    font-style: italic;
    font-size: 13px;
  }

  .item-row {
    display: grid;
    grid-template-columns: 36px 1fr 80px 120px 36px;
    gap: 8px;
    padding: 8px 12px;
    align-items: center;
    border-bottom: 1px solid var(--border-color, #555);
    font-size: 13px;
  }

  .item-row:last-child {
    border-bottom: none;
  }

  .item-row.editing {
    background-color: rgba(74, 158, 255, 0.1);
  }

  .item-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-color);
  }

  .compact-input {
    width: 100%;
    padding: 6px 8px;
    font-size: 13px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    text-align: right;
    box-sizing: border-box;
  }

  .compact-input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  /* Hide number spinners */
  .compact-input::-webkit-outer-spin-button,
  .compact-input::-webkit-inner-spin-button {
    appearance: none;
    -webkit-appearance: none;
    margin: 0;
  }

  .compact-input[type=number] {
    appearance: textfield;
    -moz-appearance: textfield;
  }

  .col-markup {
    display: flex;
    align-items: center;
  }

  .markup-unit {
    font-size: 11px;
    color: var(--text-muted, #999);
    margin-left: 4px;
    white-space: nowrap;
  }

  .remove-btn {
    background-color: var(--error-bg, rgba(255, 107, 107, 0.15));
    border: 1px solid var(--error-color, #ff6b6b);
    padding: 4px;
    cursor: pointer;
    color: var(--error-color, #ff6b6b);
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .remove-btn:hover:not(:disabled) {
    background-color: var(--error-color, #ff6b6b) !important;
    color: white;
  }

  /* Reorder Buttons - Items */
  .col-order {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .reorder-btns {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .reorder-btn {
    background: none;
    border: 1px solid var(--border-color, #555);
    padding: 2px;
    cursor: pointer;
    color: var(--text-muted, #999);
    border-radius: 3px;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 16px;
  }

  .reorder-btn:hover:not(:disabled) {
    color: var(--text-color);
    background-color: var(--hover-color) !important;
    border-color: var(--accent-color, #4a9eff);
  }

  .reorder-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  /* Reorder Buttons - Groups */
  .reorder-group-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 28px;
    padding: 0;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    cursor: pointer;
  }

  .reorder-group-btn:hover:not(:disabled) {
    color: var(--text-color);
    background-color: var(--hover-color) !important;
    border-color: var(--accent-color, #4a9eff);
  }

  .reorder-group-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  /* Edit Group Name */
  .edit-group-name-wrapper {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .edit-group-input {
    width: 100px;
    padding: 6px 10px;
    font-size: 13px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--accent-color, #4a9eff);
    border-radius: 4px;
    color: var(--text-color);
  }

  .edit-group-input:focus {
    outline: none;
  }

  .edit-group-confirm,
  .edit-group-cancel {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    padding: 0;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }

  .edit-group-confirm {
    background-color: var(--success-color, #4ade80);
    color: white;
  }

  .edit-group-confirm:hover:not(:disabled) {
    background-color: #3bc96f !important;
  }

  .edit-group-confirm:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .edit-group-cancel {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    color: var(--text-muted, #999);
  }

  .edit-group-cancel:hover {
    background-color: var(--hover-color) !important;
    color: var(--text-color);
  }

  /* Messages */
  .message {
    margin-top: 12px;
    padding: 10px 12px;
    border-radius: 4px;
    font-size: 13px;
  }

  .message.error {
    background-color: var(--error-bg, rgba(255, 107, 107, 0.15));
    color: var(--error-color, #ff6b6b);
    border: 1px solid var(--error-color, #ff6b6b);
  }

  .message.success {
    background-color: var(--success-bg, rgba(74, 222, 128, 0.15));
    color: var(--success-color, #4ade80);
    border: 1px solid var(--success-color, #4ade80);
  }

  /* Footer */
  .dialog-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-top: 1px solid var(--border-color, #555);
    flex-shrink: 0;
  }

  .footer-info {
    font-size: 13px;
    color: var(--text-muted, #999);
  }

  .footer-actions {
    display: flex;
    gap: 10px;
  }

  .cancel-btn,
  .save-btn {
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 500;
    border-radius: 4px;
    cursor: pointer;
  }

  .cancel-btn {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
  }

  .cancel-btn:hover:not(:disabled) {
    background-color: var(--hover-color) !important;
  }

  .save-btn {
    background-color: var(--accent-color, #4a9eff);
    border: none;
    color: white;
  }

  .save-btn:hover:not(:disabled) {
    background-color: var(--accent-color-hover, #3a8eef) !important;
  }

  .save-btn:disabled,
  .cancel-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  /* Mobile - aligned with global 900px breakpoint */
  @media (max-width: 899px) {
    .dialog-backdrop {
      padding: 0;
      align-items: flex-end;
    }

    .dialog {
      max-width: 100%;
      max-height: 95vh;
      border-radius: 16px 16px 0 0;
    }

    .dialog-header,
    .dialog-footer {
      padding: 12px 16px;
    }

    .dialog-body {
      padding: 12px 16px;
    }

    /* Make groups row horizontally scrollable on mobile */
    .groups-row {
      margin-bottom: 12px;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      padding-bottom: 4px;
    }

    .group-tabs {
      flex-wrap: nowrap;
      gap: 6px;
      min-width: max-content;
    }

    .group-tab-wrapper {
      flex-shrink: 0;
    }

    .group-tab {
      padding: 8px 12px;
      font-size: 13px;
    }

    /* Edit mode toggle on mobile */
    .edit-mode-toggle {
      padding: 8px 12px;
      font-size: 13px;
      margin-left: 8px;
      flex-shrink: 0;
    }

    /* Larger touch targets for action buttons on mobile */
    .group-action-buttons {
      gap: 6px;
      margin-left: 6px;
    }

    .group-action-btn {
      width: 32px;
      height: 32px;
    }

    .group-action-btn svg {
      width: 14px;
      height: 14px;
    }

    .reorder-group-btn {
      width: 28px;
      height: 32px;
    }

    /* Items table */
    .items-header {
      grid-template-columns: 32px 1fr 60px 80px 32px;
      gap: 4px;
      padding: 8px 10px;
      font-size: 10px;
    }

    .item-row {
      grid-template-columns: 32px 1fr 60px 80px 32px;
      gap: 4px;
      padding: 10px;
      font-size: 12px;
    }

    .reorder-btn {
      width: 22px;
      height: 18px;
    }

    .reorder-btns {
      gap: 2px;
    }

    .remove-btn {
      width: 28px;
      height: 28px;
      padding: 6px;
    }

    .compact-input {
      padding: 6px;
      font-size: 13px;
    }

    .footer-actions {
      gap: 8px;
    }

    .cancel-btn,
    .save-btn {
      padding: 12px 16px;
      font-size: 14px;
    }
  }
</style>
