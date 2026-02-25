-- Migration: 001_transportation_enhancements
-- Description: Enhance transportation service system with tickets, flights, and check-ins
-- Date: 2026-01-28

BEGIN;

-- ===========================================
-- 1. ENHANCE SERVICE_TRANSPORTATION_DETAILS
-- ===========================================

ALTER TABLE service_transportation_details
  ADD COLUMN IF NOT EXISTS transportation_type TEXT DEFAULT 'regular',
  ADD COLUMN IF NOT EXISTS ship_name TEXT,
  ADD COLUMN IF NOT EXISTS service_mode TEXT DEFAULT 'on_demand',
  ADD COLUMN IF NOT EXISTS current_planet_id INTEGER;

-- Add check constraint for valid transportation types
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'valid_transportation_type'
  ) THEN
    ALTER TABLE service_transportation_details
      ADD CONSTRAINT valid_transportation_type
      CHECK (transportation_type IN ('regular', 'warp_equus', 'warp_privateer'));
  END IF;
END $$;

-- Add check constraint for valid service modes
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'valid_service_mode'
  ) THEN
    ALTER TABLE service_transportation_details
      ADD CONSTRAINT valid_service_mode
      CHECK (service_mode IN ('on_demand', 'scheduled', 'both'));
  END IF;
END $$;


-- ===========================================
-- 2. RECREATE TICKET SYSTEM (SERVICE-LEVEL)
-- ===========================================

-- Drop old schedule-based ticket tables (cascade will handle dependencies)
DROP TABLE IF EXISTS service_ticket_usage CASCADE;
DROP TABLE IF EXISTS service_tickets CASCADE;
DROP TABLE IF EXISTS service_ticket_offers CASCADE;

-- Create service-level ticket offers
CREATE TABLE service_ticket_offers (
    id SERIAL PRIMARY KEY,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    name TEXT NOT NULL,

    -- Usage limits (one must be set)
    uses_count INTEGER,              -- Number of uses: 1, 5, 10, -1 for unlimited
    validity_days INTEGER,           -- Duration in days: 7, 30, 90, etc.

    -- Pricing
    price NUMERIC(10,4) NOT NULL,

    -- Pickup fee waiver (for multi-use tickets)
    waives_pickup_fee BOOLEAN DEFAULT false,

    -- Display
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- Must have either uses_count or validity_days
    CONSTRAINT ticket_type_check CHECK (
      (uses_count IS NOT NULL AND validity_days IS NULL) OR
      (uses_count IS NULL AND validity_days IS NOT NULL)
    )
);

-- Prevent duplicate uses_count per service
CREATE UNIQUE INDEX idx_ticket_offers_uses
  ON service_ticket_offers(service_id, uses_count)
  WHERE uses_count IS NOT NULL;

-- Prevent duplicate validity_days per service
CREATE UNIQUE INDEX idx_ticket_offers_validity
  ON service_ticket_offers(service_id, validity_days)
  WHERE validity_days IS NOT NULL;

-- Index for fast lookups
CREATE INDEX idx_ticket_offers_service ON service_ticket_offers(service_id);


-- Create tickets table
CREATE TABLE service_tickets (
    id SERIAL PRIMARY KEY,
    offer_id INTEGER NOT NULL REFERENCES service_ticket_offers(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id),

    -- Usage tracking (copied from offer at purchase time)
    uses_total INTEGER NOT NULL,        -- Total uses purchased (-1 = unlimited)
    uses_remaining INTEGER NOT NULL,    -- Uses left (-1 = unlimited)

    -- Validity
    valid_until DATE,                   -- NULL = no expiration

    -- Pricing
    price_paid NUMERIC(10,4) NOT NULL,

    -- Status: 'pending', 'active', 'used', 'expired', 'cancelled'
    status TEXT DEFAULT 'pending',
    activated_at TIMESTAMPTZ,           -- When provider accepted first use

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_ticket_status CHECK (
      status IN ('pending', 'active', 'used', 'expired', 'cancelled')
    )
);

-- Index for user lookups
CREATE INDEX idx_tickets_user ON service_tickets(user_id);
CREATE INDEX idx_tickets_offer ON service_tickets(offer_id);
CREATE INDEX idx_tickets_status ON service_tickets(status);


-- Create ticket usage log
CREATE TABLE service_ticket_usage (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES service_tickets(id) ON DELETE CASCADE,
    used_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    departure_date DATE NOT NULL,
    notes TEXT
);

CREATE INDEX idx_ticket_usage_ticket ON service_ticket_usage(ticket_id);


-- ===========================================
-- 3. ENHANCE SCHEDULES WITH ROUTE INFO
-- ===========================================

ALTER TABLE service_transportation_schedules
  ADD COLUMN IF NOT EXISTS route_type TEXT DEFAULT 'fixed',
  ADD COLUMN IF NOT EXISTS route_stops JSONB;

-- Add check constraint for valid route types
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'valid_route_type'
  ) THEN
    ALTER TABLE service_transportation_schedules
      ADD CONSTRAINT valid_route_type
      CHECK (route_type IN ('fixed', 'flexible'));
  END IF;
END $$;


-- ===========================================
-- 4. FLIGHT INSTANCES
-- ===========================================

