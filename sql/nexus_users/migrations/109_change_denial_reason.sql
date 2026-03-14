-- Add optional denial reason to changes table
ALTER TABLE changes ADD COLUMN IF NOT EXISTS denial_reason TEXT;
