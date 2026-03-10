# Missions System Documentation

This document describes the Missions feature implementation including UI, routing, data model, API, and bot integration.

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Database Schema | **Complete** | All tables created with audit tracking |
| API Endpoints | **Complete** | Read-only endpoints (no write API) |
| Frontend Pages | **Complete** | Full edit mode support via wiki system |
| Bot Integration | **Complete** | Change processing for Mission and MissionChain entities |
| Data Population | **Pending** | No missions in database yet |

---

## Routes

- **URL**: `/information/missions/[[slug]]`
  - No slug: Sidebar list with filters (main content shows overview)
  - With slug: Mission or chain detail view
  - Query params:
    - `?view=chains` - Switch to mission chains view
    - `?mode=create` - Create new mission/chain
    - `?changeId=<id>` - View pending change

---

## Database Schema

**Database**: `nexus`

### Tables

#### Missions (Core table)
| Column | Type | Description |
|--------|------|-------------|
| Id | SERIAL PK | Auto-increment ID |
| Name | TEXT NOT NULL | Mission name |
| PlanetId | INTEGER FK | Reference to Planets |
| MissionChainId | INTEGER FK | Reference to MissionChains (nullable) |
| Type | MissionType ENUM | 'One-Time', 'Repeatable', 'Recurring' |
| Description | TEXT | Mission description (HTML) |
| CooldownDuration | INTERVAL | Cooldown duration (1 min to 30 days). Only for Recurring type |
| CooldownStartsOn | CooldownStartsOn ENUM | 'Accept' or 'Completion'. Only for Recurring type |
| EventId | INTEGER FK | Optional event association (independent of Type) |

#### MissionChains
| Column | Type | Description |
|--------|------|-------------|
| Id | SERIAL PK | Auto-increment ID |
| Name | TEXT NOT NULL | Chain name |
| PlanetId | INTEGER FK | Reference to Planets (nullable) |
| Type | TEXT | Chain type for UI |
| Description | TEXT | Chain description (HTML) |

#### MissionSteps
| Column | Type | Description |
|--------|------|-------------|
| Id | SERIAL PK | Auto-increment ID |
| MissionId | INTEGER FK | Reference to Missions (CASCADE DELETE) |
| Index | INTEGER NOT NULL | Step order (0-based) |
| Title | TEXT | Step title |
| Description | TEXT | Step description (HTML) |

#### MissionObjectives
| Column | Type | Description |
|--------|------|-------------|
| Id | SERIAL PK | Auto-increment ID |
| StepId | INTEGER FK | Reference to MissionSteps (CASCADE DELETE) |
| Type | TEXT | Objective type enum |
| Payload | JSONB | Type-specific payload data |

**Objective Types and Payloads:**
```json
// Dialog - Talk to NPC
{ "targetLocationId": number, "dialogText": "optional text" }

// KillCount - Kill specific number of mobs
{ "targets": [maturityId, ...], "totalCountRequired": number, "countsPerTarget": { "id": count } }

// KillCycle - Kill mobs to cycle PED value
{ "targets": [maturityId, ...], "pedToCycle": number }

// Explore - Visit coordinates
{ "planetId": number, "longitude": number, "latitude": number, "altitude": number }

// Interact - Interact with location
{ "targetLocationId": number }

// HandIn - Deliver items to NPC
{ "npcLocationId": number, "items": [{ "itemId": number, "quantity": number, "pedValue": number }] }

// Collect - Collect a quantity of an item
{ "itemId": number, "quantity": number }
```

#### MissionRewards
| Column | Type | Description |
|--------|------|-------------|
| Id | SERIAL PK | Auto-increment ID |
| MissionId | INTEGER FK | Reference to Missions (CASCADE DELETE) |
| Items | JSONB | Array of `{ itemId, quantity?, pedValue }` |
| Skills | JSONB | Array of `{ skillItemId, pedValue }` |
| Unlocks | TEXT[] | Free-form unlock descriptions |

#### MissionDependencies
| Column | Type | Description |
|--------|------|-------------|
| MissionId | INTEGER FK | The dependent mission |
| PrerequisiteMissionId | INTEGER FK | Mission that must be completed first |

Composite PK: (MissionId, PrerequisiteMissionId)

#### Supporting Tables
- **Npcs**: NPC locations (Id, Name, Description, PlanetId, coordinates)
- **Interactables**: Interactive objects (Id, Name, Description, PlanetId, coordinates)
- **Events**: Event data for event-type missions (placeholder)

### Unified Locations View

Combines multiple location types with ID offsets:

| Source | ID Offset | Type |
|--------|-----------|------|
| Teleporters | +100000 | 'Teleporter' |
| Areas | +200000 | (stored Type) |
| Estates | +300000 | (stored Type) |
| Npcs | +400000 | 'Npc' |
| Interactables | +500000 | 'Interactable' |

### Audit Tables

All mission tables have `{TableName}_audit` tables with automatic triggers for INSERT/UPDATE/DELETE tracking.

