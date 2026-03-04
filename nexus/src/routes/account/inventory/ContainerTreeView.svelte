<script>
  //@ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { clickable } from '$lib/actions/clickable.js';
  import { formatPedRaw, formatMarkupValue } from '../../market/exchange/orderUtils';

  export let items = [];
  export let editingMarkupId = null;
  export let editingMarkupValue = '';
  export let containerNames = new Map();

  const dispatch = createEventDispatcher();

  let expandedPaths = new Set();
  let expandedVersion = 0; // Trigger reactivity on set changes

  // Container rename state
  let editingContainerPath = null;
  let editingContainerName = '';

  // Build tree from items' container_path
  $: tree = buildTree(items);

  /** Strip '#refID' suffix from a container path segment for display. */
  function stripContainerRef(segment) {
    const idx = segment.lastIndexOf('#');
    if (idx > 0 && /^\d+$/.test(segment.substring(idx + 1))) {
      return segment.substring(0, idx);
    }
    return segment;
  }

  function buildTree(items) {
    const root = { children: {}, items: [], totalCount: 0, totalValue: 0 };

    for (const item of items) {
      // Use container_path when available; otherwise construct from container field
      let path = item.container_path;
      if (!path && item.container) {
        path = `STORAGE (${item.container})`;
      }
      if (!path) path = 'Unknown';
      const segments = path.split(' > ');
      let node = root;

      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        if (!node.children[seg]) {
          node.children[seg] = {
            name: stripContainerRef(seg),
            path: segments.slice(0, i + 1).join(' > '),
            depth: i,
            children: {},
            items: [],
            totalCount: 0,
            totalValue: 0,
          };
        }
        node = node.children[seg];
      }

      // Add item to its deepest container
      node.items.push(item);
    }

    // Compute totals bottom-up
    function computeTotals(node) {
      let count = node.items.length;
      let value = node.items.reduce((sum, it) => sum + (it._totalValue || 0), 0);

      for (const child of Object.values(node.children)) {
        computeTotals(child);
        count += child.totalCount;
        value += child.totalValue;
      }

      node.totalCount = count;
      node.totalValue = value;
    }

    computeTotals(root);

    // Convert to sorted arrays
    function toArray(childrenObj) {
      return Object.values(childrenObj)
        .map(node => ({
          ...node,
          children: toArray(node.children),
        }))
        .sort((a, b) => a.name.localeCompare(b.name));
    }

    return toArray(root.children);
  }

  function toggleExpand(path) {
    if (expandedPaths.has(path)) {
      expandedPaths.delete(path);
    } else {
      expandedPaths.add(path);
    }
    expandedPaths = expandedPaths;
    expandedVersion++;
  }

  function handleItemClick(item) {
    dispatch('rowClick', { row: item });
  }

  function hasChildren(node) {
    return node.children && node.children.length > 0;
  }

  function flattenTree(nodes, expanded) {
    const result = [];
    for (const node of nodes) {
      result.push({ type: 'container', node });
      if (expanded.has(node.path)) {
        // Show child containers first
        result.push(...flattenTree(node.children, expanded));
        // Then show direct items of this container
        for (const item of node.items) {
          result.push({ type: 'item', item, depth: node.depth + 1 });
        }
      }
    }
    return result;
  }

  function startMarkupEdit(item) {
    dispatch('startMarkupEdit', { item });
  }

  function handleMarkupInput() {
    dispatch('markupInput', { value: editingMarkupValue });
  }

  function finishMarkupEdit() {
    dispatch('finishMarkupEdit');
  }

  // --- Container rename ---

  function startContainerRename(node) {
    editingContainerPath = node.path;
    editingContainerName = containerNames?.get(node.path) || node.name;
  }

  function finishContainerRename() {
    if (editingContainerPath == null) return;
    const path = editingContainerPath;
    const name = editingContainerName.trim();

    // Extract original segment name from the path
    const segments = path.split(' > ');
    const originalName = segments[segments.length - 1];

    if (!name || name === originalName) {
      // Revert to default — delete custom name
      dispatch('deleteContainerName', { path });
    } else {
      dispatch('saveContainerName', { path, name, itemName: originalName });
    }
    editingContainerPath = null;
    editingContainerName = '';
  }

  function cancelContainerRename() {
    editingContainerPath = null;
    editingContainerName = '';
  }

  // Depend on both tree AND expandedVersion for reactivity
  $: flatRows = (expandedVersion, flattenTree(tree, expandedPaths));
