<script>
  // @ts-nocheck

  import Table from './Table.svelte';
  import { encodeURIComponentSafe, navigate } from '$lib/util';

  /**
   * @typedef {Object} Props
   * @property {any} [items]
   * @property {string} [title]
   * @property {string} [basePath]
   * @property {any} [tableViewInfo]
   * @property {any} [favourites]
   */

  /** @type {Props} */
  let {
    items = [],
    title = '',
    basePath = '',
    tableViewInfo = {},
    favourites = []
  } = $props();

  let search = $state('');
  let activeTab = $state('Browse');

  let elements = $derived.by(() => {
    const arr = items.slice();
    arr.sort((a, b) => a.Name.localeCompare(b.Name));
    return arr;
  });

  let filteredElements = $derived(filterElements(elements, search?.toLowerCase()));


  function getTableViewInfo(currentCategorySelected) {
    return tableViewInfo;
  }

  function getItemLink(item) {
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  function toggleExpand(item) {
    item.expanded = !item.expanded;
  }

  function filterElements(elements, searchTerm) {
    return elements
      .map(item => {
        if (item.children && item.children.length > 0) {
          const filteredChildren = filterElements(item.children, searchTerm);
          if (filteredChildren.length > 0) {
            return { ...item, children: filteredChildren };
          }
        } else if (item.Name.toLowerCase().includes(searchTerm)) {
          return item;
        }
        return null;
      })
      .filter(item => item !== null);
  }

  function getFlatFilteredElements(elements, searchTerm) {
    if (searchTerm.trim().length < 3) {
      return [];
    }
    let result = [];
    elements.forEach(item => {
      if (item.children && item.children.length > 0) {
        result = result.concat(getFlatFilteredElements(item.children, searchTerm));
      } else if (item.Name.toLowerCase().includes(searchTerm)) {
        result.push(item);
      }
    });
    return result.slice(0, 300);
  }
</script>

<style>
  .width100 {
    width: calc(100% - 8px);
  }

  .list-wrapper {
    position: relative;
  }

  .arrow {
    display: inline-block;
    transition: transform 0.2s;
  }

  .arrow.expanded {
    transform: rotate(90deg);
  }

  .info-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }

  .search-input {
    margin-bottom: 10px;
  }

  .nested-list {
    list-style-type: none;
    padding-left: 20px;
  }

  .nested-list-item {
    cursor: pointer;
  }

  .tabs {
    display: flex;
    margin-bottom: 10px;
  }

  .tab {
    padding: 10px;
    cursor: pointer;
    border-bottom: 2px solid transparent;
  }

  .tab.active {
    border-bottom: 2px solid #000;
  }
</style>

<div class="list-wrapper">
  <h2>{title}</h2>
  <br />

  <div class="tabs">
    <div class="tab {activeTab === 'Browse' ? 'active' : ''}" role="button" tabindex="0" onclick={() => activeTab = 'Browse'} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activeTab = 'Browse'; } }}>Browse</div>
    <div class="tab {activeTab === 'Search' ? 'active' : ''}" role="button" tabindex="0" onclick={() => activeTab = 'Search'} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activeTab = 'Search'; } }}>Search</div>
    <div class="tab {activeTab === 'Favourites' ? 'active' : ''}" role="button" tabindex="0" onclick={() => activeTab = 'Favourites'} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activeTab = 'Favourites'; } }}>Favourites</div>
  </div>

  {#if activeTab === 'Browse'}
    <div class="info-container">
      <input class="search-input width100" type="text" placeholder="Search..." bind:value={search} onfocus={(evt) => { if (evt.target.selectionStart === evt.target.selectionEnd) evt.target.select(); }} style="font-size: 20px;">
    </div>

    <ul class="nested-list">
      {#each filteredElements as item}
        <li class="nested-list-item">
          {#if item.children && item.children.length > 0}
            <span class="arrow {item.expanded ? 'expanded' : ''}" role="button" tabindex="0" onclick={() => toggleExpand(item)} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggleExpand(item))}>&#9654;</span>
          {/if}
          <span role="button" tabindex="0" onclick={() => navigate(getItemLink(item))} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), navigate(getItemLink(item)))}>{item.Name}</span>
          {#if item.expanded && item.children && item.children.length > 0}
            <ul class="nested-list">
              {#each item.children as child}
                <li class="nested-list-item">
                  {#if child.children && child.children.length > 0}
                    <span class="arrow {child.expanded ? 'expanded' : ''}" role="button" tabindex="0" onclick={() => toggleExpand(child)} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggleExpand(child))}>&#9654;</span>
                  {/if}
                  <span role="button" tabindex="0" onclick={() => navigate(getItemLink(child))} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), navigate(getItemLink(child)))}>{child.Name}</span>
                  {#if child.expanded && child.children && child.children.length > 0}
                    <ul class="nested-list">
                      {#each child.children as grandchild}
                        <li class="nested-list-item">
                          <span role="button" tabindex="0" onclick={() => navigate(getItemLink(grandchild))} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), navigate(getItemLink(grandchild)))}>{grandchild.Name}</span>
                        </li>
                      {/each}
                    </ul>
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}

  {#if activeTab === 'Search'}
    <div class="info-container">
      <input class="search-input width100" type="text" placeholder="Search..." bind:value={search} onfocus={(evt) => { if (evt.target.selectionStart === evt.target.selectionEnd) evt.target.select(); }} style="font-size: 20px;">
    </div>

    <ul class="nested-list">
      {#each getFlatFilteredElements(elements, search.toLowerCase()) as item}
        <li class="nested-list-item">
          <span role="button" tabindex="0" onclick={() => navigate(getItemLink(item))} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), navigate(getItemLink(item)))}>{item.Name}</span>
        </li>
      {/each}
    </ul>
  {/if}

  {#if activeTab === 'Favourites'}
    <ul class="nested-list">
      {#each favourites as item}
        <li class="nested-list-item">
          {#if item.children && item.children.length > 0}
            <span class="arrow {item.expanded ? 'expanded' : ''}" role="button" tabindex="0" onclick={() => toggleExpand(item)} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggleExpand(item))}>&#9654;</span>
          {/if}
          <span role="button" tabindex="0" onclick={() => navigate(getItemLink(item))} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), navigate(getItemLink(item)))}>{item.Name}</span>
          {#if item.expanded && item.children && item.children.length > 0}
            <ul class="nested-list">
              {#each item.children as child}
                <li class="nested-list-item">
                  {#if child.children && child.children.length > 0}
                    <span class="arrow {child.expanded ? 'expanded' : ''}" role="button" tabindex="0" onclick={() => toggleExpand(child)} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggleExpand(child))}>&#9654;</span>
                  {/if}
                  <span role="button" tabindex="0" onclick={() => navigate(getItemLink(child))} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), navigate(getItemLink(child)))}>{child.Name}</span>
                  {#if child.expanded && child.children && child.children.length > 0}
                    <ul class="nested-list">
                      {#each child.children as grandchild}
                        <li class="nested-list-item">
                          <span role="button" tabindex="0" onclick={() => navigate(getItemLink(grandchild))} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), navigate(getItemLink(grandchild)))}>{grandchild.Name}</span>
                        </li>
                      {/each}
                    </ul>
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>