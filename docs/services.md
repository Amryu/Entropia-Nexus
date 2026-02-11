# Services System

Player-offered services marketplace with availability management, ticket-based transportation, and Discord-integrated booking.

## Service Types

| Type | Description | Billing Model |
|------|-------------|---------------|
| `healing` | Healing services with medical tools/chips | Time or decay-based |
| `dps` | Damage dealing support with weapons/armor | Time or decay-based |
| `transportation` | Scheduled or on-demand transport | Ticket-based |
| `crafting` | Crafting services | Custom pricing |
| `hunting` | Hunting assistance | Custom pricing |
| `mining` | Mining services | Custom pricing |
| `custom` | User-defined services | Custom pricing |

## Key Design Decisions

- **Time Zone**: All times in Game Time (MA) = UTC+1/CET
- **Discord Notifications**: Dedicated channel for service requests and flight threads
- **Tool Whitelist**: Per-service-type allowed item categories
- **Reviews**: Rating system with 1-10 score + comments
- **Pilots**: Transportation services can have multiple authorized pilots

## Database Schema

### Core Tables

#### `services`
Main service listings.

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| user_id | bigint | Service owner (Discord ID) |
| type | enum | Service type (healing, dps, transportation, etc.) |
| custom_type_name | text | Name for custom service types |
| title | text | Service title |
| description | text | Full description |
| planet_id | integer | Base planet (FK to planets) |
| willing_to_travel | boolean | If provider travels to client |
| travel_fee | numeric | Fee for traveling to client |
| is_active | boolean | Visible in marketplace |
| is_busy | boolean | Currently in session |
| created_at, updated_at, deleted_at | timestamptz | Timestamps |

#### `service_healing_details`
Healing-specific configuration.

| Column | Type | Description |
|--------|------|-------------|
| service_id | integer | FK to services |
| paramedic_level | integer | Paramedic profession level |
| hp_per_second | numeric | Healing rate |
| price_per_hour | numeric | Hourly rate |
| price_per_decay_ped | numeric | Rate per PED decay |

#### `service_dps_details`
DPS-specific configuration.

| Column | Type | Description |
|--------|------|-------------|
| service_id | integer | FK to services |
| damage_per_second | numeric | DPS rate |
| profession | text | Combat profession |
| price_per_hour | numeric | Hourly rate |
| price_per_decay_ped | numeric | Rate per PED decay |

#### `service_transportation_details`
Transportation-specific configuration.

| Column | Type | Description |
|--------|------|-------------|
| service_id | integer | FK to services |
| transportation_type | text | regular, warp_equus, warp_privateer |
| service_mode | text | on_demand, scheduled, both |
| ship_name | text | Name of the ship |
| departure_location | text | Default departure location |
| pickup_fee | numeric | Fee for pickup requests |
| routes | jsonb | Available routes configuration |

### Equipment Tables

#### `service_equipment`
Unified table for weapons, medical tools, clothing, consumables.

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| service_id | integer | FK to services |
| item_id | integer | FK to items (API) |
| item_type | text | weapon, medical, clothing, consumable |
| tier | numeric | Item tier level |
| attachments | jsonb | Amp, scope, sight, absorber, enhancers |

#### `service_armor_sets`
Armor sets with per-piece configuration.

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| service_id | integer | FK to services |
| pieces | jsonb | Per-slot armor configuration |

#### `service_type_tool_whitelist`
Allowed item categories per service type.

### Scheduling & Availability

#### `service_availability`
Weekly availability pattern in 15-minute slots.

| Column | Type | Description |
|--------|------|-------------|
| service_id | integer | FK to services |
| day_of_week | integer | 0-6 (Sunday-Saturday) |
| slot_index | integer | 0-95 (15-min slots in a day) |
| is_available | boolean | Slot availability |

#### `service_locked_slots`
Booked/blocked time periods.

| Column | Type | Description |
|--------|------|-------------|
| service_id | integer | FK to services |
| start_time | timestamptz | Lock start |
| end_time | timestamptz | Lock end |
| reason | text | booking, blocked, etc. |

#### `service_transportation_schedules`
Recurring departure schedules.

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| service_id | integer | FK to services |
| day_of_week | integer | 0-6 |
| departure_time | time | Departure time (game time) |
| route | jsonb | Route stops configuration |
| is_active | boolean | Schedule active |

### Tickets & Flights

