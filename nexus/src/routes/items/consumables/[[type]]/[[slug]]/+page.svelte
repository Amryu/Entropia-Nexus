<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { getTimeString, clampDecimals, groupBy } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";

  export let data;

  const navButtonInfo = [
    {
      Label: 'Cns',
      Title: 'Consumables',
      Type: 'consumables',
    },
    {
      Label: 'CCC',
      Title: 'Creature Control Capsules',
      Type: 'creaturecontrolcapsules',
    },
  ];

  function getCategory(type) {
    switch (type) {
      case 'consumables':
        return 'Buff Consumable';
      case 'creaturecontrolcapsules':
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
        Type: additional.type === 'consumables'
          ? consumable.Properties?.Type ?? 'N/A'
          : null,
      },
      Economy: {
        Value: consumable.Properties?.Economy?.MaxTT != null ? `${clampDecimals(consumable.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
      },
      "Consume Effects": additional.type === 'consumables' && consumable.EffectsOnConsume != null && consumable.EffectsOnConsume.length > 0 ? onConsume : null,
      Creature: additional.type === 'creaturecontrolcapsules' ? {
        Mob: {
          Label: 'Mob',
          Value: consumable.Mob?.Name != null ? consumable.Mob?.Name : 'N/A',
        },
        Profession: {
          Label: 'Profession',
          Tooltip: 'The profession and the required level to use the item',
          Value: [consumable.Profession?.Name != null ? consumable.Profession?.Name : 'N/A', consumable.Properties?.Level != null ? consumable.Properties?.Level : 'N/A'],
        },
      } : null,
    };
  };

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
    consumables: {
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
    creaturecontrolcapsules: {
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
  tableViewInfo={tableViewInfo}
  navButtonInfo={navButtonInfo}
  propertiesDataFunction={propertiesDataFunction}
  title='Consumables'
  basePath='/items/consumables'
  let:object
  let:additional>
  <div class="flex-item-double">
    <div class="big-title">{object.Name}</div>
  </div>
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>