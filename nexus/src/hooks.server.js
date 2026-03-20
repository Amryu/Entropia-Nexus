//@ts-nocheck
import { resolveShortRedirect } from '$lib/server/short-url.js';

let dbGetSession, getUserFromSession, updateSession, upsertUser, getUserInfo, handleRefresh, getUserById, getUserFullDetails, resolveUserGrants;
let validateAccessToken, getGrantKeysForScopes, cleanupExpiredTokens;

if (import.meta.env.SSR) {
  const db = await import('$lib/server/db');
  dbGetSession = db.getSession;
  getUserFromSession = db.getUserFromSession;
  updateSession = db.updateSession;
  upsertUser = db.upsertUser;
  getUserById = db.getUserById;
  getUserFullDetails = db.getUserFullDetails;

  const grants = await import('$lib/server/grants');
  resolveUserGrants = grants.resolveUserGrants;
  grants.startGrantsPoller();

  const discord = await import('$lib/server/discord');
  getUserInfo = discord.getUserInfo;
  handleRefresh = discord.handleRefresh;

  const oauth = await import('$lib/server/oauth');
  validateAccessToken = oauth.validateAccessToken;
  getGrantKeysForScopes = oauth.getGrantKeysForScopes;
  cleanupExpiredTokens = oauth.cleanupExpiredTokens;

  // Periodically clean up expired OAuth tokens
  const OAUTH_CLEANUP_INTERVAL_MS = 60 * 60_000; // 1 hour
  cleanupExpiredTokens().catch(err => console.error('[oauth] Error cleaning up tokens:', err));
  setInterval(() => {
    cleanupExpiredTokens().catch(err => console.error('[oauth] Error cleaning up tokens:', err));
  }, OAUTH_CLEANUP_INTERVAL_MS).unref();

  // Periodically end expired auctions so they don't depend on API traffic
  const { endExpiredAuctions } = await import('$lib/server/auction.js');
  const AUCTION_EXPIRY_INTERVAL_MS = 60_000; // 1 minute
  endExpiredAuctions().catch(err => console.error('[auction] Error ending expired auctions:', err));
  setInterval(() => {
    endExpiredAuctions().catch(err => console.error('[auction] Error ending expired auctions:', err));
  }, AUCTION_EXPIRY_INTERVAL_MS).unref();

  // Periodically refresh content creator cached data (YouTube, Twitch)
  const { refreshStaleCreators } = await import('$lib/server/creator-enrichment.js');
  const CREATOR_REFRESH_INTERVAL_MS = 3 * 60_000; // 3 minutes
  refreshStaleCreators().catch(err => console.error('[creator-enrichment] Error refreshing creators:', err));
  setInterval(() => {
    refreshStaleCreators().catch(err => console.error('[creator-enrichment] Error refreshing creators:', err));
  }, CREATOR_REFRESH_INTERVAL_MS).unref();

  // Periodically sync Steam news to the announcements table
  const { syncSteamNews } = await import('$lib/server/news-cache.js');
  const STEAM_SYNC_INTERVAL_MS = 30 * 60_000; // 30 minutes
  syncSteamNews().catch(err => console.error('[news-sync] Error syncing Steam news:', err));
  setInterval(() => {
    syncSteamNews().catch(err => console.error('[news-sync] Error syncing Steam news:', err));
  }, STEAM_SYNC_INTERVAL_MS).unref();

  // Periodically index Planet Calypso Forum trading threads
  const { syncForumTrading } = await import('$lib/server/forum-indexer.js');
  const FORUM_SYNC_INTERVAL_MS = 5 * 60_000; // 15 minutes
  syncForumTrading().catch(err => console.error('[forum-indexer] Error syncing forum:', err));
  setInterval(() => {
    syncForumTrading().catch(err => console.error('[forum-indexer] Error syncing forum:', err));
  }, FORUM_SYNC_INTERVAL_MS).unref();

  // Periodically finalize pending market price submissions
  const { maybeRunMarketFinalization } = await import('$lib/server/ingestion.js');
  const MARKET_FINALIZATION_INTERVAL_MS = 5 * 60_000; // 5 minutes
  setInterval(() => {
    maybeRunMarketFinalization();
  }, MARKET_FINALIZATION_INTERVAL_MS).unref();

  // Initialize mob/maturity resolver for global event ingestion (hourly refresh)
  const { initMobResolver } = await import('$lib/server/mobResolver.js');
  initMobResolver().catch(err => console.error('[mobResolver] Error initializing mob resolver:', err));

  // Initialize globals rollup tables first (populates agg tables), then cache (reads from agg tables)
  const { initGlobalsRollups } = await import('$lib/server/globals-rollup.js');
  const { initGlobalsCache } = await import('$lib/server/globals-cache.js');
  initGlobalsRollups()
    .then(() => initGlobalsCache())
    .catch(err => console.error('[globals] Error initializing rollup/cache:', err));

  // Route analytics: page view tracking, GeoIP, bot detection, rollups
  const routeAnalytics = await import('$lib/server/route-analytics.js');
  const routeAnalyticsRollup = await import('$lib/server/route-analytics-rollup.js');
  var _recordVisit = routeAnalytics.recordVisit;
  routeAnalytics.initRouteAnalytics().catch(err => console.error('[route-analytics] Init error:', err));
  routeAnalyticsRollup.initRouteAnalyticsRollups().catch(err => console.error('[route-analytics-rollup] Init error:', err));

  // Error log: captures 4xx/5xx responses with diagnostics
  const errorLog = await import('$lib/server/error-log.js');
  var _recordError = errorLog.recordError;
  var _recordErrorMessage = errorLog.recordErrorMessage;
  errorLog.initErrorLog();
}

