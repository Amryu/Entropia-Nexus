<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { clampDecimals } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";

  export let data;

  const navButtonInfo = [
    {
      Label: 'Wp',
      Title: 'Weapon Amplifiers',
      Type: 'weaponamplifiers',
    },
    {
      Label: 'S/S',
      Title: 'Sights/Scopes',
      Type: 'weaponvisionattachments',
    },
    {
      Label: 'Abs',
      Title: 'Deterioation Absorbers',
      Type: 'absorbers',
    },
    {
      Label: 'Fnd',
      Title: 'Finder Amplifiers',
      Type: 'finderamplifiers',
    },
    {
      Label: 'Plt',
      Title: 'Armor Platings',
      Type: 'armorplatings',
    },
    {
      Label: 'Enh',
      Title: 'Enhancers',
      Type: 'enhancers',
    },
    {
      Label: 'Imp',
      Title: 'Mindforce Implants',
      Type: 'mindforceimplants',
    }
  ]

  function getTypeLabel(type) {
    switch (type) {
      case 'weaponamplifiers':
        return 'Weapon Amplifier';
      case 'weaponvisionattachment':
        return 'Sight/Scope';
      case 'absorbers':
        return 'Deterioation Absorber';
      case 'finderamplifiers':
        return 'Finder Amplifier';
      case 'armorplatings':
        return 'Armor Plates';
      case 'enhancers':
        return 'Enhancer';
      case 'mindforceimplants':
        return 'Mindforce Implant';
      default:
        return 'Other';
    }
  }

  function getCost(item, type) {
    return item.Properties?.Economy.Decay != null && (item.Properties?.Economy.AmmoBurn != null || type !== 'weaponamplifiers')
      ? (item.Properties?.Economy.Decay + (item.Properties?.Economy.AmmoBurn ?? 0) / 100)
      : null;
  }

  function getTotalUses(item) {
    return item.Properties?.Economy.MaxTT != null && item.Properties?.Economy.Decay != null
      ? Math.floor(((item.Properties?.Economy.MaxTT ?? null) - (item.Properties?.Economy.MinTT ?? 0)) / (item.Properties?.Economy.Decay / 100))
      : null;
  }

  function getTotalDamage(item) {
    return (item.Properties?.Damage?.Impact ?? 0) + (item.Properties?.Damage?.Cut ?? 0) + (item.Properties?.Damage?.Stab ?? 0) + (item.Properties?.Damage?.Penetration ?? 0) + (item.Properties?.Damage?.Shrapnel ?? 0) + (item.Properties?.Damage?.Burn ?? 0) + (item.Properties?.Damage?.Cold ?? 0) + (item.Properties?.Damage?.Acid ?? 0) + (item.Properties?.Damage?.Electric ?? 0);
  }

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

  function getEnhancerEffect(item) {
    switch (`${item.Properties?.Tool} ${item.Properties?.Type}`) {
      case 'Weapon Damage':
        return 'Increases damage, decay and ammo burn by 10%';
      case 'Weapon Range':
        return 'Increases range by 5%';
      case 'Weapon Skill Modification':
        return 'Increases your profession levels for the weapon by 0.5';
      case 'Weapon Economy':
        return 'Reduces the decay and ammo burn by approximately 1-1.1%';
      case 'Weapon Accuracy':
        return 'Increases the chance for a critical hit by 0.2% (at max skill)';
      case 'Armor Defense':
        return 'Increases all protection by 5%';
      case 'Armor Durability':
        return 'Increases durability by 10%';
      case 'Medical Tool Economy':
        return 'Reduces the decay by 10%';
      case 'Medical Tool Heal':
        return 'Increases the decay and the amount healed by 5%';
      case 'Medical Tool Skill Modification':
        return 'Increases your profession levels for the tool by 0.5';
      case 'Mining Excavator Speed':
        return 'Increases the efficiency by 10%';
      case 'Mining Finder Depth':
        return 'Increases the average depth by approximately 7.5%';
      case 'Mining Finder Range':
        return 'Increases the range by 1%';
      case 'Mining Finder Skill Modification':
        return 'Increases your profession levels for the finder by 0.5';
      default:
        return null;
    }
  }

  let propertiesDataFunction = (object, additional) => { 
    let type = getTypeLabel(additional.type);
    let cost = getCost(object, type);
    let totalUses = getTotalUses(object);
    let totalDamage =  getTotalDamage(object);
    let totalDefense = getTotalDefense(object);
    let maxArmorDecay = getMaxArmorDecay(object);
    let totalAbsorption = getTotalAbsorption(object);
    let enhancerEffect = getEnhancerEffect(object);

    return {
      General: {
        AttachmentType: {
          Label: 'Attachment Type',
          Value: type,
        },
        AmplifierType: additional.type === 'weaponamplifiers' ? {
          Label: 'Amplifier Type',
          Value: object.Properties?.Type ?? 'N/A',
        } : null,
        Weight: object.Properties?.Weight != null ? `${clampDecimals(object.Properties?.Weight, 1, 6)}kg` : 'N/A',
        Zoom: additional.type === 'weaponvisionattachments' ? {
          Label: 'Zoom',
          Value: object.Properties?.Zoom != null ? `${object.Properties?.Zoom.toFixed(1)}x` : 'N/A',
        } : null,
        Tool: additional.type === 'enhancers' ? object.Properties?.Tool ?? 'N/A' : null,
        EnhancerType: additional.type === 'enhancers' ? {
          Label: 'Enhancer Type',
          Value: object.Properties?.Type ?? 'N/A',
        } : null,
        Socket: additional.type === 'enhancers' ? {
          Label: 'Socket #',
          Value: object.Properties?.Socket ?? 'N/A',
        } : null,
        ProfessionLevel: additional.type === 'mindforceimplants' ? {
          Label: 'Max. Profession Level',
          Value: object.Properties?.MaxProfessionLevel ?? 'N/A',
        } : null,
      },
      Economy: {
        MaxTT: {
          Label: 'Max. TT',
          Value: object.Properties?.Economy.MaxTT != null ? `${clampDecimals(object.Properties?.Economy.MaxTT, 2, 8) ?? 'N/A'} PED` : 'N/A',
        },
        MinTT: additional.type !== 'enhancers' ? {
          Label: 'Min. TT',
          Value: object.Properties?.Economy.MinTT != null ? `${clampDecimals(object.Properties?.Economy.MinTT, 2, 8) ?? 'N/A'} PED` : 'N/A',
        } : null,
        Absorption: additional.type === 'absorbers' || additional.type === 'mindforceimplants' ? {
          Label: 'Absorption',
          Tooltip: 'The percentage of decay this item will in place of it\'s tool.',
          Value: object.Properties?.Economy.Absorption != null ? `${clampDecimals(object.Properties?.Economy.Absorption * 100, 0, 2) ?? 'N/A'} %` : 'N/A',
        } : null,
        Decay: additional.type === 'weaponamplifiers' || additional.type === 'weaponvisionattachments' || additional.type === 'finderamplifiers'
          ? object.Properties?.Economy.Decay != null ? `${object.Properties?.Economy.Decay.toFixed(4) ?? 'N/A'} PEC` : 'N/A'
          : null,
        MiningEfficiency: additional.type === 'finderamplifiers' ? {
          Label: 'Efficiency',
          Tooltip: 'The efficiency of the finder amplifier. This is just an indirect measure of how much decay is lost per probe drop.',
          Value: object.Properties?.Economy.Efficiency != null ? `${object.Properties?.Economy.Efficiency.toFixed(1)}` : 'N/A',
        } : null,
        MaxDecay: additional.type === 'armorplatings' ? {
          Label: 'Maximum Decay',
          Tooltip: 'The maximum amount of decay the armor can take at once, if it uses its full protection.',
          Value: maxArmorDecay != null ? `${maxArmorDecay.toFixed(4)} PEC` : 'N/A',
        } : null,
        Durability: additional.type === 'armorplatings' ? {
          Label: 'Durability',
          Value: `${object.Properties?.Economy.Durability ?? 'N/A'}`,
        } : null,
        AmmoBurn: additional.type === 'weaponamplifiers' ? {
          Label: 'Ammo Burn',
          Value: `${object.Properties?.Economy?.AmmoBurn ?? 'N/A'}`,
        } : null,
        Cost: additional.type === 'weaponamplifiers' ? `${cost?.toFixed(4) ?? 'N/A'} PEC` : null,
      },
      Damage: additional.type === 'weaponamplifiers' ? {
        Impact: object.Properties?.Damage?.Impact > 0 ? `${object.Properties?.Damage?.Impact?.toFixed(1)}` : null,
        Cut: object.Properties?.Damage?.Cut > 0 ? `${object.Properties?.Damage?.Cut?.toFixed(1)}` : null,
        Stab: object.Properties?.Damage?.Stab > 0 ? `${object.Properties?.Damage?.Stab?.toFixed(1)}` : null,
        Penetration: object.Properties?.Damage?.Penetration > 0 ? `${object.Properties?.Damage?.Penetration?.toFixed(1)}` : null,
        Shrapnel: object.Properties?.Damage?.Shrapnel > 0 ? `${object.Properties?.Damage?.Shrapnel?.toFixed(1)}` : null,
        Burn: object.Properties?.Damage?.Burn > 0 ? `${object.Properties?.Damage?.Burn?.toFixed(1)}` : null,
        Cold: object.Properties?.Damage?.Cold > 0 ? `${object.Properties?.Damage?.Cold?.toFixed(1)}` : null,
        Acid: object.Properties?.Damage?.Acid > 0 ? `${object.Properties?.Damage?.Acid?.toFixed(1)}` : null,
        Electric: object.Properties?.Damage?.Electric > 0 ? `${object.Properties?.Damage?.Electric?.toFixed(1)}` : null,
        Total: {
          Label: 'Total',
          Value: totalDamage != null ? `${(totalDamage).toFixed(1)}` : 'N/A',
          Bold: true,
        },
      } : null,
      Defense: additional.type === 'armorplatings' ? {
        Block: object.Properties?.Defense?.Block > 0 ? `${object.Properties?.Defense?.Block?.toFixed(1)}%` : null,
        Impact: object.Properties?.Defense?.Impact > 0 ? `${object.Properties?.Defense?.Impact?.toFixed(1)}` : null,
        Cut: object.Properties?.Defense?.Cut > 0 ? `${object.Properties?.Defense?.Cut?.toFixed(1)}` : null,
        Stab: object.Properties?.Defense?.Stab > 0 ? `${object.Properties?.Defense?.Stab?.toFixed(1)}` : null,
        Penetration: object.Properties?.Defense?.Penetration > 0 ? `${object.Properties?.Defense?.Penetration?.toFixed(1)}` : null,
        Shrapnel: object.Properties?.Defense?.Shrapnel > 0 ? `${object.Properties?.Defense?.Shrapnel?.toFixed(1)}` : null,
        Burn: object.Properties?.Defense?.Burn > 0 ? `${object.Properties?.Defense?.Burn?.toFixed(1)}` : null,
        Cold: object.Properties?.Defense?.Cold > 0 ? `${object.Properties?.Defense?.Cold?.toFixed(1)}` : null,
        Acid: object.Properties?.Defense?.Acid > 0 ? `${object.Properties?.Defense?.Acid?.toFixed(1)}` : null,
        Electric: object.Properties?.Defense?.Electric > 0 ? `${object.Properties?.Defense?.Electric?.toFixed(1)}` : null,
        Total: {
          Label: 'Total',
          Value: totalDefense != null ? `${(totalDefense).toFixed(1)}` : 'N/A',
          Bold: true,
        },
      } : null,
      Skill: additional.type === 'weaponvisionattachments' || additional.type === 'finderamplifiers' ? {
        SkillModification: additional.type === 'weaponvisionattachments' ? {
          Label: 'Skill Modification Factor',
          Tooltip: 'This stat will grant a bonus on your Hit skill for hit calculation purposes. Its effectiveness linearly scales with distance to the target, gaining maximum benefit at maximum range.',
          Value: object.Properties?.SkillModification != null ? `${object.Properties?.SkillModification}%` : 'N/A',
        } : null,
        SkillBonus: additional.type === 'weaponvisionattachments' ? {
          Label: 'Skill Bonus',
          Tooltip: 'Increases the amount of skill points gained.',
          Value: object.Properties?.SkillBonus != null ? `${object.Properties?.SkillBonus.toFixed(1)}%` : 'N/A',
        } : null,
        ProfessionsMining: additional.type === 'finderamplifiers' ? {
          Label: 'Professions',
          Value: [
            ...(additional.type === 'finders' ? ['Prospector', 'Surveyor', 'Treasure Hunter'] : ['Driller', 'Miner', 'Archaelogist']),
            `${object.Properties?.Skill?.LearningIntervalStart?.toFixed(1) ?? 'N/A'} - ${object.Properties?.Skill?.LearningIntervalEnd?.toFixed(1) ?? 'N/A'}`],
        } : null,
      } : null,
      Misc: additional.type !== 'absorbers' && additional.type !== 'mindforceimplants' ? {
        TotalUses: {
          Label: 'Total Uses',
          Value: additional.type === 'weaponamplifiers' || additional.type === 'weaponvisionattachments' || additional.type === 'finderamplifiers'
            ? totalUses ?? 'N/A'
            : null,
        },
        TotalAbsorption: additional.type === 'armorplatings'  ? {
          Label: 'Total Absorption',
          Tooltip: 'The total amount of damage the plate can absorb before it breaks. This number does not take block into account.',
          Value: totalAbsorption != null ? `${totalAbsorption.toFixed(1)} HP` : 'N/A',
        } : null,
        Effect: additional.type === 'enhancers' ? {
          Value: enhancerEffect,
        } : null,
      } : null,
    };
  };

  let tableViewInfo = {
    all: {
      columns: ['Name', 'Type', 'Weight', 'Max. TT'],
      columnWidths: ['1fr', '150px', '100px', '100px'],
      rowValuesFunction: (item) => [
        item.Name,
        getTypeLabel(item._type),
        item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
        item.Properties?.Economy.MaxTT != null ? `${item.Properties?.Economy.MaxTT.toFixed(2)} PED` : 'N/A',
      ],
    },
    weaponamplifiers: {
      columns: ['Name', 'Type', 'Weight', 'Max. TT', 'Decay', 'Ammo Burn', 'Cost', 'Damage', 'Total Uses'],
      columnWidths: ['1fr', '80px', '80px', '100px', '100px', '100px', '100px', '90px', '100px'],
      rowValuesFunction: (item) => [
        item.Name,
        item.Properties?.Type ?? 'N/A',
        item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
        item.Properties?.Economy.MaxTT != null ? `${item.Properties?.Economy.MaxTT.toFixed(2)} PED` : 'N/A',
        item.Properties?.Economy.Decay != null ? `${item.Properties?.Economy.Decay.toFixed(4)} PEC` : 'N/A',
        item.Properties?.Economy.AmmoBurn != null ? `${item.Properties?.Economy.AmmoBurn}` : 'N/A',
        getCost(item, 'Weapon Amplifier') != null ? `${getCost(item, 'Weapon Amplifier').toFixed(4)} PEC` : 'N/A',
        getTotalDamage(item) != null ? `${getTotalDamage(item).toFixed(1)}` : 'N/A',
        getTotalUses(item) != null ? `${getTotalUses(item)}` : 'N/A',
      ],
    },
    weaponvisionattachments: {
      columns: ['Name', 'Type', 'Weight', 'Max. TT', 'Decay', 'Zoom', 'Skill Modification', 'Skill Bonus'],
      columnWidths: ['1fr', '80px', '80px', '100px', '100px', '80px', '130px', '100px'],
      rowValuesFunction: (item) => [
        item.Name,
        item.Properties?.Type ?? 'N/A',
        item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
        item.Properties?.Economy.MaxTT != null ? `${item.Properties?.Economy.MaxTT.toFixed(2)} PED` : 'N/A',
        item.Properties?.Economy.Decay != null ? `${item.Properties?.Economy.Decay.toFixed(4)} PEC` : 'N/A',
        item.Properties?.Zoom != null ? `${item.Properties?.Zoom.toFixed(1)}x` : 'N/A',
        item.Properties?.SkillModification != null ? `${item.Properties?.SkillModification}%` : 'N/A',
        item.Properties?.SkillBonus != null ? `${item.Properties?.SkillBonus.toFixed(1)}%` : 'N/A',
      ],
    },
    absorbers: {
      columns: ['Name', 'Type', 'Weight', 'Max. TT', 'Absorption'],
      columnWidths: ['1fr', '80px', '80px', '100px', '100px'],
      rowValuesFunction: (item) => [
        item.Name,
        item.Properties?.Type ?? 'N/A',
        item.Properties?.Weight != null ? `${item.Properties?.Weight.toFixed(1)}kg` : 'N/A',
        item.Properties?.Economy.MaxTT != null ? `${item.Properties?.Economy.MaxTT.toFixed(2)} PED` : 'N/A',
        item.Properties?.Economy.Absorption != null ? `${clampDecimals(object.Properties?.Economy.Absorption * 100, 0, 2)}%` : 'N/A',
      ],
    },
    finderamplifiers: {
      columns: ['Name', 'Weight', 'Max. TT', 'Decay', 'Total Uses', 'Min. Prof.'],
      columnWidths: ['1fr', '80px', '100px', '100px', '100px', '100px'],
      rowValuesFunction: (item) => [
        item.Name,
        item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
        item.Properties?.Economy.MaxTT != null ? `${item.Properties?.Economy.MaxTT.toFixed(2)} PED` : 'N/A',
        item.Properties?.Economy.Decay != null ? `${item.Properties?.Economy.Decay.toFixed(4)} PEC` : 'N/A',
        getTotalUses(item) != null ? `${getTotalUses(item)}` : 'N/A',
        item.Properties?.Skill?.LearningIntervalStart != null ? item.Properties?.Skill?.LearningIntervalStart.toFixed(1) : 'N/A',
      ],
    },
    armorplatings: {
      columns: ['Name', 'Weight', 'Max. TT', 'Durability', 'Total Absorption', 'Imp', 'Cut', 'Stab', 'Pen', 'Shrap', 'Burn', 'Cold', 'Acid', 'Elec', 'Total'],
      columnWidths: ['1fr', '80px', '100px', '90px', '130px', '70px', '70px', '70px', '70px', '70px', '70px', '70px', '70px', '70px', '70px'],
      rowValuesFunction: (item) => [
        item.Name,
        item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
        item.Properties?.Economy.MaxTT != null ? `${item.Properties?.Economy.MaxTT.toFixed(2)} PED` : 'N/A',
        item.Properties?.Economy.Durability ?? 'N/A',
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
      ],
    },
    enhancers: {
      columns: ['Name', 'Weight', 'Max. TT', 'Tool', 'Type', 'Socket #'],
      columnWidths: ['1fr', '80px', '100px', '130px', '130px', '100px'],
      rowValuesFunction: (item) => [
        item.Name,
        item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
        item.Properties?.Economy.MaxTT != null ? `${item.Properties?.Economy.MaxTT.toFixed(2)} PED` : 'N/A',
        item.Properties?.Tool ?? 'N/A',
        item.Properties?.Type ?? 'N/A',
        item.Properties?.Socket ?? 'N/A',
      ],
    },
    mindforceimplants: {
      columns: ['Name', 'Weight', 'Max. TT', 'Absorption', 'Max. Prof. Level'],
      columnWidths: ['1fr', '80px', '100px', '100px', '130px'],
      rowValuesFunction: (item) => [
        item.Name,
        item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
        item.Properties?.Economy.MaxTT != null ? `${item.Properties?.Economy.MaxTT.toFixed(2)} PED` : 'N/A',
        item.Properties?.Economy.Absorption != null ? `${clampDecimals(object.Properties?.Economy.Absorption * 100, 0, 2)}%` : 'N/A',
        item.Properties?.MaxProfessionLevel ?? 'N/A',
      ],
    },
  };
</script>

<EntityViewer
  data={data}
  tableViewInfo={tableViewInfo}
  navButtonInfo={navButtonInfo}
  propertiesDataFunction={propertiesDataFunction}
  title='Attachments'
  basePath='/items/attachments'
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