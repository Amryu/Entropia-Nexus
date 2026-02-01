<!--
  @component VendorOffers
  Displays items offered by a vendor with their values and special prices.
  Uses FancyTable for consistent styling.
-->
<script>
  // @ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { clampDecimals, getItemLink, getTypeName } from '$lib/util';

  export let offers = [];

  // Type badge colors
  const typeColors = {
    'Weapon': { bg: 'rgba(239, 68, 68, 0.25)', color: '#ef4444' },
    'Armor': { bg: 'rgba(59, 130, 246, 0.25)', color: '#3b82f6' },
    'Material': { bg: 'rgba(34, 197, 94, 0.25)', color: '#22c55e' },
    'MedicalTool': { bg: 'rgba(236, 72, 153, 0.25)', color: '#ec4899' },
    'MiscTool': { bg: 'rgba(107, 114, 128, 0.25)', color: '#9ca3af' },
    'Finder': { bg: 'rgba(245, 158, 11, 0.25)', color: '#f59e0b' },
    'Excavator': { bg: 'rgba(132, 204, 22, 0.25)', color: '#84cc16' },
    'Refiner': { bg: 'rgba(20, 184, 166, 0.25)', color: '#14b8a6' },
    'Scanner': { bg: 'rgba(6, 182, 212, 0.25)', color: '#06b6d4' },
    'Consumable': { bg: 'rgba(168, 85, 247, 0.25)', color: '#a855f7' },
    'MindforceImplant': { bg: 'rgba(139, 92, 246, 0.25)', color: '#8b5cf6' },
    'Vehicle': { bg: 'rgba(249, 115, 22, 0.25)', color: '#f97316' },
    'Pet': { bg: 'rgba(234, 179, 8, 0.25)', color: '#eab308' },
  };

  function getTypeStyle(type) {
    const style = typeColors[type] || { bg: 'rgba(107, 114, 128, 0.25)', color: '#9ca3af' };
    return `background-color: ${style.bg}; color: ${style.color};`;
  }

  function getItemValue(offer) {
    return offer.Value ?? offer.Item.Properties?.Economy?.Value ?? 0;
  }

  function formatPrices(prices) {
    if (!prices || prices.length === 0) return null;
    return prices.map(p => `${p.Amount} ${p.Item.Name}`).join(', ');
  }

  // Transform data for FancyTable
  $: tableData = (offers || [])
    .sort((a, b) => a.Item.Name.localeCompare(b.Item.Name))
    .map(offer => {
      const itemLink = getItemLink(offer.Item);
      const type = offer.Item.Properties?.Type || 'Other';
      const value = getItemValue(offer);
      const specialCost = formatPrices(offer.Prices);

      return {
        itemName: offer.Item.Name,
        itemLink: itemLink,
        type: type,
        typeName: getTypeName(type) || 'Other',
        typeStyle: getTypeStyle(type),
        value: value,
        valueFormatted: `${clampDecimals(value, 2, 4)} PED`,
        specialCost: specialCost,
        isLimited: offer.IsLimited || false
      };
    });

  const columns = [
    {
      key: 'itemName',
      header: 'Item',
      width: '1fr',
      sortable: true,
      formatter: (value, row) => row.itemLink
        ? `<a href="${row.itemLink}" class="wiki-link">${value}</a>`
        : `<span style="font-weight: 500;">${value}</span>`
    },
    {
      key: 'typeName',
      header: 'Type',
      width: '110px',
      sortable: true,
      hideOnMobile: true,
      formatter: (value, row) => `<span style="display: inline-block; padding: 2px 8px; font-size: 10px; font-weight: 600; border-radius: 4px; text-transform: uppercase; ${row.typeStyle}">${value}</span>`
    },
    {
      key: 'value',
      header: 'Value',
      width: '100px',
      sortable: true,
      formatter: (value, row) => `<span style="font-family: monospace;">${row.valueFormatted}</span>`
    },
    {
      key: 'specialCost',
      header: 'Special Cost',
      width: '180px',
      hideOnMobile: true,
      formatter: (value) => value
        ? `<span style="color: var(--warning-color, #fbbf24);">${value}</span>`
        : '<span style="color: var(--text-muted);">-</span>'
    },
    {
      key: 'isLimited',
      header: 'Limited',
      width: '80px',
      sortable: true,
      formatter: (value) => value
        ? '<span style="display: inline-block; padding: 2px 6px; font-size: 10px; background-color: var(--warning-bg, rgba(251, 191, 36, 0.15)); color: var(--warning-color, #fbbf24); border-radius: 4px; font-weight: 500;">Limited</span>'
        : '<span style="color: var(--text-muted);">-</span>'
    }
  ];
</script>

<div class="offers-table-container">
  {#if !offers || offers.length === 0}
    <div class="no-data">This vendor has no offers.</div>
  {:else}
    <FancyTable
      {columns}
      data={tableData}
      searchable={tableData.length > 10}
      sortable={true}
      rowHeight={44}
      emptyMessage="No offers found."
    />
  {/if}
</div>

<style>
  .offers-table-container {
    width: 100%;
    min-height: 200px;
  }

  .offers-table-container :global(.fancy-table-container) {
    max-height: 600px;
  }

  .no-data {
    color: var(--text-muted, #999);
    font-style: italic;
    padding: 20px;
    text-align: center;
  }
</style>
