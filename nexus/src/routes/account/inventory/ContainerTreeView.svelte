<script>
  //@ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { formatPedRaw, formatMarkupValue } from '../../market/exchange/orderUtils';

  export let items = [];
  export let editingMarkupId = null;
  export let editingMarkupValue = '';

  const dispatch = createEventDispatcher();

  let expandedPaths = new Set();
  let expandedVersion = 0; // Trigger reactivity on set changes

  // Build tree from items' container_path
  $: tree = buildTree(items);

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
            name: seg,
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

  // Depend on both tree AND expandedVersion for reactivity
  $: flatRows = (expandedVersion, flattenTree(tree, expandedPaths));
</script>

<div class="tree-view">
  {#if flatRows.length === 0}
    <p class="tree-empty">No items match your filters</p>
  {:else}
    {#each flatRows as row (row.type === 'container' ? 'c:' + row.node.path : 'i:' + row.item.id)}
      {#if row.type === 'container'}
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <div
          class="tree-row tree-container"
          class:expanded={expandedPaths.has(row.node.path)}
          on:click={() => toggleExpand(row.node.path)}
        >
          <span class="tree-indent" style="width: {row.node.depth * 12}px"></span>
          <span class="tree-arrow">
            {#if hasChildren(row.node) || row.node.items.length > 0}
              {expandedPaths.has(row.node.path) ? '▾' : '▸'}
            {:else}
              ·
            {/if}
          </span>
          <span class="tree-name">{row.node.name}</span>
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
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <div
          class="tree-row tree-item"
          on:click={() => handleItemClick(row.item)}
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
              <!-- svelte-ignore a11y-autofocus -->
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
              />
            {:else}
              <!-- svelte-ignore a11y-click-events-have-key-events -->
              <span
                class="mu-cell"
                class:has-mu={row.item._markup != null}
                on:click|stopPropagation={() => row.item.item_id > 0 && startMarkupEdit(row.item)}
                title="Click to edit markup"
              >
                {#if row.item._markup != null}
                  {row.item._isAbsolute ? formatMarkupValue(row.item._markup, true) : formatMarkupValue(row.item._markup, false)}
                {:else}
                  <span class="text-muted">{row.item._isAbsolute ? '+0' : '100%'}</span>
                {/if}
              </span>
            {/if}
          </span>
          <span class="tree-col tree-col-total" class:value-custom={row.item._valueSource === 'custom'} class:value-default={row.item._valueSource === 'default' || row.item._totalValue == null}>
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
  }

  .tree-item-name {
    font-weight: 400;
    font-size: 0.82rem;
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