</script>

<div class="tree-view">
  {#if flatRows.length === 0}
    <p class="tree-empty">No items match your filters</p>
  {:else}
    {#each flatRows as row (row.type === 'container' ? 'c:' + row.node.path : 'i:' + row.item.id)}
      {#if row.type === 'container'}
        <div
          class="tree-row tree-container"
          class:expanded={expandedPaths.has(row.node.path)}
          on:click={() => editingContainerPath !== row.node.path && toggleExpand(row.node.path)}
          use:clickable
        >
          <span class="tree-indent" style="width: {row.node.depth * 12}px"></span>
          <span class="tree-arrow">
            {#if hasChildren(row.node) || row.node.items.length > 0}
              {expandedPaths.has(row.node.path) ? '▾' : '▸'}
            {:else}
              ·
            {/if}
          </span>
          <span class="tree-name">
            {#if editingContainerPath === row.node.path}
              <!-- svelte-ignore a11y-autofocus -- intentional focus on inline edit activation -->
              <input
                type="text"
                class="container-name-input"
                bind:value={editingContainerName}
                on:blur={finishContainerRename}
                on:keydown={(e) => {
                  if (e.key === 'Enter') finishContainerRename();
                  if (e.key === 'Escape') cancelContainerRename();
                }}
                on:click|stopPropagation
                autofocus
                maxlength="100"
              />
            {:else}
              {@const customName = containerNames?.get(row.node.path)}
              <span
                class="container-label"
                class:has-custom-name={!!customName}
                title={customName ? `Original: ${row.node.name}` : row.node.name}
              >
                {customName || row.node.name}
              </span>
              {#if row.node.depth > 0}
                <span
                  class="rename-btn"
                  role="button"
                  tabindex="0"
                  on:click|stopPropagation={() => startContainerRename(row.node)}
                  on:keydown|stopPropagation={(e) => e.key === 'Enter' && startContainerRename(row.node)}
                  title="Rename container"
                >&#9998;</span>
              {/if}
            {/if}
          </span>
          <span class="tree-col tree-col-value">
            {#if row.node.totalValue > 0}
              {formatPedRaw(row.node.totalValue)} PED
            {:else}
              -
            {/if}
          </span>
          <span class="tree-col tree-col-count">{row.node.totalCount} {row.node.totalCount === 1 ? 'item' : 'items'}</span>
        </div>
      {:else}
        <div
          class="tree-row tree-item"
          on:click={() => handleItemClick(row.item)}
          use:clickable
        >
          <span class="tree-indent" style="width: {row.depth * 12}px"></span>
          <span class="tree-arrow"></span>
          <span class="tree-name tree-item-name">{row.item.item_name}</span>
          <span class="tree-col tree-col-tt">
            {row.item._ttValue != null ? formatPedRaw(row.item._ttValue) + ' PED' : '-'}
          </span>
          <span class="tree-col tree-col-qty">{row.item.quantity?.toLocaleString() ?? '-'}</span>
          <span class="tree-col tree-col-mu">
            {#if editingMarkupId === row.item.item_id}
              <!-- svelte-ignore a11y-autofocus -- intentional focus on inline edit activation -->
              <input
                type="number"
                class="mu-input"
                bind:value={editingMarkupValue}
                on:input={handleMarkupInput}
                on:blur={finishMarkupEdit}
                on:keydown={(e) => e.key === 'Enter' && finishMarkupEdit()}
                on:click|stopPropagation
                autofocus
                step="0.01"
                placeholder={row.item._isAbsolute ? '+0' : '100%'}
              />
            {:else}
              <span
                class="mu-cell"
                class:has-mu={row.item._markup != null}
                class:has-market={row.item._markup == null && row.item._marketPrice != null}
                on:click|stopPropagation={() => row.item.item_id > 0 && startMarkupEdit(row.item)}
                title="Click to edit markup"
                use:clickable
              >
                {#if row.item._markup != null}
                  {row.item._isAbsolute ? formatMarkupValue(row.item._markup, true) : formatMarkupValue(row.item._markup, false)}
                {:else if row.item._marketPrice != null}
                  {row.item._isAbsolute ? formatMarkupValue(row.item._marketPrice, true) : formatMarkupValue(row.item._marketPrice, false)}
                {:else}
                  <span class="text-muted">{row.item._isAbsolute ? '+0' : '100%'}</span>
                {/if}
              </span>
            {/if}
          </span>
          <span class="tree-col tree-col-total" class:value-custom={row.item._valueSource === 'custom'} class:value-exchange={row.item._valueSource === 'exchange'} class:value-default={row.item._valueSource === 'default' || row.item._totalValue == null}>
            {row.item._totalValue != null ? formatPedRaw(row.item._totalValue) + ' PED' : '-'}
          </span>
        </div>
      {/if}
    {/each}
  {/if}
</div>

<style>
  .tree-view {
    display: flex;
    flex-direction: column;
    padding-bottom: 1rem;
  }

  .tree-empty {
    color: var(--text-muted);
    text-align: center;
    padding: 2rem;
    margin: 0;
  }

  .tree-row {
    display: flex;
    align-items: center;
    padding: 0.3rem 0.75rem;
    cursor: pointer;
    border-radius: 4px;
    user-select: none;
    transition: background 0.1s;
  }

  .tree-row:hover {
    background: var(--hover-color);
  }

  .tree-container.expanded {
    background: var(--secondary-color);
  }

  .tree-indent {
    flex-shrink: 0;
  }

  .tree-arrow {
    width: 16px;
    flex-shrink: 0;
    text-align: center;
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .tree-name {
    flex: 1;
    font-size: 0.85rem;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    padding-left: 4px;
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
  }

  .tree-item-name {
    font-weight: 400;
    font-size: 0.82rem;
  }

  .container-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .container-label.has-custom-name {
    color: var(--accent-color);
  }

  .rename-btn {
    flex-shrink: 0;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 0.7rem;
    padding: 0 2px;
    opacity: 0;
    transition: opacity 0.15s;
    line-height: 1;
  }

  .tree-container:hover .rename-btn {
    opacity: 0.5;
  }

  .rename-btn:hover {
    opacity: 1 !important;
    color: var(--accent-color);
  }

  .container-name-input {
    width: 100%;
    padding: 1px 4px;
    border: 1px solid var(--accent-color);
    border-radius: 3px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 0.85rem;
    box-sizing: border-box;
  }

  .container-name-input:focus {
    outline: none;
  }

  .tree-col {
    flex-shrink: 0;
    text-align: right;
    font-size: 0.75rem;
    white-space: nowrap;
    padding: 0 0.25rem;
  }

  /* Container columns */
  .tree-col-value {
    width: 110px;
    color: var(--accent-color);
    font-weight: 500;
  }

  .tree-col-count {
    width: 80px;
    color: var(--text-muted);
  }

  /* Item columns: TT, Qty, MU, Value */
  .tree-col-tt {
    width: 85px;
    color: var(--text-muted);
  }

  .tree-col-qty {
    width: 55px;
    color: var(--text-muted);
  }

  .tree-col-mu {
    width: 85px;
  }

  .tree-col-total {
    width: 95px;
    font-weight: 500;
  }

  .tree-col-total.value-custom {
    color: var(--accent-color);
  }

  .tree-col-total.value-exchange {
    color: var(--text-color);
  }

  .tree-col-total.value-default {
    color: var(--text-muted);
  }

  /* Markup editing */
  .mu-cell {
    cursor: pointer;
    padding: 1px 4px;
    border-radius: 3px;
    border: 1px dashed var(--border-color);
    display: inline-block;
    width: 100%;
    text-align: right;
    color: var(--text-muted);
    box-sizing: border-box;
  }

  .mu-cell:hover {
    background: var(--hover-color);
    border-color: var(--accent-color);
  }

  .mu-cell.has-mu {
    color: var(--accent-color);
    border-color: transparent;
  }

  .mu-cell.has-market {
    color: var(--text-color);
    border-color: transparent;
  }

  .mu-cell.has-mu:hover {
    border-color: var(--accent-color);
  }

  .mu-input {
    width: 100%;
    padding: 1px 3px;
    border: 1px solid var(--accent-color);
    border-radius: 3px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 0.75rem;
    text-align: right;
    box-sizing: border-box;
  }

  .mu-input:focus {
    outline: none;
  }

  .text-muted {
    color: var(--text-muted);
  }
</style>
