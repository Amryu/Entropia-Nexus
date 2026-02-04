CREATE TABLE IF NOT EXISTS public.societies (
  id bigserial PRIMARY KEY,
  name text NOT NULL,
  abbreviation text,
  description text,
  discord_code text,
  leader_id bigint NOT NULL
);

CREATE TABLE IF NOT EXISTS public.society_join_requests (
  id bigserial PRIMARY KEY,
  user_id bigint NOT NULL,
  society_id bigint NOT NULL,
  status text NOT NULL DEFAULT 'Pending',
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'society_join_requests_status_check'
      AND conrelid = 'public.society_join_requests'::regclass
  ) THEN
    ALTER TABLE public.society_join_requests
      ADD CONSTRAINT society_join_requests_status_check
      CHECK (status IN ('Pending', 'Approved', 'Rejected'));
  END IF;
END
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_profile_tab') THEN
    CREATE TYPE public.user_profile_tab AS ENUM ('General', 'Avatar', 'Services', 'Shops', 'Offers');
  END IF;
END
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notification_type') THEN
    CREATE TYPE public.notification_type AS ENUM ('Society');
  END IF;
END
$$;

ALTER TABLE public.societies
  ADD COLUMN IF NOT EXISTS discord_code text;

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS society_id bigint,
  ADD COLUMN IF NOT EXISTS biography_html text,
  ADD COLUMN IF NOT EXISTS default_profile_tab public.user_profile_tab DEFAULT 'General',
  ADD COLUMN IF NOT EXISTS showcase_loadout_code text;

CREATE TABLE IF NOT EXISTS public.notifications (
  id bigserial PRIMARY KEY,
  user_id bigint NOT NULL,
  type public.notification_type NOT NULL,
  message text NOT NULL,
  date timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  read boolean DEFAULT false
);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.societies TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.society_join_requests TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.notifications TO "nexus-users";

GRANT USAGE, SELECT ON SEQUENCE public.societies_id_seq TO "nexus-users";
GRANT USAGE, SELECT ON SEQUENCE public.society_join_requests_id_seq TO "nexus-users";
GRANT USAGE, SELECT ON SEQUENCE public.notifications_id_seq TO "nexus-users";
