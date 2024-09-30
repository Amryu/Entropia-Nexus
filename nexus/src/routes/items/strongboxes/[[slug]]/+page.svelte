<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { clampDecimals } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";
  import Loots from './Loots.svelte';

  export let data;

  let propertiesDataFunction = (material) => {
    return {
      General: {
        Weight: material.Properties?.Weight != null ? `${clampDecimals(material.Properties?.Weight, 1, 6)}kg` : 'N/A',
      },
      Economy: {
        Value: material.Properties?.Economy?.MaxTT != null ? `${clampDecimals(material.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
      }
    };
  };

  const editConfig = {
    constructor: () => ({
      Name: '',
      Properties: {
        Description: null
      },
      Loots: []
    }),
    controls: [
      {
        label: 'General',
        type: 'group',
        controls: [
          { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
          { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v }
        ]
      },
      { label: 'Loots', type: 'list', config: {
        constructor: () => ({
          Rarity: "Common",
          AvailableFrom: null,
          AvailableUntil: null,
          Item: {
            Name: null,
          }
        }),
        dependencies: ['items'],
        controls: [
          { label: 'Item', type: 'input-validator', validator: (x, d) => d.items.some(y => y.Name === x), '_get': x => x.Item.Name, '_set': (x, v) => x.Item.Name = v },
          { label: 'Rarity', type: 'select', options: (_, d) => ["Common", "Uncommong", "Rare", "Epic", "Supreme", "Legendary", "Mythical"], '_get': x => x.Rarity, '_set': (x, v) => x.Rarity = v},
          { label: 'Available From', type: 'date', '_get': x => x.AvailableFrom, '_set': (x, v) => x.AvailableFrom = v},
          { label: 'Available Until', type: 'date', '_get': x => x.AvailableUntil, '_set': (x, v) => x.AvailableUntil = v}
        ]
      }, '_get': x => x.Loots, '_set': (x, v) => x.Loots = v}
    ]
  };

  let tableViewInfo = {
    columns: ['Name', 'Weight', 'Max. TT'],
    columnWidths: ['1fr', '80px', '100px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
        item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
      ];
    }
  };
</script>

<EntityViewer
  data={data}
  user={data.session.user}
  tableViewInfo={tableViewInfo}
  editConfig={editConfig}
  propertiesDataFunction={propertiesDataFunction}
  title='Strongboxes'
  type='Strongbox'
  basePath='/items/strongboxes'
  let:object
  let:additional>
  <!-- Loots -->
  <div class="flex-item long-content">
    <Loots loots={object.Loots} />
  </div>
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>