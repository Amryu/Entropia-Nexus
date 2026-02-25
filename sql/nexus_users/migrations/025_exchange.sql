-- Exchange (order-book marketplace) migration
-- Alters trade_offers table and creates user_items table

-- 1. Create state enum for offers
CREATE TYPE trade_offer_state AS ENUM ('active', 'stale', 'expired', 'terminated', 'closed');

-- 2. Alter trade_offers: add columns, fix user_id type
ALTER TABLE trade_offers
  ALTER COLUMN user_id TYPE BIGINT,
  ADD COLUMN state trade_offer_state NOT NULL DEFAULT 'active',
  ADD COLUMN planet VARCHAR(50) DEFAULT NULL,
  ADD COLUMN markup NUMERIC DEFAULT 0,
  ADD COLUMN bumped_at TIMESTAMPTZ;

-- Backfill bumped_at from created for any existing rows
UPDATE trade_offers SET bumped_at = created WHERE bumped_at IS NULL;

-- Now make bumped_at NOT NULL with default
ALTER TABLE trade_offers
  ALTER COLUMN bumped_at SET NOT NULL,
  ALTER COLUMN bumped_at SET DEFAULT NOW();

-- 3. Add indexes for trade_offers
-- Order book lookup: all offers for an item by side and state
CREATE INDEX trade_offers_item_type_state_idx ON trade_offers (item_id, type, state);

-- My offers lookup: user's offers by state
CREATE INDEX trade_offers_user_state_idx ON trade_offers (user_id, state);

-- Staleness batch cleanup: find offers by state and age
CREATE INDEX trade_offers_state_bumped_idx ON trade_offers (state, bumped_at);

-- Enforce 1 active offer per item per user per side
CREATE UNIQUE INDEX trade_offers_user_item_type_active_uq
  ON trade_offers (user_id, item_id, type)
  WHERE state NOT IN ('closed', 'terminated');

-- 4. Create user_items table for inventory
CREATE TABLE user_items (
  id            SERIAL PRIMARY KEY,
  user_id       BIGINT NOT NULL,
  item_id       INTEGER NOT NULL,
  item_name     VARCHAR(255) NOT NULL,
  quantity      INTEGER NOT NULL DEFAULT 0,
  instance_key  VARCHAR(255) DEFAULT NULL,
  details       JSONB DEFAULT NULL,
  storage       VARCHAR(10) NOT NULL DEFAULT 'server',
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fungible items: one row per (user, item) where instance_key is null
CREATE UNIQUE INDEX user_items_fungible_uq ON user_items (user_id, item_id) WHERE instance_key IS NULL;

-- Non-fungible items: one row per (user, item, instance) where instance_key is not null
CREATE UNIQUE INDEX user_items_instance_uq ON user_items (user_id, item_id, instance_key) WHERE instance_key IS NOT NULL;

-- User inventory lookup
CREATE INDEX user_items_user_idx ON user_items (user_id);

-- 5. Grant permissions to app role if needed
-- (Assuming the app connects as the table owner or has appropriate permissions)
