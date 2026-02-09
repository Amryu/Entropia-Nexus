# Market System

Player-to-player trading features including the exchange and shop directory.

## Exchange

A trading platform for buying and selling items between players.

### Features

- **Category Browser**: Hierarchical tree navigation for item categories
- **Planet Filter**: Filter by trading location
- **Item Type Filters**:
  - Limited (L) vs Unlimited (UL)
  - Sex filter for clothing
  - Tier/TiR filters for tierable items
  - QR filter for blueprints
- **Buy/Sell Orders**: Create and manage trade orders with real-time API
- **Order Freshness**: Filter by last update time
- **Offer Staleness**: Active (<3d), Stale (3-7d), Expired (7-30d), Terminated (>30d)
- **My Offers**: View, bump, edit, and close your offers
- **Inventory System**: Import items via JSON, manage server-stored inventory
- **Shopping Cart**: Add sell offers to cart, group by seller/planet, checkout creates trade requests
- **Buy/Sell Now**: Click Buy/Sell buttons on order rows to create instant trade requests
- **Bulk Buy/Sell**: Tab in OrderDialog for batch purchasing with quantity/min/max/planet filters
- **User Offers Panel**: Click seller names to view all their offers in a floating panel
- **Trade Requests**: Track active trades with Discord thread integration
- **Price Suggestions**: Match best offer, undercut/outbid with tiered amounts
- **Exchange Pricing**: Derived price data from active exchange offers

### Routes

```
/market/exchange/                    - Main exchange view
/market/exchange/[[slug]]            - Category selected
/market/exchange/[[slug]]/[[id]]     - Item detail with orders
```

### Components

```
nexus/src/routes/market/exchange/[[slug]]/[[id]]/
├── +page.svelte                - Route entry
├── ExchangeBrowser.svelte      - Main exchange UI coordinator
├── CategoryTree.svelte         - Category navigation
├── OrderDialog.svelte          - Create/edit order modal with price suggestions + bulk tab
├── OrderBookTable.svelte       - FancyTable wrapper for buy/sell orders
├── OrderStatusBadge.svelte     - Color-coded staleness badge
├── MyOffersView.svelte         - User's offers management (bump/edit/close)
├── InventoryImportDialog.svelte - JSON import wizard
├── InventoryPanel.svelte       - Inventory browser and management
├── CartSummary.svelte          - Shopping cart with seller grouping + checkout
├── FavouritesTree.svelte       - Favourites sidebar with folders and drag-and-drop
├── QuickTradeDialog.svelte     - Buy Now / Sell Now confirmation dialog
├── UserOffersPanel.svelte      - View a specific user's active offers
├── TradeRequestsPanel.svelte   - View/manage trade requests in floating panel
└── orderUtils.js               - Order calculation helpers
```

### State Management

```
nexus/src/routes/market/exchange/exchangeStore.js    - Svelte stores (myOffers, inventory, cart, showTrades, tradeRequests)
nexus/src/routes/market/exchange/favouritesStore.js   - Favourites store with folder management
nexus/src/routes/market/exchange/exchangeConstants.js - Constants and helpers (staleness, undercut tiers)
```

### Order Types

| Field | Description |
|-------|-------------|
| Type | 'Buy' or 'Sell' |
| Item | Item reference (name, type, maxTT) |
| Planet | Trading location |
| Quantity | Number of items (1 for instance items) |
| Markup | Percentage or +PED value |
| CurrentTT | Current TT value (for condition items) |
| Metadata | Tier, TiR, QR, Pet info |

### Price Calculation

**Percent Markup Items** (stackables, L items):
```
Unit Price = MaxTT × (Markup / 100)
Total = Quantity × Unit Price
```

**Absolute Markup Items** (condition items):
```
Unit Price = CurrentTT + Markup
Total = Quantity × Unit Price
```

**Blueprints**:
```
Unit Price = (QR / 100) + Markup
```

### Tierable Items

Items that can have tier levels:
- Weapons
- Armor
- Finders
- Excavators
- Medical Tools

Metadata stored:
```json
{
  "Tier": 7.5,
  "TierIncreaseRate": 150
}
```

