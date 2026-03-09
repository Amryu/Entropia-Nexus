-- Migration: Rework blueprint drops to rule-based system
-- Description: Add IsDroppable and DropRarity columns to Blueprints, drop the BlueprintDrops table
-- Database: nexus
-- Date: 2026-03-09

BEGIN;

-- 1. Create the BlueprintDropRarity enum
CREATE TYPE "BlueprintDropRarity" AS ENUM (
    'Common',
    'Uncommon',
    'Rare',
    'Very Rare',
    'Extremely Rare'
);

-- 2. Add new columns to Blueprints (inherited by Blueprints_audit automatically)
ALTER TABLE "Blueprints"
    ADD COLUMN "IsDroppable" boolean NOT NULL DEFAULT false,
    ADD COLUMN "DropRarity" "BlueprintDropRarity";

-- 3. Create partial index for efficient drop lookups
CREATE INDEX "Blueprints_droppable_idx"
    ON "Blueprints" ("IsDroppable", "Type", "Level")
    WHERE "IsDroppable" = true;

-- 5. Drop the old BlueprintDrops junction table (start fresh)
DROP TRIGGER IF EXISTS "BlueprintDrops_audit_trigger" ON "BlueprintDrops";
DROP TABLE IF EXISTS "BlueprintDrops_audit";
DROP TABLE IF EXISTS "BlueprintDrops";
DROP FUNCTION IF EXISTS "BlueprintDrops_audit_trigger"();

COMMIT;
