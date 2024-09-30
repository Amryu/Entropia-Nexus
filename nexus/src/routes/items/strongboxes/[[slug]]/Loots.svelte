<script>
// @ts-nocheck
  import '$lib/style.css';

  import { getItemLink } from '$lib/util';

  import Table from '$lib/components/Table.svelte';

  export let loots;

  const rarityOrder = {
    'Common': 0,
    'Uncommon': 1,
    'Rare': 2,
    'Epic': 3,
    'Supreme': 4,
    'Legendary': 5,
    'Mythical': 6
  };

  function sortByRarity(a, b) {
    if (rarityOrder[a] === undefined && rarityOrder[b] !== undefined) {
      return rarityOrder.length - rarityOrder[b];
    }
    if (rarityOrder[a] !== undefined && rarityOrder[b] === undefined) {
      return rarityOrder[a] - rarityOrder.length;
    }

    return rarityOrder[a] - rarityOrder[b];
  }
</script>

<h2>Loots</h2>
{#if (!loots || loots.length === 0)}
<br />  
<div>No data available.</div>
{:else}
<Table
  header = { 
    {
      values: ['Item', 'Rarity', 'From', 'Until'],
      options: { sortFunctions: [null, null, null, sortByRarity] }
    }
  }
  data = {loots.map(loot => ({
    values: [
      loot.Item.Name,
      loot.Rarity,
      loot.AvailableFrom,
      loot.AvailableUntil
    ],
    links: [getItemLink(loot.Item)]
  }))}
  options={{searchable: true}} />
{/if}