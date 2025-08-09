<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { clampDecimals } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";
  import Usage from '$lib/components/Usage.svelte';

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
        Description: null,
        Weight: null,
        Economy: {
          MaxTT: null
        }
      },
      RefiningRecipes: []
    }),
    dependencies: ['materials'],
    controls: [
      {
        label: 'General',
        type: 'group',
        controls: [
          { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
          { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
          { label: 'Weight', type: 'number', '_get': x => x.Properties.Weight, '_set': (x, v) => x.Properties.Weight = v }
        ]
      },
      {
        label: 'Economy',
        type: 'group',
        controls: [
          { label: 'Value', type: 'number', '_get': x => x.Properties.Economy.MaxTT, '_set': (x, v) => x.Properties.Economy.MaxTT = v }
        ]
      },
      {
        label: 'Refining Recipes',
        type: 'list',
        config: {
          constructor: () => ({
            Amount: 1,
            Ingredients: []
          }),
          dependencies: ['items'],
          controls: [
            { label: 'Product Amount', type: 'number', step: '1', min: '1', '_get': x => x.Amount, '_set': (x, v) => x.Amount = v },
            { 
              label: 'Ingredients', 
              type: 'list', 
              config: {
                constructor: () => ({
                  Item: {
                    Name: null
                  },
                  Amount: 1
                }),
                controls: [
                  { label: 'Item', type: 'input-validator', validator: (v, d) => d.items.find(y => y.Name === v), '_get': (x, d) => x.Item?.Name ?? '', '_set': (x, v, d) => x.Item.Name = v },
                  { label: 'Ingredient Amount', type: 'number', step: '1', min: '1', '_get': x => x.Amount, '_set': (x, v) => x.Amount = v }
                ]
              },
              '_get': x => x.Ingredients, 
              '_set': (x, v) => x.Ingredients = v 
            }
          ]
        },
        '_get': x => x.RefiningRecipes || [],
        '_set': (x, v) => x.RefiningRecipes = v
      }
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
  title='Materials'
  type='Material'
  basePath='/items/materials'
  let:object
  let:additional>
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
  <div class="flex-item long-content">
    <Usage item={object} usage={additional.usage} />
  </div>
</EntityViewer>