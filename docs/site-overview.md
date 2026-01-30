# Entropia Nexus - Site Overview

A comprehensive resource for Entropia Universe, including item databases, maps, marketplace features, and player tools.

## Architecture

### Technology Stack

- **Frontend**: SvelteKit 2.0 with Svelte 4.2
- **Backend API**: Express.js (separate `api/` project)
- **Databases**:
  - `nexus` - Game data (items, mobs, locations, etc.)
  - `nexus-users` - User data (sessions, shops, services, trades)
- **Authentication**: Discord OAuth2
- **Testing**: Playwright E2E tests

### Project Structure

```
Entropia Nexus/
├── api/                    # Express API server (public game data)
│   ├── app.js              # Main server
│   ├── endpoints/          # API route handlers
│   └── credentials.js      # Database configuration
├── nexus/                  # SvelteKit frontend
│   ├── src/
│   │   ├── routes/         # Page routes and API routes
│   │   ├── lib/
│   │   │   ├── components/ # Reusable Svelte components
│   │   │   ├── style.css   # Global styles with CSS variables
│   │   │   └── util.js     # Utility functions
│   │   └── stores.js       # Svelte stores (darkMode, loading)
│   └── tests/              # Playwright E2E tests
├── nexus-bot/              # Discord bot
├── docs/                   # Documentation
└── sql/                    # Database migrations and dumps
```

## Site Sections

### Items (`/items/`)

Browse game items organized by category:

| Route | Description |
|-------|-------------|
| `/items/weapons/[[slug]]` | Weapons with damage, range, economy stats |
| `/items/armorsets/[[slug]]` | Armor sets with protection values |
| `/items/clothing/[[slug]]` | Clothing items |
| `/items/attachments/[[type]]/[[slug]]` | Weapon attachments (amps, scopes, sights) |
| `/items/medicaltools/[[type]]/[[slug]]` | Medical tools and chips |
| `/items/tools/[[type]]/[[slug]]` | Mining/crafting tools |
| `/items/materials/[[slug]]` | Materials and resources |
| `/items/blueprints/[[slug]]` | Crafting blueprints |
| `/items/consumables/[[type]]/[[slug]]` | Consumables (pills, food, etc.) |
| `/items/vehicles/[[slug]]` | Vehicles |
| `/items/pets/[[slug]]` | Pets with skills |
| `/items/furnishings/[[type]]/[[slug]]` | Furniture and decorations |
| `/items/strongboxes/[[slug]]` | Storage containers |

**Features**:
- List and detail views with `[[slug]]` parameter
- Entity viewer component for consistent display
- Item properties, acquisition methods, usage information
- Links to related items (blueprints, drops, etc.)

### Information (`/information/`)

Game reference data:

| Route | Description |
|-------|-------------|
| `/information/professions/[[slug]]` | Profession skill trees |
| `/information/skills/[[slug]]` | Individual skills |
| `/information/vendors/[[slug]]` | NPC vendor locations and offers |
| `/information/mobs/[[slug]]` | Creature information and loot |

### Maps (`/maps/`)

Interactive planet maps:

| Route | Description |
|-------|-------------|
| `/maps/[[planet]]/[[slug]]` | Interactive SVG maps with locations |

**Features**:
- Pan and zoom navigation
- Teleporter, area, and estate markers
- Mob spawn locations
- Coordinate waypoint generation

### Market (`/market/`)

Player marketplace features:

| Route | Description | Documentation |
|-------|-------------|---------------|
| `/market/exchange/[[slug]]/[[id]]` | Item trading exchange | See below |
| `/market/shops/[[slug]]` | Player shop directory | See below |
| `/market/services/` | Service marketplace | `docs/services.md` |

### Tools (`/tools/`)

Player utilities:

| Route | Description | Documentation |
|-------|-------------|---------------|
| `/tools/loadouts` | Loadout calculator | See below |

### Account (`/account/`)

User account management:

| Route | Description |
|-------|-------------|
| `/account/setup` | Initial account configuration |

## Key Features

### Exchange System

Player-to-player trading marketplace.

**Features**:
- Browse items by category tree
- Filter by planet, limited status, sex (clothing)
- Create buy/sell orders
- Tier and TiR filters for tierable items
- QR filter for blueprints
- Order freshness indicators

**Database Tables** (`nexus-users`):
- `trade_offers` - Buy/sell orders

**API Endpoints**:
```
GET  /api/market/exchange   - Get categorized items for trading
```

### Shop System

Player shop directory with inventory management.

**Features**:
- Browse shops by planet
- View shop inventory organized by groups
- Shop owner and manager roles
- Coordinate waypoints

**Database Tables** (`nexus-users`):
- `shop_inventory_groups` - Inventory categories
- `shop_inventory_items` - Items in each group
- `shop_managers` - Shop access permissions

