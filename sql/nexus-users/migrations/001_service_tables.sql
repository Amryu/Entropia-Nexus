-- ===========================================
-- ENUMS
-- ===========================================

-- Service type enum
CREATE TYPE service_type AS ENUM (
    'healing',
    'dps',
    'transportation',
    'custom'
);

-- Pricing model enum
CREATE TYPE pricing_model AS ENUM (
    'time_based',      -- Charged per hour
    'decay_based',     -- Charged per PED of tool decay
    'ticket_based',    -- Fixed price per ticket (transportation)
    'fixed'            -- One-time fixed price
);

-- Request status enum
CREATE TYPE request_status AS ENUM (
    'pending',         -- New request, waiting for provider response
    'negotiating',     -- Both parties discussing terms
    'accepted',        -- Terms agreed, locked in
    'declined',        -- Provider declined
    'in_progress',     -- Service currently being performed
    'completed',       -- Service finished
    'cancelled'        -- Cancelled by either party
);


-- ===========================================
-- CORE TABLES
-- ===========================================

-- Main services table
CREATE TABLE services (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type service_type NOT NULL,
    custom_type_name TEXT,              -- Only used when type='custom'
    title TEXT NOT NULL,
    description TEXT,

    -- Location
    planet_id INTEGER,                  -- FK to Planets in nexus db
    willing_to_travel BOOLEAN DEFAULT false,
    -- Flat fee for inter-planet travel through lootable space
    -- Only charged when traveling between planet groups (not within safe zones)
    travel_fee NUMERIC(10,4),

    -- Status
    is_active BOOLEAN DEFAULT true,
    is_busy BOOLEAN DEFAULT false,      -- Currently performing service

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);


-- ===========================================
-- SERVICE TYPE DETAILS (one per type)
-- ===========================================

-- Healing service specifics
CREATE TABLE service_healing_details (
    service_id INTEGER PRIMARY KEY REFERENCES services(id) ON DELETE CASCADE,
    paramedic_level INTEGER,
    -- Time-based billing
    accepts_time_billing BOOLEAN DEFAULT true,
    rate_per_hour NUMERIC(10,4),        -- Base rate for time-based billing
    -- Decay-based billing (binary - either accepts or not, amount determined after)
    accepts_decay_billing BOOLEAN DEFAULT true
);

-- DPS service specifics
CREATE TABLE service_dps_details (
    service_id INTEGER PRIMARY KEY REFERENCES services(id) ON DELETE CASCADE,
    profession_id INTEGER,              -- FK to Professions in nexus db
    profession_level INTEGER,
    -- Time-based billing
    accepts_time_billing BOOLEAN DEFAULT true,
    rate_per_hour NUMERIC(10,4),        -- Base rate for time-based billing
    -- Decay-based billing
    accepts_decay_billing BOOLEAN DEFAULT true,
    notes TEXT                          -- e.g., "Specializing in hunting Atrox"
);

-- Transportation service specifics
CREATE TABLE service_transportation_details (
    service_id INTEGER PRIMARY KEY REFERENCES services(id) ON DELETE CASCADE,
    vehicle_id INTEGER,                 -- FK to Vehicles in nexus db (2-seater, privateer, mothership, etc.)
    route_description TEXT,
    departure_planet_id INTEGER,        -- FK to Planets
    departure_location TEXT,            -- Specific location name
    arrival_planet_id INTEGER,          -- FK to Planets
    arrival_location TEXT,
    -- Pickup options for non-scheduled transport
    allows_pickup BOOLEAN DEFAULT false,
    pickup_fee NUMERIC(10,4),           -- Flat fee per pickup (ship jump cost)
    -- Request window configuration
    request_window_hours_before INTEGER DEFAULT 24,  -- How far in advance requests can be made
    request_cutoff_minutes INTEGER DEFAULT 30        -- When to stop accepting requests before departure
);


-- ===========================================
-- EQUIPMENT / TOOLS
-- ===========================================

-- Per-service-type whitelist of allowed tool categories
CREATE TABLE service_type_tool_whitelist (
    id SERIAL PRIMARY KEY,
    service_type service_type NOT NULL,
    tool_category TEXT NOT NULL,        -- 'medicaltools', 'weapons', 'armors', etc.
    is_primary BOOLEAN DEFAULT false,   -- Primary vs utility tool
    display_name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(service_type, tool_category, is_primary)
);

