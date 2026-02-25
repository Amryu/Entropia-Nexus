-- Track when unverified users leave the Discord server.
-- Used by the bot to delete unverified accounts absent for 7+ days.

ALTER TABLE users ADD COLUMN left_server_at TIMESTAMPTZ;

CREATE INDEX idx_users_unverified_left
  ON users (left_server_at)
  WHERE verified = false AND left_server_at IS NOT NULL;
