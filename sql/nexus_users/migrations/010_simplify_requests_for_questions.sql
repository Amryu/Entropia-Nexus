-- Migration: 010_simplify_requests_for_questions
-- Description: Remove request workflow for HPS/DPS/Custom services, keep only for questions
-- Transportation now uses tickets + check-ins + flights instead of requests
-- Date: 2026-01-29

BEGIN;

-- ===========================================
-- 1. DROP OBSOLETE TABLES
-- ===========================================

-- service_transport_request_details: No longer needed
-- Transportation now uses service_checkins directly with flights
DROP TABLE IF EXISTS service_transport_request_details CASCADE;

-- service_locked_slots: No longer needed
-- Was used for time-slot booking which is removed
DROP TABLE IF EXISTS service_locked_slots CASCADE;


-- ===========================================
-- 2. UPDATE SERVICE_CHECKINS CONSTRAINT
-- ===========================================

-- Remove the XOR constraint that required either flight_id OR request_id
-- Now check-ins only reference flights (request_id column kept for legacy/migration safety)
ALTER TABLE service_checkins DROP CONSTRAINT IF EXISTS checkin_type_check;

-- Make request_id nullable without constraint
-- (It was already nullable, but had a constraint requiring one of flight_id/request_id)

-- Add new constraint: flight_id is required for check-ins
-- Note: keeping request_id column for now to avoid breaking any existing data
ALTER TABLE service_checkins
  ADD CONSTRAINT checkin_flight_required CHECK (flight_id IS NOT NULL);


-- ===========================================
-- 3. SIMPLIFY SERVICE_REQUESTS TABLE
-- ===========================================

-- Drop columns that were only used for time-based booking requests
-- Keep: id, service_id, requester_id, status, service_notes, discord_thread_id, created_at, updated_at

-- Time-related columns (not needed for questions)
ALTER TABLE service_requests DROP COLUMN IF EXISTS requested_start;
ALTER TABLE service_requests DROP COLUMN IF EXISTS requested_duration_minutes;
ALTER TABLE service_requests DROP COLUMN IF EXISTS is_open_ended;
ALTER TABLE service_requests DROP COLUMN IF EXISTS final_start;
ALTER TABLE service_requests DROP COLUMN IF EXISTS final_duration_minutes;

-- Pricing columns (not needed for questions)
ALTER TABLE service_requests DROP COLUMN IF EXISTS final_price;
ALTER TABLE service_requests DROP COLUMN IF EXISTS actual_payment;

-- Actual execution tracking (not needed for questions)
ALTER TABLE service_requests DROP COLUMN IF EXISTS actual_start;
ALTER TABLE service_requests DROP COLUMN IF EXISTS actual_end;
ALTER TABLE service_requests DROP COLUMN IF EXISTS actual_decay_ped;
ALTER TABLE service_requests DROP COLUMN IF EXISTS break_minutes;

-- Review columns (not needed for questions)
ALTER TABLE service_requests DROP COLUMN IF EXISTS review_score;
ALTER TABLE service_requests DROP COLUMN IF EXISTS review_comment;
ALTER TABLE service_requests DROP COLUMN IF EXISTS reviewed_at;


-- ===========================================
-- 4. ADD COMMENT TO CLARIFY PURPOSE
-- ===========================================

COMMENT ON TABLE service_requests IS
  'Used only for service questions (service_notes starts with [QUESTION]). '
  'The request workflow for HPS/DPS/Custom services has been removed. '
  'Transportation uses tickets + check-ins + flights instead.';

COMMENT ON COLUMN service_requests.service_notes IS
  'Question content, prefixed with [QUESTION]';


-- ===========================================
-- 5. DROP UNUSED INDEXES
-- ===========================================

-- Index on status is still useful for finding pending questions
-- Keep: idx_service_requests_service_id, idx_service_requests_requester_id, idx_service_requests_status

-- Drop the locked_slots indexes (table was dropped)
DROP INDEX IF EXISTS idx_service_locked_slots_service_id;
DROP INDEX IF EXISTS idx_service_locked_slots_times;


-- ===========================================
-- 6. CLEAN UP SEQUENCES (if tables were dropped)
-- ===========================================

-- Sequences for dropped tables will be automatically dropped with CASCADE
-- No manual cleanup needed


-- ===========================================
-- 7. REVOKE PERMISSIONS ON DROPPED TABLES
-- ===========================================

-- Permissions are automatically cleaned up when tables are dropped with CASCADE
-- No manual cleanup needed


COMMIT;