#### `service_ticket_offers`
Ticket packages (single, multi-packs, passes).

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| service_id | integer | FK to services |
| name | text | Offer name (e.g., "10-Trip Pass") |
| uses_count | integer | Number of uses (null = unlimited) |
| validity_days | integer | Days valid after purchase (null = unlimited) |
| price | numeric | Price in PED |
| waives_pickup_fee | boolean | If true, no pickup fee charged |
| description | text | Offer description |
| sort_order | integer | Display order |
| is_active | boolean | Currently available |

#### `service_tickets`
Purchased tickets.

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| offer_id | integer | FK to service_ticket_offers |
| user_id | bigint | Ticket owner |
| uses_total | integer | Total uses when purchased |
| uses_remaining | integer | Remaining uses |
| valid_until | date | Expiration date |
| price_paid | numeric | Price paid |
| status | text | active, expired, exhausted |
| activated_at | timestamptz | When first used |

#### `service_flight_instances`
Individual flight occurrences.

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| schedule_id | integer | FK to schedules (null for ad-hoc) |
| service_id | integer | FK to services |
| scheduled_departure | timestamptz | Planned departure time |
| actual_departure | timestamptz | When actually departed |
| completed_at | timestamptz | When completed |
| status | text | scheduled, boarding, in_progress, completed, cancelled |
| current_stop_index | integer | Current position in route |
| current_state | text | boarding, departing, traveling, arriving |
| route_stops | jsonb | Route with ETAs and actual times |
| route_type | text | one_way, round_trip, circuit |
| auto_cancel_at | timestamptz | Auto-cancel if not enough passengers |
| discord_thread_id | bigint | Flight coordination thread |

#### `service_flight_state_log`
State transition history for flights.

#### `service_checkins`
Flight check-ins.

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| flight_id | integer | FK to flight_instances |
| request_id | integer | FK to service_requests (optional) |
| ticket_id | integer | FK to service_tickets (optional) |
| user_id | bigint | Passenger |
| join_location | text | Where passenger joins |
| join_planet_id | integer | Join location planet |
| exit_location | text | Where passenger exits |
| exit_planet_id | integer | Exit location planet |
| status | text | pending, accepted, denied, cancelled, boarded, completed |
| denial_reason | text | If denied, why |
| added_to_thread | boolean | Added to Discord thread |
| checked_in_at | timestamptz | Check-in time |
| accepted_at | timestamptz | Acceptance time |

#### `service_ticket_usage`
Multi-ticket usage log for auditing.

### Requests & Reviews

#### `service_requests`
Booking requests with review support.

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| service_id | integer | FK to services |
| requester_id | bigint | Who made the request |
| status | text | pending, negotiating, accepted, in_progress, completed, cancelled, declined, aborted |
| requested_start | timestamptz | Requested start time |
| requested_duration_minutes | integer | Requested duration |
| is_open_ended | boolean | No fixed end time |
| final_start | timestamptz | Agreed start time |
| final_duration_minutes | integer | Agreed duration |
| final_price | numeric | Agreed price |
| actual_start | timestamptz | When actually started |
| actual_end | timestamptz | When actually ended |
| actual_decay_ped | numeric | Actual decay used |
| break_minutes | integer | Break time during session |
| actual_payment | numeric | Final payment amount |
| service_notes | text | Notes (prefix [QUESTION] for questions) |
| discord_thread_id | bigint | Discussion thread |
| review_score | integer | 1-10 rating |
| review_comment | text | Review text |
| reviewed_at | timestamptz | When reviewed |

#### `service_transport_request_details`
Transport-specific request details.

| Column | Type | Description |
|--------|------|-------------|
| request_id | integer | FK to service_requests |
| passenger_count | integer | Number of passengers |
| pickup_location | text | Where to pick up |
| dropoff_location | text | Where to drop off |
| needs_pickup | boolean | Requests pickup |

### Pilots

#### `service_pilots`
Authorized pilots for transportation services.

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| service_id | integer | FK to services |
| user_id | bigint | Pilot's Discord ID |
| can_manage_flights | boolean | Can create/manage flights |
| added_at | timestamptz | When added |

## Request Flow

### Standard Service Request

```
1. User requests service
   └─> Status: pending

2. Discord bot creates thread in #service-requests
   └─> Provider notified

3. Provider responds:
   ├─> Accept → Status: accepted, slot locked
   ├─> Decline → Status: declined (with reason)
   └─> Invite to Discuss → Requester added, Status: negotiating

4. Negotiation phase:
   └─> Lock In terms → Status: accepted, slot locked

5. Session start:
   └─> Provider clicks Start → Status: in_progress, is_busy = true

6. Session end:
   └─> Provider clicks End → Status: completed, record payment

7. Review:
   └─> Requester can leave 1-10 rating + comment
```