-- Service equipment (unified table for all items: tools, weapons, accessories, consumables)
-- Keeps the schema general while allowing type-specific attachments via JSON
CREATE TABLE service_equipment (
    id SERIAL PRIMARY KEY,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,

    -- Base item
    item_id INTEGER NOT NULL,           -- References Items in nexus db
    item_type TEXT NOT NULL,            -- 'weapons', 'medicaltools', 'medicalchips', 'clothings', 'consumables', etc.
    tier INTEGER CHECK (tier >= 0 AND tier <= 10),  -- 0-10 for tierable items, NULL otherwise

    -- Classification
    is_primary BOOLEAN DEFAULT true,    -- Primary tool vs utility/support

    -- Attachments stored as JSON (structure varies by item_type):
    -- weapons:      { amplifier_id, scope_id, sight_id, absorber_id,
    --                 enhancers: { damage: 0-10, accuracy: 0-10, range: 0-10, economy: 0-10, skillmod: 0-10 } }
    -- medicaltools: { enhancers: { ... } } if applicable
    -- clothings:    NULL (clothing items can have EffectsOnEquip buffs, no attachments)
    -- consumables:  NULL (steroids, pills - no attachments)
    attachments JSONB,

    -- Pricing
    extra_price NUMERIC(10,4),          -- NULL = included in base price

    notes TEXT,
    sort_order INTEGER DEFAULT 0
);

-- Armor sets listed for DPS services (separate because armor = 7 pieces, not a single item)
CREATE TABLE service_armor_sets (
    id SERIAL PRIMARY KEY,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    armor_set_id INTEGER,               -- FK to ArmorSets in nexus db (NULL if custom/mixed)
    set_name TEXT,                      -- Display name if custom

    -- Individual pieces with per-piece tier, plate, and enhancers
    -- Each piece can have its own configuration:
    -- {
    --   head:  { armor_id, tier: 0-10, plate_id, enhancers: { defense: 0-10 } },
    --   torso: { armor_id, tier: 0-10, plate_id, enhancers: { defense: 0-10 } },
    --   arms:  { armor_id, tier: 0-10, plate_id, enhancers: { defense: 0-10 } },
    --   hands: { armor_id, tier: 0-10, plate_id, enhancers: { defense: 0-10 } },
    --   legs:  { armor_id, tier: 0-10, plate_id, enhancers: { defense: 0-10 } },
    --   shins: { armor_id, tier: 0-10, plate_id, enhancers: { defense: 0-10 } },
    --   feet:  { armor_id, tier: 0-10, plate_id, enhancers: { defense: 0-10 } }
    -- }
    -- Frontend can simplify by applying same values to all pieces
    pieces JSONB,

    notes TEXT,
    sort_order INTEGER DEFAULT 0
);


-- ===========================================
-- AVAILABILITY (no external dependencies)
-- ===========================================

-- Weekly availability pattern (15-minute slots)
CREATE TABLE service_availability (
    id SERIAL PRIMARY KEY,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6), -- 0=Sunday
    start_time TIME NOT NULL,           -- e.g., '09:00' (Game Time UTC+1)
    end_time TIME NOT NULL,             -- e.g., '09:15'
    is_available BOOLEAN DEFAULT true,
    UNIQUE(service_id, day_of_week, start_time)
);


-- ===========================================
-- REQUESTS & BOOKINGS
-- (must come before service_locked_slots)
-- ===========================================

-- Service requests/bookings
CREATE TABLE service_requests (
    id SERIAL PRIMARY KEY,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    requester_id BIGINT NOT NULL REFERENCES users(id),

    -- Request details
    status request_status DEFAULT 'pending',
    -- Note: message and decline_reason handled via Discord threads, not stored here

    -- Time (nullable for "now" requests)
    requested_start TIMESTAMPTZ,
    requested_duration_minutes INTEGER,
    is_open_ended BOOLEAN DEFAULT false,

    -- Negotiated/final values
    final_start TIMESTAMPTZ,
    final_duration_minutes INTEGER,
    final_price NUMERIC(10,4),

    -- Actual execution tracking
    actual_start TIMESTAMPTZ,
    actual_end TIMESTAMPTZ,
    actual_decay_ped NUMERIC(10,4),
    break_minutes INTEGER DEFAULT 0,

    -- Post-service recording
    actual_payment NUMERIC(10,4),       -- What was actually paid (may differ from final_price)
    service_notes TEXT,                 -- Notes about the service (pirate attacks, issues, discounts, etc.)

    -- Discord integration
    discord_thread_id BIGINT,

    -- Review (only shown in frontend when service has 5+ reviews)
    review_score INTEGER CHECK (review_score >= 1 AND review_score <= 10),
    review_comment TEXT,
    reviewed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);


