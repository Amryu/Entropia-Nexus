<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { untrack } from 'svelte';

  import VirtualTableRow from '$lib/components/VirtualTableRow.svelte';



  /**
   * @typedef {Object} Props
   * @property {any} [title]
   * @property {any} [header]
   * @property {any} [data]
   * @property {any} [options]
   * @property {string} [style]
   * @property {number} [start]
   * @property {number} [end]
   * @property {number} [count]
   */

  /** @type {Props} */
  let {
    title = null,
    header = { values: [] },
    data = [],
    options = {},
    style = '',
    start = $bindable(0),
    end = $bindable(0),
    count = $bindable(0),
    onrowClick,
    onrowHover
  } = $props();

  const rowHeight = 19;

  let viewport = $state();
  let contents = $state();

  let searchValues = $state([]);
  let sortDirections = $state([]);

  let filteredData = $state([]);

  let currentHeaders = $state([]);


  function resetHeaderFilters() {
    searchValues = Array(header?.values?.length).fill('');
    sortDirections = [];
  }

  let spanMap = $state([]);
  let spanLengths = $state([]);

  function isSpannable(v) {
    return v === true || (typeof v === 'number' && v >= 1);
  }


  function getSpanLength(colIndex, rowIndex) {
    if (!spanLengths || !spanLengths[colIndex]) return 1;
    const m = spanLengths[colIndex];
    return m.get(rowIndex) || 1;
  }

  function search(value, searchString) {
    if (searchString.trimStart().startsWith('=')) {
      return value == searchString.trimStart().substring(1);
    }

    if (!searchString.trimStart().startsWith('~')) {
      value = value?.toString().toLowerCase() ?? '';
      searchString = searchString?.toLowerCase() ?? '';
    }
    else {
      value ??= '';
      searchString = searchString.trimStart().substring(1);
    }

    if (searchString.trimStart().startsWith('!')) {
      return !value.includes(searchString.trimStart().substring(1));
    }
    if (searchString.trimStart().startsWith('>=')) {
      return value >= Number(searchString.trimStart().substring(2).trim());
    }
    if (searchString.trimStart().startsWith('<=')) {
      return value <= Number(searchString.trimStart().substring(2).trim());
    }
    if (searchString.trimStart().startsWith('>')) {
      return value > Number(searchString.trimStart().substring(1).trim());
    }
    if (searchString.trimStart().startsWith('<')) {
      return value < Number(searchString.trimStart().substring(1).trim());
    }

    return value.includes(searchString);
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

  function rowClick(row) {
    onrowClick?.(row);
  }

  function rowHover(row) {
    onrowHover?.(row);
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

  // Returns true if the given column should continue the span from the previous row
  function spanCellMatches(colIndex, row, prevRow) {
    if (row == null || prevRow == null) return false;
    const spans = row.spans;
    if (spans == null) return false;
    if (!isSpannable(spans[colIndex])) return false;
    return row.values[colIndex] === prevRow.values[colIndex];
  }
  $effect(() => {
    if (header.values
      && (untrack(() => currentHeaders).length !== header?.values.length
      || !untrack(() => currentHeaders).every((x, i) => x === header.values[i])
      || !header.values.every((x, i) => x === untrack(() => currentHeaders)[i]))) {
      resetHeaderFilters();
      currentHeaders = header.values;
    }
  });
  $effect(() => {
    if (data != null && data.length > 0) {
      filteredData = data;

      if (options.searchable) {
        if (searchValues?.length !== header?.values?.length) {
          searchValues = Array(header?.values?.length).fill('');
        }

        filteredData = filteredData.filter((row) => {
          for (let i = 0; i < searchValues.length; i++) {
            if (searchValues[i].trim().length !== 0 && !search(row.values[i]?.toString().toLowerCase() ?? '', searchValues[i].toLowerCase())) {
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
              let isANull = (a.values[index] == null || a.values[index] === 'N/A');
              let isBNull = (b.values[index] == null || b.values[index] === 'N/A');

              if (isANull && b.values[index] != null) {
                return 1;
              }
              if (isBNull && a.values[index] != null) {
                return -1;
              }
              if (isANull && isBNull) {
                continue;
              }

              if (typeof a.values[index] !== 'number' && typeof b.values[index] === 'number') {
                return sortDirections[i].asc ? 1 : -1;
              }
              if (typeof a.values[index] === 'number' && typeof b.values[index] !== 'number') {
                return sortDirections[i].asc ? -1 : 1;
              }

              let value = typeof a.values[index] === 'number' && typeof b.values[index] !== 'number'
                ? a.values[index] - b.values[index]
                : a.values[index].toString().localeCompare(b.values[index].toString(), undefined, { numeric: true });
              
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

      count = filteredData.length;
    }
  });
  $effect(() => {
    if (filteredData && options.virtual !== true) {
      // Map the starting index of every span column. A new span starts once the value of the current row is different from the previous row.
      spanMap = Array(getColumnCount(header, filteredData)).fill(null);
      spanLengths = Array(getColumnCount(header, filteredData)).fill(null);

      for (let i = 0; i < getColumnCount(header, filteredData); i++) {
        spanMap[i] = [0];
        for (let j = 1; j < filteredData.length; j++) {
          // Start a new span group if this column is not spannable, or if the value changes vs previous row
          if (!spanCellMatches(i, filteredData[j], filteredData[j - 1])) {
            spanMap[i].push(j);
          }
        }
        // Compute dynamic span lengths per start index
        const starts = spanMap[i];
        const lengthsMap = new Map();
        for (let k = 0; k < starts.length; k++) {
          const start = starts[k];
          const next = (k + 1 < starts.length) ? starts[k + 1] : filteredData.length;
          lengthsMap.set(start, Math.max(1, next - start));
        }
        spanLengths[i] = lengthsMap;
      }
    }
  });
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

  .copyable-link {
    text-decoration: underline;
    cursor: pointer;
    background: none;
    border: none;
    padding: 0;
    color: inherit;
    font: inherit;
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

  tbody, .tscroll {
    display: grid;
    grid-template-columns: subgrid;
    overflow: hidden;
  }

  tbody {
    grid-template-rows: repeat(auto-fill, var(--rowHeight)px);
  }

  .tscroll {
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
  
  tr.hover {
    cursor: pointer;
  }
  
  tr.hover:hover td {
    background-color: var(--table-row-hover-color);
  }

  h3 {
    margin-top: 0;
    margin-bottom: 0;
    font-size: inherit;
  }
</style>
<table style={`${getTableGridStyle(options.virtual, header)} ${style}`}>
  {#if title || header.values?.length > 0}
    <thead>
      {#if title}
        <tr>
          <th style="text-align: center; grid-column: span {getColumnCount(header, filteredData)};"><h3>{title}</h3></th>
        </tr>
      {/if}
      {#if header.values?.length > 0}
        <tr>
          {#each header.values as headerValue, index}
            {#if sortDirections.find((x) => x.index === index)}
              <th class='sortable' onclick={(evt) => sortColumn(evt, index)}>{headerValue} {getSortIndicator(sortDirections.find((x) => x.index === index))}</th>
            {:else}
              <th class='{options.sortable !== false ? 'sortable' : ''}' onclick={(evt) => sortColumn(evt, index)}>{headerValue}</th>
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
      <table class="tscroll" bind:this={viewport} style={`grid-column: span ${getColumnCount(header, filteredData) + 1};`}>
        <tbody bind:this={contents} class={options.virtual ? 'virtual' : ''} style={`grid-column: span ${getColumnCount(header, filteredData)};`}>
          <VirtualTableRow
            items={filteredData}
            itemHeight={rowHeight}
            viewport={viewport}
            contents={contents}
            onrowClick={(row) => rowClick(row)}
            onrowHover={(row) => rowHover(row)}
            bind:start
            bind:end
            
            >
            {#snippet children({ item, index })}
                    <tdgroup style="display: contents;">
              {#each item.values as value, valueIndex}
                <td class="clickable {(index) % 2 === 0 ? 'row-color' : 'row-color-alt'}" height="17px" style={item?.tdStyles ? item?.tdStyles[valueIndex] : null}>
                  <span class={(shouldShowTooltip(item, valueIndex) && !(item?.copyables && item.copyables[valueIndex])) ? 'dotted-underline' : ''} title={shouldShowTooltip(item, valueIndex) ? item?.tooltips[valueIndex] : null}>
                    {#if item?.links != null && item?.links[valueIndex] != null}
                      <a href={item?.links[valueIndex]}>{@html value ?? ''}</a>
                    {:else if item?.copyables && item.copyables[valueIndex]}
                      <button type="button" class='copyable-link' title={shouldShowTooltip(item, valueIndex) ? item?.tooltips[valueIndex] : null} onclick={() => item?.onClicks && item.onClicks[valueIndex] ? item.onClicks[valueIndex]() : null}>
                        {@html value ?? ''}
                      </button>
                    {:else}
                      {@html value ?? ''}
                    {/if}
                  </span>
                </td>
              {/each}
              </tdgroup>
                              {/snippet}
                </VirtualTableRow>
        </tbody>
      </table>
    {:else}
      <tbody bind:this={contents} class={options.virtual ? 'virtual' : ''} style={`grid-column: span ${getColumnCount(header, filteredData)};`}>
        {#each filteredData as item, index}
          <tr onclick={() => rowClick({ index, data: item })} onmouseover={() => rowHover({ index, data: item })} onfocus={() => rowHover({ index, data: item })} onmouseout={() => rowHover(null)} onblur={() => rowHover(null)} style={item?.trStyle ?? ''} class="{options.highlightOnHover ? 'hover' : ''}">
            {#each item.values as value, valueIndex}
              {#if (item?.spans == null || item?.spans[valueIndex] == null) || (isSpannable(item?.spans[valueIndex]) && !spanCellMatches(valueIndex, item, filteredData[index - 1]))}
                <td class={(item?.spans != null && isSpannable(item?.spans[valueIndex]) ? spanMap[valueIndex].indexOf(index) : index) % 2 === 0 ? 'row-color' : 'row-color-alt'} style={`${item?.spans != null && isSpannable(item?.spans[valueIndex]) && !spanCellMatches(valueIndex, item, filteredData[index - 1]) ? `grid-row: span ${getSpanLength(valueIndex, index)};` : ''}${item?.tdStyles && item?.tdStyles[valueIndex] != null ? item?.tdStyles[valueIndex] : ''}`}>
                  <span style={(shouldShowTooltip(item, valueIndex) && !(item?.copyables && item.copyables[valueIndex])) ? 'text-decoration: underline; text-decoration-style: dashed; text-decoration-thickness: 1px;' : ''} title={shouldShowTooltip(item, valueIndex) ? item?.tooltips[valueIndex] : null}>
                    {#if item?.links != null && item?.links[valueIndex] != null}
                      <a href={item?.links[valueIndex]}>{@html value ?? ''}</a>
                    {:else if item?.copyables && item.copyables[valueIndex]}
                      <button type="button" class='copyable-link' title={shouldShowTooltip(item, valueIndex) ? item?.tooltips[valueIndex] : null} onclick={() => item?.onClicks && item.onClicks[valueIndex] ? item.onClicks[valueIndex]() : null}>
                        {@html value ?? ''}
                      </button>
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