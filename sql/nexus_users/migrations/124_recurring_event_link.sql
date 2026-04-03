-- Link community-submitted events to recurring game events by name.
-- Cross-DB FK not possible in PostgreSQL; name is unique and stable.
ALTER TABLE events ADD COLUMN recurring_event_name TEXT;
