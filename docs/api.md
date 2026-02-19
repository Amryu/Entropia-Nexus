# Frontend API Reference

All SvelteKit API routes served at `/api/...`. These are called by the frontend and handle authentication, business logic, and database operations against the `nexus-users` database.

## Authentication & Authorization

### Session Model

Discord OAuth2 flow → session cookie → `event.locals.session`. Sessions are HttpOnly cookies with 30-day max age, refreshed automatically within 2 days of expiry.

### Auth Levels

| Level | Description | Helper |
|-------|-------------|--------|
| Public | No authentication needed | — |
| Authenticated | Logged-in user | `requireLogin(locals)` |
| Verified | EU name verified | `requireVerified(locals)` |
| Grant-based | Specific permission required | `requireGrant(locals, key)` |

### Grants

Role-based permission system with recursive parent-role resolution. Common grants:

- `admin.panel` — Admin dashboard access
- `admin.users` — User management
- `admin.impersonate` — Impersonate users
- `wiki.approve` — Approve wiki changes
- `guide.create`, `guide.edit`, `guide.delete` — Guide content management
- `market.trade` — Create trade requests

### Turnstile (CAPTCHA)

Exchange order mutations (create, edit, close, bump) and auction actions (bid, buyout) require a Cloudflare Turnstile token in the request body as `turnstile_token`.

### Rate Limiting

In-memory sliding-window rate limiter. Two patterns:
- **Atomic**: `checkRateLimit(key, max, windowMs)` — checks and increments in one call
- **Two-phase**: `checkRateLimitPeek()` → validate → `incrementRateLimit()` — only counts on success

Rate-limited responses return HTTP 429 with `{ error, retryAfter }`.

---

## Events

### `GET /api/events`

Upcoming approved events for the landing page.

- **Auth**: Public
- **Query Params**: `limit` (default 5, max 20)
- **Response** `200`: Array of approved events with future start dates

### `POST /api/events`

Submit a community event for admin review.

- **Auth**: Verified
- **Rate Limits**: Max 5 pending events per user
- **Body**:
  | Field | Type | Required | Description |
  |-------|------|----------|-------------|
  | `title` | string | Yes | Event title (max 200) |
  | `start_date` | ISO date | Yes | Must be in the future |
  | `end_date` | ISO date | No | Must be after start_date |
  | `description` | string | No | Event description (max 2000) |
  | `location` | string | No | In-game location (max 200) |
  | `type` | string | No | `"official"` or `"player_run"` (default) |
  | `link` | string | No | External link |
- **Response** `201`: Created event (state: `pending`)

---

## Market & Exchange

### `GET /api/market/exchange`

Exchange categorization summary with all items, offer counts, and prices.

- **Auth**: Public
- **Cache**: `Cache-Control: public, max-age=60`, ETag/304 support
- **Compression**: Brotli or gzip based on `Accept-Encoding`
- **Response**: Full categorized item tree as JSON

### `GET /api/market/exchange/orders`

Current user's orders (My Orders panel).

- **Auth**: Verified
- **Response** `200`: Array of user's orders (all states except terminated)

### `POST /api/market/exchange/orders`

Create a new buy or sell order.

- **Auth**: Verified + Turnstile
- **Rate Limits**: Per-minute, per-hour, per-day global limits; per-item 3-minute cooldown; per-item daily limit
- **Body**:
  | Field | Type | Required | Description |
  |-------|------|----------|-------------|
  | `type` | string | Yes | `"BUY"` or `"SELL"` |
  | `item_id` | integer | Yes | Positive item ID |
  | `quantity` | integer | Yes | >= 1 |
  | `markup` | number | Yes | >= 0; >= 100 for percent-markup types |
  | `planet` | string | No | Valid planet name |
  | `min_quantity` | integer | No | >= 1 |
  | `details` | object | No | `{ item_name, Tier, TierIncreaseRate, QualityRating, CurrentTT, Pet: { Level }, is_set, Gender }` |
  | `turnstile_token` | string | Yes | Captcha token |
- **Validations**: Gender constraints per item type, set constraint (ArmorPlating only), per-side order cap (`MAX_SELL_ORDERS`=1000, `MAX_BUY_ORDERS`=1000), per-item order cap (`MAX_ORDERS_PER_ITEM`=5)
- **Response** `201`: Created order object

### `PUT /api/market/exchange/orders/[id]`

Edit an existing order.

- **Auth**: Verified + Turnstile + owner
- **Rate Limits**: Edit per-minute limit; per-item 3-minute cooldown
- **Body**: `{ quantity, markup, planet?, min_quantity?, details?, turnstile_token }`
- **Blocked**: Cannot edit closed orders
- **Response** `200`: Updated order object

### `DELETE /api/market/exchange/orders/[id]`

Close (soft-delete) an order.

- **Auth**: Verified + Turnstile + owner
- **Rate Limits**: Close per-minute limit
- **Body**: `{ turnstile_token }`
- **Blocked**: Cannot close already-closed orders
- **Response** `200`: Closed order object

### `POST /api/market/exchange/orders/bump-all`

Bump all of the current user's active orders (refreshes `bumped_at` timestamp).

- **Auth**: Verified + Turnstile
- **Rate Limits**: 1 per minute
- **Body**: `{ turnstile_token }`
- **Response** `200`: `{ orders: [...], count: number }`

### `GET /api/market/exchange/orders/item/[itemId]`

Order book for a specific item.

