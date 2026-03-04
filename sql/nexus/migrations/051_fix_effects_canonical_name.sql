-- Migration: Fix Effects.CanonicalName column and Name unique constraint
-- Original migration 030 used ALTER TABLE ONLY which is incompatible with
-- PostgreSQL table inheritance (ADD COLUMN cannot use ONLY when child tables
-- exist). This migration applies the same changes without ONLY.
-- IDEMPOTENT: Safe to re-run (uses IF NOT EXISTS / IF NOT EXISTS patterns)
-- Database: nexus

BEGIN;

-- Add CanonicalName column (propagates to Effects_audit via inheritance)
ALTER TABLE "Effects" ADD COLUMN IF NOT EXISTS "CanonicalName" TEXT;

-- Add UNIQUE constraint on Name (required for bot upsert-by-name pattern)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'Effects_Name_key'
  ) THEN
    ALTER TABLE ONLY "Effects"
      ADD CONSTRAINT "Effects_Name_key" UNIQUE ("Name");
  END IF;
END $$;

COMMIT;
