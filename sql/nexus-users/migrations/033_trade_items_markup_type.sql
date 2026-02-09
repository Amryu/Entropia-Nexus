-- Migration: Add markup_type to trade_request_items
-- Stores whether the price is percentage-based or absolute (+PED)
-- so the Discord bot can format it correctly in trade threads.

ALTER TABLE trade_request_items
  ADD COLUMN markup_type TEXT NOT NULL DEFAULT 'percent';
