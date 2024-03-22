<script>
  // @ts-nocheck

  import '$lib/style.css';

  import { createEventDispatcher } from 'svelte';

  import Table from './Table.svelte';
  import { navigate } from '$lib/util';

  export let items = [];
  export let filterButtonInfo = [];
  export let currentSelection = '';
  export let title = '';
  export let basePath = '';
  export let tableViewInfo = {};

  let currentCategorySelected = null;

  let search = '';
  let isMultiType;
  let elements;

  let expanded = false;

  let start;
  let end;

  $: {
    isMultiType = typeof items === 'object' && !Array.isArray(items)
    elements = isMultiType ? Object.keys(items).map(x => items[x].map(y => { y._type = x; return y })).flat() : items;
    elements = elements.sort((a, b) => a.Name.localeCompare(b.Name));
  }
  
  let filteredElements;

  $: {
    filteredElements = elements.filter((item) => {
      return !(isMultiType && currentCategorySelected && item._type !== currentCategorySelected);
    });

    const searchTerm = search?.toLowerCase();
    filteredElements = !search.trim() ? filteredElements : filteredElements.filter((item) => {
      return item.Name.toLowerCase().includes(searchTerm);
    });
  }

  const dispatch = createEventDispatcher();

  function expand() {
    expanded = !expanded;

    if (expanded) {
      search = '';
    }

    dispatch('expand', { expanded });
  }

  function getTableViewInfo(currentCategorySelected) {
    return isMultiType ? tableViewInfo[currentCategorySelected ?? 'all'] : tableViewInfo;
  }
</script>

<style>
  .title {
    font-size: 32px;
  }
  
  .width100 {
    width: calc(100% - 8px);
  }

  .button-container {
    display: flex;
    text-align: center;
  }

  .square-button {
    width: 32px;
    height: 32px;
    border: none;
    margin-right: 5px;
    font-size: 12px;
  }

  .square-button:not([disabled]):hover {
    cursor: pointer;
    background-color: var(--hover-color);
  }

  .square-button:not([disabled]).selected {
    border: 1px solid var(--text-color);
    background-color: var(--hover-color);
  }

  .list-wrapper {
    position: relative;
  }

  .expand-button {
    position: absolute;
    top: 0;
    right: 0;
    font-size: 16px;
    padding: 5px;
    cursor: pointer;
    border: 1px solid var(--text-color);
    background-color: var(--primary-color);
  }

  .expand-button:hover {
    background-color: var(--hover-color);
  }

  .expanded {
    width: 100%;
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
</style>

<div class="list-wrapper {expanded ? 'expanded' : ''}">
  <button class="expand-button" on:click={expand}>{expanded ? 'Close' : 'Expand'}</button>

  <div class="title">{title}</div>
  <br />

  <div class="info-container">
    {#if isMultiType}
      <div class="button-container">
        <button class="square-button {currentCategorySelected === null ? 'selected' : ''}" on:click={() => currentCategorySelected = null} title='All'>All</button>
        {#each filterButtonInfo as buttonInfo}
          <button class="square-button {currentCategorySelected === buttonInfo.Type ? 'selected' : ''}" on:click={() => currentCategorySelected = buttonInfo.Type} title='{buttonInfo.Title}'>{buttonInfo.Label}</button>
        {/each}
      </div>
    {/if} 
    {#if expanded}
    <div class="data-info">
      Showing element {start + 1} to {end} of {filteredElements.length} elements
    </div>
    {/if}
  </div>
  {#if !expanded}
  <input class="search-input width100" type="text" placeholder="Search..." bind:value={search} on:focus={(evt) => { if (evt.target.selectionStart === evt.target.selectionEnd) evt.target.select(); }} style="font-size: 20px;">
  {/if}

  {#if expanded}
    <div style="display: flex; overflow-x: auto; overflow-y: hidden; flex-grow: 1;">
      <Table
        style='width: 100%; text-align: left; white-space: nowrap; text-overflow: ellipsis;'
        header={
          { 
            values: getTableViewInfo(currentCategorySelected).columns,
            widths: getTableViewInfo(currentCategorySelected).columnWidths
          }
        }
        data={
          filteredElements.map((item) => {
            return {
              values: getTableViewInfo(currentCategorySelected).rowValuesFunction(item),
              trStyle: item.Name === currentSelection ? `font-weight: bold;` : ''
            };
          })
        }
        options={
          { 
            highlightOnHover: true,
            searchable: true,
            virtual: true
          }
        }
        bind:start
        bind:end
        on:rowClick={(evt) => {
          currentSelection = evt.detail.data.values[0];

          navigate(`${basePath}${filteredElements.find(x => x.Name === currentSelection)._type ? `/${filteredElements.find(x => x.Name === currentSelection)._type}` : ''}/${encodeURIComponent(currentSelection)}`);
        }} />
      </div>
  {:else}
    <div style="display: flex; overflow-x: auto; overflow-y: hidden; flex-grow: 1;">
      {#if filteredElements.length === 0}
      <div style="text-align: center; margin: auto;">
        <br />
        No items found...<br />
        <br />
        <input type="button" value="Clear Search" on:click="{() => search = ''}" />
      </div>
      {:else}
        <Table
          style='width: 300px'
          header={
            { 
              values: ['Name'],
              widths: ['1fr']
            }
          }
          data={
            filteredElements.map((item) => {
              return {
                values: [item.Name],
                trStyle: item.Name === currentSelection ? `font-weight: bold;` : '',
              };
            })
          }
          options={
            { 
              highlightOnHover: true,
              virtual: true
            }
          }
          on:rowClick={(evt) => {
            currentSelection = evt.detail.data.values[0];

            navigate(`${basePath}${filteredElements.find(x => x.Name === currentSelection)._type ? `/${filteredElements.find(x => x.Name === currentSelection)._type}` : ''}/${encodeURIComponent(currentSelection)}`);
          }} />
      {/if}
    </div>
  {/if}
</div>