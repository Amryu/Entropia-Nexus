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
- **Order Staleness**: Active (<3d), Stale (3-7d), Expired (7-30d), Terminated (>30d)
- **My Orders**: View, bump, edit, and close your orders
- **Inventory System**: Full-sync import from EU API with diff preview, order coverage checking
- **Inventory Editing**: Inline config for item metadata (Tier, TiR, QR, value, quantity) with auto-save
- **Sell from Inventory**: Create sell orders directly from inventory rows with pre-filled data
- **Order Coverage**: Standalone dialog to check/adjust sell orders exceeding inventory
- **Shopping Cart**: Add sell orders to cart, group by seller/planet, checkout creates trade requests
- **TT Badge**: Non-condition items show their TT value next to the item name in detail view
- **Buy/Sell Now**: Click Buy/Sell buttons on order rows to create instant trade requests
- **Bulk Buy/Sell**: Tab in OrderDialog for batch purchasing with quantity/min/max/planet filters
- **User Orders Panel**: Click seller names to view all their orders in a floating panel
- **Trade Requests**: Track active trades with Discord thread integration
- **Price Suggestions**: Match best order, undercut/outbid with tiered amounts
- **Exchange Pricing**: Derived price data from active exchange orders

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
├── MyOrdersView.svelte         - User's orders management (bump/edit/close)
├── InventoryImportDialog.svelte - JSON import wizard
├── InventoryItemDialog.svelte  - Item config dialog (Tier/TiR/QR/value/qty editing)
├── InventoryPanel.svelte       - Inventory browser with config/sell/remove actions
├── OrderAdjustDialog.svelte    - Standalone order coverage checking dialog
├── CartSummary.svelte          - Shopping cart with seller grouping + checkout
├── FavouritesTree.svelte       - Favourites sidebar with folders and drag-and-drop
├── QuickTradeDialog.svelte     - Buy Now / Sell Now confirmation dialog
├── UserOrdersPanel.svelte      - View a specific user's active orders
├── TradeRequestsPanel.svelte   - View/manage trade requests in floating panel
├── PriceHistoryChart.svelte    - Chart.js line chart for exchange price history
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

Unique constraint: 1 active order per user per item per side.
Limit: 200 orders per side per user.

### Exchange Price History

The bot snapshots exchange prices every 15 minutes from active trade orders. Each snapshot computes a volume-weighted average price (WAP) per item, combining buy and sell sides with IQR outlier filtering.

#### Snapshot Pipeline

1. Query all non-closed orders with `bumped_at` within 7 days
2. Group by item, separate buy/sell sides
3. Apply IQR filtering per side (Tukey fence, k=1.5; skipped if <4 orders)
4. Compute per-side WAP: `SUM(markup * qty) / SUM(qty)`
5. Combine sides: volume-weighted average when both exist, single side otherwise
6. Insert into `exchange_price_snapshots` with `source='exchange'`
7. Compute summaries (hour/day/week) into `exchange_price_summaries`

#### Frontend

- **Period dropdown**: 24h, 7d (default), 30d, 3m, 6m, 1y, 5y, All
- **Chart toggle**: Replaces order book with line chart (WAP over time, with min/max for summary periods)
- **Metrics**: Median, 10%, WAP update based on selected period
- **Item name**: Clickable link to wiki page

#### Database Tables (nexus-users)

**`exchange_price_snapshots`**: Raw WAP observations per item per 15-min interval

| Column | Type | Description |
|--------|------|-------------|
| id | bigserial | Primary key |
| item_id | integer | Item reference |
| markup_value | numeric(12,4) | Computed WAP markup |
| volume | integer | Total order volume |
| buy_count | smallint | Number of buy orders |
| sell_count | smallint | Number of sell orders |
| recorded_at | timestamptz | Snapshot time |

**`exchange_price_summaries`**: Pre-computed rollups for chart display

| Column | Type | Description |
|--------|------|-------------|
| id | bigserial | Primary key |
| item_id | integer | Item reference |
| period_type | exchange_price_period | hour/day/week |
| period_start | timestamptz | Period start time |
| price_min/max/avg | numeric(12,4) | Price range stats |
| price_p10/median/p90 | numeric(12,4) | Percentiles |
| price_wap | numeric(12,4) | Volume-weighted average |
| volume | bigint | Total volume in period |
| sample_count | integer | Number of snapshots |

#### Bot Module

`nexus-bot/exchange-prices.js`: `snapshotExchangePrices()`, `computeAllExchangeSummaries()`

