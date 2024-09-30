<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { clampDecimals, getTypeLink } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";
  import Construction from "./Construction.svelte";

  export let data;

  const craftDuration = 5;

  let propertiesDataFunction = (blueprint) => {
    let cost = blueprint.Materials?.reduce((acc, mat) => acc + (mat.Item?.Properties?.Economy?.MaxTT * mat?.Amount), 0);

    let cyclePerHour = cost ? (3600 / craftDuration) * cost : null;

    return {
      General: {
        Weight: `0.1kg`,
        Level: blueprint.Properties?.Level ?? 'N/A',
        Type: blueprint.Properties?.Type ?? 'N/A',
        Book: blueprint.Book?.Name ?? 'N/A',
        ProductAmountInterval: {
          Label: 'Product Amount',
          Value: `${blueprint.Properties?.MinimumCraftAmount ?? 'N/A'} - ${blueprint.Properties?.MaximumCraftAmount ?? 'N/A'}`,
        }
      },
      Economy: {
        Cost: {
          Label: 'Cost',
          Value: cost != null ? `${cost.toFixed(2)} PED` : 'N/A',
          Bold: true
        },
        IsBoosted: {
          Label: 'Boosted',
          Tooltip: 'A boosted blueprint will return a significantly higher TT value.',
          Value: blueprint.Properties?.IsBoosted ? 'Yes' : 'No',
        }
      },
      Skill: {
        SiB: {
          Label: 'SiB',
          Tooltip: 'Skill Increase Bonus',
          Value: blueprint.Properties?.Skill.IsSiB ? 'Yes' : 'No',
        },
        Profession: {
          Label: 'Profession',
          LinkValue: [blueprint.Profession?.Name != null ? getTypeLink(blueprint.Profession.Name, 'Profession') : null, null],
          Value: [blueprint.Profession?.Name ?? 'N/A', `${blueprint.Properties?.Skill.LearningIntervalStart ?? 'N/A'} - ${blueprint.Properties?.Skill.LearningIntervalEnd ?? 'N/A'}`],
        },
      },
      Misc: {
        CyclePerHour: {
          Label: 'PED/h',
          Tooltip: 'PED cycled per hour',
          Value: cyclePerHour != null ? `${cyclePerHour.toFixed(2)} PED` : 'N/A',
        }
      }
    };
  };

  const editConfig = {
    constructor: () => ({
      Name: null,
      Properties: {
        Description: null,
        Type: null,
        Level: null,
        IsBoosted: false,
        MinimumCraftAmount: null,
        MaximumCraftAmount: null,
        Skill: {
          IsSiB: false,
          LearningIntervalStart: null,
          LearningIntervalEnd: null
        }
      },
      Book: {
        Name: null
      },
      Profession: {
        Name: null
      },
      Product: {
        Name: null
      },
      Materials: []
    }),
    dependencies: ['items', 'materials', 'blueprintbooks',  'professions'],
    controls: [
      {
        label: 'General',
        type: 'group',
        controls: [
          { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v},
          { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
          { label: 'Type', type: 'select', options: _ => [
            'Weapon',
            'Textile',
            'Vehicle',
            'Enhancer',
            'Furniture',
            'Tool',
            'Armor',
            'Attachment',
            'Metal Component',
            'Electrical Component',
            'Mechanical Component'
          ], '_get': x => x.Properties.Type, '_set': (x, v) => x.Properties.Type = v},
          { label: 'Level', type: 'number', step: 1, min: 0, '_get': x => x.Properties.Level, '_set': (x, v) => x.Properties.Level = v},
          { label: 'Boosted', type: 'checkbox', '_get': x => x.Properties.IsBoosted, '_set': (x, v) => x.Properties.IsBoosted = v},
          { label: 'Book', type: 'select', options: (_, d) => d.blueprintbooks.map(x => x.Name), '_get': x => x.Book.Name, '_set': (x, v) => x.Book.Name = v},
          { label: 'Product', type: 'select', options: (_, d) => d.items.filter(x => x.Properties.Type !== 'Blueprint' &&  x.Properties.Type !== 'Pet').map(x => x.Name), '_get': x => x.Product.Name, '_set': (x, v) => x.Product.Name = v},
          { label: 'Product Amount', type: 'range', step: 1, min: 1, '_get': x => [x.Properties.MinimumCraftAmount, x.Properties.MaximumCraftAmount], '_set': (x, v) => { x.Properties.MinimumCraftAmount = v[0]; x.Properties.MaximumCraftAmount = v[1]; }},
        ]
      },
      {
        label: 'Skill',
        type: 'group',
        controls: [
          { label: 'SiB', type: 'checkbox', '_get': x => x.Properties.Skill.IsSiB, '_set': (x, v) => x.Properties.Skill.IsSiB = v},
          { label: 'Profession', type: 'select', options: (_, d) => d.professions.filter(x => x.Category.Name === 'Manufacturing').map(x => x.Name), '_get': x => x.Profession.Name, '_set': (x, v) => x.Profession.Name = v},
          { label: 'Learning Interval', type: 'range', step: 0.1, min: 0, '_get': x => [x.Properties.Skill.LearningIntervalStart, x.Properties.Skill.LearningIntervalEnd], '_set': (x, v) => { x.Properties.Skill.LearningIntervalStart = v[0]; x.Properties.Skill.LearningIntervalEnd = v[1]; }},
        ]
      },
      { label: 'Materials', type: 'list', config: {
        constructor: () => ({
          Item: {
            Name: null,
          },
          Amount: null
        }),
        dependencies: ['materials'],
        controls: [
          { label: 'Material', type: 'select', options: (_, d) => d.materials.map(x => x.Name), '_get': x => x.Item?.Name, '_set': (x, v) => x.Item.Name = v},
          { label: 'Amount', type: 'number', step: 1, min: 1, '_get': x => x.Amount, '_set': (x, v) => x.Amount = v},
        ]
      }, '_get': x => x.Materials, '_set': (x, v) => x.Materials = v}
    ]
  }

  let tableViewInfo = {
    columns: ['Name', 'Type', 'Level', 'Book', 'Cost', 'Boosted', 'SiB', 'Min', 'Max'],
    columnWidths: ['1fr', '170px', '70px', '250px', '90px', '70px', '70px', '70px', '70px'],
    rowValuesFunction: (item) => {
      let cost = item.Materials?.reduce((acc, mat) => acc + (mat.Item.Properties.Economy.MaxTT * mat.Amount), 0);

      return [
        item.Name,
        item.Properties?.Type ?? 'N/A',
        item.Properties?.Level ?? 'N/A',
        item.Book?.Name ?? 'N/A',
        cost != null ? clampDecimals(cost, 2, 4) + ' PED' : 'N/A',
        item.Properties?.IsBoosted ? 'Yes' : 'No',
        item.Properties?.Skill?.LearningIntervalStart != null ? 'Yes' : 'No',
        item.Properties?.Skill?.LearningIntervalStart != null ? item.Properties?.Skill?.LearningIntervalStart.toFixed(1) : 'N/A',
        item.Properties?.Skill?.LearningIntervalEnd != null ? item.Properties?.Skill?.LearningIntervalEnd.toFixed(1) : 'N/A',
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
  title='Blueprints'
  type='Blueprint'
  basePath='/items/blueprints'
  let:object
  let:additional>
  <!-- Construction -->
  <div class="flex-item long-content">
    <Construction blueprint={object} />
  </div>
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>