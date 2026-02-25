-- Migration: Rental feature tables
-- Allows users to rent out items (via Item Sets) to other players

-- ===========================================
-- ENUMS
-- ===========================================

CREATE TYPE rental_offer_status AS ENUM ('draft', 'available', 'rented', 'unlisted', 'deleted');
CREATE TYPE rental_request_status AS ENUM ('open', 'accepted', 'rejected', 'in_progress', 'completed', 'cancelled');


-- ===========================================
-- TABLES
-- ===========================================

-- Main rental offers table
CREATE TABLE rental_offers (
  id            SERIAL PRIMARY KEY,
  user_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  item_set_id   UUID NOT NULL REFERENCES item_sets(id) ON DELETE RESTRICT,
  title         TEXT NOT NULL,
  description   TEXT,
  planet_id     INTEGER,                              -- FK to Planets in nexus db
  location      TEXT,                                 -- Pickup/return location description

  -- Pricing
  price_per_day NUMERIC(10,2) NOT NULL,               -- Base price per day in PED
  discounts     JSONB DEFAULT '[]',                   -- [{minDays: 7, percent: 10}, ...]
  deposit       NUMERIC(10,2) NOT NULL DEFAULT 0,     -- Security deposit in PED (0 = no deposit)

  -- Status
  status        rental_offer_status NOT NULL DEFAULT 'draft',

  -- Metadata
  created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at    TIMESTAMPTZ                           -- Soft delete timestamp
);

-- Owner-blocked dates (manual unavailability)
CREATE TABLE rental_blocked_dates (
  id            SERIAL PRIMARY KEY,
  offer_id      INTEGER NOT NULL REFERENCES rental_offers(id) ON DELETE CASCADE,
  start_date    DATE NOT NULL,
  end_date      DATE NOT NULL,                        -- Inclusive
  reason        TEXT,
  CONSTRAINT valid_blocked_date_range CHECK (end_date >= start_date)
);

-- Rental requests / bookings
CREATE TABLE rental_requests (
  id              SERIAL PRIMARY KEY,
  offer_id        INTEGER NOT NULL REFERENCES rental_offers(id) ON DELETE CASCADE,
  requester_id    BIGINT NOT NULL REFERENCES users(id),

  -- Requested period
  start_date      DATE NOT NULL,
  end_date        DATE NOT NULL,                      -- Inclusive (last full rental day)

  -- Pricing snapshot (captured at creation, updated on extensions)
  total_days      INTEGER NOT NULL,
  price_per_day   NUMERIC(10,2) NOT NULL,             -- Effective rate after discount
  discount_pct    NUMERIC(5,2) NOT NULL DEFAULT 0,    -- Applied discount percentage
  total_price     NUMERIC(10,2) NOT NULL,             -- total_days * price_per_day
  deposit         NUMERIC(10,2) NOT NULL DEFAULT 0,   -- Deposit snapshot

  -- Status
  status          rental_request_status NOT NULL DEFAULT 'open',

  -- Actual dates (may differ from requested if early return)
  actual_return_date DATE,

  -- Notes
  requester_note  TEXT,                               -- Note from requester
  owner_note      TEXT,                               -- Note from owner (accept/reject reason)

  created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT valid_request_date_range CHECK (end_date >= start_date)
);

-- Rental period extensions
CREATE TABLE rental_extensions (
  id              SERIAL PRIMARY KEY,
  request_id      INTEGER NOT NULL REFERENCES rental_requests(id) ON DELETE CASCADE,

  -- Date changes
  previous_end    DATE NOT NULL,
  new_end         DATE NOT NULL,
  extra_days      INTEGER NOT NULL,

  -- Pricing for the extension
  retroactive     BOOLEAN NOT NULL DEFAULT false,     -- If true, discount recalculated for total duration
  price_per_day   NUMERIC(10,2) NOT NULL,             -- Rate for extra days
  discount_pct    NUMERIC(5,2) NOT NULL DEFAULT 0,    -- Discount applied
  extra_price     NUMERIC(10,2) NOT NULL,             -- Cost of the extension
  new_total_price NUMERIC(10,2) NOT NULL,             -- Updated total for full rental

  -- Owner note explaining terms
  note            TEXT,

  created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ===========================================
-- INDEXES
-- ===========================================

CREATE INDEX idx_rental_offers_user_id ON rental_offers(user_id);
CREATE INDEX idx_rental_offers_status ON rental_offers(status) WHERE status = 'available';
CREATE INDEX idx_rental_offers_item_set ON rental_offers(item_set_id);

CREATE INDEX idx_rental_blocked_dates_offer ON rental_blocked_dates(offer_id);
CREATE INDEX idx_rental_blocked_dates_range ON rental_blocked_dates(start_date, end_date);

CREATE INDEX idx_rental_requests_offer ON rental_requests(offer_id);
CREATE INDEX idx_rental_requests_requester ON rental_requests(requester_id);
CREATE INDEX idx_rental_requests_status ON rental_requests(status);
CREATE INDEX idx_rental_requests_dates ON rental_requests(start_date, end_date);

CREATE INDEX idx_rental_extensions_request ON rental_extensions(request_id);


-- ===========================================
-- PERMISSIONS
-- ===========================================

-- rental_offers
GRANT SELECT, INSERT, UPDATE, DELETE ON rental_offers TO nexus_users;
GRANT ALL ON rental_offers TO postgres;

-- rental_blocked_dates
GRANT SELECT, INSERT, UPDATE, DELETE ON rental_blocked_dates TO nexus_users;
GRANT ALL ON rental_blocked_dates TO postgres;

-- rental_requests
GRANT SELECT, INSERT, UPDATE, DELETE ON rental_requests TO nexus_users;
GRANT ALL ON rental_requests TO postgres;

-- rental_extensions
GRANT SELECT, INSERT, UPDATE, DELETE ON rental_extensions TO nexus_users;
GRANT ALL ON rental_extensions TO postgres;

-- Sequence permissions
GRANT USAGE, SELECT, UPDATE ON SEQUENCE rental_offers_id_seq TO nexus_users;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE rental_blocked_dates_id_seq TO nexus_users;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE rental_requests_id_seq TO nexus_users;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE rental_extensions_id_seq TO nexus_users;
