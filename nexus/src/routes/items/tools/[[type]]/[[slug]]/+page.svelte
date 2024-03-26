<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { hasItemTag, clampDecimals } from "$lib/util";

  import EntityViewer from '$lib/components/EntityViewer.svelte';
  import Tiering from "$lib/components/Tiering.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";

  export let data;

  const navButtonInfo = [
    {
      Label: 'Rf',
      Title: 'Refiners',
      Type: 'refiners',
    },
    {
      Label: 'Scn',
      Title: 'Scanners',
      Type: 'scanners',
    },
    {
      Label: 'Fnd',
      Title: 'Finders',
      Type: 'finders',
    },
    {
      Label: 'Ecv',
      Title: 'Excavators',
      Type: 'excavators',
    },
    {
      Label: 'Tp',
      Title: 'Teleportation Chips',
      Type: 'teleportationchips',
    },
    {
      Label: 'Eff',
      Title: 'Effect Chips',
      Type: 'effectchips',
    },
    {
      Label: 'Msc',
      Title: 'Misc. Tools',
      Type: 'misctools',
    }
  ];

  function getTypeName(type) {
    switch (type) {
      case 'finders':
        return 'Finder'
      case 'excavators':
        return 'Excavator';
      case 'scanners':
        return 'Scanner';
      case 'refiners':
       return 'Refiner';
      case 'teleportationchips':
        return 'Teleportation Chip';
      case 'effectchips':
        return 'Effect Chip';
      default:
        return 'Misc. Tool';
    };
  }

  function getTotalUses(maxTT, minTT, decay) {
    return decay != null
      ? Math.floor(((maxTT ?? 0) - (minTT ?? 0)) / (decay / 100))
      : 'N/A';
  }

  function getCost(item) {
    return item.Properties?.Economy?.Decay != null && item.Properties?.Economy?.AmmoBurn != null
      ? item.Properties?.Economy?.Decay + item.Properties?.Economy?.AmmoBurn / 100
      : 'N/A';
  }
  
  let propertiesDataFunction = (object, additional) => {
    let reload = object.Properties?.UsesPerMinute ? 60 / object.Properties?.UsesPerMinute : null;

    let totalUses = getTotalUses(object.Properties?.Economy?.MaxTT, object.Properties?.Economy?.MinTT, object.Properties?.Economy?.Decay);

    let type = getTypeName(additional.type);

    let onEquip = {};

    if (object.EffectsOnEquip != null && object.EffectsOnEquip.length > 0) {
      object.EffectsOnEquip
        .sort((a,b) => a.Name.localeCompare(b.Name))
        .forEach(effect => onEquip[effect.Name] = `${effect.Values.Strength}${effect.Values.Unit}`);
    }

    return {
      General: {
        Type: type,
        Weight: object.Properties?.Weight != null ? `${clampDecimals(object.Properties?.Weight, 1, 6)}kg` : 'N/A',
        Reload: reload !== null && additional.type !== 'refiners' && additional.type !== 'misctools' ? `${reload.toFixed(2)}s` : null,
        Range: additional.type === 'scanners' || additional.type === 'effectchips' || additional.type === 'teleportationchips'
          ? `${object.Properties?.Range ?? 'N/A'}${additional.type === 'teleportationchips' ? 'km' : 'm'}`
          : null,
      },
      Economy: {
        MaxTT: {
          Label: 'Max. TT',
          Value: object.Properties?.Economy.MaxTT != null ? `${clampDecimals(object.Properties?.Economy.MaxTT, 2, 8)} PED` : 'N/A',
        },
        MinTT: {
          Label: 'Min. TT',
          Value: object.Properties?.Economy.MinTT != null ? `${clampDecimals(object.Properties?.Economy.MinTT, 2, 8)} PED` : 'N/A',
        },
        Decay: object.Properties?.Economy.Decay != null ? `${object.Properties?.Economy.Decay.toFixed(4) ?? 'N/A'} PEC` : 'N/A',
        Ammo: additional.type === 'finders'
        ? 'Survey Probe'
        : additional.type === 'teleportationchips' || additional.type === 'effectchips'
        ? object.Ammo?.Name
        : null,
        AmmoBurn: additional.type === 'finders' ? {
          Label: 'Ammo Burn',
          Value: `${object.Properties?.Economy.AmmoBurn ?? 'N/A'}/${(object.Properties?.Economy.AmmoBurn * 2) ?? 'N/A'}/${(object.Properties?.Economy.AmmoBurn * 3) ?? 'N/A'}`,
        } : additional.type === 'teleportationchips' || additional.type === 'effectchips' ?
        {
          Label: 'Ammo Burn',
          Value: object.Properties?.Economy?.AmmoBurn ?? 'N/A',
        } : null,
        Cost: additional.type === 'teleportationchips' || additional.type === 'effectchips' ? {
          Label: 'Cost',
          Value: getCost(object) !== 'N/A' ? `${getCost(object).toFixed(2)} PEC` : 'N/A',
        } : null,
      },
      Mindforce: additional.type === 'teleportationchips' || additional.type === 'effectchips' ? {
        Level: object.Properties?.Mindforce?.Level ?? 'N/A',
        Concentration: object.Properties?.Mindforce?.Concentration ? `${object.Properties?.Mindforce?.Concentration}s` : 'N/A',
        Cooldown: object.Properties?.Mindforce?.Cooldown ? `${object.Properties?.Mindforce?.Cooldown}s` : 'N/A',
        CooldownGroup: {
          Label: 'Cooldown Group',
          Value: object.Properties?.Mindforce?.CooldownGroup ?? 'N/A',
        }
      } : null,
      Mining: additional.type === 'finders' || additional.type === 'excavators' ? {
        MaxDepth: additional.type === 'finders' ? {
          Label: 'Depth',
          Value: `${object.Properties?.Depth ?? 'N/A'}m`,
        } : null,
        Range: additional.type === 'finders' ? {
          Label: 'Range',
          Value: `${object.Properties?.Range ?? 'N/A'}m`,
        } : null,
        ExcavationEfficiency: additional.type === 'excavators' ? {
          Label: 'Efficiency',
          Tooltip: 'Affects how much this extractor will gather per operation. Higher efficiency means more resources per operation.',
          Value: `${object.Properties?.Efficiency ?? 'N/A'}`,
        } : null,
        EfficencyPerPED: additional.type === 'excavators' ? {
          Label: 'Efficiency/PED',
          Tooltip: 'How much resources can be pulled up per PED. Exact amount depends on the resource.',
          Value: `${(object.Properties?.Efficiency / (object.Properties?.Economy?.Decay / 100)).toFixed(1) ?? 'N/A'}`,
        } : null,
        EfficiencyPerSecond: additional.type === 'excavators' ? {
          Label: 'Efficiency/s',
          Tooltip: 'How fast resources are gathered.',
          Value: `${(object.Properties?.Efficiency / reload).toFixed(2) ?? 'N/A'}`,
        } : null,
      } : null,
      Skill: additional.type !== 'scanners' && additional.type !== 'refiners' ? {
        SkillIncreaseBonus: {
          Label: 'SiB',
          Tooltip: 'Skill Increase Bonus',
          Value: `${object.Properties?.Skill?.IsSiB ? 'Yes' : 'No'}`,
        },
        ProfessionsMining: additional.type === 'finders' || additional.type === 'excavators' ? {
          Label: 'Professions',
          Value: [
            ...(additional.type === 'finders' ? ['Prospector', 'Surveyor', 'Treasure Hunter'] : ['Driller', 'Miner', 'Archaelogist']),
            `${object.Properties?.Skill?.LearningIntervalStart?.toFixed(1) ?? 'N/A'} - ${object.Properties?.Skill?.LearningIntervalEnd?.toFixed(1) ?? 'N/A'}`],
        } : null,
        ProfessionsMindforce: additional.type === 'teleportationchips' || additional.type === 'effectchips' ? {
          Label: 'Professions',
          Value: [
            object.Profession?.Name, 
            `${object.Properties?.Skill?.LearningIntervalStart?.toFixed(1) ?? 'N/A'} - ${object.Properties?.Skill?.LearningIntervalEnd?.toFixed(1) ?? 'N/A'}`],
        } : null,
        ProfessionMisc: additional.type === 'misctools' ?
        {
          Label: 'Profession',
          Value: object.Profession?.Name ?? 'N/A',
        } : null,
      } : null,
      "Equip Effects": object.EffectsOnEquip?.length > 0 ? onEquip : null,
      Misc: {
        TotalUses: {
          Label: 'Total Uses',
          Value: totalUses ?? 'N/A',
        },
      }
    };
  };

  let tableViewInfo = {
    all: {
      columns: ['Name', 'Type', 'Weight', 'Max. TT'],
      columnWidths: ['1fr', '100px', '80px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          getTypeName(item._type),
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        ];
      }
    },
    refiners: {
      columns: ['Name', 'Weight', 'Max. TT', 'Decay', 'Total Uses'],
      columnWidths: ['1fr', '100px', '90px', '100px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
          item.Properties?.Economy?.Decay != null ? `${item.Properties?.Economy?.Decay.toFixed(4)} PEC` : 'N/A',
          getTotalUses(item.Properties?.Economy?.MaxTT, item.Properties?.Economy?.MinTT, item.Properties?.Economy?.Decay) ?? 'N/A'
        ];
      }
    },
    scanners: {
      columns: ['Name', 'Weight', 'Reload', 'Range', 'Max. TT', 'Decay', 'Total Uses'],
      columnWidths: ['1fr', '100px', '90px', '100px', '100px', '100px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          item.Properties?.UsesPerMinute != null ? `${(60 / item.Properties?.UsesPerMinute).toFixed(2)}s` : 'N/A',
          item.Properties?.Range != null ? `${item.Properties?.Range}m` : 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
          item.Properties?.Economy?.Decay != null ? `${item.Properties?.Economy?.Decay.toFixed(4)} PEC` : 'N/A',
          getTotalUses(item.Properties?.Economy?.MaxTT, item.Properties?.Economy?.MinTT, item.Properties?.Economy?.Decay) ?? 'N/A'
        ];
      }
    },
    finders: {
      columns: ['Name', 'Weight', 'Depth', 'Range', 'Reload', 'Max. TT', 'Decay', 'Total Uses', 'SiB', 'Min', 'Max'],
      columnWidths: ['1fr', '100px', '90px', '100px', '100px', '100px', '100px', '100px', '60px', '60px', '60px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          item.Properties?.Depth != null ? `${item.Properties?.Depth}m` : 'N/A',
          item.Properties?.Range != null ? `${item.Properties?.Range}m` : 'N/A',
          item.Properties?.UsesPerMinute != null ? `${(60 / item.Properties?.UsesPerMinute).toFixed(2)}s` : 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
          item.Properties?.Economy?.Decay != null ? `${item.Properties?.Economy?.Decay.toFixed(4)} PEC` : 'N/A',
          getTotalUses(item.Properties?.Economy?.MaxTT, item.Properties?.Economy?.MinTT, item.Properties?.Economy?.Decay) ?? 'N/A',
          item.Properties?.Skill?.IsSiB ? 'Yes' : 'No',
          item.Properties?.Skill?.LearningIntervalStart?.toFixed(1) ?? 'N/A',
          item.Properties?.Skill?.LearningIntervalEnd?.toFixed(1) ?? 'N/A'
        ];
      }
    },
    excavators: {
      columns: ['Name', 'Weight', 'Efficiency', 'Efficiency/PED', 'Efficiency/s', 'Max. TT', 'Decay', 'Total Uses', 'SiB', 'Min', 'Max'],
      columnWidths: ['1fr', '80px', '95px', '130px', '110px', '100px', '100px', '100px', '60px', '60px', '60px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          item.Properties?.Efficiency != null ? `${item.Properties?.Efficiency}` : 'N/A',
          item.Properties?.Efficiency != null && item.Properties?.Economy?.Decay != null ? `${(item.Properties?.Efficiency / (item.Properties?.Economy?.Decay / 100)).toFixed(1)}` : 'N/A',
          item.Properties?.Efficiency != null && item.Properties?.UsesPerMinute != null ? `${(item.Properties?.Efficiency / (60 / item.Properties?.UsesPerMinute)).toFixed(2)}` : 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
          item.Properties?.Economy?.Decay != null ? `${item.Properties?.Economy?.Decay.toFixed(4)} PEC` : 'N/A',
          getTotalUses(item.Properties?.Economy?.MaxTT, item.Properties?.Economy?.MinTT, item.Properties?.Economy?.Decay) ?? 'N/A',
          item.Properties?.Skill?.IsSiB ? 'Yes' : 'No',
          item.Properties?.Skill?.LearningIntervalStart?.toFixed(1) ?? 'N/A',
          item.Properties?.Skill?.LearningIntervalEnd?.toFixed(1) ?? 'N/A'
        ];
      }
    },
    teleportationchips: {
      columns: ['Name', 'Weight', 'Range', 'Reload', 'Max. TT', 'Cost', 'Cost/km', 'm/s', 'Level', 'Concentration', 'Cooldown', 'Cooldown Group', 'Min', 'Max'],
      columnWidths: ['1fr', '80px', '80px', '80px', '100px', '75px', '98px', '85px', '70px', '100px', '100px', '120px', '60px', '60px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          item.Properties?.Range != null ? `${item.Properties?.Range}km` : 'N/A',
          item.Properties?.UsesPerMinute != null ? `${(60 / item.Properties?.UsesPerMinute).toFixed(2)}s` : 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
          getCost(item) !== 'N/A' ? `${getCost(item).toFixed(2)} PEC` : 'N/A',
          getCost(item) !== 'N/A' && item.Properties?.Range != null ? `${(getCost(item) / item.Properties?.Range).toFixed(2)} PEC/km` : 'N/A',
          item.Properties?.Range != null && item.Properties?.UsesPerMinute != null ? `${(item.Properties?.Range * 1000 / (60 / item.Properties?.UsesPerMinute)).toFixed(2)}m/s` : 'N/A',
          item.Properties?.Mindforce?.Level ?? 'N/A',
          item.Properties?.Mindforce?.Concentration ? `${item.Properties?.Mindforce?.Concentration}s` : 'N/A',
          item.Properties?.Mindforce?.Cooldown ? `${item.Properties?.Mindforce?.Cooldown}s` : 'N/A',
          item.Properties?.Mindforce?.CooldownGroup ?? 'N/A',
          item.Properties?.Skill?.LearningIntervalStart?.toFixed(1) ?? 'N/A',
          item.Properties?.Skill?.LearningIntervalEnd?.toFixed(1) ?? 'N/A'
        ];
      }
    },
    effectchips: {
      columns: ['Name', 'Weight', 'Range', 'Reload', 'Max. TT', 'Cost', 'Level', 'Concentration', 'Cooldown', 'Cooldown Group', 'Min', 'Max'],
      columnWidths: ['1fr', '80px', '80px', '80px', '100px', '75px', '70px', '100px', '100px', '120px', '60px', '60px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          item.Properties?.Range != null ? `${item.Properties?.Range}m` : 'N/A',
          item.Properties?.UsesPerMinute != null ? `${(60 / item.Properties?.UsesPerMinute).toFixed(2)}s` : 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
          getCost(item) !== 'N/A' ? `${getCost(item).toFixed(2)} PEC` : 'N/A',
          item.Properties?.Mindforce?.Level ?? 'N/A',
          item.Properties?.Mindforce?.Concentration ? `${item.Properties?.Mindforce?.Concentration}s` : 'N/A',
          item.Properties?.Mindforce?.Cooldown ? `${item.Properties?.Mindforce?.Cooldown}s` : 'N/A',
          item.Properties?.Mindforce?.CooldownGroup ?? 'N/A',
          item.Properties?.Skill?.LearningIntervalStart?.toFixed(1) ?? 'N/A',
          item.Properties?.Skill?.LearningIntervalEnd?.toFixed(1) ?? 'N/A'
        ];
      }
    },
    misctools: {
      columns: ['Name', 'Weight', 'Max. TT', 'Decay', 'Profession', 'Total Uses'],
      columnWidths: ['1fr', '100px', '90px', '100px', '100px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
          item.Properties?.Economy?.Decay != null ? `${item.Properties?.Economy?.Decay.toFixed(4)} PEC` : 'N/A',
          item.Profession?.Name ?? 'N/A',
          getTotalUses(item.Properties?.Economy?.MaxTT, item.Properties?.Economy?.MinTT, item.Properties?.Economy?.Decay) ?? 'N/A'
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
  title='Tools'
  basePath='/items/tools'
  let:object
  let:additional>
  <div class="flex-item-double">
    <div class="big-title">{object.Name}</div>
  </div>
  {#if object && !hasItemTag(object.Name, 'L') && ['finders', 'excavators'].includes(additional.type)}
  <!-- Tiering -->
  <div class="flex-item long-content">
    <Tiering tieringInfo={additional.tierInfo} />
  </div>
  {/if}
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>