### Pet Orders

Pet orders include additional metadata:
```json
{
  "Pet": {
    "Level": 10,
    "Experience": 5000,
    "Skills": [
      { "Level": 3, "Name": "Increased Run Speed" }
    ],
    "Food": 100
  }
}
```

### Database

**Table**: `trade_offers` (nexus-users)

| Column | Type | Description |
|--------|------|-------------|
| id | serial | Primary key |
| user_id | bigint | Owner (Discord ID) |
| type | trade_offer_type | 'BUY' or 'SELL' |
| item_id | integer | Item reference |
| quantity | integer | Number of items |
| min_quantity | integer | Min quantity (optional) |
| markup | numeric | Price modifier |
| planet | varchar(50) | Trading planet |
| details | jsonb | Item name, tier, TiR, pet info |
| state | trade_offer_state | active/stale/expired/terminated/closed |
| bumped_at | timestamptz | Last bump time (determines staleness) |
| created | timestamptz | Creation time |
| updated | timestamptz | Last update |

Unique constraint: 1 active offer per user per item per side.
Limit: 50 offers per side per user.

**Table**: `user_items` (nexus-users)

| Column | Type | Description |
|--------|------|-------------|
| id | serial | Primary key |
| user_id | bigint | Owner (Discord ID) |
| item_id | integer | Item reference |
| item_name | varchar(255) | Item name |
| quantity | integer | Stack count |
| instance_key | varchar(255) | Null=fungible, non-null=unique instance |
| details | jsonb | Tier, condition, QR, pet data |
| storage | varchar(10) | 'server' or 'local' |
| updated_at | timestamptz | Last update |

### Staleness Thresholds

| State | Age since bumped_at | Computed on |
|-------|---------------------|-------------|
| Active | < 3 days | Read (SQL CASE) |
| Stale | 3-7 days | Read (SQL CASE) |
| Expired | 7-30 days | Read (SQL CASE) |
| Terminated | > 30 days | Read (SQL CASE) |
| Closed | User action | Explicit state |

### API Endpoints

```
GET  /api/market/exchange                          - Get categorized items for trading
GET  /api/market/exchange/offers                   - User's own offers (My Offers)
POST /api/market/exchange/offers                   - Create a new offer
PUT  /api/market/exchange/offers/[id]              - Edit an offer
DELETE /api/market/exchange/offers/[id]             - Close an offer (soft delete)
POST /api/market/exchange/offers/[id]/bump         - Bump an offer (reset staleness)
GET  /api/market/exchange/offers/item/[itemId]     - Order book for an item
GET  /api/market/exchange/offers/user/[userId]     - All active offers by a user (public)
GET  /api/market/trade-requests                    - User's trade requests
POST /api/market/trade-requests                    - Create/append trade request
GET  /api/market/trade-requests/[id]               - Single trade request with items
POST /api/market/trade-requests/[id]/cancel        - Cancel a trade request
GET  /api/users/inventory                          - User's server inventory
PUT  /api/users/inventory                          - Bulk upsert inventory (import)
DELETE /api/users/inventory/[id]                   - Remove inventory item
GET  /api/market/prices/exchange/[itemId]           - Exchange-derived price data
```

### Undercut / Outbid System

Price suggestions use a 2% relative undercut formula:

**Percent-markup items** (stackables, L items):
```
undercut_amount = 2% × (markup - 100)
```
Example: 150% → 2% × 50 = 1.0 → undercut to 149%. Minimum: 0.01 percentage points.

**Absolute-markup items** (condition items):
```
undercut_amount = 2% × markup
```
Example: +50 PED → 2% × 50 = 1.0 → undercut to +49 PED. Minimum: 0.01 PED.

For buy orders the same formula is used but the amount is *added* (outbid).

### Price Suggestions

Three suggestion buttons in the order dialog:
- **Match Best**: Sets markup to the best opposing offer
- **Undercut / Outbid**: Applies the 2% relative undercut formula
- **Daily Avg**: Uses the most recent daily average price from historical data (shown when available)

Suggestions are available in both create and edit modes.

### Partial Trades

