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

Main canvas map component (view mode):
- Canvas-based rendering
- Pan/zoom transforms
- Marker management
- Click handlers

### MapList.svelte

Location list sidebar (view mode):
- Searchable list
- Category filters
- Click to navigate

### MapSVGReference.svelte

SVG asset loader for map images.

### Shared Map Editor Components (`$lib/components/map-editor/`)

Reusable Leaflet-based editing components used by the public map edit mode. A `MapEditorWorkspace` wrapper owns all shared state and event handlers.

| Component | Description |
|-----------|-------------|
| `MapEditorWorkspace.svelte` | **Wrapper**: 3-column layout + all 17 event handlers + shared state management |
| `MapEditorLeaflet.svelte` | Leaflet CRS.Simple map with draw tools, context menu (clone, waypoint copy) |
| `LocationList.svelte` | Searchable/filterable location sidebar with multi-select |
| `LocationEditor.svelte` | Location property editor with shape controls, parent picker, LandArea fields |
| `MobAreaEditor.svelte` | Mob spawn density and maturity selection editor |
| `ChangesSummary.svelte` | Public mode: submit pending changes via wiki changes API |
| `mapEditorUtils.js` | Shared constants, coordinate transforms, color helpers |

---

## Map Editor Component Reference

### MapEditorWorkspace.svelte

Wrapper that owns the 3-column editor layout, all shared state, and all event handlers.

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `planet` | object\|null | `null` | Planet with `Properties.Map` data |
| `locations` | array | `[]` | All locations (including mob spawn data) |
| `allMobs` | array | `[]` | All mobs for MobAreaEditor |
| `editMode` | boolean | `false` | Enable draw tools and shape editing |
| `loading` | boolean | `false` | Show loading overlay on map |
| `mode` | `'admin'\|'public'` | `'admin'` | Behavioral mode passed to child components |

**Exported bindable state:**
| Binding | Type | Description |
|---------|------|-------------|
| `pendingChanges` | Map | `id → {action, original, modified}` — parent reads for toolbar badges |
| `rightPanel` | string | `'editor'\|'mobEditor'\|<other>` — parent toggles from toolbar |
| `mapComponent` | component | MapEditorLeaflet instance — parent calls `loadPlanetImage()` |
| `changeCount` | number | Derived from `pendingChanges.size` — for toolbar badge |

**Exported method:**
- `reset()` — Clears all internal state: pendingChanges, selectedId, isNewLocation, drawnShapeData, rightPanel, previewShape, mobEditorContext, filteredIds, nextTempId, changeCount

**Slot:**
- `output` — Renders when `rightPanel` is not `'editor'` or `'mobEditor'`. Public passes `ChangesSummary`.

**Internal state (not exported):**
`selectedId`, `isNewLocation`, `drawnShapeData`, `previewShape`, `mobEditorContext`, `filteredLocationIds`, `nextTempId`

**Reactive derivations:**
- `selectedLocation` — resolves `selectedId` from `locations` array or pending adds (with `_isPendingAdd` flag)
- `changeCount` — `pendingChanges.size`

**All 17 consolidated handlers:**
`handleMapSelect`, `handleListSelect`, `handleFilterChange`, `handleDrawCreated`, `handleAddLocation`, `handleEditLocation`, `handleDeleteLocation`, `handleRevertLocation`, `handleRemovePendingAdd`, `handleMassDelete`, `handlePreview`, `handleShapeEdited`, `handleEditMobArea`, `handleMobSave`, `handleMobCancel`, `handleClone`, `offsetShapeData`

**Layout:** 3-column flex — left sidebar (280px, LocationList), center (flex:1, MapEditorLeaflet), right panel (320px, conditional content).

**Usage (dynamic import via `svelte:component`):**
```svelte
<svelte:component this={MapEditorWorkspace}
  planet={currentPlanet} {locations} {allMobs} editMode={true} mode="public"
  bind:pendingChanges={editorPendingChanges}
  bind:rightPanel={editorRightPanel}
  bind:changeCount={editorChangeCount}
>
  <svelte:fragment slot="output">
    <svelte:component this={ChangesSummary}
      pendingChanges={editorPendingChanges} planet={currentPlanet}
      on:clear={() => { editorPendingChanges = new Map(); }} />
  </svelte:fragment>
</svelte:component>
```

