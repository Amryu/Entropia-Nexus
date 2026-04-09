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

## Gear Advisor

A collection of small gear-related calculators.

### Route

```
/tools/gear-advisor
/tools/gear-advisor/armor-vs-mob
/tools/gear-advisor/weapon-profitability
```

### Sub-tools

#### Armor vs Mob

Rank armor sets against a target mob's damage composition (or vice versa). Computes mitigation, damage taken, and decay.

#### (L) Weapon Profitability

Evaluate whether an (L) weapon's efficiency advantage generates enough extra TT returns over its lifetime to justify the markup premium paid.

**Game Mechanics:**
- Efficiency adds linearly: X% efficiency returns X * 0.07% more of cycled PED compared to 0% efficiency
- TT cycling cost = full cost per use at TT rates (weapon decay + attachment decay + ammo)
- Decay premium = per-use cost above TT on decay components only (not ammo)
- UL items have 0 premium (repairable at TT value)

**Key Calculations:**
- `efficiencySavingsPerPED = (eff_comp - eff_base) * 0.07 / 100`
- `netProfitability = efficiencySavings - (comp_premium - base_premium)`
- Break-even markup: maximum MU% where the weapon is still economically viable

**Features:**
- Multiple base weapons (UL or L) with full attachment support
- Multiple (L) comparison weapons
- Import base configs from saved loadouts (including weapon sets)
- Global absorber with conditional application (weapon MU > absorber MU)
- Markup source toggle: Custom / Inventory / In-Game / Exchange
- Three views: List (summary cards), Detail (full breakdown), Table (sortable comparison)
- State persisted to user preferences

---

## Client

Desktop companion app for Entropia Universe that runs alongside the game.

### Route

```
/tools/client
```

### Features

- **OCR Skill Scanner**: Reads the in-game Skills window using computer vision, extracts skill names, ranks, points, and progress bars, then imports to the user's Nexus account
- **In-Game Overlays**: Transparent always-on-top overlays for exchange market, player profiles, search, and scan results
- **Exchange Market**: Browse items, view orders, and place buy/sell offers from an overlay without leaving the game
- **Auto-Updates**: Delta update system — only changed files are downloaded; checks hourly and applies with one click

### Distribution

Built with PyInstaller. Available for Windows and Linux.

- Downloads served from `/static/client/{platform}/`
- Delta updates via `manifest.json` (SHA256 hashes per file)
- Changelog at `/static/client/changelog.json`

### Release Process

1. Update `client/data/changelog.json`
2. Tag: `git tag client-X.Y.Z`
3. Build: `./client/build.sh` (per platform)
4. Upload dist files + zip archive to `/static/client/{platform}/`
5. Upload `changelog.json` to `/static/client/`

### Components & Files

```
client/                     - Python client source
├── build.sh                - PyInstaller build script
├── VERSION                 - Fallback version file
├── data/changelog.json     - Changelog data
├── updater.py              - Delta update system
├── ocr/                    - OCR skill scanning pipeline
├── overlay/                - In-game overlay widgets
└── ui/                     - Main application UI

nexus/src/routes/tools/client/
├── +page.js                - Loads changelog from static
└── +page.svelte            - Client page (features, downloads, changelog)
```

---

## Skills Calculator

Import skill data, calculate profession levels and HP, and optimize skill progression costs.

### Route

```
/tools/skills
```

### Layout

Uses `WikiPage` component with `pageClass="tool-skills"` for consistent layout:
- Desktop: sidebar (280px) + content area
- Mobile (<900px): sidebar as slide-in drawer via `MobileDrawer`
- Breadcrumbs: Tools / Skills Calculator
- Header actions: Import, Export (icon-only on mobile), History & Online/Local toggle (when logged in)
- Shared CSS from `tools.css` (`.sidebar-toggle`, `.sidebar-search`, `.sidebar-item`, `.action-btn`, etc.)

### Features

