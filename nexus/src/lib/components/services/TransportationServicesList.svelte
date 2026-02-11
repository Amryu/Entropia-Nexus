<script>
  // @ts-nocheck
  import { goto } from '$app/navigation';
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { encodeURIComponentSafe } from '$lib/util';

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

  function getProviderLink(service, value) {
    if (!service?.owner_id) return value || 'Unknown';
    const identifier = service.owner_name || service.owner_id;
    const url = `/users/${encodeURIComponentSafe(String(identifier))}`;
    return `<a class="provider-link" href="${url}" onclick="event.stopPropagation()">${value || 'Unknown'}</a>`;
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
      width: '1.8fr'
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
      width: '1fr'
    },
    {
      key: '_priceSort',
      header: 'Price',
      sortable: true,
      searchable: false,
      width: '180px',
      formatter: (value, row) => row._priceDisplay
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

    .table-wrapper :global(.fancy-table th:nth-child(3)),
    .table-wrapper :global(.fancy-table td:nth-child(3)),
    .table-wrapper :global(.fancy-table th:nth-child(5)),
    .table-wrapper :global(.fancy-table td:nth-child(5)) {
      display: none;
    }
  }
</style>
