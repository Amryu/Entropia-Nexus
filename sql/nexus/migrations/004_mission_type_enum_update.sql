-- Migration: Update MissionType enum
-- Description: Rename 'Regular' to 'One-Time' and remove 'Event' value (event association is now independent of type)
-- Database: nexus
-- Date: 2026-02-05

BEGIN;

-- ===========================================
-- UPDATE MISSIONTYPE ENUM
-- ===========================================
-- Old values: 'Regular', 'Repeatable', 'Recurring', 'Event'
-- New values: 'One-Time', 'Repeatable', 'Recurring'
--
-- Changes:
-- - 'Regular' renamed to 'One-Time' for clarity (mission can only be completed once)
-- - 'Event' removed - event association is now handled via EventId foreign key independent of type

-- Step 1: Add the new 'One-Time' value to the enum
ALTER TYPE "MissionType" ADD VALUE IF NOT EXISTS 'One-Time';

COMMIT;

-- Note: PostgreSQL doesn't allow removing enum values or renaming within a transaction easily.
-- We need to handle existing 'Regular' and 'Event' values in application code.
-- The database will continue to accept old values, but the frontend will only show the new values.

-- For a clean migration, we need to:
-- 1. Update existing 'Regular' values to 'One-Time'
-- 2. Update existing 'Event' values to an appropriate type

BEGIN;

-- Update existing missions with 'Regular' type to 'One-Time'
UPDATE "Missions" SET "Type" = 'One-Time' WHERE "Type" = 'Regular';

-- Update existing missions with 'Event' type to 'One-Time'
-- (they still keep their EventId reference for event association)
UPDATE "Missions" SET "Type" = 'One-Time' WHERE "Type" = 'Event';

-- Also update audit table if it has any records with old values
UPDATE "Missions_audit" SET "Type" = 'One-Time' WHERE "Type" = 'Regular';
UPDATE "Missions_audit" SET "Type" = 'One-Time' WHERE "Type" = 'Event';

-- Update the default value for the Type column
ALTER TABLE "Missions" ALTER COLUMN "Type" SET DEFAULT 'One-Time';

-- Update the comment to reflect new enum values
COMMENT ON COLUMN "Missions"."Type" IS 'Mission repeatability type: One-Time (single completion), Repeatable (can be done again immediately), Recurring (can be done again after cooldown)';

-- ===========================================
-- ADD COOLDOWN CONFIGURATION FOR RECURRING MISSIONS
-- ===========================================

-- Create enum for cooldown start trigger
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'CooldownStartsOn') THEN
    CREATE TYPE "CooldownStartsOn" AS ENUM ('Accept', 'Completion');
  END IF;
END$$;

-- Add CooldownStartsOn column to Missions table
ALTER TABLE "Missions" ADD COLUMN IF NOT EXISTS "CooldownStartsOn" "CooldownStartsOn";

-- Update comment for CooldownDuration
COMMENT ON COLUMN "Missions"."CooldownDuration" IS 'Cooldown duration before mission can be repeated (1 minute to 30 days). Only used when Type = Recurring.';
COMMENT ON COLUMN "Missions"."CooldownStartsOn" IS 'When the cooldown timer starts: Accept (on mission accept) or Completion (on mission completion). Only used when Type = Recurring.';

-- Add column to audit table if it exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'Missions_audit') THEN
    ALTER TABLE "Missions_audit" ADD COLUMN IF NOT EXISTS "CooldownStartsOn" "CooldownStartsOn";
  END IF;
END$$;

COMMIT;
