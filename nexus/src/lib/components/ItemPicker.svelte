<script>
  //@ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import Table from './Table.svelte';

  const dispatch = createEventDispatcher();

  let {
    items = [],
    columns = [],
    columnWidths = [],
    columnFunctions = []
  } = $props();
</script>

<div class="table-wrapper">
  <Table
    style='height: 300px; width: 100%; text-align: left; white-space: nowrap; text-overflow: ellipsis;'
    header={{
      values: ['Name', ...columns],
      widths: ['1fr', ...columnWidths]
    }}
    data={items.map(item => {
      return {
        values: [item.Name, ...columns.map((_, colIndex) => {
          return columnFunctions[colIndex](item);
        })]
      }
    })}
    options={{ searchable: true, virtual: true }}
    on:rowClick={(evt) => {
      dispatch('rowClick', evt.detail.data);
    }} />
</div>