# API Reference

## Data API

**Base URL:** `https://api.entropianexus.com`

The Data API provides read-only access to the full Entropia Universe database. No authentication required. All responses are JSON. OpenAPI spec available at `/schema.json` and interactive documentation at `/docs`.

### Search

#### `GET /search`

Search across all entity types. Returns up to 50 results (max 5 per type).

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | **Required.** Search term |
| `fuzzy` | string | Set to `true` or `1` for fuzzy matching |

**Searchable types:** Items, ArmorSets, Mobs, Skills, Professions, Vendors, Missions, MissionChains, Locations, Users, Societies

```json
[
  { "Id": 12345, "Name": "Adjusted HeartBeat", "Type": "Weapon", "SubType": "Shortblade", "Score": 95 }
]
```

#### `GET /search/detailed`

Same parameters as `/search`. Returns enriched results with full entity data (up to 300 results, 100 per type).

#### `GET /search/items`

Items-only search with optional type filtering.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | **Required.** Search term |
| `fuzzy` | string | Set to `true` or `1` for fuzzy matching |
| `type` | string | Filter to a specific item type (optional) |
| `limit` | integer | Max results (default 50) |

**Valid types:** `Weapon`, `Armor`, `Clothing`, `Tool`, `Material`, `Blueprint`, `Component`, `Furniture`, `Enhancer`, `Attachment`, `ArmorSet`, `Consumable`, `Mining`, `Amplifier`, `Vehicle`

### Entity Data

All entity endpoints follow the pattern: `GET /{collection}` returns all entries, `GET /{collection}/{id}` returns a single entry by ID or name. Responses are cached in-memory and refreshed when underlying data changes.

**Items & Equipment:**

| Endpoint | Description |
|----------|-------------|
| `/absorbers` | Energy absorbers |
| `/armorplatings` | Armor plating attachments |
| `/armorsets` | Armor sets with pieces, effects, and tiers |
| `/armors` | Individual armor pieces |
| `/blueprints` | Blueprints with materials, books, and drops |
| `/blueprintbooks` | Blueprint book collections |
| `/blueprintdrops` | Blueprint drop sources |
| `/capsules` | Creature control capsules |
| `/clothings` | Clothing with effects and equip sets |
| `/consumables` | Consumable items with effects |
| `/decorations` | Decorative items |
| `/effectchips` | Effect chips with materials and effects |
| `/effects` | All effect definitions |
| `/enhancers` | Enhancer attachments |
| `/equipsets` | Equipment sets |
| `/excavators` | Excavators with effects and tiers |
| `/finderamplifiers` | Finder amplifiers |
| `/finders` | Finders with effects and tiers |
| `/furniture` | Furniture items |
| `/items` | All items (supports `?Ids=1,2,3` for batch fetch) |
| `/medicalchips` | Medical chips with effects |
| `/medicaltools` | Medical tools with effects and tiers |
| `/mindforce` | Mindforce implants |
| `/misctools` | Miscellaneous tools |
| `/pets` | Tamed creatures |
| `/refiners` | Refiner tools |
| `/refining` | Refining recipes with ingredients |
| `/scanners` | Scanner tools |
| `/signs` | Sign items |
| `/storagecontainers` | Storage containers |
| `/strongboxes` | Strongbox items |
| `/teleportationchips` | Teleportation chips |
| `/tiers` | Tier data with materials |
| `/vehicles` | Vehicles |
| `/weaponamplifiers` | Weapon amplifiers |
| `/weaponvisionattachments` | Weapon vision attachments |
| `/weapons` | Weapons with effects, tiers, and materials |

**World & Information:**

| Endpoint | Description |
|----------|-------------|
| `/apartments` | Apartment estates |
| `/areas` | Geographic areas |
| `/events` | In-game events |
| `/locations` | All locations with facilities and wave events |
| `/missions` | Missions with chains and events |
| `/missionchains` | Mission chain collections |
| `/planets` | Planet data |
| `/professions` | Professions with skills and unlocks |
| `/professioncategories` | Profession category groupings |
| `/shops` | Player shops with inventory |
| `/skills` | Skills with profession links |
| `/skillcategories` | Skill category groupings |
| `/teleporters` | Teleporter locations |
| `/vendoroffers` | NPC vendor offer prices |
| `/vendors` | NPC vendors with offers |

**Mobs:**

| Endpoint | Description |
|----------|-------------|
| `/mobs` | Creatures with species, loots, maturities, and spawns |
| `/mobloots` | Creature loot tables |
| `/mobmaturities` | Creature maturity levels |
| `/mobspawns` | Creature spawn locations |
| `/mobspecies` | Creature species |

### Acquisition & Usage

#### `GET /acquisition`

Find where items can be obtained. Returns blueprints that craft the item, mob loot tables, vendor offers, refining recipes, shop listings, and blueprint drops.

| Parameter | Type | Description |
|-----------|------|-------------|
| `items` | string | **Required.** Comma-separated item names or IDs |

Also available as `GET /acquisition/{item}` for a single item.

#### `GET /usage`

Find where items are used as ingredients. Returns blueprints, refining recipes, and vendor offers.

| Parameter | Type | Description |
|-----------|------|-------------|
| `items` | string | **Required.** Comma-separated item names or IDs |

Also available as `GET /usage/{item}` for a single item.

### Enumerations

#### `GET /enumerations`

Returns all available enumeration names.

#### `GET /enumerations/{name}`

Returns tabular data for a specific enumeration.

### Audit History

#### `GET /audit/types`

Returns the list of entity types that support audit history.

**Supported types:** Weapon, ArmorSet, Material, MedicalTool, MedicalChip, Refiner, Scanner, Finder, Excavator, TeleportChip, EffectChip, MiscTool, WeaponAmplifier, WeaponVisionAttachment, Absorber, FinderAmplifier, ArmorPlating, MindforceImplant, Blueprint, Pet, Mob, Consumable, CreatureControlCapsule, Vehicle, Furniture, Decoration, StorageContainer, Sign, Clothing, Vendor

