# Information Pages

Reference data for Entropia Universe game mechanics and content.

## Professions (`/information/professions/`)

Character profession skill trees.

### Route
```
/information/professions/[[slug]]
```

### Data Structure

```json
{
  "Id": 1,
  "Name": "Laser Sniper (Hit)",
  "Category": "Combat",
  "Skills": [
    {
      "SkillId": 101,
      "Name": "Laser Weaponry Technology",
      "Contribution": 0.25
    }
  ]
}
```

### Properties

| Field | Description |
|-------|-------------|
| Name | Profession name |
| Category | Combat, Mining, Crafting, etc. |
| Skills | Contributing skills with weights |
| MaxLevel | Maximum profession level |

### API Endpoints

```
GET /professions           - All professions
GET /professions/:id       - Single profession
GET /professioncategories  - Profession categories
```

---

## Skills (`/information/skills/`)

Individual character skills.

### Route
```
/information/skills/[[slug]]
```

### Data Structure

```json
{
  "Id": 101,
  "Name": "Laser Weaponry Technology",
  "Category": "Combat",
  "MaxLevel": 100,
  "ContributesToProfessions": [
    { "ProfessionId": 1, "Contribution": 0.25 }
  ]
}
```

### Properties

| Field | Description |
|-------|-------------|
| Name | Skill name |
| Category | Skill category |
| MaxLevel | Maximum skill level |
| ContributesToProfessions | Profession contributions |

### API Endpoints

```
GET /skills              - All skills
GET /skills/:id          - Single skill
GET /skillcategories     - Skill categories
```

---

## Vendors (`/information/vendors/`)

NPC trade terminal vendors.

### Route
```
/information/vendors/[[slug]]
```

### Data Structure

```json
{
  "Id": 1,
  "Name": "Trade Terminal",
  "Planet": {
    "Id": 1,
    "Name": "Calypso"
  },
  "Location": {
    "Longitude": 12345,
    "Latitude": 67890
  },
  "Offers": [
    {
      "ItemId": 100,
      "ItemName": "Basic Filters",
      "Price": 5.00,
      "Quantity": -1
    }
  ]
}
```

### Properties

| Field | Description |
|-------|-------------|
| Name | Vendor name |
| Planet | Location planet |
| Location | Coordinates |
| Offers | Items for sale |

### API Endpoints

```
GET /vendors           - All vendors
GET /vendors/:id       - Single vendor
GET /vendoroffers      - All vendor offers
```

---

## Mobs Wiki (`/information/mobs/`)

Creature information including spawns, loot, maturities, and codex calculator. Uses Wikipedia-style layout with floating infobox.

### Route
```
/information/mobs/[[slug]]
```

### Layout Structure

Wikipedia-style layout with:
- **Floating Infobox** (right side): Icon, name, type badges, quick stats, skills, damage breakdown, codex info
- **Article Content** (main area): Description, collapsible data sections

### Data Sections

| Section | Component | Description |
|---------|-----------|-------------|
| Maturities | `MobMaturities.svelte` | Table showing all maturity levels with HP, Level, attacks, defense, taming status |
| Locations | `MobLocations.svelte` | Spawn locations with waypoint copy buttons, density badges, map links |
| Loots | `MobLoots.svelte` | Drop table with item links, maturity requirements, frequency badges |
| Codex Calculator | `MobCodex.svelte` | Interactive calculator for 25 codex ranks with skill rewards |
| Damage Grid | `MobDamageGrid.svelte` | Visual damage type breakdown with colored bars |

### Components

Located in `nexus/src/lib/components/wiki/mobs/`:

#### MobMaturities.svelte
Displays maturity progression table:
- Name, Level, HP, HP/Level ratio
- Boss indicator (Yes/No) - boss maturities appear at the bottom with red background
- Primary/Secondary/Tertiary attacks (damage and type)
- Defense value, Tameable status

Note: Boss maturities are excluded from tier 1 property calculations (HP range, Level range, HP/Level).

#### MobLocations.svelte
Displays spawn locations:
- Maturities available at each spawn
- Other mobs sharing the spawn
- Waypoint button (click to copy `/wp` command)
- Density badge (Low/Medium/High with colored backgrounds)
- Map link to view spawn on interactive map

#### MobLoots.svelte
Displays loot drops:
- Item name with link to item page
- Lowest maturity that drops the item
- Event indicator (for seasonal drops)
- Frequency badge (Always → Extremely rare)
- Sorted by frequency (most common first)

#### MobCodex.svelte
Interactive codex calculator:
- 25 rank grid with PED costs
- Rank selection shows skill rewards
- Category 1/2/3 skill rotation per rank
- Category 4 bonus skills on ranks 5, 15, 25 (MobLooter type)
- Asteroid codex has different skill set

#### MobDamageGrid.svelte
Damage type visualization:
- 9 damage types with unique colors
- Horizontal bars showing percentage
- Used in infobox for attack/defense breakdown

