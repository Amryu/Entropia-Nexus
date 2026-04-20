-- FishDiscoveries: fish that have had a first-time discovery global.
--
-- Fish and their linked materials (oil + size) are hidden from all public
-- listings until a discovery global is observed. Globals live in the
-- nexus_users DB (ingested_globals), but filtering needs to happen against
-- entities here in nexus, so nexus-bot periodically denormalizes the set of
-- discovered Fish into this local table. No FK to the globals row — we only
-- keep enough to show "discovered by X at time Y" if we ever want to.

BEGIN;

CREATE TABLE "FishDiscoveries" (
    "FishId"          integer PRIMARY KEY REFERENCES "Fish"("Id") ON DELETE CASCADE,
    "DiscoveredAt"    timestamp,
    "DiscovererName"  text
);

GRANT SELECT ON "FishDiscoveries" TO nexus;
GRANT INSERT, UPDATE, DELETE ON "FishDiscoveries" TO nexus_bot;

-- View: Items.Id values that belong to an undiscovered fish (fish oil +
-- every fish-size material). Used by /materials, /refiningrecipes, /search
-- to exclude those rows. Fish.FishOilItemId and FishSizes.ItemId are already
-- in the Items-view numbering (Materials.Id + 1000000), so no offset math
-- here.
--
-- A material is hidden only when *every* Fish row referencing it is
-- undiscovered. If the same material is shared with a discovered fish, the
-- material must remain visible; GROUP BY + bool_or enforces that.
CREATE OR REPLACE VIEW "UndiscoveredFishItemIds" AS
  SELECT "Id" FROM (
    SELECT f."FishOilItemId" AS "Id",
           (fd."FishId" IS NOT NULL) AS discovered
      FROM ONLY "Fish" f
      LEFT JOIN "FishDiscoveries" fd ON fd."FishId" = f."Id"
      WHERE f."FishOilItemId" IS NOT NULL
    UNION ALL
    SELECT fs."ItemId" AS "Id",
           (fd."FishId" IS NOT NULL) AS discovered
      FROM ONLY "FishSizes" fs
      JOIN ONLY "Fish" f ON f."Id" = fs."FishId"
      LEFT JOIN "FishDiscoveries" fd ON fd."FishId" = f."Id"
      WHERE fs."ItemId" IS NOT NULL
  ) x
  GROUP BY "Id"
  HAVING bool_or(discovered) = FALSE;

GRANT SELECT ON "UndiscoveredFishItemIds" TO nexus;

-- Cache-invalidation trigger so /fishes, /materials, /refiningrecipes,
-- /search all rebuild when a new discovery is synced in.
CREATE TRIGGER zz_track_change AFTER INSERT OR UPDATE OR DELETE ON "FishDiscoveries"
  FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();

COMMIT;