CREATE TABLE IF NOT EXISTS service_flight_instances (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER REFERENCES service_transportation_schedules(id) ON DELETE SET NULL,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,

    -- Timing
    scheduled_departure TIMESTAMPTZ NOT NULL,
    actual_departure TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- State: 'scheduled', 'boarding', 'running', 'completed', 'cancelled'
    status TEXT DEFAULT 'scheduled',
    current_stop_index INTEGER DEFAULT 0,
    current_state TEXT,              -- e.g., 'docked_at_calypso', 'in_warp_to_arkadia'

    -- Route (copy from schedule, can be modified for flexible routes)
    route_type TEXT DEFAULT 'fixed',
    route_stops JSONB NOT NULL,

    -- Auto-cancel tracking (2h after scheduled departure)
    auto_cancel_at TIMESTAMPTZ,

    -- Discord thread for this flight
    discord_thread_id BIGINT,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_flight_status CHECK (
      status IN ('scheduled', 'boarding', 'running', 'completed', 'cancelled')
    )
);

CREATE INDEX idx_flights_service ON service_flight_instances(service_id);
CREATE INDEX idx_flights_schedule ON service_flight_instances(schedule_id);
CREATE INDEX idx_flights_status ON service_flight_instances(status);
CREATE INDEX idx_flights_departure ON service_flight_instances(scheduled_departure);


-- ===========================================
-- 5. FLIGHT STATE LOG (FOR UNDO)
-- ===========================================

CREATE TABLE IF NOT EXISTS service_flight_state_log (
    id SERIAL PRIMARY KEY,
    flight_id INTEGER NOT NULL REFERENCES service_flight_instances(id) ON DELETE CASCADE,
    previous_state TEXT,
    new_state TEXT NOT NULL,
    stop_index INTEGER,
    changed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    can_undo BOOLEAN DEFAULT true,   -- false after 10 seconds
    undone BOOLEAN DEFAULT false
);

CREATE INDEX idx_flight_log_flight ON service_flight_state_log(flight_id);
CREATE INDEX idx_flight_log_time ON service_flight_state_log(changed_at);


-- ===========================================
-- 6. CHECK-INS TABLE
-- ===========================================

CREATE TABLE IF NOT EXISTS service_checkins (
    id SERIAL PRIMARY KEY,
    flight_id INTEGER REFERENCES service_flight_instances(id) ON DELETE CASCADE,
    request_id INTEGER REFERENCES service_requests(id) ON DELETE CASCADE,
    ticket_id INTEGER NOT NULL REFERENCES service_tickets(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id),

    -- Check-in details
    join_location TEXT,              -- Where customer will board
    join_planet_id INTEGER,
    exit_location TEXT,              -- Where customer wants to exit (for flexible routes)
    exit_planet_id INTEGER,

    -- Status: 'pending', 'accepted', 'denied', 'completed', 'no_show'
    status TEXT DEFAULT 'pending',
    denial_reason TEXT,

    -- Discord tracking
    added_to_thread BOOLEAN DEFAULT false,

    checked_in_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMPTZ,

    -- Either flight_id OR request_id must be set (XOR)
    CONSTRAINT checkin_type_check CHECK (
      (flight_id IS NOT NULL AND request_id IS NULL) OR
      (flight_id IS NULL AND request_id IS NOT NULL)
    ),

    CONSTRAINT valid_checkin_status CHECK (
      status IN ('pending', 'accepted', 'denied', 'completed', 'no_show')
    )
);

CREATE INDEX idx_checkins_flight ON service_checkins(flight_id);
CREATE INDEX idx_checkins_request ON service_checkins(request_id);
CREATE INDEX idx_checkins_user ON service_checkins(user_id);
CREATE INDEX idx_checkins_ticket ON service_checkins(ticket_id);
CREATE INDEX idx_checkins_status ON service_checkins(status);


-- ===========================================
-- 7. ENHANCE TRANSPORT REQUEST DETAILS
-- ===========================================

ALTER TABLE service_transport_request_details
  ADD COLUMN IF NOT EXISTS ticket_id INTEGER REFERENCES service_tickets(id),
  ADD COLUMN IF NOT EXISTS customer_planet_id INTEGER,
  ADD COLUMN IF NOT EXISTS pickup_fee_waived BOOLEAN DEFAULT false;


-- ===========================================
-- 8. GRANT PERMISSIONS
-- ===========================================

GRANT SELECT, INSERT, UPDATE, DELETE ON service_ticket_offers TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON service_tickets TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON service_ticket_usage TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON service_flight_instances TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON service_flight_state_log TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON service_checkins TO nexus_users;

-- Grant sequence access
GRANT USAGE, SELECT ON SEQUENCE service_ticket_offers_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE service_tickets_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE service_ticket_usage_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE service_flight_instances_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE service_flight_state_log_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE service_checkins_id_seq TO nexus_users;

-- Grant permissions to bot user for flight management
GRANT SELECT, UPDATE ON service_flight_instances TO nexus_bot;
GRANT SELECT, UPDATE ON service_checkins TO nexus_bot;
GRANT SELECT ON service_flight_state_log TO nexus_bot;

COMMIT;