### Infobox Stats

| Stat | Description |
|------|-------------|
| HP/Level | Average HP per level across non-boss maturities |
| Level Range | Min-max level from non-boss maturities |
| HP Range | Min-max HP from non-boss maturities |
| Species | Mob species name |
| Planet | Native planet |
| Type | Animal, Mutant, Robot, Asteroid |
| Attack Speed | Attack interval |
| Attack Range | Attack distance |
| Aggro Range | Detection range |
| Sweatable | Whether mob drops vibrant sweat |

### Skills Section

Links to profession pages for:
- Defense skill (e.g., Evader)
- Scanning skill (e.g., Animal Investigator)
- Looting skill (e.g., Animal Looter)

### Badge Styling

Frequency badges use `badge-subtle` class for visibility:
- `badge-freq-always` - Green
- `badge-freq-veryoften` - Teal
- `badge-freq-often` - Blue
- `badge-freq-common` - Light blue
- `badge-freq-uncommon` - Yellow
- `badge-freq-rare` - Orange
- `badge-freq-veryrare` - Red
- `badge-freq-extremelyrare` - Purple

Density badges:
- `badge-density-low` - Blue
- `badge-density-medium` - Yellow
- `badge-density-high` - Green

### API Endpoints

```
GET /mobs              - All mobs with related data
GET /mobs/:id          - Single mob
GET /mobmaturities     - All maturities
GET /mobspawns         - Spawn locations with maturity mappings
GET /mobloots          - Loot tables with item data
GET /mobspecies        - Species list
```

### Data Loader

The page loader (`+page.js`) performs:
1. Fetches all mobs with `Maturities`, `Spawns`, `Loots` expanded
2. Groups mobs by planet for sidebar navigation
3. Resolves item links for loot items (weapons, materials, armor, etc.)
4. Calculates HP/Level stats, level/HP ranges

---

## Common Features

### Planet Filtering

All information pages support planet filtering:
- Calypso
- Arkadia
- Cyrene
- ROCKtropia
- Next Island
- Monria
- Toulan

### Search

Search by name across all entries.

### Waypoints

Location data includes waypoint generation:

```javascript
import { waypoint } from "$lib/components/Properties.svelte";

// Generate /wp command
const wp = waypoint(
  "Location",
  "Planet_Calypso",
  { Longitude: 12345, Latitude: 67890 },
  "Location Name"
);
```

### Related Content

Cross-references between:
- Skills ↔ Professions
- Mobs ↔ Loot items
- Vendors ↔ Items
- Spawns ↔ Map areas

## Components

### EntityViewer

Standard detail view with:
- Property panels
- Related data sections
- Navigation links

### BrowseList

List view with:
- Category filters
- Search
- Planet filter
- Sortable columns

### Properties

Property display component supporting:
- Text values
- Links
- Waypoint buttons
- Nested objects

---

## Missions (`/information/missions/`)

Mission information including chains, objectives, rewards, and dependencies. See `docs/missions.md` for full documentation.

### Route
```
/information/missions/[[slug]]
```

Query parameters:
- `?view=chains` - Toggle mission chains view
- `?mode=create` - Create new mission/chain
- `?changeId=<id>` - View pending change

### Layout Structure

Wikipedia-style layout with:
- **Sidebar** (left): Planet filters, missions/chains toggle, searchable list
- **Floating Infobox** (right): Type, planet, chain, stats summary
- **Article Content** (main): Description, steps, rewards, dependencies

### Data Sections

| Section | Description |
|---------|-------------|
| Chain Preview | Shows `-2..+2` missions around current in chain |
| Steps & Objectives | Mission steps with typed objectives |
| Rewards | Items, skills, and special unlocks |
| Dependencies | Prerequisites and missions unlocked |

### Objective Types

| Type | Description |
|------|-------------|
| Dialog | Talk to NPC with optional dialog text |
| KillCount | Kill specific number of creatures |
| KillCycle | Kill creatures to cycle PED value |
| Explore | Visit specific coordinates |
| Interact | Interact with location |
| HandIn | Deliver items to NPC |

### Components

Located in `nexus/src/lib/components/wiki/missions/`:

| Component | Description |
|-----------|-------------|
| `MissionStepsEditor.svelte` | Full CRUD for steps and objectives |
| `MissionRewardsEditor.svelte` | Items, skills, unlocks editing |
| `ChainEditorDialog.svelte` | Chain creation/editing modal |

### API Endpoints

```
GET /missions              - All missions
GET /missions?planetId=<id> - Filter by planet
GET /missions/:idOrName    - Mission with steps, rewards, dependencies
GET /missions/:id/graph    - Dependency graph

GET /missionchains         - All chains
GET /missionchains/:id     - Chain with missions and graph
GET /missionchains/:id/graph - Chain dependency graph
```

---

## Future Content

Planned additions:

### Events
- Seasonal events
- Event rewards
- Event-type missions
- Historical data
