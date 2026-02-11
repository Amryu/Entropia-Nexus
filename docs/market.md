# Market System

Player-to-player trading features including the exchange and shop directory.

## Exchange

A trading platform for buying and selling items between players.

### Features

- **Category Browser**: Hierarchical tree navigation for item categories
- **Planet Filter**: Filter by trading location; only shows planets that have at least one active order
- **Item Type Filters**:
  - Limited (L) vs Unlimited (UL)
  - Gender filter for Armor/Clothing only
  - Tier range slider (0-10) for UL tierable items
  - TiR range slider (0-200 UL, 0-4000 L) for L tierable items
  - QR range slider (0-100) for non-L blueprints
  - Condition % slider for items with condition (filters by CurrentTT/MaxTT)
  - Min TT input for stackable items (in detail title bar)
- **Buy/Sell Orders**: Create and manage trade orders with real-time API
- **Order Freshness**: Filter by last update time
- **Order Staleness**: Active (<3d), Stale (3-7d), Expired (7-30d), Terminated (>30d)
- **My Orders**: View, bump, edit, and close your orders
- **Inventory System**: Full-sync import from EU API with diff preview, order coverage checking
- **Inventory Editing**: Inline config for item metadata (Tier, TiR, QR, value, quantity) with auto-save
- **Sell from Inventory**: Create sell orders directly from inventory rows with pre-filled data
- **Order Coverage**: Standalone dialog to check/adjust sell orders exceeding inventory
- **Shopping Cart**: Add sell orders to cart, group by seller/planet, checkout creates trade requests
- **Planet Data**: Server-side per-item planet tracking via `getOrderPlanets()` in exchange.js; cached as `pl` field on slim items
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

nexus/src/lib/components/
├── RangeSlider.svelte          - Dual-knob range slider for filter ranges
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
| Metadata | Tier, TiR, QR, Pet info, is_set (armor plates) |

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

### Armor Plate Sets

Armor plates can be traded as single plates or as a full set of 7 plates. Set orders multiply pricing accordingly:

- **Absolute markup (UL plates)**: MaxTT ×7, markup ×7, total price ×7
- **Percent markup (L plates)**: MaxTT ×7, markup % unchanged, total price ×7

The "Full set (7 plates)" checkbox appears in the OrderDialog when the item type is `ArmorPlating`. The order book shows a "Set" column with highlighted "Yes"/"No" badges.

Metadata stored:
```json
{
  "is_set": true
}
```

**Backend enforcement**: `is_set: true` is only accepted for `ArmorPlating` items. For any other item type, `is_set` is silently stripped by `enforceSetConstraint()`.

**Price snapshots**: Set orders contribute 7× weight to the volume-weighted average price calculation in `exchange-prices.js`, reflecting that a set represents 7 individual plates at the per-plate markup value.

### Armor Sets

Armor sets (complete matching armor pieces) are tradeable in the exchange. Since armor sets aren't in the Items table, they use a dedicated ID offset.

- **ID offset**: `ARMOR_SET_OFFSET = 13000000` (range 13000000–13999999)
- **API**: `GET /armorsets` returns `ItemId` field (`Id + 13000000`)
- **Type classification**: Has condition (CurrentTT for full set), tierable (Tier/TiR per piece), not stackable
- **Markup**: Non-L sets use absolute markup (+PED); (L) sets use percent markup (condition + L)
- **OrderDialog**: Shows Tier, TiR, MaxTT, CurrentTT, Markup, Planet fields
- **Item lookup**: `getItemType()` in `exchange.js` checks the ArmorSet ID range before querying the Items table
- **Cache**: `slimItem()` detects ArmorSet type via the `Armors` property when no explicit `Type` field exists

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
Limit: 1000 sell orders / 50 buy orders per user.

### Exchange Price History

The bot snapshots exchange prices every 15 minutes from active trade orders. Each snapshot computes a volume-weighted average price (WAP) per item, combining buy and sell sides with IQR outlier filtering.

#### Snapshot Pipeline

