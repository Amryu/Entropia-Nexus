-- Add value and container columns to user_items for richer inventory tracking
ALTER TABLE user_items ADD COLUMN IF NOT EXISTS value NUMERIC DEFAULT NULL;
ALTER TABLE user_items ADD COLUMN IF NOT EXISTS container VARCHAR(255) DEFAULT NULL;

-- Grant permissions to the application role
GRANT SELECT, INSERT, UPDATE, DELETE ON user_items TO nexus_users;
