-- Purge FishDiscoveries rows so the bot can re-populate using per-fish
-- name matching only.
--
-- Previous sync logic (nexus-bot/fish-discoveries.js) also matched against
-- the family oil name (`{Species.Name} Fish Oil`) and marked every Fish in
-- that species as discovered when the oil was first looted. That leaked
-- undiscovered fish through the public listings. The bot now matches only
-- on Fish.Name, so the stale oil-derived rows must be removed here to let
-- the next sync repopulate the table cleanly.

BEGIN;

TRUNCATE TABLE "FishDiscoveries";

COMMIT;