1. Query all non-closed orders with `bumped_at` within 7 days
2. Group by item, separate buy/sell sides (armor plate set orders weighted as 7× quantity)
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
- **Order details**: `item_name` (string, max 200), `Tier` (0-10), `TierIncreaseRate` (1-4000), `QualityRating` (0-100), `CurrentTT` (>= 0), `Pet` (object with Level/Experience/Skills/Food), `is_set` (boolean, ArmorPlating only)
- **Inventory details**: `Tier` (0-10), `TierIncreaseRate` (1-4000), `QualityRating` (0-100)
- **Planet validation**: All endpoints validate planet against the `PLANETS` constant list
- Unknown keys are silently stripped

### Rate Limiting

All exchange order endpoints are rate-limited to prevent abuse. The in-memory rate limiter (`$lib/server/rateLimiter.js`) tracks requests per user within sliding time windows.

#### Global Order Creation Limits

| Scope | Limit | Window |
|-------|-------|--------|
| Per minute | 100 | 1 min |
| Per hour | 500 | 1 hour |
| Per day | 3,000 | 24 hours |

Global limits increment on every attempt (even failed validation) to prevent abuse.

#### Per-Item Limits

| Scope | Fungible | Non-Fungible | Window |
|-------|----------|--------------|--------|
| Cooldown | 1 | 5 (`MAX_ORDERS_PER_ITEM`) | 3 min |
| Daily | 10 | 50 (`10 × MAX_ORDERS_PER_ITEM`) | 24 hours |

Per-item limits use peek-then-increment: only count on successful creation.

The 3-minute per-item cooldown is **shared between create and edit** operations via the key `order:item:{userId}:{itemId}`. Creating an order starts the cooldown, and editing any order for the same item within that window also counts.

#### Action Rate Limits

| Action | Limit | Window |
|--------|-------|--------|
| Edit | 60 | 1 min |
| Bump | 1 | 1 min |
| Close | 100 | 1 min |

#### Order Caps

| Side | Max Active Orders |
|------|-------------------|
| SELL | 1,000 |
| BUY | 50 |

#### Error Responses

Rate-limited requests return HTTP 429 with:
```json
{
  "error": "Rate limit exceeded (100 orders per minute). Try again in 45s.",
  "retryAfter": 45
}
```

The `retryAfter` field (seconds) and human-readable time in the error message (e.g. `45s`, `3m`, `2h`) help the frontend display appropriate messaging.

#### Constants

Defined in `$lib/server/exchange.js`:
- `RATE_LIMIT_CREATE_PER_MIN`, `RATE_LIMIT_CREATE_PER_HOUR`, `RATE_LIMIT_CREATE_PER_DAY`
- `RATE_LIMIT_ITEM_COOLDOWN_MS`, `RATE_LIMIT_ITEM_FUNGIBLE_COOLDOWN`, `RATE_LIMIT_ITEM_NONFUNGIBLE_COOLDOWN`
- `RATE_LIMIT_ITEM_DAILY_FUNGIBLE`
- `RATE_LIMIT_EDIT_PER_MIN`, `RATE_LIMIT_BUMP_PER_MIN`, `RATE_LIMIT_CLOSE_PER_MIN`

Frontend order caps in `exchangeConstants.js`: `MAX_SELL_ORDERS`, `MAX_BUY_ORDERS`.

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

## Rentals

Item rental marketplace allowing players to rent equipment from other players.

### Features

- **Rental Offers**: Create listings for item sets available for rent
- **Calendar Availability**: Visual calendar showing available, booked, and blocked dates
- **Tiered Pricing**: Base price per day with discount thresholds for longer rentals
- **Security Deposits**: Configurable deposit amounts (0 for no deposit)
- **Rental Extensions**: Extend active rentals with optional retroactive discount recalculation
- **Item Set Protection**: Item sets linked to rental offers cannot be edited or deleted
- **Request Workflow**: State machine for rental request lifecycle

### Routes

```
/market/rental/                 - Listing page (browse available offers)
/market/rental/create           - Create new rental offer (verified users)
/market/rental/[id]             - Offer detail with calendar and request button
/market/rental/[id]/edit        - Edit offer, manage blocked dates and requests
/market/rental/my               - Dashboard (my offers + my requests tabs)
```

### Components

```
nexus/src/lib/components/rental/
├── RentalStatusBadge.svelte     - Color-coded status badge (offer/request)
├── RentalOfferCard.svelte       - Card for listing page
├── RentalCalendar.svelte        - Month-grid availability calendar
├── DateRangePicker.svelte       - Date inputs with live pricing preview
├── RentalPricingEditor.svelte   - Price/day, discounts, deposit editor
├── BlockedDatesEditor.svelte    - Add/remove blocked date ranges
└── RentalRequestDialog.svelte   - Modal for creating rental requests
```

