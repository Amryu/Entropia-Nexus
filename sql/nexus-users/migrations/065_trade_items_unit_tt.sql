-- Add unit_tt to trade_request_items for TT/cost display in Discord threads.
-- Stores per-unit TT value at trade creation time so the bot can show
-- total TT and total cost without cross-database lookups.
-- NULL for existing rows — bot omits TT/cost gracefully.

ALTER TABLE trade_request_items ADD COLUMN unit_tt NUMERIC DEFAULT NULL;
