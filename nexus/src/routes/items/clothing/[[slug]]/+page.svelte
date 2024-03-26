<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { clampDecimals, groupBy } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";

  export let data;

  let propertiesDataFunction = (clothing) => {
    let onEquip = {};

    if (clothing.EffectsOnEquip != null && clothing.EffectsOnEquip.length > 0) {
      clothing.EffectsOnEquip
        .sort((a,b) => a.Name.localeCompare(b.Name))
        .forEach(effect => onEquip[effect.Name] = `${effect.Values.Strength}${effect.Values.Unit}`);
    }

    let onSetEquip = {};

    if (clothing.EffectsOnSetEquip != null && clothing.EffectsOnSetEquip.length > 0) {
      Object.entries(groupBy(clothing.EffectsOnSetEquip, x => x.Values.MinSetPieces))
        .sort(([a],[b]) => Number(a) - Number(b))
        .forEach(([key, effects]) => onSetEquip[key + ' Pieces'] = { Value: effects.map(effect => `${effect.Values.Strength}${effect.Values.Unit} ${effect.Name}`) });
    }

    return {
      General: {
        Weight: clothing.Properties?.Weight != null ? `${clampDecimals(clothing.Properties?.Weight, 1, 6)}kg` : 'N/A',
        Type: clothing.Properties?.Type ?? 'N/A',
        Slot: clothing.Properties?.Slot ?? 'N/A',
        Gender: clothing.Properties?.Gender ?? 'N/A',
      },
      Economy: {
        MaxTT: {
          Label: 'Max. TT',
          Value: clothing.Properties?.Economy?.MaxTT != null ? `${clampDecimals(clothing.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        },
        MinTT: {
          Label: 'Min. TT',
          Value: clothing.Properties?.Economy?.MinTT != null ? `${clampDecimals(clothing.Properties?.Economy?.MinTT, 2, 8)} PED` : 'N/A',
        },
      },
      "Equip Effects": clothing.EffectsOnEquip?.length > 0 ? onEquip : null,
      "Set Effects": clothing.EffectsOnSetEquip?.length > 0 ? onSetEquip : null,
    }
  };

  let tableViewInfo = {
    columns: ['Name', 'Weight', 'Type', 'Slot', 'Gender', 'Max. TT'],
    columnWidths: ['1fr', '80px', '100px', '100px', '100px', '100px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
        item.Properties?.Type ?? 'N/A',
        item.Properties?.Slot ?? 'N/A',
        item.Properties?.Gender ?? 'N/A',
        item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
      ];
    }
  };
</script>

<EntityViewer
  data={data}
  tableViewInfo={tableViewInfo}
  propertiesDataFunction={propertiesDataFunction}
  title='Clothing'
  basePath='/items/clothing'
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