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
- **Buy/Sell Orders**: Create and manage trade orders
- **Order Freshness**: Filter by last update time

### Routes

```
/market/exchange/                    - Main exchange view
/market/exchange/[[slug]]            - Category selected
/market/exchange/[[slug]]/[[id]]     - Item detail with orders
```

### Components

```
nexus/src/routes/market/exchange/[[slug]]/[[id]]/
├── +page.svelte           - Route entry
├── ExchangeBrowser.svelte - Main exchange UI
├── CategoryTree.svelte    - Category navigation
├── OrderDialog.svelte     - Create/edit order modal
└── orderUtils.js          - Order calculation helpers
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
| id | integer | Primary key |
| user_id | bigint | Owner (Discord ID) |
| type | text | 'Buy' or 'Sell' |
| item_name | text | Item name |
| item_type | text | Item category |
| planet | text | Trading planet |
| quantity | integer | Number of items |
| markup | numeric | Price modifier |
| current_tt | numeric | Current TT (optional) |
| metadata | jsonb | Tier, TiR, pet info |
| created_at | timestamptz | Creation time |
| updated_at | timestamptz | Last update |

### API Endpoints

```
GET /api/market/exchange   - Get categorized items for trading
```

### Local Storage

Filter preferences persisted:
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
