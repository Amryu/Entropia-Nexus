<script>
  // @ts-nocheck
  import '$lib/style.css';

  import { getItemLink, getTypeLink } from '$lib/util';

  import Table from './Table.svelte';

  export let item;
  export let usage;
</script>

<style>
  .container {
    display: grid;
    grid-template-columns: minmax(500px, 1fr) minmax(500px, 1fr);
    gap: 15px;
    align-items: start;
  }
</style>

<h2>Usage</h2>
<br />
{#if usage != null
  && ((usage.Blueprints != null && usage.Blueprints.length > 0 )
  || (usage.RefiningRecipes != null && usage.RefiningRecipes.length > 0)
  || (usage.Missions != null && usage.Missions.length > 0)
  || (usage.VendorOffers != null && usage.VendorOffers.length > 0 && usage.VendorOffers.some(vendorOffer => vendorOffer.Prices.length > 0)))}
  <div class="container">
    {#if usage.Blueprints != null && usage.Blueprints.length > 0}
      <Table
        title="Blueprints"
        header={ 
          {
            values: ['Name', 'Amount'],
            widths: ['1fr', '80px'],
          }
        }
        data={
          usage.Blueprints.map(blueprint => {
            return {
              values: [
                blueprint.Name,
                blueprint.MaterialAmount ?? 'N/A',
              ],
              tdStyles: [null, null],
              links: [getTypeLink(blueprint.Name, 'Blueprint'), null]
            };
          })
        }
        options={{sortable: true, searchable: true}}  
      />
    {/if}
    {#if usage.RefiningRecipes != null && usage.RefiningRecipes.length > 0}
      <Table
        title="Refining Recipes"
        header={ 
          {
            values: [ 'Product', 'Amount', 'Ingredients', 'Amount',],
            widths: ['1fr', '80', '1fr', '80px']
          }
        }
        data={
          usage.RefiningRecipes.flatMap(recipe => {
            return recipe.Ingredients.map(ingredient => {
              return {
                values: [
                  recipe.Product.Name,
                  recipe.Amount,
                  ingredient.Item.Name,
                  ingredient.Amount,
                ],
                spans: [recipe.Ingredients.length, recipe.Ingredients.length, null, null],
                links: [getItemLink(recipe.Product), null, getItemLink(ingredient.Item), null]
              }
            })
          })
        }
        options={{sortable: false}}  
      />
    {/if}
    {#if usage.Missions != null && usage.Missions.length > 0}
      <Table
        title = "Missions"
        header = { 
          {
            values: ['Name', 'Type', 'Location', 'Hand-ins'],
            widths: ['1fr', '80', '120px', 'max-content'],
          }
        }
        data = {
          usage.Missions.map(mission => {
            return {
              values: [
                mission.Name,
                mission.Type,
                mission.Location,
              ],
              links: [getTypeLink(mission.Name, 'Mission'), null, null]
            }
          })
        }
      />
    {/if}
    {#if usage.VendorOffers != null && usage.VendorOffers.length > 0}
      <Table
        title = "Vendor Offers"
        header = { 
          {
            values: ['Name', 'Location', 'Item', 'Prices'],
            widths: ['1fr', '120px', '1fr', '80px'],
          }
        }
        data = {
          usage.VendorOffers.flatMap(vendorOffer => {
            return vendorOffer.Prices.map(price => {
              return {
                values: [
                  vendorOffer?.Vendor?.Name,
                  vendorOffer?.Vendor?.Planet?.Name,
                  price.Item.Name,
                  price.Amount,
                ],
                spans: [null, null, vendorOffer.Prices.length, vendorOffer.Prices.length],
                links: [getTypeLink(vendorOffer?.Vendor?.Name, 'Vendor'), null, getItemLink(price.Item), null]
              }
            })
          })
        }
        options={{sortable: false}}  
      />
    {/if}
  </div>
{:else}
  <div>
    No data available.<br />
  </div>
{/if}
    