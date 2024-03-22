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
      Label: 'Rgd',
      Title: 'Ranged',
      Type: 'ranged',
    },
    {
      Label: 'Mle',
      Title: 'Melee',
      Type: 'melee',
    },
    {
      Label: 'Mdf',
      Title: 'Mindforce',
      Type: 'mindforce',
    },
    {
      Label: 'Att',
      Title: 'Attached',
      Type: 'attached',
    }
  ]

  function getTotalDamage(item) {
    return (item.Properties?.Damage?.Impact
      + item.Properties?.Damage?.Cut
      + item.Properties?.Damage?.Stab
      + item.Properties?.Damage?.Penetration
      + item.Properties?.Damage?.Shrapnel
      + item.Properties?.Damage?.Burn
      + item.Properties?.Damage?.Cold
      + item.Properties?.Damage?.Acid
      + item.Properties?.Damage?.Electric) || null;
  }

  function getEffectiveDamage(item) {
    const totalDamage = getTotalDamage(item);

    return totalDamage != null
      ? totalDamage * (0.88*0.75 + 0.02*1.75)
      : null;
  }

  function getDps(item) {
    const reload = getReload(item);
    const effectiveDamage = getEffectiveDamage(item);

    return effectiveDamage != null && reload != null
      ? effectiveDamage / reload
      : null;
  }

  function getDpp(item) {
    const cost = getCost(item);
    const effectiveDamage = getEffectiveDamage(item);

    return effectiveDamage > 0 && cost != null
      ? effectiveDamage / cost
      : null;
  }

  function getCost(item) {
    return item.Properties?.Economy?.Decay != null && item.Properties?.Economy?.AmmoBurn >= 0
      ? (item.Properties?.Economy?.Decay + (item.Properties?.Economy?.AmmoBurn ?? 0) / 100)
      : null;
  }

  function getReload(item) {
    return item.Properties?.UsesPerMinute != null
      ? 60 / item.Properties?.UsesPerMinute
      : null;
  }

  function getTotalUses(item) {
    let maxTT = item.Properties?.Economy?.MaxTT ?? null;
    let minTT = item.Properties?.Economy?.MinTT ?? 0;
    let decay = item.Properties?.Economy?.Decay ?? null;

    return maxTT != null && decay != null
      ? Math.floor((maxTT - minTT) / (decay / 100))
      : null;
  }

  let propertiesDataFunction = (weapon, additional) => {
    let cost = getCost(weapon);
    let totalDamage = getTotalDamage(weapon);
    let effectiveDamage = getEffectiveDamage(weapon);
    let reload = getReload(weapon);

    let totalUses = getTotalUses(weapon);
    let cyclePerRepair = totalUses * (cost / 100);
    let cyclePerHour = (3600 / reload) * (cost / 100);

    return {
      General: {
        Weight: weapon.Properties?.Weight != null ? `${clampDecimals(weapon.Properties?.Weight, 1, 6)}kg` : 'N/A',
        Class: weapon.Properties?.Class ?? 'N/A',
        Category: weapon.Properties?.Category ?? 'N/A',
        Type: weapon.Properties?.Type ?? 'N/A',
        Range: weapon.Properties?.Range != null ? `${weapon.Properties?.Range}m` : 'N/A',
        Reload: reload != null ? `${reload.toFixed(2)}s` : 'N/A',
      },
      Economy: {
        Efficiency: {
          Label: 'Efficiency',
          Value: weapon.Properties?.Economy?.Efficiency != null ? `${weapon.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
          Bold: true
        },
        DPP: {
          Label: 'DPP',
          Tooltip: 'Damage per PEC',
          Value: cost !== null && effectiveDamage != null ? (effectiveDamage / cost).toFixed(4) : 'N/A',
          Bold: true
        },
        MaxTT: {
          Label: 'Max. TT',
          Value: weapon.Properties?.Economy.MaxTT != null ? `${clampDecimals(weapon.Properties?.Economy.MaxTT, 2, 8)} PED` : 'N/A',
        },
        MinTT: {
          Label: 'Min. TT',
          Value: weapon.Properties?.Economy.MinTT != null ? `${clampDecimals(weapon.Properties?.Economy.MinTT, 2, 8)} PED` : 'N/A',
        },
        Decay: weapon.Properties?.Economy.Decay != null ? `${weapon.Properties?.Economy.Decay.toFixed(4)} PEC` : 'N/A',
        Ammo: {
          Label: 'Ammo',
          Value: `${weapon.Ammo?.Name ?? 'N/A'}`,
        },
        AmmoBurn: {
          Label: 'Ammo Burn',
          Value: `${weapon.Properties?.Economy.AmmoBurn ?? 'N/A'}`,
        },
        Cost: cost != null ? `${cost.toFixed(4)} PEC` : 'N/A',
      },
      Damage: {
        DPS: {
          Label: 'DPS',
          Tooltip: 'Damage per second',
          Value: effectiveDamage != null && reload != null ? (effectiveDamage / reload).toFixed(4) : 'N/A',
          Bold: true
        },
        Impact: weapon.Properties?.Damage?.Impact > 0 ? `${weapon.Properties?.Damage?.Impact?.toFixed(1) ?? 'N/A'}` : null,
        Cut: weapon.Properties?.Damage?.Cut > 0 ? `${weapon.Properties?.Damage?.Cut?.toFixed(1) ?? 'N/A'}` : null,
        Stab: weapon.Properties?.Damage?.Stab > 0 ? `${weapon.Properties?.Damage?.Stab?.toFixed(1) ?? 'N/A'}` : null,
        Penetration: weapon.Properties?.Damage?.Penetration > 0 ? `${weapon.Properties?.Damage?.Penetration?.toFixed(1) ?? 'N/A'}` : null,
        Shrapnel: weapon.Properties?.Damage?.Shrapnel > 0 ? `${weapon.Properties?.Damage?.Shrapnel?.toFixed(1) ?? 'N/A'}` : null,
        Burn: weapon.Properties?.Damage?.Burn > 0 ? `${weapon.Properties?.Damage?.Burn?.toFixed(1) ?? 'N/A'}` : null,
        Cold: weapon.Properties?.Damage?.Cold > 0 ? `${weapon.Properties?.Damage?.Cold?.toFixed(1) ?? 'N/A'}` : null,
        Acid: weapon.Properties?.Damage?.Acid > 0 ? `${weapon.Properties?.Damage?.Acid?.toFixed(1) ?? 'N/A'}` : null,
        Electric: weapon.Properties?.Damage?.Electric > 0 ? `${weapon.Properties?.Damage?.Electric?.toFixed(1) ?? 'N/A'}` : null,
        Total: {
          Label: 'Total',
          Value: totalDamage != null ? `${(totalDamage).toFixed(1)}` : 'N/A',
          Bold: true,
        },
      },
      Mindforce: weapon.Properties?.Class ? {
        Level: weapon.Properties?.Mindforce?.Level ?? 'N/A',
        Concentration: weapon.Properties?.Mindforce?.Concentration ? `${weapon.Properties?.Mindforce?.Concentration}s` : 'N/A',
        Cooldown: weapon.Properties?.Mindforce?.Cooldown ? `${weapon.Properties?.Mindforce?.Cooldown}s` : 'N/A',
        CooldownGroup: {
          Label: 'Cooldown Group',
          Value: weapon.Properties?.Mindforce?.CooldownGroup ?? 'N/A',
        }
      } : null,
      Skill: {
        SiB: {
          Label: 'SiB',
          Tooltip: 'Skill Increase Bonus',
          Value: weapon.Properties?.Skill.IsSiB ? 'Yes' : 'No',
        },
        ProfessionHit: {
          Label: 'Prof. (Hit)',
          Tooltip: 'Profession (Hit)',
          Value: [weapon.ProfessionHit?.Name ?? 'N/A', `${weapon.Properties?.Skill.Hit.LearningIntervalStart ?? 'N/A'} - ${weapon.Properties?.Skill.Hit.LearningIntervalEnd ?? 'N/A'}`],
        },
        ProfessionDmg: {
          Label: 'Prof. (Dmg)',
          Tooltip: 'Profession (Dmg)',
          Value: [weapon.ProfessionDmg?.Name ?? 'N/A', `${weapon.Properties?.Skill.Dmg.LearningIntervalStart ?? 'N/A'} - ${weapon.Properties?.Skill.Dmg.LearningIntervalEnd ?? 'N/A'}`],
        },
      },
      Misc: {
        TotalUses: {
          Label: 'Total Uses',
          Value: totalUses ?? 'N/A',
        },
        CyclePerRepair: {
          Label: 'PED/repair',
          Tooltip: 'PED cycled per full repair',
          Value: cyclePerRepair != null ? `${cyclePerRepair.toFixed(2)} PED` : 'N/A',
        },
        CyclePerHour: {
          Label: 'PED/h',
          Tooltip: 'PED cycled per hour (theoretical maximum)',
          Value: cyclePerHour != null ? `${cyclePerHour.toFixed(2)} PED` : 'N/A',
        },
        TimeToBreak: {
          Label: 'Time to break',
          Tooltip: 'Time until the tool is broken from full condition',
          Value: cyclePerHour > 0 ? `${(cyclePerRepair / cyclePerHour).toFixed(2)}h` : 'N/A',
        },
      }
    };
  };

  let viewInfoSection = {
    columns: ['Name', 'Category', 'Type', 'DPS', 'Damage', 'Range', 'Reload', 'Efficiency', 'DPP', 'Max. TT', 'Cost', 'SiB', 'Min', 'Max'],
    columnWidths: ['1fr', '105px', '85px', '70px', '80px', '65px', '70px', '85px', '70px', '100px', '95px', '50px', '50px', '50px'],
    rowValuesFunction: (item) => [
      item.Name,
      item.Properties?.Category ?? 'N/A',
      item.Properties?.Type ?? 'N/A',
      getDps(item) != null ? getDps(item).toFixed(2) : 'N/A',
      getTotalDamage(item) != null ? Math.round(getTotalDamage(item)) : 'N/A',
      item.Properties?.Range != null ? `${item.Properties?.Range}m` : 'N/A',
      getReload(item) != null ? `${getReload(item).toFixed(2)}s` : 'N/A',
      item.Properties?.Economy?.Efficiency != null ? `${item.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
      getDpp(item) != null ? getDpp(item).toFixed(4) : 'N/A',
      item.Properties?.Economy?.MaxTT != null ? `${item.Properties?.Economy?.MaxTT.toFixed(2)} PED` : 'N/A',
      getCost(item) != null ? `${getCost(item).toFixed(4)} PEC` : 'N/A',
      item.Properties?.Skill.IsSiB ? 'Yes' : 'No',
      item.Properties?.Skill?.Hit?.LearningIntervalStart ?? 'N/A',
      item.Properties?.Skill?.Hit?.LearningIntervalEnd ?? 'N/A',
    ]
  };

  let tableViewInfo = {
    all: viewInfoSection,
    ranged: viewInfoSection,
    melee: viewInfoSection,
    mindforce: viewInfoSection,
    attached: viewInfoSection,
  };
</script>

<EntityViewer
  data={data}
  tableViewInfo={tableViewInfo}
  navButtonInfo={navButtonInfo}
  propertiesDataFunction={propertiesDataFunction}
  title='Weapons'
  basePath='/items/weapons'
  let:object
  let:additional>
  <div class="flex-item-double">
    <div class="big-title">{object.Name}</div>
  </div>
  {#if !hasItemTag(object.Name, 'L')}
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