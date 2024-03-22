<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { createEventDispatcher } from 'svelte';

  import VirtualTableRow from '$lib/components/VirtualTableRow.svelte';

  export let title = null;
  export let header = { values: [] };
  export let data = [];
  export let options = {};

  export let style = '';

  export let start = 0;
  export let end = 0;

  const rowHeight = 19;

  let viewport;
  let contents;

  let searchValues = [];
  let sortDirections = [];

  let filteredData = [];

  let currentHeaders = [];

  $: if (header.values
    && (currentHeaders.length !== header?.values.length 
    || !currentHeaders.every((x, i) => x === header.values[i])
    || !header.values.every((x, i) => x === currentHeaders[i]))) {
    resetHeaderFilters();
    currentHeaders = header.values;
  }

  function resetHeaderFilters() {
    searchValues = Array(header?.values?.length).fill('');
    sortDirections = [];
  }

  let spanMap = [];

  $: if (filteredData && options.virtual !== true) {
    // Map the starting index of every span column. A new span starts once the value of the current row is different from the previous row.
    spanMap = Array(getColumnCount(header, filteredData)).fill(null);

    for (let i = 0; i < getColumnCount(header, filteredData); i++) {
      spanMap[i] = [0];
      for (let j = 1; j < filteredData.length; j++) {
        if ((filteredData[j].spans == null || filteredData[j].spans[i] == null)
          ||(filteredData[j].spans[i] != null && filteredData[j].spans[i] >= 1 && filteredData[j].values[i] !== filteredData[j - 1].values[i])) {
          spanMap[i].push(j);
        }
      }
    }
  }

  $: if (data != null && data.length > 0) {
    filteredData = data;

    if (options.searchable) {
      if (searchValues?.length !== header?.values?.length) {
        searchValues = Array(header?.values?.length).fill('');
      }

      filteredData = filteredData.filter((row) => {
        for (let i = 0; i < searchValues.length; i++) {
          if (searchValues[i].trim().length !== 0 && !(row.values[i]?.toString().toLowerCase() ?? '').includes(searchValues[i].toLowerCase())) {
            return false;
          }
        }
        return true;
      });
    }

    if (options.sortable !== false) {
      filteredData = filteredData.sort((a, b) => {
        for (let i = 0; i < sortDirections.length; i++) {
          let index = sortDirections[i].index;

          if (!header?.options?.sortFunctions || header.options.sortFunctions[index] == null) {
            if (a.values[index] == null) {
              return 1;
            }
            if (b.values[index] == null) {
              return -1;
            }

            let value = typeof a.values[index] === 'number'
              ? a.values[index] - b.values[index]
              : a.values[index].localeCompare(b.values[index], undefined, { numeric: true });
            
            if (value !== 0) {
              return sortDirections[i].asc ? value : -value;
            }
          }
          else if (header?.options?.sortFunctions && header.options.sortFunctions[index] != null) {
            let result = sortDirections[i].asc
              ? header.options.sortFunctions[index](a?.values[index], b?.values[index])
              : header.options.sortFunctions[index](b?.values[index], a?.values[index]);

            if (result !== 0) {
              return result;
            }
          }
        }
        return 0;
      });
    }
  }

  function sortColumn(evt, index) {
    if (options.sortable == false) return;

    let sortDirection = sortDirections.find((x) => x.index === index);

    if (!evt.shiftKey) {
      sortDirections = sortDirection ? [sortDirection] : [];
    }

    if (sortDirection) {
      sortDirection.asc = !sortDirection.asc;
    }
    else {
      sortDirections.push({ index: index, asc: true });
    }

    // Trigger svelte to re-sort the data
    sortDirections = sortDirections;
  }

  function getSortIndicator(sortDirection) {
    if (sortDirection) {
      return sortDirection.asc ? '▲' : '▼';
    }

    return '';
  }

  const dispatch = createEventDispatcher();

  function rowClick(row) {
    dispatch('rowClick', row?.detail);
  }

  function rowHover(row) {
    dispatch('rowHover', row?.detail);
  }

  function shouldShowTooltip(row, index) {
    return row?.tooltips != null && row?.tooltips[index] != null;
  }

  function getColumnCount(header, filteredData) {
    return header?.values?.length > 0 
      ? header.values.length
      : filteredData != null && filteredData.length > 0
      ? filteredData[0].values.length
      : 1;
  }

  function getTableGridStyle(isVirtual, header) {
    let cols = isVirtual
      ? (`grid-template-columns: ${header?.widths != null
        ? (header.widths.reduce((acc, v) => acc + ' ' + (v || 'auto'), '') + ' 16px')
        : new Array(getColumnCount(header, filteredData)).fill('max-content').join(' ') + ' 16px'};`)
      : (`grid-template-columns: ${header?.widths != null
        ? header.widths.reduce((acc, v) => acc + ' ' + (v || 'auto'), '')
        : new Array(getColumnCount(header, filteredData)).fill('max-content').join(' ')};`);

    let rows = ' grid-template-rows:';  

    if (title) {
      rows += ` ${rowHeight}px`;
    }
    if (header?.values?.length > 0) {
      rows += ` ${rowHeight}px`;
    }
    if (options.searchable === true) {
      rows += ` ${rowHeight}px`;
    }

    rows += ' 1fr;';

    return `${cols} ${rows}`;
  }
