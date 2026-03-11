-- Migration: Rename AreaType 'WaveEvent' to 'WaveEventArea'
-- Description: Migration 059 originally used 'WaveEvent' as the AreaType value.
--   This corrects it to 'WaveEventArea' for consistency with other area types
--   (MobArea, LandArea, etc.). Safe to run on DBs that never ran the old 059.
-- Database: nexus
-- Date: 2026-03-11
-- IDEMPOTENT: Safe to re-run

BEGIN;

-- Step 1: Add the correctly-named value (safe if already present)
ALTER TYPE "AreaType" ADD VALUE IF NOT EXISTS 'WaveEventArea';

-- Step 2: Re-run data migration in case 059 used the old name
UPDATE ONLY "Areas"
  SET "Type" = 'WaveEventArea'
  WHERE "Type" = 'WaveEvent';

COMMIT;
