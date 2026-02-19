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

## Inventory Page

Dedicated inventory management page at `/account/inventory` for analyzing, categorizing, and configuring imported items.

### Features

- **Container Structure**: Preserves full container hierarchy from EU imports (e.g., `STORAGE (Calypso) > Sleipnir Mk.1 (C,L) > Storage Container (L)`)
- **Four View Modes**: List (FancyTable), Grid (cards), Category grouping (collapsible sections), Compact (dense table)
- **Flat/Tree Toggle**: Flat mode groups by planet; Tree mode shows container hierarchy with folder navigation
- **Filtering**: By planet, container, category, search term, markup status — all synced to URL query params
- **Markup Management**: Inline editing in list view, bulk edit dialog, import from exchange orders
- **Value Calculations**: TT value, user markup, market price (WAP), total estimated value per item and in summary bar
- **Import Delta Tracking**: Shows changes between imports (added/removed/changed items) with history
- **Item Metadata Editing**: Reuses InventoryItemDialog for editing Tier, TiR, QR, value, quantity

### Layout

```
.scroll-container (height: 100%)
  .page-container (max-width: 1200px)
    .inventory-layout (display: flex)
      .inventory-sidebar (220px)
        PlanetSelector — pill buttons with item counts
        ContainerTree — recursive folder tree from container_path
        CategoryFilter — collapsible list with counts
      .inventory-main (flex: 1)
        InventoryToolbar — search, view toggle, structure toggle, import, bulk actions
        InventorySummaryBar — total TT, estimated value, item count, scope label
        [View: list | grid | category | compact]
        InventoryDeltaPanel — expandable panel showing last import changes
```

Mobile (≤900px): sidebar becomes overlay panel.

### Categories

Items are organized using `getTopCategory()` and sorted by `CATEGORY_ORDER` from `orderUtils.ts`. Categories include: Weapons, Armor, Tools, Mining, Medical, Materials, Blueprints, Vehicles, Clothing, Consumables, Pets, Furnishings, and more.

### Database Tables (nexus-users)

#### `user_items` (extended)

| Column | Type | Description |
|--------|------|-------------|
| container_path | text | Full container hierarchy (e.g., `STORAGE (Calypso) > Vehicle Name`) |

#### `inventory_imports`

| Column | Type | Description |
|--------|------|-------------|
| id | bigserial | Primary key |
| user_id | bigint | Owner |
| imported_at | timestamptz | Import time |
| item_count | integer | Number of items imported |
| total_value | numeric | Total TT value |
| summary | jsonb | `{added, updated, removed, unchanged}` |

#### `inventory_import_deltas`

| Column | Type | Description |
|--------|------|-------------|
| id | bigserial | Primary key |
| import_id | bigint | FK to inventory_imports |
| delta_type | enum | `added`, `removed`, `changed` |
| item_id | integer | Item reference |
| item_name | varchar(255) | Item display name |
| container | varchar(255) | Planet/storage location |
| old_quantity / new_quantity | integer | Quantity change |
| old_value / new_value | numeric | Value change |

#### `user_item_markups`

| Column | Type | Description |
|--------|------|-------------|
| user_id | bigint | Owner (PK) |
| item_id | integer | Item reference (PK) |
| markup | numeric | User-configured markup value |
| updated_at | timestamptz | Last update |

### Route

```
/account/inventory    - Main inventory page (CSR only, auth required)
```

Short URL: `ai` → `/account/inventory`

### Components

```
nexus/src/routes/account/inventory/
├── +page.js              - CSR only (ssr = false)
├── +page.svelte          - Thin shell mounting InventoryPage
└── InventoryPage.svelte  - Main component with all views, filtering, markup editing
```

### Related API Endpoints

```
GET    /api/users/inventory                      - User's inventory
PUT    /api/users/inventory                      - Full-sync import
GET    /api/users/inventory/imports              - Import history (paginated)
GET    /api/users/inventory/imports/[id]/deltas  - Deltas for a specific import
GET    /api/users/inventory/markups              - User's markup configs
PUT    /api/users/inventory/markups              - Bulk upsert markups
DELETE /api/users/inventory/markups/[itemId]     - Remove markup for item
```

---

## Unknown Items (Admin)

Admin page at `/admin/unknown-items` for tracking unresolved item names encountered during inventory imports.

### Features

- FancyTable with columns: Item Name, Per-Unit TT, User Count, First Seen, Last Seen, Actions
- Default sort by user_count DESC (most common unknowns first)
- Toggle to show resolved items
- "Resolve" button to mark items as resolved

### Database Tables (nexus-users)

#### `unknown_items`

| Column | Type | Description |
|--------|------|-------------|
| id | serial | Primary key |
| item_name | varchar(255) | Unknown item name |
| value | numeric | Per-unit TT value |
| user_count | integer | Number of unique users reporting this item |
| first_seen_at | timestamptz | First encounter |
| last_seen_at | timestamptz | Most recent encounter |
| resolved | boolean | Whether admin has resolved it |
| resolved_item_id | integer | Linked item ID (if resolved to existing item) |

Unique index on `LOWER(item_name)` for case-insensitive dedup.

#### `unknown_item_users`

Junction table tracking which users have reported each unknown item. Primary key `(unknown_item_id, user_id)`.

### API Endpoints

```
GET   /api/admin/unknown-items       - List unknown items (admin)
PATCH /api/admin/unknown-items/[id]  - Mark resolved (admin)
```

---

## Related Documentation

- `docs/site-overview.md` - Site architecture
- `docs/ui-styling.md` - Component styling
- `docs/market.md` - Exchange inventory import system
