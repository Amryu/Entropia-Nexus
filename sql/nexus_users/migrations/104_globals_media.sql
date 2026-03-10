-- Migration: Add media support to globals (screenshot uploads, YouTube links)
-- Players can attach screenshots or YouTube videos to confirmed globals.
-- Monthly upload budget: 100 screenshots, 30 YouTube links per user.

BEGIN;

-- Media columns on ingested_globals
ALTER TABLE ingested_globals ADD COLUMN media_image_key text;
ALTER TABLE ingested_globals ADD COLUMN media_youtube_id text;
ALTER TABLE ingested_globals ADD COLUMN media_uploaded_by bigint REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE ingested_globals ADD COLUMN media_uploaded_at timestamptz;

-- Only one media type per global (image XOR youtube, not both)
ALTER TABLE ingested_globals ADD CONSTRAINT chk_globals_media_exclusive
  CHECK (NOT (media_image_key IS NOT NULL AND media_youtube_id IS NOT NULL));

-- Fast lookup for globals that have media attached
CREATE INDEX idx_ingested_globals_has_media
  ON ingested_globals (id) WHERE media_image_key IS NOT NULL OR media_youtube_id IS NOT NULL;

-- Monthly budget counting (user uploads within current month)
CREATE INDEX idx_ingested_globals_media_budget
  ON ingested_globals (media_uploaded_by, media_uploaded_at)
  WHERE media_uploaded_by IS NOT NULL;

COMMIT;