**API Endpoints**:
```
GET    /api/shops/:shop/inventory  - Get shop inventory
GET    /api/shops/:shop/managers   - Get shop managers
POST   /api/shops/:shop/managers   - Add manager
DELETE /api/shops/:shop/managers   - Remove manager
```

### Loadout Calculator

Equipment planning tool for calculating DPS, economy, and protection.

**Features**:
- Weapon selection with attachments (amp, scope, sight, absorber)
- Enhancer slots (damage, accuracy, range, economy, skill mod)
- Armor set builder with individual piece selection
- Plating and armor enhancers
- Clothing and pet buffs
- Markup cost calculations
- Local storage for saving loadouts
- Compare mode for loadout comparison

**Data Sources**: Fetches from public API:
- Weapons, amplifiers, scopes, sights, absorbers
- Armor sets, armors, platings, enhancers
- Clothing, pets, stimulants

### Change System

Crowdsourced data corrections with review workflow.

**Workflow**:
1. User creates a change (Draft state)
2. User submits for review (Pending state)
3. Admin reviews and approves/rejects
4. Approved changes update the database

**Database Tables** (`nexus-users`):
- `changes` - Change requests with state tracking

**API Endpoints**:
```
GET    /api/changes/[[slug]]  - Get change details
POST   /api/changes           - Create change
PUT    /api/changes/:id       - Update change
```

## Authentication

Discord OAuth2 integration:

**Flow**:
1. User clicks login
2. Redirect to Discord OAuth
3. Callback to `/discord/auth`
4. Session created in `sessions` table
5. User record in `users` table

**Database Tables** (`nexus-users`):
- `users` - User profiles (Discord ID, avatar, roles)
- `sessions` - Active sessions
- `user_settings` - User preferences

## Shared Components

### Core Components (`nexus/src/lib/components/`)

| Component | Description |
|-----------|-------------|
| `Table.svelte` | Sortable, searchable data table |
| `EntityViewer.svelte` | Item/entity detail display |
| `Properties.svelte` | Property list with waypoint support |
| `Map.svelte` | Interactive SVG map viewer |
| `MapList.svelte` | Map location list |
| `ItemPicker.svelte` | Item selection modal |
| `Menu.svelte` | Navigation menu |
| `Tooltip.svelte` | Hover tooltips |
| `ContextMenu.svelte` | Right-click context menus |

### Utility Functions (`nexus/src/lib/util.js`)

```javascript
apiCall(fetch, path, baseUrl?)     // API GET request
apiPost(fetch, path, data, baseUrl?) // API POST request
apiPut(fetch, path, data, baseUrl?)  // API PUT request
getItemLink(item)                   // Generate item detail URL
navigate(url)                       // Client-side navigation
hasItemTag(name, tag)               // Check item name for tag (L, UL, etc.)
clampDecimals(value, decimals)      // Number formatting
```

### Stores (`nexus/src/stores.js`)

```javascript
darkMode    // Theme toggle state
loading     // Global loading indicator
```

## Public API (Express)

The `api/` project serves game data from the `nexus` database.

**Base URL**: `https://api.entropianexus.com`

**Common Endpoints**:
```
GET /weapons           - All weapons
GET /weapons/:id       - Weapon details
GET /armors            - All armor pieces
GET /armorsets         - Armor sets
GET /materials         - Materials
GET /blueprints        - Blueprints
GET /mobs              - Mobs/creatures
GET /mobmaturities     - Mob maturity levels
GET /planets           - Planets
GET /teleporters       - Teleporter locations
GET /areas             - Named areas
GET /vendors           - NPC vendors
GET /vendoroffers      - Vendor trade offers
GET /professions       - Professions
GET /skills            - Skills
GET /pets              - Pets with effects
... (many more item type endpoints)
```

**Documentation**: Swagger UI at `/docs`

## Database Overview

### nexus (Game Data)

Primary game data from Entropia Universe:
- Items (weapons, armor, tools, etc.)
- Locations (planets, teleporters, areas)
- Creatures (mobs, maturities, spawns, loot)
- Professions and skills
- Vendors and trade offers

### nexus-users (User Data)

User-generated content and sessions:
- User accounts and sessions
- Shop inventories and managers
- Trade offers (exchange)
- Service marketplace (see `docs/services.md`)
- Change requests

## Styling

See `docs/ui-styling.md` for:
- CSS variable reference
- Component patterns
- Theme support (light/dark mode)
- Responsive breakpoints

## Testing

Playwright E2E tests in `nexus/tests/`:

**Configuration**: `nexus/playwright.config.ts`
- Frontend: port 3002
- Test API: port 3001 (uses test databases)

**Test Databases**:
- `nexus-test` - Test game data
- `nexus-users-test` - Test user data

**Run Tests**:
```bash
cd nexus
npx playwright test
```
