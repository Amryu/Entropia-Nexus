-- Migration 057: Add optional YouTube playlist filter for content creators
-- When set, only videos from this playlist are shown and trigger notifications.

ALTER TABLE content_creators ADD COLUMN youtube_playlist_id text;
