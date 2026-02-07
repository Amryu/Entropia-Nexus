-- Migration: Drop icon column from guide categories (banners use entity image system)
-- Database: nexus-users

BEGIN;

ALTER TABLE guide_categories DROP COLUMN IF EXISTS icon;

COMMIT;
