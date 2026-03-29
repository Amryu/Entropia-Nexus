<script>
  //@ts-nocheck
  import { addToast } from '$lib/stores/toasts.js';
  import { apiCall } from '$lib/util.js';
  import { getTopCategory } from '../../market/exchange/orderUtils';
  import NegotiableFilterModal from './NegotiableFilterModal.svelte';

  /**
   * @typedef {Object} Props
   * @property {boolean} [show]
   * @property {Array} [inventoryItems] - All inventory items
   * @property {Map} [itemLookup] - item_id → slim item
   * @property {() => void} [onclose]
   * @property {(result: any) => void} [onsaved]
   */

  /** @type {Props} */
  let {
    show = false,
    inventoryItems = [],
    itemLookup = new Map(),
    onclose,
    onsaved,
  } = $props();

  // Node states: 'unchecked' | 'included' | 'excluded'
  let nodeStates = $state(new Map()); // path → state
  let nodeFilters = $state(new Map()); // path → filter config or null
  let saving = $state(false);
  let loading = $state(true);
  let syncResult = $state(null);
  let showFilterModal = $state(false);
  let filterModalNode = $state(null);
  let filterModalItems = $state([]);

  /** Strip '#refID' suffix from a container path segment for display. */
  function stripRef(segment) {
    const idx = segment.lastIndexOf('#');
    if (idx > 0 && /^\d+$/.test(segment.substring(idx + 1))) {
      return segment.substring(0, idx);
    }
    return segment;
  }

  function buildTree(items) {
    const root = { children: {}, items: [], path: '', name: 'Root', depth: -1 };
    for (const item of items) {
      let path = item.container_path;
      if (!path && item.container) path = `STORAGE (${item.container})`;
      if (!path) continue; // skip items without a path
      const segments = path.split(' > ');
      let node = root;
      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        if (!node.children[seg]) {
          node.children[seg] = {
            name: stripRef(seg),
            path: segments.slice(0, i + 1).join(' > '),
            depth: i,
            children: {},
            items: [],
          };
        }
        node = node.children[seg];
      }
      node.items.push(item);
    }

    function countItems(node) {
      let count = node.items.length;
      for (const child of Object.values(node.children)) {
        count += countItems(child);
      }
      node.totalCount = count;
      return count;
    }
    countItems(root);

    function toArray(childrenObj) {
      return Object.values(childrenObj)
        .map(n => ({ ...n, children: toArray(n.children) }))
        .sort((a, b) => a.name.localeCompare(b.name));
    }
    return toArray(root.children);
  }

  let tree = $derived(buildTree(inventoryItems));

  // Check if a node is effectively included (directly or via parent)
  function getEffectiveState(path) {
    const direct = nodeStates.get(path);
    if (direct === 'excluded') return 'excluded';
    if (direct === 'included') return 'included';
    // Check ancestors
    const segments = path.split(' > ');
    for (let i = segments.length - 1; i >= 1; i--) {
      const ancestorPath = segments.slice(0, i).join(' > ');
      const aState = nodeStates.get(ancestorPath);
      if (aState === 'included') return 'inherited'; // included via parent
      if (aState === 'excluded') return 'unchecked'; // parent excluded
    }
    return 'unchecked';
  }

  function isParentIncluded(path) {
    const segments = path.split(' > ');
    for (let i = segments.length - 1; i >= 1; i--) {
      const ancestorPath = segments.slice(0, i).join(' > ');
      if (nodeStates.get(ancestorPath) === 'included') return true;
    }
    return false;
  }

  function toggleNode(path) {
    const current = nodeStates.get(path);
    const parentIncl = isParentIncluded(path);

    if (parentIncl) {
      // Child of included parent: toggle between inherited (unchecked in map) and excluded
      if (current === 'excluded') {
        nodeStates.delete(path);
      } else {
        nodeStates.set(path, 'excluded');
        nodeFilters.delete(path);
      }
    } else {
      // Top-level toggle: unchecked ↔ included
      if (current === 'included') {
        nodeStates.delete(path);
        nodeFilters.delete(path);
        // Also remove any child exclusions
        for (const [k] of nodeStates) {
          if (k.startsWith(path + ' > ')) { nodeStates.delete(k); nodeFilters.delete(k); }
        }
      } else {
        nodeStates.set(path, 'included');
      }
    }
    nodeStates = new Map(nodeStates); // trigger reactivity
    nodeFilters = new Map(nodeFilters);
  }

  function openFilterModal(node) {
    filterModalNode = node;
    // Collect all items recursively in this container
    const items = [];
    function collect(n) {
      items.push(...n.items);
      for (const child of n.children) collect(child);
    }
    collect(node);
    filterModalItems = items;
    showFilterModal = true;
  }

  function handleFilterSave(filter) {
    if (filterModalNode) {
      const path = filterModalNode.path;
      if (filter) {
        nodeFilters.set(path, filter);
        // Ensure inherited nodes are explicitly included so their filter is persisted
        if (!nodeStates.has(path)) {
          nodeStates.set(path, 'included');
          nodeStates = new Map(nodeStates);
        }
      } else {
        nodeFilters.delete(path);
      }
      nodeFilters = new Map(nodeFilters);
    }
    showFilterModal = false;
    filterModalNode = null;
  }

  // Resolve preview of items that will be listed
  let previewItems = $derived((() => {
    const items = [];
    const seen = new Set();

    function matchesFilter(item, filter) {
      if (!filter) return true;
      const slim = itemLookup.get(item.item_id);
      if (filter.mode === 'whitelist') return filter.itemIds?.includes(item.item_id);
      if (filter.mode === 'blacklist') return !filter.itemIds?.includes(item.item_id);
      if (filter.mode === 'match') {
        let nameMatch = true;
        if (filter.substring) {
          if (filter.useRegex) {
            try { nameMatch = new RegExp(filter.substring, 'i').test(item.item_name); } catch { nameMatch = false; }
          } else {
            nameMatch = item.item_name.toLowerCase().includes(filter.substring.toLowerCase());
          }
        }
        let typeMatch = true;
        if (filter.itemTypes?.length > 0) {
          const cat = slim?.t ? getTopCategory(slim.t) : 'Other';
          typeMatch = filter.itemTypes.includes(cat);
        }
        const result = nameMatch && typeMatch;
        return filter.negate ? !result : result;
      }
      return true;
    }

    function isPathExcluded(path) {
      return nodeStates.get(path) === 'excluded';
    }

    // Find the nearest ancestor's filter for a given path
    function getApplicableFilter(path) {
      // Only use the directly-included node's filter, not ancestors
      // This matches the backend resolveNegotiableConfig behavior
      const directFilter = nodeFilters.get(path);
      if (directFilter) return directFilter;
      // Check if this node is directly included (has its own filter)
      if (nodeStates.get(path) === 'included') return null; // included with no filter = all items
      // Inherited node: find the nearest included ancestor's filter
      const segments = path.split(' > ');
      for (let i = segments.length - 1; i >= 1; i--) {
        const ancestorPath = segments.slice(0, i).join(' > ');
        if (nodeStates.get(ancestorPath) === 'included') {
          return nodeFilters.get(ancestorPath) || null;
        }
      }
      return null;
    }

    function collectNode(node) {
      const eff = getEffectiveState(node.path);
      if (eff === 'excluded' || eff === 'unchecked') return;
      const filter = getApplicableFilter(node.path);

      for (const item of node.items) {
        if (!item.item_id || item.item_id === 0) continue;
        if (!matchesFilter(item, filter)) continue;
        // Non-stackable items have instance_key — include it to avoid merging condition items
        const key = item.instance_key
          ? `${item.item_id}::${item.container || ''}::${item.instance_key}`
          : `${item.item_id}::${item.container || ''}`;
        if (seen.has(key)) continue;
        seen.add(key);
        const slim = itemLookup.get(item.item_id);
        items.push({
          _key: key,
          item_id: item.item_id,
          item_name: slim?.n || item.item_name,
          quantity: item.quantity || 1,
          type: slim?.t || null,
          planet: item.container || null,
        });
      }
      for (const child of node.children) {
        if (!isPathExcluded(child.path)) collectNode(child);
      }
    }

    for (const node of tree) collectNode(node);
    return items.sort((a, b) => a.item_name.localeCompare(b.item_name));
  })());

  let listingCount = $derived(previewItems.length);
  let showPreview = $state(false);

  // Flatten tree for rendering
  function flattenTree(nodes, expandedSet) {
    const result = [];
    for (const node of nodes) {
      result.push(node);
      if (expandedSet.has(node.path)) {
        result.push(...flattenTree(node.children, expandedSet));
      }
    }
    return result;
  }

  let expandedPaths = $state(new Set());
  let expandedVersion = $state(0);

  function toggleExpand(path) {
    if (expandedPaths.has(path)) expandedPaths.delete(path);
    else expandedPaths.add(path);
    expandedVersion++;
  }

  let flatNodes = $derived((expandedVersion, flattenTree(tree, expandedPaths)));

  // Load existing config on open
  $effect(() => {
    if (show) {
      loading = true;
      syncResult = null;
      loadConfig();
    }
  });

  async function loadConfig() {
    try {
      const res = await fetch('/api/users/inventory/negotiable');
      if (res.ok) {
        const config = await res.json();
        if (config?.nodes) {
          nodeStates = new Map();
          nodeFilters = new Map();
          for (const n of config.nodes) {
            nodeStates.set(n.path, n.state);
            if (n.filter) nodeFilters.set(n.path, n.filter);
          }
          nodeStates = new Map(nodeStates);
          nodeFilters = new Map(nodeFilters);
          // Auto-expand paths that have config
          for (const n of config.nodes) {
            const segments = n.path.split(' > ');
            for (let i = 0; i < segments.length - 1; i++) {
              expandedPaths.add(segments.slice(0, i + 1).join(' > '));
            }
          }
          expandedVersion++;
        }
      }
    } catch (err) {
      console.error('Error loading negotiable config:', err);
    } finally {
      loading = false;
    }
  }

  async function save() {
    saving = true;
    syncResult = null;
    try {
      const nodes = [];
      for (const [path, state] of nodeStates) {
        const entry = { path, state };
        if (state === 'included') {
          const filter = nodeFilters.get(path) || null;
          if (filter) entry.filter = filter;
        }
        nodes.push(entry);
      }
      const res = await fetch('/api/users/inventory/negotiable', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to save');
      syncResult = data;
      addToast(`Listed ${data.created} items, removed ${data.removed || 0}${data.skipped ? `, skipped ${data.skipped}` : ''}`, 'success');
      onsaved?.(data);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      saving = false;
    }
  }

  async function deleteConfig() {
    saving = true;
    try {
      const res = await fetch('/api/users/inventory/negotiable', { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to delete');
      nodeStates = new Map();
      nodeFilters = new Map();
      syncResult = null;
      addToast(`Config removed, ${data.closed} listings closed`, 'success');
      onsaved?.(data);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      saving = false;
    }
  }
</script>

{#if show}
  <div
    class="dialog-overlay"
    role="button"
    tabindex="-1"
    onclick={(e) => e.target === e.currentTarget && onclose?.()}
    onkeydown={(e) => e.key === 'Escape' && !showFilterModal && onclose?.()}
  >
    <div class="dialog">
      <div class="dialog-header">
        <h3>List Inventory on Exchange</h3>
        <span class="listing-count">{listingCount} item{listingCount !== 1 ? 's' : ''} selected</span>
        <button class="close-btn" onclick={() => onclose?.()}>&times;</button>
      </div>

      <div class="dialog-body">
        {#if loading}
          <p class="loading-text">Loading configuration...</p>
        {:else}
          <p class="help-text">Select containers to list their contents on the exchange without a price. Buyers can then propose offers.</p>

          <div class="tree-container">
            {#each flatNodes as node (node.path)}
              {@const effState = getEffectiveState(node.path)}
              {@const directState = nodeStates.get(node.path)}
              {@const isIncluded = effState === 'included' || effState === 'inherited'}
              {@const isExcluded = effState === 'excluded'}
              {@const hasFilter = nodeFilters.has(node.path)}
              {@const hasChildren = node.children.length > 0}
              <div
                class="tree-row"
                class:included={isIncluded}
                class:excluded={isExcluded}
              >
                <span class="tree-indent" style="width: {node.depth * 16}px"></span>

                {#if hasChildren}
                  <button class="tree-expand" class:expanded={expandedPaths.has(node.path)} onclick={() => toggleExpand(node.path)}>
                    <span class="chevron">&#9656;</span>
                  </button>
                {:else}
                  <span class="tree-expand-spacer"></span>
                {/if}

                <button
                  class="tree-checkbox"
                  class:checked={directState === 'included'}
                  class:inherited={effState === 'inherited'}
                  class:excluded-check={isExcluded}
                  onclick={() => toggleNode(node.path)}
                  title={isExcluded ? 'Click to re-include' : (isIncluded ? 'Click to exclude' : 'Click to include')}
                >
                  {#if isExcluded}
                    ✕
                  {:else if directState === 'included'}
                    ✓
                  {:else if effState === 'inherited'}
                    ✓
                  {:else}
                    &nbsp;
                  {/if}
                </button>

                <span class="tree-name" class:strikethrough={isExcluded}>
                  {node.name}
                </span>

                <span class="tree-count">{node.totalCount}</span>

                {#if isIncluded && !isExcluded}
                  <button
                    class="configure-btn"
                    class:has-filter={hasFilter}
                    onclick={(e) => { e.stopPropagation(); openFilterModal(node); }}
                    title={hasFilter ? 'Edit filter' : 'Configure filter'}
                  >
                    {hasFilter ? '⚙ filtered' : '⚙'}
                  </button>
                {/if}
              </div>
            {/each}

            {#if flatNodes.length === 0}
              <p class="empty-text">No inventory containers found. Import your inventory first.</p>
            {/if}
          </div>

          {#if listingCount > 0}
            <button class="preview-toggle" onclick={() => showPreview = !showPreview}>
              {showPreview ? '▾' : '▸'} Preview ({listingCount} item{listingCount !== 1 ? 's' : ''})
            </button>
            {#if showPreview}
              <div class="preview-list">
                {#each previewItems as item (item._key)}
                  <div class="preview-row">
                    <span class="preview-name">{item.item_name}</span>
                    {#if item.type}
                      <span class="preview-type">{item.type}</span>
                    {/if}
                    <span class="preview-qty">x{item.quantity.toLocaleString()}</span>
                  </div>
                {/each}
              </div>
            {/if}
          {/if}

          {#if syncResult}
            <div class="sync-result">
              Created: {syncResult.created} · Closed: {syncResult.closed}
              {#if syncResult.skipped > 0} · Skipped: {syncResult.skipped}{/if}
            </div>
          {/if}
        {/if}
      </div>

      <div class="dialog-actions">
        {#if nodeStates.size > 0}
          <button class="btn btn-danger" onclick={deleteConfig} disabled={saving}>
            Remove All Listings
          </button>
        {/if}
        <span class="spacer"></span>
        <button class="btn btn-secondary" onclick={() => onclose?.()}>Close</button>
        <button class="btn btn-primary" onclick={save} disabled={saving || loading || nodeStates.size === 0}>
          {saving ? 'Saving...' : 'Save & Sync'}
        </button>
      </div>
    </div>
  </div>

  <NegotiableFilterModal
    show={showFilterModal}
    node={filterModalNode}
    items={filterModalItems}
    {itemLookup}
    existingFilter={filterModalNode ? nodeFilters.get(filterModalNode.path) || null : null}
    onclose={() => { showFilterModal = false; filterModalNode = null; }}
    onsave={handleFilterSave}
  />
{/if}

<style>
  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .dialog {
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 600px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
  }

  .dialog-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border-color);
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 1rem;
  }

  .listing-count {
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
    font-size: 1.3rem;
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }

  .close-btn:hover { color: var(--text-color); }

  .dialog-body {
    padding: 0.75rem 1rem;
    overflow-y: auto;
    flex: 1;
  }

  .help-text {
    font-size: 0.82rem;
    color: var(--text-muted);
    margin: 0 0 0.75rem 0;
  }

  .loading-text, .empty-text {
    text-align: center;
    color: var(--text-muted);
    padding: 2rem;
    font-size: 0.85rem;
  }

  .tree-container {
    border: 1px solid var(--border-color);
    border-radius: 4px;
    max-height: 50vh;
    overflow-y: auto;
  }

  .tree-row {
    display: flex;
    align-items: center;
    padding: 0.3rem 0.5rem;
    gap: 4px;
    user-select: none;
    transition: background 0.1s;
  }

  .tree-row:hover {
    background: var(--hover-color);
  }

  .tree-row.included {
    background: color-mix(in srgb, var(--accent-color) 8%, transparent);
  }

  .tree-row.excluded {
    opacity: 0.6;
  }

  .tree-indent { flex-shrink: 0; }

  .tree-expand {
    width: 20px;
    height: 20px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.85rem;
    color: var(--text-muted);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .tree-expand-spacer {
    width: 20px;
    flex-shrink: 0;
  }

  .chevron {
    display: inline-block;
    transition: transform 0.15s ease;
    font-size: 1.1rem;
  }

  .tree-expand.expanded .chevron {
    transform: rotate(90deg);
  }

  .tree-checkbox {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background: var(--secondary-color);
    color: var(--text-color);
    font-size: 0.7rem;
    cursor: pointer;
    padding: 0;
    line-height: 1;
  }

  .tree-checkbox.checked {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: #fff;
  }

  .tree-checkbox.inherited {
    background: color-mix(in srgb, var(--accent-color) 40%, var(--secondary-color));
    border-color: var(--accent-color);
    color: #fff;
    opacity: 0.7;
  }

  .tree-checkbox.excluded-check {
    background: var(--error-color);
    border-color: var(--error-color);
    color: #fff;
  }

  .tree-name {
    flex: 1;
    font-size: 0.85rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tree-name.strikethrough {
    text-decoration: line-through;
    color: var(--text-muted);
  }

  .tree-count {
    font-size: 0.72rem;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .configure-btn {
    flex-shrink: 0;
    background: none;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    color: var(--text-muted);
    font-size: 0.72rem;
    cursor: pointer;
    padding: 1px 6px;
    transition: all 0.15s;
  }

  .configure-btn:hover {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }

  .configure-btn.has-filter {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }

  .preview-toggle {
    background: none;
    border: none;
    color: var(--accent-color);
    font-size: 0.82rem;
    cursor: pointer;
    padding: 0.4rem 0;
    text-align: left;
  }

  .preview-toggle:hover {
    text-decoration: underline;
  }

  .preview-list {
    max-height: 200px;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--secondary-color);
    margin-bottom: 0.5rem;
  }

  .preview-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.2rem 0.6rem;
    font-size: 0.78rem;
  }

  .preview-row:nth-child(even) {
    background: var(--hover-color);
  }

  .preview-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .preview-type {
    font-size: 0.7rem;
    color: var(--text-muted);
    padding: 0 3px;
    border: 1px solid var(--border-color);
    border-radius: 2px;
  }

  .preview-qty {
    font-size: 0.72rem;
    color: var(--text-muted);
  }

  .sync-result {
    margin-top: 0.75rem;
    padding: 0.5rem 0.75rem;
    background: var(--secondary-color);
    border-radius: 4px;
    font-size: 0.82rem;
    color: var(--text-muted);
  }

  .dialog-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    border-top: 1px solid var(--border-color);
  }

  .spacer { flex: 1; }

  .btn {
    padding: 0.4rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
  }

  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-secondary { background: var(--secondary-color); color: var(--text-color); }
  .btn-primary { background: var(--accent-color); color: #fff; border-color: var(--accent-color); }
  .btn-danger { background: var(--error-color); color: #fff; border-color: var(--error-color); }
</style>
