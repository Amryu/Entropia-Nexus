<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Codex from './Codex.svelte';
  import Loots from './Loots.svelte';
  import Maturities from './Maturities.svelte';
  import Locations from './Locations.svelte';

  export let data;

  const navButtonInfo = [
    {
      Label: 'Cly',
      Title: 'Calypso',
      Type: 'calypso',
      IsRoute: false
    },
    {
      Label: 'Cyr',
      Title: 'Cyrene',
      Type: 'cyrene',
      IsRoute: false
    },
    {
      Label: 'Ark',
      Title: 'Arkadia',
      Type: 'arkadia',
      IsRoute: false
    },
    {
      Label: 'Mnr',
      Title: 'Monria',
      Type: 'monria',
      IsRoute: false
    },
    {
      Label: 'Rck',
      Title: 'ROCKtropia',
      Type: 'rocktropia',
      IsRoute: false
    },
    {
      Label: 'Tou',
      Title: 'Toulan',
      Type: 'toulan',
      IsRoute: false
    },
    {
      Label: 'NI',
      Title: 'Next Island',
      Type: 'nextisland',
      IsRoute: false
    }
  ]

  function getDamageSpread(mob, name) {
    let attackSpreads = mob.Maturities.map(x => {
      let attack = x.Attacks.find(y => y.Name === name);
      if (attack == null) return null;
      return {
        Impact: attack.Damage.Impact,
        Cut: attack.Damage.Cut,
        Stab: attack.Damage.Stab,
        Penetration: attack.Damage.Penetration,
        Shrapnel: attack.Damage.Shrapnel,
        Burn: attack.Damage.Burn,
        Cold: attack.Damage.Cold,
        Acid: attack.Damage.Acid,
        Electric: attack.Damage.Electric,
      }
    }).filter(x => x != null).flat();

    if (attackSpreads.length === 0) return null;

    return {
      Impact: attackSpreads.map(x => x.Impact).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Cut: attackSpreads.map(x => x.Cut).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Stab: attackSpreads.map(x => x.Stab).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Penetration: attackSpreads.map(x => x.Penetration).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Shrapnel: attackSpreads.map(x => x.Shrapnel).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Burn: attackSpreads.map(x => x.Burn).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Cold: attackSpreads.map(x => x.Cold).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Acid: attackSpreads.map(x => x.Acid).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Electric: attackSpreads.map(x => x.Electric).reduce((a, b) => a + b, 0) / attackSpreads.length,
    }
  }

  let propertiesDataFunction = (mob) => {
    let primaryDamageSpread = getDamageSpread(mob, 'Primary');
    let secondaryDamageSpread = getDamageSpread(mob, 'Secondary');
    let tertiaryDamageSpread = getDamageSpread(mob, 'Tertiary');

    return {
      General: {
        Species: {
          Value: mob.Species?.Name ?? 'N/A',
          Tooltip: 'The Codex entry name for this mob. Mobs with the same species will progress the same codex.'
        },
        Planet: mob.Planet?.Name ?? 'N/A',
        Type: mob.ScanningProfession?.Name === 'Animal Investigator'
          ? 'Animal'
          : mob.ScanningProfession?.Name === 'Mutant Investigator'
          ? 'Mutant'
          : mob.ScanningProfession?.Name === 'Robot Investigator'
          ? 'Robot'
          : 'N/A',
        AttacksSpeed: {
          Label: 'Attack Speed',
          Value: mob.Properties?.AttacksPerMinute != null ? (60 /mob.Properties?.AttacksPerMinute).toFixed(2) : 'N/A',
        },
        AttackRange: {
          Label: 'Attack Range',
          Value: mob.Properties?.AttackRange != null ? `${mob.Properties?.AttackRange}m` : 'N/A',
        },
        AggressionRange: {
          Label: 'Aggression Range',
          Value: mob.Properties?.AggressionRange != null ? `${mob.Properties?.AggressionRange}m` : 'N/A',
        },
        VisionRange: {
          Label: 'Vision Range',
          Value: mob.Properties?.VisionRange != null ? `${mob.Properties?.VisionRange}m` : 'N/A',
        },
        Sweatable: {
          Label: 'Sweatable',
          Value: mob.Properties?.IsSweatable ? 'Yes' : 'No',
        },
      },
      Damage: {
        Primary: {
          Label: 'Primary',
          Value: primaryDamageSpread != null
            ? Object.entries(primaryDamageSpread).filter(x => x[1] > 0).map(x => `${x[0]}: ${x[1].toFixed(1)}%`)
            : 'N/A',
        },
        Secondary: secondaryDamageSpread != null ? {
          Label: 'Secondary',
          Value: Object.entries(secondaryDamageSpread).filter(x => x[1] > 0).map(x => `${x[0]}: ${x[1].toFixed(1)}%`)
        } : null,
        Tertiary: tertiaryDamageSpread != null ? {
          Label: 'Tertiary',
          Value: Object.entries(tertiaryDamageSpread).filter(x => x[1] > 0).map(x => `${x[0]}: ${x[1].toFixed(1)}%`)
        } : null,
      },
      Skill: {
        Defense: {
          Label: 'Defense',
          Value: mob.DefensiveProfession?.Name ?? 'N/A',
        },
        Scanning: {
          Label: 'Scanning',
          Value: mob.ScanningProfession?.Name ?? 'N/A',
        },
        Looting: {
          Label: 'Looting',
          Value: mob.ScanningProfession?.Name === 'Animal Investigator'
            ? 'Animal Looter'
            : mob.ScanningProfession?.Name === 'Mutant Investigator'
            ? 'Mutant Looter'
            : mob.ScanningProfession?.Name === 'Robot Investigator'
            ? 'Robot Looter'
            : 'N/A',
        },
      }
    };
  };

  const editConfig = {
    constructor: () => ({
      Name: '',
      Properties: {
        Description: null,
        AttacksPerMinute: null,
        AttackRange: null,
        AggressionRange: null,
        IsSweatable: false,
      },
      Species: {
        Name: null,
      },
      Planet: {
        Name: null,
      },
      DefensiveProfession: {
        Name: null,
      },
      ScanningProfession: {
        Name: null,
      },
      Maturities: [],
      Loots: [],
    }),
    dependencies: ['planets', 'mobspecies'],
    controls: [
      {
        label: 'General',
        type: 'group',
        controls: [
          { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
          { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
          { label: 'Species', type: 'select', options: (_, d) => ['', ...d.mobspecies.map(x => x.Name)], '_get': x => x.Species?.Name, '_set': (x, v) => x.Species.Name = v },
          { label: 'Planet', type: 'select', options: (_, d) => d.planets.filter(x => x.Id > 0).map(x => x.Name), '_get': x => x.Planet?.Name, '_set': (x, v) => x.Planet.Name = v },
          { label: 'Defensive Prof.', type: 'select', options: _ => ['Evader', 'Dodger', 'Jammer'], '_get': x => x.DefensiveProfession?.Name, '_set': (x, v) => x.DefensiveProfession.Name = v },
          { label: 'Scanning Prof.', type: 'select', options: _ => ['Animal Investigator', 'Mutant Investigator', 'Robot Investigator'], '_get': x => x.ScanningProfession?.Name, '_set': (x, v) => x.ScanningProfession.Name = v },
          { label: 'Attack Range', type: 'number', '_get': x => x.Properties.AttackRange, '_set': (x, v) => x.Properties.AttackRange = v },
          { label: 'Aggro Range', type: 'number', '_get': x => x.Properties.AggressionRange, '_set': (x, v) => x.Properties.AggressionRange = v },
          { label: 'Is Sweatable', type: 'checkbox', '_get': x => x.Properties.IsSweatable, '_set': (x, v) => x.Properties.IsSweatable = v },
        ]
      },
      { label: 'Maturities', type: 'list', config: {
          constructor: () => ({
            Name: '',
            Properties: {
              Level: null,
              Health: null,
              RegenerationInterval: null,
              RegenerationAmount: null,
              MissChance: null,
              Taming: {
                IsTameable: null,
                TamingLevel: null,
              },
              Attributes: {
                Strength: null,
                Agility: null,
                Intelligence: null,
                Psyche: null,
                Stamina: null,
              },
              Defense: {
                Stab: 0,
                Cut: 0,
                Impact: 0,
                Penetration: 0,
                Shrapnel: 0,
                Burn: 0,
                Cold: 0,
                Acid: 0,
                Electric: 0,
              },
            },
            Attacks: [],
          }),
          controls: [
            {
              label: 'General',
              type: 'group',
              controls: [
                { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
                { label: 'Level', type: 'number', '_get': x => x.Properties.Level, '_set': (x, v) => x.Properties.Level = v },
                { label: 'Health', type: 'number', '_get': x => x.Properties.Health, '_set': (x, v) => x.Properties.Health = v },
                {
                  label: 'Attributes',
                  type: 'multi',
                  fields: ['Strength', 'Agility', 'Intelligence', 'Psyche', 'Stamina'],
                  '_get': x => [x.Properties.Attributes.Strength, x.Properties.Attributes.Agility, x.Properties.Attributes.Intelligence, x.Properties.Attributes.Psyche, x.Properties.Attributes.Stamina],
                  '_set': (x, v) => [x.Properties.Attributes.Strength, x.Properties.Attributes.Agility, x.Properties.Attributes.Intelligence, x.Properties.Attributes.Psyche, x.Properties.Attributes.Stamina] = v
                }
              ]
            },
            {
              label: 'Combat',
              type: 'group',
              controls: [
                { label: 'Regen. Interval', type: 'number', '_get': x => x.Properties.RegenerationInterval, '_set': (x, v) => x.Properties.RegenerationInterval = v },
                { label: 'Regen. Amount', type: 'number', '_get': x => x.Properties.RegenerationAmount, '_set': (x, v) => x.Properties.RegenerationAmount = v },
                { label: 'Miss Chance', type: 'number', '_get': x => x.Properties.MissChance, '_set': (x, v) => x.Properties.MissChance = v },
                { 
                  label: 'Defense',
                  type: 'multi',
                  fields: ['Stb', 'Cut', 'Imp', 'Pen', 'Shp', 'Brn', 'Cld', 'Acd', 'Ele'],
                  '_get': x => [x.Properties.Defense.Stab, x.Properties.Defense.Cut, x.Properties.Defense.Impact, x.Properties.Defense.Penetration, x.Properties.Defense.Shrapnel, x.Properties.Defense.Burn, x.Properties.Defense.Cold, x.Properties.Defense.Acid, x.Properties.Defense.Electric],
                  '_set': (x, v) => [x.Properties.Defense.Stab, x.Properties.Defense.Cut, x.Properties.Defense.Impact, x.Properties.Defense.Penetration, x.Properties.Defense.Shrapnel, x.Properties.Defense.Burn, x.Properties.Defense.Cold, x.Properties.Defense.Acid, x.Properties.Defense.Electric] = v
                },
              ]
            },
            {
              label: 'Taming',
              type: 'group',
              controls: [
                { label: 'Is Tameable', type: 'checkbox', '_get': x => x.Properties.Taming.IsTameable, '_set': (x, v) => { if (v) { x.Properties.Taming.IsTameable = true; x.Properties.Taming.TamingLevel = 1; } else { x.Properties.Taming.IsTameable = false; x.Properties.Taming.TamingLevel = null; } }},
                { "_if": x => x.Properties.Taming.IsTameable, label: 'Taming Level', type: 'number', '_get': x => x.Properties.Taming.TamingLevel, '_set': (x, v) => x.Properties.Taming.TamingLevel = v },
              ]
            },
            { label: 'Attacks', type: 'list', config: {
                constructor: () => ({
                  Name: '',
                  Damage: {
                    Stab: null,
                    Cut: null,
                    Impact: null,
                    Penetration: null,
                    Shrapnel: null,
                    Burn: null,
                    Cold: null,
                    Acid: null,
                    Electric: null
                  },
                  TotalDamage: null,
                  IsAoE: false
                }),
                controls: [
                  { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
                  { label: 'Damage', type: 'number', '_get': x => x.TotalDamage, '_set': (x, v) => x.TotalDamage = v },
                  {
                    label: 'Composition',
                    type: 'multi',
                    fields: ['Stab', 'Cut', 'Impact', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'],
                    '_get': x => [x.Damage.Stab, x.Damage.Cut, x.Damage.Impact, x.Damage.Penetration, x.Damage.Shrapnel, x.Damage.Burn, x.Damage.Cold, x.Damage.Acid, x.Damage.Electric],
                    '_set': (x, v) => [x.Damage.Stab, x.Damage.Cut, x.Damage.Impact, x.Damage.Penetration, x.Damage.Shrapnel, x.Damage.Burn, x.Damage.Cold, x.Damage.Acid, x.Damage.Electric] = v
                  },
                  { label: 'Is AoE', type: 'checkbox', '_get': x => x.IsAoE, '_set': (x, v) => x.IsAoE = v}
                ]
              }, itemNameFunc: j => `Attack ${j + 1}`, '_get': x => x.Attacks, '_set': (x, v) => x.Attacks = v
            }
          ]
        }, '_get': x => x.Maturities, '_set': (x, v) => x.Maturities = v
      },
      { label: 'Loots', type: 'list', config: {
          constructor: () => ({
            Item: {
              Name: null,
            },
            Maturity: {
              Name: null,
            },
            Frequency: null,
            IsEvent: false,
          }),
          dependencies: ['items'],
          controls: [
            { label: 'Item', type: 'input-validator', validator: (x, d) => d.items.some(y => y.Name === x), '_get': x => x.Item.Name, '_set': (x, v) => x.Item.Name = v },
            { label: 'Least Maturity', type: 'select', options: (_, __, r) => r.Maturities.map(y => y.Name), '_get': x => x.Maturity.Name, '_set': (x, v) => x.Maturity.Name = v },
            { label: 'Frequency', type: 'select', options: _ => ['Always', 'Very often', 'Often', 'Common', 'Uncommon', 'Rare', 'Very rare', 'Extremely rare'], '_get': x => x.Frequency, '_set': (x, v) => x.Frequency = v },
            { label: 'Is Event', type: 'checkbox', '_get': x => x.IsEvent, '_set': (x, v) => x.IsEvent = v },
          ]
      }, '_get': x => x.Loots, '_set': (x, v) => x.Loots = v 
      },
    ]
  }

  function getLowestHpPerLevel(mob) {
    if (mob.Maturities.length === 0) return null;
  
    let lowest = mob.Maturities.reduce((a, b) => {
      // Check if a or b have null or undefined Health or Level
      const aValid = a.Properties.Health != null && a.Properties.Level != null;
      const bValid = b.Properties.Health != null && b.Properties.Level != null;
  
      // If both are valid, compare their Health/Level ratios
      if (aValid && bValid) {
        return a.Properties.Health / a.Properties.Level < b.Properties.Health / b.Properties.Level ? a : b;
      }
  
      // If only a is valid, return a
      if (aValid) return a;
  
      // If only b is valid, return b
      if (bValid) return b;
  
      // If neither are valid, return a (or you could return b, it doesn't matter)
      return a;
    });
  
    // Check if the lowest found has valid Health and Level
    if (!lowest.Properties.Level || !lowest.Properties.Health) return null;
  
    return lowest.Properties.Health / lowest.Properties.Level;
  }

  let viewInfoSection = {
    columns: ['Name', 'Species', 'Type', 'Planet', 'Lowest HP/Lvl', 'Cat 4 Codex'],
    columnWidths: ['1fr', '100px', '100px', '150px', '120px', '100px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Species?.Name ?? 'N/A',
        item.ScanningProfession?.Name === 'Animal Investigator'
          ? 'Animal'
          : item.ScanningProfession?.Name === 'Mutant Investigator'
          ? 'Mutant'
          : item.ScanningProfession?.Name === 'Robot Investigator'
          ? 'Robot'
          : 'N/A',
        item.Planet?.Name ?? 'N/A',
        getLowestHpPerLevel(item)?.toFixed(2) ?? 'N/A',
        item.Species?.Properties?.IsCat4Codex ? 'Yes' : 'No',
      ];
    }
  };

  let tableViewInfo = {
    all: viewInfoSection,
    calypso: viewInfoSection,
    cyrene: viewInfoSection,
    arkadia: viewInfoSection,
    monria: viewInfoSection,
    rocktropia: viewInfoSection,
    toulan: viewInfoSection,
    nextisland: viewInfoSection,
  }
</script>

<EntityViewer
  data={data}
  user={data.session.user}
  tableViewInfo={tableViewInfo}
  navButtonInfo={navButtonInfo}
  editConfig={editConfig}
  propertiesDataFunction={propertiesDataFunction}
  title='Mobs'
  type='Mob'
  basePath='/information/mobs'
  let:object
  let:additional>
  <div class="flex-item">
    <Maturities maturities={object.Maturities} />
  </div>
  <div class="flex-item">
    <Locations mobName={object.Name} mobSpawns={object.Spawns} />
  </div>
  <div class="flex-item">
    <Loots loots={object.Loots} />
  </div>
  <div class="flex-item">
    <Codex baseCost={object.Species?.Properties?.CodexBaseCost} isCat4={object.Species?.Properties?.IsCat4Codex ?? false} />
  </div>
</EntityViewer>