- **Skill Import**: Import skill data via JSON (supports external kebab-case format and Nexus format)
- **Profession Levels**: Automatic calculation using `Level = Σ(skill_points × weight) / 10000`
- **HP Calculation**: Base 80 + contributions from skills with HPIncrease
- **Interactive Navigation**: Click between skills and professions to explore relationships
- **Online/Local Mode**: Dual storage with auto-import prompt on login
- **Import History**: Track skill changes over time with per-skill deltas
- **Optimizer**: Find cheapest path to target profession level or HP
  - **Target types**: Profession level or HP
  - **Per-skill method toggle**: Codex / Chip / None per skill, with bulk toggle buttons
  - **Skills without codex** are locked to Chip/None only
- **Markup Sources**: Custom, Market (WAP), or Inventory markups for skill implant pricing
  - Market lookup uses `"{SkillName} Skill Implant (L)"` naming convention
  - Warning icon shown for skills missing market data

### Profession Level Formula

```
Level = Σ(skill_points × weight) / 10000
```

Where `weight` is from the ProfessionSkills cross-table. Weights often sum to 100 but not always.

### HP Formula

```
Total HP = 80 + Σ(skill_points / HPIncrease)
```

For each skill where HPIncrease > 0.

### Codex Cost per Skill PED

| Category | Cost Multiplier |
|----------|----------------|
| Cat 1 | 200 PED/PED |
| Cat 2 | 320 PED/PED |
| Cat 3 | 640 PED/PED |
| Cat 4 | 1000 PED/PED |

### Skill Value Conversion API

Skill point ↔ PED conversions are computed server-side to keep the formula secret.

```
POST /api/tools/skills/values

Request:  { skillPointsToPED?: number[], pedToSkillPoints?: number[] }
Response: { skillPointsToPED?: number[], pedToSkillPoints?: number[] }
```

- **Public** endpoint (no auth required)
- **Rate limited**: 60 requests/minute per IP
- **Batch cap**: 200 total conversions per request
- Formula implementation: `nexus/src/lib/server/skillFormula.js` (server-only)
- Client wrappers: `fetchSkillPEDValues()`, `fetchPEDToSkillPoints()`, `fetchAllSkillPEDValues()` in `skillCalculations.js`
- UI uses debounced (400ms) batch fetch with loading shimmer

### Constants

- `CHIP_OUT_LOSS_PERCENT` — Skill extraction loss percentage (unknown, set to 0)

### Optimizer Functions

In `skillCalculations.js`:

- `findCheapestPath(currentSkills, professionSkills, currentLevel, targetLevel, markups, methodOverrides)` — Greedy allocation by cost-efficiency (profession level gained per PED spent)
- `findCheapestHPPath(currentSkills, skillMetadata, currentHP, targetHP, markups, methodOverrides)` — Same greedy approach but optimizes for HP gain (only skills with `HPIncrease > 0`)
- `methodOverrides` object: `{ skillName: 'codex' | 'chip' | 'none' }` — forces method per skill, `'none'` excludes the skill

### Components & Files

```
nexus/src/routes/tools/skills/
└── [[slug]]/
    ├── +page.js            - Page loader (fetches skills/professions from API)
    └── +page.svelte        - Main skills calculator UI (uses WikiPage + tools.css)

nexus/src/routes/tools/
└── tools.css               - Shared tool styles (scoped under .tool-skills)

nexus/src/lib/utils/
├── skillCalculations.js    - Profession level, HP, optimizer functions
├── codexUtils.js           - Codex constants and calculations (shared with MobCodex)
└── skillImportUtils.js     - Import/export format parsing

nexus/src/lib/server/
├── skillsDb.js             - Database operations for user skills
└── skillFormula.js         - Server-only skill↔PED conversion formula

nexus/src/routes/api/tools/skills/
├── +server.js              - GET/PUT user skills
├── values/+server.js       - POST batch skill↔PED conversions
└── imports/
    ├── +server.js          - GET import history
    ├── value-history/+server.js - GET value over time
    └── [id]/deltas/+server.js   - GET per-skill deltas
```

### Database Tables (nexus_users)

- `user_skills` — Current skill values per user (JSONB)
- `skill_imports` — Import history records
- `skill_import_deltas` — Per-skill change tracking

---

## Summary Bar (Skills Calculator)

| Metric | Description |
|--------|-------------|
| HP | Base 80 + skill contributions |
| Total Value | Sum of all skill point values |
| Total Skill Points | Sum of all positive skill point values |
| Unlocks remaining | Profession unlocks not yet reached |
