-- Migration: Add content_updated_at column to changes table
-- This column tracks when the actual change content (data) was last modified
-- The bot should use this instead of last_update to detect user edits
-- last_update still updates on every change (including admin actions like setting thread_id)

-- Add the new column
ALTER TABLE changes ADD COLUMN IF NOT EXISTS content_updated_at TIMESTAMP WITH TIME ZONE;

-- Initialize content_updated_at to match last_update for existing rows
UPDATE changes SET content_updated_at = last_update WHERE content_updated_at IS NULL;

-- Set default for new rows
ALTER TABLE changes ALTER COLUMN content_updated_at SET DEFAULT NOW();

-- Create or replace the trigger function to update content_updated_at only for content changes
CREATE OR REPLACE FUNCTION update_content_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    -- Only update content_updated_at if the data column changed
    IF TG_OP = 'INSERT' THEN
        NEW.content_updated_at = NOW();
    ELSIF TG_OP = 'UPDATE' THEN
        -- Only update if data or state (to Draft/Pending) changed
        IF (OLD.data IS DISTINCT FROM NEW.data) OR
           (OLD.state IS DISTINCT FROM NEW.state AND NEW.state IN ('Draft', 'Pending')) THEN
            NEW.content_updated_at = NOW();
        ELSE
            -- Preserve the original content_updated_at
            NEW.content_updated_at = OLD.content_updated_at;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger (drop first if exists)
DROP TRIGGER IF EXISTS update_content_updated_at_trigger ON changes;
CREATE TRIGGER update_content_updated_at_trigger
    BEFORE INSERT OR UPDATE ON changes
    FOR EACH ROW
    EXECUTE FUNCTION update_content_updated_at();

-- Grant permissions to the bot user
GRANT SELECT, UPDATE ON changes TO nexus_bot;

-- Grant SELECT permission to the API user (for entity-changes endpoints)
-- Note: nexus_users is the database user for the SvelteKit app
GRANT SELECT ON changes TO nexus_users;
GRANT SELECT ON change_history TO nexus_users;
