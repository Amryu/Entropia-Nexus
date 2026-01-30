<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { clampDecimals, groupBy } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";
  import { editConfigEffectsOnEquip, editConfigEffectsOnSetEquip } from '$lib/editConfigUtil.js';

  export let data;

  let propertiesDataFunction = (clothing) => {
    let onEquip = {};

    if (clothing.EffectsOnEquip != null && clothing.EffectsOnEquip.length > 0) {
      clothing.EffectsOnEquip
        .sort((a,b) => a.Name.localeCompare(b.Name))
        .forEach(effect => onEquip[effect.Name] = `${effect.Values.Strength}${effect.Values.Unit}`);
    }

    let onSetEquip = {};

    if (clothing?.Set?.EffectsOnSetEquip != null && clothing.Set.EffectsOnSetEquip.length > 0) {
      Object.entries(groupBy(clothing.Set.EffectsOnSetEquip, x => x.Values.MinSetPieces))
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
      "Set Effects": clothing?.Set?.EffectsOnSetEquip?.length > 0 ? {
        Name: clothing.Set.Name,
        ...onSetEquip
      } : null,
    }
  };

  const editConfig = {
    constructor: () => ({
      Name: '',
      Properties: {
        Description: null,
        Weight: null,
        Type: null,
        Slot: null,
        Gender: null,
        Economy: {
          MaxTT: null,
          MinTT: null,
        }
      },
      Set: {
        Name: null,
        EffectsOnSetEquip: [],
      },
      EffectsOnEquip: [],
    }),
    dependencies: ['effects', 'equipsets'],
    controls: [
      {
        label: 'General',
        type: 'group',
        controls: [
          { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
          { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
          { label: 'Weight', type: 'number', '_get': x => x.Properties.Weight, '_set': (x, v) => x.Properties.Weight = v },
          { label: 'Type', type: 'text', '_get': x => x.Properties.Type, '_set': (x, v) => x.Properties.Type = v },
          { label: 'Slot', type: 'text', '_get': x => x.Properties.Slot, '_set': (x, v) => x.Properties.Slot = v },
          { label: 'Gender', type: 'select', options: _ => ['Both', 'Male', 'Female'], '_get': x => x.Properties.Gender, '_set': (x, v) => x.Properties.Gender = v },
        ]
      },
      {
        label: 'Economy',
        type: 'group',
        controls: [
          { label: 'Max. TT', type: 'number', '_get': x => x.Properties.Economy.MaxTT, '_set': (x, v) => x.Properties.Economy.MaxTT = v },
          { label: 'Min. TT', type: 'number', '_get': x => x.Properties.Economy.MinTT, '_set': (x, v) => x.Properties.Economy.MinTT = v },
        ]
      },
      {
        label: 'Set',
        type: 'group',
        controls: [
          { label: 'Name', type: 'input-select', options: (_, d) => d.equipsets.map(x => x.Name).sort((a,b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })), '_get': x => x.Set?.Name, '_set': (x, v, d) => { x.Set ||= {}; x.Set.Name = v && v.length > 0 ? v : null; x.Set.EffectsOnSetEquip = d.equipsets.find(y => y.Name === v)?.EffectsOnSetEquip ?? [] }},
          { '_if': x => x.Set?.Name != null && x.Set.Name.trim().length > 0, label: 'Set Effects', type: 'list', config: editConfigEffectsOnSetEquip, '_get': x => x.Set.EffectsOnSetEquip, '_set': (x, v) => x.Set.EffectsOnSetEquip = v},
        ]
      },
      { label: 'Equip Effects', type: 'list', config: editConfigEffectsOnEquip, '_get': x => x.EffectsOnEquip, '_set': (x, v) => x.EffectsOnEquip = v},
    ]
  }

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
  user={data.session.user}
  tableViewInfo={tableViewInfo}
  editConfig={editConfig}
  propertiesDataFunction={propertiesDataFunction}
  title='Clothing'
  type='Clothing'
  basePath='/items/clothing'
  let:object
  let:additional>
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>