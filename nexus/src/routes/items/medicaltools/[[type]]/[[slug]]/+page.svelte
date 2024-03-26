<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { hasItemTag, clampDecimals, getTimeString } from "$lib/util";

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Tiering from "$lib/components/Tiering.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";

  export let data;

  const navButtonInfo = [
    {
      Label: 'Tool',
      Title: 'Medical Tools',
      Type: 'tools',
    },
    {
      Label: 'Chip',
      Title: 'Medical Chips',
      Type: 'chips',
    }
  ]

  function getCost(item) {
    return item.Properties?.Economy.Decay != null
      ? (item.Properties?.Economy.Decay + (item.Properties?.Economy.AmmoBurn ?? 0) / 100)
      : null;
  }

  function getEffectiveHealing(item) {
    return item.Properties?.MaxHeal != null && item.Properties?.MinHeal != null
      ? (item.Properties?.MaxHeal + item.Properties?.MinHeal) / 2
      : null;
  }

  function getReload(item) {
    return item.Properties?.UsesPerMinute != null
      ? 60 / item.Properties?.UsesPerMinute
      : null;
  }

  function getHps(item) {
    let reload = getReload(item);
    let effectiveHealing = getEffectiveHealing(item);

    return reload != null && effectiveHealing != null
      ? effectiveHealing / reload
      : null;
  }

  function getHpp(item) {
    let cost = getCost(item);
    let effectiveHealing = getEffectiveHealing(item);

    return cost != null && effectiveHealing != null
      ? (effectiveHealing / cost).toFixed(4)
      : null;
  }

  function getTotalUses(item) {
    return item.Properties?.Economy.MaxTT != null && item.Properties?.Economy.Decay != null
      ? Math.floor(((item.Properties?.Economy.MaxTT ?? null) - (item.Properties?.Economy.MinTT ?? 0)) / (item.Properties?.Economy.Decay / 100))
      : null;
  }

  let propertiesDataFunction = (object, additional) => {
    let cost = getCost(object);
    let reload = getReload(object);
    let totalUses = getTotalUses(object);

    let cyclePerRepair = totalUses * (cost / 100);
    let cyclePerHour = (3600 / reload) * (cost / 100);

    let onEquip = {};

    if (object.EffectsOnEquip != null && object.EffectsOnEquip.length > 0) {
      object.EffectsOnEquip
        .sort((a,b) => a.Name.localeCompare(b.Name))
        .forEach(effect => onEquip[effect.Name] = `${effect.Values.Strength}${effect.Values.Unit}`);
    }

    let onUse = {};

    if (object.EffectsOnUse != null && object.EffectsOnUse.length > 0) {
      object.EffectsOnUse
        .sort((a,b) => a.Name.localeCompare(b.Name))
        .forEach(effect => onUse[effect.Name] = `${effect.Values.Strength}${effect.Values.Unit} for ${getTimeString(effect.Values.DurationSeconds)}`);
    }

    return {
      General: {
        Weight: object.Properties?.Weight != null ? `${clampDecimals(object.Properties?.Weight, 1, 6)}kg` : 'N/A',
        Reload: reload ? `${reload.toFixed(2)}s` : 'N/A',
      },
      Economy: {
        HPP: {
          Label: 'HPP',
          Tooltip: 'Heal per PEC',
          Value: getHpp(object) != null ? getHpp(object) : 'N/A',
          Bold: true
        },
        MaxTT: {
          Label: 'Max. TT',
          Value: object.Properties?.Economy.MaxTT != null ? `${clampDecimals(object.Properties?.Economy.MaxTT, 2, 8)} PED` : 'N/A',
        },
        MinTT: {
          Label: 'Min. TT',
          Value: object.Properties?.Economy.MinTT != null ? `${clampDecimals(object.Properties?.Economy.MinTT, 2, 8)} PED` : 'N/A',
        },
        Decay: object.Properties?.Economy.Decay != null ? `${object.Properties?.Economy.Decay.toFixed(4)} PEC` : 'N/A',
        Cost: cost ? `${cost.toFixed(4)} PEC` : 'N/A',
      },
      Healing: {
        HPS: {
          Label: 'HPS',
          Tooltip: 'Heal per second',
          Value: getHps(object) != null ? `${getHps(object).toFixed(2)}` : 'N/A',
          Bold: true
        },
        MaxHeal: {
          Label: 'Max. Heal',
          Value: object.Properties?.MaxHeal != null ? `${object.Properties?.MaxHeal.toFixed(2)} HP` : 'N/A',
        },
        MinHeal: {
          Label: 'Min. Heal',
          Value: object.Properties?.MinHeal != null ? `${object.Properties?.MinHeal.toFixed(2)} HP` : 'N/A',
        }
      },
      Skill: {
        SkillIncreaseBonus: {
          Label: 'SiB',
          Tooltip: 'Skill Increase Bonus',
          Value: `${object.Properties?.Skill.IsSiB ? 'Yes' : 'No'}`,
        },
        Profession: {
          Value: [
            additional.type === 'chips' ? 'Biotropic' : 'Paramedic',
            `${object.Properties?.Skill.LearningIntervalStart?.toFixed(1) ?? 'N/A'} - ${object.Properties?.Skill.LearningIntervalEnd?.toFixed(1) ?? 'N/A'}`],
        }
      },
      "Equip Effects": object.EffectsOnEquip?.length > 0 ? onEquip : null,
      "Use Effects": object.EffectsOnUse?.length > 0 ? onUse : null,
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
          Tooltip: 'Time until the weapon is broken from full condition',
          Value: cyclePerHour != null ? `${(cyclePerRepair / cyclePerHour).toFixed(2)}h` : 'N/A',
        },
      }
    };
  };

  let tableViewInfo = {
    all: {
      columns: ['Name', 'Type', 'Weight', 'HPS', 'Max. Heal', 'Min. Heal', 'Reload', 'HPP', 'Max. TT', 'Cost', 'SiB', 'Min', 'Max', 'Total Uses'],
      columnWidths: ['1fr', '100px', '90px', '60px', '90px', '90px', '70px', '80px', '100px', '100px', '60px', '60px', '60px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item._type === 'tool' ? 'Medical Tool' : 'Medical Chip',
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          getHps(item) != null ? `${getHps(item).toFixed(2)}` : 'N/A',
          item.Properties?.MaxHeal != null ? `${item.Properties?.MaxHeal.toFixed(2)} HP` : 'N/A',
          item.Properties?.MinHeal != null ? `${item.Properties?.MinHeal.toFixed(2)} HP` : 'N/A',
          getReload(item) != null ? `${getReload(item).toFixed(2)}s` : 'N/A',
          getHpp(item) != null ? getHpp(item) : 'N/A',
          item.Properties?.Economy.MaxTT != null ? `${clampDecimals(item.Properties?.Economy.MaxTT, 2, 8)} PED` : 'N/A',
          getCost(item) != null ? `${getCost(item).toFixed(4)} PEC` : 'N/A',
          item.Properties?.Skill?.IsSiB ? 'Yes' : 'No',
          item.Properties?.Skill?.LearningIntervalStart != null ? item.Properties?.Skill?.LearningIntervalStart.toFixed(1) : 'N/A',
          item.Properties?.Skill?.LearningIntervalEnd != null ? item.Properties?.Skill?.LearningIntervalEnd.toFixed(1) : 'N/A',
          getTotalUses(item) ?? 'N/A',
        ];
      }
    },
    tools: {
      columns: ['Name', 'Weight', 'HPS', 'Max. Heal', 'Min. Heal', 'Reload', 'HPP', 'Max. TT', 'Cost', 'SiB', 'Min', 'Max', 'Total Uses'],
      columnWidths: ['1fr', '90px', '60px', '90px', '90px', '70px', '80px', '100px', '100px', '60px', '60px', '60px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          getHps(item) != null ? `${getHps(item).toFixed(2)}` : 'N/A',
          item.Properties?.MaxHeal != null ? `${item.Properties?.MaxHeal.toFixed(2)} HP` : 'N/A',
          item.Properties?.MinHeal != null ? `${item.Properties?.MinHeal.toFixed(2)} HP` : 'N/A',
          getReload(item) != null ? `${getReload(item).toFixed(2)}s` : 'N/A',
          getHpp(item) != null ? getHpp(item) : 'N/A',
          item.Properties?.Economy.MaxTT != null ? `${clampDecimals(item.Properties?.Economy.MaxTT, 2, 8)} PED` : 'N/A',
          getCost(item) != null ? `${getCost(item).toFixed(4)} PEC` : 'N/A',
          item.Properties?.Skill?.IsSiB ? 'Yes' : 'No',
          item.Properties?.Skill?.LearningIntervalStart != null ? item.Properties?.Skill?.LearningIntervalStart.toFixed(1) : 'N/A',
          item.Properties?.Skill?.LearningIntervalEnd != null ? item.Properties?.Skill?.LearningIntervalEnd.toFixed(1) : 'N/A',
          getTotalUses(item) ?? 'N/A',
        ];
      }
    },
    chips: {
      columns: ['Name', 'Weight', 'HPS', 'Max. Heal', 'Min. Heal', 'Reload', 'HPP', 'Max. TT', 'Cost', 'SiB', 'Min', 'Max', 'Total Uses'],
      columnWidths: ['1fr', '90px', '60px', '90px', '90px', '70px', '80px', '100px', '100px', '60px', '60px', '60px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          getHps(item) != null ? `${getHps(item).toFixed(2)}` : 'N/A',
          item.Properties?.MaxHeal != null ? `${item.Properties?.MaxHeal.toFixed(2)} HP` : 'N/A',
          item.Properties?.MinHeal != null ? `${item.Properties?.MinHeal.toFixed(2)} HP` : 'N/A',
          getReload(item) != null ? `${getReload(item).toFixed(2)}s` : 'N/A',
          getHpp(item) != null ? getHpp(item) : 'N/A',
          item.Properties?.Economy.MaxTT != null ? `${clampDecimals(item.Properties?.Economy.MaxTT, 2, 8)} PED` : 'N/A',
          getCost(item) != null ? `${getCost(item).toFixed(4)} PEC` : 'N/A',
          item.Properties?.Skill?.IsSiB ? 'Yes' : 'No',
          item.Properties?.Skill?.LearningIntervalStart != null ? item.Properties?.Skill?.LearningIntervalStart.toFixed(1) : 'N/A',
          item.Properties?.Skill?.LearningIntervalEnd != null ? item.Properties?.Skill?.LearningIntervalEnd.toFixed(1) : 'N/A',
          getTotalUses(item) ?? 'N/A',
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
  title='Medical Tools'
  basePath='/items/medicaltools'
  let:object
  let:additional>
  <div class="flex-item-double">
    <div class="big-title">{object.Name}</div>
  </div>
  {#if object && !hasItemTag(object.Name, 'L') && additional.type == 'tools'}
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