---

## API Endpoints

### Missions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/missions` | List all missions |
| GET | `/missions?planetId=<id>` | Filter by planet |
| GET | `/missions/:idOrName` | Get mission details with steps, rewards, dependencies |
| GET | `/missions/:idOrName/graph` | Get dependency graph (chain or local) |

### Mission Chains

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/missionchains` | List all chains |
| GET | `/missionchains?planetId=<id>` | Filter by planet |
| GET | `/missionchains/:idOrName` | Get chain with missions and graph |
| GET | `/missionchains/:idOrName/graph` | Get chain dependency graph |

### Events

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/events` | List all events (ordered by StartDate desc) |
| GET | `/events/:idOrName` | Get event details |

Events are used to associate missions with in-game events. The Event field is optional and only relevant for Event-type missions.

### Search Integration

Missions and chains are included in global search (`/search`):
- Missions: Type `'Mission'`, ID offset `+6000000000`
- Chains: Type `'MissionChain'`, ID offset `+7000000000`

### Response Formats

**Mission Summary:**
```json
{
  "Id": 1,
  "Name": "Mission Name",
  "Properties": { "Type": "One-Time", "Description": "..." },
  "Planet": { "Name": "Calypso", "Links": { "$Url": "/planets/1" } },
  "MissionChain": { "Name": "Chain Name", "Links": { "$Url": "/missionchains/1" } },
  "Event": { "Id": 5, "Name": "Summer Event", "Links": { "$Url": "/events/5" } },
  "Links": { "$Url": "/missions/1" }
}
```

**Mission Detail** (extends summary):
```json
{
  "Steps": [
    {
      "Id": 1, "Index": 0, "Title": "Step Title", "Description": "...",
      "Objectives": [{ "Id": 1, "Type": "KillCount", "Payload": {...} }]
    }
  ],
  "Rewards": {
    "Items": [{ "itemId": 123, "quantity": 1, "pedValue": 5.00 }],
    "Skills": [{ "skillItemId": 456, "pedValue": 1.50 }],
    "Unlocks": ["Unlocks next mission"]
  },
  "Dependencies": {
    "Prerequisites": [{ "Id": 2, "Name": "Prereq Mission" }],
    "Dependents": [{ "Id": 3, "Name": "Next Mission" }]
  }
}
```

**Graph Response:**
```json
{
  "source": "chain",
  "chainId": 1,
  "rootId": 5,
  "nodes": [{ "Id": 1, "Name": "...", "Type": "...", "PlanetId": 1 }],
  "edges": [{ "FromId": 1, "ToId": 2 }]
}
```

---

## Frontend Implementation

### Files

**Route:** `nexus/src/routes/information/missions/[[slug]]/`
- `+page.svelte` - Main page component (1400+ lines)
- `+page.js` - Data loader

**Components:** `nexus/src/lib/components/wiki/missions/`
- `MissionStepsEditor.svelte` - Steps and objectives editor
- `MissionRewardsEditor.svelte` - Rewards editor (items, skills, unlocks)
- `ChainEditorDialog.svelte` - Chain creation/editing modal
- `MissionMapEmbed.svelte` - Canvas-based mini-map showing objective locations

### Features

**View Mode:**
- Sidebar with planet filters and mission/chain toggle
- Infobox with mission details (type, planet, chain, event, stats)
- Steps with objectives displayed
- Objectives map embed (shows location-based objectives with path lines)
- Rewards grid (items, skills, unlocks)
- Dependencies section (prerequisites and dependents)
- Chain preview showing nearby missions
- Graph dialog for full chain visualization

**Edit Mode:**
- Inline editing for all fields (name, planet, type, description)
- Type selector with options: One-Time, Repeatable, Recurring
- Cooldown configuration for Recurring type (duration: 1 min to 30 days, starts on: Accept/Completion)
- Event assignment via SearchableSelect (optional, for any mission type)
- Chain assignment with validation
- MissionStepsEditor for full CRUD on steps/objectives
- MissionRewardsEditor for items, skills, unlocks
- SearchableSelect for dependencies
- ChainEditorDialog for chain management
- Pending change workflow integration

### Objective Type Editors

| Type | Fields |
|------|--------|
| Dialog | NPC target (SearchableSelect), Dialog text (RichTextEditor) |
| KillCount | Targets (mob maturities), Per-target counts, Total required |
| KillCycle | Targets (mob maturities), PED to cycle |
| Explore | WaypointInput (planet, coordinates) |
| Interact | Target location (SearchableSelect) |
| HandIn | NPC location, Items array with quantity/TT/PED |
| Collect | Item (SearchInput), Quantity |

### MissionMapEmbed Component

The `MissionMapEmbed` component provides a visual overview of mission objective locations on a mini-map.

