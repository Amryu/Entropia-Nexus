<script>
// @ts-nocheck
  import '$lib/style.css';

  import { encodeURIComponentSafe, getItemLink, getTypeLink } from '$lib/util';

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

<style>
  .container {
    display: grid;
    grid-template-columns: minmax(500px, 1fr) minmax(500px, 1fr);
    gap: 15px;
    align-items: start;
  }
</style>

<h2>Acquisition</h2>
<br />
{#if (acquisition == null
  || ((!acquisition.VendorOffers || acquisition.VendorOffers.length === 0)
  && (!acquisition.Loots || acquisition.Loots.length === 0)
  && (!acquisition.RefiningRecipes || acquisition.RefiningRecipes.length === 0)
  && (!acquisition.Blueprints || acquisition.Blueprints.length === 0)
  && (!acquisition.Upgrades || acquisition.Upgrades.length === 0)
  && (!acquisition.Events || acquisition.Events.length === 0)))}
<div>No data available.</div>
{:else}
  <div class="container">
    {#if acquisition != null && acquisition.VendorOffers && acquisition.VendorOffers.length > 0}
    <Table
      title = "Vendor"
      header = { 
        {
          values: ['Name', 'Price', 'Special Price', 'Planet', 'Limited'],
          widths: ['1fr', 'max-content', 'max-content', '1fr', 'max-content']
        }
      }
      data = {
        acquisition.VendorOffers.map(vendorOffer => ({
          values: [
            vendorOffer.Vendor.Name,
            `${vendorOffer.Item.Properties.Economy.Value} PED`,
            vendorOffer.Prices?.length > 0 ? vendorOffer.Prices.map(price => `${price.Amount} ${price.Item.Name}`).join('<br />') : 'N/A',
            vendorOffer.Vendor.Planet.Name,
            vendorOffer.IsLimited ? 'Yes' : 'No'
          ],
          links: [getTypeLink(vendorOffer.Vendor.Name, 'Vendor'), null, null, null, null]
        }))
      }
      options={{searchable: "true"}} />
    {/if}
    {#if acquisition.Loots && acquisition.Loots.length > 0}
    <Table 
      title = "Looted"
      header = {
        {
          values: ['Mob', 'Item', 'Planet', 'Lowest Maturity', 'Frequency'],
          options: { sortFunctions: [null, null, null, null, sortByFrequency] },
          widths: ['1fr', 'max-content', '1fr', '1fr', 'max-content']
        }
      }
      data = {
        acquisition.Loots.map(loot => ({
          values: [
            loot.Mob.Name,
            loot.Item.Name,
            loot.Mob?.Planet?.Name ?? 'N/A',
            loot.Maturity.Name,
            loot.Frequency
          ],
          links: [getTypeLink(loot.Mob.Name, 'Mob', loot.Mob.Planet.Name), null, null, null, null]
        }))}
      options={{searchable: "true"}} />
    {/if}
    {#if acquisition.RefiningRecipes && acquisition.RefiningRecipes.length > 0}
    <Table
      title="Refining Recipes"
      header={
        {
          values: ['Product', 'Product Amount', 'Ingredient', 'Ingredient Amount'],
          widths: ['1fr', 'max-content', '1fr', 'max-content']
        }
      }
      data = {
        acquisition.RefiningRecipes.flatMap(recipe => recipe.Ingredients.map((ingredient, index) => ({
          values: [
            recipe.Product.Name,
            recipe.Amount,
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
          values: ['Blueprint', 'Blueprint Level', 'Profession'],
          widths: ['1fr', 'max-content', '1fr']
        }
      }
      data = {
        acquisition.Blueprints.map(bp => ({
          values: [
            bp.Name,
            bp.Properties.Level,
            bp.Profession.Name
          ],
          links: [getTypeLink(bp.Name, 'Blueprint'), null, null]
        }))
      } />
    {/if}
    {#if acquisition.Upgrades && acquisition.Upgrades.length > 0}
    <Table
      title="Upgraded"
      header = {
        {
          values: ['Mission', 'Planet', 'Location'],
          widths: ['1fr', '1fr', '1fr']
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
    <h2>Event</h2>
    {/if}
  </div>
{/if}