-- Add markup-aware estimated value and unknown items value to import snapshots
BEGIN;

ALTER TABLE inventory_imports
  ADD COLUMN IF NOT EXISTS estimated_value NUMERIC DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS unknown_value NUMERIC DEFAULT NULL;

COMMIT;