Fungible items support partial trades via `min_quantity`:
- **Allow Partial** checkbox in the order dialog
- Default min quantity: 20% of total quantity (minimum 1)
- Stored in the `min_quantity` column of `trade_offers`
- Instance items (tierable, condition, blueprints, pets) do not support partial trades

### Edit Existing Offer

When a user already has a buy or sell order for an item:
- The button changes to "Edit Buy" / "Edit Sell"
- Clicking opens the existing order in edit mode with pre-populated values
- Saving updates the existing offer (PUT) and resets staleness

### Favourites

Users can star items to add them to favourites. Favourites appear in the sidebar and support:
- **Folders**: Create, rename, delete folders to organize favourites
- **Drag-and-Drop**: Move items between folders (HTML5 native DnD)
- **Star Toggle**: Click the star in the detail title bar to add/remove
- **Persistence**: Stored via the user preferences system (DB when logged in, localStorage otherwise)

Data stored under preference key `exchange.favourites`:
```json
{
  "folders": [
    { "id": "uuid", "name": "Mining Gear", "items": [1000124, 2000081], "order": 0 }
  ],
  "items": [3000789]
}
```

### User Preferences System

Centralized preference storage that abstracts localStorage vs database persistence.

**Client utility**: `nexus/src/lib/preferences.js`
- `createPreference(key, defaultValue, options?)` — creates a Svelte writable store
- Writes to localStorage immediately, syncs to DB when logged in
- On login: migrates localStorage → DB if DB has no entry for the key
- Option `{ debounceMs }` for frequently-changing preferences

**Server module**: `nexus/src/lib/server/preferences.js`
- Validates keys against allowed prefixes
- Enforces 20KB max per key, 50 keys max per user

**Database**: `user_preferences` table (nexus-users)

| Column | Type | Description |
|--------|------|-------------|
| user_id | bigint | User Discord ID (PK) |
| key | text | Preference key (PK) |
| data | jsonb | Preference data |
| updated_at | timestamptz | Last update |

**Allowed key prefixes**: `exchange.`, `darkMode`, `construction.`, `loadouts`, `wiki.`, `services.`

**API Endpoints**:
```
GET    /api/users/preferences           - All preferences for logged-in user
PUT    /api/users/preferences           - Upsert { key, data }
GET    /api/users/preferences/[key]     - Single preference
DELETE /api/users/preferences/[key]     - Delete preference
```

### Trade Request System

Players can initiate trades by clicking Buy/Sell buttons on order rows, using the bulk trade feature, or checking out from the cart. These actions create trade requests that are managed through Discord threads.

#### Flow

1. **User clicks Buy/Sell** on an order row -> QuickTradeDialog opens
2. **User confirms** -> POST `/api/market/trade-requests` creates a trade request (requires `market.trade` grant)
3. **Bot polls** every 30s, finds pending requests, creates private Discord threads
4. **Both users** are added to the thread to negotiate
5. **Thread activity** is tracked; after 18h inactivity a warning is sent
6. **After 24h** inactivity the trade is auto-expired and thread is locked/archived
7. **`/done` command** marks the trade as completed and locks the thread

#### Grants

| Grant | Description |
|-------|-------------|
| `market.trade` | Create trade requests (Buy/Sell Now, cart checkout) |
| `market.bulk` | Use bulk buy/sell feature to create multiple trade requests |

#### Trade Request Lifecycle

| Status | Description |
|--------|-------------|
| `pending` | Just created, waiting for bot to create Discord thread |
| `active` | Discord thread created, users negotiating |
| `completed` | Marked complete via `/done` command |
| `cancelled` | One party cancelled |
| `expired` | Auto-closed after 24h inactivity |

Only one open request (pending or active) is allowed between any two users at a time. If a user initiates another trade with the same person, items are appended to the existing request.

#### Bulk Buy/Sell

Tab 2 in the OrderDialog allows bulk trading:
- **Quantity needed**: Total quantity to acquire
- **Min offer amount**: Only consider offers with at least this quantity (0 = no minimum)
- **Max traders**: Maximum number of different traders (slider 0-20, default 5)
- **Planet**: Filter by planet