**Note:** `bind:this` does not work on `svelte:component` in Svelte 4. The public page resets state through bound props; internal state is destroyed when the component unmounts.

---

### MapEditorLeaflet.svelte

Interactive Leaflet CRS.Simple map for viewing and editing location shapes and points.

**Props:**
| Prop | Type | Description |
|------|------|-------------|
| `planet` | object | Planet data with `Properties.Map.Width/Height/MinX/MinY/MaxX/MaxY` for coordinate transforms |
| `locations` | array | All location objects to display |
| `filteredLocationIds` | Set\|null | Set of visible IDs; null shows all |
| `selectedId` | any | Currently selected location ID |
| `pendingChanges` | Map | `id → {action, original, modified}` for unsaved edits |
| `editMode` | boolean | Enables draw tools and shape editing |
| `previewShape` | object\|null | `{shape, data, center}` for live preview overlay |

**Events:**
| Event | Payload | Description |
|-------|---------|-------------|
| `select` | location ID | User clicked a location layer |
| `drawCreated` | `{shape, data, center, isMarker}` | User drew a new shape with Leaflet Draw |
| `shapeEdited` | `{locId, entropiaData}` | User dragged/edited shape vertices on map |
| `clone` | location object | Right-click context menu "Clone Shape" |

**Exported functions:**
- `loadPlanetImage()` — Loads planet map image, calculates coordinate transforms, initializes Leaflet map
- `panToLocation(loc)` — Animates map view to center on a location

**Visual indicators for pending changes:**
- Green dashed outline: pending add
- Orange dashed outline: pending edit
- Red dashed outline: pending delete
- Cyan dashed outline: preview overlay (live shape data from form)

**Coordinate transforms** (via `buildCoordTransforms` from mapEditorUtils):
- `entropiaToLeaflet(x, y)` → `[lat, lng]` for Leaflet map
- `leafletToEntropia(lat, lng)` → `{x, y}` for Entropia coordinates
- `ratio`: Scale factor between coordinate systems

---

### LocationList.svelte

Left sidebar with searchable, filterable list of locations and multi-select for mass operations.

**Props:**
| Prop | Type | Description |
|------|------|-------------|
| `locations` | array | All available locations |
| `selectedId` | any | Currently selected location ID |
| `pendingChanges` | Map | Pending changes for change state indicators |
| `editMode` | boolean | Enables multi-select mode |
| `mode` | `'admin'\|'public'` | Controls mass-delete behavior |

**Events:**
| Event | Payload | Description |
|-------|---------|-------------|
| `select` | location ID | User clicked a location |
| `filterChange` | Set of location IDs | Filter state changed |
| `massDelete` | Set of location IDs | Multi-select delete (admin: marks for deletion; public: copies info to clipboard) |

**Filtering:** Type filters (Teleporter, Npc, etc.) and area type filters (MobArea, LandArea, etc.) with text search.

---

### LocationEditor.svelte

Right panel form for creating or editing location properties, coordinates, and shape data.

**Props:**
| Prop | Type | Description |
|------|------|-------------|
| `location` | object\|null | Location being edited, or null |
| `isNew` | boolean | True if creating from drawn shape |
| `drawnShapeData` | object\|null | `{shape, data, center, isMarker}` from map drawing |
| `mode` | `'admin'\|'public'` | Controls delete button behavior |
| `allLocations` | array | All locations for parent picker filtering |

**Events:**
| Event | Payload | Description |
|-------|---------|-------------|
| `add` | `{name, locationType, longitude, latitude, altitude, areaType, shape, shapeData, parentLocationName, landAreaOwner, landAreaTaxRate}` | New location form saved |
| `edit` | `{original, modified}` | Existing location edited |
| `delete` | location object | Admin: marks for deletion |
| `revert` | location object | Revert changes to original |
| `removePendingAdd` | location ID | Remove a pending add from changes |
| `editMobArea` | `{location, isNew}` | Open MobAreaEditor |
| `preview` | `{shape, data, center}` or null | Live shape preview on map (debounced 150ms) |

