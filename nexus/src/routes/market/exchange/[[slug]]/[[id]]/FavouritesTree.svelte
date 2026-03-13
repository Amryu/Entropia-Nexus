<script>
  // @ts-nocheck
  import { createFolder, renameFolder, deleteFolder, removeFavourite, moveToFolder } from '../../favouritesStore.js';
  import { clickable } from '$lib/actions/clickable.js';

  /**
   * @typedef {Object} Props
   * @property {any} [favouritesData]
   * @property {any} [allItems]
   * @property {any} [onSelectItem]
   * @property {any} [onSelectFolder]
   * @property {any} [selectedFolderId] - 'all' | 'root' | folder id | null
   * @property {any} [selectedItemId] - currently selected item id
   * @property {boolean} [showNewFolderButton]
   */

  /** @type {Props} */
  let {
    favouritesData = { folders: [], items: [] },
    allItems = [],
    onSelectItem = null,
    onSelectFolder = null,
    selectedFolderId = null,
    selectedItemId = null,
    showNewFolderButton = true
  } = $props();

  let expandedFolders = $state(new Set());
  let editingFolderId = $state(null);
  let editingFolderName = $state('');
  let dragItemId = $state(null);
  let dragOverTarget = $state(null); // folder id or 'root'

  // Build a lookup map for item names by ID
  let itemMap = $derived((() => {
    const map = {};
    for (const item of (allItems || [])) {
      if (item?.i != null) map[item.i] = item;
    }
    return map;
  })());

  // Sort folders by order
  let sortedFolders = $derived([...(favouritesData?.folders || [])].sort((a, b) => (a.order ?? 0) - (b.order ?? 0)));

  // Root items (not in any folder)
  let rootItems = $derived(favouritesData?.items || []);

  // Gather all favourite item IDs across all folders + root
  let allFavItemIds = $derived((() => {
    const ids = new Set(rootItems);
    for (const f of sortedFolders) {
      for (const id of (f.items || [])) ids.add(id);
    }
    return [...ids];
  })());

  let hasFavourites = $derived(rootItems.length > 0 || sortedFolders.some(f => f.items?.length > 0));

  function toggleFolder(folderId) {
    if (expandedFolders.has(folderId)) {
      expandedFolders.delete(folderId);
    } else {
      expandedFolders.add(folderId);
    }
    expandedFolders = new Set(expandedFolders);
  }

  function handleFolderSelect(folderId, itemIds) {
    if (onSelectFolder) onSelectFolder(folderId, itemIds);
  }

  function handleItemClick(itemId) {
    if (onSelectItem) onSelectItem(itemId);
  }

  function handleNewFolder() {
    const id = createFolder('New Folder');
    expandedFolders.add(id);
    expandedFolders = new Set(expandedFolders);
    // Start editing the name
    editingFolderId = id;
    editingFolderName = 'New Folder';
  }

  function startRename(folder) {
    editingFolderId = folder.id;
    editingFolderName = folder.name;
  }

  function finishRename() {
    if (editingFolderId && editingFolderName.trim()) {
      renameFolder(editingFolderId, editingFolderName.trim());
    }
    editingFolderId = null;
    editingFolderName = '';
  }

  function handleRenameKeydown(e) {
    if (e.key === 'Enter') finishRename();
    if (e.key === 'Escape') { editingFolderId = null; editingFolderName = ''; }
  }

  function handleDeleteFolder(folderId) {
    deleteFolder(folderId, true); // keep items, move to root
  }

  // --- Drag and Drop ---
  function handleDragStart(e, itemId) {
    dragItemId = itemId;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(itemId));
  }

  function handleDragEnd() {
    dragItemId = null;
    dragOverTarget = null;
  }

  function handleDragOver(e, target) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    dragOverTarget = target;
  }

  function handleDragLeave(target) {
    if (dragOverTarget === target) dragOverTarget = null;
  }

  function handleDrop(e, folderId) {
    e.preventDefault();
    const itemId = parseInt(e.dataTransfer.getData('text/plain'), 10);
    if (Number.isFinite(itemId)) {
      moveToFolder(itemId, folderId);
    }
    dragOverTarget = null;
    dragItemId = null;
  }
</script>

