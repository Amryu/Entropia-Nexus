-- Migration: Drop dead ingestion_conflicts table and slot conflict indexes
-- Slot conflict detection has been removed; nothing writes to ingestion_conflicts anymore.
-- Fraud detection (collusion, solo fabrication) queries ingested_global_submissions directly.
-- Database: nexus_users

BEGIN;

-- Drop indexes on ingestion_conflicts
DROP INDEX IF EXISTS idx_ingestion_conflicts_user;
DROP INDEX IF EXISTS idx_ingestion_conflicts_created;
DROP INDEX IF EXISTS idx_ingestion_conflicts_existing;
DROP INDEX IF EXISTS idx_ingestion_conflicts_type_created;

-- Drop the table
DROP TABLE IF EXISTS ingestion_conflicts;

-- Drop slot conflict detection indexes (no longer used)
DROP INDEX IF EXISTS idx_ingested_globals_slot;
DROP INDEX IF EXISTS idx_ingested_trades_slot;

COMMIT;
