//@ts-nocheck
let dbGetSession, getUserFromSession, updateSession, upsertUser, getUserInfo, handleRefresh;

if (import.meta.env.SSR) {
  const db = await import('$lib/server/db');
  dbGetSession = db.getSession;
  getUserFromSession = db.getUserFromSession;
  updateSession = db.updateSession;
  upsertUser = db.upsertUser;

  const discord = await import('$lib/server/discord');
  getUserInfo = discord.getUserInfo;
  handleRefresh = discord.handleRefresh;
}

const sessions = new Map();

export async function handle({ event, resolve }) {
  let sessionId = event.cookies.get(import.meta.env.VITE_SESSION_COOKIE_NAME);

  let session = await getSessionObject(sessionId);
  
  const response = await resolve({
    ...event,
    locals: {
      ...event.locals,
      session
    }
  });

  if (sessionId) {
    response.headers['set-cookie'] = `${import.meta.env.VITE_SESSION_COOKIE_NAME}=${sessionId}; HttpOnly; Path=/; SameSite=Lax; Max-Age=${60 * 60 * 24 * 7}; Domain=${import.meta.env.VITE_DOMAIN}; Secure=${import.meta.env.MODE === 'development' ? false : true};`;
  }

  return response;
}

export async function getSession(request) {
  return request.locals.session;
}

const ONE_DAY = 60 * 60 * 24;

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

  if (!sessionData) {
    const [user, session] = await Promise.all([
      getUserFromSession(sessionId),
      dbGetSession(sessionId)
    ]);

    if (!session) {
      return {};
    }

    sessionData = { user, expires: session.expires };

    sessions.set(sessionId, sessionData);
  }

  if (Date.now() / 1000 > sessionData.expires - ONE_DAY) {
    const response = await handleRefresh(sessionId);

    // If response errored, assume the refresh token expired
    if (response.error) {
      return {};
    }

    const discordUser = await getUserInfo(response.access_token);

    const [user] = Promise.all([
      upsertUser(discordUser),
      updateSession(sessionId, response.access_token, response.refresh_token, Math.floor(Date.now() / 1000) + response.expires_in)
    ]);

    sessionData = { user, expires: Math.floor(Date.now() / 1000) + response.expires_in };

    sessions.set(sessionId, sessionData);
  }

  return {
    id: sessionId,
    ...sessionData
  };
}