- **Auth**: Public
- **Path Params**: `itemId` (positive integer)
- **Response** `200`: `{ buy: [...], sell: [...] }`

### `GET /api/market/exchange/orders/user/[userId]`

All active orders for a specific user.

- **Auth**: Public
- **Path Params**: `userId` (numeric string)
- **Response** `200`: Array of user's active orders

---

## Prices

### `GET /api/market/prices/[itemId]`

Price history for an item with configurable granularity.

- **Auth**: Public
- **Path Params**: `itemId`
- **Query Params**:
  | Param | Default | Description |
  |-------|---------|-------------|
  | `from` | — | Start timestamp |
  | `to` | — | End timestamp |
  | `granularity` | `auto` | `raw`, `hour`, `day`, `week`, `auto` |
  | `source` | — | Price source filter |
  | `limit` | 500 | Max 2000 |
- **Response** `200`: Price history with min/max/avg/percentiles/WAP

### `GET /api/market/prices/latest`

Latest prices for multiple items.

- **Auth**: Public
- **Query Params**: `items` (comma-separated IDs, max 100), `source`
- **Response** `200`: Array of latest prices per item

### `GET /api/market/prices/exchange/[itemId]`

Exchange-derived prices with period statistics.

- **Auth**: Public
- **Path Params**: `itemId` (positive integer)
- **Query Params**:
  | Param | Default | Description |
  |-------|---------|-------------|
  | `period` | `7d` | `24h`, `7d`, `30d`, `3m`, `6m`, `1y`, `5y`, `all` |
  | `history` | — | If `"1"`, includes time series for charting |
  | `gender` | — | `"Male"` or `"Female"` for gendered items |
- **Response** `200`: Merged prices data with buy/sell stats, period summary, optional history array

### `POST /api/market/prices/ingest`

Ingest price data (admin only).

- **Auth**: Requires `admin.panel` grant
- **Body**: `{ prices: [{ item_id, price_value, quantity?, source?, recorded_at? }] }` (max 1000)
- **Response** `200`: `{ inserted: number }`

### `POST /api/market/prices/summarize`

Compute price summaries for aggregation periods.

- **Auth**: Requires `admin.panel` grant
- **Body**: `{ period_type?: "hour" | "day" | "week" }` (all if omitted)
- **Response** `200`: Summary computation results

---

## Trade Requests

### `GET /api/market/trade-requests`

Current user's trade requests.

- **Auth**: Verified
- **Response** `200`: Array of trade requests

### `POST /api/market/trade-requests`

Create a trade request.

- **Auth**: Verified + `market.trade` grant
- **Body**:
  ```json
  {
    "target_id": 123,
    "planet": "Calypso",
    "items": [{
      "offer_id": 456,
      "item_id": 789,
      "item_name": "Item Name",
      "quantity": 1,
      "markup": 120,
      "side": "BUY"
    }]
  }
  ```
- **Response** `201`: Created trade request

### `GET /api/market/trade-requests/[id]`

Single trade request details.

- **Auth**: Authenticated (requester, target, or admin only)
- **Response** `200`: Trade request with items

### `POST /api/market/trade-requests/[id]/cancel`

Cancel a trade request.

- **Auth**: Authenticated (requester or target)
- **Response** `200`: Cancelled trade request

---

## Auction

### `GET /api/auction`

List auctions with filtering.

- **Auth**: Public
- **Query Params**: `status` (active/ended/settled/cancelled), `search`, `sort`, `order`, `limit`, `offset`
- **Response** `200`: Paginated auction list

### `POST /api/auction`

Create a draft auction.

- **Auth**: Verified + seller disclaimer accepted
- **Rate Limits**: Per-hour create limit
- **Body**: `{ title, starting_bid, buyout_price, duration_days, item_set_id }`
- **Validations**: Max active auctions per user, item set ownership
- **Response** `201`: Created auction (draft state)

### `GET /api/auction/[id]`

Single auction with bid history. Auto-ends expired auctions.

- **Auth**: Public
- **Response** `200`: Auction object + bids array

### `PUT /api/auction/[id]`

Edit draft auction or activate it.

- **Auth**: Verified + owner
- **Body** (edit draft): `{ title, starting_bid, buyout_price, duration_days, item_set_id }`
- **Body** (activate): `{ action: "activate" }`
- **Blocked**: Only draft auctions can be edited/activated
- **Response** `200`: Updated/activated auction

### `DELETE /api/auction/[id]`

Cancel or soft-delete an auction.

- **Auth**: Verified + owner
- **Logic**: Draft → soft delete; Active with no bids → cancel; Active with bids → error
- **Response** `200`: Deleted/cancelled auction

### `POST /api/auction/[id]/bid`

Place a bid.

- **Auth**: Verified + Turnstile + bidder disclaimer
- **Rate Limits**: Bids per-minute limit
- **Body**: `{ amount, turnstile_token }`
- **Response** `200`: `{ bid, auction: { current_bid, bid_count, ends_at } }`

### `POST /api/auction/[id]/buyout`

Instant buyout.

- **Auth**: Verified + Turnstile + bidder disclaimer
- **Rate Limits**: Buyout per-minute limit
- **Body**: `{ turnstile_token }`
- **Response** `200`: `{ auction }`

### `POST /api/auction/[id]/settle`

Settle an ended auction.

- **Auth**: Verified + seller
- **Rate Limits**: Settle per-minute limit
- **Response** `200`: Settled auction

