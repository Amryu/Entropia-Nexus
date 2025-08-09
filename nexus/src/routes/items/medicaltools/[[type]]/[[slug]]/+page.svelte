<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { hasItemTag, clampDecimals, getTimeString, getTypeLink } from "$lib/util";

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Tiering from "$lib/components/Tiering.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";
  import { editConfigEffectsOnEquip, editConfigEffectsOnUse, getEditConfigTier } from '$lib/editConfigUtil.js';

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
        UsesPerMinute: {
          Label: 'Uses/min',
          Value: reload ? `${clampDecimals(60 / reload, 0, 2)}` : 'N/A',
        }
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
        Ammo: additional.type === 'chips' ? {
          Label: 'Ammo',
          Value: `${object.Ammo?.Name ?? 'N/A'}`,
        } : null,
        AmmoBurn: additional.type === 'chips' ?  {
          Label: 'Ammo Burn',
          Value: `${object.Properties?.Economy.AmmoBurn ?? 'N/A'}`,
        } : null,
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
      Mindforce: additional.type === 'chips' ? {
        Level: object.Properties?.Mindforce?.Level ?? 'N/A',
        Concentration: object.Properties?.Mindforce?.Concentration ? `${object.Properties?.Mindforce?.Concentration}s` : 'N/A',
        Cooldown: object.Properties?.Mindforce?.Cooldown ? `${object.Properties?.Mindforce?.Cooldown}s` : 'N/A',
        CooldownGroup: {
          Label: 'Cooldown Group',
          Value: object.Properties?.Mindforce?.CooldownGroup ?? 'N/A',
        }
      } : null,
      Skill: {
        SkillIncreaseBonus: {
          Label: 'SiB',
          Tooltip: 'Skill Increase Bonus',
          Value: `${object.Properties?.Skill.IsSiB ? 'Yes' : 'No'}`,
        },
        Profession: {
          LinkValue: [getTypeLink(additional.type === 'chips' ? 'Biotropic' : 'Paramedic', 'Profession'), null],
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
          Value: cyclePerHour > 0 ? `${(cyclePerRepair / cyclePerHour).toFixed(2)}h` : 'N/A',
        },
      }
    };
  };

  let editConfig = {
    tools: {
      constructor: () => ({
        Name: 'New Medical Tool',
        Properties: {
          Description: null,
          Weight: null,
          MaxHeal: null,
          MinHeal: null,
          UsesPerMinute: null,
          Economy: {
            MaxTT: null,
            MinTT: null,
            Decay: null,
            AmmoBurn: null
          },
          Skill: {
            IsSiB: true,
            LearningIntervalStart: null,
            LearningIntervalEnd: null
          }
        },
        EffectsOnEquip: [],
        EffectsOnUse: [],
        Tiers: []
      }),
      dependencies: ['effects'],
      controls: [
        {
          label: 'General',
          type: 'group',
          controls: [
            { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
            { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
            { label: 'Weight', type: 'number', step: 0.1, min: 0, '_get': x => x.Properties.Weight, '_set': (x, v) => x.Properties.Weight = v },
            { label: 'Max. Heal', type: 'number', step: 0.01, min: 0, '_get': x => x.Properties.MaxHeal, '_set': (x, v) => x.Properties.MaxHeal = v },
            { label: 'Min. Heal', type: 'number', step: 0.01, min: 0, '_get': x => x.Properties.MinHeal, '_set': (x, v) => x.Properties.MinHeal = v },
            { label: 'Uses/min', type: 'number', step: 0.01, min: 0, '_get': x => x.Properties.UsesPerMinute, '_set': (x, v) => x.Properties.UsesPerMinute = v },
          ]
        },
        {
          label: 'Economy',
          type: 'group',
          controls: [
            { label: 'Max. TT (PED)', type: 'number', step: 0.01, min: 0, '_get': x => x.Properties.Economy.MaxTT, '_set': (x, v) => x.Properties.Economy.MaxTT = v },
            { label: 'Min. TT (PED)', type: 'number', step: 0.01, min: 0, '_get': x => x.Properties.Economy.MinTT, '_set': (x, v) => x.Properties.Economy.MinTT = v },
            { label: 'Decay (PEC)', type: 'number', step: 0.0001, min: 0, '_get': x => x.Properties.Economy.Decay, '_set': (x, v) => x.Properties.Economy.Decay = v },
          ]
        },
        {
          label: 'Skill',
          type: 'group',
          controls: [
            { label: 'SiB', type: 'checkbox', '_get': x => x.Properties.Skill.IsSiB, '_set': (x, v) => x.Properties.Skill.IsSiB = v },
            { label: 'Learning Interval', type: 'range', min: 0, step: 0.1, '_get': x => [x.Properties.Skill.LearningIntervalStart, x.Properties.Skill.LearningIntervalEnd], '_set': (x, v) => { x.Properties.Skill.LearningIntervalStart = v[0]; x.Properties.Skill.LearningIntervalEnd = v[1]; } },
          ]
        },
        { label: 'Effects on Equip', type: 'list', config: editConfigEffectsOnEquip, '_get': x => x.EffectsOnEquip, '_set': (x, v) => x.EffectsOnEquip = v },
        { label: 'Effects on Use', type: 'list', config: editConfigEffectsOnUse, '_get': x => x.EffectsOnUse, '_set': (x, v) => x.EffectsOnUse = v },
        { '_if': x => !hasItemTag(x.Name, 'L'), label: 'Tiering', type: 'array', size: 10, config: getEditConfigTier('MedicalTool'), indexFunc: (x, i) => x?.Properties?.Tier === i + 1, itemNameFunc: (i) => `Tier ${i + 1}`, '_get': x => x.Tiers, '_set': (x, v) => x.Tiers = v },
      ]
    },
    chips: {
      constructor: () => ({
        Name: 'New Medical Chip',
        Properties: {
          Description: null,
          Weight: null,
          MaxHeal: null,
          MinHeal: null,
          UsesPerMinute: null,
          Range: null,
          Economy: {
            MaxTT: null,
            MinTT: null,
            Decay: null,
            AmmoBurn: null
          },
          Skill: {
            IsSiB: null,
            LearningIntervalStart: null,
            LearningIntervalEnd: null
          },
          Mindforce: {
            Level: null,
            Concentration: null,
            Cooldown: null,
            CooldownGroup: null
          }
        },
        Ammo: {
          Name: null,
        },
        EffectsOnEquip: [],
        EffectsOnUse: []
      }),
      dependencies: ['effects'],
      controls: [
        {
          label: 'General',
          type: 'group',
          controls: [
            { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
            { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
            { label: 'Weight', type: 'number', step: 0.1, min: 0, '_get': x => x.Properties.Weight, '_set': (x, v) => x.Properties.Weight = v },
            { label: 'Max. Heal', type: 'number', step: 0.01, min: 0, '_get': x => x.Properties.MaxHeal, '_set': (x, v) => x.Properties.MaxHeal = v },
            { label: 'Min. Heal', type: 'number', step: 0.01, min: 0, '_get': x => x.Properties.MinHeal, '_set': (x, v) => x.Properties.MinHeal = v },
            { label: 'Uses/min', type: 'number', step: 0.01, min: 0, '_get': x => x.Properties.UsesPerMinute, '_set': (x, v) => x.Properties.UsesPerMinute = v },
            { label: 'Range', type: 'number', step: 0.1, min: 0, '_get': x => x.Properties.Range, '_set': (x, v) => x.Properties.Range = v },
          ]
        },
        {
          label: 'Economy',
          type: 'group',
          controls: [
            { label: 'Max. TT (PED)', type: 'number', step: 0.01, min: 0, '_get': x => x.Properties.Economy.MaxTT, '_set': (x, v) => x.Properties.Economy.MaxTT = v },
            { label: 'Min. TT (PED)', type: 'number', step: 0.01, min: 0, '_get': x => x.Properties.Economy.MinTT, '_set': (x, v) => x.Properties.Economy.MinTT = v },
            { label: 'Decay (PEC)', type: 'number', step: 0.0001, min: 0, '_get': x => x.Properties.Economy.Decay, '_set': (x, v) => x.Properties.Economy.Decay = v },
            { label: 'Ammo Type', type: 'select', options: _ => ['Synthetic Mind Essence', 'Mind Essence', 'Light Mind Essence'], '_get': x => x.Ammo.Name, '_set': (x, v) => x.Ammo.Name = v },
            { label: 'Ammo Burn', type: 'number', step: 0.0001, min: 0, '_get': x => x.Properties.Economy.AmmoBurn, '_set': (x, v) => x.Properties.Economy.AmmoBurn = v },
          ]
        },
        {
          label: 'Skill',
          type: 'group',
          controls: [
            { label: 'SiB', type: 'checkbox', '_get': x => x.Properties.Skill.IsSiB, '_set': (x, v) => x.Properties.Skill.IsSiB = v },
            { label: 'Learning Interval', type: 'range', min: 0, step: 0.1, '_get': x => [x.Properties.Skill.LearningIntervalStart, x.Properties.Skill.LearningIntervalEnd], '_set': (x, v) => { x.Properties.Skill.LearningIntervalStart = v[0]; x.Properties.Skill.LearningIntervalEnd = v[1]; } },
          ]
        },
        {
          label: 'Mindforce',
          type: 'group',
          controls: [
            { label: 'Level', type: 'number', step: 1, min: 0, '_get': x => x.Properties.Mindforce.Level, '_set': (x, v) => x.Properties.Mindforce.Level = v },
            { label: 'Concentration', type: 'number', step: 1, min: 0, '_get': x => x.Properties.Mindforce.Concentration, '_set': (x, v) => x.Properties.Mindforce.Concentration = v },
            { label: 'Cooldown', type: 'number', step: 0.1, min: 0, '_get': x => x.Properties.Mindforce.Cooldown, '_set': (x, v) => x.Properties.Mindforce.Cooldown = v },
            { label: 'Cooldown Group', type: 'number', step: 1, min: 0, '_get': x => x.Properties.Mindforce.CooldownGroup, '_set': (x, v) => x.Properties.Mindforce.CooldownGroup = v },
          ]
        },
        { label: 'Effects on Equip', type: 'list', config: editConfigEffectsOnEquip, '_get': x => x.EffectsOnEquip, '_set': (x, v) => x.EffectsOnEquip = v },
        { label: 'Effects on Use', type: 'list', config: editConfigEffectsOnUse, '_get': x => x.EffectsOnUse, '_set': (x, v) => x.EffectsOnUse = v }
      ]
    }
  };

  let tableViewInfo = {
    all: {
      columns: ['Name', 'Type', 'Weight', 'HPS', 'Max. Heal', 'Min. Heal', 'Reload', 'Uses/min', 'HPP', 'Max. TT', 'Cost', 'SiB', 'Min', 'Max', 'Total Uses'],
      columnWidths: ['1fr', '100px', '90px', '60px', '90px', '90px', '70px', '80px', '80px', '100px', '100px', '60px', '60px', '60px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item._type === 'tool' ? 'Medical Tool' : 'Medical Chip',
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          getHps(item) != null ? `${getHps(item).toFixed(2)}` : 'N/A',
          item.Properties?.MaxHeal != null ? `${item.Properties?.MaxHeal.toFixed(2)} HP` : 'N/A',
          item.Properties?.MinHeal != null ? `${item.Properties?.MinHeal.toFixed(2)} HP` : 'N/A',
          getReload(item) != null ? `${getReload(item).toFixed(2)}s` : 'N/A',
          getReload(item) != null ? `${clampDecimals(60 / getReload(item), 0, 2)}` : 'N/A',
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
      columns: ['Name', 'Weight', 'HPS', 'Max. Heal', 'Min. Heal', 'Reload', 'Uses/min', 'HPP', 'Max. TT', 'Cost', 'SiB', 'Min', 'Max', 'Total Uses'],
      columnWidths: ['1fr', '90px', '60px', '90px', '90px', '70px', '80px', '80px', '100px', '100px', '60px', '60px', '60px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          getHps(item) != null ? `${getHps(item).toFixed(2)}` : 'N/A',
          item.Properties?.MaxHeal != null ? `${item.Properties?.MaxHeal.toFixed(2)} HP` : 'N/A',
          item.Properties?.MinHeal != null ? `${item.Properties?.MinHeal.toFixed(2)} HP` : 'N/A',
          getReload(item) != null ? `${getReload(item).toFixed(2)}s` : 'N/A',
          getReload(item) != null ? `${clampDecimals(60 / getReload(item), 0, 2)}` : 'N/A',
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
      columns: ['Name', 'Weight', 'HPS', 'Max. Heal', 'Min. Heal', 'Reload', 'Uses/min', 'HPP', 'Max. TT', 'Cost', 'SiB', 'Min', 'Max', 'Total Uses'],
      columnWidths: ['1fr', '90px', '60px', '90px', '90px', '70px', '80px', '80px', '100px', '100px', '60px', '60px', '60px', '100px'],
      rowValuesFunction: (item) => {
        return [
          item.Name,
          item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
          getHps(item) != null ? `${getHps(item).toFixed(2)}` : 'N/A',
          item.Properties?.MaxHeal != null ? `${item.Properties?.MaxHeal.toFixed(2)} HP` : 'N/A',
          item.Properties?.MinHeal != null ? `${item.Properties?.MinHeal.toFixed(2)} HP` : 'N/A',
          getReload(item) != null ? `${getReload(item).toFixed(2)}s` : 'N/A',
          getReload(item) != null ? `${clampDecimals(60 / getReload(item), 0, 2)}` : 'N/A',
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
  user={data.session.user}
  tableViewInfo={tableViewInfo}
  navButtonInfo={navButtonInfo}
  editConfig={editConfig}
  propertiesDataFunction={propertiesDataFunction}
  title='Medical Tools'
  type={data?.additional?.type ? (data.additional.type === 'tools' ? 'MedicalTool' : 'MedicalChip') : null}
  basePath='/items/medicaltools'
  let:object
  let:additional>
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