# Items Database

Comprehensive database of Entropia Universe items with stats, properties, and related information.

## Route Structure

All item routes follow the pattern:
```
/items/[category]/[[slug]]
```

- No slug: List view of all items in category
- With slug: Detail view for specific item

## Item Categories

### Weapons (`/items/weapons/`)

Combat weapons including:
- Melee weapons
- Ranged weapons (pistols, rifles, etc.)
- BLP and laser weapons

**Properties**:
- Damage (min/max)
- Range
- Attacks per minute
- Decay
- Ammo consumption
- Accuracy
- Profession requirements

### Armor (`/items/armorsets/`)

Protective equipment:
- Full armor sets
- Individual armor pieces

**Properties**:
- Protection values (by damage type)
- Durability
- Tier support
- Set bonuses

### Clothing (`/items/clothing/`)

Wearable items:
- Shirts, pants, shoes, etc.
- Cosmetic items
- Items with buff effects

**Properties**:
- EffectsOnEquip (buffs when worn)
- Gender restrictions
- Color variants

### Attachments (`/items/attachments/[type]/`)

Equipment enhancements and modifications:

| Type | Description | Editable |
|------|-------------|----------|
| weaponamplifiers | Damage/range amplifiers | Yes |
| weaponvisionattachments | Scopes and sights | Yes |
| absorbers | Deterioration absorbers | Yes |
| finderamplifiers | Finder amplifiers | Yes |
| armorplatings | Armor platings | Yes |
| enhancers | Tool/weapon/armor enhancers | **No** (database-generated) |
| mindforceimplants | Mindforce implants | Yes |

**Note**: Enhancers are automatically generated in the database and cannot be manually created or edited through the wiki interface.

### Medical Tools (`/items/medicaltools/[type]/`)

Healing and buff equipment:

| Type | Description |
|------|-------------|
| tools | FAP devices |
| chips | Healing chips |

**Properties**:
- Heal amount
- Decay rate
- Profession level requirements

### Tools (`/items/tools/[type]/`)

Mining and crafting equipment:

| Type | Description |
|------|-------------|
| finders | Ore/treasure detection |
| excavators | Resource extraction |
| refiners | Material processing |
| scanners | Analysis tools |

### Materials (`/items/materials/`)

Crafting resources:
- Ores and enmatter
- Animal materials
- Components
- Textures

**Properties**:
- TT value
- Stack size
- Refining options
- Blueprint usage

### Blueprints (`/items/blueprints/`)

Crafting recipes:
- Item blueprints
- Component blueprints

**Properties**:
- Output item
- Material requirements
- Quality Rating (QR)
- Success rate modifiers
- Profession requirements

### Consumables (`/items/consumables/[type]/`)

Single-use items:

| Type | Description |
|------|-------------|
| pills | Buff consumables |
| nutrio | Food items |
| stimulants | Temporary boosts |

**Properties**:
- Effect type and duration
- Stack size
- TT value

### Vehicles (`/items/vehicles/`)

Transportation:
- Ground vehicles
- Air vehicles
- Water vehicles

**Properties**:
- Speed
- Capacity
- Fuel consumption

### Pets (`/items/pets/`)

Companion creatures:

**Properties**:
- Skills (by unlock level)
- Buff effects
- Food requirements

### Furnishings (`/items/furnishings/[type]/`)

Estate decorations:

| Type | Description |
|------|-------------|
| furniture | Functional items |
| decorations | Cosmetic items |
| signs | Display items |

### Strongboxes (`/items/strongboxes/`)

Storage containers with capacity limits.

## Common Components

### EntityViewer

Standard component for item detail display:
- Title bar with item name
- Properties panel
- Related items
- Acquisition methods
- Usage information

### BrowseList

List view component with:
- Searchable item list
- Sortable columns
- Category filtering
- Planet filtering (where applicable)

### Table Component

Data table with:
- Sortable columns
- Search functionality
- Pagination
- Row click handlers

## API Integration

Items are fetched from the public API:

```javascript
// Example: Fetch weapons
const weapons = await apiCall(fetch, '/weapons');

// Example: Fetch single weapon
const weapon = await apiCall(fetch, `/weapons/${id}`);
```

### Common Endpoints

```
GET /weapons              - All weapons
GET /weapons/:id          - Single weapon
GET /armors               - All armor pieces
GET /armorsets            - Armor sets
GET /weaponamplifiers     - Weapon amps
GET /weaponvisionattachments - Scopes/sights
GET /absorbers            - Absorbers
GET /medicaltools         - FAPs
GET /medicalchips         - Healing chips
GET /finders              - Mining finders
GET /excavators           - Excavators
GET /materials            - All materials
GET /blueprints           - All blueprints
GET /consumables          - Consumables
GET /vehicles             - Vehicles
GET /pets                 - Pets
GET /clothing             - Clothing
GET /furniture            - Furniture
GET /decorations          - Decorations
GET /strongboxes          - Storage boxes
```

## Item Properties

### Common Fields

| Field | Description |
|-------|-------------|
| Id | Unique identifier |
| Name | Display name |
| Properties | Type-specific properties |
| Type | Item category |
| TT | Trade terminal value |
| MaxTT | Maximum TT (for condition items) |

### Limited vs Unlimited

Items tagged with:
- `(L)` - Limited items (can break)
- No tag or `(UL)` - Unlimited items

```javascript
// Check if item is limited
hasItemTag(item.Name, "L")
```

### Tierable Items

Items that support tiering:
- Weapons
- Armor
- Finders
- Excavators
- Medical Tools

Tier properties:
- Current tier level
- Tier Increase Rate (TiR)

## Data Sources

### Primary Database (nexus)

Game data tables:
- Items by category
- Item properties
- Relationships (blueprints, drops, etc.)

### Public API

Express server (`api/`) provides:
- REST endpoints for all item types
- Swagger documentation at `/docs`
- Caching for performance

## Item Links

Generate links to item detail pages:

```javascript
import { getItemLink } from '$lib/util';

const link = getItemLink(item);
// Returns: "/items/weapons/armatrix-ln-35"
```

## Related Documentation

- `docs/site-overview.md` - Site architecture
- `docs/ui-styling.md` - Component styling