### `GET /api/auction/my`

User's auctions and bid history. Auto-ends expired auctions.

- **Auth**: Verified
- **Response** `200`: `{ auctions, bids }`

### `GET /api/auction/disclaimer`

Check disclaimer acceptance status.

- **Auth**: Verified
- **Response** `200`: Status for `bidder` and `seller` roles

### `POST /api/auction/disclaimer`

Accept a disclaimer.

- **Auth**: Verified
- **Body**: `{ role: "bidder" | "seller" }`
- **Response** `200`: `{ success: true, role }`

### Auction Admin

All require `requireAdmin()`:

| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| `/api/auction/[id]/admin/freeze` | POST | `{ reason }` | Toggle freeze/unfreeze |
| `/api/auction/[id]/admin/cancel` | POST | `{ reason }` | Force cancel |
| `/api/auction/[id]/admin/rollback` | POST | `{ reason, target_bid_id? }` | Rollback bids (null = all) |
| `/api/auction/[id]/admin/audit` | GET | — | Fetch audit log |

---

## Services

### `GET /api/services`

List all services.

- **Auth**: Public
- **Query Params**: `type`, `planet_id`, `include_details` (`"true"` for type-specific details + equipment)
- **Response** `200`: Array of services with `planet_name`

### `POST /api/services`

Create a new service.

- **Auth**: Verified
- **Rate Limits**: 5/min, 15/hour
- **Body**:
  | Field | Type | Required | Description |
  |-------|------|----------|-------------|
  | `title` | string | Yes | Service title |
  | `type` | string | Yes | `healing`, `dps`, `transportation`, `crafting`, `hunting`, `mining`, `custom` |
  | `custom_type_name` | string | No | Name for custom type |
  | `description` | string | No | Description |
  | `planet_id` | integer | No | Planet ID |
  | `willing_to_travel` | boolean | No | Provider travels |
  | `travel_fee` | number | No | Travel fee in PED |
  | `healing_details` | object | No | Type-specific (healing) |
  | `dps_details` | object | No | Type-specific (dps) |
  | `transportation_details` | object | No | Type-specific (transportation) |
  | `equipment` | array | No | Max 50 items: `{ item_id, item_type, extra_price }` |
- **Response** `201`: Created service

### `GET /api/services/my`

User's own services.

- **Auth**: Authenticated
- **Response** `200`: Array of user's services

### `GET /api/services/[id]`

Single service with full details.

- **Auth**: Public
- **Response** `200`: Service with type-specific details, equipment, availability

### `PUT /api/services/[id]`

Update a service.

- **Auth**: Authenticated (owner or admin)
- **Body**: Service fields to update (type, title, description, availability, rates, etc.)
- **Response** `200`: Updated service

### `DELETE /api/services/[id]`

Delete a service.

- **Auth**: Authenticated (owner or admin)
- **Response** `200`: Success

### `POST /api/services/[id]/question`

Ask a question about a service.

- **Auth**: Verified
- **Rate Limits**: 5/min, 20/hour
- **Body**: `{ message: string }`
- **Response** `201`: Service request with question

### `GET /api/services/[id]/equipment`

Service equipment list.

- **Auth**: Public
- **Response** `200`: Equipment array

### `POST /api/services/[id]/equipment`

Add equipment to service.

- **Auth**: Authenticated (owner)
- **Body**: `{ item_id, item_type, extra_price? }`
- **Response** `201`: Added equipment

### `PUT /api/services/[id]/equipment`

Replace all equipment.

- **Auth**: Authenticated (owner)
- **Body**: `{ equipment: [{ id?, item_id, item_type, extra_price? }] }`
- **Response** `200`: Updated equipment array

### `GET /api/services/[id]/availability`

Service availability slots.

- **Auth**: Public
- **Response** `200`: Availability slots array

### `PUT /api/services/[id]/availability`

Update availability slots.

- **Auth**: Authenticated (owner)
- **Body**: `{ slots: [{ day_of_week, start_time, end_time }] }`
- **Response** `200`: Updated slots

### `PUT /api/services/[id]/location`

Update current planet for transportation service.

- **Auth**: Authenticated (owner or pilot)
- **Body**: `{ planet_id: integer | null }`
- **Response** `200`: `{ current_planet_id, message }`

### `GET /api/services/[id]/pilots`

List pilots for transportation service.

- **Auth**: Authenticated (owner)
- **Response** `200`: Pilots array

### `POST /api/services/[id]/pilots`

Add a pilot.

- **Auth**: Authenticated (owner)
- **Body**: `{ identifier: string }` (username or discord tag)
- **Response** `201`: Updated pilots

### `DELETE /api/services/[id]/pilots`

Remove a pilot.

- **Auth**: Authenticated (owner)
- **Body**: `{ userId: integer }`
- **Response** `200`: Success

### `GET /api/services/[id]/ticket-offers`

List ticket offers.

- **Auth**: Public
- **Response** `200`: Ticket offers array

### `POST /api/services/[id]/ticket-offers`

Create ticket offer.

- **Auth**: Authenticated (owner)
- **Body**: `{ name, price, uses_count | validity_days, waives_pickup_fee?, description?, sort_order? }`
- **Response** `201`: Created offer

### `GET /api/services/[id]/ticket-offers/[offerId]`

Single ticket offer.

- **Auth**: Public
- **Response** `200`: Ticket offer

### `PUT /api/services/[id]/ticket-offers/[offerId]`

