<script>
  // @ts-nocheck
  import { goto } from '$app/navigation';
  import FancyTable from '$lib/components/FancyTable.svelte';

  export let services = [];
  export let loading = false;

  function viewService(service) {
    goto(`/market/services/${service.id}`);
  }

  function getTransportationType(service) {
    const type = service.transportation_details?.transportation_type;
    const labels = {
      regular: 'Regular',
      warp_equus: 'Warp (Equus)',
      warp_privateer: 'Warp (Privateer)'
    };
    return labels[type] || type || 'Not specified';
  }

  function getShipName(service) {
    return service.transportation_details?.ship_name || 'Not specified';
  }

  function getCurrentLocation(service) {
    if (service.transportation_details?.departure_location) {
      return service.transportation_details.departure_location;
    }
    return service.planet_name || 'Not specified';
  }

  function getPriceSpan(service) {
    const minPrice = service.min_price;
    const maxPrice = service.max_price;

    if (!minPrice && !maxPrice) {
      return 'See details';
    }

    if (minPrice === maxPrice) {
      return `${parseFloat(minPrice).toFixed(2)} PED`;
    }

    return `${parseFloat(minPrice).toFixed(2)} - ${parseFloat(maxPrice).toFixed(2)} PED`;
  }

  // Precompute values for sorting
  $: tableData = services.map(service => ({
    ...service,
    _type: getTransportationType(service),
    _ship: getShipName(service),
    _location: getCurrentLocation(service),
    _priceDisplay: getPriceSpan(service),
    _priceSort: service.min_price ? parseFloat(service.min_price) : 999999
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
      key: '_type',
      header: 'Type',
      sortable: true,
      searchable: false,
      width: '1fr'
    },
    {
      key: '_ship',
      header: 'Ship',
      sortable: true,
      searchable: true,
      width: '1fr'
    },
    {
      key: '_location',
      header: 'Location',
      sortable: true,
      searchable: true,
      width: '1.2fr'
    },
    {
      key: '_priceSort',
      header: 'Price',
      sortable: true,
      searchable: false,
      width: '120px',
      formatter: (value, row) => row._priceDisplay
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
    emptyMessage="No transportation services found"
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

    .table-wrapper :global(.fancy-table th:nth-child(3)),
    .table-wrapper :global(.fancy-table td:nth-child(3)),
    .table-wrapper :global(.fancy-table th:nth-child(5)),
    .table-wrapper :global(.fancy-table td:nth-child(5)) {
      display: none;
    }
  }
</style>