### Question Flow

Users can ask questions about a service without making a booking request:

```
1. User submits question (service_notes starts with [QUESTION])
   └─> Status: pending

2. Provider responds in thread
   └─> Status: negotiating

3. Either party can close:
   └─> Status: aborted
```

## Transportation Flow

### Scheduled Flights

```
1. Provider creates schedule with departure times and route

2. Provider creates ticket offers:
   ├─> Single trip
   ├─> Multi-packs (5x, 10x)
   ├─> Time passes (weekly, monthly)
   └─> Lifetime passes

3. Users purchase tickets

4. Flight instance created (from schedule or ad-hoc)

5. Check-in opens (~30 min before departure):
   ├─> Users with tickets check in
   ├─> Specify join/exit locations
   └─> Request pickup if needed

6. Provider manages flight:
   ├─> Review check-ins (accept/deny)
   ├─> Update flight state as traveling
   └─> Mark stops as completed

7. Flight completion:
   └─> Ticket uses decremented, check-ins marked complete
```

### Flight States

| State | Description |
|-------|-------------|
| scheduled | Waiting for departure time |
| boarding | Check-in open, accepting passengers |
| in_progress | Currently traveling |
| completed | Flight finished |
| cancelled | Flight cancelled |

### Check-in States

| Status | Description |
|--------|-------------|
| pending | Awaiting provider review |
| accepted | Confirmed for flight |
| denied | Rejected (with reason) |
| cancelled | User cancelled |
| boarded | On the ship |
| completed | Successfully transported |

## API Endpoints

### Services

```
GET    /api/services                    - List services (type filter, planet filter, include_details includes equipment)
POST   /api/services                    - Create service (verified users)
GET    /api/services/my                 - Current user's owned services
GET    /api/services/:id                - Get service details
PUT    /api/services/:id                - Update service (owner/pilot)
DELETE /api/services/:id                - Deactivate service
```

### Equipment

```
GET    /api/services/:id/equipment      - Get service equipment
POST   /api/services/:id/equipment      - Add equipment item
PUT    /api/services/:id/equipment      - Update equipment
```

### Location & Pilots (Transportation)

```
PUT    /api/services/:id/location       - Update current location
GET    /api/services/:id/pilots         - List pilots
POST   /api/services/:id/pilots         - Add pilot
DELETE /api/services/:id/pilots         - Remove pilot
```

### Availability

```
GET    /api/services/:id/availability   - Get weekly pattern
PUT    /api/services/:id/availability   - Update pattern
POST   /api/services/my/sync-availability - Sync availability across services
```

### Ticket Offers

```
GET    /api/services/:id/ticket-offers           - List offers
POST   /api/services/:id/ticket-offers           - Create offer
GET    /api/services/:id/ticket-offers/:offerId  - Get offer details
PUT    /api/services/:id/ticket-offers/:offerId  - Update offer
DELETE /api/services/:id/ticket-offers/:offerId  - Delete offer
```

### Tickets

```
POST   /api/services/:id/tickets/purchase  - Buy ticket
GET    /api/services/:id/tickets/my        - User's tickets for service
GET    /api/tickets/my                     - All user's tickets
GET    /api/tickets/my/:ticketId           - Ticket details
PUT    /api/tickets/:ticketId/extend       - Extend ticket validity
GET    /api/services/tickets/owned         - All owned tickets
GET    /api/services/tickets/issued        - Tickets issued by provider
```

### Flights

```
GET    /api/services/:id/flights            - List flights
POST   /api/services/:id/flights            - Create flight
GET    /api/services/:id/flights/:flightId  - Get flight details
PUT    /api/services/:id/flights/:flightId  - Update flight
```

### Check-ins

```
GET    /api/flights/:flightId/checkins           - List check-ins
POST   /api/flights/:flightId/checkin            - Check in for flight
POST   /api/flights/:flightId/checkins/cancel    - Cancel check-in
GET    /api/flights/:flightId/checkins/:id       - Get check-in details
PUT    /api/flights/:flightId/checkins/:id/accept  - Accept check-in
PUT    /api/flights/:flightId/checkins/:id/deny    - Deny check-in
PUT    /api/flights/:flightId/checkins/:id/refund  - Refund check-in
```

### Requests

