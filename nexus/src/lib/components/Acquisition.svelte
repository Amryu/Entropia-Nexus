<script>
// @ts-nocheck
  import '$lib/style.css';

  import { encodeURIComponentSafe, getItemLink, getTypeLink } from '$lib/util';
  import { hasCondition } from '$lib/shopUtils';

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

  // Build rows for Shops section (grouped by Shop+Item) with spans across Shop/Planet/Location
  $: shopsRows = (() => {
    try {
      const list = acquisition?.ShopListings ?? [];
      if (!Array.isArray(list) || list.length === 0) return [];
      const groups = new Map();
      for (const e of list) {
        // server returns fields with capitalized names: Shop, Group, Item, ItemId, StackSize, Markup
        const shopId = e?.Shop?.Id ?? e?.ShopId ?? e?.shopId;
        const itemId = e?.Item?.Id ?? e?.ItemId ?? e?.itemId;
        if (!shopId || !itemId) continue;
        const key = `${shopId}|${itemId}`;
        if (!groups.has(key)) {
          groups.set(key, { shop: e.Shop, item: e.Item, ItemId: e.ItemId ?? e.Item?.Id ?? itemId, entries: [] });
        }
        const g = groups.get(key);
        const s = Number(e.StackSize ?? e.stack_size ?? 0);
        const m = Number(e.Markup ?? e.markup ?? 0);
        if (!Number.isNaN(s) && s > 0 && !Number.isNaN(m) && m > 0) {
          const muText = hasCondition(g.item) ? `+${m.toFixed(2)}` : `${m.toFixed(2)}%`;
          g.entries.push({ stack: s, muText });
        }
      }
      const rows = [];
      for (const g of Array.from(groups.values())) {
        const planetTech = g.shop?.Planet?.Properties?.TechnicalName ?? g.shop?.Planet?.Name;
        const coords = g.shop?.Coordinates;
        const locationText = (coords?.Longitude != null && coords?.Latitude != null)
          ? `${coords.Longitude}, ${coords.Latitude}`
          : 'N/A';
        const wpCopy = (coords?.Longitude != null && coords?.Latitude != null && planetTech)
          ? `/wp [${planetTech}, ${coords.Longitude}, ${coords.Latitude}, ${coords?.Altitude ?? 100}, ${g.shop?.Name ?? ''}]`
          : null;
    const spanLen = Math.max(1, g.entries.length);
        if (g.entries.length === 0) {
          // still render one row with N/A stack/MU
          rows.push({
            values: [
              g.shop?.Name ?? 'N/A',
              g.shop?.Planet?.Name ?? 'N/A',
              locationText,
              'N/A',
              'N/A'
            ],
  // Use true as a marker to indicate spanned columns; Table will compute dynamic lengths
  spans: [true, true, true, null, null],
            links: [
              g.shop ? `/market/shops/${encodeURIComponentSafe(g.shop.Name)}` : null,
              null,
              null,
              null,
              null
            ],
            copyables: [false, false, !!wpCopy, false, false],
            onClicks: [null, null, () => { if (wpCopy) navigator.clipboard.writeText(wpCopy); }, null, null],
            tooltips: [null, null, wpCopy ? 'Click to copy waypoint' : null, null, null]
          });
          continue;
        }
    for (let i = 0; i < g.entries.length; i++) {
          const entry = g.entries[i];
          rows.push({
            values: [
              g.shop?.Name ?? 'N/A',
              g.shop?.Planet?.Name ?? 'N/A',
              locationText,
              entry.stack,
              entry.muText
            ],
  // Use true as a marker to indicate spanned columns; Table will compute dynamic lengths
  spans: [true, true, true, null, null],
            links: [
              g.shop ? `/market/shops/${encodeURIComponentSafe(g.shop.Name)}` : null,
              null,
              null,
              null,
              null
            ],
            copyables: [false, false, !!wpCopy, false, false],
            onClicks: [null, null, () => { if (wpCopy) navigator.clipboard.writeText(wpCopy); }, null, null],
            tooltips: [null, null, wpCopy ? 'Click to copy waypoint' : null, null, null]
          });
        }
      }
      return rows;
    } catch {
      return [];
    }
  })();
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
  && (!acquisition.ShopListings || acquisition.ShopListings.length === 0)
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
      options={{searchable: true}} />
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
      options={{searchable: true}} />
    {/if}
    {#if acquisition.ShopListings && acquisition.ShopListings.length > 0}
    <Table
      title="Shop Listings"
      header={{
        values: ['Shop', 'Planet', 'Location', 'Stack', 'MU'],
        widths: ['1fr', '120px', '110px', '50px', '90px']
      }}
      data={shopsRows}
      options={{ searchable: true, sortable: false }} />
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