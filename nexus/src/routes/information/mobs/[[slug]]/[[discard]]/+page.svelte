<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Codex from './Codex.svelte';
  import Loots from './Loots.svelte';
  import Maturities from './Maturities.svelte';
  import Locations from './Locations.svelte';

  export let data;

  const DEFAULT_SPAWN_RADIUS = 100;

  const navButtonInfo = [
    {
      Label: 'Cly',
      Title: 'Calypso',
      Type: 'calypso',
      IsRoute: false
    },
    {
      Label: 'Ars',
      Title: 'ARIS',
      Type: 'aris',
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
        Impact: attack.Damage.Impact || 0,
        Cut: attack.Damage.Cut || 0,
        Stab: attack.Damage.Stab || 0,
        Penetration: attack.Damage.Penetration || 0,
        Shrapnel: attack.Damage.Shrapnel || 0,
        Burn: attack.Damage.Burn || 0,
        Cold: attack.Damage.Cold || 0,
        Acid: attack.Damage.Acid || 0,
        Electric: attack.Damage.Electric || 0,
      }
    }).filter(x => x != null);

    if (attackSpreads.length === 0) {
      // Check if the attack exists at all (even without damage values)
      const hasAttack = mob.Maturities.some(x => x.Attacks?.some(y => y.Name === name));
      if (hasAttack) {
        // Return zero spread if attack exists but has no valid damage data
        return {
          Impact: 0,
          Cut: 0,
          Stab: 0,
          Penetration: 0,
          Shrapnel: 0,
          Burn: 0,
          Cold: 0,
          Acid: 0,
          Electric: 0,
        };
      }
      return null;
    }

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
                { label: 'Health', type: 'number', '_get': x => x.Properties.Health, '_set': (x, v) => { 
                  x.Properties.Health = v;
                  // Automatically update Stamina to be Health / 10
                  if (v != null && !isNaN(v)) {
                    x.Properties.Attributes.Stamina = Math.round(v / 10);
                  }
                }},
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
                initialize: (newItem, dependencies, root, currentIndex, parentArray, parentObject) => {
                  // Set default name based on attack position
                  const attackNames = ['Primary', 'Secondary', 'Tertiary', 'Quaternary', 'Quinary', 'Senary'];
                  if (currentIndex < attackNames.length) {
                    newItem.Name = attackNames[currentIndex];
                  } else {
                    newItem.Name = `Attack ${currentIndex + 1}`;
                  }
                  
                  // parentObject is the current maturity being edited
                  // currentIndex is the position of the new attack
                  // Find the index of the current maturity in the mob's maturities
                  const currentMaturityIndex = root.Maturities?.findIndex(maturity => maturity === parentObject) ?? -1;
                  
                  // Look for previous maturities that have an attack at the same index
                  for (let i = currentMaturityIndex - 1; i >= 0; i--) {
                    const previousMaturity = root.Maturities[i];
                    if (previousMaturity.Attacks && previousMaturity.Attacks[currentIndex]) {
                      const sourceAttack = previousMaturity.Attacks[currentIndex];
                      
                      // Copy properties from the source attack, but keep the default name unless source has a custom name
                      if (sourceAttack.Name && !attackNames.includes(sourceAttack.Name) && !sourceAttack.Name.startsWith('Attack ')) {
                        newItem.Name = sourceAttack.Name;
                      }
                      newItem.TotalDamage = sourceAttack.TotalDamage;
                      newItem.IsAoE = sourceAttack.IsAoE || false;
                      
                      // Copy damage composition
                      if (sourceAttack.Damage) {
                        newItem.Damage = {
                          Stab: sourceAttack.Damage.Stab,
                          Cut: sourceAttack.Damage.Cut,
                          Impact: sourceAttack.Damage.Impact,
                          Penetration: sourceAttack.Damage.Penetration,
                          Shrapnel: sourceAttack.Damage.Shrapnel,
                          Burn: sourceAttack.Damage.Burn,
                          Cold: sourceAttack.Damage.Cold,
                          Acid: sourceAttack.Damage.Acid,
                          Electric: sourceAttack.Damage.Electric
                        };
                      }
                      
                      // Found a source attack, stop looking
                      break;
                    }
                  }
                },
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
        }, itemNameFunc: j => `Maturity ${j + 1}`, '_get': x => x.Maturities, '_set': (x, v) => x.Maturities = v
      },
      { label: 'Spawns', type: 'list', config: {
          constructor: () => ({
            Properties: {
              Density: 2,
              IsShared: false,
              IsEvent: false,
              Shape: 'Point',
              Data: {
                x: 0,
                y: 0,
                radius: DEFAULT_SPAWN_RADIUS
              },
              Coordinates: {
                Altitude: 0
              }
            },
            Maturities: [],
          }),
          dependencies: ['mobs'],
          controls: [
            {
              label: 'General',
              type: 'group',
              controls: [
                { label: 'Shape', type: 'select', options: _ => ['Point', 'Circle', 'Rectangle', 'Polygon'], '_get': x => x.Properties.Shape, '_set': (x, v) => x.Properties.Shape = v },
                { label: 'Density', type: 'select', options: _ => ['Low', 'Medium', 'High'], '_get': x => {
                  // Map numeric density (1,2,3) to string labels
                  if (x.Properties.Density === 1 || x.Properties.Density === '1') return 'Low';
                  if (x.Properties.Density === 2 || x.Properties.Density === '2') return 'Medium';
                  if (x.Properties.Density === 3 || x.Properties.Density === '3') return 'High';
                  return x.Properties.Density; // Return as-is if already a string
                }, '_set': (x, v) => {
                  // Map string labels back to numeric values
                  if (v === 'Low') x.Properties.Density = 1;
                  else if (v === 'Medium') x.Properties.Density = 2;
                  else if (v === 'High') x.Properties.Density = 3;
                  else x.Properties.Density = v;
                }},
                { label: 'Is Shared', type: 'checkbox', '_get': x => x.Properties.IsShared, '_set': (x, v) => x.Properties.IsShared = v },
                { label: 'Is Event', type: 'checkbox', '_get': x => x.Properties.IsEvent, '_set': (x, v) => x.Properties.IsEvent = v },
              ]
            },
            {
              label: 'Coordinates',
              type: 'group',
              controls: [
                { "_if": x => {
                  // Auto-convert Circle with default radius to Point first
                  if (x.Properties.Shape === 'Circle') {
                    try {
                      const dataStr = typeof x.Properties.Data === 'string' ? x.Properties.Data : JSON.stringify(x.Properties.Data || {});
                      const data = JSON.parse(dataStr);
                      if (data.radius === DEFAULT_SPAWN_RADIUS) {
                        x.Properties.Shape = 'Point';
                      }
                    } catch (e) {
                      // If data is malformed, keep as Circle
                    }
                  }
                  return x.Properties.Shape === 'Point';
                }, label: '(Paste Waypoint)', type: 'waypoint', '_get': x => {
                  try {
                    // Handle Data as either string or object
                    const dataStr = typeof x.Properties.Data === 'string' ? x.Properties.Data : JSON.stringify(x.Properties.Data || {});
                    const data = JSON.parse(dataStr);
                    
                    // Use Properties.Coordinates.Altitude for altitude storage
                    return [data.x || 0, data.y || 0, x.Properties.Coordinates?.Altitude || 0];
                  } catch (e) {
                    return [0, 0, x.Properties.Coordinates?.Altitude || 0];
                  }
                }, '_set': (x, v) => { 
                  if (v && v.length >= 3) { 
                    try {
                      // Always parse existing data first, handle as string
                      const dataStr = typeof x.Properties.Data === 'string' ? x.Properties.Data : JSON.stringify(x.Properties.Data || {});
                      let data = JSON.parse(dataStr);
                      data.x = parseFloat(v[0]) || 0;
                      data.y = parseFloat(v[1]) || 0;
                      if (!data.radius) data.radius = DEFAULT_SPAWN_RADIUS;
                      x.Properties.Data = JSON.stringify(data);
                      
                      // Store altitude in Coordinates object
                      if (!x.Properties.Coordinates) x.Properties.Coordinates = {};
                      x.Properties.Coordinates.Altitude = parseFloat(v[2]) || 0;
                      
                      // Auto-change shape to Point if radius is exactly the default
                      if (data.radius === DEFAULT_SPAWN_RADIUS) {
                        x.Properties.Shape = 'Point';
                      }
                    } catch (e) {
                      x.Properties.Data = JSON.stringify({
                        x: parseFloat(v[0]) || 0,
                        y: parseFloat(v[1]) || 0,
                        radius: DEFAULT_SPAWN_RADIUS
                      });
                      if (!x.Properties.Coordinates) x.Properties.Coordinates = {};
                      x.Properties.Coordinates.Altitude = parseFloat(v[2]) || 0;
                      x.Properties.Shape = 'Point';
                    }
                  } 
                }},
                { "_if": x => x.Properties.Shape !== 'Point', label: 'Shape Data', type: 'textarea', '_get': x => {
                  // Ensure Data is returned as a string for textarea
                  return typeof x.Properties.Data === 'string' ? x.Properties.Data : JSON.stringify(x.Properties.Data || {});
                }, '_set': (x, v) => x.Properties.Data = v },
                { "_if": x => x.Properties.Shape !== 'Point', label: 'Altitude', type: 'number', '_get': x => x.Properties.Coordinates?.Altitude || 0, '_set': (x, v) => { if (!x.Properties.Coordinates) x.Properties.Coordinates = {}; x.Properties.Coordinates.Altitude = parseFloat(v) || 0; } },
              ]
            },
            { label: 'Maturities', type: 'list', config: {
                constructor: () => ({
                  IsRare: false,
                  Maturity: {
                    Name: null,
                    Mob: {
                      Name: '',
                    }
                  }
                }),
                initialize: (newItem, dependencies, root, currentIndex, parentArray, parentObject) => {
                  // Set the mob name to the current mob by default
                  if (root && root.Name) {
                    newItem.Maturity.Mob.Name = root.Name;
                  }
                },
                dependencies: ['mobs'],
                controls: [
                  { label: 'Mob', type: 'select', options: (_, d, r) => ['', r.Name, ...d.mobs.filter(m => m.Name !== r.Name).map(m => m.Name)], '_get': x => {
                    // Now using the API-matching structure: Maturity.Mob.Name
                    return x.Maturity?.Mob?.Name;
                  }, '_set': (x, v) => { 
                    if (!x.Maturity) x.Maturity = {};
                    if (!x.Maturity.Mob) x.Maturity.Mob = {};
                    x.Maturity.Mob.Name = v; 
                  }, style: (x, _, r) => {
                    const mobName = x.Maturity?.Mob?.Name;
                    return mobName && mobName !== r.Name ? 'background-color: #e3f2fd;' : '';
                  }},
                  { label: 'Maturity', type: 'select', options: (x, d, r) => {
                    const selectedMobName = x.Maturity?.Mob?.Name || r.Name;
                    if (selectedMobName === r.Name) {
                      return r.Maturities ? r.Maturities.map(y => y.Name) : [];
                    } else {
                      const selectedMob = d.mobs.find(m => m.Name === selectedMobName);
                      return selectedMob && selectedMob.Maturities ? selectedMob.Maturities.map(y => y.Name) : [];
                    }
                  }, '_get': x => x.Maturity?.Name, '_set': (x, v) => { if (!x.Maturity) x.Maturity = {}; x.Maturity.Name = v; } },
                  { label: 'Is Rare', type: 'checkbox', '_get': x => x.IsRare, '_set': (x, v) => x.IsRare = v },
                ]
              }, itemNameFunc: j => `Maturity ${j + 1}`, '_get': x => x.Maturities, '_set': (x, v) => x.Maturities = v
            }
          ]
        }, itemNameFunc: j => `Spawn ${j + 1}`, '_get': x => x.Spawns ?? [], '_set': (x, v) => x.Spawns = v
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
        }, itemNameFunc: j => `Loot ${j + 1}`, '_get': x => x.Loots, '_set': (x, v) => x.Loots = v 
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
    aris: viewInfoSection,
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