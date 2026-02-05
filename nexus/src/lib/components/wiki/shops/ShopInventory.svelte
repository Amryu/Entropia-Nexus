<!--
  @component ShopInventory
  Displays shop inventory groups with items, stack sizes, and markup.
  Uses FancyTable for consistent styling. Each inventory group gets its own table.
-->
<script>
  // @ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { getItemLink } from '$lib/util';

  /** Array of inventory groups, each with a Name and Items array */
  export let inventoryGroups = [];

  /** Map of item ID to item details (for linking and display names) */
  export let itemDetails = {};

  /** Message to show when inventory is empty */
  export let emptyMessage = "The shop owner has not yet added any items for display.";

  // Transform a group's items into table data
  function getTableData(group) {
    if (!group?.Items || group.Items.length === 0) return [];

    return group.Items.map(item => {
      const itemId = item.ItemId ?? item.item_id;
      const itemData = itemId ? itemDetails[itemId] : null;
      const itemName = itemData?.Name || itemData?.name || 'Unknown Item';
      const itemLink = itemData ? getItemLink(itemData) : null;
      const stackSize = item.StackSize ?? item.stack_size ?? 0;
      const markup = item.Markup ?? item.markup ?? 0;

      return {
        itemName,
        itemLink,
        stackSize,
        stackSizeFormatted: stackSize.toLocaleString(),
        markup,
        markupFormatted: `${markup.toFixed(2)}%`
      };
    });
  }

  // Column definitions for FancyTable
  const columns = [
    {
      key: 'itemName',
      header: 'Item',
      main: true,
      sortable: true,
      formatter: (value, row) => row.itemLink
        ? `<a href="${row.itemLink}" class="wiki-link">${value}</a>`
        : `<span style="font-weight: 500;">${value}</span>`
    },
    {
      key: 'stackSize',
      header: 'Stack Size',
      sortable: true,
      formatter: (value, row) => `<span style="font-family: monospace;">${row.stackSizeFormatted}</span>`
    },
    {
      key: 'markup',
      header: 'Markup',
      sortable: true,
      formatter: (value, row) => {
        const color = value > 100 ? 'var(--success-color, #22c55e)' : 'var(--text-color)';
        return `<span style="font-family: monospace; color: ${color};">${row.markupFormatted}</span>`;
      }
    }
  ];

  // Check if inventory has any items
  $: hasInventory = inventoryGroups && inventoryGroups.length > 0 &&
    inventoryGroups.some(g => g?.Items?.length > 0);
</script>

<div class="inventory-container">
  {#if !hasInventory}
    <div class="no-data">{emptyMessage}</div>
  {:else}
    <div class="inventory-notice">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="16" x2="12" y2="12"></line>
        <line x1="12" y1="8" x2="12.01" y2="8"></line>
      </svg>
      <span>Inventory is maintained by the shop owner and may be out of date, sold out, or otherwise inaccurate.</span>
    </div>
    {#each inventoryGroups as group}
      {#if group && group.Items && group.Items.length > 0}
        <div class="inventory-group">
          <h3 class="group-title">{group.Name || group.name || 'Inventory'}</h3>
          <FancyTable
            {columns}
            data={getTableData(group)}
            searchable={group.Items.length > 10}
            sortable={true}
            rowHeight={40}
            emptyMessage="No items in this section."
          />
        </div>
      {/if}
    {/each}
  {/if}
</div>

<style>
  .inventory-container {
    width: 100%;
  }

  .inventory-group {
    margin-bottom: 24px;
  }

  .inventory-group:last-child {
    margin-bottom: 0;
  }

  .group-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-color);
    margin: 0 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .inventory-group :global(.fancy-table-container) {
    max-height: 596px;
  }

  @media (max-width: 767px) {
    .inventory-group :global(.fancy-table-container) {
      max-height: 499px;
    }
  }

  .no-data {
    color: var(--text-muted, #999);
    font-style: italic;
    padding: 40px 20px;
    text-align: center;
    font-size: 14px;
  }

  .inventory-notice {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 12px 14px;
    margin-bottom: 16px;
    background-color: var(--warning-bg, rgba(251, 191, 36, 0.15));
    border: 1px solid var(--warning-color, #fbbf24);
    border-radius: 6px;
    font-size: 13px;
    color: var(--warning-color, #fbbf24);
    line-height: 1.4;
  }

  .inventory-notice svg {
    flex-shrink: 0;
    margin-top: 1px;
  }
</style>
