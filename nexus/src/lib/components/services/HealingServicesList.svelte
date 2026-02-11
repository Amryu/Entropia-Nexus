<script>
  // @ts-nocheck
  import { goto } from '$app/navigation';
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { encodeURIComponentSafe } from '$lib/util';
  import { getEstimatedHealingHPS, getMaxHealingDecayPerHour } from './serviceCalculations';

  export let services = [];
  export let medicalTools = [];
  export let medicalChips = [];
  export let clothingItems = [];
  export let armorSets = [];
  export let consumables = [];
  export let loading = false;

  function viewService(service) {
    goto(`/market/services/${service.id}`);
  }

  function getLocationDisplay(service) {
    const basePlanet = service.planet_name || 'No base';
    if (service.willing_to_travel) {
      return `${basePlanet} (will travel)`;
    }
    return basePlanet;
  }

  function getHealingPerSecond(service) {
    const enabledConsumables = {};
    const allConsumables = service.equipment?.filter(e => e.item_type === 'consumables') || [];
    for (const consumable of allConsumables) {
      const consumableData = consumables.find(item => item.Name === consumable.item_name);
      const isEnhancer = consumableData?.Properties?.Type === 'Enhancer';
      enabledConsumables[consumable.item_name] = isEnhancer;
    }

    const enabledTierEnhancers = {};
    const allEquipment = service.equipment || [];
    for (const equip of allEquipment) {
      if (equip.tier && equip.tier > 0) {
        enabledTierEnhancers[equip.item_name] = true;
      }
    }

    const hps = getEstimatedHealingHPS(service, medicalTools, medicalChips, clothingItems, armorSets, consumables, null, enabledConsumables, enabledTierEnhancers);
    if (hps.base === 'TBD') return 0;
    return hps.base !== 'TBD' ? hps.base : 0;
  }

  function getHPSDisplay(service) {
    const enabledConsumables = {};
    const allConsumables = service.equipment?.filter(e => e.item_type === 'consumables') || [];
    for (const consumable of allConsumables) {
      const consumableData = consumables.find(item => item.Name === consumable.item_name);
      const isEnhancer = consumableData?.Properties?.Type === 'Enhancer';
      enabledConsumables[consumable.item_name] = isEnhancer;
    }

    const enabledTierEnhancers = {};
    const allEquipment = service.equipment || [];
    for (const equip of allEquipment) {
      if (equip.tier && equip.tier > 0) {
        enabledTierEnhancers[equip.item_name] = true;
      }
    }

    const hps = getEstimatedHealingHPS(service, medicalTools, medicalChips, clothingItems, armorSets, consumables, null, enabledConsumables, enabledTierEnhancers);
    if (hps.base === 'TBD') return 'TBD';
    return hps.base;
  }

  function getMaxDecayDisplay(service) {
    const enabledConsumables = {};
    const allConsumables = service.equipment?.filter(e => e.item_type === 'consumables') || [];
    for (const consumable of allConsumables) {
      const consumableData = consumables.find(item => item.Name === consumable.item_name);
      const isEnhancer = consumableData?.Properties?.Type === 'Enhancer';
      enabledConsumables[consumable.item_name] = isEnhancer;
    }

    const enabledTierEnhancers = {};
    const allEquipment = service.equipment || [];
    for (const equip of allEquipment) {
      if (equip.tier && equip.tier > 0) {
        enabledTierEnhancers[equip.item_name] = true;
      }
    }

    const decay = getMaxHealingDecayPerHour(service, medicalTools, medicalChips, clothingItems, armorSets, consumables, null, enabledConsumables, enabledTierEnhancers);
    if (decay.base === 'TBD') return 'TBD';
    return decay.base;
  }

  function getMaxDecayValue(service) {
    const enabledConsumables = {};
    const allConsumables = service.equipment?.filter(e => e.item_type === 'consumables') || [];
    for (const consumable of allConsumables) {
      const consumableData = consumables.find(item => item.Name === consumable.item_name);
      const isEnhancer = consumableData?.Properties?.Type === 'Enhancer';
      enabledConsumables[consumable.item_name] = isEnhancer;
    }

    const enabledTierEnhancers = {};
    const allEquipment = service.equipment || [];
    for (const equip of allEquipment) {
      if (equip.tier && equip.tier > 0) {
        enabledTierEnhancers[equip.item_name] = true;
      }
    }

    const decay = getMaxHealingDecayPerHour(service, medicalTools, medicalChips, clothingItems, armorSets, consumables, null, enabledConsumables, enabledTierEnhancers);
    if (decay.base === 'TBD') return 0;
    return decay.base !== 'TBD' ? parseFloat(decay.base) : 0;
  }

  function getPricingInfo(service) {
    const details = service.healing_details;
    if (!details) return 'Free';

    const parts = [];
    if (details.accepts_time_billing && details.rate_per_hour) {
      parts.push(`${parseFloat(details.rate_per_hour).toFixed(2)} PED/h`);
    }
    if (details.accepts_decay_billing) {
      parts.push('Decay');
    }

    if (parts.length === 0) {
      return 'Free';
    }

    return parts.join(' + ');
  }

  function getProviderLink(service, value) {
    if (!service?.owner_id) return value || 'Unknown';
    const identifier = service.owner_name || service.owner_id;
    const url = `/users/${encodeURIComponentSafe(String(identifier))}`;
    return `<a class="provider-link" href="${url}" onclick="event.stopPropagation()">${value || 'Unknown'}</a>`;
  }

  // Precompute values for sorting
  $: tableData = services.map(service => ({
    ...service,
    _hps: getHealingPerSecond(service),
    _hpsDisplay: getHPSDisplay(service),
    _decay: getMaxDecayValue(service),
    _decayDisplay: getMaxDecayDisplay(service),
    _location: getLocationDisplay(service),
    _pricing: getPricingInfo(service)
  }));

  const columns = [
    {
      key: 'title',
      header: 'Service',
      sortable: true,
      searchable: true,
      width: '1.8fr'
    },
    {
      key: '_hps',
      header: 'HP/s',
      sortable: true,
      searchable: false,
      width: '80px',
      formatter: (value, row) => row._hpsDisplay
    },
    {
      key: '_decay',
      header: 'Decay/h',
      sortable: true,
      searchable: false,
      width: '90px',
      formatter: (value, row) => row._decayDisplay
    },
    {
      key: '_location',
      header: 'Location',
      sortable: true,
      searchable: true,
      width: '1fr'
    },
    {
      key: '_pricing',
      header: 'Pricing',
      sortable: false,
      searchable: false,
      width: '180px'
    },
    {
      key: 'owner_name',
      header: 'Provider',
      sortable: true,
      searchable: true,
      width: '1fr',
      formatter: (value, row) => getProviderLink(row, value)
    }
  ];

  function handleRowClick(event) {
    const { row } = event.detail;
    viewService(row);
  }
</script>

<div class="table-wrapper">
  <FancyTable
    {columns}
    data={tableData}
    rowHeight={32}
    compact={true}
    sortable={true}
    searchable={true}
    emptyMessage="No healing services found"
    {loading}
    on:rowClick={handleRowClick}
  />
</div>

<style>
  .table-wrapper {
    height: 400px;
    min-height: 300px;
  }

  :global(.provider-link) {
    color: var(--accent-color);
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    height: 100%;
  }

  :global(.provider-link:hover) {
    text-decoration: underline;
  }

  @media (max-width: 768px) {
    .table-wrapper {
      height: 350px;
    }

    .table-wrapper :global(.fancy-table th:nth-child(2)),
    .table-wrapper :global(.fancy-table td:nth-child(2)),
    .table-wrapper :global(.fancy-table th:nth-child(3)),
    .table-wrapper :global(.fancy-table td:nth-child(3)) {
      display: none;
    }
  }
</style>
