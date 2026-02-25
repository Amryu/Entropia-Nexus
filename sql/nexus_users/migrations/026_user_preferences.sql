-- 026_user_preferences.sql
-- Upgrade existing user_settings table to a proper user_preferences system.
-- Fixes user_id type (INTEGER → BIGINT to match users.id),
-- renames value → data and changes TEXT → JSONB,
-- adds updated_at timestamp and key length constraint,
-- renames table to user_preferences.

-- 1. Fix user_id type to match users.id (BIGINT)
ALTER TABLE user_settings
  ALTER COLUMN user_id TYPE BIGINT;

-- 2. Rename value column to data
ALTER TABLE user_settings
  RENAME COLUMN value TO data;

-- 3. Drop any existing default, change type to JSONB, then set JSONB default
ALTER TABLE user_settings
  ALTER COLUMN data DROP DEFAULT;

ALTER TABLE user_settings
  ALTER COLUMN data TYPE JSONB USING COALESCE(data::jsonb, '{}'::jsonb);

ALTER TABLE user_settings
  ALTER COLUMN data SET NOT NULL;

ALTER TABLE user_settings
  ALTER COLUMN data SET DEFAULT '{}'::jsonb;

-- 4. Add updated_at timestamp
ALTER TABLE user_settings
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- 5. Add key length constraint
ALTER TABLE user_settings
  ADD CONSTRAINT user_settings_key_length CHECK (char_length(key) <= 100);

-- 6. Rename table to user_preferences
ALTER TABLE user_settings RENAME TO user_preferences;

-- 7. Rename the primary key constraint to match new table name
ALTER INDEX IF EXISTS user_settings_pkey RENAME TO user_preferences_pkey;

-- 8. Rename the key length constraint to match new table name
ALTER TABLE user_preferences
  RENAME CONSTRAINT user_settings_key_length TO user_preferences_key_length;

-- 9. Add foreign key to users table
ALTER TABLE user_preferences
  ADD CONSTRAINT user_preferences_user_id_fk
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- 10. Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON user_preferences TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_preferences TO "nexus-bot";
GRANT ALL ON user_preferences TO postgres;
