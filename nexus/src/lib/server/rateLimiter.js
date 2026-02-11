/**
 * Simple in-memory rate limiter for API endpoints.
 * Tracks requests per user/IP within sliding time windows.
 */

// Store: Map<key, { count: number, windowStart: number, windowMs: number }>
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
    // Remove entries whose window has expired (default 1 hour for legacy entries)
    const expiry = data.windowMs || 60 * 60 * 1000;
    if (now - data.windowStart > expiry) {
      keysToDelete.push(key);
    }
  }

  for (const key of keysToDelete) {
    requestCounts.delete(key);
  }
}

/**
 * Check if a request should be rate limited (increments counter)
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
    requestCounts.set(key, { count: 1, windowStart: now, windowMs });
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
 * Check rate limit without incrementing (peek).
 * Use this when you want to check availability before committing to the action.
 * @param {string} key
 * @param {number} maxRequests
 * @param {number} windowMs
 * @returns {{ allowed: boolean, remaining: number, resetIn: number }}
 */
export function checkRateLimitPeek(key, maxRequests, windowMs) {
  const now = Date.now();
  const data = requestCounts.get(key);

  if (!data || now - data.windowStart >= windowMs) {
    return { allowed: true, remaining: maxRequests, resetIn: windowMs };
  }

  const resetIn = windowMs - (now - data.windowStart);
  if (data.count >= maxRequests) {
    return { allowed: false, remaining: 0, resetIn };
  }

  return { allowed: true, remaining: maxRequests - data.count, resetIn };
}

/**
 * Increment a rate limit counter without checking (commit after success).
 * Creates a new window if the key doesn't exist or window expired.
 * @param {string} key
 * @param {number} windowMs
 */
export function incrementRateLimit(key, windowMs) {
  const now = Date.now();
  const data = requestCounts.get(key);

  if (!data || now - data.windowStart >= windowMs) {
    requestCounts.set(key, { count: 1, windowStart: now, windowMs });
  } else {
    data.count++;
  }
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
  checkRateLimitPeek,
  incrementRateLimit,
  getRateLimitHeaders,
  checkConcurrentUploads,
  startUpload,
  endUpload
};
