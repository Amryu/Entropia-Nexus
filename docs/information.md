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

## Mobs (`/information/mobs/`)

Creature information including spawns, loot, and maturities.

### Route
```
/information/mobs/[[slug]]/[[discard]]
```

### Data Structure

```json
{
  "Id": 1,
  "Name": "Atrox",
  "Species": "Atrox",
  "Planet": {
    "Id": 1,
    "Name": "Calypso"
  },
  "Maturities": [
    {
      "Id": 101,
      "Name": "Young",
      "Level": 10,
      "Health": 100,
      "DamageTypes": ["Cut", "Impact"],
      "Loot": [...]
    }
  ],
  "Spawns": [
    {
      "AreaId": 50,
      "AreaName": "Cape Corinth",
      "Density": "High"
    }
  ]
}
```

### Properties

| Field | Description |
|-------|-------------|
| Name | Creature name |
| Species | Species classification |
| Planet | Native planet |
| Maturities | Growth stages with stats |
| Spawns | Spawn locations |

### Maturity Data

| Field | Description |
|-------|-------------|
| Name | Maturity level (Young, Mature, etc.) |
| Level | Creature level |
| Health | Hit points |
| DamageTypes | Attack damage types |
| Loot | Drop table |

### Spawn Data

| Field | Description |
|-------|-------------|
| AreaId | Location reference |
| AreaName | Named area |
| Density | Spawn density |
| Coordinates | Optional coordinates |

### API Endpoints

```
GET /mobs              - All mobs
GET /mobs/:id          - Single mob
GET /mobmaturities     - All maturities
GET /mobspawns         - Spawn locations
GET /mobloots          - Loot tables
GET /mobspecies        - Species list
```

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

## Future Content

Planned additions (see `docs/missions.md`):

### Missions
- Mission chains
- Objectives
- Rewards
- NPCs

### Events
- Seasonal events
- Event rewards
- Historical data