{#if hasFavourites || sortedFolders.length > 0}
  <div class="favourites-tree">
    <!-- All Favourites -->
    <div
      class="fav-folder-header clickable"
      class:selected={selectedFolderId === 'all'}
      onclick={() => handleFolderSelect('all', allFavItemIds)}
      use:clickable
    >
      <span class="expand-spacer"></span>
      <span class="folder-name">All Favourites</span>
      <span class="folder-count">{allFavItemIds.length}</span>
    </div>

    <!-- Folders -->
    {#each sortedFolders as folder (folder.id)}
      <div
        class="fav-folder"
        class:drag-over={dragOverTarget === folder.id}
        ondragover={(e) => { e.preventDefault(); handleDragOver(e, folder.id); }}
        ondragleave={() => handleDragLeave(folder.id)}
        ondrop={(e) => handleDrop(e, folder.id)}
        role="group"
      >
        <div
          class="fav-folder-header clickable"
          class:selected={selectedFolderId === folder.id}
          onclick={() => handleFolderSelect(folder.id, folder.items || [])}
          use:clickable
        >
          <span
            class="expand-toggle"
            class:expanded={expandedFolders.has(folder.id)}
            onclick={(e) => { e.stopPropagation(); toggleFolder(folder.id); }}
            use:clickable={{ tabindex: -1 }}
          >{expandedFolders.has(folder.id) ? '▾' : '▸'}</span>

          {#if editingFolderId === folder.id}
            <!-- svelte-ignore a11y_autofocus -- intentional focus on rename activation -->
            <!-- svelte-ignore a11y_click_events_have_key_events -- stopPropagation on input to prevent folder toggle -->
            <input
              class="folder-rename-input"
              type="text"
              bind:value={editingFolderName}
              onblur={finishRename}
              onkeydown={handleRenameKeydown}
              onclick={(e) => e.stopPropagation()}
              autofocus
            />
          {:else}
            <span
              class="folder-name"
              ondblclick={(e) => { e.stopPropagation(); startRename(folder); }}
            >{folder.name}</span>
          {/if}

          <span class="folder-count">{(folder.items || []).length}</span>
          <div class="folder-actions">
            <button class="folder-action-btn" onclick={(e) => { e.stopPropagation(); startRename(folder); }} title="Rename">
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M11.5 1.5l3 3L5 14H2v-3L11.5 1.5z"/>
              </svg>
            </button>
            <button class="folder-action-btn delete" onclick={(e) => { e.stopPropagation(); handleDeleteFolder(folder.id); }} title="Delete folder">
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 4l8 8M12 4l-8 8"/>
              </svg>
            </button>
          </div>
        </div>

        {#if expandedFolders.has(folder.id)}
          <div class="fav-folder-items">
            {#each (folder.items || []) as itemId (itemId)}
              <div
                class="fav-item"
                class:dragging={dragItemId === itemId}
                class:selected={selectedItemId === itemId}
                draggable="true"
                onclick={() => handleItemClick(itemId)}
                ondragstart={(e) => handleDragStart(e, itemId)}
                ondragend={handleDragEnd}
                use:clickable
              >
                <span class="expand-spacer"></span>
                <span class="fav-item-name">
                  {itemMap[itemId]?.n || `Item #${itemId}`}
                </span>
                <button class="fav-remove-btn" onclick={(e) => { e.stopPropagation(); removeFavourite(itemId); }} title="Remove">x</button>
              </div>
            {/each}
            {#if (folder.items || []).length === 0}
              <div class="fav-empty">Drop items here</div>
            {/if}
          </div>
        {/if}
      </div>
    {/each}

    <!-- Root (unfiled) items - also a drop target -->
    {#if rootItems.length > 0}
      <div
        class="fav-root-items"
        class:drag-over={dragOverTarget === 'root'}
        ondragover={(e) => { e.preventDefault(); handleDragOver(e, 'root'); }}
        ondragleave={() => handleDragLeave('root')}
        ondrop={(e) => handleDrop(e, null)}
        role="group"
      >
        {#each rootItems as itemId (itemId)}
          <div
            class="fav-item"
            class:dragging={dragItemId === itemId}
            class:selected={selectedItemId === itemId}
            draggable="true"
            onclick={() => handleItemClick(itemId)}
            ondragstart={(e) => handleDragStart(e, itemId)}
            ondragend={handleDragEnd}
            use:clickable
          >
            <span class="expand-spacer"></span>
            <span class="fav-item-name">
              {itemMap[itemId]?.n || `Item #${itemId}`}
            </span>
            <button class="fav-remove-btn" onclick={(e) => { e.stopPropagation(); removeFavourite(itemId); }} title="Remove">x</button>
          </div>
        {/each}
      </div>
    {/if}

    {#if showNewFolderButton}
      <!-- New folder button -->
      <button class="new-folder-btn" onclick={handleNewFolder}>+ Folder</button>
    {/if}
  </div>
{:else}
  <div class="fav-empty-hint">Star items to add favourites</div>
{/if}

<style>
  .favourites-tree {
    font-size: 13px;
  }

  .fav-folder {
    margin-bottom: 2px;
    border-radius: 4px;
    transition: background 0.15s ease;
  }
  .fav-folder.drag-over {
    background: rgba(59, 130, 246, 0.08);
    outline: 1px dashed var(--accent-color);
    outline-offset: -1px;
    border-radius: 4px;
  }

  .fav-folder-header {
    display: flex;
    align-items: center;
    padding: 4px 6px;
    gap: 2px;
    border-radius: 4px;
    border-left: 2px solid transparent;
    user-select: none;
    transition: all 0.15s ease;
    min-width: 0;
    overflow: hidden;
  }
  .fav-folder-header.clickable {
    cursor: pointer;
  }
  .fav-folder-header.clickable:hover {
    background-color: var(--hover-color);
  }
  .fav-folder-header.selected {
    background-color: rgba(59, 130, 246, 0.08);
    border-left-color: var(--accent-color);
  }
  .fav-folder-header:hover .folder-actions {
    opacity: 1;
  }

  .expand-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    font-size: 13px;
    color: var(--text-muted);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .expand-toggle:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .expand-spacer {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    flex-shrink: 0;
  }

  .folder-name {
    flex: 1;
    font-weight: 500;
    cursor: pointer;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .folder-rename-input {
    flex: 1;
    font-size: inherit;
    font-weight: 500;
    padding: 1px 4px;
    border: 1px solid var(--accent-color);
    border-radius: 3px;
    background: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    outline: none;
    min-width: 0;
  }

  .folder-count {
    font-size: 11px;
    color: var(--text-muted);
    flex-shrink: 0;
    margin-left: 4px;
  }

  .folder-actions {
    display: flex;
    gap: 2px;
    opacity: 0;
    transition: opacity 0.15s ease;
    flex-shrink: 0;
    margin-left: 4px;
  }

  .folder-action-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    border-radius: 3px;
    padding: 0;
    transition: all 0.15s ease;
  }
  .folder-action-btn:hover {
    background: var(--hover-color);
    color: var(--text-color);
  }
  .folder-action-btn.delete:hover {
    color: var(--error-color, #ef4444);
    background: rgba(239, 68, 68, 0.1);
  }

  .fav-folder-items {
    padding-left: 12px;
  }

  .fav-item {
    display: flex;
    align-items: center;
    padding: 4px 6px;
    border-radius: 4px;
    border-left: 2px solid transparent;
    gap: 2px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .fav-item:hover {
    background-color: var(--hover-color);
  }
  .fav-item.selected {
    background-color: rgba(22, 163, 74, 0.08);
    border-left-color: var(--success-color, #16a34a);
  }
  .fav-item.dragging {
    opacity: 0.4;
  }

  .fav-item-name {
    flex: 1;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .fav-remove-btn {
    display: none;
    width: 14px;
    height: 14px;
    font-size: 10px;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0;
    line-height: 1;
    flex-shrink: 0;
    border-radius: 2px;
    align-items: center;
    justify-content: center;
  }
  .fav-item:hover .fav-remove-btn {
    display: inline-flex;
  }
  .fav-remove-btn:hover {
    color: var(--error-color, #ef4444);
    background: rgba(239, 68, 68, 0.1);
  }

  .fav-root-items {
    border-radius: 4px;
    transition: background 0.15s ease;
  }
  .fav-root-items.drag-over {
    background: rgba(59, 130, 246, 0.05);
  }

  .fav-empty {
    font-size: 11px;
    color: var(--text-muted);
    padding: 2px 4px;
    font-style: italic;
  }

  .fav-empty-hint {
    font-size: 11px;
    color: var(--text-muted);
    padding: 4px 0;
  }

  .new-folder-btn {
    display: inline-flex;
    align-items: center;
    margin-top: 4px;
    padding: 2px 8px;
    font-size: 11px;
    border: 1px dashed var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .new-folder-btn:hover {
    border-color: var(--accent-color);
    color: var(--accent-color);
    background: rgba(59, 130, 246, 0.05);
  }
</style>
