-- Allow multiple offers per non-fungible item (up to 5 enforced in application code)
-- Drop the strict 1-per-item unique constraint
DROP INDEX IF EXISTS trade_offers_user_item_type_active_uq;
