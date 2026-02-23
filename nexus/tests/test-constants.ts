/**
 * Global timeout constants for E2E tests
 *
 * Use these constants instead of magic numbers to ensure consistent timing across tests.
 *
 * Usage:
 * - TIMEOUT_INSTANT: 500ms - Client-side operations with no network involvement
 *   (e.g., client-side search/filtering, dialog opening/closing, CSS transitions)
 *
 * - TIMEOUT_SHORT: 1000ms - Tasks requiring some client-side computation
 *   (e.g., rendering complex UI, sorting data, local state updates)
 *
 * - TIMEOUT_MEDIUM: 3000ms - API calls and site loading operations
 *   (e.g., page navigation, data fetching, form submission)
 *
 * - TIMEOUT_LONG: 10000ms - Complex operations or initial page loads
 *   (e.g., initial navigation with authentication, large data loads, slow APIs)
 */

export const TIMEOUT_INSTANT = 500;   // Client-side operations only
export const TIMEOUT_SHORT = 1000;    // Client-side computation
export const TIMEOUT_MEDIUM = 3000;   // API/network operations
export const TIMEOUT_LONG = 10000;    // Complex/slow operations
export const TIMEOUT_CACHE = 60000;   // Exchange cache build on first request