Preview shows matched offers sorted by best markup. Confirm creates one trade request per matched trader.

#### Database Tables

**`trade_requests`** (nexus-users):

| Column | Type | Description |
|--------|------|-------------|
| id | serial | Primary key |
| requester_id | bigint | Requesting user (Discord ID) |
| target_id | bigint | Target user (Discord ID) |
| status | text | pending/active/completed/cancelled/expired |
| planet | text | Trading planet (optional) |
| discord_thread_id | text | Discord thread ID (set by bot) |
| last_activity_at | timestamptz | Last activity timestamp |
| warning_sent | boolean | Whether inactivity warning was sent |
| created_at | timestamptz | Creation time |
| closed_at | timestamptz | When request was closed |

Unique constraint: Only 1 open request between any pair of users, using `LEAST/GREATEST` for direction-independence.

**`trade_request_items`** (nexus-users):

| Column | Type | Description |
|--------|------|-------------|
| id | serial | Primary key |
| trade_request_id | integer | FK to trade_requests |
| offer_id | integer | Reference to trade_offers (optional) |
| item_id | integer | Item reference |
| item_name | text | Item display name |
| quantity | integer | Quantity to trade |
| markup | numeric | Markup value |
| side | text | 'BUY' or 'SELL' (the offer side) |
| added_at | timestamptz | When item was added |

#### API Endpoints

```
GET  /api/market/trade-requests                - User's trade requests
POST /api/market/trade-requests                - Create/append trade request (market.trade)
GET  /api/market/trade-requests/[id]           - Single trade request with items
POST /api/market/trade-requests/[id]/cancel    - Cancel a trade request
GET  /api/market/exchange/offers/user/[userId] - All active offers by a user (public)
```

#### Server Lib

`nexus/src/lib/server/trade-requests.js` provides:
- `getOrCreateTradeRequest(requesterId, targetId, planet, items)` — Transaction-safe; appends to existing open request or creates new
- `getUserTradeRequests(userId)` — All requests where user is party, with partner names and item counts
- `getTradeRequest(requestId)` — Full request with items array
- `cancelTradeRequest(requestId, userId)` — Cancel (only parties can cancel)
- `getUserPublicOffers(userId)` — All active offers by a user
- Bot functions: `getPendingTradeRequests`, `getWarnableTradeRequests`, `getExpirableTradeRequests`, `findTradeRequestByThread`, `updateLastActivity`, `setTradeRequestThread`

#### Discord Bot Integration

- **Channel**: Configured via `/channel set trade #channel-name`
- **Thread creation**: Private threads named "Trade: User1 <-> User2"
- **Activity tracking**: `messageCreate` event updates `last_activity_at`
- **Warning**: Sent at 18h inactivity (once per request)
- **Expiry**: Thread locked and archived at 24h inactivity
- **`/done` command**: Only usable by trade participants in trade threads

### Local Storage (Legacy)

Filter preferences persisted (will be migrated to user preferences over time):
- `exchangeFilters.v1` - Category, planet, type filters
- `exchangeOrderPrefs.v1` - Order creation preferences

---

## Shops

Player shop directory with inventory management.

### Features

- **Shop Directory**: Browse shops by planet
- **Inventory Display**: Items organized by groups
- **Shop Management**: Owner and manager roles
- **Waypoint Links**: Navigate to shop locations

### Routes

```
/market/shops/              - Shop list
/market/shops/[[slug]]      - Shop detail with inventory
```

### Shop Data Structure

```json
{
  "Id": 123,
  "Name": "Shop Name",
  "Owner": {
    "Name": "OwnerName",
    "Id": "discord_id"
  },
  "Planet": {
    "Name": "Calypso",
    "Properties": {
      "TechnicalName": "Planet_Calypso"
    }
  },
  "Coordinates": {
    "Longitude": 12345,
    "Latitude": 67890
  },
  "InventoryGroups": [
    {
      "Name": "Weapons",
      "Items": [
        { "ItemId": 456, "Name": "Item Name", "Quantity": 5, "Price": 100 }
      ]
    }
  ]
}
```

### Database Tables (nexus-users)