const IMPERSONATE_COOKIE = 'nexus_impersonate';
const VIEWPORT_COOKIE = 'nexus_viewport';

// Mobile breakpoint - aligned with global 900px mobile breakpoint (see style.css)
const MOBILE_BREAKPOINT = 900;
const DEFAULT_DESKTOP_WIDTH = 1200;
const DEFAULT_MOBILE_WIDTH = 375;

/**
 * Detect if User-Agent indicates a mobile device
 * @param {string} userAgent
 * @returns {boolean}
 */
function isMobileUserAgent(userAgent) {
  if (!userAgent) return false;
  // Match common mobile device patterns
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile|CriOS/i.test(userAgent);
}

/**
 * Get initial viewport width based on User-Agent and stored cookie
 * @param {Request} request
 * @param {import('@sveltejs/kit').Cookies} cookies
 * @returns {number}
 */
function getInitialViewportWidth(request, cookies) {
  // First, check if we have a stored viewport width from a previous visit
  const storedViewport = cookies.get(VIEWPORT_COOKIE);
  if (storedViewport) {
    const width = parseInt(storedViewport, 10);
    if (!isNaN(width) && width > 0 && width < 10000) {
      return width;
    }
  }

  // Fall back to User-Agent detection
  const userAgent = request.headers.get('user-agent') || '';
  return isMobileUserAgent(userAgent) ? DEFAULT_MOBILE_WIDTH : DEFAULT_DESKTOP_WIDTH;
}

// Session cookie duration: 30 days (refresh will keep it alive)
const SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 days

// Refresh threshold: refresh when less than 2 days remain on the token
// Discord tokens typically last 7 days, so this gives us plenty of margin
const REFRESH_THRESHOLD = 60 * 60 * 24 * 2; // 2 days

// How often to re-resolve grants from DB (in ms).
// Ensures role/grant changes and verification apply within this window.
const GRANTS_REFRESH_INTERVAL = 30_000; // 30 seconds

const sessions = new Map();

