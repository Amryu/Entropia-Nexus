-- Migration: Admin Dashboard Support
-- Adds tracking for change approval/denial and user lock/ban functionality

-- =============================================
-- CHANGES TABLE ADDITIONS
-- =============================================

-- Add created_at timestamp (backfill from last_update for existing records)
ALTER TABLE changes ADD COLUMN IF NOT EXISTS created_at timestamp with time zone;

-- Update existing records to use last_update as created_at if null
UPDATE changes SET created_at = last_update WHERE created_at IS NULL;

-- Set default for new records
ALTER TABLE changes ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;

-- Add reviewed_at and reviewed_by for tracking who approved/denied
ALTER TABLE changes ADD COLUMN IF NOT EXISTS reviewed_at timestamp with time zone;
ALTER TABLE changes ADD COLUMN IF NOT EXISTS reviewed_by bigint REFERENCES users(id);

-- Index for efficient querying by state and entity type
CREATE INDEX IF NOT EXISTS idx_changes_state ON changes(state);
CREATE INDEX IF NOT EXISTS idx_changes_entity ON changes(entity);
CREATE INDEX IF NOT EXISTS idx_changes_author ON changes(author_id);
CREATE INDEX IF NOT EXISTS idx_changes_created ON changes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_changes_reviewed ON changes(reviewed_at DESC) WHERE reviewed_at IS NOT NULL;

-- =============================================
-- USERS TABLE ADDITIONS - LOCK FUNCTIONALITY
-- =============================================

-- Lock: Restricts user from verified-only features without full ban
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked boolean DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_at timestamp with time zone;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_reason text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_by bigint REFERENCES users(id);

-- =============================================
-- USERS TABLE ADDITIONS - BAN FUNCTIONALITY
-- =============================================

-- Ban: Complete access denial
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned boolean DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_at timestamp with time zone;
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_until timestamp with time zone; -- NULL = permanent
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_reason text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_by bigint REFERENCES users(id);

-- Index for quick filtering of locked/banned users
CREATE INDEX IF NOT EXISTS idx_users_locked ON users(locked) WHERE locked = true;
CREATE INDEX IF NOT EXISTS idx_users_banned ON users(banned) WHERE banned = true;

-- =============================================
-- CHANGE HISTORY TABLE (for tracking data versions)
-- =============================================

-- Store historical snapshots of change data for diff viewing
CREATE TABLE IF NOT EXISTS change_history (
    id serial PRIMARY KEY,
    change_id integer NOT NULL REFERENCES changes(id) ON DELETE CASCADE,
    data jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    created_by bigint REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_change_history_change ON change_history(change_id);
CREATE INDEX IF NOT EXISTS idx_change_history_created ON change_history(created_at DESC);

-- =============================================
-- ADMIN ACTION LOG (for audit trail)
-- =============================================

CREATE TABLE IF NOT EXISTS admin_actions (
    id serial PRIMARY KEY,
    admin_id bigint NOT NULL REFERENCES users(id),
    action_type text NOT NULL, -- 'lock', 'unlock', 'ban', 'unban', 'approve_change', 'deny_change'
    target_type text NOT NULL, -- 'user', 'change'
    target_id text NOT NULL, -- user id or change id
    reason text,
    metadata jsonb, -- additional context (ban duration, etc.)
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_admin_actions_admin ON admin_actions(admin_id);
CREATE INDEX IF NOT EXISTS idx_admin_actions_target ON admin_actions(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_admin_actions_created ON admin_actions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_actions_type ON admin_actions(action_type);

-- =============================================
-- GRANT PERMISSIONS TO BOT
-- =============================================

-- Grant permissions on new tables/columns to the bot user
GRANT SELECT, INSERT ON change_history TO "nexus-bot";
GRANT SELECT, UPDATE ON changes TO "nexus-bot";
GRANT SELECT, INSERT ON admin_actions TO "nexus-bot";
GRANT SELECT, UPDATE ON users TO "nexus-bot";
GRANT USAGE ON SEQUENCE change_history_id_seq TO "nexus-bot";
GRANT USAGE ON SEQUENCE admin_actions_id_seq TO "nexus-bot";
