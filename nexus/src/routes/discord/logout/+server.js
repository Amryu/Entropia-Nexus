//@ts-nocheck
import { deleteSession, getSession } from '$lib/server/db.js';
import { handleRevoke } from '$lib/server/discord.js';

export async function GET({ cookies }) {
  let sessionId = cookies.get(import.meta.env.VITE_SESSION_COOKIE_NAME);

  if (!sessionId) {
    return new Response(null, {
      status: 302,
      headers: {
        location: '/'
      }
    });
  }

  let session = await getSession(sessionId);

  if (session) {
    await Promise.all([
      handleRevoke(session.accessToken),
      handleRevoke(session.refreshToken),
      deleteSession(sessionId)
    ]);
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
      location: '/'
    }
  });
}