<script>
  // @ts-nocheck
  import '$lib/style.css';

  import { getItemLink, getTypeLink } from '$lib/util';
  import { editMode } from '$lib/stores/wikiEditState.js';

  import FancyTable from './FancyTable.svelte';
  import RefiningRecipesDisplay from './wiki/RefiningRecipesDisplay.svelte';

  export let item;
  export let usage;

  // Build blueprint data
  $: blueprintData = (() => {
    if (!usage?.Blueprints?.length) return [];
    return usage.Blueprints.map(blueprint => ({
      name: blueprint.Name,
      nameLink: getTypeLink(blueprint.Name, 'Blueprint'),
      type: blueprint.Properties?.Type ?? 'N/A',
      amount: blueprint.MaterialAmount ?? 'N/A'
    }));
  })();

  $: blueprintColumns = [
    { key: 'name', header: 'Blueprint', main: true, formatter: (v, row) => row.nameLink ? `<a href="${row.nameLink}">${v}</a>` : v },
    { key: 'type', header: 'Type' },
    { key: 'amount', header: 'Amount' }
  ];

  // Build mission data
  $: missionData = (() => {
    if (!usage?.Missions?.length) return [];
    return usage.Missions.map(mission => ({
      name: mission.Name,
      nameLink: getTypeLink(mission.Name, 'Mission'),
      type: mission.Type ?? 'N/A',
      location: mission.Location ?? 'N/A',
      handins: mission.HandIns ?? 'N/A'
    }));
  })();

  $: missionColumns = [
    { key: 'name', header: 'Name', main: true, formatter: (v, row) => row.nameLink ? `<a href="${row.nameLink}">${v}</a>` : v },
    { key: 'type', header: 'Type' },
    { key: 'location', header: 'Location' },
    { key: 'handins', header: 'Hand-ins' }
  ];

  // Build vendor offer data (where this item is used as currency)
  $: vendorOfferData = (() => {
    if (!usage?.VendorOffers?.length) return [];
    return usage.VendorOffers.flatMap(vendorOffer =>
      vendorOffer.Prices.map(price => ({
        vendor: vendorOffer?.Vendor?.Name ?? 'N/A',
        vendorLink: getTypeLink(vendorOffer?.Vendor?.Name, 'Vendor'),
        planet: vendorOffer?.Vendor?.Planet?.Name ?? 'N/A',
        item: vendorOffer?.Item?.Name ?? 'N/A',
        itemLink: getItemLink(vendorOffer?.Item),
        amount: price?.Amount ?? 'N/A'
      }))
    );
  })();

  $: vendorOfferColumns = [
    { key: 'vendor', header: 'Vendor', main: true, formatter: (v, row) => row.vendorLink ? `<a href="${row.vendorLink}">${v}</a>` : v },
    { key: 'planet', header: 'Planet' },
    { key: 'item', header: 'Item', formatter: (v, row) => row.itemLink ? `<a href="${row.itemLink}">${v}</a>` : v },
    { key: 'amount', header: 'Amount' }
  ];

  // Check if there's any usage data
  $: hasUsageData = usage != null && (
    (usage.Blueprints?.length > 0) ||
    (usage.RefiningRecipes?.length > 0) ||
    (usage.Missions?.length > 0) ||
    (usage.VendorOffers?.length > 0 && usage.VendorOffers.some(vo => vo.Prices?.length > 0))
  );
</script>

<style>
  .usage-container {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 100%;
    overflow: hidden;
  }

  .usage-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(400px, 100%), 1fr));
    gap: 16px;
    align-items: start;
    max-width: 100%;
  }

  .usage-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: 100%;
    overflow: hidden;
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
    height: 596px;
    border-radius: 6px;
    overflow: hidden;
    border: 1px solid var(--border-color, #555);
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

  :global(.usage-container a) {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  :global(.usage-container a:hover) {
    text-decoration: underline;
  }

  /* Override pointer cursor on table rows since they don't link anywhere */
  :global(.usage-container .table-row) {
    cursor: default;
  }

  @media (max-width: 767px) {
    .usage-grid {
      grid-template-columns: 1fr;
    }

    .table-wrapper {
      height: 499px;
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
{:else if !hasUsageData}
  <div class="no-data">No usage data available for this item.</div>
{:else}
  <div class="usage-container">
    <div class="usage-grid">
      {#if usage.Blueprints && usage.Blueprints.length > 0}
        <div class="usage-section">
          <h4 class="section-title">Blueprints</h4>
          <div class="table-wrapper">
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

      {#if usage.RefiningRecipes && usage.RefiningRecipes.length > 0}
        <div class="usage-section">
          <h4 class="section-title">Refining Recipes</h4>
          <div class="recipe-wrapper">
            <RefiningRecipesDisplay
              recipes={usage.RefiningRecipes}
              layout="list"
              linkProduct={true}
              linkIngredients={true}
              currentEntityName={item?.Name || null}
            />
          </div>
        </div>
      {/if}

      {#if usage.Missions && usage.Missions.length > 0}
        <div class="usage-section">
          <h4 class="section-title">Missions</h4>
          <div class="table-wrapper">
            <FancyTable
              columns={missionColumns}
              data={missionData}
              rowHeight={40}
              searchable={true}
              sortable={true}
              emptyMessage="No mission data"
            />
          </div>
        </div>
      {/if}

      {#if usage.VendorOffers && usage.VendorOffers.length > 0 && usage.VendorOffers.some(vo => vo.Prices?.length > 0)}
        <div class="usage-section">
          <h4 class="section-title">Vendor Currency</h4>
          <div class="table-wrapper">
            <FancyTable
              columns={vendorOfferColumns}
              data={vendorOfferData}
              rowHeight={40}
              searchable={true}
              sortable={true}
              emptyMessage="No vendor offers"
            />
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}
