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

## Integration with Services

The market section works alongside the services marketplace:

- **Exchange**: One-time item trades
- **Shops**: Persistent storefronts
- **Services**: Recurring service offerings (healing, DPS, transport)

See `docs/services.md` for service marketplace documentation.
