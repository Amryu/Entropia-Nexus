<script>
  //@ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import Table from './Table.svelte';

  const dispatch = createEventDispatcher();

  export let items = [];
  export let columns = [];
  export let columnWidths = [];
  export let columnFunctions = [];
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