-- Migration: Remove occurrence upper bound limit
-- Allow any positive occurrence value, not just 1-3.
-- Database: nexus_users

ALTER TABLE ingested_globals DROP CONSTRAINT chk_occurrence_range;
ALTER TABLE ingested_globals ADD CONSTRAINT chk_occurrence_positive CHECK (occurrence >= 1);
