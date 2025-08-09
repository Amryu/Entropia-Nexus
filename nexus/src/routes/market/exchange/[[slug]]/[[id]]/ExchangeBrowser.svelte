<script lang="ts">
  // @ts-nocheck
  import { onMount } from 'svelte';
  import CategoryTree from './CategoryTree.svelte';

  export let data;
  
  let searchTerm = '';
  let selectedCategory = null;
  let filteredItems = [];
  
  $: categorizedItems = data?.categorizedItems || {};
  
  // Filter items based on search and selected category
  $: {
    if (selectedCategory && filteredItems) {
      filteredItems = filteredItems.filter(item =>
        item.Name?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    } else if (searchTerm) {
      // Search across all items - flatten all arrays in the categorized structure
      const allItems = flattenItems(categorizedItems);
      filteredItems = allItems.filter(item => 
        item.Name?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    } else {
      filteredItems = [];
    }
  }

  function flattenItems(obj) {
    const items = [];
    
    function traverse(current) {
      if (Array.isArray(current)) {
        items.push(...current);
      } else if (typeof current === 'object' && current !== null) {
        Object.values(current).forEach(traverse);
      }
    }
    
    traverse(obj);
    return items;
  }

  function handleCategorySelect(categoryPath, items) {
    if (Array.isArray(items)) {
      selectedCategory = categoryPath;
      filteredItems = items.filter(item =>
        item.Name?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
  }

  function formatPrice(value) {
    return value ? `${value.toFixed(2)} PED` : 'N/A';
  }
</script>

<div class="exchange-browser">
  <div class="header">
    <h1>Entropia Exchange</h1>
    <div class="search-bar">
      <input
        type="text"
        placeholder="Search items..."
        bind:value={searchTerm}
        class="search-input"
      />
    </div>
  </div>

  <div class="content">
    <div class="sidebar">
      <h3>Categories</h3>
      <CategoryTree 
        categories={categorizedItems} 
        onSelectCategory={handleCategorySelect}
      />
    </div>

    <div class="main-content">
      {#if filteredItems.length > 0}
        <div class="items-header">
          <h3>{selectedCategory || 'Search Results'} ({filteredItems.length} items)</h3>
        </div>
        
        <div class="items-grid">
          {#each filteredItems as item}
            <div class="item-card">
              <div class="item-name">{item.Name}</div>
              <div class="item-details">
                <div class="item-type">{item.Properties?.Type || 'Unknown'}</div>
                <div class="item-weight">Weight: {item.Properties?.Weight || 'N/A'}</div>
                <div class="item-value">Value: {formatPrice(item.Properties?.Economy?.Value)}</div>
                {#if item.Properties?.Class}
                  <div class="item-class">Class: {item.Properties.Class}</div>
                {/if}
                {#if item.Properties?.Category}
                  <div class="item-category">Category: {item.Properties.Category}</div>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {:else if selectedCategory}
        <div class="empty-state">
          <p>No items found in this category{searchTerm ? ` matching "${searchTerm}"` : ''}.</p>
        </div>
      {:else if searchTerm}
        <div class="empty-state">
          <p>No items found matching "{searchTerm}".</p>
        </div>
      {:else}
        <div class="welcome-state">
          <h3>Welcome to the Entropia Exchange</h3>
          <p>Select a category from the sidebar or use the search bar to find items.</p>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .exchange-browser {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
  }

  .header {
    margin-bottom: 30px;
  }

  .header h1 {
    color: #2c3e50;
    margin-bottom: 20px;
  }

  .search-bar {
    max-width: 400px;
  }

  .search-input {
    width: 100%;
    padding: 12px;
    border: 1px solid #ddd;
    border-radius: 6px;
    font-size: 16px;
  }

  .content {
    display: flex;
    gap: 30px;
  }

  .sidebar {
    flex: 0 0 250px;
    background: #f8f9fa;
    padding: 20px;
    border-radius: 8px;
    height: fit-content;
  }

  .sidebar h3 {
    margin: 0 0 15px 0;
    color: #2c3e50;
  }

  .main-content {
    flex: 1;
  }

  .items-header h3 {
    color: #2c3e50;
    margin-bottom: 20px;
  }

  .items-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
  }

  .item-card {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 15px;
    transition: box-shadow 0.2s;
  }

  .item-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  }

  .item-name {
    font-weight: bold;
    font-size: 16px;
    color: #2c3e50;
    margin-bottom: 10px;
  }

  .item-details {
    font-size: 14px;
    color: #666;
  }

  .item-details > div {
    margin-bottom: 4px;
  }

  .item-type {
    color: #3498db;
    font-weight: 500;
  }

  .empty-state,
  .welcome-state {
    text-align: center;
    padding: 60px 20px;
    color: #666;
  }

  .welcome-state h3 {
    color: #2c3e50;
    margin-bottom: 10px;
  }
</style>
