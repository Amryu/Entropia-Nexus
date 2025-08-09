<script>
  // @ts-nocheck
  export let categories = {};
  export let onSelectCategory;
  export let category = null; // For recursive component use
  export let expandedNodes = new Set();
  export let toggleExpanded = null;
  export let getItemCount = null;
  export let handleCategorySelect = null;
  
  // Initialize functions if not provided (for root component)
  if (!toggleExpanded) {
    toggleExpanded = function(nodeId) {
      if (expandedNodes.has(nodeId)) {
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
      if (category.items && Array.isArray(category.items)) {
        onSelectCategory(category.path.join(' > '), category.items);
      }
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
    />
  {/each}
</div>

<!-- Component for individual category items -->
{#if category}
  <div class="category-item" style="margin-left: {category.level * 16}px">
    <div 
      class="category-header {category.items ? 'clickable' : ''} {category.children.length > 0 ? 'expandable' : ''}"
      on:click={() => {
        if (category.items && Array.isArray(category.items)) {
          handleCategorySelect(category);
        } else if (category.children.length > 0) {
          toggleExpanded(category.id);
        }
      }}
      on:keydown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (category.items && Array.isArray(category.items)) {
            handleCategorySelect(category);
          } else if (category.children.length > 0) {
            toggleExpanded(category.id);
          }
        }
      }}
      role="button"
      tabindex="0"
    >
      {#if category.children.length > 0}
        <span class="expand-icon {expandedNodes.has(category.id) ? 'expanded' : ''}">
          {expandedNodes.has(category.id) ? '▼' : '▶'}
        </span>
      {/if}
      <span class="category-name">{category.name}</span>
      {#if getItemCount(category) > 0}
        <span class="item-count">({getItemCount(category)})</span>
      {/if}
    </div>
    
    {#if category.children.length > 0 && expandedNodes.has(category.id)}
      <div class="category-children">
        {#each category.children as child}
          <svelte:self 
            category={child} 
            {onSelectCategory} 
            {expandedNodes} 
            {toggleExpanded} 
            {getItemCount}
            {handleCategorySelect}
          />
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .category-tree {
    font-size: 14px;
  }
  
  .category-item {
    margin-bottom: 2px;
  }
  
  .category-header {
    display: flex;
    align-items: center;
    padding: 4px 8px;
    border-radius: 4px;
    transition: background-color 0.2s;
    user-select: none;
  }
  
  .category-header.clickable:hover,
  .category-header.expandable:hover {
    background-color: #f0f0f0;
    cursor: pointer;
  }
  
  .category-header.clickable {
    cursor: pointer;
  }
  
  .expand-icon {
    margin-right: 6px;
    font-size: 10px;
    transition: transform 0.2s;
    cursor: pointer;
  }
  
  .category-name {
    flex: 1;
    font-weight: 500;
  }
  
  .item-count {
    font-size: 12px;
    color: #666;
    margin-left: 8px;
  }
  
  .category-children {
    margin-top: 2px;
  }
</style>
