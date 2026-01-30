/**
 * Simple in-memory rate limiter for API endpoints.
 * Tracks requests per user/IP within sliding time windows.
 */

// Store: Map<key, { count: number, windowStart: number }>
const requestCounts = new Map();

// Cleanup old entries periodically (every 5 minutes)
const CLEANUP_INTERVAL = 5 * 60 * 1000;
let lastCleanup = Date.now();

/**
 * Clean up expired rate limit entries
 * @param {number} now - Current timestamp
 */
function cleanup(now) {
  if (now - lastCleanup < CLEANUP_INTERVAL) return;

  lastCleanup = now;
  const keysToDelete = [];

  for (const [key, data] of requestCounts.entries()) {
    // Remove entries older than 1 hour
    if (now - data.windowStart > 60 * 60 * 1000) {
      keysToDelete.push(key);
    }
  }

  for (const key of keysToDelete) {
    requestCounts.delete(key);
  }
}

/**
 * Check if a request should be rate limited
 * @param {string} key - Unique identifier (e.g., 'upload:userId' or 'upload:ip')
 * @param {number} maxRequests - Maximum requests allowed in the window
 * @param {number} windowMs - Time window in milliseconds
 * @returns {{ allowed: boolean, remaining: number, resetIn: number }}
 */
export function checkRateLimit(key, maxRequests, windowMs) {
  const now = Date.now();
  cleanup(now);

  const data = requestCounts.get(key);

  if (!data || now - data.windowStart >= windowMs) {
    // New window
    requestCounts.set(key, { count: 1, windowStart: now });
    return {
      allowed: true,
      remaining: maxRequests - 1,
      resetIn: windowMs
    };
  }

  if (data.count >= maxRequests) {
    // Rate limited
    const resetIn = windowMs - (now - data.windowStart);
    return {
      allowed: false,
      remaining: 0,
      resetIn
    };
  }

  // Increment counter
  data.count++;
  const resetIn = windowMs - (now - data.windowStart);
  return {
    allowed: true,
    remaining: maxRequests - data.count,
    resetIn
  };
}

/**
 * Get rate limit headers for response
 * @param {number} limit - Max requests
 * @param {number} remaining - Remaining requests
 * @param {number} resetIn - Reset time in ms
 * @returns {object}
 */
export function getRateLimitHeaders(limit, remaining, resetIn) {
  return {
    'X-RateLimit-Limit': String(limit),
    'X-RateLimit-Remaining': String(Math.max(0, remaining)),
    'X-RateLimit-Reset': String(Math.ceil(Date.now() / 1000 + resetIn / 1000))
  };
}

// Concurrent upload tracking per user
const activeUploads = new Map();

/**
 * Check if user has too many concurrent uploads
 * @param {string} userId
 * @param {number} maxConcurrent
 * @returns {boolean} - true if allowed
 */
export function checkConcurrentUploads(userId, maxConcurrent = 3) {
  const count = activeUploads.get(userId) || 0;
  return count < maxConcurrent;
}

/**
 * Increment active upload count for user
 * @param {string} userId
 */
export function startUpload(userId) {
  const count = activeUploads.get(userId) || 0;
  activeUploads.set(userId, count + 1);
}

/**
 * Decrement active upload count for user
 * @param {string} userId
 */
export function endUpload(userId) {
  const count = activeUploads.get(userId) || 0;
  if (count <= 1) {
    activeUploads.delete(userId);
  } else {
    activeUploads.set(userId, count - 1);
  }
}

export default {
  checkRateLimit,
  getRateLimitHeaders,
  checkConcurrentUploads,
  startUpload,
  endUpload
};