**Shape data controls:**
- **Circle**: Structured inputs for center X, center Y, radius
- **Rectangle**: Structured inputs for origin X, origin Y, width, height
- **Polygon**: Raw JSON textarea for `{vertices: [x1, y1, x2, y2, ...]}` array

**Conditional sections:**
- **Area Type** (areaType dropdown, shape controls): Visible when `locationType === 'Area'`
- **MobArea** ("Edit Mob Spawns" button): Visible when `areaType === 'MobArea'`
- **LandArea** (owner name, tax rate): Visible when `areaType === 'LandArea'`
- **Parent Location** (SearchInput filtered to areas): Always visible for all types
- **Related Entities** (collapsible, read-only): Lazy-fetches missions via `GET /missions?StartLocationId=<id>`

**Admin vs Public delete behavior:**
- Admin: "Mark for Deletion" button dispatches `delete` event
- Public: "Copy Delete Info" copies formatted location details to clipboard
- Pending adds: "Remove" button dispatches `removePendingAdd` event (both modes)

---

### MobAreaEditor.svelte

Full-screen overlay for configuring mob spawns on a MobArea location.

**Props:**
| Prop | Type | Description |
|------|------|-------------|
| `mobs` | array | All mobs from `/mobs` API with embedded `Maturities` arrays |
| `location` | object\|null | Existing MobArea if editing (reads `location.Maturities`) |
| `isNew` | boolean | True if this is a new pending location |

**Events:**
| Event | Payload | Description |
|-------|---------|-------------|
| `save` | `{name, density, maturities: [{maturityId, isRare}]}` | Configuration saved |
| `cancel` | — | Cancelled without saving |

**Features:**
- Search and add mobs from the full mob database
- Select specific maturities per mob (health, level, boss indicators)
- Toggle rare flag per maturity
- Set spawn density (Low/Medium/High)
- Auto-generates name from selected mobs and maturities (e.g., "Atrox - Young/Mature, Sabakuma - Old Alpha")
- Optional name override

**Data flow:** Mob maturity data comes from the `mobs` prop (loaded once from `/mobs` API). No per-mob API calls needed — all maturity data is embedded in the mob objects.

---

### ChangesSummary.svelte

Public-mode right panel showing summary of pending changes with submission interface.

**Props:**
| Prop | Type | Description |
|------|------|-------------|
| `pendingChanges` | Map | Map of pending changes |
| `planet` | object | Current planet for API submissions |

**Events:**
| Event | Payload | Description |
|-------|---------|-------------|
| `clear` | — | Clear all changes |

**Submission:** Submits each change to `POST /api/changes` with `state=Pending` for admin review:
- ADD → `type=Create`, builds entity body matching Location/Area schema
- EDIT → `type=Update`, builds entity body with modified fields
- DELETE → Skipped (info-only)
- Per-change status indicators (pending/submitting/success/error)

---

### mapEditorUtils.js

Shared constants and utility functions.

**Constants:**
- `LOCATION_TYPES`: `['Teleporter', 'Npc', 'Interactable', 'Outpost', 'Camp', 'City', 'WaveEvent', 'RevivalPoint', 'InstanceEntrance', 'Vendor', 'Estate']`
- `AREA_TYPES`: `['MobArea', 'LandArea', 'PvpArea', 'PvpLootArea', 'ZoneArea', 'CityArea', 'EstateArea', 'EventArea']`
- `SHAPES`: `['Circle', 'Rectangle', 'Polygon']`
- `TYPE_COLORS`: Map of type → hex color for map visualization

