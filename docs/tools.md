# Tools

Player utility tools for Entropia Universe.

## Loadout Calculator

A comprehensive equipment planning tool for calculating combat effectiveness and costs.

### Route

```
/tools/loadouts
```

### Features

- **Weapon Configuration**: Select weapons with all attachment slots
- **Armor Building**: Full armor set with individual piece customization
- **Cost Analysis**: Calculate markup costs for entire loadout
- **DPS/Economy**: Damage per second and cost efficiency metrics
- **Save/Load**: Local storage for loadout management
- **Compare Mode**: Side-by-side loadout comparison

### Equipment Slots

#### Weapon Configuration

| Slot | Description |
|------|-------------|
| Weapon | Primary weapon selection |
| Amplifier | Damage/range amplifier |
| Scope | Zoom/accuracy scope |
| Sight | Laser sight |
| Absorber | Recoil absorber |

#### Weapon Enhancers

| Type | Max | Effect |
|------|-----|--------|
| Damage | 10 | Increased damage output |
| Accuracy | 10 | Better hit chance |
| Range | 10 | Extended range |
| Economy | 10 | Reduced decay |
| Skill Mod | 10 | Skill gain bonus |

#### Armor Slots

| Slot | Description |
|------|-------------|
| Head | Helmet |
| Torso | Chest piece |
| Arms | Arm guards |
| Hands | Gloves |
| Legs | Leg armor |
| Shins | Shin guards |
| Feet | Boots |

Each armor slot supports:
- Individual armor piece selection
- Armor plating attachment
- Tier level

#### Armor Enhancers

| Type | Max | Effect |
|------|-----|--------|
| Defense | 10 | Protection bonus |
| Durability | 10 | Reduced decay |

#### Additional Equipment

| Slot | Description |
|------|-------------|
| Clothing | Clothing with buff effects |
| Pet | Active pet with skills |
| Stimulants | Active buff consumables |

### Loadout Data Structure

```javascript
{
  Name: "My Loadout",
  Gear: {
    Weapon: {
      Item: null,           // Selected weapon
      Amplifier: null,      // Amp item
      Scope: null,          // Scope item
      Sight: null,          // Sight item
      Absorber: null,       // Absorber item
      Tier: 0,              // Weapon tier
      Enhancers: {
        Damage: 0,
        Accuracy: 0,
        Range: 0,
        Economy: 0,
        SkillMod: 0
      }
    },
    Armor: {
      Set: null,            // Armor set (optional)
      Pieces: {
        Head: { Item: null, Plating: null, Tier: 0 },
        Torso: { Item: null, Plating: null, Tier: 0 },
        Arms: { Item: null, Plating: null, Tier: 0 },
        Hands: { Item: null, Plating: null, Tier: 0 },
        Legs: { Item: null, Plating: null, Tier: 0 },
        Shins: { Item: null, Plating: null, Tier: 0 },
        Feet: { Item: null, Plating: null, Tier: 0 }
      },
      Enhancers: {
        Defense: 0,
        Durability: 0
      }
    },
    Clothing: [],           // Clothing items with buffs
    Pet: null,              // Active pet
    Stimulants: []          // Active consumables
  },
  Markup: {
    Weapon: 100,
    Ammo: 100,
    Amplifier: 100,
    Absorber: 100,
    Scope: 100,
    Sight: 100,
    Armor: 100,
    Plating: 100,
    // ... per-slot markup overrides
  }
}
```

### Calculations

Calculations are performed in `nexus/src/lib/utils/loadoutCalculations.js`:

#### Weapon Stats

- **DPS**: Damage per second based on weapon stats and enhancers
- **DPP**: Damage per PED (economy)
- **Range**: Effective range with scope/enhancers
- **Accuracy**: Hit chance calculation

#### Armor Stats

- **Protection**: Total damage reduction
- **Durability**: Armor decay rate
- **Coverage**: Body part protection

#### Cost Analysis

- **TT Cost**: Base trade terminal value
- **Markup Cost**: Total cost with player markup
- **Decay Cost**: Expected decay per hour/session

### Data Sources

Items fetched from public API on page load:

```javascript
data.additional = {
  weapons,              // All weapons
  weaponamplifiers,     // Amps and matrices
  weaponvisionattachments, // Scopes and sights
  absorbers,            // Recoil absorbers
  armorsets,            // Armor sets
  armors,               // Individual armor pieces
  armorplatings,        // Armor plates
  enhancers,            // All enhancer types
  clothing,             // Clothing with effects
  pets,                 // Pets with skills
  stimulants            // Buff consumables
}
```

### Components

```
nexus/src/routes/tools/loadouts/
└── +page.svelte        - Main loadout calculator

nexus/src/lib/components/
├── ItemPicker.svelte   - Item selection modal
└── LoadoutList.svelte  - Saved loadout list

nexus/src/lib/utils/
└── loadoutCalculations.js - Stat calculation functions
```

### Local Storage

Loadouts are saved to browser local storage:

```javascript
// Key: 'loadouts'
// Value: JSON array of loadout objects
[
  { Name: "PvP Setup", Gear: {...}, Markup: {...} },
  { Name: "Hunting", Gear: {...}, Markup: {...} }
]
```

### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| onlyShowReasonableAmplifiers | true | Filter out over-amp options |
| overampCap | 10 | Maximum over-amp level to show |

### Item Filtering

Weapons are filtered to exclude:
- Attached weapons (turrets)
- Stationary weapons (vehicles)

Amplifiers are split into:
- Standard amplifiers
- Matrices (separate category)

### Compare Mode

Compare mode allows side-by-side comparison of two loadouts:
- Toggle with compare mode button
- Select second loadout to compare
- Highlights differences in stats

---

## Future Tools

Planned tools (not yet implemented):

### Crafting Calculator
- Blueprint selection
- Material requirements
- Success rate estimation
- Cost/profit analysis

### Mining Calculator
- Finder/amp combinations
- Expected returns
- Decay calculations

### Skill Planner
- Profession progress tracking
- Skill point allocation
- Training recommendations