#### `shop_inventory_groups`

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| shop_id | integer | Shop reference |
| name | text | Group name |
| sort_order | integer | Display order |

#### `shop_inventory_items`

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| group_id | integer | Group reference |
| item_id | integer | Item reference (from API) |
| name | text | Item name |
| quantity | integer | Stock count |
| price | numeric | Selling price |

#### `shop_managers`

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| shop_id | integer | Shop reference |
| user_id | bigint | Manager Discord ID |
| can_edit | boolean | Edit permissions |

### API Endpoints

```
GET    /api/shops/:shop/inventory   - Get shop inventory
POST   /api/shops/:shop/inventory   - Update inventory
GET    /api/shops/:shop/managers    - List managers
POST   /api/shops/:shop/managers    - Add manager
DELETE /api/shops/:shop/managers    - Remove manager
```

### Shop Planets

Available planet filters:
- Calypso (Cly)
- ARIS (Ars)
- Cyrene (Cyr)
- Arkadia (Ark)
- Monria (Mnr)
- ROCKtropia (Rck)
- Toulan (Tou)
- Next Island (NI)

---

## Price Tracking

Historical item price observations with pre-computed summaries for charting.

### Price Formats

- **Stackable items**: percentage markup (e.g., `123.4567` = 123.4567% of MaxTT)
- **Condition items** (`hasCondition()` = true): flat absolute markup (e.g., `45.0000` = +45 PED)

The `price_value` column stores the raw number; interpretation depends on item type.

### Database Tables (nexus-users)

#### `item_prices` — Raw observations

| Column | Type | Description |
|--------|------|-------------|
| id | bigserial | Primary key |
| item_id | integer | Composite item ID |
| price_value | numeric(12,4) | Markup value |
| quantity | integer | Traded quantity (for WAP) |
| source | text | NULL = aggregate, or specific source |
| recorded_at | timestamptz | Observation time |

#### `item_price_summaries` — Pre-computed rollups

| Column | Type | Description |
|--------|------|-------------|
| id | bigserial | Primary key |
| item_id | integer | Composite item ID |
| source | text | Source filter |
| period_type | enum | 'hour', 'day', 'week' |
| period_start | timestamptz | Start of period |
| price_min/max/avg | numeric(12,4) | Basic stats |
| price_p5/median/p95 | numeric(12,4) | Percentiles |
| price_wap | numeric(12,4) | Volume-weighted average |
| volume | bigint | Total traded quantity |
| sample_count | integer | Number of observations |

#### `item_price_summary_watermarks` — Incremental computation tracking

One row per period type, tracks `last_computed_until` for watermark-based processing.

### API Endpoints

```
GET  /api/market/prices/[itemId]    - Price history (raw or summary)
GET  /api/market/prices/latest      - Latest prices (batch)
POST /api/market/prices/ingest      - Insert price data (admin)
POST /api/market/prices/summarize   - Trigger summary computation (admin)
```

#### Price History

`GET /api/market/prices/[itemId]?from=&to=&granularity=auto&source=&limit=500`

Granularity options: `raw`, `hour`, `day`, `week`, `auto`

Auto-granularity selects based on time range:
- ≤ 48h → raw, ≤ 30d → hour, ≤ 365d → day, > 365d → week

#### Latest Prices

`GET /api/market/prices/latest?items=1000124,2000081&source=`

Returns most recent price per item using `DISTINCT ON`.

#### Ingest

`POST /api/market/prices/ingest` (admin-only)

```json
{ "prices": [{ "item_id": 1000124, "price_value": 123.45, "quantity": 10, "source": "auction" }] }
```

Max 1000 per request. Bot can also insert directly via `nexus-bot/db.js`.

### Summary Computation

Bot runs `computeAllPriceSummaries()` every 15 minutes. Uses watermark-based incremental processing — only aggregates new raw data since last run. Computes min, max, avg, p5, median, p95, WAP, and volume per item/source/period bucket.

---

## Integration with Services

The market section works alongside the services marketplace:

- **Exchange**: One-time item trades
- **Shops**: Persistent storefronts
- **Services**: Recurring service offerings (healing, DPS, transport)

See `docs/services.md` for service marketplace documentation.