-- ===========================================
-- LOCKED SLOTS (depends on service_requests)
-- ===========================================

-- Locked time slots (bookings, manual blocks)
CREATE TABLE service_locked_slots (
    id SERIAL PRIMARY KEY,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    request_id INTEGER REFERENCES service_requests(id) ON DELETE CASCADE,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    reason TEXT                         -- 'booking', 'manual_block'
);


-- ===========================================
-- TRANSPORTATION SCHEDULES & TICKETS
-- ===========================================

-- Transportation schedules (recurring departures)
CREATE TABLE service_transportation_schedules (
    id SERIAL PRIMARY KEY,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    departure_time TIME NOT NULL,       -- Game Time (UTC+1)
    days_of_week INTEGER[] NOT NULL,    -- Array: [1,3,5] = Mon/Wed/Fri
    max_passengers INTEGER,
    -- Pickup/dropoff for this schedule
    allows_pickup_requests BOOLEAN DEFAULT false,
    allows_dropoff_requests BOOLEAN DEFAULT false,
    -- Status
    is_active BOOLEAN DEFAULT true
);

-- Ticket offers/packages for a schedule
CREATE TABLE service_ticket_offers (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER NOT NULL REFERENCES service_transportation_schedules(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                 -- e.g., "Single Ticket", "5-Pack", "Monthly Pass"

    -- Usage limits
    uses_count INTEGER NOT NULL,        -- Number of rides: 1, 5, 10, 50, -1 for unlimited/lifetime

    -- Validity period (NULL = no expiration, or number of days from purchase)
    validity_days INTEGER,              -- e.g., 30 for monthly, NULL for lifetime, NULL for single

    -- Pricing
    price NUMERIC(10,4) NOT NULL,

    -- Display
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true
);

-- Transportation-specific request fields
CREATE TABLE service_transport_request_details (
    request_id INTEGER PRIMARY KEY REFERENCES service_requests(id) ON DELETE CASCADE,
    schedule_id INTEGER REFERENCES service_transportation_schedules(id) ON DELETE SET NULL,
    passenger_count INTEGER DEFAULT 1,
    -- Pickup/dropoff requests
    pickup_requested BOOLEAN DEFAULT false,
    pickup_location TEXT,
    dropoff_requested BOOLEAN DEFAULT false,
    dropoff_location TEXT,
    -- Check-in tracking
    checked_in BOOLEAN DEFAULT false,
    checked_in_at TIMESTAMPTZ
);

-- Transportation tickets (purchased by users)
CREATE TABLE service_tickets (
    id SERIAL PRIMARY KEY,
    offer_id INTEGER NOT NULL REFERENCES service_ticket_offers(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id),

    -- Usage tracking (copied from offer at purchase time, then decremented)
    uses_total INTEGER NOT NULL,        -- Total uses purchased (from offer)
    uses_remaining INTEGER NOT NULL,    -- Uses left (-1 = unlimited)

    -- Validity
    valid_until DATE,                   -- Calculated at purchase: NOW + offer.validity_days (NULL = no expiration)

    -- Pricing
    price_paid NUMERIC(10,4) NOT NULL,  -- Actual price paid (may differ from offer if discounted)

    -- Status
    status TEXT DEFAULT 'active',       -- 'active', 'used', 'cancelled', 'expired'

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Ticket usage log (for multi-tickets)
CREATE TABLE service_ticket_usage (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES service_tickets(id) ON DELETE CASCADE,
    used_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    departure_date DATE NOT NULL,
    notes TEXT
);


-- ===========================================
-- DEFAULT DATA
-- ===========================================

-- Healing service tool whitelist
INSERT INTO service_type_tool_whitelist (service_type, tool_category, is_primary, display_name) VALUES
('healing', 'medicaltools', true, 'Medical Tools'),
('healing', 'medicalchips', true, 'Medical Chips'),
('healing', 'refiners', false, 'Refiners'),
('healing', 'teleportationchips', false, 'Teleportation Chips');

-- DPS service tool whitelist
INSERT INTO service_type_tool_whitelist (service_type, tool_category, is_primary, display_name) VALUES
('dps', 'weapons', true, 'Weapons'),
('dps', 'armorsets', true, 'Armor Sets'),
('dps', 'clothings', true, 'Clothing'),           -- Clothing items with EffectsOnEquip buffs
('dps', 'consumables', true, 'Consumables'),      -- Steroids, pills, etc.
('dps', 'medicaltools', false, 'Medical Tools'),
('dps', 'medicalchips', false, 'Medical Chips'),
('dps', 'teleportationchips', false, 'Teleportation Chips');


-- ===========================================
-- INDEXES
-- ===========================================

CREATE INDEX idx_services_user_id ON services(user_id);
CREATE INDEX idx_services_type ON services(type);
CREATE INDEX idx_services_planet_id ON services(planet_id);
CREATE INDEX idx_services_active ON services(is_active) WHERE is_active = true;

CREATE INDEX idx_service_equipment_service_id ON service_equipment(service_id);
CREATE INDEX idx_service_equipment_item_type ON service_equipment(item_type);
CREATE INDEX idx_service_armor_sets_service_id ON service_armor_sets(service_id);

CREATE INDEX idx_service_availability_service_id ON service_availability(service_id);
CREATE INDEX idx_service_locked_slots_service_id ON service_locked_slots(service_id);
CREATE INDEX idx_service_locked_slots_times ON service_locked_slots(start_time, end_time);

CREATE INDEX idx_service_requests_service_id ON service_requests(service_id);
CREATE INDEX idx_service_requests_requester_id ON service_requests(requester_id);
CREATE INDEX idx_service_requests_status ON service_requests(status);

CREATE INDEX idx_service_ticket_offers_schedule_id ON service_ticket_offers(schedule_id);

CREATE INDEX idx_service_tickets_user_id ON service_tickets(user_id);
CREATE INDEX idx_service_tickets_offer_id ON service_tickets(offer_id);


-- ===========================================
-- PERMISSIONS
-- ===========================================

-- services table
REVOKE ALL ON TABLE public.services FROM "nexus-users";
REVOKE ALL ON TABLE public.services FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.services TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.services TO "nexus-bot";
GRANT ALL ON TABLE public.services TO postgres;

-- service_healing_details table
REVOKE ALL ON TABLE public.service_healing_details FROM "nexus-users";
REVOKE ALL ON TABLE public.service_healing_details FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_healing_details TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_healing_details TO "nexus-bot";
GRANT ALL ON TABLE public.service_healing_details TO postgres;

-- service_dps_details table
REVOKE ALL ON TABLE public.service_dps_details FROM "nexus-users";
REVOKE ALL ON TABLE public.service_dps_details FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_dps_details TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_dps_details TO "nexus-bot";
GRANT ALL ON TABLE public.service_dps_details TO postgres;

-- service_transportation_details table
REVOKE ALL ON TABLE public.service_transportation_details FROM "nexus-users";
REVOKE ALL ON TABLE public.service_transportation_details FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_transportation_details TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_transportation_details TO "nexus-bot";
GRANT ALL ON TABLE public.service_transportation_details TO postgres;

-- service_type_tool_whitelist table
REVOKE ALL ON TABLE public.service_type_tool_whitelist FROM "nexus-users";
REVOKE ALL ON TABLE public.service_type_tool_whitelist FROM "nexus-bot";
GRANT SELECT ON TABLE public.service_type_tool_whitelist TO "nexus-users";
GRANT SELECT ON TABLE public.service_type_tool_whitelist TO "nexus-bot";
GRANT ALL ON TABLE public.service_type_tool_whitelist TO postgres;

-- service_equipment table
REVOKE ALL ON TABLE public.service_equipment FROM "nexus-users";
REVOKE ALL ON TABLE public.service_equipment FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_equipment TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_equipment TO "nexus-bot";
GRANT ALL ON TABLE public.service_equipment TO postgres;

-- service_armor_sets table
REVOKE ALL ON TABLE public.service_armor_sets FROM "nexus-users";
REVOKE ALL ON TABLE public.service_armor_sets FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_armor_sets TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_armor_sets TO "nexus-bot";
GRANT ALL ON TABLE public.service_armor_sets TO postgres;

-- service_availability table
REVOKE ALL ON TABLE public.service_availability FROM "nexus-users";
REVOKE ALL ON TABLE public.service_availability FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_availability TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_availability TO "nexus-bot";
GRANT ALL ON TABLE public.service_availability TO postgres;

-- service_requests table
REVOKE ALL ON TABLE public.service_requests FROM "nexus-users";
REVOKE ALL ON TABLE public.service_requests FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_requests TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_requests TO "nexus-bot";
GRANT ALL ON TABLE public.service_requests TO postgres;

-- service_locked_slots table
REVOKE ALL ON TABLE public.service_locked_slots FROM "nexus-users";
REVOKE ALL ON TABLE public.service_locked_slots FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_locked_slots TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_locked_slots TO "nexus-bot";
GRANT ALL ON TABLE public.service_locked_slots TO postgres;

-- service_transportation_schedules table
REVOKE ALL ON TABLE public.service_transportation_schedules FROM "nexus-users";
REVOKE ALL ON TABLE public.service_transportation_schedules FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_transportation_schedules TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_transportation_schedules TO "nexus-bot";
GRANT ALL ON TABLE public.service_transportation_schedules TO postgres;

-- service_ticket_offers table
REVOKE ALL ON TABLE public.service_ticket_offers FROM "nexus-users";
REVOKE ALL ON TABLE public.service_ticket_offers FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_ticket_offers TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_ticket_offers TO "nexus-bot";
GRANT ALL ON TABLE public.service_ticket_offers TO postgres;

-- service_transport_request_details table
REVOKE ALL ON TABLE public.service_transport_request_details FROM "nexus-users";
REVOKE ALL ON TABLE public.service_transport_request_details FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_transport_request_details TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_transport_request_details TO "nexus-bot";
GRANT ALL ON TABLE public.service_transport_request_details TO postgres;

-- service_tickets table
REVOKE ALL ON TABLE public.service_tickets FROM "nexus-users";
REVOKE ALL ON TABLE public.service_tickets FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_tickets TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_tickets TO "nexus-bot";
GRANT ALL ON TABLE public.service_tickets TO postgres;

-- service_ticket_usage table
REVOKE ALL ON TABLE public.service_ticket_usage FROM "nexus-users";
REVOKE ALL ON TABLE public.service_ticket_usage FROM "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_ticket_usage TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.service_ticket_usage TO "nexus-bot";
GRANT ALL ON TABLE public.service_ticket_usage TO postgres;

-- Sequence permissions for auto-increment columns
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.services_id_seq TO "nexus-users";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.services_id_seq TO "nexus-bot";

GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_type_tool_whitelist_id_seq TO "nexus-users";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_type_tool_whitelist_id_seq TO "nexus-bot";

GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_equipment_id_seq TO "nexus-users";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_equipment_id_seq TO "nexus-bot";

GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_armor_sets_id_seq TO "nexus-users";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_armor_sets_id_seq TO "nexus-bot";

GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_availability_id_seq TO "nexus-users";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_availability_id_seq TO "nexus-bot";

GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_requests_id_seq TO "nexus-users";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_requests_id_seq TO "nexus-bot";

GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_locked_slots_id_seq TO "nexus-users";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_locked_slots_id_seq TO "nexus-bot";

GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_transportation_schedules_id_seq TO "nexus-users";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_transportation_schedules_id_seq TO "nexus-bot";

GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_ticket_offers_id_seq TO "nexus-users";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_ticket_offers_id_seq TO "nexus-bot";

GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_tickets_id_seq TO "nexus-users";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_tickets_id_seq TO "nexus-bot";

GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_ticket_usage_id_seq TO "nexus-users";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.service_ticket_usage_id_seq TO "nexus-bot";
