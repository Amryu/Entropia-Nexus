<script>
// @ts-nocheck
  import '$lib/style.css';

  import { encodeURIComponentSafe, getItemLink, getTypeLink } from '$lib/util';
  import { hasCondition } from '$lib/shopUtils';
  import { editMode } from '$lib/stores/wikiEditState.js';

  import FancyTable from './FancyTable.svelte';
  import RefiningRecipesDisplay from './wiki/RefiningRecipesDisplay.svelte';

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

  // Build vendor data
  $: vendorData = (() => {
    if (!acquisition?.VendorOffers?.length) return [];
    return acquisition.VendorOffers.map(vendorOffer => ({
      name: vendorOffer.Vendor.Name,
      nameLink: getTypeLink(vendorOffer.Vendor.Name, 'Vendor'),
      price: `${vendorOffer.Item.Properties.Economy.Value} PED`,
      specialPrice: vendorOffer.Prices?.length > 0
        ? vendorOffer.Prices.map(price => `${price.Amount} ${price.Item.Name}`).join(', ')
        : 'N/A',
      planet: vendorOffer.Vendor.Planet.Name,
      limited: vendorOffer.IsLimited ? 'Yes' : 'No'
    }));
  })();

  $: vendorColumns = [
    { key: 'name', header: 'Name', width: '1fr', formatter: (v, row) => row.nameLink ? `<a href="${row.nameLink}">${v}</a>` : v },
    { key: 'price', header: 'Price', width: '100px' },
    { key: 'specialPrice', header: 'Special Price', width: '150px' },
    { key: 'planet', header: 'Planet', width: '100px', hideOnMobile: true },
    { key: 'limited', header: 'Limited', width: '70px', hideOnMobile: true }
  ];

  // Build loot data
  $: lootData = (() => {
    if (!acquisition?.Loots?.length) return [];
    return acquisition.Loots.map(loot => ({
      mob: loot.Mob.Name,
      mobLink: getTypeLink(loot.Mob.Name, 'Mob', loot.Mob.Planet?.Name),
      item: loot.Item.Name,
      itemLink: getItemLink(loot.Item),
      planet: loot.Mob?.Planet?.Name ?? 'N/A',
      maturity: loot.Maturity.Name,
      frequency: loot.Frequency,
      frequencySort: frequencyOrder[loot.Frequency] ?? 8
    }));
  })();

  $: lootColumns = [
    { key: 'mob', header: 'Mob', width: '1fr', formatter: (v, row) => row.mobLink ? `<a href="${row.mobLink}">${v}</a>` : v },
    { key: 'item', header: 'Item', width: '180px', formatter: (v, row) => row.itemLink ? `<a href="${row.itemLink}">${v}</a>` : v },
    { key: 'planet', header: 'Planet', width: '100px', hideOnMobile: true },
    { key: 'maturity', header: 'Lowest Maturity', width: '110px', hideOnMobile: true },
    { key: 'frequency', header: 'Frequency', width: '110px', hideOnMobile: true }
  ];

  // Build shop listing data
  $: shopData = (() => {
    if (!acquisition?.ShopListings?.length) return [];

    const groups = new Map();
    for (const e of acquisition.ShopListings) {
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
      const coords = g.shop?.Coordinates;
      const locationText = (coords?.Longitude != null && coords?.Latitude != null)
        ? `${coords.Longitude}, ${coords.Latitude}`
        : 'N/A';
      const planetTech = g.shop?.Planet?.Properties?.TechnicalName ?? g.shop?.Planet?.Name;
      const wpCopy = (coords?.Longitude != null && coords?.Latitude != null && planetTech)
        ? `/wp [${planetTech}, ${coords.Longitude}, ${coords.Latitude}, ${coords?.Altitude ?? 100}, ${g.shop?.Name ?? ''}]`
        : null;

      if (g.entries.length === 0) {
        rows.push({
          shop: g.shop?.Name ?? 'N/A',
          shopLink: g.shop ? `/market/shops/${encodeURIComponentSafe(g.shop.Name)}` : null,
          planet: g.shop?.Planet?.Name ?? 'N/A',
          location: locationText,
          waypoint: wpCopy,
          stack: 'N/A',
          mu: 'N/A'
        });
      } else {
        for (const entry of g.entries) {
          rows.push({
            shop: g.shop?.Name ?? 'N/A',
            shopLink: g.shop ? `/market/shops/${encodeURIComponentSafe(g.shop.Name)}` : null,
            planet: g.shop?.Planet?.Name ?? 'N/A',
            location: locationText,
            waypoint: wpCopy,
            stack: entry.stack,
            mu: entry.muText
          });
        }
      }
    }
    return rows;
  })();

  $: shopColumns = [
    { key: 'shop', header: 'Shop', width: '1fr', formatter: (v, row) => row.shopLink ? `<a href="${row.shopLink}">${v}</a>` : v },
    { key: 'planet', header: 'Planet', width: '100px', hideOnMobile: true },
    { key: 'location', header: 'Location', width: '100px', hideOnMobile: true, formatter: (v, row) => row.waypoint ? `<span class="copyable" title="Click to copy waypoint">${v}</span>` : v },
    { key: 'stack', header: 'Stack', width: '60px' },
    { key: 'mu', header: 'MU', width: '80px', hideOnMobile: true }
  ];

  // Build blueprint data
  $: blueprintData = (() => {
    if (!acquisition?.Blueprints?.length) return [];
    return acquisition.Blueprints.map(bp => ({
      name: bp.Name,
      nameLink: getTypeLink(bp.Name, 'Blueprint'),
      level: bp.Properties.Level,
      profession: bp.Profession.Name,
      professionLink: getTypeLink(bp.Profession.Name, 'Profession')
    }));
  })();

  $: blueprintColumns = [
    { key: 'name', header: 'Blueprint', width: '1fr', formatter: (v, row) => row.nameLink ? `<a href="${row.nameLink}">${v}</a>` : v },
    { key: 'level', header: 'Level', width: '70px', hideOnMobile: true },
    { key: 'profession', header: 'Profession', width: '160px', hideOnMobile: true, formatter: (v, row) => row.professionLink ? `<a href="${row.professionLink}">${v}</a>` : v }
  ];

  // Build blueprint drop data
  $: blueprintDropData = (() => {
    if (!acquisition?.BlueprintDrops?.length) return [];
    return acquisition.BlueprintDrops.map(bp => ({
      name: bp.Name,
      nameLink: getTypeLink(bp.Name, 'Blueprint'),
      level: bp?.Properties?.Level ?? 'N/A'
    }));
  })();

  $: blueprintDropColumns = [
    { key: 'name', header: 'Name', width: '1fr', formatter: (v, row) => row.nameLink ? `<a href="${row.nameLink}">${v}</a>` : v },
    { key: 'level', header: 'Level', width: '80px', hideOnMobile: true }
  ];

  // Copy waypoint handler
  function copyWaypoint(waypoint) {
    if (waypoint) {
      navigator.clipboard.writeText(waypoint);
    }
  }