Update ticket offer.

- **Auth**: Authenticated (owner)
- **Body**: Offer fields to update
- **Response** `200`: Updated offer

### `DELETE /api/services/[id]/ticket-offers/[offerId]`

Delete ticket offer.

- **Auth**: Authenticated (owner)
- **Response** `200`: Success

### `POST /api/services/[id]/tickets/purchase`

Purchase a ticket.

- **Auth**: Verified
- **Rate Limits**: 5/min
- **Body**: `{ offer_id }`
- **Response** `201`: Purchased ticket

### `GET /api/services/[id]/flights`

List flights for a service.

- **Auth**: Authenticated
- **Query Params**: `include_completed?`, `upcoming?`
- **Response** `200`: Flights array

### `POST /api/services/[id]/flights`

Create a flight.

- **Auth**: Authenticated (owner)
- **Body**: `{ scheduled_departure, route_type: "fixed" | "flexible", route_stops: [...], schedule_id? }`
- **Response** `201`: Created flight

### `GET /api/services/[id]/flights/[flightId]`

Single flight details.

- **Auth**: Authenticated (owner/pilot)
- **Response** `200`: Flight with state log

### `PUT /api/services/[id]/flights/[flightId]`

Flight actions.

- **Auth**: Authenticated (owner/pilot)
- **Body**: `{ action: "board" | "start" | "advance" | "undo" | "cancel" | "restore" | "update_route" | "optimize_route" | "reschedule", ... }`
- **Response** `200`: Updated flight

---

## Service Requests

### `GET /api/services/my/requests`

Provider's incoming requests.

- **Auth**: Authenticated
- **Query Params**: `status`, `serviceId`
- **Response** `200`: Incoming requests array

### `PUT /api/services/my/requests/[requestId]/status`

Update request status (provider action).

- **Auth**: Authenticated (provider)
- **Body**: `{ status: "completed" | "cancelled", service_notes? }`
- **Response** `200`: Updated request

### `GET /api/services/requests/outgoing`

User's outgoing requests.

- **Auth**: Authenticated
- **Query Params**: `status`
- **Response** `200`: Outgoing requests array

### `GET /api/services/requests/[id]`

Single request details.

- **Auth**: Authenticated (requester, provider, or admin)
- **Response** `200`: Request with context

### `PUT /api/services/requests/[id]/cancel`

Cancel a request.

- **Auth**: Authenticated (requester or admin)
- **Rate Limits**: 10/min
- **Response** `200`: Updated request

### `PUT /api/services/requests/[id]/complete`

Complete with optional review.

- **Auth**: Authenticated (requester)
- **Rate Limits**: 10/min
- **Body**: `{ review_score?: 1-10, review_comment? }`
- **Response** `200`: Updated request

---

## Flights & Check-ins

### `GET /api/flights/[flightId]/checkins`

List check-ins for a flight.

- **Auth**: Authenticated (provider or pilot)
- **Response** `200`: Check-ins array

### `POST /api/flights/[flightId]/checkin`

Create a check-in.

- **Auth**: Verified
- **Body**: `{ join_location?, join_planet_id, exit_location?, exit_planet_id }`
- **Response** `201`: Check-in with ticket info

### `PUT /api/flights/[flightId]/checkins/[checkinId]`

Accept or deny a check-in.

- **Auth**: Authenticated (provider or pilot)
- **Body**: `{ status: "accepted" | "denied" }`
- **Response** `200`: Updated check-in

### `PUT /api/flights/[flightId]/checkins/[checkinId]/accept`

Accept a check-in (shorthand).

- **Auth**: Authenticated (provider or pilot)
- **Response** `200`: Accepted check-in

### `PUT /api/flights/[flightId]/checkins/[checkinId]/deny`

Deny a check-in.

- **Auth**: Authenticated (provider or pilot)
- **Body**: `{ reason? }`
- **Response** `200`: Denied check-in

### `POST /api/flights/[flightId]/checkins/[checkinId]/refund`

Refund an accepted check-in.

- **Auth**: Authenticated (provider or pilot); within 1 hour of flight completion
- **Response** `200`: Refund confirmation

### `POST /api/flights/[flightId]/checkins/cancel`

Cancel own check-in.

- **Auth**: Authenticated
- **Response** `200`: Success with ticket restoration

---

## Tickets

### `GET /api/tickets/my`

User's purchased tickets.

- **Auth**: Authenticated
- **Query Params**: `include_expired?`
- **Response** `200`: Tickets array

### `GET /api/tickets/my/[ticketId]`

Ticket details with usage history.

- **Auth**: Authenticated (owner or admin)
- **Response** `200`: Ticket with usage history

### `DELETE /api/tickets/my/[ticketId]`

Cancel a pending ticket.

- **Auth**: Authenticated (owner or admin)
- **Response** `200`: Success

### `POST /api/tickets/[ticketId]/extend`

Extend or reactivate a ticket (provider action).

- **Auth**: Authenticated (service owner or pilot)
- **Body**: `{ action: "extend_uses" | "extend_validity" | "reactivate", additionalUses?, additionalDays? }`
- **Response** `200`: Updated ticket

### `GET /api/services/tickets/owned`

Tickets the user has purchased.

- **Auth**: Authenticated
- **Query Params**: `expired?: "true" | "recent"`
- **Response** `200`: Owned tickets

### `GET /api/services/tickets/issued`

Tickets the provider has issued.

