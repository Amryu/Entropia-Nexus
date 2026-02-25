-- Migration: Landing page features — Announcements, Events, Content Creators
-- Announcements: admin-created news posts displayed on the landing page
-- Events: community-submitted, admin-approved events calendar
-- Content Creators: admin-whitelisted YouTube/Twitch/Kick channels with cached API data

-- ===========================================
-- ENUMS
-- ===========================================

CREATE TYPE event_state AS ENUM ('pending', 'approved', 'denied');
CREATE TYPE event_type AS ENUM ('official', 'player_run');
CREATE TYPE creator_platform AS ENUM ('youtube', 'twitch', 'kick');

-- ===========================================
-- TABLES
-- ===========================================

-- Nexus announcements (admin-created news posts)
CREATE TABLE announcements (
  id            SERIAL PRIMARY KEY,
  title         TEXT NOT NULL,
  summary       TEXT,
  link          TEXT,
  image_url     TEXT,
  pinned        BOOLEAN NOT NULL DEFAULT false,
  published     BOOLEAN NOT NULL DEFAULT false,
  author_id     BIGINT NOT NULL REFERENCES users(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Community events (submitted by verified users, approved by admins)
CREATE TABLE events (
  id            SERIAL PRIMARY KEY,
  title         TEXT NOT NULL,
  description   TEXT,
  start_date    TIMESTAMPTZ NOT NULL,
  end_date      TIMESTAMPTZ,
  location      TEXT,
  type          event_type NOT NULL DEFAULT 'player_run',
  link          TEXT,
  image_url     TEXT,
  submitted_by  BIGINT NOT NULL REFERENCES users(id),
  approved_by   BIGINT REFERENCES users(id),
  state         event_state NOT NULL DEFAULT 'pending',
  admin_note    TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Content creators (admin-whitelisted, API-enriched)
CREATE TABLE content_creators (
  id            SERIAL PRIMARY KEY,
  name          TEXT NOT NULL,
  platform      creator_platform NOT NULL,
  channel_id    TEXT,
  channel_url   TEXT NOT NULL,
  description   TEXT,
  avatar_url    TEXT,
  active        BOOLEAN NOT NULL DEFAULT true,
  display_order INTEGER NOT NULL DEFAULT 0,
  cached_data   JSONB,
  cached_at     TIMESTAMPTZ,
  added_by      BIGINT NOT NULL REFERENCES users(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ===========================================
-- INDEXES
-- ===========================================

-- Announcements: landing page query (published, newest first)
CREATE INDEX idx_announcements_published ON announcements(created_at DESC)
  WHERE published = true;
CREATE INDEX idx_announcements_pinned ON announcements(pinned)
  WHERE published = true AND pinned = true;

-- Events: upcoming approved events
CREATE INDEX idx_events_upcoming ON events(start_date ASC)
  WHERE state = 'approved';
CREATE INDEX idx_events_state ON events(state);
CREATE INDEX idx_events_submitted_by ON events(submitted_by);

-- Content creators: active list ordered by display_order
CREATE INDEX idx_creators_active ON content_creators(display_order ASC)
  WHERE active = true;

-- ===========================================
-- PERMISSIONS
-- ===========================================

-- announcements
GRANT SELECT, INSERT, UPDATE, DELETE ON announcements TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON announcements TO "nexus-bot";
GRANT ALL ON announcements TO postgres;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE announcements_id_seq TO nexus_users;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE announcements_id_seq TO "nexus-bot";

-- events
GRANT SELECT, INSERT, UPDATE, DELETE ON events TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON events TO "nexus-bot";
GRANT ALL ON events TO postgres;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE events_id_seq TO nexus_users;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE events_id_seq TO "nexus-bot";

-- content_creators
GRANT SELECT, INSERT, UPDATE, DELETE ON content_creators TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON content_creators TO "nexus-bot";
GRANT ALL ON content_creators TO postgres;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE content_creators_id_seq TO nexus_users;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE content_creators_id_seq TO "nexus-bot";
