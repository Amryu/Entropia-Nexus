# Locations System

The Locations system provides a unified data model for all location-related entities in Entropia Universe, including teleporters, NPCs, areas, estates, and more.

## Overview

The system consolidates previously separate location entities into a single unified `Locations` table with extension tables for type-specific data.

### Location Types

| Type | Description |
|------|-------------|
| `Teleporter` | Teleportation points |
| `RevivalPoint` | Revival terminals (respawn locations) |
| `Npc` | Non-player characters |
| `Interactable` | Interactive objects |
| `InstanceEntrance` | Instance/dungeon entrance points |
| `Area` | Map regions (has extension data) |
| `Estate` | Player-owned properties (has extension data) |
| `Outpost` | Outpost locations |
| `Camp` | Camp locations |
| `City` | City locations |
| `WaveEventArea` | Wave-based event areas — stored as `Type='Area'` with `AreaType='WaveEventArea'` |

## Database Schema

### Main Tables

#### Locations
The core table containing all location records.

| Column | Type | Description |
|--------|------|-------------|
| `Id` | SERIAL | Primary key |
| `Name` | TEXT | Location name |
| `Type` | LocationType | Enum: Teleporter, RevivalPoint, Npc, Interactable, InstanceEntrance, Area, Estate, Outpost, Camp, City |
| `Description` | TEXT | Optional description |
| `PlanetId` | INTEGER | FK to Planets |
| `Longitude` | INTEGER | X coordinate |
| `Latitude` | INTEGER | Y coordinate |
| `Altitude` | INTEGER | Z coordinate |
| `ParentLocationId` | INTEGER | Self-reference for hierarchies |
| `TechnicalId` | TEXT | External system identifier |

#### Areas (Extension Table)
Additional data for locations with `Type = 'Area'`.

| Column | Type | Description |
|--------|------|-------------|
| `LocationId` | INTEGER | PK, FK to Locations |
| `Type` | AreaType | Enum: PvpArea, PvpLootArea, MobArea, LandArea, WaveEventArea, ZoneArea, CityArea, EstateArea, EventArea |
| `Shape` | Shape | Enum: Point, Circle, Rectangle, Polygon |
| `Data` | JSONB | Shape-specific data (radius, bounds, polygon points) |

#### Estates (Extension Table)
Additional data for locations with `Type = 'Estate'`.

| Column | Type | Description |
|--------|------|-------------|
| `LocationId` | INTEGER | PK, FK to Locations |
| `Type` | EstateType | Enum: Shop, Apartment |
| `OwnerId` | INTEGER | FK to Users (owner) |
| `ItemTradeAvailable` | BOOLEAN | Whether item trading is enabled |
| `MaxGuests` | INTEGER | Maximum number of guests |

#### LandAreas (Extension Table)
Additional data for Area locations with `AreaType = 'LandArea'`.

| Column | Type | Description |
|--------|------|-------------|
| `LocationId` | INTEGER | PK, FK to Locations |
| `TaxRate` | NUMERIC | Tax rate for the land area |
| `OwnerId` | INTEGER | Owner user ID (references nexus_users) |

#### LandAreaMinerals (Cross Table)
Mineral compositions for LandArea locations.

| Column | Type | Description |
|--------|------|-------------|
| `LocationId` | INTEGER | FK to Locations (LandArea type) |
| `MaterialId` | INTEGER | FK to Materials |
| `Rarity` | MineralRarity | Enum: Common, Uncommon, Rare, Very Rare, Extremely Rare |
| `Notes` | TEXT | Optional notes |

### Facilities System

#### Facilities
Master list of available facilities.

| Column | Type | Description |
|--------|------|-------------|
| `Id` | SERIAL | Primary key |
| `Name` | TEXT | Facility name |
| `Description` | TEXT | Optional description |
| `Icon` | TEXT | Optional icon identifier |

Default facilities: Teleporter, Storage, Trade Terminal, Repair Terminal, Auction, Bank, Technician, Revival Point, Vehicle Extraction, Space Travel

#### LocationFacilities (Junction Table)
Links locations to their available facilities.

| Column | Type | Description |
|--------|------|-------------|
| `LocationId` | INTEGER | FK to Locations |
| `FacilityId` | INTEGER | FK to Facilities |

### Wave Events

#### WaveEventWaves
Wave definitions for WaveEventArea area locations (`Type='Area'`, `AreaType='WaveEventArea'`).

| Column | Type | Description |
|--------|------|-------------|
| `Id` | SERIAL | Primary key |
| `LocationId` | INTEGER | FK to Locations |
| `WaveIndex` | INTEGER | Wave order (1-based) |
| `TimeToComplete` | INTEGER | Time limit in minutes |
| `MobMaturities` | INTEGER[] | Array of MobMaturity IDs |

### Estate Sections

#### EstateSections
Sections within estates (shops, apartments).

| Column | Type | Description |
|--------|------|-------------|
| `Id` | SERIAL | Primary key |
| `LocationId` | INTEGER | FK to Locations (Estate type) |
| `Name` | TEXT | Section name |
| `Description` | TEXT | Optional description |
| `ItemPoints` | INTEGER | Item points capacity |

## API Endpoints

