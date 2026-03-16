-- Forum Trading Indexer
-- Indexes threads from Planet Calypso Forum Selling/Buying sections
-- for item name matching and display across the site.

BEGIN;

CREATE TABLE forum_threads (
  id               SERIAL PRIMARY KEY,
  thread_id        INTEGER NOT NULL UNIQUE,
  forum_type       TEXT NOT NULL,
  title            TEXT NOT NULL,
  author           TEXT NOT NULL,
  url              TEXT NOT NULL,
  content_snippet  TEXT,
  comment_count    INTEGER NOT NULL DEFAULT 0,
  is_closed        BOOLEAN NOT NULL DEFAULT false,
  created_at       TIMESTAMPTZ NOT NULL,
  last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  feed_position    SMALLINT,
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_forum_threads_type ON forum_threads(forum_type);
CREATE INDEX idx_forum_threads_activity ON forum_threads(last_activity_at DESC);
CREATE INDEX idx_forum_threads_active ON forum_threads(is_closed) WHERE is_closed = false;

CREATE TABLE forum_thread_items (
  id           SERIAL PRIMARY KEY,
  thread_id    INTEGER NOT NULL REFERENCES forum_threads(id) ON DELETE CASCADE,
  item_id      INTEGER NOT NULL,
  item_name    TEXT NOT NULL,
  match_source TEXT NOT NULL DEFAULT 'title',
  UNIQUE(thread_id, item_id)
);

CREATE INDEX idx_fti_item ON forum_thread_items(item_id);
CREATE INDEX idx_fti_thread ON forum_thread_items(thread_id);

GRANT ALL ON TABLE forum_threads, forum_thread_items TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE forum_threads_id_seq, forum_thread_items_id_seq TO nexus_users;

COMMIT;