- **Auth**: Authenticated (service provider)
- **Query Params**: `expired?: "recent"`
- **Response** `200`: Issued tickets

---

## Notifications

### `GET /api/notifications`

Paginated notifications.

- **Auth**: Authenticated
- **Query Params**: `page` (default 1), `pageSize` (default 10, max 50)
- **Response** `200`: `{ rows, total, unread, page, pageSize }`

### `POST /api/notifications/read-all`

Mark all notifications as read.

- **Auth**: Authenticated
- **Response** `200`: `{ success: true }`

### `PATCH /api/notifications/[id]`

Mark single notification as read.

- **Auth**: Authenticated
- **Response** `200`: `{ success: true }`

---

## Users

### `GET /api/users/search`

Search verified users.

- **Auth**: Verified or admin
- **Query Params**: `q` (min 2 chars), `limit` (default 10, max 20)
- **Response** `200`: Sanitized user array

### `GET /api/users/preferences`

All user preferences.

- **Auth**: Authenticated
- **Response** `200`: Preferences object

### `PUT /api/users/preferences`

Set a preference.

- **Auth**: Authenticated
- **Body**: `{ key, data }` (max 20KB per value, max 100 keys total)
- **Response** `200`: Updated preference

### `GET /api/users/preferences/[key]`

Single preference.

- **Auth**: Authenticated
- **Response** `200`: Preference data

### `DELETE /api/users/preferences/[key]`

Delete a preference.

- **Auth**: Authenticated
- **Response** `200`: Success

### `GET /api/users/inventory`

User's item inventory.

- **Auth**: Verified
- **Response** `200`: Inventory array

### `PUT /api/users/inventory`

Import/sync inventory.

- **Auth**: Verified
- **Body**: `{ items: [...], sync?: boolean }` (max 30,000 items)
- Each item may include `container_path` (string) for full container hierarchy
- **Response** `200`: Inventory or sync diff (includes `{ added, updated, removed, unchanged, total }`)
- **Side effects**: Creates `inventory_imports` row, records per-item deltas in `inventory_import_deltas`, tracks unknown items (`item_id=0`) in `unknown_items`

### `GET /api/users/inventory/imports`

Import history (paginated).

- **Auth**: Verified
- **Query Params**: `limit` (default 20, max 100), `offset` (default 0)
- **Response** `200`: Array of `{ id, imported_at, item_count, total_value, summary }`

### `GET /api/users/inventory/imports/[id]/deltas`

Deltas for a specific import. Verifies ownership (import must belong to requesting user).

- **Auth**: Verified
- **Path Params**: `id` (import ID, positive integer)
- **Response** `200`: Array of `{ id, delta_type, item_id, item_name, container, instance_key, old_quantity, new_quantity, old_value, new_value }`

### `GET /api/users/inventory/markups`

User's markup configurations.

- **Auth**: Verified
- **Response** `200`: Array of `{ item_id, markup, updated_at }`

### `PUT /api/users/inventory/markups`

Bulk upsert markup configurations.

- **Auth**: Verified
- **Body**: `{ items: [{ item_id: number, markup: number }] }` (max 1000 per request)
- **Validations**: `item_id` must be positive integer, `markup` must be finite number
- **Response** `200`: Array of upserted markup rows

### `DELETE /api/users/inventory/markups/[itemId]`

Remove markup for a specific item.

- **Auth**: Verified
- **Path Params**: `itemId` (positive integer)
- **Response** `200`: `{ success: true }`

### `PATCH /api/users/inventory/[id]`

Update inventory item metadata.

- **Auth**: Verified
- **Body**: `{ quantity?, value?, details? }`
- **Response** `200`: Updated item

### `DELETE /api/users/inventory/[id]`

Delete inventory item.

- **Auth**: Verified
- **Response** `200`: Success

---

## Societies

### `GET /api/societies`

Search societies.

- **Auth**: Public
- **Query Params**: `query`
- **Response** `200`: Societies array

### `POST /api/societies`

Create a society.

- **Auth**: Authenticated
- **Body**: `{ name, abbreviation?, description?, discord? }`
- **Response** `201`: Created society

### `GET /api/societies/[identifier]`

Society details with members.

- **Auth**: Public
- **Response** `200`: Society with members

### `PATCH /api/societies/[identifier]`

Update society.

- **Auth**: Authenticated (leader only)
- **Body**: `{ description?, discord? }`
- **Response** `200`: Updated society

### `GET /api/societies/[identifier]/requests`

Join requests (leader view).

- **Auth**: Authenticated (leader)
- **Query Params**: `status` (`pending`/`approved`/`rejected`), `page`, `pageSize`
- **Response** `200`: Paginated join requests

### `PATCH /api/societies/requests/[id]`

Approve or reject a join request.

- **Auth**: Authenticated (society leader)
- **Body**: `{ action: "approve" | "reject" }`
- **Response** `200`: Updated request (notification sent)

### `POST /api/societies/join`

Request to join a society.

- **Auth**: Authenticated
- **Body**: `{ societyId }`
- **Response** `201`: Join request

### `POST /api/societies/[id]/disband`

Disband a society.

- **Auth**: Authenticated (leader)
- **Response** `200`: Success

---

## Tools

### `GET /api/tools/loadout`

User's loadouts.

- **Auth**: Authenticated
- **Response** `200`: Loadouts array

### `POST /api/tools/loadout`

Create a loadout.

- **Auth**: Authenticated
- **Body**: `{ name?, data, public? }` (max 20KB)
- **Response** `201`: Created loadout