### Shared Utilities

```
nexus/src/lib/utils/rentalPricing.js     - Pricing calculations (shared client/server)
nexus/src/lib/server/rentalUtils.js      - Server-side validation/sanitization
```

Key functions in `rentalPricing.js`:
- `countDays(start, end)` — Inclusive day count between two dates
- `calculateRentalPrice(pricePerDay, discounts, totalDays)` — Price with discount lookup
- `calculateExtensionPrice(basePricePerDay, discounts, originalTotal, originalDays, extraDays, retroactive, customPrice)` — Extension pricing
- `generatePricingPreview(pricePerDay, discounts)` — Preview table for standard durations
- `formatPrice(value)` — Format as PED string

### Offer Status Machine

```
draft → available → unlisted → available (cycle)
draft → available → rented (when request is in_progress)
available → draft (only if no active requests)
any non-deleted → deleted (only if no accepted/in_progress requests)
```

| Status | Description |
|--------|-------------|
| `draft` | Not published, only visible to owner |
| `available` | Published, accepting requests |
| `rented` | Currently rented out (has in_progress request) |
| `unlisted` | Hidden from listing but still accessible by URL |
| `deleted` | Soft-deleted (set `deleted_at`) |

### Request Status Machine

```
open → accepted → in_progress → completed
open → rejected (by owner)
open → cancelled (by requester)
```

| Status | Description |
|--------|-------------|
| `open` | Awaiting owner response |
| `accepted` | Owner approved, awaiting pickup |
| `in_progress` | Items handed over, rental active |
| `completed` | Items returned, rental finished |
| `rejected` | Owner declined |
| `cancelled` | Requester withdrew |

### Pricing

**Base rate**: Price per day in PED.

**Discount thresholds**: Up to 5 tiers. Example: `[{minDays: 7, percent: 10}, {minDays: 30, percent: 20}]`. Highest applicable discount is used.

**Day counting**: Both start and end dates are inclusive. `totalDays = daysBetween(start, end) + 1`.

**Extensions**: Owner can extend an accepted/in_progress rental:
- **Non-retroactive**: Extra days priced at base rate (or custom rate). Original pricing unchanged.
- **Retroactive**: Recalculates discount for total duration (original + extension). Difference is the extra charge.

### Availability

A date is unavailable if:
1. It falls within a `rental_blocked_dates` range, OR
2. It falls within an `accepted` or `in_progress` request's date range

The availability API does NOT expose blocked date reasons (stripped for privacy).

Conflict detection uses an atomic CTE (INSERT ... WHERE NOT EXISTS) to prevent TOCTOU race conditions when creating requests.

### Database Tables (nexus-users)

#### `rental_offers`

| Column | Type | Description |
|--------|------|-------------|
| id | serial | Primary key |
| user_id | bigint | Owner (FK to users) |
| item_set_id | uuid | FK to item_sets (ON DELETE RESTRICT) |
| title | text | Offer title (max 120 chars) |
| description | text | Description (max 2000 chars) |
| planet_id | integer | Planet reference |
| location | text | Pickup/return location |
| price_per_day | numeric(10,2) | Base price per day in PED |
| discounts | jsonb | `[{minDays, percent}]` (max 5) |
| deposit | numeric(10,2) | Security deposit (default 0) |
| status | rental_offer_status | draft/available/rented/unlisted/deleted |
| created_at | timestamptz | Creation time |
| updated_at | timestamptz | Last update |
| deleted_at | timestamptz | Soft delete timestamp |

#### `rental_blocked_dates`

| Column | Type | Description |
|--------|------|-------------|
| id | serial | Primary key |
| offer_id | integer | FK to rental_offers |
| start_date | date | Block start (inclusive) |
| end_date | date | Block end (inclusive) |
| reason | text | Owner's reason (max 200, private) |

#### `rental_requests`

