/**
 * Shared auction utility functions.
 * Used by both client-side pages and server-side API endpoints.
 */

// Neat value steps for bid increments (in PED)
const NEAT_VALUES = [
  0.01, 0.02, 0.05,
  0.10, 0.20, 0.50,
  1, 2, 5,
  10, 20, 50,
  100, 200, 500,
  1000
];

/**
 * Get the minimum bid increment for a given current bid.
 * Calculated as 2% of current bid, rounded up to nearest neat value.
 * Minimum 1 PEC (0.01 PED).
 * @param {number} currentBid - Current highest bid in PED
 * @returns {number} Minimum increment in PED
 */
export function getMinIncrement(currentBid) {
  const raw = currentBid * 0.02;
  if (raw <= 0.01) return 0.01;
  return NEAT_VALUES.find(v => v >= raw) || NEAT_VALUES[NEAT_VALUES.length - 1];
}

/**
 * Get the minimum next bid amount for an auction.
 * @param {number} currentBid - Current highest bid (or starting_bid if no bids)
 * @param {boolean} hasBids - Whether the auction has any bids
 * @returns {number} Minimum next bid in PED
 */
export function getMinNextBid(currentBid, hasBids) {
  if (!hasBids) return currentBid; // First bid must meet starting bid
  return currentBid + getMinIncrement(currentBid);
}

/**
 * Calculate the auction fee for a given sale amount.
 * Tiered bracket system:
 * - First 100 PED: free
 * - 100-1000 PED: 2%
 * - Above 1000 PED: 1%
 * @param {number} amount - Sale amount in PED
 * @returns {number} Fee in PED (2 decimal places)
 */
export function calculateAuctionFee(amount) {
  if (amount <= 0) return 0;
  if (amount <= 100) return 0;
  if (amount <= 1000) {
    return Math.round((amount - 100) * 0.02 * 100) / 100;
  }
  // 900 * 0.02 = 18 PED for the 100-1000 bracket
  return Math.round((18 + (amount - 1000) * 0.01) * 100) / 100;
}

/**
 * Check if an auction is "Buyout Only" (no bidding, just buy now).
 * This is the case when buyout_price equals starting_bid.
 * @param {{ starting_bid: number, buyout_price: number|null }} auction
 * @returns {boolean}
 */
export function isBuyoutOnly(auction) {
  return auction.buyout_price != null &&
    Number(auction.buyout_price) === Number(auction.starting_bid);
}

/**
 * Get maximum auction duration in days based on auction type.
 * Buyout-only auctions can last up to 365 days.
 * Normal auctions with bidding are capped at 30 days.
 * @param {{ starting_bid: number, buyout_price: number|null }} auction
 * @returns {number} Maximum duration in days
 */
export function getMaxDuration(auction) {
  return isBuyoutOnly(auction) ? 365 : 30;
}

/** Anti-sniping: extension window in milliseconds (5 minutes) */
export const ANTI_SNIPE_WINDOW_MS = 5 * 60 * 1000;

/** Anti-sniping: extension amount in milliseconds (5 minutes) */
export const ANTI_SNIPE_EXTENSION_MS = 5 * 60 * 1000;

/** Anti-sniping: max total extension from original end time in ms (30 minutes) */
export const ANTI_SNIPE_MAX_EXTENSION_MS = 30 * 60 * 1000;

/** Auction statuses that are considered "active" for display */
export const ACTIVE_STATUSES = ['active', 'frozen'];

/** Auction statuses that are considered "completed" */
export const COMPLETED_STATUSES = ['ended', 'settled', 'cancelled'];

/**
 * Format time remaining as human-readable string.
 * @param {Date|string} endsAt - Auction end time
 * @returns {{ days: number, hours: number, minutes: number, seconds: number, total: number, expired: boolean }}
 */
export function getTimeRemaining(endsAt) {
  const end = new Date(endsAt).getTime();
  const now = Date.now();
  const total = end - now;

  if (total <= 0) {
    return { days: 0, hours: 0, minutes: 0, seconds: 0, total: 0, expired: true };
  }

  return {
    days: Math.floor(total / (1000 * 60 * 60 * 24)),
    hours: Math.floor((total / (1000 * 60 * 60)) % 24),
    minutes: Math.floor((total / (1000 * 60)) % 60),
    seconds: Math.floor((total / 1000) % 60),
    total,
    expired: false
  };
}
