-- Clean up bad price data for Mayhem Token (item_id 1002803)
-- A sell order with markup 100 was incorrectly recorded, inflating inventory values
DELETE FROM ONLY exchange_price_snapshots WHERE item_id = 1002803;
DELETE FROM ONLY exchange_price_summaries WHERE item_id = 1002803;
