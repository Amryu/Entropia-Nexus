-- Migration: 005_flight_flexible_routes
-- Description: Add flexible route support to flights and exit tracking to check-ins
-- Date: 2026-01-28

BEGIN;

-- ===========================================
-- 1. ADD ROUTE_TYPE TO FLIGHT INSTANCES
-- ===========================================

ALTER TABLE service_flight_instances
  ADD COLUMN IF NOT EXISTS route_type TEXT DEFAULT 'fixed';

-- Add check constraint for valid route types
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'valid_flight_route_type'
  ) THEN
    ALTER TABLE service_flight_instances
      ADD CONSTRAINT valid_flight_route_type
      CHECK (route_type IN ('fixed', 'flexible'));
  END IF;
END $$;


-- ===========================================
-- 2. ADD EXIT TRACKING TO CHECK-INS
-- ===========================================

-- For flexible routes, customers specify where they want to exit
ALTER TABLE service_checkins
  ADD COLUMN IF NOT EXISTS exit_location TEXT,
  ADD COLUMN IF NOT EXISTS exit_planet_id INTEGER;


COMMIT;
