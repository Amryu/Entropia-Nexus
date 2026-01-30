-- Add item_name column to service_equipment table
-- This stores the item name for display purposes (denormalized for performance)

ALTER TABLE service_equipment
ADD COLUMN IF NOT EXISTS item_name TEXT;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_service_equipment_item_name ON service_equipment(item_name);

-- Add comment
COMMENT ON COLUMN service_equipment.item_name IS 'Display name of the item (denormalized for performance)';