export async function handle({ event, resolve }) {
  const shortRedirect = resolveShortRedirect({
    host: event.url.host,
    path: event.url.pathname,
    search: event.url.search
  });
  if (shortRedirect) {
    return new Response(null, {
      status: shortRedirect.status,
      headers: { Location: shortRedirect.location }
    });
  }

  // --- CORS preflight for API paths ---
  if (event.request.method === 'OPTIONS' && event.url.pathname.startsWith('/api/')) {
    return new Response(null, {
      status: 204,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Authorization, Content-Type',
        'Access-Control-Max-Age': '86400'
      }
    });
  }

  // --- OAuth Bearer token authentication ---
  const authHeader = event.request.headers.get('authorization');
  let isOAuthRequest = false;

  if (authHeader?.startsWith('Bearer ') && event.url.pathname.startsWith('/api/')) {
    const rawToken = authHeader.slice(7);
    if (rawToken) {
      try {
        const tokenData = await validateAccessToken(rawToken);
        if (tokenData) {
          // Load user and resolve grants
          const user = await getUserById(tokenData.userId);
          if (user && user.verified && !user.banned) {
            const userGrants = await resolveUserGrants(tokenData.userId);

            // Intersect user grants with scope-allowed grants
            const scopeGrantKeys = await getGrantKeysForScopes(tokenData.scopes);
            const filteredGrants = [];
            for (const grant of userGrants) {
              // Include grants that are required by any active scope,
              // but exclude admin grants (never delegable via OAuth)
              if (grant.startsWith('admin.')) continue;
              if (scopeGrantKeys.has(grant)) {
                filteredGrants.push(grant);
              }
            }

            user.grants = filteredGrants;
            user.administrator = false; // Never admin via OAuth

            const session = { user };
            event.locals.session = session;
            event.locals.isOAuth = true;
            event.locals.oauthScopes = tokenData.scopes;
            event.locals.oauthClientId = tokenData.clientId;
            isOAuthRequest = true;
          }
        }
      } catch (e) {
        console.error('[oauth] Error validating access token:', e);
        // Fall through to cookie auth
      }
    }
  }

  // Detect initial viewport width from User-Agent or stored cookie
  const initialViewportWidth = getInitialViewportWidth(event.request, event.cookies);
  const isMobileDevice = initialViewportWidth < MOBILE_BREAKPOINT;

  // --- Cookie-based session auth (skip if OAuth already authenticated) ---
  if (!isOAuthRequest) {
    let sessionId = event.cookies.get(import.meta.env.VITE_SESSION_COOKIE_NAME);

    let session = await getSessionObject(sessionId);

    // Check if user is banned
    if (session.user) {
      try {
        const fullUser = await getUserFullDetails(BigInt(session.user.id));
      if (fullUser?.banned) {
        // Check if ban has expired
        if (fullUser.banned_until && new Date(fullUser.banned_until) < new Date()) {
          // Ban expired - could auto-unban here, but for now just allow
        } else {
          // User is still banned - clear session and deny access
          sessions.delete(sessionId);
          event.cookies.delete(import.meta.env.VITE_SESSION_COOKIE_NAME, { path: '/', domain: import.meta.env.VITE_DOMAIN });
          event.cookies.delete(IMPERSONATE_COOKIE, { path: '/', domain: import.meta.env.VITE_DOMAIN });

          // Allow access to logout route
          if (!event.url.pathname.startsWith('/discord/logout')) {
            return new Response(null, {
              status: 302,
              headers: { Location: '/banned' }
            });
          }
        }
      }

      // Sync mutable user fields from DB so changes apply without re-login
      if (fullUser) {
        session.user.verified = fullUser.verified;
        if (fullUser.locked) {
          session.user.locked = true;
          session.user.locked_reason = fullUser.locked_reason;
        } else {
          session.user.locked = false;
          session.user.locked_reason = null;
        }
      }
    } catch (e) {
      // If we can't check ban status, continue with session
      console.error('Error checking ban status:', e);
    }
  }

  // Check for admin impersonation (requires admin.impersonate grant)
  if (session.user && session.user.grants?.includes('admin.impersonate')) {
    const impersonateUserId = event.cookies.get(IMPERSONATE_COOKIE);
    if (impersonateUserId) {
      try {
        const impersonatedUser = await getUserById(BigInt(impersonateUserId));
        if (impersonatedUser) {
          // Resolve grants for the impersonated user
          const impersonatedGrants = await resolveUserGrants(BigInt(impersonatedUser.id));
          impersonatedUser.grants = [...impersonatedGrants];
          impersonatedUser.administrator = impersonatedGrants.has('admin.panel');

          // Store real user and replace user with impersonated user
          session = {
            ...session,
            realUser: session.user,
            user: impersonatedUser
          };
        }
      } catch (e) {
        // Invalid impersonation cookie, clear it
        event.cookies.delete(IMPERSONATE_COOKIE, { path: '/', domain: import.meta.env.VITE_DOMAIN });
      }
    }
  }

    event.locals.session = session;

    // Set cookie refresh after resolve
    var cookieSessionId = sessionId;
  } // end if (!isOAuthRequest)

  event.locals.initialViewportWidth = initialViewportWidth;
  event.locals.isMobileDevice = isMobileDevice;

  const _requestStart = Date.now();
  const response = await resolve(event);

  // Fire-and-forget: record route analytics (non-blocking)
  if (_recordVisit) { try { _recordVisit(event, response, _requestStart); } catch (_) {} }

  // Record error responses (4xx/5xx) with diagnostics
  if (_recordError && response.status >= 400) {
    try {
      // Clone response to read body without consuming the original
      const cloned = response.clone();
      cloned.text().then(body => {
        _recordError(event, response, _requestStart, body);
      }).catch(() => {
        _recordError(event, response, _requestStart, null);
      });
    } catch (_) {}
  }

  // Refresh session cookie for cookie-based auth
  if (!isOAuthRequest && cookieSessionId) {
    response.headers['set-cookie'] = `${import.meta.env.VITE_SESSION_COOKIE_NAME}=${cookieSessionId}; HttpOnly; Path=/; SameSite=Lax; Max-Age=${SESSION_COOKIE_MAX_AGE}; Domain=${import.meta.env.VITE_DOMAIN}; Secure=${import.meta.env.MODE === 'development' ? false : true};`;
  }

  // Add CORS headers for OAuth-authenticated API responses
  if (isOAuthRequest) {
    response.headers.set('Access-Control-Allow-Origin', '*');
    response.headers.set('Access-Control-Allow-Headers', 'Authorization, Content-Type');
  }

  // Clickjacking protection: allow framing only for embed map routes
  const isEmbedRoute = event.url.pathname.startsWith('/maps') && event.url.searchParams.get('embed') === '1';
  if (!isEmbedRoute) {
    response.headers.set('X-Frame-Options', 'SAMEORIGIN');
  }

  return response;
}