#### API

`GET /api/market/prices/exchange/[itemId]?period=7d&history=1` — Returns live order stats, period summary (median/p10/wap), and optional time series for charting.

**Table**: `user_items` (nexus-users)

| Column | Type | Description |
|--------|------|-------------|
| id | serial | Primary key |
| user_id | bigint | Owner (Discord ID) |
| item_id | integer | Item reference |
| item_name | varchar(255) | Item name |
| quantity | integer | Stack count |
| instance_key | varchar(255) | Null=fungible, non-null=unique instance |
| details | jsonb | Tier, TiR, QR metadata |
| value | numeric | Item TT value in PED |
| container | varchar(255) | Planet/storage location |
| storage | varchar(10) | 'server' or 'local' |
| updated_at | timestamptz | Last update |

### Inventory Import System

Full-sync import wizard that replaces the user's entire server inventory with data from the Entropia Universe API.

#### Import Flow

1. **Paste**: User pastes EU "myitems" JSON (with expandable "How do I get my items?" instructions)
2. **Preview**: Shows parsed items, diff against existing inventory, and unresolved item names
3. **Import**: Full sync (DELETE all + batch INSERT) in a single transaction
4. **Coverage Check**: Compares sell orders against new inventory, highlights discrepancies

#### EU API Format

The EU inventory API returns:
```json
{
  "items": [
    { "id": 1, "value": 0.05, "quantity": 1, "name": "Item Name", "container": "Pitbull Mk. 1 (C,L)", "containerRefId": 1680 }
  ],
  "statusCode": 200
}
```

Note: `id` is a positional slot ID, NOT a game item type ID. Names are resolved to `item_id` using the loaded item database.

#### Processing Pipeline

1. **Detect EU format**: Check for `statusCode` field or `items` array with `containerRefId`
2. **Build container map**: `Map<id, {name, containerRefId}>` from all items
3. **Resolve root containers**: Walk up `containerRefId` chain to find top-level container (cycle detection via Set)
4. **Extract planet**: Regex on root container name (e.g., "STORAGE (Calypso)" → "Calypso")
5. **Combine stacks**: Group by `(name, planet)`, sum quantities and values
6. **Resolve name → item_id**: Lookup against loaded `allItems`. Unresolved items get `item_id = 0` with `instance_key = 'unresolved:' + name`

#### Diff Preview

Before importing, shows comparison against existing inventory:
- New items (green), Changed quantities (yellow), To be removed (red), Unchanged
- Table with Status column badges and quantity change indicators

#### Order Coverage Checking

After import completes, checks sell orders against new inventory:
- Groups inventory by `item_id`, sums quantities
- Compares each sell order's quantity against available inventory
- Shows discrepancies with per-row **Adjust** (set order qty to inventory qty) or **Cancel** buttons
- **Bulk actions**: "Adjust All" and "Cancel All" buttons for batch handling
- Adjusting calls `PUT /api/market/exchange/orders/[id]`, canceling calls `DELETE /api/market/exchange/orders/[id]`

#### Backend

- `syncInventory(userId, items)` in `nexus/src/lib/server/inventory.js`
- Transaction: fetches existing items → DELETE all → batch INSERT (chunks of 100) → COMMIT
- Returns diff summary: `{ added, updated, removed, unchanged, total }`
- Max import size: 30000 items

### Inventory Item Editing

After importing, users can edit item metadata through the config dialog (gear icon on each row).

#### Editable Fields

| Field | Shown When | Constraints |
|-------|-----------|-------------|
| Quantity | Fungible items (`instance_key` is null) | Integer >= 0 |
| Value (PED) | Non-fungible items with condition (`itemHasCondition`) | Number >= 0, nullable |
| Tier | Tierable items (Weapon, Armor, Finder, Excavator, MedicalTool) | 0-10, step 0.01 |
| TiR | Tierable items | 1-200 (UL) or 1-4000 (L) |
| QR | Non-(L) Blueprints | 0-100 |

Changes save immediately via debounced PATCH requests (400ms delay).

#### API

```
PATCH /api/users/inventory/[id] — Update item fields (quantity, value, details)
```

Details JSONB validation: only `Tier`, `TierIncreaseRate`, `QualityRating` keys allowed with type/range checks.

### Sell from Inventory

