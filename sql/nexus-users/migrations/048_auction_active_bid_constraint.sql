-- Migration: Add partial unique index to prevent multiple active bids per auction.
-- The application already marks previous active bids as 'outbid' before inserting,
-- but this enforces the invariant at the database level as a safety net.

CREATE UNIQUE INDEX idx_auction_bids_one_active
  ON auction_bids (auction_id)
  WHERE status = 'active';