| Column | Type | Description |
|--------|------|-------------|
| id | serial | Primary key |
| offer_id | integer | FK to rental_offers |
| requester_id | bigint | FK to users |
| start_date | date | Rental start (inclusive) |
| end_date | date | Rental end (inclusive) |
| total_days | integer | Day count |
| price_per_day | numeric(10,2) | Effective rate after discount |
| discount_pct | numeric(5,2) | Applied discount percentage |
| total_price | numeric(10,2) | total_days * price_per_day |
| deposit | numeric(10,2) | Deposit snapshot |
| status | rental_request_status | open/accepted/rejected/in_progress/completed/cancelled |
| actual_return_date | date | For early returns |
| requester_note | text | Note from requester |
| owner_note | text | Note from owner |
| created_at | timestamptz | Creation time |
| updated_at | timestamptz | Last update |

#### `rental_extensions`

| Column | Type | Description |
|--------|------|-------------|
| id | serial | Primary key |
| request_id | integer | FK to rental_requests |
| previous_end | date | End date before extension |
| new_end | date | New end date |
| extra_days | integer | Number of extra days |
| retroactive | boolean | Whether discount was recalculated |
| price_per_day | numeric(10,2) | Rate for extra days |
| discount_pct | numeric(5,2) | Discount applied |
| extra_price | numeric(10,2) | Cost for extra days |
| new_total_price | numeric(10,2) | Updated total |
| note | text | Owner note |
| created_at | timestamptz | Creation time |

### API Endpoints

```
GET    /api/rental                          - List available offers (public)
POST   /api/rental                          - Create offer (verified, creates as draft)
GET    /api/rental/[id]                     - Get offer detail (drafts: owner/admin only)
PUT    /api/rental/[id]                     - Update offer (owner)
DELETE /api/rental/[id]                     - Soft delete offer (owner)
GET    /api/rental/[id]/availability        - Availability data for calendar (public)
GET    /api/rental/[id]/blocked-dates       - List blocked dates (owner)
POST   /api/rental/[id]/blocked-dates       - Add blocked date range (owner)
DELETE /api/rental/[id]/blocked-dates       - Remove blocked date range (owner)
GET    /api/rental/[id]/requests            - List requests for offer (owner)
POST   /api/rental/[id]/requests            - Create rental request (verified, not owner)
GET    /api/rental/requests/[requestId]     - Get request detail (owner or requester)
PUT    /api/rental/requests/[requestId]     - Status transitions / extensions
GET    /api/rental/my?type=offers|requests  - User's own offers or requests
```

### Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| POST `/api/rental` (create offer) | 5 | 1 min |
| PUT `/api/rental/[id]` (update offer) | 20 | 1 min |
| DELETE `/api/rental/[id]` (delete offer) | 10 | 1 min |
| POST `/api/rental/[id]/blocked-dates` | 20 | 1 min |
| DELETE `/api/rental/[id]/blocked-dates` | 20 | 1 min |
| POST `/api/rental/[id]/requests` (create request) | 10 | 1 min |
| PUT `/api/rental/requests/[requestId]` | 20 | 1 min |

### Limits

| Constraint | Value |
|-----------|-------|
| Max offers per user | 20 |
| Max discounts per offer | 5 |
| Max blocked date ranges per offer | 50 |
| Max rental duration | 365 days |
| Max price per day | 100,000 PED |
| Max deposit | 1,000,000 PED |
| Max title length | 120 chars |
| Max description length | 2,000 chars |

### Item Set Protection

Item sets linked to active rental offers (status != 'deleted') cannot be edited or deleted. Both the PUT and DELETE handlers on `/api/itemsets/[id]` check for linked offers and return 409 with `linkedRentalOffers` info.

### Security

- **Optimistic locking**: Offer updates include `expectedStatus` to prevent concurrent conflicting status transitions
- **Atomic conflict check**: Request creation uses a CTE with `NOT EXISTS` to atomically check for date conflicts and insert
- **Draft visibility**: Draft offers return 404 to non-owners
- **Availability privacy**: Blocked date reasons are not exposed in the public availability endpoint
- **Bounds validation**: Blocked dates must be in the future and within 2 years; custom extension prices are validated

### Tests

```
nexus/tests/rental/rental-api.spec.ts     - E2E API tests
```

Coverage: Authentication, CRUD operations, status transitions, blocked dates, availability, request creation/conflicts, extensions, item set protection.

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
- **Rentals**: Temporary item lending with calendar-based availability
- **Services**: Recurring service offerings (healing, DPS, transport)

See `docs/services.md` for service marketplace documentation.
