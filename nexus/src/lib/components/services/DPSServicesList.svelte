<script>
  // @ts-nocheck
  import { goto } from '$app/navigation';
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { getEstimatedDPS, getMaxCostPerHour } from '$lib/components/services/serviceCalculations';

  export let services = [];
  export let weapons = [];
  export let pets = [];
  export let clothingItems = [];
  export let armorSets = [];
  export let consumables = [];
  export let armors = [];
  export let armorPlatings = [];
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

  function getDPSValue(service) {
    if (!service.equipment || !weapons.length) return 0;

    const weaponEquipment = service.equipment.filter(e =>
      e.is_primary !== false && e.item_type === 'weapons'
    );
    const primaryWeaponEquip = weaponEquipment.find(e => e.is_primary) || weaponEquipment[0];

    if (!primaryWeaponEquip?.item_name) return 0;

    const weapon = weapons.find(w => w.Name === primaryWeaponEquip.item_name);
    if (!weapon) return 0;

    const weaponAttachments = {
      amplifier: null,
      absorber: null,
      scope: null,
      scopeSight: null,
      sight: null,
      matrix: null,
      implant: null
    };

    const dps = getEstimatedDPS(
      service,
      weapon,
      weaponAttachments,
      'Damage',
      [],
      consumables,
      pets,
      clothingItems,
      armorSets,
      {},
      {}
    );

    return dps;
  }

  function getDPSDisplay(service) {
    const dps = getDPSValue(service);
    if (dps === 0) return 'TBD';
    return dps.toFixed(1);
  }

  function getMaxDecayValue(service) {
    if (!service.equipment || !weapons.length) return 0;

    const weaponEquipment = service.equipment.filter(e =>
      e.is_primary !== false && e.item_type === 'weapons'
    );
    const primaryWeaponEquip = weaponEquipment.find(e => e.is_primary) || weaponEquipment[0];

    if (!primaryWeaponEquip?.item_name) return 0;

    const weapon = weapons.find(w => w.Name === primaryWeaponEquip.item_name);
    if (!weapon) return 0;

    const weaponAttachments = {
      amplifier: null,
      absorber: null,
      scope: null,
      scopeSight: null,
      sight: null,
      matrix: null,
      implant: null
    };

    const costPerHour = getMaxCostPerHour(
      service,
      weapon,
      weaponAttachments,
      'Economy',
      [],
      consumables,
      pets,
      clothingItems,
      armorSets,
      {},
      {},
      { ammo: 100, weapon: 100 }
    );

    return costPerHour;
  }

  function getMaxDecayDisplay(service) {
    const decay = getMaxDecayValue(service);
    if (decay === 0) return 'TBD';
    return decay.toFixed(2);
  }

  function getPricingInfo(service) {
    const details = service.dps_details;
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

  // Precompute values for sorting
  $: tableData = services.map(service => ({
    ...service,
    _dps: getDPSValue(service),
    _dpsDisplay: getDPSDisplay(service),
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
      width: '2fr'
    },
    {
      key: '_dps',
      header: 'DPS',
      sortable: true,
      searchable: false,
      width: '80px',
      formatter: (value, row) => row._dpsDisplay
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
      width: '1.2fr'
    },
    {
      key: '_pricing',
      header: 'Pricing',
      sortable: false,
      searchable: false,
      width: '120px'
    },
    {
      key: 'owner_name',
      header: 'Provider',
      sortable: true,
      searchable: true,
      width: '1fr',
      formatter: (value) => value || 'Unknown'
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
    rowHeight={48}
    sortable={true}
    searchable={true}
    emptyMessage="No DPS services found"
    {loading}
    on:rowClick={handleRowClick}
  />
</div>

<style>
  .table-wrapper {
    height: 400px;
    min-height: 300px;
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
