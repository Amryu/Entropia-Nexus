<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { getTimeString, clampDecimals, groupBy, getTypeLink } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";

  export let data;

  const navButtonInfo = [
    {
      Label: 'Stim',
      Title: 'Stimulants',
      Type: 'stimulants',
    },
    {
      Label: 'Cap',
      Title: 'Creature Control Capsules',
      Type: 'capsules',
    },
  ];

  function getCategory(type) {
    switch (type) {
      case 'stimulants':
        return 'Stimulants';
      case 'capsules':
        return 'Creature Control Capsule';
      default:
        return 'Other';
    }
  }

  let propertiesDataFunction = (consumable, additional) => {
    let category = getCategory(additional.type);

    let onConsume = {};

    if (consumable.EffectsOnConsume != null && consumable.EffectsOnConsume.length > 0) {
      consumable.EffectsOnConsume
        .sort((a,b) => a.Name.localeCompare(b.Name))
        .forEach(effect => onConsume[effect.Name] = `${effect.Values.Strength}${effect.Values.Unit} ${effect.Values.DurationSeconds > 0 ? `for ${getTimeString(effect.Values.DurationSeconds)}` : ''}`);
    }

    return {
      General: {
        Weight: consumable.Properties?.Weight != null ? `${clampDecimals(consumable.Properties?.Weight, 1, 6)}kg` : 'N/A',
        Category: category,
        Type: additional.type === 'stimulants'
          ? consumable.Properties?.Type ?? 'N/A'
          : null,
        MinProfessionLevel: additional.type === 'capsules' ? {
          Label: 'Min. Profession Level',
          Value: consumable.Properties?.MinProfessionLevel != null ? consumable.Properties?.MinProfessionLevel : 'N/A',
        } : null,
      },
      Economy: {
        Value: consumable.Properties?.Economy?.MaxTT != null ? `${clampDecimals(consumable.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
      },
      "Consume Effects": additional.type === 'stimulants' && consumable.EffectsOnConsume != null && consumable.EffectsOnConsume.length > 0 ? onConsume : null,
      Creature: additional.type === 'capsules' ? {
        Mob: {
          Label: 'Mob',
          Value: consumable.Mob?.Name != null ? consumable.Mob?.Name : 'N/A',
        },
        Profession: {
          Label: 'Profession',
          Tooltip: 'The profession and the required level to use the item',
          LinkValue: [consumable.Profession?.Name != null ? getTypeLink(consumable.Profession.Name, 'Profession') : null, null],
          Value: [consumable.Profession?.Name != null ? consumable.Profession?.Name : 'N/A', consumable.Properties?.Level != null ? consumable.Properties?.Level : 'N/A'],
        },
      } : null,
    };
  };

  const editConfig = {
    stimulants: {
      constructor: () => ({
        Name: '',
        Properties: {
          Weight: null,
          Type: null,
          Economy: {
            MaxTT: null
          }
        },
        EffectsOnConsume: []
      }),
      controls: [
        {
          label: 'General',
          type: 'group',
          controls: [
            { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
            { label: 'Weight', type: 'number', '_get': x => x.Properties.Weight, '_set': (x, v) => x.Properties.Weight = v },
            { label: 'Type', type: 'select', options: _ => ['Pill', 'Nanobots', 'Chip'], '_get': x => x.Properties.Type, '_set': (x, v) => x.Properties.Type = v }
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
          label: 'Effects on Consume',
          type: 'list',
          config: {
            constructor: () => ({
              Name: '',
              Values: {
                Strength: null,
                DurationSeconds: null,
              }
            }),
            dependencies: ['effects'],
            controls: [
              { label: 'Name', type: 'select', options: (_, d) => d.effects.map(x => x.Name), '_get': x => x.Name, '_set': (x, v) => x.Name = v },
              { label: 'Strength', type: 'number', '_get': x => x.Values.Strength, '_set': (x, v) => x.Values.Strength = v },
              { label: 'Duration (s)', type: 'number', '_get': x => x.Values.DurationSeconds, '_set': (x, v) => x.Values.DurationSeconds = v }
            ]
          },
          '_get': x => x.EffectsOnConsume,
          '_set': (x, v) => x.EffectsOnConsume = v
        }
      ]
    },
    capsules: {
      constructor: () => ({
        Name: '',
        Properties: {
          Economy: {
            MaxTT: null
          }
        },
        Mob: {
          Name: null
        },
        Profession: {
          Name: null
        }
      }),
      dependencies: ['mobs', 'professions'],
      controls: [
        {
          label: 'General',
          type: 'group',
          controls: [
            { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
            { label: 'Mob', type: 'select', options: (_, d) => d.mobs.map(x => x.Name), '_get': x => x.Mob.Name, '_set': (x, v) => x.Mob.Name = v },
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
          label: 'Skill',
          type: 'group',
          controls: [
            { label: 'Profession', type: 'select', options: (_, d) => d.professions.map(x => x.Name), '_get': x => x.Profession.Name, '_set': (x, v) => x.Profession.Name = v },
            { label: 'Min. Prof. Level', type: 'number', '_get': x => x.Properties.MinProfessionLevel, '_set': (x, v) => x.Properties.MinProfessionLevel = v }
          ]
        }
      ]
    }
  }

  let tableViewInfo = {
    all: {
      columns: ['Name', 'Category', 'Type', 'Max. TT'],
      columnWidths: ['1fr', '180px', '100px', '100px'],
      rowValuesFunction: (item) => {
        let category = getCategory(item._type);

        return [
          item.Name,
          category ?? 'N/A',
          item.Properties?.Type ?? 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        ];
      }
    },
    stimulants: {
      columns: ['Name', 'Category', 'Type', 'Max. TT', 'Effects'],
      columnWidths: ['230px', '80px', '80px', '90px', '1fr'],
      rowValuesFunction: (item) => {
        let effects = null;

        if (item.EffectsOnConsume != null && item.EffectsOnConsume.length > 0) {
          let effectsGroupedByDuration = groupBy(item.EffectsOnConsume, x => x.Values.DurationSeconds)

          effects = Object.keys(effectsGroupedByDuration).map(x => {
            let effects = effectsGroupedByDuration[x].map(x => `${x.Values.Strength ?? ''}${x.Values.Unit ?? ''} ${x.Name}`).join(' & ');
            return `${effects} for ${getTimeString(x)}`;
          });
        }

        return [
          item.Name,
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          item.Properties?.Type ?? 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
          effects != null ? effects.join(', ') : 'N/A',
        ];
      }
    },
    capsules: {
      columns: ['Name', 'Mob', 'Profession', 'Max. TT'],
      columnWidths: ['1fr', '200px', '150px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Mob?.Name != null ? item.Mob?.Name : 'N/A',
          item.Profession?.Name != null ? item.Profession?.Name : 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        ];
      }
    }
  };
</script>

<EntityViewer
  data={data}
  user={data.session.user}
  tableViewInfo={tableViewInfo}
  navButtonInfo={navButtonInfo}
  editConfig={editConfig}
  propertiesDataFunction={propertiesDataFunction}
  title='Consumables'
  type={data?.additional?.type === 'stimulants' ? 'Consumable' : 'Capsule'}
  basePath='/items/consumables'
  let:object
  let:additional>
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>