#### `GET /audit/{entityType}/{entityId}`

Returns the last 100 audit records for an entity. Each record includes `Operation` (Insert/Update/Delete), `Timestamp`, `UserId`, and `Data`.

#### `GET /audit/{entityType}/{entityId}/original`

Returns the original INSERT version of an entity.

#### `GET /audit/{entityType}/{entityId}/at`

Returns the entity version at a specific point in time.

| Parameter | Type | Description |
|-----------|------|-------------|
| `timestamp` | string | **Required.** ISO 8601 timestamp |

### Entity Changes

Community-submitted changes to the wiki database.

#### `GET /entity-changes/types`

Returns entity types with pending change counts.

#### `GET /entity-changes/search`

Search for entity changes.

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Search by name |
| `type` | string | Filter by entity type |
| `limit` | integer | Results per page (default 50) |
| `offset` | integer | Pagination offset (default 0) |

#### `GET /entity-changes/{entityType}/{entityIdOrName}`

Returns all change requests for a specific entity (by numeric ID or name).

## Public Endpoints

**Base URL:** `https://entropianexus.com`

These endpoints require no authentication and are read-only unless noted.

### Market

#### `GET /api/market/exchange`

Returns the full exchange market cache. Supports `ETag`/`304 Not Modified` and pre-compressed responses (`Accept-Encoding: br, gzip`).

#### `GET /api/market/search`

Unified market search across exchange orders, services, auctions, rentals, and shops.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | **Required.** Search term (2-100 chars) |

Returns up to 30 scored results, each with `id`, `name`, `marketType`, `entityType`, `price`, `detail`, `url`, and `score`.

#### `GET /api/market/prices/{itemId}`

Price history for an item from external price sources.

| Parameter | Type | Description |
|-----------|------|-------------|
| `from` | string | Start date (ISO 8601) |
| `to` | string | End date (ISO 8601) |
| `granularity` | string | `raw`, `hour`, `day`, `week`, or `auto` |
| `source` | string | Filter by price source |
| `limit` | integer | Max results (1-2000, default 500) |

#### `GET /api/market/prices/latest`

Latest prices for multiple items at once.

| Parameter | Type | Description |
|-----------|------|-------------|
| `items` | string | **Required.** Comma-separated item IDs (max 100) |
| `source` | string | Filter by price source |

#### `GET /api/market/prices/exchange/{itemId}`

Exchange-derived price data and statistics for an item.

| Parameter | Type | Description |
|-----------|------|-------------|
| `period` | string | `24h`, `7d`, `30d`, `3m`, `6m`, `1y`, `5y`, or `all` (default `7d`) |
| `history` | string | Set to `1` to include time-series data |
| `gender` | string | `Male` or `Female` for gendered items |

#### `GET /api/market/exchange/orders/item/{itemId}`

Full order book (buy and sell orders) for an item.

#### `GET /api/market/exchange/orders/user/{userId}`

All active exchange orders for a user.

### Auctions

#### `GET /api/auction`

Paginated list of public auctions.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | `active` | `active`, `ended`, `settled`, or `cancelled` |
| `search` | string | — | Search titles (max 100 chars) |
| `sort` | string | `ends_at` | `ends_at`, `created_at`, `current_bid`, `bid_count`, `starting_bid` |
| `order` | string | `asc` | `asc` or `desc` |
| `limit` | integer | 24 | Results per page (1-100) |
| `offset` | integer | 0 | Pagination offset |

#### `GET /api/auction/{id}`

Auction detail with bid history.

### Services

#### `GET /api/services`

List active service listings.

| Parameter | Type | Description |
|-----------|------|-------------|
| `type` | string | Filter by service type |
| `planet_id` | integer | Filter by planet |
| `include_details` | string | Set to `true` for full details |

**Service types:** `healing`, `dps`, `transportation`, `crafting`, `hunting`, `mining`, `custom`

#### `GET /api/services/{id}`

Full service detail including equipment, armor sets, and availability.

#### `GET /api/services/{id}/availability`

Weekly availability schedule for a service.

#### `GET /api/services/{id}/flights`

Flights for a warp/transportation service.

| Parameter | Type | Description |
|-----------|------|-------------|
| `include_completed` | string | Set to `true` to include past flights |
| `upcoming` | string | Set to `true` for upcoming only |

#### `GET /api/services/{id}/ticket-offers`

Ticket offers for a service.

### Rentals

#### `GET /api/rental`

List available rental offers.

| Parameter | Type | Description |
|-----------|------|-------------|
| `planet_id` | integer | Filter by planet |
| `limit` | integer | Results per page (max 100, default 50) |
| `page` | integer | Page number (default 1) |

#### `GET /api/rental/{id}`

Rental offer detail with item set data.

#### `GET /api/rental/{id}/availability`

Availability calendar showing accepted bookings and blocked dates.

| Parameter | Type | Description |
|-----------|------|-------------|
| `months` | integer | Calendar range (1-12, default 3) |

### Profiles & Societies

#### `GET /api/users/profiles/{identifier}`

Public user profile including contribution scores, services, shops, exchange orders, rental offers, and society membership. The `identifier` can be a numeric user ID or an Entropia name (use `~` for spaces).

#### `GET /api/societies`

Search for societies.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search term (returns all if empty) |

#### `GET /api/societies/{identifier}`

Society detail with members. The `identifier` can be a numeric ID or society name.

### Guides & Events

#### `GET /api/guides`

Full guide tree with all categories, chapters, and lessons.

#### `GET /api/guides/{categoryId}`

Single guide category.

#### `GET /api/guides/{categoryId}/chapters`

Chapters within a category.

#### `GET /api/guides/{categoryId}/chapters/{chapterId}`

Single chapter.

#### `GET /api/guides/{categoryId}/chapters/{chapterId}/lessons`

Lessons within a chapter.

#### `GET /api/guides/{categoryId}/chapters/{chapterId}/lessons/{lessonId}`

Single lesson with paragraphs.

#### `GET /api/events`

