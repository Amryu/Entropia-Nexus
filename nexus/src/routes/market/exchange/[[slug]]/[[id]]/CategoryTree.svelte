<script>
  // @ts-nocheck
  export let categories = {};
  export let onSelectCategory;
  export let category = null; // For recursive component use
  export let selectedPath = null;
  export let expandedNodes = new Set();
  export let toggleExpanded = null;
  export let getItemCount = null;
  export let handleCategorySelect = null;

  // Initialize functions if not provided (for root component)
  if (!toggleExpanded) {
    toggleExpanded = function(nodeId, categoryNode) {
      if (expandedNodes.has(nodeId)) {
        // Collapsing — if selected category is a descendant, select the parent instead
        if (categoryNode && selectedPath) {
          const parentDisplay = categoryNode.path.map(formatCategoryName).join(' > ');
          if (selectedPath !== parentDisplay && selectedPath.startsWith(parentDisplay + ' > ')) {
            handleCategorySelect(categoryNode);
          }
        }
        expandedNodes.delete(nodeId);
      } else {
        expandedNodes.add(nodeId);
      }
      expandedNodes = new Set(expandedNodes); // Trigger reactivity
    };
  }

  if (!getItemCount) {
    getItemCount = function(category) {
      if (category.items && Array.isArray(category.items)) {
        return category.items.length;
      }
      let count = 0;
      if (category.children) {
        for (const child of category.children) {
          count += getItemCount(child);
        }
      }
      return count;
    };
  }

  if (!handleCategorySelect) {
    handleCategorySelect = function(category) {
      // Allow selecting any node; if branch, aggregate all leaf items below
      let items = [];
      if (category.items && Array.isArray(category.items)) {
        items = category.items;
      } else if (category.children && category.children.length > 0) {
        const gather = (node) => {
          if (node.items && Array.isArray(node.items)) items.push(...node.items);
          if (node.children) node.children.forEach(gather);
        };
        category.children.forEach(gather);
      }
      // Emit display-formatted path + raw key path for unambiguous URL routing
      const displayPath = category.path.map(formatCategoryName).join(' > ');
      onSelectCategory(displayPath, items, category.path);
    };
  }

  // Convert the nested object structure into a tree format
  function buildCategoryTree(obj, path = []) {
    const tree = [];

    for (const [key, value] of Object.entries(obj)) {
      const currentPath = [...path, key];
      const displayName = formatCategoryName(key);

      if (Array.isArray(value)) {
        // This is a leaf node with items
        tree.push({
          id: currentPath.join('.'),
          name: displayName,
          path: currentPath,
          items: value,
          children: [],
          level: path.length
        });
      } else if (typeof value === 'object' && value !== null) {
        // This is a branch node
        const children = buildCategoryTree(value, currentPath);

        tree.push({
          id: currentPath.join('.'),
          name: displayName,
          path: currentPath,
          items: null,
          children: children,
          level: path.length
        });
      }
    }

    return tree;
  }

  function formatCategoryName(key) {
    if (key === 'all') return 'All';
    return key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ');
  }

  $: categoryTree = category ? [] : buildCategoryTree(categories);
</script>

<div class="category-tree">
  {#each categoryTree as category}
    <svelte:self
      category={category}
      {onSelectCategory}
      {expandedNodes}
      {toggleExpanded}
      {getItemCount}
      {handleCategorySelect}
      {selectedPath}
    />
  {/each}
</div>

<!-- Component for individual category items -->
{#if category}
  <div class="category-item" style="padding-left: {category.level * 8}px">
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div
      class="category-header clickable {selectedPath === category.path.map(formatCategoryName).join(' > ') ? 'selected' : ''}"
      on:click={() => handleCategorySelect(category)}
      on:keydown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleCategorySelect(category);
        }
      }}
      role="button"
      tabindex="0"
    >
      {#if category.children.length > 0}
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <span
          class="expand-toggle {expandedNodes.has(category.id) ? 'expanded' : ''}"
          on:click|stopPropagation={() => toggleExpanded(category.id, category)}
          role="button"
          tabindex="-1"
        >{expandedNodes.has(category.id) ? '▾' : '▸'}</span>
      {:else}
        <span class="expand-spacer"></span>
      {/if}
      <span class="category-name">{category.name}</span>
      {#if getItemCount(category) > 0}
        <span class="item-count">{getItemCount(category)}</span>
      {/if}
    </div>

    {#if category.children.length > 0 && expandedNodes.has(category.id)}
      <div class="category-children" style="margin-left: -{category.level * 8}px">
        {#each category.children as child}
          <svelte:self
            category={child}
            {onSelectCategory}
            {expandedNodes}
            {toggleExpanded}
            {getItemCount}
            {handleCategorySelect}
            {selectedPath}
          />
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .category-tree {
    font-size: 13px;
  }

  .category-item {
    margin-bottom: 0;
  }

  .category-header {
    display: flex;
    align-items: center;
    padding: 4px 6px;
    border-radius: 4px;
    border-left: 2px solid transparent;
    transition: all 0.15s ease;
    user-select: none;
    gap: 2px;
  }

  .category-header.clickable:hover {
    background-color: var(--hover-color);
    cursor: pointer;
  }

  .category-header.clickable {
    cursor: pointer;
  }
  .category-header.selected {
    background-color: rgba(59, 130, 246, 0.08);
    border-left-color: var(--accent-color);
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

  .category-name {
    flex: 1;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-count {
    font-size: 11px;
    color: var(--text-muted);
    margin-left: 4px;
    flex-shrink: 0;
  }

  .category-children {
    margin-top: 0;
  }
</style>
