-- Trade channel configuration: maps channel names to planets
-- Allows admins to control which channels are accepted for trade ingestion.

CREATE TABLE ingestion_trade_channels (
  id SERIAL PRIMARY KEY,
  channel_name TEXT NOT NULL UNIQUE,
  planet TEXT,                          -- NULL = Global
  added_at TIMESTAMPTZ DEFAULT now(),
  added_by BIGINT NOT NULL
);

-- Seed known Entropia Universe trade channels
INSERT INTO ingestion_trade_channels (channel_name, planet, added_by) VALUES
  ('#trade', NULL, 1),
  ('#arktrade', 'Arkadia', 1),
  ('#calytrade', 'Calypso', 1),
  ('#cyrtrade', 'Cyrene', 1),
  ('#rocktrade', 'Rocktropia', 1),
  ('#touchtrade', 'Toulan', 1),
  ('#nixtrade', 'Next Island', 1);

-- Index for repost dedup: find recent messages by same user in same channel
CREATE INDEX idx_ingested_trades_repost
  ON ingested_trade_messages (username, channel, event_timestamp DESC);
