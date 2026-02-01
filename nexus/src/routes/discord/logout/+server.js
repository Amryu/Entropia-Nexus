//@ts-nocheck
import { deleteSession, getSession } from '$lib/server/db.js';
import { handleRevoke } from '$lib/server/discord.js';

export async function GET({ cookies, url }) {
  let sessionId = cookies.get(import.meta.env.VITE_SESSION_COOKIE_NAME);

  // Get redirect URL from query params, default to home page
  // Validate that redirect is a relative URL to prevent open redirect
  let redirectUrl = url.searchParams.get('redirect') || '/';
  if (!redirectUrl.startsWith('/') || redirectUrl.startsWith('//')) {
    redirectUrl = '/';
  }

  if (!sessionId) {
    return new Response(null, {
      status: 302,
      headers: {
        location: redirectUrl
      }
    });
  }

  let session = await getSession(sessionId);

  if (session) {
    // Use try-catch to handle mock tokens from test users gracefully
    try {
      await Promise.all([
        session.access_token ? handleRevoke(session.access_token) : Promise.resolve(),
        session.refresh_token ? handleRevoke(session.refresh_token) : Promise.resolve(),
        deleteSession(sessionId)
      ]);
    } catch (e) {
      // Still delete session even if token revocation fails
      console.error('Error during logout:', e);
      await deleteSession(sessionId);
    }
  }

  cookies.set(import.meta.env.VITE_SESSION_COOKIE_NAME, '', {
    maxAge: 0,
    path: '/',
    secure: import.meta.env.MODE === 'development' ? false : true,
    httpOnly: true,
    sameSite: 'Lax',
    domain: import.meta.env.VITE_DOMAIN
  });

  return new Response(null, {
    status: 302,
    headers: {
      location: redirectUrl
    }
  });
}