**Functions:**
| Function | Returns | Description |
|----------|---------|-------------|
| `getTypeColor(type)` | hex string | Color for location/area type |
| `getEffectiveType(loc)` | string | Display type (prefers AreaType for areas) |
| `isArea(loc)` | boolean | True if location has Shape and Data properties |
| `buildCoordTransforms(planet, imgW, imgH)` | `{entropiaToLeaflet, leafletToEntropia, ratio}` | Coordinate transform functions |
| `generateMobAreaName(mobEntries)` | string | Display name from mob/maturity array |

---

## Pending Changes Architecture

Both admin and public pages use a `Map<id, change>` for pending changes:

```javascript
// change structure
{
  action: 'add' | 'edit' | 'delete',
  original: locationObject | null,  // null for adds
  modified: { name, locationType, longitude, latitude, altitude,
              areaType, shape, shapeData, parentLocationName,
              landAreaOwner, landAreaTaxRate, mobData } | null  // null for deletes
}
```

- **Temporary IDs**: New locations use negative numbers (`nextTempId--`)
- **`_isPendingAdd` flag**: Location-like objects built from pending adds include this flag for UI differentiation
- Changes trigger `rebuildLayers()` in MapEditorLeaflet for visual updates

---

## Public Edit Mode

Verified users see an "Edit Mode" button (bottom-right, desktop only) on planet map pages.

### Activation
- Requires: verified user, desktop viewport (>899px), planet loaded
- Dynamically imports editor components (Leaflet) to avoid SSR overhead
- Loads mob data (`/mobs` API) on first activation

### Layout
When active, replaces the canvas view with a full-screen overlay containing:
- **Editor toolbar** (public-owned): Planet label, changes toggle with badge, exit button
- **MapEditorWorkspace** (3-column, `mode="public"`): LocationList | MapEditorLeaflet | right panel

### Right Panel States
| Panel | Trigger | Description |
|-------|---------|-------------|
| `editor` | Default, location selected | LocationEditor form (`mode="public"`) |
| `mobEditor` | "Edit Mob Spawns" button | MobAreaEditor overlay |
| `changes` | Toolbar changes button | ChangesSummary with submit interface |

### Features
- Draw new areas/markers
- Edit existing location shapes (drag vertices)
- Clone shapes via right-click context menu
- Set parent location (SearchInput with area filtering)
- LandArea: set owner name and tax rate
- MobArea: configure mob spawns and maturities
- View related entities (missions) on selected locations
- "Copy Delete Info" copies location details to clipboard (no direct deletion)

### Deactivation
- "Exit Edit Mode" button
- Warns if unsaved changes exist (confirmation dialog)
- Clears all editor state and returns to canvas view

### Submitting Changes
Changes are submitted via the wiki changes API (`POST /api/changes`) with `state=Pending`:
- ADD: Creates new Location/Area change entries for admin review
- EDIT: Creates update change entries for admin review
- DELETE: Info-only (copied to clipboard for admin action)

After successful submission, pending changes are automatically re-fetched from the server so the submitted changes appear as DB pending changes on the map. Admins with the `admin.panel` grant can also "Direct Apply" changes, bypassing the review queue.

### Auto-Save
Location edits are saved locally (to `pendingChanges`) automatically as the user modifies form fields. There is no explicit "Save" button. The "Revert Changes" button undoes local edits for existing locations.

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

## Embed API

The map can be embedded on external websites via iframe. All editing functionality is automatically disabled in embed mode.

### Embed URL

```
https://entropianexus.com/maps/<planet>?embed=1
```

**Query Parameters:**

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `embed` | `1` | — | Activates embed mode (required) |
| `hideSearch` | `1` | `0` | Hide search bar and planet selectors |
| `hidePanel` | `1` | `0` | Hide location detail panel |
| `hideLayers` | `1` | `0` | Hide layer toggle buttons (TP, LA, MA, etc.) |

**Example — minimal embed (map only):**
```html
<iframe
  src="https://entropianexus.com/maps/calypso?embed=1&hideSearch=1&hidePanel=1&hideLayers=1"
  width="800" height="600"
  style="border: none;"
></iframe>
```

**Example — embed with search:**
```html
<iframe
  src="https://entropianexus.com/maps/calypso?embed=1&hidePanel=1"
  width="800" height="600"
  style="border: none;"
></iframe>
```

