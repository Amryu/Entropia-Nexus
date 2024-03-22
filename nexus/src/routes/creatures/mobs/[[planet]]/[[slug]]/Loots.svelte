<script>
// @ts-nocheck
  import '$lib/style.css';

  import { getTypeLink } from '$lib/util';

  import Table from '$lib/components/Table.svelte';

  export let loots;

  const frequencyOrder = {
    'Always': 0,
    'Very often': 1,
    'Often': 2,
    'Common': 3,
    'Uncommon': 4,
    'Rare': 5,
    'Very Rare': 6,
    'Extremely rare': 7
  };

  function sortByFrequency(a, b) {
    if (frequencyOrder[a] === undefined && frequencyOrder[b] !== undefined) {
      return 8 - frequencyOrder[b];
    }
    if (frequencyOrder[a] !== undefined && frequencyOrder[b] === undefined) {
      return frequencyOrder[a] - 8;
    }

    return frequencyOrder[a] - frequencyOrder[b];
  }
</script>

<div class="title">Loots</div>
{#if (!loots || loots.length === 0)}
<br />  
<div>No data available.</div>
{:else}
<Table
  header = { 
    {
      values: ['Item', 'Lowest Maturity', 'Event', 'Frequency'],
      options: { sortFunctions: [null, null, null, sortByFrequency] }
    }
  }
  data = {loots.map(loot => ({
    values: [
      loot.Item.Name,
      loot.Maturity.Name,
      loot.IsEvent ? 'Yes' : 'No',
      loot.Frequency
    ],
    links: [getTypeLink(loot.Item.Name, loot.Item.Properties.Type)]
  }))}
  options={{searchable: "true"}} />
{/if}