### `GET /api/tools/loadout/[id]`

Single loadout.

- **Auth**: Authenticated (owner)
- **Response** `200`: Loadout object

### `PUT /api/tools/loadout/[id]`

Update loadout.

- **Auth**: Authenticated (owner)
- **Body**: `{ name?, data?, public? }`
- **Response** `200`: Updated loadout

### `DELETE /api/tools/loadout/[id]`

Delete loadout.

- **Auth**: Authenticated (owner)
- **Response** `200`: Success

### `POST /api/tools/loadout/[id]`

Update loadout (alternative for `sendBeacon`).

- **Auth**: Authenticated (owner)
- **Body**: Same as PUT
- **Response** `200`: Updated loadout

### `GET /api/tools/loadout/share/[share_code]`

Shared loadout by code.

- **Auth**: Public (if marked public)
- **Response** `200`: Loadout data

### `POST /api/tools/loadout/import`

Bulk import loadouts.

- **Auth**: Authenticated
- **Body**: `{ loadouts: [...] }` (max 1MB)
- **Response** `200`: `{ imported, skipped }`

### `GET /api/tools/construction/plans`

User's crafting plans.

- **Auth**: Public (lists all) / Authenticated (for user-specific)
- **Response** `200`: Plans array

### `POST /api/tools/construction/plans`

Create crafting plan.

- **Auth**: Authenticated
- **Body**: `{ name?, data: { targets: [{ blueprintId, quantity }] } }` (max 50KB)
- **Response** `201`: Created plan

### `POST /api/tools/construction/import`

Import crafting plans and blueprint ownership.

- **Auth**: Authenticated
- **Body**: `{ plans: [...], ownership: {...} }` (max 1MB)
- **Response** `200`: `{ plansImported, plansSkipped, ownershipImported }`

---

## Guides

### `GET /api/guides`

Full guide tree.

- **Auth**: Public
- **Response** `200`: Hierarchical guide structure

### `POST /api/guides`

Create guide category.

- **Auth**: `guide.create` grant
- **Body**: `{ title, description?, sort_order? }`
- **Response** `201`: Created category

### `GET /api/guides/[categoryId]`

Single category.

- **Auth**: Public
- **Response** `200`: Category object

### `PUT /api/guides/[categoryId]`

Update category.

- **Auth**: `guide.edit` grant
- **Body**: `{ title, description?, sort_order? }`
- **Response** `200`: Updated category

### `DELETE /api/guides/[categoryId]`

Delete category.

- **Auth**: `guide.delete` grant
- **Response** `200`: `{ success: true }`

### `GET /api/guides/[categoryId]/chapters`

List chapters in category.

- **Auth**: Public
- **Response** `200`: Chapters array

### `POST /api/guides/[categoryId]/chapters`

Create chapter.

- **Auth**: `guide.create` grant
- **Body**: `{ title, description?, sort_order? }`
- **Response** `201`: Created chapter

### `GET /api/guides/[categoryId]/chapters/[chapterId]`

Single chapter.

- **Auth**: Public
- **Response** `200`: Chapter object

### `PUT /api/guides/[categoryId]/chapters/[chapterId]`

Update chapter.

- **Auth**: `guide.edit` grant
- **Body**: `{ title, description?, sort_order? }`
- **Response** `200`: Updated chapter

### `DELETE /api/guides/[categoryId]/chapters/[chapterId]`

Delete chapter.

- **Auth**: `guide.delete` grant
- **Response** `200`: `{ success: true }`

### `GET /api/guides/.../chapters/[chapterId]/lessons`

List lessons in chapter.

- **Auth**: Public
- **Response** `200`: Lessons array

### `POST /api/guides/.../chapters/[chapterId]/lessons`

Create lesson.

- **Auth**: `guide.create` grant
- **Body**: `{ title, slug, sort_order? }`
- **Response** `201`: Created lesson; `409` if slug conflict

### `GET /api/guides/.../lessons/[lessonId]`

Lesson with all paragraphs.

- **Auth**: Public
- **Response** `200`: Lesson + paragraphs array

### `PUT /api/guides/.../lessons/[lessonId]`

Update lesson.

- **Auth**: `guide.edit` grant
- **Body**: `{ title, slug?, sort_order? }`
- **Response** `200`: Updated lesson; `409` if slug conflict

### `DELETE /api/guides/.../lessons/[lessonId]`

Delete lesson.

- **Auth**: `guide.delete` grant
- **Response** `200`: `{ success: true }`

### `POST /api/guides/.../lessons/[lessonId]/paragraphs`

Create paragraph.

- **Auth**: `guide.create` grant
- **Body**: `{ content_html, sort_order? }`
- **HTML sanitization**: Whitelist of safe tags (p, strong, em, code, h1-h4, ul, ol, blockquote, a, img, iframe, div). Iframes limited to YouTube/Vimeo. Images only from `/api/img/`.
- **Response** `201`: Created paragraph

### `PUT /api/guides/.../lessons/[lessonId]/paragraphs`

Reorder paragraphs.

- **Auth**: `guide.edit` grant
- **Body**: `{ orderedIds: [number, ...] }`
- **Response** `200`: Reordered paragraphs

### `PUT /api/guides/.../paragraphs/[paragraphId]`

Update paragraph content.

- **Auth**: `guide.edit` grant
- **Body**: `{ content_html, sort_order? }`
- **Response** `200`: Updated paragraph