Each inventory row has a sell button ($) that opens the OrderDialog pre-filled:
- **Type**: Sell
- **Planet**: From inventory `container` field (or 'Calypso' default)
- **Quantity**: From inventory quantity
- **Metadata**: From inventory details (Tier, TiR, QR if present)

If the user already has a sell order for that item, the existing order opens in edit mode with a warning banner.

Quantity warnings appear in the OrderDialog if the order quantity exceeds available inventory.

### Order Coverage Dialog

A standalone dialog (accessible via "Adjust (N)" button when discrepancies exist) that:
- Compares all SELL orders against current inventory quantities
- Shows a table of discrepancies (item, order qty, inventory qty, deficit)
- Per-row actions: **Adjust** (set order qty to inventory) or **Cancel** (delete order)
- Bulk actions: **Adjust All**, **Cancel All**

### Input Validation

All exchange-related endpoints validate JSONB `details` fields server-side:
- **Order details**: `item_name` (string, max 200), `Tier` (0-10), `TierIncreaseRate` (1-4000), `QualityRating` (0-100), `CurrentTT` (>= 0), `Pet` (object with Level/Experience/Skills/Food)
- **Inventory details**: `Tier` (0-10), `TierIncreaseRate` (1-4000), `QualityRating` (0-100)
- **Planet validation**: All endpoints validate planet against the `PLANETS` constant list
- Unknown keys are silently stripped

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
GET  /api/market/exchange/orders                   - User's own orders (My Orders)
POST /api/market/exchange/orders                   - Create a new order
PUT  /api/market/exchange/orders/[id]              - Edit an order
DELETE /api/market/exchange/orders/[id]             - Close an order (soft delete)
POST /api/market/exchange/orders/[id]/bump         - Bump an order (reset staleness)
GET  /api/market/exchange/orders/item/[itemId]     - Order book for an item
GET  /api/market/exchange/orders/user/[userId]     - All active orders by a user (public)
GET  /api/market/trade-requests                    - User's trade requests
POST /api/market/trade-requests                    - Create/append trade request
GET  /api/market/trade-requests/[id]               - Single trade request with items
POST /api/market/trade-requests/[id]/cancel        - Cancel a trade request
GET  /api/users/inventory                          - User's server inventory
PUT  /api/users/inventory                          - Full-sync inventory import (up to 30000 items)
PATCH  /api/users/inventory/[id]                    - Update inventory item (quantity, value, details)
DELETE /api/users/inventory/[id]                    - Remove inventory item
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
- **Match Best**: Sets markup to the best opposing order
- **Undercut / Outbid**: Applies the 2% relative undercut formula
- **Daily Avg**: Uses the most recent daily average price from historical data (shown when available)

Suggestions are available in both create and edit modes.

### Partial Trades

Fungible items support partial trades via `min_quantity`:
- **Allow Partial** checkbox in the order dialog
- Default min quantity: 20% of total quantity (minimum 1)
- Stored in the `min_quantity` column of `trade_offers`
- Instance items (tierable, condition, blueprints, pets) do not support partial trades

### Edit Existing Order

When a user already has a buy or sell order for an item:
- The button changes to "Edit Buy" / "Edit Sell"
- Clicking opens the existing order in edit mode with pre-populated values
- Saving updates the existing order (PUT) and resets staleness

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
- **Min order amount**: Only consider orders with at least this quantity (0 = no minimum)
- **Max traders**: Maximum number of different traders (slider 0-20, default 5)
- **Planet**: Filter by planet

Preview shows matched orders sorted by best markup. Confirm creates one trade request per matched trader.

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
| side | text | 'BUY' or 'SELL' (the order side) |
| added_at | timestamptz | When item was added |

#### API Endpoints

```
GET  /api/market/trade-requests                - User's trade requests
POST /api/market/trade-requests                - Create/append trade request (market.trade)
GET  /api/market/trade-requests/[id]           - Single trade request with items
POST /api/market/trade-requests/[id]/cancel    - Cancel a trade request
GET  /api/market/exchange/orders/user/[userId] - All active orders by a user (public)
```

#### Server Lib

`nexus/src/lib/server/trade-requests.js` provides:
- `getOrCreateTradeRequest(requesterId, targetId, planet, items)` — Transaction-safe; appends to existing open request or creates new
- `getUserTradeRequests(userId)` — All requests where user is party, with partner names and item counts
- `getTradeRequest(requestId)` — Full request with items array
- `cancelTradeRequest(requestId, userId)` — Cancel (only parties can cancel)
- `getUserPublicOrders(userId)` — All active orders by a user
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
