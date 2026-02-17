-- Society Discord links are private (members-only) by default.
-- Leaders can toggle this to make the invite link visible to everyone.
ALTER TABLE societies ADD COLUMN IF NOT EXISTS discord_public boolean NOT NULL DEFAULT false;