export async function getSession(request) {
  return request.locals.session;
}

// Log uncaught errors with route information for easier debugging of 500s
export function handleError({ error, event }) {
  // Try to detect an HTTP status; default to 500 when unknown
  const status = (error && (error.status || error.statusCode)) || 500;
  if (status >= 500 && status < 600) {
    try {
      const routeId = event?.route?.id ?? 'unknown-route';
      const pathname = event?.url?.pathname ?? 'unknown-path';
      const href = event?.url?.href ?? event?.request?.url ?? 'unknown-url';
      console.error(`[${status}] route: ${routeId} path: ${pathname} url: ${href}`, error);

      // Store error message/stack in error_log for the matching row
      if (_recordErrorMessage) {
        const msg = error?.stack || error?.message || String(error);
        _recordErrorMessage(routeId, pathname, msg).catch(() => {});
      }
    } catch (e) {
      console.error(`[${status}] error while logging route for error`, e, error);
    }
  }
  // Suppress logging for 404 and other non-5xx by default
  return {
    message: status >= 500 ? 'Internal Server Error' : undefined
  };
}

async function getSessionObject(sessionId) {
  if (!sessionId) {
    return {};
  }

  let sessionData = sessions.get(sessionId);
  let dbSession = null;

  if (!sessionData) {
    const [user, session] = await Promise.all([
      getUserFromSession(sessionId),
      dbGetSession(sessionId)
    ]);

    if (!session) {
      return {};
    }

    dbSession = session;

    // Resolve role-based grants for the user
    if (user) {
      try {
        const userGrants = await resolveUserGrants(BigInt(user.id));
        user.grants = [...userGrants];
        user.administrator = userGrants.has('admin.panel');
      } catch (e) {
        console.error('Error resolving user grants:', e);
        user.grants = [];
      }
      // Unverified users get no grants — verification is a prerequisite
      if (!user.verified) {
        user.grants = [];
        user.administrator = false;
      }
    }

    sessionData = {
      user,
      expires: session.expires,
      refreshToken: session.refresh_token,
      grantsCachedAt: Date.now()
    };

    sessions.set(sessionId, sessionData);
  }

  // Periodically re-resolve grants so role/grant changes apply quickly
  if (sessionData.user) {
    const now = Date.now();
    if (!sessionData.grantsCachedAt || now - sessionData.grantsCachedAt > GRANTS_REFRESH_INTERVAL) {
      try {
        const freshGrants = await resolveUserGrants(BigInt(sessionData.user.id));
        sessionData.user.grants = [...freshGrants];
        sessionData.user.administrator = freshGrants.has('admin.panel');
        sessionData.grantsCachedAt = now;
      } catch (e) {
        console.error('Error refreshing user grants:', e);
      }
      // Unverified users get no grants — verification is a prerequisite
      if (!sessionData.user.verified) {
        sessionData.user.grants = [];
        sessionData.user.administrator = false;
      }
    }
  }

  const now = Math.floor(Date.now() / 1000);

  // Check if token needs refresh (within 2 days of expiry)
  if (now > sessionData.expires - REFRESH_THRESHOLD) {
    try {
      // Get the refresh token from cache or database
      let refreshToken = sessionData.refreshToken;
      if (!refreshToken) {
        // Fallback: fetch from database if not in cache
        dbSession = dbSession || await dbGetSession(sessionId);
        refreshToken = dbSession?.refresh_token;
      }

      if (!refreshToken) {
        console.warn('No refresh token available for session, clearing session');
        sessions.delete(sessionId);
        return {};
      }

      const response = await handleRefresh(refreshToken);

      // If response errored, log and return empty (session expired)
      if (response.error) {
        console.warn('Token refresh failed:', response.error, response.error_description);
        sessions.delete(sessionId);
        return {};
      }

      // Refresh successful - update everything
      const discordUser = await getUserInfo(response.access_token);
      const newExpires = Math.floor(Date.now() / 1000) + response.expires_in;

      // Update database and user info
      const [user] = await Promise.all([
        upsertUser(discordUser),
        updateSession(sessionId, response.access_token, response.refresh_token, newExpires)
      ]);

      // Resolve role-based grants after refresh
      if (user) {
        try {
          const userGrants = await resolveUserGrants(BigInt(user.id));
          user.grants = [...userGrants];
          user.administrator = userGrants.has('admin.panel');
        } catch (e) {
          console.error('Error resolving user grants after refresh:', e);
          user.grants = [];
        }
        // Unverified users get no grants — verification is a prerequisite
        if (!user.verified) {
          user.grants = [];
          user.administrator = false;
        }
      }

      sessionData = {
        user,
        expires: newExpires,
        refreshToken: response.refresh_token,
        grantsCachedAt: Date.now()
      };

      sessions.set(sessionId, sessionData);
      console.log('Token refreshed successfully, new expiry:', new Date(newExpires * 1000).toISOString());

    } catch (error) {
      console.error('Error during token refresh:', error);
      // Don't clear session on transient errors, just log and continue with existing session
      // Only clear if it's clearly an auth error
      if (error.message?.includes('invalid_grant') || error.message?.includes('unauthorized')) {
        sessions.delete(sessionId);
        return {};
      }
    }
  }

  return {
    id: sessionId,
    user: sessionData.user,
    expires: sessionData.expires
  };
}
