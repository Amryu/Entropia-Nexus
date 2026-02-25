-- ===========================================
-- Migration: Add deleted_at column and aborted status
-- ===========================================

-- Add deleted_at column to services table for soft delete
ALTER TABLE services ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- Add index for deleted_at to efficiently filter out deleted services
CREATE INDEX IF NOT EXISTS idx_services_deleted_at ON services(deleted_at) WHERE deleted_at IS NULL;

-- Add 'aborted' status to request_status enum
-- Note: PostgreSQL requires adding enum values explicitly
ALTER TYPE request_status ADD VALUE IF NOT EXISTS 'aborted' AFTER 'cancelled';

-- Comment for documentation
COMMENT ON COLUMN services.deleted_at IS 'Soft delete timestamp. NULL = active, NOT NULL = deleted. Separate from is_active which indicates paused/inactive.';
