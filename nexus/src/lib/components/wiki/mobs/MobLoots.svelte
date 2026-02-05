<!--
  @component MobLoots
  Displays a table of mob loot drops with item links, maturity, and frequency.
  Uses FancyTable for consistent styling.
-->
<script>
  // @ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import '$lib/style.css';
  import { getItemLink } from '$lib/util';

  export let loots = [];

  const frequencyOrder = {
    'Always': 0,
    'Very often': 1,
    'Often': 2,
    'Common': 3,
    'Uncommon': 4,
    'Rare': 5,
    'Very Rare': 6,
    'Very rare': 6,
    'Extremely rare': 7
  };

  // Map frequency to color
  const frequencyColors = {
    'Always': { bg: 'rgba(22, 163, 74, 0.25)', color: '#22c55e' },
    'Very often': { bg: 'rgba(34, 197, 94, 0.25)', color: '#4ade80' },
    'Often': { bg: 'rgba(101, 163, 13, 0.25)', color: '#84cc16' },
    'Common': { bg: 'rgba(202, 138, 4, 0.25)', color: '#eab308' },
    'Uncommon': { bg: 'rgba(234, 88, 12, 0.25)', color: '#f97316' },
    'Rare': { bg: 'rgba(220, 38, 38, 0.25)', color: '#ef4444' },
    'Very Rare': { bg: 'rgba(190, 18, 60, 0.25)', color: '#f43f5e' },
    'Very rare': { bg: 'rgba(190, 18, 60, 0.25)', color: '#f43f5e' },
    'Extremely rare': { bg: 'rgba(147, 51, 234, 0.25)', color: '#a855f7' }
  };

  function getFrequencyStyle(frequency) {
    const style = frequencyColors[frequency] || { bg: 'var(--hover-color)', color: 'var(--text-muted)' };
    return `background-color: ${style.bg}; color: ${style.color};`;
  }

  $: sortedLoots = loots ? [...loots].sort((a, b) => {
    const freqA = frequencyOrder[a.Frequency] ?? 99;
    const freqB = frequencyOrder[b.Frequency] ?? 99;
    return freqA - freqB;
  }) : [];

  // Transform data for FancyTable
  $: tableData = sortedLoots.map(loot => ({
    itemName: loot.Item?.Name || 'Unknown',
    itemLink: getItemLink(loot.Item),
    maturity: loot.Maturity?.Name || 'N/A',
    isEvent: loot.IsEvent || false,
    frequency: loot.Frequency || 'Unknown',
    frequencyStyle: getFrequencyStyle(loot.Frequency),
    frequencyOrder: frequencyOrder[loot.Frequency] ?? 99
  }));

  const columns = [
    {
      key: 'itemName',
      header: 'Item',
      width: '150px',
      main: true,  // Grow to fill available space
      formatter: (value, row) => row.itemLink
        ? `<a href="${row.itemLink}" class="wiki-link">${value}</a>`
        : `<span style="font-weight: 500;">${value}</span>`
    },
    {
      key: 'maturity',
      header: 'Lowest Maturity',
      width: '140px',
      hideOnMobile: true
    },
    {
      key: 'isEvent',
      header: 'Event',
      width: '80px',
      hideOnMobile: true,
      formatter: (value) => value
        ? '<span style="display: inline-block; padding: 2px 8px; font-size: 11px; background-color: var(--warning-bg, rgba(251, 191, 36, 0.15)); color: var(--warning-color, #fbbf24); border-radius: 4px; font-weight: 500;">Event</span>'
        : '-'
    },
    {
      key: 'frequency',
      header: 'Frequency',
      width: '120px',
      sortable: true,
      sortValue: (row) => row.frequencyOrder,
      formatter: (value, row) => `<span style="display: inline-block; padding: 2px 8px; font-size: 11px; border-radius: 4px; font-weight: 500; ${row.frequencyStyle}">${value}</span>`
    }
  ];
</script>

<div class="loots-table-container">
  {#if !sortedLoots || sortedLoots.length === 0}
    <div class="no-data">No loot data available.</div>
  {:else}
    <FancyTable
      {columns}
      data={tableData}
      searchable={tableData.length > 15}
      sortable={true}
      rowHeight={40}
      emptyMessage="No loot data available."
    />
  {/if}
</div>

<style>
  .loots-table-container {
    width: 100%;
  }

  .loots-table-container :global(.fancy-table-container) {
    max-height: 500px;
  }

  .no-data {
    color: var(--text-muted, #999);
    font-style: italic;
    padding: 20px;
    text-align: center;
  }
</style>
