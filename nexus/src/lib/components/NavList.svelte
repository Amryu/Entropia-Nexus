<script>
  // @ts-nocheck

  import '$lib/style.css';

  import Table from './Table.svelte';
  import { encodeURIComponentSafe, navigate } from '$lib/util';
  import ContextMenu from './ContextMenu.svelte';
  import { contextmenu } from './ContextMenu';

  /**
   * @typedef {Object} Props
   * @property {any} [items]
   * @property {any} [filterButtonInfo]
   * @property {string} [currentSelection]
   * @property {string} [title]
   * @property {string} [basePath]
   * @property {any} [tableViewInfo]
   * @property {any} user
   * @property {boolean} [editable]
   * @property {Function} [onexpand]
   */

  /** @type {Props} */
  let {
    items = [],
    filterButtonInfo = [],
    currentSelection = $bindable(''),
    title = '',
    basePath = '',
    tableViewInfo = {},
    user,
    editable = false,
    onexpand
  } = $props();

  let contextMenuElement = $state();

  let currentCategorySelected = $state(null);

  let search = $state('');
  let isMultiType = $derived(typeof items === 'object' && !Array.isArray(items));
  let elements = $derived.by(() => {
    const arr = isMultiType
      ? Object.keys(items).flatMap(x => items[x].map(y => { y._type = x; return y }))
      : items.slice();
    arr.sort((a, b) => a.Name.localeCompare(b.Name, undefined, { numeric: true, sensitivity: 'base' }));
    return arr;
  });

  let expanded = $state(false);

  let start = $state();
  let end = $state();
  let count = $state();

  let filteredElements = $derived.by(() => {
    let result = elements.filter((item) => {
      return !(isMultiType && currentCategorySelected && item._type !== currentCategorySelected);
    });
    const searchTerm = search?.toLowerCase();
    return !search.trim() ? result : result.filter((item) => {
      return item.Name.toLowerCase().includes(searchTerm);
    });
  });

  function expand() {
    expanded = !expanded;

    if (expanded) {
      search = '';
    }

    onexpand?.({ expanded });
  }

  function createItem(type = null) {
    let filterInfo = filterButtonInfo.find(x => x.Type === type);

    let useAsRoute = filterInfo?.IsRoute ?? true;
    let route = filterInfo?.Type ?? type ?? null;

    window.location.href = `${basePath}${route != null && useAsRoute ? `/${route}` : ''}?mode=create`;
  }

  function getTableViewInfo(currentCategorySelected) {
    return isMultiType ? tableViewInfo[currentCategorySelected ?? 'all'] : tableViewInfo;
  }

  function handleClick(event) {
    const contextMenuEvent = new MouseEvent('contextmenu', {
      bubbles: true,
      cancelable: false,
      view: window,
      button: 2,
      buttons: 0,
      clientX: event.clientX,
      clientY: event.clientY
    });

    event.target.dispatchEvent(contextMenuEvent);
  }

  function getItemLink(item) {
    let filterInfo = filterButtonInfo.find(x => x.Type === item._type);

    let useAsRoute = filterInfo?.IsRoute ?? true;
    let route = filterInfo?.Type ?? item._type ?? null;

    return `${basePath}${route && useAsRoute ? `/${route}` : ''}/${encodeURIComponentSafe(item.Name)}`;
  }
</script>

<style>
  .width100 {
    width: calc(100% - 8px);
  }

  .button-container {
    display: flex;
    text-align: center;
  }

  .square-button {
    width: 30px;
    height: 30px;
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
    width: 32px;
    height: 32px;
  }
  
  .create-button {
    position: absolute;
    top: 0;
    left: 0;
    font-size: 16px;
    padding: 5px;
    cursor: pointer;
    border: 1px solid var(--text-color);
    background-color: var(--primary-color);
    width: 32px;
    height: 32px;
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

<ContextMenu
  bind:this={contextMenuElement}
  menu={filterButtonInfo.map(x => ({
    label: x.Title,
    action: () => createItem(x.Type)
  }))} />
<div class="list-wrapper {expanded ? 'expanded' : ''}">
  {#if user && user.verified && editable}
    {#if !isMultiType || filterButtonInfo.every(x => x.IsRoute === false)}
      <button class="create-button" onclick={_ => createItem()} title="Create new item">+</button>
    {:else}
      <button use:contextmenu={{ contextMenu: contextMenuElement, payload: null }} class="create-button" onclick={handleClick} title="Create new item">+</button>
    {/if}
  {/if}
  <button class="expand-button" onclick={expand} title={expanded ? 'Close' : 'Expand'}>{expanded ? '<<' : '>>'}</button>

  <h2>{title}</h2>
  <br />

  <div class="info-container">
    {#if isMultiType}
      <div class="button-container">
        <button class="square-button {currentCategorySelected === null ? 'selected' : ''}" onclick={() => currentCategorySelected = null} title='All'>All</button>
        {#each filterButtonInfo as buttonInfo}
          <button class="square-button {currentCategorySelected === buttonInfo.Type ? 'selected' : ''}" onclick={() => currentCategorySelected = buttonInfo.Type} title='{buttonInfo.Title}'>{buttonInfo.Label}</button>
        {/each}
      </div>
    {/if} 
    {#if expanded}
    <div class="data-info">
      Showing element {start + 1} to {end} of {count} elements
    </div>
    {/if}
  </div>
  {#if !expanded}
  <input class="search-input width100" type="text" placeholder="Search..." bind:value={search} onfocus={(evt) => { if (evt.target.selectionStart === evt.target.selectionEnd) evt.target.select(); }} style="font-size: 20px;">
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
        bind:count
        onrowClick={(row) => {
          currentSelection = row.data.values[0];

          navigate(getItemLink(filteredElements.find(x => x.Name === currentSelection)));
        }} />
      </div>
  {:else}
    <div style="display: flex; overflow-x: auto; overflow-y: hidden; flex-grow: 1;">
      {#if filteredElements.length === 0}
      <div style="text-align: center; margin: auto;">
        <br />
        No items found...<br />
        <br />
        <input type="button" value="Clear Search" onclick={() => search = ''} />
      </div>
      {:else}
        <Table
          style='width: 300px'
          header={
            {
              values: ['Name'],
              widths: ['1fr'],
            }
          }
          data={
            filteredElements.map((item) => {
              return {
                values: [item.Name],
                trStyle: item.Name === currentSelection ? `font-weight: bold;` : '',
                links: [getItemLink(item)]
              };
            })
          }
          options={
            {
              highlightOnHover: true,
              virtual: true
            }
          }
          onrowClick={(row) => {
            currentSelection = row.data.values[0];

            navigate(getItemLink(filteredElements.find(x => x.Name === currentSelection)));
          }} />
      {/if}
    </div>
  {/if}
</div>