**Features:**
- Canvas-based rendering with pan and zoom support
- Extracts coordinates from Explore, Dialog, Interact, and HandIn objectives
- Color-coded markers by objective type (green=Dialog, red=KillCount, blue=Explore, etc.)
- Sequential numbering by step index
- Dashed path lines connecting objectives in step order
- Legend showing objective type colors
- "Expand" button to open full map in new tab

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| objectives | Array | [] | Array of objective data with coordinates |
| planet | Object | null | Planet data for map image and bounds |
| showPath | boolean | true | Whether to draw path lines |
| height | number | 280 | Height in pixels |
| title | string | "Mission Objectives" | Section title (empty to hide) |

**Coordinate Extraction:**
- Explore objectives use `longitude`, `latitude` directly from payload
- Dialog/Interact/HandIn objectives look up location coordinates from the locations API by `targetLocationId` or `npcLocationId`

---

## Bot Integration

### Entity Configurations

**Location:** `nexus-bot/changes/entity.js`

**Mission Configuration:**
```javascript
Mission: {
  table: "Missions",
  columns: ["Name", "PlanetId", "MissionChainId", "EventId", "Type", "Description", "CooldownDuration", "CooldownStartsOn"],
  relationChangeFunc: async (client, id, x) => {
    await applyMissionStepsChanges(client, id, x.Steps);
    await applyMissionRewardsChanges(client, id, x.Rewards);
    await applyMissionDependenciesChanges(client, id, x.Dependencies);
  }
}
```

**MissionChain Configuration:**
```javascript
MissionChain: {
  table: "MissionChains",
  columns: ["Name", "PlanetId", "Type", "Description"]
}
```

### Change Handlers

1. **applyMissionStepsChanges** - Manages steps with nested objectives
2. **applyMissionObjectivesChanges** - Manages objectives with JSON payloads
3. **applyMissionRewardsChanges** - Manages rewards (UPSERT pattern)
4. **applyMissionDependenciesChanges** - Manages bidirectional dependencies

### Validation

**validateChainConnectivity** - BFS algorithm to ensure all missions in a chain are connected via dependencies.

### Schemas

| Schema | Location |
|--------|----------|
| Mission | `common/schemas/Mission.js` |
| MissionChain | `common/schemas/MissionChain.js` |

---

## Data Examples

### Mission
```json
{
  "Name": "IFN Challenge: Arret Stage 1",
  "Planet": { "Name": "Calypso" },
  "MissionChain": { "Name": "IFN Challenge: Arret" },
  "Properties": {
    "Type": "One-Time",
    "Description": "Hunt Arret to help the IFN."
  },
  "Steps": [
    {
      "Index": 0,
      "Title": "Report in",
      "Objectives": [
        { "Type": "Dialog", "Payload": { "targetLocationId": 400123 } }
      ]
    },
    {
      "Index": 1,
      "Title": "Hunt Arret",
      "Description": "Any maturity counts.",
      "Objectives": [
        { "Type": "KillCount", "Payload": { "targets": [90011, 90012], "totalCountRequired": 100 } }
      ]
    }
  ],
  "Rewards": {
    "Items": [{ "itemId": 700345, "pedValue": 3.5 }],
    "Skills": [{ "skillItemId": 800123, "pedValue": 1.2 }],
    "Unlocks": ["Unlocks Arret Stage 2"]
  },
  "Dependencies": {
    "Prerequisites": [],
    "Dependents": [{ "Name": "IFN Challenge: Arret Stage 2" }]
  }
}
```

### Mission Chain
```json
{
  "Name": "IFN Challenge: Arret",
  "Planet": { "Name": "Calypso" },
  "Properties": {
    "Type": "Combat",
    "Description": "Complete all stages of the IFN Arret challenge."
  }
}
```

---

## Edge Cases

- **Cross-planet chains**: Each mission has its own planet; dependencies can cross planets
- **Variable kill targets**: Use `countsPerTarget` when exact per-target counts differ
- **Partial TT values**: Store explicitly in `pedValue` or `minPedValue` fields
- **Disconnected chains**: Validation warns but doesn't prevent saving
- **Skills display**: Strip " Skill Implant (L)" suffix in UI, store full item ID

---

## Testing

### Manual Testing
1. Navigate to `/information/missions/`
2. Toggle between Missions and Chains views
3. Filter by planet
4. Create new mission/chain (edit mode)
5. Edit existing mission with steps and rewards
6. Verify pending change workflow

### Database Verification
```sql
-- Check mission tables
SELECT COUNT(*) FROM "Missions";
SELECT COUNT(*) FROM "MissionChains";
SELECT COUNT(*) FROM "MissionSteps";
SELECT COUNT(*) FROM "MissionObjectives";
SELECT COUNT(*) FROM "MissionRewards";
SELECT COUNT(*) FROM "MissionDependencies";
```

---

## Future Enhancements

- [ ] Populate initial mission data from game
- [ ] Add write API endpoints for direct editing
- [ ] Implement events system for event-type missions
- [ ] Add map integration for explore objectives
- [ ] Mission completion tracking (user accounts)
