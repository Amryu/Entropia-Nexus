-- Migration: Role-based permission system and guide content tables
-- Replaces the administrator boolean with a flexible role/grant system
-- Adds hierarchical guide content (categories > chapters > lessons > paragraphs)
-- Database: nexus-users

BEGIN;

-- =============================================
-- ROLE & GRANT SYSTEM
-- =============================================

-- Grant definitions: all available permissions in the system
CREATE TABLE IF NOT EXISTS grants (
  id serial PRIMARY KEY,
  key text NOT NULL UNIQUE,
  description text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Roles with optional parent for inheritance
CREATE TABLE IF NOT EXISTS roles (
  id serial PRIMARY KEY,
  name text NOT NULL UNIQUE,
  description text,
  parent_id integer REFERENCES roles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_roles_parent_id ON roles(parent_id);

-- Role-grant assignments (granted = false means explicitly denied at this role level)
CREATE TABLE IF NOT EXISTS role_grants (
  role_id integer NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  grant_id integer NOT NULL REFERENCES grants(id) ON DELETE CASCADE,
  granted boolean NOT NULL DEFAULT true,
  PRIMARY KEY (role_id, grant_id)
);

CREATE INDEX IF NOT EXISTS idx_role_grants_role_id ON role_grants(role_id);

-- User-role assignments (many-to-many)
CREATE TABLE IF NOT EXISTS user_roles (
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role_id integer NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  assigned_at timestamptz NOT NULL DEFAULT now(),
  assigned_by bigint REFERENCES users(id) ON DELETE SET NULL,
  PRIMARY KEY (user_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);

-- User-level grant overrides (highest priority in resolution)
CREATE TABLE IF NOT EXISTS user_grants (
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  grant_id integer NOT NULL REFERENCES grants(id) ON DELETE CASCADE,
  granted boolean NOT NULL DEFAULT true,
  assigned_at timestamptz NOT NULL DEFAULT now(),
  assigned_by bigint REFERENCES users(id) ON DELETE SET NULL,
  PRIMARY KEY (user_id, grant_id)
);

CREATE INDEX IF NOT EXISTS idx_user_grants_user_id ON user_grants(user_id);

-- Seed grant definitions
INSERT INTO grants (key, description) VALUES
  ('admin.panel', 'Access the admin dashboard'),
  ('admin.users', 'Lock, ban, and manage users'),
  ('admin.impersonate', 'Impersonate other users'),
  ('wiki.edit', 'Edit wiki entities (create/update changes)'),
  ('wiki.approve', 'Approve or deny wiki change requests'),
  ('guide.create', 'Create new guide content (categories, chapters, lessons, paragraphs)'),
  ('guide.edit', 'Edit existing guide content'),
  ('guide.delete', 'Delete guide content')
ON CONFLICT (key) DO NOTHING;

-- Create the admin role (all grants)
INSERT INTO roles (name, description)
VALUES ('admin', 'Full administrator access')
ON CONFLICT (name) DO NOTHING;

INSERT INTO role_grants (role_id, grant_id, granted)
SELECT r.id, g.id, true
FROM roles r, grants g
WHERE r.name = 'admin'
ON CONFLICT DO NOTHING;

-- Create the editor role (wiki editing + approval)
INSERT INTO roles (name, description)
VALUES ('editor', 'Can edit wiki content and approve changes')
ON CONFLICT (name) DO NOTHING;

INSERT INTO role_grants (role_id, grant_id, granted)
SELECT r.id, g.id, true
FROM roles r, grants g
WHERE r.name = 'editor' AND g.key IN ('wiki.edit', 'wiki.approve')
ON CONFLICT DO NOTHING;

-- Create the guide_author role (guide creation + editing)
INSERT INTO roles (name, description)
VALUES ('guide_author', 'Can create and edit guide content')
ON CONFLICT (name) DO NOTHING;

INSERT INTO role_grants (role_id, grant_id, granted)
SELECT r.id, g.id, true
FROM roles r, grants g
WHERE r.name = 'guide_author' AND g.key IN ('guide.create', 'guide.edit')
ON CONFLICT DO NOTHING;

-- Migrate existing administrators to the admin role
INSERT INTO user_roles (user_id, role_id, assigned_at)
SELECT u.id, r.id, now()
FROM users u, roles r
WHERE u.administrator = true AND r.name = 'admin'
ON CONFLICT DO NOTHING;

-- =============================================
-- GUIDE CONTENT TABLES
-- =============================================

-- Guide categories (top-level grouping)
CREATE TABLE IF NOT EXISTS guide_categories (
  id serial PRIMARY KEY,
  title text NOT NULL,
  description text,
  icon text,
  sort_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by bigint REFERENCES users(id) ON DELETE SET NULL
);

-- Guide chapters (within a category)
CREATE TABLE IF NOT EXISTS guide_chapters (
  id serial PRIMARY KEY,
  category_id integer NOT NULL REFERENCES guide_categories(id) ON DELETE CASCADE,
  title text NOT NULL,
  description text,
  sort_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by bigint REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_guide_chapters_category ON guide_chapters(category_id);

-- Guide lessons (within a chapter)
CREATE TABLE IF NOT EXISTS guide_lessons (
  id serial PRIMARY KEY,
  chapter_id integer NOT NULL REFERENCES guide_chapters(id) ON DELETE CASCADE,
  title text NOT NULL,
  slug text NOT NULL UNIQUE,
  sort_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by bigint REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_guide_lessons_chapter ON guide_lessons(chapter_id);

-- Guide paragraphs (rich text content within a lesson)
CREATE TABLE IF NOT EXISTS guide_paragraphs (
  id serial PRIMARY KEY,
  lesson_id integer NOT NULL REFERENCES guide_lessons(id) ON DELETE CASCADE,
  content_html text NOT NULL DEFAULT '',
  sort_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by bigint REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_guide_paragraphs_lesson ON guide_paragraphs(lesson_id);

-- =============================================
-- PERMISSIONS
-- =============================================

-- Role/grant tables: full CRUD for app
GRANT SELECT, INSERT, UPDATE, DELETE ON grants TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON roles TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON role_grants TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON user_roles TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON user_grants TO "nexus-users";

GRANT USAGE, SELECT ON SEQUENCE grants_id_seq TO "nexus-users";
GRANT USAGE, SELECT ON SEQUENCE roles_id_seq TO "nexus-users";

-- Guide tables: full CRUD for app
GRANT SELECT, INSERT, UPDATE, DELETE ON guide_categories TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON guide_chapters TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON guide_lessons TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON guide_paragraphs TO "nexus-users";

GRANT USAGE, SELECT ON SEQUENCE guide_categories_id_seq TO "nexus-users";
GRANT USAGE, SELECT ON SEQUENCE guide_chapters_id_seq TO "nexus-users";
GRANT USAGE, SELECT ON SEQUENCE guide_lessons_id_seq TO "nexus-users";
GRANT USAGE, SELECT ON SEQUENCE guide_paragraphs_id_seq TO "nexus-users";

COMMIT;
