<script>
// @ts-nocheck
  import '$lib/style.css';

  import { getItemLink, getTypeLink } from '$lib/util';

  import Table from './Table.svelte';

  export let acquisition;

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

<div class="title">Acquisition</div>
{#if (acquisition == null
  || ((!acquisition.VendorOffers || acquisition.VendorOffers.length === 0)
  && (!acquisition.Loots || acquisition.Loots.length === 0)
  && (!acquisition.RefiningRecipes || acquisition.RefiningRecipes.length === 0)
  && (!acquisition.Blueprints || acquisition.Blueprints.length === 0)
  && (!acquisition.Upgrades || acquisition.Upgrades.length === 0)
  && (!acquisition.Events || acquisition.Events.length === 0)))}
<br />  
<div>No data available.</div>
{:else}
  {#if acquisition != null && acquisition.VendorOffers && acquisition.VendorOffers.length > 0}
  <Table
    title = "Vendor"
    header = { 
      {
        values: ['Name', 'Price', 'Planet', 'Location', 'Limited']
      }
    }
    data = {
      acquisition.VendorOffers.map(vendorOffer => ({
        values: [
          vendorOffer.Vendor.Name,
          `${vendorOffer.Item.Value} PED`,
          vendorOffer.Vendor.Planet.Name,
          '-',
          vendorOffer.IsLimited ? 'Yes' : 'No'
        ]
      }))
    }
    options={{searchable: "true"}} />
  {/if}
  {#if acquisition.Loots && acquisition.Loots.length > 0}
  <Table 
    title = "Looted"
    header = {
      {
        values: ['Mob', 'Planet', 'Item', 'Lowest Maturity', 'Frequency'],
        options: { sortFunctions: [null, null, null, null, sortByFrequency] }
      }
    }
    data = {
      acquisition.Loots.map(loot => ({
        values: [
          loot.Mob.Name,
          loot.Mob?.Planet?.Name ?? 'N/A',
          loot.Item.Name,
          loot.Maturity.Name,
          loot.Frequency
        ],
        links: [getTypeLink(loot.Mob.Name, 'Mob', loot.Mob.Planet.Name), null, getItemLink(loot.Item), null, null]
      }))}
    options={{searchable: "true"}} />
  {/if}
  {#if acquisition.RefiningRecipes && acquisition.RefiningRecipes.length > 0}
  <Table
    title="Refining Recipes"
    header={
      {
        values: ['Product', 'Product Amount', 'Ingredient', 'Ingredient Amount']
      }
    }
    data = {
      acquisition.RefiningRecipes.flatMap(recipe => recipe.Ingredients.map((ingredient, index) => ({
        values: [
          recipe.Product.Name,
          recipe.ProductAmount,
          ingredient.Item.Name,
          ingredient.Amount
        ],
        links: [getItemLink(recipe.Product), null, getItemLink(ingredient.Item), null],
        spans: [recipe.Ingredients.length, recipe.Ingredients.length, null, null, null]
      })))
    } />
  {/if}
  {#if acquisition.Blueprints && acquisition.Blueprints.length > 0}
  <Table
    title="Crafted"
    header = {
      {
        values: ['Blueprint', 'Blueprint Level', 'Profession']
      }
    }
    data = {
      acquisition.Blueprints.map(bp => ({
        values: [
          bp.Name,
          bp.Properties.Level,
          bp.Profession.Name
        ],
        links: [`/items/blueprints/${encodeURIComponent(bp.Name)}`, null, null]
      }))
    } />
  {/if}
  {#if acquisition.Upgrades && acquisition.Upgrades.length > 0}
  <Table
    title="Upgraded"
    header = {
      {
        values: ['Mission', 'Planet', 'Location']
      }
    }
    data = {
      acquisition.Upgrades.map(upgrade => ({
        values: [
          upgrade.name,
          upgrade.level,
          `${upgrade.cost.toFixed(2)} PED`,
          upgrade.profession
        ]
      }))
    } />
  {/if}
  {#if acquisition.Events && acquisition.Events.length > 0}
  <div class="small-title">Event</div>
  {/if}
{/if}