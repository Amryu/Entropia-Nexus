<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { hasItemTag, clampDecimals, groupBy } from "$lib/util";

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  
  import Tiering from "$lib/components/Tiering.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";
  import ArmorSetPieces from "./ArmorSetPieces.svelte";
  import { editConfigEffectsOnEquip, editConfigEffectsOnSetEquip, getEditConfigTier } from '$lib/editConfigUtil';

  export let data;

  function getTotalDefense(item) {
    return (item.Properties?.Defense?.Impact ?? 0) + (item.Properties?.Defense?.Cut ?? 0) + (item.Properties?.Defense?.Stab ?? 0) + (item.Properties?.Defense?.Penetration ?? 0) + (item.Properties?.Defense?.Shrapnel ?? 0) + (item.Properties?.Defense?.Burn ?? 0) + (item.Properties?.Defense?.Cold ?? 0) + (item.Properties?.Defense?.Acid ?? 0) + (item.Properties?.Defense?.Electric ?? 0);
  }

  function getMaxArmorDecay(item) {
    return item.Properties?.Economy.Durability && getTotalDefense(item)
      ? getTotalDefense(item) * ((100000 - item.Properties?.Economy.Durability) / 100000) * 0.05
      : null;
  }

  function getTotalAbsorption(item) {
    return item.Properties?.Economy.MaxTT && getMaxArmorDecay(item)
      ? getTotalDefense(item) * ((item.Properties?.Economy.MaxTT - (item.Properties?.Economy.MinTT ?? 0)) / (getMaxArmorDecay(item) / 100))
      : null;
  }

  let propertiesDataFunction = (armorSet) => {
    let onSetEquip = {};

    if (armorSet.EffectsOnSetEquip != null && armorSet.EffectsOnSetEquip.length > 0) {
      Object.entries(groupBy(armorSet.EffectsOnSetEquip, x => x.Values.MinSetPieces))
        .sort(([a],[b]) => Number(a) - Number(b))
        .forEach(([key, effects]) => onSetEquip[key + ' Pieces'] = { Value: effects.map(effect => `${effect.Values.Strength}${effect.Values.Unit ?? '<Unit>'} ${effect.Name}`) });
    }

    return {
      General: {
        Weight: armorSet.Properties?.Weight != null ? `${clampDecimals(armorSet.Properties?.Weight, 1, 6)}kg` : 'N/A',
      },
      Economy: {
        MaxTT: {
          Label: 'Max. TT',
          Value: armorSet.Properties?.Economy?.MaxTT != null ? `${clampDecimals(armorSet.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        },
        MinTT: {
          Label: 'Min. TT',
          Value: armorSet.Properties?.Economy?.MinTT != null ? `${clampDecimals(armorSet.Properties?.Economy?.MinTT, 2, 8)} PED` : 'N/A',
        },
        MaxDecay: {
          Label: 'Maximum Decay',
          Tooltip: 'The maximum amount of decay the armor can take at once, if it uses its full protection.',
          Value: getMaxArmorDecay(armorSet) != null ? `${getMaxArmorDecay(armorSet).toFixed(4)} PEC` : 'N/A',
        },
        Durability: armorSet.Properties?.Economy?.Durability ?? 'N/A',
      },
      Defense: {
        Impact: `${armorSet.Properties?.Defense?.Impact?.toFixed(1) ?? 'N/A'}`,
        Cut: `${armorSet.Properties?.Defense?.Cut?.toFixed(1) ?? 'N/A'}`,
        Stab: `${armorSet.Properties?.Defense?.Stab?.toFixed(1) ?? 'N/A'}`,
        Penetration: `${armorSet.Properties?.Defense?.Penetration?.toFixed(1) ?? 'N/A'}`,
        Shrapnel: `${armorSet.Properties?.Defense?.Shrapnel?.toFixed(1) ?? 'N/A'}`,
        Burn: `${armorSet.Properties?.Defense?.Burn?.toFixed(1) ?? 'N/A'}`,
        Cold: `${armorSet.Properties?.Defense?.Cold?.toFixed(1) ?? 'N/A'}`,
        Acid: `${armorSet.Properties?.Defense?.Acid?.toFixed(1) ?? 'N/A'}`,
        Electric: `${armorSet.Properties?.Defense?.Electric?.toFixed(1) ?? 'N/A'}`,
        Total: {
          Label: 'Total',
          Value: getTotalDefense(armorSet) != null ? `${getTotalDefense(armorSet).toFixed(1)}` : 'N/A',
          Bold: true,
        },
      },
      "Set Effects": armorSet.EffectsOnSetEquip?.length > 0 ? onSetEquip : null,
      Misc: {
        TotalAbsorption: {
          Label: 'Total Absorption',
          Tooltip: 'The total amount of damage the plate can absorb before it breaks. This number does not take block into account.',
          Value: getTotalAbsorption(armorSet) != null ? `${getTotalAbsorption(armorSet).toFixed(0)} HP` : 'N/A',
        }
      }
    };
  };

  let slots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];

  function getGenderedPiece(gender) {
    let getArmor = x => x.find(x => x.Properties.Gender === gender);
    let getSlot = x => x.length > 0 ? x[0].Properties.Slot : null;

    return {
      '_if': y => gender === 'Both'
        ? y.some(z => z.Properties.Slot === getSlot(y) && z.Properties.Gender === 'Both')
        : y.every(z => z.Properties.Slot === getSlot(y) && z.Properties.Gender !== 'Both'),
      label: gender === 'Both' ? 'Piece' : gender,
      type: 'group',
      controls: [
        { 
          label: 'Name',
          type: 'text',
          '_get': y => getArmor(y)?.Name,
          '_set': (y, v) => getArmor(y).Name = v
        },
        { label: 'Weight', type: 'number', step: '0.1', min: '0', '_get': y => getArmor(y).Properties.Weight, '_set': (y, v) => getArmor(y).Properties.Weight = v },
        { label: 'Max. TT', type: 'number', step: '0.00001', min: '0', '_get': y => getArmor(y).Properties.Economy.MaxTT, '_set': (y, v) => getArmor(y).Properties.Economy.MaxTT = v },
        { label: 'Min. TT', type: 'number', step: '0.00001', min: '0', '_get': y => getArmor(y).Properties.Economy.MinTT, '_set': (y, v) => getArmor(y).Properties.Economy.MinTT = v },
        { label: 'Effects', type: 'list', config: editConfigEffectsOnEquip, label: 'Effects on Equip', '_get': y => getArmor(y).EffectsOnEquip, '_set': (y, v) => getArmor(y).EffectsOnEquip = v },
      ],
      '_get': y => y.find(z => z.Properties.Gender === gender),
      '_set': (y, v) => {
        let index = y.findIndex(z => z.Properties.Gender === gender);
        y[index] = v;
      }
    }
  }

  function newArmorPiece(slot, gender) {
    return {
      Name: `${slot} Piece${gender !== 'Both' ? ` (${gender.substring(0, 1)})` : ``}`,
      Properties: {
        Slot: slot,
        Gender: gender,
        Economy: {
          MaxTT: null,
          MinTT: null,
          Durability: null
        },
      },
      EffectsOnEquip: [],
    };
  }

  function getArmorSlotConfig() {
    return {
      constructor: i => [newArmorPiece(slots[i], 'Both')],
      controls: [
        {
          label: 'Unisex',
          type: 'checkbox',
          '_get': y => y.length === 1 && y[0].Properties.Gender === 'Both',
          '_set': (y, v) => {
            let slot = y[0].Properties.Slot;
            y.length = 0;
            if (v) {
              y.push(newArmorPiece(slot, 'Both'));
            }
            else {
              y.push(newArmorPiece(slot, 'Male'));
              y.push(newArmorPiece(slot, 'Female'));
            }
          }
        },
        getGenderedPiece('Both'),
        getGenderedPiece('Male'),
        getGenderedPiece('Female')
      ]
    };
  }

  const editConfig = {
    constructor: () => ({
      Name: 'New Armor Set',
      Properties: {
        Description: undefined,
        Weight: undefined,
        Economy: {
          MaxTT: undefined,
          MinTT: undefined,
          Durability: undefined,
        },
        Defense: {
          Impact: undefined,
          Cut: undefined,
          Stab: undefined,
          Penetration: undefined,
          Shrapnel: undefined,
          Burn: undefined,
          Cold: undefined,
          Acid: undefined,
          Electric: undefined,
        },
      },
      Armors: [],
      EffectsOnSetEquip: [],
      Tiers: [],
    }),
    dependencies: ['effects'],
    controls: [
      {
        label: 'General',
        type: 'group',
        controls: [
          { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v},
          { label: 'Description', type: 'textarea', '_get': x => x.Properties?.Economy?.Description, '_set': (x, v) => x.Properties.Economy.Description = v},
        ]
      },
      {
        label: 'Economy',
        type: 'group',
        controls: [
          { label: 'Durability', type: 'number', step: '1', min: '0', '_get': x => x.Properties?.Economy?.Durability, '_set': (x, v) => x.Properties.Economy.Durability = v},
        ]
      },
      {
        label: 'Defense',
        type: 'group',
        controls: [
          { label: 'Impact', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Defense?.Impact, '_set': (x, v) => x.Properties.Defense.Impact = v},
          { label: 'Cut', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Defense?.Cut, '_set': (x, v) => x.Properties.Defense.Cut = v},
          { label: 'Stab', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Defense?.Stab, '_set': (x, v) => x.Properties.Defense.Stab = v},
          { label: 'Penetration', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Defense?.Penetration, '_set': (x, v) => x.Properties.Defense.Penetration = v},
          { label: 'Shrapnel', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Defense?.Shrapnel, '_set': (x, v) => x.Properties.Defense.Shrapnel = v},
          { label: 'Burn', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Defense?.Burn, '_set': (x, v) => x.Properties.Defense.Burn = v},
          { label: 'Cold', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Defense?.Cold, '_set': (x, v) => x.Properties.Defense.Cold = v},
          { label: 'Acid', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Defense?.Acid, '_set': (x, v) => x.Properties.Defense.Acid = v},
          { label: 'Electric', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Defense?.Electric, '_set': (x, v) => x.Properties.Defense.Electric = v},
        ]
      },
      {
        label: 'Armors',
        type: 'array',
        size: 7,
        config: getArmorSlotConfig(),
        indexFunc: (x, i) => x.length > 0 && x[0].Properties.Slot === slots[i],
        itemNameFunc: (i) => slots[i],
        '_get': x => x.Armors,
        '_set': (x, v) => x.Armors = v,
      },
      { label: 'Set Effects', type: 'list', config: editConfigEffectsOnSetEquip, label: 'Set Effects on Equip', '_get': x => x.EffectsOnSetEquip, '_set': (x, v) => x.EffectsOnSetEquip = v},
      { '_if': x => !hasItemTag(x.Name, 'L'), label: 'Tiering', type: 'array', size: 10, config: getEditConfigTier('ArmorSet'), indexFunc: (x, i) => x?.Properties?.Tier === i + 1, itemNameFunc: (i) => `Tier ${i + 1}`, '_get': x => x.Tiers ?? [], '_set': (x, v) => x.Tiers = v},
    ]
  };

  let tableViewInfo = {
    columns: ['Name', 'Weight', 'Max. TT', 'Durability', 'Total Absorption', 'Imp', 'Cut', 'Stab', 'Pen', 'Shrap', 'Burn', 'Cold', 'Acid', 'Elec', 'Total'],
    columnWidths: ['1fr', '80px', '100px', '90px', '130px', '70px', '70px', '70px', '70px', '70px', '70px', '70px', '70px', '70px', '70px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Properties?.Weight != null ? `${item.Properties?.Weight.toFixed(1)}kg` : 'N/A',
        item.Properties?.Economy?.MaxTT != null ? `${item.Properties?.Economy?.MaxTT.toFixed(2)} PED` : 'N/A',
        item.Properties?.Economy?.Durability ?? 'N/A',
        getTotalAbsorption(item) != null ? `${getTotalAbsorption(item).toFixed(0)} HP` : 'N/A',
        item.Properties?.Defense?.Impact?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Cut?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Stab?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Penetration?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Shrapnel?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Burn?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Cold?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Acid?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Electric?.toFixed(1) ?? 'N/A',
        getTotalDefense(item) != null ? `${getTotalDefense(item).toFixed(1)}` : 'N/A',
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
  title='Armor Sets'
  type='ArmorSet'
  basePath='/items/armorsets-legacy'
  let:object
  let:additional>
  <!-- Set Pieces -->
  <div class="flex-item long-content">
    <ArmorSetPieces armorSet={object} />
  </div>
  {#if !hasItemTag(object.Name, 'L')}
  <!-- Tiering -->
  <div class="flex-item long-content">
    <Tiering tieringInfo={additional.tierInfo} setPieceCount={object?.Armors?.flat().filter(x => x?.Properties?.Gender === 'Both' || x?.Properties?.Gender === 'Male').length ?? 0} />
  </div>
  {/if}
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>