```
POST   /api/services/:id/question              - Ask question about service
GET    /api/services/:id/my-request            - User's request for service
GET    /api/services/my/requests               - Incoming requests (provider)
GET    /api/services/requests/outgoing         - Outgoing requests (requester)
GET    /api/services/requests/:id              - Request details
PUT    /api/services/requests/:id/cancel       - Cancel request
PUT    /api/services/requests/:id/complete     - Complete request
PUT    /api/services/my/requests/:id/status    - Update request status
```

## Frontend Routes

```
/market/services/                     - Browse services (type tabs, planet filter)
/market/services/create               - Create new service
/market/services/[id]                 - Service detail view
/market/services/[id]/edit            - Edit service
/market/services/[id]/availability    - Manage availability
/market/services/[id]/ticket-offers   - Manage ticket offers
/market/services/[id]/flights         - View/create flights
/market/services/[id]/flights/[flightId]/manage - Manage flight

/market/services/my                   - My services dashboard
/market/services/my/offers            - Incoming requests (provider view)
/market/services/my/offers/[id]       - Request detail (provider)
/market/services/my/offers/[id]/finish/[requestId] - Complete session
/market/services/my/offers/sync-availability - Sync availability
/market/services/my/requests          - My outgoing requests
/market/services/my/requests/[id]     - Request detail (requester)
/market/services/my/tickets           - My purchased tickets
```

## Components

```
nexus/src/lib/components/services/
├── AvailabilityCalendar.svelte      - Weekly availability grid editor
├── DashboardNav.svelte              - Navigation for my services pages
├── DPSServicesList.svelte           - DPS services table
├── EquipmentEditor.svelte           - Add/edit equipment with attachments
├── HealingServicesList.svelte       - Healing services table
├── LocationManager.svelte           - Update current location
├── PilotManager.svelte              - Add/remove pilots
├── RequestStatusBadge.svelte        - Status indicator badge
├── TicketOfferCard.svelte           - Ticket package display
├── TicketOfferEditor.svelte         - Create/edit ticket offers
└── TransportationServicesList.svelte - Transport services table
```

## Discord Bot Integration

### Configuration

Bot polls for:
- New service requests without thread_id
- Flight check-ins needing thread notification

### Request Threads

When a request is created:
1. Bot creates private thread in configured channel
2. Adds service provider
3. Posts request details with action buttons

### Flight Threads

When a flight has check-ins:
1. Bot creates thread for flight coordination
2. Adds passengers as they check in
3. Updates with flight status changes

### Button Handlers

```
service_accept_*   - Accept request
service_decline_*  - Decline (modal for reason)
service_invite_*   - Invite requester to thread
service_lockin_*   - Lock in negotiated terms
service_start_*    - Start session (sets is_busy)
service_end_*      - End session (modal for final values)

flight_accept_*    - Accept check-in
flight_deny_*      - Deny check-in (modal for reason)
flight_board_*     - Mark passenger as boarded
```

## Equipment JSON Structures

### Weapon Attachments

```json
{
  "amplifier_id": 123,
  "scope_id": 456,
  "sight_id": null,
  "absorber_id": 789,
  "enhancers": {
    "damage": 5,
    "accuracy": 3,
    "range": 0,
    "economy": 2,
    "skillmod": 0
  }
}
```

### Armor Set Pieces

```json
{
  "head":  { "armor_id": 100, "tier": 7.2, "plate_id": 200, "enhancers": { "defense": 5 } },
  "torso": { "armor_id": 101, "tier": 8.0, "plate_id": 201, "enhancers": { "defense": 5 } },
  "arms":  { "armor_id": 102, "tier": 6.5, "plate_id": 202, "enhancers": { "defense": 4 } },
  "hands": { "armor_id": 103, "tier": 6.0, "plate_id": null, "enhancers": {} },
  "legs":  { "armor_id": 104, "tier": 7.1, "plate_id": 204, "enhancers": { "defense": 5 } },
  "shins": { "armor_id": 105, "tier": 6.3, "plate_id": 205, "enhancers": { "defense": 3 } },
  "feet":  { "armor_id": 106, "tier": 5.0, "plate_id": null, "enhancers": {} }
}
```

### Route Stops

```json
[
  {
    "planet_id": 1,
    "location": "Crystal Palace",
    "is_departure": true,
    "eta_minutes": 0,
    "actual_arrival": null,
    "actual_departure": null
  },
  {
    "planet_id": 1,
    "location": "Calypso Space Station",
    "is_departure": false,
    "eta_minutes": 5,
    "actual_arrival": null,
    "actual_departure": null
  }
]
```

## Styling Guidelines

See `docs/ui-styling.md` for:
- CSS variables for theming
- Form control patterns
- Status badge styling
- Error/success banners (never use `alert()`)
