<script>
  //@ts-nocheck
  import Table from './Table.svelte';

  let {
    items = [],
    columns = [],
    columnWidths = [],
    columnFunctions = [],
    onrowClick
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
    onrowClick={(row) => {
      onrowClick?.(row.data);
    }} />
</div>