-- Negotiable inventory listings on the exchange
-- Users can list inventory items without a price; buyers propose offers.

-- 1. Store per-user filter configuration for what inventory to list
CREATE TABLE user_negotiable_configs (
  id           SERIAL PRIMARY KEY,
  user_id      BIGINT NOT NULL UNIQUE,
  config       JSONB NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX user_negotiable_configs_user_idx ON user_negotiable_configs (user_id);

-- 2. Allow explicit NULL markup on trade_offers (NULL = negotiable/no price)
ALTER TABLE trade_offers ALTER COLUMN markup DROP DEFAULT;

-- 3. Partial index for efficient lookup of negotiable offers
CREATE INDEX trade_offers_negotiable_idx
  ON trade_offers (user_id, item_id)
  WHERE markup IS NULL AND state != 'closed';

-- 4. Grant permissions to app role
GRANT ALL ON TABLE user_negotiable_configs TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE user_negotiable_configs_id_seq TO nexus_users;
