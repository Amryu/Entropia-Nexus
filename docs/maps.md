# Maps

Interactive planet maps with locations, teleporters, and points of interest.

## Route Structure

```
/maps/[[planet]]/[[slug]]
```

- No planet: Planet selection
- Planet only: Full planet map
- With slug: Focused area view

## Available Planets

| Planet | Technical Name | Description |
|--------|----------------|-------------|
| Calypso | Planet_Calypso | Original planet |
| Arkadia | Planet_Arkadia | Mining-focused |
| Cyrene | Planet_Cyrene | Military theme |
| ROCKtropia | Planet_Rocktropia | Music/entertainment |
| Next Island | Planet_NextIsland | Tropical |
| Monria | Moon_Monria | Moon colony |
| Toulan | Planet_Toulan | Middle Eastern theme |
| ARIS | ARIS | Space station |
| Setesh | Setesh | Recent addition |

## Map Features

### Interactive Navigation

- **Pan**: Click and drag to move
- **Zoom**: Scroll wheel or pinch
- **Reset**: Double-click to reset view

### Location Markers

| Type | Icon | Description |
|------|------|-------------|
| Teleporter | TP | Fast travel points |
| Area | Zone | Named regions |
| Estate | Building | Player properties |
| Spawn | Creature | Mob spawn points |

### Marker Interactions

- **Click**: Show location details
- **Hover**: Display name tooltip
- **Context Menu**: Additional options

## Components

### Map.svelte

Main map component:
- SVG-based rendering
- Pan/zoom transforms
- Marker management
- Click handlers

### MapList.svelte

Location list sidebar:
- Searchable list
- Category filters
- Click to navigate

### MapSVGReference.svelte

SVG asset loader for map images.

## Data Sources

### Teleporters

```json
{
  "Id": 1,
  "Name": "Port Atlantis",
  "PlanetId": 1,
  "Longitude": 61400,
  "Latitude": 75800,
  "Altitude": 105
}
```

### Areas

```json
{
  "Id": 1,
  "Name": "Cape Corinth",
  "Type": "LandArea",
  "PlanetId": 1,
  "Longitude": 71000,
  "Latitude": 69000
}
```

### Estates

```json
{
  "Id": 1,
  "Name": "Treasure Island",
  "Type": "LandArea",
  "PlanetId": 1,
  "Longitude": 85000,
  "Latitude": 71000
}
```

## API Endpoints

```
GET /planets           - All planets
GET /planets/:id       - Single planet
GET /teleporters       - All teleporters
GET /areas             - All areas
GET /estates           - Player estates
```

## Coordinate System

Entropia uses a coordinate system:
- **Longitude**: X coordinate (East-West)
- **Latitude**: Y coordinate (North-South)
- **Altitude**: Z coordinate (height)

### Waypoint Format

```
/wp [Planet_TechnicalName,Longitude,Latitude,Altitude,Name]
```

Example:
```
/wp [Planet_Calypso,61400,75800,105,Port Atlantis]
```

### Waypoint Generation

```javascript
import { waypoint } from "$lib/components/Properties.svelte";

const wp = waypoint(
  "Label",
  "Planet_Calypso",
  { Longitude: 61400, Latitude: 75800, Altitude: 105 },
  "Port Atlantis"
);
```

## Map Rendering

### SVG Structure

Maps use SVG for rendering:
- Background image layer
- Marker group layers
- Interactive overlay

### Scaling

Coordinate transformation:
```javascript
// Convert game coordinates to SVG coordinates
const svgX = (longitude - mapBounds.minLon) * scale;
const svgY = (mapBounds.maxLat - latitude) * scale;
```

### Bounds

Each map has defined bounds:
```javascript
{
  minLon: 0,
  maxLon: 100000,
  minLat: 0,
  maxLat: 100000
}
```

## Integration

### Mob Spawns

Link to mob information:
- Show spawn areas on map
- Click to view mob details

### Vendor Locations

Show vendor markers:
- Trade terminals
- NPC shops

### Estate Locations

Player properties:
- Shops
- Land areas
- Apartments

## Future Features

Planned enhancements:

### Hunting Grounds
- Recommended hunting areas
- Mob density heatmaps

### Route Planning
- Teleporter routing
- Distance calculations

### User Markers
- Custom waypoints
- Saved locations
