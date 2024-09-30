<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { clampDecimals } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";

  export let data;

  const navButtonInfo = [
    {
      Label: 'Frn',
      Title: 'Furniture',
      Type: 'furniture',
    },
    {
      Label: 'Dcr',
      Title: 'Decorations',
      Type: 'decorations',
    },
    {
      Label: 'StC',
      Title: 'Storage Containers',
      Type: 'storagecontainers',
    },
    {
      Label: 'Sgn',
      Title: 'Signs',
      Type: 'signs',
    }
  ];

  function getCategory(type) {
    switch (type) {
      case 'furniture':
        return 'Furniture'
      case 'decorations':
        return 'Decoration'
      case 'storagecontainers':
        return 'Storage Container'
      case 'signs':
        return 'Sign'
      default:
        return 'Other';
    }
  }

  let propertiesDataFunction = (furnishing, additional) => {
    let category = getCategory(additional.type);

    return {
      General: {
        Weight: furnishing.Properties?.Weight != null ? `${clampDecimals(furnishing.Properties?.Weight, 1, 6)}kg` : 'N/A',
        Category: category,
        Type: additional.type === 'furniture' || additional.type === 'decorations'
          ? furnishing.Properties?.Type ?? 'N/A'
          : null,
        ItemPoints: additional.type === 'signs' ? {
          Label: 'Item Points',
          Value: furnishing.Properties?.ItemPoints != null ? furnishing.Properties?.ItemPoints : 'N/A',
        } : null,
        ItemCapacity: additional.type === 'storagecontainers' ? {
          Label: 'Item Capacity',
          Value: furnishing.Properties?.ItemCapacity != null ? furnishing.Properties?.ItemCapacity : 'N/A',
        } : null,
        WeightCapacity: additional.type === 'storagecontainers' ? {
          Label: 'Weight Capacity',
          Value: furnishing.Properties?.WeightCapacity != null ? `${clampDecimals(furnishing.Properties?.WeightCapacity, 1, 6)}kg` : 'N/A',
        } : null,
      },
      Economy: {
        MaxTT: {
          Label: 'Max. TT',
          Value: furnishing.Properties?.Economy?.MaxTT != null ? `${clampDecimals(furnishing.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        },
        MinTT: {
          Label: 'Min. TT',
          Value: furnishing.Properties?.Economy?.MinTT != null ? `${clampDecimals(furnishing.Properties?.Economy?.MinTT, 2, 8)} PED` : 'N/A',
        },
        Cost: additional.type === 'signs' ? {
          Label: 'Cost',
          Value: furnishing.Properties?.Economy?.Cost != null ? `${furnishing.Properties?.Economy?.Cost.toFixed(2)} PEC` : 'N/A',
        } : null,
      },
      Display: additional.type === 'signs' ? {
        AspectRatio: {
          Label: 'Aspect Ratio',
          Value: furnishing.Properties?.Display.AspectRatio != null ? furnishing.Properties?.Display.AspectRatio : 'N/A',
        },
        CanShowLocalContent: {
          Label: 'Local Content',
          Value: furnishing.Properties?.Display.CanShowLocalContent ? 'Yes' : 'No',
        },
        CanShowImagesAndText: {
          Label: 'Images & Text',
          Value: furnishing.Properties?.Display.CanShowImagesAndText ? 'Yes' : 'No',
        },
        CanShowEffects: {
          Label: 'Effects',
          Value: furnishing.Properties?.Display.CanShowEffects ? 'Yes' : 'No',
        },
        CanShowMultimedia: {
          Label: 'Multimedia',
          Value: furnishing.Properties?.Display.CanShowMultimedia ? 'Yes' : 'No',
        },
        CanShowParticipantContent: {
          Label: 'Participant Content',
          Value: furnishing.Properties?.Display.CanShowParticipantContent ? 'Yes' : 'No',
        },
      } : null,
    };
  };

  const editConfig = {
    furniture: {
      constructor: () => ({
        Name: '',
        Properties: {
          Description: null,
          Type: null,
          Weight: null,
          Economy: {
            MaxTT: null,
          }
        }
      }),
      controls: [
        {
          label: 'General',
          type: 'group',
          controls: [
            { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
            { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
            { label: 'Type', type: 'text', '_get': x => x.Properties.Type, '_set': (x, v) => x.Properties.Type = v },
            { label: 'Weight', type: 'number', '_get': x => x.Properties.Weight, '_set': (x, v) => x.Properties.Weight = v },
          ]
        },
        {
          label: 'Economy',
          type: 'group',
          controls: [
            { label: 'Max. TT', type: 'number', '_get': x => x.Properties.Economy.MaxTT, '_set': (x, v) => x.Properties.Economy.MaxTT = v }
          ]
        }
      ]
    },
    decorations: {
      constructor: () => ({
        Name: '',
        Properties: {
          Description: null,
          Weight: null,
          Economy: {
            MaxTT: null,
          }
        }
      }),
      controls: [
        {
          label: 'General',
          type: 'group',
          controls: [
            { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
            { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
            { label: 'Weight', type: 'number', '_get': x => x.Properties.Weight, '_set': (x, v) => x.Properties.Weight = v },
          ]
        },
        {
          label: 'Economy',
          type: 'group',
          controls: [
            { label: 'Max. TT', type: 'number', '_get': x => x.Properties.Economy.MaxTT, '_set': (x, v) => x.Properties.Economy.MaxTT = v }
          ]
        }
      ],
    },
    storagecontainers: {
      constructor: () => ({
        Name: '',
        Properties: {
          Description: null,
          Weight: null,
          ItemCapacity: null,
          WeightCapacity: null,
          Economy: {
            MaxTT: null,
          }
        }
      }),
      controls: [
        {
          label: 'General',
          type: 'group',
          controls: [
            { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
            { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
            { label: 'Weight', type: 'number', '_get': x => x.Properties.Weight, '_set': (x, v) => x.Properties.Weight = v },
            { label: 'Item Capacity', type: 'number', '_get': x => x.Properties.ItemCapacity, '_set': (x, v) => x.Properties.ItemCapacity = v },
            { label: 'Weight Capacity', type: 'number', '_get': x => x.Properties.WeightCapacity, '_set': (x, v) => x.Properties.WeightCapacity = v },
          ]
        },
        {
          label: 'Economy',
          type: 'group',
          controls: [
            { label: 'Max. TT', type: 'number', '_get': x => x.Properties.Economy.MaxTT, '_set': (x, v) => x.Properties.Economy.MaxTT = v }
          ]
        }
      ],
    },
    signs: {
      constructor: () => ({
        Name: '',
        Properties: {
          Name: '',
          Weight: null,
          ItemPoints: null,
          Display: {
            AspectRatio: null,
            CanShowLocalContent: false,
            CanShowImagesAndText: false,
            CanShowEffects: false,
            CanShowMultimedia: false,
            CanShowParticipantContent: false,
          },
          Economy: {
            Cost: null,
            MaxTT: null,
          }
        }
      }),
      controls: [
        {
          label: 'General',
          type: 'group',
          controls: [
            { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
            { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
            { label: 'Weight', type: 'number', '_get': x => x.Properties.Weight, '_set': (x, v) => x.Properties.Weight = v },
            { label: 'Item Points', type: 'number', '_get': x => x.Properties.ItemPoints, '_set': (x, v) => x.Properties.ItemPoints = v },
          ]
        },
        {
          label: 'Display',
          type: 'group',
          controls: [
            { label: 'Aspect Ratio', type: 'range', step: 1, min: 1, max: 100, '_get': x => x.Properties.Display.AspectRatio ? x.Properties.Display.AspectRatio.split(':') : [null, null], '_set': (x, v) => x.Properties.Display.AspectRatio = v.join(':') },
            { label: 'Local Content', type: 'checkbox', '_get': x => x.Properties.Display.CanShowLocalContent, '_set': (x, v) => x.Properties.Display.CanShowLocalContent = v },
            { label: 'Images & Text', type: 'checkbox', '_get': x => x.Properties.Display.CanShowImagesAndText, '_set': (x, v) => x.Properties.Display.CanShowImagesAndText = v },
            { label: 'Effects', type: 'checkbox', '_get': x => x.Properties.Display.CanShowEffects, '_set': (x, v) => x.Properties.Display.CanShowEffects = v },
            { label: 'Multimedia', type: 'checkbox', '_get': x => x.Properties.Display.CanShowMultimedia, '_set': (x, v) => x.Properties.Display.CanShowMultimedia = v },
            { label: 'Particip. Content', type: 'checkbox', '_get': x => x.Properties.Display.CanShowParticipantContent, '_set': (x, v) => x.Properties.Display.CanShowParticipantContent = v },
          ]
        },
        {
          label: 'Economy',
          type: 'group',
          controls: [
            { label: 'Cost', type: 'number', '_get': x => x.Properties.Economy.Cost, '_set': (x, v) => x.Properties.Economy.Cost = v },
            { label: 'Max. TT', type: 'number', '_get': x => x.Properties.Economy.MaxTT, '_set': (x, v) => x.Properties.Economy.MaxTT = v }
          ]
        }
      ],
    }
  }

  let tableViewInfo = {
    all: {
      columns: ['Name', 'Category', 'Max. TT'],
      columnWidths: ['1fr', '100px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Category ?? 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        ];
      }
    },
    furniture: {
      columns: ['Name', 'Type', 'Max. TT'],
      columnWidths: ['1fr', '100px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Type ?? 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        ];
      }
    },
    decorations: {
      columns: ['Name', 'Type', 'Max. TT'],
      columnWidths: ['1fr', '100px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Type ?? 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        ];
      }
    },
    storagecontainers: {
      columns: ['Name', 'Item Capacity', 'Weight Capacity', 'Max. TT'],
      columnWidths: ['1fr', '120px', '120px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.ItemCapacity != null ? item.Properties?.ItemCapacity : 'N/A',
          item.Properties?.WeightCapacity != null ? `${clampDecimals(item.Properties?.WeightCapacity, 1, 6)}kg` : 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        ];
      }
    },
    signs: {
      columns: ['Name', 'Aspect Ratio', 'Local Content', 'Images & Text', 'Effects', 'Multimedia', 'Participant Content', 'Cost', 'Max. TT'],
      columnWidths: ['1fr', '100px', '110px', '110px', '100px', '100px', '140px', '100px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Display.AspectRatio != null ? item.Properties?.Display.AspectRatio : 'N/A',
          item.Properties?.Display.CanShowLocalContent ? 'Yes' : 'No',
          item.Properties?.Display.CanShowImagesAndText ? 'Yes' : 'No',
          item.Properties?.Display.CanShowEffects ? 'Yes' : 'No',
          item.Properties?.Display.CanShowMultimedia ? 'Yes' : 'No',
          item.Properties?.Display.CanShowParticipantContent ? 'Yes' : 'No',
          item.Properties?.Economy?.Cost != null ? `${item.Properties?.Economy?.Cost.toFixed(2)} PEC` : 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        ];
      }
    }
  }
</script>

<EntityViewer
  data={data}
  user={data.session.user}
  tableViewInfo={tableViewInfo}
  navButtonInfo={navButtonInfo}
  editConfig={editConfig}
  propertiesDataFunction={propertiesDataFunction}
  title='Furnishings'
  type={data?.additional?.type === 'furniture'
    ? 'Furniture'
    : data?.additional?.type === 'decorations'
    ? 'Decoration'
    : data?.additional?.type === 'storagecontainers'
    ? 'StorageContainer'
    : 'Sign'}
  basePath='/items/furnishings'
  let:object
  let:additional>
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>