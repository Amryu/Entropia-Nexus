-- Allow the same fungible item to exist on multiple planets/containers.
-- The old constraint only used (user_id, item_id), which fails when the same
-- item is stored on different planets (e.g., Sweat on Calypso + Arkadia).
-- COALESCE(container, '') treats NULL container as empty string for uniqueness.

DROP INDEX IF EXISTS user_items_fungible_uq;
CREATE UNIQUE INDEX user_items_fungible_uq
  ON user_items (user_id, item_id, COALESCE(container, ''))
  WHERE instance_key IS NULL;
