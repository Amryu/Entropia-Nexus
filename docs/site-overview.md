# Entropia Nexus - Site Overview

A comprehensive resource for Entropia Universe, including item databases, maps, marketplace features, and player tools.

## Architecture

### Technology Stack

- **Frontend**: SvelteKit 2.0 with Svelte 4.2
- **Backend API**: Express.js (separate `api/` project)
- **Databases**:
  - `nexus` - Game data (items, mobs, locations, etc.)
  - `nexus_users` - User data (sessions, shops, services, trades)
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

### Landing Page (`/`)

Dynamic homepage with four content sections:

| Section | Data Source | Description |
|---------|------------|-------------|
| **Latest News** | Steam News API (App 3642750) + Nexus announcements | Merged news feed; pinned first, then date desc. Nexus articles with `content_html` link to `/news/{id}` for on-site reading |
| **Upcoming Events** | `events` table (approved, future) | Community-submitted events approved by admins |
| **Live Streams** | `content_creators` table (active, Twitch live) | Privacy-safe stream previews with creator avatars, ordered by priority then viewer count (up to 6) |
| **Latest Videos** | `content_creators` table (active, YouTube) | Clickable video thumbnails evenly distributed across creators (up to 6) |
| **Explore** | Static | Links to Items, Information, Maps, Tools, Market |

**Server data**: `+page.server.js` loads all four data sources in parallel.

**News cache**: `$lib/server/news-cache.js` — 30-minute in-memory TTL, filters Steam to "Community Announcements" feed.

**Creator enrichment**: `$lib/server/creator-enrichment.js` — background loop every 15 minutes refreshes stale YouTube (RSS feed for up to 6 recent videos + Data API v3 for channel info) and Twitch (Helix API for profile + live stream status with thumbnail). Kick has no API. The server processes creators into `streams` (live Twitch, sorted by display_order then viewer count) and `videos` (YouTube, evenly distributed across creators via round-robin).

**Database tables** (in `nexus_users`):
- `announcements` — Admin-created news posts (with optional `content_html` for on-site rich text articles)
- `events` — Community events with state machine (pending → approved/denied)
- `content_creators` — Whitelisted channels with `cached_data` JSONB

### News (`/news/`)

| Route | Description |
|-------|-------------|
| `/news/[id]` | Public article page for a published Nexus announcement with rich text content |

Announcements are created by admins via `/admin/announcements`. They can have either rich text content (read on-site), an external link, or both. The RichTextEditor supports markdown paste auto-conversion. Banner images use the `announcement` entity type in the image processor (1200px wide, auto-approve).

### Events (`/events/`)

| Route | Description |
|-------|-------------|
| `/events/submit` | Submit a community event (requires verified user) |

Events follow a submission-approval flow:
1. Verified user submits via `/events/submit` → state `pending`
2. Admin reviews in `/admin/events` → approves or denies with optional note
3. Approved events with future `start_date` appear on the landing page

Rate limit: max 5 pending events per user.

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

| Route | Description | Documentation |
|-------|-------------|---------------|
| `/information/professions/[[slug]]` | Profession skill trees | |
| `/information/skills/[[slug]]` | Individual skills | |
| `/information/vendors/[[slug]]` | NPC vendor locations and offers | |
| `/information/mobs/[[slug]]` | Creature information and loot | |
| `/information/missions/[[slug]]` | Missions and mission chains | `docs/missions.md` |

**Missions Features** (`?view=chains` toggles chain view):
- Mission chains with dependency graphs
- Steps with 6 objective types (Dialog, KillCount, KillCycle, Explore, Interact, HandIn)
- Rewards (items, skills, unlocks)
- Chain preview and full graph visualization

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

### Search (`/search`)

Dedicated search results page with grouped, columnar results.

| Route | Description |
|-------|-------------|
| `/search?q=...` | Full search results with enriched entity data |

**Features**:
- Debounced search input updates URL reactively
- Results grouped by entity type, sorted by search score
- Compact tables with user-configured columns (from sidebar preferences)
- Collapsible sections per entity type
- Falls back to default columns when no user preferences exist
- API: `/search/detailed` enriches results with full entity Properties

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

**Database Tables** (`nexus_users`):
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

**Database Tables** (`nexus_users`):
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

**Database Tables** (`nexus_users`):
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

**Database Tables** (`nexus_users`):
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

### nexus_users (User Data)

User-generated content and sessions:
- User accounts and sessions
- Shop inventories and managers
- Trade offers (exchange)
- Service marketplace (see `docs/services.md`)
- Change requests
- Announcements (admin-created news posts)
- Events (community-submitted, admin-approved)
- Content creators (whitelisted channels with API-enriched cached data)

## Image Storage

Entity images (icons, thumbnails) are stored with a dual-write strategy:

- **Local filesystem**: Docker volume `nexus-uploads` mounted at `/app/uploads` — used for temp/pending uploads and as fallback
- **Cloudflare R2**: S3-compatible object storage — primary source for approved images when configured

### Key files

| File | Purpose |
|------|---------|
| `nexus/src/lib/server/imageProcessor.js` | Upload processing, approval workflow, R2 upload on approve |
| `nexus/src/lib/server/imageEnhancer.js` | Dark/light mode enhancement pipeline |
| `nexus/src/lib/server/r2Storage.js` | R2 client module (gracefully disabled when env vars unset) |
| `nexus/src/lib/server/imageVariants.js` | Pre-generates resize variants (s32, s48, s64, s128) |
| `nexus/src/routes/api/img/` | Serves images: R2 first, local disk fallback |
| `nexus/src/routes/api/image/` | User profile images: same R2-first pattern |

### Approval flow

1. User uploads → sharp processes → saved to `uploads/temp/{uuid}/` (local only)
2. Admin approves → moved to `uploads/approved/` (local) + uploaded to R2 with all size variants
3. Serving reads from R2 first, falls back to local disk
4. Enhancement (`?mode=dark|light`) runs server-side from R2/local source, cached by Cloudflare CDN

### Configuration

R2 is optional. Without `R2_*` env vars, the system operates on local filesystem only. See `nexus/.env.example` for required variables.

### Migration

Run `node nexus/migrate-images-to-r2.mjs` to upload existing approved images to R2. Supports `--dry-run` and `--force` flags. Safe to run while the site is live.

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
- `nexus_users-test` - Test user data

**Run Tests**:
```bash
cd nexus
npx playwright test
```