Upcoming approved community events.

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Max results (max 20, default 5) |

### Wiki Changes

#### `GET /api/changes`

List community-submitted wiki changes with filtering.

| Parameter | Type | Description |
|-----------|------|-------------|
| `entity` | string | Comma-separated entity types |
| `type` | string | `Create`, `Update`, or `Delete` |
| `state` | string | Comma-separated states |
| `authorId` | string | Filter by author |
| `planet` | string | Filter by planet |
| `page` | integer | Page number |
| `limit` | integer | Results per page (max 100) |

#### `GET /api/changes/{id}`

Single change by ID.

### Images

#### `GET /api/img/{entityType}/{entityId}`

Entity image (WebP). Returns the approved icon or thumbnail with optional processing.

| Parameter | Type | Description |
|-----------|------|-------------|
| `type` | string | `icon` or `thumb` |
| `size` | integer | `32`, `48`, `64`, `128`, or `320` |
| `mode` | string | `dark` or `light` |

### News

#### `GET /api/news`

Returns latest published announcements. Ordered by pinned status first, then newest.

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Max results (1–500, default 3) |

```json
[
  {
    "source": "steam",
    "id": 123,
    "title": "Update 18.5 Release Notes",
    "summary": "Brief summary text...",
    "url": "/news/123",
    "image_url": "https://...",
    "pinned": false,
    "has_content": true,
    "date": "2026-02-26T10:30:00.000Z"
  }
]
```

`url` points to `/news/:id` detail page when `has_content` is true, otherwise to an external link. `source` is `"steam"` or `"nexus"`.

#### `GET /api/news/{id}`

Returns a single published announcement with full content.

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | integer | **Required.** Announcement ID (path) |

```json
{
  "id": 123,
  "title": "Update 18.5 Release Notes",
  "summary": "Brief summary",
  "link": "https://...",
  "image_url": "https://...",
  "pinned": false,
  "author_id": 456,
  "author_name": "Author Name",
  "created_at": "2026-02-26T10:30:00.000Z",
  "source": "steam",
  "has_content": true,
  "content_html": "<p>Full HTML content...</p>",
  "source_id": "gid123456789"
}
```

Returns `404` if the announcement doesn't exist or isn't published.

### Other

#### `GET /api/tools/loadout/share/{shareCode}`

Returns a publicly shared loadout by its share code.

#### `POST /api/tools/skills/values`

Batch skill point to PED value conversions. Rate limit: 60/min per IP.

```json
{
  "skillPointsToPED": [1000, 5000],
  "pedToSkillPoints": [10.00]
}
```

At least one array must be provided. Max 200 items total.

## OAuth API

All OAuth API requests require a valid OAuth 2.0 Bearer token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

**Token lifecycle:**
- Access tokens expire after **1 hour**
- Refresh tokens expire after **30 days**
- Use the token endpoint to refresh expired access tokens

**Base URL:** `https://entropianexus.com`

### Client Types

When creating an OAuth application, choose between **confidential** (server-side apps with a client secret) and **public** (browser/native apps, PKCE only). Public clients omit `client_secret` from all token requests. Client type is set at creation and cannot be changed.

### Authorization Flow (PKCE)

1. Redirect the user to `/oauth/authorize` with your client credentials and a PKCE challenge
2. User approves the requested scopes on the consent screen
3. User is redirected back to your `redirect_uri` with an authorization `code`
4. Exchange the code for tokens at `POST /api/oauth/token`

### Token Endpoint

#### `POST /api/oauth/token`

**Grant type: `authorization_code`**

| Parameter | Description |
|-----------|-------------|
| `grant_type` | `authorization_code` |
| `code` | The authorization code from the redirect |
| `client_id` | Your application's client ID |
| `client_secret` | Your client secret (confidential clients) |
| `redirect_uri` | Must match the URI used in the authorization request |
| `code_verifier` | The PKCE code verifier |

**Grant type: `refresh_token`**

| Parameter | Description |
|-----------|-------------|
| `grant_type` | `refresh_token` |
| `refresh_token` | The refresh token from a previous token response |
| `client_id` | Your application's client ID |
| `client_secret` | Your client secret (confidential clients) |

**Response:**

```json
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "...",
  "scope": "profile:read inventory:read"
}
```

> Refresh tokens are single-use. Each refresh returns a new refresh token. Reusing an old refresh token will revoke all tokens for security.

### Scopes

| Scope | Description |
|-------|-------------|
| `profile:read` | Read your profile information |
| `inventory:read` | Read your inventory |
| `inventory:write` | Import and modify your inventory |
| `loadouts:read` | Read your loadouts |
| `loadouts:write` | Create and modify loadouts |
| `itemsets:read` | Read your item sets |
| `itemsets:write` | Create and modify item sets |
| `skills:read` | Read your skill data |
| `skills:write` | Import skill data |
| `exchange:read` | Read your exchange orders |
| `exchange:write` | Create, edit, and close exchange orders |
| `trades:read` | Read your trade requests |
| `services:read` | Read your services and requests |
| `services:write` | Modify your services |
| `auction:read` | Read your auctions and bids |
| `auction:write` | Create auctions, place bids, settle |
| `rental:read` | Read your rental offers and requests |
| `rental:write` | Create and modify rental offers |
| `notifications:read` | Read your notifications |
| `notifications:write` | Mark notifications as read |
| `preferences:read` | Read your preferences |
| `preferences:write` | Modify your preferences |
| `societies:read` | Read your society membership |
| `societies:write` | Join and manage societies |
| `wiki:read` | Read wiki change data |
| `wiki:write` | Submit wiki changes |
| `guides:write` | Create and edit guide content |
| `uploads:write` | Upload images |

### Profile

#### `GET /api/oauth/userinfo`
**Scope:** `profile:read`

Returns the authenticated user's profile.

```json
{
  "id": "123456789",
  "username": "player1",
  "global_name": "Player One",
  "discriminator": "0",
  "avatar": "https://cdn.discordapp.com/avatars/...",
  "eu_name": "Player One Calypso",
  "verified": true
}
```

