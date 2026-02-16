-- Migration: Add manager/owner role distinction to transportation services
-- and Discord server integration for warp services.
--
-- services.user_id becomes the "manager" (the Nexus user who manages the service).
-- owner_user_id and owner_display_name allow designating a separate real-world owner.

-- Owner fields on services
ALTER TABLE services ADD COLUMN owner_user_id BIGINT REFERENCES users(id);
ALTER TABLE services ADD COLUMN owner_display_name TEXT;

-- Discord invite code for warp transportation services (disables Nexus thread creation)
ALTER TABLE service_transportation_details ADD COLUMN discord_code TEXT;
