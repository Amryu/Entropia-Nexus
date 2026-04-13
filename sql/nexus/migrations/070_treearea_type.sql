-- Migration: Add 'TreeArea' AreaType for harvesting activity areas
-- Description: TreeArea is a new area polygon type used to represent
--   harvestable tree clusters / forests on the maps. Gameplay analog to
--   MobArea but for the harvesting profession.
-- Database: nexus
-- Date: 2026-04-13
-- IDEMPOTENT: Safe to re-run

BEGIN;

ALTER TYPE "AreaType" ADD VALUE IF NOT EXISTS 'TreeArea';

COMMIT;
