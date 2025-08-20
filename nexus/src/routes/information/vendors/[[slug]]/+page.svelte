<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { clampDecimals, getItemLink, getTypeName } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Table from '$lib/components/Table.svelte';

  export let data;
  
  const navButtonInfo = [
    {
      Label: 'Cly',
      Title: 'Calypso',
      Type: 'calypso',
      IsRoute: false
    },
    {
      Label: 'Ars',
      Title: 'ARIS',
      Type: 'aris',
      IsRoute: false
    },
    {
      Label: 'Cyr',
      Title: 'Cyrene',
      Type: 'cyrene',
      IsRoute: false
    },
    {
      Label: 'Ark',
      Title: 'Arkadia',
      Type: 'arkadia',
      IsRoute: false
    },
    {
      Label: 'Mnr',
      Title: 'Monria',
      Type: 'monria',
      IsRoute: false
    },
    {
      Label: 'Rck',
      Title: 'ROCKtropia',
      Type: 'rocktropia',
      IsRoute: false
    },
    {
      Label: 'Tou',
      Title: 'Toulan',
      Type: 'toulan',
      IsRoute: false
    },
    {
      Label: 'NI',
      Title: 'Next Island',
      Type: 'nextisland',
      IsRoute: false
    }
  ]

  let propertiesDataFunction = (item) => {
    return {
      General: {
        Planet: item.Planet?.Name ?? 'N/A',
        Location: item.Properties.Coordinates.Longitude && item.Properties.Coordinates.Latitude
          ? `[${item.Planet?.Properties?.TechnicalName ?? item.Planet?.Name}, ${item.Properties.Coordinates.Longitude}, ${item.Properties.Coordinates.Latitude}, ${item.Properties.Coordinates.Altitude ?? 100}, ${item.Name}]`
          : 'N/A',
      },
    };
  };

  const editConfig = {
    constructor: () => ({
      Name: '',
      Properties: {
        Description: null,
        Coordinates: {
          Longitude: null,
          Latitude: null,
          Altitude: null,
        }
      },
      Planet: {
        Name: null,
      },
      Offers: [],
    }),
    dependencies: ['planets'],
    controls: [
      {
        label: 'General',
        type: 'group',
        controls: [
          { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
          { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
          { label: 'Planet', type: 'select', options: (_, d) => d.planets.filter(x => x.Id > 0).map(x => x.Name), '_get': x => x.Planet.Name, '_set': (x, v) => x.Planet.Name = v },
          { label: 'Location', type: 'multi', fields: ['Longitude', 'Latitude', 'Altitude'], '_get': x => [x.Properties.Coordinates.Longitude, x.Properties.Coordinates.Latitude, x.Properties.Coordinates.Altitude], '_set': (x, v) => { x.Properties.Coordinates.Longitude = v[0]; x.Properties.Coordinates.Latitude = v[1]; x.Properties.Coordinates.Altitude = v[2]; } }
        ]
      },
      { label: 'Offers', type: 'list', config: {
        constructor: () => ({
          IsLimited: false,
          Value: null,
          Item: {
            Name: null
          },
          Prices: []
        }),
        dependencies: ['items'],
        controls: [
          { label: 'Item', type: 'input-validator', validator: (v, d) => d.items.some(x => x.Name === v), '_get': x => x.Item.Name, '_set': (x, v) => x.Item.Name = v },
          { label: 'Value (Optional)', type: 'number', '_get': x => x.Value, '_set': (x, v) => x.Value = v },
          { label: 'Limited', type: 'checkbox', '_get': x => x.IsLimited, '_set': (x, v) => x.IsLimited = v },
          { label: 'Prices', type: 'list', config: {
            constructor: () => ({
              Item: {
                Name: null
              },
              Amount: null
            }),
            dependencies: ['items'],
            controls: [
              { label: 'Currency', type: 'input-validator', validator: (v, d) => d.items.some(x => x.Name === v), '_get': x => x.Item.Name, '_set': (x, v) => x.Item.Name = v },
              { label: 'Amount', type: 'number', '_get': x => x.Amount, '_set': (x, v) => x.Amount = v }
            ]
          }, '_get': x => x.Prices, '_set': (x, v) => x.Prices = v}
        ]
      }, '_get': x => x.Offers, '_set': (x, v) => x.Offers = v}
    ]
  };

  let tableViewInfo = {
    columns: ['Name', 'Planet'],
    columnWidths: ['1fr', '150px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Planet?.Name ?? 'N/A',
      ];
    }
  };
</script>

<style>
  .container {
    display: grid;
    grid-template-columns: minmax(500px, 1fr) minmax(500px, 1fr);
    gap: 15px;
    align-items: start;
  }
</style>

<EntityViewer
  data={data}
  user={data.session.user}
  tableViewInfo={tableViewInfo}
  navButtonInfo={navButtonInfo}
  editConfig={editConfig}
  propertiesDataFunction={propertiesDataFunction}
  title='Vendors'
  type='Vendor'
  basePath='/information/vendors'
  let:object>
  <div class="flex-item long-content">
    <h2>Offers</h2>
    <br />
    <div class="container">
      <Table
        style="grid-column: span 2;"
        title="Offers"
        header={{
          values: ['Item', 'Value', 'Special Cost', 'Type', 'Limited'],
          widths: ['1fr', 'max-content', 'Special Cost', 'max-content', 'max-content'],
        }}
        data={object.Offers.sort((a,b) => a.Item.Name.localeCompare(b.Item.Name)).map(item => ({
          values: [
            item.Item.Name,
            clampDecimals(item.Item.Properties.Economy.Value, 2, 5) + ' PED',
            item.Prices?.length > 0 ? item.Prices.map(price => `${price.Amount} ${price.Item.Name}`).join('<br />') : 'N/A',
            item.Item.Properties.Type != null ? getTypeName(item.Item.Properties.Type) : 'N/A',
            item.IsLimited ? 'Yes' : 'No'
          ],
          links: [getItemLink(item.Item), null, null, null]
        }))}
        options={{ searchable: true }} />
    </div>
  </div>
</EntityViewer>