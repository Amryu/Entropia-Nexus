-- Migration: Replace media_youtube_id with generic media_video_url
-- Supports multiple video platforms (YouTube, Twitch Clips, Vimeo).
-- Stores the full URL instead of a platform-specific ID.

BEGIN;

-- Add generic video URL column
ALTER TABLE ingested_globals ADD COLUMN media_video_url TEXT;

-- Migrate existing YouTube IDs to full URLs
UPDATE ingested_globals
SET media_video_url = 'https://www.youtube.com/watch?v=' || media_youtube_id
WHERE media_youtube_id IS NOT NULL;

-- Drop old YouTube-specific column
ALTER TABLE ingested_globals DROP COLUMN media_youtube_id;

-- Update XOR constraint: image XOR video, not both
ALTER TABLE ingested_globals DROP CONSTRAINT IF EXISTS chk_globals_media_exclusive;
ALTER TABLE ingested_globals ADD CONSTRAINT chk_globals_media_exclusive
  CHECK (NOT (media_image_key IS NOT NULL AND media_video_url IS NOT NULL));

-- Recreate has-media index
DROP INDEX IF EXISTS idx_ingested_globals_has_media;
CREATE INDEX idx_ingested_globals_has_media
  ON ingested_globals (id) WHERE media_image_key IS NOT NULL OR media_video_url IS NOT NULL;

COMMIT;