### `DELETE /api/guides/.../paragraphs/[paragraphId]`

Delete paragraph.

- **Auth**: `guide.delete` grant
- **Response** `200`: `{ success: true }`

---

## Rental

### `GET /api/rental`

List rental offers.

- **Auth**: Public
- **Query Params**: `planet_id?`, `limit` (max 100), `page`
- **Response** `200`: Rental offers array

### `POST /api/rental`

Create rental offer.

- **Auth**: Verified
- **Rate Limits**: 5/min
- **Body**: `{ item_set_id, price_per_day, discounts, deposit, title, description, planet_id, location, ... }`
- **Validations**: Item set ownership, rental-compatible item types, max offers per user
- **Response** `201`: Created offer (draft)

### `GET /api/rental/[id]`

Single rental offer.

- **Auth**: Public for published; owner/admin for drafts
- **Response** `200`: Offer with nested item_set data

### `PUT /api/rental/[id]`

Update rental offer.

- **Auth**: Verified (owner or admin)
- **Rate Limits**: 20/min
- **Body**: Status transitions + field updates
- **Status transitions**: `draft→available`, `available→draft|unlisted|deleted`, `rented→unlisted|deleted`, `unlisted→available|deleted`
- **Blocked fields when not draft**: item_set_id, pricing, title, description, planet_id
- **Response** `200`: Updated offer; `409` if active rental requests block transition

### `DELETE /api/rental/[id]`

Soft-delete rental offer.

- **Auth**: Verified (owner or admin)
- **Rate Limits**: 10/min
- **Blocked**: If active rental requests exist
- **Response** `200`: `{ success: true }`

### `GET /api/rental/my`

User's rental offers or requests.

- **Auth**: Verified
- **Query Params**: `type` (`"offers"` or `"requests"`, default `"offers"`)
- **Response** `200`: Offers or requests array

### `GET /api/rental/[id]/availability`

Availability calendar.

- **Auth**: Public
- **Query Params**: `months` (1-12, default 3)
- **Response** `200`: Availability data

### `GET /api/rental/[id]/blocked-dates`

Blocked date ranges.

- **Auth**: Verified (owner)
- **Response** `200`: Blocked dates array

### `POST /api/rental/[id]/blocked-dates`

Add blocked date range.

- **Auth**: Verified (owner)
- **Rate Limits**: 20/min
- **Body**: `{ start_date, end_date, reason? }` (YYYY-MM-DD, max 2 years ahead)
- **Response** `201`: Created blocked date

### `DELETE /api/rental/[id]/blocked-dates`

Remove blocked date range.

- **Auth**: Verified (owner)
- **Rate Limits**: 20/min
- **Body**: `{ id }`
- **Response** `200`: `{ success: true }`

---

## Images & Uploads

### `GET /api/image/[entityType]/[entityId]`

Serve entity image.

- **Auth**: Public
- **Response**: Image binary (with appropriate Content-Type)

### `POST /api/image/[entityType]/[entityId]`

Upload entity image.

- **Auth**: Authenticated (owner for profile images)
- **Body**: FormData with `image` file
- **Response** `200`: Success

### `DELETE /api/image/[entityType]/[entityId]`

Delete entity image.

- **Auth**: Authenticated (owner for profile)
- **Response** `200`: Success

### `GET /api/uploads/pending/[entityType]/[entityId]`

Check for pending image upload.

- **Auth**: Authenticated
- **Response** `200`: `{ hasPending, previewUrl?, uploadedAt? }`

### `GET /api/uploads/approved/[entityType]/[entityId]`

Serve approved image.

- **Auth**: Public
- **Query Params**: `type` (`"icon"` or `"thumb"`, default `"icon"`)
- **Response**: Image binary

### `GET /api/uploads/preview/[tempId]`

Preview image from temp storage.

- **Auth**: Public
- **Query Params**: `type` (`"icon"` or `"thumb"`)
- **Response**: Image binary

---

## Item Sets

### `GET /api/itemsets`

User's item sets.

- **Auth**: Authenticated
- **Response** `200`: Item sets array

### `POST /api/itemsets`

Create item set.

- **Auth**: Authenticated
- **Body**: `{ name, data, loadout_id? }` (max 100KB, max 100 sets per user)
- **Response** `201`: Created item set

---

## Shops

### `PUT /api/shops/[shop]/owner`

Change shop owner (admin only).

- **Auth**: `admin.panel` grant
- **Body**: `{ OwnerName }`
- **Response** `200`: Success with new owner info

---

## Admin

### Users

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/admin/users` | GET | `admin.users` | Search/list users. Query: `q`, `page`, `limit`, `sortBy`, `sortOrder` |
| `/api/admin/users/[id]` | GET | `admin.users` | User details with metrics |
| `/api/admin/users/[id]` | PATCH | `admin.users` | Lock/ban: `{ action, reason?, durationDays? }` |
| `/api/admin/users/[id]/roles` | GET | `admin.users` | User's role assignments |
| `/api/admin/users/[id]/roles` | PUT | `admin.users` | Set roles: `{ roleIds: [string] }` |
| `/api/admin/users/[id]/grants` | GET | `admin.users` | User's grant overrides |
| `/api/admin/users/[id]/grants` | PUT | `admin.users` | Set grants: `{ grants: [{ key, granted }] }` |

### Roles & Grants

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/admin/roles` | GET | `admin.users` | List all roles |
| `/api/admin/roles` | POST | `admin.users` | Create role: `{ name, description?, parent_id? }` |
| `/api/admin/roles/[id]` | GET/PUT/DELETE | `admin.users` | Role CRUD |
| `/api/admin/roles/[id]/grants` | GET | `admin.users` | Role's grants |
| `/api/admin/roles/[id]/grants` | PUT | `admin.users` | Set role grants: `{ grants: [{ key, granted }] }` |
| `/api/admin/grants` | GET | `admin.users` | List all available grants |

