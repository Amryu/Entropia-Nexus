<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { hasItemTag, clampDecimals, getTypeLink, getTimeString } from "$lib/util";

  import EntityViewer from '$lib/components/EntityViewer.svelte';
  import Tiering from "$lib/components/Tiering.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";
  import { editConfigEffectsOnEquip, editConfigEffectsOnUse, getEditConfigTier } from '$lib/editConfigUtil.js';

  export let data;

  const navButtonInfo = [
    {
      Label: 'Rgd',
      Title: 'Ranged',
      Type: 'ranged',
      IsRoute: false,
    },
    {
      Label: 'Mle',
      Title: 'Melee',
      Type: 'melee',
      IsRoute: false,
    },
    {
      Label: 'Mdf',
      Title: 'Mindforce',
      Type: 'mindforce',
      IsRoute: false,
    },
    {
      Label: 'Att',
      Title: 'Attached',
      Type: 'attached',
      IsRoute: false,
    }
  ];

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

    let onEquip = {};

    if (weapon.EffectsOnEquip != null && weapon.EffectsOnEquip.length > 0) {
      weapon.EffectsOnEquip
        .sort((a,b) => a.Name.localeCompare(b.Name))
        .forEach(effect => onEquip[effect.Name] = `${effect.Values.Strength}${effect.Values.Unit ?? '<Unit>'}`);
    }

    let onUse = {};

    if (weapon.EffectsOnUse != null && weapon.EffectsOnUse.length > 0) {
      weapon.EffectsOnUse
        .sort((a,b) => a.Name.localeCompare(b.Name))
        .forEach(effect => onUse[effect.Name] = `${effect.Values.Strength}${effect.Values.Unit ?? '<Unit>'} for ${getTimeString(effect.Values.DurationSeconds)}`);
    }

    return {
      General: {
        Weight: weapon.Properties?.Weight != null ? `${clampDecimals(weapon.Properties?.Weight, 1, 6)}kg` : 'N/A',
        Class: weapon.Properties?.Class ?? 'N/A',
        Category: weapon.Properties?.Category ?? 'N/A',
        Type: weapon.Properties?.Type ?? 'N/A',
        Range: weapon.Properties?.Range != null ? `${weapon.Properties?.Range}m` : 'N/A',
        Reload: reload != null ? `${reload.toFixed(2)}s` : 'N/A',
        UsesPerMinute: {
          Label: 'Uses/min',
          Value: reload != null ? `${clampDecimals((60 / reload), 0, 2)}` : 'N/A',
        }
      },
      Economy: {
        Efficiency: {
          Label: 'Efficiency (%)',
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
          Label: 'Max. TT (PED)',
          Value: weapon.Properties?.Economy.MaxTT != null ? `${clampDecimals(weapon.Properties?.Economy.MaxTT, 2, 8)} PED` : 'N/A',
        },
        MinTT: {
          Label: 'Min. TT (PED)',
          Value: weapon.Properties?.Economy.MinTT != null ? `${clampDecimals(weapon.Properties?.Economy.MinTT, 2, 8)} PED` : 'N/A',
        },
        Decay: {
          Label: 'Decay (PEC)',
          Value: weapon.Properties?.Economy.Decay != null ? `${weapon.Properties?.Economy.Decay.toFixed(4)} PEC` : 'N/A',
        },
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
        Interval: {
          Label: 'Interval',
          Value: totalDamage != null ? `${(totalDamage*0.5).toFixed(1)} - ${(totalDamage).toFixed(1)}` : 'N/A',
          Bold: true,
        },
      },
      Mindforce: weapon.Properties?.Class === 'Mindforce' ? {
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
          LinkKey: weapon.ProfessionHit?.Name != null ? getTypeLink(weapon.ProfessionHit?.Name, 'Profession') : null,
          Value: [weapon.ProfessionHit?.Name ?? 'N/A', `${weapon.Properties?.Skill.Hit.LearningIntervalStart ?? 'N/A'} - ${weapon.Properties?.Skill.Hit.LearningIntervalEnd ?? 'N/A'}`],
        },
        ProfessionDmg: {
          Label: 'Prof. (Dmg)',
          Tooltip: 'Profession (Dmg)',
          LinkKey: weapon.ProfessionDmg?.Name != null ? getTypeLink(weapon.ProfessionDmg?.Name, 'Profession') : null,
          Value: [weapon.ProfessionDmg?.Name ?? 'N/A', `${weapon.Properties?.Skill.Dmg.LearningIntervalStart ?? 'N/A'} - ${weapon.Properties?.Skill.Dmg.LearningIntervalEnd ?? 'N/A'}`],
        },
      },
      "Equip Effects": weapon.EffectsOnEquip?.length > 0 ? onEquip : null,
      "Use Effects": weapon.EffectsOnUse?.length > 0 ? onUse : null,
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

  const editConfig = {
    constructor: () => ({
      Name: 'New Weapon',
      Properties: {
        Description: null,
        Weight: null,
        Class: null,
        Category: null,
        Type: null,
        Range: null,
        UsesPerMinute: null,
        ImpactRadius: null,
        Economy: {
          Efficiency: null,
          MaxTT: null,
          MinTT: null,
          Decay: null,
          AmmoBurn: null,
        },
        Skill: {
          IsSiB: true,
          Hit: {
            LearningIntervalStart: null,
            LearningIntervalEnd: null,
          },
          Dmg: {
            LearningIntervalStart: null,
            LearningIntervalEnd: null,
          }
        },
        Damage: {
          Impact: null,
          Cut: null,
          Stab: null,
          Penetration: null,
          Shrapnel: null,
          Burn: null,
          Cold: null,
          Acid: null,
          Electric: null,
        },
        Mindforce: {
          Level: null,
          Concentration: null,
          Cooldown: null,
          CooldownGroup: null,
        }
      },
      Ammo: {
        Name: null,
      },
      ProfessionHit: {
        Name: null,
      },
      ProfessionDmg: {
        Name: null,
      },
      AttachmentType: {
        Name: null,
      },
      EffectsOnEquip: [],
      EffectsOnUse: [],
      Tiers: [],
    }),
    dependencies: ['effects', 'vehicleattachmenttypes'],
    controls: [
      {
        label: 'General',
        type: 'group',
        controls: [
          { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v},
          { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
          { label: 'Weight', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Weight, '_set': (x, v) => x.Properties.Weight = v},
          { label: 'Class', type: 'select', options: _ => ['Ranged', 'Melee', 'Mindforce', 'Attached', 'Stationary'], '_get': x => x.Properties?.Class, '_set': (x, v) => x.Properties.Class = v},
          { label: 'Category', type: 'select', options: x => x.Properties.Class === 'Ranged'
            ? ['Rifle', 'Carbine', 'Pistol', 'Cannon', 'Flamethrower', 'Support']
            : x.Properties.Class === 'Melee'
            ? ['Axe', 'Sword', 'Knife', 'Whip', 'Club', 'Power Fist']
            : x.Properties.Class === 'Mindforce'
            ? ['Chip']
            : x.Properties.Class === 'Attached'
            ? ['Hanging', 'Mounted', 'Turret']
            : ['Turret'],
            '_get': x => x.Properties?.Category, '_set': (x, v) => x.Properties.Category = v
          },
          { label: 'Type', type: 'select', options: x => x.Properties.Class === 'Ranged' || x.Properties.Class === 'Attached' || x.Properties.Class === 'Stationary'
            ? ['Laser', 'BLP', 'Explosive', 'Gauss', 'Plasma']
            : x.Properties.Class === 'Melee'
            ? ['Blades', 'Clubs', 'Fists', 'Whips']
            : x.Properties.Class === 'Mindforce'
            ? ['Pyrokinetic', 'Cryogenic', 'Electrokinesis']
            : [],
            '_get': x => x.Properties?.Type, '_set': (x, v) => x.Properties.Type = v
          },
          { '_if': x => x.Properties.Class === 'Attached', label: 'AttachmentType', type: 'select', options: (_, d) => d.vehicleattachmenttypes.map(x => x.Name), '_get': x => x.AttachmentType?.Name, '_set': (x, v) => x.AttachmentType.Name = v},
          { label: 'Range', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Range, '_set': (x, v) => x.Properties.Range = v},
          { label: 'Uses/min', type: 'number', step: '0.01', min: '0', '_get': x => x.Properties?.UsesPerMinute, '_set': (x, v) => x.Properties.UsesPerMinute = v},
          { '_if': x => x.Properties.Type === 'Explosive', label: 'Impact Radius', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.ImpactRadius, '_set': (x, v) => x.Properties.ImpactRadius = v},
        ]
      },
      {
        label: 'Economy',
        type: 'group',
        controls: [
          { label: 'Efficiency (%)', type: 'number', step: '0.1', min: '0', max: '100', '_get': x => x.Properties?.Economy?.Efficiency, '_set': (x, v) => x.Properties.Economy.Efficiency = v},
          { label: 'Max. TT (PED)', type: 'number', step: '0.00001', min: '0', '_get': x => x.Properties?.Economy?.MaxTT, '_set': (x, v) => x.Properties.Economy.MaxTT = v},
          { label: 'Min. TT (PED)', type: 'number', step: '0.00001', min: '0', '_get': x => x.Properties?.Economy?.MinTT, '_set': (x, v) => x.Properties.Economy.MinTT = v},
          { label: 'Decay (PEC)', type: 'number', step: '0.00001', min: '0', '_get': x => x.Properties?.Economy?.Decay, '_set': (x, v) => x.Properties.Economy.Decay = v},
          { label: 'Ammo Type', type: 'select', options: x => x.Properties.Class === 'Ranged' || x.Properties.Class === 'Attached' || x.Properties.Class === 'Stationary'
            ? ['Weapon Cells', 'BLP Pack', 'Explosive Projectiles']
            : x.Properties.Class === 'Melee'
            ? [null, 'Weapon Cells']
            : x.Properties.Class === 'Mindforce'
            ? ['Synthetic Mind Essence', 'Mind Essence', 'Light Mind Essence']
            : [],
            '_get': x => x.Ammo?.Name, '_set': (x, v) => {
              if (x.Ammo == null) {
                x.Ammo = { Name: (v === '' ? null : v)};
              } else {
                x.Ammo.Name = v === '' ? null : v;
              }
            }
          }, 
          { label: 'Ammo Burn', type: 'number', step: '1', min: '0', '_if': x => x.Ammo?.Name !== null, '_get': x => x.Properties?.Economy?.AmmoBurn, '_set': (x, v) => x.Properties.Economy.AmmoBurn = v},
        ]
      },
      {
        label: 'Damage',
        type: 'group',
        controls: [
          { label: 'Impact', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Damage?.Impact, '_set': (x, v) => x.Properties.Damage.Impact = v},
          { label: 'Cut', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Damage?.Cut, '_set': (x, v) => x.Properties.Damage.Cut = v},
          { label: 'Stab', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Damage?.Stab, '_set': (x, v) => x.Properties.Damage.Stab = v},
          { label: 'Penetration', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Damage?.Penetration, '_set': (x, v) => x.Properties.Damage.Penetration = v},
          { label: 'Shrapnel', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Damage?.Shrapnel, '_set': (x, v) => x.Properties.Damage.Shrapnel = v},
          { label: 'Burn', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Damage?.Burn, '_set': (x, v) => x.Properties.Damage.Burn = v},
          { label: 'Cold', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Damage?.Cold, '_set': (x, v) => x.Properties.Damage.Cold = v},
          { label: 'Acid', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Damage?.Acid, '_set': (x, v) => x.Properties.Damage.Acid = v},
          { label: 'Electric', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Damage?.Electric, '_set': (x, v) => x.Properties.Damage.Electric = v},
        ]
      },
      {
        '_if': x => x.Properties.Class === 'Mindforce',
        label: 'Mindforce',
        type: 'group',
        controls: [
          { label: 'Level', type: 'number', step: '1', min: '1', '_get': x => x.Properties?.Mindforce?.Level, '_set': (x, v) => x.Properties.Mindforce.Level = v},
          { label: 'Concentration', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Mindforce?.Concentration, '_set': (x, v) => x.Properties.Mindforce.Concentration = v},
          { label: 'Cooldown', type: 'number', step: '0.1', min: '0', '_get': x => x.Properties?.Mindforce?.Cooldown, '_set': (x, v) => x.Properties.Mindforce.Cooldown = v},
          { label: 'Cooldown Group', type: 'number', step: '1', min: '1', '_get': x => x.Properties?.Mindforce?.CooldownGroup, '_set': (x, v) => x.Properties.Mindforce.CooldownGroup = v},
        ]        
      },
      {
        label: 'Skill',
        type: 'group',
        controls: [
          { label: 'SiB', type: 'checkbox', '_get': x => x.Properties?.Skill.IsSiB, '_set': (x, v) => x.Properties.Skill.IsSiB = v},
          { label: 'Profession (Hit)', type: 'select', options: x => x.Properties.Type === 'Laser'
            ? ['Laser Pistoleer (Hit)', 'Laser Sniper (Hit)', 'Mounted Laser (Hit)']
            : x.Properties.Type === 'BLP'
            ? ['BLP Pistoleer (Hit)', 'BLP Sniper (Hit)', 'Mounted BLP (Hit)']
            : x.Properties.Type === 'Plasma'
            ? ['Plasma Pistoleer (Hit)', 'Plasma Sniper (Hit)']
            : x.Properties.Type === 'Gauss'
            ? ['Gauss Sniper (Hit)']
            : x.Properties.Type === 'Explosive'
            ? ['Grenadier (Hit)', 'Mounted Grenadier (Hit)']
            : x.Properties.Type === 'Pyrokinetic'
            ? ['Pyro Kinetic (Hit)']
            : x.Properties.Type === 'Cryogenic'
            ? ['Cryogenic (Hit)']
            : x.Properties.Type === 'Electrokinesis'
            ? ['Electro Kinetic (Hit)']
            : x.Properties.Type === 'Blades'
            ? ['Swordsman (Hit)', 'Knifefighter (Hit)', 'Whipper (Hit)']
            : x.Properties.Type === 'Clubs'
            ? ['One Handed Clubber (Hit)', 'Two Handed Clubber (Hit)']
            : x.Properties.Type === 'Fists'
            ? ['Brawler (Hit)']
            : x.Properties.Type === 'Whips'
            ? ['Whipper (Hit)']
            : [],
            '_get': x => x.ProfessionHit?.Name,
            '_set': (x, v) => {
              if (x.ProfessionHit == null) {
                x.ProfessionHit = { Name: (v === '' ? null : v) };
              } else {
                x.ProfessionHit.Name = v === '' ? null : v;
              }
            }},
          { '_if': x => x.Properties.Skill.IsSiB, label: 'Learning Interval (Hit)', type: 'range', min: '0', step: '0.1', '_get': x => [x.Properties?.Skill?.Hit?.LearningIntervalStart, x.Properties?.Skill?.Hit?.LearningIntervalEnd], '_set': (x, v) => { x.Properties.Skill.Hit.LearningIntervalStart = Number(v[0]); x.Properties.Skill.Hit.LearningIntervalEnd = Number(v[1]); }},
          { label: 'Profession (Dmg)', type: 'select', options: x => x.Properties.Type === 'Laser'
            ? ['Ranged Laser (Dmg)']
            : x.Properties.Type === 'BLP'
            ? ['Ranged BLP (Dmg)']
            : x.Properties.Type === 'Plasma'
            ? ['Ranged Plasma (Dmg)']
            : x.Properties.Type === 'Gauss'
            ? ['Ranged Gauss (Dmg)']
            : x.Properties.Type === 'Explosive'
            ? ['Grenadier (Dmg)']
            : x.Properties.Type === 'Pyrokinetic'
            ? ['Pyro Kinetic (Dmg)']
            : x.Properties.Type === 'Cryogenic'
            ? ['Cryogenic (Dmg)']
            : x.Properties.Type === 'Electrokinesis'
            ? ['Electro Kinetic (Dmg)']
            : x.Properties.Type === 'Blades'
            ? ['Swordsman (Dmg)', 'Knifefighter (Dmg)', 'Whipper (Dmg)']
            : x.Properties.Type === 'Clubs'
            ? ['One Handed Clubber (Dmg)', 'Two Handed Clubber (Dmg)']
            : x.Properties.Type === 'Fists'
            ? ['Brawler (Dmg)']
            : x.Properties.Type === 'Whips'
            ? ['Whipper (Dmg)']
            : [],
            '_get': x => x.ProfessionDmg?.Name,
            '_set': (x, v) => {
              if (x.ProfessionDmg == null) {
                x.ProfessionDmg = { Name: (v === '' ? null : v)};
              } else {
                x.ProfessionDmg.Name = v === '' ? null : v;
              }
            }},
          { '_if': x => x.Properties.Skill.IsSiB, label: 'Learning Interval (Dmg)', type: 'range', min: '0', step: '0.1', '_get': x => [x.Properties?.Skill?.Dmg?.LearningIntervalStart, x.Properties?.Skill?.Dmg?.LearningIntervalEnd], '_set': (x, v) => { x.Properties.Skill.Dmg.LearningIntervalStart = Number(v[0]); x.Properties.Skill.Dmg.LearningIntervalEnd = Number(v[1]); }},
        ]
      },
      { label: 'Effects on Equip', type: 'list', config: editConfigEffectsOnEquip, '_get': x => x.EffectsOnEquip, '_set': (x, v) => x.EffectsOnEquip = v },
      { label: 'Effects on Use', type: 'list', config: editConfigEffectsOnUse, '_get': x => x.EffectsOnUse, '_set': (x, v) => x.EffectsOnUse = v },
      { '_if': x => !hasItemTag(x.Name, 'L'), label: 'Tiering', type: 'array', size: 10, config: getEditConfigTier('Weapon'), indexFunc: (x, i) => x?.Properties?.Tier === i + 1, itemNameFunc: (i) => `Tier ${i + 1}`, '_get': x => x.Tiers ?? [], '_set': (x, v) => x.Tiers = v },
    ]
  };

  let viewInfoSection = {
    columns: ['Name', 'Category', 'Type', 'DPS', 'Damage', 'Range', 'Reload', 'Uses/min', 'Efficiency', 'DPP', 'Max. TT', 'Cost', 'SiB', 'Min', 'Max'],
    columnWidths: ['1fr', '105px', '85px', '70px', '80px', '65px', '70px', '80px', '85px', '70px', '100px', '95px', '50px', '50px', '50px'],
    rowValuesFunction: (item) => [
      item.Name,
      item.Properties?.Category ?? 'N/A',
      item.Properties?.Type ?? 'N/A',
      getDps(item) != null ? getDps(item).toFixed(2) : 'N/A',
      getTotalDamage(item) != null ? Math.round(getTotalDamage(item)) : 'N/A',
      item.Properties?.Range != null ? `${item.Properties?.Range}m` : 'N/A',
      getReload(item) != null ? `${getReload(item).toFixed(2)}s` : 'N/A',
      getReload(item) != null ? `${clampDecimals((60 / getReload(item)), 0, 2)}` : 'N/A',
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
  user={data.session.user}
  tableViewInfo={tableViewInfo}
  navButtonInfo={navButtonInfo}
  editConfig={editConfig}
  propertiesDataFunction={propertiesDataFunction}
  title='Weapons'
  type='Weapon'
  basePath='/items/weapons'
  let:object
  let:additional>
  {#if !hasItemTag(object.Name, 'L')}
  <!-- Tiering -->
  <div class="flex-item flex-span-2">
    <Tiering tieringInfo={additional.tierInfo} />
  </div>
  {/if}
  <!-- Acquisition -->
  <div class="flex-item flex-span-2">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>