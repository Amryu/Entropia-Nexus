<script>
// @ts-nocheck
  import '$lib/style.css';

  import { goto } from '$app/navigation';
  import { encodeURIComponentSafe, getItemLink, getTypeLink } from '$lib/util';
  import { isPercentMarkupType } from '$lib/common/itemTypes.js';
  import { editMode } from '$lib/stores/wikiEditState.js';

  import FancyTable from '../FancyTable.svelte';
  import RefiningRecipesDisplay from './RefiningRecipesDisplay.svelte';

  export let acquisition;
  export let isMultiItem = false;

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
    { key: 'name', header: 'Name', main: true, formatter: (v, row) => row.nameLink ? `<a href="${row.nameLink}">${v}</a>` : v },
    { key: 'price', header: 'Price' },
    { key: 'specialPrice', header: 'Special Price' },
    { key: 'planet', header: 'Planet' },
    { key: 'limited', header: 'Limited' }
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
    { key: 'mob', header: 'Mob', main: true, formatter: (v, row) => row.mobLink ? `<a href="${row.mobLink}">${v}</a>` : v },
    ...(isMultiItem ? [{ key: 'item', header: 'Item', formatter: (v, row) => row.itemLink ? `<a href="${row.itemLink}">${v}</a>` : v }] : []),
    { key: 'planet', header: 'Planet' },
    { key: 'maturity', header: 'Lowest Maturity' },
    { key: 'frequency', header: 'Frequency' }
  ];

  // Build combined market data (exchange orders + shop listings)
  $: marketData = (() => {
    const rows = [];

    // Exchange orders — deduplicate by seller (+ item for multi-item), keep cheapest markup
    if (acquisition?.ExchangeOrders?.length) {
      const bestBySeller = new Map();
      for (const order of acquisition.ExchangeOrders) {
        const key = isMultiItem ? `${order.seller_name}|${order.item_name || ''}` : order.seller_name;
        if (!bestBySeller.has(key) || order.markup < bestBySeller.get(key).markup) {
          bestBySeller.set(key, order);
        }
      }
      const globalExchangeItemId = acquisition._exchangeItemId;
      for (const order of bestBySeller.values()) {
        const exchId = order._exchangeItemId || globalExchangeItemId;
        rows.push({
          name: order.seller_name,
          item: order.item_name || null,
          source: 'Exchange',
          markup: order.formattedMarkup,
          markupRaw: order.markup,
          quantity: order.quantity,
          planet: order.planet,
          stale: order.state === 'stale',
          is_set: order.is_set ?? false,
          rowLink: exchId ? `/market/exchange/listings/${exchId}` : null
        });
      }
    }

    // Shop listings
    if (acquisition?.ShopListings?.length) {
      const groups = new Map();
      for (const e of acquisition.ShopListings) {
        const shopId = e?.Shop?.Id ?? e?.ShopId ?? e?.shopId;
        const itemId = e?.Item?.Id ?? e?.ItemId ?? e?.itemId;
        if (!shopId || !itemId) continue;
        const key = `${shopId}|${itemId}`;
        if (!groups.has(key)) {
          groups.set(key, { shop: e.Shop, item: e.Item, entries: [] });
        }
        const g = groups.get(key);
        const s = Number(e.StackSize ?? e.stack_size ?? 0);
        const m = Number(e.Markup ?? e.markup ?? 0);
        if (!Number.isNaN(s) && s > 0 && !Number.isNaN(m) && m > 0) {
          g.entries.push({ stack: s, markup: m });
        }
      }

      for (const g of Array.from(groups.values())) {
        const itemType = g.item?.Properties?.Type || g.item?.Type || g.item?.t || '';
        const itemName = g.item?.Name || g.item?.n || '';
        const isPercent = isPercentMarkupType(itemType, itemName);
        if (g.entries.length === 0) continue;
        for (const entry of g.entries) {
          rows.push({
            name: g.shop?.Name ?? 'N/A',
            source: 'Shop',
            markup: isPercent ? `${entry.markup.toFixed(2)}%` : `+${entry.markup.toFixed(2)}`,
            markupRaw: entry.markup,
            quantity: entry.stack,
            planet: g.shop?.Planet?.Name ?? 'N/A',
            stale: false,
            rowLink: g.shop ? `/market/shops/${encodeURIComponentSafe(g.shop.Name)}` : null
          });
        }
      }
    }

    return rows;
  })();

  $: hasMarketData = marketData.length > 0;

  $: marketColumns = [
    { key: 'name', header: 'Name', main: true, formatter: (v, row) => {
      const label = row.stale ? `<span class="stale-text">${v}</span>` : v;
      const setBadge = row.is_set ? ' <span class="badge badge-subtle badge-accent">Set</span>' : '';
      return label + setBadge;
    }},
    ...(isMultiItem ? [{ key: 'item', header: 'Item' }] : []),
    { key: 'source', header: 'Source', width: '80px' },
    { key: 'markup', header: 'Markup', sortValue: (row) => row.markupRaw, formatter: (v, row) => row.stale ? `<span class="stale-text">${v}</span>` : v },
    { key: 'quantity', header: 'Qty' },
    { key: 'planet', header: 'Planet' }
  ];

  function handleMarketRowClick(e) {
    const { row } = e.detail;
    if (row.rowLink) goto(row.rowLink);
  }

  // Build mission reward data
  $: missionRewardData = (() => {
    if (!acquisition?.MissionRewards?.length) return [];
    return acquisition.MissionRewards.map(mr => {
      let qty = '';
      if (mr.Quantity != null) qty = String(mr.Quantity);
      else if (mr.MinQuantity != null && mr.MaxQuantity != null) qty = `${mr.MinQuantity}–${mr.MaxQuantity}`;
      else if (mr.PedValue != null) qty = `${mr.PedValue} PED`;
      return {
        mission: mr.Mission.Name,
        missionLink: getTypeLink(mr.Mission.Name, 'Mission'),
        type: mr.Mission.Type ?? '',
        planet: mr.Mission.Planet?.Name ?? '',
        quantity: qty,
        rarity: mr.Rarity ?? '',
        isChoice: mr.IsChoice
      };
    });
  })();

  $: missionRewardColumns = [
    { key: 'mission', header: 'Mission', main: true, formatter: (v, row) => {
      let label = row.missionLink ? `<a href="${row.missionLink}">${v}</a>` : v;
      if (row.isChoice) label += ' <span class="badge badge-subtle badge-accent">Choice</span>';
      return label;
    }},
    { key: 'type', header: 'Type' },
    { key: 'planet', header: 'Planet' },
    { key: 'quantity', header: 'Qty' },
    { key: 'rarity', header: 'Rarity' }
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
    { key: 'name', header: 'Blueprint', main: true, formatter: (v, row) => row.nameLink ? `<a href="${row.nameLink}">${v}</a>` : v },
    { key: 'level', header: 'Level' },
    { key: 'profession', header: 'Profession', formatter: (v, row) => row.professionLink ? `<a href="${row.professionLink}">${v}</a>` : v }
  ];

  // Build blueprint drop data
  $: blueprintDropData = (() => {
    if (!acquisition?.BlueprintDrops?.length) return [];
    return acquisition.BlueprintDrops.map(bp => ({
      name: bp.Name,
      nameLink: getTypeLink(bp.Name, 'Blueprint'),
      level: bp?.Properties?.Level ?? 'N/A',
      rarity: bp?.Properties?.DropRarity ?? '-'
    }));
  })();

  $: blueprintDropColumns = [
    { key: 'name', header: 'Name', main: true, formatter: (v, row) => row.nameLink ? `<a href="${row.nameLink}">${v}</a>` : v },
    { key: 'level', header: 'Level' },
    { key: 'rarity', header: 'Rarity' }
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
    max-width: 100%;
    overflow: hidden;
  }

  .acquisition-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(400px, 100%), 1fr));
    gap: 16px;
    align-items: start;
    max-width: 100%;
  }

  .acquisition-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: 100%;
    overflow: hidden;
  }

  .acquisition-section :global(.fancy-table-container) {
    max-height: 596px;
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

  .recipe-wrapper {
    border-radius: 0;
    border: none;
    padding: 0;
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

  .exchange-link {
    color: var(--accent-color, #4a9eff);
    font-size: 13px;
  }

  .exchange-link:hover {
    text-decoration: underline;
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

  /* Market rows are clickable */
  :global(.market-section .table-row) {
    cursor: pointer;
  }

  :global(.acquisition-container .stale-text) {
    color: var(--text-muted, #999);
  }

  @media (max-width: 899px) {
    .acquisition-grid {
      grid-template-columns: 1fr;
    }

    .acquisition-section :global(.fancy-table-container) {
      max-height: 499px;
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
  && (!acquisition.MissionRewards || acquisition.MissionRewards.length === 0)
  && !hasMarketData
  && (!acquisition.Upgrades || acquisition.Upgrades.length === 0)
  && (!acquisition.Events || acquisition.Events.length === 0)))}
<div class="no-data">
  No acquisition data available for this item.
  {#if acquisition?._exchangeItemId}
    <br><a href="/market/exchange/listings/{acquisition._exchangeItemId}" class="exchange-link">Create a sell order on the Exchange</a>
  {/if}
</div>
{:else}
  <div class="acquisition-container">
    <div class="acquisition-grid">
      {#if acquisition.VendorOffers && acquisition.VendorOffers.length > 0}
        <div class="acquisition-section">
          <h4 class="section-title">Vendor</h4>
          <FancyTable
            columns={vendorColumns}
            data={vendorData}
            rowHeight={32}
            searchable={true}
            sortable={true}
            compact
            fitContent
            emptyMessage="No vendor offers"
          />
        </div>
      {/if}

      {#if acquisition.Loots && acquisition.Loots.length > 0}
        <div class="acquisition-section">
          <h4 class="section-title">Looted</h4>
          <FancyTable
            columns={lootColumns}
            data={lootData}
            rowHeight={32}
            searchable={true}
            sortable={true}
            compact
            fitContent
            emptyMessage="No loot data"
          />
        </div>
      {/if}

      {#if acquisition.MissionRewards && acquisition.MissionRewards.length > 0}
        <div class="acquisition-section">
          <h4 class="section-title">Mission Reward</h4>
          <FancyTable
            columns={missionRewardColumns}
            data={missionRewardData}
            rowHeight={32}
            searchable={true}
            sortable={true}
            compact
            fitContent
            emptyMessage="No mission rewards"
          />
        </div>
      {/if}

      {#if hasMarketData}
        <div class="acquisition-section market-section">
          <h4 class="section-title">Market</h4>
          <FancyTable
            columns={marketColumns}
            data={marketData}
            rowHeight={32}
            searchable={true}
            sortable={true}
            compact
            fitContent
            defaultSort={{ column: 'markup', order: 'ASC' }}
            emptyMessage="No market listings"
            on:rowClick={handleMarketRowClick}
          />
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
          <FancyTable
            columns={blueprintColumns}
            data={blueprintData}
            rowHeight={32}
            searchable={true}
            sortable={true}
            compact
            fitContent
            emptyMessage="No blueprint data"
          />
        </div>
      {/if}

      {#if acquisition.BlueprintDrops && acquisition.BlueprintDrops.length > 0}
        <div class="acquisition-section">
          <h4 class="section-title">Blueprint Discovery</h4>
          <FancyTable
            columns={blueprintDropColumns}
            data={blueprintDropData}
            rowHeight={32}
            searchable={true}
            sortable={true}
            compact
            fitContent
            emptyMessage="No blueprint drops"
          />
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
