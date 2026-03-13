<script>
  import CategoryNode from './CategoryNode.svelte';
  // @ts-nocheck
  import { onMount } from 'svelte';
  /**
   * @typedef {Object} Props
   * @property {any} category
   * @property {any} onSelectCategory
   * @property {number} [level]
   */

  /** @type {Props} */
  let { category, onSelectCategory, level = 0 } = $props();
  
  let expanded = $state(false);
  
  function toggleExpanded() {
    expanded = !expanded;
  }
  
  function handleSelect() {
    if (category.items && Array.isArray(category.items)) {
      onSelectCategory(category.path.join(' > '), category.items);
    } else if (category.children.length > 0) {
      toggleExpanded();
    }
  }
  
  function getItemCount(cat) {
    if (cat.items && Array.isArray(cat.items)) {
      return cat.items.length;
    }
    
    let count = 0;
    if (cat.children) {
      for (const child of cat.children) {
        count += getItemCount(child);
      }
    }
    return count;
  }
  
  let hasItems = $derived(category.items && category.items.length > 0);
  let hasChildren = $derived(category.children && category.children.length > 0);
  let itemCount = $derived(getItemCount(category));
</script>

<div class="category-node" style="margin-left: {level * 16}px">
  <div 
    class="category-header {hasItems ? 'clickable' : ''} {hasChildren ? 'expandable' : ''}"
    onclick={handleSelect}
    onkeydown={(e) => e.key === 'Enter' && handleSelect()}
    role="button"
    tabindex="0"
  >
    {#if hasChildren}
      <span class="expand-icon {expanded ? 'expanded' : ''}">{expanded ? '▼' : '▶'}</span>
    {/if}
    <span class="category-name">{category.name}</span>
    {#if itemCount > 0}
      <span class="item-count">({itemCount})</span>
    {/if}
  </div>
  
  {#if hasChildren && expanded}
    <div class="category-children">
      {#each category.children as child}
        <CategoryNode category={child} {onSelectCategory} level={level + 1} />
      {/each}
    </div>
  {/if}
</div>

<style>
  .category-node {
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
    background-color: var(--hover-color);
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
  color: var(--text-color);
  opacity: 0.7;
    margin-left: 8px;
  }
  
  .category-children {
    margin-top: 2px;
  }
</style>