### GET /locations
List all locations with optional filtering.

**Query Parameters:**
| Parameter | Description |
|-----------|-------------|
| `Planet` | Filter by planet name |
| `Planets` | Comma-separated list of planet names |
| `Type` | Filter by location type |
| `Types` | Comma-separated list of types |
| `AreaType` | Filter by area subtype (auto-filters to Area type) |
| `EstateType` | Filter by estate subtype (auto-filters to Estate type) |
| `Facilities` | Comma-separated list of facility names |
| `ParentId` | Filter by parent location ID |

**Response:**
```json
[
  {
    "Id": 123,
    "Name": "Port Atlantis",
    "Properties": {
      "Type": "City",
      "Description": "Main city on Calypso",
      "Coordinates": {
        "Longitude": 61744,
        "Latitude": 75507,
        "Altitude": 115
      }
    },
    "Planet": { "Name": "Calypso" },
    "Facilities": [
      { "Id": 1, "Name": "Teleporter" },
      { "Id": 2, "Name": "Storage" }
    ],
    "Links": { "$Url": "/locations/123" }
  }
]
```

### GET /locations/:idOrName
Get a single location by ID or name.

### GET /facilities
List all available facilities.

### Legacy Endpoints

These endpoints still work but query the unified Locations table:

| Endpoint | Behavior |
|----------|----------|
| `/teleporters` | Returns locations with `Type = 'Teleporter'` |
| `/areas` | Returns locations with `Type = 'Area'` (with extension data) |
| `/shops` | Returns locations with `Type = 'Estate'` and `EstateType = 'Shop'` |
| `/apartments` | Returns locations with `Type = 'Estate'` and `EstateType = 'Apartment'` |

## Frontend Routes

### /information/locations
Main locations wiki page with type filtering.

**URL Patterns:**
- `/information/locations` - All locations
- `/information/locations/teleporter` - Filter by Teleporter type
- `/information/locations/area` - Filter by Area type
- `/information/locations/estate` - Filter by Estate type
- `/information/locations/teleporter/port-atlantis` - View specific location
- `/information/locations?mode=create` - Create new location
- `/information/locations?changeId=123` - View pending change

### Key Components

| Component | Purpose |
|-----------|---------|
| `WikiPage` | Base wiki page layout with edit controls |
| `WikiNavigation` | Sidebar navigation with filters |
| `InlineEdit` | Inline field editing |
| `SearchableSelect` | Searchable dropdown for facilities, parent locations |

## Bot Integration

The Location entity is handled by the bot's UpsertConfigs system.

### Entity Configuration
```javascript
Location: {
  table: "Locations",
  columns: [
    { name: "Name", value: x => x.Name },
    { name: "Type", value: x => x.Properties?.Type },
    { name: "Description", value: x => x.Properties?.Description },
    { name: "PlanetId", value: async (x, c) => ... },
    { name: "Longitude", value: x => x.Properties?.Coordinates?.Longitude },
    { name: "Latitude", value: x => x.Properties?.Coordinates?.Latitude },
    { name: "Altitude", value: x => x.Properties?.Coordinates?.Altitude },
    { name: "TechnicalId", value: x => x.Properties?.TechnicalId },
    { name: "ParentLocationId", value: async (x, c) => ... }
  ],
  relationChangeFunc: async (client, id, x) => {
    await applyLocationFacilitiesChanges(client, id, x.Facilities || []);
    await applyLocationExtensionChanges(client, id, x);
  }
}
```

### Relation Functions

- `applyLocationFacilitiesChanges`: Updates LocationFacilities junction table
- `applyLocationExtensionChanges`: Updates Areas/Estates extension tables based on type
- `applyWaveEventWavesChanges`: Updates WaveEventWaves for WaveEventArea type
- `applyEstateSectionsChanges`: Updates EstateSections for Estate type

## Search Integration

Locations are included in the global search with offset `8000000000`.

The SubType in search results shows the location type (Teleporter, Area, Estate, etc.).

## JSON Schema

The Location entity schema is defined in `common/schemas/Location.js`.

Key schema properties:
- `Properties.Type` - LocationType enum
- `Properties.AreaType` - For Area type locations
- `Properties.EstateType` - For Estate type locations
- `Properties.Shape` - For Area type (Point, Circle, Rectangle, Polygon)
- `Facilities[]` - Array of facility references
- `Sections[]` - For Estate type (estate sections)
- `Waves[]` - For WaveEventArea area type (wave definitions, at body level)

## Migration Notes

The locations system was created by consolidating:
- Teleporters table -> Locations (Type='Teleporter')
- NPCs table -> Locations (Type='Npc')
- Interactables table -> Locations (Type='Interactable')
- Areas table -> Locations (Type='Area') + Areas extension
- Estates table -> Locations (Type='Estate') + Estates extension

The old tables were dropped after migration. The Areas and Estates tables were converted to extension tables that hold type-specific data.

Foreign key references were updated:
- `MobSpawns.AreaId` -> `MobSpawns.LocationId`
- `MobSpawnMaturities.AreaId` -> `MobSpawnMaturities.LocationId`
- `EstateSections.EstateId` -> `EstateSections.LocationId`