### postMessage API

All messages use a `nexus:` prefix. The embed communicates with the parent page via `window.postMessage`.

#### Inbound Messages (Parent → Embed)

| Message Type | Payload | Description |
|---|---|---|
| `nexus:panTo` | `{ longitude, latitude }` | Pan map to game coordinates |
| `nexus:focusLocation` | `{ locationId }` | Select location and animate to it |
| `nexus:selectLocation` | `{ locationId }` | Same as `focusLocation` |
| `nexus:setZoom` | `{ zoom }` | Set zoom level (clamped to valid range) |
| `nexus:search` | `{ query }` | Run search, returns `nexus:searchResults` |
| `nexus:setLayers` | `{ layers: { teleporters?, landAreas?, mobAreas?, pvpAreas?, otherAreas? } }` | Set layer visibility |
| `nexus:highlightLocations` | `{ locationIds: number[] }` | Highlight locations (others grayed out) |
| `nexus:clearHighlight` | `{}` | Remove all highlights |
| `nexus:getLocations` | `{}` | Get all locations, returns `nexus:locations` |
| `nexus:getSelectedLocation` | `{}` | Get currently selected location, returns `nexus:selectedLocation` |
| `nexus:setVisibility` | `{ search?, panel?, layers? }` | Show/hide UI elements at runtime (boolean values) |

#### Outbound Messages (Embed → Parent)

| Message Type | Payload | Description |
|---|---|---|
| `nexus:ready` | `{ planet, locationCount }` | Map loaded and ready |
| `nexus:locationSelected` | `{ id, name, type, areaType, coordinates }` | User clicked a location |
| `nexus:locationDeselected` | `{}` | User clicked empty space |
| `nexus:searchResults` | `{ query, results: [{ id, name, type, areaType, coordinates, score }] }` | Response to `nexus:search` |
| `nexus:locations` | `{ locations: [{ id, name, type, areaType, coordinates }] }` | Response to `nexus:getLocations` |
| `nexus:selectedLocation` | `{ location: { id, name, type, areaType, coordinates } \| null }` | Response to `nexus:getSelectedLocation` |

#### JavaScript Example

```javascript
const iframe = document.querySelector('iframe');

// Wait for map to be ready
window.addEventListener('message', (event) => {
  const msg = event.data;
  if (msg.type === 'nexus:ready') {
    console.log(`Map loaded: ${msg.planet} with ${msg.locationCount} locations`);

    // Focus on a specific location
    iframe.contentWindow.postMessage({
      type: 'nexus:focusLocation',
      locationId: 123
    }, '*');
  }

  if (msg.type === 'nexus:locationSelected') {
    console.log('User selected:', msg.location.name);
  }

  if (msg.type === 'nexus:searchResults') {
    console.log('Search results:', msg.results);
  }
});

// Run a search
iframe.contentWindow.postMessage({
  type: 'nexus:search',
  query: 'Fort Victoria'
}, '*');

// Highlight specific locations (others grayed out)
iframe.contentWindow.postMessage({
  type: 'nexus:highlightLocations',
  locationIds: [101, 102, 103]
}, '*');

// Toggle layers
iframe.contentWindow.postMessage({
  type: 'nexus:setLayers',
  layers: { teleporters: true, mobAreas: false, landAreas: true }
}, '*');

// Show/hide UI elements at runtime
iframe.contentWindow.postMessage({
  type: 'nexus:setVisibility',
  search: false,
  panel: true,
  layers: false
}, '*');
```

### Search Scoring

The embed uses the same scoring algorithm as the main site. Scores range from 0 (no match) to 1000 (exact match):

| Score Range | Match Type |
|---|---|
| 1000 | Exact match |
| 900+ | Name starts with query |
| 800+ | A word starts with query |
| 700+ | Contains exact substring |
| 550–650 | Multi-word match |
| 300–500 | Fuzzy match (4+ char queries) |
| 100–299 | Partial fuzzy match |

---

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