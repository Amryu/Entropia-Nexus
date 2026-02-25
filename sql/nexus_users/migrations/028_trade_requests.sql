-- Migration: Trade request tables for exchange marketplace
-- Allows users to initiate trade requests that create Discord threads for negotiation

-- 1. Trade requests table
CREATE TABLE trade_requests (
  id SERIAL PRIMARY KEY,
  requester_id BIGINT NOT NULL,
  target_id BIGINT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
    -- pending: created, waiting for bot to open Discord thread
    -- active: Discord thread created, users negotiating
    -- completed: trade finished (/done command)
    -- cancelled: one party cancelled
    -- expired: auto-closed after 24h inactivity
  planet TEXT,
  discord_thread_id TEXT,
  last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  warning_sent BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  closed_at TIMESTAMPTZ
);

-- Only 1 open request between any 2 users at a time (direction-independent)
CREATE UNIQUE INDEX trade_requests_open_pair_uq
  ON trade_requests (LEAST(requester_id, target_id), GREATEST(requester_id, target_id))
  WHERE status IN ('pending', 'active');

CREATE INDEX trade_requests_requester_idx ON trade_requests (requester_id, status);
CREATE INDEX trade_requests_target_idx ON trade_requests (target_id, status);
CREATE INDEX trade_requests_status_activity_idx ON trade_requests (status, last_activity_at);

-- 2. Items within a trade request
CREATE TABLE trade_request_items (
  id SERIAL PRIMARY KEY,
  trade_request_id INTEGER NOT NULL REFERENCES trade_requests(id) ON DELETE CASCADE,
  offer_id INTEGER,          -- references trade_offers.id (nullable, bulk may not have one)
  item_id INTEGER NOT NULL,
  item_name TEXT NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 1,
  markup NUMERIC,
  side TEXT NOT NULL,         -- 'BUY' or 'SELL' (what the original offer was)
  added_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX trade_request_items_request_idx ON trade_request_items (trade_request_id);

-- 3. Grant permissions to app role
GRANT SELECT, INSERT, UPDATE, DELETE ON trade_requests TO nexus_users;
GRANT USAGE ON SEQUENCE trade_requests_id_seq TO nexus_users;

GRANT SELECT, INSERT, UPDATE, DELETE ON trade_request_items TO nexus_users;
GRANT USAGE ON SEQUENCE trade_request_items_id_seq TO nexus_users;