### Wiki Changes

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/admin/changes` | GET | `wiki.approve` | List changes. Query: `state`, `entity`, `authorId`, `search`, `page`, `limit` |
| `/api/admin/changes/[id]` | GET | `wiki.approve` | Change detail with history |
| `/api/admin/entity-changes/search` | GET | `wiki.approve` | Search entities with changes. Query: `q`, `type`, `limit`, `offset` |
| `/api/admin/entity-changes/types` | GET | `wiki.approve` | Entity types with change counts |

### News Detail (Public)

| Route | Description |
|-------|-------------|
| `/news/[id]` | Public page displaying a published announcement with rich text content. SSR rendered. Requires `published = true`. |

### Announcements (Admin)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/admin/announcements` | GET | `admin.panel` | List announcements. Query: `page`, `limit` |
| `/api/admin/announcements` | POST | `admin.panel` | Create: `{ title, summary?, link?, image_url?, pinned?, published?, content_html? }` |
| `/api/admin/announcements/[id]` | GET | `admin.panel` | Single announcement (includes `content_html`) |
| `/api/admin/announcements/[id]` | PUT | `admin.panel` | Update announcement fields (including `content_html`) |
| `/api/admin/announcements/[id]` | DELETE | `admin.panel` | Delete announcement |

**`content_html`**: Rich text body sanitized server-side via `sanitizeRichText()`. When present, the landing page links to `/news/{id}` for on-site reading. When absent, links to the external `link` URL. Image uploads use the `announcement` entity type in `imageProcessor.js` (banner dimensions, auto-approve).

### Events (Admin)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/admin/events` | GET | `admin.panel` | List events. Query: `page`, `limit`, `state` |
| `/api/admin/events/[id]` | GET | `admin.panel` | Single event with submitter info |
| `/api/admin/events/[id]` | PUT | `admin.panel` | Update event fields |
| `/api/admin/events/[id]` | DELETE | `admin.panel` | Delete event |
| `/api/admin/events/[id]/approve` | POST | `admin.panel` | Approve pending event |
| `/api/admin/events/[id]/deny` | POST | `admin.panel` | Deny with optional `{ reason }` |

### Content Creators (Admin)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/admin/creators` | GET | `admin.panel` | List all creators |
| `/api/admin/creators` | POST | `admin.panel` | Add: `{ name, platform, channel_url, channel_id?, ... }` |
| `/api/admin/creators/[id]` | GET | `admin.panel` | Single creator |
| `/api/admin/creators/[id]` | PUT | `admin.panel` | Update creator fields |
| `/api/admin/creators/[id]` | DELETE | `admin.panel` | Delete creator |
| `/api/admin/creators/[id]/refresh` | POST | `admin.panel` | Manual API data refresh |

### Unknown Items

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/admin/unknown-items` | GET | Admin | List unknown items. Query: `resolved` (true/false), `limit` (max 200), `offset` |
| `/api/admin/unknown-items/[id]` | PATCH | Admin | Mark resolved: `{ resolved_item_id? }` |

### Other Admin

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/admin/stats` | GET | `admin.panel` | Dashboard stats |
| `/api/admin/audit/[entityType]/[entityId]/[...path]` | GET | `admin.users` | Proxy to entity audit API |
| `/api/admin/images/richtext` | GET | `admin.panel` | Scan unused richtext images |
| `/api/admin/images/richtext` | DELETE | `admin.panel` | Delete unused images: `{ hashes: [string] }` |
| `/api/admin/societies` | GET | `admin.panel` | List societies. Query: `q`, `page`, `limit` |
| `/api/admin/impersonate` | GET | `admin.impersonate` | Current impersonation status |
| `/api/admin/impersonate` | POST | `admin.impersonate` | Start: `{ userId }` |
| `/api/admin/impersonate` | DELETE | `admin.impersonate` | Stop impersonation |

---

## Test

### `POST /api/test/login`

Mock login for testing (dev/test mode only).

- **Auth**: None (dev mode only)
- **Body**: `{ userId }` — One of: `verified1`, `verified2`, `verified3`, `unverified1`, `unverified2`, `unverified3`, `admin`
- **Response**: Session cookie set

### `DELETE /api/test/login`

Mock logout for testing.

- **Auth**: None (dev mode only)
- **Response**: Session cookie cleared

---

## Common Response Patterns

All endpoints return JSON with appropriate HTTP status codes:

| Status | Meaning |
|--------|---------|
| `200` | Success |
| `201` | Created |
| `304` | Not Modified (ETag match) |
| `400` | Validation error |
| `401` | Authentication required |
| `403` | Insufficient permissions |
| `404` | Not found |
| `409` | Conflict (limit reached, duplicate, active requests block action) |
| `429` | Rate limited — includes `retryAfter` (seconds) |
| `500` | Server error |

Error responses follow the format: `{ error: "message" }`, optionally with extra fields like `retryAfter`, `itemOrderCount`, `activeRequests`.
