-- Migration: Service Pilots
-- Allow transportation service owners to add pilots who can manage flights and update ship location
-- Pilots cannot edit service settings or ticket offers

-- Create service_pilots table
CREATE TABLE IF NOT EXISTS service_pilots (
    id SERIAL PRIMARY KEY,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    added_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(service_id, user_id)
);

-- Index for efficient lookup of pilots by service
CREATE INDEX IF NOT EXISTS idx_service_pilots_service_id ON service_pilots(service_id);

-- Index for efficient lookup of services a user is pilot for
CREATE INDEX IF NOT EXISTS idx_service_pilots_user_id ON service_pilots(user_id);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON service_pilots TO "nexus-users";
GRANT USAGE, SELECT ON SEQUENCE service_pilots_id_seq TO "nexus-users";

-- Grant bot permissions (for flight thread creation with pilot info)
GRANT SELECT ON service_pilots TO "nexus-bot";