</script>

<style>
  .search {
    width: calc(100% - 3px);
    font-size: 11px;
  }

  .sortable {
    cursor: pointer;
    user-select: none;
  }

  .dotted-underline {
    text-decoration: none;
    position: relative;
    line-height: 1.2;
  }

  .dotted-underline::after {
    content: "";
    position: absolute;
    left: 0;
    bottom: 2px;
    width: 100%;
    border-bottom: 1px dotted currentColor;
  }

  tbody.virtual {
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  tbody.virtual td {
    text-overflow: ellipsis;
  }

  table {
    display: grid;
    grid-auto-rows: auto;
    align-items: stretch;
    gap: 2px;
  }

  table td {
    display: flex;
    align-items: center;
    text-overflow: ellipsis;
    overflow: hidden;
  }

  table thead td {
    padding-left: 1px;
    padding-right: 1px;
  }

  table tr, table thead {
    display: contents;
  }

  table td:first-child, table th:first-child {
    margin-left: 0;
  }

  table td:last-child, table th:last-child {
    margin-right: 0;
  }

  th {
    text-align: center;
    background-color: var(--table-header-color);
  }

  .row-color {
    background-color: var(--table-row-color);
  }

  .row-color-alt {
    background-color: var(--table-row-color-alt);
  }

  table thead tr {
    background-color: var(--table-header-color) !important;
  }

  tbody, tscroll {
    display: grid;
    grid-template-columns: subgrid;
    overflow: hidden;
  }

  tbody {
    grid-template-rows: repeat(auto-fill, var(--rowHeight)px);
  }

  tscroll {
    overflow-y: scroll;
    overflow-x: hidden;
  }

  .clickable {
    cursor: pointer;
  }

  .clickable:hover {
    background-color: var(--table-row-hover-color);
  }

  tdgroup:hover .clickable:not(:hover) {
    background-color: var(--table-row-hover-color);
  }
</style>
<table style={`${getTableGridStyle(options.virtual, header)} ${style}`}>
  {#if title || header.values?.length > 0}
    <thead>
      {#if title}
        <tr>
          <th style="text-align: center; grid-column: span {getColumnCount(header, filteredData)};">{title}</th>
        </tr>
      {/if}
      {#if header.values?.length > 0}
        <tr>
          {#each header.values as headerValue, index}
            {#if sortDirections.find((x) => x.index === index)}
              <th class='sortable' on:click={(evt) => sortColumn(evt, index)}>{headerValue} {getSortIndicator(sortDirections.find((x) => x.index === index))}</th>
            {:else}
              <th class='{options.sortable !== false ? 'sortable' : ''}' on:click={(evt) => sortColumn(evt, index)}>{headerValue}</th>
            {/if}
          {/each}
          {#if options.virtual}
            <th></th>
          {/if}
        </tr>
        {#if options.searchable === true}
          <tr>
            {#each new Array(header.values.length) as _, index}
              {#if header?.options?.searchFunctions == null || header.options.searchFunctions[index] !== false}
                <td style="padding-left: 1px; padding-right: 1px;"><input class='search' type='text' bind:value={searchValues[index]} size="1" placeholder="Search..." /></td>
              {/if}
            {/each}
            {#if options.virtual}
              <td></td>
            {/if}
          </tr>
        {/if}
      {/if}
    </thead>
  {/if}
    {#if options.virtual}
      <tscroll bind:this={viewport} style={`grid-column: span ${getColumnCount(header, filteredData) + 1};`}>
        <tbody bind:this={contents} class={options.virtual ? 'virtual' : ''} style={`grid-column: span ${getColumnCount(header, filteredData)};`}>
          <VirtualTableRow
            items={filteredData}
            itemHeight={rowHeight}
            viewport={viewport}
            contents={contents}
            on:rowClick={rowClick}
            on:rowHover={rowHover}
            bind:start
            bind:end
            let:item
            let:index>
            <tdgroup style="display: contents;">
            {#each item.values as value, valueIndex}
              <td class="clickable {(index) % 2 === 0 ? 'row-color' : 'row-color-alt'}" height="17px" style={item?.tdStyles ? item?.tdStyles[valueIndex] : null}>
                <span class={shouldShowTooltip(item, valueIndex) ? 'dotted-underline' : ''} title={shouldShowTooltip(item, valueIndex) ? item?.tooltips[valueIndex] : null}>
                  {#if item?.links != null && item?.links[valueIndex] != null}
                    <a href={item?.links[valueIndex]}>{@html value ?? ''}</a>
                  {:else}
                    {@html value ?? ''}
                  {/if}
                </span>
              </td>
            {/each}
            </tdgroup>
          </VirtualTableRow>
        </tbody>
      </tscroll>
    {:else}
      <tbody bind:this={contents} class={options.virtual ? 'virtual' : ''} style={`grid-column: span ${getColumnCount(header, filteredData)};`}>
        {#each filteredData as item, index}
          <!-- svelte-ignore a11y-mouse-events-have-key-events -->
          <tr on:click={() => rowClick(item)} on:mouseover={() => rowHover(item)} on:mouseout={() => rowHover(null)} style={item?.trStyle ?? ''} class="{options.highlightOnHover ? 'hover' : ''}">
            {#each item.values as value, valueIndex}
              {#if (item?.spans == null || item?.spans[valueIndex] == null) || (item?.spans != null && item?.spans[valueIndex] > 0 && filteredData[index - 1]?.values[valueIndex] != value)}
                <td class={(item?.spans != null && item?.spans[valueIndex] > 0 ? spanMap[valueIndex].indexOf(index) : index) % 2 === 0 ? 'row-color' : 'row-color-alt'} style={`${item?.spans != null && item?.spans[valueIndex] > 0 && filteredData[index - 1]?.values[valueIndex] != value ? `grid-row: span ${item?.spans[valueIndex]};` : ''}${item?.tdStyles && item?.tdStyles[valueIndex] != null ? item?.tdStyles[valueIndex] : ''}`}>
                  <span style={shouldShowTooltip(item, valueIndex) ? 'text-decoration: underline; text-decoration-style: dashed; text-decoration-thickness: 1px;' : ''} title={shouldShowTooltip(item, valueIndex) ? item?.tooltips[valueIndex] : null}>
                    {#if item?.links != null && item?.links[valueIndex] != null}
                      <a href={item?.links[valueIndex]}>{@html value ?? ''}</a>
                    {:else}
                      {@html value ?? ''}
                    {/if}
                  </span>
                </td>
              {/if}
            {/each}
          </tr>
        {/each}
      </tbody>
    {/if}
</table>