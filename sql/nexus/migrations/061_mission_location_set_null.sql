-- Migration: Fix Missions.StartLocationId to SET NULL on location delete
-- Description: Add ON DELETE SET NULL so deleting a location doesn't orphan mission references
-- Database: nexus
-- Date: 2026-03-13

BEGIN;

ALTER TABLE "Missions"
DROP CONSTRAINT IF EXISTS "Missions_StartLocationId_fkey";

ALTER TABLE "Missions"
ADD CONSTRAINT "Missions_StartLocationId_fkey"
FOREIGN KEY ("StartLocationId") REFERENCES "Locations"("Id") ON DELETE SET NULL;

COMMIT;