### Inventory

#### `GET /api/users/inventory`
**Scope:** `inventory:read`

Returns the user's inventory items.

#### `PUT /api/users/inventory`
**Scope:** `inventory:write` | Rate limit: 5/min, 20/hour

Import inventory items. Max 30,000 items per import, max 500 unknown items (item_id = 0).

```json
{
  "items": [
    {
      "item_id": 12345,
      "item_name": "Adjusted HeartBeat (L)",
      "quantity": 1,
      "value": 15.50,
      "container": "Storage",
      "container_path": "Storage (Twin Peaks)",
      "instance_key": "unique-key",
      "details": {
        "Tier": 3.2,
        "TierIncreaseRate": 45,
        "QualityRating": 56.0
      }
    }
  ],
  "sync": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `item_id` | integer | Item database ID. Use `0` for unknown items |
| `item_name` | string | Item name (max 200 chars, required) |
| `quantity` | integer | Stack count (default: 0) |
| `value` | number | TT value in PED (optional) |
| `container` | string | Container name (max 200 chars, optional) |
| `container_path` | string | Full container path (max 500 chars, optional) |
| `instance_key` | string | Unique instance identifier (max 300 chars, optional) |
| `details` | object | Item metadata — see details fields below (optional) |

**Details fields:**

| Field | Type | Description |
|-------|------|-------------|
| `Tier` | float | Item tier (0-10) |
| `TierIncreaseRate` | integer | Tier increase rate (1-4000) |
| `QualityRating` | float | Blueprint quality rating (0-100) |

When `sync` is `true`, items not in the import are marked as removed.

#### `PATCH /api/users/inventory/{id}`
**Scope:** `inventory:write`

Update a single inventory item's quantity, value, or details.

#### `DELETE /api/users/inventory/{id}`
**Scope:** `inventory:write`

Remove a single inventory item.

#### `GET /api/users/inventory/imports`
**Scope:** `inventory:read` | Query: `limit` (max 100), `offset`

Returns import history with summaries.

#### `GET /api/users/inventory/imports/{id}/deltas`
**Scope:** `inventory:read`

Returns per-item changes (added, updated, removed) for a specific import.

#### `GET /api/users/inventory/imports/value-history`
**Scope:** `inventory:read`

Returns total inventory value over time.

#### `GET /api/users/inventory/markups`
**Scope:** `inventory:read`

Returns custom markup values set by the user.

#### `PUT /api/users/inventory/markups`
**Scope:** `inventory:write` | Rate limit: 60/min

Set custom markup values. Max 1,000 items per request. Markup range: 0 to 2,147,483,647.

```json
{
  "items": [
    { "item_id": 12345, "markup": 135.5 }
  ]
}
```

#### `DELETE /api/users/inventory/markups/{itemId}`
**Scope:** `inventory:write` | Rate limit: 60/min (shared with PUT)

Remove a custom markup for an item.

### Loadouts

#### `GET /api/tools/loadout`
**Scope:** `loadouts:read`

Returns all loadouts owned by the user.

#### `GET /api/tools/loadout/{id}`
**Scope:** `loadouts:read`

Returns a specific loadout. Must be the owner.

#### `GET /api/tools/loadout/share/{shareCode}`
**Scope:** `loadouts:read`

Returns a public loadout by its share code.

#### `POST /api/tools/loadout`
**Scope:** `loadouts:write` | Max: 500 per user, 20KB per loadout

Create a new loadout.

```json
{
  "name": "My Hunting Setup",
  "data": { ... },
  "public": true
}
```

#### `POST /api/tools/loadout/import`
**Scope:** `loadouts:write` | Max: 1MB per request

Bulk import loadouts.

```json
{
  "loadouts": [ { "name": "...", "data": { ... } } ]
}
```

#### `PUT /api/tools/loadout/{id}`
**Scope:** `loadouts:write`

Update a loadout's name, data, or public visibility.

#### `DELETE /api/tools/loadout/{id}`
**Scope:** `loadouts:write`

Delete a loadout. Must be the owner.

### Item Sets

Item sets group items together for use in auctions and rentals.

#### `GET /api/itemsets`
**Scope:** `itemsets:read`

Returns all item sets owned by the user.

#### `GET /api/itemsets/{id}`
**Scope:** `itemsets:read`

Returns a specific item set. Must be the owner.

#### `POST /api/itemsets`
**Scope:** `itemsets:write` | Rate limit: 10/min, 30/hour | Max: 50 per user, 100KB per set

Create a new item set.

```json
{
  "name": "My Armor Set",
  "data": {
    "items": [
      {
        "id": 12345,
        "name": "Adjusted HeartBeat (L)",
        "quantity": 1,
        "tier": 3,
        "tiR": 45.20,
        "currentTT": 15.50,
        "gender": "Male"
      }
    ]
  },
  "loadout_id": "optional-loadout-id"
}
```

**Item metadata fields:**

| Field | Type | Range | Applies to |
|-------|------|-------|------------|
| `tier` | integer | 0-9 | Non-(L) tierable items |
| `tiR` | float | 0-999,999 (2 decimals) | Non-(L) tierable items |
| `currentTT` | float | 0-10,000 (2 decimals) | Condition items |
| `qr` | float | 0.01-1.0 (4 decimals) | Non-(L) blueprints |
| `gender` | string | `Male`, `Female` | Armor, Clothing |
| `level` | integer | 0-200 | Pets |

**Set types:** `ArmorSet`, `ClothingSet` — for grouped equipment sets with individual pieces.

**Limits:** Max 100 items per set, max 20 armor pieces per set.

#### `PUT /api/itemsets/{id}`
**Scope:** `itemsets:write` | Rate limit: 30/min

Update an item set. Cannot modify sets linked to active rental offers.

#### `DELETE /api/itemsets/{id}`
**Scope:** `itemsets:write` | Rate limit: 10/min

Delete an item set. Must be the owner. Cannot delete sets linked to active rental offers.

### Skills

#### `GET /api/tools/skills`
**Scope:** `skills:read`

Returns the user's skill data.

```json
{
  "skills": { "Dexterity": 4523, "Anatomy": 1200 },
  "updated_at": "2026-01-15T12:00:00Z"
}
```

#### `PUT /api/tools/skills`
**Scope:** `skills:write`

Import skill data.

```json
{
  "skills": { "Dexterity": 4600, "Anatomy": 1250 },
  "trackImport": true
}
```

When `trackImport` is `true`, a diff is calculated and stored.

#### `GET /api/tools/skills/imports`
**Scope:** `skills:read`

Returns skill import history.

#### `GET /api/tools/skills/imports/{id}/deltas`
**Scope:** `skills:read`

Returns per-skill changes for a specific import.

#### `GET /api/tools/skills/history`
**Scope:** `skills:read`

Returns per-skill value history over time. Joins import records with their deltas to show how individual skill values changed across imports.

**Query parameters:**
- `skill` (optional, repeatable) — Filter by skill name(s). Example: `?skill=Anatomy&skill=Dexterity`
- `from` (optional) — ISO 8601 start date. Example: `?from=2026-01-01T00:00:00Z`
- `to` (optional) — ISO 8601 end date. Example: `?to=2026-02-01T00:00:00Z`

**Response:**
```json
[
  { "imported_at": "2026-01-15T12:00:00Z", "skill_name": "Anatomy", "new_value": 1250 },
  { "imported_at": "2026-01-20T18:00:00Z", "skill_name": "Anatomy", "new_value": 1280 }
]
```

### Exchange

#### `GET /api/market/exchange/orders`
**Scope:** `exchange:read`

Returns the user's active exchange orders.

#### `POST /api/market/exchange/orders`
**Scope:** `exchange:write` | Rate limit: 100/min, 500/hour, 3000/day

Create an exchange order.

```json
{
  "type": "BUY",
  "item_id": 12345,
  "quantity": 100,
  "markup": 135.5,
  "planet": "Calypso",
  "min_quantity": 10,
  "details": {
    "Tier": 5,
    "TierIncreaseRate": 120,
    "Gender": "Male"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | **Required.** `BUY` or `SELL` |
| `item_id` | integer | **Required.** Item database ID |
| `quantity` | integer | **Required.** Amount (min 1) |
| `markup` | number | **Required.** Markup value (see markup types below) |
| `planet` | string | Planet restriction (optional, see planets below) |
| `min_quantity` | integer | Minimum partial fill quantity (optional) |
| `details` | object | Item-specific filters (optional, see details below) |

**Order types:** `BUY`, `SELL`

**Planets:** `Calypso`, `Arkadia`, `Cyrene`, `Rocktropia`, `Next Island`, `Monria`, `Toulan`, `Howling Mine (Space)`

**Markup types:**
- **Percentage markup** (min 100%): Material, Consumable, Capsule, Enhancer, Strongbox, and stackable financial items (Deed, Token, Share)
- **Absolute markup** (PED): all other item types

**Order details fields** (all optional):

| Field | Type | Range | Applies to |
|-------|------|-------|------------|
| `Tier` | integer | 0-10 | Tierable items (Weapon, Armor, ArmorSet, Finder, Excavator, MedicalTool) |
| `TierIncreaseRate` | integer | 0-200 (0-4000 for (L) items) | Tierable items |
| `QualityRating` | integer | 1-100 | Blueprints |
| `CurrentTT` | float | ≥0 | Condition items |
| `Gender` | string | `Male` or `Female` | Required for Armor, ArmorSet, Clothing |
| `Pet.Level` | integer | ≥0 | Pets |
| `is_set` | boolean | — | ArmorPlating only (set vs individual) |

> Turnstile captcha is automatically skipped for OAuth-authenticated requests.

**Limits:** 1,000 buy + 1,000 sell orders per user; 5 per item per side; 3-minute per-item cooldown between creates/edits.

#### `POST /api/market/exchange/orders/batch`
**Scope:** `exchange:write` | Rate limit: 100/min (creates), 60/min (edits) | Max: 50 orders per batch

Create or update multiple orders in a single request. Supports partial success — each order in the batch is processed independently.

```json
{
  "orders": [
    {
      "type": "SELL",
      "item_id": 12345,
      "quantity": 50,
      "markup": 150.0
    },
    {
      "order_id": 67890,
      "type": "BUY",
      "item_id": 12345,
      "quantity": 200,
      "markup": 130.0
    }
  ]
}
```

Each order entry accepts the same fields as `POST /api/market/exchange/orders`. To **edit** an existing order, include `order_id` — the `type` and `item_id` must match the original order.

**Response:**

```json
{
  "results": [
    { "success": true, "order": { ... }, "action": "created" },
    { "success": true, "order": { ... }, "action": "updated" },
    { "success": false, "error": "Rate limit exceeded" }
  ],
  "created": 1,
  "updated": 1,
  "failed": 1
}
```

Returns HTTP 200 if any orders succeeded, 400 if all failed.

#### `PUT /api/market/exchange/orders/{id}`
**Scope:** `exchange:write` | Rate limit: 60/min

Update an order's quantity, markup, planet, min_quantity, or details. Must be the owner.

#### `DELETE /api/market/exchange/orders/{id}`
**Scope:** `exchange:write`

Close (delete) an exchange order. Must be the owner.

### Trade Requests

#### `GET /api/market/trade-requests`
**Scope:** `trades:read`

Returns trade requests involving the user.

#### `GET /api/market/trade-requests/{id}`
**Scope:** `trades:read`

Returns a specific trade request. Must be the requester or target.

**Trade request statuses:** `pending`, `active`, `completed`, `cancelled`, `expired`

> Trade request creation and cancellation are only available through the web interface.

### Auctions

Auction participation requires accepting disclaimers through the web interface first — sellers must accept the seller disclaimer, bidders must accept the bidder disclaimer. These cannot be accepted via the API.

#### `GET /api/auction`
**Scope:** `auction:read` | Query params below

List public auctions.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | `active` | Filter: `active`, `ended`, `settled`, `cancelled` |
| `search` | string | — | Search titles (max 100 chars) |
| `sort` | string | `ends_at` | Sort by: `ends_at`, `created_at`, `current_bid`, `bid_count`, `starting_bid` |
| `order` | string | `asc` | Sort order: `asc` or `desc` |
| `limit` | integer | 24 | Results per page (1-100) |
| `offset` | integer | 0 | Pagination offset |

#### `GET /api/auction/my`
**Scope:** `auction:read`

Returns the user's auctions (all statuses including drafts).

#### `POST /api/auction`
**Scope:** `auction:write` | Rate limit: 5/hour | Max: 20 active/draft per user

Create a new auction. Requires accepted seller disclaimer.

```json
{
  "title": "Rare Weapon",
  "description": "Optional rich text description",
  "starting_bid": 100.00,
  "buyout_price": 500.00,
  "duration_days": 7,
  "item_set_id": "set-id"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Auction title (max 120 chars) |
| `description` | string | Rich text description (max 5000 chars, optional) |
| `starting_bid` | float | Starting bid in PED (0.01 – 10,000,000) |
| `buyout_price` | float | Instant-buy price (optional, must be ≥ starting_bid, max 10,000,000) |
| `duration_days` | integer | Auction duration (1-30 days, or 1-365 for buyout-only) |
| `item_set_id` | string | ID of your item set to auction |

**Auction statuses:** `draft`, `active`, `frozen`, `ended`, `settled`, `cancelled`

**Anti-sniping:** Bids placed within 5 minutes of the auction end extend the deadline by 5 minutes (max 30 minutes total extension).

#### `PUT /api/auction/{id}`
**Scope:** `auction:write`

Update an auction. Use `{ "action": "activate" }` to activate a draft. Only drafts can be fully edited — active auctions have limited editable fields.

#### `DELETE /api/auction/{id}`
**Scope:** `auction:write`

Delete a draft auction. Must be the seller.

#### `POST /api/auction/{id}/bid`
**Scope:** `auction:write` | Rate limit: 10/min

Place a bid on an auction. Requires accepted bidder disclaimer.

```json
{ "amount": 150.00 }
```

Bids must meet the minimum increment (2% of current bid, rounded to a neat value like 0.01, 0.05, 0.10, 1, 5, 10, 50, 100, etc). Minimum bid: 0.01 PED.

#### `POST /api/auction/{id}/buyout`
**Scope:** `auction:write` | Rate limit: 5/min

Buy out an auction at the listed buyout price. Requires accepted bidder disclaimer.

#### `POST /api/auction/{id}/settle`
**Scope:** `auction:write` | Rate limit: 10/min

Settle a completed auction. Must be the seller.

### Rentals

#### `GET /api/rental/my`
**Scope:** `rental:read` | Query: `type` (`offers` or `requests`)

Returns the user's rental offers or requests.

#### `POST /api/rental`
**Scope:** `rental:write` | Rate limit: 5/min | Max: 20 offers per user

Create a rental offer.

```json
{
  "item_set_id": "set-id",
  "title": "Mining Amp Rental",
  "description": "...",
  "price_per_day": 10.00,
  "deposit": 50.00,
  "planet_id": 1,
  "location": "Twin Peaks",
  "discounts": [
    { "minDays": 7, "percent": 10 },
    { "minDays": 30, "percent": 25 }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `item_set_id` | string | **Required.** ID of the item set to rent |
| `title` | string | **Required.** Listing title (max 120 chars) |
| `description` | string | Rich text description (max 5000 chars, optional) |
| `price_per_day` | float | **Required.** Daily rate in PED (0.01 – 100,000) |
| `deposit` | float | Security deposit in PED (max 1,000,000, optional) |
| `planet_id` | integer | Planet restriction (optional) |
| `location` | string | Meetup location (max 200 chars, optional) |
| `discounts` | array | Volume discount tiers (max 5, optional) |

**Discount tiers:** Each tier has `minDays` (2-365) and `percent` (1-99%). Tiers are auto-sorted by minDays ascending.

**Rental statuses:** `draft`, `available`, `unlisted`

**Status transitions:** `draft` → `available`, `available` → `draft` / `unlisted`, `unlisted` → `available`

#### `PUT /api/rental/{id}`
**Scope:** `rental:write` | Rate limit: 20/min

Update a rental offer. Only drafts allow full field changes. For non-draft offers, only status, description, location, and pricing can be updated.

#### `DELETE /api/rental/{id}`
**Scope:** `rental:write` | Rate limit: 10/min

Delete a rental offer. Cannot delete offers with active rental requests.

#### `POST /api/rental/{id}/blocked-dates`
**Scope:** `rental:write` | Rate limit: 20/min

Add blocked dates to a rental offer.

#### `DELETE /api/rental/{id}/blocked-dates`
**Scope:** `rental:write` | Rate limit: 20/min

Remove blocked dates from a rental offer.

### Services

#### `GET /api/services/my`
**Scope:** `services:read`

Returns the user's service listings.

#### `POST /api/services`
**Scope:** `services:write` | Rate limit: 5/min, 15/hour

Create a new service listing.

**Service types:** `healing`, `dps`, `transportation`, `crafting`, `hunting`, `mining`, `custom`

For `custom` type, include `custom_type_name` in the request body. Max 50 equipment items per service.

#### `PUT /api/services/{id}`
**Scope:** `services:write`

Update a service listing. Must be the owner.

#### `DELETE /api/services/{id}`
**Scope:** `services:write`

Delete a service listing. Must be the owner.

#### `PUT /api/services/{id}/availability`
**Scope:** `services:write`

Update service availability status.

#### `PUT /api/services/{id}/location`
**Scope:** `services:write`

Update service location.

#### `POST /api/services/{id}/equipment`
**Scope:** `services:write`

Add equipment to a service.

#### `PUT /api/services/{id}/equipment`
**Scope:** `services:write`

Update service equipment.

#### `POST /api/services/{id}/pilots`
**Scope:** `services:write`

Add a pilot to a service.

#### `DELETE /api/services/{id}/pilots`
**Scope:** `services:write`

Remove a pilot from a service.

#### `POST /api/services/{id}/flights`
**Scope:** `services:write`

Create a flight for a warp service. Must be the owner.

#### `PUT /api/services/{id}/flights/{flightId}`
**Scope:** `services:write`

Update a flight. Must be the owner or pilot.

#### `GET /api/services/my/requests`
**Scope:** `services:read`

Returns service requests for the user.

#### `PUT /api/services/my/requests/{requestId}/status`
**Scope:** `services:write`

Update a service request status. Must be the provider.

### Notifications

#### `GET /api/notifications`
**Scope:** `notifications:read` | Query: `page` (default 1), `pageSize` (5-50, default 10)

Returns paginated notifications.

```json
{
  "rows": [...],
  "total": 42,
  "unread": 3,
  "page": 1,
  "pageSize": 10
}
```

#### `POST /api/notifications/read-all`
**Scope:** `notifications:write`

Mark all notifications as read.

#### `PATCH /api/notifications/{id}`
**Scope:** `notifications:write`

Update a single notification (mark as read).

### Streams

#### `GET /api/streams`
**Public** (no authentication required)

Returns all active content creators with their current live status.

```json
{
  "creators": [
    {
      "id": 1,
      "name": "StreamerName",
      "platform": "twitch",
      "channel_url": "https://twitch.tv/...",
      "avatar_url": "https://...",
      "is_live": true,
      "stream_title": "Hunting Atrox!",
      "game_name": "Entropia Universe",
      "viewer_count": 42
    }
  ]
}
```

### Preferences

User preferences store arbitrary JSON data under namespaced keys. Each preference is a key-value pair where the value can be any JSON object up to 20KB.

**Allowed key prefixes:** `exchange.`, `darkMode`, `construction.`, `loadouts`, `wiki.`, `services.`

Keys must match one of these prefixes exactly or start with one followed by a dot. Max key length: 100 characters.

#### `GET /api/users/preferences`
**Scope:** `preferences:read`

Returns all user preferences as a `{key: data}` map.

#### `GET /api/users/preferences/{key}`
**Scope:** `preferences:read`

Returns a single preference by key.

#### `PUT /api/users/preferences`
**Scope:** `preferences:write` | Rate limit: 30/min | Max: 20KB per value, 50 keys per user

Set a user preference.

```json
{
  "key": "exchange.favourites",
  "data": { "items": [12345, 67890] }
}
```

#### `DELETE /api/users/preferences/{key}`
**Scope:** `preferences:write`

Delete a user preference.

### Societies

#### `GET /api/societies`
**Scope:** `societies:read` | Query: `query` (search term)

Search for societies by name.

#### `GET /api/societies/{identifier}`
**Scope:** `societies:read`

Returns a society by ID or abbreviation.

#### `POST /api/societies`
**Scope:** `societies:write`

Create a new society.

```json
{
  "name": "My Society",
  "abbreviation": "MS",
  "description": "A great society",
  "discord": "https://discord.gg/..."
}
```

#### `PATCH /api/societies/{identifier}`
**Scope:** `societies:write`

Update a society. Must be the leader.

```json
{
  "description": "Updated description",
  "discord": "https://discord.gg/...",
  "discordPublic": true
}
```

#### `POST /api/societies/join`
**Scope:** `societies:write`

Join a society.

```json
{ "societyId": "society-id" }
```

#### `POST /api/societies/{id}/disband`
**Scope:** `societies:write`

Disband a society. Must be the leader.

### Guides

The `guides:write` scope grants `guide.create` and `guide.edit` permissions. Deletion of guide content is not available via the API.

Guide content uses sanitized rich text (HTML) for descriptions and paragraph content.

#### `POST /api/guides`
**Scope:** `guides:write`

Create a guide category.

```json
{
  "title": "Mining Guide",
  "description": "Optional description",
  "sort_order": 0
}
```

#### `PUT /api/guides/{categoryId}`
**Scope:** `guides:write`

Update a guide category's title, description, or sort order.

#### `POST /api/guides/{categoryId}/chapters`
**Scope:** `guides:write`

Create a chapter within a guide category.

```json
{
  "title": "Chapter Title",
  "description": "Optional description",
  "sort_order": 0
}
```

#### `PUT /api/guides/{categoryId}/chapters/{chapterId}`
**Scope:** `guides:write`

Update a chapter.

#### `POST /api/guides/{categoryId}/chapters/{chapterId}/lessons`
**Scope:** `guides:write`

Create a lesson within a chapter.

```json
{
  "title": "Lesson Title",
  "slug": "lesson-slug"
}
```

#### `PUT /api/guides/{categoryId}/chapters/{chapterId}/lessons/{lessonId}`
**Scope:** `guides:write`

Update a lesson's title, slug, or sort order.

#### `POST /api/guides/{categoryId}/chapters/{chapterId}/lessons/{lessonId}/paragraphs`
**Scope:** `guides:write`

Create a paragraph within a lesson.

```json
{
  "content_html": "<p>Paragraph content...</p>",
  "sort_order": 0
}
```

#### `PUT /api/guides/{categoryId}/chapters/{chapterId}/lessons/{lessonId}/paragraphs/{paragraphId}`
**Scope:** `guides:write`

Update a paragraph's content or sort order.

#### `PUT /api/guides/{categoryId}/chapters/{chapterId}/lessons/{lessonId}/paragraphs`
**Scope:** `guides:write`

Reorder paragraphs within a lesson.

```json
{
  "orderedIds": [3, 1, 2]
}
```

### Image Uploads

Images are uploaded as `multipart/form-data`. The upload system supports multiple target types beyond database entities — including user profiles, rich text content, auction item sets, and guide banners.

Uploaded images are processed server-side: validated (magic bytes), resized, and converted to WebP. Most uploads go into a **pending queue** for admin approval. Some types are auto-approved:
- `guide-category`, `announcement` — auto-approved (requires appropriate permissions)
- `item-set` — auto-approved (requires at least one (C) tagged item)
- `richtext` — auto-approved if the user has `wiki.approve` or `guide.edit` grants
- **Admin uploads** — any upload by a user with `admin.panel` grant is auto-approved

Re-uploading for the same target overwrites your previous pending upload.

**Processing dimensions:**

| Type | Output size |
|------|-------------|
| Standard entities | 320×320 icon + 128×128 thumbnail |
| Banners (`guide-category`, `announcement`) | 1200px width |
| Item sets | 320×480 max (fit, portrait) |
| Rich text | Preserves aspect ratio |

**Constraints:** Max 2MB file, max 8192×8192 pixels, min 32×32 pixels. Allowed formats: JPEG, PNG, WebP, GIF (verified via magic bytes).

#### `POST /api/uploads/entity-image`
**Scope:** `uploads:write` | Rate limit: 50/5min | Max: 3MB

Upload an image for any supported target. Send as `multipart/form-data`.

| Field | Type | Description |
|-------|------|-------------|
| `image` | File | The image file (JPEG, PNG, WebP, GIF) |
| `entityType` | string | Target type (see below) |
| `entityId` | string | Target identifier |
| `entityName` | string | *(optional)* Display name for admin review |

**Supported target types:**

| Category | Types |
|----------|-------|
| Items | `weapon`, `armorset`, `material`, `blueprint`, `clothing`, `vehicle`, `pet`, `strongbox` |
| Tools | `tool`, `misctool`, `refiner`, `scanner`, `finder`, `excavator`, `teleportationchip`, `effectchip` |
| Attachments | `attachment`, `weaponamplifier`, `weaponvisionattachment`, `absorber`, `finderamplifier`, `armorplating`, `enhancer`, `mindforceimplant` |
| Consumables | `consumable`, `capsule`, `medicaltool`, `medicalchip` |
| Furnishings | `furnishing`, `furniture`, `decoration`, `storagecontainer`, `sign` |
| Information | `mob`, `skill`, `profession`, `vendor`, `location`, `area`, `shop` |
| Other | `guide-category`, `richtext`, `announcement`, `item-set` |

For `richtext` uploads, the `entityId` is ignored — a content hash is computed automatically for deduplication. If an identical image already exists, the existing URL is returned immediately.

For `item-set` uploads, the item set must belong to you and contain at least one item with a `(C)` tag.

**Response:**

```json
{
  "success": true,
  "approved": false,
  "tempPath": "uuid",
  "previewUrl": "/api/uploads/preview/uuid"
}
```

When `approved` is `true`, the image is live immediately. When `false`, it awaits admin review.

#### `POST /api/image/user/{userId}`
**Scope:** `uploads:write`

Upload a profile image. You can only update your own profile image.

#### `DELETE /api/image/user/{userId}`
**Scope:** `uploads:write`

Delete a profile image. You can only delete your own profile image.

### Ingestion

Crowdsourced trade messages and global events. Submit data from your chat log and receive confirmed data from other players. **No specific scopes required** — any verified OAuth-authenticated user can access these endpoints.

#### `POST /api/ingestion/globals`

Submit a batch of global events (kills, deposits, crafts, rare items). Supports gzip-compressed request bodies (`Content-Encoding: gzip`).

**Body:**
```json
{
  "globals": [
    {
      "timestamp": "2026-02-28T15:30:45",
      "type": "kill",
      "player": "PlayerName",
      "target": "MobName",
      "value": 100.00,
      "unit": "PED",
      "location": "Takuta Plateau",
      "hof": false,
      "ath": false
    }
  ]
}
```

**Limits:** Max 500 entries per batch, timestamps within last 24 hours, 6 requests per 60 seconds.

**Response:** `{ "accepted": 5, "duplicates": 2, "conflicts": 0, "total": 7, "invalid": 0 }`

#### `POST /api/ingestion/trade`

Submit a batch of trade chat messages. Same compression and rate limit rules.

**Body:**
```json
{
  "trades": [
    {
      "timestamp": "2026-02-28T15:30:45",
      "channel": "Local Trade",
      "username": "TraderJohn",
      "message": "WTS [Item Name] +50"
    }
  ]
}
```

#### `GET /api/ingestion/globals`

Fetch global events newer than a timestamp (distribution endpoint).

| Parameter | Type | Description |
|-----------|------|-------------|
| `since` | string | **Required.** ISO timestamp cursor |
| `limit` | integer | Max results (default 200, max 1000) |

**Response:** `{ "globals": [...], "cursor": "2026-02-28T15:31:00Z" }`

Each global includes a `confirmed` boolean (true when confirmation threshold is met) and `confirmations` count.

#### `GET /api/ingestion/trade`

Fetch trade messages newer than a timestamp.

| Parameter | Type | Description |
|-----------|------|-------------|
| `since` | string | **Required.** ISO timestamp cursor |
| `limit` | integer | Max results (default 200, max 1000) |

**Response:** `{ "trades": [...], "cursor": "2026-02-28T15:31:00Z" }`

Each trade includes a `confirmations` count.

---

## Error Responses

All endpoints return errors in a consistent format:

```json
{
  "error": "Error message describing what went wrong"
}
```

| Status | Meaning |
|--------|---------|
| 400 | Invalid request parameters |
| 401 | Missing or invalid authentication |
| 403 | Insufficient permissions or scope |
| 404 | Resource not found |
| 409 | Conflict (e.g., order limit reached) |
| 413 | Request too large |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

## Rate Limiting

Rate limits vary by endpoint. When rate limited, the API returns a `429` status with a `retryAfter` field (seconds). OAuth-authenticated requests bypass Turnstile captcha requirements but are still subject to rate limits.

## CORS

All OAuth-authenticated responses include CORS headers (`Access-Control-Allow-Origin: *`), enabling direct browser-based API calls from any origin. The Data API (`api.entropianexus.com`) also supports CORS for all origins.
