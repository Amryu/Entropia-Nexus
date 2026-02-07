//@ts-nocheck
let dbGetSession, getUserFromSession, updateSession, upsertUser, getUserInfo, handleRefresh, getUserById, getUserFullDetails, resolveUserGrants;

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

  const discord = await import('$lib/server/discord');
  getUserInfo = discord.getUserInfo;
  handleRefresh = discord.handleRefresh;
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
  let sessionId = event.cookies.get(import.meta.env.VITE_SESSION_COOKIE_NAME);

  let session = await getSessionObject(sessionId);

  // Detect initial viewport width from User-Agent or stored cookie
  const initialViewportWidth = getInitialViewportWidth(event.request, event.cookies);
  const isMobileDevice = initialViewportWidth < MOBILE_BREAKPOINT;

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

  const response = await resolve({
    ...event,
    locals: {
      ...event.locals,
      session,
      initialViewportWidth,
      isMobileDevice
    }
  });

  if (sessionId) {
    response.headers['set-cookie'] = `${import.meta.env.VITE_SESSION_COOKIE_NAME}=${sessionId}; HttpOnly; Path=/; SameSite=Lax; Max-Age=${SESSION_COOKIE_MAX_AGE}; Domain=${import.meta.env.VITE_DOMAIN}; Secure=${import.meta.env.MODE === 'development' ? false : true};`;
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