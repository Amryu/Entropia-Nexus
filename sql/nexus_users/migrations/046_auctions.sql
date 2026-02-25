-- Migration: Auction system tables
-- Allows users to auction item sets with timed bidding, buyout pricing,
-- admin controls (freeze, cancel, rollback), and full audit logging.

-- ===========================================
-- ENUMS
-- ===========================================

CREATE TYPE auction_status AS ENUM ('draft', 'active', 'ended', 'settled', 'cancelled', 'frozen');
CREATE TYPE auction_bid_status AS ENUM ('active', 'outbid', 'won', 'rolled_back');
CREATE TYPE auction_audit_action AS ENUM (
  'created', 'activated', 'bid_placed', 'buyout',
  'ended', 'settled', 'cancelled_by_seller', 'cancelled_by_admin',
  'frozen', 'unfrozen', 'bid_rolled_back', 'edited'
);


-- ===========================================
-- TABLES
-- ===========================================

-- Main auction listings
CREATE TABLE auctions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  seller_id       BIGINT NOT NULL REFERENCES users(id),
  item_set_id     UUID NOT NULL REFERENCES item_sets(id) ON DELETE RESTRICT,
  title           TEXT NOT NULL,
  description     TEXT,

  -- Pricing
  starting_bid    NUMERIC(12,2) NOT NULL CHECK (starting_bid >= 0.01),
  buyout_price    NUMERIC(12,2) CHECK (buyout_price IS NULL OR buyout_price >= starting_bid),
  current_bid     NUMERIC(12,2),
  current_bidder  BIGINT REFERENCES users(id),
  bid_count       INTEGER NOT NULL DEFAULT 0,
  fee             NUMERIC(12,2) NOT NULL DEFAULT 0,

  -- Status & timing
  status          auction_status NOT NULL DEFAULT 'draft',
  duration_days   INTEGER NOT NULL CHECK (duration_days BETWEEN 1 AND 365),
  starts_at       TIMESTAMPTZ,
  ends_at         TIMESTAMPTZ,
  settled_at      TIMESTAMPTZ,

  -- Anti-sniping: track original end time to cap extensions
  original_ends_at TIMESTAMPTZ,

  -- Freeze tracking: accumulated frozen duration for end time extension
  frozen_at       TIMESTAMPTZ,

  -- Metadata
  created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at      TIMESTAMPTZ
);

-- Bid history
CREATE TABLE auction_bids (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  auction_id  UUID NOT NULL REFERENCES auctions(id),
  bidder_id   BIGINT NOT NULL REFERENCES users(id),
  amount      NUMERIC(12,2) NOT NULL,
  status      auction_bid_status NOT NULL DEFAULT 'active',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Full audit trail for all auction actions
CREATE TABLE auction_audit_log (
  id          BIGSERIAL PRIMARY KEY,
  auction_id  UUID NOT NULL REFERENCES auctions(id),
  user_id     BIGINT REFERENCES users(id),
  action      auction_audit_action NOT NULL,
  details     JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Disclaimer acceptance tracking (one per user per role)
CREATE TABLE auction_disclaimers (
  user_id     BIGINT NOT NULL REFERENCES users(id),
  role        TEXT NOT NULL CHECK (role IN ('bidder', 'seller')),
  accepted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, role)
);

-- Item set "customized" flag for custom item images
ALTER TABLE item_sets ADD COLUMN IF NOT EXISTS customized BOOLEAN NOT NULL DEFAULT false;


-- ===========================================
-- INDEXES
-- ===========================================

-- Auction listing queries
CREATE INDEX idx_auctions_status ON auctions(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_auctions_seller ON auctions(seller_id);
CREATE INDEX idx_auctions_ends_at ON auctions(ends_at) WHERE status = 'active';
CREATE INDEX idx_auctions_item_set ON auctions(item_set_id);

-- Bid queries
CREATE INDEX idx_auction_bids_auction ON auction_bids(auction_id, created_at);
CREATE INDEX idx_auction_bids_bidder ON auction_bids(bidder_id);

-- Audit log queries
CREATE INDEX idx_auction_audit_log_auction ON auction_audit_log(auction_id, created_at);

-- Disclaimer lookups
CREATE INDEX idx_auction_disclaimers_user ON auction_disclaimers(user_id);


-- ===========================================
-- PERMISSIONS
-- ===========================================

-- auctions
GRANT SELECT, INSERT, UPDATE, DELETE ON auctions TO nexus_users;
GRANT ALL ON auctions TO postgres;

-- auction_bids
GRANT SELECT, INSERT, UPDATE ON auction_bids TO nexus_users;
GRANT ALL ON auction_bids TO postgres;

-- auction_audit_log
GRANT SELECT, INSERT ON auction_audit_log TO nexus_users;
GRANT ALL ON auction_audit_log TO postgres;

-- auction_disclaimers
GRANT SELECT, INSERT ON auction_disclaimers TO nexus_users;
GRANT ALL ON auction_disclaimers TO postgres;

-- Sequence permissions
GRANT USAGE, SELECT, UPDATE ON SEQUENCE auction_audit_log_id_seq TO nexus_users;