</script>

<style>
  .acquisition-container {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .acquisition-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 16px;
    align-items: start;
  }

  .acquisition-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .section-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 8px 0;
    padding: 0;
  }

  .table-wrapper {
    height: 300px;
    border-radius: 6px;
    overflow: hidden;
    border: 1px solid var(--border-color, #555);
  }

  .table-wrapper.short {
    height: 300px;
  }

  .recipe-wrapper {
    border-radius: 0;
    border: none;
    padding: 0;
    min-height: 300px;
  }

  .recipe-wrapper :global(.recipes-display) {
    width: 100%;
  }

  .no-data {
    padding: 16px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 14px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  .no-data.edit-mode-notice {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    background-color: var(--info-bg, #0c1929);
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
  }

  .no-data.edit-mode-notice svg {
    flex-shrink: 0;
    color: var(--accent-color, #4a9eff);
  }

  :global(.acquisition-container a) {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  :global(.acquisition-container a:hover) {
    text-decoration: underline;
  }

  :global(.acquisition-container .copyable) {
    cursor: pointer;
    color: var(--accent-color, #4a9eff);
  }

  :global(.acquisition-container .copyable:hover) {
    text-decoration: underline;
  }

  /* Override pointer cursor on table rows since they don't link anywhere */
  :global(.acquisition-container .table-row) {
    cursor: default;
  }

  @media (max-width: 767px) {
    .acquisition-grid {
      grid-template-columns: 1fr;
    }

    .table-wrapper {
      height: 250px;
    }

    .recipe-wrapper {
      min-height: 250px;
    }
  }
</style>

{#if $editMode}
  <div class="no-data edit-mode-notice">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="16" x2="12" y2="12"/>
      <circle cx="12" cy="8" r="1" fill="currentColor" stroke="none"/>
    </svg>
    <span>This information is inferred from other sources and cannot be edited directly.</span>
  </div>
{:else if (acquisition == null
  || ((!acquisition.VendorOffers || acquisition.VendorOffers.length === 0)
  && (!acquisition.Loots || acquisition.Loots.length === 0)
  && (!acquisition.RefiningRecipes || acquisition.RefiningRecipes.length === 0)
  && (!acquisition.Blueprints || acquisition.Blueprints.length === 0)
  && (!acquisition.BlueprintDrops || acquisition.BlueprintDrops.length === 0)
  && (!acquisition.ShopListings || acquisition.ShopListings.length === 0)
  && (!acquisition.Upgrades || acquisition.Upgrades.length === 0)
  && (!acquisition.Events || acquisition.Events.length === 0)))}
<div class="no-data">No acquisition data available for this item.</div>
{:else}
  <div class="acquisition-container">
    <div class="acquisition-grid">
      {#if acquisition.VendorOffers && acquisition.VendorOffers.length > 0}
        <div class="acquisition-section">
          <h4 class="section-title">Vendor</h4>
          <div class="table-wrapper">
            <FancyTable
              columns={vendorColumns}
              data={vendorData}
              rowHeight={40}
              searchable={true}
              sortable={true}
              emptyMessage="No vendor offers"
            />
          </div>
        </div>
      {/if}

      {#if acquisition.Loots && acquisition.Loots.length > 0}
        <div class="acquisition-section">
          <h4 class="section-title">Looted</h4>
          <div class="table-wrapper">
            <FancyTable
              columns={lootColumns}
              data={lootData}
              rowHeight={40}
              searchable={true}
              sortable={true}
              emptyMessage="No loot data"
            />
          </div>
        </div>
      {/if}

      {#if acquisition.ShopListings && acquisition.ShopListings.length > 0}
        <div class="acquisition-section">
          <h4 class="section-title">Shop Listings</h4>
          <div class="table-wrapper">
            <FancyTable
              columns={shopColumns}
              data={shopData}
              rowHeight={40}
              searchable={true}
              sortable={true}
              emptyMessage="No shop listings"
            />
          </div>
        </div>
      {/if}

      {#if acquisition.RefiningRecipes && acquisition.RefiningRecipes.length > 0}
        <div class="acquisition-section">
          <h4 class="section-title">Refining Recipes</h4>
          <div class="recipe-wrapper">
            <RefiningRecipesDisplay recipes={acquisition.RefiningRecipes} layout="list" />
          </div>
        </div>
      {/if}

      {#if acquisition.Blueprints && acquisition.Blueprints.length > 0}
        <div class="acquisition-section">
          <h4 class="section-title">Crafted</h4>
          <div class="table-wrapper short">
            <FancyTable
              columns={blueprintColumns}
              data={blueprintData}
              rowHeight={40}
              searchable={true}
              sortable={true}
              emptyMessage="No blueprint data"
            />
          </div>
        </div>
      {/if}

      {#if acquisition.BlueprintDrops && acquisition.BlueprintDrops.length > 0}
        <div class="acquisition-section">
          <h4 class="section-title">Blueprint Discovery</h4>
          <div class="table-wrapper short">
            <FancyTable
              columns={blueprintDropColumns}
              data={blueprintDropData}
              rowHeight={40}
              searchable={true}
              sortable={true}
              emptyMessage="No blueprint drops"
            />
          </div>
        </div>
      {/if}
    </div>

    {#if acquisition.Events && acquisition.Events.length > 0}
      <div class="events-section">
        <h3>Events</h3>
        <p class="no-data">Event data coming soon.</p>
      </div>
    {/if}
  </div>
{/if}
