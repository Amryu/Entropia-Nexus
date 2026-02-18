-- Add source tracking for external news (Steam)
ALTER TABLE announcements
  ADD COLUMN source TEXT NOT NULL DEFAULT 'nexus',
  ADD COLUMN source_id TEXT;

-- Allow null author for auto-imported news
ALTER TABLE announcements ALTER COLUMN author_id DROP NOT NULL;

-- Prevent duplicate imports
CREATE UNIQUE INDEX idx_announcements_source_id ON announcements(source, source_id) WHERE source_id IS NOT NULL;
